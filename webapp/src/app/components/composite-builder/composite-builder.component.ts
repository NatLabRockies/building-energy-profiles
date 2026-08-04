import { Component, OnInit, signal } from '@angular/core';
import { FormArray, FormBuilder, FormGroup, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common';
import { forkJoin } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { BuilderPreferencesService } from '../../services/builder-preferences.service';
import { PlotComponent, PlotData, PlotLayout } from '../plot/plot.component';
import { CompositeResolveResponse, EnergyStarTypeInfo, EuiDistributionResponse, EuiPercentileBuildingsResponse, Product } from '../../models/api.models';

/** "All" (entire USA) sentinel accepted by the backend for `state` -- kept as its own constant since it
 * must be sent/compared verbatim (not uppercased like a real 2-letter state abbreviation). */
const ALL_STATES = 'All';

/** Landing page: enter one building type, or a mix of several -- either as an ENERGY STAR Portfolio
 * Manager property type (resolved to a real BuildStock building type via the packaged crosswalk) or a
 * ComStock/ResStock building type directly -- and either as floor-area percentages or as absolute square
 * footage -- then continue to the dashboard/time-series/measures pages (which all share the resolved
 * composite via CompositeStateService).
 */
@Component({
  selector: 'app-composite-builder',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule, PlotComponent],
  templateUrl: './composite-builder.component.html',
  styleUrl: './composite-builder.component.scss',
})
export class CompositeBuilderComponent implements OnInit {
  energyStarTypes = signal<EnergyStarTypeInfo[]>([]);
  /** ComStock/ResStock building types, keyed by product, for the "ComStock/ResStock types" entry mode's
   * building-type dropdown (populated from whichever product a row's own selector is set to). */
  buildingTypesByProduct = signal<Record<Product, string[]>>({ comstock: [], resstock: [] });
  loadingBuildingTypes = signal(false);
  resolveResult = signal<CompositeResolveResponse | null>(null);
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  /** The composite's site EUI (kBtu/ft2) percentile curve, loaded once a composite resolves -- lets the
   * user click anywhere along the line to pick which real building(s) get carried through to the
   * dashboard/timeseries/measures pages, instead of an otherwise-arbitrary "first building found" pick.
   */
  euiDistribution = signal<EuiDistributionResponse | null>(null);
  loadingEuiDistribution = signal(false);
  euiDistributionError = signal<string | null>(null);
  /** The exact percentile (0-100) the user last clicked on the curve, if any. */
  selectedPercentileValue = signal<number | null>(null);
  /** The real nearby building(s) resolved for `selectedPercentileValue()` -- shown in a table under the
   * chart, and whose `selected_bldg_id` per component is pinned onto the composite before continuing. */
  selectedPercentileBuildings = signal<EuiPercentileBuildingsResponse | null>(null);
  loadingPercentileBuildings = signal(false);
  percentileBuildingsError = signal<string | null>(null);
  /** 'fraction': each row's amount is a floor-area percentage (must total 100%). 'sqft': each row's amount
   * is an absolute square footage (any total; results are scaled to represent a building of that exact
   * combined size instead of just a relative share). */
  mode = signal<'fraction' | 'sqft'>('fraction');
  /** 'energy_star' (default): each row picks an ENERGY STAR Portfolio Manager property type, resolved to a
   * BuildStock building type via the packaged crosswalk. 'buildstock': each row picks a ComStock/ResStock
   * building type directly instead, skipping the crosswalk entirely -- the two entry modes can't be mixed
   * within the same composite (see setTypeSource()). */
  typeSource = signal<'energy_star' | 'buildstock'>('energy_star');

  /** States with published BuildStock metadata (comstock/resstock cover the same 50 states + DC, so
   * "comstock" is used as the reference product for this list). */
  states = signal<string[]>([]);
  loadingStates = signal(false);
  /** Counties actually published for the selected state -- refetched whenever `state` changes. Not every
   * county in a state is guaranteed to have its own published sample, so "All" is always offered first as
   * a safe fallback regardless of what this list contains (see countiesNote). */
  counties = signal<string[]>([]);
  loadingCounties = signal(false);
  countiesNote = signal<string | null>(null);

  form: FormGroup;

