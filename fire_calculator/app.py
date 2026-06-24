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

from flask import Flask, render_template, request

import fire_calculator as fc

app = Flask(__name__)


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

    return {
        "projection": projection_points,
        "history": history_points,
        "target": target_points,
        "marker": marker_point,
        "fireNumber": result.fire_number,
    }


@app.route("/", methods=["GET", "POST"])
def index():
    values = {
        "current_net_worth": "",
        "annual_income": "",
        "monthly_savings": "",
        "nominal_return_pct": fc.DEFAULT_NOMINAL_RETURN_PCT,
        "inflation_pct": fc.DEFAULT_INFLATION_PCT,
        "withdrawal_rate_pct": fc.DEFAULT_WITHDRAWAL_RATE_PCT,
        "partial_fire": False,
        "desired_monthly_income": "",
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
        values["partial_fire"] = form.get("partial_fire") == "on"
        values["desired_monthly_income"] = form.get("desired_monthly_income", "")

        history = None
        as_of_date = _dt.date.today()
        current_net_worth = _parse_form_float(form, "current_net_worth")

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

        if not context["error"] and (
            current_net_worth is None or annual_income is None or monthly_savings is None
        ):
            context["error"] = (
                "Please fill in current net worth, annual income, and monthly savings."
            )

        if not context["error"] and values["partial_fire"] and not (
            desired_monthly_income and desired_monthly_income > 0
        ):
            context["error"] = (
                "Please enter a desired monthly amount for partial FIRE "
                "(or untick the checkbox to calculate full FIRE instead)."
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
                    as_of_date=as_of_date,
                    partial_fire=values["partial_fire"],
                    desired_monthly_income=desired_monthly_income,
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

                context["chart_payload"] = _build_chart_payload(inputs, result, history)

    reference_rows = fc.savings_rate_reference_table(
        values["nominal_return_pct"], values["inflation_pct"], values["withdrawal_rate_pct"]
    )
    for row in reference_rows:
        row["years_display"] = f"{row['years']:.1f}" if row["years"] is not None else "not reachable"
    context["reference_table"] = reference_rows

    return render_template("index.html", **context)


if __name__ == "__main__":
    app.run(debug=True)
