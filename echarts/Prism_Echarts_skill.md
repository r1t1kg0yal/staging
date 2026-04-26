# ECharts Dashboards

**Module:** `dashboards`
**Audience:** Prism (all interfaces, all workflows), developers, Observatory agents
**Tier:** 2 (on-demand)
**Scope:** ALL dashboard construction in Prism. (For one-off PNG charts in chat/email, Prism uses Altair via `make_chart()` -- not covered here.)
**Companion docs:** `DATA_SHAPES.md` (DataFrame organisation, per-archetype templates, pull-to-manifest pipeline, size budget).

A dashboard is a JSON manifest. Prism never writes HTML, CSS, or JS. Prism emits structured JSON; the compiler does the rest.

There is exactly one visual style, the Goldman Sachs brand: GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans typeface stack, thin grey grid on paper-white. No theme switcher.

**`compile_dashboard(manifest)` is the only Prism-facing entry point.** It validates a JSON manifest, lowers each `widget: chart` through internal builders, and emits an interactive dashboard HTML + manifest JSON.

For one-off PNG charts in chat / email / report, Prism uses **Altair `make_chart()`** -- a separate module not covered here.

---

## 0. The one hard rule: no literal data in JSON

Prism pulls data with existing data functions (`pull_market_data`, `pull_haver_data`, FRED, Treasury, etc.) inside `execute_analysis_script`. The resulting DataFrames flow directly into the dashboard manifest. **Prism never types numbers into the JSON.** The compiler converts DataFrames to the canonical on-disk shape automatically.

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

Three accepted shapes for a dataset entry, all normalized to the same on-disk form:

| Shape                                              | When                                                         |
|----------------------------------------------------|--------------------------------------------------------------|
| `datasets["rates"] = df`                           | Most common. Zero ceremony.                                  |
| `datasets["rates"] = {"source": df}`               | When you want to attach metadata to the entry later.         |
| `datasets["rates"] = {"source": df_to_source(df)}` | When the manifest is saved/read before the compiler touches it. |

NEVER do this:

```python
manifest = {"datasets": {"rates": {"source": [
    ["date", "us_2y", "us_10y"],
    ["2026-04-20", 4.15, 4.48],    # literal numbers in JSON
    ["2026-04-21", 4.17, 4.50],
]}}}
```

Literal data gets truncated, hallucinated, or stale within hours.

### 0.1 Computed / synthetic datasets (manifest-level expressions)

A dataset entry can declare a `compute` block listing named expressions evaluated against an existing source dataset. The compiler runs an AST-level whitelist (no `eval`, no `__import__`, no attribute access) over a small set of arithmetic + windowed helpers, materialises each output column, and auto-stamps `field_provenance` with `system: "computed"`, the recipe string, and the upstream column list. Use this instead of computing spreads / ratios / z-scores in `build.py`.

```python
manifest = {
    "datasets": {
        "rates": df_rates,                       # source columns: us_2y, us_10y, ...
        "spreads": {
            "from": "rates",                     # read columns from `rates`
            "compute": {
                "us_2s10s_bp":  "(us_10y - us_2y) * 100",
                "us_5s30s_bp":  "(us_30y - us_5y) * 100",
                "us_10y_z_60":  "zscore(us_10y, 60)",
                "spread_pct":   "pct_change(us_10y - us_2y)",
            }
        }
    },
    "layout": {"rows": [
        [{"widget": "chart", "id": "spread", "w": 12,
           "spec": {"chart_type": "line", "dataset": "spreads",
                      "mapping": {"x": "date", "y": "us_2s10s_bp",
                                   "y_title": "2s10s spread (bp)"}}}]
    ]}
}
```

After compile, `manifest["datasets"]["spreads"]` carries:
- a `source` row-of-lists containing the original date/columns + the new computed columns
- a `field_provenance` block where each computed column has `{system: "computed", recipe: "<expr>", computed_from: ["us_10y", "us_2y"], display_name: "<col>"}`
- inferred `units` when the recipe is unambiguous: `* 100` on percent-units inputs -> `bp`, `zscore(...)` -> `z`, `pct_change(...)` / `yoy_pct(...)` / `index100(...)` -> `percent`, otherwise inherit when every referenced column shares units

The same `compute` block can also append columns to an existing dataset that already has a source -- omit `from` and the compiler appends the computed columns to the entry's own source.

**Allowed function whitelist** (any other name raises a validation error):

| Group       | Functions |
|-------------|-----------|
| Arithmetic  | `+ - * / % ** //`, unary `+ -` (no other operators) |
| Numeric     | `log`, `log10`, `log2`, `exp`, `sqrt`, `abs`, `sign`, `round` |
| Aggregate   | `mean`, `std`, `min`, `max`, `sum` (broadcast scalar) |
| Series      | `zscore(x, window?)`, `rolling_mean(x, n)`, `rolling_std(x, n)`, `pct_change(x, periods?)`, `diff(x, periods?)`, `shift(x, periods?)`, `clip(x, lo?, hi?)`, `index100(x)`, `rank_pct(x)` |

Cross-dataset references work via `<other_ds>.<col>` notation:

```python
"compute": {
    "real_yield": "rates.us_10y - inflation.breakeven_10y"
}
```

**Column-name constraint.** The AST parser treats bare column names as Python identifiers, so column references in expressions must start with a letter or underscore (not a digit) and must not contain spaces / dots / dashes. Pre-rename problematic columns upstream (`df.rename(columns={"10y_real": "real_10y"})`) or compute the value inline from a reference that does parse (`"zscore(us_10y - 2.2, 60)"` instead of `"zscore(\`10y_real\`, 60)"`).

**What auto-stamping looks like.** A `rates_derived` entry computing `us_10y_z_60 = zscore(us_10y, 60)` over a rates panel produces a compiled `field_provenance` for that column of `{system: "computed", recipe: "zscore(us_10y, 60)", computed_from: ["us_10y"], units: "z"}`. The popup Sources footer on any point of the resulting chart surfaces that recipe directly.

---

## 1. Injected namespace + entry points

Inside `execute_analysis_script`, these are injected into the namespace:

```python
compile_dashboard        # manifest -> interactive dashboard HTML + manifest JSON (+ PNGs)
manifest_template        # strip data from a manifest -> reusable template
populate_template        # template + fresh DataFrames -> ready-to-compile manifest
validate_manifest        # dry-run the validator without rendering
chart_data_diagnostics   # check that data wires up correctly (missing columns, size limits)
load_manifest            # path -> manifest dict (used by refresh pipeline)
save_manifest            # manifest -> JSON file
```

One theme (`gs_clean`), three palettes (`gs_primary`, `gs_blues`, `gs_diverging`).

---

## 2. Manifest shape + metadata

### 2.1 Manifest shape

```python
manifest = {
    "schema_version": 1,
    "id": "rates_monitor",            # slug; used as filename
    "title": "Rates monitor",
    "description": "Curve, spread, KPIs.",   # optional; shown under title
    "theme": "gs_clean",              # optional; default gs_clean
    "palette": "gs_primary",          # optional; default palette-of-theme

    "metadata": {                     # optional; see 2.3
        "kerberos": "userid",
        "dashboard_id": "rates_monitor",
        "data_as_of": "2026-04-24T15:00:00Z",
        "generated_at": "2026-04-24T15:05:00Z",
        "sources": ["GS Market Data", "Haver"],
        "refresh_frequency": "daily",
        "refresh_enabled": True,
        "tags": ["rates", "curve"],
        "version": "1.0.0",
        "methodology": "## Sources\n* US Treasury OTR yields...",
    },

    "header_actions": [               # optional; see Section 8
        {"label": "Open registry", "href": "/users/userid/dashboards/"},
    ],

    "datasets": {
        "rates": df_rates,            # DataFrame -> auto-converted
        "cpi":   {"source": df_cpi},  # explicit form works too
    },

    "filters": [                      # optional; see Section 5
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
                   "source": "rates.latest.us_10y", "suffix": "%", "w": 4}],
                [{"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
                   "spec": {"chart_type": "multi_line", "dataset": "rates",
                             "mapping": {"x": "date",
                                          "y": ["us_2y", "us_5y", "us_10y"]},
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

| Field | Purpose |
|-------|---------|
| `title` / `description` | Header title + subtitle. |
| `theme` | `gs_clean` (default). The only built-in theme. |
| `palette` | `gs_primary` (default), `gs_blues` (sequential), `gs_diverging`. |
| `metadata` | Provenance + refresh block; see 2.3. |
| `header_actions` | Custom header buttons / links; see Section 8. |
| `datasets` | `{name: DataFrame \| {"source": ...}}`. |
| `filters` | See Section 5. |
| `layout` | `grid` or `tabs`; see Section 7. |
| `links` | sync + brush wiring; see Section 6. |

### 2.2 Folder structure (the unit of organization)

For **conversational** (session-only) dashboards:

```
{SESSION_PATH}/dashboards/
  {id}.json        compiled manifest (data inline)
  {id}.html        compiled dashboard
```

For **persistent user dashboards** (refresh on a schedule, appear in user's dashboard list), the compiler writes into a self-contained per-dashboard folder under `users/{kerberos}/dashboards/{name}/`. That folder is the unit of organization; everything that belongs to a dashboard lives inside it.

```
users/{kerberos}/dashboards/{dashboard_name}/
|
|-- manifest_template.json    SOURCE OF TRUTH (LLM-editable spec, NO data)
|     - schema_version, id, title, theme, palette
|     - metadata { kerberos, dashboard_id, refresh_enabled, ... }
|     - filters[], layout{}, links[]
|     - datasets:{name:{source:[[header_row]], template:true}}
|
|-- manifest.json             BUILD ARTIFACT (template + fresh data)
|     - same shape as template, but datasets fully populated
|     - written every refresh; reproduces the current dashboard exactly
|
|-- dashboard.html            DELIVERABLE (compile_dashboard output)
|     - self-contained, ECharts CDN, inline data
|     - refresh button auto-wired from metadata
|     - regenerated every refresh
|
|-- refresh_status.json       STATE FILE (written by refresh pipeline)
|     {status, started_at, completed_at, errors[], pid, auto_healed}
|
|-- thumbnail.png             OPTIONAL (rendering.save_dashboard_html_png)
|
|-- scripts/
|   |-- pull_data.py          ONLY data acquisition (~50-150 lines)
|   |-- build.py              BOILERPLATE (~15 lines, see Section 12)
|
|-- data/
|   |-- rates_eod.csv         RAW DATA CACHE (pull_data.py outputs)
|   |-- rates_intraday.csv
|
|-- history/                  OPTIONAL SNAPSHOTS (when keep_history=true)
    |-- 20260424_153000/
        |-- manifest.json
        |-- dashboard.html
```

**Hygiene rules** (forbidden -> reason):

| Forbidden | Why |
|-----------|-----|
| HTML / CSS / JS in any `.py` file | `rendering.py` owns it. Prism emits structured JSON. |
| `scripts/build_dashboard.py` | Renamed to `build.py`. Old name rejected. |
| `haver/`, `market_data/` folders | All raw data goes in `data/`. Use `name=` on data fns. |
| Timestamped scripts (`20260424_*.py`) | `scripts/` is the only source dir. |
| `*_results.md`, `*_artifacts.json` | Session-only, not dashboard-scope. |
| Multiple data JSONs | `manifest.json` is the only one. |
| Inline `<script>const DATA = {}` in HTML | Compiler embeds the manifest. Don't hand-edit HTML. |
| `sanitize_html_booleans()` calls | Compiler produces JSON-clean HTML. Helper unnecessary. |

### 2.3 Metadata block (refresh + provenance + methodology + summary)

The optional `manifest.metadata` block drives the **data-freshness badge**, **methodology popup**, **summary banner**, and **refresh button**. All fields optional -- omit for session-scope artifacts, set for persistent dashboards.

| Field | Type | Purpose |
|-------|------|---------|
| `kerberos` | str | User kerberos; required for the refresh button to render. |
| `dashboard_id` | str | Id for the refresh API; defaults to `manifest.id`. |
| `data_as_of` | str (ISO) | Timestamp of underlying data -- renders in header badge as `Data as of YYYY-MM-DD HH:MM:SS UTC`. |
| `generated_at` | str (ISO) | When this manifest was compiled. Fallback for the badge. |
| `sources` | list[str] | Data source names (e.g. `["GS Market Data", "Haver"]`). |
| `summary` | str \| dict | Markdown banner above the first row -- "today's read" / executive summary. See 2.3.2. |
| `methodology` | str \| dict | Markdown describing data sourcing/construction. Drives Methodology button + popup. See 2.3.1. |
| `refresh_frequency` | str | `hourly` \| `daily` \| `weekly` \| `manual`. |
| `refresh_enabled` | bool | Set `False` to hide refresh button (even if kerberos is set). |
| `tags` | list[str] | Free-form tags; echoed into the registry. |
| `version` | str | Manifest version string. |
| `api_url` | str | Refresh endpoint override (default `/api/dashboard/refresh/`). |
| `status_url` | str | Status endpoint override (default `/api/dashboard/refresh/status/`). |

#### 2.3.1 Methodology popup + 2.3.2 Summary banner

Both `metadata.methodology` and `metadata.summary` accept a markdown string OR a `{title, body}` dict. Both render with the shared markdown grammar (4.8). Difference: **methodology** is click-to-open via the header button (how the data is constructed); **summary** is always-visible above the first row (today's read / executive paragraph).

```python
metadata = {
    "data_as_of": "2026-04-24T15:00:00Z",
    "methodology": (
        "## Sources\n* US Treasury OTR yields (FRED H.15)\n"
        "* Global central-bank policy rates (BIS, ECB SDW)\n\n"
        "## Construction\n* 2s10s, 5s30s = simple cash differences in bp\n"
        "* 10Y real yield = 10Y nominal minus 10Y breakeven\n\n"
        "## Refresh\n* Daily after US cash close (~16:00 ET)"
    ),
    "summary": {
        "title": "Today's read",
        "body": (
            "Front-end has richened ~6bp on a softer print and a dovish-leaning Fed "
            "speaker. The curve **bull-steepened**, 2s10s out of inversion for the "
            "first time in three weeks.\n\n"
            "1. 2Y -6bp, 10Y -3bp: classic bull-steepener\n"
            "2. 5s30s flatter on long-end demand into auction\n\n"
            "> Watch 4.10% 10Y into tomorrow's PCE."
        ),
    },
}
```

#### 2.3.3 Standard top-right protocol

Fixed left-to-right header order; each element auto-shows when its enabling config is present:

| Position | Element | Visible when |
|----------|---------|--------------|
| 1 | `Data as of <ts>` | `metadata.data_as_of` or `metadata.generated_at` set |
| 2 | `Methodology` | `metadata.methodology` set |
| 3 | `Refresh` | `metadata.kerberos` + `dashboard_id` set, `refresh_enabled != False` |
| 4 | `Download Charts` | always (one file per chart widget) |
| 5 | `Download Panel` | always (full view as single PNG) |
| 6 | `Download Excel` | dashboard has at least one `widget: table` |

`header_actions[]` (Section 8) injects custom buttons in front of this bar.

### 2.4 `compile_dashboard` parameters

| Parameter | Purpose |
|-----------|---------|
| `manifest` | Dict, JSON string, or path to manifest JSON file. |
| `session_path` | Writes `{sp}/dashboards/{id}.json` + `{id}.html`. |
| `output_path` | Explicit HTML path; the `.json` is written alongside. |
| `base_dir` | Resolves `widget.ref` paths against this directory. Defaults to (1) `base_dir` arg if supplied, (2) loaded manifest file's parent, (3) current working directory. |
| `write_html` / `write_json` | Disable either emit independently (default `True`). Useful in the sandbox where outputs are saved manually via `s3_manager.put()`. |
| `save_pngs=True` | Also render each chart widget to PNG (one PNG per `widget: chart`, with title/subtitle baked in). |
| `png_dir` | Override the PNG output directory (default `{output_path}_pngs/`). |
| `png_scale=2` | Device-pixel multiplier for PNGs (1 = baseline, 2 = retina, 4 = print-quality). |
| `strict=True` (default) | Hard-fail on any error-severity diagnostic (size budget, missing column, dataset shape, KPI source typo). Production default. Pass `strict=False` for iteration mode. |
| `user_id` | Stamped into editor HTML / spec sheet localStorage scoping. |

Returns `DashboardResult(success, html_path, manifest_path, html, warnings, diagnostics, error_message)`. `result.html` is the raw HTML string (handy when `write_html=False` and you want to write to S3 manually).

---

## 3. Chart specs (for chart widgets)

Every `widget: chart` uses ECharts under the hood. Chart type, mapping, and styling live in the widget's `spec` block (variants in 4.1).

### 3.1 Chart types (30)

| chart_type | Required mapping keys |
|------------|------------------------|
| `line` | `x`, `y`, optional `color` |
| `multi_line` | `x`, `y` (list) OR `x`, `y`, `color` |
| `bar` | `x` (category), `y`, optional `color`, `stack` (bool) |
| `bar_horizontal` | `x` (value), `y` (category), optional `color`, `stack` |
| `scatter` | `x`, `y`, optional `color`, `size`, `trendline` |
| `scatter_multi` | `x`, `y`, `color`, optional `trendlines` |
| `scatter_studio` | none required; author-supplied whitelists drive runtime X/Y picker (see 3.1a) |
| `area` | `x`, `y` (stacked area) |
| `heatmap` | `x`, `y`, `value` |
| `correlation_matrix` | `columns` (list of >=2 numeric columns), optional `transform`, `method`, `order_by` (see 3.1b) |
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
| `gauge` | `value` (number or column), optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`, optional `year` |
| `funnel` | `category`, `value` |
| `parallel_coords` | `dims` (list), optional `color` |
| `tree` | `name`, `parent` |
| `waterfall` | `x` (category), `y` (signed delta), optional `is_total` (bool column flagging totals) |
| `slope` | `x` (snapshot column with exactly 2 distinct values), `y`, `color` (per-line category) |
| `fan_cone` | `x`, `y` (central path), `bands` (list of `{lower, upper, label?, opacity?}` dicts) |
| `marimekko` | `x` (column-axis cat), `y` (row-axis cat), `value` (cell magnitude), optional `order_x`, `order_y` |
| `raw` | pass `option=...` directly (passthrough) |

