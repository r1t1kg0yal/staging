#!/usr/bin/env python3
"""
demos -- tight MECE demo set for GS/viz/echarts.

Nine end-to-end scenarios, each with a distinct narrative and
non-overlapping dominant feature. Every chart type, widget, filter
type, and link mechanism in the stack is exercised at least once
across the gallery.

    rates_monitor       Full rates monitor: US curve (overview / detail /
                        macro-overlay tabs w/ brush cross-filter + dual-
                        axis) PLUS 5 identical-shape global central-bank
                        tabs (Fed / ECB / BoE / BoJ / EM). Stress-tests
                        high-tab-count layouts.
    cross_asset         Four-panel composite PNG (SPX/DXY/WTI/Gold) via
                        make_4pack_grid -- the only non-manifest path in
                        the gallery.
    risk_regime         Correlation heatmap, VIX term by regime, factor-
                        return boxplots, running drawdown with band.
    fomc_monitor        Fed policy dashboard: gauge (cut prob), candlestick
                        (FFR futures), radar (voter hawk-dove), calendar
                        heatmap (decision history), strokeDash (actuals
                        vs dots), dual-axis, metadata, header_actions.
    global_flows        Cross-border flows: sankey + donut, treemap +
                        sunburst, network graph, funnel, stat_grid.
    equity_deep_dive    Single-name equity: candlestick + volume, earnings
                        strokeDash, analyst bar_horizontal, scatter-
                        trendline beta, bullet valuation, histogram
                        returns, KPI info/popup, header_actions.
    portfolio_analytics Multi-asset book: gauge (VaR), factor radar, pie
                        allocation, stacked-area P&L, parallel_coords
                        positions, histogram returns, stat_grid.
    markets_wrap        Cross-asset end-of-day wrap -- 17-chart scrollable
                        stress-test of the layout engine with click-emit
                        filter, conditional table, metadata refresh.
    screener_studio     Three-tab table/filter/drill-down toolbox: rich
                        RV screen w/ conditional formatting + z-score
                        colors, all 9 filter types on one dataset, bond
                        universe screener with row_click.detail modal
                        (stats / markdown / charts / sub-table sections).

All data is synthetic and deterministic (SEED-controlled). Every demo
follows the PRISM pattern: pull DataFrame(s), drop into a manifest, call
compile_dashboard() or a composite. Literal numbers never appear in the
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

from echart_dashboard import compile_dashboard
from composites import ChartSpec, make_4pack_grid
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
        },
        "datasets": datasets,
        "filters": [
            {"id": "dt_us", "type": "dateRange", "default": "1Y",
              "targets": ["curve", "spread", "two_ten",
                           "fives30s", "real10y", "ism_10y"],
              "field": "date", "label": "US lookback"},
            {"id": "dt_cb", "type": "dateRange", "default": "2Y",
              "targets": ["chart_rate_fed", "chart_rate_ecb",
                           "chart_rate_boe", "chart_rate_boj",
                           "chart_rate_em"],
              "scope": "global",
              "field": "date", "label": "Global CB lookback"},
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
                      "delta_source": "rates.us_2y",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "k10y", "label": "10Y yield",
                      "source": "rates.latest.us_10y",
                      "sparkline_source": "rates.us_10y",
                      "delta_source": "rates.us_10y",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "k30y", "label": "30Y yield",
                      "source": "rates.latest.us_30y",
                      "sparkline_source": "rates.us_30y",
                      "delta_source": "rates.us_30y",
                      "suffix": "%", "decimals": 2, "w": 3},
                    {"widget": "kpi", "id": "kspr", "label": "2s10s (bp)",
                      "source": "rates.latest.2s10s",
                      "sparkline_source": "rates.2s10s",
                      "delta_source": "rates.2s10s",
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
                      "content": ("### Method\n"
                                    "Synthetic UST panel. Brush the "
                                    "curve on the Overview tab to "
                                    "filter the spread chart by date "
                                    "range.")},
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


def build_cross_asset(out_dir: Path) -> Dict[str, Any]:
    """Four-panel composite (SPX/DXY/WTI/Gold) with event annotations.
    Emits a single HTML + PNG artifact via make_4pack_grid."""
    df = pull_cross_asset()
    r = make_4pack_grid(
        ChartSpec(df=df, chart_type="line",
                    mapping={"x": "date", "y": "spx", "y_title": "SPX"},
                    title="S&P 500",
                    annotations=[{
                        "type": "vline", "x": "2026-01-15",
                        "label": "FY guidance",
                        "color": "#1a365d", "style": "dashed"}]),
        ChartSpec(df=df, chart_type="line",
                    mapping={"x": "date", "y": "dxy", "y_title": "DXY"},
                    title="US Dollar index"),
        ChartSpec(df=df, chart_type="line",
                    mapping={"x": "date", "y": "wti",
                              "y_title": "WTI ($/bbl)"},
                    title="WTI crude",
                    annotations=[{
                        "type": "band", "y1": 75, "y2": 85,
                        "label": "Fair-value band",
                        "color": "#7399C6", "opacity": 0.18}]),
        ChartSpec(df=df, chart_type="line",
                    mapping={"x": "date", "y": "gold",
                              "y_title": "Gold ($/oz)"},
                    title="Gold",
                    annotations=[{
                        "type": "point", "x": "2026-04-01", "y": 2500,
                        "label": "All-time high",
                        "color": "#dd6b20"}]),
        title="Cross-asset snapshot",
        subtitle="1Y daily close, synthetic",
        session_path=str(out_dir),
        chart_name="composite",
    )
    png_path: Optional[Path] = out_dir / "composite.png"
    try:
        r.save_png(png_path, width=1400, height=800, scale=2)
    except Exception as e:
        print(f"  [warn] PNG render failed: {e}")
        png_path = Path(r.png_path) if r.png_path else None
    return {
        "title": "Cross-asset snapshot",
        "description": ("Four major asset classes in one conversational "
                         "composite (SPX, DXY, WTI, Gold) with event "
                         "annotations."),
        "kind": "composite",
        "html": r.html_path,
        "png": str(png_path) if png_path else None,
        "manifest": None,
        "success": r.success, "warnings": r.warnings,
    }


def build_risk_regime(out_dir: Path) -> Dict[str, Any]:
    """Risk regime monitor: cross-asset correlation heatmap, VIX term
    structure by regime, factor-return boxplots, running drawdown."""
    df_corr = pull_correlation_matrix()
    df_vix = pull_vix_term()
    df_fac = pull_factor_returns()
    df_dd = pull_drawdown()

    manifest = {
        "schema_version": 1,
        "id": "risk_regime",
        "title": "Risk regime monitor",
        "description": ("Cross-asset correlation heatmap, VIX term "
                         "structure across regimes, factor-return "
                         "distributions, and running drawdown."),
        "theme": "gs_clean",
        "datasets": {
            "corr": df_corr, "vix_term": df_vix,
            "factors": df_fac, "drawdown": df_dd,
        },
        "layout": {"rows": [
            [
                {"widget": "chart", "id": "corr", "w": 6, "h_px": 420,
                  "spec": {
                      "chart_type": "heatmap", "dataset": "corr",
                      "mapping": {"x": "a", "y": "b", "value": "corr"},
                      "title": "Rolling 6M cross-asset correlation",
                      "palette": "gs_diverging"}},
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
                {"widget": "chart", "id": "drawdown", "w": 6, "h_px": 380,
                  "spec": {
                      "chart_type": "line", "dataset": "drawdown",
                      "mapping": {"x": "date", "y": "drawdown_pct",
                                    "y_title": "Drawdown (%)"},
                      "title": "Running drawdown",
                      "annotations": [
                          {"type": "band", "y1": -20, "y2": -100,
                            "label": "Bear-market zone",
                            "color": "#c53030", "opacity": 0.08},
                      ]}},
            ],
        ]},
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1500, height=1100)
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
            {"id": "dt", "type": "dateRange", "default": "1Y",
              "targets": ["ffr_chart", "fut_chart"],
              "field": "date", "label": "Lookback"},
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


def build_global_flows(out_dir: Path) -> Dict[str, Any]:
    """Global flows dashboard: sankey + donut + treemap + sunburst + graph
    + funnel + stat_grid."""
    df_flows = _pull_global_trade_flows()
    df_share = _pull_global_outbound_share()
    df_tree = _pull_global_asset_treemap()
    df_funnel = _pull_global_aum_funnel()
    df_net = _pull_global_bank_network()
    total = int(df_flows["v"].sum())
    largest_bil = int(df_flows["v"].max())

    manifest = {
        "schema_version": 1,
        "id": "global_flows",
        "title": "Global flows & allocation",
        "description": ("Cross-border trade flows, asset-class "
                         "allocation, counterparty network, mandate "
                         "conversion funnel."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "datasets": {
            "flows":  df_flows,
            "share":  df_share,
            "tree":   df_tree,
            "funnel": df_funnel,
            "net":    df_net,
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
                               "graph."),
              "rows": [
                [
                    {"widget": "chart", "id": "net_graph",
                      "w": 12, "h_px": 520,
                      "spec": {
                          "chart_type": "graph", "dataset": "net",
                          "mapping": {"source": "src",
                                        "target": "tgt",
                                        "value": "v",
                                        "node_category": "category"},
                          "title": ("Counterparty exposure network "
                                      "(drag nodes)")}},
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
            {"id": "dt", "type": "dateRange", "default": "1Y",
              "targets": ["price_chart", "vol_chart"],
              "field": "date", "label": "Price lookback"},
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
                {"widget": "kpi", "id": "k_aum", "label": "AUM",
                  "source": "kpi.latest.aum_mm",
                  "delta_source": "kpi.prev.aum_mm",
                  "sparkline_source": "kpi.aum_mm",
                  "suffix": " mm", "decimals": 0, "w": 3},
                {"widget": "kpi", "id": "k_pnl", "label": "MTD P&L",
                  "source": "kpi.latest.pnl_mtd_mm",
                  "delta_source": "kpi.prev.pnl_mtd_mm",
                  "sparkline_source": "kpi.pnl_mtd_mm",
                  "prefix": "$", "suffix": " mm",
                  "decimals": 2, "w": 3},
                {"widget": "kpi", "id": "k_sh", "label": "Sharpe",
                  "source": "kpi.latest.sharpe",
                  "delta_source": "kpi.prev.sharpe",
                  "sparkline_source": "kpi.sharpe",
                  "decimals": 2, "w": 3},
                {"widget": "kpi", "id": "k_var", "label": "1D 99% VaR",
                  "source": "kpi.latest.var_mm",
                  "delta_source": "kpi.prev.var_mm",
                  "sparkline_source": "kpi.var_mm",
                  "suffix": " mm", "decimals": 2, "w": 3},
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
        "links": [],
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
        },
        "datasets": {
            "eq":  df_eq,  "sec": df_sec, "rt": df_rt,
            "fx":  df_fx,  "cm":  df_cm,  "kpi": df_kpi,
            "mov": df_mov, "chg": df_chg,
        },
        "filters": [
            {"id": "dt", "type": "dateRange", "default": "1Y",
              "targets": ["eq_indices", "rt_curve",
                           "fx_majors", "cm_energy",
                           "cm_metals"],
              "field": "date", "label": "Lookback",
              "description": ("Filters every time-series chart on "
                                "this page to the selected lookback "
                                "window. Does not affect the "
                                "sector / top-movers panels.")},
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
            {"group": "sync_wrap",
              "members": ["eq_indices", "rt_curve",
                           "fx_majors", "cm_energy", "cm_metals"],
              "sync": ["axis", "tooltip", "dataZoom"]},
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
            {"id": "fs_dt", "type": "dateRange", "default": "6M",
              "field": "date", "label": "Lookback",
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
    "cross_asset": {
        "title": "Cross-asset snapshot (composite)",
        "description": ("Four major asset classes (SPX / DXY / WTI / "
                         "Gold) in one make_4pack_grid composite with "
                         "event annotations. The only non-manifest "
                         "path in the gallery -- pure PNG artifact."),
        "kind": "composite",
        "build": build_cross_asset,
    },
    "risk_regime": {
        "title": "Risk regime monitor",
        "description": ("Cross-asset correlation heatmap, VIX term "
                         "structure across regimes, factor-return "
                         "boxplots, and running drawdown with a "
                         "bear-market band."),
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
                         "graph network, mandate funnel, stat_grid."),
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
        "description": ("Multi-asset portfolio: VaR gauge, factor radar, "
                         "allocation pie, stacked-area P&L, parallel-"
                         "coords positions, return-distribution "
                         "histogram, stat_grid."),
        "kind": "dashboard",
        "build": build_portfolio_analytics,
    },
    "markets_wrap": {
        "title": "Cross-asset end-of-day wrap",
        "description": ("One big scrollable cross-asset wrap: KPI "
                         "ribbon, equities / rates / FX / commodities "
                         "sections, dual-axis + bar_horizontal charts, "
                         "click-emit-filter, top-movers table with "
                         "z-score colour scale. Stress-tests layout "
                         "w/ 17 charts."),
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
    <div class="pill">Engine: ECharts (GS/viz/echarts)</div>
    <div class="pill">Theme: gs_clean</div>
    <div class="pill">Palettes: gs_primary / gs_blues / gs_diverging</div>
    <div class="pill">{total} demos / {ok_count} OK</div>
  </div>
  <div class="grid">
{cards}
  </div>
</div>
<footer>
  GS/viz/echarts demos &middot; run via <code>python demos.py --all</code>
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
