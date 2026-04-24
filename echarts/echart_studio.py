#!/usr/bin/env python3
"""
echart_studio -- self-contained ECharts producer + single-chart editor.

PRODUCES ECharts "option" JSON from PRISM-style DataFrame + chart_type +
mapping inputs. Optionally wraps the option into a single-file interactive
HTML editor (knob cards, spec sheets, raw-JSON escape hatch).

Design rules:
    * Zero Python runtime deps (stdlib + pandas for DataFrame input).
    * Emitted HTML loads echarts from jsdelivr at render time.
    * No fallbacks. Unknown theme/palette/preset/chart_type raises ValueError.
    * Zero dependency on chart_studio, chart_functions, or Altair.

Library usage
-------------

    
    r = make_echart(
        df=df,
        chart_type="sankey",
        mapping={"source": "src", "target": "tgt", "value": "v"},
        title="Trade flows", theme="gs_clean", dimensions="wide",
        session_path=SP, chart_name="trade_flows",
    )
    # r.option, r.json_path, r.html_path, r.chart_id

CLI usage
---------

    python echart_studio.py                      # interactive menu
    python echart_studio.py wrap spec.json --open
    python echart_studio.py demo --matrix
    python echart_studio.py list types|themes|palettes|dimensions|knobs
    python echart_studio.py info spec.json
    python echart_studio.py test
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from config import (
    THEMES, PALETTES, DIMENSION_PRESETS, TYPOGRAPHY_OVERRIDES,
    get_theme, list_themes,
    get_palette, list_palettes, palette_colors,
    get_dimension_preset, get_typography_override, list_dimensions,
)
from rendering import render_editor_html


__version__ = "0.1.0"

# =============================================================================
# BUILDER CONTEXT + PER-TYPE BUILDERS
# =============================================================================

@dataclass
class BuilderContext:
    """Collected context passed to each chart builder."""
    chart_type: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    theme_name: str = "gs_clean"
    theme_colors: List[str] = field(default_factory=list)
    palette_name: str = "gs_primary"
    palette_colors: List[str] = field(default_factory=list)
    palette_kind: str = "categorical"
    dimension_preset: str = "wide"
    width: int = 700
    height: int = 350
    typography: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

def _df_or_none(df):
    if df is None:
        return None
    try:
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            return df
    except Exception:
        pass
    return None


def _rows(df, cols: Sequence[str]) -> List[List[Any]]:
    """Return df[cols].values as a list of plain Python rows."""
    import pandas as pd
    sub = df[list(cols)].copy()
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(sub[c]):
            sub[c] = sub[c].dt.strftime("%Y-%m-%d")
    rows = []
    for _, r in sub.iterrows():
        row = []
        for v in r:
            if v is None or (isinstance(v, float) and v != v):
                row.append(None)
            else:
                row.append(v.item() if hasattr(v, "item") else v)
        rows.append(row)
    return rows


def _unique(values: Sequence[Any]) -> List[Any]:
    seen = []
    out = []
    for v in values:
        if v in seen:
            continue
        seen.append(v)
        out.append(v)
    return out


def _ensure_columns(df, cols: Sequence[str], builder: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"{builder}: mapping references columns not present in df: {missing}. "
            f"Available: {list(df.columns)}"
        )


def _col_to_list(df, col: str) -> List[Any]:
    import pandas as pd
    ser = df[col]
    if pd.api.types.is_datetime64_any_dtype(ser):
        ser = ser.dt.strftime("%Y-%m-%d")
    out = []
    for v in ser:
        if v is None or (isinstance(v, float) and v != v):
            out.append(None)
        else:
            out.append(v.item() if hasattr(v, "item") else v)
    return out


# ---------------------------------------------------------------------------
# Shared scaffolding
# ---------------------------------------------------------------------------

def _base_option(ctx: BuilderContext) -> Dict[str, Any]:
    """Return the shared base option with title/tooltip/grid/legend scaffolding."""
    opt: Dict[str, Any] = {
        "title": {
            "text": ctx.title or "",
            "subtext": ctx.subtitle or "",
            "left": "left",
        },
        "tooltip": {"show": True, "trigger": "axis",
                     "axisPointer": {"type": "cross"}},
        # Row layout at the top of the frame:
        #   Row 1 (y=0..30):   title (left) + subtitle + toolbox (right)
        #   Row 2 (y=40..~60): legend (right-aligned, full width)
        #   Grid starts at y=80
        # Keeping the legend on its own row avoids every width-dependent
        # collision with either the title or the toolbox.
        "legend": {"show": True, "top": 42, "right": 10,
                    "orient": "horizontal", "type": "scroll"},
        "grid": {"top": 80, "right": 20, "bottom": 84, "left": 76,
                  "containLabel": True},
        "toolbox": {
            "show": True,
            "top": 8,
            "right": 10,
            "itemSize": 14,
            "itemGap": 8,
            "feature": {
                "saveAsImage": {"show": True, "title": "Save"},
                "dataZoom": {"show": True, "title": {"zoom": "Zoom", "back": "Reset zoom"}},
                "restore": {"show": True, "title": "Restore"},
            },
        },
        "animation": True,
        "animationDuration": 600,
    }
    if ctx.palette_colors and ctx.palette_kind == "categorical":
        opt["color"] = list(ctx.palette_colors)
    if ctx.typography.get("titleSize") is not None:
        opt["title"].setdefault("textStyle", {})["fontSize"] = ctx.typography["titleSize"]
    if ctx.typography.get("labelSize") is not None:
        opt["textStyle"] = {"fontSize": ctx.typography["labelSize"]}
    return opt


def _apply_typography_to_axes(opt: Dict[str, Any], ctx: BuilderContext):
    ts = ctx.typography
    if not ts:
        return
    for axis_key in ("xAxis", "yAxis"):
        axes = opt.get(axis_key)
        if axes is None:
            continue
        if isinstance(axes, dict):
            axes = [axes]
            opt[axis_key] = axes
        for ax in axes:
            al = ax.setdefault("axisLabel", {})
            if ts.get("labelSize") is not None:
                al["fontSize"] = ts["labelSize"]
            nt = ax.setdefault("nameTextStyle", {})
            if ts.get("axisTitleSize") is not None:
                nt["fontSize"] = ts["axisTitleSize"]


# ---------------------------------------------------------------------------
# Axis title / sort / dash helpers (used by multiple XY builders)
# ---------------------------------------------------------------------------

def _apply_axis_titles(opt: Dict[str, Any],
                        mapping: Dict[str, Any],
                        horizontal: bool = False) -> None:
    """Set yAxis.name / xAxis.name from mapping['y_title'] / ['x_title'].

    For horizontal=True, y_title applies to the value axis (xAxis on screen)
    and x_title applies to the category axis (yAxis on screen).

    y_title_right (if present) sets the right-axis name for dual-axis charts.

    Defaults chosen to avoid the rotated axis title colliding with wide
    tick labels (e.g. "50,000" or "2.38%"). For Y-axis the default gap
    is 52 px (was 35) and for X-axis 36 (was 30). Override per-spec
    with ``mapping.y_title_gap`` / ``mapping.x_title_gap`` or via the
    ``grid`` knob.
    """
    y_title = mapping.get("y_title")
    x_title = mapping.get("x_title")
    y_title_right = mapping.get("y_title_right")
    y_gap = mapping.get("y_title_gap", 56)
    x_gap = mapping.get("x_title_gap", 40)
    y_gap_right = mapping.get("y_title_right_gap", 52)

    def _set(axis_key: str, name: str, gap: int,
              idx: int = 0) -> None:
        ax = opt.get(axis_key)
        if isinstance(ax, list):
            if idx < len(ax):
                ax[idx]["name"] = name
                ax[idx]["nameLocation"] = "middle"
                ax[idx]["nameGap"] = gap
        elif isinstance(ax, dict):
            ax["name"] = name
            ax["nameLocation"] = "middle"
            ax["nameGap"] = gap

    if horizontal:
        # value axis is xAxis, category axis is yAxis
        if y_title:
            _set("xAxis", y_title, x_gap)
        if x_title:
            _set("yAxis", x_title, y_gap)
    else:
        if y_title:
            _set("yAxis", y_title, y_gap)
        if x_title:
            _set("xAxis", x_title, x_gap)

    if y_title_right:
        _set("yAxis", y_title_right, y_gap_right, idx=1)

    # When axis titles are set, the grid margins need to be bumped so the
    # title sits clear of axis tick labels without being clipped at the
    # canvas edge. The base grid (bottom: 84, left: 76) is sized for
    # labels-only; titles need ~40-50 more pixels in the same direction
    # because ECharts positions axis names FURTHER below the bounding
    # box than `nameGap` would suggest at face value (empirically: with
    # bottom=100 a nameGap of 40 still clips the title; bottom needs to
    # be ~120-130 for a nameGap of 40 to render fully).
    grid = opt.get("grid")
    if isinstance(grid, dict):
        if (x_title or (horizontal and y_title)):
            grid["bottom"] = max(int(grid.get("bottom", 84)), 130)
        if (y_title or (horizontal and x_title)):
            grid["left"] = max(int(grid.get("left", 76)), 100)
        if y_title_right:
            grid["right"] = max(int(grid.get("right", 20)), 76)


def _apply_x_sort(opt: Dict[str, Any],
                   mapping: Dict[str, Any],
                   axis_key: str = "xAxis") -> None:
    """If mapping['x_sort'] is an explicit list of category values, apply it
    to the named axis (xAxis by default, yAxis for horizontal bars).

    If the axis has no pre-populated category data (auto-inferred from
    series), the sort list itself becomes the category order. This avoids
    wiping out data when no existing categories are declared.
    """
    order = mapping.get("x_sort")
    if not order or not isinstance(order, (list, tuple)):
        return
    ax = opt.get(axis_key)
    if isinstance(ax, list):
        ax = ax[0] if ax else None
    if not isinstance(ax, dict):
        return
    if ax.get("type") != "category":
        return
    existing = ax.get("data") or []
    if not existing:
        ax["data"] = list(order)
        return
    ordered = [v for v in order if v in existing]
    extras = [v for v in existing if v not in order]
    ax["data"] = ordered + extras


def _style_to_dash(style: Optional[str]) -> Optional[str]:
    """Map PRISM style keyword -> ECharts lineStyle.type."""
    if not style:
        return None
    m = {"solid": "solid", "dashed": "dashed", "dotted": "dotted"}
    return m.get(str(style).lower())


def _dash_type(dash: Any, style: Optional[str] = None) -> Any:
    """Resolve a dash spec to an ECharts lineStyle.type value.

    Accepts:
        None                  -> 'solid' (or style keyword if provided)
        'solid'|'dashed'|'dotted' -> same
        [dashOn, dashOff, ...]    -> list passed through (ECharts native)
    """
    if isinstance(dash, list) and dash:
        return dash
    if isinstance(dash, str):
        return dash
    styled = _style_to_dash(style)
    return styled or "solid"


# ---------------------------------------------------------------------------
# Annotations (hline, vline, band, arrow, point)
# ---------------------------------------------------------------------------

_ANNOTATION_TYPES = {"hline", "vline", "band", "arrow", "point"}


def _apply_annotations(opt: Dict[str, Any],
                        annotations: Optional[List[Dict[str, Any]]]) -> None:
    """Attach annotations to series[0] via markLine/markArea/markPoint.

    All annotations are dicts with a 'type' key:
        hline  -> horizontal rule at y (axis='left'|'right' for dual-axis)
        vline  -> vertical rule at x
        band   -> shaded band (x1,x2) vertical or (y1,y2) horizontal
        arrow  -> directional line from (x1,y1) to (x2,y2)
        point  -> point marker at (x,y) with label

    Common keys: label, color, style ('solid'|'dashed'|'dotted'),
    stroke_dash (explicit list or string), stroke_width, label_color,
    label_position, opacity, head_size, font_size.

    Unknown 'type' values are silently skipped. Annotations on charts
    without xAxis/yAxis (pie, sankey, treemap, etc.) will be ignored by
    ECharts at render time (no axis to anchor to).
    """
    if not annotations:
        return
    series = opt.get("series")
    if not series:
        return
    if isinstance(series, dict):
        series = [series]
        opt["series"] = series
    primary = series[0]

    ml_data: List[Any] = []
    ma_data: List[List[Dict[str, Any]]] = []
    mp_data: List[Dict[str, Any]] = []

    for a in annotations or []:
        if not isinstance(a, dict):
            continue
        t = str(a.get("type", "")).lower()
        if t not in _ANNOTATION_TYPES:
            continue
        label = a.get("label")
        color = a.get("color", "#666666")
        stroke_width = a.get("stroke_width", 1.5)
        dash_val = _dash_type(a.get("stroke_dash"),
                               a.get("style", "dashed" if t in ("hline", "vline") else "solid"))
        label_color = a.get("label_color", color)
        opacity = a.get("opacity", 0.3)

        if t == "hline":
            d: Dict[str, Any] = {"yAxis": a.get("y")}
            if a.get("axis") == "right":
                d["yAxisIndex"] = 1
            if label is not None:
                d["name"] = str(label)
            d["lineStyle"] = {"color": color, "width": stroke_width,
                                "type": dash_val}
            d["label"] = ({"show": True, "formatter": str(label),
                             "color": label_color,
                             "position": a.get("label_position", "insideEndTop")}
                          if label is not None else {"show": False})
            ml_data.append(d)

        elif t == "vline":
            d = {"xAxis": a.get("x")}
            if label is not None:
                d["name"] = str(label)
            d["lineStyle"] = {"color": color, "width": stroke_width,
                                "type": dash_val}
            d["label"] = ({"show": True, "formatter": str(label),
                             "color": label_color,
                             "position": a.get("label_position", "end")}
                          if label is not None else {"show": False})
            ml_data.append(d)

        elif t == "band":
            if "x1" in a and "x2" in a:
                left: Dict[str, Any] = {"xAxis": a["x1"]}
                right: Dict[str, Any] = {"xAxis": a["x2"]}
            elif "y1" in a and "y2" in a:
                left = {"yAxis": a["y1"]}
                right = {"yAxis": a["y2"]}
            else:
                continue
            if label is not None:
                left["name"] = str(label)
            left["itemStyle"] = {"color": color, "opacity": opacity}
            if label is not None:
                left["label"] = {"show": True, "formatter": str(label),
                                  "color": label_color,
                                  "position": a.get("label_position", "insideTop")}
            ma_data.append([left, right])

        elif t == "arrow":
            d1: Dict[str, Any] = {"coord": [a.get("x1"), a.get("y1")]}
            d2: Dict[str, Any] = {"coord": [a.get("x2"), a.get("y2")]}
            d1["symbol"] = "none"
            d2["symbol"] = a.get("head_type", "arrow") if a.get("head_type", "arrow") != "none" else "none"
            d2["symbolSize"] = a.get("head_size", 10)
            d1["lineStyle"] = {"color": color, "width": stroke_width,
                                "type": dash_val}
            if label is not None:
                d1["label"] = {"show": True, "formatter": str(label),
                                "color": label_color,
                                "position": a.get("label_position", "middle")}
            else:
                d1["label"] = {"show": False}
            ml_data.append([d1, d2])

        elif t == "point":
            d = {"coord": [a.get("x"), a.get("y")]}
            d["symbol"] = a.get("symbol", "circle")
            d["symbolSize"] = a.get("symbol_size", 10)
            d["itemStyle"] = {"color": color}
            if label is not None:
                d["label"] = {"show": True, "formatter": str(label),
                                "color": label_color,
                                "fontSize": a.get("font_size", 11),
                                "position": a.get("label_position", "top")}
            else:
                d["label"] = {"show": False}
            mp_data.append(d)

    if ml_data:
        existing = primary.setdefault("markLine", {})
        existing.setdefault("symbol", ["none", "none"])
        existing.setdefault("silent", False)
        existing.setdefault("animation", False)
        existing.setdefault("data", []).extend(ml_data)
    if ma_data:
        existing = primary.setdefault("markArea", {})
        existing.setdefault("silent", True)
        existing.setdefault("animation", False)
        existing.setdefault("data", []).extend(ma_data)
    if mp_data:
        existing = primary.setdefault("markPoint", {})
        existing.setdefault("animation", False)
        existing.setdefault("data", []).extend(mp_data)


def _time_axis_if_needed(df, col: str) -> Dict[str, Any]:
    import pandas as pd
    if df is None or col not in df.columns:
        return {"type": "category", "axisLabel": {"hideOverlap": True}}
    ser = df[col]
    if pd.api.types.is_datetime64_any_dtype(ser):
        return {"type": "time",
                "axisLabel": {"hideOverlap": True, "showMinLabel": True,
                              "showMaxLabel": True}}
    if pd.api.types.is_numeric_dtype(ser):
        return {"type": "value", "axisLabel": {"hideOverlap": True}}
    return {"type": "category", "axisLabel": {"hideOverlap": True}}


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_line(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y"); color = mapping.get("color")
    if not x or not y:
        raise ValueError("line: mapping requires 'x' and 'y'")

    opt = _base_option(ctx)
    x_axis = _time_axis_if_needed(df, x) if df is not None else {"type": "category"}
    x_type_override = mapping.get("x_type")
    if x_type_override in ("category", "value", "time", "ordinal"):
        x_axis["type"] = "category" if x_type_override == "ordinal" else x_type_override
    x_axis.setdefault("name", "")
    opt["xAxis"] = x_axis

    dual = mapping.get("dual_axis_series")
    invert_right = bool(mapping.get("invert_right_axis"))
    invert_y = bool(mapping.get("invert_y"))
    y_log = bool(mapping.get("y_log"))
    x_log = bool(mapping.get("x_log"))
    y_type = "log" if y_log else "value"
    # yAxis scale=True: auto-fit range instead of always starting at 0.
    # Critical for rates, spreads, and other tight-band series.
    if dual:
        if not isinstance(dual, (list, tuple)):
            dual = [dual]
        dual_set = {str(v) for v in dual}
        opt["yAxis"] = [
            {"type": y_type, "name": "", "position": "left",
              "scale": not y_log, "inverse": invert_y,
              "axisLabel": {"hideOverlap": True}},
            {"type": y_type, "name": "", "position": "right",
              "inverse": invert_right, "scale": not y_log,
              "splitLine": {"show": False},
              "axisLabel": {"hideOverlap": True}},
        ]
    else:
        dual_set = set()
        opt["yAxis"] = {"type": y_type, "name": "",
                          "scale": not y_log, "inverse": invert_y,
                          "axisLabel": {"hideOverlap": True}}

    if x_log and opt["xAxis"].get("type") in ("value", "log"):
        opt["xAxis"]["type"] = "log"

    sd_col = mapping.get("strokeDash")
    sd_scale = mapping.get("strokeDashScale") or {}

    def _auto_dash_for(n: int, pos: int) -> Any:
        patterns = ["solid", "dashed", "dotted", [10, 5], [4, 4], [2, 2]]
        return patterns[pos % len(patterns)]

    def _dash_for(value: Any, domain: Sequence[Any]) -> Any:
        if sd_scale.get("domain") and sd_scale.get("range"):
            dom = list(sd_scale["domain"])
            rng = list(sd_scale["range"])
            if value in dom:
                idx = dom.index(value)
                if idx < len(rng):
                    return rng[idx]
        if value in list(domain):
            return _auto_dash_for(len(domain), list(domain).index(value))
        return "solid"

    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []

    # Dense time-series (more than ~30 points) look cluttered with a dot
    # on every point; keep the symbol hidden by default and let ECharts
    # expose it on hover via emphasis.
    n_points = len(df) if df is not None else 0
    show_symbol_default = mapping.get("show_symbol")
    if show_symbol_default is None:
        show_symbol_default = n_points <= 30

    def _series_entry(name: str, data: Any,
                        dash: Any = None, right: bool = False) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "type": "line", "name": name, "data": data,
            "showSymbol": bool(show_symbol_default),
            "symbolSize": 6,
            "emphasis": {"focus": "series", "scale": True},
            "lineStyle": {"width": 2},
        }
        if dash is not None:
            entry["lineStyle"]["type"] = dash
        if right:
            entry["yAxisIndex"] = 1
        return entry

    if df is None:
        data = mapping.get("data", [])
        name = mapping.get("name", "series")
        legend_names.append(name)
        series.append(_series_entry(name, data))
    else:
        _ensure_columns(df, [x], "line")
        if isinstance(y, (list, tuple)):
            _ensure_columns(df, list(y), "line")
            for i, col in enumerate(y):
                rows = _rows(df, [x, col])
                legend_names.append(col)
                right = str(col) in dual_set
                dash = _auto_dash_for(len(y), i) if sd_col is None else None
                if sd_col is None:
                    dash = None  # default: solid for simple wide-form
                series.append(_series_entry(col, rows, dash=dash, right=right))
        elif color:
            _ensure_columns(df, [y, color], "line")
            if sd_col is not None:
                _ensure_columns(df, [sd_col], "line")
            color_groups = _unique(_col_to_list(df, color))
            palette_list = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []

            if sd_col is not None:
                sd_domain = _unique(_col_to_list(df, sd_col))
                sd_legend_on = bool(mapping.get("strokeDashLegend"))
                for ci, cg in enumerate(color_groups):
                    color_hex = palette_list[ci % len(palette_list)] if palette_list else None
                    for sd_val in sd_domain:
                        sub = df[(df[color] == cg) & (df[sd_col] == sd_val)]
                        if len(sub) == 0:
                            continue
                        rows = _rows(sub, [x, y])
                        name = f"{cg} \u2014 {sd_val}"
                        right = str(cg) in dual_set
                        dash = _dash_for(sd_val, sd_domain)
                        entry = _series_entry(name, rows, dash=dash, right=right)
                        if color_hex is not None:
                            entry.setdefault("lineStyle", {})["color"] = color_hex
                            entry["itemStyle"] = {"color": color_hex}
                        series.append(entry)
                        if sd_legend_on:
                            legend_names.append(name)
                if not sd_legend_on:
                    legend_names.extend([str(g) for g in color_groups])
            else:
                for i, g in enumerate(color_groups):
                    sub = df[df[color] == g]
                    rows = _rows(sub, [x, y])
                    name = str(g)
                    legend_names.append(name)
                    right = name in dual_set
                    series.append(_series_entry(name, rows, right=right))
        else:
            _ensure_columns(df, [y], "line")
            rows = _rows(df, [x, y])
            legend_names.append(str(y))
            series.append(_series_entry(str(y), rows))

    opt["series"] = series
    opt["legend"]["data"] = legend_names

    _apply_axis_titles(opt, mapping, horizontal=False)
    _apply_x_sort(opt, mapping, axis_key="xAxis")
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_bar(df, mapping: Dict[str, Any], ctx: BuilderContext, horizontal: bool = False) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y"); color = mapping.get("color")
    if not x or not y:
        raise ValueError("bar: mapping requires 'x' and 'y'")

    stack_flag = mapping.get("stack", True)
    invert_y = bool(mapping.get("invert_y"))
    y_log = bool(mapping.get("y_log"))
    value_axis_type = "log" if y_log else "value"

    opt = _base_option(ctx)

    if horizontal:
        opt["xAxis"] = {"type": value_axis_type, "name": "",
                          "inverse": invert_y}
        opt["yAxis"] = {"type": "category", "name": "", "data": []}
        value_col = x
        category_col = y
    else:
        opt["xAxis"] = {"type": "category", "name": "", "data": []}
        opt["yAxis"] = {"type": value_axis_type, "name": "",
                          "inverse": invert_y}
        value_col = y
        category_col = x
    opt["tooltip"]["axisPointer"] = {"type": "shadow"}

    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []

    if df is None:
        data = mapping.get("data", [])
        name = mapping.get("name", "series")
        legend_names.append(name)
        if horizontal:
            opt["yAxis"]["data"] = [row[0] for row in data]
            vals = [row[1] for row in data]
        else:
            opt["xAxis"]["data"] = [row[0] for row in data]
            vals = [row[1] for row in data]
        series.append({"type": "bar", "name": name, "data": vals})
    else:
        _ensure_columns(df, [x, y], "bar")
        if color:
            _ensure_columns(df, [color], "bar")
            cat_order = _unique(_col_to_list(df, category_col))
            if horizontal:
                opt["yAxis"]["data"] = list(cat_order)
            else:
                opt["xAxis"]["data"] = list(cat_order)
            groups = _unique(_col_to_list(df, color))
            stack_name = "total" if stack_flag else None
            for g in groups:
                sub = df[df[color] == g]
                lookup = dict(zip(_col_to_list(sub, category_col), _col_to_list(sub, value_col)))
                vals = [lookup.get(c) for c in cat_order]
                legend_names.append(str(g))
                s = {"type": "bar", "name": str(g), "data": vals,
                      "emphasis": {"focus": "series"}}
                if stack_name is not None:
                    s["stack"] = stack_name
                series.append(s)
        else:
            cats = _col_to_list(df, category_col)
            vals = _col_to_list(df, value_col)
            if horizontal:
                opt["yAxis"]["data"] = cats
            else:
                opt["xAxis"]["data"] = cats
            legend_names.append(str(value_col))
            series.append({"type": "bar", "name": str(value_col), "data": vals})

    opt["series"] = series
    opt["legend"]["data"] = legend_names

    _apply_axis_titles(opt, mapping, horizontal=horizontal)
    _apply_x_sort(opt, mapping,
                    axis_key="yAxis" if horizontal else "xAxis")
    _apply_typography_to_axes(opt, ctx)
    return opt


def _linreg(xs: List[float], ys: List[float]) -> Optional[Tuple[float, float]]:
    """Simple OLS linear regression. Returns (slope, intercept) or None on
    degenerate input (fewer than 2 numeric points, or zero x-variance).
    """
    pts = [(a, b) for a, b in zip(xs, ys)
           if a is not None and b is not None
           and not (isinstance(a, float) and a != a)
           and not (isinstance(b, float) and b != b)]
    if len(pts) < 2:
        return None
    n = len(pts)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    sxx = sum(p[0] * p[0] for p in pts)
    sxy = sum(p[0] * p[1] for p in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _trendline_series(name: str, xs: List[float], ys: List[float],
                        color_hex: Optional[str] = None,
                        y_axis_index: int = 0) -> Optional[Dict[str, Any]]:
    reg = _linreg(xs, ys)
    if reg is None:
        return None
    slope, intercept = reg
    xmin = min(v for v in xs if v is not None)
    xmax = max(v for v in xs if v is not None)
    data = [[xmin, slope * xmin + intercept],
            [xmax, slope * xmax + intercept]]
    entry: Dict[str, Any] = {
        "type": "line", "name": name, "data": data,
        "showSymbol": False, "smooth": False,
        "lineStyle": {"type": "dashed", "width": 1.5,
                        "color": color_hex} if color_hex else
                      {"type": "dashed", "width": 1.5},
        "emphasis": {"focus": "none"},
        "tooltip": {"show": False},
        "silent": True,
    }
    if y_axis_index:
        entry["yAxisIndex"] = y_axis_index
    return entry


def build_scatter(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y")
    color = mapping.get("color")
    size = mapping.get("size")
    trendline = bool(mapping.get("trendline"))
    trendlines = bool(mapping.get("trendlines"))
    if not x or not y:
        raise ValueError("scatter: mapping requires 'x' and 'y'")

    invert_y = bool(mapping.get("invert_y"))
    y_log = bool(mapping.get("y_log"))
    x_log = bool(mapping.get("x_log"))
    y_type = "log" if y_log else "value"
    x_type = ("log" if x_log else
                (_time_axis_if_needed(df, x)["type"] if df is not None else "value"))

    opt = _base_option(ctx)
    opt["tooltip"]["trigger"] = "item"
    opt["xAxis"] = {"type": x_type, "name": ""}
    opt["yAxis"] = {"type": y_type, "name": "", "inverse": invert_y}

    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []

    if df is None:
        data = mapping.get("data", [])
        legend_names.append("series")
        series.append({"type": "scatter", "name": "series", "data": data,
                        "symbolSize": 10})
    else:
        _ensure_columns(df, [x, y], "scatter")
        cols = [x, y]
        if size:
            _ensure_columns(df, [size], "scatter")
        if color:
            _ensure_columns(df, [color], "scatter")
            groups = _unique(_col_to_list(df, color))
            palette = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []
            for gi, g in enumerate(groups):
                sub = df[df[color] == g]
                rows = _rows(sub, cols + ([size] if size else []))
                legend_names.append(str(g))
                s = {"type": "scatter", "name": str(g), "data": rows,
                      "emphasis": {"focus": "series"}}
                if size:
                    s["symbolSize"] = "function(val){ return Math.sqrt(Math.abs(val[2])) * 4; }"
                else:
                    s["symbolSize"] = 10
                series.append(s)
                if trendlines:
                    xs = [r[0] for r in rows if isinstance(r[0], (int, float))]
                    ys = [r[1] for r in rows if isinstance(r[1], (int, float))]
                    group_color = palette[gi % len(palette)] if palette else None
                    tl = _trendline_series(f"{g} trend", xs, ys,
                                              color_hex=group_color)
                    if tl is not None:
                        series.append(tl)
        else:
            rows = _rows(df, cols + ([size] if size else []))
            legend_names.append(str(y))
            s = {"type": "scatter", "name": str(y), "data": rows,
                  "symbolSize": 10}
            if size:
                s["symbolSize"] = "function(val){ return Math.sqrt(Math.abs(val[2])) * 4; }"
            series.append(s)

        if trendline and not trendlines:
            rows = _rows(df, [x, y])
            xs = [r[0] for r in rows if isinstance(r[0], (int, float))]
            ys = [r[1] for r in rows if isinstance(r[1], (int, float))]
            tl = _trendline_series("trend", xs, ys)
            if tl is not None:
                series.append(tl)
                legend_names.append("trend")

    opt["series"] = series
    opt["legend"]["data"] = legend_names

    _apply_axis_titles(opt, mapping, horizontal=False)
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_area(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    opt = build_line(df, mapping, ctx)
    for s in opt["series"]:
        s["areaStyle"] = {"opacity": 0.45}
        s["stack"] = "total"
        s["emphasis"] = {"focus": "series"}
        s["showSymbol"] = False
    return opt


def build_heatmap(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y"); val = mapping.get("value")
    if not x or not y or not val:
        raise ValueError("heatmap: mapping requires 'x', 'y', and 'value'")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item", "position": "top"}
    opt["legend"]["show"] = False

    if df is None:
        raise ValueError("heatmap: DataFrame is required")
    _ensure_columns(df, [x, y, val], "heatmap")

    x_cats = _unique(_col_to_list(df, x))
    y_cats = _unique(_col_to_list(df, y))
    x_idx = {v: i for i, v in enumerate(x_cats)}
    y_idx = {v: i for i, v in enumerate(y_cats)}

    cells = []
    vals = []
    for xv, yv, z in zip(_col_to_list(df, x), _col_to_list(df, y), _col_to_list(df, val)):
        if xv is None or yv is None:
            continue
        cells.append([x_idx[xv], y_idx[yv], z])
        if z is not None:
            vals.append(z)

    opt["xAxis"] = {"type": "category", "data": list(x_cats), "splitArea": {"show": True}}
    opt["yAxis"] = {"type": "category", "data": list(y_cats), "splitArea": {"show": True}}
    seq_colors = ctx.palette_colors if ctx.palette_kind != "categorical" else None
    if not seq_colors:
        seq_colors = ["#f7fbff", "#6baed6", "#08306b"]
    opt["visualMap"] = [{
        "min": min(vals) if vals else 0,
        "max": max(vals) if vals else 1,
        "calculable": True,
        "orient": "vertical",
        "right": 10,
        "top": "center",
        "inRange": {"color": list(seq_colors)},
    }]
    opt["series"] = [{
        "name": str(val), "type": "heatmap", "data": cells,
        "label": {"show": False},
        "emphasis": {"itemStyle": {"shadowBlur": 6, "shadowColor": "rgba(0,0,0,0.3)"}},
    }]
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_pie(df, mapping: Dict[str, Any], ctx: BuilderContext, donut: bool = False) -> Dict[str, Any]:
    cat = mapping.get("category"); val = mapping.get("value")
    if not cat or not val:
        raise ValueError("pie: mapping requires 'category' and 'value'")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item",
                       "formatter": "{b}: {c} ({d}%)"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    if df is None:
        raise ValueError("pie: DataFrame is required")
    _ensure_columns(df, [cat, val], "pie")

    data = [{"name": str(n), "value": v}
            for n, v in zip(_col_to_list(df, cat), _col_to_list(df, val))
            if n is not None and v is not None]

    radius = ["40%", "68%"] if donut else "68%"
    opt["series"] = [{
        "name": str(val), "type": "pie", "radius": radius,
        # Center shifted ~8% down from middle so the pie sits below the
        # row-2 legend (top: 42) without the top slice labels overlapping.
        "center": ["50%", "58%"],
        "data": data,
        "label": {"show": True, "formatter": "{b}: {d}%"},
        "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.3)"}},
    }]
    opt["legend"]["data"] = [d["name"] for d in data]
    return opt


def build_boxplot(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x"); y = mapping.get("y")
    if not x or not y:
        raise ValueError("boxplot: mapping requires 'x' (category) and 'y' (values)")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}

    if df is None:
        raise ValueError("boxplot: DataFrame is required")
    _ensure_columns(df, [x, y], "boxplot")

    groups = _unique(_col_to_list(df, x))
    box_data: List[List[float]] = []
    outliers: List[List[Any]] = []
    for i, g in enumerate(groups):
        vals = sorted(v for v in _col_to_list(df[df[x] == g], y)
                       if v is not None and not (isinstance(v, float) and v != v))
        if not vals:
            box_data.append([0, 0, 0, 0, 0])
            continue
        n = len(vals)

        def q(p):
            idx = p * (n - 1)
            lo = int(idx)
            hi = min(n - 1, lo + 1)
            frac = idx - lo
            return vals[lo] + (vals[hi] - vals[lo]) * frac

        q1 = q(0.25); q2 = q(0.5); q3 = q(0.75)
        iqr = q3 - q1
        whisk_lo = q1 - 1.5 * iqr
        whisk_hi = q3 + 1.5 * iqr
        in_vals = [v for v in vals if whisk_lo <= v <= whisk_hi]
        out_vals = [v for v in vals if v < whisk_lo or v > whisk_hi]
        lo = min(in_vals) if in_vals else q1
        hi = max(in_vals) if in_vals else q3
        box_data.append([lo, q1, q2, q3, hi])
        for ov in out_vals:
            outliers.append([i, ov])

    opt["xAxis"] = {"type": "category", "data": [str(g) for g in groups]}
    opt["yAxis"] = {"type": "value", "splitLine": {"show": True}}
    opt["series"] = [
        {"name": str(y), "type": "boxplot", "data": box_data},
        {"name": "outliers", "type": "scatter", "data": outliers,
          "symbolSize": 6, "emphasis": {"focus": "series"}},
    ]
    opt["legend"]["data"] = [str(y), "outliers"]
    _apply_typography_to_axes(opt, ctx)
    return opt


# ---------------------------------------------------------------------------
# ECharts-native builders (phase 2 types)
# ---------------------------------------------------------------------------

def build_sankey(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    s = mapping.get("source"); t = mapping.get("target"); v = mapping.get("value")
    if not s or not t or not v:
        raise ValueError("sankey: mapping requires 'source', 'target', 'value'")
    if df is None:
        raise ValueError("sankey: DataFrame is required")
    _ensure_columns(df, [s, t, v], "sankey")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    nodes = _unique(_col_to_list(df, s) + _col_to_list(df, t))
    links = [{"source": str(sv), "target": str(tv), "value": vv}
             for sv, tv, vv in zip(_col_to_list(df, s),
                                     _col_to_list(df, t),
                                     _col_to_list(df, v))
             if sv is not None and tv is not None and vv is not None]
    opt["series"] = [{
        "type": "sankey", "data": [{"name": str(n)} for n in nodes],
        "links": links,
        "emphasis": {"focus": "adjacency"},
        "lineStyle": {"color": "source", "curveness": 0.5, "opacity": 0.5},
        "label": {"show": True},
    }]
    return opt


def build_treemap(df, mapping: Dict[str, Any], ctx: BuilderContext,
                   is_sunburst: bool = False) -> Dict[str, Any]:
    path = mapping.get("path")
    name_col = mapping.get("name")
    parent_col = mapping.get("parent")
    val_col = mapping.get("value")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    if df is None:
        raise ValueError("treemap: DataFrame is required")

    if path:
        _ensure_columns(df, list(path) + [val_col] if val_col else list(path), "treemap")
        data = _hierarchy_from_path(df, path, val_col)
    elif name_col and parent_col and val_col:
        _ensure_columns(df, [name_col, parent_col, val_col], "treemap")
        data = _hierarchy_from_parent(df, name_col, parent_col, val_col)
    else:
        raise ValueError(
            "treemap/sunburst: mapping requires either 'path' (list) + 'value' "
            "OR 'name' + 'parent' + 'value'"
        )

    stype = "sunburst" if is_sunburst else "treemap"
    series = {"type": stype, "data": data}
    if is_sunburst:
        series["radius"] = ["0%", "55%"]
        series["center"] = ["50%", "55%"]
        series["top"] = 90
        series["bottom"] = 30
        series["left"] = 30
        series["right"] = 30
    else:
        series["top"] = 90
        series["bottom"] = 30
        series["left"] = 30
        series["right"] = 30
    opt["series"] = [series]
    return opt


def _hierarchy_from_path(df, path: Sequence[str], val_col: Optional[str]) -> List[Dict[str, Any]]:
    root: Dict[str, Any] = {"name": "root", "children": []}
    path_cols = list(path)
    for _, row in df.iterrows():
        node = root
        for level, pcol in enumerate(path_cols):
            label = row[pcol]
            if label is None:
                break
            label = str(label)
            existing = next((c for c in node["children"] if c["name"] == label), None)
            is_leaf = level == len(path_cols) - 1
            if existing is None:
                new_node: Dict[str, Any] = {"name": label}
                if is_leaf:
                    new_node["value"] = row[val_col] if val_col else 1
                else:
                    new_node["children"] = []
                node["children"].append(new_node)
                existing = new_node
            elif is_leaf and val_col is not None:
                existing["value"] = (existing.get("value", 0) or 0) + (row[val_col] or 0)
            node = existing if "children" in existing else node
            if is_leaf:
                break
    return root["children"]


def _hierarchy_from_parent(df, name_col: str, parent_col: str,
                             val_col: str) -> List[Dict[str, Any]]:
    by_name: Dict[Any, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        n = row[name_col]
        if n is None:
            continue
        by_name.setdefault(str(n), {"name": str(n), "children": []})
        if row[val_col] is not None:
            by_name[str(n)]["value"] = row[val_col]
    roots: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        n = row[name_col]
        if n is None:
            continue
        p = row[parent_col]
        if p is None or p == "" or str(p) == str(n):
            roots.append(by_name[str(n)])
        else:
            parent = by_name.setdefault(str(p), {"name": str(p), "children": []})
            parent.setdefault("children", []).append(by_name[str(n)])
    for node in by_name.values():
        if not node.get("children"):
            node.pop("children", None)
    return roots


def build_graph(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    nodes = mapping.get("nodes")
    edges = mapping.get("edges")
    src = mapping.get("source"); tgt = mapping.get("target"); val = mapping.get("value")
    node_id = mapping.get("node_id"); node_label = mapping.get("node_label")
    node_size = mapping.get("node_size"); node_cat = mapping.get("node_category")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    node_list: List[Dict[str, Any]] = []
    edge_list: List[Dict[str, Any]] = []

    if nodes is not None and edges is not None:
        node_list = list(nodes)
        edge_list = list(edges)
    elif df is not None and src and tgt:
        _ensure_columns(df, [src, tgt], "graph")
        ids = _unique(_col_to_list(df, src) + _col_to_list(df, tgt))
        node_list = [{"id": str(i), "name": str(i)} for i in ids]
        for a, b, vv in zip(_col_to_list(df, src), _col_to_list(df, tgt),
                             _col_to_list(df, val) if val else [None] * len(df)):
            if a is None or b is None:
                continue
            # Skip self-loops (src == tgt). A common convention is to
            # use a self-edge with value=0 to declare a node's category
            # when it only appears on the target side of real edges;
            # we don't want that ghost edge rendered.
            if a == b:
                continue
            if vv is not None:
                try:
                    if float(vv) == 0:
                        continue
                except (TypeError, ValueError):
                    pass
            e = {"source": str(a), "target": str(b)}
            if vv is not None:
                e["value"] = vv
            edge_list.append(e)
    else:
        raise ValueError(
            "graph: provide either mapping.nodes + mapping.edges, or a df with "
            "source+target column names in mapping."
        )

    categories = None
    if node_cat is not None and df is not None and node_cat in df.columns:
        cats = _unique(_col_to_list(df, node_cat))
        categories = [{"name": str(c)} for c in cats]
        cat_idx = {c: i for i, c in enumerate(cats)}
        # Build the node -> category lookup by scanning every edge
        # endpoint for which the row's category applies. The edge's
        # category field is interpreted as the source node's category,
        # so we fill sources first and then propagate from tgt only
        # when a node was never seen on the src side. Users can also
        # encode explicit per-node categories via self-edges (src==tgt).
        lookup_cat: Dict[Any, Any] = {}
        src_list = _col_to_list(df, node_id or src)
        tgt_list = _col_to_list(df, tgt)
        cat_list = _col_to_list(df, node_cat)
        for s_val, t_val, c_val in zip(src_list, tgt_list, cat_list):
            if c_val is None:
                continue
            if s_val is not None and s_val == t_val:
                # self-edge: assigns the node's own category
                lookup_cat[s_val] = c_val
                continue
            if s_val is not None and s_val not in lookup_cat:
                lookup_cat[s_val] = c_val
        # Second pass for nodes that only show up as targets -- they
        # inherit the category of their first incoming edge.
        tgt_fallback: Dict[Any, Any] = {}
        for s_val, t_val, c_val in zip(src_list, tgt_list, cat_list):
            if t_val is None or t_val in lookup_cat:
                continue
            if c_val is None:
                continue
            tgt_fallback.setdefault(t_val, c_val)
        for k, v in tgt_fallback.items():
            lookup_cat.setdefault(k, v)
        for n in node_list:
            key = n.get("id") or n.get("name")
            if key in lookup_cat:
                n["category"] = cat_idx[lookup_cat[key]]

    series = {
        "type": "graph", "layout": "force",
        "data": node_list, "edges": edge_list,
        "roam": True, "draggable": True,
        "label": {"show": True, "position": "right",
                    "distance": 4, "fontSize": 11},
        "symbolSize": 28,
        "force": {"repulsion": 800, "edgeLength": 120,
                    "gravity": 0.08, "layoutAnimation": True},
        "lineStyle": {"opacity": 0.6, "width": 1.2,
                       "curveness": 0.1},
        "emphasis": {"focus": "adjacency",
                      "lineStyle": {"width": 2.5}},
    }
    if categories:
        series["categories"] = categories
    opt["series"] = [series]
    return opt


def build_candlestick(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    x = mapping.get("x")
    o = mapping.get("open"); c = mapping.get("close")
    lo = mapping.get("low"); hi = mapping.get("high")
    if not all([x, o, c, lo, hi]):
        raise ValueError(
            "candlestick: mapping requires 'x', 'open', 'close', 'low', 'high'"
        )
    if df is None:
        raise ValueError("candlestick: DataFrame is required")
    _ensure_columns(df, [x, o, c, lo, hi], "candlestick")
    opt = _base_option(ctx)
    opt["xAxis"] = {"type": _time_axis_if_needed(df, x)["type"]}
    opt["yAxis"] = {"type": "value", "scale": True}
    ohlc = []
    dates = _col_to_list(df, x)
    if opt["xAxis"]["type"] == "category":
        opt["xAxis"]["data"] = [str(d) for d in dates]
    oo = _col_to_list(df, o); cc = _col_to_list(df, c)
    ll = _col_to_list(df, lo); hh = _col_to_list(df, hi)
    for i in range(len(dates)):
        if opt["xAxis"]["type"] == "category":
            ohlc.append([oo[i], cc[i], ll[i], hh[i]])
        else:
            ohlc.append([dates[i], oo[i], cc[i], ll[i], hh[i]])
    opt["series"] = [{"type": "candlestick", "name": "OHLC", "data": ohlc}]
    opt["legend"]["data"] = ["OHLC"]
    opt["dataZoom"] = [{"type": "inside"}, {"type": "slider"}]
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_radar(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    category = mapping.get("category")
    value = mapping.get("value")
    series_col = mapping.get("series")
    if not category or not value:
        raise ValueError("radar: mapping requires 'category' (dimension) and 'value'")
    if df is None:
        raise ValueError("radar: DataFrame is required")
    _ensure_columns(df, [category, value] + ([series_col] if series_col else []), "radar")

    opt = _base_option(ctx)
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)
    opt["tooltip"] = {"show": True, "trigger": "item"}

    dims = _unique(_col_to_list(df, category))
    max_val = max((v for v in _col_to_list(df, value) if v is not None), default=1)
    opt["radar"] = {
        "indicator": [{"name": str(d), "max": max_val * 1.2} for d in dims],
        "shape": "polygon", "splitNumber": 5,
        # Match the pie/donut shift so the top indicator label does not
        # collide with the row-2 legend.
        "center": ["50%", "58%"],
        "radius": "62%",
    }

    data: List[Dict[str, Any]] = []
    if series_col:
        groups = _unique(_col_to_list(df, series_col))
        for g in groups:
            sub = df[df[series_col] == g]
            lookup = dict(zip(_col_to_list(sub, category), _col_to_list(sub, value)))
            vals = [lookup.get(d, 0) for d in dims]
            data.append({"name": str(g), "value": vals})
    else:
        lookup = dict(zip(_col_to_list(df, category), _col_to_list(df, value)))
        vals = [lookup.get(d, 0) for d in dims]
        data.append({"name": str(value), "value": vals})

    opt["series"] = [{"type": "radar", "data": data,
                       "areaStyle": {"opacity": 0.3}}]
    opt["legend"]["data"] = [d["name"] for d in data]
    return opt


def build_gauge(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    val = mapping.get("value")
    name = mapping.get("name", "value")
    mn = mapping.get("min", 0); mx = mapping.get("max", 100)
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)
    opt["legend"]["show"] = False

    if isinstance(val, (int, float)):
        value = float(val)
    elif df is not None and isinstance(val, str):
        _ensure_columns(df, [val], "gauge")
        series = _col_to_list(df, val)
        value = float(series[-1]) if series else 0.0
    else:
        raise ValueError("gauge: mapping.value must be a number or column name")

    opt["series"] = [{
        "type": "gauge", "name": str(name),
        "min": mn, "max": mx, "splitNumber": 10,
        "progress": {"show": True, "width": 14},
        "axisLine": {"lineStyle": {"width": 14}},
        "pointer": {"show": True, "length": "60%", "width": 6},
        "title": {"show": True, "fontSize": 14},
        "detail": {"valueAnimation": True, "formatter": "{value}",
                    "fontSize": 28},
        "data": [{"value": value, "name": str(name)}],
    }]
    return opt


def build_calendar_heatmap(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    date_col = mapping.get("date"); val_col = mapping.get("value")
    if not date_col or not val_col:
        raise ValueError("calendar_heatmap: mapping requires 'date' and 'value'")
    if df is None:
        raise ValueError("calendar_heatmap: DataFrame is required")
    _ensure_columns(df, [date_col, val_col], "calendar_heatmap")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)
    opt["legend"]["show"] = False

    dates = _col_to_list(df, date_col)
    vals = _col_to_list(df, val_col)
    pairs = [[str(d), v] for d, v in zip(dates, vals) if d is not None]

    years = sorted({str(p[0])[:4] for p in pairs})
    year = mapping.get("year", years[-1] if years else "2025")
    vmin = min((p[1] for p in pairs if p[1] is not None), default=0)
    vmax = max((p[1] for p in pairs if p[1] is not None), default=1)
    seq = ctx.palette_colors if ctx.palette_kind != "categorical" else ["#f7fbff", "#6baed6", "#08306b"]

    opt["visualMap"] = [{
        "min": vmin, "max": vmax, "calculable": True,
        "orient": "horizontal", "left": "center", "top": "top",
        "inRange": {"color": list(seq)},
    }]
    opt["calendar"] = {"range": year, "cellSize": ["auto", 16],
                        "orient": "horizontal"}
    opt["series"] = [{"type": "heatmap", "coordinateSystem": "calendar",
                       "data": pairs, "name": str(val_col)}]
    return opt


def build_funnel(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    cat = mapping.get("category"); val = mapping.get("value")
    if not cat or not val:
        raise ValueError("funnel: mapping requires 'category' and 'value'")
    if df is None:
        raise ValueError("funnel: DataFrame is required")
    _ensure_columns(df, [cat, val], "funnel")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    data = [{"name": str(n), "value": v}
            for n, v in zip(_col_to_list(df, cat), _col_to_list(df, val))
            if n is not None and v is not None]
    vals = [d["value"] for d in data]
    opt["series"] = [{
        "type": "funnel", "data": data,
        "sort": "descending", "gap": 2,
        # Reserve space above for title + row-2 legend.
        "top": 80, "bottom": 20,
        # Default `min: 0` so the smallest segment still has visible
        # width. Setting min=min(vals) makes the bottom segment a
        # zero-width point.
        "min": mapping.get("min", 0),
        "max": mapping.get("max", max(vals) if vals else 100),
        "label": {"show": True, "position": "inside"},
    }]
    opt["legend"]["data"] = [d["name"] for d in data]
    return opt


def build_parallel(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    dims = mapping.get("dims")
    color = mapping.get("color")
    if not dims or not isinstance(dims, (list, tuple)):
        raise ValueError("parallel_coords: mapping requires 'dims' (list of column names)")
    if df is None:
        raise ValueError("parallel_coords: DataFrame is required")
    _ensure_columns(df, list(dims) + ([color] if color else []), "parallel_coords")

    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    axes = [{"dim": i, "name": str(d)} for i, d in enumerate(dims)]
    opt["parallelAxis"] = axes
    opt["parallel"] = {"left": "6%", "right": "6%", "top": 80, "bottom": 80}

    rows = _rows(df, list(dims))
    series: List[Dict[str, Any]] = []
    legend_names: List[str] = []
    if color:
        groups = _unique(_col_to_list(df, color))
        cols_order = list(dims)
        for g in groups:
            sub = df[df[color] == g]
            gdata = _rows(sub, cols_order)
            legend_names.append(str(g))
            series.append({"type": "parallel", "name": str(g), "data": gdata,
                            "lineStyle": {"opacity": 0.45, "width": 1.0}})
    else:
        legend_names.append("series")
        series.append({"type": "parallel", "name": "series", "data": rows,
                        "lineStyle": {"opacity": 0.45, "width": 1.0}})
    opt["series"] = series
    opt["legend"]["data"] = legend_names
    return opt


def build_tree(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    name_col = mapping.get("name") or mapping.get("node")
    parent_col = mapping.get("parent")
    if not name_col or not parent_col:
        raise ValueError("tree: mapping requires 'name' and 'parent'")
    if df is None:
        raise ValueError("tree: DataFrame is required")
    _ensure_columns(df, [name_col, parent_col], "tree")
    opt = _base_option(ctx)
    opt["tooltip"] = {"show": True, "trigger": "item"}
    opt.pop("xAxis", None); opt.pop("yAxis", None); opt.pop("grid", None)

    data = _hierarchy_from_parent(df, name_col, parent_col,
                                    mapping.get("value") or name_col)
    root = data[0] if len(data) == 1 else {"name": "root", "children": data}
    opt["series"] = [{
        "type": "tree", "data": [root], "top": "5%", "bottom": "5%",
        "left": "10%", "right": "10%",
        "layout": "orthogonal", "orient": "LR",
        "symbol": "emptyCircle", "symbolSize": 7,
        "initialTreeDepth": -1,
        "roam": True, "expandAndCollapse": True,
        "label": {"position": "left", "verticalAlign": "middle", "align": "right"},
        "leaves": {"label": {"position": "right", "verticalAlign": "middle", "align": "left"}},
    }]
    return opt


def build_histogram(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    """Bin a numeric column and render as a bar chart.

    Mapping keys:
        x       column to bin (required)
        bins    int or list of edges (default 20)
        density boolean: normalize counts to densities (default False)
        y_title, x_title: axis labels
    """
    x = mapping.get("x")
    if not x:
        raise ValueError("histogram: mapping requires 'x' (numeric column)")
    if df is None:
        raise ValueError("histogram: DataFrame is required")
    _ensure_columns(df, [x], "histogram")

    vals = [v for v in _col_to_list(df, x)
            if v is not None and not (isinstance(v, float) and v != v)]
    if not vals:
        raise ValueError(f"histogram: column '{x}' is empty")

    bins = mapping.get("bins", 20)
    if isinstance(bins, (list, tuple)):
        edges = list(bins)
    else:
        nb = max(1, int(bins))
        lo, hi = min(vals), max(vals)
        if lo == hi:
            hi = lo + 1.0
        step = (hi - lo) / nb
        edges = [lo + i * step for i in range(nb + 1)]

    counts = [0] * (len(edges) - 1)
    for v in vals:
        for i in range(len(edges) - 1):
            if v >= edges[i] and (v < edges[i + 1] or (i == len(edges) - 2 and v == edges[-1])):
                counts[i] += 1
                break

    if mapping.get("density"):
        total = sum(counts)
        if total > 0:
            widths = [edges[i + 1] - edges[i] for i in range(len(counts))]
            counts = [c / (total * w) if w > 0 else 0 for c, w in zip(counts, widths)]

    mids = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    # Short labels -- just the lower edge of each bin, rounded. The
    # verbose "a\u2013b" form was legible at 5 bins but unreadable at 30+.
    labels = [f"{edges[i]:.1f}" for i in range(len(counts))]

    opt = _base_option(ctx)
    opt["tooltip"]["axisPointer"] = {"type": "shadow"}
    # Auto-thin labels: show at most ~8 so the axis stays readable.
    # interval=0 means show every, N means skip N.
    interval = max(0, (len(labels) // 8) - 1)
    opt["xAxis"] = {"type": "category", "data": labels,
                      "axisLabel": {"interval": interval,
                                      "rotate": 0}}
    opt["yAxis"] = {"type": "value",
                      "name": "Density" if mapping.get("density") else "Count"}
    opt["series"] = [{
        "type": "bar", "name": str(x), "data": counts,
        "barCategoryGap": "2%",
    }]
    opt["legend"]["data"] = [str(x)]

    _apply_axis_titles(opt, mapping, horizontal=False)
    _apply_typography_to_axes(opt, ctx)
    return opt


def build_bullet(df, mapping: Dict[str, Any], ctx: BuilderContext) -> Dict[str, Any]:
    """Rates-RV style bullet: for each category, draw the (low, high) range
    as a pill and place a marker at the current value.

    Mapping keys:
        y       category column (required)
        x       current-value column (required)
        x_low   range-low column (required)
        x_high  range-high column (required)
        color_by column used to color the current-value dot
                 (values are interpreted as z-scores unless color_mode='palette')
        color_mode 'zscore' (default) | 'palette'
        label   optional column to annotate each row with
    """
    yc = mapping.get("y"); xc = mapping.get("x")
    low_c = mapping.get("x_low"); high_c = mapping.get("x_high")
    cb = mapping.get("color_by"); lbl_c = mapping.get("label")
    if not (yc and xc and low_c and high_c):
        raise ValueError(
            "bullet: mapping requires 'y' (category), 'x' (current), "
            "'x_low' (range_low), 'x_high' (range_high)"
        )
    if df is None:
        raise ValueError("bullet: DataFrame is required")
    need = [yc, xc, low_c, high_c] + ([cb] if cb else []) + ([lbl_c] if lbl_c else [])
    _ensure_columns(df, need, "bullet")

    categories = [str(v) for v in _col_to_list(df, yc)]
    lows = _col_to_list(df, low_c)
    highs = _col_to_list(df, high_c)
    currents = _col_to_list(df, xc)
    color_vals = _col_to_list(df, cb) if cb else [None] * len(categories)
    label_vals = _col_to_list(df, lbl_c) if lbl_c else [None] * len(categories)

    mode = mapping.get("color_mode", "zscore")

    def _z_color(z: Optional[float]) -> str:
        if z is None:
            return "#718096"
        if z >= 1.5:  return "#c53030"
        if z >= 1.0:  return "#dd6b20"
        if z >= 0.5:  return "#ecc94b"
        if z <= -1.5: return "#2b6cb0"
        if z <= -1.0: return "#3182ce"
        if z <= -0.5: return "#63b3ed"
        return "#718096"

    palette = list(ctx.palette_colors) if ctx.palette_kind == "categorical" else []

    items: List[List[Any]] = []
    for i, (cat, lo, hi, cur, cv, lbl) in enumerate(
        zip(categories, lows, highs, currents, color_vals, label_vals)
    ):
        if mode == "zscore":
            dot_color = _z_color(cv if isinstance(cv, (int, float)) else None)
        else:
            if palette:
                dot_color = palette[i % len(palette)]
            else:
                dot_color = "#002F6C"
        items.append([lo, hi, cur, dot_color,
                       str(lbl) if lbl is not None else ""])

    render_js = """function(params, api) {
  var catIdx = params.dataIndex;
  var yCenter = api.coord([0, catIdx])[1];
  var xLo = api.coord([api.value(0), catIdx])[0];
  var xHi = api.coord([api.value(1), catIdx])[0];
  var xCur = api.coord([api.value(2), catIdx])[0];
  var dotColor = api.value(3) || '#002F6C';
  var label = api.value(4) || '';
  return {
    type: 'group',
    children: [
      { type: 'rect',
        shape: { x: Math.min(xLo, xHi), y: yCenter - 8,
                 width: Math.abs(xHi - xLo), height: 16, r: 4 },
        style: { fill: '#e2e8f0', opacity: 0.85 } },
      { type: 'line',
        shape: { x1: xLo, y1: yCenter - 4, x2: xLo, y2: yCenter + 4 },
        style: { stroke: '#a0aec0', lineWidth: 2 } },
      { type: 'line',
        shape: { x1: xHi, y1: yCenter - 4, x2: xHi, y2: yCenter + 4 },
        style: { stroke: '#a0aec0', lineWidth: 2 } },
      { type: 'circle',
        shape: { cx: xCur, cy: yCenter, r: 7 },
        style: { fill: dotColor, stroke: '#fff', lineWidth: 1.5 } },
      label ? { type: 'text',
        style: { text: label, fill: '#2d3748', fontSize: 11,
                   textAlign: 'left', textVerticalAlign: 'middle',
                   x: xHi + 8, y: yCenter } } : null,
    ].filter(function(c){ return c != null; })
  };
}"""

    opt = _base_option(ctx)
    opt["tooltip"] = {
        "show": True, "trigger": "item",
        "formatter": "function(p){ return p.name + ': ' + p.value[2] + "
                       "' (range ' + p.value[0] + ', ' + p.value[1] + ')'; }",
    }
    opt["legend"]["show"] = False

    all_vals: List[float] = []
    for lo, hi, cur in zip(lows, highs, currents):
        for v in (lo, hi, cur):
            if isinstance(v, (int, float)):
                all_vals.append(float(v))
    if all_vals:
        vmin = min(all_vals)
        vmax = max(all_vals)
        pad = (vmax - vmin) * 0.05 or 1.0
    else:
        vmin, vmax, pad = 0.0, 1.0, 0.1

    opt["xAxis"] = {"type": "value",
                      "min": vmin - pad, "max": vmax + pad,
                      "splitLine": {"show": True}}
    opt["yAxis"] = {"type": "category", "data": categories,
                      "axisLine": {"show": False},
                      "axisTick": {"show": False}}
    opt["grid"]["right"] = 80

    opt["series"] = [{
        "type": "custom", "name": "bullet",
        "renderItem": render_js,
        "encode": {"x": [0, 1, 2], "y": None, "tooltip": [0, 1, 2]},
        "data": items,
    }]

    _apply_axis_titles(opt, mapping, horizontal=True)
    _apply_typography_to_axes(opt, ctx)
    return opt


# =============================================================================
# KNOB REGISTRY (for the single-chart editor HTML)
#
# A "knob" is a single editable parameter surfaced in the editor UI. Each
# knob is a dict with type, UI metadata, and either a dotted option path or
# the name of a JS apply function in editor_html.py.
# =============================================================================

UNIVERSAL_KNOBS: List[Dict[str, Any]] = [
    # Title
    {"name": "titleText", "label": "Title", "type": "text", "default": "",
     "group": "Title", "apply": "setTitleText", "essential": True},
    {"name": "subtitleText", "label": "Subtitle", "type": "text", "default": "",
     "group": "Title", "apply": "setSubtitleText"},
    {"name": "titleSize", "label": "Title size", "type": "range",
     "min": 8, "max": 40, "step": 1, "default": 18,
     "group": "Title", "path": "title.textStyle.fontSize", "essential": True},
    {"name": "titleColor", "label": "Title color", "type": "color", "default": "#000000",
     "group": "Title", "path": "title.textStyle.color"},
    {"name": "titleWeight", "label": "Title weight", "type": "select",
     "options": ["normal", "bold", "bolder"], "default": "bold",
     "group": "Title", "path": "title.textStyle.fontWeight"},
    {"name": "titleLeft", "label": "Title align", "type": "select",
     "options": ["left", "center", "right"], "default": "left",
     "group": "Title", "path": "title.left"},
    {"name": "subtitleSize", "label": "Subtitle size", "type": "range",
     "min": 6, "max": 28, "step": 1, "default": 12,
     "group": "Title", "path": "title.subtextStyle.fontSize"},
    {"name": "subtitleColor", "label": "Subtitle color", "type": "color", "default": "#333333",
     "group": "Title", "path": "title.subtextStyle.color"},

    # Typography
    {"name": "fontFamily", "label": "Font family", "type": "select",
     "options": ["Liberation Sans, Arial, sans-serif",
                  "Arial, sans-serif",
                  "Helvetica, Arial, sans-serif",
                  "Georgia, 'Times New Roman', serif",
                  "'Courier New', monospace"],
     "default": "Liberation Sans, Arial, sans-serif",
     "group": "Typography", "path": "textStyle.fontFamily"},
    {"name": "labelSize", "label": "Axis label size", "type": "range",
     "min": 6, "max": 24, "step": 1, "default": 12,
     "group": "Typography", "apply": "setAxisLabelSize"},
    {"name": "axisTitleSize", "label": "Axis title size", "type": "range",
     "min": 6, "max": 24, "step": 1, "default": 12,
     "group": "Typography", "apply": "setAxisNameSize"},
    {"name": "legendLabelSize", "label": "Legend label size", "type": "range",
     "min": 6, "max": 24, "step": 1, "default": 12,
     "group": "Typography", "path": "legend.textStyle.fontSize"},

    # Background
    {"name": "backgroundColor", "label": "Background", "type": "color", "default": "#ffffff",
     "group": "Layout", "path": "backgroundColor", "essential": True},

    # Grid
    {"name": "gridTop", "label": "Grid top", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 60,
     "group": "Grid", "path": "grid.top"},
    {"name": "gridRight", "label": "Grid right", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 20,
     "group": "Grid", "path": "grid.right"},
    {"name": "gridBottom", "label": "Grid bottom", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 60,
     "group": "Grid", "path": "grid.bottom"},
    {"name": "gridLeft", "label": "Grid left", "type": "range",
     "min": 0, "max": 200, "step": 2, "default": 60,
     "group": "Grid", "path": "grid.left"},
    {"name": "gridContainLabel", "label": "Contain axis labels", "type": "checkbox", "default": True,
     "group": "Grid", "path": "grid.containLabel"},

    # Legend
    {"name": "legendShow", "label": "Show legend", "type": "checkbox", "default": True,
     "group": "Legend", "path": "legend.show", "essential": True},
    {"name": "legendOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Legend", "path": "legend.orient", "essential": True},
    {"name": "legendPosition", "label": "Position", "type": "select",
     "options": ["top", "bottom", "left", "right", "top-left", "top-right",
                  "bottom-left", "bottom-right"], "default": "top",
     "group": "Legend", "apply": "setLegendPosition"},
    {"name": "legendItemGap", "label": "Item gap", "type": "range",
     "min": 0, "max": 40, "step": 1, "default": 10,
     "group": "Legend", "path": "legend.itemGap"},
    {"name": "legendItemWidth", "label": "Symbol width", "type": "range",
     "min": 5, "max": 40, "step": 1, "default": 20,
     "group": "Legend", "path": "legend.itemWidth"},
    {"name": "legendItemHeight", "label": "Symbol height", "type": "range",
     "min": 5, "max": 40, "step": 1, "default": 14,
     "group": "Legend", "path": "legend.itemHeight"},
    {"name": "legendIcon", "label": "Icon shape", "type": "select",
     "options": ["circle", "rect", "roundRect", "triangle", "diamond", "pin", "arrow", "none"],
     "default": "circle",
     "group": "Legend", "path": "legend.icon"},

    # Tooltip
    {"name": "tooltipShow", "label": "Show tooltip", "type": "checkbox", "default": True,
     "group": "Tooltip", "path": "tooltip.show", "essential": True},
    {"name": "tooltipTrigger", "label": "Trigger", "type": "select",
     "options": ["item", "axis", "none"], "default": "axis",
     "group": "Tooltip", "path": "tooltip.trigger"},
    {"name": "axisPointerType", "label": "Axis pointer", "type": "select",
     "options": ["line", "shadow", "cross", "none"], "default": "cross",
     "group": "Tooltip", "path": "tooltip.axisPointer.type"},
    {"name": "tooltipBackground", "label": "Background", "type": "color", "default": "#ffffff",
     "group": "Tooltip", "path": "tooltip.backgroundColor"},
    {"name": "tooltipBorderColor", "label": "Border color", "type": "color", "default": "#cccccc",
     "group": "Tooltip", "path": "tooltip.borderColor"},

    # Toolbox
    {"name": "toolboxShow", "label": "Show toolbox", "type": "checkbox", "default": True,
     "group": "Toolbox", "path": "toolbox.show"},
    {"name": "toolboxSaveAsImage", "label": "Save image btn", "type": "checkbox", "default": True,
     "group": "Toolbox", "apply": "setToolboxSaveAsImage"},
    {"name": "toolboxDataZoom", "label": "Data zoom btn", "type": "checkbox", "default": True,
     "group": "Toolbox", "apply": "setToolboxDataZoom"},
    {"name": "toolboxRestore", "label": "Restore btn", "type": "checkbox", "default": True,
     "group": "Toolbox", "apply": "setToolboxRestore"},
    {"name": "toolboxDataView", "label": "Data view btn", "type": "checkbox", "default": False,
     "group": "Toolbox", "apply": "setToolboxDataView"},
    {"name": "toolboxMagicType", "label": "Magic type btn", "type": "checkbox", "default": False,
     "group": "Toolbox", "apply": "setToolboxMagicType"},
    {"name": "toolboxBrush", "label": "Brush btn", "type": "checkbox", "default": False,
     "group": "Toolbox", "apply": "setToolboxBrush"},
    {"name": "toolboxOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Toolbox", "path": "toolbox.orient"},

    # Data zoom
    {"name": "dataZoomShow", "label": "Show dataZoom", "type": "checkbox", "default": False,
     "group": "DataZoom", "apply": "setDataZoomShow"},
    {"name": "dataZoomInside", "label": "Inside (scroll/pinch)", "type": "checkbox", "default": False,
     "group": "DataZoom", "apply": "setDataZoomInside"},
    {"name": "dataZoomStart", "label": "Start %", "type": "range",
     "min": 0, "max": 100, "step": 1, "default": 0,
     "group": "DataZoom", "apply": "setDataZoomStart"},
    {"name": "dataZoomEnd", "label": "End %", "type": "range",
     "min": 0, "max": 100, "step": 1, "default": 100,
     "group": "DataZoom", "apply": "setDataZoomEnd"},
    {"name": "dataZoomOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "DataZoom", "apply": "setDataZoomOrient"},

    # Axis pointer (global)
    {"name": "axisPointerShow", "label": "Axis pointer", "type": "checkbox", "default": True,
     "group": "Interactivity", "path": "axisPointer.show"},
    {"name": "axisPointerLineType", "label": "Pointer line", "type": "select",
     "options": ["solid", "dashed", "dotted"], "default": "solid",
     "group": "Interactivity", "path": "axisPointer.lineStyle.type"},

    # Animation
    {"name": "animation", "label": "Animation", "type": "checkbox", "default": True,
     "group": "Interactivity", "path": "animation"},
    {"name": "animationDuration", "label": "Animation ms", "type": "range",
     "min": 0, "max": 3000, "step": 100, "default": 1000,
     "group": "Interactivity", "path": "animationDuration"},
]


def _axis_knobs(axis: str) -> List[Dict[str, Any]]:
    """Return a set of axis knobs for 'x' or 'y'."""
    X = "x" if axis == "x" else "y"
    group = "XAxis" if axis == "x" else "YAxis"
    base = f"{axis}Axis[0]"
    prefix = X
    return [
        {"name": f"{prefix}AxisType", "label": "Type", "type": "select",
         "options": ["value", "category", "time", "log"], "default": "value",
         "group": group, "path": f"{base}.type"},
        {"name": f"{prefix}AxisName", "label": "Title", "type": "text", "default": "",
         "group": group, "path": f"{base}.name"},
        {"name": f"{prefix}AxisNameLocation", "label": "Title location", "type": "select",
         "options": ["start", "middle", "center", "end"], "default": "middle" if axis == "y" else "middle",
         "group": group, "path": f"{base}.nameLocation"},
        {"name": f"{prefix}AxisNameGap", "label": "Title gap", "type": "range",
         "min": 0, "max": 100, "step": 1, "default": 30,
         "group": group, "path": f"{base}.nameGap"},
        {"name": f"{prefix}AxisNameRotate", "label": "Title rotate", "type": "range",
         "min": -90, "max": 90, "step": 5, "default": 0,
         "group": group, "path": f"{base}.nameRotate"},
        {"name": f"{prefix}LabelShow", "label": "Show labels", "type": "checkbox", "default": True,
         "group": group, "path": f"{base}.axisLabel.show"},
        {"name": f"{prefix}LabelRotate", "label": "Label rotate", "type": "range",
         "min": -90, "max": 90, "step": 5, "default": 0,
         "group": group, "path": f"{base}.axisLabel.rotate"},
        {"name": f"{prefix}LabelSize", "label": "Label size", "type": "range",
         "min": 6, "max": 20, "step": 1, "default": 12,
         "group": group, "path": f"{base}.axisLabel.fontSize"},
        {"name": f"{prefix}LabelColor", "label": "Label color", "type": "color", "default": "#000000",
         "group": group, "path": f"{base}.axisLabel.color"},
        {"name": f"{prefix}LabelFormat", "label": "Label format", "type": "text", "default": "",
         "group": group, "apply": f"set{X.upper()}AxisLabelFormat"},
        {"name": f"{prefix}LineShow", "label": "Show axis line", "type": "checkbox", "default": True,
         "group": group, "path": f"{base}.axisLine.show"},
        {"name": f"{prefix}TickShow", "label": "Show ticks", "type": "checkbox", "default": True,
         "group": group, "path": f"{base}.axisTick.show"},
        {"name": f"{prefix}SplitLine", "label": "Grid lines", "type": "checkbox",
         "default": axis == "y",
         "group": group, "path": f"{base}.splitLine.show"},
        {"name": f"{prefix}SplitLineColor", "label": "Grid color", "type": "color",
         "default": "#E6E6E6",
         "group": group, "apply": f"set{X.upper()}SplitLineColor"},
        {"name": f"{prefix}Min", "label": "Min", "type": "text", "default": "",
         "group": group, "apply": f"set{X.upper()}Min"},
        {"name": f"{prefix}Max", "label": "Max", "type": "text", "default": "",
         "group": group, "apply": f"set{X.upper()}Max"},
        {"name": f"{prefix}Inverse", "label": "Invert", "type": "checkbox", "default": False,
         "group": group, "path": f"{base}.inverse"},
        {"name": f"{prefix}BoundaryGap", "label": "Boundary gap", "type": "select",
         "options": ["default", "true", "false"], "default": "default",
         "group": group, "apply": f"set{X.upper()}BoundaryGap"},
        {"name": f"{prefix}LogBase", "label": "Log base", "type": "range",
         "min": 2, "max": 10, "step": 1, "default": 10,
         "group": group, "path": f"{base}.logBase"},
    ]


XAXIS_KNOBS = _axis_knobs("x")
YAXIS_KNOBS = _axis_knobs("y")


# -- Per-chart-type knobs --

LINE_KNOBS: List[Dict[str, Any]] = [
    {"name": "lineWidth", "label": "Line width", "type": "range",
     "min": 0.5, "max": 10, "step": 0.5, "default": 2,
     "group": "Mark", "apply": "setLineWidth", "essential": True},
    {"name": "lineSmooth", "label": "Smooth", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineSmooth"},
    {"name": "lineStep", "label": "Step", "type": "select",
     "options": ["none", "start", "middle", "end"], "default": "none",
     "group": "Mark", "apply": "setLineStep"},
    {"name": "lineConnectNulls", "label": "Connect nulls", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineConnectNulls"},
    {"name": "lineShowSymbol", "label": "Show symbols", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setLineShowSymbol"},
    {"name": "lineSymbolSize", "label": "Symbol size", "type": "range",
     "min": 2, "max": 20, "step": 1, "default": 6,
     "group": "Mark", "apply": "setLineSymbolSize"},
    {"name": "lineAreaFill", "label": "Fill area", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineAreaFill"},
    {"name": "lineAreaOpacity", "label": "Area opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.3,
     "group": "Mark", "apply": "setLineAreaOpacity"},
    {"name": "lineStack", "label": "Stack", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setLineStack"},
    {"name": "lineStyleType", "label": "Line style", "type": "select",
     "options": ["solid", "dashed", "dotted"], "default": "solid",
     "group": "Mark", "apply": "setLineStyleType"},
]

BAR_KNOBS: List[Dict[str, Any]] = [
    {"name": "barWidth", "label": "Bar width", "type": "text", "default": "",
     "group": "Mark", "apply": "setBarWidth"},
    {"name": "barMaxWidth", "label": "Max bar width", "type": "text", "default": "",
     "group": "Mark", "apply": "setBarMaxWidth"},
    {"name": "barCategoryGap", "label": "Category gap", "type": "text", "default": "20%",
     "group": "Mark", "apply": "setBarCategoryGap"},
    {"name": "barGap", "label": "Bar gap (within category)", "type": "text", "default": "30%",
     "group": "Mark", "apply": "setBarGap"},
    {"name": "barBorderRadius", "label": "Corner radius", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 0,
     "group": "Mark", "apply": "setBarBorderRadius"},
    {"name": "barOpacity", "label": "Opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 1.0,
     "group": "Mark", "apply": "setBarOpacity"},
    {"name": "barStack", "label": "Stack", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setBarStack"},
    {"name": "barLabelShow", "label": "Value labels", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setBarLabelShow"},
    {"name": "barLabelPosition", "label": "Label position", "type": "select",
     "options": ["top", "inside", "insideTop", "insideBottom", "bottom"], "default": "top",
     "group": "Mark", "apply": "setBarLabelPosition"},
]

SCATTER_KNOBS: List[Dict[str, Any]] = [
    {"name": "scatterSymbolSize", "label": "Symbol size", "type": "range",
     "min": 2, "max": 60, "step": 1, "default": 10,
     "group": "Mark", "apply": "setScatterSymbolSize", "essential": True},
    {"name": "scatterSymbol", "label": "Symbol", "type": "select",
     "options": ["circle", "rect", "roundRect", "triangle", "diamond", "pin", "arrow"],
     "default": "circle",
     "group": "Mark", "apply": "setScatterSymbol"},
    {"name": "scatterOpacity", "label": "Opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.8,
     "group": "Mark", "apply": "setScatterOpacity"},
    {"name": "scatterBorderWidth", "label": "Border width", "type": "range",
     "min": 0, "max": 6, "step": 0.5, "default": 0,
     "group": "Mark", "apply": "setScatterBorderWidth"},
]

AREA_KNOBS: List[Dict[str, Any]] = [
    {"name": "areaOpacity", "label": "Area opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.6,
     "group": "Mark", "apply": "setAreaOpacity"},
    {"name": "areaStack", "label": "Stack", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setAreaStack"},
    {"name": "areaLineWidth", "label": "Border width", "type": "range",
     "min": 0, "max": 5, "step": 0.5, "default": 1.0,
     "group": "Mark", "apply": "setAreaLineWidth"},
    {"name": "areaSmooth", "label": "Smooth", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setAreaSmooth"},
]

HEATMAP_KNOBS: List[Dict[str, Any]] = [
    {"name": "heatmapShowLabels", "label": "Cell labels", "type": "checkbox", "default": False,
     "group": "Mark", "apply": "setHeatmapShowLabels"},
    {"name": "heatmapBorderWidth", "label": "Cell border", "type": "range",
     "min": 0, "max": 4, "step": 0.5, "default": 0,
     "group": "Mark", "apply": "setHeatmapBorderWidth"},
    {"name": "visualMapShow", "label": "Show visual map", "type": "checkbox", "default": True,
     "group": "VisualMap", "path": "visualMap[0].show"},
    {"name": "visualMapOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "vertical",
     "group": "VisualMap", "path": "visualMap[0].orient"},
    {"name": "visualMapCalculable", "label": "Calculable", "type": "checkbox", "default": True,
     "group": "VisualMap", "path": "visualMap[0].calculable"},
]

PIE_KNOBS: List[Dict[str, Any]] = [
    {"name": "pieInnerRadius", "label": "Inner radius", "type": "text", "default": "0%",
     "group": "Mark", "apply": "setPieInnerRadius"},
    {"name": "pieOuterRadius", "label": "Outer radius", "type": "text", "default": "75%",
     "group": "Mark", "apply": "setPieOuterRadius"},
    {"name": "pieRoseType", "label": "Rose type", "type": "select",
     "options": ["none", "radius", "area"], "default": "none",
     "group": "Mark", "apply": "setPieRoseType"},
    {"name": "pieLabelShow", "label": "Labels", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setPieLabelShow"},
    {"name": "pieLabelPosition", "label": "Label position", "type": "select",
     "options": ["outside", "inside", "center"], "default": "outside",
     "group": "Mark", "apply": "setPieLabelPosition"},
    {"name": "pieLabelLine", "label": "Label leader line", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setPieLabelLine"},
    {"name": "pieBorderRadius", "label": "Slice corner radius", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 0,
     "group": "Mark", "apply": "setPieBorderRadius"},
]

BOXPLOT_KNOBS: List[Dict[str, Any]] = [
    {"name": "boxBorderWidth", "label": "Border width", "type": "range",
     "min": 0.5, "max": 4, "step": 0.5, "default": 1.0,
     "group": "Mark", "apply": "setBoxBorderWidth"},
    {"name": "boxItemWidth", "label": "Box width", "type": "range",
     "min": 4, "max": 60, "step": 1, "default": 20,
     "group": "Mark", "apply": "setBoxItemWidth"},
]

SANKEY_KNOBS: List[Dict[str, Any]] = [
    {"name": "sankeyNodeWidth", "label": "Node width", "type": "range",
     "min": 5, "max": 40, "step": 1, "default": 20,
     "group": "Mark", "apply": "setSankeyNodeWidth"},
    {"name": "sankeyNodeGap", "label": "Node gap", "type": "range",
     "min": 2, "max": 40, "step": 1, "default": 8,
     "group": "Mark", "apply": "setSankeyNodeGap"},
    {"name": "sankeyOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Mark", "apply": "setSankeyOrient"},
    {"name": "sankeyLinkOpacity", "label": "Link opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.5,
     "group": "Mark", "apply": "setSankeyLinkOpacity"},
    {"name": "sankeyLinkCurveness", "label": "Link curveness", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.5,
     "group": "Mark", "apply": "setSankeyLinkCurveness"},
    {"name": "sankeyDraggable", "label": "Draggable nodes", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setSankeyDraggable"},
]

TREEMAP_KNOBS: List[Dict[str, Any]] = [
    {"name": "treemapLeafDepth", "label": "Leaf depth", "type": "range",
     "min": 1, "max": 8, "step": 1, "default": 1,
     "group": "Mark", "apply": "setTreemapLeafDepth"},
    {"name": "treemapRoam", "label": "Roam", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setTreemapRoam"},
    {"name": "treemapNodeClick", "label": "Node click", "type": "select",
     "options": ["zoomToNode", "link", "false"], "default": "zoomToNode",
     "group": "Mark", "apply": "setTreemapNodeClick"},
]

SUNBURST_KNOBS: List[Dict[str, Any]] = [
    {"name": "sunburstInnerRadius", "label": "Inner radius", "type": "text", "default": "0%",
     "group": "Mark", "apply": "setSunburstInnerRadius"},
    {"name": "sunburstOuterRadius", "label": "Outer radius", "type": "text", "default": "90%",
     "group": "Mark", "apply": "setSunburstOuterRadius"},
    {"name": "sunburstHighlightPolicy", "label": "Highlight", "type": "select",
     "options": ["descendant", "ancestor", "self", "none"], "default": "descendant",
     "group": "Mark", "apply": "setSunburstHighlightPolicy"},
]

GRAPH_KNOBS: List[Dict[str, Any]] = [
    {"name": "graphLayout", "label": "Layout", "type": "select",
     "options": ["none", "force", "circular"], "default": "force",
     "group": "Mark", "apply": "setGraphLayout"},
    {"name": "graphRoam", "label": "Roam", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setGraphRoam"},
    {"name": "graphRepulsion", "label": "Repulsion (force)", "type": "range",
     "min": 20, "max": 2000, "step": 20, "default": 200,
     "group": "Mark", "apply": "setGraphRepulsion"},
    {"name": "graphEdgeLength", "label": "Edge length (force)", "type": "range",
     "min": 10, "max": 400, "step": 10, "default": 80,
     "group": "Mark", "apply": "setGraphEdgeLength"},
    {"name": "graphEdgeSymbol", "label": "Edge symbol", "type": "select",
     "options": ["none", "arrow", "circle"], "default": "none",
     "group": "Mark", "apply": "setGraphEdgeSymbol"},
    {"name": "graphDraggable", "label": "Draggable", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setGraphDraggable"},
]

CANDLE_KNOBS: List[Dict[str, Any]] = [
    {"name": "candleBullColor", "label": "Bull color", "type": "color", "default": "#c23531",
     "group": "Mark", "apply": "setCandleBullColor"},
    {"name": "candleBearColor", "label": "Bear color", "type": "color", "default": "#314656",
     "group": "Mark", "apply": "setCandleBearColor"},
    {"name": "candleBorderBull", "label": "Border bull", "type": "color", "default": "#c23531",
     "group": "Mark", "apply": "setCandleBorderBull"},
    {"name": "candleBorderBear", "label": "Border bear", "type": "color", "default": "#314656",
     "group": "Mark", "apply": "setCandleBorderBear"},
]

RADAR_KNOBS: List[Dict[str, Any]] = [
    {"name": "radarShape", "label": "Shape", "type": "select",
     "options": ["polygon", "circle"], "default": "polygon",
     "group": "Mark", "apply": "setRadarShape"},
    {"name": "radarSplitNumber", "label": "Split number", "type": "range",
     "min": 2, "max": 10, "step": 1, "default": 5,
     "group": "Mark", "apply": "setRadarSplitNumber"},
    {"name": "radarAreaOpacity", "label": "Area opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.3,
     "group": "Mark", "apply": "setRadarAreaOpacity"},
]

GAUGE_KNOBS: List[Dict[str, Any]] = [
    {"name": "gaugeMin", "label": "Min", "type": "number", "default": 0,
     "group": "Mark", "apply": "setGaugeMin"},
    {"name": "gaugeMax", "label": "Max", "type": "number", "default": 100,
     "group": "Mark", "apply": "setGaugeMax"},
    {"name": "gaugeSplitNumber", "label": "Split number", "type": "range",
     "min": 2, "max": 20, "step": 1, "default": 10,
     "group": "Mark", "apply": "setGaugeSplitNumber"},
    {"name": "gaugeStartAngle", "label": "Start angle", "type": "range",
     "min": -180, "max": 360, "step": 5, "default": 225,
     "group": "Mark", "apply": "setGaugeStartAngle"},
    {"name": "gaugeEndAngle", "label": "End angle", "type": "range",
     "min": -180, "max": 360, "step": 5, "default": -45,
     "group": "Mark", "apply": "setGaugeEndAngle"},
]

CALENDAR_KNOBS: List[Dict[str, Any]] = [
    {"name": "calendarOrient", "label": "Orient", "type": "select",
     "options": ["horizontal", "vertical"], "default": "horizontal",
     "group": "Mark", "apply": "setCalendarOrient"},
    {"name": "calendarCellSize", "label": "Cell size", "type": "range",
     "min": 8, "max": 40, "step": 1, "default": 16,
     "group": "Mark", "apply": "setCalendarCellSize"},
    {"name": "calendarYearLabel", "label": "Year label", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setCalendarYearLabel"},
]

PARALLEL_KNOBS: List[Dict[str, Any]] = [
    {"name": "parallelLineOpacity", "label": "Line opacity", "type": "range",
     "min": 0, "max": 1, "step": 0.05, "default": 0.45,
     "group": "Mark", "apply": "setParallelLineOpacity"},
    {"name": "parallelLineWidth", "label": "Line width", "type": "range",
     "min": 0.5, "max": 5, "step": 0.5, "default": 1.0,
     "group": "Mark", "apply": "setParallelLineWidth"},
    {"name": "parallelLayoutHorizontal", "label": "Horizontal", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setParallelLayoutHorizontal"},
]

FUNNEL_KNOBS: List[Dict[str, Any]] = [
    {"name": "funnelSort", "label": "Sort", "type": "select",
     "options": ["descending", "ascending", "none"], "default": "descending",
     "group": "Mark", "apply": "setFunnelSort"},
    {"name": "funnelGap", "label": "Gap", "type": "range",
     "min": 0, "max": 20, "step": 1, "default": 2,
     "group": "Mark", "apply": "setFunnelGap"},
    {"name": "funnelMin", "label": "Min", "type": "number", "default": 0,
     "group": "Mark", "apply": "setFunnelMin"},
    {"name": "funnelMax", "label": "Max", "type": "number", "default": 100,
     "group": "Mark", "apply": "setFunnelMax"},
    {"name": "funnelLabelShow", "label": "Labels", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setFunnelLabelShow"},
]

TREE_KNOBS: List[Dict[str, Any]] = [
    {"name": "treeOrient", "label": "Orient", "type": "select",
     "options": ["LR", "RL", "TB", "BT", "radial"], "default": "LR",
     "group": "Mark", "apply": "setTreeOrient"},
    {"name": "treeSymbolSize", "label": "Symbol size", "type": "range",
     "min": 4, "max": 30, "step": 1, "default": 7,
     "group": "Mark", "apply": "setTreeSymbolSize"},
    {"name": "treeRoam", "label": "Roam", "type": "checkbox", "default": True,
     "group": "Mark", "apply": "setTreeRoam"},
]


MARK_KNOB_MAP: Dict[str, List[Dict[str, Any]]] = {
    "line":             LINE_KNOBS,
    "multi_line":       LINE_KNOBS,
    "bar":              BAR_KNOBS,
    "bar_horizontal":   BAR_KNOBS,
    "scatter":          SCATTER_KNOBS,
    "scatter_multi":    SCATTER_KNOBS,
    "area":             AREA_KNOBS,
    "heatmap":          HEATMAP_KNOBS,
    "pie":              PIE_KNOBS,
    "donut":            PIE_KNOBS,
    "boxplot":          BOXPLOT_KNOBS,
    "sankey":           SANKEY_KNOBS,
    "treemap":          TREEMAP_KNOBS,
    "sunburst":         SUNBURST_KNOBS,
    "graph":            GRAPH_KNOBS,
    "candlestick":      CANDLE_KNOBS,
    "radar":            RADAR_KNOBS,
    "gauge":            GAUGE_KNOBS,
    "calendar_heatmap": CALENDAR_KNOBS,
    "parallel_coords":  PARALLEL_KNOBS,
    "funnel":           FUNNEL_KNOBS,
    "tree":             TREE_KNOBS,
    "raw":              [],
}


# Subset of universal knobs that get duplicated into Essentials for quick access.
ESSENTIAL_NAMES = {
    "titleText", "titleSize",
    "backgroundColor",
    "legendShow", "legendOrient",
    "tooltipShow",
}


def knobs_for(chart_type: str) -> List[Dict[str, Any]]:
    """Return the full knob list for a chart type: universal + axes + mark."""
    if chart_type not in MARK_KNOB_MAP:
        raise ValueError(
            f"Unknown chart_type '{chart_type}'. "
            f"Available: {', '.join(sorted(MARK_KNOB_MAP.keys()))}"
        )
    mark = MARK_KNOB_MAP[chart_type]
    if chart_type in ("pie", "donut", "radar", "gauge", "sankey", "treemap",
                       "sunburst", "graph", "calendar_heatmap", "funnel",
                       "parallel_coords", "tree"):
        axes: List[Dict[str, Any]] = []
    else:
        axes = XAXIS_KNOBS + YAXIS_KNOBS
    return list(UNIVERSAL_KNOBS) + list(axes) + list(mark)


def essentials(chart_type: str) -> List[Dict[str, Any]]:
    """Return an 'Essentials' card subset."""
    all_knobs = knobs_for(chart_type)
    out: List[Dict[str, Any]] = []
    for k in all_knobs:
        if k.get("essential") or k["name"] in ESSENTIAL_NAMES:
            out.append(k)
    return out


def list_chart_types() -> List[str]:
    return sorted(MARK_KNOB_MAP.keys())


def knob_count(chart_type: str) -> Tuple[int, int, int]:
    """Return (universal, axes, mark) knob counts for a type."""
    if chart_type not in MARK_KNOB_MAP:
        raise ValueError(f"Unknown chart_type '{chart_type}'")
    universal = len(UNIVERSAL_KNOBS)
    has_axes = chart_type not in ("pie", "donut", "radar", "gauge", "sankey",
                                    "treemap", "sunburst", "graph",
                                    "calendar_heatmap", "funnel",
                                    "parallel_coords", "tree")
    axes = (len(XAXIS_KNOBS) + len(YAXIS_KNOBS)) if has_axes else 0
    mark = len(MARK_KNOB_MAP[chart_type])
    return universal, axes, mark



# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class EChartResult:
    """Result of make_echart() / wrap_echart().

    Mirrors PRISM's ChartResult shape so it plugs into existing handlers
    including check_charts_quality() which reads `.png_path`.
    """
    option: Dict[str, Any]
    chart_id: str
    chart_type: str
    theme: str
    palette: str
    dimension_preset: str
    width: int
    height: int
    json_path: Optional[str] = None
    html_path: Optional[str] = None
    html: Optional[str] = None
    png_path: Optional[str] = None
    original_png_path: Optional[str] = None
    download_url: Optional[str] = None
    editor_download_url: Optional[str] = None
    editor_html_path: Optional[str] = None
    editor_chart_id: Optional[str] = None
    success: bool = True
    success_bool: bool = True  # legacy alias
    annotated: bool = False
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    knob_names: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.success_bool = self.success
        if self.html_path and not self.editor_html_path:
            self.editor_html_path = self.html_path
        if self.chart_id and not self.editor_chart_id:
            self.editor_chart_id = self.chart_id

    def save_png(
        self,
        path: Union[str, Path],
        *,
        scale: int = 2,
        width: Optional[int] = None,
        height: Optional[int] = None,
        background: str = "#ffffff",
    ) -> Path:
        """Render this chart's option to PNG via headless Chrome and record
        the absolute path on self.png_path for downstream consumers (e.g.
        check_charts_quality).

        Requires a system Chrome/Chromium binary. Raises RuntimeError if
        Chrome is unavailable.
        """
        from rendering import save_chart_png
        p = save_chart_png(
            self.option, path,
            width=int(width if width is not None else self.width),
            height=int(height if height is not None else self.height),
            theme=self.theme,
            scale=scale,
            background=background,
        )
        self.png_path = str(p)
        return p


@dataclass
class EChartSpecSheet:
    """Named bundle of user preferences -- saved via the editor, applied on
    load. Stores styling only (title/subtitle text are chart-specific content,
    not user prefs)."""
    spec_sheet_id: str
    name: str
    description: str = ""
    owner: str = ""
    scope: str = "global"
    base_theme: str = "gs_clean"
    base_palette: str = "gs_primary"
    base_dimension_preset: str = "wide"
    overrides: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def new(cls, name: str, **kwargs) -> "EChartSpecSheet":
        now = datetime.now(timezone.utc).isoformat()
        slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "sheet"
        return cls(
            spec_sheet_id=kwargs.pop("spec_sheet_id", slug),
            name=name, created_at=now, updated_at=now, **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EChartSpecSheet":
        return cls(**d)

    @classmethod
    def from_json(cls, s: str) -> "EChartSpecSheet":
        return cls.from_dict(json.loads(s))


# =============================================================================
# CORE HELPERS
# =============================================================================


def _compute_chart_id(option: Dict[str, Any]) -> str:
    canonical = json.dumps(option, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(canonical).hexdigest()[:12]


def _slug(s: Optional[str]) -> str:
    if not s:
        return "chart"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return slug or "chart"


def _coerce_option(option: Any) -> Dict[str, Any]:
    if isinstance(option, dict):
        return option
    if isinstance(option, str):
        return json.loads(option)
    raise TypeError(
        f"Cannot coerce {type(option).__name__} to ECharts option dict. "
        "Pass a dict or JSON string."
    )


def validate_option(option: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Minimal structural check on an ECharts option. Returns (ok, warnings).

    ok is True only when the option is a dict containing a non-empty `series`
    entry whose members each have a `type` field.
    """
    warnings: List[str] = []
    if not isinstance(option, dict):
        return False, ["option must be a dict"]
    series = option.get("series")
    if series is None:
        warnings.append("option has no 'series'")
        return False, warnings
    if isinstance(series, dict):
        if "type" not in series:
            warnings.append("option.series missing 'type'")
            return False, warnings
        return True, warnings
    if isinstance(series, list):
        if not series:
            warnings.append("option.series is empty")
            return False, warnings
        for i, s in enumerate(series):
            if not isinstance(s, dict):
                warnings.append(f"option.series[{i}] is not a dict")
                return False, warnings
            if "type" not in s:
                warnings.append(f"option.series[{i}] missing 'type'")
                return False, warnings
        return True, warnings
    warnings.append("option.series must be a dict or list")
    return False, warnings


