"""
savings_rate_explorer.py -- core calculation logic (no UI dependencies).

Answers one question: given only your savings rate (the % of income you
invest each month) and a few market assumptions, how long until you reach
financial independence?

This is deliberately independent of income: if you save X% of your
income, your expenses are (100-X)% of it, and your monthly contribution
is X% of it too -- both scale with income, so income itself cancels out
of the years-to-FI calculation. Only the savings rate matters. That's
why this can be shown as a single curve (savings rate -> years) rather
than needing a specific income entered.

This module has no cross-tool dependencies -- it re-implements the small
pieces of math it needs (Fisher equation, compound-interest solver) so it
stays a fully standalone, copy-and-run tool, matching every other tool in
this repository.
"""

from __future__ import annotations

import datetime as _dt
import io
import math
from dataclasses import dataclass, field

DEFAULT_NOMINAL_RETURN_PCT = 8.0
DEFAULT_INFLATION_PCT = 3.0
DEFAULT_WITHDRAWAL_RATE_PCT = 4.0

# The curve is drawn across this range of savings rates.
MIN_SAVINGS_RATE_PCT = 5
MAX_SAVINGS_RATE_PCT = 95
STEP_SAVINGS_RATE_PCT = 1


def real_return_pct_from(nominal_pct: float, inflation_pct: float) -> float:
    """Fisher equation: converts a nominal annual rate to a real
    (inflation-adjusted) annual rate, expressed as a percentage."""
    nominal = nominal_pct / 100
    inflation = inflation_pct / 100
    real = (1 + nominal) / (1 + inflation) - 1
    return real * 100


def months_to_fire_at_rate(
    savings_rate_pct: float,
    nominal_return_pct: float = DEFAULT_NOMINAL_RETURN_PCT,
    inflation_pct: float = DEFAULT_INFLATION_PCT,
    withdrawal_rate_pct: float = DEFAULT_WITHDRAWAL_RATE_PCT,
    starting_rate_pct: float = 0.0,
) -> float | None:
    """Months to reach FI at a given savings rate, starting from zero net
    worth (or a given head start, expressed as a fraction of the annual
    FIRE number via `starting_rate_pct`, default 0).

    Income is normalised to 1 unit/year: expenses = (1 - rate), monthly
    contribution = rate/12, target = expenses / withdrawal_rate.
    Returns None if the savings rate is 0 (target is never reached) or
    withdrawal_rate is 0 (undefined).
    """
    if savings_rate_pct <= 0 or withdrawal_rate_pct <= 0:
        return None

    rate = savings_rate_pct / 100
    annual_expenses = 1 - rate
    target = annual_expenses / (withdrawal_rate_pct / 100)
    monthly_contribution = rate / 12
    starting_balance = target * (starting_rate_pct / 100)

    if starting_balance >= target:
        return 0.0

    annual_real_return = real_return_pct_from(nominal_return_pct, inflation_pct) / 100
    monthly_rate = (1 + annual_real_return) ** (1 / 12) - 1

    remaining = target - starting_balance

    if abs(monthly_rate) < 1e-12:
        return remaining / monthly_contribution

    # Closed-form solution for months n such that:
    #   remaining = contribution * ((1+r)^n - 1) / r
    numerator = remaining * monthly_rate / monthly_contribution + 1
    if numerator <= 0:
        return None
    return math.log(numerator) / math.log(1 + monthly_rate)


@dataclass
class CurveInputs:
    nominal_return_pct: float = DEFAULT_NOMINAL_RETURN_PCT
    inflation_pct: float = DEFAULT_INFLATION_PCT
    withdrawal_rate_pct: float = DEFAULT_WITHDRAWAL_RATE_PCT
    min_rate_pct: int = MIN_SAVINGS_RATE_PCT
    max_rate_pct: int = MAX_SAVINGS_RATE_PCT
    step_pct: int = STEP_SAVINGS_RATE_PCT
    # Optional "you are here" marker
    your_rate_pct: float | None = None