Unknown `chart_type` raises `ValueError`. Datetime columns auto-resolve to `xAxis.type='time'`; numeric to `'value'`; everything else to `'category'`. Missing columns raise `ValueError` listing the actual DataFrame columns -- no silent fallback.

#### Finance-flavoured shapes (waterfall / slope / fan_cone / marimekko)

* **`waterfall`** -- decomposition / attribution. Each row is an incremental delta (positive green / negative red) or a full-height total (drawn from zero) when its `is_total` cell is truthy. Use for P&L bridges, performance attribution, factor decomp.
  ```json
  {"chart_type": "waterfall", "dataset": "pnl_bridge",
    "mapping": {"x": "step", "y": "delta", "is_total": "is_total",
                  "y_title": "Contribution (bp)"}}
  ```
* **`slope`** -- compares N categories at exactly two snapshots, joining each category's left and right values with a sloped line. Right-edge label per line. Use for "month-end vs latest" / "before vs after" comparisons.
  ```json
  {"chart_type": "slope", "dataset": "perf",
    "mapping": {"x": "snapshot", "y": "ret", "color": "sector",
                  "y_title": "Return (%)"}}
  ```
* **`fan_cone`** -- forecast ribbon: a central path plus N stacked confidence bands rendered with declining opacity outside-in. Use for FOMC dot-plot fans, forecast distributions, scenario cones.
  ```json
  {"chart_type": "fan_cone", "dataset": "forecast",
    "mapping": {"x": "date", "y": "central",
                  "bands": [
                      {"lower": "p10", "upper": "p90", "label": "10-90%"},
                      {"lower": "p25", "upper": "p75", "label": "25-75%"}
                  ]}}
  ```
* **`marimekko`** -- 2D categorical proportions. Each x-category gets a column whose width is its share of total; within a column, y-categories stack at heights proportional to their share of that column's total. Use for cap-weighted allocation by sector x size, allocation by region x asset class.
  ```json
  {"chart_type": "marimekko", "dataset": "alloc",
    "mapping": {"x": "sector", "y": "size_bucket", "value": "share"}}
  ```

### 3.1a `scatter_studio` -- exploratory bivariate analysis

Use when the analyst should pick X / Y / color / size / per-axis transform / regression interactively. Author whitelists columns; regression line, R-squared, p-value, window slicer are wired automatically.

Mapping schema (every key optional unless noted):

| Mapping key | Purpose |
|-------------|---------|
| `x_columns` | Numeric columns shown in the X dropdown. Default: every numeric column in the dataset. |
| `y_columns` | Numeric columns shown in the Y dropdown. Default: every numeric column. |
| `color_columns` | Categorical columns shown in the Color dropdown. Default: empty (no color selector). |
| `size_columns` | Numeric columns shown in the Size dropdown. Default: empty. |
| `x_default`, `y_default` | Initial axis selections. Validator picks `x_columns[0]` / a non-X `y_columns` entry when omitted or invalid. |
| `color_default`, `size_default` | Initial color / size selections. |
| `order_by` | Sort key for order-aware transforms (`pct_change`, `yoy_pct`, `change`, `rolling_zscore_*`). Default: first datetime-like column in the dataset; required if any order-aware transform is in `studio.transforms`. |
| `label_column` | Row label used in the tooltip header / click_popup template. Default: `order_by`. |
| `x_transform_default`, `y_transform_default` | Initial per-axis transforms. Default `'raw'`. |

`spec.studio` block (sibling to `mapping`, all optional):

| Studio key | Purpose |
|------------|---------|
| `transforms` | Curated list of per-axis transform names. Default: `['raw', 'log', 'change', 'pct_change', 'yoy_pct', 'zscore', 'rolling_zscore_252', 'rank_pct']`. The viewer's per-axis Transform dropdown is populated from this list. |
| `regression` | Allowed regression options. Default: `['off', 'ols', 'ols_per_group']`. |
| `regression_default` | Initial regression mode. Default: `'off'`. |
| `windows` | Allowed window slices (only meaningful when `order_by` is set). Default: `['all', '252d', '504d', '5y']`. |
| `window_default` | Initial window. Default: `'all'`. |
| `outliers` | Allowed outlier filters. Default: `['off', 'iqr_3', 'z_4']`. |
| `outlier_default` | Default: `'off'`. |
| `show_stats` | Bool, default `True`. When true, a stats strip below the canvas reports `n`, Pearson `r` (with significance stars), `R squared`, slope `beta` with standard error, intercept `alpha`, RMSE, and p-value. |

Per-axis transforms (mirrored Python `_compute_transform` and JS `_ccColumnTransform`):

| Transform | Definition | Order-aware? |
|-----------|------------|--------------|
| `raw` | identity | no |
| `log` | natural log; non-positive values dropped | no |
| `change` | `x[i] - x[i-1]` | yes (`order_by`) |
| `pct_change` | `(x[i] - x[i-1]) / x[i-1] * 100` | yes |
| `yoy_change` | `x[i] - x[j]` where `j` is the most recent row at-or-before `t-365d` | yes |
| `yoy_pct` | YoY percent change against the same lookup | yes |
| `zscore` | `(x - mean(x)) / sample_stdev(x)` over the visible (post-window, post-filter) rows | no |
| `rolling_zscore_<N>` | rolling-window z-score; `N` is the window in rows. Default offering is `rolling_zscore_252`. | yes |
| `rank_pct` | percentile rank in `[0, 100]`; ties get the average rank | no |
| `index100` | reindex to 100 at the first non-zero non-null row | no |

Stats strip output:

```
n=247  r=0.68***  R^2=0.46  beta=0.42 (SE 0.03)  alpha=1.18  RMSE=0.31  p=4.2e-9
```

Stars: `***` p<0.001 / `**` p<0.01 / `*` p<0.05 / `·` p<0.10 (normal-approx tail of t-stat -- display only). With `regression: ols_per_group` the strip lists per-color stats (`r`, `R squared`, `beta`, `n`) below the overall row.

Author example:

```json
{
  "widget": "chart", "id": "yields_vs_breakevens", "w": 12, "h_px": 480,
  "spec": {
    "chart_type": "scatter_studio",
    "dataset": "macro_panel",
    "title": "Yields vs breakevens (exploratory)",
    "mapping": {
      "x_columns":     ["us_2y", "us_10y", "real_10y", "ig_oas"],
      "y_columns":     ["breakeven_5y5y", "vix", "spx_pe", "ig_oas"],
      "color_columns": ["regime", "fed_stance"],
      "order_by":      "date",
      "x_default":     "us_10y",
      "y_default":     "breakeven_5y5y",
      "color_default": "regime",
      "label_column":  "date"
    },
    "studio": {
      "transforms":    ["raw", "log", "pct_change", "yoy_pct", "zscore", "rolling_zscore_252"],
      "regression":    ["off", "ols", "ols_per_group"],
      "show_stats":    true
    }
  }
}
```

Edge cases: `n<2` after filtering -> `n<2 -- regression unavailable`; zero X-variance -> line suppressed; `log` on negatives drops those rows; filter narrowing -> studio recomputes everything against the filtered subset.

### 3.1b `correlation_matrix` -- N x N correlation heatmap from a column list

Use for "how do these N series co-move?" The builder applies a per-column transform (correlate `% changes` instead of levels), computes the correlation matrix, emits a diverging heatmap pinned to `[-1, 1]`.

Mapping schema:

| Mapping key | Purpose |
|-------------|---------|
| `columns` | List of numeric column names, length >= 2. Required. |
| `method` | `'pearson'` (default) or `'spearman'` (rank correlation; robust to monotonic non-linearity). |
| `transform` | Per-column transform applied before correlation. Default `'raw'`. Same names as `scatter_studio.studio.transforms`. |
| `order_by` | Required when `transform` is order-aware (`pct_change` / `yoy_pct` / `change` / `rolling_zscore_*`). Default: first datetime-like column. |
| `min_periods` | Minimum number of overlapping non-null pairs to report a correlation. Default 5. Cells below the threshold render blank. |
| `show_values` | Bool, default `True`. Print the correlation in each cell. |
| `value_decimals` | Int, default 2. |
| `value_label_color` | `"auto"` (default) for black/white contrast text, hex / rgb for fixed color, or `False` to use the ECharts default. |
| `colors` | Explicit list of color stops (overrides palette). |
| `color_palette` | Palette name (default `gs_diverging`). |

Cell tooltip prints `<row name> x <col name>: r=0.xx`. The diagonal is always `1.0`. Hover the diverging visualMap on the right edge to read off the exact r value at any color.

Author example:

```json
{
  "widget": "chart", "id": "rates_corr", "w": 6, "h_px": 380,
  "spec": {
    "chart_type": "correlation_matrix",
    "dataset": "rates_panel",
    "title": "Rates correlation (% change)",
    "mapping": {
      "columns":     ["us_2y", "us_5y", "us_10y", "us_30y", "real_10y", "breakeven_5y5y"],
      "method":      "pearson",
      "transform":   "pct_change",
      "order_by":    "date",
      "min_periods": 30
    }
  }
}
```

`correlation_matrix` for wide-form time-series panels (author gives columns; builder does math + visualMap). `heatmap` for pre-computed bivariate cells (cross-asset returns by month, hit-rate by quintile).

### 3.2 Core mapping keys (XY chart types)

| Key | Purpose |
|-----|---------|
| `x`, `y` | Required column(s). `y` can be a list for wide-form multi_line. |
| `color` | Grouping column (multi-series long form). |
| `y_title`, `x_title` | Axis titles (plain English). Prefer these over coded column names. |
| `y_title_right` | Right y-axis title when using dual-axis. |
| `x_sort` | Explicit category order (list of values). |
| `x_type` | Force `'category'` / `'value'` / `'time'` on ambiguous columns. |
| `invert_y` | Invert the y-axis (single-axis charts). |
| `y_log`, `x_log` | Use log scale on the respective axis. |
| `stack` (bar) | `True` (default) = stacked, `False` = grouped. |
| `dual_axis_series` | (legacy) List of series-name strings to render on the right axis. Use `axes` for 3+ axes. |
| `invert_right_axis` | (legacy) Flip the right axis (rates-style "up = bullish"). Use `axes[i].invert` for 3+ axes. |
| `axes` | List of axis spec dicts for N-axis time series (line / multi_line / area). Each axis has its own scale, side, inversion, log, min/max, format, offset. See "Multi-axis time series" below. |
| `strokeDash` | Column controlling per-series dash pattern (e.g. actual vs estimate). |
| `strokeDashScale` | `{"domain": [...], "range": [[1,0], [8,3]]}` explicit dash mapping. |
| `strokeDashLegend` | `True` to include cross-product names in legend. |
| `trendline` (scatter) | `True` adds overall OLS line. |
| `trendlines` (scatter) | `True` adds per-group OLS lines. |
| `size` (scatter) | Column driving marker size. |
| `bins` (histogram) | Int or list of bin edges. Default 20. |
| `density` (histogram) | `True` normalizes counts to density. |

Chart-specific shapes:

