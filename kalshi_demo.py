#!/usr/bin/env python3
"""
Kalshi public Trade API explorer (read-only market data).

Kalshi is a CFTC-regulated prediction market exchange. All HTTP calls in this script
hit a single API host: ``https://api.elections.kalshi.com``. The ``elections`` subdomain
is historical naming; it serves every product type (politics, economics, sports,
weather, etc.), not only election contracts.

API layout
----------
Base path for REST resources: ``/trade-api/v2``. Full URLs look like
``https://api.elections.kalshi.com/trade-api/v2/markets``.

Data hierarchy
--------------
- **Series**: Template for recurring events with shared rules and settlement sources
  (e.g. a recurring economic release or daily weather contract family).
- **Event**: One real-world occurrence (a specific date, game, or release) that
  groups related contracts.
- **Market**: One tradable binary YES/NO contract (a specific threshold or outcome
  within that event).

Pricing and order book
----------------------
Contracts are binary: YES and NO. Prices are quoted between 1 and 99 **cents** per
share (one cent minimum tick). A YES price of 65 cents implies about a 65% implied
probability; YES and NO always sum to one dollar per paired contract at fair value.

The order book exposes **bids only** (e.g. ``yes_bids`` / ``no_bids`` in raw API
shapes, or dollar ladders in ``orderbook_fp``). There are no separate "ask" ladders
because a bid to buy YES at X is economically the same as an offer to sell NO at
(100 - X) cents. That identity is standard for binary prediction markets.

Responses often include prices twice: integer **cents** fields (e.g. ``yes_bid``) and
string **dollar** fields (e.g. ``yes_bid_dollars`` like ``"$0.65"``). Volume and
counts may appear as fixed-point strings or ``*_fp`` fields depending on the endpoint.

Pagination
----------
List endpoints support cursor-based pagination: pass ``cursor`` from the previous
response to fetch the next page, subject to each endpoint's ``limit`` (often 1--200).

Auth and limits
---------------
Every route used here is **public** (no API key). Authenticated trading and portfolio
calls use RSA-PSS signed request headers and are out of scope for this file. Rate
limits depend on account tier; a typical public tier is on the order of ~10 requests
per second.

Dependencies: ``pip install requests``
"""

import argparse
import json
import sys

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


# ── HTTP / Display ──────────────────────────────────────────────────────────

def _get(path, params=None):
    """Issue a GET against the Trade API v2, returning parsed JSON or None on HTTP error.

    ``BASE_URL`` is ``https://api.elections.kalshi.com/trade-api/v2``. The ``path``
    argument is **relative** to that prefix: for example ``"/markets"`` becomes
    ``https://api.elections.kalshi.com/trade-api/v2/markets``. Query strings are
    built from the optional ``params`` mapping (e.g. ``{"limit": 20}``).

    On status codes >= 400, prints a short error snippet and returns ``None`` so
    interactive callers can bail without raising.
    """
    r = requests.get(BASE_URL + path, params=params, timeout=15)
    if r.status_code >= 400:
        print(f"  [!] HTTP {r.status_code}: {r.text[:300]}")
        return None
    return r.json()


def _print_table(rows, headers):
    """Render ``rows`` as a fixed-width, column-aligned table for terminal output."""
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
    """Read a line from stdin in the interactive menu; empty input returns ``default``."""
    suffix = f" [{default}]" if default else ""
    val = input(f"  {msg}{suffix}: ").strip()
    return val if val else default


# ── Exchange ─────────────────────────────────────────────────────────────────

def cmd_exchange_status():
    """GET {BASE}/exchange/status

    curl: curl https://api.elections.kalshi.com/trade-api/v2/exchange/status
    Returns: {exchange_active: bool, trading_active: bool, exchange_estimated_resume_time: str|null}
    Shows whether the exchange is open and accepting trades. Trading can be paused
    independently of the exchange itself (e.g. during maintenance windows).
    """
    print("\n== Exchange Status ==")
    data = _get("/exchange/status")
    if data:
        print(f"  Exchange Active: {data.get('exchange_active', 'N/A')}")
        print(f"  Trading Active:  {data.get('trading_active', 'N/A')}")
        resume = data.get("exchange_estimated_resume_time")
        if resume:
            print(f"  Est. Resume:     {resume}")


