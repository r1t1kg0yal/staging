"""
Sample demo specs for every supported chart type + sample dashboard manifests.

Two registries:

    SAMPLES             chart-type samples: name -> callable returning an
                        ECharts option dict.
    DASHBOARD_SAMPLES   full dashboard manifests: name -> callable returning
                        a manifest dict (validated by building through
                        Dashboard()).

Used by:
    python echart_studio.py demo
    python echart_studio.py demo --matrix
    python echart_dashboard.py demo
    tests/integration smoke matrix
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Callable, Dict, List


# =============================================================================
# CHART SAMPLES (one per chart type)
# =============================================================================

SAMPLES: Dict[str, Callable[[], Dict[str, Any]]] = {}


def _register(name: str):
    def decorator(fn):
        SAMPLES[name] = fn
        return fn
    return decorator


def _df_date_range(n: int = 40):
    import pandas as pd
    return pd.date_range("2025-01-01", periods=n, freq="W-FRI")


@_register("line")
def _line():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "date": _df_date_range(50),
        "a": [100 + (i * 0.5) + (i % 7) for i in range(50)],
    })
    return make_echart(df, "line", mapping={"x": "date", "y": "a"},
                        title="line sample").option


@_register("multi_line")
def _multi_line():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "date": _df_date_range(60),
        "us_2y": [4.0 + i*0.01 for i in range(60)],
        "us_10y": [4.2 + i*0.005 for i in range(60)],
        "us_30y": [4.4 + i*0.003 for i in range(60)],
    })
    return make_echart(df, "multi_line",
                        mapping={"x": "date", "y": ["us_2y", "us_10y", "us_30y"]},
                        title="UST yields", subtitle="weekly").option


@_register("bar")
def _bar():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "region": ["US", "EU", "JP", "UK", "CH", "CA"],
        "gdp": [26.9, 18.3, 4.2, 3.1, 0.9, 2.1],
    })
    return make_echart(df, "bar", mapping={"x": "region", "y": "gdp"},
                        title="GDP by region", subtitle="USD trillions").option


@_register("bar_horizontal")
def _bar_h():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "sector": ["Tech", "Financials", "Energy", "Healthcare", "Industrials", "Utilities"],
        "weight": [28, 14, 9, 13, 10, 3],
    })
    return make_echart(df, "bar_horizontal", mapping={"x": "weight", "y": "sector"},
                        title="Sector weights", subtitle="S&P 500").option


@_register("stacked_bar")
def _stacked_bar():
    import pandas as pd
    from echart_studio import make_echart
    rows = []
    for region in ("US", "EU", "JP"):
        for kind in ("goods", "services"):
            rows.append({"region": region, "kind": kind,
                          "val": {"US": {"goods": 10, "services": 15},
                                    "EU": {"goods": 8, "services": 9},
                                    "JP": {"goods": 5, "services": 4}}[region][kind]})
    df = pd.DataFrame(rows)
    opt = make_echart(df, "bar",
                        mapping={"x": "region", "y": "val", "color": "kind"},
                        title="Stacked bar").option
    for s in opt["series"]:
        s["stack"] = "total"
    return opt


@_register("scatter")
def _scatter():
    import pandas as pd
    from echart_studio import make_echart
    random.seed(7)
    df = pd.DataFrame({
        "yield_change": [random.gauss(0, 10) for _ in range(80)],
        "equity_return": [random.gauss(0, 1.2) for _ in range(80)],
    })
    return make_echart(df, "scatter",
                        mapping={"x": "yield_change", "y": "equity_return"},
                        title="Daily correlations").option


@_register("scatter_multi")
def _scatter_multi():
    import pandas as pd
    from echart_studio import make_echart
    random.seed(11)
    rows = []
    for sector in ("Tech", "Financials", "Energy"):
        for _ in range(30):
            rows.append({"sector": sector,
                          "pe": max(4, random.gauss(20, 6)),
                          "roe": max(0, random.gauss(15, 5))})
    df = pd.DataFrame(rows)
    return make_echart(df, "scatter",
                        mapping={"x": "pe", "y": "roe", "color": "sector"},
                        title="P/E vs ROE by sector").option


@_register("scatter_studio")
def _scatter_studio():
    import pandas as pd
    from echart_studio import make_echart
    from datetime import date, timedelta
    random.seed(13)
    n = 220
    base = date(2024, 6, 1)
    dates = [base + timedelta(days=i) for i in range(n)]
    us_2y = [3.5 + sum(random.gauss(0, 0.04) for _ in range(i + 1))
              for i in range(n)]
    us_10y = [u + 0.4 + random.gauss(0, 0.05) for u in us_2y]
    real_10y = [u - 2.0 + random.gauss(0, 0.10) for u in us_10y]
    breakeven = [u - r for u, r in zip(us_10y, real_10y)]
    spx_pe = [22 + 0.6 * (u - 4.0) + random.gauss(0, 0.6) for u in us_10y]
    regime = [
        "risk-on" if (i // 50) % 2 == 0 else "risk-off"
        for i in range(n)
    ]
    df = pd.DataFrame({
        "date":           dates,
        "us_2y":          us_2y,
        "us_10y":         us_10y,
        "real_10y":       real_10y,
        "breakeven_5y5y": breakeven,
        "spx_pe":         spx_pe,
        "regime":         regime,
    })
    return make_echart(df, "scatter_studio",
                        mapping={
                            "x_columns": ["us_2y", "us_10y", "real_10y",
                                            "breakeven_5y5y"],
                            "y_columns": ["spx_pe", "us_2y", "us_10y",
                                            "breakeven_5y5y"],
                            "color_columns": ["regime"],
                            "order_by": "date",
                            "x_default": "us_10y",
                            "y_default": "spx_pe",
                            "color_default": "regime",
                            "label_column": "date",
                            "x_transform_default": "raw",
                            "y_transform_default": "raw",
                        },
                        title="Macro studio (X/Y picker)").option


@_register("area")
def _area():
    import pandas as pd
    from echart_studio import make_echart
    rows = []
    for d in _df_date_range(40):
        for kind, base in (("goods", 40), ("services", 60), ("other", 20)):
            rows.append({"date": d, "kind": kind,
                          "val": base + (d.day * 0.2)})
    df = pd.DataFrame(rows)
    return make_echart(df, "area",
                        mapping={"x": "date", "y": "val", "color": "kind"},
                        title="Composition over time").option


@_register("heatmap")
def _heatmap():
    import pandas as pd
    from echart_studio import make_echart
    random.seed(3)
    rows = []
    for x in ("A", "B", "C", "D", "E"):
        for y in ("1", "2", "3", "4"):
            rows.append({"x": x, "y": y, "v": random.randint(0, 100)})
    df = pd.DataFrame(rows)
    return make_echart(df, "heatmap",
                        mapping={"x": "x", "y": "y", "value": "v"},
                        title="Correlation heatmap").option


@_register("correlation_matrix")
def _correlation_matrix():
    import pandas as pd
    from echart_studio import make_echart
    from datetime import date, timedelta
    random.seed(17)
    n = 250
    base = date(2025, 1, 1)
    dates = [base + timedelta(days=i) for i in range(n)]
    us_2y = [3.5 + sum(random.gauss(0, 0.04) for _ in range(i + 1)) for i in range(n)]
    us_5y = [u + random.gauss(0, 0.05) + 0.6 for u in us_2y]
    us_10y = [u5 + random.gauss(0, 0.05) + 0.4 for u5 in us_5y]
    us_30y = [u10 + random.gauss(0, 0.05) + 0.2 for u10 in us_10y]
    real_10y = [u10 - 2.0 + random.gauss(0, 0.10) for u10 in us_10y]
    breakeven = [u10 - r10 for u10, r10 in zip(us_10y, real_10y)]
    df = pd.DataFrame({
        "date":     dates,
        "us_2y":    us_2y,
        "us_5y":    us_5y,
        "us_10y":   us_10y,
        "us_30y":   us_30y,
        "real_10y": real_10y,
        "breakeven_5y5y": breakeven,
    })
    return make_echart(df, "correlation_matrix",
                        mapping={
                            "columns": ["us_2y", "us_5y", "us_10y", "us_30y",
                                          "real_10y", "breakeven_5y5y"],
                            "method": "pearson",
                            "transform": "pct_change",
                            "order_by": "date",
                            "show_values": True,
                            "value_decimals": 2,
                        },
                        title="Rates correlation (% change)").option


@_register("pie")
def _pie():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "asset": ["Equities", "Bonds", "Cash", "Commodities"],
        "weight": [55, 30, 10, 5],
    })
    return make_echart(df, "pie", mapping={"category": "asset", "value": "weight"},
                        title="Portfolio mix").option


@_register("donut")
def _donut():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "rating": ["AAA", "AA", "A", "BBB", "BB", "B"],
        "pct": [25, 28, 22, 15, 7, 3],
    })
    return make_echart(df, "donut",
                        mapping={"category": "rating", "value": "pct"},
                        title="Rating distribution").option


@_register("boxplot")
def _boxplot():
    import pandas as pd
    from echart_studio import make_echart
    random.seed(5)
    rows = []
    for sector in ("Tech", "Financials", "Energy", "Utilities"):
        for _ in range(40):
            rows.append({"sector": sector, "ret": random.gauss(
                {"Tech": 1.0, "Financials": 0.3, "Energy": 0.8, "Utilities": 0.2}[sector], 2)})
    df = pd.DataFrame(rows)
    return make_echart(df, "boxplot",
                        mapping={"x": "sector", "y": "ret"},
                        title="Return dispersion by sector").option


@_register("sankey")
def _sankey():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "src": ["US", "US", "EU", "EU", "CN", "CN", "Electronics", "Energy", "Food", "Electronics", "Energy", "Food"],
        "tgt": ["Electronics", "Energy", "Electronics", "Food", "Electronics", "Food",
                 "Asia", "EU", "Asia", "Africa", "Asia", "Africa"],
        "v":   [12, 6, 9, 4, 18, 5, 20, 8, 10, 4, 6, 3],
    })
    return make_echart(df, "sankey",
                        mapping={"source": "src", "target": "tgt", "value": "v"},
                        title="Trade flows").option


@_register("treemap")
def _treemap():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "region": ["US", "US", "US", "EU", "EU", "JP"],
        "sector": ["Tech", "Financials", "Energy", "Industrials", "Financials", "Automotive"],
        "cap":    [2200, 1400, 600, 800, 700, 450],
    })
    return make_echart(df, "treemap",
                        mapping={"path": ["region", "sector"], "value": "cap"},
                        title="Market cap by region + sector").option


@_register("sunburst")
def _sunburst():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "region": ["US", "US", "EU", "EU", "JP", "JP"],
        "sector": ["Tech", "Financials", "Industrials", "Financials", "Automotive", "Tech"],
        "cap":    [2200, 1400, 800, 700, 450, 200],
    })
    return make_echart(df, "sunburst",
                        mapping={"path": ["region", "sector"], "value": "cap"},
                        title="Portfolio breakdown").option


@_register("graph")
def _graph():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "src": ["US", "US", "US", "EU", "EU", "JP", "CN"],
        "tgt": ["EU", "JP", "CN", "JP", "CN", "CN", "US"],
        "v":   [10, 5, 12, 4, 8, 6, 15],
    })
    return make_echart(df, "graph",
                        mapping={"source": "src", "target": "tgt", "value": "v"},
                        title="Trade partners network").option


@_register("candlestick")
def _candlestick():
    import pandas as pd
    from echart_studio import make_echart
    random.seed(1)
    rows = []
    price = 100.0
    for d in _df_date_range(40):
        o = price
        c = o + random.gauss(0, 1.5)
        lo = min(o, c) - abs(random.gauss(0, 1))
        hi = max(o, c) + abs(random.gauss(0, 1))
        rows.append({"date": d, "o": round(o, 2), "c": round(c, 2),
                      "l": round(lo, 2), "h": round(hi, 2)})
        price = c
    df = pd.DataFrame(rows)
    return make_echart(df, "candlestick",
                        mapping={"x": "date", "open": "o", "close": "c",
                                   "low": "l", "high": "h"},
                        title="OHLC").option


@_register("radar")
def _radar():
    import pandas as pd
    from echart_studio import make_echart
    rows = []
    dims = ["Quality", "Momentum", "Value", "Size", "LowVol"]
    for port in ("Portfolio A", "Portfolio B"):
        for i, d in enumerate(dims):
            rows.append({"factor": d, "score": 3 + (i + (0 if port == "Portfolio A" else 2)) % 6,
                          "portfolio": port})
    df = pd.DataFrame(rows)
    return make_echart(df, "radar",
                        mapping={"category": "factor", "value": "score", "series": "portfolio"},
                        title="Factor exposure").option


@_register("gauge")
def _gauge():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({"v": [72]})
    return make_echart(df, "gauge",
                        mapping={"value": "v", "name": "Risk index", "min": 0, "max": 100},
                        title="Global risk gauge").option


@_register("calendar_heatmap")
def _cal():
    import pandas as pd
    from echart_studio import make_echart
    random.seed(2)
    dates = pd.date_range("2025-01-01", "2025-12-31")
    df = pd.DataFrame({"date": dates,
                         "v": [random.randint(-5, 5) for _ in range(len(dates))]})
    return make_echart(df, "calendar_heatmap",
                        mapping={"date": "date", "value": "v", "year": "2025"},
                        title="Daily returns heatmap").option


@_register("funnel")
def _funnel():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({"stage": ["Inquiry", "Qualified", "Proposal", "Won"],
                         "n": [100, 60, 30, 15]})
    return make_echart(df, "funnel",
                        mapping={"category": "stage", "value": "n"},
                        title="Sales funnel").option


@_register("parallel_coords")
def _par():
    import pandas as pd
    from echart_studio import make_echart
    random.seed(4)
    rows = []
    for g in ("HY", "IG"):
        for _ in range(25):
            rows.append({
                "group": g,
                "spread": max(50, random.gauss(180 if g == "HY" else 80, 40)),
                "dur": max(1, random.gauss(5, 1.5)),
                "yield": max(3, random.gauss(7 if g == "HY" else 5, 1)),
                "recovery": max(10, random.gauss(40, 10)),
            })
    df = pd.DataFrame(rows)
    return make_echart(df, "parallel_coords",
                        mapping={"dims": ["spread", "dur", "yield", "recovery"],
                                   "color": "group"},
                        title="Credit risk axes").option


@_register("tree")
def _tree():
    import pandas as pd
    from echart_studio import make_echart
    df = pd.DataFrame({
        "name": ["Fed Chair", "Vice Chair", "Governor 1", "Governor 2",
                  "Governor 3", "FOMC Hawk", "FOMC Dove"],
        "parent": ["", "Fed Chair", "Fed Chair", "Fed Chair",
                      "Fed Chair", "Vice Chair", "Governor 2"],
    })
    return make_echart(df, "tree",
                        mapping={"name": "name", "parent": "parent"},
                        title="Committee hierarchy").option


def list_samples() -> List[str]:
    return sorted(SAMPLES.keys())


def get_sample(name: str) -> Dict[str, Any]:
    if name not in SAMPLES:
        raise ValueError(
            f"Unknown sample '{name}'. Available: {', '.join(sorted(SAMPLES.keys()))}"
        )
    return SAMPLES[name]()


# =============================================================================
# DASHBOARD SAMPLES
# =============================================================================

DASHBOARD_SAMPLES: Dict[str, Callable[[], Dict[str, Any]]] = {}


def _register_dashboard(name: str):
    def decorator(fn):
        DASHBOARD_SAMPLES[name] = fn
        return fn
    return decorator


def _rates_panel():
    import pandas as pd
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    random.seed(1)
    base2 = 4.0; base10 = 4.2; base30 = 4.4
    vals2 = []; vals10 = []; vals30 = []
    for i in range(len(dates)):
        base2 += random.gauss(0, 0.03)
        base10 += random.gauss(0, 0.025)
        base30 += random.gauss(0, 0.02)
        vals2.append(round(base2, 3))
        vals10.append(round(base10, 3))
        vals30.append(round(base30, 3))
    df = pd.DataFrame({"date": dates, "us_2y": vals2, "us_10y": vals10,
                         "us_30y": vals30})
    df["2s10s"] = (df["us_10y"] - df["us_2y"]) * 100
    df["region"] = "US"
    return df


def _sector_panel():
    import pandas as pd
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    random.seed(2)
    rows = []
    for sec in ("Tech", "Financials", "Energy", "Healthcare", "Industrials"):
        price = 100.0
        for d in dates:
            price *= 1 + random.gauss(0.0005, 0.012)
            rows.append({"date": d, "sector": sec, "price": round(price, 2)})
    return pd.DataFrame(rows)


def _trade_flows():
    import pandas as pd
    rows = [
        {"src": "US", "tgt": "EU", "v": 280},
        {"src": "US", "tgt": "JP", "v": 100},
        {"src": "US", "tgt": "CN", "v": 450},
        {"src": "EU", "tgt": "US", "v": 450},
        {"src": "EU", "tgt": "JP", "v": 80},
        {"src": "EU", "tgt": "CN", "v": 220},
        {"src": "JP", "tgt": "US", "v": 140},
        {"src": "JP", "tgt": "CN", "v": 180},
        {"src": "CN", "tgt": "US", "v": 520},
        {"src": "CN", "tgt": "EU", "v": 380},
    ]
    return pd.DataFrame(rows)


@_register_dashboard("rates_daily")
def _rates_daily():
    from echart_studio import make_echart
    from echart_dashboard import (
        Dashboard, ChartRef, KPIRef, MarkdownRef, GlobalFilter, Link,
    )
    df = _rates_panel()

    curve_opt = make_echart(
        df, "multi_line",
        mapping={"x": "date", "y": ["us_2y", "us_10y", "us_30y"]},
        title="UST yield curve").option

    spread_opt = make_echart(
        df, "line", mapping={"x": "date", "y": "2s10s"},
        title="2s10s spread (bps)").option

    db = (Dashboard(id="rates_daily",
                      title="US Rates Daily",
                      description="Curve, spread, and snapshot KPIs.",
                      theme="gs_clean")
          .add_dataset("rates", df)
          .add_filter(GlobalFilter(id="dt", type="dateRange",
                                    default="3M", targets=["*"],
                                    label="Date range", field="date"))
          .add_filter(GlobalFilter(id="reg", type="select",
                                    options=["US"], default="US",
                                    targets=["*"], label="Region",
                                    field="region"))
          .add_row([ChartRef(id="curve", option=curve_opt, w=8, h_px=360,
                              dataset_ref="rates", title="Yield curve"),
                     KPIRef(id="k2y", label="2Y (latest)",
                             source="rates.latest.us_2y", w=4),
                     ])
          .add_row([KPIRef(id="k10y", label="10Y (latest)",
                             source="rates.latest.us_10y", w=4),
                     KPIRef(id="k30y", label="30Y (latest)",
                             source="rates.latest.us_30y", w=4),
                     KPIRef(id="kspr", label="2s10s (bps, latest)",
                             source="rates.latest.2s10s", w=4),
                     ])
          .add_row([ChartRef(id="spread", option=spread_opt, w=12, h_px=280,
                              dataset_ref="rates", title="2s10s spread")])
          .add_row([MarkdownRef(id="md", content=(
              "## Method\n"
              "Source: synthetic data. Cross-filter the yield curve to\n"
              "constrain the 2s10s chart.\n"))])
          .add_link(Link(group="rates_group",
                           members=["curve", "spread"],
                           sync=["axis", "tooltip"]))
          .add_link(Link(group="rates_brush",
                           members=["curve", "spread"],
                           brush={"type": "rect", "xAxisIndex": 0})))
    return db.to_manifest()


@_register_dashboard("macro_dashboard")
def _macro_dashboard():
    from echart_studio import make_echart
    from echart_dashboard import (
        Dashboard, ChartRef, KPIRef, MarkdownRef, DividerRef, GlobalFilter, Link,
    )
    df_rates = _rates_panel()
    df_sec = _sector_panel()
    df_flows = _trade_flows()

    rates_opt = make_echart(df_rates, "multi_line",
                              mapping={"x": "date", "y": ["us_2y", "us_10y"]},
                              title="Rates").option
    spread_opt = make_echart(df_rates, "line",
                               mapping={"x": "date", "y": "2s10s"},
                               title="2s10s").option
    sec_opt = make_echart(df_sec, "multi_line",
                            mapping={"x": "date", "y": "price", "color": "sector"},
                            title="Sectors").option
    sankey_opt = make_echart(df_flows, "sankey",
                               mapping={"source": "src", "target": "tgt", "value": "v"},
                               title="Trade flows").option

    db = (Dashboard(id="macro_dashboard", title="Macro Dashboard",
                      description="Rates, equities, and trade flows.",
                      theme="gs_clean")
          .add_dataset("rates", df_rates)
          .add_dataset("sectors", df_sec)
          .add_filter(GlobalFilter(id="dt", type="dateRange",
                                    default="6M",
                                    targets=["rates_*", "sec_*"],
                                    label="Date range", field="date"))
          .add_filter(GlobalFilter(id="sector", type="multiSelect",
                                    options=["Tech", "Financials", "Energy",
                                              "Healthcare", "Industrials"],
                                    default=["Tech", "Financials"],
                                    targets=["sec_*"], label="Sectors",
                                    field="sector"))
          .add_row([ChartRef(id="rates_curve", option=rates_opt, w=6, h_px=300,
                              dataset_ref="rates", title="UST curve"),
                     ChartRef(id="rates_2s10s", option=spread_opt, w=6, h_px=300,
                              dataset_ref="rates", title="2s10s")])
          .add_row([ChartRef(id="sec_ts", option=sec_opt, w=8, h_px=340,
                              dataset_ref="sectors", title="Sector prices"),
                     KPIRef(id="flows_ttl", label="Total flows (USD bn)",
                             value=sum(r["v"] for r in df_flows.to_dict("records")),
                             w=4)])
          .add_row([ChartRef(id="sankey", option=sankey_opt, w=12, h_px=320,
                              title="Trade flows (sankey)")])
          .add_row([DividerRef()])
          .add_row([MarkdownRef(id="md", content=(
              "### Notes\n"
              "All synthetic. Brush the UST curve to cross-filter the spread.\n"
              "Use Sectors multiSelect to filter the sector time series.\n"))])
          .add_link(Link(group="rates_link",
                           members=["rates_curve", "rates_2s10s"],
                           sync=["axis", "tooltip"]))
          .add_link(Link(group="rates_brush",
                           members=["rates_curve", "rates_2s10s"],
                           brush={"type": "rect", "xAxisIndex": 0})))
    return db.to_manifest()


@_register_dashboard("cross_asset_board")
def _cross_asset_board():
    from echart_studio import make_echart
    from echart_dashboard import (
        Dashboard, ChartRef, GlobalFilter, Link,
    )
    df_rates = _rates_panel()
    df_sec = _sector_panel()

    rates_opt = make_echart(df_rates, "line",
                              mapping={"x": "date", "y": "us_10y"},
                              title="10Y").option
    spread_opt = make_echart(df_rates, "line",
                               mapping={"x": "date", "y": "2s10s"},
                               title="2s10s").option
    tech_df = df_sec[df_sec["sector"] == "Tech"].copy()
    fin_df = df_sec[df_sec["sector"] == "Financials"].copy()
    tech_opt = make_echart(tech_df, "line",
                             mapping={"x": "date", "y": "price"},
                             title="Tech").option
    fin_opt = make_echart(fin_df, "line",
                            mapping={"x": "date", "y": "price"},
                            title="Financials").option

    db = (Dashboard(id="cross_asset_board",
                      title="Cross-Asset Board",
                      description="Four linked mini-charts with shared dataZoom.",
                      theme="gs_clean")
          .add_dataset("rates", df_rates)
          .add_dataset("sectors", df_sec)
          .add_filter(GlobalFilter(id="dt", type="dateRange", default="6M",
                                    targets=["*"], label="Date", field="date"))
          .add_row([ChartRef(id="mini_10y",  option=rates_opt,  w=6, h_px=240,
                              dataset_ref="rates", title="US 10Y"),
                     ChartRef(id="mini_2s10s", option=spread_opt, w=6, h_px=240,
                              dataset_ref="rates", title="2s10s")])
          .add_row([ChartRef(id="mini_tech", option=tech_opt, w=6, h_px=240,
                              dataset_ref="sectors", title="Tech"),
                     ChartRef(id="mini_fin",  option=fin_opt,  w=6, h_px=240,
                              dataset_ref="sectors", title="Financials")])
          .add_link(Link(group="cross",
                           members=["mini_10y", "mini_2s10s", "mini_tech", "mini_fin"],
                           sync=["axis", "tooltip", "dataZoom"])))
    return db.to_manifest()


def list_dashboard_samples() -> List[str]:
    return sorted(DASHBOARD_SAMPLES.keys())

# =============================================================================
# PRISM ROLEPLAY DEMOS (JSON-first)
#
# Four analysis scenarios, each as a SINGLE dict passed to compile_dashboard().
# Run via `python samples.py demo --all` or `python samples.py demo --scenario rates`.
# =============================================================================

import argparse
import sys
import time
from datetime import datetime

import pandas as pd

from echart_dashboard import compile_dashboard


def new_session(name: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    root = Path("/tmp") / f"{ts}_{name}"
    (root / "dashboards").mkdir(parents=True, exist_ok=True)
    return root


def df_to_source(df: pd.DataFrame) -> List[List[Any]]:
    """Convert a DataFrame to the manifest's [header, ...rows] source shape."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    source: List[List[Any]] = [list(out.columns)]
    for _, row in out.iterrows():
        source.append([
            None if (v is None or (isinstance(v, float) and v != v))
            else (v.item() if hasattr(v, "item") else v)
            for v in row
        ])
    return source


