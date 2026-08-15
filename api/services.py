"""Business logic bridging the composite building explorer API to building_energy_profiles.

Every endpoint in `api/main.py` is a thin wrapper around a function here. Keeping this layer separate
(and free of any FastAPI/HTTP concepts) makes it straightforward to unit test the pure logic (see
`tests/test_api_services.py`) without needing a running server or real network access for everything.
"""

from __future__ import annotations

import contextlib
import dataclasses
import math
from pathlib import Path
from typing import Any

import pandas as pd

from api.config import Settings
from api.mos_export import MosExportError, build_thermal_load_mos
from api.schemas import (
    AvailableCountiesResponse,
    AvailableStatesResponse,
    BuildingDistributionRequest,
    BuildingDistributionResponse,
    ComponentDistribution,
    ComponentFilterOptions,
    ComponentSummary,
    CompositeComponentSpec,
    CompositeResolveRequest,
    CompositeResolveResponse,
    DistributionPointOut,
    EndUseValue,
    EnergyStarTypeInfo,
    FilterColumnOptions,
    FilterOptionsRequest,
    FilterOptionsResponse,
    FilterValueCount,
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
from building_energy_profiles import location
from building_energy_profiles.building_condition import select_building_condition_sample
from building_energy_profiles.building_distribution import compute_building_distribution
from building_energy_profiles.composite import (
    CompositeBuildingType,
    CompositeComponent,
    find_nearest_sqft_bldg_id,
    is_dwelling_unit_product,
    normalize_time_series_columns,
    pull_composite_time_series,
    resolve_fraction_weights_for,
)
from building_energy_profiles.comstock import ComStockProcessor
from building_energy_profiles.data_dictionary import result_variables_from_columns
from building_energy_profiles.energy_star_crosswalk import (
    energy_star_crosswalk,
    map_energy_star_property_type,
    refine_building_type_for_sqft,
)
from building_energy_profiles.resstock import ResStockProcessor

# Fuel/end-use source names that are stock-level aggregates, not distinct fuels -- excluded from the
# by-fuel breakdown so they don't double-count alongside their constituent fuels.
_AGGREGATE_SOURCES = {"site_energy"}
# end_use labels that aren't real building end uses (accounting/rollup categories).
_NON_END_USE_LABELS = {"total", "net", "purchased"}

# Site energy is published in kWh; EUI is conventionally reported in kBtu/ft2 (the ENERGY STAR
# Portfolio Manager / DOE convention), so we convert with the standard kWh->kBtu unit factor
# (this is a unit conversion only, not a source-to-site energy conversion).
KWH_TO_KBTU = 3.412141633

# For a roughly-normal distribution, the interquartile range (25th-75th percentile) spans ~1.349 standard
# deviations (norm.ppf(0.75) - norm.ppf(0.25) ~= 1.34898), i.e. a *half*-IQR (median-to-Q3, or Q1-to-median)
# is ~0.6745 standard deviations, so a half-IQR is converted to an implied standard deviation by dividing by
# 0.6745 (equivalently, multiplying by ~1.4826). `compare_measures`'s `include_uncertainty` uses this to
# convert a component's (robust, but not directly combinable) IQR into an implied standard deviation, so
# multiple components'/quantities' uncertainty can be combined by summing variances (assuming independence)
# and converted back to a combined half-IQR.
_HALF_IQR_TO_STD = 1.0 / 0.6744897501960817

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

# Curated, per-product subset of "in.*" metadata columns exposed as population filters (see
# get_filter_options()) -- BuildStock metadata carries dozens to ~190 "in.*" columns per product, most of
# which are identifiers (census tract/PUMA/county GISJOINs), simulation bookkeeping, or too granular to be
# a meaningful filter -- this intentionally curates down to a handful of well-known, broadly-applicable
# building characteristics a user would actually want to narrow a population by. {product: [(column,
# display_name), ...]}.
CURATED_FILTER_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "comstock": [
        ("in.vintage", "Vintage"),
        ("in.hvac_system_type", "HVAC system type"),
        ("in.number_of_stories", "Number of stories"),
        ("in.wall_construction_type", "Wall construction"),
        ("in.window_to_wall_ratio_category", "Window-to-wall ratio"),
        ("in.heating_fuel", "Heating fuel"),
    ],
    "resstock": [
        ("in.vintage", "Vintage"),
        ("in.hvac_heating_type", "HVAC heating type"),
        ("in.hvac_cooling_type", "HVAC cooling type"),
        ("in.geometry_foundation_type", "Foundation type"),
        ("in.geometry_stories", "Number of stories"),
        ("in.insulation_wall", "Wall insulation"),
    ],
}


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


