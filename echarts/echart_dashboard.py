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

import difflib
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
                  "stat_grid", "image", "note"}
# Semantic kinds for the `note` widget (callouts for narrative writing).
# Each kind drives a distinct accent color + label so PRISM can flag
# load-bearing prose ("this is the thesis", "this is a risk", etc.)
# rather than relying on a flat markdown widget for everything.
VALID_NOTE_KINDS = {"insight", "thesis", "watch", "risk",
                     "context", "fact"}
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

    Datasets are normalized on a shallow copy so that DataFrames passed
    in via ``manifest.datasets`` stay intact for downstream consumers
    -- specifically :func:`_capture_shape_info`, which needs the
    original DataFrame shapes to emit shape diagnostics. A caller that
    does ``validate_manifest(m); compile_dashboard(m)`` keeps full
    shape-diagnostic coverage on the second call.

    Other in-place augmentations (filter ``scope`` inference, ``radio``
    / ``select`` / ``multiSelect`` dict-default reduction to primitive
    values) DO mutate the input -- those have always been documented as
    the validator's job and several callers rely on them.

    Missing required fields produce one error each; the validator
    does not short-circuit on first error.
    """
    errs: List[str] = []
    if not isinstance(manifest, dict):
        return False, [_err("(root)", "manifest must be a dict")]
    # Datasets get a throwaway working copy so DataFrames in the
    # caller's manifest stay raw. Everything else is normalized
    # in place (filter defaults, scope inference) -- those mutations
    # are part of the contract.
    _validate_dataset_restore: Optional[Dict[str, Any]] = None
    original_datasets = manifest.get("datasets")
    if isinstance(original_datasets, dict):
        working_datasets = {k: v for k, v in original_datasets.items()}
        manifest["datasets"] = working_datasets
        _validate_dataset_restore = original_datasets
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
            # methodology: markdown string OR {title?, body} dict.
            # Drives the header "Methodology" popup button.
            meth = metadata.get("methodology")
            if meth is not None:
                if isinstance(meth, str):
                    pass
                elif isinstance(meth, dict):
                    for k in ("title", "body", "text"):
                        v = meth.get(k)
                        if v is not None and not isinstance(v, str):
                            errs.append(_err(
                                f"metadata.methodology.{k}",
                                f"must be a string, got {type(v).__name__}"))
                    if not (meth.get("body") or meth.get("text")):
                        errs.append(_err(
                            "metadata.methodology",
                            "dict form requires a 'body' (or 'text') key"))
                else:
                    errs.append(_err(
                        "metadata.methodology",
                        "must be a markdown string or "
                        "{title?, body} dict"))

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
        if ft in ("select", "multiSelect", "radio"):
            if "options" not in f:
                errs.append(_err(f"{base}.options",
                                  f"required for type '{ft}'"))
            else:
                opts = f.get("options")
                if not isinstance(opts, list):
                    errs.append(_err(f"{base}.options",
                                      f"must be a list, got {type(opts).__name__}"))
                else:
                    for oi, o in enumerate(opts):
                        opath = f"{base}.options[{oi}]"
                        if isinstance(o, dict):
                            if "value" not in o:
                                errs.append(_err(
                                    opath,
                                    "dict option missing required 'value' "
                                    "key (use {\"value\": ..., \"label\": ...})"))
                            extras = set(o.keys()) - {"value", "label"}
                            if extras:
                                errs.append(_err(
                                    opath,
                                    f"dict option has unsupported keys "
                                    f"{sorted(extras)}; only "
                                    f"'value' and 'label' are allowed"))
                        elif not isinstance(o, (str, int, float, bool)):
                            errs.append(_err(
                                opath,
                                f"option must be a primitive (str/int/float/"
                                f"bool) or {{'value', 'label'}} dict, got "
                                f"{type(o).__name__}: {o!r}"))
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
                    click_popup = w.get("click_popup")
                    if click_popup is not None and not isinstance(click_popup, dict):
                        errs.append(_err(
                            f"{wbase}.click_popup",
                            "must be a dict when present (mirrors table 'row_click' "
                            "shape: title_field, subtitle_template, popup_fields, "
                            "or detail.sections[])"
                        ))
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
                elif wt == "note":
                    if "body" not in w:
                        errs.append(_err(f"{wbase}.body",
                                           "required for note"))
                    kind = w.get("kind", "insight")
                    if kind not in VALID_NOTE_KINDS:
                        errs.append(_err(
                            f"{wbase}.kind",
                            f"'{kind}' not in {sorted(VALID_NOTE_KINDS)}"
                        ))
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

    # Restore the caller's original dataset entries so DataFrames
    # remain available to downstream callers (compile_dashboard's
    # _capture_shape_info, in particular).
    if _validate_dataset_restore is not None:
        manifest["datasets"] = _validate_dataset_restore

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
class NoteRef:
    """Semantic callout tile for narrative commentary.

    Distinct from a plain ``markdown`` widget in two ways:
      1. The ``kind`` (``insight`` / ``thesis`` / ``watch`` / ``risk``
         / ``context`` / ``fact``) drives a colored left-edge stripe
         and small kind label so the reader can tell at a glance
         which paragraphs are load-bearing.
      2. It always renders as a tinted card (instead of the markdown
         widget's transparent-prose styling) so it visually breaks
         from surrounding flat text.

    ``body`` is markdown using the same grammar as the ``markdown``
    widget. ``title`` is plain text. ``icon`` is an optional short
    glyph rendered to the left of the title.
    """
    id: str
    body: str
    kind: str = "insight"
    title: Optional[str] = None
    icon: Optional[str] = None
    w: int = 12

    def to_dict(self) -> Dict[str, Any]:
        if self.kind not in VALID_NOTE_KINDS:
            raise ValueError(
                f"NoteRef.kind '{self.kind}' not in "
                f"{sorted(VALID_NOTE_KINDS)}"
            )
        d: Dict[str, Any] = {
            "widget": "note", "id": self.id,
            "kind": self.kind, "body": self.body, "w": self.w,
        }
        if self.title is not None:
            d["title"] = self.title
        if self.icon is not None:
            d["icon"] = self.icon
        return d


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
    # Structured chart-data diagnostics (separate from `warnings`, which
    # is kept as flat strings for backwards compat). PRISM should read
    # these directly when iterating on a manifest.
    diagnostics: List["Diagnostic"] = field(default_factory=list)


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

    # Reduce {value, label} dict defaults to their underlying value so the
    # JS runtime (which compares filterState[id] against row cells via
    # String() coercion) stays primitive-only. Options themselves keep
    # their original dict shape -- the renderer extracts value+label from
    # them in _option_value_label.
    def _strip_option_dict(v: Any) -> Any:
        if isinstance(v, dict) and "value" in v:
            return v["value"]
        return v

    for f in filters:
        if not isinstance(f, dict):
            continue
        if f.get("type") not in ("select", "multiSelect", "radio"):
            continue
        if "default" not in f:
            continue
        d = f["default"]
        if isinstance(d, list):
            f["default"] = [_strip_option_dict(x) for x in d]
        else:
            f["default"] = _strip_option_dict(d)

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

    The ``pd.to_datetime(..., errors="coerce")`` probe is wrapped in
    ``warnings.catch_warnings`` so the dateutil-fallback ``UserWarning``
    pandas emits on string columns doesn't pollute compile_dashboard's
    output. The probe is just our heuristic and the user explicitly
    opted into best-effort parsing by passing a string column.
    """
    import pandas as pd
    import warnings
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
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
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


def _empty_placeholder_option(reason: str) -> Dict[str, Any]:
    """Minimal ECharts option used as a fallback when a chart's spec
    cannot be lowered to a real option (missing column, build error,
    etc.). The placeholder renders as a graphic-text annotation inside
    the otherwise-empty chart card, so the dashboard still loads and
    PRISM can see exactly which tile failed."""
    return {
        "title": {"text": "(no data)", "left": "center", "top": "middle",
                   "textStyle": {"fontSize": 12, "fontWeight": "normal",
                                   "color": "#999"},
                   "subtext": reason[:140] if reason else "",
                   "subtextStyle": {"fontSize": 10, "color": "#bbb"}},
        "xAxis": {"show": False},
        "yAxis": {"show": False},
        "series": [],
    }


def _resolve_chart_specs(manifest: Dict[str, Any],
                          base_dir: Optional[Path],
                          diags: Optional[List["Diagnostic"]] = None
                          ) -> Dict[str, Dict[str, Any]]:
    """Resolve every chart widget in the manifest into an ECharts option dict.

    Resolution order per widget (first match wins):

        1. spec={...}       high-level -> lowered via builder dispatch
        2. option={...}     inline raw option
        3. option_inline    legacy alias for option
        4. ref="..."        load JSON from base_dir / ref or cwd / ref

    Widgets that don't match any of these are left with an empty series dict
    so the renderer still produces a card (blank chart) instead of failing.

    Per-chart resilience: when a spec fails to lower (missing columns,
    bad chart_type, etc.) we capture the failure as a Diagnostic into
    ``diags`` (when provided) and substitute a placeholder option so
    sibling charts still compile. PRISM-iteration callers should pass
    ``diags=[]`` and surface the accumulated list to the LLM.
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

    def _record_build_failure(wid: str, wpath: str, reason: str,
                                ctx: Dict[str, Any]) -> None:
        if diags is None:
            return
        diags.append(Diagnostic(
            severity="error", code="chart_build_failed",
            widget_id=wid, path=f"{wpath}.spec",
            message=(f"chart '{wid}' build raised: {reason}"),
            context=ctx))

    def visit(rows, path_prefix: str):
        for ri, row in enumerate(rows or []):
            for wi, w in enumerate(row):
                if w.get("widget") != "chart":
                    continue
                wid = w.get("id")
                if not wid:
                    continue
                wpath = f"{path_prefix}[{ri}][{wi}]"
                if isinstance(w.get("spec"), dict):
                    try:
                        opt = _spec_to_option(
                            w["spec"], datasets,
                            manifest_theme, manifest_palette,
                        )
                        specs[wid] = _suppress_chart_title_if_widget_has_one(
                            w, opt)
                    except (ValueError, TypeError, KeyError) as e:
                        _record_build_failure(
                            wid, wpath, str(e),
                            {"chart_type": w["spec"].get("chart_type"),
                              "dataset": w["spec"].get("dataset"),
                              "exception_type": type(e).__name__})
                        specs[wid] = _empty_placeholder_option(str(e))
                    except Exception as e:  # noqa: BLE001
                        _record_build_failure(
                            wid, wpath, str(e),
                            {"chart_type": w["spec"].get("chart_type"),
                              "dataset": w["spec"].get("dataset"),
                              "exception_type": type(e).__name__})
                        specs[wid] = _empty_placeholder_option(str(e))
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
        for ti, tab in enumerate(layout.get("tabs", []) or []):
            visit(tab.get("rows", []),
                  f"layout.tabs[{ti}].rows")
    else:
        visit(layout.get("rows", []), "layout.rows")
    return specs


# =============================================================================
# DATA DIAGNOSTICS
#
# Programmatic detection of chart/table/kpi widgets that will render as
# blank or broken because of empty datasets, missing columns, all-NaN
# series, etc. These are NOT validation errors -- the manifest is
# structurally valid, but the *data* won't produce a meaningful chart.
#
# Diagnostics are accumulated per widget so PRISM can see ALL data
# problems in one compile cycle (instead of fixing one and re-compiling
# to discover the next). Severity is informational, not blocking:
# compile_dashboard still emits HTML, with broken charts replaced by an
# empty-state placeholder.
# =============================================================================

# -----------------------------------------------------------------------------
# Data budget thresholds.
#
# Size limits are deterministic guardrails -- a dashboard that embeds
# 250k rows or 26 MB of data is broken regardless of whether every
# chart spec validates. Warnings are advisory; errors block compilation
# under ``strict=True``. PRISM is expected to keep datasets under
# these limits via top-N filtering, reduced lookback, or a lazy-load
# drill-down pattern (see DATA_SHAPES.md "Data budget limits").
# -----------------------------------------------------------------------------

# Single-dataset row counts. Daily-2y = 500, daily-10y = 2500, daily-20y
# = 5000 -- the warn threshold lets normal dashboards through and
# catches obvious history-pre-loading. The error threshold catches
# universe-scale embedding (the 248k-row drill-down case).
DATASET_ROWS_WARN = 10_000
DATASET_ROWS_ERROR = 50_000

# Single-dataset serialised JSON bytes. 2 MB is the cliff above which
# browser parse + render starts to feel sluggish even on a fast
# machine. 1 MB is the soft warning.
DATASET_BYTES_WARN = 1_048_576       # 1 MB
DATASET_BYTES_ERROR = 2_097_152      # 2 MB

# Total manifest serialised bytes. The HTML payload roughly tracks
# this; 5 MB+ HTML files take 1-2 seconds just to parse.
MANIFEST_BYTES_WARN = 3_145_728      # 3 MB
MANIFEST_BYTES_ERROR = 5_242_880     # 5 MB

# Table widget row counts. The table widget renders every row into the
# DOM regardless of `max_rows` (which only limits the visible
# viewport), so very large tables are slow to interact with.
TABLE_ROWS_WARN = 1_000
TABLE_ROWS_ERROR = 5_000

# Mapping keys whose values are dataset column references (string or
# list of strings). Anything not in this set is treated as a config
# flag (e.g. legend_position, x_log, humanize) and not column-checked.
_COLUMN_REF_KEYS = {
    "x", "y", "value", "color", "colour", "size",
    "source", "target", "weight", "name", "category",
    "low", "high", "open", "close", "date",
    "strokeDash", "id", "parent", "labels",
    "dims", "path", "series", "node",
}

# Required mapping keys per chart_type. Mirrors the builder's own
# raise-on-missing logic in echart_studio.py; we surface it as a
# diagnostic up-front so PRISM gets the available-columns context
# without parsing a Python traceback.
_REQUIRED_MAPPING_KEYS: Dict[str, Tuple[str, ...]] = {
    "line": ("x", "y"),
    "multi_line": ("x", "y"),
    "bar": ("x", "y"),
    "bar_horizontal": ("x", "y"),
    "scatter": ("x", "y"),
    "scatter_multi": ("x", "y"),
    "area": ("x", "y"),
    "heatmap": ("x", "y", "value"),
    "pie": ("category", "value"),
    "donut": ("category", "value"),
    "histogram": ("x",),
    "bullet": ("value",),
    "sankey": ("source", "target", "value"),
    "candlestick": ("x", "open", "high", "low", "close"),
    "calendar_heatmap": ("date", "value"),
    "funnel": ("category", "value"),
    "gauge": ("value",),
    "radar": ("category", "value"),
    "graph": ("source", "target"),
    "boxplot": ("x", "y"),
    "parallel_coords": ("dims",),
    "tree": ("name", "parent"),
    # treemap/sunburst accept either {path, value} or {name, parent, value};
    # require_any_of handled below in _check_chart_widget.
    "treemap": (),
    "sunburst": (),
}

# chart_types whose required mapping is "either A-set OR B-set"
# (rather than a single hardcoded list). Each entry is a list of valid
# alternatives, where each alternative is itself a tuple of required
# keys. The diagnostic fires only when none of the alternatives are
# satisfied, with the union of required keys cited as context.
_REQUIRED_MAPPING_KEYS_ANY_OF: Dict[str, List[Tuple[str, ...]]] = {
    "treemap":  [("path", "value"), ("name", "parent", "value")],
    "sunburst": [("path", "value"), ("name", "parent", "value")],
}

# Mapping keys whose referenced column should be numeric (floats / ints /
# convertible). A non-numeric column here typically means the chart
# silently degenerates to the wrong axis type or a flat line.
_NUMERIC_COLUMN_REF_KEYS = {
    "y", "value", "size", "weight", "low", "high", "open", "close",
}


@dataclass
class Diagnostic:
    """A structured chart-data finding from :func:`chart_data_diagnostics`.

    Designed to be both human- and LLM-readable. ``code`` is a stable
    short identifier; PRISM iteration prompts can pattern-match on
    ``code`` to fix specific failure modes. ``context`` carries the
    actionable data (e.g. ``available_columns``) needed to repair the
    manifest without another inspection round-trip.
    """
    severity: str           # "error" | "warning" | "info"
    code: str
    widget_id: Optional[str]
    path: str               # dotted manifest path, e.g. layout.rows[0][0]
    message: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity, "code": self.code,
            "widget_id": self.widget_id, "path": self.path,
            "message": self.message, "context": dict(self.context),
        }

    def __str__(self) -> str:
        wid = f" [{self.widget_id}]" if self.widget_id else ""
        ctx = ""
        if self.context:
            try:
                ctx = " " + json.dumps(self.context, default=str,
                                         sort_keys=True)
            except (TypeError, ValueError):
                ctx = f" {self.context!r}"
        return (f"[{self.severity}] {self.code}{wid} @ {self.path}: "
                f"{self.message}{ctx}")


def _series_is_numeric(ser) -> bool:
    """True iff a pandas Series can be coerced to numeric without
    every value going NaN. Strings like '1.23' count as numeric."""
    import pandas as pd
    if ser is None or len(ser) == 0:
        return False
    if pd.api.types.is_numeric_dtype(ser):
        return True
    coerced = pd.to_numeric(ser, errors="coerce")
    return coerced.notna().any()


def _all_nan(ser) -> bool:
    """True iff every value in the series is null / NaN / None."""
    import pandas as pd
    if ser is None:
        return True
    if len(ser) == 0:
        return True
    return bool(pd.isna(ser).all())


def _nan_fraction(ser) -> float:
    """Fraction (0..1) of NaN/None in the series."""
    import pandas as pd
    if ser is None or len(ser) == 0:
        return 1.0
    return float(pd.isna(ser).mean())


def _walk_column_refs(mapping: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return [(mapping_key, column_name), ...] for every column-reference
    in a chart mapping. Handles both string values and list-of-string
    values. Skips non-string non-list values (those are config flags)."""
    out: List[Tuple[str, str]] = []
    for k, v in (mapping or {}).items():
        if k not in _COLUMN_REF_KEYS:
            continue
        if isinstance(v, str):
            out.append((k, v))
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str):
                    out.append((k, item))
    return out