def cmd_exchange_schedule():
    """GET {BASE}/exchange/schedule

    curl: curl https://api.elections.kalshi.com/trade-api/v2/exchange/schedule
    Returns the weekly trading schedule with open/close times per day.
    The exchange typically operates on a defined weekly schedule with possible
    holiday closures.
    """
    print("\n== Exchange Schedule ==")
    data = _get("/exchange/schedule")
    if data:
        sched = data.get("schedule", data)
        print(json.dumps(sched, indent=2))


# ── Series ───────────────────────────────────────────────────────────────────

def cmd_list_series():
    """GET {BASE}/series?limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/series?limit=20"
    A Series is a template for recurring events that share the same format and rules.
    Examples: "Monthly Jobs Report", "Weekly Jobless Claims", "Daily Weather in NYC".
    Series define settlement sources, methodology, and generate new events on schedule.
    Response: {series: [{ticker, title, category, frequency, tags, ...}]}
    """
    print("\n== Series List ==")
    limit = _prompt("Limit", "20")
    data = _get("/series", params={"limit": int(limit)})
    if not data:
        return
    series_list = data.get("series", [])
    rows = []
    for s in series_list:
        rows.append([
            s.get("ticker", ""),
            s.get("title", "")[:50],
            s.get("category", ""),
            s.get("frequency", ""),
        ])
    _print_table(rows, ["Ticker", "Title", "Category", "Frequency"])
    print(f"\n  Returned: {len(series_list)}")


def cmd_get_series():
    """GET {BASE}/series/{ticker}

    curl: curl https://api.elections.kalshi.com/trade-api/v2/series/KXHIGHNY
    Returns full detail for a single series including its settlement rules,
    category, frequency (daily/weekly/monthly), and tags.
    Response: {series: {ticker, title, category, frequency, settlement_sources, ...}}
    """
    print("\n== Get Series ==")
    ticker = _prompt("Series ticker (e.g. KXHIGHNY)")
    if not ticker:
        return
    data = _get(f"/series/{ticker}")
    if data:
        s = data.get("series", data)
        print(f"  Title:     {s.get('title', 'N/A')}")
        print(f"  Ticker:    {s.get('ticker', 'N/A')}")
        print(f"  Category:  {s.get('category', 'N/A')}")
        print(f"  Frequency: {s.get('frequency', 'N/A')}")
        print(f"  Tags:      {s.get('tags', [])}")


# ── Events ───────────────────────────────────────────────────────────────────

def cmd_list_events():
    """GET {BASE}/events?status={s}&series_ticker={t}&limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/events?status=open&limit=20"
    An Event is a real-world occurrence that can be traded on (election, sports game,
    economic indicator release). Events contain one or more markets.
    Params: status (open/closed/settled), series_ticker, limit (1-200), cursor
    Response: {events: [{event_ticker, title, category, status, market_count, markets: [...]}]}
    Excludes multivariate events - use GET /events/multivariate for those.
    """
    print("\n== Events ==")
    params = {"limit": 20}
    status = _prompt("Status filter (open/closed/settled/empty for all)", "")
    if status:
        params["status"] = status
    series = _prompt("Series ticker filter (empty for all)", "")
    if series:
        params["series_ticker"] = series
    data = _get("/events", params=params)
    if not data:
        return
    events = data.get("events", [])
    rows = []
    for e in events:
        rows.append([
            e.get("event_ticker", ""),
            e.get("title", "")[:50],
            e.get("category", ""),
            str(e.get("market_count", "")),
        ])
    _print_table(rows, ["Ticker", "Title", "Category", "Markets"])
    print(f"\n  Returned: {len(events)}")


def cmd_get_event():
    """GET {BASE}/events/{event_ticker}

    curl: curl https://api.elections.kalshi.com/trade-api/v2/events/KXHIGHNY-25APR01
    Returns a single event with all its child markets embedded.
    Each market includes current pricing, volume, open interest, and status.
    Response: {event: {event_ticker, title, category, status, markets: [...]}}
    """
    print("\n== Get Event ==")
    ticker = _prompt("Event ticker")
    if not ticker:
        return
    data = _get(f"/events/{ticker}")
    if data:
        e = data.get("event", data)
        print(f"  Title:        {e.get('title', 'N/A')}")
        print(f"  Category:     {e.get('category', 'N/A')}")
        print(f"  Status:       {e.get('status', 'N/A')}")
        print(f"  Markets:      {e.get('market_count', 'N/A')}")
        print(f"  Series:       {e.get('series_ticker', 'N/A')}")
        markets = e.get("markets", [])
        if markets:
            print(f"\n  Markets in this event:")
            rows = []
            for m in markets:
                rows.append([
                    m.get("ticker", ""),
                    m.get("title", "")[:40],
                    str(m.get("yes_bid_dollars", "")),
                    str(m.get("volume_fp", "")),
                    m.get("status", ""),
                ])
            _print_table(rows, ["Ticker", "Title", "YesBid$", "Volume", "Status"])


