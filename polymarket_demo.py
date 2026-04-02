#!/usr/bin/env python3
"""
Polymarket API Explorer: public market data (no API key for read-only flows).

Polymarket is the world's largest prediction market, built on Polygon (chain ID 137).

Three separate APIs, each with a different base URL and purpose:

  * Gamma API (https://gamma-api.polymarket.com) -- Primary market discovery API.
    Events, markets, tags, series, comments, search, sports, public profiles.
    Fully public, no auth. Rate limit: 4000 req/10s general, 500/10s for /events,
    300/10s for /markets.

  * Data API (https://data-api.polymarket.com) -- Analytics and position data.
    Wallet positions/trades/activity (lookup any address), leaderboards, holders,
    open interest. Fully public, no auth. Rate limit: 1000 req/10s general.

  * CLOB API (https://clob.polymarket.com) -- Central Limit Order Book.
    Orderbook depth, midpoint/market prices, spreads, tick sizes, fee rates,
    price history. Read endpoints are public (no auth). Trading endpoints need
    L1/L2 auth (not used here). Rate limit: 9000 req/10s general, 1500/10s for /book.

Data hierarchy: Events contain Markets. Each Market has two outcome tokens (YES/NO).
Token IDs are long integers (e.g. "85014971590839487...") used to query the CLOB.
The "condition ID" is the market's identifier across the Conditional Token Framework (CTF).

Pricing: outcome token prices range 0.00-1.00 representing implied probability.
Midpoint = avg(best bid, best ask). The two outcomes always sum to ~$1.00.

Slug: Human-readable URL identifier. From https://polymarket.com/event/fed-decision-in-october
the slug is "fed-decision-in-october". Use slugs for direct lookups.

WebSocket: wss://ws-subscriptions-clob.polymarket.com/ws/market provides real-time
orderbook updates, price changes, and trade notifications. No auth needed for market data.

Pagination: uses limit/offset parameters (not cursor-based like Kalshi).

Dependencies: pip install requests
Optional for streaming: pip install websocket-client
"""

import argparse
import json
import sys
import time
import datetime

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_BASE = "https://data-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
WS_MARKET = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


# ── HTTP / Display ──────────────────────────────────────────────────────────

def _get(base, path, params=None):
    r = requests.get(base + path, params=params, timeout=15)
    if r.status_code >= 400:
        print(f"  [!] HTTP {r.status_code}: {r.text[:300]}")
        return None
    try:
        return r.json()
    except Exception:
        return r.text


def _print_table(rows, headers):
    if not rows:
        print("  (no data)")
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))
    fmt = "  " + " | ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  " + "-+-".join("-" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*[str(v) for v in row]))


def _prompt(msg, default=""):
    suffix = f" [{default}]" if default else ""
    val = input(f"  {msg}{suffix}: ").strip()
    return val if val else default


def _trunc(s, n=50):
    s = str(s)
    return s[:n] + "..." if len(s) > n else s


# ── Gamma API - Events ──────────────────────────────────────────────────────

def cmd_list_events():
    """GET https://gamma-api.polymarket.com/events?active=true&closed=false&order={o}&ascending=false&limit={n}
    curl: curl "https://gamma-api.polymarket.com/events?active=true&closed=false&order=volume24hr&limit=20"
    Lists events (containers for related markets), sorted by the chosen field.
    Params: active (bool), closed (bool), order (volume24hr/volume/liquidity/startDate/endDate),
      ascending (bool), limit, offset, tag_id (filter by category tag)
    Each event includes its nested markets array with current prices and volumes.
    Response: [{id, title, slug, description, active, closed, markets: [...]}]"""
    print("\n== List Events ==")
    params = {"limit": 20, "active": "true", "closed": "false"}
    order = _prompt("Order by (volume24hr/volume/liquidity/startDate/endDate)", "volume24hr")
    params["order"] = order
    params["ascending"] = "false"
    tag_id = _prompt("Tag ID filter (empty for all)", "")
    if tag_id:
        params["tag_id"] = tag_id
    limit = _prompt("Limit", "20")
    params["limit"] = int(limit)
    data = _get(GAMMA_BASE, "/events", params=params)
    if not data:
        return
    if not isinstance(data, list):
        data = [data]
    rows = []
    for e in data:
        markets = e.get("markets", [])
        vol = ""
        if markets:
            vol = str(sum(float(m.get("volume", 0) or 0) for m in markets))[:12]
        rows.append([
            str(e.get("id", ""))[:10],
            _trunc(e.get("title", ""), 45),
            str(len(markets)),
            vol,
            str(e.get("active", "")),
        ])
    _print_table(rows, ["ID", "Title", "Mkts", "TotalVol", "Active"])
    print(f"\n  Returned: {len(data)} events")