  constructor(
    private readonly fb: FormBuilder,
    private readonly api: ApiService,
    private readonly compositeState: CompositeStateService,
    private readonly builderPreferences: BuilderPreferencesService,
    private readonly router: Router,
  ) {
    // Default to "All" (entire USA) on a cold page load/hard refresh -- but if the user is *returning* to
    // the builder from elsewhere in the app (e.g. after the confirm-clear-scenarios guard let them start a
    // new composite), `router.navigated` is already true, meaning at least one real in-app navigation has
    // happened this session -- in that case, prefill whichever specific state they last used instead, since
    // someone starting a new composite after exploring one region is far more likely to want to keep
    // exploring that same region than start back over at the whole country.
    const lastState = this.builderPreferences.getLastState();
    const initialState = this.router.navigated && lastState ? lastState : ALL_STATES;
    this.form = this.fb.group({
      rows: this.fb.array([this.buildRow(100, 'Office')]),
      state: [initialState, [Validators.required, Validators.pattern(/^([A-Za-z]{2}|All)$/)]],
      countyName: ['All'],
    });
  }

  ngOnInit(): void {
    this.api.getEnergyStarTypes().subscribe({
      next: (types) => this.energyStarTypes.set(types),
      error: () => this.errorMessage.set('Failed to load the ENERGY STAR property type list from the API.'),
    });

    this.loadingBuildingTypes.set(true);
    forkJoin({
      comstock: this.api.getBuildingTypes('comstock'),
      resstock: this.api.getBuildingTypes('resstock'),
    }).subscribe({
      next: (result) => {
        this.buildingTypesByProduct.set({
          comstock: result.comstock.building_types,
          resstock: result.resstock.building_types,
        });
        this.loadingBuildingTypes.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load the ComStock/ResStock building type list from the API.');
        this.loadingBuildingTypes.set(false);
      },
    });

    this.loadingStates.set(true);
    this.api.getAvailableStates('comstock').subscribe({
      next: (result) => {
        this.states.set(result.states);
        this.loadingStates.set(false);
      },
      error: () => {
        this.errorMessage.set('Failed to load the list of available states from the API.');
        this.loadingStates.set(false);
      },
    });

    this.loadCounties(this.form.get('state')!.value);
    this.updateCountyEnabled(this.form.get('state')!.value);
    this.form.get('state')!.valueChanges.subscribe((state: string) => {
      // A new state's previously-selected county almost certainly doesn't apply -- reset to "All" (always
      // a safe choice) before the new county list arrives.
      this.form.get('countyName')?.setValue('All', { emitEvent: false });
      this.loadCounties(state);
      this.updateCountyEnabled(state);
      // Remember this pick (a no-op if `state` is "All") so the *next* time the user returns to the
      // builder to start a new composite, it prefills this specific state instead of "All" again.
      this.builderPreferences.setLastState(state);
    });
  }

  /** Enable/disable the county control based on `state` -- done imperatively (rather than a template
   * `[disabled]` binding) per Angular's own guidance for reactive forms, so the control's `disabled`
   * status stays in sync with its FormControl state instead of just the rendered DOM attribute. */
  private updateCountyEnabled(state: string): void {
    const countyControl = this.form.get('countyName');
    if ((state ?? '').toUpperCase() === 'ALL') {
      countyControl?.disable({ emitEvent: false });
    } else {
      countyControl?.enable({ emitEvent: false });
    }
  }

  /** Whether the state field is currently set to the "All" (entire USA) sentinel -- county selection
   * doesn't make sense in that case (a single county can't scope "the entire USA"), so the template
   * disables the county dropdown while this is true. */
  get isAllStates(): boolean {
    return (this.form.get('state')!.value ?? '').toUpperCase() === 'ALL';
  }

  /** The state field's value normalized for sending to the API -- "All" verbatim (the backend's sentinel
   * for "entire USA"), or the entered state uppercased into a real 2-letter abbreviation. */
  private normalizedState(): string {
    const raw = (this.form.get('state')!.value ?? '') as string;
    return raw.toUpperCase() === 'ALL' ? ALL_STATES : raw.toUpperCase();
  }

  private loadCounties(state: string): void {
    if (!state || state.toUpperCase() === 'ALL' || state.length !== 2) {
      this.counties.set([]);
      this.countiesNote.set(null);
      return;
    }
    this.loadingCounties.set(true);
    this.api.getAvailableCounties('comstock', state.toUpperCase()).subscribe({
      next: (result) => {
        this.counties.set(result.counties);
        this.countiesNote.set(result.note);
        this.loadingCounties.set(false);
      },
      error: () => {
        this.counties.set([]);
        this.countiesNote.set(null);
        this.loadingCounties.set(false);
      },
    });
  }

  get rows(): FormArray {
    return this.form.get('rows') as FormArray;
  }

  /** Building types available for `product` in "ComStock/ResStock types" mode -- used by the template to
   * populate each row's building-type dropdown based on that row's own product selector. */
  buildingTypesFor(product: Product): string[] {
    return this.buildingTypesByProduct()[product] ?? [];
  }