def cmd_event_candlesticks():
    """GET {BASE}/events/{ticker}/candlesticks?period_interval={minutes}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/events/KXHIGHNY-25APR01/candlesticks?period_interval=60"
    Returns OHLCV candlestick data aggregated across all markets in the event.
    period_interval: 1 (1-min), 60 (1-hour), or 1440 (1-day)
    Response: {candlesticks: [{end_period_ts, price: {open, high, low, close}, volume_fp}]}
    Useful for charting the overall probability distribution of an event over time.
    """
    print("\n== Event Candlesticks ==")
    ticker = _prompt("Event ticker")
    if not ticker:
        return
    period = _prompt("Period minutes (1/60/1440)", "60")
    data = _get(f"/events/{ticker}/candlesticks", params={"period_interval": int(period)})
    if data:
        candles = data.get("candlesticks", [])
        rows = []
        for c in candles[:20]:
            rows.append([
                c.get("end_period_ts", "")[:19],
                str(c.get("price", {}).get("open", "")),
                str(c.get("price", {}).get("high", "")),
                str(c.get("price", {}).get("low", "")),
                str(c.get("price", {}).get("close", "")),
                str(c.get("volume_fp", "")),
            ])
        _print_table(rows, ["Time", "Open", "High", "Low", "Close", "Volume"])
        print(f"  (showing up to 20 of {len(candles)} candles)")


def cmd_event_forecast():
    """GET {BASE}/events/{ticker}/forecast/percentile_history

    curl: curl https://api.elections.kalshi.com/trade-api/v2/events/KXHIGHNY-25APR01/forecast/percentile_history
    Returns historical raw and formatted forecast numbers at specific percentiles.
    Used for events with numerical outcomes (like temperature, job numbers) to see
    how the market's probability distribution has shifted over time.
    """
    print("\n== Event Forecast Percentile History ==")
    ticker = _prompt("Event ticker")
    if not ticker:
        return
    data = _get(f"/events/{ticker}/forecast/percentile_history")
    if data:
        print(json.dumps(data, indent=2)[:2000])


# ── Markets ──────────────────────────────────────────────────────────────────

def cmd_list_markets():
    """GET {BASE}/markets?status={s}&series_ticker={t}&event_ticker={e}&limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit=20"
    A Market is a specific binary outcome within an event (e.g. "Will temp exceed 80F?").
    Each market has YES/NO positions with prices from $0.01 to $0.99.
    Params: status (unopened/open/closed/settled), series_ticker, event_ticker, limit, cursor
    Response: {markets: [{ticker, title, status, yes_bid_dollars, no_bid_dollars,
      yes_ask_dollars, no_ask_dollars, volume_fp, open_interest_fp, ...}]}
    Only one status filter at a time. Timestamp filters are mutually exclusive.
    """
    print("\n== Markets ==")
    params = {"limit": 20}
    status = _prompt("Status (open/closed/settled/empty for all)", "open")
    if status:
        params["status"] = status
    series = _prompt("Series ticker filter", "")
    if series:
        params["series_ticker"] = series
    event = _prompt("Event ticker filter", "")
    if event:
        params["event_ticker"] = event
    data = _get("/markets", params=params)
    if not data:
        return
    markets = data.get("markets", [])
    rows = []
    for m in markets:
        yes_price = m.get("yes_bid_dollars", m.get("yes_bid", ""))
        vol = m.get("volume_fp", m.get("volume", ""))
        rows.append([
            m.get("ticker", ""),
            m.get("title", "")[:45],
            str(yes_price),
            str(vol),
            m.get("status", ""),
        ])
    _print_table(rows, ["Ticker", "Title", "YesBid$", "Volume", "Status"])
    print(f"\n  Returned: {len(markets)}")


