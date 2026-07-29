import { ClientSideRowModelModule, ModuleRegistry, NumberFilterModule, TextFilterModule, ValidationModule } from 'ag-grid-community';
import { isDevMode } from '@angular/core';

// AG Grid v31+ is fully modular -- only the features actually used by this app are registered
// (client-side rows + text/number filtering) to keep bundle size down, rather than pulling in
// AllCommunityModule (charts, row grouping, master/detail, etc. this app doesn't use).
ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  TextFilterModule,
  NumberFilterModule,
  ...(isDevMode() ? [ValidationModule] : []),
]);
