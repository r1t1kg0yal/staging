#!/usr/bin/env python3
"""
echart_dashboard -- manifest-first dashboard composer and compiler.

The manifest is the source of truth -- a recyclable, LLM-editable JSON asset
that fully describes a dashboard. Two entry points render a manifest to HTML:

    compile_dashboard(spec)     JSON-first. Accepts a dict, a path to a JSON
                                file, or a JSON string. Recommended for LLMs.

    Dashboard(...).build(...)   Python builder sugar. Useful when composing
                                from DataFrames in notebooks / scripts.

Both paths converge on the same compiler pipeline:

    manifest  ->  validator  ->  spec resolver  ->  HTML renderer
                                  (spec -> option)    (dashboard_html.py)

Example: JSON-first (PRISM's preferred shape)
---------------------------------------------

    from echart_dashboard import compile_dashboard

    manifest = {
      "schema_version": 1,
      "id": "rates_monitor",
      "title": "Rates monitor",
      "theme": "gs_clean",
      "datasets": {
        "rates": {"source": [
          ["date", "us_2y", "us_10y", "2s10s"],
          ["2026-04-22", 4.12, 4.48, 36.0],
          ...
        ]}
      },
      "filters": [
        {"id": "dt", "type": "dateRange", "default": "6M",
         "targets": ["*"], "field": "date"}
      ],
      "layout": {
        "kind": "tabs",
        "tabs": [{
          "id": "overview", "label": "Overview",
          "rows": [[{
            "widget": "chart", "id": "curve", "w": 12,
            "spec": {
              "chart_type": "multi_line",
              "dataset": "rates",
              "mapping": {"x": "date", "y": ["us_2y", "us_10y"]},
              "title": "UST curve"
            }
          }]]
        }]
      }
    }

    r = compile_dashboard(manifest, session_path="sessions/demo")
    # r.manifest_path -> sessions/demo/dashboards/rates_monitor.json
    # r.html_path     -> sessions/demo/dashboards/rates_monitor.html

Example: Python builder
-----------------------

    from echart_dashboard import (
        Dashboard, ChartRef, KPIRef, GlobalFilter, Link,
    )

    db = (Dashboard(id="rates_monitor", title="Rates monitor")
          .add_dataset("rates", rates_df)
          .add_filter(GlobalFilter(id="dt", type="dateRange",
                                    default="6M", targets=["*"]))
          .add_row([
              ChartRef(id="curve", w=12,
                        spec={"chart_type": "multi_line",
                              "dataset": "rates",
                              "mapping": {"x": "date",
                                          "y": ["us_2y", "us_10y"]}}),
          ]))
    r = db.build(session_path="sessions/demo")
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from rendering import render_dashboard_html

# =============================================================================
# MANIFEST SCHEMA + VALIDATOR
# =============================================================================

SCHEMA_VERSION = 1
VALID_WIDGETS = {"chart", "kpi", "table", "markdown", "divider",
                  "stat_grid", "image"}
VALID_FILTERS = {"dateRange", "select", "multiSelect", "numberRange",
                  "toggle", "slider", "radio", "text", "number"}
VALID_FILTER_OPS = {"==", "!=", ">", ">=", "<", "<=",
                     "contains", "startsWith", "endsWith"}
VALID_SYNC = {"axis", "tooltip", "legend", "dataZoom"}
VALID_BRUSH_TYPES = {"rect", "polygon", "lineX", "lineY"}
VALID_REFRESH_FREQUENCIES = {"hourly", "daily", "weekly", "manual"}

# Supported column format tokens for table widgets.
# Examples: "number:2" (2 decimals), "percent:1", "currency:2",
# "bps:0", "integer", "date", "datetime", "text", "link".
VALID_TABLE_FORMATS = {
    "text", "number", "integer", "percent", "currency", "bps",
    "date", "datetime", "link", "signed", "delta",
}

VALID_CHART_TYPES = {
    "line", "multi_line", "bar", "bar_horizontal", "scatter", "scatter_multi",
    "area", "heatmap", "pie", "donut", "boxplot", "histogram", "bullet",
    "sankey", "treemap", "sunburst", "graph", "candlestick", "radar",
    "gauge", "calendar_heatmap", "funnel", "parallel_coords", "tree",
}


def _err(path: str, msg: str) -> str:
    return f"{path}: {msg}"


def validate_manifest(manifest: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a manifest dict. Return (ok, error_list).

    If datasets contain raw DataFrames or list-shorthand, they are normalized
    in place before validation so callers can pass PRISM-style manifests
    directly. Missing required fields produce one error each; does not
    short-circuit on first error.
    """
    errs: List[str] = []
    if not isinstance(manifest, dict):
        return False, [_err("(root)", "manifest must be a dict")]
    # Normalize DataFrames / list-shorthand into canonical dataset form
    # so validate_manifest accepts the same shapes compile_dashboard does.
    try:
        _normalize_manifest_datasets(manifest)
        _augment_manifest(manifest)
    except Exception:  # noqa: BLE001
        pass  # let validation report the issue
    sv = manifest.get("schema_version")
    if sv != SCHEMA_VERSION:
        errs.append(_err("schema_version",
                          f"expected {SCHEMA_VERSION}, got {sv!r}"))

    for key in ("id", "title"):
        if not manifest.get(key):
            errs.append(_err(key, "required field missing or empty"))

    theme = manifest.get("theme", "gs_clean")
    palette = manifest.get("palette")
    if theme:
        from config import THEMES
        if theme not in THEMES:
            errs.append(_err("theme",
                              f"unknown theme '{theme}'; "
                              f"valid: {sorted(THEMES.keys())}"))
    if palette:
        from config import PALETTES
        if palette not in PALETTES:
            errs.append(_err("palette",
                              f"unknown palette '{palette}'; "
                              f"valid: {sorted(PALETTES.keys())}"))

    # metadata block (optional; all fields optional)
    metadata = manifest.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            errs.append(_err("metadata", "must be a dict"))
        else:
            for k in ("kerberos", "dashboard_id", "data_as_of",
                       "generated_at", "version", "api_url", "status_url"):
                v = metadata.get(k)
                if v is not None and not isinstance(v, str):
                    errs.append(_err(f"metadata.{k}",
                                       f"must be a string, got {type(v).__name__}"))
            for k in ("sources", "tags"):
                v = metadata.get(k)
                if v is not None and not isinstance(v, list):
                    errs.append(_err(f"metadata.{k}", "must be a list of strings"))
            re = metadata.get("refresh_enabled")
            if re is not None and not isinstance(re, bool):
                errs.append(_err("metadata.refresh_enabled", "must be a bool"))
            rf = metadata.get("refresh_frequency")
            if rf is not None and rf not in VALID_REFRESH_FREQUENCIES:
                errs.append(_err("metadata.refresh_frequency",
                                   f"'{rf}' not in "
                                   f"{sorted(VALID_REFRESH_FREQUENCIES)}"))

    # header_actions: optional custom buttons/links in the header
    header_actions = manifest.get("header_actions")
    if header_actions is not None:
        if not isinstance(header_actions, list):
            errs.append(_err("header_actions", "must be a list"))
        else:
            for i, a in enumerate(header_actions):
                base = f"header_actions[{i}]"
                if not isinstance(a, dict):
                    errs.append(_err(base, "must be a dict"))
                    continue
                if not a.get("label"):
                    errs.append(_err(f"{base}.label", "required"))
                if not (a.get("href") or a.get("onclick")):
                    errs.append(_err(
                        base,
                        "requires 'href' (URL) or 'onclick' (JS function name)",
                    ))

    # datasets
    datasets = manifest.get("datasets", {}) or {}
    if not isinstance(datasets, dict):
        errs.append(_err("datasets", "must be a dict of name -> dataset"))
        datasets = {}
    for name, ds in datasets.items():
        if not isinstance(ds, dict) or "source" not in ds:
            errs.append(_err(f"datasets.{name}", "must be a dict with 'source'"))
            continue
        if not isinstance(ds["source"], list):
            errs.append(_err(f"datasets.{name}.source", "must be a list"))

    dataset_names = set(datasets.keys())

    # filters
    filters = manifest.get("filters", []) or []
    if not isinstance(filters, list):
        errs.append(_err("filters", "must be a list"))
        filters = []
    filter_ids = set()
    for i, f in enumerate(filters):
        base = f"filters[{i}]"
        if not isinstance(f, dict):
            errs.append(_err(base, "must be a dict"))
            continue
        fid = f.get("id")
        if not fid:
            errs.append(_err(f"{base}.id", "required"))
        elif fid in filter_ids:
            errs.append(_err(f"{base}.id", f"duplicate id '{fid}'"))
        else:
            filter_ids.add(fid)
        ft = f.get("type")
        if ft not in VALID_FILTERS:
            errs.append(_err(f"{base}.type",
                              f"'{ft}' not in {sorted(VALID_FILTERS)}"))
        if "targets" in f and not isinstance(f["targets"], list):
            errs.append(_err(f"{base}.targets", "must be a list of chart ids or patterns"))
        if ft in ("select", "multiSelect", "radio") and "options" not in f:
            errs.append(_err(f"{base}.options",
                              f"required for type '{ft}'"))
        if ft == "slider":
            for k in ("min", "max"):
                if k not in f:
                    errs.append(_err(f"{base}.{k}",
                                       f"required for slider"))
        if ft in ("slider", "number", "text") and "field" not in f:
            errs.append(_err(f"{base}.field",
                              f"required for type '{ft}' "
                              "(column to filter against)"))
        if "op" in f and f["op"] not in VALID_FILTER_OPS:
            errs.append(_err(f"{base}.op",
                              f"'{f['op']}' not in {sorted(VALID_FILTER_OPS)}"))

    # layout
    layout = manifest.get("layout")
    if not isinstance(layout, dict):
        errs.append(_err("layout", "must be a dict"))
        layout = {}
    kind = layout.get("kind", "grid")
    if kind not in ("grid", "tabs"):
        errs.append(_err("layout.kind",
                          f"must be 'grid' or 'tabs', got '{kind}'"))
    cols = layout.get("cols", 12)
    if not isinstance(cols, int) or cols <= 0:
        errs.append(_err("layout.cols", f"must be a positive int, got {cols!r}"))
        cols = 12

    seen_ids: set = set()
    chart_ids: set = set()
    filter_target_ids: set = set()  # any widget that consumes dataset data
                                      # (charts + tables + kpis via dataset_ref)

    def _validate_rows(rows, path_prefix):
        if not isinstance(rows, list):
            errs.append(_err(path_prefix, "must be a list of rows"))
            return
        for ri, row in enumerate(rows):
            if not isinstance(row, list):
                errs.append(_err(f"{path_prefix}[{ri}]",
                                   "must be a list of widgets"))
                continue
            total_w = 0
            for wi, w in enumerate(row):
                wbase = f"{path_prefix}[{ri}][{wi}]"
                if not isinstance(w, dict):
                    errs.append(_err(wbase, "must be a dict"))
                    continue
                wt = w.get("widget")
                if wt not in VALID_WIDGETS:
                    errs.append(_err(f"{wbase}.widget",
                                       f"'{wt}' not in {sorted(VALID_WIDGETS)}"))
                wid = w.get("id")
                if wid:
                    if wid in seen_ids:
                        errs.append(_err(f"{wbase}.id",
                                           f"duplicate widget id '{wid}'"))
                    else:
                        seen_ids.add(wid)
                    if wt == "chart":
                        chart_ids.add(wid)
                    if wt in ("chart", "table", "kpi", "stat_grid"):
                        filter_target_ids.add(wid)
                width = w.get("w", cols)
                if not isinstance(width, int) or width <= 0 or width > cols:
                    errs.append(_err(f"{wbase}.w",
                                       f"width must be 1..{cols}, got {width!r}"))
                else:
                    total_w += width
                if wt == "chart":
                    has_ref = bool(w.get("ref"))
                    has_option = isinstance(w.get("option"), dict)
                    has_option_inline = isinstance(w.get("option_inline"), dict)
                    spec = w.get("spec")
                    has_spec = isinstance(spec, dict)
                    if not (has_ref or has_option or has_option_inline or has_spec):
                        errs.append(_err(
                            f"{wbase}",
                            "chart widget requires one of 'spec' (high-level), "
                            "'ref' (spec file path), or 'option' (inline ECharts dict)"
                        ))
                    if has_spec:
                        ct = spec.get("chart_type")
                        if not ct:
                            errs.append(_err(f"{wbase}.spec.chart_type",
                                               "required"))
                        elif ct not in VALID_CHART_TYPES:
                            errs.append(_err(
                                f"{wbase}.spec.chart_type",
                                f"'{ct}' not in {sorted(VALID_CHART_TYPES)}"
                            ))
                        ds = spec.get("dataset")
                        if not ds:
                            errs.append(_err(f"{wbase}.spec.dataset",
                                               "required"))
                        elif ds not in dataset_names:
                            errs.append(_err(
                                f"{wbase}.spec.dataset",
                                f"'{ds}' not declared in manifest.datasets "
                                f"(available: {sorted(dataset_names)})"
                            ))
                        if "mapping" not in spec:
                            errs.append(_err(f"{wbase}.spec.mapping",
                                               "required"))
                        elif not isinstance(spec["mapping"], dict):
                            errs.append(_err(f"{wbase}.spec.mapping",
                                               "must be a dict"))
                        palette = spec.get("palette")
                        if palette:
                            from config import PALETTES
                            if palette not in PALETTES:
                                errs.append(_err(
                                    f"{wbase}.spec.palette",
                                    f"unknown palette '{palette}'; "
                                    f"valid: {sorted(PALETTES.keys())}"
                                ))
                        theme_override = spec.get("theme")
                        if theme_override:
                            from config import THEMES
                            if theme_override not in THEMES:
                                errs.append(_err(
                                    f"{wbase}.spec.theme",
                                    f"unknown theme '{theme_override}'; "
                                    f"valid: {sorted(THEMES.keys())}"
                                ))
                    dsr = w.get("dataset_ref")
                    if dsr and dsr not in dataset_names:
                        errs.append(_err(f"{wbase}.dataset_ref",
                                           f"dataset '{dsr}' not declared in manifest.datasets"))
                elif wt == "kpi":
                    for req in ("label",):
                        if req not in w:
                            errs.append(_err(f"{wbase}.{req}",
                                               f"required for kpi"))
                elif wt == "table":
                    if not w.get("ref") and not w.get("dataset_ref"):
                        errs.append(_err(f"{wbase}.ref|dataset_ref",
                                           "table widget requires 'ref' or 'dataset_ref'"))
                    cols_def = w.get("columns")
                    if cols_def is not None:
                        if not isinstance(cols_def, list):
                            errs.append(_err(f"{wbase}.columns",
                                               "must be a list of column dicts"))
                        else:
                            for ci, col in enumerate(cols_def):
                                cbase = f"{wbase}.columns[{ci}]"
                                if not isinstance(col, dict):
                                    errs.append(_err(cbase, "must be a dict"))
                                    continue
                                if "field" not in col:
                                    errs.append(_err(f"{cbase}.field",
                                                       "required"))
                                align = col.get("align")
                                if align and align not in ("left", "center", "right"):
                                    errs.append(_err(
                                        f"{cbase}.align",
                                        f"must be left|center|right, got {align!r}"
                                    ))
                                fmt = col.get("format")
                                if isinstance(fmt, str):
                                    token = fmt.split(":")[0]
                                    if token not in VALID_TABLE_FORMATS:
                                        errs.append(_err(
                                            f"{cbase}.format",
                                            f"unknown format '{fmt}'; token "
                                            f"must be in {sorted(VALID_TABLE_FORMATS)}"
                                        ))
                                conditional = col.get("conditional")
                                if conditional is not None:
                                    if not isinstance(conditional, list):
                                        errs.append(_err(
                                            f"{cbase}.conditional",
                                            "must be a list of rule dicts"
                                        ))
                                    else:
                                        for ri, rule in enumerate(conditional):
                                            rbase = f"{cbase}.conditional[{ri}]"
                                            if not isinstance(rule, dict):
                                                errs.append(_err(rbase, "must be a dict"))
                                                continue
                                            op = rule.get("op")
                                            if op and op not in VALID_FILTER_OPS:
                                                errs.append(_err(
                                                    f"{rbase}.op",
                                                    f"'{op}' not in {sorted(VALID_FILTER_OPS)}"
                                                ))
                                color_scale = col.get("color_scale")
                                if color_scale is not None:
                                    if not isinstance(color_scale, dict):
                                        errs.append(_err(
                                            f"{cbase}.color_scale",
                                            "must be a dict with min/max/palette"
                                        ))
                                    else:
                                        p = color_scale.get("palette")
                                        if p:
                                            from config import PALETTES
                                            if p not in PALETTES:
                                                errs.append(_err(
                                                    f"{cbase}.color_scale.palette",
                                                    f"unknown palette '{p}'"
                                                ))
                    row_click = w.get("row_click")
                    if row_click is not None and not isinstance(row_click, dict):
                        errs.append(_err(f"{wbase}.row_click",
                                           "must be a dict when present"))
                elif wt == "stat_grid":
                    stats = w.get("stats")
                    if not isinstance(stats, list) or not stats:
                        errs.append(_err(f"{wbase}.stats",
                                           "required non-empty list of stat dicts"))
                    else:
                        for si, st in enumerate(stats):
                            if not isinstance(st, dict):
                                errs.append(_err(
                                    f"{wbase}.stats[{si}]", "must be a dict"
                                ))
                                continue
                            if "label" not in st:
                                errs.append(_err(
                                    f"{wbase}.stats[{si}].label", "required"
                                ))
                            if "value" not in st and "source" not in st:
                                errs.append(_err(
                                    f"{wbase}.stats[{si}]",
                                    "requires 'value' or 'source'"
                                ))
                elif wt == "image":
                    if not (w.get("src") or w.get("url")):
                        errs.append(_err(f"{wbase}.src",
                                           "image widget requires 'src' or 'url'"))
                elif wt == "markdown":
                    if "content" not in w:
                        errs.append(_err(f"{wbase}.content",
                                           "required for markdown"))
            if total_w > cols:
                errs.append(_err(f"{path_prefix}[{ri}]",
                                   f"widget widths sum to {total_w} > cols={cols}"))

    if kind == "tabs":
        tabs = layout.get("tabs", [])
        if not isinstance(tabs, list) or not tabs:
            errs.append(_err("layout.tabs",
                              "required non-empty list when kind='tabs'"))
            tabs = []
        tab_ids = set()
        for ti, tab in enumerate(tabs):
            base = f"layout.tabs[{ti}]"
            if not isinstance(tab, dict):
                errs.append(_err(base, "must be a dict"))
                continue
            tid = tab.get("id")
            if not tid:
                errs.append(_err(f"{base}.id", "required"))
            elif tid in tab_ids:
                errs.append(_err(f"{base}.id", f"duplicate tab id '{tid}'"))
            else:
                tab_ids.add(tid)
            if not tab.get("label"):
                errs.append(_err(f"{base}.label", "required"))
            _validate_rows(tab.get("rows", []), f"{base}.rows")
    else:
        rows = layout.get("rows", [])
        _validate_rows(rows, "layout.rows")

    # validate filter targets reference a real data-bound widget id
    # (chart | table | kpi | stat_grid) or a wildcard pattern
    for i, f in enumerate(filters):
        if not isinstance(f, dict):
            continue
        for tpat in f.get("targets", []) or []:
            if tpat == "*" or "*" in tpat:
                continue
            if tpat not in filter_target_ids:
                errs.append(_err(
                    f"filters[{i}].targets",
                    f"target '{tpat}' is not a data-bound widget id; "
                    f"available: {sorted(filter_target_ids)}"))

    # links
    links = manifest.get("links", []) or []
    if not isinstance(links, list):
        errs.append(_err("links", "must be a list"))
        links = []
    link_groups = set()
    for i, lk in enumerate(links):
        base = f"links[{i}]"
        if not isinstance(lk, dict):
            errs.append(_err(base, "must be a dict"))
            continue
        group = lk.get("group")
        if not group:
            errs.append(_err(f"{base}.group", "required"))
        elif group in link_groups:
            errs.append(_err(f"{base}.group", f"duplicate group '{group}'"))
        else:
            link_groups.add(group)
        members = lk.get("members", [])
        if not isinstance(members, list):
            errs.append(_err(f"{base}.members", "must be a list"))
            members = []
        for m in members:
            if m == "*" or (isinstance(m, str) and "*" in m):
                continue
            if m not in chart_ids:
                errs.append(_err(
                    f"{base}.members",
                    f"'{m}' is not a chart widget id; "
                    f"available: {sorted(chart_ids)}"))
        sync = lk.get("sync", [])
        if sync:
            if not isinstance(sync, list):
                errs.append(_err(f"{base}.sync", "must be a list"))
            else:
                for s in sync:
                    if s not in VALID_SYNC:
                        errs.append(_err(f"{base}.sync",
                                           f"'{s}' not in {sorted(VALID_SYNC)}"))
        brush = lk.get("brush")
        if brush:
            if not isinstance(brush, dict):
                errs.append(_err(f"{base}.brush", "must be a dict"))
            else:
                bt = brush.get("type", "rect")
                if bt not in VALID_BRUSH_TYPES:
                    errs.append(_err(f"{base}.brush.type",
                                       f"'{bt}' not in {sorted(VALID_BRUSH_TYPES)}"))

    return (not errs), errs