def cmd_get_event_slug():
    """GET https://gamma-api.polymarket.com/events/slug/{slug}
    curl: curl https://gamma-api.polymarket.com/events/slug/fed-decision-in-october
    Fetches a single event by its URL slug (the path segment after /event/ on polymarket.com).
    Returns the full event object with all child markets, each containing their condition IDs,
    CLOB token IDs, outcome prices, volume, and liquidity.
    The clobTokenIds field is critical - these long integer IDs are what you pass to the CLOB API
    to get orderbook data, prices, spreads, etc."""
    print("\n== Get Event by Slug ==")
    slug = _prompt("Event slug (from polymarket URL e.g. fed-decision-in-october)")
    if not slug:
        return
    data = _get(GAMMA_BASE, f"/events/slug/{slug}")
    if not data:
        return
    print(f"  Title:       {data.get('title', 'N/A')}")
    print(f"  ID:          {data.get('id', 'N/A')}")
    print(f"  Description: {_trunc(data.get('description', ''), 100)}")
    print(f"  Active:      {data.get('active', 'N/A')}")
    print(f"  Closed:      {data.get('closed', 'N/A')}")
    print(f"  Start:       {data.get('startDate', 'N/A')}")
    print(f"  End:         {data.get('endDate', 'N/A')}")
    markets = data.get("markets", [])
    if markets:
        print(f"\n  Markets ({len(markets)}):")
        rows = []
        for m in markets:
            tokens = m.get("clobTokenIds", m.get("tokens", []))
            token_str = ""
            if isinstance(tokens, list) and tokens:
                if isinstance(tokens[0], dict):
                    token_str = tokens[0].get("token_id", "")[:20]
                else:
                    token_str = str(tokens[0])[:20]
            elif isinstance(tokens, str):
                token_str = tokens[:20]
            rows.append([
                str(m.get("id", ""))[:10],
                _trunc(m.get("question", m.get("groupItemTitle", "")), 40),
                str(m.get("outcomePrices", ""))[:20],
                str(m.get("volume", ""))[:12],
                token_str,
            ])
        _print_table(rows, ["ID", "Question", "Prices", "Volume", "TokenID"])


def cmd_get_event_id():
    """GET https://gamma-api.polymarket.com/events/{id}
    curl: curl https://gamma-api.polymarket.com/events/12345
    Fetches a single event by its numeric ID. Same response as the slug endpoint."""
    print("\n== Get Event by ID ==")
    eid = _prompt("Event ID")
    if not eid:
        return
    data = _get(GAMMA_BASE, f"/events/{eid}")
    if data:
        print(f"  Title:       {data.get('title', 'N/A')}")
        print(f"  Active:      {data.get('active', 'N/A')}")
        print(f"  Markets:     {len(data.get('markets', []))}")
        print(json.dumps(data, indent=2)[:2000])


# ── Gamma API - Markets ─────────────────────────────────────────────────────

def cmd_list_markets():
    """GET https://gamma-api.polymarket.com/markets?active=true&closed=false&order={o}&limit={n}
    curl: curl "https://gamma-api.polymarket.com/markets?active=true&closed=false&order=volume24hr&limit=20"
    Lists individual markets (each is a single binary question).
    Key response fields per market:
      question      - the binary question text
      outcomePrices - JSON string like '["0.65","0.35"]' for [YES_price, NO_price]
      volume        - total USDC volume traded
      volume24hr    - 24-hour volume
      clobTokenIds  - JSON string of two token IDs [YES_token, NO_token] for CLOB queries
      conditionId   - the market's CTF condition identifier"""
    print("\n== List Markets ==")
    params = {"limit": 20, "active": "true", "closed": "false"}
    order = _prompt("Order by (volume24hr/volume/liquidity)", "volume24hr")
    params["order"] = order
    params["ascending"] = "false"
    data = _get(GAMMA_BASE, "/markets", params=params)
    if not data:
        return
    if not isinstance(data, list):
        data = [data]
    rows = []
    for m in data:
        prices = m.get("outcomePrices", "")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                pass
        price_str = ""
        if isinstance(prices, list) and len(prices) >= 2:
            price_str = f"Y:{prices[0]} N:{prices[1]}"
        elif prices:
            price_str = str(prices)[:20]
        rows.append([
            str(m.get("id", ""))[:10],
            _trunc(m.get("question", ""), 40),
            price_str[:20],
            str(m.get("volume", ""))[:12],
            str(m.get("volume24hr", ""))[:10],
        ])
    _print_table(rows, ["ID", "Question", "Prices", "Volume", "Vol24h"])


def cmd_get_market_slug():
    """GET https://gamma-api.polymarket.com/markets/slug/{slug}
    curl: curl https://gamma-api.polymarket.com/markets/slug/fed-decision-in-october
    Fetches a single market by slug. Returns full market detail including outcomes,
    prices, volume, liquidity, and the CLOB token IDs needed for orderbook queries."""
    print("\n== Get Market by Slug ==")
    slug = _prompt("Market slug")
    if not slug:
        return
    data = _get(GAMMA_BASE, f"/markets/slug/{slug}")
    if data:
        print(f"  Question:     {data.get('question', 'N/A')}")
        print(f"  ID:           {data.get('id', 'N/A')}")
        print(f"  Condition ID: {data.get('conditionId', 'N/A')}")
        print(f"  Outcomes:     {data.get('outcomes', 'N/A')}")
        print(f"  Prices:       {data.get('outcomePrices', 'N/A')}")
        print(f"  Volume:       {data.get('volume', 'N/A')}")
        print(f"  Liquidity:    {data.get('liquidity', 'N/A')}")
        print(f"  Active:       {data.get('active', 'N/A')}")
        tokens = data.get("clobTokenIds", data.get("tokens", []))
        if tokens:
            print(f"  Token IDs:    {tokens}")


def cmd_get_market_id():
    """GET https://gamma-api.polymarket.com/markets/{id}
    curl: curl https://gamma-api.polymarket.com/markets/12345
    Fetches a single market by its numeric condition ID."""
    print("\n== Get Market by ID ==")
    mid = _prompt("Market ID (condition ID)")
    if not mid:
        return
    data = _get(GAMMA_BASE, f"/markets/{mid}")
    if data:
        print(f"  Question:   {data.get('question', 'N/A')}")
        print(f"  Prices:     {data.get('outcomePrices', 'N/A')}")
        print(f"  Volume:     {data.get('volume', 'N/A')}")
        tokens = data.get("clobTokenIds", data.get("tokens", []))
        if tokens:
            print(f"  Token IDs:  {tokens}")


