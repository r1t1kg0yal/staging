# Charts and Dashboards

**Module:** charts_dashboards
**Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
**Tier:** 2 (on-demand)
**Scope:** ALL chart and dashboard construction in PRISM
**Engine:** ECharts (`GS/viz/echarts/`)

One system handles both one-off conversational charts and persistent, refreshable dashboards. PRISM never writes HTML. PRISM emits structured JSON; the compiler does the rest.

## Module file map

```
GS/viz/echarts/
  config.py             GS brand tokens + one theme + 3 palettes + dimensions
  echart_studio.py      single-chart producer: builders + knobs + CLI
  echart_dashboard.py   dashboard compiler: validator + manifest_template +
                          populate_template + Dashboard builder + CLI
  composites.py         multi-grid layouts (2/3/4/6-pack composition)
  rendering.py          single-chart editor HTML + dashboard HTML +
                          dashboard runtime JS + headless-Chrome PNG export
  samples.py            chart + dashboard samples + PRISM roleplay demos
  demos.py              5 consolidated end-to-end demo scenarios + CLI
  inspect_dashboard.py  visual diagnostics for compiled dashboards
  tests.py              full unit-test suite (171 tests)
  README.md             this file
  output/               generated demo dashboards (one folder per timestamp)
  inspect/              generated inspection artifacts
  archive/              legacy files kept for reference
```

`rendering.py` merges what used to be three separate files: the single-chart editor HTML template, the dashboard HTML template + runtime JS, and the PNG-export module. Public interface:

```python
from rendering import (
    render_editor_html, render_dashboard_html,
    save_chart_png, save_dashboard_pngs, save_dashboard_html_png,
    find_chrome,
)
```

There is exactly one visual style, the Goldman Sachs brand: GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans typeface stack, thin grey grid on paper-white. No theme switcher, no alternates.

---

## 0. The one hard rule: no literal data in JSON

PRISM pulls data with existing data functions (`pull_market_data`, `pull_haver_data`, FRED, Treasury, etc.) inside `execute_analysis_script`. The resulting DataFrames flow directly into the chart / dashboard JSON. **PRISM never types numbers into the JSON.** The compiler converts DataFrames to the canonical on-disk shape automatically.

```python
df_rates = pull_market_data(coordinates=['IR_USD_Swap_2Y', 'IR_USD_Swap_10Y'])
manifest = {
    "schema_version": 1, "id": "rates", "title": "US Rates",
    "datasets": {"rates": df_rates},                 # DataFrame -> source
    "layout": {"rows": [[{"widget": "chart", "id": "curve", "w": 12,
        "spec": {"chart_type": "multi_line", "dataset": "rates",
                  "mapping": {"x": "date", "y": ["us_2y", "us_10y"]}}}]]}
}
compile_dashboard(manifest, session_path=SESSION_PATH)
```

```python
# WRONG: never do this
manifest = {"datasets": {"rates": {"source": [
    ["date", "us_2y", "us_10y"],
    ["2026-04-20", 4.15, 4.48],    # <-- literal numbers in JSON
    ["2026-04-21", 4.17, 4.50],
    ...                             # <-- will get truncated, hallucinated, or stale
]}}}
```

Three accepted shapes for a dataset entry, all normalized to the same on-disk form:

| Shape                                              | When                                                         |
|----------------------------------------------------|--------------------------------------------------------------|
| `datasets["rates"] = df`                           | Most common. Zero ceremony.                                  |
| `datasets["rates"] = {"source": df}`               | When you want to attach metadata to the entry later.         |
| `datasets["rates"] = {"source": df_to_source(df)}` | When the manifest is saved/read before the compiler touches it. |

---

## 1. Two entry points + helpers

```python
# Inside execute_analysis_script these are injected into the namespace.
make_echart             # single chart -> option JSON + editor HTML + (optional) PNG
compile_dashboard       # manifest -> interactive dashboard HTML + manifest JSON (+ PNGs)
df_to_source            # DataFrame -> list-of-lists (rarely called directly)
manifest_template       # strip data from a manifest -> reusable template
populate_template       # template + fresh DataFrames -> ready-to-compile manifest
validate_manifest       # dry-run the validator without rendering
check_charts_quality    # PNG QC gate (unchanged from the prior system)

# Composite shortcuts (conversational multi-chart artifacts):
ChartSpec, make_2pack_horizontal, make_2pack_vertical,
make_3pack_triangle, make_4pack_grid, make_6pack_grid
```

One theme (`gs_clean`), three palettes (`gs_primary`, `gs_blues`, `gs_diverging`), twelve dimension presets + `custom`. No theme switcher. No skin config.

---

## 2. Single charts: `make_echart()`

### 2.1 Signature + `EChartResult`

```python
def make_echart(
    df: Any = None,
    chart_type: str = "line",
    mapping: Optional[Dict[str, Any]] = None,
    option: Optional[Dict[str, Any]] = None,   # passthrough mode
    title: Optional[str] = None,
    subtitle: Optional[str] = None,            # never source attribution
    theme: str = "gs_clean",
    palette: Optional[str] = None,             # defaults to gs_primary
    dimensions: str = "wide",                  # 12 named presets + custom
    annotations: Optional[List[Dict]] = None,
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None,          # filename slug
    save_as: Optional[str] = None,             # alternate output path
    write_html: bool = True,
    write_json: bool = True,
    save_png: bool = False,
    png_scale: int = 2,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
) -> EChartResult
```

Two invocation modes:

- **Builder mode:** pass `df` + `chart_type` + `mapping`. The per-type builder translates the inputs to an ECharts option.
- **Passthrough mode:** pass `option=...` and `chart_type="raw"` (or any type). The passed option is deep-copied, theme/palette are applied, and the wrap proceeds as usual.

`EChartResult` (dataclass; attribute access only):

| Field                          | Purpose                                                    |
|--------------------------------|------------------------------------------------------------|
| `option`                       | ECharts option dict                                        |
| `chart_id`                     | 12-char SHA-1 hash of canonical option                     |
| `chart_type`                   | Resolved chart type (`"composite"` for pack layouts)       |
| `theme`, `palette`, `dimension_preset`, `width`, `height` | Resolved style context        |
| `json_path`                    | Session path to the option JSON                            |
| `html_path`                    | Session path to the interactive editor HTML (~140 knobs)   |
| `png_path`                     | Session path to PNG (when `save_png=True` or after `.save_png()`) |
| `success`, `error_message`, `warnings` | Standard PRISM contract                            |
| `editor_download_url`, `download_url`, `editor_html_path`, `editor_chart_id` | Populated by the session/S3 layer when available |
| `knob_names`                   | Names of knobs exposed in the editor UI                    |
| `result.save_png(path, scale=2, width=..., height=..., background='#ffffff')` | Method: render this chart to PNG after the fact |

The editor HTML is the ECharts equivalent of Chart Center: clients can tweak title / axes / typography / palette / dimensions, export PNG / SVG / JSON, save spec sheets. For **aesthetic** changes, hand the user the editor link. For **data / structure** changes, re-call `make_echart()`.

`wrap_echart(option, ...)` takes a pre-built ECharts option dict and returns the editor HTML. Good for rehydrating a saved spec or wrapping a hand-rolled option.

### 2.2 Cosmetic / layout knobs (apply to every chart type)

These cross-cutting polish knobs live on `spec` (or `mapping`) and are applied after the builder runs, so every chart type honors them uniformly:

| Key (on `spec` or `mapping`) | Purpose                                                                                 |
|-------------------------------|-----------------------------------------------------------------------------------------|
| `legend_position`             | `"top"` (default), `"bottom"`, `"left"`, `"right"`, `"none"`. Hides legend if `none`. Auto-adjusts pie / donut to hide slice edge labels (rely on the legend). |
| `legend_show`                 | `True` / `False`. Overrides the default for the chart type.                             |
| `series_labels`               | Dict `{raw_name: display_name}` to override auto-humanised series names in legend.      |
| `humanize`                    | `True` (default) / `False`. Auto-humanises snake_case series / axis labels (`us_10y` -> `US 10Y`, `volume_m` -> `Volume M`, `beta` -> `Beta`). |
| `x_date_format`               | `"auto"` for compact `MMM D` tick labels on date axes; pass a raw ECharts function string for custom formatting. |
| `show_slice_labels` (pie/donut) | `True` to keep the per-slice edge labels even when the legend is placed top/bottom.  |
| `y_min` / `y_max`             | Force the y-axis range. Useful when auto-scale squashes a tight-range series against the plot floor (rates around 5% on a 0-9 axis). Applies to the value axis on horizontal charts. |
| `x_min` / `x_max`             | Force the x-axis range.                                                                 |
| `y_format` / `x_format`       | Numeric tick formatter preset. `"percent"` (x100 + %), `"bp"`, `"usd"`, `"compact"` (K/M/B suffix), or a raw ECharts function string. |
| `y_title_gap` / `x_title_gap` | Pixels between axis tick labels and axis title. Defaults: `52` for y, `36` for x (enough clearance for `50,000` / `2.38%`). Bump when you know tick labels are unusually wide. |
| `y_title_right_gap`           | Same, for the right y-axis on dual-axis charts.                                         |
| `grid_padding`                | Dict `{top, right, bottom, left}` overriding the plot-area margins. Auto-bumps `right` to 56 when a right-axis name is present. |
| `show_grid` / `show_axis_line` / `show_axis_ticks` | `False` to suppress the corresponding axis chrome (split lines, axis line, tick marks). Applies uniformly to x and y unless you gate them via `spec` vs `mapping`. |
| `series_colors`               | Dict `{col_name: "#hex"}`. Overrides the palette for specific series. Column name can be the raw column (`"us_2y"`) or the post-humanise display name (`"US 2Y"`). |
| `tooltip`                     | Spec-level tooltip override. Either a full ECharts `tooltip` dict, or a sugared form: `{"trigger": "axis" \| "item" \| "none", "decimals": 2, "formatter": "<JS fn string>", "show": False}`. `decimals` controls numeric-value rounding without writing a function. |

**Y-axis titles never collide with tick labels.** The default `y_title_gap` (52 px) and grid `left: 72` are tuned for comma-formatted numbers up to 5 digits. If you're rendering unusually wide labels (e.g. basis-point spreads up to `10,000 bp`) set `y_title_gap: 64` on that spec.

### 2.3 Chart types (24)

