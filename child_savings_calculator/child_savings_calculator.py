"""
child_savings_calculator.py

How much will a fixed monthly contribution grow into by the time a child
reaches a chosen age (or after a chosen number of years)? Compares two
scenarios side by side:

  - "Flat":              the same nominal contribution every month.
  - "Rising with inflation": the contribution is bumped up once a year by
    the inflation rate, so it keeps the same real (today's-money) value
    throughout instead of eroding.

Both scenarios compound at the same nominal rate of return. At the end,
the tool also reports what a theoretical monthly withdrawal (e.g. the
classic 4% rule) would look like on the final balance -- not real
retirement advice, just a "what could this become" sense of scale.

This module has no external dependencies. The web interface (app.py)
imports the dataclasses and calculate_child_savings() from here and adds
no calculation logic of its own -- same split as the other tools in this
repo, and no cross-tool imports either (this file is fully self-contained,
copy-pasteable on its own).
"""

from dataclasses import dataclass, field
from typing import List, Tuple

# Same defaults used across the other calculators in this toolkit, so a
# figure that means "8% return" here means the same thing everywhere else.
DEFAULT_NOMINAL_RETURN_PCT = 8.0
DEFAULT_INFLATION_PCT = 3.0
DEFAULT_WITHDRAWAL_RATE_PCT = 4.0
DEFAULT_END_AGE_YEARS = 18


@dataclass
class ChildSavingsInputs:
    monthly_contribution: float             # amount set aside each month, in today's money
    duration_months: int                    # total months to save for (>= 1)
    starting_balance: float = 0.0           # already saved for the child, if any
    nominal_return_pct: float = DEFAULT_NOMINAL_RETURN_PCT
    inflation_pct: float = DEFAULT_INFLATION_PCT
    withdrawal_rate_pct: float = DEFAULT_WITHDRAWAL_RATE_PCT


@dataclass
class ScenarioResult:
    label: str
    final_balance: float                    # nominal money at the end
    final_balance_today: float              # same amount, deflated to today's purchasing power
    total_contributed: float                # sum of all monthly contributions (nominal), excludes starting_balance
    total_growth: float                     # final_balance - starting_balance - total_contributed
    monthly_income: float                   # final_balance * withdrawal_rate / 12 (nominal)
    monthly_income_today: float             # same, deflated to today's purchasing power
    final_contribution: float               # the last month's contribution (== first month's for "flat")
    projection: List[Tuple[int, float]] = field(default_factory=list)  # (month, balance), nominal


@dataclass
class ChildSavingsResult:
    duration_months: int
    duration_years_part: int
    duration_months_part: int
    flat: ScenarioResult
    rising: ScenarioResult


def duration_months_from_age(
    current_age_years: int,
    current_age_months: int,
    end_age_years: float,
) -> int:
    """Months between a child's current age and a target end age (default 18).
    `end_age_years` may be fractional (e.g. 18.5)."""
    current_total_months = current_age_years * 12 + current_age_months
    end_total_months = round(end_age_years * 12)
    return end_total_months - current_total_months


def _simulate(
    starting_balance: float,
    monthly_contribution: float,
    duration_months: int,
    monthly_rate: float,
    annual_contribution_growth: float,
) -> Tuple[List[Tuple[int, float]], float, float]:
    """Month-by-month simulation. Contribution is bumped up once every 12
    months by `annual_contribution_growth` (0.0 for the flat scenario).
    Returns (projection, total_contributed, last_contribution_used) --
    `last_contribution_used` is the amount actually applied in the final
    month (not a bump that happened to land on the last month itself and
    was never used again)."""
    balance = starting_balance
    contribution = monthly_contribution
    total_contributed = 0.0
    last_contribution_used = contribution
    projection: List[Tuple[int, float]] = [(0, balance)]

    for month in range(1, duration_months + 1):
        balance = balance * (1 + monthly_rate) + contribution
        total_contributed += contribution
        last_contribution_used = contribution
        projection.append((month, balance))
        if annual_contribution_growth and month % 12 == 0 and month < duration_months:
            contribution *= (1 + annual_contribution_growth)

    return projection, total_contributed, last_contribution_used


