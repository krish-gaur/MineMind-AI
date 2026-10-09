# Repository audit and implementation plan

Audit date: 2026-10-09 (sandbox clock, UTC). Branch: `arena/9566b465-minemind-ai`, base `f5c1150` on `main`.

## 1. What the repository contained

| Area | Finding |
| --- | --- |
| Git history | One commit, "Initial commit". `main` and the working branch both contain only `README.md` (`# MineMind-AI`). |
| Application code | None. No frontend, no backend, no API routes, no models, no data files. |
| Dependencies | No `package.json`, `requirements*.txt`, `pyproject.toml` or lockfile. |
| Configuration | No environment variables, no `.env.example`, no CORS, no deployment files. |
| Tests / CI | None. |
| Documentation | README only. |
| Remote | Public repository `krish-gaur/MineMind-AI`, no description, default branch `main`. |

**Conclusion.** There was no existing working feature to preserve and nothing broken to repair. The
application was built from scratch inside the existing repository. No other copy of the project
exists on this machine (searched `/home/user` and the filesystem).

## 2. Environment and network constraints (verified in this sandbox)

* Toolchain: Node 22.22.3, npm 10.9.8, Python 3.11.2, git 2.39.5, gh 2.23.0. No Docker, no PostgreSQL, no system browser.
* Reachable: `registry.npmjs.org`, `pypi.org`, `github.com`, `api.github.com`.
* **Not reachable (connection failed):** Copernicus Data Space catalogue, Element 84 Earth Search, Open-Meteo
  (forecast and archive), OpenFreeMap tiles, the MapLibre demo style, Google Fonts, Nominatim, AWS S3 (Sentinel COGs).

**Consequences**

1. Live satellite and weather calls cannot be exercised from this sandbox. Their clients are tested with
   mocked HTTP transports, and every such feature shows an explicit "unavailable" state when the service is unreachable.
2. Map basemaps from third-party tile hosts cannot be loaded here. The map uses a bundled public-domain
   outline (Natural Earth via `world-atlas`) so it works offline; an online style is optional via env.
3. Google-hosted fonts are replaced by self-hosted `@fontsource` packages, so builds do not depend on Google.

## 3. Risks found during the audit and how they are handled

| Risk | Handling |
| --- | --- |
| No real MOIL data is available. | All production, geology and drilling data is **synthetic** and labelled SYNTHETIC on every surface, in exports and in reports. No boundaries, drilling results, reserves or accuracy figures are invented. |
| A "prospectivity" score could be mistaken for a reserve estimate. | Exploration output is an *index* over stated evidence classes, gated by evidence sufficiency, and always labelled "not a reserve estimate". |
| Rule-based scores presented as trained models. | Value types are explicit: `measured`, `forecast`, `probability`, `estimate`, `scenario`, `rule_based`, `index`. Policy thresholds are listed in `backend/app/domain/policy.py`. |
| Data leakage in forecasting. | Features at day *t* use only information up to *t-1*, plus the plan for *t*. Tests check this directly. Time-based split, no shuffling. |
| Upload abuse (size, type, path). | Size limit enforced while reading, `.csv` only, filenames reduced to a safe base name and never used as paths, dataset IDs validated against a strict pattern. |
| Stack traces leaking to clients. | Global handler returns the error envelope with a request id; traces are logged server-side only. |
| CORS misconfiguration on Vercel↔Render. | Origins come from `CORS_ORIGINS` (and an optional regex for previews). Default deployment uses a same-origin proxy, so no CORS is needed. |
| Ephemeral filesystem on Render. | Demo data is regenerated deterministically at startup. Uploads persist only if `DATA_DIR` is on a persistent disk (documented). |
| npm 10 peer-resolution crash with vitest 4 optional peers. | `.npmrc` sets `legacy-peer-deps=true`; the explicit dependency list is pinned. Verified with `npm ls`. |
| ESLint 10 incompatible with `eslint-plugin-react`/`-import`/`-jsx-a11y` peer ranges used by `eslint-config-next` 16.4. | ESLint pinned to 9.39.x (still supported by the plugins). |

## 4. Implementation plan (priority order)

| Priority | Item | Phase | Status at time of writing |
| --- | --- | --- | --- |
| P0 | Repo hygiene: `.gitignore`, audit document, layout | 0 | Done |
| P0 | Backend API foundation: config, errors, logging, health/readiness, CORS | 1 | Done, tested |
| P0 | Production CSV contract, validation, synthetic generator, dataset registry | 2 | Done, tested |
| P0 | Executive overview computed from data | 1 | Done, tested |
| P1 | Forecasting: baselines, leakage-safe features, time-based backtest, save/reload | 3 | In progress |
| P1 | Shortfall risk: classifier, expected net gap, transparent bands | 3 | Pending |
| P1 | Recommendations: rule-driven, evidence-backed, impact flagged as estimated or not estimated | 4 | Pending |
| P2 | MapLibre geospatial view, Sentinel-2 scene search and Open-Meteo rainfall (live calls mocked here) | 5 | Pending |
| P2 | Exploration zone ranking gated by evidence; drillhole demo with synthetic labels | 5 | Pending |
| P2 | Reports (HTML and JSON) distinguishing measured/forecast/estimate/synthetic | 6 | Pending |
| P3 | Deployment configs (Vercel, Render blueprint), CI workflow, runbooks, demo script | 6 | Pending |

Each row is verified by tests and by the lint, type and build commands recorded in `README.md`.
