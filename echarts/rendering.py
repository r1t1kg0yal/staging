"""
rendering -- HTML templates + headless-Chrome PNG export for GS/viz/echarts.

Three concerns merged into one module:

    1. Single-chart editor HTML  (render_editor_html)
       Minimal-aesthetic interactive editor for one chart: knobs, spec-sheets,
       raw JSON escape hatch. Used by make_echart() and the composites layer.

    2. Dashboard HTML            (render_dashboard_html)
       GS-branded self-contained dashboard: cards, tabs, grid, global filters,
       brush cross-filter, echarts.connect() link groups. Used by
       compile_dashboard().

    3. PNG export                (save_chart_png, save_dashboard_pngs,
                                   save_dashboard_html_png, find_chrome)
       Server-side rasterization via headless Chrome. Zero Python deps; only
       requires a Chrome/Chromium binary (auto-detected on macOS, overridable
       via $CHROME_BIN).

Entry points
============

    render_editor_html(option, chart_id, chart_type, theme, palette,
                        dimension_preset, knob_defs, spec_sheets,
                        active_spec_sheet, user_id, filename_base) -> str

    render_dashboard_html(manifest, chart_specs, filename_base) -> str

    save_chart_png(option, path, ...) -> Path
    save_dashboard_pngs(manifest, chart_specs, dir, ...) -> List[Path]
    save_dashboard_html_png(html_path, png_path, ...) -> Path
    find_chrome() -> str

All PNG functions raise RuntimeError with an explicit message when the
Chrome dependency is not available -- there is no silent fallback.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from config import (
    THEMES, PALETTES, DIMENSION_PRESETS, TYPOGRAPHY_OVERRIDES,
    GS_SKY, GS_NAVY, GS_NAVY_DEEP, GS_INK, GS_PAPER, GS_BG,
    GS_GREY_70, GS_GREY_40, GS_GREY_20, GS_GREY_10, GS_GREY_05,
    GS_POS, GS_NEG, GS_FONT_SANS, GS_FONT_SERIF,
)


# =============================================================================
# SHARED HELPERS
# =============================================================================

def _html_escape(s: Any) -> str:
    """HTML-escape any value (cast to str first)."""
    return (str(s).replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _option_value_label(o: Any) -> Tuple[str, str]:
    """Normalise a filter option to a (value, label) pair of strings.

    Two option shapes are supported on `filters[].options`:

      * Primitive  -- ``"3M"``, ``42``, ``True``: value == label == ``str(o)``.
      * Dict       -- ``{"value": "sell", "label": "Looking to Sell"}``:
                      value comes from ``o["value"]``, label falls back to
                      ``o.get("label", o["value"])``.

    Anything else (list, set, dict without ``value``) is rejected here --
    ``validate_manifest`` catches the same shape earlier, so reaching this
    helper with a bad option is a programmer error, not user input.
    """
    if isinstance(o, dict):
        if "value" not in o:
            raise ValueError(
                f"filter option dict missing 'value' key: {o!r}")
        v = str(o["value"])
        l = str(o.get("label", o["value"]))
        return v, l
    if isinstance(o, (str, int, float, bool)):
        return str(o), str(o)
    raise ValueError(
        f"filter option must be a primitive or {{value,label}} dict, "
        f"got {type(o).__name__}: {o!r}")


def _default_value_for_compare(default: Any) -> Any:
    """Pull the underlying ``value`` out of a dict default so it compares
    against an option's value rather than against the whole dict.
    """
    if isinstance(default, dict) and "value" in default:
        return default["value"]
    return default


def _json_default(o: Any) -> Any:
    """json.dumps default handler that keeps numpy / pandas scalars as
    numbers instead of strings.

    The prior behaviour (``default=str``) turned ``numpy.int64(68)``
    into the string ``"68"``, which then fell through the KPI value
    format branch (``typeof v === 'number'``) and rendered without the
    configured prefix / suffix / decimals. We cast known scalar types
    to their plain Python counterparts here.
    """
    for attr in ("item",):
        f = getattr(o, attr, None)
        if callable(f):
            try:
                v = f()
            except Exception:  # noqa: BLE001
                v = None
            if isinstance(v, (bool, int, float)):
                return v
    try:
        import numpy as _np
        if isinstance(o, _np.integer):
            return int(o)
        if isinstance(o, _np.floating):
            return float(o)
        if isinstance(o, _np.bool_):
            return bool(o)
        if isinstance(o, _np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    try:
        import pandas as _pd
        if isinstance(o, _pd.Timestamp):
            return o.isoformat()
    except ImportError:
        pass
    return str(o)



# =============================================================================
# PART 1 -- SINGLE-CHART EDITOR HTML
# =============================================================================
# Minimal-aesthetic interactive editor: knob cards, spec sheets, data/code/
# metadata/export panels, raw JSON escape hatch.


HTML_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
/* bare-minimum layout; aesthetics intentionally austere per project
   convention. Typeface is the Goldman Sachs stack so the editor
   matches the rendered chart. */
html,body{margin:0;padding:0;font-family:__GS_FONT_SANS__;
  font-size:13px;background:#fff;color:__GS_INK__}
header,main,footer{padding:8px 12px}
header{border-bottom:2px solid __GS_NAVY__}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.wrap{display:flex;flex-wrap:wrap;gap:12px}
.chart-col{flex:1 1 600px;min-width:400px}
.side-col{flex:0 0 440px;min-width:320px;max-width:520px}
#chart{width:100%;height:480px}
.side-col{border-left:1px solid #ccc;padding-left:10px}
.tabs button{background:none;border:1px solid #ccc;padding:3px 8px;cursor:pointer;margin-right:2px}
.tabs button.active{background:#eee;font-weight:bold}
.tab{display:none;margin-top:6px}
.tab.active{display:block}
textarea.raw{width:100%;height:300px;font-family:monospace;font-size:11px}
table.data{border-collapse:collapse;font-size:11px}
table.data th,table.data td{border:1px solid #ccc;padding:2px 6px}
table.data th{background:#f4f4f4;cursor:pointer}
input[type=search]{padding:3px;width:200px}
details.card{border:1px solid #ccc;padding:8px;margin-bottom:8px}
details.card>summary{font-weight:bold;cursor:pointer;padding:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px}
.knob{display:flex;justify-content:space-between;align-items:center;margin:3px 0;gap:6px}
.knob label{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis}
.knob input,.knob select{flex:0 0 140px}
.knob input[type=range]{flex:0 0 100px}
.knob input[type=checkbox]{flex:0 0 auto}
.knob input[type=color]{flex:0 0 40px;padding:0}
.knob .val{flex:0 0 50px;text-align:right;font-family:monospace;font-size:11px}
button{cursor:pointer}
.status{color:#888;font-size:11px;margin-left:12px}
.group-title{font-weight:bold;margin-top:10px}
hr{border:none;border-top:1px solid #ccc;margin:6px 0}
</style>
</head>
<body>
<header>
<div class="row">
<strong>__TITLE__</strong>
<span class="status" id="chart-meta">chart_id: __CHART_ID__ | type: __CHART_TYPE__</span>
</div>
<div class="row" style="margin-top:4px">
<label>spec sheet:
<select id="sheet-select"></select>
</label>
<button id="sheet-save">Save</button>
<button id="sheet-saveas">Save as</button>
<button id="sheet-delete">Delete</button>
<button id="sheet-download">Download</button>
<button id="sheet-upload">Upload</button>
<input type="file" id="sheet-upload-file" accept=".json" style="display:none"/>
<span class="status" id="sheet-status"></span>
</div>
</header>
<main>
<div class="wrap">
<div class="chart-col">
<div class="row">
<button id="btn-reset">Reset view</button>
<button id="btn-full">Fullscreen</button>
<button id="btn-png2x">PNG 2x</button>
<button id="btn-png4x">PNG 4x</button>
<button id="btn-svg">SVG</button>
<span class="status" id="chart-status"></span>
</div>
<div id="chart" style="width:100%;height:480px"></div>
</div>
<div class="side-col">
<div class="tabs">
<button class="active" data-tab="data">Data</button>
<button data-tab="code">Code</button>
<button data-tab="meta">Metadata</button>
<button data-tab="export">Export</button>
<button data-tab="raw">Raw</button>
</div>
<div id="tab-data" class="tab active"></div>
<div id="tab-code" class="tab"></div>
<div id="tab-meta" class="tab"></div>
<div id="tab-export" class="tab"></div>
<div id="tab-raw" class="tab"></div>
</div>
</div>
<hr/>
<div class="row">
<input id="knob-search" type="search" placeholder="search knobs..."/>
<span class="status" id="knob-count"></span>
<button id="btn-reset-knobs">Reset all knobs</button>
</div>
<div id="knob-cards" class="cards" style="margin-top:8px"></div>
</main>
<footer>
<span class="status">echart_studio v__VERSION__ | echarts@5 (CDN)</span>
</footer>
<script>
__PAYLOAD__
__APP__
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# JS app: apply functions + knob wiring + tabs + spec sheets
# ---------------------------------------------------------------------------

APP_JS = r"""
(function(){
  'use strict';

  // Revive string-encoded JS functions into real functions before any
  // setOption call. The editor uses this for every mutation + reset path.
  function _isFnStr(s) {
    return typeof s === 'string' && /^\s*function\s*\(/.test(s);
  }
  function reviveFns(x) {
    if (x == null) return x;
    if (_isFnStr(x)) {
      try { return new Function('return (' + x + ')')(); }
      catch(e) { return x; }
    }
    if (Array.isArray(x)) {
      for (var i = 0; i < x.length; i++) x[i] = reviveFns(x[i]);
      return x;
    }
    if (typeof x === 'object') {
      for (var k in x) {
        if (Object.prototype.hasOwnProperty.call(x, k)) {
          x[k] = reviveFns(x[k]);
        }
      }
    }
    return x;
  }

  var state = {
    originalOption: JSON.parse(JSON.stringify(PAYLOAD.option)),
    option: JSON.parse(JSON.stringify(PAYLOAD.option)),
    chart: null,
    theme: PAYLOAD.theme,
    palette: PAYLOAD.palette,
    dimension: PAYLOAD.dimension,
    chartType: PAYLOAD.chartType,
    chartId: PAYLOAD.chartId,
    knobDefs: PAYLOAD.knobDefs,
    knobValues: {},
    sheets: PAYLOAD.sheets || {},
    activeSheet: PAYLOAD.activeSheet || '',
    sheetsKey: PAYLOAD.sheetsKey || 'echart_studio_sheets',
    prefKey: PAYLOAD.prefKey || ('echart_studio_prefs_' + PAYLOAD.chartType),
    paletteColors: PAYLOAD.paletteColors,
    paletteKind: PAYLOAD.paletteKind,
    themes: PAYLOAD.themes,
    palettes: PAYLOAD.palettes,
    dimensions: PAYLOAD.dimensions,
    typographyOverrides: PAYLOAD.typographyOverrides,
    version: PAYLOAD.version
  };

  // register themes
  try {
    Object.keys(state.themes || {}).forEach(function(tn){
      try { echarts.registerTheme(tn, state.themes[tn]); } catch(e){}
    });
  } catch(e){}

  // ------------------------------------------------------------------
  // APPLY FUNCTIONS
  // ------------------------------------------------------------------
  var APPLY = {};

  function getPath(obj, path){
    var parts = path.split('.'); var o = obj;
    for (var i=0;i<parts.length;i++){
      if (o == null) return undefined;
      var p = parts[i];
      var m = p.match(/^(.*)\[(\d+)\]$/);
      if (m){ o = o[m[1]]; if (o == null) return undefined; o = o[parseInt(m[2])]; }
      else { o = o[p]; }
    }
    return o;
  }
  function setPath(obj, path, val){
    var parts = path.split('.'); var o = obj;
    for (var i=0;i<parts.length-1;i++){
      var p = parts[i];
      var m = p.match(/^(.*)\[(\d+)\]$/);
      if (m){
        var arr = o[m[1]]; if (arr == null) { arr = []; o[m[1]] = arr; }
        var idx = parseInt(m[2]); if (arr[idx] == null) arr[idx] = {};
        o = arr[idx];
      } else {
        if (o[p] == null || typeof o[p] !== 'object' || Array.isArray(o[p])) o[p] = (typeof o[p] === 'object' && o[p] !== null) ? o[p] : {};
        o = o[p];
      }
    }
    var last = parts[parts.length-1];
    var mm = last.match(/^(.*)\[(\d+)\]$/);
    if (mm){ var arr2 = o[mm[1]] || (o[mm[1]] = []); arr2[parseInt(mm[2])] = val; }
    else { o[last] = val; }
  }

  // Title/subtitle
  APPLY.setTitleText = function(v){ setPath(state.option, 'title.text', v || ''); };
  APPLY.setSubtitleText = function(v){ setPath(state.option, 'title.subtext', v || ''); };

  // Legend position. All 'top*' positions sit at y=42 (row 2) so the
  // legend has its own row below the title/toolbox (row 1, y=0..30) and
  // never collides with either, regardless of chart width or the number
  // of legend entries.
  APPLY.setLegendPosition = function(v){
    var leg = state.option.legend || {}; state.option.legend = leg;
    ['top','bottom','left','right'].forEach(function(k){ delete leg[k]; });
    if (v === 'top') { leg.top = 42; leg.left = 'center'; }
    else if (v === 'bottom') { leg.bottom = 'bottom'; leg.left = 'center'; }
    else if (v === 'left') { leg.left = 'left'; leg.top = 'middle'; leg.orient = 'vertical'; }
    else if (v === 'right') { leg.right = 'right'; leg.top = 'middle'; leg.orient = 'vertical'; }
    else if (v === 'top-left') { leg.top = 42; leg.left = 'left'; }
    else if (v === 'top-right') { leg.top = 42; leg.right = 10; }
    else if (v === 'bottom-left') { leg.bottom = 'bottom'; leg.left = 'left'; }
    else if (v === 'bottom-right') { leg.bottom = 'bottom'; leg.right = 'right'; }
  };

  // Axis label / name sizes
  function forEachAxis(cb){
    ['xAxis','yAxis'].forEach(function(k){
      var ax = state.option[k]; if (!ax) return;
      if (Array.isArray(ax)) ax.forEach(cb); else cb(ax);
    });
  }
  APPLY.setAxisLabelSize = function(v){ forEachAxis(function(a){
    a.axisLabel = a.axisLabel || {}; a.axisLabel.fontSize = v;
  });};
  APPLY.setAxisNameSize = function(v){ forEachAxis(function(a){
    a.nameTextStyle = a.nameTextStyle || {}; a.nameTextStyle.fontSize = v;
  });};

  function xAxes(){ var a = state.option.xAxis; if (!a) return []; return Array.isArray(a)?a:[a]; }
  function yAxes(){ var a = state.option.yAxis; if (!a) return []; return Array.isArray(a)?a:[a]; }
  function onEachAxis(axisList, cb){ axisList.forEach(cb); }

  function applyBoundaryGap(axisList, v){
    axisList.forEach(function(a){
      if (v === 'default') delete a.boundaryGap;
      else if (v === 'true') a.boundaryGap = true;
      else if (v === 'false') a.boundaryGap = false;
    });
  }
  function tryNumber(v){ if (v === '' || v == null) return undefined; var n = Number(v); return isFinite(n) ? n : v; }
  function setMin(axisList, v){ axisList.forEach(function(a){ if (v === '' || v == null) delete a.min; else a.min = tryNumber(v); }); }
  function setMax(axisList, v){ axisList.forEach(function(a){ if (v === '' || v == null) delete a.max; else a.max = tryNumber(v); }); }
  APPLY.setXMin = function(v){ setMin(xAxes(), v); };
  APPLY.setXMax = function(v){ setMax(xAxes(), v); };
  APPLY.setYMin = function(v){ setMin(yAxes(), v); };
  APPLY.setYMax = function(v){ setMax(yAxes(), v); };
  APPLY.setXBoundaryGap = function(v){ applyBoundaryGap(xAxes(), v); };
  APPLY.setYBoundaryGap = function(v){ applyBoundaryGap(yAxes(), v); };
  APPLY.setXSplitLineColor = function(v){ xAxes().forEach(function(a){ a.splitLine = a.splitLine || {}; a.splitLine.lineStyle = a.splitLine.lineStyle || {}; a.splitLine.lineStyle.color = v; }); };
  APPLY.setYSplitLineColor = function(v){ yAxes().forEach(function(a){ a.splitLine = a.splitLine || {}; a.splitLine.lineStyle = a.splitLine.lineStyle || {}; a.splitLine.lineStyle.color = v; }); };
  APPLY.setXAxisLabelFormat = function(v){ xAxes().forEach(function(a){
    a.axisLabel = a.axisLabel || {};
    if (!v){ delete a.axisLabel.formatter; return; }
    a.axisLabel.formatter = v;
  });};
  APPLY.setYAxisLabelFormat = function(v){ yAxes().forEach(function(a){
    a.axisLabel = a.axisLabel || {};
    if (!v){ delete a.axisLabel.formatter; return; }
    a.axisLabel.formatter = v;
  });};

  // Toolbox feature toggles
  function toolboxFeat(){ state.option.toolbox = state.option.toolbox || {show:true, feature:{}}; state.option.toolbox.feature = state.option.toolbox.feature || {}; return state.option.toolbox.feature; }
  APPLY.setToolboxSaveAsImage = function(v){ var f = toolboxFeat(); if (v) f.saveAsImage = f.saveAsImage || {}; else delete f.saveAsImage; };
  APPLY.setToolboxDataZoom = function(v){ var f = toolboxFeat(); if (v) f.dataZoom = f.dataZoom || {}; else delete f.dataZoom; };
  APPLY.setToolboxRestore = function(v){ var f = toolboxFeat(); if (v) f.restore = f.restore || {}; else delete f.restore; };
  APPLY.setToolboxDataView = function(v){ var f = toolboxFeat(); if (v) f.dataView = f.dataView || {}; else delete f.dataView; };
  APPLY.setToolboxMagicType = function(v){ var f = toolboxFeat(); if (v) f.magicType = {type:['line','bar']}; else delete f.magicType; };
  APPLY.setToolboxBrush = function(v){ var f = toolboxFeat(); if (v) f.brush = {type:['rect','polygon','lineX','clear']}; else delete f.brush; };

  // DataZoom
  function dzFind(kind){
    var dz = state.option.dataZoom;
    if (!dz) return -1;
    if (!Array.isArray(dz)) dz = [dz];
    for (var i=0;i<dz.length;i++) if (dz[i] && dz[i].type === kind) return i;
    return -1;
  }
  function dzEnsure(){ if (!state.option.dataZoom) state.option.dataZoom = [];
    if (!Array.isArray(state.option.dataZoom)) state.option.dataZoom = [state.option.dataZoom]; }
  APPLY.setDataZoomShow = function(v){
    dzEnsure();
    var idx = dzFind('slider');
    if (v){ if (idx < 0) state.option.dataZoom.push({type:'slider'}); }
    else { if (idx >= 0) state.option.dataZoom.splice(idx,1); }
  };
  APPLY.setDataZoomInside = function(v){
    dzEnsure();
    var idx = dzFind('inside');
    if (v){ if (idx < 0) state.option.dataZoom.push({type:'inside'}); }
    else { if (idx >= 0) state.option.dataZoom.splice(idx,1); }
  };
  APPLY.setDataZoomStart = function(v){ dzEnsure(); state.option.dataZoom.forEach(function(d){ d.start = v; }); };
  APPLY.setDataZoomEnd = function(v){ dzEnsure(); state.option.dataZoom.forEach(function(d){ d.end = v; }); };
  APPLY.setDataZoomOrient = function(v){ dzEnsure(); state.option.dataZoom.forEach(function(d){ d.orient = v; }); };

  // Mark helpers
  function mainSeries(){
    var s = state.option.series; if (!s) return [];
    if (!Array.isArray(s)) return [s];
    return s;
  }
  function seriesOfType(t){ return mainSeries().filter(function(s){ return s.type === t; }); }

  // Line
  APPLY.setLineWidth = function(v){ seriesOfType('line').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.width = v; }); };
  APPLY.setLineSmooth = function(v){ seriesOfType('line').forEach(function(s){ s.smooth = !!v; }); };
  APPLY.setLineStep = function(v){ seriesOfType('line').forEach(function(s){ if (v === 'none') delete s.step; else s.step = v; }); };
  APPLY.setLineConnectNulls = function(v){ seriesOfType('line').forEach(function(s){ s.connectNulls = !!v; }); };
  APPLY.setLineShowSymbol = function(v){ seriesOfType('line').forEach(function(s){ s.showSymbol = !!v; }); };
  APPLY.setLineSymbolSize = function(v){ seriesOfType('line').forEach(function(s){ s.symbolSize = v; }); };
  APPLY.setLineAreaFill = function(v){ seriesOfType('line').forEach(function(s){ if (v){ s.areaStyle = s.areaStyle || {opacity:0.3}; } else delete s.areaStyle; }); };
  APPLY.setLineAreaOpacity = function(v){ seriesOfType('line').forEach(function(s){ if (s.areaStyle){ s.areaStyle.opacity = v; } }); };
  APPLY.setLineStack = function(v){ seriesOfType('line').forEach(function(s){ if (v) s.stack = 'total'; else delete s.stack; }); };
  APPLY.setLineStyleType = function(v){ seriesOfType('line').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.type = v; }); };

  // Bar
  APPLY.setBarWidth = function(v){ seriesOfType('bar').forEach(function(s){ if (v === '' || v == null) delete s.barWidth; else s.barWidth = v; }); };
  APPLY.setBarMaxWidth = function(v){ seriesOfType('bar').forEach(function(s){ if (v === '' || v == null) delete s.barMaxWidth; else s.barMaxWidth = v; }); };
  APPLY.setBarCategoryGap = function(v){ seriesOfType('bar').forEach(function(s){ s.barCategoryGap = v; }); };
  APPLY.setBarGap = function(v){ seriesOfType('bar').forEach(function(s){ s.barGap = v; }); };
  APPLY.setBarBorderRadius = function(v){ seriesOfType('bar').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderRadius = v; }); };
  APPLY.setBarOpacity = function(v){ seriesOfType('bar').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.opacity = v; }); };
  APPLY.setBarStack = function(v){ seriesOfType('bar').forEach(function(s){ if (v) s.stack = 'total'; else delete s.stack; }); };
  APPLY.setBarLabelShow = function(v){ seriesOfType('bar').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };
  APPLY.setBarLabelPosition = function(v){ seriesOfType('bar').forEach(function(s){ s.label = s.label || {}; s.label.position = v; }); };

  // Scatter
  APPLY.setScatterSymbolSize = function(v){ seriesOfType('scatter').forEach(function(s){ s.symbolSize = v; }); };
  APPLY.setScatterSymbol = function(v){ seriesOfType('scatter').forEach(function(s){ s.symbol = v; }); };
  APPLY.setScatterOpacity = function(v){ seriesOfType('scatter').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.opacity = v; }); };
  APPLY.setScatterBorderWidth = function(v){ seriesOfType('scatter').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderWidth = v; }); };

  // Area (lines with areaStyle; we also cover pure area by piggybacking on setLineArea*)
  APPLY.setAreaOpacity = function(v){ seriesOfType('line').forEach(function(s){ if (s.areaStyle){ s.areaStyle.opacity = v; } }); };
  APPLY.setAreaStack = function(v){ seriesOfType('line').forEach(function(s){ if (v) s.stack = 'total'; else delete s.stack; }); };
  APPLY.setAreaLineWidth = function(v){ seriesOfType('line').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.width = v; }); };
  APPLY.setAreaSmooth = function(v){ seriesOfType('line').forEach(function(s){ s.smooth = !!v; }); };

  // Heatmap
  APPLY.setHeatmapShowLabels = function(v){ seriesOfType('heatmap').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };
  APPLY.setHeatmapBorderWidth = function(v){ seriesOfType('heatmap').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderWidth = v; }); };

  // Pie
  APPLY.setPieInnerRadius = function(v){ seriesOfType('pie').forEach(function(s){ var r = s.radius || ['0%','75%']; if (!Array.isArray(r)) r = ['0%', r]; r[0] = v; s.radius = r; }); };
  APPLY.setPieOuterRadius = function(v){ seriesOfType('pie').forEach(function(s){ var r = s.radius || ['0%','75%']; if (!Array.isArray(r)) r = ['0%', r]; r[1] = v; s.radius = r; }); };
  APPLY.setPieRoseType = function(v){ seriesOfType('pie').forEach(function(s){ if (v === 'none') delete s.roseType; else s.roseType = v; }); };
  APPLY.setPieLabelShow = function(v){ seriesOfType('pie').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };
  APPLY.setPieLabelPosition = function(v){ seriesOfType('pie').forEach(function(s){ s.label = s.label || {}; s.label.position = v; }); };
  APPLY.setPieLabelLine = function(v){ seriesOfType('pie').forEach(function(s){ s.labelLine = s.labelLine || {}; s.labelLine.show = !!v; }); };
  APPLY.setPieBorderRadius = function(v){ seriesOfType('pie').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderRadius = v; }); };

  // Boxplot
  APPLY.setBoxBorderWidth = function(v){ seriesOfType('boxplot').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderWidth = v; }); };
  APPLY.setBoxItemWidth = function(v){ seriesOfType('boxplot').forEach(function(s){ s.boxWidth = [Math.max(1,v/2), v]; }); };

  // Sankey
  APPLY.setSankeyNodeWidth = function(v){ seriesOfType('sankey').forEach(function(s){ s.nodeWidth = v; }); };
  APPLY.setSankeyNodeGap = function(v){ seriesOfType('sankey').forEach(function(s){ s.nodeGap = v; }); };
  APPLY.setSankeyOrient = function(v){ seriesOfType('sankey').forEach(function(s){ s.orient = v; }); };
  APPLY.setSankeyLinkOpacity = function(v){ seriesOfType('sankey').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.opacity = v; }); };
  APPLY.setSankeyLinkCurveness = function(v){ seriesOfType('sankey').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.curveness = v; }); };
  APPLY.setSankeyDraggable = function(v){ seriesOfType('sankey').forEach(function(s){ s.draggable = !!v; }); };

  // Treemap / sunburst
  APPLY.setTreemapLeafDepth = function(v){ seriesOfType('treemap').forEach(function(s){ s.leafDepth = v; }); };
  APPLY.setTreemapRoam = function(v){ seriesOfType('treemap').forEach(function(s){ s.roam = !!v; }); };
  APPLY.setTreemapNodeClick = function(v){ seriesOfType('treemap').forEach(function(s){ if (v === 'false') s.nodeClick = false; else s.nodeClick = v; }); };
  APPLY.setSunburstInnerRadius = function(v){ seriesOfType('sunburst').forEach(function(s){ var r = s.radius || ['0%','90%']; if (!Array.isArray(r)) r = ['0%', r]; r[0] = v; s.radius = r; }); };
  APPLY.setSunburstOuterRadius = function(v){ seriesOfType('sunburst').forEach(function(s){ var r = s.radius || ['0%','90%']; if (!Array.isArray(r)) r = ['0%', r]; r[1] = v; s.radius = r; }); };
  APPLY.setSunburstHighlightPolicy = function(v){ seriesOfType('sunburst').forEach(function(s){ s.emphasis = s.emphasis || {}; s.emphasis.focus = v === 'none' ? undefined : v; }); };

  // Graph
  APPLY.setGraphLayout = function(v){ seriesOfType('graph').forEach(function(s){ s.layout = v; }); };
  APPLY.setGraphRoam = function(v){ seriesOfType('graph').forEach(function(s){ s.roam = !!v; }); };
  APPLY.setGraphRepulsion = function(v){ seriesOfType('graph').forEach(function(s){ s.force = s.force || {}; s.force.repulsion = v; }); };
  APPLY.setGraphEdgeLength = function(v){ seriesOfType('graph').forEach(function(s){ s.force = s.force || {}; s.force.edgeLength = v; }); };
  APPLY.setGraphEdgeSymbol = function(v){ seriesOfType('graph').forEach(function(s){ if (v === 'none') s.edgeSymbol = ['none','none']; else s.edgeSymbol = ['none', v]; }); };
  APPLY.setGraphDraggable = function(v){ seriesOfType('graph').forEach(function(s){ s.draggable = !!v; }); };

  // Candlestick
  APPLY.setCandleBullColor = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.color = v; }); };
  APPLY.setCandleBearColor = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.color0 = v; }); };
  APPLY.setCandleBorderBull = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderColor = v; }); };
  APPLY.setCandleBorderBear = function(v){ seriesOfType('candlestick').forEach(function(s){ s.itemStyle = s.itemStyle || {}; s.itemStyle.borderColor0 = v; }); };

  // Radar
  APPLY.setRadarShape = function(v){ state.option.radar = state.option.radar || {}; state.option.radar.shape = v; };
  APPLY.setRadarSplitNumber = function(v){ state.option.radar = state.option.radar || {}; state.option.radar.splitNumber = v; };
  APPLY.setRadarAreaOpacity = function(v){ seriesOfType('radar').forEach(function(s){ s.areaStyle = s.areaStyle || {}; s.areaStyle.opacity = v; }); };

  // Gauge
  APPLY.setGaugeMin = function(v){ seriesOfType('gauge').forEach(function(s){ s.min = v; }); };
  APPLY.setGaugeMax = function(v){ seriesOfType('gauge').forEach(function(s){ s.max = v; }); };
  APPLY.setGaugeSplitNumber = function(v){ seriesOfType('gauge').forEach(function(s){ s.splitNumber = v; }); };
  APPLY.setGaugeStartAngle = function(v){ seriesOfType('gauge').forEach(function(s){ s.startAngle = v; }); };
  APPLY.setGaugeEndAngle = function(v){ seriesOfType('gauge').forEach(function(s){ s.endAngle = v; }); };

  // Calendar
  APPLY.setCalendarOrient = function(v){ state.option.calendar = state.option.calendar || {}; state.option.calendar.orient = v; };
  APPLY.setCalendarCellSize = function(v){ state.option.calendar = state.option.calendar || {}; state.option.calendar.cellSize = ['auto', v]; };
  APPLY.setCalendarYearLabel = function(v){ state.option.calendar = state.option.calendar || {}; state.option.calendar.yearLabel = state.option.calendar.yearLabel || {}; state.option.calendar.yearLabel.show = !!v; };

  // Parallel coords
  APPLY.setParallelLineOpacity = function(v){ seriesOfType('parallel').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.opacity = v; }); };
  APPLY.setParallelLineWidth = function(v){ seriesOfType('parallel').forEach(function(s){ s.lineStyle = s.lineStyle || {}; s.lineStyle.width = v; }); };
  APPLY.setParallelLayoutHorizontal = function(v){ state.option.parallel = state.option.parallel || {}; state.option.parallel.layout = v ? 'horizontal' : 'vertical'; };

  // Funnel
  APPLY.setFunnelSort = function(v){ seriesOfType('funnel').forEach(function(s){ s.sort = v === 'none' ? undefined : v; }); };
  APPLY.setFunnelGap = function(v){ seriesOfType('funnel').forEach(function(s){ s.gap = v; }); };
  APPLY.setFunnelMin = function(v){ seriesOfType('funnel').forEach(function(s){ s.min = v; }); };
  APPLY.setFunnelMax = function(v){ seriesOfType('funnel').forEach(function(s){ s.max = v; }); };
  APPLY.setFunnelLabelShow = function(v){ seriesOfType('funnel').forEach(function(s){ s.label = s.label || {}; s.label.show = !!v; }); };

  // Tree
  APPLY.setTreeOrient = function(v){ seriesOfType('tree').forEach(function(s){ s.orient = v; s.layout = v === 'radial' ? 'radial' : 'orthogonal'; }); };
  APPLY.setTreeSymbolSize = function(v){ seriesOfType('tree').forEach(function(s){ s.symbolSize = v; }); };
  APPLY.setTreeRoam = function(v){ seriesOfType('tree').forEach(function(s){ s.roam = !!v; }); };

  // ------------------------------------------------------------------
  // KNOB RENDERING + WIRING
  // ------------------------------------------------------------------

  function applyKnob(def, val){
    state.knobValues[def.name] = val;
    if (def.apply){
      var fn = APPLY[def.apply];
      if (typeof fn === 'function') fn(val);
    } else if (def.path){
      setPath(state.option, def.path, val);
    }
  }

  function renderKnob(def){
    var row = document.createElement('div'); row.className = 'knob'; row.dataset.knob = def.name;
    var lab = document.createElement('label'); lab.textContent = def.label; lab.title = def.name;
    row.appendChild(lab);
    var val = state.knobValues[def.name];
    if (val === undefined) val = def.default;
    var input;
    if (def.type === 'range'){
      input = document.createElement('input'); input.type = 'range';
      input.min = def.min; input.max = def.max; input.step = def.step;
      input.value = val;
      var valSpan = document.createElement('span'); valSpan.className = 'val'; valSpan.textContent = val;
      input.addEventListener('input', function(){
        var v = Number(input.value); valSpan.textContent = v;
        applyKnob(def, v); render();
      });
      row.appendChild(input); row.appendChild(valSpan);
    } else if (def.type === 'number'){
      input = document.createElement('input'); input.type = 'number'; input.value = val;
      input.addEventListener('input', function(){ var v = Number(input.value); applyKnob(def, v); render(); });
      row.appendChild(input);
    } else if (def.type === 'select'){
      input = document.createElement('select');
      (def.options || []).forEach(function(o){ var op = document.createElement('option'); op.value = o; op.textContent = o; input.appendChild(op); });
      input.value = val;
      input.addEventListener('change', function(){ applyKnob(def, input.value); render(); });
      row.appendChild(input);
    } else if (def.type === 'checkbox'){
      input = document.createElement('input'); input.type = 'checkbox'; input.checked = !!val;
      input.addEventListener('change', function(){ applyKnob(def, input.checked); render(); });
      row.appendChild(input);
    } else if (def.type === 'color'){
      input = document.createElement('input'); input.type = 'color'; input.value = val || '#000000';
      input.addEventListener('input', function(){ applyKnob(def, input.value); render(); });
      row.appendChild(input);
    } else {
      input = document.createElement('input'); input.type = 'text'; input.value = val == null ? '' : val;
      input.addEventListener('change', function(){ applyKnob(def, input.value); render(); });
      row.appendChild(input);
    }
    return row;
  }

  function groupedKnobs(){
    var groups = {};
    (state.knobDefs || []).forEach(function(def){
      var g = def.group || 'Other';
      groups[g] = groups[g] || [];
      groups[g].push(def);
    });
    return groups;
  }

  function renderKnobCards(){
    var wrap = document.getElementById('knob-cards');
    wrap.innerHTML = '';
    // Presets card
    var presets = document.createElement('details'); presets.className = 'card'; presets.open = true;
    var psum = document.createElement('summary'); psum.textContent = 'Presets'; presets.appendChild(psum);
    presets.appendChild(makePresetRow('Theme', Object.keys(state.themes), state.theme, function(v){ state.theme = v; applyTheme(v); render(); rerenderKnobs(); }));
    var paletteNames = Object.keys(state.palettes);
    presets.appendChild(makePresetRow('Palette', paletteNames, state.palette, function(v){ state.palette = v; applyPalette(v); render(); }));
    presets.appendChild(makePresetRow('Dimensions', Object.keys(state.dimensions), state.dimension, function(v){ state.dimension = v; applyDimension(v); render(); rerenderKnobs(); }));
    wrap.appendChild(presets);

    // Essentials card
    var ess = document.createElement('details'); ess.className = 'card'; ess.open = true;
    var esum = document.createElement('summary'); esum.textContent = 'Essentials'; ess.appendChild(esum);
    (state.knobDefs || []).forEach(function(d){ if (d.essential || ESSENTIALS[d.name]) ess.appendChild(renderKnob(d)); });
    wrap.appendChild(ess);

    // Other groups
    var grouped = groupedKnobs();
    var order = ['Title','Typography','Layout','Grid','XAxis','YAxis','Legend','Tooltip','Toolbox','DataZoom','VisualMap','Interactivity','Mark','Colors'];
    var seen = {};
    order.forEach(function(g){
      if (!grouped[g]) return; seen[g] = true;
      var d = document.createElement('details'); d.className = 'card'; d.open = false;
      var sum = document.createElement('summary'); sum.textContent = g; d.appendChild(sum);
      grouped[g].forEach(function(def){ d.appendChild(renderKnob(def)); });
      wrap.appendChild(d);
    });
    Object.keys(grouped).forEach(function(g){
      if (seen[g]) return;
      var d = document.createElement('details'); d.className = 'card'; d.open = false;
      var sum = document.createElement('summary'); sum.textContent = g; d.appendChild(sum);
      grouped[g].forEach(function(def){ d.appendChild(renderKnob(def)); });
      wrap.appendChild(d);
    });

    // Session Prefs card
    var sp = document.createElement('details'); sp.className = 'card';
    var spSum = document.createElement('summary'); spSum.textContent = 'Session preferences'; sp.appendChild(spSum);
    var resetBtn = document.createElement('button'); resetBtn.textContent = 'Reset to theme defaults';
    resetBtn.addEventListener('click', function(){ resetToTheme(); });
    sp.appendChild(resetBtn);
    wrap.appendChild(sp);

    document.getElementById('knob-count').textContent = (state.knobDefs || []).length + ' knobs';
  }

  var ESSENTIALS = ESSENTIAL_NAMES;

  function makePresetRow(label, options, current, onChange){
    var row = document.createElement('div'); row.className = 'knob';
    var l = document.createElement('label'); l.textContent = label; row.appendChild(l);
    var sel = document.createElement('select');
    options.forEach(function(o){ var op = document.createElement('option'); op.value = o; op.textContent = o; sel.appendChild(op); });
    sel.value = current;
    sel.addEventListener('change', function(){ onChange(sel.value); });
    row.appendChild(sel); return row;
  }

  function applyTheme(name){
    state.theme = name;
    var theme = state.themes[name];
    if (theme && theme.color){ state.option.color = theme.color.slice(); }
    var kv = THEME_KNOB_VALUES[name] || {};
    Object.keys(kv).forEach(function(n){
      var def = KNOB_INDEX[n]; if (!def) return;
      applyKnob(def, kv[n]);
    });
  }

  function applyPalette(name){
    var p = state.palettes[name];
    if (!p) return;
    state.paletteColors = p.colors;
    state.paletteKind = p.kind;
    if (p.kind === 'categorical'){
      state.option.color = p.colors.slice();
    } else {
      // sequential/diverging -> visualMap ramp if present
      if (state.option.visualMap){
        var vm = state.option.visualMap;
        if (!Array.isArray(vm)) vm = [vm];
        vm.forEach(function(v){ v.inRange = {color: p.colors.slice()}; });
        state.option.visualMap = vm;
      }
    }
  }

  function applyDimension(name){
    var dim = state.dimensions[name]; if (!dim) return;
    var chartEl = document.getElementById('chart');
    chartEl.style.width = dim.width + 'px';
    chartEl.style.height = dim.height + 'px';
    state.chart && state.chart.resize();
    // typography override
    var to = state.typographyOverrides[name];
    if (to){
      Object.keys(to).forEach(function(k){
        var def = KNOB_INDEX[k]; if (!def) return;
        applyKnob(def, to[k]);
      });
    }
  }

  function resetToTheme(){
    state.option = JSON.parse(JSON.stringify(state.originalOption));
    state.knobValues = {};
    applyTheme(state.theme);
    render(); rerenderKnobs();
  }

  function rerenderKnobs(){
    renderKnobCards();
    filterKnobs(document.getElementById('knob-search').value || '');
  }

  function filterKnobs(q){
    q = q.toLowerCase();
    document.querySelectorAll('.knob').forEach(function(row){
      var label = row.querySelector('label');
      var name = row.dataset.knob || '';
      var text = (label ? label.textContent : '') + ' ' + name;
      row.style.display = (!q || text.toLowerCase().indexOf(q) >= 0) ? 'flex' : 'none';
    });
  }

  // Index knob defs by name
  var KNOB_INDEX = {};
  (state.knobDefs || []).forEach(function(d){ KNOB_INDEX[d.name] = d; });
  var THEME_KNOB_VALUES = PAYLOAD.themeKnobValues;

  // ------------------------------------------------------------------
  // CHART RENDERING
  // ------------------------------------------------------------------

  function render(){
    if (!state.chart){
      state.chart = echarts.init(document.getElementById('chart'), state.theme in state.themes ? state.theme : null);
    }
    try {
      // Pass through the reviver so renderItem/formatter/filter strings
      // become real functions. state.option is kept as-is so Raw/Code tab
      // still shows the serializable JSON.
      var live = reviveFns(JSON.parse(JSON.stringify(state.option)));
      state.chart.setOption(live, true);
      document.getElementById('chart-status').textContent = 'ok';
    } catch (e){
      document.getElementById('chart-status').textContent = 'error: ' + (e && e.message || e);
    }
    refreshTabs();
  }

  function refreshTabs(){
    refreshCodeTab(); refreshDataTab(); refreshMetaTab(); refreshExportTab(); refreshRawTab();
  }

  function refreshCodeTab(){
    var el = document.getElementById('tab-code');
    el.innerHTML = '';
    var pre = document.createElement('pre');
    pre.textContent = JSON.stringify(state.option, null, 2);
    var copyBtn = document.createElement('button'); copyBtn.textContent = 'Copy JSON';
    copyBtn.addEventListener('click', function(){
      try { navigator.clipboard.writeText(pre.textContent); copyBtn.textContent = 'copied'; setTimeout(function(){copyBtn.textContent = 'Copy JSON';}, 800); } catch(e){}
    });
    el.appendChild(copyBtn); el.appendChild(pre);
  }

  function extractData(){
    var rows = [];
    (mainSeries() || []).forEach(function(s){
      if (s.data && Array.isArray(s.data)){
        s.data.forEach(function(d){ rows.push({series: s.name || s.type, data: d}); });
      }
    });
    return rows;
  }

  function refreshDataTab(){
    var el = document.getElementById('tab-data');
    el.innerHTML = '';
    var rows = extractData();
    var info = document.createElement('div'); info.textContent = rows.length + ' rows across ' + (mainSeries().length) + ' series';
    el.appendChild(info);
    if (rows.length === 0) return;
    var tbl = document.createElement('table'); tbl.className = 'data';
    var thead = document.createElement('thead'); var trh = document.createElement('tr');
    ['series','value'].forEach(function(h){ var th = document.createElement('th'); th.textContent = h; trh.appendChild(th); });
    thead.appendChild(trh); tbl.appendChild(thead);
    var tbody = document.createElement('tbody');
    rows.slice(0, 500).forEach(function(r){
      var tr = document.createElement('tr');
      var tds = document.createElement('td'); tds.textContent = r.series;
      var tdv = document.createElement('td'); tdv.textContent = JSON.stringify(r.data);
      tr.appendChild(tds); tr.appendChild(tdv); tbody.appendChild(tr);
    });
    tbl.appendChild(tbody); el.appendChild(tbl);
    if (rows.length > 500){
      var more = document.createElement('div'); more.textContent = '(showing first 500 of ' + rows.length + ' rows)';
      el.appendChild(more);
    }
  }

  function refreshMetaTab(){
    var el = document.getElementById('tab-meta');
    el.innerHTML = '';
    var k = ['chart_id','chart_type','theme','palette','dimension'];
    var v = [state.chartId, state.chartType, state.theme, state.palette, state.dimension];
    var dl = document.createElement('dl');
    for (var i=0;i<k.length;i++){
      var dt = document.createElement('dt'); dt.textContent = k[i];
      var dd = document.createElement('dd'); dd.textContent = v[i];
      dl.appendChild(dt); dl.appendChild(dd);
    }
    el.appendChild(dl);
    var series = document.createElement('div');
    series.textContent = 'series types: ' + mainSeries().map(function(s){ return s.type; }).join(', ');
    el.appendChild(series);
  }

  function refreshExportTab(){
    var el = document.getElementById('tab-export');
    el.innerHTML = '';
    var specs = [
      {label: 'PNG 1x', fn: function(){ downloadImage(1, 'png'); }},
      {label: 'PNG 2x', fn: function(){ downloadImage(2, 'png'); }},
      {label: 'PNG 4x', fn: function(){ downloadImage(4, 'png'); }},
      {label: 'SVG', fn: function(){ downloadSvg(); }},
      {label: 'Option JSON', fn: function(){ downloadText('option.json', JSON.stringify(state.option, null, 2)); }},
      {label: 'Spec Sheet JSON', fn: function(){ downloadText('spec_sheet.json', JSON.stringify(exportSheet(), null, 2)); }},
    ];
    specs.forEach(function(s){ var b = document.createElement('button'); b.textContent = s.label; b.addEventListener('click', s.fn); el.appendChild(b); });
  }

  function refreshRawTab(){
    var el = document.getElementById('tab-raw');
    el.innerHTML = '';
    var title = document.createElement('div'); title.textContent = 'Edit ECharts option as JSON. Changes apply on blur.';
    el.appendChild(title);
    var ta = document.createElement('textarea'); ta.className = 'raw';
    ta.value = JSON.stringify(state.option, null, 2);
    ta.addEventListener('blur', function(){
      try {
        var parsed = JSON.parse(ta.value);
        state.option = parsed; render();
        document.getElementById('chart-status').textContent = 'raw applied';
      } catch (e){
        document.getElementById('chart-status').textContent = 'invalid JSON';
      }
    });
    el.appendChild(ta);
  }

  // ------------------------------------------------------------------
  // EXPORT / IO
  // ------------------------------------------------------------------

  function downloadImage(pixelRatio, type){
    var url = state.chart.getDataURL({pixelRatio: pixelRatio, backgroundColor: state.option.backgroundColor || '#fff', type: type});
    var a = document.createElement('a'); a.href = url; a.download = (PAYLOAD.filename || 'chart') + '.' + type; a.click();
  }
  function downloadSvg(){
    var dom = document.getElementById('chart');
    var svg = dom.querySelector('svg');
    if (!svg) { alert('SVG renderer not active. Use PNG.'); return; }
    var xml = new XMLSerializer().serializeToString(svg);
    var blob = new Blob([xml], {type: 'image/svg+xml'});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = (PAYLOAD.filename || 'chart') + '.svg'; a.click();
  }
  function downloadText(name, text){
    var blob = new Blob([text], {type: 'text/plain'});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
  }

  // ------------------------------------------------------------------
  // SPEC SHEETS (localStorage)
  // ------------------------------------------------------------------

  function loadSheets(){
    try {
      var raw = localStorage.getItem(state.sheetsKey);
      if (raw){ state.sheets = Object.assign({}, state.sheets, JSON.parse(raw)); }
    } catch(e){}
  }
  function saveSheets(){
    try { localStorage.setItem(state.sheetsKey, JSON.stringify(state.sheets)); } catch(e){}
  }
  function refreshSheetDropdown(){
    var sel = document.getElementById('sheet-select');
    sel.innerHTML = '';
    var none = document.createElement('option'); none.value = ''; none.textContent = '(none)'; sel.appendChild(none);
    Object.keys(state.sheets).forEach(function(id){
      var op = document.createElement('option'); op.value = id; op.textContent = state.sheets[id].name || id; sel.appendChild(op);
    });
    sel.value = state.activeSheet || '';
  }
  function exportSheet(){
    return {
      schema_version: 1,
      spec_sheet_id: state.activeSheet || 'unnamed',
      name: state.activeSheet || 'unnamed',
      base_theme: state.theme, base_palette: state.palette,
      base_dimension_preset: state.dimension,
      overrides: Object.assign({}, state.knobValues),
      created_at: new Date().toISOString(), updated_at: new Date().toISOString()
    };
  }
  function applySheet(sheet){
    if (!sheet) return;
    if (sheet.base_theme){ state.theme = sheet.base_theme; applyTheme(sheet.base_theme); }
    if (sheet.base_palette){ state.palette = sheet.base_palette; applyPalette(sheet.base_palette); }
    if (sheet.base_dimension_preset){ state.dimension = sheet.base_dimension_preset; applyDimension(sheet.base_dimension_preset); }
    Object.keys(sheet.overrides || {}).forEach(function(n){
      var def = KNOB_INDEX[n]; if (!def) return;
      applyKnob(def, sheet.overrides[n]);
    });
    render(); rerenderKnobs();
  }

  // ------------------------------------------------------------------
  // WIRE UI
  // ------------------------------------------------------------------

  document.querySelectorAll('.tabs button').forEach(function(b){
    b.addEventListener('click', function(){
      document.querySelectorAll('.tabs button').forEach(function(x){ x.classList.remove('active'); });
      document.querySelectorAll('.tab').forEach(function(x){ x.classList.remove('active'); });
      b.classList.add('active');
      document.getElementById('tab-' + b.dataset.tab).classList.add('active');
    });
  });

  document.getElementById('btn-reset').addEventListener('click', function(){
    state.chart && state.chart.dispatchAction({type: 'restore'});
  });
  document.getElementById('btn-full').addEventListener('click', function(){
    var el = document.getElementById('chart');
    if (document.fullscreenElement) document.exitFullscreen(); else el.requestFullscreen();
  });
  document.getElementById('btn-png2x').addEventListener('click', function(){ downloadImage(2, 'png'); });
  document.getElementById('btn-png4x').addEventListener('click', function(){ downloadImage(4, 'png'); });
  document.getElementById('btn-svg').addEventListener('click', function(){ downloadSvg(); });

  document.getElementById('knob-search').addEventListener('input', function(e){ filterKnobs(e.target.value); });
  document.getElementById('btn-reset-knobs').addEventListener('click', function(){ resetToTheme(); });

  // sheet buttons
  document.getElementById('sheet-save').addEventListener('click', function(){
    var id = state.activeSheet || prompt('Name for this spec sheet:'); if (!id) return;
    var s = exportSheet(); s.spec_sheet_id = id; s.name = id;
    state.sheets[id] = s; state.activeSheet = id; saveSheets(); refreshSheetDropdown();
    document.getElementById('sheet-status').textContent = 'saved';
  });
  document.getElementById('sheet-saveas').addEventListener('click', function(){
    var id = prompt('New sheet name:'); if (!id) return;
    var s = exportSheet(); s.spec_sheet_id = id; s.name = id;
    state.sheets[id] = s; state.activeSheet = id; saveSheets(); refreshSheetDropdown();
  });
  document.getElementById('sheet-delete').addEventListener('click', function(){
    if (!state.activeSheet) return;
    delete state.sheets[state.activeSheet]; state.activeSheet = ''; saveSheets(); refreshSheetDropdown();
  });
  document.getElementById('sheet-download').addEventListener('click', function(){
    downloadText((state.activeSheet || 'spec_sheet') + '.json', JSON.stringify(exportSheet(), null, 2));
  });
  document.getElementById('sheet-upload').addEventListener('click', function(){
    document.getElementById('sheet-upload-file').click();
  });
  document.getElementById('sheet-upload-file').addEventListener('change', function(e){
    var f = e.target.files[0]; if (!f) return;
    var fr = new FileReader();
    fr.onload = function(){
      try {
        var s = JSON.parse(fr.result);
        var id = s.spec_sheet_id || s.name || ('sheet_' + Date.now());
        state.sheets[id] = s; state.activeSheet = id; saveSheets(); refreshSheetDropdown();
        applySheet(s);
      } catch(err){ alert('bad JSON'); }
    };
    fr.readAsText(f);
  });
  document.getElementById('sheet-select').addEventListener('change', function(e){
    state.activeSheet = e.target.value;
    if (state.activeSheet){ applySheet(state.sheets[state.activeSheet]); }
    else { resetToTheme(); }
  });

  // init
  loadSheets(); refreshSheetDropdown();
  renderKnobCards();
  filterKnobs('');
  render();
  if (state.activeSheet && state.sheets[state.activeSheet]) applySheet(state.sheets[state.activeSheet]);
})();
"""


def _essential_names_map() -> Dict[str, bool]:
    from echart_studio import ESSENTIAL_NAMES
    return {n: True for n in ESSENTIAL_NAMES}


def _themes_for_js() -> Dict[str, Any]:
    """Return a name -> ECharts theme object map for registerTheme."""
    return {name: theme["echarts"] for name, theme in THEMES.items()}


def _theme_knob_values_for_js() -> Dict[str, Dict[str, Any]]:
    return {name: dict(theme["knob_values"]) for name, theme in THEMES.items()}


def _palettes_for_js() -> Dict[str, Any]:
    return {name: {"colors": list(p["colors"]), "kind": p["kind"]}
            for name, p in PALETTES.items()}


def _dimensions_for_js() -> Dict[str, Any]:
    return {name: {"width": d["width"], "height": d["height"]}
            for name, d in DIMENSION_PRESETS.items()}


def render_editor_html(
    option: Dict[str, Any],
    chart_id: str,
    chart_type: str,
    theme: str,
    palette: str,
    dimension_preset: str,
    knob_defs: List[Dict[str, Any]],
    spec_sheets: Optional[Dict[str, Any]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
    filename_base: Optional[str] = None,
) -> str:
    """Render the single-chart editor HTML document."""
    from echart_studio import __version__ as VERSION

    title = option.get("title", {}).get("text", "") or filename_base or "chart"
    essential_map = _essential_names_map()
    # Also mark per-knob .essential flags
    for d in knob_defs:
        if d.get("essential"):
            essential_map[d["name"]] = True

    payload = {
        "option": option,
        "chartId": chart_id,
        "chartType": chart_type,
        "theme": theme,
        "palette": palette,
        "dimension": dimension_preset,
        "knobDefs": knob_defs,
        "themes": _themes_for_js(),
        "palettes": _palettes_for_js(),
        "dimensions": _dimensions_for_js(),
        "typographyOverrides": dict(TYPOGRAPHY_OVERRIDES),
        "themeKnobValues": _theme_knob_values_for_js(),
        "paletteColors": list(PALETTES[palette]["colors"]),
        "paletteKind": PALETTES[palette]["kind"],
        "sheets": spec_sheets or {},
        "activeSheet": active_spec_sheet or "",
        "sheetsKey": f"echart_studio_sheets_{user_id or 'anon'}",
        "prefKey": f"echart_studio_prefs_{user_id or 'anon'}_{chart_type}",
        "filename": filename_base or "chart",
        "version": VERSION,
    }
    payload_js = (
        "var PAYLOAD = " + json.dumps(payload, default=_json_default) + ";\n"
        "var ESSENTIAL_NAMES = " + json.dumps(essential_map) + ";\n"
    )
    html = (HTML_SHELL
            .replace("__TITLE__", _html_escape(title))
            .replace("__CHART_ID__", chart_id)
            .replace("__CHART_TYPE__", chart_type)
            .replace("__VERSION__", VERSION)
            .replace("__PAYLOAD__", payload_js)
            .replace("__APP__", APP_JS)
            .replace("__GS_FONT_SANS__", GS_FONT_SANS)
            .replace("__GS_NAVY__", GS_NAVY)
            .replace("__GS_INK__", GS_INK)
            .replace("__GS_PAPER__", GS_PAPER))
    return html


# =============================================================================
# PART 2 -- DASHBOARD HTML
# =============================================================================
# GS-branded cards, tabs, grid layout, global filter bus, echarts.connect()
# link groups, brush cross-filter via shared dataset scopes.


DASHBOARD_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
<style>
/* =============================================================
   Goldman Sachs canonical design tokens (synced with
   GS/viz/echarts/config.py). There is one style -- this one.
   ============================================================= */
:root {
  --gs-navy:       __GS_NAVY__;
  --gs-navy-deep:  __GS_NAVY_DEEP__;
  --gs-sky:        __GS_SKY__;
  --gs-ink:        __GS_INK__;
  --gs-paper:      __GS_PAPER__;
  --gs-bg:         __GS_BG__;
  --gs-grey-70:    __GS_GREY_70__;
  --gs-grey-40:    __GS_GREY_40__;
  --gs-grey-20:    __GS_GREY_20__;
  --gs-grey-10:    __GS_GREY_10__;
  --gs-grey-05:    __GS_GREY_05__;
  --gs-pos:        __GS_POS__;
  --gs-neg:        __GS_NEG__;
  --gs-font-sans:  __GS_FONT_SANS__;
  --gs-font-serif: __GS_FONT_SERIF__;

  /* semantic slots used by the chrome */
  --bg:            var(--gs-bg);
  --surface:       var(--gs-paper);
  --surface-2:     var(--gs-grey-05);
  --surface-hover: #F2F5FA;
  --text:          var(--gs-ink);
  --text-dim:      var(--gs-grey-70);
  --text-faint:    var(--gs-grey-40);
  --border:        var(--gs-grey-10);
  --border-strong: var(--gs-grey-20);
  --accent:        var(--gs-navy);
  --accent-2:      var(--gs-sky);
  --accent-soft:   rgba(115,153,198,0.16);
  --accent-ring:   rgba(0,47,108,0.14);
  --pos:           var(--gs-pos);
  --pos-soft:      rgba(46,125,50,0.12);
  --neg:           var(--gs-neg);
  --neg-soft:      rgba(179,38,30,0.10);

  /* surface geometry */
  --shadow-sm:  0 1px 2px rgba(10,18,40,0.04);
  --shadow:     0 1px 3px rgba(10,18,40,0.06),
                0 1px 2px rgba(10,18,40,0.04);
  --shadow-md:  0 4px 8px -2px rgba(10,18,40,0.08),
                0 2px 4px -2px rgba(10,18,40,0.05);
  --shadow-lg:  0 12px 24px -4px rgba(10,18,40,0.12),
                0 4px 8px -4px rgba(10,18,40,0.08);
  --radius:     6px;
  --radius-sm:  4px;
  --bounce:     cubic-bezier(0.34, 1.56, 0.64, 1);
  --ease:       cubic-bezier(0.16, 1, 0.3, 1);
}

* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: var(--bg); color: var(--text);
  font-family: var(--gs-font-sans);
  font-size: 14px; line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-feature-settings: "ss01", "ss02", "kern", "liga", "tnum";
  transition: background-color 0.15s var(--ease),
              color 0.15s var(--ease);
}

.app { display: flex; flex-direction: column; min-height: 100vh; }

/* GS brand mark -- a compact navy "blue-box" reminiscent of the
   historic Goldman Sachs logo. Pure CSS, no images. */
.gs-mark {
  display: inline-flex; align-items: center; gap: 10px;
  font-family: var(--gs-font-serif); letter-spacing: 0.01em;
}
.gs-mark .gs-box {
  width: 28px; height: 28px; background: var(--gs-navy);
  color: #fff; display: inline-flex; align-items: center;
  justify-content: center;
  font-family: var(--gs-font-serif); font-weight: 700;
  font-size: 13px; letter-spacing: 0.02em;
}
.gs-mark .gs-wordmark {
  font-family: var(--gs-font-serif); font-weight: 600;
  font-size: 13px; color: var(--gs-ink);
  letter-spacing: 0.03em; white-space: nowrap;
}

header.app-header {
  background: var(--surface);
  border-bottom: 2px solid var(--gs-navy);
  padding: 16px 28px 14px 28px;
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 18px; flex-wrap: wrap;
}
.header-titles { flex: 1 1 auto; min-width: 280px;
                   display: flex; flex-direction: column; gap: 4px; }
.header-titles h1 {
  font-family: var(--gs-font-serif);
  font-size: 22px; margin: 2px 0 0 0; font-weight: 600;
  letter-spacing: -0.005em; color: var(--gs-ink);
}
.header-titles .subtitle {
  color: var(--text-dim); font-size: 13px;
  max-width: 820px; font-family: var(--gs-font-sans);
}
.header-meta { color: var(--text-faint); font-size: 12px;
                 display: flex; align-items: center; gap: 10px;
                 font-variant-numeric: tabular-nums; flex-wrap: wrap; }
.header-meta .meta-dot {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; background: var(--gs-grey-05);
  border: 1px solid var(--border); border-radius: 3px;
  color: var(--text-dim); font-size: 11px;
}
.header-meta .meta-dot span { color: var(--gs-ink); font-weight: 600; }
.header-actions .icon-btn.refreshing {
  background: var(--gs-grey-05); color: var(--text-dim);
  cursor: wait; opacity: 0.9;
}
.header-actions .icon-btn.refresh-success {
  background: var(--pos); color: #fff; border-color: var(--pos);
}
.header-actions .icon-btn.refresh-error {
  background: var(--neg); color: #fff; border-color: var(--neg);
}
.badge {
  padding: 3px 9px; font-size: 10px; border-radius: 2px;
  background: var(--gs-navy); color: #fff;
  font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;
  font-family: var(--gs-font-sans);
}
.header-actions { display: flex; gap: 6px; align-items: center; }
.icon-btn {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 6px 12px;
  cursor: pointer; color: var(--text); font-size: 12px;
  font-family: var(--gs-font-sans); font-weight: 500;
  letter-spacing: 0.01em;
  display: inline-flex; align-items: center; gap: 6px;
  transition: background-color 0.12s var(--ease),
              border-color 0.12s var(--ease),
              color 0.12s var(--ease),
              transform 0.12s var(--bounce);
}
.icon-btn:hover {
  background: var(--surface-hover);
  border-color: var(--accent-2);
  color: var(--accent);
}
.icon-btn:active { transform: scale(0.97); }
.icon-btn.primary {
  background: var(--accent); color: #fff; border-color: var(--accent);
}
.icon-btn.primary:hover {
  background: var(--gs-navy-deep); border-color: var(--gs-navy-deep);
  color: #fff;
}

nav.tab-bar {
  display: flex; gap: 0; padding: 0 28px;
  background: var(--surface); border-bottom: 1px solid var(--border);
  overflow-x: auto; scrollbar-width: thin;
}
.tab-btn {
  background: none; border: none;
  padding: 12px 18px; font-size: 12px; color: var(--text-dim);
  border-bottom: 2px solid transparent; cursor: pointer;
  transition: color 0.12s var(--ease),
              border-color 0.15s var(--ease),
              background-color 0.12s var(--ease);
  font-family: var(--gs-font-sans);
  white-space: nowrap;
  font-weight: 600;
  letter-spacing: 0.04em; text-transform: uppercase;
}
.tab-btn:hover { color: var(--accent); background: var(--surface-hover); }
.tab-btn.active {
  color: var(--accent); border-bottom-color: var(--gs-navy);
  background: var(--gs-grey-05);
}

.filter-bar {
  background: var(--surface); padding: 12px 28px;
  border-bottom: 1px solid var(--border);
  display: flex; gap: 18px; flex-wrap: wrap; align-items: center;
}
.filter-item {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--text-dim);
  font-family: var(--gs-font-sans);
}
.filter-item label {
  font-weight: 600; color: var(--text);
  letter-spacing: 0.04em; text-transform: uppercase; font-size: 11px;
  display: inline-flex; align-items: center; gap: 4px;
}
.filter-info {
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; color: var(--text-faint); cursor: pointer;
  text-transform: none; letter-spacing: 0; font-weight: 400;
  border-radius: 50%; user-select: none;
}
.filter-info:hover { color: var(--accent);
                      background: var(--surface-hover); }
.filter-info:focus { outline: 2px solid var(--accent-ring); outline-offset: 2px; }
.filter-item select, .filter-item input[type=text], .filter-item input[type=date],
.filter-item input[type=number] {
  padding: 6px 10px; border: 1px solid var(--border);
  border-radius: var(--radius-sm); background: var(--surface);
  font-size: 13px; color: var(--text); font-family: inherit;
  min-width: 120px;
  transition: border-color 0.15s var(--ease),
              box-shadow 0.15s var(--ease);
}
.filter-item select[multiple] {
  min-width: 160px; min-height: 68px;
  padding: 4px 8px;
}
.filter-item.slider input[type=range] { min-width: 140px; }
.filter-item select:focus, .filter-item input:focus {
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-ring);
}
.filter-item input[type=checkbox] {
  accent-color: var(--accent); width: 15px; height: 15px;
}
.filter-reset { margin-left: auto; }

.tab-filter-bar {
  display: inline-flex; gap: 14px; flex-wrap: wrap; align-items: center;
  padding: 8px 12px; margin-bottom: 14px;
  background: var(--gs-grey-05);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.tab-filter-bar .filter-item { font-size: 12px; }
.tab-filter-bar .filter-item label { font-size: 10.5px; }
.tab-filter-bar .filter-item select,
.tab-filter-bar .filter-item input[type=text],
.tab-filter-bar .filter-item input[type=number],
.tab-filter-bar .filter-item input[type=date] {
  padding: 4px 8px; font-size: 12px;
}
.tab-filter-bar .filter-reset {
  margin-left: 0; padding: 4px 10px; font-size: 11px;
}

main.app-main { padding: 20px 28px 40px 28px; flex: 1 1 auto; }

.tab-panel {
  display: none;
  animation: fadeInUp 0.22s var(--ease);
}
.tab-panel.active { display: block; }
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.tab-panel-header {
  margin-bottom: 14px;
  display: flex; justify-content: space-between; align-items: baseline;
  border-left: 3px solid var(--gs-navy); padding-left: 10px;
}
.tab-panel-header h2 {
  font-family: var(--gs-font-serif);
  font-size: 13px; margin: 0; color: var(--text-dim);
  font-weight: 500; font-style: italic;
}

.grid { display: grid; grid-template-columns: repeat(__COLS__, 1fr); gap: 14px; }

.tile {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: box-shadow 0.18s var(--ease),
              border-color 0.18s var(--ease);
  display: flex; flex-direction: column;
}
.tile:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--accent-2);
}
.tile.is-fullscreen {
  position: fixed; inset: 16px; z-index: 50;
  box-shadow: var(--shadow-lg);
  grid-column: 1/-1 !important;
}
.tile-header {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  gap: 8px;
  background: var(--surface);
}
.tile-title-wrap {
  flex: 1 1 auto; min-width: 0;
  display: flex; flex-direction: column; gap: 2px;
}
.tile-title {
  font-family: var(--gs-font-sans);
  font-size: 12px; font-weight: 600; color: var(--gs-ink);
  letter-spacing: 0.04em; text-transform: uppercase;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px;
  min-width: 0;
}
.tile-subtitle {
  font-family: var(--gs-font-serif);
  font-size: 11px; color: var(--text-dim);
  font-style: italic; font-weight: 400;
  letter-spacing: 0.01em;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.tile-info {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; font-size: 13px; color: var(--text-faint);
  cursor: pointer; border-radius: 50%; user-select: none;
  text-transform: none; letter-spacing: 0;
  transition: color 0.12s var(--ease),
              background-color 0.12s var(--ease);
}
.tile-info:hover { color: var(--accent); background: var(--surface-hover); }
.tile-info:focus { outline: 2px solid var(--accent-ring); outline-offset: 2px; }
.tile-info:hover { color: var(--accent); }
.tile-info-kpi { margin-left: 6px; vertical-align: middle; }
.tile-badge {
  display: inline-flex; align-items: center;
  padding: 1px 7px; border-radius: 999px;
  font-family: var(--gs-font-sans); font-size: 9px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase;
  background: var(--gs-navy); color: white;
}
.tile-badge[data-color="gs-navy"] { background: var(--gs-navy); color: white; }
.tile-badge[data-color="sky"]     { background: var(--gs-sky);
                                      color: var(--gs-navy-deep); }
.tile-badge[data-color="pos"]     { background: var(--pos-soft);
                                      color: var(--pos); }
.tile-badge[data-color="neg"]     { background: var(--neg-soft);
                                      color: var(--neg); }
.tile-badge[data-color="muted"]   { background: var(--surface-2);
                                      color: var(--text-dim); }
.tile-actions { display: flex; gap: 2px; flex: 0 0 auto; }
.tile-btn, a.tile-btn {
  background: none; border: 1px solid transparent;
  border-radius: var(--radius-sm); padding: 3px 8px;
  cursor: pointer; color: var(--text-faint); font-size: 11px;
  font-family: var(--gs-font-sans); font-weight: 600;
  letter-spacing: 0.04em; text-decoration: none;
  transition: color 0.12s var(--ease),
              background-color 0.12s var(--ease),
              border-color 0.12s var(--ease);
}
.tile-btn:hover, a.tile-btn:hover { background: var(--surface-2);
                                      color: var(--accent);
                                      border-color: var(--accent-2); }
.tile-btn.primary, a.tile-btn.primary {
  background: var(--gs-navy); color: white;
  border-color: var(--gs-navy);
}
.tile-btn.primary:hover, a.tile-btn.primary:hover {
  background: var(--gs-navy-deep); color: white;
  border-color: var(--gs-navy-deep);
}
.tile-btn-custom { padding: 3px 10px; }
.tile-body { padding: 10px 14px; flex: 1 1 auto; position: relative; }

.tile-footer {
  padding: 6px 14px 8px; font-size: 11px; color: var(--text-faint);
  font-family: var(--gs-font-sans); border-top: 1px dashed var(--border);
  background: var(--surface);
  line-height: 1.45;
}
.tile-emphasis {
  border-color: var(--gs-navy);
  box-shadow: 0 0 0 1px var(--gs-navy), var(--shadow-md);
}
.tile-emphasis::before {
  content: ''; display: block; height: 3px; background: var(--gs-navy);
  margin: -1px -1px 0 -1px;
  border-top-left-radius: var(--radius-md);
  border-top-right-radius: var(--radius-md);
}
.tile-emphasis.kpi-tile { border-top-width: 3px;
                            border-top-color: var(--gs-sky); }
.tile-emphasis.kpi-tile::before { display: none; }
.tile-pinned {
  position: sticky; top: 12px; z-index: 5;
}

/* chart tile */
.chart-tile .tile-body { padding: 6px 8px 8px; }
.chart-div { width: 100%; min-height: 240px; }

/* kpi tile */
.kpi-tile {
  padding: 16px 20px 18px 20px;
  display: flex; flex-direction: column; justify-content: center;
  min-height: 118px; gap: 0;
  border-top: 3px solid var(--gs-navy);
}
.kpi-label {
  font-family: var(--gs-font-sans);
  font-size: 10px; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.09em;
  font-weight: 700;
}
.kpi-value {
  font-family: var(--gs-font-serif);
  font-size: 32px; font-weight: 600; margin-top: 8px;
  line-height: 1.02; color: var(--gs-navy);
  font-feature-settings: "tnum";
  letter-spacing: -0.015em;
}
.kpi-value.small { font-size: 24px; }
.kpi-delta {
  font-family: var(--gs-font-sans);
  font-size: 11px; margin-top: 6px; font-weight: 600;
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: 2px; align-self: flex-start;
  letter-spacing: 0.02em;
}
.kpi-delta.pos { color: var(--pos); background: var(--pos-soft); }
.kpi-delta.neg { color: var(--neg); background: var(--neg-soft); }
.kpi-delta.flat { color: var(--text-dim); background: var(--surface-2); }
.kpi-sub { font-size: 11px; color: var(--text-faint); margin-top: 6px;
           font-family: var(--gs-font-sans); }
.kpi-sparkline { height: 32px; margin-top: 10px;
                  margin-left: -4px; margin-right: -4px; }

/* markdown tile + shared prose styling.
   Both `.markdown-tile` (transparent prose-on-page) and
   `.markdown-body` (used inside note tiles, drill-down sections,
   summary banner, popups) share the typography rules so prose
   reads identically wherever PRISM places it. */
.markdown-tile {
  background: transparent; border: none; box-shadow: none;
  padding: 0;
}
.markdown-tile .tile-body { padding: 12px 4px; }
.markdown-tile h1, .markdown-tile h2, .markdown-tile h3,
.markdown-tile h4, .markdown-tile h5,
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5 {
  margin: 6px 0 6px 0; color: var(--text);
  font-family: var(--gs-font-serif); font-weight: 600;
  letter-spacing: -0.005em;
}
.markdown-tile h1, .markdown-body h1 { font-size: 20px; }
.markdown-tile h2, .markdown-body h2 { font-size: 15px; }
.markdown-tile h3, .markdown-body h3 {
  font-family: var(--gs-font-sans);
  font-size: 11px; color: var(--text-dim);
  text-transform: uppercase; letter-spacing: 0.09em; font-weight: 700;
}
.markdown-tile h4, .markdown-body h4 {
  font-family: var(--gs-font-sans);
  font-size: 12px; color: var(--text); font-weight: 700;
}
.markdown-tile h5, .markdown-body h5 {
  font-family: var(--gs-font-sans);
  font-size: 11px; color: var(--text-dim); font-weight: 700;
  font-style: italic;
}
.markdown-tile p, .markdown-body p {
  margin: 4px 0; color: var(--text-dim); line-height: 1.6;
  font-family: var(--gs-font-sans);
}
.markdown-tile a, .markdown-body a {
  color: var(--accent); text-decoration: underline;
  text-decoration-color: var(--accent-2);
  text-underline-offset: 3px;
}
.markdown-tile a:hover, .markdown-body a:hover {
  color: var(--gs-navy-deep);
}
.markdown-tile ul, .markdown-tile ol,
.markdown-body ul, .markdown-body ol {
  margin: 6px 0; padding-left: 22px; color: var(--text-dim);
  font-family: var(--gs-font-sans); line-height: 1.55;
}
.markdown-tile li, .markdown-body li { margin: 2px 0; }
.markdown-tile ul ul, .markdown-tile ul ol,
.markdown-tile ol ul, .markdown-tile ol ol,
.markdown-body ul ul, .markdown-body ul ol,
.markdown-body ol ul, .markdown-body ol ol {
  margin: 2px 0; padding-left: 18px;
}
.markdown-tile blockquote, .markdown-body blockquote {
  margin: 8px 0; padding: 6px 12px;
  border-left: 3px solid var(--accent-2);
  background: rgba(115,153,198,0.08);
  color: var(--text-dim); font-style: italic;
}
.markdown-tile blockquote p, .markdown-body blockquote p {
  margin: 2px 0; font-style: italic;
}
.markdown-tile pre, .markdown-body pre {
  margin: 6px 0; padding: 8px 12px;
  background: var(--gs-grey-05);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow-x: auto;
}
.markdown-tile pre code, .markdown-body pre code {
  background: none; padding: 0;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px; color: var(--text); line-height: 1.5;
}
.markdown-tile code, .markdown-body code {
  background: var(--gs-grey-05); padding: 1px 4px;
  border-radius: 3px;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px; color: var(--text);
}
.markdown-tile hr, .markdown-body hr {
  margin: 12px 0; border: none;
  border-top: 1px solid var(--border);
}
.markdown-tile del, .markdown-body del {
  color: var(--text-faint);
  text-decoration-thickness: 1.5px;
}
.markdown-tile table.md-table, .markdown-body table.md-table {
  border-collapse: collapse; margin: 8px 0;
  font-family: var(--gs-font-sans); font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.markdown-tile table.md-table th, .markdown-body table.md-table th {
  text-align: left; padding: 6px 10px;
  border-bottom: 1px solid var(--gs-navy);
  background: var(--gs-grey-05);
  text-transform: uppercase; font-size: 10px;
  letter-spacing: 0.08em; color: var(--gs-ink); font-weight: 700;
}
.markdown-tile table.md-table td, .markdown-body table.md-table td {
  padding: 6px 10px; border-bottom: 1px solid var(--border);
  color: var(--text);
}

/* note tile - semantic callout for narrative writing.
   Six kinds, each with its own accent stripe + label tint:
     insight   sky      "this is the lightbulb"
     thesis    navy     "this is the load-bearing claim"
     watch     amber    "this is what to monitor"
     risk      red      "this is the downside"
     context   muted    "this is background"
     fact      green    "this is established"
   The body is full markdown via the shared `.markdown-body`
   typography rules so prose matches the markdown widget. */
.note-tile {
  background: var(--surface); border: 1px solid var(--border);
  border-left: 4px solid var(--accent-2);
  border-radius: var(--radius);
  padding: 10px 14px 12px 14px;
  box-shadow: var(--shadow-sm);
}
.note-tile .note-head {
  display: flex; align-items: baseline; gap: 8px;
  margin-bottom: 4px;
}
.note-tile .note-icon {
  font-size: 14px; color: var(--accent-2);
}
.note-tile .note-kind {
  font-family: var(--gs-font-sans);
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.09em;
  color: var(--accent-2);
}
.note-tile .note-title {
  font-family: var(--gs-font-serif);
  font-size: 14px; font-weight: 600; color: var(--text);
  letter-spacing: -0.005em;
}
.note-tile .note-body { padding: 0; }
.note-tile .note-body > :first-child { margin-top: 0; }
.note-tile .note-body > :last-child { margin-bottom: 0; }
.note-tile .tile-footer { margin-top: 8px; }
.note-tile-insight {
  border-left-color: var(--accent-2);
  background: rgba(115,153,198,0.06);
}
.note-tile-insight .note-icon,
.note-tile-insight .note-kind { color: var(--accent-2); }
.note-tile-thesis {
  border-left-color: var(--accent);
  background: var(--accent-soft);
}
.note-tile-thesis .note-icon,
.note-tile-thesis .note-kind { color: var(--accent); }
.note-tile-watch {
  border-left-color: #dd6b20;
  background: rgba(221,107,32,0.07);
}
.note-tile-watch .note-icon,
.note-tile-watch .note-kind { color: #dd6b20; }
.note-tile-risk {
  border-left-color: var(--neg);
  background: var(--neg-soft);
}
.note-tile-risk .note-icon,
.note-tile-risk .note-kind { color: var(--neg); }
.note-tile-context {
  border-left-color: var(--gs-grey-40);
  background: var(--gs-grey-05);
}
.note-tile-context .note-icon,
.note-tile-context .note-kind { color: var(--text-dim); }
.note-tile-fact {
  border-left-color: var(--pos);
  background: var(--pos-soft);
}
.note-tile-fact .note-icon,
.note-tile-fact .note-kind { color: var(--pos); }

/* dashboard summary banner - markdown body rendered below the
   global filter bar, above the first row / tab bar. Used for the
   one-paragraph "today's read" / "executive summary" that sits at
   the top of the page so PRISM can frame the dashboard before any
   chart loads. Uses .markdown-body typography for parity with the
   markdown widget. */
.summary-banner {
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 4px solid var(--gs-navy);
  border-radius: var(--radius);
  padding: 12px 18px;
  margin: 14px 28px 0 28px;
}
.summary-banner > :first-child { margin-top: 0; }
.summary-banner > :last-child { margin-bottom: 0; }

/* divider tile */
.divider-tile {
  background: transparent; border: none; box-shadow: none;
  padding: 8px 0;
}
.divider-tile hr {
  border: none; border-top: 1px solid var(--gs-grey-20);
  margin: 0;
}

/* table tile */
.table-tile .tile-body { padding: 0; }
.data-table {
  border-collapse: collapse; width: 100%; font-size: 12px;
  font-family: var(--gs-font-sans);
  font-variant-numeric: tabular-nums;
}
.data-table thead { background: var(--gs-grey-05);
                      position: sticky; top: 0;
                      border-bottom: 2px solid var(--gs-navy); }
.data-table th {
  padding: 8px 12px; text-align: left; font-weight: 700;
  color: var(--gs-ink); text-transform: uppercase;
  letter-spacing: 0.08em; font-size: 10px;
}
.data-table td {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  color: var(--text);
}
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--surface-hover); }
.data-table.compact th { padding: 5px 8px; font-size: 9px; }
.data-table.compact td { padding: 5px 8px; font-size: 11px; }
.data-table.clickable tbody tr { cursor: pointer; }
.data-table th.sortable { cursor: pointer; user-select: none; }
.data-table th.sortable:hover { background: var(--gs-grey-10); }

/* Row highlight buckets (see row_highlight on table widgets).
   Subtle left-border accent + tinted background so the row pops
   without stomping the per-cell conditional colors. Note: the
   `--pos-soft` / `--neg-soft` variables are deliberately used
   directly here -- avoiding `color-mix(in srgb, ..., transparent)`
   so html2canvas (used by the "Download Dashboard" button) can
   parse this rule. The visual difference is imperceptible because
   both vars are already very low-alpha rgba. */
.data-table tr.row-hl-pos td   { background: var(--pos-soft); }
.data-table tr.row-hl-pos td:first-child {
  box-shadow: inset 3px 0 0 var(--pos);
}
.data-table tr.row-hl-neg td   { background: var(--neg-soft); }
.data-table tr.row-hl-neg td:first-child {
  box-shadow: inset 3px 0 0 var(--neg);
}
.data-table tr.row-hl-warn td  { background: rgba(221, 107, 32, 0.08); }
.data-table tr.row-hl-warn td:first-child {
  box-shadow: inset 3px 0 0 #dd6b20;
}
.data-table tr.row-hl-info td  { background: rgba(49, 130, 206, 0.07); }
.data-table tr.row-hl-info td:first-child {
  box-shadow: inset 3px 0 0 var(--accent);
}
.data-table tr.row-hl-muted td { background: var(--gs-grey-05);
                                   color: var(--text-dim); }

.table-toolbar {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px; background: var(--gs-grey-05);
  border-bottom: 1px solid var(--border);
}
.table-toolbar .table-search {
  flex: 1; min-width: 120px; max-width: 320px;
  padding: 6px 10px; border: 1px solid var(--border);
  border-radius: 4px; font-size: 12px; font-family: var(--gs-font-sans);
  background: var(--surface);
}
.table-toolbar .table-search:focus { outline: none; border-color: var(--gs-navy); }
.table-toolbar .table-count {
  color: var(--text-faint); font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.table-toolbar .table-xlsx-btn {
  margin-left: auto;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-dim); border-radius: 4px;
  padding: 5px 10px; font-size: 11px;
  font-family: var(--gs-font-sans); font-weight: 600;
  letter-spacing: 0.04em; cursor: pointer;
  transition: background 0.12s var(--ease), color 0.12s var(--ease),
              border-color 0.12s var(--ease);
}
.table-toolbar .table-xlsx-btn:hover {
  background: var(--gs-navy); color: #fff; border-color: var(--gs-navy);
}
.table-toolbar .table-xlsx-btn:focus {
  outline: 2px solid var(--accent-ring); outline-offset: 2px;
}
.table-empty {
  padding: 32px 16px; text-align: center; color: var(--text-faint);
  font-size: 12px; font-style: italic;
}

/* modal popup (row-click details) */
.ed-modal-backdrop {
  position: fixed; inset: 0; background: rgba(26, 54, 93, 0.45);
  display: none; align-items: center; justify-content: center;
  z-index: 9999;
}
.ed-modal {
  background: var(--surface); border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  max-width: 640px; min-width: 360px;
  max-height: 86vh; overflow: auto;
  border-top: 4px solid var(--gs-navy);
}
.ed-modal.wide {
  max-width: 880px; min-width: 560px;
}
.ed-modal-header {
  padding: 14px 18px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 14px;
}
.ed-modal-title-wrap { flex: 1 1 auto; min-width: 0; }
.ed-modal-title { font-weight: 600; font-size: 16px; color: var(--gs-navy);
                    font-family: var(--gs-font-serif); }
.ed-modal-subtitle {
  font-size: 12px; color: var(--text-dim); font-style: italic;
  margin-top: 2px; display: none;
}
.ed-modal-close {
  background: transparent; border: none; cursor: pointer;
  font-size: 16px; color: var(--text-faint); padding: 4px 8px;
}
.ed-modal-close:hover { color: var(--text); }
.ed-modal-body {
  padding: 16px 18px; font-size: 13px; line-height: 1.55;
  color: var(--text);
}
.ed-modal-body p { margin: 0 0 10px; }
.ed-modal-body p:last-child { margin-bottom: 0; }
.ed-modal-body h1, .ed-modal-body h2, .ed-modal-body h3,
.ed-modal-body h4, .ed-modal-body h5 {
  font-family: var(--gs-font-sans); color: var(--gs-navy);
  margin: 0 0 10px; font-weight: 600;
}
.ed-modal-body h1 { font-size: 16px; }
.ed-modal-body h2 { font-size: 14px; }
.ed-modal-body h3 { font-size: 13px; text-transform: uppercase;
                     letter-spacing: 0.04em; color: var(--text-faint); }
.ed-modal-body h4 { font-size: 13px; color: var(--text); }
.ed-modal-body h5 { font-size: 12px; color: var(--text-dim);
                     font-style: italic; }
.ed-modal-body ul, .ed-modal-body ol {
  margin: 6px 0 12px 18px; padding: 0;
}
.ed-modal-body li { margin-bottom: 4px; }
.ed-modal-body ul ul, .ed-modal-body ul ol,
.ed-modal-body ol ul, .ed-modal-body ol ol {
  margin: 4px 0 4px 18px;
}
.ed-modal-body blockquote {
  margin: 8px 0; padding: 6px 12px;
  border-left: 3px solid var(--accent-2);
  background: rgba(115,153,198,0.08);
  color: var(--text-dim); font-style: italic;
}
.ed-modal-body pre {
  margin: 8px 0; padding: 8px 12px;
  background: var(--gs-grey-05); border: 1px solid var(--border);
  border-radius: var(--radius-sm); overflow-x: auto;
}
.ed-modal-body pre code {
  background: none; padding: 0;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px; color: var(--text);
}
.ed-modal-body hr {
  margin: 12px 0; border: none;
  border-top: 1px solid var(--border);
}
.ed-modal-body del { color: var(--text-faint); }
.ed-modal-body table.md-table {
  border-collapse: collapse; margin: 8px 0;
  font-family: var(--gs-font-sans); font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.ed-modal-body table.md-table th {
  text-align: left; padding: 5px 10px;
  border-bottom: 1px solid var(--gs-navy);
  background: var(--gs-grey-05);
  text-transform: uppercase; font-size: 10px;
  letter-spacing: 0.08em; color: var(--gs-ink);
}
.ed-modal-body table.md-table td {
  padding: 5px 10px; border-bottom: 1px solid var(--border);
}
.ed-modal-body strong { color: var(--gs-navy); font-weight: 600; }
.ed-modal-body em { color: var(--text); }
.ed-modal-body code {
  background: var(--gs-grey-05); padding: 1px 6px;
  border-radius: 3px; font-family: ui-monospace, monospace;
  font-size: 12px;
}
.ed-modal-body a {
  color: var(--accent); text-decoration: underline;
  text-underline-offset: 2px;
}
.ed-modal-body a:hover { color: var(--gs-navy); }
.modal-detail-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.modal-detail-table th {
  text-align: left; padding: 6px 12px 6px 0; width: 42%;
  color: var(--text-faint); font-weight: 500; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.06em;
}
.modal-detail-table td {
  padding: 6px 0; color: var(--text);
  border-bottom: 1px solid var(--border);
}
.modal-detail-table tr:last-child td { border-bottom: none; }
.modal-extra {
  margin-top: 14px; padding-top: 14px;
  border-top: 1px solid var(--border); font-size: 12px;
  color: var(--text-faint);
}

/* Rich row-click detail layout (row_click.detail.sections) */
.detail-section-title {
  font-family: var(--gs-font-sans); font-size: 10px;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-faint); font-weight: 600;
  margin: 18px 0 8px;
}
.detail-section-title:first-child { margin-top: 4px; }
.detail-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 1px; background: var(--border);
  border-radius: 4px; overflow: hidden;
  margin-bottom: 6px;
}
.detail-stat {
  background: var(--surface); padding: 10px 12px;
  display: flex; flex-direction: column; gap: 2px;
}
.detail-stat-label {
  font-size: 10px; color: var(--text-faint);
  text-transform: uppercase; letter-spacing: 0.07em; font-weight: 600;
}
.detail-stat-value {
  font-family: var(--gs-font-serif); font-size: 18px;
  color: var(--gs-navy); font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.detail-stat.pos .detail-stat-value { color: var(--pos); }
.detail-stat.neg .detail-stat-value { color: var(--neg); }
.detail-stat-sub { font-size: 10px; color: var(--text-dim); }
.detail-chart {
  width: 100%; margin: 4px 0 12px;
  border: 1px solid var(--border); border-radius: 4px;
  background: var(--surface);
}
.detail-chart-empty {
  padding: 24px; text-align: center; color: var(--text-faint);
  font-size: 12px; font-style: italic;
}
.detail-markdown {
  font-size: 13px; color: var(--text); line-height: 1.55;
  margin: 4px 0 12px;
}
.detail-markdown p { margin: 0 0 8px; }
.detail-markdown ul { margin: 4px 0 8px 16px; }
.detail-markdown strong { color: var(--gs-navy); }
.detail-markdown code {
  background: var(--gs-grey-05); padding: 1px 5px;
  border-radius: 3px; font-family: ui-monospace, monospace;
  font-size: 12px;
}
.detail-markdown a {
  color: var(--accent); text-decoration: underline;
  text-underline-offset: 2px;
}
.modal-detail-table.sub th {
  font-size: 10px; padding-top: 4px;
}
.modal-detail-table.sub td {
  font-size: 12px; padding: 4px 8px 4px 0;
}

/* filter widgets extensions */
.filter-item.slider { min-width: 200px; }
.filter-item.slider .slider-row {
  display: flex; align-items: center; gap: 8px;
}
.filter-item.slider input[type="range"] { flex: 1; }
.filter-item.slider .slider-val {
  min-width: 36px; text-align: right;
  font-variant-numeric: tabular-nums; color: var(--gs-navy);
  font-weight: 600; font-size: 12px;
}
.filter-item.radio-group .radio-row {
  display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
}
.filter-item.radio-group label.radio-opt {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text); font-weight: 400;
  text-transform: none; letter-spacing: 0; cursor: pointer;
}
.filter-item.text input[type="text"],
.filter-item.number input[type="number"] {
  padding: 6px 10px; border: 1px solid var(--border);
  border-radius: 4px; font-size: 12px;
  font-family: var(--gs-font-sans);
  background: var(--surface);
  min-width: 120px;
}
.filter-item.text input[type="text"]:focus,
.filter-item.number input[type="number"]:focus {
  outline: none; border-color: var(--gs-navy);
}

/* stat_grid widget */
.stat-grid-tile .tile-body { padding: 0; }
.stat-grid-tile .stat-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px; background: var(--border);
}
.stat-grid-tile .stat-cell {
  background: var(--surface); padding: 12px 14px;
  display: flex; flex-direction: column; gap: 4px;
  cursor: default;
}
.stat-grid-tile .stat-label {
  font-size: 10px; color: var(--text-faint);
  text-transform: uppercase; letter-spacing: 0.08em; font-weight: 500;
  display: inline-flex; align-items: center; gap: 4px;
}
.stat-grid-tile .stat-info {
  font-size: 11px; color: var(--text-faint); cursor: pointer;
  text-transform: none; border-radius: 50%;
}
.stat-grid-tile .stat-info:hover { color: var(--accent);
                                     background: var(--surface-hover); }
.stat-grid-tile .stat-info:focus { outline: 2px solid var(--accent-ring);
                                     outline-offset: 2px; }
.stat-grid-tile .stat-value {
  font-size: 18px; color: var(--gs-navy); font-weight: 700;
  font-variant-numeric: tabular-nums;
  display: inline-flex; align-items: baseline; gap: 6px;
}
.stat-grid-tile .stat-trend {
  font-size: 12px;
}
.stat-grid-tile .stat-trend.pos  { color: var(--pos); }
.stat-grid-tile .stat-trend.neg  { color: var(--neg); }
.stat-grid-tile .stat-trend.flat { color: var(--text-faint); }
.stat-grid-tile .stat-sub {
  font-size: 10px; color: var(--text-faint);
}

/* image widget */
.image-tile .tile-body {
  padding: 0; display: flex; align-items: center; justify-content: center;
}
.image-tile img { max-width: 100%; max-height: 100%; display: block; }

.status { color: var(--text-faint); font-size: 11px;
          font-family: var(--gs-font-sans);
          font-variant-numeric: tabular-nums; }

footer.app-footer {
  padding: 14px 28px; border-top: 1px solid var(--border);
  background: var(--gs-grey-05); color: var(--text-faint);
  font-size: 11px; font-family: var(--gs-font-sans);
  letter-spacing: 0.02em;
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 8px;
}
footer.app-footer .gs-mark .gs-box {
  width: 22px; height: 22px; font-size: 11px;
}
footer.app-footer .gs-mark .gs-wordmark { font-size: 12px; }

/* responsive */
@media (max-width: 1024px) {
  .grid > .tile { grid-column: span 6; }
}
@media (max-width: 720px) {
  .grid > .tile { grid-column: span 12; }
  header.app-header { padding: 14px 16px; }
  nav.tab-bar { padding: 0 16px; }
  .filter-bar { padding: 10px 16px; }
  main.app-main { padding: 14px 16px; }
}

/* motion preferences */
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
</style>
</head>
<body>
<div class="app">
  <header class="app-header">
    <div class="header-titles">
      <span class="gs-mark">
        <span class="gs-box">GS</span>
        <span class="gs-wordmark">Goldman Sachs</span>
      </span>
      <h1>__TITLE__</h1>
      <div class="subtitle">__DESCRIPTION__</div>
    </div>
    <div class="header-meta">
      <span class="meta-dot" id="data-as-of" style="display:none">
        Data as of <span id="data-as-of-val"></span>
      </span>
    </div>
    <div class="header-actions" id="header-actions">
      <button class="icon-btn" id="methodology-btn"
              title="View dashboard methodology" style="display:none">
        Methodology
      </button>
      <button class="icon-btn" id="refresh-btn"
              title="Refresh dashboard data" style="display:none">
        <span id="refresh-btn-label">Refresh</span>
      </button>
      <button class="icon-btn" id="export-all"
              title="Download all charts as PNG (2x)">
        Download PNGs
      </button>
      <button class="icon-btn" id="export-dashboard"
              title="Download the entire dashboard as one PNG (full page).">
        Download Dashboard
      </button>
      <button class="icon-btn primary" id="export-excel"
              title="Download all tables as one Excel workbook"
              style="display:none">
        Download Excel
      </button>
    </div>
  </header>
  __TAB_BAR__
  __FILTER_BAR__
  __SUMMARY__
  <main class="app-main">
    __TAB_PANELS__
  </main>
  <footer class="app-footer">
    <span class="gs-mark">
      <span class="gs-box">GS</span>
      <span class="gs-wordmark">Goldman Sachs</span>
    </span>
    <span class="status">
      echart_dashboard v__VERSION__ &middot; ECharts@5 &middot; __TIMESTAMP__
    </span>
  </footer>
</div>
<script>
__PAYLOAD__
__APP__
</script>
</body>
</html>
"""


