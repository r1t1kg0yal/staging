#!/usr/bin/env python3
"""
Geopolitical OFAC Sanctions Monitor
===================================
Macro-program buckets (Russia, Iran, China, etc.), entity counts per bucket,
and geographic distribution of sanctioned entities tied to address countries.

Usage:
    python geopolitical_sanctions_monitor.py
    python geopolitical_sanctions_monitor.py run
    python geopolitical_sanctions_monitor.py run --json
    python geopolitical_sanctions_monitor.py country Russia --export json
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
    MACRO_PROGRAMS,
    _filter_by_country,
    _get_addresses,
    _get_entities,
    _split_programs,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
PROGRESS_EVERY_S = 5.0


def _print_progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s elapsed)")
        last_print[0] = now


def _macro_entity_counts(entities, t0, last):
    out = {}
    for key, group in MACRO_PROGRAMS.items():
        _print_progress(f"macro scan:{key}", t0, last)
        progs = set(group["programs"])
        cnt = 0
        for e in entities:
            ent_progs = set(_split_programs(e.get("Program", "")))
            if progs.intersection(ent_progs):
                cnt += 1
        out[key] = {
            "label": group["label"],
            "entity_count": cnt,
            "programs": sorted(progs),
        }
    return out


def _geo_distribution(addresses, t0, last):
    country_counts = Counter()
    for ent_num, addr_list in addresses.items():
        _print_progress("address geography", t0, last)
        seen = set()
        for addr in addr_list:
            c = (addr.get("Country") or "").strip()
            if c and c not in seen:
                country_counts[c] += 1
                seen.add(c)
    return country_counts.most_common(40)


def cmd_run(as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    print("\n  Building macro-program and geography panels...")
    entities = _get_entities()
    addresses = _get_addresses()
    _print_progress("entities loaded", t0, last)
    macro = _macro_entity_counts(entities, t0, last)
    geo = _geo_distribution(addresses, t0, last)
    payload = {
        "macro_programs": macro,
        "geographic_top40": [{"country": c, "entities": n} for c, n in geo],
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"\n  MACRO PROGRAM ENTITY COUNTS")
        print("  " + "=" * 70)
        print(f"  {'Bucket':<22} {'Entities':>10}  Label")
        print(f"  {'-'*22} {'-'*10}  {'-'*30}")
        for key in MACRO_PROGRAMS:
            r = macro[key]
            print(f"  {key:<22} {r['entity_count']:>10,}  {r['label']}")
        print(f"\n  GEOGRAPHIC DISTRIBUTION (entities with at least one address; top 25)")
        print(f"  {'-'*35} {'-'*10}")
        for c, n in geo[:25]:
            print(f"  {c:<35} {n:>10,}")

    print(f"\n  Completed in {int(time.time() - t0)}s\n")
    if export_fmt:
        _export(payload, "ofac_geopolitical_monitor_run", export_fmt)


def cmd_country(country=None, as_json=False, export_fmt=None):
    if not country:
        print("  [country requires a name]")
        return
    t0 = time.time()
    last = [t0]
    print(f"\n  Country focus: {country} ...")
    matches = _filter_by_country(country)
    _print_progress("country filter done", t0, last)
    macro_hits = Counter()
    for e in matches:
        for p in _split_programs(e.get("Program", "")):
            macro_hits[p] += 1
    top_progs = macro_hits.most_common(15)
    payload = {
        "country": country,
        "entity_count": len(matches),
        "top_programs": [{"program": p, "count": c} for p, c in top_progs],
        "entities": matches,
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"\n  ENTITIES: {len(matches)}")
        print(f"  TOP PROGRAMS WITHIN {country}")
        for p, c in top_progs:
            print(f"    {p:<35} {c:>6,}")

    print(f"\n  Completed in {int(time.time() - t0)}s\n")
    if export_fmt:
        _export(payload, "ofac_geopolitical_monitor_country", export_fmt)


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
            if isinstance(data.get("entities"), list) and data["entities"]:
                rows = data["entities"]
            elif isinstance(data.get("geographic_top40"), list):
                rows = data["geographic_top40"]
            elif isinstance(data.get("macro_programs"), dict):
                rows = []
                for k, v in data["macro_programs"].items():
                    rows.append({"bucket": k, "label": v.get("label"), "entity_count": v.get("entity_count")})
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
   Geopolitical OFAC Sanctions Monitor
  ============================================================

   1) run            Macro-program counts + geographic distribution
   2) country        Single-country program mix

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
        elif choice in ("2", "country"):
            c = input("  Country: ").strip()
            cmd_country(country=c)
        else:
            print(f"  Unknown: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="geopolitical_sanctions_monitor.py",
        description="OFAC macro-program and geography monitor",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Macro-program breakdown + geography")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("country", help="Single-country focus")
    s.add_argument("country", help="Country substring (address match)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(as_json=args.json, export_fmt=args.export)
    elif args.command == "country":
        cmd_country(country=args.country, as_json=args.json, export_fmt=args.export)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
