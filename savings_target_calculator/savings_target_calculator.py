"""
savings_target_calculator.py

The mirror image of fire_calculator: instead of asking "how long until I
reach my number at my current savings rate", this tool asks "given a
desired retirement income and a savings horizon, how much do I need to
set aside each month to get there".

Everything is calculated in real terms (today's purchasing power). The
desired income, the target amount, and the monthly savings figure are
all expressed in today's money - the nominal return and inflation rate
are only used to derive the real rate of return used for growth.

This module has no external dependencies of its own; the optional chart
in the CLI needs matplotlib (see requirements.txt). The web interface
(app.py) imports the dataclasses and calculate_savings_target() from
here and adds no calculation logic of its own.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None


@dataclass
class SavingsTargetInputs:
    desired_monthly_income: float       # desired retirement income, today's money
    years: float                        # savings horizon in years (may be fractional)
    withdrawal_rate: float = 0.04        # e.g. 0.04 for the 4% rule
    nominal_return: float = 0.08         # expected nominal annual return
    inflation: float = 0.03              # expected annual inflation
    current_savings: float = 0.0         # already set aside, today's money


@dataclass
class SavingsTargetResult:
    annual_income_needed: float
    target_amount: float
    real_annual_return: float
    monthly_real_return: float
    total_months: int
    required_monthly_savings: float
    total_contributed: float            # current_savings + all monthly contributions
    total_growth: float                 # target_amount - total_contributed
    projection: List[Tuple[int, float]] = field(default_factory=list)  # (month, net worth)


def _real_return(nominal_return: float, inflation: float) -> float:
    """Real annual return implied by a nominal return and an inflation rate."""
    return (1 + nominal_return) / (1 + inflation) - 1


def calculate_savings_target(inputs: SavingsTargetInputs) -> SavingsTargetResult:
    if inputs.years <= 0:
        raise ValueError("years must be greater than 0")
    if inputs.withdrawal_rate <= 0:
        raise ValueError("withdrawal_rate must be greater than 0")

    annual_income_needed = inputs.desired_monthly_income * 12
    target_amount = annual_income_needed / inputs.withdrawal_rate

    real_annual_return = _real_return(inputs.nominal_return, inputs.inflation)
    monthly_r = (1 + real_annual_return) ** (1 / 12) - 1

    total_months = max(round(inputs.years * 12), 1)

    # Future value of what's already saved, grown at the real rate.
    fv_current = inputs.current_savings * (1 + monthly_r) ** total_months
    remaining_target = max(target_amount - fv_current, 0.0)

    if remaining_target == 0.0:
        required_monthly_savings = 0.0
    elif monthly_r == 0:
        required_monthly_savings = remaining_target / total_months
    else:
        required_monthly_savings = (
            remaining_target * monthly_r / ((1 + monthly_r) ** total_months - 1)
        )

    # Month-by-month projection for the chart (contributions at month end).
    projection: List[Tuple[int, float]] = [(0, inputs.current_savings)]
    balance = inputs.current_savings
    for month in range(1, total_months + 1):
        balance = balance * (1 + monthly_r) + required_monthly_savings
        projection.append((month, balance))

    total_contributed = inputs.current_savings + required_monthly_savings * total_months
    total_growth = projection[-1][1] - total_contributed

    return SavingsTargetResult(
        annual_income_needed=annual_income_needed,
        target_amount=target_amount,
        real_annual_return=real_annual_return,
        monthly_real_return=monthly_r,
        total_months=total_months,
        required_monthly_savings=required_monthly_savings,
        total_contributed=total_contributed,
        total_growth=total_growth,
        projection=projection,
    )


def build_projection_figure(result: SavingsTargetResult):
    """Matplotlib chart: projected net worth (blue) vs. target (red, dashed)."""
    if plt is None:
        raise RuntimeError("matplotlib is not installed")

    years_axis = [month / 12 for month, _ in result.projection]
    values = [value for _, value in result.projection]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(years_axis, values, color="#2c5f8a", linewidth=2, label="Projected net worth")
    ax.axhline(result.target_amount, color="#b3402a", linestyle="--", linewidth=1.5, label="Target")
    ax.set_xlabel("Years")
    ax.set_ylabel("Net worth (today's money)")
    ax.set_title("Savings projection vs. target")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


def _prompt_float(prompt: str, default: float) -> float:
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("Please enter a number.")
        return _prompt_float(prompt, default)


def run_cli() -> None:
    print("=== Savings Target Calculator ===")
    print("How much do you need to save each month to reach a target retirement income?\n")

    desired_monthly_income = _prompt_float(
        "Desired monthly income in retirement (today's money)", 30000
    )
    years = _prompt_float("Number of years you plan to save", 15)
    withdrawal_rate = _prompt_float("Withdrawal rate (e.g. 0.04 for 4%)", 0.04)
    nominal_return = _prompt_float("Expected nominal annual return (e.g. 0.08 for 8%)", 0.08)
    inflation = _prompt_float("Expected annual inflation (e.g. 0.03 for 3%)", 0.03)
    current_savings = _prompt_float("Already saved today (0 if none)", 0.0)

    inputs = SavingsTargetInputs(
        desired_monthly_income=desired_monthly_income,
        years=years,
        withdrawal_rate=withdrawal_rate,
        nominal_return=nominal_return,
        inflation=inflation,
        current_savings=current_savings,
    )
    result = calculate_savings_target(inputs)

    print(f"\nTarget amount needed:       {result.target_amount:,.0f}")
    print(f"Real annual return used:    {result.real_annual_return:.2%}")
    print(f"Required monthly savings:   {result.required_monthly_savings:,.0f}")
    print(f"Of the final amount, {result.total_growth:,.0f} comes from investment growth")
    print(f"(you would contribute {result.total_contributed:,.0f} out of pocket in total).")

    if plt is not None:
        build_projection_figure(result)
        plt.show()
    else:
        print("\n(matplotlib not installed - skipping chart)")


if __name__ == "__main__":
    run_cli()