def latest_prev(df: pd.DataFrame, col: str):
    return float(df[col].iloc[-1]), float(df[col].iloc[-2])


# =============================================================================
# SYNTHETIC DATA
# =============================================================================


def rates_panel(n: int = 252, seed: int = 1) -> pd.DataFrame:
    random.seed(seed)
    dates = pd.date_range(end="2026-04-22", periods=n, freq="B")
    base = [4.05, 4.22, 4.31, 4.48]
    rows = []
    for d in dates:
        base = [b + random.gauss(0, 0.03) for b in base]
        rows.append({
            "date": d, "us_2y": round(base[0], 3), "us_5y": round(base[1], 3),
            "us_10y": round(base[2], 3), "us_30y": round(base[3], 3),
        })
    df = pd.DataFrame(rows)
    df["2s10s"] = ((df["us_10y"] - df["us_2y"]) * 100).round(1)
    df["5s30s"] = ((df["us_30y"] - df["us_5y"]) * 100).round(1)
    return df


def cross_asset_panel(n: int = 252, seed: int = 3) -> pd.DataFrame:
    random.seed(seed)
    dates = pd.date_range(end="2026-04-22", periods=n, freq="B")
    spx, ust10, dxy, wti = 5100.0, 4.30, 104.0, 82.0
    rows = []
    for d in dates:
        spx *= 1 + random.gauss(0.0005, 0.010)
        ust10 += random.gauss(0, 0.025)
        dxy += random.gauss(0, 0.3)
        wti += random.gauss(0, 0.8)
        rows.append({
            "date": d, "spx": round(spx, 2), "us_10y": round(ust10, 3),
            "dxy": round(dxy, 2), "wti": round(wti, 2),
        })
    return pd.DataFrame(rows)


