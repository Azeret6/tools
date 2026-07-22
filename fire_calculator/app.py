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

from flask import Blueprint, Flask, jsonify, render_template, request

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
    main_horizon_months = len(dates) - 1  # passed to scenarios so they match
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

    x_max = max((p["x"] for p in projection_points), default=None)

    # Milestones: 25 / 50 / 75 % of the FIRE target, with the date the
    # projection first crosses each. Shown as subtle dashed lines on the
    # chart and as a list in the results panel (b16).
    milestones = []
    for pct in (25, 50, 75):
        value = result.fire_number * pct / 100
        cross_ms = None
        for p in projection_points:
            if p["y"] >= value:
                cross_ms = p["x"]
                break
        milestones.append({"pct": pct, "y": value, "crossMs": cross_ms})

    return {
        "projection": projection_points,
        "history": history_points,
        "target": target_points,
        "marker": marker_point,
        "fireNumber": result.fire_number,
        "coastTarget": coast_target_points,
        "coastMarker": coast_marker_point,
        "coastFireNumber": result.coast_fire_number,
        "xMax": x_max,
        "mainHorizonMonths": main_horizon_months,
        "milestones": milestones,
        "asOfMs": _to_epoch_ms(inputs.as_of_date),
        "currentAge": inputs.current_age,
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
        "scenarios": False,
        "calc_mode": "time_to_fire",
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
        values["scenarios"] = form.get("scenarios") == "on"
        # New: calc_mode radio replaces the three checkboxes
        calc_mode = form.get("calc_mode", "time_to_fire")
        values["calc_mode"] = calc_mode
        # Map to existing flags so the rest of the logic is unchanged
        values["partial_fire"]   = calc_mode == "time_to_fire" and bool(form.get("desired_monthly_income", "").strip())
        values["coast_fire"]     = calc_mode == "coast_fire"
        values["savings_target"] = calc_mode == "required_savings"
        # In required_savings mode, desired_monthly_income doubles as savings_target_income
        if calc_mode == "required_savings":
            values["savings_target_income"] = form.get("desired_monthly_income", "")

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

        savings_target_income = _parse_form_float(
            form, "savings_target_income" if calc_mode != "required_savings" else "desired_monthly_income"
        )
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
                    context["display"]["st_years"] = round(float(values["savings_target_years"]), 1)
                    context["display"]["st_income"] = f"{savings_target_income:,.0f}"
                    gap = result.st_gap
                    context["display"]["st_gap"] = f"{abs(gap):,.0f}"
                    context["display"]["st_gap_positive"] = gap > 0
                    context["display"]["st_already_enough"] = gap <= 0

                # Nominal monthly income at retirement — what the withdrawal
                # will look like in the actual prices of the year you retire.
                if result.months_to_fire is not None:
                    years_to_fire = result.months_to_fire / 12
                    inflation = values["inflation_pct"] / 100
                    monthly_today = (
                        inputs.desired_monthly_income
                        if result.is_partial
                        else result.annual_expenses / 12
                    )
                    monthly_nominal = monthly_today * (1 + inflation) ** years_to_fire
                    context["display"]["monthly_income_today"] = f"{monthly_today:,.0f}"
                    context["display"]["monthly_income_nominal"] = f"{monthly_nominal:,.0f}"
                    context["display"]["fire_year"] = result.fire_date.year

                # Savings progression table (only when savings growth is active).
                if abs(values["savings_growth_pct"]) > 0.01 and result.months_to_fire is not None:
                    real_growth = result.real_savings_growth_pct / 100
                    inflation = values["inflation_pct"] / 100
                    # Nominal savings at year t = real_savings(t) * inflation_factor(t)
                    # because real = today's purchasing power, nominal = actual transfer amount
                    base = inputs.monthly_savings
                    max_year = max(int(result.months_to_fire / 12) + 1, 5)
                    checkpoints = sorted(set(
                        [1, 3, 5, 10, 15, 20, 25, 30, int(result.months_to_fire / 12)]
                    ))
                    milestones = []
                    for yr in checkpoints:
                        if yr < 1 or yr > max_year + 1:
                            continue
                        real_val = base * (1 + real_growth) ** yr
                        nom_val = real_val * (1 + inflation) ** yr
                        milestones.append({
                            "year": yr,
                            "real": f"{real_val:,.0f}",
                            "nominal": f"{nom_val:,.0f}",
                            "is_fire_year": yr == int(result.months_to_fire / 12),
                        })
                    context["display"]["savings_milestones"] = milestones

                context["chart_payload"] = _build_chart_payload(inputs, result, history)

                # Subtitle data for the badge above the chart — needed for live updates
                # because the badge is outside #results-area and isn't replaced by doLiveUpdate
                if result.is_partial and result.desired_monthly_income_today is not None:
                    _mode = "Partial FIRE"
                    _detail = (f"target {result.desired_monthly_income_today:,.0f}/mo"
                               f" · goal {result.fire_number:,.0f}"
                               + (f" · {result.fire_date.strftime('%B %Y')}" if result.fire_date else ""))
                else:
                    _mode = "Full FIRE"
                    _detail = (f"goal {result.fire_number:,.0f}"
                               + (f" · {result.fire_date.strftime('%B %Y')}" if result.fire_date else ""))
                context["chart_payload"]["subtitle"] = {"mode": _mode, "detail": _detail}

                # Milestones for the results panel (25/50/75 % of target + dates)
                _ms_display = []
                for m in context["chart_payload"].get("milestones", []):
                    if m["crossMs"] is not None:
                        _d = _dt.datetime.fromtimestamp(m["crossMs"] / 1000).strftime("%b %Y")
                    else:
                        _d = "—"
                    _ms_display.append({"pct": m["pct"], "amount": f"{m['y']:,.0f}", "date": _d})
                context["display"]["milestones"] = _ms_display

                # ±5 % savings rate scenarios
                if values["scenarios"] and result.months_to_fire is not None:
                    delta = inputs.annual_income * 5 / 100 / 12
                    scenario_defs = [
                        ("+5 % savings rate", +delta, "#2F6F52"),
                        ("−5 % savings rate", -delta, "#B3402F"),
                    ]

                    # Phase 1: compute all scenario results (no projections yet)
                    phase1 = []
                    for label, sign, color in scenario_defs:
                        new_savings = max(0.0, inputs.monthly_savings + delta * (1 if sign > 0 else -1))
                        inp_s = fc.FireInputs(
                            current_net_worth=inputs.current_net_worth,
                            annual_income=inputs.annual_income,
                            monthly_savings=new_savings,
                            nominal_return_pct=inputs.nominal_return_pct,
                            inflation_pct=inputs.inflation_pct,
                            withdrawal_rate_pct=inputs.withdrawal_rate_pct,
                            savings_growth_pct=inputs.savings_growth_pct,
                            as_of_date=inputs.as_of_date,
                        )
                        try:
                            res_s = fc.calculate_fire(inp_s)
                        except ValueError:
                            continue
                        phase1.append((label, color, inp_s, res_s))

                    # Phase 2: find the maximum natural horizon across all projections
                    def _natural_horizon(res):
                        if res.months_to_fire is not None:
                            h = max(round(res.months_to_fire * 1.15), round(res.months_to_fire) + 6)
                        else:
                            h = 40 * 12
                        if res.months_to_coast is not None:
                            h = max(h, round(res.months_to_coast) + 6)
                        return h

                    max_horizon = _natural_horizon(result)
                    for _, _, _, res_s in phase1:
                        max_horizon = max(max_horizon, _natural_horizon(res_s))

                    # Phase 3: recompute ALL projections with the unified horizon
                    dates_main, bal_main = fc.compute_projection_series(
                        inputs, result, min_horizon_months=max_horizon
                    )
                    context["chart_payload"]["projection"] = [
                        {"x": _to_epoch_ms(d), "y": round(v, 2)} for d, v in zip(dates_main, bal_main)
                    ]
                    new_x_max = context["chart_payload"]["projection"][-1]["x"]
                    context["chart_payload"]["xMax"] = new_x_max

                    # Extend horizontal target lines to new xMax
                    for key in ("target", "coastTarget"):
                        pts = context["chart_payload"].get(key)
                        if pts and len(pts) == 2:
                            pts[1]["x"] = new_x_max

                    # Recompute milestone crossings against the extended projection
                    new_milestones = []
                    for pct in (25, 50, 75):
                        value = result.fire_number * pct / 100
                        cross_ms = None
                        for p in context["chart_payload"]["projection"]:
                            if p["y"] >= value:
                                cross_ms = p["x"]
                                break
                        new_milestones.append({"pct": pct, "y": value, "crossMs": cross_ms})
                    context["chart_payload"]["milestones"] = new_milestones

                    scenario_results = []
                    main_fire_number = result.fire_number  # the target line on the chart
                    for label, color, inp_s, res_s in phase1:
                        dates_s, bal_s = fc.compute_projection_series(
                            inp_s, res_s, min_horizon_months=max_horizon
                        )
                        proj_s = [{"x": _to_epoch_ms(d), "y": round(v, 2)} for d, v in zip(dates_s, bal_s)]

                        marker_s = None
                        if result.is_partial:
                            # Partial FIRE: fixed target for all scenarios — find when
                            # scenario crosses the SAME target line (main_fire_number)
                            for d, v in zip(dates_s, bal_s):
                                if v >= main_fire_number:
                                    months_elapsed = (
                                        (d.year - inp_s.as_of_date.year) * 12
                                        + (d.month - inp_s.as_of_date.month)
                                    )
                                    yrs, mos = divmod(months_elapsed, 12)
                                    marker_s = {
                                        "x": _to_epoch_ms(d),
                                        "y": main_fire_number,
                                        "label": f"{label}: {d.strftime('%B %Y')} ({yrs}y {mos}m)",
                                    }
                                    break
                        else:
                            # Full FIRE: each scenario has its own target (different expenses).
                            # Show marker at scenario's own fire_number — dot sits on its
                            # own (implied) target level, making the difference visible.
                            if res_s.months_to_fire is not None and res_s.fire_date is not None:
                                months_elapsed = (
                                    (res_s.fire_date.year - inp_s.as_of_date.year) * 12
                                    + (res_s.fire_date.month - inp_s.as_of_date.month)
                                )
                                yrs, mos = divmod(months_elapsed, 12)
                                marker_s = {
                                    "x": _to_epoch_ms(res_s.fire_date),
                                    "y": res_s.fire_number,
                                    "label": f"{label}: {res_s.fire_date.strftime('%B %Y')} ({yrs}y {mos}m)",
                                }
                        scenario_results.append({
                            "label": label,
                            "color": color,
                            "projection": proj_s,
                            "marker": marker_s,
                            "years": res_s.years_part,
                            "months_val": res_s.months_part,
                            "fire_date": res_s.fire_date.strftime("%B %Y") if res_s.fire_date else None,
                            "reachable": res_s.months_to_fire is not None,
                            "fire_number": res_s.fire_number,
                        })

                    context["chart_payload"]["scenarios"] = scenario_results
                    context["display"]["scenarios"] = [
                        {
                            "label": s["label"],
                            "color": s["color"],
                            "years": s["years"],
                            "months_val": s["months_val"],
                            "fire_date": s["fire_date"],
                            "reachable": s["reachable"],
                        }
                        for s in scenario_results
                    ]

    reference_rows = fc.savings_rate_reference_table(
        values["nominal_return_pct"], values["inflation_pct"], values["withdrawal_rate_pct"]
    )
    for row in reference_rows:
        row["years_display"] = f"{row['years']:.1f}" if row["years"] is not None else "not reachable"
    context["reference_table"] = reference_rows

    from flask import current_app
    context["hub_tools"] = current_app.config.get("HUB_TOOLS")
    context["hub_active"] = "fire_calculator"
    # JSON mode — used by the live-update JS to refresh chart and results
    # without a full page reload. Called as POST /?json=1
    if request.method == "POST" and request.args.get("json") == "1":
        results_html = render_template(
            "fire_calculator/_results.html",
            display=context.get("display"),
            error=context.get("error"),
            values=values,
        )
        return jsonify({
            "chart_payload": context.get("chart_payload"),
            "results_html": results_html,
            "error": context.get("error"),
        })

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
