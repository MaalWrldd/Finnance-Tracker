#!/usr/bin/env python3
"""
Personal Finance Tracker - single-file SQLite console app.

Usage:
    python finance_tracker.py          -> interactive menu
    python finance_tracker.py add ...  -> quick add via CLI (see --help)
Dependencies:
    - Python 3.8+
    - matplotlib (optional, for plotting)
"""

import sqlite3
import csv
import sys
import argparse
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path.home() / ".finance_tracker.db"

# ------------------------
# Database helpers
# ------------------------
def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        type TEXT CHECK(type IN ('income','expense')) NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        note TEXT
    )
    """)
    conn.commit()
    conn.close()

# ------------------------
# CRUD operations
# ------------------------
def add_transaction(tx_date, tx_type, amount, category, note=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO transactions (date, type, amount, category, note) VALUES (?, ?, ?, ?, ?)",
                (tx_date, tx_type, amount, category, note))
    conn.commit()
    conn.close()
    print("Added transaction.")

def list_transactions(start_date=None, end_date=None, category=None, tx_type=None, limit=100):
    conn = get_conn()
    cur = conn.cursor()
    q = "SELECT * FROM transactions WHERE 1=1"
    params = []
    if start_date:
        q += " AND date >= ?"; params.append(start_date)
    if end_date:
        q += " AND date <= ?"; params.append(end_date)
    if category:
        q += " AND category = ?"; params.append(category)
    if tx_type:
        q += " AND type = ?"; params.append(tx_type)
    q += " ORDER BY date DESC, id DESC LIMIT ?"; params.append(limit)
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("No transactions found.")
        return []
    # Print table
    print(f"{'ID':>3} {'Date':10} {'Type':7} {'Amount':>10} {'Category':15} Note")
    print("-"*70)
    for r in rows:
        print(f"{r['id']:>3} {r['date']:10} {r['type']:7} {r['amount']:10.2f} {r['category'][:15]:15} {r['note'] or ''}")
    return rows

def get_transaction(tx_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    r = cur.fetchone()
    conn.close()
    return r

def edit_transaction(tx_id, **fields):
    allowed = {"date","type","amount","category","note"}
    updates = []
    params = []
    for k,v in fields.items():
        if k in allowed and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        print("Nothing to update.")
        return
    params.append(tx_id)
    q = f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(q, params)
    conn.commit()
    conn.close()
    print("Transaction updated.")

def delete_transaction(tx_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()
    print("Transaction deleted.")

# ------------------------
# Reporting
# ------------------------
def monthly_summary(year=None, month=None):
    conn = get_conn()
    cur = conn.cursor()
    q = """
    SELECT type, SUM(amount) as total
    FROM transactions
    WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
    GROUP BY type
    """
    if year is None or month is None:
        today = date.today()
        year = str(today.year)
        month = f"{today.month:02d}"
    else:
        year = str(year)
        month = f"{int(month):02d}"
    cur.execute(q, (year, month))
    rows = {r['type']: r['total'] for r in cur.fetchall()}
    income = rows.get('income', 0.0) or 0.0
    expense = rows.get('expense', 0.0) or 0.0
    balance = income - expense
    print(f"Summary for {year}-{month}: Income: {income:.2f}, Expenses: {expense:.2f}, Balance: {balance:.2f}")
    conn.close()
    return {"year":year, "month":month, "income":income, "expense":expense, "balance":balance}

def category_breakdown(year=None, month=None):
    conn = get_conn()
    cur = conn.cursor()
    if year is None or month is None:
        today = date.today()
        year = str(today.year)
        month = f"{today.month:02d}"
    else:
        year = str(year)
        month = f"{int(month):02d}"
    q = """
    SELECT category, type, SUM(amount) as total
    FROM transactions
    WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
    GROUP BY category, type
    ORDER BY total DESC
    """
    cur.execute(q, (year, month))
    rows = cur.fetchall()
    if not rows:
        print("No category data for this period.")
        conn.close()
        return []
    print(f"Category breakdown for {year}-{month}:")
    print(f"{'Category':20} {'Type':8} {'Total':>10}")
    print("-"*44)
    for r in rows:
        print(f"{r['category'][:20]:20} {r['type']:8} {r['total']:10.2f}")
    conn.close()
    return rows

# ------------------------
# Export
# ------------------------
def export_csv(output_path="transactions_export.csv", start_date=None, end_date=None):
    rows = list_transactions(start_date=start_date, end_date=end_date, limit=1000000)
    if not rows:
        print("Nothing to export.")
        return
    keys = ["id","date","type","amount","category","note"]
    with open(output_path, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(keys)
        for r in rows:
            writer.writerow([r[k] for k in keys])
    print(f"Exported {len(rows)} rows to {output_path}")

# ------------------------
# Plotting (optional)
# ------------------------
def plot_monthly(years=1):
    try:
        import matplotlib.pyplot as plt
    except Exception as e:
        print("matplotlib not available. Install with: pip install matplotlib")
        return
    conn = get_conn()
    cur = conn.cursor()
    # gather last N months
    today = date.today()
    start_year = today.year - (years if today.month == 12 else years - 1)
    q = """
    SELECT strftime('%Y-%m', date) as ym, type, SUM(amount) as total
    FROM transactions
    WHERE date >= date('now','-{} months')
    GROUP BY ym, type
    ORDER BY ym
    """.format(years*12)
    cur.execute(q)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("No data to plot.")
        return
    # organize
    labels = []
    inc = {}
    exp = {}
    for r in rows:
        ym = r['ym']
        labels.append(ym) if ym not in labels else None
    labels = sorted(set(labels))
    for l in labels:
        inc[l] = 0.0
        exp[l] = 0.0
    for r in rows:
        if r['type'] == 'income':
            inc[r['ym']] = r['total']
        else:
            exp[r['ym']] = r['total']
    xs = labels
    ys_inc = [inc[x] for x in xs]
    ys_exp = [exp[x] for x in xs]
    plt.figure(figsize=(10,5))
    plt.plot(xs, ys_inc, marker='o', label='Income')
    plt.plot(xs, ys_exp, marker='o', label='Expense')
    plt.xticks(rotation=45)
    plt.title("Monthly Income vs Expense")
    plt.ylabel("Amount")
    plt.legend()
    plt.tight_layout()
    plt.show()

# ------------------------
# CLI & Interactive menu
# ------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Simple Personal Finance Tracker")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("add", help="Add a transaction from CLI")
    a.add_argument("--date", "-d", default=date.today().isoformat(), help="YYYY-MM-DD")
    a.add_argument("--type", "-t", choices=["income","expense"], required=True)
    a.add_argument("--amount", "-a", type=float, required=True)
    a.add_argument("--category", "-c", required=True)
    a.add_argument("--note", "-n", default="")

    e = sub.add_parser("list", help="List transactions (CLI)")
    e.add_argument("--start", help="start date YYYY-MM-DD")
    e.add_argument("--end", help="end date YYYY-MM-DD")
    e.add_argument("--type", choices=["income","expense"])
    e.add_argument("--category")

    ex = sub.add_parser("export", help="Export to CSV")
    ex.add_argument("--out", default="transactions_export.csv")
    ex.add_argument("--start")
    ex.add_argument("--end")

    sum_p = sub.add_parser("summary", help="Monthly summary")
    sum_p.add_argument("--year", type=int)
    sum_p.add_argument("--month", type=int)

    sub.add_parser("plot", help="Plot monthly totals (requires matplotlib)")

    return p.parse_args()

def interactive_menu():
    def help_menu():
        print("""
