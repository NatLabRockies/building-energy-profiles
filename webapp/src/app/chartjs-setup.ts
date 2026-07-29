import { Chart, registerables } from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';
import zoomPlugin from 'chartjs-plugin-zoom';

// Registered once, app-wide, so every <app-chart> instance gets pan/zoom (chartjs-plugin-zoom)
// and reference-line/box annotations (chartjs-plugin-annotation) without each chart needing to
// register plugins itself.
Chart.register(...registerables);
Chart.register(annotationPlugin);
Chart.register(zoomPlugin);
