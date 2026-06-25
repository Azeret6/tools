"""
app.py - web interface for the savings target calculator.

This file has no calculation logic of its own. It collects form input,
calls the shared functions in savings_target_calculator.py, and returns
the result as JSON for the page's JavaScript to render into the result
panel and chart.
"""

from flask import Flask, render_template, request, jsonify

from savings_target_calculator import SavingsTargetInputs, calculate_savings_target

app = Flask(__name__)

DEFAULTS = {
    "desired_monthly_income": 30000,
    "years": 15,
    "withdrawal_rate": 0.04,
    "nominal_return": 0.08,
    "inflation": 0.03,
    "current_savings": 0,
}


@app.route("/")
def index():
    return render_template("index.html", defaults=DEFAULTS)


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json(silent=True) or {}

    try:
        inputs = SavingsTargetInputs(
            desired_monthly_income=float(data["desired_monthly_income"]),
            years=float(data["years"]),
            withdrawal_rate=float(data["withdrawal_rate"]),
            nominal_return=float(data["nominal_return"]),
            inflation=float(data["inflation"]),
            current_savings=float(data.get("current_savings") or 0),
        )
        result = calculate_savings_target(inputs)
    except (KeyError, ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "annual_income_needed": result.annual_income_needed,
            "target_amount": result.target_amount,
            "real_annual_return": result.real_annual_return,
            "required_monthly_savings": result.required_monthly_savings,
            "total_contributed": result.total_contributed,
            "total_growth": result.total_growth,
            "total_months": result.total_months,
            "projection": [{"month": m, "value": v} for m, v in result.projection],
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
