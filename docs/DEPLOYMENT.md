# Deployment

Target: **frontend on Vercel**, **API on Render**. Both are configured through the environment. Nothing secret is needed, because every public service used is keyless.

> These steps were written against the platforms' documented behaviour. They were **not executed** from the build sandbox, which has no access to Vercel or Render accounts. Confirm them on the first deploy, and record the outcome in `docs/TEST_REPORT.md`.

## 0. Before you deploy

1. Run the checks locally (see `README.md` and `docs/TEST_REPORT.md`).
2. Decide the public origins: the Vercel project URL (for example `https://minemind.vercel.app`) and the Render URL (for example `https://minemind-api.onrender.com`).
3. Decide whether uploads must survive restarts. On Render's free plan the disk is ephemeral. If they must, attach a persistent disk and point `DATA_DIR` at it (see step 2c).

## 1. API on Render

### 1a. Blueprint (recommended)

The repository contains `render.yaml`:

* `rootDir: backend`
* build: `pip install -r requirements.txt && python -m app.cli generate-demo`
* start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* health check: `/api/health`
* Python `3.11.9`

In Render: **New → Blueprint**, select the repository and branch, then apply. Render asks for the `sync: false` variables; fill them in (below).

### 1b. Manual Web Service

If you prefer not to use the blueprint:

* **Root directory**: `backend`
* **Runtime**: Python 3, and set `PYTHON_VERSION=3.11.9`
* **Build command**: `pip install -r requirements.txt && python -m app.cli generate-demo`
* **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* **Health check path**: `/api/health`

### 1c. Environment variables (API)

| Variable | Set to | Notes |
| --- | --- | --- |
| `APP_ENV` | `production` | |
| `LOG_LEVEL` | `INFO` | |
| `CORS_ORIGINS` | `https://<your-vercel-domain>` | Needed only if the browser calls the API directly (`NEXT_PUBLIC_API_BASE_URL`). Harmless otherwise. |
| `CORS_ORIGIN_REGEX` | `https://.*\.vercel\.app` | Lets Vercel preview deployments call the API directly. Remove it if you do not want previews to call the API. |
| `ENABLE_EXTERNAL_SERVICES` | `true` | Set `false` to force the offline path, for example during an upstream outage. |
| `MAX_UPLOAD_MB` | `5` | |
| `MAX_UPLOAD_ROWS` | `50000` | |
| `STALE_DATA_DAYS` | `14` | |
| `DATA_DIR` | (leave unset) or a mounted disk path | Unset means `backend/data_store` on the instance's ephemeral disk. |
| `ARTIFACTS_DIR` | (leave unset) | Saved models. Regenerated on first use after a restart. |

No API keys are needed. Do not add any secret to the frontend.

### 1d. Verify the API

```bash
curl -s https://<render-host>/api/health
curl -s https://<render-host>/api/ready
curl -s "https://<render-host>/api/overview?mine_id=SYN-A"
```

* `/api/health` should return `{"status":"ok", ...}` immediately.
* The first request to `/api/forecast` for a scope trains a model. Expect a few seconds on free hardware.
* The first request after an idle period may be slow while the free instance wakes.

### 1e. Operating notes

* **Ephemeral storage.** Uploaded datasets and saved models vanish on redeploy or restart unless `DATA_DIR` is on a persistent disk. The synthetic demo is regenerated automatically at startup, so the demo always works.
* **Pre-training (optional).** To avoid a slow first forecast, add `python -m app.cli train --all-scopes` to the build command. Models saved during the build stay on the instance only if the build and the runtime share the same filesystem; check this on your plan.
* **Scaling.** The app is single-process and file-based. Run one instance. Do not scale horizontally without moving the store to shared storage.

## 2. Frontend on Vercel

### 2a. Project

1. **Add New → Project**, import the repository.
2. **Root Directory**: `frontend`. The framework preset is detected as Next.js.
3. **Install command**: default (`npm install` or `npm ci`). The repository's `frontend/.npmrc` sets `legacy-peer-deps=true`; keep it.
4. **Build command**: default (`next build`). **Output**: default.
5. **Node.js version**: 22.x (the package declares `>=20.9.0`).

### 2b. Environment variables (frontend)

| Variable | Set to | Notes |
| --- | --- | --- |
| `BACKEND_URL` | `https://<render-host>` (no trailing slash) | Used by the `/api` rewrite. **Read at build time.** Redeploy after you change it. |
| `NEXT_PUBLIC_API_BASE_URL` | leave **empty** | Recommended. The browser calls `/api/*` on the Vercel domain and Vercel forwards it to Render, so no CORS is needed. |
| `NEXT_PUBLIC_MAP_STYLE_URL` | leave **empty** | Optional. Set it only to an online style whose terms you have checked. |

Upload size note: Vercel's proxy can impose a request-body limit below the API's 5 MB default. If large uploads fail through Vercel, set `NEXT_PUBLIC_API_BASE_URL=https://<render-host>` (the browser then calls Render directly) and set `CORS_ORIGINS=https://<your-vercel-domain>` on Render.

### 2c. Verify the frontend

1. Open the Vercel URL. The overview should load with the SYNTHETIC banner.
2. Open `/forecast`. The first load may take a few seconds while the API trains a model.
3. Open `/map`. The basemap and zones should draw. Satellite and rainfall panels show an honest status (live, cached, unavailable or disabled).
4. Open `/reports`, choose HTML, and download a report.

### 2d. Preview deployments

Each pull request gets a preview URL. With `BACKEND_URL` set and the default rewrite, previews call the same Render API. Nothing else is needed.

## 3. Rollback

* **Frontend:** in Vercel, promote a previous deployment.
* **API:** in Render, roll back to a previous deploy. Saved models and uploads on an ephemeral disk do not survive a rollback; the synthetic demo regenerates.

## 4. Pre-deployment checklist

- [ ] `python -m pytest -q` passes in `backend/`.
- [ ] `npm run check` passes in `frontend/`.
- [ ] `BACKEND_URL` is set to the Render URL in Vercel and the project was redeployed after setting it.
- [ ] `CORS_ORIGIN_REGEX` and `CORS_ORIGINS` match the domains you actually use.
- [ ] The Render health check passes and `/api/ready` reports `ready`.
- [ ] The synthetic banner appears on every analysis page (it is part of the product, not a debug setting).
- [ ] The official SIH26009 deadline and rules have been checked (see `docs/DATA_SOURCES.md`).