def corr_long() -> pd.DataFrame:
    random.seed(4)
    labels = ["SPX", "US10Y", "DXY", "WTI", "Gold", "IG"]
    rows = []
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            v = 1.0 if i == j else max(-1, min(1, round(random.gauss(0, 0.5), 2)))
            rows.append({"a": a, "b": b, "corr": v})
    return pd.DataFrame(rows)


def trade_flows() -> pd.DataFrame:
    return pd.DataFrame([
        {"src": "US", "tgt": "EU", "v": 280},
        {"src": "US", "tgt": "CN", "v": 450},
        {"src": "US", "tgt": "MX", "v": 320},
        {"src": "EU", "tgt": "US", "v": 450},
        {"src": "EU", "tgt": "CN", "v": 220},
        {"src": "CN", "tgt": "US", "v": 530},
        {"src": "CN", "tgt": "EU", "v": 410},
        {"src": "JP", "tgt": "US", "v": 180},
        {"src": "MX", "tgt": "US", "v": 380},
    ])


def tariff_bars() -> pd.DataFrame:
    return pd.DataFrame([
        {"action": "US -> CN tariff (2024)", "rate_pct": 25.0},
        {"action": "EU -> US steel (2025)", "rate_pct": 17.5},
        {"action": "US -> EV import (2026)", "rate_pct": 20.0},
        {"action": "CN -> US retaliatory", "rate_pct": 12.5},
        {"action": "US -> MX autos",       "rate_pct": 8.0},
        {"action": "JP bilateral accord",   "rate_pct": 3.5},
    ])


