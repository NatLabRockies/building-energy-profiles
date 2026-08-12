import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ChartConfiguration } from 'chart.js';
// Type-only import -- brings in chartjs-plugin-annotation's TypeScript module augmentation (so
// `plugins.annotation` below type-checks) without emitting a runtime import; the plugin itself is
// registered app-wide in chartjs-setup.ts.
import type { AnnotationOptions } from 'chartjs-plugin-annotation';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import {
  ComponentDistribution,
  ComponentFilterOptions,
  DistributionPoint,
  FilterColumnOptions,
  KWH_TO_KBTU,
  PERCENTILE_KEYS,
  PERCENTILE_LABELS,
  PercentileKey,
} from '../../models/api.models';
import { ChartComponent } from '../chart/chart.component';

interface Selection {
  bldgId: number;
  value: number;
  sqft: number | null;
  annualSiteEnergyKwh: number | null;
}

interface DistributionViewModel {
  key: string;
  dist: ComponentDistribution;
  selection: Selection | undefined;
  chartData: ChartConfiguration<'line'>['data'];
  chartOptions: ChartConfiguration<'line'>['options'];
  /** Curated filterable columns for this component (see FilterColumnOptions), for the "narrow the
   * population" controls -- empty if filter options haven't loaded (or none are available). */
  filterColumns: FilterColumnOptions[];
  /** Column -> currently selected (but not necessarily yet applied) allowed values in the <select>. */
  draftFilters: Record<string, string[]>;
  /** Number of columns with an actively APPLIED filter (reflected in this component's current
   * distribution) -- shown as a badge so it's clear the population has been narrowed. */
  appliedFilterCount: number;
  /** True while re-fetching this component's distribution after Apply/Clear filters. */
  refreshing: boolean;
}

interface Curve {
  x: number[];
  y: number[];
}

interface CompositeViewModel {
  chartData: ChartConfiguration<'line'>['data'];
  chartOptions: ChartConfiguration<'line'>['options'];
  /** Fraction-weighted site EUI using each component's population average -- matches the Dashboard's
   * `weighted_site_eui_kbtu_per_ft2` exactly (fetched from the same endpoint). */
  weightedSampleAverageEui: number | null;
  /** Fraction-weighted site EUI using each component's currently *selected* building -- computed
   * client-side with the same formula the backend uses, from the selected buildings' own sqft/energy, so
   * it updates live as the user clicks around without a network round-trip. `null` until every component
   * has a selection. */
  weightedSelectedEui: number | null;
}

/** Step inserted between the composite builder and the dashboard/time-series/measures pages: for every
 * building type in the resolved mix, shows the real sampled buildings' site-EUI distribution ("PDF" curve
 * + a "rug" of individual buildings) so a user can pin a specific representative building either by
 * clicking a point on the curve or via a percentile/mean shortcut, instead of always defaulting to the
 * first building found (or, in sqft mode, just the closest floor-area match). The pinned `bldg_id` is only
 * consumed by time-series-based results (Time Series page, Modelica export) -- the Dashboard's annual
 * metadata summary always reflects the full sample's average regardless of this choice (see the Dashboard's
 * separate "sample average" vs "selected buildings" cards). A "Composite Mix" panel combines every
 * component's individual distribution into one floor-area-weighted mixture curve, with reference lines for
 * both the sample-average and selected-building weighted EUI -- so it's clear how one specific building's
 * value (e.g. a high percentile pick) relates to the population-average figure the Dashboard reports. */
