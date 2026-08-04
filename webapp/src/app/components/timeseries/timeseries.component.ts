import { Component, OnInit, ViewChild, signal } from '@angular/core';

import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import type { Config, Data, Layout } from 'plotly.js-dist-min';
import { forkJoin, of } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { DEFAULT_METRIC_COLUMNS, EndUseValue, TimeseriesResponse } from '../../models/api.models';
import { CHART_COLORS } from '../../models/chart-colors';
import { HeatmapComponent, HeatmapPoint } from '../heatmap/heatmap.component';
import { PlotComponent } from '../plot/plot.component';

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
  imports: [FormsModule, PlotComponent, HeatmapComponent],
  templateUrl: './timeseries.component.html',
  styleUrl: './timeseries.component.scss',
})
export class TimeseriesComponent implements OnInit {
  loading = signal(false);
  exporting = signal(false);
  downloadingModels = signal(false);
  errorMessage = signal<string | null>(null);
  timeseries = signal<TimeseriesResponse | null>(null);
  /** Only populated when the composite's configured upgrade isn't already baseline ("0") -- lets the LDC
   * show both series side by side so the user can see the effect of the configured upgrade. */
  baselineTimeseries = signal<TimeseriesResponse | null>(null);
  selectedColumn = signal<string>(DEFAULT_METRIC_COLUMNS[6]);

  heatmapPoints: HeatmapPoint[] = [];
  loadDurationChartData?: Data[];
  /** Reference to the load duration curve's <app-plot>, so its "Reset zoom" button can restore autorange. */
  @ViewChild('ldcChart') ldcChart?: PlotComponent;
  endUseChartData?: Data[];
  readonly plotConfig: Partial<Config> = { responsive: true, displaylogo: false };
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
    margin: { l: 60, r: 20, t: 20, b: 50 },
    xaxis: {},
    yaxis: {
      title: { text: 'Annual energy (kWh)' },
    },
  };

  get isComparingToBaseline(): boolean {
    return this.compositeState.upgrade() !== '0';
  }

  /** The exact real building/dwelling-unit downloaded and used for each composite component -- since this
   * page only pulls a single representative building per component (not every sampled one), this makes an
   * otherwise-invisible selection (the API's own pick, absent an explicit override) visible to the user.
   */
  get selectedBuildings(): { key: string; label: string; bldgId: number | null }[] {
    const data = this.timeseries();
    if (!data) {
      return [];
    }
    return Object.keys(data.component_labels).map((key) => ({
      key,
      label: data.component_labels[key],
      bldgId: data.component_bldg_ids[key] ?? null,
    }));
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
    const datasets: Data[] = [
      {
        type: 'scatter',
        mode: 'lines',
        name: baseline ? `Current (upgrade ${this.compositeState.upgrade()})` : this.columnLabel(column),
        x: currentSorted.map((_, i) => i),
        y: currentSorted,
        line: { color: '#2563eb' },
        fill: 'tozeroy',
        fillcolor: 'rgba(37, 99, 235, 0.15)',
      },
    ];
    if (baseline) {
      const baselineSorted = this.sortedDescending(baseline, column);
      datasets.push({
        type: 'scatter',
        mode: 'lines',
        name: 'Baseline (upgrade 0)',
        x: baselineSorted.map((_, i) => i),
        y: baselineSorted,
        line: { color: '#94a3b8' },
        fill: 'tozeroy',
        fillcolor: 'rgba(148, 163, 184, 0.15)',
      });
    }

    this.loadDurationChartData = datasets;
  }

  private renderEndUseChart(currentByEndUse: EndUseValue[], baselineByEndUse: EndUseValue[] | null): void {
    const endUseKeys = Array.from(new Set([...(baselineByEndUse ?? []).map((v) => v.key), ...currentByEndUse.map((v) => v.key)]));
    const labels = baselineByEndUse ? ['Baseline (upgrade 0)', `Current (upgrade ${this.compositeState.upgrade()})`] : ['Current'];
    const valueFor = (list: EndUseValue[], key: string) => list.find((v) => v.key === key)?.annual_energy_kwh ?? 0;

    this.endUseChartData = endUseKeys.map((key, i) => ({
      type: 'bar',
      name: key,
      x: labels,
      y: baselineByEndUse ? [valueFor(baselineByEndUse, key), valueFor(currentByEndUse, key)] : [valueFor(currentByEndUse, key)],
      marker: { color: CHART_COLORS[i % CHART_COLORS.length] },
    }));
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

  /** Download the actual OpenStudio building energy model(s) for the composite's representative
   * building(s) -- one real model per component (ComStock: gzipped ".osm.gz"; ResStock: a ".zip" of the
   * model + its schedule files), bundled into one ".zip" if there's more than one component. Reuses this
   * page's already-resolved `component_bldg_ids` (the same bldg_id(s) shown in "Representative
   * building(s)" above and used for the time series/LDC/heat map) so the downloaded model always matches
   * what's already displayed, instead of an independently auto-selected building. */
  downloadBuildingModels(): void {
    const data = this.timeseries();
    this.downloadingModels.set(true);
    this.errorMessage.set(null);
    this.api
      .downloadBuildingEnergyModels({
        components: this.compositeState.components(),
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        upgrade: this.compositeState.upgrade(),
        bldg_ids: data?.component_bldg_ids ?? null,
      })
      .subscribe({
        next: (blob) => {
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement('a');
          anchor.href = url;
          const components = this.compositeState.components();
          anchor.download =
            components.length === 1
              ? `${components[0].product}_${components[0].building_type}_model.${components[0].product === 'resstock' ? 'zip' : 'osm.gz'}`
              : `composite_building_energy_models_${this.compositeState.state()}.zip`;
          anchor.click();
          URL.revokeObjectURL(url);
          this.downloadingModels.set(false);
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to download the building energy model(s).');
          this.downloadingModels.set(false);
        },
      });
  }

}