def cmd_get_market():
    """GET {BASE}/markets/{ticker}

    curl: curl https://api.elections.kalshi.com/trade-api/v2/markets/KXHIGHNY-25APR01-T80
    Returns full detail for a single market including current best bid/ask for both sides,
    volume, open interest, expiration time, close time, result (if settled), and subtitle.
    Key price fields:
      yes_bid_dollars / yes_ask_dollars - best bid/ask for YES side ("$0.65")
      no_bid_dollars / no_ask_dollars   - best bid/ask for NO side ("$0.35")
      volume_fp                         - total contracts traded (fixed-point)
      open_interest_fp                  - outstanding open positions
    """
    print("\n== Get Market ==")
    ticker = _prompt("Market ticker")
    if not ticker:
        return
    data = _get(f"/markets/{ticker}")
    if data:
        m = data.get("market", data)
        print(f"  Title:           {m.get('title', 'N/A')}")
        print(f"  Ticker:          {m.get('ticker', 'N/A')}")
        print(f"  Event:           {m.get('event_ticker', 'N/A')}")
        print(f"  Status:          {m.get('status', 'N/A')}")
        print(f"  Yes Bid:         ${m.get('yes_bid_dollars', 'N/A')}")
        print(f"  Yes Ask:         ${m.get('yes_ask_dollars', 'N/A')}")
        print(f"  No Bid:          ${m.get('no_bid_dollars', 'N/A')}")
        print(f"  No Ask:          ${m.get('no_ask_dollars', 'N/A')}")
        print(f"  Volume:          {m.get('volume_fp', m.get('volume', 'N/A'))}")
        print(f"  Open Interest:   {m.get('open_interest_fp', m.get('open_interest', 'N/A'))}")
        print(f"  Expiration:      {m.get('expiration_time', 'N/A')}")
        print(f"  Result:          {m.get('result', 'N/A')}")
        print(f"  Close Time:      {m.get('close_time', 'N/A')}")
        subtitle = m.get("subtitle", "")
        if subtitle:
            print(f"  Subtitle:        {subtitle}")


def cmd_market_orderbook():
    """GET {BASE}/markets/{ticker}/orderbook?depth={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/markets/KXHIGHNY-25APR01-T80/orderbook"
    Returns the live order book for a market. Kalshi orderbooks are unique because they only
    return BIDS (no asks). In binary markets, a YES bid at $0.65 is mathematically equivalent
    to a NO ask at $0.35 (since YES + NO = $1.00). So the book has:
      yes_dollars: [[price, quantity], ...] - bids to buy YES contracts
      no_dollars:  [[price, quantity], ...] - bids to buy NO contracts
    Optional depth param limits the number of price levels returned.
    Response: {orderbook_fp: {yes_dollars: [[price, qty], ...], no_dollars: [[price, qty], ...]}}
    """
    print("\n== Market Orderbook ==")
    ticker = _prompt("Market ticker")
    if not ticker:
        return
    depth = _prompt("Depth (default all)", "")
    params = {}
    if depth:
        params["depth"] = int(depth)
    data = _get(f"/markets/{ticker}/orderbook", params=params)
    if not data:
        return
    ob = data.get("orderbook_fp", data.get("orderbook", {}))
    yes_bids = ob.get("yes_dollars", ob.get("yes", []))
    no_bids = ob.get("no_dollars", ob.get("no", []))
    print(f"\n  YES BIDS ({len(yes_bids)} levels):")
    rows = []
    for level in yes_bids[:15]:
        if isinstance(level, list) and len(level) >= 2:
            rows.append([str(level[0]), str(level[1])])
        else:
            rows.append([str(level), ""])
    _print_table(rows, ["Price", "Quantity"])
    print(f"\n  NO BIDS ({len(no_bids)} levels):")
    rows = []
    for level in no_bids[:15]:
        if isinstance(level, list) and len(level) >= 2:
            rows.append([str(level[0]), str(level[1])])
        else:
            rows.append([str(level), ""])
    _print_table(rows, ["Price", "Quantity"])


