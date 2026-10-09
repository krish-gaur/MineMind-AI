# Test and verification report

Build date: 2026-10-09 (sandbox clock, UTC). Branch `arena/9566b465-minemind-ai`. Every result below was produced by the command shown, in this sandbox, on the code as committed. Nothing here is a claim that a check passed without being run.

**Environment.** Debian 12 (Linux x86_64), 2 CPUs, 3.8 GiB RAM. Python 3.11.2 with a virtual environment at `backend/.venv`. Node 22.22.3, npm 10.9.8. HeadlessChrome 153.0.8010.0 (from `@sparticuz/chromium` 153.0.0, installed outside the repository) for browser checks.

## 1. Results at a glance

| Gate | Command | Result |
| --- | --- | --- |
| Backend lint | `python -m ruff check .` | **All checks passed** |
| Backend format | `python -m ruff format --check .` | **62 files already formatted** |
| Backend types | `python -m mypy app` | **Success: no issues found in 49 source files** |
| Backend tests | `python -m pytest -q` | **132 passed** (12 test modules, 32 s) |
| Frontend lint | `npm run lint` (`eslint . --max-warnings=0`) | **exit 0** |
| Frontend types | `npm run typecheck` (`tsc --noEmit`) | **exit 0** |
| Frontend tests | `npm run test` (Vitest, happy-dom) | **25 passed** (6 files) |
| Frontend build | `npm run build` (`next build`) | **Compiled; 9 routes prerendered**, exit 0 |
| Clean install | `npm ci` from the committed lockfile | **added 512 packages**, exit 0 |
| Runtime-only install | `pip install -r requirements.txt` in a fresh venv, then start the app | **imports OK; health ok; readiness `ready`; a forecast trains from an empty data directory** |
| Browser smoke | headless Chromium loads every page | **0 console or page errors on `/`, `/forecast`, `/risk`, `/recommendations`, `/map`, `/exploration`, `/reports`, `/data`** |
| API samples | requests against the running service | **12 responses recorded** in `docs/samples/` (one upload created, then deleted) |

## 2. Backend tests by module

| Module | Tests | What it covers |
| --- | ---: | --- |
| `test_validation.py` | 20 | Production CSV contract: required and unknown columns, header normalisation, row-level errors with line numbers, blank plan (blocking), blank actual (pending, not imputed), duplicates, date gaps, IQR outliers kept, BOM and CRLF, quoted fields, row limits, encoding and empty-file errors |
| `test_synthetic.py` | 7 | Byte-identical regeneration (SHA-256), identifiers are synthetic, plan present everywhere, pending days have no actuals, gaps not zero-filled, generated file passes the validator, provenance labelled SYNTHETIC |
| `test_datasets_api.py` | 12 | Listing and provenance, preview with nulls, valid and invalid uploads (422 stores nothing), extension and size limits (415, 413), path traversal in filenames, unsafe dataset ids (404), synthetic not deletable (403), schema and export |
| `test_overview.py` | 11 | Exact KPI arithmetic on matched days, sign conventions, constraint shares, filters, empty selections, freshness, API matches an independent recomputation from the stored CSV, user upload |
| `test_api_core.py` | 9 | Health and readiness, CORS allowed and denied origins (including on error responses), error envelope, request ids, safe 500 with no internals, sources registry |
| `test_features.py` | 6 | **Leakage**: features for day *t* unchanged when day *t*'s target or operations change, and unchanged when later days change; exact lag and rolling definitions; strict aggregation on partial days |
| `test_forecasting.py` | 14 | Fold windows contiguous, training only before each test window, baselines equal their definitions, MAE and RMSE by hand, reported MAE recomputed, bootstrap deterministic and zero for equal errors, detects a clearly better model, classifier agrees with sklearn, insufficient-data error with details, save and reload give identical predictions, non-model files refused, forward forecast uses plan and documents scenario, truncation where plan is missing, classifier target |
| `test_forecast_api.py` | 9 | Endpoints, model source (trained, memory, loaded after restart), risk equals forecast totals, scope validation, horizon bounds, insufficient data for a small upload, **changed data invalidates the saved model**, unknown dataset ids |
| `test_risk.py` | 10 | Band boundaries (−5, −2), rule-based labelling, classifier verdict branches |
| `test_recommendations.py` | 9 | Designed data: exact estimated impact (2,660 t from 190 t/day × 14 heavy days), zone concentration, clean data fires nothing and says so, freshness threshold, missing-actuals rule, blasting weekday, forecast rules use the risk output, no-actuals case, endpoint evidence |
| `test_geo_exploration.py` | 20 | Polygon area against hand calculation, zones with drilling ranked, context indices never scored, one-class zones unranked, ranking disabled with too few zones, missing inputs listed not imputed, demo gating, GeoJSON upload keeps valid features and reports invalid ones, drillhole ranges and columns, layers labelled synthetic, satellite and rainfall outcomes (live, cached, timeout, HTTP 503, bad JSON, disabled, missing days kept missing, input validation), disk cache keyed by request |
| `test_reports.py` | 5 | Synthetic notice and value-type legend present, user text escaped (`<script>` rendered inert), only requested sections, JSON labels, invalid sections and formats rejected |