def cmd_search():
    """GET https://gamma-api.polymarket.com/public-search?q={query}&limit={n}
    curl: curl "https://gamma-api.polymarket.com/public-search?q=bitcoin&limit=10"
    Full-text search across events, markets, and profiles. The 'q' parameter is required.
    Returns matching events with their nested markets. Rate limit: 350 req/10s."""
    print("\n== Search Markets/Events ==")
    query = _prompt("Search query")
    if not query:
        return
    data = _get(GAMMA_BASE, "/public-search", params={"q": query, "limit": 10})
    if not data:
        return
    events = data if isinstance(data, list) else data.get("events", data.get("results", []))
    if isinstance(events, list):
        rows = []
        for item in events[:15]:
            rows.append([
                str(item.get("id", ""))[:10],
                _trunc(item.get("title", item.get("question", "")), 50),
                str(item.get("volume", ""))[:12],
            ])
        _print_table(rows, ["ID", "Title/Question", "Volume"])
    else:
        print(json.dumps(data, indent=2)[:2000])


def cmd_price_history():
    """GET https://gamma-api.polymarket.com/prices-history?market={condition_id}&interval={i}&fidelity={n}
    curl: curl "https://gamma-api.polymarket.com/prices-history?market=CONDITION_ID&interval=1h&fidelity=100"
    Returns historical price time-series for a market (by condition ID, not token ID).
    Params: market (condition ID), interval (1m/5m/1h/6h/1d/1w), fidelity (max data points)
    Response: [{t: unix_timestamp, p: price_decimal}] - one entry per time bucket."""
    print("\n== Price History ==")
    market_id = _prompt("Market condition ID")
    if not market_id:
        return
    interval = _prompt("Interval (1m/5m/1h/6h/1d/1w)", "1h")
    fidelity = _prompt("Max data points", "100")
    params = {"market": market_id, "interval": interval, "fidelity": int(fidelity)}
    data = _get(GAMMA_BASE, "/prices-history", params=params)
    if not data:
        return
    if isinstance(data, list):
        print(f"  {len(data)} data points")
        for pt in data[:20]:
            print(f"    t={pt.get('t', '')}  p={pt.get('p', '')}")
        if len(data) > 20:
            print(f"    ... ({len(data) - 20} more)")
    elif isinstance(data, dict):
        history = data.get("history", data)
        if isinstance(history, list):
            print(f"  {len(history)} data points")
            for pt in history[:20]:
                print(f"    t={pt.get('t', '')}  p={pt.get('p', '')}")
        else:
            print(json.dumps(data, indent=2)[:2000])


# ── Gamma API - Tags / Series / Sports ──────────────────────────────────────

def cmd_list_tags():
    """GET https://gamma-api.polymarket.com/tags
    curl: curl https://gamma-api.polymarket.com/tags
    Returns all available tags used to categorize events/markets (e.g. "Politics", "Crypto",
    "Sports", "Science"). Each tag has an id, label, and slug. Use tag IDs to filter
    the /events endpoint via the tag_id parameter."""
    print("\n== Tags ==")
    data = _get(GAMMA_BASE, "/tags")
    if not data:
        return
    if isinstance(data, list):
        rows = []
        for t in data[:40]:
            rows.append([
                str(t.get("id", "")),
                t.get("label", t.get("name", t.get("slug", ""))),
                str(t.get("slug", "")),
            ])
        _print_table(rows, ["ID", "Label", "Slug"])
        print(f"\n  Total: {len(data)} tags")
    else:
        print(json.dumps(data, indent=2)[:2000])


def cmd_get_event_tags():
    """GET https://gamma-api.polymarket.com/events/{id}/tags
    curl: curl https://gamma-api.polymarket.com/events/12345/tags
    Returns the tags associated with a specific event."""
    print("\n== Event Tags ==")
    event_id = _prompt("Event ID")
    if not event_id:
        return
    data = _get(GAMMA_BASE, f"/events/{event_id}/tags")
    if data:
        print(json.dumps(data, indent=2)[:1000])


def cmd_list_series():
    """GET https://gamma-api.polymarket.com/series?limit={n}
    curl: curl "https://gamma-api.polymarket.com/series?limit=20"
    Series are recurring event templates (e.g. "Fed Rate Decision", "Weekly Bitcoin Price").
    Each series generates periodic events following the same structure."""
    print("\n== Series ==")
    data = _get(GAMMA_BASE, "/series", params={"limit": 20})
    if not data:
        return
    if isinstance(data, list):
        rows = []
        for s in data:
            rows.append([
                str(s.get("id", "")),
                _trunc(s.get("title", s.get("name", "")), 50),
                str(s.get("slug", "")),
            ])
        _print_table(rows, ["ID", "Title", "Slug"])
    else:
        print(json.dumps(data, indent=2)[:2000])


def cmd_sports_metadata():
    """GET https://gamma-api.polymarket.com/sports
    curl: curl https://gamma-api.polymarket.com/sports
    Returns metadata for all supported sports including tag IDs, images, resolution sources,
    and associated series. Covers NFL, NBA, MLB, NHL, soccer, and more."""
    print("\n== Sports Metadata ==")
    data = _get(GAMMA_BASE, "/sports")
    if not data:
        return
    if isinstance(data, list):
        for s in data[:15]:
            print(f"  {s.get('label', s.get('name', 'N/A')):30s}  id={s.get('id', '')}")
    else:
        print(json.dumps(data, indent=2)[:2000])


def cmd_sports_market_types():
    """GET https://gamma-api.polymarket.com/sports/market-types
    curl: curl https://gamma-api.polymarket.com/sports/market-types
    Returns the valid market type categories for sports markets (e.g. moneyline,
    spread, totals, player props, etc.)."""
    print("\n== Valid Sports Market Types ==")
    data = _get(GAMMA_BASE, "/sports/market-types")
    if data:
        print(json.dumps(data, indent=2)[:2000])