def _did_you_mean(target: str, candidates: List[Any],
                    n: int = 3, cutoff: float = 0.6) -> List[str]:
    """Return up to ``n`` close-match suggestions for ``target`` from
    ``candidates``. Used to add typo hints to column-missing diagnostics
    so PRISM gets actionable repair guidance (e.g. ``us_2y`` -> ``usd_2y``)
    rather than just the available-columns dump.

    Includes a case-insensitive pass before falling back to difflib so
    'date' -> 'Date' and 'us_2y' -> 'US_2Y' still match even when the
    edit distance is large. Returns empty list when nothing close enough.

    Non-string candidates (e.g. MultiIndex column tuples) are filtered
    out before comparison so a malformed dataset doesn't crash the
    diagnostic emitter -- the dedicated shape diagnostic
    ``dataset_columns_multiindex`` already names that mistake.
    """
    if not target or not candidates:
        return []
    str_candidates = [c for c in candidates if isinstance(c, str)]
    if not str_candidates:
        return []
    target_lc = target.lower()
    case_hits = [c for c in str_candidates if c.lower() == target_lc]
    if case_hits:
        return case_hits[:n]
    return difflib.get_close_matches(target, str_candidates,
                                      n=n, cutoff=cutoff)


def _suggest_for_missing_column(
    column: str, available: List[str]
) -> Dict[str, Any]:
    """Bundle the ``did_you_mean`` + ``fix_hint`` keys for a missing-column
    diagnostic context. Returned dict can be merged into the existing
    context. Empty when no close match found -- caller still gets the
    available_columns list either way.
    """
    suggestions = _did_you_mean(column, list(available))
    out: Dict[str, Any] = {}
    if suggestions:
        out["did_you_mean"] = suggestions
        if len(suggestions) == 1:
            out["fix_hint"] = (
                f"Did you mean '{suggestions[0]}'? Replace '{column}' "
                f"with '{suggestions[0]}' (case/spelling)."
            )
        else:
            opts = " | ".join(f"'{s}'" for s in suggestions)
            out["fix_hint"] = (
                f"Closest matches: {opts}. Replace '{column}' with one "
                f"of these or pick from available_columns."
            )
    else:
        out["fix_hint"] = (
            f"'{column}' is not present. Pick a column from "
            f"available_columns, or repopulate the dataset to include it."
        )
    return out


