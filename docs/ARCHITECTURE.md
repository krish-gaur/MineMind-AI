# Architecture

## Shape of the system

```
browser ──► Next.js app (Vercel)                       FastAPI app (Render)
            pages, components, charts, MapLibre         routers (thin HTTP layer)
            /api/* rewrite ────────────────────────────► domain (pure Python)
                                                         ├─ validation, schema
                                                         ├─ synthetic generators
                                                         ├─ features, forecasting, risk
                                                         ├─ recommendations, exploration
                                                         ├─ reports (HTML/JSON)
                                                         └─ external clients (keyless, cached)
                                                       storage: files under DATA_DIR
                                                         datasets/<id>/{manifest.json, data}
                                                         artifacts/models/<dataset>/<scope>.joblib
                                                         cache/*.json (public responses, TTL)
                                                       public services (optional, degradable)
                                                         Copernicus STAC · Open-Meteo archive
```

One API process, one web app. There are no microservices, no queues and no database. The data volume (a few thousand daily rows per dataset) does not justify more.

## Backend (`backend/app`)

| Layer | Modules | Rule |
| --- | --- | --- |
| HTTP | `api/routes/*.py`, `api/deps.py`, `api/router.py` | Validates parameters, calls the domain, maps errors. No business logic. |
| Domain | `domain/*.py` | Pure functions over DataFrames and plain dicts. Unit-tested without HTTP. |
| Schemas | `schemas/*.py` | Pydantic models document responses (OpenAPI) and validate requests. |
| Infrastructure | `config.py`, `logging_config.py`, `middleware.py`, `errors.py`, `domain/store.py`, `domain/external.py` | Settings from the environment; JSON logs; request ids; error envelope; file store; cached public client. |

Key decisions:

* **Error envelope.** Every error is `{"error": {"code", "message", "details", "request_id"}}`. Stack traces are logged on the server with the request id and are never returned. An unhandled exception becomes a generic 500 with that request id.
* **Upload safety.** The size limit is enforced while reading the body (`read(limit + 1)`), before parsing. Only `.csv` (production, drillholes) and `.geojson`/`.json` (zones) are accepted. Filenames are reduced to a safe base name and are never used as paths. Dataset ids are matched against a strict pattern before any filesystem access, so `..` and similar input 404.
* **Provenance travels with data.** Every manifest stores `source_type` (synthetic, user_provided, public), a human label, the provider, licence, attribution and limitations. Every analysis response repeats the dataset's source label and value types.
* **Value types.** `measured`, `forecast`, `probability`, `estimate`, `scenario`, `rule_based`, `index`. They are declared per field and rendered as badges in the UI and as tags in reports.
* **Policy in one place.** Thresholds (heavy-day hours, risk bands, rule triggers, the material-shortfall tolerance, the exploration gates) live in `domain/policy.py` and are echoed to users wherever they apply.
* **Determinism.** The synthetic generator uses a seeded NumPy generator. Its output is byte-identical across runs (checked by SHA-256 in tests). Models use fixed random states. Model artefacts carry a data fingerprint and a configuration hash.

## Frontend (`frontend/src`)

* **Next.js 16 App Router**, React 19, TypeScript in strict mode, Tailwind CSS 4 with design tokens in `globals.css`.
* **Data flow.** `DatasetProvider` loads the dataset list once and keeps the active production dataset (persisted in `localStorage`). Each page keys its view by dataset id, so filters reset when the dataset changes. `useApiResource` tags every response with the query it answers, so stale numbers from an earlier selection are never shown under a new one.
* **API access.** One typed client (`lib/api.ts`). Errors become `ApiError` with a user-safe message and the request id. Network failures are reported as "backend unreachable".
* **Charts.** Recharts for the monthly trend, backtest and forward forecast. Every chart has a "View as table" alternative. Constraint bars are plain HTML.
* **Map.** MapLibre GL JS, loaded client-side only. Data updates use `setData` and visibility uses layout properties, so toggling a layer never rebuilds the map. The zone list is the keyboard-accessible alternative.
* **Routing to the API.** `next.config.ts` rewrites `/api/*` to `BACKEND_URL` on the server. The browser calls same-origin paths, so no CORS is needed by default.

## Why no PostGIS

The data is small (thousands of rows, tens of polygons), read-mostly, and produced by the app itself. Shapely (geometry validity and area) and GeoJSON files cover the spatial needs. PostGIS would add a database service, migrations and a hosting cost, and nothing in the brief needs spatial joins at scale. If the project later needs multi-user editing of geometries or large spatial queries, that is the point to revisit it.

## Why these libraries

| Need | Choice | Alternatives considered |
| --- | --- | --- |
| Web API | FastAPI + Pydantic v2 | Flask (no typed contracts by default) |
| Tabular work | pandas 3 | Polars (fine, but the rest of the stack is pandas) |
| Models | scikit-learn (HistGradientBoosting, Ridge, Logistic) | XGBoost/LightGBM (extra native dependency for no demonstrated gain on this data size) |
| Persistence | joblib with fingerprints and version checks | Hand-rolled pickle (no); ONNX (unnecessary) |
| Geometry | Shapely | GeoPandas/GDAL (heavy binary stack on Render's free tier) |
| Frontend | Next.js, Tailwind, Recharts | Vite SPA (would need a separate proxy story for Vercel) |
| Map | MapLibre GL JS | Leaflet (fine, but MapLibre vector styles are the path to online basemaps) |
| Fonts | `@fontsource` | `next/font/google` (build fails without Google reachable) |

## Data lifecycle

1. **Upload or generate.** `POST /api/datasets` validates the file. Errors stop the upload with a report that cites lines or features. Accepted data is written atomically (staged directory, then rename) with its manifest.
2. **Analyse.** The overview computes figures from the stored table, filtered per request. Nothing is cached in the browser beyond the current page.
3. **Model.** For a scope (all, a mine, or a zone) the service builds a daily series, features, and a backtest. The fitted models are saved with the fingerprint. A later request reuses them only if the fingerprint and configuration hash still match.
4. **Report.** `POST /api/reports` calls the same domain functions and renders them, so report numbers match the dashboard.

## Operational characteristics

* Startup creates the synthetic production and exploration datasets if missing or outdated (`GENERATOR_VERSION` mismatch). Startup takes well under a second.
* Forecast training for one scope takes about two seconds on the build sandbox (2 CPUs). A `risk`, `recommendations` or `report` request reuses the model from memory after the first call.
* Public-service calls have a timeout, a disk cache with a TTL, and report one of four statuses (`live`, `cached`, `unavailable`, `disabled`). They never raise into the UI.
* Logs are JSON lines. Request bodies, uploaded contents and query values are not logged.