def cpi_stack(seed: int = 7) -> pd.DataFrame:
    random.seed(seed)
    dates = pd.date_range("2024-01-01", "2026-04-01", freq="MS")
    rows = []
    for d in dates:
        for comp, mu in (("Goods", 0.2), ("Shelter", 0.35),
                         ("Services", 0.45), ("Energy", 0.1), ("Food", 0.25)):
            rows.append({"date": d, "component": comp,
                          "yoy_pct": round(mu + random.gauss(0, 0.35), 2)})
    return pd.DataFrame(rows)


def fed_path_series(seed: int = 6) -> pd.DataFrame:
    random.seed(seed)
    hist_dates = pd.date_range("2020-01-01", "2026-04-01", freq="MS")
    rate = 0.1
    hist = []
    for d in hist_dates:
        if d.year == 2020: rate = 0.1
        elif d.year == 2021: rate = 0.1
        elif d.year == 2022 and d.month < 3: rate = 0.1
        elif d.year == 2022: rate = min(4.5, rate + 0.25)
        elif d.year == 2023: rate = min(5.5, rate + 0.05)
        elif d.year == 2024 and d.month < 10: rate = 5.5
        elif d.year == 2024: rate = 4.75
        elif d.year == 2025: rate = 4.25
        else: rate = 4.0
        hist.append({"date": d, "rate": round(rate, 2), "series": "history"})
    sep_dates = pd.date_range("2026-04-01", "2029-12-01", freq="MS")
    sr = 4.0
    sep = []
    for d in sep_dates:
        if d.year == 2026: sr -= 0.04
        elif d.year == 2027: sr -= 0.03
        elif d.year == 2028: sr -= 0.02
        else: sr = 2.75
        sep.append({"date": d, "rate": round(max(2.5, sr), 2),
                     "series": "SEP median"})
    return pd.DataFrame(hist + sep)


