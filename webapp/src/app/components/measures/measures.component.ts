import { Component, computed, OnInit, ViewChild, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AgGridAngular } from 'ag-grid-angular';
import { ColDef, themeMaterial, ValueFormatterParams } from 'ag-grid-community';
import type { Config, Data, Layout } from 'plotly.js-dist-min';
import { forkJoin } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { ScenarioHistoryService } from '../../services/scenario-history.service';
import { EndUseValue, MeasureInfo, MeasureSavings, MeasuresCompareResponse, Product, TimeseriesResponse } from '../../models/api.models';
import { Scenario } from '../../models/scenario.model';
import { CHART_COLORS } from '../../models/chart-colors';
import { PlotComponent } from '../plot/plot.component';

const DEFAULT_SAVINGS_COLUMN = 'out.site_energy.total.energy_consumption';
const MAX_SELECTABLE_MEASURES = 5;

/** A measure with a globally-unique selection key ("<product>:<id>") so residential and commercial
 * measures that happen to share a bare numeric id can be told apart once merged into one list. */
interface MeasureOption extends MeasureInfo {
  selectionKey: string;
}

const PRODUCT_LABELS: Record<Product, string> = {
  comstock: 'Commercial',
  resstock: 'Residential',
};

@Component({
  selector: 'app-measures',
  standalone: true,
  imports: [CommonModule, FormsModule, PlotComponent, AgGridAngular],
  templateUrl: './measures.component.html',
  styleUrl: './measures.component.scss',
})
export class MeasuresComponent implements OnInit {
  readonly productLabels = PRODUCT_LABELS;

  loading = signal(false);
  comparing = signal(false);
  loadingDetail = signal(false);
  errorMessage = signal<string | null>(null);
  measures = signal<MeasureOption[]>([]);
  selectedKeys = signal<Set<string>>(new Set());
  compareResult = signal<MeasuresCompareResponse | null>(null);
  searchTerm = signal('');
  /** 'all' or a specific product -- lets the user narrow the (potentially long) list down to just the
   * commercial or residential measures relevant to their composite. */
  productFilter = signal<'all' | Product>('all');
  /** The exact selection keys that were part of the last successful compare() call -- used to drive the
   * detail section (LDC + end-use split) below the savings table for *every* compared measure, not just
   * the first. Kept separate from selectedKeys() so toggling checkboxes after comparing doesn't change
   * what's shown until the user re-compares. */
  comparedKeys = signal<string[]>([]);

  savingsChartData?: Data[];
  /** 'kwh' (default): bars show absolute site energy savings. 'pct': bars show savings as a percentage of
   * baseline instead -- useful for comparing measures of very different scale (e.g. a small vs. a huge
   * composite) on the same relative footing. */
  savingsUnit = signal<'kwh' | 'pct'>('kwh');
  loadDurationChartData?: Data[];
  @ViewChild('ldcChart') ldcChart?: PlotComponent;
  endUseChartData?: Data[];
  readonly plotConfig: Partial<Config> = { responsive: true, displaylogo: false };
  get barLayout(): Partial<Layout> {
    const isPct = this.savingsUnit() === 'pct';
    return {
      autosize: true,
      showlegend: false,
      margin: { l: 60, r: 20, t: 20, b: 80 },
      xaxis: {},
      yaxis: {
        title: { text: isPct ? 'Savings vs. baseline (%)' : 'Savings vs. baseline (kWh)' },
        ticksuffix: isPct ? '%' : undefined,
      },
    };
  }
  readonly lineLayout: Partial<Layout> = {
    autosize: true,
    margin: { l: 60, r: 20, t: 20, b: 50 },
    xaxis: { title: { text: 'Hours, sorted descending' } },
    yaxis: { title: { text: 'kW' } },
    legend: { orientation: 'h' },
  };
  readonly stackedBarLayout: Partial<Layout> = {
    autosize: true,
    barmode: 'stack',
    margin: { l: 60, r: 20, t: 20, b: 80 },
    xaxis: {},
    yaxis: {
      title: { text: 'Annual energy (kWh)' },
    },
  };

  readonly maxSelectable = MAX_SELECTABLE_MEASURES;

