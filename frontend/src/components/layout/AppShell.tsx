"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { SourceBadge } from "@/components/ui/Badges";
import { useDatasets } from "@/lib/dataset-context";
import { isActivePath, NAV_ITEMS } from "@/lib/nav";
import { DatasetSwitcher } from "./DatasetSwitcher";

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-3 rounded focus-visible:outline-amber-500">
      <svg aria-hidden="true" width="28" height="28" viewBox="0 0 28 28" className="shrink-0">
        <polygon points="14,2 25,8 25,20 14,26 3,20 3,8" fill="none" stroke="#c98a1b" strokeWidth="2" />
        <circle cx="14" cy="14" r="4" fill="#c98a1b" />
      </svg>
      <div>
        <p className="text-[15px] font-semibold tracking-tight text-white">MineMind AI</p>
        <p className="text-[11px] uppercase tracking-[0.14em] text-forest-200/80">SIH26009 prototype</p>
      </div>
    </Link>
  );
}

function NavList({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <ul className="space-y-1">
      {NAV_ITEMS.map((item) => {
        const active = isActivePath(pathname, item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`block rounded-md px-3 py-2 transition-colors focus-visible:outline-amber-500 ${
                active ? "bg-forest-800 text-white" : "text-forest-200 hover:bg-forest-800/60 hover:text-white"
              }`}
            >
              <span className="block text-sm font-medium">{item.label}</span>
              <span className="mt-0.5 block text-xs text-forest-200/70">{item.description}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const { active } = useDatasets();

  return (
    <div className="min-h-screen lg:flex">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        Skip to content
      </a>

      <aside className="hidden w-64 shrink-0 flex-col bg-forest-900 px-4 py-6 text-white lg:flex lg:sticky lg:top-0 lg:h-screen">
        <Brand />
        <nav aria-label="Primary" className="mt-8">
          <NavList pathname={pathname} />
        </nav>
        <div className="mt-auto space-y-2 rounded-md border border-forest-800 bg-forest-950/40 p-3 text-xs text-forest-200/80">
          <p className="font-medium text-forest-100">Data labelling</p>
          <p>Synthetic, user-provided and public data are labelled on every screen. Forecasts and risk bands are not measurements.</p>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
          <div className="flex items-center gap-3 px-4 py-3 sm:px-6">
            <button
              type="button"
              className="rounded-md border border-line px-2.5 py-1.5 text-sm font-medium text-ink-900 lg:hidden"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? "Close" : "Menu"}
            </button>
            <Link href="/" className="font-semibold text-forest-900 lg:hidden">
              MineMind AI
            </Link>
            <div className="ml-auto flex min-w-0 items-center gap-3">
              <DatasetSwitcher />
              {active ? (
                <span className="hidden md:inline-flex">
                  <SourceBadge sourceType={active.source_type} />
                </span>
              ) : null}
            </div>
          </div>
          {menuOpen ? (
            <nav id="mobile-nav" aria-label="Primary mobile" className="border-t border-line bg-forest-900 p-3 lg:hidden">
              <NavList pathname={pathname} onNavigate={() => setMenuOpen(false)} />
            </nav>
          ) : null}
        </header>

        <main id="main" className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
