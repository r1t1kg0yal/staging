"""
composites -- single-artifact multi-chart layouts (2pack / 3pack / 4pack / 6pack).

Parity with chart_functions.make_2pack_horizontal / _vertical / make_3pack_triangle
/ make_4pack_grid / make_6pack_grid. Each helper produces ONE EChartResult
whose `.option` is a multi-grid ECharts composite showing all sub-specs in a
single canvas. When rendered to PNG, the output is one image.

Design
------

Callers pass ChartSpec objects as positional args (matching the Altair
composite API), plus keyword metadata (title, subtitle, dimension_preset,
session_path, chart_name, save_as, theme, palette). Internally:

    1. Each ChartSpec is lowered into an ECharts option via the same
       _BUILDER_DISPATCH used by make_echart().
    2. Axes + series indices are remapped so each sub-option lives in its
       own grid.
    3. Grid rectangles are placed according to the layout topology.
    4. A single composite title/subtitle sits at the top.
    5. The result wraps like any other chart: editor HTML + JSON + PNG
       export via EChartResult.save_png().

No HTML is authored by callers. No layout CSS is manipulated. The composite
is literally one ECharts option with multiple grids.

Usage
-----

    from composites import ChartSpec, make_2pack_horizontal

    spec_a = ChartSpec(df=df_rates, chart_type="multi_line",
                        mapping={"x": "date", "y": ["us_2y", "us_10y"]},
                        title="UST yields")
    spec_b = ChartSpec(df=df_spread, chart_type="line",
                        mapping={"x": "date", "y": "spread_bps"},
                        title="2s10s spread")

    r = make_2pack_horizontal(spec_a, spec_b,
                                 title="US rates snapshot",
                                 subtitle="live",
                                 session_path=SP)
    # r.option, r.html_path, r.json_path
    r.save_png("snapshot.png", scale=2)
"""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from echart_studio import (
    _BUILDER_DISPATCH, _build_context, _apply_annotations,
    _compute_chart_id, _slug, EChartResult, validate_option,
)
from rendering import render_editor_html


# =============================================================================
# ChartSpec
# =============================================================================

@dataclass
class ChartSpec:
    """Per-panel specification for composite layouts.

    Positional arg for make_2pack_*, make_3pack_*, make_4pack_grid,
    make_6pack_grid. Captures enough state for the compiler to lower the
    spec to an ECharts option.
    """
    df: Any = None
    chart_type: str = "line"
    mapping: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None
    subtitle: Optional[str] = None
    annotations: Optional[List[Dict[str, Any]]] = None
    theme: Optional[str] = None
    palette: Optional[str] = None
    dimensions: Optional[str] = None
    option: Optional[Dict[str, Any]] = None  # raw passthrough

    def to_option(self, default_theme: str = "gs_clean",
                    default_palette: Optional[str] = None,
                    default_dimensions: str = "compact") -> Dict[str, Any]:
        """Lower this spec to a single-grid ECharts option dict."""
        if self.option is not None:
            return copy.deepcopy(self.option)
        chart_type = self.chart_type
        if chart_type not in _BUILDER_DISPATCH:
            raise ValueError(
                f"ChartSpec.chart_type '{chart_type}' not in builder dispatch; "
                f"available: {sorted(_BUILDER_DISPATCH.keys())}"
            )
        ctx = _build_context(
            chart_type=chart_type,
            theme=self.theme or default_theme,
            palette=self.palette or default_palette,
            dimensions=self.dimensions or default_dimensions,
            title=self.title,
            subtitle=self.subtitle,
        )
        builder = _BUILDER_DISPATCH[chart_type]
        opt = builder(self.df, dict(self.mapping or {}), ctx)
        mapping_ann = (self.mapping or {}).get("annotations")
        ann: List[Dict[str, Any]] = []
        if mapping_ann:
            ann.extend(list(mapping_ann))
        if self.annotations:
            ann.extend(list(self.annotations))
        if ann:
            _apply_annotations(opt, ann)
        return opt


# =============================================================================
# Multi-grid merging
# =============================================================================