def _apply_component_filters(metadata: pd.DataFrame, filters: dict[str, list[str]] | None) -> pd.DataFrame:
    """Narrow `metadata` to rows matching every column in `filters` -- OR within one column's allowed
    values, AND across columns (e.g. `{"in.vintage": ["2000 to 2012", "2013 to 2018"], "in.heating_fuel":
    ["Electricity"]}` keeps only electric-heated buildings from either of those two vintage bands).

    A filter column not present in `metadata` (e.g. stale filters left over from a different building
    type/product) is silently skipped rather than raising, since `CompositeComponentSpec.filters` is
    shared across every component in a request regardless of whether a given column applies to it.
    """
    if not filters:
        return metadata
    for column, allowed_values in filters.items():
        if not allowed_values:
            continue
        matched_column = _find_column(metadata.columns, column)
        if not matched_column:
            continue
        metadata = metadata[metadata[matched_column].astype(str).isin(allowed_values)]
    return metadata


def _apply_component_sqft_range(metadata: pd.DataFrame, min_sqft: float | None, max_sqft: float | None) -> pd.DataFrame:
    """Narrow `metadata` to rows whose floor area (`in.sqft`) falls within `[min_sqft, max_sqft]` (either
    bound optional) -- the numeric floor-area counterpart of `_apply_component_filters`'s categorical
    column filters, for the same "narrow the population" UI control (see `CompositeComponentSpec.min_sqft`/
    `max_sqft`).

    A no-op if both bounds are `None`, or if `metadata` has no usable floor-area column, rather than
    raising -- consistent with `_apply_component_filters`'s "silently skip what doesn't apply" behavior.
    """
    if min_sqft is None and max_sqft is None:
        return metadata
    sqft_column = _find_column(metadata.columns, "in.sqft")
    if not sqft_column:
        return metadata
    sqft = pd.to_numeric(metadata[sqft_column], errors="coerce")
    mask = pd.Series(True, index=metadata.index)
    if min_sqft is not None:
        mask &= sqft >= min_sqft
    if max_sqft is not None:
        mask &= sqft <= max_sqft
    return metadata[mask]


def _target_sqft_map(components: list[CompositeComponentSpec]) -> dict[tuple[str, str], float] | None:
    """Return `{(product, building_type): sqft}` if every component has an absolute target square footage
    set, else `None` (fraction mode). Schema validation on the resolve endpoint keeps a resolved composite
    consistently all-fraction or all-sqft, but callers can also build `CompositeComponentSpec`s directly, so
    this treats "any missing" as fraction mode rather than assuming consistency.
    """
    if not components or any(c.sqft is None for c in components):
        return None
    return {(c.product, c.building_type): c.sqft for c in components if c.sqft is not None}


def _component_scales(
    components: list[CompositeComponentSpec],
    component_sqft: dict[tuple[str, str], float],
    target_sqft_map: dict[tuple[str, str], float] | None,
) -> tuple[dict[tuple[str, str], float], bool]:
    """Resolve each component's multiplier of its own average sampled building/dwelling unit, plus whether
    those multipliers are floor-area-based (as opposed to bare fractions).

    Mixing ComStock with ResStock always goes through the floor-area path, since a ResStock row is one
    dwelling unit rather than a whole building -- see `composite.resolve_fraction_weights_for()`.
    """
    keys = [(component.product, component.building_type) for component in components]
    if target_sqft_map is not None:
        scales: dict[tuple[str, str], float] = {}
        for key in keys:
            if not component_sqft.get(key):
                raise ServiceError(f"Could not determine floor area for {key[1]} ({key[0]}) to scale by target square footage.")
            scales[key] = target_sqft_map[key] / component_sqft[key]
        return scales, True

    fractions = {(component.product, component.building_type): component.fraction for component in components}
    resolved = resolve_fraction_weights_for(fractions, component_sqft)
    return (resolved, True) if resolved is not None else (fractions, False)


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


