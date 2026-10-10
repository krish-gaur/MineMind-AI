# Repository audit and implementation record

Audit date: 2026-10-09 (sandbox clock, UTC). Branch `arena/9566b465-minemind-ai`, base commit `f5c1150` on `main`.

## 1. What the repository contained

| Area | Finding |
| --- | --- |
| Git history | One commit, "Initial commit". `main` and the working branch both contain only `README.md` (`# MineMind-AI`). |
| Application code | None. No frontend, no backend, no API routes, no models, no data files. |
| Dependencies | No `package.json`, `requirements*.txt`, `pyproject.toml` or lockfile. |
| Configuration | No environment variables, no `.env.example`, no CORS, no deployment files. |
| Tests and CI | None. |
| Documentation | README only. |
| Remote | Public repository `krish-gaur/MineMind-AI`, no description, default branch `main`. |

**Conclusion.** There was no working feature to preserve and nothing broken to repair. No other copy of the project exists on this machine (searched `/home/user` and the filesystem). The application was built from scratch inside the existing repository.

## 2. Environment and network constraints (verified in this sandbox)

* Toolchain: Node 22.22.3, npm 10.9.8, Python 3.11.2, git 2.39.5, gh 2.23.0. No Docker, no PostgreSQL, no system browser, no PowerShell.
* Reachable: `registry.npmjs.org`, `pypi.org`, `github.com`, `api.github.com`.
* **Not reachable (connection failed):** Copernicus Data Space catalogue, Element 84 Earth Search, Open-Meteo (forecast and archive), OpenFreeMap tiles, MapLibre demo style, Google Fonts, Nominatim, AWS S3 (Sentinel COGs).

**Consequences**

1. Live satellite and rainfall calls could not be exercised. Their clients are tested with mocked transports, and every such panel shows an explicit "unavailable" state. The recorded sample is in `docs/samples/satellite_unavailable_in_sandbox.json`.
2. Third-party map tiles could not be loaded. The map uses a bundled public-domain outline, so it works offline. An online style is optional through an environment variable.
3. Google-hosted fonts are replaced by `@fontsource` packages, so the build does not depend on Google.
4. A headless Chromium was installed from npm (`@sparticuz/chromium`) outside the repository, to take screenshots for visual review. It is not part of the project.

## 3. Risks found during the audit and how each was handled

| Risk | Handling |
| --- | --- |
| No MOIL data is available. | All production, geology, drillhole and boundary data is **synthetic**, fictional (`SYN-*`) and labelled SYNTHETIC on every screen, in every export and in every report. Nothing is presented as a reserve, resource, drilling result, satellite observation or measured accuracy. |
| A prospectivity score could be read as a reserve estimate. | Exploration output is an index over evidence classes, gated on sufficiency, and labelled as not a probability and not a reserve estimate. |
| Rule-based outputs presented as trained models. | Value types are explicit (`measured`, `forecast`, `probability`, `estimate`, `scenario`, `rule_based`, `index`). Thresholds live in `backend/app/domain/policy.py`. |
| Data leakage in forecasting. | Features for day *t* use only earlier information (plus the plan for *t*). Tests perturb targets, same-day values and future values, and check that features do not move. |
| Upload abuse (size, type, path). | Size enforced while reading; `.csv` and `.geojson`/`.json` only; filenames reduced to a safe base name and never used as paths; dataset ids matched against a strict pattern. |
| Stack traces reaching clients. | A global handler returns the error envelope with a request id. Traces are logged on the server only. |
| CORS misconfiguration between Vercel and Render. | Origins come from `CORS_ORIGINS`, plus an optional regex for previews. The default deployment uses a same-origin proxy, so CORS is not needed. |
| Ephemeral filesystem on Render. | Demo data is regenerated deterministically at startup. Uploads persist only on a persistent disk (documented). |
| npm 10 peer-resolution crash with vitest 4's optional peers. | `frontend/.npmrc` sets `legacy-peer-deps=true`; explicit dependencies are pinned. |
| ESLint 10 is incompatible with `eslint-plugin-react`, `-import` and `-jsx-a11y`, which `eslint-config-next` depends on. | ESLint is pinned to 9.39.x, which all of them support. |
| jsdom pulled in a native `canvas` optional peer that broke installs. | Tests use happy-dom instead. |
| Google Fonts unreachable during build. | `@fontsource` packages. |
| Map container collapsed to zero height. | MapLibre's own stylesheet sets `position: relative`, which overrode an absolute-positioned container. Fixed with a sized wrapper; verified in a browser. |
| Zones coloured by status never received their status. | The zone geometry carries no status; it is now copied from the exploration result before rendering. Verified in a browser. |
| "Recoverable output" wording overstated what the arithmetic shows. | Reworded to describe the gap and the uplift it implies. |
| YAML double-quote escaping turned `\.` into `\\.` in the CORS regex. | Single-quoted in `render.yaml`; regex checked against a preview host and a foreign host. |
| Recommendations' "as of" date moved back when actuals were missing, hiding the gap. | Windows end on the last day with any recorded value; freshness uses the last actual. Tested. |

## 4. Implementation record (phase by phase)

| Phase | Scope | Status | Evidence |
| --- | --- | --- | --- |
| 0 | Audit, plan, network probe, repository hygiene | Done | This document; `.gitignore`. |
| 1 | Backend foundation (config, errors, logs, health, readiness, CORS), executive overview, frontend shell | Done | Backend and frontend tests; overview screenshots. |
| 2 | Production CSV contract and validation, synthetic generator, dataset registry, data page | Done | Validation, synthetic and dataset API tests. |
| 3 | Forecasting (baselines, backtest, MAE/RMSE, bootstrap, save/reload), shortfall risk, classifier, forecast and risk pages | Done | Leakage, split, baseline, metric, persistence and API tests; page screenshots. |
| 4 | Recommendations (eight rules, evidence, impact labels, rules checked) and page | Done | Designed-data tests with exact arithmetic; page screenshot. |
| 5 | Geospatial (MapLibre, offline basemap), exploration index with gates, GeoJSON and drillhole ingestion, keyless Copernicus and Open-Meteo clients | Done, with live calls unverified here | Gating and ingestion tests; mocked-transport tests for every client outcome; map screenshot. |
| 6 | HTML and JSON reports, documentation, deployment files, CI workflow | Done | Report tests; the docs in this folder; `render.yaml`; `.github/workflows/ci.yml`. |

Each row is backed by commands and their real outputs in [`TEST_REPORT.md`](TEST_REPORT.md).

## 5. Decisions taken during the build

* **Gradient boosting is the forecast model; ridge is a benchmark.** The model was fixed before the backtest. On 7 of the 9 scopes ridge has lower backtest MAE. The verdict text says so, the forecast is not swapped, and the choice of default is flagged as open.
* **Material-shortfall target (below 95% of plan)** for the classifier. The strict "below plan" target was almost always true in the synthetic data (base rate around 99%), so its AUC was meaningless. The tolerance is policy and is shown in the UI.
* **Interval for the net gap** uses every backtest window of the same length, with at least 70% of days present, rather than only complete windows. Strict windows left none for the all-mines scope.
* **HTML reports are self-contained and printable; PDF is not implemented.** This keeps the dependency list small.
* **Shapely is used**, for geometry validity and area. GeoPandas and GDAL were rejected because of their binary weight on free hosting.
* **Python dependencies are pinned** exactly. Node dependencies come from a committed lockfile.

## 6. Post-build status of this audit

Nothing in this audit is left unfixed except the items listed as not verified or not implemented in `README.md` ("Limitations and incomplete features") and in `TEST_REPORT.md` ("What was not verified").
