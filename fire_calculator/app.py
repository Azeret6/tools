#!/usr/bin/env python3
"""
FIRE Calculator -- Web UI
==========================

A small Flask web app providing the same FIRE (Financial Independence)
calculation as `fire_calculator.py`, with a browser form (sliders for
the adjustable assumptions, an interactive chart) instead of
command-line prompts.

This file contains NO calculation logic of its own. It only collects
input from an HTML form, hands it to the functions in
`fire_calculator.py` (the single source of truth, shared with the CLI),
and renders the result. The CLI script keeps working exactly as before
-- this is an additional way to use the same calculator, not a
replacement.

The chart itself is rendered client-side (Chart.js, via CDN) for
interactivity (hover to see exact values at any point in time). This
file only computes the data points -- all the underlying math is still
exactly the same shared calculation, just serialized as JSON instead of
drawn as a static image.

Run it with:

    pip install -r requirements.txt
    python3 app.py

Then open http://127.0.0.1:5000 in your browser.
"""

from __future__ import annotations

import datetime as _dt
import io
import os
import threading
import webbrowser

from flask import Blueprint, Flask, render_template, request

import fire_calculator as fc

bp = Blueprint(
    "fire_calculator",
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


def _to_epoch_ms(d: _dt.date) -> int:
    """Convert a date to epoch milliseconds (UTC), for plotting on a
    Chart.js linear x-axis (avoids needing a date-adapter plugin while
    still keeping points correctly spaced in real time)."""
    return int(_dt.datetime(d.year, d.month, d.day, tzinfo=_dt.timezone.utc).timestamp() * 1000)


def _build_chart_payload(inputs: fc.FireInputs, result: fc.FireResult, history) -> dict:
    """Compute the JSON-serializable data the client-side chart needs:
    the projection curve, the recorded history (if any), a horizontal
    target line, and the crossing-point marker."""
    dates, balances = fc.compute_projection_series(inputs, result)
    projection_points = [{"x": _to_epoch_ms(d), "y": round(v, 2)} for d, v in zip(dates, balances)]

    history_points = []
    if history:
        history_points = [{"x": _to_epoch_ms(d), "y": v} for d, v in history]

    all_x = [p["x"] for p in projection_points] + [p["x"] for p in history_points]
    target_points = []
    if all_x:
        target_points = [
            {"x": min(all_x), "y": result.fire_number},
            {"x": max(all_x), "y": result.fire_number},
        ]

    marker_point = None
    if result.months_to_fire is not None and result.fire_date is not None:
        marker_point = {
            "x": _to_epoch_ms(result.fire_date),
            "y": result.fire_number,
            "label": f"{result.fire_date.strftime('%B %Y')} ({result.years_part}y {result.months_part}m)",
        }

    coast_target_points = []
    coast_marker_point = None
    if result.coast_fire_number is not None and all_x:
        coast_target_points = [
            {"x": min(all_x), "y": result.coast_fire_number},
            {"x": max(all_x), "y": result.coast_fire_number},
        ]
        if result.already_coast:
            coast_marker_point = {
                "x": _to_epoch_ms(inputs.as_of_date),
                "y": result.coast_fire_number,
                "label": "Already Coast FIRE!",
            }
        elif result.coast_date is not None:
            coast_marker_point = {
                "x": _to_epoch_ms(result.coast_date),
                "y": result.coast_fire_number,
                "label": f"Coast FIRE: {result.coast_date.strftime('%B %Y')} ({result.years_coast}y {result.months_coast}m)",
            }

    return {
        "projection": projection_points,
        "history": history_points,
        "target": target_points,
        "marker": marker_point,
        "fireNumber": result.fire_number,
        "coastTarget": coast_target_points,
        "coastMarker": coast_marker_point,
        "coastFireNumber": result.coast_fire_number,
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    values = {
        "current_net_worth": "",
        "annual_income": "",
        "monthly_savings": "",
        "nominal_return_pct": fc.DEFAULT_NOMINAL_RETURN_PCT,
        "inflation_pct": fc.DEFAULT_INFLATION_PCT,
        "withdrawal_rate_pct": fc.DEFAULT_WITHDRAWAL_RATE_PCT,
        "savings_growth_pct": fc.DEFAULT_SAVINGS_GROWTH_PCT,
        "partial_fire": False,
        "desired_monthly_income": "",
        "coast_fire": False,
        "current_age": "",
        "retirement_age": "",
        "savings_target": False,
        "savings_target_income": "",
        "savings_target_years": "",
    }
    context = {
        "values": values,
        "withdrawal_min": fc.WITHDRAWAL_RATE_MIN_PCT,
        "withdrawal_max": fc.WITHDRAWAL_RATE_MAX_PCT,
        "result": None,
        "display": None,
        "error": None,
        "chart_payload": None,
        "history_count": None,
        "reference_table": None,
    }

    if request.method == "POST":
        form = request.form

        values["current_net_worth"] = form.get("current_net_worth", "")
        values["annual_income"] = form.get("annual_income", "")
        values["monthly_savings"] = form.get("monthly_savings", "")
        values["nominal_return_pct"] = _parse_form_float(
            form, "nominal_return_pct", values["nominal_return_pct"]
        )
        values["inflation_pct"] = _parse_form_float(
            form, "inflation_pct", values["inflation_pct"]
        )
        values["withdrawal_rate_pct"] = _parse_form_float(
            form, "withdrawal_rate_pct", values["withdrawal_rate_pct"]
        )
        values["savings_growth_pct"] = _parse_form_float(
            form, "savings_growth_pct", values["savings_growth_pct"]
        )
        values["partial_fire"] = form.get("partial_fire") == "on"
        values["desired_monthly_income"] = form.get("desired_monthly_income", "")
        values["coast_fire"] = form.get("coast_fire") == "on"
        values["current_age"] = form.get("current_age", "")
        values["retirement_age"] = form.get("retirement_age", "")
        values["savings_target"] = form.get("savings_target") == "on"
        values["savings_target_income"] = form.get("savings_target_income", "")
        values["savings_target_years"] = form.get("savings_target_years", "")

        history = None
        as_of_date = _dt.date.today()
        current_net_worth = _parse_form_float(form, "current_net_worth", default=0.0)

        uploaded = request.files.get("savings_diary")
        if uploaded and uploaded.filename:
            try:
                text_stream = io.TextIOWrapper(uploaded.stream, encoding="utf-8")
                history = fc.parse_savings_csv(text_stream)
            except ValueError as exc:
                context["error"] = f"Could not read the savings diary: {exc}"

            if history:
                as_of_date, current_net_worth = history[-1]
                values["current_net_worth"] = current_net_worth
                context["history_count"] = len(history)
            elif not context["error"]:
                context["error"] = (
                    "No valid rows found in that savings diary -- check it has "
                    "'date' and 'net_worth' columns."
                )

        annual_income = _parse_form_float(form, "annual_income")
        monthly_savings = _parse_form_float(form, "monthly_savings")
        desired_monthly_income = _parse_form_float(form, "desired_monthly_income")
        current_age_raw = form.get("current_age", "").strip()
        retirement_age_raw = form.get("retirement_age", "").strip()
        current_age = int(current_age_raw) if current_age_raw.isdigit() else None
        retirement_age = int(retirement_age_raw) if retirement_age_raw.isdigit() else None

        if not context["error"] and (
            annual_income is None or monthly_savings is None
        ):
            context["error"] = (
                "Please fill in annual income and monthly savings."
            )

        if not context["error"] and values["partial_fire"] and not (
            desired_monthly_income and desired_monthly_income > 0
        ):
            context["error"] = (
                "Please enter a desired monthly amount for partial FIRE "
                "(or untick the checkbox to calculate full FIRE instead)."
            )

        if not context["error"] and values["coast_fire"] and (
            current_age is None or retirement_age is None
            or retirement_age <= current_age
        ):
            context["error"] = (
                "For Coast FIRE, please enter a valid current age and a "
                "retirement age that is higher than your current age."
            )

        savings_target_income = _parse_form_float(form, "savings_target_income")
        savings_target_years = _parse_form_float(form, "savings_target_years")

        if not context["error"] and values["savings_target"] and (
            not savings_target_income or savings_target_income <= 0
            or not savings_target_years or savings_target_years <= 0
        ):
            context["error"] = (
                "For the savings target, please enter a positive desired "
                "monthly income and a savings horizon in years."
            )

        if not context["error"]:
            try:
                inputs = fc.FireInputs(
                    current_net_worth=current_net_worth,
                    annual_income=annual_income,
                    monthly_savings=monthly_savings,
                    nominal_return_pct=values["nominal_return_pct"],
                    inflation_pct=values["inflation_pct"],
                    withdrawal_rate_pct=values["withdrawal_rate_pct"],
                    savings_growth_pct=values["savings_growth_pct"],
                    as_of_date=as_of_date,
                    partial_fire=values["partial_fire"],
                    desired_monthly_income=desired_monthly_income,
                    coast_fire=values["coast_fire"],
                    current_age=current_age,
                    retirement_age=retirement_age,
                    savings_target=values["savings_target"],
                    savings_target_income=savings_target_income,
                    savings_target_years=savings_target_years,
                )
                result = fc.calculate_fire(inputs)
            except ValueError as exc:
                context["error"] = str(exc)
            else:
                context["result"] = result
                context["display"] = {
                    "savings_rate_pct": f"{result.savings_rate_pct:.1f}",
                    "annual_expenses": f"{result.annual_expenses:,.0f}",
                    "fire_number": f"{result.fire_number:,.0f}",
                    "real_return_pct": f"{result.real_return_pct:.1f}",
                    "reachable": result.months_to_fire is not None,
                    "is_partial": result.is_partial,
                    "savings_growth_active": abs(values["savings_growth_pct"]) > 0.01,
                    "real_savings_growth_pct": f"{result.real_savings_growth_pct:.1f}",
                }
                if result.months_to_fire is not None:
                    context["display"]["years"] = result.years_part
                    context["display"]["months"] = result.months_part
                    context["display"]["fire_date"] = result.fire_date.strftime("%B %Y")
                if result.is_partial:
                    context["display"]["desired_monthly_income_today"] = (
                        f"{result.desired_monthly_income_today:,.0f}"
                    )
                    if result.desired_monthly_income_future is not None:
                        context["display"]["desired_monthly_income_future"] = (
                            f"{result.desired_monthly_income_future:,.0f}"
                        )
                        context["display"]["future_year"] = result.fire_date.year
                if result.coast_fire_number is not None:
                    context["display"]["coast_fire_number"] = f"{result.coast_fire_number:,.0f}"
                    context["display"]["already_coast"] = result.already_coast
                    if not result.already_coast and result.coast_date is not None:
                        context["display"]["years_coast"] = result.years_coast
                        context["display"]["months_coast"] = result.months_coast
                        context["display"]["coast_date"] = result.coast_date.strftime("%B %Y")

                if result.st_target_amount is not None:
                    context["display"]["st_target_amount"] = f"{result.st_target_amount:,.0f}"
                    context["display"]["st_required_monthly"] = f"{result.st_required_monthly:,.0f}"
                    context["display"]["st_years"] = int(values["savings_target_years"])
                    context["display"]["st_income"] = f"{savings_target_income:,.0f}"
                    gap = result.st_gap
                    context["display"]["st_gap"] = f"{abs(gap):,.0f}"
                    context["display"]["st_gap_positive"] = gap > 0
                    context["display"]["st_already_enough"] = gap <= 0

                context["chart_payload"] = _build_chart_payload(inputs, result, history)

    reference_rows = fc.savings_rate_reference_table(
        values["nominal_return_pct"], values["inflation_pct"], values["withdrawal_rate_pct"]
    )
    for row in reference_rows:
        row["years_display"] = f"{row['years']:.1f}" if row["years"] is not None else "not reachable"
    context["reference_table"] = reference_rows

    from flask import current_app
    context["hub_tools"] = current_app.config.get("HUB_TOOLS")
    context["hub_active"] = "fire_calculator"
    return render_template("fire_calculator/index.html", **context)


def create_app() -> Flask:
    """Build a standalone Flask app around this tool's blueprint, so it
    can still be run on its own (`python3 app.py`). The hub instead
    imports `bp` directly and mounts it alongside the other tools."""
    standalone = Flask(__name__)
    standalone.register_blueprint(bp)
    return standalone


if __name__ == "__main__":
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    create_app().run(debug=True)
