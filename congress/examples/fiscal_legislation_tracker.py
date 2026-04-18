#!/usr/bin/env python3
"""
Fiscal Legislation Tracker
==========================
Tracks tax, spending, debt ceiling, and appropriations-related bills in the
current Congress using curated macro topics and fiscal keyword scans. Pulls
recent bills, classifies them, and attaches action timelines for review.

Workflow:
  1. Scan MACRO_TOPICS buckets relevant to fiscal policy
  2. Augment with a client-side fiscal keyword pass on recent House/Senate bills
  3. Categorize each bill (tax, spending, trade, regulation)
  4. Fetch action timelines for the most recently updated bills

Usage:
    python fiscal_legislation_tracker.py
    python fiscal_legislation_tracker.py run
    python fiscal_legislation_tracker.py run --json
    python fiscal_legislation_tracker.py run --export json
    python fiscal_legislation_tracker.py bill-detail 119 hr 1
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from congress import (
    CURRENT_CONGRESS,
    MACRO_TOPICS,
    BILL_TYPES,
    _paginate,
    _fetch_bill_detail,
    _fetch_bill_actions,
    _bill_id,
    _bill_title,
    _latest_action,
    _truncate,
    _parse_date,
    _prompt,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR_LOCAL, "..", "data")

FISCAL_TOPIC_KEYS = ("debt_ceiling", "tax", "appropriations", "tariff", "financial_reg")

FISCAL_TITLE_KEYWORDS = (
    "tax", "appropriation", "spending", "debt limit", "debt ceiling",
    "budget", "reconciliation", "continuing resolution", "omnibus",
    "tariff", "trade", "levy", "excise",
)


def _export(data, prefix, fmt):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(
        DATA_DIR,
        f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}",
    )
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  Exported: {path}")
    elif fmt == "csv":
        rows = data if isinstance(data, list) else []
        if not rows:
            print("  No rows to export.")
            return
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"  Exported: {path}")


def _categorize_bill(bill):
    title = (bill.get("title", "") or "").lower()
    cats = []
    if any(w in title for w in ("tax", "tcja", "irs", "revenue", "excise", "levy")):
        cats.append("tax")
    if any(
        w in title
        for w in (
            "appropriat",
            "spending",
            "omnibus",
            "budget",
            "shutdown",
            "continuing resolution",
            "supplemental",
            "debt limit",
            "debt ceiling",
            "borrowing",
        )
    ):
        cats.append("spending")
    if any(w in title for w in ("tariff", "trade", "customs", "import", "export")):
        cats.append("trade")
    if any(
        w in title
        for w in (
            "regulation",
            "dodd-frank",
            "bank",
            "financial stability",
            "securities",
            "derivative",
        )
    ):
        cats.append("regulation")
    if not cats:
        cats.append("other")
    return sorted(set(cats))


def _collect_fiscal_bills(congress, bill_limit_per_type, t0, progress_every=5.0):
    seen = {}
    topic_keys = [k for k in FISCAL_TOPIC_KEYS if k in MACRO_TOPICS]
    total_steps = len(topic_keys) * len(("hr", "s", "hjres", "sjres")) + 2
    step = 0
    last_prog = t0

    for topic_key in topic_keys:
        topic = MACRO_TOPICS[topic_key]
        terms = topic["terms"]
        for btype in ("hr", "s", "hjres", "sjres"):
            step += 1
            now = time.time()
            if now - last_prog >= progress_every:
                print(
                    f"  [{step}/{total_steps}] topic={topic_key} "
                    f"type={btype} ({int(now - t0)}s elapsed)"
                )
                last_prog = now
            bills = _paginate(
                f"bill/{congress}/{btype}", None, max_items=bill_limit_per_type
            )
            for bill in bills:
                title = (bill.get("title", "") or "").lower()
                if any(t.lower() in title for t in terms):
                    key = f"{bill.get('type', '')}-{bill.get('number', '')}"
                    if key not in seen:
                        seen[key] = {"bill": bill, "sources": []}
                    seen[key]["sources"].append(f"topic:{topic_key}")
            time.sleep(0.15)

    for btype in ("hr", "s"):
        step += 1
        now = time.time()
        if now - last_prog >= progress_every:
            print(f"  [{step}/{total_steps}] keyword scan {btype} ({int(now - t0)}s)")
            last_prog = now
        bills = _paginate(
            f"bill/{congress}/{btype}", None, max_items=bill_limit_per_type
        )
        for bill in bills:
            title = (bill.get("title", "") or "").lower()
            if any(k in title for k in FISCAL_TITLE_KEYWORDS):
                key = f"{bill.get('type', '')}-{bill.get('number', '')}"
                if key not in seen:
                    seen[key] = {"bill": bill, "sources": []}
                if "keyword:title" not in seen[key]["sources"]:
                    seen[key]["sources"].append("keyword:title")
        time.sleep(0.15)

    merged = list(seen.values())
    merged.sort(
        key=lambda x: x["bill"].get("latestAction", {}).get("actionDate", ""),
        reverse=True,
    )
    return merged


def cmd_run(congress=None, bill_limit=200, action_top=12, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    print(f"\n  FISCAL LEGISLATION TRACKER ({congress}th Congress)")
    print("  " + "=" * 72)
    t0 = time.time()
    print(f"  Collecting fiscal bills (limit {bill_limit} per type scan)...")
    rows = _collect_fiscal_bills(congress, bill_limit, t0)

    out_bills = []
    for entry in rows:
        b = entry["bill"]
        cats = _categorize_bill(b)
        adate, atext = _latest_action(b)
        out_bills.append(
            {
                "bill_id": _bill_id(b),
                "congress": b.get("congress", ""),
                "type": b.get("type", ""),
                "number": b.get("number", ""),
                "title": b.get("title", ""),
                "categories": cats,
                "sources": entry["sources"],
                "last_action_date": adate,
                "last_action_text": _truncate(atext, 240),
            }
        )

    timelines = []
    n_act = min(action_top, len(rows))
    last_prog = t0
    for idx in range(n_act):
        b = rows[idx]["bill"]
        btype = b.get("type", "").lower()
        number = str(b.get("number", ""))
        now = time.time()
        if now - last_prog >= 5.0:
            print(
                f"  Actions [{idx + 1}/{n_act}] {_bill_id(b)} "
                f"({int(now - t0)}s elapsed)"
            )
            last_prog = now
        actions = _fetch_bill_actions(congress, btype, number, limit=40)
        timelines.append(
            {
                "bill_id": _bill_id(b),
                "actions": [
                    {
                        "date": _parse_date(a.get("actionDate", "")),
                        "type": a.get("type", ""),
                        "text": _truncate(a.get("text", ""), 400),
                    }
                    for a in actions
                ],
            }
        )
        time.sleep(0.12)

    result = {
        "timestamp": datetime.now().isoformat(),
        "congress": congress,
        "bill_count": len(out_bills),
        "bills": out_bills,
        "timelines": timelines,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, "fiscal_legislation_tracker", export_fmt)
        return result

    by_cat = {"tax": [], "spending": [], "trade": [], "regulation": [], "other": []}
    for ob in out_bills:
        placed = False
        for c in ob["categories"]:
            if c in by_cat:
                by_cat[c].append(ob)
                placed = True
        if not placed:
            by_cat["other"].append(ob)

    print(f"\n  Bills matched: {len(out_bills)}")
    for label, items in by_cat.items():
        if not items:
            continue
        print(f"\n  {label.upper()} ({len(items)})")
        print(f"  {'Bill':<14} {'Date':<12} {'Title'}")
        print(f"  {'-'*14} {'-'*12} {'-'*52}")
        for ob in items[:8]:
            print(
                f"  {ob['bill_id']:<14} {ob['last_action_date']:<12} "
                f"{_truncate(ob['title'], 52)}"
            )
        if len(items) > 8:
            print(f"    ... {len(items) - 8} more")

    print(f"\n  ACTION SNAPSHOTS (top {n_act} by recency)")
    for tl in timelines:
        print(f"\n  {tl['bill_id']}")
        for a in tl["actions"][:5]:
            print(f"    {a['date']:<12} {_truncate(a['text'], 70)}")

    print(f"\n  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        flat = []
        for ob in out_bills:
            row = dict(ob)
            row["categories"] = ",".join(ob["categories"])
            row["sources"] = ",".join(ob["sources"])
            flat.append(row)
        _export(flat if export_fmt == "csv" else result, "fiscal_legislation_tracker", export_fmt)
    return result


def cmd_bill_detail(congress, bill_type, number, as_json=False, export_fmt=None):
    print(f"\n  BILL DETAIL {bill_type.upper()} {number} ({congress})")
    t0 = time.time()
    bill = _fetch_bill_detail(congress, bill_type, number)
    if not bill:
        print("  Bill not found or API unavailable.")
        return None
    actions = _fetch_bill_actions(congress, bill_type, number, limit=80)
    payload = {
        "timestamp": datetime.now().isoformat(),
        "bill": bill,
        "actions": actions,
        "categories": _categorize_bill(bill),
    }
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        cats = ", ".join(payload["categories"])
        print(f"  Categories: {cats}")
        print(f"  Title: {_truncate(bill.get('title', ''), 900)}")
        print(f"\n  ACTIONS ({len(actions)})")
        for a in actions[:25]:
            d = _parse_date(a.get("actionDate", ""))
            print(f"    {d:<12} {_truncate(a.get('text', ''), 76)}")
        if len(actions) > 25:
            print(f"    ... {len(actions) - 25} more")
    print(f"  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        _export(payload, "fiscal_bill_detail", export_fmt)
    return payload


MENU = """
  =====================================================
   Fiscal Legislation Tracker (Congress.gov)
  =====================================================

   1) run            Scan fiscal bills + action timelines
   2) bill-detail    Deep dive on one bill

   q) quit
"""


def interactive_loop():
    print(MENU)
    while True:
        try:
            choice = _prompt("\n  Command").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice in ("q", "quit", "exit"):
            break
        if choice == "1":
            c = _prompt("Congress", str(CURRENT_CONGRESS))
            cmd_run(congress=int(c))
        elif choice == "2":
            c = _prompt("Congress", str(CURRENT_CONGRESS))
            bt = _prompt("Bill type (hr/s/...)", "hr")
            num = _prompt("Bill number")
            cmd_bill_detail(int(c), bt, num)
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="fiscal_legislation_tracker.py",
        description="Fiscal legislation tracker (Congress.gov)",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Scan fiscal bills and timelines")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--bill-limit", type=int, default=200)
    s.add_argument("--action-top", type=int, default=12)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("bill-detail", help="Single bill deep dive")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(
            congress=args.congress,
            bill_limit=args.bill_limit,
            action_top=args.action_top,
            as_json=getattr(args, "json", False),
            export_fmt=getattr(args, "export", None),
        )
    elif args.command == "bill-detail":
        cmd_bill_detail(
            args.congress,
            args.bill_type,
            args.number,
            as_json=getattr(args, "json", False),
            export_fmt=getattr(args, "export", None),
        )
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
