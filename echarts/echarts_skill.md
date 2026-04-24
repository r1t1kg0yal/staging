# Charts and Dashboards

**Module:** charts_dashboards
**Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
**Tier:** 2 (on-demand)
**Scope:** ALL chart and dashboard construction in PRISM
**Engine:** ECharts (GS/viz/echarts/)

One system handles both one-off conversational charts and persistent, refreshable dashboards. PRISM never writes HTML. PRISM emits structured JSON; the compiler does the rest.

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
# In execute_analysis_script these are injected into the namespace.
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

## 2. `make_echart(...)` -- single chart

```python
result = make_echart(
    df=df,                      # pandas DataFrame
    chart_type='multi_line',    # see Chart Types (24 types)
    mapping={'x': 'date', 'y': ['us_2y', 'us_10y'], 'y_title': 'Yield (%)'},
    title='UST yields',
    subtitle='daily close',     # optional; never source attribution
    dimensions='wide',          # see Dimensions (12 presets + custom)
    palette=None,               # defaults to gs_primary
    theme='gs_clean',           # the only option
    annotations=[...],          # see Annotations
    session_path=SESSION_PATH,  # writes {SP}/echarts/{name}.json + .html
    chart_name='ust_yields',    # filename slug
    save_as=None,               # alternate output path (overrides session_path)
    write_html=True,            # emit the interactive editor HTML
    write_json=True,            # emit the raw option JSON
    save_png=False,             # emit a PNG via headless Chrome
    png_scale=2,                # device-pixel multiplier for PNG
)
```

`EChartResult` (dataclass; attribute access only):

| Attribute                | Purpose                                                    |
|--------------------------|------------------------------------------------------------|
| `option`                 | ECharts option dict                                        |
| `chart_id`               | 12-char SHA-1 of canonical option                          |
| `chart_type`             | Resolved chart type (`"composite"` for pack layouts)       |
| `theme`, `palette`, `dimension_preset`, `width`, `height` | Resolved style context            |
| `json_path`              | Session path to the option JSON                            |
| `html_path`              | Session path to the interactive editor HTML (~140 knobs)   |
| `png_path`               | Session path to PNG (when `save_png=True` or after `save_png()`) |
| `success`, `warnings`    | Render status + any non-fatal warnings                     |
| `editor_download_url`, `download_url`, `editor_html_path`, `editor_chart_id` | Populated by the session/S3 layer when available |
| `result.save_png(path, scale=2, width=..., height=..., background='#ffffff')` | Methods: render this chart to PNG after the fact |

The editor HTML is the ECharts equivalent of Chart Center: clients can tweak title / axes / typography / palette / dimensions, export PNG / SVG / JSON, save spec sheets. For **aesthetic** changes, hand the user the editor link. For **data / structure** changes, re-call `make_echart()`.

### 2.1 Chart types (24)

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

Unknown `chart_type` -> `ValueError` with the full list.

### 2.2 Core mapping keys (XY chart types)

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

### 2.3 Annotations

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

### 2.4 Dimensions

12 named presets + `custom`. `wide` (700x350, default), `square` (450x450), `tall` (400x550), `compact` (400x300), `presentation` (900x500), `thumbnail` (300x200), `teams` (420x210), `report` (600x400), `dashboard` (800x500), `widescreen` (1200x500), `twopack` (540x360), `fourpack` (420x280), `custom` (600x400 -- preserves the caller's own size when that's already set).

Small presets (`teams`, `thumbnail`, `compact`) auto-downscale typography.

When the request originates from Teams, always use `dimensions='teams'`.

### 2.5 Composites (conversational multi-chart single-artifact)

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

### 2.6 Quality gate

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

---

## 3. Dashboards

A dashboard is a JSON manifest. The compiler writes:

- `{SESSION_PATH}/dashboards/{id}.json`  -- manifest (source of truth, editable by PRISM across turns)
- `{SESSION_PATH}/dashboards/{id}.html`  -- fully-interactive self-contained HTML

For **user dashboards** (persistent, refreshable), the compiler writes to `users/{kerberos}/dashboards/{name}/`. The registry, manifest.json pipeline pointer, and `refresh_dashboards.py` cron job are unchanged from the prior system; see Section 4.

### 3.1 Manifest shape