def cmd_multi_orderbooks():
    """GET {BASE}/markets/orderbooks?tickers={t1},{t2},...

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/markets/orderbooks?tickers=TICKER1,TICKER2"
    Batch endpoint to fetch orderbooks for multiple markets in a single request.
    Returns a dict keyed by ticker, each containing the same orderbook_fp structure
    as the single-market endpoint. Useful for scanning multiple markets at once.
    """
    print("\n== Multiple Orderbooks ==")
    tickers = _prompt("Comma-separated market tickers")
    if not tickers:
        return
    ticker_list = [t.strip() for t in tickers.split(",")]
    data = _get("/markets/orderbooks", params={"tickers": ",".join(ticker_list)})
    if not data:
        return
    for ticker, ob_data in data.items():
        print(f"\n  --- {ticker} ---")
        ob = ob_data.get("orderbook_fp", ob_data.get("orderbook", {}))
        yes_bids = ob.get("yes_dollars", ob.get("yes", []))
        no_bids = ob.get("no_dollars", ob.get("no", []))
        print(f"    YES levels: {len(yes_bids)}, NO levels: {len(no_bids)}")
        if yes_bids:
            top = yes_bids[0]
            if isinstance(top, list):
                print(f"    Best YES: ${top[0]} x {top[1]}")
        if no_bids:
            top = no_bids[0]
            if isinstance(top, list):
                print(f"    Best NO:  ${top[0]} x {top[1]}")


def cmd_market_candlesticks():
    """GET {BASE}/markets/{ticker}/candlesticks?period_interval={minutes}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/markets/TICKER/candlesticks?period_interval=60"
    Returns OHLCV candlestick data for a specific market (not aggregated across event).
    period_interval: 1 (1-min), 60 (1-hour), or 1440 (1-day)
    Note: candlesticks for markets settled before the historical cutoff are only available
    via GET /historical/markets/{ticker}/candlesticks instead.
    Response: {candlesticks: [{end_period_ts, price: {open, high, low, close}, volume_fp}]}
    """
    print("\n== Market Candlesticks ==")
    ticker = _prompt("Market ticker")
    if not ticker:
        return
    period = _prompt("Period minutes (1/60/1440)", "60")
    data = _get(f"/markets/{ticker}/candlesticks", params={"period_interval": int(period)})
    if data:
        candles = data.get("candlesticks", [])
        rows = []
        for c in candles[:20]:
            rows.append([
                c.get("end_period_ts", "")[:19],
                str(c.get("price", {}).get("open", "")),
                str(c.get("price", {}).get("high", "")),
                str(c.get("price", {}).get("low", "")),
                str(c.get("price", {}).get("close", "")),
                str(c.get("volume_fp", c.get("volume", ""))),
            ])
        _print_table(rows, ["Time", "Open", "High", "Low", "Close", "Volume"])
        print(f"  (showing up to 20 of {len(candles)} candles)")


def cmd_get_trades():
    """GET {BASE}/markets/trades?ticker={t}&limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/markets/trades?limit=20"
    Returns recent public trades across all markets (or filtered to one market).
    Each trade shows the market ticker, the YES price at which it executed,
    the number of contracts (count_fp), which side was the taker, and timestamp.
    Paginated with cursor. Trades before the historical cutoff need GET /historical/trades.
    Response: {trades: [{ticker, yes_price, count_fp, taker_side, created_time}], cursor}
    """
    print("\n== Public Trades ==")
    params = {"limit": 20}
    ticker = _prompt("Market ticker filter (empty for all)", "")
    if ticker:
        params["ticker"] = ticker
    data = _get("/markets/trades", params=params)
    if not data:
        return
    trades = data.get("trades", [])
    rows = []
    for t in trades:
        rows.append([
            t.get("ticker", ""),
            t.get("yes_price", ""),
            str(t.get("count_fp", t.get("count", ""))),
            t.get("taker_side", ""),
            t.get("created_time", "")[:19],
        ])
    _print_table(rows, ["Ticker", "YesPrice", "Count", "TakerSide", "Time"])


# ── Search / Discovery ──────────────────────────────────────────────────────