DASHBOARD_APP_JS = r"""
(function(){
  'use strict';
  var MANIFEST = PAYLOAD.manifest;
  var SPECS    = PAYLOAD.specs;       // id -> ECharts option dict
  var DATASETS = PAYLOAD.datasets;    // name -> {source: [...rows]}

  // Revive string-encoded JS functions (renderItem, formatter, filter)
  // into real functions. Python emits them as strings because JSON cannot
  // carry code; ECharts needs real functions at setOption() time.
  function _isFnStr(s) {
    return typeof s === 'string' && /^\s*function\s*\(/.test(s);
  }
  function reviveFns(x) {
    if (x == null) return x;
    if (_isFnStr(x)) {
      try { return new Function('return (' + x + ')')(); }
      catch(e) { return x; }
    }
    if (Array.isArray(x)) {
      for (var i = 0; i < x.length; i++) x[i] = reviveFns(x[i]);
      return x;
    }
    if (typeof x === 'object') {
      for (var k in x) {
        if (Object.prototype.hasOwnProperty.call(x, k)) {
          x[k] = reviveFns(x[k]);
        }
      }
    }
    return x;
  }

  // register themes so echarts can use them
  try {
    Object.keys(PAYLOAD.themes || {}).forEach(function(tn){
      try { echarts.registerTheme(tn, PAYLOAD.themes[tn]); } catch(e){}
    });
  } catch(e){}

  // ----- filter state + event bus -----
  var filterState = {};
  (MANIFEST.filters || []).forEach(function(f){
    filterState[f.id] = f.default != null ? f.default :
                          (f.type === 'multiSelect' ? [] : '');
  });
  var listeners = {}; // filterId -> [chartId, ...]

  function subscribe(chartId, filterIds){
    filterIds.forEach(function(fid){
      listeners[fid] = listeners[fid] || [];
      if (listeners[fid].indexOf(chartId) < 0) listeners[fid].push(chartId);
    });
  }
  function broadcast(filterId){
    (listeners[filterId] || []).forEach(rerenderChart);
    renderKpis();
    renderTables();
  }

  // ----- dataset management -----
  var currentDatasets = {};
  Object.keys(DATASETS || {}).forEach(function(name){
    currentDatasets[name] = JSON.parse(JSON.stringify(DATASETS[name].source || DATASETS[name]));
  });
  function resetDataset(name){
    var src = (DATASETS[name] && DATASETS[name].source) || DATASETS[name];
    currentDatasets[name] = JSON.parse(JSON.stringify(src));
  }

  // ----- widget meta registry -----
  var WIDGET_META = {};
  function collectWidgets(){
    function visit(rows){
      rows.forEach(function(row){ row.forEach(function(w){
        if (w.id) WIDGET_META[w.id] = w;
      }); });
    }
    var layout = MANIFEST.layout || {};
    if (layout.kind === 'tabs'){
      (layout.tabs || []).forEach(function(t){ visit(t.rows || []); });
    } else {
      visit(layout.rows || []);
    }
  }
  collectWidgets();

  function targetMatch(target, id){
    if (target === '*') return true;
    if (target.indexOf('*') < 0) return target === id;
    var rx = new RegExp('^' + target.replace(/\*/g,'.*') + '$');
    return rx.test(id);
  }
  function filtersForChart(chartId){
    var out = [];
    (MANIFEST.filters || []).forEach(function(f){
      if ((f.targets || []).some(function(t){ return targetMatch(t, chartId); })){
        out.push(f.id);
      }
    });
    return out;
  }

  // ----- apply global filters to a dataset -----
  function resolveDateRange(val){
    var now = Date.now();
    if (typeof val === 'string'){
      var m = val.match(/^(\d+)([DWMY])$/);
      if (m){
        var n = parseInt(m[1]);
        var ms = {D:86400e3, W:7*86400e3, M:30*86400e3, Y:365*86400e3}[m[2]];
        return [now - n*ms, now];
      }
      if (val === 'YTD'){
        var jan1 = new Date(new Date().getFullYear(), 0, 1).getTime();
        return [jan1, now];
      }
      if (val === 'All') return [0, now];
    }
    if (Array.isArray(val) && val.length === 2){
      return [Date.parse(val[0]), Date.parse(val[1])];
    }
    return [0, now];
  }

  // Generic cell-vs-value comparator used by slider/number/text + conditional
  // formatting rules on tables. op defaults to '==' (equality).
  function cmpOp(op, cell, val){
    if (cell == null) return false;
    if (op == null) op = '==';
    if (op === 'contains')   return String(cell).toLowerCase().indexOf(String(val).toLowerCase()) >= 0;
    if (op === 'startsWith') return String(cell).toLowerCase().indexOf(String(val).toLowerCase()) === 0;
    if (op === 'endsWith')   return String(cell).toLowerCase().lastIndexOf(String(val).toLowerCase()) === String(cell).length - String(val).length;
    var a = +cell, b = +val;
    if (isNaN(a) || isNaN(b)) {
      if (op === '==' ) return String(cell) === String(val);
      if (op === '!=' ) return String(cell) !== String(val);
      return false;
    }
    if (op === '==') return a === b;
    if (op === '!=') return a !== b;
    if (op === '>' ) return a >  b;
    if (op === '>=') return a >= b;
    if (op === '<' ) return a <  b;
    if (op === '<=') return a <= b;
    return false;
  }

  function applyFilters(name, rows){
    var header = rows[0]; var body = rows.slice(1); var out = body;
    (MANIFEST.filters || []).forEach(function(f){
      var val = filterState[f.id];
      if (val === '' || val == null || (Array.isArray(val) && val.length === 0)) return;
      // Escape-hatch: if the filter declares `all_value` and the current
      // value matches it, treat this filter as a no-op. Lets radio/select
      // filters have an explicit "All / Any / None" option without having
      // to invent a null sentinel.
      if (f.all_value != null && String(val) === String(f.all_value)) return;
      var idx = f.field != null ? header.indexOf(f.field) : -1;
      if (f.type === 'dateRange'){
        if (idx < 0) idx = 0;
        var r = resolveDateRange(val);
        out = out.filter(function(row){
          var c = row[idx]; if (c == null) return false;
          var d = (typeof c === 'string') ? Date.parse(c) : +c;
          if (isNaN(d)) return true;
          return d >= r[0] && d <= r[1];
        });
      } else if ((f.type === 'select' || f.type === 'radio') && idx >= 0){
        out = out.filter(function(row){ return String(row[idx]) === String(val); });
      } else if (f.type === 'multiSelect' && idx >= 0){
        out = out.filter(function(row){ return val.indexOf(String(row[idx])) >= 0; });
      } else if (f.type === 'numberRange' && idx >= 0){
        var lo = val[0], hi = val[1];
        out = out.filter(function(row){ var n = +row[idx]; return !isNaN(n) && n>=lo && n<=hi; });
      } else if (f.type === 'toggle' && idx >= 0){
        if (val) out = out.filter(function(row){ return !!row[idx]; });
      } else if ((f.type === 'slider' || f.type === 'number' || f.type === 'text')
                   && idx >= 0){
        var op = f.op || (f.type === 'text' ? 'contains' : '>=');
        var transform = f.transform; // optional 'abs' | 'neg'
        out = out.filter(function(row){
          var cell = row[idx];
          if (transform === 'abs' && cell != null) cell = Math.abs(+cell);
          else if (transform === 'neg' && cell != null) cell = -(+cell);
          return cmpOp(op, cell, val);
        });
      }
    });
    return [header].concat(out);
  }

  // ----- rewire a chart spec to use a shared dataset -----
  //
  // The widget was auto-wired by _augment_manifest ONLY when the chart
  // type + mapping is in the known-safe rewire set (see
  // _is_safe_for_rewire in echart_dashboard.py). That means we can
  // assume a wide-form dataset whose columns include the x col and
  // each series' y col (indexed by `s.name`). We match series to
  // columns by name first, falling back to positional index, so extra
  // trailing columns in the dataset don't shift the mapping.
  function materializeOption(cid){
    var w = WIDGET_META[cid]; var base = SPECS[cid];
    var opt = JSON.parse(JSON.stringify(base));
    if (!(w && w.dataset_ref && currentDatasets[w.dataset_ref])) return opt;
    var filt = applyFilters(w.dataset_ref, currentDatasets[w.dataset_ref]);
    opt.dataset = {source: filt};
    var header = filt[0] || [];
    (opt.series || []).forEach(function(s, i){
      var t = s.type;
      var isRewireable = (t === 'line' || t === 'bar'
                          || t === 'scatter' || t === 'area');
      if (!isRewireable) return;
      if (s.encode) return;                // already fully specified
      // Resolve the y dataset column. Priority:
      //   1. `_column` hint set at build time (raw, pre-humanise col)
      //   2. exact match of series name against header
      //   3. positional index (x is col 0, series i -> col i+1)
      var yIdx = -1;
      if (s._column && header.indexOf(s._column) >= 0) {
        yIdx = header.indexOf(s._column);
      } else if (s.name && header.indexOf(s.name) >= 0) {
        yIdx = header.indexOf(s.name);
      } else {
        yIdx = Math.min(1 + i, header.length - 1);
      }
      if (yIdx <= 0) yIdx = Math.min(1, header.length - 1);
      s.encode = {x: header[0], y: header[yIdx]};
      s.name = s.name || header[yIdx];
      delete s.data;
    });
    return opt;
  }

  // ----- chart init/render -----
  var CHARTS = {};

  function chartThemeName(){
    // Use the manifest theme regardless of dark/light dashboard surface.
    // Dashboard chrome and chart styling are decoupled by design.
    return MANIFEST.theme || 'gs_clean';
  }

  function initChart(cid){
    var el = document.getElementById('chart-' + cid); if (!el) return;
    if (CHARTS[cid]) return;
    var theme = chartThemeName();
    var inst = echarts.init(el, theme in PAYLOAD.themes ? theme : null);
    CHARTS[cid] = {inst: inst, datasetRef: WIDGET_META[cid].dataset_ref};
    inst.setOption(reviveFns(materializeOption(cid)), true);
    subscribe(cid, filtersForChart(cid));
    wireBrush(cid, inst);
    wireChartClick(cid, inst);
    wireChartClickPopup(cid, inst);
  }

  // ----- chart click -> filter emit -----
  //
  // If a widget declares `click_emit_filter`, clicking any data point
  // in the chart writes a value to the named filter and broadcasts so
  // all downstream widgets react. The config can be either a simple
  // filter id string, or an object:
  //   { filter_id: "region",            (required)
  //     value_from: "name" | "value" |  (default "name")
  //                 "seriesName",
  //     toggle: true }                  (default true; clicking the
  //                                       same value again clears it)
  // Pairs well with a `radio` or `select` filter whose `options`
  // include an `all_value`, so the user can reset via the reset btn
  // or by re-clicking the same point.
  function wireChartClick(cid, inst){
    var w = WIDGET_META[cid] || {};
    var cfg = w.click_emit_filter;
    if (!cfg) return;
    if (typeof cfg === 'string') cfg = {filter_id: cfg};
    if (!cfg.filter_id) return;
    var src = cfg.value_from || 'name';
    var toggle = cfg.toggle !== false;
    inst.on('click', function(params){
      var v = (src === 'value') ? params.value
            : (src === 'seriesName') ? params.seriesName
            : params.name;
      if (v == null) return;
      if (toggle && filterState[cfg.filter_id] === v){
        var f = (MANIFEST.filters || []).find(function(x){
          return x.id === cfg.filter_id;
        });
        filterState[cfg.filter_id] = (f && f.default != null)
          ? f.default
          : (f && f.type === 'multiSelect' ? [] : '');
      } else {
        filterState[cfg.filter_id] = v;
      }
      // Sync the control DOM (so the user sees it change too)
      try {
        var el = document.getElementById('filter-' + cfg.filter_id);
        if (el) {
          if (el.type === 'checkbox') el.checked = !!filterState[cfg.filter_id];
          else el.value = filterState[cfg.filter_id] == null
            ? '' : filterState[cfg.filter_id];
        } else {
          var radios = document.querySelectorAll('input[name="filter-' + cfg.filter_id + '"]');
          Array.prototype.forEach.call(radios, function(r){
            r.checked = (r.value === String(filterState[cfg.filter_id]));
          });
        }
      } catch (e) {}
      broadcast(cfg.filter_id);
    });
  }

  // ----- chart click -> detail popup -----
  //
  // If a chart widget declares `click_popup`, clicking any data point
  // resolves the corresponding row in the chart's dataset and opens
  // a modal with that row's details. Same configuration grammar as
  // table `row_click` -- simple `popup_fields` mode OR rich
  // `detail.sections[]` mode (stats / markdown / chart / table).
  //
  // The row resolver maps ECharts click params -> dataset row across
  // chart types:
  //   line / area / multi_line / bar / scatter / candlestick / bullet
  //                            (no color)  -> rows[params.dataIndex]
  //                            (color set) -> filter color==seriesName,
  //                                             then dataIndex-th row
  //   scatter_multi                        -> grouped fallback (color)
  //   pie / donut / funnel / treemap /
  //   sunburst                             -> match category col ==
  //                                             params.name
  //   heatmap                              -> match (x_cat, y_cat)
  //                                             from params.value[0..1]
  //   calendar_heatmap                      -> match date col ==
  //                                              params.value[0]
  //   histogram / radar / gauge / sankey /
  //   graph / tree / parallel_coords /
  //   boxplot                              -> not row-resolvable;
  //                                              click is a no-op
  //
  // For grouped charts (mapping.color set), series names are
  // humanised by post-build polish but the raw column value is
  // preserved on `series._column`. We read that off the live ECharts
  // option so a humanised legend label like "Investment Grade" still
  // matches a raw cell value of "Investment Grade" (or its
  // pre-humanise form).
  function wireChartClickPopup(cid, inst){
    var w = WIDGET_META[cid] || {};
    var cp = w.click_popup;
    if (!cp || typeof cp !== 'object') return;
    var spec = w.spec || {};
    var dsName = w.dataset_ref || spec.dataset;
    if (!dsName) return;
    var ds = (DATASETS[dsName] && DATASETS[dsName].source) || DATASETS[dsName];
    if (!Array.isArray(ds) || ds.length < 2) return;
    inst.on('click', function(params){
      if (!params || params.componentType !== 'series') return;
      // When the chart is rewireable, currentDatasets holds the
      // filter-stripped view that matches what's painted on screen;
      // otherwise the original DATASETS entry is what we have.
      var liveDs = currentDatasets[dsName] || ds;
      var filtered = w.dataset_ref
        ? applyFilters(w.dataset_ref, liveDs)
        : liveDs;
      var header = filtered[0];
      var rows = filtered.slice(1);
      var row = _resolveClickRow(w, params, inst, header, rows);
      if (!row) return;
      _openPopupModal(cp, header, row, null);
    });
  }

  function _resolveClickRow(w, params, inst, header, rows){
    var spec = w.spec || {};
    var ct = String(spec.chart_type || '').toLowerCase();
    var mapping = spec.mapping || {};

    // Aggregate / non-row chart types: histogram bins, radar/gauge
    // summaries, sankey/graph topology, derived structures. No row
    // identity to resolve.
    if (ct === 'histogram' || ct === 'radar' || ct === 'gauge'
        || ct === 'sankey' || ct === 'graph' || ct === 'tree'
        || ct === 'parallel_coords' || ct === 'boxplot') {
      return null;
    }

    // Category-keyed shapes: match by category cell == params.name.
    if (ct === 'pie' || ct === 'donut' || ct === 'funnel'
        || ct === 'treemap' || ct === 'sunburst') {
      var catCol = mapping.category || mapping.name;
      if (!catCol) return null;
      var ci = header.indexOf(catCol);
      if (ci < 0 || params.name == null) return null;
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i][ci]) === String(params.name)) return rows[i];
      }
      return null;
    }

    // Heatmap: ECharts emits params.value = [xIdx, yIdx, val] using
    // the same unique-ordered category lists the Python builder
    // produced. Reconstruct those lists from the dataset and match
    // back to the (x_cat, y_cat) row.
    if (ct === 'heatmap') {
      if (!Array.isArray(params.value)) return null;
      var xCol = mapping.x, yCol = mapping.y;
      var xi = header.indexOf(xCol), yi = header.indexOf(yCol);
      if (xi < 0 || yi < 0) return null;
      var xCats = [], yCats = [], seenX = {}, seenY = {};
      for (var i = 0; i < rows.length; i++) {
        var rxk = String(rows[i][xi]);
        var ryk = String(rows[i][yi]);
        if (!seenX[rxk]) { seenX[rxk] = 1; xCats.push(rows[i][xi]); }
        if (!seenY[ryk]) { seenY[ryk] = 1; yCats.push(rows[i][yi]); }
      }
      var xv = xCats[params.value[0]];
      var yv = yCats[params.value[1]];
      if (xv == null || yv == null) return null;
      for (var j = 0; j < rows.length; j++) {
        if (String(rows[j][xi]) === String(xv)
            && String(rows[j][yi]) === String(yv)) return rows[j];
      }
      return null;
    }

    if (ct === 'calendar_heatmap') {
      if (!Array.isArray(params.value)) return null;
      var dCol = mapping.date;
      var di = header.indexOf(dCol);
      if (di < 0) return null;
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i][di]) === String(params.value[0])) return rows[i];
      }
      return null;
    }

    // Default path: line / area / multi_line / bar / bar_horizontal /
    // scatter / scatter_multi / candlestick / bullet. dataIndex is
    // the position within the (color-grouped) series, so when a
    // color column is set we filter the dataset by series name first.
    var colorCol = mapping.color || mapping.colour;
    if (colorCol) {
      var cci = header.indexOf(colorCol);
      if (cci < 0) return null;
      var rawSeries = null;
      try {
        var opt = inst.getOption();
        var sArr = opt.series || [];
        var s = sArr[params.seriesIndex] || {};
        rawSeries = s._column || s.name || params.seriesName;
      } catch(e){ rawSeries = params.seriesName; }
      if (rawSeries == null) return null;
      var sub = [];
      for (var i = 0; i < rows.length; i++) {
        if (String(rows[i][cci]) === String(rawSeries)) sub.push(rows[i]);
      }
      var didx = params.dataIndex == null ? 0 : params.dataIndex;
      return sub[didx] || null;
    }
    if (params.dataIndex == null) return null;
    return rows[params.dataIndex] || null;
  }
  function rerenderChart(cid){
    var rec = CHARTS[cid]; if (!rec) return;
    rec.inst.setOption(reviveFns(materializeOption(cid)), true);
  }

  // ----- brush cross-filter -----
  function wireBrush(cid, inst){
    var link = (MANIFEST.links || []).find(function(l){
      return l.brush && (l.members || []).some(function(m){ return targetMatch(m, cid); });
    });
    if (!link) return;
    inst.on('brushSelected', function(params){
      var sel = (params.batch && params.batch[0]) || {};
      applyBrush(cid, link, sel.areas || []);
    });
  }
  function applyBrush(cid, link, areas){
    var members = (link.members || []).flatMap(function(p){
      return Object.keys(WIDGET_META).filter(function(k){
        return targetMatch(p, k) && WIDGET_META[k].widget === 'chart';
      });
    });
    if (!areas.length){
      members.forEach(function(m){
        if (m === cid) return;
        var rec = CHARTS[m]; if (!rec || !rec.datasetRef) return;
        resetDataset(rec.datasetRef); rerenderChart(m);
      });
      return;
    }
    var xMin, xMax;
    areas.forEach(function(a){
      if (a.coordRange && a.coordRange.length >= 2){
        var cr = a.coordRange;
        var xr = Array.isArray(cr[0]) ? cr[0] : cr;
        if (xMin == null) xMin = xr[0]; else xMin = Math.min(xMin, xr[0]);
        if (xMax == null) xMax = xr[1]; else xMax = Math.max(xMax, xr[1]);
      }
    });
    members.forEach(function(m){
      if (m === cid) return;
      var rec = CHARTS[m]; if (!rec || !rec.datasetRef) return;
      var ds = DATASETS[rec.datasetRef]; if (!ds) return;
      var src = ds.source || ds;
      var header = src[0]; var body = src.slice(1);
      var filt = body.filter(function(r){
        var v = r[0]; var d = (typeof v === 'string') ? Date.parse(v) : +v;
        if (isNaN(d)) return true;
        return d >= xMin && d <= xMax;
      });
      currentDatasets[rec.datasetRef] = [header].concat(filt);
      rerenderChart(m);
    });
  }

  function applyConnects(){
    (MANIFEST.links || []).forEach(function(lk){
      if (!lk.sync) return;
      var group = lk.group;
      var members = (lk.members || []).flatMap(function(p){
        return Object.keys(CHARTS).filter(function(k){ return targetMatch(p, k); });
      });
      members.map(function(m){ return CHARTS[m] && CHARTS[m].inst; })
              .filter(Boolean).forEach(function(i){ i.group = group; });
      try { echarts.connect(group); } catch(e){}
    });
  }

  // ----- tabs -----
  function activateTab(tabId){
    document.querySelectorAll('.tab-btn').forEach(function(b){
      b.classList.toggle('active', b.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-panel').forEach(function(p){
      p.classList.toggle('active', p.id === 'tab-panel-' + tabId);
    });
    // lazy-init any chart tiles in the newly active tab
    var panel = document.getElementById('tab-panel-' + tabId);
    if (panel){
      panel.querySelectorAll('.chart-div').forEach(function(div){
        var id = (div.id || '').replace(/^chart-/, '');
        if (id && !CHARTS[id]) initChart(id);
        else if (id && CHARTS[id]){
          try { CHARTS[id].inst.resize(); } catch(e){}
        }
      });
      applyConnects();
    }
    try { localStorage.setItem('echart_dashboard_tab_' + MANIFEST.id, tabId); } catch(e){}
  }

  document.querySelectorAll('.tab-btn').forEach(function(b){
    b.addEventListener('click', function(){ activateTab(b.dataset.tab); });
  });

  // ----- filter wiring -----
  function wireFilters(){
    (MANIFEST.filters || []).forEach(function(f){
      // Radio groups have no single DOM node for the filter itself --
      // there are N radio inputs sharing a common name. Everything
      // else is addressable by id.
      if (f.type === 'radio'){
        var inputs = document.querySelectorAll(
          'input[name="filter-' + f.id + '"]');
        if (!inputs.length) return;
        Array.prototype.forEach.call(inputs, function(r){
          r.addEventListener('change', function(){
            if (r.checked){
              filterState[f.id] = r.value;
              broadcast(f.id);
            }
          });
        });
        return;
      }
      var el = document.getElementById('filter-' + f.id); if (!el) return;
      if (f.type === 'multiSelect'){
        el.addEventListener('change', function(){
          filterState[f.id] = Array.from(el.selectedOptions).map(function(o){ return o.value; });
          broadcast(f.id);
        });
      } else if (f.type === 'toggle'){
        el.addEventListener('change', function(){ filterState[f.id] = el.checked; broadcast(f.id); });
      } else if (f.type === 'numberRange'){
        el.addEventListener('change', function(){
          var parts = el.value.split(',').map(function(s){ return Number(s.trim()); });
          if (parts.length === 2){ filterState[f.id] = parts; broadcast(f.id); }
        });
      } else if (f.type === 'slider'){
        var display = document.getElementById('filter-' + f.id + '-val');
        el.addEventListener('input', function(){
          var n = Number(el.value);
          filterState[f.id] = n;
          if (display) display.textContent = n;
        });
        el.addEventListener('change', function(){ broadcast(f.id); });
      } else if (f.type === 'number'){
        el.addEventListener('change', function(){
          var n = Number(el.value);
          filterState[f.id] = isNaN(n) ? '' : n;
          broadcast(f.id);
        });
      } else if (f.type === 'text'){
        // Debounce text input so broadcasts aren't firing per keystroke.
        var tId = null;
        el.addEventListener('input', function(){
          filterState[f.id] = el.value;
          if (tId) clearTimeout(tId);
          tId = setTimeout(function(){ broadcast(f.id); }, 180);
        });
      } else {
        // dateRange / select / date / default text -- all of these
        // use the native `change` event on the <select> or <input>.
        el.addEventListener('change', function(){
          filterState[f.id] = el.value; broadcast(f.id);
        });
      }
    });
    // Wire every reset button: both the global `#filter-reset` and any
    // per-tab inline reset buttons (marked with `data-filter-reset`).
    // An inline reset resets only the filters whose scope matches its
    // containing tab panel. Global reset clears everything.
    function resetFilters(targetsToReset){
      (MANIFEST.filters || []).forEach(function(f){
        if (targetsToReset && targetsToReset.indexOf(f.id) < 0) return;
        filterState[f.id] = f.default != null ? f.default :
                            (f.type === 'multiSelect' ? [] : '');
        if (f.type === 'radio'){
          var inputs = document.querySelectorAll('input[name="filter-' + f.id + '"]');
          Array.prototype.forEach.call(inputs, function(r){
            r.checked = r.value === String(filterState[f.id]);
          });
          return;
        }
        var el = document.getElementById('filter-' + f.id);
        if (!el) return;
        if (f.type === 'toggle') el.checked = !!filterState[f.id];
        else if (f.type === 'multiSelect')
          Array.from(el.options).forEach(function(o){ o.selected = (filterState[f.id] || []).indexOf(o.value) >= 0; });
        else if (f.type === 'slider'){
          el.value = filterState[f.id];
          var display = document.getElementById('filter-' + f.id + '-val');
          if (display) display.textContent = filterState[f.id];
        }
        else el.value = filterState[f.id] == null ? '' : filterState[f.id];
      });
      Object.keys(currentDatasets).forEach(resetDataset);
      Object.keys(CHARTS).forEach(rerenderChart);
      renderKpis(); renderTables();
    }

    document.querySelectorAll('[data-filter-reset]').forEach(function(btn){
      btn.addEventListener('click', function(){
        var panel = btn.closest('.tab-panel');
        var scopedIds = null;
        if (panel && btn.classList.contains('filter-reset') &&
            panel.classList.contains('tab-panel') && btn.closest('.tab-filter-bar')){
          var pid = (panel.id || '').replace(/^tab-panel-/, '');
          scopedIds = (MANIFEST.filters || [])
            .filter(function(f){ return String(f.scope || '') === 'tab:' + pid; })
            .map(function(f){ return f.id; });
        }
        resetFilters(scopedIds);
      });
    });
  }

  // ----- KPI widgets -----
  //
  // Default behavior: use comma-grouped digits for numbers < 1M
  // (so 2820 -> "2,820" not "3K"); compact K / M / B / T suffix only
  // kicks in at >= 1M. Callers can override via `format`:
  //    "compact"  -> always K/M/B/T abbreviation
  //    "comma"    -> always full digits w/ commas, no abbreviation
  //    "percent"  -> multiply by 100 + "%" suffix
  //    "raw"      -> Number(v).toString() no grouping
  // `decimals` controls fractional digits (defaults vary by magnitude).
  function _commaGroup(intStr){
    // insert thousands separators on the integer portion
    return intStr.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function formatNumber(v, opts){
    opts = opts || {};
    if (v == null || isNaN(+v)) return String(v);
    var n = +v;
    var prefix = opts.prefix || '';
    var suffix = opts.suffix || '';
    var mode = opts.format || 'auto';
    var abs = Math.abs(n);
    var d = opts.decimals;
    function _apply(formatted){ return prefix + formatted + suffix; }
    if (mode === 'raw'){
      return _apply(String(n));
    }
    if (mode === 'percent'){
      if (d == null) d = 2;
      return _apply((n * 100).toFixed(d) + '%');
    }
    if (mode === 'comma'){
      if (d == null) d = (abs >= 1000 ? 0 : 2);
      var parts = n.toFixed(d).split('.');
      parts[0] = _commaGroup(parts[0]);
      return _apply(parts.join('.'));
    }
    if (mode === 'compact'){
      if (d == null) d = 1;
      var f;
      if (abs >= 1e12) f = (n/1e12).toFixed(d) + 'T';
      else if (abs >= 1e9)  f = (n/1e9).toFixed(d) + 'B';
      else if (abs >= 1e6)  f = (n/1e6).toFixed(d) + 'M';
      else if (abs >= 1e3)  f = (n/1e3).toFixed(d) + 'K';
      else                   f = n.toFixed(d);
      return _apply(f);
    }
    // auto: commas below 1M, compact above
    if (abs >= 1e12) { if (d == null) d = 1;
      return _apply((n/1e12).toFixed(d) + 'T'); }
    if (abs >= 1e9)  { if (d == null) d = 1;
      return _apply((n/1e9).toFixed(d) + 'B'); }
    if (abs >= 1e6)  { if (d == null) d = 1;
      return _apply((n/1e6).toFixed(d) + 'M'); }
    if (d == null) d = (abs >= 1000 ? 0 : 2);
    var parts2 = n.toFixed(d).split('.');
    parts2[0] = _commaGroup(parts2[0]);
    return _apply(parts2.join('.'));
  }

  function resolveAgg(src, agg, col){
    var ds = currentDatasets[src]; if (!ds) return null;
    var header = ds[0]; var idx = header.indexOf(col);
    if (idx < 0) return null;
    var vals = ds.slice(1).map(function(r){ return r[idx]; })
                .filter(function(v){ return typeof v === 'number'; });
    if (!vals.length) return null;
    if (agg === 'latest') return vals[vals.length - 1];
    if (agg === 'first')  return vals[0];
    if (agg === 'sum')    return vals.reduce(function(a,b){ return a+b; }, 0);
    if (agg === 'mean')   return vals.reduce(function(a,b){ return a+b; }, 0) / vals.length;
    if (agg === 'min')    return Math.min.apply(null, vals);
    if (agg === 'max')    return Math.max.apply(null, vals);
    if (agg === 'count')  return vals.length;
    if (agg === 'prev'){
      return vals.length >= 2 ? vals[vals.length - 2] : vals[vals.length - 1];
    }
    return null;
  }
  function resolveSource(src){
    if (!src) return null;
    var parts = String(src).split('.');
    if (parts.length < 3) return null;
    return resolveAgg(parts[0], parts[1], parts.slice(2).join('.'));
  }

  function renderKpis(){
    Object.keys(WIDGET_META).forEach(function(id){
      var w = WIDGET_META[id]; if (w.widget !== 'kpi') return;
      var el = document.getElementById('kpi-' + id); if (!el) return;
      var value = w.value != null ? w.value : resolveSource(w.source);
      var formatted;
      if (typeof value === 'number'){
        formatted = formatNumber(value, {
          decimals: w.decimals, format: w.format,
          prefix: w.prefix || '', suffix: w.suffix || ''
        });
      } else {
        formatted = value == null ? '--' : String(value);
      }
      var vNode = el.querySelector('.kpi-value');
      if (vNode) vNode.textContent = formatted;

      // delta: {delta: 1.2, delta_pct: 4.5, delta_label: 'vs prev'}
      // or automatic if delta_source points to prev aggregator
      var dNode = el.querySelector('.kpi-delta');
      if (dNode){
        var deltaVal = w.delta;
        var deltaSrc = w.delta_source;
        var pct = w.delta_pct;
        if (deltaVal == null && deltaSrc){
          var cur = (typeof value === 'number') ? value : resolveSource(w.source);
          var prev = resolveSource(deltaSrc);
          if (typeof cur === 'number' && typeof prev === 'number'){
            deltaVal = cur - prev;
            pct = prev !== 0 ? (deltaVal / Math.abs(prev)) * 100 : null;
          }
        }
        if (deltaVal != null){
          dNode.classList.remove('pos','neg','flat');
          var sign = deltaVal > 0 ? 'pos' : (deltaVal < 0 ? 'neg' : 'flat');
          dNode.classList.add(sign);
          var arrow = deltaVal > 0 ? '\u25B2' : (deltaVal < 0 ? '\u25BC' : '\u25B6');
          var txt = arrow + ' ' + formatNumber(Math.abs(deltaVal), {decimals: w.delta_decimals || 2});
          if (pct != null && !isNaN(pct)) txt += ' (' + (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%)';
          if (w.delta_label) txt += ' ' + w.delta_label;
          dNode.textContent = txt;
          dNode.style.display = 'inline-flex';
        } else {
          dNode.style.display = 'none';
        }
      }

      // sparkline
      var sNode = el.querySelector('.kpi-sparkline');
      if (sNode && w.sparkline_source){
        var sp = String(w.sparkline_source).split('.');
        if (sp.length >= 2){
          var dsName = sp[0], col = sp.slice(1).join('.');
          var ds = currentDatasets[dsName];
          if (ds){
            var header = ds[0]; var idx = header.indexOf(col);
            var rows = ds.slice(1);
            if (idx >= 0){
              var data = rows.map(function(r){ return r[idx]; });
              if (!sNode._inst){
                sNode._inst = echarts.init(sNode);
              }
              sNode._inst.setOption({
                grid:{top:2,bottom:2,left:2,right:2,containLabel:false},
                xAxis:{type:'category',show:false,data:data.map(function(_,i){return i;})},
                yAxis:{type:'value',show:false,scale:true},
                tooltip:{show:false},
                animation:false,
                series:[{type:'line',data:data,symbol:'none',
                          smooth:true,lineStyle:{width:1.6},
                          areaStyle:{opacity:0.18}}]
              }, true);
            }
          }
        }
      }
    });
  }

  // ----- table widgets -----
  // Column formatters. Token is the prefix before ':' in the format string;
  // the suffix (if any) is decimals / precision.
  function formatValue(v, fmt){
    if (v == null || v === '') return '';
    if (fmt == null || fmt === 'text') return String(v);
    var parts = String(fmt).split(':');
    var kind = parts[0];
    var prec = parts.length > 1 ? Number(parts[1]) : 2;
    var n = Number(v);
    if (kind === 'integer') {
      if (isNaN(n)) return String(v);
      return Math.round(n).toLocaleString();
    }
    if (kind === 'number')  {
      if (isNaN(n)) return String(v);
      return n.toLocaleString(undefined, {minimumFractionDigits: prec,
                                             maximumFractionDigits: prec});
    }
    if (kind === 'percent') {
      if (isNaN(n)) return String(v);
      // Accept both fractional (0.12) and percent (12) forms
      var pct = Math.abs(n) <= 1 ? n * 100 : n;
      return pct.toFixed(isNaN(prec) ? 1 : prec) + '%';
    }
    if (kind === 'currency') {
      if (isNaN(n)) return String(v);
      return '$' + n.toLocaleString(undefined, {minimumFractionDigits: prec,
                                                     maximumFractionDigits: prec});
    }
    if (kind === 'bps') {
      if (isNaN(n)) return String(v);
      return n.toFixed(isNaN(prec) ? 0 : prec) + 'bp';
    }
    if (kind === 'signed') {
      if (isNaN(n)) return String(v);
      var sign = n > 0 ? '+' : '';
      return sign + n.toFixed(isNaN(prec) ? 2 : prec);
    }
    if (kind === 'delta') {
      if (isNaN(n)) return String(v);
      var arrow = n > 0 ? '\u25B2' : n < 0 ? '\u25BC' : '\u25AC';
      return arrow + ' ' + Math.abs(n).toFixed(isNaN(prec) ? 2 : prec);
    }
    if (kind === 'date') {
      var d = new Date(v);
      if (!isNaN(d.getTime())) return d.toISOString().slice(0, 10);
      return String(v);
    }
    if (kind === 'datetime') {
      var dt = new Date(v);
      if (!isNaN(dt.getTime())) return dt.toISOString().replace('T', ' ').slice(0, 19);
      return String(v);
    }
    if (kind === 'link') {
      var safe = String(v).replace(/"/g, '&quot;');
      return '<a href="' + safe + '" target="_blank">open</a>';
    }
    return String(v);
  }

  function _lerp(a, b, t){ return a + (b - a) * t; }
  function _hex2rgb(hex){
    hex = hex.replace('#', '');
    if (hex.length === 3) hex = hex.split('').map(function(c){ return c+c; }).join('');
    return [parseInt(hex.substr(0,2),16), parseInt(hex.substr(2,2),16), parseInt(hex.substr(4,2),16)];
  }
  function _rgb2hex(r, g, b){
    function hx(x){ return ('0' + Math.round(x).toString(16)).slice(-2); }
    return '#' + hx(r) + hx(g) + hx(b);
  }
  function interpolatePalette(stops, t){
    if (!stops || !stops.length) return null;
    if (stops.length === 1) return stops[0];
    var n = stops.length - 1;
    var pos = Math.max(0, Math.min(1, t)) * n;
    var lo = Math.floor(pos), hi = Math.min(n, lo + 1);
    var frac = pos - lo;
    var a = _hex2rgb(stops[lo]), b = _hex2rgb(stops[hi]);
    return _rgb2hex(_lerp(a[0], b[0], frac), _lerp(a[1], b[1], frac), _lerp(a[2], b[2], frac));
  }
  function colorForScale(v, scale){
    var n = Number(v);
    if (isNaN(n) || !scale) return null;
    var pal = PAYLOAD.palettes[scale.palette];
    if (!pal) return null;
    var lo = scale.min != null ? scale.min : 0;
    var hi = scale.max != null ? scale.max : 1;
    var span = hi - lo || 1;
    var t = (n - lo) / span;
    return interpolatePalette(pal.colors, t);
  }
  function conditionalStyle(v, rules){
    if (!rules) return null;
    for (var i = 0; i < rules.length; i++){
      var r = rules[i];
      if (cmpOp(r.op || '==', v, r.value)){
        return r;
      }
    }
    return null;
  }
  // Table per-widget state: sort column index (null = original order),
  // sort direction (1 = asc, -1 = desc), search string.
  var TABLE_STATE = {};
  function tableState(id){
    if (!TABLE_STATE[id]){
      TABLE_STATE[id] = {sortCol: null, sortDir: 1, search: ''};
    }
    return TABLE_STATE[id];
  }

  function _rowMatchesSearch(row, needle){
    if (!needle) return true;
    var n = String(needle).toLowerCase();
    for (var i = 0; i < row.length; i++){
      var c = row[i]; if (c == null) continue;
      if (String(c).toLowerCase().indexOf(n) >= 0) return true;
    }
    return false;
  }

  function renderTables(){
    Object.keys(WIDGET_META).forEach(function(id){
      var w = WIDGET_META[id]; if (w.widget !== 'table') return;
      var el = document.getElementById('table-' + id); if (!el) return;

      // The whole table is rebuilt via innerHTML below, which destroys
      // the search <input> and any focus/selection on it. Capture caret
      // state up-front so we can restore it after the rebuild and the
      // user can keep typing without their cursor being kicked out.
      var caret = null;
      var prevSearch = el.querySelector('.table-search');
      if (prevSearch && document.activeElement === prevSearch){
        caret = {
          start: prevSearch.selectionStart,
          end:   prevSearch.selectionEnd,
          dir:   prevSearch.selectionDirection || 'none'
        };
      }

      var ds = w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
      if (!ds || !ds.length) {
        el.innerHTML = '<div class="table-empty">' +
          (w.empty_message || 'No rows.') + '</div>';
        return;
      }
      var header = ds[0];
      var allBody = applyFilters(w.dataset_ref, ds).slice(1);
      var ts = tableState(id);

      // Search filter
      if (ts.search){
        allBody = allBody.filter(function(r){ return _rowMatchesSearch(r, ts.search); });
      }

      // Column config: if not supplied, auto-generate from header.
      var cols = w.columns;
      if (!cols || !cols.length){
        cols = header.map(function(h){ return {field: h, label: h}; });
      }
      var colIndexes = cols.map(function(c){ return header.indexOf(c.field); });
      var colCompare = function(ci, dir){
        return function(a, b){
          var av = a[ci], bv = b[ci];
          if (av == null && bv == null) return 0;
          if (av == null) return 1;
          if (bv == null) return -1;
          var an = Number(av), bn = Number(bv);
          if (!isNaN(an) && !isNaN(bn)) return (an - bn) * dir;
          return String(av).localeCompare(String(bv)) * dir;
        };
      };
      if (ts.sortCol != null && colIndexes[ts.sortCol] >= 0){
        allBody = allBody.slice().sort(colCompare(colIndexes[ts.sortCol], ts.sortDir));
      }

      var maxRows = w.max_rows || 100;
      var visible = allBody.slice(0, maxRows);
      var allRowsShown = allBody.length <= maxRows;

      var html = '';
      var downloadable = w.downloadable !== false;
      if (w.searchable || downloadable){
        html += '<div class="table-toolbar">';
        if (w.searchable){
          html += '<input class="table-search" data-tid="' + id +
            '" placeholder="Search..." value="' + _he(ts.search) + '"/>';
        }
        if (w.searchable){
          html += '<span class="table-count">' + allBody.length +
            (allRowsShown ? '' : ' (showing ' + maxRows + ')') +
            ' rows</span>';
        }
        if (downloadable){
          html += '<button class="table-xlsx-btn" data-tid="' + id +
            '" title="Download this table as Excel">XLSX</button>';
        }
        html += '</div>';
      }
      html += '<table class="data-table' +
              (w.row_height === 'compact' ? ' compact' : '') +
              (w.row_click ? ' clickable' : '') +
              '"><thead><tr>';

      cols.forEach(function(c, ci){
        var lbl = c.label != null ? c.label : c.field;
        var align = c.align || (c.format && /^(number|integer|percent|currency|bps|signed|delta)/.test(c.format) ? 'right' : 'left');
        var tip = c.tooltip ? ' title="' + _he(c.tooltip) + '"' : '';
        var sortable = c.sortable !== false && w.sortable !== false;
        var arrow = '';
        if (sortable && ts.sortCol === ci){
          arrow = ts.sortDir === 1 ? ' \u25B4' : ' \u25BE';
        }
        html += '<th style="text-align:' + align + '"' +
                (sortable ? ' class="sortable" data-col="' + ci + '" data-tid="' + id + '"' : '') +
                tip + '>' + _he(lbl) + arrow + '</th>';
      });
      html += '</tr></thead><tbody>';

      // Row highlighting: match a list of rules `{field, op, value,
      // class}` against each row. First matching rule wins. `class`
      // must be one of: 'pos', 'neg', 'muted', 'warn', 'info', or
      // a dashed bucket name. The row gets a `.row-hl-<class>` CSS
      // class (styles below).
      function _pickRowHL(row) {
        var rules = w.row_highlight || [];
        for (var i = 0; i < rules.length; i++){
          var r = rules[i];
          var fi = header.indexOf(r.field);
          if (fi < 0) continue;
          if (cmpOp(r.op || '==', row[fi], r.value)){
            return r.class || r.cls || r.className || 'info';
          }
        }
        return null;
      }

      visible.forEach(function(row, ri){
        var hlClass = _pickRowHL(row);
        var rowCls = hlClass ? ' class="row-hl-' + hlClass + '"' : '';
        html += '<tr' + rowCls + ' data-row-idx="' + ri + '" data-tid="' + id + '">';
        cols.forEach(function(c, ci){
          var hi = colIndexes[ci];
          var v = hi >= 0 ? row[hi] : null;
          var txt = formatValue(v, c.format);
          var align = c.align || (c.format && /^(number|integer|percent|currency|bps|signed|delta)/.test(c.format) ? 'right' : 'left');
          var styleParts = ['text-align:' + align];
          // Conditional formatting
          var cs = conditionalStyle(v, c.conditional);
          if (cs){
            if (cs.background) styleParts.push('background:' + cs.background);
            if (cs.color)      styleParts.push('color:' + cs.color);
            if (cs.bold)       styleParts.push('font-weight:600');
          }
          // Color scale (continuous heatmap)
          if (c.color_scale){
            var bg = colorForScale(v, c.color_scale);
            if (bg){
              styleParts.push('background:' + bg);
              // Pick black or white text for contrast
              var rgb = _hex2rgb(bg);
              var lum = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2];
              styleParts.push('color:' + (lum > 128 ? '#1a1a1a' : '#ffffff'));
            }
          }
          var tip = c.tooltip ? ' title="' + _he(c.tooltip) + '"' : '';
          html += '<td style="' + styleParts.join(';') + '"' + tip + '>' + txt + '</td>';
        });
        html += '</tr>';
      });
      html += '</tbody></table>';
      el.innerHTML = html;

      // Wire search
      var searchEl = el.querySelector('.table-search');
      if (searchEl){
        if (caret){
          searchEl.focus();
          try { searchEl.setSelectionRange(caret.start, caret.end, caret.dir); }
          catch(e){}
        }
        var tId = null;
        searchEl.addEventListener('input', function(){
          ts.search = searchEl.value;
          if (tId) clearTimeout(tId);
          tId = setTimeout(function(){ renderTables(); }, 160);
        });
      }
      // Wire per-table XLSX button
      var xlsxEl = el.querySelector('.table-xlsx-btn');
      if (xlsxEl){
        xlsxEl.addEventListener('click', function(){
          if (typeof window.downloadOneTableXlsx === 'function'){
            window.downloadOneTableXlsx(id);
          }
        });
      }
      // Wire header-click sort
      el.querySelectorAll('th.sortable').forEach(function(th){
        th.addEventListener('click', function(){
          var ci = Number(th.dataset.col);
          if (ts.sortCol === ci) ts.sortDir = -ts.sortDir;
          else { ts.sortCol = ci; ts.sortDir = 1; }
          renderTables();
        });
      });
      // Wire row click -> popup modal
      if (w.row_click){
        el.querySelectorAll('tbody tr').forEach(function(tr){
          tr.addEventListener('click', function(){
            var idx = Number(tr.dataset.rowIdx);
            var row = visible[idx];
            openRowModal(w, header, row, cols);
          });
        });
      }
    });
  }

  function _he(s){
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  // ----- popup modal (table row_click + chart click_popup) -----
  //
  // Single source of truth for the click-popup modal. Both
  // table.row_click and chart.click_popup hand a config dict +
  // header + row to `_openPopupModal` and get back a populated
  // modal -- simple key/value table OR rich detail.sections[] layout.
  //
  // Two modes (apply identically to row_click and click_popup):
  //   A) Simple key/value table. Use `popup_fields` -- a list of
  //      field-name strings, OR `{field, label, format, prefix,
  //      suffix}` dicts when the caller wants per-row formatting
  //      without dropping into rich mode (chart click popups don't
  //      have a column config to inherit formats from).
  //      Default (no `popup_fields`) = every column in `header`.
  //   B) Rich detail layout. Use `detail.sections[]` with
  //      section `type: "stats" | "markdown" | "chart" | "table"`.
  //      Charts and sub-tables can be filtered by the clicked row's
  //      key value, so you can embed a per-entity time series,
  //      yield curve, etc.
  //
  // `cols` is the table widget's column config (per-column format
  // hints, used as a fallback when popup_fields entries are bare
  // field-name strings). Pass `null` for chart click popups.
  function openRowModal(w, header, row, cols){
    _openPopupModal(w.row_click || {}, header, row, cols);
  }
  function _openPopupModal(rc, header, row, cols){
    if (!rc || typeof rc !== 'object') return;
    var title = '';
    if (rc.title_field){
      var tIdx = header.indexOf(rc.title_field);
      if (tIdx >= 0) title = String(row[tIdx]);
    }
    if (!title && cols && cols.length){
      var firstIdx = header.indexOf(cols[0].field);
      if (firstIdx >= 0) title = String(row[firstIdx]);
    }
    // subtitle support: `subtitle_field` or `subtitle_template`
    // (string with `{field}` / `{field:format}` placeholders).
    var subtitle = null;
    if (rc.subtitle_field){
      var sIdx = header.indexOf(rc.subtitle_field);
      if (sIdx >= 0) subtitle = String(row[sIdx]);
    } else if (rc.subtitle_template){
      subtitle = _expandRowTemplate(rc.subtitle_template, header, row);
    }

    if (rc.detail && rc.detail.sections){
      openRichRowModal(rc, title, subtitle, header, row, cols);
      return;
    }

    // Simple mode: key/value table.
    // Each entry of `popup_fields` is either a plain field-name string
    // (we look up the format in `cols` if any), or a dict
    // {field, label?, format?, prefix?, suffix?}. Mixed lists are fine.
    var showFields = rc.popup_fields;
    if (!showFields || showFields === '*' ||
        (Array.isArray(showFields) && showFields.length === 1
          && showFields[0] === '*')){
      showFields = header.slice();
    }

    var body = '<table class="modal-detail-table">';
    showFields.forEach(function(item){
      var fname = (typeof item === 'string') ? item : (item && item.field);
      if (!fname) return;
      var hi = header.indexOf(fname);
      if (hi < 0) return;
      var val = row[hi];
      var label = (item && typeof item === 'object' && item.label != null)
        ? item.label : fname;
      var fmt = (item && typeof item === 'object') ? item.format : null;
      if (!fmt && cols){
        for (var i = 0; i < cols.length; i++){
          if (cols[i].field === fname){ fmt = cols[i].format; break; }
        }
      }
      var text = formatValue(val, fmt);
      if (item && typeof item === 'object'){
        if (item.prefix) text = item.prefix + text;
        if (item.suffix) text = text + item.suffix;
      }
      body += '<tr><th>' + _he(label) + '</th>' +
               '<td>' + text + '</td></tr>';
    });
    body += '</table>';

    if (rc.extra_content){
      body += '<div class="modal-extra">' + String(rc.extra_content) + '</div>';
    }

    showModal(title || 'Details', body, {subtitle: subtitle, wide: false});
  }

  // Substitute `{field}` tokens in a template using the current row
  // values. `{field:format}` applies a value format (see formatValue).
  function _expandRowTemplate(tpl, header, row){
    return String(tpl).replace(/\{([^}:]+)(?::([^}]+))?\}/g, function(m, f, fmt){
      var i = header.indexOf(f.trim());
      if (i < 0) return m;
      return formatValue(row[i], fmt ? fmt.trim() : null);
    });
  }

  function openRichRowModal(rc, title, subtitle, header, row, cols){
    var detail = rc.detail || {};
    var sections = detail.sections || [];
    var rowMap = {};
    header.forEach(function(h, i){ rowMap[h] = row[i]; });

    // Give each chart section a stable dom id so we can init ECharts
    // after the modal HTML is in the DOM.
    var chartJobs = [];
    var parts = [];

    sections.forEach(function(sec, si){
      var sType = (sec.type || '').toLowerCase();
      if (sType === 'stats'){
        parts.push(_renderDetailStats(sec, rowMap, header, cols));
      } else if (sType === 'markdown'){
        parts.push(_renderDetailMarkdown(sec, header, row));
      } else if (sType === 'chart'){
        var cid = 'detail-chart-' + si + '-' + (Math.random() * 1e6 | 0);
        var h = sec.height || sec.h_px || 260;
        parts.push(
          (sec.title ? '<div class="detail-section-title">'
             + _he(sec.title) + '</div>' : '') +
          '<div id="' + cid + '" class="detail-chart"'
          + ' style="height:' + h + 'px"></div>'
        );
        chartJobs.push({id: cid, sec: sec});
      } else if (sType === 'table'){
        parts.push(_renderDetailTable(sec, rowMap, header, row));
      } else if (sType === 'kv' || sType === 'kv_table'){
        // Simple key/value inline
        parts.push(_renderDetailKV(sec, header, row, cols));
      }
    });

    showModal(title || 'Details', parts.join('\n'),
                {subtitle: subtitle, wide: detail.wide !== false});

    // Init embedded charts AFTER the DOM is live so ECharts can
    // measure their containers.
    setTimeout(function(){
      chartJobs.forEach(function(job){ _renderDetailChart(job.id, job.sec, rowMap); });
    }, 0);
  }

  function _renderDetailStats(sec, rowMap, header, cols){
    var items = (sec.fields || []).map(function(f){
      // Accept plain string ("ticker") or {field, label, format,
      // prefix, suffix}.
      if (typeof f === 'string') f = {field: f};
      var v = rowMap[f.field];
      var lbl = f.label != null ? f.label : f.field;
      var fmt = f.format;
      if (!fmt && cols){
        for (var i = 0; i < cols.length; i++){
          if (cols[i].field === f.field){ fmt = cols[i].format; break; }
        }
      }
      var text = formatValue(v, fmt);
      if (f.prefix) text = f.prefix + text;
      if (f.suffix) text = text + f.suffix;
      var cls = 'detail-stat';
      if (typeof v === 'number'){
        if (f.signed_color && v > 0) cls += ' pos';
        else if (f.signed_color && v < 0) cls += ' neg';
      }
      return '<div class="' + cls + '">'
        + '<div class="detail-stat-label">' + _he(lbl) + '</div>'
        + '<div class="detail-stat-value">' + text + '</div>'
        + (f.sub ? '<div class="detail-stat-sub">'
                    + _he(_expandRowTemplate(f.sub, header,
                        header.map(function(h){ return rowMap[h]; })))
                    + '</div>' : '')
        + '</div>';
    });
    var title = sec.title
      ? '<div class="detail-section-title">' + _he(sec.title) + '</div>'
      : '';
    return title + '<div class="detail-stats">' + items.join('') + '</div>';
  }

  function _renderDetailMarkdown(sec, header, row){
    var tpl = sec.template != null ? sec.template
               : (sec.content != null ? sec.content : '');
    var md = _expandRowTemplate(tpl, header, row);
    return '<div class="detail-markdown">' + _mdInlinePopup(md) + '</div>';
  }

  function _renderDetailKV(sec, header, row, cols){
    var fields = sec.fields || header;
    var body = '<table class="modal-detail-table">';
    fields.forEach(function(fname){
      var hi = header.indexOf(fname);
      if (hi < 0) return;
      var fmt = null;
      if (cols){
        for (var i = 0; i < cols.length; i++){
          if (cols[i].field === fname){ fmt = cols[i].format; break; }
        }
      }
      body += '<tr><th>' + _he(fname) + '</th>'
           + '<td>' + formatValue(row[hi], fmt) + '</td></tr>';
    });
    body += '</table>';
    var title = sec.title
      ? '<div class="detail-section-title">' + _he(sec.title) + '</div>'
      : '';
    return title + body;
  }

  function _renderDetailTable(sec, rowMap, header, row){
    // A sub-table driven by a filtered manifest dataset.
    // sec: {dataset, filter_field?, row_key?, columns?, max_rows?}
    var ds = DATASETS[sec.dataset];
    var src = ds && ds.source ? ds.source : ds;
    if (!Array.isArray(src) || src.length < 2) return '';
    var sHeader = src[0];
    var body = src.slice(1);
    if (sec.filter_field && sec.row_key){
      var key = rowMap[sec.row_key];
      var fi = sHeader.indexOf(sec.filter_field);
      if (fi >= 0) body = body.filter(function(r){ return r[fi] === key; });
    }
    var maxRows = sec.max_rows || 12;
    body = body.slice(0, maxRows);
    var colsCfg = sec.columns ||
      sHeader.map(function(h){ return {field: h, label: h}; });
    var cIdx = colsCfg.map(function(c){ return sHeader.indexOf(c.field); });
    var html = '<table class="modal-detail-table sub"><thead><tr>';
    colsCfg.forEach(function(c){
      html += '<th>' + _he(c.label || c.field) + '</th>';
    });
    html += '</tr></thead><tbody>';
    body.forEach(function(r){
      html += '<tr>';
      colsCfg.forEach(function(c, ci){
        var v = cIdx[ci] >= 0 ? r[cIdx[ci]] : null;
        html += '<td>' + formatValue(v, c.format) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    var title = sec.title
      ? '<div class="detail-section-title">' + _he(sec.title) + '</div>'
      : '';
    return title + html;
  }

  function _renderDetailChart(elId, sec, rowMap){
    var el = document.getElementById(elId); if (!el) return;
    var ds = DATASETS[sec.dataset];
    var src = ds && ds.source ? ds.source : ds;
    if (!Array.isArray(src) || src.length < 2) return;
    var header = src[0];
    var body = src.slice(1);
    // Filter to the clicked row's key value if configured.
    if (sec.filter_field && sec.row_key){
      var key = rowMap[sec.row_key];
      var fi = header.indexOf(sec.filter_field);
      if (fi >= 0) body = body.filter(function(r){ return r[fi] === key; });
    }
    if (!body.length) {
      el.innerHTML = '<div class="detail-chart-empty">No data for this row.</div>';
      return;
    }
    var m = sec.mapping || {};
    var chartType = (sec.chart_type || 'line').toLowerCase();
    var xCol = m.x;
    var yCol = m.y;
    var xIdx = header.indexOf(xCol);
    // Build the option. We intentionally keep this small and purpose-
    // built (rather than calling into the main builder dispatch on
    // the server) so detail popups render fast and don't need a full
    // Python round-trip on each row click.
    var series = [];
    if (Array.isArray(yCol)){
      // Wide-form: one line per y column.
      yCol.forEach(function(y){
        var yi = header.indexOf(y);
        series.push({
          type: chartType === 'bar' ? 'bar' : 'line',
          name: y, showSymbol: false,
          data: body.map(function(r){ return [r[xIdx], r[yi]]; }),
        });
      });
    } else {
      var yi = header.indexOf(yCol);
      series.push({
        type: chartType === 'bar' ? 'bar' : 'line',
        name: yCol, showSymbol: false,
        areaStyle: chartType === 'area' ? {opacity: 0.25} : undefined,
        data: body.map(function(r){ return [r[xIdx], r[yi]]; }),
      });
    }
    var opt = {
      grid: {top: 24, right: 24, bottom: 40, left: 56, containLabel: true},
      tooltip: {trigger: 'axis'},
      xAxis: {type: _guessAxisTypeFromValues(body, xIdx)},
      yAxis: {type: 'value', scale: true,
               name: m.y_title || ''},
      series: series,
    };
    // date formatting like the main charts
    if (opt.xAxis.type === 'time'){
      opt.xAxis.axisLabel = {formatter: function(v){
        var d = new Date(v);
        if (isNaN(d.getTime())) return v;
        var mo = ['Jan','Feb','Mar','Apr','May','Jun',
                  'Jul','Aug','Sep','Oct','Nov','Dec'][d.getMonth()];
        return mo + ' ' + d.getDate();
      }};
    }
    // Palette from GS theme
    opt.color = PAYLOAD.palettes.gs_primary ? PAYLOAD.palettes.gs_primary.colors : null;
    if (sec.annotations){
      _applyDetailAnnotations(opt, sec.annotations);
    }
    var theme = MANIFEST.theme || 'gs_clean';
    var inst = echarts.init(el, theme in PAYLOAD.themes ? theme : null);
    inst.setOption(opt, true);
    // Track so we can dispose on modal close (prevents leak over many
    // clicks).
    _DETAIL_CHARTS.push(inst);
  }

  function _guessAxisTypeFromValues(rows, idx){
    if (!rows.length || idx < 0) return 'value';
    var v = rows[0][idx];
    if (typeof v === 'number') return 'value';
    if (typeof v === 'string') {
      var d = Date.parse(v);
      if (!isNaN(d)) return 'time';
      return 'category';
    }
    return 'value';
  }

  function _applyDetailAnnotations(opt, ann){
    var mlData = [], maData = [];
    (ann || []).forEach(function(a){
      if (!a || typeof a !== 'object') return;
      if (a.type === 'hline' && a.y != null){
        mlData.push({yAxis: a.y,
                      lineStyle: {color: a.color || '#718096',
                                    type: a.style || 'dashed'},
                      label: {formatter: a.label || ''}});
      } else if (a.type === 'vline' && a.x != null){
        mlData.push({xAxis: a.x,
                      lineStyle: {color: a.color || '#718096',
                                    type: a.style || 'dashed'},
                      label: {formatter: a.label || ''}});
      } else if (a.type === 'band' && a.y1 != null && a.y2 != null){
        maData.push([{yAxis: a.y1,
                       itemStyle: {color: a.color || 'rgba(26,54,93,0.08)',
                                     opacity: a.opacity || 0.2}},
                      {yAxis: a.y2}]);
      }
    });
    if (mlData.length || maData.length){
      var s0 = (opt.series || [])[0] || {};
      if (mlData.length) s0.markLine = {symbol: 'none', data: mlData};
      if (maData.length) s0.markArea = {data: maData};
    }
  }

  var _DETAIL_CHARTS = [];

  function showModal(title, bodyHtml, opts){
    opts = opts || {};
    var back = document.getElementById('ed-modal-backdrop');
    if (!back){
      back = document.createElement('div');
      back.id = 'ed-modal-backdrop';
      back.className = 'ed-modal-backdrop';
      back.innerHTML =
        '<div class="ed-modal">' +
          '<div class="ed-modal-header">' +
            '<div class="ed-modal-title-wrap">' +
              '<div class="ed-modal-title"></div>' +
              '<div class="ed-modal-subtitle"></div>' +
            '</div>' +
            '<button class="ed-modal-close" aria-label="close">\u2715</button>' +
          '</div>' +
          '<div class="ed-modal-body"></div>' +
        '</div>';
      document.body.appendChild(back);
      back.addEventListener('click', function(e){
        if (e.target === back) hideModal();
      });
      back.querySelector('.ed-modal-close').addEventListener('click', hideModal);
      document.addEventListener('keydown', function(e){
        if (e.key === 'Escape') hideModal();
      });
    }
    var modal = back.querySelector('.ed-modal');
    modal.classList.toggle('wide', !!opts.wide);
    back.querySelector('.ed-modal-title').textContent = title;
    var subEl = back.querySelector('.ed-modal-subtitle');
    if (opts.subtitle){
      subEl.textContent = opts.subtitle;
      subEl.style.display = 'block';
    } else {
      subEl.textContent = '';
      subEl.style.display = 'none';
    }
    back.querySelector('.ed-modal-body').innerHTML = bodyHtml;
    back.style.display = 'flex';
  }
  function hideModal(){
    var back = document.getElementById('ed-modal-backdrop');
    if (back) back.style.display = 'none';
    // Dispose embedded detail charts so they don't leak memory
    // across many row clicks.
    if (typeof _DETAIL_CHARTS !== 'undefined' && _DETAIL_CHARTS){
      _DETAIL_CHARTS.forEach(function(inst){
        try { inst.dispose(); } catch(e){}
      });
      _DETAIL_CHARTS.length = 0;
    }
  }

  // ----- click popup wiring (info icons) -----
  //
  // Every \u24D8 icon in the dashboard carries `data-popup-title` and
  // `data-popup-body` attributes (set server-side by
  // _popup_icon_html). Clicking the icon opens the shared modal with
  // markdown-rendered body content. ESC / overlay click / X button
  // all close the modal via existing hideModal wiring.
  //
  // Also: clicking inside a <label> normally toggles the associated
  // form control; we stopPropagation so the filter doesn't re-focus
  // underneath the open modal.
  function _mdInlinePopup(text){
    // Markdown renderer for popup bodies (info / methodology /
    // row drill-down / dashboard summary). Twin of the Python
    // `_render_md` in rendering.py - both must support the same
    // grammar so server-rendered tiles and client-rendered modals
    // read identically.
    //
    // Block grammar:
    //   # ... ##### headings (h1..h5)
    //   blank-line separated paragraphs
    //   - / * unordered list items, 1. ordered list items
    //     (nested via 2-space indent)
    //   > blockquote (multi-line; recursively parsed)
    //   ``` fenced code blocks ``` (with optional language tag)
    //   | a | b |  GFM tables (header + separator + body rows)
    //   --- / *** / ___ horizontal rules
    //
    // Inline grammar:
    //   **bold**  *italic*  ~~strike~~  `code`  [label](url)
    //
    // IMPORTANT ordering: line-level constructs (headings, bullets,
    // tables, code fences) are detected BEFORE inline transforms run.
    // Otherwise the italic regex eats things like consecutive bullet
    // markers across lines.
    if (text == null) return '';
    var escapeHTML = function(s){
      return String(s == null ? '' : s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    };
    function inlineTransforms(raw){
      var phs = [];
      var staged = String(raw).replace(/\[([^\]]+)\]\(([^)]+)\)/g,
        function(_, lbl, url){
          phs.push('<a href="' + escapeHTML(url) + '" target="_blank"' +
                    ' rel="noopener">' + escapeHTML(lbl) + '</a>');
          return '\x00LINK' + (phs.length - 1) + '\x00';
        });
      var e = escapeHTML(staged);
      e = e.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      e = e.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
      e = e.replace(/~~([^~]+)~~/g, '<del>$1</del>');
      e = e.replace(/`([^`]+)`/g, '<code>$1</code>');
      for (var i = 0; i < phs.length; i++){
        e = e.replace('\x00LINK' + i + '\x00', phs[i]);
      }
      return e;
    }
    function splitTableRow(line){
      var s = String(line).trim();
      if (s.charAt(0) === '|') s = s.slice(1);
      if (s.charAt(s.length - 1) === '|') s = s.slice(0, -1);
      return s.split('|').map(function(c){ return c.trim(); });
    }
    function parseTableAligns(sep){
      return splitTableRow(sep).map(function(c){
        if (c.charAt(0) === ':' && c.charAt(c.length - 1) === ':') return 'center';
        if (c.charAt(c.length - 1) === ':') return 'right';
        if (c.charAt(0) === ':') return 'left';
        return null;
      });
    }
    var TABLE_SEP_RE = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;
    var HR_RE = /^\s*([-*_])\s*\1\s*\1[\s\1]*$/;
    var lines = String(text).split(/\n/);
    var out = [];
    var para = [];
    var quoteBuf = [];
    var listStack = [];   // [{kind, indent}, ...]
    var liOpen = [];       // parallel to listStack: is the deepest <li> still open?
    function flushPara(){
      if (para.length){
        out.push('<p>' + para.join(' ') + '</p>');
        para = [];
      }
    }
    function flushQuote(){
      if (quoteBuf.length){
        var inner = _mdInlinePopup(quoteBuf.join('\n'));
        out.push('<blockquote>' + inner + '</blockquote>');
        quoteBuf = [];
      }
    }
    function closeTopList(){
      var top = listStack.pop();
      if (liOpen.pop()) out.push('</li>');
      out.push('</' + top.kind + '>');
    }
    function closeAllLists(){
      while (listStack.length) closeTopList();
    }
    function pushListItem(kind, indent, text){
      while (listStack.length && listStack[listStack.length - 1].indent > indent){
        closeTopList();
      }
      if (listStack.length && listStack[listStack.length - 1].indent === indent){
        var top = listStack[listStack.length - 1];
        if (top.kind !== kind){
          closeTopList();
        } else {
          if (liOpen[liOpen.length - 1]){
            out.push('</li>');
            liOpen[liOpen.length - 1] = false;
          }
        }
      }
      var topIndent = listStack.length ? listStack[listStack.length - 1].indent : -1;
      if (!listStack.length || topIndent < indent){
        listStack.push({kind: kind, indent: indent});
        liOpen.push(false);
        out.push('<' + kind + '>');
      }
      out.push('<li>' + inlineTransforms(text));
      liOpen[liOpen.length - 1] = true;
    }
    var i = 0, n = lines.length;
    while (i < n){
      var raw = lines[i];
      var stripped = raw.replace(/^\s+/, '');
      var indent = raw.length - stripped.length;
      var s = stripped.replace(/\s+$/, '');

      if (s.indexOf('```') === 0){
        var lang = s.slice(3).trim();
        flushPara(); flushQuote(); closeAllLists();
        var buf = []; i += 1;
        while (i < n){
          var fl = lines[i].replace(/^\s+/, '').replace(/\s+$/, '');
          if (fl.indexOf('```') === 0) break;
          buf.push(lines[i]); i += 1;
        }
        i += 1;
        var cls = lang ? ' class="lang-' + escapeHTML(lang) + '"' : '';
        out.push('<pre><code' + cls + '>' + escapeHTML(buf.join('\n')) + '</code></pre>');
        continue;
      }

      if (s.indexOf('|') !== -1 && i + 1 < n &&
          TABLE_SEP_RE.test(lines[i + 1].replace(/\s+$/, ''))){
        flushPara(); flushQuote(); closeAllLists();
        var hdr = splitTableRow(s);
        var aligns = parseTableAligns(lines[i + 1].replace(/\s+$/, ''));
        i += 2;
        var rows = [];
        while (i < n){
          var rs = lines[i].replace(/\s+$/, '');
          if (rs.indexOf('|') !== -1 && rs.trim()){
            rows.push(splitTableRow(rs)); i += 1;
          } else { break; }
        }
        var tbl = ['<table class="md-table"><thead><tr>'];
        hdr.forEach(function(h, j){
          var al = aligns[j];
          tbl.push('<th' + (al ? ' style="text-align:' + al + '"' : '') + '>' +
                    inlineTransforms(h) + '</th>');
        });
        tbl.push('</tr></thead><tbody>');
        rows.forEach(function(row){
          tbl.push('<tr>');
          row.forEach(function(c, j){
            var al = aligns[j];
            tbl.push('<td' + (al ? ' style="text-align:' + al + '"' : '') + '>' +
                      inlineTransforms(c) + '</td>');
          });
          tbl.push('</tr>');
        });
        tbl.push('</tbody></table>');
        out.push(tbl.join(''));
        continue;
      }

      if (HR_RE.test(s)){
        flushPara(); flushQuote(); closeAllLists();
        out.push('<hr/>');
        i += 1; continue;
      }

      if (s === ''){
        flushPara(); flushQuote(); closeAllLists();
        i += 1; continue;
      }

      var hMatch = /^(#{1,5})\s+(.*)$/.exec(s);
      if (hMatch){
        flushPara(); flushQuote(); closeAllLists();
        var lvl = Math.min(hMatch[1].length, 5);
        out.push('<h' + lvl + '>' + inlineTransforms(hMatch[2]) + '</h' + lvl + '>');
        i += 1; continue;
      }

      if (s.indexOf('> ') === 0){
        flushPara(); closeAllLists();
        quoteBuf.push(s.slice(2));
        i += 1; continue;
      }
      if (s === '>'){
        flushPara(); closeAllLists();
        quoteBuf.push('');
        i += 1; continue;
      }

      var olMatch = /^(\d+)\.\s+(.*)$/.exec(s);
      var ulMatch = /^[-*]\s+(.*)$/.exec(s);
      if (olMatch || ulMatch){
        flushPara(); flushQuote();
        var kind = olMatch ? 'ol' : 'ul';
        var liText = olMatch ? olMatch[2] : ulMatch[1];
        var snapped = (indent - (indent % 2));
        pushListItem(kind, snapped, liText);
        i += 1; continue;
      }

      flushQuote(); closeAllLists();
      para.push(inlineTransforms(stripped));
      i += 1;
    }
    flushPara(); flushQuote(); closeAllLists();
    return out.join('\n');
  }

  function wirePopupIcons(){
    document.querySelectorAll(
      '.tile-info, .filter-info, .stat-info'
    ).forEach(function(icon){
      if (icon._popupWired) return;
      icon._popupWired = true;
      icon.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var title = icon.getAttribute('data-popup-title') || '';
        var body = icon.getAttribute('data-popup-body') || '';
        if (!body) return;
        showModal(title || 'Details', _mdInlinePopup(body));
      });
      icon.addEventListener('keydown', function(e){
        if (e.key === 'Enter' || e.key === ' '){
          e.preventDefault(); icon.click();
        }
      });
    });
  }
  wirePopupIcons();

  // ----- chart PNG export (with title baked in) -----
  //
  // The dashboard tile renders the chart's title in its header chrome
  // and the compiler suppresses the internal ECharts title to avoid
  // duplication on screen. That means a vanilla `chart.getDataURL()`
  // produces a PNG with no title, which is useless for embeds /
  // vision-model handoffs / decks.
  //
  // Strategy: temporarily inject a title (using GS type styles)
  // straight into the live chart, snapshot via getDataURL(), then
  // immediately revert. ECharts' setOption + getDataURL is fully
  // synchronous, so the whole sequence runs inside one event-loop
  // tick and the browser never paints the intermediate state -- no
  // visual flicker for the user.
  //
  // We tried an offscreen-instance variant first (clean isolation,
  // no live mutation). It rendered the title and axes correctly but
  // the dataset rows didn't draw -- ECharts doesn't reliably accept
  // a dataset payload via setOption when it was sourced from another
  // live instance's getOption(). Mutating-and-restoring is simpler
  // and bullet-proof.
  function _hasExistingChartTitle(t){
    if (!t) return false;
    if (Array.isArray(t)){
      return t.some(function(x){ return x && x.text; });
    }
    return !!t.text;
  }
  function _exportTitleBlock(w){
    return {
      text: w && w.title ? String(w.title) : '',
      subtext: w && w.subtitle ? String(w.subtitle) : '',
      left: 16,
      top: 10,
      textStyle: {
        fontFamily: 'Goldman Sans, GS Sans, Helvetica Neue, Arial, sans-serif',
        fontSize: 14,
        fontWeight: 600,
        color: '#1A1A1A'
      },
      subtextStyle: {
        fontFamily: 'Goldman Sans, GS Sans, Helvetica Neue, Arial, sans-serif',
        fontSize: 11,
        color: '#595959',
        fontStyle: 'italic'
      }
    };
  }
  function _downloadChartPngTitled(id, scale){
    var c = CHARTS[id]; if (!c) return false;
    var w = WIDGET_META[id] || {};
    var inst = c.inst;
    var hasOwnTitle = false;
    try {
      hasOwnTitle = _hasExistingChartTitle(inst.getOption().title);
    } catch(e){}

    // Skip injection when the chart already shows its own title
    // (spec.keep_title=true) or there's nothing to inject. Fall
    // through to the plain getDataURL path.
    var canInject = (w.title || w.subtitle) && !hasOwnTitle;

    if (canInject){
      try {
        // Inject title (and small grid.top bump so the plot area
        // doesn't overlap the title text).
        var titlePx = 26 + (w.subtitle ? 18 : 0) + 10;
        inst.setOption({
          title: [_exportTitleBlock(w)],
          grid: {top: titlePx + 30}
        }, false);
      } catch(e){ canInject = false; }
    }

    var url = inst.getDataURL({
      pixelRatio: scale,
      backgroundColor: '#ffffff',
      type: 'png'
    });

    if (canInject){
      // Restore: ECharts' setOption(opt, true) keeps prior title /
      // grid state across "notMerge" resets when the new option
      // doesn't restate them, so calling clear() first is the only
      // reliable way to wipe them. Then fully re-render from the
      // single source of truth (materializeOption) which is what
      // every other code path also uses to draw this chart.
      try {
        inst.clear();
        var fresh = (typeof reviveFns === 'function')
                       ? reviveFns(materializeOption(id))
                       : materializeOption(id);
        inst.setOption(fresh, true);
      } catch(e){}
    }

    var a = document.createElement('a');
    a.href = url; a.download = (id || 'chart') + '.png'; a.click();
    return true;
  }
  window.downloadChartPngTitled = _downloadChartPngTitled;

  // ----- per-tile fullscreen + export -----
  function wireTileActions(){
    document.querySelectorAll('.tile').forEach(function(tile){
      var id = tile.dataset.tileId;
      var fs = tile.querySelector('.tile-btn.fullscreen');
      if (fs){
        fs.addEventListener('click', function(){
          tile.classList.toggle('is-fullscreen');
          var c = CHARTS[id]; if (c) { setTimeout(function(){ c.inst.resize(); }, 120); }
        });
      }
      var dl = tile.querySelector('.tile-btn.download');
      if (dl){
        dl.addEventListener('click', function(){
          _downloadChartPngTitled(id, 2);
        });
      }
    });
  }

  var exportAll = document.getElementById('export-all');
  if (exportAll){
    exportAll.addEventListener('click', function(){
      Object.keys(CHARTS).forEach(function(id){
        _downloadChartPngTitled(id, 2);
      });
    });
  }

  // ----- whole-dashboard PNG (html2canvas, lazy-loaded) -----
  //
  // Captures the entire .app subtree (header, tabs, filter bar, active
  // tab panel, footer) to a single PNG. Designed for the "drop into a
  // vision model" workflow, so the export is intentionally generous:
  // backgroundColor='#fff', scale=2, full scrollHeight. html2canvas is
  // fetched lazily on first click so dashboards that never click this
  // pay zero cost.
  function ensureHtml2Canvas(){
    if (window.html2canvas) return Promise.resolve();
    if (window.__h2cLoading__) return window.__h2cLoading__;
    window.__h2cLoading__ = new Promise(function(resolve, reject){
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
      s.async = true;
      s.onload = function(){ resolve(); };
      s.onerror = function(){
        window.__h2cLoading__ = null;
        reject(new Error('Failed to load html2canvas'));
      };
      document.head.appendChild(s);
    });
    return window.__h2cLoading__;
  }

  var exportDash = document.getElementById('export-dashboard');
  if (exportDash){
    exportDash.addEventListener('click', function(){
      var btn = exportDash;
      var origLabel = btn.textContent;
      btn.textContent = 'Capturing...';
      btn.disabled = true;
      var stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 19);
      var fname = (MANIFEST.id || 'dashboard') + '_' + stamp + '.png';
      ensureHtml2Canvas().then(function(){
        // Settle ECharts: every chart that has a pending render
        // resolves on its 'finished' event before we rasterize.
        var charts = Object.keys(CHARTS).map(function(k){ return CHARTS[k]; })
          .filter(Boolean);
        return Promise.all(charts.map(function(c){
          return new Promise(function(resolve){
            try {
              c.inst.on('finished', function once(){
                c.inst.off('finished', once); resolve();
              });
              setTimeout(resolve, 1200);
            } catch(e){ resolve(); }
          });
        })).then(function(){ return new Promise(function(r){
          requestAnimationFrame(function(){ requestAnimationFrame(r); });
        }); });
      }).then(function(){
        var target = document.querySelector('.app') || document.body;
        // Note on file:// origins: Chrome prints a one-time
        // "Unsafe attempt to load URL ... 'file:' URLs are treated as
        // unique security origins" warning when html2canvas clones
        // the document into a sandbox iframe. It is purely a console
        // warning -- html2canvas falls through to rendering against
        // the live document and toBlob() succeeds. The warning
        // disappears entirely if the dashboard is served from http
        // (e.g. `python -m http.server` in the dashboard folder).
        return window.html2canvas(target, {
          backgroundColor: '#ffffff',
          scale: 2,
          useCORS: true,
          logging: false,
          windowWidth: target.scrollWidth,
          windowHeight: target.scrollHeight,
          width: target.scrollWidth,
          height: target.scrollHeight,
        });
      }).then(function(canvas){
        return new Promise(function(resolve){
          canvas.toBlob(function(blob){
            if (!blob){ resolve(); return; }
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url; a.download = fname; a.click();
            setTimeout(function(){ URL.revokeObjectURL(url); }, 1500);
            resolve();
          }, 'image/png');
        });
      }).catch(function(e){
        console.error('Dashboard PNG export failed:', e);
        alert('Dashboard PNG export failed. See console for details.');
      }).then(function(){
        btn.textContent = origLabel;
        btn.disabled = false;
      });
    });
  }

  // ----- data freshness badge -----
  //
  // Renders the "Data as of <stamp>" pill. Input is an ISO-8601 string
  // from `metadata.data_as_of` (preferred) or `metadata.generated_at`
  // (fallback). Output is "YYYY-MM-DD HH:MM:SS UTC" -- full second
  // precision, explicit timezone label. Strings the JS Date parser
  // can't handle pass through verbatim so the user still sees something.
  var MD = MANIFEST.metadata || {};
  (function(){
    var el = document.getElementById('data-as-of');
    var val = document.getElementById('data-as-of-val');
    if (!el || !val) return;
    var stamp = MD.data_as_of || MD.generated_at;
    if (!stamp) return;
    var s = String(stamp);
    var d = new Date(s);
    if (!isNaN(d.getTime())){
      s = d.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    }
    val.textContent = s;
    el.style.display = 'inline-flex';
  })();

  // ----- methodology popup -----
  //
  // Shown when manifest.metadata.methodology is set. Accepts either a
  // plain markdown string or a {title, body} dict. Renders into the
  // shared modal via _mdInlinePopup() (same engine used by every other
  // popup in the dashboard, so styling is automatically consistent).
  (function(){
    var btn = document.getElementById('methodology-btn');
    if (!btn) return;
    var m = MD.methodology;
    if (m == null || m === '') return;
    var title = 'Methodology';
    var body = '';
    if (typeof m === 'string'){ body = m; }
    else if (typeof m === 'object'){
      title = m.title || title;
      body = m.body || m.text || '';
    }
    if (!body) return;
    btn.style.display = 'inline-flex';
    btn.addEventListener('click', function(){
      showModal(title, _mdInlinePopup(body));
    });
  })();

  // ----- excel download (header) -----
  //
  // One workbook for the whole dashboard. Each `widget=table` widget
  // gets its own sheet. Rows reflect the current applyFilters() state
  // PLUS the per-table search string and sort order, so what's
  // exported is exactly what the user sees. Sheet names are taken
  // from the widget title (or id), truncated to Excel's 31-char limit
  // and uniquified if collisions occur.
  function _excelSheetName(raw, used){
    var name = String(raw || 'sheet').replace(/[\\\/\?\*\[\]:]/g, ' ').trim();
    if (!name) name = 'sheet';
    name = name.slice(0, 31);
    var base = name, n = 2;
    while (used[name]){
      var suf = ' (' + n + ')';
      name = base.slice(0, 31 - suf.length) + suf;
      n++;
    }
    used[name] = true;
    return name;
  }
  function _exportTableRowsForXlsx(id){
    var w = WIDGET_META[id]; if (!w || w.widget !== 'table') return null;
    var ds = w.dataset_ref ? currentDatasets[w.dataset_ref] : null;
    if (!ds || !ds.length) return null;
    var header = ds[0];
    var body = applyFilters(w.dataset_ref, ds).slice(1);
    var ts = (typeof TABLE_STATE !== 'undefined' && TABLE_STATE[id])
              ? TABLE_STATE[id] : null;
    if (ts && ts.search){
      body = body.filter(function(r){ return _rowMatchesSearch(r, ts.search); });
    }
    var cols = w.columns;
    if (!cols || !cols.length){
      cols = header.map(function(h){ return {field: h, label: h}; });
    }
    var colIndexes = cols.map(function(c){ return header.indexOf(c.field); });
    if (ts && ts.sortCol != null && colIndexes[ts.sortCol] >= 0){
      var ci = colIndexes[ts.sortCol], dir = ts.sortDir;
      body = body.slice().sort(function(a, b){
        var av = a[ci], bv = b[ci];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        var an = Number(av), bn = Number(bv);
        if (!isNaN(an) && !isNaN(bn)) return (an - bn) * dir;
        return String(av).localeCompare(String(bv)) * dir;
      });
    }
    var outHeader = cols.map(function(c){ return c.label != null ? c.label : c.field; });
    var rows = body.map(function(row){
      return cols.map(function(c, i){
        var hi = colIndexes[i];
        return hi >= 0 ? row[hi] : null;
      });
    });
    return [outHeader].concat(rows);
  }
  function downloadAllTablesXlsx(){
    if (typeof XLSX === 'undefined'){
      alert('Excel export requires network access to load the SheetJS ' +
            'library. Please reload while online.');
      return;
    }
    var wb = XLSX.utils.book_new();
    var used = {};
    var added = 0;
    Object.keys(WIDGET_META).forEach(function(id){
      var w = WIDGET_META[id]; if (w.widget !== 'table') return;
      var aoa = _exportTableRowsForXlsx(id);
      if (!aoa) return;
      var ws = XLSX.utils.aoa_to_sheet(aoa);
      var nm = _excelSheetName(w.title || id, used);
      XLSX.utils.book_append_sheet(wb, ws, nm);
      added++;
    });
    if (!added){
      alert('No table widgets to export.');
      return;
    }
    var stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    XLSX.writeFile(wb, (MANIFEST.id || 'dashboard') + '_' + stamp + '.xlsx');
  }
  window.downloadAllTablesXlsx = downloadAllTablesXlsx;
  function downloadOneTableXlsx(id){
    if (typeof XLSX === 'undefined'){
      alert('Excel export requires network access to load the SheetJS ' +
            'library. Please reload while online.');
      return;
    }
    var w = WIDGET_META[id]; if (!w || w.widget !== 'table') return;
    var aoa = _exportTableRowsForXlsx(id);
    if (!aoa){ alert('No rows to export.'); return; }
    var wb = XLSX.utils.book_new();
    var ws = XLSX.utils.aoa_to_sheet(aoa);
    var nm = _excelSheetName(w.title || id, {});
    XLSX.utils.book_append_sheet(wb, ws, nm);
    XLSX.writeFile(wb, (w.title ? String(w.title).replace(/[^\w\-]+/g, '_') : id) + '.xlsx');
  }
  window.downloadOneTableXlsx = downloadOneTableXlsx;
  (function(){
    var btn = document.getElementById('export-excel');
    if (!btn) return;
    var hasTable = Object.keys(WIDGET_META).some(function(k){
      return WIDGET_META[k].widget === 'table';
    });
    if (!hasTable) return;
    btn.style.display = 'inline-flex';
    btn.addEventListener('click', downloadAllTablesXlsx);
  })();

  // ----- header_actions: custom buttons/links in the header -----
  (function(){
    var host = document.getElementById('header-actions');
    var actions = MANIFEST.header_actions || [];
    if (!host || !actions.length) return;
    actions.forEach(function(a){
      var el;
      if (a.href){
        el = document.createElement('a');
        el.href = a.href;
        el.target = a.target || '_blank';
        if (a.target !== '_self') el.rel = 'noopener noreferrer';
      } else {
        el = document.createElement('button');
        el.type = 'button';
      }
      el.className = 'icon-btn' + (a.primary ? ' primary' : '');
      if (a.id) el.id = a.id;
      if (a.title) el.title = a.title;
      el.innerHTML = (a.icon ? (a.icon + ' ') : '') + _he(a.label || '');
      if (a.onclick && typeof window[a.onclick] === 'function'){
        el.addEventListener('click', function(e){
          try { window[a.onclick](e, a); } catch(err){ console.warn(err); }
        });
      }
      host.insertBefore(el, host.firstChild);
    });
  })();

  // ----- refresh button -----
  // Shown when metadata.kerberos + metadata.dashboard_id are set AND
  // metadata.refresh_enabled !== false. POSTs to metadata.api_url (default
  // /api/dashboard/refresh/) and polls metadata.status_url for completion.
  (function(){
    var btn = document.getElementById('refresh-btn');
    var label = document.getElementById('refresh-btn-label');
    if (!btn || !label) return;
    var kerberos = MD.kerberos;
    var dashboardId = MD.dashboard_id || MANIFEST.id;
    var enabled = MD.refresh_enabled !== false;
    if (!kerberos || !dashboardId || !enabled) return;
    var apiUrl = MD.api_url || '/api/dashboard/refresh/';
    var statusUrl = MD.status_url || '/api/dashboard/refresh/status/';
    btn.style.display = 'inline-flex';

    function setLabel(cls, txt){
      btn.classList.remove('refreshing','refresh-success','refresh-error');
      if (cls) btn.classList.add(cls);
      label.textContent = txt;
    }
    function resetLabel(){ setLabel('', 'Refresh'); btn.disabled = false; }
    function pollStatus(){
      var polls = 0, maxPolls = 60; // 3s x 60 = 3 min
      var timer = setInterval(function(){
        polls++;
        if (polls > maxPolls){
          clearInterval(timer); setLabel('refresh-error', 'Timeout');
          setTimeout(resetLabel, 3000); return;
        }
        fetch(statusUrl + '?dashboard_id=' + encodeURIComponent(dashboardId))
          .then(function(r){ return r.json(); })
          .then(function(st){
            if (st.status === 'success'){
              clearInterval(timer);
              setLabel('refresh-success', 'Done -- reloading...');
              setTimeout(function(){ location.reload(); }, 900);
            } else if (st.status === 'error'){
              clearInterval(timer);
              setLabel('refresh-error', 'Error');
              var msg = (st.errors && st.errors.length) ? st.errors[0] : 'Unknown error';
              console.warn('[refresh] error:', msg);
              setTimeout(resetLabel, 3500);
            } else if (st.status === 'partial'){
              clearInterval(timer);
              setLabel('refresh-error', 'Partial');
              setTimeout(function(){ location.reload(); }, 2000);
            }
            // still running -> keep polling
          })
          .catch(function(e){ console.warn('[refresh] poll network error:', e); });
      }, 3000);
    }
    btn.addEventListener('click', function(){
      if (window.location.protocol === 'file:'){
        alert('Refresh is not available when viewing the dashboard offline. ' +
              'Open the dashboard from the PRISM portal to refresh.');
        return;
      }
      btn.disabled = true; setLabel('refreshing', 'Refreshing...');
      fetch(apiUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({kerberos: kerberos, dashboard_id: dashboardId})
      })
        .then(function(r){ return r.json().then(function(j){ return [r.status, j]; }); })
        .then(function(pair){
          var code = pair[0], result = pair[1] || {};
          if (code === 409){ pollStatus(); return; }
          if (result.status === 'refreshing'){ pollStatus(); return; }
          if (result.status === 'success' || result.status === 'partial'){
            setLabel('refresh-success', 'Done -- reloading...');
            setTimeout(function(){ location.reload(); }, 900);
          } else {
            setLabel('refresh-error', 'Error');
            var msg = result.errors || result.error || 'Unknown error';
            console.warn('[refresh] failed:', msg);
            setTimeout(resetLabel, 3500);
          }
        })
        .catch(function(err){
          setLabel('refresh-error', 'Error');
          console.warn('[refresh] network error:', err);
          setTimeout(resetLabel, 3500);
        });
    });
  })();

  // ----- init -----
  window.addEventListener('load', function(){
    wireFilters(); wireTileActions();

    // figure initial tab
    var layout = MANIFEST.layout || {};
    var initialTab = null;
    if (layout.kind === 'tabs' && (layout.tabs || []).length){
      try {
        var saved = localStorage.getItem('echart_dashboard_tab_' + MANIFEST.id);
        if (saved && layout.tabs.some(function(t){ return t.id === saved; })) initialTab = saved;
      } catch(e){}
      initialTab = initialTab || layout.tabs[0].id;
      activateTab(initialTab);
    } else {
      // initialize every chart in the single default tab
      Object.keys(WIDGET_META).forEach(function(id){
        var w = WIDGET_META[id]; if (w.widget === 'chart') initChart(id);
      });
      applyConnects();
    }
    renderKpis(); renderTables();
    window.addEventListener('resize', function(){
      Object.keys(CHARTS).forEach(function(k){
        try { CHARTS[k].inst.resize(); } catch(e){}
      });
    });
  });

  window.DASHBOARD = { manifest: MANIFEST, charts: CHARTS,
                        filters: filterState, datasets: currentDatasets };
})();
"""