@Component({
  selector: 'app-select-buildings',
  standalone: true,
  imports: [CommonModule, ChartComponent],
  templateUrl: './select-buildings.component.html',
  styleUrl: './select-buildings.component.scss',
})
export class SelectBuildingsComponent implements OnInit {
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  warnings = signal<string[]>([]);
  distributions = signal<ComponentDistribution[]>([]);
  /** `"<product>:<building_type>"` -> the currently selected building for that component. */
  selections = signal<Record<string, Selection>>({});
  /** The composite's fraction-weighted sample-average site EUI (`MetadataSummaryResponse.
   * weighted_site_eui_kbtu_per_ft2`), fetched once alongside the distributions -- doesn't depend on any
   * selection, so it's not recomputed as the user clicks around. `null` while loading or if unavailable. */
  sampleAverageWeightedEui = signal<number | null>(null);
  /** `"<product>:<building_type>"` -> curated filterable columns for that component (see
   * ComponentFilterOptions), used to build the "narrow the population" controls. */
  filterOptionsByKey = signal<Record<string, ComponentFilterOptions>>({});
  /** `"<product>:<building_type>"` -> column -> currently selected (but not necessarily yet applied)
   * <select> values -- committed into `appliedFilters` (and refetched) only on "Apply filters". */
  draftFilters = signal<Record<string, Record<string, string[]>>>({});
  /** `"<product>:<building_type>"` -> column -> APPLIED allowed values -- what's actually reflected in
   * this component's current distribution/selection and the composite/sample-average calculations. */
  appliedFilters = signal<Record<string, Record<string, string[]>>>({});
  /** `"<product>:<building_type>"` -> true while re-fetching that component's distribution after
   * Apply/Clear filters. */
  refreshingByKey = signal<Record<string, boolean>>({});

  readonly percentileKeys = PERCENTILE_KEYS;
  readonly percentileLabels = PERCENTILE_LABELS;

  readonly viewModels = computed<DistributionViewModel[]>(() => {
    const selections = this.selections();
    const filterOptions = this.filterOptionsByKey();
    const draft = this.draftFilters();
    const applied = this.appliedFilters();
    const refreshing = this.refreshingByKey();
    return this.distributions().map((dist) => {
      const key = this.componentKey(dist.product, dist.building_type);
      const selection = selections[key];
      return {
        key,
        dist,
        selection,
        chartData: this.buildChartData(dist),
        chartOptions: this.buildChartOptions(dist, selection),
        filterColumns: filterOptions[key]?.columns ?? [],
        draftFilters: draft[key] ?? {},
        appliedFilterCount: Object.keys(applied[key] ?? {}).length,
        refreshing: !!refreshing[key],
      };
    });
  });

  /** Combines every component's distribution into one floor-area-weighted mixture curve -- `null` when
   * there are fewer than 2 components (nothing to combine) or any component lacks a usable curve. */
  readonly compositeViewModel = computed<CompositeViewModel | null>(() => this.buildCompositeViewModel());

  constructor(
    private readonly api: ApiService,
    readonly compositeState: CompositeStateService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    if (!this.compositeState.hasComposite()) {
      this.router.navigate(['/']);
      return;
    }
    this.load();
  }

  private componentKey(product: string, buildingType: string): string {
    return `${product}:${buildingType}`;
  }

  load(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.api
      .getBuildingDistributions({
        components: this.compositeState.components(),
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        upgrade: this.compositeState.upgrade(),
      })
      .subscribe({
        next: (result) => {
          this.distributions.set(result.distributions);
          this.warnings.set(result.warnings);
          this.initializeSelections(result.distributions);
          this.loading.set(false);
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to load building distributions.');
          this.loading.set(false);
        },
      });

    this.refreshSampleAverage();

    // Fetched purely to build the "narrow the population" filter controls -- non-critical, so a failure
    // here doesn't block the page (those components just show no filter controls).
    this.api
      .getFilterOptions({
        components: this.compositeState.components(),
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        upgrade: this.compositeState.upgrade(),
      })
      .subscribe({
        next: (result) => {
          const byKey: Record<string, ComponentFilterOptions> = {};
          for (const options of result.components) {
            byKey[this.componentKey(options.product, options.building_type)] = options;
          }
          this.filterOptionsByKey.set(byKey);
        },
        error: () => this.filterOptionsByKey.set({}),
      });
  }

