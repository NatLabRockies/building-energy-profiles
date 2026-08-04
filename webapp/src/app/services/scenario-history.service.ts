import { Injectable, signal } from '@angular/core';
import { MeasuresCompareResponse, TimeseriesResponse } from '../models/api.models';
import { Scenario } from '../models/scenario.model';

const STORAGE_KEY = 'buildstock.scenario-history';
const MAX_SCENARIOS = 10;

/** Everything a scenario needs to redisplay its results without re-downloading them -- held only in
 * memory (see `ScenarioHistoryService`'s own docstring for why this can't be persisted to localStorage
 * alongside the rest of `Scenario`). */
export interface ScenarioResultCache {
  compareResult: MeasuresCompareResponse;
  baselineTimeseries: TimeseriesResponse;
  measureTimeseries: Record<string, TimeseriesResponse>;
}

/** Recently-run "measures comparison" scenarios, shown in the left nav so a user can jump straight back
 * into a prior comparison (composite + baseline + selected measures) without re-building it. Persisted to
 * localStorage so the list survives a page reload, capped at the 10 most recent (oldest dropped first).
 *
 * Scenarios only make sense for the composite they were run against -- see `clear()`, called by the
 * composite builder whenever it's (re)entered, since navigating back there to define a new/different
 * composite invalidates whatever was previously recalled here.
 *
 * Each scenario's actual downloaded/computed *results* (the full compare() response + baseline/measure
 * time series -- easily several hundred KB to a few MB apiece) are cached separately, in memory only (see
 * `resultCache`/`cacheResult()`/`getCachedResult()`) -- NOT persisted to localStorage alongside the rest of
 * `Scenario`, since that would risk blowing past localStorage's ~5-10MB quota after just a couple of
 * scenarios. This means recalling a scenario avoids re-downloading its data (and, since compare() only
 * saves a *new* scenario on an actual API call, avoids duplicating this nav entry) for as long as the
 * current browser tab stays open, but a scenario recalled after a full page reload will need one real
 * re-compare to repopulate this cache -- an acceptable trade-off for avoiding a much worse UX (storage
 * quota errors silently breaking the whole "recent scenarios" feature).
 */
@Injectable({ providedIn: 'root' })
export class ScenarioHistoryService {
  readonly scenarios = signal<Scenario[]>(this.readStorage());

  /** In-memory-only cache of each scenario's actual results, keyed by scenario id -- see class docstring. */
  private readonly resultCache = new Map<string, ScenarioResultCache>();

  /** Add a newly-run scenario to the front of the list (most recent first), trimming to MAX_SCENARIOS. */
  add(scenario: Omit<Scenario, 'id' | 'createdAt'>): string {
    const id = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const entry: Scenario = { ...scenario, id, createdAt: Date.now() };
    const updated = [entry, ...this.scenarios()].slice(0, MAX_SCENARIOS);
    // Drop any cached results for scenarios that just fell off the end of the capped list, so the cache
    // doesn't grow unbounded past what's actually still shown in the nav.
    const keptIds = new Set(updated.map((s) => s.id));
    for (const cachedId of this.resultCache.keys()) {
      if (!keptIds.has(cachedId)) {
        this.resultCache.delete(cachedId);
      }
    }
    this.writeStorage(updated);
    return id;
  }

  /** Cache `result` in memory for `id` so `getCachedResult(id)` can restore it without re-downloading --
   * call once a scenario's full comparison (compare() + its detail time series) actually finishes. */
  cacheResult(id: string, result: ScenarioResultCache): void {
    this.resultCache.set(id, result);
  }

  getCachedResult(id: string): ScenarioResultCache | undefined {
    return this.resultCache.get(id);
  }

  remove(id: string): void {
    this.resultCache.delete(id);
    this.writeStorage(this.scenarios().filter((s) => s.id !== id));
  }

  /** Drop every saved scenario -- called when the composite builder is (re)entered, since a new/edited
   * composite there makes any previously-recalled scenario's inputs stale. */
  clear(): void {
    this.resultCache.clear();
    this.writeStorage([]);
  }

  findById(id: string): Scenario | undefined {
    return this.scenarios().find((s) => s.id === id);
  }

  private readStorage(): Scenario[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as Scenario[]) : [];
    } catch {
      // Corrupt JSON, storage disabled (e.g. private browsing), etc. -- fall back to an empty history
      // rather than breaking the app.
      return [];
    }
  }

  private writeStorage(scenarios: Scenario[]): void {
    this.scenarios.set(scenarios);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(scenarios));
    } catch {
      // Quota exceeded/storage disabled -- the in-memory signal above still reflects the update for the
      // current session even if it can't be persisted.
    }
  }
}
