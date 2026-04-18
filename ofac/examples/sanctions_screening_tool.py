#!/usr/bin/env python3
"""
OFAC Sanctions Screening Tool
==============================
Search the SDN list by name, country, or program; show entity details; and
summarize country-level exposure alongside aggregate SDN statistics.

Usage:
    python sanctions_screening_tool.py
    python sanctions_screening_tool.py run
    python sanctions_screening_tool.py run --json
    python sanctions_screening_tool.py search "bank" --export json
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
from ofac import (
    _filter_by_country,
    _filter_by_program,
    _get_addresses,
    _get_entities,
    _search_entities,
    _split_programs,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
PROGRESS_EVERY_S = 5.0


def _print_progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s elapsed)")
        last_print[0] = now


def _compute_stats():
    entities = _get_entities()
    addresses = _get_addresses()
    type_counts = Counter()
    program_counts = Counter()
    for e in entities:
        t = (e.get("SDN_Type") or "").strip()
        type_counts[t or "(unspecified)"] += 1
        for p in _split_programs(e.get("Program", "")):
            program_counts[p] += 1
    country_counts = Counter()
    for ent_num, addr_list in addresses.items():
        seen = set()
        for addr in addr_list:
            c = (addr.get("Country") or "").strip()
            if c and c not in seen:
                country_counts[c] += 1
                seen.add(c)
    return {
        "total_entities": len(entities),
        "by_type": dict(type_counts.most_common()),
        "top_programs": program_counts.most_common(25),
        "top_countries": country_counts.most_common(50),
        "unique_programs": len(program_counts),
        "unique_countries": len(country_counts),
    }


def _print_entity_block(entities, title, limit=40):
    print(f"\n  {title}")
    print("  " + "=" * 88)
    print(f"  {'Ent':>8}  {'Type':<12}  {'Program':<28}  {'Name':<30}")
    print(f"  {'-'*8}  {'-'*12}  {'-'*28}  {'-'*30}")
    for e in entities[:limit]:
        ent = e.get("ent_num", "")
        st = (e.get("SDN_Type") or "")[:12]
        progs = ", ".join(_split_programs(e.get("Program", "")))[:28]
        name = (e.get("SDN_Name") or "")[:30]
        print(f"  {ent!s:>8}  {st:<12}  {progs:<28}  {name:<30}")
    if len(entities) > limit:
        print(f"  ... ({len(entities) - limit} more not shown)")
    for e in entities[: min(5, len(entities))]:
        rem = (e.get("Remarks") or "").strip()
        if rem:
            print(f"    remarks ent {e.get('ent_num')}: {rem[:200]}")


def _screen_by_mode(mode, query):
    mode = (mode or "").lower().strip()
    q = (query or "").strip()
    if not q:
        return [], "empty"
    if mode.startswith("c"):
        return _filter_by_country(q), f"country:{q}"
    if mode.startswith("p"):
        return _filter_by_program(q), f"program:{q}"
    return _search_entities(q), f"name:{q}"


def cmd_run(as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    print("\n  Loading SDN and address files (first run may download)...")
    _print_progress("SDN load", t0, last)
    stats = _compute_stats()
    _print_progress("stats computed", t0, last)
    countries = [{"country": c, "entities": n} for c, n in stats["top_countries"]]
    out = {"stats": stats, "country_exposure_top50": countries}

    if as_json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(f"\n  SDN SUMMARY")
        print("  " + "-" * 56)
        print(f"  Total entities:     {stats['total_entities']:,}")
        print(f"  Unique programs:    {stats['unique_programs']:,}")
        print(f"  Unique countries:   {stats['unique_countries']:,}")
        print(f"\n  TOP PROGRAMS (entity-designation count)")
        print(f"  {'-'*40} {'-'*10}")
        for p, c in stats["top_programs"][:12]:
            print(f"  {p:<40} {c:>10,}")
        print(f"\n  COUNTRY EXPOSURE (entities with address in country, top 25)")
        print(f"  {'-'*35} {'-'*10}")
        for c, n in stats["top_countries"][:25]:
            print(f"  {c:<35} {n:>10,}")

    print(f"\n  Completed in {int(time.time() - t0)}s\n")
    if export_fmt:
        _export(out, "ofac_sanctions_screening_run", export_fmt)


def cmd_search(term=None, mode="name", as_json=False, export_fmt=None):
    if not term:
        print("  [search requires a term]")
        return
    t0 = time.time()
    last = [t0]
    print(f"\n  Screening (mode={mode})...")
    matches, label = _screen_by_mode(mode, term)
    _print_progress(f"screen {label}", t0, last)
    rows = []
    for e in matches:
        rows.append({
            "ent_num": e.get("ent_num"),
            "SDN_Name": e.get("SDN_Name"),
            "SDN_Type": e.get("SDN_Type"),
            "Program": e.get("Program"),
            "Title": e.get("Title"),
            "Remarks": e.get("Remarks"),
        })
    payload = {"mode": mode, "query": term, "count": len(matches), "entities": rows}

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        _print_entity_block(matches, f"MATCHES ({len(matches)}) {label}", limit=50)

    print(f"\n  Completed in {int(time.time() - t0)}s\n")
    if export_fmt:
        _export(payload, "ofac_sanctions_screening_search", export_fmt)


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("entities", "country_exposure_top50"):
                if isinstance(data.get(key), list) and data[key] and isinstance(data[key][0], dict):
                    rows = data[key]
                    break
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
   OFAC Sanctions Screening Tool
  ============================================================

   1) run            Full SDN stats + country exposure (top 50)
   2) search         Screen by name / country / program

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
        elif choice in ("2", "search"):
            mode = input("  Mode (name/country/program) [name]: ").strip().lower() or "name"
            term = input("  Query: ").strip()
            cmd_search(term=term, mode=mode)
        else:
            print(f"  Unknown: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="sanctions_screening_tool.py",
        description="OFAC SDN screening: stats, country exposure, and search",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Full stats + country exposure summary")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("search", help="Search / filter SDN by name, country, or program")
    s.add_argument("term", help="Query string")
    s.add_argument(
        "--mode",
        choices=["name", "country", "program"],
        default="name",
        help="Match mode",
    )
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(as_json=args.json, export_fmt=args.export)
    elif args.command == "search":
        cmd_search(term=args.term, mode=args.mode, as_json=args.json, export_fmt=args.export)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
