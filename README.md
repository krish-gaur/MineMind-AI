# MineMind AI

Manganese exploration and production intelligence for **SIH26009** (Ministry of Steel / MOIL, "Using AI/ML and Space Technology to Identify Manganese Reserves and Overcome Production Shortfalls").

MineMind AI is a working prototype with:

* **Executive overview**: plan against actual, matched-day gap and attainment, constraint hours, zone table, data freshness.
* **Data ingestion**: validated production CSV, drillhole CSV and exploration-zone GeoJSON, with row- or feature-level error reports.
* **Forecasting**: leakage-safe features, naive baselines first, expanding-window backtest, MAE and RMSE, bootstrap comparison, saved and reloadable models.
* **Shortfall risk**: expected net gap to plan with an empirical interval, a separate logistic classifier for shortfall days, and a transparent rule-based band.
* **Recommendations**: eight evidence-gated rules, impact marked *estimated* or *not estimated*, and the rules that did not fire are listed.
* **Exploration zones**: an evidence-gated priority index from geological and drilling indicators only. Vegetation, rainfall and similar indices are context, never score.
* **Geospatial view**: MapLibre map, offline basemap, synthetic demonstration area, Sentinel-2 footprint search and public rainfall (both keyless, both degrade gracefully).
* **Reports**: self-contained HTML or JSON, every figure tagged with its value type and source.

> **Data integrity.** No MOIL data was available. Every production, geology, drillhole and boundary record shipped with the prototype is **SYNTHETIC** (fictional `SYN-*` mines and zones, invented grades, invented outlines). It is labelled SYNTHETIC on every screen, in every export and in every report. Nothing here is a reserve, resource, drilling result, satellite observation or measured accuracy for any real mine. Good backtest figures on synthetic data show that the workflow runs; they do not show real-world performance.