# ---------------------------------------------------------------------------
# PYTHON RENDERING
# ---------------------------------------------------------------------------




def _span_style(w: int, cols: int) -> str:
    return f"grid-column: span {max(1, min(w, cols))};"


def _render_filter_controls(filters: List[Dict[str, Any]],
                              *, inline: bool = False,
                              show_reset: bool = True) -> str:
    """Render a list of filter controls as HTML.

    When ``inline=True`` the bar is emitted with the ``tab-filter-bar``
    class (flush with tab content, no full-width border) instead of the
    global ``filter-bar`` chrome. When no filters are supplied an empty
    string is returned so the container can be hidden entirely.
    """
    if not filters:
        return ""
    cls = "tab-filter-bar" if inline else "filter-bar"
    out = [f"<div class=\"{cls}\">"]

    def _label_html(label_text: str, description: Optional[str],
                      popup: Optional[Dict[str, Any]] = None) -> str:
        """Filter label with optional info icon. Hovering shows the
        description as a native tooltip; clicking opens a modal with
        the same text (or the richer ``popup`` body if provided)."""
        if description or popup:
            info = _popup_icon_html(
                info_text=description,
                popup=popup,
                fallback_title=label_text,
                cls="filter-info tile-info",
            )
        else:
            info = ""
        return f'<label>{_html_escape(label_text)}{info}</label>'

    for f in filters:
        fid = f["id"]
        label = f.get("label", fid)
        ftype = f.get("type")
        default = f.get("default", "")
        desc = f.get("description") or f.get("help") or f.get("info")
        lbl = _label_html(label, desc, f.get("popup"))
        if ftype == "dateRange":
            options = ["1M", "3M", "6M", "YTD", "1Y", "2Y", "5Y", "All"]
            opts_html = "".join(
                f"<option value=\"{o}\"{' selected' if str(default) == o else ''}>{o}</option>"
                for o in options
            )
            out.append(
                f"<div class=\"filter-item\">{lbl}"
                f"<select id=\"filter-{fid}\">{opts_html}</select></div>"
            )
        elif ftype in ("select", "multiSelect"):
            options = f.get("options", [])
            multi = " multiple" if ftype == "multiSelect" else ""
            default_set: set = set()
            if isinstance(default, list):
                default_set = set(
                    str(_default_value_for_compare(d)) for d in default)
            elif default:
                default_set = {str(_default_value_for_compare(default))}
            opt_pairs = [_option_value_label(o) for o in options]
            opts_html = "".join(
                f"<option value=\"{_html_escape(v)}\""
                f"{' selected' if v in default_set else ''}>"
                f"{_html_escape(l)}</option>"
                for v, l in opt_pairs
            )
            out.append(
                f"<div class=\"filter-item\">{lbl}"
                f"<select id=\"filter-{fid}\"{multi}>{opts_html}</select></div>"
            )
        elif ftype == "numberRange":
            out.append(
                f"<div class=\"filter-item\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"text\" "
                f"value=\"{_html_escape(str(default))}\" "
                f"placeholder=\"min,max\"/>"
                f"</div>"
            )
        elif ftype == "toggle":
            checked = " checked" if default else ""
            out.append(
                f"<div class=\"filter-item\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"checkbox\"{checked}/></div>"
            )
        elif ftype == "slider":
            mn = f.get("min", 0)
            mx = f.get("max", 100)
            step = f.get("step", 1)
            val = default if default != "" else mn
            out.append(
                f"<div class=\"filter-item slider\">{lbl}"
                f"<div class=\"slider-row\">"
                f"<input id=\"filter-{fid}\" type=\"range\" "
                f"min=\"{mn}\" max=\"{mx}\" step=\"{step}\" value=\"{val}\"/>"
                f"<span id=\"filter-{fid}-val\" class=\"slider-val\">{val}</span>"
                f"</div></div>"
            )
        elif ftype == "radio":
            options = f.get("options", [])
            default_v = str(_default_value_for_compare(default))
            radios: List[str] = []
            for o in options:
                v, l = _option_value_label(o)
                checked = " checked" if v == default_v else ""
                radios.append(
                    f"<label class=\"radio-opt\">"
                    f"<input type=\"radio\" name=\"filter-{fid}\" "
                    f"value=\"{_html_escape(v)}\"{checked}/>"
                    f"{_html_escape(l)}</label>"
                )
            out.append(
                f"<div class=\"filter-item radio-group\">{lbl}"
                f"<div class=\"radio-row\">{''.join(radios)}</div></div>"
            )
        elif ftype == "text":
            placeholder = f.get("placeholder", "Type to search...")
            out.append(
                f"<div class=\"filter-item text\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"text\" "
                f"value=\"{_html_escape(str(default))}\" "
                f"placeholder=\"{_html_escape(placeholder)}\"/></div>"
            )
        elif ftype == "number":
            mn = f.get("min", None)
            mx = f.get("max", None)
            step = f.get("step", "any")
            extra = ""
            if mn is not None:
                extra += f" min=\"{mn}\""
            if mx is not None:
                extra += f" max=\"{mx}\""
            extra += f" step=\"{step}\""
            out.append(
                f"<div class=\"filter-item number\">{lbl}"
                f"<input id=\"filter-{fid}\" type=\"number\""
                f"{extra} value=\"{_html_escape(str(default))}\"/></div>"
            )
    if show_reset:
        reset_id = "filter-reset" if not inline else ""
        reset_attr = f" id=\"{reset_id}\"" if reset_id else ""
        out.append(
            f"<button class=\"icon-btn filter-reset\"{reset_attr}"
            f" data-filter-reset>Reset</button>"
        )
    out.append("</div>")
    return "\n".join(out)


