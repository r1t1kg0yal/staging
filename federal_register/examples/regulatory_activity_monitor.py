#!/usr/bin/env python3
"""
Regulatory Activity Monitor
===========================
Tracks recent Federal Register activity for core financial regulators (SEC,
CFTC, Federal Reserve, OCC, FDIC, Treasury). Counts final rules, proposed
rules, and notices, highlights economically significant items, and supports a
single-agency drill-down.

Workflow:
  1. Pull a recent window of documents per regulator
  2. Summarize counts by document type and significance flag
  3. Optionally repeat the pull for one agency with richer paging

Usage:
    python regulatory_activity_monitor.py
    python regulatory_activity_monitor.py run
    python regulatory_activity_monitor.py run --json
    python regulatory_activity_monitor.py agency-focus sec
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
    AGENCY_REGISTRY,
    _fetch_documents,
    _agency_names,
    _truncate,
    _parse_date,
    _short_type,
    _prompt,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR_LOCAL, "..", "data")

FIN_WATCH = ("sec", "cftc", "fed", "occ", "fdic", "treasury")


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


def _flatten_doc(doc):
    return {
        "document_number": doc.get("document_number", ""),
        "title": doc.get("title", ""),
        "type": doc.get("type", ""),
        "subtype": doc.get("subtype", ""),
        "publication_date": _parse_date(doc.get("publication_date", "")),
        "agency": _agency_names(doc),
        "significant": bool(doc.get("significant")),
        "abstract": _truncate(doc.get("abstract", ""), 400),
        "html_url": doc.get("html_url", ""),
    }


def _summarize_docs(docs):
    by_type = {}
    sig = []
    for doc in docs:
        key = doc.get("type") or doc.get("subtype") or "unknown"
        by_type[key] = by_type.get(key, 0) + 1
        if doc.get("significant"):
            sig.append(doc)
    return by_type, sig


def cmd_run(days=45, per_page=40, as_json=False, export_fmt=None):
    print("\n  REGULATORY ACTIVITY MONITOR (financial agencies)")
    print("  " + "=" * 72)
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    t0 = time.time()
    last_prog = t0
    agencies_out = []
    flat_docs = []

    for idx, alias in enumerate(FIN_WATCH):
        now = time.time()
        if now - last_prog >= 5.0:
            print(
                f"  [{idx + 1}/{len(FIN_WATCH)}] {alias.upper()} "
                f"({int(now - t0)}s elapsed)"
            )
            last_prog = now
        info = AGENCY_REGISTRY[alias]
        docs, total, desc = _fetch_documents(
            agency_alias=alias,
            date_gte=date_gte,
            per_page=per_page,
            page=1,
        )
        by_type, sig = _summarize_docs(docs)
        row = {
            "alias": alias,
            "name": info["name"],
            "api_total_count": total,
            "page_sample_size": len(docs),
            "types_in_page": by_type,
            "significant_in_page": len(sig),
            "description": _truncate(desc or "", 160),
        }
        agencies_out.append(row)
        for d in docs:
            fd = _flatten_doc(d)
            fd["_agency_alias"] = alias
            flat_docs.append(fd)
        time.sleep(0.35)

    print(f"  [{len(FIN_WATCH) + 1}/{len(FIN_WATCH) + 1}] Significant rules (all agencies)... ({int(time.time() - t0)}s)")
    sig_docs, sig_total, _ = _fetch_documents(
        significant_only=True,
        date_gte=date_gte,
        per_page=min(per_page, 50),
        page=1,
    )
    fin_ids = {AGENCY_REGISTRY[a]["id"] for a in FIN_WATCH}
    sig_fin = []
    for doc in sig_docs:
        aids = {a.get("id") for a in doc.get("agencies", []) if isinstance(a, dict)}
        if aids & fin_ids:
            sig_fin.append(doc)

    result = {
        "timestamp": datetime.now().isoformat(),
        "window_days": days,
        "date_gte": date_gte,
        "agencies": agencies_out,
        "significant_all_count": sig_total,
        "significant_financial_sample": [_flatten_doc(d) for d in sig_fin],
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, "regulatory_activity_monitor", export_fmt)
        return result

    print(f"\n  Window: last {days} days (from {date_gte})")
    for row in agencies_out:
        print(f"\n  {row['name']}")
        print(f"    API total: {row['api_total_count']:,} | page sample: {row['page_sample_size']}")
        print(f"    Significant (page): {row['significant_in_page']}")
        if row["types_in_page"]:
            parts = [f"{k}: {v}" for k, v in sorted(row["types_in_page"].items())]
            print(f"    Types in page: {', '.join(parts)}")

    print(f"\n  SIGNIFICANT RULES (financial agencies in first page): {len(sig_fin)}")
    for doc in sig_fin[:10]:
        print(
            f"    {_parse_date(doc.get('publication_date', ''))} "
            f"{_short_type(doc):<12} {_truncate(doc.get('title', ''), 58)}"
        )

    print(f"\n  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        _export(flat_docs if export_fmt == "csv" else result, "regulatory_activity_monitor", export_fmt)
    return result


def cmd_agency_focus(alias, days=90, pages=2, per_page=25, as_json=False, export_fmt=None):
    alias = alias.lower()
    if alias not in AGENCY_REGISTRY:
        print(f"  Unknown agency alias: {alias}")
        return None
    info = AGENCY_REGISTRY[alias]
    print(f"\n  AGENCY FOCUS: {info['name']} ({alias})")
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    t0 = time.time()
    last_prog = t0
    combined = []
    for page in range(1, pages + 1):
        now = time.time()
        if now - last_prog >= 5.0:
            print(f"  Page {page}/{pages} ({int(now - t0)}s)")
            last_prog = now
        docs, total, desc = _fetch_documents(
            agency_alias=alias,
            date_gte=date_gte,
            per_page=per_page,
            page=page,
        )
        combined.extend(docs)
        if len(docs) < per_page:
            break
        time.sleep(0.35)

    by_dtype = {k: [] for k in ("rule", "proposed", "notice")}
    for doc in combined:
        dtype = doc.get("type", "")
        if dtype == "Rule":
            by_dtype["rule"].append(doc)
        elif dtype == "Proposed Rule":
            by_dtype["proposed"].append(doc)
        elif dtype == "Notice":
            by_dtype["notice"].append(doc)

    payload = {
        "timestamp": datetime.now().isoformat(),
        "alias": alias,
        "agency": info["name"],
        "window_days": days,
        "date_gte": date_gte,
        "documents": [_flatten_doc(d) for d in combined],
        "counts": {k: len(v) for k, v in by_dtype.items()},
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        if export_fmt:
            _export(payload, f"regulatory_agency_{alias}", export_fmt)
        return payload

    print(f"  Window: {days}d from {date_gte} | rows pulled: {len(combined)}")
    for key, label in (("rule", "FINAL RULES"), ("proposed", "PROPOSED RULES"), ("notice", "NOTICES")):
        items = by_dtype[key]
        print(f"\n  {label} ({len(items)})")
        print(f"  {'Date':<12} {'Sig':>3} {'Type':<12} {'Title'}")
        print(f"  {'-'*12} {'-'*3} {'-'*12} {'-'*48}")
        for doc in items[:12]:
            sig = "Y" if doc.get("significant") else ""
            print(
                f"  {_parse_date(doc.get('publication_date', '')):<12} {sig:>3} "
                f"{_short_type(doc):<12} {_truncate(doc.get('title', ''), 48)}"
            )
        if len(items) > 12:
            print(f"    ... {len(items) - 12} more")

    print(f"\n  Completed in {int(time.time() - t0)}s")
    if export_fmt:
        if export_fmt == "csv":
            _export(payload["documents"], f"regulatory_agency_{alias}", export_fmt)
        else:
            _export(payload, f"regulatory_agency_{alias}", export_fmt)
    return payload


MENU = """
  =====================================================
   Regulatory Activity Monitor (Federal Register)
  =====================================================

   1) run             Financial regulator sweep
   2) agency-focus    Single agency drill-down

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
            d = _prompt("Days back", "45")
            cmd_run(days=int(d))
        elif choice == "2":
            print(f"  Aliases: {', '.join(FIN_WATCH)}")
            al = _prompt("Agency alias", "sec")
            d = _prompt("Days back", "90")
            cmd_agency_focus(al, days=int(d))
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="regulatory_activity_monitor.py",
        description="Financial regulatory activity monitor",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Multi-agency sweep")
    s.add_argument("--days", type=int, default=45)
    s.add_argument("--per-page", type=int, default=40)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("agency-focus", help="Deep dive on one agency")
    s.add_argument("alias", choices=list(AGENCY_REGISTRY.keys()))
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--pages", type=int, default=2)
    s.add_argument("--per-page", type=int, default=25)
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
    elif args.command == "agency-focus":
        cmd_agency_focus(
            args.alias,
            days=args.days,
            pages=args.pages,
            per_page=args.per_page,
            as_json=getattr(args, "json", False),
            export_fmt=getattr(args, "export", None),
        )
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