def load_manifest(path: Union[str, Path]) -> Dict[str, Any]:
    """Load a manifest JSON file and return the dict. No validation."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"manifest not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_manifest(manifest: Dict[str, Any], path: Union[str, Path]) -> Path:
    """Write a manifest dict to JSON. Returns Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return p


def match_targets(targets: List[str], chart_ids: List[str]) -> List[str]:
    """Resolve a list of target patterns against actual chart ids.

    Supports '*' (match all) and simple 'prefix_*' / '*_suffix' patterns.
    """
    if not targets:
        return []
    out: List[str] = []
    for pat in targets:
        if pat == "*":
            out.extend(chart_ids)
        elif "*" in pat:
            rx = re.compile("^" + re.escape(pat).replace(r"\*", ".*") + "$")
            out.extend([c for c in chart_ids if rx.match(c)])
        else:
            if pat in chart_ids:
                out.append(pat)
    # dedupe preserving order
    seen = set(); uniq = []
    for c in out:
        if c in seen:
            continue
        seen.add(c); uniq.append(c)
    return uniq



# =============================================================================
# WIDGET BUILDERS
# =============================================================================


@dataclass
class ChartRef:
    """Reference to a chart inside a dashboard manifest.

    Three mutually-compatible shapes (prefer in listed order):

        spec={"chart_type": ..., "dataset": ..., "mapping": {...}, ...}
            High-level spec lowered at compile time. Preferred for LLMs.
        ref="echarts/chart.json"
            Path (relative to session or manifest dir) to a pre-built
            ECharts option JSON.
        option={...raw ECharts option dict...}
            Inline raw option. Useful for passthrough and tests.
    """
    id: str
    ref: Optional[str] = None                 # relative path to spec JSON
    option: Optional[Dict[str, Any]] = None    # inline raw ECharts option
    spec: Optional[Dict[str, Any]] = None      # high-level spec (compiled)
    dataset_ref: Optional[str] = None
    w: int = 12
    h_px: int = 320
    title: str = ""
    theme: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"widget": "chart", "id": self.id,
                               "w": self.w, "h_px": self.h_px,
                               "title": self.title}
        if self.ref: d["ref"] = self.ref
        if self.option is not None: d["option"] = self.option
        if self.spec is not None: d["spec"] = dict(self.spec)
        if self.dataset_ref: d["dataset_ref"] = self.dataset_ref
        if self.theme: d["theme"] = self.theme
        return d


