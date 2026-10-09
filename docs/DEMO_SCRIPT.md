# Demo walkthrough (about 10 minutes)

Run the app as described in `README.md`. Open <http://localhost:3000>.

Say this first, every time: **the data is synthetic.** Every page shows the amber SYNTHETIC banner. The point of the demo is that the workflow is complete, labelled and checkable, not that the numbers describe a real mine.

## 1. The problem and the three questions (1 min)

* The brief has two halves: **where to look for ore** (exploration) and **why production falls short** (forecasting, risk, action).
* MineMind separates them. Exploration output is an index over geological and drilling evidence. Production output is a forecast, a rule-based band and recommendations. No number is passed off as a reserve.

## 2. Executive overview (2 min): `/`

* Start on the default range (last 12 months of the synthetic demo).
* Point out the KPI tiles. Each has a value type (**Measured**, **Estimate**). Gap and attainment use **matched days only**; the note says so, and the count of pending rows is visible.
* Scroll to the monthly chart. Use "View as table" to show the same numbers as text.
* "Where hours were lost": equipment downtime leads, weather second. Weather delay is concentrated in June to September.
* Zone table: sorted by gap. SYN-A-Z2 stands out, with the lowest attainment and the most downtime.
* Freshness: the last actual is 30 Sep 2026; the dashboard says how many days ago that was.
* Try a filter: pick **SYN-A** and then the zone. The notes update, and the figures change.

## 3. Data and validation (2 min): `/data`

* Show the registered datasets. Each has a source badge: SYNTHETIC, USER-PROVIDED or PUBLIC.
* Scroll to **Upload data**. Choose **Production records (CSV)** and upload a file with a bad date and a negative plan (you can build one in Notepad from the template download on this page). The upload is refused, and the report cites the file lines (for example `line 2: date '2026-13-40' is not a valid YYYY-MM-DD calendar date`). Nothing was stored.
* Upload a valid file with a blank actual on one row. It is accepted with a warning: "pending". The blank is not filled in, and the warning says so.
* Show the production contract and the template download.
* Scroll to **Data sources**. Every source has its licence, attribution and limitations. Note that Open-Meteo's free API is for non-commercial use.

## 4. Forecast and backtest (3 min): `/forecast`

* Scope: **All mines and zones**. Read the **verdict** first: the gradient boosting model beats the best baseline on this backtest, with a 95% interval for the difference that excludes zero.
* Read the **model comparison**: plan, persistence, seasonal naive and moving average are the baselines. Ridge is a linear benchmark. Point out that the baselines are scored on the same days.
* Explain **leakage prevention**: each day is predicted with information dated before it. The test suite proves that same-day operational values are not used.
* Look at the **forward forecast** and its scenario box. The future downtime and weather are assumptions held at trailing means, and the page says so.
* Open the **classifier** card. The "material shortfall" target is "actual below 95% of plan". Its AUC and Brier skill against the base rate are on the card, not implied.
* Switch the scope to **SYN-A-Z2**. The verdict can differ by scope; the page reports whatever the backtest gives.

## 5. Shortfall risk (2 min): `/risk`

* The band is **HIGH** for all mines, with the rule printed next to it: HIGH at or below −5% of plan, MEDIUM at or below −2%.
* The expected net gap is an **estimate** with an empirical interval. The probability that the period ends below plan is an **empirical frequency** from backtest windows.
* Switch to **SYN-C-C1**: the band is **MEDIUM**. The bands move with the data; the thresholds are policy and can be challenged.

## 6. Recommendations (2 min): `/recommendations`

* Scope **SYN-A-Z2**. Read the first card: **recurring equipment downtime**. The evidence table shows the heavy-day count, the share and the totals. Its expected impact is **estimated**, and the basis says it is an association in the data, not a causal effect.
* Read a **not estimated** card, for example the data-capture or the weather card. The response says why no number is given.
* Scroll to **Rules checked**. Every rule is listed with the outcome and the reason, including the ones that did not fire. Silence is never mistaken for approval.

## 7. Geospatial view and exploration (2 min): `/map` and `/exploration`

* On `/map`, zones are coloured by evidence status: green for drilling observed, amber dashed for host unit mapped with no drilling, grey for host unit not mapped. Mine outlines are dark-outlined boxes.
* Select EZ-04 in the list. It is **not ranked**: it has one evidence class (the mapped host unit), and the page says ranking needs two.
* On `/exploration`, show the method: weights, the cut-off, and the **context indices that are not scored** (vegetation, rainfall, soil moisture, temperature, SAR). The reason is printed: those indices respond to many non-mineral processes.
* Show "Inputs needed before any real assessment". This demonstration does not replace them.
* On the map panels, press **Search last 90 days**. In an environment that cannot reach the catalogue, the status says so (for example "unavailable"). In a networked environment, footprints appear on the map. The same applies to the rainfall panel.

## 8. Reports (1 min): `/reports`

* Keep the default sections. Choose **HTML**, click **Generate and download**, and open the file.
* In the report, point out the synthetic notice at the top, the legend of value types, and a tag on every section (for example **Forecast** and **Estimate**).
* The JSON option carries the same labels for machines.

## 9. Close (1 min)

* What works end to end: validated ingestion, leakage-safe forecasting with baselines and intervals, a separate classifier, transparent bands, evidence-backed recommendations, gated exploration, a map, and labelled reports.
* What does not: real data, live verification of the public services from this environment, deployment on Vercel and Render, PDF reports, authentication, and the geology indicators a real assessment needs. See the limitations in `README.md`.

## If something goes wrong during the demo

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| "Backend unreachable" | API not running | Start `uvicorn` in `backend/` (see README). |
| Forecast takes a few seconds | First training of that scope | Expected. Later requests are fast. |
| Map is blank | WebGL unavailable in the browser | The zone list still works. Try a current Chrome or Edge. |
| Satellite panel says "unavailable" | No route to the catalogue | Expected offline. Say so; the status is the honest answer. |
| Upload says the file is too large | Over `MAX_UPLOAD_MB` | Split the file by period. |
