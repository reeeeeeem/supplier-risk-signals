"""
Reads each supplier's buyer notes and asks Claude to extract risk signals.

The delivery metrics tell you a supplier has already slipped. The notes
are where the warning lives before that shows up in the numbers — a
mention of capacity, a contact who left, a date that keeps moving.

The hard part is not calling the API. It's getting the model to stay
quiet when the notes are routine. Models over-flag by default.
"""

import json
import os
import sqlite3

import pandas as pd
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

MODEL = "claude-sonnet-4-6"
DB = "supply.db"


SYSTEM_PROMPT = """You review buyer notes about suppliers and identify early \
warning signs of supply risk.

Most notes are routine. Say so when they are. Do not invent concern.

Signals that matter:
- CAPACITY: longer lead times, running extra shifts, line downtime, hedging on volume
- PERSONNEL: contacts leaving, repeated account manager changes, no clear backup
- EVASIVE: vague answers, slow or no response, won't commit a date in writing
- RESCHEDULE: dates moving repeatedly, especially without explanation
- QUALITY: holds, defects, damage, particularly if recurring
- COST: price increases, renegotiation requests, pushing back on agreed rates

What does NOT count as a signal:
- A single reschedule with a clear reason
- One quality issue that was resolved
- Routine confirmations, acknowledgements, or check-ins
- A supplier who is consistently slow but shows no change in behaviour

Pay attention to CHANGE OVER TIME. Notes are given in date order. A supplier
who has always had minor issues is different from one whose notes are getting
worse. The second is the real signal.

Return only valid JSON, no other text:
{
  "risk_level": "none" | "low" | "medium" | "high",
  "signals": ["CAPACITY", "EVASIVE"],
  "reasoning": "one or two sentences, specific to these notes",
  "trend": "stable" | "worsening" | "improving",
  "key_notes": ["the note text that most supports your read"]
}"""


def get_notes_by_supplier(conn):
    """Pull notes grouped by supplier, in date order."""
    query = """
        SELECT n.supplier_id, s.supplier_name, n.note_date, n.note_text
        FROM notes n
        JOIN suppliers s ON s.supplier_id = n.supplier_id
        ORDER BY n.supplier_id, n.note_date
    """
    df = pd.read_sql_query(query, conn)
    return df.groupby(["supplier_id", "supplier_name"])


def analyze_supplier(supplier_id, supplier_name, notes_df):
    """Send one supplier's notes to the model, get structured risk back."""
    notes_text = "\n".join(
        f"{row.note_date}: {row.note_text}" for row in notes_df.itertuples()
    )

    user_message = (
        f"Supplier: {supplier_name} ({supplier_id})\n"
        f"Notes in date order:\n\n{notes_text}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Models sometimes wrap JSON in markdown fences. Strip them.
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"  WARNING: {supplier_id} returned unparseable JSON")
        print(f"  Raw output: {raw[:200]}")
        return {
            "risk_level": "unknown",
            "signals": [],
            "reasoning": "parse failure",
            "trend": "unknown",
            "key_notes": [],
        }


def main():
    conn = sqlite3.connect(DB)
    grouped = get_notes_by_supplier(conn)

    results = []
    print(f"Analyzing notes for {len(grouped)} suppliers...\n")

    for (supplier_id, supplier_name), notes_df in grouped:
        print(f"  {supplier_id} {supplier_name}... ", end="", flush=True)
        result = analyze_supplier(supplier_id, supplier_name, notes_df)
        print(f"{result['risk_level']} ({result['trend']})")

        results.append({
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "note_count": len(notes_df),
            "risk_level": result["risk_level"],
            "trend": result["trend"],
            "signals": ", ".join(result["signals"]),
            "reasoning": result["reasoning"],
        })

    df = pd.DataFrame(results)

    order = {"high": 0, "medium": 1, "low": 2, "none": 3, "unknown": 4}
    df["_sort"] = df["risk_level"].map(order)
    df = df.sort_values("_sort").drop(columns="_sort")

    print("\n" + "=" * 70)
    print("TEXT SIGNAL ANALYSIS")
    print("=" * 70)
    for _, row in df.iterrows():
        if row["risk_level"] in ("high", "medium"):
            print(f"\n{row['supplier_id']}  {row['supplier_name']}")
            print(f"  risk: {row['risk_level']}   trend: {row['trend']}")
            print(f"  signals: {row['signals']}")
            print(f"  {row['reasoning']}")

    df.to_csv("output_note_signals.csv", index=False)
    print("\n\nSaved to output_note_signals.csv")
    conn.close()


if __name__ == "__main__":
    main()