#!/usr/bin/env python3
"""
QT & Fed Balance Sheet Analysis
================================
Tracks SOMA runoff pace, composition shifts, and primary dealer positioning
to assess the Fed's balance sheet normalization trajectory.

Analysis:
  1. SOMA composition: Treasuries (notes+bonds, bills, TIPS), MBS, agencies
  2. Weekly runoff pace vs reinvestment caps ($25B/mo Tsy, $35B/mo MBS)
  3. Annualized runoff rate and projection to terminal balance sheet
  4. Primary dealer positioning overlay (inventory absorption)
  5. Bill/coupon composition shift tracking

Usage:
    python qt_balance_sheet_analysis.py              # interactive CLI
    python qt_balance_sheet_analysis.py run           # full QT analysis
    python qt_balance_sheet_analysis.py run --json    # JSON for PRISM
    python qt_balance_sheet_analysis.py composition   # SOMA composition deep dive
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nyfed import (
    _fetch_soma_summary, _fetch_pd_series, _safe_float, _parse_date,
    _fmt_billions, _str_to_billions, _prompt, PD_KEY_SERIES, QT_CAPS,
    REQUEST_DELAY,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))


def cmd_run(weeks=52, as_json=False, export_fmt=None):
    print(f"\n  QT & FED BALANCE SHEET ANALYSIS")
    print("  " + "=" * 70)
    t0 = time.time()

    print("  [1/2] Fetching SOMA holdings history...")
    summaries = _fetch_soma_summary()
    time.sleep(REQUEST_DELAY)

    print("  [2/2] Fetching primary dealer Treasury positions...")
    pd_tsy = _fetch_pd_series("PDPOSGST-TOT")

    if not summaries:
        print("  No SOMA data returned.")
        return

    recent = sorted(summaries, key=lambda x: x.get("asOfDate", ""), reverse=True)[:weeks]

    if len(recent) < 2:
        print("  Not enough data for QT analysis.")
        return

    weekly_changes = []
    for i in range(len(recent) - 1):
        curr = recent[i]
        prev = recent[i + 1]
        date = _parse_date(curr.get("asOfDate", ""))

        tot_c = _str_to_billions(curr.get("total", "0"))
        tot_p = _str_to_billions(prev.get("total", "0"))
        nb_c = _str_to_billions(curr.get("notesbonds", "0"))
        nb_p = _str_to_billions(prev.get("notesbonds", "0"))
        bills_c = _str_to_billions(curr.get("bills", "0"))
        bills_p = _str_to_billions(prev.get("bills", "0"))
        tips_c = _str_to_billions(curr.get("tips", "0"))
        tips_p = _str_to_billions(prev.get("tips", "0"))
        mbs_c = _str_to_billions(curr.get("mbs", "0"))
        mbs_p = _str_to_billions(prev.get("mbs", "0"))

        weekly_changes.append({
            "date": date,
            "total_bn": round(tot_c, 1),
            "chg_total": round(tot_c - tot_p, 2),
            "chg_notesbonds": round(nb_c - nb_p, 2),
            "chg_bills": round(bills_c - bills_p, 2),
            "chg_tips": round(tips_c - tips_p, 2),
            "chg_mbs": round(mbs_c - mbs_p, 2),
            "chg_tsy_total": round((nb_c - nb_p) + (bills_c - bills_p) + (tips_c - tips_p), 2),
        })

    n = len(weekly_changes)
    avg_total = sum(w["chg_total"] for w in weekly_changes) / n
    avg_tsy = sum(w["chg_tsy_total"] for w in weekly_changes) / n
    avg_mbs = sum(w["chg_mbs"] for w in weekly_changes) / n

    monthly_tsy = avg_tsy * (52 / 12)
    monthly_mbs = avg_mbs * (52 / 12)
    ann_total = avg_total * 52

    tsy_cap_util = abs(monthly_tsy) / QT_CAPS["treasury"] * 100 if QT_CAPS["treasury"] > 0 else 0
    mbs_cap_util = abs(monthly_mbs) / QT_CAPS["mbs"] * 100 if QT_CAPS["mbs"] > 0 else 0

    latest_soma = recent[0]
    latest_total = _str_to_billions(latest_soma.get("total", "0"))

    if ann_total < 0:
        years_to_target = (latest_total - 6000) / abs(ann_total)
    else:
        years_to_target = None

    latest_comp = {
        "date": _parse_date(latest_soma.get("asOfDate", "")),
        "total_bn": round(latest_total, 1),
        "notesbonds_bn": round(_str_to_billions(latest_soma.get("notesbonds", "0")), 1),
        "bills_bn": round(_str_to_billions(latest_soma.get("bills", "0")), 1),
        "tips_bn": round(_str_to_billions(latest_soma.get("tips", "0")), 1),
        "mbs_bn": round(_str_to_billions(latest_soma.get("mbs", "0")), 1),
        "agencies_bn": round(_str_to_billions(latest_soma.get("agencies", "0")), 1),
    }

    pd_data = None
    if pd_tsy:
        pd_sorted = sorted(pd_tsy, key=lambda x: x.get("asofdate", ""), reverse=True)[:12]
        pd_data = [{"date": _parse_date(r.get("asofdate", "")),
                     "value_millions": _safe_float(r.get("value"))}
                    for r in pd_sorted]

    result = {
        "timestamp": datetime.now().isoformat(),
        "soma_latest": latest_comp,
        "runoff_pace": {
            "avg_weekly_total_bn": round(avg_total, 2),
            "avg_weekly_tsy_bn": round(avg_tsy, 2),
            "avg_weekly_mbs_bn": round(avg_mbs, 2),
            "monthly_tsy_bn": round(monthly_tsy, 1),
            "monthly_mbs_bn": round(monthly_mbs, 1),
            "annualized_total_bn": round(ann_total, 0),
            "tsy_cap_utilization_pct": round(tsy_cap_util, 1),
            "mbs_cap_utilization_pct": round(mbs_cap_util, 1),
        },
        "caps": {"treasury_monthly_bn": QT_CAPS["treasury"],
                 "mbs_monthly_bn": QT_CAPS["mbs"]},
        "projection": {
            "years_to_6T_target": round(years_to_target, 1) if years_to_target else None,
        },
        "weekly_detail": weekly_changes[:12],
        "pd_treasury_positions": pd_data,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    # SOMA snapshot
    print(f"\n  SOMA HOLDINGS (as of {latest_comp['date']})")
    print(f"  {'-'*50}")
    print(f"  Total:          {_fmt_billions(latest_comp['total_bn'])}")
    print(f"  Notes & Bonds:  {_fmt_billions(latest_comp['notesbonds_bn'])}")
    print(f"  Bills:          {_fmt_billions(latest_comp['bills_bn'])}")
    print(f"  TIPS:           {_fmt_billions(latest_comp['tips_bn'])}")
    print(f"  MBS:            {_fmt_billions(latest_comp['mbs_bn'])}")
    print(f"  Agencies:       {_fmt_billions(latest_comp['agencies_bn'])}")

    # Runoff pace
    print(f"\n  RUNOFF PACE ({n}-week average)")
    print(f"  {'-'*55}")
    print(f"  {'':22} {'Weekly':>10} {'Monthly':>10} {'Annual':>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'Total':22} {_fmt_billions(avg_total):>10} "
          f"{_fmt_billions(avg_total * 52/12):>10} {_fmt_billions(ann_total):>10}")
    print(f"  {'Treasuries':22} {_fmt_billions(avg_tsy):>10} "
          f"{_fmt_billions(monthly_tsy):>10} {_fmt_billions(avg_tsy * 52):>10}")
    print(f"  {'MBS':22} {_fmt_billions(avg_mbs):>10} "
          f"{_fmt_billions(monthly_mbs):>10} {_fmt_billions(avg_mbs * 52):>10}")

    # Cap comparison
    print(f"\n  CAP UTILIZATION")
    print(f"  {'-'*55}")
    print(f"  Treasuries: {abs(monthly_tsy):.1f}B/mo vs {QT_CAPS['treasury']:.0f}B cap "
          f"({tsy_cap_util:.0f}% utilized)")
    print(f"  MBS:        {abs(monthly_mbs):.1f}B/mo vs {QT_CAPS['mbs']:.0f}B cap "
          f"({mbs_cap_util:.0f}% utilized)")

    # Weekly detail
    print(f"\n  RECENT WEEKLY CHANGES")
    print(f"  {'-'*70}")
    print(f"  {'Date':<12} {'Total':>10} {'Tsy':>10} {'NB':>10} {'Bills':>10} {'MBS':>10}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for w in weekly_changes[:12]:
        print(f"  {w['date']:<12} {w['chg_total']:>+10.1f} {w['chg_tsy_total']:>+10.1f} "
              f"{w['chg_notesbonds']:>+10.1f} {w['chg_bills']:>+10.1f} {w['chg_mbs']:>+10.1f}")

    # PD positioning
    if pd_data:
        print(f"\n  PRIMARY DEALER TREASURY POSITIONS ($M)")
        print(f"  {'-'*35}")
        for p in pd_data[:6]:
            print(f"  {p['date']:<12} {p['value_millions']:>12,.0f}")

    # Projection
    if years_to_target and years_to_target > 0:
        print(f"\n  PROJECTION")
        print(f"  {'-'*50}")
        print(f"  At current pace ({ann_total:+.0f}B/yr), ~{years_to_target:.1f} years to reach ~$6T")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _export(result, "qt_analysis", export_fmt)
    return result


def cmd_composition(weeks=104, as_json=False, export_fmt=None):
    print(f"\n  Fetching SOMA composition history ({weeks} weeks)...")
    summaries = _fetch_soma_summary()

    if not summaries:
        print("  No data returned.")
        return

    recent = sorted(summaries, key=lambda x: x.get("asOfDate", ""), reverse=True)[:weeks]

    records = []
    for s in recent:
        total = _str_to_billions(s.get("total", "0"))
        nb = _str_to_billions(s.get("notesbonds", "0"))
        bills = _str_to_billions(s.get("bills", "0"))
        tips = _str_to_billions(s.get("tips", "0"))
        mbs = _str_to_billions(s.get("mbs", "0"))

        records.append({
            "date": _parse_date(s.get("asOfDate", "")),
            "total_bn": round(total, 1),
            "notesbonds_bn": round(nb, 1),
            "bills_bn": round(bills, 1),
            "tips_bn": round(tips, 1),
            "mbs_bn": round(mbs, 1),
            "tsy_pct": round((nb + bills + tips) / total * 100, 1) if total > 0 else 0,
            "mbs_pct": round(mbs / total * 100, 1) if total > 0 else 0,
            "bills_pct": round(bills / total * 100, 1) if total > 0 else 0,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  SOMA COMPOSITION HISTORY ({len(records)} weeks)")
    print("  " + "=" * 85)
    print(f"  {'Date':<12} {'Total':>10} {'N&B':>10} {'Bills':>10} {'TIPS':>8} "
          f"{'MBS':>10} {'TSY%':>6} {'MBS%':>6}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*10} {'-'*6} {'-'*6}")

    display = records[:min(len(records), 52)]
    for r in display:
        print(f"  {r['date']:<12} {_fmt_billions(r['total_bn']):>10} "
              f"{_fmt_billions(r['notesbonds_bn']):>10} {_fmt_billions(r['bills_bn']):>10} "
              f"{_fmt_billions(r['tips_bn']):>8} {_fmt_billions(r['mbs_bn']):>10} "
              f"{r['tsy_pct']:>5.1f}% {r['mbs_pct']:>5.1f}%")

    if len(records) >= 2:
        latest = records[0]
        oldest = records[-1]
        print(f"\n  Period summary ({oldest['date']} -> {latest['date']}):")
        print(f"  Total:  {_fmt_billions(oldest['total_bn'])} -> {_fmt_billions(latest['total_bn'])} "
              f"({latest['total_bn'] - oldest['total_bn']:+.1f}B)")
        print(f"  MBS %:  {oldest['mbs_pct']:.1f}% -> {latest['mbs_pct']:.1f}%")
        print(f"  Bills %: {oldest['bills_pct']:.1f}% -> {latest['bills_pct']:.1f}%")

    print()

    if export_fmt:
        _export(records, "soma_composition", export_fmt)
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
        rows = data if isinstance(data, list) else data.get("weekly_detail", [data])
        if rows and isinstance(rows[0], dict):
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
    print(f"  Exported: {path}")


MENU = """
  =====================================================
   NY Fed QT & Balance Sheet Analysis
  =====================================================

   1) run             Full QT analysis + runoff pace
   2) composition     SOMA composition history

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
            weeks = _prompt("Weeks of history", "52")
            cmd_run(weeks=int(weeks))
        elif choice == "2":
            weeks = _prompt("Weeks of history", "104")
            cmd_composition(weeks=int(weeks))
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(prog="qt_balance_sheet_analysis.py",
                                description="NY Fed QT & Balance Sheet Analysis")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Full QT analysis")
    s.add_argument("--weeks", type=int, default=52)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("composition", help="SOMA composition history")
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
        cmd_run(weeks=args.weeks, as_json=j, export_fmt=exp)
    elif args.command == "composition":
        cmd_composition(weeks=args.weeks, as_json=j, export_fmt=exp)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
