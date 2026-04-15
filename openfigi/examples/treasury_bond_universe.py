#!/usr/bin/env python3
"""
Treasury Bond Universe (OpenFIGI)
==================================
Enumerate Treasury instruments via OpenFIGI mapping, resolve to FIGIs, and
bucket by security style (bill, note, bond, TIPS, FRN). Corporate issuer bond
stacks are available under issuer-bonds.

Usage:
    python treasury_bond_universe.py
    python treasury_bond_universe.py run --maturity 2025-2028
    python treasury_bond_universe.py issuer-bonds JPM --json
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from openfigi import api_map, cmd_issuer_bonds, _parse_bond_ticker

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
PROGRESS_EVERY_S = 5.0


def _print_progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s elapsed)")
        last_print[0] = now


def _fetch_ust_range(mat_start, mat_end, instrument_type, t0, last):
    start_y = int(mat_start[:4])
    end_y = int(mat_end[:4])
    type_map = {
        "notes": [("T", "Note")],
        "bonds": [("T", "Bond")],
        "bills": [("T", "Bill")],
        "all": [("T", "Note"), ("T", "Bond")],
    }
    queries = type_map.get(instrument_type, type_map["all"])
    all_bonds = []
    for base_ticker, sec_type2 in queries:
        for y in range(start_y, end_y + 1):
            _print_progress(f"{sec_type2} {y}", t0, last)
            cs, ce = f"{y}-01-01", f"{y}-12-31"
            job = {
                "idType": "BASE_TICKER",
                "idValue": base_ticker,
                "securityType2": sec_type2,
                "marketSecDes": "Govt",
                "maturity": [cs, ce],
            }
            result = api_map([job])
            if result and len(result) > 0 and "data" in result[0]:
                for b in result[0]["data"]:
                    b["_parsed"] = _parse_bond_ticker(b.get("ticker"))
                    b["_ust_type"] = sec_type2
                all_bonds.extend(result[0]["data"])
    seen = set()
    deduped = []
    for b in all_bonds:
        figi = b.get("figi")
        if figi and figi not in seen:
            seen.add(figi)
            deduped.append(b)
    deduped.sort(key=lambda x: x.get("_parsed", {}).get("maturity") or "9999")
    return deduped


def _classify_ust(inst):
    name = (inst.get("name") or "").upper()
    ticker = (inst.get("ticker") or "").upper()
    st = (inst.get("securityType") or "").upper()
    st2 = (inst.get("securityType2") or "").upper()
    ust = (inst.get("_ust_type") or inst.get("type") or st2 or "").upper()
    if "TIPS" in name or "TIPS" in ticker or "INFLATION" in name or "TIPS" in st:
        return "TIPS"
    if "FRN" in name or "FRN" in ticker or "FLOATING RATE" in name or "FLOAT" in st:
        return "FRN"
    if ust == "BILL" or "BILL" in st or "TBILL" in ticker:
        return "bill"
    if ust == "NOTE" or "NOTE" in st:
        return "note"
    if ust == "BOND" or "BOND" in st:
        return "bond"
    if ust:
        return ust.lower()
    return "other"


def cmd_run(maturity=None, include_bills=True, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    y0 = datetime.now().year
    mat_start, mat_end = f"{y0}-01-01", f"{y0 + 10}-12-31"
    if maturity and "-" in maturity:
        parts = maturity.split("-", 1)
        y_a = int(parts[0].strip())
        y_b = int(parts[1].strip())
        mat_start, mat_end = f"{y_a}-01-01", f"{y_b}-12-31"
    print(f"\n  Treasury universe scan {mat_start} .. {mat_end} (include_bills={include_bills})")
    merged = _fetch_ust_range(mat_start, mat_end, "all", t0, last)
    seen = {b.get("figi") for b in merged if b.get("figi")}
    if include_bills:
        bills = _fetch_ust_range(mat_start, mat_end, "bills", t0, last)
        for row in bills:
            figi = row.get("figi")
            if figi and figi not in seen:
                seen.add(figi)
                merged.append(row)
    merged.sort(key=lambda x: x.get("_parsed", {}).get("maturity") or "9999")
    buckets = Counter(_classify_ust(b) for b in merged)
    payload = {
        "maturity_start": mat_start,
        "maturity_end": mat_end,
        "instrument_count": len(merged),
        "by_bucket": dict(buckets.most_common()),
        "instruments": merged,
    }
    if as_json:
        slim = []
        for b in merged:
            p = b.get("_parsed") or {}
            slim.append({
                "ticker": b.get("ticker"),
                "figi": b.get("figi"),
                "name": b.get("name"),
                "type": b.get("_ust_type"),
                "bucket": _classify_ust(b),
                "coupon": p.get("coupon"),
                "maturity": p.get("maturity"),
            })
        out = {"summary": {k: payload[k] for k in ("maturity_start", "maturity_end", "instrument_count", "by_bucket")}, "instruments": slim}
        print(json.dumps(out, indent=2, default=str))
    else:
        print(f"\n  SECURITY-TYPE BUCKETS")
        print("  " + "-" * 40)
        for k, v in buckets.most_common():
            print(f"  {k:<20} {v:>8,}")
        print(f"\n  SAMPLE (first 15)")
        print(f"  {'-'*88}")
        for b in merged[:15]:
            p = b.get("_parsed") or {}
            print(
                f"  {(b.get('ticker') or '')[:24]:<24} "
                f"{_classify_ust(b):<8} "
                f"{(p.get('maturity') or ''):<12} "
                f"{(b.get('figi') or '')}"
            )

    print(f"\n  Completed in {int(time.time() - t0)}s\n")
    if export_fmt:
        _export(payload, "openfigi_treasury_universe_run", export_fmt)


def cmd_issuer_bonds_cmd(ticker, maturity=None, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    mat_start, mat_end = None, None
    if maturity and "-" in maturity:
        parts = maturity.split("-", 1)
        mat_start = f"{parts[0].strip()}-01-01"
        mat_end = f"{parts[1].strip()}-12-31"
    print(f"\n  Issuer bonds: {ticker} ...")
    _print_progress("issuer bonds fetch", t0, last)
    bonds = cmd_issuer_bonds(
        ticker,
        maturity_start=mat_start,
        maturity_end=mat_end,
        as_json=as_json,
        export_fmt=None,
    )
    _print_progress("issuer bonds done", t0, last)
    if export_fmt and bonds is not None:
        rows = []
        for b in bonds or []:
            if not isinstance(b, dict):
                continue
            row = {k: v for k, v in b.items() if k != "_parsed"}
            rows.append(row)
        _export({"ticker": ticker, "bonds": rows}, "openfigi_treasury_universe_issuer", export_fmt)
    print(f"\n  Completed in {int(time.time() - t0)}s\n")


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = None
        if isinstance(data, dict):
            if isinstance(data.get("instruments"), list) and data["instruments"]:
                rows = data["instruments"]
            elif isinstance(data.get("bonds"), list):
                rows = data["bonds"]
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
   Treasury Bond Universe (OpenFIGI)
  ============================================================

   1) run            Treasury universe + security-type buckets
   2) issuer-bonds   Corporate issuer bond stack (BASE_TICKER)

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
            mat = input("  Maturity range YYYY-YYYY [blank = default]: ").strip()
            bills = input("  Include bills? (y/n) [y]: ").strip().lower() != "n"
            cmd_run(maturity=mat or None, include_bills=bills)
        elif choice in ("2", "issuer-bonds", "issuer"):
            t = input("  Issuer ticker: ").strip().upper()
            mat = input("  Optional maturity YYYY-YYYY: ").strip()
            if t:
                cmd_issuer_bonds_cmd(t, maturity=mat or None)
        else:
            print(f"  Unknown: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="treasury_bond_universe.py",
        description="Treasury universe mapping and issuer bond stacks via OpenFIGI",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Treasury universe scan + buckets")
    s.add_argument("--maturity", help="Maturity range YYYY-YYYY (default: this year +10)")
    s.add_argument("--no-bills", action="store_true", help="Skip bill fetch pass")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("issuer-bonds", help="Corporate issuer bond lookup")
    s.add_argument("ticker", help="Issuer ticker (e.g. JPM, INTC)")
    s.add_argument("--maturity", help="Optional maturity range YYYY-YYYY")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(
            maturity=getattr(args, "maturity", None),
            include_bills=not args.no_bills,
            as_json=args.json,
            export_fmt=args.export,
        )
    elif args.command == "issuer-bonds":
        cmd_issuer_bonds_cmd(
            args.ticker,
            maturity=getattr(args, "maturity", None),
            as_json=args.json,
            export_fmt=args.export,
        )
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