| Chart | Mapping keys |
|-------|--------------|
| `sankey`, `graph` | `source`, `target`, `value`; `graph` adds `node_category` |
| `treemap`, `sunburst` | `path` (list) + `value`, or `name` + `parent` + `value` |
| `candlestick` | `x`, `open`, `close`, `low`, `high` |
| `radar` | `category`, `value`, optional `series` |
| `gauge` | `value`, optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`, optional `year` |
| `parallel_coords` | `dims` (list of columns), optional `color` |
| `tree` | `name`, `parent` |

Heatmap-style charts (`heatmap`, `correlation_matrix`, `calendar_heatmap`) accept these additional cell-label and color keys:

| Key | Purpose |
|-----|---------|
| `show_values` | Print each cell's numeric value. Default `True` for `heatmap` / `correlation_matrix`, `False` for `calendar_heatmap`. |
| `value_decimals` | Decimals on the cell label. Auto-picked from data magnitude when omitted. |
| `value_formatter` | Explicit JS formatter string (suppresses auto-contrast). |
| `value_label_color` | `"auto"` (default) for black/white contrast text, hex / rgb for fixed color, or `False` for the ECharts default. |
| `value_label_size` | Cell-label font size (default 11). |
| `colors` | Explicit list of color stops (overrides palette). |
| `color_palette` | Palette name (e.g. `gs_blues`, `gs_diverging`). |
| `color_scale` | `sequential` / `diverging` / `auto`. `auto` picks diverging when data crosses zero. |
| `value_min` / `value_max` | Pin the visualMap range so colors stay interpretable across reruns. |

Auto-contrast text is implemented through ECharts rich-text styles (`label.rich.l` for dark text on light cells, `label.rich.d` for light text on dark cells) and a JS formatter that wraps each value with the right style based on the cell color's WCAG sRGB luminance. ECharts heatmap series do not evaluate `label.color` as a callback -- that path is static-only -- which is why auto-contrast routes through rich text instead.

#### Multi-axis time series (`mapping.axes`)

Line / multi_line / area accept an arbitrary number of independent y-axes via `mapping.axes`. Each axis spec dict supports its own scale, side, inversion, log, range bounds, and tick formatter. The 2-axis API (`dual_axis_series` + `invert_right_axis`) still works; `axes` takes precedence when both are present.

```json
{
  "widget": "chart", "id": "macro_overlay", "w": 12, "h_px": 420,
  "spec": {
    "chart_type": "multi_line", "dataset": "macro",
    "mapping": {
      "x": "date",
      "y": ["spx", "ust", "dxy", "wti"],
      "axes": [
        {"side": "left",  "title": "SPX",     "series": ["spx"], "format": "compact"},
        {"side": "right", "title": "UST 10Y", "series": ["ust"], "invert": true, "format": "percent"},
        {"side": "left",  "title": "DXY",     "series": ["dxy"]},
        {"side": "right", "title": "WTI",     "series": ["wti"], "format": "usd"}
      ]
    }
  }
}
```

Per-axis spec keys: `side` (`left`/`right`, required), `title`, `series` (list of series names), `invert`, `log`, `min`/`max`, `format` (`percent`/`bp`/`usd`/`compact` or raw ECharts function string), `offset` (auto-stacked at 0, 80, 160, ... when omitted), `scale` (default `True`), `color` (axis tint; defaults to the series' palette color for single-series axes).

Mapping-level: `axis_offset_step` (default 80, controls spacing between stacked axes) and `axis_color_coding` (default `True`, can be disabled globally).

Color-coding: every axis that carries exactly one series auto-tints its axis line, tick labels, and rotated name to match the series' palette color (Bloomberg-style). Axes carrying 2+ series stay neutral unless `axes[i].color` is set explicitly.

Layout: `grid.left`/`grid.right` auto-bump to clear every offset axis plus its tick-label band. Only the first axis shows `splitLine`; additional axes hide their gridlines so the plot doesn't get crowded.

Annotations target an axis via `axis: <index>` (0..N-1). Legacy `axis: "right"` resolves to index 1 for backward compat.

**When to use `axes`:** 2 axes -> prefer `dual_axis_series` (shorter). 3+ axes across asset classes / units -> `axes`. 3+ series same unit -> one axis is right. 3+ series different units comparing patterns -> consider Index=100 normalisation instead.

### 3.3 Cosmetic / layout knobs (apply to every chart type)

Cross-cutting polish knobs on `spec` (or `mapping`), applied after the builder runs:

| Key | Purpose |
|-----|---------|
| `legend_position` | `"top"` (default), `"bottom"`, `"left"`, `"right"`, `"none"`. Auto-adjusts pie/donut to hide slice edge labels (rely on legend). |
| `legend_show` | `True` / `False`. Overrides the default for the chart type. |
| `series_labels` | Dict `{raw_name: display_name}` to override auto-humanised series names in legend. |
| `humanize` | `True` (default) / `False`. Auto-humanises snake_case (`us_10y` -> `US 10Y`). |
| `x_date_format` | `"auto"` for compact `MMM D` tick labels on date axes; pass a raw ECharts function string for custom formatting. |
| `show_slice_labels` (pie/donut) | `True` to keep per-slice edge labels even when the legend is placed top/bottom. |
| `y_min` / `y_max` | Force the y-axis range. |
| `x_min` / `x_max` | Force the x-axis range. |
| `y_format` / `x_format` | Numeric tick formatter preset. `"percent"` (x100 + %), `"bp"`, `"usd"`, `"compact"` (K/M/B), or a raw ECharts function string. |
| `y_title_gap` / `x_title_gap` | Pixels between axis tick labels and axis title. Auto-sized from the longest category-axis label by default. |
| `y_title_right_gap` | Same, for the right y-axis on dual-axis charts. |
| `category_label_max_px` | Max pixel width for category-axis tick labels (default `220`). Labels longer get `axisLabel.width` + ellipsis. |
| `grid_padding` | Dict `{top, right, bottom, left}` overriding plot-area margins. |
| `show_grid` / `show_axis_line` / `show_axis_ticks` | `False` to suppress. |
| `series_colors` | Dict `{col_name: "#hex"}` overrides palette for specific series. Column name can be raw (`"us_2y"`) or post-humanise display (`"US 2Y"`). |
| `tooltip` | Spec-level tooltip override. Sugared form: `{"trigger": "axis"|"item"|"none", "decimals": 2, "formatter": "<JS fn string>", "show": False}`. |

**Layout-aware sizing.** Axis titles never collide with tick labels. The compiler:
- Truncates long category labels to `category_label_max_px` (default 220px)
- Sizes `nameGap` from real label widths
- Bumps `grid.left` / `grid.bottom` for rotated axis names
- Auto-rotates vertical-bar / boxplot x-labels when crowded
- Bumps heatmap `grid.right` to 76px for visualMap clearance

**Per-spec overrides** (theme/palette/styling). The chart `spec` may include `palette`, `theme`, `annotations` to override manifest-level defaults for that one widget. Required keys: `chart_type`, `dataset`, `mapping`. Titles and subtitles live at the widget level only -- `spec.title` / `spec.subtitle` are rejected by the validator (see Section 4.1).

### 3.4 Annotations

Five types, all specified as dicts in `annotations=[...]` on the chart spec:

```python
"annotations": [
    {"type": "hline", "y": 2.0, "label": "Fed target",
      "color": "#666", "style": "dashed"},
    {"type": "vline", "x": "2022-03-15", "label": "Liftoff"},
    {"type": "band", "x1": "2020-03-01", "x2": "2020-06-01",
      "label": "COVID", "opacity": 0.3},
    {"type": "arrow", "x1": "2020-04-01", "y1": 5,
      "x2": "2021-03-01", "y2": 8, "label": "recovery"},
    {"type": "point", "x": "2023-06-15", "y": 4.4, "label": "peak"},
]
```

Common keys: `label`, `color`, `style` (`'solid'|'dashed'|'dotted'`), `stroke_dash` (list `[4,4]`), `stroke_width`, `label_color`, `label_position`, `opacity` (band), `head_size` / `head_type` (arrow), `font_size` (point). `band` also accepts `y1` / `y2` (horizontal band) and the aliases `x_start / x_end`, `y_start / y_end`.

For dual-axis charts, `hline` accepts `"axis": "right"` to anchor to the right y-axis.

Charts without axes (pie / donut / sankey / treemap / sunburst / radar / gauge / funnel / parallel_coords / tree) silently ignore annotations.

**Annotate regime changes, policy shifts, event dates, structural breaks.** Don't annotate self-evident facts (zero line on a spread chart; inflation target on every CPI chart).

---

## 4. Widgets

### 4.1 Widget table + presentation knobs

| Widget | Required | Purpose |
|--------|----------|---------|
| `chart` | `id`, one of `spec` / `ref` / `option` | ECharts canvas tile |
| `kpi` | `id`, `label` | Big-number tile + delta + sparkline |
| `table` | `id`, `ref` or `dataset_ref` | Rich table with sort / search / format / popup |
| `pivot` | `id`, `dataset_ref`, `row_dim_columns`, `col_dim_columns`, `value_columns` | Crosstab with row/col/value/agg dropdowns (see 4.5) |
| `stat_grid` | `id`, `stats[]` | Dense grid of label/value stats |
| `image` | `id`, `src` or `url` | Embed a static image or logo |
| `markdown` | `id`, `content` | Freeform markdown prose block (transparent) |
| `note` | `id`, `body` | **Semantic callout** for narrative writing -- tinted card with colored left-edge stripe keyed by `kind` |
| `divider` | `id` | Horizontal rule, forces row break |

Common optional fields: `w` (1-12 grid span), `h_px` (chart only; default 280), `title`, `show_when` (conditional visibility -- see 4.1.1).

#### 4.1.1 `show_when` -- conditional widget visibility

Adaptive dashboards: a widget can declare a `show_when` condition; if it fails the widget is removed (compile-time) or hidden via CSS (runtime). Two evaluation contexts:

* **Data condition** (compile-time) -- `{"data": "<dotted_source> <op> <value>"}`. Source uses the same `dataset.aggregator.column` shape KPI sources use; supported ops: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`. Widget is removed entirely from the manifest layout when the condition fails.
* **Filter condition** (runtime) -- `{"filter": "<filter_id>", "value": <v>}`, `{"filter": "<filter_id>", "in": [<v>, ...]}`, or `{"filter": "<filter_id>", "op": ">", "value": 25}`. The compiler keeps the widget in the layout and the JS runtime toggles its visibility on filter change.
* **Compound** -- `{"all": [...]}` (AND), `{"any": [...]}` (OR). Mix data and filter clauses freely; the compile-time pass evaluates only the data sub-conditions.

```python
{"widget": "note", "id": "vol_warning", "kind": "risk",
  "body": "Vol regime elevated; tighten stops...",
  "show_when": {"data": "rates.latest.vix > 25"}}              # compile-time

{"widget": "chart", "id": "fed_path",
  "show_when": {"filter": "scope", "value": "domestic"}}        # runtime

{"widget": "pivot", "id": "global_pivot",
  "show_when": {"all": [
      {"data": "market.latest.vix < 30"},                       # compile-time
      {"filter": "scope", "in": ["us", "eu"]}                   # runtime
  ]}}
```

Validation: filter-clause `filter` ids must reference declared filter ids; the validator emits an error for typos.

#### 4.1.2 Per-widget `initial_state` (opening defaults)

Every chart / table / KPI tile carries a controls drawer (`⋮` button) that mutates state at runtime. `initial_state` seeds those state objects so a chart can open in the desired view (e.g. YoY % instead of raw levels) without an extra click. Mirrors the drawer state shape; unknown keys are ignored.

```python
# Chart: open in YoY % with 5-period smoothing, log y-scale
"spec": {
    "chart_type": "line", "dataset": "rates",
    "mapping": {"x": "date", "y": "us_10y"},
    "initial_state": {
        "transform": "yoy_pct",
        "smoothing": 5,
        "y_scale": "log",
        "y_range": "from_zero",
        "shape": {"lineStyleType": "dashed", "step": "middle",
                    "width": 2, "areaFill": True, "stack": "percent"},
        "series": {"us_10y": {"transform": "log", "visible": True}},
        "bar_sort": "value_desc", "bar_stack": "stacked",
        "trendline": "linear", "color_scale": "diverging",
        "show_labels": True, "pie_sort": "largest", "pie_other_threshold": 0.05
    }
}

# Table: open with search + sort + hidden columns
{"widget": "table", "id": "rv", ..., "initial_state": {
    "search": "tech", "sort_by": "z", "sort_dir": "desc",
    "hidden_columns": ["legacy_col"], "density": "compact",
    "freeze_first_col": True, "decimals": 2
}}

# KPI: open with 1m compare period
{"widget": "kpi", "id": "k", ..., "initial_state": {
    "compare_period": "1m", "sparkline_visible": True,
    "delta_visible": True, "decimals": 1
}}
```

#### 4.1.3 Auto-computed stat strip (Sigma button -> popup)

Every supported time-series chart (`line`, `multi_line`, `area`) gets a small **Σ button** in its toolbar (next to the `⋮` controls drawer toggle). Clicking it opens a popup with one row per visible series carrying current value, deltas at standard horizons (`1d` / `5d` / `1m` / `3m` / `YTD` / `1Y`), 1Y high-low range, and 1Y percentile rank. The popup is computed on-demand (no inline rendering, no compile-time payload), so it always reflects whatever's currently on screen -- including any active drawer transforms or filter state.

The strip used to render inline above each chart, but stacking that band on every time-series tile became visually cluttering. The button-on-toolbar approach keeps the chrome quiet by default and surfaces the stats only when a reader actively asks.

Format choice (bp / pct + abs / pp / arithmetic) follows `field_provenance.units`:

| units | delta format | example |
|-------|--------------|---------|
| `percent` / `pct` / `%` | bp arithmetic | `4.07%  Δ5d -6bp` |
| `bp` / `basis_points` | bp arithmetic | `-28bp  Δ5d +4bp` |
| `index` / `usd` / `eur` | pct + abs | `4,869  Δ5d +1.5% (+71)` |
| `z` / `zscore` / `sigma` | arithmetic | `1.8  Δ5d +0.6` |
| `pp` / `percentage_points` | pp arithmetic | `+18.4%  Δ5d +1.2pp` |
| (missing) | magnitude heuristic | falls back to pct |

The popup renders one row per series with no upper limit (the modal is scrollable); on-tile space is no longer a constraint because there is no on-tile strip.

Per-spec overrides:

```python
"spec": {
    ...,
    "stat_strip": False,                          # suppress the button entirely
    # OR
    "stat_strip": {
        "horizons": ["1d", "5d", "1m", "YTD", "1Y"],
        "delta_format": "bp",                     # override units inference
        "show_range": True, "show_percentile": True
    }
}
```

The Σ button is automatically suppressed for chart types where the strip doesn't apply (anything other than `line` / `multi_line` / `area`), so authors don't need to opt out per chart type.

PRISM contract: every dataset backing a charted column should carry `field_provenance.units`. The popup degrades gracefully when units are missing (heuristic kicks in), but explicit units always read better.

**Chart widget variants: `spec` / `ref` / `option`.** Every `widget: chart` declares exactly one of three variants. Use the lowest ceremony that fits.

| Variant | Shape | When to use |
|---------|-------|-------------|
| `spec` | `{chart_type, dataset, mapping, [title, palette, ...]}` | **Preferred.** LLM-friendly. Data lives in manifest. |
| `ref` | `"echarts/mychart.json"` (relative path) | When a pre-emitted ECharts spec JSON exists on disk and you want to embed it. |
| `option` | raw ECharts option dict | Passthrough for hand-crafted options. The compiler does not validate semantics; you own correctness. |

`spec.dataset` references `manifest.datasets.<name>`. At compile time the source rows are materialized into a pandas DataFrame and fed into the per-chart-type builder. `spec.chart_type` must be one of the 30 supported types (Section 3.1). `ref` paths resolve relative to (1) `base_dir` argument to `compile_dashboard`, (2) the loaded manifest file's parent directory when `compile_dashboard(path)` is called with a path, (3) current working directory.

**`option` variant for hand-crafted ECharts.** Use when none of the 30 builder types fit. The widget passes the raw option dict straight to ECharts; the compiler injects only theme + dimensions + dataZoom (unless suppressed).

**Widget presentation knobs (apply to every tile type):**

| Field | Purpose |
|-------|---------|
| `title` | Card header text. Always lives at the widget level (sibling of `spec`), never inside `spec` -- this keeps every tile type (chart, KPI, table, markdown) on the same uniform header contract. The validator rejects `spec.title` / `spec.subtitle`. PNG export bakes the widget title back into the chart option automatically. |
| `subtitle` | Secondary italic text under title. Great for methodology notes, data vintage, scope. |
| `footer` (alias `footnote`) | Small text below tile body, separated by dashed border. Source attribution, methodology caveats. |
| `info` | Short help string. Renders an info icon: hover shows tooltip, **click opens modal** with same text. |
| `popup` | `{title, body}` for the modal when info icon is clicked. `body` is markdown. Takes precedence over `info` for modal content; `info` stays as hover tooltip. |
| `badge` | Short string (1-6 chars) as a pill next to title -- e.g. `"LIVE"`, `"BETA"`, `"NEW"`. |
| `badge_color` | `"gs-navy"` (default) / `"sky"` / `"pos"` / `"neg"` / `"muted"`. |
| `emphasis` | `True` highlights tile with thicker navy border + subtle shadow. KPIs get sky-blue top border. |
| `pinned` | `True` makes tile sticky to viewport top while scrolling. |
| `action_buttons` | List of extra buttons in chart toolbar. Each: `{label, icon?, href?, onclick?, primary?, title?}`. |
| `click_emit_filter` | (chart only) Turn data-point clicks into filter changes. Either bare filter id, or `{filter_id, value_from, toggle}` where `value_from` is `"name"` (default) / `"value"` / `"seriesName"`. |
| `click_popup` | (chart only) Turn data-point clicks into per-row detail popup. Same grammar as table `row_click`. See 4.4. |

Example chart widget using all the presentation knobs:

```json
{
  "widget": "chart", "id": "price_chart", "w": 12, "h_px": 440,
  "title": "ACME daily OHLC (1Y)",
  "badge": "LIVE", "badge_color": "pos",
  "info": "Daily OHLC. Drag the brush at the bottom to zoom.",
  "footer": "Source: GS Market Data. Updated at market close.",
  "action_buttons": [
    {"label": "Open in portal", "href": "https://example.com/acme"}
  ],
  "spec": { "chart_type": "candlestick", "dataset": "ohlc",
             "mapping": {"x": "date", "open": "open", "close": "close",
                          "low": "low", "high": "high"} }
}
```

### 4.2 KPI widget

**Source path syntax.** `source` (and `delta_source`) use dotted notation `<dataset>.<aggregator>.<column>`. The first segment is the dataset name, the second is the aggregator, the third (and any trailing dots) is the column name. `sparkline_source` drops the aggregator: `<dataset>.<column>`.

For time-series datasets (rows are dates):

- `rates.latest.us_10y` -- last numeric value of `us_10y` in dataset `rates`
- `rates.prev.us_10y` -- second-to-last numeric value (drives delta vs prev)
- `rates.mean.us_10y` -- mean of all numeric values

For categorical / summary datasets (rows are entities like tickers, countries), source paths still work but the aggregator collapses N rows to one number, which is rarely what you want. Two alternatives:

1. **Direct `value`**: pass the number you already computed in Python; skip `source` entirely.
2. **Single-row DataFrame**: pivot the summary so each metric is its own column, then point `source` at it.

```python
# Pivot a multi-row summary so KPIs can read it as a single-row "latest"
kpi_row = {'AAPL_eps': 8.98, 'MSFT_eps': 18.49, 'NVDA_eps': 8.93}
kpi_df = pd.DataFrame([kpi_row])
kpi_df['date'] = latest_date
manifest['datasets']['kpis'] = kpi_df
# Then in a widget: "source": "kpis.latest.AAPL_eps"

# Or skip source entirely for categorical data:
{"widget": "kpi", "id": "kpi_aapl", "label": "AAPL NTM EPS", "value": 8.98, "w": 3}
```

