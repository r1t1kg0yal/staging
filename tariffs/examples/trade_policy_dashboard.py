#!/usr/bin/env python3
"""
Trade Policy Dashboard
======================
Prints the curated tariff-actions reference, a chronological view of major
events, and chapter-level duty distribution summaries for large traded-goods
chapters. Single-sector drill-down uses the macro sector registry.

Usage:
    python trade_policy_dashboard.py
    python trade_policy_dashboard.py run --export json
    python trade_policy_dashboard.py sector autos --json
"""

import argparse
import contextlib
import csv
import io
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tariffs import (
    MACRO_CHAPTERS,
    SECTOR_KEYS,
    TARIFF_ACTIONS,
    cmd_chapter_summary,
    cmd_sector,
    cmd_tariff_actions,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
PROGRESS_EVERY_S = 5.0

DASHBOARD_CHAPTERS = (72, 73, 76, 84, 85, 87, 10, 27)


def _progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s elapsed)")
        last_print[0] = now


def _timeline_rows():
    rows = []
    for key, info in TARIFF_ACTIONS.items():
        rows.append(
            {
                "key": key,
                "year": info.get("year"),
                "description": info.get("desc"),
                "codes_prefix": info.get("codes_prefix"),
                "chapters": info.get("chapters"),
            }
        )
    rows.sort(key=lambda r: (r.get("year") or 0, r.get("key") or ""))
    return rows


def cmd_run(as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    timeline = _timeline_rows()

    summaries = []
    total = len(DASHBOARD_CHAPTERS)
    if not as_json:
        print("\n  TARIFF ACTIONS (reference)")
        cmd_tariff_actions(as_json=False)

        print("\n  TIMELINE (sorted by year)")
        print("  " + "-" * 88)
        for r in timeline:
            y = r.get("year")
            print(f"  {y}  {r.get('key')}: {r.get('description')}")

    print(f"\n  CHAPTER SUMMARIES ({total} chapters) ...")
    for i, ch in enumerate(DASHBOARD_CHAPTERS, 1):
        _progress(f"chapter summary {i}/{total} ch={ch}", t0, last)
        if not as_json:
            print(f"  [{i}/{total}] chapter {ch} ...", flush=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            summ = cmd_chapter_summary(ch, as_json=False, export_fmt=None)
        if summ:
            summaries.append(summ)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "tariff_actions": TARIFF_ACTIONS,
        "timeline": timeline,
        "chapter_summaries": summaries,
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    if export_fmt:
        _export(payload, "trade_policy_dashboard_run", export_fmt)
    return payload


def cmd_sector_focus(sector_key, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    if sector_key not in MACRO_CHAPTERS:
        print(f"  Unknown sector '{sector_key}'. Options: {', '.join(SECTOR_KEYS)}")
        return None

    _progress("sector fetch", t0, last)
    if not as_json:
        print(f"\n  Sector focus: {sector_key} ({MACRO_CHAPTERS[sector_key]['label']})")
        codes = cmd_sector(sector_key, as_json=False, export_fmt=None)
    else:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            codes = cmd_sector(sector_key, as_json=False, export_fmt=None)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "sector": sector_key,
        "sector_info": MACRO_CHAPTERS.get(sector_key),
        "codes": codes,
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))

    elapsed = int(time.time() - t0)
    print(f"  Completed in {elapsed}s")
    if export_fmt:
        _export(payload, f"trade_policy_sector_{sector_key}", export_fmt)
    return payload


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = data.get("chapter_summaries") or data.get("timeline") or data.get("codes") or []
        if rows and isinstance(rows[0], dict):
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        else:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["key", "value"])
                for k, v in data.items():
                    w.writerow([k, json.dumps(v, default=str)])
    print(f"  Exported: {path}")


MENU = """
  ============================================================
   Trade Policy Dashboard (USITC HTS)
  ============================================================

   1) run     Tariff actions + timeline + chapter summaries
   2) sector  Pull all codes/rates for one macro sector

   q) quit
"""


def _prompt(msg, default=None):
    suf = f" [{default}]" if default is not None else ""
    try:
        v = input(f"  {msg}{suf}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return v if v else (default if default is not None else "")


def interactive_loop():
    print(MENU)
    while True:
        try:
            c = input("\n  Command: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if c in ("q", "quit", "exit"):
            break
        if c in ("1", "run"):
            cmd_run()
        elif c in ("2", "sector"):
            print(f"  Sectors: {', '.join(SECTOR_KEYS)}")
            sk = _prompt("Sector key", "autos")
            if not sk:
                continue
            cmd_sector_focus(sk)
        else:
            print(f"  Unknown: {c}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="trade_policy_dashboard.py",
        description="Tariff actions timeline and chapter-level HTS dashboard",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Full dashboard")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("sector", help="Single macro sector pull")
    s.add_argument("sector", choices=SECTOR_KEYS, help="Sector key from MACRO_CHAPTERS")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if not args.command:
        interactive_loop()
        return
    if args.command == "run":
        cmd_run(as_json=args.json, export_fmt=args.export)
    elif args.command == "sector":
        cmd_sector_focus(args.sector, as_json=args.json, export_fmt=args.export)


if __name__ == "__main__":
    main()
