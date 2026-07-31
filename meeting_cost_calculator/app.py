"""
Meeting Cost Calculator -- Web UI

Same calculation as meeting_cost_calculator.py, with a browser form
and an interactive chart instead of the CLI's static output.

No cross-tool dependencies -- all the math lives in
meeting_cost_calculator.py, shared with the CLI.
"""

from __future__ import annotations

import os
import threading
import webbrowser

from flask import Blueprint, Flask, current_app, jsonify, render_template, request

import meeting_cost_calculator as mcc

bp = Blueprint(
    "meeting_cost_calculator",
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


def _build_payload(inputs: mcc.MeetingInputs) -> dict:
    result = mcc.calculate_meeting(inputs)

    def fmt_minutes(m):
        h, mm = divmod(round(m), 60)
        return f"{h}h {mm}m" if h else f"{mm}m"

    curve = [
        {
            "attendees": p.attendees,
            "minutes": round(p.minutes, 1),
            "minutesDisplay": fmt_minutes(p.minutes),
            "cost": round(p.cost, 2),
        }
        for p in result.curve
    ]

    return {
        "hourlyCostPerPerson": round(result.hourly_cost_per_person, 2),
        "coreMinutes": result.core_minutes,
        "discussionMinutes": round(result.discussion_minutes, 1),
        "totalMinutes": round(result.total_minutes, 1),
        "totalMinutesDisplay": fmt_minutes(result.total_minutes),
        "coreCost": round(result.core_cost, 2),
        "discussionCost": round(result.discussion_cost, 2),
        "totalCost": round(result.total_cost, 2),
        "overheadFactor": round(result.overhead_factor, 2),
        "naiveCost": round(result.naive_cost, 2),
        "hiddenCost": round(result.total_cost - result.naive_cost, 2),
        "occurrencesPerYear": result.occurrences_per_year,
        "annualCost": round(result.annual_cost, 2) if result.annual_cost is not None else None,
        "curve": curve,
        "attendees": inputs.attendees,
        "curveMax": inputs.curve_max_attendees,
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    values = {
        "attendees": mcc.DEFAULT_ATTENDEES,
        "avg_annual_salary": 90000,
        "core_minutes": mcc.DEFAULT_CORE_MINUTES,
        "round_robin": True,
        "turn_minutes": mcc.DEFAULT_TURN_MINUTES,
        "overhead_growth_pct": mcc.DEFAULT_OVERHEAD_GROWTH_PCT,
        "benefits_multiplier": mcc.DEFAULT_BENEFITS_MULTIPLIER,
        "recurrence": "none",
        "extend_range": False,
        "curve_max_attendees": mcc.DEFAULT_CURVE_MAX_ATTENDEES,
    }

    if request.method == "POST":
        form = request.form
        values["attendees"] = int(_parse_float(form, "attendees", values["attendees"]))
        values["avg_annual_salary"] = _parse_float(form, "avg_annual_salary", values["avg_annual_salary"])
        values["core_minutes"] = _parse_float(form, "core_minutes", values["core_minutes"])
        values["round_robin"] = form.get("round_robin") == "on"
        values["turn_minutes"] = _parse_float(form, "turn_minutes", values["turn_minutes"])
        values["overhead_growth_pct"] = _parse_float(form, "overhead_growth_pct", values["overhead_growth_pct"])
        values["benefits_multiplier"] = _parse_float(form, "benefits_multiplier", values["benefits_multiplier"])
        values["recurrence"] = form.get("recurrence", "none")
        values["extend_range"] = form.get("extend_range") == "on"
        if values["extend_range"]:
            custom_max = _parse_float(form, "curve_max_attendees", mcc.DEFAULT_CURVE_MAX_ATTENDEES)
            values["curve_max_attendees"] = int(max(1, min(custom_max, mcc.MAX_CURVE_ATTENDEES_CAP)))
        else:
            values["curve_max_attendees"] = mcc.DEFAULT_CURVE_MAX_ATTENDEES

    # Always extend the curve at least as far as the current headcount,
    # so "You" is never off the edge of the chart.
    effective_curve_max = max(values["curve_max_attendees"], values["attendees"])

    inputs = mcc.MeetingInputs(
        attendees=values["attendees"],
        avg_annual_salary=values["avg_annual_salary"],
        core_minutes=values["core_minutes"],
        round_robin=values["round_robin"],
        turn_minutes=values["turn_minutes"],
        overhead_growth_pct=values["overhead_growth_pct"],
        benefits_multiplier=values["benefits_multiplier"],
        recurrence=values["recurrence"],
        curve_max_attendees=effective_curve_max,
    )
    chart_payload = _build_payload(inputs)

    context = {
        "values": values,
        "chart_payload": chart_payload,
        "recurrence_options": [
            ("none", "One-off"), ("daily", "Daily"), ("weekly", "Weekly"),
            ("biweekly", "Every 2 weeks"), ("monthly", "Monthly"),
        ],
        "default_curve_max": mcc.DEFAULT_CURVE_MAX_ATTENDEES,
        "max_curve_cap": mcc.MAX_CURVE_ATTENDEES_CAP,
        "hub_tools": current_app.config.get("HUB_TOOLS"),
        "hub_active": "meeting_cost_calculator",
    }

    if request.method == "POST" and request.args.get("json") == "1":
        return jsonify(chart_payload)

    return render_template("meeting_cost_calculator/index.html", **context)


def create_app() -> Flask:
    standalone = Flask(__name__)
    standalone.register_blueprint(bp)
    return standalone


if __name__ == "__main__":
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    create_app().run(debug=True)
