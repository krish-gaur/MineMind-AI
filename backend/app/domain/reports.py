"""Self-contained HTML and JSON reports.

Every figure in a report carries two labels: its *value type* (measured, forecast, probability,
estimate, scenario, rule-based or index) and the *source* it came from. Synthetic data is labelled
at the top of the report and beside each section that uses it. All user-supplied text is HTML-escaped.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from app.domain.exploration import score_zones, zone_inputs_from_geojson
from app.domain.features import Scope
from app.domain.forecast_service import ForecastService, dataset_context
from app.domain.kpis import ProductionFilter, compute_overview
from app.domain.provenance import VALUE_KIND_LABELS, SourceType, ValueKind
from app.domain.recommendations import build_recommendations
from app.domain.sources import list_sources
from app.domain.store import DatasetStore
from app.domain.synthetic import DEMO_DATASET_ID
from app.domain.synthetic_geo import DEMO_DRILLHOLES_DATASET_ID, DEMO_ZONES_DATASET_ID
from app.errors import AppError
from app.schemas.datasets import DatasetManifest

REPORT_VERSION = "report-v1"
ALL_SECTIONS: tuple[str, ...] = ("overview", "forecast", "risk", "recommendations", "exploration", "sources")
SYNTHETIC_TEXT = (
    "SYNTHETIC DEMONSTRATION DATA. This report uses invented records to show how MineMind AI works. "
    "It is not MOIL operational data, not a resource or reserve statement, and not evidence of real performance."
)


_CSS = """body { font-family: "IBM Plex Sans", system-ui, Arial, sans-serif; color:#14191c; margin: 2rem auto; max-width: 980px; line-height: 1.45; padding: 0 1rem; }
h1 { font-size: 1.6rem; margin-bottom: .2rem; } h2 { font-size: 1.2rem; border-bottom: 1px solid #dfdacd; padding-bottom: .3rem; margin-top: 2rem; }
h3 { font-size: 1rem; margin-top: 1.2rem; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; font-size: .9rem; }
caption { text-align: left; font-weight: 600; padding: .3rem 0; color:#3b4348; }
th, td { border-bottom: 1px solid #eceff1; padding: .35rem .5rem; text-align: left; vertical-align: top; }
thead th { background: #eceff1; }
.banner { border-left: 6px solid #c98a1b; background: #fdf8ec; padding: .8rem 1rem; margin: 1rem 0; }
.meta { color:#5d656a; font-size:.85rem; }
.tag { display:inline-block; border:1px solid #9aa3a9; border-radius:4px; padding:0 .4rem; font-size:.75rem; margin-right:.3rem; }
.tag.src { border-color:#c98a1b; background:#fbf0d9; }
.band { font-size: 1.1rem; } .band-high { color:#8e2f21; } .band-medium { color:#7a5110; } .band-low { color:#1f4d3a; }
.legend th { border: none; font-weight: 500; padding: .15rem .5rem .15rem 0; }
article { border: 1px solid #dfdacd; border-radius: 6px; padding: .6rem 1rem; margin: .8rem 0; }
footer { margin-top: 2.5rem; color:#5d656a; font-size:.8rem; border-top:1px solid #dfdacd; padding-top:.8rem; }
"""


def _label(kind: ValueKind | str) -> str:
    return VALUE_KIND_LABELS[ValueKind(kind)]


def _fmt(value: Any, digits: int = 0) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def build_report(
    *,
    store: DatasetStore,
    service: ForecastService,
    dataset_id: str | None,
    mine_id: str | None,
    zone_id: str | None,
    start: date | None,
    end: date | None,
    horizon_days: int,
    sections: list[str],
    title: str,
    stale_days: int,
    zones_dataset_id: str | None = None,
    drillholes_dataset_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    manifest: DatasetManifest = store.get_manifest(dataset_id or DEMO_DATASET_ID)
    if manifest.kind != "production":
        raise AppError("Reports need a production dataset.", status_code=422, code="wrong_dataset_kind")
    now = now or datetime.now(UTC)
    scope = Scope(mine_id=mine_id or None, zone_id=zone_id or None)
    frame = store.load_production(manifest.id)
    context = dataset_context(manifest)
    result: dict[str, Any] = {
        "report_version": REPORT_VERSION,
        "title": title,
        "generated_at": now.isoformat(timespec="seconds"),
        "dataset": {k: context[k] for k in ("id", "name", "source_type", "source_label", "is_synthetic")},
        "scope": {"mine_id": scope.mine_id, "zone_id": scope.zone_id, "label": scope.label},
        "period": {"start": start.isoformat() if start else None, "end": end.isoformat() if end else None},
        "synthetic_notice": SYNTHETIC_TEXT if context["is_synthetic"] else None,
        "value_type_legend": {kind.value: VALUE_KIND_LABELS[kind] for kind in ValueKind},
        "sections": {},
    }
    flt = ProductionFilter(start=start, end=end, mine_id=mine_id or None, zone_id=zone_id or None)
    if "overview" in sections:
        overview = compute_overview(frame, flt, as_of=now.date(), stale_days=stale_days)
        result["sections"]["overview"] = {
            "value_type": ValueKind.MEASURED.value,
            "source": context["source_label"],
            "kpis": overview["kpis"],
            "period": overview["period"],
            "constraints": overview["constraints"],
            "zones": overview["zones"],
            "freshness": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in overview["freshness"].items()},
            "empty": overview["empty"],
        }
    if "forecast" in sections:
        payload = service.forecast_payload(manifest.id, scope, horizon_days, context)
        result["sections"]["forecast"] = {
            "value_type": ValueKind.FORECAST.value,
            "source": context["source_label"],
            "model": payload["model"],
            "evaluation": {
                "verdict": payload["evaluation"]["verdict"],
                "verdict_text": payload["evaluation"]["verdict_text"],
                "models": payload["evaluation"]["models"],
                "gap_to_best_baseline": payload["evaluation"]["gap_to_best_baseline"],
                "evaluation_start": payload["evaluation"]["evaluation_start"],
                "evaluation_end": payload["evaluation"]["evaluation_end"],
                "n_evaluated_days": payload["evaluation"]["n_evaluated_days"],
            },
            "classification": {
                k: payload["classification"][k]
                for k in ("verdict_text", "roc_auc", "brier_skill_pct", "base_rate", "n")
            },
            "totals": payload["forecast"]["totals"],
            "days": payload["forecast"]["days"],
            "scenario_assumptions": payload["forecast"]["scenario_assumptions"],
            "notes": payload["notes"],
        }
    if "risk" in sections:
        risk = service.risk_payload(manifest.id, scope, horizon_days, context)
        result["sections"]["risk"] = {
            "value_type": ValueKind.RULE_BASED.value,
            "band": risk["band"],
            "expected": risk["expected"],
            "shortfall_probability": risk["shortfall_probability"],
            "classification_check": risk["classification_check"],
            "limitations": risk["limitations"],
        }
    else:
        risk = None
    if "recommendations" in sections:
        recs = build_recommendations(frame, scope, today=now.date(), stale_days=stale_days, risk=risk)
        result["sections"]["recommendations"] = {
            "value_type": ValueKind.RULE_BASED.value,
            "as_of": recs["as_of"],
            "items": recs["recommendations"],
            "rules": recs["rules"],
            "notes": recs["notes"],
        }
    if "exploration" in sections:
        zones_id = zones_dataset_id or DEMO_ZONES_DATASET_ID
        holes_id = drillholes_dataset_id or DEMO_DRILLHOLES_DATASET_ID
        zones_manifest = store.get_manifest(zones_id)
        holes_manifest = store.get_manifest(holes_id)
        collection = json.loads(store.read_bytes(zones_id).decode("utf-8"))
        holes = pd.read_csv(store.data_path(holes_id), dtype={"hole_id": str, "zone_id": str})
        scored = score_zones(zone_inputs_from_geojson(collection, holes))
        synthetic = SourceType.SYNTHETIC in {
            SourceType(zones_manifest.source_type),
            SourceType(holes_manifest.source_type),
        }
        result["sections"]["exploration"] = {
            "value_type": ValueKind.INDEX.value,
            "source": "SYNTHETIC DEMONSTRATION DATA" if synthetic else "USER-PROVIDED DATA (not verified)",
            "zones_dataset": zones_manifest.name,
            "drillholes_dataset": holes_manifest.name,
            "ranking_enabled": scored["ranking_enabled"],
            "zones": scored["zones"],
            "weights": scored["weights"],
            "required_inputs": scored["required_inputs"],
            "not_a_reserve_estimate": True,
        }
    if "sources" in sections:
        result["sections"]["sources"] = {"value_type": "measured", "items": list_sources()}
    return result


def _table(headers: list[str], rows: list[list[str]], caption: str) -> str:
    head = "".join(f"<th scope='col'>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return (
        f"<table><caption>{html.escape(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )


def _section(title: str, value_type: str, source: str, body: str) -> str:
    return (
        f"<section><h2>{html.escape(title)}</h2>"
        f"<p class='meta'><span class='tag'>{html.escape(_label(value_type))}</span> "
        f"<span class='tag src'>{html.escape(source)}</span></p>{body}</section>"
    )


def render_html(report: dict[str, Any]) -> str:
    esc = html.escape
    sections = report["sections"]
    parts: list[str] = []
    banner = (
        "<div class='banner' role='note'><strong>SYNTHETIC DEMONSTRATION DATA</strong><br>"
        f"{esc(report['synthetic_notice'])}</div>"
        if report.get("synthetic_notice")
        else ""
    )
    legend_rows = "".join(
        f"<tr><th scope='row'>{esc(label)}</th></tr>" for label in report["value_type_legend"].values()
    )
    legend = (
        f"<table class='legend'><caption>Value types used in this report</caption><tbody>{legend_rows}</tbody></table>"
    )

    if "overview" in sections:
        o = sections["overview"]
        k = o["kpis"]
        kpi_rows = [
            ["Planned, matched days (t)", _fmt(k["planned_t"], 0)],
            ["Actual, matched days (t)", _fmt(k["actual_t"], 0)],
            ["Gap to plan (t)", _fmt(k["gap_t"], 0)],
            ["Attainment (%)", _fmt(k["attainment_pct"], 1)],
            ["Equipment downtime (h per zone-day)", _fmt(k["equipment_downtime_h_per_zone_day"], 2)],
            ["Coverage (% rows with actuals)", _fmt(k["coverage_pct"], 1)],
        ]
        zone_rows = [
            [
                z["mine_id"],
                z["zone_id"],
                _fmt(z["planned_t"], 0),
                _fmt(z["actual_t"], 0),
                _fmt(z["gap_t"], 0),
                _fmt(z["attainment_pct"], 1),
            ]
            for z in o["zones"]
        ]
        body = (
            _table(["Measure", "Value"], kpi_rows, "Overview KPIs")
            + "<h3>Zones</h3>"
            + _table(
                ["Mine", "Zone", "Planned (t)", "Actual (t)", "Gap (t)", "Attainment (%)"],
                zone_rows,
                "Zone performance",
            )
            + f"<p class='meta'>Last recorded actual: {esc(str(o['freshness']['last_actual_date']))}. "
            "Gap and attainment use matched days only.</p>"
        )
        parts.append(_section("Overview", "measured", report["dataset"]["source_label"], body))

    if "forecast" in sections:
        f = sections["forecast"]
        ev = f["evaluation"]
        model_rows = [[m["label"], _fmt(m["mae"], 1), _fmt(m["rmse"], 1), _fmt(m["n"])] for m in ev["models"]]
        totals = f["totals"]
        body = (
            f"<p>{esc(ev['verdict_text'])}</p>"
            + _table(["Method", "MAE (t/day)", "RMSE (t/day)", "Days"], model_rows, "Backtest comparison")
            + "<h3>Forward forecast</h3>"
        )
        if totals:
            body += _table(
                ["Quantity", "Value"],
                [
                    ["Planned (t)", _fmt(totals["plan_t"], 0)],
                    ["Forecast output (t)", _fmt(totals["forecast_t"], 0)],
                    ["Expected net gap (t, estimate)", _fmt(totals["net_gap_t"], 0)],
                    ["Net gap (% of plan, estimate)", _fmt(totals["net_gap_pct"], 2)],
                    ["Interval basis", totals["interval_basis"]],
                    ["Mean daily shortfall probability", _fmt(totals["mean_daily_shortfall_probability"], 3)],
                ],
                "Forward forecast totals",
            )
        body += "<p class='meta'>Scenario inputs: " + esc(f["scenario_assumptions"]["description"]) + "</p>"
        parts.append(_section("Forecast and backtest", "forecast", f["source"], body))

    if "risk" in sections:
        r = sections["risk"]
        band = r["band"]
        body = (
            f"<p class='band band-{esc(band['level'])}'><strong>Risk band: {esc(band['label'])}</strong></p>"
            f"<p>{esc(band['rule'])}</p>"
        )
        if r.get("expected"):
            e = r["expected"]
            body += _table(
                ["Quantity", "Value"],
                [
                    ["Expected net gap (t, estimate)", _fmt(e["net_gap_t"], 0)],
                    [
                        "Gap interval (t, estimate)",
                        f"{_fmt(e['gap_interval_low_t'], 0)} to {_fmt(e['gap_interval_high_t'], 0)}",
                    ],
                    ["Interval basis", e["interval_basis"]],
                ],
                "Expected shortfall",
            )
        body += "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in r["limitations"]) + "</ul>"
        parts.append(_section("Shortfall risk", "rule_based", report["dataset"]["source_label"], body))

    if "recommendations" in sections:
        rec = sections["recommendations"]
        items = rec["items"]
        if items:
            cards = []
            for item in items:
                impact = item["expected_impact"]
                impact_text = (
                    f"Estimated {_fmt(impact['value_t'], 0)} {esc(impact['unit'])}. {esc(impact['basis'])}"
                    if impact["status"] == "estimated"
                    else f"Not estimated. {esc(impact['basis'])}"
                )
                cards.append(
                    f"<article><h3>{esc(item['priority'].upper())}: {esc(item['title'])}</h3>"
                    f"<p>{esc(item['summary'])}</p><p><em>Evidence:</em> "
                    + "; ".join(
                        f"{esc(e['metric'])} {esc(_fmt(e['value']))} {esc(e['unit'])} ({esc(e['value_kind'])})"
                        for e in item["evidence"]
                    )
                    + f"</p><p><em>Expected impact:</em> {impact_text}</p>"
                    + "<ol>"
                    + "".join(f"<li>{esc(a)}</li>" for a in item["suggested_actions"])
                    + "</ol></article>"
                )
            body = "".join(cards)
        else:
            body = "<p>No rule triggered on this selection.</p>"
        checked = "".join(
            f"<li>{esc(r['title'])}: {'triggered' if r['fired'] else 'not triggered'}. {esc(r['reason'])}</li>"
            for r in rec["rules"]
        )
        body += f"<h3>Rules checked</h3><ul>{checked}</ul>"
        parts.append(_section("Recommendations", "rule_based", report["dataset"]["source_label"], body))

    if "exploration" in sections:
        ex = sections["exploration"]
        zone_rows = [
            [
                z["zone_id"],
                z["status"],
                _fmt(z["drillholes"]),
                _fmt(z["score"], 2),
                _fmt(z["rank"]) if z["rank"] is not None else "not ranked",
                z["ranking_reason"],
            ]
            for z in ex["zones"]
        ]
        body = (
            "<p><strong>Priority index, not a probability or reserve estimate.</strong> Scores use only "
            "geological and drilling indicators; vegetation, rainfall and similar indices are context only.</p>"
            + _table(["Zone", "Status", "Drillholes", "Index (0-1)", "Rank", "Reason"], zone_rows, "Exploration zones")
            + "<h3>Inputs required before any real assessment</h3><ul>"
            + "".join(f"<li>{esc(item)}</li>" for item in ex["required_inputs"])
            + "</ul>"
        )
        parts.append(_section("Exploration zone prioritisation", "index", ex["source"], body))

    if "sources" in sections:
        rows = [
            [s["name"], s["licence"], s["attribution"], "; ".join(s["limitations"])]
            for s in sections["sources"]["items"]
        ]
        body = _table(["Source", "Licence", "Attribution", "Limitations"], rows, "Data sources")
        parts.append(_section("Data sources and licences", "measured", "Registry", body))

    generated = esc(report["generated_at"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(report["title"])}</title>
<style>{_CSS}</style>
</head>
<body>
<header>
<p class="meta">MineMind AI - SIH26009 prototype report</p>
<h1>{esc(report["title"])}</h1>
<p class="meta">Dataset: {esc(report["dataset"]["name"])} ({esc(report["dataset"]["source_label"])}).
Scope: {esc(report["scope"]["label"])}. Generated {generated} UTC.</p>
</header>
{banner}
<section><h2>How to read this report</h2>
<p>Each section is labelled with its value type and source. A forecast is a model output, an estimate is arithmetic on
stated assumptions, a probability comes from a classifier or from backtest frequencies, a rule-based value follows a
written threshold, and an index is a weighted combination of indicators.</p>
{legend}</section>
{"".join(parts)}
<footer>
<p>Not a resource or reserve statement. Not a licence, legal boundary or drilling decision. Verify with a competent
geologist and with operational records before acting. Report generated by {esc(REPORT_VERSION)}.</p>
</footer>
</body>
</html>"""


__all__ = ["ALL_SECTIONS", "build_report", "render_html"]