Mocked transports are used for every public-service test. The sandbox cannot reach those services, so no live call is claimed.

## 3. Frontend tests

| File | Tests | What it covers |
| --- | ---: | --- |
| `lib/format.test.ts` | 6 | Number, tonne, percent and date formatting; true minus sign; `n/a` for missing values instead of invented numbers |
| `lib/api.test.ts` | 5 | Query building, backend error envelope mapped to `ApiError` without internals, non-JSON errors, network failure as "backend unreachable", success parsing |
| `components/ui/States.test.tsx` | 3 | Plain-language error mapping, request reference shown, retry calls back |
| `components/data/SyntheticBanner.test.tsx` | 2 | Synthetic warning text, source badges |
| `app/__tests__/overview.test.tsx` | 3 | KPIs rendered from the API response, synthetic warning shown, failed request shows a retryable error and no numbers, changing selection does not show old figures |
| `app/__tests__/analysis-pages.test.tsx` | 6 | Risk band rendered with the rule and estimate labels, recommendations separate estimated from not-estimated impacts and list rules checked, empty recommendations state, map zone list and evidence selection (map library mocked), synthetic banner on the map, report submission posts the selected sections |

## 4. Browser verification

Headless Chromium (Linux) against the production build (`next start`) with the API on port 8000, the `/api` rewrite active.

* **Pages**: all eight routes load with no console or page errors. Screenshots were reviewed at 1440 px for every page, and the overview was reviewed at 390 px (phone width). Other pages were not reviewed at phone width.
* **Defects found in review and fixed before this report**:
  * The map container had zero height because MapLibre's stylesheet overrode an absolute-positioned container. Fixed with a sized wrapper and verified by reading the container's rendered height (618 px) and the canvas size.
  * Zones were all drawn in one colour because the zone geometry carries no evidence status. Fixed by copying the status from the exploration result. Verified visually: observed zones green, the inferred zone amber with a dashed outline, the unmapped zone grey.
  * KPI tonnage values wrapped onto two lines. Fixed with non-wrapping values.
  * The synthetic warning was repeated on the overview. Removed the repeat.
  * Zone IDs wrapped mid-token in the exploration table. Fixed.
  * The exploration banner repeated its own prefix. Fixed.
  * Drillhole and zone datasets showed "n/a to n/a" for dates. Now shows "Not dated".
  * The brand name wrapped in the phone header. Fixed.
  * Recommendation wording overstated "recoverable output". Reworded to describe the gap and the uplift it implies.

## 5. Synthetic backtest results (final code, saved models)

These are the numbers the product shows for the synthetic demonstration data. They describe how the method behaves on data designed by the generator. **They are not evidence of real-world forecasting performance.**

Read the table with these points in mind:

* Gradient boosting is the pre-specified forecast model. **On 7 of the 9 scopes the ridge benchmark has lower MAE than gradient boosting** (all exceptions are Zone SYN-A-Z2 and Zone SYN-B-W, where gradient boosting is marginally better). The product reports this on the affected pages and does not switch models after the fact. Whether to make ridge the default is an open decision; if taken, it needs a holdout period that was not used to choose it.
* SYN-C and SYN-C-C1 rows are identical because mine SYN-C has a single zone.
* "Gap to best baseline" is the mean difference in absolute error against the lowest-MAE baseline, with a 95% moving-block bootstrap interval. Negative means the model has lower error.
* The classifier target is a *material shortfall day* (actual below 95% of plan).

| Scope | Eval days | Gradient boosting MAE (t/day) | Ridge MAE | Best baseline (MAE) | Gap to best baseline, 95% interval (t/day) | Verdict | Classifier AUC | Brier skill | Expected net gap (%) | Band |
|---|---:|---:|---:|---|---|---|---:|---:|---:|---|
| All mines and zones | 224 | 201.1 | 184.5 | seasonal_naive_7 (293.7) | -92.6 [-140.8, -42.4] | beats_best_baseline | 0.738 | 2.9% | -10.81 | High |
| Mine SYN-A (all zones) | 249 | 113.7 | 109.4 | seasonal_naive_7 (187.5) | -73.8 [-102.4, -44.0] | beats_best_baseline | 0.832 | 15.7% | -11.15 | High |
| Mine SYN-B (all zones) | 250 | 98.4 | 89.5 | seasonal_naive_7 (127.4) | -29.0 [-45.8, -14.2] | beats_best_baseline | 0.747 | 15.4% | -9.16 | High |
| Mine SYN-C (all zones) | 264 | 26.7 | 25.0 | seasonal_naive_7 (40.4) | -13.7 [-18.6, -9.6] | beats_best_baseline | 0.748 | 15.4% | -2.85 | Medium |
| Zone SYN-A-Z1 | 261 | 86.8 | 77.6 | seasonal_naive_7 (120.9) | -34.1 [-49.6, -19.1] | beats_best_baseline | 0.701 | 7.7% | -7.19 | High |
| Zone SYN-A-Z2 | 258 | 46.6 | 46.7 | seasonal_naive_7 (87.9) | -41.3 [-53.2, -26.6] | beats_best_baseline | 0.836 | 11.9% | -23.82 | High |
| Zone SYN-B-E | 267 | 65.8 | 59.2 | seasonal_naive_7 (88.0) | -22.3 [-32.0, -12.4] | beats_best_baseline | 0.725 | 11.9% | -9.95 | High |
| Zone SYN-B-W | 253 | 38.3 | 39.0 | plan (53.1) | -14.8 [-22.2, -6.3] | beats_best_baseline | 0.712 | 12.2% | -13.27 | High |
| Zone SYN-C-C1 | 264 | 26.7 | 25.0 | seasonal_naive_7 (40.4) | -13.7 [-18.6, -9.6] | beats_best_baseline | 0.748 | 15.4% | -2.85 | Medium |