def _chart_toolbar_buttons(w: Dict[str, Any]) -> str:
    """Toolbar buttons for a chart tile.

    Includes built-in PNG / fullscreen buttons and any custom
    ``action_buttons`` the widget defines. Each custom button is a
    dict ``{label, onclick?, href?, icon?, title?}``. `onclick` names
    a global JS function (wired via ``window.<name>``); `href` opens a
    new tab. Unknown entries are skipped.
    """
    extra: List[str] = []
    for btn in w.get("action_buttons") or []:
        if not isinstance(btn, dict):
            continue
        label = _html_escape(btn.get("label", ""))
        if not label and btn.get("icon"):
            label = _html_escape(btn["icon"])
        title = _html_escape(btn.get("title", btn.get("label", "")))
        cls = "tile-btn tile-btn-custom"
        if btn.get("primary"):
            cls += " primary"
        onclick = btn.get("onclick")
        href = btn.get("href")
        if href:
            target = ' target="_blank" rel="noopener"'
            extra.append(
                f'<a class="{cls}" href="{_html_escape(href)}"'
                f' title="{title}"{target}>{label}</a>'
            )
        elif onclick:
            js = (f'(window.{onclick} && window.{onclick}'
                   f'("{_html_escape(w.get("id", ""))}"))')
            extra.append(
                f'<button class="{cls}" title="{title}" '
                f'onclick=\'{js}\'>{label}</button>'
            )
        else:
            extra.append(
                f'<button class="{cls}" title="{title}" disabled>'
                f'{label}</button>'
            )
    return (
        "<div class=\"tile-actions\">"
        + "".join(extra)
        + "<button class=\"tile-btn download\" title=\"PNG 2x\">PNG</button>"
        "<button class=\"tile-btn fullscreen\" title=\"Fullscreen\">"
        "&#x26F6;</button>"
        "</div>"
    )