# =============================================================================
# BUILDER DISPATCH
# =============================================================================


_BUILDER_DISPATCH = {
    "line":              lambda df, m, c: build_line(df, m, c),
    "multi_line":        lambda df, m, c: build_line(df, m, c),
    "bar":               lambda df, m, c: build_bar(df, m, c, horizontal=False),
    "bar_horizontal":    lambda df, m, c: build_bar(df, m, c, horizontal=True),
    "scatter":           lambda df, m, c: build_scatter(df, m, c),
    "scatter_multi":     lambda df, m, c: build_scatter(df, m, c),
    "area":              lambda df, m, c: build_area(df, m, c),
    "heatmap":           lambda df, m, c: build_heatmap(df, m, c),
    "pie":               lambda df, m, c: build_pie(df, m, c, donut=False),
    "donut":             lambda df, m, c: build_pie(df, m, c, donut=True),
    "boxplot":           lambda df, m, c: build_boxplot(df, m, c),
    "histogram":         lambda df, m, c: build_histogram(df, m, c),
    "bullet":            lambda df, m, c: build_bullet(df, m, c),
    "sankey":            lambda df, m, c: build_sankey(df, m, c),
    "treemap":           lambda df, m, c: build_treemap(df, m, c, is_sunburst=False),
    "sunburst":          lambda df, m, c: build_treemap(df, m, c, is_sunburst=True),
    "graph":             lambda df, m, c: build_graph(df, m, c),
    "candlestick":       lambda df, m, c: build_candlestick(df, m, c),
    "radar":             lambda df, m, c: build_radar(df, m, c),
    "gauge":             lambda df, m, c: build_gauge(df, m, c),
    "calendar_heatmap":  lambda df, m, c: build_calendar_heatmap(df, m, c),
    "funnel":            lambda df, m, c: build_funnel(df, m, c),
    "parallel_coords":   lambda df, m, c: build_parallel(df, m, c),
    "tree":              lambda df, m, c: build_tree(df, m, c),
}


