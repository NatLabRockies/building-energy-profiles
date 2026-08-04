import { TestBed } from '@angular/core/testing';

import { BuilderPreferencesService } from './builder-preferences.service';

describe('BuilderPreferencesService', () => {
  let service: BuilderPreferencesService;

  beforeEach(() => {
    localStorage.removeItem('buildstock.builder.last-state');
    TestBed.configureTestingModule({});
    service = TestBed.inject(BuilderPreferencesService);
  });

  it('returns null when nothing has been remembered yet', () => {
    expect(service.getLastState()).toBeNull();
  });

  it('remembers a specific state and returns it uppercased', () => {
    service.setLastState('de');

    expect(service.getLastState()).toBe('DE');
  });

  it('persists across service instances (localStorage-backed)', () => {
    service.setLastState('CO');

    const otherInstance = TestBed.inject(BuilderPreferencesService);
    expect(otherInstance.getLastState()).toBe('CO');
  });

  it('does not remember "All" as a specific state', () => {
    service.setLastState('DE');
    service.setLastState('All');

    // "All" is never worth remembering as a "go back to my region" default -- the last *specific* state
    // (DE) should still be what's returned.
    expect(service.getLastState()).toBe('DE');
  });

  it('ignores an empty state', () => {
    service.setLastState('');

    expect(service.getLastState()).toBeNull();
  });
});