def _tile_title_html(w: Dict[str, Any]) -> str:
    """Compose the inner title text for a tile header, including an
    optional info icon, compact badge, and subtitle.

      * ``info``     -- short hover tooltip. Clicking the \u24D8 icon
                         also opens a modal with the same text (so long
                         blurbs are readable and dismissable).
      * ``popup``    -- {title, body} (body is markdown). Takes priority
                         over `info` as the modal content; `info` is
                         still used as the native hover tooltip.
      * ``badge``    -- short pill (e.g. "LIVE", "BETA"); pair with
                         ``badge_color`` to pick the hue.
      * ``subtitle`` -- secondary text rendered on the line below the
                         title, italic, small.
    """
    title = _html_escape(w.get("title", ""))
    info = w.get("info")
    popup = w.get("popup")
    badge = w.get("badge")
    subtitle = w.get("subtitle")
    parts = ['<div class="tile-title-wrap">']
    parts.append(f'<div class="tile-title">{title}')
    if info or popup:
        icon_html = _popup_icon_html(
            info_text=info,
            popup=popup,
            fallback_title=w.get("title"),
        )
        parts.append(icon_html)
    if badge:
        color = w.get("badge_color") or "gs-navy"
        parts.append(
            f'<span class="tile-badge" data-color="{_html_escape(color)}">'
            f'{_html_escape(str(badge))}</span>'
        )
    parts.append("</div>")
    if subtitle:
        parts.append(
            f'<div class="tile-subtitle">{_html_escape(str(subtitle))}</div>'
        )
    parts.append("</div>")
    return "".join(parts)