def _build_context(
    chart_type: str,
    theme: str,
    palette: Optional[str],
    dimensions: str,
    title: Optional[str],
    subtitle: Optional[str],
) -> BuilderContext:
    theme_obj = get_theme(theme)
    palette_name = palette or theme_obj["palette"]
    palette_obj = get_palette(palette_name)
    dim = get_dimension_preset(dimensions)
    typography = get_typography_override(dimensions)

    return BuilderContext(
        chart_type=chart_type,
        title=title,
        subtitle=subtitle,
        theme_name=theme,
        theme_colors=list(theme_obj["echarts"].get("color", [])),
        palette_name=palette_name,
        palette_colors=list(palette_obj["colors"]),
        palette_kind=palette_obj["kind"],
        dimension_preset=dimensions,
        width=dim["width"],
        height=dim["height"],
        typography=typography,
    )


# =============================================================================
# PUBLIC API
# =============================================================================


def make_echart(
    df: Any = None,
    chart_type: str = "line",
    mapping: Optional[Dict[str, Any]] = None,
    option: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    theme: str = "gs_clean",
    palette: Optional[str] = None,
    dimensions: str = "wide",
    annotations: Optional[List[Dict[str, Any]]] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None,
    save_as: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    save_png: bool = False,
    png_scale: int = 2,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
) -> EChartResult:
    """Produce an ECharts option from a DataFrame and mapping.

    Two paths:
        (a) df + chart_type + mapping     ->  builder produces option
        (b) option=...                    ->  passthrough (raw ECharts option)

    Annotations (hline, vline, band, arrow, point) are attached as markLine/
    markArea/markPoint on the primary series after the builder runs.

    When session_path is supplied, writes {session_path}/echarts/{name}.json
    and (if write_html) {session_path}/echarts/{name}.html.
    """
    if chart_type not in _BUILDER_DISPATCH and chart_type != "raw":
        raise ValueError(
            f"Unknown chart_type '{chart_type}'. "
            f"Available: {', '.join(sorted(list(_BUILDER_DISPATCH.keys()) + ['raw']))}"
        )

    ctx = _build_context(chart_type if chart_type != "raw" else "line",
                           theme, palette, dimensions, title, subtitle)

    if option is not None:
        opt = _coerce_option(option)
        opt = copy.deepcopy(opt)
        if title is not None:
            opt.setdefault("title", {})["text"] = title
        if subtitle is not None:
            opt.setdefault("title", {})["subtext"] = subtitle
        if ctx.palette_colors and ctx.palette_kind == "categorical" and "color" not in opt:
            opt["color"] = list(ctx.palette_colors)
    else:
        if mapping is None:
            raise ValueError("make_echart: either 'option' or 'mapping' must be given.")
        builder = _BUILDER_DISPATCH.get(chart_type)
        if builder is None:
            raise ValueError(f"No builder for chart_type '{chart_type}'.")
        opt = builder(df, dict(mapping), ctx)

    mapping_annotations = (mapping or {}).get("annotations") if mapping else None
    combined_annotations: List[Dict[str, Any]] = []
    if mapping_annotations:
        combined_annotations.extend(list(mapping_annotations))
    if annotations:
        combined_annotations.extend(list(annotations))
    if combined_annotations:
        _apply_annotations(opt, combined_annotations)

    ok, warnings = validate_option(opt)
    chart_id = _compute_chart_id(opt)

    knob_defs = knobs_for(chart_type) if chart_type in MARK_KNOB_MAP else []
    knob_names = [k["name"] for k in knob_defs]

    # Paths
    json_path: Optional[Path] = None
    html_path: Optional[Path] = None
    html: Optional[str] = None
    if save_as:
        p = Path(save_as)
        json_path = p.with_suffix(".json")
        html_path = p.with_suffix(".html") if write_html else None
    elif session_path:
        sp = Path(session_path)
        name = chart_name or f"chart_{chart_id}"
        out = sp / "echarts"
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / f"{_slug(name)}.json"
        html_path = (out / f"{_slug(name)}.html") if write_html else None

    if json_path and write_json:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(opt, indent=2, default=str), encoding="utf-8")

    if html_path and write_html:
        html = render_editor_html(
            option=opt,
            chart_id=chart_id,
            chart_type=chart_type,
            theme=theme,
            palette=ctx.palette_name,
            dimension_preset=dimensions,
            knob_defs=knob_defs,
            spec_sheets=spec_sheets or {},
            active_spec_sheet=active_spec_sheet,
            user_id=user_id,
            filename_base=_slug(chart_name or (title or "chart")),
        )
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    result = EChartResult(
        option=opt,
        chart_id=chart_id,
        chart_type=chart_type,
        theme=theme,
        palette=ctx.palette_name,
        dimension_preset=dimensions,
        width=ctx.width,
        height=ctx.height,
        json_path=str(json_path) if json_path else None,
        html_path=str(html_path) if html_path else None,
        html=html,
        success=ok,
        warnings=list(warnings),
        knob_names=knob_names,
    )

    if save_png:
        png_path: Optional[Path] = None
        if save_as:
            png_path = Path(save_as).with_suffix(".png")
        elif session_path:
            sp = Path(session_path)
            name = chart_name or f"chart_{chart_id}"
            png_path = sp / "echarts" / f"{_slug(name)}.png"
        if png_path is not None:
            try:
                result.save_png(png_path, scale=int(png_scale))
            except Exception as e:  # noqa: BLE001
                result.warnings.append(f"PNG export failed: {e}")
        else:
            result.warnings.append(
                "save_png=True but neither session_path nor save_as provided"
            )

    return result