  /** Re-fetch the composite panel's "sample average" reference line using every component's currently
   * APPLIED filters -- so it stays in sync with the (possibly narrowed) population, matching what the
   * Dashboard would report for the same filters. */
  private refreshSampleAverage(): void {
    const applied = this.appliedFilters();
    const components = this.compositeState.components().map((component) => {
      const key = this.componentKey(component.product, component.building_type);
      const filters = applied[key];
      return filters && Object.keys(filters).length > 0 ? { ...component, filters } : component;
    });
    this.api
      .getMetadataSummary({
        components,
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        upgrade: this.compositeState.upgrade(),
      })
      .subscribe({
        next: (result) => this.sampleAverageWeightedEui.set(result.weighted_site_eui_kbtu_per_ft2),
        error: () => this.sampleAverageWeightedEui.set(null),
      });
  }

  /** Default each component's selection to its already-pinned `bldg_id` (e.g. from sqft-mode auto-
   * selection) if that building shows up in its distribution's points, else the sample's median building --
   * a sensible "typical building" default that the user can then override. Keeps any selection already
   * made if this runs again (e.g. re-navigating back to this page). */
  private initializeSelections(distributions: ComponentDistribution[]): void {
    const existingComponents = this.compositeState.components();
    const next: Record<string, Selection> = { ...this.selections() };
    for (const dist of distributions) {
      const key = this.componentKey(dist.product, dist.building_type);
      if (next[key]) {
        continue;
      }
      const existingBldgId = existingComponents.find(
        (c) => c.product === dist.product && c.building_type === dist.building_type,
      )?.bldg_id;
      const matched = existingBldgId != null ? dist.points.find((p) => p.bldg_id === existingBldgId) : undefined;
      const fallback = matched ?? dist.percentile_buildings['median'];
      if (fallback) {
        next[key] = this.toSelection(fallback);
      }
    }
    this.selections.set(next);
  }

  private toSelection(point: DistributionPoint): Selection {
    return {
      bldgId: point.bldg_id,
      value: point.value,
      sqft: point.sqft ?? null,
      annualSiteEnergyKwh: point.annual_site_energy_kwh ?? null,
    };
  }

  private setSelection(dist: ComponentDistribution, point: DistributionPoint): void {
    const key = this.componentKey(dist.product, dist.building_type);
    this.selections.update((current) => ({ ...current, [key]: this.toSelection(point) }));
  }

  /** Update the in-progress (not yet applied) <select multiple> choice for one component/column -- only
   * takes effect (and re-fetches that component's distribution) once "Apply filters" is clicked. */
  onFilterValueChange(componentKey: string, column: string, event: Event): void {
    const select = event.target as HTMLSelectElement;
    const values = Array.from(select.selectedOptions).map((option) => option.value);
    this.draftFilters.update((current) => {
      const forComponent = { ...(current[componentKey] ?? {}) };
      if (values.length > 0) {
        forComponent[column] = values;
      } else {
        delete forComponent[column];
      }
      return { ...current, [componentKey]: forComponent };
    });
  }

  isDraftValueSelected(componentKey: string, column: string, value: string): boolean {
    return this.draftFilters()[componentKey]?.[column]?.includes(value) ?? false;
  }

  /** Commit this component's draft <select> choices as the APPLIED filters, re-fetch its distribution
   * under the narrowed population, reset its selection to the new population's median (the previous pick
   * may no longer exist in it), and refresh the composite panel's sample-average reference line. */
  applyFilters(dist: ComponentDistribution): void {
    const key = this.componentKey(dist.product, dist.building_type);
    const filters = { ...(this.draftFilters()[key] ?? {}) };
    this.appliedFilters.update((current) => ({ ...current, [key]: filters }));
    this.refreshComponentDistribution(dist, filters);
  }

