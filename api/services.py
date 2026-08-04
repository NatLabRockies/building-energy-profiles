"""Business logic bridging the composite building explorer API to buildstock_processor.

Every endpoint in `api/main.py` is a thin wrapper around a function here. Keeping this layer separate
(and free of any FastAPI/HTTP concepts) makes it straightforward to unit test the pure logic (see
`tests/test_api_services.py`) without needing a running server or real network access for everything.
"""

from __future__ import annotations

import contextlib
import io
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal, TypeVar

import numpy as np
import pandas as pd

from api.config import Settings
from api.mos_export import MosExportError, build_thermal_load_mos
from api.schemas import (
    AvailableCountiesResponse,
    AvailableStatesResponse,
    BuildingEnergyModelRequest,
    BuildingEnergyModelResponse,
    BuildingTypesResponse,
    ComponentBuildingModel,
    ComponentSummary,
    CompositeComponentSpec,
    CompositeResolveRequest,
    CompositeResolveResponse,
    EndUseValue,
    EnergyStarTypeInfo,
    EuiCandidateBuilding,
    EuiCurvePoint,
    EuiDistributionRequest,
    EuiDistributionResponse,
    EuiPercentileBuildingsComponent,
    EuiPercentileBuildingsRequest,
    EuiPercentileBuildingsResponse,
    EuiPercentileSelection,
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
from buildstock_processor.building_condition import select_building_condition_sample
from buildstock_processor.composite import (
    CompositeBuildingType,
    CompositeComponent,
    find_nearest_sqft_bldg_id,
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

_PROCESSOR_CLASSES: dict[str, type[ComStockProcessor] | type[ResStockProcessor]] = {
    "comstock": ComStockProcessor,
    "resstock": ResStockProcessor,
}

# Composite components are independent to download (different processors/files), so metadata for a
# multi-component composite is fetched concurrently rather than one component at a time -- bounded
# modestly since a composite is typically a handful of components, not dozens.
_COMPONENT_FETCH_WORKERS = 8

# Generic return type for _fetch_components_concurrently() below.
_T = TypeVar("_T")

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


def _is_per_dwelling_unit_component(component: CompositeComponentSpec) -> bool:
    """True if `component` is a ResStock component, whose `in.sqft` metadata column is one sampled *dwelling's*
    own floor area (a multifamily unit OR a whole standalone single-family/mobile home -- see `resstock.py`'s
    module docstring: every ResStock metadata row is one simulated dwelling either way), not an arbitrary
    total -- unlike ComStock, where one row is one whole (possibly large) building. A `target_sqft` for a
    ResStock component is this component's *total* floor area across however many dwellings it represents,
    so it's directly comparable to `in.sqft` only for a single dwelling, not for the whole component.
    """
    return component.product == "resstock"


def _dwelling_noun(component: CompositeComponentSpec) -> str:
    """ "unit" for a ResStock multifamily building type, or "home" for a standalone single-family/mobile-home
    type (mirrors `portfolio._dwelling_count_label`'s "units"/"homes" pluralized convention).
    """
    return "unit" if "Multi-Family" in component.building_type else "home"


def _sqft_bounds_warning(
    component: CompositeComponentSpec, metadata: pd.DataFrame, sqft_column: str | None, target_sqft: float
) -> str | None:
    """Warn if `target_sqft` falls outside the observed `in.sqft` range of `metadata`'s sampled buildings.

    E.g. if a user picks "LargeOffice" but every sampled LargeOffice building in this state is >10,000 sqft,
    entering 8,000 sqft extrapolates well beyond what the underlying BuildStock data actually represents --
    the result is still computed (see `get_metadata_summary`/`get_composite_timeseries`/`compare_measures`),
    but this surfaces a warning so the user knows to treat it with caution.

    For a ResStock component (see `_is_per_dwelling_unit_component`), `in.sqft` is one sampled dwelling's
    floor area (a single apartment unit, or a single standalone home -- typically hundreds-to-low-thousands
    of sqft), while `target_sqft` is this component's total floor area across however many dwellings it
    represents -- entered as a whole neighborhood's/building's worth of sqft, it's completely normal for
    that to exceed a single dwelling's sqft (`pull_composite_time_series` picks the closest-matching real
    dwelling, then scales it up by the implied dwelling count, `target_sqft / representative_sqft` -- see
    `_sqft_scaling_note`), so only flagging it once it *exceeds* the max observed dwelling size would be a
    false positive on virtually every real multi-dwelling entry (multiple apartment units, or a subdivision
    of many homes). The only genuine extrapolation concern for this case is a target *smaller* than the
    smallest sampled dwelling, which can't represent even one whole dwelling.
    """
    if not sqft_column:
        return None
    sqft_values = pd.to_numeric(metadata[sqft_column], errors="coerce").dropna()
    if sqft_values.empty:
        return None
    observed_min, observed_max = float(sqft_values.min()), float(sqft_values.max())
    per_dwelling_unit = _is_per_dwelling_unit_component(component)
    in_bounds = target_sqft >= observed_min if per_dwelling_unit else observed_min <= target_sqft <= observed_max
    if in_bounds:
        return None
    label = component.label or component.building_type
    if per_dwelling_unit:
        noun = _dwelling_noun(component)
        return (
            f"{label} ({component.product}): entered {target_sqft:,.0f} sqft is smaller than the smallest sampled "
            f"{component.building_type} {noun} ({observed_min:,.0f} sqft) -- it doesn't represent even one whole "
            f"{noun}, so results are extrapolated beyond the underlying data and may not be reliable."
        )
    return (
        f"{label} ({component.product}): entered {target_sqft:,.0f} sqft is outside the {observed_min:,.0f}-{observed_max:,.0f} sqft range "
        f"observed in the sampled {component.building_type} buildings -- results are extrapolated beyond the underlying data and may not be reliable."
    )


def _sqft_scaling_note(component: CompositeComponentSpec, sample_sqft: float, target_sqft: float) -> str | None:
    """Inform the user when the specific representative building actually modeled for this component isn't
    the same size as their requested `target_sqft` -- e.g. "you asked for 40,000 sqft, but the closest
    available modeled building is 46,000 sqft, so results are scaled by 0.87x to represent your smaller
    target". Time series results are always scaled to `target_sqft` regardless (see
    `find_nearest_sqft_bldg_id`), so this is purely informational transparency about *how much* scaling was
    applied, distinct from `_sqft_bounds_warning`'s "this extrapolates beyond the data" concern. Returns
    `None` for a near-exact match (within 1%) to avoid noise.

    For a ResStock component (see `_is_per_dwelling_unit_component`), `sample_sqft` is one representative
    dwelling's floor area, so the scale factor here doubles as this component's implied dwelling count (e.g.
    requesting 80,000 sqft against a ~850 sqft representative unit scales by ~94x, i.e. ~94 units/homes) --
    the wording below reflects that instead of implying a single building was resized.
    """
    if not sample_sqft or not target_sqft:
        return None
    relative_diff = abs(target_sqft - sample_sqft) / sample_sqft
    if relative_diff < 0.01:
        return None
    label = component.label or component.building_type
    scale = target_sqft / sample_sqft
    direction = "smaller than" if target_sqft < sample_sqft else "larger than"
    if _is_per_dwelling_unit_component(component):
        noun = _dwelling_noun(component)
        return (
            f"{label} ({component.product}): requested {target_sqft:,.0f} sqft is {direction} the closest available modeled "
            f"{noun} ({sample_sqft:,.0f} sqft/{noun}) -- results are scaled by {scale:.2f}x, i.e. ~{scale:.1f} {noun}s of this size."
        )
    return (
        f"{label} ({component.product}): requested {target_sqft:,.0f} sqft is {direction} the closest available modeled "
        f"building ({sample_sqft:,.0f} sqft) -- results are scaled by {scale:.2f}x to represent your requested size."
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


def list_building_types(product: str) -> BuildingTypesResponse:
    """List every real ComStock/ResStock building type for `product`, for a building-type dropdown when
    entering a composite component directly instead of via the ENERGY STAR crosswalk. A plain, offline
    lookup against each processor's own `building_types` -- no network access needed."""
    return BuildingTypesResponse(ok=True, product=product, building_types=list(_PROCESSOR_CLASSES[product].building_types))


def _select_bldg_id_for_sqft(
    product: str,
    building_type: str,
    target_sqft: float,
    state: str,
    county_name: str | list[str],
    settings: Settings,
    warnings: list[str],
) -> int | None:
    """Best-effort lookup of the real sampled building closest in floor area to `target_sqft`, for
    `resolve_composite()`'s sqft-mode auto-selection. Returns `None` (and appends a warning) instead of
    raising, so one component's metadata download failing doesn't fail the whole resolve -- that component
    just falls back to each downstream endpoint's own default building selection.
    """
    try:
        processor = _build_processor(settings.cache_dir, product, state, county_name, building_type, "0", None, None)
        metadata = processor.process_metadata(save_dir=processor.base_dir)
        return find_nearest_sqft_bldg_id(metadata, target_sqft)
    except Exception as exc:
        warnings.append(f"Could not auto-select a representative building for {building_type} ({product}): {exc}")
        return None


def resolve_composite(request: CompositeResolveRequest, settings: Settings) -> CompositeResolveResponse:
    resolved: list[ResolvedComponent] = []
    unmapped: list[str] = []
    warnings: list[str] = []

    # Schema validation guarantees every component is consistently either all-fraction or all-sqft.
    sqft_mode = any(entry.sqft is not None for entry in request.components)
    total_sqft = sum(entry.sqft or 0.0 for entry in request.components) if sqft_mode else None
    # Auto-selecting a representative bldg_id needs real metadata, so it's opt-in: only happens in sqft
    # mode, and only once a state is given (fraction mode has no target size to match a building against).
    select_bldg_ids = sqft_mode and request.state is not None

    for entry in request.components:
        # Schema validation guarantees exactly one of these is set -- see EnergyStarComponentIn's own
        # validators -- and this label is only used for error messages below.
        entry_label = entry.energy_star_property_type or f"{entry.building_type} ({entry.product})"

        # In sqft mode, `fraction` is derived (share of the total entered sqft, including unmapped
        # entries) purely so downstream renormalization/display logic can stay identical to fraction mode.
        # entry.sqft/entry.fraction being unexpectedly None here would mean EnergyStarComponentIn's own
        # validator (exactly one of fraction/sqft) was bypassed -- treated as a service-level bug, not a
        # user input error.
        if sqft_mode:
            if entry.sqft is None or not total_sqft:
                raise ServiceError(f"Component {entry_label!r} is missing a valid sqft value in sqft mode.")
            entry_fraction = entry.sqft / total_sqft
        else:
            if entry.fraction is None:
                raise ServiceError(f"Component {entry_label!r} is missing a valid fraction value in fraction mode.")
            entry_fraction = entry.fraction

        if entry.product is not None and entry.building_type is not None:
            # A directly-entered ComStock/ResStock building type -- already a real BuildStock type, so
            # there's no crosswalk to resolve; just validate it against that product's known types.
            product, building_type = entry.product, entry.building_type
            if building_type not in _PROCESSOR_CLASSES[product].building_types:
                resolved.append(
                    ResolvedComponent(
                        energy_star_property_type=entry_label,
                        product=None,
                        building_type=None,
                        fraction=entry_fraction,
                        sqft=entry.sqft,
                        match_quality="unmapped",
                        notes=f"Not a recognized {product} building type.",
                    )
                )
                unmapped.append(entry_label)
                continue
            match_quality: Literal["exact", "approximate", "unmapped"] = "exact"
            notes = "Directly-selected ComStock/ResStock building type (ENERGY STAR crosswalk not used)."
        else:
            mapping = map_energy_star_property_type(entry.energy_star_property_type)
            if mapping is None:
                resolved.append(
                    ResolvedComponent(
                        energy_star_property_type=entry_label,
                        product=None,
                        building_type=None,
                        fraction=entry_fraction,
                        sqft=entry.sqft,
                        match_quality="unmapped",
                        notes="Not a recognized ENERGY STAR Portfolio Manager property type.",
                    )
                )
                unmapped.append(entry_label)
                continue
            product, building_type = mapping.buildstock_product, mapping.buildstock_building_type
            match_quality, notes = mapping.match_quality, mapping.notes

        bldg_id: int | None = None
        if select_bldg_ids and entry.sqft is not None and product is not None and building_type is not None:
            # request.state is guaranteed non-None here: select_bldg_ids is only True when it was set.
            bldg_id = _select_bldg_id_for_sqft(
                product,
                building_type,
                entry.sqft,
                request.state or "",
                request.county_name,
                settings,
                warnings,
            )

        resolved.append(
            ResolvedComponent(
                energy_star_property_type=entry_label,
                product=product,
                building_type=building_type,
                fraction=entry_fraction,
                sqft=entry.sqft,
                bldg_id=bldg_id,
                match_quality=match_quality,
                notes=notes,
            )
        )
        if match_quality == "unmapped":
            unmapped.append(entry_label)

    resolvable_source = [r for r in resolved if r.product is not None and r.building_type is not None]
    resolvable_total = sum(r.fraction for r in resolvable_source)
    resolvable = [
        CompositeComponentSpec(
            product=r.product,
            building_type=r.building_type,
            fraction=(r.fraction / resolvable_total) if resolvable_total else 0.0,
            sqft=r.sqft,
            bldg_id=r.bldg_id,
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
        warnings=warnings,
    )


def _fetch_components_concurrently[T](
    components: list[CompositeComponentSpec],
    fetch: Callable[[CompositeComponentSpec], _T],
) -> list[_T]:
    """Call `fetch(component)` for every component, concurrently when there's more than one -- each
    component downloads from its own processor/files, so they're fully independent and safe to fetch in
    parallel instead of one at a time. Returns results in the same order as `components` (`ThreadPoolExecutor.map`
    preserves input order for both results and any raised exception).
    """
    if len(components) <= 1:
        return [fetch(component) for component in components]
    with ThreadPoolExecutor(max_workers=min(len(components), _COMPONENT_FETCH_WORKERS)) as executor:
        return list(executor.map(fetch, components))


def get_metadata_summary(request: MetadataSummaryRequest, settings: Settings) -> MetadataSummaryResponse:
    component_summaries: list[ComponentSummary] = []
    by_fuel: dict[str, float] = {}
    by_end_use: dict[str, float] = {}
    weighted_sqft = 0.0
    weighted_site_energy = 0.0
    weighted_building_count = 0
    warnings: list[str] = []

    target_sqft_map = _target_sqft_map(request.components)

    def _fetch_metadata(component: CompositeComponentSpec) -> pd.DataFrame:
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
        return metadata

    metadata_by_component = _fetch_components_concurrently(request.components, _fetch_metadata)

    for component, metadata_frame in zip(request.components, metadata_by_component):
        metadata = metadata_frame
        # A pinned bldg_id (e.g. from the builder's EUI-percentile picker, or sqft-mode auto-selection)
        # means every downstream page should describe *that one real building*, not the full building
        # type's population mean -- restrict to just that row so this summary (and the Dashboard it feeds)
        # actually matches the building the user explicitly chose, instead of silently ignoring the pin and
        # showing a different (population-average) EUI than what was selected.
        if component.bldg_id is not None and "bldg_id" in metadata.columns:
            pinned = metadata[metadata["bldg_id"] == component.bldg_id]
            if not pinned.empty:
                metadata = pinned

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


def _weighted_percentile(sorted_values: list[float], sorted_weights: list[float], percentile: float) -> float:
    """Weighted-percentile of `sorted_values` (ascending, paired with `sorted_weights` summing to ~1.0),
    via linear interpolation on the cumulative weight -- the standard way to rank a fraction-weighted
    composite sample where every row doesn't count equally (unlike a plain unweighted `pandas` quantile).
    """
    if not sorted_values:
        raise ValueError("Cannot compute a percentile of an empty sample.")
    target = max(0.0, min(100.0, percentile)) / 100.0
    cumulative_at = []
    running = 0.0
    for w in sorted_weights:
        cumulative_at.append(running + w / 2.0)
        running += w
    total = running or 1.0
    targets = [c / total for c in cumulative_at]
    if target <= targets[0]:
        return sorted_values[0]
    if target >= targets[-1]:
        return sorted_values[-1]
    for i in range(1, len(targets)):
        if target <= targets[i]:
            lo_t, hi_t = targets[i - 1], targets[i]
            lo_v, hi_v = sorted_values[i - 1], sorted_values[i]
            span = hi_t - lo_t
            frac = (target - lo_t) / span if span else 0.0
            return lo_v + frac * (hi_v - lo_v)
    return sorted_values[-1]  # pragma: no cover - unreachable, targets[-1] always satisfies the loop above


def _weighted_percentile_rank(sorted_values: list[float], sorted_weights: list[float], value: float) -> float:
    """Inverse of `_weighted_percentile()`: the (0-100) weighted percentile rank of an arbitrary `value`
    (not necessarily one of `sorted_values`) within the weighted sample, via linear interpolation on the
    cumulative weight -- used to label each point on the density curve with the percentile it corresponds
    to, so a click can still resolve to a percentile even though the y-axis itself is now density, not
    rank.
    """
    if not sorted_values:
        return 0.0
    cumulative_at = []
    running = 0.0
    for w in sorted_weights:
        cumulative_at.append(running + w / 2.0)
        running += w
    total = running or 1.0
    ranks = [c / total * 100.0 for c in cumulative_at]
    if value <= sorted_values[0]:
        return ranks[0]
    if value >= sorted_values[-1]:
        return ranks[-1]
    for i in range(1, len(sorted_values)):
        if value <= sorted_values[i]:
            lo_v, hi_v = sorted_values[i - 1], sorted_values[i]
            lo_r, hi_r = ranks[i - 1], ranks[i]
            span = hi_v - lo_v
            frac = (value - lo_v) / span if span else 0.0
            return lo_r + frac * (hi_r - lo_r)
    return ranks[-1]  # pragma: no cover - unreachable, sorted_values[-1] always satisfies the loop above


def _fetch_component_euis(
    components: list[CompositeComponentSpec],
    state: str,
    county_name: str | list[str],
    upgrade: str,
    min_sqft: float | None,
    max_sqft: float | None,
    settings: Settings,
    warnings: list[str],
) -> list[tuple[CompositeComponentSpec, pd.DataFrame, str, str]]:
    """Download each component's metadata and compute its site EUI (kBtu/ft2) column, for building an EUI
    distribution/percentile curve or looking up nearby buildings at a specific percentile. Returns
    `(component, working_metadata_with_eui_column, sqft_column, energy_column)` per component that has a
    usable EUI sample -- components missing the needed columns or with no valid rows are skipped (and
    noted in `warnings`), not raised, so one bad component doesn't fail the whole request.
    """

    def _fetch_metadata(component: CompositeComponentSpec) -> pd.DataFrame:
        processor = _build_processor(
            settings.cache_dir, component.product, state, county_name, component.building_type, upgrade, min_sqft, max_sqft
        )
        try:
            metadata = processor.process_metadata(save_dir=processor.base_dir)
        except Exception as exc:
            raise ServiceError(f"Failed to download metadata for {component.building_type} ({component.product}): {exc}") from exc
        if metadata.empty:
            raise ServiceError(f"No buildings found for {component.building_type} ({component.product}) in state={state!r}.")
        return metadata

    metadata_by_component = _fetch_components_concurrently(components, _fetch_metadata)

    component_euis: list[tuple[CompositeComponentSpec, pd.DataFrame, str, str]] = []
    for component, metadata in zip(components, metadata_by_component):
        sqft_column = _find_column(metadata.columns, "in.sqft")
        energy_column = _find_column(metadata.columns, "out.site_energy.total.energy_consumption")
        if sqft_column is None or energy_column is None:
            warnings.append(
                f"({component.product}, {component.building_type}): missing floor-area or site energy column -- excluded "
                "from the EUI distribution."
            )
            continue

        sqft = pd.to_numeric(metadata[sqft_column], errors="coerce")
        energy = pd.to_numeric(metadata[energy_column], errors="coerce")
        eui = ((energy * KWH_TO_KBTU) / sqft).replace([float("inf"), float("-inf")], pd.NA)
        working = metadata.assign(_eui=eui).dropna(subset=["_eui"])
        if working.empty:
            warnings.append(f"({component.product}, {component.building_type}): no rows with a valid site EUI -- excluded.")
            continue

        if "bldg_id" in working.columns and working["bldg_id"].duplicated().any():
            # A state-wide ("All" county) ComStock query samples buildings independently per county, so the
            # same synthetic bldg_id (same geometry/sqft/energy) is legitimately repeated once per county it
            # was drawn in -- collapse those repeats to one row per bldg_id here, otherwise the percentile
            # curve/ranking would be skewed toward whichever buildings happen to appear in more counties,
            # and the "nearby buildings" table would show the same building listed several times over.
            working = working.drop_duplicates(subset=["bldg_id"])

        component_euis.append((component, working, sqft_column, energy_column))

    return component_euis


def _weighted_kde(sorted_values: list[float], sorted_weights: list[float], eval_points: list[float]) -> list[float]:
    """Weighted Gaussian kernel density estimate of `sorted_values`/`sorted_weights` (weights need not sum
    to 1), evaluated at `eval_points`, then peak-normalized so the highest value is exactly 1.0. Used to
    draw a real probability-density-shaped curve (not a percentile-rank line) for the EUI distribution
    chart -- avoids adding a `scipy` dependency for what's a fairly small, one-off calculation.

    Bandwidth follows Silverman's rule of thumb (using the weighted standard deviation and an effective
    sample size that accounts for uneven weights), which is standard for a quick, reasonable-looking KDE
    without needing cross-validation.
    """
    values = np.asarray(sorted_values, dtype=float)
    weights = np.asarray(sorted_weights, dtype=float)
    total_weight = weights.sum()
    if total_weight <= 0 or values.size == 0:
        return [0.0 for _ in eval_points]
    weights = weights / total_weight

    mean = float(np.sum(values * weights))
    variance = float(np.sum(weights * (values - mean) ** 2))
    std = variance**0.5
    if std <= 0:
        # A degenerate (all-identical) sample has no spread -- fall back to a tiny nonzero bandwidth so the
        # KDE below doesn't divide by zero, rather than special-casing a single spike.
        std = max(abs(mean), 1.0) * 1e-6

    # Effective sample size for unevenly-weighted data (Kish's approximation), used in place of a plain
    # sample count so a few dominant rows don't produce an artificially narrow (overfit-looking) bandwidth.
    effective_n = 1.0 / float(np.sum(weights**2)) if np.sum(weights**2) > 0 else float(values.size)
    bandwidth = 1.06 * std * effective_n ** (-1.0 / 5.0)
    bandwidth = max(bandwidth, std * 0.05 if std else 1e-6)

    eval_arr = np.asarray(eval_points, dtype=float)
    # Gaussian kernel, vectorized over (eval_points x values) -- fine at this scale (curve_points typically
    # ~100-300, sample sizes typically in the thousands).
    diffs = (eval_arr[:, None] - values[None, :]) / bandwidth
    kernel = np.exp(-0.5 * diffs**2)
    density = (kernel * weights[None, :]).sum(axis=1) / bandwidth
    peak = float(density.max()) if density.size else 0.0
    if peak <= 0:
        return [0.0 for _ in eval_points]
    return [float(d / peak) for d in density]


def get_eui_distribution(request: EuiDistributionRequest, settings: Settings) -> EuiDistributionResponse:
    """Build the composite's fraction-weighted site EUI (kBtu/ft2) probability density curve, and resolve
    which real building each component contributes at the 5th/25th/50th/75th/95th percentile + average --
    so the builder page can let a user explicitly pick *where* along the distribution the actual
    representative buildings come from (5th = a below-average/inefficient sample, 95th = a highly
    efficient one), instead of every downstream page implicitly using an otherwise-arbitrary "first
    building found"/nearest-sqft pick that a user has no visibility into or control over.

    Every component's own metadata sample contributes `component.fraction` of total weight, spread evenly
    across its own rows (so a component with more sampled buildings doesn't dominate the composite's shape
    just by having a bigger sample) -- this mirrors how `component.fraction` already weights every other
    composite aggregate (see `pull_composite_time_series`/`summarize_composite_metadata`).

    Returns a true probability-density-shaped `curve` (`request.curve_points` evenly-spaced site-EUI
    x-positions spanning the sample's range, each with a peak-normalized `density` 0-1 and its own
    `percentile` rank) rather than a percentile-rank line or binned histogram -- the y-axis is a real
    density shape a user can read visually (where buildings cluster), while each point's `percentile`
    still lets the frontend map an x-position click to a percentile for `POST
    /api/composite/eui-percentile-buildings` to resolve into real nearby building(s).
    """
    warnings: list[str] = []
    component_euis = _fetch_component_euis(
        request.components, request.state, request.county_name, request.upgrade, request.min_sqft, request.max_sqft, settings, warnings
    )
    if not component_euis:
        raise ServiceError("No component had a usable site EUI sample to build a distribution from.")

    all_eui_values: list[float] = []
    all_weights: list[float] = []
    sample_size = 0
    for component, working, _sqft_column, _energy_column in component_euis:
        sample_size += len(working)
        row_weight = component.fraction / len(working)
        all_eui_values.extend(float(v) for v in working["_eui"].tolist())
        all_weights.extend([row_weight] * len(working))

    paired = sorted(zip(all_eui_values, all_weights), key=lambda pair: pair[0])
    sorted_values = [p[0] for p in paired]
    sorted_weights = [p[1] for p in paired]
    total_weight = sum(sorted_weights) or 1.0

    # Evenly-spaced x-positions spanning (slightly past) the sample's observed range, so the density curve
    # doesn't get artificially truncated right at the min/max sampled value.
    eui_min, eui_max = sorted_values[0], sorted_values[-1]
    pad = (eui_max - eui_min) * 0.05 or max(abs(eui_min), 1.0) * 0.05
    x_start, x_end = eui_min - pad, eui_max + pad
    x_points = [x_start + (x_end - x_start) * i / (request.curve_points - 1) for i in range(request.curve_points)]
    densities = _weighted_kde(sorted_values, sorted_weights, x_points)
    curve = [
        EuiCurvePoint(
            eui_kbtu_per_ft2=x,
            density=density,
            percentile=_weighted_percentile_rank(sorted_values, sorted_weights, x),
        )
        for x, density in zip(x_points, densities)
    ]

    mean_eui = sum(v * w for v, w in paired) / total_weight
    median_eui = _weighted_percentile(sorted_values, sorted_weights, 50.0)

    percentile_targets: list[tuple[str, float | None]] = [
        ("5th percentile", 5.0),
        ("25th percentile", 25.0),
        ("Median (50th)", 50.0),
        ("Average", None),
        ("75th percentile", 75.0),
        ("95th percentile", 95.0),
    ]
    percentiles: list[EuiPercentileSelection] = []
    for label, percentile in percentile_targets:
        bldg_ids: dict[str, int] = {}
        composite_eui = 0.0
        for component, working, sqft_column, energy_column in component_euis:
            key = f"{component.product}:{component.building_type}"
            if percentile is None:
                # "Average": pick the real row whose own EUI is closest to this component's plain mean,
                # rather than an interpolated value with no corresponding actual building.
                component_mean = float(working["_eui"].mean())
                nearest_row = working.iloc[(working["_eui"] - component_mean).abs().argsort().iloc[0]]
                bldg_ids[key] = int(nearest_row["bldg_id"])
                component_eui = float(nearest_row["_eui"])
            else:
                selection = select_building_condition_sample(
                    working,
                    percentile=percentile,
                    sqft_column=sqft_column,
                    energy_column=energy_column,
                )
                bldg_ids[key] = selection.median_bldg_id
                component_eui = selection.eui_kbtu_per_ft2_median
            composite_eui += component.fraction * component_eui
        percentiles.append(
            EuiPercentileSelection(
                label=label,
                percentile=percentile,
                eui_kbtu_per_ft2=composite_eui,
                bldg_ids=bldg_ids,
            )
        )

    return EuiDistributionResponse(
        ok=True,
        state=request.state,
        curve=curve,
        mean_eui_kbtu_per_ft2=mean_eui,
        median_eui_kbtu_per_ft2=median_eui,
        sample_size=sample_size,
        percentiles=percentiles,
        warnings=warnings,
    )


def get_eui_percentile_buildings(request: EuiPercentileBuildingsRequest, settings: Settings) -> EuiPercentileBuildingsResponse:
    """List the real sampled buildings near a user-clicked percentile on the EUI curve, per component --
    lets the builder page show exactly which building(s) a percentile pick corresponds to, including any
    other close candidates in a finite sample (especially likely in a flat/dense part of the curve).
    """
    warnings: list[str] = []
    component_euis = _fetch_component_euis(
        request.components, request.state, request.county_name, request.upgrade, request.min_sqft, request.max_sqft, settings, warnings
    )
    if not component_euis:
        raise ServiceError("No component had a usable site EUI sample to look up nearby buildings from.")

    components: list[EuiPercentileBuildingsComponent] = []
    target_sqft_map = _target_sqft_map(request.components)
    for component, working, sqft_column, _energy_column in component_euis:
        ranked = working.assign(_rank=working["_eui"].rank(pct=True) * 100.0)
        ranked = ranked.assign(_distance=(ranked["_rank"] - request.percentile).abs())

        within_band = ranked[ranked["_distance"] <= request.band].sort_values("_distance")
        if within_band.empty:
            # A narrow band or tiny sample can miss everything -- fall back to the single closest row
            # rather than showing no candidates at all for this component.
            within_band = ranked.sort_values("_distance").head(1)

        within_band = within_band.head(request.max_candidates_per_component)
        target_sqft = target_sqft_map.get((component.product, component.building_type)) if target_sqft_map else None
        candidates = []
        for _, row in within_band.iterrows():
            sample_sqft = float(row[sqft_column])
            unit_multiplier = target_sqft / sample_sqft if target_sqft and sample_sqft else None
            candidates.append(
                EuiCandidateBuilding(
                    bldg_id=int(row["bldg_id"]),
                    eui_kbtu_per_ft2=float(row["_eui"]),
                    sqft=sample_sqft,
                    scaled_sqft=target_sqft if unit_multiplier is not None else None,
                    unit_multiplier=unit_multiplier,
                    percentile_rank=float(row["_rank"]),
                )
            )
        components.append(
            EuiPercentileBuildingsComponent(
                product=component.product,
                building_type=component.building_type,
                label=component.label,
                selected_bldg_id=candidates[0].bldg_id,
                candidates=candidates,
            )
        )

    return EuiPercentileBuildingsResponse(ok=True, percentile=request.percentile, components=components, warnings=warnings)


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

    `bldg_ids` (an explicit per-call override) is merged with each component's own persisted
    `CompositeComponentSpec.bldg_id` (e.g. from `resolve_composite()`'s sqft-mode auto-selection), with
    `bldg_ids` taking priority for a component set in both -- so a caller doesn't need to re-merge this
    itself, and every page reusing the same resolved components picks the same building consistently.
    """
    effective_bldg_ids: dict[tuple[str, str], int] = {
        (component.product, component.building_type): component.bldg_id for component in components if component.bldg_id is not None
    }
    effective_bldg_ids.update(bldg_ids or {})
    bldg_ids = effective_bldg_ids or None
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
            elif target_sqft_map is not None:
                # Pick a real building already close in size to the target, rather than an arbitrary
                # "first found" one that then gets linearly rescaled -- see find_nearest_sqft_bldg_id().
                nearest_bldg_id = find_nearest_sqft_bldg_id(metadata, target_sqft_map[key])
                metadata = metadata[metadata["bldg_id"] == nearest_bldg_id]
            sqft_column = _find_column(metadata.columns, "in.sqft") if target_sqft_map is not None else None
            select_columns = ["bldg_id", "in.state"] + ([sqft_column] if sqft_column else [])
            sample = metadata[select_columns].drop_duplicates().head(1)
            if sqft_column:
                sample_sqft = float(sample[sqft_column].iloc[0])
                if target_sqft_map is not None:
                    warning = _sqft_bounds_warning(component, metadata, sqft_column, target_sqft_map[key])
                    if warning:
                        warnings.append(warning)
                    note = _sqft_scaling_note(component, sample_sqft, target_sqft_map[key])
                    if note:
                        warnings.append(note)

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

            # Mirror pull_composite_time_series()'s own building-selection precedence (an explicit/
            # persisted bldg_id pin, else the nearest-sqft match) so this note describes the building it
            # will actually use.
            if sqft_column:
                pinned_bldg_id = (bldg_ids or {}).get(key)
                if pinned_bldg_id is not None:
                    pinned_row = metadata[metadata["bldg_id"] == pinned_bldg_id]
                    component_sqft = float(pinned_row[sqft_column].iloc[0]) if not pinned_row.empty else None
                else:
                    nearest_bldg_id = find_nearest_sqft_bldg_id(metadata, target_sqft_map[key], sqft_column=sqft_column)
                    component_sqft = float(metadata.loc[metadata["bldg_id"] == nearest_bldg_id, sqft_column].iloc[0])
                if component_sqft is not None:
                    note = _sqft_scaling_note(component, component_sqft, target_sqft_map[key])
                    if note:
                        warnings.append(note)

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
        combined, component_series, warnings = _pull_timeseries(
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

    component_bldg_ids = {
        f"{key[0]}:{key[1]}": int(series["bldg_id"].iloc[0])
        for key, series in component_series.items()
        if not series.empty and "bldg_id" in series.columns
    }

    return TimeseriesResponse(
        ok=True,
        state=request.state,
        upgrade=request.upgrade,
        resample=request.resample,
        columns=available_columns,
        row_count=len(records),
        series=records,
        component_labels={f"{c.product}:{c.building_type}": c.label or f"{c.building_type} ({c.product})" for c in request.components},
        component_bldg_ids=component_bldg_ids,
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

    def _fetch_measures_metadata(component: CompositeComponentSpec) -> tuple[dict[str, str], pd.DataFrame]:
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
        component_upgrade_names: dict[str, str] = {}
        with contextlib.suppress(Exception):
            component_upgrade_names = processor.list_upgrades(save_dir=processor.base_dir)

        needed_upgrades = sorted(upgrades_by_product.get(component.product, {request.baseline_upgrade}))
        try:
            combined_metadata = processor.process_metadata_for_upgrades(save_dir=processor.base_dir, upgrades=needed_upgrades)
        except Exception as exc:
            raise ServiceError(f"Failed to download upgrade metadata for {component.building_type} ({component.product}): {exc}") from exc
        return component_upgrade_names, combined_metadata

    fetched = _fetch_components_concurrently(request.components, _fetch_measures_metadata)

    for component, (component_upgrade_names, combined_metadata_frame) in zip(request.components, fetched):
        combined_metadata = combined_metadata_frame
        if component.product not in upgrade_names_by_product:
            upgrade_names_by_product[component.product] = component_upgrade_names

        if combined_metadata.empty or "upgrade" not in combined_metadata.columns:
            continue
        combined_metadata = combined_metadata.copy()
        combined_metadata["upgrade"] = combined_metadata["upgrade"].astype(str)

        # A pinned bldg_id (e.g. from the builder's EUI-percentile picker) means every downstream page
        # should describe *that one real building* across every upgrade, not the full building type's
        # population mean -- mirrors the same restriction in get_metadata_summary().
        if component.bldg_id is not None and "bldg_id" in combined_metadata.columns:
            pinned = combined_metadata[combined_metadata["bldg_id"] == component.bldg_id]
            if not pinned.empty:
                combined_metadata = pinned

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


def _resolve_component_bldg_ids(
    components: list[CompositeComponentSpec],
    bldg_ids: dict[tuple[str, str], int] | None,
    state: str,
    county_name: str | list[str],
    settings: Settings,
) -> dict[tuple[str, str], int]:
    """Resolve exactly one representative `bldg_id` per component, for downloading its building energy
    model -- mirrors `_pull_timeseries()`'s own building-selection precedence (an explicit `bldg_ids`
    override, else the component's own persisted `CompositeComponentSpec.bldg_id`, else the real building
    closest in floor area to `sqft` in sqft mode, else the first metadata row found) so the model file
    downloaded here always matches the same building already shown/used on the Dashboard/Timeseries/
    Measures pages, instead of an independently (and possibly different) auto-selected one.
    """
    effective_bldg_ids: dict[tuple[str, str], int] = {
        (component.product, component.building_type): component.bldg_id for component in components if component.bldg_id is not None
    }
    effective_bldg_ids.update(bldg_ids or {})

    def _fetch_bldg_id(component: CompositeComponentSpec) -> int:
        key = (component.product, component.building_type)
        pinned = effective_bldg_ids.get(key)
        if pinned is not None:
            return pinned

        processor = _build_processor(settings.cache_dir, component.product, state, county_name, component.building_type, "0", None, None)
        metadata = processor.process_metadata(save_dir=processor.base_dir)
        if metadata.empty:
            raise ServiceError(f"No buildings found for {component.building_type} ({component.product}) in state={state!r}.")
        if component.sqft is not None:
            return int(find_nearest_sqft_bldg_id(metadata, component.sqft))
        return int(metadata["bldg_id"].iloc[0])

    resolved = _fetch_components_concurrently(components, _fetch_bldg_id)
    return {(c.product, c.building_type): bldg_id for c, bldg_id in zip(components, resolved)}


def get_building_energy_model_manifest(request: BuildingEnergyModelRequest, settings: Settings) -> BuildingEnergyModelResponse:
    """List which real building energy model file each composite component will download, without
    actually downloading the (potentially large) model file(s) yet -- lets the UI show the user what
    they're about to get before committing to the download."""
    bldg_ids = None
    if request.bldg_ids:
        bldg_ids = {}
        for override_key, bldg_id in request.bldg_ids.items():
            product, building_type = override_key.split(":", 1)
            bldg_ids[(product, building_type)] = bldg_id

    try:
        resolved_bldg_ids = _resolve_component_bldg_ids(request.components, bldg_ids, request.state, request.county_name, settings)
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError(f"Failed to resolve representative buildings for model download: {exc}") from exc

    upgrade_product, upgrade_id = _parse_measure_selection(request.upgrade)
    components: list[ComponentBuildingModel] = []
    for component in request.components:
        component_key = (component.product, component.building_type)
        bldg_id = resolved_bldg_ids[component_key]
        effective_upgrade = upgrade_id if (upgrade_product is None or upgrade_product == component.product) else "0"
        processor = _build_processor(
            settings.cache_dir,
            component.product,
            request.state,
            request.county_name,
            component.building_type,
            effective_upgrade,
            None,
            None,
        )
        filename = processor.building_energy_model_filename(bldg_id, effective_upgrade)
        components.append(
            ComponentBuildingModel(
                product=component.product,
                building_type=component.building_type,
                label=component.label,
                bldg_id=bldg_id,
                filename=filename,
            )
        )

    return BuildingEnergyModelResponse(ok=True, state=request.state, upgrade=request.upgrade, components=components)


def build_building_energy_models(request: BuildingEnergyModelRequest, settings: Settings) -> tuple[bytes, str, str]:
    """Download the composite's representative building energy model file(s) -- one per component -- and
    package them for a single HTTP response.

    A single-component composite returns that one model file as-is (its own native format/extension --
    ComStock's gzipped ".osm.gz", ResStock's ".zip" bundle). A multi-component composite returns a ".zip"
    bundling every component's model file together (each under its own `ComponentBuildingModel.filename`),
    since an HTTP response can only carry one file.

    Returns `(content_bytes, filename, media_type)`.
    """
    bldg_ids = None
    if request.bldg_ids:
        bldg_ids = {}
        for override_key, bldg_id in request.bldg_ids.items():
            product, building_type = override_key.split(":", 1)
            bldg_ids[(product, building_type)] = bldg_id

    try:
        resolved_bldg_ids = _resolve_component_bldg_ids(request.components, bldg_ids, request.state, request.county_name, settings)
    except ServiceError:
        raise
    except Exception as exc:
        raise ServiceError(f"Failed to resolve representative buildings for model download: {exc}") from exc

    upgrade_product, upgrade_id = _parse_measure_selection(request.upgrade)

    def _download_one(component: CompositeComponentSpec) -> tuple[str, Path]:
        component_key = (component.product, component.building_type)
        bldg_id = resolved_bldg_ids[component_key]
        effective_upgrade = upgrade_id if (upgrade_product is None or upgrade_product == component.product) else "0"
        processor = _build_processor(
            settings.cache_dir,
            component.product,
            request.state,
            request.county_name,
            component.building_type,
            effective_upgrade,
            None,
            None,
        )
        models_dir = processor.base_dir / "building_energy_models"
        try:
            path = processor.download_building_energy_model(bldg_id, models_dir, upgrade=effective_upgrade)
        except Exception as exc:
            raise ServiceError(
                f"Failed to download the building energy model for {component.building_type} ({component.product}), "
                f"bldg_id {bldg_id}: {exc}"
            ) from exc
        return path.name, path

    downloaded = _fetch_components_concurrently(request.components, _download_one)

    if len(downloaded) == 1:
        filename, path = downloaded[0]
        media_type = "application/zip" if filename.endswith(".zip") else "application/gzip"
        return path.read_bytes(), filename, media_type

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, path in downloaded:
            archive.write(path, arcname=filename)

    building_types = "-".join(f"{c.product}_{c.building_type}" for c in request.components)
    bundle_filename = f"composite_building_energy_models_{request.state}_upgrade{request.upgrade}_{building_types}.zip"
    return buffer.getvalue(), bundle_filename, "application/zip"