  // AG Grid setup for the savings comparison table. `themeMaterial` keeps the grid's look
  // consistent with the rest of the app now that Angular Material is the base component library.
  readonly gridTheme = themeMaterial;
  readonly defaultColDef: ColDef = { sortable: true, resizable: true, filter: true };
  readonly savingsColDefs: ColDef<MeasureSavings>[] = [
    {
      headerName: 'Measure',
      field: 'name',
      flex: 2,
      minWidth: 220,
      valueGetter: (p) => p.data?.name ?? p.data?.upgrade_id ?? '',
    },
    {
      headerName: 'Type',
      field: 'product',
      width: 130,
      valueFormatter: (p: ValueFormatterParams<MeasureSavings, Product | null | undefined>) =>
        p.value ? PRODUCT_LABELS[p.value] : '',
      cellClass: (p) => (p.value ? ['product-badge', p.value] : []),
    },
    {
      headerName: 'Baseline (kWh)',
      field: 'baseline_kwh',
      type: 'numericColumn',
      valueFormatter: (p) => this.formatKwh(p.value),
    },
    {
      headerName: 'Upgrade (kWh)',
      field: 'upgrade_kwh',
      type: 'numericColumn',
      valueFormatter: (p) => this.formatKwh(p.value),
    },
    {
      headerName: 'Savings (kWh)',
      field: 'absolute_savings_kwh',
      type: 'numericColumn',
      valueFormatter: (p) => this.formatKwh(p.value),
      cellClassRules: { error: (p) => (p.value ?? 0) < 0 },
    },
    {
      headerName: 'Savings (%)',
      field: 'pct_savings',
      type: 'numericColumn',
      valueFormatter: (p) => (p.value == null ? '' : `${p.value.toFixed(1)}%`),
      cellClassRules: { error: (p) => (p.value ?? 0) < 0 },
    },
  ];

  /** Row data for the savings grid -- recomputed whenever a new compare() result comes in. */
  readonly savingsRowData = computed<MeasureSavings[]>(() => this.compareResult()?.results[DEFAULT_SAVINGS_COLUMN] ?? []);

  private formatKwh(value: number | null | undefined): string {
    return value == null ? '' : Math.round(value).toLocaleString('en-US');
  }

  constructor(
    private readonly api: ApiService,
    readonly compositeState: CompositeStateService,
    private readonly scenarioHistory: ScenarioHistoryService,
    private readonly router: Router,
    private readonly route: ActivatedRoute,
  ) {}

  /** Every distinct BuildStock product represented in the composite -- a mixed (commercial + residential)
   * composite pulls measures from both catalogs; a single-product composite pulls from just the one. */
  get distinctProducts(): Product[] {
    return Array.from(new Set(this.compositeState.components().map((c) => c.product)));
  }

  ngOnInit(): void {
    // Subscribed (not just `.snapshot`) because clicking a *different* "recent scenario" nav link while
    // already on this page navigates to the same route with just a new `?scenario=<id>` query param --
    // Angular reuses this component instance rather than re-running ngOnInit, so a one-time `.snapshot`
    // read would silently miss every subsequent scenario click after the first. Subscribing to
    // `queryParamMap` re-runs this load logic for every navigation, same-route or not.
    this.route.queryParamMap.subscribe((params) => {
      this.loadForScenario(params.get('scenario'));
    });
  }

