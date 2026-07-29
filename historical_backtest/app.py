"""
Historical Backtest -- Web UI

Same calculation as historical_backtest.py, with a browser form and an
interactive chart instead of the CLI's static matplotlib image.

No cross-tool dependencies -- all the math lives in
historical_backtest.py, shared with the CLI.
"""

from __future__ import annotations

import os
import threading
import webbrowser

from flask import Blueprint, Flask, current_app, jsonify, render_template, request

import historical_backtest as hb

bp = Blueprint(
    "historical_backtest",
    __name__,
    template_folder="templates",
    static_folder="static",
)


def _parse_float(form, key, default=None):
    raw = (form.get(key) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _build_payload(inputs: hb.BacktestInputs) -> dict:
    result = hb.run_backtest(inputs)
    stats = hb.summary_stats(result)

    points = []
    for o in result.outcomes:
        if o.months_to_fire is not None:
            status = "reached"
            years = round(o.months_to_fire / 12, 2)
        elif o.ran_out_of_data:
            status = "insufficient_data"
            years = None
        else:
            status = "not_reached"
            years = None
        points.append({"year": o.start_year, "years": years, "status": status})

    return {
        "points": points,
        "target": round(result.target, 4),
        "monthlyContribution": round(result.monthly_contribution, 5),
        "reachableCount": result.reachable_count,
        "unreachableCount": result.unreachable_count,
        "insufficientCount": result.insufficient_data_count,
        "stats": {
            "successRatePct": round(stats["success_rate_pct"], 1),
            "bestYears": round(stats["best_years"], 1) if stats["best_years"] is not None else None,
            "medianYears": round(stats["median_years"], 1) if stats["median_years"] is not None else None,
            "worstYears": round(stats["worst_years"], 1) if stats["worst_years"] is not None else None,
            "totalWindows": stats["total_windows"],
        },
        "firstYear": hb.FIRST_YEAR,
        "lastYear": hb.LAST_YEAR,
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    values = {
        "savings_rate_pct": 25,
        "withdrawal_rate_pct": hb.DEFAULT_WITHDRAWAL_RATE_PCT,
        "horizon_years": hb.DEFAULT_HORIZON_YEARS,
    }

    if request.method == "POST":
        form = request.form
        values["savings_rate_pct"] = _parse_float(form, "savings_rate_pct", values["savings_rate_pct"])
        values["withdrawal_rate_pct"] = _parse_float(form, "withdrawal_rate_pct", values["withdrawal_rate_pct"])
        values["horizon_years"] = int(_parse_float(form, "horizon_years", values["horizon_years"]))

    inputs = hb.BacktestInputs(
        savings_rate_pct=values["savings_rate_pct"],
        withdrawal_rate_pct=values["withdrawal_rate_pct"],
        horizon_years=values["horizon_years"],
    )
    chart_payload = _build_payload(inputs)

    context = {
        "values": values,
        "chart_payload": chart_payload,
        "withdrawal_min": hb.WITHDRAWAL_RATE_MIN_PCT,
        "withdrawal_max": hb.WITHDRAWAL_RATE_MAX_PCT,
        "max_horizon": hb.MAX_HORIZON_YEARS,
        "hub_tools": current_app.config.get("HUB_TOOLS"),
        "hub_active": "historical_backtest",
    }

    if request.method == "POST" and request.args.get("json") == "1":
        return jsonify(chart_payload)

    return render_template("historical_backtest/index.html", **context)


def create_app() -> Flask:
    standalone = Flask(__name__)
    standalone.register_blueprint(bp)
    return standalone


if __name__ == "__main__":
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    create_app().run(debug=True)