def _materialize_datasets(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Build ``{dataset_name: pandas.DataFrame}`` once for diagnostic
    checks. Accepts every dataset shape that ``_normalize_manifest_datasets``
    normalises (DataFrame shorthand, list shorthand, ``{"source": ...}``
    wrapper) so callers can run diagnostics on raw PRISM-style manifests
    without pre-normalising.

    Datasets that fail to materialise (malformed source) yield an empty
    DataFrame; that empty state is flagged via ``chart_dataset_empty``
    only if a chart actually consumes the dataset.

    Pandas emits a noisy ``UserWarning`` when ``pd.to_datetime`` falls
    back to ``dateutil`` on string columns inside _source_to_dataframe.
    Silenced here so a diagnostics-only pass doesn't double-print
    warnings already surfaced during the render pipeline.
    """
    import pandas as pd
    import warnings
    datasets = manifest.get("datasets") or {}
    out: Dict[str, Any] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        for name, entry in datasets.items():
            try:
                if _is_dataframe(entry):
                    out[name] = entry
                elif isinstance(entry, list):
                    out[name] = _source_to_dataframe(entry)
                elif isinstance(entry, dict):
                    src = entry.get("source")
                    if _is_dataframe(src):
                        out[name] = src
                    else:
                        out[name] = _source_to_dataframe(src)
                else:
                    out[name] = pd.DataFrame()
            except (TypeError, ValueError):
                out[name] = pd.DataFrame()
    return out


# Chart types that interpret `value` as a slice / portion. Negative
# values silently render as 0 or as confusing reverse arcs / inverted
# blocks. Whitelisted explicitly so we don't false-positive on
# scatter/bar/line where negative values are legitimate.
_PORTION_CHART_TYPES = {"pie", "donut", "funnel", "sunburst", "treemap"}

# Chart types where a constant numeric y produces a degenerate flat
# line / single-bar-cluster -- worth surfacing because PRISM should
# either pick a different chart_type or apply a transformation.
_SERIES_CHART_TYPES = {"line", "multi_line", "area", "bar",
                         "bar_horizontal", "scatter", "scatter_multi"}


def _check_chart_widget(w: Dict[str, Any], path: str,
                          dfs: Dict[str, Any]) -> List[Diagnostic]:
    """All chart-widget data checks. Idempotent, no side effects."""
    out: List[Diagnostic] = []
    wid = w.get("id")
    spec = w.get("spec") if isinstance(w.get("spec"), dict) else None

    # Inline option / ref widgets bypass the spec pipeline -- their data
    # is already baked into the option JSON, so we can't usefully
    # introspect it from here. We don't emit diagnostics for those.
    if not spec:
        return out

    chart_type = spec.get("chart_type")
    ds_name = spec.get("dataset")
    mapping = spec.get("mapping") or {}

    # Dataset existence / emptiness ------------------------------------
    if ds_name and ds_name in dfs:
        df = dfs[ds_name]
        if df is None or len(df) == 0:
            out.append(Diagnostic(
                severity="error", code="chart_dataset_empty",
                widget_id=wid, path=f"{path}.spec.dataset",
                message=(f"chart '{wid}' references dataset '{ds_name}' "
                         f"which has 0 rows; chart will render blank."),
                context={"dataset": ds_name,
                           "available_datasets": sorted(dfs.keys()),
                           "fix_hint": (
                               "Repopulate the dataset before passing it "
                               "to the manifest -- check upstream loader, "
                               "filters, or join keys returning empty.")}))
            return out  # downstream column checks are noise on empty df
    elif ds_name:
        # Validator already flagged unknown datasets; skip duplicate.
        return out
    else:
        return out

    df = dfs[ds_name]
    available = list(df.columns)

    # Required mapping keys for this chart_type ------------------------
    required = _REQUIRED_MAPPING_KEYS.get(chart_type or "", ())
    for rk in required:
        if rk not in mapping or mapping[rk] in (None, "", [], ()):
            out.append(Diagnostic(
                severity="error", code="chart_mapping_required_missing",
                widget_id=wid, path=f"{path}.spec.mapping.{rk}",
                message=(f"chart_type '{chart_type}' requires "
                         f"mapping.{rk}; not provided."),
                context={"chart_type": chart_type, "missing_key": rk,
                           "required_keys": list(required),
                           "available_columns": available,
                           "fix_hint": (
                               f"Add 'mapping.{rk}' pointing to a column "
                               f"in available_columns. All required keys "
                               f"for chart_type='{chart_type}': "
                               f"{list(required)}.")}))

    # Either-or required-key sets (e.g. treemap/sunburst can be path+value
    # OR name+parent+value).
    any_of = _REQUIRED_MAPPING_KEYS_ANY_OF.get(chart_type or "")
    if any_of:
        def _has(keys):
            return all(
                k in mapping and mapping[k] not in (None, "", [], ())
                for k in keys
            )
        if not any(_has(alt) for alt in any_of):
            alt_repr = " | ".join(
                "{" + ",".join(alt) + "}" for alt in any_of
            )
            out.append(Diagnostic(
                severity="error",
                code="chart_mapping_required_missing",
                widget_id=wid, path=f"{path}.spec.mapping",
                message=(f"chart_type '{chart_type}' requires one of: "
                         + alt_repr + "; none provided."),
                context={"chart_type": chart_type,
                           "required_alternatives": [list(a) for a in any_of],
                           "available_columns": available,
                           "fix_hint": (
                               f"Pick ONE alternative and provide ALL its "
                               f"keys: {alt_repr}. Each key value must be "
                               f"a column in available_columns.")}))

    # Column existence / NaN coverage / numericity ---------------------
    refs = _walk_column_refs(mapping)
    for key, col in refs:
        if col not in df.columns:
            ctx = {"mapping_key": key, "missing_column": col,
                    "dataset": ds_name,
                    "available_columns": available}
            ctx.update(_suggest_for_missing_column(col, available))
            out.append(Diagnostic(
                severity="error", code="chart_mapping_column_missing",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' is not a column in "
                         f"dataset '{ds_name}'."),
                context=ctx))
            continue
        ser = df[col]
        if _all_nan(ser):
            out.append(Diagnostic(
                severity="error", code="chart_mapping_column_all_nan",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' is all-NaN in dataset "
                         f"'{ds_name}'; chart will render blank."),
                context={"mapping_key": key, "column": col,
                           "dataset": ds_name, "row_count": len(df),
                           "fix_hint": (
                               "Repopulate the column upstream. Common "
                               "causes: API returning sentinels instead "
                               "of values, or a join missing rows.")}))
            continue
        nan_frac = _nan_fraction(ser)
        if nan_frac >= 0.5:
            out.append(Diagnostic(
                severity="warning",
                code="chart_mapping_column_mostly_nan",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' is "
                         f"{nan_frac*100:.0f}% NaN in dataset "
                         f"'{ds_name}'; chart may look empty."),
                context={"mapping_key": key, "column": col,
                           "dataset": ds_name,
                           "nan_fraction": round(nan_frac, 3),
                           "row_count": len(df)}))
        if (key in _NUMERIC_COLUMN_REF_KEYS
                and not _series_is_numeric(ser)):
            samples = [str(v) for v in ser.dropna().head(3).tolist()]
            out.append(Diagnostic(
                severity="error",
                code="chart_mapping_column_non_numeric",
                widget_id=wid, path=f"{path}.spec.mapping.{key}",
                message=(f"mapping.{key}='{col}' must be numeric for "
                         f"chart_type '{chart_type}'; column is "
                         f"non-numeric."),
                context={"mapping_key": key, "column": col,
                           "dataset": ds_name,
                           "sample_values": samples,
                           "fix_hint": (
                               f"Coerce '{col}' to numeric upstream "
                               f"(replace sentinels like {samples} with "
                               f"NaN, or remap to a numeric column).")}))

    # Single-row warning (most chart types degenerate at n=1) ----------
    if len(df) == 1 and chart_type in _SERIES_CHART_TYPES:
        out.append(Diagnostic(
            severity="warning", code="chart_dataset_single_row",
            widget_id=wid, path=f"{path}.spec.dataset",
            message=(f"chart '{wid}' has only 1 row in dataset "
                     f"'{ds_name}'; series-style charts need >=2."),
            context={"dataset": ds_name, "row_count": 1,
                       "fix_hint": (
                           "Add more rows to the dataset, or switch to a "
                           "single-value chart_type (kpi, gauge, bullet).")}))

    # Topology + degeneracy checks (run only when columns are present) -
    out.extend(_check_chart_degeneracy(wid, path, df, chart_type,
                                          mapping, ds_name))

    return out


def _check_chart_degeneracy(
    wid: Optional[str], path: str, df, chart_type: Optional[str],
    mapping: Dict[str, Any], ds_name: str,
) -> List[Diagnostic]:
    """Per-chart-type degeneracy checks: data is structurally fine
    (right columns, right types, not-all-NaN) but the *distribution*
    or *topology* makes the chart meaningless.

    Each check is gated on its mapping being valid (column exists,
    numeric where required) so we don't double-flag cases already
    raised upstream. Returns [] if every check passes.
    """
    import pandas as pd
    out: List[Diagnostic] = []
    if df is None or len(df) == 0 or not chart_type:
        return out

    def _col(key: str):
        v = mapping.get(key)
        if isinstance(v, str) and v in df.columns:
            return df[v], v
        return None, None

    # 1. Negative slice values for portion-style charts ----------------
    if chart_type in _PORTION_CHART_TYPES:
        ser, vname = _col("value")
        if ser is not None and _series_is_numeric(ser):
            coerced = pd.to_numeric(ser, errors="coerce")
            neg_mask = coerced < 0
            n_neg = int(neg_mask.sum())
            if n_neg > 0:
                samples = [
                    {"row": int(i), "value": float(coerced.iloc[i])}
                    for i in range(len(coerced))
                    if i < 5 and bool(neg_mask.iloc[i])
                ]
                out.append(Diagnostic(
                    severity="error",
                    code="chart_negative_values_in_portion",
                    widget_id=wid, path=f"{path}.spec.mapping.value",
                    message=(f"chart_type '{chart_type}' value column "
                             f"'{vname}' contains {n_neg} negative "
                             f"value(s); ECharts renders these as 0 or "
                             f"reversed arcs."),
                    context={
                        "chart_type": chart_type,
                        "column": vname, "dataset": ds_name,
                        "negative_count": n_neg, "row_count": len(df),
                        "negative_samples": samples,
                        "fix_hint": (
                            "Drop or absolute-value negative rows "
                            "before charting, or use a chart_type that "
                            "handles signed values (bar, bar_horizontal, "
                            "diverging colour palettes).")}))

    # 2. Constant numeric y for series charts --------------------------
    if chart_type in _SERIES_CHART_TYPES:
        for ykey in ("y",):
            v = mapping.get(ykey)
            cols = [v] if isinstance(v, str) else (
                list(v) if isinstance(v, (list, tuple)) else []
            )
            for ycol in cols:
                if not isinstance(ycol, str) or ycol not in df.columns:
                    continue
                ser = df[ycol]
                if not _series_is_numeric(ser):
                    continue
                coerced = pd.to_numeric(ser, errors="coerce").dropna()
                if len(coerced) < 2:
                    continue
                if coerced.nunique() == 1:
                    out.append(Diagnostic(
                        severity="warning",
                        code="chart_constant_values",
                        widget_id=wid,
                        path=f"{path}.spec.mapping.{ykey}",
                        message=(f"mapping.{ykey} column '{ycol}' has "
                                 f"a single unique value "
                                 f"({coerced.iloc[0]}) across "
                                 f"{len(coerced)} rows; chart will "
                                 f"render as a flat line."),
                        context={
                            "chart_type": chart_type, "column": ycol,
                            "dataset": ds_name,
                            "constant_value": float(coerced.iloc[0]),
                            "row_count": int(len(coerced)),
                            "fix_hint": (
                                "Pick a y column with variance, or "
                                "switch to a single-value chart_type "
                                "(kpi, gauge).")}))

    # 3. Sankey topology -- self-loops + disconnected ------------------
    if chart_type == "sankey":
        s_ser, sname = _col("source")
        t_ser, tname = _col("target")
        if s_ser is not None and t_ser is not None:
            n = len(df)
            self_loop_mask = (s_ser == t_ser)
            n_self = int(self_loop_mask.sum())
            if n_self > 0:
                pct = (n_self / n * 100) if n > 0 else 0.0
                samples = [
                    {"source": str(s_ser.iloc[i]),
                      "target": str(t_ser.iloc[i])}
                    for i in range(min(n, 5))
                    if bool(self_loop_mask.iloc[i])
                ]
                out.append(Diagnostic(
                    severity="error" if n_self == n else "warning",
                    code="chart_sankey_self_loops",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"sankey '{wid}' has {n_self}/{n} "
                             f"({pct:.0f}%) self-loop edges where "
                             f"source==target; sankey renders these as "
                             f"disconnected stubs."),
                    context={
                        "self_loop_count": n_self, "row_count": n,
                        "self_loop_pct": round(pct, 1),
                        "source_column": sname, "target_column": tname,
                        "samples": samples,
                        "fix_hint": (
                            "Filter rows where source!=target before "
                            "passing to the manifest, or model the data "
                            "as a graph (chart_type='graph').")}))
            sources = set(s_ser.dropna().astype(str).unique().tolist())
            targets = set(t_ser.dropna().astype(str).unique().tolist())
            if sources and targets and not (sources & targets):
                out.append(Diagnostic(
                    severity="warning",
                    code="chart_sankey_disconnected",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"sankey '{wid}' source/target sets share "
                             f"no nodes; the diagram is one bipartite "
                             f"step with no chained flow."),
                    context={
                        "source_unique": sorted(list(sources))[:8],
                        "target_unique": sorted(list(targets))[:8],
                        "fix_hint": (
                            "If you want a multi-step flow, the same "
                            "node names must appear on BOTH sides (a "
                            "target of step N becomes a source of step "
                            "N+1). For a one-step flow, this is fine -- "
                            "ignore the warning.")}))

    # 4. Candlestick OHLC inversion ------------------------------------
    if chart_type == "candlestick":
        o, _ = _col("open")
        h, _ = _col("high")
        l_ser, _ = _col("low")
        c, _ = _col("close")
        if all(s is not None for s in (o, h, l_ser, c)):
            o_n = pd.to_numeric(o, errors="coerce")
            h_n = pd.to_numeric(h, errors="coerce")
            l_n = pd.to_numeric(l_ser, errors="coerce")
            c_n = pd.to_numeric(c, errors="coerce")
            inv_hl = int((h_n < l_n).sum())
            inv_oh = int((o_n > h_n).sum())
            inv_ol = int((o_n < l_n).sum())
            inv_ch = int((c_n > h_n).sum())
            inv_cl = int((c_n < l_n).sum())
            problems = {"high<low": inv_hl, "open>high": inv_oh,
                          "open<low": inv_ol, "close>high": inv_ch,
                          "close<low": inv_cl}
            problems = {k: v for k, v in problems.items() if v > 0}
            if problems:
                out.append(Diagnostic(
                    severity="error",
                    code="chart_candlestick_inverted",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"candlestick '{wid}' has OHLC "
                             f"inversions: {problems}; ECharts will "
                             f"draw nonsense candles."),
                    context={
                        "row_count": len(df),
                        "inversions": problems,
                        "fix_hint": (
                            "Verify the open/high/low/close column "
                            "assignments; the most common cause is a "
                            "swap between mapping.high and mapping.low.")}))

    # 5. Tree orphan parents -------------------------------------------
    if chart_type == "tree":
        n_ser, nname = _col("name")
        p_ser, pname = _col("parent")
        if n_ser is not None and p_ser is not None:
            names_set = set(n_ser.dropna().astype(str).tolist())
            orphans: List[Tuple[int, str, str]] = []
            for i in range(len(p_ser)):
                p = p_ser.iloc[i]
                if p is None or (isinstance(p, float) and pd.isna(p)):
                    continue
                p_str = str(p)
                if p_str not in names_set:
                    orphans.append((i, str(n_ser.iloc[i]), p_str))
            if orphans:
                out.append(Diagnostic(
                    severity="error",
                    code="chart_tree_orphan_parents",
                    widget_id=wid, path=f"{path}.spec.mapping",
                    message=(f"tree '{wid}' has {len(orphans)} row(s) "
                             f"whose parent doesn't exist as a name; "
                             f"those nodes won't render."),
                    context={
                        "orphan_count": len(orphans),
                        "orphan_samples": [
                            {"row": r, "name": n, "parent": p}
                            for r, n, p in orphans[:5]
                        ],
                        "name_column": nname,
                        "parent_column": pname,
                        "fix_hint": (
                            "Every parent value must match a 'name' "
                            "value in the same dataset (the root row "
                            "uses null/None for its parent).")}))

    return out


def _check_table_widget(w: Dict[str, Any], path: str,
                          dfs: Dict[str, Any]) -> List[Diagnostic]:
    """Per-column field-existence + the all-columns-missing roll-up.

    When EVERY defined column is missing, the table will render a header
    row with empty cells -- worse than just one bad column. Flagged as
    a single `table_columns_all_missing` error so PRISM gets one
    actionable diagnostic instead of N near-identical ones.
    """
    out: List[Diagnostic] = []
    wid = w.get("id")
    ds_name = w.get("dataset_ref")
    if not ds_name or ds_name not in dfs:
        return out
    df = dfs[ds_name]
    if df is None or len(df) == 0:
        out.append(Diagnostic(
            severity="warning", code="table_dataset_empty",
            widget_id=wid, path=f"{path}.dataset_ref",
            message=(f"table '{wid}' references dataset '{ds_name}' "
                     f"which has 0 rows; table will render empty."),
            context={"dataset": ds_name,
                       "fix_hint": (
                           "Repopulate the dataset upstream, or filter "
                           "less aggressively before passing it to the "
                           "manifest.")}))
        return out

    cols = w.get("columns") or []
    if not isinstance(cols, list):
        return out
    available = list(df.columns)
    field_cols = [
        (ci, c.get("field"))
        for ci, c in enumerate(cols)
        if isinstance(c, dict) and c.get("field")
    ]
    missing_cols = [
        (ci, fld) for ci, fld in field_cols if fld not in df.columns
    ]
    # Aggregate roll-up first so it appears before the per-column noise
    if field_cols and len(missing_cols) == len(field_cols):
        out.append(Diagnostic(
            severity="error", code="table_columns_all_missing",
            widget_id=wid, path=f"{path}.columns",
            message=(f"table '{wid}' has {len(missing_cols)} defined "
                     f"columns and ALL of them are missing from dataset "
                     f"'{ds_name}'; the table will render an empty "
                     f"header row only."),
            context={
                "missing_columns": [fld for _, fld in missing_cols],
                "dataset": ds_name,
                "available_columns": available,
                "fix_hint": (
                    "Either redefine 'columns' to fields actually in "
                    "the dataset, or change 'dataset_ref' to a dataset "
                    "that has these columns.")}))
    for ci, fld in missing_cols:
        ctx = {"missing_column": fld, "dataset": ds_name,
                "available_columns": available}
        ctx.update(_suggest_for_missing_column(fld, available))
        out.append(Diagnostic(
            severity="error", code="table_column_field_missing",
            widget_id=wid, path=f"{path}.columns[{ci}].field",
            message=(f"table '{wid}' columns[{ci}].field='{fld}' is "
                     f"not a column in dataset '{ds_name}'."),
            context=ctx))
    return out


def _check_kpi_widget(w: Dict[str, Any], path: str,
                        dfs: Dict[str, Any]) -> List[Diagnostic]:
    """KPI source-binding diagnostics. Three sources can be set:
    `source` (the value), `delta_source` (the change indicator), and
    `sparkline_source` (the inline mini-line). Each is checked
    independently; sparkline gets an additional length check because a
    sparkline with <2 points is not a line at all.
    """
    import pandas as pd
    out: List[Diagnostic] = []
    wid = w.get("id")
    sources = [
        ("source", w.get("source")),
        ("delta_source", w.get("delta_source")),
        ("sparkline_source", w.get("sparkline_source")),
    ]
    for key, src in sources:
        if not src or not isinstance(src, str):
            continue
        # Source format is "dataset.column" or "dataset.column.aggregator"
        parts = src.split(".")
        if len(parts) < 2:
            out.append(Diagnostic(
                severity="error", code="kpi_source_malformed",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}='{src}' must be "
                         f"'dataset.column' or 'dataset.column.agg'."),
                context={key: src,
                           "fix_hint": (
                               f"Use the form 'dataset.column' (or "
                               f"'dataset.column.aggregator' where "
                               f"aggregator in last/first/min/max/mean/"
                               f"sum). Got '{src}'.")}))
            continue
        ds_name = parts[0]
        col_name = parts[1]
        if ds_name not in dfs:
            ds_suggestions = _did_you_mean(ds_name, sorted(dfs.keys()))
            ctx: Dict[str, Any] = {
                key: src, "dataset": ds_name,
                "available_datasets": sorted(dfs.keys()),
            }
            if ds_suggestions:
                ctx["did_you_mean"] = ds_suggestions
                ctx["fix_hint"] = (
                    f"Did you mean dataset '{ds_suggestions[0]}'? "
                    f"Replace '{ds_name}.' prefix or pick from "
                    f"available_datasets.")
            else:
                ctx["fix_hint"] = (
                    f"Declare dataset '{ds_name}' in manifest.datasets, "
                    f"or pick from available_datasets.")
            out.append(Diagnostic(
                severity="error", code="kpi_source_dataset_unknown",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}='{src}' references "
                         f"unknown dataset '{ds_name}'."),
                context=ctx))
            continue
        df = dfs[ds_name]
        if col_name not in df.columns:
            ctx = {key: src, "dataset": ds_name,
                    "missing_column": col_name,
                    "available_columns": list(df.columns)}
            ctx.update(_suggest_for_missing_column(
                col_name, list(df.columns)))
            out.append(Diagnostic(
                severity="error", code="kpi_source_column_missing",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}='{src}' references "
                         f"column '{col_name}' which is not in "
                         f"dataset '{ds_name}'."),
                context=ctx))
            continue
        if _all_nan(df[col_name]):
            out.append(Diagnostic(
                severity="warning", code="kpi_source_column_all_nan",
                widget_id=wid, path=f"{path}.{key}",
                message=(f"kpi '{wid}' {key}='{src}' column "
                         f"'{col_name}' is all-NaN; the tile will "
                         f"display '--'."),
                context={key: src, "dataset": ds_name,
                           "column": col_name,
                           "fix_hint": (
                               "Repopulate the column upstream, or "
                               "point this source at a different "
                               "column with data.")}))
            continue
        # Sparkline-specific: a 'line' of <2 points isn't a line.
        if key == "sparkline_source":
            n_valid = int(pd.to_numeric(
                df[col_name], errors="coerce"
            ).notna().sum())
            if n_valid < 2:
                out.append(Diagnostic(
                    severity="warning",
                    code="kpi_sparkline_too_short",
                    widget_id=wid, path=f"{path}.{key}",
                    message=(f"kpi '{wid}' sparkline_source='{src}' "
                             f"has only {n_valid} numeric value(s); "
                             f"the sparkline will be empty or a dot."),
                    context={key: src, "dataset": ds_name,
                               "column": col_name,
                               "valid_value_count": n_valid,
                               "row_count": len(df),
                               "fix_hint": (
                                   "Sparklines need >=2 points. Either "
                                   "drop sparkline_source on this KPI or "
                                   "point at a column with more "
                                   "history.")}))
    return out


def _check_filter(f: Dict[str, Any], idx: int, manifest: Dict[str, Any],
                    dfs: Dict[str, Any]) -> List[Diagnostic]:
    """Filter-level diagnostics. Three failure modes:

      1. ``filter_field_missing_in_target`` - filter.field is not a
         column in any of the target widgets' datasets.
      2. ``filter_default_not_in_options`` - filter.default is not in
         filter.options for select/multiSelect/radio types.
      3. ``filter_targets_no_match`` - none of the filter.targets
         patterns matches a real widget id.
    """
    out: List[Diagnostic] = []
    fid = f.get("id")
    fld = f.get("field")
    targets = f.get("targets") or []
    layout = manifest.get("layout") or {}

    # Build the universe of widget ids in the manifest so we can flag
    # filter targets that resolve to nothing.
    widget_ids: List[str] = []

    def _gather_ids(rows):
        for row in rows or []:
            for w in row:
                if isinstance(w, dict) and isinstance(w.get("id"), str):
                    widget_ids.append(w["id"])

    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            _gather_ids(tab.get("rows", []))
    else:
        _gather_ids(layout.get("rows", []))

    # 1. Default not in options for select-style filters
    ftype = f.get("type")
    default = f.get("default")
    options = f.get("options")
    if ftype in ("select", "multiSelect", "radio") and isinstance(
        options, list
    ):
        flat_opts: List[Any] = []
        for o in options:
            if isinstance(o, dict):
                if "value" in o:
                    flat_opts.append(o["value"])
            else:
                flat_opts.append(o)
        if default is not None:
            defaults = (default if (ftype == "multiSelect" and
                                       isinstance(default, list))
                         else [default])
            missing = [d for d in defaults if d not in flat_opts]
            if missing:
                out.append(Diagnostic(
                    severity="warning",
                    code="filter_default_not_in_options",
                    widget_id=fid,
                    path=f"filters[{idx}].default",
                    message=(f"filter '{fid}' default={default!r} is not "
                             f"in options; UI will reset to first "
                             f"option or render unselected."),
                    context={"default": default, "options": flat_opts,
                               "missing": missing,
                               "fix_hint": (
                                   f"Set 'default' to one of "
                                   f"{flat_opts}, or add the missing "
                                   f"value(s) {missing} to "
                                   f"'options'.")}))

    # 2. Targets resolve to nothing
    def _matches(wid: str, pat: str) -> bool:
        if pat == "*":
            return True
        if "*" in pat:
            if pat.endswith("*"):
                return wid.startswith(pat[:-1])
            if pat.startswith("*"):
                return wid.endswith(pat[1:])
        return wid == pat

    if targets:
        unmatched = [
            t for t in targets
            if t != "*" and not any(_matches(w, t) for w in widget_ids)
        ]
        if unmatched and len(unmatched) == len(
            [t for t in targets if t != "*"]
        ):
            # Every non-wildcard target was unmatched -> filter is dead.
            out.append(Diagnostic(
                severity="warning",
                code="filter_targets_no_match",
                widget_id=fid,
                path=f"filters[{idx}].targets",
                message=(f"filter '{fid}' targets={targets!r} match no "
                         f"widget ids; the filter will be a no-op."),
                context={"targets": targets,
                           "available_widget_ids": sorted(set(widget_ids)),
                           "fix_hint": (
                               "Replace targets with widget ids that "
                               "exist (or '*' for all). Patterns like "
                               "'foo*' / '*bar' are supported.")}))

    # 3. Field doesn't exist in target dataset
    if not fld or not targets:
        return out

    # Resolve target widget ids -> their dataset_ref / spec.dataset
    target_datasets: set = set()

    def _visit(rows):
        for row in rows or []:
            for w in row:
                if not isinstance(w, dict):
                    continue
                wid = w.get("id")
                if not isinstance(wid, str):
                    continue
                if not any(_matches(wid, t) for t in targets):
                    continue
                ds = w.get("dataset_ref")
                if not ds and isinstance(w.get("spec"), dict):
                    ds = w["spec"].get("dataset")
                if ds:
                    target_datasets.add(ds)

    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            _visit(tab.get("rows", []))
    else:
        _visit(layout.get("rows", []))

    for ds in target_datasets:
        df = dfs.get(ds)
        if df is None:
            continue
        if fld not in df.columns:
            ctx = {"field": fld, "dataset": ds,
                    "available_columns": list(df.columns)}
            ctx.update(_suggest_for_missing_column(fld, list(df.columns)))
            out.append(Diagnostic(
                severity="error",
                code="filter_field_missing_in_target",
                widget_id=fid,
                path=f"filters[{idx}].field",
                message=(f"filter '{fid}' field='{fld}' is not "
                         f"a column in target dataset '{ds}'; the "
                         f"filter will silently filter nothing."),
                context=ctx))
    return out


# -----------------------------------------------------------------------------
# DATA SHAPE DIAGNOSTICS
#
# Shape problems are visible only on the original DataFrame -- once
# _normalize_manifest_datasets() converts datasets to list-of-lists,
# the index, dtype, and df.attrs metadata are gone. So we snapshot
# the relevant shape attributes BEFORE normalize and feed the snapshot
# into chart_data_diagnostics() so it can emit precise "you forgot
# reset_index() on dataset X" / "dataset Y was a tuple" messages.
#
# The compiler does NOT auto-fix any of these; it names them clearly
# so PRISM can fix the producer in one round-trip.
# -----------------------------------------------------------------------------

# Patterns for column names that look like raw API codes. When such a
# column is referenced by a chart/table/kpi the compiler emits a
# warning suggesting humanisation -- the legend / tooltip / table
# header reads the column name verbatim.
_OPAQUE_CODE_PATTERNS = (
    re.compile(r"^[A-Z][A-Z0-9_]*@[A-Z][A-Z0-9_]*$"),   # GDP@USECON (Haver)
    re.compile(r"^IR_[A-Z]{3}_"),                        # IR_USD_Treasury_10Y_Rate
    re.compile(r"^FX_[A-Z]{3}_"),
    re.compile(r"^EQ_[A-Z]{3}_"),
    re.compile(r"^CR_[A-Z]{3}_"),
    re.compile(r"\s"),                                    # whitespace in name
    re.compile(r"[/%]"),                                  # path-y / unit-y chars
)


def _looks_like_opaque_code(name: str) -> bool:
    """True iff column name matches one of the known opaque-code patterns.

    Conservative: a snake_case ASCII name like 'core_cpi' or 'us_10y'
    never trips. A code like 'JCXFE@USECON' or 'IR_USD_Swap_10Y' does.
    Used to surface humanisation suggestions, not to block compile.
    """
    if not isinstance(name, str) or not name:
        return False
    for pat in _OPAQUE_CODE_PATTERNS:
        if pat.search(name):
            return True
    return False


def _capture_shape_info(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Snapshot DataFrame shape attributes BEFORE normalize destroys them.

    Returns ``{dataset_name: shape_info}`` where shape_info captures only
    what the shape diagnostics need (kind, DTI flag, index name, columns,
    MultiIndex flag, attrs metadata). Datasets that are already in list-
    of-lists form yield ``{kind: 'list'}`` and trip none of the shape
    checks.

    Safe to call on any manifest -- non-dict input returns ``{}``.
    """
    info: Dict[str, Dict[str, Any]] = {}
    if not isinstance(manifest, dict):
        return info
    datasets = manifest.get("datasets") or {}
    if not isinstance(datasets, dict):
        return info
    try:
        import pandas as pd
    except ImportError:
        return info
    for name, entry in datasets.items():
        if isinstance(entry, tuple):
            info[name] = {"kind": "tuple", "tuple_len": len(entry)}
            continue
        df = None
        if isinstance(entry, pd.DataFrame):
            df = entry
        elif isinstance(entry, dict):
            src = entry.get("source")
            if isinstance(src, tuple):
                info[name] = {"kind": "tuple", "tuple_len": len(src)}
                continue
            if isinstance(src, pd.DataFrame):
                df = src
        if df is None:
            info[name] = {"kind": "list"}
            continue
        info[name] = {
            "kind": "dataframe",
            "has_dti": isinstance(df.index, pd.DatetimeIndex),
            "index_name": df.index.name,
            "columns": list(df.columns),
            "multiindex_columns": isinstance(df.columns, pd.MultiIndex),
            "attrs_metadata": df.attrs.get("metadata"),
        }
    return info


def _columns_referenced_by_widgets(
    manifest: Dict[str, Any], ds_name: str,
) -> List[str]:
    """Collect every column name referenced by chart mappings, table
    column fields, KPI sources, and filter fields targeting the given
    dataset. Used to gate "looks like an opaque code" warnings to
    columns the dashboard actually consumes -- raw codes nobody plots
    aren't worth flagging.
    """
    refs: List[str] = []

    def _visit_rows(rows):
        for row in rows or []:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                wt = w.get("widget")
                if wt == "chart":
                    spec = w.get("spec")
                    if not isinstance(spec, dict):
                        continue
                    if spec.get("dataset") != ds_name:
                        continue
                    for _k, c in _walk_column_refs(spec.get("mapping") or {}):
                        refs.append(c)
                elif wt == "table":
                    if w.get("dataset_ref") != ds_name:
                        continue
                    for c in (w.get("columns") or []):
                        if isinstance(c, dict) and c.get("field"):
                            refs.append(c["field"])
                elif wt == "kpi":
                    for src_key in ("source", "delta_source",
                                       "sparkline_source"):
                        s = w.get(src_key)
                        if not isinstance(s, str) or "." not in s:
                            continue
                        parts = s.split(".")
                        if parts[0] != ds_name:
                            continue
                        # source/delta_source are <ds>.<agg>.<col>
                        # sparkline_source is <ds>.<col>
                        if src_key == "sparkline_source" and len(parts) >= 2:
                            refs.append(parts[1])
                        elif len(parts) >= 3:
                            refs.append(parts[2])

    layout = manifest.get("layout") or {}
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            if isinstance(tab, dict):
                _visit_rows(tab.get("rows", []))
    else:
        _visit_rows(layout.get("rows", []))
    return list(set(refs))


def _check_dataset_shape(
    manifest: Dict[str, Any],
    shape_info: Dict[str, Dict[str, Any]],
) -> List[Diagnostic]:
    """Emit shape-mistake diagnostics from the pre-normalize snapshot.

    Catches the four most common "PRISM passed un-cleaned data" mistakes:
    tuple instead of DataFrame, MultiIndex columns, DatetimeIndex with
    no 'date' column, opaque codes used as column names. Each diagnostic
    carries a ``fix_hint`` with the literal pandas snippet to apply.
    """
    out: List[Diagnostic] = []
    for name, info in shape_info.items():
        kind = info.get("kind")
        if kind == "tuple":
            out.append(Diagnostic(
                severity="error", code="dataset_passed_as_tuple",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' is a tuple (likely the "
                         f"unpacked return of pull_market_data, which "
                         f"yields (eod_df, intraday_df)). The compiler "
                         f"requires a single DataFrame."),
                context={"dataset": name,
                           "tuple_len": info.get("tuple_len"),
                           "fix_hint": (
                               f"Unpack first, then pick the relevant "
                               f"DataFrame: eod_df, _ = "
                               f"pull_market_data(...); "
                               f"datasets={{'{name}': eod_df}}.")}))
            continue
        if kind != "dataframe":
            continue
        if info.get("multiindex_columns"):
            out.append(Diagnostic(
                severity="error", code="dataset_columns_multiindex",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' columns is a pandas MultiIndex; "
                         f"the compiler does not auto-flatten it."),
                context={"dataset": name,
                           "columns": [list(c) if isinstance(c, tuple) else c
                                          for c in info.get("columns") or []],
                           "fix_hint": (
                               "Flatten before passing: "
                               "df.columns = ['_'.join(str(x) for x in c) "
                               "for c in df.columns]")}))
            continue
        # DatetimeIndex with no 'date' column AND a chart that wants 'date'.
        if info.get("has_dti"):
            cols = info.get("columns") or []
            if "date" not in cols and _any_widget_uses_date(manifest, name):
                idx_name = info.get("index_name") or "(unnamed)"
                out.append(Diagnostic(
                    severity="error", code="dataset_dti_no_date_column",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' has a DatetimeIndex "
                             f"(name='{idx_name}') but no 'date' column. "
                             f"The compiler does not auto-reset_index(); "
                             f"a chart/filter on this dataset references "
                             f"'date' and will fail to bind."),
                    context={"dataset": name,
                               "index_name": idx_name,
                               "available_columns": cols,
                               "fix_hint": (
                                   f"Reset before passing: "
                                   f"df = df.reset_index()"
                                   + (f"  # 'date' column appears"
                                      if idx_name == "date" else
                                      "; then rename the index column "
                                      "to 'date' if needed"))}))
        # Opaque-code column names referenced by widgets.
        refs = set(_columns_referenced_by_widgets(manifest, name))
        for col in info.get("columns") or []:
            if not isinstance(col, str):
                continue
            if col not in refs:
                continue
            if not _looks_like_opaque_code(col):
                continue
            out.append(Diagnostic(
                severity="warning",
                code="dataset_column_looks_like_code",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' column '{col}' looks like a "
                         f"raw API code (Haver / coordinate / expression). "
                         f"It will appear verbatim in legends, tooltips, "
                         f"and table headers."),
                context={"dataset": name, "column": col,
                           "fix_hint": (
                               f"Rename to plain English before passing: "
                               f"df = df.rename(columns={{'{col}': "
                               f"'<plain_english_name>'}}). "
                               f"df.attrs['metadata'] usually carries a "
                               f"display_name for each pulled series.")}))
        # Pull-time metadata available but columns still match raw codes.
        meta = info.get("attrs_metadata")
        if isinstance(meta, list) and meta:
            cols_set = set(info.get("columns") or [])
            meta_keys = set()
            for m in meta:
                if not isinstance(m, dict):
                    continue
                for k in ("coordinate", "code", "expression"):
                    v = m.get(k)
                    if isinstance(v, str):
                        meta_keys.add(v)
            overlap = cols_set & meta_keys
            if overlap:
                out.append(Diagnostic(
                    severity="info",
                    code="dataset_metadata_attrs_unused",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' carries pull-time metadata "
                             f"in df.attrs['metadata'] but columns still "
                             f"use raw codes ({sorted(overlap)[:3]}...). "
                             f"Consider mapping coordinate -> plain "
                             f"English before passing."),
                    context={"dataset": name,
                               "raw_columns_in_metadata": sorted(overlap),
                               "fix_hint": (
                                   "rename = {m['coordinate']: "
                                   "<plain_english> for m in "
                                   "df.attrs['metadata']}; "
                                   "df = df.rename(columns=rename)")}))
    return out


