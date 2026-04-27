# ECharts Dashboards

**Module:** `dashboards`
**Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
**Tier:** 2 (on-demand)
**Scope:** ALL dashboard construction in PRISM. (For one-off PNG charts in chat / email / report, PRISM uses Altair via `make_chart()` -- a separate module not covered here.)

A dashboard is a JSON manifest. PRISM never writes HTML, CSS, or JS. PRISM emits structured JSON; the compiler does the rest.

One visual style only -- the Goldman Sachs brand: GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans typeface stack, thin grey grid on paper-white. No theme switcher.

`compile_dashboard(manifest)` is the only PRISM-facing entry point. It validates a JSON manifest, lowers each `widget: chart` through internal builders, and emits an interactive dashboard HTML + manifest JSON.

---

## 0. The contract: real data only, no literals in JSON

Three rules; all three absolute.

**Rule 1 -- real data only.** Every series traces to a real pull (`pull_market_data`, `pull_haver_data`, `pull_plottool_data`, `pull_fred_data`, Treasury / Bloomberg / FactSet / Refinitiv backends, registered scrapers, or a vetted CSV in S3). Forbidden: `np.random.*`, `np.linspace`/`np.arange` as data, hand-typed numeric arrays as "demo"/"placeholder", synthetic fill for missing values, invented dates or labels. If no source exists, do not build the panel -- add a data source first.

**Rule 2 -- no literal data inside the manifest JSON.** Pass DataFrames; the compiler converts them to the canonical on-disk shape. PRISM never types numbers into the JSON. Three accepted dataset entry shapes, all normalised:

| Shape | When |
|-------|------|
| `datasets["rates"] = df` | Most common. Zero ceremony. |
| `datasets["rates"] = {"source": df}` | When attaching metadata to the entry later. |
| `datasets["rates"] = {"source": df_to_source(df)}` | When the manifest is saved/read before the compiler touches it. |

**Rule 3 -- order is non-negotiable; remediation is the work.** `pull_data.py` (Section 12) must complete with real DataFrames -- printed `df.shape` / `df.head()` / `df.dtypes` -- before `build.py` is authored. Write the manifest *against verified shapes*, not imagined columns. If you inherit a non-compliant dashboard (bypasses `compile_dashboard()`, hand-writes HTML/CSS/JS, types numbers into `datasets[*].source`, or skips persistence), bringing it back to spec takes priority over whatever surface change was originally asked for. Surface the trade transparently.

```python
df_rates = pull_market_data(coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
                             start_date='2020-01-01', name='rates')
manifest = {
    "schema_version": 1, "id": "rates", "title": "US Rates",
    "datasets": {"rates": df_rates},
    "layout": {"rows": [[{"widget": "chart", "id": "curve", "w": 12,
        "spec": {"chart_type": "multi_line", "dataset": "rates",
                  "mapping": {"x": "date", "y": ["us_2y", "us_10y"]}}}]]}
}
compile_dashboard(manifest, session_path=SESSION_PATH)
```

### 0.1 Computed columns (manifest-level expressions)

A dataset entry can declare a `compute` block of named expressions evaluated against an existing source dataset. Use this instead of computing spreads / ratios / z-scores in `build.py`. The compiler runs an AST-level whitelist (no `eval`, no `__import__`, no attribute access), materialises each output column, and auto-stamps `field_provenance` with `system: "computed"`, the recipe string, and the upstream column list.

```python
"datasets": {
    "rates": df_rates,                        # source columns: us_2y, us_10y, ...
    "spreads": {
        "from": "rates",
        "compute": {
            "us_2s10s_bp":  "(us_10y - us_2y) * 100",
            "us_5s30s_bp":  "(us_30y - us_5y) * 100",
            "us_10y_z_60":  "zscore(us_10y, 60)",
            "spread_pct":   "pct_change(us_10y - us_2y)",
        }
    }
}
```

Cross-dataset references via `<other_ds>.<col>`. Omit `from` to append computed columns to the same dataset's source.

**Allowed function whitelist** (any other name = validation error):

| Group       | Functions |
|-------------|-----------|
| Arithmetic  | `+ - * / % ** //`, unary `+ -` |
| Numeric     | `log`, `log10`, `log2`, `exp`, `sqrt`, `abs`, `sign`, `round` |
| Aggregate   | `mean`, `std`, `min`, `max`, `sum` (broadcast scalar) |
| Series      | `zscore(x, window?)`, `rolling_mean(x, n)`, `rolling_std(x, n)`, `pct_change(x, periods?)`, `diff(x, periods?)`, `shift(x, periods?)`, `clip(x, lo?, hi?)`, `index100(x)`, `rank_pct(x)` |

Column names referenced in expressions must start with a letter or underscore (no digits, no spaces / dots / dashes); rename upstream or compute inline if the name doesn't parse. Inferred units: `* 100` on percent inputs → `bp`, `zscore(...)` → `z`, `pct_change(...)` / `yoy_pct(...)` / `index100(...)` → `percent`, otherwise inherit when every referenced column shares units.

The popup Sources footer on any point of the resulting chart surfaces the recipe directly.

---

## 1. Injected namespace

Inside `execute_analysis_script`:

```python
compile_dashboard       # manifest -> interactive HTML + manifest JSON (+ optional PNGs)
manifest_template       # strip data from a manifest -> reusable template
populate_template       # template + fresh DataFrames -> ready-to-compile manifest
validate_manifest       # dry-run the validator without rendering
chart_data_diagnostics  # check data wires up correctly (missing columns, size limits)
load_manifest           # path -> manifest dict (used by refresh pipeline)
save_manifest           # manifest -> JSON file
df_to_source            # DataFrame -> canonical row-of-lists source form
```

One theme (`gs_clean`); three palettes (`gs_primary` categorical, `gs_blues` sequential, `gs_diverging` diverging).

---

## 2. Manifest shape + metadata

### 2.1 Manifest shape

```python
manifest = {
    "schema_version": 1, "id": "rates_monitor", "title": "Rates monitor",
    "description": "Curve, spread, KPIs.",   # optional subtitle
    "theme": "gs_clean", "palette": "gs_primary",   # both defaults
    "metadata":        { ... },               # see 2.3
    "header_actions":  [ ... ],               # see Section 8
    "datasets":        {"rates": df_rates, "cpi": {"source": df_cpi}},
    "filters":         [ ... ],               # see Section 5
    "layout":          {"kind": "tabs",       # or "grid" (default); see Section 7
                         "tabs": [{"id": "overview", "label": "Overview",
                                   "description": "Headline rates + spread",
                                   "rows": [ [ widget, widget, ... ], ... ]}]},
    "links":           [ ... ],               # see Section 6
}
compile_dashboard(manifest, session_path=SESSION_PATH)
```

| Top-level field | Purpose |
|-----------------|---------|
| `title` / `description` | Header title + subtitle |
| `theme` / `palette` | `gs_clean` (only theme); `gs_primary` (default) / `gs_blues` (sequential) / `gs_diverging` |
| `metadata` | Provenance + refresh block; see 2.3 |
| `header_actions` | Custom header buttons; see Section 8 |
| `datasets` | `{name: DataFrame \| {"source": ...}}` |
| `filters` / `layout` / `links` | See Sections 5 / 7 / 6 |

### 2.2 Folder structure

For **conversational (session-only)** dashboards:

```
{SESSION_PATH}/dashboards/{id}.json     compiled manifest
{SESSION_PATH}/dashboards/{id}.html     compiled dashboard
```

For **persistent user dashboards** the unit of organisation is `users/{kerberos}/dashboards/{name}/`; everything that belongs to a dashboard lives inside it:

```
users/{kerberos}/dashboards/{dashboard_name}/
  manifest_template.json    SOURCE OF TRUTH (LLM-editable spec, NO data)
  manifest.json             BUILD ARTIFACT (template + fresh data, embedded)
  dashboard.html            DELIVERABLE (compile_dashboard output)
  refresh_status.json       STATE (status, started_at, errors[], pid, auto_healed)
  thumbnail.png             optional
  scripts/
    pull_data.py            data acquisition (~50-150 lines)
    build.py                ~12 lines: load data, populate_template, compile
  data/
    rates_eod.csv           raw cache (pull_data.py outputs)
  history/                  optional snapshots when keep_history=true
```

Forbidden: HTML / CSS / JS in any `.py` file (`rendering.py` owns it); `scripts/build_dashboard.py` (renamed to `build.py`); per-source folders (`haver/`, `market_data/` -- everything goes to `data/`); timestamped scripts (`20260424_*.py`); session-only artifacts at dashboard scope (`*_results.md`, `*_artifacts.json`); multiple data JSONs (only `manifest.json`); inline `<script>const DATA = {}` in HTML; legacy helpers (`sanitize_html_booleans()`).

### 2.3 Metadata block

Drives the data-freshness badge, methodology popup, summary banner, and refresh button. All fields optional -- omit for session artifacts, set for persistent dashboards.