| Key | Purpose |
|-----|---------|
| `value` | Direct value override (skips `source`). Best for categorical / pre-computed numbers. |
| `source` | Dotted: `<dataset>.<agg>.<column>`. Agg in `latest \| first \| sum \| mean \| min \| max \| count \| prev`. |
| `sub` | Subtext under the value. |
| `delta` | Direct delta value. |
| `delta_source` | Dotted source (typically `<dataset>.prev.<column>`) -- delta = current - prev. |
| `delta_pct` | Direct percent change (auto-computed from `delta_source` if absent). |
| `delta_label` | Label appended after the delta (e.g. `"vs prev"`). |
| `delta_decimals` | Precision for the delta (default 2). |
| `prefix`, `suffix` | Prepended/appended to value (e.g. `$`, `%`, `bp`). |
| `decimals` | Precision for value (default 2 for < 1000, else 0). |
| `sparkline_source` | Dotted: `<dataset>.<column>` for inline sparkline (no aggregator -- plots all rows). |
| `format` | `"auto"` (default), `"compact"` (K/M/B/T), `"comma"` (full digits), `"percent"`, `"raw"`. |

```json
{"widget": "kpi", "id": "k10y", "label": "10Y",
  "source": "rates.latest.us_10y", "suffix": "%",
  "delta_source": "rates.prev.us_10y", "delta_label": "vs prev",
  "sparkline_source": "rates.us_10y", "w": 3}
```

With `format="auto"`, KPI renders `2820` as `2,820` (not `3K`). Use `format="compact"` only when abbreviated labels are explicitly desired.

### 4.3 Rich table widget

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
      "color_scale": {"min": -2, "max": 2, "palette": "gs_diverging"}},
    {"field": "pct", "label": "Pctile",
      "format": "percent:0", "align": "right",
      "conditional": [
        {"op": ">=", "value": 0.85,
          "background": "#c53030", "color": "#fff", "bold": true},
        {"op": "<=", "value": 0.15,
          "background": "#2b6cb0", "color": "#fff", "bold": true}
      ]}
  ],
  "row_click": {
    "title_field": "metric",
    "popup_fields": ["metric", "current", "z", "pct", "note"]
  }
}
```

**Per-column fields:**

| Key | Purpose |
|-----|---------|
| `field` | Column name in dataset (required). |
| `label` | Header label (defaults to field). |
| `format` | `text` / `number[:d]` / `integer` / `percent[:d]` / `currency[:d]` / `bps[:d]` / `signed[:d]` / `delta[:d]` / `date` / `datetime` / `link` |
| `align` | `left` / `center` / `right` (auto-right for numeric formats). |
| `sortable` | Defaults to table-level. |
| `tooltip` | Hover text on header and cells. |
| `conditional` | Rules fired first-match-wins: `{op, value, background?, color?, bold?}`. `op` from filter ops set. |
| `color_scale` | Continuous heatmap: `{min, max, palette}` (`gs_diverging` / `gs_blues`). |

**Table-level fields:** `searchable`, `sortable`, `downloadable` (XLSX button; default `true`), `row_height` (`compact` / default), `max_rows` (default 100), `empty_message`.

**`row_click`** opens a click-popup modal when any row is clicked. Two modes:

*Simple mode* -- key/value table:

```json
"row_click": {
  "title_field": "ticker",
  "popup_fields": ["ticker", "sector", "last", "d1_pct"]
}
```

*Rich drill-down mode* -- mini-dashboard inside the modal. Sections include stats, markdown (with `{field}` template substitution), charts filtered to clicked row, sub-tables. Modal widens to 880 px when `detail.wide: True`.

```json
"row_click": {
  "title_field": "issuer",
  "subtitle_template": "CUSIP {cusip} - {coupon_pct:number:2}% coupon - matures {maturity}",
  "detail": {
    "wide": true,
    "sections": [
      {"type": "stats",
        "fields": [
          {"field": "price", "label": "Price", "format": "number:2"},
          {"field": "ytm_pct", "label": "YTM", "format": "number:2", "suffix": "%"},
          {"field": "spread_bp", "label": "Spread", "format": "number:0", "suffix": " bp"}
        ]},
      {"type": "markdown",
        "template": "**{issuer}** - rated `{rating}`."},
      {"type": "chart",
        "title": "Price history (180 biz days)",
        "chart_type": "line",
        "dataset": "bond_hist",
        "row_key": "cusip",
        "filter_field": "cusip",
        "mapping": {"x": "date", "y": "price"},
        "height": 220},
      {"type": "table",
        "title": "Recent events",
        "dataset": "bond_events",
        "row_key": "issuer",
        "filter_field": "issuer",
        "max_rows": 6,
        "columns": [{"field": "date"}, {"field": "event"}]}
    ]
  }
}
```

**Section types inside `detail.sections`:**

| Type | Purpose |
|------|---------|
| `stats` | Dense KPI-style row. `fields[]` can be a string or `{field, label, format, prefix, suffix, sub, signed_color}`. |
| `markdown` | Paragraph with `{field}` / `{field:format}` template substitution. Full markdown grammar (4.8). |
| `chart` | Embedded mini-chart. `chart_type` in `line` / `bar` / `area`; dataset + `filter_field` / `row_key` to scope to clicked row. Supports `mapping.y` as column or list, `annotations`, numeric `height`. |
| `table` | Sub-table driven by filtered manifest dataset. `max_rows` caps length. |
| `kv` / `kv_table` | Key/value table for subset of `row` fields. |

**Template substitution** (`{field:format}`): formats match column formats: `number:N`, `signed:N`, `percent:N`, `currency:N`, `bps:N`, `delta:N`, `date`. Unknown fields pass through untouched.

**Modal close**: X button, ESC, overlay click.

**Row-level highlighting**: `row_highlight` is a list of rules evaluated per row; first match wins. Each rule: `{field, op, value, class}` where `op` is `==, !=, >, >=, <, <=, contains, startsWith, endsWith` and `class` is `"pos"`, `"neg"`, `"warn"`, `"info"`, `"muted"`. The row gets a tinted background plus a left-edge accent stripe.

```json
"row_highlight": [
  {"field": "d1_pct", "op": ">",  "value":  2.0, "class": "pos"},
  {"field": "d1_pct", "op": "<",  "value": -2.0, "class": "neg"},
  {"field": "ticker", "op": "==", "value": "GS",  "class": "info"}
]
```

### 4.4 Chart click popups (`click_popup`)

Data-point analog of `row_click`. Click any point in a scatter, line, bar, area, candlestick, bullet, pie, donut, funnel, treemap, sunburst, heatmap, or calendar_heatmap and the corresponding row in the chart's `dataset` opens in the same modal grammar tables use. Same simple / rich modes, same template substitution, same modal close.

```json
{
  "widget": "chart", "id": "carry_roll", "w": 8, "h_px": 480,
  "title": "Carry vs roll, by sector",
  "subtitle": "Click any point to open the bond's profile.",
  "spec": {
    "chart_type": "scatter", "dataset": "bonds",
    "mapping": {"x": "carry_bp", "y": "roll_bp", "color": "sector",
                  "x_title": "Carry (bp)", "y_title": "Roll (bp)"}
  },
  "click_popup": {
    "title_field": "issuer",
    "subtitle_template": "CUSIP {cusip} - {sector} - {coupon_pct:number:2}% coupon",
    "detail": {
      "wide": true,
      "sections": [
        {"type": "stats", "fields": [
          {"field": "carry_bp", "label": "Carry", "format": "number:1", "suffix": " bp"},
          {"field": "roll_bp",  "label": "Roll",  "format": "number:1", "suffix": " bp"},
          {"field": "ytm_pct",  "label": "YTM",   "format": "number:2", "suffix": "%"}
        ]},
        {"type": "markdown",
          "template": "**{issuer}** - *{sector}*\n\n{blurb}"},
        {"type": "chart", "title": "OAS spread history",
          "chart_type": "line", "dataset": "bond_hist",
          "row_key": "cusip", "filter_field": "cusip",
          "mapping": {"x": "date", "y": "spread_bp"}, "height": 220}
      ]
    }
  }
}
```

Simple mode (lighter alternative):

```json
"click_popup": {
  "title_field": "issuer",
  "subtitle_template": "{sector} - {rating}",
  "popup_fields": [
    {"field": "carry_bp", "label": "Carry", "format": "number:1", "suffix": " bp"},
    {"field": "roll_bp",  "label": "Roll",  "format": "number:1", "suffix": " bp"}
  ]
}
```

`popup_fields` accepts plain field-name strings OR `{field, label, format, prefix, suffix}` dicts -- mix freely.

**Row resolution.** ECharts hands the click handler params; the compiler maps that back to a dataset row using rules keyed off `chart_type` and `mapping`:

| Chart type | How params -> row |
|------------|-------------------|
| `line` / `multi_line` / `area` / `bar` / `bar_horizontal` / `scatter` / `scatter_multi` / `candlestick` / `bullet` (no `mapping.color`) | `rows[dataIndex]` of the (filter-stripped) dataset |
| Same chart types with `mapping.color` set | filter dataset by `color_col == params.seriesName`, then take `dataIndex`-th row of that subset |
| `pie` / `donut` / `funnel` / `treemap` / `sunburst` | match `mapping.category` (or `mapping.name`) cell `== params.name` |
| `heatmap` | reconstruct unique x/y category lists, match `(x_cat, y_cat)` cell pair |
| `calendar_heatmap` | match `mapping.date` cell `== params.value[0]` |
| `histogram` / `radar` / `gauge` / `sankey` / `graph` / `tree` / `parallel_coords` / `boxplot` | not row-resolvable; click is a no-op |

For grouped charts (`mapping.color` set), the compiler reads the raw column value off the live ECharts option (`series._column`) so the lookup matches the dataset cell exactly even after humanise renames the series.

**Filter awareness.** The popup pulls the current filter-stripped view for charts that auto-rewire on filter change. Other charts pull from the unfiltered dataset, mirroring the chart's own state.

### 4.4.1 Data provenance & source attribution (PRISM contract)

Every line / bar / point / row / cell should carry the upstream identifier plus the source system. The compiler does NOT introspect `df.attrs`; PRISM cleans upstream metadata into the canonical shape and passes it explicitly. The slot is vendor-agnostic by design: two universal keys (`system`, `symbol`) plus optional rendering keys (`display_name`, `units`, `source_label`, `recipe`, ...). The renderer treats `system` as opaque -- adding a new data source is one PRISM-side adapter (~10 lines), no echarts code change.

**The contract**: attach `field_provenance` (and optionally `row_provenance_field` + `row_provenance`) to each dataset entry alongside `source`.

```python
manifest["datasets"]["rates"] = {
    "source": df_rates,
    "field_provenance": {
        "UST10Y": {"system": "market_data",
                    "symbol": "IR_USD_Treasury_10Y_Rate",
                    "tsdb_symbol": "ustsy10y",
                    "display_name": "US 10Y Treasury Rate",
                    "units": "percent",
                    "source_label": "GS Market Data"},
        "UST2Y":  {"system": "market_data",
                    "symbol": "IR_USD_Treasury_2Y_Rate",
                    "tsdb_symbol": "ustsy2y",
                    "source_label": "GS Market Data"},
        "JCXFE":  {"system": "haver",
                    "symbol": "JCXFE@USECON",
                    "haver_code": "JCXFE@USECON",
                    "display_name": "Core PCE YoY",
                    "units": "percent",
                    "source_label": "Haver Economics"},
        "DGS10":  {"system": "fred",
                    "symbol": "DGS10",
                    "fred_series": "DGS10",
                    "source_label": "FRED"},
        "us_2s10s": {"system": "computed",
                     "recipe": "UST10Y - UST2Y",
                     "computed_from": ["UST10Y", "UST2Y"],
                     "display_name": "2s10s spread",
                     "units": "bp"},
    },
}
```

**Per-column provenance keys** (all but `system`/`symbol` are optional, all are free-form strings):

| Key             | Purpose                                                                              |
|-----------------|--------------------------------------------------------------------------------------|
| `system`        | Source system identifier: `haver`, `market_data`, `plottool`, `fred`, `bloomberg`, `refinitiv`, `factset`, `csv`, `computed`, `manual`, or **any string PRISM picks for a new vendor**. The renderer treats this as opaque -- no validation against a known list. |
| `symbol`        | **Universal primary identifier in that system. ALWAYS populate this** -- the runtime's footer keys off it for the `<code>` rendering. Pass exactly the upstream string PRISM used: `GDP@USECON`, `IR_USD_Treasury_10Y_Rate`, `sofrswp10y - sofrswp2y`, `DGS10`, `USGG10YR Index`, `AAPL-US.GAAP.EPS_DILUTED`, ... |
| `display_name`  | Human-readable label rendered in the footer (defaults to the column name).            |
| `units`         | `percent`, `bp`, `USD billion (SAAR)`, etc.                                          |
| `source_label`  | Vendor/desk attribution rendered in the footer (e.g. `GS Market Data`, `Haver Economics`, `Bloomberg`, `FactSet`, `S&P Capital IQ`). |
| `recipe`        | For `system: "computed"`. Free-form formula string: `UST10Y - UST2Y`.                 |
| `computed_from` | List of source column names the recipe references.                                    |
| `as_of`         | ISO timestamp of the latest tick at the column level.                                 |
| `<vendor_alt>`  | System-specific alternate id, optional. Common: `haver_code`, `tsdb_symbol`, `fred_series`, `bloomberg_ticker`, `refinitiv_ric`, `factset_id`. Add a new one for any new vendor (e.g. `capital_iq_id`). The renderer will fall back to a small list of historically-known alts if `symbol` is missing -- new vendors are NOT on that fallback list, so always populate `symbol`. |

**Mapping from PRISM data fns to provenance** -- the cleaning step PRISM does. Starter set; any new data source follows the same recipe (see below).

| Source fn                 | Use these keys                                                                |
|---------------------------|-------------------------------------------------------------------------------|
| `pull_haver_data()`       | `system="haver"`, `symbol=<haver_code>`, `haver_code=<haver_code>`, `display_name`, `units`, `source_label="Haver Economics"` |
| `pull_market_data()`      | `system="market_data"`, `symbol=<coordinate>`, `tsdb_symbol=<tsdb_symbol>`, `display_name`, `units`, `source_label="GS Market Data"` |
| `pull_plottool_data()`    | `system="plottool"`, `symbol=<expression>`, `display_name=<label>`, `source_label="GS plottool/TSDB"` |
| `pull_fred_data()`        | `system="fred"`, `symbol=<series_id>`, `fred_series=<series_id>`, `source_label="FRED"` |
| Bloomberg pulls           | `system="bloomberg"`, `symbol=<ticker>`, `bloomberg_ticker=<ticker>`, `source_label="Bloomberg"` |
| FactSet pulls             | `system="factset"`, `symbol=<factset_id>`, `factset_id=<factset_id>`, `display_name`, `units`, `source_label="FactSet"` |
| Refinitiv pulls           | `system="refinitiv"`, `symbol=<ric>`, `refinitiv_ric=<ric>`, `source_label="Refinitiv"` |
| Computed columns          | `system="computed"`, `recipe=<formula>`, `computed_from=[...]`, `display_name`, `units` |
| CSV / static asset master | `system="csv"`, `symbol=<file_basename:col>`, `source_label=<dataset description>` |

#### Adding a new data source (extensibility)

For any new vendor `pull_<vendor>_data()`: pick a `system` slug, map the vendor's primary id into `symbol` (always populate it -- the footer's `<code>` rendering keys off it; the legacy fallback list does NOT include new vendors), pick a `source_label`, carry over `display_name` / `units`. One ~10-line cleaning helper, no echarts code change.

```python
def factset_provenance(meta_row: dict) -> dict:
    return {
        "system": "factset", "symbol": meta_row["factset_id"],
        "factset_id": meta_row["factset_id"],
        "display_name": meta_row.get("description"),
        "units": meta_row.get("units"),
        "source_label": "FactSet",
    }

