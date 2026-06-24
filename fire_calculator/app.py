#!/usr/bin/env python3
"""
FIRE Calculator -- Web UI
==========================

A small Flask web app providing the same FIRE (Financial Independence)
calculation as `fire_calculator.py`, with a browser form (sliders for
the adjustable assumptions) instead of command-line prompts.

This file contains NO calculation logic of its own. It only collects
input from an HTML form, hands it to the functions in
`fire_calculator.py` (the single source of truth, shared with the CLI),
and renders the result. The CLI script keeps working exactly as before
-- this is an additional way to use the same calculator, not a
replacement.

Run it with:

    pip install -r requirements.txt
    python3 app.py

Then open http://127.0.0.1:5000 in your browser.
"""

from __future__ import annotations

import base64
import datetime as _dt
import io

import matplotlib
matplotlib.use("Agg")  # No GUI needed: we render charts to PNG bytes.
import matplotlib.pyplot as plt

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


@app.route("/", methods=["GET", "POST"])
def index():
    values = {
        "current_net_worth": "",
        "annual_income": "",
        "monthly_savings": "",
        "nominal_return_pct": fc.DEFAULT_NOMINAL_RETURN_PCT,
        "inflation_pct": fc.DEFAULT_INFLATION_PCT,
        "withdrawal_rate_pct": fc.DEFAULT_WITHDRAWAL_RATE_PCT,
    }
    context = {
        "values": values,
        "withdrawal_min": fc.WITHDRAWAL_RATE_MIN_PCT,
        "withdrawal_max": fc.WITHDRAWAL_RATE_MAX_PCT,
        "result": None,
        "display": None,
        "error": None,
        "chart_data_uri": None,
        "history_count": None,
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

        if not context["error"] and (
            current_net_worth is None or annual_income is None or monthly_savings is None
        ):
            context["error"] = (
                "Please fill in current net worth, annual income, and monthly savings."
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
                )
                result = fc.calculate_fire(inputs)
            except ValueError as exc:
                context["error"] = str(exc)
            else:
                context["result"] = result
                context["display"] = {
                    "annual_expenses": f"{result.annual_expenses:,.0f}",
                    "fire_number": f"{result.fire_number:,.0f}",
                    "real_return_pct": f"{result.real_return_pct:.1f}",
                    "reachable": result.months_to_fire is not None,
                }
                if result.months_to_fire is not None:
                    context["display"]["years"] = result.years_part
                    context["display"]["months"] = result.months_part
                    context["display"]["fire_date"] = result.fire_date.strftime("%B %Y")

                fig = fc.build_projection_figure(inputs, result, history=history)
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=130)
                plt.close(fig)
                buf.seek(0)
                encoded = base64.b64encode(buf.read()).decode("ascii")
                context["chart_data_uri"] = f"data:image/png;base64,{encoded}"

    return render_template("index.html", **context)


if __name__ == "__main__":
    app.run(debug=True)