| chart_type         | Required mapping keys                                     |
|--------------------|-----------------------------------------------------------|
| `line`             | `x`, `y`, optional `color`                                |
| `multi_line`       | `x`, `y` (list) OR `x`, `y`, `color`                      |
| `bar`              | `x` (category), `y`, optional `color`, `stack` (bool)     |
| `bar_horizontal`   | `x` (value), `y` (category), optional `color`, `stack`    |
| `scatter`          | `x`, `y`, optional `color`, `size`, `trendline`           |
| `scatter_multi`    | `x`, `y`, `color`, optional `trendlines`                  |
| `area`             | `x`, `y` (stacked area)                                   |
| `heatmap`          | `x`, `y`, `value`                                         |
| `histogram`        | `x`, optional `bins` (int or list of edges), `density`    |
| `bullet`           | `y` (cat), `x` (cur), `x_low`, `x_high`, optional `color_by`, `label` |
| `pie`              | `category`, `value`                                       |
| `donut`            | `category`, `value`                                       |
| `boxplot`          | `x` (cat), `y`                                            |
| `sankey`           | `source`, `target`, `value`                               |
| `treemap`          | `path` (list) + `value`  OR  `name` + `parent` + `value`  |
| `sunburst`         | same as treemap                                           |
| `graph`            | `source`, `target`, `value`, `node_category`              |
| `candlestick`      | `x`, `open`, `close`, `low`, `high`                       |
| `radar`            | `category`, `value`, optional `series`                    |
| `gauge`            | `value` (number or column), optional `min`, `max`         |
| `calendar_heatmap` | `date`, `value`, optional `year`                          |
| `funnel`           | `category`, `value`                                       |
| `parallel_coords`  | `dims` (list), optional `color`                           |
| `tree`             | `name`, `parent`                                          |
| `raw`              | pass `option=...` directly                                |

Unknown `chart_type` -> `ValueError` with the full list. Datetime columns auto-resolve to `xAxis.type='time'`; numeric to `'value'`; everything else to `'category'`. Missing columns raise `ValueError` listing the actual DataFrame columns -- no silent fallback.

### 2.4 Core mapping keys (XY chart types)

| Key                  | Purpose                                                  |
|----------------------|----------------------------------------------------------|
| `x`, `y`             | Required column(s). `y` can be a list for wide-form multi_line. |
| `color`              | Grouping column (multi-series long form).                |
| `y_title`, `x_title` | Axis titles (plain English). Prefer these over coded column names. |
| `y_title_right`      | Right y-axis title when using dual-axis.                 |
| `x_sort`             | Explicit category order (list of values).                |
| `x_type`             | Force `'category'` / `'value'` / `'time'` on ambiguous columns. |
| `invert_y`           | Invert the y-axis (single-axis charts).                  |
| `y_log`, `x_log`     | Use log scale on the respective axis.                    |
| `stack` (bar)        | `True` (default) = stacked, `False` = grouped.           |
| `dual_axis_series`   | List of series-name strings to render on the right axis. |
| `invert_right_axis`  | Flip the right axis (rates-style "up = bullish").        |
| `strokeDash`         | Column controlling per-series dash pattern (e.g. actual vs estimate). |
| `strokeDashScale`    | `{"domain": [...], "range": [[1,0], [8,3]]}` explicit dash mapping. |
| `strokeDashLegend`   | `True` to include cross-product names in legend.         |
| `trendline` (scatter)  | `True` adds overall OLS line.                          |
| `trendlines` (scatter) | `True` adds per-group OLS lines.                       |
| `size` (scatter)     | Column driving marker size.                              |
| `bins` (histogram)   | Int or list of bin edges. Default 20.                    |
| `density` (histogram)| `True` normalizes counts to density.                     |

Chart-specific shapes:

| Chart                       | Mapping keys                                              |
|-----------------------------|-----------------------------------------------------------|
| `sankey`, `graph`           | `source`, `target`, `value`; `graph` adds `node_category` |
| `treemap`, `sunburst`       | `path` (list) + `value`, or `name` + `parent` + `value`   |
| `candlestick`               | `x`, `open`, `close`, `low`, `high`                       |
| `radar`                     | `category`, `value`, optional `series`                    |
| `gauge`                     | `value`, optional `min`, `max`                            |
| `calendar_heatmap`          | `date`, `value`, optional `year`                          |
| `parallel_coords`           | `dims` (list of columns), optional `color`                |
| `tree`                      | `name`, `parent`                                          |

### 2.5 Annotations

Five types, all specified as dicts in `annotations=[...]`:

```python
annotations=[
    {"type": "hline", "y": 2.0, "label": "Fed target",
      "color": "#666", "style": "dashed"},
    {"type": "vline", "x": "2022-03-15", "label": "Liftoff"},
    {"type": "band", "x1": "2020-03-01", "x2": "2020-06-01",
      "label": "COVID", "opacity": 0.3},
    {"type": "arrow", "x1": "2020-04-01", "y1": 5, "x2": "2021-03-01", "y2": 8,
      "label": "recovery"},
    {"type": "point", "x": "2023-06-15", "y": 4.4, "label": "peak"},
]
```

Common keys: `label`, `color`, `style` (`'solid'|'dashed'|'dotted'`), `stroke_dash` (list `[4,4]`), `stroke_width`, `label_color`, `label_position`, `opacity` (band), `head_size` / `head_type` (arrow), `font_size` (point). `band` also accepts `y1` / `y2` (horizontal band) and the aliases `x_start / x_end`, `y_start / y_end`.

For dual-axis charts, `hline` accepts `"axis": "right"` to anchor to the right y-axis.

Charts without axes (pie / donut / sankey / treemap / sunburst / radar / gauge / funnel / parallel_coords / tree) silently ignore annotations.

**Annotate regime changes, policy shifts, event dates, structural breaks.** Don't annotate self-evident facts (zero line on a spread chart; inflation target on every CPI chart).

### 2.6 Dimensions

12 named presets + `custom`. `wide` (700x350, default), `square` (450x450), `tall` (400x550), `compact` (400x300), `presentation` (900x500), `thumbnail` (300x200), `teams` (420x210), `report` (600x400), `dashboard` (800x500), `widescreen` (1200x500), `twopack` (540x360), `fourpack` (420x280), `custom` (600x400 -- preserves the caller's own size when that's already set).

Small presets (`teams`, `thumbnail`, `compact`) auto-downscale typography. When the request originates from Teams, always use `dimensions='teams'`.

### 2.7 Composites (conversational multi-chart single-artifact)

Five functions, all returning a single `EChartResult` whose `option` is a multi-grid ECharts composite. Sub-charts are `ChartSpec` objects passed positionally.

```python
r = make_2pack_horizontal(
    ChartSpec(df=df_rates, chart_type='multi_line',
                mapping={'x': 'date', 'y': ['us_2y', 'us_10y']},
                title='UST curve'),
    ChartSpec(df=df_spread, chart_type='line',
                mapping={'x': 'date', 'y': 'spread_bps'},
                title='2s10s spread'),
    title='Rates snapshot', subtitle='daily',
    session_path=SESSION_PATH,
)
r.save_png('rates_snapshot.png', scale=2)
```

| Function                  | Shape                         | Canvas     |
|---------------------------|-------------------------------|------------|
| `make_2pack_horizontal`   | 2 side-by-side                | 1200x450   |
| `make_2pack_vertical`     | 2 stacked                     | 700x750    |
| `make_3pack_triangle`     | 1 top full-width, 2 below     | 1100x750   |
| `make_4pack_grid`         | 2x2                           | 1200x800   |
| `make_6pack_grid`         | 3x2                           | 1400x900   |

`ChartSpec` fields: `df`, `chart_type`, `mapping`, `title`, `subtitle`, `annotations`, `theme`, `palette`, `dimensions`, `option` (raw passthrough).

Keyword args accepted by every composite function: `title`, `subtitle`, `theme`, `palette`, `dimension_preset`, `session_path`, `chart_name`, `save_as`, `write_html`, `write_json`, `user_id`. Composite PNGs via `result.save_png(...)`.

### 2.8 Quality gate

Every delivered chart / composite must pass through `check_charts_quality()` before it reaches the user. Fail-open: if Gemini is unavailable, all charts auto-pass.

```python
r1 = make_echart(df=df1, chart_type='multi_line', mapping={...},
                   session_path=SESSION_PATH, save_png=True)
r2 = make_echart(df=df2, chart_type='bar', mapping={...},
                   session_path=SESSION_PATH, save_png=True)

qc_results = check_charts_quality([r1, r2])
for r, qc in zip([r1, r2], qc_results):
    if not qc['passed']:
        print(f"FAIL: {r.png_path} -- {qc['reason']}")
        s3_manager.delete(r.png_path)
    else:
        print(f"PASS: {r.png_path}")
```

Failed PNGs MUST be deleted. Pass composite results as single PNGs (one entry per composite, not per sub-chart).

### 2.9 PNG export (Python-side)

Every chart can be rendered to a PNG without opening a browser. The `rendering` module invokes headless Chrome against a tiny self-hosted HTML harness that loads ECharts and calls `setOption`. Zero extra Python dependencies; only requires a Chrome/Chromium binary (auto-detected on macOS at `/Applications/Google Chrome.app/...`, overridable via the `CHROME_BIN` env var).

```python
from rendering import save_chart_png

save_chart_png(option, "chart.png",
               width=1000, height=520, theme="gs_clean", scale=2)

# or from an EChartResult
r = make_echart(df, "multi_line", mapping=..., title="UST yields")
r.save_png("yields.png", scale=2)
```

Dashboards can bulk-export one PNG per chart widget:

```python
compile_dashboard(
    manifest,
    output_path="out/macro.html",
    save_pngs=True,          # one PNG per chart widget
    png_scale=2,
)
# -> out/macro.html, out/macro.json, out/macro_pngs/{widget_id}.png
```

---

## 3. Dashboards

A dashboard is a JSON manifest. `compile_dashboard(manifest, ...)` is the only entry point. The compiler validates, resolves chart specs through the same builder dispatch `make_echart()` uses, renders the HTML via `rendering.render_dashboard_html`, and writes both artifacts.

### 3.1 Folder structure (the unit of organization)

For **conversational** (session-only) dashboards the compiler writes a flat pair under `{SESSION_PATH}/dashboards/`:

```
{SESSION_PATH}/dashboards/
  {id}.json        compiled manifest (data inline)
  {id}.html        compiled dashboard
{SESSION_PATH}/echarts/
  *.json           (optional) chart specs if a widget uses `ref`
  *.html           (optional) standalone chart editors
```

