import { Component, OnInit, signal } from '@angular/core';

import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ChartConfiguration } from 'chart.js';
// Side-effect import only -- brings in chartjs-plugin-zoom's TypeScript module augmentation so
// `plugins.zoom` below type-checks. The plugin itself is registered app-wide in chartjs-setup.ts.
import 'chartjs-plugin-zoom';
import { forkJoin, of } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { DEFAULT_METRIC_COLUMNS, EndUseValue, TimeseriesResponse } from '../../models/api.models';
import { CHART_COLORS } from '../../models/chart-colors';
import { ChartComponent } from '../chart/chart.component';
import { HeatmapComponent, HeatmapPoint } from '../heatmap/heatmap.component';

const COLUMN_LABELS: Record<string, string> = {
  'out.electricity.total.energy_consumption': 'Electricity (total)',
  'out.natural_gas.total.energy_consumption': 'Natural gas (total)',
  'out.district_cooling.total.energy_consumption': 'District cooling (total)',
  'out.district_heating.total.energy_consumption': 'District heating (total)',
  'out.fuel_oil.total.energy_consumption': 'Fuel oil (total)',
  'out.propane.total.energy_consumption': 'Propane (total)',
  'out.site_energy.total.energy_consumption': 'Site energy (total)',
};

@Component({
  selector: 'app-timeseries',
  standalone: true,
  imports: [FormsModule, ChartComponent, HeatmapComponent],
  templateUrl: './timeseries.component.html',
  styleUrl: './timeseries.component.scss',
})
export class TimeseriesComponent implements OnInit {
  loading = signal(false);
  exporting = signal(false);
  errorMessage = signal<string | null>(null);
  timeseries = signal<TimeseriesResponse | null>(null);
  /** Only populated when the composite's configured upgrade isn't already baseline ("0") -- lets the LDC
   * show both series side by side so the user can see the effect of the configured upgrade. */
  baselineTimeseries = signal<TimeseriesResponse | null>(null);
  selectedColumn = signal<string>(DEFAULT_METRIC_COLUMNS[6]);

  heatmapPoints: HeatmapPoint[] = [];
  loadDurationChartData?: ChartConfiguration<'line'>['data'];
  endUseChartData?: ChartConfiguration<'bar'>['data'];
  readonly lineOptions: ChartConfiguration<'line'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    elements: { point: { radius: 0 } },
    plugins: {
      legend: { display: true },
      // Scroll-wheel/pinch to zoom, click-drag to pan -- useful for a full 8760-hour load duration
      // curve where the interesting detail (top/bottom of the curve) can be a small fraction of it.
      zoom: {
        zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
        pan: { enabled: true, mode: 'x' },
        limits: { x: { min: 'original', max: 'original' } },
      },
    },
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

  get isComparingToBaseline(): boolean {
    return this.compositeState.upgrade() !== '0';
  }

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

  columnLabel(column: string): string {
    return COLUMN_LABELS[column] ?? column;
  }

  load(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    const components = this.compositeState.components();
    const state = this.compositeState.state();
    const countyName = this.compositeState.countyName();
    const upgrade = this.compositeState.upgrade();
    const comparingToBaseline = this.isComparingToBaseline;

    const requests = {
      current: this.api.getCompositeTimeseries({ components, state, county_name: countyName, upgrade, resample: 'hourly' }),
      baseline: comparingToBaseline
        ? this.api.getCompositeTimeseries({ components, state, county_name: countyName, upgrade: '0', resample: 'hourly' })
        : of(null),
      currentSummary: this.api.getMetadataSummary({ components, state, county_name: countyName, upgrade }),
      baselineSummary: comparingToBaseline ? this.api.getMetadataSummary({ components, state, county_name: countyName, upgrade: '0' }) : of(null),
    };

    forkJoin(requests).subscribe({
      next: (result) => {
        this.timeseries.set(result.current);
        this.baselineTimeseries.set(result.baseline);
        if (!result.current.columns.includes(this.selectedColumn())) {
          this.selectedColumn.set(result.current.columns[result.current.columns.length - 1]);
        }
        this.render();
        this.renderEndUseChart(result.currentSummary.by_end_use, result.baselineSummary?.by_end_use ?? null);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.error ?? 'Failed to load the composite time series.');
        this.loading.set(false);
      },
    });
  }

  onColumnChange(column: string): void {
    this.selectedColumn.set(column);
    this.render();
  }

  private sortedDescending(response: TimeseriesResponse | null, column: string): number[] {
    if (!response) {
      return [];
    }
    return response.series
      .map((row) => row[column] as number | null)
      .filter((v): v is number => v !== null)
      .sort((a, b) => b - a);
  }

  private render(): void {
    const data = this.timeseries();
    if (!data) {
      return;
    }
    const column = this.selectedColumn();
    const values = data.series.map((row) => (row[column] as number | null) ?? null);

    this.heatmapPoints = data.series.map((row) => ({
      timestamp: row['timestamp'] as string,
      value: (row[column] as number | null) ?? null,
    }));

    const currentSorted = this.sortedDescending(data, column);
    const baseline = this.baselineTimeseries();
    const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
      {
        label: baseline ? `Current (upgrade ${this.compositeState.upgrade()})` : this.columnLabel(column),
        data: currentSorted,
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37, 99, 235, 0.15)',
        fill: true,
        tension: 0,
      },
    ];
    if (baseline) {
      const baselineSorted = this.sortedDescending(baseline, column);
      datasets.push({
        label: 'Baseline (upgrade 0)',
        data: baselineSorted,
        borderColor: '#94a3b8',
        backgroundColor: 'rgba(148, 163, 184, 0.15)',
        fill: true,
        tension: 0,
      });
    }

    this.loadDurationChartData = {
      labels: currentSorted.map((_, i) => i),
      datasets,
    };
  }

  private renderEndUseChart(currentByEndUse: EndUseValue[], baselineByEndUse: EndUseValue[] | null): void {
    const endUseKeys = Array.from(new Set([...(baselineByEndUse ?? []).map((v) => v.key), ...currentByEndUse.map((v) => v.key)]));
    const labels = baselineByEndUse ? ['Baseline (upgrade 0)', `Current (upgrade ${this.compositeState.upgrade()})`] : ['Current'];
    const valueFor = (list: EndUseValue[], key: string) => list.find((v) => v.key === key)?.annual_energy_kwh ?? 0;

    this.endUseChartData = {
      labels,
      datasets: endUseKeys.map((key, i) => ({
        label: key,
        data: baselineByEndUse ? [valueFor(baselineByEndUse, key), valueFor(currentByEndUse, key)] : [valueFor(currentByEndUse, key)],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
      })),
    };
  }

  exportMos(): void {
    this.exporting.set(true);
    this.errorMessage.set(null);
    this.api
      .exportMos({
        components: this.compositeState.components(),
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        upgrade: this.compositeState.upgrade(),
      })
      .subscribe({
        next: (blob) => {
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement('a');
          anchor.href = url;
          anchor.download = `composite_thermal_loads_${this.compositeState.state()}.mos`;
          anchor.click();
          URL.revokeObjectURL(url);
          this.exporting.set(false);
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to export the .mos file.');
          this.exporting.set(false);
        },
      });
  }
}
