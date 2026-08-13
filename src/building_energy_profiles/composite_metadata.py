"""Annual-metadata summaries and multi-measure comparisons for a `CompositeBuildingType`.

`composite.py` combines per-component *time series* (a synthetic load shape) for one representative
building per component. This module instead answers annual/whole-sample questions about the same kind of
fraction-weighted (or absolute-square-footage) composite building, using each component's average annual
metadata rather than a single building's load shape:

- `summarize_composite_metadata()`: the composite's expected annual energy total, site EUI, and energy
  broken down by fuel/end-use -- a fast way to characterize a mixed-use building's energy profile without
  downloading any time series.
- `compare_composite_measures()`: how several upgrade/measure packages change that composite's annual energy,
  expressed as savings (absolute and %) per metric column, plus a baseline-vs-measure end-use breakdown for
  each comparison -- the composite-building analogue of `compare_buildstock_metadata_upgrades`.

Both functions share the same sizing conventions as `pull_composite_time_series()`: by default each
component contributes its `fraction` share of an unspecified-size composite (fractions must sum to 1.0, see
`CompositeBuildingType.assert_normalized()`); passing `target_sqft` (a `{(product, building_type): sqft}`
map covering every component) instead scales each component to an absolute floor area, so results represent
an actual building of that combined square footage rather than a floor-area-agnostic share.

Composites that mix ComStock and ResStock components are always sized by floor area (as is any composite
given an explicit `total_sqft`), because a ResStock row is one dwelling unit rather than a whole building:
each component's floor-area share is divided by its own average size, which turns a multifamily component
into a realistic dwelling-unit count instead of a fraction of a single apartment. See
`composite.resolve_fraction_weights()` and `ComponentMetadataSummary.unit_multiplier`.

A `compare_composite_measures()` comparison entry may be a bare upgrade id (e.g. `"5"`, applied to every
component regardless of product -- only meaningful when every component shares the same upgrade catalog) or
a `"<product>:<upgrade_id>"`-prefixed entry (e.g. `"comstock:5"`) that isolates the upgrade to components of
that product only, leaving every other component at `baseline_upgrade` for that particular comparison -- so
a commercial-only measure can't silently reapply an unrelated residential upgrade that happens to share the
same numeric id, and vice versa.

Both functions also accept an optional `building_condition` map (`{(product, building_type): percentile}`)
to represent a component by a specific "building condition" (e.g. a below-average/poor-condition building at
the 10th percentile, or a highly efficient one at the 90th) instead of its full sample's plain mean -- see
`building_condition.select_building_condition_sample()` for how the percentile band, its median, and its
error range are computed. A component with no entry in `building_condition` keeps using the full sample's
mean, unaffected.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ._base import BuildStockProcessor
from .building_condition import DEFAULT_BAND, select_building_condition_sample
from .composite import CompositeBuildingType, CompositeComponent, is_dwelling_unit_product, resolve_fraction_weights
from .comstock import ComStockProcessor
from .data_dictionary import result_variables_from_columns
from .resstock import ResStockProcessor

# Fuel/end-use source names that are stock-level aggregates, not distinct fuels -- excluded from the
# by-fuel breakdown so they don't double-count alongside their constituent fuels.
_AGGREGATE_SOURCES = {"site_energy"}
# end_use labels that aren't real building end uses (accounting/rollup categories).
_NON_END_USE_LABELS = {"total", "net", "purchased"}

# Site energy is published in kWh; EUI is conventionally reported in kBtu/ft2 (the ENERGY STAR
# Portfolio Manager / DOE convention), so we convert with the standard kWh->kBtu unit factor (a unit
# conversion only, not a source-to-site energy conversion).
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


@dataclass(frozen=True)
class EndUseValue:
    key: str
    """Fuel name (for a by-fuel breakdown) or end-use name (for a by-end-use breakdown)."""
    annual_energy_kwh: float


@dataclass(frozen=True)
class ComponentMetadataSummary:
    key: tuple[str, str]
    building_type: str
    fraction: float
    building_count: int
    """Total sampled buildings/dwelling units for this component's (product, building_type) scope --
    unaffected by `building_condition` (see `condition_sample_size` for the narrower band's size)."""
    avg_sqft: float
    annual_site_energy_kwh: float
    """The full sample's mean, or (if `building_condition` set this component's percentile) the selected
    band's median -- see module docstring."""
    site_eui_kbtu_per_ft2: float
    building_condition_percentile: float | None = None
    """The percentile requested for this component via `building_condition`, if any."""
    condition_sample_size: int | None = None
    """Number of buildings/dwelling units in the percentile band, if `building_condition` was set."""
    annual_site_energy_kwh_range: tuple[float, float] | None = None
    """(min, max) annual site energy across the percentile band -- an error range reflecting how much
    buildings *within the same condition band* still vary, distinct from the full sample's spread. Only set
    when `building_condition` was set for this component."""
    unit_multiplier: float | None = None
    """How many of this component's representative buildings/dwelling units its floor area works out to --
    ~1 for a whole-building (ComStock) component sized to its own average, and the dwelling-unit count for a
    ResStock component (e.g. 28 apartments). `None` in bare-`fraction` mode, where the composite has no
    floor area to count against (see `composite.resolve_fraction_weights()`)."""


@dataclass(frozen=True)
class CompositeMetadataSummary:
    name: str
    state: str
    upgrade: str
    components: list[ComponentMetadataSummary]
    weighted_building_count: int
    weighted_avg_sqft: float
    weighted_annual_site_energy_kwh: float
    weighted_site_eui_kbtu_per_ft2: float
    by_fuel: list[EndUseValue]
    by_end_use: list[EndUseValue]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MeasureSavings:
    upgrade_id: str
    name: str | None
    product: str | None
    """Which product's catalog this comparison's upgrade came from, if the selection was product-prefixed."""
    baseline_kwh: float
    upgrade_kwh: float
    absolute_savings_kwh: float
    """baseline_kwh - upgrade_kwh: positive means the measure saves energy, negative means it increases it."""
    pct_savings: float | None


@dataclass(frozen=True)
class CompositeMeasuresComparison:
    name: str
    state: str
    baseline_upgrade: str
    comparison_upgrades: list[str]
    results: dict[str, list[MeasureSavings]]
    """column -> list of per-selection savings."""
    baseline_by_end_use: list[EndUseValue]
    by_end_use: dict[str, list[EndUseValue]]
    """selection -> annual energy by end-use category, isolated the same way as `results`."""
    warnings: list[str] = field(default_factory=list)


def _processor_for(
    component: CompositeComponent,
    save_dir: Path,
    state: str,
    county_name: str | list[str],
    upgrade: str,
    release_by_product: Mapping[str, str] | None,
    min_sqft: float | None,
    max_sqft: float | None,
) -> BuildStockProcessor:
    processor_cls: type[BuildStockProcessor] = ComStockProcessor if component.product.strip().lower() == "comstock" else ResStockProcessor
    product_base_dir = save_dir / component.product.strip().lower()
    kwargs: dict[str, Any] = {
        "state": state,
        "county_name": county_name,
        "building_type": component.building_type,
        "upgrade": upgrade,
        "base_dir": product_base_dir,
        "min_sqft": min_sqft,
        "max_sqft": max_sqft,
    }
    release = (release_by_product or {}).get(component.key[0])
    if release:
        kwargs["release"] = release
    return processor_cls(**kwargs)


def _find_column(columns: pd.Index, prefix: str) -> str | None:
    """Find a metadata column matching `prefix`, tolerating an annual-metadata "..<unit>" suffix."""
    for column in columns:
        if column == prefix or column.startswith(prefix + ".."):
            return str(column)
    return None


def _sqft_bounds_warning(component: CompositeComponent, metadata: pd.DataFrame, sqft_column: str | None, target_sqft: float) -> str | None:
    """Warn if `target_sqft` falls outside the observed `in.sqft` range of `metadata`'s sampled buildings."""
    if not sqft_column:
        return None
    sqft_values = pd.to_numeric(metadata[sqft_column], errors="coerce").dropna()
    if sqft_values.empty:
        return None
    observed_min, observed_max = float(sqft_values.min()), float(sqft_values.max())
    if observed_min <= target_sqft <= observed_max:
        return None
    return (
        f"({component.product}, {component.building_type}): entered {target_sqft:,.0f} sqft is outside the "
        f"{observed_min:,.0f}-{observed_max:,.0f} sqft range observed in the sampled {component.building_type} buildings -- "
        "results are extrapolated beyond the underlying data and may not be reliable."
    )


def _extract_metric_means(group: pd.DataFrame, columns: list[str], use_median: bool = False) -> dict[str, float]:
    """Return `{column: mean (or median, if `use_median`) value}` for each of `columns` present (after
    annual-metadata unit-suffix matching) in `group`, skipping any that are missing or all-NaN. Empty
    `group` yields `{}`. `use_median` is set when a component has a `building_condition` percentile band
    (see module docstring) -- a median is the representative value for that band, matching
    `building_condition.select_building_condition_sample()`'s own median.
    """
    if group.empty:
        return {}
    values: dict[str, float] = {}
    for column in columns:
        matched = _find_column(group.columns, column)
        if not matched:
            continue
        series = pd.to_numeric(group[matched], errors="coerce")
        value = series.median() if use_median else series.mean()
        if pd.isna(value):
            continue
        values[column] = float(value)
    return values


def _extract_end_use_means(group: pd.DataFrame, use_median: bool = False) -> dict[str, float]:
    """Return `{end_use: mean (or median, if `use_median`) value summed across fuels}` for `group`'s annual
    metadata columns (e.g. "heating" sums electricity + gas + ... heating columns together). Empty `group`
    yields `{}`.

    Note: in `use_median` mode this sums each fuel column's own median (not the median of their sum, which
    isn't well-defined column-by-column) -- a reasonable approximation, but not identical to "the band's
    median total heating energy" the way the `use_median=False` sum-of-means is exactly "the band's mean
    total heating energy" (means of a sum equal the sum of means; medians don't).
    """
    if group.empty:
        return {}
    values: dict[str, float] = {}
    for variable in result_variables_from_columns(group.columns):
        if variable.metric != "energy_consumption" or variable.source is None or variable.end_use is None:
            continue
        if variable.end_use in _NON_END_USE_LABELS or variable.source in _AGGREGATE_SOURCES:
            continue
        series = pd.to_numeric(group[variable.name], errors="coerce")
        value = series.median() if use_median else series.mean()
        if pd.isna(value):
            continue
        values[variable.end_use] = values.get(variable.end_use, 0.0) + float(value)
    return values


def _parse_measure_selection(selection: str) -> tuple[str | None, str]:
    """Parse a `comparison_upgrades` entry into `(product, upgrade_id)` -- see module docstring."""
    if ":" in selection:
        product, upgrade_id = selection.split(":", 1)
        if product in {"comstock", "resstock"}:
            return product, upgrade_id
    return None, selection


def summarize_composite_metadata(
    composite: CompositeBuildingType,
    save_dir: Path,
    state: str,
    county_name: str | list[str] = "All",
    upgrade: str = "0",
    release_by_product: Mapping[str, str] | None = None,
    min_sqft: float | None = None,
    max_sqft: float | None = None,
    target_sqft: Mapping[tuple[str, str], float] | None = None,
    total_sqft: float | None = None,
    building_condition: Mapping[tuple[str, str], float] | None = None,
    building_condition_band: float = DEFAULT_BAND,
) -> CompositeMetadataSummary:
    """Summarize a composite building's expected annual energy use: total site energy, site EUI, and a
    by-fuel/by-end-use breakdown, weighted across every component's `fraction` (or `target_sqft`, if given).

    A composite that mixes ComStock and ResStock components (or one given an explicit `total_sqft`) is sized
    by floor area instead of by bare fractions, so a ResStock component contributes a realistic dwelling-unit
    count rather than a fraction of a single apartment -- see `composite.resolve_fraction_weights()` and each
    component's `unit_multiplier`.

    Unlike `estimate_portfolio_energy()` (which reports the *population* mean and standard deviation across
    every sampled building of a type), this reports just the *mean* per component -- a faster, simpler
    "expected value" view matching `pull_composite_time_series()`'s one-representative-building-per-fraction
    model, with no statistical error bars -- unless `building_condition` selects a specific percentile band
    for a component, in which case that component instead uses the band's median (and its min/max becomes
    that component's `annual_site_energy_kwh_range`; see module docstring and
    `building_condition.select_building_condition_sample()`).
    """
    if target_sqft is None:
        composite.assert_normalized()

    component_summaries: list[ComponentMetadataSummary] = []
    by_fuel: dict[str, float] = {}
    by_end_use: dict[str, float] = {}
    weighted_sqft = 0.0
    weighted_site_energy = 0.0
    weighted_building_count = 0
    warnings: list[str] = []

    # Pass 1: load every component's sample. Scales can't be computed inline because a fraction-mode
    # composite's implied total floor area depends on *all* components' average sizes.
    loaded: list[dict[str, Any]] = []
    component_sqft: dict[tuple[str, str], float] = {}

    for component in composite.components:
        processor = _processor_for(component, save_dir, state, county_name, upgrade, release_by_product, min_sqft, max_sqft)
        metadata = processor.process_metadata(save_dir=processor.base_dir)
        if metadata.empty:
            raise ValueError(f"No buildings found for component ({component.product}, {component.building_type}) in state={state!r}.")

        sqft_column = _find_column(metadata.columns, "in.sqft")
        site_energy_column = _find_column(metadata.columns, "out.site_energy.total.energy_consumption")

        percentile = (building_condition or {}).get(component.key)
        condition_sample_size: int | None = None
        energy_range: tuple[float, float] | None = None
        source_metadata = metadata
        use_median = False

        if percentile is not None:
            selection = select_building_condition_sample(
                metadata,
                percentile=percentile,
                band=building_condition_band,
                sqft_column=sqft_column,
            )
            source_metadata = metadata[metadata["bldg_id"].isin(selection.bldg_ids)]
            condition_sample_size = selection.sample_size
            energy_range = selection.metric_ranges.get("out.site_energy.total.energy_consumption")
            use_median = True
            if condition_sample_size < 3:
                warnings.append(
                    f"({component.product}, {component.building_type}): only {condition_sample_size} building(s) fall within "
                    f"{selection.lower_percentile:.0f}-{selection.upper_percentile:.0f} percentile of site EUI -- this component's "
                    "median/range may be noisy; consider a wider building_condition_band."
                )

        avg_sqft = float(pd.to_numeric(source_metadata[sqft_column], errors="coerce").mean()) if sqft_column else 0.0
        energy_series = pd.to_numeric(source_metadata[site_energy_column], errors="coerce") if site_energy_column else None
        if energy_series is not None:
            energy_value = energy_series.median() if use_median else energy_series.mean()
            annual_site_energy = 0.0 if pd.isna(energy_value) else float(energy_value)
        else:
            annual_site_energy = 0.0

        if avg_sqft:
            component_sqft[component.key] = avg_sqft
        loaded.append(
            {
                "component": component,
                "metadata": metadata,
                "source_metadata": source_metadata,
                "sqft_column": sqft_column,
                "avg_sqft": avg_sqft,
                "annual_site_energy": annual_site_energy,
                "percentile": percentile,
                "condition_sample_size": condition_sample_size,
                "energy_range": energy_range,
                "use_median": use_median,
            }
        )

    if target_sqft is not None:
        scales: dict[tuple[str, str], float] = {}
        for component in composite.components:
            if component.key not in target_sqft:
                raise ValueError(f"Missing target_sqft for composite component {component.key}")
            if component.key not in component_sqft:
                raise ValueError(f"Could not determine floor area for component {component.key} to scale by target_sqft.")
            scales[component.key] = target_sqft[component.key] / component_sqft[component.key]
        area_scaled = True
    else:
        # A mixed ComStock/ResStock composite (or an explicit total_sqft) is sized by floor area so a
        # ResStock component becomes a dwelling-unit count rather than a fraction of one apartment.
        resolved = resolve_fraction_weights(composite, component_sqft, total_sqft)
        area_scaled = resolved is not None
        scales = resolved or {component.key: component.fraction for component in composite.components}

    # Pass 2: scale and accumulate.
    composite_total_sqft = sum(scales[component.key] * component_sqft.get(component.key, 0.0) for component in composite.components)
    for entry in loaded:
        component: CompositeComponent = entry["component"]
        avg_sqft = entry["avg_sqft"]
        annual_site_energy = entry["annual_site_energy"]
        energy_range = entry["energy_range"]
        source_metadata = entry["source_metadata"]
        use_median = entry["use_median"]
        scale = scales[component.key]

        # Site EUI (energy per sqft) is an intensity, so it's unaffected by any of the sizing modes.
        eui = (annual_site_energy * KWH_TO_KBTU) / avg_sqft if avg_sqft else 0.0

        if area_scaled:
            display_sqft = scale * avg_sqft
            display_energy = scale * annual_site_energy
            display_energy_range = (energy_range[0] * scale, energy_range[1] * scale) if energy_range is not None else None
            if not is_dwelling_unit_product(component.product):
                warning = _sqft_bounds_warning(component, entry["metadata"], entry["sqft_column"], display_sqft)
                if warning:
                    warnings.append(warning)
            elif target_sqft is None:
                warnings.append(
                    f"({component.product}, {component.building_type}): {component.fraction:.0%} of the composite's "
                    f"{composite_total_sqft:,.0f} sqft is modeled as ~{scale:,.0f} dwelling unit(s) of {avg_sqft:,.0f} sqft each."
                )
        else:
            display_sqft = avg_sqft
            display_energy = annual_site_energy
            display_energy_range = energy_range

        component_summaries.append(
            ComponentMetadataSummary(
                key=component.key,
                building_type=component.building_type,
                fraction=component.fraction,
                building_count=len(entry["metadata"]),
                avg_sqft=display_sqft,
                annual_site_energy_kwh=display_energy,
                site_eui_kbtu_per_ft2=eui,
                building_condition_percentile=entry["percentile"],
                condition_sample_size=entry["condition_sample_size"],
                annual_site_energy_kwh_range=display_energy_range,
                unit_multiplier=scale if area_scaled else None,
            )
        )

        # These accumulation lines are identical for every mode -- only `scale`'s definition differs. When
        # `area_scaled`, `scale * avg_sqft` is this component's actual floor area and `scale *
        # annual_site_energy` its energy for that area, so summing across components yields the composite's
        # total floor area and total energy (rather than a fraction-weighted average of population means).
        weighted_sqft += scale * avg_sqft
        weighted_site_energy += scale * annual_site_energy
        weighted_building_count += len(entry["metadata"])

        for variable in result_variables_from_columns(source_metadata.columns):
            if variable.metric != "energy_consumption" or variable.source is None or variable.end_use is None:
                continue
            series = pd.to_numeric(source_metadata[variable.name], errors="coerce")
            value = series.median() if use_median else series.mean()
            if pd.isna(value):
                continue
            if variable.end_use == "total" and variable.source not in _AGGREGATE_SOURCES:
                by_fuel[variable.source] = by_fuel.get(variable.source, 0.0) + scale * float(value)
            if variable.end_use not in _NON_END_USE_LABELS and variable.source not in _AGGREGATE_SOURCES:
                by_end_use[variable.end_use] = by_end_use.get(variable.end_use, 0.0) + scale * float(value)

    weighted_eui = (weighted_site_energy * KWH_TO_KBTU) / weighted_sqft if weighted_sqft else 0.0

    return CompositeMetadataSummary(
        name=composite.name,
        state=state,
        upgrade=upgrade,
        components=component_summaries,
        weighted_building_count=weighted_building_count,
        weighted_avg_sqft=weighted_sqft,
        weighted_annual_site_energy_kwh=weighted_site_energy,
        weighted_site_eui_kbtu_per_ft2=weighted_eui,
        by_fuel=sorted((EndUseValue(key=k, annual_energy_kwh=v) for k, v in by_fuel.items()), key=lambda item: -item.annual_energy_kwh),
        by_end_use=sorted(
            (EndUseValue(key=k, annual_energy_kwh=v) for k, v in by_end_use.items()), key=lambda item: -item.annual_energy_kwh
        ),
        warnings=warnings,
    )


def compare_composite_measures(
    composite: CompositeBuildingType,
    save_dir: Path,
    state: str,
    baseline_upgrade: str = "0",
    comparison_upgrades: list[str] | None = None,
    county_name: str | list[str] = "All",
    release_by_product: Mapping[str, str] | None = None,
    min_sqft: float | None = None,
    max_sqft: float | None = None,
    target_sqft: Mapping[tuple[str, str], float] | None = None,
    total_sqft: float | None = None,
    metric_columns: list[str] | None = None,
    building_condition: Mapping[tuple[str, str], float] | None = None,
    building_condition_band: float = DEFAULT_BAND,
) -> CompositeMeasuresComparison:
    """Compare how several upgrade/measure packages change a composite building's annual energy, expressed
    as savings (absolute and %) per `metric_columns` column, plus a baseline-vs-measure by-end-use
    breakdown for each comparison -- the composite-building analogue of
    `compare_buildstock_metadata_upgrades` (which compares upgrades for a single building type/product, not
    a fraction-weighted mix of several).

    See the module docstring for `comparison_upgrades` entry format (bare vs. `"<product>:<upgrade_id>"`),
    the `fraction`/`target_sqft` sizing convention shared with `pull_composite_time_series()`, and
    `building_condition`. For a `building_condition` component, the percentile band is selected *once* from
    that component's baseline-upgrade sample, and the *same* `bldg_id`s are then used for every upgrade
    being compared (not re-selected per upgrade) -- so "savings" reflect what happens to the same buildings
    under each measure, not a comparison of two different, independently-selected samples.
    """
    if target_sqft is None:
        composite.assert_normalized()
    if not comparison_upgrades:
        raise ValueError("compare_composite_measures requires at least 1 entry in comparison_upgrades.")

    columns = metric_columns or DEFAULT_METRIC_COLUMNS
    all_products = {component.key[0] for component in composite.components}
    parsed_selections = [(selection, *_parse_measure_selection(selection)) for selection in comparison_upgrades]

    # Every upgrade id that might be needed, per product -- a selection with no product prefix could apply
    # to any component, so it's needed for every product present in the composite.
    upgrades_by_product: dict[str, set[str]] = {}
    for _selection, sel_product, sel_upgrade_id in parsed_selections:
        for product in [sel_product] if sel_product else all_products:
            upgrades_by_product.setdefault(product, set()).add(sel_upgrade_id)
    for product in all_products:
        upgrades_by_product.setdefault(product, set()).add(baseline_upgrade)

    upgrade_names_by_product: dict[str, dict[str, str]] = {}
    per_selection_values: dict[str, dict[str, float]] = {}
    baseline_values: dict[str, float] = {}
    per_selection_end_use: dict[str, dict[str, float]] = {}
    baseline_end_use: dict[str, float] = {}
    warnings: list[str] = []

    # Pass 1: load each component's samples and floor area. Scales can't be computed inline because a
    # fraction-mode composite's implied total floor area depends on *all* components' average sizes.
    loaded: list[dict[str, Any]] = []
    component_sqft: dict[tuple[str, str], float] = {}

    for component in composite.components:
        processor = _processor_for(component, save_dir, state, county_name, baseline_upgrade, release_by_product, min_sqft, max_sqft)
        product = component.key[0]
        if product not in upgrade_names_by_product:
            try:
                upgrade_names_by_product[product] = processor.list_upgrades(save_dir=processor.base_dir)
            except Exception:
                upgrade_names_by_product[product] = {}

        needed_upgrades = sorted(upgrades_by_product.get(product, {baseline_upgrade}))
        combined_metadata = processor.process_metadata_for_upgrades(save_dir=processor.base_dir, upgrades=needed_upgrades)

        if combined_metadata.empty or "upgrade" not in combined_metadata.columns:
            continue
        combined_metadata = combined_metadata.copy()
        combined_metadata["upgrade"] = combined_metadata["upgrade"].astype(str)

        percentile = (building_condition or {}).get(component.key)
        use_median = percentile is not None
        selected_bldg_ids: list[int] | None = None
        if percentile is not None:
            baseline_group_for_selection = combined_metadata[combined_metadata["upgrade"] == baseline_upgrade]
            if not baseline_group_for_selection.empty:
                condition_selection = select_building_condition_sample(
                    baseline_group_for_selection,
                    percentile=percentile,
                    band=building_condition_band,
                )
                selected_bldg_ids = condition_selection.bldg_ids
                if condition_selection.sample_size < 3:
                    warnings.append(
                        f"({component.product}, {component.building_type}): only {condition_selection.sample_size} building(s) fall "
                        f"within {condition_selection.lower_percentile:.0f}-{condition_selection.upper_percentile:.0f} percentile of "
                        "site EUI -- this component's comparison may be noisy; consider a wider building_condition_band."
                    )

        # Floor area doesn't change across upgrades for the same building type, so the baseline upgrade's
        # group average sqft is used as the scaling denominator for every upgrade.
        sqft_column = _find_column(combined_metadata.columns, "in.sqft")
        baseline_group_for_sqft = combined_metadata[combined_metadata["upgrade"] == baseline_upgrade]
        if selected_bldg_ids is not None:
            baseline_group_for_sqft = baseline_group_for_sqft[baseline_group_for_sqft["bldg_id"].isin(selected_bldg_ids)]
        avg_sqft = (
            float(pd.to_numeric(baseline_group_for_sqft[sqft_column], errors="coerce").mean())
            if sqft_column and not baseline_group_for_sqft.empty
            else 0.0
        )
        if avg_sqft:
            component_sqft[component.key] = avg_sqft

        loaded.append(
            {
                "component": component,
                "product": product,
                "combined_metadata": combined_metadata,
                "selected_bldg_ids": selected_bldg_ids,
                "use_median": use_median,
                "sqft_column": sqft_column,
                "baseline_group_for_sqft": baseline_group_for_sqft,
            }
        )

    if target_sqft is not None:
        scales: dict[tuple[str, str], float] = {}
        for component in composite.components:
            if component.key not in target_sqft:
                raise ValueError(f"Missing target_sqft for composite component {component.key}")
            if component.key not in component_sqft:
                raise ValueError(f"Could not determine floor area for component {component.key} to scale by target_sqft.")
            scales[component.key] = target_sqft[component.key] / component_sqft[component.key]
        area_scaled = True
    else:
        # A mixed ComStock/ResStock composite (or an explicit total_sqft) is sized by floor area so a
        # ResStock component becomes a dwelling-unit count rather than a fraction of one apartment.
        resolved = resolve_fraction_weights(composite, component_sqft, total_sqft)
        area_scaled = resolved is not None
        scales = resolved or {component.key: component.fraction for component in composite.components}

    # Pass 2: scale and accumulate.
    for entry in loaded:
        component: CompositeComponent = entry["component"]
        product = entry["product"]
        combined_metadata = entry["combined_metadata"]
        selected_bldg_ids = entry["selected_bldg_ids"]
        use_median = entry["use_median"]
        scale = scales[component.key]

        if area_scaled and not is_dwelling_unit_product(component.product):
            warning = _sqft_bounds_warning(
                component, entry["baseline_group_for_sqft"], entry["sqft_column"], scale * component_sqft[component.key]
            )
            if warning:
                warnings.append(warning)

        baseline_group = combined_metadata[combined_metadata["upgrade"] == baseline_upgrade]
        if selected_bldg_ids is not None:
            baseline_group = baseline_group[baseline_group["bldg_id"].isin(selected_bldg_ids)]
        for column, value in _extract_metric_means(baseline_group, columns, use_median=use_median).items():
            baseline_values[column] = baseline_values.get(column, 0.0) + scale * value
        for end_use, value in _extract_end_use_means(baseline_group, use_median=use_median).items():
            baseline_end_use[end_use] = baseline_end_use.get(end_use, 0.0) + scale * value

        # Per-selection: this component uses its own upgrade id if the selection targets its product (or
        # has no product prefix); otherwise it stays at baseline_upgrade for this particular comparison.
        for selection, sel_product, sel_upgrade_id in parsed_selections:
            effective_upgrade = sel_upgrade_id if (sel_product is None or sel_product == product) else baseline_upgrade
            group = combined_metadata[combined_metadata["upgrade"] == effective_upgrade]
            if selected_bldg_ids is not None:
                # Same bldg_ids as the baseline selection -- see docstring on why we don't re-select per upgrade.
                group = group[group["bldg_id"].isin(selected_bldg_ids)]
            for column, value in _extract_metric_means(group, columns, use_median=use_median).items():
                bucket = per_selection_values.setdefault(selection, {})
                bucket[column] = bucket.get(column, 0.0) + scale * value
            for end_use, value in _extract_end_use_means(group, use_median=use_median).items():
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
                    product=sel_product,
                    baseline_kwh=baseline_value,
                    upgrade_kwh=upgrade_value,
                    absolute_savings_kwh=absolute_savings,
                    pct_savings=pct_savings,
                )
            )
        if savings_for_column:
            results[column] = savings_for_column

    return CompositeMeasuresComparison(
        name=composite.name,
        state=state,
        baseline_upgrade=baseline_upgrade,
        comparison_upgrades=comparison_upgrades,
        results=results,
        baseline_by_end_use=sorted(
            (EndUseValue(key=k, annual_energy_kwh=v) for k, v in baseline_end_use.items()), key=lambda item: -item.annual_energy_kwh
        ),
        by_end_use={
            selection: sorted(
                (EndUseValue(key=k, annual_energy_kwh=v) for k, v in values.items()), key=lambda item: -item.annual_energy_kwh
            )
            for selection, values in per_selection_end_use.items()
        },
        warnings=warnings,
    )


__all__ = [
    "DEFAULT_METRIC_COLUMNS",
    "KWH_TO_KBTU",
    "ComponentMetadataSummary",
    "CompositeMeasuresComparison",
    "CompositeMetadataSummary",
    "EndUseValue",
    "MeasureSavings",
    "compare_composite_measures",
    "summarize_composite_metadata",
]