  /** Reset this component back to its full (unfiltered) population. */
  clearFilters(dist: ComponentDistribution): void {
    const key = this.componentKey(dist.product, dist.building_type);
    this.draftFilters.update((current) => ({ ...current, [key]: {} }));
    this.appliedFilters.update((current) => ({ ...current, [key]: {} }));
    this.refreshComponentDistribution(dist, {});
  }

  private refreshComponentDistribution(dist: ComponentDistribution, filters: Record<string, string[]>): void {
    const key = this.componentKey(dist.product, dist.building_type);
    const componentSpec = this.compositeState
      .components()
      .find((c) => c.product === dist.product && c.building_type === dist.building_type);
    if (!componentSpec) {
      return;
    }
    const hasFilters = Object.keys(filters).length > 0;

    this.refreshingByKey.update((current) => ({ ...current, [key]: true }));
    this.errorMessage.set(null);
    this.api
      .getBuildingDistributions({
        components: [{ ...componentSpec, filters: hasFilters ? filters : null }],
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        upgrade: this.compositeState.upgrade(),
      })
      .subscribe({
        next: (result) => {
          const updated = result.distributions[0];
          if (updated) {
            this.distributions.update((current) => current.map((d) => (this.componentKey(d.product, d.building_type) === key ? updated : d)));
            const median = updated.percentile_buildings['median'];
            if (median) {
              this.setSelection(updated, median);
            }
          } else {
            const label = dist.label || dist.building_type;
            this.errorMessage.set(
              result.warnings[0] ?? `No buildings match the selected filters for ${label} -- try a broader combination.`,
            );
          }
          this.refreshingByKey.update((current) => ({ ...current, [key]: false }));
          this.refreshSampleAverage();
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to apply filters.');
          this.refreshingByKey.update((current) => ({ ...current, [key]: false }));
        },
      });
  }

  /** Select the real building closest to `value` -- used both for percentile/mean shortcuts and for a
   * user's click on the chart (mapped from a pixel position to a data value beforehand). */
  private nearestPoint(dist: ComponentDistribution, value: number): DistributionPoint {
    let nearest = dist.points[0];
    let bestDiff = Math.abs(nearest.value - value);
    for (const point of dist.points) {
      const diff = Math.abs(point.value - value);
      if (diff < bestDiff) {
        nearest = point;
        bestDiff = diff;
      }
    }
    return nearest;
  }

  selectPercentile(dist: ComponentDistribution, key: PercentileKey): void {
    const point = dist.percentile_buildings[key];
    if (point) {
      this.setSelection(dist, point);
    }
  }

  private selectValue(dist: ComponentDistribution, value: number): void {
    if (dist.points.length === 0) {
      return;
    }
    this.setSelection(dist, this.nearestPoint(dist, value));
  }

  /** The (KDE, or histogram-fallback) density curve for one component -- shared between its own chart and
   * the composite mixture panel below. */
  private curveFor(dist: ComponentDistribution): Curve {
    if (dist.kde_x.length > 0) {
      return { x: dist.kde_x, y: dist.kde_y };
    }
    const x = dist.histogram_bin_edges.slice(0, -1).map((edge, i) => (edge + dist.histogram_bin_edges[i + 1]) / 2);
    return { x, y: dist.histogram_density };
  }

  /** Linearly interpolate `curve` at `value`, returning 0 outside its domain (a density curve tapers to
   * ~0 at its edges anyway, so this is a reasonable extrapolation for the mixture sum below). */
  private interpolate(curve: Curve, value: number): number {
    const { x, y } = curve;
    if (x.length === 0 || value < x[0] || value > x[x.length - 1]) {
      return 0;
    }
    let lo = 0;
    let hi = x.length - 1;
    while (hi - lo > 1) {
      const mid = Math.floor((lo + hi) / 2);
      if (x[mid] <= value) {
        lo = mid;
      } else {
        hi = mid;
      }
    }
    const span = x[hi] - x[lo];
    const t = span > 0 ? (value - x[lo]) / span : 0;
    return y[lo] + t * (y[hi] - y[lo]);
  }

