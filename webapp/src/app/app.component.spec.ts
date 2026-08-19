import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { AppComponent } from './app.component';

describe('AppComponent', () => {
  beforeEach(async () => {
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
    expect(compiled.querySelector('.brand-title')?.textContent).toContain('Building Energy Profiles');
    expect(compiled.querySelector('.brand-subtitle')?.textContent).toContain('Composite Explorer');
    const navLinks = compiled.querySelectorAll('mat-nav-list a[mat-list-item]');
    expect(navLinks.length).toBe(5);
  });
});