def _any_widget_uses_date(manifest: Dict[str, Any], ds_name: str) -> bool:
    """True iff some widget in manifest references column 'date' on
    the named dataset (chart mapping, filter field, kpi source). Used
    to gate the dataset_dti_no_date_column diagnostic so we only fire
    it when the dashboard actually expects a date column.
    """
    def _visit(rows):
        for row in rows or []:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                if w.get("widget") == "chart":
                    spec = w.get("spec")
                    if isinstance(spec, dict) and spec.get("dataset") == ds_name:
                        for _k, c in _walk_column_refs(
                            spec.get("mapping") or {}
                        ):
                            if c == "date":
                                return True
                if w.get("widget") in ("table", "kpi"):
                    if w.get("dataset_ref") == ds_name:
                        # tables / kpis don't usually use 'date' directly,
                        # but a date column is implied for time-series
                        # contexts; safe to skip here.
                        pass
        return False

    layout = manifest.get("layout") or {}
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            if isinstance(tab, dict) and _visit(tab.get("rows", [])):
                return True
    else:
        if _visit(layout.get("rows", [])):
            return True
    # Filters can also imply a date column.
    for f in manifest.get("filters") or []:
        if not isinstance(f, dict):
            continue
        if f.get("type") == "dateRange" or f.get("field") == "date":
            # Check whether this filter targets the dataset.
            for t in f.get("targets") or []:
                # If target is '*' or a widget on this dataset, count it.
                if t == "*":
                    return True
                # Target is a widget id; we'd need the widget->dataset
                # map. Conservative: treat as "may target ds_name".
                return True
    return False