def _popup_icon_html(info_text: Optional[str] = None,
                      popup: Optional[Dict[str, Any]] = None,
                      fallback_title: Optional[str] = None,
                      cls: str = "tile-info") -> str:
    """Render a clickable \u24D8 icon that opens a modal popup.

    Click behaviour takes priority:
      1. ``popup = {title, body}`` -- modal with that content
      2. otherwise ``info`` -- modal with just that text
    Hover shows the ``info`` text natively via the ``title=`` attr.
    """
    hover_title = ""
    modal_title = ""
    modal_body = ""
    if isinstance(popup, dict):
        modal_title = str(popup.get("title", fallback_title or ""))
        modal_body = str(popup.get("body", info_text or ""))
        hover_title = modal_title or info_text or ""
    elif info_text:
        hover_title = str(info_text)
        modal_title = fallback_title or ""
        modal_body = str(info_text)
    title_attr = (f' title="{_html_escape(hover_title)}"'
                   if hover_title else "")
    return (
        f'<span class="{cls}" tabindex="0" role="button"'
        f' aria-label="More info"'
        f'{title_attr}'
        f' data-popup-title="{_html_escape(modal_title)}"'
        f' data-popup-body="{_html_escape(modal_body)}"'
        f'>\u24D8</span>'
    )


