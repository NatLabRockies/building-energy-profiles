import { Routes } from '@angular/router';

import { CompositeBuilderComponent } from './components/composite-builder/composite-builder.component';
import { SelectBuildingsComponent } from './components/select-buildings/select-buildings.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { TimeseriesComponent } from './components/timeseries/timeseries.component';
import { MeasuresComponent } from './components/measures/measures.component';

export const routes: Routes = [
  { path: '', component: CompositeBuilderComponent, title: 'Composite Building Explorer' },
  { path: 'select-buildings', component: SelectBuildingsComponent, title: 'Select Representative Buildings' },
  { path: 'dashboard', component: DashboardComponent, title: 'Dashboard' },
  { path: 'timeseries', component: TimeseriesComponent, title: 'Time Series' },
  { path: 'measures', component: MeasuresComponent, title: 'Measures' },
  { path: '**', redirectTo: '' },
];