  buildRow(amount: number, energyStarType = '', product: Product = 'comstock', buildingType = ''): FormGroup {
    const energyStarMode = this.typeSource() === 'energy_star';
    return this.fb.group({
      energyStarType: [energyStarType, energyStarMode ? [Validators.required] : []],
      product: [product, energyStarMode ? [] : [Validators.required]],
      buildingType: [buildingType, energyStarMode ? [] : [Validators.required]],
      amount: [amount, this.amountValidators()],
    });
  }

  private amountValidators(): ValidatorFn[] {
    return this.mode() === 'fraction'
      ? [Validators.required, Validators.min(0.01), Validators.max(100)]
      : [Validators.required, Validators.min(1)];
  }

  setMode(mode: 'fraction' | 'sqft'): void {
    if (this.mode() === mode) {
      return;
    }
    this.mode.set(mode);
    this.resolveResult.set(null);
    // Re-apply validators for the new mode's numeric range without clobbering entered amounts.
    for (const row of this.rows.controls) {
      row.get('amount')?.setValidators(this.amountValidators());
      row.get('amount')?.updateValueAndValidity();
    }
    if (mode === 'fraction') {
      // Whatever was left over from sqft mode is almost certainly not a valid percentage split -- clean
      // it up immediately so the boxes start back at a sensible 100% total.
      this.distributeRemainder(
        100,
        this.rows.controls.map((_, i) => i),
      );
    }
  }

  /** Switch between entering ENERGY STAR property types (resolved via the crosswalk) and entering
   * ComStock/ResStock building types directly -- the two can't be mixed within one composite (see
   * CompositeResolveRequest's "same type source" validation on the backend), so switching resets every
   * row's type selection (amounts/mode are left untouched) and re-applies the relevant controls'
   * required-ness.
   */
  setTypeSource(typeSource: 'energy_star' | 'buildstock'): void {
    if (this.typeSource() === typeSource) {
      return;
    }
    this.typeSource.set(typeSource);
    this.resolveResult.set(null);
    const energyStarMode = typeSource === 'energy_star';
    for (const row of this.rows.controls) {
      row.get('energyStarType')?.setValue('', { emitEvent: false });
      row.get('energyStarType')?.setValidators(energyStarMode ? [Validators.required] : []);
      row.get('energyStarType')?.updateValueAndValidity();

      row.get('product')?.setValue('comstock', { emitEvent: false });
      row.get('product')?.setValidators(energyStarMode ? [] : [Validators.required]);
      row.get('product')?.updateValueAndValidity();

      row.get('buildingType')?.setValue('', { emitEvent: false });
      row.get('buildingType')?.setValidators(energyStarMode ? [] : [Validators.required]);
      row.get('buildingType')?.updateValueAndValidity();
    }
  }

  /** Reset a row's building type when its product changes (ComStock/ResStock building types are disjoint
   * lists, so whatever was previously selected almost certainly doesn't exist for the new product). */
  onProductChanged(index: number): void {
    this.rows.controls[index].get('buildingType')?.setValue('');
  }

  addRow(): void {
    this.rows.push(this.buildRow(0));
    if (this.mode() === 'fraction') {
      const rows = this.rows.controls;
      const newIndex = rows.length - 1;
      const evenShare = this.clampPercent(100 / rows.length);
      rows[newIndex].get('amount')?.setValue(evenShare, { emitEvent: false });
      this.distributeRemainder(
        100 - evenShare,
        rows.map((_, i) => i).filter((i) => i !== newIndex),
      );
    }
  }

  removeRow(index: number): void {
    this.rows.removeAt(index);
    if (this.mode() === 'fraction' && this.rows.length > 0) {
      this.distributeRemainder(
        100,
        this.rows.controls.map((_, i) => i),
      );
    }
  }

  /** Called when a row's amount field loses focus (or its value is committed) in percentage mode --
   * proportionally rescales every OTHER row so the whole set still sums to exactly 100%, preserving their
   * relative shares to each other (e.g. edit row 1 to 50% while rows 2/3 were 30%/20% -> they become
   * 30%/20% rescaled to fit the remaining 50%, i.e. 30%/20%). Does nothing in sqft mode or with only one
   * row (nothing to redistribute against).
   */
  onAmountChanged(editedIndex: number): void {
    if (this.mode() !== 'fraction' || this.rows.length < 2) {
      return;
    }
    const rows = this.rows.controls;
    const edited = this.clampPercent(Number(rows[editedIndex].get('amount')?.value) || 0);
    rows[editedIndex].get('amount')?.setValue(edited, { emitEvent: false });
    this.distributeRemainder(
      100 - edited,
      rows.map((_, i) => i).filter((i) => i !== editedIndex),
    );
  }