@dataclass
class KPIRef:
    """A big-number tile.

    value OR source drives the displayed figure. delta + delta_source + prefix
    + suffix + decimals drive formatting. sparkline_source=<ds>.<col> adds a
    tiny inline chart.
    """
    id: str
    label: str
    value: Any = None
    source: Optional[str] = None
    sub: Optional[str] = None
    delta: Optional[float] = None
    delta_source: Optional[str] = None
    delta_label: Optional[str] = None
    delta_decimals: Optional[int] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    decimals: Optional[int] = None
    sparkline_source: Optional[str] = None
    w: int = 4

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"widget": "kpi", "id": self.id,
                               "label": self.label, "w": self.w}
        if self.value is not None: d["value"] = self.value
        if self.source: d["source"] = self.source
        if self.sub: d["sub"] = self.sub
        if self.delta is not None: d["delta"] = self.delta
        if self.delta_source: d["delta_source"] = self.delta_source
        if self.delta_label: d["delta_label"] = self.delta_label
        if self.delta_decimals is not None: d["delta_decimals"] = self.delta_decimals
        if self.prefix is not None: d["prefix"] = self.prefix
        if self.suffix is not None: d["suffix"] = self.suffix
        if self.decimals is not None: d["decimals"] = self.decimals
        if self.sparkline_source: d["sparkline_source"] = self.sparkline_source
        return d


@dataclass
class TableRef:
    id: str
    dataset_ref: Optional[str] = None
    ref: Optional[str] = None
    title: str = ""
    w: int = 12
    max_rows: int = 50

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"widget": "table", "id": self.id, "w": self.w,
                               "title": self.title, "max_rows": self.max_rows}
        if self.dataset_ref: d["dataset_ref"] = self.dataset_ref
        if self.ref: d["ref"] = self.ref
        return d


@dataclass
class MarkdownRef:
    id: str
    content: str
    w: int = 12

    def to_dict(self) -> Dict[str, Any]:
        return {"widget": "markdown", "id": self.id, "content": self.content, "w": self.w}


@dataclass
class DividerRef:
    id: str = "divider"

    def to_dict(self) -> Dict[str, Any]:
        return {"widget": "divider", "id": self.id, "w": 12}


@dataclass
class GlobalFilter:
    id: str
    type: str
    label: Optional[str] = None
    default: Any = None
    options: Optional[List[Any]] = None
    targets: List[str] = field(default_factory=lambda: ["*"])
    field: Optional[str] = None  # dataset column name filtered

    def to_dict(self) -> Dict[str, Any]:
        if self.type not in VALID_FILTERS:
            raise ValueError(
                f"GlobalFilter.type '{self.type}' not in {sorted(VALID_FILTERS)}"
            )
        d: Dict[str, Any] = {"id": self.id, "type": self.type,
                               "targets": list(self.targets)}
        if self.label is not None: d["label"] = self.label
        if self.default is not None: d["default"] = self.default
        if self.options is not None: d["options"] = list(self.options)
        if self.field: d["field"] = self.field
        return d


@dataclass
class Link:
    group: str
    members: List[str] = field(default_factory=list)
    sync: List[str] = field(default_factory=list)
    brush: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        bad = [s for s in self.sync if s not in VALID_SYNC]
        if bad:
            raise ValueError(
                f"Link.sync contains invalid entries {bad}; valid: {sorted(VALID_SYNC)}"
            )
        if self.brush:
            bt = self.brush.get("type", "rect")
            if bt not in VALID_BRUSH_TYPES:
                raise ValueError(
                    f"Link.brush.type '{bt}' not in {sorted(VALID_BRUSH_TYPES)}"
                )
        d: Dict[str, Any] = {"group": self.group, "members": list(self.members)}
        if self.sync: d["sync"] = list(self.sync)
        if self.brush: d["brush"] = dict(self.brush)
        return d


# =============================================================================
# RESULT
# =============================================================================


@dataclass
class DashboardResult:
    manifest: Dict[str, Any]
    manifest_path: Optional[str]
    html_path: Optional[str]
    html: Optional[str]
    success: bool
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    download_url: Optional[str] = None


# =============================================================================
# DASHBOARD BUILDER
# =============================================================================


@dataclass
class Tab:
    """A tab in a tabs-layout dashboard. Built up via Dashboard.add_tab(id, label).

    Mutators return self so they can be chained. Rows live per-tab.
    """
    id: str
    label: str
    description: str = ""
    rows: List[List[Any]] = field(default_factory=list)

    def add_row(self, widgets: Sequence[Any]) -> "Tab":
        self.rows.append(list(widgets))
        return self


