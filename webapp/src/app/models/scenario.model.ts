import { CompositeComponentSpec } from './api.models';

/** A saved "measures comparison" run for a composite -- everything needed to recall it (repopulate the
 * composite + baseline + selected measures and re-run the comparison) from the left nav, without the user
 * re-entering the composite builder or re-selecting measures from scratch. See ScenarioHistoryService.
 */
export interface Scenario {
  id: string;
  /** Short display label for the nav, e.g. "SmallOffice + MediumOffice — DE, Kent County". */
  label: string;
  /** Comma-separated measure names compared in this run, e.g. "LED Lighting, Cool Roof" -- shown as a
   * second line under `label` in the nav. */
  measuresSummary: string;
  createdAt: number;
  state: string;
  countyName: string;
  baselineUpgrade: string;
  components: CompositeComponentSpec[];
  /** The exact "<product>:<upgrade_id>" selection keys that were compared, so recalling this scenario
   * reselects the same measures instead of just the same composite. */
  comparisonKeys: string[];
}