def cmd_list_comments():
    """GET https://gamma-api.polymarket.com/comments?market_slug={s}&event_slug={s}&limit={n}
    curl: curl "https://gamma-api.polymarket.com/comments?limit=10"
    Returns user comments on markets or events. Can filter by market_slug or event_slug.
    Each comment includes author info, content, like count, and timestamp."""
    print("\n== Comments ==")
    market_slug = _prompt("Market slug (optional)", "")
    event_slug = _prompt("Event slug (optional)", "")
    params = {"limit": 10}
    if market_slug:
        params["market_slug"] = market_slug
    if event_slug:
        params["event_slug"] = event_slug
    data = _get(GAMMA_BASE, "/comments", params=params)
    if not data:
        return
    comments = data if isinstance(data, list) else data.get("comments", [])
    for c in comments[:10]:
        author = c.get("author", c.get("user", {}))
        name = author.get("name", author.get("username", str(author)[:20])) if isinstance(author, dict) else str(author)[:20]
        print(f"  [{name}] {_trunc(c.get('content', c.get('body', c.get('text', ''))), 70)}")
        print(f"    Likes: {c.get('likes', c.get('likesCount', 'N/A'))}  |  {c.get('createdAt', c.get('timestamp', ''))[:19]}")
        print()


# ── CLOB API - Orderbook & Pricing ──────────────────────────────────────────