For **persistent user dashboards** (those that need to refresh on a schedule and appear in the user's dashboard list), the compiler writes into a self-contained per-dashboard folder under `users/{kerberos}/dashboards/{name}/`. That folder is the unit of organization; everything that belongs to a dashboard lives inside it.

```
users/{kerberos}/dashboards/{dashboard_name}/
│
├── manifest_template.json        SOURCE OF TRUTH (LLM-editable spec, NO data)
│       │     - schema_version, id, title, theme, palette
│       │     - metadata { kerberos, dashboard_id, refresh_enabled, ... }
│       │     - filters[], layout{}, links[]
│       │     - datasets:{name:{source:[[header_row]], template:true}}
│       │
│       └── This is the file PRISM reads + edits across turns.
│
├── manifest.json                 BUILD ARTIFACT (template + fresh data)
│       │     - same shape as template, but datasets fully populated
│       │     - written every refresh; reproduces the current dashboard exactly
│       │
│       └── Useful for: history snapshots, debugging "what was shown",
│           re-rendering offline via compile_dashboard(json.load(...)).
│
├── dashboard.html                DELIVERABLE (compile_dashboard output)
│       │     - self-contained, ECharts CDN, inline data
│       │     - refresh button auto-wired from metadata
│       │     - regenerated every refresh (no hand-rolled HTML inside)
│
├── refresh_status.json           STATE FILE (written by refresh pipeline)
│       │     {status, started_at, completed_at, errors[], pid, auto_healed}
│       │     status in {running, success, error, partial}
│
├── thumbnail.png                 OPTIONAL (rendering.save_dashboard_html_png)
│                                     for portal previews / email cards
│
├── scripts/
│   ├── pull_data.py              ONLY data acquisition (~50-150 lines)
│   │       │     - pull_market_data(), pull_haver_data(), FRED, etc.
│   │       │     - intraday-aware try/except (Section 4.5)
│   │       │     - writes raw outputs to ../data/*.csv | parquet
│   │       │     - prints progress every ~5s for long pulls
│   │
│   └── build.py                  BOILERPLATE (~15 lines, see Section 4.1)
│           │     - load manifest_template.json
│           │     - load raw data from ../data/
│           │     - populate_template(template, datasets)
│           │     - compile_dashboard(populated, output_path='..')
│
├── data/
│   ├── rates_eod.csv             RAW DATA CACHE (pull_data.py outputs)
│   ├── rates_intraday.csv             survives between refreshes; used by build.py
│   └── ...
│
└── history/                      OPTIONAL SNAPSHOTS (when keep_history=true)
    └── 20260424_153000/
        ├── manifest.json
        └── dashboard.html
```

Hygiene rules that fall out of this layout:

| Forbidden                              | Why                                                      |
|----------------------------------------|----------------------------------------------------------|
| HTML / CSS / JS in any `.py` file      | `rendering.py` owns it. PRISM emits structured JSON.     |
| `scripts/build_dashboard.py`           | Renamed to `build.py` (it's tiny). Old name is rejected. |
| `haver/`, `market_data/` folders       | All raw data goes in `data/`. Use `name=` on data fns.   |
| Timestamped scripts (`20260424_*.py`)  | `scripts/` is the only source dir. No development trace. |
| `*_results.md`, `*_artifacts.json`     | Session-only, not dashboard-scope.                       |
| Multiple data JSONs                    | `manifest.json` is the only one. No `dashboard_data.json`. |
| `make_chart()` PNGs in HTML            | ECharts renders client-side. PNGs go stale on refresh.   |
| Inline `<script>const DATA = {}` in HTML | Compiler embeds the manifest. Don't hand-edit HTML.    |
| `sanitize_html_booleans()` calls       | Compiler produces JSON-clean HTML. Helper is unnecessary. |
| `script_path=` round trips during build | Three-tool-call model writes scripts inline in tool 2.  |

The session folder remains the **execution environment** (scripts run with their working directory in `/tmp/<session>/...`) but persistent dashboards write outputs directly to the dashboard folder on S3, not to `SESSION_PATH`.

### 3.2 Manifest shape

```python
manifest = {
    "schema_version": 1,
    "id": "rates_monitor",            # slug; used as filename
    "title": "Rates monitor",
    "description": "Curve, spread, KPIs.",   # optional; shown under the title
    "theme": "gs_clean",              # optional; default gs_clean
    "palette": "gs_primary",          # optional; default palette-of-theme

    "metadata": {                     # optional; see 3.3
        "kerberos": "goyairl",
        "dashboard_id": "rates_monitor",
        "data_as_of": "2026-04-24T15:00:00Z",
        "generated_at": "2026-04-24T15:05:00Z",
        "sources": ["GS Market Data", "Haver"],
        "refresh_frequency": "daily",
        "refresh_enabled": True,
        "tags": ["rates", "curve"],
        "version": "1.0.0",
    },

    "header_actions": [               # optional; see 3.10
        {"label": "Open registry",
          "href": "/users/goyairl/dashboards/", "icon": "\u2198"},
    ],

    "datasets": {
        "rates": df_rates,            # DataFrame -> auto-converted
        "cpi":   {"source": df_cpi},  # explicit form works too
    },

    "filters": [                      # optional
        {"id": "dt", "type": "dateRange", "default": "6M",
          "targets": ["*"], "field": "date"},
    ],

    "layout": {
        "kind": "tabs",               # or "grid" (default)
        "tabs": [{
            "id": "overview", "label": "Overview",
            "description": "Headline rates + spread",
            "rows": [
                [{"widget": "kpi", "id": "k10y", "label": "10Y",
                   "source": "rates.latest.us_10y", "suffix": "%", "w": 4},
                 {"widget": "kpi", "id": "k2y", "label": "2Y",
                   "source": "rates.latest.us_2y", "suffix": "%", "w": 4},
                 {"widget": "kpi", "id": "k2s10s", "label": "2s10s",
                   "source": "rates.latest.2s10s", "suffix": "bp", "w": 4}],
                [{"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
                   "spec": {"chart_type": "multi_line", "dataset": "rates",
                             "mapping": {"x": "date",
                                          "y": ["us_2y", "us_5y", "us_10y", "us_30y"]},
                             "title": "UST curve"}}],
            ],
        }],
    },

    "links": [                        # optional (connect + brush cross-filter)
        {"group": "rates_sync", "members": ["curve"],
          "sync": ["axis", "tooltip"]},
    ],
}

compile_dashboard(manifest, session_path=SESSION_PATH)
```

**Manifest-level knobs:**

| Field                 | Purpose                                                                            |
|-----------------------|------------------------------------------------------------------------------------|
| `title` / `description` | Header title + subtitle.                                                         |
| `theme`               | `gs_clean` (default). The only built-in theme.                                     |
| `palette`             | `gs_primary` (default, categorical), `gs_blues` (sequential), `gs_diverging`.      |
| `metadata`            | Provenance + refresh block; see 3.3.                                               |
| `header_actions`      | Custom header buttons / links; see 3.10.                                           |
| `datasets`            | `{name: DataFrame | {"source": ...}}`.                                             |
| `filters`             | See 3.7.                                                                           |
| `layout`              | `grid` or `tabs`; see 3.9.                                                         |
| `links`               | sync + brush wiring; see 3.8.                                                      |

`compile_dashboard` parameters:

| Parameter            | Purpose                                                   |
|----------------------|-----------------------------------------------------------|
| `manifest`           | Dict, JSON string, or path to a manifest JSON file.        |
| `session_path`       | Writes `{sp}/dashboards/{id}.json` + `{id}.html`.          |
| `output_path`        | Explicit HTML path; the .json is written alongside.        |
| `write_html` / `write_json` | Disable either emit independently.                  |
| `save_pngs=True`     | Also render each chart widget to PNG.                      |
| `png_dir`            | Override the PNG output directory.                         |
| `png_scale=2`        | Device-pixel multiplier for PNG.                           |

### 3.3 Metadata block (refresh + provenance)

The optional `manifest.metadata` block is the single place where data provenance and refresh configuration live. It drives the **data-freshness badge** (header) and the **refresh button** (header). All fields are optional -- omit them for pure session-scope artifacts, set them for persistent dashboards.

| Field                    | Type         | Purpose                                                             |
|--------------------------|--------------|---------------------------------------------------------------------|
| `kerberos`               | `str`        | User kerberos; required for the refresh button to render.           |
| `dashboard_id`           | `str`        | Id for the refresh API; defaults to `manifest.id`.                  |
| `data_as_of`             | `str` (ISO)  | Timestamp of the underlying data -- renders in the header badge.    |
| `generated_at`           | `str` (ISO)  | When this manifest was compiled. Used as a fallback for the badge.  |
| `sources`                | `list[str]`  | Data source names (e.g. `["GS Market Data", "Haver"]`).             |
| `refresh_frequency`      | `str`        | One of `hourly | daily | weekly | manual`.                          |
| `refresh_enabled`        | `bool`       | Set `False` to hide the refresh button (even if kerberos is set).   |
| `tags`                   | `list[str]`  | Free-form tags; echoed into the registry.                           |
| `version`                | `str`        | Manifest version string.                                            |
| `api_url`                | `str`        | Refresh endpoint override (default `/api/dashboard/refresh/`).      |
| `status_url`             | `str`        | Status endpoint override (default `/api/dashboard/refresh/status/`).|

### 3.4 Chart widget variants: `spec` / `ref` / `option`

Every `widget: chart` declares one of three variants. Use the lowest ceremony that fits.

| Variant   | Shape                                                  | When to use                                             |
|-----------|--------------------------------------------------------|---------------------------------------------------------|
| `spec`    | `{chart_type, dataset, mapping, [title, palette, ...]}` | **Preferred.** LLM-friendly. Data lives in manifest.   |
| `ref`     | `"echarts/mychart.json"`                                | When you have pre-emitted spec JSON from `make_echart`. |
| `option`  | raw ECharts option dict                                | Passthrough for hand-crafted options / tests.           |

`spec.dataset` references `manifest.datasets.<name>`. At compile time the source rows are materialized into a pandas DataFrame and fed into the same `_BUILDER_DISPATCH` that `make_echart()` uses. `spec.chart_type` must be one of the 24 supported types.

Per-spec `palette`, `theme`, `subtitle`, `title`, `dimensions`, `annotations` override the manifest-level defaults. Required keys: `chart_type`, `dataset`, `mapping`.

`ref` paths resolve relative to (1) `base_dir` argument if supplied, (2) the loaded manifest file's parent directory when `compile_dashboard(path)` is called with a path, (3) current working directory.

### 3.5 Widgets

| widget      | Required                                | Purpose                              |
|-------------|-----------------------------------------|--------------------------------------|
| `chart`     | `id`, one of `spec` / `ref` / `option`  | ECharts canvas tile                  |
| `kpi`       | `id`, `label`                           | Big-number tile + delta + sparkline  |
| `table`     | `id`, `ref` or `dataset_ref`            | Rich table with sort / search / format / popup |
| `stat_grid` | `id`, `stats[]`                         | Dense grid of label/value stats      |
| `image`     | `id`, `src` or `url`                    | Embed a static image or logo         |
| `markdown`  | `id`, `content`                         | Freeform markdown text block         |
| `divider`   | `id`                                    | Horizontal rule, forces row break    |

Common optional fields: `w` (1-12 grid span), `h_px` (chart only; default 280), `title`.

**Widget presentation knobs (apply to every tile type):**

| Field            | Purpose                                                                                   |
|------------------|-------------------------------------------------------------------------------------------|
| `title`          | Card header text. When set on a chart, the internal ECharts title is auto-suppressed so the chart doesn't show a duplicate headline. Set `spec.keep_title: True` to opt out. |
| `subtitle`       | Secondary italic text rendered under the title in the tile header. Great for methodology notes, data vintage, scope disclaimers ("daily OHLC", "3Y rolling window"). |
| `footer`         | Small text rendered below the tile body, separated by a dashed border. Useful for source attribution, methodology caveats, refresh cadence notes. `footnote` is accepted as an alias. |
| `info`           | Short help string. Renders an `\u24D8` icon; hover shows it as a native tooltip, **clicking opens a modal** with the same text (so long blurbs are still readable + dismissable). |
| `popup`          | `{title, body}` for the modal when the `\u24D8` icon is clicked. `body` is markdown (same grammar as the markdown widget: headings / bullets / **bold** / *italic* / `code` / [links](url)). Takes precedence over `info` for the modal content; `info` stays as the hover tooltip. |
| `badge`          | Short string (1-6 characters) rendered as a pill next to the title -- e.g. `"LIVE"`, `"BETA"`, `"NEW"`. Pair with `badge_color` (`"gs-navy"` default / `"sky"` / `"pos"` / `"neg"` / `"muted"`). |
| `emphasis`       | `True` highlights the tile with a thicker navy border + subtle shadow. KPIs get a sky-blue top border accent. Use sparingly for the one stat that matters most. |
| `pinned`         | `True` makes the tile sticky to the top of the viewport while the user scrolls. Good for a KPI row the reader always needs in view. |
| `action_buttons` | List of extra buttons rendered in the chart toolbar alongside the built-in PNG / fullscreen buttons. Each is `{label, icon?, href?, onclick?, primary?, title?}`. `href` opens a new tab; `onclick` names a global JS function (e.g. `"customRun"`) called with the widget id. |
| `click_emit_filter` | (chart widgets only) Turn data-point clicks into filter changes. Either a bare filter id string, or `{filter_id, value_from, toggle}` where `value_from` is `"name"` (default), `"value"`, or `"seriesName"` and `toggle` defaults `True` (re-clicking the same value clears the filter). Wire this to a `select` / `radio` filter whose `targets` point at downstream widgets for click-through filtering. |

Example chart widget using all the presentation knobs:

```json
{
  "widget": "chart", "id": "price_chart", "w": 12, "h_px": 440,
  "title": "ACME daily OHLC (1Y)",
  "badge": "LIVE", "badge_color": "pos",
  "info": "Daily OHLC. Drag the brush at the bottom to zoom.",
  "footer": "Source: GS Market Data \u00B7 Updated at market close.",
  "action_buttons": [
    {"label": "Open in portal", "icon": "\u2197",
      "href": "https://example.com/acme"}
  ],
  "spec": { "chart_type": "candlestick", "dataset": "ohlc",
            "mapping": {"x": "date", "open": "open", "close": "close",
                         "low": "low", "high": "high"} }
}
```

### 3.6 KPI / table / stat_grid / image / markdown / divider

**KPI widget**

| Key                    | Purpose                                                    |
|------------------------|------------------------------------------------------------|
| `value`                | Direct value override (skips `source`).                    |
| `source`               | Dotted: `<dataset>.<agg>.<column>`. Agg ∈ `latest | first | sum | mean | min | max | count | prev`. |
| `sub`                  | Subtext under the value.                                   |
| `delta`                | Direct delta value.                                        |
| `delta_source`         | Dotted source (typically `<dataset>.prev.<column>`) -- delta = current − prev. |
| `delta_pct`            | Direct percent change (otherwise auto-computed from `delta_source`). |
| `delta_label`          | Label appended after the delta (e.g. `"vs prev"`).         |
| `delta_decimals`       | Precision for the delta (default 2).                       |
| `prefix`, `suffix`     | Prepended/appended to the value (e.g. `$`, `%`, `bp`).     |
| `decimals`             | Precision for the value (default 2 for < 1000, else 0).    |
| `sparkline_source`     | Dotted: `<dataset>.<column>`; renders an inline sparkline. |
| `format`               | `"auto"` (default; commas < 1M, compact abbrev >= 1M), `"compact"` (always K/M/B/T), `"comma"` (always full digits), `"percent"` (multiply by 100, suffix %), `"raw"` (no grouping). |

Example: `{"widget": "kpi", "id": "k10y", "label": "10Y", "source": "rates.latest.us_10y", "suffix": "%", "delta_source": "rates.prev.us_10y", "delta_label": "vs prev", "sparkline_source": "rates.us_10y", "w": 3}`

With `format="auto"` the KPI renders `2820` as `2,820` (not `3K`). Use `format="compact"` on KPIs where abbreviated labels are explicitly desired.

**Rich table widget**

Pass `dataset_ref` and the table renders every column by default. For production dashboards, declare a `columns[]` config for per-column labels, formatters, tooltips, conditional formatting, and color scales, plus search / sort / row-click popups.

```json
{
  "widget": "table", "id": "rv_table", "w": 12,
  "dataset_ref": "rv",
  "title": "RV screen (click a row for detail)",
  "searchable": true, "sortable": true,
  "max_rows": 50, "row_height": "compact",
  "empty_message": "No metrics match the current filters.",
  "columns": [
    {"field": "metric", "label": "Metric", "align": "left",
      "tooltip": "RV metric name"},
    {"field": "current", "label": "Current",
      "format": "number:2", "align": "right"},
    {"field": "z", "label": "Z",
      "format": "signed:2", "align": "right",
      "tooltip": "5Y rolling z-score",
      "color_scale": {"min": -2, "max": 2, "palette": "gs_diverging"}},
    {"field": "pct", "label": "Pctile",
      "format": "percent:0", "align": "right",
      "conditional": [
        {"op": ">=", "value": 0.85,
          "background": "#c53030", "color": "#fff", "bold": true},
        {"op": ">=", "value": 0.70, "background": "#fed7d7"},
        {"op": "<=", "value": 0.15,
          "background": "#2b6cb0", "color": "#fff", "bold": true}
      ]},
    {"field": "ytd_chg", "label": "YTD \u0394",
      "format": "delta:2", "align": "right",
      "conditional": [
        {"op": ">", "value": 0, "color": "#38a169"},
        {"op": "<", "value": 0, "color": "#c53030"}
      ]}
  ],
  "row_click": {
    "title_field": "metric",
    "popup_fields": ["metric", "current", "z", "pct", "ytd_chg", "note"]
  }
}
```

Per-column fields:

| Key            | Type          | Purpose                                         |
|----------------|---------------|-------------------------------------------------|
| `field`        | str (required)| Column name in the dataset source.              |
| `label`        | str           | Header label (defaults to field).               |
| `format`       | str           | `text` / `number[:d]` / `integer` / `percent[:d]` / `currency[:d]` / `bps[:d]` / `signed[:d]` / `delta[:d]` / `date` / `datetime` / `link` |
| `align`        | str           | `left` / `center` / `right` (auto-right for numeric formats). |
| `sortable`     | bool          | Defaults to the table-level `sortable`.         |
| `tooltip`      | str           | Hover text on header and cells in this column.  |
| `conditional`  | list          | Rules fired first-match-wins. Each rule: `{op, value, background?, color?, bold?}`. `op` uses the filter ops set. |
| `color_scale`  | dict          | Continuous heatmap: `{min, max, palette}` where palette is a manifest palette name (prefer `gs_diverging` / `gs_blues`). |

Table-level fields: `searchable` (search input + row count), `sortable` (header click reorders), `row_height` (`compact` / default), `max_rows` (viewport cap, default 100), `empty_message`.

**`row_click`** opens a click-popup modal when any row is clicked. Two modes:

*Simple mode* -- key/value table of the row's fields:

```json
"row_click": {
  "title_field": "ticker",
  "popup_fields": ["ticker", "sector", "last", "d1_pct"]
}
```

*Rich drill-down mode* -- full mini-dashboard inside the modal. Sections can include stats, markdown (with `{field}` template substitution), charts filtered to the clicked row, and sub-tables. The modal widens to 880 px when `detail.wide: True` (the default). Example:

```json
"row_click": {
  "title_field": "issuer",
  "subtitle_template": "CUSIP {cusip} · {coupon_pct:number:2}% coupon · matures {maturity}",
  "detail": {
    "wide": true,
    "sections": [
      {"type": "stats",
        "fields": [
          {"field": "price",    "label": "Price",    "format": "number:2"},
          {"field": "ytm_pct",  "label": "YTM",      "format": "number:2", "suffix": "%"},
          {"field": "spread_bp","label": "Spread",   "format": "number:0", "suffix": " bp"},
          {"field": "duration_yrs","label": "Duration","format": "number:2","suffix": " yrs"}
        ]},
      {"type": "markdown",
        "template": "**{issuer}** · *{sector}* · rated `{rating}`.\n\nCoupon {coupon_pct:number:3}%, matures **{maturity}**."},
      {"type": "chart",
        "title": "Price history (180 biz days)",
        "chart_type": "line",
        "dataset": "bond_hist",          // a dataset in manifest.datasets
        "row_key": "cusip",              // column on this table
        "filter_field": "cusip",          // column on `bond_hist`
        "mapping": {"x": "date", "y": "price", "y_title": "Clean price"},
        "height": 220},
      {"type": "table",
        "title": "Recent events",
        "dataset": "bond_events",
        "row_key": "issuer",
        "filter_field": "issuer",
        "max_rows": 6,
        "columns": [
          {"field": "date", "label": "Date"},
          {"field": "event", "label": "Event"},
          {"field": "reaction", "label": "Spread reaction"}
        ]}
    ]
  }
}
```

**Section types inside `detail.sections`:**

| Type         | Purpose                                                                                       |
|--------------|-----------------------------------------------------------------------------------------------|
| `stats`      | Dense KPI-style row. `fields[]` can be a string (column name) or `{field, label, format, prefix, suffix, sub, signed_color}`. |
| `markdown`   | Paragraph with `{field}` / `{field:format}` template substitution. Supports the same inline grammar as the markdown widget (bold / italic / `code` / [links](url) / bullets / headings). |
| `chart`      | Embedded mini-chart. `chart_type` one of `line` / `bar` / `area`; dataset + filter_field / row_key to scope to the clicked row. Supports `mapping.y` as a column or a list of columns, `annotations` (hline / vline / band), and a numeric `height`. |
| `table`      | Sub-table driven by a filtered manifest dataset, same filter_field / row_key pattern. `max_rows` caps length. |
| `kv` / `kv_table` | Key/value table for a subset of `row` fields (useful to split the row into multiple themed panels). |

**Template substitution** (`{field:format}`):

Template strings in `subtitle_template` / markdown section `template` / stats field `sub` support placeholders like `{field}` and `{field:format}`. Formats match the column formats: `number:N`, `signed:N`, `percent:N`, `currency:N`, `bps:N`, `delta:N`, `date`. Unknown fields pass through untouched.

**Modal close** (same as simple mode): X button, ESC, or overlay click.

`row_click.extra_content` (HTML string) is still honored as a postscript on simple mode. On rich mode it's ignored -- use a `markdown` section instead.

**Row-level highlighting**: `row_highlight` is a list of rules evaluated per row; first match wins. Each rule is `{field, op, value, class}` where `op` is one of `==, !=, >, >=, <, <=, contains, startsWith, endsWith` and `class` is one of `"pos"`, `"neg"`, `"warn"`, `"info"`, `"muted"`. The row gets a subtle tinted background plus a left-edge accent stripe that doesn't stomp per-cell conditional colors.

```json
"row_highlight": [
  {"field": "d1_pct", "op": ">",  "value":  2.0, "class": "pos"},
  {"field": "d1_pct", "op": "<",  "value": -2.0, "class": "neg"},
  {"field": "ticker", "op": "==", "value": "GS",  "class": "info"}
]
```

**stat_grid widget**

Dense grid of label / value stats -- for when a row of KPIs would take too much vertical space.

```json
{"widget": "stat_grid", "id": "summary", "w": 12,
  "title": "Risk summary",
  "info": "Rolling risk metrics aggregated across the full book.",
  "stats": [
    {"id": "s1", "label": "Beta to SPX",   "value": "0.82",  "sub": "60D",
      "trend": 0.04,
      "info": "OLS beta of book P&L vs S&P 500 TR, trailing 60 biz days."},
    {"id": "s2", "label": "Duration",      "value": "4.8y",  "sub": "DV01 $280k",
      "info": "Book-weighted modified duration across rates positions."},
    {"id": "s3", "label": "Gross leverage","value": "2.3x",  "sub": "vs 3.0x cap",
      "trend": 0.1},
    {"id": "s4", "label": "HY OAS",        "value": "285 bp","sub": "z = -1.1",
      "trend": -0.05}
  ]}
```

Per-stat fields:

| Field    | Purpose                                                                                      |
|----------|----------------------------------------------------------------------------------------------|
| `id`     | Optional id for DOM addressing.                                                              |
| `label`  | Title line (small caps, dim).                                                                |
| `value`  | The stat itself. Pre-format; no number formatting is applied here.                           |
| `source` | Alternative to `value`: dotted `<dataset>.<agg>.<column>` expression evaluated at render. |
| `sub`    | Smaller secondary caption below the value.                                                   |
| `info`   | Short help text. Shows an `\u24D8` icon next to the label; hover shows it as a tooltip + cell `title=`, **clicking opens a modal** with the same text. `description` is an alias. |
| `popup`  | `{title, body}` markdown popup for click (takes priority over `info` for modal content). |
| `trend`  | Optional numeric delta. Positive renders a green `\u25B2`, negative a red `\u25BC`, neither when `0` or absent. |

**image / markdown / divider widgets**

```json
{"widget": "image", "id": "logo", "w": 3,
  "src": "https://.../gs_logo.png",
  "alt": "Goldman Sachs",
  "link": "https://..."}

{"widget": "markdown", "id": "md", "w": 12,
  "content": "### Method\nSynthetic UST panel. **Brush** the curve to cross-filter.\n\n- Source: [GS Market Data](https://example.com)\n- Refresh: daily\n- Scope: US only"}

{"widget": "divider", "id": "sep"}
```

Markdown supports a strict subset: `#` / `##` / `###` headings, blank-line paragraph breaks, `- ` / `* ` bullets, `**bold**`, `*italic*`, `` `code` ``, `[label](url)` (always opens new tab). Anything else is escaped.

### 3.7 Filters

```json
{"id": "region", "type": "multiSelect", "default": ["US", "EU"],
  "options": ["US", "EU", "JP", "UK"],
  "targets": ["*"], "field": "region", "label": "Region"}
```

**Nine filter types:**

| Type          | UI                              | Applies to                                  |
|---------------|---------------------------------|---------------------------------------------|
| `dateRange`   | select of 1M/3M/6M/YTD/1Y/2Y/5Y/All | `rows[field]` within resolved date range |
| `select`      | `<select>`                      | `rows[field] == value`                      |
| `multiSelect` | `<select multiple>`             | `rows[field] in [values]`                   |
| `radio`       | radio button group              | same as `select`, different UI              |
| `numberRange` | text `min,max`                  | `min <= rows[field] <= max`                 |
| `slider`      | `<input type="range">` + value  | `rows[field] op value` (op defaults `>=`)   |
| `number`      | `<input type="number">`         | `rows[field] op value` (op defaults `>=`)   |
| `text`        | `<input type="text">`           | `rows[field] op value` (op defaults `contains`) |
| `toggle`      | checkbox                        | `rows[field]` truthy when checked           |

**Fields:**

| Field        | Purpose                                                       |
|--------------|---------------------------------------------------------------|
| `id`         | Required; unique within manifest.                             |
| `type`       | Required; one of the 9 above.                                 |
| `default`    | Initial value.                                                |
| `field`      | Dataset column to filter against.                             |
| `op`         | Comparator: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`. |
| `transform`  | `abs` / `neg` applied to the cell before compare (e.g. `|z|` filters). |
| `options`    | Required for `select`, `multiSelect`, `radio`.                |
| `min`, `max`, `step` | Required for `slider`; optional for `number`.         |
| `placeholder`| Placeholder text for `text` / `number`.                       |
| `all_value`  | Sentinel that means "no filter" (e.g. `"All"` / `"Any"`). Lets radio/select have an explicit all option. |
| `targets`    | List of widget ids to refresh when this filter changes. `"*"` matches every data-bound widget (charts, tables, kpis, stat_grids). Wildcards: `"prefix_*"`, `"*_suffix"`. |
| `label`      | Display label.                                                |
| `description` | Short help text. Renders an `\u24D8` icon next to the filter label; hover shows it as a tooltip, **clicking opens a modal** with the same text. Aliases: `help`, `info`. |
| `popup`       | `{title, body}` markdown popup for click, same mechanism as widget popups. Use for long-form help that doesn't fit a tooltip. |
| `scope`      | `"global"` (default; top filter bar) or `"tab:<id>"` (render inline inside a tab panel). Auto-inferred from `targets`: when every target lives in the same tab, scope becomes `"tab:<that_tab>"`; any wildcard / cross-tab target stays global. |

Filters update the shared filter state and are applied client-side by the dashboard runtime on every bound widget.

**Filter placement is auto-scoped.** Every filter goes in one of two places:

- **Global filter bar** (top of the dashboard, below the header) -- for filters that span multiple tabs or use the `"*"` wildcard. Renders only when at least one global filter exists, so dashboards without global filters have no empty bar.
- **Tab-inline filter bar** (flush inside the tab panel) -- for filters whose `targets` all resolve to a single tab. The filter appears only when that tab is active.

Explicitly set `scope: "tab:<tab_id>"` to override the auto-inferred placement, or `scope: "global"` to force the top bar even when the filter could live in a tab.

**Which chart types reshape on filter change.** Auto-wire happens only when a filter targets the widget AND the chart_type + mapping is safe to re-shape client-side: `line` / `multi_line` / `bar` / `area` with simple wide-form mapping (no `color` long-form grouping, no `stack`, no `trendline`). Filtered tables, KPIs, stat_grids, and chart types with computed series data (histograms, bullets, candlesticks, heatmaps, scatter-with-trendline, radar, gauge, sankey, treemap, sunburst, funnel, parallel_coords, tree, graph, boxplot) keep rendering their baseline data -- the filter state still tracks but those charts don't visually reshape.

### 3.8 Links (connect + brush)

```json
"links": [
    {"group": "sync", "members": ["curve", "spread"],
      "sync": ["axis", "tooltip", "dataZoom"]},
    {"group": "brush", "members": ["curve", "spread"],
      "brush": {"type": "rect", "xAxisIndex": 0}}
]
```

`sync` values: `axis`, `tooltip`, `legend`, `dataZoom`. At load, the runtime sets `chart.group = group` for each member and calls `echarts.connect(group)`.

`brush.type`: `rect`, `polygon`, `lineX`, `lineY`. When a user brushes on any member chart, the runtime extracts the `coordRange` from the brush selection, filters the linked charts' datasets to the brushed range on the x axis, and re-renders all other linked charts. Clearing the brush resets the dataset to its original contents.

`members` accepts widget ids or wildcards. Unknown sync entries / brush types raise validation errors.

### 3.9 Layouts

```python
# Grid (default, simple)
"layout": {"kind": "grid", "cols": 12, "rows": [
    [widget, widget, ...],    # rows of widgets; widths must sum to <= cols
    [widget, ...],
]}

# Tabs
"layout": {"kind": "tabs", "cols": 12, "tabs": [
    {"id": "overview", "label": "Overview",
      "description": "Short summary shown under the tab title",
      "rows": [...]},
    {"id": "detail",   "label": "Detail",   "rows": [...]},
]}
```

Tabs lazily initialize their charts on first activation; the last-active tab is persisted in `localStorage` per dashboard id.

Each tab accepts:

| Field         | Purpose                                                                       |
|---------------|-------------------------------------------------------------------------------|
| `id`          | Required. Stable slug used in DOM ids and localStorage keys.                  |
| `label`       | Visible tab text.                                                             |
| `description` | (1) Italic secondary text rendered below the tab bar when the tab is active, (2) a hover tooltip on the tab button itself. Use to caption the scope of the tab. |
| `rows`        | List-of-lists of widgets (see 3.5).                                           |

### 3.10 Header actions (custom buttons / links)

Optional `manifest.header_actions[]` appends custom buttons/links to the header (left of the Refresh / Download PNGs buttons). Use for dashboard-specific escape hatches -- docs, related dashboards, run-a-script hooks, etc.

| Key        | Purpose                                                           |
|------------|-------------------------------------------------------------------|
| `label`    | Required. Display text.                                           |
| `href`     | If set, renders an `<a>` (opens in a new tab by default).          |
| `onclick`  | Name of a global JS function (e.g. `"customRun"`) to wire as click handler. One of `href` / `onclick` is required. |
| `target`   | `"_self"` to open inline (defaults to `_blank`).                   |
| `id`       | Optional DOM id.                                                  |
| `primary`  | `True` -> GS Navy primary button styling.                         |
| `icon`     | Optional leading glyph (e.g. `"\u25B6"`, an emoji).               |
| `title`    | Hover tooltip text.                                               |

### 3.11 Tooltips, info icons, and popups

Two classes of help UI:

1. **Hover tooltips** -- short text shown via the browser's native `title=` attribute. Good for 1-2 word clarifications (column names, button labels, filter operators).
2. **Click popups** -- a centered modal with a title, markdown body, and X / ESC / overlay-click to close. Good for paragraph-length explanations, methodology, or links to source.

Every `\u24D8` icon in the dashboard does BOTH: hover shows the short text as a native tooltip, clicking opens the same content in a modal. Set `popup: {title, body}` on the same widget / filter / stat to give the modal its own richer markdown content while keeping `info` as the hover line.

| Surface                          | Field                          | Appears as                                             |
|----------------------------------|--------------------------------|--------------------------------------------------------|
| Any widget header                | `info`                         | `\u24D8` icon: hover tooltip + click popup            |
| Any widget header                | `popup: {title, body}`         | Richer markdown body for the click popup              |
| Any widget header                | `subtitle`                     | italic sub-line under the title                       |
| Any widget                       | `footer` / `footnote`          | small text below the tile body                        |
| KPI widget                       | `info`, `popup`                | `\u24D8` next to the KPI label (click popup)          |
| Table column header              | `columns[i].tooltip`           | header `title=` attribute                             |
| Table cell (per column)          | `columns[i].tooltip`           | cell `title=` attribute, same text                    |
| Table row                        | `row_highlight` rules          | tinted row + left-edge accent stripe                  |
| Table row click                  | `row_click` (simple)           | modal with configurable `popup_fields` (key/value)    |
| Table row click                  | `row_click.detail.sections[]`  | rich drill-down modal w/ stats, markdown, per-row charts, sub-tables. See the **Bond drill-down** tab in the `screener_studio` demo. |
| stat_grid cell                   | `stats[i].info`, `stats[i].popup` | `\u24D8` next to label; click opens modal          |
| Filter control                   | `description` / `help` / `info`, `popup` | `\u24D8` icon next to the filter label      |
| Tab button                       | `tabs[i].description`          | hover tooltip + italic sub-line under tab bar         |
| Header action button             | `header_actions[i].title`      | native browser tooltip                                |
| Chart tile action buttons        | `action_buttons[i].title`      | native browser tooltip                                |
| Chart tooltip (on hover of data) | `spec.tooltip = {...}`         | ECharts tooltip with optional custom formatter        |
| Chart annotation label           | `annotations[i].label`         | permanent label on the annotation                     |

**Modal behavior** (applies to every click-popup and every table `row_click`):

- X button in the upper-right closes the modal
- ESC key closes the modal
- Clicking on the dim overlay closes the modal
- Only one modal is visible at a time; opening a new popup reuses the same modal element

Markdown in popups supports the same subset as the markdown widget. Use sparingly. A dashboard with a `\u24D8` icon on every control is louder than one without.

### 3.12 Runtime features (free for every compiled dashboard)

Everything below is rendered by `compile_dashboard` automatically; PRISM doesn't configure anything extra.

- **Refresh button** -- visible when `metadata.kerberos` + `metadata.dashboard_id` are set and `metadata.refresh_enabled != False`. POSTs `{kerberos, dashboard_id}` to `/api/dashboard/refresh/` (override via `metadata.api_url`), polls `/api/dashboard/refresh/status/?dashboard_id=...` every 3 s up to 3 minutes, then reloads on success. Offline (`file://`) users see an explanatory alert. See Section 4.3.
- **Data freshness badge** -- header shows `Data as of <metadata.data_as_of>` (falls back to `generated_at`).
- **Download PNGs** -- header button exports every chart on the current tab at 2x.
- **Per-tile PNG** -- each chart tile has a `PNG` button in its toolbar.
- **Fullscreen tile** -- each chart tile has a fullscreen toggle.
- **Tab persistence** -- last-active tab restored per dashboard id via `localStorage`.
- **Filter reset** -- filter bar includes a Reset button.
- **Brush cross-filter** -- drag-select in one chart filters all linked charts.
- **Chart sync (connect)** -- tooltips / axes / data zoom synchronised across members of a sync group.
- **Row-click modal** -- table rows open a detail modal when `row_click` is configured.
- **Table search / sort** -- free when `searchable` / `sortable` are true.
- **Conditional / color-scale cells** -- rendered automatically per column spec.
- **KPI sparklines** -- inline when `sparkline_source` is set.
- **Responsive layout** -- tiles collapse to 6 cols < 1024 px, 12 cols < 720 px.

### 3.13 Validation

```python
from echart_dashboard import validate_manifest
ok, errs = validate_manifest(manifest)
```

Rules:

- `schema_version` must equal `1`
- `id`, `title` must be present
- `theme`, `palette` must be registered names
- Each dataset entry must be `{"source": [...]}` (DataFrames are normalized first)
- Filter `id` must be unique; `type` must be in the valid set
- `select` / `multiSelect` / `radio` require `options`
- `slider` requires `min`, `max`
- `slider`, `number`, `text` require `field`
- Each widget `id` must be unique; widths must sum to at most `cols`
- Widget-specific required fields enforced:
    - `chart` requires one of `spec` / `ref` / `option`
    - `kpi` requires `label`
    - `table` requires `ref` or `dataset_ref`
    - `stat_grid` requires `stats[]`
    - `image` requires `src` or `url`
    - `markdown` requires `content`
- Chart `spec` blocks require `chart_type` (in the 24-type set), `dataset` (must reference a declared dataset), and `mapping` dict. Per-spec `palette` / `theme` overrides must be registered names.
- Filter `targets` must match real chart widget ids (wildcards OK)
- Link members must match real chart widget ids (wildcards OK)
- `sync` values must be in `{axis, tooltip, legend, dataZoom}`
- `brush.type` must be in `{rect, polygon, lineX, lineY}`
- `metadata.refresh_frequency` must be in `{hourly, daily, weekly, manual}`

Returns `(ok, [errors...])`. Each error is a human-readable string identifying the offending path.

---

## 4. Persistence + the refresh pipeline

THIS IS NON-NEGOTIABLE. Every user-requested dashboard persists to `users/{kerberos}/dashboards/{name}/`. A dashboard living only in `SESSION_PATH` is a failed workflow: it won't refresh, won't appear in the user's list, and is lost when the conversation ends.

### 4.1 Three-tool-call build model

```
Tool call 1: pull_data.py     Pulls DataFrames, saves raw data to S3
Tool call 2: build.py         Loads data, populates manifest template, compiles
Tool call 3: register         Updates registry + user manifest
```

Each call uses the `script` parameter (ephemeral code) of `execute_analysis_script` to BOTH persist a script to S3 AND execute the data/build logic in the same invocation. There is no session-folder staging and no separate copy step. The session folder remains the execution environment, but scripts write outputs directly to the dashboard path on S3.

**`pull_data.py`** handles ALL data acquisition. Use `name=` on every data-pull function (prevents sprawl), saves to `{DASHBOARD_PATH}/data/`. Wrap intraday pulls in try/except (Section 4.5).

**`build.py`** is now trivial (~15 lines):

```python
"""build.py -- populate manifest template + compile to HTML."""
import json, io, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sys.path.insert(0, '/GS/viz/echarts')
from echart_dashboard import compile_dashboard, populate_template

KERBEROS = 'goyairl'
DASHBOARD_NAME = 'rates_monitor'
DASHBOARD_PATH = f'users/{KERBEROS}/dashboards/{DASHBOARD_NAME}'

# Load raw data produced by pull_data.py
eod_df = pd.read_csv(io.BytesIO(
    s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')))

# Load the template PRISM authored once, reused forever
template = json.loads(s3_manager.get(
    f'{DASHBOARD_PATH}/manifest_template.json'))

# Wire fresh data + stamp data_as_of / generated_at
m = populate_template(template, {"rates": eod_df}, metadata={
    "data_as_of": str(eod_df.index.max()),
    "generated_at": datetime.now(timezone.utc).isoformat(),
})

# Compile -- writes HTML + manifest to the dashboard folder on S3
r = compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html')
assert r.success, r.warnings
print(f"[build.py] wrote {r.html_path}, {r.manifest_path}")
```

No HTML template. No `sanitize_html_booleans()`. No hand-coded JS. No Canvas API. No per-dashboard chart drawing. The compiler handles all of it.

If Tool Call 1 or 2 fails, PRISM fixes the script and re-runs. The `execute_analysis_script` return includes stdout, stderr, and any files created -- PRISM inspects these to verify success before proceeding. Because the ephemeral script executes the same logic that the persistent script contains, the dashboard is validated during the build conversation: if the logic works now, it will work during automated refresh.

Tool Call 3:

- Creates / updates `manifest.json` (for the registry's pipeline pointer -- distinct from the compiled `manifest.json` written by `compile_dashboard`).
- Updates `dashboards_registry.json` at `users/{kerberos}/dashboards/dashboards_registry.json`.
- Calls `update_user_manifest(kerberos, artifact_type='dashboard')`.
- Generates a download link for the persisted `dashboard.html`.

### 4.2 Registry + pipeline manifest

The user's registry at `users/{kerberos}/dashboards/dashboards_registry.json` is the SSOT for what dashboards a user has. The refresh job reads it to discover which dashboards to refresh; the user manifest has a lightweight pointer that summarizes it.

Registry entry:

```json
{
  "id": "rates_monitor",
  "name": "Rates Monitor",
  "description": "Daily snapshot of key rates and curve shape",
  "created_at": "2026-04-20T21:00:00Z",
  "last_refreshed": "2026-04-24T15:00:00Z",
  "last_refresh_status": "success",
  "refresh_enabled": true,
  "refresh_frequency": "daily",
  "folder": "/users/goyairl/dashboards/rates_monitor/",
  "html_path": "/users/goyairl/dashboards/rates_monitor/dashboard.html",
  "data_path": "/users/goyairl/dashboards/rates_monitor/manifest.json",
  "tags": ["rates", "curve"],
  "keep_history": false,
  "history_retention_days": 30
}
```

The pipeline `manifest.json` (sitting at `{DASHBOARD_PATH}/manifest.json` -- same file as the compiled manifest, written by `compile_dashboard`) lists `scripts/pull_data.py` and `scripts/build.py` with their dependencies. `refresh_dashboards.py` runs them on the configured schedule (`hourly | daily | weekly | manual`).

### 4.3 Refresh flow end-to-end

```
   BROWSER                      DJANGO BACKEND               REFRESH PIPELINE
  (dashboard.html)              (news/views.py)              (refresh_dashboards.py)
  ──────────────                ───────────────              ─────────────────────

  user clicks
  [Refresh] button
        │
        │ rendering.py JS reads MANIFEST.metadata
        │ -> guards on .kerberos + .dashboard_id + .refresh_enabled
        │ -> if file:// protocol, alert("offline, open via portal") and return
        │
        ▼
   POST /api/dashboard/refresh/
   { kerberos, dashboard_id }
        ──────────────────────────►
                                    look up dashboard in
                                    dashboards_registry.json
                                          │
                                    spawn refresh subprocess
                                    (or rejoin running one)
                                          │
                                          │  HTTP 200
                                          │  { status:"refreshing" }
        ◄──────────────────────────       │
                                          │
                                          ▼
                                    refresh_single_user_dashboard()
                                          │
                                          ├─► write refresh_status.json
                                          │   {status:"running",
                                          │    started_at, pid}
                                          │
                                          ├─► RUN scripts/pull_data.py
                                          │   ├─ pull_market_data(), etc.
                                          │   └─ writes ../data/*.csv
                                          │
                                          ├─► RUN scripts/build.py
                                          │   ├─ load manifest_template.json
                                          │   ├─ load ../data/*.csv into dfs
                                          │   ├─ populate_template(...)
                                          │   ├─ compile_dashboard(...)
                                          │   ├─ writes dashboard.html
                                          │   └─ writes manifest.json
                                          │
                                          ├─► (optional) snapshot to history/
                                          │
                                          ├─► update dashboards_registry.json
                                          │   .last_refreshed,
                                          │   .last_refresh_status
                                          │
                                          └─► write refresh_status.json
                                              {status:"success",completed_at}

        meanwhile, every 3 s for up to 3 min:

   GET /api/dashboard/refresh/status/?dashboard_id=...
        ──────────────────────────►
                                          read refresh_status.json
                                          ◄─ HTTP 200
                                          {status:"running"|"success"|"error"|"partial"}
        ◄──────────────────────────

        when status==="success":
        location.reload()
        -> fresh dashboard.html served from S3/portal
```

The API endpoints are defined in Django (`news/urls.py` + `news/views.py`):

```
POST /api/dashboard/refresh/        -> {status: "refreshing" | "success" | ...}
GET  /api/dashboard/refresh/status/?dashboard_id=...  -> {status, errors[], ...}
```

Behaviour:

- Offline (`file://`) -> alert explaining the user needs the portal.
- HTTP 409 (already running) -> switch to polling the status endpoint instead of surfacing an error.
- `status == "success"` -> reload after ~1 s.
- `status == "error"` -> show the error, restore the button after 3 s.
- `status == "partial"` -> reload after 2 s to show whatever was produced.

`metadata.api_url` / `metadata.status_url` override the default endpoints.

The refresh button is rendered into the dashboard header by `compile_dashboard` whenever `metadata.kerberos` and `metadata.dashboard_id` are set and `metadata.refresh_enabled != False`. Same code path for the cron refresh job and the in-browser Refresh click; both run `pull_data.py` -> `build.py` in dependency order.

### 4.4 Templates: `manifest_template` + `populate_template`

```python
from echart_dashboard import manifest_template, populate_template

# One-time: strip data rows, keep column headers + every other config.
tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(),
                f'{DASHBOARD_PATH}/manifest_template.json')

# Each refresh: fresh DataFrames get wired into the template slots.
m = populate_template(tpl, {"rates": eod_df, "cpi": cpi_df},
                         metadata={"data_as_of": "..."},
                         require_all_slots=True)
compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html')
```

The template is pure JSON (no pandas); safe to persist and diff. `require_all_slots=True` raises `KeyError` if the template declares a dataset slot but no DataFrame was provided -- useful to guard refresh pipelines from silently missing data.

### 4.5 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_data.py` that fetches intraday MUST wrap it in `try/except` with an EOD fallback. Every `build.py` must handle a missing intraday file defensively. Dashboard scripts run unattended; silent failures cascade.

```python
# pull_data.py
eod_df, _ = pull_market_data(coordinates=[...], start_date='2020-01-01',
                                name='rates_eod')
try:
    iday_df = pull_market_data(coordinates=[...], mode='iday',
                                  start_date=datetime.now().strftime('%Y-%m-%d'),
                                  name='rates_intraday')
except Exception as e:
    print(f"Intraday unavailable (normal overnight/weekends): {e}")
    iday_df = None
```

```python
# build.py
try:
    iday_df = pd.read_csv(io.BytesIO(
        s3_manager.get(f'{DASHBOARD_PATH}/data/rates_intraday.csv')),
        index_col=0, parse_dates=True)
except Exception:
    iday_df = None

current = iday_df.ffill().iloc[-1] if iday_df is not None and len(iday_df) > 0 else eod_df.iloc[-1]
```

Other common failure modes and prevention:

| Failure                              | Prevention                                                |
|--------------------------------------|-----------------------------------------------------------|
| `KeyError` on DataFrame column       | Check `col in df.columns` before access                   |
| Empty DataFrame after merge          | Use outer join, then handle NaNs explicitly               |
| Division by zero                     | Add epsilon or check denominator                          |
| `IndexError: .iloc[-1]`              | Check `len(df) > 0` first                                  |

Print informative log lines that help debug refresh failures:

```python
print(f"[pull_data.py] Starting at {datetime.now().isoformat()}")
print(f"[pull_data.py] EOD shape: {eod_df.shape}")
print(f"[pull_data.py] Intraday: {'available' if iday_df is not None else 'NOT AVAILABLE (normal overnight)'}")
```

### 4.6 Troubleshooting ("my dashboard is not working")

Diagnose, don't rebuild. Protocol:

1. **Registry** -- read `users/{kerberos}/dashboards/dashboards_registry.json` -- confirm `refresh_enabled`, inspect `last_refresh_status`, `last_refreshed`.
2. **refresh_status.json** -- read `{DASHBOARD_PATH}/refresh_status.json` for `status`, `started_at`, `completed_at`, `errors[]`, `pid`, `auto_healed`. `status="running"` with a `started_at` > 10 min old = stale lock.
3. **Artifacts** -- confirm `dashboard.html`, `manifest.json`, `manifest_template.json`, `scripts/pull_data.py`, `scripts/build.py` exist on S3. Empty `data/` -> pull failed; missing scripts -> dashboard was never properly built; needs rebuild.
4. **Scripts** -- read the failing script, fix the bug (usually intraday guards or column checks), re-upload via `s3_search_and_replace` or rewrite.
5. **Test** -- run `execute_analysis_script(script_path=...)` for each script in order; confirm outputs.
6. **Update registry + deliver** -- set `last_refresh_status="success"`, `last_refreshed=now`, generate a download link for the fixed `dashboard.html`, explain transparently what was wrong.

Common error -> root cause:

| Error pattern                       | Root cause                                                | Fix                                         |
|-------------------------------------|-----------------------------------------------------------|---------------------------------------------|
| "No data successfully fetched"      | Intraday unavailable (overnight/weekend)                  | Wrap intraday in try/except (Section 4.5)   |
| `KeyError: 'column_name'`           | Data schema changed                                       | Defensive column checks in `build.py`       |
| Connection / Timeout                | Transient network                                         | Manual refresh; check source availability   |
| "Auto-healed stale lock"            | Previous refresh hung, was auto-cleared                   | Self-resolves; check for slow pulls         |
| `FileNotFoundError` on script path  | Scripts missing                                           | Rebuild scripts                             |
| Empty DataFrame / no data           | Coordinates / codes invalid                               | Verify pull_data.py codes still valid       |
| `ZeroDivisionError`                 | Analytics edge case                                       | Add epsilon or zero-check in build.py       |

Stale lock cleanup (when the refresh API hasn't auto-healed):

```python
status = {
    "status": "error",
    "started_at": datetime.now(timezone.utc).isoformat(),
    "completed_at": datetime.now(timezone.utc).isoformat(),
    "errors": ["Manually cleared stale running lock"],
    "pid": None,
    "auto_healed": False,
}
s3_manager.put(status, f'{DASHBOARD_FOLDER}/refresh_status.json')
```

Full rebuild only when scripts are missing / corrupted -- use the three-tool-call model in 4.1.

---

## 5. Chart vs dashboard decision

| Intent                                               | Build                                     |
|------------------------------------------------------|-------------------------------------------|
| Share a PNG in chat / email                          | `make_echart(...)`                        |
| Share 2-6 related charts in chat as one artifact     | `make_2pack_*` / `make_3pack_*` / `make_4pack_grid` / `make_6pack_grid` |
| Persistent, refreshable, user-owned monitor          | `compile_dashboard(manifest, session_path=)` then persist to `users/{kerberos}/dashboards/{name}/` |
| Report / email snapshot of a dashboard               | Same as user dashboard + PNGs via `compile_dashboard(..., save_pngs=True)` |

Charts and dashboards use the same engine. Chart specs written for `make_echart()` work verbatim inside a dashboard widget's `spec` block.

---

## 6. Common patterns

### 6.1 Wide-form `multi_line` (fastest)

```python
make_echart(df=df_wide, chart_type='multi_line',
             mapping={'x': 'date', 'y': ['us_2y', 'us_5y', 'us_10y', 'us_30y'],
                      'y_title': 'Yield (%)'},
             title='UST curve', session_path=SP)
```

### 6.2 Long-form `multi_line` with color

```python
df_long = df.melt(id_vars=['date'], var_name='series', value_name='yield')
make_echart(df=df_long, chart_type='multi_line',
             mapping={'x': 'date', 'y': 'yield', 'color': 'series',
                      'y_title': 'Yield (%)'},
             title='UST curve', session_path=SP)
```

### 6.3 Actuals vs estimates via `strokeDash`

```python
make_echart(df=df_long, chart_type='multi_line',
             mapping={'x': 'date', 'y': 'capex', 'color': 'company',
                      'strokeDash': 'type',      # 'Actual' vs 'Estimate'
                      'y_title': 'Capex ($B)'},
             title='Big Tech capex',
             subtitle='solid = actual, dashed = estimate',
             session_path=SP)
```

### 6.4 Dual axis

```python
make_echart(df=df_long, chart_type='multi_line',
             mapping={'x': 'date', 'y': 'value', 'color': 'series',
                      'dual_axis_series': ['ISM Manufacturing'],
                      'y_title': 'S&P 500', 'y_title_right': 'ISM Index',
                      'invert_right_axis': False},
             title='Equities vs ISM', session_path=SP)
```

Before dual-axis, print `df_long['series'].unique()` and assert the right-axis name is present. Name mismatch is the #1 failure mode.

### 6.5 Scatter with trendline

```python
make_echart(df=df, chart_type='scatter',
             mapping={'x': 'unemployment', 'y': 'cpi', 'color': 'decade',
                      'trendlines': True,
                      'x_title': 'U-rate (%)', 'y_title': 'Core CPI YoY (%)'},
             title='Phillips curve by decade', session_path=SP)
```

### 6.6 Bullet: rates RV screen

```python
df_rv = pd.DataFrame({
    'metric': ['2s10s', '5s30s', '10Y real'],
    'current': [38, -5, 1.85],
    'low_5y':  [-20, -10, 0.5],
    'high_5y': [45, 60, 2.4],
    'z': [1.2, -1.5, 0.1],
    'pct': ['85th', '12th', '45th'],
})
make_echart(df=df_rv, chart_type='bullet',
             mapping={'y': 'metric', 'x': 'current',
                      'x_low': 'low_5y', 'x_high': 'high_5y',
                      'color_by': 'z', 'label': 'pct'},
             title='Rates RV screen', dimensions='tall', session_path=SP)
```

---

## 7. Time horizons

| Frequency          | Default lookback | Rationale             |
|--------------------|------------------|-----------------------|
| Quarterly/monthly  | 10 years         | Full business cycle   |
| Weekly             | 5 years          | Trend + cycle         |
| Daily              | 2 years          | Regime without noise  |
| Intraday           | 5 trading days   | Event reaction window |

Override: if the narrative references "highest since X", the chart must include X. For pre-pandemic comparisons, start >= 2015.

Don't show 12 months of monthly data (hides cycle). Don't show 30 years of daily data (noise). Don't use different time ranges for charts meant to be compared.

---

## 8. Data shape preparation

Haver stores many monthly/quarterly series at business-daily granularity. Symptom: stair-step lines. Fix: resample to true native frequency before charting.

```python
starts = starts.resample('M').last()   # stock: last-of-month
claims = claims.resample('M').mean()   # flow: mean
cpi    = cpi.resample('Q').last()      # rate: last
```

Never chart a DataFrame with mixed-frequency NaN gaps. Resample everything to the lowest common frequency before concat / merge.

Always clean before charting:

```python
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
assert len(df) > 0, "empty after cleaning"
```

If a column is named something opaque (`JCXFE@USECON`, `zspread_bps`), rename to a plain-English label BEFORE charting and let the mapping use the new name.

---

## 9. Styling + editor

One theme: `gs_clean` (GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans stack, paper-white with thin grey grid). Lives in `config.py` as a single dict with two top-level parts: `echarts` (the theme JSON registered in-browser via `echarts.registerTheme`) and `knob_values` (flat knob-name -> value overrides applied by the editor). Unknown theme raises `ValueError`.

Three palettes:

| Palette          | Kind        | Use                                            |
|------------------|-------------|------------------------------------------------|
| `gs_primary`     | categorical | Default (navy, sky, gold, burgundy, ...)       |
| `gs_blues`       | sequential  | Heatmaps, calendar heatmaps, gradients         |
| `gs_diverging`   | diverging   | Correlation matrices, z-score heatmaps         |

**Categorical** goes into `option.color`. **Sequential** and **diverging** go into `visualMap.inRange.color` (heatmaps and correlation matrices).

**Single-chart editor HTML** wraps a spec for preview + interactive tweaking:

```
+-----------------------------------------------------------+
| title   spec-sheet [v]  Save SaveAs Delete DL UL  status  |
+------------------------+---------------------------------+-+
| CHART ZONE             | INFO SIDEBAR (440px)            | |
|  Reset Full PNG2x SVG  |  [Data][Code][Metadata][Export] | |
|                        |  [Raw]                          | |
|   live ECharts canvas  |                                 | |
+------------------------+---------------------------------+-+
|  search [_____]   73 knobs   [Reset all knobs]            |
|  +--Presets--+ +--Essentials--+ +--Title--+ +--XAxis--+   |
|  +--YAxis--+ +--Grid--+ +--Legend--+ +--Tooltip--+ ...    |
|  +--Mark--+ +--Interactivity--+ +--Session prefs--+       |
+-----------------------------------------------------------+
```

- `Data`: series table (up to 500 rows displayed)
- `Code`: pretty-printed option JSON with Copy button
- `Metadata`: chart id/type/theme/palette/dimension + series types
- `Export`: PNG 1x/2x/4x, SVG, option JSON, spec sheet JSON
- `Raw`: editable textarea with the full option JSON; edits apply on blur

**Spec sheets** are named bundles of user preferences -- saved via the editor, applied on load. Stores styling only (title/subtitle text are chart-specific content, not user prefs). Stored in `localStorage` under `echart_studio_sheets_{user_id or 'anon'}`. Precedence:

```
knob default -> theme -> dimension typography override -> spec sheet -> live edits
```

**Dashboard runtime** (browser side) iterates widgets, creates ECharts instances per chart tile, subscribes each chart to the filters whose `targets` match it, applies `echarts.connect()` groups after init, wires brush listeners, resolves KPI sources via dotted aggregation, and reset-filters restores defaults + clears all brushes. In the browser console, inspect `window.DASHBOARD`:

```
DASHBOARD.manifest   // original manifest
DASHBOARD.charts     // {id: {inst, datasetRef}}
DASHBOARD.filters    // current filter state
DASHBOARD.datasets   // current dataset copies (post-filter/brush)
```

For **aesthetic** tweaks (colors, fonts, sizes, legend placement): hand the user the `html_path` / `editor_download_url` -- it's a full 140-knob editor with spec sheet save/load and PNG/SVG/JSON export. Do NOT re-call `make_echart()` to tweak styling. For **data / structure** changes: re-call `make_echart()` with the new data or chart type.

---

## 10. Anti-patterns

| Anti-pattern                                              | Do instead                                 |
|-----------------------------------------------------------|--------------------------------------------|
| Literal numbers in manifest JSON                          | Pass the DataFrame; compiler converts      |
| PRISM hand-writing HTML, CSS, or JS                       | Emit manifest; `compile_dashboard()` does it |
| Calling `make_chart()` (legacy) or `matplotlib` anywhere  | Only `make_echart` / `compile_dashboard` from this module |
| Source attribution in title/subtitle                      | Keep it in `metadata.sources`              |
| Annotating self-evident facts (zero line on a spread)     | Omit                                       |
| `np.zeros()` fill when data is missing                    | Skip the panel or add a text note          |
| Positive/negative color on bar charts                     | Bar's position vs zero already conveys sign |
| Horizontal rules on bar charts                            | Put threshold in title/subtitle/narrative  |
| Saving a user dashboard only to `SESSION_PATH`            | Persist to `users/{kerberos}/dashboards/...` |
| `build.py` with > 50 lines                                | It's inlining HTML; use `compile_dashboard` |
| `make_echart()` calls inside `build.py`                   | Dashboards use manifest specs, not `make_echart` |
| Skipping the refresh button by editing HTML               | Don't edit HTML; set `metadata.kerberos` + `dashboard_id` instead |
| Calling `sanitize_html_booleans()` or similar legacy helpers | Not needed -- the compiler handles booleans |

---

## 11. Pre-flight checklist (user dashboard)

- [ ] `dashboard.html` persisted to `users/{kerberos}/dashboards/{name}/`
- [ ] `manifest.metadata.kerberos` + `dashboard_id` + `data_as_of` are set (drives refresh button + freshness badge)
- [ ] `manifest.metadata.refresh_frequency` set (`hourly | daily | weekly | manual`)
- [ ] `manifest_template.json` saved alongside the manifest
- [ ] `scripts/pull_data.py` + `scripts/build.py` saved to `{DASHBOARD_PATH}/scripts/`
- [ ] `manifest.json` saved with both scripts registered
- [ ] Registry entry added to `users/{kerberos}/dashboards/dashboards_registry.json`
- [ ] `update_user_manifest(kerberos, artifact_type='dashboard')` called
- [ ] `pull_data.py` handles intraday failures defensively
- [ ] `build.py` is thin (loads data + `populate_template` + `compile_dashboard`, nothing else)
- [ ] Download link delivered to the user

---

## 12. CLI

Running any script without arguments launches its interactive menu. Argparse mirrors every option for non-interactive / CI use.

```
python echart_studio.py                        # interactive menu
python echart_studio.py wrap spec.json --open  # wrap JSON to HTML
python echart_studio.py demo --matrix          # 23 samples x 5 themes
python echart_studio.py list types|themes|palettes|dimensions|knobs|samples
python echart_studio.py info spec.json         # summarize a spec file
python echart_studio.py test                   # run unit tests
python echart_studio.py png option.json -o chart.png --scale 2
```

```
python echart_dashboard.py                                    # interactive menu
python echart_dashboard.py compile manifest.json -o out.html --open
python echart_dashboard.py compile manifest.json -s SESSION_DIR
python echart_dashboard.py compile manifest.json -o out/dash.html --pngs
python echart_dashboard.py validate manifest.json
python echart_dashboard.py demo
python echart_dashboard.py list widgets|filters|links|chart_types
```

```
python demos.py                                   # interactive menu (5 demos)
python demos.py --all                             # run every demo
python demos.py --demo rv_table                   # run one demo
python demos.py --list                            # list demos and exit
python demos.py --all --open                      # run all, auto-open gallery
```

`demos.py` bundles end-to-end scenarios that collectively exercise every capability in the stack:

| Name              | Kind      | Highlights                                                   |
|-------------------|-----------|--------------------------------------------------------------|
| `rates_daily`     | dashboard | Tabs, KPIs with sparklines + deltas, brush cross-filter      |
| `cross_asset`     | composite | 4-pack grid, event annotations per panel (vline/band/point)  |
| `risk_regime`     | dashboard | Correlation heatmap (diverging), VIX term, boxplot, drawdown |
| `rv_table`        | dashboard | Rich table w/ conditional fmt + color scale + row popup      |
| `filter_showcase` | dashboard | All 9 filter types wired to the same dataset                 |

Each demo writes its output under `output/<timestamp>/<name>/` alongside a combined `gallery.html` page with PNG thumbnails + links to every interactive artifact.

---

## 13. Extending

### Add a chart type

1. Write a builder in `echart_studio.py` (section "BUILDER CONTEXT + PER-TYPE BUILDERS"): `build_mytype(df, mapping, ctx) -> option`.
2. Register it in `_BUILDER_DISPATCH` and add it to `VALID_CHART_TYPES` (in `echart_dashboard.py`).
3. Define per-type knobs in `echart_studio.py` (section "KNOB REGISTRY") and register in `MARK_KNOB_MAP`.
4. Add a sample in `samples.py` (use `@_register("mytype")`).
5. Add relevant `APPLY.*` functions in `rendering.py` (PART 1 - editor HTML) for complex knobs.

### Add a knob

Append to `UNIVERSAL_KNOBS` (applies everywhere) or to the appropriate mark list in the "KNOB REGISTRY" section of `echart_studio.py`. Required fields: `name`, `label`, `type`, `default`, `group`, and one of `path` or `apply`.

### Add a theme / palette / dimension preset

Append to the dict in `config.py`. Edit that file and every chart/dashboard picks up the change.

### Add a widget type

1. Add the widget name to `VALID_WIDGETS` in `echart_dashboard.py` and the per-widget validation block in `validate_manifest`.
2. Add the renderer in `rendering.py` PART 2 (dashboard HTML) -- both the static HTML scaffold and the runtime JS that wires up data flow.
3. Add a sample in `samples.py` exercising the new widget.

---

## 14. Testing

```
python tests.py                        # 171 tests (studio + dashboard + composites)
python tests.py TestThemes             # one test class
python echart_studio.py test           # shortcut: runs tests.py
```

The sample matrix (23 chart samples + dashboard fixtures) runs as part of `TestSamplesMatrix`. Demos in `demos.py` are integration tests with visual outputs; rerun them after behavioural changes to `rendering.py` and inspect the generated `gallery.html`.

---

## 15. File reference

```
GS/viz/echarts/
  config.py             GS brand tokens, theme, palettes, dimensions
  echart_studio.py      make_echart, wrap_echart, EChartResult
  echart_dashboard.py   compile_dashboard, manifest validator,
                          manifest_template / populate_template, Dashboard builder
  composites.py         make_2pack_*, make_3pack_triangle, make_4pack_grid,
                          make_6pack_grid
  rendering.py          single-chart editor HTML + dashboard HTML +
                          dashboard runtime JS + PNG export
  samples.py            chart + dashboard samples + PRISM roleplay demos
  demos.py              end-to-end demo scenarios + CLI + gallery
  inspect_dashboard.py  visual diagnostics for compiled dashboards
  tests.py              unit tests
  README.md             this file
```

For programmatic exploration of every supported capability:

```
python GS/viz/echarts/echart_dashboard.py                 # interactive CLI
python GS/viz/echarts/echart_dashboard.py demo            # render every sample
python GS/viz/echarts/samples.py --all                    # chart gallery
python GS/viz/echarts/tests.py                            # full test suite
```