def jobs_panel(seed: int = 9) -> pd.DataFrame:
    random.seed(seed)
    dates = pd.date_range("2024-01-01", "2026-04-01", freq="MS")
    rows = []
    ur, vac = 3.7, 10.2
    for d in dates:
        ur += random.gauss(0.01, 0.05)
        vac += random.gauss(-0.02, 0.2)
        rows.append({"date": d, "unemp": round(ur, 2), "vacancies": round(vac, 2)})
    return pd.DataFrame(rows)


def fx_ohlc(seed: int = 8, n: int = 80) -> pd.DataFrame:
    random.seed(seed)
    dates = pd.date_range(end="2026-04-22", periods=n, freq="B")
    rows = []
    px = 1.0850
    for d in dates:
        o = px
        c = o + random.gauss(0, 0.004)
        lo = min(o, c) - abs(random.gauss(0, 0.003))
        hi = max(o, c) + abs(random.gauss(0, 0.003))
        rows.append({"date": d, "open": round(o, 4), "close": round(c, 4),
                      "low": round(lo, 4), "high": round(hi, 4)})
        px = c
    return pd.DataFrame(rows)


# =============================================================================
# SCENARIO 1: US RATES DAILY -- PURE JSON MANIFEST
# =============================================================================


def scenario_us_rates_daily() -> Dict[str, Any]:
    df = rates_panel()
    l2y, p2y = latest_prev(df, "us_2y")
    l5y, p5y = latest_prev(df, "us_5y")
    l10, p10 = latest_prev(df, "us_10y")
    l30, p30 = latest_prev(df, "us_30y")
    lspr, pspr = latest_prev(df, "2s10s")

    return {
        "schema_version": 1,
        "id": "us_rates_daily",
        "title": "US Rates Daily",
        "description": ("UST curve, spreads, and snapshot KPIs. "
                         "252-business-day synthetic panel."),
        "theme": "gs_clean",
        "datasets": {
            "rates": {"source": df_to_source(df)},
        },
        "filters": [
            {"id": "dt", "type": "dateRange", "default": "6M",
             "targets": ["*"], "field": "date", "label": "Date range"},
        ],
        "layout": {
            "kind": "tabs", "cols": 12,
            "tabs": [
                {
                    "id": "overview", "label": "Overview",
                    "description": "Snapshot KPIs and yield curve",
                    "rows": [
                        [
                            {"widget": "kpi", "id": "k2y",  "label": "2Y",
                             "value": l2y, "delta": round(l2y - p2y, 3),
                             "suffix": "%", "decimals": 3, "w": 3},
                            {"widget": "kpi", "id": "k5y",  "label": "5Y",
                             "value": l5y, "delta": round(l5y - p5y, 3),
                             "suffix": "%", "decimals": 3, "w": 3},
                            {"widget": "kpi", "id": "k10y", "label": "10Y",
                             "value": l10, "delta": round(l10 - p10, 3),
                             "suffix": "%", "decimals": 3, "w": 3},
                            {"widget": "kpi", "id": "k30y", "label": "30Y",
                             "value": l30, "delta": round(l30 - p30, 3),
                             "suffix": "%", "decimals": 3, "w": 3},
                        ],
                        [
                            {"widget": "chart", "id": "curve", "w": 12,
                             "h_px": 380, "title": "UST yield curve",
                             "spec": {
                                 "chart_type": "multi_line",
                                 "dataset": "rates",
                                 "mapping": {"x": "date",
                                              "y": ["us_2y", "us_5y",
                                                    "us_10y", "us_30y"]},
                             }},
                        ],
                    ],
                },
                {
                    "id": "spreads", "label": "Spreads",
                    "description": "Term-structure spreads with brush cross-filter",
                    "rows": [
                        [
                            {"widget": "kpi", "id": "kspr_2s10s",
                             "label": "2s10s",
                             "value": lspr, "delta": round(lspr - pspr, 1),
                             "suffix": " bp", "decimals": 1, "w": 6},
                            {"widget": "kpi", "id": "kspr_5s30s",
                             "label": "5s30s",
                             "value": float(df["5s30s"].iloc[-1]),
                             "delta": round(float(df["5s30s"].iloc[-1] -
                                                   df["5s30s"].iloc[-2]), 1),
                             "suffix": " bp", "decimals": 1, "w": 6},
                        ],
                        [
                            {"widget": "chart", "id": "two_ten", "w": 6,
                             "h_px": 320, "title": "2s10s spread",
                             "spec": {
                                 "chart_type": "line", "dataset": "rates",
                                 "mapping": {"x": "date", "y": "2s10s"},
                             }},
                            {"widget": "chart", "id": "five_thirty", "w": 6,
                             "h_px": 320, "title": "5s30s spread",
                             "spec": {
                                 "chart_type": "line", "dataset": "rates",
                                 "mapping": {"x": "date", "y": "5s30s"},
                             }},
                        ],
                        [{"widget": "markdown", "id": "sp_notes", "w": 12,
                          "content": ("### How to use\n"
                                      "Brush (rectangle) on either spread chart "
                                      "to cross-filter the other. Both share axis "
                                      "pointer and tooltip via echarts.connect().")}],
                    ],
                },
            ],
        },
        "links": [
            {"group": "rates_ts", "members": ["curve", "two_ten", "five_thirty"],
             "sync": ["axis", "tooltip"]},
            {"group": "rates_brush", "members": ["two_ten", "five_thirty"],
             "brush": {"type": "rect", "xAxisIndex": 0}},
        ],
    }