class Dashboard:
    """Builder for a manifest. `build(session_path)` produces manifest + HTML.

    Two layout modes:

        grid  (default)   .add_row([...])       rows become a single grid
        tabs              .add_tab(id, label)   each tab has its own .rows

    Calling add_tab() flips the dashboard into tabs mode; any previously added
    grid rows are migrated into a 'main' tab so nothing is lost.
    """

    def __init__(self, id: str, title: str, description: str = "",
                 theme: str = "gs_clean", palette: Optional[str] = None):
        from config import THEMES, PALETTES
        if theme not in THEMES:
            raise ValueError(
                f"Unknown theme '{theme}'. "
                f"Valid: {sorted(THEMES.keys())}"
            )
        if palette is not None and palette not in PALETTES:
            raise ValueError(
                f"Unknown palette '{palette}'. "
                f"Valid: {sorted(PALETTES.keys())}"
            )
        self.id = id
        self.title = title
        self.description = description
        self.theme = theme
        self.palette = palette
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.filters: List[GlobalFilter] = []
        self.rows: List[List[Any]] = []
        self.tabs: List[Tab] = []
        self.links: List[Link] = []
        self.cols: int = 12

    # ----- datasets -----

    def add_dataset(self, name: str, df_or_source: Any, *,
                     field_types: Optional[Dict[str, str]] = None) -> "Dashboard":
        """Add a shared dataset to the manifest. Accepts either a pandas
        DataFrame (converted to a [header, ...rows] array) or a raw list."""
        source = _dataset_source(df_or_source)
        self.datasets[name] = {"source": source}
        if field_types:
            self.datasets[name]["field_types"] = dict(field_types)
        return self

    def add_dataset_inline(self, name: str, rows: List[List[Any]]) -> "Dashboard":
        """Add a dataset from a pre-built [header, ...rows] list."""
        if not isinstance(rows, list) or not rows:
            raise ValueError("add_dataset_inline: rows must be a non-empty list")
        self.datasets[name] = {"source": list(rows)}
        return self

    # ----- filters -----

    def add_filter(self, f: GlobalFilter) -> "Dashboard":
        self.filters.append(f)
        return self

    # ----- layout -----

    def set_cols(self, cols: int) -> "Dashboard":
        self.cols = int(cols)
        return self

    def add_row(self, widgets: Sequence[Any]) -> "Dashboard":
        if self.tabs:
            # already in tabs mode -> route to the active (last) tab
            self.tabs[-1].rows.append(list(widgets))
        else:
            self.rows.append(list(widgets))
        return self

    def add_tab(self, id: str, label: str,
                 description: str = "") -> Tab:
        """Create and append a new tab, switching the dashboard into tabs mode.

        Returns the Tab so the caller can chain `.add_row([...])` on it.
        Any previously-added grid rows migrate into an auto-generated
        'overview' tab.
        """
        if not self.tabs and self.rows:
            migrated = Tab(id="overview", label="Overview",
                            rows=list(self.rows))
            self.tabs.append(migrated)
            self.rows = []
        tab = Tab(id=id, label=label, description=description)
        self.tabs.append(tab)
        return tab

    # ----- links -----

    def add_link(self, link: Link) -> "Dashboard":
        self.links.append(link)
        return self

    # ----- manifest assembly -----

    def _rows_to_dict(self, rows: List[List[Any]]) -> List[List[Dict[str, Any]]]:
        rows_out: List[List[Dict[str, Any]]] = []
        for row in rows:
            row_out = []
            for w in row:
                if hasattr(w, "to_dict"):
                    row_out.append(w.to_dict())
                elif isinstance(w, dict):
                    row_out.append(dict(w))
                else:
                    raise TypeError(
                        f"widget must have to_dict() or be dict, got {type(w)}"
                    )
            rows_out.append(row_out)
        return rows_out

    def to_manifest(self) -> Dict[str, Any]:
        manifest: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "theme": self.theme,
            "datasets": dict(self.datasets),
            "filters": [f.to_dict() for f in self.filters],
            "links": [lk.to_dict() for lk in self.links],
        }
        if self.tabs:
            manifest["layout"] = {
                "kind": "tabs",
                "cols": self.cols,
                "tabs": [
                    {"id": t.id, "label": t.label,
                      "description": t.description,
                      "rows": self._rows_to_dict(t.rows)}
                    for t in self.tabs
                ],
            }
        else:
            manifest["layout"] = {
                "kind": "grid",
                "cols": self.cols,
                "rows": self._rows_to_dict(self.rows),
            }
        if self.palette:
            manifest["palette"] = self.palette
        return manifest

    # ----- build -----

    def build(self, session_path: Optional[Union[str, Path]] = None,
              output_path: Optional[Union[str, Path]] = None,
              write_html: bool = True, write_json: bool = True) -> DashboardResult:
        manifest = self.to_manifest()
        ok, errs = validate_manifest(manifest)
        if not ok:
            return DashboardResult(
                manifest=manifest, manifest_path=None,
                html_path=None, html=None, success=False,
                error_message="manifest validation failed",
                warnings=list(errs),
            )
        manifest_path: Optional[Path] = None
        html_path: Optional[Path] = None
        if output_path:
            html_path = Path(output_path)
            manifest_path = html_path.with_suffix(".json")
        elif session_path:
            sp = Path(session_path) / "dashboards"
            sp.mkdir(parents=True, exist_ok=True)
            manifest_path = sp / f"{self.id}.json"
            html_path = sp / f"{self.id}.html"

        if manifest_path and write_json:
            save_manifest(manifest, manifest_path)

        try:
            chart_specs = _resolve_chart_specs(manifest, base_dir=(
                manifest_path.parent.parent if manifest_path else None
            ))
        except (ValueError, TypeError) as e:
            return DashboardResult(
                manifest=manifest,
                manifest_path=str(manifest_path) if manifest_path else None,
                html_path=None, html=None, success=False,
                error_message=f"spec resolution failed: {e}",
                warnings=[str(e)],
            )
        html = render_dashboard_html(manifest, chart_specs, filename_base=self.id)

        if html_path and write_html:
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html, encoding="utf-8")

        return DashboardResult(
            manifest=manifest,
            manifest_path=str(manifest_path) if manifest_path else None,
            html_path=str(html_path) if html_path else None,
            html=html,
            success=True,
            warnings=[],
        )


# =============================================================================
# HELPERS
# =============================================================================


def df_to_source(df_or_source: Any) -> List[List[Any]]:
    """Convert a pandas DataFrame (or a list-shaped source) to the manifest
    dataset 'source' shape: [[header...], [row...], ...].

    Accepts:
        * pandas DataFrame  -- converted; datetime columns emit as ISO-8601
          strings; NaN becomes None.
        * list              -- returned as-is (assumed already in source shape).

    Raises TypeError on anything else. This is the canonical bridge between
    PRISM-side DataFrames and the manifest dataset contract; PRISM should
    use this (or pass a DataFrame directly and let compile_dashboard convert
    it) instead of hand-writing data rows into the JSON.
    """
    try:
        import pandas as pd
        if isinstance(df_or_source, pd.DataFrame):
            df = df_or_source.copy()
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df[c] = df[c].dt.strftime("%Y-%m-%d")
            source: List[List[Any]] = [list(df.columns)]
            for _, row in df.iterrows():
                source.append([_scalarize(v) for v in row])
            return source
    except Exception:
        pass
    if isinstance(df_or_source, list):
        return list(df_or_source)
    raise TypeError(
        f"df_to_source: expected DataFrame or list, got {type(df_or_source).__name__}"
    )


# Internal alias kept for older internal callers (Dashboard.add_dataset).
_dataset_source = df_to_source


def _scalarize(v: Any) -> Any:
    try:
        import math
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def _is_dataframe(obj: Any) -> bool:
    try:
        import pandas as pd
        return isinstance(obj, pd.DataFrame)
    except Exception:
        return False


