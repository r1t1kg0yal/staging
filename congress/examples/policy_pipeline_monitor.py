#!/usr/bin/env python3
"""
Policy Pipeline Monitor
=========================
Monitors where legislation sits in the process (introduced, committee, floor,
enrolled/signed) using latest actions, surfaces recent amendments, and samples
cosponsor depth for bills that are still moving.

Workflow:
  1. Pull the newest House and Senate bills
  2. Bucket each bill by pipeline stage from latest action text
  3. List recent amendments and attach cosponsor counts for a short list of
     active bills

Usage:
    python policy_pipeline_monitor.py
    python policy_pipeline_monitor.py run
    python policy_pipeline_monitor.py run --json
    python policy_pipeline_monitor.py activity --limit 40
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
    _fetch_bills,
    _fetch_bill_actions,
    _fetch_bill_cosponsors,
    _paginate,
    _bill_id,
    _bill_title,
    _latest_action,
    _truncate,
    _parse_date,
    _prompt,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR_LOCAL, "..", "data")


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


def _pipeline_stage(bill):
    _, text = _latest_action(bill)
    t = (text or "").lower()
    if any(
        x in t
        for x in (
            "became public law",
            "signed by president",
            "presented to president",
            "enrolled",
        )
    ):
        return "signed_or_enrolled"
    if any(
        x in t
        for x in (
            "passed house",
            "passed senate",
            "agreed to in the house",
            "agreed to in the senate",
            "cloture",
            "considered",
            "motion to proceed",
            "invoke cloture",
        )
    ):
        return "floor"
    if any(
        x in t
        for x in (
            "committee",
            "referred to",
            "markup",
            "hearing",
            "ordered to be reported",
            "subcommittee",
            "discharged from",
        )
    ):
        return "committee"
    if any(
        x in t
        for x in (
            "introduced",
            "read the first time",
            "read twice",
            "received in the house",
            "received in the senate",
        )
    ):
        return "introduced"
    return "other"


def cmd_run(congress=None, per_type=120, cosponsor_sample=6, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    print(f"\n  POLICY PIPELINE MONITOR ({congress}th Congress)")
    print("  " + "=" * 72)
    t0 = time.time()
    bills = []
    last_prog = t0
    for idx, btype in enumerate(("hr", "s")):
        now = time.time()
        if now - last_prog >= 5.0:
            print(f"  [{idx + 1}/2] Fetching {btype.upper()} bills ({int(now - t0)}s)")
            last_prog = now
        chunk, total = _fetch_bills(congress=congress, bill_type=btype, limit=per_type)
        print(f"  Pulled {len(chunk)} {btype.upper()} bills (total catalog {total})")
        bills.extend(chunk)
        time.sleep(0.15)

    stages = {
        "introduced": [],
        "committee": [],
        "floor": [],
        "signed_or_enrolled": [],
        "other": [],
    }
    for bill in bills:
        stage = _pipeline_stage(bill)
        stages[stage].append(bill)

    movers = []
    for stage in ("floor", "committee"):
        movers.extend(
            sorted(
                stages[stage],
                key=lambda b: b.get("latestAction", {}).get("actionDate", ""),
                reverse=True,
            )[: cosponsor_sample if stage == "floor" else cosponsor_sample // 2 or 1]
        )

    cosponsor_rows = []
    last_prog = time.time()
    for idx, bill in enumerate(movers):
        now = time.time()
        if now - last_prog >= 5.0:
            print(
                f"  Cosponsors [{idx + 1}/{len(movers)}] {_bill_id(bill)} "
                f"({int(now - t0)}s)"
            )
            last_prog = now
        btype = bill.get("type", "").lower()
        number = str(bill.get("number", ""))
        cosp = _fetch_bill_cosponsors(congress, btype, number, limit=250)
        cosponsor_rows.append(
            {
                "bill_id": _bill_id(bill),
                "stage": _pipeline_stage(bill),
                "cosponsor_count": len(cosp),
                "last_action_date": _latest_action(bill)[0],
                "last_action_text": _truncate(_latest_action(bill)[1], 200),
            }
        )
        time.sleep(0.12)

    result = {
        "timestamp": datetime.now().isoformat(),
        "congress": congress,
        "stage_counts": {k: len(v) for k, v in stages.items()},
        "cosponsor_sample": cosponsor_rows,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, "policy_pipeline_monitor", export_fmt)
        return result

    print("\n  PIPELINE COUNTS (recent hr+s pull)")
    for stage, items in stages.items():
        print(f"    {stage:<20} {len(items):>4}")

    print("\n  SAMPLE: FLOOR / COMMITTEE BILLS")
    for stage in ("floor", "committee"):
        subset = sorted(
            stages[stage],
            key=lambda b: b.get("latestAction", {}).get("actionDate", ""),
            reverse=True,
        )[:6]
        print(f"\n  {stage.upper()} ({len(stages[stage])} total)")
        print(f"  {'Bill':<14} {'Date':<12} {'Title'}")
        print(f"  {'-'*14} {'-'*12} {'-'*52}")
        for b in subset:
            d, txt = _latest_action(b)
            print(f"  {_bill_id(b):<14} {d:<12} {_truncate(_bill_title(b, 200), 52)}")

    if cosponsor_rows:
        print("\n  COSPONSOR DEPTH (key movers)")
        print(f"  {'Bill':<14} {'Stage':<18} {'Cosponsors':>10} {'Last action'}")
        print(f"  {'-'*14} {'-'*18} {'-'*10} {'-'*40}")
        for row in cosponsor_rows:
            print(
                f"  {row['bill_id']:<14} {row['stage']:<18} "
                f"{row['cosponsor_count']:>10} {_truncate(row['last_action_text'], 40)}"
            )

    print(f"\n  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        flat = []
        for b in bills:
            d, txt = _latest_action(b)
            flat.append(
                {
                    "bill_id": _bill_id(b),
                    "stage": _pipeline_stage(b),
                    "last_action_date": d,
                    "last_action_text": _truncate(txt, 220),
                    "title": _bill_title(b, 400),
                }
            )
        _export(
            flat if export_fmt == "csv" else result,
            "policy_pipeline_monitor",
            export_fmt,
        )
    return result


def cmd_activity(congress=None, bill_limit=35, amend_limit=40, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    print(f"\n  RECENT LEGISLATIVE ACTIVITY ({congress}th Congress)")
    print("  " + "=" * 72)
    t0 = time.time()
    print(f"  [{1}/3] Amendments ({int(time.time() - t0)}s)")
    amendments = _paginate(f"amendment/{congress}", None, max_items=amend_limit)
    atotal = len(amendments)
    time.sleep(0.15)
    last_prog = time.time()
    events = []

    for a in amendments:
        la = a.get("latestAction", {}) or {}
        events.append(
            {
                "kind": "amendment",
                "date": _parse_date(la.get("actionDate", "")),
                "label": str(a.get("number", "")),
                "text": _truncate(a.get("description", a.get("purpose", "")), 220),
            }
        )

    print(f"  [{2}/3] Scanning latest bills for fresh actions ({int(time.time() - t0)}s)")
    bills = []
    for btype in ("hr", "s"):
        chunk, _ = _fetch_bills(congress=congress, bill_type=btype, limit=bill_limit)
        bills.extend(chunk)
        time.sleep(0.12)

    bills.sort(
        key=lambda b: b.get("latestAction", {}).get("actionDate", ""),
        reverse=True,
    )

    print(f"  [{3}/3] Pulling incremental actions for top movers ({int(time.time() - t0)}s)")
    for idx, bill in enumerate(bills[: min(18, len(bills))]):
        now = time.time()
        if now - last_prog >= 5.0:
            print(
                f"    actions [{idx + 1}/{min(18, len(bills))}] {_bill_id(bill)} "
                f"({int(now - t0)}s)"
            )
            last_prog = now
        btype = bill.get("type", "").lower()
        number = str(bill.get("number", ""))
        acts = _fetch_bill_actions(congress, btype, number, limit=8)
        for a in acts[:3]:
            events.append(
                {
                    "kind": "bill_action",
                    "date": _parse_date(a.get("actionDate", "")),
                    "label": _bill_id(bill),
                    "text": _truncate(a.get("text", ""), 220),
                }
            )
        time.sleep(0.1)

    events.sort(key=lambda e: e.get("date", ""), reverse=True)

    result = {
        "timestamp": datetime.now().isoformat(),
        "congress": congress,
        "amendment_rows": atotal,
        "events": events[: amend_limit + 40],
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, "policy_pipeline_activity", export_fmt)
        return result

    print(f"\n  Amendments fetched: {len(amendments)} (paginated cap {amend_limit})")
    print("\n  MERGED ACTIVITY (most recent first)")
    print(f"  {'Date':<12} {'Kind':<14} {'Ref':<16} {'Detail'}")
    print(f"  {'-'*12} {'-'*14} {'-'*16} {'-'*46}")
    for e in result["events"][:35]:
        print(
            f"  {e['date']:<12} {e['kind']:<14} {str(e['label'])[:16]:<16} "
            f"{_truncate(e['text'], 46)}"
        )

    print(f"\n  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        _export(result["events"], "policy_pipeline_activity", export_fmt)
    return result


MENU = """
  =====================================================
   Policy Pipeline Monitor (Congress.gov)
  =====================================================

   1) run        Stage buckets + cosponsor sample
   2) activity   Recent amendments + bill actions

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
            lim = _prompt("Bill scan limit", "35")
            cmd_activity(congress=int(c), bill_limit=int(lim))
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="policy_pipeline_monitor.py",
        description="Legislative pipeline monitor (Congress.gov)",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Stage grouping + cosponsor sample")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--per-type", type=int, default=120)
    s.add_argument("--cosponsor-sample", type=int, default=6)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("activity", help="Recent amendments and bill actions")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--bill-limit", type=int, default=35)
    s.add_argument("--amend-limit", type=int, default=40)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(
            congress=args.congress,
            per_type=args.per_type,
            cosponsor_sample=args.cosponsor_sample,
            as_json=getattr(args, "json", False),
            export_fmt=getattr(args, "export", None),
        )
    elif args.command == "activity":
        cmd_activity(
            congress=args.congress,
            bill_limit=args.bill_limit,
            amend_limit=args.amend_limit,
            as_json=getattr(args, "json", False),
            export_fmt=getattr(args, "export", None),
        )
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
