/** TypeScript mirrors of api/schemas.py -- keep in sync with the FastAPI backend. */

export type Product = 'comstock' | 'resstock';
export type MatchQuality = 'exact' | 'approximate' | 'unmapped';

export interface EnergyStarTypeInfo {
  energy_star_property_type: string;
  buildstock_product: Product | null;
  buildstock_building_type: string | null;
  match_quality: MatchQuality;
  notes: string;
}

export interface EnergyStarComponentIn {
  energy_star_property_type: string;
  /** Exactly one of `fraction`/`sqft` must be set -- see CompositeResolveRequest. */
  fraction?: number | null;
  sqft?: number | null;
}

export interface CompositeResolveRequest {
  components: EnergyStarComponentIn[];
  /** 2-letter state abbreviation. Optional, but required (alongside sqft mode) to auto-select a
   * representative bldg_id per component -- see `bldg_id` on ResolvedComponent/CompositeComponentSpec. */
  state?: string | null;
  county_name?: string | string[];
}

export interface ResolvedComponent {
  energy_star_property_type: string;
  product: Product | null;
  building_type: string | null;
  fraction: number;
  sqft?: number | null;
  /** The real sampled building (closest in floor area to `sqft`) auto-selected for this component, if
   * `state` was given in sqft mode -- reused as-is by every downstream page via
   * CompositeComponentSpec.bldg_id instead of each independently guessing a representative building. */
  bldg_id?: number | null;
  match_quality: MatchQuality;
  notes: string;
}

export interface CompositeComponentSpec {
  product: Product;
  building_type: string;
  fraction: number;
  sqft?: number | null;
  /** Pin a specific representative building for this component (e.g. one already selected by
   * resolve_composite()'s sqft-mode auto-selection) instead of letting the timeseries endpoint pick its
   * own default. */
  bldg_id?: number | null;
  label?: string | null;
  /** Optional `{"in.<column>": [allowed values]}` filters narrowing this component's sampled population
   * (OR within a column, AND across columns). Applied by the building-distribution, metadata-summary, and
   * single-component time-series endpoints. */
  filters?: Record<string, string[]> | null;
}

export interface CompositeResolveResponse {
  ok: boolean;
  components: ResolvedComponent[];
  resolvable: CompositeComponentSpec[];
  unmapped: string[];
  total_fraction: number;
  total_sqft?: number | null;
  warnings: string[];
}

export interface CompositeRequestBase {
  components: CompositeComponentSpec[];
  state: string;
  county_name?: string | string[];
  upgrade?: string;
  min_sqft?: number | null;
  max_sqft?: number | null;
}

export type MetadataSummaryRequest = CompositeRequestBase;

export interface ComponentSummary {
  product: Product;
  building_type: string;
  label: string | null;
  fraction: number;
  building_count: number;
  /** Population-average figures across all `building_count` sampled buildings -- distinct from the
   * `selected_*` fields below, which describe one specific pinned building. */
  avg_sqft: number;
  annual_site_energy_kwh: number;
  site_eui_kbtu_per_ft2: number;
  /** The specific building pinned for this component (e.g. via the Select Buildings page), if any. */
  selected_bldg_id?: number | null;
  selected_sqft?: number | null;
  selected_annual_site_energy_kwh?: number | null;
  selected_site_eui_kbtu_per_ft2?: number | null;
  /** How many of this component's representative buildings/dwelling units its floor-area share works out
   * to -- ~1 for a whole-building (ComStock) component sized to its own average, and the dwelling-unit
   * count for a ResStock component (e.g. 28.4 apartments). Set whenever the composite is sized by floor
   * area (any mix of ComStock and ResStock components, or an explicit sqft target); `null` in
   * bare-fraction mode, where there's no floor area to count units against. */
  unit_multiplier?: number | null;
}

export interface EndUseValue {
  key: string;
  annual_energy_kwh: number;
}

export interface MetadataSummaryResponse {
  ok: boolean;
  state: string;
  upgrade: string;
  components: ComponentSummary[];
  weighted_building_count: number;
  weighted_avg_sqft: number;
  weighted_annual_site_energy_kwh: number;
  /** The composite's fraction-weighted site EUI using each component's *population average* -- not tied
   * to any specific pinned building. */
  weighted_site_eui_kbtu_per_ft2: number;
  /** The composite's fraction-weighted site EUI using each component's specifically *pinned* building
   * instead of its population average -- `null` unless every component has a resolvable pinned building. */
  weighted_selected_building_annual_site_energy_kwh?: number | null;
  weighted_selected_building_site_eui_kbtu_per_ft2?: number | null;
  by_fuel: EndUseValue[];
  by_end_use: EndUseValue[];
  cache_dir: string;
  /** Data-quality warnings, e.g. a sqft-mode target square footage falling outside the observed range of
   * the sampled BuildStock buildings for a component. */
  warnings: string[];
}


export interface TimeseriesRequest extends CompositeRequestBase {
  columns?: string[] | null;
  resample?: 'native' | 'hourly';
  bldg_ids?: Record<string, number> | null;
}

export interface TimeseriesResponse {
  ok: boolean;
  state: string;
  upgrade: string;
  resample: string;
  columns: string[];
  row_count: number;
  series: Record<string, number | string | null>[];
  component_labels: Record<string, string>;
  warnings: string[];
}

export interface MeasureInfo {
  id: string;
  name: string;
  product: Product;
}

export interface MeasuresListResponse {
  ok: boolean;
  product: Product;
  release: string;
  measures: MeasureInfo[];
}

export interface AvailableStatesResponse {
  ok: boolean;
  product: Product;
  states: string[];
}

