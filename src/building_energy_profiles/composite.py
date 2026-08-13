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

Mixing ResStock with ComStock needs one extra correction, because the two products' rows aren't the same
kind of thing: a ComStock row is a whole building, while a ResStock row is a *single dwelling unit* (see
`resstock.py`). Blending "50% MediumOffice + 50% Multi-Family with 5+ Units" by bare fractions therefore
puts half of a ~50,000 sqft office next to half of a ~900 sqft apartment, and the multifamily side comes out
far too small. `resolve_fraction_weights()` fixes this by turning each component's floor-area share into a
*count* of its representative building/unit: the composite's implied gross floor area is anchored on its
whole-building (ComStock) components (or given explicitly via `total_sqft`), each component's floor area is
`fraction * total_sqft`, and its weight is that area divided by its own representative floor area -- which,
for a ResStock component, is exactly the dwelling-unit multiplier ("50% of 50,000 sqft / 900 sqft per unit
= ~28 apartments"). `pull_composite_time_series()` and `summarize_composite_metadata()` apply this
automatically to any composite that mixes products.

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
from .building_condition import DEFAULT_BAND as BUILDING_CONDITION_DEFAULT_BAND
from .building_condition import select_building_condition_sample
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


def is_dwelling_unit_product(product: str) -> bool:
    """True for products whose metadata rows are individual dwelling units rather than whole buildings.

    ResStock simulates one housing unit per row (an apartment within a multifamily building, or a whole
    single-family home), so its floor area is a *per-unit* area that has to be multiplied up to a building
    -- see `resolve_fraction_weights()`.
    """
    return product.strip().lower() == "resstock"


def average_sqft(metadata: pd.DataFrame, sqft_column: str | None = None) -> float | None:
    """Return the mean floor area of `metadata`'s buildings/dwelling units, or `None` if unavailable."""
    resolved_column = sqft_column or next((c for c in metadata.columns if c.startswith("in.sqft")), None)
    if resolved_column is None or metadata.empty:
        return None
    mean_sqft = pd.to_numeric(metadata[resolved_column], errors="coerce").mean()
    return None if pd.isna(mean_sqft) else float(mean_sqft)


def resolve_fraction_weights(
    composite: CompositeBuildingType,
    component_sqft: Mapping[tuple[str, str], float],
    total_sqft: float | None = None,
) -> dict[tuple[str, str], float] | None:
    """Convert a composite's floor-area `fraction`s into per-component multipliers of each component's own
    representative building/dwelling unit -- the correction that makes a ResStock component's contribution
    a realistic *unit count* instead of a fraction of one apartment (see module docstring).

    `component_sqft` is each component's representative floor area (`{(product, building_type): sqft}`) --
    the whole-building area for a ComStock component, the per-dwelling-unit area for a ResStock one.

    The composite's gross floor area is `total_sqft` if given, else inferred from the whole-building
    (ComStock) components alone: `sum(fraction * sqft) / sum(fraction)` over those components, i.e. "the
    office is 50% of the building, and the office we're modeling is 50,000 sqft, so the whole building is
    100,000 sqft". Each component's weight is then `fraction * total_sqft / component_sqft[key]`.

    Returns `None` when no correction applies and bare `fraction`s should be used as-is: `total_sqft`
    wasn't given and the composite either has no dwelling-unit component (every component is already the
    same kind of whole building) or has no whole-building component to anchor a total floor area on (e.g. an
    all-ResStock composite, where the per-unit blend is already self-consistent).
    """
    composite.assert_normalized()
    return resolve_fraction_weights_for(
        {component.key: component.fraction for component in composite.components}, component_sqft, total_sqft
    )


def resolve_fraction_weights_for(
    fractions: Mapping[tuple[str, str], float],
    component_sqft: Mapping[tuple[str, str], float],
    total_sqft: float | None = None,
) -> dict[tuple[str, str], float] | None:
    """`resolve_fraction_weights()` over a bare `{(product, building_type): fraction}` mapping, for callers
    (e.g. the API layer) that don't build a `CompositeBuildingType`. Fractions are assumed normalized.
    """
    if total_sqft is None:
        if not any(is_dwelling_unit_product(product) for product, _building_type in fractions):
            return None
        anchors = {key: fraction for key, fraction in fractions.items() if not is_dwelling_unit_product(key[0]) and component_sqft.get(key)}
        anchor_fraction = sum(anchors.values())
        if not anchor_fraction:
            return None
        total_sqft = sum(fraction * component_sqft[key] for key, fraction in anchors.items()) / anchor_fraction

    if total_sqft <= 0:
        raise ValueError(f"Composite total_sqft must be > 0, got {total_sqft}")

    weights: dict[tuple[str, str], float] = {}
    for key, fraction in fractions.items():
        sqft = component_sqft.get(key)
        if not sqft:
            raise ValueError(f"Could not determine floor area for composite component {key} to size it against total_sqft.")
        weights[key] = fraction * total_sqft / sqft
    return weights


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
    being `weights[component.key]` if given, else `component.fraction`). The multiplier actually applied to
    each component is recorded in the result's `.attrs["component_weights"]`.
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
    applied_weights = {
        component.key: (weights[component.key] if weights is not None else component.fraction) for component in composite.components
    }
    for column in value_columns:
        total = pd.Series(0.0, index=shared_index)
        for component in composite.components:
            frame = normalized_frames[component.key]
            total = total + applied_weights[component.key] * frame.loc[shared_index, column].astype(float)
        combined[column] = total

    combined.index.name = timestamp_column
    combined = combined.reset_index()
    combined.attrs["component_weights"] = applied_weights
    return combined


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
    target_sqft: Mapping[tuple[str, str], float] | None = None,
    total_sqft: float | None = None,
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
    `combine_composite_time_series()`.

    Args:
        composite: the `CompositeBuildingType` to pull and combine time series for.
        save_dir: base directory for downloaded metadata/time series (one subfolder per product).
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
        total_sqft: optional gross floor area of the whole composite building, in `fraction` mode (i.e.
            without `target_sqft`). Each component is then sized to `fraction * total_sqft` and weighted by
            that area divided by its own representative floor area -- so a ResStock component becomes a
            realistic dwelling-unit count instead of a fraction of one apartment. A composite that mixes
            ComStock and ResStock components gets this treatment automatically even without `total_sqft`,
            anchoring the total on its ComStock components' representative sizes (see
            `resolve_fraction_weights()`); in that case each component with no `bldg_ids`/
            `building_condition` override is represented by the sampled building closest to its type's
            average floor area, so the inferred total isn't at the mercy of whichever building came back
            first.
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
        inspect both the blended result and each underlying component's own profile. The multiplier applied
        to each component (e.g. a ResStock component's dwelling-unit count) is recorded in the combined
        frame's `.attrs["component_weights"]`.
    """
    component_time_series: dict[tuple[str, str], pd.DataFrame] = {}
    component_scale: dict[tuple[str, str], float] = {}
    component_sqft: dict[tuple[str, str], float] = {}
    # A mixed-product composite needs each component's floor area even in fraction mode, to turn a
    # dwelling-unit component's floor-area share into a unit count -- see resolve_fraction_weights().
    mixes_products = len({component.key[0] for component in composite.components}) > 1
    needs_sqft = target_sqft is not None or total_sqft is not None or mixes_products
    for component in composite.components:
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
        if bldg_id is not None and not needs_sqft:
            sample = pd.DataFrame({"bldg_id": [bldg_id], "in.state": [state]})
        else:
            metadata = processor.process_metadata(save_dir=processor.base_dir)
            if metadata.empty:
                raise ValueError(f"No buildings found for composite component {component.key} in state={state!r}.")
            sqft_column = next((c for c in metadata.columns if c.startswith("in.sqft")), None) if needs_sqft else None
            if bldg_id is not None:
                metadata = metadata[metadata["bldg_id"] == bldg_id]
                if metadata.empty:
                    raise ValueError(f"bldg_id {bldg_id} not found in metadata for composite component {component.key}.")
            elif percentile is not None:
                selection = select_building_condition_sample(metadata, percentile=percentile, band=building_condition_band)
                metadata = metadata[metadata["bldg_id"] == selection.median_bldg_id]
            elif needs_sqft:
                # Match a real building close to the size being modeled, rather than an arbitrary "first
                # found" one that then gets linearly rescaled -- see find_nearest_sqft_bldg_id(). The
                # yardstick is `target_sqft` for a whole-building component sized to an absolute area, and
                # otherwise the sample's own average size: a dwelling-unit component is always sized in
                # units (its target is a whole component's floor area, not one apartment's), and in
                # fraction mode the composite's implied floor area is *derived* from its components, so
                # anchoring it on a typical building beats anchoring it on whichever one came back first.
                match_sqft = (
                    target_sqft[component.key]
                    if target_sqft is not None and component.key in target_sqft and not is_dwelling_unit_product(component.product)
                    else average_sqft(metadata, sqft_column)
                )
                if match_sqft:
                    nearest_bldg_id = find_nearest_sqft_bldg_id(metadata, match_sqft, sqft_column=sqft_column)
                    metadata = metadata[metadata["bldg_id"] == nearest_bldg_id]
            select_columns = ["bldg_id", "in.state"] + ([sqft_column] if sqft_column else [])
            sample = metadata[select_columns].head(1)
            if sqft_column:
                sample_sqft = float(sample[sqft_column].iloc[0])
                component_sqft[component.key] = sample_sqft

        if target_sqft is not None:
            if component.key not in target_sqft:
                raise ValueError(f"Missing target_sqft for composite component {component.key}")
            if not sample_sqft:
                raise ValueError(f"Could not determine floor area for composite component {component.key} to scale by target_sqft.")
            component_scale[component.key] = target_sqft[component.key] / sample_sqft

        ts_dir = processor.base_dir / "timeseries" / f"upgrade_{component_upgrade}"
        ts_dir.mkdir(parents=True, exist_ok=True)
        paths, _building_ids = processor.process_building_time_series(sample[["bldg_id", "in.state"]], save_dir=ts_dir)
        if not paths:
            raise ValueError(f"Failed to download time series for composite component {component.key}.")
        component_time_series[component.key] = pd.read_parquet(paths[0])

    if target_sqft is not None:
        weights: dict[tuple[str, str], float] | None = component_scale
    else:
        weights = resolve_fraction_weights(composite, component_sqft, total_sqft) if needs_sqft else None
    combined = combine_composite_time_series(composite, component_time_series, value_columns=value_columns, weights=weights)
    return combined, component_time_series
