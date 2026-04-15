#!/usr/bin/env python3
"""
Overnight Funding Stress Monitor
=================================
Combines NY Fed reference rates, ON RRP, and repo operations to produce
a real-time funding stress assessment.

Analysis:
  1. SOFR-EFFR spread matrix (secured vs unsecured divergence)
  2. Rate percentile dispersion (P1-P99 width = market stress proxy)
  3. Target band positioning (where rates print within the corridor)
  4. ON RRP trajectory (reserve regime indicator)
  5. Quarter-end / month-end detection and seasonality flagging
  6. Composite funding stress score

Usage:
    python funding_stress_monitor.py               # interactive CLI
    python funding_stress_monitor.py run            # full stress assessment
    python funding_stress_monitor.py run --json     # JSON for PRISM
    python funding_stress_monitor.py spreads        # spread history analysis
    python funding_stress_monitor.py rrp-trajectory # RRP drainage tracking
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nyfed import (
    cmd_rates, cmd_sofr, cmd_effr, cmd_rrp, cmd_funding_snapshot,
    _fetch_all_rates_latest, _fetch_rate_last, _fetch_rrp_results,
    _safe_float, _parse_date, _fmt_billions, _prompt,
    RATE_TYPES, REQUEST_DELAY,
)

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))


def _is_quarter_end(date_str):
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return d.month in (3, 6, 9, 12) and d.day >= 25
    except (ValueError, TypeError):
        return False


def _is_month_end(date_str):
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return d.day >= 27
    except (ValueError, TypeError):
        return False


def _percentile_width(rate_data):
    p1 = _safe_float(rate_data.get("percentPercentile1"))
    p99 = _safe_float(rate_data.get("percentPercentile99"))
    if p1 and p99:
        return (p99 - p1) * 100
    return None


def _stress_score(spread_bps, dispersion_bps, rrp_bn, target_from, target_to, sofr_rate):
    score = 0.0

    if abs(spread_bps) > 15:
        score += 30
    elif abs(spread_bps) > 8:
        score += 15
    elif abs(spread_bps) > 3:
        score += 5

    if dispersion_bps is not None:
        if dispersion_bps > 15:
            score += 25
        elif dispersion_bps > 8:
            score += 12
        elif dispersion_bps > 4:
            score += 5

    if rrp_bn < 20:
        score += 20
    elif rrp_bn < 50:
        score += 10
    elif rrp_bn < 100:
        score += 5

    if target_to > 0 and sofr_rate > 0:
        above_top = (sofr_rate - target_to) * 100
        below_bottom = (target_from - sofr_rate) * 100
        if above_top > 5:
            score += 20
        elif above_top > 0:
            score += 10
        if below_bottom > 5:
            score += 15

    return min(100.0, score)


def _stress_label(score):
    if score >= 60:
        return "HIGH STRESS"
    elif score >= 35:
        return "ELEVATED"
    elif score >= 15:
        return "MODERATE"
    else:
        return "NORMAL"


def cmd_run(as_json=False, export_fmt=None):
    print("\n  OVERNIGHT FUNDING STRESS MONITOR")
    print("  " + "=" * 70)
    t0 = time.time()

    print("  [1/3] Fetching reference rates...")
    rates = _fetch_all_rates_latest()
    time.sleep(REQUEST_DELAY)

    print("  [2/3] Fetching ON RRP operations...")
    rrp_ops = _fetch_rrp_results(10)
    time.sleep(REQUEST_DELAY)

    print("  [3/3] Fetching SOFR history (30d)...")
    sofr_hist = _fetch_rate_last("sofr", 30)

    if not rates:
        print("  No rate data returned.")
        return

    rate_map = {}
    sofrai = None
    for r in rates:
        rtype = r.get("type", "")
        if rtype == "SOFRAI":
            sofrai = r
        else:
            rate_map[rtype] = r

    sofr = rate_map.get("SOFR", {})
    effr = rate_map.get("EFFR", {})
    obfr = rate_map.get("OBFR", {})
    tgcr = rate_map.get("TGCR", {})
    bgcr = rate_map.get("BGCR", {})

    sofr_rate = _safe_float(sofr.get("percentRate"))
    effr_rate = _safe_float(effr.get("percentRate"))
    obfr_rate = _safe_float(obfr.get("percentRate"))
    tgcr_rate = _safe_float(tgcr.get("percentRate"))
    bgcr_rate = _safe_float(bgcr.get("percentRate"))

    target_from = _safe_float(effr.get("targetRateFrom"))
    target_to = _safe_float(effr.get("targetRateTo"))
    midpoint = (target_from + target_to) / 2 if target_to > 0 else 0

    sofr_effr_spread = (sofr_rate - effr_rate) * 100
    sofr_tgcr_spread = (sofr_rate - tgcr_rate) * 100 if tgcr_rate else None
    effr_obfr_spread = (effr_rate - obfr_rate) * 100 if obfr_rate else None

    sofr_disp = _percentile_width(sofr)
    effr_disp = _percentile_width(effr)

    date = _parse_date(sofr.get("effectiveDate", effr.get("effectiveDate", "")))
    qe_flag = _is_quarter_end(date)
    me_flag = _is_month_end(date)

    rrp_bn = 0
    rrp_cpty = 0
    rrp_trend = []
    if rrp_ops:
        rrp_bn = _safe_float(rrp_ops[0].get("totalAmtAccepted")) / 1e9
        rrp_cpty = rrp_ops[0].get("participatingCpty", rrp_ops[0].get("acceptedCpty", 0))
        for op in rrp_ops:
            rrp_trend.append({
                "date": _parse_date(op.get("operationDate", "")),
                "accepted_bn": round(_safe_float(op.get("totalAmtAccepted")) / 1e9, 2),
                "counterparties": op.get("participatingCpty", op.get("acceptedCpty", 0)),
            })

    score = _stress_score(sofr_effr_spread, sofr_disp, rrp_bn, target_from, target_to, sofr_rate)
    if qe_flag:
        score = min(100, score + 10)
    label = _stress_label(score)

    result = {
        "timestamp": datetime.now().isoformat(),
        "date": date,
        "stress_score": round(score, 1),
        "stress_label": label,
        "quarter_end": qe_flag,
        "month_end": me_flag,
        "target_band": {"lower": target_from, "upper": target_to, "midpoint": midpoint},
        "rates": {
            "SOFR": sofr_rate, "EFFR": effr_rate, "OBFR": obfr_rate,
            "TGCR": tgcr_rate, "BGCR": bgcr_rate,
        },
        "spreads_bps": {
            "SOFR_EFFR": round(sofr_effr_spread, 1),
            "SOFR_TGCR": round(sofr_tgcr_spread, 1) if sofr_tgcr_spread else None,
            "EFFR_OBFR": round(effr_obfr_spread, 1) if effr_obfr_spread else None,
        },
        "dispersion_bps": {
            "SOFR_p1_p99": round(sofr_disp, 1) if sofr_disp else None,
            "EFFR_p1_p99": round(effr_disp, 1) if effr_disp else None,
        },
        "rrp": {
            "accepted_bn": round(rrp_bn, 2),
            "counterparties": rrp_cpty,
            "trend": rrp_trend,
        },
        "sofr_averages": {
            "30d": _safe_float(sofrai.get("average30day")) if sofrai else None,
            "90d": _safe_float(sofrai.get("average90day")) if sofrai else None,
            "180d": _safe_float(sofrai.get("average180day")) if sofrai else None,
        },
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    # Rate table
    print(f"\n  REFERENCE RATES (as of {date})")
    print(f"  Target band: {target_from:.2f}% - {target_to:.2f}%  |  Midpoint: {midpoint:.2f}%")
    if qe_flag:
        print(f"  ** QUARTER-END WINDOW **")
    elif me_flag:
        print(f"  ** MONTH-END WINDOW **")
    print(f"  {'-'*65}")
    print(f"  {'Rate':<8} {'Level':>8} {'vs Mid':>10} {'Volume ($B)':>12} {'P1-P99':>10}")
    print(f"  {'-'*8} {'-'*8} {'-'*10} {'-'*12} {'-'*10}")

    for rlabel, data, rate in [("SOFR", sofr, sofr_rate), ("EFFR", effr, effr_rate),
                                ("OBFR", obfr, obfr_rate), ("TGCR", tgcr, tgcr_rate),
                                ("BGCR", bgcr, bgcr_rate)]:
        vol = _safe_float(data.get("volumeInBillions"))
        vol_str = f"${vol:,.0f}" if vol > 0 else "--"
        vs_mid = f"{(rate - midpoint) * 100:+.1f}bp" if midpoint > 0 else "--"
        disp = _percentile_width(data)
        disp_str = f"{disp:.1f}bp" if disp is not None else "--"
        print(f"  {rlabel:<8} {rate:>7.2f}% {vs_mid:>10} {vol_str:>12} {disp_str:>10}")

    # Spread matrix
    print(f"\n  SPREAD MATRIX")
    print(f"  {'-'*40}")
    print(f"  SOFR - EFFR:  {sofr_effr_spread:+.1f}bp")
    if sofr_tgcr_spread is not None:
        print(f"  SOFR - TGCR:  {sofr_tgcr_spread:+.1f}bp")
    if effr_obfr_spread is not None:
        print(f"  EFFR - OBFR:  {effr_obfr_spread:+.1f}bp")

    # RRP
    if rrp_ops:
        print(f"\n  ON RRP TRAJECTORY")
        print(f"  {'-'*50}")
        print(f"  {'Date':<12} {'Accepted ($B)':>14} {'Counterparties':>16}")
        print(f"  {'-'*12} {'-'*14} {'-'*16}")
        for t in rrp_trend:
            print(f"  {t['date']:<12} {_fmt_billions(t['accepted_bn']):>14} {str(t['counterparties']):>16}")

    # Score
    print(f"\n  {'=' * 50}")
    print(f"  FUNDING STRESS SCORE: {score:.0f} / 100  [{label}]")
    print(f"  {'=' * 50}")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _export(result, "funding_stress", export_fmt)
    return result


def cmd_spreads(obs=60, as_json=False, export_fmt=None):
    print(f"\n  Fetching SOFR and EFFR history ({obs} observations)...")
    t0 = time.time()

    sofr_data = _fetch_rate_last("sofr", obs)
    time.sleep(REQUEST_DELAY)
    effr_data = _fetch_rate_last("effr", obs)

    if not sofr_data or not effr_data:
        print("  Insufficient data.")
        return

    sofr_by_date = {_parse_date(r.get("effectiveDate", "")): r for r in sofr_data}
    effr_by_date = {_parse_date(r.get("effectiveDate", "")): r for r in effr_data}
    common_dates = sorted(set(sofr_by_date.keys()) & set(effr_by_date.keys()))

    records = []
    for d in common_dates:
        s = sofr_by_date[d]
        e = effr_by_date[d]
        sofr_r = _safe_float(s.get("percentRate"))
        effr_r = _safe_float(e.get("percentRate"))
        spread = (sofr_r - effr_r) * 100
        sofr_vol = _safe_float(s.get("volumeInBillions"))
        records.append({
            "date": d,
            "sofr": sofr_r,
            "effr": effr_r,
            "spread_bps": round(spread, 1),
            "sofr_volume_bn": round(sofr_vol, 0) if sofr_vol else None,
            "quarter_end": _is_quarter_end(d),
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  SOFR-EFFR SPREAD HISTORY ({len(records)} observations)")
    print("  " + "=" * 72)
    print(f"  {'Date':<12} {'SOFR':>7} {'EFFR':>7} {'Spread':>8} {'Vol($B)':>10} {'QE':>4}")
    print(f"  {'-'*12} {'-'*7} {'-'*7} {'-'*8} {'-'*10} {'-'*4}")

    for r in records[-40:]:
        vol_str = f"{r['sofr_volume_bn']:,.0f}" if r["sofr_volume_bn"] else "--"
        qe_str = " *" if r["quarter_end"] else ""
        print(f"  {r['date']:<12} {r['sofr']:>6.2f}% {r['effr']:>6.2f}% "
              f"{r['spread_bps']:>+7.1f} {vol_str:>10}{qe_str}")

    spreads = [r["spread_bps"] for r in records]
    avg = sum(spreads) / len(spreads)
    print(f"\n  Spread range: {min(spreads):+.1f}bp to {max(spreads):+.1f}bp  |  "
          f"Mean: {avg:+.1f}bp  |  Latest: {spreads[-1]:+.1f}bp")

    qe_spreads = [r["spread_bps"] for r in records if r["quarter_end"]]
    non_qe_spreads = [r["spread_bps"] for r in records if not r["quarter_end"]]
    if qe_spreads and non_qe_spreads:
        qe_avg = sum(qe_spreads) / len(qe_spreads)
        non_qe_avg = sum(non_qe_spreads) / len(non_qe_spreads)
        print(f"  Quarter-end avg: {qe_avg:+.1f}bp  |  Non-QE avg: {non_qe_avg:+.1f}bp  |  "
              f"QE premium: {qe_avg - non_qe_avg:+.1f}bp")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _export(records, "sofr_effr_spreads", export_fmt)
    return records


def cmd_rrp_trajectory(n=30, as_json=False, export_fmt=None):
    print(f"\n  Fetching ON RRP trajectory (last {n} operations)...")
    ops = _fetch_rrp_results(n)

    if not ops:
        print("  No data returned.")
        return

    records = []
    for i, op in enumerate(ops):
        accepted = _safe_float(op.get("totalAmtAccepted")) / 1e9
        cpty = op.get("participatingCpty", op.get("acceptedCpty", 0))
        prev_accepted = _safe_float(ops[i + 1].get("totalAmtAccepted")) / 1e9 if i + 1 < len(ops) else None
        chg = accepted - prev_accepted if prev_accepted is not None else None
        records.append({
            "date": _parse_date(op.get("operationDate", "")),
            "accepted_bn": round(accepted, 2),
            "counterparties": cpty,
            "day_change_bn": round(chg, 2) if chg is not None else None,
        })

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  ON RRP DRAINAGE TRAJECTORY ({len(records)} operations)")
    print("  " + "=" * 60)
    print(f"  {'Date':<12} {'Accepted ($B)':>14} {'DoD Chg':>10} {'CPTYs':>8}")
    print(f"  {'-'*12} {'-'*14} {'-'*10} {'-'*8}")

    for r in records:
        chg_str = f"{r['day_change_bn']:+.1f}" if r["day_change_bn"] is not None else "--"
        print(f"  {r['date']:<12} {_fmt_billions(r['accepted_bn']):>14} {chg_str:>10} "
              f"{str(r['counterparties']):>8}")

    if len(records) >= 2:
        latest = records[0]["accepted_bn"]
        oldest = records[-1]["accepted_bn"]
        chg = latest - oldest
        print(f"\n  Period change: {chg:+.1f}B over {len(records)} days")
        if latest > 500:
            print(f"  Reserve regime: AMPLE (substantial excess liquidity)")
        elif latest > 100:
            print(f"  Reserve regime: ADEQUATE (moderate RRP usage)")
        elif latest > 20:
            print(f"  Reserve regime: DECLINING (watch for scarcity)")
        else:
            print(f"  Reserve regime: SCARCE (minimal RRP, potential stress)")

    print()

    if export_fmt:
        _export(records, "rrp_trajectory", export_fmt)
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
        rows = data if isinstance(data, list) else [data]
        if rows and isinstance(rows[0], dict):
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
    print(f"  Exported: {path}")


# --- Interactive + Argparse ---

MENU = """
  =====================================================
   NY Fed Overnight Funding Stress Monitor
  =====================================================

   1) run             Full stress assessment
   2) spreads         SOFR-EFFR spread history
   3) rrp-trajectory  ON RRP drainage tracking

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
            cmd_run()
        elif choice == "2":
            obs = _prompt("Number of observations", "60")
            cmd_spreads(obs=int(obs))
        elif choice == "3":
            n = _prompt("Number of operations", "30")
            cmd_rrp_trajectory(n=int(n))
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(prog="funding_stress_monitor.py",
                                description="NY Fed Overnight Funding Stress Monitor")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Full stress assessment")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("spreads", help="SOFR-EFFR spread history")
    s.add_argument("--obs", type=int, default=60)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("rrp-trajectory", help="ON RRP drainage tracking")
    s.add_argument("--count", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "run":
        cmd_run(as_json=j, export_fmt=exp)
    elif args.command == "spreads":
        cmd_spreads(obs=args.obs, as_json=j, export_fmt=exp)
    elif args.command == "rrp-trajectory":
        cmd_rrp_trajectory(n=args.count, as_json=j, export_fmt=exp)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
