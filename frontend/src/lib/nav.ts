export type NavItem = {
  href: string;
  label: string;
  description: string;
};

/** Pages that exist in this build. Keep in sync with src/app. */
export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Overview",
    description: "Plan, actual, constraints and freshness",
  },
  {
    href: "/forecast",
    label: "Forecast",
    description: "Backtest, baselines and forward output",
  },
  {
    href: "/risk",
    label: "Shortfall risk",
    description: "Expected gap, probability and risk band",
  },
  {
    href: "/recommendations",
    label: "Recommendations",
    description: "Evidence-backed actions and rules checked",
  },
  {
    href: "/data",
    label: "Data & sources",
    description: "Upload, validate and inspect datasets",
  },
];

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