def _tile_class(w: Dict[str, Any], base: str) -> str:
    """Base CSS classes for any tile, honoring widget-level flags."""
    cls = base
    if w.get("emphasis") or w.get("emphasized"):
        cls += " tile-emphasis"
    if w.get("pinned"):
        cls += " tile-pinned"
    return cls


def _tile_footer_html(w: Dict[str, Any]) -> str:
    foot = w.get("footer") or w.get("footnote")
    if not foot:
        return ""
    return f'<div class="tile-footer">{_html_escape(str(foot))}</div>'


def _render_widget(w: Dict[str, Any], cols: int) -> str:
    wt = w.get("widget")
    width = w.get("w", cols)
    wid = w.get("id") or f"w_{id(w)}"
    style = _span_style(width, cols)
    if wt == "chart":
        height = int(w.get("h_px", 280))
        cls = _tile_class(w, "tile chart-tile")
        return (
            f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
            f"style=\"{style}\">"
            f"  <div class=\"tile-header\">"
            f"    {_tile_title_html(w)}"
            f"    {_chart_toolbar_buttons(w)}"
            f"  </div>"
            f"  <div class=\"tile-body\">"
            f"    <div id=\"chart-{_html_escape(wid)}\" class=\"chart-div\" "
            f"style=\"height:{height}px\"></div>"
            f"  </div>"
            f"  {_tile_footer_html(w)}"
            f"</div>"
        )

    if wt == "kpi":
        label = w.get("label", "")
        val = w.get("value", "--")
        sub = w.get("sub", "")
        has_sparkline = bool(w.get("sparkline_source"))
        sub_html = (f'<div class="kpi-sub">{_html_escape(sub)}</div>'
                     if sub else "")
        sparkline_html = ('<div class="kpi-sparkline"></div>'
                           if has_sparkline else "")
        info_html = ""
        if w.get("info") or w.get("popup"):
            info_html = _popup_icon_html(
                info_text=w.get("info"),
                popup=w.get("popup"),
                fallback_title=w.get("label", w.get("title", "")),
                cls="tile-info tile-info-kpi",
            )
        cls = _tile_class(w, "tile kpi-tile")
        return (
            f"<div class=\"{cls}\" id=\"kpi-{_html_escape(wid)}\" "
            f"data-tile-id=\"{_html_escape(wid)}\" style=\"{style}\">"
            f"<div class=\"kpi-label\">{_html_escape(label)}{info_html}</div>"
            f"<div class=\"kpi-value\">{_html_escape(val)}</div>"
            f"<div class=\"kpi-delta\" style=\"display:none\"></div>"
            f"{sub_html}"
            f"{sparkline_html}"
            f"{_tile_footer_html(w)}"
            f"</div>"
        )

    if wt == "table":
        cls = _tile_class(w, "tile table-tile")
        return (
            f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
            f"style=\"{style}\">"
            f"  <div class=\"tile-header\">"
            f"    {_tile_title_html(w)}"
            f"  </div>"
            f"  <div class=\"tile-body\" id=\"table-{_html_escape(wid)}\"></div>"
            f"  {_tile_footer_html(w)}"
            f"</div>"
        )

    if wt == "markdown":
        cls = _tile_class(w, "tile markdown-tile")
        return (
            f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
            f"style=\"{style}\">"
            f"  <div class=\"tile-body markdown-body\">"
            f"{_render_md(w.get('content', ''))}</div>"
            f"  {_tile_footer_html(w)}"
            f"</div>"
        )

    if wt == "note":
        # Semantic callout. Tinted card with a colored left-edge stripe
        # keyed by `kind` so the reader can scan for "this is the
        # thesis" / "this is a risk" without reading prose. The body
        # is full markdown via the same renderer used by markdown
        # widgets; the title is plain text. An optional short icon
        # glyph renders to the left of the title.
        kind = str(w.get("kind", "insight"))
        title = w.get("title")
        icon = w.get("icon")
        body_md = w.get("body", "")
        cls = _tile_class(w, f"tile note-tile note-tile-{kind}")
        kind_label = {
            "insight": "Insight",
            "thesis":  "Thesis",
            "watch":   "Watch",
            "risk":    "Risk",
            "context": "Context",
            "fact":    "Fact",
        }.get(kind, kind.capitalize())
        head_parts: List[str] = []
        if icon:
            head_parts.append(
                f'<span class="note-icon">{_html_escape(str(icon))}</span>'
            )
        head_parts.append(
            f'<span class="note-kind">{_html_escape(kind_label)}</span>'
        )
        if title:
            head_parts.append(
                f'<span class="note-title">{_html_escape(str(title))}</span>'
            )
        head_html = (
            f'<div class="note-head">{"".join(head_parts)}</div>'
        )
        body_html = _render_md(body_md)
        return (
            f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
            f"data-note-kind=\"{_html_escape(kind)}\" "
            f"style=\"{style}\">"
            f"{head_html}"
            f"<div class=\"note-body markdown-body\">{body_html}</div>"
            f"{_tile_footer_html(w)}"
            f"</div>"
        )

    if wt == "divider":
        return (
            f"<div class=\"tile divider-tile\" data-tile-id=\"{_html_escape(wid)}\" "
            f"style=\"{_span_style(cols, cols)};grid-column:1/-1\">"
            f"<hr/></div>"
        )

    if wt == "stat_grid":
        stats = w.get("stats", [])
        cells: List[str] = []
        for st in stats:
            lbl = _html_escape(st.get("label", ""))
            val = _html_escape(st.get("value", "--"))
            sub = st.get("sub", "")
            sub_html = (f'<div class="stat-sub">{_html_escape(sub)}</div>'
                          if sub else "")
            info = st.get("info") or st.get("description")
            stat_popup = st.get("popup")
            info_html = (
                _popup_icon_html(
                    info_text=info,
                    popup=stat_popup,
                    fallback_title=st.get("label", ""),
                    cls="tile-info stat-info",
                )
                if info or stat_popup else ""
            )
            trend = st.get("trend")
            trend_cls = "pos" if trend and trend > 0 else (
                "neg" if trend and trend < 0 else "flat"
            )
            trend_arrow = (
                "\u25B2" if trend and trend > 0 else (
                    "\u25BC" if trend and trend < 0 else ""
                )
            )
            trend_html = (
                f'<span class="stat-trend {trend_cls}">{trend_arrow}</span>'
                if trend is not None and trend != 0 else ""
            )
            cell_tip = (f' title="{_html_escape(str(info))}"'
                          if info else "")
            cells.append(
                f'<div class="stat-cell"'
                f' data-stat-id="{_html_escape(st.get("id", ""))}"'
                f'{cell_tip}>'
                f'<div class="stat-label">{lbl}{info_html}</div>'
                f'<div class="stat-value">{trend_html}{val}</div>'
                f'{sub_html}</div>'
            )
        cls = _tile_class(w, "tile stat-grid-tile")
        return (
            f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
            f"style=\"{style}\">"
            f"  <div class=\"tile-header\">"
            f"    {_tile_title_html(w)}"
            f"  </div>"
            f"  <div class=\"tile-body\">"
            f"    <div class=\"stat-grid\" id=\"stat-grid-{_html_escape(wid)}\">"
            f"{''.join(cells)}</div>"
            f"  </div>"
            f"  {_tile_footer_html(w)}"
            f"</div>"
        )

    if wt == "image":
        title = w.get("title", "")
        src = w.get("src") or w.get("url") or ""
        alt = _html_escape(w.get("alt", title))
        link = w.get("link")
        img_html = (
            f'<img src="{_html_escape(src)}" alt="{alt}" '
            f'loading="lazy"/>'
        )
        if link:
            img_html = (
                f'<a href="{_html_escape(link)}" target="_blank" '
                f'rel="noopener noreferrer">{img_html}</a>'
            )
        header_html = (
            f"<div class=\"tile-header\">{_tile_title_html(w)}</div>"
            if title else ""
        )
        cls = _tile_class(w, "tile image-tile")
        return (
            f"<div class=\"{cls}\" data-tile-id=\"{_html_escape(wid)}\" "
            f"style=\"{style}\">"
            f"{header_html}"
            f"<div class=\"tile-body\">{img_html}</div>"
            f"{_tile_footer_html(w)}"
            f"</div>"
        )

    return ""


import re as _re

# Inline markdown regexes. The grammar is intentionally bounded (no
# full CommonMark / GFM compiler): links, bold, italic, strikethrough,
# inline code. Block-level constructs (headings, lists, blockquotes,
# fenced code, tables, hr) are handled by `_render_md` below.
_RE_LINK = _re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_BOLD = _re.compile(r"\*\*([^*]+)\*\*")
_RE_ITAL = _re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_RE_STRK = _re.compile(r"~~([^~]+)~~")
_RE_CODE = _re.compile(r"`([^`]+)`")

# Block-level regexes used by `_render_md`.
_RE_MD_HEADING = _re.compile(r"^(#{1,5})\s+(.*)$")
_RE_MD_OL_ITEM = _re.compile(r"^(\d+)\.\s+(.*)$")
_RE_MD_UL_ITEM = _re.compile(r"^[-*]\s+(.*)$")
_RE_MD_TABLE_SEP = _re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
_RE_MD_HR = _re.compile(r"^\s*([-*_])\s*\1\s*\1[\s\1]*$")


def _md_inline(text: str) -> str:
    """Escape the text then re-apply inline markdown for a safe
    subset: [label](url), **bold**, *italic*, ~~strike~~, `code`.
    URLs are passed through intact so we must be careful about
    escaping.
    """
    placeholders: List[str] = []
    def _stash_link(m):
        label, url = m.group(1), m.group(2)
        placeholders.append(
            f'<a href="{_html_escape(url)}" target="_blank"'
            f' rel="noopener noreferrer">{_html_escape(label)}</a>'
        )
        return f"\x00LINK{len(placeholders) - 1}\x00"

    staged = _RE_LINK.sub(_stash_link, text)
    escaped = _html_escape(staged)
    escaped = _RE_BOLD.sub(r"<strong>\1</strong>", escaped)
    escaped = _RE_ITAL.sub(r"<em>\1</em>", escaped)
    escaped = _RE_STRK.sub(r"<del>\1</del>", escaped)
    escaped = _RE_CODE.sub(r"<code>\1</code>", escaped)
    for i, ph in enumerate(placeholders):
        escaped = escaped.replace(f"\x00LINK{i}\x00", ph)
    return escaped


def _split_md_table_row(line: str) -> List[str]:
    """Split a markdown table row by `|`, trimming surrounding whitespace
    and dropping a leading/trailing empty cell when the row is fully
    bounded with `|` (e.g. `| a | b |`).
    """
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _parse_md_table_aligns(sep: str) -> List[Optional[str]]:
    """Parse a GFM separator row like `| :--- | ---: | :---: |` into a
    list of alignment hints (`left` / `right` / `center` / None).
    """
    cells = _split_md_table_row(sep)
    out: List[Optional[str]] = []
    for c in cells:
        c = c.strip()
        if c.startswith(":") and c.endswith(":"):
            out.append("center")
        elif c.endswith(":"):
            out.append("right")
        elif c.startswith(":"):
            out.append("left")
        else:
            out.append(None)
    return out


