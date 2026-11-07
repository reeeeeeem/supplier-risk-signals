"""
Generates notes.csv — short buyer notes attached to suppliers over time.

The design: for the three degrading suppliers (SUP002, SUP009, SUP013),
the notes carry quiet early signals BEFORE the delivery metrics move.
For everyone else the notes are mostly routine.

That gap is the whole point. The metrics tell you a supplier has already
slipped. The notes tell you they're about to.
"""

import csv
import random
from datetime import date, timedelta

random.seed(7)

START = date(2025, 11, 1)
TODAY = date(2026, 11, 1)

# ---------------------------------------------------------------
# Routine notes. These should dominate. Real note logs are boring.
# ---------------------------------------------------------------
ROUTINE = [
    "Confirmed delivery for the {d}th.",
    "Received, counts matched.",
    "No issues this cycle.",
    "PO acknowledged same day.",
    "Shipment tracking looks on schedule.",
    "Quick call to confirm specs, all good.",
    "Invoice matched PO, sent to AP.",
    "Standard reorder placed.",
    "They flagged a holiday closure next month, planned around it.",
    "Delivered a day early, no complaints.",
    "Routine check-in, nothing to report.",
    "Spec question answered within the hour.",
]

# ---------------------------------------------------------------
# Early-warning notes. Vague, human, easy to scroll past.
# Grouped by the kind of signal they represent.
# ---------------------------------------------------------------
EARLY_SIGNALS = {
    "capacity": [
        "Asked about lead time for a bigger order, answer was non-committal.",
        "Mentioned they're running a second shift to keep up.",
        "Said their line was down briefly last week, caught up since.",
        "Quoted a longer lead time than usual, didn't say why.",
    ],
    "personnel": [
        "New contact, {name} has moved on. Had to re-explain the spec.",
        "Account manager changed again, third one this year.",
        "{name} out, no clear backup. Took two days to get an answer.",
        "Their ops lead left, new person still getting up to speed.",
    ],
    "evasive": [
        "Asked for a firm date twice, got 'soon' both times.",
        "No response to Tuesday's email, followed up Thursday.",
        "Vague on the delay reason. Said 'logistics'.",
        "Confirmed verbally but wouldn't put the date in writing.",
    ],
    "reschedule": [
        "Pushed the date again. Second time this order.",
        "Rescheduled, now the {d}th. No explanation given.",
        "Asked to move delivery out a week.",
    ],
    "quality": [
        "Minor quality hold, they sorted it but it cost us two days.",
        "Dimensional issue on three units, replaced.",
        "Packaging damage on arrival, second time recently.",
    ],
}

# Cost-pressure signals — only for SUP006, whose delivery is fine
COST_SIGNALS = [
    "Raised pricing again, said material costs.",
    "Pushing back on the current rate card.",
    "Asked to renegotiate terms mid-contract.",
    "Quoted 8% above last order for the same part.",
]

NAMES = ["Priya", "Tom", "Marcus", "Yuki", "Dana", "Rafael", "Ingrid", "Sam"]

# ---------------------------------------------------------------
# How many notes each supplier gets, and how risky they are.
#
#   signal_rate = fraction of notes that carry a warning signal
#   ramp        = True means signals cluster in the SECOND half
#                 of the year, i.e. they appear as things degrade
# ---------------------------------------------------------------
PROFILES = {
    # the three degrading ones — signals ramp up over time
    "SUP002": dict(n=16, signal_rate=0.45, ramp=True,  kinds=["capacity", "evasive", "reschedule"]),
    "SUP009": dict(n=15, signal_rate=0.40, ramp=True,  kinds=["personnel", "evasive", "quality"]),
    "SUP013": dict(n=14, signal_rate=0.40, ramp=True,  kinds=["capacity", "reschedule", "personnel"]),

    # consistently late but stable — a few reschedules, no escalation
    "SUP005": dict(n=12, signal_rate=0.20, ramp=False, kinds=["reschedule"]),
    "SUP011": dict(n=11, signal_rate=0.15, ramp=False, kinds=["reschedule"]),

    # cost pressure, delivery fine
    "SUP006": dict(n=12, signal_rate=0.35, ramp=True,  kinds=["cost"]),

    # the stable majority
    "SUP001": dict(n=10, signal_rate=0.08, ramp=False, kinds=["quality"]),
    "SUP003": dict(n=11, signal_rate=0.10, ramp=False, kinds=["reschedule"]),
    "SUP004": dict(n=9,  signal_rate=0.05, ramp=False, kinds=["capacity"]),
    "SUP007": dict(n=12, signal_rate=0.10, ramp=False, kinds=["evasive"]),
    "SUP008": dict(n=10, signal_rate=0.08, ramp=False, kinds=["quality"]),
    "SUP010": dict(n=8,  signal_rate=0.05, ramp=False, kinds=["personnel"]),
    "SUP012": dict(n=10, signal_rate=0.08, ramp=False, kinds=["reschedule"]),
    "SUP014": dict(n=11, signal_rate=0.10, ramp=False, kinds=["evasive"]),
    "SUP015": dict(n=9,  signal_rate=0.05, ramp=False, kinds=["quality"]),
}


def fill(template):
    return template.format(d=random.randint(1, 28), name=random.choice(NAMES))


def generate():
    rows = []
    note_num = 500
    total_days = (TODAY - START).days

    for supplier_id, p in PROFILES.items():
        for _ in range(p["n"]):
            offset = random.randint(0, total_days)
            progress = offset / total_days
            note_date = START + timedelta(days=offset)

            # if ramping, signals get more likely later in the year
            rate = p["signal_rate"] * (0.3 + 1.4 * progress) if p["ramp"] else p["signal_rate"]

            if random.random() < rate:
                kind = random.choice(p["kinds"])
                pool = COST_SIGNALS if kind == "cost" else EARLY_SIGNALS[kind]
                text = fill(random.choice(pool))
            else:
                text = fill(random.choice(ROUTINE))

            note_num += 1
            rows.append({
                "note_id": f"N{note_num}",
                "supplier_id": supplier_id,
                "note_date": note_date.isoformat(),
                "note_text": text,
            })

    rows.sort(key=lambda r: r["note_date"])

    with open("data/notes.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} notes to data/notes.csv")


if __name__ == "__main__":
    generate()