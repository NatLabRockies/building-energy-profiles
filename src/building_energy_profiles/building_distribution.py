"""Full-distribution ("probability distribution function") building selection for BuildStock metadata.

Complements `building_condition.py`'s percentile-*band* selection with a full-sample view: given one
composite component's metadata sample, compute a smoothed density curve (a Gaussian KDE) and a histogram of
site EUI across every sampled building, plus every individual (bldg_id, EUI) point -- so a caller (e.g. the
webapp's building-selection step) can let a user click anywhere along the curve and pick the real building
closest to that point, or jump straight to a specific percentile/mean via `PERCENTILE_TARGETS`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from building_energy_profiles.building_condition import KWH_TO_KBTU

DEFAULT_ENERGY_COLUMN = "out.site_energy.total.energy_consumption"
DEFAULT_BINS = 30
DEFAULT_KDE_POINTS = 200
# Cap on the number of individual building points shipped to a caller -- BuildStock samples per building
# type/state are usually a few hundred to a few thousand, so this only kicks in for the largest samples.
# Percentile/mean lookups always use the full (undownsampled) population regardless of this cap.
MAX_POINTS_RETURNED = 2000

# name -> target percentile (0-100) along the site EUI distribution. "mean" is handled separately (the
# building nearest the arithmetic mean, not a rank-based percentile) -- see `compute_building_distribution`.
PERCENTILE_TARGETS: dict[str, float] = {"p5": 5.0, "p25": 25.0, "median": 50.0, "p75": 75.0, "p95": 95.0}


def _find_column(columns: pd.Index, prefix: str) -> str | None:
    """Find a metadata column matching `prefix`, tolerating an annual-metadata "..<unit>" suffix."""
    for column in columns:
        if column == prefix or column.startswith(prefix + ".."):
            return str(column)
    return None


@dataclass(frozen=True)
class DistributionPoint:
    """One real building's position along a `BuildingDistribution`."""

    bldg_id: int
    value: float
    """The distribution's metric value for this building (site EUI, kBtu/ft2/yr, by default)."""
    percentile_rank: float
    """This building's percentile rank (0-100) within the full sample."""
    sqft: float | None = None
    annual_site_energy_kwh: float | None = None


@dataclass(frozen=True)
class BuildingDistribution:
    """A full-sample distribution for one composite component, ready to plot as a PDF curve/histogram and
    to pick a representative building from -- either by exact percentile/mean, or by nearest value to an
    arbitrary point (e.g. a user's click on a chart)."""

    metric: str
    unit: str
    sample_size: int
    mean_value: float
    points: list[DistributionPoint]
    """Every (possibly downsampled, see `MAX_POINTS_RETURNED`) building in the sample, sorted ascending by
    `value` -- suitable for a "rug plot" and for nearest-value lookups."""
    histogram_bin_edges: list[float]
    histogram_counts: list[int]
    histogram_density: list[float]
    """A normalized histogram *is* a piecewise-constant probability density estimate: each bar's height is
    its count divided by `(sample_size * bin_width)`, so the total area under the bars integrates to 1."""
    kde_x: list[float]
    kde_y: list[float]
    """A smoothed Gaussian kernel density estimate (x, y) -- the continuous "PDF curve" look, sampled at
    `kde_x`. Empty for degenerate samples (fewer than 2 distinct values) where a density curve isn't
    meaningful."""
    percentile_buildings: dict[str, DistributionPoint] = field(default_factory=dict)
    """Quick-select markers: keys `"p5"`, `"p25"`, `"median"`, `"p75"`, `"p95"` (see `PERCENTILE_TARGETS`)
    plus `"mean"` -- each the real building whose value is closest to that statistic."""


def _nearest_row(frame: pd.DataFrame, value_column: str, target_value: float) -> pd.Series:
    idx = (frame[value_column] - target_value).abs().idxmin()
    return frame.loc[idx]


def _gaussian_kde(values: np.ndarray, grid_points: int) -> tuple[list[float], list[float]]:
    """Evaluate a Gaussian kernel density estimate of `values` at `grid_points` evenly-spaced locations
    spanning (and slightly padded beyond) their range, using Silverman's rule of thumb for bandwidth.

    Implemented directly with numpy (rather than e.g. `scipy.stats.gaussian_kde`) to avoid adding a scipy
    dependency for this one calculation -- fine at BuildStock's per-building-type sample sizes (tens to low
    thousands of buildings), where the O(n * grid_points) broadcasted evaluation below is negligible.
    """
    n = len(values)
    std = float(np.std(values))
    if n < 2 or std == 0:
        return [], []
    bandwidth = 1.06 * std * n ** (-1.0 / 5.0)
    if not bandwidth:
        return [], []
    value_min, value_max = float(values.min()), float(values.max())
    pad = (value_max - value_min) * 0.1 or bandwidth
    grid = np.linspace(value_min - pad, value_max + pad, grid_points)
    diffs = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * diffs**2).sum(axis=1) / (n * bandwidth * np.sqrt(2 * np.pi))
    return grid.tolist(), density.tolist()


