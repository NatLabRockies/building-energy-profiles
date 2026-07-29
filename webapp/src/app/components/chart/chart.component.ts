import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { Chart, ChartConfiguration, ChartType } from 'chart.js';

// Chart.js registerables + the zoom/annotation plugins are registered once, app-wide, in
// chartjs-setup.ts (imported from main.ts) -- no per-component registration needed here.

/** Thin wrapper around Chart.js (used directly rather than an ng2-charts-style Angular wrapper, to avoid
 * its Angular-version peer-dependency churn) -- pass a standard Chart.js `data`/`options`/`type` and this
 * creates/updates/destroys the underlying chart as inputs change. */
@Component({
  selector: 'app-chart',
  standalone: true,
  template: `<canvas #canvas></canvas>`,
  styles: [':host { display: block; position: relative; width: 100%; height: 100%; }'],
})
export class ChartComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) type!: ChartType;
  @Input({ required: true }) data!: ChartConfiguration['data'];
  @Input() options: ChartConfiguration['options'] = {};

  @ViewChild('canvas', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  private chart?: Chart;

  ngAfterViewInit(): void {
    this.chart = new Chart(this.canvasRef.nativeElement, {
      type: this.type,
      data: this.data,
      options: this.options,
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.chart) {
      return;
    }
    if (changes['type'] && !changes['type'].firstChange) {
      this.chart.destroy();
      this.chart = new Chart(this.canvasRef.nativeElement, {
        type: this.type,
        data: this.data,
        options: this.options,
      });
      return;
    }
    if (changes['data']) {
      this.chart.data = this.data;
    }
    if (changes['options']) {
      this.chart.options = this.options ?? {};
    }
    this.chart.update();
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }
}
