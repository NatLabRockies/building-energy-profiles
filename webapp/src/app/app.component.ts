import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { Component, inject, ViewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatSidenav, MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { map } from 'rxjs/operators';

interface NavItem {
  path: string;
  label: string;
  /** Material Icons (classic ligature font, self-hosted via the `material-icons` package) icon name. */
  icon: string;
  exact?: boolean;
}

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatSidenavModule,
    MatToolbarModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  private readonly breakpointObserver = inject(BreakpointObserver);
  private readonly router = inject(Router);

  title = 'BuildStock Composite Building Explorer';

  // Left-nav items, in display order.
  readonly navItems: NavItem[] = [
    { path: '/', label: 'Builder', icon: 'dashboard_customize', exact: true },
    { path: '/dashboard', label: 'Dashboard', icon: 'space_dashboard' },
    { path: '/timeseries', label: 'Time Series', icon: 'show_chart' },
    { path: '/measures', label: 'Measures', icon: 'checklist' },
  ];

  /** True on phone-sized viewports (CDK's standard "Handset" breakpoint query) -- drives the
   * sidenav between a permanent side panel (desktop/tablet) and an over-content drawer (mobile). */
  readonly isHandset = toSignal(
    this.breakpointObserver.observe(Breakpoints.Handset).pipe(map((state) => state.matches)),
    { initialValue: false },
  );

  @ViewChild('sidenav') private sidenav?: MatSidenav;

  constructor() {
    // Auto-close the mobile drawer after navigating (e.g. tapping a nav link), so it doesn't stay
    // open over the newly-loaded page.
    this.router.events.pipe(filter((event) => event instanceof NavigationEnd)).subscribe(() => {
      if (this.isHandset()) {
        this.sidenav?.close();
      }
    });
  }
}
