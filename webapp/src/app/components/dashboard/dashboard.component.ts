import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import type { Data, Layout } from 'plotly.js-dist-min';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { MetadataSummaryResponse } from '../../models/api.models';
import { CHART_COLORS } from '../../models/chart-colors';
import { PlotComponent } from '../plot/plot.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, PlotComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  summary = signal<MetadataSummaryResponse | null>(null);
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  byFuelChartData?: Data[];
  byEndUseChartData?: Data[];
  readonly pieLayout: Partial<Layout> = {
    autosize: true,
    margin: { l: 20, r: 20, t: 20, b: 20 },
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

  load(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.api
      .getMetadataSummary({
        components: this.compositeState.components(),
        state: this.compositeState.state(),
        county_name: this.compositeState.countyName(),
        upgrade: this.compositeState.upgrade(),
      })
      .subscribe({
        next: (result) => {
          this.summary.set(result);
          this.buildCharts(result);
          this.loading.set(false);
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to load the metadata summary.');
          this.loading.set(false);
        },
      });
  }

  private buildCharts(result: MetadataSummaryResponse): void {
    this.byFuelChartData = [
      {
        type: 'pie',
        labels: result.by_fuel.map((item) => item.key),
        values: result.by_fuel.map((item) => Math.round(item.annual_energy_kwh)),
        marker: { colors: CHART_COLORS },
      },
    ];
    this.byEndUseChartData = result.by_end_use.map((item, i) => ({
      type: 'bar',
      name: item.key,
      x: ['Composite'],
      y: [Math.round(item.annual_energy_kwh)],
      marker: { color: CHART_COLORS[i % CHART_COLORS.length] },
    }));
  }
}