def wrap_echart(
    option: Any,
    chart_type: Optional[str] = None,
    theme: str = "gs_clean",
    palette: Optional[str] = None,
    dimensions: str = "wide",
    title: Optional[str] = None,
    output_path: Optional[Union[str, Path]] = None,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
) -> EChartResult:
    """Wrap a pre-built ECharts option dict into the interactive editor HTML.

    Use this when the caller has already produced an option (e.g. from a
    pre-existing JSON asset or hand-rolled dict) and just wants the editor
    wrapper.
    """
    opt = _coerce_option(option)
    inferred = chart_type or _infer_chart_type(opt)
    ctx = _build_context(inferred if inferred in MARK_KNOB_MAP else "line",
                           theme, palette, dimensions, title, None)

    if title is not None:
        opt.setdefault("title", {})["text"] = title

    chart_id = _compute_chart_id(opt)
    knob_defs = knobs_for(inferred) if inferred in MARK_KNOB_MAP else []
    html = render_editor_html(
        option=opt, chart_id=chart_id, chart_type=inferred,
        theme=theme, palette=ctx.palette_name, dimension_preset=dimensions,
        knob_defs=knob_defs,
        spec_sheets=spec_sheets or {}, active_spec_sheet=active_spec_sheet,
        user_id=user_id, filename_base=_slug(title or "chart"),
    )
    html_path: Optional[Path] = None
    if output_path:
        html_path = Path(output_path)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    ok, warnings = validate_option(opt)
    return EChartResult(
        option=opt,
        chart_id=chart_id,
        chart_type=inferred,
        theme=theme,
        palette=ctx.palette_name,
        dimension_preset=dimensions,
        width=ctx.width,
        height=ctx.height,
        html=html,
        html_path=str(html_path) if html_path else None,
        success=ok,
        warnings=list(warnings),
        knob_names=[k["name"] for k in knob_defs],
    )


