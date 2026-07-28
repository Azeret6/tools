#!/usr/bin/env python3
"""
Raise Calculator -- Web UI
===========================

A small Flask web app providing the same raise-impact calculation as
`raise_calculator.py`, with a browser form (sliders for the adjustable
assumptions, an interactive chart) instead of command-line prompts.

This file contains NO calculation logic of its own. It only collects
input from an HTML form, hands it to the functions in
`raise_calculator.py` (the single source of truth, shared with the
CLI), and renders the result. The CLI script keeps working exactly as
before -- this is an additional way to use the same calculator, not a
replacement.

This tool has no dependency on any other tool in this repository and
can be copied and used entirely on its own -- notably, it does NOT
import fire_calculator (or any sibling tool); all the math it needs
lives in raise_calculator.py.

The chart itself is rendered client-side (Chart.js, via CDN) for
interactivity. This file only computes the data points.

Run it with:

    pip install -r requirements.txt
    python3 app.py

Then open http://127.0.0.1:5000 in your browser.
"""

from __future__ import annotations

import os
import threading
import webbrowser

from flask import Blueprint, Flask, current_app, jsonify, render_template, request

import raise_calculator as rc

bp = Blueprint(
    "raise_calculator",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Same colours used by the CLI's matplotlib chart (build_comparison_figure),
# so the web chart and the CLI chart look consistent with each other.
_SCENARIO_COLORS = {
    "current_path": "#475569",       # slate -- nothing changes
    "raise_uninvested": "#d97706",   # amber -- idle cash
    "raise_invested": "#16a34a",     # green -- growth
}


def _parse_form_float(form, name: str, default: float | None = None) -> float | None:
    """Parse a form field as a float, accepting comma as a decimal
    separator. Returns `default` if the field is blank or invalid."""
    raw = (form.get(name) or "").strip().replace(",", ".")
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _build_chart_payload(result: rc.RaiseComparisonResult) -> dict:
    """Compute the JSON-serializable data the client-side chart needs:
    one series per scenario (years-from-now -> net worth), and an
    optional horizontal FIRE target line."""
    series = [
        {
            "label": s.label,
            "color": _SCENARIO_COLORS.get(s.key, "#2563eb"),
            "points": [{"x": year, "y": round(value, 2)} for year, value in s.net_worth_by_year],
        }
        for s in result.scenarios
    ]

    target_points = []
    if result.fire_target is not None:
        target_points = [
            {"x": 0, "y": result.fire_target},
            {"x": result.horizon_years, "y": result.fire_target},
        ]

    return {"series": series, "target": target_points}


def _build_diffs(result: rc.RaiseComparisonResult) -> list[str]:
    """Human-readable comparison lines for the callout box: how much
    sooner (if a FIRE target is set) and how much richer (always)
    investing the raise leaves you, vs. the other two scenarios."""
    by_key = {s.key: s for s in result.scenarios}
    current = by_key.get("current_path")
    uninvested = by_key.get("raise_uninvested")
    invested = by_key.get("raise_invested")
    if not (current and uninvested and invested):
        return []

    diffs: list[str] = []

    if result.fire_target is not None:
        def _time_diff(label: str, slower, faster) -> None:
            if slower.years_to_target is None or faster.years_to_target is None:
                return
            diff_years = slower.years_to_target - faster.years_to_target
            if diff_years > 0.05:
                years_part = int(diff_years)
                months_part = round((diff_years - years_part) * 12)
                diffs.append(f"Investing the raise vs. {label}: {years_part}y {months_part}m sooner.")

        _time_diff("the current path", current, invested)
        _time_diff("keeping it as cash", uninvested, invested)

    # Always show a value-based comparison at the end of the horizon too,
    # since not everyone sets a FIRE target.
    final_current = current.net_worth_by_year[-1][1]
    final_uninvested = uninvested.net_worth_by_year[-1][1]
    final_invested = invested.net_worth_by_year[-1][1]
    diffs.append(
        f"After {result.horizon_years} years, investing the raise leaves you with "
        f"{final_invested - final_current:,.0f} more than the current path, and "
        f"{final_invested - final_uninvested:,.0f} more than keeping it as cash."
    )

    return diffs


def _context(values: dict) -> dict:
    context = {
        "values": values,
        "withdrawal_min": rc.WITHDRAWAL_RATE_MIN_PCT,
        "withdrawal_max": rc.WITHDRAWAL_RATE_MAX_PCT,
        "result": None,
        "error": None,
        "chart_payload": None,
        "diffs": None,
        "hub_tools": current_app.config.get("HUB_TOOLS"),
        "hub_active": "raise_calculator",
    }
    return context


@bp.route("/", methods=["GET", "POST"])
def index():
    values = {
        "current_monthly_savings": "",
        "raise_amount": "",
        "current_net_worth": "",
        "compare_fire": False,
        "annual_expenses": "",
        "withdrawal_rate_pct": rc.DEFAULT_WITHDRAWAL_RATE_PCT,
        "nominal_return_pct": rc.DEFAULT_NOMINAL_RETURN_PCT,
        "inflation_pct": rc.DEFAULT_INFLATION_PCT,
        "projection_years": rc.DEFAULT_PROJECTION_YEARS,
    }

    error = None
    result = None
    chart_payload = None
    diffs = None

    if request.method == "POST":
        form = request.form

        values["current_monthly_savings"] = form.get("current_monthly_savings", "")
        values["raise_amount"] = form.get("raise_amount", "")
        values["current_net_worth"] = form.get("current_net_worth", "")
        values["compare_fire"] = form.get("compare_fire") == "on"
        values["annual_expenses"] = form.get("annual_expenses", "")
        values["withdrawal_rate_pct"] = _parse_form_float(
            form, "withdrawal_rate_pct", values["withdrawal_rate_pct"]
        )
        values["nominal_return_pct"] = _parse_form_float(
            form, "nominal_return_pct", values["nominal_return_pct"]
        )
        values["inflation_pct"] = _parse_form_float(
            form, "inflation_pct", values["inflation_pct"]
        )
        values["projection_years"] = int(_parse_form_float(
            form, "projection_years", values["projection_years"]
        ))

        current_monthly_savings = _parse_form_float(form, "current_monthly_savings")
        raise_amount = _parse_form_float(form, "raise_amount")
        current_net_worth = _parse_form_float(form, "current_net_worth", default=0.0)
        annual_expenses = (
            _parse_form_float(form, "annual_expenses") if values["compare_fire"] else None
        )

        if current_monthly_savings is None or raise_amount is None:
            error = "Please fill in current monthly savings and the net monthly raise."
        elif values["compare_fire"] and not (annual_expenses and annual_expenses > 0):
            error = (
                "Please enter annual expenses in retirement, or untick "
                "'Compare against a FIRE target'."
            )

        if not error:
            try:
                inputs = rc.RaiseInputs(
                    current_monthly_savings=current_monthly_savings,
                    raise_amount=raise_amount,
                    current_net_worth=current_net_worth or 0.0,
                    nominal_return_pct=values["nominal_return_pct"],
                    inflation_pct=values["inflation_pct"],
                    projection_years=values["projection_years"],
                    annual_expenses=annual_expenses,
                    withdrawal_rate_pct=values["withdrawal_rate_pct"],
                )
                result = rc.calculate_raise_scenarios(inputs)
            except ValueError as exc:
                error = str(exc)
            else:
                chart_payload = _build_chart_payload(result)
                diffs = _build_diffs(result)

    context = _context(values)
    context["error"] = error
    context["result"] = result
    context["chart_payload"] = chart_payload
    context["diffs"] = diffs

    if request.method == "POST" and request.args.get("json") == "1":
        return jsonify({
            "error": error,
            "chart_payload": chart_payload,
        })

    return render_template("raise_calculator/index.html", **context)


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