def cmd_search_tags():
    """GET {BASE}/search/tags

    curl: curl https://api.elections.kalshi.com/trade-api/v2/search/tags
    Returns all series categories and their associated tags, organized hierarchically.
    Tags are used to classify and filter series/events (e.g. "Politics", "Economics",
    "Weather", "Sports"). Response structure: {categories: {category_name: [tag, ...]}}
    """
    print("\n== Series Categories & Tags ==")
    data = _get("/search/tags")
    if data:
        categories = data.get("categories", data)
        if isinstance(categories, dict):
            for cat, tags in categories.items():
                print(f"\n  {cat}:")
                if isinstance(tags, list):
                    for tag in tags[:10]:
                        print(f"    - {tag}")
        else:
            print(json.dumps(categories, indent=2)[:1000])


def cmd_sports_filters():
    """GET {BASE}/search/sports/filters

    curl: curl https://api.elections.kalshi.com/trade-api/v2/search/sports/filters
    Returns available filter dimensions organized by sport (NFL, NBA, MLB, NHL, etc).
    Each sport has its own set of filterable attributes (teams, leagues, game types).
    Useful for building sport-specific market discovery UIs.
    """
    print("\n== Sports Filters ==")
    data = _get("/search/sports/filters")
    if data:
        print(json.dumps(data, indent=2)[:2000])


def cmd_milestones():
    """GET {BASE}/milestones?limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/milestones?limit=20"
    Milestones represent scheduled real-world events that markets are tied to
    (e.g. a specific NBA game, a jobs report release date). They have start/end times
    and types. Markets reference milestones for their settlement triggers.
    Response: {milestones: [{id, title, type, start_date, ...}]}
    """
    print("\n== Milestones ==")
    data = _get("/milestones", params={"limit": 20})
    if not data:
        return
    milestones = data.get("milestones", [])
    rows = []
    for m in milestones:
        rows.append([
            str(m.get("id", ""))[:12],
            m.get("title", "")[:40],
            m.get("type", ""),
            m.get("start_date", "")[:10],
        ])
    _print_table(rows, ["ID", "Title", "Type", "StartDate"])


def cmd_structured_targets():
    """GET {BASE}/structured_targets?limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/structured_targets?limit=20"
    Structured targets are predefined numerical thresholds that markets are built around
    (e.g. "temperature above 80F", "jobs report above 200K"). They provide the specific
    values that determine YES/NO resolution for markets in a series.
    Response: {structured_targets: [{id, title, type, ...}]}
    """
    print("\n== Structured Targets ==")
    data = _get("/structured_targets", params={"limit": 20})
    if not data:
        return
    targets = data.get("structured_targets", [])
    rows = []
    for t in targets:
        rows.append([
            str(t.get("id", ""))[:12],
            t.get("title", "")[:40],
            t.get("type", ""),
        ])
    _print_table(rows, ["ID", "Title", "Type"])


def cmd_live_data():
    """GET {BASE}/live_data/milestone/{milestone_id}

    curl: curl https://api.elections.kalshi.com/trade-api/v2/live_data/milestone/MILESTONE_ID
    Returns real-time data for a specific milestone - primarily used for sports markets.
    For supported sports (NFL, NBA, MLB, NHL, etc.) this includes play-by-play stats,
    current scores, and game state. Returns null for unsupported milestone types.
    """
    print("\n== Live Data (Sports/Events) ==")
    milestone_id = _prompt("Milestone ID")
    if not milestone_id:
        return
    data = _get(f"/live_data/milestone/{milestone_id}")
    if data:
        print(json.dumps(data, indent=2)[:2000])


# ── Historical ───────────────────────────────────────────────────────────────

def cmd_historical_trades():
    """GET {BASE}/historical/trades?ticker={t}&limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/historical/trades?limit=20"
    Returns trades that occurred before the historical cutoff date. Kalshi maintains a
    rolling window of "live" data; older data is archived to historical endpoints.
    Same response format as GET /markets/trades but for archived data.
    Use GET /historical/cutoff to find the exact cutoff timestamp.
    """
    print("\n== Historical Trades ==")
    params = {"limit": 20}
    ticker = _prompt("Market ticker filter (empty for all)", "")
    if ticker:
        params["ticker"] = ticker
    data = _get("/historical/trades", params=params)
    if not data:
        return
    trades = data.get("trades", [])
    rows = []
    for t in trades:
        rows.append([
            t.get("ticker", ""),
            str(t.get("yes_price", "")),
            str(t.get("count_fp", t.get("count", ""))),
            t.get("taker_side", ""),
            t.get("created_time", "")[:19],
        ])
    _print_table(rows, ["Ticker", "YesPrice", "Count", "TakerSide", "Time"])