def _infer_chart_type(option: Dict[str, Any]) -> str:
    """Best-effort detect chart type from option.series[0].type."""
    series = option.get("series")
    if isinstance(series, dict):
        series = [series]
    if isinstance(series, list) and series:
        t = series[0].get("type", "line")
        if t == "pie":
            first = series[0]
            r = first.get("radius")
            if isinstance(r, (list, tuple)) and len(r) == 2 and str(r[0]).strip() != "0%":
                return "donut"
            return "pie"
        mapping = {
            "line": "line", "bar": "bar", "scatter": "scatter",
            "effectScatter": "scatter", "sankey": "sankey", "treemap": "treemap",
            "sunburst": "sunburst", "graph": "graph", "candlestick": "candlestick",
            "radar": "radar", "gauge": "gauge", "heatmap": "heatmap",
            "boxplot": "boxplot", "funnel": "funnel", "parallel": "parallel_coords",
            "tree": "tree",
        }
        return mapping.get(t, "line")
    return "line"


# =============================================================================
# MODULE-LEVEL LISTING HELPERS (for CLI)
# =============================================================================


def info_option(option: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize a raw option dict for the CLI 'info' command."""
    chart_type = _infer_chart_type(option)
    series = option.get("series")
    if isinstance(series, dict):
        series = [series]
    series_count = len(series) if isinstance(series, list) else 0
    has_x = "xAxis" in option
    has_y = "yAxis" in option
    has_grid = "grid" in option
    has_visual_map = "visualMap" in option
    return {
        "chart_type": chart_type,
        "series_count": series_count,
        "has_xAxis": has_x,
        "has_yAxis": has_y,
        "has_grid": has_grid,
        "has_visualMap": has_visual_map,
        "has_tooltip": "tooltip" in option,
        "has_legend": "legend" in option,
    }


# =============================================================================
# CLI ENTRY
# =============================================================================


# =============================================================================
# CLI (interactive + argparse)
# =============================================================================

import argparse
import time
import webbrowser

# ----- helpers -----

def _print_table(rows: List[Dict[str, Any]], columns: List[str]) -> None:
    if not rows:
        print("  (empty)")
        return
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    sep = "  ".join("-" * widths[c] for c in columns)
    print(header)
    print(sep)
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))


def _ask(prompt: str, default: Optional[str] = None) -> str:
    if default is not None:
        s = input(f"{prompt} [{default}]: ").strip()
        return s or default
    return input(f"{prompt}: ").strip()


def _choice(prompt: str, options: List[str], default: Optional[str] = None) -> str:
    print(prompt)
    for i, o in enumerate(options, 1):
        marker = "*" if o == default else " "
        print(f"  {marker} {i}. {o}")
    while True:
        raw = input(f"select [1-{len(options)}] or name: ").strip()
        if not raw:
            if default is not None:
                return default
            continue
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        if raw in options:
            return raw
        print(f"  invalid, try again.")


def _heartbeat(label: str, start: float, last: List[float]) -> None:
    now = time.time()
    if now - last[0] >= 5.0:
        print(f"  ... {label} ({int(now - start)}s)")
        last[0] = now


# ---------------------------------------------------------------------------
# STUDIO CLI
# ---------------------------------------------------------------------------

def _load_option(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_wrap(args: argparse.Namespace) -> int:
    option = _load_option(args.input)
    out = args.output or Path(args.input).with_suffix(".html").name
    r = wrap_echart(
        option=option, theme=args.theme, palette=args.palette,
        dimensions=args.dimensions, title=args.title,
        output_path=out,
    )
    print(f"wrote {r.html_path}")
    if args.open:
        webbrowser.open(f"file://{Path(r.html_path).resolve()}")
    return 0


def cmd_png(args: argparse.Namespace) -> int:
    from rendering import save_chart_png
    option = _load_option(args.input)
    out = args.output or str(Path(args.input).with_suffix(".png").name)
    path = save_chart_png(
        option, out,
        width=args.width, height=args.height,
        theme=args.theme, scale=args.scale,
        background=args.background,
        verbose=bool(getattr(args, "verbose", False)),
    )
    size_kb = Path(path).stat().st_size / 1024.0
    print(f"wrote {path}  ({size_kb:.1f} KB, "
          f"{args.width * args.scale}x{args.height * args.scale})")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from samples import SAMPLES, get_sample, list_samples
    out = Path(args.output_dir or "echarts_demo")
    out.mkdir(parents=True, exist_ok=True)
    start = time.time(); last = [start]
    if args.matrix:
        sample_names = list_samples()
        themes = sorted(THEMES.keys())
        total = len(sample_names) * len(themes)
        done = 0
        print(f"rendering {total} samples x themes ...")
        for name in sample_names:
            for th in themes:
                try:
                    opt = get_sample(name)
                    r = wrap_echart(
                        option=opt, theme=th,
                        output_path=str(out / f"{name}_{th}.html"),
                    )
                    done += 1
                    _heartbeat(f"{name} + {th} ({done}/{total})", start, last)
                except Exception as e:
                    print(f"  FAIL {name} x {th}: {e}")
        print(f"done. wrote {done} files to {out}")
        return 0
    else:
        names = [args.sample] if args.sample else list_samples()
        for name in names:
            try:
                opt = get_sample(name)
                r = wrap_echart(option=opt, theme=args.theme,
                                  output_path=str(out / f"{name}.html"))
                print(f"wrote {r.html_path}")
                _heartbeat(name, start, last)
            except Exception as e:
                print(f"  FAIL {name}: {e}")
        return 0


def cmd_list(args: argparse.Namespace) -> int:
    target = args.target
    if target == "types":
        rows = [{"type": t,
                  "knobs": sum(knob_count(t))}
                 for t in list_chart_types()]
        _print_table(rows, ["type", "knobs"])
    elif target == "themes":
        rows = list_themes()
        _print_table(rows, ["name", "label", "palette", "description"])
    elif target == "palettes":
        rows = list_palettes()
        _print_table(rows, ["name", "label", "kind", "n_colors"])
    elif target == "dimensions":
        rows = list_dimensions()
        _print_table(rows, ["name", "width", "height", "label"])
    elif target == "knobs":
        if not args.chart_type:
            print("error: --chart-type required for `list knobs`", file=sys.stderr)
            return 2
        rows = [
            {"name": k["name"], "label": k["label"], "type": k["type"],
              "group": k["group"],
              "default": "" if k.get("default") is None else str(k["default"])}
            for k in knobs_for(args.chart_type)
        ]
        _print_table(rows, ["name", "label", "type", "group", "default"])
    elif target == "samples":
        for n in list_samples():
            print(f"  {n}")
    else:
        print(f"unknown list target '{target}'", file=sys.stderr)
        return 2
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    opt = _load_option(args.input)
    info = info_option(opt)
    for k, v in info.items():
        print(f"  {k}: {v}")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    import unittest
    import importlib
    m = importlib.import_module("tests")
    suite = unittest.defaultTestLoader.loadTestsFromModule(m)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


# ---------------------------------------------------------------------------
# INTERACTIVE MENU (studio)
# ---------------------------------------------------------------------------

def _interactive_studio() -> int:
    while True:
        print("""
echart_studio -- main menu
  1. wrap a spec file
  2. render a spec file to PNG
  3. generate demos
  4. list themes / palettes / dimensions / types / knobs / samples
  5. info on a spec file
  6. run tests
  q. quit
""")
        choice = _ask("choice", default="q")
        if choice == "1":
            inp = _ask("input JSON path")
            out = _ask("output HTML path", default=Path(inp).with_suffix(".html").name)
            theme = _ask("theme", default="gs_clean")
            args = argparse.Namespace(
                input=inp, output=out, theme=theme,
                palette=None, dimensions="wide", title=None, open=False,
            )
            cmd_wrap(args)
        elif choice == "2":
            inp = _ask("input JSON path")
            out = _ask("output PNG path",
                         default=str(Path(inp).with_suffix(".png").name))
            width = int(_ask("width px", default="900") or "900")
            height = int(_ask("height px", default="520") or "520")
            scale = int(_ask("scale (1/2/3)", default="2") or "2")
            args = argparse.Namespace(
                input=inp, output=out, theme="gs_clean",
                width=width, height=height, scale=scale,
                background="#ffffff", verbose=False,
            )
            cmd_png(args)
        elif choice == "3":
            matrix = _ask("matrix? (y/n)", default="n").lower().startswith("y")
            sample = None
            if not matrix:
                options = ["(all)"] + list_samples()
                if len(options) > 1:
                    sel = _choice("sample", options, default="(all)")
                    sample = None if sel == "(all)" else sel
            out_dir = _ask("output dir", default="echarts_demo")
            theme = _ask("theme", default="gs_clean")
            args = argparse.Namespace(matrix=matrix, sample=sample,
                                        output_dir=out_dir, theme=theme)
            cmd_demo(args)
        elif choice == "4":
            target = _choice("target",
                               ["types", "themes", "palettes", "dimensions",
                                "knobs", "samples"], default="themes")
            chart_type = None
            if target == "knobs":
                chart_type = _choice("chart_type", list_chart_types(), default="line")
            args = argparse.Namespace(target=target, chart_type=chart_type)
            cmd_list(args)
        elif choice == "5":
            inp = _ask("input JSON path")
            args = argparse.Namespace(input=inp)
            cmd_info(args)
        elif choice == "6":
            args = argparse.Namespace()
            cmd_test(args)
        elif choice == "q":
            return 0


def run_studio_cli(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return _interactive_studio()
    p = argparse.ArgumentParser("echart_studio")
    sub = p.add_subparsers(dest="cmd")

    w = sub.add_parser("wrap", help="wrap an option JSON into HTML")
    w.add_argument("input")
    w.add_argument("-o", "--output")
    w.add_argument("--theme", default="gs_clean")
    w.add_argument("--palette")
    w.add_argument("--dimensions", default="wide")
    w.add_argument("--title")
    w.add_argument("--open", action="store_true")
    w.set_defaults(func=cmd_wrap)

    g = sub.add_parser("png", help="render an option JSON to a PNG")
    g.add_argument("input", help="path to ECharts option JSON")
    g.add_argument("-o", "--output",
                     help="output PNG path (default: input name + .png)")
    g.add_argument("--theme", default="gs_clean")
    g.add_argument("--width", type=int, default=900)
    g.add_argument("--height", type=int, default=520)
    g.add_argument("--scale", type=int, default=2,
                     help="device-pixel multiplier (1 | 2 | 3)")
    g.add_argument("--background", default="#ffffff")
    g.add_argument("--verbose", action="store_true")
    g.set_defaults(func=cmd_png)

    o = sub.add_parser("open", help="wrap + open in browser")
    o.add_argument("input"); o.add_argument("-o", "--output")
    o.add_argument("--theme", default="gs_clean"); o.add_argument("--palette")
    o.add_argument("--dimensions", default="wide"); o.add_argument("--title")
    o.set_defaults(func=lambda a: cmd_wrap(argparse.Namespace(**{**vars(a), "open": True})))

    d = sub.add_parser("demo", help="generate sample HTML")
    d.add_argument("--sample")
    d.add_argument("--output-dir", default="echarts_demo")
    d.add_argument("--theme", default="gs_clean")
    d.add_argument("--matrix", action="store_true")
    d.set_defaults(func=cmd_demo)

    l = sub.add_parser("list", help="list types|themes|palettes|dimensions|knobs|samples")
    l.add_argument("target")
    l.add_argument("--chart-type")
    l.set_defaults(func=cmd_list)

    i = sub.add_parser("info", help="summarize a spec file")
    i.add_argument("input")
    i.set_defaults(func=cmd_info)

    t = sub.add_parser("test", help="run built-in tests")
    t.set_defaults(func=cmd_test)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 2
    return args.func(args)

def main(argv: Optional[List[str]] = None) -> int:
    return run_studio_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