  private buildCompositeViewModel(): CompositeViewModel | null {
    const distributions = this.distributions();
    if (distributions.length < 2) {
      return null;
    }
    const curves = distributions.map((dist) => this.curveFor(dist));
    if (curves.some((c) => c.x.length === 0)) {
      return null;
    }

    const components = this.compositeState.components();
    const fractions = distributions.map(
      (dist) => components.find((c) => c.product === dist.product && c.building_type === dist.building_type)?.fraction ?? 0,
    );
    const totalFraction = fractions.reduce((a, b) => a + b, 0) || 1;
    const weights = fractions.map((f) => f / totalFraction);

    const gridMin = Math.min(...curves.map((c) => c.x[0]));
    const gridMax = Math.max(...curves.map((c) => c.x[c.x.length - 1]));
    const gridSize = 300;
    const grid = Array.from({ length: gridSize }, (_, i) => gridMin + (i * (gridMax - gridMin)) / (gridSize - 1));
    const mixtureDensity = grid.map((x) => curves.reduce((sum, curve, i) => sum + weights[i] * this.interpolate(curve, x), 0));

    const selections = this.selections();
    let selectedEnergyNumerator = 0;
    let selectedSqftDenominator = 0;
    let allSelected = true;
    distributions.forEach((dist, i) => {
      const key = this.componentKey(dist.product, dist.building_type);
      const selection = selections[key];
      if (!selection || selection.sqft == null || selection.annualSiteEnergyKwh == null) {
        allSelected = false;
        return;
      }
      selectedEnergyNumerator += weights[i] * selection.annualSiteEnergyKwh;
      selectedSqftDenominator += weights[i] * selection.sqft;
    });
    const weightedSelectedEui =
      allSelected && selectedSqftDenominator ? (selectedEnergyNumerator * KWH_TO_KBTU) / selectedSqftDenominator : null;
    const weightedSampleAverageEui = this.sampleAverageWeightedEui();

    return {
      chartData: this.buildCompositeChartData(grid, mixtureDensity),
      chartOptions: this.buildCompositeChartOptions(weightedSampleAverageEui, weightedSelectedEui),
      weightedSampleAverageEui,
      weightedSelectedEui,
    };
  }

  private buildCompositeChartData(grid: number[], mixtureDensity: number[]): ChartConfiguration<'line'>['data'] {
    return {
      datasets: [
        {
          label: 'Composite mixture density',
          data: grid.map((x, i) => ({ x, y: mixtureDensity[i] })),
          borderColor: '#7c3aed',
          backgroundColor: 'rgba(124, 58, 237, 0.15)',
          fill: true,
          pointRadius: 0,
          tension: 0.3,
        },
      ],
    };
  }

  private buildCompositeChartOptions(sampleAverageEui: number | null, selectedEui: number | null): ChartConfiguration<'line'>['options'] {
    const annotations: Record<string, AnnotationOptions<'line'>> = {};
    if (sampleAverageEui != null) {
      annotations['sampleAverageLine'] = {
        type: 'line',
        xMin: sampleAverageEui,
        xMax: sampleAverageEui,
        borderColor: '#2563eb',
        borderWidth: 2,
        borderDash: [4, 4],
        label: { display: true, content: `Sample avg: ${sampleAverageEui.toFixed(1)}`, position: 'end', backgroundColor: '#2563eb' },
      };
    }
    if (selectedEui != null) {
      annotations['selectedLine'] = {
        type: 'line',
        xMin: selectedEui,
        xMax: selectedEui,
        borderColor: '#dc2626',
        borderWidth: 2,
        borderDash: [6, 4],
        label: { display: true, content: `Selected: ${selectedEui.toFixed(1)}`, position: 'start', backgroundColor: '#dc2626' },
      };
    }
    return {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      scales: {
        x: { type: 'linear', title: { display: true, text: 'Site EUI (kBtu/ft2/yr)' } },
        y: { beginAtZero: true, title: { display: true, text: 'Probability density' } },
      },
      plugins: {
        legend: { display: false },
        annotation: { annotations },
      },
    };
  }