def _sqft_scaling_note(component: CompositeComponentSpec, sample_sqft: float, target_sqft: float) -> str | None:
    """Inform the user when the specific representative building actually modeled for this component isn't
    the same size as their requested `target_sqft` -- e.g. "you asked for 40,000 sqft, but the closest
    available modeled building is 46,000 sqft, so results are scaled by 0.87x to represent your smaller
    target". Time series results are always scaled to `target_sqft` regardless (see
    `find_nearest_sqft_bldg_id`), so this is purely informational transparency about *how much* scaling was
    applied, distinct from `_sqft_bounds_warning`'s "this extrapolates beyond the data" concern. Returns
    `None` for a near-exact match (within 1%) to avoid noise.
    """
    if not sample_sqft or not target_sqft:
        return None
    relative_diff = abs(target_sqft - sample_sqft) / sample_sqft
    if relative_diff < 0.01:
        return None
    label = component.label or component.building_type
    scale = target_sqft / sample_sqft
    direction = "smaller than" if target_sqft < sample_sqft else "larger than"
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

        # A generic, size-ambiguous crosswalk entry (currently just "Office" -- see
        # `refine_building_type_for_sqft`) gets its building type refined by the actual requested square
        # footage instead of always using the crosswalk's single static default (e.g. "Office" always
        # defaulting to MediumOffice even for a 5,000 sqft or 300,000 sqft building).
        building_type = mapping.buildstock_building_type
        notes = mapping.notes
        if sqft_mode and entry.sqft and mapping.buildstock_product == "comstock" and building_type:
            refined_building_type = refine_building_type_for_sqft(entry.energy_star_property_type, entry.sqft)
            if refined_building_type and refined_building_type != building_type:
                notes = f"{notes} Refined to {refined_building_type} based on the entered {entry.sqft:,.0f} sqft."
                building_type = refined_building_type

        bldg_id: int | None = None
        if select_bldg_ids and entry.sqft is not None and mapping.buildstock_product is not None and building_type is not None:
            # request.state is guaranteed non-None here: select_bldg_ids is only True when it was set.
            bldg_id = _select_bldg_id_for_sqft(
                mapping.buildstock_product,
                building_type,
                entry.sqft,
                request.state or "",
                request.county_name,
                settings,
                warnings,
            )

        resolved.append(
            ResolvedComponent(
                energy_star_property_type=entry.energy_star_property_type,
                product=mapping.buildstock_product,
                building_type=building_type,
                fraction=entry_fraction,
                sqft=entry.sqft,
                bldg_id=bldg_id,
                match_quality=mapping.match_quality,
                notes=notes,
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


def _distribution_point_to_schema(point: Any) -> DistributionPointOut:
    return DistributionPointOut(**dataclasses.asdict(point))


def get_building_distributions(request: BuildingDistributionRequest, settings: Settings) -> BuildingDistributionResponse:
    """For each composite component, download its metadata and compute a site-EUI distribution ("PDF") --
    see `building_energy_profiles.building_distribution.compute_building_distribution`.

    Lets a caller (the webapp's building-selection step) show, for each component in a mixed-use
    composite, the spread of real sampled buildings of that type/location, so a user can either click a
    point on the curve or jump to a percentile/mean shortcut to pin a specific representative `bldg_id`
    (persisted the same way as `resolve_composite()`'s sqft-mode auto-selection -- see
    `CompositeComponentSpec.bldg_id`) for downstream time-series-based pages.

    A component whose metadata can't be downloaded (or has no usable site EUI) is skipped with a warning
    rather than failing the whole request, so one bad component doesn't block selecting buildings for the
    rest of a mix.
    """
    distributions: list[ComponentDistribution] = []
    warnings: list[str] = []

    for component in request.components:
        label = component.label or component.building_type
        try:
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
            metadata = processor.process_metadata(save_dir=processor.base_dir)
            metadata = _apply_component_filters(metadata, component.filters)
            metadata = _apply_component_sqft_range(metadata, component.min_sqft, component.max_sqft)
            distribution = compute_building_distribution(metadata, bins=request.bins)
        except Exception as exc:
            warnings.append(f"Could not compute a building distribution for {label} ({component.product}): {exc}")
            continue

        distributions.append(
            ComponentDistribution(
                product=component.product,
                building_type=component.building_type,
                label=component.label,
                metric=distribution.metric,
                unit=distribution.unit,
                sample_size=distribution.sample_size,
                mean_value=distribution.mean_value,
                points=[_distribution_point_to_schema(p) for p in distribution.points],
                histogram_bin_edges=distribution.histogram_bin_edges,
                histogram_counts=distribution.histogram_counts,
                histogram_density=distribution.histogram_density,
                kde_x=distribution.kde_x,
                kde_y=distribution.kde_y,
                percentile_buildings={k: _distribution_point_to_schema(v) for k, v in distribution.percentile_buildings.items()},
            )
        )

    return BuildingDistributionResponse(ok=True, state=request.state, distributions=distributions, warnings=warnings)


def get_filter_options(request: FilterOptionsRequest, settings: Settings) -> FilterOptionsResponse:
    """For each composite component, list curated metadata columns (see `CURATED_FILTER_COLUMNS`) with
    their distinct values/counts in the current sample, to build a "narrow the population" filter UI.

    Only includes a column if it's actually present for this component's product/building_type and has
    more than one distinct value in the sample (a constant column isn't a useful filter). A component whose
    metadata can't be downloaded is skipped with a warning rather than failing the whole request.
    """
    components: list[ComponentFilterOptions] = []
    warnings: list[str] = []

    for component in request.components:
        label = component.label or component.building_type
        try:
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
            metadata = processor.process_metadata(save_dir=processor.base_dir)
        except Exception as exc:
            warnings.append(f"Could not load filter options for {label} ({component.product}): {exc}")
            continue

        column_options: list[FilterColumnOptions] = []
        for column, display_name in CURATED_FILTER_COLUMNS.get(component.product, []):
            matched_column = _find_column(metadata.columns, column)
            if not matched_column:
                continue
            value_counts = metadata[matched_column].astype(str).value_counts()
            if len(value_counts) < 2:
                # A single-valued column (or one that's empty after dropna) can't narrow anything.
                continue
            column_options.append(
                FilterColumnOptions(
                    column=column,
                    display_name=display_name,
                    values=[FilterValueCount(value=str(value), count=int(count)) for value, count in value_counts.items()],
                )
            )

        components.append(
            ComponentFilterOptions(
                product=component.product,
                building_type=component.building_type,
                label=component.label,
                columns=column_options,
            )
        )

    return FilterOptionsResponse(ok=True, components=components, warnings=warnings)


def get_metadata_summary(request: MetadataSummaryRequest, settings: Settings) -> MetadataSummaryResponse:
    component_summaries: list[ComponentSummary] = []
    by_fuel: dict[str, float] = {}
    by_end_use: dict[str, float] = {}
    weighted_sqft = 0.0
    weighted_site_energy = 0.0
    weighted_building_count = 0
    warnings: list[str] = []

    # Parallel accumulation for the "selected buildings" weighted total (see
    # MetadataSummaryResponse.weighted_selected_building_site_eui_kbtu_per_ft2) -- only meaningful once
    # every component actually has a resolvable pinned building, tracked via `all_components_selected`.
    weighted_selected_sqft = 0.0
    weighted_selected_site_energy = 0.0
    all_components_selected = True

    target_sqft_map = _target_sqft_map(request.components)

    # Pass 1: load every component's sample. Scales can't be computed inline because a fraction-mode
    # composite's implied total floor area depends on *all* components' average sizes.
    loaded: list[dict[str, Any]] = []
    component_sqft: dict[tuple[str, str], float] = {}

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

        metadata = _apply_component_filters(metadata, component.filters)
        metadata = _apply_component_sqft_range(metadata, component.min_sqft, component.max_sqft)
        if metadata.empty:
            reason = (
                "the applied filters excluded every sampled building"
                if (component.filters or component.min_sqft or component.max_sqft)
                else f"in state={request.state!r}"
            )
            raise ServiceError(f"No buildings found for {component.building_type} ({component.product}) -- {reason}.")

        sqft_column = _find_column(metadata.columns, "in.sqft")
        avg_sqft = float(metadata[sqft_column].mean()) if sqft_column else 0.0

        site_energy_column = _find_column(metadata.columns, "out.site_energy.total.energy_consumption")
        annual_site_energy = float(metadata[site_energy_column].mean()) if site_energy_column else 0.0

        # Site EUI (energy per sqft) is an intensity, so it's unaffected by sqft-mode scaling either way.
        eui = (annual_site_energy * KWH_TO_KBTU) / avg_sqft if avg_sqft else 0.0

        # The specific building pinned for this component (e.g. from the Select Buildings page), if any --
        # its OWN sqft/energy/EUI, distinct from the population averages computed above.
        selected_bldg_id = component.bldg_id
        selected_sqft: float | None = None
        selected_annual_site_energy: float | None = None
        selected_eui: float | None = None
        if selected_bldg_id is not None and sqft_column and site_energy_column:
            selected_row = metadata[metadata["bldg_id"] == selected_bldg_id]
            if not selected_row.empty:
                selected_sqft = float(selected_row[sqft_column].iloc[0])
                selected_annual_site_energy = float(selected_row[site_energy_column].iloc[0])
                selected_eui = (selected_annual_site_energy * KWH_TO_KBTU) / selected_sqft if selected_sqft else None
            else:
                label = component.label or component.building_type
                warnings.append(
                    f"Pinned bldg_id {selected_bldg_id} for {label} ({component.product}) was not found in the current "
                    "sample -- selected-building metrics are unavailable for this component."
                )
        if selected_eui is None:
            all_components_selected = False

        if avg_sqft:
            component_sqft[(component.product, component.building_type)] = avg_sqft
        loaded.append(
            {
                "component": component,
                "metadata": metadata,
                "sqft_column": sqft_column,
                "avg_sqft": avg_sqft,
                "annual_site_energy": annual_site_energy,
                "eui": eui,
                "selected_bldg_id": selected_bldg_id,
                "selected_sqft": selected_sqft,
                "selected_annual_site_energy": selected_annual_site_energy,
                "selected_eui": selected_eui,
            }
        )

    scales, area_scaled = _component_scales(request.components, component_sqft, target_sqft_map)

    # Pass 2: scale and accumulate.
    composite_total_sqft = sum(
        scales[(c.product, c.building_type)] * component_sqft.get((c.product, c.building_type), 0.0) for c in request.components
    )
    for entry in loaded:
        component = entry["component"]
        metadata = entry["metadata"]
        avg_sqft = entry["avg_sqft"]
        annual_site_energy = entry["annual_site_energy"]
        eui = entry["eui"]
        selected_sqft = entry["selected_sqft"]
        selected_annual_site_energy = entry["selected_annual_site_energy"]
        scale = scales[(component.product, component.building_type)]

        if area_scaled:
            # `scale` replaces `component.fraction` below -- it turns the population-average sqft/energy
            # for this building type into the values for an *actual* building (or, for a dwelling-unit
            # product, that many actual apartments/homes) of the resolved square footage, rather than a
            # floor-area share of an unspecified total.
            display_sqft = scale * avg_sqft
            display_energy = scale * annual_site_energy
            if not is_dwelling_unit_product(component.product):
                warning = _sqft_bounds_warning(component, metadata, entry["sqft_column"], display_sqft)
                if warning:
                    warnings.append(warning)
            elif target_sqft_map is None:
                label = component.label or component.building_type
                warnings.append(
                    f"{label} ({component.product}): {component.fraction:.0%} of the composite's {composite_total_sqft:,.0f} sqft is "
                    f"modeled as ~{scale:,.0f} dwelling unit(s) of {avg_sqft:,.0f} sqft each."
                )
        else:
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
                selected_bldg_id=entry["selected_bldg_id"],
                selected_sqft=selected_sqft,
                selected_annual_site_energy_kwh=selected_annual_site_energy,
                selected_site_eui_kbtu_per_ft2=entry["selected_eui"],
                unit_multiplier=scale if area_scaled else None,
            )
        )

        # These accumulation lines are identical for every mode -- only `scale`'s definition differs. When
        # `area_scaled`, `scale * avg_sqft` is this component's actual floor area and `scale *
        # annual_site_energy` its energy for that area, so summing across components yields the composite's
        # total floor area and total energy (rather than a fraction-weighted average of population means).
        weighted_sqft += scale * avg_sqft
        weighted_site_energy += scale * annual_site_energy
        weighted_building_count += len(metadata)

        if selected_sqft is not None and selected_annual_site_energy is not None:
            # Reuse the same per-component `scale` so the "selected buildings" weighted total is
            # comparable (fraction- or target-sqft-weighted, matching the sample-average total above) --
            # just substituting the pinned building's own values for the population average.
            weighted_selected_sqft += scale * selected_sqft
            weighted_selected_site_energy += scale * selected_annual_site_energy

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
    weighted_selected_eui = (
        (weighted_selected_site_energy * KWH_TO_KBTU) / weighted_selected_sqft
        if all_components_selected and weighted_selected_sqft
        else None
    )

    return MetadataSummaryResponse(
        ok=True,
        state=request.state,
        upgrade=request.upgrade,
        components=component_summaries,
        weighted_building_count=weighted_building_count,
        weighted_avg_sqft=weighted_sqft,
        weighted_annual_site_energy_kwh=weighted_site_energy,
        weighted_site_eui_kbtu_per_ft2=weighted_eui,
        weighted_selected_building_annual_site_energy_kwh=(weighted_selected_site_energy if all_components_selected else None),
        weighted_selected_building_site_eui_kbtu_per_ft2=weighted_selected_eui,
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
            metadata = _apply_component_filters(metadata, component.filters)
            metadata = _apply_component_sqft_range(metadata, component.min_sqft, component.max_sqft)
            if metadata.empty:
                reason = (
                    "the applied filters excluded every sampled building"
                    if (component.filters or component.min_sqft or component.max_sqft)
                    else f"in state={state!r}"
                )
                raise ServiceError(f"No buildings found for {key} -- {reason}.")
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


def get_model_download_url(product: str, bldg_id: int, upgrade: str, settings: Settings) -> str:
    """Return the public OEDI download URL for one building's energy model file -- a gzipped OpenStudio
    ".osm.gz" model for ComStock, or a ".zip" archive (bundling the OSM with its supporting files) for
    ResStock. Building energy models aren't partitioned by state/county/building type, so only `product`,
    `bldg_id`, and `upgrade` are needed to build the URL; nothing is downloaded server-side -- the caller
    (`GET /api/composite/model-download`) redirects the browser straight to this public S3 URL.
    """
    processor = _build_processor(settings.cache_dir, product, settings.default_state, "All", "All", upgrade, None, None)
    # `_build_processor()`'s building_energy_profiles-derived return type isn't seen as fully typed by mypy
    # (no py.typed marker), same pre-existing gap already visible elsewhere in this module -- str(...)
    # keeps this new, plain-`str`-returning function itself clean rather than leaking that Any through.
    return str(processor.model_file_url(bldg_id, upgrade))


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


def _extract_metric_intensity_iqr(
    group: pd.DataFrame, columns: list[str], sqft_column: str | None, bldg_ids: list[int] | None
) -> dict[str, tuple[float, float]]:
    """Return `{column: (25th percentile, 75th percentile)}` of each column's per-square-foot *intensity*
    (`column / sqft_column`) for rows in `group`, restricted to `bldg_ids` if given (see
    `_neighborhood_bldg_ids`) -- the interquartile range of the "population of buildings near the building
    selected".

    Working in per-sqft intensity (rather than each row's raw absolute value) isolates real
    efficiency/vintage/equipment variability from pure building-size variability -- a percentile-banded
    neighborhood is selected by site-EUI rank (an intensity), so two buildings in the same neighborhood can
    still have very different absolute floor areas (and thus very different absolute energy) despite
    similar efficiency. `compare_measures` multiplies this intensity IQR back out by the same *absolute*
    floor area used for its point estimate (rather than each neighbor's own, differing, floor area), so the
    reported uncertainty reflects "how much might a similarly-efficient building of *this* size vary",
    consistent with how the point estimate itself is a fixed-size scaling of a population average.

    Skips any column that's missing/all-NaN, or a `bldg_ids` restriction that matches no rows, or if there's
    no usable `sqft_column`. Empty `group` yields `{}`.
    """
    if not sqft_column or sqft_column not in group.columns:
        return {}
    if bldg_ids is not None:
        group = group[group["bldg_id"].isin(bldg_ids)]
    if group.empty:
        return {}
    sqft = pd.to_numeric(group[sqft_column], errors="coerce")
    values: dict[str, tuple[float, float]] = {}
    for column in columns:
        matched = _find_column(group.columns, column)
        if not matched:
            continue
        intensity = (pd.to_numeric(group[matched], errors="coerce") / sqft).replace([float("inf"), float("-inf")], pd.NA).dropna()
        if intensity.empty:
            continue
        values[column] = (float(intensity.quantile(0.25)), float(intensity.quantile(0.75)))
    return values


def _neighborhood_bldg_ids(baseline_group: pd.DataFrame, bldg_id: int | None, sqft_column: str | None, band: float) -> list[int] | None:
    """Find the `bldg_id`s within `band` percentile points of `bldg_id`'s own site-EUI rank in
    `baseline_group` -- "the population of buildings near the building selected", for
    `compare_measures`'s `include_uncertainty`. Returns `None` (meaning: use the *whole* `baseline_group` as
    the neighborhood -- e.g. for a component with no pinned building) if `bldg_id` is `None`, wasn't found
    in `baseline_group`, or there's no usable floor-area/site-energy data to rank it by.
    """
    if bldg_id is None or not sqft_column or "bldg_id" not in baseline_group.columns:
        return None
    energy_column = _find_column(baseline_group.columns, "out.site_energy.total.energy_consumption")
    if not energy_column:
        return None
    row = baseline_group[baseline_group["bldg_id"] == bldg_id]
    if row.empty:
        return None

    sqft = pd.to_numeric(baseline_group[sqft_column], errors="coerce")
    energy = pd.to_numeric(baseline_group[energy_column], errors="coerce")
    eui = energy * KWH_TO_KBTU / sqft
    target_eui = eui.loc[row.index[0]]
    if pd.isna(target_eui):
        return None

    valid_eui = eui.dropna()
    if valid_eui.empty:
        return None
    rank = float((valid_eui <= target_eui).mean() * 100.0)

    try:
        selection = select_building_condition_sample(baseline_group, percentile=rank, band=band, sqft_column=sqft_column)
    except ValueError:
        return None
    return selection.bldg_ids


def _combine_half_iqr(scaled_half_iqrs: list[float]) -> float:
    """Combine multiple independent quantities' half-IQR uncertainties (see `_HALF_IQR_TO_STD`) into one
    combined half-IQR, by converting each to an implied standard deviation, summing variances (the standard
    "combine independent uncertainties in quadrature" rule), and converting the combined standard deviation
    back to a half-IQR. Terms of `0` (e.g. a component with no computable IQR) contribute no variance."""
    combined_variance = sum((half_iqr * _HALF_IQR_TO_STD) ** 2 for half_iqr in scaled_half_iqrs)
    return math.sqrt(combined_variance) / _HALF_IQR_TO_STD


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
    # column -> [scaled half-IQR per component] -- only populated when request.include_uncertainty; see
    # `_combine_half_iqr` for how each column's list is combined into one uncertainty range.
    baseline_half_iqr: dict[str, list[float]] = {}
    per_selection_half_iqr: dict[str, dict[str, list[float]]] = {}
    warnings: list[str] = []

    # Pass 1: load each component's samples and floor area. Scales can't be computed inline because a
    # fraction-mode composite's implied total floor area depends on *all* components' average sizes.
    loaded: list[dict[str, Any]] = []
    component_sqft: dict[tuple[str, str], float] = {}

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

        # Floor area doesn't change across upgrades for the same building type, so the baseline upgrade's
        # group average sqft is used as the scaling denominator for every upgrade.
        sqft_column = _find_column(combined_metadata.columns, "in.sqft")
        baseline_group_for_sqft = combined_metadata[combined_metadata["upgrade"] == request.baseline_upgrade]
        avg_sqft = (
            float(pd.to_numeric(baseline_group_for_sqft[sqft_column], errors="coerce").mean())
            if sqft_column and not baseline_group_for_sqft.empty
            else 0.0
        )
        if avg_sqft:
            component_sqft[(component.product, component.building_type)] = avg_sqft

        loaded.append(
            {
                "component": component,
                "combined_metadata": combined_metadata,
                "sqft_column": sqft_column,
                "baseline_group_for_sqft": baseline_group_for_sqft,
            }
        )

    scales, area_scaled = _component_scales(request.components, component_sqft, target_sqft_map)

    # Pass 2: scale and accumulate.
    for entry in loaded:
        component = entry["component"]
        combined_metadata = entry["combined_metadata"]
        scale = scales[(component.product, component.building_type)]

        if area_scaled and not is_dwelling_unit_product(component.product):
            warning = _sqft_bounds_warning(
                component,
                entry["baseline_group_for_sqft"],
                entry["sqft_column"],
                scale * component_sqft[(component.product, component.building_type)],
            )
            if warning:
                warnings.append(warning)

        # This component always contributes at `baseline_upgrade` to the shared baseline total (the
        # denominator every comparison is measured against).
        baseline_group = combined_metadata[combined_metadata["upgrade"] == request.baseline_upgrade]
        for column, value in _extract_metric_means(baseline_group, columns).items():
            baseline_values[column] = baseline_values.get(column, 0.0) + scale * value
        for end_use, value in _extract_end_use_means(baseline_group).items():
            baseline_end_use[end_use] = baseline_end_use.get(end_use, 0.0) + scale * value

        # Uncertainty (opt-in): find this component's own "population of buildings near the building
        # selected" (its pinned bldg_id's site-EUI neighborhood, or its whole sample if unpinned), then use
        # that same neighborhood's bldg_ids to compute each column's per-sqft intensity IQR under baseline
        # and under every upgrade -- so the uncertainty reflects the same (matched) subset of physical
        # buildings throughout. The intensity IQR is then scaled by this component's own *target* absolute
        # floor area (the same one used for its point estimate above), not each neighbor's own -- see
        # `_extract_metric_intensity_iqr`.
        target_sqft_for_component = scale * component_sqft.get((component.product, component.building_type), 0.0)
        if request.include_uncertainty and target_sqft_for_component:
            neighborhood_bldg_ids = _neighborhood_bldg_ids(
                baseline_group, component.bldg_id, entry["sqft_column"], request.uncertainty_band
            )
            for column, (q1, q3) in _extract_metric_intensity_iqr(
                baseline_group, columns, entry["sqft_column"], neighborhood_bldg_ids
            ).items():
                baseline_half_iqr.setdefault(column, []).append(target_sqft_for_component * (q3 - q1) / 2.0)

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
            if request.include_uncertainty and target_sqft_for_component:
                for column, (q1, q3) in _extract_metric_intensity_iqr(group, columns, entry["sqft_column"], neighborhood_bldg_ids).items():
                    half_iqr_bucket = per_selection_half_iqr.setdefault(selection, {})
                    half_iqr_bucket.setdefault(column, []).append(target_sqft_for_component * (q3 - q1) / 2.0)

    # Combine each column's per-component half-IQR contributions (see `_combine_half_iqr`) into one
    # uncertainty range around the already-computed point estimate -- only when requested.
    baseline_iqr: dict[str, tuple[float, float]] = {}
    per_selection_iqr: dict[str, dict[str, tuple[float, float]]] = {}
    if request.include_uncertainty:
        for column, halves in baseline_half_iqr.items():
            baseline_value = baseline_values.get(column)
            if baseline_value is None or not halves:
                continue
            combined_half = _combine_half_iqr(halves)
            baseline_iqr[column] = (baseline_value - combined_half, baseline_value + combined_half)
        for selection, column_halves in per_selection_half_iqr.items():
            for column, halves in column_halves.items():
                upgrade_value = per_selection_values.get(selection, {}).get(column)
                if upgrade_value is None or not halves:
                    continue
                combined_half = _combine_half_iqr(halves)
                per_selection_iqr.setdefault(selection, {})[column] = (upgrade_value - combined_half, upgrade_value + combined_half)

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

            baseline_kwh_iqr = baseline_iqr.get(column)
            upgrade_kwh_iqr = per_selection_iqr.get(selection, {}).get(column)
            absolute_savings_kwh_iqr: tuple[float, float] | None = None
            pct_savings_iqr: tuple[float, float] | None = None
            if baseline_kwh_iqr is not None and upgrade_kwh_iqr is not None:
                # Baseline and upgrade are treated as independent quantities here (a simplification -- in
                # reality they share the same underlying buildings, just simulated under different
                # upgrades), so their variances (derived from each one's half-IQR) are summed.
                savings_half = _combine_half_iqr(
                    [(baseline_kwh_iqr[1] - baseline_kwh_iqr[0]) / 2.0, (upgrade_kwh_iqr[1] - upgrade_kwh_iqr[0]) / 2.0]
                )
                absolute_savings_kwh_iqr = (absolute_savings - savings_half, absolute_savings + savings_half)
                if baseline_value:
                    pct_savings_iqr = (
                        absolute_savings_kwh_iqr[0] / baseline_value * 100,
                        absolute_savings_kwh_iqr[1] / baseline_value * 100,
                    )

            savings_for_column.append(
                MeasureSavings(
                    upgrade_id=sel_upgrade_id,
                    name=name,
                    product=sel_product,  # type: ignore[arg-type]
                    baseline_kwh=baseline_value,
                    upgrade_kwh=upgrade_value,
                    absolute_savings_kwh=absolute_savings,
                    pct_savings=pct_savings,
                    baseline_kwh_iqr=baseline_kwh_iqr,
                    upgrade_kwh_iqr=upgrade_kwh_iqr,
                    absolute_savings_kwh_iqr=absolute_savings_kwh_iqr,
                    pct_savings_iqr=pct_savings_iqr,
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
