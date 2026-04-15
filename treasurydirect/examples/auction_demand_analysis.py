#!/usr/bin/env python3
"""
Treasury auction demand quality
================================
Reads TreasuryDirect securities JSON (Notes/Bonds by default), computes
bid-to-cover, tail (high vs median yield, bps), and direct / indirect /
primary dealer shares of accepted competitive size.

Usage:
    python auction_demand_analysis.py
    python auction_demand_analysis.py run
    python auction_demand_analysis.py run --days 90 --json
    python auction_demand_analysis.py by-type --type Bill --days 30
    python auction_demand_analysis.py run --export json
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Optional
from urllib.parse import urlencode

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from treasurydirect import SECURITIES_ENDPOINTS, SECURITY_TYPES, TreasuryDirectScraper

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _prompt(label: str, default: str = "") -> str:
    tail = f" [{default}]" if default else ""
    v = input(f"  {label}{tail}: ").strip()
    return v if v else default


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return s


def _safe_float(x):
    if x is None or x == "":
        return None
    try:
        return float(str(x).strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


def _auction_sort_key(rec: dict) -> str:
    return (rec.get("auctionDate") or "")[:19]


def _fetch_auctions(
    session: requests.Session,
    security_type: str,
    start_mmddyyyy: str,
    end_mmddyyyy: str,
    label: str,
    t0: float,
    quiet: bool = False,
) -> list:
    params = {
        "format": "json",
        "type": security_type,
        "startDate": start_mmddyyyy,
        "endDate": end_mmddyyyy,
        "pagesize": "250",
    }
    url = f"{SECURITIES_ENDPOINTS['search']}?{urlencode(params)}"
    if not quiet:
        print(f"  Fetching {security_type} ({start_mmddyyyy} - {end_mmddyyyy})... ({int(time.time() - t0)}s)")
        sys.stdout.flush()
    r = session.get(url, timeout=45)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        return []
    out = []
    for rec in data:
        if isinstance(rec, dict):
            TreasuryDirectScraper._compute_tail(rec)
            out.append(rec)
    if not quiet:
        print(f"    {len(out)} records ({label})")
        sys.stdout.flush()
    return out


def _allocation_pct(rec: dict) -> tuple:
    tot = _safe_float(rec.get("totalAccepted"))
    if not tot or tot <= 0:
        comp = _safe_float(rec.get("competitiveAccepted"))
        tot = comp if comp and comp > 0 else None
    if not tot or tot <= 0:
        return None, None, None
    d = _safe_float(rec.get("directBidderAccepted")) or 0.0
    i = _safe_float(rec.get("indirectBidderAccepted")) or 0.0
    p = _safe_float(rec.get("primaryDealerAccepted")) or 0.0
    return 100.0 * d / tot, 100.0 * i / tot, 100.0 * p / tot


def _summarize_type(records: list, name: str) -> dict:
    if not records:
        return {
            "security_type": name,
            "count": 0,
            "bid_to_cover_mean": None,
            "bid_to_cover_median": None,
            "tail_bps_mean": None,
            "tail_bps_median": None,
            "direct_pct_mean": None,
            "indirect_pct_mean": None,
            "dealer_pct_mean": None,
        }
    bcs = [_safe_float(r.get("bidToCoverRatio")) for r in records]
    bcs = [x for x in bcs if x is not None]
    tails = [_safe_float(r.get("tailBps")) for r in records]
    tails = [x for x in tails if x is not None]
    allocs = [_allocation_pct(r) for r in records]
    dps = [a[0] for a in allocs if a[0] is not None]
    ips = [a[1] for a in allocs if a[1] is not None]
    pps = [a[2] for a in allocs if a[2] is not None]
    return {
        "security_type": name,
        "count": len(records),
        "bid_to_cover_mean": round(mean(bcs), 3) if bcs else None,
        "bid_to_cover_median": round(median(bcs), 3) if bcs else None,
        "tail_bps_mean": round(mean(tails), 2) if tails else None,
        "tail_bps_median": round(median(tails), 2) if tails else None,
        "direct_pct_mean": round(mean(dps), 2) if dps else None,
        "indirect_pct_mean": round(mean(ips), 2) if ips else None,
        "dealer_pct_mean": round(mean(pps), 2) if pps else None,
    }


def _trend_split(records: list) -> tuple:
    ordered = sorted(records, key=_auction_sort_key, reverse=True)
    n = len(ordered)
    if n < 4:
        return None, None
    half = max(2, n // 2)
    recent = ordered[:half]
    prior = ordered[half : half * 2] if half * 2 <= n else ordered[half:]
    if not prior:
        return None, None

    def avg_bc(rs):
        xs = [_safe_float(r.get("bidToCoverRatio")) for r in rs]
        xs = [x for x in xs if x is not None]
        return mean(xs) if xs else None

    return avg_bc(recent), avg_bc(prior)


def cmd_run(days: int = 60, as_json: bool = False, export_fmt: Optional[str] = None):
    session = _session()
    end = datetime.now()
    start = end - timedelta(days=days)
    start_s = start.strftime("%m/%d/%Y")
    end_s = end.strftime("%m/%d/%Y")
    types = ["Note", "Bond"]

    if not as_json:
        print("\n  TREASURY AUCTION DEMAND ANALYSIS")
        print("  " + "=" * 72)
    t0 = time.time()
    last_prog = t0

    combined: list = []
    by_type: dict[str, list] = {t: [] for t in types}
    for i, st in enumerate(types):
        if not as_json and time.time() - last_prog >= 5:
            print(f"  ...still loading ({i}/{len(types)} types)... ({int(time.time() - t0)}s)")
            sys.stdout.flush()
            last_prog = time.time()
        rows = _fetch_auctions(session, st, start_s, end_s, st, t0, quiet=as_json)
        by_type[st].extend(rows)
        combined.extend(rows)

    seen = set()
    deduped = []
    for rec in sorted(combined, key=_auction_sort_key, reverse=True):
        k = f"{rec.get('cusip', '')}_{(rec.get('auctionDate') or '')[:10]}"
        if k in seen:
            continue
        seen.add(k)
        deduped.append(rec)

    summaries = [_summarize_type(by_type[t], t) for t in types]
    overall = _summarize_type(deduped, "Note+Bond")
    tr_recent, tr_prior = _trend_split(deduped)
    trend_note = None
    if tr_recent is not None and tr_prior is not None:
        trend_note = round(tr_recent - tr_prior, 4)

    top_rows = []
    for rec in sorted(deduped, key=_auction_sort_key, reverse=True)[:12]:
        d, i, p = _allocation_pct(rec)
        top_rows.append({
            "auctionDate": (rec.get("auctionDate") or "")[:10],
            "cusip": rec.get("cusip"),
            "securityType": rec.get("securityType"),
            "securityTerm": rec.get("securityTerm"),
            "bidToCoverRatio": _safe_float(rec.get("bidToCoverRatio")),
            "tailBps": _safe_float(rec.get("tailBps")),
            "highYield": rec.get("highYield"),
            "direct_pct": d,
            "indirect_pct": i,
            "dealer_pct": p,
        })

    result = {
        "timestamp": datetime.now().isoformat(),
        "window_days": days,
        "startDate": start_s,
        "endDate": end_s,
        "auction_count_unique": len(deduped),
        "by_security_type": summaries,
        "combined_metrics": overall,
        "bid_to_cover_trend": {
            "recent_half_mean": tr_recent,
            "prior_half_mean": tr_prior,
            "recent_minus_prior": trend_note,
        },
        "recent_auctions": top_rows,
        "raw_auctions": deduped,
    }

    if as_json:
        out = {k: v for k, v in result.items() if k != "raw_auctions"}
        out["raw_auctions"] = deduped
        print(json.dumps(out, indent=2, default=str))
        if export_fmt:
            _export(out, "auction_demand", export_fmt, stream=sys.stderr)
        return result

    print(f"\n  Window: last {days} days ({start_s} -> {end_s})")
    print(f"  Unique auctions (Notes+Bonds, deduped): {len(deduped)}")
    print("\n  DEMAND QUALITY BY TYPE")
    print("  " + "-" * 72)
    hdr = f"  {'Type':<8} {'N':>4} {'B/C mean':>10} {'B/C med':>10} {'Tail mean':>11} {'Dir%':>7} {'Ind%':>7} {'PD%':>7}"
    print(hdr)
    print("  " + "-" * 72)
    for s in summaries + [overall]:
        if s["security_type"] == "Note+Bond":
            print("  " + "-" * 72)
        print(
            f"  {s['security_type']:<8} {s['count']:>4} "
            f"{(str(s['bid_to_cover_mean']) if s['bid_to_cover_mean'] is not None else '-'):>10} "
            f"{(str(s['bid_to_cover_median']) if s['bid_to_cover_median'] is not None else '-'):>10} "
            f"{(str(s['tail_bps_mean']) if s['tail_bps_mean'] is not None else '-'):>11} "
            f"{(str(s['direct_pct_mean']) if s['direct_pct_mean'] is not None else '-'):>7} "
            f"{(str(s['indirect_pct_mean']) if s['indirect_pct_mean'] is not None else '-'):>7} "
            f"{(str(s['dealer_pct_mean']) if s['dealer_pct_mean'] is not None else '-'):>7}"
        )

    print("\n  BID-TO-COVER TREND (recent half vs earlier half, same window)")
    print("  " + "-" * 72)
    if tr_recent is None:
        print("  Not enough auctions to split window.")
    else:
        print(f"  Recent half mean B/C: {tr_recent:.3f}")
        print(f"  Earlier half mean B/C: {tr_prior:.3f}")
        if trend_note is not None:
            sign = "+" if trend_note >= 0 else ""
            print(f"  Delta (recent - earlier): {sign}{trend_note:.4f}")

    print("\n  LATEST AUCTIONS (allocation % of total accepted)")
    print("  " + "-" * 100)
    print(
        f"  {'Date':<12} {'Type':<6} {'Term':<14} {'B/C':>6} {'Tail':>8} "
        f"{'Dir%':>7} {'Ind%':>7} {'PD%':>7} {'CUSIP':<12}"
    )
    print("  " + "-" * 100)
    for row in top_rows:
        bc = row["bidToCoverRatio"]
        tl = row["tailBps"]
        bc_s = f"{bc:.2f}" if bc is not None else "-"
        tl_s = f"{tl:.1f}" if tl is not None else "-"
        d_s = f"{row['direct_pct']:.1f}" if row["direct_pct"] is not None else "-"
        i_s = f"{row['indirect_pct']:.1f}" if row["indirect_pct"] is not None else "-"
        p_s = f"{row['dealer_pct']:.1f}" if row["dealer_pct"] is not None else "-"
        term = (row.get("securityTerm") or "")[:14]
        print(
            f"  {row['auctionDate']:<12} {str(row['securityType']):<6} {term:<14} "
            f"{bc_s:>6} {tl_s:>8} {d_s:>7} {i_s:>7} {p_s:>7} {str(row['cusip']):<12}"
        )

    print(f"\n  Completed in {int(time.time() - t0)}s\n")

    if export_fmt:
        _export({k: v for k, v in result.items()}, "auction_demand", export_fmt)
    return result


def cmd_by_type(
    security_type: str,
    days: int = 60,
    as_json: bool = False,
    export_fmt: Optional[str] = None,
):
    if security_type not in SECURITY_TYPES:
        print(f"  Unknown type {security_type}. Choose from {SECURITY_TYPES}")
        return None
    session = _session()
    end = datetime.now()
    start = end - timedelta(days=days)
    start_s = start.strftime("%m/%d/%Y")
    end_s = end.strftime("%m/%d/%Y")

    if not as_json:
        print("\n  TREASURY AUCTION DEMAND BY TYPE")
        print("  " + "=" * 72)
    t0 = time.time()
    rows = _fetch_auctions(session, security_type, start_s, end_s, security_type, t0, quiet=as_json)

    summary = _summarize_type(rows, security_type)
    tr_recent, tr_prior = _trend_split(rows)
    trend_note = None
    if tr_recent is not None and tr_prior is not None:
        trend_note = round(tr_recent - tr_prior, 4)

    result = {
        "timestamp": datetime.now().isoformat(),
        "security_type": security_type,
        "window_days": days,
        "startDate": start_s,
        "endDate": end_s,
        "summary": summary,
        "bid_to_cover_trend": {
            "recent_half_mean": tr_recent,
            "prior_half_mean": tr_prior,
            "recent_minus_prior": trend_note,
        },
        "auctions": rows,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, f"auction_demand_{security_type.lower()}", export_fmt, stream=sys.stderr)
        return result

    print(f"\n  Type: {security_type}  |  Window: {days} days")
    s = summary
    print(f"  Auctions: {s['count']}")
    print(f"  B/C mean / median: {s['bid_to_cover_mean']} / {s['bid_to_cover_median']}")
    print(f"  Tail bps mean / median: {s['tail_bps_mean']} / {s['tail_bps_median']}")
    print(f"  Mean alloc % direct / indirect / PD: "
          f"{s['direct_pct_mean']} / {s['indirect_pct_mean']} / {s['dealer_pct_mean']}")
    if trend_note is not None:
        print(f"  B/C trend (recent - earlier half): {trend_note:+.4f}")
    print(f"\n  Completed in {int(time.time() - t0)}s\n")

    if export_fmt:
        _export(result, f"auction_demand_{security_type.lower()}", export_fmt)
    return result


def _export(data, prefix: str, fmt: str, stream=sys.stdout):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    path = os.path.join(
        SCRIPT_DIR_LOCAL,
        "..",
        "data",
        f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}",
    )
    if fmt == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = data.get("raw_auctions") or data.get("auctions") or []
        if not rows and "recent_auctions" in data:
            rows = data["recent_auctions"]
        if rows and isinstance(rows[0], dict):
            keys = list(rows[0].keys())
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
                w.writeheader()
                for row in rows:
                    w.writerow(row)
    print(f"  Exported: {path}", file=stream)


MENU = """
  =====================================================
   TreasuryDirect auction demand analysis
  =====================================================

   1) run             Notes + Bonds, demand dashboard
   2) by-type         Single security type

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
        if choice == "1":
            d = _prompt("Days back", "60")
            cmd_run(days=int(d), as_json=False, export_fmt=None)
        elif choice == "2":
            print(f"  Types: {', '.join(SECURITY_TYPES)}")
            st = _prompt("Security type", "Bill")
            d = _prompt("Days back", "60")
            cmd_by_type(st, days=int(d), as_json=False, export_fmt=None)
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="auction_demand_analysis.py",
        description="TreasuryDirect auction demand metrics (HTTP JSON)",
    )
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("run", help="Notes + Bonds dashboard")
    r.add_argument("--days", type=int, default=60)
    r.add_argument("--json", action="store_true")
    r.add_argument("--export", choices=["csv", "json"])

    b = sub.add_parser("by-type", help="Single security type")
    b.add_argument("--type", required=True, choices=SECURITY_TYPES)
    b.add_argument("--days", type=int, default=60)
    b.add_argument("--json", action="store_true")
    b.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    cmd = getattr(args, "command", None)
    if cmd is None:
        interactive_loop()
        return
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)
    if cmd == "run":
        cmd_run(days=args.days, as_json=j, export_fmt=exp)
    elif cmd == "by-type":
        cmd_by_type(args.type, days=args.days, as_json=j, export_fmt=exp)


if __name__ == "__main__":
    main()