def _render_md(src: str) -> str:
    """Markdown renderer for prose-style dashboard content.

    Single source of truth for server-side prose rendering: markdown
    widget body, ``note`` widget body, and the dashboard summary
    banner. The JS twin ``_mdInlinePopup`` (defined in the dashboard
    shell script) mirrors this grammar for client-side popup bodies
    (info / methodology / row drill-down). Both must be upgraded
    together when extending the grammar.

    Block-level grammar:
      * ``# H1`` .. ``##### H5`` headings
      * blank-line separated paragraphs (lines within a paragraph are
        joined with a single space)
      * ``-`` / ``*`` unordered list items, ``1.`` ordered list items;
        nested via 2-space indent (each two leading spaces opens
        another list level)
      * ``> ...`` blockquotes (multi-line; consecutive ``>`` lines are
        collapsed and re-rendered through this same parser so quotes
        can carry their own headings, lists, and emphasis)
      * triple-backtick fenced code blocks (with optional language tag,
        rendered as ``<pre><code class="lang-<X>">``)
      * GFM-style tables: header row, ``| --- |`` separator (with
        optional ``:`` alignment hints), zero or more body rows
      * ``---`` / ``***`` / ``___`` on a line by itself for horizontal
        rules

    Inline grammar:
      ``**bold**``  ``*italic*``  ``~~strike~~``  ``` `code` ```
      ``[label](url)`` (always opens new tab)

    Anything that does not match is escaped as plain text.
    """
    lines = str(src).splitlines()
    n = len(lines)
    out: List[str] = []
    buf_para: List[str] = []
    quote_buf: List[str] = []
    # Parallel stacks: list_stack tracks (kind, indent) per open list,
    # li_open tracks whether the deepest <li> at that level is still
    # awaiting its closing tag. Keeping `<li>` open lets a nested
    # `<ul>` / `<ol>` live inside its parent `<li>`, which is the
    # only HTML-valid nesting shape.
    list_stack: List[Tuple[str, int]] = []
    li_open: List[bool] = []

    def flush_para():
        if buf_para:
            out.append(f"<p>{_md_inline(' '.join(buf_para))}</p>")
            buf_para.clear()

    def flush_quote():
        if quote_buf:
            inner = _render_md("\n".join(quote_buf))
            out.append(f"<blockquote>{inner}</blockquote>")
            quote_buf.clear()

    def close_top_list():
        kind, _ = list_stack.pop()
        if li_open.pop():
            out.append("</li>")
        out.append(f"</{kind}>")

    def close_all_lists():
        while list_stack:
            close_top_list()

    def push_list_item(kind: str, indent: int, text: str):
        # Step 1: pop all lists deeper than this indent (with their open
        # <li>, since the parent <li> at the shallower level is still
        # awaiting its close).
        while list_stack and list_stack[-1][1] > indent:
            close_top_list()
        # Step 2: at the same indent, close any open <li> sibling, and
        # if the kind switches (ul -> ol or vice versa) close that list
        # entirely so we can open a fresh one of the new kind.
        if list_stack and list_stack[-1][1] == indent:
            top_kind, _ = list_stack[-1]
            if top_kind != kind:
                close_top_list()
            else:
                if li_open[-1]:
                    out.append("</li>")
                    li_open[-1] = False
        # Step 3: if no list at this indent (either empty stack or
        # parent is shallower), open a new nested one INSIDE the
        # parent <li> (which we deliberately leave open).
        if not list_stack or list_stack[-1][1] < indent:
            list_stack.append((kind, indent))
            li_open.append(False)
            out.append(f"<{kind}>")
        # Step 4: open the new <li>; it stays open until either a
        # sibling closes it or a deeper list nests inside it.
        out.append(f"<li>{_md_inline(text)}")
        li_open[-1] = True

    i = 0
    while i < n:
        raw = lines[i]
        stripped = raw.lstrip()
        indent = len(raw) - len(stripped)
        s = stripped.rstrip()

        if s.startswith("```"):
            lang = s[3:].strip()
            flush_para(); flush_quote(); close_all_lists()
            buf: List[str] = []
            i += 1
            while i < n and not lines[i].lstrip().rstrip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(buf)
            cls = (f' class="lang-{_html_escape(lang)}"'
                   if lang else "")
            out.append(
                f"<pre><code{cls}>{_html_escape(code)}</code></pre>"
            )
            continue

        if "|" in s and i + 1 < n and \
           _RE_MD_TABLE_SEP.match(lines[i + 1].rstrip()):
            flush_para(); flush_quote(); close_all_lists()
            hdr = _split_md_table_row(s)
            aligns = _parse_md_table_aligns(lines[i + 1].rstrip())
            i += 2
            rows: List[List[str]] = []
            while i < n:
                rs = lines[i].rstrip()
                if "|" in rs and rs.strip():
                    rows.append(_split_md_table_row(rs))
                    i += 1
                else:
                    break
            tbl: List[str] = ['<table class="md-table">']
            tbl.append("<thead><tr>")
            for j, h in enumerate(hdr):
                al = aligns[j] if j < len(aligns) else None
                style = (f' style="text-align:{al}"' if al else "")
                tbl.append(f"<th{style}>{_md_inline(h)}</th>")
            tbl.append("</tr></thead><tbody>")
            for row in rows:
                tbl.append("<tr>")
                for j, c in enumerate(row):
                    al = aligns[j] if j < len(aligns) else None
                    style = (f' style="text-align:{al}"' if al else "")
                    tbl.append(f"<td{style}>{_md_inline(c)}</td>")
                tbl.append("</tr>")
            tbl.append("</tbody></table>")
            out.append("".join(tbl))
            continue

        if _RE_MD_HR.match(s):
            flush_para(); flush_quote(); close_all_lists()
            out.append("<hr/>")
            i += 1
            continue

        if s == "":
            flush_para(); flush_quote(); close_all_lists()
            i += 1
            continue

        h_match = _RE_MD_HEADING.match(s)
        if h_match:
            flush_para(); flush_quote(); close_all_lists()
            level = min(len(h_match.group(1)), 5)
            out.append(
                f"<h{level}>{_md_inline(h_match.group(2))}</h{level}>"
            )
            i += 1
            continue

        if s.startswith("> "):
            flush_para(); close_all_lists()
            quote_buf.append(s[2:])
            i += 1
            continue
        if s == ">":
            flush_para(); close_all_lists()
            quote_buf.append("")
            i += 1
            continue

        ol_match = _RE_MD_OL_ITEM.match(s)
        ul_match = _RE_MD_UL_ITEM.match(s)
        if ol_match or ul_match:
            flush_para(); flush_quote()
            kind = "ol" if ol_match else "ul"
            text = (ol_match.group(2) if ol_match
                    else ul_match.group(1))
            snapped = (indent // 2) * 2
            push_list_item(kind, snapped, text)
            i += 1
            continue

        flush_quote(); close_all_lists()
        buf_para.append(stripped)
        i += 1

    flush_para(); flush_quote(); close_all_lists()
    return "\n".join(out)


def _render_rows(rows: List[List[Dict[str, Any]]], cols: int) -> str:
    out = ["<div class=\"grid\">"]
    for row in rows:
        for w in row:
            out.append(_render_widget(w, cols))
    out.append("</div>")
    return "\n".join(out)


def _collect_specs(manifest: Dict[str, Any],
                    chart_specs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    def visit_rows(rows):
        for row in rows:
            for w in row:
                if w.get("widget") != "chart":
                    continue
                wid = w.get("id") or f"chart_{len(out)}"
                if wid in chart_specs:
                    out[wid] = chart_specs[wid]
                elif isinstance(w.get("option"), dict):
                    out[wid] = w["option"]
                elif isinstance(w.get("option_inline"), dict):
                    out[wid] = w["option_inline"]
                else:
                    out[wid] = {"series": []}

    layout = manifest.get("layout", {})
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            visit_rows(tab.get("rows", []) or [])
    else:
        visit_rows(layout.get("rows", []) or [])
    return out


def render_dashboard_html(
    manifest: Dict[str, Any],
    chart_specs: Dict[str, Dict[str, Any]],
    filename_base: Optional[str] = None,
) -> str:
    from echart_studio import __version__ as VERSION
    from datetime import datetime

    layout = manifest.get("layout", {})
    cols = int(layout.get("cols", 12))
    kind = layout.get("kind", "grid")

    # Split filters by scope: globals go in the top bar, "tab:<id>" filters
    # render inline inside their host tab panel. Filters without an
    # explicit scope default to global (_augment_manifest sets this).
    filters = manifest.get("filters", []) or []
    global_filters: List[Dict[str, Any]] = []
    per_tab_filters: Dict[str, List[Dict[str, Any]]] = {}
    for f in filters:
        scope = str(f.get("scope", "global"))
        if scope.startswith("tab:"):
            per_tab_filters.setdefault(scope[4:], []).append(f)
        else:
            global_filters.append(f)

    if kind == "tabs":
        tabs = layout.get("tabs", []) or []
        tab_btns: List[str] = []
        for t in tabs:
            tip = t.get("description", "")
            title_attr = (f' title="{_html_escape(tip)}"' if tip else "")
            tab_btns.append(
                f"<button class=\"tab-btn\""
                f" data-tab=\"{_html_escape(t['id'])}\"{title_attr}>"
                f"{_html_escape(t.get('label', t['id']))}</button>"
            )
        tab_bar_html = "<nav class=\"tab-bar\">" + "".join(tab_btns) + "</nav>"

        def _panel(t: Dict[str, Any]) -> str:
            tid = t["id"]
            header = (
                f"<div class=\"tab-panel-header\">"
                f"<h2>{_html_escape(t.get('description', ''))}</h2></div>"
                if t.get("description") else ""
            )
            inline_bar = _render_filter_controls(
                per_tab_filters.get(tid, []), inline=True,
                show_reset=bool(per_tab_filters.get(tid))
            )
            rows = _render_rows(t.get("rows", []) or [], cols)
            return (
                f"<section class=\"tab-panel\" "
                f"id=\"tab-panel-{_html_escape(tid)}\">"
                f"{header}{inline_bar}{rows}</section>"
            )
        panels_html = "\n".join(_panel(t) for t in tabs)
    else:
        tab_bar_html = ""
        panels_html = (
            "<section class=\"tab-panel active\" id=\"tab-panel-main\">"
            + _render_rows(layout.get("rows", []) or [], cols)
            + "</section>"
        )

    filter_bar_html = _render_filter_controls(global_filters, inline=False)

    # Optional dashboard-level summary banner. `metadata.summary` is a
    # short markdown blurb rendered below the filter bar and above the
    # first row / tab bar - the "today's read" header. Accepts either
    # a plain markdown string or a {title, body} dict where `title`
    # becomes a leading `<h2>` (so PRISM can label the banner without
    # the body needing its own `## Title` line).
    summary = (manifest.get("metadata") or {}).get("summary")
    if summary:
        if isinstance(summary, dict):
            s_title = summary.get("title")
            s_body = summary.get("body") or summary.get("text") or ""
        else:
            s_title = None
            s_body = str(summary)
        if s_body:
            head = (f"<h2>{_html_escape(str(s_title))}</h2>"
                    if s_title else "")
            summary_html = (
                f'<aside class="summary-banner markdown-body">'
                f'{head}{_render_md(s_body)}</aside>'
            )
        else:
            summary_html = ""
    else:
        summary_html = ""

    # Payload
    # The runtime JS reads DATASETS = PAYLOAD.datasets exclusively; nothing
    # in DASHBOARD_APP_JS references PAYLOAD.manifest.datasets. So the
    # canonical dataset copy lives in PAYLOAD.datasets and the manifest
    # copy in the payload is shipped without its datasets to avoid
    # serialising the rows twice (would otherwise ~double the HTML size
    # on data-heavy dashboards). The on-disk manifest.json written by
    # save_manifest() still includes datasets in full.
    specs = _collect_specs(manifest, chart_specs)
    datasets = manifest.get("datasets", {}) or {}
    manifest_for_payload = {k: v for k, v in manifest.items() if k != "datasets"}
    manifest_for_payload["datasets"] = {}
    payload = {
        "manifest": manifest_for_payload,
        "specs": specs,
        "datasets": datasets,
        "themes": {n: t["echarts"] for n, t in THEMES.items()},
        "palettes": {n: {"colors": list(p["colors"]), "kind": p["kind"]}
                      for n, p in PALETTES.items()},
    }
    payload_js = ("var PAYLOAD = "
                   + json.dumps(payload, default=_json_default)
                   + ";\n")

    title = manifest.get("title", "Dashboard")
    description = manifest.get("description", "")
    theme_name = manifest.get("theme", "gs_clean")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # GS brand tokens injected into CSS custom properties at render
    # time (keeps the stylesheet in lockstep with config.py).
    GS_TOKENS = {
        "__GS_NAVY__":       GS_NAVY,
        "__GS_NAVY_DEEP__":  GS_NAVY_DEEP,
        "__GS_SKY__":        GS_SKY,
        "__GS_INK__":        GS_INK,
        "__GS_PAPER__":      GS_PAPER,
        "__GS_BG__":         GS_BG,
        "__GS_GREY_70__":    GS_GREY_70,
        "__GS_GREY_40__":    GS_GREY_40,
        "__GS_GREY_20__":    GS_GREY_20,
        "__GS_GREY_10__":    GS_GREY_10,
        "__GS_GREY_05__":    GS_GREY_05,
        "__GS_POS__":        GS_POS,
        "__GS_NEG__":        GS_NEG,
        "__GS_FONT_SANS__":  GS_FONT_SANS,
        "__GS_FONT_SERIF__": GS_FONT_SERIF,
    }

    html = DASHBOARD_SHELL
    for k, v in GS_TOKENS.items():
        html = html.replace(k, v)
    html = (html
            .replace("__TITLE__", _html_escape(title))
            .replace("__DESCRIPTION__", _html_escape(description))
            .replace("__THEME__", _html_escape(theme_name))
            .replace("__COLS__", str(cols))
            .replace("__TAB_BAR__", tab_bar_html)
            .replace("__FILTER_BAR__", filter_bar_html)
            .replace("__SUMMARY__", summary_html)
            .replace("__TAB_PANELS__", panels_html)
            .replace("__TIMESTAMP__", _html_escape(ts))
            .replace("__VERSION__", VERSION)
            .replace("__PAYLOAD__", payload_js)
            .replace("__APP__", DASHBOARD_APP_JS))
    return html


# =============================================================================
# PART 3 -- PNG EXPORT (headless Chrome)
# =============================================================================
# Server-side PNG rendering via a tiny HTML harness + Chrome --screenshot.


_HARNESS = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>chart</title>
<style>
html,body{{margin:0;padding:0;width:{width}px;height:{height}px;
  background:{background};overflow:hidden;}}
#chart{{width:{width}px;height:{height}px;}}
</style>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
</head>
<body>
<div id="chart"></div>
<script>
(function(){{
  // Revive string-encoded functions (renderItem, formatter, filter) into
  // real JS functions. Python emits function bodies as strings because JSON
  // cannot carry code; ECharts needs real functions at setOption() time.
  function _isFnStr(s) {{
    return typeof s === 'string' && /^\\s*function\\s*\\(/.test(s);
  }}
  function _reviveFns(x) {{
    if (x == null) return x;
    if (_isFnStr(x)) {{
      try {{ return new Function('return (' + x + ')')(); }}
      catch(e) {{ return x; }}
    }}
    if (Array.isArray(x)) {{
      for (var i = 0; i < x.length; i++) x[i] = _reviveFns(x[i]);
      return x;
    }}
    if (typeof x === 'object') {{
      for (var k in x) {{
        if (Object.prototype.hasOwnProperty.call(x, k)) {{
          x[k] = _reviveFns(x[k]);
        }}
      }}
    }}
    return x;
  }}

  var OPTION = {option_json};
  var THEMES = {themes_json};
  var THEME_NAME = {theme_name_json};
  Object.keys(THEMES).forEach(function(k){{
    try {{ echarts.registerTheme(k, THEMES[k]); }} catch(e){{}}
  }});
  var inst = echarts.init(document.getElementById('chart'),
                            THEME_NAME in THEMES ? THEME_NAME : null,
                            {{renderer: 'canvas'}});
  // Strip interactive-only UI elements from the PNG output.
  delete OPTION.toolbox;
  delete OPTION.dataZoom;
  delete OPTION.brush;
  OPTION.animation = false;
  if (OPTION.series) {{
    (Array.isArray(OPTION.series) ? OPTION.series : [OPTION.series])
      .forEach(function(s){{ s.animation = false; }});
  }}
  OPTION = _reviveFns(OPTION);
  inst.setOption(OPTION, true);
  inst.on('finished', function(){{ document.title = 'rendered'; }});
}})();
</script>
</body>
</html>
"""


def find_chrome() -> str:
    """Locate the Chrome/Chromium binary. Raises RuntimeError if not found.

    Resolution order:
      1. $CHROME_BIN env var (absolute path)
      2. /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
      3. PATH lookup for google-chrome / chromium / chromium-browser / chrome
    """
    env = os.environ.get("CHROME_BIN")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return str(p)
        raise RuntimeError(
            f"CHROME_BIN={env!r} is set but the file does not exist."
        )
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(mac).is_file():
        return mac
    for candidate in ("google-chrome", "chromium", "chromium-browser",
                       "chrome", "Chromium"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError(
        "PNG export needs a Chrome/Chromium binary. Install Google Chrome "
        "or set the CHROME_BIN environment variable to the binary path."
    )


def save_chart_png(
    option: Union[Dict[str, Any], str],
    output_path: Union[str, Path],
    *,
    width: int = 900,
    height: int = 520,
    theme: str = "gs_clean",
    scale: int = 2,
    background: str = "#ffffff",
    virtual_time_ms: int = 2500,
    timeout_s: float = 30.0,
    verbose: bool = False,
) -> Path:
    """Render a single ECharts option to PNG via headless Chrome.

    Parameters
    ----------
    option : dict | str
        ECharts option object (or JSON string).
    output_path : str | Path
        Destination PNG path. Parent directories are created.
    width, height : int
        Logical chart dimensions (CSS pixels). Final PNG dimensions will
        be `width * scale` x `height * scale`.
    theme : str
        Theme name to apply (one of the THEMES keys). Defaults to
        ``gs_clean``. The theme spec is embedded and registered inline.
    scale : int
        Device-pixel multiplier (2 = retina). 1, 2, 3 supported.
    background : str
        Page background color. Use this for transparent exports by
        passing ``'rgba(0,0,0,0)'`` plus `--default-background-color=00000000`.
    virtual_time_ms : int
        How long to advance Chrome's virtual clock before the screenshot.
        Large charts with many series may need more.
    timeout_s : float
        Hard subprocess timeout.
    verbose : bool
        If True, prints the command line and the Chrome output.

    Returns
    -------
    Path
        Absolute path to the written PNG.
    """
    if isinstance(option, str):
        option = json.loads(option)
    if not isinstance(option, dict):
        raise TypeError(
            f"option must be a dict or JSON string, got {type(option).__name__}"
        )

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    themes_payload = {n: t.get("echarts", {}) for n, t in THEMES.items()}
    html = _HARNESS.format(
        width=int(width),
        height=int(height),
        background=background,
        option_json=json.dumps(option, default=str),
        themes_json=json.dumps(themes_payload, default=str),
        theme_name_json=json.dumps(theme),
    )

    chrome = find_chrome()
    tmp = Path(tempfile.mkdtemp(prefix="echarts_png_"))
    try:
        harness = tmp / "chart.html"
        harness.write_text(html, encoding="utf-8")
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--mute-audio",
            "--allow-file-access-from-files",
            f"--window-size={int(width)},{int(height)}",
            f"--force-device-scale-factor={int(scale)}",
            f"--virtual-time-budget={int(virtual_time_ms)}",
            "--run-all-compositor-stages-before-draw",
            f"--screenshot={output_path}",
            f"file://{harness}",
        ]
        if verbose:
            print("  [png_export] " + " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout_s)
        if verbose:
            if res.stdout:
                print(res.stdout.strip())
            if res.stderr:
                print(res.stderr.strip(), file=sys.stderr)
        if res.returncode != 0:
            raise RuntimeError(
                f"headless Chrome failed (exit {res.returncode}): "
                f"{(res.stderr or res.stdout).strip()}"
            )
        if not output_path.is_file():
            raise RuntimeError(
                f"Chrome did not write PNG to {output_path}. stderr: "
                f"{res.stderr.strip()}"
            )
        return output_path
    finally:
        try:
            for f in tmp.iterdir():
                try:
                    f.unlink()
                except OSError:
                    pass
            tmp.rmdir()
        except OSError:
            pass


def _cell_px(w_cols: int, container_px: int, cols: int, gap_px: int) -> int:
    """Approximate pixel width of a `w_cols`-wide cell in a `cols`-column grid.

    `container_px` is the total usable width after gutters.
    """
    w_cols = max(1, min(w_cols, cols))
    cell = (container_px - (cols - 1) * gap_px) / cols
    return int(round(cell * w_cols + (w_cols - 1) * gap_px))


def _has_existing_chart_title(t: Any) -> bool:
    if not t:
        return False
    if isinstance(t, list):
        return any(isinstance(x, dict) and x.get("text") for x in t)
    if isinstance(t, dict):
        return bool(t.get("text"))
    return False


def _inject_widget_title_into_option(
    opt: Dict[str, Any], w: Dict[str, Any]
) -> Tuple[Dict[str, Any], int]:
    """Bake the widget's tile title (and subtitle) into the chart option
    so PNG exports show what the user sees on the dashboard tile.

    The dashboard compiler clears ``opt.title.text`` to avoid double
    headlines on screen (the tile chrome already shows the title).
    That same stripping bites every PNG export -- in-browser via
    ``getDataURL()`` and headless-Chrome via ``save_chart_png``.
    This helper re-injects the title using GS type styles so the
    exported PNG has the title visually attached to the chart.

    Returns the (possibly mutated) option and the extra vertical
    pixels the title block consumes (so the caller can grow the
    canvas height accordingly and not squeeze the plot area).
    """
    title = w.get("title") or ""
    subtitle = w.get("subtitle") or ""
    if not title and not subtitle:
        return opt, 0
    if _has_existing_chart_title(opt.get("title")):
        return opt, 0
    spec = w.get("spec") or {}
    if isinstance(spec, dict) and spec.get("keep_title"):
        return opt, 0
    title_block = {
        "text": str(title),
        "subtext": str(subtitle),
        "left": 16,
        "top": 10,
        "textStyle": {
            "fontFamily": ('Goldman Sans, GS Sans, '
                            'Helvetica Neue, Arial, sans-serif'),
            "fontSize": 14, "fontWeight": 600, "color": "#1A1A1A",
        },
        "subtextStyle": {
            "fontFamily": ('Goldman Sans, GS Sans, '
                            'Helvetica Neue, Arial, sans-serif'),
            "fontSize": 11, "color": "#595959", "fontStyle": "italic",
        },
    }
    opt["title"] = [title_block]
    title_px = 26 + (18 if subtitle else 0) + 10
    grid = opt.get("grid")
    if isinstance(grid, list):
        for g in grid:
            if isinstance(g, dict):
                cur = g.get("top", 30)
                cur_n = cur if isinstance(cur, (int, float)) else 30
                g["top"] = int(cur_n) + title_px
    elif isinstance(grid, dict):
        cur = grid.get("top", 30)
        cur_n = cur if isinstance(cur, (int, float)) else 30
        grid["top"] = int(cur_n) + title_px
    return opt, title_px


def save_dashboard_pngs(
    manifest: Dict[str, Any],
    chart_specs: Dict[str, Dict[str, Any]],
    output_dir: Union[str, Path],
    *,
    theme: Optional[str] = None,
    scale: int = 2,
    container_px: int = 1400,
    gap_px: int = 14,
    min_width: int = 480,
    background: str = "#ffffff",
    virtual_time_ms: int = 2500,
    verbose: bool = False,
) -> List[Path]:
    """Render every chart widget in a dashboard as a separate PNG.

    Widget ``id`` becomes the filename stem. Widget pixel width is
    estimated from its grid span so the PNG matches the on-screen aspect.

    Parameters
    ----------
    manifest : dict
        The dashboard manifest (after validation).
    chart_specs : dict
        Mapping of chart widget id -> compiled ECharts option. This is
        exactly the output of ``_resolve_chart_specs()`` in
        ``echart_dashboard``.
    output_dir : str | Path
        Destination directory; created if missing.
    theme : str, optional
        Override theme; defaults to ``manifest['theme']`` or ``gs_clean``.
    scale : int
        Device-pixel multiplier.
    container_px : int
        Assumed dashboard container width (used to convert grid spans
        to pixel widths).
    gap_px : int
        Grid gap (matches dashboard CSS ``--gap``).
    min_width : int
        Floor for tiny tiles so PNGs remain legible.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    theme_name = theme or manifest.get("theme", "gs_clean")
    layout = manifest.get("layout", {}) or {}
    cols = int(layout.get("cols", 12))
    paths: List[Path] = []

    def visit(rows: List[List[Dict[str, Any]]]) -> None:
        for row in rows or []:
            for w in row or []:
                if w.get("widget") != "chart":
                    continue
                wid = w.get("id")
                opt = chart_specs.get(wid) or w.get("option")
                if not opt or not wid:
                    continue
                # Bake the tile title into the option so the PNG
                # actually shows what's on screen. _inject... is a
                # no-op when there's no widget title or the chart
                # already provides one (spec.keep_title=True).
                opt = json.loads(json.dumps(opt))
                opt, title_px = _inject_widget_title_into_option(opt, w)
                height = int(w.get("h_px", 320)) + title_px
                w_cols = int(w.get("w", cols))
                width = max(
                    min_width,
                    _cell_px(w_cols, container_px, cols, gap_px),
                )
                out = output_dir / f"{wid}.png"
                if verbose:
                    print(f"  rendering {wid}: {width}x{height} "
                          f"-> {out}")
                save_chart_png(
                    opt, out, width=width, height=height,
                    theme=theme_name, scale=scale,
                    background=background,
                    virtual_time_ms=virtual_time_ms,
                )
                paths.append(out)

    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []) or []:
            visit(tab.get("rows", []))
    else:
        visit(layout.get("rows", []))
    return paths


def save_dashboard_html_png(
    html_path: Union[str, Path],
    output_path: Union[str, Path],
    *,
    width: int = 1400,
    height: int = 1200,
    scale: int = 2,
    virtual_time_ms: int = 4500,
    timeout_s: float = 45.0,
    verbose: bool = False,
) -> Path:
    """Screenshot a full dashboard HTML file (or any local HTML) to PNG.

    Unlike save_dashboard_pngs() which renders one PNG per chart widget,
    this captures the entire dashboard page as a single PNG -- useful for
    gallery thumbnails, email embeds, and report previews.

    Width is the browser viewport; height should be enough to fit the
    full dashboard (scroll height is NOT auto-detected; the PNG is
    clipped to the viewport).

    Raises RuntimeError on Chrome failure.
    """
    html_path = Path(html_path).resolve()
    if not html_path.is_file():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chrome = find_chrome()
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        f"--window-size={int(width)},{int(height)}",
        f"--force-device-scale-factor={int(scale)}",
        f"--virtual-time-budget={int(virtual_time_ms)}",
        "--run-all-compositor-stages-before-draw",
        f"--screenshot={output_path}",
        f"file://{html_path}",
    ]
    if verbose:
        print("  [png_export] " + " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout_s)
    if verbose:
        if res.stdout:
            print(res.stdout.strip())
        if res.stderr:
            print(res.stderr.strip(), file=sys.stderr)
    if res.returncode != 0:
        raise RuntimeError(
            f"headless Chrome failed (exit {res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}"
        )
    if not output_path.is_file():
        raise RuntimeError(
            f"Chrome did not write PNG to {output_path}. stderr: "
            f"{res.stderr.strip()}"
        )
    return output_path


# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    "render_editor_html",
    "render_dashboard_html",
    "save_chart_png",
    "save_dashboard_pngs",
    "save_dashboard_html_png",
    "find_chrome",
]


# =============================================================================
# CLI (smoke test)
# =============================================================================

def _cli_interactive() -> int:
    print("""
rendering -- interactive menu

  1. render one chart sample to PNG
  2. render all chart samples to PNG (gs_clean theme)
  3. print Chrome binary path
  q. quit
""")
    choice = input("choice [q]: ").strip().lower() or "q"
    if choice == "q":
        return 0
    if choice == "3":
        try:
            print(f"chrome: {find_chrome()}")
        except RuntimeError as e:
            print(f"ERROR: {e}")
        return 0
    from samples import SAMPLES
    out_dir = input("output dir [pngs_demo]: ").strip() or "pngs_demo"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if choice == "1":
        names = sorted(SAMPLES.keys())
        print("\n".join(f"  {i+1}. {n}" for i, n in enumerate(names)))
        pick = input("sample [1]: ").strip() or "1"
        name = names[int(pick) - 1] if pick.isdigit() else pick
        path = save_chart_png(SAMPLES[name](), out / f"{name}.png",
                                verbose=True)
        print(f"wrote {path}")
    else:
        for name, fn in sorted(SAMPLES.items()):
            try:
                path = save_chart_png(fn(), out / f"{name}.png")
                print(f"  ok  {name:24s} -> {path}")
            except Exception as e:
                print(f"  FAIL {name}: {e}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return _cli_interactive()
    p = argparse.ArgumentParser(
        "rendering",
        description="HTML + PNG rendering smoke test.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    c1 = sub.add_parser("render",
                          help="render one option JSON file to PNG")
    c1.add_argument("input", help="path to JSON option file")
    c1.add_argument("-o", "--output", required=True,
                     help="output PNG path")
    c1.add_argument("--width", type=int, default=900)
    c1.add_argument("--height", type=int, default=520)
    c1.add_argument("--theme", default="gs_clean")
    c1.add_argument("--scale", type=int, default=2)
    c1.add_argument("--background", default="#ffffff")
    c1.add_argument("--verbose", action="store_true")

    c2 = sub.add_parser("samples",
                          help="render every chart sample to PNG")
    c2.add_argument("--output-dir", default="pngs_demo")
    c2.add_argument("--theme", default="gs_clean")
    c2.add_argument("--scale", type=int, default=2)
    c2.add_argument("--width", type=int, default=900)
    c2.add_argument("--height", type=int, default=520)

    c3 = sub.add_parser("chrome",
                          help="print Chrome binary path")

    args = p.parse_args(argv)
    if args.cmd == "render":
        option = json.loads(Path(args.input).read_text(encoding="utf-8"))
        path = save_chart_png(
            option, args.output,
            width=args.width, height=args.height,
            theme=args.theme, scale=args.scale,
            background=args.background,
            verbose=args.verbose,
        )
        print(f"wrote {path}")
        return 0
    if args.cmd == "samples":
        from samples import SAMPLES
        out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
        ok = fail = 0
        for name, fn in sorted(SAMPLES.items()):
            try:
                save_chart_png(
                    fn(), out / f"{name}.png",
                    width=args.width, height=args.height,
                    theme=args.theme, scale=args.scale,
                )
                print(f"  ok   {name:24s}")
                ok += 1
            except Exception as e:
                print(f"  FAIL {name}: {e}")
                fail += 1
        print(f"\n{ok} ok, {fail} failed. dir: {out.resolve()}")
        return 0 if fail == 0 else 1
    if args.cmd == "chrome":
        try:
            print(find_chrome())
            return 0
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
