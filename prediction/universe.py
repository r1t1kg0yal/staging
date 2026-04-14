#!/usr/bin/env python3
"""
Prediction Markets Universe Analysis
=====================================

Pulls the FULL active universe from Kalshi and Polymarket public APIs and
produces structural analysis: total market counts, volume distributions,
concentration metrics, category breakdowns, and a macro-filtered state-of-
prediction-markets view.

Two complementary tools in this directory:
  prediction_markets_scraper.py  -- operational: autopilot briefings, price history, change detection
  universe.py (this file)        -- structural: landscape analysis, volume skew, macro filtering

APIs (same as scraper, no auth required):
  Kalshi:      https://api.elections.kalshi.com/trade-api/v2
  Polymarket:  https://gamma-api.polymarket.com
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

# ── Constants ─────────────────────────────────────────────────────────────────

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
POLY_GAMMA = "https://gamma-api.polymarket.com"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json", "User-Agent": "prediction-markets-universe/1.0"})

KALSHI_MACRO_CATEGORIES = {"economics", "politics", "world", "finance", "climate", "tech"}
KALSHI_NON_MACRO_CATEGORIES = {"sports", "entertainment", "mentions"}

POLYMARKET_MACRO_TAGS = {
    "politics", "elections", "global elections", "business",
    "science", "midterms",
}
POLYMARKET_NON_MACRO_TAGS = {
    "sports", "games", "soccer", "pop culture", "hype",
    "nfl", "nba", "mlb", "nhl", "mma", "tennis", "golf",
    "formula 1", "cricket", "rugby",
}

MACRO_KEYWORDS = [
    "fed ", "fomc", "rate cut", "rate hike", "interest rate",
    "inflation", "cpi", "gdp", "recession",
    "tariff", "trade war", "trade deal", "trade policy",
    "china", "iran", "russia", "ukraine", "war ",
    "oil", "opec", "nato", "nuclear", "sanctions", "ceasefire",
    "trump", "biden", "election", "congress", "debt ceiling",
    "treasury", "yield", "s&p", "nasdaq", "bitcoin", "crypto",
    "unemployment", "jobs report", "nonfarm", "pmi", "ism",
    "default", "shutdown", "stimulus", "qe", "qt",
    "israel", "gaza", "hamas", "hezbollah", "taiwan",
    "regulation", "antitrust",
    "supreme court", "impeach", "indictment",
    "pope", "vatican",
    "immigration", "border wall", "fbi", "doj",
    "debt", "deficit", "spending", "budget",
    "climate change", "carbon", "emissions",
    "semiconductor", "chip act",
    "gold price", "commodity",
    "housing market", "mortgage rate",
    "pandemic", "vaccine", "outbreak",
    "drone strike", "missile", "military",
    "senate", "governor race",
    "approval rating", "favorability",
    "ai regulation", "artificial intelligence",
    "fed funds", "monetary policy", "central bank",
    "regime", "coup", "invasion", "annex",
    "eu sanctions", "european union",
    "north korea", "south china sea",
]

MACRO_EXCLUSIONS = [
    "fifa", "world cup", "premier league", "champions league",
    "nba", "nfl", "mlb", "nhl", "mma", "ufc",
    "tennis", "golf", "masters tournament",
    "cricket", "rugby", "formula 1", "f1 ",
    "super bowl", "stanley cup", "world series",
    "oscars", "grammy", "emmy", "tony award",
    "bachelor", "bachelorette", "love island",
    "tiktok followers", "youtube", "twitch",
    "box office", "movie", "album",
    "home run", "touchdown", "goal scorer",
    "batting average", "rushing yards",
    "win the 2025", "win the 2026",
]

MEME_MARKET_PATTERNS = [
    "will jesus christ", "will aliens",
    "will elon musk visit mars",
    "humans colonize mars",
    "supervolcano",
]

MACRO_TOPIC_BUCKETS = {
    "Federal Reserve & Monetary Policy": ["fed ", "fed's", "fomc", "rate cut", "rate hike", "interest rate", "monetary policy", "powell", "fed chair", "fed decrease", "fed increase", "fed funds"],
    "Inflation & Economic Data": ["inflation", "cpi", "pce", "gdp", "recession", "unemployment", "jobs report", "nonfarm", "pmi", "ism", "housing market", "mortgage rate", "consumer confidence", "retail sales"],
    "Trade & Tariffs": ["tariff", "trade war", "trade deal", "trade policy", "trade deficit"],
    "US Politics & Elections": ["election", "senate", "house ", "congress", "governor", "approval rating", "midterm", "primary", "nominee", "presidential", "speaker", "caucus", "ballot"],
    "US Policy: Executive Branch": ["trump", "executive order", "doj", "fbi", "indictment", "impeach", "pardon", "executive action", "white house", "cabinet"],
    "Geopolitics: Iran & Middle East": ["iran", "israel", "gaza", "hamas", "hezbollah", "ceasefire", "middle east", "netanyahu", "knesset", "tehran", "ayatollah", "pahlavi", "irgc"],
    "Geopolitics: Russia & Ukraine": ["russia", "ukraine", "putin", "zelensky", "kremlin", "donbas", "crimea"],
    "Geopolitics: China & Taiwan": ["china", "taiwan", "xi jinping", "beijing", "south china sea"],
    "Crypto & Digital Assets": ["bitcoin", "crypto", "ethereum", "btc", "eth ", "microstrategy", "stablecoin", "defi"],
    "Energy & Commodities": ["oil", "opec", "energy", "natural gas", "gold", "silver", "copper", "commodity", "wti", "brent"],
    "Financial Markets": ["s&p", "nasdaq", "dow jones", "stock market", "yield", "bond", "treasury", "vix", "downturn", "market crash"],
    "Climate & Environment": ["climate", "carbon", "emissions", "hurricane", "wildfire", "named storm"],
    "Technology & AI": ["ai ", "artificial intelligence", "semiconductor", "chip act", "antitrust", "tech layoff", "layoff", "big tech"],
    "Global & Misc Geopolitics": ["pope", "vatican", "european union", "korea", "japan", "india", "saudi", "turkey", "mexico", "nuclear", "nato", "sanctions", "military", "missile", "drone", "venezuela", "grenell", "cuba", "brazil", "hungary", "prime minister"],
    "Fiscal & Debt": ["debt ceiling", "deficit", "spending", "budget", "shutdown", "default", "fiscal"],
    "Health & Pandemic": ["pandemic", "vaccine", "outbreak", "bird flu", "h5n1", "mpox"],
}

VOLUME_THRESHOLDS = [0, 100, 1_000, 5_000, 10_000, 25_000, 50_000, 100_000,
                     250_000, 500_000, 1_000_000, 5_000_000, 10_000_000,
                     50_000_000, 100_000_000]

TOP_N_BUCKETS = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]


# ── API Pulls ─────────────────────────────────────────────────────────────────

def pull_kalshi_events(status="open"):
    """Paginate through all Kalshi events with nested markets."""
    all_events = []
    cursor = None
    page = 0
    while True:
        params = {"limit": 200, "status": status, "with_nested_markets": "true"}
        if cursor:
            params["cursor"] = cursor
        resp = SESSION.get(f"{KALSHI_BASE}/events", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        all_events.extend(events)
        page += 1
        n_mkts = sum(len(e.get("markets", [])) for e in events)
        print(f"  [Kalshi] page {page}: {len(events)} events, {n_mkts} markets (total: {len(all_events)} events)")
        cursor = data.get("cursor")
        if not events or not cursor:
            break
        time.sleep(0.05)
    return all_events


def pull_polymarket_events(active=True):
    """Paginate through all Polymarket events (no volume filter)."""
    all_events = []
    offset = 0
    page = 0
    while True:
        params = {
            "limit": 100,
            "offset": offset,
            "active": str(active).lower(),
            "closed": "false" if active else "true",
            "order": "volume",
            "ascending": "false",
        }
        resp = SESSION.get(f"{POLY_GAMMA}/events", params=params, timeout=30)
        resp.raise_for_status()
        events = resp.json()
        if isinstance(events, dict):
            events = events.get("data", events.get("events", []))
        if not events:
            break
        all_events.extend(events)
        page += 1
        n_mkts = sum(len(e.get("markets", [])) or 1 for e in events)
        print(f"  [Polymarket] page {page}: {len(events)} events, {n_mkts} markets (total: {len(all_events)} events)")
        if len(events) < 100:
            break
        offset += 100
        time.sleep(0.1)
    return all_events


# ── Normalization ─────────────────────────────────────────────────────────────

def _safe_float(v, default=0.0):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _extract_poly_tags(event):
    tags = event.get("tags", [])
    if not tags:
        return []
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            return []
    result = []
    for t in tags:
        if isinstance(t, dict):
            result.append(t.get("label", t.get("name", str(t))).strip())
        else:
            result.append(str(t).strip())
    return result


def normalize_kalshi(raw_events):
    """Flatten Kalshi events -> list of normalized market dicts."""
    markets = []
    for ev in raw_events:
        cat = ev.get("category", "unknown").lower().strip()
        ev_title = ev.get("title", "")
        for m in ev.get("markets", []):
            markets.append({
                "source": "kalshi",
                "market_id": m.get("ticker", ""),
                "event_id": ev.get("event_ticker", ""),
                "title": m.get("title", ""),
                "event_title": ev_title,
                "category": cat,
                "tags": [],
                "volume": _safe_float(m.get("volume_fp") or m.get("volume")),
                "volume_24h": _safe_float(m.get("volume_24h_fp")),
                "open_interest": _safe_float(m.get("open_interest_fp") or m.get("open_interest")),
                "liquidity": _safe_float(m.get("liquidity_dollars")),
                "yes_price": _safe_float(m.get("last_price_dollars") or m.get("last_price")),
                "close_time": m.get("close_time", ""),
                "status": m.get("status", ""),
            })
    return markets


def normalize_polymarket(raw_events):
    """Flatten Polymarket events -> list of normalized market dicts."""
    markets = []
    for ev in raw_events:
        ev_title = ev.get("title", "")
        ev_tags = _extract_poly_tags(ev)
        mkts = ev.get("markets", [])
        if not mkts:
            mkts = [ev]
        for m in mkts:
            prices = m.get("outcomePrices", "[]")
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except Exception:
                    prices = []
            yes_price = _safe_float(prices[0]) if prices else 0.0

            markets.append({
                "source": "polymarket",
                "market_id": m.get("id", ""),
                "event_id": ev.get("id", ""),
                "title": m.get("question", m.get("title", "")),
                "event_title": ev_title,
                "category": "",
                "tags": ev_tags,
                "volume": _safe_float(m.get("volume") or m.get("volumeNum")),
                "volume_24h": _safe_float(m.get("volume24hr")),
                "open_interest": _safe_float(m.get("openInterest")),
                "liquidity": _safe_float(m.get("liquidity")),
                "yes_price": yes_price,
                "close_time": m.get("endDate", ""),
                "status": "active" if m.get("active") else "closed",
            })
    return markets


# ── Filtering ─────────────────────────────────────────────────────────────────

def _is_macro_relevant(market):
    """Check if a market is macro/econ/politics/geopolitics relevant.

    Three-pass filter:
      1. Exclude obvious sports/entertainment via MACRO_EXCLUSIONS
      2. Exclude meme markets via MEME_MARKET_PATTERNS
      3. Include if keyword match OR macro category/tag
    """
    text = f"{market['title']} {market['event_title']}".lower()

    if any(ex in text for ex in MACRO_EXCLUSIONS):
        return False
    if any(pat in text for pat in MEME_MARKET_PATTERNS):
        return False

    # 2028/2032 novelty candidate markets: "Will [X] win the 20XX presidential..."
    # at <=5% probability are meme markets (LeBron, Kim K, MrBeast, etc.)
    # Real frontrunners (Vance, DeSantis, Newsom) will be >5%
    if "presidential" in text and market["yes_price"] <= 0.05:
        import re
        if re.search(r"will .+ win the 20\d{2}", text):
            return False

    if market["source"] == "kalshi":
        if market["category"] in KALSHI_NON_MACRO_CATEGORIES:
            return False
    if market["source"] == "polymarket":
        tags_lower = {t.lower() for t in market["tags"]}
        if tags_lower & POLYMARKET_NON_MACRO_TAGS:
            return False

    if any(kw in text for kw in MACRO_KEYWORDS):
        return True
    if market["source"] == "kalshi" and market["category"] in KALSHI_MACRO_CATEGORIES:
        return True
    if market["source"] == "polymarket":
        tags_lower = {t.lower() for t in market["tags"]}
        if tags_lower & POLYMARKET_MACRO_TAGS:
            return True

    return False


def filter_macro(markets):
    return [m for m in markets if _is_macro_relevant(m)]


def classify_topic(market):
    """Assign a market to a macro topic bucket."""
    text = f"{market['title']} {market['event_title']}".lower()
    for bucket, keywords in MACRO_TOPIC_BUCKETS.items():
        if any(kw in text for kw in keywords):
            return bucket
    return "Other / Uncategorized"


# ── Statistics ────────────────────────────────────────────────────────────────

def gini(values):
    vals = sorted(values)
    n = len(vals)
    total = sum(vals)
    if n == 0 or total == 0:
        return 0.0
    cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(vals))
    return cum / (n * total)


def compute_stats(markets):
    """Compute summary statistics for a list of normalized markets."""
    n = len(markets)
    if n == 0:
        return {"count": 0}

    volumes = sorted([m["volume"] for m in markets], reverse=True)
    total_vol = sum(volumes)
    event_ids = {(m["source"], m["event_id"]) for m in markets}
    vol_24h = sum(m["volume_24h"] for m in markets)
    total_oi = sum(m["open_interest"] for m in markets)
    total_liq = sum(m["liquidity"] for m in markets)

    nonzero = [v for v in volumes if v > 0]

    concentration = []
    for top_n in TOP_N_BUCKETS:
        if top_n > n:
            break
        cum = sum(volumes[:top_n])
        concentration.append({
            "top_n": top_n,
            "pct_markets": top_n / n * 100,
            "cumulative_vol": cum,
            "pct_vol": cum / total_vol * 100 if total_vol > 0 else 0,
        })

    thresholds = []
    for t in VOLUME_THRESHOLDS:
        above = [v for v in volumes if v >= t]
        vol_above = sum(above)
        thresholds.append({
            "threshold": t,
            "markets_above": len(above),
            "pct_count": len(above) / n * 100 if n > 0 else 0,
            "vol_above": vol_above,
            "pct_vol": vol_above / total_vol * 100 if total_vol > 0 else 0,
        })

    percentiles = {}
    for p in [99, 95, 90, 75, 50, 25, 10, 5, 1]:
        idx = max(0, int((1 - p / 100) * n) - 1)
        percentiles[f"p{p}"] = volumes[idx] if idx < n else 0

    return {
        "count": n,
        "event_count": len(event_ids),
        "total_volume": total_vol,
        "volume_24h": vol_24h,
        "total_open_interest": total_oi,
        "total_liquidity": total_liq,
        "mean_volume": total_vol / n,
        "median_volume": volumes[n // 2],
        "max_volume": volumes[0],
        "min_volume": volumes[-1],
        "nonzero_count": len(nonzero),
        "zero_count": n - len(nonzero),
        "pct_zero": (n - len(nonzero)) / n * 100,
        "gini": gini(volumes),
        "concentration": concentration,
        "thresholds": thresholds,
        "percentiles": percentiles,
    }


def compute_category_breakdown(markets):
    """Group markets by category/tags and compute per-group stats."""
    groups = defaultdict(list)
    for m in markets:
        if m["source"] == "kalshi":
            key = f"kalshi:{m['category']}"
        else:
            tags = m["tags"]
            if tags:
                for t in tags:
                    groups[f"poly:{t.lower()}"].append(m)
                continue
            key = "poly:untagged"
        groups[key].append(m)

    result = []
    for key, mkts in groups.items():
        vol = sum(m["volume"] for m in mkts)
        result.append({
            "group": key,
            "markets": len(mkts),
            "total_volume": vol,
            "mean_volume": vol / len(mkts) if mkts else 0,
            "nonzero": len([m for m in mkts if m["volume"] > 0]),
        })
    result.sort(key=lambda x: -x["total_volume"])
    return result


def compute_topic_breakdown(markets):
    """Classify macro-filtered markets into topic buckets."""
    buckets = defaultdict(list)
    for m in markets:
        topic = classify_topic(m)
        buckets[topic].append(m)

    result = []
    for topic, mkts in buckets.items():
        volumes = sorted([m["volume"] for m in mkts], reverse=True)
        total_vol = sum(volumes)
        top5 = sorted(mkts, key=lambda x: -x["volume"])[:5]
        result.append({
            "topic": topic,
            "markets": len(mkts),
            "total_volume": total_vol,
            "mean_volume": total_vol / len(mkts) if mkts else 0,
            "max_volume": volumes[0] if volumes else 0,
            "top_markets": [
                {"title": m["title"] or m["event_title"], "volume": m["volume"],
                 "yes_price": m["yes_price"], "source": m["source"]}
                for m in top5
            ],
        })
    result.sort(key=lambda x: -x["total_volume"])
    return result


# ── Display ───────────────────────────────────────────────────────────────────

def _fmt_vol(v):
    if v >= 1_000_000_000:
        return f"${v/1e9:.2f}B"
    if v >= 1_000_000:
        return f"${v/1e6:.1f}M"
    if v >= 1_000:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"


def _bar(pct, width=40):
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def print_overview(k_stats, p_stats):
    print(f"\n{'='*72}")
    print(f"  PREDICTION MARKETS UNIVERSE OVERVIEW")
    print(f"  {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*72}")

    def _row(label, k, p, fmt="d"):
        if fmt == "d":
            print(f"  {label:<28} {k:>16,}   {p:>16,}")
        elif fmt == "$":
            print(f"  {label:<28} {_fmt_vol(k):>16}   {_fmt_vol(p):>16}")
        elif fmt == "%":
            print(f"  {label:<28} {k:>15.1f}%   {p:>15.1f}%")
        elif fmt == "f":
            print(f"  {label:<28} {k:>16.3f}   {p:>16.3f}")

    print(f"\n  {'Metric':<28} {'Kalshi':>16}   {'Polymarket':>16}")
    print(f"  {'-'*28} {'-'*16}   {'-'*16}")
    _row("Events", k_stats["event_count"], p_stats["event_count"])
    _row("Markets", k_stats["count"], p_stats["count"])
    _row("Total Volume", k_stats["total_volume"], p_stats["total_volume"], "$")
    _row("24h Volume", k_stats["volume_24h"], p_stats["volume_24h"], "$")
    _row("Open Interest", k_stats["total_open_interest"], p_stats["total_open_interest"], "$")
    _row("Liquidity", k_stats["total_liquidity"], p_stats["total_liquidity"], "$")
    _row("Mean Vol/Market", k_stats["mean_volume"], p_stats["mean_volume"], "$")
    _row("Median Vol/Market", k_stats["median_volume"], p_stats["median_volume"], "$")
    _row("Max Single Market", k_stats["max_volume"], p_stats["max_volume"], "$")
    _row("Zero-Volume Markets", k_stats["zero_count"], p_stats["zero_count"])
    _row("% Zero-Volume", k_stats["pct_zero"], p_stats["pct_zero"], "%")
    _row("Gini (volume)", k_stats["gini"], p_stats["gini"], "f")

    combined_vol = k_stats["total_volume"] + p_stats["total_volume"]
    combined_mkts = k_stats["count"] + p_stats["count"]
    combined_events = k_stats["event_count"] + p_stats["event_count"]
    print(f"\n  Combined: {combined_events:,} events, {combined_mkts:,} markets, {_fmt_vol(combined_vol)} volume")


def print_distribution(stats, label):
    print(f"\n{'='*72}")
    print(f"  {label} - VOLUME DISTRIBUTION")
    print(f"{'='*72}")

    print(f"\n  Concentration (Top N -> % of total volume):")
    print(f"  {'Top N':>8} | {'% Mkts':>8} | {'Cum Vol':>14} | {'% Vol':>8} | Bar")
    print(f"  {'-'*8}-+-{'-'*8}-+-{'-'*14}-+-{'-'*8}-+-{'-'*42}")
    for c in stats["concentration"]:
        print(f"  {c['top_n']:>8,} | {c['pct_markets']:>7.1f}% | {_fmt_vol(c['cumulative_vol']):>14} | {c['pct_vol']:>7.1f}% | {_bar(c['pct_vol'])}")

    print(f"\n  Volume Thresholds:")
    print(f"  {'Threshold':>14} | {'# Above':>10} | {'% Mkts':>8} | {'Vol Above':>14} | {'% Vol':>8}")
    print(f"  {'-'*14}-+-{'-'*10}-+-{'-'*8}-+-{'-'*14}-+-{'-'*8}")
    for t in stats["thresholds"]:
        print(f"  {_fmt_vol(t['threshold']):>14} | {t['markets_above']:>10,} | {t['pct_count']:>7.1f}% | {_fmt_vol(t['vol_above']):>14} | {t['pct_vol']:>7.1f}%")

    print(f"\n  Percentiles:")
    for k, v in stats["percentiles"].items():
        print(f"    {k.upper():<5}: {_fmt_vol(v):>14}")


def print_categories(cat_breakdown, label):
    print(f"\n{'='*72}")
    print(f"  {label} - CATEGORY BREAKDOWN (by volume)")
    print(f"{'='*72}")
    print(f"  {'Category':<35} | {'Markets':>8} | {'Vol':>12} | {'Nonzero':>8}")
    print(f"  {'-'*35}-+-{'-'*8}-+-{'-'*12}-+-{'-'*8}")
    for c in cat_breakdown[:30]:
        print(f"  {c['group']:<35} | {c['markets']:>8,} | {_fmt_vol(c['total_volume']):>12} | {c['nonzero']:>8,}")


def print_macro_state(topic_breakdown, macro_stats):
    print(f"\n{'='*72}")
    print(f"  MACRO STATE OF PREDICTION MARKETS")
    print(f"  {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*72}")
    print(f"  Macro-relevant markets: {macro_stats['count']:,} ({macro_stats['count']/(macro_stats['count'] + 1)*100:.1f}% pass macro filter)")
    print(f"  Macro total volume:     {_fmt_vol(macro_stats['total_volume'])}")
    print(f"  Macro 24h volume:       {_fmt_vol(macro_stats['volume_24h'])}")

    for bucket in topic_breakdown:
        print(f"\n  --- {bucket['topic']} ---")
        print(f"      {bucket['markets']:,} markets | {_fmt_vol(bucket['total_volume'])} total volume")
        for tm in bucket["top_markets"]:
            prob = f"{tm['yes_price']:.0%}" if tm["yes_price"] else "n/a"
            print(f"        {prob:>5} | {_fmt_vol(tm['volume']):>10} | [{tm['source'][:4]}] {tm['title'][:65]}")


def print_top_markets(markets, n=30, label=""):
    sorted_m = sorted(markets, key=lambda x: -x["volume"])[:n]
    print(f"\n{'='*72}")
    print(f"  TOP {n} MARKETS BY VOLUME{' - ' + label if label else ''}")
    print(f"{'='*72}")
    print(f"  {'#':>4} | {'Source':<5} | {'Volume':>12} | {'Price':>6} | Title")
    print(f"  {'-'*4}-+-{'-'*5}-+-{'-'*12}-+-{'-'*6}-+-{'-'*45}")
    for i, m in enumerate(sorted_m, 1):
        title = m["title"] or m["event_title"]
        if len(title) > 55:
            title = title[:52] + "..."
        prob = f"{m['yes_price']:.0%}" if m["yes_price"] else "n/a"
        print(f"  {i:>4} | {m['source'][:5]:<5} | {_fmt_vol(m['volume']):>12} | {prob:>6} | {title}")


# ── Core Pipeline ─────────────────────────────────────────────────────────────

def pull_universe(use_cache=False):
    """Pull full universe from both platforms. Returns (kalshi_markets, poly_markets)."""
    cache_path = os.path.join(DATA_DIR, "_universe_cache.json")

    if use_cache and os.path.exists(cache_path):
        print(f"  Loading cached universe from {cache_path}")
        with open(cache_path) as f:
            data = json.load(f)
        print(f"  Loaded {len(data['kalshi']):,} Kalshi + {len(data['polymarket']):,} Polymarket markets")
        return data["kalshi"], data["polymarket"]

    print("\n[1/4] Pulling Kalshi events...")
    k_raw = pull_kalshi_events()
    print(f"  -> {len(k_raw):,} Kalshi events")

    print("\n[2/4] Normalizing Kalshi markets...")
    k_markets = normalize_kalshi(k_raw)
    print(f"  -> {len(k_markets):,} Kalshi markets")

    print("\n[3/4] Pulling Polymarket events...")
    p_raw = pull_polymarket_events()
    print(f"  -> {len(p_raw):,} Polymarket events")

    print("\n[4/4] Normalizing Polymarket markets...")
    p_markets = normalize_polymarket(p_raw)
    print(f"  -> {len(p_markets):,} Polymarket markets")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump({
            "kalshi": k_markets,
            "polymarket": p_markets,
            "pulled_at": datetime.now(tz=timezone.utc).isoformat(),
        }, f, default=str)
    print(f"\n  Cached to {cache_path}")

    return k_markets, p_markets


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_overview(use_cache=False):
    """Full universe overview: counts, volumes, distribution, categories."""
    k_markets, p_markets = pull_universe(use_cache=use_cache)
    k_stats = compute_stats(k_markets)
    p_stats = compute_stats(p_markets)
    print_overview(k_stats, p_stats)
    print_distribution(k_stats, "KALSHI")
    print_distribution(p_stats, "POLYMARKET")
    cat_breakdown = compute_category_breakdown(k_markets + p_markets)
    print_categories(cat_breakdown, "COMBINED")
    return k_markets, p_markets, k_stats, p_stats


def cmd_macro(use_cache=False, top_n=30):
    """Macro-filtered state of prediction markets."""
    k_markets, p_markets = pull_universe(use_cache=use_cache)
    all_markets = k_markets + p_markets
    macro_markets = filter_macro(all_markets)
    macro_k = [m for m in macro_markets if m["source"] == "kalshi"]
    macro_p = [m for m in macro_markets if m["source"] == "polymarket"]

    print(f"\n  Universe: {len(all_markets):,} total markets")
    print(f"  Macro filter passed: {len(macro_markets):,} markets ({len(macro_markets)/len(all_markets)*100:.1f}%)")
    print(f"    Kalshi:      {len(macro_k):,} / {len(k_markets):,} ({len(macro_k)/max(len(k_markets),1)*100:.1f}%)")
    print(f"    Polymarket:  {len(macro_p):,} / {len(p_markets):,} ({len(macro_p)/max(len(p_markets),1)*100:.1f}%)")

    macro_stats = compute_stats(macro_markets)
    topic_breakdown = compute_topic_breakdown(macro_markets)
    print_macro_state(topic_breakdown, macro_stats)
    print_distribution(macro_stats, "MACRO-FILTERED")
    print_top_markets(macro_markets, n=top_n, label="MACRO")
    return macro_markets, macro_stats, topic_breakdown


def cmd_distribution(use_cache=False):
    """Deep dive on volume distribution for both platforms."""
    k_markets, p_markets = pull_universe(use_cache=use_cache)
    k_stats = compute_stats(k_markets)
    p_stats = compute_stats(p_markets)
    print_distribution(k_stats, "KALSHI")
    print_distribution(p_stats, "POLYMARKET")
    combined_stats = compute_stats(k_markets + p_markets)
    print_distribution(combined_stats, "COMBINED")
    return k_stats, p_stats, combined_stats


def cmd_top(use_cache=False, n=50, macro_only=False):
    """Top N markets by volume."""
    k_markets, p_markets = pull_universe(use_cache=use_cache)
    all_markets = k_markets + p_markets
    if macro_only:
        all_markets = filter_macro(all_markets)
    print_top_markets(all_markets, n=n, label="MACRO" if macro_only else "ALL")
    print_top_markets([m for m in (k_markets if not macro_only else filter_macro(k_markets))],
                      n=min(n, 20), label="KALSHI" + (" MACRO" if macro_only else ""))
    print_top_markets([m for m in (p_markets if not macro_only else filter_macro(p_markets))],
                      n=min(n, 20), label="POLYMARKET" + (" MACRO" if macro_only else ""))


def cmd_categories(use_cache=False):
    """Category/tag breakdown by volume."""
    k_markets, p_markets = pull_universe(use_cache=use_cache)
    k_cats = compute_category_breakdown(k_markets)
    p_cats = compute_category_breakdown(p_markets)
    print_categories(k_cats, "KALSHI")
    print_categories(p_cats, "POLYMARKET")


def cmd_export(use_cache=False, macro_only=False):
    """Export universe data as JSON for downstream analysis."""
    k_markets, p_markets = pull_universe(use_cache=use_cache)
    all_markets = k_markets + p_markets
    if macro_only:
        all_markets = filter_macro(all_markets)
        for m in all_markets:
            m["topic"] = classify_topic(m)

    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M")
    suffix = "_macro" if macro_only else ""
    path = os.path.join(DATA_DIR, f"universe{suffix}_{ts}.json")

    stats = compute_stats(all_markets)
    output = {
        "pulled_at": datetime.now(tz=timezone.utc).isoformat(),
        "macro_only": macro_only,
        "stats": stats,
        "markets": all_markets,
    }
    if macro_only:
        output["topic_breakdown"] = compute_topic_breakdown(all_markets)

    with open(path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Exported {len(all_markets):,} markets to {path}")
    print(f"  File size: {os.path.getsize(path):,} bytes")
    return path


# ── CLI ───────────────────────────────────────────────────────────────────────

def _ask_int(prompt, default):
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _ask_yn(prompt, default=True):
    d = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{d}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def interactive_loop():
    MENU = """
  Prediction Markets Universe Analysis
  =====================================

  Commands:
    1) overview      Full universe: counts, volumes, distribution, categories
    2) macro         Macro-filtered state (econ/politics/geopolitics/finance)
    3) distribution  Deep dive on volume skew for both platforms
    4) top           Top N markets by volume
    5) categories    Category/tag breakdown
    6) export        Export universe data as JSON
    q) quit