Status, verification and gaps: [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md), [`docs/AUDIT.md`](docs/AUDIT.md) and the [limitations](#limitations-and-incomplete-features) below.

---

## Quick start (Windows PowerShell)

Requirements: Python 3.11 (`py -3.11`), Node.js 20.9 or newer (22 LTS recommended), Git.

```powershell
# ---- Backend (terminal 1) ----
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
# If activation is blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m app.cli generate-demo
python -m app.cli train --all-scopes
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
# ---- Frontend (terminal 2) ----
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

Open <http://localhost:3000>. API docs are at <http://127.0.0.1:8000/api/docs>.

The Next.js dev server proxies `/api/*` to `BACKEND_URL` (default `http://127.0.0.1:8000`), so the browser never talks to the backend directly.

Run the checks:

```powershell
# backend (from backend\ with the venv active)
python -m ruff check .
python -m mypy app
python -m pytest -q

# frontend (from frontend\)
npm run lint
npm run typecheck
npm run test
npm run build
```

> These PowerShell commands were written for Windows PowerShell 5.1 and 7 but were **executed on Linux** in this build's sandbox. They have not been run on Windows. See [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md#what-was-not-verified).

macOS and Linux equivalents are the same commands with `source .venv/bin/activate` in place of the activation line.

## Repository layout

```
MineMind-AI/
├── README.md                     this file
├── render.yaml                   Render blueprint for the API (backend)
├── .github/workflows/ci.yml      lint, type, test and build on push and pull request
├── docs/
│   ├── AUDIT.md                  repository audit, constraints, risks and plan
│   ├── ARCHITECTURE.md           components, data flow, decisions (why no PostGIS, etc.)
│   ├── METHODOLOGY.md            forecasting, baselines, risk bands, exploration index, recommendations
│   ├── DATA_SOURCES.md           every dataset, licence, attribution and limitation
│   ├── API.md                    endpoints, parameters, sample requests and responses
│   ├── DEPLOYMENT.md             Vercel (frontend) and Render (backend) steps and environment variables
│   ├── DEMO_SCRIPT.md            judge walkthrough
│   ├── TEST_REPORT.md            commands run and their real results
│   └── samples/                  real responses recorded from this build (trimmed)
├── backend/                      FastAPI, pandas, scikit-learn, Pydantic
│   ├── app/
│   │   ├── main.py               app factory, CORS, lifespan (demo data)
│   │   ├── config.py             environment settings (see .env.example)
│   │   ├── errors.py             error envelope; no stack traces to clients
│   │   ├── middleware.py         request ids, timing, safe 500s
│   │   ├── cli.py                generate-demo, train, status
│   │   ├── api/routes/           thin HTTP layer (health, datasets, overview, forecast, ...)
│   │   ├── domain/               pure logic: validation, synthetic data, forecasting, risk,
│   │   │                         recommendations, exploration, reports, public-service clients
│   │   ├── schemas/              Pydantic request and response models
│   │   └── demo_data/            (synthetic geometry is generated in domain/synthetic_geo.py)
│   ├── tests/                    pytest suite (validation, leakage, forecasting, API, geo, reports)
│   ├── requirements.txt          pinned runtime dependencies
│   ├── requirements-dev.txt      + pytest, ruff, mypy
│   └── pyproject.toml            ruff and mypy configuration
└── frontend/                     Next.js 16 (App Router), React 19, Tailwind CSS 4, MapLibre, Recharts
    ├── src/app/                  pages: overview, forecast, risk, recommendations, map, exploration, reports, data
    ├── src/components/           layout, charts, forecast, risk, recs, map, data, ui primitives
    ├── src/lib/                  typed API client, formatting, dataset context, hooks
    ├── public/geo/               offline basemap (Natural Earth, public domain)
    ├── scripts/build-basemap.mjs regenerates public/geo/countries-context.geojson
    └── next.config.ts            /api rewrite to BACKEND_URL, security headers
```

Pages: `/` overview · `/forecast` · `/risk` · `/recommendations` · `/map` · `/exploration` · `/reports` · `/data`.

## Environment variables

Backend (`backend/.env`, or the host's environment). Full notes in [`backend/.env.example`](backend/.env.example).

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | `development`, `test` or `production`. |
| `LOG_LEVEL` | `INFO` | JSON logs to stdout. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated origins allowed to call the API directly. |
| `CORS_ORIGIN_REGEX` | empty | Optional regex, e.g. `https://.*\.vercel\.app` for preview deployments. |
| `DATA_DIR` | `backend/data_store` | Dataset store. Ephemeral on Render unless mounted on a disk. |
| `ARTIFACTS_DIR` | `backend/artifacts` | Saved forecasting models. |
| `MAX_UPLOAD_MB` | `5` | Upload size limit (read-time enforcement). |
| `MAX_UPLOAD_ROWS` | `50000` | Row limit for production CSV. |
| `STALE_DATA_DAYS` | `14` | Freshness threshold for the dashboard and recommendations. |
| `ENABLE_EXTERNAL_SERVICES` | `true` | `false` forces the offline path (no calls to CDSE or Open-Meteo). |
| `EXTERNAL_TIMEOUT_S` | `8` | Timeout for public-service calls. |
| `EXTERNAL_CACHE_TTL_H` | `24` | Disk cache lifetime for public responses. |
| `CDSE_STAC_URL` | `https://stac.dataspace.copernicus.eu/v1` | Sentinel-2 catalogue (keyless). |
| `OPEN_METEO_ARCHIVE_URL` | `https://archive-api.open-meteo.com/v1/archive` | Rainfall archive (keyless; non-commercial use). |
| `FORECAST_HORIZON_DAYS` | `30` | Default horizon (7 to 90 days). |

Frontend (`frontend/.env.local`, or Vercel project settings). Only non-secret values belong here.

| Variable | Default | Purpose |
| --- | --- | --- |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Server-side target of the `/api` rewrite. **Read at build time**; redeploy after changing it. |
| `NEXT_PUBLIC_API_BASE_URL` | empty | Set only if the browser must call the API directly (then the backend's `CORS_ORIGINS` must include the site). |
| `NEXT_PUBLIC_MAP_STYLE_URL` | empty | Optional online MapLibre style. Empty uses the bundled offline outline. Check that style's attribution terms. |

No API keys are required by any feature. No secret is read or exposed by the frontend.

## Endpoints (summary)

Full parameters and sample responses: [`docs/API.md`](docs/API.md). Interactive docs: `/api/docs` on the backend.

| Area | Endpoints |
| --- | --- |
| Health | `GET /api/health` (liveness), `GET /api/ready` (readiness: storage and demo data) |
| Datasets | `GET /api/datasets`, `GET /api/datasets/{id}`, `GET /api/datasets/{id}/preview`, `GET /api/datasets/{id}/export`, `POST /api/datasets` (CSV or GeoJSON), `DELETE /api/datasets/{id}`, `GET /api/datasets/schema/production` |
| Analysis | `GET /api/overview`, `GET /api/forecast`, `GET /api/risk`, `GET /api/recommendations`, `GET /api/exploration` |
| Geospatial | `GET /api/geo/layers`, `GET /api/geo/layers/{aoi\|mines\|zones}`, `GET /api/geo/satellite/scenes`, `GET /api/geo/weather/daily` |
| Reports | `POST /api/reports` (HTML or JSON download) |
| Metadata | `GET /api/meta/sources`, `GET /api/meta/capabilities` |

## Limitations and incomplete features

Honest list. Items marked *not implemented* were in the brief's spirit but are absent from this build.

**Data**
* All demonstration data is synthetic. No real MOIL production, geology, drilling, boundary or assay data was available or used.
* The synthetic production generator encodes the relationships the demo illustrates (monsoon-linked weather delays, lagged downtime, a recurring breakdown in SYN-A-Z2, blasting on Tuesdays and Fridays). Patterns found in this data reflect the generator, not real operations.
* Rainfall is synthetic inside the production dataset. A public rainfall series is shown only as a point panel on the map; it is *not* yet joined into production records (*not implemented*).
* No known-occurrence distances, DEM or slope, lineament, SAR or spectral indicators are computed. The required inputs are listed in the exploration view (*not implemented*).

**Public services**
* Live calls to the Copernicus catalogue and Open-Meteo could **not be verified** from the build sandbox, which cannot reach those hosts. Their clients are tested only with mocked transports. In the sandbox every such panel shows an honest "unavailable" status.
* Satellite support is metadata only (scene footprints, dates, cloud cover). No band values, indices or imagery processing (*not implemented*).

**Models and analysis**
* Forecasts use plan, lagged actuals and lagged operational inputs. Future operational inputs are scenario assumptions (trailing 28-day means), so forecasts are conditional on those assumptions.
* Only one regression family (gradient boosting) plus a ridge benchmark and a logistic classifier. No hyperparameter search, no ensembles, no conformal calibration.
* Prediction intervals are empirical from backtest residuals. They are not calibrated predictive distributions.
* On 7 of the 9 scopes in the synthetic backtest, the ridge benchmark has lower MAE than the gradient boosting model. The UI and the API report this; the pre-specified gradient boosting model remains the forecast. Whether to make ridge the default is an open decision (see `docs/TEST_REPORT.md`, section 5).
* Recommendation impacts are associations in the data (for example, the output difference between heavy-downtime and normal days times the number of heavy days). They are not causal effects.

**Product**
* Reports are HTML or JSON. PDF export is *not implemented*.
* No authentication, authorisation or user accounts. The API is open, so deploy it only where that is acceptable, or put it behind your platform's access controls.
* File-based storage on a single process. No database. Uploads persist only on a persistent disk (see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)).
* Cold starts on hosting free tiers are slow. The first forecast for a scope trains a model (about two seconds locally). `python -m app.cli train --all-scopes` pre-trains and saves all nine scopes.
* Map labels are not drawn (no glyph server is bundled). Zone details are in the adjacent list.
* Accessibility: semantic markup, labelled controls, keyboard-operable zone list, data tables behind every chart. No automated accessibility audit has been run.
* Browser coverage: headless Chromium on Linux. Every page was checked at desktop width; the overview was also checked at phone width. Other browsers and real devices were not tested.

**Process**
* No Windows, Vercel or Render runs were performed from the sandbox. The deployment steps are written from the platforms' documented behaviour and must be confirmed on first deploy.

## Licences and attribution

* Code: see the repository licence (none was specified in the repository before this build).
* Sentinel-2 metadata: Copernicus Sentinel data. When imagery is displayed, credit: *Contains modified Copernicus Sentinel data [year]*.
* Rainfall: Open-Meteo data, CC BY 4.0. ERA5 reanalysis via Copernicus Climate Change Service. **Open-Meteo's free API is for non-commercial use**; commercial use needs a paid plan.
* Basemap outline: Natural Earth (public domain), packaged by `world-atlas` (ISC).
* Fonts: IBM Plex Sans and IBM Plex Mono via `@fontsource` (SIL Open Font License 1.1).

Full table with URLs and terms: [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).
