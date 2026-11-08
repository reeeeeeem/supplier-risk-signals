# Supplier Risk Signals

Delivery metrics tell you a supplier has already slipped. The notes buyers write "they mentioned their line was down," "third account manager this year," "asked for a firm date twice, got 'soon' both times" tell you they're about to.

This project combines both: SQL to measure delivery drift, and an LLM to read the notes nobody has time to read.

---

## The problem

A supplier who is reliably four days late is annoying. You plan around them.

A supplier who was on time all year and is now three days late is a different problem, even though their annual average still looks better. The first supplier is a known cost. The second is an unknown risk.

Most supplier scorecards report annual averages, which hides exactly that distinction.

---

## Approach

**Quantitative layer (`analyze_delivery.py`)**

SQL over 405 orders across 15 suppliers. For each supplier it computes on-time rate and average lateness for the full 12 months and separately for the last 90 days, then takes the difference.

That difference — `drift_days` — is the metric. A supplier who has always been late has a drift near zero. A supplier who is getting worse has positive drift.

Written as CTEs rather than pandas, since the point was to do the aggregation in SQL.

**Text layer (`analyze_notes.py`)**

170 buyer notes sent to Claude, grouped by supplier and ordered by date. The model returns structured JSON: risk level, signal categories, trend, and reasoning.

The prompt does three things deliberately:

- Defines what counts as a signal (capacity, personnel, evasiveness, repeated reschedules, recurring quality issues, cost pressure)
- Defines what does **not** count — one resolved quality issue, a single explained reschedule, routine confirmations
- Asks the model to weigh change over time rather than absolute volume of complaints

That second point mattered most. Without it the model flagged nearly everything.

---

## Results

The synthetic data has three suppliers deliberately degrading over the period, two who are consistently late but stable, and one whose delivery is fine while cost climbs.

**Delivery drift correctly identified all three degrading suppliers:**

| Supplier                 | On-time (year) | On-time (90d) | Drift      |
| ------------------------ | -------------- | ------------- | ---------- |
| SUP002 Kanto Precision   | 66.7%          | 0.0%          | +2.74 days |
| SUP009 Halvorsen Tooling | 40.7%          | 0.0%          | +2.12 days |
| SUP013 Northgate Cartons | 55.6%          | 11.1%         | +1.96 days |

The two consistently-late suppliers (SUP005, SUP011) sit at 3.7% on-time — worse than SUP002 in absolute terms — but their drift is 0.02 and 0.06 days. They are correctly absent from the flagged list.

**Text analysis independently flagged the same three**, plus the cost-pressure supplier, from notes alone with no access to the delivery data.

---

## What the model got wrong

**14 of 15 suppliers classified correctly on the first run, with no prompt tuning.**

The one error: **SUP005 was flagged medium/worsening when it should have been low or none.** It is consistently late with near-zero drift, which the prompt explicitly described as not a signal.

Looking at why: three reschedule notes happened to cluster in October. With only 12 notes spread across a year, random clustering looks like a pattern.

Two things make this interesting rather than just a bug:

1. **SUP011 has the same behavioural profile and was correctly dismissed** — "consistent, stable pattern throughout the period." So the model can make this distinction; it just didn't here.
2. The failure is a small-sample problem, not a prompt comprehension problem. More notes per supplier would likely fix it without touching the prompt.

Next iteration: give the model note density as context, or ask it to weigh cluster timing against total note volume.

---

## Why both layers

The two signals are not redundant.

Delivery drift is objective but lagging — by the time it moves, the supplier has already missed deliveries. Text signals are earlier but noisier, as the SUP005 false positive shows.

Agreement between them is the useful output. All three degrading suppliers were flagged by both independently, which is a stronger finding than either alone.

---

## Running it

```bash
python3 -m venv venv
source venv/bin/activate
pip install pandas anthropic python-dotenv

echo "ANTHROPIC_API_KEY=your-key" > .env

python3 generate_orders.py     # creates data/orders.csv
python3 generate_notes.py      # creates data/notes.csv
python3 analyze_delivery.py    # SQL drift metrics
python3 analyze_notes.py       # LLM note analysis
```

---

## Files

| File                  | Purpose                                                              |
| --------------------- | -------------------------------------------------------------------- |
| `generate_orders.py`  | Builds 405 orders with behaviour profiles per supplier               |
| `generate_notes.py`   | Builds 170 buyer notes, with signals ramping for degrading suppliers |
| `analyze_delivery.py` | SQL drift and cost analysis                                          |
| `analyze_notes.py`    | LLM risk extraction from notes                                       |

The data is synthetic. The patterns in it were designed deliberately so the output could be checked against a known answer — which is what made the SUP005 finding visible at all.

**Stack:** Python, SQLite, pandas, Anthropic API
