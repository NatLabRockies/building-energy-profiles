import { Injectable, signal } from '@angular/core';
import { CompositeComponentSpec } from '../models/api.models';

/** Holds the resolved composite building spec + query parameters shared across every page (builder ->
 * dashboard -> time series -> measures -> export), so the user only enters it once. */
@Injectable({ providedIn: 'root' })
export class CompositeStateService {
  readonly components = signal<CompositeComponentSpec[]>([]);
  readonly state = signal<string>('CO');
  readonly countyName = signal<string>('All');
  readonly upgrade = signal<string>('0');

  setComposite(components: CompositeComponentSpec[], state: string, countyName: string, upgrade: string): void {
    this.components.set(components);
    this.state.set(state);
    this.countyName.set(countyName);
    this.upgrade.set(upgrade);
  }

  hasComposite(): boolean {
    return this.components().length > 0 && this.state().length === 2;
  }
}
