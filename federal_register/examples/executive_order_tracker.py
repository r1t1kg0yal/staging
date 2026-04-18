#!/usr/bin/env python3
"""
Executive Order Tracker
=======================
Tracks recent executive orders and related presidential documents, surfaces
plain-language summaries from Federal Register abstracts, and monitors the
public inspection queue for items nearing publication.

Workflow:
  1. Pull executive orders in a rolling publication window
  2. Attach abstracts as working summaries plus metadata (signing/publication)
  3. Pull public inspection documents for the upcoming pipeline view

Usage:
    python executive_order_tracker.py
    python executive_order_tracker.py run
    python executive_order_tracker.py run --json
    python executive_order_tracker.py pipeline --count 25
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from federal_register import (
    _fetch_documents,
    _fetch_public_inspection,
    _agency_names,
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


def _eo_summary_row(doc):
    abstract = doc.get("abstract") or ""
    return {
        "document_number": doc.get("document_number", ""),
        "executive_order_number": doc.get("executive_order_number", ""),
        "title": doc.get("title", ""),
        "signing_date": _parse_date(doc.get("signing_date", "")),
        "publication_date": _parse_date(doc.get("publication_date", "")),
        "agency": _agency_names(doc),
        "summary": _truncate(abstract.replace("\n", " "), 600),
        "html_url": doc.get("html_url", ""),
    }


def cmd_run(days=120, per_page=25, as_json=False, export_fmt=None):
    print("\n  EXECUTIVE ORDER TRACKER")
    print("  " + "=" * 72)
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    t0 = time.time()
    print(f"  Fetching executive orders ({days}d window from {date_gte})... ({int(time.time() - t0)}s)")
    docs, total, desc = _fetch_documents(
        doc_type="presidential",
        presidential_type="executive_order",
        date_gte=date_gte,
        per_page=per_page,
        page=1,
    )
    time.sleep(0.25)
    last_prog = time.time()
    extra_pages = []
    if total > per_page and per_page >= 10:
        print(f"  [{2}/2] Additional page for coverage... ({int(time.time() - t0)}s)")
        page2, _, _ = _fetch_documents(
            doc_type="presidential",
            presidential_type="executive_order",
            date_gte=date_gte,
            per_page=per_page,
            page=2,
        )
        extra_pages = page2
        time.sleep(0.25)
    now = time.time()
    if now - last_prog >= 5.0:
        print(f"  ...still assembling ({int(now - t0)}s)")
    merged = docs + extra_pages

    rows = [_eo_summary_row(d) for d in merged]
    result = {
        "timestamp": datetime.now().isoformat(),
        "window_days": days,
        "date_gte": date_gte,
        "api_total": total,
        "description": _truncate(desc or "", 200),
        "executive_orders": rows,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, "executive_order_tracker", export_fmt)
        return result

    print(f"  API reports {total:,} matching documents; showing {len(rows)} rows")
    if desc:
        print(f"  Query note: {_truncate(desc, 140)}")
    print(f"\n  {'EO #':<8} {'Signed':<12} {'Published':<12} {'Summary'}")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*52}")
    for r in rows:
        eo = str(r["executive_order_number"] or "")
        print(
            f"  {eo:<8} {r['signing_date']:<12} {r['publication_date']:<12} "
            f"{_truncate(r['summary'], 52)}"
        )

    print(f"\n  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        _export(rows if export_fmt == "csv" else result, "executive_order_tracker", export_fmt)
    return result


def cmd_pipeline(per_page=30, as_json=False, export_fmt=None):
    print("\n  PUBLIC INSPECTION PIPELINE")
    print("  " + "=" * 72)
    t0 = time.time()
    last_prog = t0
    print(f"  [{1}/1] Fetching public inspection documents... ({int(time.time() - t0)}s)")
    docs, total = _fetch_public_inspection(per_page=per_page)
    now = time.time()
    if now - last_prog >= 5.0:
        print(f"  ...records retrieved ({int(now - t0)}s)")
    rows = []
    for doc in docs:
        rows.append(
            {
                "title": doc.get("title", ""),
                "type": doc.get("type", ""),
                "filed_at": _parse_date(doc.get("filed_at", "")),
                "publication_date": _parse_date(doc.get("publication_date", "")),
                "agency": _agency_names(doc),
                "pages": doc.get("num_pages", ""),
                "html_url": doc.get("html_url", ""),
            }
        )

    result = {
        "timestamp": datetime.now().isoformat(),
        "public_inspection_total": total,
        "upcoming": rows,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, "executive_order_pipeline", export_fmt)
        return result

    print(f"  Filings in response: {len(rows)} (API total {total})")
    print(f"\n  {'Filed':<12} {'Pub date':<12} {'Type':<14} {'Agency':<22} {'Title'}")
    print(f"  {'-'*12} {'-'*12} {'-'*14} {'-'*22} {'-'*36}")
    for r in rows:
        print(
            f"  {r['filed_at']:<12} {r['publication_date']:<12} "
            f"{str(r['type'])[:14]:<14} {_truncate(r['agency'], 22):<22} "
            f"{_truncate(r['title'], 36)}"
        )

    print(f"\n  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        _export(rows if export_fmt == "csv" else result, "executive_order_pipeline", export_fmt)
    return result


MENU = """
  =====================================================
   Executive Order Tracker (Federal Register)
  =====================================================

   1) run        Recent executive orders + summaries
   2) pipeline   Public inspection (upcoming filings)

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
            d = _prompt("Days back", "120")
            n = _prompt("Per page", "25")
            cmd_run(days=int(d), per_page=int(n))
        elif choice == "2":
            n = _prompt("Count", "30")
            cmd_pipeline(per_page=int(n))
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="executive_order_tracker.py",
        description="Executive order + public inspection tracker",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Recent executive orders")
    s.add_argument("--days", type=int, default=120)
    s.add_argument("--per-page", type=int, default=25)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("pipeline", help="Public inspection queue")
    s.add_argument("--count", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(
            days=args.days,
            per_page=args.per_page,
            as_json=getattr(args, "json", False),
            export_fmt=getattr(args, "export", None),
        )
    elif args.command == "pipeline":
        cmd_pipeline(
            per_page=args.count,
            as_json=getattr(args, "json", False),
            export_fmt=getattr(args, "export", None),
        )
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
