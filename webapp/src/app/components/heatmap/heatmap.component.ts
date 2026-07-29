import { AfterViewInit, Component, ElementRef, Input, OnChanges, SimpleChanges, ViewChild } from '@angular/core';
import { DecimalPipe } from '@angular/common';

export interface HeatmapPoint {
  timestamp: string;
  value: number | null;
}

const DAYS_IN_YEAR = 365;
const HOURS_IN_DAY = 24;
const CELL_WIDTH = 2;
const CELL_HEIGHT = 8;
const LEFT_MARGIN = 36;
const TOP_MARGIN = 10;

/** Renders a classic annual "8760" heat map: 365 day columns x 24 hour rows, colored by value. Built with
 * plain Canvas 2D (no charting library dependency) since this isn't a standard Chart.js chart type. */
@Component({
  selector: 'app-heatmap',
  standalone: true,
  template: `
    <canvas #canvas [width]="canvasWidth" [height]="canvasHeight"></canvas>
    <div class="legend">
      <span>{{ minValue | number: '1.0-1' }}</span>
      <div class="gradient"></div>
      <span>{{ maxValue | number: '1.0-1' }}</span>
      <span class="units">{{ unitsLabel }}</span>
    </div>
  `,
  styleUrl: './heatmap.component.scss',
  imports: [DecimalPipe],
})
export class HeatmapComponent implements AfterViewInit, OnChanges {
  @Input({ required: true }) points!: HeatmapPoint[];
  @Input() unitsLabel = '';

  @ViewChild('canvas', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  canvasWidth = LEFT_MARGIN + DAYS_IN_YEAR * CELL_WIDTH;
  canvasHeight = TOP_MARGIN + HOURS_IN_DAY * CELL_HEIGHT;
  minValue = 0;
  maxValue = 0;

  ngAfterViewInit(): void {
    this.draw();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['points'] && this.canvasRef) {
      this.draw();
    }
  }

  private draw(): void {
    const ctx = this.canvasRef.nativeElement.getContext('2d');
    if (!ctx || !this.points?.length) {
      return;
    }

    const values = this.points.map((p) => p.value).filter((v): v is number => v !== null && !Number.isNaN(v));
    this.minValue = values.length ? Math.min(...values) : 0;
    this.maxValue = values.length ? Math.max(...values) : 1;
    const range = this.maxValue - this.minValue || 1;

    ctx.clearRect(0, 0, this.canvasWidth, this.canvasHeight);

    for (let i = 0; i < this.points.length && i < DAYS_IN_YEAR * HOURS_IN_DAY; i++) {
      const day = Math.floor(i / HOURS_IN_DAY);
      const hour = i % HOURS_IN_DAY;
      const value = this.points[i].value;
      ctx.fillStyle = value === null || Number.isNaN(value) ? '#e5e7eb' : this.colorFor((value - this.minValue) / range);
      ctx.fillRect(LEFT_MARGIN + day * CELL_WIDTH, TOP_MARGIN + hour * CELL_HEIGHT, CELL_WIDTH, CELL_HEIGHT);
    }

    ctx.fillStyle = '#374151';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    [0, 6, 12, 18].forEach((hour) => {
      ctx.fillText(`${hour}:00`, LEFT_MARGIN - 4, TOP_MARGIN + hour * CELL_HEIGHT + CELL_HEIGHT);
    });

    const monthStarts = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    ctx.textAlign = 'left';
    monthStarts.forEach((dayIndex, i) => {
      ctx.fillText(monthLabels[i], LEFT_MARGIN + dayIndex * CELL_WIDTH, TOP_MARGIN + HOURS_IN_DAY * CELL_HEIGHT + 12);
    });
  }

  /** A simple blue -> yellow -> red gradient (low to high), good enough for relative-intensity heat maps
   * without pulling in a color-scale library. */
  private colorFor(fraction: number): string {
    const clamped = Math.min(1, Math.max(0, fraction));
    const stops: [number, [number, number, number]][] = [
      [0, [37, 99, 235]],
      [0.5, [250, 204, 21]],
      [1, [220, 38, 38]],
    ];
    for (let i = 0; i < stops.length - 1; i++) {
      const [startFraction, startColor] = stops[i];
      const [endFraction, endColor] = stops[i + 1];
      if (clamped >= startFraction && clamped <= endFraction) {
        const localFraction = (clamped - startFraction) / (endFraction - startFraction || 1);
        const [r, g, b] = startColor.map((channel, index) => Math.round(channel + (endColor[index] - channel) * localFraction));
        return `rgb(${r}, ${g}, ${b})`;
      }
    }
    return `rgb(${stops[stops.length - 1][1].join(', ')})`;
  }
}
