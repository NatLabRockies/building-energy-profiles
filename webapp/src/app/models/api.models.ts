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
}

export interface ResolvedComponent {
  energy_star_property_type: string;
  product: Product | null;
  building_type: string | null;
  fraction: number;
  sqft?: number | null;
  match_quality: MatchQuality;
  notes: string;
}

export interface CompositeComponentSpec {
  product: Product;
  building_type: string;
  fraction: number;
  sqft?: number | null;
  label?: string | null;
}

export interface CompositeResolveResponse {
  ok: boolean;
  components: ResolvedComponent[];
  resolvable: CompositeComponentSpec[];
  unmapped: string[];
  total_fraction: number;
  total_sqft?: number | null;
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