def _wrap_axes_list(axes: Any) -> List[Dict[str, Any]]:
    if axes is None:
        return []
    if isinstance(axes, dict):
        return [axes]
    return list(axes)


def _wrap_series(series: Any) -> List[Dict[str, Any]]:
    if series is None:
        return []
    if isinstance(series, dict):
        return [series]
    return list(series)


def _remap_axis_index(s: Dict[str, Any],
                        axis_offset_x: int, axis_offset_y: int) -> None:
    """Remap xAxisIndex/yAxisIndex on a series entry for multi-grid merging.

    If the series has no explicit axis index, it gets offset + 0. If it has
    e.g. yAxisIndex=1 (dual-axis second axis), it becomes offset + 1.
    """
    cur_x = s.get("xAxisIndex", 0)
    cur_y = s.get("yAxisIndex", 0)
    if not isinstance(cur_x, int):
        cur_x = 0
    if not isinstance(cur_y, int):
        cur_y = 0
    s["xAxisIndex"] = axis_offset_x + cur_x
    s["yAxisIndex"] = axis_offset_y + cur_y


def _merge_multigrid(
    specs_and_options: Sequence[Tuple[ChartSpec, Dict[str, Any]]],
    grid_rects: Sequence[Dict[str, str]],
    composite_title: Optional[str],
    composite_subtitle: Optional[str],
    palette_colors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Merge N per-panel options into one multi-grid composite option.

    grid_rects[i] is a dict with ECharts grid keys (left/right/top/bottom).
    """
    if len(specs_and_options) != len(grid_rects):
        raise ValueError(
            f"_merge_multigrid: got {len(specs_and_options)} specs vs "
            f"{len(grid_rects)} grid rects"
        )

    merged: Dict[str, Any] = {
        "title": {
            "text": composite_title or "",
            "subtext": composite_subtitle or "",
            "left": "left",
            "top": 6,
        },
        "tooltip": {"show": True, "trigger": "axis",
                     "axisPointer": {"type": "cross"}},
        "legend": {"show": True, "top": 30, "right": 10,
                     "orient": "horizontal", "type": "scroll",
                     "data": []},
        "toolbox": {
            "show": True, "top": 8, "right": 10, "itemSize": 14,
            "feature": {
                "saveAsImage": {"show": True, "title": "Save"},
                "restore": {"show": True, "title": "Restore"},
            },
        },
        "animation": True,
        "animationDuration": 600,
        "grid": [],
        "xAxis": [],
        "yAxis": [],
        "series": [],
    }
    if palette_colors:
        merged["color"] = list(palette_colors)

    legend_names: List[str] = []
    legend_seen = set()

    for i, ((_spec, opt), rect) in enumerate(zip(specs_and_options, grid_rects)):
        opt = copy.deepcopy(opt)
        axis_x_offset = len(merged["xAxis"])
        axis_y_offset = len(merged["yAxis"])
        grid_idx = len(merged["grid"])

        # Grid: combine the per-spec rect with left/right/top/bottom strings
        per_grid = rect.copy()
        per_grid.setdefault("containLabel", True)
        merged["grid"].append(per_grid)

        # xAxes: tag each with gridIndex
        for ax in _wrap_axes_list(opt.get("xAxis")):
            ax = copy.deepcopy(ax)
            ax["gridIndex"] = grid_idx
            merged["xAxis"].append(ax)
        # yAxes
        for ax in _wrap_axes_list(opt.get("yAxis")):
            ax = copy.deepcopy(ax)
            ax["gridIndex"] = grid_idx
            merged["yAxis"].append(ax)

        # series: remap axis indices
        for s in _wrap_series(opt.get("series")):
            s = copy.deepcopy(s)
            s_type = s.get("type")
            # Position-anchored series (no xAxis/yAxis concept) use
            # center/left/top/bottom rather than axis indices.
            if s_type in ("pie", "sankey", "treemap", "sunburst", "graph",
                            "radar", "gauge", "funnel", "parallelSeries",
                            "tree", "parallel"):
                s.setdefault("left", per_grid.get("left", "0"))
                s.setdefault("right", per_grid.get("right", "0"))
                s.setdefault("top", per_grid.get("top", "0"))
                s.setdefault("bottom", per_grid.get("bottom", "0"))
                s.pop("xAxisIndex", None)
                s.pop("yAxisIndex", None)
            else:
                # XY + custom series are grid-anchored via axis indices.
                _remap_axis_index(s, axis_x_offset, axis_y_offset)
            name = s.get("name")
            if name and name not in legend_seen:
                legend_seen.add(name)
                legend_names.append(name)
            merged["series"].append(s)

        # Per-panel title: a small text graphic anchored to the grid's
        # top-left. Only rendered when the grid has a pixel-valued top.
        top_val = per_grid.get("top", "60px")
        if _spec.title and isinstance(top_val, str):
            if top_val.endswith("px"):
                try:
                    title_top = max(16, int(top_val[:-2]) - 18)
                except ValueError:
                    title_top = 40
            elif top_val.endswith("%"):
                # Approximate: title above grid at same percent minus 3%
                try:
                    pct = float(top_val[:-1])
                    title_top = f"{max(1.0, pct - 3.0):.2f}%"
                except ValueError:
                    title_top = top_val
            else:
                title_top = 40
            merged.setdefault("graphic", []).append({
                "type": "text",
                "left": per_grid.get("left", "0"),
                "top": title_top,
                "style": {
                    "text": _spec.title,
                    "fontSize": 12, "fontWeight": "bold",
                    "fill": "#2d3748",
                },
                "z": 100,
            })

    merged["legend"]["data"] = legend_names
    return merged


# =============================================================================
# Layout topologies
# =============================================================================

def _rects_horizontal(n: int, *, gap_pct: float = 4.0,
                        top_px: int = 60, bottom_px: int = 40) -> List[Dict[str, str]]:
    """N side-by-side panels spanning the full width."""
    frac = (100.0 - gap_pct * (n - 1)) / n
    rects = []
    for i in range(n):
        left = i * (frac + gap_pct)
        right = 100.0 - (left + frac)
        rects.append({
            "left": f"{left:.2f}%", "right": f"{right:.2f}%",
            "top": f"{top_px}px", "bottom": f"{bottom_px}px",
        })
    return rects


def _rects_vertical(n: int, *, gap_pct: float = 6.0,
                      top_pct: float = 12.0, bottom_pct: float = 6.0,
                      left_px: int = 60, right_px: int = 40) -> List[Dict[str, str]]:
    """N stacked panels spanning the full height (minus composite title)."""
    usable = 100.0 - top_pct - bottom_pct
    frac = (usable - gap_pct * (n - 1)) / n
    rects = []
    for i in range(n):
        top = top_pct + i * (frac + gap_pct)
        bottom = 100.0 - (top + frac)
        rects.append({
            "top": f"{top:.2f}%", "bottom": f"{bottom:.2f}%",
            "left": f"{left_px}px", "right": f"{right_px}px",
        })
    return rects


def _rects_triangle() -> List[Dict[str, str]]:
    """1 panel on top full-width, 2 panels side-by-side below."""
    top_frac = 44.0
    gap_pct = 4.0
    bottom_frac = 100.0 - top_frac - gap_pct - 8.0
    left_frac = (100.0 - gap_pct) / 2.0
    return [
        {"left": "4%", "right": "4%",
          "top": "14%", "bottom": f"{100.0 - (14.0 + top_frac):.2f}%"},
        {"left": "4%", "right": f"{100.0 - (4.0 + left_frac):.2f}%",
          "top": f"{14.0 + top_frac + gap_pct:.2f}%", "bottom": "6%"},
        {"left": f"{100.0 - (4.0 + left_frac):.2f}%", "right": "4%",
          "top": f"{14.0 + top_frac + gap_pct:.2f}%", "bottom": "6%"},
    ]


def _rects_grid(rows: int, cols: int, *,
                   gap_h_pct: float = 4.0, gap_v_pct: float = 6.0,
                   top_pct: float = 12.0, bottom_pct: float = 6.0,
                   left_pct: float = 4.0, right_pct: float = 4.0) -> List[Dict[str, str]]:
    """rows x cols grid of equal-size panels."""
    usable_h = 100.0 - top_pct - bottom_pct
    usable_w = 100.0 - left_pct - right_pct
    panel_h = (usable_h - gap_v_pct * (rows - 1)) / rows
    panel_w = (usable_w - gap_h_pct * (cols - 1)) / cols
    rects: List[Dict[str, str]] = []
    for r in range(rows):
        for c in range(cols):
            top = top_pct + r * (panel_h + gap_v_pct)
            left = left_pct + c * (panel_w + gap_h_pct)
            rects.append({
                "top": f"{top:.2f}%", "bottom": f"{100.0 - top - panel_h:.2f}%",
                "left": f"{left:.2f}%", "right": f"{100.0 - left - panel_w:.2f}%",
            })
    return rects


# =============================================================================
# Public composite functions
# =============================================================================

_COMPOSITE_DIMENSIONS = {
    "2pack_h":    (1200, 450),
    "2pack_v":    (700, 750),
    "3pack_tri":  (1100, 750),
    "4pack":      (1200, 800),
    "6pack":      (1400, 900),
}


def _compose(
    specs: Sequence[ChartSpec],
    rects: Sequence[Dict[str, str]],
    layout_key: str,
    title: Optional[str],
    subtitle: Optional[str],
    theme: str,
    palette: Optional[str],
    dimension_preset: Optional[str],
    session_path: Optional[Union[str, Path]],
    chart_name: Optional[str],
    save_as: Optional[str],
    write_html: bool,
    write_json: bool,
    user_id: Optional[str],
) -> EChartResult:
    # Palette: use the first spec's palette if unset, else gs_primary
    from config import (
        get_theme, get_palette, get_dimension_preset, get_typography_override,
    )
    theme_obj = get_theme(theme)
    palette_name = palette or theme_obj["palette"]
    palette_obj = get_palette(palette_name)

    default_dims = dimension_preset or "compact"
    specs_options: List[Tuple[ChartSpec, Dict[str, Any]]] = [
        (s, s.to_option(default_theme=theme, default_palette=palette_name,
                          default_dimensions=default_dims))
        for s in specs
    ]

    opt = _merge_multigrid(
        specs_options, rects,
        composite_title=title, composite_subtitle=subtitle,
        palette_colors=list(palette_obj["colors"]) if palette_obj["kind"] == "categorical" else None,
    )

    w, h = _COMPOSITE_DIMENSIONS.get(layout_key, (1200, 500))
    chart_id = _compute_chart_id(opt)

    ok, warnings = validate_option(opt)

    # Paths
    json_path: Optional[Path] = None
    html_path: Optional[Path] = None
    html_content: Optional[str] = None
    if save_as:
        p = Path(save_as)
        json_path = p.with_suffix(".json")
        html_path = p.with_suffix(".html") if write_html else None
    elif session_path:
        sp = Path(session_path)
        name = chart_name or f"composite_{chart_id}"
        out = sp / "echarts"
        out.mkdir(parents=True, exist_ok=True)
        json_path = out / f"{_slug(name)}.json"
        html_path = (out / f"{_slug(name)}.html") if write_html else None

    if json_path and write_json:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(opt, indent=2, default=str),
                              encoding="utf-8")

    if html_path and write_html:
        html_content = render_editor_html(
            option=opt,
            chart_id=chart_id,
            chart_type="composite",
            theme=theme,
            palette=palette_name,
            dimension_preset=default_dims,
            knob_defs=[],
            spec_sheets={},
            active_spec_sheet=None,
            user_id=user_id,
            filename_base=_slug(chart_name or (title or "composite")),
        )
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_content, encoding="utf-8")

    return EChartResult(
        option=opt,
        chart_id=chart_id,
        chart_type="composite",
        theme=theme,
        palette=palette_name,
        dimension_preset=default_dims,
        width=w, height=h,
        json_path=str(json_path) if json_path else None,
        html_path=str(html_path) if html_path else None,
        html=html_content,
        success=ok,
        warnings=list(warnings),
    )


def make_2pack_horizontal(
    spec_a: ChartSpec, spec_b: ChartSpec, *,
    title: Optional[str] = None, subtitle: Optional[str] = None,
    theme: str = "gs_clean", palette: Optional[str] = None,
    dimension_preset: Optional[str] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None, save_as: Optional[str] = None,
    write_html: bool = True, write_json: bool = True,
    user_id: Optional[str] = None,
) -> EChartResult:
    """Two charts side-by-side in a single 1200x450 canvas."""
    return _compose(
        [spec_a, spec_b], _rects_horizontal(2),
        "2pack_h", title, subtitle, theme, palette, dimension_preset,
        session_path, chart_name, save_as, write_html, write_json, user_id,
    )


def make_2pack_vertical(
    top: ChartSpec, bottom: ChartSpec, *,
    title: Optional[str] = None, subtitle: Optional[str] = None,
    theme: str = "gs_clean", palette: Optional[str] = None,
    dimension_preset: Optional[str] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None, save_as: Optional[str] = None,
    write_html: bool = True, write_json: bool = True,
    user_id: Optional[str] = None,
) -> EChartResult:
    """Two charts stacked vertically in a 700x750 canvas."""
    return _compose(
        [top, bottom], _rects_vertical(2),
        "2pack_v", title, subtitle, theme, palette, dimension_preset,
        session_path, chart_name, save_as, write_html, write_json, user_id,
    )


def make_3pack_triangle(
    top: ChartSpec, bottom_left: ChartSpec, bottom_right: ChartSpec, *,
    title: Optional[str] = None, subtitle: Optional[str] = None,
    theme: str = "gs_clean", palette: Optional[str] = None,
    dimension_preset: Optional[str] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None, save_as: Optional[str] = None,
    write_html: bool = True, write_json: bool = True,
    user_id: Optional[str] = None,
) -> EChartResult:
    """One chart on top spanning full width, two side-by-side below."""
    return _compose(
        [top, bottom_left, bottom_right], _rects_triangle(),
        "3pack_tri", title, subtitle, theme, palette, dimension_preset,
        session_path, chart_name, save_as, write_html, write_json, user_id,
    )


def make_4pack_grid(
    tl: ChartSpec, tr: ChartSpec, bl: ChartSpec, br: ChartSpec, *,
    title: Optional[str] = None, subtitle: Optional[str] = None,
    theme: str = "gs_clean", palette: Optional[str] = None,
    dimension_preset: Optional[str] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None, save_as: Optional[str] = None,
    write_html: bool = True, write_json: bool = True,
    user_id: Optional[str] = None,
) -> EChartResult:
    """2 x 2 grid of four charts in a 1200x800 canvas."""
    return _compose(
        [tl, tr, bl, br], _rects_grid(2, 2),
        "4pack", title, subtitle, theme, palette, dimension_preset,
        session_path, chart_name, save_as, write_html, write_json, user_id,
    )


def make_6pack_grid(
    r1l: ChartSpec, r1r: ChartSpec,
    r2l: ChartSpec, r2r: ChartSpec,
    r3l: ChartSpec, r3r: ChartSpec, *,
    title: Optional[str] = None, subtitle: Optional[str] = None,
    theme: str = "gs_clean", palette: Optional[str] = None,
    dimension_preset: Optional[str] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None, save_as: Optional[str] = None,
    write_html: bool = True, write_json: bool = True,
    user_id: Optional[str] = None,
) -> EChartResult:
    """3 x 2 grid of six charts in a 1400x900 canvas."""
    return _compose(
        [r1l, r1r, r2l, r2r, r3l, r3r], _rects_grid(3, 2),
        "6pack", title, subtitle, theme, palette, dimension_preset,
        session_path, chart_name, save_as, write_html, write_json, user_id,
    )


__all__ = [
    "ChartSpec",
    "make_2pack_horizontal", "make_2pack_vertical",
    "make_3pack_triangle", "make_4pack_grid", "make_6pack_grid",
]
