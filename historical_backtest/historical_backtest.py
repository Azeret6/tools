"""
historical_backtest.py -- core calculation logic (no UI dependencies).

Every other calculator in this repo asks "if returns average X% a year,
forever, how long until FIRE?" That single constant number hides a huge
amount of risk: real markets don't return a steady 8% -- they crash,
boom, and crash again, in a different order for every possible starting
year. Two people who both average 8% real return over 30 years can have
wildly different outcomes if one of them started right before a crash.
This is called "sequence of returns risk".

This tool answers a different question: "if I had started saving in
YEAR, using the *actual* historical sequence of returns from that year
onward, how long would FIRE have taken?" -- repeated for every possible
historical starting year, so you can see the full spread of outcomes
history has actually produced, not just their average.

Data
----
`ANNUAL_NOMINAL_RETURNS_PCT` and `ANNUAL_INFLATION_PCT` below are
approximate, illustrative year-by-year figures for total US stock
market returns (S&P 500, dividends reinvested) and CPI-U inflation,
broadly consistent with widely-published historical series (the kind
of data Robert Shiller's and Aswath Damodaran's public datasets
contain, which tools like FIRECalc/cFIREsim are built on). They were
reconstructed from general knowledge rather than pulled from a live,
verified feed, so treat exact single-year figures as approximate --
the long-run averages and the *shape* of the sequence-of-returns story
they tell are the point, not any individual year's decimal precision.
For research-grade work, cross-check against a primary source.

Like every other tool in this repository, this module is fully
self-contained: no cross-tool dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DEFAULT_WITHDRAWAL_RATE_PCT = 4.0
WITHDRAWAL_RATE_MIN_PCT = 3.0
WITHDRAWAL_RATE_MAX_PCT = 5.0
DEFAULT_HORIZON_YEARS = 30
MAX_HORIZON_YEARS = 50

# ---------------------------------------------------------------------------
# Historical data: nominal total return (S&P 500, dividends reinvested) and
# CPI-U inflation, by calendar year. Real return for each year is derived
# via the same Fisher equation used everywhere else in this repo:
#   real = (1 + nominal) / (1 + inflation) - 1
# ---------------------------------------------------------------------------

ANNUAL_NOMINAL_RETURNS_PCT: dict[int, float] = {
    1928: 43.6, 1929: -8.4, 1930: -24.9, 1931: -43.3, 1932: -8.2,
    1933: 54.0, 1934: -1.4, 1935: 47.7, 1936: 33.9, 1937: -35.0,
    1938: 31.1, 1939: -0.4, 1940: -9.8, 1941: -11.6, 1942: 20.3,
    1943: 25.9, 1944: 19.7, 1945: 36.4, 1946: -8.1, 1947: 5.7,
    1948: 5.5, 1949: 18.8, 1950: 31.7, 1951: 24.6, 1952: 18.5,
    1953: -1.1, 1954: 52.6, 1955: 31.6, 1956: 6.6, 1957: -10.8,
    1958: 43.4, 1959: 12.0, 1960: 0.5, 1961: 26.9, 1962: -8.7,
    1963: 22.8, 1964: 16.5, 1965: 12.5, 1966: -10.1, 1967: 24.0,
    1968: 11.1, 1969: -8.5, 1970: 4.0, 1971: 14.3, 1972: 19.0,
    1973: -14.7, 1974: -26.5, 1975: 37.2, 1976: 23.8, 1977: -7.2,
    1978: 6.6, 1979: 18.4, 1980: 32.4, 1981: -5.0, 1982: 21.4,
    1983: 22.5, 1984: 6.3, 1985: 32.2, 1986: 18.5, 1987: 5.8,
    1988: 16.6, 1989: 31.7, 1990: -3.1, 1991: 30.5, 1992: 7.6,
    1993: 10.1, 1994: 1.3, 1995: 37.6, 1996: 23.0, 1997: 33.4,
    1998: 28.6, 1999: 21.0, 2000: -9.1, 2001: -11.9, 2002: -22.1,
    2003: 28.7, 2004: 10.9, 2005: 4.9, 2006: 15.8, 2007: 5.5,
    2008: -37.0, 2009: 26.5, 2010: 15.1, 2011: 2.1, 2012: 16.0,
    2013: 32.4, 2014: 13.7, 2015: 1.4, 2016: 12.0, 2017: 21.8,
    2018: -4.4, 2019: 31.5, 2020: 18.4, 2021: 28.7, 2022: -18.1,
    2023: 26.3,
}

ANNUAL_INFLATION_PCT: dict[int, float] = {
    1928: -1.2, 1929: 0.0, 1930: -2.7, 1931: -8.9, 1932: -10.3,
    1933: 0.8, 1934: 1.5, 1935: 3.0, 1936: 1.4, 1937: 2.9,
    1938: -2.8, 1939: 0.0, 1940: 0.7, 1941: 9.9, 1942: 9.0,
    1943: 3.0, 1944: 2.3, 1945: 2.2, 1946: 18.1, 1947: 8.8,
    1948: 3.0, 1949: -2.1, 1950: 5.9, 1951: 6.0, 1952: 0.8,
    1953: 0.7, 1954: -0.7, 1955: 0.4, 1956: 3.0, 1957: 2.9,
    1958: 1.8, 1959: 1.7, 1960: 1.4, 1961: 0.7, 1962: 1.3,
    1963: 1.6, 1964: 1.0, 1965: 1.9, 1966: 3.5, 1967: 3.0,
    1968: 4.7, 1969: 6.2, 1970: 5.6, 1971: 3.3, 1972: 3.4,
    1973: 8.7, 1974: 12.3, 1975: 6.9, 1976: 4.9, 1977: 6.7,
    1978: 9.0, 1979: 13.3, 1980: 12.5, 1981: 8.9, 1982: 3.8,
    1983: 3.8, 1984: 3.9, 1985: 3.8, 1986: 1.1, 1987: 4.4,
    1988: 4.4, 1989: 4.6, 1990: 6.1, 1991: 3.1, 1992: 2.9,
    1993: 2.7, 1994: 2.7, 1995: 2.5, 1996: 3.3, 1997: 1.7,
    1998: 1.6, 1999: 2.7, 2000: 3.4, 2001: 1.6, 2002: 2.4,
    2003: 1.9, 2004: 3.3, 2005: 3.4, 2006: 2.5, 2007: 4.1,
    2008: 0.1, 2009: 2.7, 2010: 1.5, 2011: 3.0, 2012: 1.7,
    2013: 1.5, 2014: 0.8, 2015: 0.7, 2016: 2.1, 2017: 2.1,
    2018: 1.9, 2019: 2.3, 2020: 1.4, 2021: 7.0, 2022: 6.5,
    2023: 3.4,
}

FIRST_YEAR = min(ANNUAL_NOMINAL_RETURNS_PCT)
LAST_YEAR = max(ANNUAL_NOMINAL_RETURNS_PCT)


def real_return_pct_from(nominal_pct: float, inflation_pct: float) -> float:
    """Fisher equation, identical to the one used throughout this repo."""
    nominal = nominal_pct / 100
    inflation = inflation_pct / 100
    return ((1 + nominal) / (1 + inflation) - 1) * 100


def annual_real_returns() -> dict[int, float]:
    """Every year's real (inflation-adjusted) return, derived from the
    two raw series above."""
    return {
        year: real_return_pct_from(ANNUAL_NOMINAL_RETURNS_PCT[year], ANNUAL_INFLATION_PCT[year])
        for year in ANNUAL_NOMINAL_RETURNS_PCT
    }


@dataclass
class BacktestInputs:
    savings_rate_pct: float          # % of income saved -- income is normalised
                                      # to 1 unit, same trick as savings_rate_explorer,
                                      # so no income figure is required.
    withdrawal_rate_pct: float = DEFAULT_WITHDRAWAL_RATE_PCT
    horizon_years: int = DEFAULT_HORIZON_YEARS
    starting_rate_pct: float = 0.0   # optional head start, as a fraction of the target


@dataclass
class YearOutcome:
    start_year: int
    months_to_fire: float | None    # None = target not reached within horizon
                                      # (either ran out of years, or ran out of data)
    ran_out_of_data: bool            # True if the *data* ended before the horizon did
                                      # (distinct from genuinely not reaching the target)
    balance_path: list[float] = field(default_factory=list)  # year-end balances, for the chart


@dataclass
class BacktestResult:
    outcomes: list[YearOutcome]
    target: float
    monthly_contribution: float
    reachable_count: int
    unreachable_count: int
    insufficient_data_count: int
    years_to_fire_reachable: list[float] = field(default_factory=list)


def _simulate_from_year(
    start_year: int,
    monthly_contribution: float,
    target: float,
    horizon_months: int,
    real_returns: dict[int, float],
    starting_balance: float = 0.0,
) -> YearOutcome:
    """Simulate month-by-month starting Jan of `start_year`, using the
    *actual* historical sequence of real annual returns from that year
    onward (wrapping each year's annual rate into 12 equal monthly
    compounding steps). Stops early if the target is reached, if the
    horizon elapses, or if the historical data runs out."""
    balance = starting_balance
    balance_path = [balance]
    months_to_fire = None
    ran_out_of_data = False

    if balance >= target:
        return YearOutcome(start_year, 0.0, False, [balance])

    month = 0
    year = start_year
    while month < horizon_months:
        if year not in real_returns:
            ran_out_of_data = True
            break
        annual_real = real_returns[year] / 100
        monthly_rate = (1 + annual_real) ** (1 / 12) - 1
        for _ in range(12):
            if month >= horizon_months:
                break
            balance = balance * (1 + monthly_rate) + monthly_contribution
            month += 1
            if months_to_fire is None and balance >= target:
                months_to_fire = float(month)
        balance_path.append(balance)
        year += 1
        if months_to_fire is not None:
            break

    return YearOutcome(start_year, months_to_fire, ran_out_of_data, balance_path)


def run_backtest(inputs: BacktestInputs) -> BacktestResult:
    """Run the simulation starting from every historical year for which
    at least some data exists, and collect the spread of outcomes."""
    real_returns = annual_real_returns()

    rate = inputs.savings_rate_pct / 100
    annual_expenses = 1 - rate
    target = annual_expenses / (inputs.withdrawal_rate_pct / 100)
    monthly_contribution = rate / 12
    starting_balance = target * (inputs.starting_rate_pct / 100)
    horizon_months = inputs.horizon_years * 12

    outcomes = []
    for start_year in range(FIRST_YEAR, LAST_YEAR + 1):
        outcome = _simulate_from_year(
            start_year, monthly_contribution, target, horizon_months,
            real_returns, starting_balance,
        )
        outcomes.append(outcome)

    reachable = [o for o in outcomes if o.months_to_fire is not None]
    unreachable = [o for o in outcomes if o.months_to_fire is None and not o.ran_out_of_data]
    insufficient = [o for o in outcomes if o.ran_out_of_data and o.months_to_fire is None]

    return BacktestResult(
        outcomes=outcomes,
        target=target,
        monthly_contribution=monthly_contribution,
        reachable_count=len(reachable),
        unreachable_count=len(unreachable),
        insufficient_data_count=len(insufficient),
        years_to_fire_reachable=sorted(o.months_to_fire / 12 for o in reachable),
    )


def summary_stats(result: BacktestResult) -> dict:
    """Best/worst/median case among the historical starting years that
    actually reached the target within the horizon and had complete data."""
    ys = result.years_to_fire_reachable
    total_complete = result.reachable_count + result.unreachable_count
    if not ys or total_complete == 0:
        return {
            "success_rate_pct": 0.0,
            "best_years": None,
            "worst_years": None,
            "median_years": None,
            "total_windows": total_complete,
        }
    n = len(ys)
    median = ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2
    return {
        "success_rate_pct": 100 * result.reachable_count / total_complete,
        "best_years": ys[0],
        "worst_years": ys[-1],
        "median_years": median,
        "total_windows": total_complete,
    }


def build_backtest_figure(result: BacktestResult, inputs: BacktestInputs):
    """Matplotlib bar chart: historical starting year (x) vs. years to
    FIRE (y), used by the CLI."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    years = [o.start_year for o in result.outcomes]
    values = []
    colors = []
    for o in result.outcomes:
        if o.months_to_fire is not None:
            values.append(o.months_to_fire / 12)
            colors.append("#2F6F52")
        elif o.ran_out_of_data:
            values.append(0)
            colors.append("#DCE3DA")
        else:
            values.append(inputs.horizon_years)
            colors.append("#B3402F")

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(years, values, color=colors, width=0.9)
    ax.set_xlabel("Starting year")
    ax.set_ylabel("Years to FIRE")
    ax.set_title(
        f"Historical backtest -- {inputs.savings_rate_pct:.0f}% savings rate, "
        f"{inputs.withdrawal_rate_pct:.1f}% withdrawal, {inputs.horizon_years}y horizon"
    )
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def _run_cli() -> None:
    print("Historical FIRE Backtest")
    print("=" * 60)
    print(f"Data available: {FIRST_YEAR}-{LAST_YEAR} ({LAST_YEAR - FIRST_YEAR + 1} years)\n")

    inputs = BacktestInputs(savings_rate_pct=25, withdrawal_rate_pct=4.0, horizon_years=30)
    result = run_backtest(inputs)
    stats = summary_stats(result)

    print(f"Savings rate: {inputs.savings_rate_pct:.0f}%  |  "
          f"Withdrawal rate: {inputs.withdrawal_rate_pct:.1f}%  |  "
          f"Horizon: {inputs.horizon_years}y\n")
    print(f"Historical windows tested: {stats['total_windows']}")
    print(f"Reached FIRE within horizon: {result.reachable_count} "
          f"({stats['success_rate_pct']:.0f}%)")
    if stats["best_years"] is not None:
        print(f"  Best case:   {stats['best_years']:.1f} years")
        print(f"  Median case: {stats['median_years']:.1f} years")
        print(f"  Worst case:  {stats['worst_years']:.1f} years")
    print(f"Did not reach it within {inputs.horizon_years}y: {result.unreachable_count}")
    print(f"Insufficient data to test fully: {result.insufficient_data_count}")

    try:
        fig = build_backtest_figure(result, inputs)
        fig.savefig("historical_backtest.png", dpi=150)
        print("\nChart saved to historical_backtest.png")
    except ImportError:
        print("\n(matplotlib not installed -- skipping chart)")


if __name__ == "__main__":
    _run_cli()