# -----------------------------------------------------------------------------
# DATA SIZE DIAGNOSTICS
#
# Run after normalize so we measure the actual list-of-lists payload,
# which is what the HTML embeds. Both row-count and serialised-byte
# limits fire so the failure mode is clearly named -- "this dataset
# has too many rows" reads differently from "this dataset is too
# heavy" (row counts are bounded but each row is a 200-char dict).
# -----------------------------------------------------------------------------

def _serialised_bytes(source: Any) -> int:
    """Length of ``json.dumps(source, default=str)`` in bytes. Mirrors
    the actual cost of embedding the dataset in the HTML payload.
    Returns 0 on non-serialisable input so a corrupted dataset doesn't
    blow up the size check.
    """
    try:
        return len(json.dumps(source, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return 0


def _row_count(source: Any) -> int:
    """Row count for a normalised list-of-lists source: len-1 because
    row 0 is the header. Returns 0 for malformed input.
    """
    if not isinstance(source, list) or not source:
        return 0
    return max(0, len(source) - 1)


def _check_dataset_size(
    manifest: Dict[str, Any],
    table_dataset_refs: set,
) -> List[Diagnostic]:
    """Emit size-budget diagnostics for every dataset in the manifest
    plus a manifest-level total. ``table_dataset_refs`` is the set of
    dataset names consumed by table widgets (used to apply the stricter
    table-rows thresholds).

    Pre-condition: manifest.datasets are normalised to list-of-lists.
    """
    out: List[Diagnostic] = []
    datasets = manifest.get("datasets") or {}
    if not isinstance(datasets, dict):
        return out

    total_bytes = 0
    for name, entry in datasets.items():
        source = entry.get("source") if isinstance(entry, dict) else entry
        rows = _row_count(source)
        sbytes = _serialised_bytes(source)
        total_bytes += sbytes

        if rows >= DATASET_ROWS_ERROR:
            out.append(Diagnostic(
                severity="error", code="dataset_rows_error",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' has {rows:,} rows "
                         f"(>= {DATASET_ROWS_ERROR:,}); embedding this "
                         f"in the dashboard HTML produces multi-MB "
                         f"payloads and slow first-render."),
                context={"dataset": name, "row_count": rows,
                           "threshold": DATASET_ROWS_ERROR,
                           "fix_hint": (
                               "Top-N filter at pull time (only the rows "
                               "the dashboard actually needs), reduce the "
                               "history window, or move the data behind "
                               "an API endpoint and lazy-load. See "
                               "DATA_SHAPES.md 'Data budget limits'.")}))
        elif rows >= DATASET_ROWS_WARN:
            out.append(Diagnostic(
                severity="warning", code="dataset_rows_warning",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' has {rows:,} rows "
                         f"(>= {DATASET_ROWS_WARN:,}); consider whether "
                         f"this much history is necessary."),
                context={"dataset": name, "row_count": rows,
                           "threshold": DATASET_ROWS_WARN,
                           "fix_hint": (
                               "Daily 10y is ~2,500 rows. Datasets above "
                               "10K usually mean the lookback is too long "
                               "or the universe wasn't filtered.")}))

        if sbytes >= DATASET_BYTES_ERROR:
            out.append(Diagnostic(
                severity="error", code="dataset_bytes_error",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' serialises to "
                         f"{sbytes:,} bytes "
                         f"(>= {DATASET_BYTES_ERROR:,}); the HTML "
                         f"payload will be sluggish to load."),
                context={"dataset": name, "bytes": sbytes,
                           "threshold": DATASET_BYTES_ERROR,
                           "fix_hint": (
                               "Drop columns that no widget reads, "
                               "shorten the history window, or split "
                               "into multiple smaller datasets keyed by "
                               "primary entity.")}))
        elif sbytes >= DATASET_BYTES_WARN:
            out.append(Diagnostic(
                severity="warning", code="dataset_bytes_warning",
                widget_id=None, path=f"datasets.{name}",
                message=(f"dataset '{name}' serialises to "
                         f"{sbytes:,} bytes "
                         f"(>= {DATASET_BYTES_WARN:,})."),
                context={"dataset": name, "bytes": sbytes,
                           "threshold": DATASET_BYTES_WARN}))

        # Stricter row caps for tables (the table widget renders every
        # row to the DOM regardless of max_rows).
        if name in table_dataset_refs:
            if rows >= TABLE_ROWS_ERROR:
                out.append(Diagnostic(
                    severity="error", code="table_rows_error",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' (consumed by a table "
                             f"widget) has {rows:,} rows "
                             f"(>= {TABLE_ROWS_ERROR:,}); the table "
                             f"will be unusable to scroll."),
                    context={"dataset": name, "row_count": rows,
                               "threshold": TABLE_ROWS_ERROR,
                               "fix_hint": (
                                   "Filter / aggregate the table dataset "
                                   "to a screened subset before passing. "
                                   "max_rows on the table widget only "
                                   "limits the visible viewport, not "
                                   "the embedded row count.")}))
            elif rows >= TABLE_ROWS_WARN:
                out.append(Diagnostic(
                    severity="warning", code="table_rows_warning",
                    widget_id=None, path=f"datasets.{name}",
                    message=(f"dataset '{name}' (consumed by a table "
                             f"widget) has {rows:,} rows "
                             f"(>= {TABLE_ROWS_WARN:,})."),
                    context={"dataset": name, "row_count": rows,
                               "threshold": TABLE_ROWS_WARN}))

    if total_bytes >= MANIFEST_BYTES_ERROR:
        out.append(Diagnostic(
            severity="error", code="manifest_bytes_error",
            widget_id=None, path="datasets",
            message=(f"manifest datasets total {total_bytes:,} bytes "
                     f"(>= {MANIFEST_BYTES_ERROR:,}); the compiled HTML "
                     f"will exceed practical browser-load thresholds."),
            context={"total_bytes": total_bytes,
                       "threshold": MANIFEST_BYTES_ERROR,
                       "fix_hint": (
                           "Trim the largest dataset (see per-dataset "
                           "diagnostics) or split this dashboard into "
                           "two narrower ones.")}))
    elif total_bytes >= MANIFEST_BYTES_WARN:
        out.append(Diagnostic(
            severity="warning", code="manifest_bytes_warning",
            widget_id=None, path="datasets",
            message=(f"manifest datasets total {total_bytes:,} bytes "
                     f"(>= {MANIFEST_BYTES_WARN:,})."),
            context={"total_bytes": total_bytes,
                       "threshold": MANIFEST_BYTES_WARN}))

    return out