| Field | Type | Purpose |
|-------|------|---------|
| `kerberos` / `dashboard_id` | str | Required for refresh button (defaults to `manifest.id`) |
| `data_as_of` / `generated_at` | str (ISO) | Header badge `Data as of YYYY-MM-DD HH:MM:SS UTC`; compile time (badge fallback) |
| `sources` | list[str] | Data source names (`["GS Market Data", "Haver"]`) |
| `summary` | str \| `{title, body}` | Always-visible markdown banner above row 1 (today's read) |
| `methodology` | str \| `{title, body}` | Click-to-open markdown popup (header button) |
| `refresh_frequency` / `refresh_enabled` | str / bool | `hourly` / `daily` / `weekly` / `manual`; set `False` to hide refresh button |
| `tags` / `version` | list[str] / str | Echoed into the registry; manifest version string |
| `api_url` / `status_url` | str | Refresh / status endpoint overrides |

`summary` and `methodology` both accept the shared markdown grammar (4.8). `summary` is always-visible above row 1 (today's read); `methodology` is click-to-open via the header button (how the data is constructed).

```python
metadata = {
    "data_as_of": "2026-04-24T15:00:00Z",
    "methodology": "## Sources\n* US Treasury OTR yields (FRED H.15)\n## Construction\n"
                    "* 2s10s, 5s30s = simple cash differences in bp",
    "summary": {"title": "Today's read",
                 "body": "Front-end has richened ~6bp on a softer print. Curve **bull-steepened**, "
                          "2s10s out of inversion for the first time in three weeks."},
}
```

**Standard top-right protocol** (fixed left-to-right; each element auto-shows when its enabling config is present):

| # | Element | Visible when |
|---|---------|--------------|
| 1 | `Data as of <ts>` | `metadata.data_as_of` or `generated_at` set |
| 2 | `Methodology` | `metadata.methodology` set |
| 3 | `Refresh` | `metadata.kerberos` + `dashboard_id` set, `refresh_enabled != False` |
| 4 | `Download Charts` | always (one PNG per `widget: chart`) |
| 5 | `Download Panel` | always (full view as single PNG) |
| 6 | `Download Excel` | dashboard has at least one `widget: table` |

`header_actions[]` (Section 8) injects custom buttons in front of this bar.

### 2.4 `compile_dashboard` parameters

| Parameter | Purpose |
|-----------|---------|
| `manifest` | Dict, JSON string, or path to manifest JSON |
| `session_path` | Writes `{sp}/dashboards/{id}.json` + `{id}.html` |
| `output_path` | Explicit HTML path; the `.json` is written alongside |
| `base_dir` | Resolves `widget.ref` paths (defaults: arg, manifest's parent, cwd) |
| `write_html` / `write_json` | Disable either emit (default `True`); use `False` in sandbox to write via `s3_manager.put()` |
| `save_pngs=True` | Render each chart widget to PNG (titles/subtitles baked in) |
| `png_dir` / `png_scale=2` | PNG output dir / device-pixel multiplier (1=baseline, 2=retina, 4=print) |
| `strict=True` (default) | Hard-fail on any error-severity diagnostic. `strict=False` keeps going so PRISM can fix all in one round-trip |
| `user_id` | Stamped into editor HTML / spec sheet localStorage scoping |

Returns `DashboardResult(success, html_path, manifest_path, html, warnings, diagnostics, error_message)`. `result.html` is the raw HTML string (handy when `write_html=False`).

---

## 3. Chart specs

Every `widget: chart` declares one of three variants. Use the lowest ceremony that fits.

| Variant | Shape | When |
|---------|-------|------|
| `spec` | `{chart_type, dataset, mapping, [title, palette, ...]}` | **Preferred.** LLM-friendly. |
| `ref` | `"echarts/mychart.json"` (relative path) | Pre-emitted ECharts spec on disk |
| `option` | raw ECharts option dict | Hand-crafted; you own correctness (no validation) |

`spec.dataset` references `manifest.datasets.<name>`. At compile time the source rows are materialised into a pandas DataFrame and fed into the per-chart-type builder. `ref` paths resolve relative to `base_dir` arg → loaded manifest's parent → cwd.

### 3.1 Chart types (30)

| chart_type | Required mapping keys |
|------------|------------------------|
| `line` | `x`, `y`, optional `color` |
| `multi_line` | `x`, `y` (list) OR `x`, `y`, `color` |
| `bar` | `x` (category), `y`, optional `color`, `stack` (bool) |
| `bar_horizontal` | `x` (value), `y` (category), optional `color`, `stack` |
| `scatter` | `x`, `y`, optional `color`, `size`, `trendline` |
| `scatter_multi` | `x`, `y`, `color`, optional `trendlines` |
| `scatter_studio` | none required; author-supplied whitelists drive runtime picker (3.1a) |
| `area` | `x`, `y` (stacked area) |
| `heatmap` | `x`, `y`, `value` |
| `correlation_matrix` | `columns` (list of >=2 numeric cols), optional `transform`, `method`, `order_by` (3.1b) |
| `histogram` | `x`, optional `bins` (int or list of edges), `density` |
| `bullet` | `y` (cat), `x` (cur), `x_low`, `x_high`, optional `color_by`, `label` |
| `pie` | `category`, `value` |
| `donut` | `category`, `value` |
| `boxplot` | `x` (cat), `y` |
| `sankey` | `source`, `target`, `value` |
| `treemap` | `path` (list) + `value` OR `name` + `parent` + `value` |
| `sunburst` | same as treemap |
| `graph` | `source`, `target`, `value`, `node_category` |
| `candlestick` | `x`, `open`, `close`, `low`, `high` |
| `radar` | `category`, `value`, optional `series` |
| `gauge` | `value`, optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`, optional `year` |
| `funnel` | `category`, `value` |
| `parallel_coords` | `dims` (list), optional `color` |
| `tree` | `name`, `parent` |
| `waterfall` | `x` (cat), `y` (signed delta), optional `is_total` (bool col flagging totals) |
| `slope` | `x` (snapshot col with exactly 2 distinct values), `y`, `color` (per-line cat) |
| `fan_cone` | `x`, `y` (central path), `bands` (list of `{lower, upper, label?, opacity?}`) |
| `marimekko` | `x` (col-axis cat), `y` (row-axis cat), `value` (cell magnitude), optional `order_x`, `order_y` |
| `raw` | pass `option=...` directly (passthrough) |

Unknown `chart_type` raises `ValueError`. Datetime cols auto-resolve to `xAxis.type='time'`; numeric to `'value'`; everything else to `'category'`. Missing columns raise `ValueError` listing actual DataFrame columns -- no silent fallback.

**Finance-flavoured shapes:** `waterfall` -- decomposition / attribution (each row is incremental delta -- positive green / negative red -- or a full-height total when `is_total` truthy; P&L bridges, attribution, factor decomp). `slope` -- N categories at exactly two snapshots joined by sloped lines, right-edge labels ("month-end vs latest", "before vs after"). `fan_cone` -- forecast ribbon (central path + N stacked confidence bands, opacity declines outside-in; FOMC dot-plot fans, scenario cones). `marimekko` -- 2D categorical proportions (each x-cat column width = its share of total; y-cats stack proportional to column total; cap-weighted allocation by sector × size).

### 3.1a `scatter_studio` -- exploratory bivariate

Use when the analyst should pick X / Y / color / size / per-axis transform / regression interactively. Author whitelists columns; regression line, R², p-value, window slicer wired automatically.

| Mapping key | Purpose |
|-------------|---------|
| `x_columns` / `y_columns` / `color_columns` / `size_columns` | Whitelisted numeric / categorical columns for the X / Y / color / size dropdowns. Default: every numeric col for X/Y, empty for color/size |
| `x_default` / `y_default` / `color_default` / `size_default` | Initial selections |
| `order_by` | Sort key for order-aware transforms. Default: first datetime-like col. Required if any order-aware transform is in `studio.transforms` |
| `label_column` | Row label in tooltip header / `click_popup` template. Default: `order_by` |
| `x_transform_default` / `y_transform_default` | Initial per-axis transforms (default `'raw'`) |

`spec.studio` block (sibling to `mapping`, all optional):

| Key | Default |
|-----|---------|
| `transforms` | `['raw', 'log', 'change', 'pct_change', 'yoy_pct', 'zscore', 'rolling_zscore_252', 'rank_pct']` |
| `regression` / `regression_default` | `['off', 'ols', 'ols_per_group']` / `'off'` |
| `windows` / `window_default` | `['all', '252d', '504d', '5y']` / `'all'` |
| `outliers` / `outlier_default` | `['off', 'iqr_3', 'z_4']` / `'off'` |
| `show_stats` | `True`. Stats strip below canvas: `n`, Pearson `r` (with stars), `R²`, slope `beta` (SE), intercept `alpha`, RMSE, p-value |

Per-axis transforms (`raw`, `log` (drops non-positive), `change`, `pct_change`, `yoy_change`, `yoy_pct`, `zscore`, `rolling_zscore_<N>`, `rank_pct`, `index100`). Order-aware (`change`, `pct_change`, `yoy_*`, `rolling_zscore_*`) require `order_by`.

Stats strip: `n=247  r=0.68***  R²=0.46  beta=0.42 (SE 0.03)  alpha=1.18  RMSE=0.31  p=4.2e-9`. Stars: `***` p<0.001 / `**` p<0.01 / `*` p<0.05 / `·` p<0.10. With `regression: ols_per_group` the strip lists per-color stats below the overall row.

Edge cases: `n<2` → `n<2 -- regression unavailable`; zero X-variance suppresses the line; `log` drops negatives; filter narrowing recomputes everything against the filtered subset.

### 3.1b `correlation_matrix` -- N×N heatmap from a column list

"How do these N series co-move?" The builder applies a per-column transform (correlate `% changes` instead of levels), computes the correlation matrix, emits a diverging heatmap pinned to `[-1, 1]`.

| Mapping key | Purpose |
|-------------|---------|
| `columns` (req) | List of numeric column names, length >= 2 |
| `method` | `'pearson'` (default) or `'spearman'` (rank correlation; robust to monotonic non-linearity) |
| `transform` | Per-column transform before correlation (default `'raw'`; same names as scatter_studio) |
| `order_by` | Required when `transform` is order-aware. Default: first datetime-like col |
| `min_periods` | Min overlapping non-null pairs to report a correlation (default 5); below threshold renders blank |
| `show_values` / `value_decimals` | Print correlation in each cell (default `True` / `2`) |
| `value_label_color` | `"auto"` (B/W contrast), hex, or `False` |
| `colors` / `color_palette` | Override palette (default `gs_diverging`) |

Cell tooltip prints `<row name> × <col name>: r=0.xx`. The diagonal is always `1.0`. Hover the diverging visualMap on the right edge to read off the exact `r` at any color.

`correlation_matrix` for wide-form time-series panels (author gives columns; builder does math + visualMap). `heatmap` for pre-computed bivariate cells (cross-asset returns by month, hit-rate by quintile).

### 3.2 Core mapping keys (XY chart types)

| Key | Purpose |
|-----|---------|
| `x`, `y` | Required. `y` can be a list (wide-form multi_line) |
| `color` | Grouping column (multi-series long form) |
| `y_title` / `x_title` / `y_title_right` | Plain-English axis titles. Right-axis title for dual-axis |
| `x_sort` | Explicit category order (list of values) |
| `x_type` | Force `'category'` / `'value'` / `'time'` on ambiguous columns |
| `invert_y` / `y_log` / `x_log` | Invert single-axis y; log scale on respective axis |
| `stack` (bar) | `True` (default) = stacked, `False` = grouped |
| `dual_axis_series` / `invert_right_axis` | (legacy) Right-axis series list; flip right axis (rates "up = bullish") |
| `axes` | List of axis spec dicts for N-axis time series. Takes precedence over the legacy 2-axis API |
| `strokeDash` / `strokeDashScale` / `strokeDashLegend` | Column controlling per-series dash pattern; `{"domain": [...], "range": [[1,0], [8,3]]}` explicit mapping; legend cross-product |
| `trendline` / `trendlines` (scatter) | `True` adds overall / per-group OLS line |
| `size` (scatter) | Column driving marker size |
| `bins` / `density` (histogram) | Int or list of bin edges (default 20); `True` normalises counts to density |

**Chart-specific shapes:**

| Chart | Mapping keys |
|-------|--------------|
| `sankey` / `graph` | `source`, `target`, `value`; `graph` adds `node_category` |
| `treemap` / `sunburst` | `path` + `value`, or `name` + `parent` + `value` |
| `candlestick` | `x`, `open`, `close`, `low`, `high` |
| `radar` | `category`, `value`, optional `series` |
| `gauge` | `value`, optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`, optional `year` |
| `parallel_coords` | `dims` (list), optional `color` |
| `tree` | `name`, `parent` |

**Heatmap-style charts** (`heatmap`, `correlation_matrix`, `calendar_heatmap`) accept these cell-label / color keys: `show_values` (default `True` for heatmap / correlation_matrix, `False` for calendar_heatmap), `value_decimals` (auto-picked from data magnitude), `value_formatter` (raw ECharts function string -- suppresses auto-contrast), `value_label_color` (`"auto"` / hex / `False`), `value_label_size` (default 11), `colors`, `color_palette`, `color_scale` (`sequential` / `diverging` / `auto` -- diverging when data crosses zero), `value_min` / `value_max` (pin visualMap range so colors stay interpretable across reruns).

Auto-contrast routes through ECharts rich-text styles (`label.rich.l` for dark text on light cells, `label.rich.d` for light on dark) plus a JS formatter that picks the right style from cell luminance -- the heatmap series doesn't evaluate `label.color` as a callback, which is why rich text is used.

**Multi-axis time series (`mapping.axes`).** Line / multi_line / area accept arbitrary independent y-axes. Each axis spec dict supports its own scale, side, inversion, log, range bounds, tick formatter.

```json
"mapping": {
  "x": "date", "y": ["spx", "ust", "dxy", "wti"],
  "axes": [
    {"side": "left",  "title": "SPX",     "series": ["spx"], "format": "compact"},
    {"side": "right", "title": "UST 10Y", "series": ["ust"], "invert": true, "format": "percent"},
    {"side": "left",  "title": "DXY",     "series": ["dxy"]},
    {"side": "right", "title": "WTI",     "series": ["wti"], "format": "usd"}
  ]
}
```

Per-axis keys: `side` (`left`/`right`, req), `title`, `series`, `invert`, `log`, `min`/`max`, `format` (`percent`/`bp`/`usd`/`compact` or raw ECharts function string), `offset` (auto-stacked at 0, 80, 160, ... when omitted), `scale` (default `True`), `color` (auto-tints to series' palette color for single-series axes, Bloomberg-style).

Mapping-level: `axis_offset_step` (default 80, controls spacing), `axis_color_coding` (default `True`). Annotations target an axis via `axis: <index>` (0..N-1); legacy `axis: "right"` resolves to index 1.

When to use: 2 axes → prefer `dual_axis_series`. 3+ across asset classes/units → `axes`. 3+ same unit → one axis right. 3+ different units comparing patterns → consider Index=100 normalisation instead.

### 3.3 Cosmetic / layout knobs (every chart type)

| Key | Purpose |
|-----|---------|
| `legend_position` / `legend_show` | `"top"` (default), `"bottom"`, `"left"`, `"right"`, `"none"`; explicit `True`/`False` override. Auto-hides pie/donut slice edge labels when set to top/bottom |
| `series_labels` / `humanize` | `{raw_name: display_name}` overrides auto-humanise; `humanize: False` disables `us_10y` → `US 10Y` |
| `x_date_format` | `"auto"` for compact `MMM D`; raw ECharts function string for custom |
| `show_slice_labels` (pie/donut) | Keep per-slice edge labels even with top/bottom legend |
| `y_min` / `y_max` / `x_min` / `x_max` | Force axis range |
| `y_format` / `x_format` | `"percent"` / `"bp"` / `"usd"` / `"compact"` (K/M/B) or raw ECharts function string |
| `y_title_gap` / `x_title_gap` / `y_title_right_gap` | Pixels between tick labels and axis title (auto-sized by default) |
| `category_label_max_px` | Max pixel width for category-axis tick labels (default 220); longer get ellipsis |
| `grid_padding` | `{top, right, bottom, left}` overriding plot-area margins |
| `show_grid` / `show_axis_line` / `show_axis_ticks` | `False` to suppress |
| `series_colors` | `{col_name: "#hex"}` overrides palette for specific series (raw or post-humanise name) |
| `tooltip` | `{"trigger": "axis"\|"item"\|"none", "decimals": 2, "formatter": "<JS fn>", "show": False}` |

**Layout-aware sizing.** Compiler truncates long category labels to `category_label_max_px`; sizes `nameGap` from real label widths; bumps `grid.left`/`grid.bottom` for rotated axis names; auto-rotates vertical-bar / boxplot x-labels when crowded; bumps heatmap `grid.right` to 76px for visualMap clearance.

**Per-spec overrides.** `palette`, `theme`, `annotations` may live on `spec` to override manifest defaults. Required keys: `chart_type`, `dataset`, `mapping`. Titles / subtitles live at the widget level only -- `spec.title` / `spec.subtitle` are rejected by the validator (Section 4.1).

### 3.4 Annotations

Five types in `annotations=[...]`:

```python
"annotations": [
    {"type": "hline", "y": 2.0, "label": "Fed target", "color": "#666", "style": "dashed"},
    {"type": "vline", "x": "2022-03-15", "label": "Liftoff"},
    {"type": "band",  "x1": "2020-03-01", "x2": "2020-06-01", "label": "COVID", "opacity": 0.3},
    {"type": "arrow", "x1": "2020-04-01", "y1": 5, "x2": "2021-03-01", "y2": 8, "label": "recovery"},
    {"type": "point", "x": "2023-06-15", "y": 4.4, "label": "peak"}]
```

Common keys: `label`, `color`, `style` (`'solid'|'dashed'|'dotted'`), `stroke_dash` (`[4,4]`), `stroke_width`, `label_color`, `label_position`, `opacity` (band), `head_size` / `head_type` (arrow), `font_size` (point). `band` accepts `y1`/`y2` (horizontal band) and aliases `x_start`/`x_end`, `y_start`/`y_end`. For dual-axis charts, `hline` accepts `"axis": "right"`. Charts without axes (pie / donut / sankey / treemap / sunburst / radar / gauge / funnel / parallel_coords / tree) silently ignore annotations.

Annotate regime changes, policy shifts, event dates, structural breaks. Don't annotate self-evident facts (zero line on a spread, target on every CPI chart).

---

## 4. Widgets

### 4.1 Widget table + presentation knobs

| Widget | Required | Purpose |
|--------|----------|---------|
| `chart` | `id`, one of `spec` / `ref` / `option` | ECharts canvas tile |
| `kpi` | `id`, `label` | Big-number tile + delta + sparkline |
| `table` | `id`, `ref` or `dataset_ref` | Rich table with sort / search / format / popup |
| `pivot` | `id`, `dataset_ref`, `row_dim_columns`, `col_dim_columns`, `value_columns` | Crosstab with row/col/value/agg dropdowns (4.5a) |
| `stat_grid` | `id`, `stats[]` | Dense grid of label/value stats |
| `image` | `id`, `src` or `url` | Embed static image or logo |
| `markdown` | `id`, `content` | Freeform markdown block (transparent) |
| `note` | `id`, `body` | Semantic callout: tinted card, colored left-edge stripe by `kind` |
| `divider` | `id` | Horizontal rule, forces row break |

Common optional fields: `w` (1-12 grid span), `h_px` (chart only; default 280), `title`, `show_when` (4.1.1).

**Widget presentation knobs** (every tile type):

| Field | Purpose |
|-------|---------|
| `title` / `subtitle` | Card header at widget level (never in `spec` -- validator rejects). Italic secondary line. PNG export bakes title into the chart |
| `footer` (alias `footnote`) | Small text below tile body, dashed-border separator. Source attribution |
| `info` / `popup` | Short help (info icon: hover tooltip + click modal with same text). `popup: {title, body}` markdown overrides modal content |
| `badge` / `badge_color` | Short string (1-6 chars) pill next to title; color ∈ `"gs-navy"` (default) / `"sky"` / `"pos"` / `"neg"` / `"muted"` |
| `emphasis` / `pinned` | `True`: thicker navy border + shadow (KPIs: sky-blue top border) / sticky to viewport top |
| `action_buttons` | List of extra toolbar buttons: `{label, icon?, href?, onclick?, primary?, title?}` |
| `click_emit_filter` (chart) | Data-point clicks → filter changes. Bare filter id, or `{filter_id, value_from, toggle}` (`value_from` ∈ `"name"` / `"value"` / `"seriesName"`) |
| `click_popup` (chart) | Data-point clicks → per-row detail popup. Same grammar as table `row_click` (4.4) |

```json
{"widget": "chart", "id": "price_chart", "w": 12, "h_px": 440,
  "title": "ACME daily OHLC (1Y)", "badge": "LIVE", "badge_color": "pos",
  "info": "Daily OHLC. Drag the brush at the bottom to zoom.",
  "footer": "Source: GS Market Data. Updated at market close.",
  "action_buttons": [{"label": "Open in portal", "href": "https://example.com/acme"}],
  "spec": {"chart_type": "candlestick", "dataset": "ohlc",
            "mapping": {"x": "date", "open": "open", "close": "close",
                        "low": "low", "high": "high"}}}
```

#### 4.1.1 `show_when` -- conditional widget visibility

A widget can declare `show_when`; if it fails the widget is removed (compile-time data conditions) or hidden via CSS (runtime filter conditions).

* **Data condition** (compile-time) -- `{"data": "<dotted_source> <op> <value>"}`. Source uses KPI dotted shape (`dataset.aggregator.column`); ops: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`. Widget removed entirely from layout when condition fails.
* **Filter condition** (runtime) -- `{"filter": "<filter_id>", "value": <v>}`, `{"filter": "<filter_id>", "in": [<v>, ...]}`, or `{"filter": "<filter_id>", "op": ">", "value": 25}`. JS toggles widget visibility on filter change.
* **Compound** -- `{"all": [...]}` (AND), `{"any": [...]}` (OR). Mix data and filter clauses freely; the compile-time pass evaluates only the data sub-conditions.

```python
{"widget": "note", "id": "vol_warning", "kind": "risk",
  "body": "Vol regime elevated; tighten stops...",
  "show_when": {"data": "rates.latest.vix > 25"}}              # compile-time

{"widget": "chart", "id": "fed_path",
  "show_when": {"filter": "scope", "value": "domestic"}}        # runtime

{"widget": "pivot", "id": "global_pivot",
  "show_when": {"all": [{"data": "market.latest.vix < 30"},     # compile-time
                          {"filter": "scope", "in": ["us", "eu"]}]}}  # runtime
```

Validation: filter-clause `filter` ids must reference declared filter ids; the validator emits an error for typos.

#### 4.1.2 Per-widget `initial_state`

Every chart / table / KPI carries a controls drawer (`⋮` button, see 10.1). `initial_state` seeds those state objects so a chart opens in the desired view (e.g. YoY % instead of raw levels) without an extra click. Mirrors the drawer state shape; unknown keys are ignored.

```python
# Chart: open in YoY %, log y-scale, dashed-step shape, per-series transforms
"spec": {"chart_type": "line", "dataset": "rates", "mapping": {"x": "date", "y": "us_10y"},
          "initial_state": {
              "transform": "yoy_pct", "smoothing": 5,
              "y_scale": "log", "y_range": "from_zero",
              "shape": {"lineStyleType": "dashed", "step": "middle",
                         "width": 2, "areaFill": True, "stack": "percent"},
              "series": {"us_10y": {"transform": "log", "visible": True}},
              "bar_sort": "value_desc", "bar_stack": "stacked",
              "trendline": "linear", "color_scale": "diverging",
              "show_labels": True, "pie_sort": "largest", "pie_other_threshold": 0.05}}

# Table: open with search + sort + hidden columns + density
{"widget": "table", "initial_state": {"search": "tech", "sort_by": "z", "sort_dir": "desc",
    "hidden_columns": ["legacy_col"], "density": "compact",
    "freeze_first_col": True, "decimals": 2}}

# KPI: open with 1m compare period
{"widget": "kpi", "initial_state": {"compare_period": "1m", "sparkline_visible": True,
    "delta_visible": True, "decimals": 1}}
```

#### 4.1.3 Auto stat strip (Σ button → popup)

Every supported time-series chart (`line`, `multi_line`, `area`) gets a small **Σ** button in its toolbar (next to the `⋮` controls drawer toggle). Clicking it opens a popup with one row per visible series carrying current value, deltas at standard horizons (`1d` / `5d` / `1m` / `3m` / `YTD` / `1Y`), 1Y high-low range, and 1Y percentile rank. Computed on-demand (no inline rendering, no compile-time payload), so it always reflects current state -- including drawer transforms or filter state.

Format choice (bp / pct+abs / pp / arithmetic) follows `field_provenance.units`:

| units | delta format | example |
|-------|--------------|---------|
| `percent` / `pct` / `%` | bp arithmetic | `4.07%  Δ5d -6bp` |
| `bp` / `basis_points` | bp arithmetic | `-28bp  Δ5d +4bp` |
| `index` / `usd` / `eur` | pct + abs | `4,869  Δ5d +1.5% (+71)` |
| `z` / `zscore` / `sigma` | arithmetic | `1.8  Δ5d +0.6` |
| `pp` / `percentage_points` | pp arithmetic | `+18.4%  Δ5d +1.2pp` |
| (missing) | magnitude heuristic | falls back to pct |

Per-spec overrides: `"stat_strip": False` to suppress; or `"stat_strip": {"horizons": ["1d","5d","1m","YTD","1Y"], "delta_format": "bp", "show_range": True, "show_percentile": True}`. The Σ button is automatically suppressed for chart types where the strip doesn't apply (anything other than line/multi_line/area).

PRISM contract: every dataset backing a charted column should carry `field_provenance.units`. The popup degrades gracefully when units are missing (heuristic kicks in), but explicit units always read better.

### 4.2 KPI widget

**Source path syntax.** `source` (and `delta_source`) use dotted notation `<dataset>.<aggregator>.<column>`. `sparkline_source` drops the aggregator: `<dataset>.<column>`. Aggregators: `latest` / `first` / `sum` / `mean` / `min` / `max` / `count` / `prev`.

For time-series datasets (rows are dates):
- `rates.latest.us_10y` -- last numeric value of `us_10y`
- `rates.prev.us_10y` -- second-to-last (drives delta vs prev)
- `rates.mean.us_10y` -- mean of all numeric values

For categorical / summary datasets (rows are entities like tickers, countries), source paths still work but the aggregator collapses N rows to one number, which is rarely what you want. Two alternatives:

```python
# Pivot a multi-row summary so KPIs read it as a single-row "latest"
kpi_df = pd.DataFrame([{'AAPL_eps': 8.98, 'MSFT_eps': 18.49, 'NVDA_eps': 8.93}])
kpi_df['date'] = latest_date
manifest['datasets']['kpis'] = kpi_df
# "source": "kpis.latest.AAPL_eps"

# Or skip source entirely for categorical data:
{"widget": "kpi", "id": "kpi_aapl", "label": "AAPL NTM EPS", "value": 8.98, "w": 3}
```

| Key | Purpose |
|-----|---------|
| `value` / `source` | Direct override (skips `source`); dotted `<dataset>.<agg>.<column>` |
| `sub` | Subtext under the value |
| `delta` / `delta_source` / `delta_pct` | Direct delta or dotted source (delta = current - prev); `delta_pct` auto-computed from `delta_source` if absent |
| `delta_label` / `delta_decimals` | Label after delta / precision (default 2) |
| `prefix` / `suffix` / `decimals` | Prepended / appended (`$`, `%`, `bp`); precision for value (default 2 for <1000, else 0) |
| `sparkline_source` | Dotted: `<dataset>.<column>` for inline sparkline (no aggregator) |
| `format` | `"auto"` (default; `2820` → `2,820`), `"compact"` (K/M/B/T), `"comma"`, `"percent"`, `"raw"` |

```json
{"widget": "kpi", "id": "k10y", "label": "10Y", "w": 3,
  "source": "rates.latest.us_10y", "suffix": "%",
  "delta_source": "rates.prev.us_10y", "delta_label": "vs prev",
  "sparkline_source": "rates.us_10y"}
```

### 4.3 Rich table widget

Pass `dataset_ref` and the table renders every column by default. For production dashboards, declare `columns[]` for per-column labels, formatters, tooltips, conditional formatting, color scales, plus search / sort / row-click popups.

```json
{"widget": "table", "id": "rv_table", "w": 12, "dataset_ref": "rv",
  "title": "RV screen (click a row for detail)",
  "searchable": true, "sortable": true,
  "max_rows": 50, "row_height": "compact",
  "empty_message": "No metrics match the current filters.",
  "columns": [
    {"field": "metric", "label": "Metric", "align": "left", "tooltip": "RV metric name"},
    {"field": "current", "label": "Current", "format": "number:2", "align": "right"},
    {"field": "z", "label": "Z", "format": "signed:2", "align": "right",
      "color_scale": {"min": -2, "max": 2, "palette": "gs_diverging"}},
    {"field": "pct", "label": "Pctile", "format": "percent:0", "align": "right",
      "conditional": [
        {"op": ">=", "value": 0.85, "background": "#c53030", "color": "#fff", "bold": true},
        {"op": "<=", "value": 0.15, "background": "#2b6cb0", "color": "#fff", "bold": true}]}],
  "row_click": {"title_field": "metric",
                "popup_fields": ["metric", "current", "z", "pct", "note"]}}
```

**Per-column fields:**

| Key | Purpose |
|-----|---------|
| `field` (req) / `label` | Column name in dataset; header label (defaults to field) |
| `format` | `text` / `number[:d]` / `integer` / `percent[:d]` / `currency[:d]` / `bps[:d]` / `signed[:d]` / `delta[:d]` / `date` / `datetime` / `link` |
| `align` / `sortable` / `tooltip` | `left` / `center` / `right` (auto-right for numeric); defaults to table-level; hover text on header + cells |
| `conditional` | First-match-wins rules: `{op, value, background?, color?, bold?}` (op from filter ops set) |
| `color_scale` | Continuous heatmap: `{min, max, palette}` (`gs_diverging` / `gs_blues`) |

**Table-level fields:** `searchable`, `sortable`, `downloadable` (XLSX button; default `true`), `row_height` (`compact` / default), `max_rows` (default 100), `empty_message`.

**`row_click`** opens a click-popup modal. Two modes:

*Simple mode* -- key/value table:

```json
"row_click": {"title_field": "ticker", "popup_fields": ["ticker", "sector", "last", "d1_pct"]}
```

*Rich drill-down mode* -- mini-dashboard inside the modal. Sections: stats, markdown (with `{field}` template substitution), charts filtered to clicked row, sub-tables. Modal widens to 880 px when `detail.wide: True`:

```json
"row_click": {
  "title_field": "issuer",
  "subtitle_template": "CUSIP {cusip} - {coupon_pct:number:2}% coupon - matures {maturity}",
  "detail": {"wide": true, "sections": [
    {"type": "stats", "fields": [
      {"field": "price", "label": "Price", "format": "number:2"},
      {"field": "ytm_pct", "label": "YTM", "format": "number:2", "suffix": "%"},
      {"field": "spread_bp", "label": "Spread", "format": "number:0", "suffix": " bp"}]},
    {"type": "markdown", "template": "**{issuer}** - rated `{rating}`."},
    {"type": "chart", "title": "Price history (180 biz days)",
      "chart_type": "line", "dataset": "bond_hist",
      "row_key": "cusip", "filter_field": "cusip",
      "mapping": {"x": "date", "y": "price"}, "height": 220},
    {"type": "table", "title": "Recent events", "dataset": "bond_events",
      "row_key": "issuer", "filter_field": "issuer", "max_rows": 6,
      "columns": [{"field": "date"}, {"field": "event"}]}]}}
```

**Section types inside `detail.sections`:**

| Type | Purpose |
|------|---------|
| `stats` | Dense KPI-style row. `fields[]`: string OR `{field, label, format, prefix, suffix, sub, signed_color}` |
| `markdown` | Paragraph with `{field}` / `{field:format}` template substitution. Full markdown grammar (4.8) |
| `chart` | Embedded mini-chart. `chart_type` ∈ `line` / `bar` / `area`; dataset + `filter_field` / `row_key` to scope. Supports `mapping.y` (col or list), `annotations`, numeric `height` |
| `table` | Sub-table from filtered manifest dataset. `max_rows` caps length |
| `kv` / `kv_table` | Key/value table for subset of `row` fields |

**Template substitution** (`{field:format}`): formats match column formats (`number:N`, `signed:N`, `percent:N`, `currency:N`, `bps:N`, `delta:N`, `date`). Unknown fields pass through.

**Modal close**: X button, ESC, overlay click.

**Row-level highlighting** (`row_highlight`): list of rules evaluated per row; first match wins. Each rule: `{field, op, value, class}` where `op` is `==, !=, >, >=, <, <=, contains, startsWith, endsWith` and `class` ∈ `"pos"` / `"neg"` / `"warn"` / `"info"` / `"muted"`. The row gets a tinted background + left-edge accent stripe.

```json
"row_highlight": [
  {"field": "d1_pct", "op": ">",  "value":  2.0, "class": "pos"},
  {"field": "d1_pct", "op": "<",  "value": -2.0, "class": "neg"},
  {"field": "ticker", "op": "==", "value": "GS",  "class": "info"}]
```

### 4.4 Chart click popups (`click_popup`)

Data-point analog of `row_click`. Click any point in scatter / line / bar / area / candlestick / bullet / pie / donut / funnel / treemap / sunburst / heatmap / calendar_heatmap → corresponding row opens in the same modal grammar (simple mode or rich `detail.sections` mode):

```json
{"widget": "chart", "id": "carry_roll", "w": 8, "h_px": 480,
  "title": "Carry vs roll, by sector", "subtitle": "Click any point for the bond's profile.",
  "spec": {"chart_type": "scatter", "dataset": "bonds",
            "mapping": {"x": "carry_bp", "y": "roll_bp", "color": "sector"}},
  "click_popup": {"title_field": "issuer",
    "subtitle_template": "CUSIP {cusip} - {sector} - {coupon_pct:number:2}% coupon",
    "detail": {"wide": true, "sections": [
      {"type": "stats", "fields": [
        {"field": "carry_bp", "label": "Carry", "format": "number:1", "suffix": " bp"},
        {"field": "ytm_pct",  "label": "YTM",   "format": "number:2", "suffix": "%"}]},
      {"type": "markdown", "template": "**{issuer}** - *{sector}*\n\n{blurb}"},
      {"type": "chart", "title": "OAS spread history",
        "chart_type": "line", "dataset": "bond_hist",
        "row_key": "cusip", "filter_field": "cusip",
        "mapping": {"x": "date", "y": "spread_bp"}, "height": 220}]}}}
```

Simple mode: `"click_popup": {"title_field": "issuer", "subtitle_template": "{sector} - {rating}", "popup_fields": [{"field": "carry_bp", "label": "Carry", "format": "number:1", "suffix": " bp"}, ...]}`. `popup_fields` accepts plain field-name strings OR `{field, label, format, prefix, suffix}` dicts -- mix freely.

**Row resolution.** ECharts hands click params; compiler maps to a dataset row by `chart_type` + `mapping`:

| Chart type | params → row |
|------------|--------------|
| line / multi_line / area / bar / bar_horizontal / scatter / scatter_multi / candlestick / bullet | `rows[dataIndex]` of (filter-stripped) dataset; with `mapping.color` set, filter by `color_col == params.seriesName` first |
| pie / donut / funnel / treemap / sunburst | match `mapping.category` / `mapping.name` cell `== params.name` |
| heatmap / calendar_heatmap | reconstruct unique x/y categories and match pair / match `mapping.date` cell `== params.value[0]` |
| histogram / radar / gauge / sankey / graph / tree / parallel_coords / boxplot | not row-resolvable; click is a no-op |

For grouped charts (`mapping.color` set), compiler reads the raw column value off the live ECharts option (`series._column`) so lookup matches the dataset cell after humanise renames.

**Filter awareness.** Popup pulls the current filter-stripped view for charts that auto-rewire on filter change; other charts pull from the unfiltered dataset.

### 4.4.1 Data provenance & source attribution (PRISM contract)

Every line / bar / point / row / cell carries the upstream identifier plus source system. The compiler does NOT introspect `df.attrs`; PRISM cleans upstream metadata into the canonical shape and passes it explicitly. Vendor-agnostic: two universal keys (`system`, `symbol`) plus optional rendering keys. The renderer treats `system` as opaque -- adding a new data source is one PRISM-side adapter (~10 lines), no echarts code change.

**The contract**: attach `field_provenance` (and optionally `row_provenance_field` + `row_provenance`) alongside `source`.

```python
manifest["datasets"]["rates"] = {
    "source": df_rates,
    "field_provenance": {
        "UST10Y": {"system": "market_data", "symbol": "IR_USD_Treasury_10Y_Rate",
                    "tsdb_symbol": "ustsy10y", "display_name": "US 10Y Treasury Rate",
                    "units": "percent", "source_label": "GS Market Data"},
        "JCXFE":  {"system": "haver", "symbol": "JCXFE@USECON",
                    "haver_code": "JCXFE@USECON", "units": "percent",
                    "source_label": "Haver Economics"},
        "us_2s10s": {"system": "computed", "recipe": "UST10Y - UST2Y",
                      "computed_from": ["UST10Y", "UST2Y"], "units": "bp"}}}
```

**Per-column provenance keys** (all but `system` / `symbol` optional, all free-form strings):

| Key | Purpose |
|-----|---------|
| `system` | Source slug: `haver`, `market_data`, `plottool`, `fred`, `bloomberg`, `refinitiv`, `factset`, `csv`, `computed`, `manual`, **or any string PRISM picks for a new vendor**. Renderer treats as opaque -- no validation against a known list |
| `symbol` | **Universal primary identifier. ALWAYS populate.** Footer's `<code>` rendering keys off it. Pass the exact upstream string (`GDP@USECON`, `IR_USD_Treasury_10Y_Rate`, `DGS10`, `USGG10YR Index`, `AAPL-US.GAAP.EPS_DILUTED`, ...) |
| `display_name` / `units` / `source_label` | Human-readable footer label; `percent` / `bp` / etc.; vendor attribution (`GS Market Data`, `Haver Economics`, `Bloomberg`, ...) |
| `recipe` / `computed_from` | For `system: "computed"`: free-form formula string + list of source columns the recipe references |
| `as_of` | ISO timestamp of the latest tick at column level |
| `<vendor_alt>` | System-specific alternate id: `haver_code`, `tsdb_symbol`, `fred_series`, `bloomberg_ticker`, `refinitiv_ric`, `factset_id`. Add `<new>_id` for any new vendor. Always populate `symbol` -- the legacy fallback list does NOT include new vendors |

**Mapping pattern (uniform across data fns).** Every `pull_<vendor>_data()` cleans into `system=<slug>`, `symbol=<primary_id>`, `<vendor>_<altkey>=<primary_id>`, `display_name`, `units`, `source_label="<Vendor>"`. For a new vendor: pick a `system` slug, map the primary id into `symbol`, pick a `source_label`, carry over `display_name` / `units`. One ~10-line cleaning helper, no echarts code change. Edge cases: hand-entered → `system: "manual"` + `display_name`; computed → `system: "computed"` + `recipe` + `computed_from`; CSV → `system: "csv"` + `symbol=<file_basename:col>`. Never drop provenance silently.

**Mixed-vendor columns** (one column, different upstream per row) use `row_provenance_field` + `row_provenance` to override per row:

```python
{"source": df_screener,
 "field_provenance": {"last": {"system": "market_data", "source_label": "GS Market Data"}},
 "row_provenance_field": "ticker",
 "row_provenance": {
    "AAPL": {"last": {"system": "market_data", "symbol": "EQ_US_AAPL_Last",
                       "source_label": "GS Market Data"}},
    "TSLA": {"last": {"system": "bloomberg", "symbol": "TSLA US Equity",
                       "source_label": "Bloomberg"}}}}
```

**Where it surfaces.** (1) Auto-default popup when `field_provenance` is set but no `click_popup`/`row_click` declared (minimal modal + Sources footer). (2) Sources footer auto-appended to every explicit popup; suppress per popup with `show_provenance: false`. (3) Inline source line under `detail.sections[type=stats]` via `show_source: true`. Opt-out: `click_popup: false` / `row_click: false`. PRISM rule: every dataset backing a chart or table carries `field_provenance`. Validation only warns, but coverage is expected.

### 4.4.2 In-cell visualisations (table column `in_cell`)

Per-column `in_cell` adds a visual encoding alongside the formatted text:

| `in_cell` | Behavior |
|-----------|----------|
| `"bar"` | Horizontal bar inside cell, width proportional to value's position in column range. Values crossing zero anchor at column-center (positive grows right, negative grows left). Override via `bar_color_pos` / `bar_color_neg` |
| `"sparkline"` | Inline 80×16 SVG reading from a sibling dataset. Requires `from_dataset` + `row_key` + `filter_field`. Optional `value` (numeric col on sibling; defaults to `row_key`), `show_text: false` (hide cell number) |

```python
{"widget": "table", "dataset_ref": "tickers",
  "columns": [
    {"field": "ticker", "label": "Ticker"},
    {"field": "ret",  "label": "1d ret",  "format": "signed:2", "in_cell": "bar"},
    {"field": "ytd",  "label": "YTD %",   "format": "signed:1", "in_cell": "bar"},
    {"field": "ticker", "label": "Spark (60d)",
      "in_cell": "sparkline", "from_dataset": "ticker_history",
      "row_key": "ticker", "filter_field": "ticker", "value": "price",
      "show_text": False}]}
```

Bar normalises against **visible-row** range (after filter + search). Sparklines fall back to a flat dot when <2 numeric values for a row.

### 4.5 stat_grid widget

Dense grid of label / value stats -- for when a row of KPIs would take too much vertical space.

```json
{"widget": "stat_grid", "id": "summary", "w": 12, "title": "Risk summary",
  "info": "Rolling risk metrics aggregated across the full book.",
  "stats": [
    {"id": "s1", "label": "Beta to SPX", "value": "0.82", "sub": "60D", "trend": 0.04,
      "info": "OLS beta of book P&L vs S&P 500 TR, trailing 60 biz days."},
    {"id": "s2", "label": "Duration", "value": "4.8y", "sub": "DV01 $280k"},
    {"id": "s3", "label": "Gross leverage", "value": "2.3x", "sub": "vs 3.0x cap", "trend": 0.1},
    {"id": "s4", "label": "HY OAS", "value": "285 bp", "sub": "z = -1.1", "trend": -0.05}]}
```

| Field | Purpose |
|-------|---------|
| `id` / `label` / `sub` | Optional DOM id; title line (small caps, dim); secondary caption |
| `value` / `source` | Pre-formatted (no number formatting applied) OR dotted `<dataset>.<agg>.<column>` |
| `info` (alias `description`) / `popup` | Hover tooltip + click modal; `{title, body}` markdown popup |
| `trend` | Optional numeric delta. Positive = green up, negative = red down |

### 4.5a Pivot widget

Long-form dataset → interactive crosstab where the viewer picks row dim, col dim, value column, aggregator from author-supplied whitelists. "Show me sector × country breakdown of YTD perf, actually pivot it by sector × beta-decile, actually agg on median" -- three different tables become one widget.

```python
{"widget": "pivot", "id": "perf_pivot", "w": 12,
  "title": "Sector × window perf", "subtitle": "Drag the dropdowns to repivot.",
  "dataset_ref": "perf_long",
  "row_dim_columns": ["sector", "country", "ticker"],
  "col_dim_columns": ["window"],
  "value_columns":   ["ret", "ret_pct"],
  "agg_options":     ["mean", "median", "sum", "min", "max", "count"],
  "row_default": "sector", "col_default": "window",
  "value_default": "ret", "agg_default": "mean",
  "decimals": 2, "color_scale": "diverging", "show_totals": True}
```

| Key | Required | Purpose |
|-----|----------|---------|
| `dataset_ref` | yes | Long-form dataset (one row per `(row_cat, col_cat, value)`) |
| `row_dim_columns` / `col_dim_columns` / `value_columns` | yes | Whitelists |
| `agg_options` | no | Default `["mean", "sum", "median", "min", "max", "count"]` |
| `row_default` / `col_default` / `value_default` / `agg_default` / `decimals` | no | Initial selections; cell precision (default 2) |
| `color_scale` / `show_totals` | no | `"sequential"` / `"diverging"` / `"auto"` (diverging when crosses 0) / `false`; append row/col totals (recomputed, not summed from cells; default `True`) |

Filters targeting `dataset_ref` flow through naturally. User's last dropdown selections survive URL state encoding (`#p.<id>.r=...&p.<id>.c=...`).

### 4.6 Image / markdown / divider

```json
{"widget": "image", "id": "logo", "w": 3,
  "src": "https://.../gs_logo.png", "alt": "Goldman Sachs", "link": "https://..."}

{"widget": "markdown", "id": "md", "w": 12,
  "content": "### Method\nSynthetic UST panel. **Brush** the curve to cross-filter."}

{"widget": "divider", "id": "sep"}
```

### 4.7 Note widget (semantic callout)

Tinted card with colored left-edge stripe keyed by `kind`. Use when a paragraph is load-bearing -- the thesis, the risk, the watch level -- and you want the reader to find it without re-reading the whole page.

Required: `id`, `body` (markdown). Optional: `kind` (default `insight`) / `title` / `icon` (1-2 char glyph) / `w` (1..12, default 12) / `footer` / `popup` / `info`.

| Kind | Visual | Use for |
|------|--------|---------|
| `insight` | sky stripe + sky tint (default) | Observation / "the lightbulb" |
| `thesis` | navy stripe + navy tint | Load-bearing claim of the dashboard |
| `watch` | amber stripe + amber tint | Levels / events to monitor |
| `risk` | red stripe + red tint | Downside / pain trades |
| `context` | grey stripe + grey tint | Background / setup info |
| `fact` | green stripe + green tint | Established / point-in-time facts |

```json
{"widget": "note", "id": "n_thesis", "w": 6,
  "kind": "thesis", "title": "Bull-steepener resumes",
  "body": "The curve is **bull-steepening** for the third session in a row.\n\n"
          "1. 2Y -6bp on the day, -18bp on the week\n2. 10Y -3bp on the day, -9bp on the week\n"
          "3. Spread widening primarily front-led, consistent with a *priced-in cut* trade"}
```

Pairing a `thesis` and `watch` note in a 6/6 row at the top is high-leverage: load-bearing claim + "what would change my mind" criteria, before any chart loads.

### 4.8 Markdown grammar (shared)

Same grammar applies to: `widget: markdown`, `widget: note` body, `metadata.summary`, `metadata.methodology`, `popup: {body}` on any tile / filter / stat, per-row `markdown` sections (4.3). The `subtitle` / `description` line on tabs is plain text, not markdown.

| Block | Syntax |
|-------|--------|
| Headings | `# H1` ... `##### H5` (deeper clamped to h5) |
| Paragraph | Lines separated by blank line; lines within a para joined with single space |
| Unordered / ordered list | `-` or `*` (UL); `1.` / `2.` / ... (OL; numbers don't have to be sequential) |
| Nested list | Indent by **2 spaces** per level. Mix `ul`/`ol` freely; nested lists live inside parent `<li>` |
| Blockquote / code block | `> ...`, multi-line accumulates / triple-backtick fenced (optional language tag) |
| Table | GFM: header row, separator `\| --- \| --- \|`, body rows. Alignment hints `:---` / `---:` / `:---:` |
| Horizontal rule | A line containing only `---`, `***`, or `___` |
| Inline | `**bold**` / `*italic*` / `~~strike~~` / `` `code` `` / `[label](url)` (opens in new tab) |

Anything that does not match is escaped as plain text -- including raw HTML.

---

## 5. Filters

```json
{"id": "region", "type": "multiSelect", "default": ["US", "EU"],
  "options": ["US", "EU", "JP", "UK"],
  "targets": ["*"], "field": "region", "label": "Region"}
```

`options` can also be `{value, label}` dicts when visible text differs from underlying value:

```json
{"id": "mode", "type": "radio", "default": "sell",
  "options": [
    {"value": "sell", "label": "Looking to Sell (Feel Best to Buy)"},
    {"value": "buy",  "label": "Looking to Buy (Feel Best to Sell)"}],
  "targets": ["screener"], "field": "mode", "label": "Mode"}
```

**Nine filter types:**

| Type | UI | Applies to |
|------|-----|-----------|
| `dateRange` | select 1M/3M/6M/YTD/1Y/2Y/5Y/All | Charts (view-mode default): sets initial `dataZoom` window. Tables/KPIs/stat_grids: row-filters `rows[field]`. `mode: "filter"` row-filters charts too |
| `select` | `<select>` | `rows[field] == value` |
| `multiSelect` | `<select multiple>` | `rows[field] in [values]` |
| `radio` | radio button group | same as `select`, different UI |
| `numberRange` | text `min,max` | `min <= rows[field] <= max` |
| `slider` | range input + value | `rows[field] op value` (op defaults `>=`) |
| `number` | number input | `rows[field] op value` (op defaults `>=`) |
| `text` | text input | `rows[field] op value` (op defaults `contains`) |
| `toggle` | checkbox | `rows[field]` truthy when checked |

**`dateRange` semantics on charts.** Time-series charts ship with their own `dataZoom` (5.1). A `dateRange` filter is a global "initial lookback" knob, not a data filter -- changing the dropdown moves every targeted chart's visible window via `dispatchAction({type:'dataZoom'})` and leaves the underlying dataset untouched. Tables/KPIs/stat_grids targeted by the same filter still see real row-filtering. Pass `"mode": "filter"` to force row-filter on charts (e.g. histograms / aggregates that must recompute over the window).

**Fields:**

| Field | Purpose |
|-------|---------|
| `id` / `type` (req) | Unique id; one of the 9 types above |
| `default` / `label` | Initial value; display label |
| `field` | Dataset column to filter against |
| `op` | `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith` |
| `transform` | `abs` / `neg` applied to cell before compare (e.g. `\|z\|` filters) |
| `options` | Required for select/multiSelect/radio. List of primitives OR `{value, label}` dicts |
| `min` / `max` / `step` | Required for slider; optional for number |
| `placeholder` / `all_value` | Placeholder text for text/number; "no filter" sentinel (`"All"`, `"Any"`) |
| `targets` | List of widget ids to refresh. `"*"` = all data-bound. Wildcards: `"prefix_*"`, `"*_suffix"` |
| `description` (aliases `help`, `info`) / `popup` | Help text + info icon; `{title, body}` markdown popup for click |
| `scope` | `"global"` (top filter bar) or `"tab:<id>"` (inline). Auto-inferred from targets |

**Filter placement is auto-scoped.** Filters targeting multiple tabs or `"*"` go in the global bar (top of dashboard); filters whose targets all resolve to a single tab go in a tab-inline bar. Override with explicit `scope`.

**Which chart types reshape on filter change.** Auto-wire happens when chart_type + mapping is safe to re-shape client-side: `line` / `multi_line` / `bar` / `area` with simple wide-form mapping (no `color` long-form, no `stack`, no `trendline`). Tables, KPIs, stat_grids, and chart types with computed series data (histograms, bullets, candlesticks, heatmaps, scatter-with-trendline, radar, gauge, sankey, treemap, sunburst, funnel, parallel_coords, tree, graph, boxplot) keep their baseline data.

### 5.0a Cascading filters (`depends_on` + `options_from`)

A filter declares `depends_on: <upstream_filter_id>` + `options_from: {dataset, key, where?}`. When the upstream changes, dependent rebuilds options from the named dataset, optionally filtered by `where` substituting upstream values via `${filter_id}`.

```python
"filters": [
    {"id": "region", "type": "select", "label": "Region", "default": "NA",
      "options": ["NA", "EU", "AP"], "field": "region", "targets": ["country_view"]},
    {"id": "country", "type": "select", "label": "Country",
      "depends_on": "region",
      "options_from": {"dataset": "universe", "key": "country",
                         "where": "region == ${region}"},
      "options": ["US"], "field": "country", "targets": ["country_view"]},
    {"id": "ticker", "type": "select", "label": "Ticker",
      "depends_on": "country",
      "options_from": {"dataset": "universe", "key": "ticker",
                         "where": "country == ${country}"},
      "options": [""], "field": "ticker", "targets": ["country_view"]}]
```

Supported `where` ops: `==`, `!=`, `>`, `>=`, `<`, `<=`. The dependent filter's existing value is preserved when valid in the new option set; otherwise falls back to first new option (or empty for `multiSelect`). Cascades chain (region → country → ticker) -- when region changes, both country and ticker rebuild in dependency order.

Validation: `depends_on` must reference a declared filter id; self-dependency raises an error.

### 5.1 Per-chart zoom (in-chart `dataZoom`)

Every chart with `time` x-axis ships with two `dataZoom` controls injected at compile time (independent of any `dateRange` filter): `type: "inside"` (mouse wheel / pinch zoom + click-and-drag pan) and `type: "slider"` (draggable slider beneath the grid). Full dataset embedded; slider clips visible window. `grid.bottom` auto-bumps. Opt-out for sparkline-style tiles via `chart_zoom: false` on `spec` (or `mapping`); builders that already declared their own `dataZoom` (e.g. candlestick) are left alone.

```json
{"widget": "chart", "id": "tiny_sparkline", "w": 3,
  "spec": {"chart_type": "line", "dataset": "rates",
            "mapping": {"x": "date", "y": "us_2y"}, "chart_zoom": false}}
```

### 5.2 `click_emit_filter`

Turn a data-point click on one chart into a filter change driving downstream widgets:

```json
"click_emit_filter": "sector_filter"

"click_emit_filter": {
    "filter_id": "sector_filter",
    "value_from": "name",     // "name" (default) | "value" | "seriesName"
    "toggle": true              // re-clicking same value clears (default true)
}
```

`filter_id` must reference a `select` or `radio` filter whose `targets` point at the widgets to re-render. Click-through navigation pattern: click sector slice on a donut → filter screener table to that sector.

---

## 6. Links (sync + brush)

```json
"links": [
    {"group": "sync", "members": ["curve", "spread"],
      "sync": ["axis", "tooltip", "dataZoom"]},
    {"group": "brush", "members": ["curve", "spread"],
      "brush": {"type": "rect", "xAxisIndex": 0}}
]
```

`sync` values: `axis`, `tooltip`, `legend`, `dataZoom`. At load, runtime sets `chart.group = group` and calls `echarts.connect(group)`.

`brush.type`: `rect`, `polygon`, `lineX`, `lineY`. When user brushes on any member chart, runtime extracts `coordRange`, filters linked charts' datasets to brushed range on x axis, re-renders all linked charts. Clearing brush resets dataset to original contents.

`members` accepts widget ids or wildcards. Unknown sync entries / brush types raise validation errors.

---

## 7. Layouts (grid + tabs)

```python
# Grid (default, simple)
"layout": {"kind": "grid", "cols": 12, "rows": [
    [widget, widget, ...],     # rows of widgets; widths must sum to <= cols
    [widget, ...]]}

# Tabs
"layout": {"kind": "tabs", "cols": 12, "tabs": [
    {"id": "overview", "label": "Overview",
      "description": "Short summary shown under the tab title",
      "rows": [...]},
    {"id": "detail", "label": "Detail", "rows": [...]}]}
```

Tabs lazily initialise charts on first activation; last-active tab persisted in `localStorage` per dashboard id.

| Tab field | Purpose |
|-----------|---------|
| `id` (req) | Stable slug used in DOM ids and localStorage keys |
| `label` | Visible tab text |
| `description` | (1) Italic secondary text below tab bar when active, (2) hover tooltip on the tab button |
| `rows` | List-of-lists of widgets |

---

## 8. Header actions

Optional `manifest.header_actions[]` appends custom buttons / links to the header (left of the standard top-right protocol). Use for dashboard-specific escape hatches.

| Key | Purpose |
|-----|---------|
| `label` (req) | Display text |
| `href` | If set, renders `<a>` (opens in new tab by default) |
| `onclick` | Name of a global JS function. One of `href` / `onclick` is required |
| `target` | `"_self"` to open inline (defaults to `_blank`) |
| `id` | Optional DOM id |
| `primary` | `True` → GS Navy primary button styling |
| `icon` | Optional leading glyph |
| `title` | Hover tooltip |

---

## 9. Tooltips, info icons, popups

Two classes of help UI: **hover tooltips** (browser `title=` attribute, 1-2 word clarifications) and **click popups** (centered modal, paragraph-length explanations, X / ESC / overlay-click to close).

Every info icon does BOTH: hover shows short text, clicking opens the same content in a modal. Set `popup: {title, body}` on the same widget / filter / stat to give the modal richer markdown while keeping `info` as the hover line.

| Surface | Field | Appears as |
|---------|-------|-----------|
| Any widget header | `info`, `popup`, `subtitle`, `footer`/`footnote` | info icon (hover + click modal); italic sub; small text below body |
| Table column header / cell | `columns[i].tooltip` | `title=` on header + cell |
| Table row | `row_highlight` rules | tinted row + left-edge accent |
| Table row click | `row_click` (simple `popup_fields` OR rich `detail.sections[]`) | modal: key/value or drill-down |
| stat_grid cell | `stats[i].info`, `stats[i].popup` | info icon next to label |
| Filter control | `description` / `help` / `info`, `popup` | info icon next to filter label |
| Tab button | `tabs[i].description` | hover tooltip + italic sub |
| Header action / chart action button | `.title` | native browser tooltip |
| Chart tooltip (hover) | `spec.tooltip` | ECharts tooltip with custom formatter |
| Chart annotation | `annotations[i].label` | permanent label on annotation |
| Chart data-point click | `click_popup` (simple OR `detail.sections[]`) | modal: key/value or drill-down |
| Click / row auto-default | `field_provenance` set, no explicit popup | minimal modal with mapped fields + Sources footer. Suppress with `click_popup: false` / `row_click: false` |
| Sources footer (every popup) | `field_provenance` auto-appended | trailing "Sources" table. Suppress per popup with `show_provenance: false` |

**Modal behavior**: X button, ESC, overlay click. Only one modal visible at a time.

Markdown in popups uses the shared grammar (4.8). Use sparingly -- a dashboard with an info icon on every control is louder than one without.

---

## 10. Runtime features

Rendered automatically -- PRISM doesn't configure anything extra.

| Feature | Trigger |
|---------|---------|
| Data freshness badge / Methodology popup | `metadata.data_as_of` (or `generated_at`) / `metadata.methodology` |
| Refresh button | `metadata.kerberos` + `dashboard_id`, `refresh_enabled != False`. POSTs to `/api/dashboard/refresh/`, polls every 3s up to 3 min, reloads on success |
| Download Charts / Panel / Excel | one 2× PNG per chart (always) / full view as single 2× PNG via `html2canvas@1.4.1` (always) / one sheet per table when any `widget: table` exists (reflects current filter/search/sort) |
| Per-tile controls drawer / PNG / fullscreen / XLSX | every chart/table/KPI (see 10.1); chart toolbar PNG with title+subtitle baked; fullscreen toggle; per-table XLSX (`downloadable: False` to hide) |
| Per-chart `dataZoom` (inside + slider) | every time-axis chart; suppress with `chart_zoom: false`. See 5.1 |
| Tab persistence / Filter reset | last-active tab via `localStorage` / filter-bar Reset button |
| Brush cross-filter / Chart sync (connect) | drag-select on linked chart filters all members / tooltips / axes / legend / dataZoom synchronised across `sync` group |
| Row-click / chart-click modal | `row_click` / `click_popup` configured. Auto-fires minimal popup if `field_provenance` set but no popup declared. Suppress with `*: false` |
| Click-emit-filter | data-point click drives filter change. See 5.2 |
| Sources footer (every popup) | auto-appended from `field_provenance`. Suppress per popup with `show_provenance: false` |
| Table search / sort / conditional + color-scale cells | when `searchable` / `sortable: true`; per column spec |
| In-cell bars / sparklines / row highlighting | `columns[i].in_cell` (`bar` or `sparkline`); `row_highlight` rules (tinted + accent stripe) |
| KPI sparklines | when `sparkline_source` is set |
| Auto stat strip (Σ button) | toolbar of every line / multi_line / area chart; click for popup with value, deltas, range, percentile per visible series. Units from `field_provenance`. Suppress with `stat_strip: false` |
| URL state (shareable views) | active tab + filters + chart-drawer state + table sort/search + KPI compare period + pivot dropdowns serialise to URL hash; restored on load. Send the URL → recipient sees same view |
| Conditional widget visibility / Cascading filters | `show_when` (4.1.1); `depends_on` + `options_from` (5.0a) |
| Pivot dropdowns / Responsive layout | row/col/value/agg dropdowns wired automatically for every `widget: pivot` (4.5a); tiles collapse to 6 cols < 1024 px, 12 cols < 720 px |

### 10.1 Per-tile controls drawer (`⋮`)

Every chart / table / KPI tile carries a `⋮` button. Drawer populates lazily on first open with only the knobs the underlying widget supports.

**Chart drawer sections** (only those that apply to the chart type):

| Section | Knobs |
|---------|-------|
| Series | per-series `transform` + show/hide checkbox (line / multi_line / area, wide-form). Long-form (`mapping.color`) gets a single chart-wide transform |
| Shape | `Style` (solid/dotted/dashed) + `Step` (off/start/middle/end) + `Width` (1/2/3 px) + `Area fill` + `Stack` (group / stack / 100% stacked) + `Markers` |
| Chart | `Smoothing` (off/5/20/50/200) + `Y-scale` (linear/log) + `Y-range` (auto/from-zero) |
| Bar / Bar_horizontal | `Sort` (input order / value desc / value asc / alphabetical) + `Stack` (grouped / stacked / 100% stacked) |
| Scatter / Scatter_multi | `Trendline` (off / linear OLS) + `X-scale` (linear/log) |
| Scatter_studio | X / Y / color / size dropdowns (from author whitelists) + per-axis transform + `Window` + `Outliers` + `Regression` |
| Heatmap / correlation_matrix | `Color scale` (sequential / diverging) + `Labels` + `Auto-contrast` |
| Pie / Donut | `Sort` (input order / largest first) + `"Other" bucket` (group slices below 1%/3%/5%) |
| Calendar_heatmap | `Labels` toggle (default off) |
| Actions | `View data` / `Copy CSV` / `Reset chart` / `Download PNG` (2×, title baked) / `Download CSV` / `Download XLSX` |

When every visible series shares the same transform, y-axis name auto-tags (e.g. ` (YoY %)`); each transformed series' legend entry gets a `· Δ` / `· z` suffix.

**Time-series transforms** (all client-side, no PRISM round-trip):

| Transform | Notes |
|-----------|-------|
| `raw`, `change` (Δ), `pct_change` (%Δ), `log_change` | period over period |
| `yoy_change` (YoY Δ), `yoy_pct` (YoY %), `yoy_log` | look up `t-365d` via binary search |
| `annualized_change` | `Δ × f`; `f` auto-detected from median timestamp gap (≈daily→252, weekly→52, monthly→12, quarterly→4, semi→2, annual→1) |
| `log` | `ln(v[i])` for `v[i] > 0`; non-positive points drop |
| `zscore` | `(v[i] - mean) / std` over visible window |
| `rolling_zscore_252` | 252-day rolling z; `min_periods=2`. Pattern `rolling_zscore_<N>` for arbitrary windows |
| `rank_pct` | Percentile rank (0..100), ties → average rank |
| `ytd` | `v[i] - v[anchor]` where anchor = first non-null point of same calendar year |
| `index100` | `v[i] / anchor * 100` where anchor = first non-zero non-null point |

**Table drawer.** Search input + sort-by-column + asc/desc + per-column visibility checkboxes + density (regular/compact) + freeze-first-col + decimals override. Actions: `View raw`, `Copy CSV`, `Download CSV`, `Download XLSX`, `Reset table`. Suppress with `table_controls: false`.

**KPI drawer.** Compare-period dropdown (auto/prev/1d/5d/1w/1m/3m/6m/1y/YTD; only when `sparkline_source` is set; recomputes delta on the fly), sparkline visibility toggle, delta visibility toggle, decimals override. Actions: `View data`, `Copy CSV`, `Download CSV`, `Download XLSX`, `Reset KPI`. Suppress with `kpi_controls: false`.

**Suppressing per widget:** `chart_controls: False` on `spec`; `table_controls: False` / `kpi_controls: False` on the widget.

Drawer state is exposed for inspection / scripting:

```js
window.DASHBOARD.chartControlState['curve'].series['us_10y'].transform = 'rolling_zscore_252';
window.DASHBOARD.chartControlState['curve'].shape = {lineStyleType: 'dashed', step: 'middle'};
window.DASHBOARD.tableState['screener'].hidden = {2: true};
window.DASHBOARD.kpiState['fed_funds'].comparePeriod = '1m';
```

---

## 11. Validation + diagnostics

### 11.1 `validate_manifest`

```python
ok, errs = validate_manifest(manifest)
```

Rules:
- `schema_version` must equal `1`; `id`, `title` must be present
- `theme`, `palette` must be registered names
- Each dataset entry must be `{"source": [...]}` (DataFrames normalised first). Optional `field_provenance` (dict of dicts), `row_provenance_field` (str), `row_provenance` validated for shape only -- inner provenance keys are free-form
- Filter `id` unique; `type` in valid set; `select`/`multiSelect`/`radio` require `options`; `slider` requires `min`+`max`; `slider`/`number`/`text` require `field`
- Each widget `id` unique; widths sum ≤ `cols`
- Widget-specific required fields enforced (chart needs spec/ref/option, kpi needs label, table needs ref/dataset_ref, stat_grid needs stats[], image needs src/url, markdown needs content, note needs body + valid kind)
- Chart `spec` requires `chart_type` (in 30-type set), `dataset` (must reference declared), `mapping`
- Chart `click_popup` / table `row_click`, when present, must be a dict OR boolean `false` (suppress auto-default provenance popup)
- Filter `targets` must match real widget ids (wildcards OK); link members same
- `sync` ∈ `{axis, tooltip, legend, dataZoom}`; `brush.type` ∈ `{rect, polygon, lineX, lineY}`
- `metadata.refresh_frequency` ∈ `{hourly, daily, weekly, manual}`

Returns `(ok, [errors...])`. Each error is human-readable, identifies the offending path.

### 11.2 `chart_data_diagnostics`

`validate_manifest` checks structure. **`chart_data_diagnostics(manifest)` checks the data actually wires up** -- empty datasets, missing columns, all-NaN series, non-numeric values, missing mapping keys, filter fields that don't exist, dataset shape, size budgets.

```python
diags = chart_data_diagnostics(manifest)
for d in diags:
    print(d.severity, d.code, d.widget_id, d.message)

r = compile_dashboard(manifest)                 # default: strict=True, raises on error diags
r = compile_dashboard(manifest, strict=False)   # keep going so PRISM can fix all in one round-trip
```

**Strict mode** (`strict=True`, default) raises `ValueError` listing every error-severity diagnostic. `strict=False` keeps going. Warnings/info never trigger strict-mode failure. Refresh pipelines + CI inherit strict default. Contract: a broken headline number is a broken dashboard.

`Diagnostic` is a dataclass with `severity` (`error`/`warning`/`info`), stable `code`, `widget_id`, dotted manifest `path`, `message`, and a `context` dict carrying actionable repair data:
- `did_you_mean` -- close-match suggestions for typo'd column / dataset names
- `fix_hint` -- one-sentence repair instruction (surfaced as `-> fix:` line)

**Stable diagnostic codes** (pattern-match on `code` for automated repair):

| Code | Severity | Fires when |
|------|----------|------------|
| `chart_dataset_empty` / `chart_dataset_single_row` | error / warn | 0 rows / 1 row in series chart |
| `chart_mapping_required_missing` | error | Required mapping key absent (e.g. pie needs `category`+`value`) |
| `chart_mapping_column_missing` | error | Mapping references column not in dataset (`did_you_mean`) |
| `chart_mapping_column_all_nan` / `_mostly_nan` | error / warn | All NaN / ≥50% NaN |
| `chart_mapping_column_non_numeric` | error | Numeric-required key (y/value/size/weight/low/high/open/close) isn't numeric-coercible |
| `chart_constant_values` | warn | Numeric y has single unique value; renders as flat line |
| `chart_negative_values_in_portion` | error | Pie/donut/funnel/sunburst/treemap value contains negatives |
| `chart_sankey_self_loops` / `_disconnected` | error/warn / warn | Edges where source==target / source/target sets share no nodes |
| `chart_candlestick_inverted` | error | OHLC inversions (high<low, open>high, ...) |
| `chart_tree_orphan_parents` | error | `mapping.parent` values not in `mapping.name` |
| `chart_build_failed` | error | Builder raised at compile (`context.exception_type` carries cause) |
| `table_dataset_empty` | warn | Table's `dataset_ref` has 0 rows |
| `table_column_field_missing` / `_columns_all_missing` | error | `columns[].field` not in dataset / EVERY defined column missing (`did_you_mean`) |
| `kpi_no_value_no_source` / `_value_is_placeholder` | error | Neither `value` nor `source`, or `value` is `--` / `n/a` |
| `kpi_source_malformed` | error | `source`/`delta_source` not in `dataset.agg.column` form, or `sparkline_source` not `dataset.column` |
| `kpi_source_dataset_unknown` / `_aggregator_unknown` / `_column_missing` | error | Reference undeclared / aggregator not in allow-list / column not in dataset (`did_you_mean`) |
| `kpi_source_no_numeric_values` / `_sparkline_too_short` | error / warn | Source column has zero numerics / `sparkline_source` <2 numeric values |
| `stat_grid_no_value_no_source` / `_value_is_placeholder` / `_source_unresolvable` | error | No `value`/`source`, placeholder string, or `source` not resolvable at compile time (server-rendered, no JS resolution) |
| `filter_field_missing_in_target` | error | Filter `field` not in any target widget's dataset |
| `filter_default_not_in_options` / `_targets_no_match` | warn | `default` not in `options` / every non-wildcard target resolves to no widget |
| `dataset_dti_no_date_column` | error | DataFrame has DatetimeIndex and no `date` column AND chart/filter references `date`. Fires when PRISM forgets `df.reset_index()` |
| `dataset_passed_as_tuple` | error | Dataset is a tuple -- catches the `pull_market_data` "didn't unpack `(eod_df, intraday_df)`" mistake |
| `dataset_columns_multiindex` | error | DataFrame columns is `pd.MultiIndex`; compiler does not auto-flatten |
| `dataset_column_looks_like_code` | warn | Column matches opaque-code pattern (Haver `X@Y`, coordinates, whitespace, slashes); rename to plain English |
| `dataset_metadata_attrs_unused` | info | DataFrame has `df.attrs['metadata']` AND columns still match raw codes; suggests building rename map from attrs |
| `dataset_rows_{warning,error}` / `_bytes_{warning,error}` | warn/err | ≥10K/50K rows; ≥1MB/2MB bytes |
| `manifest_bytes_{warning,error}` / `table_rows_{warning,error}` | warn/err | Total `manifest.datasets` ≥3MB/5MB; table-widget dataset ≥1K/5K rows |

Both `compile_dashboard` and renderer are **resilient by design**: a chart that fails to build (missing column, malformed mapping, builder raise) gets a `(no data)` placeholder + `chart_build_failed` diagnostic. Dashboard still renders, sibling charts still work, PRISM gets the full failure list in one round-trip.

---

## 12. Persistence + refresh

NON-NEGOTIABLE: every user-requested dashboard persists to `users/{kerberos}/dashboards/{name}/`. A dashboard living only in `SESSION_PATH` won't refresh, won't appear in the user's list, and is lost when the conversation ends.

### 12.1 Three-tool-call build model

```
Tool 1: pull_data.py     Pulls DataFrames, saves raw CSVs to {DASHBOARD_PATH}/data/
Tool 2: build.py         Loads data, populates manifest template, compiles, uploads
Tool 3: register         Updates registry + user manifest
```

Each tool call uses `execute_analysis_script.script` to BOTH execute logic in the current session AND persist that same logic to S3 under `{DASHBOARD_PATH}/scripts/` for the refresh pipeline. Order is non-negotiable (Section 0): `pull_data.py` must complete with real DataFrames -- printed `df.shape` / `df.head()` / `df.dtypes` -- before `build.py` is authored. Write the manifest *against verified shapes*, never imagined columns.

**Tool 1 -- `pull_data.py`** (~50-150 lines depending on sources): pulls DataFrames, writes raw CSVs to `{DASHBOARD_PATH}/data/`, persists itself to `{DASHBOARD_PATH}/scripts/pull_data.py`. Print informative log lines (`[pull_data.py] Starting at <ts>`, `EOD shape: ...`, `Intraday: available | NOT AVAILABLE (normal overnight)`).

**Tool 2 -- `build.py` (one-shot first build):** compose the full manifest with DataFrames, derive a template (`manifest_template(initial_manifest)` strips data, keeps structure), compile + upload. From that point, the persisted refresh-time `build.py` only needs `populate_template(template, fresh_dfs)` -- the structural manifest never has to be rewritten.

```python
df = pd.read_csv(io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                 index_col=0, parse_dates=True)

manifest = {
    "schema_version": 1, "id": DASHBOARD_NAME, "title": "Rates Monitor",
    "metadata": {"kerberos": KERBEROS, "dashboard_id": DASHBOARD_NAME,
                  "data_as_of": str(df.index.max().date()),
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "sources": ["GS Market Data"], "refresh_frequency": "daily",
                  "refresh_enabled": True, "tags": ["rates"]},
    "datasets": {"rates": df.reset_index()},
    "layout": {"rows": [[{"widget": "chart", "id": "curve", "w": 12, "title": "UST Curve",
        "spec": {"chart_type": "multi_line", "dataset": "rates",
                  "mapping": {"x": "date",
                               "y": ["IR_USD_Swap_2Y_Rate", "IR_USD_Swap_10Y_Rate"]}}}]]}}

tpl = manifest_template(manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(), f'{DASHBOARD_PATH}/manifest_template.json')

r = compile_dashboard(manifest, write_html=False, write_json=False, strict=True)
if not r.success: raise ValueError(f"COMPILE FAILED: {r.error_message}")
s3_manager.put(r.html.encode('utf-8'), f'{DASHBOARD_PATH}/dashboard.html')
s3_manager.put(json.dumps(manifest, indent=2).encode('utf-8'),
                f'{DASHBOARD_PATH}/manifest.json')
```

The persisted `scripts/build.py` (~12 lines) is the refresh-time variant -- loads the template + fresh CSVs, calls `populate_template`, compiles, uploads.

**Tool 3 -- register:** writes the per-dashboard pipeline manifest, upserts an entry into `users/{kerberos}/dashboards/dashboards_registry.json` (`id`, `name`, `description`, `created_at`, `last_refreshed`, `last_refresh_status`, `refresh_enabled`, `refresh_frequency`, `folder`, `html_path`, `data_path`, `tags`, `keep_history`, `history_retention_days`), then calls `update_user_manifest(kerberos, artifact_type='dashboard')`. Always print the portal URL (`http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{DASHBOARD_NAME}/`) -- the persistent, auto-refreshing link.

### 12.2 Templates: `manifest_template` + `populate_template`

Auto-injected into both the `execute_analysis_script` sandbox and the refresh-runner namespace; no import needed.

```python
# One-time: strip data rows, keep column headers + every other config
tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(),
                f'{DASHBOARD_PATH}/manifest_template.json')

# Each refresh: fresh DataFrames wired into template slots
m = populate_template(tpl, {"rates": eod_df, "cpi": cpi_df},
                         metadata={"data_as_of": "..."},
                         require_all_slots=True)
compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html')
```

Template is pure JSON (no pandas); safe to persist and diff. `require_all_slots=True` raises `KeyError` if a template slot has no DataFrame.

### 12.3 Refresh flow (high level)

Browser [Refresh] → `POST /api/dashboard/refresh/` → Django spawns `refresh_runner.py` → runs `scripts/pull_data.py` then `scripts/build.py` in order → updates `dashboards_registry.json` + `refresh_status.json` → frontend polls `GET /api/dashboard/refresh/status/` every 3s up to 3 min → on success, `location.reload()`.

API contract: HTTP 409 (already running) → switch to status polling; `status: "success"` → reload after ~1s; `status: "error"` → show error, restore button after 3s; `status: "partial"` → reload after 2s. `metadata.api_url` / `metadata.status_url` override the default endpoints.

### 12.4 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_data.py` that fetches intraday MUST wrap it in `try/except` with EOD fallback. Every `build.py` must handle missing intraday file defensively.

```python
# pull_data.py
eod_df, _ = pull_market_data(coordinates=[...], start_date='2020-01-01', name='rates_eod')
try:
    iday_df = pull_market_data(coordinates=[...], mode='iday',
                                start_date=datetime.now().strftime('%Y-%m-%d'),
                                name='rates_intraday')
except Exception as e:
    print(f"Intraday unavailable (normal overnight/weekends): {e}")
    iday_df = None

# build.py
try:
    iday_df = pd.read_csv(io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_intraday.csv')),
                          index_col=0, parse_dates=True)
except Exception:
    iday_df = None
current = (iday_df.ffill().iloc[-1] if iday_df is not None and len(iday_df) > 0
           else eod_df.iloc[-1])
```

### 12.5 Common failures → fix

| Symptom | Cause | Fix |
|---------|-------|-----|
| "No data successfully fetched" | Intraday unavailable (overnight / weekend) | try/except + EOD fallback |
| `KeyError: '<col>'` | Schema drift | check `col in df.columns` before access |
| `IndexError: .iloc[-1]` | Empty frame | guard with `len(df) > 0` |
| Empty after merge | Inner join dropped rows | outer join, handle NaNs |
| Chart shows `(no data)` | One spec failed to bind | read `compile_dashboard().diagnostics` |
| "Auto-healed stale lock" | Previous refresh hung | self-resolves; investigate slow pulls |
| Refresh button absent | `metadata.kerberos` / `dashboard_id` missing | add to metadata block |
| `FileNotFoundError` on script path | Scripts missing on S3 | rebuild scripts |

When a refresh is broken: read the registry (`last_refresh_status`, `last_refreshed`), read `refresh_status.json` (`status`, `errors[]`, `pid`), confirm artifacts on S3, fix the failing script, re-upload. Don't rebuild from scratch.

---

## 13. Sandbox patterns

`compile_dashboard`, `manifest_template`, `populate_template`, `validate_manifest`, `df_to_source`, `chart_data_diagnostics`, `load_manifest`, `save_manifest` are all auto-injected into both `execute_analysis_script` and the refresh-runner namespace. Never write `from echart_dashboard import ...` or `sys.path.insert(0, ...)`.

In the sandbox, `compile_dashboard` writes to local FS if `output_path` is given -- which is blocked by the AST checks. For persistent user dashboards, the right pattern is `write_html=False, write_json=False` and `s3_manager.put()` manually so the artifact lands at `{DASHBOARD_PATH}/dashboard.html` rather than the compiler's default `{session_path}/dashboards/{id}.html`:

```python
r = compile_dashboard(manifest, write_html=False, write_json=False, strict=True)
if not r.success: raise ValueError(f"COMPILE FAILED: {r.error_message}")
s3_manager.put(r.html.encode('utf-8'), f'{DASHBOARD_PATH}/dashboard.html')
s3_manager.put(json.dumps(manifest, indent=2).encode('utf-8'),
                f'{DASHBOARD_PATH}/manifest.json')
```

---

## 14. Common patterns

Same chart-type names + mapping keys as Section 3.

### 14.1 Long-form `multi_line` with color

```python
datasets["rates_long"] = df.melt(id_vars=['date'], var_name='series', value_name='yield')
```

```json
{"widget": "chart", "id": "curve", "w": 12, "h_px": 380, "title": "UST curve",
  "spec": {"chart_type": "multi_line", "dataset": "rates_long",
            "mapping": {"x": "date", "y": "yield", "color": "series",
                        "y_title": "Yield (%)"}}}
```

### 14.2 Actuals vs estimates via `strokeDash`

```json
{"widget": "chart", "id": "capex", "w": 12, "h_px": 380,
  "title": "Big Tech capex", "subtitle": "solid = actual, dashed = estimate",
  "spec": {"chart_type": "multi_line", "dataset": "capex",
            "mapping": {"x": "date", "y": "capex", "color": "company",
                        "strokeDash": "type", "y_title": "Capex ($B)"}}}
```

### 14.3 Dual axis

```json
{"widget": "chart", "id": "spx_ism", "w": 12, "h_px": 380, "title": "Equities vs ISM",
  "spec": {"chart_type": "multi_line", "dataset": "macro",
            "mapping": {"x": "date", "y": "value", "color": "series",
                        "dual_axis_series": ["ISM Manufacturing"],
                        "y_title": "S&P 500", "y_title_right": "ISM Index",
                        "invert_right_axis": false}}}
```

Before dual-axis: print `df['series'].unique()` and assert the right-axis name is present. Name mismatch is the #1 failure mode.

### 14.4 Bullet: rates RV screen

```python
datasets["rv"] = pd.DataFrame({"metric": [...], "current": [...],
                                "low_5y": [...], "high_5y": [...],
                                "z": [...], "pct": [...]})
```

```json
{"widget": "chart", "id": "rv_screen", "w": 6, "h_px": 480, "title": "Rates RV screen",
  "spec": {"chart_type": "bullet", "dataset": "rv",
            "mapping": {"y": "metric", "x": "current",
                        "x_low": "low_5y", "x_high": "high_5y",
                        "color_by": "z", "label": "pct"}}}
```

### 14.5 Pairing thesis + watch notes (high-leverage opening)

```json
"layout": {"rows": [
  [{"widget": "note", "id": "n_thesis", "w": 6,
     "kind": "thesis", "title": "Bull-steepener resumes",
     "body": "The curve is **bull-steepening** for the third session..."},
   {"widget": "note", "id": "n_watch", "w": 6,
     "kind": "watch", "title": "Levels to watch",
     "body": "| Level | Significance |\n|---|---|\n| 4.10% 10Y | 50dma |\n"}],
  [{"widget": "chart", "id": "curve", "w": 12, "h_px": 380, "spec": {...}}]]}
```

---

## 15. Palettes

| Palette | Kind | Use |
|---------|------|-----|
| `gs_primary` | categorical | Default (navy, sky, gold, burgundy, ...) |
| `gs_blues` | sequential | Heatmaps, calendar heatmaps, gradients |
| `gs_diverging` | diverging | Correlation matrices, z-score heatmaps |

Categorical → `option.color`. Sequential / diverging → `visualMap.inRange.color` (heatmaps, correlation matrices).

Brand hex anchors for `series_colors`: GS Navy `#002F6C`, GS Sky `#7399C6`, GS Gold `#B08D3F`, GS Burgundy `#8C1D40`, GS Forest `#3E7C17`, GS Positive `#2E7D32`, GS Negative `#B3261E`.

---

## 16. Anti-patterns

| Anti-pattern | Do instead |
|--------------|-----------|
| `np.random.*` / `np.linspace` / `np.arange` / hand-typed arrays as data; `np.zeros()` fill for missing data | Pull real data first (Section 12.1). If no source, do not build the panel; render a note or use a small real slice |
| Authoring `build.py` before `pull_data.py` produced real DataFrames | Run pulls first, print shapes/heads/dtypes, then write manifest against verified columns |
| Literal numbers in manifest JSON | Pass the DataFrame; compiler converts |
| PRISM hand-writing HTML/CSS/JS or `build.py` >50 lines | Emit manifest; `compile_dashboard()` does it |
| Source attribution in title/subtitle | `metadata.sources` for dashboard-level; `field_provenance` per-column (4.4.1) |
| Dropping provenance because vendor isn't standard | `system: "computed"` + `recipe`, or `system: "csv"` + path. Never drop |
| Annotating self-evident facts (zero on a spread) | Omit |
| Hand-tuning `y_title_gap` / `grid.left` | Just set `x_title` / `y_title`; compiler sizes from real label widths |
| Saving a user dashboard only to `SESSION_PATH`; skipping refresh button by editing HTML | Persist to `users/{kerberos}/dashboards/...`; set `metadata.kerberos` + `dashboard_id` |

---

## 17. Pre-flight checklist

- `dashboard.html` persisted to `users/{kerberos}/dashboards/{name}/`
- `metadata.kerberos` + `dashboard_id` + `data_as_of` set; `refresh_frequency` set
- `manifest_template.json` + `manifest.json` saved alongside; `scripts/pull_data.py` + `scripts/build.py` saved
- Registry entry added; `update_user_manifest(kerberos, artifact_type='dashboard')` called
- Every dataset traces to a real pull (Rule 1, Section 0); zero `np.random` / `np.linspace`-as-data / hand-typed arrays
- `pull_data.py` printed real shapes/heads/dtypes before `build.py` was authored; handles intraday failures defensively
- Every dataset cleaned: `df.reset_index()` for DTI-keyed frames, plain English columns, no MultiIndex
- Every dataset backing a chart/table carries `field_provenance` (per-column `system` + `symbol`)
- Every dataset under budget: <50K rows, <2 MB; total manifest <5 MB
- `build.py` is thin (loads data + `populate_template` + `compile_dashboard`)
- `compile_dashboard(..., strict=True)`; `write_html=False, write_json=False` + manual `s3_manager.put()` for persistent dashboards
- Download link + portal URL delivered to the user

---

## 18. Data shape preparation + budgets

**Five non-negotiables for DataFrames:**

1. **Tidy.** One row = one observation, one column = one variable. No multi-index, no embedded headers, no totals row.
2. **Date as a column.** Never as `DatetimeIndex`. Use `df.reset_index()`. Compiler emits `date` to ISO-8601; ECharts auto-detects time-axis.
3. **Plain-English columns.** `us_10y`, not `USGG10YR Index`. Compiler humanises `us_10y` → `US 10Y` and uses your column name in legends, tooltips, axis hints.
4. **Datasets named like nouns.** `rates`, `cpi`, `flows`, `bond_screen` -- not `df1`, not `usggt10y_panel`.
5. **A dataset earns its name.** Register in `manifest.datasets` if (a) more than one widget reads from it, OR (b) a single widget needs filter-aware re-rendering, OR (c) a table widget displays the rows verbatim. Otherwise inline a one-shot DataFrame is fine.

**Data archetypes → chart types:**

| # | Archetype | DataFrame shape | Chart type |
|---|-----------|-----------------|------------|
| 1 | Univariate time series | `(date, value)` | `line` |
| 2 | Multi-variable TS, fixed | `(date, v1, v2, ...)` wide | `multi_line`, `area` |
| 3 | Multi-variable TS, dynamic | `(date, group, value)` long | `multi_line` color=, `area` color= |
| 4 | Cross-section, 1 metric | `(cat, value)` | `bar`, `bar_horizontal`, `pie`, `donut`, `funnel` |
| 5 | Cross-section, grouped | `(cat, group, value)` long | `bar` stack, `scatter` color= |
| 6 | Bivariate scatter | `(x_num, y_num, [color])` | `scatter`, `scatter_multi` |
| 7 | Distribution | `(value)` one column | `histogram` |
| 8 | Distribution by group | `(group, value)` long | `boxplot` |
| 9 | Range + current marker | `(cat, lo, hi, cur, ...)` | `bullet` |
| 10 | OHLC time series | `(date, open, close, low, high)` | `candlestick` |
| 11 | Daily scalar over a year | `(date, value)` | `calendar_heatmap` |
| 12 | Cat × cat matrix | `(x_cat, y_cat, value)` long | `heatmap` |
| 12b | Wide-form TS correlation | `(date, col_a, col_b, ...)` wide | `correlation_matrix` |
| 13 | Hierarchy | path or `(name, parent, value)` | `treemap`, `sunburst`, `tree` |
| 14 | Flow / network | `(source, target, value)` | `sankey`, `graph` |
| 15 | Multi-dim by entity | `(entity, dim, value)` long | `radar`, `parallel_coords` |
| 16 | Single scalar | one number | `gauge` |
| 17 | Rich row-per-entity | `(id, attr1, attr2, ...)` wide | `table` widget |
| 18 | Latest snapshot from TS | (any TS DF) | `kpi`, source = `<ds>.latest.<col>` |
| 19 | Sparse event list | `(date, label, [color])` | annotations on another chart |
| 20 | Schedule / agenda | `(date, time, event, ...)` | `table` widget |
| 21 | Exploratory bivariate | wide numeric panel | `scatter_studio` |

**Compiler refuses to silently fix:**

| What PRISM must do | Diagnostic if skipped |
|--------------------|------------------------|
| `df.reset_index()` before passing DTI-keyed frame | `dataset_dti_no_date_column` |
| Unpack `pull_market_data` tuples: `eod_df, _ = pull_market_data(...)` | `dataset_passed_as_tuple` |
| Flatten MultiIndex: `df.columns = ['_'.join(c) for c in df.columns]` | `dataset_columns_multiindex` |
| Rename opaque API codes to plain English | `dataset_column_looks_like_code` (warn) |
| Resample to native frequency per series | mixed-freq NaN gaps render as broken stair-steps |

**Data budget limits** (enforced by `strict=True`): single dataset rows 10K (warn) / 50K (err); single dataset bytes 1 MB / 2 MB; total manifest bytes 3 MB / 5 MB; table-widget rows 1K / 5K.

Haver stores many monthly/quarterly series at business-daily granularity. Symptom: stair-step lines. Fix: resample to true native frequency before charting; never chart a DataFrame with mixed-frequency NaN gaps (resample to lowest common frequency before concat / merge).

```python
starts = starts.resample('M').last()   # stock: last-of-month
claims = claims.resample('M').mean()   # flow: mean
cpi    = cpi.resample('Q').last()      # rate: last-of-quarter
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
```

If a column is opaquely named (`JCXFE@USECON`, `IR_USD_Swap_2Y_Rate`), rename to plain-English before charting.

---

## 19. Time horizons

| Frequency | Default lookback | Rationale |
|-----------|-----------------|-----------|
| Quarterly/monthly | 10 years | Full business cycle |
| Weekly | 5 years | Trend + cycle |
| Daily | 2 years | Regime without noise |
| Intraday | 5 trading days | Event reaction window |

Override: if narrative references "highest since X", chart must include X. For pre-pandemic comparisons start ≥ 2015. Don't show 12 months of monthly (hides cycle), 30 years of daily (noise), or different ranges for charts meant to be compared.