def compute_building_distribution(
    metadata: pd.DataFrame,
    energy_column: str = DEFAULT_ENERGY_COLUMN,
    sqft_column: str | None = None,
    bldg_id_column: str = "bldg_id",
    bins: int = DEFAULT_BINS,
    kde_points: int = DEFAULT_KDE_POINTS,
    max_points: int = MAX_POINTS_RETURNED,
) -> BuildingDistribution:
    """Compute a site-EUI `BuildingDistribution` across every building in `metadata`.

    Args:
        metadata: one component's full metadata sample (e.g. from `BuildStockProcessor.process_metadata()`).
        energy_column: annual energy column used as the EUI numerator; tolerates a "..<unit>" suffix.
        sqft_column: floor-area column name; auto-detected (`in.sqft` family) if not given.
        bldg_id_column: the building/dwelling-unit identifier column.
        bins: number of histogram bins (clamped to the sample size if smaller).
        kde_points: number of (x, y) points to sample the smoothed density curve at.
        max_points: cap on the number of individual points returned (see `MAX_POINTS_RETURNED`).

    Raises:
        ValueError: if `metadata` is empty, or has no usable site EUI (missing/non-positive energy/sqft).
    """
    if metadata.empty:
        raise ValueError("Cannot compute a building distribution from empty metadata.")

    resolved_sqft_column = sqft_column or _find_column(metadata.columns, "in.sqft")
    resolved_energy_column = _find_column(metadata.columns, energy_column)
    if resolved_sqft_column is None or resolved_energy_column is None:
        raise ValueError(f"Could not find both a floor-area column and {energy_column!r} in metadata to compute site EUI.")

    sqft = pd.to_numeric(metadata[resolved_sqft_column], errors="coerce")
    energy = pd.to_numeric(metadata[resolved_energy_column], errors="coerce")
    eui = ((energy * KWH_TO_KBTU) / sqft).replace([float("inf"), float("-inf")], pd.NA)

    working = metadata.assign(_dist_eui=eui, _dist_sqft=sqft, _dist_energy=energy).dropna(subset=["_dist_eui"])
    working = working[working["_dist_eui"] > 0]
    if working.empty:
        raise ValueError(f"No rows with a valid site EUI (non-null, positive {resolved_sqft_column}) found.")

    # `.replace([inf, -inf], pd.NA)` above can leave `_dist_eui` as an `object`-dtype column (pandas doesn't
    # keep a plain float64 dtype once `pd.NA` -- rather than `NaN` -- appears in it), which breaks numpy
    # ufuncs like `np.exp` in `_gaussian_kde` below -- force it back to float64 now that NAs are dropped.
    working["_dist_eui"] = working["_dist_eui"].astype(float)
    working = working.sort_values("_dist_eui").reset_index(drop=True)
    working["_dist_rank"] = working["_dist_eui"].rank(pct=True) * 100.0

    values = working["_dist_eui"].to_numpy(dtype=float)
    sample_size = len(working)
    mean_value = float(values.mean())

    bin_count = max(1, min(bins, sample_size))
    counts, bin_edges = np.histogram(values, bins=bin_count)
    density, _ = np.histogram(values, bins=bin_edges, density=True)

    kde_x, kde_y = _gaussian_kde(values, kde_points)

    def _row_to_point(row: pd.Series) -> DistributionPoint:
        return DistributionPoint(
            bldg_id=int(row[bldg_id_column]),
            value=float(row["_dist_eui"]),
            percentile_rank=float(row["_dist_rank"]),
            sqft=float(row["_dist_sqft"]) if pd.notna(row["_dist_sqft"]) else None,
            annual_site_energy_kwh=float(row["_dist_energy"]) if pd.notna(row["_dist_energy"]) else None,
        )

    if sample_size > max_points:
        # Thin evenly by rank (not randomly), so the returned points still trace out the full shape of the
        # distribution -- percentile/mean lookups below still use the full `working` frame regardless.
        step = sample_size / max_points
        indices = sorted({int(i * step) for i in range(max_points)})
        points_frame = working.iloc[indices]
    else:
        points_frame = working
    points = [_row_to_point(row) for _, row in points_frame.iterrows()]

    percentile_buildings: dict[str, DistributionPoint] = {}
    for name, target_percentile in PERCENTILE_TARGETS.items():
        target_value = float(np.percentile(values, target_percentile))
        percentile_buildings[name] = _row_to_point(_nearest_row(working, "_dist_eui", target_value))
    percentile_buildings["mean"] = _row_to_point(_nearest_row(working, "_dist_eui", mean_value))

    return BuildingDistribution(
        metric="site_eui",
        unit="kBtu/ft2/yr",
        sample_size=sample_size,
        mean_value=mean_value,
        points=points,
        histogram_bin_edges=bin_edges.tolist(),
        histogram_counts=counts.tolist(),
        histogram_density=density.tolist(),
        kde_x=kde_x,
        kde_y=kde_y,
        percentile_buildings=percentile_buildings,
    )


__all__ = [
    "DEFAULT_BINS",
    "DEFAULT_ENERGY_COLUMN",
    "DEFAULT_KDE_POINTS",
    "MAX_POINTS_RETURNED",
    "PERCENTILE_TARGETS",
    "BuildingDistribution",
    "DistributionPoint",
    "compute_building_distribution",
]