export interface AvailableCountiesResponse {
  ok: boolean;
  product: Product;
  state: string;
  counties: string[];
  /** Not every county in a state is guaranteed to be represented in the underlying BuildStock sample --
   * "All" is always a safe fallback alongside this list. */
  note: string;
}

export interface MeasuresCompareRequest extends CompositeRequestBase {
  baseline_upgrade: string;
  /** Each entry is `"<product>:<upgrade_id>"` (e.g. "comstock:5"), applying that upgrade only to
   * components of that product -- components of any other product stay at `baseline_upgrade` for that
   * comparison, so a commercial and a residential measure that happen to share a numeric id can't get
   * conflated in a mixed composite. */
  comparison_upgrades: string[];
  columns?: string[] | null;
  /** When true, also compute an IQR-based uncertainty range for every value (see `MeasureSavings`), from
   * the population of sampled buildings near each component's pinned building. Off by default. */
  include_uncertainty?: boolean;
  /** +/- percentile points (of site EUI) around each component's pinned building defining its "nearby
   * population" for `include_uncertainty`. Defaults to 10 (backend default) if omitted. */
  uncertainty_band?: number;
}

export interface MeasureSavings {
  upgrade_id: string;
  name: string | null;
  product?: Product | null;
  baseline_kwh: number;
  upgrade_kwh: number;
  absolute_savings_kwh: number;
  pct_savings: number | null;
  /** [low, high] uncertainty ranges -- only populated when the request set `include_uncertainty: true`.
   * See api/schemas.py's `MeasureSavings` docstring for how these are computed (an IQR-based
   * "population of buildings near the building selected" band, combined across composite components). */
  baseline_kwh_iqr?: [number, number] | null;
  upgrade_kwh_iqr?: [number, number] | null;
  absolute_savings_kwh_iqr?: [number, number] | null;
  pct_savings_iqr?: [number, number] | null;
}

export interface MeasuresCompareResponse {
  ok: boolean;
  baseline_upgrade: string;
  comparison_upgrades: string[];
  results: Record<string, MeasureSavings[]>;
  warnings: string[];
  baseline_by_end_use: EndUseValue[];
  by_end_use: Record<string, EndUseValue[]>;
}

export interface MosExportRequest extends CompositeRequestBase {
  heating_columns?: string[] | null;
  cooling_columns?: string[] | null;
}

export interface DistributionPoint {
  bldg_id: number;
  value: number;
  percentile_rank: number;
  sqft?: number | null;
  annual_site_energy_kwh?: number | null;
}

/** Quick-select shortcut keys on ComponentDistribution.percentile_buildings. */
export const PERCENTILE_KEYS = ['p5', 'p25', 'median', 'mean', 'p75', 'p95'] as const;
export type PercentileKey = (typeof PERCENTILE_KEYS)[number];

export const PERCENTILE_LABELS: Record<PercentileKey, string> = {
  p5: '5th percentile',
  p25: '25th percentile',
  median: 'Median',
  mean: 'Mean',
  p75: '75th percentile',
  p95: '95th percentile',
};

export interface ComponentDistribution {
  product: Product;
  building_type: string;
  label: string | null;
  metric: string;
  unit: string;
  sample_size: number;
  mean_value: number;
  /** Every (possibly downsampled) building in the sample, sorted ascending by `value`. */
  points: DistributionPoint[];
  histogram_bin_edges: number[];
  histogram_counts: number[];
  histogram_density: number[];
  /** Smoothed density curve (x, y) -- empty for a degenerate sample. */
  kde_x: number[];
  kde_y: number[];
  percentile_buildings: Record<PercentileKey, DistributionPoint>;
}

export interface BuildingDistributionRequest extends CompositeRequestBase {
  metric?: 'site_eui';
  bins?: number;
}

export interface BuildingDistributionResponse {
  ok: boolean;
  state: string;
  distributions: ComponentDistribution[];
  warnings: string[];
}

export interface FilterValueCount {
  value: string;
  count: number;
}

export interface FilterColumnOptions {
  /** Raw metadata column name (e.g. "in.vintage") -- pass this back as a key in
   * CompositeComponentSpec.filters to narrow the population by it. */
  column: string;
  display_name: string;
  values: FilterValueCount[];
}

export interface ComponentFilterOptions {
  product: Product;
  building_type: string;
  label: string | null;
  columns: FilterColumnOptions[];
}

export type FilterOptionsRequest = CompositeRequestBase;

export interface FilterOptionsResponse {
  ok: boolean;
  components: ComponentFilterOptions[];
  warnings: string[];
}

export interface ApiErrorResponse {
  ok: false;
  error_type: string;
  error: string;
}

/** Site energy (kWh) -> site EUI (kBtu/ft2) unit conversion, mirroring api/services.py's KWH_TO_KBTU --
 * kept in sync so a client-side weighted-EUI calculation (e.g. the Select Buildings page's composite
 * mixture panel) matches the backend's `weighted_site_eui_kbtu_per_ft2`/`weighted_selected_building_
 * site_eui_kbtu_per_ft2` exactly, not just approximately. */
export const KWH_TO_KBTU = 3.412141633;

/** Common annual "total" energy columns shared by ComStock and ResStock, mirroring
 * api/services.py's DEFAULT_METRIC_COLUMNS. Used as chart series defaults in the UI. */
export const DEFAULT_METRIC_COLUMNS = [
  'out.electricity.total.energy_consumption',
  'out.natural_gas.total.energy_consumption',
  'out.district_cooling.total.energy_consumption',
  'out.district_heating.total.energy_consumption',
  'out.fuel_oil.total.energy_consumption',
  'out.propane.total.energy_consumption',
  'out.site_energy.total.energy_consumption',
];
