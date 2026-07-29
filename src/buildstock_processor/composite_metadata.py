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

A `compare_composite_measures()` comparison entry may be a bare upgrade id (e.g. `"5"`, applied to every
component regardless of product -- only meaningful when every component shares the same upgrade catalog) or
a `"<product>:<upgrade_id>"`-prefixed entry (e.g. `"comstock:5"`) that isolates the upgrade to components of
that product only, leaving every other component at `baseline_upgrade` for that particular comparison -- so
a commercial-only measure can't silently reapply an unrelated residential upgrade that happens to share the
same numeric id, and vice versa.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ._base import BuildStockProcessor
from .composite import CompositeBuildingType, CompositeComponent
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
    avg_sqft: float
    annual_site_energy_kwh: float
    site_eui_kbtu_per_ft2: float


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
    """Return `{end_use: mean value summed across fuels}` for `group`'s annual metadata columns (e.g.
    "heating" sums electricity + gas + ... heating columns together). Empty `group` yields `{}`."""
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
) -> CompositeMetadataSummary:
    """Summarize a composite building's expected annual energy use: total site energy, site EUI, and a
    by-fuel/by-end-use breakdown, weighted across every component's `fraction` (or `target_sqft`, if given).

    Unlike `estimate_portfolio_energy()` (which reports the *population* mean and standard deviation across
    every sampled building of a type), this reports just the *mean* per component -- a faster, simpler
    "expected value" view matching `pull_composite_time_series()`'s one-representative-building-per-fraction
    model, with no statistical error bars.
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

    for component in composite.components:
        processor = _processor_for(component, save_dir, state, county_name, upgrade, release_by_product, min_sqft, max_sqft)
        metadata = processor.process_metadata(save_dir=processor.base_dir)
        if metadata.empty:
            raise ValueError(f"No buildings found for component ({component.product}, {component.building_type}) in state={state!r}.")

        sqft_column = _find_column(metadata.columns, "in.sqft")
        avg_sqft = float(pd.to_numeric(metadata[sqft_column], errors="coerce").mean()) if sqft_column else 0.0

        site_energy_column = _find_column(metadata.columns, "out.site_energy.total.energy_consumption")
        annual_site_energy = float(pd.to_numeric(metadata[site_energy_column], errors="coerce").mean()) if site_energy_column else 0.0

        # Site EUI (energy per sqft) is an intensity, so it's unaffected by target_sqft-mode scaling either way.
        eui = (annual_site_energy * KWH_TO_KBTU) / avg_sqft if avg_sqft else 0.0

        if target_sqft is not None:
            if component.key not in target_sqft:
                raise ValueError(f"Missing target_sqft for composite component {component.key}")
            if not avg_sqft:
                raise ValueError(f"Could not determine floor area for component {component.key} to scale by target_sqft.")
            display_sqft = target_sqft[component.key]
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
            ComponentMetadataSummary(
                key=component.key,
                building_type=component.building_type,
                fraction=component.fraction,
                building_count=len(metadata),
                avg_sqft=display_sqft,
                annual_site_energy_kwh=display_energy,
                site_eui_kbtu_per_ft2=eui,
            )
        )

        # These accumulation lines are identical for both modes -- only `scale`'s definition differs. In
        # target_sqft mode, `scale * avg_sqft == target_sqft` and `scale * annual_site_energy == intensity *
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
    metric_columns: list[str] | None = None,
) -> CompositeMeasuresComparison:
    """Compare how several upgrade/measure packages change a composite building's annual energy, expressed
    as savings (absolute and %) per `metric_columns` column, plus a baseline-vs-measure by-end-use
    breakdown for each comparison -- the composite-building analogue of
    `compare_buildstock_metadata_upgrades` (which compares upgrades for a single building type/product, not
    a fraction-weighted mix of several).

    See the module docstring for `comparison_upgrades` entry format (bare vs. `"<product>:<upgrade_id>"`)
    and the `fraction`/`target_sqft` sizing convention shared with `pull_composite_time_series()`.
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

        if target_sqft is not None:
            # Floor area doesn't change across upgrades for the same building type, so the baseline
            # upgrade's group average sqft is used as the scaling denominator for every upgrade.
            sqft_column = _find_column(combined_metadata.columns, "in.sqft")
            baseline_group_for_sqft = combined_metadata[combined_metadata["upgrade"] == baseline_upgrade]
            avg_sqft = (
                float(pd.to_numeric(baseline_group_for_sqft[sqft_column], errors="coerce").mean())
                if sqft_column and not baseline_group_for_sqft.empty
                else 0.0
            )
            if not avg_sqft:
                raise ValueError(f"Could not determine floor area for component {component.key} to scale by target_sqft.")
            if component.key not in target_sqft:
                raise ValueError(f"Missing target_sqft for composite component {component.key}")
            scale = target_sqft[component.key] / avg_sqft
            warning = _sqft_bounds_warning(component, baseline_group_for_sqft, sqft_column, target_sqft[component.key])
            if warning:
                warnings.append(warning)
        else:
            scale = component.fraction

        baseline_group = combined_metadata[combined_metadata["upgrade"] == baseline_upgrade]
        for column, value in _extract_metric_means(baseline_group, columns).items():
            baseline_values[column] = baseline_values.get(column, 0.0) + scale * value
        for end_use, value in _extract_end_use_means(baseline_group).items():
            baseline_end_use[end_use] = baseline_end_use.get(end_use, 0.0) + scale * value

        # Per-selection: this component uses its own upgrade id if the selection targets its product (or
        # has no product prefix); otherwise it stays at baseline_upgrade for this particular comparison.
        for selection, sel_product, sel_upgrade_id in parsed_selections:
            effective_upgrade = sel_upgrade_id if (sel_product is None or sel_product == product) else baseline_upgrade
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
