import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { ChartConfiguration } from 'chart.js';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { ComponentSummary, MetadataSummaryResponse } from '../../models/api.models';
import { CHART_COLORS } from '../../models/chart-colors';
import { ChartComponent } from '../chart/chart.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, ChartComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  summary = signal<MetadataSummaryResponse | null>(null);
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  byFuelChartData?: ChartConfiguration<'pie'>['data'];
  byEndUseChartData?: ChartConfiguration<'bar'>['data'];

  /** True once the composite is sized by floor area (e.g. any mix of ComStock and ResStock components) --
   * that's the only case where `ComponentSummary.unit_multiplier` (the number of representative
   * buildings/dwelling units, such as apartment count for a multifamily component) is populated and
   * worth showing as its own column. */
  readonly hasUnitMultipliers = computed(() => this.summary()?.components.some((c) => c.unit_multiplier != null) ?? false);

  readonly pieOptions: ChartConfiguration<'pie'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
  };
  readonly stackedBarOptions: ChartConfiguration<'bar'>['options'] = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true },
      y: { stacked: true, title: { display: true, text: 'Annual energy (kWh)' } },
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
    this.byFuelChartData = {
      labels: result.by_fuel.map((item) => item.key),
      datasets: [
        {
          data: result.by_fuel.map((item) => Math.round(item.annual_energy_kwh)),
          backgroundColor: CHART_COLORS,
        },
      ],
    };
    this.byEndUseChartData = {
      labels: ['Composite'],
      datasets: result.by_end_use.map((item, i) => ({
        label: item.key,
        data: [Math.round(item.annual_energy_kwh)],
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
      })),
    };
  }

  /** URL for downloading a component's pinned building's energy model file (ComStock ".osm.gz" model or
   * ResStock ".zip" archive) -- `null` if this component has no pinned building yet (see "Select
   * Buildings"). Meant to be used directly as a link `href`, not fetched via HttpClient. */
  modelDownloadUrl(component: ComponentSummary): string | null {
    if (component.selected_bldg_id == null) {
      return null;
    }
    return this.api.getModelDownloadUrl(component.product, component.selected_bldg_id, this.compositeState.upgrade());
  }
}