@dataclass
class CurvePoint:
    rate_pct: int
    months: float | None
    years_part: int
    months_part: int


@dataclass
class CurveResult:
    points: list[CurvePoint] = field(default_factory=list)
    real_return_pct: float = 0.0
    your_point: CurvePoint | None = None


def compute_curve(inputs: CurveInputs) -> CurveResult:
    """Compute years-to-FI for every savings rate in the configured
    range, plus an optional single point for the user's own rate."""
    real_return = real_return_pct_from(inputs.nominal_return_pct, inputs.inflation_pct)

    points: list[CurvePoint] = []
    for rate in range(inputs.min_rate_pct, inputs.max_rate_pct + 1, inputs.step_pct):
        months = months_to_fire_at_rate(
            rate, inputs.nominal_return_pct, inputs.inflation_pct, inputs.withdrawal_rate_pct
        )
        if months is None:
            points.append(CurvePoint(rate, None, 0, 0))
        else:
            y, m = divmod(round(months), 12)
            points.append(CurvePoint(rate, months, y, m))

    your_point = None
    if inputs.your_rate_pct is not None and inputs.your_rate_pct > 0:
        months = months_to_fire_at_rate(
            inputs.your_rate_pct, inputs.nominal_return_pct,
            inputs.inflation_pct, inputs.withdrawal_rate_pct,
        )
        if months is not None:
            y, m = divmod(round(months), 12)
            your_point = CurvePoint(inputs.your_rate_pct, months, y, m)

    return CurveResult(points=points, real_return_pct=real_return, your_point=your_point)


def build_curve_figure(result: CurveResult, inputs: CurveInputs):
    """Matplotlib line chart: savings rate (x) vs. years to FI (y). Used
    by the CLI. Import is local so the web app doesn't require matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [p.rate_pct for p in result.points]
    ys = [p.months / 12 if p.months is not None else None for p in result.points]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(xs, ys, color="#2F6F52", linewidth=2.5)
    ax.set_xlabel("Savings rate (%)")
    ax.set_ylabel("Years to FI")
    ax.set_title(
        f"Years to FI by savings rate  "
        f"(return {inputs.nominal_return_pct:.1f}%, inflation {inputs.inflation_pct:.1f}%, "
        f"withdrawal {inputs.withdrawal_rate_pct:.1f}%)"
    )
    ax.grid(True, linestyle="--", alpha=0.4)

    if result.your_point is not None and result.your_point.months is not None:
        ax.scatter(
            [result.your_point.rate_pct], [result.your_point.months / 12],
            color="#B3402F", zorder=5, s=60,
        )
        ax.annotate(
            f"You: {result.your_point.years_part}y {result.your_point.months_part}m",
            xy=(result.your_point.rate_pct, result.your_point.months / 12),
            xytext=(8, 8), textcoords="offset points", fontsize=9, color="#B3402F",
        )

    fig.tight_layout()
    return fig


def _run_cli() -> None:
    """Simple command-line entry point: prints a table and saves a chart."""
    print("Savings Rate Explorer")
    print("=" * 60)
    print(f"Assumptions: {DEFAULT_NOMINAL_RETURN_PCT}% nominal return, "
          f"{DEFAULT_INFLATION_PCT}% inflation, "
          f"{DEFAULT_WITHDRAWAL_RATE_PCT}% withdrawal rate\n")

    inputs = CurveInputs(step_pct=5)
    result = compute_curve(inputs)

    print(f"{'Rate':>6} | {'Years to FI':>12}")
    print("-" * 23)
    for p in result.points:
        label = f"{p.years_part}y {p.months_part}m" if p.months is not None else "never"
        print(f"{p.rate_pct:>5}% | {label:>12}")

    try:
        fig = build_curve_figure(result, inputs)
        out_path = "savings_rate_curve.png"
        fig.savefig(out_path, dpi=150)
        print(f"\nChart saved to {out_path}")
    except ImportError:
        print("\n(matplotlib not installed -- skipping chart)")


if __name__ == "__main__":
    _run_cli()
