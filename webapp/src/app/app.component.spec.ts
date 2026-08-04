import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { AppComponent } from './app.component';
import { ScenarioHistoryService } from './services/scenario-history.service';

describe('AppComponent', () => {
  beforeEach(async () => {
    // The scenario-history nav section persists to localStorage (see ScenarioHistoryService) -- start
    // each test from a clean slate so leftover scenarios from another spec/run don't add extra nav links.
    localStorage.removeItem('buildstock.scenario-history');

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [provideRouter([]), provideNoopAnimations()],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the left nav sidebar', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('mat-sidenav.app-sidenav')).toBeTruthy();
    expect(compiled.querySelector('.brand-title')?.textContent).toContain('BuildStock');
    expect(compiled.querySelector('.brand-subtitle')?.textContent).toContain('Composite Explorer');
    const navLinks = compiled.querySelectorAll('mat-nav-list a[mat-list-item]');
    expect(navLinks.length).toBe(4);
  });

  it('does not show a recent-scenarios section when none have been run', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.sidenav-section-header')).toBeNull();
  });

  it('lists recently-run scenarios in the left nav, most recent first', () => {
    const scenarioHistory = TestBed.inject(ScenarioHistoryService);
    scenarioHistory.add({
      label: 'SmallOffice — DE',
      measuresSummary: 'LED Lighting',
      state: 'DE',
      countyName: 'All',
      baselineUpgrade: '0',
      components: [],
      comparisonKeys: ['comstock:1'],
    });
    scenarioHistory.add({
      label: 'MediumOffice — CO',
      measuresSummary: 'Cool Roof',
      state: 'CO',
      countyName: 'All',
      baselineUpgrade: '0',
      components: [],
      comparisonKeys: ['comstock:2'],
    });

    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;

    expect(compiled.querySelector('.sidenav-section-header')).toBeTruthy();
    const scenarioLinks = compiled.querySelectorAll('a.scenario-item');
    expect(scenarioLinks.length).toBe(2);
    expect(scenarioLinks[0].textContent).toContain('MediumOffice — CO');
    expect(scenarioLinks[1].textContent).toContain('SmallOffice — DE');
  });

  it('caps the recent-scenarios list at 10, dropping the oldest', () => {
    const scenarioHistory = TestBed.inject(ScenarioHistoryService);
    for (let i = 0; i < 12; i++) {
      scenarioHistory.add({
        label: `Scenario ${i}`,
        measuresSummary: 'Some measure',
        state: 'DE',
        countyName: 'All',
        baselineUpgrade: '0',
        components: [],
        comparisonKeys: [`comstock:${i}`],
      });
    }

    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;

    const scenarioLinks = compiled.querySelectorAll('a.scenario-item');
    expect(scenarioLinks.length).toBe(10);
    // Most recent (11) first, oldest two (0, 1) dropped.
    expect(scenarioLinks[0].textContent).toContain('Scenario 11');
    expect(compiled.querySelector('.sidenav-nav')?.textContent).not.toContain('Scenario 0');
  });
});
