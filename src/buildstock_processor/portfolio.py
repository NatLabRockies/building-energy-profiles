"""Portfolio-scale, statistically-uncertain energy estimates for BuildStock.

`composite.py` models one synthetic building's *load shape* as a fraction-weighted blend of a single
representative building per component. This module instead answers a different, complementary question:
"how much annual energy does a real portfolio of buildings/dwelling units of these type(s) and size(s) use,
and how confident should I be in that number?" -- e.g. "a mixed-use development that's 20% office (by floor
area) plus a 1000-unit multifamily building, in Denver, CO".

Rather than picking one representative building and reporting its number as gospel, `estimate_portfolio_energy()`
downloads *every* sampled building/dwelling-unit BuildStock publishes for each component's
`(product, building_type, state, county_name, upgrade)` scope, and summarizes the population's mean *and*
standard deviation for each requested energy metric. That population spread becomes this estimate's "error
bars" -- a statistical uncertainty band reflecting real building-to-building variability (different
occupants, equipment, vintage, etc. within the same nominal building type), not simulation numerical error.

A component's underlying BuildStock product determines which statistical model applies to *any* of its
sizing modes (`target_sqft`, `target_units`, or `fraction`):

- ComStock simulates whole buildings (one metadata row = one representative building), so a ComStock
  component always rescales *one* building's population mean/std intensity to an actual floor area, by
  multiplying by `target_sqft / avg_sqft`. This models "my one office building is this big instead of the
  sample's average size" -- both the mean *and* the standard deviation scale by the same linear factor,
  since resizing one building doesn't reduce how uncertain we are about it.
- ResStock simulates individual dwelling units/homes (one metadata row = one simulated dwelling, whether an
  apartment unit within a larger multifamily building or a whole standalone single-family/mobile home -- see
  `resstock.py`'s module docstring), so a ResStock component's size is fundamentally a *dwelling count*, not
  a floor area -- even when the caller specifies `target_sqft` or `fraction`, this is converted to an
  equivalent dwelling count (`target_sqft / avg_sqft_per_dwelling`) before scaling. This models *summing*
  that many independent dwellings' energy use into one total. Assuming dwelling-to-dwelling energy use is
  roughly independent (a simplification -- real units in the same building share climate/construction/
  systems and are therefore correlated, so this likely *understates* true uncertainty somewhat), the mean
  scales linearly (`mean * dwelling_count`) but the standard deviation scales by `sqrt(dwelling_count)`
  (summing N i.i.d. random variables), so a 1000-unit building's *relative* uncertainty is much tighter than
  any single unit's. Every ResStock result reports *both* the resolved dwelling count and its equivalent
  square footage (whichever wasn't given directly is estimated from the sample's average dwelling size), and
  labels the count "units" for multifamily building types or "homes" for single-family/mobile home types.
  `target_units` is rejected for ComStock components, which have no per-dwelling metadata to convert from.

A `fraction` component (e.g. "office is 20% of the total mixed-use floor area") has no size of its own to
scale by -- it's resolved against the *other* components' resolved square footage: given every non-fraction
component's resolved square footage (`target_sqft` directly, or `target_units * avg_sqft_per_dwelling` for a
unit-scaled ResStock component), the implied total floor area is
`anchor_sqft / (1 - sum_of_fractions)`, and each fraction component's resolved square footage is
`fraction * total_sqft`. At least one non-fraction (anchor) component is required to resolve any fractions.
`fraction` sizing makes most sense for components that genuinely share a building envelope (e.g. ground-floor
retail under apartments, or an office portion of a mixed-use tower); it's a poor fit for ResStock's
single-family/mobile-home types, which represent whole standalone structures rather than a floor-area share
of something larger -- see `_dwelling_count_label()` below, which flags this case with a warning.

Per-component and combined (portfolio-total) results assume independence *between* components (e.g. an
office component's energy use is uncorrelated with a multifamily component's), so combined variance is the
sum of each component's scaled variance -- a standard, if simplifying, assumption for mixing unrelated
building types.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ._base import BuildStockProcessor
from .comstock import ComStockProcessor
from .resstock import ResStockProcessor

# Default annual energy metrics summarized when a caller doesn't specify `value_columns`.
DEFAULT_VALUE_COLUMNS = [
    "out.site_energy.total.energy_consumption",
    "out.electricity.total.energy_consumption",
    "out.natural_gas.total.energy_consumption",
]

# 1.96 std devs is the standard ~95% confidence interval multiplier for a roughly-normal distribution.
_CI95_Z = 1.96


@dataclass(frozen=True)
class PortfolioComponent:
    """One `(product, building_type)` component of a portfolio energy estimate, sized by exactly one of
    `target_sqft`, `target_units`, or `fraction` -- see module docstring for what each means.
    """

    product: str
    """"comstock" or "resstock"."""
    building_type: str
    """A ComStockProcessor/ResStockProcessor building type (e.g. "MediumOffice", "Multi-Family with 5+ Units")."""
    target_sqft: float | None = None
    """Absolute target square footage for this component (e.g. a 30,000 sqft office building)."""
    target_units: float | None = None
    """Absolute target dwelling count for this component (e.g. 1000 apartment units, or 40 single-family
    homes). Only valid for a ResStock component, since each ResStock metadata row is already one simulated
    dwelling unit/home; ComStock has no per-dwelling metadata to size by count."""
    fraction: float | None = None
    """This component's share, in (0, 1), of the *total* portfolio's floor area -- resolved against the
    other components' resolved square footage (see module docstring). Requires at least one other
    component in the same portfolio to set `target_sqft`/`target_units`."""

    def __post_init__(self) -> None:
        normalized_product = self.product.strip().lower()
        if normalized_product not in {"comstock", "resstock"}:
            raise ValueError(f"PortfolioComponent product must be 'comstock' or 'resstock', got {self.product!r}")
        set_modes = [
            mode_name
            for mode_name, value in (("target_sqft", self.target_sqft), ("target_units", self.target_units), ("fraction", self.fraction))
            if value is not None
        ]
        if len(set_modes) != 1:
            raise ValueError(
                f"PortfolioComponent for building_type={self.building_type!r} must set exactly one of "
                f"target_sqft, target_units, or fraction; got {set_modes or 'none'}."
            )
        if self.target_units is not None and normalized_product != "resstock":
            raise ValueError(
                f"PortfolioComponent for building_type={self.building_type!r} sets target_units, but target_units is only "
                "valid for resstock components (ComStock has no per-dwelling metadata to size by count) -- use target_sqft instead."
            )
        if self.target_sqft is not None and self.target_sqft <= 0:
            raise ValueError(f"PortfolioComponent target_sqft must be > 0, got {self.target_sqft}")
        if self.target_units is not None and self.target_units <= 0:
            raise ValueError(f"PortfolioComponent target_units must be > 0, got {self.target_units}")
        if self.fraction is not None and not 0 < self.fraction < 1:
            raise ValueError(f"PortfolioComponent fraction must be in (0, 1), got {self.fraction}")

    @property
    def key(self) -> tuple[str, str]:
        """The `(product, building_type)` pair identifying this component."""
        return (self.product.strip().lower(), self.building_type)

    @property
    def sizing_mode(self) -> str:
        if self.target_sqft is not None:
            return "sqft"
        if self.target_units is not None:
            return "units"
        return "fraction"


@dataclass(frozen=True)
class MetricStats:
    """Population mean/std (across every sampled building/unit in scope) for one energy metric column, and
    that same distribution rescaled to this component's resolved size -- the scaled mean/std are what feed
    into the combined portfolio total and its error bars.
    """

    column: str
    sample_mean: float
    """Mean of `column` across every sampled building/dwelling-unit in this component's scope, unscaled."""
    sample_std: float
    """Standard deviation of `column` across the same sample -- the source of this estimate's error bars."""
    scaled_mean: float
    scaled_std: float


