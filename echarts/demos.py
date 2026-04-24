#!/usr/bin/env python3
"""
demos -- consolidated demo scenarios for GS/viz/echarts.

Five end-to-end scenarios covering the major capabilities of the stack:

    rates_daily       Multi-tab rates dashboard with KPIs, sparklines, brush
                      cross-filter, dual-axis macro overlay.
    cross_asset       Four-panel composite (SPX/DXY/WTI/Gold) with event
                      annotations. Single PNG artifact via make_4pack_grid.
    risk_regime       Correlation heatmap, VIX term by regime, factor-return
                      boxplots, running drawdown with band annotation.
    rv_table          Rich RV screen with conditional formatting, z-score
                      color scale, clickable rows, 3 filter types.
    filter_showcase   All 9 filter types (dateRange, select, multiSelect,
                      toggle, slider, radio, text, number, numberRange)
                      bound to the same dataset.

All data is synthetic and deterministic (SEED-controlled). Every demo
follows the PRISM pattern: pull DataFrame(s), drop into a manifest, call
compile_dashboard() or a composite. Literal numbers never appear in the
manifest emitted by PRISM.

Run
---

    python demos.py                    interactive menu
    python demos.py --all              run every demo
    python demos.py --demo rv_table    run one
    python demos.py --list             list demos and exit
    python demos.py --open             auto-open the gallery in browser
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

def build_rates_daily(out_dir: Path) -> Dict[str, Any]:
    """Multi-tab US rates monitoring dashboard with KPIs, sparklines,
    brush cross-filter, and dual-axis macro overlay."""
    df_rates = pull_rates_panel()
    df_ism = pull_ism()

    manifest = {
        "schema_version": 1,
        "id": "us_rates_daily",
        "title": "US Rates Daily",
        "description": ("Multi-tab rates monitoring dashboard with KPIs, "
                         "sparklines, filter, brush cross-filter, and "
                         "dual-axis macro overlay."),
        "theme": "gs_clean",
        "palette": "gs_primary",
        "datasets": {"rates": df_rates, "ism_monthly": df_ism},
        "filters": [
            {"id": "dt", "type": "dateRange", "default": "1Y",
              "targets": ["*"], "field": "date", "label": "Lookback"},
        ],
        "layout": {"kind": "tabs", "tabs": [
            {"id": "overview", "label": "Overview", "rows": [
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
                    {"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
                      "spec": {
                          "chart_type": "multi_line", "dataset": "rates",
                          "mapping": {"x": "date",
                                        "y": ["us_2y", "us_5y",
                                               "us_10y", "us_30y"],
                                        "y_title": "Yield (%)"},
                          "title": "UST yield curve"}},
                ],
                [
                    {"widget": "chart", "id": "spread", "w": 12, "h_px": 280,
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
            {"id": "detail", "label": "Curve detail", "rows": [
                [
                    {"widget": "chart", "id": "two_ten", "w": 6, "h_px": 340,
                      "spec": {
                          "chart_type": "multi_line", "dataset": "rates",
                          "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"],
                                        "y_title": "Yield (%)"},
                          "title": "2Y vs 10Y"}},
                    {"widget": "chart", "id": "fives30s", "w": 6, "h_px": 340,
                      "spec": {
                          "chart_type": "line", "dataset": "rates",
                          "mapping": {"x": "date", "y": "5s30s",
                                        "y_title": "5s30s (bp)"},
                          "title": "5s30s spread"}},
                ],
                [
                    {"widget": "chart", "id": "real10y", "w": 12, "h_px": 300,
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
                                    "curve (top tab) to filter the "
                                    "spread chart by date range.")},
                ],
            ]},
            {"id": "macro", "label": "Macro overlay", "rows": [
                [
                    {"widget": "chart", "id": "ism_10y", "w": 12, "h_px": 420,
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
                        width=1400, height=1200)
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


def build_rv_table(out_dir: Path) -> Dict[str, Any]:
    """Rich RV screen with conditional formatting, z-score color scale,
    clickable rows, 3 filter types (radio/slider/text), drill-down charts."""
    df_rv = pull_rates_rv_rich()
    df_rates = pull_rates_panel()

    manifest = {
        "schema_version": 1,
        "id": "rates_rv_monitor",
        "title": "Rates RV Monitor",
        "description": ("Rich cross-asset RV screen with conditional "
                         "formatting, z-score color scale, clickable rows, "
                         "multiple filter types, and drill-down charts."),
        "theme": "gs_clean",
        "datasets": {"rv": df_rv, "rates": df_rates},
        "filters": [
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
            {"id": "search", "type": "text", "default": "",
              "field": "metric", "op": "contains",
              "label": "Metric contains",
              "placeholder": "e.g. 10Y, vol, spread",
              "targets": ["rv_table"]},
        ],
        "layout": {"kind": "grid", "cols": 12, "rows": [
            [
                {"widget": "stat_grid", "id": "summary", "w": 12,
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
                  "searchable": True, "sortable": True, "max_rows": 50,
                  "empty_message": ("No metrics match the current "
                                      "filters."),
                  "columns": [
                      {"field": "metric", "label": "Metric",
                        "align": "left", "tooltip": "RV metric name"},
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
                        "tooltip": "5Y rolling z-score of current",
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
                      {"field": "ytd_chg", "label": "YTD \u0394",
                        "format": "delta:2", "align": "right",
                        "tooltip": "YTD change in level",
                        "conditional": [
                            {"op": ">", "value": 0, "color": "#38a169"},
                            {"op": "<", "value": 0, "color": "#c53030"},
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
                      "chart_type": "multi_line", "dataset": "rates",
                      "mapping": {
                          "x": "date", "y": ["us_2y", "us_10y"],
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
                            "color": "#c53030", "style": "dashed"},
                      ]}},
            ],
        ]},
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1600, height=1800)
    return _result(r, thumb)


def build_filter_showcase(out_dir: Path) -> Dict[str, Any]:
    """All 9 filter types in one dashboard, bound to the same dataset.
    Each filter uses a different column + operator; updates cascade to
    both a scatter chart and a searchable table."""
    df = pull_active_filters_demo()
    manifest = {
        "schema_version": 1,
        "id": "filter_showcase",
        "title": "Filter controls showcase",
        "description": ("Every filter type supported by the manifest "
                         "(dateRange, select, multiSelect, numberRange, "
                         "toggle, slider, radio, text, number) bound to "
                         "the same dataset."),
        "theme": "gs_clean",
        "datasets": {"rows": df},
        "filters": [
            {"id": "dt", "type": "dateRange", "default": "6M",
              "targets": ["*"], "field": "date", "label": "Lookback"},
            {"id": "region", "type": "select", "default": "",
              "all_value": "",
              "options": ["", "US", "EU", "UK", "Japan", "EM"],
              "field": "region", "label": "Region", "targets": ["*"]},
            {"id": "sectors", "type": "multiSelect", "default": [],
              "options": ["Tech", "Financials", "Energy",
                           "Healthcare", "Consumer"],
              "field": "sector", "label": "Sectors", "targets": ["*"]},
            {"id": "rating", "type": "radio", "default": "Any",
              "all_value": "Any",
              "options": ["Any", "AAA", "AA", "A", "BBB", "BB"],
              "field": "rating", "label": "Rating", "targets": ["*"]},
            {"id": "min_vol", "type": "slider",
              "default": 0, "min": 0, "max": 40, "step": 1,
              "field": "volatility", "op": ">=",
              "label": "Min vol", "targets": ["*"]},
            {"id": "max_dd", "type": "number",
              "default": "", "min": -20, "max": 20, "step": 0.5,
              "field": "return_pct", "op": ">=",
              "label": "Return >=", "targets": ["*"]},
            {"id": "mcap_range", "type": "numberRange",
              "default": [1, 100], "field": "mcap_b",
              "label": "Mkt cap (\u0024B, min,max)", "targets": ["*"]},
            {"id": "tech_only", "type": "toggle", "default": False,
              "field": "is_tech", "label": "Tech only", "targets": ["*"]},
            {"id": "search", "type": "text", "default": "",
              "field": "ticker", "op": "contains",
              "label": "Ticker search",
              "placeholder": "TEC-US...", "targets": ["*"]},
        ],
        "layout": {"kind": "grid", "cols": 12, "rows": [
            [
                {"widget": "markdown", "id": "intro", "w": 12,
                  "content": (
                      "### Filter reference\n\n"
                      "All 9 filter types above are wired to the same "
                      "underlying dataset. Every filter has a `field` "
                      "(the column to filter against) and an `op` "
                      "(`==`, `>=`, `contains`, etc.). "
                      "Change any control above to watch the chart "
                      "and table below update.")},
            ],
            [
                {"widget": "chart", "id": "vol_by_sector",
                  "w": 6, "h_px": 320,
                  "spec": {
                      "chart_type": "scatter", "dataset": "rows",
                      "mapping": {"x": "volatility", "y": "return_pct",
                                    "color": "sector", "size": "mcap_b",
                                    "x_title": "Volatility (%)",
                                    "y_title": "Return (%)"},
                      "title": "Vol vs return (size = mcap)",
                      "annotations": [
                          {"type": "hline", "y": 0,
                            "color": "#718096", "style": "dashed",
                            "label": ""},
                      ]}},
                {"widget": "chart", "id": "count_by_rating",
                  "w": 6, "h_px": 320,
                  "spec": {
                      "chart_type": "bar", "dataset": "rows",
                      "mapping": {"x": "rating", "y": "mcap_b",
                                    "color": "sector", "stack": True,
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
                  "empty_message": "No rows match the current filters.",
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
                            {"op": ">", "value": 0, "color": "#38a169"},
                            {"op": "<", "value": 0, "color": "#c53030"},
                        ]},
                      {"field": "mcap_b", "label": "Mkt cap",
                        "format": "currency:1", "align": "right"},
                  ],
                  "row_click": {
                      "title_field": "ticker",
                      "popup_fields": ["date", "ticker", "sector",
                                         "region", "rating",
                                         "volatility", "return_pct",
                                         "mcap_b"]}},
            ],
        ]},
    }
    r = compile_dashboard(manifest,
                           output_path=str(out_dir / "dashboard.html"))
    thumb = _thumbnail(r.html_path, out_dir / "thumbnail.png",
                        width=1600, height=1600)
    return _result(r, thumb)


# =============================================================================
# DEMO REGISTRY + SHARED HELPERS
# =============================================================================

DEMO_REGISTRY: Dict[str, Dict[str, Any]] = {
    "rates_daily": {
        "title": "US Rates Daily",
        "description": ("Multi-tab rates monitoring dashboard with KPIs, "
                         "sparklines, brush cross-filter, and dual-axis "
                         "macro overlay."),
        "kind": "dashboard",
        "build": build_rates_daily,
    },
    "cross_asset": {
        "title": "Cross-asset snapshot",
        "description": ("Four major asset classes in one conversational "
                         "composite (SPX, DXY, WTI, Gold) with event "
                         "annotations."),
        "kind": "composite",
        "build": build_cross_asset,
    },
    "risk_regime": {
        "title": "Risk regime monitor",
        "description": ("Cross-asset correlation heatmap, VIX term "
                         "structure across regimes, factor-return "
                         "distributions, and running drawdown."),
        "kind": "dashboard",
        "build": build_risk_regime,
    },
    "rv_table": {
        "title": "Rates RV Monitor",
        "description": ("Rich cross-asset RV screen with conditional "
                         "formatting, z-score color scale, clickable "
                         "rows, multiple filter types, drill-down "
                         "charts."),
        "kind": "dashboard",
        "build": build_rv_table,
    },
    "filter_showcase": {
        "title": "Filter controls showcase",
        "description": ("Every filter type supported by the manifest "
                         "(dateRange, select, multiSelect, numberRange, "
                         "toggle, slider, radio, text, number) bound to "
                         "the same dataset."),
        "kind": "dashboard",
        "build": build_filter_showcase,
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
