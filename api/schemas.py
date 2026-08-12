"""Pydantic request/response models for the composite building explorer API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Product = Literal["comstock", "resstock"]


class EnergyStarTypeInfo(BaseModel):
    """One packaged ENERGY STAR Portfolio Manager -> BuildStock crosswalk entry."""

    energy_star_property_type: str
    buildstock_product: Product | None
    buildstock_building_type: str | None
    match_quality: Literal["exact", "approximate", "unmapped"]
    notes: str


class EnergyStarComponentIn(BaseModel):
    """One ENERGY STAR property type + floor-area share, as entered by a user.

    Exactly one of `fraction` (a 0-1 floor-area share) or `sqft` (an absolute square footage) must be set.
    All components within one `CompositeResolveRequest` must use the same mode -- see that model's
    validator. `sqft` mode scales the *reported results* (Dashboard/Time Series/Measures/`.mos` export) to
    an actual building of that square footage, rather than just a relative share of an unspecified total.
    """

    energy_star_property_type: str
    fraction: float | None = Field(default=None, gt=0, le=1)
    sqft: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_exactly_one_of_fraction_or_sqft(self) -> EnergyStarComponentIn:
        if (self.fraction is None) == (self.sqft is None):
            raise ValueError(
                f"Component {self.energy_star_property_type!r} must set exactly one of 'fraction' or 'sqft', not both/neither."
            )
        return self


class CompositeResolveRequest(BaseModel):
    components: list[EnergyStarComponentIn] = Field(min_length=1)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    """2-letter state abbreviation. Optional, but required (alongside sqft mode) to auto-select a
    representative bldg_id per component -- see `bldg_id` on `ResolvedComponent`/`CompositeComponentSpec`.
    Without it, resolution stays a fast, offline crosswalk lookup with no bldg_id selected."""
    county_name: str | list[str] = "All"

    @model_validator(mode="after")
    def _check_consistent_mode(self) -> CompositeResolveRequest:
        modes = {"sqft" if c.sqft is not None else "fraction" for c in self.components}
        if len(modes) > 1:
            raise ValueError("All components must use the same mode -- either all 'fraction' (%) or all 'sqft', not a mix of both.")
        return self


class ResolvedComponent(BaseModel):
    energy_star_property_type: str
    product: Product | None
    building_type: str | None
    fraction: float
    sqft: float | None = None
    """The absolute square footage originally entered for this component, if the request used sqft mode."""
    bldg_id: int | None = None
    """The real sampled building (closest in floor area to `sqft`) auto-selected for this component, if
    `CompositeResolveRequest.state` was given in sqft mode -- see
    `building_energy_profiles.composite.find_nearest_sqft_bldg_id()`. Reused as-is by every downstream page
    (Dashboard/Timeseries/Measures) via `CompositeComponentSpec.bldg_id` instead of each independently
    guessing a representative building."""
    match_quality: Literal["exact", "approximate", "unmapped"]
    notes: str


class CompositeComponentSpec(BaseModel):
    """A resolved composite component, as sent to the metadata/timeseries/measures endpoints."""

    product: Product
    building_type: str
    fraction: float = Field(gt=0, le=1)
    sqft: float | None = Field(default=None, gt=0)
    """Absolute target square footage for this component. When every component in a request sets this,
    results are scaled to represent an actual building of that square footage (see
    `building_energy_profiles.composite.pull_composite_time_series`'s `target_sqft` parameter) instead of just
    a floor-area share of an unspecified total."""
    bldg_id: int | None = None
    """Pin a specific representative building for this component (e.g. one already selected by
    `resolve_composite()`'s sqft-mode auto-selection) instead of letting the timeseries endpoint pick its
    own (by default, the real building closest in size to `sqft`, or otherwise the first one found)."""
    label: str | None = None
    """Optional original ENERGY STAR property type name, for display purposes only."""
    filters: dict[str, list[str]] | None = None
    """Optional `{"in.<column>": [allowed values]}` filters narrowing this component's sampled population
    (e.g. `{"in.vintage": ["2000 to 2012", "2013 to 2018"]}` keeps only buildings in either vintage band --
    OR within a column, AND across columns). Applied by the building-distribution, metadata-summary, and
    single-component time-series endpoints; not yet applied to the multi-component composite time-series
    pipeline or measures comparison, which delegate to building_energy_profiles's lower-level composite/
    metadata functions. See `api/services.py`'s `CURATED_FILTER_COLUMNS` for the columns exposed via
    `GET/POST .../composite/filter-options`; an unrecognized column for this component's product is
    silently ignored rather than raising."""


class CompositeResolveResponse(BaseModel):
    ok: bool
    components: list[ResolvedComponent]
    """Every entered component, including unmapped ones, with match_quality/notes for display."""
    resolvable: list[CompositeComponentSpec]
    """Just the components that resolved to a real BuildStock building type, with fractions renormalized
    to sum to 1.0 across this subset -- ready to pass directly as `components` to the metadata/timeseries/
    measures endpoints."""
    unmapped: list[str]
    total_fraction: float
    """Sum of every entered component's fraction, before dropping unmapped ones."""
    total_sqft: float | None = None
    """Sum of every entered component's sqft, if the request used sqft mode."""
    warnings: list[str] = Field(default_factory=list)
    """Data-quality warnings, e.g. a bldg_id auto-selection failing for one component (that component just
    keeps `bldg_id=None`, falling back to each downstream endpoint's own default selection, rather than
    failing the whole resolve)."""


class CompositeRequestBase(BaseModel):
    components: list[CompositeComponentSpec] = Field(min_length=1)
    state: str = Field(min_length=2, max_length=2)
    county_name: str | list[str] = "All"
    upgrade: str = "0"
    min_sqft: float | None = None
    max_sqft: float | None = None


class MetadataSummaryRequest(CompositeRequestBase):
    pass


class ComponentSummary(BaseModel):
    product: Product
    building_type: str
    label: str | None
    fraction: float
    building_count: int
    """Number of sampled buildings this component's `avg_sqft`/`annual_site_energy_kwh`/`site_eui_kbtu_per_ft2`
    are averaged across -- i.e. the size of "the sample" those population-average fields describe."""
    avg_sqft: float
    annual_site_energy_kwh: float
    site_eui_kbtu_per_ft2: float
    """The *population average* across all `building_count` sampled buildings -- distinct from
    `selected_site_eui_kbtu_per_ft2`, which is one specific real building's own value."""
    selected_bldg_id: int | None = None
    """The specific building pinned for this component (e.g. via the Select Buildings page), if any."""
    selected_sqft: float | None = None
    selected_annual_site_energy_kwh: float | None = None
    selected_site_eui_kbtu_per_ft2: float | None = None
    """`selected_bldg_id`'s own EUI -- one real building's actual value, not a population average. `None`
    if no building is pinned for this component, or the pinned `bldg_id` wasn't found in the current
    sample (e.g. filters changed since it was selected)."""


class EndUseValue(BaseModel):
    key: str
    """Fuel name (for by-fuel breakdown) or end-use name (for by-end-use breakdown)."""
    annual_energy_kwh: float


class MetadataSummaryResponse(BaseModel):
    ok: bool
    state: str
    upgrade: str
    components: list[ComponentSummary]
    weighted_building_count: int
    weighted_avg_sqft: float
    weighted_annual_site_energy_kwh: float
    weighted_site_eui_kbtu_per_ft2: float
    """The composite's fraction-weighted site EUI using each component's *population average* -- the
    statistically representative figure for "a typical building of this mix", not tied to any specific
    pinned building."""
    weighted_selected_building_annual_site_energy_kwh: float | None = None
    weighted_selected_building_site_eui_kbtu_per_ft2: float | None = None
    """The composite's fraction-weighted site EUI using each component's specifically *pinned* building
    (`ComponentSummary.selected_bldg_id`) instead of its population average -- `None` unless every
    component in the composite has a resolvable pinned building, since a partial mix of "some pinned, some
    not" wouldn't be a meaningful weighted total."""
    by_fuel: list[EndUseValue]
    by_end_use: list[EndUseValue]
    cache_dir: str
    warnings: list[str] = Field(default_factory=list)
    """Data-quality warnings, e.g. an entered target square footage (sqft mode) falling outside the
    observed in.sqft range of the sampled BuildStock buildings for a component -- results are still
    computed, but are extrapolated beyond the underlying data."""


class TimeseriesRequest(CompositeRequestBase):
    """`upgrade` may be a bare id (applied uniformly to every component) or a `"<product>:<upgrade_id>"`
    prefix (e.g. "comstock:5") that isolates the upgrade to components of that product only -- every other
    component is pulled at baseline ("0") instead, so a single measure's effect can be inspected in the
    combined time series without contaminating an unrelated product's component in a mixed composite."""

    columns: list[str] | None = None
    resample: Literal["native", "hourly"] = "hourly"
    bldg_ids: dict[str, int] | None = None
    """Optional {"product:building_type": bldg_id} overrides for specific representative buildings."""


class TimeseriesResponse(BaseModel):
    ok: bool
    state: str
    upgrade: str
    resample: str
    columns: list[str]
    row_count: int
    series: list[dict[str, Any]]
    component_labels: dict[str, str]
    """{"product:building_type" -> display label} for every requested component."""
    warnings: list[str] = Field(default_factory=list)
    """Data-quality warnings, e.g. an entered target square footage (sqft mode) falling outside the
    observed in.sqft range of the sampled BuildStock buildings for a component."""


class MeasureInfo(BaseModel):
    id: str
    name: str
    product: Product
    """Which BuildStock product's upgrade catalog this measure comes from -- "comstock" measures apply to
    commercial composite components, "resstock" measures apply to residential ones."""


class MeasuresListResponse(BaseModel):
    ok: bool
    product: Product
    release: str
    measures: list[MeasureInfo]


class AvailableStatesResponse(BaseModel):
    ok: bool
    product: Product
    states: list[str]
    """Every 2-letter state abbreviation with published metadata for this product's release."""


class AvailableCountiesResponse(BaseModel):
    ok: bool
    product: Product
    state: str
    counties: list[str]
    """Every distinct county name actually published for `state` in this product's metadata (e.g. "Kent
    County"). Not every county in a state necessarily has its own published sample -- BuildStock's sampling
    is probabilistic, not exhaustive per-county -- so this list may be incomplete or, for a state with very
    little data, even empty."""
    note: str = (
        "Not all counties in this state may be represented in the underlying BuildStock sample. "
        '"All" is always a safe fallback that includes the whole state regardless of which counties are '
        "individually represented."
    )


class MeasuresCompareRequest(CompositeRequestBase):
    baseline_upgrade: str = "0"
    comparison_upgrades: list[str] = Field(min_length=1)
    """Each entry is either a bare upgrade id (e.g. "5"), applied to every composite component regardless
    of product (legacy behavior -- only meaningful when every component shares the same upgrade catalog),
    or a `"<product>:<upgrade_id>"`-prefixed entry (e.g. "comstock:5") that applies only to components of
    that product, leaving components of any other product at `baseline_upgrade` for this comparison. The
    webapp always sends prefixed entries so mixed commercial/residential composites can't accidentally
    conflate two unrelated measures that happen to share a numeric id."""
    columns: list[str] | None = None


class MeasureSavings(BaseModel):
    upgrade_id: str
    name: str | None
    product: Product | None = None
    """Which product's catalog this comparison's upgrade came from, if the selection was product-prefixed."""
    baseline_kwh: float
    upgrade_kwh: float
    absolute_savings_kwh: float
    """baseline_kwh - upgrade_kwh: positive means the measure saves energy, negative means it increases it."""
    pct_savings: float | None


class MeasuresCompareResponse(BaseModel):
    ok: bool
    baseline_upgrade: str
    comparison_upgrades: list[str]
    results: dict[str, list[MeasureSavings]]
    """column -> list of per-upgrade savings."""
    warnings: list[str] = Field(default_factory=list)
    """Data-quality warnings, e.g. an entered target square footage (sqft mode) falling outside the
    observed in.sqft range of the sampled BuildStock buildings for a component."""
    baseline_by_end_use: list[EndUseValue] = Field(default_factory=list)
    """Annual energy by end-use category for the baseline, for a stacked bar chart."""
    by_end_use: dict[str, list[EndUseValue]] = Field(default_factory=dict)
    """selection -> annual energy by end-use category, isolated the same way as `results` (a
    product-prefixed selection only reflects that product's component's change) -- pairs with
    `baseline_by_end_use` for a baseline-vs-measure stacked bar chart of end uses."""


class MosExportRequest(CompositeRequestBase):
    """See `TimeseriesRequest` -- `upgrade` supports the same product-prefixed isolation."""

    heating_columns: list[str] | None = None
    cooling_columns: list[str] | None = None


class FilterValueCount(BaseModel):
    value: str
    count: int
    """Number of sampled buildings in the current (unfiltered-by-this-column) population with this value."""


class FilterColumnOptions(BaseModel):
    column: str
    """Raw metadata column name (e.g. `"in.vintage"`) -- pass this back as a key in
    `CompositeComponentSpec.filters` to narrow the population by it."""
    display_name: str
    values: list[FilterValueCount]
    """Every distinct value for this column in the current sample, sorted by descending count."""


class ComponentFilterOptions(BaseModel):
    product: Product
    building_type: str
    label: str | None
    columns: list[FilterColumnOptions]
    """Only curated columns (see `api/services.py`'s `CURATED_FILTER_COLUMNS`) that are actually present in
    this component's sample and have more than one distinct value (a constant column isn't a useful
    filter)."""


class FilterOptionsRequest(CompositeRequestBase):
    """Request curated, filterable metadata columns for every composite component, to build a "narrow the
    population" filter UI -- see `building_energy_profiles` result variables for the full raw column set this
    intentionally curates down from."""


class FilterOptionsResponse(BaseModel):
    ok: bool
    components: list[ComponentFilterOptions]
    """One entry per component whose metadata could be downloaded -- a component that fails is skipped (see
    `warnings`) rather than failing the whole request."""
    warnings: list[str] = Field(default_factory=list)


class BuildingDistributionRequest(CompositeRequestBase):
    """Request a site-EUI distribution ("PDF") for every composite component, to pick a representative
    building from -- see `building_energy_profiles.building_distribution.compute_building_distribution`."""

    metric: Literal["site_eui"] = "site_eui"
    bins: int = Field(default=30, ge=1, le=200)


class DistributionPointOut(BaseModel):
    """One real building's position along a `ComponentDistribution` -- mirrors
    `building_energy_profiles.building_distribution.DistributionPoint`."""

    bldg_id: int
    value: float
    percentile_rank: float
    sqft: float | None = None
    annual_site_energy_kwh: float | None = None


class ComponentDistribution(BaseModel):
    product: Product
    building_type: str
    label: str | None
    metric: str
    unit: str
    sample_size: int
    mean_value: float
    points: list[DistributionPointOut]
    """Every (possibly downsampled) building in the sample, sorted ascending by `value` -- for a "rug plot"
    and for the frontend to map a clicked chart position to the nearest real building."""
    histogram_bin_edges: list[float]
    histogram_counts: list[int]
    histogram_density: list[float]
    kde_x: list[float]
    kde_y: list[float]
    """A smoothed density curve (x, y) -- the continuous "PDF" look for the chart. Empty for a degenerate
    (fewer than 2 distinct values) sample."""
    percentile_buildings: dict[str, DistributionPointOut]
    """Quick-select markers keyed `"p5"`, `"p25"`, `"median"`, `"p75"`, `"p95"`, `"mean"`."""


class BuildingDistributionResponse(BaseModel):
    ok: bool
    state: str
    distributions: list[ComponentDistribution]
    """One entry per component that could be computed -- a component whose metadata couldn't be downloaded
    is skipped (with a warning) rather than failing the whole request."""
    warnings: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    ok: bool = False
    error_type: str
    error: str