@dataclass(frozen=True)
class ComponentEstimate:
    """One component's resolved sizing and per-metric statistics."""

    key: tuple[str, str]
    building_type: str
    sizing_mode: str
    sample_size: int
    avg_sqft: float | None
    resolved_target_sqft: float | None
    """This component's resolved (or, for a ResStock component, *estimated* -- see `dwelling_count_label`)
    absolute square footage."""
    resolved_target_units: float | None
    """This component's resolved dwelling count. Always set for ResStock components (directly from
    `target_units`, or estimated from `target_sqft`/`fraction` via the sample's average dwelling size);
    always `None` for ComStock components, which have no per-dwelling metadata to estimate a count from."""
    dwelling_count_label: str | None
    """"units" or "homes" for a ResStock component (see module docstring); `None` for ComStock."""
    metrics: dict[str, MetricStats]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CombinedMetric:
    """Portfolio-total mean/std/95% CI for one energy metric, combined across every component assuming
    component-to-component independence (see module docstring).
    """

    column: str
    mean: float
    std: float
    ci95_low: float
    ci95_high: float


@dataclass(frozen=True)
class PortfolioEnergyEstimate:
    components: list[ComponentEstimate]
    combined: dict[str, CombinedMetric]
    warnings: list[str]


def _processor_for(
    component: PortfolioComponent,
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


def _find_sqft_column(columns: pd.Index) -> str | None:
    for column in columns:
        if column == "in.sqft" or column.startswith("in.sqft.."):
            return str(column)
    return None


def _dwelling_count_label(building_type: str) -> str:
    """Return "units" for a ResStock multifamily building type, or "homes" for a standalone
    single-family/mobile-home type -- every ResStock metadata row is one simulated dwelling either way (see
    module docstring), but the natural way to describe a count of them differs.
    """
    return "units" if "Multi-Family" in building_type else "homes"


def _resolve_metric_columns(columns: pd.Index, requested: list[str]) -> tuple[dict[str, str], list[str]]:
    """Map each requested bare `out.*` column to the actual metadata column, tolerating ResStock's
    "..<unit>" suffix (see `composite.normalize_time_series_columns`). Returns (requested -> actual,
    columns with no match at all).
    """
    normalized = {(column.split("..", 1)[0] if ".." in column else column): column for column in columns}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for column in requested:
        if column in normalized:
            resolved[column] = normalized[column]
        else:
            missing.append(column)
    return resolved, missing


def _component_metadata_and_stats(
    component: PortfolioComponent,
    save_dir: Path,
    state: str,
    county_name: str | list[str],
    upgrade: str,
    release_by_product: Mapping[str, str] | None,
    min_sqft: float | None,
    max_sqft: float | None,
    value_columns: list[str],
) -> tuple[pd.DataFrame, float | None, dict[str, tuple[float, float]], list[str]]:
    """Download this component's full metadata sample and return
    `(metadata, avg_sqft, {column: (mean, std)}, warnings)`.
    """
    warnings: list[str] = []
    processor = _processor_for(component, save_dir, state, county_name, upgrade, release_by_product, min_sqft, max_sqft)
    metadata = processor.process_metadata(save_dir=processor.base_dir)
    if metadata.empty:
        raise ValueError(
            f"No buildings/units found for component ({component.product}, {component.building_type}) "
            f"in state={state!r}, county_name={county_name!r}."
        )

    sqft_column = _find_sqft_column(metadata.columns)
    avg_sqft = float(pd.to_numeric(metadata[sqft_column], errors="coerce").mean()) if sqft_column else None

    column_map, missing_columns = _resolve_metric_columns(metadata.columns, value_columns)
    if missing_columns:
        warnings.append(
            f"Component ({component.product}, {component.building_type}): metric column(s) not found and skipped: {missing_columns}"
        )

    stats: dict[str, tuple[float, float]] = {}
    for requested, actual in column_map.items():
        series = pd.to_numeric(metadata[actual], errors="coerce").dropna()
        if series.empty:
            continue
        # ddof=0 (population std, not sample std) since we treat every published record as the full
        # population of interest for this scope, not a sub-sample drawn from it.
        stats[requested] = (float(series.mean()), float(series.std(ddof=0)))

    return metadata, avg_sqft, stats, warnings


def estimate_portfolio_energy(
    components: Sequence[PortfolioComponent],
    save_dir: Path,
    state: str,
    county_name: str | list[str] = "All",
    upgrade: str = "0",
    release_by_product: Mapping[str, str] | None = None,
    min_sqft: float | None = None,
    max_sqft: float | None = None,
    value_columns: list[str] | None = None,
) -> PortfolioEnergyEstimate:
    """Estimate a multi-component portfolio's annual energy use, with error bars from real BuildStock
    building-to-building variability.

    See the module docstring for the full model: each component is sized by `target_sqft`, `target_units`,
    or `fraction` (resolved against the other components), and per-component/combined results include a
    population mean and standard deviation for every metric in `value_columns` (default:
    `DEFAULT_VALUE_COLUMNS`).

    Args:
        components: 1+ `PortfolioComponent`s. If any use `fraction` sizing, at least one other component
            must use `target_sqft`/`target_units` to anchor the implied total floor area.
        save_dir: base directory for downloaded/cached metadata (one subfolder per product).
        state: 2-letter state abbreviation shared by every component.
        county_name: county filter shared by every component.
        upgrade: upgrade id shared by every component (e.g. "0" for baseline).
        release_by_product: optional `{"comstock": release_id, "resstock": release_id}` override.
        min_sqft, max_sqft: optional shared square-footage filters applied to each component's metadata query.
        value_columns: annual energy metric columns to summarize; defaults to `DEFAULT_VALUE_COLUMNS`.

    Returns:
        A `PortfolioEnergyEstimate` with resolved per-component stats/sizing and combined portfolio totals.
    """
    if not components:
        raise ValueError("estimate_portfolio_energy requires at least 1 component.")
    keys = [component.key for component in components]
    if len(set(keys)) != len(keys):
        raise ValueError(f"Portfolio components must have unique (product, building_type) pairs, got {keys}")

    selected_columns = value_columns or DEFAULT_VALUE_COLUMNS
    warnings: list[str] = []

    per_component_data: dict[tuple[str, str], tuple[pd.DataFrame, float | None, dict[str, tuple[float, float]]]] = {}
    for component in components:
        metadata, avg_sqft, stats, metadata_warnings = _component_metadata_and_stats(
            component, save_dir, state, county_name, upgrade, release_by_product, min_sqft, max_sqft, selected_columns
        )
        per_component_data[component.key] = (metadata, avg_sqft, stats)
        warnings.extend(metadata_warnings)

    # Resolve each non-fraction component's absolute floor area (used both as its own scaling basis and,
    # summed, as the anchor for resolving any `fraction` components).
    anchor_sqft_total = 0.0
    fraction_sum = 0.0
    for component in components:
        _metadata, avg_sqft, _stats = per_component_data[component.key]
        if component.target_sqft is not None:
            anchor_sqft_total += component.target_sqft
        elif component.target_units is not None:
            if not avg_sqft:
                raise ValueError(
                    f"Could not determine floor area for component ({component.product}, {component.building_type}) "
                    "to resolve its contribution to the portfolio's total square footage."
                )
            anchor_sqft_total += component.target_units * avg_sqft
        else:
            fraction_sum += component.fraction or 0.0

    if fraction_sum > 0 and anchor_sqft_total <= 0:
        raise ValueError(
            "At least one component must set target_sqft/target_units to anchor the total floor area used to "
            "resolve fraction-sized components."
        )
    if fraction_sum >= 1:
        raise ValueError(
            f"Fraction-sized components must sum to less than 1.0 (they leave room for the anchor components), got {fraction_sum}."
        )
    total_sqft = anchor_sqft_total / (1 - fraction_sum) if fraction_sum > 0 else anchor_sqft_total

    component_estimates: list[ComponentEstimate] = []
    combined_mean: dict[str, float] = dict.fromkeys(selected_columns, 0.0)
    combined_variance: dict[str, float] = dict.fromkeys(selected_columns, 0.0)

    for component in components:
        metadata, avg_sqft, stats = per_component_data[component.key]
        component_warnings: list[str] = []
        resolved_target_sqft: float | None = None
        resolved_target_units: float | None = None
        dwelling_count_label: str | None = None

        if component.product.strip().lower() == "resstock":
            # ResStock rows are always one independent dwelling (apartment unit or standalone home), so
            # sizing is fundamentally a dwelling *count* -- even a target_sqft/fraction request is converted
            # to an equivalent count via the sample's average dwelling size, and both the resolved count and
            # its equivalent square footage are reported regardless of which one the caller provided.
            if not avg_sqft:
                raise ValueError(f"Could not determine floor area for component ({component.product}, {component.building_type}) to scale.")
            if component.target_units is not None:
                dwelling_count = component.target_units
            elif component.target_sqft is not None:
                dwelling_count = component.target_sqft / avg_sqft
            elif component.fraction is not None:
                dwelling_count = (component.fraction * total_sqft) / avg_sqft
            else:
                # Unreachable: __post_init__ guarantees exactly one of target_sqft/target_units/fraction is set.
                raise ValueError(f"Component ({component.product}, {component.building_type}) has no resolvable sizing.")

            resolved_target_units = dwelling_count
            resolved_target_sqft = dwelling_count * avg_sqft
            dwelling_count_label = _dwelling_count_label(component.building_type)
            scale_mean = dwelling_count
            scale_std = math.sqrt(dwelling_count)

            if dwelling_count_label == "units":
                units_column = next((c for c in metadata.columns if c.startswith("in.geometry_building_number_units_mf")), None)
                if units_column is not None:
                    observed = pd.to_numeric(metadata[units_column], errors="coerce").dropna()
                    if not observed.empty and not (observed.min() <= dwelling_count <= observed.max()):
                        component_warnings.append(
                            f"({component.product}, {component.building_type}): resolved target of {dwelling_count:,.0f} units is outside "
                            f"the {observed.min():,.0f}-{observed.max():,.0f} unit range observed in sampled buildings of this type -- "
                            "results are extrapolated beyond the underlying data."
                        )
            if component.sizing_mode == "fraction" and dwelling_count_label == "homes":
                component_warnings.append(
                    f"({component.product}, {component.building_type}): sizing a standalone single-family/mobile-home component by "
                    "fraction-of-floor-area is unusual -- each sampled row is already a whole separate home, not a floor-area share of a "
                    "shared building. Consider target_units (a home count) instead."
                )
        else:
            if component.target_sqft is not None:
                resolved_target_sqft = component.target_sqft
            elif component.fraction is not None:
                resolved_target_sqft = component.fraction * total_sqft
            else:
                # Unreachable: __post_init__ guarantees exactly one of target_sqft/target_units/fraction is
                # set, and this branch is only reached when target_units and target_sqft are both None.
                raise ValueError(f"Component ({component.product}, {component.building_type}) has no resolvable sizing.")
            if not avg_sqft:
                raise ValueError(f"Could not determine floor area for component ({component.product}, {component.building_type}) to scale.")
            scale_mean = resolved_target_sqft / avg_sqft
            scale_std = scale_mean
            sqft_column = _find_sqft_column(metadata.columns)
            if sqft_column is not None:
                observed = pd.to_numeric(metadata[sqft_column], errors="coerce").dropna()
                if not observed.empty and not (observed.min() <= resolved_target_sqft <= observed.max()):
                    component_warnings.append(
                        f"({component.product}, {component.building_type}): resolved target of {resolved_target_sqft:,.0f} sqft is outside the "
                        f"{observed.min():,.0f}-{observed.max():,.0f} sqft range observed in sampled buildings of this type -- "
                        "results are extrapolated beyond the underlying data."
                    )

        metrics: dict[str, MetricStats] = {}
        for column in selected_columns:
            if column not in stats:
                continue
            sample_mean, sample_std = stats[column]
            scaled_mean = sample_mean * scale_mean
            scaled_std = sample_std * scale_std
            metrics[column] = MetricStats(
                column=column,
                sample_mean=sample_mean,
                sample_std=sample_std,
                scaled_mean=scaled_mean,
                scaled_std=scaled_std,
            )
            combined_mean[column] += scaled_mean
            combined_variance[column] += scaled_std**2

        component_estimates.append(
            ComponentEstimate(
                key=component.key,
                building_type=component.building_type,
                sizing_mode=component.sizing_mode,
                sample_size=len(metadata),
                avg_sqft=avg_sqft,
                resolved_target_sqft=resolved_target_sqft,
                resolved_target_units=resolved_target_units,
                dwelling_count_label=dwelling_count_label,
                metrics=metrics,
                warnings=component_warnings,
            )
        )
        warnings.extend(component_warnings)

    combined: dict[str, CombinedMetric] = {}
    for column in selected_columns:
        if column not in combined_variance:
            continue
        mean = combined_mean[column]
        std = math.sqrt(combined_variance[column])
        combined[column] = CombinedMetric(
            column=column,
            mean=mean,
            std=std,
            ci95_low=mean - _CI95_Z * std,
            ci95_high=mean + _CI95_Z * std,
        )

    return PortfolioEnergyEstimate(components=component_estimates, combined=combined, warnings=warnings)


__all__ = [
    "DEFAULT_VALUE_COLUMNS",
    "CombinedMetric",
    "ComponentEstimate",
    "MetricStats",
    "PortfolioComponent",
    "PortfolioEnergyEstimate",
    "estimate_portfolio_energy",
]
