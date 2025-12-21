"""
export_transactions.py

Pull the 'transactions_transaction' table from a Postgres instance
running inside the Docker container 'japb-api' and dump it to
a CSV file named 'transactions_transaction.csv'.

Author:   <your_name>
Date:     2025‑12‑14
"""

from __future__ import annotations

import csv
import os
import sys
from contextlib import closing
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError as exc:
    sys.exit(
        "❌  psycopg2 is not installed. Install it with:\n"
        "    pip install psycopg2-binary\n"
        f"    Error: {exc}"
    )


# ----------------------------------------------------------------------
# 1️⃣  Configuration – pull from env or fall back to defaults
# ----------------------------------------------------------------------
DB_HOST = os.getenv("PGHOST", "postgres")          # Docker port mapping points to localhost
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "postgres")
DB_USER = os.getenv("PGUSER", "postgres")
DB_PASS = os.getenv("PGPASSWORD", "postgres")

TABLE_NAME = os.getenv("PGTABLE", "transactions_transaction")
CSV_FILE  = os.getenv("PGCSV_FILE", "transactions_transaction.csv")

# ----------------------------------------------------------------------
# 2️⃣  Helper – format a nice connection string
# ----------------------------------------------------------------------
def _conn_str() -> str:
    return f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASS}"


# ----------------------------------------------------------------------
# 3️⃣  Main logic
# ----------------------------------------------------------------------
def export_table_to_csv() -> None:
    """
    Connect to Postgres, fetch the entire table, and write it to CSV.
    """
    """
    print(f"[{datetime.now().isoformat()}] Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME} …")
    with closing(psycopg2.connect(_conn_str())) as conn:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(f"SELECT * FROM {TABLE_NAME};")
            rows = cur.fetchall()

            if not rows:
                print(f"⚠️  Table '{TABLE_NAME}' is empty. No CSV generated.")
                return

            # Get column names from the cursor description
            fieldnames = [desc.name for desc in cur.description]

            print(f"[{datetime.now().isoformat()}] Writing {len(rows)} rows to '{CSV_FILE}' …")
            with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            print(f"✅  Finished! CSV file saved to '{CSV_FILE}'.")
    """
    conn = psycopg2.connect(
        dbname=os.getenv("PGDATABASE", "postgres"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        host=os.getenv("PGHOST", "postgres"),
        port=os.getenv("PGPORT", "5432")
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions_transaction")

    # 1. Grab column names
    fieldnames = [desc[0] for desc in cur.description]

    # 2. Turn each row into a dict
    rows = [
        dict(zip(fieldnames, row))
        for row in cur.fetchall()
    ]

    # 3. Write header + data
    with open("transactions_transaction.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)   # rows is list of dicts

    cur.close()
    conn.close()
    print(f"[{datetime.utcnow().isoformat()}] Written {len(rows)} rows.")


if __name__ == "__main__":
    export_table_to_csv()

