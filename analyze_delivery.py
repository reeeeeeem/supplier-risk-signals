"""
Loads the CSVs into SQLite and computes delivery metrics per supplier.

The metric that matters is DRIFT: how much worse a supplier has got
in the last 90 days compared to their own baseline. A supplier who
is always 4 days late has a drift of zero. A supplier who was on time
and is now 5 days late has a drift of 5 — and that's the one to worry
about, even though their overall average still looks fine.
"""

import sqlite3
import pandas as pd

DB = "supply.db"


def load_data():
    """Read the three CSVs into SQLite tables."""
    conn = sqlite3.connect(DB)

    for name in ["suppliers", "orders", "notes"]:
        df = pd.read_csv(f"data/{name}.csv")
        df.to_sql(name, conn, if_exists="replace", index=False)
        print(f"  loaded {len(df):>4} rows into {name}")

    return conn


# Written as real SQL rather than pandas. Date functions below are
# SQLite-specific: julianday() converts a date to a number so you can
# subtract two dates and get days.
DELIVERY_SQL = """
WITH order_performance AS (
    SELECT
        o.supplier_id,
        o.order_date,
        o.was_rescheduled,
        o.unit_cost,
        julianday(o.actual_delivery_date) - julianday(o.promised_date) AS days_late,
        CASE
            WHEN julianday(o.actual_delivery_date) <= julianday(o.promised_date)
            THEN 1 ELSE 0
        END AS on_time,
        CASE
            WHEN julianday('2026-11-01') - julianday(o.order_date) <= 90
            THEN 1 ELSE 0
        END AS is_recent
    FROM orders o
),

overall AS (
    SELECT
        supplier_id,
        COUNT(*)                                  AS total_orders,
        ROUND(AVG(on_time) * 100, 1)              AS on_time_pct_all,
        ROUND(AVG(days_late), 2)                  AS avg_days_late_all,
        SUM(was_rescheduled)                      AS reschedules
    FROM order_performance
    GROUP BY supplier_id
),

recent AS (
    SELECT
        supplier_id,
        COUNT(*)                                  AS recent_orders,
        ROUND(AVG(on_time) * 100, 1)              AS on_time_pct_90d,
        ROUND(AVG(days_late), 2)                  AS avg_days_late_90d
    FROM order_performance
    WHERE is_recent = 1
    GROUP BY supplier_id
),

cost_trend AS (
    SELECT
        supplier_id,
        ROUND(
            (AVG(CASE WHEN is_recent = 1 THEN unit_cost END)
             / AVG(CASE WHEN is_recent = 0 THEN unit_cost END) - 1) * 100
        , 1) AS cost_change_pct
    FROM order_performance
    GROUP BY supplier_id
)

SELECT
    s.supplier_id,
    s.supplier_name,
    s.category,
    o.total_orders,
    o.on_time_pct_all,
    r.on_time_pct_90d,
    o.avg_days_late_all,
    r.avg_days_late_90d,
    ROUND(r.avg_days_late_90d - o.avg_days_late_all, 2) AS drift_days,
    o.reschedules,
    c.cost_change_pct
FROM suppliers s
JOIN overall     o ON o.supplier_id = s.supplier_id
LEFT JOIN recent r ON r.supplier_id = s.supplier_id
LEFT JOIN cost_trend c ON c.supplier_id = s.supplier_id
ORDER BY drift_days DESC;
"""


def main():
    print("Loading data...")
    conn = load_data()

    print("\nRunning delivery analysis...\n")
    df = pd.read_sql_query(DELIVERY_SQL, conn)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(df.to_string(index=False))

    print("\n" + "=" * 70)
    print("Suppliers with the largest degradation (drift > 1.5 days):")
    print("=" * 70)
    flagged = df[df["drift_days"] > 1.5]
    if len(flagged):
        for _, row in flagged.iterrows():
            print(f"  {row['supplier_id']}  {row['supplier_name']:<24} "
                  f"drift {row['drift_days']:>5} days   "
                  f"on-time {row['on_time_pct_all']}% -> {row['on_time_pct_90d']}%")
    else:
        print("  none")

    print("\nCost pressure (unit cost up more than 5%):")
    cost = df[df["cost_change_pct"] > 5]
    if len(cost):
        for _, row in cost.iterrows():
            print(f"  {row['supplier_id']}  {row['supplier_name']:<24} "
                  f"+{row['cost_change_pct']}%")
    else:
        print("  none")

    df.to_csv("output_delivery_metrics.csv", index=False)
    print("\nSaved to output_delivery_metrics.csv")
    conn.close()


if __name__ == "__main__":
    main()