```python
manifest = {
    "schema_version": 1,
    "id": "rates_daily",              # slug; used as filename
    "title": "US Rates Daily",
    "description": "Curve, spread, KPIs.",   # optional; shown under the title
    "theme": "gs_clean",              # optional; default gs_clean
    "palette": "gs_primary",          # optional; default palette-of-theme

    "metadata": {                     # optional; see Section 3.2
        "kerberos": "goyairl",
        "dashboard_id": "rates_daily",
        "data_as_of": "2026-04-24T15:00:00Z",
        "generated_at": "2026-04-24T15:05:00Z",
        "sources": ["GS Market Data", "Haver"],
        "refresh_frequency": "daily",
        "refresh_enabled": True,
        "tags": ["rates", "curve"],
        "version": "1.0.0",
    },

    "header_actions": [               # optional; see Section 3.7
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

### 3.2 Metadata block (refresh + provenance)

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

### 3.3 Widgets

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

**Chart widget**

`spec` is the preferred variant. It's what this doc describes everywhere:

```json
{"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
  "dataset_ref": "rates",
  "spec": {"chart_type": "multi_line", "dataset": "rates",
            "mapping": {"x": "date", "y": ["us_2y", "us_10y"]},
            "annotations": [...],
            "title": "UST curve", "subtitle": "daily",
            "palette": "gs_primary", "theme": "gs_clean",
            "dimensions": "dashboard"}}
```

`spec.dataset` must reference a name in `manifest.datasets`. Per-spec `title`, `subtitle`, `palette`, `theme`, `dimensions`, `annotations` override the manifest-level defaults. When `dataset_ref` is set on the widget, the client runtime rewires the chart to the live (possibly filtered) dataset on every render.

Two lower-level variants exist for edge cases:

- `"ref": "echarts/curve.json"` -- pre-saved option JSON path (resolved relative to the manifest dir).
- `"option": {...}` -- raw ECharts option dict passthrough.

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

Example: `{"widget": "kpi", "id": "k10y", "label": "10Y", "source": "rates.latest.us_10y", "suffix": "%", "delta_source": "rates.prev.us_10y", "delta_label": "vs prev", "sparkline_source": "rates.us_10y", "w": 3}`

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

Table-level fields: `searchable` (search input + row count), `sortable` (header click reorders), `row_height` (`compact` / default), `max_rows` (viewport cap, default 100), `empty_message`. `row_click` opens a modal with the fields listed in `row_click.popup_fields` (`"*"` or omit for all fields); also supports `title_field` and `extra_content` (HTML).

**stat_grid widget**

Dense grid of label / value stats -- for when a row of KPIs would take too much vertical space.

```json
{"widget": "stat_grid", "id": "summary", "w": 12,
  "title": "Current readings",
  "stats": [
    {"id": "s1", "label": "2s10s (bp)",    "value": "+38",  "sub": "z = +0.9"},
    {"id": "s2", "label": "MOVE index",    "value": "102",  "sub": "z = +0.3"},
    {"id": "s3", "label": "USDJPY 1M vol", "value": "9.4",  "sub": "z = -1.8"},
    {"id": "s4", "label": "HY OAS",        "value": "285 bp","sub": "z = -1.1"}
  ]}
```

Each stat takes `id` (optional), `label`, `value` (or `source` for dotted agg), optional `sub`.

**image widget**

```json
{"widget": "image", "id": "logo", "w": 3,
  "src": "https://.../gs_logo.png",
  "alt": "Goldman Sachs",
  "link": "https://..."}
```

**markdown widget**

```json
{"widget": "markdown", "id": "md", "w": 12,
  "content": "### Method\nSynthetic data. Brush the curve to cross-filter."}
```

Supports `#`, `##`, `###` headings and plain paragraphs. Paragraphs separated by blank lines.

**divider widget**

```json
{"widget": "divider", "id": "sep"}
```

Renders a horizontal rule and forces a full-width row break.

### 3.4 Filters

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

Filters update the shared filter state and are applied client-side by the dashboard runtime on every bound widget.

### 3.5 Links (connect + brush)

```json
"links": [
    {"group": "sync", "members": ["curve", "spread"],
      "sync": ["axis", "tooltip", "dataZoom"]},
    {"group": "brush", "members": ["curve", "spread"],
      "brush": {"type": "rect", "xAxisIndex": 0}}
]
```

`sync` values: `axis`, `tooltip`, `legend`, `dataZoom`. `brush.type`: `rect`, `polygon`, `lineX`, `lineY`. Brushing on one chart filters the linked charts' datasets to the brushed x-range. `members` accepts widget ids or wildcards.

### 3.6 Layouts

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

### 3.7 Header actions (custom buttons / links)

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

### 3.8 Dashboard runtime features (free for every compiled dashboard)

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

---

## 4. Persistence + the refresh pipeline

