"""
Monte Carlo FIRE Simulator -- Web UI

Same calculation as monte_carlo_simulator.py, with a browser form and
an interactive fan chart instead of the CLI's static output.

No cross-tool dependencies -- all the math lives in
monte_carlo_simulator.py, shared with the CLI.
"""

from __future__ import annotations

import os
import threading
import webbrowser

from flask import Blueprint, Flask, current_app, jsonify, render_template, request

import monte_carlo_simulator as mc

bp = Blueprint(
    "monte_carlo_simulator",
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


def _build_payload(inputs: mc.SimulationInputs) -> dict:
    result = mc.run_simulation(inputs)

    years = list(range(inputs.horizon_years + 1))
    band = {
        str(p): [round(v, 2) for v in result.percentile_paths[p]]
        for p in mc.PERCENTILES
    }

    return {
        "years": years,
        "band": band,
        "target": round(result.target, 4),
        "successRatePct": round(result.success_rate_pct, 1),
        "medianYears": round(result.median_years, 1) if result.median_years is not None else None,
        "percentileYears": {
            str(p): (round(v, 1) if v is not None else None)
            for p, v in result.percentile_years.items()
        },
        "numSimulations": result.num_simulations,
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    values = {
        "savings_rate_pct": 25,
        "withdrawal_rate_pct": mc.DEFAULT_WITHDRAWAL_RATE_PCT,
        "horizon_years": mc.DEFAULT_HORIZON_YEARS,
        "mean_return_pct": mc.DEFAULT_MEAN_RETURN_PCT,
        "return_std_dev_pct": mc.DEFAULT_RETURN_STD_DEV_PCT,
        "num_simulations": mc.DEFAULT_NUM_SIMULATIONS,
    }

    if request.method == "POST":
        form = request.form
        values["savings_rate_pct"] = _parse_float(form, "savings_rate_pct", values["savings_rate_pct"])
        values["withdrawal_rate_pct"] = _parse_float(form, "withdrawal_rate_pct", values["withdrawal_rate_pct"])
        values["horizon_years"] = int(_parse_float(form, "horizon_years", values["horizon_years"]))
        values["mean_return_pct"] = _parse_float(form, "mean_return_pct", values["mean_return_pct"])
        values["return_std_dev_pct"] = _parse_float(form, "return_std_dev_pct", values["return_std_dev_pct"])
        values["num_simulations"] = int(_parse_float(form, "num_simulations", values["num_simulations"]))

    inputs = mc.SimulationInputs(
        savings_rate_pct=values["savings_rate_pct"],
        withdrawal_rate_pct=values["withdrawal_rate_pct"],
        horizon_years=values["horizon_years"],
        mean_return_pct=values["mean_return_pct"],
        return_std_dev_pct=values["return_std_dev_pct"],
        num_simulations=values["num_simulations"],
    )
    chart_payload = _build_payload(inputs)

    context = {
        "values": values,
        "chart_payload": chart_payload,
        "withdrawal_min": mc.WITHDRAWAL_RATE_MIN_PCT,
        "withdrawal_max": mc.WITHDRAWAL_RATE_MAX_PCT,
        "max_horizon": mc.MAX_HORIZON_YEARS,
        "max_simulations": mc.MAX_NUM_SIMULATIONS,
        "hub_tools": current_app.config.get("HUB_TOOLS"),
        "hub_active": "monte_carlo_simulator",
    }

    if request.method == "POST" and request.args.get("json") == "1":
        return jsonify(chart_payload)

    return render_template("monte_carlo_simulator/index.html", **context)


def create_app() -> Flask:
    standalone = Flask(__name__)
    standalone.register_blueprint(bp)
    return standalone


if __name__ == "__main__":
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    create_app().run(debug=True)