  /** Proportionally scale the rows at `indices` so they sum to `remainder`, preserving their current
   * relative shares to each other (or splitting evenly if they currently sum to 0 -- e.g. freshly zeroed
   * rows). Any leftover rounding drift (rows are rounded to one decimal place) is nudged into whichever
   * of those rows currently has the largest share, so the displayed total lands on exactly 100%. */
  private distributeRemainder(remainder: number, indices: number[]): void {
    if (indices.length === 0) {
      return;
    }
    const rows = this.rows.controls;
    const currentTotal = indices.reduce((sum, i) => sum + (Number(rows[i].get('amount')?.value) || 0), 0);
    for (const i of indices) {
      const current = Number(rows[i].get('amount')?.value) || 0;
      const share = currentTotal > 0 ? current / currentTotal : 1 / indices.length;
      rows[i].get('amount')?.setValue(this.clampPercent(remainder * share), { emitEvent: false });
    }

    const total = rows.reduce((sum, row) => sum + (Number(row.get('amount')?.value) || 0), 0);
    const drift = Math.round((100 - total) * 10) / 10;
    if (drift !== 0) {
      const largest = [...indices].sort(
        (a, b) => (Number(rows[b].get('amount')?.value) || 0) - (Number(rows[a].get('amount')?.value) || 0),
      )[0];
      const current = Number(rows[largest].get('amount')?.value) || 0;
      rows[largest].get('amount')?.setValue(Math.max(0, this.clampPercent(current + drift)), { emitEvent: false });
    }
  }

  private clampPercent(value: number): number {
    return Math.round(Math.min(100, Math.max(0, value)) * 10) / 10;
  }

  get amountTotal(): number {
    return this.rows.controls.reduce((sum, row) => sum + (Number(row.get('amount')?.value) || 0), 0);
  }

  /** Exposes `Math.abs` to the template -- used to highlight whichever preset percentile button (if any)
   * matches the currently-selected percentile within a small tolerance. */
  abs(value: number): number {
    return Math.abs(value);
  }

  /** True for a ResStock component, whose sample sqft is one dwelling unit/home (not a whole arbitrary
   * building) -- used to word the scaling note appropriately in the candidates table. */
  isPerDwellingUnit(component: { product: Product }): boolean {
    return component.product === 'resstock';
  }

  resolve(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.errorMessage.set(null);
    this.resolveResult.set(null);
    this.euiDistribution.set(null);
    this.euiDistributionError.set(null);
    this.selectedPercentileValue.set(null);
    this.selectedPercentileBuildings.set(null);
    this.percentileBuildingsError.set(null);

    const sqftMode = this.mode() === 'sqft';
    const energyStarMode = this.typeSource() === 'energy_star';
    const components = this.rows.controls.map((row) => {
      const amount = Number(row.get('amount')!.value);
      const typeFields = energyStarMode
        ? { energy_star_property_type: row.get('energyStarType')!.value }
        : { product: row.get('product')!.value, building_type: row.get('buildingType')!.value };
      return {
        ...typeFields,
        ...(sqftMode ? { sqft: amount } : { fraction: amount / 100 }),
      };
    });

    this.api
      .resolveComposite({
        components,
        // Sent so sqft-mode resolution can auto-select a representative bldg_id per component (the real
        // sampled building closest in floor area to its sqft) -- see ResolvedComponent.bldg_id.
        state: this.normalizedState(),
        county_name: this.form.get('countyName')!.value || 'All',
      })
      .subscribe({
        next: (result) => {
          this.resolveResult.set(result);
          this.loading.set(false);
          if (result.resolvable.length > 0) {
            this.loadEuiDistribution(result);
          }
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to resolve the composite building type.');
          this.loading.set(false);
        },
      });
  }

  /** Load the composite's site EUI percentile curve once it resolves, so the user can see -- and click
   * anywhere along -- the actual spread of real sampled buildings this composite could represent, instead
   * of a single (previously arbitrary/"random"-seeming) representative building being silently chosen for
   * them downstream. */
  private loadEuiDistribution(result: CompositeResolveResponse): void {
    this.loadingEuiDistribution.set(true);
    this.euiDistributionError.set(null);
    this.api
      .getEuiDistribution({
        components: result.resolvable,
        state: this.normalizedState(),
        county_name: this.form.get('countyName')!.value || 'All',
      })
      .subscribe({
        next: (distribution) => {
          this.euiDistribution.set(distribution);
          this.loadingEuiDistribution.set(false);
          // Default to the median so a real building is already pinned even before the user clicks the
          // curve themselves.
          this.selectPercentile(50);
        },
        error: (err) => {
          this.euiDistributionError.set(err?.error?.error ?? 'Failed to load the site EUI distribution.');
          this.loadingEuiDistribution.set(false);
        },
      });
  }