def cmd_historical_markets():
    """GET {BASE}/historical/markets?series_ticker={t}&limit={n}

    curl: curl "https://api.elections.kalshi.com/trade-api/v2/historical/markets?limit=20"
    Returns markets that have been archived from the live dataset. Settled markets older
    than the historical cutoff are only available here. Includes full market data with
    final result, settlement price, and all the same fields as GET /markets.
    Response: {markets: [{ticker, title, status, result, ...}]}
    """
    print("\n== Historical Markets ==")
    params = {"limit": 20}
    series = _prompt("Series ticker filter", "")
    if series:
        params["series_ticker"] = series
    data = _get("/historical/markets", params=params)
    if not data:
        return
    markets = data.get("markets", [])
    rows = []
    for m in markets:
        rows.append([
            m.get("ticker", ""),
            m.get("title", "")[:40],
            m.get("result", ""),
            m.get("status", ""),
        ])
    _print_table(rows, ["Ticker", "Title", "Result", "Status"])


# ── Menu ─────────────────────────────────────────────────────────────────────

MENU_SECTIONS = [
    ("Exchange", [
        ("1", "Exchange Status", cmd_exchange_status),
        ("2", "Exchange Schedule", cmd_exchange_schedule),
    ]),
    ("Series", [
        ("3", "List Series", cmd_list_series),
        ("4", "Get Series Detail", cmd_get_series),
    ]),
    ("Events", [
        ("5", "List Events", cmd_list_events),
        ("6", "Get Event Detail", cmd_get_event),
        ("7", "Event Candlesticks", cmd_event_candlesticks),
        ("8", "Event Forecast History", cmd_event_forecast),
    ]),
    ("Markets", [
        ("9", "List Markets", cmd_list_markets),
        ("10", "Get Market Detail", cmd_get_market),
        ("11", "Market Orderbook", cmd_market_orderbook),
        ("12", "Multiple Orderbooks", cmd_multi_orderbooks),
        ("13", "Market Candlesticks", cmd_market_candlesticks),
        ("14", "Public Trades", cmd_get_trades),
    ]),
    ("Search & Discovery", [
        ("15", "Series Categories & Tags", cmd_search_tags),
        ("16", "Sports Filters", cmd_sports_filters),
        ("17", "Milestones", cmd_milestones),
        ("18", "Structured Targets", cmd_structured_targets),
        ("19", "Live Data (Sports)", cmd_live_data),
    ]),
    ("Historical", [
        ("20", "Historical Trades", cmd_historical_trades),
        ("21", "Historical Markets", cmd_historical_markets),
    ]),
]

COMMAND_MAP = {}
for _, items in MENU_SECTIONS:
    for key, label, func in items:
        COMMAND_MAP[key] = func


def print_menu():
    """Print the numbered menu mapping choices to the same public Trade API flows as ``run_noninteractive``."""
    print(f"\n{'=' * 56}")
    print(f"  KALSHI EXPLORER  |  No API key required")
    print(f"{'=' * 56}")
    for section, items in MENU_SECTIONS:
        print(f"\n  {section}")
        print(f"  {'-' * len(section)}")
        for key, label, _ in items:
            print(f"    {key:>3}. {label}")
    print(f"\n    q. Quit")
    print(f"{'=' * 56}")


def interactive_loop():
    """Drive the explorer interactively: menu choice -> ``cmd_*`` (each documented with its HTTP path)."""
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
    """Define argparse subcommands that mirror a subset of the interactive ``cmd_*`` endpoints (same ``_get`` paths)."""
    parser = argparse.ArgumentParser(description="Kalshi Explorer - public market data")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("exchange-status", help="Get exchange status")
    sub.add_parser("exchange-schedule", help="Get exchange schedule")

    p = sub.add_parser("list-series", help="List series")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("get-series", help="Get series detail")
    p.add_argument("ticker")

    p = sub.add_parser("list-events", help="List events")
    p.add_argument("--status", default="")
    p.add_argument("--series", default="")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("get-event", help="Get event detail")
    p.add_argument("ticker")

    p = sub.add_parser("event-candles", help="Event candlesticks")
    p.add_argument("ticker")
    p.add_argument("--period", type=int, default=60)

    p = sub.add_parser("list-markets", help="List markets")
    p.add_argument("--status", default="open")
    p.add_argument("--series", default="")
    p.add_argument("--event", default="")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("get-market", help="Get market detail")
    p.add_argument("ticker")

    p = sub.add_parser("orderbook", help="Get market orderbook")
    p.add_argument("ticker")
    p.add_argument("--depth", type=int, default=0)

    p = sub.add_parser("candles", help="Market candlesticks")
    p.add_argument("ticker")
    p.add_argument("--period", type=int, default=60)

    p = sub.add_parser("trades", help="Public trades")
    p.add_argument("--ticker", default="")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("historical-trades", help="Historical trades")
    p.add_argument("--ticker", default="")

    p = sub.add_parser("historical-markets", help="Historical markets")
    p.add_argument("--series", default="")

    return parser


