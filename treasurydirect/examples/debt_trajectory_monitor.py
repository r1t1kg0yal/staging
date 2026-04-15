#!/usr/bin/env python3
"""
Debt-to-the-penny trajectory
============================
TreasuryDirect NP_WS debt JSON: current snapshot plus daily history to
monitor total public debt, month-over-month and year-over-year changes,
and simple growth rates.

Usage:
    python debt_trajectory_monitor.py
    python debt_trajectory_monitor.py run
    python debt_trajectory_monitor.py run --json
    python debt_trajectory_monitor.py history --months 12
    python debt_trajectory_monitor.py run --export json
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlencode

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from treasurydirect import DEBT_ENDPOINTS

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


def _safe_float(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(str(x).strip().replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_effective_date(s: str) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    base = s.rsplit(" ", 1)[0].strip()
    try:
        return datetime.strptime(base, "%B %d, %Y")
    except ValueError:
        return None


def _public_debt_value(rec: dict) -> Optional[float]:
    for k in ("publicDebt", "totalPublicDebtOutstanding", "tot_pub_debt_out_amt", "totalDebt"):
        v = _safe_float(rec.get(k))
        if v is not None:
            return v
    return None


def _fetch_current(session: requests.Session) -> Optional[dict]:
    url = f"{DEBT_ENDPOINTS['current']}?format=json"
    r = session.get(url, timeout=45)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else None


def _normalize_history_payload(data: Any) -> list:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        inner = data.get("entries") or data.get("data") or []
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


def _fetch_debt_range(
    session: requests.Session,
    start: datetime,
    end: datetime,
    progress_label: str,
    quiet: bool = False,
) -> list:
    rows: list = []
    cur = start.date()
    end_d = end.date()
    t0 = time.time()
    last_print = t0
    chunk_idx = 0
    while cur <= end_d:
        if not quiet and time.time() - last_print >= 5:
            print(f"  {progress_label}: loaded {len(rows)} rows... ({int(time.time() - t0)}s)")
            sys.stdout.flush()
            last_print = time.time()
        chunk_end = min(cur + timedelta(days=365), end_d)
        params = {
            "startdate": cur.isoformat(),
            "enddate": chunk_end.isoformat(),
            "format": "json",
        }
        url = f"{DEBT_ENDPOINTS['search']}?{urlencode(params)}"
        chunk_idx += 1
        if not quiet:
            print(f"  [{progress_label}] chunk {chunk_idx}: {cur} -> {chunk_end} ({int(time.time() - t0)}s)")
            sys.stdout.flush()
        r = session.get(url, timeout=60)
        r.raise_for_status()
        part = _normalize_history_payload(r.json())
        rows.extend(part)
        cur = chunk_end + timedelta(days=1)
        time.sleep(0.5)
    return rows


def _dedupe_sort_records(records: list) -> list:
    seen = set()
    out = []
    for rec in records:
        dt = _parse_effective_date(rec.get("effectiveDate", ""))
        key = (rec.get("effectiveDate"), _public_debt_value(rec))
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    out.sort(key=lambda r: _parse_effective_date(r.get("effectiveDate", "")) or datetime.min)
    return out


def _closest_on_or_before(sorted_desc: list, target: datetime) -> Optional[dict]:
    best: Optional[dict] = None
    best_delta: Optional[int] = None
    for rec in sorted_desc:
        dt = _parse_effective_date(rec.get("effectiveDate", ""))
        if dt is None:
            continue
        delta = (target - dt).days
        if delta >= 0 and (best_delta is None or delta < best_delta):
            best = rec
            best_delta = delta
    return best


def _daily_changes(sorted_asc: list) -> list:
    out = []
    for i in range(1, len(sorted_asc)):
        prev = sorted_asc[i - 1]
        cur = sorted_asc[i]
        d0 = _parse_effective_date(prev.get("effectiveDate", ""))
        d1 = _parse_effective_date(cur.get("effectiveDate", ""))
        v0 = _public_debt_value(prev)
        v1 = _public_debt_value(cur)
        if d0 is None or d1 is None or v0 is None or v1 is None:
            continue
        days = max(1, (d1 - d0).days)
        chg = v1 - v0
        out.append({
            "date": d1.strftime("%Y-%m-%d"),
            "public_debt_bn": round(v1 / 1e9, 2),
            "chg_bn": round(chg / 1e9, 3),
            "chg_per_day_bn": round(chg / 1e9 / days, 4),
        })
    return out


def cmd_run(history_days: int = 400, as_json: bool = False, export_fmt: Optional[str] = None):
    session = _session()
    if not as_json:
        print("\n  DEBT TRAJECTORY MONITOR")
        print("  " + "=" * 72)
    t0 = time.time()
    last_print = t0

    if not as_json:
        print("  [1/2] Current debt snapshot...")
        sys.stdout.flush()
    current = _fetch_current(session)
    if not as_json and time.time() - last_print >= 5:
        last_print = time.time()

    end = datetime.now()
    start = end - timedelta(days=history_days)
    if not as_json:
        print(f"  [2/2] Historical debt ({start.date()} -> {end.date()})...")
        sys.stdout.flush()
    raw = _fetch_debt_range(session, start, end, "history", quiet=as_json)
    records = _dedupe_sort_records(raw)
    if not as_json and time.time() - last_print >= 5:
        print(f"  ...merge complete, {len(records)} unique days ({int(time.time() - t0)}s)")
        sys.stdout.flush()

    sorted_asc = records
    sorted_desc = list(reversed(sorted_asc))

    latest_rec = sorted_desc[0] if sorted_desc else None
    latest_dt = _parse_effective_date(latest_rec.get("effectiveDate", "")) if latest_rec else None
    latest_val = _public_debt_value(latest_rec) if latest_rec else None

    mom_rec = None
    yoy_rec = None
    if latest_dt and sorted_desc:
        mom_rec = _closest_on_or_before(sorted_desc, latest_dt - timedelta(days=30))
        yoy_rec = _closest_on_or_before(sorted_desc, latest_dt - timedelta(days=365))

    mom_val = _public_debt_value(mom_rec) if mom_rec else None
    yoy_val = _public_debt_value(yoy_rec) if yoy_rec else None

    mom_pct = None
    if latest_val is not None and mom_val and mom_val > 0:
        mom_pct = round((latest_val - mom_val) / mom_val * 100, 4)
    yoy_pct = None
    if latest_val is not None and yoy_val and yoy_val > 0:
        yoy_pct = round((latest_val - yoy_val) / yoy_val * 100, 4)

    daily = _daily_changes(sorted_asc)
    recent_daily = daily[-20:] if daily else []

    cutoff_6m = (latest_dt or end) - timedelta(days=180)
    traj_6m = [
        r for r in sorted_desc
        if (_parse_effective_date(r.get("effectiveDate", "")) or datetime.min) >= cutoff_6m
    ][:40]

    snap = {}
    if current:
        snap = {
            "effectiveDate": current.get("effectiveDate"),
            "publicDebt_bn": round(_public_debt_value(current) / 1e9, 2) if _public_debt_value(current) else None,
            "totalDebt_bn": round(_safe_float(current.get("totalDebt")) / 1e9, 2)
            if _safe_float(current.get("totalDebt")) else None,
            "governmentHoldings_bn": round(_safe_float(current.get("governmentHoldings")) / 1e9, 2)
            if _safe_float(current.get("governmentHoldings")) else None,
        }

    result = {
        "timestamp": datetime.now().isoformat(),
        "current_api": snap,
        "history_days_fetched": history_days,
        "series_points": len(sorted_asc),
        "latest_from_history": {
            "effectiveDate": latest_rec.get("effectiveDate") if latest_rec else None,
            "public_debt_bn": round(latest_val / 1e9, 2) if latest_val else None,
        },
        "changes": {
            "mom_reference_date": mom_rec.get("effectiveDate") if mom_rec else None,
            "mom_public_debt_bn": round(mom_val / 1e9, 2) if mom_val else None,
            "mom_change_pct": mom_pct,
            "yoy_reference_date": yoy_rec.get("effectiveDate") if yoy_rec else None,
            "yoy_public_debt_bn": round(yoy_val / 1e9, 2) if yoy_val else None,
            "yoy_change_pct": yoy_pct,
        },
        "trajectory_recent_daily": recent_daily,
        "trajectory_6m_sample": [
            {
                "effectiveDate": r.get("effectiveDate"),
                "public_debt_bn": round(_public_debt_value(r) / 1e9, 2)
                if _public_debt_value(r) else None,
            }
            for r in traj_6m
        ],
        "history_sorted_asc": sorted_asc,
    }

    if as_json:
        slim = {k: v for k, v in result.items() if k != "history_sorted_asc"}
        slim["history_sorted_asc"] = sorted_asc
        print(json.dumps(slim, indent=2, default=str))
        if export_fmt:
            _export(slim, "debt_trajectory", export_fmt, stream=sys.stderr)
        return result

    print("\n  CURRENT (NP_WS/debt/current)")
    print("  " + "-" * 60)
    if snap:
        print(f"  As of:        {snap.get('effectiveDate')}")
        print(f"  Public debt:  {snap.get('publicDebt_bn')} bn USD")
        print(f"  Total debt:     {snap.get('totalDebt_bn')} bn USD")
        print(f"  Gov holdings:   {snap.get('governmentHoldings_bn')} bn USD")
    else:
        print("  No current payload returned.")

    print("\n  LATEST FROM HISTORY SEARCH")
    print("  " + "-" * 60)
    if latest_rec:
        print(f"  Date:         {latest_rec.get('effectiveDate')}")
        print(f"  Public debt:  {result['latest_from_history']['public_debt_bn']} bn USD")
    else:
        print("  No historical rows.")

    print("\n  GROWTH (public debt outstanding)")
    print("  " + "-" * 60)
    if mom_pct is not None:
        print(f"  ~30d change vs {mom_rec.get('effectiveDate')}: {mom_pct:+.4f}% "
              f"(from {round(mom_val / 1e9, 2)} bn)")
    else:
        print("  ~30d change: insufficient history")
    if yoy_pct is not None:
        print(f"  ~365d change vs {yoy_rec.get('effectiveDate')}: {yoy_pct:+.4f}% "
              f"(from {round(yoy_val / 1e9, 2)} bn)")
    else:
        print("  ~365d change: insufficient history")

    print("\n  RECENT DAY-OVER-DAY (from search series)")
    print("  " + "-" * 72)
    print(f"  {'Date':<12} {'Public bn':>12} {'Chg bn':>12} {'Chg/day bn':>14}")
    print("  " + "-" * 72)
    for row in recent_daily:
        print(
            f"  {row['date']:<12} {row['public_debt_bn']:>12.2f} "
            f"{row['chg_bn']:>+12.3f} {row['chg_per_day_bn']:>+14.4f}"
        )

    print("\n  6-MONTH WINDOW (newest dates first, sample)")
    print("  " + "-" * 50)
    for row in result["trajectory_6m_sample"][:15]:
        print(f"  {row.get('effectiveDate')!s:<32} {row.get('public_debt_bn')} bn")

    print(f"\n  Completed in {int(time.time() - t0)}s ({len(sorted_asc)} points)\n")

    if export_fmt:
        _export({k: v for k, v in result.items()}, "debt_trajectory", export_fmt)
    return result


def cmd_history(months: int = 6, as_json: bool = False, export_fmt: Optional[str] = None):
    session = _session()
    if not as_json:
        print("\n  DEBT HISTORY")
        print("  " + "=" * 72)
    t0 = time.time()
    end = datetime.now()
    start = end - timedelta(days=int(months * 30.4375))
    raw = _fetch_debt_range(session, start, end, f"{months}mo", quiet=as_json)
    records = _dedupe_sort_records(raw)
    sorted_asc = records
    daily = _daily_changes(sorted_asc)

    growth_week = None
    if len(sorted_asc) >= 8:
        v0 = _public_debt_value(sorted_asc[-8])
        v1 = _public_debt_value(sorted_asc[-1])
        if v0 and v1 and v0 > 0:
            growth_week = round((v1 - v0) / v0 * 100, 4)

    result = {
        "timestamp": datetime.now().isoformat(),
        "months": months,
        "points": len(sorted_asc),
        "daily_changes": daily,
        "approx_weekly_pct_change": growth_week,
        "history_sorted_asc": sorted_asc,
    }

    if as_json:
        slim = {k: v for k, v in result.items() if k != "history_sorted_asc"}
        slim["history_sorted_asc"] = sorted_asc
        print(json.dumps(slim, indent=2, default=str))
        if export_fmt:
            _export(slim, "debt_history", export_fmt, stream=sys.stderr)
        return result

    print(f"  Range ~{months} months: {len(sorted_asc)} trading-day points")
    if growth_week is not None:
        print(f"  Approx 7-observation log change (public debt): {growth_week:+.4f}%")
    print("\n  END OF SERIES (oldest -> newest, up to 24 rows)")
    print("  " + "-" * 72)
    tail = sorted_asc[-24:]
    print(f"  {'Date':<32} {'Public bn':>14}")
    print("  " + "-" * 72)
    for rec in tail:
        dt_s = str(rec.get("effectiveDate", ""))
        pv = _public_debt_value(rec)
        pv_s = f"{pv / 1e9:.2f}" if pv is not None else "-"
        print(f"  {dt_s:<32} {pv_s:>14}")

    print("\n  DAILY CHANGES (last 24 steps)")
    print("  " + "-" * 72)
    for row in daily[-24:]:
        print(
            f"  {row['date']:<12} {row['public_debt_bn']:>10.2f} bn  "
            f"chg {row['chg_bn']:+.3f} bn  ({row['chg_per_day_bn']:+.4f} bn/day)"
        )

    print(f"\n  Completed in {int(time.time() - t0)}s\n")

    if export_fmt:
        _export({k: v for k, v in result.items()}, "debt_history", export_fmt)
    return result


def _export(data: dict, prefix: str, fmt: str, stream=sys.stdout):
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
        rows = data.get("history_sorted_asc") or data.get("trajectory_recent_daily") or []
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
   TreasuryDirect debt trajectory monitor
  =====================================================

   1) run             Current snapshot + history + MoM/YoY
   2) history         Rolling window (6 or 12 months)

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
            d = _prompt("History days to pull", "400")
            cmd_run(history_days=int(d), as_json=False, export_fmt=None)
        elif choice == "2":
            m = _prompt("Months (6 or 12)", "6")
            cmd_history(months=int(m), as_json=False, export_fmt=None)
        else:
            print(f"  Unknown command: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="debt_trajectory_monitor.py",
        description="TreasuryDirect debt-to-the-penny trajectory (HTTP JSON)",
    )
    sub = p.add_subparsers(dest="command")

    r = sub.add_parser("run", help="Current debt + history + MoM/YoY")
    r.add_argument("--history-days", type=int, default=400, dest="history_days")
    r.add_argument("--json", action="store_true")
    r.add_argument("--export", choices=["csv", "json"])

    h = sub.add_parser("history", help="Fixed horizon history")
    h.add_argument("--months", type=int, default=6, help="Approximate months of history (default 6)")
    h.add_argument("--json", action="store_true")
    h.add_argument("--export", choices=["csv", "json"])

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
        cmd_run(history_days=args.history_days, as_json=j, export_fmt=exp)
    elif cmd == "history":
        cmd_history(months=args.months, as_json=j, export_fmt=exp)


if __name__ == "__main__":
    main()