  /** (Re)initialize the page for `scenarioId` (or "no scenario", i.e. a composite freshly created via the
   * builder) -- restores the scenario's composite/baseline/selected measures and re-runs compare() when a
   * scenario id is given, otherwise just loads the measure catalog for whatever composite is already in
   * CompositeStateService. Safe to call repeatedly (e.g. once per distinct scenario nav click). */
  private loadForScenario(scenarioId: string | null): void {
    // A "?scenario=<id>" query param (set by the left nav's recent-scenarios links) recalls a previously
    // saved measures comparison -- restore its composite/baseline before the hasComposite() guard below,
    // so recalling a scenario works even after the composite state was otherwise cleared.
    const scenario = scenarioId ? this.scenarioHistory.findById(scenarioId) : undefined;
    if (scenario) {
      this.compositeState.setComposite(scenario.components, scenario.state, scenario.countyName, scenario.baselineUpgrade);
    }

    if (!this.compositeState.hasComposite()) {
      this.router.navigate(['/']);
      return;
    }

    // Reset whatever was shown for a previously-recalled/compared scenario before loading the new one, so
    // stale results/selections from the prior scenario don't linger on screen while the new one loads.
    this.compareResult.set(null);
    this.comparedKeys.set([]);
    this.savingsChartData = undefined;
    this.loadDurationChartData = undefined;
    this.endUseChartData = undefined;
    this.errorMessage.set(null);
    this.selectedKeys.set(scenario ? new Set(scenario.comparisonKeys) : new Set());

    this.loading.set(true);
    const products = this.distinctProducts;
    forkJoin(products.map((product) => this.api.getMeasures(product))).subscribe({
      next: (results) => {
        const merged = results.flatMap((result) =>
          result.measures.map((m): MeasureOption => ({ ...m, selectionKey: `${m.product}:${m.id}` })),
        );
        this.measures.set(merged);
        this.loading.set(false);
        if (scenario) {
          this.recallScenario(scenario);
        }
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.error ?? 'Failed to load the measure catalog.');
        this.loading.set(false);
      },
    });
  }

  /** Restore a recalled scenario's results directly from what was already downloaded/computed the first
   * time it was run (this session), instead of re-issuing the same compare()/getCompositeTimeseries()
   * requests -- both avoids an unnecessary re-download and (since compare() only saves a scenario on an
   * actual new comparison) avoids re-saving an identical scenario and duplicating this same nav entry every
   * time it's clicked. Falls back to a real compare() (e.g. after a page reload, when the in-memory result
   * cache is empty, or for measure selections not yet cached) -- that compare() call intentionally does
   * NOT re-save a new scenario, since we're just repopulating an existing one (see compare()'s `scenarioId`
   * param). */
  private recallScenario(scenario: Scenario): void {
    const cached = this.scenarioHistory.getCachedResult(scenario.id);
    if (!cached) {
      this.compare(scenario.id);
      return;
    }
    const { compareResult, baselineTimeseries, measureTimeseries } = cached;
    const selectionKeys = scenario.comparisonKeys;

    this.compareResult.set(compareResult);
    this.buildChart(compareResult);
    this.comparedKeys.set(selectionKeys);
    this.buildEndUseChart(compareResult, selectionKeys);
    this.buildLoadDurationChart(baselineTimeseries, measureTimeseries, selectionKeys);
  }


  get baselineUpgrade(): string {
    return this.compositeState.upgrade();
  }

  /** Non-baseline measures, narrowed by the product filter and search term -- what's actually rendered as
   * selectable checkboxes. */
  get comparableMeasures(): MeasureOption[] {
    const term = this.searchTerm().trim().toLowerCase();
    const filter = this.productFilter();
    return this.measures().filter((m) => {
      if (m.id === this.baselineUpgrade) {
        return false;
      }
      if (filter !== 'all' && m.product !== filter) {
        return false;
      }
      return !term || m.name.toLowerCase().includes(term);
    });
  }

  isSelected(key: string): boolean {
    return this.selectedKeys().has(key);
  }

  toggle(key: string): void {
    const current = new Set(this.selectedKeys());
    if (current.has(key)) {
      current.delete(key);
    } else if (current.size < MAX_SELECTABLE_MEASURES) {
      current.add(key);
    }
    this.selectedKeys.set(current);
  }

  clearSelection(): void {
    this.selectedKeys.set(new Set());
  }

  measureName(key: string): string {
    const result = this.compareResult();
    if (!result) {
      return key;
    }
    const savings = result.results[DEFAULT_SAVINGS_COLUMN]?.find((s) => `${s.product}:${s.upgrade_id}` === key);
    return savings?.name ?? key;
  }

  /** Comma-separated display names of comparedKeys(), for the detail section's summary line. */
  comparedMeasureNames(): string {
    return this.comparedKeys()
      .map((key) => this.measureName(key))
      .join(', ');
  }

  /** Run a fresh comparison for the currently-selected measures. `existingScenarioId`, set only when
   * recalling a scenario whose in-memory result cache was empty (e.g. after a page reload), tells
   * `loadDetailTimeseries()`/`saveScenario()` to cache these results onto that *existing* scenario instead
   * of creating a brand new nav entry for what the user perceives as just "reopening" an old one. */
  compare(existingScenarioId?: string): void {
    const selectionKeys = Array.from(this.selectedKeys());
    if (selectionKeys.length === 0) {
      return;
    }
    this.comparing.set(true);
    this.errorMessage.set(null);
    this.loadDurationChartData = undefined;
    this.endUseChartData = undefined;
    this.api
      .compareMeasures({
        components: this.compositeState.components(),
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        baseline_upgrade: this.baselineUpgrade,
        comparison_upgrades: selectionKeys,
      })
      .subscribe({
        next: (result) => {
          this.compareResult.set(result);
          this.buildChart(result);
          this.comparing.set(false);
          // Detail (LDC + end-use split) is shown for every compared measure, so downloading full
          // timeseries is capped to MAX_SELECTABLE_MEASURES + baseline (see loadDetailTimeseries).
          this.comparedKeys.set(selectionKeys);
          this.buildEndUseChart(result, selectionKeys);
          this.loadDetailTimeseries(selectionKeys, result, existingScenarioId);
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to compare measures.');
          this.comparing.set(false);
        },
      });
  }

  /** Compact "<BuildingType> + <BuildingType> ..." summary of the current composite's building types, for
   * a scenario's nav label -- e.g. "SmallOffice + MediumOffice" or "SmallOffice + 2 more" once there are
   * more than a couple of components. */
  private componentsSummary(): string {
    const labels = this.compositeState.components().map((c) => c.label || c.building_type);
    if (labels.length <= 2) {
      return labels.join(' + ');
    }
    return `${labels[0]} + ${labels.length - 1} more`;
  }

  /** Record this comparison in the recent-scenarios history (left nav) so it can be recalled later --
   * called once a compare() + its detail time series both complete successfully, for a genuinely *new*
   * comparison only (see `loadDetailTimeseries()`'s `existingScenarioId` handling, which re-caches an
   * existing scenario's results instead of calling this for a recall). The full result is cached (in
   * memory only, see `ScenarioHistoryService`) so recalling this scenario later (see `recallScenario()`)
   * can restore it directly instead of re-downloading. */
  private saveScenario(
    selectionKeys: string[],
    compareResult: MeasuresCompareResponse,
    baselineTimeseries: TimeseriesResponse,
    measureTimeseries: Record<string, TimeseriesResponse>,
  ): void {
    const countyName = this.compositeState.countyName();
    const location = countyName && countyName !== 'All' ? `${this.compositeState.state()}, ${countyName}` : this.compositeState.state();
    const scenario: Omit<Scenario, 'id' | 'createdAt'> = {
      label: `${this.componentsSummary()} — ${location}`,
      measuresSummary: selectionKeys.map((key) => this.measureName(key)).join(', '),
      state: this.compositeState.state(),
      countyName,
      baselineUpgrade: this.baselineUpgrade,
      components: this.compositeState.components(),
      comparisonKeys: selectionKeys,
    };
    const id = this.scenarioHistory.add(scenario);
    this.scenarioHistory.cacheResult(id, { compareResult, baselineTimeseries, measureTimeseries });
  }

  private loadDetailTimeseries(
    selectionKeys: string[],
    compareResult: MeasuresCompareResponse,
    existingScenarioId?: string,
  ): void {
    this.loadingDetail.set(true);
    const components = this.compositeState.components();
    const state = this.compositeState.state();
    const countyName = this.compositeState.countyName();

    const requests: Record<string, ReturnType<ApiService['getCompositeTimeseries']>> = {
      baseline: this.api.getCompositeTimeseries({
        components,
        state,
        county_name: countyName,
        upgrade: this.baselineUpgrade,
        resample: 'hourly',
        columns: [DEFAULT_SAVINGS_COLUMN],
      }),
    };
    for (const key of selectionKeys) {
      requests[key] = this.api.getCompositeTimeseries({
        components,
        state,
        county_name: countyName,
        upgrade: key,
        resample: 'hourly',
        columns: [DEFAULT_SAVINGS_COLUMN],
      });
    }

    forkJoin(requests).subscribe({
      next: (responses) => {
        const { baseline, ...measureResponses } = responses;
        const typedMeasureResponses = measureResponses as Record<string, TimeseriesResponse>;
        this.buildLoadDurationChart(baseline, typedMeasureResponses, selectionKeys);
        this.loadingDetail.set(false);
        // Only save/cache once the full detail (needed to recall this scenario later without
        // re-downloading) has actually finished loading. `existingScenarioId` means this was a recall
        // whose in-memory cache had already been lost (e.g. after a page reload) -- re-cache onto that
        // *same* scenario rather than creating a brand new nav entry for what's really just a reload.
        if (existingScenarioId) {
          this.scenarioHistory.cacheResult(existingScenarioId, {
            compareResult,
            baselineTimeseries: baseline,
            measureTimeseries: typedMeasureResponses,
          });
        } else {
          this.saveScenario(selectionKeys, compareResult, baseline, typedMeasureResponses);
        }
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.error ?? 'Failed to load the measure time series detail.');
        this.loadingDetail.set(false);
      },
    });
  }

  private sortedDescending(response: TimeseriesResponse, column: string): number[] {
    return response.series
      .map((row) => row[column] as number | null)
      .filter((v): v is number => v !== null)
      .sort((a, b) => b - a);
  }

  private buildLoadDurationChart(
    baseline: TimeseriesResponse,
    measureResponses: Record<string, TimeseriesResponse>,
    selectionKeys: string[],
  ): void {
    const baselineSorted = this.sortedDescending(baseline, DEFAULT_SAVINGS_COLUMN);
    const datasets: Data[] = [
      {
        type: 'scatter',
        mode: 'lines',
        name: 'Baseline',
        x: baselineSorted.map((_, i) => i),
        y: baselineSorted,
        line: { color: '#94a3b8' },
        fill: 'tozeroy',
        fillcolor: 'rgba(148, 163, 184, 0.15)',
      },
    ];
    // One line per compared measure (not just the first) so every selected measure's load profile is
    // represented alongside the baseline.
    selectionKeys.forEach((key, i) => {
      const response = measureResponses[key];
      if (!response) {
        return;
      }
      datasets.push({
        type: 'scatter',
        mode: 'lines',
        name: this.measureName(key),
        x: baselineSorted.map((_, idx) => idx),
        y: this.sortedDescending(response, DEFAULT_SAVINGS_COLUMN),
        line: { color: CHART_COLORS[i % CHART_COLORS.length] },
      });
    });
    this.loadDurationChartData = datasets;
  }

  private buildEndUseChart(result: MeasuresCompareResponse, selectionKeys: string[]): void {
    const perSelectionEndUse = selectionKeys.map((key) => result.by_end_use[key] ?? []);
    const endUseKeys = Array.from(
      new Set([...result.baseline_by_end_use.map((v) => v.key), ...perSelectionEndUse.flat().map((v) => v.key)]),
    );
    const valueFor = (list: EndUseValue[], key: string) => list.find((v) => v.key === key)?.annual_energy_kwh ?? 0;

    const labels = ['Baseline', ...selectionKeys.map((key) => this.measureName(key))];
    this.endUseChartData = endUseKeys.map((key, i) => ({
      type: 'bar',
      name: key,
      x: labels,
      y: [valueFor(result.baseline_by_end_use, key), ...perSelectionEndUse.map((list) => valueFor(list, key))],
      marker: { color: CHART_COLORS[i % CHART_COLORS.length] },
    }));
  }

  /** Switch the savings chart between absolute (kWh) and percent-of-baseline savings, rebuilding it from
   * the last compare() result so no re-fetch is needed (both units are already in `pct_savings`/
   * `absolute_savings_kwh` on each `MeasureSavings` row). */
  setSavingsUnit(unit: 'kwh' | 'pct'): void {
    if (this.savingsUnit() === unit) {
      return;
    }
    this.savingsUnit.set(unit);
    const result = this.compareResult();
    if (result) {
      this.buildChart(result);
    }
  }

  private buildChart(result: MeasuresCompareResponse): void {
    const savings = result.results[DEFAULT_SAVINGS_COLUMN];
    if (!savings) {
      this.savingsChartData = undefined;
      return;
    }
    const isPct = this.savingsUnit() === 'pct';
    const values = savings.map((s) => (isPct ? (s.pct_savings ?? 0) : s.absolute_savings_kwh));
    this.savingsChartData = [
      {
        type: 'bar',
        name: isPct ? 'Site energy savings (%)' : 'Site energy savings (kWh)',
        x: savings.map((s) => s.name ?? s.upgrade_id),
        y: values.map((v) => (isPct ? Math.round(v * 10) / 10 : Math.round(v))),
        marker: { color: values.map((v) => (v >= 0 ? '#16a34a' : '#dc2626')) },
      },
    ];
  }
}
