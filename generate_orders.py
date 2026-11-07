"""
Generates orders.csv with deliberate patterns built in.

The point of this file is the patterns, not the code. Read the
SUPPLIER_PROFILES dict below — that's the part you'll talk about
in an interview.
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)  # same data every run, so results are comparable

START = date(2025, 11, 1)   # 12 months back from "today"
TODAY = date(2026, 11, 1)

# ---------------------------------------------------------------
# The design. Each supplier gets a behaviour profile.
#
#   early_late     - avg days vs promised at the START of the period.
#                    Negative means they usually deliver EARLY, which is
#                    normal: suppliers pad their quoted lead times.
#   drift          - extra days added by the END of the period
#                    (0 = stable, positive = degrading)
#   noise          - how erratic they are week to week
#   reschedule_pct - how often the promised date moves before delivery
#   cost_drift     - % unit cost change across the period
# ---------------------------------------------------------------
SUPPLIER_PROFILES = {
    # --- The three that quietly degrade. This is what we want caught. ---
    # early_late = avg days late at the START, drift = extra days by the END
    "SUP002": dict(early_late=-1.5, drift=5.0, noise=1.2, reschedule_pct=0.30, cost_drift=0.02),
    "SUP009": dict(early_late=-1.2, drift=4.5, noise=1.4, reschedule_pct=0.25, cost_drift=0.01),
    "SUP013": dict(early_late=-1.8, drift=4.0, noise=1.2, reschedule_pct=0.22, cost_drift=0.00),

    # --- The two that are always late but predictable. Should NOT alarm. ---
    "SUP005": dict(early_late=2.5, drift=0.0, noise=1.0, reschedule_pct=0.08, cost_drift=0.01),
    "SUP011": dict(early_late=2.2, drift=0.2, noise=0.9, reschedule_pct=0.06, cost_drift=0.00),

    # --- Delivery fine, cost climbing. A different kind of risk. ---
    "SUP006": dict(early_late=-2.0, drift=0.1, noise=1.0, reschedule_pct=0.05, cost_drift=0.18),

    # --- Everyone else: stable, mostly on time. ---
    "SUP001": dict(early_late=-2.0, drift=0.0, noise=1.1, reschedule_pct=0.05, cost_drift=0.01),
    "SUP003": dict(early_late=-1.5, drift=0.2, noise=1.3, reschedule_pct=0.07, cost_drift=0.02),
    "SUP004": dict(early_late=-2.5, drift=0.0, noise=0.9, reschedule_pct=0.04, cost_drift=0.01),
    "SUP007": dict(early_late=-1.0, drift=0.3, noise=1.5, reschedule_pct=0.09, cost_drift=0.02),
    "SUP008": dict(early_late=-1.8, drift=0.0, noise=1.2, reschedule_pct=0.06, cost_drift=0.03),
    "SUP010": dict(early_late=-2.5, drift=0.0, noise=0.8, reschedule_pct=0.03, cost_drift=0.01),
    "SUP012": dict(early_late=-2.0, drift=0.1, noise=1.1, reschedule_pct=0.05, cost_drift=0.01),
    "SUP014": dict(early_late=-1.2, drift=0.2, noise=1.4, reschedule_pct=0.08, cost_drift=0.02),
    "SUP015": dict(early_late=-2.2, drift=0.0, noise=1.0, reschedule_pct=0.04, cost_drift=0.00),
}

BASE_UNIT_COST = {
    "SUP001": 42.50, "SUP002": 118.00, "SUP003": 3.75,  "SUP004": 96.20,
    "SUP005": 2.40,  "SUP006": 64.80,  "SUP007": 850.00, "SUP008": 5.10,
    "SUP009": 210.00,"SUP010": 1200.00,"SUP011": 0.85,  "SUP012": 31.60,
    "SUP013": 4.20,  "SUP014": 640.00, "SUP015": 78.90,
}

ORDERS_PER_SUPPLIER = 27  # ~400 total


def generate():
    rows = []
    order_num = 1000
    total_days = (TODAY - START).days

    for supplier_id, profile in SUPPLIER_PROFILES.items():
        for _ in range(ORDERS_PER_SUPPLIER):
            # where in the 12-month window this order falls, 0.0 to 1.0
            offset = random.randint(0, total_days - 20)
            progress = offset / total_days

            order_date = START + timedelta(days=offset)
            lead_time = random.randint(10, 25)
            promised = order_date + timedelta(days=lead_time)

            # lateness = baseline + however much drift has accumulated by now
            expected_late = profile["early_late"] + (profile["drift"] * progress)
            actual_late = round(random.gauss(expected_late, profile["noise"]))
            actual = promised + timedelta(days=actual_late)

            was_rescheduled = random.random() < profile["reschedule_pct"]

            unit_cost = round(
                BASE_UNIT_COST[supplier_id] * (1 + profile["cost_drift"] * progress), 2
            )
            quantity = random.choice([10, 25, 50, 100, 200, 500])

            order_num += 1
            rows.append({
                "order_id": f"PO{order_num}",
                "supplier_id": supplier_id,
                "order_date": order_date.isoformat(),
                "promised_date": promised.isoformat(),
                "actual_delivery_date": actual.isoformat(),
                "was_rescheduled": int(was_rescheduled),
                "quantity": quantity,
                "unit_cost": unit_cost,
                "order_value": round(quantity * unit_cost, 2),
            })

    rows.sort(key=lambda r: r["order_date"])

    with open("data/orders.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} orders to data/orders.csv")
    print(f"Date range: {rows[0]['order_date']} to {rows[-1]['order_date']}")


if __name__ == "__main__":
    generate()