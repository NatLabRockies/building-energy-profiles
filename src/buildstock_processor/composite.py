"""Composite ("mixed-use") building representation for BuildStock.

A `ComStockProcessor`/`ResStockProcessor` simulates buildings as one specific DOE prototype building model
(ComStock) or housing type (ResStock) at a time. Many real buildings aren't well represented by a single
building type -- for example, a building that is 70% office space over 30% ground-floor retail. A
`CompositeBuildingType` models such a building as a weighted combination of one or more BuildStock
`(product, building_type)` components, each contributing a `fraction` of the combined building's energy
profile. Fractions across all components must sum to 1.0 (see `CompositeBuildingType.normalized()` if your
shares don't sum perfectly due to rounding).

This module provides two levels of functionality:

- `combine_composite_time_series()` combines already-downloaded per-component time series DataFrames (e.g.
  from `BuildStockProcessor.process_building_time_series()`) into one synthetic composite time series,
  linearly blended by each component's `fraction`.
- `pull_composite_time_series()` is the end-to-end version: for each component, builds the right processor,
  finds (or uses a caller-supplied) representative building, downloads its time series, then combines
  everything with `combine_composite_time_series()`.

Combining is a simple linear blend of every shared numeric `out.*` column:

    composite[column][t] = sum(component.fraction * component_series[column][t] for component in composite)

ComStock and ResStock publish the same per-building time series layout (15-minute intervals, aligned to the
same AMY2018-based calendar for the currently supported releases) but use different unit-suffix conventions
on column names (e.g. ResStock's `out.electricity.total.energy_consumption..kwh` vs. ComStock's
`out.electricity.total.energy_consumption`). Both are normalized to the bare `out.*` name before combining,
so composites can freely mix ComStock and ResStock components (e.g. ground-floor retail over apartments).

`fraction` is unrelated to the `weight` metadata column (which scales a sampled building/unit up to the
number of real buildings/units it represents in the overall stock) -- it's simply how much of the composite
building's combined profile each component contributes, most commonly a floor-area share.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ._base import BuildStockProcessor
from .comstock import ComStockProcessor
from .resstock import ResStockProcessor

_WEIGHT_SUM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class CompositeComponent:
    """One weighted BuildStock building-type component of an `CompositeBuildingType`."""

    product: str
    """"comstock" or "resstock"."""
    building_type: str
    """A ComStockProcessor/ResStockProcessor building type (e.g. "MediumOffice", "Single-Family Detached")."""
    fraction: float
    """This component's share of the combined composite profile, in (0, 1]. All of an composite's component
    fractions must sum to 1.0."""

    def __post_init__(self) -> None:
        if not 0 < self.fraction <= 1:
            raise ValueError(f"CompositeComponent fraction must be in (0, 1], got {self.fraction}")
        normalized_product = self.product.strip().lower()
        if normalized_product not in {"comstock", "resstock"}:
            raise ValueError(f"CompositeComponent product must be 'comstock' or 'resstock', got {self.product!r}")

    @property
    def key(self) -> tuple[str, str]:
        """The `(product, building_type)` pair identifying this component, used to key component time series."""
        return (self.product.strip().lower(), self.building_type)


@dataclass(frozen=True)
class CompositeBuildingType:
    """A synthetic "building" represented as a fraction-weighted mix of two or more BuildStock building
    types (e.g. 70% MediumOffice + 30% RetailStripmall for a mixed-use building with ground-floor retail).
    """

    name: str
    components: tuple[CompositeComponent, ...]

    def __post_init__(self) -> None:
        if len(self.components) < 2:
            raise ValueError("A CompositeBuildingType needs at least 2 components")
        keys = [component.key for component in self.components]
        if len(set(keys)) != len(keys):
            raise ValueError(f"Composite components must have unique (product, building_type) pairs, got {keys}")
        # Note: fractions summing to 1.0 is intentionally *not* enforced here -- see `assert_normalized()`,
        # which `combine_composite_time_series()`/`pull_composite_time_series()` call before combining. That
        # keeps `normalized()` usable on a freshly constructed, not-yet-normalized composite.

    @property
    def total_fraction(self) -> float:
        """The sum of every component's fraction. Should be ~1.0 before combining -- see `normalized()`."""
        return sum(component.fraction for component in self.components)

    def assert_normalized(self) -> None:
        """Raise `ValueError` unless this composite's component fractions sum to ~1.0."""
        if not math.isclose(self.total_fraction, 1.0, abs_tol=_WEIGHT_SUM_TOLERANCE):
            raise ValueError(
                f"Composite '{self.name}' component fractions must sum to 1.0 (got {self.total_fraction}); "
                "rescale them or call `.normalized()` if they're percentages that don't sum perfectly due to rounding."
            )

    @classmethod
    def from_fractions(cls, name: str, fractions: Mapping[tuple[str, str], float]) -> CompositeBuildingType:
        """Convenience constructor from a `{(product, building_type): fraction}` mapping."""
        return cls(
            name=name,
            components=tuple(
                CompositeComponent(product=product, building_type=building_type, fraction=fraction)
                for (product, building_type), fraction in fractions.items()
            ),
        )

    def normalized(self) -> CompositeBuildingType:
        """Return a copy with fractions rescaled to sum to exactly 1.0.

        Useful when fractions were entered as percentages that don't sum perfectly due to rounding (e.g.
        33.3 / 33.3 / 33.3).
        """
        total = self.total_fraction
        return CompositeBuildingType(
            name=self.name,
            components=tuple(
                CompositeComponent(product=component.product, building_type=component.building_type, fraction=component.fraction / total)
                for component in self.components
            ),
        )

    def component_map(self) -> dict[tuple[str, str], CompositeComponent]:
        """Return this composite's components keyed by `(product, building_type)`."""
        return {component.key: component for component in self.components}


