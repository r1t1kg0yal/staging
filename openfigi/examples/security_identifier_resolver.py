#!/usr/bin/env python3
"""
Security Identifier Resolver (OpenFIGI)
========================================
Map CUSIP, ISIN, ticker, and other ID types to FIGIs; batch-resolve comma-
separated lists; print full instrument fields (name, exchange, sector, type).

Usage:
    python security_identifier_resolver.py
    python security_identifier_resolver.py run --id-type ID_CUSIP --id-value 912810SZ9
    python security_identifier_resolver.py batch --id-type TICKER --ids IBM,AAPL --json
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from openfigi import ID_TYPES, api_map, cmd_map, _display_instruments

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
PROGRESS_EVERY_S = 5.0


def _print_progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s elapsed)")
        last_print[0] = now


def _flatten_batch(jobs, results):
    rows = []
    for job, res in zip(jobs, results):
        id_val = job.get("idValue", "")
        id_type = job.get("idType", "")
        if isinstance(res, dict) and "data" in res:
            for inst in res["data"]:
                row = dict(inst)
                row["_query_idType"] = id_type
                row["_query_idValue"] = id_val
                rows.append(row)
        else:
            rows.append({
                "_query_idType": id_type,
                "_query_idValue": id_val,
                "_error": (res or {}).get("error") if isinstance(res, dict) else str(res),
            })
    return rows


def cmd_run(id_type=None, id_value=None, exch=None, sector=None, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    if not id_type:
        if not sys.stdin.isatty():
            print("  [--id-type required in non-interactive mode]")
            return
        id_type = input("  ID type (TICKER, ID_CUSIP, ID_ISIN, ...): ").strip().upper() or "TICKER"
    if not id_value:
        if not sys.stdin.isatty():
            print("  [--id-value required in non-interactive mode]")
            return
        id_value = input("  ID value: ").strip()
    if not id_value:
        print("  [id value required]")
        return
    _print_progress("mapping", t0, last)
    result = cmd_map(
        id_type,
        id_value,
        exch_code=exch or None,
        sector=sector or None,
        as_json=as_json,
        export_fmt=None,
    )
    if export_fmt and isinstance(result, dict) and result.get("data") is not None:
        _export(
            {"query": {"idType": id_type, "idValue": id_value}, "data": result.get("data")},
            "openfigi_resolver_run",
            export_fmt,
        )
    print(f"\n  Completed in {int(time.time() - t0)}s\n")


def cmd_batch(id_type, ids_csv, exch=None, sector=None, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    parts = [x.strip() for x in ids_csv.split(",") if x.strip()]
    if not parts:
        print("  [no identifiers]")
        return
    id_type = id_type.upper()
    jobs = []
    for val in parts:
        job = {"idType": id_type, "idValue": val}
        if exch:
            job["exchCode"] = exch
        if sector:
            job["marketSecDes"] = sector
        jobs.append(job)
    print(f"\n  Batch mapping {len(jobs)} identifiers ({id_type})...")
    _print_progress("batch mapping", t0, last)
    results = api_map(jobs)
    _print_progress("batch complete", t0, last)
    flat = _flatten_batch(jobs, results)
    payload = {"jobs": jobs, "results": results, "flat": flat}

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        inst_only = [r for r in flat if "figi" in r]
        _display_instruments(inst_only, title="BATCH RESOLUTION", compact=len(inst_only) > 5)

    print(f"\n  Completed in {int(time.time() - t0)}s\n")
    if export_fmt:
        _export(payload if as_json else flat, "openfigi_resolver_batch", export_fmt)


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = data if isinstance(data, list) else None
        if isinstance(data, dict) and isinstance(data.get("flat"), list):
            rows = data["flat"]
        if rows and isinstance(rows[0], dict):
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        else:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["key", "value"])
                for k, v in (data or {}).items():
                    w.writerow([k, json.dumps(v, default=str)])
    print(f"  Exported: {path}")


MENU = """
  ============================================================
   Security Identifier Resolver (OpenFIGI)
  ============================================================

   1) run            Interactive single-ID lookup
   2) batch          Comma-separated multi-ID resolution

   i) id-types       Show supported id types (abbrev)

   q) quit
"""


def interactive_loop():
    print(MENU)
    while True:
        try:
            choice = input("\n  Command: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice in ("q", "quit", "exit"):
            break
        if choice in ("1", "run"):
            cmd_run()
        elif choice in ("2", "batch"):
            id_type = input("  ID type [TICKER]: ").strip() or "TICKER"
            ids = input("  Comma-separated IDs: ").strip()
            cmd_batch(id_type, ids)
        elif choice in ("i", "id-types"):
            print(f"\n  Common: {', '.join(list(ID_TYPES)[:8])} ... ({len(ID_TYPES)} total)\n")
        else:
            print(f"  Unknown: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="security_identifier_resolver.py",
        description="Resolve security identifiers to FIGIs via OpenFIGI",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Single identifier lookup")
    s.add_argument("--id-type", default=None, help="OpenFIGI idType")
    s.add_argument("--id-value", default=None, help="Identifier value")
    s.add_argument("--exch", default=None, help="Optional exchCode")
    s.add_argument("--sector", default=None, help="Optional marketSecDes")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("batch", help="Batch map comma-separated identifiers")
    s.add_argument("--id-type", required=True, help="OpenFIGI idType for all values")
    s.add_argument("--ids", required=True, help="Comma-separated identifier values")
    s.add_argument("--exch", default=None)
    s.add_argument("--sector", default=None)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(
            id_type=args.id_type,
            id_value=args.id_value,
            exch=args.exch,
            sector=args.sector,
            as_json=args.json,
            export_fmt=args.export,
        )
    elif args.command == "batch":
        cmd_batch(
            args.id_type,
            args.ids,
            exch=args.exch,
            sector=args.sector,
            as_json=args.json,
            export_fmt=args.export,
        )
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