  private buildChartData(dist: ComponentDistribution): ChartConfiguration<'line'>['data'] {
    const curve = this.curveFor(dist);
    const curvePoints = curve.x.map((x, i) => ({ x, y: curve.y[i] }));
    const rugPoints = dist.points.map((p) => ({ x: p.value, y: 0 }));

    return {
      datasets: [
        {
          label: 'Probability density',
          data: curvePoints,
          borderColor: '#2563eb',
          backgroundColor: 'rgba(37, 99, 235, 0.15)',
          fill: true,
          pointRadius: 0,
          tension: 0.3,
          order: 2,
        },
        {
          label: 'Sampled buildings',
          data: rugPoints,
          showLine: false,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointBackgroundColor: 'rgba(100, 116, 139, 0.55)',
          pointBorderColor: 'rgba(100, 116, 139, 0.55)',
          order: 1,
        },
      ],
    };
  }

  private buildChartOptions(dist: ComponentDistribution, selection: Selection | undefined): ChartConfiguration<'line'>['options'] {
    return {
      responsive: true,
      maintainAspectRatio: false,
      parsing: false,
      scales: {
        x: {
          type: 'linear',
          title: { display: true, text: `Site EUI (${dist.unit})` },
        },
        y: {
          beginAtZero: true,
          title: { display: true, text: 'Probability density' },
        },
      },
      plugins: {
        legend: { display: true },
        tooltip: {
          callbacks: {
            label: (ctx) =>
              ctx.datasetIndex === 1 ? `bldg_id ${dist.points[ctx.dataIndex]?.bldg_id}` : `density: ${(ctx.parsed.y ?? 0).toFixed(4)}`,
          },
        },
        annotation: {
          annotations: selection
            ? {
                selectedLine: {
                  type: 'line',
                  xMin: selection.value,
                  xMax: selection.value,
                  borderColor: '#dc2626',
                  borderWidth: 2,
                  borderDash: [6, 4],
                  label: {
                    display: true,
                    content: `Selected: bldg ${selection.bldgId}`,
                    position: 'start',
                    backgroundColor: '#dc2626',
                  },
                },
                sampleMeanLine: {
                  type: 'line',
                  xMin: dist.mean_value,
                  xMax: dist.mean_value,
                  borderColor: '#64748b',
                  borderWidth: 1.5,
                  borderDash: [2, 3],
                  label: {
                    display: true,
                    content: `Population mean: ${dist.mean_value.toFixed(1)}`,
                    position: 'end',
                    backgroundColor: '#64748b',
                  },
                },
              }
            : {},
        },
      },
      // Click anywhere on the chart to pin the real building closest to that x-position -- lets a user
      // pick any point along the PDF curve, not just the discrete percentile/mean shortcuts below it.
      onClick: (event, _elements, chart) => {
        const xScale = chart.scales['x'];
        if (!xScale || event.x == null) {
          return;
        }
        const value = xScale.getValueForPixel(event.x);
        if (value != null) {
          this.selectValue(dist, value);
        }
      },
    };
  }

  skip(): void {
    this.router.navigate(['/dashboard']);
  }

  continueToDashboard(): void {
    const selections = this.selections();
    const applied = this.appliedFilters();
    const updated = this.compositeState.components().map((component) => {
      const key = this.componentKey(component.product, component.building_type);
      const selection = selections[key];
      const filters = applied[key];
      return {
        ...component,
        ...(selection ? { bldg_id: selection.bldgId } : {}),
        filters: filters && Object.keys(filters).length > 0 ? filters : null,
      };
    });
    this.compositeState.setComposite(
      updated,
      this.compositeState.state(),
      this.compositeState.countyName(),
      this.compositeState.upgrade(),
    );
    this.router.navigate(['/dashboard']);
  }
}
