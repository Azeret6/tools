"""
app.py - web interface for the child savings calculator.

This file has no calculation logic of its own. It collects form input,
calls the shared functions in child_savings_calculator.py, and returns
the result as JSON for the page's JavaScript to render into the results
panel and chart. Same split as savings_target_calculator.
"""

import os
import threading
import webbrowser

from flask import Blueprint, Flask, current_app, render_template, request, jsonify

from child_savings_calculator import (
    ChildSavingsInputs,
    calculate_child_savings,
    duration_months_from_age,
    DEFAULT_NOMINAL_RETURN_PCT,
    DEFAULT_INFLATION_PCT,
    DEFAULT_WITHDRAWAL_RATE_PCT,
    DEFAULT_END_AGE_YEARS,
)

bp = Blueprint(
    "child_savings_calculator",
    __name__,
    template_folder="templates",
    static_folder="static",
)

DEFAULTS = {
    "monthly_contribution": 2000,
    "years": 15,
    "current_age_years": 5,
    "current_age_months": 0,
    "end_age_years": DEFAULT_END_AGE_YEARS,
    "starting_balance": 0,
    "nominal_return_pct": DEFAULT_NOMINAL_RETURN_PCT,
    "inflation_pct": DEFAULT_INFLATION_PCT,
    "withdrawal_rate_pct": DEFAULT_WITHDRAWAL_RATE_PCT,
}


@bp.route("/")
def index():
    return render_template(
        "child_savings_calculator/index.html",
        defaults=DEFAULTS,
        hub_tools=current_app.config.get("HUB_TOOLS"),
        hub_active="child_savings_calculator",
    )


def _to_float(data, key, default=0.0):
    raw = data.get(key)
    if raw is None or raw == "":
        return default
    return float(raw)


@bp.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json(silent=True) or {}

    try:
        horizon_mode = data.get("horizon_mode", "years")
        if horizon_mode == "age":
            current_age_years = int(_to_float(data, "current_age_years", 0))
            current_age_months = int(_to_float(data, "current_age_months", 0))
            end_age_years = _to_float(data, "end_age_years", DEFAULT_END_AGE_YEARS)
            duration_months = duration_months_from_age(
                current_age_years, current_age_months, end_age_years
            )
        else:
            years = _to_float(data, "years", 0)
            duration_months = round(years * 12)

        inputs = ChildSavingsInputs(
            monthly_contribution=_to_float(data, "monthly_contribution", 0),
            duration_months=duration_months,
            starting_balance=_to_float(data, "starting_balance", 0),
            nominal_return_pct=_to_float(data, "nominal_return_pct", DEFAULT_NOMINAL_RETURN_PCT),
            inflation_pct=_to_float(data, "inflation_pct", DEFAULT_INFLATION_PCT),
            withdrawal_rate_pct=_to_float(data, "withdrawal_rate_pct", DEFAULT_WITHDRAWAL_RATE_PCT),
        )
        result = calculate_child_savings(inputs)
    except (KeyError, ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    def scenario_json(s):
        return {
            "label": s.label,
            "final_balance": s.final_balance,
            "final_balance_today": s.final_balance_today,
            "total_contributed": s.total_contributed,
            "total_growth": s.total_growth,
            "monthly_income": s.monthly_income,
            "monthly_income_today": s.monthly_income_today,
            "final_contribution": s.final_contribution,
            "projection": [{"month": m, "value": v} for m, v in s.projection],
        }

    return jsonify(
        {
            "duration_months": result.duration_months,
            "duration_years_part": result.duration_years_part,
            "duration_months_part": result.duration_months_part,
            "flat": scenario_json(result.flat),
            "rising": scenario_json(result.rising),
        }
    )


def create_app() -> Flask:
    """Build a standalone Flask app around this tool's blueprint, so it
    can still be run on its own (`python3 app.py`) exactly as before."""
    standalone = Flask(__name__)
    standalone.register_blueprint(bp)
    return standalone


if __name__ == "__main__":
    # Open the app in the system's default browser shortly after the
    # server starts -- avoids it opening inside VS Code's "Simple
    # Browser" panel instead of a real browser window. The env check
    # ensures this only fires once (not once per Werkzeug reloader
    # process) when running with debug=True.
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    create_app().run(debug=True)
