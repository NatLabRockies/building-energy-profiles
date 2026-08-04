import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { confirmClearScenariosGuard } from './confirm-clear-scenarios.guard';
import { ScenarioHistoryService } from '../services/scenario-history.service';

/** Tests for the composite builder route's confirm-before-clearing guard -- see the guard's own docstring
 * for the "skip on cold page load" rationale behind checking `router.navigated`. */
describe('confirmClearScenariosGuard', () => {
  let scenarioHistory: ScenarioHistoryService;
  let router: Router;
  let confirmSpy: jasmine.Spy;

  beforeEach(() => {
    localStorage.removeItem('buildstock.scenario-history');
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
    scenarioHistory = TestBed.inject(ScenarioHistoryService);
    router = TestBed.inject(Router);
    confirmSpy = spyOn(window, 'confirm');
  });

  function runGuard(): boolean {
    return TestBed.runInInjectionContext(() => confirmClearScenariosGuard({} as never, {} as never)) as boolean;
  }

  it('allows navigation without prompting on the initial page load, even with saved scenarios', () => {
    scenarioHistory.add({
      label: 'SmallOffice — DE',
      measuresSummary: 'LED Lighting',
      state: 'DE',
      countyName: 'All',
      baselineUpgrade: '0',
      components: [],
      comparisonKeys: ['comstock:1'],
    });
    expect(router.navigated).toBe(false);

    const result = runGuard();

    expect(result).toBe(true);
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(scenarioHistory.scenarios().length).toBe(1);
  });

  it('allows navigation without prompting when there are no saved scenarios', () => {
    router.navigated = true;

    const result = runGuard();

    expect(result).toBe(true);
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it('prompts and clears history when the user confirms', () => {
    router.navigated = true;
    scenarioHistory.add({
      label: 'SmallOffice — DE',
      measuresSummary: 'LED Lighting',
      state: 'DE',
      countyName: 'All',
      baselineUpgrade: '0',
      components: [],
      comparisonKeys: ['comstock:1'],
    });
    confirmSpy.and.returnValue(true);

    const result = runGuard();

    expect(confirmSpy).toHaveBeenCalled();
    expect(result).toBe(true);
    expect(scenarioHistory.scenarios().length).toBe(0);
  });

  it('blocks navigation and keeps history when the user declines', () => {
    router.navigated = true;
    scenarioHistory.add({
      label: 'SmallOffice — DE',
      measuresSummary: 'LED Lighting',
      state: 'DE',
      countyName: 'All',
      baselineUpgrade: '0',
      components: [],
      comparisonKeys: ['comstock:1'],
    });
    confirmSpy.and.returnValue(false);

    const result = runGuard();

    expect(result).toBe(false);
    expect(scenarioHistory.scenarios().length).toBe(1);
  });
});
