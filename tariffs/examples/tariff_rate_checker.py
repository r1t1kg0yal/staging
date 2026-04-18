#!/usr/bin/env python3
"""
Tariff Rate Checker
===================
Scans representative HTS lines across macro sectors (steel/aluminum, autos,
electronics, agriculture) and supports single-code duty lookups with general,
special, and other rate columns.

Usage:
    python tariff_rate_checker.py
    python tariff_rate_checker.py run --export json
    python tariff_rate_checker.py lookup 8703.23.01 --json
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tariffs import (
    MACRO_CHAPTERS,
    _fetch_search,
    _flatten_code,
    _safe_str,
    _truncate,
    cmd_duty,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
PROGRESS_EVERY_S = 5.0

KEY_SECTOR_KEYS = ("steel_aluminum", "autos", "semiconductors", "agriculture")


def _progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s elapsed)")
        last_print[0] = now


def _print_code_row(c):
    hts = _safe_str(c, "htsno")[:18]
    desc = _truncate(_safe_str(c, "description"), 44)
    gen = _truncate(_safe_str(c, "general"), 14)
    spc = _truncate(_safe_str(c, "special"), 14)
    oth = _truncate(_safe_str(c, "other"), 14)
    print(f"  {hts:<18} {desc:<44} {gen:>14} {spc:>14} {oth:>14}")


def cmd_run(as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    print("\n  Tariff rate scan (representative HTS per macro sector)")
    print("  " + "=" * 96)
    print(f"  {'HTS':<18} {'Description':<44} {'General':>14} {'Special':>14} {'Other':>14}")
    print("  " + "-" * 96)

    blocks = []
    idx = 0
    for sk in KEY_SECTOR_KEYS:
        if sk not in MACRO_CHAPTERS:
            continue
        info = MACRO_CHAPTERS[sk]
        label = info["label"]
        codes = info.get("codes") or []
        print(f"\n  [{sk}] {label}")
        for code in codes:
            idx += 1
            _progress(f"duty lookup {idx} ({code})", t0, last)
            print(f"  querying {code} ...", flush=True)
            raw = _fetch_search(code)
            if not raw:
                print(f"    (no results for {code})")
                continue
            pick = raw[0]
            for c in raw:
                h = _safe_str(c, "htsno").replace(" ", "")
                if h.startswith(code.replace(" ", "")):
                    pick = c
                    break
            pick = dict(_flatten_code(pick))
            pick["sector_key"] = sk
            pick["sector_label"] = label
            blocks.append(pick)
            if not as_json:
                _print_code_row(
                    {
                        "htsno": pick["htsno"],
                        "description": pick["description"],
                        "general": pick["general"],
                        "special": pick["special"],
                        "other": pick["other"],
                    }
                )

    payload = {
        "generated_at": datetime.now().isoformat(),
        "sectors": list(KEY_SECTOR_KEYS),
        "codes": blocks,
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    if export_fmt:
        _export(payload, "tariff_rate_checker_run", export_fmt)
    return payload


def cmd_lookup(hts_number, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    _progress("duty lookup", t0, last)
    if as_json:
        codes = _fetch_search(hts_number)
        out = {"hts": hts_number, "matches": [_flatten_code(c) for c in (codes or [])]}
        print(json.dumps(out, indent=2, default=str))
    else:
        cmd_duty(hts_number, as_json=False, export_fmt=None)
        codes = _fetch_search(hts_number)
        out = {"hts": hts_number, "matches": [_flatten_code(c) for c in (codes or [])]}

    elapsed = int(time.time() - t0)
    print(f"  Completed in {elapsed}s")
    if export_fmt:
        _export(out, f"tariff_lookup_{hts_number.replace('.', '')}", export_fmt)
    return out


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = data.get("codes") or data.get("matches") or []
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
   Tariff Rate Checker (USITC HTS)
  ============================================================

   1) run      Scan representative codes for steel, autos, electronics, ag
   2) lookup   Duty detail for one HTS number

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
        elif c in ("2", "lookup"):
            h = _prompt("HTS number")
            if not h:
                continue
            cmd_lookup(h)
        else:
            print(f"  Unknown: {c}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="tariff_rate_checker.py",
        description="HTS duty scan across macro sectors and single-code lookup",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Scan key macro sectors via MACRO_CHAPTERS sample codes")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("lookup", help="Single HTS duty lookup")
    s.add_argument("hts", help="HTS code")
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
    elif args.command == "lookup":
        cmd_lookup(args.hts, as_json=args.json, export_fmt=args.export)


if __name__ == "__main__":
    main()