def _normalize_manifest_datasets(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DataFrames in manifest.datasets.{name} / .source to source
    arrays IN PLACE and return the manifest.

    Accepted shapes per dataset entry:
        {"source": DataFrame}           -> converted to list-of-lists
        {"source": list_of_lists}       -> left alone
        DataFrame                       -> wrapped as {"source": [[...], ...]}
        list_of_lists                   -> wrapped as {"source": [...]}

    This runs BEFORE validate_manifest so that validation sees the canonical
    list-of-lists source shape in every case. PRISM code that builds a
    manifest in execute_analysis_script can simply pass DataFrames through
    with zero conversion boilerplate.
    """
    ds = manifest.get("datasets")
    if not isinstance(ds, dict):
        return manifest
    for name, entry in list(ds.items()):
        if _is_dataframe(entry):
            ds[name] = {"source": df_to_source(entry)}
            continue
        if isinstance(entry, list):
            ds[name] = {"source": df_to_source(entry)}
            continue
        if isinstance(entry, dict):
            src = entry.get("source")
            if _is_dataframe(src):
                entry["source"] = df_to_source(src)
    return manifest


def _augment_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Post-normalization, pre-validation enrichment that wires implicit
    contracts so PRISM-written manifests behave the way they look:

      1. chart widgets get ``dataset_ref`` auto-populated from
         ``spec.dataset`` when missing, so the runtime filter-application
         path (which keys off ``widget.dataset_ref``) reaches the chart.

      2. filters get a ``scope`` field inferred from their targets.
         If every resolved target lives in a single tab, ``scope`` is set
         to ``"tab:<id>"`` so the filter can render inside that tab
         (instead of squatting globally). If targets span tabs or include
         the wildcard ``"*"``, ``scope`` defaults to ``"global"``.

    Mutates the manifest in place and returns it.
    """
    layout = manifest.get("layout") or {}
    kind = layout.get("kind", "grid")

    widget_to_tab: Dict[str, Optional[str]] = {}
    tab_widget_ids: Dict[str, List[str]] = {}
    all_widgets: List[Dict[str, Any]] = []

    def _visit_rows(rows, tab_id: Optional[str]):
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                all_widgets.append(w)
                wid = w.get("id")
                if wid:
                    widget_to_tab[wid] = tab_id
                    if tab_id is not None:
                        tab_widget_ids.setdefault(tab_id, []).append(wid)

    if kind == "tabs":
        for t in layout.get("tabs", []) or []:
            if not isinstance(t, dict):
                continue
            _visit_rows(t.get("rows", []) or [], t.get("id"))
    else:
        _visit_rows(layout.get("rows", []) or [], None)

    filters = manifest.get("filters") or []

    # Set of widget ids that ANY filter targets. We only auto-populate
    # dataset_ref on widgets actually in the filter path so that charts
    # with pre-baked computed data (histograms, trendlines, bullets,
    # candlesticks, heatmaps, radar, gauge, sankey, treemap, funnel,
    # etc.) are not silently rewired and broken.
    targeted_ids: set = set()
    wildcard = False
    for f in filters:
        if not isinstance(f, dict):
            continue
        for t in f.get("targets") or []:
            if isinstance(t, str) and "*" in t:
                wildcard = True
            else:
                targeted_ids.add(t)

    # Chart types where the runtime rewire-on-filter path (dataset swap
    # + series encode substitution) can safely produce the right series
    # shape *without* access to the original builder. We only auto-wire
    # dataset_ref for widgets whose (chart_type, mapping) shape is in
    # this set. Anything else (computed series data, long-form with
    # color grouping, stacked bars, scatter with size/trendline, etc.)
    # keeps its pre-baked series.data and will not visually reshape on
    # filter change -- filter state still tracks and affects tables /
    # KPIs referencing the same dataset_ref.
    def _is_safe_for_rewire(chart_type: Optional[str],
                              mapping: Dict[str, Any]) -> bool:
        if chart_type not in {"line", "bar", "area", "multi_line"}:
            return False
        if mapping.get("color") or mapping.get("colour"):
            return False
        if mapping.get("trendline") or mapping.get("trendlines"):
            return False
        if mapping.get("stack") is True:
            return False
        if mapping.get("dual_axis_series"):
            # Dual-axis multi_line keeps wide-form compatibility; allow.
            return chart_type == "multi_line"
        return True

    for w in all_widgets:
        if w.get("widget") != "chart":
            continue
        if w.get("dataset_ref"):
            continue
        wid = w.get("id")
        spec = w.get("spec")
        if not isinstance(spec, dict):
            continue
        ds_name = spec.get("dataset")
        if not ds_name:
            continue
        is_targeted = wildcard or (wid in targeted_ids)
        if not is_targeted:
            continue
        if not _is_safe_for_rewire(spec.get("chart_type"),
                                       spec.get("mapping") or {}):
            continue
        w["dataset_ref"] = ds_name

    for f in filters:
        if not isinstance(f, dict):
            continue
        if f.get("scope"):
            continue
        targets = f.get("targets") or []
        if not targets:
            f["scope"] = "global"
            continue
        has_wildcard = any(
            isinstance(t, str) and ("*" in t) for t in targets
        )
        if has_wildcard:
            f["scope"] = "global"
            continue
        resolved_tabs: set = set()
        for t in targets:
            tab = widget_to_tab.get(t)
            if tab is None:
                resolved_tabs.add("__none__")
                break
            resolved_tabs.add(tab)
        if len(resolved_tabs) == 1 and "__none__" not in resolved_tabs:
            f["scope"] = f"tab:{next(iter(resolved_tabs))}"
        else:
            f["scope"] = "global"

    return manifest


def manifest_template(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Return a data-free copy of ``manifest`` suitable to save to disk
    as a reusable dashboard template.

    Dataset data rows are stripped; the header row (column names) is
    preserved when available so consumers know what schema each slot
    expects. Everything else (id, title, filters, layout, links, etc.)
    is deep-copied unchanged.

    Round-trips with :func:`populate_template`:

        tpl = manifest_template(m_with_dataframes)
        # ... later, at refresh time ...
        m_fresh = populate_template(tpl, {"rates": fresh_df, ...})
        compile_dashboard(m_fresh, ...)

    The template is pure JSON (no pandas), so ``json.dumps(tpl)`` works.
    """
    import copy
    if not isinstance(manifest, dict):
        raise TypeError(
            f"manifest_template: expected dict, got {type(manifest).__name__}"
        )

    # Normalize first so we always reason about the canonical
    # {name: {"source": [[header], [row], ...]}} shape.
    normalized = _normalize_manifest_datasets(copy.deepcopy(manifest))
    out = copy.deepcopy(normalized)

    ds = out.get("datasets")
    if not isinstance(ds, dict):
        return out
    for name, entry in list(ds.items()):
        header: List[Any] = []
        if isinstance(entry, dict):
            src = entry.get("source")
            if isinstance(src, list) and src and isinstance(src[0], list):
                header = list(src[0])
        ds[name] = {
            "source": [header] if header else [],
            "template": True,  # marker for populate_template sanity check
        }
    return out


def populate_template(template: Dict[str, Any],
                        datasets: Dict[str, Any],
                        *,
                        metadata: Optional[Dict[str, Any]] = None,
                        require_all_slots: bool = False) -> Dict[str, Any]:
    """Fill in a manifest template with fresh data and return a new
    manifest ready for :func:`compile_dashboard`.

    Parameters
    ----------
    template
        A manifest dict, typically produced by :func:`manifest_template`
        and re-loaded from disk via ``json.load``.
    datasets
        Mapping of dataset name -> DataFrame (or canonical list-of-lists
        source). Each entry replaces the corresponding slot in the
        template's ``datasets`` block. Names not already declared in the
        template are added.
    metadata
        Optional ``manifest.metadata`` merge (e.g. ``{"data_as_of": "..."}``).
        Existing metadata keys are preserved; passed keys override them.
    require_all_slots
        When True, raises ``KeyError`` if the template declares a dataset
        slot but no corresponding DataFrame was provided. Useful to guard
        refresh pipelines from silently missing data.

    Returns
    -------
    dict
        A new manifest ready to pass to ``compile_dashboard``. The input
        template is NOT mutated.
    """
    import copy
    if not isinstance(template, dict):
        raise TypeError(
            f"populate_template: template must be a dict, "
            f"got {type(template).__name__}"
        )
    if not isinstance(datasets, dict):
        raise TypeError(
            f"populate_template: datasets must be a dict of name -> "
            f"DataFrame, got {type(datasets).__name__}"
        )

    out = copy.deepcopy(template)
    out_ds = out.setdefault("datasets", {})

    if require_all_slots:
        missing = [
            name for name, entry in out_ds.items()
            if isinstance(entry, dict) and entry.get("template")
            and name not in datasets
        ]
        if missing:
            raise KeyError(
                f"populate_template: template declares dataset slot(s) "
                f"{sorted(missing)} but no data was provided for them"
            )

    for name, df in datasets.items():
        out_ds[name] = df  # compile_dashboard normalizes DataFrames -> source

    if metadata:
        md = out.setdefault("metadata", {})
        if not isinstance(md, dict):
            raise TypeError(
                f"populate_template: manifest.metadata must be a dict, "
                f"got {type(md).__name__}"
            )
        md.update(metadata)
    return out


def _source_to_dataframe(source: Any):
    """Materialize a manifest dataset source into a pandas DataFrame.

    Accepts either:
        [[header...], [row...], ...]     list-of-lists w/ header as row 0
        [{"col": val, ...}, ...]         list-of-dicts (column keys)

    Attempts lightweight date parsing: any column whose non-null values all
    parse as dates is converted to datetime.
    """
    import pandas as pd
    if source is None:
        return pd.DataFrame()
    if not isinstance(source, list) or not source:
        return pd.DataFrame()
    first = source[0]
    if isinstance(first, dict):
        df = pd.DataFrame(source)
    elif isinstance(first, list):
        header = first
        rows = source[1:]
        df = pd.DataFrame(rows, columns=header)
    else:
        raise TypeError(
            f"dataset.source must be list-of-lists or list-of-dicts, "
            f"got first element of type {type(first).__name__}"
        )
    for col in df.columns:
        ser = df[col]
        if ser.dtype != object:
            continue
        non_null = ser.dropna()
        if non_null.empty:
            continue
        if not all(isinstance(v, str) for v in non_null):
            continue
        parsed = pd.to_datetime(non_null, errors="coerce")
        if parsed.notna().all():
            df[col] = pd.to_datetime(ser, errors="coerce")
    return df


def _spec_to_option(
    spec: Dict[str, Any],
    datasets: Dict[str, Dict[str, Any]],
    manifest_theme: str,
    manifest_palette: Optional[str],
) -> Dict[str, Any]:
    """Lower a high-level chart spec into an ECharts option dict.

    Looks up `spec.dataset` in manifest.datasets, reconstructs a DataFrame,
    and runs it through the same builder dispatch that make_echart() uses.
    Per-spec `theme` / `palette` override the manifest defaults.

    Raises ValueError on unknown dataset / chart_type, or missing mapping.
    """
    if not isinstance(spec, dict):
        raise TypeError(f"spec must be a dict, got {type(spec).__name__}")
    chart_type = spec.get("chart_type")
    if not chart_type:
        raise ValueError("spec.chart_type is required")
    ds_name = spec.get("dataset")
    if not ds_name:
        raise ValueError("spec.dataset is required")
    if ds_name not in datasets:
        raise ValueError(
            f"spec.dataset '{ds_name}' not declared in manifest.datasets "
            f"(available: {sorted(datasets.keys())})"
        )
    mapping = spec.get("mapping")
    if mapping is None:
        raise ValueError("spec.mapping is required")
    if not isinstance(mapping, dict):
        raise TypeError("spec.mapping must be a dict")

    # Lazy imports: keep the manifest module light and avoid import cycles
    from echart_studio import _BUILDER_DISPATCH, _build_context, _apply_annotations

    if chart_type not in _BUILDER_DISPATCH:
        raise ValueError(
            f"spec.chart_type '{chart_type}' not in builder dispatch; "
            f"available: {sorted(_BUILDER_DISPATCH.keys())}"
        )

    source = datasets[ds_name].get("source")
    df = _source_to_dataframe(source)

    ctx = _build_context(
        chart_type=chart_type,
        theme=spec.get("theme") or manifest_theme,
        palette=spec.get("palette") or manifest_palette,
        dimensions=spec.get("dimensions", "wide"),
        title=spec.get("title"),
        subtitle=spec.get("subtitle"),
    )

    builder = _BUILDER_DISPATCH[chart_type]
    opt = builder(df, dict(mapping), ctx)

    spec_annotations = spec.get("annotations")
    mapping_annotations = mapping.get("annotations")
    combined: List[Dict[str, Any]] = []
    if mapping_annotations:
        combined.extend(list(mapping_annotations))
    if spec_annotations:
        combined.extend(list(spec_annotations))
    if combined:
        _apply_annotations(opt, combined)

    # Post-build cosmetic pass: humanize series / legend labels, apply
    # optional legend_position / legend_show overrides, and format
    # date-like x-axis tick labels. Each of these is a "polish layer"
    # applied uniformly across every chart type so individual builders
    # don't all need to grow the same cosmetic knobs.
    _apply_post_build_polish(opt, spec, mapping)
    return opt


def _humanize_col(name: Any) -> str:
    """Turn a column/series identifier into a readable label.

    Rules:
      * snake_case -> Title Case with spaces
      * '_pct' -> '(%)'
      * preserves all-uppercase tokens (e.g. 'us_10y' -> 'US 10Y')
      * leaves non-string input untouched
    """
    if not isinstance(name, str) or not name:
        return name
    lowered = name.lower()
    if lowered.endswith("_pct"):
        lowered = lowered[:-4] + "_(%)"
    parts = [p for p in lowered.split("_") if p]

    def _tok(t: str) -> str:
        if t == "(%)":
            return "(%)"
        if t in {"us", "eu", "uk", "jp", "cn", "em", "dm", "hk"}:
            return t.upper()
        if len(t) <= 3 and any(ch.isdigit() for ch in t):
            return t.upper()
        if t in {"pnl", "mtd", "ytd", "yoy", "mom", "wow", "eps", "dxy",
                  "gdp", "cpi", "pmi", "ism", "nfp", "oas", "vix", "var",
                  "fx", "hy", "ig", "ir"}:
            return t.upper()
        return t.capitalize()
    return " ".join(_tok(p) for p in parts)


def _apply_post_build_polish(opt: Dict[str, Any],
                               spec: Dict[str, Any],
                               mapping: Dict[str, Any]) -> None:
    """Apply polish layers to an already-built chart option in place.

    Polish layers:
      * legend position/visibility (spec.legend_position, legend_show)
      * humanize series names unless mapping.humanize is False, or override
        via mapping.series_labels = {raw_name: display_name}
      * x-axis tick date formatting via mapping.x_date_format
    """
    # Legend visibility + position overrides. These are top-level knobs
    # that apply uniformly to every chart type.
    legend = opt.get("legend") or {}
    legend_show = spec.get("legend_show")
    if legend_show is not None:
        legend["show"] = bool(legend_show)
    pos = spec.get("legend_position") or mapping.get("legend_position")
    if pos:
        # reset any prior side settings so the assignment is crisp
        for k in ("left", "right", "top", "bottom", "orient"):
            legend.pop(k, None)
        pos = str(pos).lower()
        if pos == "top":
            legend["top"] = 8
            legend["left"] = "center"
            legend["orient"] = "horizontal"
        elif pos == "bottom":
            legend["bottom"] = 8
            legend["left"] = "center"
            legend["orient"] = "horizontal"
        elif pos == "left":
            legend["left"] = 8
            legend["top"] = "middle"
            legend["orient"] = "vertical"
        elif pos == "right":
            legend["right"] = 8
            legend["top"] = "middle"
            legend["orient"] = "vertical"
        elif pos == "none":
            legend["show"] = False
        # Plain (wrapping) legend is easier to read on dashboards than
        # the paginated default when many items don't fit on one line.
        legend["type"] = "plain"
        legend.setdefault("itemGap", 14)
        legend.setdefault("textStyle", {"fontSize": 12})
    if legend:
        opt["legend"] = legend

    # Humanize series names + legend entries. Caller can disable
    # globally with mapping.humanize = False or override per-series
    # with mapping.series_labels = {raw: display}.
    humanize = mapping.get("humanize")
    overrides = mapping.get("series_labels") or {}
    if humanize is None:
        humanize = True
    def _maybe_humanize(name: str) -> Optional[str]:
        if name in overrides:
            return overrides[name]
        if not humanize:
            return None
        if "_" in name:
            return _humanize_col(name)
        # single-word lowercase token: capitalize it (so axis labels
        # like "beta" render as "Beta"). Multi-case tokens like "SPX"
        # or "AAA" are left alone.
        if name.isalpha() and name.islower():
            return _humanize_col(name)
        return None

    rename: Dict[str, str] = {}
    for s in opt.get("series") or []:
        if not isinstance(s, dict):
            continue
        orig = s.get("name")
        if not isinstance(orig, str) or not orig:
            continue
        new = _maybe_humanize(orig)
        if new and new != orig:
            # Preserve the raw column name on the series so the
            # runtime (materializeOption) can still look up the right
            # dataset column when rewiring filter state. Without this,
            # a humanised name like "ECB" doesn't match the lowercase
            # dataset column "ecb" and ECharts falls back to positional
            # index, which is wrong for long-form datasets.
            s["_column"] = orig
            s["name"] = new
            rename[orig] = new

    if rename and isinstance(opt.get("legend"), dict):
        ld = opt["legend"].get("data")
        if isinstance(ld, list):
            opt["legend"]["data"] = [
                rename.get(n, n) if isinstance(n, str) else n
                for n in ld
            ]

    # Parallel coordinates axis names come from column names; humanize
    # them unless mapping.humanize is False.
    if isinstance(opt.get("parallelAxis"), list):
        for ax in opt["parallelAxis"]:
            if not isinstance(ax, dict):
                continue
            nm = ax.get("name")
            if not isinstance(nm, str):
                continue
            new = _maybe_humanize(nm)
            if new:
                ax["name"] = new

    # Pie / donut polish:
    #   * When the legend sits at the bottom, the slice-edge labels
    #     duplicate what's in the legend AND get truncated into the
    #     tile walls ("United States..."). Hide them and rely on the
    #     legend. Users can force them back with
    #     `mapping.show_slice_labels: True`.
    #   * Also recenter / slightly shrink the pie so the plot itself
    #     is vertically centered above the legend.
    show_slice = bool(mapping.get("show_slice_labels", False))
    for s in opt.get("series") or []:
        if not isinstance(s, dict):
            continue
        if s.get("type") != "pie":
            continue
        if pos in ("top", "bottom") and not show_slice:
            label = s.get("label") or {}
            label["show"] = False
            s["label"] = label
            # Also suppress label lines connecting to hidden labels.
            s["labelLine"] = {"show": False}
            if pos == "bottom":
                s.setdefault("center", ["50%", "42%"])
            else:
                s.setdefault("center", ["50%", "58%"])
            # Give the pie a bit more breathing room now that labels
            # are gone.
            cur_r = s.get("radius")
            if isinstance(cur_r, list) and len(cur_r) == 2:
                # donut: keep the ring ratio, bump outer radius a touch
                s["radius"] = [cur_r[0], "78%"]
            else:
                s["radius"] = "72%"

    # X-axis date formatting. ECharts understands JS format functions;
    # we emit a string that the rendering layer's _reviveFns treats as
    # a live JS function so the tick label looks like "Apr 15" etc.
    x_fmt = mapping.get("x_date_format") or spec.get("x_date_format")
    if x_fmt:
        x_axis = opt.get("xAxis")
        axes: List[Dict[str, Any]]
        if isinstance(x_axis, list):
            axes = x_axis
        elif isinstance(x_axis, dict):
            axes = [x_axis]
        else:
            axes = []
        for ax in axes:
            al = ax.setdefault("axisLabel", {})
            if x_fmt == "auto":
                al["formatter"] = (
                    "function(v){"
                    " var d = new Date(v);"
                    " if (isNaN(d.getTime())) return v;"
                    " var m = ['Jan','Feb','Mar','Apr','May','Jun',"
                    "'Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];"
                    " return m + ' ' + d.getDate();"
                    "}"
                )
            else:
                al["formatter"] = str(x_fmt)

    # Axis range overrides. `y_min` / `y_max` / `x_min` / `x_max` on
    # mapping or spec get applied to the corresponding axis. Helpful
    # when auto-scale zooms the chart out to include 0 and squashes
    # the signal (e.g. rates around 5% plotted on a 0-9 axis).
    def _axis_range(axis_key: str, min_key: str, max_key: str):
        mn = mapping.get(min_key)
        mx = mapping.get(max_key)
        if mn is None and mx is None:
            mn = spec.get(min_key)
            mx = spec.get(max_key)
        if mn is None and mx is None:
            return
        axis = opt.get(axis_key)
        axes_: List[Dict[str, Any]]
        if isinstance(axis, list):
            axes_ = axis
        elif isinstance(axis, dict):
            axes_ = [axis]
        else:
            return
        for a in axes_:
            if mn is not None:
                a["min"] = mn
            if mx is not None:
                a["max"] = mx

    _axis_range("yAxis", "y_min", "y_max")
    _axis_range("xAxis", "x_min", "x_max")

    # `axis_format` / `y_format` / `x_format` shortcut for common
    # numeric label styles without writing raw ECharts functions.
    def _axis_number_format(axis_key: str, key: str):
        fmt = mapping.get(key) or spec.get(key)
        if not fmt:
            return
        axis = opt.get(axis_key)
        axes_: List[Dict[str, Any]] = (
            axis if isinstance(axis, list)
            else ([axis] if isinstance(axis, dict) else [])
        )
        fmt_str: Optional[str] = None
        if fmt == "percent":
            fmt_str = ("function(v){ return (v*100).toFixed(1) + '%'; }")
        elif fmt == "bp":
            fmt_str = ("function(v){ return v.toFixed(0) + ' bp'; }")
        elif fmt == "usd":
            fmt_str = ("function(v){ return '$' + v.toLocaleString(); }")
        elif fmt == "compact":
            fmt_str = (
                "function(v){"
                " var a = Math.abs(v);"
                " if (a >= 1e12) return (v/1e12).toFixed(1) + 'T';"
                " if (a >= 1e9)  return (v/1e9).toFixed(1) + 'B';"
                " if (a >= 1e6)  return (v/1e6).toFixed(1) + 'M';"
                " if (a >= 1e3)  return (v/1e3).toFixed(1) + 'K';"
                " return v.toString();"
                "}"
            )
        else:
            fmt_str = str(fmt)
        for a in axes_:
            al = a.setdefault("axisLabel", {})
            al["formatter"] = fmt_str

    _axis_number_format("yAxis", "y_format")
    _axis_number_format("xAxis", "x_format")

    # Axis cosmetic toggles.
    def _axis_cosmetics(axis_key: str):
        axis = opt.get(axis_key)
        if isinstance(axis, list):
            axes_ = axis
        elif isinstance(axis, dict):
            axes_ = [axis]
        else:
            return
        show_grid = spec.get("show_grid", mapping.get("show_grid"))
        show_axis_line = spec.get(
            "show_axis_line", mapping.get("show_axis_line"))
        show_axis_ticks = spec.get(
            "show_axis_ticks", mapping.get("show_axis_ticks"))
        for a in axes_:
            if show_grid is not None:
                a.setdefault("splitLine", {})["show"] = bool(show_grid)
            if show_axis_line is not None:
                a.setdefault("axisLine", {})["show"] = bool(show_axis_line)
            if show_axis_ticks is not None:
                a.setdefault("axisTick", {})["show"] = bool(show_axis_ticks)
    _axis_cosmetics("xAxis")
    _axis_cosmetics("yAxis")

    # `tooltip`: per-spec chart tooltip override. Accepts an ECharts
    # tooltip dict directly, or a sugared form:
    #   "tooltip": {
    #       "trigger": "axis" | "item" | "none",
    #       "decimals": 2,                      # format numeric values
    #       "formatter": "<fn string>",         # raw ECharts formatter
    #       "show": False,                      # hide tooltip entirely
    #   }
    tip_cfg = spec.get("tooltip")
    if tip_cfg is not None:
        tt = opt.get("tooltip") or {}
        if not isinstance(tt, dict):
            tt = {}
        if isinstance(tip_cfg, dict):
            if "show" in tip_cfg:
                tt["show"] = bool(tip_cfg["show"])
            if "trigger" in tip_cfg:
                tt["trigger"] = tip_cfg["trigger"]
            if "formatter" in tip_cfg:
                tt["formatter"] = tip_cfg["formatter"]
            if "decimals" in tip_cfg:
                d = int(tip_cfg["decimals"])
                tt["valueFormatter"] = (
                    "function(v){"
                    f" if (v == null) return '';"
                    f" var n = Number(v);"
                    f" if (isNaN(n)) return String(v);"
                    f" return n.toLocaleString(undefined,"
                    f" {{minimumFractionDigits: {d},"
                    f"   maximumFractionDigits: {d}}});"
                    "}"
                )
            # Pass through any unknown keys verbatim so callers can
            # reach ECharts-native tooltip options.
            for k, v in tip_cfg.items():
                if k in {"show", "trigger", "formatter", "decimals"}:
                    continue
                tt[k] = v
        opt["tooltip"] = tt

    # Per-series color overrides. `mapping.series_colors = {raw_col:
    # "#hex"}`. We look up by either the pre-humanise `_column` or the
    # final `name`, so callers can reference whichever is natural.
    series_colors = mapping.get("series_colors") or {}
    if isinstance(series_colors, dict) and series_colors:
        for s in opt.get("series") or []:
            if not isinstance(s, dict):
                continue
            col_key = s.get("_column") or s.get("name")
            if col_key in series_colors:
                s.setdefault("itemStyle", {})["color"] = \
                    series_colors[col_key]
                s.setdefault("lineStyle", {})["color"] = \
                    series_colors[col_key]

    # `grid_padding`: per-spec grid override. Accepts a dict with any
    # subset of {top, right, bottom, left} and merges into the option's
    # grid. Useful when a chart has an especially long y-axis title
    # or tick labels that need more breathing room. Auto-bumps
    # `right` when a dual-axis chart emits a right-side axis name so
    # the rotated label doesn't clip against the tile edge.
    pad = (spec.get("grid_padding") or mapping.get("grid_padding")
           or {})
    grid = opt.get("grid") or {}
    if isinstance(grid, list):
        grids = grid
    elif isinstance(grid, dict):
        grids = [grid]
    else:
        grids = []
    yaxes = opt.get("yAxis")
    has_right_axis_name = (
        isinstance(yaxes, list) and len(yaxes) >= 2
        and isinstance(yaxes[1], dict) and yaxes[1].get("name")
    )
    for g in grids:
        for k in ("top", "right", "bottom", "left"):
            if k in pad:
                g[k] = pad[k]
        if has_right_axis_name and "right" not in pad:
            # Ensure the rotated right-axis name has room even when
            # tick labels run to 4 or 5 digits on the right side.
            g["right"] = max(int(g.get("right", 24) or 24), 56)


def _resolve_chart_specs(manifest: Dict[str, Any],
                          base_dir: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """Resolve every chart widget in the manifest into an ECharts option dict.

    Resolution order per widget (first match wins):

        1. spec={...}       high-level -> lowered via builder dispatch
        2. option={...}     inline raw option
        3. option_inline    legacy alias for option
        4. ref="..."        load JSON from base_dir / ref or cwd / ref

    Widgets that don't match any of these are left with an empty series dict
    so the renderer still produces a card (blank chart) instead of failing.
    """
    specs: Dict[str, Dict[str, Any]] = {}
    datasets = manifest.get("datasets", {}) or {}
    manifest_theme = manifest.get("theme", "gs_clean")
    manifest_palette = manifest.get("palette")

    def _suppress_chart_title_if_widget_has_one(w, opt):
        """When the widget has its own title rendered in the tile
        header, clear the internal ECharts title to avoid the double
        "ACME daily OHLC / ACME daily OHLC" headline. The chart's
        subtitle stays so callers can use `spec.subtitle` for extra
        context (e.g. "daily OHLC"). Widget author can override by
        setting ``spec.keep_title: True``.
        """
        if not isinstance(opt, dict):
            return opt
        if not w.get("title"):
            return opt
        spec_obj = w.get("spec") or {}
        if isinstance(spec_obj, dict) and spec_obj.get("keep_title"):
            return opt
        title = opt.get("title")
        if isinstance(title, dict):
            title["text"] = ""
        return opt

    def visit(rows):
        for row in rows or []:
            for w in row:
                if w.get("widget") != "chart":
                    continue
                wid = w.get("id")
                if not wid:
                    continue
                if isinstance(w.get("spec"), dict):
                    opt = _spec_to_option(
                        w["spec"], datasets, manifest_theme, manifest_palette
                    )
                    specs[wid] = _suppress_chart_title_if_widget_has_one(w, opt)
                    continue
                if isinstance(w.get("option"), dict):
                    specs[wid] = _suppress_chart_title_if_widget_has_one(
                        w, w["option"]
                    )
                    continue
                if isinstance(w.get("option_inline"), dict):
                    specs[wid] = _suppress_chart_title_if_widget_has_one(
                        w, w["option_inline"]
                    )
                    continue
                ref = w.get("ref")
                if ref and base_dir:
                    candidate = (Path(base_dir) / ref)
                    if candidate.is_file():
                        specs[wid] = _suppress_chart_title_if_widget_has_one(
                            w,
                            json.loads(candidate.read_text(encoding="utf-8"))
                        )
                        continue
                if ref and Path(ref).is_file():
                    specs[wid] = _suppress_chart_title_if_widget_has_one(
                        w,
                        json.loads(Path(ref).read_text(encoding="utf-8"))
                    )

    layout = manifest.get("layout", {}) or {}
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            visit(tab.get("rows", []))
    else:
        visit(layout.get("rows", []))
    return specs


# =============================================================================
# PUBLIC FUNCTIONS
# =============================================================================


def render_dashboard(manifest: Dict[str, Any],
                      output_path: Optional[Union[str, Path]] = None,
                      chart_specs: Optional[Dict[str, Dict[str, Any]]] = None,
                      base_dir: Optional[Union[str, Path]] = None) -> DashboardResult:
    """Render an already-validated or in-memory manifest to HTML.

    If chart_specs is None, refs in the manifest are resolved relative to
    base_dir (or the output_path's parent directory). High-level `spec`
    widgets are lowered to ECharts options via the builder dispatch.

    DataFrames in manifest.datasets (via the .source field or as shorthand
    for the entry itself) are transparently converted to source arrays.
    """
    _normalize_manifest_datasets(manifest)
    _augment_manifest(manifest)
    ok, errs = validate_manifest(manifest)
    if not ok:
        return DashboardResult(
            manifest=manifest, manifest_path=None,
            html_path=None, html=None, success=False,
            error_message="manifest validation failed",
            warnings=list(errs),
        )
    if chart_specs is None:
        base = Path(base_dir) if base_dir else (
            Path(output_path).parent if output_path else Path.cwd()
        )
        try:
            chart_specs = _resolve_chart_specs(manifest, base)
        except (ValueError, TypeError) as e:
            return DashboardResult(
                manifest=manifest, manifest_path=None,
                html_path=None, html=None, success=False,
                error_message=f"spec resolution failed: {e}",
                warnings=[str(e)],
            )
    html = render_dashboard_html(manifest, chart_specs,
                                  filename_base=manifest.get("id", "dashboard"))
    html_path: Optional[Path] = None
    if output_path:
        html_path = Path(output_path)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")
    return DashboardResult(
        manifest=manifest, manifest_path=None,
        html_path=str(html_path) if html_path else None,
        html=html, success=True, warnings=[],
    )


def compile_dashboard(
    manifest: Union[Dict[str, Any], str, Path],
    session_path: Optional[Union[str, Path]] = None,
    output_path: Optional[Union[str, Path]] = None,
    write_html: bool = True,
    write_json: bool = True,
    save_pngs: bool = False,
    png_dir: Optional[Union[str, Path]] = None,
    png_scale: int = 2,
) -> DashboardResult:
    """JSON-first entry point. Compile a manifest to a dashboard.

    Accepts any of:
        * a manifest dict
        * a JSON string containing the manifest
        * a filesystem path (str or Path) to a manifest JSON file

    Side effects (when write_html/write_json):
        * session_path  -> session_path/dashboards/{id}.json + {id}.html
        * output_path   -> output_path + .json + .html (suffixes forced)
        * neither       -> returns result with html attribute only, no IO

    Unlike render_dashboard(), this function always re-validates and always
    runs the spec resolver, and it writes the *canonical* manifest JSON
    alongside the HTML. This is the function PRISM should call.

    High-level `spec` widgets are lowered to ECharts option JSON at compile
    time; the written manifest mirrors the input exactly (specs are NOT
    inlined into the manifest, they're resolved only for the HTML payload).
    """
    if isinstance(manifest, (str, Path)):
        base_dir: Optional[Path] = None
        text = str(manifest).strip()
        if text.startswith("{"):
            manifest_dict = json.loads(text)
        else:
            p = Path(manifest)
            try:
                is_file = p.is_file()
            except OSError:
                is_file = False
            if is_file:
                manifest_dict = load_manifest(p)
                base_dir = p.parent
            else:
                raise FileNotFoundError(
                    f"compile_dashboard: '{manifest}' is neither a valid file "
                    f"path nor a JSON string"
                )
    elif isinstance(manifest, dict):
        manifest_dict = manifest
        base_dir = None
    else:
        raise TypeError(
            f"compile_dashboard: manifest must be dict, str, or Path; "
            f"got {type(manifest).__name__}"
        )

    _normalize_manifest_datasets(manifest_dict)
    _augment_manifest(manifest_dict)

    ok, errs = validate_manifest(manifest_dict)
    if not ok:
        return DashboardResult(
            manifest=manifest_dict, manifest_path=None,
            html_path=None, html=None, success=False,
            error_message="manifest validation failed",
            warnings=list(errs),
        )

    manifest_path: Optional[Path] = None
    html_path: Optional[Path] = None
    if output_path:
        html_path = Path(output_path)
        if html_path.suffix.lower() != ".html":
            html_path = html_path.with_suffix(".html")
        manifest_path = html_path.with_suffix(".json")
        base_dir = base_dir or html_path.parent
    elif session_path:
        sp = Path(session_path) / "dashboards"
        sp.mkdir(parents=True, exist_ok=True)
        dashboard_id = manifest_dict.get("id", "dashboard")
        manifest_path = sp / f"{dashboard_id}.json"
        html_path = sp / f"{dashboard_id}.html"
        base_dir = base_dir or Path(session_path)

    if manifest_path and write_json:
        save_manifest(manifest_dict, manifest_path)

    try:
        chart_specs = _resolve_chart_specs(manifest_dict, base_dir)
    except (ValueError, TypeError) as e:
        return DashboardResult(
            manifest=manifest_dict,
            manifest_path=str(manifest_path) if manifest_path else None,
            html_path=None, html=None, success=False,
            error_message=f"spec resolution failed: {e}",
            warnings=[str(e)],
        )

    html = render_dashboard_html(
        manifest_dict, chart_specs,
        filename_base=manifest_dict.get("id", "dashboard"),
    )

    if html_path and write_html:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    warnings: List[str] = []
    if save_pngs:
        # pick a dir: explicit override, or alongside the html file
        resolved_png_dir: Optional[Path] = None
        if png_dir is not None:
            resolved_png_dir = Path(png_dir)
        elif html_path is not None:
            resolved_png_dir = html_path.parent / (html_path.stem + "_pngs")
        elif session_path is not None:
            resolved_png_dir = Path(session_path) / "pngs"
        if resolved_png_dir is None:
            warnings.append(
                "save_pngs=True but no png_dir/html_path/session_path "
                "provided; skipping PNG export."
            )
        else:
            try:
                from rendering import save_dashboard_pngs
                save_dashboard_pngs(
                    manifest_dict, chart_specs, resolved_png_dir,
                    scale=int(png_scale),
                )
            except Exception as e:  # noqa: BLE001
                warnings.append(f"PNG export failed: {e}")

    return DashboardResult(
        manifest=manifest_dict,
        manifest_path=str(manifest_path) if manifest_path else None,
        html_path=str(html_path) if html_path else None,
        html=html, success=True, warnings=warnings,
    )


__all__ = [
    "Dashboard", "DashboardResult", "Tab",
    "ChartRef", "KPIRef", "TableRef", "MarkdownRef", "DividerRef",
    "GlobalFilter", "Link",
    "compile_dashboard", "render_dashboard",
    "load_manifest", "validate_manifest", "save_manifest",
    "df_to_source", "manifest_template", "populate_template",
    "SCHEMA_VERSION", "VALID_WIDGETS", "VALID_FILTERS",
    "VALID_CHART_TYPES", "VALID_FILTER_OPS", "VALID_SYNC",
    "VALID_BRUSH_TYPES", "VALID_TABLE_FORMATS",
    "VALID_REFRESH_FREQUENCIES",
]




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


# DASHBOARD CLI (filled in when echart_dashboard exists)
# ---------------------------------------------------------------------------

def run_dashboard_cli(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv:
        return _interactive_dashboard()

    p = argparse.ArgumentParser("echart_dashboard")
    sub = p.add_subparsers(dest="cmd")

    c = sub.add_parser(
        "compile",
        help="compile a manifest JSON to an interactive dashboard (recommended)",
    )
    c.add_argument("manifest", help="manifest JSON file path OR raw JSON string")
    c.add_argument("-o", "--output",
                    help="output HTML path (manifest written alongside)")
    c.add_argument("-s", "--session",
                    help="session dir; writes dashboards/{id}.json + .html inside")
    c.add_argument("--open", action="store_true")
    c.add_argument("--pngs", action="store_true",
                     help="also render each chart widget to PNG")
    c.add_argument("--png-dir",
                     help="directory for PNGs (default: <html>_pngs/ "
                          "next to the HTML)")
    c.add_argument("--png-scale", type=int, default=2,
                     help="device-pixel multiplier for PNG output")

    b = sub.add_parser("build", help="render a manifest to HTML (alias of compile)")
    b.add_argument("manifest")
    b.add_argument("-o", "--output")
    b.add_argument("--open", action="store_true")

    v = sub.add_parser("validate", help="validate a manifest")
    v.add_argument("manifest")

    demo = sub.add_parser("demo", help="render sample dashboards")
    demo.add_argument("--output-dir", default="dashboards_demo")
    demo.add_argument("--pngs", action="store_true",
                       help="also render PNGs for every chart in every sample")

    l = sub.add_parser("list", help="list widgets|filters|links|chart_types")
    l.add_argument("target")

    args = p.parse_args(argv)
    if args.cmd == "compile":
        r = compile_dashboard(
            args.manifest,
            session_path=args.session,
            output_path=args.output,
            save_pngs=bool(getattr(args, "pngs", False)),
            png_dir=getattr(args, "png_dir", None),
            png_scale=int(getattr(args, "png_scale", 2) or 2),
        )
        if not r.success:
            print(f"  FAIL: {r.error_message}", file=sys.stderr)
            for w in r.warnings:
                print(f"    - {w}", file=sys.stderr)
            return 1
        print(f"manifest: {r.manifest_path}")
        print(f"html    : {r.html_path}")
        for w in r.warnings:
            print(f"warning : {w}")
        if args.open and r.html_path:
            webbrowser.open(f"file://{Path(r.html_path).resolve()}")
        return 0
    elif args.cmd == "build":
        m = load_manifest(args.manifest)
        out = args.output or Path(args.manifest).with_suffix(".html").name
        r = render_dashboard(m, output_path=out)
        if not r.success:
            print(f"  FAIL: {r.error_message}", file=sys.stderr)
            return 1
        print(f"wrote {r.html_path}")
        if args.open:
            webbrowser.open(f"file://{Path(r.html_path).resolve()}")
        return 0
    elif args.cmd == "validate":
        m = load_manifest(args.manifest)
        ok, errs = validate_manifest(m)
        if ok:
            print("OK")
            return 0
        for e in errs:
            print(f"  ERROR: {e}")
        return 1
    elif args.cmd == "demo":
        from samples import DASHBOARD_SAMPLES
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        start = time.time(); last = [start]
        for name, build in DASHBOARD_SAMPLES.items():
            m = build()
            r = compile_dashboard(
                m, output_path=str(out / f"{name}.html"),
                save_pngs=bool(getattr(args, "pngs", False)),
            )
            print(f"wrote {r.html_path}")
            for w in r.warnings:
                print(f"  warn: {w}")
            _heartbeat(name, start, last)
        return 0
    elif args.cmd == "list":
        target = args.target
        if target == "widgets":
            for w in ["chart", "kpi", "table", "markdown", "divider"]:
                print(f"  {w}")
        elif target == "filters":
            for f in ["dateRange", "select", "multiSelect", "numberRange", "toggle"]:
                print(f"  {f}")
        elif target == "links":
            for link in ["connect (axis/tooltip)", "brush (rect/polygon/lineX/lineY)"]:
                print(f"  {link}")
        elif target == "chart_types":
            for ct in sorted(VALID_CHART_TYPES):
                print(f"  {ct}")
        else:
            print(f"  unknown target: {target}", file=sys.stderr)
            return 2
        return 0
    p.print_help()
    return 2


def _interactive_dashboard() -> int:
    while True:
        print("""
echart_dashboard -- main menu
  1. compile a manifest to an interactive dashboard
  2. validate a manifest
  3. render sample dashboards
  4. list widgets / filters / links / chart_types
  q. quit
""")
        choice = _ask("choice", default="q")
        if choice == "q":
            return 0
        if choice == "1":
            mp = _ask("manifest path")
            sess = _ask("session dir (blank for alongside manifest)", default="")
            args_list = ["compile", mp]
            if sess:
                args_list += ["-s", sess]
            else:
                out = _ask("output html", default=str(Path(mp).with_suffix(".html").name))
                args_list += ["-o", out]
            run_dashboard_cli(args_list)
        elif choice == "2":
            mp = _ask("manifest path")
            run_dashboard_cli(["validate", mp])
        elif choice == "3":
            out = _ask("output dir", default="dashboards_demo")
            run_dashboard_cli(["demo", "--output-dir", out])
        elif choice == "4":
            target = _choice("target",
                               ["widgets", "filters", "links", "chart_types"],
                               default="chart_types")
            run_dashboard_cli(["list", target])

def main(argv: Optional[List[str]] = None) -> int:
    return run_dashboard_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
