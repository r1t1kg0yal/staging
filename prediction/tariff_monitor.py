#!/usr/bin/env python3
"""
Tariff Monitor
==============
Pulls all trade/tariff-related prediction markets from Kalshi and Polymarket,
classifies by tariff dimension (China, EU, autos, reciprocal, etc.), shows
current crowd-implied probabilities, fetches price histories, and runs event
detection to identify tariff repricing episodes.

Designed for PRISM context ingestion: the --json output gives a structured
view of what the crowd is pricing on tariff escalation, de-escalation,
trade deals, and sector-specific impacts.

Usage:
    python tariff_monitor.py                    # interactive menu
    python tariff_monitor.py dashboard          # full terminal dashboard
    python tariff_monitor.py dashboard --json   # structured JSON output
    python tariff_monitor.py search             # discover tariff-related markets
    python tariff_monitor.py history            # price history + shock detection
    python tariff_monitor.py history --days-back 180 --top-n 15
    python tariff_monitor.py timeline           # tariff repricing timeline
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from prediction_markets import (
    kalshi_get_all_events,
    kalshi_extract_market_record,
    kalshi_get_candlesticks,
    poly_get_all_events,
    poly_extract_market_record,
    poly_get_price_history,
    _safe_volume,
    _ts_to_iso,
    detect_shocks,
    detect_regime_shifts,
    compute_volatility_profile,
    _extract_series,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")

TARIFF_KEYWORDS = [
    "tariff", "tariffs",
    "trade war", "trade deal", "trade deficit", "trade surplus",
    "trade policy", "trade agreement", "trade negotiation",
    "import duty", "import duties", "export ban", "export control",
    "reciprocal tariff", "retaliatory tariff",
    "customs duty", "trade barrier",
    "section 301", "section 232",
    "trade representative",
    "china trade", "china tariff", "china import",
    "eu tariff", "european tariff", "eu trade",
    "auto tariff", "car tariff", "automotive tariff",
    "steel tariff", "aluminum tariff",
    "semiconductor tariff", "chip tariff", "tech tariff",
    "agriculture tariff", "farm tariff", "soybean tariff",
    "canada tariff", "mexico tariff",
    "universal tariff", "baseline tariff",
    "decoupling", "nearshoring", "reshoring", "friendshoring",
    "refund tariff", "tariff refund",
    "tariff rate", "tariff level",
    "duties on", "duty on",
]

TARIFF_SUBTOPICS = {
    "China Tariffs": ["china", "chinese", "beijing"],
    "EU / Europe Tariffs": ["eu ", "european", "europe", "brussels", "germany", "france"],
    "Canada / Mexico / USMCA": ["canada", "mexico", "usmca", "nafta", "canadian", "mexican"],
    "Auto / Automotive": ["auto", "car ", "vehicle", "automotive"],
    "Steel / Aluminum / Metals": ["steel", "aluminum", "metal"],
    "Semiconductors / Tech": ["semiconductor", "chip", "tech", "electronic"],
    "Agriculture / Food": ["agriculture", "farm", "soybean", "corn", "food", "grain"],
    "Universal / Reciprocal": ["universal", "reciprocal", "baseline", "across-the-board", "blanket"],
    "Trade Deals / Negotiations": ["deal", "negotiation", "agreement", "resolution", "talks", "wto"],
    "Sector-Specific Tariffs": ["section 301", "section 232", "duty", "duties"],
}

SPORTS_EXCLUSIONS = [
    "fifa", "world cup", "premier league", "champions league",
    "nba", "nfl", "mlb", "nhl", "mma", "ufc",
    "tennis", "australian open", "french open", "wimbledon", "us open tennis",
    "golf", "masters tournament", "pga",
    "cricket", "rugby", "formula 1",
    "super bowl", "stanley cup", "world series",
    "home run", "touchdown", "goal scorer", "rushing yards",
    "eurovision", "oscars", "grammy", "emmy",
]

PROGRESS_EVERY_S = 5.0


def _matches_tariff(title, event_title=""):
    combined = (title + " " + event_title).lower()
    if any(ex in combined for ex in SPORTS_EXCLUSIONS):
        return False
    return any(kw in combined for kw in TARIFF_KEYWORDS)


def _classify_subtopic(title, event_title=""):
    combined = (title + " " + event_title).lower()
    for subtopic, keywords in TARIFF_SUBTOPICS.items():
        if any(kw in combined for kw in keywords):
            return subtopic
    return "General Trade / Tariff"


def _fetch_tariff_markets():
    """Pull all events from both platforms, filter to tariff-related."""
    print("  Fetching Kalshi events...")
    t0 = time.time()
    kalshi_events = kalshi_get_all_events(status="open")
    print(f"  {len(kalshi_events)} Kalshi events ({time.time()-t0:.1f}s)")

    print("  Fetching Polymarket events...")
    t1 = time.time()
    poly_events = poly_get_all_events(active=True, min_volume=1000)
    print(f"  {len(poly_events)} Polymarket events ({time.time()-t1:.1f}s)")

    records = []
    for event in kalshi_events:
        markets = event.get("markets", [])
        for m in markets:
            rec = kalshi_extract_market_record(m, event)
            if _matches_tariff(rec["title"], rec.get("event_title", "")):
                rec["subtopic"] = _classify_subtopic(rec["title"], rec.get("event_title", ""))
                records.append(rec)

    for event in poly_events:
        markets = event.get("markets", [])
        for m in markets:
            rec = poly_extract_market_record(m, event)
            if _matches_tariff(rec["title"], rec.get("event_title", "")):
                rec["subtopic"] = _classify_subtopic(rec["title"], rec.get("event_title", ""))
                records.append(rec)

    records.sort(key=lambda r: _safe_volume(r.get("volume")), reverse=True)
    return records


def _fetch_histories(records, top_n=15, days_back=90):
    """Fetch daily price histories for the top N tariff markets by volume."""
    histories = {}
    count = 0
    last_progress = time.time()

    for rec in records:
        if count >= top_n:
            break
        mid = rec["market_id"]
        source = rec["source"]
        if mid in histories:
            continue

        now = time.time()
        if now - last_progress >= PROGRESS_EVERY_S:
            print(f"  [{count+1}/{top_n}] Fetching: {rec['title'][:65]}...")
            last_progress = now

        if source == "kalshi":
            candles = kalshi_get_candlesticks(mid, period_minutes=1440, days_back=days_back)
            if candles:
                histories[mid] = {
                    "source": "kalshi",
                    "market_id": mid,
                    "market_title": rec["title"],
                    "event_title": rec.get("event_title", ""),
                    "subtopic": rec.get("subtopic", ""),
                    "series": [
                        {"timestamp": _ts_to_iso(c.get("end_period_ts")), "yes_price": c.get("close") or c.get("yes_price")}
                        for c in candles
                    ],
                }
                count += 1

        elif source == "polymarket":
            token_ids = rec.get("clob_token_ids", [])
            if token_ids:
                history = poly_get_price_history(token_ids[0])
                if history:
                    histories[mid] = {
                        "source": "polymarket",
                        "market_id": mid,
                        "market_title": rec["title"],
                        "event_title": rec.get("event_title", ""),
                        "subtopic": rec.get("subtopic", ""),
                        "series": [
                            {"timestamp": _ts_to_iso(h.get("t")), "yes_price": h.get("p")}
                            for h in history
                        ],
                    }
                    count += 1

        time.sleep(0.15)

    return histories


def _print_market_table(records, limit=30):
    if not records:
        print("  (no tariff-related markets found)")
        return
    hdr = f"  {'Prob':>5s}  {'Volume':>12s}  {'Src':4s}  {'Subtopic':28s}  Title"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in records[:limit]:
        prob = r.get("yes_price")
        try:
            prob = float(prob) if prob is not None else None
        except (ValueError, TypeError):
            prob = None
        prob_str = f"{prob:.0%}" if prob is not None else "  ? "
        vol = _safe_volume(r.get("volume"))
        vol_str = f"${vol:,.0f}" if vol else "$0"
        src = r["source"][:4]
        subtopic = r.get("subtopic", "")[:28]
        title = r["title"][:68]
        print(f"  {prob_str:>5s}  {vol_str:>12s}  {src:4s}  {subtopic:28s}  {title}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_dashboard(output_json=False):
    """Full Tariff Monitor dashboard."""
    print("\n" + "=" * 80)
    print("  TARIFF MONITOR -- Prediction Market Surveillance")
    print("=" * 80)

    print("\n[1/3] Pulling tariff-related markets from Kalshi + Polymarket...")
    records = _fetch_tariff_markets()
    print(f"  Found {len(records)} tariff-related markets")

    if not records:
        print("  No tariff-related markets found.")
        return

    by_subtopic = defaultdict(list)
    for r in records:
        by_subtopic[r.get("subtopic", "General")].append(r)

    total_vol = sum(_safe_volume(r.get("volume")) for r in records)
    kalshi_count = len([r for r in records if r["source"] == "kalshi"])
    poly_count = len([r for r in records if r["source"] == "polymarket"])

    def _float_price(r):
        try:
            return float(r["yes_price"]) if r.get("yes_price") is not None else None
        except (ValueError, TypeError):
            return None
    high_prob = [r for r in records if (_float_price(r) or 0) >= 0.70]
    low_prob = [r for r in records if _float_price(r) is not None and _float_price(r) <= 0.30]

    print(f"\n[2/3] Summary")
    print(f"  Total markets:         {len(records)} (Kalshi: {kalshi_count}, Polymarket: {poly_count})")
    print(f"  Total volume:          ${total_vol:,.0f}")
    print(f"  Subtopics:             {len(by_subtopic)}")
    print(f"  High conviction (>70%): {len(high_prob)} markets")
    print(f"  Low probability (<30%): {len(low_prob)} markets")

    print(f"\n[3/3] Markets by subtopic\n")
    for subtopic in sorted(by_subtopic.keys(), key=lambda s: -sum(_safe_volume(r.get("volume")) for r in by_subtopic[s])):
        bucket = by_subtopic[subtopic]
        bucket_vol = sum(_safe_volume(r.get("volume")) for r in bucket)
        probs = []
        for r in bucket:
            try:
                p = float(r["yes_price"]) if r.get("yes_price") is not None else None
            except (ValueError, TypeError):
                p = None
            if p is not None:
                probs.append(p)
        avg_prob = sum(probs) / len(probs) if probs else 0
        print(f"  --- {subtopic} ({len(bucket)} markets, ${bucket_vol:,.0f} vol, avg prob {avg_prob:.0%}) ---")
        _print_market_table(bucket, limit=10)
        print()

    if output_json:
        payload = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "description": "Trade/tariff-related markets from Kalshi + Polymarket",
            "summary": {
                "total_markets": len(records),
                "kalshi_markets": kalshi_count,
                "polymarket_markets": poly_count,
                "total_volume_usd": total_vol,
                "subtopic_count": len(by_subtopic),
                "high_conviction_count": len(high_prob),
                "low_probability_count": len(low_prob),
            },
            "subtopics": {},
            "all_markets": [],
        }
        for subtopic, bucket in by_subtopic.items():
            bucket.sort(key=lambda r: _safe_volume(r.get("volume")), reverse=True)
            probs = []
            for r in bucket:
                try:
                    p = float(r["yes_price"]) if r.get("yes_price") is not None else None
                except (ValueError, TypeError):
                    p = None
                if p is not None:
                    probs.append(p)
            payload["subtopics"][subtopic] = {
                "market_count": len(bucket),
                "total_volume": sum(_safe_volume(r.get("volume")) for r in bucket),
                "avg_probability": sum(probs) / len(probs) if probs else None,
                "markets": [
                    {
                        "source": r["source"],
                        "market_id": r["market_id"],
                        "title": r["title"],
                        "event_title": r.get("event_title", ""),
                        "probability": r.get("yes_price"),
                        "volume": _safe_volume(r.get("volume")),
                    }
                    for r in bucket[:15]
                ],
            }
        for r in records:
            payload["all_markets"].append({
                "source": r["source"],
                "market_id": r["market_id"],
                "title": r["title"],
                "event_title": r.get("event_title", ""),
                "subtopic": r.get("subtopic", ""),
                "probability": r.get("yes_price"),
                "volume": _safe_volume(r.get("volume")),
                "close_time": r.get("close_time", ""),
            })
        print(json.dumps(payload, indent=2, default=str))


def cmd_search():
    """Discover tariff-related markets across both platforms."""
    print("\n" + "=" * 80)
    print("  TARIFF MARKET SEARCH")
    print("=" * 80)

    print("\n  Pulling markets...")
    records = _fetch_tariff_markets()
    print(f"  Found {len(records)} tariff-related markets\n")
    _print_market_table(records, limit=50)


def cmd_history(days_back=90, top_n=15, output_json=False):
    """Fetch price histories for top tariff markets, run shock detection."""
    print("\n" + "=" * 80)
    print("  TARIFF MARKETS -- Price History & Shock Detection")
    print("=" * 80)

    print("\n[1/3] Pulling tariff-related markets...")
    records = _fetch_tariff_markets()
    print(f"  Found {len(records)} markets")

    if not records:
        print("  No markets found.")
        return

    print(f"\n[2/3] Fetching daily price history for top {top_n} markets ({days_back}d)...")
    histories = _fetch_histories(records, top_n=top_n, days_back=days_back)
    print(f"  Got history for {len(histories)} markets")

    print(f"\n[3/3] Analysis\n")

    all_shocks = []
    all_regimes = []
    json_histories = {}

    for mid, hist in histories.items():
        title = hist.get("market_title", mid)
        subtopic = hist.get("subtopic", "")
        dates, prices = _extract_series(hist, truncate_to_date=True)
        if len(dates) < 3:
            continue

        first_p, last_p = prices[0], prices[-1]
        change = last_p - first_p

        shocks, daily_vol = detect_shocks(dates, prices, sigma_thresholds=(2.5, 4.0))
        regimes = detect_regime_shifts(dates, prices, min_shift_pp=8.0)
        vol_mean, vol_curr, vol_max, vol_max_date = compute_volatility_profile(dates, prices)

        print(f"  {title[:72]}")
        print(f"    [{subtopic}] {hist['source']}  |  {len(dates)} days  |  {first_p:.0%} -> {last_p:.0%} ({change:+.1%})")
        print(f"    Vol: mean={vol_mean:.1f}pp  current={vol_curr:.1f}pp  max={vol_max:.1f}pp ({vol_max_date})")
        if shocks:
            top_shock = shocks[0]
            print(f"    Biggest shock: {top_shock['change']:+.1%} on {top_shock['date']} ({top_shock['sigma']:.1f} sigma)")
        if regimes:
            latest = regimes[-1]
            print(f"    Latest regime shift: {latest['direction']} {latest['shift_pp']:+.1f}pp ({latest['start_date']} to {latest['end_date']})")
        print()

        for s in shocks:
            s["market"] = title
            s["subtopic"] = subtopic
        all_shocks.extend(shocks)

        for rg in regimes:
            rg["market"] = title
            rg["subtopic"] = subtopic
        all_regimes.extend(regimes)

        if output_json:
            json_histories[mid] = {
                "title": title,
                "subtopic": subtopic,
                "source": hist["source"],
                "days": len(dates),
                "first_price": first_p,
                "last_price": last_p,
                "change": change,
                "vol_mean_pp": vol_mean,
                "vol_current_pp": vol_curr,
                "shocks": shocks[:5],
                "regime_shifts": regimes,
                "daily_series": [{"date": d, "price": p} for d, p in zip(dates, prices)],
            }

    all_shocks.sort(key=lambda s: s["sigma"], reverse=True)
    if all_shocks:
        print("  === TOP SHOCKS ACROSS ALL TARIFF MARKETS ===\n")
        for s in all_shocks[:10]:
            print(f"    {s['sigma']:5.1f}x  {s['change']:+.1%}  {s['date']}  {s['market'][:60]}")
        print()

    if output_json:
        payload = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "days_back": days_back,
            "markets_with_history": len(json_histories),
            "total_shocks": len(all_shocks),
            "total_regime_shifts": len(all_regimes),
            "top_shocks": all_shocks[:15],
            "histories": json_histories,
        }
        print(json.dumps(payload, indent=2, default=str))


def cmd_timeline(days_back=180, top_n=20, output_json=False):
    """Build a tariff repricing timeline: date-indexed view of what moved and when."""
    print("\n" + "=" * 80)
    print("  TARIFF REPRICING TIMELINE")
    print("=" * 80)

    print("\n[1/3] Pulling tariff-related markets...")
    records = _fetch_tariff_markets()
    print(f"  Found {len(records)} markets")

    if not records:
        print("  No markets found.")
        return

    print(f"\n[2/3] Fetching daily price history for top {top_n} markets ({days_back}d)...")
    histories = _fetch_histories(records, top_n=top_n, days_back=days_back)
    print(f"  Got history for {len(histories)} markets")

    print(f"\n[3/3] Building timeline\n")

    date_events = defaultdict(list)
    for mid, hist in histories.items():
        title = hist.get("market_title", mid)
        subtopic = hist.get("subtopic", "")
        dates, prices = _extract_series(hist, truncate_to_date=True)
        if len(dates) < 2:
            continue

        for i in range(1, len(dates)):
            chg = prices[i] - prices[i - 1]
            if abs(chg) >= 0.02:
                date_events[dates[i]].append({
                    "market": title,
                    "subtopic": subtopic,
                    "source": hist["source"],
                    "price_before": prices[i - 1],
                    "price_after": prices[i],
                    "change": chg,
                })

    timeline = []
    for date_key in sorted(date_events.keys()):
        moves = date_events[date_key]
        moves.sort(key=lambda x: abs(x["change"]), reverse=True)
        total_abs_move = sum(abs(m["change"]) for m in moves)
        timeline.append({
            "date": date_key,
            "move_count": len(moves),
            "total_abs_move": total_abs_move,
            "moves": moves[:10],
        })

    timeline.sort(key=lambda t: t["total_abs_move"], reverse=True)

    print(f"  {len(timeline)} days with tariff market moves (>= 2pp)\n")
    print(f"  {'Date':10s}  {'Moves':>5s}  {'TotalMove':>9s}  Top Market Move")
    print(f"  {'----------':10s}  {'-----':>5s}  {'---------':>9s}  ---------------")
    for day in timeline[:30]:
        top = day["moves"][0] if day["moves"] else None
        top_str = f"{top['change']:+.1%} {top['market'][:50]}" if top else ""
        print(f"  {day['date']:10s}  {day['move_count']:5d}  {day['total_abs_move']:8.1%}  {top_str}")

    if output_json:
        payload = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "days_back": days_back,
            "total_days_with_moves": len(timeline),
            "timeline": timeline[:50],
        }
        print("\n" + json.dumps(payload, indent=2, default=str))


# ── Interactive Menu ──────────────────────────────────────────────────────────

def interactive_menu():
    while True:
        print(f"\n{'=' * 50}")
        print(f"  TARIFF MONITOR")
        print(f"{'=' * 50}")
        print(f"    1. Dashboard (full overview)")
        print(f"    2. Search (discover markets)")
        print(f"    3. History (price trajectories + shocks)")
        print(f"    4. Timeline (tariff repricing episodes)")
        print(f"    q. Quit")
        print(f"{'=' * 50}")

        choice = input("\n  Select: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("  Done.")
            break
        elif choice in ("1", "dashboard"):
            cmd_dashboard()
        elif choice in ("2", "search"):
            cmd_search()
        elif choice in ("3", "history"):
            days = input("  Days back [90]: ").strip()
            days = int(days) if days else 90
            top = input("  Top N markets [15]: ").strip()
            top = int(top) if top else 15
            cmd_history(days_back=days, top_n=top)
        elif choice in ("4", "timeline"):
            days = input("  Days back [180]: ").strip()
            days = int(days) if days else 180
            top = input("  Top N markets [20]: ").strip()
            top = int(top) if top else 20
            cmd_timeline(days_back=days, top_n=top)
        else:
            print("  Invalid choice.")


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_argparse():
    parser = argparse.ArgumentParser(description="Tariff Monitor - prediction market surveillance")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("dashboard", help="Full tariff overview: subtopics, probabilities, volume")
    p.add_argument("--json", action="store_true", help="Output structured JSON")

    sub.add_parser("search", help="Discover all tariff-related markets")

    p = sub.add_parser("history", help="Price history + shock detection for top tariff markets")
    p.add_argument("--days-back", type=int, default=90)
    p.add_argument("--top-n", type=int, default=15)
    p.add_argument("--json", action="store_true", help="Output structured JSON")

    p = sub.add_parser("timeline", help="Tariff repricing timeline: date-indexed moves")
    p.add_argument("--days-back", type=int, default=180)
    p.add_argument("--top-n", type=int, default=20)
    p.add_argument("--json", action="store_true", help="Output structured JSON")

    return parser


def main():
    parser = build_argparse()
    args = parser.parse_args()

    if args.command == "dashboard":
        cmd_dashboard(output_json=args.json)
    elif args.command == "search":
        cmd_search()
    elif args.command == "history":
        cmd_history(days_back=args.days_back, top_n=args.top_n, output_json=args.json)
    elif args.command == "timeline":
        cmd_timeline(days_back=args.days_back, top_n=args.top_n, output_json=args.json)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
