"""Percentile-banded "building condition" sample selection for BuildStock metadata.

Rather than always representing a building type by its full sample's plain average, a caller can instead
pick a target percentile (e.g. "10th percentile" for a below-average/poor-condition building, "90th
percentile" for a highly efficient one) along the sample's site EUI (energy per square foot) distribution
-- used here as a proxy for "building condition" since it normalizes for building size, so the percentile
reflects efficiency/vintage/equipment quality rather than just being a bigger or smaller building.

Since real BuildStock samples are finite, no single building sits at an *exact* percentile, so
`select_building_condition_sample()` selects every building within a percentile *band* (default +/-5
percentile points) around the target instead of trying to find one exact match:

- The band's per-metric **median** becomes the representative value for that condition (a robust
  "typical building near this percentile" summary, less sensitive to one outlier's exact rank than the mean
  would be for a narrow band).
- The band's per-metric **min/max range** becomes an error range -- how much buildings *within the same
  condition band* still vary from each other, distinct from (and typically narrower than) the full sample's
  spread.
- The band's median-EUI building's own `bldg_id` is surfaced as a single representative building, e.g. for
  pulling one actual time series to display (see `composite.pull_composite_time_series`'s
  `building_condition` parameter).

Callers that don't set a percentile keep the existing behavior of using the full sample's plain mean (see
each consuming function's own docstring) -- this module is opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

DEFAULT_BAND = 5.0

# Site energy is published in kWh; EUI is conventionally reported in kBtu/ft2 (the ENERGY STAR Portfolio
# Manager / DOE convention), so we convert with the standard kWh->kBtu unit factor (a unit conversion only,
# not a source-to-site energy conversion). Ranking/percentile order is unaffected either way (a constant
# multiplicative factor doesn't change relative rank), but the reported `eui_kbtu_per_ft2_median` value
# needs it to actually be in kBtu/ft2 as its name promises.
KWH_TO_KBTU = 3.412141633


@dataclass(frozen=True)
class BuildingConditionSelection:
    """A percentile-banded subset of one component's full metadata sample, selected by site EUI rank."""

    percentile: float
    """The target percentile requested (0-100), before clamping to the sample's available range."""
    band: float
    """+/- percentile points around `percentile` that were included (see `DEFAULT_BAND`)."""
    lower_percentile: float
    """The actual (clamped to [0, 100]) lower bound of the selected band."""
    upper_percentile: float
    """The actual (clamped to [0, 100]) upper bound of the selected band."""
    sample_size: int
    """Number of buildings/dwelling units in the selected band."""
    bldg_ids: list[int]
    """Every `bldg_id` in the selected band, sorted by ascending site EUI."""
    median_bldg_id: int
    """The band's median-site-EUI building/unit -- a single representative building for this condition."""
    eui_kbtu_per_ft2_median: float
    """The band's median site EUI (kBtu/ft2) -- what "condition" this selection actually landed on."""
    metric_medians: dict[str, float] = field(default_factory=dict)
    """column -> median value across the selected band, for every requested metric column."""
    metric_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)
    """column -> (min, max) across the selected band -- the error range for that metric."""


def _find_column(columns: pd.Index, prefix: str) -> str | None:
    """Find a metadata column matching `prefix`, tolerating an annual-metadata "..<unit>" suffix."""
    for column in columns:
        if column == prefix or column.startswith(prefix + ".."):
            return str(column)
    return None


