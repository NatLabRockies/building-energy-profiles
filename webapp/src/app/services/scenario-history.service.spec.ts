import { TestBed } from '@angular/core/testing';

import { ScenarioHistoryService } from './scenario-history.service';
import { Scenario } from '../models/scenario.model';
import { MeasuresCompareResponse, TimeseriesResponse } from '../models/api.models';

const STORAGE_KEY = 'buildstock.scenario-history';

function makeScenario(overrides: Partial<Omit<Scenario, 'id' | 'createdAt'>> = {}): Omit<Scenario, 'id' | 'createdAt'> {
  return {
    label: 'SmallOffice — DE',
    measuresSummary: 'LED Lighting',
    state: 'DE',
    countyName: 'All',
    baselineUpgrade: '0',
    components: [],
    comparisonKeys: ['comstock:1'],
    ...overrides,
  };
}

function makeCompareResult(): MeasuresCompareResponse {
  return {
    ok: true,
    baseline_upgrade: '0',
    comparison_upgrades: ['comstock:1'],
    results: {},
    warnings: [],
    baseline_by_end_use: [],
    by_end_use: {},
  };
}

function makeTimeseries(): TimeseriesResponse {
  return {
    ok: true,
    state: 'DE',
    upgrade: '0',
    resample: 'hourly',
    columns: [],
    row_count: 0,
    series: [],
    component_labels: {},
    component_bldg_ids: {},
    warnings: [],
  };
}

describe('ScenarioHistoryService', () => {
  let service: ScenarioHistoryService;

  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY);
    TestBed.configureTestingModule({});
    service = TestBed.inject(ScenarioHistoryService);
  });

  it('add() returns the new scenario id and adds it to scenarios()', () => {
    const id = service.add(makeScenario());

    expect(service.scenarios().length).toBe(1);
    expect(service.scenarios()[0].id).toBe(id);
  });

  it('cacheResult()/getCachedResult() round-trip in memory for a given scenario id', () => {
    const id = service.add(makeScenario());
    const cached = { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} };

    service.cacheResult(id, cached);

    expect(service.getCachedResult(id)).toBe(cached);
  });

  it('getCachedResult() returns undefined when nothing has been cached for that id', () => {
    const id = service.add(makeScenario());

    expect(service.getCachedResult(id)).toBeUndefined();
  });

  it('recalling the same scenario id does not create a duplicate nav entry', () => {
    // Simulates the fixed flow: a scenario is added once, then "recalled" repeatedly by re-caching its
    // results onto the *same* id (never calling add() again) -- the count must stay at 1.
    const id = service.add(makeScenario());
    service.cacheResult(id, { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} });
    service.cacheResult(id, { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} });
    service.cacheResult(id, { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} });

    expect(service.scenarios().length).toBe(1);
  });

  it("remove() also drops that scenario's cached result", () => {
    const id = service.add(makeScenario());
    service.cacheResult(id, { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} });

    service.remove(id);

    expect(service.scenarios().length).toBe(0);
    expect(service.getCachedResult(id)).toBeUndefined();
  });

  it('clear() drops every scenario and every cached result', () => {
    const id1 = service.add(makeScenario({ label: 'A' }));
    const id2 = service.add(makeScenario({ label: 'B' }));
    service.cacheResult(id1, { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} });
    service.cacheResult(id2, { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} });

    service.clear();

    expect(service.scenarios().length).toBe(0);
    expect(service.getCachedResult(id1)).toBeUndefined();
    expect(service.getCachedResult(id2)).toBeUndefined();
  });

  it('evicts cached results for scenarios that fall off the capped list', () => {
    const firstId = service.add(makeScenario({ label: 'first' }));
    service.cacheResult(firstId, { compareResult: makeCompareResult(), baselineTimeseries: makeTimeseries(), measureTimeseries: {} });

    // Add 10 more (MAX_SCENARIOS = 10) so the first one gets pushed out of the capped, persisted list.
    for (let i = 0; i < 10; i++) {
      service.add(makeScenario({ label: `extra-${i}` }));
    }

    expect(service.scenarios().find((s) => s.id === firstId)).toBeUndefined();
    expect(service.getCachedResult(firstId)).toBeUndefined();
  });

  it('findById() finds a scenario by id', () => {
    const id = service.add(makeScenario({ label: 'findable' }));

    expect(service.findById(id)?.label).toBe('findable');
  });
});
