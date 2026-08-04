import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { Validators } from '@angular/forms';

import { CompositeBuilderComponent } from './composite-builder.component';
import { BuilderPreferencesService } from '../../services/builder-preferences.service';
import { CompositeStateService } from '../../services/composite-state.service';

/** Tests for the fraction-mode auto-rebalancing logic added to the Composite Builder: editing one row's
 * percentage, or adding/removing a row, should automatically rescale the other rows so the whole set keeps
 * summing to exactly 100% (preserving their relative shares to each other), without fighting the user
 * while sqft mode is active (where totals are informational only). */
describe('CompositeBuilderComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    localStorage.removeItem('buildstock.builder.last-state');
    await TestBed.configureTestingModule({
      imports: [CompositeBuilderComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function createComponent(): CompositeBuilderComponent {
    const fixture = TestBed.createComponent(CompositeBuilderComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    // ngOnInit fires 5 requests (ENERGY STAR types, ComStock/ResStock building types x2, available states,
    // available counties for the default state) -- irrelevant to the rebalancing logic under test, so just
    // flush each with an empty/minimal response matching its endpoint.
    for (const req of httpMock.match(() => true)) {
      if (req.request.url.includes('/locations/states')) {
        req.flush({ ok: true, product: 'comstock', states: [] });
      } else if (req.request.url.includes('/locations/counties')) {
        req.flush({ ok: true, product: 'comstock', state: 'DE', counties: [], note: '' });
      } else if (req.request.url.includes('/building-types')) {
        const product = req.request.params.get('product') ?? 'comstock';
        const buildingTypes = product === 'comstock' ? ['SmallOffice', 'MediumOffice'] : ['Single-Family Detached'];
        req.flush({ ok: true, product, building_types: buildingTypes });
      } else {
        req.flush([]);
      }
    }
    return component;
  }

  function amounts(component: CompositeBuilderComponent): number[] {
    return component.rows.controls.map((row) => Number(row.get('amount')?.value));
  }

  it('starts with a single row at 100%', () => {
    const component = createComponent();
    expect(amounts(component)).toEqual([100]);
    expect(component.amountTotal).toBe(100);
  });

  it('addRow() splits the total evenly and keeps the sum at 100%', () => {
    const component = createComponent();
    component.addRow();
    expect(amounts(component)).toEqual([50, 50]);
    expect(component.amountTotal).toBe(100);
  });

  it('addRow() a third time preserves the existing rows relative shares', () => {
    const component = createComponent();
    component.addRow(); // 50/50
    component.rows.at(0).get('amount')?.setValue(70);
    component.onAmountChanged(0); // 70/30
    component.addRow(); // new row gets an even 1/3 share, other two rescale preserving 70:30 ratio

    const [a, b, c] = amounts(component);
    expect(c).toBeCloseTo(100 / 3, 1);
    expect(a / b).toBeCloseTo(70 / 30, 1);
    expect(component.amountTotal).toBeCloseTo(100, 6);
  });

  it('removeRow() rescales the remaining rows to sum back to 100%, preserving their ratio', () => {
    const component = createComponent();
    component.addRow();
    component.rows.at(0).get('amount')?.setValue(60);
    component.onAmountChanged(0); // 60/40
    component.addRow(); // 3 rows: 40/26.7/33.3-ish, sums to 100

    component.removeRow(2); // drop the newest row -- remaining two should rescale to sum to 100 again
    const [a, b] = amounts(component);
    expect(a + b).toBeCloseTo(100, 6);
    expect(a).toBeGreaterThan(b); // original 60:40 skew should still favor row 0
  });

  it('removing down to a single row makes it 100%', () => {
    const component = createComponent();
    component.addRow();
    component.removeRow(1);
    expect(amounts(component)).toEqual([100]);
  });

  it('onAmountChanged() rescales the other rows proportionally to keep the total at 100%', () => {
    const component = createComponent();
    component.addRow(); // 50/50
    component.addRow(); // ~33.3/33.3/33.4

    component.rows.at(0).get('amount')?.setValue(70);
    component.onAmountChanged(0);

    const [a, b, c] = amounts(component);
    expect(a).toBe(70);
    expect(b).toBeCloseTo(c, 1); // rows 2/3 were equal before, so they should still be equal after
    expect(a + b + c).toBeCloseTo(100, 6);
  });

  it('onAmountChanged() splits evenly among other rows that are currently at 0%', () => {
    const component = createComponent();
    component.addRow();
    component.addRow(); // 3 rows summing to 100

    // Directly zero out rows 1 and 2 (bypassing rebalance) to set up the "others sum to 0" case.
    component.rows.at(1).get('amount')?.setValue(0);
    component.rows.at(2).get('amount')?.setValue(0);

    component.rows.at(0).get('amount')?.setValue(40);
    component.onAmountChanged(0);

    const [a, b, c] = amounts(component);
    expect(a).toBe(40);
    expect(b).toBeCloseTo(30, 1);
    expect(c).toBeCloseTo(30, 1);
  });

  it('clamps an edited value above 100 down to 100, zeroing the other rows', () => {
    const component = createComponent();
    component.addRow();
    component.rows.at(0).get('amount')?.setValue(150);
    component.onAmountChanged(0);

    const [a, b] = amounts(component);
    expect(a).toBe(100);
    expect(b).toBe(0);
  });

  it('does not rebalance in sqft mode', () => {
    const component = createComponent();
    component.setMode('sqft');
    component.addRow();
    component.rows.at(0).get('amount')?.setValue(40_000);
    component.onAmountChanged(0);
    component.rows.at(1).get('amount')?.setValue(20_000);
    component.onAmountChanged(1);

    expect(amounts(component)).toEqual([40_000, 20_000]);
  });

  it('normalizes leftover sqft-mode values proportionally when switching back to fraction mode', () => {
    const component = createComponent();
    component.setMode('sqft');
    component.addRow();
    component.rows.at(0).get('amount')?.setValue(40_000);
    component.onAmountChanged(0);
    component.rows.at(1).get('amount')?.setValue(20_000);
    component.onAmountChanged(1);

    component.setMode('fraction');

    const [a, b] = amounts(component);
    expect(a).toBeCloseTo((2 / 3) * 100, 0);
    expect(b).toBeCloseTo((1 / 3) * 100, 0);
    expect(component.amountTotal).toBeCloseTo(100, 6);
  });
});

/** Tests for the ENERGY STAR vs. ComStock/ResStock "type source" toggle: ENERGY STAR is the default, and
 * switching between the two resets each row's type selection (never mixes the two within one composite --
 * enforced by the backend's "same type source" validation on resolve). */
describe('CompositeBuilderComponent type source toggle', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CompositeBuilderComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function createComponent(): CompositeBuilderComponent {
    const fixture = TestBed.createComponent(CompositeBuilderComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    for (const req of httpMock.match(() => true)) {
      if (req.request.url.includes('/locations/states')) {
        req.flush({ ok: true, product: 'comstock', states: [] });
      } else if (req.request.url.includes('/locations/counties')) {
        req.flush({ ok: true, product: 'comstock', state: 'DE', counties: [], note: '' });
      } else if (req.request.url.includes('/building-types')) {
        const product = req.request.params.get('product') ?? 'comstock';
        const buildingTypes = product === 'comstock' ? ['SmallOffice', 'MediumOffice'] : ['Single-Family Detached'];
        req.flush({ ok: true, product, building_types: buildingTypes });
      } else {
        req.flush([]);
      }
    }
    return component;
  }

  it('defaults to the ENERGY STAR property type entry mode', () => {
    const component = createComponent();
    expect(component.typeSource()).toBe('energy_star');
    expect(component.rows.at(0).get('energyStarType')?.hasValidator(Validators.required)).toBe(true);
    expect(component.rows.at(0).get('product')?.hasValidator(Validators.required)).toBe(false);
    expect(component.rows.at(0).get('buildingType')?.hasValidator(Validators.required)).toBe(false);
  });

  it('switching to buildstock mode requires product/buildingType instead of energyStarType', () => {
    const component = createComponent();
    component.setTypeSource('buildstock');

    const row = component.rows.at(0);
    expect(row.get('energyStarType')?.hasValidator(Validators.required)).toBe(false);
    expect(row.get('product')?.hasValidator(Validators.required)).toBe(true);
    expect(row.get('buildingType')?.hasValidator(Validators.required)).toBe(true);
    // Product defaults to comstock once building-type entry is selected.
    expect(row.get('product')?.value).toBe('comstock');
  });

  it('lists the fetched building types for the row\'s selected product', () => {
    const component = createComponent();
    expect(component.buildingTypesFor('comstock')).toEqual(['SmallOffice', 'MediumOffice']);
    expect(component.buildingTypesFor('resstock')).toEqual(['Single-Family Detached']);
  });

  it('resets buildingType when the product selector changes', () => {
    const component = createComponent();
    component.setTypeSource('buildstock');
    component.rows.at(0).get('buildingType')?.setValue('MediumOffice');

    component.rows.at(0).get('product')?.setValue('resstock');
    component.onProductChanged(0);

    expect(component.rows.at(0).get('buildingType')?.value).toBe('');
  });

  it('switching back to ENERGY STAR mode clears product/buildingType and re-requires energyStarType', () => {
    const component = createComponent();
    component.setTypeSource('buildstock');
    component.rows.at(0).get('product')?.setValue('resstock');
    component.rows.at(0).get('buildingType')?.setValue('Single-Family Detached');

    component.setTypeSource('energy_star');

    const row = component.rows.at(0);
    expect(row.get('product')?.hasValidator(Validators.required)).toBe(false);
    expect(row.get('buildingType')?.hasValidator(Validators.required)).toBe(false);
    expect(row.get('buildingType')?.value).toBe('');
    expect(row.get('energyStarType')?.hasValidator(Validators.required)).toBe(true);
  });

  it('does nothing when setTypeSource() is called with the already-active source', () => {
    const component = createComponent();
    component.rows.at(0).get('energyStarType')?.setValue('Office');

    component.setTypeSource('energy_star');

    expect(component.rows.at(0).get('energyStarType')?.value).toBe('Office');
  });
});

describe('CompositeBuilderComponent state default', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    localStorage.removeItem('buildstock.builder.last-state');
    await TestBed.configureTestingModule({
      imports: [CompositeBuilderComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function createComponent(): CompositeBuilderComponent {
    const fixture = TestBed.createComponent(CompositeBuilderComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    for (const req of httpMock.match(() => true)) {
      if (req.request.url.includes('/locations/states')) {
        req.flush({ ok: true, product: 'comstock', states: [] });
      } else if (req.request.url.includes('/locations/counties')) {
        req.flush({ ok: true, product: 'comstock', state: 'DE', counties: [], note: '' });
      } else if (req.request.url.includes('/building-types')) {
        const product = req.request.params.get('product') ?? 'comstock';
        req.flush({ ok: true, product, building_types: [] });
      } else {
        req.flush([]);
      }
    }
    return component;
  }

  it('defaults the state field to "All" on a cold page load, even with a remembered state', () => {
    const preferences = TestBed.inject(BuilderPreferencesService);
    preferences.setLastState('DE');
    const router = TestBed.inject(Router);
    expect(router.navigated).toBe(false);

    const component = createComponent();

    expect(component.form.get('state')?.value).toBe('All');
  });

  it('defaults the state field to "All" when nothing has been remembered yet, even on a return visit', () => {
    const router = TestBed.inject(Router);
    router.navigated = true;

    const component = createComponent();

    expect(component.form.get('state')?.value).toBe('All');
  });

  it('prefills the last-remembered specific state when returning to the builder mid-session', () => {
    const preferences = TestBed.inject(BuilderPreferencesService);
    preferences.setLastState('CO');
    const router = TestBed.inject(Router);
    router.navigated = true;

    const component = createComponent();

    expect(component.form.get('state')?.value).toBe('CO');
  });

  it('remembers a newly-picked specific state, but not "All", for next time', () => {
    const component = createComponent();
    const preferences = TestBed.inject(BuilderPreferencesService);

    component.form.get('state')?.setValue('co');
    for (const req of httpMock.match((r) => r.url.includes('/locations/counties'))) {
      req.flush({ ok: true, product: 'comstock', state: 'CO', counties: [], note: '' });
    }
    expect(preferences.getLastState()).toBe('CO');

    component.form.get('state')?.setValue('All');
    expect(preferences.getLastState()).toBe('CO');
  });

  it('disables the county control when state is "All"', () => {
    const component = createComponent();

    expect(component.form.get('state')?.value).toBe('All');
    expect(component.form.get('countyName')?.disabled).toBe(true);

    component.form.get('state')?.setValue('DE');
    for (const req of httpMock.match((r) => r.url.includes('/locations/counties'))) {
      req.flush({ ok: true, product: 'comstock', state: 'DE', counties: [], note: '' });
    }

    expect(component.form.get('countyName')?.disabled).toBe(false);
  });
});

describe('CompositeBuilderComponent EUI percentile curve', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    localStorage.removeItem('buildstock.builder.last-state');
    await TestBed.configureTestingModule({
      imports: [CompositeBuilderComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function createComponent(): CompositeBuilderComponent {
    const fixture = TestBed.createComponent(CompositeBuilderComponent);
    const component = fixture.componentInstance;
    fixture.detectChanges();
    for (const req of httpMock.match(() => true)) {
      if (req.request.url.includes('/locations/states')) {
        req.flush({ ok: true, product: 'comstock', states: [] });
      } else if (req.request.url.includes('/locations/counties')) {
        req.flush({ ok: true, product: 'comstock', state: 'DE', counties: [], note: '' });
      } else if (req.request.url.includes('/building-types')) {
        const product = req.request.params.get('product') ?? 'comstock';
        req.flush({ ok: true, product, building_types: [] });
      } else {
        req.flush([]);
      }
    }
    return component;
  }

  function resolveAndFlush(component: CompositeBuilderComponent): void {
    component.resolve();
    const resolveReq = httpMock.expectOne((r) => r.url.includes('/composite/resolve'));
    resolveReq.flush({
      ok: true,
      components: [],
      resolvable: [{ product: 'comstock', building_type: 'SmallOffice', fraction: 1, label: 'Office' }],
      unmapped: [],
      total_fraction: 1,
      warnings: [],
    });

    const distributionReq = httpMock.expectOne((r) => r.url.includes('/composite/eui-distribution'));
    distributionReq.flush({
      ok: true,
      state: 'All',
      curve: [
        { percentile: 0, eui_kbtu_per_ft2: 20, density: 0.1 },
        { percentile: 50, eui_kbtu_per_ft2: 60, density: 1.0 },
        { percentile: 100, eui_kbtu_per_ft2: 150, density: 0.2 },
      ],
      mean_eui_kbtu_per_ft2: 65,
      median_eui_kbtu_per_ft2: 60,
      sample_size: 100,
      percentiles: [
        { label: '5th percentile', percentile: 5, eui_kbtu_per_ft2: 25, bldg_ids: { 'comstock:SmallOffice': 1 } },
        { label: 'Median (50th)', percentile: 50, eui_kbtu_per_ft2: 60, bldg_ids: { 'comstock:SmallOffice': 2 } },
        { label: '95th percentile', percentile: 95, eui_kbtu_per_ft2: 140, bldg_ids: { 'comstock:SmallOffice': 3 } },
      ],
      warnings: [],
    });

    // resolve() -> loadEuiDistribution() automatically calls selectPercentile(50) on success.
    const buildingsReq = httpMock.expectOne((r) => r.url.includes('/composite/eui-percentile-buildings'));
    buildingsReq.flush({
      ok: true,
      percentile: 50,
      components: [
        {
          product: 'comstock',
          building_type: 'SmallOffice',
          label: 'Office',
          selected_bldg_id: 42,
          candidates: [{ bldg_id: 42, eui_kbtu_per_ft2: 60, sqft: 5000, percentile_rank: 50 }],
        },
      ],
      warnings: [],
    });
  }

  it('automatically selects the median percentile once the distribution loads', () => {
    const component = createComponent();
    resolveAndFlush(component);

    expect(component.selectedPercentileValue()).toBe(50);
    expect(component.selectedPercentileBuildings()?.components[0].selected_bldg_id).toBe(42);
  });

  it('clicking a preset percentile button looks up that percentile\'s buildings', () => {
    const component = createComponent();
    resolveAndFlush(component);

    component.pickPresetPercentile(95);
    const req = httpMock.expectOne((r) => r.url.includes('/composite/eui-percentile-buildings'));
    expect(req.request.body.percentile).toBe(95);
    req.flush({
      ok: true,
      percentile: 95,
      components: [
        {
          product: 'comstock',
          building_type: 'SmallOffice',
          label: 'Office',
          selected_bldg_id: 99,
          candidates: [{ bldg_id: 99, eui_kbtu_per_ft2: 140, sqft: 5000, percentile_rank: 95 }],
        },
      ],
      warnings: [],
    });

    expect(component.selectedPercentileValue()).toBe(95);
    expect(component.selectedPercentileBuildings()?.components[0].selected_bldg_id).toBe(99);
  });

  it('continueToDashboard() pins the selected percentile\'s bldg_id onto the composite', () => {
    const component = createComponent();
    resolveAndFlush(component);
    const compositeState = TestBed.inject(CompositeStateService);

    component.continueToDashboard();

    expect(compositeState.components()[0].bldg_id).toBe(42);
  });
});