"""
    cache_available = os.path.exists(os.path.join(DATA_DIR, "_universe_cache.json"))

    while True:
        print(MENU)
        if cache_available:
            print("  [cache available -- will ask whether to use it]")
        choice = input("  > ").strip().lower()

        if choice in ("q", "quit", "exit"):
            break

        use_cache = False
        if cache_available and choice not in ("q", "quit", "exit"):
            use_cache = _ask_yn("  Use cached data?", True)

        if choice in ("1", "overview"):
            cmd_overview(use_cache=use_cache)

        elif choice in ("2", "macro"):
            top_n = _ask_int("  Top N markets to show", 30)
            cmd_macro(use_cache=use_cache, top_n=top_n)

        elif choice in ("3", "distribution"):
            cmd_distribution(use_cache=use_cache)

        elif choice in ("4", "top"):
            n = _ask_int("  How many top markets", 50)
            macro_only = _ask_yn("  Macro-only filter?", False)
            cmd_top(use_cache=use_cache, n=n, macro_only=macro_only)

        elif choice in ("5", "categories"):
            cmd_categories(use_cache=use_cache)

        elif choice in ("6", "export"):
            macro_only = _ask_yn("  Macro-only filter?", False)
            cmd_export(use_cache=use_cache, macro_only=macro_only)

        else:
            print(f"  Unknown command: {choice}")

        cache_available = os.path.exists(os.path.join(DATA_DIR, "_universe_cache.json"))


def build_argparse():
    parser = argparse.ArgumentParser(
        description="Prediction Markets Universe Analysis - structural landscape analysis for Kalshi + Polymarket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    for name, help_text in [
        ("overview", "Full universe: counts, volumes, distribution, categories"),
        ("macro", "Macro-filtered state (econ/politics/geopolitics/finance)"),
        ("distribution", "Deep dive on volume skew for both platforms"),
        ("top", "Top N markets by volume"),
        ("categories", "Category/tag breakdown"),
        ("export", "Export universe data as JSON"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--cache", action="store_true", help="Use cached universe data instead of re-pulling")

    sub.choices["macro"].add_argument("--top-n", type=int, default=30, help="Number of top markets to display (default: 30)")
    sub.choices["top"].add_argument("-n", type=int, default=50, help="Number of top markets (default: 50)")
    sub.choices["top"].add_argument("--macro", action="store_true", help="Apply macro filter")
    sub.choices["export"].add_argument("--macro", action="store_true", help="Export macro-filtered only")

    return parser


def run_noninteractive(args):
    if args.command == "overview":
        cmd_overview(use_cache=args.cache)
    elif args.command == "macro":
        cmd_macro(use_cache=args.cache, top_n=args.top_n)
    elif args.command == "distribution":
        cmd_distribution(use_cache=args.cache)
    elif args.command == "top":
        cmd_top(use_cache=args.cache, n=args.n, macro_only=args.macro)
    elif args.command == "categories":
        cmd_categories(use_cache=args.cache)
    elif args.command == "export":
        cmd_export(use_cache=args.cache, macro_only=args.macro)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = build_argparse()
        args = parser.parse_args()
        if args.command:
            run_noninteractive(args)
        else:
            parser.print_help()
    else:
        interactive_loop()
