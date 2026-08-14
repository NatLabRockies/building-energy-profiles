import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { CompositeBuilderComponent } from './composite-builder.component';

/** Tests for the fraction-mode auto-rebalancing logic added to the Composite Builder: editing one row's
 * percentage, or adding/removing a row, should automatically rescale the other rows so the whole set keeps
 * summing to exactly 100% (preserving their relative shares to each other), without fighting the user
 * while sqft mode is active (where totals are informational only). */
describe('CompositeBuilderComponent', () => {
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
    // ngOnInit fires 3 requests (ENERGY STAR types, available states, available counties for the default
    // state) -- irrelevant to the rebalancing logic under test, so just flush each with an empty/minimal
    // response matching its endpoint.
    for (const req of httpMock.match(() => true)) {
      if (req.request.url.includes('/locations/states')) {
        req.flush({ ok: true, product: 'comstock', states: [] });
      } else if (req.request.url.includes('/locations/counties')) {
        req.flush({ ok: true, product: 'comstock', state: 'DE', counties: [], note: '' });
      } else {
        req.flush([]);
      }
    }
    return component;
  }

  function amounts(component: CompositeBuilderComponent): number[] {
    return component.rows.controls.map((row) => Number(row.get('amount')?.value));
  }

  /** Force the component into a known single-row state for a given mode/amount -- the rebalancing tests
   * below are about the rebalancing *logic*, not about whatever the production default composite happens
   * to be (a 10,000 sqft office + 50,000 sqft multifamily, see the dedicated "default composite" test),
   * so they set up their own starting point rather than relying on it. Manipulates the FormArray/mode
   * signal directly (bypassing removeRow()/setMode()'s own rebalancing side effects) for a clean slate. */
  function resetToSingleRow(component: CompositeBuilderComponent, mode: 'fraction' | 'sqft', amount: number): void {
    while (component.rows.length > 1) {
      component.rows.removeAt(component.rows.length - 1);
    }
    component.mode.set(mode);
    component.rows.at(0).get('amount')?.setValue(amount);
  }

  it('defaults to a 10,000 sqft office + 50,000 sqft multifamily composite in Colorado', () => {
    const component = createComponent();

    expect(component.mode()).toBe('sqft');
    expect(component.rows.at(0).get('energyStarType')?.value).toBe('Office');
    expect(component.rows.at(1).get('energyStarType')?.value).toBe('Multifamily Housing');
    expect(amounts(component)).toEqual([10_000, 50_000]);
    expect(component.form.get('state')?.value).toBe('CO');
  });

  it('starts with a single row at 100% (fraction mode)', () => {
    const component = createComponent();
    resetToSingleRow(component, 'fraction', 100);
    expect(amounts(component)).toEqual([100]);
    expect(component.amountTotal).toBe(100);
  });

  it('addRow() splits the total evenly and keeps the sum at 100%', () => {
    const component = createComponent();
    resetToSingleRow(component, 'fraction', 100);
    component.addRow();
    expect(amounts(component)).toEqual([50, 50]);
    expect(component.amountTotal).toBe(100);
  });

  it('addRow() a third time preserves the existing rows relative shares', () => {
    const component = createComponent();
    resetToSingleRow(component, 'fraction', 100);
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
    resetToSingleRow(component, 'fraction', 100);
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
    resetToSingleRow(component, 'fraction', 100);
    component.addRow();
    component.removeRow(1);
    expect(amounts(component)).toEqual([100]);
  });

  it('onAmountChanged() rescales the other rows proportionally to keep the total at 100%', () => {
    const component = createComponent();
    resetToSingleRow(component, 'fraction', 100);
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
    resetToSingleRow(component, 'fraction', 100);
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
    resetToSingleRow(component, 'fraction', 100);
    component.addRow();
    component.rows.at(0).get('amount')?.setValue(150);
    component.onAmountChanged(0);

    const [a, b] = amounts(component);
    expect(a).toBe(100);
    expect(b).toBe(0);
  });

  it('does not rebalance in sqft mode', () => {
    const component = createComponent();
    resetToSingleRow(component, 'sqft', 100_000);
    component.addRow();
    component.rows.at(0).get('amount')?.setValue(40_000);
    component.onAmountChanged(0);
    component.rows.at(1).get('amount')?.setValue(20_000);
    component.onAmountChanged(1);

    expect(amounts(component)).toEqual([40_000, 20_000]);
  });

  it('normalizes leftover sqft-mode values proportionally when switching back to fraction mode', () => {
    const component = createComponent();
    resetToSingleRow(component, 'sqft', 100_000);
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
