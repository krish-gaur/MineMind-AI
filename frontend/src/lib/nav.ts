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
    href: "/data",
    label: "Data & sources",
    description: "Upload, validate and inspect datasets",
  },
];

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}