  /** Plotly filled-area line chart of the composite's site EUI probability density curve (x = site EUI,
   * y = peak-normalized density 0-1) -- a true density shape, not a percentile-rank line. Each point still
   * carries its own `percentile`, used by `onEuiChartClick` to map an x-position click back to a
   * percentile even though the y-axis itself is density. */
  get euiChartData(): PlotData[] | null {
    const distribution = this.euiDistribution();
    if (!distribution) {
      return null;
    }
    return [
      {
        type: 'scatter',
        mode: 'lines',
        name: 'Composite site EUI density',
        x: distribution.curve.map((point) => point.eui_kbtu_per_ft2),
        y: distribution.curve.map((point) => point.density),
        line: { color: '#4a90d9', shape: 'spline' },
        fill: 'tozeroy',
        fillcolor: 'rgba(74, 144, 217, 0.15)',
        hovertemplate: '%{x:.1f} kBtu/ft2<br>Density: %{y:.2f}<extra></extra>',
        customdata: distribution.curve.map((point) => point.percentile),
      },
    ];
  }

  readonly euiChartLayout: Partial<PlotLayout> = {
    title: { text: 'Composite site EUI (kBtu/ft2) probability density -- click anywhere on the curve' },
    showlegend: false,
    xaxis: { title: { text: 'Site EUI (kBtu/ft2)' } },
    yaxis: { title: { text: 'Relative density' }, range: [0, 1] },
    margin: { t: 40 },
  };

  /** Handle a click anywhere on the EUI density curve (via `<app-plot>`'s `onPointClick`, which already
   * resolves the click to `(x, y)` data-coordinates) -- finds the nearest curve point to the clicked site
   * EUI to read off its percentile, then looks up the real nearby building(s) for that percentile. */
  onEuiChartClickHandler = (x: number, _y: number): void => {
    const curve = this.euiDistribution()?.curve;
    if (!curve || curve.length === 0) {
      return;
    }
    const nearest = curve.reduce((closest, point) =>
      Math.abs(point.eui_kbtu_per_ft2 - x) < Math.abs(closest.eui_kbtu_per_ft2 - x) ? point : closest,
    );
    this.selectPercentile(nearest.percentile);
  };

  /** Look up the real nearby building(s) for `percentile` per component, and pin the single closest one
   * per component onto the composite so the dashboard/timeseries/measures pages all use this exact choice
   * instead of each independently (and inconsistently) picking their own. */
  selectPercentile(percentile: number): void {
    const result = this.resolveResult();
    if (!result || result.resolvable.length === 0) {
      return;
    }
    this.selectedPercentileValue.set(percentile);
    this.loadingPercentileBuildings.set(true);
    this.percentileBuildingsError.set(null);
    this.api
      .getEuiPercentileBuildings({
        components: result.resolvable,
        state: this.normalizedState(),
        county_name: this.form.get('countyName')!.value || 'All',
        percentile,
      })
      .subscribe({
        next: (buildings) => {
          this.selectedPercentileBuildings.set(buildings);
          this.loadingPercentileBuildings.set(false);
        },
        error: (err) => {
          this.percentileBuildingsError.set(err?.error?.error ?? 'Failed to look up buildings near that percentile.');
          this.loadingPercentileBuildings.set(false);
        },
      });
  }

  /** Auto-pick one of the preset percentile buttons (5th/25th/median/average/75th/95th) -- same lookup as
   * clicking the curve directly, just at a fixed target instead of an arbitrary click position. */
  pickPresetPercentile(percentile: number): void {
    this.selectPercentile(percentile);
  }

  continueToDashboard(): void {
    const result = this.resolveResult();
    if (!result || result.resolvable.length === 0) {
      return;
    }
    const buildings = this.selectedPercentileBuildings();
    const resolvable = buildings
      ? result.resolvable.map((component) => {
          const match = buildings.components.find((c) => c.product === component.product && c.building_type === component.building_type);
          return match ? { ...component, bldg_id: match.selected_bldg_id } : component;
        })
      : result.resolvable;
    this.compositeState.setComposite(
      resolvable,
      this.normalizedState(),
      this.form.get('countyName')!.value || 'All',
      '0', // Always baseline -- the builder page no longer exposes an upgrade/measure ID selector.
    );
    this.router.navigate(['/dashboard']);
  }
}
