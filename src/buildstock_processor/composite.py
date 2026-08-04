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

`fraction` represents a *share* of an unspecified-size composite, so combining is a weighted average, not a
size-accurate blend -- if you know the actual target floor area of each component (e.g. "30,000 sqft
office + 70,000 sqft retail = 100,000 sqft total"), pass `target_sqft` to `pull_composite_time_series()` (or
precomputed `weights` to `combine_composite_time_series()` directly) instead: each component is scaled by
`target_sqft / representative_building_sqft` rather than by its bare `fraction`, so the combined result
represents an actual building of that square footage rather than a floor-area-agnostic share.

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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ._base import BuildStockProcessor
from .building_condition import DEFAULT_BAND as BUILDING_CONDITION_DEFAULT_BAND
from .building_condition import select_building_condition_sample
from .comstock import ComStockProcessor
from .resstock import ResStockProcessor

_WEIGHT_SUM_TOLERANCE = 1e-6

# Composite components are fully independent to download (different processors/files), so
# pull_composite_time_series() downloads them concurrently rather than one at a time -- bounded modestly
# since a composite is typically a handful of components, not dozens.
_COMPONENT_DOWNLOAD_WORKERS = 8


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


def find_nearest_sqft_bldg_id(
    metadata: pd.DataFrame, target_sqft: float, sqft_column: str | None = None, bldg_id_column: str = "bldg_id"
) -> int:
    """Return the `bldg_id` of the row in `metadata` whose floor area is closest to `target_sqft`.

    Used to pick a real, appropriately-sized representative building for a `target_sqft`-mode composite
    component, instead of an arbitrary "first found" building that's then linearly rescaled to the target
    size -- a building that's already close in size to begin with carries more realistic non-linear
    characteristics (HVAC equipment sizing, schedules, etc.) than one rescaled from a very different size.

    Args:
        metadata: a metadata sample (e.g. from `BuildStockProcessor.process_metadata()`) to search.
        target_sqft: the floor area to match against.
        sqft_column: floor-area column name; auto-detected (`in.sqft` family) if not given.
        bldg_id_column: the building/dwelling-unit identifier column.

    Raises:
        ValueError: if `metadata` is empty, or has no usable floor-area column.
    """
    if metadata.empty:
        raise ValueError("Cannot find a nearest-sqft building in empty metadata.")
    resolved_sqft_column = sqft_column or next((c for c in metadata.columns if c.startswith("in.sqft")), None)
    if resolved_sqft_column is None:
        raise ValueError("Could not find a floor-area column (in.sqft*) in metadata to match target_sqft against.")
    numeric_sqft = pd.to_numeric(metadata[resolved_sqft_column], errors="coerce")
    valid = numeric_sqft.dropna()
    if valid.empty:
        raise ValueError(f"No rows with a valid {resolved_sqft_column} value found.")
    nearest_index = (valid - target_sqft).abs().idxmin()
    return int(metadata.loc[nearest_index, bldg_id_column])


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
    weights: Mapping[tuple[str, str], float] | None = None,
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

    `weights`, if given, overrides `component.fraction` as the per-component blend multiplier -- one weight
    per composite component, keyed the same as `component_time_series`. Unlike fractions, weights aren't
    required to sum to 1.0 (`assert_normalized()` is skipped), which lets a caller scale each component to
    an absolute target square footage rather than a floor-area *share* of an unspecified total (see
    `pull_composite_time_series`'s `target_sqft` parameter, which computes exactly this).

    Returns a DataFrame with `timestamp_column` plus one combined column per resolved value column, where
    `composite[column][t] = sum(weight * component_series[column][t] for component in composite)` (`weight`
    being `weights[component.key]` if given, else `component.fraction`).
    """
    required_keys = [component.key for component in composite.components]
    if weights is not None:
        missing_weights = [key for key in required_keys if key not in weights]
        if missing_weights:
            raise ValueError(f"Missing weight for composite component(s): {missing_weights}")
    else:
        composite.assert_normalized()
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
            multiplier = weights[component.key] if weights is not None else component.fraction
            total = total + multiplier * frame.loc[shared_index, column].astype(float)
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
    timeseries_dir: Path | None = None,
    target_sqft: Mapping[tuple[str, str], float] | None = None,
    upgrade_by_component: Mapping[tuple[str, str], str] | None = None,
    building_condition: Mapping[tuple[str, str], float] | None = None,
    building_condition_band: float = BUILDING_CONDITION_DEFAULT_BAND,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.DataFrame]]:
    """End-to-end: download one representative building's time series per composite component, then combine
    them into a single synthetic composite time series.

    For each component, this builds the matching processor (`ComStockProcessor` for "comstock",
    `ResStockProcessor` for "resstock") scoped to `state`/`county_name`/`upgrade`/`min_sqft`/`max_sqft` and
    that component's `building_type`, picks a representative building (`bldg_ids[component.key]` if given;
    else `building_condition[component.key]`'s percentile-band median building if given; else the first
    building `process_metadata()` finds in scope), downloads its time series via
    `process_building_time_series()`, and normalizes/combines every component with
    `combine_composite_time_series()`. Components are fully independent of each other (different
    processors/files), so a composite with 2+ components downloads them concurrently (one thread per
    component, up to `_COMPONENT_DOWNLOAD_WORKERS`) instead of one at a time.

    Args:
        composite: the `CompositeBuildingType` to pull and combine time series for.
        save_dir: base directory for downloaded metadata (one subfolder per product).
        timeseries_dir: optional separate base directory for downloaded time series (one subfolder per
            product). When omitted, time series remain under each product's metadata directory for
            backwards compatibility.
        state: 2-letter state abbreviation shared by every component.
        county_name: county filter shared by every component (see `ComStockProcessor`/`ResStockProcessor`
            for format differences between products).
        upgrade: upgrade id used by every component that isn't overridden in `upgrade_by_component` (e.g.
            "0" for baseline).
        release_by_product: optional `{"comstock": release_id, "resstock": release_id}` override; defaults
            to each processor's own default release.
        bldg_ids: optional `{(product, building_type): bldg_id}` override to pick specific buildings instead
            of the first one found per component. Takes precedence over `building_condition` for the same
            component.
        min_sqft, max_sqft: optional shared square-footage filters.
        value_columns: passed through to `combine_composite_time_series()`.
        target_sqft: optional `{(product, building_type): square_feet}` override that scales each
            component's contribution to an *absolute* target floor area instead of a `fraction` share of an
            unspecified total. Unless `bldg_ids` already pins a specific building for that component, the
            representative building is chosen via `find_nearest_sqft_bldg_id()` -- the real sampled
            building whose own floor area is closest to the target -- rather than an arbitrary "first
            found" one; this looks up that building's own `in.sqft` and computes
            `weight = target_sqft[key] / representative_sqft`, passed through to
            `combine_composite_time_series()` as `weights` (so `composite`'s fractions don't need to sum to
            1.0 in this mode -- they're ignored in favor of `target_sqft`). When given together with
            `bldg_ids`, metadata is still fetched (filtered to that `bldg_id`) purely to read its floor area.
        upgrade_by_component: optional `{(product, building_type): upgrade_id}` per-component override --
            each component uses its own entry here instead of the shared `upgrade` if present. Useful for
            isolating a single measure's effect to just the component(s) it actually applies to (e.g. a
            commercial-only upgrade shouldn't also change a residential component's profile just because
            they happen to share a composite) while every other component stays at its own baseline.
        building_condition: optional `{(product, building_type): percentile}` -- for a component with no
            `bldg_ids` override, picks that percentile band's median-site-EUI building (see
            `building_condition.select_building_condition_sample()`) as the representative building instead
            of the first one `process_metadata()` finds. There's no per-building error range here (only one
            building's time series is downloaded); use `summarize_composite_metadata()`'s `building_condition`
            for that band's annual energy median/range instead.
        building_condition_band: `+/-` percentile points around each `building_condition` target to select
            from (default `building_condition.DEFAULT_BAND`).

    Returns:
        A tuple of `(combined_composite_time_series, {component.key: component_time_series})` so callers can
        inspect both the blended result and each underlying component's own profile.
    """

    def _pull_one(component: CompositeComponent) -> tuple[tuple[str, str], pd.DataFrame, float | None]:
        """Download one component's representative building time series -- the unit of work run
        concurrently (one thread per component) below, since each component uses its own processor/files
        and is otherwise fully independent of every other component."""
        processor_cls: type[BuildStockProcessor] = (
            ComStockProcessor if component.product.strip().lower() == "comstock" else ResStockProcessor
        )
        product_base_dir = save_dir / component.product.strip().lower()
        component_upgrade = (upgrade_by_component or {}).get(component.key, upgrade)

        processor_kwargs: dict[str, object] = {
            "state": state,
            "county_name": county_name,
            "building_type": component.building_type,
            "upgrade": component_upgrade,
            "base_dir": product_base_dir,
            "min_sqft": min_sqft,
            "max_sqft": max_sqft,
        }
        release = (release_by_product or {}).get(component.key[0])
        if release:
            processor_kwargs["release"] = release
        processor = processor_cls(**processor_kwargs)

        bldg_id = (bldg_ids or {}).get(component.key)
        percentile = None if bldg_id is not None else (building_condition or {}).get(component.key)
        sample_sqft: float | None = None
        if bldg_id is not None and target_sqft is None:
            sample = pd.DataFrame({"bldg_id": [bldg_id], "in.state": [state]})
        else:
            metadata = processor.process_metadata(save_dir=processor.base_dir)
            if metadata.empty:
                raise ValueError(f"No buildings found for composite component {component.key} in state={state!r}.")
            if bldg_id is not None:
                metadata = metadata[metadata["bldg_id"] == bldg_id]
                if metadata.empty:
                    raise ValueError(f"bldg_id {bldg_id} not found in metadata for composite component {component.key}.")
            elif percentile is not None:
                selection = select_building_condition_sample(metadata, percentile=percentile, band=building_condition_band)
                metadata = metadata[metadata["bldg_id"] == selection.median_bldg_id]
            elif target_sqft is not None and component.key in target_sqft:
                # Pick a real building already close in size to the target, rather than an arbitrary
                # "first found" one that then gets linearly rescaled -- see find_nearest_sqft_bldg_id().
                nearest_bldg_id = find_nearest_sqft_bldg_id(metadata, target_sqft[component.key])
                metadata = metadata[metadata["bldg_id"] == nearest_bldg_id]
            sqft_column = next((c for c in metadata.columns if c.startswith("in.sqft")), None) if target_sqft is not None else None
            select_columns = ["bldg_id", "in.state"] + ([sqft_column] if sqft_column else [])
            sample = metadata[select_columns].head(1)
            if sqft_column:
                sample_sqft = float(sample[sqft_column].iloc[0])

        scale: float | None = None
        if target_sqft is not None:
            if component.key not in target_sqft:
                raise ValueError(f"Missing target_sqft for composite component {component.key}")
            if not sample_sqft:
                raise ValueError(f"Could not determine floor area for composite component {component.key} to scale by target_sqft.")
            scale = target_sqft[component.key] / sample_sqft

        ts_root = timeseries_dir or processor.base_dir
        ts_dir = ts_root / component.product.strip().lower() / f"upgrade_{component_upgrade}"
        ts_dir.mkdir(parents=True, exist_ok=True)
        paths, _building_ids = processor.process_building_time_series(sample[["bldg_id", "in.state"]], save_dir=ts_dir)
        if not paths:
            raise ValueError(f"Failed to download time series for composite component {component.key}.")
        return component.key, pd.read_parquet(paths[0]), scale

    component_time_series: dict[tuple[str, str], pd.DataFrame] = {}
    component_scale: dict[tuple[str, str], float] = {}
    if len(composite.components) > 1:
        with ThreadPoolExecutor(max_workers=min(len(composite.components), _COMPONENT_DOWNLOAD_WORKERS)) as executor:
            results = list(executor.map(_pull_one, composite.components))
    else:
        results = [_pull_one(component) for component in composite.components]

    for key, time_series, scale in results:
        component_time_series[key] = time_series
        if scale is not None:
            component_scale[key] = scale

    weights = component_scale if target_sqft is not None else None
    combined = combine_composite_time_series(composite, component_time_series, value_columns=value_columns, weights=weights)
    return combined, component_time_series
