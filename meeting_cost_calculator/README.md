# Meeting Cost Calculator

The basic idea behind every online "meeting cost calculator" is
simple: headcount &times; average pay &times; duration. That part is
just arithmetic, and it's what every existing calculator does.

This one adds the part that's usually ignored: **does a meeting's
duration itself depend on how many people are in it?** Two well-known
findings from organisational research say yes.

- **Brooks's Law** (Fred Brooks, *The Mythical Man-Month*, 1975): the
  number of communication *channels* between people in a group grows
  much faster than the group itself (n(n&minus;1)/2 pairs) &mdash;
  more people means more cross-talk, tangents, and re-explaining.
- **Bain & Company's decision-effectiveness research** (widely cited,
  e.g. Rogers & Blenko, *"Who Has the D?"*, Harvard Business Review,
  2006): each person added to a decision-making group beyond about 7
  reduces decision quality/speed by roughly 10%, with effectiveness
  collapsing well before 20 people &mdash; part of why Amazon caps
  team meetings with its famous "two-pizza rule".

This tool turns that into a simple, transparent, **adjustable**
model rather than a fake precise formula:

```
total duration = fixed agenda time
                + (attendees × average turn length × overhead factor)

overhead factor = 1 + growth_rate × (attendees − 1)
```

`growth_rate` is a slider you control — a heuristic knob, not a
measured constant. The point is making the well-established "bigger
groups are disproportionately less efficient" effect visible and
adjustable, instead of assuming duration is independent of headcount
(which every simpler meeting-cost calculator does).

## Running the web interface

```bash
pip install -r requirements.txt
python3 app.py
```

Then open **http://127.0.0.1:5000**.

## What it shows

- **Total cost** for this specific meeting, split into core (fixed)
  cost and discussion cost.
- **Hidden cost callout** — how much of the total is attributable
  purely to group-size friction (the gap between "duration scales
  with headcount" and "duration scales with headcount *and* the
  overhead effect").
- **Interactive chart** — cost vs. headcount, with your current
  meeting marked, so you can see how steeply cost rises as you add
  more people.
- **Annualized cost** if the meeting recurs (daily/weekly/biweekly/
  monthly) — the number that usually causes the most surprise.

## Inputs

| Input | Notes |
|---|---|
| Attendees | Headcount in the meeting. |
| Average annual salary | Base salary; grossed up by the benefits multiplier below to get a "fully loaded" hourly cost. |
| Benefits & overhead load | Common finance/HR rule of thumb: fully-loaded employee cost is typically 1.25&ndash;1.4&times; base salary once you include benefits, payroll tax, etc. |
| Fixed agenda time | Time that doesn't depend on headcount — presentations, decisions, status updates. |
| Everyone gets a turn to speak | Toggles the group-size-dependent discussion component on/off. |
| Avg. speaking time per person | Base time each person takes for their turn, before overhead. |
| Overhead growth per extra person | How much longer each person's *average* turn gets as the group grows. Adjustable — see methodology above. |
| Recurrence | If this is a recurring meeting, annualizes the cost. |

## Command line

```bash
python3 meeting_cost_calculator.py
```

Prints a cost breakdown and saves a matplotlib chart
(`meeting_cost_curve.png`) of cost vs. headcount.

## Limitations

- The overhead-growth model is a simplified, adjustable heuristic
  motivated by real research findings — not itself a measured
  empirical constant. Treat the shape of the effect (bigger groups
  cost disproportionately more) as the reliable part, not any single
  number it produces.
- Doesn't account for meeting prep/follow-up time, only the meeting
  itself.
- Assumes one flat average salary for all attendees rather than
  per-person rates.

## Requirements

Python 3.9+. Needs `matplotlib` for the CLI chart and `flask` for the
web interface.

```bash
pip install -r requirements.txt
```
