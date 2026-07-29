import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ChartConfiguration } from 'chart.js';
import { forkJoin } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { EndUseValue, MeasureInfo, MeasuresCompareResponse, Product, TimeseriesResponse } from '../../models/api.models';
import { CHART_COLORS } from '../../models/chart-colors';
import { ChartComponent } from '../chart/chart.component';

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
  imports: [CommonModule, FormsModule, ChartComponent],
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

  savingsChartData?: ChartConfiguration<'bar'>['data'];
  loadDurationChartData?: ChartConfiguration<'line'>['data'];
  endUseChartData?: ChartConfiguration<'bar'>['data'];
  readonly barOptions: ChartConfiguration<'bar'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: { y: { title: { display: true, text: 'Savings vs. baseline (kWh)' } } },
  };
  readonly lineOptions: ChartConfiguration<'line'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    elements: { point: { radius: 0 } },
    plugins: { legend: { display: true } },
    scales: {
      x: { title: { display: true, text: 'Hours, sorted descending' } },
      // Hourly-resampled energy (kWh per hour) is numerically equal to average power (kW) over that
      // hour, and a load *duration* curve is conventionally a power curve, not an energy curve.
      y: { title: { display: true, text: 'kW' } },
    },
  };
  readonly stackedBarOptions: ChartConfiguration<'bar'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true },
      y: { stacked: true, title: { display: true, text: 'Annual energy (kWh)' } },
    },
  };

  readonly maxSelectable = MAX_SELECTABLE_MEASURES;

  constructor(
    private readonly api: ApiService,
    readonly compositeState: CompositeStateService,
    private readonly router: Router,
  ) {}

  /** Every distinct BuildStock product represented in the composite -- a mixed (commercial + residential)
   * composite pulls measures from both catalogs; a single-product composite pulls from just the one. */
  get distinctProducts(): Product[] {
    return Array.from(new Set(this.compositeState.components().map((c) => c.product)));
  }

  ngOnInit(): void {
    if (!this.compositeState.hasComposite()) {
      this.router.navigate(['/']);
      return;
    }
    this.loading.set(true);
    const products = this.distinctProducts;
    forkJoin(products.map((product) => this.api.getMeasures(product))).subscribe({
      next: (results) => {
        const merged = results.flatMap((result) =>
          result.measures.map((m): MeasureOption => ({ ...m, selectionKey: `${m.product}:${m.id}` })),
        );
        this.measures.set(merged);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.error ?? 'Failed to load the measure catalog.');
        this.loading.set(false);
      },
    });
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

  compare(): void {
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
          this.loadDetailTimeseries(selectionKeys);
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to compare measures.');
          this.comparing.set(false);
        },
      });
  }

  private loadDetailTimeseries(selectionKeys: string[]): void {
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
        this.buildLoadDurationChart(baseline, measureResponses as Record<string, TimeseriesResponse>, selectionKeys);
        this.loadingDetail.set(false);
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
    const datasets: NonNullable<ChartConfiguration<'line'>['data']>['datasets'] = [
      {
        label: 'Baseline',
        data: baselineSorted,
        borderColor: '#94a3b8',
        backgroundColor: 'rgba(148, 163, 184, 0.15)',
        fill: true,
        tension: 0,
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
        label: this.measureName(key),
        data: this.sortedDescending(response, DEFAULT_SAVINGS_COLUMN),
        borderColor: CHART_COLORS[i % CHART_COLORS.length],
        fill: false,
        tension: 0,
      });
    });
    this.loadDurationChartData = { labels: baselineSorted.map((_, i) => i), datasets };
  }

  private buildEndUseChart(result: MeasuresCompareResponse, selectionKeys: string[]): void {
    const perSelectionEndUse = selectionKeys.map((key) => result.by_end_use[key] ?? []);
    const endUseKeys = Array.from(
      new Set([...result.baseline_by_end_use.map((v) => v.key), ...perSelectionEndUse.flat().map((v) => v.key)]),
    );
    const valueFor = (list: EndUseValue[], key: string) => list.find((v) => v.key === key)?.annual_energy_kwh ?? 0;

    this.endUseChartData = {
      labels: ['Baseline', ...selectionKeys.map((key) => this.measureName(key))],
      datasets: endUseKeys.map((key, i) => ({
        label: key,
        data: [valueFor(result.baseline_by_end_use, key), ...perSelectionEndUse.map((list) => valueFor(list, key))],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
      })),
    };
  }

  private buildChart(result: MeasuresCompareResponse): void {
    const savings = result.results[DEFAULT_SAVINGS_COLUMN];
    if (!savings) {
      this.savingsChartData = undefined;
      return;
    }
    this.savingsChartData = {
      labels: savings.map((s) => s.name ?? s.upgrade_id),
      datasets: [
        {
          label: 'Site energy savings (kWh)',
          data: savings.map((s) => Math.round(s.absolute_savings_kwh)),
          backgroundColor: savings.map((s) => (s.absolute_savings_kwh >= 0 ? '#16a34a' : '#dc2626')),
        },
      ],
    };
  }
}
