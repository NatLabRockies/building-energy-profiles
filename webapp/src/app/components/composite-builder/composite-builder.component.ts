import { Component, OnInit, signal } from '@angular/core';
import { FormArray, FormBuilder, FormGroup, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common';

import { ApiService } from '../../services/api.service';
import { CompositeStateService } from '../../services/composite-state.service';
import { CompositeResolveResponse, EnergyStarTypeInfo } from '../../models/api.models';

/** Landing page: enter one ENERGY STAR building type, or a mix of several -- either as floor-area
 * percentages or as absolute square footage -- resolve them to real BuildStock building types via the
 * packaged crosswalk, then continue to the dashboard/time-series/measures pages (which all share the
 * resolved composite via CompositeStateService).
 */
@Component({
  selector: 'app-composite-builder',
  standalone: true,
  imports: [ReactiveFormsModule, CommonModule],
  templateUrl: './composite-builder.component.html',
  styleUrl: './composite-builder.component.scss',
})
export class CompositeBuilderComponent implements OnInit {
  energyStarTypes = signal<EnergyStarTypeInfo[]>([]);
  resolveResult = signal<CompositeResolveResponse | null>(null);
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  /** 'fraction': each row's amount is a floor-area percentage (must total 100%). 'sqft': each row's amount
   * is an absolute square footage (any total; results are scaled to represent a building of that exact
   * combined size instead of just a relative share). */
  mode = signal<'fraction' | 'sqft'>('fraction');

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
    private readonly router: Router,
  ) {
    this.form = this.fb.group({
      rows: this.fb.array([this.buildRow('Office', 100)]),
      state: ['DE', [Validators.required, Validators.pattern(/^[A-Za-z]{2}$/)]],
      countyName: ['All'],
    });
  }

  ngOnInit(): void {
    this.api.getEnergyStarTypes().subscribe({
      next: (types) => this.energyStarTypes.set(types),
      error: () => this.errorMessage.set('Failed to load the ENERGY STAR property type list from the API.'),
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
    this.form.get('state')!.valueChanges.subscribe((state: string) => {
      // A new state's previously-selected county almost certainly doesn't apply -- reset to "All" (always
      // a safe choice) before the new county list arrives.
      this.form.get('countyName')?.setValue('All', { emitEvent: false });
      this.loadCounties(state);
    });
  }

  private loadCounties(state: string): void {
    if (!state || state.length !== 2) {
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

  buildRow(energyStarType: string, amount: number): FormGroup {
    return this.fb.group({
      energyStarType: [energyStarType, Validators.required],
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

  addRow(): void {
    this.rows.push(this.buildRow('', 0));
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

  resolve(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.errorMessage.set(null);
    this.resolveResult.set(null);

    const sqftMode = this.mode() === 'sqft';
    const components = this.rows.controls.map((row) => {
      const amount = Number(row.get('amount')!.value);
      return {
        energy_star_property_type: row.get('energyStarType')!.value,
        ...(sqftMode ? { sqft: amount } : { fraction: amount / 100 }),
      };
    });

    this.api
      .resolveComposite({
        components,
        // Sent so sqft-mode resolution can auto-select a representative bldg_id per component (the real
        // sampled building closest in floor area to its sqft) -- see ResolvedComponent.bldg_id.
        state: this.form.get('state')!.value?.toUpperCase(),
        county_name: this.form.get('countyName')!.value || 'All',
      })
      .subscribe({
        next: (result) => {
          this.resolveResult.set(result);
          this.loading.set(false);
        },
        error: (err) => {
          this.errorMessage.set(err?.error?.error ?? 'Failed to resolve the composite building type.');
          this.loading.set(false);
        },
      });
  }

  continueToDashboard(): void {
    const result = this.resolveResult();
    if (!result || result.resolvable.length === 0) {
      return;
    }
    this.compositeState.setComposite(
      result.resolvable,
      this.form.get('state')!.value.toUpperCase(),
      this.form.get('countyName')!.value || 'All',
      '0', // Always baseline -- the builder page no longer exposes an upgrade/measure ID selector.
    );
    this.router.navigate(['/dashboard']);
  }
}