def _table_dataset_refs(manifest: Dict[str, Any]) -> set:
    """Set of dataset names consumed by any table widget. Used by
    _check_dataset_size to apply the stricter table-rows thresholds.
    """
    refs: set = set()

    def _visit(rows):
        for row in rows or []:
            if not isinstance(row, list):
                continue
            for w in row:
                if not isinstance(w, dict):
                    continue
                if w.get("widget") != "table":
                    continue
                ds = w.get("dataset_ref")
                if isinstance(ds, str):
                    refs.add(ds)

    layout = manifest.get("layout") or {}
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            if isinstance(tab, dict):
                _visit(tab.get("rows", []))
    else:
        _visit(layout.get("rows", []))
    return refs


def chart_data_diagnostics(
    manifest: Dict[str, Any],
) -> List[Diagnostic]:
    """Inspect every chart/table/kpi/filter binding in ``manifest`` and
    return a list of :class:`Diagnostic` entries for empty datasets,
    missing columns, all-NaN series, missing required mapping keys,
    non-numeric value columns, filter-field/target mismatches, and
    dataset / manifest size budget violations.

    Shape diagnostics (DatetimeIndex with no 'date' column, MultiIndex
    columns, opaque-code names, tuple-instead-of-DataFrame, attrs
    metadata unused) require a snapshot of the original DataFrame
    shapes taken BEFORE :func:`_normalize_manifest_datasets` ran;
    :func:`compile_dashboard` and :func:`render_dashboard` capture
    that snapshot via :func:`_capture_shape_info` and call
    :func:`_check_dataset_shape` separately, so this function only
    needs to handle the post-normalize binding + size checks.

    Pure function: no side effects, no IO, manifest is not mutated.
    Safe to call at any time on any manifest (validator-checked or not).
    Returns an empty list when no problems are detected.
    """
    diags: List[Diagnostic] = []
    if not isinstance(manifest, dict):
        return diags

    dfs = _materialize_datasets(manifest)
    layout = manifest.get("layout") or {}

    def _walk(rows, path_prefix: str) -> None:
        for ri, row in enumerate(rows or []):
            if not isinstance(row, list):
                continue
            for wi, w in enumerate(row):
                if not isinstance(w, dict):
                    continue
                wpath = f"{path_prefix}[{ri}][{wi}]"
                wt = w.get("widget")
                if wt == "chart":
                    diags.extend(_check_chart_widget(w, wpath, dfs))
                elif wt == "table":
                    diags.extend(_check_table_widget(w, wpath, dfs))
                elif wt == "kpi":
                    diags.extend(_check_kpi_widget(w, wpath, dfs))

    if layout.get("kind") == "tabs":
        for ti, tab in enumerate(layout.get("tabs", []) or []):
            if isinstance(tab, dict):
                _walk(tab.get("rows", []),
                      f"layout.tabs[{ti}].rows")
    else:
        _walk(layout.get("rows", []), "layout.rows")

    for fi, f in enumerate(manifest.get("filters") or []):
        if isinstance(f, dict):
            diags.extend(_check_filter(f, fi, manifest, dfs))

    diags.extend(_check_dataset_size(manifest, _table_dataset_refs(manifest)))

    return diags


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

    Data diagnostics (empty datasets, missing columns, all-NaN series,
    etc.) are collected per widget and returned on
    :class:`DashboardResult.diagnostics`. Render does not fail because
    of diagnostics -- broken charts get an empty placeholder option so
    the rest of the dashboard still renders.
    """
    pre_shapes = _capture_shape_info(manifest)
    shape_diags = _check_dataset_shape(manifest, pre_shapes)
    _normalize_manifest_datasets(manifest)
    _augment_manifest(manifest)
    ok, errs = validate_manifest(manifest)
    if not ok:
        return DashboardResult(
            manifest=manifest, manifest_path=None,
            html_path=None, html=None, success=False,
            error_message="manifest validation failed",
            warnings=list(errs) + [str(d) for d in shape_diags],
            diagnostics=list(shape_diags),
        )
    diags: List[Diagnostic] = (list(shape_diags)
                                  + list(chart_data_diagnostics(manifest)))
    if chart_specs is None:
        base = Path(base_dir) if base_dir else (
            Path(output_path).parent if output_path else Path.cwd()
        )
        chart_specs = _resolve_chart_specs(manifest, base, diags=diags)
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
        html=html, success=True,
        warnings=[str(d) for d in diags],
        diagnostics=diags,
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
    strict: bool = False,
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

    ``strict`` (default ``False``) raises :class:`ValueError` when any
    error-severity diagnostic fires (size budget breach, dataset shape
    mistake, missing column, etc.). The resilient default keeps the
    inner-loop iteration model -- compile still produces HTML, broken
    charts get placeholders, every diagnostic shows up on the result
    -- so PRISM can fix everything in one round-trip. Refresh
    pipelines and CI use ``strict=True`` to hard-fail before publishing
    a broken dashboard.
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

    pre_shapes = _capture_shape_info(manifest_dict)
    # Shape diagnostics run from the snapshot; any tuple/MultiIndex
    # dataset would also fail validation downstream, but the shape
    # diagnostic names the exact fix so we want it in the result even
    # when validation later rejects the manifest.
    shape_diags = _check_dataset_shape(manifest_dict, pre_shapes)
    _normalize_manifest_datasets(manifest_dict)
    _augment_manifest(manifest_dict)

    ok, errs = validate_manifest(manifest_dict)
    if not ok:
        return DashboardResult(
            manifest=manifest_dict, manifest_path=None,
            html_path=None, html=None, success=False,
            error_message="manifest validation failed",
            warnings=list(errs) + [str(d) for d in shape_diags],
            diagnostics=list(shape_diags),
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

    diags: List[Diagnostic] = (list(shape_diags)
                                  + list(chart_data_diagnostics(manifest_dict)))
    if strict:
        errors = [d for d in diags if d.severity == "error"]
        if errors:
            preview = "\n".join(f"  - {e}" for e in errors[:10])
            extra = (f"\n  ... and {len(errors) - 10} more"
                     if len(errors) > 10 else "")
            raise ValueError(
                f"compile_dashboard(strict=True): "
                f"{len(errors)} error-severity diagnostic(s):\n"
                f"{preview}{extra}"
            )
    chart_specs = _resolve_chart_specs(
        manifest_dict, base_dir, diags=diags,
    )

    html = render_dashboard_html(
        manifest_dict, chart_specs,
        filename_base=manifest_dict.get("id", "dashboard"),
    )

    if html_path and write_html:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

    warnings: List[str] = [str(d) for d in diags]
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
        diagnostics=diags,
    )


__all__ = [
    "Dashboard", "DashboardResult", "Tab",
    "ChartRef", "KPIRef", "TableRef", "MarkdownRef", "NoteRef", "DividerRef",
    "GlobalFilter", "Link",
    "compile_dashboard", "render_dashboard",
    "load_manifest", "validate_manifest", "save_manifest",
    "df_to_source", "manifest_template", "populate_template",
    "Diagnostic", "chart_data_diagnostics",
    "SCHEMA_VERSION", "VALID_WIDGETS", "VALID_FILTERS",
    "VALID_CHART_TYPES", "VALID_FILTER_OPS", "VALID_SYNC",
    "VALID_BRUSH_TYPES", "VALID_TABLE_FORMATS",
    "VALID_REFRESH_FREQUENCIES", "VALID_NOTE_KINDS",
    "DATASET_ROWS_WARN", "DATASET_ROWS_ERROR",
    "DATASET_BYTES_WARN", "DATASET_BYTES_ERROR",
    "MANIFEST_BYTES_WARN", "MANIFEST_BYTES_ERROR",
    "TABLE_ROWS_WARN", "TABLE_ROWS_ERROR",
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


def _print_diagnostics(diags: List[Diagnostic],
                         *, as_json: bool = False,
                         stream=None) -> None:
    """Pretty-print a list of Diagnostic to stderr.

    Default format groups by severity, with a header that includes:
    total counts, unique-widgets-affected count, and a code roll-up
    (which codes fired N times) so PRISM can decide whether to fix
    a single root cause or iterate per-widget.

    Each diagnostic line emits the structured ``str(diagnostic)``
    representation followed by an indented ``-> fix:`` hint when the
    diagnostic carries a ``fix_hint`` in its context. This keeps the
    tight one-liner format while making the actionable repair text
    obvious.

    JSON mode emits one JSON object per line for log scrapers / PRISM.
    """
    if stream is None:
        stream = sys.stderr
    if not diags:
        return
    if as_json:
        for d in diags:
            print(json.dumps(d.to_dict(), default=str), file=stream)
        return

    by_sev: Dict[str, List[Diagnostic]] = {"error": [], "warning": [],
                                              "info": []}
    for d in diags:
        by_sev.setdefault(d.severity, []).append(d)
    counts = {sev: len(lst) for sev, lst in by_sev.items() if lst}
    summary = ", ".join(f"{n} {sev}" + ("s" if n != 1 else "")
                        for sev, n in counts.items())
    distinct_widgets = sorted(set(
        d.widget_id for d in diags if d.widget_id
    ))
    code_counts: Dict[str, int] = {}
    for d in diags:
        code_counts[d.code] = code_counts.get(d.code, 0) + 1
    top_codes = sorted(code_counts.items(),
                        key=lambda kv: (-kv[1], kv[0]))[:5]
    code_roll_up = ", ".join(f"{c} x{n}" for c, n in top_codes)
    print(f"chart-data diagnostics: {summary} "
          f"({len(distinct_widgets)} widget(s) affected)",
          file=stream)
    if code_roll_up:
        print(f"  top codes: {code_roll_up}", file=stream)
    for sev in ("error", "warning", "info"):
        rows = by_sev.get(sev) or []
        if not rows:
            continue
        for d in rows:
            print(f"  - {d}", file=stream)
            hint = d.context.get("fix_hint") if isinstance(
                d.context, dict
            ) else None
            if hint:
                print(f"      -> fix: {hint}", file=stream)


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
    c.add_argument("--diagnostics-json", action="store_true",
                     help="emit chart-data diagnostics as JSON-lines on "
                          "stderr instead of human-readable text")

    b = sub.add_parser("build", help="render a manifest to HTML (alias of compile)")
    b.add_argument("manifest")
    b.add_argument("-o", "--output")
    b.add_argument("--open", action="store_true")

    v = sub.add_parser("validate", help="validate a manifest")
    v.add_argument("manifest")

    d = sub.add_parser(
        "diagnose",
        help=("lint a manifest for chart-data problems (empty datasets, "
                "missing columns, all-NaN series, etc.) without compiling"),
    )
    d.add_argument("manifest", help="manifest JSON file path OR raw JSON string")
    d.add_argument("--json", action="store_true",
                    help="emit diagnostics as JSON-lines (one per line)")
    d.add_argument("--severity", default=None,
                    choices=["error", "warning", "info"],
                    help="only emit diagnostics at this severity or higher")

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
        _print_diagnostics(
            r.diagnostics,
            as_json=bool(getattr(args, "diagnostics_json", False)),
        )
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
        _print_diagnostics(r.diagnostics, as_json=False)
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
    elif args.cmd == "diagnose":
        # Lint-only path: parse the manifest, run diagnostics, print, no
        # HTML / IO. Exit code reflects worst-severity finding so PRISM
        # iteration loops can branch on $? cleanly.
        text = str(args.manifest).strip()
        if text.startswith("{"):
            m = json.loads(text)
        else:
            m = load_manifest(args.manifest)
        _normalize_manifest_datasets(m)
        _augment_manifest(m)
        ok, errs = validate_manifest(m)
        if not ok:
            for e in errs:
                print(f"  VALIDATION_ERROR: {e}", file=sys.stderr)
            return 2
        diags = chart_data_diagnostics(m)
        sev_filter = getattr(args, "severity", None)
        if sev_filter:
            order = {"error": 0, "warning": 1, "info": 2}
            cutoff = order[sev_filter]
            diags = [d for d in diags
                     if order.get(d.severity, 99) <= cutoff]
        _print_diagnostics(diags, as_json=bool(getattr(args, "json", False)))
        if any(d.severity == "error" for d in diags):
            return 1
        return 0
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
            for w in sorted(VALID_WIDGETS):
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