Commands:
  add         - add transaction
  list        - list transactions
  edit        - edit by id
  del         - delete by id
  summary     - monthly summary
  cat         - category breakdown
  export      - export CSV
  plot        - plot monthly totals (matplotlib)
  quit/exit   - exit
""")
    help_menu()
    while True:
        cmd = input("finance> ").strip().lower()
        if cmd in ("quit","exit"):
            break
        if cmd == "help":
            help_menu(); continue
        if cmd == "add":
            d = input(f"Date (YYYY-MM-DD) [{date.today().isoformat()}]: ").strip() or date.today().isoformat()
            t = input("Type (income/expense): ").strip().lower()
            amt = float(input("Amount: ").strip())
            cat = input("Category: ").strip()
            note = input("Note (optional): ").strip()
            add_transaction(d, t, amt, cat, note or None)
            continue
        if cmd == "list":
            s = input("Start date (YYYY-MM-DD, blank for none): ").strip() or None
            e = input("End date (YYYY-MM-DD, blank for none): ").strip() or None
            c = input("Category (blank for all): ").strip() or None
            t = input("Type (income/expense, blank for all): ").strip() or None
            list_transactions(start_date=s, end_date=e, category=c, tx_type=t)
            continue
        if cmd == "edit":
            tid = int(input("Transaction id: ").strip())
            r = get_transaction(tid)
            if not r:
                print("Not found."); continue
            print("Leave blank to keep current.")
            d = input(f"Date [{r['date']}]: ").strip() or None
            t = input(f"Type [{r['type']}]: ").strip() or None
            amt_input = input(f"Amount [{r['amount']}]: ").strip()
            amt = float(amt_input) if amt_input else None
            cat = input(f"Category [{r['category']}]: ").strip() or None
            note = input(f"Note [{r['note'] or ''}]: ").strip() or None
            edit_transaction(tid, date=d, type=t, amount=amt, category=cat, note=note)
            continue
        if cmd in ("del","delete"):
            tid = int(input("Transaction id to delete: ").strip())
            delete_transaction(tid)
            continue
        if cmd == "summary":
            y = input("Year (YYYY, blank for this year): ").strip() or None
            m = input("Month (1-12, blank for this month): ").strip() or None
            monthly_summary(y, m)
            continue
        if cmd == "cat":
            y = input("Year (YYYY, blank for this year): ").strip() or None
            m = input("Month (1-12, blank for this month): ").strip() or None
            category_breakdown(y, m)
            continue
        if cmd == "export":
            out = input("Filename [transactions_export.csv]: ").strip() or "transactions_export.csv"
            start = input("Start (YYYY-MM-DD, blank none): ").strip() or None
            end = input("End (YYYY-MM-DD, blank none): ").strip() or None
            export_csv(out, start, end)
            continue
        if cmd == "plot":
            plot_monthly(years=1)
            continue
        print("Unknown command. Type 'help' for options.")

def main():
    init_db()
    args = parse_args()
    if not args.cmd:
        # interactive
        interactive_menu()
        return
    if args.cmd == "add":
        add_transaction(args.date, args.type, args.amount, args.category, args.note or None)
    elif args.cmd == "list":
        list_transactions(start_date=args.start, end_date=args.end, category=args.category, tx_type=args.type)
    elif args.cmd == "export":
        export_csv(args.out, args.start, args.end)
    elif args.cmd == "summary":
        monthly_summary(args.year, args.month)
    elif args.cmd == "plot":
        plot_monthly()
    else:
        print("Command not implemented.")

if __name__ == "__main__":
    main()

