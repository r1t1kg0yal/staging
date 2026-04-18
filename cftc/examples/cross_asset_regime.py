#!/usr/bin/env python3
"""
Cross-Asset Positioning Regime Map
===================================
Scans all 25 CFTC COT contracts to classify the current positioning regime,
detect rotation signals, and identify crowding extremes across asset classes.

Analysis:
  1. Full 25-contract positioning scan with 3Y crowding percentiles
  2. Regime classification: risk-on / risk-off / mixed / rotational
  3. Extreme detection: contracts >85th or <15th percentile
  4. Weekly flow momentum: biggest position changes sorted by magnitude
  5. Asset class rotation: compare rates/FX/equity/commodity tilts

Usage:
    python cross_asset_regime.py                  # interactive CLI
    python cross_asset_regime.py run              # full regime scan
    python cross_asset_regime.py run --json       # JSON for PRISM
    python cross_asset_regime.py extremes         # extreme positions only
    python cross_asset_regime.py flows            # weekly flow analysis
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cftc import (
    _fetch_latest, _fetch_multi_history,
    _net_spec, _net_comm, _chg_net_spec, _get_oi, _pct_oi,
    _percentile_rank, _crowding_label, _bar,
    _fmt_num, _fmt_pct, _prompt,
    CONTRACT_REGISTRY, FIELD_MAP, GROUP_ORDER, GROUP_NAMES,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))


def _classify_regime(summaries):
    risk_on_signals = 0
    risk_off_signals = 0

    for s in summaries:
        grp = s["group"]
        pctile = s["pctile"]

        if grp == "equity" and s["alias"] in ("SP500", "NASDAQ"):
            if pctile > 60:
                risk_on_signals += 1
            elif pctile < 40:
                risk_off_signals += 1

        if grp == "equity" and s["alias"] == "VIX":
            if pctile > 60:
                risk_off_signals += 1
            elif pctile < 40:
                risk_on_signals += 1

        if grp in ("energy", "metals", "ags"):
            if pctile > 65:
                risk_on_signals += 1
            elif pctile < 35:
                risk_off_signals += 1

    if risk_on_signals >= 4 and risk_off_signals <= 1:
        return "RISK-ON"
    elif risk_off_signals >= 4 and risk_on_signals <= 1:
        return "RISK-OFF"
    elif risk_on_signals >= 2 and risk_off_signals >= 2:
        return "ROTATIONAL"
    else:
        return "MIXED"


def cmd_run(years=3, as_json=False, export_fmt=None):
    print("\n  CROSS-ASSET POSITIONING REGIME MAP")
    print("  " + "=" * 70)
    t0 = time.time()

    print("  [1/2] Fetching latest positioning (25 contracts)...")
    latest = _fetch_latest(quiet=True)
    time.sleep(0.3)

    print(f"  [2/2] Fetching {years}Y history for crowding...")
    history = _fetch_multi_history(weeks=years * 52)

    if not latest:
        print("  No data returned.")
        return

    summaries = []
    for grp in GROUP_ORDER:
        for alias, info in CONTRACT_REGISTRY.items():
            if info["group"] != grp or alias not in latest:
                continue
            rtype = info["report"]
            row = latest[alias]

            net = _net_spec(row, rtype)
            chg = _chg_net_spec(row, rtype)
            oi = _get_oi(row, rtype)
            pct = _pct_oi(net, oi)
            net_c = _net_comm(row, rtype)

            pctile = 50.0
            if alias in history:
                hist_nets = [_net_spec(r, rtype) for r in history[alias]]
                if hist_nets:
                    pctile = _percentile_rank(net, hist_nets)

            summaries.append({
                "alias": alias, "name": info["name"], "group": grp,
                "date": row.get("report_date_as_yyyy_mm_dd", "")[:10],
                "net_spec": net, "chg_spec": chg, "oi": oi,
                "pct_oi": round(pct, 2), "net_comm": net_c,
                "pctile": round(pctile, 1),
                "crowding": _crowding_label(pctile),
            })

    regime = _classify_regime(summaries)

    # Per-group average percentile
    group_pctiles = {}
    for grp in GROUP_ORDER:
        grp_data = [s for s in summaries if s["group"] == grp]
        if grp_data:
            group_pctiles[grp] = round(sum(s["pctile"] for s in grp_data) / len(grp_data), 1)

    extremes = [s for s in summaries if s["pctile"] >= 85 or s["pctile"] <= 15]

    result = {
        "timestamp": datetime.now().isoformat(),
        "regime": regime,
        "history_years": years,
        "group_avg_pctiles": group_pctiles,
        "extremes": extremes,
        "positions": summaries,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    # Table by group
    report_date = max(s["date"] for s in summaries) if summaries else "unknown"
    print(f"\n  As of: {report_date}  |  REGIME: {regime}")

    current_grp = None
    for s in summaries:
        if s["group"] != current_grp:
            current_grp = s["group"]
            print(f"\n  {GROUP_NAMES.get(current_grp, current_grp)}"
                  f"  [avg %ile: {group_pctiles.get(current_grp, 50):.0f}]")
            print(f"  {'Contract':<18} {'Net Spec':>11} {'Chg 1w':>10} {'%OI':>7} "
                  f"{'%ile':>5}  {'':20}  {'Signal'}")
            print(f"  {'-'*18} {'-'*11} {'-'*10} {'-'*7} {'-'*5}  {'-'*20}  {'-'*14}")

        label = s["crowding"] if s["crowding"] else ""
        print(f"  {s['name']:<18} {_fmt_num(s['net_spec']):>11} {_fmt_num(s['chg_spec']):>10} "
              f"{_fmt_pct(s['pct_oi']):>7} {s['pctile']:>4.0f}%  {_bar(s['pctile']):20}  {label}")

    # Extremes
    if extremes:
        print(f"\n  POSITIONING EXTREMES ({len(extremes)} contracts)")
        print(f"  {'-'*50}")
        shorts = [s for s in extremes if s["pctile"] <= 15]
        longs = [s for s in extremes if s["pctile"] >= 85]
        if shorts:
            print(f"  Crowded Shorts (squeeze risk):")
            for s in sorted(shorts, key=lambda x: x["pctile"]):
                print(f"    {s['name']}: {s['pctile']:.0f}th %ile ({_fmt_num(s['net_spec'])} net)")
        if longs:
            print(f"  Crowded Longs (unwind risk):")
            for s in sorted(longs, key=lambda x: -x["pctile"]):
                print(f"    {s['name']}: {s['pctile']:.0f}th %ile ({_fmt_num(s['net_spec'])} net)")

    # Group comparison
    print(f"\n  ASSET CLASS POSITIONING TILT")
    print(f"  {'-'*50}")
    for grp in GROUP_ORDER:
        pct = group_pctiles.get(grp, 50)
        bar_str = _bar(pct, width=30)
        label = GROUP_NAMES.get(grp, grp)
        print(f"  {label:<15} {pct:>4.0f}%  {bar_str}")

    print(f"\n  REGIME: {regime}")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _export(result, "cross_asset_regime", export_fmt)
    return result


def cmd_extremes(threshold=15, years=3, as_json=False, export_fmt=None):
    print(f"\n  Scanning for positioning extremes (threshold: {threshold}th / {100-threshold}th %ile)...")
    t0 = time.time()

    latest = _fetch_latest(quiet=True)
    time.sleep(0.3)
    history = _fetch_multi_history(weeks=years * 52)

    if not latest:
        print("  No data returned.")
        return

    extremes = []
    for alias, info in CONTRACT_REGISTRY.items():
        if alias not in latest:
            continue
        rtype = info["report"]
        row = latest[alias]
        net = _net_spec(row, rtype)
        chg = _chg_net_spec(row, rtype)

        pctile = 50.0
        if alias in history:
            hist_nets = [_net_spec(r, rtype) for r in history[alias]]
            if hist_nets:
                pctile = _percentile_rank(net, hist_nets)

        if pctile <= threshold or pctile >= (100 - threshold):
            extremes.append({
                "alias": alias, "name": info["name"], "group": info["group"],
                "net_spec": net, "chg_spec": chg,
                "pctile": round(pctile, 1),
                "crowding": _crowding_label(pctile),
            })

    extremes.sort(key=lambda x: x["pctile"])

    if as_json:
        print(json.dumps(extremes, indent=2, default=str))
        return extremes

    if not extremes:
        print(f"  No contracts at extremes.")
        return

    print(f"\n  POSITIONING EXTREMES ({len(extremes)} contracts, {years}Y history)")
    print("  " + "=" * 70)
    print(f"  {'Contract':<18} {'Group':<10} {'Net Spec':>11} {'Chg':>10} "
          f"{'%ile':>5}  {'':20}  {'Signal'}")
    print(f"  {'-'*18} {'-'*10} {'-'*11} {'-'*10} {'-'*5}  {'-'*20}  {'-'*14}")

    for e in extremes:
        print(f"  {e['name']:<18} {e['group']:<10} {_fmt_num(e['net_spec']):>11} "
              f"{_fmt_num(e['chg_spec']):>10} {e['pctile']:>4.0f}%  "
              f"{_bar(e['pctile']):20}  {e['crowding']}")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _export(extremes, "extremes", export_fmt)
    return extremes


def cmd_flows(as_json=False, export_fmt=None):
    print("\n  WEEKLY POSITION FLOW ANALYSIS")
    print("  " + "=" * 70)

    latest = _fetch_latest(quiet=True)
    if not latest:
        print("  No data returned.")
        return

    records = []
    for alias, info in CONTRACT_REGISTRY.items():
        if alias not in latest:
            continue
        rtype = info["report"]
        row = latest[alias]
        chg = _chg_net_spec(row, rtype)
        net = _net_spec(row, rtype)

        if chg > 0:
            direction = "adding long" if net > 0 else "covering"
        elif chg < 0:
            direction = "adding short" if net < 0 else "cutting"
        else:
            direction = "flat"

        records.append({
            "alias": alias, "name": info["name"], "group": info["group"],
            "net_spec": net, "chg_spec": chg, "abs_chg": abs(chg),
            "direction": direction,
        })

    records.sort(key=lambda x: x["abs_chg"], reverse=True)

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  Sorted by magnitude of weekly change:")
    print(f"  {'Contract':<18} {'Group':<10} {'Chg 1w':>10} {'Net Spec':>11} {'Direction'}")
    print(f"  {'-'*18} {'-'*10} {'-'*10} {'-'*11} {'-'*16}")
    for r in records:
        print(f"  {r['name']:<18} {r['group']:<10} {_fmt_num(r['chg_spec']):>10} "
              f"{_fmt_num(r['net_spec']):>11} {r['direction']}")

    print()
    return records


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data",
                        f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        import csv
        rows = data if isinstance(data, list) else data.get("positions", [data])
        if rows and isinstance(rows[0], dict):
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
    print(f"  Exported: {path}")


MENU = """
  =====================================================
   CFTC Cross-Asset Positioning Regime Map
  =====================================================

   1) run             Full 25-contract regime scan
   2) extremes        Positioning extremes only
   3) flows           Weekly flow analysis

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
        elif choice == "1":
            years = _prompt("History years", "3")
            cmd_run(years=int(years))
        elif choice == "2":
            threshold = _prompt("Percentile threshold", "15")
            cmd_extremes(threshold=int(threshold))
        elif choice == "3":
            cmd_flows()
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(prog="cross_asset_regime.py",
                                description="CFTC Cross-Asset Positioning Regime Map")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Full regime scan")
    s.add_argument("--years", type=int, default=3)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("extremes", help="Positioning extremes")
    s.add_argument("--threshold", type=int, default=15)
    s.add_argument("--years", type=int, default=3)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("flows", help="Weekly flow analysis")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "run":
        cmd_run(years=args.years, as_json=j, export_fmt=exp)
    elif args.command == "extremes":
        cmd_extremes(threshold=args.threshold, years=args.years, as_json=j, export_fmt=exp)
    elif args.command == "flows":
        cmd_flows(as_json=j, export_fmt=exp)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
