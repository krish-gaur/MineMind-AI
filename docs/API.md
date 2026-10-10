# API reference

Base path `/api`. Interactive OpenAPI docs: `/api/docs` (Swagger UI) and `/api/openapi.json`.

Examples below use `http://127.0.0.1:8000`. Through the Next.js app, use `http://localhost:3000/api/...` instead; the app forwards the request unchanged.

**Real responses.** Files in [`docs/samples/`](samples/) were recorded from this build with the synthetic demonstration data. Long lists are trimmed and marked `... N more item(s) omitted`.

**Conventions**

* Every response has an `X-Request-ID` header. Quote it when reporting a problem.
* Errors use one envelope:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Mine 'NOPE' is not in this dataset.",
    "request_id": "7c1f0e2a9b3d4a5f8e6d1c2b3a4f5e6d",
    "details": { "valid_mines": ["SYN-A", "SYN-B", "SYN-C"] }
  }
}
```

  Codes in use: `validation_failed` (422), `insufficient_data` (422), `not_found` (404), `forbidden` (403, for example deleting synthetic data), `payload_too_large` (413), `unsupported_media_type` (415), `wrong_dataset_kind` (422), `external_service_unavailable` (503, reserved), `internal_error` (500, generic). Stack traces are never returned. See [`samples/error_unknown_mine.json`](samples/error_unknown_mine.json).
* Value types: each analysis block carries `value_kind` (`measured`, `forecast`, `probability`, `estimate`, `scenario`, `rule_based`, `index`). Source labels are on the dataset object.
* Dates are ISO `YYYY-MM-DD`. Tonnes are `t`, hours are `h`, rainfall is `mm`.

---

## Health and metadata

### `GET /api/health`: liveness

No dependencies are touched. Render's health check uses this path.

```bash
curl -s http://127.0.0.1:8000/api/health
```

Response: [`samples/health.json`](samples/health.json)

### `GET /api/ready`: readiness

Checks that storage is writable and that the synthetic demonstration dataset is registered. External services are reported but never make the service unready. Returns 503 only when storage is not writable.

Response: [`samples/ready.json`](samples/ready.json)

### `GET /api/meta/sources`

Every data source with its access route, licence, attribution and limitations.

### `GET /api/meta/capabilities`

Feature flags and limits in effect (horizon, upload limits, freshness threshold, whether external services are enabled).

---

## Datasets

### `GET /api/datasets?kind=production|drillholes|exploration_zones`

Lists registered datasets with source labels. Synthetic datasets are listed first and cannot be deleted.

Response: [`samples/datasets_list.json`](samples/datasets_list.json)

### `GET /api/datasets/{id}`

Metadata, provenance, the stored validation report and the file's SHA-256.

### `GET /api/datasets/{id}/preview?rows=20`

First rows (1 to 200). Missing values are `null`.

### `GET /api/datasets/{id}/export`

The normalised CSV (`text/csv`, attachment).

### `GET /api/datasets/schema/production`

The production.v1 column contract, limits and an example CSV.

### `POST /api/datasets`: upload and validate

`multipart/form-data`:

| Field | Required | Values |
| --- | --- | --- |
| `file` | yes | `.csv` for `production` and `drillholes`; `.geojson` or `.json` for `exploration_zones` |
| `kind` | no (default `production`) | `production`, `drillholes`, `exploration_zones` |
| `name` | no | up to 120 characters |
| `description` | no | up to 400 characters |

Limits: `MAX_UPLOAD_MB` (default 5, enforced while reading) and `MAX_UPLOAD_ROWS` (default 50,000). Filenames are reduced to a safe base name and are never used as paths.

```bash
curl -s -F "file=@pilot.csv;type=text/csv" -F "name=Pilot extract" http://127.0.0.1:8000/api/datasets
```

```powershell
curl.exe -s -F "file=@pilot.csv;type=text/csv" -F "name=Pilot extract" http://127.0.0.1:8000/api/datasets
```

* `201 Created` with the dataset detail on success. Production uploads are labelled USER-PROVIDED. Warnings are accepted; their list is in `validation.issues`.
* `422` when there are errors. **Nothing is stored.** The response's `error.details` is the full report with row errors cited by file line. Response: [`samples/upload_invalid.json`](samples/upload_invalid.json)
* `413`, `415` for size and type.

Response for a valid file: [`samples/upload_valid.json`](samples/upload_valid.json)

### `DELETE /api/datasets/{id}`

Deletes a user-provided dataset (`204`). Synthetic datasets return `403`.

---

## Overview

### `GET /api/overview`

| Parameter | Description |
| --- | --- |
| `dataset_id` | production dataset; default is the synthetic demo |
| `start`, `end` | inclusive dates; `start` must not be after `end` (422) |
| `mine_id`, `zone_id` | must exist in the dataset (422 lists the valid values) |

```bash
curl -s "http://127.0.0.1:8000/api/overview?mine_id=SYN-A&start=2026-07-01&end=2026-09-30"
```

Response: [`samples/overview_filtered.json`](samples/overview_filtered.json). Blocks: `kpis` (measured), `constraints` (measured hours by cause with shares), `monthly`, `zones` (sorted by gap), `freshness`, `notes`, `dataset.banner` (for synthetic data).

---

## Forecast and risk

Both accept `dataset_id`, `mine_id`, `zone_id`, `horizon_days` (7 to 90, default 30). A zone must belong to the mine it is given with.

### `GET /api/forecast`

Backtest evaluation, the model card, baselines, classification check, backtest history, the forward forecast with intervals and scenario assumptions, and drivers.

```bash
curl -s "http://127.0.0.1:8000/api/forecast?zone_id=SYN-A-Z2&horizon_days=30"
```

```powershell
curl.exe -s "http://127.0.0.1:8000/api/forecast?zone_id=SYN-A-Z2&horizon_days=30"
```

Response (trimmed): [`samples/forecast_zone.json`](samples/forecast_zone.json)

Key fields:

* `model.source`: `memory`, `loaded` (from a saved model whose data is unchanged) or `trained`.
* `evaluation.verdict`: `beats_best_baseline`, `worse_than_best_baseline` or `no_reliable_difference`, with `gap_to_best_baseline` (MAE difference, bootstrap 95% interval, skill).
* `classification`: material-shortfall classifier metrics (`value_kind: probability`).
* `forecast.totals`: planned, forecast, net gap (estimate), interval, probability the period ends below plan, mean daily probability.
* `forecast.scenario_assumptions`: the inputs held at trailing means (`value_kind: scenario`).

Errors: `422 insufficient_data` when the scope has fewer complete days than the backtest needs. The message states the numbers.

### `GET /api/risk`

Expected gap, interval, probabilities, the rule-based band and its rule, the classifier check and the model check.

```bash
curl -s "http://127.0.0.1:8000/api/risk?zone_id=SYN-A-Z2"
```

Response: [`samples/risk_zone.json`](samples/risk_zone.json). `band.value_kind` is `rule_based`. `expected.value_kind` is `estimate`.

---

## Recommendations

### `GET /api/recommendations`

Adds `include_forecast=true|false` (default true). With it, the forecast-based rules are evaluated too.

```bash
curl -s "http://127.0.0.1:8000/api/recommendations?zone_id=SYN-A-Z2"
```

Response: [`samples/recommendations_zone.json`](samples/recommendations_zone.json). Each recommendation has `priority`, `category`, `summary`, `reasoning`, `suggested_actions`, `evidence`, `expected_impact` (`status: estimated` with `value_t` and `basis`, or `not_estimated`), `confidence` and `limitations`. `rules` lists every rule with `fired` and `reason`.

---

## Exploration zones

### `GET /api/exploration`

| Parameter | Default |
| --- | --- |
| `zones_dataset_id` | synthetic zones |
| `drillholes_dataset_id` | synthetic drillholes |

```bash
curl -s "http://127.0.0.1:8000/api/exploration"
```

Response: [`samples/exploration.json`](samples/exploration.json). Each zone has `status`, `indicators`, `indicator_rows` (value, normalised value, weight, evidence class, availability), `missing_inputs`, `score` (index, `value_kind: index`), `rank` (null when not ranked), `ranking_reason`, `confidence`. `method` documents the weights and the context indices that are displayed but not scored.

---

## Geospatial

### `GET /api/geo/layers`

Layer catalogue with counts, source type, synthetic flag and notes. Includes `aoi_bbox` and the attribution for the basemap.

### `GET /api/geo/layers/{aoi|mines|zones}`

GeoJSON `FeatureCollection`. `zones` accepts `dataset_id` (an exploration-zones dataset).

### `GET /api/geo/satellite/scenes`

Sentinel-2 L2A scene metadata from the Copernicus STAC catalogue.

| Parameter | Default |
| --- | --- |
| `bbox` | demonstration area, `minLon,minLat,maxLon,maxLat` |
| `start`, `end` | last 90 days |
| `max_cloud` | 30 (percent) |
| `limit` | 20 (1 to 100) |

```bash
curl -s "http://127.0.0.1:8000/api/geo/satellite/scenes?start=2026-09-01&end=2026-09-30"
```

`status` is one of `live`, `cached`, `unavailable` or `disabled`, with a `message`. **In the build sandbox the catalogue was unreachable**, so the recorded response is `unavailable` with no scenes: [`samples/satellite_unavailable_in_sandbox.json`](samples/satellite_unavailable_in_sandbox.json). Requests are limited to 366 days.

### `GET /api/geo/weather/daily`

Daily precipitation at a point from the Open-Meteo archive (CC BY 4.0; free API for non-commercial use).

```bash
curl -s "http://127.0.0.1:8000/api/geo/weather/daily?lat=21.85&lon=80.2&start=2026-09-01&end=2026-09-03"
```

Missing days come back as `null` and are counted in `missing_days`. They are never zero-filled.

---

## Reports

### `POST /api/reports`

Body (JSON):

```json
{
  "dataset_id": "demo-synthetic-production-v1",
  "mine_id": "SYN-A",
  "horizon_days": 30,
  "sections": ["overview", "forecast", "risk", "recommendations", "exploration", "sources"],
  "format": "html",
  "title": "SIH demo report"
}
```

`sections` may contain `overview`, `forecast`, `risk`, `recommendations`, `exploration` and `sources`. `format` is `html` (self-contained page) or `json`. Both are returned as attachments.

```bash
curl -s -X POST http://127.0.0.1:8000/api/reports -H "Content-Type: application/json" -d @report-request.json -o report.html
```

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/reports -H "Content-Type: application/json" --data-binary "@report-request.json" -o report.html
```

The HTML report opens with the synthetic notice (for synthetic data), a legend of value types, and one section per requested block. Every section is labelled with its value type and source. All user-supplied text is escaped.

---

## Versioning and stability

The API is unversioned in this prototype (`/api/...`). Response fields may gain keys; existing keys keep their meaning. Breaking changes would move to `/api/v2`.