df, meta = pull_factset_data(["AAPL-US.GAAP.EPS_DILUTED", ...])
manifest["datasets"]["fundamentals"] = {
    "source": df,
    "field_provenance": {col: factset_provenance(m) for col, m in zip(df.columns, meta)},
}
```

**Edge cases.** `system="manual"` + descriptive `display_name` for hand-entered numbers (PM thresholds, annotations) -- never drop provenance silently. Mixed-vendor columns (one column, different upstream per row) use `row_provenance_field` + `row_provenance` to override per row:

```python
{
    "source": df_screener,
    "field_provenance": {"last": {"system": "market_data",
                                    "source_label": "GS Market Data"}},
    "row_provenance_field": "ticker",
    "row_provenance": {
        "AAPL": {"last": {"system": "market_data",
                            "symbol": "EQ_US_AAPL_Last",
                            "source_label": "GS Market Data"}},
        "TSLA": {"last": {"system": "bloomberg",
                            "symbol": "TSLA US Equity",
                            "source_label": "Bloomberg"}},
    },
}
```

**Where it surfaces.** (1) Auto-default popup -- when `click_popup` / `row_click` is not declared but `field_provenance` is set, clicking auto-opens a minimal modal with mapped fields + Sources footer. (2) Sources footer auto-appended to every explicit popup; suppress per popup with `show_provenance: false`. (3) Inline source line under `detail.sections[type=stats]` via `show_source: true`. Opt-out: `click_popup: false` / `row_click: false`.

**The PRISM rule**: every dataset backing a chart or table carries `field_provenance`. Validation only warns, but coverage is expected. When the upstream has no canonical symbol, declare it explicitly (`system: "computed"` + `recipe`, or `system: "csv"` + path) -- never drop silently.

### 4.4.2 In-cell visualisations (table column `in_cell`)

Per-column `in_cell` adds a visual encoding alongside the formatted text. Two kinds:

| `in_cell` value | Behavior |
|-----------------|----------|
| `"bar"`         | Horizontal bar inside the cell, width proportional to the value's position in the column's range. Values that cross zero anchor at column-center (positive grows right, negative grows left). Override colors via `bar_color_pos` / `bar_color_neg`. |
| `"sparkline"`   | Inline 80x16 SVG sparkline reading from a sibling dataset. Requires `from_dataset` (sibling dataset name) + `row_key` (column on this row used as the lookup key) + `filter_field` (column on the sibling dataset that matches `row_key`). Optional `value` (numeric column on the sibling dataset; defaults to `row_key`), `show_text: false` (hide the cell's number, keep only the line). |

```python
{"widget": "table", "id": "movers", "dataset_ref": "tickers",
  "columns": [
      {"field": "ticker", "label": "Ticker"},
      {"field": "ret",  "label": "1d ret",  "format": "signed:2",
        "in_cell": "bar"},
      {"field": "ytd",  "label": "YTD %",   "format": "signed:1",
        "in_cell": "bar"},
      {"field": "ticker", "label": "Spark (60d)",
        "in_cell": "sparkline",
        "from_dataset": "ticker_history",
        "row_key": "ticker",       # column on this table's row
        "filter_field": "ticker",  # column on `ticker_history` to match
        "value": "price",          # column on `ticker_history` to plot
        "show_text": False}
  ]}
```

The bar normalises against the **visible-row** range (after filter + search), so the encoding reflects what's actually on screen. Sparklines fall back to a flat dot when there are <2 numeric values for a row.

### 4.5 stat_grid widget

Dense grid of label / value stats -- for when a row of KPIs would take too much vertical space.

```json
{"widget": "stat_grid", "id": "summary", "w": 12,
  "title": "Risk summary",
  "info": "Rolling risk metrics aggregated across the full book.",
  "stats": [
    {"id": "s1", "label": "Beta to SPX", "value": "0.82",  "sub": "60D",
      "trend": 0.04,
      "info": "OLS beta of book P&L vs S&P 500 TR, trailing 60 biz days."},
    {"id": "s2", "label": "Duration", "value": "4.8y",  "sub": "DV01 $280k"},
    {"id": "s3", "label": "Gross leverage", "value": "2.3x",  "sub": "vs 3.0x cap",
      "trend": 0.1},
    {"id": "s4", "label": "HY OAS", "value": "285 bp", "sub": "z = -1.1",
      "trend": -0.05}
  ]}
```

**Per-stat fields:**

| Field | Purpose |
|-------|---------|
| `id` | Optional id for DOM addressing. |
| `label` | Title line (small caps, dim). |
| `value` | The stat itself. Pre-format; no number formatting applied. |
| `source` | Alternative to `value`: dotted `<dataset>.<agg>.<column>`. |
| `sub` | Smaller secondary caption below value. |
| `info` | Short help text. Info icon next to label; hover tooltip + click modal. Alias `description`. |
| `popup` | `{title, body}` markdown popup for click. |
| `trend` | Optional numeric delta. Positive = green up arrow, negative = red down arrow. |

### 4.5a Pivot / crosstab widget

A pivot widget reads from a long-form dataset and renders an interactive crosstab where the viewer picks the row dimension, column dimension, value column, and aggregator from author-supplied whitelists. Use for "show me sector x country breakdown of YTD perf, actually pivot it by sector x decile of beta, actually agg on median" -- three different tables become one widget where the viewer decides the layout.

```python
{"widget": "pivot", "id": "perf_pivot", "w": 12,
  "title": "Sector x window perf",
  "subtitle": "Drag the dropdowns to repivot.",
  "dataset_ref": "perf_long",
  "row_dim_columns": ["sector", "country", "ticker"],
  "col_dim_columns": ["window"],
  "value_columns":   ["ret", "ret_pct"],
  "agg_options":     ["mean", "median", "sum", "min", "max", "count"],
  "row_default": "sector", "col_default": "window",
  "value_default": "ret", "agg_default": "mean",
  "decimals": 2,
  "color_scale": "diverging",            # 'sequential' | 'diverging' | 'auto' | dict
  "show_totals": True}
```

| Key | Required | Purpose |
|-----|----------|---------|
| `dataset_ref` | yes | Long-form dataset (one row per (row_cat, col_cat, value) triple). |
| `row_dim_columns` | yes | Whitelist of columns the user can pick as the row dimension. |
| `col_dim_columns` | yes | Whitelist for the column dimension. |
| `value_columns` | yes | Whitelist of numeric columns to aggregate. |
| `agg_options` | no | Default `["mean", "sum", "median", "min", "max", "count"]`. |
| `row_default` / `col_default` / `value_default` / `agg_default` | no | Initial selections; defaults to the first item in each list / `"mean"`. |
| `decimals` | no | Cell formatting precision (default 2). |
| `color_scale` | no | `"sequential"` (single-direction blue ramp), `"diverging"` (red-white-blue around 0), `"auto"` (diverging when data crosses 0, else sequential), or `false` to disable. |
| `show_totals` | no | Append row/column totals (recomputed from the underlying values, not summed from the cells). Default `True`. |

Filters that target the pivot's `dataset_ref` flow through naturally -- the table recomputes against the filtered subset on every filter change. The user's last dropdown selections survive URL state encoding (`#p.<id>.r=...&p.<id>.c=...`).

### 4.6 Image / markdown / divider widgets

```json
{"widget": "image", "id": "logo", "w": 3,
  "src": "https://.../gs_logo.png",
  "alt": "Goldman Sachs",
  "link": "https://..."}

{"widget": "markdown", "id": "md", "w": 12,
  "content": "### Method\nSynthetic UST panel. **Brush** the curve to cross-filter.\n\n- Source: [GS Market Data](https://example.com)\n- Refresh: daily"}

{"widget": "divider", "id": "sep"}
```

### 4.7 Note widget (semantic callout)

Tinted card with colored left-edge stripe keyed by `kind`. Use when a paragraph is load-bearing -- the thesis, the risk, the watch level -- and you want the reader to find it without re-reading the whole page.

| Field | Required | Purpose |
|-------|----------|---------|
| `id` | yes | Widget id. |
| `body` | yes | Markdown body. Full grammar (4.8). |
| `kind` | no | One of `insight` / `thesis` / `watch` / `risk` / `context` / `fact`. Default `insight`. |
| `title` | no | Short title rendered next to the kind label. |
| `icon` | no | Optional 1-2 character glyph rendered to the left of the title. |
| `w` | no | Grid span 1..12. Default 12. |
| `footer` / `popup` / `info` | no | Standard widget knobs work here too. |

| Kind | Visual | Use for |
|------|--------|---------|
| `insight` | sky-blue stripe + sky tint (default) | Observation / "the lightbulb" |
| `thesis` | navy stripe + navy tint | The load-bearing claim of the dashboard |
| `watch` | amber stripe + amber tint | Levels / events to monitor |
| `risk` | red stripe + red tint | Downside / pain trades |
| `context` | grey stripe + grey tint | Background / setup info |
| `fact` | green stripe + green tint | Established / point-in-time facts |

```json
{"widget": "note", "id": "n_thesis", "w": 6,
  "kind": "thesis", "title": "Bull-steepener resumes",
  "body":
    "The curve is **bull-steepening** for the third session in a row.\n\n"
    "1. 2Y -6bp on the day, -18bp on the week\n"
    "2. 10Y -3bp on the day, -9bp on the week\n"
    "3. Spread widening primarily front-led, consistent with a *priced-in cut* trade"
}

{"widget": "note", "id": "n_watch", "w": 6,
  "kind": "watch", "title": "Levels to watch",
  "body":
    "| Level | Significance |\n"
    "|---|---|\n"
    "| 4.10% 10Y | 50dma; clean break opens 4.00% |\n"
    "| -50bp 2s10s | recession signal floor |\n"
}
```

Pairing a `thesis` and `watch` note in a 6/6 row at the top of a dashboard is a high-leverage pattern: reader gets the load-bearing claim and the "what would change my mind" criteria in one row, before any chart loads.

### 4.8 Markdown grammar (shared)

The same grammar applies to **every** prose-rendering surface in the dashboard:

* `widget: markdown` -- the dedicated freeform tile (transparent on page).
* `widget: note` -- the `body` field of every callout kind.
* `metadata.summary` -- the top-of-dashboard banner (2.3.2).
* `metadata.methodology` -- the header methodology popup (2.3.1).
* `popup: {body}` -- click-popup body on any tile / filter / stat.
* Per-row drill-down `markdown` sections (4.3, table widget).

The `subtitle` / `description` line on tabs is plain text, not markdown.

