#!/usr/bin/env python3
"""
Rates Positioning Analysis
============================
Deep dive into Treasury and SOFR futures positioning from CFTC COT data.
Maps the positioning profile across the yield curve and identifies
crowding, divergence, and directional momentum signals.

Analysis:
  1. Yield curve positioning map: 2Y/5Y/10Y/30Y/Ultra/SOFR net spec
  2. Crowding percentile for each tenor (3-year history)
  3. Leveraged fund vs dealer divergence (contrarian signal)
  4. Weekly change momentum (who is adding/cutting)
  5. Duration tilt: front-end vs back-end positioning

Usage:
    python rates_positioning_analysis.py              # interactive CLI
    python rates_positioning_analysis.py run           # full rates analysis
    python rates_positioning_analysis.py run --json    # JSON for PRISM
    python rates_positioning_analysis.py curve-history # 2Y curve history
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from cftc import (
    _fetch_latest, _fetch_history, _fetch_multi_history,
    _net_spec, _net_comm, _chg_net_spec, _chg_net_comm, _get_oi, _pct_oi,
    _percentile_rank, _crowding_label, _ordinal,
    _safe_int, _fmt_num, _fmt_pct, _prompt, _bar, _filter_contracts,
    CONTRACT_REGISTRY, FIELD_MAP, GROUP_NAMES,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))

RATES_ALIASES = ["UST_2Y", "UST_5Y", "UST_10Y", "UST_30Y", "UST_ULTRA", "SOFR_3M"]
TENOR_ORDER = {a: i for i, a in enumerate(RATES_ALIASES)}


def cmd_run(years=3, as_json=False, export_fmt=None):
    print("\n  RATES POSITIONING ANALYSIS")
    print("  " + "=" * 70)
    t0 = time.time()

    contracts = {a: CONTRACT_REGISTRY[a] for a in RATES_ALIASES}

    print("  [1/2] Fetching latest positioning...")
    latest = _fetch_latest(contracts)
    time.sleep(0.3)

    print(f"  [2/2] Fetching {years}Y history for crowding...")
    history = _fetch_multi_history(contracts, weeks=years * 52)

    if not latest:
        print("  No data returned.")
        return

    records = []
    for alias in RATES_ALIASES:
        if alias not in latest:
            continue
        info = CONTRACT_REGISTRY[alias]
        rtype = info["report"]
        row = latest[alias]

        net = _net_spec(row, rtype)
        chg = _chg_net_spec(row, rtype)
        oi = _get_oi(row, rtype)
        pct = _pct_oi(net, oi)
        net_c = _net_comm(row, rtype)
        chg_c = _chg_net_comm(row, rtype)

        pctile = 50.0
        if alias in history:
            hist_nets = [_net_spec(r, rtype) for r in history[alias]]
            if hist_nets:
                pctile = _percentile_rank(net, hist_nets)

        divergence = ""
        if net > 0 and net_c < 0:
            divergence = "Specs L / Dealers S"
        elif net < 0 and net_c > 0:
            divergence = "Specs S / Dealers L"
        else:
            divergence = "Aligned"

        if chg > 0:
            momentum = "adding long" if net > 0 else "covering"
        elif chg < 0:
            momentum = "adding short" if net < 0 else "cutting"
        else:
            momentum = "flat"

        records.append({
            "alias": alias,
            "name": info["name"],
            "date": row.get("report_date_as_yyyy_mm_dd", "")[:10],
            "net_spec": net,
            "chg_spec": chg,
            "net_dealer": net_c,
            "chg_dealer": chg_c,
            "oi": oi,
            "pct_oi": round(pct, 2),
            "pctile": round(pctile, 1),
            "crowding": _crowding_label(pctile),
            "divergence": divergence,
            "momentum": momentum,
        })

    # Duration tilt
    front_end = [r for r in records if r["alias"] in ("UST_2Y", "UST_5Y", "SOFR_3M")]
    back_end = [r for r in records if r["alias"] in ("UST_10Y", "UST_30Y", "UST_ULTRA")]
    front_avg_pctile = sum(r["pctile"] for r in front_end) / len(front_end) if front_end else 50
    back_avg_pctile = sum(r["pctile"] for r in back_end) / len(back_end) if back_end else 50

    if front_avg_pctile > back_avg_pctile + 15:
        duration_tilt = "FRONT-END LONG (expecting cuts / short-rate decline)"
    elif back_avg_pctile > front_avg_pctile + 15:
        duration_tilt = "BACK-END LONG (expecting steepening / term premium)"
    else:
        duration_tilt = "BALANCED (no strong curve bet)"

    result = {
        "timestamp": datetime.now().isoformat(),
        "history_years": years,
        "duration_tilt": duration_tilt,
        "front_end_avg_pctile": round(front_avg_pctile, 1),
        "back_end_avg_pctile": round(back_avg_pctile, 1),
        "positions": records,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    # Display
    report_date = max(r["date"] for r in records) if records else "unknown"
    print(f"\n  YIELD CURVE POSITIONING MAP (as of {report_date})")
    print("  " + "=" * 95)
    print(f"  {'Tenor':<16} {'Net Spec':>11} {'Chg 1w':>10} {'%OI':>7} {'%ile':>5}  "
          f"{'':20}  {'Signal'}")
    print(f"  {'-'*16} {'-'*11} {'-'*10} {'-'*7} {'-'*5}  {'-'*20}  {'-'*14}")

    for r in records:
        label = r["crowding"] if r["crowding"] else ""
        print(f"  {r['name']:<16} {_fmt_num(r['net_spec']):>11} {_fmt_num(r['chg_spec']):>10} "
              f"{_fmt_pct(r['pct_oi']):>7} {r['pctile']:>4.0f}%  {_bar(r['pctile']):20}  {label}")

    # Divergence
    print(f"\n  SPEC vs DEALER DIVERGENCE")
    print(f"  {'-'*70}")
    print(f"  {'Tenor':<16} {'Spec Net':>11} {'Dealer Net':>11} {'Spec Chg':>10} "
          f"{'Dealer Chg':>10} {'Signal'}")
    print(f"  {'-'*16} {'-'*11} {'-'*11} {'-'*10} {'-'*10} {'-'*20}")
    for r in records:
        print(f"  {r['name']:<16} {_fmt_num(r['net_spec']):>11} {_fmt_num(r['net_dealer']):>11} "
              f"{_fmt_num(r['chg_spec']):>10} {_fmt_num(r['chg_dealer']):>10} {r['divergence']}")

    # Duration tilt
    print(f"\n  DURATION TILT")
    print(f"  {'-'*50}")
    print(f"  Front-end avg %ile: {front_avg_pctile:.0f}  |  Back-end avg %ile: {back_avg_pctile:.0f}")
    print(f"  Assessment: {duration_tilt}")

    # Key signals
    extreme = [r for r in records if r["crowding"]]
    if extreme:
        print(f"\n  KEY SIGNALS")
        print(f"  {'-'*50}")
        for r in extreme:
            print(f"  - {r['name']}: {r['crowding']} ({r['pctile']:.0f}th %ile, "
                  f"{_fmt_num(r['net_spec'])} net spec)")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _export(result, "rates_positioning", export_fmt)
    return result


def cmd_curve_history(weeks=104, as_json=False, export_fmt=None):
    print(f"\n  Fetching {weeks}-week history for rates curve...")
    t0 = time.time()

    contracts = {a: CONTRACT_REGISTRY[a] for a in RATES_ALIASES}
    history = _fetch_multi_history(contracts, weeks=weeks)

    if not history:
        print("  No data returned.")
        return

    if as_json:
        out = {}
        for alias in RATES_ALIASES:
            rows = history.get(alias, [])
            rtype = CONTRACT_REGISTRY[alias]["report"]
            out[alias] = [{"date": r.get("report_date_as_yyyy_mm_dd", "")[:10],
                           "net_spec": _net_spec(r, rtype),
                           "oi": _get_oi(r, rtype)}
                          for r in sorted(rows, key=lambda x: x.get("report_date_as_yyyy_mm_dd", ""),
                                          reverse=True)]
        print(json.dumps(out, indent=2, default=str))
        return out

    for alias in RATES_ALIASES:
        rows = history.get(alias, [])
        if not rows:
            continue
        info = CONTRACT_REGISTRY[alias]
        rtype = info["report"]
        rows = sorted(rows, key=lambda x: x.get("report_date_as_yyyy_mm_dd", ""), reverse=True)

        nets = [_net_spec(r, rtype) for r in rows]
        latest = nets[0] if nets else 0
        pctile = _percentile_rank(latest, nets) if nets else 50

        print(f"\n  {info['name']} -- {len(rows)} weeks  |  "
              f"Current: {_fmt_num(latest)}  |  %ile: {_ordinal(pctile)}")
        print(f"  {'Date':<12} {'Net Spec':>11} {'Chg':>10} {'OI':>12}")
        print(f"  {'-'*12} {'-'*11} {'-'*10} {'-'*12}")

        for r in rows[:26]:
            date = r.get("report_date_as_yyyy_mm_dd", "")[:10]
            net = _net_spec(r, rtype)
            chg = _chg_net_spec(r, rtype)
            oi = _get_oi(r, rtype)
            print(f"  {date:<12} {_fmt_num(net):>11} {_fmt_num(chg):>10} "
                  f"{_fmt_num(oi, sign=False):>12}")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        flat = []
        for alias in RATES_ALIASES:
            rows = history.get(alias, [])
            rtype = CONTRACT_REGISTRY[alias]["report"]
            for r in rows:
                flat.append({"alias": alias, "name": CONTRACT_REGISTRY[alias]["name"],
                             "date": r.get("report_date_as_yyyy_mm_dd", "")[:10],
                             "net_spec": _net_spec(r, rtype), "oi": _get_oi(r, rtype)})
        _export(flat, "rates_curve_history", export_fmt)
    return history


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
   CFTC Rates Positioning Analysis
  =====================================================

   1) run              Full rates positioning map
   2) curve-history    Multi-tenor history

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
            years = _prompt("History years for crowding", "3")
            cmd_run(years=int(years))
        elif choice == "2":
            weeks = _prompt("Weeks of history", "104")
            cmd_curve_history(weeks=int(weeks))
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(prog="rates_positioning_analysis.py",
                                description="CFTC Rates Positioning Analysis")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Full rates positioning map")
    s.add_argument("--years", type=int, default=3)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("curve-history", help="Multi-tenor positioning history")
    s.add_argument("--weeks", type=int, default=104)
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
    elif args.command == "curve-history":
        cmd_curve_history(weeks=args.weeks, as_json=j, export_fmt=exp)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
