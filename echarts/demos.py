#!/usr/bin/env python3
"""
demos -- MECE dashboard demo set for ai_development/dashboards.

Fourteen end-to-end dashboard scenarios that collectively exercise
every PRISM-facing capability of the dashboard system: 26 chart
types, 8 widget kinds, 9 filter types, 4 brush types, 4 sync values,
5 annotation types, 3 chart-widget variants (spec / ref / option),
the persistence + diagnostics workflow, and the prose / markdown
surfaces.

Note: the legacy `make_echart()` and composite (make_2pack_*,
make_4pack_grid, etc.) helpers are NOT exercised here; PRISM ships
one-off conversational charts via Altair `make_chart()`, not via
this module. See README sections 1, 2, 5 for the scope.

    rates_monitor       8-tab rates monitor: US curve (overview /
                        detail / macro overlay) PLUS 5 identical-
                        shape global central-bank tabs.
    risk_regime         correlation_matrix on % changes (dedicated
                        builder), VIX term by regime, factor
                        scatter_multi vs MKT with per-group OLS,
                        boxplots, drawdown with arrow / band /
                        point annotations + lineX brush.
    fomc_monitor        Fed policy: gauge (cut prob), candlestick
                        (FFR futures), radar (voter hawk-dove),
                        calendar heatmap, strokeDash dot plot,
                        dual-axis, metadata, header_actions.
    global_flows        Cross-border flows: sankey + donut,
                        treemap + sunburst, network graph, funnel,
                        stat_grid, hierarchical tree (org chart).
    equity_deep_dive    Single-name tear sheet: candlestick + volume,
                        EPS strokeDash, bar_horizontal, beta scatter-
                        trendline, bullet, histogram, y_log toggle,
                        KPI info/popup.
    portfolio_analytics Multi-asset book: pinned KPI ribbon, VaR
                        gauge, factor radar, allocation pie, stacked-
                        area P&L, parallel_coords positions,
                        histogram, stat_grid, lineY brush.
    markets_wrap        Cross-asset EOD wrap: 17 charts, KPI ribbon,
                        image widget (logo), divider widgets, click-
                        emit-filter, conditional-formatted top movers
                        table, legend sync, filter "*" wildcard.
    screener_studio     Three-tab toolbox: rich RV screen w/
                        conditional formatting + z-score colors, all
                        9 filter types on one dataset, bond universe
                        screener with row_click.detail rich modal.
    bond_carry_roll     Carry/roll scatter where every point is
                        clickable: chart click_popup rich modal
                        (per-bond stats, issuer blurb, spread + price
                        history filtered by CUSIP, recent events).
    news_wrap           Intraday news desk: summary banner, six
                        semantic note kinds, sortable headlines table
                        with full-body markdown drilldown, per-asset
                        commentary, calendar + reading list.
    fomc_brief          Document-first FOMC dashboard: statement diff
                        narrative, minutes excerpts (blockquotes), Fed
                        speakers table w/ row-click verbatim quote
                        modal + hawk-dove bar chart, dot plot panel.
    research_feed       Substack-style aggregator: featured + theme
                        notes, curated reading list, full article feed
                        with row-click drilldown surfacing each piece's
                        full markdown body.
    macro_studio        Interactive bivariate analysis: scatter_studio
                        centerpiece (full feature surface), correlation_
                        matrix sidebar, 4-axis macro overlay
                        (mapping.axes), log-scale credit chart,
                        polygon brush.
    dev_workflow        Lifecycle showcase: manifest_template +
                        populate_template, validate_manifest,
                        chart_data_diagnostics, strict=False mode,
                        save_pngs=True. Three chart variants
                        (spec / option / ref) and `raw` chart_type.
                        KPI direct value + format=raw + controls-
                        drawer opt-out flags. header_actions onclick.

All data is synthetic and deterministic (SEED-controlled). Every demo
follows the PRISM pattern: pull DataFrame(s), drop into a manifest,
call `compile_dashboard()`. Literal numbers never appear in the
manifest emitted by PRISM.

Run
---

    python demos.py                         interactive menu
    python demos.py --all                   run every demo
    python demos.py --demo screener_studio  run one
    python demos.py --list                  list demos and exit
    python demos.py --open                  auto-open the gallery in browser
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from echart_dashboard import (
    compile_dashboard,
    manifest_template,
    populate_template,
    validate_manifest,
    chart_data_diagnostics,
)
from rendering import save_dashboard_html_png


SEED = 42
END_DATE = "2026-04-22"


# =============================================================================
# DATA GENERATORS (synthetic, deterministic)
# =============================================================================
#
# Each generator returns a pandas DataFrame with a clean schema. Demos pass
# them straight into a manifest's `datasets` block -- the dashboard compiler
# normalizes DataFrames -> canonical list-of-lists form internally.


def pull_rates_panel(days: int = 252) -> pd.DataFrame:
    """US Treasury yields (2/5/10/30Y) + derived spreads."""
    random.seed(SEED)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    y2, y5, y10, y30 = 4.05, 4.22, 4.31, 4.48
    rows = []
    for d in dates:
        y2 = max(0.5, y2 + random.gauss(0, 0.018))
        y5 = max(0.8, y5 + random.gauss(0, 0.017))
        y10 = max(1.2, y10 + random.gauss(0, 0.016))
        y30 = max(1.5, y30 + random.gauss(0, 0.014))
        rows.append({"date": d,
                      "us_2y": round(y2, 3), "us_5y": round(y5, 3),
                      "us_10y": round(y10, 3), "us_30y": round(y30, 3)})
    df = pd.DataFrame(rows)
    df["2s10s"] = ((df["us_10y"] - df["us_2y"]) * 100).round(1)
    df["5s30s"] = ((df["us_30y"] - df["us_5y"]) * 100).round(1)
    df["10y_real"] = (df["us_10y"] - 2.2).round(3)
    return df


def pull_ism(n_months: int = 72) -> pd.DataFrame:
    """ISM Manufacturing PMI, monthly."""
    random.seed(SEED + 2)
    dates = pd.date_range(end=END_DATE, periods=n_months, freq="MS")
    ism = 52.0
    rows = []
    for d in dates:
        ism += random.gauss(0, 1.1)
        ism = max(38, min(62, ism))
        rows.append({"date": d, "ism": round(ism, 1)})
    return pd.DataFrame(rows)


def pull_cross_asset(days: int = 252) -> pd.DataFrame:
    """SPX, DXY, WTI, Gold daily."""
    random.seed(SEED + 1)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    spx, dxy, wti, gold = 5100.0, 104.0, 82.0, 2320.0
    rows = []
    for d in dates:
        spx *= 1 + random.gauss(0.0004, 0.0095)
        dxy += random.gauss(0, 0.22)
        wti += random.gauss(0, 0.75)
        gold *= 1 + random.gauss(0.00025, 0.0075)
        rows.append({"date": d,
                      "spx": round(spx, 2), "dxy": round(dxy, 2),
                      "wti": round(wti, 2), "gold": round(gold, 2)})
    return pd.DataFrame(rows)


_CORR_SEEDS = {
    ("SPX", "NDX"): 0.88, ("SPX", "10Y"): -0.18,
    ("SPX", "DXY"): -0.32, ("SPX", "Gold"): 0.05,
    ("SPX", "WTI"): 0.22, ("SPX", "Bitcoin"): 0.45,
    ("10Y", "2Y"): 0.72, ("10Y", "DXY"): 0.28,
    ("10Y", "Gold"): -0.22, ("DXY", "Gold"): -0.48,
    ("Gold", "WTI"): 0.18, ("NDX", "Bitcoin"): 0.52,
    ("NDX", "DXY"): -0.28, ("NDX", "10Y"): -0.20,
    ("Bitcoin", "DXY"): -0.15, ("WTI", "DXY"): -0.30,
    ("2Y", "DXY"): 0.35,
}


def pull_correlation_matrix() -> pd.DataFrame:
    """Cross-asset correlation matrix (rolling 6M)."""
    assets = ["SPX", "NDX", "10Y", "2Y", "DXY", "Gold", "WTI", "Bitcoin"]
    random.seed(SEED + 40)
    rows = []
    for a in assets:
        for b in assets:
            if a == b:
                c = 1.0
            elif (a, b) in _CORR_SEEDS:
                c = _CORR_SEEDS[(a, b)]
            elif (b, a) in _CORR_SEEDS:
                c = _CORR_SEEDS[(b, a)]
            else:
                c = round(random.uniform(-0.3, 0.3), 2)
            rows.append({"a": a, "b": b, "corr": c})
    return pd.DataFrame(rows)


def pull_vix_term() -> pd.DataFrame:
    """VIX term structure at a few regime snapshots."""
    tenors = ["1M", "2M", "3M", "6M", "9M", "1Y"]
    data = {
        "Normal backwardation (2021)":   [20.5, 22.0, 23.1, 24.3, 25.0, 25.4],
        "Flat (current)":                  [15.2, 15.8, 16.5, 17.2, 17.8, 18.3],
        "Inverted stress (Mar 2020)":      [70.0, 58.0, 48.0, 40.0, 36.0, 33.0],
        "Contango calm (Jul 2024)":        [13.1, 14.8, 15.9, 16.7, 17.2, 17.5],
    }
    rows = []
    for regime, values in data.items():
        for t, v in zip(tenors, values):
            rows.append({"regime": regime, "tenor": t, "vix": v})
    return pd.DataFrame(rows)


def pull_factor_returns() -> pd.DataFrame:
    """Monthly returns for standard equity factors."""
    random.seed(SEED + 14)
    factors = ["MKT", "VAL", "MOM", "SIZE", "QUAL", "LOWVOL"]
    dates = pd.date_range("2020-01-01", END_DATE, freq="MS")
    rows = []
    for d in dates:
        for f in factors:
            sigma = {"MKT": 4.2, "VAL": 3.0, "MOM": 3.8,
                      "SIZE": 2.5, "QUAL": 2.0, "LOWVOL": 1.8}[f]
            rows.append({"date": d, "factor": f,
                           "ret_pct": round(random.gauss(0.3, sigma), 2)})
    return pd.DataFrame(rows)


def pull_corr_panel(years: int = 3) -> pd.DataFrame:
    """Wide-form panel of cross-asset daily prices for the
    `correlation_matrix` chart_type (which computes its own correlation
    after applying the per-column transform). Columns: date + 8 assets."""
    random.seed(SEED + 70)
    dates = pd.date_range(end=END_DATE, periods=252 * years, freq="B")
    spx = 5100.0
    ndx = 17800.0
    us_10y = 4.31
    us_2y = 4.05
    dxy = 104.0
    gold = 2320.0
    wti = 82.0
    btc = 65000.0
    rows = []
    for _ in dates:
        s_shock = random.gauss(0, 1)
        spx *= 1 + 0.0003 + 0.009 * s_shock
        ndx *= 1 + 0.0004 + 0.011 * (0.85 * s_shock + 0.4 * random.gauss(0, 1))
        us_10y = max(0.5, us_10y + 0.018 * (-0.20 * s_shock + random.gauss(0, 1)))
        us_2y = max(0.5, us_2y + 0.018 * (0.72 * (us_10y - 4.31) / 0.018
                                              + random.gauss(0, 1)))
        dxy += 0.22 * (-0.30 * s_shock + random.gauss(0, 1))
        gold *= 1 + 0.005 * (-0.45 * (dxy - 104.0) / 0.22 + random.gauss(0, 1))
        wti += 0.75 * (0.20 * s_shock + random.gauss(0, 1))
        btc *= 1 + 0.025 * (0.50 * s_shock + random.gauss(0, 1))
    # Re-iterate with cached values to fill rows in chronological order
    random.seed(SEED + 70)
    spx = 5100.0
    ndx = 17800.0
    us_10y = 4.31
    us_2y = 4.05
    dxy = 104.0
    gold = 2320.0
    wti = 82.0
    btc = 65000.0
    rows = []
    for d in dates:
        s_shock = random.gauss(0, 1)
        spx *= 1 + 0.0003 + 0.009 * s_shock
        ndx *= 1 + 0.0004 + 0.011 * (0.85 * s_shock + 0.4 * random.gauss(0, 1))
        us_10y = max(0.5, us_10y + 0.018 * (-0.20 * s_shock + random.gauss(0, 1)))
        us_2y = max(0.5, us_2y + 0.013 * (0.72 * s_shock + random.gauss(0, 1)))
        dxy += 0.22 * (-0.30 * s_shock + random.gauss(0, 1))
        gold *= 1 + 0.0055 * (-0.45 * s_shock + random.gauss(0, 1))
        wti += 0.75 * (0.20 * s_shock + random.gauss(0, 1))
        btc *= 1 + 0.025 * (0.50 * s_shock + random.gauss(0, 1))
        rows.append({
            "date":      d,
            "spx":       round(spx, 2),
            "ndx":       round(ndx, 2),
            "us_10y":    round(us_10y, 3),
            "us_2y":     round(us_2y, 3),
            "dxy":       round(dxy, 2),
            "gold":      round(gold, 1),
            "wti":       round(wti, 2),
            "bitcoin":   round(btc, 0),
        })
    return pd.DataFrame(rows)


def pull_factor_vs_mkt(n_months: int = 60) -> pd.DataFrame:
    """Paired (market, factor) monthly returns -- one row per
    factor x month -- with realistic per-factor betas to MKT.
    Shape suits scatter_multi with `color: factor` + `trendlines: true`
    so each factor gets its own OLS line."""
    random.seed(SEED + 71)
    factor_betas = {
        "VAL":    (0.85, 2.4),
        "MOM":    (1.05, 3.0),
        "QUAL":   (0.55, 1.7),
        "SIZE":   (0.95, 2.6),
        "LOWVOL": (0.40, 1.5),
    }
    dates = pd.date_range(end=END_DATE, periods=n_months, freq="MS")
    rows = []
    for d in dates:
        mkt = round(random.gauss(0.6, 4.0), 2)
        for f, (beta, sigma) in factor_betas.items():
            ret = round(beta * mkt + random.gauss(0, sigma), 2)
            rows.append({"date": d, "factor": f,
                          "mkt_pct": mkt, "factor_pct": ret})
    return pd.DataFrame(rows)


def pull_drawdown() -> pd.DataFrame:
    """Simulated equity drawdown curve for regime analysis."""
    random.seed(SEED + 41)
    dates = pd.date_range(end=END_DATE, periods=252 * 5, freq="B")
    level = 100.0
    peak = 100.0
    rows = []
    for d in dates:
        level *= 1 + random.gauss(0.0004, 0.011)
        if random.random() < 0.003:
            level *= 1 - abs(random.gauss(0, 0.015))
        peak = max(peak, level)
        rows.append({"date": d, "level": round(level, 2),
                      "drawdown_pct": round(100 * (level - peak) / peak, 2)})
    return pd.DataFrame(rows)


def pull_rates_rv_rich() -> pd.DataFrame:
    """Extended RV screen with per-row metadata for rich tables:
    asset_class, bucket, ytd change, percentile as fraction, note-for-tooltip.
    """
    return pd.DataFrame([
        {"metric": "2s10s",        "asset_class": "Rates",  "bucket": "Curve",    "current": 38,   "low_5y": -60, "high_5y": 120, "z": 0.9,  "pct": 0.73, "ytd_chg": -12, "note": "Bear steepener YTD, back above Fed dots."},
        {"metric": "5s30s",        "asset_class": "Rates",  "bucket": "Curve",    "current": -5,   "low_5y": -30, "high_5y": 80,  "z": -1.4, "pct": 0.15, "ytd_chg": -28, "note": "Aggressive flattening vs 5Y range, extreme."},
        {"metric": "2s5s",         "asset_class": "Rates",  "bucket": "Curve",    "current": -8,   "low_5y": -35, "high_5y": 45,  "z": -0.6, "pct": 0.31, "ytd_chg": -11, "note": "Belly tight; signals positioning unwind."},
        {"metric": "10Y real",     "asset_class": "Rates",  "bucket": "Real",     "current": 1.85, "low_5y": -1.2,"high_5y": 2.6, "z": 0.2,  "pct": 0.48, "ytd_chg": -0.4,"note": "Near 5Y median; term premium re-building."},
        {"metric": "5Y5Y infl",    "asset_class": "Rates",  "bucket": "Infl.",    "current": 2.38, "low_5y": 1.7, "high_5y": 3.0, "z": -0.8, "pct": 0.34, "ytd_chg": -0.25,"note": "Sub-anchored but above Fed 2% target."},
        {"metric": "30Y TIPS BE",  "asset_class": "Rates",  "bucket": "Infl.",    "current": 2.18, "low_5y": 1.4, "high_5y": 2.8, "z": 0.1,  "pct": 0.62, "ytd_chg": -0.12,"note": "Median; long-run inflation well-anchored."},
        {"metric": "USDJPY 1M",    "asset_class": "FX",     "bucket": "Vol",      "current": 9.4,  "low_5y": 4.8, "high_5y": 22.5,"z": -1.8, "pct": 0.08, "ytd_chg": -3.1, "note": "Extreme low vol; complacency indicator."},
        {"metric": "MOVE index",   "asset_class": "Rates",  "bucket": "Vol",      "current": 102,  "low_5y": 55,  "high_5y": 185, "z": 0.3,  "pct": 0.58, "ytd_chg": 15,   "note": "Elevated vs pre-2022; policy repricing."},
        {"metric": "VIX 1M",       "asset_class": "Equity", "bucket": "Vol",      "current": 16.5, "low_5y": 11,  "high_5y": 82,  "z": -0.6, "pct": 0.35, "ytd_chg": 2.1,  "note": "Below median; macro risk appetite constructive."},
        {"metric": "HY OAS",       "asset_class": "Credit", "bucket": "Spread",   "current": 285,  "low_5y": 275, "high_5y": 1100,"z": -1.1, "pct": 0.12, "ytd_chg": -38,  "note": "Tight vs regime; risk-asset friendly."},
        {"metric": "IG OAS",       "asset_class": "Credit", "bucket": "Spread",   "current": 92,   "low_5y": 80,  "high_5y": 265, "z": -1.0, "pct": 0.15, "ytd_chg": -11,  "note": "Very tight; demand technicals dominate."},
        {"metric": "CDX IG 5Y",    "asset_class": "Credit", "bucket": "Spread",   "current": 58,   "low_5y": 50,  "high_5y": 140, "z": -0.9, "pct": 0.18, "ytd_chg": -6,   "note": "Index tight; overlay-friendly."},
        {"metric": "DXY",          "asset_class": "FX",     "bucket": "Level",    "current": 104.5,"low_5y": 89,  "high_5y": 115, "z": 0.5,  "pct": 0.68, "ytd_chg": 1.2,  "note": "Range-bound; yield-diff driven."},
        {"metric": "EURUSD",       "asset_class": "FX",     "bucket": "Level",    "current": 1.085,"low_5y": 0.96,"high_5y": 1.23,"z": -0.4, "pct": 0.42, "ytd_chg": -0.02,"note": "Below median; growth differentials."},
        {"metric": "Gold $/oz",    "asset_class": "Commodity","bucket": "Level",  "current": 2520, "low_5y": 1620,"high_5y": 2810,"z": 1.3,  "pct": 0.85, "ytd_chg": 185,  "note": "Near ATH; central bank bid persistent."},
        {"metric": "WTI $/bbl",    "asset_class": "Commodity","bucket": "Level",  "current": 68,   "low_5y": 20,  "high_5y": 130, "z": -0.3, "pct": 0.44, "ytd_chg": -6.5, "note": "Below 5Y median; demand soft patch."},
    ])


def pull_active_filters_demo() -> pd.DataFrame:
    """Diverse per-row dataset for the filter showcase. Each row represents a
    hypothetical trade/ticker snapshot so every filter type has real bite.
    """
    random.seed(SEED + 60)
    sectors = ["Tech", "Financials", "Energy", "Healthcare", "Consumer"]
    regions = ["US", "EU", "UK", "Japan", "EM"]
    ratings = ["AAA", "AA", "A", "BBB", "BB"]
    dates = pd.date_range("2024-01-01", END_DATE, freq="W-FRI")
    rows = []
    for d in dates:
        n = random.randint(5, 12)
        for _ in range(n):
            sec = random.choice(sectors)
            reg = random.choice(regions)
            rat = random.choice(ratings)
            vol = max(5, random.gauss(18, 7))
            ret = random.gauss(0.5, 2.4)
            mcap = max(1, random.gauss(25, 20))
            is_tech = sec == "Tech"
            rows.append({
                "date": d, "sector": sec, "region": reg,
                "rating": rat, "volatility": round(vol, 2),
                "return_pct": round(ret, 2), "mcap_b": round(mcap, 1),
                "is_tech": is_tech,
                "ticker": f"{sec[:3].upper()}-{reg[:2]}{random.randint(100, 999)}",
            })
    return pd.DataFrame(rows)


# =============================================================================
# DEMO BUILDERS
# =============================================================================

def _pull_cb_policy_rates(days: int = 252 * 3) -> pd.DataFrame:
    """Policy rate history for 5 major central banks. Each bank steps
    +/-25 bp on deterministic meeting days ~8 per year so the history
    actually shows movement."""
    random.seed(SEED + 500)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    rates = {"fed": 5.375, "ecb": 4.00, "boe": 5.25,
              "boj": 0.50, "cb_em": 11.25}
    meeting_step = 32
    meeting_days = list(range(meeting_step // 2, days, meeting_step))
    rows = []
    bias = {"fed": -1, "ecb": -1, "boe": -1, "boj": +1, "cb_em": -2}
    for i, d in enumerate(dates):
        if i in meeting_days:
            for k in rates:
                step = 25 * random.choice([-1, 0, 0, 0, 0, 1]) + 25 * bias[k]
                if random.random() < 0.55:
                    rates[k] = max(0.0, round(rates[k] + step / 100, 3))
        rows.append({"date": d, **rates})
    return pd.DataFrame(rows)


def _pull_cb_recent_decisions() -> pd.DataFrame:
    """Recent 15 decisions per CB with bp change (long-form).
    Month column formatted as ``Mon YY`` so the x-axis stays readable
    without date-parsing magic in the bar builder.
    """
    random.seed(SEED + 501)
    banks = ["Fed", "ECB", "BoE", "BoJ", "EM agg"]
    rows = []
    months = pd.date_range("2024-06-01", "2026-04-01", freq="MS")[-15:]
    for m in months:
        label = m.strftime("%b %y")
        for b in banks:
            ch = random.choice([0, 0, 0, -25, -25, -50, 25])
            rows.append({"month": label, "cb": b, "bp_change": ch})
    return pd.DataFrame(rows)


def build_rates_monitor(out_dir: Path) -> Dict[str, Any]:
    """Full rates monitor: US curve (overview / detail / macro-overlay)
    plus 5 identical-shape global central-bank tabs. Stress-tests a
    high-tab-count layout (8 tabs) with a mix of time-series, dual-axis,
    annotations, brush cross-filter, KPI sparklines, and repeat-shape
    gauge + decisions-bar patterns."""
    df_rates = pull_rates_panel()
    df_ism = pull_ism()
    df_cb = _pull_cb_policy_rates()
    df_dec = _pull_cb_recent_decisions()

    cb_decisions = {}
    for cb_label, cb_name in [("fed", "Fed"), ("ecb", "ECB"),
                                ("boe", "BoE"), ("boj", "BoJ"),
                                ("em", "EM agg")]:
        cb_decisions[f"dec_{cb_label}"] = (
            df_dec[df_dec["cb"] == cb_name]
            .drop(columns=["cb"])
            .reset_index(drop=True)
        )
    cb_probs = {
        "prob_fed": pd.DataFrame([{"p": 68}]),
        "prob_ecb": pd.DataFrame([{"p": 82}]),
        "prob_boe": pd.DataFrame([{"p": 55}]),
        "prob_boj": pd.DataFrame([{"p":  5}]),
        "prob_em":  pd.DataFrame([{"p": 48}]),
    }

    datasets = {"rates": df_rates, "ism_monthly": df_ism,
                 "cb_rates": df_cb}
    datasets.update(cb_decisions)
    datasets.update(cb_probs)

    def _cb_tab(tab_id: str, label: str, cb_key: str,
                 cb_label: str) -> Dict[str, Any]:
        return {
            "id": tab_id, "label": label,
            "description": f"{cb_label} policy rate + recent decisions.",
            "rows": [
                [
                    {"widget": "kpi", "id": f"k_rate_{tab_id}",
                      "w": 3, "label": f"{cb_label} policy rate",
                      "source": f"cb_rates.latest.{cb_key}",
                      "delta_source": f"cb_rates.prev.{cb_key}",
                      "sparkline_source": f"cb_rates.{cb_key}",
                      "suffix": "%", "decimals": 3},
                    {"widget": "kpi", "id": f"k_cut_{tab_id}",
                      "w": 3, "label": "Cut prob (next)",
                      "value": int(cb_probs[f"prob_{tab_id}"]["p"].iloc[0]),
                      "format": "compact", "suffix": "%",
                      "decimals": 0},
                    {"widget": "kpi", "id": f"k_eoy_{tab_id}",
                      "w": 3,
                      "label": "EOY 2026 implied (bp)",
                      "value": -75, "suffix": " bp", "decimals": 0},
                    {"widget": "kpi", "id": f"k_real_{tab_id}",
                      "w": 3,
                      "label": "Real policy rate",
                      "value": 1.8, "suffix": "%", "decimals": 2,
                      "sub": "policy rate \u2212 core CPI"},
                ],
                [
                    {"widget": "chart",
                      "id": f"chart_rate_{tab_id}",
                      "w": 8, "h_px": 320,
                      "spec": {
                          "chart_type": "line", "dataset": "cb_rates",
                          "mapping": {"x": "date", "y": cb_key,
                                        "y_title": "Policy rate (%)",
                                        "x_date_format": "auto",
                                        "legend_position": "none",
                                        "series_labels": {
                                            cb_key: cb_label}},
                          "title": f"{cb_label} policy rate"}},
                    {"widget": "chart",
                      "id": f"chart_gauge_{tab_id}",
                      "w": 4, "h_px": 320,
                      "spec": {
                          "chart_type": "gauge",
                          "dataset": f"prob_{tab_id}",
                          "mapping": {"value": "p",
                                        "name": "Cut prob",
                                        "min": 0, "max": 100},
                          "title": "Cut prob (next meeting, %)"}},
                ],
                [
                    {"widget": "chart",
                      "id": f"chart_dec_{tab_id}",
                      "w": 12, "h_px": 260,
                      "spec": {
                          "chart_type": "bar",
                          "dataset": f"dec_{tab_id}",
                          "mapping": {
                              "x": "month", "y": "bp_change",
                              "y_title": "Decision (bp)",
                              "legend_position": "none"},
                          "title": "Recent decisions",
                          "annotations": [
                              {"type": "hline", "y": 0,
                                "color": "#718096",
                                "style": "dashed", "label": ""},
                          ]}},
                ],
            ],
        }

    manifest = {
        "schema_version": 1,
        "id": "rates_monitor",
        "title": "Rates monitor (US + global CB)",
        "description": ("US Treasury curve, macro overlay, plus "
                         "identical-shape tabs for the 5 major central "
                         "banks. Stress-tests an 8-tab layout with a "
                         "mix of dual-axis, brush cross-filter, gauges, "
                         "KPI sparklines, and bar/line primitives."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "kerberos": "goyairl",
            "dashboard_id": "rates_monitor",
            "data_as_of": "2026-04-24T15:00:00Z",
            "generated_at": "2026-04-24T15:05:00Z",
            "sources": ["GS Market Data", "FRED", "BIS"],
            "refresh_frequency": "daily",
            "refresh_enabled": True,
            "tags": ["rates", "policy", "global"],
            "summary": {
                "title": "Today's read",
                "body": (
                    "Front-end has richened ~6bp into the close on a "
                    "softer print and a dovish-leaning Fed speaker. "
                    "The curve **bull-steepened**, with 2s10s widening "
                    "out of the inversion zone for the first time in "
                    "three weeks.\n\n"
                    "1. 2Y -6bp, 10Y -3bp: classic bull-steepener\n"
                    "2. 5s30s flatter on long-end demand into auction\n"
                    "3. Real-yield curve barely moved; the move is "
                    "predominantly nominal / breakeven-driven\n\n"
                    "> Watch the 4.10% 10Y level into tomorrow's PCE; "
                    "a clean break opens the door to 4.00% as the "
                    "next pivot."
                ),
            },
            "methodology": (
                "## Sources\n\n"
                "* US Treasury OTR yields (FRED H.15)\n"
                "* Global central-bank policy rates (BIS, ECB SDW, "
                "BoE Bankstats, BoJ statistics)\n\n"
                "## Construction\n\n"
                "* Curve points are end-of-day actively-traded OTR "
                "Treasuries\n"
                "* Spreads (2s10s, 5s30s) are simple cash differences "
                "in basis points\n"
                "* 10Y real yield = 10Y nominal minus 10Y breakeven\n"
                "* Cut probabilities are derived from FFR futures "
                "settlement (CME FedWatch methodology)\n\n"
                "## Refresh\n\n"
                "* Daily after US cash close (~16:00 ET)\n"
                "* Curve and CB rates land independently; partial "
                "refreshes flag the affected widgets only"
            ),
        },
        "datasets": datasets,
        "filters": [
            {"id": "us_range", "type": "dateRange", "default": "1Y",
              "targets": ["curve", "spread", "two_ten",
                           "fives30s", "real10y", "ism_10y"],
              "field": "date", "label": "US initial range"},
            {"id": "cb_range", "type": "dateRange", "default": "2Y",
              "targets": ["chart_rate_fed", "chart_rate_ecb",
                           "chart_rate_boe", "chart_rate_boj",
                           "chart_rate_em"],
              "scope": "global",
              "field": "date", "label": "CB initial range"},
        ],
        "layout": {"kind": "tabs", "tabs": [
            {"id": "overview", "label": "US overview",
              "description": ("US Treasury curve and 2s10s spread with "
                               "brush cross-filter."),
              "rows": [
                [
                    {"widget": "kpi", "id": "k2y", "label": "2Y yield",
                      "source": "rates.latest.us_2y",
                      "sparkline_source": "rates.us_2y",
                      "delta_source": "rates.prev.us_2y",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "k10y", "label": "10Y yield",
                      "source": "rates.latest.us_10y",
                      "sparkline_source": "rates.us_10y",
                      "delta_source": "rates.prev.us_10y",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "k30y", "label": "30Y yield",
                      "source": "rates.latest.us_30y",
                      "sparkline_source": "rates.us_30y",
                      "delta_source": "rates.prev.us_30y",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "kspr", "label": "2s10s (bp)",
                      "source": "rates.latest.2s10s",
                      "sparkline_source": "rates.2s10s",
                      "delta_source": "rates.prev.2s10s",
                      "decimals": 1, "w": 3},
                ],
                [
                    {"widget": "chart", "id": "curve",
                      "w": 12, "h_px": 380,
                      "spec": {
                          "chart_type": "multi_line", "dataset": "rates",
                          "mapping": {"x": "date",
                                        "y": ["us_2y", "us_5y",
                                               "us_10y", "us_30y"],
                                        "y_title": "Yield (%)"},
                          "title": "UST yield curve"}},
                ],
                [
                    {"widget": "note", "id": "n_thesis", "w": 6,
                      "kind": "thesis",
                      "title": "Bull-steepener resumes",
                      "body": (
                          "The curve is **bull-steepening** for the "
                          "third session in a row. Front-end demand "
                          "is led by real-money buyers re-engaging "
                          "after the FOMC; long-end is range-bound.\n\n"
                          "1. 2Y -6bp on the day, -18bp on the week\n"
                          "2. 10Y -3bp on the day, -9bp on the week\n"
                          "3. Spread widening primarily front-led, "
                          "consistent with a *priced-in cut* trade")},
                    {"widget": "note", "id": "n_watch", "w": 6,
                      "kind": "watch",
                      "title": "Levels to watch",
                      "body": (
                          "| Level | Significance |\n"
                          "|---|---|\n"
                          "| 4.10% 10Y | 50dma; clean break opens 4.00% |\n"
                          "| -50bp 2s10s | recession signal floor |\n"
                          "| 4.50% 2Y | terminal-rate-implied ceiling |\n\n"
                          "Tomorrow's core PCE is the key catalyst; "
                          "consensus is 0.2% m/m / 2.7% y/y.")},
                ],
                [
                    {"widget": "chart", "id": "spread",
                      "w": 12, "h_px": 280,
                      "spec": {
                          "chart_type": "line", "dataset": "rates",
                          "mapping": {"x": "date", "y": "2s10s",
                                        "y_title": "Spread (bp)"},
                          "title": "2s10s spread",
                          "annotations": [
                              {"type": "hline", "y": 0,
                                "label": "Flat curve",
                                "color": "#c53030", "style": "dashed"},
                              {"type": "band", "y1": -50, "y2": 0,
                                "color": "#c53030", "opacity": 0.08,
                                "label": "Inverted"},
                          ]}},
                ],
                [
                    {"widget": "note", "id": "n_risk", "w": 6,
                      "kind": "risk",
                      "title": "Tail risk",
                      "body": (
                          "A hot core PCE print (>0.3% m/m) would "
                          "likely reverse the front-end rally and put "
                          "2Y yields back through 4.40%. The pain "
                          "trade is a hawkish *re-flattening* into a "
                          "long-only book that has been adding "
                          "duration on the cuts narrative.")},
                    {"widget": "note", "id": "n_context", "w": 6,
                      "kind": "context",
                      "title": "Backdrop",
                      "body": (
                          "Positioning into PCE is **light** vs the "
                          "5Y average; CFTC futures show specs net "
                          "short ~140k 10Y contracts (-0.5z). "
                          "Real-money long base from Q1 has largely "
                          "been monetized, so a hawkish surprise has "
                          "less stop-out risk than it did six weeks "
                          "ago.")},
                ],
            ]},
            {"id": "detail", "label": "US curve detail",
              "description": ("2Y / 10Y / 5s30s / 10Y real -- synced "
                               "axis & tooltip."),
              "rows": [
                [
                    {"widget": "chart", "id": "two_ten",
                      "w": 6, "h_px": 340,
                      "spec": {
                          "chart_type": "multi_line", "dataset": "rates",
                          "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"],
                                        "y_title": "Yield (%)"},
                          "title": "2Y vs 10Y"}},
                    {"widget": "chart", "id": "fives30s",
                      "w": 6, "h_px": 340,
                      "spec": {
                          "chart_type": "line", "dataset": "rates",
                          "mapping": {"x": "date", "y": "5s30s",
                                        "y_title": "5s30s (bp)"},
                          "title": "5s30s spread"}},
                ],
                [
                    {"widget": "chart", "id": "real10y",
                      "w": 12, "h_px": 300,
                      "spec": {
                          "chart_type": "line", "dataset": "rates",
                          "mapping": {"x": "date", "y": "10y_real",
                                        "y_title": "10Y real yield (%)"},
                          "title": "10Y real yield",
                          "annotations": [{
                              "type": "hline", "y": 2.0,
                              "label": "Tightening threshold",
                              "color": "#666", "style": "dashed"}]}},
                ],
                [
                    {"widget": "markdown", "id": "method", "w": 12,
                      "content": (
                          "### Method\n\n"
                          "Synthetic UST panel. **Brush** the curve "
                          "on the Overview tab to filter the spread "
                          "chart by date range.\n\n"
                          "#### Reading the panel\n\n"
                          "1. The 2Y/10Y line carries the most "
                          "information about Fed expectations.\n"
                          "2. The 5s30s spread is the cleanest "
                          "duration-only barometer.\n"
                          "3. The real-yield series strips inflation "
                          "out and is closer to *true cost of capital*.\n\n"
                          "#### Reference levels\n\n"
                          "| Series | Threshold | Meaning |\n"
                          "|---|---:|---|\n"
                          "| 2s10s | `0bp` | flat -> recession watch |\n"
                          "| 5s30s | `+50bp` | normal carry regime |\n"
                          "| 10Y real | `+2.0%` | restrictive territory |\n\n"
                          "> Synthetic data; do not trade off this "
                          "panel. Real GS data is plumbed in via the "
                          "`rates` dataset reference.\n\n"
                          "Skip the dashed annotations on the spread "
                          "chart -- those are ~~policy targets~~ "
                          "shape thresholds, not central-bank levels.")},
                ],
            ]},
            {"id": "macro", "label": "US macro overlay",
              "description": ("ISM Manufacturing PMI with expansion / "
                               "contraction line + recessionary band."),
              "rows": [
                [
                    {"widget": "chart", "id": "ism_10y",
                      "w": 12, "h_px": 420,
                      "spec": {
                          "chart_type": "multi_line",
                          "dataset": "ism_monthly",
                          "mapping": {"x": "date", "y": "ism",
                                        "y_title": "ISM Mfg PMI"},
                          "title": "ISM Manufacturing",
                          "annotations": [
                              {"type": "hline", "y": 50,
                                "label": "Expansion / contraction",
                                "color": "#c53030", "style": "dashed"},
                              {"type": "band", "y1": 40, "y2": 45,
                                "label": "Recessionary zone",
                                "color": "#c53030", "opacity": 0.08},
                          ]}},
                ],
            ]},
            _cb_tab("fed", "Fed",  "fed",   "Fed"),
            _cb_tab("ecb", "ECB",  "ecb",   "ECB"),
            _cb_tab("boe", "BoE",  "boe",   "BoE"),
            _cb_tab("boj", "BoJ",  "boj",   "BoJ"),
            _cb_tab("em",  "EM",   "cb_em", "EM agg"),
        ]},
        "links": [
            {"group": "sync_main", "members": ["curve", "spread"],
              "sync": ["axis", "tooltip", "dataZoom"]},
            {"group": "brush_main", "members": ["curve", "spread"],
              "brush": {"type": "rect", "xAxisIndex": 0}},
            {"group": "sync_detail",
              "members": ["two_ten", "fives30s", "real10y"],
              "sync": ["axis", "tooltip"]},
        ],
    }

    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1500, height=1300)
    return _result(r, thumb)


def build_risk_regime(out_dir: Path) -> Dict[str, Any]:
    """Risk regime monitor: cross-asset correlation_matrix, VIX term
    structure by regime, scatter_multi factor vs MKT, running drawdown."""
    df_panel = pull_corr_panel()
    df_vix = pull_vix_term()
    df_fac = pull_factor_returns()
    df_fvm = pull_factor_vs_mkt()
    df_dd = pull_drawdown()

    manifest = {
        "schema_version": 1,
        "id": "risk_regime",
        "title": "Risk regime monitor",
        "description": ("Cross-asset correlation_matrix on % changes, "
                         "VIX term structure across regimes, factor "
                         "scatter_multi vs MKT with per-group OLS, "
                         "factor-return boxplots, and running drawdown "
                         "with arrow + band annotations."),
        "theme": "gs_clean",
        "datasets": {
            "corr_panel": df_panel,
            "vix_term":  df_vix,
            "factors":   df_fac,
            "fvm":       df_fvm,
            "drawdown":  df_dd,
        },
        "layout": {"rows": [
            [
                {"widget": "chart", "id": "corr", "w": 6, "h_px": 420,
                  "title": "Cross-asset correlation (% change)",
                  "subtitle": ("Pearson r over the visible window; "
                                "computed by the correlation_matrix "
                                "builder from the wide-form panel."),
                  "spec": {
                      "chart_type": "correlation_matrix",
                      "dataset": "corr_panel",
                      "mapping": {
                          "columns": ["spx", "ndx", "us_10y", "us_2y",
                                       "dxy", "gold", "wti", "bitcoin"],
                          "method":      "pearson",
                          "transform":   "pct_change",
                          "order_by":    "date",
                          "min_periods": 30,
                          "show_values": True,
                          "value_decimals": 2}}},
                {"widget": "chart", "id": "vix", "w": 6, "h_px": 420,
                  "spec": {
                      "chart_type": "multi_line", "dataset": "vix_term",
                      "mapping": {
                          "x": "tenor", "y": "vix", "color": "regime",
                          "x_type": "category",
                          "x_sort": ["1M", "2M", "3M", "6M", "9M", "1Y"],
                          "y_title": "VIX (implied vol)"},
                      "title": "VIX term structure by regime",
                      "annotations": [
                          {"type": "hline", "y": 20,
                            "label": "Stress threshold",
                            "color": "#c53030", "style": "dashed"},
                      ]}},
            ],
            [
                {"widget": "chart", "id": "fvm_scatter", "w": 6, "h_px": 380,
                  "title": "Factor returns vs MKT (per-group OLS)",
                  "subtitle": "scatter_multi with trendlines per factor.",
                  "spec": {
                      "chart_type": "scatter_multi", "dataset": "fvm",
                      "mapping": {"x": "mkt_pct", "y": "factor_pct",
                                    "color": "factor",
                                    "trendlines": True,
                                    "x_title": "MKT monthly return (%)",
                                    "y_title": ("Factor monthly "
                                                 "return (%)")},
                      "annotations": [
                          {"type": "hline", "y": 0, "color": "#aaa",
                            "style": "dashed"},
                          {"type": "vline", "x": 0, "color": "#aaa",
                            "style": "dashed"}]}},
                {"widget": "chart", "id": "factors", "w": 6, "h_px": 380,
                  "spec": {
                      "chart_type": "boxplot", "dataset": "factors",
                      "mapping": {"x": "factor", "y": "ret_pct",
                                    "y_title": "Monthly return (%)"},
                      "title": "Factor returns (last 5Y)",
                      "annotations": [
                          {"type": "hline", "y": 0, "label": "",
                            "color": "#718096", "style": "dashed"},
                      ]}},
            ],
            [
                {"widget": "chart", "id": "drawdown", "w": 12, "h_px": 360,
                  "spec": {
                      "chart_type": "line", "dataset": "drawdown",
                      "mapping": {"x": "date", "y": "drawdown_pct",
                                    "y_title": "Drawdown (%)"},
                      "title": "Running drawdown",
                      "subtitle": ("Band marks the bear-market zone; "
                                    "arrow points from the trough to "
                                    "the recovery."),
                      "annotations": [
                          {"type": "band", "y1": -20, "y2": -100,
                            "label": "Bear-market zone",
                            "color": "#c53030", "opacity": 0.08},
                          {"type": "arrow",
                            "x1": "2022-10-12", "y1": -23.5,
                            "x2": "2023-08-01", "y2": -4.5,
                            "label": "10mo recovery",
                            "color": "#2E7D32",
                            "head_size": 9},
                          {"type": "point",
                            "x": "2022-10-12", "y": -23.5,
                            "label": "Trough",
                            "color": "#B3261E",
                            "font_size": 11},
                      ]}},
            ],
        ]},
        "links": [
            # Brush-cross-filter: drag a vertical band on the drawdown
            # chart to filter the cross-asset panel. lineX brush
            # exercises a brush type the gallery otherwise misses.
            {"group": "dd_brush", "members": ["drawdown", "corr"],
              "brush": {"type": "lineX", "xAxisIndex": 0}},
        ],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1500, height=1500)
    return _result(r, thumb)


# NOTE: the rv-table + filter-showcase scenarios are merged into
# `build_screener_studio` below (alongside the bond-screener drill-down)
# so all 3 table/filter/drill-down patterns live in one demo.


# =============================================================================
# DEMO: fomc_monitor  (self-contained: data + manifest)
# =============================================================================
#
# Chart types showcased: gauge, candlestick, radar, calendar_heatmap,
# multi_line with strokeDash (actuals vs SEP dots), dual-axis multi_line.
# Features: metadata block (refresh button + freshness badge),
# header_actions, markdown, tabs, filters, links.


def _pull_fomc_fed_funds() -> pd.DataFrame:
    """Fed funds target-rate time series (actuals) + 2Y yield for dual axis."""
    random.seed(SEED + 100)
    dates = pd.date_range(end=END_DATE, periods=252 * 3, freq="B")
    ffr = 5.375
    y2 = 4.60
    path = []
    for i, d in enumerate(dates):
        if i > 0 and random.random() < 0.003:
            ffr = max(0.25, ffr - 0.25)
        y2 = max(0.5, y2 + random.gauss(0, 0.02))
        path.append({"date": d, "fed_funds": ffr,
                      "us_2y": round(y2, 3)})
    return pd.DataFrame(path)


def _pull_fomc_dots_vs_actual() -> pd.DataFrame:
    """SEP median dot plot (projection) vs realized Fed funds.
    Long form with a 'type' column toggling Actual vs SEP so we can render
    via strokeDash on the same multi_line chart.
    """
    horizons = ["2024", "2025", "2026", "2027", "Longer run"]
    rows = []
    sep_actual = [4.75, 4.25, 3.50, 3.00, 2.75]
    sep_proj = [4.50, 3.75, 3.25, 2.75, 2.50]
    for h, a, p in zip(horizons, sep_actual, sep_proj):
        rows.append({"horizon": h, "rate_pct": a, "type": "Actual"})
        rows.append({"horizon": h, "rate_pct": p, "type": "SEP median"})
    return pd.DataFrame(rows)


def _pull_fomc_futures_ohlc() -> pd.DataFrame:
    """Fed Funds futures daily OHLC (synthetic 6-month contract)."""
    random.seed(SEED + 101)
    dates = pd.date_range(end=END_DATE, periods=120, freq="B")
    price = 95.38
    rows = []
    for d in dates:
        o = price
        move = random.gauss(0, 0.04)
        c = max(94.5, min(96.5, price + move))
        lo = min(o, c) - abs(random.gauss(0, 0.015))
        hi = max(o, c) + abs(random.gauss(0, 0.015))
        rows.append({"date": d,
                      "open": round(o, 3), "close": round(c, 3),
                      "low": round(lo, 3), "high": round(hi, 3)})
        price = c
    return pd.DataFrame(rows)


def _pull_fomc_voter_radar() -> pd.DataFrame:
    """Hawk-dove score across dimensions for 4 current FOMC voters.
    Long-form: (voter, dimension, score 0-10).
    """
    dims = ["Inflation hawk", "Growth concern",
             "Labor focus", "Financial stability", "Forward guidance"]
    voters = {
        "Chair Powell":   [6.5, 5.5, 5.5, 7.0, 8.0],
        "Gov. Bowman":    [8.5, 3.5, 4.5, 7.5, 6.0],
        "Pres. Williams": [5.5, 6.5, 6.5, 7.0, 7.5],
        "Pres. Goolsbee": [3.5, 7.5, 7.0, 5.5, 6.5],
    }
    rows = []
    for v, scores in voters.items():
        for d, s in zip(dims, scores):
            rows.append({"voter": v, "dimension": d, "score": s})
    return pd.DataFrame(rows)


def _pull_fomc_decision_calendar() -> pd.DataFrame:
    """Daily calendar with FOMC meeting-day magnitudes (-50, -25, 0, +25...).
    Non-FOMC days get a tiny placeholder so the calendar renders full-year.
    """
    random.seed(SEED + 102)
    dates = pd.date_range("2025-01-01", "2025-12-31", freq="D")
    meeting_days = [
        ("2025-01-29",  0), ("2025-03-19", +25), ("2025-05-07",  0),
        ("2025-06-18", +25), ("2025-07-30",  0), ("2025-09-17", -25),
        ("2025-10-29", -25), ("2025-12-10", -50),
    ]
    meetings = {pd.to_datetime(d): m for d, m in meeting_days}
    rows = []
    for d in dates:
        if d in meetings:
            rows.append({"date": d, "bp_change": meetings[d]})
        else:
            rows.append({"date": d, "bp_change": 0})
    return pd.DataFrame(rows)


def build_fomc_monitor(out_dir: Path) -> Dict[str, Any]:
    """FOMC policy monitor dashboard showcasing gauge, candlestick, radar,
    calendar heatmap, dual-axis multi_line, strokeDash."""
    df_ffr = _pull_fomc_fed_funds()
    df_dots = _pull_fomc_dots_vs_actual()
    df_fut = _pull_fomc_futures_ohlc()
    df_voters = _pull_fomc_voter_radar()
    df_cal = _pull_fomc_decision_calendar()
    df_probs = pd.DataFrame([{"prob": 68}])

    manifest = {
        "schema_version": 1,
        "id": "fomc_monitor",
        "title": "FOMC policy monitor",
        "description": ("Fed policy + market-implied path. Probability "
                         "gauge, FFR futures candlestick, dot plot vs "
                         "realized, voter hawk-dove radar, decision "
                         "calendar."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "kerberos": "goyairl",
            "dashboard_id": "fomc_monitor",
            "data_as_of": "2026-04-24T15:00:00Z",
            "generated_at": "2026-04-24T15:05:00Z",
            "sources": ["GS Market Data", "FRED", "CME FedWatch"],
            "refresh_frequency": "daily",
            "refresh_enabled": True,
            "tags": ["rates", "policy", "fed"],
            "version": "1.0.0",
            "methodology": {
                "title": "FOMC monitor methodology",
                "body": (
                    "## Cut probability gauge\n\n"
                    "Implied probability that the Fed delivers a 25bp "
                    "cut at the next meeting. Derived from the front-"
                    "month Fed Funds futures contract using the CME "
                    "FedWatch convention.\n\n"
                    "## FFR path candlestick\n\n"
                    "Each candle is one Fed Funds futures contract: "
                    "open / high / low / close = the implied effective "
                    "rate over the contract's reference month. Reads "
                    "left-to-right as the market-implied policy path.\n\n"
                    "## Dot plot vs realised\n\n"
                    "Dashed line is the median SEP dot at the most "
                    "recent quarterly meeting. Solid line is realised "
                    "EFFR. Gap between them is the SEP-vs-market "
                    "policy disagreement.\n\n"
                    "## Voter hawk-dove radar\n\n"
                    "Compositional score across five dimensions "
                    "(growth, inflation, employment, financial "
                    "conditions, balance sheet) sourced from public "
                    "speeches in the past 60 days. Pure heuristic; not "
                    "a formal scoring model.\n\n"
                    "## Decision calendar\n\n"
                    "One cell per FOMC meeting, color-coded by the "
                    "decision (hike / hold / cut). Hover for the "
                    "statement summary."
                ),
            },
        },
        "header_actions": [
            {"label": "FOMC calendar",
              "href": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
              "icon": "\u2197"},
            {"label": "SEP archive",
              "href": "https://www.federalreserve.gov/monetarypolicy/fomc_projtabl.htm",
              "icon": "\u2197"},
        ],
        "datasets": {
            "ffr": df_ffr,
            "dots": df_dots,
            "futures": df_fut,
            "voters": df_voters,
            "cal": df_cal,
            "probs": df_probs,
        },
        "filters": [
            {"id": "lookback", "type": "dateRange", "default": "1Y",
              "targets": ["ffr_chart", "fut_chart"],
              "field": "date", "label": "Initial range",
              "scope": "global"},
        ],
        "layout": {"kind": "tabs", "tabs": [
            {"id": "overview", "label": "Overview",
              "description": ("Market-implied path + realized "
                               "Fed funds trajectory."),
              "rows": [
                [
                    {"widget": "kpi", "id": "k_ffr", "label": "Fed funds",
                      "source": "ffr.latest.fed_funds",
                      "delta_source": "ffr.prev.fed_funds",
                      "sparkline_source": "ffr.fed_funds",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "k_2y", "label": "2Y yield",
                      "source": "ffr.latest.us_2y",
                      "delta_source": "ffr.prev.us_2y",
                      "sparkline_source": "ffr.us_2y",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "k_cut", "label": "Next-meeting cut odds",
                      "value": 68, "suffix": "%", "decimals": 0,
                      "sub": "CME FedWatch", "w": 3},
                    {"widget": "kpi", "id": "k_eoy", "label": "EOY 2026 implied",
                      "value": 3.625, "suffix": "%", "decimals": 3,
                      "sub": "3 cuts priced", "w": 3},
                ],
                [
                    {"widget": "chart", "id": "gauge_cut",
                      "w": 4, "h_px": 340,
                      "spec": {
                          "chart_type": "gauge", "dataset": "probs",
                          "mapping": {"value": "prob",
                                        "name": "Cut probability",
                                        "min": 0, "max": 100},
                          "title": "Probability of cut by next meeting",
                          "subtitle": "CME FedWatch (%)"}},
                    {"widget": "chart", "id": "ffr_chart",
                      "w": 8, "h_px": 340,
                      "spec": {
                          "chart_type": "multi_line", "dataset": "ffr",
                          "mapping": {
                              "x": "date",
                              "y": ["fed_funds", "us_2y"],
                              "y_title": "Rate (%)",
                              "x_date_format": "auto",
                              "series_labels": {
                                  "fed_funds": "Fed funds target",
                                  "us_2y": "UST 2Y"}},
                          "title": "Fed funds target vs UST 2Y",
                          "legend_position": "top",
                          "annotations": [
                              {"type": "hline", "y": 2.0,
                                "label": "Neutral rate",
                                "color": "#999", "style": "dashed"},
                          ]}},
                ],
                [
                    {"widget": "chart", "id": "fut_chart",
                      "w": 12, "h_px": 380,
                      "spec": {
                          "chart_type": "candlestick",
                          "dataset": "futures",
                          "mapping": {"x": "date",
                                        "open": "open",
                                        "close": "close",
                                        "low": "low",
                                        "high": "high"},
                          "title": ("Fed Funds futures (front month)"),
                          "subtitle": "daily OHLC"}},
                ],
            ]},
            {"id": "dots", "label": "Dots & path",
              "description": ("FOMC dot plot vs realized path + voter "
                               "profile."),
              "rows": [
                [
                    {"widget": "chart", "id": "dots_chart",
                      "w": 7, "h_px": 380,
                      "spec": {
                          "chart_type": "multi_line", "dataset": "dots",
                          "mapping": {
                              "x": "horizon", "y": "rate_pct",
                              "color": "type",
                              "strokeDash": "type",
                              "strokeDashScale": {
                                  "domain": ["Actual", "SEP median"],
                                  "range": ["solid", [6, 4]]},
                              "x_type": "category",
                              "x_sort": ["2024", "2025", "2026",
                                          "2027", "Longer run"],
                              "y_title": "Fed funds rate (%)"},
                          "title": ("Realized vs SEP median dot plot"),
                          "subtitle": ("solid = realized / market-implied, "
                                         "dashed = SEP median")}},
                    {"widget": "chart", "id": "voter_radar",
                      "w": 5, "h_px": 380,
                      "spec": {
                          "chart_type": "radar", "dataset": "voters",
                          "mapping": {"category": "dimension",
                                        "value": "score",
                                        "series": "voter"},
                          "title": "Voter hawk/dove profile",
                          "subtitle": "0 = dove, 10 = hawk"}},
                ],
                [
                    {"widget": "markdown", "id": "notes", "w": 12,
                      "content": (
                          "### Reading the dot plot\n\n"
                          "- **Solid line** = realized / market-implied "
                          "path (CME FedWatch).\n"
                          "- *Dashed line* = latest SEP median from "
                          "the FOMC's quarterly projections.\n"
                          "- A gap at `2026` = market pricing fewer "
                          "cuts than the committee signals. "
                          "Reconvergence typically happens via the "
                          "committee migrating lower between meetings.\n\n"
                          "See the full SEP archive at "
                          "[federalreserve.gov](https://www.federalreserve.gov/monetarypolicy/fomc_projtabl.htm).")},
                ],
            ]},
            {"id": "calendar", "label": "Decision calendar",
              "description": "FOMC meeting days coloured by rate change.",
              "rows": [
                [
                    {"widget": "chart", "id": "cal_heat",
                      "w": 12, "h_px": 260,
                      "spec": {
                          "chart_type": "calendar_heatmap",
                          "dataset": "cal",
                          "mapping": {"date": "date",
                                        "value": "bp_change",
                                        "year": "2025"},
                          "title": ("2025 FOMC decision calendar "
                                      "(bp change)"),
                          "palette": "gs_diverging"}},
                ],
            ]},
        ]},
        "links": [
            {"group": "sync_overview",
              "members": ["ffr_chart", "fut_chart"],
              "sync": ["axis", "tooltip", "dataZoom"]},
        ],
    }

    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1500, height=1700)
    return _result(r, thumb)


# =============================================================================
# DEMO: global_flows  (self-contained: data + manifest)
# =============================================================================
#
# Chart types showcased: sankey, donut, treemap, sunburst, graph (network),
# funnel, stat_grid. Features: tabs, multi-dataset manifest.


def _pull_global_trade_flows() -> pd.DataFrame:
    """Bilateral trade flows (USD bn). Sankey requires a DAG so we
    distinguish exporter-side nodes from importer-side nodes with a
    suffix; the result is a clean bipartite left-to-right sankey.
    """
    flows = [
        ("United States", "China",          650),
        ("United States", "Mexico",         830),
        ("United States", "Canada",         720),
        ("United States", "EU",             590),
        ("United States", "Japan",          230),
        ("United States", "UK",             145),
        ("China",         "United States",  540),
        ("China",         "EU",             700),
        ("China",         "Japan",          280),
        ("China",         "Brazil",         170),
        ("EU",            "United States",  610),
        ("EU",            "China",          290),
        ("EU",            "UK",             480),
        ("Japan",         "United States",  160),
        ("Japan",         "China",          195),
    ]
    return pd.DataFrame(
        [{"src": f"{s} \u2192",
           "tgt": f"\u2190 {t}",
           "v": v} for s, t, v in flows]
    )


def _pull_global_asset_treemap() -> pd.DataFrame:
    """Region -> country -> asset-class allocation for treemap."""
    rows = [
        ("North America", "United States", "Equities", 4200),
        ("North America", "United States", "Rates",    3100),
        ("North America", "United States", "Credit",   1400),
        ("North America", "Canada",        "Rates",     250),
        ("North America", "Canada",        "Equities",  310),
        ("Europe",        "UK",            "Rates",     520),
        ("Europe",        "UK",            "Equities",  410),
        ("Europe",        "Germany",       "Rates",     610),
        ("Europe",        "Germany",       "Equities",  320),
        ("Europe",        "France",        "Rates",     390),
        ("Europe",        "France",        "Credit",    220),
        ("APAC",          "Japan",         "Rates",     780),
        ("APAC",          "Japan",         "Equities",  420),
        ("APAC",          "China",         "Equities",  610),
        ("APAC",          "China",         "Rates",     380),
        ("APAC",          "India",         "Equities",  290),
        ("EM",            "Brazil",        "Commodities",210),
        ("EM",            "Mexico",        "Credit",    180),
        ("EM",            "Mexico",        "Equities",  140),
    ]
    return pd.DataFrame(rows, columns=["region", "country",
                                          "asset_class", "aum"])


def _pull_global_aum_funnel() -> pd.DataFrame:
    """Marketing/AUM conversion funnel."""
    return pd.DataFrame([
        {"stage": "Prospects reached",   "aum_bn": 1200},
        {"stage": "First meeting",        "aum_bn": 740},
        {"stage": "Mandate discussion",   "aum_bn": 430},
        {"stage": "Proposal sent",        "aum_bn": 260},
        {"stage": "Signed",               "aum_bn": 145},
        {"stage": "Funded",               "aum_bn": 128},
    ])


def _pull_global_bank_network() -> pd.DataFrame:
    """Bank-counterparty exposure network (long-form edges).
    `category` records the source node's bucket; the builder propagates
    it to targets that never appear on the source side (Pensions here),
    giving each cluster a distinct colour.
    """
    edges = [
        ("GS",       "JPM",      35, "Bank"),
        ("GS",       "MS",       28, "Bank"),
        ("GS",       "BLK",      42, "Bank"),
        ("GS",       "BAC",      20, "Bank"),
        ("JPM",      "MS",       15, "Bank"),
        ("JPM",      "BLK",      25, "Bank"),
        ("JPM",      "Vanguard", 30, "Bank"),
        ("MS",       "BLK",      18, "Bank"),
        ("MS",       "Vanguard", 22, "Bank"),
        ("BAC",      "BLK",      16, "Bank"),
        ("BAC",      "Vanguard", 12, "Bank"),
        ("BLK",      "CalPERS",  28, "AM"),
        ("BLK",      "GPFG",     34, "AM"),
        ("Vanguard", "CalPERS",  19, "AM"),
        ("Vanguard", "GPFG",     22, "AM"),
        # Self-edges (v=0, suppressed at render time) declare the
        # category for nodes that never appear on the src side.
        ("CalPERS",  "CalPERS",   0, "Pension"),
        ("GPFG",     "GPFG",      0, "Pension"),
    ]
    return pd.DataFrame(edges, columns=["src", "tgt", "v", "category"])


def _pull_global_outbound_share() -> pd.DataFrame:
    """Outbound flow share for donut."""
    flows = _pull_global_trade_flows()
    out = flows.groupby("src")["v"].sum().reset_index()
    out["region"] = out["src"].str.replace(" \u2192", "", regex=False)
    return out[["region", "v"]].rename(columns={"v": "outbound"})


def _pull_counterparty_tree() -> pd.DataFrame:
    """Tiered hierarchy of counterparty types -> firms.
    Shape suits the `tree` chart_type (mapping: name + parent)."""
    rows = [
        # Root.
        {"name": "Universe",      "parent": None},
        # Tiers.
        {"name": "Banks",         "parent": "Universe"},
        {"name": "Asset Mgrs",    "parent": "Universe"},
        {"name": "Pensions",      "parent": "Universe"},
        # Banks.
        {"name": "GS",            "parent": "Banks"},
        {"name": "JPM",           "parent": "Banks"},
        {"name": "MS",            "parent": "Banks"},
        {"name": "BAC",           "parent": "Banks"},
        # Asset managers.
        {"name": "BlackRock",     "parent": "Asset Mgrs"},
        {"name": "Vanguard",      "parent": "Asset Mgrs"},
        {"name": "State Street",  "parent": "Asset Mgrs"},
        # Pensions.
        {"name": "CalPERS",       "parent": "Pensions"},
        {"name": "GPFG",          "parent": "Pensions"},
        {"name": "ABP",           "parent": "Pensions"},
    ]
    return pd.DataFrame(rows)


def build_global_flows(out_dir: Path) -> Dict[str, Any]:
    """Global flows dashboard: sankey + donut + treemap + sunburst + graph
    + tree + funnel + stat_grid."""
    df_flows = _pull_global_trade_flows()
    df_share = _pull_global_outbound_share()
    df_tree = _pull_global_asset_treemap()
    df_funnel = _pull_global_aum_funnel()
    df_net = _pull_global_bank_network()
    df_cptree = _pull_counterparty_tree()
    total = int(df_flows["v"].sum())
    largest_bil = int(df_flows["v"].max())

    manifest = {
        "schema_version": 1,
        "id": "global_flows",
        "title": "Global flows & allocation",
        "description": ("Cross-border trade flows, asset-class "
                         "allocation, counterparty network + "
                         "hierarchy, mandate conversion funnel."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "datasets": {
            "flows":  df_flows,
            "share":  df_share,
            "tree":   df_tree,
            "funnel": df_funnel,
            "net":    df_net,
            "cptree": df_cptree,
        },
        "layout": {"kind": "tabs", "tabs": [
            {"id": "flows", "label": "Flows",
              "description": ("Bilateral trade flows (sankey) "
                               "and outbound share (donut)."),
              "rows": [
                [
                    {"widget": "stat_grid", "id": "flow_summary", "w": 12,
                      "title": "Flow headlines (USD bn)",
                      "stats": [
                          {"id": "s1", "label": "Total flows",
                            "value": f"{total}", "sub": "USD bn, all pairs"},
                          {"id": "s2", "label": "Largest bilateral",
                            "value": f"{largest_bil}",
                            "sub": "US \u2192 Mexico"},
                          {"id": "s3", "label": "Bilateral legs",
                            "value": f"{len(df_flows)}",
                            "sub": "directed pairs"},
                          {"id": "s4", "label": "Top exporter",
                            "value": "US", "sub": "USD 3,165 bn"},
                          {"id": "s5", "label": "APAC share",
                            "value": "29%", "sub": "of outbound"},
                          {"id": "s6", "label": "YoY growth",
                            "value": "+4.2%", "sub": "nominal, USD"},
                      ]},
                ],
                [
                    {"widget": "chart", "id": "flow_sankey",
                      "w": 8, "h_px": 480,
                      "spec": {
                          "chart_type": "sankey", "dataset": "flows",
                          "mapping": {"source": "src",
                                        "target": "tgt",
                                        "value": "v"},
                          "title": "Bilateral trade flows (USD bn)"}},
                    {"widget": "chart", "id": "flow_donut",
                      "w": 4, "h_px": 480,
                      "spec": {
                          "chart_type": "donut", "dataset": "share",
                          "mapping": {"category": "region",
                                        "value": "outbound",
                                        "legend_position": "bottom"},
                          "title": "Outbound share"}},
                ],
            ]},
            {"id": "alloc", "label": "Allocation",
              "description": ("AUM hierarchy across region \u2192 "
                               "country \u2192 asset class."),
              "rows": [
                [
                    {"widget": "chart", "id": "alloc_tree",
                      "w": 6, "h_px": 480,
                      "spec": {
                          "chart_type": "treemap", "dataset": "tree",
                          "mapping": {
                              "path": ["region", "country",
                                        "asset_class"],
                              "value": "aum"},
                          "title": "AUM treemap (USD bn)"}},
                    {"widget": "chart", "id": "alloc_sun",
                      "w": 6, "h_px": 480,
                      "spec": {
                          "chart_type": "sunburst", "dataset": "tree",
                          "mapping": {
                              "path": ["region", "country",
                                        "asset_class"],
                              "value": "aum"},
                          "title": "AUM sunburst"}},
                ],
            ]},
            {"id": "network", "label": "Counterparty network",
              "description": ("Bank-asset-manager-pension exposure "
                               "graph (left) + hierarchical tree "
                               "(right)."),
              "rows": [
                [
                    {"widget": "chart", "id": "net_graph",
                      "w": 8, "h_px": 520,
                      "spec": {
                          "chart_type": "graph", "dataset": "net",
                          "mapping": {"source": "src",
                                        "target": "tgt",
                                        "value": "v",
                                        "node_category": "category"},
                          "title": ("Counterparty exposure network "
                                      "(drag nodes)")}},
                    {"widget": "chart", "id": "cp_tree",
                      "w": 4, "h_px": 520,
                      "spec": {
                          "chart_type": "tree", "dataset": "cptree",
                          "mapping": {"name": "name",
                                        "parent": "parent"},
                          "title": "Counterparty hierarchy",
                          "subtitle": ("Org-style view: tier -> firm. "
                                         "Click a node to collapse.")}},
                ],
            ]},
            {"id": "funnel", "label": "Mandate funnel",
              "description": "Prospect \u2192 funded conversion funnel.",
              "rows": [
                [
                    {"widget": "chart", "id": "fun_chart",
                      "w": 8, "h_px": 440,
                      "spec": {
                          "chart_type": "funnel", "dataset": "funnel",
                          "mapping": {"category": "stage",
                                        "value": "aum_bn"},
                          "title": ("Prospect-to-funded pipeline "
                                      "(USD bn)")}},
                    {"widget": "markdown", "id": "fun_notes",
                      "w": 4,
                      "content": (
                          "### Conversion commentary\n\n"
                          "Roughly 10.7% of initial prospect AUM "
                          "converts to funded mandates. The largest "
                          "drop-off is between first meeting and "
                          "mandate discussion (~42%).\n\n"
                          "Historical average funded rate is ~9.5%. "
                          "Current cohort running slightly above.")},
                ],
            ]},
        ]},
        "links": [],
    }

    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1600, height=1700)
    return _result(r, thumb)


# =============================================================================
# DEMO: equity_deep_dive  (self-contained: data + manifest)
# =============================================================================
#
# Chart types showcased: candlestick (price), multi_line w/ strokeDash
# (actuals vs consensus estimates), bar_horizontal (analyst ratings),
# scatter w/ trendline (beta regression), bullet (valuation vs range),
# histogram (return distribution), KPIs with sparklines, image widget,
# markdown thesis, header_actions, metadata, tabs.


def _pull_equity_ohlc(days: int = 252) -> pd.DataFrame:
    """Synthetic single-name OHLC."""
    random.seed(SEED + 200)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    price = 185.0
    rows = []
    for d in dates:
        o = price
        c = max(50, o * (1 + random.gauss(0.0005, 0.018)))
        lo = min(o, c) - abs(random.gauss(0, 0.8))
        hi = max(o, c) + abs(random.gauss(0, 0.8))
        vol = max(1e6, random.gauss(62e6, 14e6))
        rows.append({
            "date": d,
            "open": round(o, 2), "close": round(c, 2),
            "low": round(lo, 2), "high": round(hi, 2),
            "volume_m": round(vol / 1e6, 1),
        })
        price = c
    return pd.DataFrame(rows)


def _pull_equity_earnings_actual_vs_est() -> pd.DataFrame:
    """Quarterly EPS: actual vs consensus estimate, long form with
    a 'type' column so strokeDash = type renders Actual solid, Est dashed.
    """
    quarters = ["Q1-24", "Q2-24", "Q3-24", "Q4-24",
                 "Q1-25", "Q2-25", "Q3-25", "Q4-25",
                 "Q1-26"]
    actual = [1.68, 1.52, 1.72, 2.18, 1.88, 1.62, 1.95, 2.35, 2.05]
    est = [1.60, 1.55, 1.70, 2.12, 1.82, 1.66, 1.88, 2.28, 2.02]
    rows = []
    for q, a, e in zip(quarters, actual, est):
        rows.append({"quarter": q, "eps": a, "type": "Actual"})
        rows.append({"quarter": q, "eps": e, "type": "Consensus"})
    return pd.DataFrame(rows)


def _pull_equity_analyst_ratings() -> pd.DataFrame:
    """Analyst rating counts for bar_horizontal.

    Row order matters: ECharts renders horizontal bars bottom-up, so we
    list the most-negative rating first and bullish last. Combined with
    the natural category axis that puts index 0 at the bottom, the
    visual top-to-bottom is Strong Buy ... Strong Sell (reading order).
    """
    return pd.DataFrame([
        {"rating": "Strong Sell", "count": 1},
        {"rating": "Sell",        "count": 3},
        {"rating": "Hold",        "count": 11},
        {"rating": "Buy",         "count": 22},
        {"rating": "Strong Buy",  "count": 18},
    ])


def _pull_equity_beta_scatter() -> pd.DataFrame:
    """Stock vs market daily returns for beta regression scatter."""
    random.seed(SEED + 201)
    rows = []
    beta = 1.22
    for _ in range(252):
        mkt = random.gauss(0.03, 0.95)
        stk = mkt * beta + random.gauss(0.05, 0.7)
        rows.append({"mkt_return_pct": round(mkt, 2),
                      "stk_return_pct": round(stk, 2)})
    return pd.DataFrame(rows)


def _pull_equity_valuation_bullet() -> pd.DataFrame:
    """Valuation multiples: current vs 5Y low/high + z-score."""
    return pd.DataFrame([
        {"metric": "P/E NTM",       "current": 29.4, "low_5y": 16.2,
          "high_5y": 35.1, "z": 1.1},
        {"metric": "EV/EBITDA",     "current": 22.1, "low_5y": 12.5,
          "high_5y": 26.4, "z": 1.3},
        {"metric": "P/S NTM",       "current": 7.8,  "low_5y": 3.9,
          "high_5y": 9.2,  "z": 1.4},
        {"metric": "FCF yield (%)", "current": 3.1,  "low_5y": 2.4,
          "high_5y": 6.8,  "z": -1.2},
        {"metric": "Dividend yld",  "current": 0.48, "low_5y": 0.42,
          "high_5y": 0.95, "z": -1.0},
        {"metric": "PEG",           "current": 2.4,  "low_5y": 1.1,
          "high_5y": 2.8,  "z": 1.5},
    ])


def _pull_equity_daily_returns() -> pd.DataFrame:
    """Daily return series for return-distribution histogram."""
    random.seed(SEED + 202)
    rows = [{"return_pct": round(random.gauss(0.05, 1.5), 2)}
            for _ in range(500)]
    return pd.DataFrame(rows)


def _pull_equity_kpi_series() -> pd.DataFrame:
    """Small time series used to drive KPI sparklines."""
    random.seed(SEED + 203)
    days = 60
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    px = 185.0
    mcap = 2820.0
    pe = 29.4
    iv = 24.0
    rows = []
    for d in dates:
        px *= 1 + random.gauss(0.0005, 0.016)
        mcap *= 1 + random.gauss(0.0005, 0.016)
        pe += random.gauss(0, 0.12)
        iv = max(12, iv + random.gauss(0, 0.4))
        rows.append({"date": d,
                      "price": round(px, 2),
                      "mcap_bn": round(mcap, 1),
                      "pe": round(pe, 2),
                      "iv_30d": round(iv, 2)})
    return pd.DataFrame(rows)


def build_equity_deep_dive(out_dir: Path) -> Dict[str, Any]:
    """Single-name equity dashboard."""
    df_ohlc = _pull_equity_ohlc()
    df_earn = _pull_equity_earnings_actual_vs_est()
    df_rat = _pull_equity_analyst_ratings()
    df_beta = _pull_equity_beta_scatter()
    df_val = _pull_equity_valuation_bullet()
    df_ret = _pull_equity_daily_returns()
    df_kpi = _pull_equity_kpi_series()

    manifest = {
        "schema_version": 1,
        "id": "equity_deep_dive",
        "title": "ACME Corp. (ACME) deep dive",
        "description": ("Single-name equity tear-sheet: price + "
                         "volume, earnings vs consensus, analyst "
                         "ratings, beta regression, valuation vs "
                         "5Y range, return distribution."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "kerberos": "goyairl",
            "dashboard_id": "equity_deep_dive",
            "data_as_of": "2026-04-24T20:00:00Z",
            "generated_at": "2026-04-24T20:05:00Z",
            "sources": ["GS Market Data", "Visible Alpha"],
            "refresh_frequency": "daily",
            "refresh_enabled": True,
            "tags": ["equity", "single_name"],
            "version": "1.0.0",
            "methodology": (
                "## Price + volume\n\n"
                "Daily OHLC bars with overlaid volume; dollar "
                "volume not adjusted for splits.\n\n"
                "## Earnings vs consensus\n\n"
                "Reported EPS minus the consensus median in the "
                "5 trading days before announcement (Visible Alpha). "
                "Bars are absolute USD; tooltip shows percent surprise.\n\n"
                "## Analyst ratings distribution\n\n"
                "Snapshot of buy / hold / sell counts, refreshed "
                "weekly. Conviction-weighted is excluded; treat each "
                "analyst equally.\n\n"
                "## Beta regression\n\n"
                "OLS of daily log returns vs SPX over a 2Y rolling "
                "window. Outliers >3sigma kept (no Winsorisation).\n\n"
                "## Valuation\n\n"
                "Forward P/E percentile rank vs the stock's own "
                "5Y range; sector median shown as a dashed reference.\n\n"
                "## Return distribution\n\n"
                "Histogram of daily log returns over the displayed "
                "lookback. Bin width = 25bp, no smoothing."
            ),
        },
        "header_actions": [
            {"label": "Company filings", "icon": "\u2197",
              "href": "https://www.sec.gov/"},
            {"label": "GIR research", "icon": "\u2197",
              "href": "https://research.gs.com/"},
            {"label": "Model refresh", "icon": "\u21bb",
              "onclick": "customRun", "primary": True},
        ],
        "datasets": {
            "ohlc":   df_ohlc,
            "earn":   df_earn,
            "rat":    df_rat,
            "beta":   df_beta,
            "val":    df_val,
            "ret":    df_ret,
            "kpi":    df_kpi,
        },
        "filters": [
            {"id": "price_range", "type": "dateRange", "default": "1Y",
              "targets": ["price_chart", "vol_chart"],
              "field": "date", "label": "Initial price range",
              "scope": "global"},
        ],
        "layout": {"kind": "tabs", "tabs": [
            {"id": "price", "label": "Price & volume",
              "description": "Daily OHLC with the 60D KPI ribbon.",
              "rows": [
                [
                    {"widget": "kpi", "id": "k_px", "label": "Close",
                      "source": "kpi.latest.price",
                      "delta_source": "kpi.prev.price",
                      "sparkline_source": "kpi.price",
                      "prefix": "$", "decimals": 2, "w": 3,
                      "emphasis": True,
                      "info": "Last-trade equity price.",
                      "popup": {
                          "title": "Close price",
                          "body": (
                              "### Definition\n\n"
                              "**Close** is the last printed trade on "
                              "the primary listing exchange for the "
                              "current trading session.\n\n"
                              "### Data sourcing\n\n"
                              "- Feed: *GS Market Data* (equities)\n"
                              "- Latency: roughly 100ms intraday, "
                              "snapshot at session close\n"
                              "- Adjustments: cash dividends and "
                              "splits are applied retroactively\n\n"
                              "### Related\n\n"
                              "See the [price history chart]"
                              "(#price_chart) below and the full "
                              "OHLC candle detail in the ECharts "
                              "tooltip.")}},
                    {"widget": "kpi", "id": "k_mc", "label": "Market cap",
                      "source": "kpi.latest.mcap_bn",
                      "delta_source": "kpi.prev.mcap_bn",
                      "sparkline_source": "kpi.mcap_bn",
                      "suffix": " bn", "decimals": 0, "w": 3},
                    {"widget": "kpi", "id": "k_pe",
                      "label": "P/E NTM",
                      "source": "kpi.latest.pe",
                      "delta_source": "kpi.prev.pe",
                      "sparkline_source": "kpi.pe",
                      "decimals": 2, "w": 3,
                      "info": ("Forward P/E on next-12-month "
                                 "consensus EPS.")},
                    {"widget": "kpi", "id": "k_iv",
                      "label": "IV 30D (%)",
                      "source": "kpi.latest.iv_30d",
                      "delta_source": "kpi.prev.iv_30d",
                      "sparkline_source": "kpi.iv_30d",
                      "suffix": "%", "decimals": 2, "w": 3},
                ],
                [
                    {"widget": "chart", "id": "price_chart",
                      "w": 12, "h_px": 440,
                      "title": "ACME daily OHLC (1Y)",
                      "badge": "LIVE",
                      "badge_color": "pos",
                      "info": ("Daily OHLC with dataZoom brush "
                                 "at the bottom. Drag the brush to "
                                 "zoom in on a date range."),
                      "footer": ("Source: GS Market Data. "
                                   "Updated at market close."),
                      "action_buttons": [
                          {"label": "Open in portal", "icon": "\u2197",
                            "href": "https://example.com/acme",
                            "title": "Open ACME page"},
                      ],
                      "spec": {
                          "chart_type": "candlestick",
                          "dataset": "ohlc",
                          "mapping": {"x": "date",
                                        "open": "open",
                                        "close": "close",
                                        "low": "low",
                                        "high": "high"},
                          "title": "ACME daily OHLC (1Y)"}},
                ],
                [
                    {"widget": "chart", "id": "vol_chart",
                      "w": 12, "h_px": 220,
                      "spec": {
                          "chart_type": "bar", "dataset": "ohlc",
                          "mapping": {"x": "date", "y": "volume_m",
                                        "y_title": "Volume (M sh)",
                                        "x_date_format": "auto",
                                        "series_labels": {
                                            "volume_m": "Volume"},
                                        "legend_position": "none"},
                          "title": "Daily volume"}},
                ],
            ]},
            {"id": "fundamentals", "label": "Fundamentals",
              "description": ("Quarterly EPS actuals vs consensus "
                               "and analyst rating distribution."),
              "rows": [
                [
                    {"widget": "chart", "id": "eps_chart",
                      "w": 8, "h_px": 380,
                      "spec": {
                          "chart_type": "multi_line", "dataset": "earn",
                          "mapping": {
                              "x": "quarter", "y": "eps",
                              "color": "type",
                              "strokeDash": "type",
                              "strokeDashScale": {
                                  "domain": ["Actual", "Consensus"],
                                  "range": ["solid", [6, 4]]},
                              "x_type": "category",
                              "x_sort": ["Q1-24", "Q2-24", "Q3-24",
                                          "Q4-24", "Q1-25", "Q2-25",
                                          "Q3-25", "Q4-25", "Q1-26"],
                              "y_title": "EPS ($)"},
                          "title": ("Quarterly EPS: actuals vs "
                                      "consensus"),
                          "subtitle": ("solid = actual, dashed = "
                                         "consensus"),
                          "annotations": [
                              {"type": "vline", "x": "Q1-26",
                                "label": "Current qtr",
                                "color": "#1a365d", "style": "dashed"},
                          ]}},
                    {"widget": "chart", "id": "rating_chart",
                      "w": 4, "h_px": 380,
                      "spec": {
                          "chart_type": "bar_horizontal",
                          "dataset": "rat",
                          "mapping": {"x": "count", "y": "rating",
                                        "x_title": "# analysts",
                                        "legend_position": "none"},
                          "title": "Sell-side distribution"}},
                ],
                [
                    {"widget": "markdown", "id": "thesis", "w": 12,
                      "content": (
                          "### Thesis\n\n"
                          "ACME has beaten consensus EPS in 7 of the "
                          "last 9 quarters, with the magnitude of beat "
                          "widening on services revenue. Sell-side "
                          "skew remains bullish (40 Buy+ vs 4 Sell-). "
                          "Near-term catalyst: Q1 print in 3 weeks.")},
                ],
            ]},
            {"id": "risk", "label": "Risk & valuation",
              "description": ("Beta regression, return distribution, "
                               "valuation vs 5Y range."),
              "rows": [
                [
                    {"widget": "chart", "id": "beta_chart",
                      "w": 6, "h_px": 360,
                      "spec": {
                          "chart_type": "scatter", "dataset": "beta",
                          "mapping": {
                              "x": "mkt_return_pct",
                              "y": "stk_return_pct",
                              "trendline": True,
                              "x_title": "Market daily return (%)",
                              "y_title": "ACME daily return (%)"},
                          "title": ("Beta regression (1Y daily)"),
                          "subtitle": "trendline = OLS slope"}},
                    {"widget": "chart", "id": "hist_chart",
                      "w": 6, "h_px": 360,
                      "spec": {
                          "chart_type": "histogram", "dataset": "ret",
                          "mapping": {"x": "return_pct", "bins": 30,
                                        "x_title": "Daily return (%)",
                                        "y_title": "Frequency"},
                          "title": "Daily return distribution (2Y)"}},
                ],
                [
                    {"widget": "chart", "id": "val_bullet",
                      "w": 12, "h_px": 360,
                      "spec": {
                          "chart_type": "bullet", "dataset": "val",
                          "mapping": {"y": "metric", "x": "current",
                                        "x_low": "low_5y",
                                        "x_high": "high_5y",
                                        "color_by": "z"},
                          "title": ("Valuation vs 5Y range "
                                      "(z-score colored)")}},
                ],
            ]},
        ]},
        "links": [],
    }

    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1600, height=1800)
    return _result(r, thumb)


# =============================================================================
# DEMO: portfolio_analytics  (self-contained: data + manifest)
# =============================================================================
#
# Chart types showcased: gauge (VaR), radar (factor exposures), area
# (stacked cumulative P&L), parallel_coords (position-level snapshot),
# pie (allocation), histogram (return dist), bullet (risk metrics).
# Features: stat_grid, filters, grid layout (single-page overview).


def _pull_portfolio_pnl_stack() -> pd.DataFrame:
    """Stacked cumulative P&L by asset class (long form). Generated as a
    monotonically-non-negative cumulative series per bucket so the
    stacked area never has to render below zero (which produces ugly
    overlaps on stacked areas).
    """
    random.seed(SEED + 300)
    dates = pd.date_range(end=END_DATE, periods=252, freq="B")
    buckets = ["Equities", "Rates", "Credit", "Commodities", "FX"]
    # Daily pnl expected value (in $mm). All positive-drifting so the
    # stacked sum climbs monotonically; sigma is small enough that
    # downside stays bounded.
    drift = {"Equities": 0.012, "Rates": 0.004,
              "Credit": 0.006, "Commodities": 0.003,
              "FX": 0.002}
    sigma = {"Equities": 0.018, "Rates": 0.008,
              "Credit": 0.010, "Commodities": 0.014,
              "FX": 0.009}
    cum = {b: 0.0 for b in buckets}
    rows = []
    for d in dates:
        for b in buckets:
            step = max(0.0, random.gauss(drift[b], sigma[b]))
            cum[b] += step
            rows.append({"date": d, "bucket": b,
                           "pnl_cum_mm": round(cum[b], 3)})
    return pd.DataFrame(rows)


def _pull_portfolio_allocation() -> pd.DataFrame:
    """Current asset-class weights."""
    return pd.DataFrame([
        {"bucket": "Equities",    "weight_pct": 42},
        {"bucket": "Rates",       "weight_pct": 25},
        {"bucket": "Credit",      "weight_pct": 15},
        {"bucket": "Commodities", "weight_pct": 8},
        {"bucket": "FX",           "weight_pct": 6},
        {"bucket": "Cash",         "weight_pct": 4},
    ])


def _pull_portfolio_factor_radar() -> pd.DataFrame:
    """Factor exposure: current vs target vs benchmark (long form)."""
    dims = ["Growth", "Value", "Momentum", "Quality", "Size", "LowVol"]
    curr = [0.80, 0.40, 0.70, 0.85, 0.30, 0.55]
    tgt = [0.60, 0.50, 0.65, 0.75, 0.40, 0.60]
    bench = [0.50, 0.50, 0.50, 0.50, 0.50, 0.50]
    rows = []
    for src, vals in [("Current", curr), ("Target", tgt),
                        ("Benchmark", bench)]:
        for d, v in zip(dims, vals):
            rows.append({"factor": d, "score": v, "book": src})
    return pd.DataFrame(rows)


def _pull_portfolio_positions_parallel() -> pd.DataFrame:
    """Position-level multi-dim snapshot for parallel_coords."""
    random.seed(SEED + 301)
    buckets = ["Equities", "Rates", "Credit", "Commodities", "FX"]
    rows = []
    for _ in range(120):
        b = random.choice(buckets)
        rows.append({
            "bucket": b,
            "size_mm": round(random.gauss(18, 9), 2),
            "vol_pct": round(max(3, random.gauss(14, 5)), 2),
            "beta": round(random.gauss(0.95, 0.45), 2),
            "mtd_ret_pct": round(random.gauss(0.4, 2.1), 2),
            "carry_bps": round(random.gauss(45, 35), 1),
        })
    return pd.DataFrame(rows)


def _pull_portfolio_return_dist() -> pd.DataFrame:
    random.seed(SEED + 302)
    rows = [{"daily_pct": round(random.gauss(0.04, 0.74), 3)}
            for _ in range(756)]
    return pd.DataFrame(rows)


def _pull_portfolio_kpi_series() -> pd.DataFrame:
    random.seed(SEED + 303)
    days = 60
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    aum = 2480.0
    pnl_mtd = 0.0
    sharpe = 1.45
    var = 18.0
    rows = []
    for d in dates:
        aum *= 1 + random.gauss(0.0006, 0.007)
        pnl_mtd += random.gauss(0.8, 2.5)
        sharpe = max(0.2, sharpe + random.gauss(0, 0.02))
        var = max(6, var + random.gauss(0, 0.25))
        rows.append({"date": d,
                      "aum_mm": round(aum, 1),
                      "pnl_mtd_mm": round(pnl_mtd, 2),
                      "sharpe": round(sharpe, 2),
                      "var_mm": round(var, 2)})
    return pd.DataFrame(rows)


def build_portfolio_analytics(out_dir: Path) -> Dict[str, Any]:
    """Multi-asset portfolio analytics dashboard."""
    df_pnl = _pull_portfolio_pnl_stack()
    df_alloc = _pull_portfolio_allocation()
    df_radar = _pull_portfolio_factor_radar()
    df_parallel = _pull_portfolio_positions_parallel()
    df_ret = _pull_portfolio_return_dist()
    df_kpi = _pull_portfolio_kpi_series()
    df_var = pd.DataFrame([{"used": 62}])

    manifest = {
        "schema_version": 1,
        "id": "portfolio_analytics",
        "title": "Portfolio analytics",
        "description": ("Multi-asset portfolio analytics: VaR gauge, "
                         "factor exposures, stacked P&L, position "
                         "parallel-coords, return distribution."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "datasets": {
            "pnl":      df_pnl,
            "alloc":    df_alloc,
            "radar":    df_radar,
            "parallel": df_parallel,
            "ret":      df_ret,
            "kpi":      df_kpi,
            "var":      df_var,
        },
        "filters": [
            {"id": "bucket", "type": "multiSelect", "default": [],
              "options": ["Equities", "Rates", "Credit",
                           "Commodities", "FX", "Cash"],
              "field": "bucket",
              "label": "Asset class",
              "targets": ["pnl_area", "alloc_pie",
                           "parallel_chart"]},
        ],
        "layout": {"kind": "grid", "cols": 12, "rows": [
            [
                # `pinned: True` glues the KPI ribbon to the top of
                # the viewport while the user scrolls through the
                # rest of the dashboard. Exercises a widget knob the
                # rest of the gallery doesn't reach.
                {"widget": "kpi", "id": "k_aum", "label": "AUM",
                  "source": "kpi.latest.aum_mm",
                  "delta_source": "kpi.prev.aum_mm",
                  "sparkline_source": "kpi.aum_mm",
                  "suffix": " mm", "decimals": 0, "w": 3,
                  "pinned": True},
                {"widget": "kpi", "id": "k_pnl", "label": "MTD P&L",
                  "source": "kpi.latest.pnl_mtd_mm",
                  "delta_source": "kpi.prev.pnl_mtd_mm",
                  "sparkline_source": "kpi.pnl_mtd_mm",
                  "prefix": "$", "suffix": " mm",
                  "decimals": 2, "w": 3,
                  "pinned": True},
                {"widget": "kpi", "id": "k_sh", "label": "Sharpe",
                  "source": "kpi.latest.sharpe",
                  "delta_source": "kpi.prev.sharpe",
                  "sparkline_source": "kpi.sharpe",
                  "decimals": 2, "w": 3,
                  "pinned": True},
                {"widget": "kpi", "id": "k_var", "label": "1D 99% VaR",
                  "source": "kpi.latest.var_mm",
                  "delta_source": "kpi.prev.var_mm",
                  "sparkline_source": "kpi.var_mm",
                  "suffix": " mm", "decimals": 2, "w": 3,
                  "pinned": True},
            ],
            [
                {"widget": "stat_grid", "id": "summary", "w": 12,
                  "title": "Risk summary",
                  "info": ("Rolling risk metrics aggregated across "
                             "the full book. Hover any stat for its "
                             "definition."),
                  "stats": [
                      {"id": "rs1", "label": "Beta to SPX",
                        "value": "0.82", "sub": "60D",
                        "trend": 0.04,
                        "info": ("OLS beta of book P&L vs S&P 500 "
                                   "total return, trailing 60 biz "
                                   "days.")},
                      {"id": "rs2", "label": "Duration",
                        "value": "4.8y", "sub": "DV01 $280k",
                        "trend": 0.0,
                        "info": ("Book-weighted modified duration "
                                   "across rates positions.")},
                      {"id": "rs3", "label": "Gross leverage",
                        "value": "2.3x", "sub": "vs 3.0x cap",
                        "trend": 0.1,
                        "info": ("Sum of |notional| / equity. Risk "
                                   "limit is 3.0x.")},
                      {"id": "rs4", "label": "FX exposure",
                        "value": "-$18mm", "sub": "EUR, JPY short",
                        "trend": -0.2,
                        "info": ("Net FX delta translated back to "
                                   "USD.")},
                      {"id": "rs5", "label": "Max DD (1Y)",
                        "value": "-6.8%", "sub": "Jul 2025",
                        "info": ("Peak-to-trough drawdown of the "
                                   "combined book over the past "
                                   "year.")},
                      {"id": "rs6", "label": "Hit ratio",
                        "value": "56%", "sub": "trailing 90D",
                        "trend": 0.03,
                        "info": ("Fraction of trading days with "
                                   "positive P&L, trailing 90 days.")},
                  ]},
            ],
            [
                {"widget": "chart", "id": "var_gauge",
                  "w": 4, "h_px": 360,
                  "spec": {
                      "chart_type": "gauge", "dataset": "var",
                      "mapping": {"value": "used",
                                    "name": "VaR used",
                                    "min": 0, "max": 100},
                      "title": "VaR utilisation (%)",
                      "subtitle": "of $30mm limit"}},
                {"widget": "chart", "id": "radar_chart",
                  "w": 4, "h_px": 360,
                  "spec": {
                      "chart_type": "radar", "dataset": "radar",
                      "mapping": {"category": "factor",
                                    "value": "score",
                                    "series": "book",
                                    "legend_position": "bottom"},
                      "title": "Factor exposure vs benchmark"}},
                {"widget": "chart", "id": "alloc_pie",
                  "w": 4, "h_px": 360,
                  "spec": {
                      "chart_type": "pie", "dataset": "alloc",
                      "mapping": {"category": "bucket",
                                    "value": "weight_pct",
                                    "legend_position": "bottom"},
                      "title": "Asset-class allocation"}},
            ],
            [
                {"widget": "chart", "id": "pnl_area",
                  "w": 12, "h_px": 360,
                  "spec": {
                      "chart_type": "area", "dataset": "pnl",
                      "mapping": {"x": "date",
                                    "y": "pnl_cum_mm",
                                    "color": "bucket",
                                    "y_title": "Cumulative P&L ($mm)"},
                      "title": "Cumulative P&L by asset class",
                      "annotations": [
                          {"type": "hline", "y": 0,
                            "label": "",
                            "color": "#718096",
                            "style": "dashed"},
                      ]}},
            ],
            [
                {"widget": "chart", "id": "parallel_chart",
                  "w": 8, "h_px": 380,
                  "spec": {
                      "chart_type": "parallel_coords",
                      "dataset": "parallel",
                      "mapping": {
                          "dims": ["size_mm", "vol_pct", "beta",
                                    "mtd_ret_pct", "carry_bps"],
                          "color": "bucket",
                          "legend_position": "bottom"},
                      "title": "Position risk dimensions"}},
                {"widget": "chart", "id": "ret_hist",
                  "w": 4, "h_px": 380,
                  "spec": {
                      "chart_type": "histogram", "dataset": "ret",
                      "mapping": {"x": "daily_pct", "bins": 40,
                                    "x_title": "Daily return (%)",
                                    "y_title": "Count"},
                      "title": "Daily return distribution (3Y)",
                      "annotations": [
                          {"type": "vline", "x": 0,
                            "label": "",
                            "color": "#718096",
                            "style": "dashed"},
                      ]}},
            ],
        ]},
        "links": [
            # lineY brush exercises the y-band selection shape that
            # rect / lineX / polygon don't cover. Drag a horizontal
            # band on the histogram to mark a return range; the
            # parallel_chart member echoes the selection.
            {"group": "ret_brush",
              "members": ["ret_hist", "parallel_chart"],
              "brush": {"type": "lineY", "yAxisIndex": 0}},
        ],
    }

    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1600, height=1700)
    return _result(r, thumb)


# =============================================================================
# DEMO: markets_wrap  (self-contained: data + manifest)
# =============================================================================
#
# Big end-of-day cross-asset dashboard that stress-tests the layout
# engine with 15+ charts in a single scrollable page. Also shows off
# the newer customization knobs: legend_position, series_labels,
# x_date_format, humanize, kpi format, show_slice_labels.


def _pull_wrap_equities(days: int = 252) -> pd.DataFrame:
    """Major equity indices + sector performance."""
    random.seed(SEED + 400)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    spx, ndx, dax, nkyo, ftse = 5100.0, 17800.0, 17500.0, 38500.0, 8200.0
    rows = []
    for d in dates:
        spx  *= 1 + random.gauss(0.0005, 0.0092)
        ndx  *= 1 + random.gauss(0.0007, 0.0115)
        dax  *= 1 + random.gauss(0.0003, 0.0098)
        nkyo *= 1 + random.gauss(0.0004, 0.0110)
        ftse *= 1 + random.gauss(0.0002, 0.0082)
        rows.append({"date": d,
                      "spx":  round(spx, 2), "ndx":  round(ndx, 2),
                      "dax":  round(dax, 2), "nky":  round(nkyo, 2),
                      "ftse": round(ftse, 2)})
    return pd.DataFrame(rows)


def _pull_wrap_sectors() -> pd.DataFrame:
    """Sector 1D / MTD / YTD performance in percent.

    Sorted ascending by YTD so the bar_horizontal chart places the
    biggest positive mover at the top and the laggard at the bottom.
    """
    rows = [
        {"sector": "Technology",    "d1_pct":  1.25, "mtd_pct":  3.80, "ytd_pct": 18.4},
        {"sector": "Financials",    "d1_pct":  0.55, "mtd_pct":  2.10, "ytd_pct":  9.7},
        {"sector": "Energy",        "d1_pct": -0.80, "mtd_pct": -1.30, "ytd_pct": -2.1},
        {"sector": "Healthcare",    "d1_pct":  0.20, "mtd_pct":  1.20, "ytd_pct":  5.4},
        {"sector": "Industrials",   "d1_pct":  0.42, "mtd_pct":  2.60, "ytd_pct":  8.1},
        {"sector": "Consumer Disc", "d1_pct":  0.85, "mtd_pct":  2.95, "ytd_pct": 11.2},
        {"sector": "Consumer Stp",  "d1_pct": -0.15, "mtd_pct":  0.40, "ytd_pct":  2.8},
        {"sector": "Utilities",     "d1_pct":  0.10, "mtd_pct": -0.20, "ytd_pct":  1.4},
        {"sector": "Materials",     "d1_pct": -0.25, "mtd_pct":  0.80, "ytd_pct":  4.3},
        {"sector": "Real Estate",   "d1_pct":  0.32, "mtd_pct":  1.85, "ytd_pct":  6.0},
        {"sector": "Comm Services", "d1_pct":  0.65, "mtd_pct":  2.40, "ytd_pct": 12.7},
    ]
    rows.sort(key=lambda r: r["ytd_pct"])
    return pd.DataFrame(rows)


def _pull_wrap_rates(days: int = 252) -> pd.DataFrame:
    """UST yield curve points (5 tenors)."""
    random.seed(SEED + 401)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    y = {"us_2y": 4.05, "us_5y": 4.20, "us_10y": 4.35,
          "us_20y": 4.55, "us_30y": 4.65}
    rows = []
    for d in dates:
        for k in y:
            y[k] = max(0.5, y[k] + random.gauss(0, 0.017))
        row = {"date": d}
        row.update({k: round(v, 3) for k, v in y.items()})
        rows.append(row)
    return pd.DataFrame(rows)


def _pull_wrap_fx_majors(days: int = 252) -> pd.DataFrame:
    """DXY + EURUSD + USDJPY + GBPUSD."""
    random.seed(SEED + 402)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    dxy, eur, jpy, gbp = 104.0, 1.085, 154.0, 1.265
    rows = []
    for d in dates:
        dxy += random.gauss(0, 0.22)
        eur *= 1 + random.gauss(0, 0.0035)
        jpy += random.gauss(0.01, 0.18)
        gbp *= 1 + random.gauss(0, 0.0038)
        rows.append({"date": d, "dxy": round(dxy, 2),
                      "eurusd": round(eur, 4),
                      "usdjpy": round(jpy, 2),
                      "gbpusd": round(gbp, 4)})
    return pd.DataFrame(rows)


def _pull_wrap_commodities(days: int = 252) -> pd.DataFrame:
    """WTI + Brent + Gold + Copper + Wheat, daily close."""
    random.seed(SEED + 403)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    wti, brent, gold, copper, wheat = 82.0, 86.0, 2320.0, 4.05, 620.0
    rows = []
    for d in dates:
        wti    += random.gauss(0, 0.85)
        brent  += random.gauss(0, 0.85)
        gold   *= 1 + random.gauss(0.00035, 0.0075)
        copper *= 1 + random.gauss(0.0002, 0.0115)
        wheat  += random.gauss(0, 6)
        rows.append({"date": d,
                      "wti":   round(wti, 2),
                      "brent": round(brent, 2),
                      "gold":  round(gold, 2),
                      "copper":round(copper, 3),
                      "wheat": round(wheat, 2)})
    return pd.DataFrame(rows)


def _pull_wrap_kpi_series(days: int = 60) -> pd.DataFrame:
    random.seed(SEED + 404)
    dates = pd.date_range(end=END_DATE, periods=days, freq="B")
    spx, y10, dxy, wti, gold, vix, ndx = (
        5100.0, 4.35, 104.0, 82.0, 2320.0, 16.0, 17800.0)
    rows = []
    for d in dates:
        spx  *= 1 + random.gauss(0.0005, 0.0092)
        ndx  *= 1 + random.gauss(0.0007, 0.0115)
        y10  += random.gauss(0, 0.015)
        dxy  += random.gauss(0, 0.22)
        wti  += random.gauss(0, 0.85)
        gold *= 1 + random.gauss(0.00035, 0.0075)
        vix   = max(9, vix + random.gauss(0, 0.4))
        rows.append({"date": d,
                      "spx":  round(spx, 2), "ndx":  round(ndx, 2),
                      "us_10y": round(y10, 3),
                      "dxy":  round(dxy, 2), "wti":  round(wti, 2),
                      "gold": round(gold, 1), "vix":  round(vix, 2)})
    return pd.DataFrame(rows)


def _pull_wrap_top_movers() -> pd.DataFrame:
    """Top 12 1D movers (stocks) for table. Sector labels intentionally
    match `_pull_wrap_sectors` so that clicking a sector bar in the
    equity chart filters this table via click_emit_filter."""
    random.seed(SEED + 405)
    names = ["NVDA", "META", "TSLA", "AMD", "AVGO", "ORCL",
              "CRWD", "MSFT", "AMZN", "GOOGL", "AAPL", "UBER",
              "NFLX", "XOM", "CVX", "JPM", "GS", "BAC"]
    sectors = {
        "NVDA": "Technology", "META": "Technology",
        "TSLA": "Consumer Disc", "AMD": "Technology",
        "AVGO": "Technology", "ORCL": "Technology",
        "CRWD": "Technology", "MSFT": "Technology",
        "AMZN": "Consumer Disc", "GOOGL": "Technology",
        "AAPL": "Technology", "UBER": "Technology",
        "NFLX": "Comm Services", "XOM": "Energy",
        "CVX": "Energy", "JPM": "Financials",
        "GS": "Financials", "BAC": "Financials",
    }
    rows = []
    for n in names:
        d1 = round(random.gauss(0.0, 3.0), 2)
        rows.append({
            "ticker": n, "sector": sectors[n],
            "last":   round(random.uniform(40, 980), 2),
            "d1_pct":  d1,
            "mtd_pct": round(random.gauss(d1 * 1.5, 4.0), 2),
            "ytd_pct": round(random.gauss(8, 18), 2),
            "mcap_bn": round(random.uniform(50, 3200), 0),
            "vol_m":   round(random.uniform(2, 80), 1),
        })
    rows.sort(key=lambda r: r["d1_pct"], reverse=True)
    return pd.DataFrame(rows)


def _pull_wrap_curve_changes() -> pd.DataFrame:
    """1D / 1W / 1M bp changes across curve tenors (wide form)."""
    return pd.DataFrame([
        {"tenor": "2Y",  "d1_bp": 1.5,  "w1_bp":  4.0,  "m1_bp": -12.0},
        {"tenor": "5Y",  "d1_bp": 0.8,  "w1_bp":  2.5,  "m1_bp":  -9.5},
        {"tenor": "10Y", "d1_bp": -0.2, "w1_bp":  1.2,  "m1_bp":  -6.5},
        {"tenor": "20Y", "d1_bp": -1.0, "w1_bp":  0.1,  "m1_bp":  -4.0},
        {"tenor": "30Y", "d1_bp": -1.5, "w1_bp": -0.8,  "m1_bp":  -2.5},
    ])


def build_markets_wrap(out_dir: Path) -> Dict[str, Any]:
    """End-of-day cross-asset wrap. One big scrollable page with 4
    asset-class sections, 17 charts, KPI ribbon, and top-movers table."""
    df_eq = _pull_wrap_equities()
    df_sec = _pull_wrap_sectors()
    df_rt = _pull_wrap_rates()
    df_fx = _pull_wrap_fx_majors()
    df_cm = _pull_wrap_commodities()
    df_kpi = _pull_wrap_kpi_series()
    df_mov = _pull_wrap_top_movers()
    df_chg = _pull_wrap_curve_changes()

    manifest = {
        "schema_version": 1,
        "id": "markets_wrap",
        "title": "Cross-asset end-of-day wrap",
        "description": ("Single-page scrollable wrap of all major "
                         "asset classes. 17 charts stress-test the "
                         "compositor; customisation knobs exercise "
                         "legend placement, label humanisation, date "
                         "formatting, and KPI formatters."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "kerberos": "goyairl",
            "dashboard_id": "markets_wrap",
            "data_as_of": "2026-04-24T16:00:00Z",
            "generated_at": "2026-04-24T16:05:00Z",
            "sources": ["GS Market Data"],
            "refresh_frequency": "daily",
            "refresh_enabled": True,
            "tags": ["cross_asset", "eod"],
            "version": "1.0.0",
            "methodology": (
                "## Coverage\n\n"
                "End-of-day prints for the major asset classes: "
                "equities (regional + sector), rates (UST + global), "
                "FX (DXY + G10), commodities (energy + metals + ags), "
                "and credit (IG + HY).\n\n"
                "## Returns\n\n"
                "* Single-day moves are absolute price changes (or "
                "basis points for yields)\n"
                "* WTD / MTD / YTD tiles use simple price returns; "
                "FX is quote-currency depreciation ('+' = USD up)\n\n"
                "## Sector + regional bars\n\n"
                "Cap-weighted within sector; equal-weighted across "
                "regions for the global panel.\n\n"
                "## Notes\n\n"
                "Pre-market / overnight moves are excluded. "
                "Snapshot is a single timestamp, not VWAP."
            ),
        },
        "datasets": {
            "eq":  df_eq,  "sec": df_sec, "rt": df_rt,
            "fx":  df_fx,  "cm":  df_cm,  "kpi": df_kpi,
            "mov": df_mov, "chg": df_chg,
        },
        "filters": [
            # Wildcard prefix targets exercise the "fx_*" / "cm_*"
            # pattern that the rest of the gallery never reaches.
            # Together they cover every time-series chart on the
            # page without listing each widget id explicitly.
            {"id": "lookback", "type": "dateRange", "default": "1Y",
              "targets": ["eq_indices", "rt_curve",
                           "fx_*", "cm_*"],
              "field": "date", "label": "Initial range",
              "scope": "global",
              "description": ("Wildcard prefix targets (`fx_*`, "
                                "`cm_*`) plus explicit ids for the "
                                "remaining time-series tiles. Each "
                                "chart can still be zoomed "
                                "independently via its slider.")},
            {"id": "sector", "type": "select", "default": "",
              "all_value": "",
              "options": ["", "Technology", "Consumer Disc",
                           "Energy", "Financials",
                           "Comm Services", "Consumer Stp",
                           "Healthcare", "Industrials",
                           "Materials", "Real Estate",
                           "Utilities"],
              "field": "sector",
              "label": "Sector",
              "description": ("Filter the Top movers table by "
                                "S&P 500 GICS sector. Same filter "
                                "is set by clicking a bar in the "
                                "S&P 500 sectors YTD chart above."),
              "targets": ["movers_table"]},
        ],
        "layout": {"kind": "grid", "cols": 12, "rows": [
            # Top banner: image widget (GS Markets logo as inline
            # SVG data URL) + a markdown title strip beside it.
            [
                {"widget": "image", "id": "logo", "w": 3,
                  "src": (
                      "data:image/svg+xml;base64,"
                      "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdm"
                      "ciIHZpZXdCb3g9IjAgMCAyMjAgNjAiIHdpZHRoPSIyMjAiIGh"
                      "laWdodD0iNjAiPjxyZWN0IHdpZHRoPSIyMjAiIGhlaWdodD0i"
                      "NjAiIGZpbGw9IiMwMDJGNkMiLz48dGV4dCB4PSIxMTAiIHk9I"
                      "jQyIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaX"
                      "plPSIzMCIgZmlsbD0id2hpdGUiIHRleHQtYW5jaG9yPSJtaWR"
                      "kbGUiIGZvbnQtd2VpZ2h0PSI3MDAiPkdTIE1hcmtldHM8L3Rl"
                      "eHQ+PC9zdmc+"
                  ),
                  "alt": "GS Markets",
                  "link": "https://example.com/markets"},
                {"widget": "markdown", "id": "banner", "w": 9,
                  "content": ("# Cross-asset end-of-day wrap\n\n"
                                "*Equities, rates, FX, commodities -- "
                                "one scrollable page. Heat-mapped top "
                                "movers at the bottom.*")},
            ],
            [{"widget": "divider", "id": "div_kpi"}],
            [
                {"widget": "kpi", "id": "k_spx", "w": 2,
                  "label": "S&P 500",
                  "source": "kpi.latest.spx",
                  "delta_source": "kpi.prev.spx",
                  "sparkline_source": "kpi.spx",
                  "format": "comma", "decimals": 2},
                {"widget": "kpi", "id": "k_ndx", "w": 2,
                  "label": "Nasdaq 100",
                  "source": "kpi.latest.ndx",
                  "delta_source": "kpi.prev.ndx",
                  "sparkline_source": "kpi.ndx",
                  "format": "comma", "decimals": 2},
                {"widget": "kpi", "id": "k_10y", "w": 2,
                  "label": "UST 10Y",
                  "source": "kpi.latest.us_10y",
                  "delta_source": "kpi.prev.us_10y",
                  "sparkline_source": "kpi.us_10y",
                  "suffix": "%", "decimals": 3},
                {"widget": "kpi", "id": "k_dxy", "w": 2,
                  "label": "DXY",
                  "source": "kpi.latest.dxy",
                  "delta_source": "kpi.prev.dxy",
                  "sparkline_source": "kpi.dxy",
                  "decimals": 2},
                {"widget": "kpi", "id": "k_wti", "w": 2,
                  "label": "WTI",
                  "source": "kpi.latest.wti",
                  "delta_source": "kpi.prev.wti",
                  "sparkline_source": "kpi.wti",
                  "prefix": "$", "decimals": 2},
                {"widget": "kpi", "id": "k_vix", "w": 2,
                  "label": "VIX",
                  "source": "kpi.latest.vix",
                  "delta_source": "kpi.prev.vix",
                  "sparkline_source": "kpi.vix",
                  "decimals": 2},
            ],
            [{"widget": "divider", "id": "div_eq"}],
            [
                {"widget": "markdown", "id": "sec_eq", "w": 12,
                  "content": "## Equities"},
            ],
            [
                {"widget": "chart", "id": "eq_indices",
                  "w": 8, "h_px": 320,
                  "spec": {
                      "chart_type": "multi_line", "dataset": "eq",
                      "mapping": {
                          "x": "date",
                          "y": ["spx", "ndx", "dax", "nky", "ftse"],
                          "y_title": "Index level",
                          "x_date_format": "auto",
                          "series_labels": {
                              "spx":  "S&P 500",
                              "ndx":  "Nasdaq 100",
                              "dax":  "DAX",
                              "nky":  "Nikkei",
                              "ftse": "FTSE 100"},
                          "series_colors": {
                              "spx":  "#002F6C",
                              "ndx":  "#7399C6",
                              "dax":  "#B8860B",
                              "nky":  "#C53030",
                              "ftse": "#38A169"}},
                      "title": "Global equity indices",
                      "legend_position": "bottom",
                      "tooltip": {"trigger": "axis", "decimals": 0}}},
                {"widget": "chart", "id": "eq_sectors",
                  "w": 4, "h_px": 320,
                  "title": "S&P 500 sectors YTD",
                  "info": ("Click a sector bar to filter the "
                             "top-movers table below."),
                  "click_emit_filter": {"filter_id": "sector",
                                           "value_from": "name",
                                           "toggle": True},
                  "spec": {
                      "chart_type": "bar_horizontal",
                      "dataset": "sec",
                      "mapping": {"x": "ytd_pct", "y": "sector",
                                    "x_title": "YTD (%)",
                                    "legend_position": "none"},
                      "title": "S&P 500 sectors YTD"}},
            ],
            [{"widget": "divider", "id": "div_rt"}],
            [
                {"widget": "markdown", "id": "sec_rt", "w": 12,
                  "content": "## Rates"},
            ],
            [
                {"widget": "chart", "id": "rt_curve",
                  "w": 8, "h_px": 300,
                  "spec": {
                      "chart_type": "multi_line", "dataset": "rt",
                      "mapping": {
                          "x": "date",
                          "y": ["us_2y", "us_5y", "us_10y",
                                 "us_20y", "us_30y"],
                          "y_title": "Yield (%)",
                          "x_date_format": "auto"},
                      "title": "UST yield curve history",
                      "legend_position": "bottom"}},
                {"widget": "chart", "id": "rt_changes",
                  "w": 4, "h_px": 300,
                  "spec": {
                      "chart_type": "bar", "dataset": "chg",
                      "mapping": {"x": "tenor", "y": "d1_bp",
                                    "y_title": "1D change (bp)",
                                    "legend_position": "none"},
                      "title": "Curve shift (1D, bp)",
                      "annotations": [
                          {"type": "hline", "y": 0,
                            "color": "#718096",
                            "style": "dashed", "label": ""},
                      ]}},
            ],
            [{"widget": "divider", "id": "div_fx"}],
            [
                {"widget": "markdown", "id": "sec_fx", "w": 12,
                  "content": "## FX"},
            ],
            [
                {"widget": "chart", "id": "fx_majors",
                  "w": 8, "h_px": 280,
                  "spec": {
                      "chart_type": "multi_line", "dataset": "fx",
                      "mapping": {
                          "x": "date",
                          "y": ["dxy", "usdjpy"],
                          "dual_axis_series": ["usdjpy"],
                          "y_title": "DXY",
                          "y_title_right": "USD/JPY",
                          "x_date_format": "auto",
                          "series_labels": {
                              "dxy": "DXY",
                              "usdjpy": "USD/JPY"}},
                      "title": "DXY vs USD/JPY (dual-axis)",
                      "legend_position": "top"}},
                {"widget": "chart", "id": "fx_eg",
                  "w": 4, "h_px": 280,
                  "spec": {
                      "chart_type": "multi_line", "dataset": "fx",
                      "mapping": {
                          "x": "date",
                          "y": ["eurusd", "gbpusd"],
                          "y_title": "Rate",
                          "x_date_format": "auto",
                          "series_labels": {
                              "eurusd": "EUR/USD",
                              "gbpusd": "GBP/USD"}},
                      "title": "EUR vs GBP",
                      "legend_position": "top"}},
            ],
            [{"widget": "divider", "id": "div_cm"}],
            [
                {"widget": "markdown", "id": "sec_cm", "w": 12,
                  "content": "## Commodities"},
            ],
            [
                {"widget": "chart", "id": "cm_energy",
                  "w": 4, "h_px": 280,
                  "spec": {
                      "chart_type": "multi_line", "dataset": "cm",
                      "mapping": {
                          "x": "date", "y": ["wti", "brent"],
                          "y_title": "$ / bbl",
                          "x_date_format": "auto",
                          "series_labels": {
                              "wti": "WTI", "brent": "Brent"}},
                      "title": "Crude oil",
                      "legend_position": "top"}},
                {"widget": "chart", "id": "cm_metals",
                  "w": 4, "h_px": 280,
                  "spec": {
                      "chart_type": "multi_line", "dataset": "cm",
                      "mapping": {
                          "x": "date",
                          "y": ["gold", "copper"],
                          "dual_axis_series": ["copper"],
                          "y_title": "Gold ($/oz)",
                          "y_title_right": "Copper ($/lb)",
                          "x_date_format": "auto",
                          "series_labels": {
                              "gold": "Gold",
                              "copper": "Copper"}},
                      "title": "Gold vs Copper",
                      "legend_position": "top"}},
                {"widget": "chart", "id": "cm_ags",
                  "w": 4, "h_px": 280,
                  "spec": {
                      "chart_type": "line", "dataset": "cm",
                      "mapping": {"x": "date", "y": "wheat",
                                    "y_title": "$ / bu",
                                    "x_date_format": "auto",
                                    "legend_position": "none"},
                      "title": "Wheat"}},
            ],
            [{"widget": "divider", "id": "div_tab"}],
            [
                {"widget": "markdown", "id": "sec_tab", "w": 12,
                  "content": "## Top movers"},
            ],
            [
                {"widget": "table", "id": "movers_table", "w": 12,
                  "dataset_ref": "mov",
                  "title": ("Single-name top movers (click a row "
                              "for detail)"),
                  "searchable": True, "sortable": True,
                  "max_rows": 20, "row_height": "compact",
                  "info": ("Rows highlighted green / red based on "
                             "1-day move. Click a sector bar above "
                             "to filter."),
                  "row_highlight": [
                      {"field": "d1_pct", "op": ">",
                        "value": 2.0, "class": "pos"},
                      {"field": "d1_pct", "op": "<",
                        "value": -2.0, "class": "neg"},
                  ],
                  "columns": [
                      {"field": "ticker",  "label": "Ticker",
                        "align": "left"},
                      {"field": "sector",  "label": "Sector",
                        "align": "left"},
                      {"field": "last",    "label": "Last",
                        "format": "number:2", "align": "right"},
                      {"field": "d1_pct",   "label": "1D",
                        "format": "signed:2", "align": "right",
                        "conditional": [
                            {"op": ">", "value": 0, "color": "#38a169"},
                            {"op": "<", "value": 0, "color": "#c53030"},
                        ]},
                      {"field": "mtd_pct",  "label": "MTD",
                        "format": "signed:2", "align": "right",
                        "conditional": [
                            {"op": ">", "value": 0, "color": "#38a169"},
                            {"op": "<", "value": 0, "color": "#c53030"},
                        ]},
                      {"field": "ytd_pct",  "label": "YTD",
                        "format": "signed:2", "align": "right",
                        "color_scale": {"min": -20, "max": 40,
                                          "palette": "gs_diverging"}},
                      {"field": "mcap_bn", "label": "Mkt Cap",
                        "format": "number:0", "align": "right"},
                      {"field": "vol_m",   "label": "Vol",
                        "format": "number:1", "align": "right"},
                  ]},
            ],
        ]},
        "links": [
            # legend sync exercises a sync value the rest of the
            # gallery misses (axis / tooltip / dataZoom are common;
            # legend stays in sync as the user toggles series).
            {"group": "sync_wrap",
              "members": ["eq_indices", "rt_curve",
                           "fx_majors", "cm_energy", "cm_metals"],
              "sync": ["axis", "tooltip", "dataZoom", "legend"]},
        ],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1500, height=2400)
    return _result(r, thumb)


# =============================================================================
# DEMO: screener_studio  (self-contained: data + manifest)
# =============================================================================
#
# Shows off the `row_click.detail` rich-popup pattern: click any bond
# row and a modal opens with per-bond stats, issuer blurb, price
# history chart, and OAS-spread chart, all dynamically filtered from
# manifest datasets by the clicked bond's CUSIP.


_BOND_UNIVERSE = [
    # cusip       issuer                  coupon  maturity     rating  sector
    ("037833AZ1", "Apple Inc.",            3.250, "2030-02-08", "AA+",  "Technology"),
    ("594918BW3", "Microsoft Corp.",       2.700, "2031-02-12", "AAA",  "Technology"),
    ("38141GXL3", "Goldman Sachs Group",   4.750, "2033-02-10", "A+",   "Financials"),
    ("46625HRT9", "JPMorgan Chase",        5.100, "2034-02-12", "AA-",  "Financials"),
    ("06051GJG4", "Bank of America",       4.950, "2033-02-01", "A+",   "Financials"),
    ("30231GAS4", "Exxon Mobil Corp.",     3.950, "2032-09-12", "AA-",  "Energy"),
    ("166764BH4", "Chevron Corp.",         3.800, "2029-03-03", "AA",   "Energy"),
    ("437076BR3", "Home Depot Inc.",       4.300, "2028-05-15", "A",    "Consumer"),
    ("931142DN8", "Walmart Inc.",          4.150, "2030-04-01", "AA",   "Consumer"),
    ("717081EZ4", "Pfizer Inc.",           2.750, "2029-10-28", "A+",   "Healthcare"),
    ("478160CN2", "Johnson & Johnson",     3.400, "2029-01-15", "AAA",  "Healthcare"),
    ("25746UCG7", "Dominion Energy",       5.250, "2033-08-15", "BBB+", "Utilities"),
    ("17275RAY8", "Cisco Systems",         3.625, "2029-03-04", "AA-",  "Technology"),
    ("88160RAG6", "Tesla Inc.",            5.300, "2030-08-15", "BB",   "Consumer"),
    ("68389XAX3", "Oracle Corp.",          4.000, "2029-07-15", "BBB+", "Technology"),
    ("437086AQ0", "HCA Healthcare",        5.450, "2034-06-01", "BB+",  "Healthcare"),
    ("65339FAS8", "Netflix Inc.",          4.875, "2028-06-15", "BBB-", "Media"),
    ("26884LAK7", "EPR Properties",        6.100, "2031-04-15", "BB+",  "REIT"),
    ("125581GV0", "CMS Energy Corp.",      4.500, "2032-09-15", "BBB+", "Utilities"),
    ("459200HZ7", "IBM Corp.",             3.300, "2030-05-15", "A-",   "Technology"),
]


_RATING_SPREAD_BP = {
    "AAA": 45, "AA+": 60, "AA": 75, "AA-": 90,
    "A+": 100, "A": 115, "A-": 135,
    "BBB+": 160, "BBB": 185, "BBB-": 215,
    "BB+": 260, "BB": 320, "BB-": 390,
}


def _pull_bond_main() -> pd.DataFrame:
    """Main bond table. Derived YTM, spread, duration, current-yield,
    price from the universe definition + coupon + rating."""
    random.seed(SEED + 600)
    rows = []
    today = pd.Timestamp(END_DATE)
    for cusip, issuer, coupon, maturity, rating, sector in _BOND_UNIVERSE:
        mat = pd.Timestamp(maturity)
        years = max(0.1, (mat - today).days / 365.25)
        ust_level = 4.20 + random.gauss(0, 0.03)
        spread = _RATING_SPREAD_BP.get(rating, 120) + random.gauss(0, 8)
        ytm = ust_level + spread / 100
        duration = max(0.1, years / (1 + ytm / 100) * 0.92)
        price = round(100 + (coupon - ytm) * duration, 3)
        current_yield = coupon / price * 100
        rows.append({
            "cusip": cusip,
            "issuer": issuer,
            "sector": sector,
            "rating": rating,
            "coupon_pct": round(coupon, 3),
            "maturity": maturity,
            "years_to_maturity": round(years, 2),
            "price": round(price, 2),
            "ytm_pct": round(ytm, 3),
            "spread_bp": round(spread, 1),
            "duration_yrs": round(duration, 2),
            "current_yield_pct": round(current_yield, 3),
        })
    return pd.DataFrame(rows)


def _bond_main_field_provenance() -> Dict[str, Dict[str, Any]]:
    """Per-column lineage for the bond universe dataset. Illustrative
    rather than real (the demo is synthetic) but mirrors the canonical
    shape PRISM emits in production: GS market_data coordinates for
    valuation columns, an internal bond reference table for static
    descriptors, computed columns for derived quantities. Drives the
    "Sources" footer on every click popup -- both the explicit ones
    in this demo and the auto-default popups (top_total bar, sector
    summary chart) where no click_popup is declared."""
    md = "GS Market Data"
    ref = "GS Bond Reference Master"
    return {
        "cusip":       {"system": "csv", "symbol": "bond_master:cusip",
                         "source_label": ref,
                         "display_name": "CUSIP"},
        "issuer":      {"system": "csv", "symbol": "bond_master:issuer",
                         "source_label": ref,
                         "display_name": "Issuer"},
        "sector":      {"system": "csv", "symbol": "bond_master:sector",
                         "source_label": ref, "display_name": "Sector"},
        "rating":      {"system": "csv", "symbol": "bond_master:rating",
                         "source_label": ref, "display_name": "Composite rating"},
        "coupon_pct":  {"system": "csv", "symbol": "bond_master:coupon",
                         "source_label": ref, "display_name": "Coupon",
                         "units": "percent"},
        "maturity":    {"system": "csv", "symbol": "bond_master:maturity",
                         "source_label": ref, "display_name": "Maturity"},
        "years_to_maturity": {"system": "computed",
                                 "recipe": "(maturity - as_of) / 365.25",
                                 "computed_from": ["maturity"],
                                 "display_name": "Years to maturity",
                                 "units": "years"},
        "price":       {"system": "market_data",
                         "symbol": "FI_Corp_<cusip>_CleanPrice",
                         "tsdb_symbol": "fi.corp.<cusip>.clean_px",
                         "source_label": md,
                         "display_name": "Clean price"},
        "ytm_pct":     {"system": "market_data",
                         "symbol": "FI_Corp_<cusip>_YTM",
                         "tsdb_symbol": "fi.corp.<cusip>.ytm",
                         "source_label": md,
                         "display_name": "YTM",
                         "units": "percent"},
        "spread_bp":   {"system": "market_data",
                         "symbol": "FI_Corp_<cusip>_Spread",
                         "tsdb_symbol": "fi.corp.<cusip>.oas",
                         "source_label": md,
                         "display_name": "OAS to UST",
                         "units": "bp"},
        "duration_yrs": {"system": "computed",
                          "recipe": "years_to_maturity / (1 + ytm/100) * 0.92",
                          "computed_from": ["years_to_maturity", "ytm_pct"],
                          "display_name": "Modified duration",
                          "units": "years"},
        "current_yield_pct": {"system": "computed",
                                "recipe": "coupon_pct / price * 100",
                                "computed_from": ["coupon_pct", "price"],
                                "display_name": "Current yield",
                                "units": "percent"},
        "carry_bp":    {"system": "computed",
                         "recipe": "(ytm_pct - financing_rate) * 100",
                         "computed_from": ["ytm_pct"],
                         "display_name": "Carry",
                         "units": "bp"},
        "roll_bp":     {"system": "computed",
                         "recipe": "approx rolldown along the curve",
                         "computed_from": ["duration_yrs", "spread_bp"],
                         "display_name": "Roll",
                         "units": "bp"},
        "total_bp":    {"system": "computed",
                         "recipe": "carry_bp + roll_bp",
                         "computed_from": ["carry_bp", "roll_bp"],
                         "display_name": "Total expected return",
                         "units": "bp"},
        "financing_bp": {"system": "market_data",
                          "symbol": "FI_USD_1M_FundingRate",
                          "tsdb_symbol": "fi.usd.fund.1m",
                          "source_label": md,
                          "display_name": "1M financing rate",
                          "units": "bp"},
        "blurb":       {"system": "csv", "symbol": "issuer_blurbs:blurb",
                         "source_label": "GS Research issuer notes"},
    }


def _bond_hist_field_provenance() -> Dict[str, Dict[str, Any]]:
    """Provenance for the bond_hist dataset (price + spread time
    series filtered per CUSIP in click-popup detail charts)."""
    md = "GS Market Data"
    return {
        "date":      {"system": "index", "symbol": "date",
                       "display_name": "Date"},
        "cusip":     {"system": "csv", "symbol": "bond_master:cusip",
                       "source_label": "GS Bond Reference Master"},
        "price":     {"system": "market_data",
                       "symbol": "FI_Corp_<cusip>_CleanPrice_EOD",
                       "tsdb_symbol": "fi.corp.<cusip>.clean_px.eod",
                       "source_label": md, "units": "USD"},
        "spread_bp": {"system": "market_data",
                       "symbol": "FI_Corp_<cusip>_OAS_EOD",
                       "tsdb_symbol": "fi.corp.<cusip>.oas.eod",
                       "source_label": md, "units": "bp"},
    }


def _pull_bond_price_history() -> pd.DataFrame:
    """Daily price + spread history per bond for the last 180 biz days.
    Modeled off the current price with stochastic shocks biased toward
    the rating level."""
    random.seed(SEED + 601)
    dates = pd.date_range(end=END_DATE, periods=180, freq="B")
    main = _pull_bond_main().set_index("cusip")
    rows = []
    for cusip, rec in main.iterrows():
        price = rec["price"] - random.uniform(1.5, 4.5)
        spread = rec["spread_bp"] + random.uniform(-25, 25)
        for d in dates:
            price += random.gauss(0.004, 0.12)
            spread += random.gauss(0, 1.5)
            spread = max(5, spread)
            rows.append({
                "cusip": cusip,
                "date": d,
                "price": round(price, 3),
                "spread_bp": round(spread, 1),
                "ytm_pct": round(rec["ytm_pct"]
                                    + (spread - rec["spread_bp"]) / 100, 3),
            })
        # Make the last row line up with the main table's reported
        # levels so the popup charts visually converge on the row stats.
        rows[-1]["price"] = rec["price"]
        rows[-1]["spread_bp"] = rec["spread_bp"]
    return pd.DataFrame(rows)


_BOND_ISSUER_BLURBS = {
    "Apple Inc.":        ("US-headquartered consumer tech. Net cash "
                            "position ~$60bn, category leader in "
                            "smartphones & wearables."),
    "Microsoft Corp.":   ("Enterprise software + hyperscale cloud "
                            "(Azure). Investment grade benchmark issuer."),
    "Goldman Sachs Group": ("Global investment bank. Senior holdco "
                              "paper, callable step-up structure."),
    "JPMorgan Chase":    ("Largest US bank by deposits. Bail-in "
                            "senior holdco paper."),
    "Bank of America":   ("US G-SIB. Senior holdco paper subject to "
                            "the Fed's SPOE resolution regime."),
    "Exxon Mobil Corp.": ("Integrated supermajor. AA-range senior "
                            "unsecured."),
    "Chevron Corp.":     ("Integrated supermajor. Strong balance "
                            "sheet; benchmark IG energy."),
    "Home Depot Inc.":   ("Home-improvement retailer. Stable FCF, "
                            "consistent buyer of A-range paper."),
    "Walmart Inc.":      ("US-listed mass retailer. AA credit; "
                            "stable cash generation through cycles."),
    "Pfizer Inc.":       ("Global pharma. Post-Seagen integration "
                            "leverage modestly elevated."),
    "Johnson & Johnson": ("Diversified healthcare. AAA-rated; "
                            "pristine balance sheet."),
    "Dominion Energy":   ("US regulated utility. BBB+ paper with "
                            "stable regulated ROE underpinning."),
    "Cisco Systems":     ("Network hardware + subscription pivot. "
                            "Net cash; strong IG credit."),
    "Tesla Inc.":        ("EV manufacturer. BB high-yield despite "
                            "cash cushion; cyclical fundamentals."),
    "Oracle Corp.":      ("Enterprise software + cloud. Shareholder "
                            "returns-heavy balance sheet (BBB+)."),
    "HCA Healthcare":    ("US hospital operator. BB+ senior paper; "
                            "cash-flow driven credit."),
    "Netflix Inc.":      ("Streaming. Recently IG (BBB-); FCF "
                            "positive since 2022."),
    "EPR Properties":    ("Experiential REIT. Theatre exposure; BB+ "
                            "with wide spread."),
    "CMS Energy Corp.":  ("Michigan regulated utility. BBB+ with "
                            "defensive cash flow."),
    "IBM Corp.":         ("Diversified tech services. A- credit; "
                            "consistent dividend payer."),
}


def _pull_bond_issuer_blurbs() -> pd.DataFrame:
    rows = []
    for _, issuer, *_ in _BOND_UNIVERSE:
        rows.append({"issuer": issuer,
                      "blurb": _BOND_ISSUER_BLURBS.get(issuer, "")})
    return pd.DataFrame(rows)


def _pull_bond_recent_events() -> pd.DataFrame:
    """Per-issuer recent event log -- lets the detail popup include a
    sub-table filtered to the clicked bond's issuer."""
    random.seed(SEED + 602)
    events = [
        ("Apple Inc.",     "2026-04-01", "Earnings beat",
          "+3.5bp tighten"),
        ("Apple Inc.",     "2026-03-15", "Buyback announced",
          "+2bp tighten"),
        ("Apple Inc.",     "2026-01-28", "iPhone refresh",
          "Neutral"),
        ("Microsoft Corp.","2026-04-22", "Cloud Q4 beat",
          "+4bp tighten"),
        ("Microsoft Corp.","2026-02-10", "Capex guide raised",
          "Neutral"),
        ("Goldman Sachs Group","2026-04-15", "Q1 earnings",
          "+1bp tighten"),
        ("Goldman Sachs Group","2026-03-20", "New $10B issuance",
          "+6bp widen"),
        ("JPMorgan Chase", "2026-04-12", "Q1 earnings beat",
          "+2bp tighten"),
        ("Bank of America","2026-03-08", "Stress test pass",
          "+1bp tighten"),
        ("Exxon Mobil Corp.","2026-03-01", "Permian acquisition",
          "+3bp widen"),
        ("Chevron Corp.",  "2026-02-15", "Hess deal closed",
          "Neutral"),
        ("Home Depot Inc.","2026-04-05", "Q1 comp sales miss",
          "+5bp widen"),
        ("Walmart Inc.",   "2026-02-20", "Grocery guide raised",
          "+2bp tighten"),
        ("Pfizer Inc.",    "2026-04-10", "Seagen integration update",
          "+4bp tighten"),
        ("Johnson & Johnson","2026-03-25", "Talc litigation update",
          "Neutral"),
        ("Dominion Energy","2026-02-05", "Rate case filed",
          "+2bp widen"),
        ("Cisco Systems",  "2026-04-01", "Splunk integration",
          "+3bp tighten"),
        ("Tesla Inc.",     "2026-03-30", "Model Q debut",
          "+15bp widen"),
        ("Tesla Inc.",     "2026-02-08", "China delivery miss",
          "+22bp widen"),
        ("Oracle Corp.",   "2026-04-18", "Cloud Q4 beat",
          "+3bp tighten"),
        ("HCA Healthcare", "2026-03-15", "Volume beat",
          "+5bp tighten"),
        ("Netflix Inc.",   "2026-04-02", "Subs beat 3M",
          "+8bp tighten"),
        ("EPR Properties", "2026-03-05", "Theatre rent coverage",
          "+10bp widen"),
        ("CMS Energy Corp.","2026-02-28", "Capex plan raised",
          "+3bp widen"),
        ("IBM Corp.",      "2026-04-14", "Cloud revenue beat",
          "+4bp tighten"),
    ]
    return pd.DataFrame(events,
                          columns=["issuer", "date", "event", "reaction"])


