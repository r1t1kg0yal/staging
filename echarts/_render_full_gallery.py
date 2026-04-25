#!/usr/bin/env python3
"""
_render_full_gallery -- render a PNG of every chart type the ECharts
system supports, plus a few realistic finance examples and one composite,
into a single output folder with a minimal HTML index.

Run:
    python _render_full_gallery.py [--out <dir>]

Reuses samples.SAMPLES for the simple per-type fixtures and adds three
items the SAMPLES registry doesn't cover (histogram, bullet, composite).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

import pandas as pd

from echart_studio import make_echart
from composites import ChartSpec, make_4pack_grid
from rendering import save_chart_png
from samples import SAMPLES


# =============================================================================
# EXTRA SAMPLES (not in samples.SAMPLES)
# =============================================================================

def _histogram_option():
    random.seed(13)
    df = pd.DataFrame({"ret": [random.gauss(0.04, 1.1) for _ in range(2500)]})
    return make_echart(
        df,
        "histogram",
        mapping={"x": "ret", "bins": 40, "x_title": "Daily return (%)",
                  "y_title": "Frequency"},
        title="Daily SPX returns (2Y)",
    ).option


def _bullet_option():
    df = pd.DataFrame({
        "metric":  ["2s10s", "5s30s", "10Y real", "30Y BE",
                     "USD/JPY 1Y vol", "EUR-USD 5Y BE"],
        "current": [38.0, -5.0, 1.85, 2.42, 9.6, 2.31],
        "low_5y":  [-25.0, -12.0, 0.45, 1.85, 6.1, 1.62],
        "high_5y": [78.0,  82.0, 2.40, 3.05, 14.8, 2.95],
        "z":       [1.2, -1.5, 0.10, -0.4, -0.9, 1.4],
    })
    return make_echart(
        df,
        "bullet",
        mapping={"y": "metric", "x": "current",
                  "x_low": "low_5y", "x_high": "high_5y",
                  "color_by": "z"},
        title="Rates RV screen",
        dimensions="tall",
    ).option


def _multi_line_with_annotations_option():
    """Realistic UST curve example with annotations (band, vline, hline)."""
    random.seed(21)
    dates = pd.date_range("2022-01-03", "2026-04-22", freq="B")
    y2 = []
    y10 = []
    a, b = 0.5, 1.5
    for _ in range(len(dates)):
        a += random.gauss(0, 0.025)
        b += random.gauss(0, 0.020)
        y2.append(round(max(0, a + 4.0), 3))
        y10.append(round(max(0, b + 2.5), 3))
    df = pd.DataFrame({"date": dates, "us_2y": y2, "us_10y": y10})
    return make_echart(
        df,
        "multi_line",
        mapping={"x": "date", "y": ["us_2y", "us_10y"], "y_title": "Yield (%)"},
        title="UST yields with regime shading",
        subtitle="weekly",
        annotations=[
            {"type": "band", "x1": "2022-03-15", "x2": "2023-07-26",
              "label": "Hiking", "opacity": 0.18},
            {"type": "vline", "x": "2024-09-18", "label": "First cut"},
            {"type": "hline", "y": 5.0, "label": "FF target high",
              "style": "dashed", "color": "#666"},
        ],
    ).option


def _dual_axis_option():
    random.seed(33)
    dates = pd.date_range("2024-01-01", "2026-04-22", freq="B")
    spx, ism = 5000.0, 51.0
    rows = []
    for d in dates:
        spx *= 1 + random.gauss(0.0006, 0.011)
        ism += random.gauss(0, 0.18)
        rows.append({"date": d, "series": "SPX", "value": round(spx, 2)})
        rows.append({"date": d, "series": "ISM Manufacturing",
                      "value": round(max(35, min(65, ism)), 1)})
    df = pd.DataFrame(rows)
    return make_echart(
        df,
        "multi_line",
        mapping={"x": "date", "y": "value", "color": "series",
                  "dual_axis_series": ["ISM Manufacturing"],
                  "y_title": "SPX index", "y_title_right": "ISM index"},
        title="SPX vs ISM Manufacturing (dual-axis)",
    ).option


def _scatter_with_trendlines_option():
    random.seed(44)
    rows = []
    for decade in ("1990s", "2000s", "2010s", "2020s"):
        slope = {"1990s": -0.2, "2000s": -0.5, "2010s": -0.6, "2020s": -1.0}[decade]
        for _ in range(45):
            x = random.uniform(3.5, 9.0)
            y = max(-1, slope * (x - 6) + 2.4 + random.gauss(0, 0.5))
            rows.append({"u_rate": x, "core_cpi": y, "decade": decade})
    df = pd.DataFrame(rows)
    return make_echart(
        df,
        "scatter_multi",
        mapping={"x": "u_rate", "y": "core_cpi", "color": "decade",
                  "trendlines": True,
                  "x_title": "Unemployment rate (%)",
                  "y_title": "Core CPI YoY (%)"},
        title="Phillips curve by decade",
    ).option


# --- multi-axis time series (3 / 4 independent y-axes) -----------------------

def _three_axis_line_option():
    """Cross-asset line chart with 3 independent y-axes:
    SPX (left, $) | UST 10Y (right, inverted, %) | DXY (left, outer)."""
    random.seed(11)
    n = 250
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    spx, ust, dxy = [5000.0], [4.2], [104.0]
    for _ in range(n - 1):
        spx.append(spx[-1] * (1 + random.gauss(0.0005, 0.011)))
        ust.append(max(2.0, ust[-1] + random.gauss(0, 0.025)))
        dxy.append(dxy[-1] + random.gauss(0, 0.30))
    df = pd.DataFrame({"date": dates, "spx": spx, "ust": ust, "dxy": dxy})
    return make_echart(
        df,
        "multi_line",
        mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX",      "series": ["spx"],
                  "format": "compact"},
                {"side": "right", "title": "UST 10Y",  "series": ["ust"],
                  "invert": True},
                {"side": "left",  "title": "DXY",      "series": ["dxy"]},
            ],
        },
        title="3-axis: SPX (compact $) | UST 10Y (inverted) | DXY",
    ).option


def _four_axis_line_option():
    """Cross-asset line chart with 4 independent y-axes:
    SPX (L), DXY (L outer), UST 10Y (R, inverted), WTI (R outer, $)."""
    random.seed(22)
    n = 250
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    spx, ust, dxy, wti = [5000.0], [4.2], [104.0], [82.0]
    for _ in range(n - 1):
        spx.append(spx[-1] * (1 + random.gauss(0.0005, 0.011)))
        ust.append(max(2.0, ust[-1] + random.gauss(0, 0.025)))
        dxy.append(dxy[-1] + random.gauss(0, 0.30))
        wti.append(max(40, wti[-1] + random.gauss(0, 0.85)))
    df = pd.DataFrame({"date": dates, "spx": spx, "ust": ust,
                        "dxy": dxy, "wti": wti})
    return make_echart(
        df,
        "multi_line",
        mapping={
            "x": "date", "y": ["spx", "ust", "dxy", "wti"],
            "axes": [
                {"side": "left",  "title": "SPX",     "series": ["spx"],
                  "format": "compact"},
                {"side": "right", "title": "UST 10Y", "series": ["ust"],
                  "invert": True},
                {"side": "left",  "title": "DXY",     "series": ["dxy"]},
                {"side": "right", "title": "WTI",     "series": ["wti"],
                  "format": "usd"},
            ],
        },
        title="4-axis: SPX | DXY | UST (inverted) | WTI ($)",
    ).option


# --- heatmap showcase (cell labels + auto-contrast + color configuration) ----

def _heatmap_default_option():
    """Default heatmap: cell values printed with auto B/W contrast text."""
    random.seed(11)
    rows = []
    for x in ("Tech", "Fin", "Health", "Energy", "Util", "Cons"):
        for y in ("Q1", "Q2", "Q3", "Q4"):
            rows.append({"x": x, "y": y, "v": random.randint(50, 200)})
    df = pd.DataFrame(rows)
    return make_echart(
        df,
        "heatmap",
        mapping={"x": "x", "y": "y", "value": "v",
                  "color_palette": "gs_blues",
                  "value_decimals": 0},
        title="Sector quarterly volumes (auto-contrast labels, gs_blues)",
    ).option


def _heatmap_diverging_auto_option():
    """Heatmap with cross-zero data triggers auto-diverging palette."""
    random.seed(42)
    rows = []
    for x in ("Equity", "Rates", "FX", "Credit", "Commod", "Vol"):
        for y in ("1D", "1W", "1M", "3M", "YTD"):
            rows.append({"x": x, "y": y, "v": random.randint(-30, 50)})
    df = pd.DataFrame(rows)
    return make_echart(
        df,
        "heatmap",
        mapping={"x": "x", "y": "y", "value": "v",
                  "color_scale": "auto",
                  "value_decimals": 0},
        title="Cross-asset returns (color_scale=auto, diverging at zero)",
    ).option


def _heatmap_custom_palette_option():
    """Custom 3-stop palette via mapping.colors."""
    random.seed(7)
    rows = []
    for x in ("Mon", "Tue", "Wed", "Thu", "Fri"):
        for y in ("9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm"):
            rows.append({"x": x, "y": y, "v": round(random.uniform(0.1, 4.5), 1)})
    df = pd.DataFrame(rows)
    return make_echart(
        df,
        "heatmap",
        mapping={"x": "x", "y": "y", "value": "v",
                  "colors": ["#fff5e6", "#ff9933", "#cc3300"],
                  "value_decimals": 1,
                  "x_title": "Day", "y_title": "Hour"},
        title="Trading volume heatmap (custom 3-stop palette)",
    ).option


def _calendar_heatmap_with_labels_option():
    """Calendar heatmap with show_values=True for the larger-cell variant."""
    import pandas as pd
    random.seed(9)
    dates = pd.date_range("2025-09-01", "2025-12-31")
    df = pd.DataFrame({
        "date": dates,
        "v": [round(random.gauss(0.02, 1.4), 1) for _ in range(len(dates))],
    })
    return make_echart(
        df,
        "calendar_heatmap",
        mapping={"date": "date", "value": "v", "year": "2025",
                  "color_scale": "auto",
                  "show_values": True,
                  "value_label_size": 8,
                  "value_decimals": 1},
        title="Daily P&L with cell values (cross-zero, auto-diverging)",
    ).option


def _composite_4pack_option():
    """Single-artifact 4-pack composite. PNG renders all 4 sub-charts."""
    random.seed(55)
    dates = pd.date_range("2025-01-01", "2026-04-22", freq="B")
    spx = [5000.0]
    dxy = [104.0]
    wti = [82.0]
    gold = [2050.0]
    for _ in range(len(dates) - 1):
        spx.append(spx[-1] * (1 + random.gauss(0.0005, 0.011)))
        dxy.append(dxy[-1] + random.gauss(0, 0.30))
        wti.append(wti[-1] + random.gauss(0, 0.85))
        gold.append(gold[-1] * (1 + random.gauss(0.0001, 0.009)))
    df_spx = pd.DataFrame({"date": dates, "value": spx})
    df_dxy = pd.DataFrame({"date": dates, "value": dxy})
    df_wti = pd.DataFrame({"date": dates, "value": wti})
    df_au = pd.DataFrame({"date": dates, "value": gold})

    r = make_4pack_grid(
        ChartSpec(df=df_spx, chart_type="line",
                   mapping={"x": "date", "y": "value", "y_title": "SPX"},
                   title="S&P 500"),
        ChartSpec(df=df_dxy, chart_type="line",
                   mapping={"x": "date", "y": "value", "y_title": "DXY"},
                   title="DXY"),
        ChartSpec(df=df_wti, chart_type="line",
                   mapping={"x": "date", "y": "value", "y_title": "$/bbl"},
                   title="WTI"),
        ChartSpec(df=df_au, chart_type="line",
                   mapping={"x": "date", "y": "value", "y_title": "$/oz"},
                   title="Gold"),
        title="Cross-asset snapshot",
        subtitle="weekly close",
    )
    return r.option


# =============================================================================
# GALLERY ITEMS
# =============================================================================

# (id, label, kind, builder, w, h)
ITEMS: List[Tuple[str, str, str, Callable[[], Dict[str, Any]], int, int]] = [
    # --- 24 standard chart types ---
    ("01_line", "line", "core", SAMPLES["line"], 700, 360),
    ("02_multi_line", "multi_line", "core", SAMPLES["multi_line"], 700, 360),
    ("03_bar", "bar", "core", SAMPLES["bar"], 700, 360),
    ("04_bar_horizontal", "bar_horizontal", "core", SAMPLES["bar_horizontal"], 700, 360),
    ("05_stacked_bar", "stacked_bar", "core", SAMPLES["stacked_bar"], 700, 360),
    ("06_scatter", "scatter", "core", SAMPLES["scatter"], 700, 360),
    ("07_scatter_multi", "scatter_multi (groups)", "core", SAMPLES["scatter_multi"], 700, 360),
    ("08_area", "area (stacked)", "core", SAMPLES["area"], 700, 360),
    ("09_heatmap", "heatmap", "core", SAMPLES["heatmap"], 700, 360),
    ("10_histogram", "histogram", "core", _histogram_option, 700, 360),
    ("11_boxplot", "boxplot", "core", SAMPLES["boxplot"], 700, 360),
    ("12_pie", "pie", "core", SAMPLES["pie"], 600, 420),
    ("13_donut", "donut", "core", SAMPLES["donut"], 600, 420),
    ("14_bullet", "bullet (range dot)", "core", _bullet_option, 700, 420),
    ("15_candlestick", "candlestick", "core", SAMPLES["candlestick"], 700, 360),
    ("16_radar", "radar (multi-series)", "core", SAMPLES["radar"], 600, 420),
    ("17_gauge", "gauge", "core", SAMPLES["gauge"], 600, 420),
    ("18_calendar_heatmap", "calendar_heatmap", "core", SAMPLES["calendar_heatmap"], 900, 280),
    ("19_funnel", "funnel", "core", SAMPLES["funnel"], 600, 420),
    ("20_sankey", "sankey", "core", SAMPLES["sankey"], 800, 460),
    ("21_treemap", "treemap", "core", SAMPLES["treemap"], 700, 460),
    ("22_sunburst", "sunburst", "core", SAMPLES["sunburst"], 600, 460),
    ("23_graph", "graph (network)", "core", SAMPLES["graph"], 700, 460),
    ("24_parallel_coords", "parallel_coords", "core", SAMPLES["parallel_coords"], 800, 360),
    ("25_tree", "tree", "core", SAMPLES["tree"], 700, 420),

    # --- realistic PRISM-style examples ---
    ("30_annotations", "multi_line + annotations (band/vline/hline)",
      "advanced", _multi_line_with_annotations_option, 800, 380),
    ("31_dual_axis", "multi_line + dual axis",
      "advanced", _dual_axis_option, 800, 380),
    ("32_scatter_trend", "scatter_multi + per-group trendlines",
      "advanced", _scatter_with_trendlines_option, 700, 420),
    ("33_4pack_grid", "make_4pack_grid composite (single PNG)",
      "advanced", _composite_4pack_option, 1200, 800),

    # --- multi-axis time series (mapping.axes -> N independent y-axes) ---
    ("34_3_axis_line", "multi_line + 3 independent y-axes (mapping.axes)",
      "advanced", _three_axis_line_option, 1100, 420),
    ("35_4_axis_line", "multi_line + 4 independent y-axes (mapping.axes)",
      "advanced", _four_axis_line_option, 1200, 460),

    # --- heatmap showcase (cell labels + auto-contrast + color config) ---
    ("40_heatmap_default", "heatmap: default (auto-contrast text on gs_blues)",
      "heatmap", _heatmap_default_option, 800, 420),
    ("41_heatmap_diverging_auto", "heatmap: color_scale=auto on cross-zero data",
      "heatmap", _heatmap_diverging_auto_option, 800, 420),
    ("42_heatmap_custom_palette", "heatmap: custom 3-stop palette via mapping.colors",
      "heatmap", _heatmap_custom_palette_option, 800, 420),
    ("43_calendar_heatmap_labels", "calendar_heatmap: show_values=True with auto-contrast",
      "heatmap", _calendar_heatmap_with_labels_option, 1100, 320),
]


# =============================================================================
# RENDER
# =============================================================================

def _heartbeat(start: float, last: List[float], label: str) -> None:
    now = time.time()
    if now - last[0] >= 5.0:
        print(f"  ... {label} ({int(now - start)}s elapsed)", flush=True)
        last[0] = now


def render_all(out_root: Path) -> List[Dict[str, Any]]:
    out_root.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    start = time.time()
    last = [start]
    print(f"[gallery] writing to {out_root}", flush=True)
    print(f"[gallery] {len(ITEMS)} items to render", flush=True)
    for idx, (slug, label, kind, builder, w, h) in enumerate(ITEMS, 1):
        png = out_root / f"{slug}.png"
        t0 = time.time()
        try:
            opt = builder()
            save_chart_png(opt, png, width=w, height=h, scale=2)
            ok = png.is_file()
            results.append({"id": slug, "label": label, "kind": kind,
                              "png": png.name, "w": w, "h": h, "ok": ok,
                              "elapsed_s": round(time.time() - t0, 2)})
            print(f"  [{idx:2d}/{len(ITEMS)}] {slug:24s} {'OK' if ok else 'FAIL':4s} "
                  f"({results[-1]['elapsed_s']}s)", flush=True)
        except Exception as e:
            print(f"  [{idx:2d}/{len(ITEMS)}] {slug:24s} FAIL: {e}",
                  flush=True)
            results.append({"id": slug, "label": label, "kind": kind,
                              "png": None, "ok": False,
                              "error": str(e),
                              "elapsed_s": round(time.time() - t0, 2)})
        _heartbeat(start, last, "rendering")
    print(f"[gallery] done in {int(time.time() - start)}s, "
          f"{sum(1 for r in results if r['ok'])}/{len(results)} ok",
          flush=True)
    return results


# =============================================================================
# MINIMAL INDEX HTML
# =============================================================================

def write_index(results: List[Dict[str, Any]], out_root: Path) -> Path:
    n_ok = sum(1 for r in results if r["ok"])
    rows = []
    rows.append("<!doctype html>")
    rows.append("<html><head><meta charset='utf-8'>")
    rows.append("<title>GS ECharts -- full chart-type gallery</title>")
    rows.append("</head><body>")
    rows.append("<h1>GS ECharts -- full chart-type gallery</h1>")
    rows.append(f"<p>{n_ok}/{len(results)} items rendered. "
                  f"Each PNG below is one call to "
                  f"<code>make_echart(...)</code> (or "
                  f"<code>make_4pack_grid(...)</code>).</p>")
    rows.append("<hr>")
    rows.append("<h2>Core chart types (24)</h2>")
    rows.append("<ul>")
    for r in results:
        if r["kind"] != "core":
            continue
        if r["ok"]:
            rows.append(
                f"<li><b>{r['label']}</b> "
                f"(<code>{r['id']}</code>)<br>"
                f"<img src='{r['png']}' alt='{r['label']}' "
                f"style='max-width:760px'></li>")
        else:
            rows.append(
                f"<li><b>{r['label']}</b> -- FAILED: "
                f"<code>{r.get('error', '')}</code></li>")
    rows.append("</ul>")
    rows.append("<hr>")
    rows.append("<h2>Advanced examples (annotations / dual axis / "
                  "trendlines / composite)</h2>")
    rows.append("<ul>")
    for r in results:
        if r["kind"] != "advanced":
            continue
        if r["ok"]:
            rows.append(
                f"<li><b>{r['label']}</b><br>"
                f"<img src='{r['png']}' alt='{r['label']}' "
                f"style='max-width:980px'></li>")
        else:
            rows.append(
                f"<li><b>{r['label']}</b> -- FAILED: "
                f"<code>{r.get('error', '')}</code></li>")
    rows.append("</ul>")
    rows.append("<hr>")
    rows.append("<h2>Heatmap showcase (cell labels + auto-contrast + "
                  "color configuration)</h2>")
    rows.append("<p>Demonstrates the configurable heatmap features: cell "
                  "values printed by default, black/white text contrast "
                  "picked per cell from background luminance, and color "
                  "stops configurable via "
                  "<code>mapping.colors</code> / "
                  "<code>mapping.color_palette</code> / "
                  "<code>mapping.color_scale</code>.</p>")
    rows.append("<ul>")
    for r in results:
        if r["kind"] != "heatmap":
            continue
        if r["ok"]:
            rows.append(
                f"<li><b>{r['label']}</b><br>"
                f"<img src='{r['png']}' alt='{r['label']}' "
                f"style='max-width:1100px'></li>")
        else:
            rows.append(
                f"<li><b>{r['label']}</b> -- FAILED: "
                f"<code>{r.get('error', '')}</code></li>")
    rows.append("</ul>")
    rows.append("</body></html>")
    out_path = out_root / "index.html"
    out_path.write_text("\n".join(rows), encoding="utf-8")
    (out_root / "index.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    return out_path


# =============================================================================
# CLI
# =============================================================================

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=None,
                    help="output directory (default: output/gallery_<timestamp>)")
    args = p.parse_args(argv)

    if args.out:
        out_root = Path(args.out).resolve()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_root = (_here / "output" / f"gallery_{ts}").resolve()

    results = render_all(out_root)
    idx = write_index(results, out_root)
    print(f"\n[gallery] index: {idx}")
    print(f"[gallery] folder: {out_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