THIS IS NON-NEGOTIABLE. Every user-requested dashboard persists to `users/{kerberos}/dashboards/{name}/`. A dashboard living only in `SESSION_PATH` is a failed workflow: it won't refresh, won't appear in the user's list, and is lost when the conversation ends.

### 4.1 Three-tool-call model

```
Tool call 1: pull_data.py          Pulls DataFrames, saves raw data to S3
Tool call 2: build_dashboard.py    Loads data, populates manifest template, compiles
Tool call 3: register              Updates registry + user manifest
```

**pull_data.py** uses `name=` on every data-pull function (prevents sprawl), saves to `{DASHBOARD_PATH}/data/`.

**build_dashboard.py** is now trivial (~30 lines):

```python
import json, io, sys
import pandas as pd

sys.path.insert(0, '/GS/viz/echarts')
from echart_dashboard import compile_dashboard, populate_template

KERBEROS = 'goyairl'
DASHBOARD_NAME = 'rates_monitor'
DASHBOARD_PATH = f'users/{KERBEROS}/dashboards/{DASHBOARD_NAME}'

# Load raw data produced by pull_data.py
eod_df = pd.read_csv(io.BytesIO(
    s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')))

# Load the template Prism authored once, reused forever
template = json.loads(s3_manager.get(
    f'{DASHBOARD_PATH}/manifest_template.json'))

# Wire fresh data + stamp data_as_of / generated_at
m = populate_template(template, {"rates": eod_df}, metadata={
    "data_as_of": str(eod_df.index.max()),
    "generated_at": pd.Timestamp.utcnow().isoformat(),
})

# Compile -- writes HTML + manifest to the dashboard folder on S3
r = compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html')
assert r.success, r.warnings
```

No 500-line HTML template. No `sanitize_html_booleans()`. No hand-coded JS. No Canvas API. The compiler handles all of it.

### 4.2 Registry + manifest.json (pipeline registry)

Unchanged from before. The user's registry at `users/{kerberos}/dashboards/dashboards_registry.json` declares the dashboard, its refresh frequency, and its folder. The pipeline manifest at `{DASHBOARD_PATH}/manifest.json` lists `scripts/pull_data.py` and `scripts/build_dashboard.py` with their dependencies. `refresh_dashboards.py` runs them on the configured schedule (`hourly | daily | weekly | manual`). The build script above is idempotent.

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
  "data_path": "/users/goyairl/dashboards/rates_monitor/dashboard_data.json",
  "tags": ["rates", "curve"],
  "keep_history": false,
  "history_retention_days": 30
}
```

Tool call 3 also calls `update_user_manifest(kerberos, artifact_type='dashboard')`.

### 4.3 Refresh button (wired automatically)

`compile_dashboard` renders the refresh button into the dashboard header whenever `metadata.kerberos` and `metadata.dashboard_id` are set and `metadata.refresh_enabled != False`. It calls the same endpoint the cron uses:

```
POST /api/dashboard/refresh/        -> {status: "refreshing" | "success" | ...}
GET  /api/dashboard/refresh/status/?dashboard_id=...  -> {status, errors[], ...}
```

Behavior:

- Offline (`file://`) -> alert explaining the user needs the portal.
- HTTP 409 (already running) -> switch to polling the status endpoint instead of surfacing an error.
- `status == "success"` -> reload after ~1 s.
- `status == "error"` -> show the error, restore the button after 3 s.
- `status == "partial"` -> reload after 2 s to show whatever was produced.

`metadata.api_url` / `metadata.status_url` override the default endpoints.

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

The template is pure JSON (no pandas); safe to persist and diff.

### 4.5 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_data.py` that fetches intraday MUST wrap it in `try/except` with an EOD fallback. Every `build_dashboard.py` must handle a missing intraday file defensively. Dashboard scripts run unattended; silent failures cascade.

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
# build_dashboard.py
try:
    iday_df = pd.read_csv(io.BytesIO(
        s3_manager.get(f'{DASHBOARD_PATH}/data/rates_intraday.csv')),
        index_col=0, parse_dates=True)
except Exception:
    iday_df = None