## 6. Real API samples

Recorded from the running service. Long lists are trimmed and marked in the files. See [`docs/samples/`](samples/) and [`docs/API.md`](API.md).

| File | Request | Status | Notes |
| --- | --- | ---: | --- |
| `health.json` | `GET /api/health` | 200 | liveness |
| `ready.json` | `GET /api/ready` | 200 | storage ok, demo dataset ok, external services ok (enabled; this sandbox cannot reach them) |
| `datasets_list.json` | `GET /api/datasets` | 200 | synthetic first, not deletable |
| `overview_filtered.json` | `GET /api/overview?mine_id=SYN-A&start=2026-07-01&end=2026-09-30` | 200 | measured KPIs and constraints |
| `error_unknown_mine.json` | `GET /api/overview?mine_id=NOPE` | 422 | error envelope with valid values |
| `forecast_zone.json` | `GET /api/forecast?zone_id=SYN-A-Z2&horizon_days=30` | 200 | backtest, classifier, forward forecast, scenario |
| `risk_zone.json` | `GET /api/risk?zone_id=SYN-A-Z2` | 200 | band HIGH, expected gap −23.8% (estimate) |
| `recommendations_zone.json` | `GET /api/recommendations?zone_id=SYN-A-Z2` | 200 | recommendations with evidence and impact labels; rules checked |
| `exploration.json` | `GET /api/exploration` | 200 | EZ-01 ranked 1; EZ-04 and EZ-05 not ranked |
| `satellite_unavailable_in_sandbox.json` | `GET /api/geo/satellite/scenes?...` | 200 | `status: unavailable` (sandbox cannot reach the catalogue) |
| `upload_valid.json` | `POST /api/datasets` (valid CSV) | 201 | user-provided; then deleted, so the store is clean |
| `upload_invalid.json` | `POST /api/datasets` (bad date, negative plan) | 422 | nothing stored; errors cite file lines 2 and 3 |

## 7. Commands to reproduce

```text
backend:   python -m ruff check .
           python -m ruff format --check .
           python -m mypy app
           python -m pytest -q
frontend:  npm ci
           npm run lint
           npm run typecheck
           npm run test
           npm run build
```

On Windows PowerShell use the same commands; see `README.md`.

## What was not verified

Stated plainly, so nobody mistakes an untested path for a tested one.

* **Windows PowerShell commands.** Written for PowerShell 5.1 and 7 but **not executed on Windows**. They were not run in PowerShell at all in this sandbox.
* **Vercel deployment.** Not performed. The steps in `docs/DEPLOYMENT.md` follow the platform's documented behaviour and must be confirmed on the first deploy.
* **Render deployment.** Not performed. `render.yaml` parses and its CORS regex was checked against a preview host and a foreign host, but the service was not created on Render.
* **Live public services.** The Copernicus STAC catalogue and the Open-Meteo archive were **unreachable from the sandbox**. Their clients are tested with mocked transports only. Their live behaviour, response sizes and rate limits are unverified.
* **Real data.** Every dataset is synthetic. No result describes a real mine.
* **Cross-browser and devices.** Only headless Chromium on Linux. Every page at desktop width; the overview at phone width. Not tested on Firefox, Safari, Edge or real devices.
* **Accessibility audit.** Semantic structure and labels were built in, and keyboard use of the zone list was considered, but no automated accessibility audit (for example axe) was run.
* **GitHub Actions.** `.github/workflows/ci.yml` parses and runs the same commands as above, but the workflow itself was not executed on GitHub.
* **npm notices (known, not failures).** `eslint@9.39.5` is deprecated upstream; ESLint 9 is pinned because the plugins used by `eslint-config-next` do not yet support ESLint 10. `npm ls` reports an invalid optional peer for `picomatch@2.3.2` required by `fdir`; the install succeeds and nothing in the build uses that peer.
* **Load and performance under concurrent use.** Not tested. Single-process, file-based storage.
