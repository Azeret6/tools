"""
app.py -- web interface for the Savings Rate Explorer.

Interactive chart: savings rate (x-axis) vs. years to financial
independence (y-axis). No calculation logic lives here -- it all comes
from savings_rate_explorer.py.
"""

import os
import threading
import webbrowser

from flask import Blueprint, Flask, current_app, jsonify, render_template, request

import savings_rate_explorer as sre

bp = Blueprint(
    "savings_rate_explorer",
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


def _build_payload(inputs: sre.CurveInputs) -> dict:
    result = sre.compute_curve(inputs)
    points = [
        {
            "rate": p.rate_pct,
            "months": p.months,
            "years": p.years_part,
            "monthsPart": p.months_part,
            "label": f"{p.years_part}y {p.months_part}m" if p.months is not None else "never",
        }
        for p in result.points
    ]
    your_point = None
    if result.your_point is not None:
        your_point = {
            "rate": result.your_point.rate_pct,
            "months": result.your_point.months,
            "years": result.your_point.years_part,
            "monthsPart": result.your_point.months_part,
        }
    return {
        "points": points,
        "yourPoint": your_point,
        "realReturnPct": round(result.real_return_pct, 2),
    }


def _context(values: dict) -> dict:
    inputs = sre.CurveInputs(
        nominal_return_pct=values["nominal_return_pct"],
        inflation_pct=values["inflation_pct"],
        withdrawal_rate_pct=values["withdrawal_rate_pct"],
        your_rate_pct=values.get("your_rate_pct"),
    )
    return {
        "values": values,
        "chart_payload": _build_payload(inputs),
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    values = {
        "nominal_return_pct": sre.DEFAULT_NOMINAL_RETURN_PCT,
        "inflation_pct": sre.DEFAULT_INFLATION_PCT,
        "withdrawal_rate_pct": sre.DEFAULT_WITHDRAWAL_RATE_PCT,
        "your_rate_pct": None,
        "annual_income": "",
        "monthly_savings": "",
    }

    if request.method == "POST":
        form = request.form
        values["nominal_return_pct"] = _parse_float(form, "nominal_return_pct", values["nominal_return_pct"])
        values["inflation_pct"] = _parse_float(form, "inflation_pct", values["inflation_pct"])
        values["withdrawal_rate_pct"] = _parse_float(form, "withdrawal_rate_pct", values["withdrawal_rate_pct"])
        values["annual_income"] = form.get("annual_income", "")
        values["monthly_savings"] = form.get("monthly_savings", "")
        annual_income = _parse_float(form, "annual_income")
        monthly_savings = _parse_float(form, "monthly_savings")

        # If both income+savings AND a manual rate are present, the concrete
        # numbers win — a stray value left in the rate field must never
        # silently override numbers the person just typed.
        your_rate = None
        if annual_income and annual_income > 0 and monthly_savings is not None:
            your_rate = min(99.0, max(0.0, monthly_savings * 12 / annual_income * 100))
        else:
            your_rate = _parse_float(form, "your_rate_pct")
        values["your_rate_pct"] = your_rate

    context = _context(values)

    if request.method == "POST" and request.args.get("json") == "1":
        return jsonify(context["chart_payload"])

    return render_template(
        "savings_rate_explorer/index.html",
        hub_tools=current_app.config.get("HUB_TOOLS"),
        hub_active="savings_rate_explorer",
        **context,
    )


def create_app() -> Flask:
    """Build a standalone Flask app around this tool's blueprint, so it
    can still be run on its own (`python3 app.py`)."""
    standalone = Flask(__name__)
    standalone.register_blueprint(bp)
    return standalone


if __name__ == "__main__":
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    create_app().run(debug=True)