current = iday_df.ffill().iloc[-1] if iday_df is not None and len(iday_df) > 0 else eod_df.iloc[-1]
```

### 4.6 Troubleshooting ("my dashboard is not working")

Diagnose, don't rebuild. Protocol:

1. **Registry** -- read `users/{kerberos}/dashboards/dashboards_registry.json` -- confirm `refresh_enabled`, inspect `last_refresh_status`, `last_refreshed`.
2. **refresh_status.json** -- read `{DASHBOARD_PATH}/refresh_status.json` for `status`, `started_at`, `completed_at`, `errors[]`, `pid`, `auto_healed`. `status="running"` with a `started_at` > 10 min old = stale lock.
3. **Artifacts** -- confirm `dashboard.html`, `dashboard_data.json`, `manifest.json`, `manifest_template.json`, `scripts/pull_data.py`, `scripts/build_dashboard.py` exist on S3.
4. **Scripts** -- read the failing script, fix the bug (usually intraday guards or column checks), re-upload via `s3_search_and_replace` or rewrite.
5. **Test** -- run `execute_analysis_script(script_path=...)` for each script in order; confirm outputs.
6. **Update registry + deliver** -- set `last_refresh_status="success"`, `last_refreshed=now`, generate a download link for the fixed `dashboard.html`, explain transparently what was wrong.

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

### 6.1 Wide-form multi_line (fastest)

```python
make_echart(df=df_wide, chart_type='multi_line',
             mapping={'x': 'date', 'y': ['us_2y', 'us_5y', 'us_10y', 'us_30y'],
                      'y_title': 'Yield (%)'},
             title='UST curve', session_path=SP)
```

### 6.2 Long-form multi_line with color

```python
df_long = df.melt(id_vars=['date'], var_name='series', value_name='yield')
make_echart(df=df_long, chart_type='multi_line',
             mapping={'x': 'date', 'y': 'yield', 'color': 'series',
                      'y_title': 'Yield (%)'},
             title='UST curve', session_path=SP)
```

### 6.3 Actuals vs estimates via strokeDash

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

Never chart a DataFrame with mixed-frequency NaN gaps. Resample everything to the lowest common frequency before concat/merge.

Always clean before charting:

```python
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
assert len(df) > 0, "empty after cleaning"
```

If a column is named something opaque (`JCXFE@USECON`, `zspread_bps`), rename to a plain-English label BEFORE charting and let the mapping use the new name.

---

## 9. Styling + editor

One theme: `gs_clean` (GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans stack, paper-white with thin grey grid).

Three palettes:

| Palette          | Kind        | Use                                            |
|------------------|-------------|------------------------------------------------|
| `gs_primary`     | categorical | Default (navy, sky, gold, burgundy, ...)       |
| `gs_blues`       | sequential  | Heatmaps, calendar heatmaps, gradients         |
| `gs_diverging`   | diverging   | Correlation matrices, z-score heatmaps         |

For **aesthetic** tweaks (colors, fonts, sizes, legend placement): hand the user the `html_path` / `editor_download_url` -- it's a full 140-knob editor with spec sheet save/load and PNG/SVG/JSON export. Do NOT re-call `make_echart()` to tweak styling.

For **data / structure** changes: re-call `make_echart()` with the new data or chart type.

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
| `build_dashboard.py` with > 200 lines                     | It's inlining HTML; use `compile_dashboard` instead |
| `make_echart()` calls inside `build_dashboard.py`         | Dashboards use manifest specs, not `make_echart` |
| Skipping the refresh button by editing HTML               | Don't edit HTML; set `metadata.kerberos` + `dashboard_id` instead |
| Calling `sanitize_html_booleans()` or similar legacy helpers | Not needed -- the compiler handles booleans |

---

## 11. Pre-flight checklist (user dashboard)

- [ ] `dashboard.html` persisted to `users/{kerberos}/dashboards/{name}/`
- [ ] `manifest.metadata.kerberos` + `dashboard_id` + `data_as_of` are set (drives refresh button + freshness badge)
- [ ] `manifest.metadata.refresh_frequency` set (`hourly | daily | weekly | manual`)
- [ ] `manifest_template.json` saved alongside the manifest
- [ ] `scripts/pull_data.py` + `scripts/build_dashboard.py` saved to `{DASHBOARD_PATH}/scripts/`
- [ ] `manifest.json` (pipeline registry) saved with both scripts registered
- [ ] Registry entry added to `users/{kerberos}/dashboards/dashboards_registry.json`
- [ ] `update_user_manifest(kerberos, artifact_type='dashboard')` called
- [ ] `pull_data.py` handles intraday failures defensively
- [ ] `build_dashboard.py` is thin (loads data + `populate_template` + `compile_dashboard`, nothing else)
- [ ] Download link delivered to the user

---

## 12. File locations (reference)

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
  tests.py              unit tests
  README.md             engineering docs for the echarts module
```

For programmatic exploration of every supported capability:

```
python GS/viz/echarts/echart_dashboard.py                 # interactive CLI
python GS/viz/echarts/echart_dashboard.py demo            # render every sample
python GS/viz/echarts/samples.py --all                    # chart gallery
python GS/viz/echarts/tests.py                            # full test suite
```
