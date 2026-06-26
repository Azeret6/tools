#!/usr/bin/env python3
"""
Raise Calculator -- Web UI
============================

A small Flask web app providing the same raise-impact calculation as
`raise_calculator.py`, with a browser form (sliders for the adjustable
assumptions, an interactive chart) instead of command-line prompts.

This file contains NO calculation logic of its own. It only collects
input from an HTML form, hands it to the functions in
`raise_calculator.py` (the single source of truth, shared with the CLI),
and renders the result. The CLI script keeps working exactly as before
-- this is an additional way to use the same calculator, not a
replacement.

Run it on its own with:

    pip install -r requirements.txt
    python3 app.py

Then open http://127.0.0.1:5000 in your browser.
"""

from __future__ import annotations

from flask import Blueprint, Flask, current_app, render_template, request

import raise_calculator as rc

bp = Blueprint(
    "raise_calculator",
    __name__,
    template_folder="templates",
    static_folder="static",
)


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
    one series per scenario, plus an optional FIRE target line. Uses the
    same scenario colors as the matplotlib chart in raise_calculator.py,
    so the web and CLI versions look consistent."""
    colors = {
        "current_path": "#475569",
        "raise_uninvested": "#d97706",
        "raise_invested": "#16a34a",
    }

    series = []
    for scenario in result.scenarios:
        series.append(
            {
                "key": scenario.key,
                "label": scenario.label,
                "color": colors.get(scenario.key, "#2563eb"),
                "points": [{"x": year, "y": round(value, 2)} for year, value in scenario.net_worth_by_year],
                "yearsToTarget": scenario.years_to_target,
            }
        )

    target_points = []
    if result.fire_target is not None:
        target_points = [
            {"x": 0, "y": result.fire_target},
            {"x": result.horizon_years, "y": result.fire_target},
        ]

    return {
        "series": series,
        "target": target_points,
        "fireTarget": result.fire_target,
        "horizonYears": result.horizon_years,
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    values = {
        "current_monthly_savings": "",
        "raise_amount": "",
        "current_net_worth": "0",
        "compare_fire": False,
        "annual_expenses": "",
        "withdrawal_rate_pct": rc.DEFAULT_WITHDRAWAL_RATE_PCT,
        "nominal_return_pct": rc.DEFAULT_NOMINAL_RETURN_PCT,
        "inflation_pct": rc.DEFAULT_INFLATION_PCT,
        "projection_years": rc.DEFAULT_PROJECTION_YEARS,
    }
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

    if request.method == "POST":
        form = request.form

        values["current_monthly_savings"] = form.get("current_monthly_savings", "")
        values["raise_amount"] = form.get("raise_amount", "")
        values["current_net_worth"] = form.get("current_net_worth", "0")
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
        values["projection_years"] = _parse_form_float(
            form, "projection_years", values["projection_years"]
        )

        current_monthly_savings = _parse_form_float(form, "current_monthly_savings")
        raise_amount = _parse_form_float(form, "raise_amount")
        current_net_worth = _parse_form_float(form, "current_net_worth", 0.0)
        annual_expenses = (
            _parse_form_float(form, "annual_expenses") if values["compare_fire"] else None
        )

        if current_monthly_savings is None or raise_amount is None:
            context["error"] = "Please fill in current monthly savings and the raise amount."
        elif values["compare_fire"] and not annual_expenses:
            context["error"] = (
                "Enter annual expenses for the FIRE comparison, or untick the checkbox "
                "to skip it."
            )

        if not context["error"]:
            try:
                inputs = rc.RaiseInputs(
                    current_monthly_savings=current_monthly_savings,
                    raise_amount=raise_amount,
                    current_net_worth=current_net_worth,
                    nominal_return_pct=values["nominal_return_pct"],
                    inflation_pct=values["inflation_pct"],
                    projection_years=int(values["projection_years"]),
                    annual_expenses=annual_expenses,
                    withdrawal_rate_pct=values["withdrawal_rate_pct"],
                )
                result = rc.calculate_raise_scenarios(inputs)
            except ValueError as exc:
                context["error"] = str(exc)
            else:
                context["result"] = result
                context["chart_payload"] = _build_chart_payload(result)

                if result.fire_target is not None:
                    by_key = {s.key: s for s in result.scenarios}
                    diffs = []
                    pairs = [
                        ("Investing vs. the current path", by_key["current_path"], by_key["raise_invested"]),
                        ("Investing vs. keeping it as cash", by_key["raise_uninvested"], by_key["raise_invested"]),
                    ]
                    for label, slower, faster in pairs:
                        if slower.years_to_target is not None and faster.years_to_target is not None:
                            diff = slower.years_to_target - faster.years_to_target
                            if diff > 0.05:
                                years_part = int(diff)
                                months_part = round((diff - years_part) * 12)
                                diffs.append(f"{label}: {years_part}y {months_part}m sooner.")
                    context["diffs"] = diffs

    return render_template("raise_calculator/index.html", **context)


def create_app() -> Flask:
    """Build a standalone Flask app around this tool's blueprint, so it
    can still be run on its own (`python3 app.py`). The hub instead
    imports `bp` directly and mounts it alongside the other tools."""
    standalone = Flask(__name__)
    standalone.register_blueprint(bp)
    return standalone


if __name__ == "__main__":
    create_app().run(debug=True)