def build_screener_studio(out_dir: Path) -> Dict[str, Any]:
    """Three-tab table / filter / drill-down studio.

    Tab 1 - RV screen: rich z-score RV table with conditional formatting,
    drill-down time-series charts, stat_grid headline panel.
    Tab 2 - Filter library: every filter type (9) bound to one dataset,
    feeding scatter + stacked bar + searchable table.
    Tab 3 - Bond drill-down: IG+HY universe table with row_click.detail
    rich modal (stats, markdown, per-row charts, sub-table).

    Filters auto-scope to the tab their targets live in so each tab
    shows only its own controls. Covers: all 9 filter types, conditional
    cell formatting, z-score color_scale, row_highlight classes,
    row_click popup (simple + detail modal), searchable / sortable
    tables, inverted y-axis chart, drill-down filtering from row key.
    """
    df_rv = pull_rates_rv_rich()
    df_rates = pull_rates_panel()
    df_fs = pull_active_filters_demo()
    df_main = _pull_bond_main()
    df_hist = _pull_bond_price_history()
    df_blurbs = _pull_bond_issuer_blurbs()
    df_events = _pull_bond_recent_events()

    n_bonds = len(df_main)
    avg_ytm = round(float(df_main["ytm_pct"].mean()), 2)
    avg_spread = round(float(df_main["spread_bp"].mean()), 1)
    hy_count = int(df_main["rating"].isin(
        ["BB+", "BB", "BB-", "B+", "B", "B-"]).sum())

    manifest = {
        "schema_version": 1,
        "id": "screener_studio",
        "title": "Screener studio (tables / filters / drill-down)",
        "description": ("Three-tab toolbox showing every table + filter "
                         "+ drill-down pattern in the stack. Tab 1: rich "
                         "RV screen with conditional formatting + z-score "
                         "colour scale. Tab 2: all 9 filter types on one "
                         "dataset. Tab 3: bond universe with row-click "
                         "rich-modal drill-down."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "data_as_of": "2026-04-24T16:30:00Z",
            "generated_at": "2026-04-24T16:35:00Z",
            "sources": ["GS Market Data", "FRED"],
            "tags": ["rates", "credit", "screener"],
            "methodology": (
                "## RV screen\n\n"
                "Each row is a relative-value pair. Z-score is the "
                "current spread minus the rolling 1Y mean, divided by "
                "its rolling 1Y stdev. Cell colours map to z bins:\n\n"
                "* `z >= 2`  rich (blue)\n"
                "* `z <= -2` cheap (gold)\n"
                "* `|z| < 0.5` neutral (white)\n\n"
                "## Filter library\n\n"
                "All nine filter types bound to a single synthetic "
                "dataset so the wiring of each control type is "
                "demonstrable in isolation. No live data; for shape "
                "reference only.\n\n"
                "## Bond universe\n\n"
                "IG + HY USD bonds with daily indicative spreads "
                "(GS market data). Row click opens a detail modal: "
                "issuer blurb, recent events, price history, and "
                "issuer-level peer table."
            ),
        },
        "datasets": {
            "rv": df_rv,
            "rates": df_rates,
            "rows": df_fs,
            "bonds": df_main,
            "bond_hist": df_hist,
            "bond_blurbs": df_blurbs,
            "bond_events": df_events,
        },
        "filters": [
            # Tab 1 (auto-scoped to rv_screen via targets)
            {"id": "asset", "type": "radio", "default": "All",
              "all_value": "All",
              "options": ["All", "Rates", "FX", "Credit",
                           "Equity", "Commodity"],
              "field": "asset_class", "label": "Asset class",
              "targets": ["rv_table"]},
            {"id": "z_thresh", "type": "slider",
              "default": 0, "min": 0, "max": 2, "step": 0.1,
              "field": "z", "op": ">=", "transform": "abs",
              "label": "|z| >=", "targets": ["rv_table"]},
            {"id": "metric_search", "type": "text", "default": "",
              "field": "metric", "op": "contains",
              "label": "Metric contains",
              "placeholder": "e.g. 10Y, vol, spread",
              "targets": ["rv_table"]},
            # Tab 2 (auto-scoped to filter_library: all 9 filter types)
            {"id": "fs_lookback", "type": "dateRange", "default": "6M",
              "field": "date", "label": "Initial range",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_region", "type": "select", "default": "",
              "all_value": "",
              "options": ["", "US", "EU", "UK", "Japan", "EM"],
              "field": "region", "label": "Region",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_sectors", "type": "multiSelect", "default": [],
              "options": ["Tech", "Financials", "Energy",
                           "Healthcare", "Consumer"],
              "field": "sector", "label": "Sectors",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_rating", "type": "radio", "default": "Any",
              "all_value": "Any",
              "options": ["Any", "AAA", "AA", "A", "BBB", "BB"],
              "field": "rating", "label": "Rating",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_min_vol", "type": "slider",
              "default": 0, "min": 0, "max": 40, "step": 1,
              "field": "volatility", "op": ">=",
              "label": "Min vol",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_max_dd", "type": "number",
              "default": "", "min": -20, "max": 20, "step": 0.5,
              "field": "return_pct", "op": ">=",
              "label": "Return >=",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_mcap_range", "type": "numberRange",
              "default": [1, 100], "field": "mcap_b",
              "label": "Mkt cap (\u0024B, min,max)",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_tech_only", "type": "toggle", "default": False,
              "field": "is_tech", "label": "Tech only",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            {"id": "fs_search", "type": "text", "default": "",
              "field": "ticker", "op": "contains",
              "label": "Ticker search",
              "placeholder": "TEC-US...",
              "targets": ["vol_by_sector", "count_by_rating",
                           "rows_table"]},
            # Tab 3 (auto-scoped to bond_drill via targets)
            {"id": "bs_sector", "type": "select", "default": "",
              "all_value": "",
              "options": ["", "Technology", "Financials", "Energy",
                           "Consumer", "Healthcare", "Utilities",
                           "Media", "REIT"],
              "field": "sector", "label": "Sector",
              "targets": ["bond_table"]},
            {"id": "bs_rating_bucket", "type": "radio",
              "default": "All", "all_value": "All",
              "options": ["All", "IG", "HY"],
              "field": "rating",
              "targets": ["bond_table"],
              "description": ("Crude IG/HY split: IG = AAA through "
                                "BBB-, HY = BB+ and wider. Map your "
                                "actual credit policy definitions in "
                                "production.")},
            {"id": "bs_max_ytm", "type": "slider",
              "default": 15, "min": 0, "max": 15, "step": 0.25,
              "field": "ytm_pct", "op": "<=",
              "label": "Max YTM (%)",
              "targets": ["bond_table"]},
        ],
        "layout": {"kind": "tabs", "tabs": [
            {"id": "rv_screen", "label": "RV screen",
              "description": ("Cross-asset relative-value monitor with "
                               "conditional formatting, z-score colour "
                               "scale, and drill-down time-series."),
              "rows": [
                [
                    {"widget": "stat_grid", "id": "rv_summary", "w": 12,
                      "title": "Current readings",
                      "stats": [
                          {"id": "s1", "label": "2s10s (bp)",
                            "value": "+38", "sub": "z = +0.9"},
                          {"id": "s2", "label": "MOVE index",
                            "value": "102", "sub": "z = +0.3"},
                          {"id": "s3", "label": "USDJPY 1M vol",
                            "value": "9.4", "sub": "z = -1.8 (low)"},
                          {"id": "s4", "label": "HY OAS",
                            "value": "285 bp", "sub": "z = -1.1 (tight)"},
                          {"id": "s5", "label": "Gold ($/oz)",
                            "value": "2,520", "sub": "z = +1.3 (hi)"},
                          {"id": "s6", "label": "VIX 1M",
                            "value": "16.5", "sub": "z = -0.6"},
                      ]},
                ],
                [
                    {"widget": "table", "id": "rv_table", "w": 12,
                      "dataset_ref": "rv",
                      "title": "RV screen (click a row for detail)",
                      "searchable": True, "sortable": True,
                      "max_rows": 50,
                      "empty_message": ("No metrics match the current "
                                          "filters."),
                      "columns": [
                          {"field": "metric", "label": "Metric",
                            "align": "left",
                            "tooltip": "RV metric name"},
                          {"field": "asset_class", "label": "Class",
                            "align": "left",
                            "tooltip": "Macro asset class bucket"},
                          {"field": "bucket", "label": "Bucket",
                            "align": "left"},
                          {"field": "current", "label": "Current",
                            "format": "number:2", "align": "right",
                            "tooltip": "Latest observation"},
                          {"field": "low_5y", "label": "5Y low",
                            "format": "number:2", "align": "right"},
                          {"field": "high_5y", "label": "5Y high",
                            "format": "number:2", "align": "right"},
                          {"field": "z", "label": "Z",
                            "format": "signed:2", "align": "right",
                            "tooltip": ("5Y rolling z-score of "
                                           "current"),
                            "color_scale": {"min": -2, "max": 2,
                                              "palette": "gs_diverging"}},
                          {"field": "pct", "label": "Pctile",
                            "format": "percent:0", "align": "right",
                            "tooltip": "5Y percentile (0-100%)",
                            "conditional": [
                                {"op": ">=", "value": 0.85,
                                  "background": "#c53030",
                                  "color": "#ffffff", "bold": True},
                                {"op": ">=", "value": 0.70,
                                  "background": "#fed7d7"},
                                {"op": "<=", "value": 0.15,
                                  "background": "#2b6cb0",
                                  "color": "#ffffff", "bold": True},
                                {"op": "<=", "value": 0.30,
                                  "background": "#bee3f8"},
                            ]},
                          {"field": "ytd_chg",
                            "label": "YTD \u0394",
                            "format": "delta:2", "align": "right",
                            "tooltip": "YTD change in level",
                            "conditional": [
                                {"op": ">", "value": 0,
                                  "color": "#38a169"},
                                {"op": "<", "value": 0,
                                  "color": "#c53030"},
                            ]},
                      ],
                      "row_click": {
                          "title_field": "metric",
                          "popup_fields": [
                              "metric", "asset_class", "bucket",
                              "current", "low_5y", "high_5y",
                              "z", "pct", "ytd_chg", "note"]}},
                ],
                [
                    {"widget": "chart", "id": "rates_history",
                      "w": 8, "h_px": 320,
                      "spec": {
                          "chart_type": "multi_line",
                          "dataset": "rates",
                          "mapping": {
                              "x": "date",
                              "y": ["us_2y", "us_10y"],
                              "y_title": "Yield (%)"},
                          "title": "UST 2Y vs 10Y"}},
                    {"widget": "chart", "id": "spread_inverted",
                      "w": 4, "h_px": 320,
                      "spec": {
                          "chart_type": "line", "dataset": "rates",
                          "mapping": {
                              "x": "date", "y": "2s10s",
                              "y_title": "2s10s (bp, inverted)",
                              "invert_y": True},
                          "title": "2s10s (inverted y)",
                          "subtitle": "up = flattening",
                          "annotations": [
                              {"type": "hline", "y": 0,
                                "label": "Flat curve",
                                "color": "#c53030",
                                "style": "dashed"},
                          ]}},
                ],
            ]},
            {"id": "filter_library", "label": "Filter library",
              "description": ("Every filter type supported by the "
                               "manifest (dateRange, select, "
                               "multiSelect, numberRange, toggle, "
                               "slider, radio, text, number) bound to "
                               "one dataset."),
              "rows": [
                [
                    {"widget": "markdown", "id": "fs_intro", "w": 12,
                      "content": (
                          "### Filter reference\n\n"
                          "All 9 filter types above are wired to the "
                          "same underlying dataset. Every filter has "
                          "a `field` (the column to filter against) "
                          "and an `op` (`==`, `>=`, `contains`, etc.). "
                          "Change any control above to watch the "
                          "chart and table below update.")},
                ],
                [
                    {"widget": "chart", "id": "vol_by_sector",
                      "w": 6, "h_px": 320,
                      "spec": {
                          "chart_type": "scatter", "dataset": "rows",
                          "mapping": {"x": "volatility",
                                        "y": "return_pct",
                                        "color": "sector",
                                        "size": "mcap_b",
                                        "x_title": "Volatility (%)",
                                        "y_title": "Return (%)"},
                          "title": "Vol vs return (size = mcap)",
                          "annotations": [
                              {"type": "hline", "y": 0,
                                "color": "#718096",
                                "style": "dashed", "label": ""},
                          ]}},
                    {"widget": "chart", "id": "count_by_rating",
                      "w": 6, "h_px": 320,
                      "spec": {
                          "chart_type": "bar", "dataset": "rows",
                          "mapping": {"x": "rating", "y": "mcap_b",
                                        "color": "sector",
                                        "stack": True,
                                        "x_sort": ["AAA", "AA", "A",
                                                    "BBB", "BB"],
                                        "y_title": "Mkt cap sum ($B)"},
                          "title": "Mkt cap by rating x sector"}},
                ],
                [
                    {"widget": "table", "id": "rows_table", "w": 12,
                      "dataset_ref": "rows",
                      "title": "Matching rows (sort, search, click)",
                      "searchable": True, "sortable": True,
                      "max_rows": 30, "row_height": "compact",
                      "empty_message": ("No rows match the current "
                                          "filters."),
                      "columns": [
                          {"field": "date", "label": "Date",
                            "format": "date", "align": "left"},
                          {"field": "ticker", "label": "Ticker",
                            "align": "left"},
                          {"field": "sector", "label": "Sector",
                            "align": "left"},
                          {"field": "region", "label": "Region",
                            "align": "left"},
                          {"field": "rating", "label": "Rating",
                            "align": "center"},
                          {"field": "volatility", "label": "Vol",
                            "format": "number:1", "align": "right",
                            "color_scale": {"min": 5, "max": 35,
                                              "palette": "gs_blues"}},
                          {"field": "return_pct", "label": "Return",
                            "format": "signed:2", "align": "right",
                            "conditional": [
                                {"op": ">", "value": 0,
                                  "color": "#38a169"},
                                {"op": "<", "value": 0,
                                  "color": "#c53030"},
                            ]},
                          {"field": "mcap_b", "label": "Mkt cap",
                            "format": "currency:1", "align": "right"},
                      ],
                      "row_click": {
                          "title_field": "ticker",
                          "popup_fields": ["date", "ticker", "sector",
                                             "region", "rating",
                                             "volatility",
                                             "return_pct",
                                             "mcap_b"]}},
                ],
            ]},
            {"id": "bond_drill", "label": "Bond drill-down",
              "description": ("Single-name IG + HY universe. Click any "
                               "row for per-bond stats, issuer blurb, "
                               "price + OAS history, and recent-event "
                               "log filtered to that CUSIP."),
              "rows": [
                [
                    {"widget": "kpi", "id": "k_n", "label": "Bonds",
                      "value": n_bonds, "format": "comma", "w": 3,
                      "info": ("Bonds in the universe after "
                                 "filters.")},
                    {"widget": "kpi", "id": "k_ytm",
                      "label": "Avg YTM", "value": avg_ytm,
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "k_spread",
                      "label": "Avg spread", "value": avg_spread,
                      "suffix": " bp", "decimals": 0, "w": 3},
                    {"widget": "kpi", "id": "k_hy", "label": "HY count",
                      "value": hy_count, "format": "comma",
                      "sub": "BB+ and wider", "w": 3},
                ],
                [
                    {"widget": "table", "id": "bond_table", "w": 12,
                      "dataset_ref": "bonds",
                      "title": "Bond universe",
                      "info": ("Click any row to open the per-bond "
                                 "drill-down."),
                      "searchable": True, "sortable": True,
                      "max_rows": 30, "row_height": "compact",
                      "columns": [
                          {"field": "cusip", "label": "CUSIP",
                            "align": "left", "format": "text"},
                          {"field": "issuer", "label": "Issuer",
                            "align": "left",
                            "tooltip": ("Click row for full issuer "
                                          "drill-down.")},
                          {"field": "sector", "label": "Sector",
                            "align": "left"},
                          {"field": "rating", "label": "Rating",
                            "align": "center"},
                          {"field": "coupon_pct", "label": "Coupon",
                            "format": "number:2", "align": "right",
                            "tooltip": "Coupon rate (%)"},
                          {"field": "maturity", "label": "Maturity",
                            "align": "left"},
                          {"field": "years_to_maturity",
                            "label": "YTM (yrs)",
                            "format": "number:1", "align": "right"},
                          {"field": "price", "label": "Price",
                            "format": "number:2", "align": "right"},
                          {"field": "ytm_pct", "label": "YTM (%)",
                            "format": "number:2", "align": "right",
                            "color_scale": {"min": 3, "max": 12,
                                              "palette": "gs_blues"}},
                          {"field": "spread_bp", "label": "Spread (bp)",
                            "format": "number:0", "align": "right",
                            "color_scale": {"min": 40, "max": 400,
                                              "palette": "gs_blues"},
                            "tooltip": ("OAS spread over UST "
                                          "curve (bp)")},
                          {"field": "duration_yrs",
                            "label": "Dur (yrs)",
                            "format": "number:2", "align": "right"},
                      ],
                      "row_highlight": [
                          {"field": "spread_bp", "op": ">",
                            "value": 250, "class": "warn"},
                          {"field": "rating", "op": "==",
                            "value": "AAA", "class": "pos"},
                      ],
                      "row_click": {
                          "title_field": "issuer",
                          "subtitle_template": (
                              "CUSIP {cusip} \u00B7 "
                              "{coupon_pct:number:2}% "
                              "coupon \u00B7 matures {maturity}"
                          ),
                          "detail": {
                              "wide": True,
                              "sections": [
                                  {"type": "stats",
                                    "fields": [
                                        {"field": "price",
                                          "label": "Price",
                                          "format": "number:2"},
                                        {"field": "ytm_pct",
                                          "label": "YTM",
                                          "format": "number:2",
                                          "suffix": "%"},
                                        {"field": "spread_bp",
                                          "label": "Spread",
                                          "format": "number:0",
                                          "suffix": " bp"},
                                        {"field": "duration_yrs",
                                          "label": "Duration",
                                          "format": "number:2",
                                          "suffix": " yrs"},
                                        {"field": "current_yield_pct",
                                          "label": "Current yield",
                                          "format": "number:2",
                                          "suffix": "%"},
                                        {"field": "rating",
                                          "label": "Rating"},
                                    ]},
                                  {"type": "markdown",
                                    "template": (
                                        "**{issuer}** \u00B7 "
                                        "*{sector}* \u00B7 "
                                        "rated `{rating}`.\n\n"
                                        "Coupon "
                                        "{coupon_pct:number:3}%, "
                                        "matures **{maturity}** "
                                        "({years_to_maturity:number:1}y). "
                                        "Current OAS spread "
                                        "**{spread_bp:number:0} bp** "
                                        "over the UST curve.")},
                                  {"type": "chart",
                                    "title": ("Price history "
                                                "(180 biz days)"),
                                    "chart_type": "line",
                                    "dataset": "bond_hist",
                                    "row_key": "cusip",
                                    "filter_field": "cusip",
                                    "mapping": {"x": "date",
                                                  "y": "price",
                                                  "y_title": "Clean price"},
                                    "height": 220},
                                  {"type": "chart",
                                    "title": "OAS spread history (bp)",
                                    "chart_type": "line",
                                    "dataset": "bond_hist",
                                    "row_key": "cusip",
                                    "filter_field": "cusip",
                                    "mapping": {"x": "date",
                                                  "y": "spread_bp",
                                                  "y_title": "Spread (bp)"},
                                    "height": 200},
                                  {"type": "table",
                                    "title": "Recent events",
                                    "dataset": "bond_events",
                                    "row_key": "issuer",
                                    "filter_field": "issuer",
                                    "max_rows": 6,
                                    "columns": [
                                        {"field": "date",
                                          "label": "Date"},
                                        {"field": "event",
                                          "label": "Event"},
                                        {"field": "reaction",
                                          "label": "Spread reaction"},
                                    ]},
                              ],
                          },
                      }},
                ],
            ]},
        ]},
        "links": [],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1600, height=1700)
    return _result(r, thumb)


# =============================================================================
# DEMO: bond_carry_roll  (chart click_popup -- click a scatter point for
#                          per-bond detail)
# =============================================================================
#
# Stress-tests the chart `click_popup` feature: a carry / roll scatter
# across the IG+HY bond universe where every point is interactive.
# Clicking a point opens a per-bond modal with stats, an issuer blurb,
# spread + price history charts filtered to that CUSIP, and a recent-
# events sub-table filtered to that issuer. Same modal grammar as
# `row_click`, applied to chart points.
#
# Tab 1 -- Carry & roll: scatter (rich popup) + bar of top combined
#          carry/roll names (simple popup with a few key stats).
# Tab 2 -- Sector view: avg-carry-by-sector bar (sector summary popup)
#          + sector weights donut + bond universe table for context.


def _pull_bond_carry_roll() -> pd.DataFrame:
    """Adds toy carry_bp / roll_bp / total_bp / financing_bp columns
    onto the main bond table. The numbers are deliberately illustrative
    (carry tracks rating, roll tracks duration) rather than market-
    accurate; the demo's purpose is the click interaction, not the
    valuation methodology."""
    main = _pull_bond_main()
    rng = random.Random(SEED + 700)
    financing_pct = 4.20
    carry_bp, roll_bp = [], []
    for _, row in main.iterrows():
        c = (row["ytm_pct"] - financing_pct) * 100 + rng.uniform(-8, 8)
        d = row["duration_yrs"]
        spread_factor = max(0.4, min(2.5, row["spread_bp"] / 120))
        r = (15 + d * 4.5 + (spread_factor - 1) * 18
              + rng.uniform(-6, 6))
        carry_bp.append(round(c, 1))
        roll_bp.append(round(r, 1))
    main["carry_bp"] = carry_bp
    main["roll_bp"] = roll_bp
    main["total_bp"] = [round(c + r, 1)
                          for c, r in zip(carry_bp, roll_bp)]
    main["financing_bp"] = round(financing_pct * 100, 1)
    return main


def _pull_bond_sector_summary(carry_roll_df: pd.DataFrame) -> pd.DataFrame:
    """One row per sector with average carry/roll/total and headline-
    line counts -- powers Tab 2 click popups (sector-level summary
    instead of bond-level)."""
    grouped = (carry_roll_df.groupby("sector")
                .agg(avg_carry_bp=("carry_bp", "mean"),
                       avg_roll_bp=("roll_bp", "mean"),
                       avg_total_bp=("total_bp", "mean"),
                       avg_duration=("duration_yrs", "mean"),
                       avg_spread_bp=("spread_bp", "mean"),
                       avg_ytm_pct=("ytm_pct", "mean"),
                       n_bonds=("cusip", "count"))
                .reset_index())
    for c in ("avg_carry_bp", "avg_roll_bp", "avg_total_bp",
                "avg_spread_bp"):
        grouped[c] = grouped[c].round(1)
    for c in ("avg_duration", "avg_ytm_pct"):
        grouped[c] = grouped[c].round(2)
    return grouped


def build_bond_carry_roll(out_dir: Path) -> Dict[str, Any]:
    """Carry / roll scatter dashboard. The main demo for chart
    click_popup."""
    bonds = _pull_bond_carry_roll()
    sectors = _pull_bond_sector_summary(bonds)
    hist = _pull_bond_price_history()
    blurbs = _pull_bond_issuer_blurbs()
    events = _pull_bond_recent_events()

    main_with_blurb = bonds.merge(blurbs, on="issuer", how="left")
    top_total = (bonds.sort_values("total_bp", ascending=False)
                  .head(10).copy())

    manifest = {
        "schema_version": 1,
        "id": "bond_carry_roll",
        "title": "Bond carry & roll screen",
        "description": ("Click any point on the scatter to see the "
                         "bond's full profile -- demoing chart "
                         "click_popup."),
        "theme": "gs_clean", "palette": "gs_primary",
        "metadata": {
            "data_as_of": "2026-04-22T20:00:00Z",
            "generated_at": "2026-04-22T21:00:00Z",
            "sources": ["GS Market Data (synthetic)"],
            "summary": {
                "title": "How to read this screen",
                "body": (
                    "Each point is a corporate bond plotted by **carry** "
                    "(YTM minus 1M financing, in bp) versus **roll** "
                    "(rolldown along the curve, in bp). Names in the "
                    "**upper-right quadrant** are the highest combined "
                    "carry+roll trades; names in the **lower-left** are "
                    "the cheapest legs to fund.\n\n"
                    "**Click any point** to open a modal with that "
                    "bond's stats, issuer blurb, recent spread + price "
                    "history, and event log. The same interaction is "
                    "wired on the bar charts in Tabs 1 and 2."),
            },
            "methodology": (
                "## Definitions\n\n"
                "* **Carry** = `(YTM - 1M financing rate) * 100`, in bp\n"
                "* **Roll** = approximated rolldown gain along the curve "
                "based on duration and current spread\n"
                "* **Total** = carry + roll, the headline 1-year "
                "expected ex-mark-to-market return in bp\n\n"
                "## Universe\n\n"
                "20 corporate bonds spanning IG and HY, deliberately "
                "selected to span sectors (Tech, Financials, Energy, "
                "Consumer, Healthcare, Utilities, Media, REIT)."),
        },

        # Datasets carry per-column provenance so every click popup
        # (explicit OR auto-default) gets a Sources footer for free.
        # For one bond (Tesla) we override a couple of cells to show
        # how `row_provenance` swaps the system/source per row -- in
        # production this is the pattern when an entity-keyed table
        # mixes vendors (one bond from market_data, another from
        # Bloomberg, a third from a static CSV).
        "datasets": {
            "bonds": {
                "source": main_with_blurb,
                "field_provenance": _bond_main_field_provenance(),
                "row_provenance_field": "cusip",
                "row_provenance": {
                    "TSLA-2030": {
                        "price":     {"system": "bloomberg",
                                       "symbol": "TSLA 5.000 6/15/30 Corp",
                                       "bloomberg_ticker": "TSLA 5 30",
                                       "source_label": "Bloomberg"},
                        "ytm_pct":   {"system": "bloomberg",
                                       "symbol": "TSLA 5.000 6/15/30 Corp YTM",
                                       "source_label": "Bloomberg"},
                        "spread_bp": {"system": "bloomberg",
                                       "symbol": "TSLA 5.000 6/15/30 Corp OAS",
                                       "source_label": "Bloomberg"},
                    },
                },
            },
            "sectors": {
                "source": sectors,
                "field_provenance": {
                    "sector": {"system": "csv",
                                "symbol": "bond_master:sector",
                                "source_label": "GS Bond Reference Master",
                                "display_name": "Sector"},
                    "avg_carry_bp": {"system": "computed",
                                       "recipe": "mean(carry_bp) by sector",
                                       "computed_from": ["bonds.carry_bp"],
                                       "display_name": "Avg carry",
                                       "units": "bp"},
                    "avg_roll_bp":  {"system": "computed",
                                       "recipe": "mean(roll_bp) by sector",
                                       "computed_from": ["bonds.roll_bp"],
                                       "display_name": "Avg roll",
                                       "units": "bp"},
                    "avg_total_bp": {"system": "computed",
                                       "recipe": "avg_carry_bp + avg_roll_bp",
                                       "computed_from":
                                           ["sectors.avg_carry_bp",
                                            "sectors.avg_roll_bp"],
                                       "display_name": "Avg total",
                                       "units": "bp"},
                    "avg_duration": {"system": "computed",
                                       "recipe": "mean(duration_yrs) by sector",
                                       "computed_from":
                                           ["bonds.duration_yrs"],
                                       "display_name": "Avg duration",
                                       "units": "years"},
                    "avg_spread_bp": {"system": "computed",
                                        "recipe": "mean(spread_bp) by sector",
                                        "computed_from": ["bonds.spread_bp"],
                                        "display_name": "Avg OAS",
                                        "units": "bp"},
                    "avg_ytm_pct":  {"system": "computed",
                                       "recipe": "mean(ytm_pct) by sector",
                                       "computed_from": ["bonds.ytm_pct"],
                                       "display_name": "Avg YTM",
                                       "units": "percent"},
                    "n_bonds":      {"system": "computed",
                                       "recipe": "count(cusip) by sector",
                                       "computed_from": ["bonds.cusip"],
                                       "display_name": "Bonds in sector"},
                },
            },
            "top_total": {
                "source": top_total,
                "field_provenance": _bond_main_field_provenance(),
            },
            "bond_hist": {
                "source": hist,
                "field_provenance": _bond_hist_field_provenance(),
            },
            "bond_events": {
                "source": events,
                "field_provenance": {
                    "date":     {"system": "csv",
                                  "symbol": "bond_events:date",
                                  "source_label": "GS Research event log"},
                    "issuer":   {"system": "csv",
                                  "symbol": "bond_master:issuer",
                                  "source_label":
                                      "GS Bond Reference Master"},
                    "event":    {"system": "csv",
                                  "symbol": "bond_events:event",
                                  "source_label":
                                      "GS Research event log"},
                    "reaction": {"system": "csv",
                                  "symbol": "bond_events:reaction",
                                  "source_label":
                                      "GS Research event log"},
                },
            },
        },

        "filters": [
            {"id": "rating_grade", "type": "radio", "default": "All",
              "options": ["All", "IG", "HY"],
              "all_value": "All",
              "label": "Rating grade",
              "field": "rating",
              "scope": "global",
              "targets": ["scatter_carry_roll"],
              "description": ("All shows everything; IG keeps "
                                "investment-grade ratings (BBB- and "
                                "above); HY keeps speculative-grade "
                                "(BB+ and below)."),
              "popup": {"title": "Rating grade filter",
                          "body": ("This filter is a placeholder for the "
                                    "demo -- the radio is wired to the "
                                    "scatter only. In a production build "
                                    "you'd target every widget that reads "
                                    "from the bond universe.")}},
        ],

        "layout": {"kind": "tabs", "cols": 12, "tabs": [
            # --- Tab 1: scatter + bar of top names -----------------------
            {"id": "carry_roll", "label": "Carry & roll",
              "description": ("Scatter every bond by carry (x) and roll "
                                "(y); click any point for the bond "
                                "profile."),
              "rows": [
                  [{"widget": "note", "id": "n_thesis", "w": 12,
                     "kind": "thesis", "title": "Where to look",
                     "body": (
                         "The **scatter is the primary chart** -- carry "
                         "on x, roll on y, colored by sector. Bonds "
                         "drift upper-right as combined return rises.\n\n"
                         "1. **Tech / Healthcare** anchor the IG cluster "
                         "in the lower-left -- low carry, low roll.\n"
                         "2. **Financials** drift north on duration\n"
                         "3. **Consumer HY (Tesla, Netflix)** sits in the "
                         "upper-right with the highest combined "
                         "carry+roll -- earn the most, but *click them* "
                         "to see why.")}],
                  [{"widget": "chart", "id": "scatter_carry_roll", "w": 8,
                     "h_px": 480,
                     "title": "Carry vs roll, by sector",
                     "subtitle": ("Click any point to open the bond's "
                                    "profile."),
                     "footer": ("Total return = carry + roll, ignoring "
                                 "MTM. Synthetic illustrative data."),
                     "spec": {
                         "chart_type": "scatter",
                         "dataset": "bonds",
                         "mapping": {"x": "carry_bp", "y": "roll_bp",
                                       "color": "sector",
                                       "x_title": "Carry (bp)",
                                       "y_title": "Roll (bp)"},
                         "annotations": [
                             {"type": "vline", "x": 100,
                               "label": "100bp carry", "style": "dashed",
                               "color": "#999"},
                             {"type": "hline", "y": 30,
                               "label": "30bp roll", "style": "dashed",
                               "color": "#999"},
                         ],
                     },
                     "click_popup": {
                         "title_field": "issuer",
                         "subtitle_template": (
                             "CUSIP {cusip} \u00B7 {sector} \u00B7 "
                             "{coupon_pct:number:2}% coupon \u00B7 "
                             "matures {maturity}"),
                         "detail": {
                             "wide": True,
                             "sections": [
                                 {"type": "stats",
                                   "fields": [
                                       {"field": "carry_bp",
                                         "label": "Carry",
                                         "format": "number:1",
                                         "suffix": " bp",
                                         "signed_color": True},
                                       {"field": "roll_bp",
                                         "label": "Roll",
                                         "format": "number:1",
                                         "suffix": " bp",
                                         "signed_color": True},
                                       {"field": "total_bp",
                                         "label": "Total",
                                         "format": "number:1",
                                         "suffix": " bp",
                                         "signed_color": True},
                                       {"field": "ytm_pct",
                                         "label": "YTM",
                                         "format": "number:2",
                                         "suffix": "%"},
                                       {"field": "duration_yrs",
                                         "label": "Duration",
                                         "format": "number:2",
                                         "suffix": " yrs"},
                                       {"field": "spread_bp",
                                         "label": "OAS",
                                         "format": "number:0",
                                         "suffix": " bp"},
                                       {"field": "rating",
                                         "label": "Rating"},
                                   ]},
                                 {"type": "markdown",
                                   "template": (
                                       "**{issuer}** \u00B7 *{sector}* "
                                       "\u00B7 rated `{rating}`.\n\n"
                                       "{blurb}\n\n"
                                       "Coupon {coupon_pct:number:3}%, "
                                       "matures **{maturity}** "
                                       "({years_to_maturity:number:1}y). "
                                       "OAS spread "
                                       "**{spread_bp:number:0} bp** vs "
                                       "the UST curve.")},
                                 {"type": "chart",
                                   "title": ("OAS spread history "
                                               "(180 biz days)"),
                                   "chart_type": "line",
                                   "dataset": "bond_hist",
                                   "row_key": "cusip",
                                   "filter_field": "cusip",
                                   "mapping": {"x": "date",
                                                 "y": "spread_bp",
                                                 "y_title": "Spread (bp)"},
                                   "height": 220},
                                 {"type": "chart",
                                   "title": ("Clean price history "
                                               "(180 biz days)"),
                                   "chart_type": "line",
                                   "dataset": "bond_hist",
                                   "row_key": "cusip",
                                   "filter_field": "cusip",
                                   "mapping": {"x": "date",
                                                 "y": "price",
                                                 "y_title": ("Clean "
                                                              "price")},
                                   "height": 200},
                                 {"type": "table",
                                   "title": "Recent events",
                                   "dataset": "bond_events",
                                   "row_key": "issuer",
                                   "filter_field": "issuer",
                                   "max_rows": 6,
                                   "columns": [
                                       {"field": "date", "label": "Date"},
                                       {"field": "event",
                                         "label": "Event"},
                                       {"field": "reaction",
                                         "label": ("Spread "
                                                    "reaction")},
                                   ]},
                             ],
                         },
                     }},
                    {"widget": "chart", "id": "bar_top_total", "w": 4,
                     "h_px": 480,
                     "title": "Top 10 by carry + roll",
                     "subtitle": ("Same data, different view. Click a "
                                    "bar for a quick stat sheet."),
                     "spec": {
                         "chart_type": "bar_horizontal",
                         "dataset": "top_total",
                         "mapping": {"x": "total_bp", "y": "issuer",
                                       "x_title": ("Carry + roll "
                                                    "(bp)")},
                     },
                     "click_popup": {
                         "title_field": "issuer",
                         "subtitle_template": (
                             "{sector} \u00B7 {rating} \u00B7 matures "
                             "{maturity}"),
                         "popup_fields": [
                             {"field": "total_bp", "label": "Total",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "carry_bp", "label": "Carry",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "roll_bp", "label": "Roll",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "ytm_pct", "label": "YTM",
                               "format": "number:2", "suffix": "%"},
                             {"field": "duration_yrs",
                               "label": "Duration",
                               "format": "number:2", "suffix": " yrs"},
                             {"field": "spread_bp", "label": "OAS",
                               "format": "number:0", "suffix": " bp"},
                         ]}},
                  ]]},
            # --- Tab 2: sector view + universe table --------------------
            {"id": "sectors", "label": "Sector view",
              "description": ("Same universe, aggregated by sector "
                                "(click bars or pie slices for the "
                                "sector summary)."),
              "rows": [
                  [{"widget": "chart", "id": "bar_sector_avg", "w": 8,
                     "h_px": 360,
                     "title": "Average carry + roll, by sector",
                     "subtitle": "Click a bar for the sector summary.",
                     "spec": {
                         "chart_type": "bar",
                         "dataset": "sectors",
                         "mapping": {"x": "sector", "y": "avg_total_bp",
                                       "y_title": ("Avg carry + roll "
                                                    "(bp)")},
                     },
                     "click_popup": {
                         "title_field": "sector",
                         "subtitle_template": (
                             "{n_bonds:integer} bonds \u00B7 avg "
                             "duration {avg_duration:number:1}y"),
                         "popup_fields": [
                             {"field": "avg_total_bp",
                               "label": "Avg total",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "avg_carry_bp",
                               "label": "Avg carry",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "avg_roll_bp",
                               "label": "Avg roll",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "avg_ytm_pct",
                               "label": "Avg YTM",
                               "format": "number:2", "suffix": "%"},
                             {"field": "avg_spread_bp",
                               "label": "Avg OAS",
                               "format": "number:0", "suffix": " bp"},
                             {"field": "n_bonds",
                               "label": "Bond count",
                               "format": "integer"},
                         ]}},
                    {"widget": "chart", "id": "pie_sector_count", "w": 4,
                     "h_px": 360,
                     "title": "Sector weight (bond count)",
                     "subtitle": ("Click a slice for the same sector "
                                    "summary."),
                     "spec": {
                         "chart_type": "donut",
                         "dataset": "sectors",
                         "mapping": {"category": "sector",
                                       "value": "n_bonds"},
                     },
                     "click_popup": {
                         "title_field": "sector",
                         "popup_fields": [
                             {"field": "n_bonds",
                               "label": "Bond count",
                               "format": "integer"},
                             {"field": "avg_total_bp",
                               "label": "Avg total",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "avg_duration",
                               "label": "Avg duration",
                               "format": "number:2",
                               "suffix": " yrs"},
                         ]}},
                  ],
                  [{"widget": "table", "id": "tbl_universe", "w": 12,
                     "title": "Full universe",
                     "subtitle": ("Same dataset as the scatter; "
                                    "click a row for the full profile "
                                    "(matches the scatter popup)."),
                     "dataset_ref": "bonds",
                     "max_rows": 50,
                     "row_height": "compact",
                     "searchable": True, "sortable": True,
                     "columns": [
                         {"field": "issuer", "label": "Issuer",
                           "align": "left"},
                         {"field": "sector", "label": "Sector",
                           "align": "left"},
                         {"field": "rating", "label": "Rating"},
                         {"field": "carry_bp", "label": "Carry (bp)",
                           "format": "number:1"},
                         {"field": "roll_bp", "label": "Roll (bp)",
                           "format": "number:1"},
                         {"field": "total_bp", "label": "Total (bp)",
                           "format": "number:1"},
                         {"field": "ytm_pct", "label": "YTM (%)",
                           "format": "number:2"},
                         {"field": "duration_yrs",
                           "label": "Duration",
                           "format": "number:2"},
                         {"field": "spread_bp", "label": "OAS (bp)",
                           "format": "number:0"},
                     ],
                     "row_click": {
                         "title_field": "issuer",
                         "subtitle_template": (
                             "CUSIP {cusip} \u00B7 {sector} \u00B7 "
                             "{coupon_pct:number:2}% coupon"),
                         "popup_fields": [
                             {"field": "carry_bp", "label": "Carry",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "roll_bp", "label": "Roll",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "total_bp", "label": "Total",
                               "format": "number:1", "suffix": " bp"},
                             {"field": "ytm_pct", "label": "YTM",
                               "format": "number:2", "suffix": "%"},
                             {"field": "spread_bp", "label": "OAS",
                               "format": "number:0", "suffix": " bp"},
                             {"field": "duration_yrs",
                               "label": "Duration",
                               "format": "number:2",
                               "suffix": " yrs"},
                             {"field": "rating", "label": "Rating"},
                         ]}}],
              ]},
        ]},
        "links": [],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1600, height=1500)
    return _result(r, thumb)


# =============================================================================
# DEMO: news_wrap  (text-heavy: headlines table + thematic notes + summary)
# =============================================================================
#
# Stress-tests the prose surface area of the dashboard system. Built
# entirely around the new note widget + summary banner + extended
# markdown grammar (ordered lists, blockquotes, tables in markdown,
# strikethrough). No charts in the headline area; PRISM is the
# narrator and the dashboard is the page.


def pull_news_headlines() -> pd.DataFrame:
    """Synthetic intraday news desk: 30 headlines with timestamp,
    source, asset class, sentiment, impact rating (1-5), tags, and
    a markdown body for drill-down."""
    rng = random.Random(SEED + 11)
    sources = ["Bloomberg", "Reuters", "FT", "WSJ",
                "GS Research", "DJ Newswires", "MNI", "BBG TOP"]
    classes = ["Rates", "Equity", "FX", "Commodity",
                "Credit", "Macro", "Policy"]
    sentiments = ["bullish", "bearish", "neutral"]
    base_dt = pd.Timestamp("2026-04-24 09:30:00")
    rows = []
    headlines = [
        ("Front-end UST richens 6bp on softer payrolls",
          "Rates", "bullish", 5,
          ["UST", "front-end", "NFP"],
          "Two-year yields **fell ~6bp** to 4.32% intraday after a "
          "weaker-than-expected NFP print (180k vs 210k consensus). "
          "Real-money buyers re-engaged at the front end, and dealer "
          "books saw a notable lift in 2Y/3Y demand.\n\n"
          "1. NFP 180k vs 210k consensus\n"
          "2. Unemployment rate held at 3.9%\n"
          "3. Average hourly earnings 0.2% m/m\n\n"
          "> The rally extends a multi-week bull-steepener; 2s10s "
          "is back in positive territory for the first time in "
          "three weeks."),
        ("ECB's Lagarde: 'Disinflation broadly on track'",
          "Policy", "bullish", 4,
          ["ECB", "Lagarde", "inflation"],
          "ECB President Lagarde said disinflation in the euro area "
          "is **broadly on track** but warned that services prices "
          "remain sticky. Markets pared back bets on a faster cutting "
          "cycle, with EUR OIS pricing now implying ~70bp of cuts "
          "by year-end vs ~85bp pre-speech.\n\n"
          "> 'We are confident inflation is heading to target, but "
          "the last mile is the hardest.' -- Lagarde, press conf"),
        ("WTI -2.1% as inventory build surprises",
          "Commodity", "bearish", 3,
          ["oil", "WTI", "inventories"],
          "EIA reported a +5.4mb crude build vs -1.0mb consensus. "
          "WTI front-month traded below $78 for the first time "
          "in two weeks. Refining margins narrowed on the print.\n\n"
          "Bias: ~~tight~~ amply supplied near-term; OPEC+ meeting "
          "on May 8 remains the next catalyst."),
        ("Equity vol bid: VIX +1.8 vols ahead of CPI",
          "Equity", "neutral", 3,
          ["VIX", "CPI", "vol"],
          "S&P front-month vol bid up 1.8 vols into tomorrow's "
          "core PCE print. SPX skew steepened modestly. Single-stock "
          "vol underperformed the index on dispersion bets."),
        ("Apple beats on services, Q3 guide light",
          "Equity", "neutral", 4,
          ["AAPL", "earnings", "services"],
          "Apple reported Q2 EPS $1.55 vs $1.50 consensus. Services "
          "revenue +14% y/y was the standout. Q3 guide light: "
          "iPhone units expected -5% y/y on weak China demand.\n\n"
          "1. Services rev: $24.2bn (+14% y/y)\n"
          "2. iPhone: $46.0bn (-2% y/y)\n"
          "3. Mac: $7.5bn (+4% y/y)\n"
          "4. China: $16.4bn (-8% y/y)"),
        ("Fed's Powell: 'No rush' to ease policy",
          "Policy", "bearish", 5,
          ["Fed", "Powell", "FOMC"],
          "Chair Powell, speaking at the Economic Club of New York, "
          "said the Fed is in **no rush** to ease policy and needs "
          "to see further evidence inflation is sustainably moving "
          "to 2%. Front-end softened ~3bp on the headline before "
          "recovering.\n\n"
          "> 'The strength of the economy and ongoing progress on "
          "inflation give us the ability to be patient.'"),
        ("EUR/USD breaks 1.10, lowest since November",
          "FX", "bearish", 4,
          ["EUR", "USD", "DXY"],
          "EUR/USD broke below 1.10 for the first time since "
          "November on the back of a hawkish Powell tape and weaker "
          "EU services PMI. DXY trades at 105.3, +0.5% on the day.\n\n"
          "Levels:\n\n"
          "| Level | Tech significance |\n"
          "|---|---|\n"
          "| 1.0950 | Q4 2025 swing low |\n"
          "| 1.0900 | psychological + 200dma |\n"
          "| 1.0850 | next major support |"),
        ("CDX IG -2bp on macro tailwind",
          "Credit", "bullish", 2,
          ["CDX", "IG", "credit"],
          "CDX IG tightened 2bp to 53bp, the lowest level in two "
          "weeks, on broad risk-on tone. HY also tightened 8bp to "
          "324bp. New-issue calendar is light through month-end."),
        ("BoJ leaves policy unchanged, hints at June review",
          "Policy", "neutral", 4,
          ["BoJ", "JPY", "policy"],
          "Bank of Japan held the policy rate at 0.10% as expected. "
          "Governor Ueda flagged a **likely** policy review in June. "
          "USD/JPY traded a 156.20-156.80 range on the announcement."),
        ("Tesla -3.5% pre-market on delivery cut",
          "Equity", "bearish", 3,
          ["TSLA", "deliveries"],
          "Tesla cut its Q2 delivery target by ~5% citing soft "
          "China demand and the Cybertruck production ramp. "
          "Sell-side reactions mixed; consensus PT range $180-$220."),
        ("China loan prime rate held at 3.45% / 3.95%",
          "Macro", "neutral", 2,
          ["China", "PBOC", "LPR"],
          "PBOC held both 1Y and 5Y LPRs unchanged. Market focus "
          "shifts to potential RRR cut in May."),
        ("Gold near record high on geopolitical premium",
          "Commodity", "bullish", 3,
          ["gold", "geopolitics"],
          "Spot gold traded near $2,420/oz, +1.1% intraday. ETF "
          "flows neutral, suggesting the bid is institutional / "
          "central-bank rather than retail."),
        ("US 5Y auction tails 0.4bp, BTC at 2.42x",
          "Rates", "bearish", 2,
          ["UST", "auction", "5Y"],
          "Today's $70bn 5Y auction stopped at 4.215%, 0.4bp tail. "
          "Bid-to-cover 2.42x (5-auction avg 2.45x). Indirect bid "
          "62% (avg 65%). Tepid demand; modest concession in 5Y "
          "afterwards."),
        ("Bitcoin breaks $70k, ETF inflows +$420mn",
          "Macro", "bullish", 2,
          ["BTC", "crypto", "ETF"],
          "Spot BTC ETFs saw $420mn of inflows yesterday, the "
          "largest daily inflow in two weeks. Spot price broke "
          "above $70k on Asia open."),
        ("EU services PMI 49.8 vs 51.2 expected",
          "Macro", "bearish", 4,
          ["EU", "PMI", "macro"],
          "Eurozone composite services PMI printed 49.8 vs 51.2 "
          "consensus, dipping back into contraction. Manufacturing "
          "PMI was firmer at 47.6 (vs 47.0 prior).\n\n"
          "Country detail:\n\n"
          "* Germany services 50.1 (-2.0pt)\n"
          "* France services 47.3 (-1.5pt)\n"
          "* Italy services 51.5 (+0.4pt)"),
        ("Saudi Arabia raises May OSP to Asia by 60c",
          "Commodity", "bullish", 2,
          ["oil", "Saudi", "OSP"],
          "Saudi Aramco raised its May Arab Light OSP to Asia "
          "by 60c to a $2.30 premium. Larger increase than market "
          "expected; supportive for crude term structure."),
        ("Chinese ADRs +2.4%; Alibaba leads",
          "Equity", "bullish", 2,
          ["China", "ADR", "BABA"],
          "Chinese ADRs rallied on rumors of further policy "
          "support measures. KWEB +2.8%, BABA +3.4%, JD +2.1%."),
        ("UK CPI 3.2% y/y vs 3.1% expected",
          "Macro", "bearish", 4,
          ["UK", "CPI", "BoE"],
          "UK headline CPI surprised to the upside at 3.2% y/y. "
          "Core CPI 4.2% y/y vs 4.1% expected. GBP rallied 50 "
          "pips; Gilt curve flattened on hawkish repricing."),
        ("S&P 500 +0.6%, NDX +0.9%; small-caps lag",
          "Equity", "bullish", 1,
          ["SPX", "NDX", "small-caps"],
          "Broader equities firm with tech leading. Russell 2000 "
          "underperformed (+0.1%) on rates sensitivity into PCE."),
        ("US 10Y trades range 4.10-4.18%",
          "Rates", "neutral", 1,
          ["UST", "10Y"],
          "Belly-of-curve consolidation pre-PCE. Range trade; "
          "no clear catalyst until tomorrow's print."),
        ("Yen weakness sparks intervention chatter",
          "FX", "neutral", 3,
          ["JPY", "intervention"],
          "USD/JPY pushing 156.80; Japanese officials reiterated "
          "they are 'watching FX moves carefully'. Market parsing "
          "language as one step short of formal warning."),
        ("Copper -0.8% on Chinese property data",
          "Commodity", "bearish", 2,
          ["copper", "China", "property"],
          "Copper weighed by soft China April property starts data. "
          "LME 3M -0.8% to $9,820/t; broader base metals firmer."),
        ("Schwab cuts 5-7Y UST recommendation",
          "Rates", "bearish", 2,
          ["UST", "Schwab", "research"],
          "Schwab fixed-income strategists downgraded 5-7Y UST "
          "to neutral from buy citing tactical positioning and "
          "richer valuations vs 10Y."),
        ("Goldman raises year-end SPX target to 5,800",
          "Equity", "bullish", 3,
          ["SPX", "GS", "research"],
          "Goldman strategists raised year-end S&P 500 target "
          "to 5,800 from 5,600 citing earnings resilience and "
          "easing financial conditions."),
        ("US new home sales 712k vs 670k expected",
          "Macro", "bullish", 2,
          ["housing", "new-home-sales"],
          "March new home sales surprised firmly at 712k saar. "
          "Median price +1.6% y/y to $429,800. Months of supply "
          "fell to 7.3 from 7.9."),
        ("Crude term structure flattens 2c",
          "Commodity", "neutral", 1,
          ["oil", "WTI", "term-structure"],
          "WTI Dec25/Dec26 spread flattened 2c to 38c backwardation. "
          "Front spreads firmer on inventory print noise."),
        ("Norges Bank dovish hold, NOK -0.4%",
          "FX", "bearish", 2,
          ["NOK", "Norges-Bank"],
          "Norges Bank held rates at 4.50% with dovish guidance. "
          "First cut signaled for September; NOK underperformed "
          "G10 peers."),
        ("Brent -1.5%, near 6-week low",
          "Commodity", "bearish", 2,
          ["Brent", "oil"],
          "Brent front-month near $82, 6-week low on inventory "
          "build + soft China demand signal."),
        ("Chair Powell speaks 1:00pm ET tomorrow",
          "Policy", "neutral", 4,
          ["Fed", "Powell", "calendar"],
          "Speech at Stanford Business School, topic: 'Monetary "
          "policy under uncertainty.' First public remarks since "
          "the FOMC press conference."),
        ("EM debt fund flows +$280mn last week",
          "Macro", "bullish", 1,
          ["EM", "flows"],
          "EPFR data shows EM debt funds saw $280mn of inflows "
          "last week, the eighth consecutive week of inflows."),
    ]
    for hh, asset_class, sent, impact, tags, body in headlines:
        ts = base_dt + pd.Timedelta(minutes=rng.randint(0, 360))
        rows.append({
            "ts": ts.strftime("%H:%M"),
            "headline": hh,
            "source": rng.choice(sources),
            "asset_class": asset_class,
            "sentiment": sent,
            "impact": impact,
            "tags": ", ".join(tags),
            "body": body,
        })
    df = pd.DataFrame(rows)
    return df.sort_values("impact", ascending=False).reset_index(drop=True)


def pull_news_sparklines() -> pd.DataFrame:
    """Tiny intraday tape for sparkline tiles -- one row per minute,
    one column per asset class proxy."""
    rng = random.Random(SEED + 12)
    n = 60
    base_ts = pd.Timestamp("2026-04-24 09:30:00")
    out = []
    spx = 5710.0; ust10 = 4.13; dxy = 105.30; wti = 78.0
    for i in range(n):
        spx *= 1 + rng.gauss(0.00015, 0.0008)
        ust10 += rng.gauss(0, 0.008)
        dxy *= 1 + rng.gauss(0, 0.0006)
        wti *= 1 + rng.gauss(-0.0003, 0.003)
        out.append({
            "ts": (base_ts + pd.Timedelta(minutes=i)).strftime("%H:%M"),
            "spx": round(spx, 2),
            "ust10": round(ust10, 4),
            "dxy": round(dxy, 3),
            "wti": round(wti, 2),
        })
    return pd.DataFrame(out)


def build_news_wrap(out_dir: Path) -> Dict[str, Any]:
    """News-desk dashboard: headlines table + thematic notes + per-
    asset commentary + reading list. Stress-tests the prose surfaces:
    summary banner, semantic note widgets across all six kinds, full
    markdown grammar in widget bodies + drill-down sections, and a
    rich row-click drilldown that surfaces the markdown body of each
    headline in a modal."""
    df_hl = pull_news_headlines()
    df_tape = pull_news_sparklines()

    manifest = {
        "schema_version": 1,
        "id": "news_wrap",
        "title": "News desk -- intraday market wrap",
        "description": ("Headline-driven dashboard: top of book, "
                         "themed commentary, sortable headlines table "
                         "with full-body drill-down, per-asset "
                         "callouts, reading list. Demonstrates the "
                         "text-heavy / prose-heavy dashboard pattern."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "data_as_of": "2026-04-24T16:00:00Z",
            "generated_at": "2026-04-24T16:05:00Z",
            "sources": ["Bloomberg", "Reuters", "FT", "WSJ",
                         "GS Research", "MNI"],
            "tags": ["news", "headlines", "wrap"],
            "summary": {
                "title": "Today's read",
                "body": (
                    "**Soft-data day** dominated by a weaker NFP "
                    "print and a market-friendly Lagarde tape. The "
                    "front-end of the UST curve led the rally and "
                    "the curve **bull-steepened**; FX is the cleanest "
                    "expression of the divergence between dovish ECB "
                    "comments and a still-firm DXY.\n\n"
                    "1. **Rates**: 2Y -6bp; 2s10s back positive\n"
                    "2. **FX**: EUR/USD broke 1.10 -- watch 1.0950\n"
                    "3. **Equity**: bid into PCE; vol up 1.8 vols\n"
                    "4. **Commodity**: WTI -2.1% on inventory build\n\n"
                    "> All eyes on tomorrow's core PCE print (consensus "
                    "0.2% m/m / 2.7% y/y). A clean miss likely extends "
                    "the front-end rally; an upside surprise risks a "
                    "hawkish re-flattening into a long book."
                ),
            },
            "methodology": (
                "## Sources\n\n"
                "Synthetic feed; production version pulls from the GS "
                "Research news API + curated wire feeds (Bloomberg, "
                "Reuters, FT, WSJ, MNI, DJ).\n\n"
                "## Impact rating\n\n"
                "1-5 scale set by the desk:\n\n"
                "1. Information only / no market reaction\n"
                "2. Sector-level / single-asset move\n"
                "3. Multi-asset reaction\n"
                "4. Macro driver / cross-asset reaction\n"
                "5. Regime / week-defining event\n\n"
                "## Refresh\n\n"
                "Continuous during US cash session; this dashboard "
                "snapshot was taken at 4:00pm ET."
            ),
        },
        "datasets": {
            "headlines": df_hl,
            "tape": df_tape,
        },
        "filters": [
            {"id": "asset_f", "type": "multiSelect",
              "default": ["Rates", "Equity", "FX", "Commodity",
                           "Credit", "Macro", "Policy"],
              "options": ["Rates", "Equity", "FX", "Commodity",
                           "Credit", "Macro", "Policy"],
              "field": "asset_class", "label": "Asset class",
              "targets": ["headlines_table"]},
            {"id": "sent_f", "type": "radio", "default": "All",
              "all_value": "All",
              "options": ["All", "bullish", "bearish", "neutral"],
              "field": "sentiment", "label": "Sentiment",
              "targets": ["headlines_table"]},
            {"id": "impact_f", "type": "slider", "default": 1,
              "min": 1, "max": 5, "step": 1,
              "field": "impact", "op": ">=",
              "label": "Impact >=", "targets": ["headlines_table"]},
            {"id": "search_f", "type": "text", "default": "",
              "field": "headline", "op": "contains",
              "label": "Headline contains",
              "placeholder": "e.g. CPI, Powell, oil",
              "targets": ["headlines_table"]},
        ],
        "layout": {"kind": "grid", "rows": [
            [
                {"widget": "note", "id": "n_thesis", "w": 6,
                  "kind": "thesis",
                  "title": "Bull-steepener resumes on soft NFP",
                  "body": (
                      "The **2Y led the rally** with -6bp on a "
                      "180k NFP print (vs 210k consensus). 5s30s "
                      "flatter on long-end demand into the 7Y "
                      "auction. 2s10s widening primarily front-led, "
                      "consistent with a *priced-in cut* trade.\n\n"
                      "1. NFP: 180k vs 210k (miss)\n"
                      "2. Unemployment: 3.9% (in line)\n"
                      "3. AHE: 0.2% m/m (in line)")},
                {"widget": "note", "id": "n_watch", "w": 6,
                  "kind": "watch",
                  "title": "Levels into PCE",
                  "body": (
                      "Core PCE consensus 0.2% m/m / 2.7% y/y at "
                      "8:30am ET tomorrow.\n\n"
                      "| Asset | Level | If broken |\n"
                      "|---|---|---|\n"
                      "| 10Y UST | 4.10% | 4.00% pivot |\n"
                      "| EUR/USD | 1.0950 | 1.0900 200dma |\n"
                      "| 2s10s | +20bp | momentum confirm |\n"
                      "| SPX | 5,725 | range break to 5,750 |")},
            ],
            [
                {"widget": "note", "id": "n_risk", "w": 6,
                  "kind": "risk",
                  "title": "Hawkish PCE tail",
                  "body": (
                      "A hot core PCE (>0.3% m/m) reverses the "
                      "front-end rally and puts 2Y back through "
                      "4.40%. Pain trade is a *hawkish "
                      "re-flattening* into a long book that has "
                      "been adding duration on the cuts narrative.\n\n"
                      "Adjacent risk: Powell speaks 1pm ET. First "
                      "remarks since the press conference; the bar "
                      "for fresh dovishness is high.")},
                {"widget": "note", "id": "n_context", "w": 6,
                  "kind": "context",
                  "title": "Positioning backdrop",
                  "body": (
                      "Positioning into PCE is **light** vs the 5Y "
                      "average. CFTC futures show specs net short "
                      "~140k 10Y contracts (-0.5z); real-money long "
                      "base from Q1 has largely been monetized.\n\n"
                      "> A hawkish surprise has less stop-out risk "
                      "than it did six weeks ago.")},
            ],
            [
                {"widget": "note", "id": "n_fact", "w": 12,
                  "kind": "fact",
                  "title": "By the numbers",
                  "body": (
                      "End-of-day cash settles, GS Market Data:\n\n"
                      "| | Level | 1d | 1w | YTD |\n"
                      "|---|---:|---:|---:|---:|\n"
                      "| SPX | 5,742 | +0.6% | +1.4% | +14.2% |\n"
                      "| NDX | 18,310 | +0.9% | +2.1% | +9.8% |\n"
                      "| US 2Y | 4.32% | -6bp | -18bp | -41bp |\n"
                      "| US 10Y | 4.13% | -3bp | -9bp | -22bp |\n"
                      "| 2s10s | +20bp | +3bp | +9bp | +19bp |\n"
                      "| EUR/USD | 1.0982 | -0.5% | -0.9% | -2.4% |\n"
                      "| WTI | $78.10 | -2.1% | -3.4% | +9.1% |\n"
                      "| Gold | $2,418 | +1.1% | +2.6% | +17.0% |\n"
                      "| BTC | $70,420 | +2.4% | +5.1% | +66% |")},
            ],
            [
                {"widget": "table", "id": "headlines_table", "w": 12,
                  "dataset_ref": "headlines",
                  "title": "Headlines (sorted by impact)",
                  "info": ("Click any row to read the full body. "
                           "Filter by asset class, sentiment, or "
                           "impact threshold via the controls above."),
                  "searchable": True, "sortable": True,
                  "downloadable": True,
                  "max_rows": 30, "row_height": "compact",
                  "columns": [
                      {"field": "ts", "label": "Time", "align": "left"},
                      {"field": "headline", "label": "Headline",
                        "align": "left",
                        "tooltip": "Click row for full body"},
                      {"field": "source", "label": "Source",
                        "align": "left"},
                      {"field": "asset_class", "label": "Class",
                        "align": "left"},
                      {"field": "sentiment", "label": "Sentiment",
                        "align": "center",
                        "conditional": [
                            {"op": "==", "value": "bullish",
                              "background": "#c6f6d5", "color": "#22543d"},
                            {"op": "==", "value": "bearish",
                              "background": "#fed7d7", "color": "#742a2a"},
                            {"op": "==", "value": "neutral",
                              "background": "#edf2f7", "color": "#4a5568"},
                        ]},
                      {"field": "impact", "label": "Impact",
                        "align": "center", "format": "integer",
                        "color_scale": {"min": 1, "max": 5,
                                          "palette": "gs_blues"}},
                      {"field": "tags", "label": "Tags", "align": "left"},
                  ],
                  "row_highlight": [
                      {"field": "impact", "op": ">=", "value": 5,
                        "class": "info"},
                      {"field": "sentiment", "op": "==",
                        "value": "bullish", "class": "pos"},
                      {"field": "sentiment", "op": "==",
                        "value": "bearish", "class": "neg"},
                  ],
                  "row_click": {
                      "title_field": "headline",
                      "subtitle_template": (
                          "{ts} ET . {source} . {asset_class} . "
                          "impact {impact}/5"
                      ),
                      "detail": {
                          "wide": True,
                          "sections": [
                              {"type": "stats",
                                "fields": [
                                    {"field": "asset_class",
                                      "label": "Asset class"},
                                    {"field": "sentiment",
                                      "label": "Sentiment"},
                                    {"field": "impact",
                                      "label": "Impact",
                                      "format": "integer",
                                      "suffix": " / 5"},
                                    {"field": "source",
                                      "label": "Source"},
                                ]},
                              {"type": "markdown",
                                "title": "Full story",
                                "template": "{body}"},
                              {"type": "markdown",
                                "title": "Tags",
                                "template":
                                    "Filed under: `{tags}`."},
                          ],
                      },
                  }},
            ],
            [
                {"widget": "markdown", "id": "section_a",
                  "w": 12, "content": "## By asset class"},
            ],
            [
                {"widget": "note", "id": "n_rates", "w": 6,
                  "kind": "insight",
                  "title": "Rates",
                  "body": (
                      "Bull-steepener; 2Y led the rally on soft NFP. "
                      "Auction noise in 5Y modestly poor (0.4bp tail). "
                      "Real yields little changed; nominal-led move.\n\n"
                      "Headlines:\n\n"
                      "* Front-end UST richens 6bp on softer payrolls\n"
                      "* US 5Y auction tails 0.4bp\n"
                      "* Schwab cuts 5-7Y UST recommendation")},
                {"widget": "chart", "id": "tape_ust10", "w": 6, "h_px": 200,
                  "title": "10Y UST yield (today, intraday)",
                  "subtitle": "Range trade pre-PCE",
                  "spec": {
                      "chart_type": "line", "dataset": "tape",
                      "mapping": {"x": "ts", "y": "ust10",
                                    "y_title": "Yield (%)"}}},
            ],
            [
                {"widget": "note", "id": "n_eq", "w": 6,
                  "kind": "insight",
                  "title": "Equity",
                  "body": (
                      "Broader index firm into PCE; tech leadership "
                      "narrow. Vol bid up 1.8 vols on the day. "
                      "Earnings dispersion reasserting (AAPL services "
                      "beat, TSLA delivery cut).\n\n"
                      "Headlines:\n\n"
                      "* Equity vol bid: VIX +1.8 vols ahead of CPI\n"
                      "* Apple beats on services, Q3 guide light\n"
                      "* Goldman raises year-end SPX target to 5,800")},
                {"widget": "chart", "id": "tape_spx", "w": 6, "h_px": 200,
                  "title": "S&P 500 (today, intraday)",
                  "subtitle": "Drift higher into close",
                  "spec": {
                      "chart_type": "line", "dataset": "tape",
                      "mapping": {"x": "ts", "y": "spx",
                                    "y_title": "Index"}}},
            ],
            [
                {"widget": "note", "id": "n_fx", "w": 6,
                  "kind": "watch",
                  "title": "FX",
                  "body": (
                      "**EUR/USD broke 1.10**, lowest since November. "
                      "Lagarde tape pulled back EUR OIS cut bets. "
                      "JPY weakness past 156.80 sparking intervention "
                      "chatter.\n\n"
                      "1. EUR/USD: 1.10 break, eyes 1.0950\n"
                      "2. USD/JPY: 156.80, intervention zone\n"
                      "3. NOK underperformed G10 on dovish Norges hold")},
                {"widget": "chart", "id": "tape_dxy", "w": 6, "h_px": 200,
                  "title": "DXY (today, intraday)",
                  "subtitle": "Bid throughout the session",
                  "spec": {
                      "chart_type": "line", "dataset": "tape",
                      "mapping": {"x": "ts", "y": "dxy",
                                    "y_title": "Index"}}},
            ],
            [
                {"widget": "note", "id": "n_cmdy", "w": 6,
                  "kind": "risk",
                  "title": "Commodities",
                  "body": (
                      "Crude weighed by surprise inventory build "
                      "(+5.4mb vs -1.0mb). Gold near record on "
                      "geopolitical premium. Copper soft on China "
                      "property data.\n\n"
                      "> OPEC+ meeting May 8 remains the crude "
                      "catalyst. Algorithmic selling extended the "
                      "WTI move post-print.")},
                {"widget": "chart", "id": "tape_wti", "w": 6, "h_px": 200,
                  "title": "WTI (today, intraday)",
                  "subtitle": "Inventory print drove the move",
                  "spec": {
                      "chart_type": "line", "dataset": "tape",
                      "mapping": {"x": "ts", "y": "wti",
                                    "y_title": "$/bbl"}}},
            ],
            [
                {"widget": "markdown", "id": "section_b",
                  "w": 12, "content": "## Reading list"},
            ],
            [
                {"widget": "markdown", "id": "reading", "w": 12,
                  "content": (
                      "### Recommended\n\n"
                      "1. [GS Research: Front-end UST playbook into "
                      "PCE](https://example.com/gs/front-end-pce) "
                      "-- *thesis-level*; informs the bull-steepener "
                      "view above.\n"
                      "2. [Hilsenrath: Powell's 'no rush' framing"
                      "](https://example.com/wsj/hilsenrath-no-rush) "
                      "-- short read; useful colour on the FOMC "
                      "thinking.\n"
                      "3. [GS Research: ECB cuts repriced "
                      "lower](https://example.com/gs/ecb-cuts) -- "
                      "EUR FX tactical desk note.\n"
                      "4. [Bloomberg: Inside the BoJ June review"
                      "](https://example.com/bbg/boj-june) -- "
                      "background; positions are light, surprise "
                      "potential exists.\n"
                      "5. [FT Lex: Apple services premium"
                      "](https://example.com/ft/aapl-services) -- "
                      "single-name; relevant for tech earnings vol.\n\n"
                      "### Listening\n\n"
                      "* [Odd Lots: 'When does the front end stop "
                      "trading the cuts?'](https://example.com/oddlots) "
                      "-- 50min, recorded yesterday.\n"
                      "* [Macro Voices: 'Curve dynamics with "
                      "Burghardt'](https://example.com/mv-burghardt) "
                      "-- 1h, foundational on butterflies / spreads.\n\n"
                      "### Calendar (next 24h)\n\n"
                      "| Time (ET) | Event | Consensus |\n"
                      "|---|---|---|\n"
                      "| 8:30am | US Core PCE | 0.2% m/m / 2.7% y/y |\n"
                      "| 10:00am | UMich sentiment | 79.0 |\n"
                      "| 1:00pm | Powell speech | -- |\n"
                      "| 2:30pm | Fed Williams | -- |\n\n"
                      "> *Skip the 6pm BoE Pill speech; he is on "
                      "embargo until Friday.*")},
            ],
        ]},
        "links": [],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1400, height=2000)
    return _result(r, thumb)


# =============================================================================
# DEMO: fomc_brief  (Fed-document analysis: statement, minutes, speakers)
# =============================================================================
#
# Heavy on blockquotes (direct quotes from Fed officials), markdown
# tables (statement diff matrix), nested lists (themes inside topics),
# and note widgets (hawk/dove signals). Demonstrates how to build a
# document-centric dashboard where prose is the artifact, not
# decoration.


def pull_fed_speakers() -> pd.DataFrame:
    """Recent Fed speakers with hawkish-dovish rating (-2..+2) and
    a key quote. Synthetic but flavoured to reflect each FOMC voter's
    public bias."""
    rows = [
        ("2026-04-22", "Powell", "Chair", "neutral", 0,
          "FOMC press conference",
          "The strength of the economy and ongoing progress on "
          "inflation give us the ability to be patient."),
        ("2026-04-23", "Williams", "NY Fed", "neutral", 0,
          "Speech at Stanford",
          "We are well positioned to respond to the economy as it "
          "evolves. There is no rush to cut."),
        ("2026-04-22", "Bowman", "Governor", "hawk", 2,
          "OMFIF speech",
          "I see meaningful upside risks to inflation and would "
          "support holding policy steady for some time."),
        ("2026-04-21", "Waller", "Governor", "hawk", 1,
          "Hoover Institution",
          "The data continue to suggest that monetary policy "
          "should remain restrictive for longer."),
        ("2026-04-21", "Goolsbee", "Chicago", "dove", -1,
          "Yahoo Finance interview",
          "If we get a few more good inflation readings, I think "
          "we should be cutting."),
        ("2026-04-20", "Daly", "SF Fed", "neutral", 0,
          "FRBSF town hall",
          "Patience is the operative word. The risks are now "
          "two-sided."),
        ("2026-04-19", "Kashkari", "Minneapolis", "hawk", 1,
          "Town hall",
          "I'm not yet convinced inflation is on a sustainable "
          "path back to 2%."),
        ("2026-04-18", "Mester", "Cleveland", "hawk", 1,
          "Speech to NABE",
          "We need more data to be confident in cuts. Three rate "
          "cuts this year still seems reasonable."),
        ("2026-04-17", "Logan", "Dallas", "hawk", 2,
          "Money marketeers speech",
          "Recent disinflation has been bumpier than expected. "
          "I am much more cautious about cuts."),
        ("2026-04-16", "Bostic", "Atlanta", "dove", -1,
          "Speech at NABE",
          "I now see one cut this year, in Q4. The path forward "
          "remains data dependent."),
        ("2026-04-15", "Jefferson", "Vice Chair", "neutral", 0,
          "Brookings speech",
          "Monetary policy is well positioned to respond to the "
          "evolving economic outlook."),
        ("2026-04-14", "Cook", "Governor", "neutral", 0,
          "Speech at Macroeconomic Policy Institute",
          "I expect to gradually reduce the policy rate as "
          "inflation moves toward 2%."),
    ]
    return pd.DataFrame(rows, columns=[
        "date", "speaker", "role", "lean", "hawk_score",
        "venue", "quote",
    ])


def pull_fed_dots() -> pd.DataFrame:
    """Synthetic dot-plot snapshot: median + range per FOMC year."""
    return pd.DataFrame([
        {"year": "2026", "median": 4.625, "low": 4.375, "high": 5.125,
          "n_voters": 19},
        {"year": "2027", "median": 3.875, "low": 3.375, "high": 4.625,
          "n_voters": 19},
        {"year": "2028", "median": 3.125, "low": 2.625, "high": 3.625,
          "n_voters": 19},
        {"year": "Long run", "median": 2.750,
          "low": 2.500, "high": 3.000, "n_voters": 19},
    ])


def pull_fed_speaker_history() -> pd.DataFrame:
    """Speaker hawkish-dovish rating over time, for a small ribbon
    chart on the speakers tab."""
    rng = random.Random(SEED + 7)
    rows = []
    speakers = ["Powell", "Williams", "Waller", "Bowman",
                 "Goolsbee", "Daly", "Bostic"]
    base = pd.Timestamp("2026-01-01")
    for s in speakers:
        baseline = rng.uniform(-1, 1)
        for w in range(16):
            ts = base + pd.Timedelta(weeks=w)
            score = baseline + rng.gauss(0, 0.4)
            score = max(-2, min(2, score))
            rows.append({"date": ts.strftime("%Y-%m-%d"),
                          "speaker": s,
                          "score": round(score, 2)})
    return pd.DataFrame(rows)


def build_fomc_brief(out_dir: Path) -> Dict[str, Any]:
    """Fed-document-centric dashboard: statement diff prose, minutes
    excerpts with blockquotes, speakers timeline + quote table with
    drill-down, and dot-plot panel with commentary. Heavy use of
    note widgets (hawk / dove / watch) and the full markdown grammar
    (blockquotes, tables, nested lists, ordered lists)."""
    df_speakers = pull_fed_speakers()
    df_dots = pull_fed_dots()
    df_speaker_hist = pull_fed_speaker_history()

    # Average lean score across most recent comments (positive = hawkish)
    recent_score = round(float(df_speakers["hawk_score"].mean()), 2)

    manifest = {
        "schema_version": 1,
        "id": "fomc_brief",
        "title": "FOMC document brief",
        "description": ("Statement diff narrative, minutes excerpts, "
                         "speakers timeline + quote board, and dot "
                         "plot. Document-first dashboard pattern."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "data_as_of": "2026-04-24T18:00:00Z",
            "generated_at": "2026-04-24T18:05:00Z",
            "sources": ["FOMC press materials",
                         "GS Research", "MNI", "Bloomberg"],
            "tags": ["fed", "fomc", "policy"],
            "summary": {
                "title": "Today's read on the Fed",
                "body": (
                    "The post-April-FOMC tape has been **incrementally "
                    "hawkish** despite the soft NFP. Average speaker "
                    f"hawk-dove score is +{recent_score} (positive = "
                    "hawkish), driven by Bowman / Logan / Kashkari "
                    "leaning into 'patience' and a less-frequent "
                    "dovish push from Goolsbee / Bostic.\n\n"
                    "1. **Statement**: removed 'further progress' "
                    "language; added 'risks two-sided'\n"
                    "2. **Press conf**: Powell 'no rush' was the "
                    "memorable line; markets parsed neutral-hawkish\n"
                    "3. **Dots**: 2026 median 4.625% implies one cut "
                    "from current; tail higher\n"
                    "4. **Speakers**: 8/12 recent comments rated "
                    "neutral-to-hawkish\n\n"
                    "> Watch tomorrow's Powell at Stanford. The "
                    "venue is academic; speeches there have "
                    "historically carried more signal than press "
                    "conferences."
                ),
            },
            "methodology": (
                "## Statement diff\n\n"
                "Prose is the artifact. Each row of the diff captures "
                "**one substantive change** between the prior FOMC "
                "statement and the current one. Wording-only edits "
                "(punctuation, paragraphing) are dropped.\n\n"
                "## Hawk-dove score\n\n"
                "Each speaker comment is rated by the desk on a "
                "-2..+2 scale where:\n\n"
                "* `+2` very hawkish (e.g. 'no cuts this year')\n"
                "* `+1` hawkish lean (e.g. 'patient', 'restrictive')\n"
                "* ` 0` neutral / two-sided\n"
                "* `-1` dovish lean (e.g. 'data-dependent cuts')\n"
                "* `-2` very dovish (e.g. 'cuts soon')\n\n"
                "## Refresh\n\n"
                "Manual after each FOMC + speaker event. Production "
                "version pulls the FOMC press doc, Powell transcript, "
                "and speakers from the wires."
            ),
        },
        "datasets": {
            "speakers": df_speakers,
            "dots": df_dots,
            "speaker_hist": df_speaker_hist,
        },
        "filters": [
            {"id": "lean_f", "type": "radio", "default": "All",
              "all_value": "All",
              "options": ["All", "hawk", "dove", "neutral"],
              "field": "lean", "label": "Lean",
              "scope": "tab:speakers",
              "targets": ["speakers_table", "speakers_chart"]},
        ],
        "layout": {"kind": "tabs", "tabs": [
            {"id": "statement", "label": "Statement",
              "description": ("Statement-language diff and the "
                               "hawkish / dovish read of the changes."),
              "rows": [
                  [
                      {"widget": "note", "id": "stmt_thesis", "w": 12,
                        "kind": "thesis",
                        "title": "Read of the April statement",
                        "body": (
                            "The committee **removed the "
                            "'further progress' language** that had "
                            "underwritten the cuts narrative since "
                            "January. New phrasing -- 'risks to "
                            "achieving the dual mandate are now "
                            "more in balance' -- is consistent with "
                            "a longer hold than markets are pricing.\n\n"
                            "Three load-bearing edits:\n\n"
                            "1. *'Inflation has eased over the past "
                            "year but remains elevated'* -> "
                            "*'Inflation has eased; lack of further "
                            "progress in recent months'*\n"
                            "2. *'Risks to mandates are moving "
                            "toward better balance'* -> *'Risks to "
                            "mandates are roughly in balance'*\n"
                            "3. New sentence: *'The committee does "
                            "not expect it will be appropriate to "
                            "reduce the target range until it has "
                            "gained greater confidence...'* (this "
                            "is the meaningful add)")},
                  ],
                  [
                      {"widget": "note", "id": "stmt_hawk", "w": 6,
                        "kind": "watch",
                        "title": "Hawkish reads",
                        "body": (
                            "1. **Inflation language harder.** "
                            "'Lack of further progress' is the "
                            "starkest framing in 18 months.\n"
                            "2. **Explicit cut-conditioning** added "
                            "for the first time. This is the "
                            "biggest move from press-conference "
                            "guidance into the formal statement.\n"
                            "3. Removal of 'better balance' "
                            "phrasing dampens the dovish-pivot "
                            "narrative.")},
                      {"widget": "note", "id": "stmt_dove", "w": 6,
                        "kind": "context",
                        "title": "Dovish counters",
                        "body": (
                            "1. *'Solid pace'* growth language "
                            "**unchanged** (vs upgraded).\n"
                            "2. Labor-market characterization still "
                            "*'strong job gains'* (no upgrade to "
                            "'overheating').\n"
                            "3. No change to the 'sum total of "
                            "data' boilerplate.\n\n"
                            "> Net read: incremental hawkish on "
                            "inflation language; tone elsewhere "
                            "unchanged. Not a regime shift, a "
                            "calibration.")},
                  ],
                  [
                      {"widget": "markdown", "id": "stmt_full", "w": 12,
                        "content": (
                            "## Statement diff (April vs March)\n\n"
                            "| Theme | March '26 | April '26 |\n"
                            "|---|---|---|\n"
                            "| Inflation | 'eased over the past "
                            "year' | 'lack of further progress in "
                            "recent months' |\n"
                            "| Growth | 'expanding at a solid pace' "
                            "| 'expanding at a solid pace' |\n"
                            "| Labor | 'strong job gains' | "
                            "'strong job gains' |\n"
                            "| Risks | 'moving toward better "
                            "balance' | 'roughly in balance' |\n"
                            "| Cut path | (implicit) | 'not "
                            "appropriate... until greater confidence' |\n"
                            "| Balance sheet | unchanged | unchanged |\n\n"
                            "### Voting record\n\n"
                            "All voters **for** the unchanged target "
                            "range and the QT taper schedule. "
                            "Bowman-style dissent absent this round.\n\n"
                            "### What didn't change\n\n"
                            "- Forward guidance framework "
                            "(data-dependent)\n"
                            "- Reference to financial-conditions "
                            "tightening\n"
                            "- The 2% target restatement in "
                            "paragraph 4\n\n"
                            "### Removed phrasing\n\n"
                            "Three short clauses were dropped vs "
                            "March:\n\n"
                            "1. ~~'further progress toward 2%'~~\n"
                            "2. ~~'continued moderation'~~ (in the "
                            "labor section)\n"
                            "3. ~~'broadly disinflationary'~~ "
                            "(price-pressures paragraph)\n\n"
                            "> Each removal is incrementally hawkish; "
                            "the cumulative effect is the most "
                            "hawkish statement since September 2024.")},
                  ],
              ]},
            {"id": "minutes", "label": "Minutes",
              "description": ("Excerpted passages by topic with "
                               "verbatim quotes from participants."),
              "rows": [
                  [
                      {"widget": "note", "id": "min_thesis", "w": 12,
                        "kind": "thesis",
                        "title": "What the minutes say",
                        "body": (
                            "Two themes carry the minutes:\n\n"
                            "1. **Risk-management framing on "
                            "inflation** is more two-sided than "
                            "the statement implies. Several "
                            "participants flagged services prices "
                            "as the bottleneck; a smaller group "
                            "noted shelter has rolled.\n"
                            "2. **Balance-sheet decisions** got "
                            "more space than expected. The minutes "
                            "lean toward a **slower QT pace** than "
                            "current; this is dovish at the "
                            "margin.\n\n"
                            "Net read: the statement was hawkish "
                            "by edit; the minutes are slightly "
                            "more dovish in tone. Markets correctly "
                            "split the difference on the headline "
                            "vol.")},
                  ],
                  [
                      {"widget": "markdown", "id": "min_inflation",
                        "w": 6, "content": (
                            "### Inflation\n\n"
                            "> 'Several participants noted that the "
                            "process of disinflation appears to "
                            "have slowed in recent months, with "
                            "shelter and services components "
                            "providing most of the resistance.'\n\n"
                            "> 'A few participants emphasized that "
                            "shelter inflation has begun to roll "
                            "and may decelerate further over coming "
                            "quarters as observed market rents "
                            "translate to the official series with "
                            "the usual lag.'\n\n"
                            "Implication:\n\n"
                            "1. Services / non-housing services is "
                            "the watch-item.\n"
                            "2. Shelter is mechanically backward-"
                            "looking; the rolling-off is real.\n"
                            "3. The committee's *modal* path is "
                            "still toward 2%; the patience is about "
                            "confidence, not direction.")},
                      {"widget": "markdown", "id": "min_labor",
                        "w": 6, "content": (
                            "### Labor\n\n"
                            "> 'Most participants viewed the labor "
                            "market as having continued to "
                            "rebalance over the past several "
                            "months, with job openings declining "
                            "while the unemployment rate has "
                            "remained low and stable.'\n\n"
                            "> 'A couple of participants suggested "
                            "that further softening in the labor "
                            "market may bring inflation back to "
                            "target more quickly than implied by "
                            "the central tendency of projections.'\n\n"
                            "Implication:\n\n"
                            "* Soft-landing language survives.\n"
                            "* The 'couple' framing on a faster cut "
                            "path is **dovish at the margin**.\n"
                            "* Watch JOLTS / quits ratio for early "
                            "signs of cracks.")},
                  ],
                  [
                      {"widget": "markdown", "id": "min_balance",
                        "w": 6, "content": (
                            "### Balance sheet\n\n"
                            "> 'The vast majority of participants "
                            "judged that it would be appropriate "
                            "to slow the pace of decline of "
                            "securities holdings fairly soon.'\n\n"
                            "> 'A few participants suggested that "
                            "the slower pace might be implemented "
                            "in the next few meetings, with "
                            "appropriate communication.'\n\n"
                            "Implication:\n\n"
                            "1. **QT taper is coming.** This was "
                            "the most concrete forward-looking "
                            "language in the document.\n"
                            "2. Communication path matters; a "
                            "May/June pre-announcement is "
                            "consistent with this language.")},
                      {"widget": "markdown", "id": "min_growth",
                        "w": 6, "content": (
                            "### Growth\n\n"
                            "> 'Real GDP appeared to be expanding "
                            "at a solid pace, supported by resilient "
                            "consumer spending and continued "
                            "strength in business investment.'\n\n"
                            "> 'Some participants noted softening "
                            "in interest-rate-sensitive sectors, "
                            "particularly auto sales and "
                            "single-family residential investment.'\n\n"
                            "Implication:\n\n"
                            "1. Headline growth narrative unchanged.\n"
                            "2. The 'softening' language on rate-"
                            "sensitive sectors is **the leading "
                            "indicator** to watch.\n"
                            "3. No participants flagged "
                            "overheating; demand-side overheat is "
                            "off the table for now.")},
                  ],
              ]},
            {"id": "speakers", "label": "Speakers",
              "description": ("Recent FOMC speakers with hawkish-"
                               "dovish rating + verbatim quote "
                               "highlights. Click any row for the "
                               "full quote."),
              "rows": [
                  [
                      {"widget": "note", "id": "sp_thesis", "w": 12,
                        "kind": "insight",
                        "title": "What the speakers are saying",
                        "body": (
                            f"Average score across the 12 most "
                            f"recent speakers is **+{recent_score}** "
                            "(positive = hawkish). The hawkish "
                            "skew is **Bowman / Logan / Kashkari**; "
                            "dovish counterweight is **Goolsbee / "
                            "Bostic**. Powell himself remains "
                            "neutral with a hawkish tilt on the "
                            "inflation side.\n\n"
                            "> Filter by lean to isolate either "
                            "side; click any row to read the full "
                            "quote in context.")},
                  ],
                  [
                      {"widget": "chart", "id": "speakers_chart",
                        "w": 12, "h_px": 320,
                        "title": "Hawk-dove score by speaker",
                        "subtitle": ("Sum of recent comments; "
                                      "positive = hawkish"),
                        "spec": {
                            "chart_type": "bar_horizontal",
                            "dataset": "speakers",
                            "mapping": {"y": "speaker",
                                          "x": "hawk_score",
                                          "x_title": "Hawk-dove score"},
                            "annotations": [
                                {"type": "vline", "x": 0,
                                  "label": "Neutral",
                                  "color": "#666",
                                  "style": "dashed"},
                            ]}},
                  ],
                  [
                      {"widget": "table", "id": "speakers_table",
                        "w": 12, "dataset_ref": "speakers",
                        "title": "Speaker quote board",
                        "info": ("Click a row for the full venue + "
                                  "quote. Filter by lean above."),
                        "searchable": True, "sortable": True,
                        "max_rows": 30, "row_height": "compact",
                        "columns": [
                            {"field": "date", "label": "Date",
                              "align": "left", "format": "date"},
                            {"field": "speaker", "label": "Speaker",
                              "align": "left"},
                            {"field": "role", "label": "Role",
                              "align": "left"},
                            {"field": "lean", "label": "Lean",
                              "align": "center",
                              "conditional": [
                                  {"op": "==", "value": "hawk",
                                    "background": "#fed7d7",
                                    "color": "#742a2a"},
                                  {"op": "==", "value": "dove",
                                    "background": "#c6f6d5",
                                    "color": "#22543d"},
                                  {"op": "==", "value": "neutral",
                                    "background": "#edf2f7",
                                    "color": "#4a5568"},
                              ]},
                            {"field": "hawk_score", "label": "Score",
                              "align": "center", "format": "signed:0",
                              "color_scale": {
                                  "min": -2, "max": 2,
                                  "palette": "gs_diverging"}},
                            {"field": "quote", "label": "Quote",
                              "align": "left",
                              "tooltip": "Click row for full quote"},
                        ],
                        "row_click": {
                            "title_field": "speaker",
                            "subtitle_template": (
                                "{role} . {date} . lean: {lean} "
                                "({hawk_score:signed:0})"),
                            "detail": {
                                "wide": True,
                                "sections": [
                                    {"type": "stats",
                                      "fields": [
                                          {"field": "lean",
                                            "label": "Lean"},
                                          {"field": "hawk_score",
                                            "label": "Score",
                                            "format": "signed:0",
                                            "suffix": " / +2"},
                                          {"field": "venue",
                                            "label": "Venue"},
                                      ]},
                                    {"type": "markdown",
                                      "title": "Quote",
                                      "template": (
                                          "> {quote}\n\n"
                                          "Source: *{venue}*, "
                                          "{date}.")},
                                ],
                            },
                        }},
                  ],
              ]},
            {"id": "dots", "label": "Dot plot",
              "description": ("March SEP median + range with desk "
                               "commentary."),
              "rows": [
                  [
                      {"widget": "note", "id": "dot_thesis", "w": 12,
                        "kind": "thesis",
                        "title": "What the dots imply",
                        "body": (
                            "2026 median at **4.625%** implies one "
                            "25bp cut from the current target range "
                            "(4.875%). The range (4.375%-5.125%) is "
                            "**asymmetric to the upside** -- two "
                            "voters at 5.125% pull the tail "
                            "higher.\n\n"
                            "1. **2026 median**: 4.625% (one cut)\n"
                            "2. **2027 median**: 3.875% (three more)\n"
                            "3. **Long run**: 2.75% (unchanged)\n\n"
                            "> Market is currently pricing ~50bp of "
                            "cuts in 2026, slightly more than the "
                            "median. The hawkish tail of the dots "
                            "is more meaningful than the median for "
                            "the right-skew of policy outcomes.")},
                  ],
                  [
                      {"widget": "chart", "id": "dot_chart", "w": 8,
                        "h_px": 320,
                        "title": "FOMC dots: median + range",
                        "subtitle": ("Vertical bars = high-low across "
                                      "voters; line = median"),
                        "spec": {
                            "chart_type": "bullet", "dataset": "dots",
                            "mapping": {"y": "year",
                                          "x": "median",
                                          "x_low": "low",
                                          "x_high": "high",
                                          "label": "year",
                                          "x_title": "Policy rate (%)"}}},
                      {"widget": "stat_grid", "id": "dot_summary",
                        "w": 4,
                        "title": "Dot summary",
                        "stats": [
                            {"id": "d1", "label": "2026 median",
                              "value": "4.625%",
                              "sub": "One cut from current",
                              "info": ("Median of the 19 voter dots "
                                        "for end-2026")},
                            {"id": "d2", "label": "2027 median",
                              "value": "3.875%",
                              "sub": "Three more cuts implied"},
                            {"id": "d3", "label": "Long run",
                              "value": "2.750%",
                              "sub": "Unchanged from prior SEP"},
                            {"id": "d4", "label": "Hawk tail (2026)",
                              "value": "5.125%",
                              "sub": "Two voters; matters for skew"},
                        ]},
                  ],
              ]},
        ]},
        "links": [],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1400, height=1700)
    return _result(r, thumb)


# =============================================================================
# DEMO: research_feed  (Substack-style article feed with full-body drilldown)
# =============================================================================
#
# A reading-list-meets-aggregator pattern: list of analyst pieces with
# tags + truncated takeaway, click any row to read the full markdown
# body. Curator commentary lives in note widgets at the top. Heavy
# use of the row_click rich modal pattern with markdown sections,
# nested lists for "key takeaways" inside articles, and the new
# tables-in-markdown for inline data.


def pull_research_articles() -> pd.DataFrame:
    """Synthetic feed of analyst articles. Each row carries a full
    markdown body for the drill-down panel."""
    rows = [
        {
            "date": "2026-04-24",
            "author": "G. Burghardt",
            "title": "Rolling down the curve: a primer for 2026",
            "topic": "Rates",
            "tags": "carry, butterflies, 2s5s10s",
            "minutes": 8,
            "summary": ("Foundational note on butterfly trades "
                         "and roll-down mechanics. Reframes carry "
                         "as the dominant factor in 2026's range-"
                         "bound rates regime."),
            "body": (
                "## Why this note now\n\n"
                "We're in a **range-bound** regime. With realized "
                "vol on the 10Y collapsed to 6 vols and Fed-cut "
                "expectations flat-lined into PCE, the dominant "
                "P&L driver is **carry**, not direction.\n\n"
                "Three implications:\n\n"
                "1. The cleanest expression of a range view is a "
                "**fly**, not a duration trade.\n"
                "2. Roll-down on the belly is currently +6bp/3M, "
                "the highest since 2019.\n"
                "3. The 5s30s flattener loses ~1.5bp/month to "
                "negative carry; needs ~3bp/month of curve roll "
                "to break even.\n\n"
                "## The mechanics\n\n"
                "A 2s5s10s fly works because:\n\n"
                "- The **belly** (5Y) carries positive vs the "
                "wings (2Y, 10Y) in a positively-sloped curve.\n"
                "- Roll-down compounds: the 5Y rolls down to "
                "the 4Y faster than the 2Y rolls to 1Y or the "
                "10Y rolls to 9Y.\n"
                "- *Convexity* on the belly is lower than the "
                "wings, so the trade is short-gamma. This is "
                "the cost of the carry.\n\n"
                "> The fly is **not** a directional trade. It "
                "is a duration-neutral expression of a range "
                "view. If you want directional, use a 2Y or "
                "10Y outright.\n\n"
                "## Sizing\n\n"
                "I default to:\n\n"
                "| Leg | DV01 |\n"
                "|---|---:|\n"
                "| 2Y | -50 |\n"
                "| 5Y | +100 |\n"
                "| 10Y | -50 |\n\n"
                "DV01-neutral, ~3:1:3 in face value. "
                "Adjust the wings if your view is asymmetric.\n\n"
                "## Risk\n\n"
                "1. **Sudden steepening**: hot CPI + Fed reaction "
                "function flip. Stop is +25bp on the wings.\n"
                "2. **Sudden flattening**: recession trade; "
                "front-end rallies into the belly.\n"
                "3. *~~Idiosyncratic auction noise~~* is usually "
                "transitory; do not stop on it."),
        },
        {
            "date": "2026-04-23",
            "author": "K. Lim",
            "title": "EUR positioning: short EUR/USD into Lagarde",
            "topic": "FX",
            "tags": "EUR, USD, ECB",
            "minutes": 4,
            "summary": ("Tactical short EUR/USD into Lagarde "
                         "press conference; entry 1.1020, target "
                         "1.0950, stop 1.1080."),
            "body": (
                "## Setup\n\n"
                "EUR has been **range-bound** for three weeks, "
                "1.0980-1.1060. ECB cut path is fully priced; "
                "I see asymmetric risk into Lagarde.\n\n"
                "Trade:\n\n"
                "| | Level |\n"
                "|---|---|\n"
                "| Entry | 1.1020 |\n"
                "| Target | 1.0950 |\n"
                "| Stop | 1.1080 |\n"
                "| R/R | 1.2 |\n\n"
                "## Catalyst\n\n"
                "Three things to listen for:\n\n"
                "1. Service-prices framing (sticky vs cooling).\n"
                "2. Wage-growth language (deceleration vs "
                "stable).\n"
                "3. Any pushback on **June** vs September for "
                "the first cut.\n\n"
                "> If she leans into 'broadly on track' "
                "disinflation **and** signals June is on the "
                "table, EUR breaks 1.10."),
        },
        {
            "date": "2026-04-22",
            "author": "M. Reyes",
            "title": "Front-end UST: positioning vs price",
            "topic": "Rates",
            "tags": "UST, positioning, CFTC",
            "minutes": 6,
            "summary": ("CFTC futures show net specs short 140k 2Y "
                         "contracts. Net dealer long was the largest "
                         "since 2019. The pain trade is a rally."),
            "body": (
                "## Positioning\n\n"
                "The **CFTC TFF** report shows specs short ~140k "
                "2Y contracts (-0.5z vs 5Y avg). The mirror image "
                "is dealers long; this is the largest net dealer "
                "long since 2019.\n\n"
                "Mechanically:\n\n"
                "1. Specs are short.\n"
                "2. Dealers are long.\n"
                "3. Real money is moderately long; this is the "
                "balance.\n\n"
                "## What changes my mind\n\n"
                "- A clean 2Y break above 4.40% with no headline "
                "would tell me dealers are flipping.\n"
                "- A failed rally on a soft NFP would tell me "
                "the spec base has rotated.\n\n"
                "> The pain trade is a 2Y rally; specs cover and "
                "dealers monetize. Short-vol carry trades on the "
                "front-end **work** in this setup."),
        },
        {
            "date": "2026-04-22",
            "author": "P. Singh",
            "title": "Apple services: re-rating or a one-off?",
            "topic": "Equity",
            "tags": "AAPL, services, re-rating",
            "minutes": 5,
            "summary": ("AAPL services 14% y/y vs 8% trailing 4Q "
                         "average. Buy-side debate: structural "
                         "re-rating or pulling forward?"),
            "body": (
                "## What happened\n\n"
                "Apple Q2 services revenue was **$24.2bn**, +14% "
                "y/y vs an 8% trailing 4Q average. The largest "
                "single beat on services in three years.\n\n"
                "## Bull case\n\n"
                "1. Subscription mix is hardening: video, music, "
                "cloud, news all growing double digits.\n"
                "2. App Store take rate stable despite EU/US "
                "regulatory pressure.\n"
                "3. AI-services bundle (rumored) starts to drip "
                "into the FY27 estimate stack.\n\n"
                "## Bear case\n\n"
                "1. China iPhone weakness offsets services "
                "growth at the consolidated level.\n"
                "2. *Pulling forward* of subscription renewals "
                "from a Q3 calendar shift.\n"
                "3. Services margin pressure once AI compute "
                "costs hit COGS.\n\n"
                "## Trade implication\n\n"
                "> Long AAPL Q3 vol via straddle. The buy/sell "
                "side dispersion on services is the largest in "
                "the cohort; expect a 5-7% post-print move.\n\n"
                "Skip the ~~outright long~~ trade -- the China "
                "tail is real."),
        },
        {
            "date": "2026-04-21",
            "author": "G. Burghardt",
            "title": "When does carry stop working?",
            "topic": "Rates",
            "tags": "carry, regime, vol",
            "minutes": 7,
            "summary": ("Three signals for the carry-regime "
                         "rolling over: realized vol breakout, "
                         "MOVE > 110, and a 2s5s spread move > "
                         "1z."),
            "body": (
                "## The setup\n\n"
                "Carry trades work when:\n\n"
                "1. The curve is positively sloped (so roll-"
                "down is positive).\n"
                "2. Realized vol is contained (so the carry "
                "outpaces the noise).\n"
                "3. The Fed reaction function is well anchored "
                "(so the tails are bounded).\n\n"
                "All three are **currently true**. None are "
                "permanent.\n\n"
                "## Three regime-rollover signals\n\n"
                "Order matters; the first one tends to lead the "
                "next two by 2-4 weeks.\n\n"
                "1. **MOVE index > 110**. Currently 78. Fed "
                "uncertainty is the marginal driver.\n"
                "2. **5d realized 10Y vol > 8 vols**. Currently "
                "6.0. A breakout means dealers have to widen.\n"
                "3. **2s5s break of 1z**. Currently flat; a 1z "
                "break tells you the front-end pricing is "
                "shifting.\n\n"
                "## Trades to watch\n\n"
                "* If signal 1 hits: cut fly size by 50%.\n"
                "* If 1+2 hit: flatten the fly entirely.\n"
                "* If 1+2+3 hit: flip to a long-vol expression.\n\n"
                "> The cleanest hedge is a **payer ladder** in "
                "1Y-1Y; roughly delta-neutral, gets paid if any "
                "of the three signals fires."),
        },
        {
            "date": "2026-04-21",
            "author": "T. Nakamura",
            "title": "BoJ June review: what to listen for",
            "topic": "Policy",
            "tags": "BoJ, JPY, Ueda",
            "minutes": 4,
            "summary": ("BoJ governor Ueda flagged a 'likely' "
                         "June review. Three things matter: "
                         "wage-growth read, JGB purchase taper "
                         "schedule, and FX language."),
            "body": (
                "## Why June matters\n\n"
                "The BoJ has been the slowest of the G3 "
                "central banks to normalize. June is the "
                "earliest plausible window for a meaningful "
                "**second hike** + JGB taper announcement.\n\n"
                "## Three things to listen for\n\n"
                "1. **Wage-growth read.** Shunto results "
                "outperformed; if Ueda upgrades the language, "
                "the case for a hike strengthens.\n"
                "2. **JGB purchase schedule.** A pre-announced "
                "taper would be the biggest signal.\n"
                "3. **FX language.** USDJPY 156+ has put MoF "
                "back in the picture; coordination matters.\n\n"
                "> The risk is the BoJ talks about wages "
                "carefully without committing to action; this "
                "would be **dovish at the margin**, fueling "
                "another leg of yen weakness."),
        },
        {
            "date": "2026-04-20",
            "author": "M. Reyes",
            "title": "5Y auction tail: what it tells us",
            "topic": "Rates",
            "tags": "UST, auction, 5Y",
            "minutes": 3,
            "summary": ("Today's 5Y stopped 0.4bp through. BTC "
                         "2.42x vs 5-auction avg 2.45x. Modest "
                         "concession; not a regime signal."),
            "body": (
                "## The print\n\n"
                "$70bn 5Y stopped at **4.215%**, **0.4bp tail**. "
                "Bid-to-cover 2.42x (5-auction avg 2.45x). "
                "Indirect bid 62% (avg 65%).\n\n"
                "## Read\n\n"
                "1. Tail is **modest**; not a 2-bp+ regime "
                "signal.\n"
                "2. Indirect bid soft but within range.\n"
                "3. Concession was visible 30min ahead in cash; "
                "auction was *priced in*.\n\n"
                "> No action; the auction was a non-event "
                "wrapped in headline noise."),
        },
        {
            "date": "2026-04-19",
            "author": "K. Lim",
            "title": "DXY's correlation with the front-end has flipped",
            "topic": "FX",
            "tags": "DXY, USD, correlation",
            "minutes": 5,
            "summary": ("60d rolling correlation between DXY and "
                         "US 2Y has flipped negative for the "
                         "first time since 2022. What it means "
                         "for FX positioning."),
            "body": (
                "## The chart\n\n"
                "60d rolling correlation between DXY (level) "
                "and US 2Y (level) has flipped from +0.6 to "
                "**-0.2** over the last six weeks. First "
                "negative print since 2022.\n\n"
                "## Why it might matter\n\n"
                "1. The **rates-driven** USD trade weakens. "
                "Currency now responds more to growth "
                "differentials than rate differentials.\n"
                "2. **Carry trades into USD** lose their "
                "anchor; expect more two-way price action.\n"
                "3. **EUR/USD vol** is mispricing this regime "
                "shift; the curve is too flat in the 1m-3m "
                "tenor.\n\n"
                "## Trade\n\n"
                "Long EUR/USD 1m-3m vol via calendar.\n\n"
                "> Hedge with a digital strangle so the "
                "carry into the position is contained."),
        },
    ]
    return pd.DataFrame(rows)


def build_research_feed(out_dir: Path) -> Dict[str, Any]:
    """Substack-style article feed: list of analyst notes with
    truncated takeaway, click any row for full markdown body in a
    drill-down modal. Curator commentary lives in note widgets up
    top. Stress-tests the rich row-click pattern with markdown
    sections at scale."""
    df = pull_research_articles()
    n_articles = len(df)
    n_authors = df["author"].nunique()

    manifest = {
        "schema_version": 1,
        "id": "research_feed",
        "title": "Research feed",
        "description": ("Substack-style aggregator: analyst notes "
                         "as rows, full markdown bodies in row-click "
                         "drilldown. Curator commentary in note "
                         "widgets up top. Demonstrates how to package "
                         "a reading-list as an interactive artifact."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "data_as_of": "2026-04-24T17:00:00Z",
            "generated_at": "2026-04-24T17:05:00Z",
            "sources": ["GS Research", "Curated external"],
            "tags": ["research", "reading-list", "feed"],
            "summary": {
                "title": "Editor's read this week",
                "body": (
                    f"**{n_articles} pieces from {n_authors} authors** "
                    "this week. The cohort is converging on a "
                    "**carry-regime** narrative across rates and FX, "
                    "with the equity desk arguing for **vol** as the "
                    "expression rather than direction.\n\n"
                    "1. **Burghardt** anchors the rates-carry view; "
                    "his fly piece is the load-bearing read.\n"
                    "2. **Lim** picks up the FX corollary -- short "
                    "EUR/USD vol-of-vol play.\n"
                    "3. **Singh** on AAPL: long vol via "
                    "straddle, not outright.\n\n"
                    "> Pick one Burghardt piece and one tactical "
                    "trade idea; you'll have today covered."
                ),
            },
            "methodology": (
                "## Source\n\n"
                "Synthetic feed for demo. Production version pulls "
                "from the GS Research API + a curated external set "
                "(buyside notes, blog posts, podcasts).\n\n"
                "## Tagging\n\n"
                "Tags are author-supplied; topic is curator-"
                "assigned for filtering."
            ),
        },
        "datasets": {
            "articles": df,
        },
        "filters": [
            {"id": "author_f", "type": "multiSelect",
              "default": list(df["author"].unique()),
              "options": list(df["author"].unique()),
              "field": "author", "label": "Author",
              "targets": ["articles_table"]},
            {"id": "topic_f", "type": "radio", "default": "All",
              "all_value": "All",
              "options": (["All"]
                           + sorted(df["topic"].unique().tolist())),
              "field": "topic", "label": "Topic",
              "targets": ["articles_table"]},
            {"id": "search_f", "type": "text", "default": "",
              "field": "title", "op": "contains",
              "label": "Title contains",
              "placeholder": "e.g. carry, AAPL, BoJ",
              "targets": ["articles_table"]},
        ],
        "layout": {"kind": "grid", "rows": [
            [
                {"widget": "note", "id": "feat", "w": 12,
                  "kind": "thesis",
                  "title": "Featured: 'Rolling down the curve' (Burghardt)",
                  "icon": "*",
                  "body": (
                      "Foundational read on butterflies in a "
                      "carry-regime. Reframes the 2026 rates "
                      "playbook: **the dominant factor is roll-"
                      "down, not direction**. Eight-minute read; "
                      "I'd put it on every desk.\n\n"
                      "Three things to take away:\n\n"
                      "1. The cleanest range expression is a fly, "
                      "not a duration trade.\n"
                      "2. Belly roll-down (+6bp/3M) is the highest "
                      "since 2019.\n"
                      "3. Skip the 5s30s flattener; negative carry "
                      "eats the trade.\n\n"
                      "> Click the row in the feed below for the "
                      "full body, including DV01 sizing and the "
                      "regime-rollover playbook from the companion "
                      "piece.")},
            ],
            [
                {"widget": "note", "id": "curator_carry", "w": 6,
                  "kind": "insight",
                  "title": "Theme: carry across asset classes",
                  "body": (
                      "Three pieces converge on the carry view:\n\n"
                      "1. **Burghardt** -- rates-curve roll-down\n"
                      "2. **Reyes** -- positioning vs price (front-"
                      "end UST)\n"
                      "3. **Burghardt** (companion) -- regime-"
                      "rollover signals\n\n"
                      "> The triangulation is rare. When three "
                      "pieces with different framings reach the "
                      "same conclusion, the conclusion is more "
                      "load-bearing than any one piece.")},
                {"widget": "note", "id": "curator_vol", "w": 6,
                  "kind": "watch",
                  "title": "Theme: vol > direction",
                  "body": (
                      "The cross-asset vol case is being made "
                      "from three sides:\n\n"
                      "1. **Lim** -- DXY-rates correlation flip "
                      "argues for FX vol\n"
                      "2. **Singh** -- AAPL straddle, not outright\n"
                      "3. **Burghardt** -- payer ladder as the "
                      "regime hedge\n\n"
                      "Connector: each author argues against a "
                      "**directional** expression. This is "
                      "informative on its own.")},
            ],
            [
                {"widget": "note", "id": "curator_skip", "w": 12,
                  "kind": "context",
                  "title": "What I would skip",
                  "body": (
                      "Three pieces I would not prioritize on a "
                      "tight schedule:\n\n"
                      "* **5Y auction read** -- non-event by the "
                      "author's own admission; useful as a tape-"
                      "reading reference but not actionable.\n"
                      "* **Apple services** -- the bull/bear is "
                      "well-trafficked; the trade idea is the "
                      "value-add.\n"
                      "* **BoJ June review** -- worth bookmarking "
                      "for late May; the actionable date is the "
                      "preview window, not now.\n\n"
                      "> *Bookmark the BoJ piece for May 25; that's "
                      "the read window for June.*")},
            ],
            [
                {"widget": "table", "id": "articles_table", "w": 12,
                  "dataset_ref": "articles",
                  "title": "Article feed",
                  "info": ("Click any row for the full markdown "
                           "body in a drill-down panel. Filter by "
                           "author / topic / title-search above."),
                  "searchable": True, "sortable": True,
                  "max_rows": 30, "row_height": "compact",
                  "downloadable": False,
                  "columns": [
                      {"field": "date", "label": "Date",
                        "align": "left", "format": "date"},
                      {"field": "author", "label": "Author",
                        "align": "left"},
                      {"field": "title", "label": "Title",
                        "align": "left",
                        "tooltip": "Click row for full body"},
                      {"field": "topic", "label": "Topic",
                        "align": "left"},
                      {"field": "tags", "label": "Tags",
                        "align": "left"},
                      {"field": "minutes", "label": "Minutes",
                        "align": "right", "format": "integer",
                        "tooltip": "Estimated read time"},
                  ],
                  "row_highlight": [
                      {"field": "author", "op": "==",
                        "value": "G. Burghardt", "class": "info"},
                  ],
                  "row_click": {
                      "title_field": "title",
                      "subtitle_template": (
                          "{author} . {date} . {topic} . "
                          "{minutes} min read"),
                      "detail": {
                          "wide": True,
                          "sections": [
                              {"type": "stats",
                                "fields": [
                                    {"field": "author",
                                      "label": "Author"},
                                    {"field": "topic",
                                      "label": "Topic"},
                                    {"field": "minutes",
                                      "label": "Read time",
                                      "format": "integer",
                                      "suffix": " min"},
                                    {"field": "date",
                                      "label": "Date"},
                                ]},
                              {"type": "markdown",
                                "title": "TL;DR",
                                "template": "> {summary}"},
                              {"type": "markdown",
                                "title": "Full body",
                                "template": "{body}"},
                              {"type": "markdown",
                                "title": "Filed under",
                                "template":
                                    "Tags: `{tags}`."},
                          ],
                      },
                  }},
            ],
        ]},
        "links": [],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1400, height=1500)
    return _result(r, thumb)


# =============================================================================
# DEMO: macro_studio  (interactive bivariate analysis)
# =============================================================================
#
# Centerpiece: `scatter_studio` chart with the full feature surface --
# author whitelists X / Y / color / size columns, viewer picks
# combinations at runtime, per-axis transforms, regression toggle,
# window slicer, outlier filter, stats strip.
#
# Also exercises:
#   - `correlation_matrix` builder w/ a different transform than
#     risk_regime (raw levels) so both views are represented.
#   - `mapping.axes` 4-axis time-series chart (3+ axes API the
#     legacy 2-axis demo never reaches).
#   - `y_log` log-scale toggle on a credit spread chart.
#   - `polygon` brush type on the studio scatter.


def _pull_macro_panel(years: int = 5) -> pd.DataFrame:
    """Wide-form macro panel for scatter_studio + correlation_matrix +
    mapping.axes. One row per business day, plain-English columns,
    plus a categorical `regime` for the color dropdown."""
    random.seed(SEED + 80)
    n = 252 * years
    dates = pd.date_range(end=END_DATE, periods=n, freq="B")
    us_2y, us_10y, real_10y, be_5y5y = 4.05, 4.31, 1.85, 2.42
    ig_oas, hy_oas = 110.0, 360.0
    vix = 16.0
    spx = 5100.0
    dxy = 104.0
    rows = []
    for i, d in enumerate(dates):
        # Stylised regime path: Hiking -> Hold -> Cutting -> Easing
        if i < n * 0.30:
            regime = "Hiking"
            us_2y += random.gauss(0.005, 0.020)
            spx_drift, ig_drift = -0.0001, 0.18
        elif i < n * 0.55:
            regime = "Hold"
            us_2y += random.gauss(0.0, 0.014)
            spx_drift, ig_drift = 0.0004, 0.05
        elif i < n * 0.80:
            regime = "Cutting"
            us_2y += random.gauss(-0.005, 0.018)
            spx_drift, ig_drift = 0.0006, -0.10
        else:
            regime = "Easing"
            us_2y += random.gauss(-0.004, 0.020)
            spx_drift, ig_drift = 0.0008, -0.15
        us_2y = max(0.50, us_2y)
        us_10y = max(0.80, us_10y + random.gauss(0, 0.016))
        be_5y5y = max(0.5, be_5y5y + random.gauss(0, 0.012))
        real_10y = max(-0.5, us_10y - be_5y5y)
        ig_oas = max(60, ig_oas + ig_drift + random.gauss(0, 1.2))
        hy_oas = max(220, hy_oas + 2.5 * ig_drift + random.gauss(0, 4.0))
        vix = max(9, vix + random.gauss(0, 0.85)
                   + (3.0 if regime == "Hiking" else 0.0)
                   + (-1.2 if regime == "Easing" else 0.0))
        spx *= 1 + spx_drift + random.gauss(0, 0.0095)
        dxy += random.gauss(0, 0.20)
        rows.append({
            "date":         d,
            "us_2y":        round(us_2y, 3),
            "us_10y":       round(us_10y, 3),
            "real_10y":     round(real_10y, 3),
            "breakeven_5y5y": round(be_5y5y, 3),
            "ig_oas_bp":    round(ig_oas, 1),
            "hy_oas_bp":    round(hy_oas, 1),
            "vix":          round(vix, 2),
            "spx":          round(spx, 2),
            "dxy":          round(dxy, 2),
            "regime":       regime,
        })
    return pd.DataFrame(rows)


def build_macro_studio(out_dir: Path) -> Dict[str, Any]:
    """Macro studio: scatter_studio + correlation_matrix + multi-axis
    time series + log-scale credit spread chart."""
    df_panel = _pull_macro_panel()

    manifest = {
        "schema_version": 1,
        "id": "macro_studio",
        "title": "Macro studio (interactive)",
        "description": ("Exploratory bivariate analysis: pick any X / "
                         "Y / color / size from the whitelist, apply "
                         "per-axis transforms, fit OLS per group, and "
                         "read off the stats strip beneath the canvas. "
                         "Plus a 4-axis macro overlay and a log-scale "
                         "credit chart with polygon brush."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "data_as_of": "2026-04-22T16:00:00Z",
            "generated_at": "2026-04-22T16:05:00Z",
            "sources": ["GS Market Data", "Synthetic"],
            "tags": ["macro", "interactive", "studio"],
            "summary": {
                "title": "Studio mode",
                "body": (
                    "Use the **chart controls drawer** "
                    "(`\u22EE` button on each chart tile) to flip X / "
                    "Y, change transform, toggle the regression line, "
                    "and slice the visible window.\n\n"
                    "1. **Levels vs levels**: pick `us_10y` (X) and "
                    "`vix` (Y) -- baseline negative tilt, wide cloud.\n"
                    "2. **% change vs % change**: switch both "
                    "transforms to `pct_change` -- structure tightens.\n"
                    "3. **Per-regime fit**: set color to `regime`, "
                    "regression to `ols_per_group` -- different fits "
                    "by Hiking / Hold / Cutting / Easing."),
            },
            "methodology": (
                "## Studio whitelist\n\n"
                "All numeric columns of the macro panel are exposed "
                "as X / Y choices. Color is restricted to `regime`. "
                "Window slicer ranges from full history down to "
                "1-year. Per-axis transforms include raw / log / "
                "change / pct_change / yoy_pct / zscore / "
                "rolling_zscore_252 / rank_pct.\n\n"
                "## Stats strip\n\n"
                "* `n` -- count after window + outlier filter\n"
                "* `r` -- Pearson correlation (with significance "
                "stars)\n"
                "* `R^2` -- coefficient of determination\n"
                "* `beta`, `alpha`, `RMSE`, `p-value`\n\n"
                "With `OLS per color`, per-group `r` / `R^2` / "
                "`beta` / `n` is also listed."
            ),
        },
        "datasets": {"macro": df_panel},
        "filters": [
            {"id": "studio_window", "type": "dateRange", "default": "2Y",
              "field": "date", "label": "Initial range",
              "scope": "global",
              "targets": ["spread_log", "macro_axes"],
              "description": ("Sets the visible window on the credit "
                                "and multi-axis charts. The studio's "
                                "own slider is on the controls drawer.")},
        ],
        "layout": {"kind": "tabs", "cols": 12, "tabs": [
            # --- Tab 1: Studio + correlation matrix --------------------
            {"id": "studio", "label": "Bivariate studio",
              "description": ("Pick any X / Y from the dropdowns; "
                                "the OLS line and stats strip "
                                "recompute live."),
              "rows": [
                  [
                      {"widget": "chart", "id": "studio_chart",
                        "w": 8, "h_px": 520,
                        "title": "Macro pairs (interactive)",
                        "subtitle": ("Use the controls drawer "
                                       "(\u22EE) to switch X / Y / "
                                       "color / transform / "
                                       "regression / window."),
                        "footer": ("Stars: *** p<0.001, ** p<0.01, "
                                    "* p<0.05, \u00B7 p<0.10. "
                                    "P-value uses normal-approx; "
                                    "display only."),
                        "spec": {
                            "chart_type": "scatter_studio",
                            "dataset": "macro",
                            "mapping": {
                                "x_columns":     [
                                    "us_2y", "us_10y", "real_10y",
                                    "breakeven_5y5y", "ig_oas_bp",
                                    "hy_oas_bp", "vix", "dxy"],
                                "y_columns":     [
                                    "spx", "vix", "ig_oas_bp",
                                    "hy_oas_bp", "breakeven_5y5y",
                                    "real_10y", "us_10y"],
                                "color_columns": ["regime"],
                                "order_by":      "date",
                                "x_default":     "us_10y",
                                "y_default":     "vix",
                                "color_default": "regime",
                                "label_column":  "date"},
                            "studio": {
                                "transforms": [
                                    "raw", "log", "change",
                                    "pct_change", "yoy_pct",
                                    "zscore", "rolling_zscore_252",
                                    "rank_pct"],
                                "regression": ["off", "ols",
                                                "ols_per_group"],
                                "regression_default": "ols",
                                "windows": ["all", "252d", "504d",
                                              "5y"],
                                "window_default": "all",
                                "outliers": ["off", "iqr_3", "z_4"],
                                "outlier_default": "off",
                                "show_stats": True}}},
                      {"widget": "chart", "id": "corr_levels",
                        "w": 4, "h_px": 520,
                        "title": "Macro correlation",
                        "subtitle": "% change, 252-day rolling pairs.",
                        "spec": {
                            "chart_type": "correlation_matrix",
                            "dataset": "macro",
                            "mapping": {
                                "columns": [
                                    "us_2y", "us_10y", "real_10y",
                                    "breakeven_5y5y", "ig_oas_bp",
                                    "vix", "spx", "dxy"],
                                "method":      "pearson",
                                "transform":   "pct_change",
                                "order_by":    "date",
                                "min_periods": 60,
                                "show_values": True,
                                "value_decimals": 2}}},
                  ],
                  [{"widget": "note", "id": "studio_thesis", "w": 12,
                     "kind": "insight",
                     "title": "Reading the studio",
                     "body": (
                         "*r* is the headline number on the strip; the "
                         "stars summarise significance. Beware: a tight "
                         "fit on **levels** can vanish entirely on "
                         "**% change** -- common for trending series. "
                         "The right-hand correlation matrix runs the "
                         "same `pct_change` transform across the panel "
                         "for a quick sanity-check on what the studio "
                         "should be reproducing for any given pair.")}],
              ]},
            # --- Tab 2: Multi-axis time series + log scale -------------
            {"id": "axes", "label": "Multi-axis overlay",
              "description": ("Four independent y-axes on one chart "
                                "via `mapping.axes`; log-scale credit "
                                "panel underneath."),
              "rows": [
                  [{"widget": "chart", "id": "macro_axes",
                     "w": 12, "h_px": 460,
                     "title": "SPX / UST10Y / DXY / VIX overlay",
                     "subtitle": ("Each series renders on its own "
                                    "axis with its own scale and "
                                    "color-coded ticks."),
                     "spec": {
                         "chart_type": "multi_line",
                         "dataset": "macro",
                         "mapping": {
                             "x": "date",
                             "y": ["spx", "us_10y", "dxy", "vix"],
                             "axes": [
                                 {"side": "left",  "title": "SPX",
                                   "series": ["spx"],
                                   "format": "compact"},
                                 {"side": "right", "title": "UST 10Y",
                                   "series": ["us_10y"],
                                   "format": "percent",
                                   "invert": True},
                                 {"side": "left",  "title": "DXY",
                                   "series": ["dxy"]},
                                 {"side": "right", "title": "VIX",
                                   "series": ["vix"]},
                             ],
                             "axis_offset_step": 80,
                             "axis_color_coding": True,
                         },
                         "annotations": [
                             {"type": "vline", "x": "2024-04-15",
                               "axis": 0,
                               "label": "Hiking peak",
                               "color": "#999",
                               "style": "dashed"},
                             {"type": "hline", "y": 30, "axis": 3,
                               "label": "Stress",
                               "color": "#c53030",
                               "style": "dashed"},
                         ],
                     }}],
                  [{"widget": "chart", "id": "spread_log",
                     "w": 12, "h_px": 380,
                     "title": "IG vs HY OAS (log scale)",
                     "subtitle": ("Y-axis log10 -- compresses the "
                                    "HY range without flattening "
                                    "IG."),
                     "spec": {
                         "chart_type": "multi_line",
                         "dataset": "macro",
                         "mapping": {
                             "x": "date",
                             "y": ["ig_oas_bp", "hy_oas_bp"],
                             "y_log": True,
                             "y_title": "OAS (bp, log scale)",
                             "series_labels": {
                                 "ig_oas_bp": "IG",
                                 "hy_oas_bp": "HY"}}}}],
              ]},
        ]},
        "links": [
            # Polygon brush exercises a brush type the gallery
            # otherwise misses. Drag a freeform shape on the studio
            # scatter to filter the multi-axis chart to that subset.
            {"group": "studio_brush",
              "members": ["studio_chart", "macro_axes"],
              "brush": {"type": "polygon"}},
        ],
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1500, height=1500)
    return _result(r, thumb)


# =============================================================================
# DEMO: dev_workflow  (lifecycle / diagnostics / chart variants)
# =============================================================================
#
# Showcases the developer-facing surface that no other demo touches:
#   - `manifest_template` + `populate_template` (template-then-fill)
#   - `validate_manifest`           (structural validator output)
#   - `chart_data_diagnostics`      (data-binding lint output)
#   - `compile_dashboard(strict=False)` iteration mode (would-be errors
#     surface as warnings + `(no data)` placeholders)
#   - `save_pngs=True` per-widget PNG export
#   - chart `option` variant (raw ECharts option passthrough)
#   - chart `ref` variant (external JSON spec on disk)
#   - `header_actions` w/ `onclick` JS hook
#   - KPI direct `value` + direct `delta_pct` + `format="raw"`
#   - opt-out flags: `chart_zoom`, `chart_controls`, `table_controls`,
#     `kpi_controls`, `keep_title`


def _format_validate_errors(errs: List[str]) -> str:
    if not errs:
        return "*(none -- manifest is structurally valid)*"
    lines = ["| # | Path / message |", "|---|---|"]
    for i, e in enumerate(errs, 1):
        lines.append(f"| {i} | `{e}` |")
    return "\n".join(lines)


def _format_diagnostics(diags: List[Any]) -> str:
    if not diags:
        return "*(none -- no data-binding issues)*"
    lines = [
        "| Severity | Code | Widget | Message |",
        "|---|---|---|---|",
    ]
    for d in diags:
        sev = getattr(d, "severity", "?")
        code = getattr(d, "code", "?")
        wid = getattr(d, "widget_id", "") or "-"
        msg = getattr(d, "message", "")
        msg = msg.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {sev} | `{code}` | `{wid}` | {msg} |")
    return "\n".join(lines)


def build_dev_workflow(out_dir: Path) -> Dict[str, Any]:
    """Lifecycle / diagnostics / chart-variant showcase. Runs
    `validate_manifest`, `chart_data_diagnostics`, and the
    `manifest_template` / `populate_template` round-trip on
    deliberately-problematic manifests; renders the captured output
    into markdown widgets so the diagnostic surface is visible
    without having to read the console."""
    df_rates = pull_rates_panel()

    # 1. manifest_template / populate_template round-trip ---------------
    seed_manifest = {
        "schema_version": 1,
        "id": "dev_seed",
        "title": "Seed",
        "datasets": {"rates": df_rates},
        "layout": {"rows": [[
            {"widget": "chart", "id": "curve",
              "spec": {"chart_type": "multi_line", "dataset": "rates",
                        "mapping": {"x": "date",
                                     "y": ["us_2y", "us_10y"]}}}]]},
    }
    template = manifest_template(seed_manifest)
    template_columns = list(
        (template.get("datasets", {}).get("rates", {})
                  .get("source", []) or [[]])[0]
    )
    populated = populate_template(template, {"rates": df_rates})
    pop_entry = populated.get("datasets", {}).get("rates")
    # populate_template returns the DataFrame as-is; compile_dashboard
    # normalises DataFrames into list-of-lists at compile time.
    if hasattr(pop_entry, "shape"):
        populated_rows = int(pop_entry.shape[0])
    elif isinstance(pop_entry, dict):
        src = pop_entry.get("source", [])
        populated_rows = max(0, len(src) - 1)
    else:
        populated_rows = 0
    template_md = (
        "## `manifest_template` -> `populate_template`\n\n"
        f"**Step 1:** `manifest_template(seed)` strips data rows from "
        f"every dataset, keeping only the header row. The template's "
        f"`datasets.rates.source` now has 1 row (the header) with "
        f"columns: `{template_columns}`.\n\n"
        "Templates are pure JSON -- safe to persist alongside the "
        "compiled dashboard, diff in source control, hand-edit, and "
        "re-feed each refresh.\n\n"
        f"**Step 2:** `populate_template(template, {{'rates': "
        f"df_rates}})` re-injects fresh data. The populated "
        f"`datasets.rates` slot now holds a DataFrame with "
        f"**{populated_rows} rows**; `compile_dashboard` normalises "
        f"DataFrames to list-of-lists at compile time.\n\n"
        "Pass `require_all_slots=True` to fail loudly when the "
        "template declares a dataset slot the call doesn't fill."
    )

    # 2. validate_manifest on a deliberately broken manifest -----------
    bad_manifest = {
        "schema_version": 1,
        "id": "dev_broken",
        "title": "Deliberately broken",
        "datasets": {"rates": df_rates},
        "filters": [
            {"id": "x", "type": "select"},  # missing options
            {"id": "x", "type": "dateRange",  # duplicate id
              "default": "1Y", "field": "date"},
        ],
        "layout": {"rows": [[
            {"widget": "chart", "id": "c",  # ok
              "spec": {"chart_type": "multi_line",
                        "dataset": "missing_dataset",  # bad ref
                        "mapping": {"x": "date", "y": ["us_2y"]}}},
            {"widget": "chart", "id": "c",  # duplicate widget id
              "spec": {"chart_type": "frobnicator",  # bad type
                        "dataset": "rates",
                        "mapping": {"x": "date"}}},
        ]]},
    }
    ok, errs = validate_manifest(bad_manifest)
    validate_md = (
        "## `validate_manifest`\n\n"
        f"Status: **{'OK' if ok else 'FAILED'}** "
        f"-- {len(errs)} error(s).\n\n"
        "The validator checks structure (types, ids, references, "
        "required keys). It is the cheapest pass; PRISM should call "
        "it before compiling when iterating on a manifest.\n\n"
        + _format_validate_errors(errs)
    )

    # 3. chart_data_diagnostics on a borderline manifest ---------------
    df_empty = pd.DataFrame({"date": [], "us_10y": []})
    diag_manifest = {
        "schema_version": 1,
        "id": "dev_diag",
        "title": "Diagnostic surface",
        "datasets": {
            "rates": df_rates,
            "empty": df_empty,
        },
        "layout": {"rows": [[
            {"widget": "chart", "id": "good",
              "spec": {"chart_type": "multi_line", "dataset": "rates",
                        "mapping": {"x": "date",
                                     "y": ["us_2y", "us_10y"]}}},
            {"widget": "chart", "id": "empty_chart",
              "spec": {"chart_type": "line", "dataset": "empty",
                        "mapping": {"x": "date", "y": "us_10y"}}},
            {"widget": "chart", "id": "missing_col",
              "spec": {"chart_type": "line", "dataset": "rates",
                        "mapping": {"x": "date",
                                     "y": "us_99y"}}},
            {"widget": "kpi", "id": "k_typo",
              "label": "Bad KPI",
              "source": "rates.latest.us_99y"},
        ]]},
    }
    diags = chart_data_diagnostics(diag_manifest)
    diag_md = (
        "## `chart_data_diagnostics`\n\n"
        f"Returned **{len(diags)}** diagnostic(s) on a 4-widget "
        "manifest with one healthy chart + an empty dataset + a "
        "missing column + a KPI source typo. The diagnostic codes are "
        "stable -- pattern-match on `code` to drive automated "
        "repair.\n\n"
        + _format_diagnostics(diags)
    )

    # 4. compile_dashboard(strict=False) -- iteration mode --------------
    iter_md = (
        "## `compile_dashboard(strict=False)`\n\n"
        "Default mode (`strict=True`) raises `ValueError` listing "
        "every error-severity diagnostic before any HTML is "
        "produced. Refresh pipelines + CI rely on that contract -- a "
        "broken headline is a broken dashboard.\n\n"
        "Pass `strict=False` to keep going: errored charts get a "
        "`(no data)` placeholder, KPI tiles render `--`, and the "
        "full diagnostic list is returned on `result.diagnostics`. "
        "Useful inside an iterative LLM round-trip when you want to "
        "fix everything in one pass."
    )

    # 5. save_pngs (per-widget PNG export) ------------------------------
    pngs_md = (
        "## `compile_dashboard(save_pngs=True, png_scale=2)`\n\n"
        "Pass `save_pngs=True` to also drive headless Chrome over "
        "every chart widget after compile, writing one "
        "`{widget_id}.png` per chart into `<out>/{id}_pngs/`. PRISM "
        "ships these into report decks and report e-mails."
    )

    # 6. raw ECharts option for the `option` and `raw` chart variants ---
    raw_option_dict = {
        "title": {"text": "Hand-rolled option (passthrough)",
                   "left": "center"},
        "tooltip": {"trigger": "item"},
        "legend": {"orient": "vertical", "left": "left", "top": "bottom"},
        "series": [{
            "name": "Tier",
            "type": "pie",
            "radius": ["35%", "65%"],
            "data": [
                {"value": 35, "name": "Producer"},
                {"value": 28, "name": "Consumer"},
                {"value": 22, "name": "Refiner"},
                {"value": 15, "name": "Other"}],
        }],
    }
    # Persist a small ref JSON alongside the dashboard so the `ref`
    # variant exercises the file-loading path. Compiler resolves
    # paths relative to the loaded manifest's parent dir.
    ref_dir = out_dir / "echarts"
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_path = ref_dir / "ref_chart.json"
    ref_option_dict = {
        "chart_type": "raw",
        "option": {
            "title": {"text": "Loaded from echarts/ref_chart.json"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category",
                       "data": ["Q1", "Q2", "Q3", "Q4"]},
            "yAxis": {"type": "value", "name": "Score"},
            "series": [{"type": "bar", "name": "Score",
                          "data": [3, 5, 7, 9],
                          "itemStyle": {"color": "#002F6C"}}],
        },
    }
    ref_path.write_text(json.dumps(ref_option_dict, indent=2),
                          encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "id": "dev_workflow",
        "title": "Dev workflow & diagnostics",
        "description": ("Lifecycle showcase: manifest_template + "
                         "populate_template, validate_manifest, "
                         "chart_data_diagnostics, strict=False mode, "
                         "save_pngs=True, the three chart-widget "
                         "variants (spec / ref / option), the `raw` "
                         "chart_type, header_actions onclick, and the "
                         "controls-drawer opt-out flags."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "metadata": {
            "data_as_of": "2026-04-22T16:00:00Z",
            "generated_at": "2026-04-22T16:05:00Z",
            "sources": ["Synthetic"],
            "tags": ["developer", "diagnostics", "lifecycle"],
            "summary": (
                "Read the four sections in order: template -> "
                "validate -> diagnostics -> compile modes. The "
                "Variants and Knobs tabs document the chart-widget "
                "shapes and the per-tile opt-out flags."
            ),
            "methodology": (
                "Each markdown panel below was generated **at compile "
                "time** by calling the corresponding helper "
                "(`manifest_template`, `populate_template`, "
                "`validate_manifest`, `chart_data_diagnostics`) "
                "against an in-memory deliberately-imperfect "
                "manifest, formatting the result, and embedding it "
                "into a `widget: markdown` block. The `kerberos` + "
                "`dashboard_id` slots are left empty so the Refresh "
                "button stays hidden -- this dashboard documents "
                "the persistence story rather than participating in "
                "it."
            ),
            # Endpoint overrides demonstrate the override knobs even
            # though refresh is disabled (no kerberos set).
            "api_url": "/api/dev/refresh/",
            "status_url": "/api/dev/refresh/status/",
        },
        "header_actions": [
            {"label": "Run validator (console)",
              "onclick": "window.console.log('validator hook fired')",
              "icon": "\u2713",
              "title": "Hook for a JS-side validator wired by host"},
            {"label": "Open repo",
              "href": "https://example.com/dev-workflow",
              "primary": False,
              "title": "Linkout"},
        ],
        "datasets": {
            "rates": df_rates,
        },
        "layout": {"kind": "tabs", "cols": 12, "tabs": [
            # --- Tab 1: Template + populate ----------------------------
            {"id": "lifecycle", "label": "Template + populate",
              "description": ("Strip data -> persistent JSON -> "
                                "re-fill on each refresh."),
              "rows": [
                  [{"widget": "markdown", "id": "md_template",
                     "w": 12, "content": template_md}],
              ]},
            # --- Tab 2: Validate -------------------------------------
            {"id": "validate", "label": "validate_manifest",
              "description": ("Structural validator output on a "
                                "deliberately-broken manifest."),
              "rows": [
                  [{"widget": "markdown", "id": "md_validate",
                     "w": 12, "content": validate_md}],
              ]},
            # --- Tab 3: Diagnostics ----------------------------------
            {"id": "diagnostics", "label": "chart_data_diagnostics",
              "description": ("Data-binding lint output: empty "
                                "datasets, missing columns, KPI "
                                "source typos."),
              "rows": [
                  [{"widget": "markdown", "id": "md_diagnostics",
                     "w": 12, "content": diag_md}],
                  [{"widget": "markdown", "id": "md_iter",
                     "w": 6, "content": iter_md},
                   {"widget": "markdown", "id": "md_pngs",
                     "w": 6, "content": pngs_md}],
              ]},
            # --- Tab 4: Chart variants (spec / option / ref / raw) ----
            {"id": "variants", "label": "Chart variants",
              "description": ("Three ways to declare a chart "
                                "widget: `spec`, `option`, `ref`."),
              "rows": [
                  [
                      # Standard `spec` variant -- the LLM-friendly path.
                      {"widget": "chart", "id": "v_spec",
                        "w": 6, "h_px": 320,
                        "title": "Variant 1: spec",
                        "subtitle": ("chart_type + dataset + "
                                       "mapping. PRISM-preferred."),
                        "spec": {
                            "chart_type": "multi_line",
                            "dataset": "rates",
                            "mapping": {"x": "date",
                                         "y": ["us_2y", "us_10y"],
                                         "y_title": "Yield (%)"}}},
                      # Raw passthrough via top-level `option`.
                      {"widget": "chart", "id": "v_option",
                        "w": 6, "h_px": 320,
                        "title": "Variant 2: option",
                        "subtitle": ("Hand-rolled ECharts option "
                                       "dict on the widget."),
                        "option": raw_option_dict},
                  ],
                  [
                      # Reference path -- spec read from external JSON.
                      {"widget": "chart", "id": "v_ref",
                        "w": 12, "h_px": 320,
                        "title": "Variant 3: ref",
                        "subtitle": ("Spec loaded from "
                                       "echarts/ref_chart.json. "
                                       "The compiler resolves paths "
                                       "relative to the manifest's "
                                       "parent directory."),
                        "ref": "echarts/ref_chart.json"},
                  ],
                  [
                      # Markdown summarising the three variants.
                      {"widget": "markdown", "id": "md_variants",
                        "w": 12,
                        "content": (
                            "## Three chart-widget variants\n\n"
                            "| Variant | When | Use |\n"
                            "|---|---|---|\n"
                            "| `spec` | Standard, LLM-friendly | "
                            "chart_type + dataset + mapping; data "
                            "lives in manifest. **PRISM-preferred.** |\n"
                            "| `option` | Raw passthrough | Hand-"
                            "crafted ECharts option dict on the "
                            "widget; bypasses the builder. Useful "
                            "for one-off chart types not in the "
                            "VALID_CHART_TYPES set. |\n"
                            "| `ref` | External JSON | File path "
                            "(string) to a pre-emitted spec. "
                            "Resolved relative to the manifest "
                            "directory. |\n\n"
                            "All three render through the same "
                            "tile chrome (title, subtitle, info, "
                            "popup, action_buttons, controls "
                            "drawer). The `option` and `ref` "
                            "variants skip the builder dispatch "
                            "and the `chart_type` validator -- "
                            "they're for cases when the "
                            "VALID_CHART_TYPES set doesn't fit."
                        )},
                  ],
              ]},
            # --- Tab 5: Knob opt-outs -------------------------------
            {"id": "knobs", "label": "Knob opt-outs",
              "description": ("KPI value override + format=raw + "
                                "controls-drawer opt-out flags + "
                                "header_actions onclick."),
              "rows": [
                  [
                      # KPI direct value (no dotted source) +
                      # format=raw so the runtime doesn't insert
                      # commas / abbreviations.
                      {"widget": "kpi", "id": "kv_direct", "w": 3,
                        "label": "Direct value",
                        "value": 12345.6789,
                        "format": "raw",
                        "kpi_controls": False,
                        "info": ("KPI with `value=` direct override "
                                  "(no dotted source) and "
                                  "`format='raw'` -- runtime "
                                  "displays the number unmodified.")},
                      # KPI direct value + direct delta_pct.
                      {"widget": "kpi", "id": "kv_delta", "w": 3,
                        "label": "Direct delta_pct",
                        "value": 4.55,
                        "delta_pct": 0.32,
                        "delta_label": "vs 4.50",
                        "suffix": "%",
                        "info": ("`delta_pct` set directly without "
                                  "a delta_source.")},
                      # KPI compact format.
                      {"widget": "kpi", "id": "kv_compact", "w": 3,
                        "label": "format='compact'",
                        "value": 2820000.0,
                        "format": "compact",
                        "info": "2.82M via compact formatter."},
                      # KPI comma format.
                      {"widget": "kpi", "id": "kv_comma", "w": 3,
                        "label": "format='comma'",
                        "value": 2820,
                        "format": "comma",
                        "info": "2,820 via comma formatter."},
                  ],
                  [
                      # Sparkline-style chart with controls drawer
                      # AND zoom slider suppressed.
                      {"widget": "chart", "id": "no_controls",
                        "w": 6, "h_px": 200,
                        "title": "chart_zoom + chart_controls = false",
                        "subtitle": ("Slider + controls drawer "
                                       "suppressed for tight tile."),
                        "spec": {
                            "chart_type": "line", "dataset": "rates",
                            "mapping": {"x": "date", "y": "us_10y",
                                         "y_title": "10Y"},
                            "chart_zoom": False,
                            "chart_controls": False}},
                      # Chart with `keep_title=True` so internal title
                      # stays alongside the tile title.
                      {"widget": "chart", "id": "keep_title", "w": 6,
                        "h_px": 200,
                        "title": "keep_title=True",
                        "subtitle": ("Spec keeps its own internal "
                                       "title."),
                        "spec": {
                            "chart_type": "line", "dataset": "rates",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "Internal title (kept)",
                            "keep_title": True}},
                  ],
                  [
                      # Static table widget with controls drawer
                      # disabled. Compact reference view of the rates
                      # dataset.
                      {"widget": "table", "id": "tbl_static",
                        "w": 12,
                        "title": "table_controls = false",
                        "subtitle": ("Static reference table; the "
                                       "controls drawer is "
                                       "suppressed."),
                        "dataset_ref": "rates",
                        "table_controls": False,
                        "max_rows": 10,
                        "row_height": "compact",
                        "searchable": False,
                        "sortable": False,
                        "downloadable": False,
                        "columns": [
                            {"field": "date", "label": "Date"},
                            {"field": "us_2y", "label": "2Y",
                              "format": "number:3"},
                            {"field": "us_5y", "label": "5Y",
                              "format": "number:3"},
                            {"field": "us_10y", "label": "10Y",
                              "format": "number:3"},
                            {"field": "us_30y", "label": "30Y",
                              "format": "number:3"},
                        ]},
                  ],
                  [
                      # Markdown summarising what the runtime now does
                      # differently because of the opt-out flags.
                      {"widget": "markdown", "id": "md_optouts",
                        "w": 12,
                        "content": (
                            "## Per-tile opt-outs\n\n"
                            "* `chart_zoom: False` -- suppresses the "
                            "auto-injected dataZoom slider on time "
                            "axes (use for sparkline-sized tiles).\n"
                            "* `chart_controls: False` -- hides the "
                            "`\u22EE` controls drawer button.\n"
                            "* `table_controls: False` -- same, for "
                            "table widgets.\n"
                            "* `kpi_controls: False` -- same, for "
                            "KPI widgets (set on the KPI above).\n"
                            "* `keep_title: True` -- prevents the "
                            "compiler from auto-stripping the "
                            "ECharts internal title (the tile chrome "
                            "normally renders the title above)."
                        )},
                  ],
              ]},
        ]},
        "links": [],
    }

    # `save_pngs=True` exercised at compile time so the artifact
    # folder includes a `<id>_pngs/` directory the gallery can point
    # at. PNG generation requires Chrome; if unavailable, the call
    # still produces HTML / JSON.
    r = compile_dashboard(
        manifest,
        output_path=str(out_dir / "dashboard.html"),
        save_pngs=True,
        png_scale=1,
    )
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1500, height=1500)
    return _result(r, thumb)


# =============================================================================
# DEMO REGISTRY + SHARED HELPERS
# =============================================================================

DEMO_REGISTRY: Dict[str, Dict[str, Any]] = {
    "rates_monitor": {
        "title": "Rates monitor (US + global CB)",
        "description": ("8-tab rates monitor: US curve overview / curve "
                         "detail (brush) / macro overlay (dual-axis ISM) "
                         "plus 5 identical-shape tabs for Fed / ECB / "
                         "BoE / BoJ / EM with KPI + policy-rate line + "
                         "cut-prob gauge + decisions bar. Stress-tests "
                         "high-tab-count layouts."),
        "kind": "dashboard",
        "build": build_rates_monitor,
    },
    "risk_regime": {
        "title": "Risk regime monitor",
        "description": ("Cross-asset correlation_matrix on % changes "
                         "(dedicated builder), VIX term structure "
                         "across regimes, factor scatter_multi vs MKT "
                         "with per-group OLS, factor boxplots, running "
                         "drawdown with arrow / band annotations and "
                         "lineX brush cross-filter."),
        "kind": "dashboard",
        "build": build_risk_regime,
    },
    "fomc_monitor": {
        "title": "FOMC policy monitor",
        "description": ("Fed policy: probability gauge, FFR futures "
                         "candlestick, dot plot vs realized (strokeDash), "
                         "voter hawk/dove radar, decision calendar "
                         "heatmap, dual-axis rates chart. Metadata + "
                         "header_actions."),
        "kind": "dashboard",
        "build": build_fomc_monitor,
    },
    "global_flows": {
        "title": "Global flows & allocation",
        "description": ("Cross-border trade sankey + outbound donut, "
                         "treemap + sunburst allocation, counterparty "
                         "graph network + hierarchical tree, mandate "
                         "funnel, stat_grid."),
        "kind": "dashboard",
        "build": build_global_flows,
    },
    "equity_deep_dive": {
        "title": "Equity deep dive",
        "description": ("Single-name tear sheet: candlestick + volume, "
                         "EPS actuals vs consensus (strokeDash), analyst "
                         "bar_horizontal, beta scatter-trendline, return "
                         "histogram, valuation bullet, KPI info/popup, "
                         "header_actions, refresh metadata."),
        "kind": "dashboard",
        "build": build_equity_deep_dive,
    },
    "portfolio_analytics": {
        "title": "Portfolio analytics",
        "description": ("Multi-asset portfolio: pinned KPI ribbon, "
                         "VaR gauge, factor radar, allocation pie, "
                         "stacked-area P&L, parallel-coords "
                         "positions, return-distribution histogram, "
                         "stat_grid, lineY brush."),
        "kind": "dashboard",
        "build": build_portfolio_analytics,
    },
    "markets_wrap": {
        "title": "Cross-asset end-of-day wrap",
        "description": ("One big scrollable cross-asset wrap: image "
                         "banner, KPI ribbon, equities / rates / FX / "
                         "commodities sections separated by dividers, "
                         "dual-axis + bar_horizontal charts, click-"
                         "emit-filter, top-movers table with z-score "
                         "colour scale. Stress-tests layout with 17 "
                         "charts. Filter `fx_*` / `cm_*` wildcard "
                         "prefixes and `legend` sync across the "
                         "asset-class panels."),
        "kind": "dashboard",
        "build": build_markets_wrap,
    },
    "screener_studio": {
        "title": "Screener studio (tables / filters / drill-down)",
        "description": ("Three-tab toolbox. Tab 1: RV screen with "
                         "conditional formatting + z-score colour scale "
                         "+ drill-down time-series. Tab 2: all 9 filter "
                         "types on one dataset. Tab 3: bond universe "
                         "with row_click.detail rich-modal (stats / "
                         "markdown / charts / sub-table sections)."),
        "kind": "dashboard",
        "build": build_screener_studio,
    },
    "bond_carry_roll": {
        "title": "Bond carry & roll (chart click_popup)",
        "description": ("Click any point on the carry/roll scatter "
                         "to open a per-bond modal: stats, issuer "
                         "blurb, spread + price history filtered to "
                         "that CUSIP, and recent events. Plus simple-"
                         "mode click popups on a top-10 bar and a "
                         "sector summary chart."),
        "kind": "dashboard",
        "build": build_bond_carry_roll,
    },
    "news_wrap": {
        "title": "News desk (intraday market wrap)",
        "description": ("Text-heavy news desk dashboard: summary "
                         "banner, six semantic note kinds, sortable "
                         "headlines table with full-body markdown "
                         "drilldown, per-asset commentary + intraday "
                         "sparklines, calendar + reading list. "
                         "Stress-tests the prose surfaces."),
        "kind": "dashboard",
        "build": build_news_wrap,
    },
    "fomc_brief": {
        "title": "FOMC document brief",
        "description": ("Document-first dashboard: statement diff "
                         "with prose narrative, minutes excerpts "
                         "(blockquotes by topic), recent speakers "
                         "table + hawk-dove bar chart with "
                         "row-click verbatim quote modal, dot plot "
                         "panel with desk commentary."),
        "kind": "dashboard",
        "build": build_fomc_brief,
    },
    "research_feed": {
        "title": "Research feed (Substack-style aggregator)",
        "description": ("Reading-list-meets-aggregator: featured "
                         "article note up top, curator commentary "
                         "across themes, full article feed with "
                         "row-click drilldown rendering each piece's "
                         "full markdown body in a side panel."),
        "kind": "dashboard",
        "build": build_research_feed,
    },
    "macro_studio": {
        "title": "Macro studio (interactive bivariate)",
        "description": ("scatter_studio centerpiece: pick X / Y / "
                         "color / size from author whitelists, "
                         "per-axis transforms, OLS regression, stats "
                         "strip. Plus correlation_matrix sidebar, "
                         "4-axis macro overlay (mapping.axes), "
                         "log-scale credit chart, polygon brush."),
        "kind": "dashboard",
        "build": build_macro_studio,
    },
    "dev_workflow": {
        "title": "Dev workflow & diagnostics",
        "description": ("Lifecycle showcase: manifest_template + "
                         "populate_template, validate_manifest, "
                         "chart_data_diagnostics, strict=False mode, "
                         "save_pngs=True. Three chart-widget "
                         "variants (spec / option / ref). KPI direct "
                         "value + format=raw + controls-drawer "
                         "opt-out flags. header_actions onclick."),
        "kind": "dashboard",
        "build": build_dev_workflow,
    },
}


def _thumbnail(html_path: str, png_path: Path, *,
                width: int, height: int) -> Optional[Path]:
    """Render a dashboard HTML to PNG, returning None on failure with a
    warning printed (Chrome may be unavailable)."""
    try:
        save_dashboard_html_png(html_path, png_path,
                                 width=width, height=height, scale=1)
        return png_path
    except Exception as e:
        print(f"  [warn] thumbnail render failed: {e}")
        return None


def _result(r: Any, thumb: Optional[Path]) -> Dict[str, Any]:
    return {
        "html": r.html_path,
        "png": str(thumb) if thumb else None,
        "manifest": r.manifest_path,
        "success": r.success,
        "warnings": r.warnings,
    }


# =============================================================================
# GALLERY BUILDER
# =============================================================================

def _gallery_html(results: List[Dict[str, Any]], out_root: Path) -> str:
    """GS-branded gallery page embedding PNGs + links to interactive HTML."""
    gen = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _rel(p: Optional[str]) -> Optional[str]:
        if not p:
            return None
        try:
            return str(Path(p).resolve().relative_to(out_root.resolve()))
        except ValueError:
            return str(Path(p).resolve())

    cards = "\n".join(_card({
        "title": r.get("title", ""),
        "description": r.get("description", ""),
        "kind": r.get("kind", ""),
        "html": _rel(r.get("html")),
        "png": _rel(r.get("png")),
        "manifest": _rel(r.get("manifest")),
        "module": r.get("name", ""),
        "elapsed_s": r.get("elapsed_s", 0),
        "success": r.get("success", True),
    }) for r in results)

    ok_count = sum(1 for r in results if r.get("success"))
    total = len(results)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>GS echarts demo gallery</title>
<style>
  html, body {{ margin:0; padding:0; background:#f5f6fa;
                 font-family: -apple-system, "Segoe UI", Roboto,
                               Helvetica, Arial, sans-serif;
                 color:#2d3748; }}
  header {{ background:#1a365d; color:white; padding:18px 28px;
             display:flex; justify-content:space-between; align-items:center; }}
  header .brand {{ display:flex; align-items:center; gap:14px; }}
  header .brand .logo {{ background:#002f6c; color:white;
                           padding:4px 8px; border-radius:3px;
                           font-weight:700; font-size:14px; letter-spacing:0.8px; }}
  header h1 {{ font-size:22px; margin:0; font-weight:600; }}
  header .meta {{ font-size:12px; opacity:0.85; }}
  .wrap {{ padding:22px 28px 64px; }}
  .summary {{ display:flex; gap:18px; margin-bottom:22px;
                font-size:13px; color:#2d3748; }}
  .summary .pill {{ background:white; border:1px solid #e2e8f0;
                      border-radius:999px; padding:6px 14px; }}
  .grid {{ display:grid;
             grid-template-columns: repeat(auto-fill, minmax(520px, 1fr));
             gap: 18px; }}
  .card {{ background:white; border:1px solid #e2e8f0; border-radius:10px;
            box-shadow:0 1px 3px rgba(0,0,0,0.04); overflow:hidden;
            display:flex; flex-direction:column; }}
  .card .head {{ padding:14px 18px; border-bottom:1px solid #edf2f7;
                   display:flex; justify-content:space-between;
                   align-items:center; gap:12px; }}
  .card .head h2 {{ font-size:15px; margin:0; font-weight:600;
                      color:#1a365d; }}
  .card .head .kind {{ background:#edf2f7; color:#2d3748;
                         padding:3px 10px; border-radius:999px;
                         font-size:11px; font-weight:500; }}
  .card .body {{ padding:0; }}
  .card .body img {{ width:100%; display:block; background:#fafbfd;
                       border-bottom:1px solid #edf2f7; }}
  .card .desc {{ padding:12px 18px; font-size:12px; color:#4a5568;
                   line-height:1.55; min-height:38px; }}
  .card .actions {{ padding:10px 18px 16px; display:flex; gap:8px;
                      flex-wrap:wrap; font-size:12px; }}
  .card .actions a {{ text-decoration:none; color:white;
                        background:#3182ce; padding:6px 12px;
                        border-radius:6px; font-weight:500; }}
  .card .actions a:hover {{ background:#2c5282; }}
  .card .actions a.secondary {{ background:#e2e8f0; color:#2d3748; }}
  .card .actions a.secondary:hover {{ background:#cbd5e0; }}
  .card .actions .mod {{ margin-left:auto; color:#718096; font-size:11px;
                           align-self:center; }}
  .missing {{ background:#fff5f5; color:#c53030; padding:20px; text-align:center;
                font-size:12px; }}
  footer {{ text-align:center; color:#a0aec0; font-size:11px;
              padding:30px; }}
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="logo">GS</span>
    <h1>Charts &amp; Dashboards Demo Gallery</h1>
  </div>
  <div class="meta">generated {gen} &middot; {ok_count}/{total} demos succeeded</div>
</header>
<div class="wrap">
  <div class="summary">
    <div class="pill">Engine: ECharts (ai_development/dashboards)</div>
    <div class="pill">Theme: gs_clean</div>
    <div class="pill">Palettes: gs_primary / gs_blues / gs_diverging</div>
    <div class="pill">{total} demos / {ok_count} OK</div>
  </div>
  <div class="grid">
{cards}
  </div>
</div>
<footer>
  ai_development/dashboards demos &middot; run via <code>python demos.py --all</code>
</footer>
</body>
</html>
"""


def _card(r: Dict[str, Any]) -> str:
    title = r.get("title", "")
    desc = r.get("description", "")
    kind = r.get("kind", "chart")
    html = r.get("html")
    png = r.get("png")
    mod = r.get("module", "")
    elapsed = r.get("elapsed_s", 0)
    ok = r.get("success", True)

    img_block = (
        f'<img src="{png}" alt="{title}"/>'
        if png
        else '<div class="missing">PNG not generated (Chrome unavailable?)</div>'
    )
    actions = []
    if html:
        actions.append(f'<a href="{html}" target="_blank">Open interactive</a>')
    if png:
        actions.append(
            f'<a class="secondary" href="{png}" target="_blank">PNG</a>')
    manifest = r.get("manifest")
    if manifest:
        actions.append(
            f'<a class="secondary" href="{manifest}" target="_blank">'
            f'JSON manifest</a>')

    status_badge = "" if ok else '<span style="color:#c53030">FAILED</span> '
    return f"""
    <div class="card">
      <div class="head">
        <h2>{status_badge}{title}</h2>
        <span class="kind">{kind}</span>
      </div>
      <div class="body">{img_block}</div>
      <div class="desc">{desc}</div>
      <div class="actions">
        {"".join(actions)}
        <span class="mod">{mod} &middot; {elapsed}s</span>
      </div>
    </div>"""


# =============================================================================
# RUNNER
# =============================================================================

def _heartbeat(label: str, start: float, last: List[float]) -> None:
    now = time.time()
    if now - last[0] >= 5.0:
        print(f"  ... {label} ({int(now - start)}s elapsed)")
        last[0] = now


def run(out_root: Path, names: List[str], do_open: bool = False) -> int:
    print(f"[demos] output root: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    start_all = time.time()
    last = [start_all]
    results: List[Dict[str, Any]] = []

    for name in names:
        if name not in DEMO_REGISTRY:
            print(f"  unknown demo: {name}")
            continue
        entry = DEMO_REGISTRY[name]
        print(f"\n[demos] {name}")
        out_dir = out_root / name
        out_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        last[0] = t0
        try:
            r = entry["build"](out_dir)
            r.setdefault("title", entry["title"])
            r.setdefault("description", entry["description"])
            r.setdefault("kind", entry["kind"])
            r["name"] = name
            r["elapsed_s"] = round(time.time() - t0, 2)
            results.append(r)
            print(f"  ok  in {r['elapsed_s']}s  -> {out_dir}")
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            results.append({
                "name": name, "title": entry["title"],
                "description": entry["description"],
                "kind": "error", "success": False,
                "elapsed_s": round(time.time() - t0, 2),
                "error": str(e),
            })
        _heartbeat(f"running {name}", start_all, last)

    gallery_path = out_root / "gallery.html"
    gallery_path.write_text(
        _gallery_html(results, out_root), encoding="utf-8"
    )
    (out_root / "index.json").write_text(
        json.dumps([{k: v for k, v in r.items()} for r in results],
                    indent=2, default=str),
        encoding="utf-8",
    )

    print("\n" + "=" * 70)
    print(f"[demos] DONE in {int(time.time() - start_all)}s")
    print(f"  gallery: {gallery_path}")
    ok = sum(1 for r in results if r.get("success"))
    print(f"  {ok}/{len(results)} demos succeeded")
    if do_open:
        webbrowser.open(f"file://{gallery_path.resolve()}")
    return 0 if ok == len(results) else 1


# =============================================================================
# CLI
# =============================================================================

def _interactive() -> int:
    names = list(DEMO_REGISTRY.keys())
    print("\nGS echarts demo runner")
    print("=" * 60)
    for i, n in enumerate(names, 1):
        entry = DEMO_REGISTRY[n]
        print(f"  {i:2d}. {n:20s} [{entry['kind']:9s}] {entry['title']}")
    print(f"  {len(names) + 1:2d}. all")
    print(f"  {len(names) + 2:2d}. quit")
    raw = input("\nselect: ").strip()
    if not raw or raw == str(len(names) + 2) or raw.lower() in ("q", "quit"):
        return 0
    out_root = _here / "output" / datetime.now().strftime("%Y%m%d_%H%M%S")
    if raw == str(len(names) + 1) or raw.lower() == "all":
        return run(out_root, names, do_open=True)
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(names):
            return run(out_root, [names[idx]], do_open=True)
    except ValueError:
        if raw in DEMO_REGISTRY:
            return run(out_root, [raw], do_open=True)
    print(f"  invalid: {raw}")
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run GS echarts demo scenarios and build a gallery."
    )
    parser.add_argument("--all", action="store_true",
                          help="run every demo")
    parser.add_argument("--demo", action="append", default=[],
                          help="demo name to run (repeatable); "
                               f"valid: {sorted(DEMO_REGISTRY.keys())}")
    parser.add_argument("--out", default=None,
                          help="output directory (default: output/<timestamp>)")
    parser.add_argument("--open", action="store_true",
                          help="auto-open gallery in browser")
    parser.add_argument("--list", action="store_true",
                          help="list demos and exit")

    args = parser.parse_args(argv)

    if args.list:
        for name, entry in DEMO_REGISTRY.items():
            print(f"{name:20s}  [{entry['kind']}]  {entry['title']}")
        return 0

    out_root = (Path(args.out) if args.out
                 else _here / "output" / datetime.now().strftime("%Y%m%d_%H%M%S"))

    if args.demo:
        picked = [d for d in args.demo if d in DEMO_REGISTRY]
        unknown = [d for d in args.demo if d not in DEMO_REGISTRY]
        for u in unknown:
            print(f"  unknown demo: {u}  (valid: "
                  f"{sorted(DEMO_REGISTRY.keys())})")
        if not picked:
            return 1
        return run(out_root, picked, do_open=args.open)

    if args.all:
        return run(out_root, list(DEMO_REGISTRY.keys()), do_open=args.open)

    return _interactive()


if __name__ == "__main__":
    sys.exit(main())
