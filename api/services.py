"""Business logic bridging the composite building explorer API to buildstock_processor.

Every endpoint in `api/main.py` is a thin wrapper around a function here. Keeping this layer separate
(and free of any FastAPI/HTTP concepts) makes it straightforward to unit test the pure logic (see
`tests/test_api_services.py`) without needing a running server or real network access for everything.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import pandas as pd

from api.config import Settings
from api.mos_export import MosExportError, build_thermal_load_mos
from api.schemas import (
    AvailableCountiesResponse,
    AvailableStatesResponse,
    ComponentSummary,
    CompositeComponentSpec,
    CompositeResolveRequest,
    CompositeResolveResponse,
    EndUseValue,
    EnergyStarTypeInfo,
    MeasureInfo,
    MeasureSavings,
    MeasuresCompareRequest,
    MeasuresCompareResponse,
    MeasuresListResponse,
    MetadataSummaryRequest,
    MetadataSummaryResponse,
    MosExportRequest,
    ResolvedComponent,
    TimeseriesRequest,
    TimeseriesResponse,
)
from buildstock_processor import location
from buildstock_processor.composite import (
    CompositeBuildingType,
    CompositeComponent,
    normalize_time_series_columns,
    pull_composite_time_series,
)
from buildstock_processor.comstock import ComStockProcessor
from buildstock_processor.data_dictionary import result_variables_from_columns
from buildstock_processor.energy_star_crosswalk import (
    energy_star_crosswalk,
    map_energy_star_property_type,
)
from buildstock_processor.resstock import ResStockProcessor

# Fuel/end-use source names that are stock-level aggregates, not distinct fuels -- excluded from the
# by-fuel breakdown so they don't double-count alongside their constituent fuels.
_AGGREGATE_SOURCES = {"site_energy"}
# end_use labels that aren't real building end uses (accounting/rollup categories).
_NON_END_USE_LABELS = {"total", "net", "purchased"}

# Site energy is published in kWh; EUI is conventionally reported in kBtu/ft2 (the ENERGY STAR
# Portfolio Manager / DOE convention), so we convert with the standard kWh->kBtu unit factor
# (this is a unit conversion only, not a source-to-site energy conversion).
KWH_TO_KBTU = 3.412141633

DEFAULT_METRIC_COLUMNS = [
    "out.electricity.total.energy_consumption",
    "out.natural_gas.total.energy_consumption",
    "out.district_cooling.total.energy_consumption",
    "out.district_heating.total.energy_consumption",
    "out.fuel_oil.total.energy_consumption",
    "out.propane.total.energy_consumption",
    "out.site_energy.total.energy_consumption",
]
DEFAULT_HEATING_COLUMNS = [
    "out.electricity.heating.energy_consumption",
    "out.natural_gas.heating.energy_consumption",
    "out.district_heating.heating.energy_consumption",
    "out.fuel_oil.heating.energy_consumption",
    "out.propane.heating.energy_consumption",
]
DEFAULT_COOLING_COLUMNS = [
    "out.electricity.cooling.energy_consumption",
    "out.district_cooling.cooling.energy_consumption",
]


class ServiceError(ValueError):
    """A user-facing error (bad input, no data found, etc.) -- translated to an HTTP 400 by the API layer."""


def _cache_dir_for_product(base_cache_dir: Path, product: str) -> Path:
    path = base_cache_dir / product
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_processor(
    base_cache_dir: Path,
    product: str,
    state: str,
    county_name: str | list[str],
    building_type: str,
    upgrade: str,
    min_sqft: float | None,
    max_sqft: float | None,
) -> ComStockProcessor | ResStockProcessor:
    base_dir = _cache_dir_for_product(base_cache_dir, product)
    kwargs: dict[str, Any] = {
        "state": state,
        "county_name": county_name,
        "building_type": building_type,
        "upgrade": upgrade,
        "base_dir": base_dir,
        "min_sqft": min_sqft,
        "max_sqft": max_sqft,
    }
    if product == "comstock":
        return ComStockProcessor(**kwargs)
    return ResStockProcessor(**kwargs)


def _find_column(columns: pd.Index, prefix: str) -> str | None:
    """Find a metadata column matching `prefix`, tolerating an annual-metadata "..<unit>" suffix."""
    for column in columns:
        if column == prefix or column.startswith(prefix + ".."):
            return str(column)
    return None


def _target_sqft_map(components: list[CompositeComponentSpec]) -> dict[tuple[str, str], float] | None:
    """Return `{(product, building_type): sqft}` if every component has an absolute target square footage
    set, else `None` (fraction mode). Schema validation on the resolve endpoint keeps a resolved composite
    consistently all-fraction or all-sqft, but callers can also build `CompositeComponentSpec`s directly, so
    this treats "any missing" as fraction mode rather than assuming consistency.
    """
    if not components or any(c.sqft is None for c in components):
        return None
    return {(c.product, c.building_type): c.sqft for c in components if c.sqft is not None}


def _sqft_bounds_warning(
    component: CompositeComponentSpec, metadata: pd.DataFrame, sqft_column: str | None, target_sqft: float
) -> str | None:
    """Warn if `target_sqft` falls outside the observed `in.sqft` range of `metadata`'s sampled buildings.

    E.g. if a user picks "LargeOffice" but every sampled LargeOffice building in this state is >10,000 sqft,
    entering 8,000 sqft extrapolates well beyond what the underlying BuildStock data actually represents --
    the result is still computed (see `get_metadata_summary`/`get_composite_timeseries`/`compare_measures`),
    but this surfaces a warning so the user knows to treat it with caution.
    """
    if not sqft_column:
        return None
    sqft_values = pd.to_numeric(metadata[sqft_column], errors="coerce").dropna()
    if sqft_values.empty:
        return None
    observed_min, observed_max = float(sqft_values.min()), float(sqft_values.max())
    if observed_min <= target_sqft <= observed_max:
        return None
    label = component.label or component.building_type
    return (
        f"{label} ({component.product}): entered {target_sqft:,.0f} sqft is outside the {observed_min:,.0f}-{observed_max:,.0f} sqft range "
        f"observed in the sampled {component.building_type} buildings -- results are extrapolated beyond the underlying data and may not be reliable."
    )


def list_energy_star_types() -> list[EnergyStarTypeInfo]:
    return [
        EnergyStarTypeInfo(
            energy_star_property_type=mapping.energy_star_property_type,
            buildstock_product=mapping.buildstock_product,
            buildstock_building_type=mapping.buildstock_building_type,
            match_quality=mapping.match_quality,
            notes=mapping.notes,
        )
        for mapping in energy_star_crosswalk()
    ]


def resolve_composite(request: CompositeResolveRequest) -> CompositeResolveResponse:
    resolved: list[ResolvedComponent] = []
    unmapped: list[str] = []

    # Schema validation guarantees every component is consistently either all-fraction or all-sqft.
    sqft_mode = any(entry.sqft is not None for entry in request.components)
    total_sqft = sum(entry.sqft or 0.0 for entry in request.components) if sqft_mode else None

    for entry in request.components:
        # In sqft mode, `fraction` is derived (share of the total entered sqft, including unmapped
        # entries) purely so downstream renormalization/display logic can stay identical to fraction mode.
        # entry.sqft/entry.fraction being unexpectedly None here would mean EnergyStarComponentIn's own
        # validator (exactly one of fraction/sqft) was bypassed -- treated as a service-level bug, not a
        # user input error.
        if sqft_mode:
            if entry.sqft is None or not total_sqft:
                raise ServiceError(f"Component {entry.energy_star_property_type!r} is missing a valid sqft value in sqft mode.")
            entry_fraction = entry.sqft / total_sqft
        else:
            if entry.fraction is None:
                raise ServiceError(f"Component {entry.energy_star_property_type!r} is missing a valid fraction value in fraction mode.")
            entry_fraction = entry.fraction
        mapping = map_energy_star_property_type(entry.energy_star_property_type)
        if mapping is None:
            resolved.append(
                ResolvedComponent(
                    energy_star_property_type=entry.energy_star_property_type,
                    product=None,
                    building_type=None,
                    fraction=entry_fraction,
                    sqft=entry.sqft,
                    match_quality="unmapped",
                    notes="Not a recognized ENERGY STAR Portfolio Manager property type.",
                )
            )
            unmapped.append(entry.energy_star_property_type)
            continue

        resolved.append(
            ResolvedComponent(
                energy_star_property_type=entry.energy_star_property_type,
                product=mapping.buildstock_product,
                building_type=mapping.buildstock_building_type,
                fraction=entry_fraction,
                sqft=entry.sqft,
                match_quality=mapping.match_quality,
                notes=mapping.notes,
            )
        )
        if mapping.match_quality == "unmapped":
            unmapped.append(entry.energy_star_property_type)

    resolvable_source = [r for r in resolved if r.product is not None and r.building_type is not None]
    resolvable_total = sum(r.fraction for r in resolvable_source)
    resolvable = [
        CompositeComponentSpec(
            product=r.product,
            building_type=r.building_type,
            fraction=(r.fraction / resolvable_total) if resolvable_total else 0.0,
            sqft=r.sqft,
            label=r.energy_star_property_type,
        )
        for r in resolvable_source
    ]

    return CompositeResolveResponse(
        ok=True,
        components=resolved,
        resolvable=resolvable,
        unmapped=unmapped,
        total_fraction=sum(r.fraction for r in resolved),
        total_sqft=total_sqft,
    )


def get_metadata_summary(request: MetadataSummaryRequest, settings: Settings) -> MetadataSummaryResponse:
    component_summaries: list[ComponentSummary] = []
    by_fuel: dict[str, float] = {}
    by_end_use: dict[str, float] = {}
    weighted_sqft = 0.0
    weighted_site_energy = 0.0
    weighted_building_count = 0
    warnings: list[str] = []

    target_sqft_map = _target_sqft_map(request.components)

    for component in request.components:
        processor = _build_processor(
            settings.cache_dir,
            component.product,
            request.state,
            request.county_name,
            component.building_type,
            request.upgrade,
            request.min_sqft,
            request.max_sqft,
        )
        try:
            metadata = processor.process_metadata(save_dir=processor.base_dir)
        except Exception as exc:
            raise ServiceError(f"Failed to download metadata for {component.building_type} ({component.product}): {exc}") from exc

        if metadata.empty:
            raise ServiceError(f"No buildings found for {component.building_type} ({component.product}) in state={request.state!r}.")

        sqft_column = _find_column(metadata.columns, "in.sqft")
        avg_sqft = float(metadata[sqft_column].mean()) if sqft_column else 0.0

        site_energy_column = _find_column(metadata.columns, "out.site_energy.total.energy_consumption")
        annual_site_energy = float(metadata[site_energy_column].mean()) if site_energy_column else 0.0

        # Site EUI (energy per sqft) is an intensity, so it's unaffected by sqft-mode scaling either way.
        eui = (annual_site_energy * KWH_TO_KBTU) / avg_sqft if avg_sqft else 0.0

        if target_sqft_map is not None:
            if not avg_sqft:
                raise ServiceError(
                    f"Could not determine floor area for {component.building_type} ({component.product}) to scale by target square footage."
                )
            # `scale` replaces `component.fraction` below -- it turns the population-average sqft/energy
            # for this building type into the values for an *actual* building of the entered square
            # footage, rather than a floor-area share of an unspecified total.
            display_sqft = target_sqft_map[(component.product, component.building_type)]
            scale = display_sqft / avg_sqft
            display_energy = eui / KWH_TO_KBTU * display_sqft
            warning = _sqft_bounds_warning(component, metadata, sqft_column, display_sqft)
            if warning:
                warnings.append(warning)
        else:
            scale = component.fraction
            display_sqft = avg_sqft
            display_energy = annual_site_energy

        component_summaries.append(
            ComponentSummary(
                product=component.product,
                building_type=component.building_type,
                label=component.label,
                fraction=component.fraction,
                building_count=len(metadata),
                avg_sqft=display_sqft,
                annual_site_energy_kwh=display_energy,
                site_eui_kbtu_per_ft2=eui,
            )
        )

        # These accumulation lines are identical for both modes -- only `scale`'s definition differs. In
        # sqft mode, `scale * avg_sqft == target_sqft` and `scale * annual_site_energy == intensity *
        # target_sqft`, so summing across components yields the composite's total floor area and total
        # energy for that floor area (rather than a fraction-weighted average of population means).
        weighted_sqft += scale * avg_sqft
        weighted_site_energy += scale * annual_site_energy
        weighted_building_count += len(metadata)

        for variable in result_variables_from_columns(metadata.columns):
            if variable.metric != "energy_consumption" or variable.source is None or variable.end_use is None:
                continue
            value = pd.to_numeric(metadata[variable.name], errors="coerce").mean()
            if pd.isna(value):
                continue
            if variable.end_use == "total" and variable.source not in _AGGREGATE_SOURCES:
                by_fuel[variable.source] = by_fuel.get(variable.source, 0.0) + scale * float(value)
            if variable.end_use not in _NON_END_USE_LABELS and variable.source not in _AGGREGATE_SOURCES:
                by_end_use[variable.end_use] = by_end_use.get(variable.end_use, 0.0) + scale * float(value)

    weighted_eui = (weighted_site_energy * KWH_TO_KBTU) / weighted_sqft if weighted_sqft else 0.0

    return MetadataSummaryResponse(
        ok=True,
        state=request.state,
        upgrade=request.upgrade,
        components=component_summaries,
        weighted_building_count=weighted_building_count,
        weighted_avg_sqft=weighted_sqft,
        weighted_annual_site_energy_kwh=weighted_site_energy,
        weighted_site_eui_kbtu_per_ft2=weighted_eui,
        by_fuel=sorted((EndUseValue(key=k, annual_energy_kwh=v) for k, v in by_fuel.items()), key=lambda item: -item.annual_energy_kwh),
        by_end_use=sorted(
            (EndUseValue(key=k, annual_energy_kwh=v) for k, v in by_end_use.items()), key=lambda item: -item.annual_energy_kwh
        ),
        cache_dir=str(settings.cache_dir),
        warnings=warnings,
    )


def _resample_hourly(data_frame: pd.DataFrame, columns: list[str], timestamp_column: str = "timestamp") -> pd.DataFrame:
    """Resample to hourly sums, then trim to exactly 8760 rows (a full year).

    Resampling a full year of period-ending BuildStock time series lands one extra row exactly at the
    following year's start (e.g. 2019-01-01T00:00:00 after a full 2018), which resample('h') buckets as
    its own (near-empty) hour. Dropping any rows beyond the first 8760 gives callers a clean, standard
    8760-row year for heat maps/load duration curves.
    """
    available = [column for column in columns if column in data_frame.columns]
    indexed = data_frame.set_index(timestamp_column)
    resampled = indexed[available].resample("h").sum() if available else indexed.resample("h").size().to_frame("_count").iloc[:, :0]
    resampled.index.name = timestamp_column
    return resampled.reset_index().iloc[:8760]


def _frame_to_records(data_frame: pd.DataFrame, timestamp_column: str = "timestamp") -> list[dict[str, Any]]:
    """Convert a time series DataFrame to a list of JSON-friendly records.

    Uses column-name-based access (`.items()`/`.loc`) rather than `itertuples()`/`to_dict("records")`'s
    namedtuple path, since BuildStock column names contain dots and aren't valid Python identifiers --
    `itertuples()` silently renames those columns to `_1`, `_2`, ... instead of raising.
    """
    value_columns = [column for column in data_frame.columns if column != timestamp_column]
    records: list[dict[str, Any]] = []
    for _, row in data_frame.iterrows():
        record: dict[str, Any] = {"timestamp": pd.Timestamp(row[timestamp_column]).isoformat()}
        for column in value_columns:
            value = row[column]
            record[column] = None if pd.isna(value) else float(value)
        records.append(record)
    return records


def _pull_timeseries(
    components: list[CompositeComponentSpec],
    settings: Settings,
    state: str,
    county_name: str | list[str],
    upgrade: str,
    min_sqft: float | None,
    max_sqft: float | None,
    bldg_ids: dict[tuple[str, str], int] | None,
    value_columns: list[str] | None,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame], list[str]]:
    """Download/combine time series for 1+ composite components.

    `CompositeBuildingType` requires 2+ components (a genuine mix), so a single-component request (just
    one ENERGY STAR/building type, no mixing) is handled directly here instead.

    If every component has an absolute target square footage set (`CompositeComponentSpec.sqft`), the
    result is scaled to represent an actual building of that square footage: each component's time series
    is multiplied by `target_sqft / representative_building_sqft` instead of `component.fraction`. The
    third return value is a list of data-quality warnings (see `_sqft_bounds_warning`).

    `upgrade` may be a bare id (e.g. "5", applied uniformly to every component -- today's behavior) or a
    `"<product>:<upgrade_id>"`-prefixed id (e.g. "comstock:5", reusing `_parse_measure_selection`), which
    applies that upgrade only to components of that product; every other component is pulled at baseline
    ("0") instead. This lets a single measure's effect be isolated in a mixed composite's time series the
    same way `compare_measures()` already isolates it in the annual aggregates.
    """
    target_sqft_map = _target_sqft_map(components)
    upgrade_product, upgrade_id = _parse_measure_selection(upgrade)

    def _effective_upgrade(component_product: str) -> str:
        return upgrade_id if (upgrade_product is None or upgrade_product == component_product) else "0"

    if len(components) == 1:
        component = components[0]
        key = (component.product, component.building_type)
        effective_upgrade = _effective_upgrade(component.product)
        processor = _build_processor(
            settings.cache_dir, component.product, state, county_name, component.building_type, effective_upgrade, min_sqft, max_sqft
        )

        sample_bldg_id = (bldg_ids or {}).get(key)
        sample_sqft: float | None = None
        warnings: list[str] = []
        if sample_bldg_id is not None and target_sqft_map is None:
            sample = pd.DataFrame({"bldg_id": [sample_bldg_id], "in.state": [state]})
        else:
            metadata = processor.process_metadata(save_dir=processor.base_dir)
            if metadata.empty:
                raise ServiceError(f"No buildings found for {key} in state={state!r}.")
            if sample_bldg_id is not None:
                metadata = metadata[metadata["bldg_id"] == sample_bldg_id]
                if metadata.empty:
                    raise ServiceError(f"bldg_id {sample_bldg_id} not found in metadata for {key}.")
            sqft_column = _find_column(metadata.columns, "in.sqft") if target_sqft_map is not None else None
            select_columns = ["bldg_id", "in.state"] + ([sqft_column] if sqft_column else [])
            sample = metadata[select_columns].drop_duplicates().head(1)
            if sqft_column:
                sample_sqft = float(sample[sqft_column].iloc[0])
                if target_sqft_map is not None:
                    warning = _sqft_bounds_warning(component, metadata, sqft_column, target_sqft_map[key])
                    if warning:
                        warnings.append(warning)

        ts_dir = processor.base_dir / "timeseries" / f"upgrade_{effective_upgrade}"
        ts_dir.mkdir(parents=True, exist_ok=True)
        paths, _building_ids = processor.process_building_time_series(sample[["bldg_id", "in.state"]], save_dir=ts_dir)
        if not paths:
            raise ServiceError(f"Failed to download time series for {key}.")

        raw = pd.read_parquet(paths[0])
        normalized = normalize_time_series_columns(raw)

        if target_sqft_map is not None:
            if not sample_sqft:
                raise ServiceError(f"Could not determine floor area for {key} to scale by target square footage.")
            scale = target_sqft_map[key] / sample_sqft
            numeric_columns = [
                column
                for column in normalized.columns
                if column not in {"timestamp", "bldg_id"} and pd.api.types.is_numeric_dtype(normalized[column])
            ]
            normalized = normalized.copy()
            normalized[numeric_columns] = normalized[numeric_columns] * scale

        available_columns = [column for column in (value_columns or []) if column in normalized.columns] or None
        combined = normalized[["timestamp", *available_columns]] if available_columns else normalized
        return combined, {key: raw}, warnings

    warnings = []
    if target_sqft_map is not None:
        for component in components:
            key = (component.product, component.building_type)
            processor = _build_processor(
                settings.cache_dir,
                component.product,
                state,
                county_name,
                component.building_type,
                _effective_upgrade(component.product),
                min_sqft,
                max_sqft,
            )
            metadata = processor.process_metadata(save_dir=processor.base_dir)
            if metadata.empty:
                continue
            sqft_column = _find_column(metadata.columns, "in.sqft")
            warning = _sqft_bounds_warning(component, metadata, sqft_column, target_sqft_map[key])
            if warning:
                warnings.append(warning)

    upgrade_overrides: dict[tuple[str, str], str] | None = (
        {(c.product, c.building_type): _effective_upgrade(c.product) for c in components} if upgrade_product is not None else None
    )
    composite = CompositeBuildingType(
        name="API composite",
        components=tuple(CompositeComponent(product=c.product, building_type=c.building_type, fraction=c.fraction) for c in components),
    )
    combined, component_series = pull_composite_time_series(
        composite,
        save_dir=settings.cache_dir,
        state=state,
        county_name=county_name,
        upgrade=upgrade_id,
        bldg_ids=bldg_ids,
        min_sqft=min_sqft,
        max_sqft=max_sqft,
        value_columns=value_columns,
        target_sqft=target_sqft_map,
        upgrade_by_component=upgrade_overrides,
    )
    return combined, component_series, warnings


def get_composite_timeseries(request: TimeseriesRequest, settings: Settings) -> TimeseriesResponse:
    bldg_ids = None
    if request.bldg_ids:
        bldg_ids = {}
        for key, bldg_id in request.bldg_ids.items():
            product, building_type = key.split(":", 1)
            bldg_ids[(product, building_type)] = bldg_id

    columns = request.columns or DEFAULT_METRIC_COLUMNS
    try:
        combined, _component_series, warnings = _pull_timeseries(
            request.components,
            settings,
            request.state,
            request.county_name,
            request.upgrade,
            request.min_sqft,
            request.max_sqft,
            bldg_ids,
            columns,
        )
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError(f"Failed to download/combine composite time series: {exc}") from exc

    if request.resample == "hourly":
        combined = _resample_hourly(combined, columns)

    available_columns = [column for column in columns if column in combined.columns]
    records = _frame_to_records(combined[["timestamp", *available_columns]])

    return TimeseriesResponse(
        ok=True,
        state=request.state,
        upgrade=request.upgrade,
        resample=request.resample,
        columns=available_columns,
        row_count=len(records),
        series=records,
        component_labels={f"{c.product}:{c.building_type}": c.label or f"{c.building_type} ({c.product})" for c in request.components},
        warnings=warnings,
    )


def list_measures(product: str, settings: Settings, release: str | None = None) -> MeasuresListResponse:
    processor = _build_processor(settings.cache_dir, product, settings.default_state, "All", "All", "0", None, None)
    if release:
        processor.release = release
    try:
        upgrades = processor.list_upgrades(save_dir=processor.base_dir)
    except Exception as exc:
        raise ServiceError(f"Failed to download upgrade catalog for {product}: {exc}") from exc

    return MeasuresListResponse(
        ok=True,
        product=product,
        release=processor.release,
        measures=[MeasureInfo(id=key, name=value, product=product) for key, value in upgrades.items()],
    )


def list_available_states(product: str, settings: Settings, release: str | None = None) -> AvailableStatesResponse:
    """List every 2-letter state abbreviation with published metadata for `product`, for a state dropdown."""
    try:
        states = location.list_available_states(product, save_dir=_cache_dir_for_product(settings.cache_dir, product), release=release)
    except Exception as exc:
        raise ServiceError(f"Failed to list available states for {product}: {exc}") from exc
    return AvailableStatesResponse(ok=True, product=product, states=states)


def list_available_counties(product: str, state: str, settings: Settings, release: str | None = None) -> AvailableCountiesResponse:
    """List every distinct county name published for `state` in `product`'s metadata, for a county dropdown
    dependent on the selected state. See `AvailableCountiesResponse.note` -- not every county is guaranteed
    to be represented, so "All" should always be offered as a fallback alongside this list.
    """
    try:
        counties = location.list_available_counties(
            product, state, save_dir=_cache_dir_for_product(settings.cache_dir, product), release=release
        )
    except Exception as exc:
        raise ServiceError(f"Failed to list available counties for {product}/{state}: {exc}") from exc
    return AvailableCountiesResponse(ok=True, product=product, state=state, counties=counties)


def _extract_metric_means(group: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    """Return `{column: mean value}` for each of `columns` present (after annual-metadata unit-suffix
    matching) in `group`, skipping any that are missing or all-NaN. Empty `group` yields `{}`."""
    if group.empty:
        return {}
    values: dict[str, float] = {}
    for column in columns:
        matched = _find_column(group.columns, column)
        if not matched:
            continue
        value = pd.to_numeric(group[matched], errors="coerce").mean()
        if pd.isna(value):
            continue
        values[column] = float(value)
    return values


def _extract_end_use_means(group: pd.DataFrame) -> dict[str, float]:
    """Return `{end_use: mean value summed across fuels}` for `group`'s annual metadata columns, mirroring
    `get_metadata_summary`'s `by_end_use` aggregation (e.g. "heating" sums electricity + gas + ... heating
    columns together). Empty `group` yields `{}`."""
    if group.empty:
        return {}
    values: dict[str, float] = {}
    for variable in result_variables_from_columns(group.columns):
        if variable.metric != "energy_consumption" or variable.source is None or variable.end_use is None:
            continue
        if variable.end_use in _NON_END_USE_LABELS or variable.source in _AGGREGATE_SOURCES:
            continue
        value = pd.to_numeric(group[variable.name], errors="coerce").mean()
        if pd.isna(value):
            continue
        values[variable.end_use] = values.get(variable.end_use, 0.0) + float(value)
    return values


def _parse_measure_selection(selection: str) -> tuple[str | None, str]:
    """Parse a `comparison_upgrades` entry into `(product, upgrade_id)`.

    A `"<product>:<upgrade_id>"`-prefixed entry (e.g. `"comstock:5"`) returns `("comstock", "5")` -- this
    upgrade only applies to composite components of that product; components of any other product are
    treated as staying at `baseline_upgrade` for this particular comparison. A bare entry (e.g. `"5"`,
    kept for backward compatibility) returns `(None, "5")` -- applied to every component regardless of
    product, which is only meaningful when every component shares the same upgrade catalog.
    """
    if ":" in selection:
        product, upgrade_id = selection.split(":", 1)
        if product in {"comstock", "resstock"}:
            return product, upgrade_id
    return None, selection


def compare_measures(request: MeasuresCompareRequest, settings: Settings) -> MeasuresCompareResponse:
    columns = request.columns or DEFAULT_METRIC_COLUMNS
    target_sqft_map = _target_sqft_map(request.components)
    all_products = {component.product for component in request.components}
    parsed_selections = [(selection, *_parse_measure_selection(selection)) for selection in request.comparison_upgrades]

    # Every upgrade id that might be needed, per product -- a selection with no product prefix could apply
    # to any component, so it's needed for every product present in the composite.
    upgrades_by_product: dict[str, set[str]] = {}
    for _selection, sel_product, sel_upgrade_id in parsed_selections:
        for product in [sel_product] if sel_product else all_products:
            upgrades_by_product.setdefault(product, set()).add(sel_upgrade_id)
    for product in all_products:
        upgrades_by_product.setdefault(product, set()).add(request.baseline_upgrade)

    upgrade_names_by_product: dict[str, dict[str, str]] = {}
    # selection -> column -> scale-weighted value across components
    per_selection_values: dict[str, dict[str, float]] = {}
    baseline_values: dict[str, float] = {}
    # selection -> end_use -> scale-weighted value across components (for a baseline-vs-measure stacked
    # bar chart of end uses, mirroring get_metadata_summary's by_end_use aggregation)
    per_selection_end_use: dict[str, dict[str, float]] = {}
    baseline_end_use: dict[str, float] = {}
    warnings: list[str] = []

    for component in request.components:
        processor = _build_processor(
            settings.cache_dir,
            component.product,
            request.state,
            request.county_name,
            component.building_type,
            request.baseline_upgrade,
            request.min_sqft,
            request.max_sqft,
        )
        if component.product not in upgrade_names_by_product:
            with contextlib.suppress(Exception):
                upgrade_names_by_product[component.product] = processor.list_upgrades(save_dir=processor.base_dir)

        needed_upgrades = sorted(upgrades_by_product.get(component.product, {request.baseline_upgrade}))
        try:
            combined_metadata = processor.process_metadata_for_upgrades(save_dir=processor.base_dir, upgrades=needed_upgrades)
        except Exception as exc:
            raise ServiceError(f"Failed to download upgrade metadata for {component.building_type} ({component.product}): {exc}") from exc

        if combined_metadata.empty or "upgrade" not in combined_metadata.columns:
            continue
        combined_metadata = combined_metadata.copy()
        combined_metadata["upgrade"] = combined_metadata["upgrade"].astype(str)

        if target_sqft_map is not None:
            # Floor area doesn't change across upgrades for the same building type, so the baseline
            # upgrade's group average sqft is used as the scaling denominator for every upgrade.
            sqft_column = _find_column(combined_metadata.columns, "in.sqft")
            baseline_group_for_sqft = combined_metadata[combined_metadata["upgrade"] == request.baseline_upgrade]
            avg_sqft = (
                float(pd.to_numeric(baseline_group_for_sqft[sqft_column], errors="coerce").mean())
                if sqft_column and not baseline_group_for_sqft.empty
                else 0.0
            )
            if not avg_sqft:
                raise ServiceError(
                    f"Could not determine floor area for {component.building_type} ({component.product}) to scale by target square footage."
                )
            scale = target_sqft_map[(component.product, component.building_type)] / avg_sqft
            warning = _sqft_bounds_warning(
                component, baseline_group_for_sqft, sqft_column, target_sqft_map[(component.product, component.building_type)]
            )
            if warning:
                warnings.append(warning)
        else:
            scale = component.fraction

        # This component always contributes at `baseline_upgrade` to the shared baseline total (the
        # denominator every comparison is measured against).
        baseline_group = combined_metadata[combined_metadata["upgrade"] == request.baseline_upgrade]
        for column, value in _extract_metric_means(baseline_group, columns).items():
            baseline_values[column] = baseline_values.get(column, 0.0) + scale * value
        for end_use, value in _extract_end_use_means(baseline_group).items():
            baseline_end_use[end_use] = baseline_end_use.get(end_use, 0.0) + scale * value

        # Per-selection: this component uses its own upgrade id if the selection targets its product (or
        # has no product prefix); otherwise it stays at baseline for this particular comparison, so a
        # commercial-only measure can't silently reapply an unrelated residential upgrade that happens to
        # share the same numeric id, and vice versa.
        for selection, sel_product, sel_upgrade_id in parsed_selections:
            effective_upgrade = sel_upgrade_id if (sel_product is None or sel_product == component.product) else request.baseline_upgrade
            group = combined_metadata[combined_metadata["upgrade"] == effective_upgrade]
            for column, value in _extract_metric_means(group, columns).items():
                bucket = per_selection_values.setdefault(selection, {})
                bucket[column] = bucket.get(column, 0.0) + scale * value
            for end_use, value in _extract_end_use_means(group).items():
                end_use_bucket = per_selection_end_use.setdefault(selection, {})
                end_use_bucket[end_use] = end_use_bucket.get(end_use, 0.0) + scale * value

    results: dict[str, list[MeasureSavings]] = {}
    for column in columns:
        baseline_value = baseline_values.get(column)
        if baseline_value is None:
            continue
        savings_for_column: list[MeasureSavings] = []
        for selection, sel_product, sel_upgrade_id in parsed_selections:
            upgrade_value = per_selection_values.get(selection, {}).get(column)
            if upgrade_value is None:
                continue
            if sel_product is not None:
                name = upgrade_names_by_product.get(sel_product, {}).get(sel_upgrade_id)
            else:
                name = next((names.get(sel_upgrade_id) for names in upgrade_names_by_product.values() if sel_upgrade_id in names), None)
            # Positive = savings (less energy than baseline); negative = an increase vs. baseline.
            absolute_savings = baseline_value - upgrade_value
            pct_savings = (absolute_savings / baseline_value * 100) if baseline_value else None
            savings_for_column.append(
                MeasureSavings(
                    upgrade_id=sel_upgrade_id,
                    name=name,
                    product=sel_product,  # type: ignore[arg-type]
                    baseline_kwh=baseline_value,
                    upgrade_kwh=upgrade_value,
                    absolute_savings_kwh=absolute_savings,
                    pct_savings=pct_savings,
                )
            )
        if savings_for_column:
            results[column] = savings_for_column

    return MeasuresCompareResponse(
        ok=True,
        baseline_upgrade=request.baseline_upgrade,
        comparison_upgrades=request.comparison_upgrades,
        results=results,
        warnings=warnings,
        baseline_by_end_use=sorted(
            (EndUseValue(key=k, annual_energy_kwh=v) for k, v in baseline_end_use.items()), key=lambda item: -item.annual_energy_kwh
        ),
        by_end_use={
            selection: sorted(
                (EndUseValue(key=k, annual_energy_kwh=v) for k, v in values.items()), key=lambda item: -item.annual_energy_kwh
            )
            for selection, values in per_selection_end_use.items()
        },
    )


def export_mos(request: MosExportRequest, settings: Settings) -> tuple[str, str]:
    heating_columns = request.heating_columns or DEFAULT_HEATING_COLUMNS
    cooling_columns = request.cooling_columns or DEFAULT_COOLING_COLUMNS

    try:
        combined, _component_series, warnings = _pull_timeseries(
            request.components,
            settings,
            request.state,
            request.county_name,
            request.upgrade,
            request.min_sqft,
            request.max_sqft,
            None,
            list(dict.fromkeys([*heating_columns, *cooling_columns])),
        )
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError(f"Failed to download/combine composite time series for export: {exc}") from exc

    available_heating = [column for column in heating_columns if column in combined.columns]
    available_cooling = [column for column in cooling_columns if column in combined.columns]
    if not available_heating and not available_cooling:
        raise ServiceError("None of the requested heating/cooling columns were available in the composite time series.")

    title = f"BuildStock composite thermal loads -- state={request.state}, upgrade={request.upgrade}"
    target_sqft_map = _target_sqft_map(request.components)
    if target_sqft_map is not None:
        title += f", target floor area={sum(target_sqft_map.values()):,.0f} sqft"

    try:
        mos_text = build_thermal_load_mos(
            combined,
            heating_columns=available_heating,
            cooling_columns=available_cooling,
            title=title,
            extra_comments=warnings,
        )
    except MosExportError as exc:
        raise ServiceError(str(exc)) from exc

    building_types = "-".join(f"{c.product}_{c.building_type}" for c in request.components)
    filename = f"composite_thermal_loads_{request.state}_upgrade{request.upgrade}_{building_types}.mos"
    return mos_text, filename
