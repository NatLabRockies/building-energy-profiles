import { bootstrapApplication } from '@angular/platform-browser';
import './app/ag-grid-modules';
import './app/chartjs-setup';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

bootstrapApplication(AppComponent, appConfig)
  .catch((err) => console.error(err));