def calculate_child_savings(inputs: ChildSavingsInputs) -> ChildSavingsResult:
    if inputs.duration_months < 1:
        raise ValueError(
            "The savings horizon must be at least 1 month -- check the child's "
            "current age against the savings end age."
        )
    if inputs.monthly_contribution < 0 or inputs.starting_balance < 0:
        raise ValueError("Contribution and starting balance can't be negative.")
    if inputs.withdrawal_rate_pct <= 0:
        raise ValueError("Withdrawal rate must be greater than 0.")

    monthly_rate = (1 + inputs.nominal_return_pct / 100) ** (1 / 12) - 1
    duration_years_exact = inputs.duration_months / 12
    # Cumulative inflation over the full horizon, used to deflate the nominal
    # end figures back to today's purchasing power (same "same amount in
    # {future year}" idea as fire_calculator, just phrased the other way
    # around: "this future amount is worth X today").
    inflation_factor = (1 + inputs.inflation_pct / 100) ** duration_years_exact

    def build_scenario(label: str, annual_contribution_growth: float) -> ScenarioResult:
        projection, total_contributed, final_contribution = _simulate(
            starting_balance=inputs.starting_balance,
            monthly_contribution=inputs.monthly_contribution,
            duration_months=inputs.duration_months,
            monthly_rate=monthly_rate,
            annual_contribution_growth=annual_contribution_growth,
        )
        final_balance = projection[-1][1]
        final_balance_today = final_balance / inflation_factor
        monthly_income = final_balance * inputs.withdrawal_rate_pct / 100 / 12
        monthly_income_today = final_balance_today * inputs.withdrawal_rate_pct / 100 / 12
        total_growth = final_balance - inputs.starting_balance - total_contributed
        return ScenarioResult(
            label=label,
            final_balance=final_balance,
            final_balance_today=final_balance_today,
            total_contributed=total_contributed,
            total_growth=total_growth,
            monthly_income=monthly_income,
            monthly_income_today=monthly_income_today,
            final_contribution=final_contribution,
            projection=projection,
        )

    flat = build_scenario("Flat monthly contribution", annual_contribution_growth=0.0)
    rising = build_scenario("Rising with inflation", annual_contribution_growth=inputs.inflation_pct / 100)

    duration_years_part, duration_months_part = divmod(inputs.duration_months, 12)

    return ChildSavingsResult(
        duration_months=inputs.duration_months,
        duration_years_part=duration_years_part,
        duration_months_part=duration_months_part,
        flat=flat,
        rising=rising,
    )


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
    print("=== Child Savings Calculator ===")
    print("How much could a monthly contribution grow into by the time your child")
    print("reaches a chosen age?\n")

    monthly_contribution = _prompt_float("Monthly contribution", 2000)
    use_age = input("Specify the horizon by child's age instead of years? [y/N]: ").strip().lower() == "y"

    if use_age:
        current_age_years = int(_prompt_float("Child's current age (years)", 5))
        current_age_months = int(_prompt_float("...and extra months", 0))
        end_age_years = _prompt_float("Savings end age", DEFAULT_END_AGE_YEARS)
        duration_months = duration_months_from_age(current_age_years, current_age_months, end_age_years)
    else:
        years = _prompt_float("Number of years to save", 15)
        duration_months = round(years * 12)

    starting_balance = _prompt_float("Already saved for the child (0 if none)", 0.0)
    nominal_return_pct = _prompt_float("Expected nominal annual return (%)", DEFAULT_NOMINAL_RETURN_PCT)
    inflation_pct = _prompt_float("Expected annual inflation (%)", DEFAULT_INFLATION_PCT)
    withdrawal_rate_pct = _prompt_float("Withdrawal rate for the final figure (%)", DEFAULT_WITHDRAWAL_RATE_PCT)

    inputs = ChildSavingsInputs(
        monthly_contribution=monthly_contribution,
        duration_months=duration_months,
        starting_balance=starting_balance,
        nominal_return_pct=nominal_return_pct,
        inflation_pct=inflation_pct,
        withdrawal_rate_pct=withdrawal_rate_pct,
    )
    result = calculate_child_savings(inputs)

    print(f"\nSavings horizon: {result.duration_years_part}y {result.duration_months_part}m "
          f"({result.duration_months} months)\n")

    for scenario in (result.flat, result.rising):
        print(f"--- {scenario.label} ---")
        print(f"Final balance:            {scenario.final_balance:,.0f}  "
              f"(worth {scenario.final_balance_today:,.0f} in today's money)")
        print(f"Total contributed:        {scenario.total_contributed:,.0f}")
        print(f"From investment growth:   {scenario.total_growth:,.0f}")
        print(f"Theoretical monthly income at withdrawal: {scenario.monthly_income:,.0f} "
              f"(worth {scenario.monthly_income_today:,.0f} in today's money)")
        print()


if __name__ == "__main__":
    run_cli()
