import { AfterViewInit, Component, ElementRef, Input, OnChanges, OnDestroy, SimpleChanges, ViewChild } from '@angular/core';
import type { Config, Data, Layout, PlotMouseEvent, PlotRelayoutEvent, PlotlyHTMLElement } from 'plotly.js-dist-min';
import Plotly from 'plotly.js-dist-min';

/** Thin Angular wrapper around Plotly.js -- replaces the old Chart.js-based `<app-chart>`. Plotly's own
 * `Plotly.react()` (rather than `newPlot()`) is used for every update, which Plotly diffs against the
 * existing figure internally and only touches what changed -- this avoids the "flashing"/constant
 * re-animation that Chart.js's `chart.update()` suffered when a *new* (but equal-by-value) `options`
 * object reference was passed in on every Angular change-detection tick (a very easy trap with Chart.js,
 * since it has no built-in equality check and always treats a new object reference as a real change).
 *
 * Plotly's native UI already includes box-zoom (default left-drag), scroll/pinch zoom, pan, and a
 * "reset axes" toolbar button out of the box, so there's no need for a separate zoom plugin/library like
 * chartjs-plugin-zoom -- `resetZoom()` below just triggers Plotly's own axis autorange.
 */
@Component({
  selector: 'app-plot',
  standalone: true,
  template: `<div #plotDiv class="plot-div"></div>`,
  styles: [
    ':host { display: block; position: relative; width: 100%; height: 100%; }',
    '.plot-div { width: 100%; height: 100%; }',
  ],
})
export class PlotComponent implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) data!: Data[];
  @Input() layout: Partial<Layout> = {};
  @Input() config: Partial<Config> = { responsive: true, displaylogo: false };
  /** Emits `(x, y)` data-coordinates (not pixel coordinates) for a click anywhere on the plot area --
   * lets callers implement "click a point on the curve" interactions without wiring up Plotly's raw event
   * objects themselves. */
  @Input() onPointClick?: (x: number, y: number) => void;

  @ViewChild('plotDiv', { static: true }) plotDivRef!: ElementRef<HTMLDivElement>;

  private plotElement?: PlotlyHTMLElement;
  private rendered = false;

  resetZoom(): void {
    if (!this.plotElement) {
      return;
    }
    void Plotly.relayout(this.plotElement, { 'xaxis.autorange': true, 'yaxis.autorange': true });
  }

  ngAfterViewInit(): void {
    this.render();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.rendered) {
      // Not mounted yet (inputs can change before ngAfterViewInit runs) -- ngAfterViewInit's initial
      // render will pick up the latest input values already, so there's nothing to do here yet.
      return;
    }
    if (changes['data'] || changes['layout'] || changes['config']) {
      this.render();
    }
  }

  ngOnDestroy(): void {
    if (this.plotElement) {
      void Plotly.purge(this.plotElement);
    }
  }

  private render(): void {
    const element = this.plotDivRef.nativeElement;
    void Plotly.react(element, this.data, this.layout, this.config).then((plotElement) => {
      this.plotElement = plotElement;
      if (!this.rendered) {
        this.rendered = true;
        if (this.onPointClick) {
          plotElement.on('plotly_click', (event: PlotMouseEvent) => {
            const point = event.points?.[0];
            if (point && this.onPointClick) {
              this.onPointClick(point.x as number, point.y as number);
            }
          });
        }
      }
    });
  }
}

export type { Data as PlotData, Layout as PlotLayout, PlotRelayoutEvent };