# =============================================================================
# SCENARIO 2: CROSS-ASSET MONITOR
# =============================================================================


def scenario_cross_asset_monitor() -> Dict[str, Any]:
    xa = cross_asset_panel()
    corr = corr_long()
    spx_l, spx_p = latest_prev(xa, "spx")
    y_l, y_p = latest_prev(xa, "us_10y")
    dxy_l, dxy_p = latest_prev(xa, "dxy")
    wti_l, wti_p = latest_prev(xa, "wti")

    return {
        "schema_version": 1,
        "id": "cross_asset_monitor",
        "title": "Cross-Asset Monitor",
        "description": "Linked SPX / UST / DXY / WTI + correlation heatmap.",
        "theme": "gs_clean",
        "datasets": {
            "xa":   {"source": df_to_source(xa)},
            "corr": {"source": df_to_source(corr)},
        },
        "filters": [
            {"id": "dt", "type": "dateRange", "default": "6M",
             "targets": ["mini_*"], "field": "date", "label": "Date"},
        ],
        "layout": {
            "kind": "tabs", "cols": 12,
            "tabs": [
                {"id": "markets", "label": "Markets",
                  "description": "Linked price panels",
                  "rows": [
                      [
                          {"widget": "kpi", "id": "kpi_spx", "label": "SPX",
                           "value": round(spx_l), "delta": round(spx_l - spx_p),
                           "decimals": 0, "w": 3},
                          {"widget": "kpi", "id": "kpi_10y", "label": "US 10Y",
                           "value": y_l, "delta": round(y_l - y_p, 3),
                           "decimals": 3, "suffix": "%", "w": 3},
                          {"widget": "kpi", "id": "kpi_dxy", "label": "DXY",
                           "value": dxy_l, "delta": round(dxy_l - dxy_p, 2),
                           "decimals": 2, "w": 3},
                          {"widget": "kpi", "id": "kpi_wti", "label": "WTI",
                           "value": wti_l, "delta": round(wti_l - wti_p, 2),
                           "decimals": 2, "prefix": "$", "w": 3},
                      ],
                      [
                          {"widget": "chart", "id": "mini_spx", "w": 6, "h_px": 260,
                           "title": "S&P 500",
                           "spec": {"chart_type": "line", "dataset": "xa",
                                    "mapping": {"x": "date", "y": "spx"},}},
                          {"widget": "chart", "id": "mini_ust10y", "w": 6, "h_px": 260,
                           "title": "US 10Y",
                           "spec": {"chart_type": "line", "dataset": "xa",
                                    "mapping": {"x": "date", "y": "us_10y"},}},
                      ],
                      [
                          {"widget": "chart", "id": "mini_dxy", "w": 6, "h_px": 260,
                           "title": "DXY",
                           "spec": {"chart_type": "line", "dataset": "xa",
                                    "mapping": {"x": "date", "y": "dxy"},}},
                          {"widget": "chart", "id": "mini_wti", "w": 6, "h_px": 260,
                           "title": "WTI",
                           "spec": {"chart_type": "line", "dataset": "xa",
                                    "mapping": {"x": "date", "y": "wti"},}},
                      ],
                  ]},
                {"id": "corr", "label": "Correlations",
                  "description": "Cross-asset correlation matrix",
                  "rows": [
                      [
                          {"widget": "chart", "id": "corrmat", "w": 12, "h_px": 420,
                           "title": "Cross-asset correlation (60d)",
                           "spec": {"chart_type": "heatmap", "dataset": "corr",
                                    "mapping": {"x": "a", "y": "b",
                                                "value": "corr"},
                                    "palette": "gs_diverging"}},
                      ],
                  ]},
            ],
        },
        "links": [
            {"group": "xa_panels",
             "members": ["mini_spx", "mini_ust10y", "mini_dxy", "mini_wti"],
             "sync": ["axis", "tooltip", "dataZoom"]},
            {"group": "xa_brush",
             "members": ["mini_spx", "mini_ust10y", "mini_dxy", "mini_wti"],
             "brush": {"type": "rect", "xAxisIndex": 0}},
        ],
    }


