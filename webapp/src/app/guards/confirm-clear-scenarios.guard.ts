import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { ScenarioHistoryService } from '../services/scenario-history.service';

/** Guards the composite builder route ('') -- if the user has any recent scenarios saved (left nav) and
 * is navigating there from somewhere else in the app (not the initial page load), confirms that starting
 * over will clear them before allowing the navigation through. Declining keeps the user on their current
 * page and leaves the scenario history untouched.
 *
 * Scoped to actual in-app navigation (`router.navigated` is only true once at least one navigation has
 * already completed) so a fresh page load/reload landing on '/' with a still-persisted history from an
 * earlier session doesn't immediately interrupt the user with a confirmation they didn't ask for.
 */
export const confirmClearScenariosGuard: CanActivateFn = () => {
  const router = inject(Router);
  const scenarioHistory = inject(ScenarioHistoryService);

  if (!router.navigated) {
    return true;
  }

  const scenarios = scenarioHistory.scenarios();
  if (scenarios.length === 0) {
    return true;
  }

  const confirmed = window.confirm(
    `Starting a new composite will clear your ${scenarios.length} recent scenario${scenarios.length > 1 ? 's' : ''}. Continue?`,
  );
  if (confirmed) {
    scenarioHistory.clear();
  }
  return confirmed;
};