def run_noninteractive(args):
    """Dispatch CLI subcommands to ``_get`` with the same relative paths as the interactive menu (JSON or compact lines)."""
    cmd = args.command
    if cmd == "exchange-status":
        data = _get("/exchange/status")
        print(json.dumps(data, indent=2))
    elif cmd == "exchange-schedule":
        data = _get("/exchange/schedule")
        print(json.dumps(data, indent=2))
    elif cmd == "list-series":
        data = _get("/series", params={"limit": args.limit})
        if data:
            for s in data.get("series", []):
                print(f"{s['ticker']:20s} {s.get('title', '')[:50]}")
    elif cmd == "get-series":
        data = _get(f"/series/{args.ticker}")
        print(json.dumps(data, indent=2))
    elif cmd == "list-events":
        params = {"limit": args.limit}
        if args.status:
            params["status"] = args.status
        if args.series:
            params["series_ticker"] = args.series
        data = _get("/events", params=params)
        if data:
            for e in data.get("events", []):
                print(f"{e['event_ticker']:30s} {e.get('title', '')[:50]}")
    elif cmd == "get-event":
        data = _get(f"/events/{args.ticker}")
        print(json.dumps(data, indent=2))
    elif cmd == "event-candles":
        data = _get(f"/events/{args.ticker}/candlesticks", params={"period_interval": args.period})
        print(json.dumps(data, indent=2))
    elif cmd == "list-markets":
        params = {"limit": args.limit}
        if args.status:
            params["status"] = args.status
        if args.series:
            params["series_ticker"] = args.series
        if args.event:
            params["event_ticker"] = args.event
        data = _get("/markets", params=params)
        if data:
            for m in data.get("markets", []):
                price = m.get("yes_bid_dollars", "?")
                print(f"{m['ticker']:30s} ${price:>6s}  {m.get('title', '')[:40]}")
    elif cmd == "get-market":
        data = _get(f"/markets/{args.ticker}")
        print(json.dumps(data, indent=2))
    elif cmd == "orderbook":
        params = {}
        if args.depth:
            params["depth"] = args.depth
        data = _get(f"/markets/{args.ticker}/orderbook", params=params)
        print(json.dumps(data, indent=2))
    elif cmd == "candles":
        data = _get(f"/markets/{args.ticker}/candlesticks", params={"period_interval": args.period})
        print(json.dumps(data, indent=2))
    elif cmd == "trades":
        params = {"limit": args.limit}
        if args.ticker:
            params["ticker"] = args.ticker
        data = _get("/markets/trades", params=params)
        print(json.dumps(data, indent=2))
    elif cmd == "historical-trades":
        params = {"limit": 20}
        if args.ticker:
            params["ticker"] = args.ticker
        data = _get("/historical/trades", params=params)
        print(json.dumps(data, indent=2))
    elif cmd == "historical-markets":
        params = {"limit": 20}
        if args.series:
            params["series_ticker"] = args.series
        data = _get("/historical/markets", params=params)
        print(json.dumps(data, indent=2))
    else:
        print(f"Unknown command: {cmd}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    """Entry point: if argv includes a subcommand, run ``run_noninteractive``; else print banner and ``interactive_loop``."""
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        print("\n  Kalshi Explorer - Public Market Data")
        print("  ------------------------------------")
        print(f"  Base URL: {BASE_URL}")
        print(f"  No API key needed - all endpoints are public.")
        print()
        interactive_loop()


if __name__ == "__main__":
    main()