def normalize_time_series_columns(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Strip trailing "..<unit>" suffixes (e.g. "..kwh", "..kwh_per_ft2") from column names.

    ResStock time series columns carry a unit suffix that ComStock's don't (e.g.
    "out.electricity.total.energy_consumption..kwh" vs. "out.electricity.total.energy_consumption"); this
    normalizes both to the same bare `out.*` name so components from either product can be combined.
    """
    rename = {column: column.split("..", 1)[0] for column in data_frame.columns if ".." in column}
    return data_frame.rename(columns=rename)


def combine_composite_time_series(
    composite: CompositeBuildingType,
    component_time_series: Mapping[tuple[str, str], pd.DataFrame],
    value_columns: list[str] | None = None,
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    """Linearly combine each component's time series DataFrame into one synthetic composite time series.

    `component_time_series` must have one entry per `composite` component, keyed by
    `CompositeComponent.key` (i.e. `(product, building_type)`), each a DataFrame like the ones returned by
    reading a `BuildStockProcessor.process_building_time_series()` parquet file. Column names are
    normalized (see `normalize_time_series_columns()`) before combining, so ComStock and ResStock
    components can be mixed freely.

    `value_columns` defaults to every numeric column shared by all components (excluding `bldg_id`). If
    given explicitly, it's narrowed the same way: a requested column missing from *any* component is
    silently dropped rather than raising, since ComStock and ResStock don't publish identical end-use
    categories (e.g. ComStock has district cooling/heating outputs that ResStock's residential schema
    doesn't). Compare the requested list against the returned DataFrame's columns to see what was dropped.

    Combining requires overlapping timestamps -- rows are aligned on the intersection of every component's
    `timestamp_column` values (an inner join), so components must share the same interval/calendar (true
    for ComStock and ResStock's currently supported AMY2018-based releases).

    Returns a DataFrame with `timestamp_column` plus one combined column per resolved value column, where
    `composite[column][t] = sum(component.fraction * component_series[column][t] for component in composite)`.
    """
    composite.assert_normalized()

    required_keys = [component.key for component in composite.components]
    missing = [key for key in required_keys if key not in component_time_series]
    if missing:
        raise ValueError(f"Missing component time series for composite '{composite.name}': {missing}")

    normalized_frames: dict[tuple[str, str], pd.DataFrame] = {}
    for key, data_frame in component_time_series.items():
        if timestamp_column not in data_frame.columns:
            raise ValueError(f"Component time series for {key} has no '{timestamp_column}' column")
        normalized = normalize_time_series_columns(data_frame)
        normalized_frames[key] = normalized.set_index(timestamp_column)

    if value_columns is None:
        common_columns: set[str] | None = None
        for key in required_keys:
            frame = normalized_frames[key]
            numeric_columns = {column for column in frame.columns if column != "bldg_id" and pd.api.types.is_numeric_dtype(frame[column])}
            common_columns = numeric_columns if common_columns is None else common_columns & numeric_columns
        value_columns = sorted(common_columns or set())
    else:
        # Requested columns aren't guaranteed to exist in every component -- narrow to the ones present in
        # all of them instead of raising, mirroring the auto-detected (value_columns=None) behavior above.
        value_columns = [column for column in value_columns if all(column in normalized_frames[key].columns for key in required_keys)]

    if not value_columns:
        raise ValueError("No shared numeric columns found across composite components to combine.")

    shared_index = normalized_frames[required_keys[0]].index
    for key in required_keys[1:]:
        shared_index = shared_index.intersection(normalized_frames[key].index)
    shared_index = shared_index.sort_values()

    if len(shared_index) == 0:
        raise ValueError(f"Component time series for composite '{composite.name}' share no common timestamps to combine.")

    combined = pd.DataFrame(index=shared_index)
    for column in value_columns:
        total = pd.Series(0.0, index=shared_index)
        for component in composite.components:
            frame = normalized_frames[component.key]
            total = total + component.fraction * frame.loc[shared_index, column].astype(float)
        combined[column] = total

    combined.index.name = timestamp_column
    return combined.reset_index()


def pull_composite_time_series(
    composite: CompositeBuildingType,
    save_dir: Path,
    state: str,
    county_name: str | list[str] = "All",
    upgrade: str = "0",
    release_by_product: Mapping[str, str] | None = None,
    bldg_ids: Mapping[tuple[str, str], int] | None = None,
    min_sqft: float | None = None,
    max_sqft: float | None = None,
    value_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    """End-to-end: download one representative building's time series per composite component, then combine
    them into a single synthetic composite time series.

    For each component, this builds the matching processor (`ComStockProcessor` for "comstock",
    `ResStockProcessor` for "resstock") scoped to `state`/`county_name`/`upgrade`/`min_sqft`/`max_sqft` and
    that component's `building_type`, picks a representative building (`bldg_ids[component.key]` if given,
    otherwise the first building `process_metadata()` finds in scope), downloads its time series via
    `process_building_time_series()`, and normalizes/combines every component with
    `combine_composite_time_series()`.

    Args:
        composite: the `CompositeBuildingType` to pull and combine time series for.
        save_dir: base directory for downloaded metadata/time series (one subfolder per product).
        state: 2-letter state abbreviation shared by every component.
        county_name: county filter shared by every component (see `ComStockProcessor`/`ResStockProcessor`
            for format differences between products).
        upgrade: upgrade id shared by every component (e.g. "0" for baseline).
        release_by_product: optional `{"comstock": release_id, "resstock": release_id}` override; defaults
            to each processor's own default release.
        bldg_ids: optional `{(product, building_type): bldg_id}` override to pick specific buildings instead
            of the first one found per component.
        min_sqft, max_sqft: optional shared square-footage filters.
        value_columns: passed through to `combine_composite_time_series()`.

    Returns:
        A tuple of `(combined_composite_time_series, {component.key: component_time_series})` so callers can
        inspect both the blended result and each underlying component's own profile.
    """
    component_time_series: dict[tuple[str, str], pd.DataFrame] = {}
    for component in composite.components:
        processor_cls: type[BuildStockProcessor] = (
            ComStockProcessor if component.product.strip().lower() == "comstock" else ResStockProcessor
        )
        product_base_dir = save_dir / component.product.strip().lower()

        processor_kwargs: dict[str, object] = {
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
            processor_kwargs["release"] = release
        processor = processor_cls(**processor_kwargs)

        bldg_id = (bldg_ids or {}).get(component.key)
        if bldg_id is not None:
            sample = pd.DataFrame({"bldg_id": [bldg_id], "in.state": [state]})
        else:
            metadata = processor.process_metadata(save_dir=processor.base_dir)
            if metadata.empty:
                raise ValueError(f"No buildings found for composite component {component.key} in state={state!r}.")
            sample = metadata[["bldg_id", "in.state"]].head(1)

        ts_dir = processor.base_dir / "timeseries" / f"upgrade_{upgrade}"
        ts_dir.mkdir(parents=True, exist_ok=True)
        paths, _building_ids = processor.process_building_time_series(sample, save_dir=ts_dir)
        if not paths:
            raise ValueError(f"Failed to download time series for composite component {component.key}.")
        component_time_series[component.key] = pd.read_parquet(paths[0])

    combined = combine_composite_time_series(composite, component_time_series, value_columns=value_columns)
    return combined, component_time_series