# =============================================================================
# SCENARIO 3: TRADE FLOWS
# =============================================================================


def scenario_trade_flows() -> Dict[str, Any]:
    flows = trade_flows()
    tariffs = tariff_bars()
    share = (flows.groupby("src")["v"].sum().reset_index()
             .rename(columns={"src": "region", "v": "flow"}))
    total = int(flows["v"].sum())

    return {
        "schema_version": 1,
        "id": "trade_flows",
        "title": "Trade Flows & Tariffs",
        "description": "Bilateral trade, outbound share, tariff actions.",
        "theme": "gs_clean",
        "datasets": {
            "flows":   {"source": df_to_source(flows)},
            "tariffs": {"source": df_to_source(tariffs)},
            "share":   {"source": df_to_source(share)},
        },
        "filters": [],
        "layout": {
            "kind": "tabs", "cols": 12,
            "tabs": [
                {"id": "flows", "label": "Flows",
                  "description": "Bilateral trade flows and outbound share",
                  "rows": [
                      [
                          {"widget": "kpi", "id": "kpi_total",
                           "label": "Total flows",
                           "value": total, "suffix": " bn", "decimals": 0,
                           "sub": "USD billions", "w": 4},
                          {"widget": "kpi", "id": "kpi_largest",
                           "label": "Largest pair",
                           "value": int(flows["v"].max()),
                           "suffix": " bn", "decimals": 0,
                           "sub": "single leg", "w": 4},
                          {"widget": "kpi", "id": "kpi_count",
                           "label": "Bilateral legs",
                           "value": len(flows),
                           "sub": "5 regions", "w": 4},
                      ],
                      [
                          {"widget": "chart", "id": "sankey", "w": 8, "h_px": 420,
                           "title": "Bilateral trade flows (USD bn)",
                           "spec": {"chart_type": "sankey", "dataset": "flows",
                                    "mapping": {"source": "src", "target": "tgt",
                                                "value": "v"},}},
                          {"widget": "chart", "id": "flow_share", "w": 4, "h_px": 420,
                           "title": "Outbound flow share",
                           "spec": {"chart_type": "donut", "dataset": "share",
                                    "mapping": {"category": "region",
                                                "value": "flow"},}},
                      ],
                  ]},
                {"id": "tariffs", "label": "Tariffs",
                  "description": "Recent tariff actions by rate",
                  "rows": [
                      [{"widget": "chart", "id": "tariffs", "w": 12, "h_px": 420,
                        "title": "Tariff actions (rate, %)",
                        "spec": {"chart_type": "bar_horizontal",
                                 "dataset": "tariffs",
                                 "mapping": {"x": "rate_pct", "y": "action"},}}],
                  ]},
            ],
        },
        "links": [],
    }


# =============================================================================
# SCENARIO 4: MACRO OUTLOOK
# =============================================================================