def cmd_clob_orderbook():
    """GET https://clob.polymarket.com/book?token_id={id}
    curl: curl "https://clob.polymarket.com/book?token_id=TOKEN_ID"
    Returns the full order book for a specific outcome token. Unlike Kalshi, Polymarket
    returns both bids AND asks since each outcome is a separate tradeable token.
      bids: [{price, size}] - orders to buy this outcome token (descending price)
      asks: [{price, size}] - orders to sell this outcome token (ascending price)
    Also returns: market (condition hash), last_trade_price, tick_size, neg_risk flag.
    The token_id is the long integer from the market's clobTokenIds array.
    Rate limit: 1500 req/10s for single book, 500/10s for batch."""
    print("\n== CLOB Orderbook ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    data = _get(CLOB_BASE, "/book", params={"token_id": token_id})
    if not data:
        return
    print(f"\n  Market: {data.get('market', 'N/A')}")
    print(f"  Asset:  {data.get('asset_id', 'N/A')}")
    bids = data.get("bids", [])
    asks = data.get("asks", [])
    print(f"\n  BIDS ({len(bids)} levels):")
    rows = []
    for b in bids[:15]:
        rows.append([str(b.get("price", "")), str(b.get("size", ""))])
    _print_table(rows, ["Price", "Size"])
    print(f"\n  ASKS ({len(asks)} levels):")
    rows = []
    for a in asks[:15]:
        rows.append([str(a.get("price", "")), str(a.get("size", ""))])
    _print_table(rows, ["Price", "Size"])
    print(f"\n  Last Trade: {data.get('last_trade_price', 'N/A')}")
    print(f"  Tick Size:  {data.get('tick_size', 'N/A')}")
    print(f"  Neg Risk:   {data.get('neg_risk', 'N/A')}")


def cmd_clob_midpoint():
    """GET https://clob.polymarket.com/midpoint?token_id={id}
    curl: curl "https://clob.polymarket.com/midpoint?token_id=TOKEN_ID"
    Returns the midpoint price for a token: avg(best_bid, best_ask).
    This is the most commonly used "current price" for a market outcome.
    Response: {mid: "0.55"} - a decimal string between 0 and 1."""
    print("\n== CLOB Midpoint Price ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    data = _get(CLOB_BASE, "/midpoint", params={"token_id": token_id})
    if data:
        print(f"  Midpoint: {data.get('mid', data.get('midpoint', data))}")


def cmd_clob_price():
    """GET https://clob.polymarket.com/price?token_id={id}&side={BUY|SELL}
    curl: curl "https://clob.polymarket.com/price?token_id=TOKEN_ID&side=BUY"
    Returns the best available price for a given side:
      BUY  -> best ask price (cheapest offer to sell to you)
      SELL -> best bid price (highest bid to buy from you)
    Response: {price: "0.55"}"""
    print("\n== CLOB Market Price ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    side = _prompt("Side (BUY/SELL)", "BUY")
    data = _get(CLOB_BASE, "/price", params={"token_id": token_id, "side": side})
    if data:
        print(f"  Price ({side}): {data.get('price', data)}")


def cmd_clob_spread():
    """GET https://clob.polymarket.com/spread?token_id={id}
    curl: curl "https://clob.polymarket.com/spread?token_id=TOKEN_ID"
    Returns the bid-ask spread: best_ask - best_bid.
    Tighter spreads indicate more liquid markets.
    Response: {spread: "0.02"}"""
    print("\n== CLOB Spread ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    data = _get(CLOB_BASE, "/spread", params={"token_id": token_id})
    if data:
        print(f"  Spread: {data.get('spread', data)}")


def cmd_clob_spreads():
    """GET https://clob.polymarket.com/spreads?token_ids={id1},{id2},...
    curl: curl "https://clob.polymarket.com/spreads?token_ids=TOKEN1,TOKEN2"
    Batch endpoint to get spreads for multiple tokens in one request."""
    print("\n== CLOB Spreads (Multiple) ==")
    ids_str = _prompt("Comma-separated token IDs")
    if not ids_str:
        return
    token_ids = [t.strip() for t in ids_str.split(",")]
    data = _get(CLOB_BASE, "/spreads", params={"token_ids": ",".join(token_ids)})
    if data:
        print(json.dumps(data, indent=2)[:2000])


def cmd_clob_last_trade():
    """GET https://clob.polymarket.com/last-trade-price?token_id={id}
    curl: curl "https://clob.polymarket.com/last-trade-price?token_id=TOKEN_ID"
    Returns the most recent trade price and which side initiated it.
    Defaults to price "0.5" and empty side if no trades have occurred.
    Response: {price: "0.55", side: "BUY"}"""
    print("\n== CLOB Last Trade Price ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    data = _get(CLOB_BASE, "/last-trade-price", params={"token_id": token_id})
    if data:
        print(f"  Last Price: {data.get('price', 'N/A')}")
        print(f"  Side:       {data.get('side', 'N/A')}")


def cmd_clob_tick_size():
    """GET https://clob.polymarket.com/tick-size/{token_id}
    curl: curl https://clob.polymarket.com/tick-size/TOKEN_ID
    Returns the minimum price increment for this market. Most markets use 0.01 (1 cent),
    but some high-activity markets use 0.001 for finer granularity.
    Response: {minimum_tick_size: "0.01"}"""
    print("\n== CLOB Tick Size ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    data = _get(CLOB_BASE, f"/tick-size/{token_id}")
    if data:
        print(f"  Tick Size: {data.get('minimum_tick_size', data)}")


def cmd_clob_fee_rate():
    """GET https://clob.polymarket.com/fee-rate/{token_id}
    curl: curl https://clob.polymarket.com/fee-rate/TOKEN_ID
    Returns the base fee rate for trading this token. Makers may receive rebates
    that reduce or eliminate fees. Takers pay the full rate.
    Response: {fee_rate: "0.02"}"""
    print("\n== CLOB Fee Rate ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    data = _get(CLOB_BASE, f"/fee-rate/{token_id}")
    if data:
        print(f"  Fee Rate: {data.get('fee_rate', data)}")


def cmd_clob_prices_history():
    """GET https://clob.polymarket.com/prices-history?market={token_id}&interval={i}&fidelity={n}
    curl: curl "https://clob.polymarket.com/prices-history?market=TOKEN_ID&interval=1h&fidelity=100"
    Returns historical price data from the CLOB (using token_id, not condition_id).
    Similar to the Gamma API prices-history but queried by token rather than condition.
    Params: market (token_id), interval (1m/5m/1h/1d), fidelity (max points)
    Response: {history: [{t: timestamp, p: price}]}"""
    print("\n== CLOB Prices History ==")
    token_id = _prompt("Token ID")
    if not token_id:
        return
    interval = _prompt("Interval (1m/5m/1h/1d)", "1h")
    fidelity = _prompt("Max data points", "100")
    params = {"market": token_id, "interval": interval, "fidelity": int(fidelity)}
    data = _get(CLOB_BASE, "/prices-history", params=params)
    if not data:
        return
    history = data.get("history", data) if isinstance(data, dict) else data
    if isinstance(history, list):
        print(f"  {len(history)} data points")
        for pt in history[:20]:
            print(f"    t={pt.get('t', '')}  p={pt.get('p', '')}")
        if len(history) > 20:
            print(f"    ... ({len(history) - 20} more)")
    else:
        print(json.dumps(data, indent=2)[:2000])


def cmd_clob_server_time():
    """GET https://clob.polymarket.com/time
    curl: curl https://clob.polymarket.com/time
    Returns the current CLOB server Unix timestamp. Useful for synchronizing local
    clocks with the exchange, which matters for order signing and time-sensitive operations."""
    print("\n== CLOB Server Time ==")
    data = _get(CLOB_BASE, "/time")
    if data:
        print(f"  Server timestamp: {data}")


# ── Data API - Public Analytics ──────────────────────────────────────────────

def cmd_lookup_positions():
    """GET https://data-api.polymarket.com/positions?user={address}&limit={n}&sizeThreshold=0
    curl: curl "https://data-api.polymarket.com/positions?user=0x...&limit=20&sizeThreshold=0"
    Looks up current open positions for ANY wallet address (public data on Polygon chain).
    Returns each position with its asset/token, size, average entry price, current value, and PnL.
    The sizeThreshold=0 includes dust positions; increase to filter small ones.
    Useful for researching what smart money / whale wallets are holding."""
    print("\n== Lookup Wallet Positions ==")
    address = _prompt("Wallet address (0x...)")
    if not address:
        return
    data = _get(DATA_BASE, "/positions", params={"user": address, "limit": 20, "sizeThreshold": 0})
    if not data:
        return
    positions = data if isinstance(data, list) else data.get("positions", [])
    rows = []
    for p in positions[:20]:
        asset = p.get("asset", p.get("market", ""))
        rows.append([
            _trunc(str(asset), 20),
            str(p.get("size", ""))[:12],
            str(p.get("avgPrice", p.get("averagePrice", "")))[:10],
            str(p.get("currentValue", ""))[:12],
            str(p.get("pnl", p.get("realizedPnl", "")))[:12],
        ])
    _print_table(rows, ["Asset", "Size", "AvgPrice", "Value", "PnL"])


def cmd_lookup_trades():
    """GET https://data-api.polymarket.com/trades?user={address}&limit={n}
    curl: curl "https://data-api.polymarket.com/trades?user=0x...&limit=20"
    Returns recent trades executed by a specific wallet. Public blockchain data.
    Each trade shows the market, side (BUY/SELL), size, price, and timestamp."""
    print("\n== Lookup Wallet Trades ==")
    address = _prompt("Wallet address")
    if not address:
        return
    data = _get(DATA_BASE, "/trades", params={"user": address, "limit": 20})
    if not data:
        return
    trades = data if isinstance(data, list) else data.get("trades", [])
    rows = []
    for t in trades[:20]:
        rows.append([
            _trunc(str(t.get("market", t.get("conditionId", ""))), 15),
            t.get("side", ""),
            str(t.get("size", ""))[:10],
            str(t.get("price", ""))[:8],
            str(t.get("timestamp", t.get("createdAt", "")))[:19],
        ])
    _print_table(rows, ["Market", "Side", "Size", "Price", "Time"])


def cmd_lookup_activity():
    """GET https://data-api.polymarket.com/activity?user={address}&limit={n}
    curl: curl "https://data-api.polymarket.com/activity?user=0x...&limit=20"
    Returns a chronological activity feed for a wallet including trades, position changes,
    deposits, and withdrawals. Broader than /trades which only shows executed orders."""
    print("\n== Lookup Wallet Activity ==")
    address = _prompt("Wallet address")
    if not address:
        return
    data = _get(DATA_BASE, "/activity", params={"user": address, "limit": 20})
    if not data:
        return
    if isinstance(data, list):
        for a in data[:15]:
            print(f"  {a.get('type', ''):15s} {a.get('timestamp', '')[:19]}  {_trunc(str(a.get('description', a.get('market', ''))), 50)}")
    else:
        print(json.dumps(data, indent=2)[:2000])


def cmd_top_holders():
    """GET https://data-api.polymarket.com/holders?token_id={id}&limit={n}
    curl: curl "https://data-api.polymarket.com/holders?token_id=TOKEN_ID&limit=20"
    Returns the largest holders of a specific outcome token, sorted by position size.
    Extremely useful for seeing who has conviction on a particular outcome - whale watching."""
    print("\n== Top Holders ==")
    token_id = _prompt("Token ID (CLOB token)")
    if not token_id:
        return
    data = _get(DATA_BASE, "/holders", params={"token_id": token_id, "limit": 20})
    if not data:
        return
    holders = data if isinstance(data, list) else data.get("holders", [])
    rows = []
    for h in holders[:20]:
        rows.append([
            _trunc(str(h.get("address", h.get("user", ""))), 20),
            str(h.get("amount", h.get("size", "")))[:15],
        ])
    _print_table(rows, ["Address", "Amount"])


def cmd_leaderboard():
    """GET https://data-api.polymarket.com/leaderboard?limit={n}&window=all
    curl: curl "https://data-api.polymarket.com/leaderboard?limit=20&window=all"
    Returns the top traders ranked by profit. Window can be "all" (all-time),
    "day", "week", "month". Shows profit, volume, and number of markets traded."""
    print("\n== Trader Leaderboard ==")
    data = _get(DATA_BASE, "/leaderboard", params={"limit": 20, "window": "all"})
    if not data:
        return
    leaders = data if isinstance(data, list) else data.get("leaderboard", data.get("rankings", []))
    if isinstance(leaders, list):
        rows = []
        for i, l in enumerate(leaders[:20]):
            rows.append([
                str(i + 1),
                _trunc(str(l.get("address", l.get("user", l.get("name", "")))), 20),
                str(l.get("profit", l.get("pnl", "")))[:15],
                str(l.get("volume", ""))[:15],
                str(l.get("marketsTraded", l.get("markets_traded", "")))[:8],
            ])
        _print_table(rows, ["Rank", "Trader", "Profit", "Volume", "Markets"])
    else:
        print(json.dumps(data, indent=2)[:2000])


def cmd_open_interest():
    """GET https://data-api.polymarket.com/open-interest?conditionId={id}
    curl: curl "https://data-api.polymarket.com/open-interest?conditionId=CONDITION_ID"
    Returns total open interest for a market (by condition ID). Open interest is the
    total number of outstanding contracts that haven't been settled or closed."""
    print("\n== Open Interest ==")
    condition_id = _prompt("Condition ID (market)")
    if not condition_id:
        return
    data = _get(DATA_BASE, "/open-interest", params={"conditionId": condition_id})
    if data:
        print(json.dumps(data, indent=2)[:1000])


def cmd_live_volume():
    """GET https://data-api.polymarket.com/volume/{event_id}
    curl: curl https://data-api.polymarket.com/volume/12345
    Returns real-time trading volume for a specific event. Useful for gauging
    current market activity and interest level."""
    print("\n== Live Event Volume ==")
    event_id = _prompt("Event ID")
    if not event_id:
        return
    data = _get(DATA_BASE, f"/volume/{event_id}")
    if data:
        print(json.dumps(data, indent=2)[:1000])


def cmd_public_profile():
    """GET https://gamma-api.polymarket.com/profiles/{address}
    curl: curl https://gamma-api.polymarket.com/profiles/0x...
    Returns the public profile for a wallet address including display name, bio,
    profile image URL, and linked Twitter handle (if set)."""
    print("\n== Public Profile ==")
    address = _prompt("Wallet address")
    if not address:
        return
    data = _get(GAMMA_BASE, f"/profiles/{address}")
    if data:
        print(f"  Name:       {data.get('name', data.get('username', 'N/A'))}")
        print(f"  Bio:        {_trunc(data.get('bio', ''), 80)}")
        print(f"  PFP:        {data.get('profileImage', 'N/A')}")
        print(f"  Twitter:    {data.get('twitter', data.get('twitterHandle', 'N/A'))}")


# ── WebSocket Streaming ─────────────────────────────────────────────────────

def cmd_ws_market():
    """WebSocket: wss://ws-subscriptions-clob.polymarket.com/ws/market
    Subscribes to real-time market data updates for specified token IDs.
    On connect, send a JSON subscription message:
      {"auth": {}, "markets": [token_id, ...], "assets_ids": [token_id, ...], "type": "market"}
    The server streams events including:
      - price_change: updated best bid/ask/midpoint
      - book_update: orderbook depth changes
      - last_trade: new trade executions
    No authentication required for market data streams.
    Rate: unlimited inbound messages; the server pushes updates as they occur."""
    print("\n== WebSocket Market Stream ==")
    print("  Requires: pip install websocket-client")
    try:
        import websocket
    except ImportError:
        print("  [!] Install: pip install websocket-client")
        return

    assets_str = _prompt("Comma-separated token IDs to subscribe")
    if not assets_str:
        return
    assets = [a.strip() for a in assets_str.split(",")]
    duration = int(_prompt("Stream duration seconds", "30"))

    print(f"  Connecting to {WS_MARKET} ...")

    def on_message(ws, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        try:
            data = json.loads(message)
            event_type = data[0].get("event_type", "?") if isinstance(data, list) and data else "?"
            print(f"  [{ts}] {event_type}: {json.dumps(data)[:200]}")
        except Exception:
            print(f"  [{ts}] {message[:200]}")

    def on_error(ws, error):
        print(f"  [!] WS Error: {error}")

    def on_open(ws):
        sub = {"auth": {}, "markets": assets, "assets_ids": assets, "type": "market"}
        ws.send(json.dumps(sub))
        print(f"  Subscribed to {len(assets)} assets")
        print(f"  Streaming for {duration}s...\n")

    ws_app = websocket.WebSocketApp(
        WS_MARKET,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
    )

    import threading
    t = threading.Thread(target=ws_app.run_forever, daemon=True)
    t.start()
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        pass
    ws_app.close()
    print("\n  Stream ended.")


# ── Menu ─────────────────────────────────────────────────────────────────────

MENU_SECTIONS = [
    ("Events & Markets (Gamma API)", [
        ("1", "List Events (trending)", cmd_list_events),
        ("2", "Get Event by Slug", cmd_get_event_slug),
        ("3", "Get Event by ID", cmd_get_event_id),
        ("4", "List Markets", cmd_list_markets),
        ("5", "Get Market by Slug", cmd_get_market_slug),
        ("6", "Get Market by ID", cmd_get_market_id),
        ("7", "Search Markets/Events", cmd_search),
        ("8", "Price History", cmd_price_history),
    ]),
    ("Tags / Series / Sports (Gamma API)", [
        ("9", "List Tags", cmd_list_tags),
        ("10", "Event Tags", cmd_get_event_tags),
        ("11", "List Series", cmd_list_series),
        ("12", "Sports Metadata", cmd_sports_metadata),
        ("13", "Sports Market Types", cmd_sports_market_types),
        ("14", "Comments", cmd_list_comments),
        ("15", "Public Profile", cmd_public_profile),
    ]),
    ("Orderbook & Pricing (CLOB API)", [
        ("16", "Orderbook", cmd_clob_orderbook),
        ("17", "Midpoint Price", cmd_clob_midpoint),
        ("18", "Market Price (BUY/SELL)", cmd_clob_price),
        ("19", "Spread", cmd_clob_spread),
        ("20", "Spreads (Multiple)", cmd_clob_spreads),
        ("21", "Last Trade Price", cmd_clob_last_trade),
        ("22", "Tick Size", cmd_clob_tick_size),
        ("23", "Fee Rate", cmd_clob_fee_rate),
        ("24", "Prices History (CLOB)", cmd_clob_prices_history),
        ("25", "Server Time", cmd_clob_server_time),
    ]),
    ("Analytics (Data API)", [
        ("26", "Lookup Wallet Positions", cmd_lookup_positions),
        ("27", "Lookup Wallet Trades", cmd_lookup_trades),
        ("28", "Lookup Wallet Activity", cmd_lookup_activity),
        ("29", "Top Holders for Token", cmd_top_holders),
        ("30", "Trader Leaderboard", cmd_leaderboard),
        ("31", "Open Interest", cmd_open_interest),
        ("32", "Live Event Volume", cmd_live_volume),
    ]),
    ("WebSocket Streaming", [
        ("33", "Market Stream (orderbook/prices)", cmd_ws_market),
    ]),
]

COMMAND_MAP = {}
for _, items in MENU_SECTIONS:
    for key, label, func in items:
        COMMAND_MAP[key] = func


def print_menu():
    print(f"\n{'=' * 60}")
    print(f"  POLYMARKET EXPLORER  |  No API key required")
    print(f"{'=' * 60}")
    for section, items in MENU_SECTIONS:
        print(f"\n  {section}")
        print(f"  {'-' * len(section)}")
        for key, label, _ in items:
            print(f"    {key:>3}. {label}")
    print(f"\n    q. Quit")
    print(f"{'=' * 60}")


def interactive_loop():
    while True:
        print_menu()
        choice = input("\n  Select: ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            print("  Bye.")
            break
        if choice in COMMAND_MAP:
            try:
                COMMAND_MAP[choice]()
            except KeyboardInterrupt:
                print("\n  (interrupted)")
            except Exception as e:
                print(f"  [!] Error: {e}")
        else:
            print("  Invalid choice.")


# ── Non-Interactive CLI ──────────────────────────────────────────────────────

def build_argparse():
    parser = argparse.ArgumentParser(description="Polymarket Explorer - public market data")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("events", help="List events")
    p.add_argument("--order", default="volume24hr")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--tag-id", default="")

    p = sub.add_parser("event-slug", help="Get event by slug")
    p.add_argument("slug")

    p = sub.add_parser("event-id", help="Get event by ID")
    p.add_argument("id")

    p = sub.add_parser("markets", help="List markets")
    p.add_argument("--order", default="volume24hr")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("market-slug", help="Get market by slug")
    p.add_argument("slug")

    p = sub.add_parser("market-id", help="Get market by ID")
    p.add_argument("id")

    p = sub.add_parser("search", help="Search markets/events")
    p.add_argument("query")

    p = sub.add_parser("price-history", help="Price history")
    p.add_argument("market_id")
    p.add_argument("--interval", default="1h")
    p.add_argument("--fidelity", type=int, default=100)

    sub.add_parser("tags", help="List tags")
    sub.add_parser("series", help="List series")
    sub.add_parser("sports", help="Sports metadata")

    p = sub.add_parser("orderbook", help="CLOB orderbook")
    p.add_argument("token_id")

    p = sub.add_parser("midpoint", help="CLOB midpoint")
    p.add_argument("token_id")

    p = sub.add_parser("price", help="CLOB market price")
    p.add_argument("token_id")
    p.add_argument("--side", default="BUY")

    p = sub.add_parser("spread", help="CLOB spread")
    p.add_argument("token_id")

    p = sub.add_parser("last-trade", help="CLOB last trade price")
    p.add_argument("token_id")

    p = sub.add_parser("positions", help="Lookup wallet positions")
    p.add_argument("address")

    p = sub.add_parser("trades", help="Lookup wallet trades")
    p.add_argument("address")

    p = sub.add_parser("activity", help="Lookup wallet activity")
    p.add_argument("address")

    p = sub.add_parser("leaderboard", help="Trader leaderboard")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("holders", help="Top holders for token")
    p.add_argument("token_id")

    p = sub.add_parser("profile", help="Public profile")
    p.add_argument("address")

    sub.add_parser("server-time", help="CLOB server time")

    return parser


def run_noninteractive(args):
    cmd = args.command
    if cmd == "events":
        params = {"limit": args.limit, "order": args.order, "ascending": "false", "active": "true", "closed": "false"}
        if args.tag_id:
            params["tag_id"] = args.tag_id
        data = _get(GAMMA_BASE, "/events", params=params)
        if data:
            items = data if isinstance(data, list) else [data]
            for e in items:
                print(f"{str(e.get('id', ''))[:10]:12s} {e.get('title', '')[:60]}")
    elif cmd == "event-slug":
        data = _get(GAMMA_BASE, f"/events/slug/{args.slug}")
        print(json.dumps(data, indent=2))
    elif cmd == "event-id":
        data = _get(GAMMA_BASE, f"/events/{args.id}")
        print(json.dumps(data, indent=2))
    elif cmd == "markets":
        params = {"limit": args.limit, "order": args.order, "ascending": "false", "active": "true", "closed": "false"}
        data = _get(GAMMA_BASE, "/markets", params=params)
        if data:
            items = data if isinstance(data, list) else [data]
            for m in items:
                print(f"{str(m.get('id', ''))[:10]:12s} {m.get('question', '')[:60]}")
    elif cmd == "market-slug":
        data = _get(GAMMA_BASE, f"/markets/slug/{args.slug}")
        print(json.dumps(data, indent=2))
    elif cmd == "market-id":
        data = _get(GAMMA_BASE, f"/markets/{args.id}")
        print(json.dumps(data, indent=2))
    elif cmd == "search":
        data = _get(GAMMA_BASE, "/public-search", params={"q": args.query, "limit": 10})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "price-history":
        data = _get(GAMMA_BASE, "/prices-history", params={"market": args.market_id, "interval": args.interval, "fidelity": args.fidelity})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "tags":
        data = _get(GAMMA_BASE, "/tags")
        if isinstance(data, list):
            for t in data:
                print(f"{str(t.get('id', '')):10s} {t.get('label', t.get('name', t.get('slug', '')))}")
    elif cmd == "series":
        data = _get(GAMMA_BASE, "/series", params={"limit": 20})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "sports":
        data = _get(GAMMA_BASE, "/sports")
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "orderbook":
        data = _get(CLOB_BASE, "/book", params={"token_id": args.token_id})
        print(json.dumps(data, indent=2))
    elif cmd == "midpoint":
        data = _get(CLOB_BASE, "/midpoint", params={"token_id": args.token_id})
        print(json.dumps(data, indent=2))
    elif cmd == "price":
        data = _get(CLOB_BASE, "/price", params={"token_id": args.token_id, "side": args.side})
        print(json.dumps(data, indent=2))
    elif cmd == "spread":
        data = _get(CLOB_BASE, "/spread", params={"token_id": args.token_id})
        print(json.dumps(data, indent=2))
    elif cmd == "last-trade":
        data = _get(CLOB_BASE, "/last-trade-price", params={"token_id": args.token_id})
        print(json.dumps(data, indent=2))
    elif cmd == "positions":
        data = _get(DATA_BASE, "/positions", params={"user": args.address, "limit": 20})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "trades":
        data = _get(DATA_BASE, "/trades", params={"user": args.address, "limit": 20})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "activity":
        data = _get(DATA_BASE, "/activity", params={"user": args.address, "limit": 20})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "leaderboard":
        data = _get(DATA_BASE, "/leaderboard", params={"limit": args.limit, "window": "all"})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "holders":
        data = _get(DATA_BASE, "/holders", params={"token_id": args.token_id, "limit": 20})
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "profile":
        data = _get(GAMMA_BASE, f"/profiles/{args.address}")
        print(json.dumps(data, indent=2, default=str))
    elif cmd == "server-time":
        data = _get(CLOB_BASE, "/time")
        print(f"Server time: {data}")
    else:
        print(f"Unknown command: {cmd}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        print("\n  Polymarket Explorer - Public Market Data")
        print("  ----------------------------------------")
        print(f"  Gamma API: {GAMMA_BASE}")
        print(f"  Data API:  {DATA_BASE}")
        print(f"  CLOB API:  {CLOB_BASE}")
        print(f"  No API key needed - all endpoints are public.")
        print()
        interactive_loop()


if __name__ == "__main__":
    main()