| Block | Syntax |
|-------|--------|
| Headings | `# H1` ... `##### H5` (h1-h5; deeper clamped to h5) |
| Paragraph | Lines separated by blank line; lines within a paragraph joined with single space |
| Unordered list | `-` or `*` at line start |
| Ordered list | `1.` / `2.` / ... at line start (numbers don't have to be sequential) |
| Nested list | Indent by **2 spaces** per level. Mix `ul` and `ol` freely; nested lists live inside parent `<li>` |
| Blockquote | `> ...` at line start; multi-line blocks accumulate |
| Code block | Triple-backtick fenced. Optional language tag: ```` ```python ```` |
| Table | GFM: header row, separator row `\| --- \| --- \|`, body rows. Alignment hints `:---` / `---:` / `:---:` |
| Horizontal rule | A line containing only `---`, `***`, or `___` |

| Inline | Syntax |
|--------|--------|
| Bold | `**bold**` |
| Italic | `*italic*` |
| Strike | `~~strike~~` |
| Inline code | `` `code` `` |
| Link | `[label](url)` (always opens in new tab) |

Anything that does not match is escaped as plain text -- including raw HTML.

---

## 5. Filters (9 types)

```json
{"id": "region", "type": "multiSelect", "default": ["US", "EU"],
  "options": ["US", "EU", "JP", "UK"],
  "targets": ["*"], "field": "region", "label": "Region"}
```

`options` can also be a list of `{value, label}` dicts when visible text differs from the underlying filter value:

```json
{"id": "mode", "type": "radio", "default": "sell",
  "options": [
    {"value": "sell", "label": "Looking to Sell (Feel Best to Buy)"},
    {"value": "buy",  "label": "Looking to Buy (Feel Best to Sell)"}
  ],
  "targets": ["screener"], "field": "mode", "label": "Mode"}
```

**Nine filter types:**

| Type | UI | Applies to |
|------|-----|-----------|
| `dateRange` | select of 1M/3M/6M/YTD/1Y/2Y/5Y/All | **Charts** (view-mode, default): sets initial `dataZoom` window. **Tables / KPIs / stat_grids**: filters `rows[field]` to range. Set `mode: "filter"` to row-filter charts too. |
| `select` | `<select>` | `rows[field] == value` |
| `multiSelect` | `<select multiple>` | `rows[field] in [values]` |
| `radio` | radio button group | same as `select`, different UI |
| `numberRange` | text `min,max` | `min <= rows[field] <= max` |
| `slider` | range input + value | `rows[field] op value` (op defaults `>=`) |
| `number` | number input | `rows[field] op value` (op defaults `>=`) |
| `text` | text input | `rows[field] op value` (op defaults `contains`) |
| `toggle` | checkbox | `rows[field]` truthy when checked |

**`dateRange` semantics on charts.** Time-series charts ship with their own `dataZoom` controls (mouse-wheel/pinch zoom + slider beneath the grid + drag-pan -- see 5.1), so users can zoom and pan every chart independently. A `dateRange` filter is a global "initial lookback" knob, not a data filter -- changing the dropdown moves every targeted chart's visible window via `dispatchAction({type:'dataZoom'})` and leaves the underlying dataset untouched. Tables / KPIs / stat_grids targeted by the same filter still see real row-filtering. Pass `"mode": "filter"` to force the legacy row-filter behavior on charts (e.g. histograms / aggregates that must recompute over the window).

**Fields:**

| Field | Purpose |
|-------|---------|
| `id` | Required; unique within manifest. |
| `type` | Required; one of the 9 above. |
| `default` | Initial value. |
| `field` | Dataset column to filter against. |
| `op` | Comparator: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`. |
| `transform` | `abs` / `neg` applied to cell before compare (e.g. `\|z\|` filters). |
| `options` | Required for `select`, `multiSelect`, `radio`. Two shapes: list of primitives OR list of `{value, label}` dicts. Anything else raises validation error. |
| `min`, `max`, `step` | Required for `slider`; optional for `number`. |
| `placeholder` | Placeholder text for `text` / `number`. |
| `all_value` | Sentinel for "no filter" (e.g. `"All"` / `"Any"`). |
| `targets` | List of widget ids to refresh. `"*"` = all data-bound widgets. Wildcards: `"prefix_*"`, `"*_suffix"`. |
| `label` | Display label. |
| `description` (aliases `help`, `info`) | Short help text. Info icon: hover tooltip + click modal. |
| `popup` | `{title, body}` markdown popup for click. |
| `scope` | `"global"` (top filter bar) or `"tab:<id>"` (inline in tab). Auto-inferred from targets. |

**Filter placement is auto-scoped.** Every filter goes in one of two places:
- **Global filter bar** (top of dashboard, below header) -- for filters spanning multiple tabs or using `"*"` wildcard.
- **Tab-inline filter bar** (flush inside the tab panel) -- for filters whose `targets` all resolve to a single tab.

Override placement with explicit `scope: "global"` or `scope: "tab:<tab_id>"`.

**Which chart types reshape on filter change.** Auto-wire happens only when chart_type + mapping is safe to re-shape client-side: `line` / `multi_line` / `bar` / `area` with simple wide-form mapping (no `color` long-form grouping, no `stack`, no `trendline`). Filtered tables, KPIs, stat_grids, and chart types with computed series data (histograms, bullets, candlesticks, heatmaps, scatter-with-trendline, radar, gauge, sankey, treemap, sunburst, funnel, parallel_coords, tree, graph, boxplot) keep rendering their baseline data.

### 5.0a Cascading filters (`depends_on` + `options_from`)

A filter can declare `depends_on: <upstream_filter_id>` and `options_from: {dataset, key, where?}`. When the upstream filter changes, the dependent filter rebuilds its options from the named dataset, optionally filtered by a `where` clause that substitutes upstream filter values via `${filter_id}` syntax.

```python
"filters": [
    {"id": "region", "type": "select", "label": "Region",
      "default": "NA",
      "options": ["NA", "EU", "AP"],
      "field": "region", "targets": ["country_view"]},
    {"id": "country", "type": "select", "label": "Country",
      "depends_on": "region",
      "options_from": {"dataset": "universe",
                         "key": "country",
                         "where": "region == ${region}"},
      "options": ["US"],                # initial seed; runtime rebuilds
      "field": "country", "targets": ["country_view"]},
    {"id": "ticker", "type": "select", "label": "Ticker",
      "depends_on": "country",
      "options_from": {"dataset": "universe",
                         "key": "ticker",
                         "where": "country == ${country}"},
      "options": [""],
      "field": "ticker", "targets": ["country_view"]},
]
```

Supported `where` ops: `==`, `!=`, `>`, `>=`, `<`, `<=`. The dependent filter's existing value is preserved when it remains valid in the new option set; otherwise it falls back to the first new option (or empty for `multiSelect`). Cascades chain (region -> country -> ticker) -- when region changes, both country and ticker rebuild in dependency order.

Validation: `depends_on` must reference a declared filter id; self-dependency raises an error.

### 5.1 Per-chart zoom (in-chart `dataZoom`)

Every chart whose x-axis resolves to `time` ships with two `dataZoom` controls injected at compile time, independent of any `dateRange` filter:

- **`type: "inside"`** -- mouse wheel / pinch zoom + click-and-drag pan directly on the plot area
- **`type: "slider"`** -- a draggable slider beneath the grid with handles for fine-grained range control

The full dataset is always embedded; the slider clips the visible window. `grid.bottom` auto-bumps to make room for the slider so existing charts don't need layout changes.

Opt-out for sparkline-style tiles where the slider would dominate:

```json
{"widget": "chart", "id": "tiny_sparkline", "w": 3,
  "spec": {"chart_type": "line", "dataset": "rates",
            "mapping": {"x": "date", "y": "us_2y"},
            "chart_zoom": false}}
```

`chart_zoom: false` on `spec` (or `mapping`) suppresses the auto-injection. Builders that already declared their own `dataZoom` (e.g. `candlestick`) are left alone.

### 5.2 `click_emit_filter` -- chart click drives a filter

Turn a data-point click on one chart into a filter change that re-renders downstream widgets. Two shapes:

```json
"click_emit_filter": "sector_filter"

"click_emit_filter": {
    "filter_id": "sector_filter",
    "value_from": "name",     // "name" (default) | "value" | "seriesName"
    "toggle": true              // re-clicking same value clears (default true)
}
```

`filter_id` must reference a `select` or `radio` filter whose `targets` point at the widgets that should re-render. Useful for click-through navigation: click a sector slice on a donut to filter a screener table to that sector.

---

## 6. Links (connect + brush)

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

| Field | Purpose |
|-------|---------|
| `id` | Required. Stable slug used in DOM ids and localStorage keys. |
| `label` | Visible tab text. |
| `description` | (1) Italic secondary text rendered below tab bar when active, (2) a hover tooltip on the tab button itself. |
| `rows` | List-of-lists of widgets. |

---

## 8. Header actions (custom buttons / links)

Optional `manifest.header_actions[]` appends custom buttons/links to the header (left of the standard top-right protocol). Use for dashboard-specific escape hatches.

| Key | Purpose |
|-----|---------|
| `label` | Required. Display text. |
| `href` | If set, renders an `<a>` (opens in new tab by default). |
| `onclick` | Name of a global JS function to wire as click handler. One of `href` / `onclick` is required. |
| `target` | `"_self"` to open inline (defaults to `_blank`). |
| `id` | Optional DOM id. |
| `primary` | `True` -> GS Navy primary button styling. |
| `icon` | Optional leading glyph. |
| `title` | Hover tooltip text. |

---

## 9. Tooltips, info icons, and popups

Two classes of help UI:
1. **Hover tooltips** -- short text via browser's native `title=` attribute. 1-2 word clarifications.
2. **Click popups** -- centered modal with title, markdown body, X / ESC / overlay-click to close. Paragraph-length explanations.

Every info icon does BOTH: hover shows short text, clicking opens the same content in a modal. Set `popup: {title, body}` on the same widget / filter / stat to give the modal richer markdown content while keeping `info` as the hover line.

| Surface | Field | Appears as |
|---------|-------|-----------|
| Any widget header | `info`, `popup: {title, body}`, `subtitle`, `footer`/`footnote` | info icon (hover tooltip + click modal); italic sub-line; small text below body |
| Table column header / cell | `columns[i].tooltip` | header + cell `title=` attribute |
| Table row | `row_highlight` rules | tinted row + left-edge accent stripe |
| Table row click | `row_click` (simple `popup_fields` OR rich `detail.sections[]`) | modal: key/value or drill-down |
| stat_grid cell | `stats[i].info`, `stats[i].popup` | info icon next to label |
| Filter control | `description` / `help` / `info`, `popup` | info icon next to filter label |
| Tab button | `tabs[i].description` | hover tooltip + italic sub-line |
| Header action / chart action button | `.title` | native browser tooltip |
| Chart tooltip (hover) | `spec.tooltip = {...}` | ECharts tooltip with custom formatter |
| Chart annotation | `annotations[i].label` | permanent label on annotation |
| Chart data-point click | `click_popup` (simple OR `detail.sections[]`) | modal: key/value or drill-down |
| Click / row auto-default | dataset has `field_provenance`, no explicit popup | minimal modal with mapped fields + Sources footer. Suppress with `click_popup: false` / `row_click: false`. See 4.4.1. |
| Sources footer (every popup) | `field_provenance` auto-appended | trailing "Sources" table (symbol / system / source). Suppress per popup with `show_provenance: false`. |

**Modal behavior**: X button, ESC, overlay click. Only one modal visible at a time.

Markdown in popups uses the shared grammar (4.8). Use sparingly. A dashboard with an info icon on every control is louder than one without.

---

## 10. Runtime features (free for every compiled dashboard)

Rendered automatically -- Prism doesn't configure anything extra.

| Feature | Trigger |
|---------|---------|
| Data freshness badge | `metadata.data_as_of` (or `generated_at`) |
| Methodology popup | `metadata.methodology` |
| Refresh button | `metadata.kerberos` + `dashboard_id`, `refresh_enabled != False`. POSTs to `/api/dashboard/refresh/`, polls every 3s up to 3 min, reloads on success |
| Download Charts | always; one 2x PNG per chart, titles/subtitles baked in |
| Download Panel | always; full view as single 2x PNG via `html2canvas@1.4.1` (CDN, lazy-loaded). Filename `<id>_YYYY-MM-DD-HH-MM-SS.png` |
| Download Excel | dashboard has any `widget: table`; one sheet per table (title truncated to 31 chars), reflects current filter/search/sort state |
| Per-tile controls drawer | every chart / table / KPI -- see 10.1 |
| Per-tile PNG | each chart tile toolbar; baked-in title + subtitle |
| Per-tile fullscreen | each chart tile toolbar; toggles to full viewport |
| Per-tile XLSX | each table widget toolbar; hide with `downloadable: False` |
| Per-chart `dataZoom` (inside + slider) | every time-axis chart; suppress with `chart_zoom: false`. See 5.1 |
| Tab persistence | last-active tab restored via `localStorage` per dashboard id |
| Filter reset | filter bar Reset button |
| Brush cross-filter | drag-select in one linked chart filters all members |
| Chart sync (connect) | tooltips / axes / legend / dataZoom synchronised across `sync` group |
| Row-click / chart-click modal | `row_click` / `click_popup` configured. Auto-fires minimal popup if `field_provenance` exists but no popup declared. Suppress with `*: false`. See 4.4.1 |
| Click-emit-filter | data-point click drives filter change. See 5.2 |
| Sources footer (every popup) | auto-appended from `field_provenance`. Suppress per popup with `show_provenance: false` |
| Table search / sort | when `searchable` / `sortable: true` |
| Conditional / color-scale cells | per column spec |
| In-cell bars / sparklines | `columns[i].in_cell` (`bar` or `sparkline`); see 4.4.2 |
| Row-level highlighting | `row_highlight` rules (per-row tinted background + accent stripe) |
| KPI sparklines | when `sparkline_source` is set |
| Auto stat strip | Sigma button in the toolbar of every line / multi_line / area chart; click to open a popup with current value, deltas, range, percentile -- one row per visible series. Units pulled from `field_provenance`; see 4.1.3. Suppress with `stat_strip: false`. |
| URL state (shareable views) | active tab + filters + chart-drawer state + table sort/search + KPI compare period + pivot dropdowns serialise to the URL hash on every change; restored on load. Send the URL, the recipient sees the same view. |
| Conditional widget visibility | `show_when` clause -- compile-time data conditions remove widgets entirely; runtime filter conditions toggle CSS display. See 4.1.1 |
| Cascading filters | `depends_on` + `options_from` rebuild downstream options on upstream change. See 5.0a |
| Pivot dropdowns | row/col/value/agg dropdowns wired automatically for every `widget: pivot`. See 4.5a |
| Responsive layout | tiles collapse to 6 cols < 1024 px, 12 cols < 720 px |

### 10.1 Per-tile controls drawer (`⋮`)

Every chart / table / KPI tile carries a `⋮` button. Drawer populates lazily on first open with only the knobs the underlying widget supports.

**Chart drawer.** Per-series + chart-level + universal action knobs:

| Section          | Knobs                                                                                                |
|------------------|------------------------------------------------------------------------------------------------------|
| Series           | per-series `transform` + show/hide checkbox (line / multi_line / area, wide-form). Long-form (`mapping.color`) gets a single chart-wide transform instead. |
| Shape            | `Style` (solid / dotted / dashed) + `Step` (off/start/middle/end) + `Width` (1/2/3 px) + `Area fill` + `Stack` (group / stack / 100% stacked, auto-rescales each x to a percent) + `Markers`. Mirrors Haver's chart-type strip but composable -- each axis is its own dropdown. |
| Chart            | `Smoothing` (off / 5 / 20 / 50 / 200) + `Y-scale` (linear / log) + `Y-range` (auto / from-zero). |
| Bar / Bar_horizontal | `Sort` (input order / value desc / value asc / alphabetical) + `Stack` (grouped / stacked / 100% stacked, auto-rescales values, formats axis as %). |
| Scatter / Scatter_multi | `Trendline` (off / linear OLS, fitted client-side from `series.data`) + `X-scale` (linear / log). |
| Scatter_studio  | `X / Y / color / size column` dropdowns (populated from author's `x_columns` / `y_columns` / `color_columns` / `size_columns` whitelists) + per-axis transform (raw / log / Δ / %Δ / YoY % / z-score / rolling z (Nd) / pct rank) + `Window` (`All` / `252d` / `504d` / `5y`) + `Outliers` (`Off` / `IQR x 3` / `\|z\|>4`) + `Regression` (`Off` / `OLS` / `OLS per color`). |
| Heatmap / correlation_matrix | `Color scale` (sequential / diverging-around-zero, GS palette) + `Labels` toggle + `Auto-contrast` toggle (black/white text per cell from background luminance via `label.rich`). Override defaults via mapping `colors` / `color_palette` / `color_scale`. |
| Pie / Donut     | `Sort` (input order / largest first) + `"Other" bucket` (group slices below 1% / 3% / 5% as "Other"). |
| Calendar_heatmap | `Labels` toggle (default off because cells are tiny). |
| Actions row 1    | `View data` (modal, truncates at 1,000 rows; full set in Copy CSV) / `Copy CSV` (clipboard, full filtered dataset) / `Reset chart` (back to compile-time defaults). |
| Actions row 2    | `Download PNG` (2x, title baked in via the per-tile PNG path) / `Download CSV` / `Download XLSX` (uses SheetJS bundle already loaded for dashboard-level Excel export). |

When every visible series shares the same transform, the y-axis name auto-tags (e.g. ` (YoY %)`). Each transformed series' legend entry gets a `· Δ` / `· z` suffix so units stay unambiguous after the change.

**Time-series transforms** (computed entirely client-side, no PRISM round-trip):

| Group     | Transform                | Notes |
|-----------|--------------------------|-------|
| Basic     | `raw`, `change` (`Δ`), `pct_change` (`%Δ`), `log_change` | period over period |
| Basic     | `yoy_change` (`YoY Δ`), `yoy_pct` (`YoY %`), `yoy_log`   | look up `t - 365d` via binary search |
| Basic     | `annualized_change`      | `Δ × f`; `f` auto-detected from median timestamp gap (≈daily → 252, weekly → 52, monthly → 12, quarterly → 4, semi → 2, annual → 1) |
| Advanced  | `log`                    | `ln(v[i])` for `v[i] > 0`; non-positive points drop |
| Advanced  | `zscore`                 | `(v[i] - mean) / std` over the visible window |
| Advanced  | `rolling_zscore_252`     | 252-day rolling z; `min_periods=2`. Pattern `rolling_zscore_<N>` for arbitrary windows. |
| Advanced  | `rank_pct`               | Percentile rank (0..100), ties → average rank |
| Advanced  | `ytd`                    | `v[i] - v[anchor]` where anchor = first non-null point of the same calendar year |
| Advanced  | `index100`               | `v[i] / anchor * 100` where anchor = first non-zero non-null point |

When every visible series shares the same transform, the y-axis name auto-tags (e.g. ` (YoY %)`); each transformed series' legend entry gets a `· Δ` / `· z` suffix so units stay unambiguous.

**Table drawer.** Search input + sort-by-column + asc/desc dropdown + per-column visibility checkboxes + density (regular / compact) + freeze-first-col toggle + decimals override (auto / 0..4, splices into every numeric column's format string at render time). Action bar: `View raw`, `Copy CSV`, `Download CSV`, `Download XLSX`, `Reset table`. Suppress with `table_controls: false`.

**KPI drawer.** Compare-period dropdown (auto / prev / 1d / 5d / 1w / 1m / 3m / 6m / 1y / YTD; only shown when `sparkline_source` is set, recomputes the displayed delta on the fly), sparkline visibility toggle, delta visibility toggle, decimals override. Actions: `View data`, `Copy CSV`, `Download CSV`, `Download XLSX`, `Reset KPI`. Suppress with `kpi_controls: false`.

**Suppressing the drawer per widget:**

```python
{"widget": "chart", "id": "kpi_spark", "w": 3,
  "spec": {"chart_type": "line", "dataset": "rates",
            "mapping": {"x": "date", "y": "us_2y"},
            "chart_zoom": False, "chart_controls": False}}
{"widget": "table", "id": "fixed_summary", "w": 6, "table_controls": False, ...}
{"widget": "kpi",   "id": "fed_funds",     "w": 3, "kpi_controls": False, ...}
```

Drawer state is exposed for inspection / scripting:

```js
window.DASHBOARD.chartControlState['curve'].series['us_10y'].transform = 'rolling_zscore_252';
window.DASHBOARD.chartControlState['curve'].shape = {lineStyleType: 'dashed', step: 'middle'};
window.DASHBOARD.tableState['screener'].hidden = {2: true};      // hide column 2
window.DASHBOARD.kpiState['fed_funds'].comparePeriod = '1m';
```

---

## 11. Validation + diagnostics

### 11.1 `validate_manifest`

```python
ok, errs = validate_manifest(manifest)
```

Rules:
- `schema_version` must equal `1`
- `id`, `title` must be present
- `theme`, `palette` must be registered names
- Each dataset entry must be `{"source": [...]}` (DataFrames are normalized first). Optional `field_provenance` (dict of dicts), `row_provenance_field` (string), `row_provenance` (dict of dicts of dicts) are validated for shape only -- inner provenance keys are free-form.
- Filter `id` must be unique; `type` must be in valid set
- `select` / `multiSelect` / `radio` require `options`
- `slider` requires `min`, `max`
- `slider`, `number`, `text` require `field`
- Each widget `id` must be unique; widths must sum to at most `cols`
- Widget-specific required fields enforced (chart needs spec/ref/option, kpi needs label, table needs ref/dataset_ref, stat_grid needs stats[], image needs src/url, markdown needs content, note needs body + valid kind)
- Chart `spec` requires `chart_type` (in 26-type set), `dataset` (must reference declared dataset), `mapping` dict
- Chart `click_popup`, when present, must be a dict (mirroring table `row_click` shape) OR boolean `false` to suppress the auto-default provenance popup. Same rule for table `row_click`.
- Filter `targets` must match real chart widget ids (wildcards OK)
- Link members must match real chart widget ids
- `sync` values must be in `{axis, tooltip, legend, dataZoom}`
- `brush.type` must be in `{rect, polygon, lineX, lineY}`
- `metadata.refresh_frequency` must be in `{hourly, daily, weekly, manual}`

Returns `(ok, [errors...])`. Each error is a human-readable string identifying the offending path.

### 11.2 `chart_data_diagnostics` (the second-pass lint)

`validate_manifest` checks structure. **`chart_data_diagnostics(manifest)` checks the data actually wires up** -- empty datasets, missing columns, all-NaN series, non-numeric values, missing mapping keys, filter fields that don't exist, dataset shape, size budgets.

```python
diags = chart_data_diagnostics(manifest)
for d in diags:
    print(d.severity, d.code, d.widget_id, d.message)

r = compile_dashboard(manifest)                 # default: strict=True, raises on error diags
r = compile_dashboard(manifest, strict=False)   # keep going so PRISM can fix all in one round-trip
for d in r.diagnostics:
    print(d.to_dict())
```

**Strict mode** (`compile_dashboard(strict=True)`, the default) raises `ValueError` listing every error-severity diagnostic. `strict=False` keeps going so Prism can fix all findings in one round-trip; refresh pipelines and CI inherit the strict default. Warnings + info never trigger strict-mode failure. Contract: a broken headline number is a broken dashboard.

`Diagnostic` is a dataclass with `severity` (`error` / `warning` / `info`), stable `code`, `widget_id`, dotted manifest `path`, `message`, and a `context` dict carrying actionable repair data.

**Actionable repair context.** Most codes carry two Prism-friendly keys:
* `did_you_mean` -- close-match suggestions for typo'd column / dataset names. Fires for `chart_mapping_column_missing`, `table_column_field_missing`, `kpi_source_column_missing`, `kpi_source_dataset_unknown`, `filter_field_missing_in_target`.
* `fix_hint` -- one-sentence repair instruction. Surfaced as indented `-> fix:` line.

**Stable diagnostic codes** -- pattern-match on `code` for automated repair:

| Code | Severity | Fires when |
|------|----------|------------|
| `chart_dataset_empty` | error | Chart's dataset has 0 rows |
| `chart_dataset_single_row` | warning | Series chart has only 1 row |
| `chart_mapping_required_missing` | error | chart_type's required mapping key is absent (e.g. pie needs `category`+`value`) |
| `chart_mapping_column_missing` | error | mapping references column not in dataset; carries `did_you_mean` |
| `chart_mapping_column_all_nan` | error | mapping column exists but every value is NaN/None |
| `chart_mapping_column_mostly_nan` | warning | mapping column is >=50% NaN |
| `chart_mapping_column_non_numeric` | error | mapping key requires numeric (y/value/size/weight/low/high/open/close) but column isn't numeric-coercible |
| `chart_constant_values` | warning | numeric y column has single unique value across all rows; renders as flat line |
| `chart_negative_values_in_portion` | error | pie/donut/funnel/sunburst/treemap value column contains negative values |
| `chart_sankey_self_loops` | error/warn | sankey edges where source==target |
| `chart_sankey_disconnected` | warning | source/target sets share no nodes |
| `chart_candlestick_inverted` | error | OHLC inversions detected (high<low, open>high, etc.) |
| `chart_tree_orphan_parents` | error | `mapping.parent` values that don't appear in `mapping.name` |
| `chart_build_failed` | error | builder raised at compile time; `context.exception_type` carries the cause |
| `table_dataset_empty` | warning | table's `dataset_ref` has 0 rows |
| `table_column_field_missing` | error | `columns[].field` is not in the dataset; carries `did_you_mean` |
| `table_columns_all_missing` | error | EVERY defined column is missing from the dataset |
| `kpi_no_value_no_source` | error | KPI tile has neither `value` nor `source`; runtime would render `--` |
| `kpi_value_is_placeholder` | error | `value` is a placeholder string (`--`, `n/a`, etc.) -- ship a real value or bind a source |
| `kpi_source_malformed` | error | `source` / `delta_source` is not in `dataset.aggregator.column` form (3 parts) or `sparkline_source` is not `dataset.column` (2 parts) |
| `kpi_source_dataset_unknown` | error | KPI source references undeclared dataset; carries `did_you_mean` |
| `kpi_source_aggregator_unknown` | error | aggregator segment isn't in the runtime allow-list (`latest`/`first`/`sum`/`mean`/`min`/`max`/`count`/`prev`); carries `did_you_mean` |
| `kpi_source_column_missing` | error | KPI source column is not in its dataset; carries `did_you_mean` |
| `kpi_source_no_numeric_values` | error | KPI source column has zero numeric values (all-string OR all-NaN); JS resolver returns null and the tile shows `--` |
| `kpi_sparkline_too_short` | warning | `sparkline_source` has <2 numeric values |
| `stat_grid_no_value_no_source` | error | stat_grid cell has neither `value` nor `source`; cell would render `--` |
| `stat_grid_value_is_placeholder` | error | stat_grid `value` is a placeholder string |
| `stat_grid_source_unresolvable` | error | stat_grid `source` cannot be resolved at compile time (stat_grid is server-rendered, no JS resolution) |
| `filter_field_missing_in_target` | error | filter `field` is not a column in any of target widgets' datasets |
| `filter_default_not_in_options` | warning | `default` is not in `options` for select/multiSelect/radio |
| `filter_targets_no_match` | warning | every non-wildcard `targets` pattern resolves to no widget id |
| `dataset_dti_no_date_column` | error | dataset DataFrame has `DatetimeIndex` and no `date` column AND a chart/filter on this dataset references `date`. Fires when Prism forgets `df.reset_index()` |
| `dataset_passed_as_tuple` | error | dataset is a Python tuple instead of DataFrame -- catches the `pull_market_data` "didn't unpack `(eod_df, intraday_df)`" mistake |
| `dataset_columns_multiindex` | error | DataFrame columns is a `pd.MultiIndex`; compiler does not auto-flatten |
| `dataset_column_looks_like_code` | warning | column name matches opaque-code pattern (Haver `X@Y`, coordinates `IR_USD_*`, whitespace, slashes); rename to plain English |
| `dataset_metadata_attrs_unused` | info | DataFrame has `df.attrs['metadata']` AND its columns still match the raw codes inside that metadata; suggests building a rename map from attrs |
| `dataset_rows_{warning,error}` | warn / error | dataset has >= 10K (warn) / 50K (error) rows |
| `dataset_bytes_{warning,error}` | warn / error | dataset serialises to >= 1 MB / 2 MB |
| `manifest_bytes_{warning,error}` | warn / error | total bytes across `manifest.datasets` >= 3 MB / 5 MB |
| `table_rows_{warning,error}` | warn / error | table-widget dataset has >= 1K / 5K rows |

Both `compile_dashboard` and the renderer are **resilient by design**: a chart that fails to build (missing column, malformed mapping, builder raise) gets a `(no data)` placeholder option and a `chart_build_failed` diagnostic. The dashboard still renders, sibling charts still work, and Prism gets the full failure list in one round-trip.

---

## 12. Persistence + the refresh pipeline

NON-NEGOTIABLE: every user-requested dashboard persists to `users/{kerberos}/dashboards/{name}/`. A dashboard living only in `SESSION_PATH` won't refresh, won't appear in the user's list, and is lost when the conversation ends.

### 12.1 Three-tool-call build model

```
Tool call 1: pull_data.py     Pulls DataFrames, saves raw data to S3
Tool call 2: build.py         Loads data, populates manifest template, compiles
Tool call 3: register         Updates registry + user manifest
```

Each call uses the `script` parameter of `execute_analysis_script` to BOTH execute logic in the current session AND persist that same logic to S3 for the refresh pipeline. The persisted script is identical to the one that just ran -- write it once, exec + upload.

#### Tool Call 1: `pull_data.py`

```python
import io
from datetime import datetime

KERBEROS = 'userid'
DASHBOARD_NAME = 'rates_monitor'
DASHBOARD_PATH = f'users/{KERBEROS}/dashboards/{DASHBOARD_NAME}'

PULL_DATA_PY = '''"""pull_data.py"""
import io
DASHBOARD_PATH = "users/userid/dashboards/rates_monitor"

eod_df, _ = pull_market_data(
    coordinates=["IR_USD_Swap_2Y_Rate", "IR_USD_Swap_10Y_Rate"],
    start_date="2020-01-01", name="rates_eod",
)

buf = io.StringIO(); eod_df.to_csv(buf)
s3_manager.put(buf.getvalue().encode(), f"{DASHBOARD_PATH}/data/rates_eod.csv")
print(f"[pull_data.py] EOD shape: {eod_df.shape}")
'''

exec(PULL_DATA_PY)
s3_manager.put(PULL_DATA_PY.encode(), f'{DASHBOARD_PATH}/scripts/pull_data.py')
```

#### Tool Call 2: `build.py`

The first build is one-shot: compose the full manifest with DataFrames, derive a template from it (strips data, keeps structure), compile + upload. From that point on, the persisted `build.py` only needs `populate_template(template, fresh_dfs)` -- the structural manifest never has to be rewritten.

```python
import json, io, sys
from datetime import datetime, timezone
import pandas as pd
sys.path.insert(0, '/ai_development/dashboards')
from echart_dashboard import compile_dashboard, manifest_template

KERBEROS = 'userid'
DASHBOARD_NAME = 'rates_monitor'
DASHBOARD_PATH = f'users/{KERBEROS}/dashboards/{DASHBOARD_NAME}'

df = pd.read_csv(io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                 index_col=0, parse_dates=True)

manifest = {
    "schema_version": 1, "id": DASHBOARD_NAME, "title": "Rates Monitor",
    "theme": "gs_clean",
    "metadata": {
        "kerberos": KERBEROS, "dashboard_id": DASHBOARD_NAME,
        "data_as_of": str(df.index.max().date()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": ["GS Market Data"], "refresh_frequency": "daily",
        "refresh_enabled": True, "tags": ["rates"],
    },
    "datasets": {"rates": df.reset_index()},
    "layout": {"rows": [
        [{"widget": "chart", "id": "curve", "w": 12, "h_px": 380, "title": "UST Curve",
          "spec": {"chart_type": "multi_line", "dataset": "rates",
                    "mapping": {"x": "date",
                                 "y": ["IR_USD_Swap_2Y_Rate", "IR_USD_Swap_10Y_Rate"],
                                 "y_title": "Rate (%)"}}}]
    ]},
}

tpl = manifest_template(manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(), f'{DASHBOARD_PATH}/manifest_template.json')

r = compile_dashboard(manifest, write_html=False, write_json=False, strict=True)
if not r.success:
    raise ValueError(f"COMPILE FAILED: {r.error_message} | WARNINGS: {r.warnings}")
s3_manager.put(r.html.encode('utf-8'), f'{DASHBOARD_PATH}/dashboard.html')
s3_manager.put(json.dumps(manifest, indent=2).encode('utf-8'), f'{DASHBOARD_PATH}/manifest.json')

BUILD_PY = '''"""build.py -- refresh-pipeline build script (~15 lines)"""
import json, io, sys
from datetime import datetime, timezone
import pandas as pd
sys.path.insert(0, "/ai_development/dashboards")
from echart_dashboard import compile_dashboard, populate_template

DASHBOARD_PATH = "users/userid/dashboards/rates_monitor"

df = pd.read_csv(io.BytesIO(s3_manager.get(f"{DASHBOARD_PATH}/data/rates_eod.csv")),
                 index_col=0, parse_dates=True)
template = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json"))
m = populate_template(template, {"rates": df.reset_index()}, metadata={
    "data_as_of": str(df.index.max().date()),
    "generated_at": datetime.now(timezone.utc).isoformat(),
})
r = compile_dashboard(m, write_html=False, write_json=False, strict=True)
assert r.success, r.error_message
s3_manager.put(r.html.encode("utf-8"), f"{DASHBOARD_PATH}/dashboard.html")
s3_manager.put(json.dumps(m, indent=2).encode("utf-8"), f"{DASHBOARD_PATH}/manifest.json")
'''
s3_manager.put(BUILD_PY.encode(), f'{DASHBOARD_PATH}/scripts/build.py')
```

#### Tool Call 3: Register dashboard

```python
import json
from datetime import datetime, timezone

KERBEROS = 'userid'
DASHBOARD_NAME = 'rates_monitor'
DASHBOARD_PATH = f'users/{KERBEROS}/dashboards/{DASHBOARD_NAME}'
REGISTRY_PATH = f'users/{KERBEROS}/dashboards/dashboards_registry.json'

# Pipeline manifest (lists scripts for refresh job)
pipeline_manifest = {
    "schema_version": "1.0",
    "dashboard_id": DASHBOARD_NAME,
    "scripts": [
        {"name": "pull_data.py", "path": f'{DASHBOARD_PATH}/scripts/pull_data.py',
          "order": 1, "description": "Data acquisition"},
        {"name": "build.py", "path": f'{DASHBOARD_PATH}/scripts/build.py',
          "order": 2, "description": "Transform + compile",
          "depends_on": ["pull_data.py"]}
    ],
    "created_at": datetime.now(timezone.utc).isoformat(),
}
s3_manager.put(pipeline_manifest, f'{DASHBOARD_PATH}/manifest.json')

# Update registry
try:
    registry = json.loads(s3_manager.get(REGISTRY_PATH).rstrip(b'\x00').decode('utf-8'))
except Exception:
    registry = {"schema_version": "1.0", "owner_kerberos": KERBEROS,
                 "dashboards": [], "last_updated": None}

existing_idx = next((i for i, d in enumerate(registry['dashboards'])
                       if d['id'] == DASHBOARD_NAME), None)

entry = {
    "id": DASHBOARD_NAME, "name": "Rates Monitor",
    "description": "Daily snapshot of key rates",
    "created_at": datetime.now(timezone.utc).isoformat() if existing_idx is None
                    else registry['dashboards'][existing_idx].get('created_at'),
    "last_refreshed": datetime.now(timezone.utc).isoformat(),
    "last_refresh_status": "success",
    "refresh_enabled": True, "refresh_frequency": "daily",
    "folder": f'{DASHBOARD_PATH}/',
    "html_path": f'{DASHBOARD_PATH}/dashboard.html',
    "data_path": f'{DASHBOARD_PATH}/manifest.json',
    "tags": ["rates"], "keep_history": False, "history_retention_days": 30
}

if existing_idx is not None:
    registry['dashboards'][existing_idx] = entry
else:
    registry['dashboards'].append(entry)

registry['last_updated'] = datetime.now(timezone.utc).isoformat()
s3_manager.put(registry, REGISTRY_PATH)
update_user_manifest(KERBEROS, artifact_type='dashboard')

links = generate_download_links(f'{DASHBOARD_PATH}/dashboard.html')
if links and links[0].get('success'):
    print(f"Download: {links[0]['presigned_url']}")

# ALWAYS print the hosted portal link too -- it's the persistent, auto-refreshing URL
portal_url = f'http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{DASHBOARD_NAME}/'
print(f"Portal (live, auto-refreshing): {portal_url}")
```

### 12.2 Templates: `manifest_template` + `populate_template`

```python
from echart_dashboard import manifest_template, populate_template

# One-time: strip data rows, keep column headers + every other config
tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(),
                f'{DASHBOARD_PATH}/manifest_template.json')

# Each refresh: fresh DataFrames get wired into the template slots
m = populate_template(tpl, {"rates": eod_df, "cpi": cpi_df},
                         metadata={"data_as_of": "..."},
                         require_all_slots=True)
compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html')
```

The template is pure JSON (no pandas); safe to persist and diff. `require_all_slots=True` raises `KeyError` if the template declares a dataset slot but no DataFrame was provided.

### 12.3 Refresh flow end-to-end

```
   BROWSER                    DJANGO BACKEND              REFRESH PIPELINE
  (dashboard.html)            (news/views.py)            (refresh_dashboards.py)

  user clicks [Refresh]
        |
        | rendering JS reads MANIFEST.metadata
        | -> guards on kerberos + dashboard_id + refresh_enabled
        | -> if file:// protocol, alert("offline") and return
        v
   POST /api/dashboard/refresh/
   {kerberos, dashboard_id}
        ----------------------->
                                lookup in dashboards_registry.json
                                spawn refresh subprocess (or rejoin running)
                                HTTP 200 {status:"refreshing"}
        <-----------------------
                                refresh_single_user_dashboard()
                                  +-> write refresh_status.json {running, started_at, pid}
                                  +-> RUN scripts/pull_data.py -> writes ../data/*.csv
                                  +-> RUN scripts/build.py -> writes dashboard.html + manifest.json
                                  +-> (optional) snapshot to history/
                                  +-> update dashboards_registry.json
                                  +-> write refresh_status.json {success, completed_at}

        meanwhile, every 3s for up to 3 min:
   GET /api/dashboard/refresh/status/?dashboard_id=...
        ----------------------->
                                read refresh_status.json
                                HTTP 200 {status, errors[], ...}
        <-----------------------

        when status==="success": location.reload()
```

API endpoint behavior:
- Offline (`file://`) -> alert explaining user needs the portal.
- HTTP 409 (already running) -> switch to polling status endpoint.
- `status == "success"` -> reload after ~1 s.
- `status == "error"` -> show error, restore button after 3 s.
- `status == "partial"` -> reload after 2 s to show whatever was produced.

`metadata.api_url` / `metadata.status_url` override default endpoints.

### 12.4 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_data.py` that fetches intraday MUST wrap it in `try/except` with EOD fallback. Every `build.py` must handle missing intraday file defensively.

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

current = (iday_df.ffill().iloc[-1]
           if iday_df is not None and len(iday_df) > 0
           else eod_df.iloc[-1])
```

Print informative log lines (`[pull_data.py] Starting at <ts>`, `EOD shape: ...`, `Intraday: available | NOT AVAILABLE (normal overnight)`).

### 12.5 Troubleshooting ("my dashboard is not working")

Diagnose, don't rebuild. Protocol:

1. **Registry** (`dashboards_registry.json`) -- confirm `refresh_enabled`, inspect `last_refresh_status` / `last_refreshed`.
2. **refresh_status.json** -- check `status`, `errors[]`, `pid`. `status="running"` with `started_at` > 10 min old = stale lock.
3. **Artifacts** -- confirm `dashboard.html`, `manifest.json`, `manifest_template.json`, `scripts/pull_data.py`, `scripts/build.py` all exist on S3.
4. **Fix the failing script** -- read, patch, re-upload. Test via `execute_analysis_script(script_path=...)` in order.
5. **Update registry + deliver** -- set `last_refresh_status="success"`, regenerate download link, explain transparently what was wrong.

Error patterns -> root cause -> fix:

| Symptom | Cause | Fix |
|---------|-------|-----|
| "No data successfully fetched" | Intraday unavailable (overnight / weekend) | Wrap intraday in try/except, fall back to EOD |
| `KeyError: '<col>'` | Schema drift | Check `col in df.columns` before access |
| Empty DataFrame after merge | Inner join dropped rows | Use outer join, handle NaNs explicitly |
| `IndexError: .iloc[-1]` | Empty frame | Guard with `len(df) > 0` |
| `ZeroDivisionError` | Analytics edge case | Add epsilon / zero-check |
| Connection / Timeout | Transient network | Manual refresh; check source availability |
| "Auto-healed stale lock" | Previous refresh hung | Self-resolves; investigate slow pulls |
| `FileNotFoundError` on script path | Scripts missing on S3 | Rebuild scripts |
| Empty DataFrame / no data | Codes invalid | Verify `pull_data.py` codes still valid |
| Chart shows "(no data)" placeholder | One chart spec failed to bind | Read `compile_dashboard().diagnostics` |
| Several blank tiles after refresh | Schema drift, missing cols, all-NaN | Diagnostics surface every binding failure |

Stale lock cleanup (when refresh API hasn't auto-healed):

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

---

## 13. Critical sandbox patterns

In the sandbox, `compile_dashboard` writes to local FS if `output_path` is given -- which doesn't work. Always pass `write_html=False, write_json=False` and `s3_manager.put()` manually. Always import via `sys.path.insert(0, '/ai_development/dashboards')`.

```python
import sys
sys.path.insert(0, '/ai_development/dashboards')
from echart_dashboard import compile_dashboard, manifest_template, populate_template

r = compile_dashboard(manifest, write_html=False, write_json=False, strict=True)
if not r.success:
    raise ValueError(f"COMPILE FAILED: {r.error_message}")

s3_manager.put(r.html.encode('utf-8'), f'{DASHBOARD_PATH}/dashboard.html')
s3_manager.put(json.dumps(manifest, indent=2).encode('utf-8'),
                f'{DASHBOARD_PATH}/manifest.json')
```

---

## 14. Common dashboard patterns

Chart widget specs inside a dashboard manifest. Same chart-type names and mapping keys as Section 3. (For the basic wide-form `multi_line` see the §0 example.)

### 14.1 Long-form `multi_line` with color

`datasets["rates_long"] = df.melt(id_vars=['date'], var_name='series', value_name='yield')`

```json
{"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
  "title": "UST curve",
  "spec": {
    "chart_type": "multi_line", "dataset": "rates_long",
    "mapping": {"x": "date", "y": "yield", "color": "series",
                  "y_title": "Yield (%)"}
  }}
```

### 14.2 Actuals vs estimates via `strokeDash`

```json
{"widget": "chart", "id": "capex", "w": 12, "h_px": 380,
  "title": "Big Tech capex",
  "subtitle": "solid = actual, dashed = estimate",
  "spec": {
    "chart_type": "multi_line", "dataset": "capex",
    "mapping": {"x": "date", "y": "capex", "color": "company",
                  "strokeDash": "type",
                  "y_title": "Capex ($B)"}
  }}
```

### 14.3 Dual axis

```json
{"widget": "chart", "id": "spx_ism", "w": 12, "h_px": 380,
  "title": "Equities vs ISM",
  "spec": {
    "chart_type": "multi_line", "dataset": "macro",
    "mapping": {"x": "date", "y": "value", "color": "series",
                  "dual_axis_series": ["ISM Manufacturing"],
                  "y_title": "S&P 500", "y_title_right": "ISM Index",
                  "invert_right_axis": false}
  }}
```

Before dual-axis, print `df['series'].unique()` and assert the right-axis name is present. Name mismatch is the #1 failure mode.

### 14.4 Bullet: rates RV screen

`datasets["rv"] = pd.DataFrame({"metric": [...], "current": [...], "low_5y": [...], "high_5y": [...], "z": [...], "pct": [...]})`

```json
{"widget": "chart", "id": "rv_screen", "w": 6, "h_px": 480,
  "title": "Rates RV screen",
  "spec": {
    "chart_type": "bullet", "dataset": "rv",
    "mapping": {"y": "metric", "x": "current",
                  "x_low": "low_5y", "x_high": "high_5y",
                  "color_by": "z", "label": "pct"}
  }}
```

### 14.5 Pairing thesis + watch notes (high-leverage opening pattern)

```json
"layout": {"rows": [
  [
    {"widget": "note", "id": "n_thesis", "w": 6,
      "kind": "thesis", "title": "Bull-steepener resumes",
      "body": "The curve is **bull-steepening** for the third session..."},
    {"widget": "note", "id": "n_watch", "w": 6,
      "kind": "watch", "title": "Levels to watch",
      "body": "| Level | Significance |\n|---|---|\n| 4.10% 10Y | 50dma |\n"}
  ],
  [{"widget": "chart", "id": "curve", "w": 12, "h_px": 380, "spec": {...}}]
]}
```

---

## 15. Palettes

| Palette | Kind | Use |
|---------|------|-----|
| `gs_primary` | categorical | Default (navy, sky, gold, burgundy, ...) |
| `gs_blues` | sequential | Heatmaps, calendar heatmaps, gradients |
| `gs_diverging` | diverging | Correlation matrices, z-score heatmaps |

**Categorical** goes into `option.color`. **Sequential** and **diverging** go into `visualMap.inRange.color` (heatmaps and correlation matrices).

For `series_colors` overrides, the GS brand hex anchors: GS Navy `#002F6C`, GS Sky `#7399C6`, GS Gold `#B08D3F`, GS Burgundy `#8C1D40`, GS Forest `#3E7C17`, GS Positive `#2E7D32`, GS Negative `#B3261E`.

---

## 16. Anti-patterns (PROHIBITED)

| Anti-pattern | Do instead |
|--------------|-----------|
| Literal numbers in manifest JSON | Pass the DataFrame; compiler converts |
| Prism hand-writing HTML, CSS, or JS | Emit manifest; `compile_dashboard()` does it |
| Source attribution in title/subtitle | Keep dashboard-level vendors in `metadata.sources`; per-column lineage in dataset `field_provenance` (4.4.1) |
| Dropping provenance because the upstream system isn't Haver/FRED/market_data | Use `system: "computed"` + `recipe`, or `system: "csv"` + file path. Never drop -- one click should always trace back to the source. |
| Annotating self-evident facts (zero line on a spread) | Omit |
| `np.zeros()` fill when data is missing | Skip the panel or add a text note |
| Positive/negative color on bar charts | Bar's position vs zero already conveys sign |
| Horizontal rules on bar charts | Put threshold in title/subtitle/narrative |
| Hand-tuning `y_title_gap` / `grid.left` | Just set `x_title` / `y_title`; compiler sizes from real label widths |
| Setting `axisLabel.show: false` to hide overflowing categories | Set `category_label_max_px` (or accept 220 px default) |
| Saving a user dashboard only to `SESSION_PATH` | Persist to `users/{kerberos}/dashboards/...` |
| `build.py` with > 50 lines | It's inlining HTML; use `compile_dashboard` |
| Skipping the refresh button by editing HTML | Don't edit HTML; set `metadata.kerberos` + `dashboard_id` instead |
| Calling `sanitize_html_booleans()` or similar legacy helpers | Not needed -- compiler handles booleans |

---

## 17. Pre-flight checklist (user dashboard)

- [ ] `dashboard.html` persisted to `users/{kerberos}/dashboards/{name}/`
- [ ] `manifest.metadata.kerberos` + `dashboard_id` + `data_as_of` are set (drives refresh button + freshness badge)
- [ ] `manifest.metadata.refresh_frequency` set (`hourly | daily | weekly | manual`)
- [ ] `manifest_template.json` saved alongside the manifest
- [ ] `scripts/pull_data.py` + `scripts/build.py` saved to `{DASHBOARD_PATH}/scripts/`
- [ ] `manifest.json` saved with both scripts registered
- [ ] Registry entry added to `users/{kerberos}/dashboards/dashboards_registry.json`
- [ ] `update_user_manifest(kerberos, artifact_type='dashboard')` called
- [ ] `pull_data.py` handles intraday failures defensively
- [ ] Each dataset is cleaned before passing: `df.reset_index()` for DTI-keyed frames, plain English column names, no MultiIndex
- [ ] Each dataset that backs a chart or table widget carries `field_provenance` (per-column `system` + `symbol`); see 4.4.1 for the cleaning contract by source fn (Haver / market_data / plottool / FRED / Bloomberg / computed)
- [ ] Each dataset is under the size budget: < 50K rows, < 2 MB serialised; total manifest < 5 MB
- [ ] `build.py` is thin (loads data + `populate_template` + `compile_dashboard`, nothing else)
- [ ] Refresh `build.py` calls `compile_dashboard(..., strict=True)` so size / shape errors hard-fail before publication
- [ ] Download link delivered to the user
- [ ] `compile_dashboard` called with `write_html=False, write_json=False` and outputs manually saved via `s3_manager.put()`

---

## 18. Data shape preparation & budget limits

> Companion: `DATA_SHAPES.md` covers the *prior question* in depth -- DataFrame organisation, tidy vs wide, per-archetype templates (#1-20), reuse across widgets, the pull-to-manifest cleaning pipeline (Haver / market_data / plottool / FRED), filter alignment rules, drill-down patterns, and size budgets. Read once, internalise the model, then refer back to its cheat-sheet (Section 13 of `DATA_SHAPES.md`) when authoring a manifest.

**The five non-negotiables for DataFrames:**

1. **Tidy.** One row = one observation, one column = one variable. No multi-index, no embedded headers, no "totals" row.
2. **Date as a column.** Never as a `DatetimeIndex`. Use `df.reset_index()`. The compiler emits `date` to ISO-8601; ECharts auto-detects time-axis from that column.
3. **Plain-English columns.** `us_10y`, not `USGG10YR Index`. The compiler humanizes `us_10y` -> `US 10Y` and uses your column name in legends, tooltips, axis hints.
4. **Datasets named like nouns.** `rates`, `cpi`, `flows`, `bond_screen` -- not `df1`, not `usggt10y_panel`.
5. **A dataset earns its name.** Register in `manifest.datasets` if (a) more than one widget reads from it, OR (b) a single widget needs filter-aware re-rendering, OR (c) a table widget displays the rows verbatim. Otherwise inline a one-shot DataFrame is fine.

**20 data archetypes** mapped to chart types (full table in `DATA_SHAPES.md` §3):

| # | Archetype | DataFrame shape | Chart type |
|---|-----------|-----------------|------------|
| 1 | Univariate time series | `(date, value)` | `line` |
| 2 | Multi-variable TS, fixed set | `(date, v1, v2, ...)` wide | `multi_line`, `area` |
| 3 | Multi-variable TS, dynamic | `(date, group, value)` long | `multi_line` color=, `area` color= |
| 4 | Cross-section, 1 metric | `(cat, value)` | `bar`, `bar_horizontal`, `pie`, `donut`, `funnel` |
| 5 | Cross-section, grouped | `(cat, group, value)` long | `bar` stack, `scatter` color= |
| 6 | Bivariate scatter | `(x_num, y_num, [color])` | `scatter`, `scatter_multi` |
| 7 | Distribution / sample | `(value)` one column | `histogram` |
| 8 | Distribution by group | `(group, value)` long | `boxplot` |
| 9 | Range + current marker | `(cat, lo, hi, cur, ...)` | `bullet` |
| 10 | OHLC time series | `(date, open, close, low, high)` wide | `candlestick` |
| 11 | Daily scalar over a year | `(date, value)` | `calendar_heatmap` |
| 12 | Cat x cat matrix | `(x_cat, y_cat, value)` long | `heatmap` |
| 12b | Wide-form time-series correlation | `(date, col_a, col_b, ...)` wide | `correlation_matrix` |
| 13 | Hierarchy | path or `(name, parent, value)` | `treemap`, `sunburst`, `tree` |
| 14 | Flow / network | `(source, target, value)` | `sankey`, `graph` |
| 15 | Multi-dim by entity | `(entity, dim, value)` long | `radar`, `parallel_coords` |
| 16 | Single scalar | one number | `gauge` |
| 17 | Rich row-per-entity | `(id, attr1, attr2, ...)` wide | `table` widget |
| 18 | Latest snapshot from TS | (any TS DF) | `kpi` source = `<ds>.latest.<col>` |
| 19 | Sparse event list | `(date, label, [color])` | annotations on another chart |
| 20 | Schedule / agenda | `(date, time, event, ...)` | `table` widget |
| 21 | Exploratory bivariate | wide numeric panel | `scatter_studio` (interactive picker) |

**Five mistakes the compiler refuses to silently fix** (and what each diagnostic is named):

| What Prism must do | Diagnostic if skipped |
|--------------------|------------------------|
| `df.reset_index()` before passing a DatetimeIndex-keyed frame | `dataset_dti_no_date_column` |
| Unpack `pull_market_data` tuples: `eod_df, _ = pull_market_data(...)` | `dataset_passed_as_tuple` |
| Flatten MultiIndex columns: `df.columns = ['_'.join(c) for c in df.columns]` | `dataset_columns_multiindex` |
| Rename opaque API codes to plain English (use `df.attrs['metadata']`) | `dataset_column_looks_like_code` (warning) |
| Resample to native frequency per series | mixed-freq NaN gaps render as broken stair-steps |

**Data budget limits** (enforced by `compile_dashboard(strict=True)`):

- **Single dataset rows**: 10,000 (warn), 50,000 (error)
- **Single dataset bytes**: 1 MB (warn), 2 MB (error)
- **Total manifest bytes**: 3 MB (warn), 5 MB (error)
- **Table widget rows**: 1,000 (warn), 5,000 (error)

Haver stores many monthly/quarterly series at business-daily granularity. Symptom: stair-step lines. Fix: resample to true native frequency before charting -- and never chart a DataFrame with mixed-frequency NaN gaps (resample to lowest common frequency before concat / merge).

```python
starts = starts.resample('M').last()   # stock: last-of-month
claims = claims.resample('M').mean()   # flow: mean
cpi    = cpi.resample('Q').last()      # rate: last

df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
assert len(df) > 0, "empty after cleaning"
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

Override: if the narrative references "highest since X", the chart must include X. For pre-pandemic comparisons start >= 2015. Don't show 12 months of monthly (hides cycle), 30 years of daily (noise), or different ranges for charts meant to be compared.