def scenario_macro_outlook() -> Dict[str, Any]:
    path = fed_path_series()
    cpi = cpi_stack()
    jobs = jobs_panel()
    fx = fx_ohlc()
    latest_cpi = float(cpi.groupby("date")["yoy_pct"].sum().iloc[-1])
    prev_cpi = float(cpi.groupby("date")["yoy_pct"].sum().iloc[-2])
    ur_l, ur_p = latest_prev(jobs, "unemp")
    fx_l, fx_p = latest_prev(fx, "close")

    return {
        "schema_version": 1,
        "id": "macro_outlook",
        "title": "Macro Outlook",
        "description": "Policy path, inflation, labor market, FX.",
        "theme": "gs_clean",
        "datasets": {
            "path": {"source": df_to_source(path)},
            "cpi":  {"source": df_to_source(cpi)},
            "jobs": {"source": df_to_source(jobs)},
            "fx":   {"source": df_to_source(fx)},
        },
        "filters": [
            {"id": "dt", "type": "dateRange", "default": "1Y",
             "targets": ["*"], "field": "date", "label": "Date"},
        ],
        "layout": {
            "kind": "tabs", "cols": 12,
            "tabs": [
                {"id": "policy", "label": "Policy",
                  "description": "Fed funds path: history vs SEP median",
                  "rows": [
                      [
                          {"widget": "kpi", "id": "kpi_cpi", "w": 4,
                           "label": "Headline CPI y/y",
                           "value": round(latest_cpi, 2),
                           "delta": round(latest_cpi - prev_cpi, 2),
                           "suffix": "%", "decimals": 2},
                          {"widget": "kpi", "id": "kpi_unemp", "w": 4,
                           "label": "Unemployment",
                           "value": ur_l,
                           "delta": round(ur_l - ur_p, 2),
                           "suffix": "%", "decimals": 2},
                          {"widget": "kpi", "id": "kpi_eur", "w": 4,
                           "label": "EUR/USD",
                           "value": round(fx_l, 4),
                           "delta": round(fx_l - fx_p, 4),
                           "decimals": 4},
                      ],
                      [{"widget": "chart", "id": "fed_path",
                      "subtitle": '% (end-of-period)', "w": 12, "h_px": 380,
                        "title": "Fed funds path",
                        "spec": {"chart_type": "multi_line",
                                 "dataset": "path",
                                 "mapping": {"x": "date", "y": "rate",
                                             "color": "series"},}}],
                  ]},
                {"id": "infl_labor", "label": "Inflation & Labor",
                  "rows": [
                      [
                          {"widget": "chart", "id": "cpi_stack", "w": 6, "h_px": 380,
                           "title": "CPI contributions (% y/y)",
                           "spec": {"chart_type": "area", "dataset": "cpi",
                                    "mapping": {"x": "date", "y": "yoy_pct",
                                                "color": "component"},}},
                          {"widget": "chart", "id": "jobs_line", "w": 6, "h_px": 380,
                           "title": "Unemployment vs vacancies",
                           "spec": {"chart_type": "multi_line", "dataset": "jobs",
                                    "mapping": {"x": "date",
                                                "y": ["unemp", "vacancies"]},}},
                      ],
                  ]},
                {"id": "fx", "label": "FX",
                  "rows": [
                      [{"widget": "chart", "id": "eurusd", "w": 12, "h_px": 460,
                        "title": "EUR/USD",
                        "spec": {"chart_type": "candlestick", "dataset": "fx",
                                 "mapping": {"x": "date", "open": "open",
                                              "close": "close", "low": "low",
                                              "high": "high"},}}],
                  ]},
            ],
        },
        "links": [
            {"group": "macro_sync",
             "members": ["fed_path", "cpi_stack", "jobs_line"],
             "sync": ["axis", "tooltip"]},
        ],
    }


# =============================================================================
# ORCHESTRATION
# =============================================================================


SCENARIOS = [
    ("rates",  "us_rates_daily",      scenario_us_rates_daily),
    ("xa",     "cross_asset_monitor", scenario_cross_asset_monitor),
    ("trade",  "trade_flows",         scenario_trade_flows),
    ("macro",  "macro_outlook",       scenario_macro_outlook),
]


def run_one(short: str, sess_name: str, builder) -> Dict[str, Any]:
    t0 = time.time()
    sp = new_session(sess_name)
    print(f"\n>>> {sess_name} -> {sp}")
    manifest = builder()
    r = compile_dashboard(manifest, session_path=sp)
    dt = time.time() - t0
    if not r.success:
        print(f"    FAIL: {r.error_message}")
        for w in r.warnings:
            print(f"    - {w}")
    else:
        print(f"    manifest: {r.manifest_path}")
        print(f"    html    : {r.html_path}")
        print(f"    elapsed : {dt:.2f}s")
    return {"scenario": sess_name, "session": str(sp),
            "manifest": r.manifest_path, "dashboard": r.html_path,
            "success": r.success, "elapsed_s": round(dt, 2)}


def run_all() -> List[Dict[str, Any]]:
    out = []
    for short, name, fn in SCENARIOS:
        out.append(run_one(short, f"json_first_{short}", fn))
    return out


def print_summary(results: List[Dict[str, Any]]):
    print()
    print("=" * 74)
    print("JSON-first PRISM roleplay -- session summary")
    print("=" * 74)
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        print(f"\n  [{status}] {r['scenario']}")
        print(f"      session   : {r['session']}")
        print(f"      manifest  : {r['manifest']}")
        print(f"      dashboard : {r['dashboard']}")
        print(f"      elapsed   : {r['elapsed_s']}s")
    print()
    print("Open any dashboard HTML in a browser to explore. No HTML was")
    print("written by the 'author' -- only the JSON manifest.")
    print("-" * 74)


def interactive() -> int:
    print("""
JSON-first PRISM roleplay -- interactive menu

  1. us_rates_daily        UST curve + spreads + snapshot KPIs
  2. cross_asset_monitor   SPX / UST / DXY / WTI + correlation heatmap
  3. trade_flows           Sankey + donut + tariff bars
  4. macro_outlook         Fed path + CPI + jobs + EUR/USD
  a. all four
  q. quit
""")
    while True:
        choice = input("choice [a]: ").strip().lower() or "a"
        if choice == "q":
            return 0
        if choice == "a":
            print_summary(run_all())
            return 0
        try:
            idx = int(choice)
        except ValueError:
            print("  invalid choice"); continue
        if idx < 1 or idx > len(SCENARIOS):
            print("  invalid choice"); continue
        short, name, fn = SCENARIOS[idx - 1]
        print_summary([run_one(short, f"json_first_{short}", fn)])
        return 0


def demo_main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--all", action="store_true",
                    help="run every scenario and print summary")
    p.add_argument("--scenario",
                    choices=[s[0] for s in SCENARIOS],
                    help="run a single scenario (short id: rates|xa|trade|macro)")
    args = p.parse_args(argv)
    if args.all:
        print_summary(run_all())
        return 0
    if args.scenario:
        for short, name, fn in SCENARIOS:
            if short == args.scenario:
                print_summary([run_one(short, f"json_first_{short}", fn)])
                return 0
    return interactive()



def main(argv=None) -> int:
    """When samples.py is run directly, launch the PRISM roleplay demo menu."""
    return demo_main(argv)


if __name__ == "__main__":
    sys.exit(main())