def select_building_condition_sample(
    metadata: pd.DataFrame,
    percentile: float,
    band: float = DEFAULT_BAND,
    sqft_column: str | None = None,
    energy_column: str = "out.site_energy.total.energy_consumption",
    metric_columns: list[str] | None = None,
    bldg_id_column: str = "bldg_id",
) -> BuildingConditionSelection:
    """Select the buildings/dwelling units within `[percentile - band, percentile + band]` of `metadata`'s
    site EUI (`energy_column / sqft_column`) distribution.

    Args:
        metadata: one component's full metadata sample (e.g. from `BuildStockProcessor.process_metadata()`).
        percentile: target percentile (0-100) along the sample's site EUI distribution; clamped to [0, 100].
        band: +/- percentile points around `percentile` to include (default `DEFAULT_BAND` = 5.0); widened
            automatically (see below) if the initial band selects no rows.
        sqft_column: floor-area column name; auto-detected (`in.sqft` family) if not given.
        energy_column: annual energy column used as the EUI numerator; tolerates a "..<unit>" suffix.
        metric_columns: additional columns to compute a median/range for, alongside `energy_column`
            (e.g. by-fuel breakdown columns). Missing/all-NaN columns are silently skipped.
        bldg_id_column: the building/dwelling-unit identifier column.

    Returns:
        A `BuildingConditionSelection` describing the selected band, its representative building, and its
        per-metric median/range.

    Raises:
        ValueError: if `metadata` is empty, or has no usable site EUI (missing/all-NaN energy or sqft).
    """
    if metadata.empty:
        raise ValueError("Cannot select a building-condition sample from empty metadata.")

    resolved_sqft_column = sqft_column or _find_column(metadata.columns, "in.sqft")
    resolved_energy_column = _find_column(metadata.columns, energy_column)
    if resolved_sqft_column is None or resolved_energy_column is None:
        raise ValueError(f"Could not find both a floor-area column and {energy_column!r} in metadata to compute site EUI.")

    sqft = pd.to_numeric(metadata[resolved_sqft_column], errors="coerce")
    energy = pd.to_numeric(metadata[resolved_energy_column], errors="coerce")
    eui = ((energy * KWH_TO_KBTU) / sqft).replace([float("inf"), float("-inf")], pd.NA)

    working = metadata.assign(_building_condition_eui=eui).dropna(subset=["_building_condition_eui"])
    if working.empty:
        raise ValueError(f"No rows with a valid site EUI (non-null, non-zero {resolved_sqft_column}) found.")

    working = working.assign(_building_condition_rank=working["_building_condition_eui"].rank(pct=True) * 100.0)

    clamped_percentile = max(0.0, min(100.0, percentile))
    clamped_band = max(0.0, band)
    lower = max(0.0, clamped_percentile - clamped_band)
    upper = min(100.0, clamped_percentile + clamped_band)

    selected = working[(working["_building_condition_rank"] >= lower) & (working["_building_condition_rank"] <= upper)]
    while selected.empty and (lower > 0.0 or upper < 100.0):
        # Extremely small samples or a narrow band near the tails can select nothing -- widen the band
        # around the (clamped) target percentile until at least one row qualifies, rather than raising.
        lower = max(0.0, lower - DEFAULT_BAND)
        upper = min(100.0, upper + DEFAULT_BAND)
        selected = working[(working["_building_condition_rank"] >= lower) & (working["_building_condition_rank"] <= upper)]

    selected = selected.sort_values("_building_condition_eui")
    eui_median = float(selected["_building_condition_eui"].median())
    # The median EUI value rarely belongs to an actual row in a finite sample -- use the real row closest
    # to it so `median_bldg_id` is an identifiable building, not an interpolated one.
    median_row = selected.iloc[(selected["_building_condition_eui"] - eui_median).abs().argsort().iloc[0]]

    requested_columns = [energy_column, *(metric_columns or [])]
    metric_medians: dict[str, float] = {}
    metric_ranges: dict[str, tuple[float, float]] = {}
    for requested in dict.fromkeys(requested_columns):  # de-dupe, preserving order
        matched = requested if requested in selected.columns else _find_column(selected.columns, requested)
        if not matched:
            continue
        series = pd.to_numeric(selected[matched], errors="coerce").dropna()
        if series.empty:
            continue
        metric_medians[requested] = float(series.median())
        metric_ranges[requested] = (float(series.min()), float(series.max()))

    return BuildingConditionSelection(
        percentile=percentile,
        band=band,
        lower_percentile=lower,
        upper_percentile=upper,
        sample_size=len(selected),
        bldg_ids=[int(v) for v in selected[bldg_id_column].tolist()],
        median_bldg_id=int(median_row[bldg_id_column]),
        eui_kbtu_per_ft2_median=eui_median,
        metric_medians=metric_medians,
        metric_ranges=metric_ranges,
    )


__all__ = ["DEFAULT_BAND", "BuildingConditionSelection", "select_building_condition_sample"]
