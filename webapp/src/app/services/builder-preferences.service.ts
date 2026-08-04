import { Injectable } from '@angular/core';

const LAST_STATE_KEY = 'buildstock.builder.last-state';

/** Remembers the last *specific* (non-"All") state the user picked in the composite builder, persisted to
 * localStorage so it survives a page reload.
 *
 * The builder itself always *defaults* to "All" (entire USA) on a cold page load/hard refresh -- but once
 * the user has run at least one scenario and returns to the builder to start a new composite (see
 * `confirmClearScenariosGuard`), it's far more likely they want to keep exploring their own region than
 * start back over at the entire country, so that return trip pre-fills whatever specific state was last
 * used instead.
 */
@Injectable({ providedIn: 'root' })
export class BuilderPreferencesService {
  /** The last specific (2-letter) state the user selected, or `null` if none has been picked yet (i.e.
   * every builder visit so far used "All" or this is a fresh browser/profile). Never stores "All" itself --
   * only a real state is worth remembering as a "go back to my region" default. */
  getLastState(): string | null {
    try {
      return localStorage.getItem(LAST_STATE_KEY);
    } catch {
      // Storage disabled (e.g. private browsing) -- behave as if nothing's been remembered yet.
      return null;
    }
  }

  setLastState(state: string): void {
    if (!state || state.toUpperCase() === 'ALL') {
      return;
    }
    try {
      localStorage.setItem(LAST_STATE_KEY, state.toUpperCase());
    } catch {
      // Quota exceeded/storage disabled -- silently skip persisting; the current session just won't
      // remember this pick for next time.
    }
  }
}
