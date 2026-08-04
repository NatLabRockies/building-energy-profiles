import { Routes } from '@angular/router';

import { CompositeBuilderComponent } from './components/composite-builder/composite-builder.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { TimeseriesComponent } from './components/timeseries/timeseries.component';
import { MeasuresComponent } from './components/measures/measures.component';
import { confirmClearScenariosGuard } from './guards/confirm-clear-scenarios.guard';

export const routes: Routes = [
  { path: '', component: CompositeBuilderComponent, title: 'Composite Building Explorer', canActivate: [confirmClearScenariosGuard] },
  { path: 'dashboard', component: DashboardComponent, title: 'Dashboard' },
  { path: 'timeseries', component: TimeseriesComponent, title: 'Time Series' },
  { path: 'measures', component: MeasuresComponent, title: 'Measures' },
  { path: '**', redirectTo: '' },
];
