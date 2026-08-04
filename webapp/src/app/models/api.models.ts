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
  /** Exactly one of `energy_star_property_type` or (`product` + `building_type`) must be set -- see
   * CompositeResolveRequest. */
  energy_star_property_type?: string | null;
  /** A ComStock/ResStock building type entered directly, skipping the ENERGY STAR crosswalk -- both
   * `product` and `building_type` must be set together. */
  product?: Product | null;
  building_type?: string | null;
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
  avg_sqft: number;
  annual_site_energy_kwh: number;
  site_eui_kbtu_per_ft2: number;
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
  weighted_site_eui_kbtu_per_ft2: number;
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
  /** {"product:building_type" -> bldg_id} identifying the exact real building/dwelling-unit whose time
   * series was downloaded and used for each component -- this endpoint only pulls a single representative
   * building per component, so this surfaces exactly which one was picked. */
  component_bldg_ids: Record<string, number>;
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

export interface BuildingTypesResponse {
  ok: boolean;
  product: Product;
  building_types: string[];
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
}

export interface MeasureSavings {
  upgrade_id: string;
  name: string | null;
  product?: Product | null;
  baseline_kwh: number;
  upgrade_kwh: number;
  absolute_savings_kwh: number;
  pct_savings: number | null;
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

export interface ApiErrorResponse {
  ok: false;
  error_type: string;
  error: string;
}

export interface EuiDistributionRequest extends CompositeRequestBase {
  curve_points?: number;
}

export interface EuiPercentileSelection {
  label: string;
  percentile: number | null;
  eui_kbtu_per_ft2: number;
  /** {"product:building_type" -> bldg_id} for the real building selected for each component at this
   * percentile target. */
  bldg_ids: Record<string, number>;
}

export interface EuiCurvePoint {
  eui_kbtu_per_ft2: number;
  /** Peak-normalized probability density (0-1) at this site EUI -- the curve's shape, not a percentile
   * rank. */
  density: number;
  /** This point's percentile rank (0-100) along the composite's distribution -- used to map an x-position
   * click back to a percentile. */
  percentile: number;
}

export interface EuiDistributionResponse {
  ok: boolean;
  state: string;
  curve: EuiCurvePoint[];
  mean_eui_kbtu_per_ft2: number;
  median_eui_kbtu_per_ft2: number;
  sample_size: number;
  percentiles: EuiPercentileSelection[];
  warnings: string[];
}

export interface EuiPercentileBuildingsRequest extends CompositeRequestBase {
  percentile: number;
  band?: number;
  max_candidates_per_component?: number;
}

export interface EuiCandidateBuilding {
  bldg_id: number;
  eui_kbtu_per_ft2: number;
  /** The sampled building/dwelling's own floor area, as-is in the underlying metadata (for a ResStock
   * component, this is ONE dwelling's sqft, not the component's requested total). */
  sqft: number;
  /** `sqft` scaled to the component's requested target square footage (null in fraction mode). */
  scaled_sqft?: number | null;
  /** How many of this sampled dwelling/building it takes to reach the component's target sqft (null in
   * fraction mode). E.g. ~68 for a multifamily component requesting 75,000 sqft against a ~1,100 sqft
   * sample unit. */
  unit_multiplier?: number | null;
  percentile_rank: number;
}

export interface EuiPercentileBuildingsComponent {
  product: Product;
  building_type: string;
  label?: string | null;
  selected_bldg_id: number;
  candidates: EuiCandidateBuilding[];
}

export interface EuiPercentileBuildingsResponse {
  ok: boolean;
  percentile: number;
  components: EuiPercentileBuildingsComponent[];
  warnings: string[];
}

export interface BuildingEnergyModelRequest extends CompositeRequestBase {
  /** Optional {"product:building_type" -> bldg_id} overrides for specific representative buildings --
   * mirrors TimeseriesRequest.bldg_ids. */
  bldg_ids?: Record<string, number> | null;
}

export interface ComponentBuildingModel {
  product: Product;
  building_type: string;
  label?: string | null;
  bldg_id: number;
  /** The building energy model's own filename, e.g. "comstock-bldg0000123-up00.osm.gz" -- included in a
   * multi-component ".zip" bundle under this name. */
  filename: string;
}

export interface BuildingEnergyModelResponse {
  ok: boolean;
  state: string;
  upgrade: string;
  components: ComponentBuildingModel[];
  warnings: string[];
}


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
