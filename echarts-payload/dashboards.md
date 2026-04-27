# ECharts Dashboards

**Module:** `dashboards`
**Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
**Tier:** 2 (on-demand)
**Scope:** ALL dashboard construction in PRISM. (For one-off PNG charts in chat / email / report, PRISM uses Altair via `make_chart()` -- a separate module not covered here.)

A dashboard is a JSON manifest. PRISM never writes HTML, CSS, or JS. PRISM emits structured JSON; the compiler does the rest.

One visual style only -- the Goldman Sachs brand: GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans typeface stack, thin grey grid on paper-white. No theme switcher.

`compile_dashboard(manifest)` is the only PRISM-facing entry point. It validates a JSON manifest, lowers each `widget: chart` through internal builders, and emits an interactive dashboard HTML + manifest JSON.

---

## 0. The contract: real data, no literals, canonical layout, scripts on disk

Four rules; all four absolute. A dashboard that violates any of them is broken even if `dashboard.html` renders.

**Rule 1 -- real data only.** Every series traces to a real pull. The four auto-saving primitives are `pull_market_data`, `pull_haver_data`, `pull_plottool_data`, `pull_fred_data`. Everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, Coalition, Inquiry, hand-built DataFrames from scrapers) lands via `save_artifact()` (Section 12.1a). Forbidden: `np.random.*`, `np.linspace`/`np.arange` as data, hand-typed numeric arrays as "demo"/"placeholder", synthetic fill for missing values, invented dates or labels. If no source exists, do not build the panel -- add a data source first.

**Rule 2 -- no literal data inside the manifest JSON.** Pass DataFrames; the compiler converts them to the canonical on-disk shape. PRISM never types numbers into the JSON. Three accepted dataset entry shapes, all normalised:

| Shape | When |
|-------|------|
| `datasets["rates"] = df` | Most common. Zero ceremony. |
| `datasets["rates"] = {"source": df}` | When attaching metadata to the entry later. |
| `datasets["rates"] = {"source": df_to_source(df)}` | When the manifest is saved/read before the compiler touches it. |

**Rule 3 -- order is non-negotiable; remediation is the work.** `pull_data.py` (Section 12) must complete with real DataFrames -- printed `df.shape` / `df.head()` / `df.dtypes` -- before `build.py` is authored. Write the manifest *against verified shapes*, not imagined columns. If you inherit a non-compliant dashboard (bypasses `compile_dashboard()`, hand-writes HTML/CSS/JS, types numbers into `datasets[*].source`, or skips persistence), bringing it back to spec takes priority over whatever surface change was originally asked for. Surface the trade transparently.

**Rule 4 -- canonical layout is non-negotiable; `scripts/` is required, not optional; the persisted script IS what runs.** Every persistent user dashboard MUST land at `users/{kerberos}/dashboards/{name}/` with the full set of artefacts shown in Section 2.2: `dashboard.html`, `manifest.json`, `manifest_template.json`, `scripts/pull_data.py`, `scripts/build.py`, and the raw CSVs in `data/`. The two `.py` files under `scripts/` are not "nice to have" -- they are exactly what the refresh runner re-executes on schedule (Section 12.3). A dashboard whose `scripts/` folder is empty or missing is a one-shot static snapshot: [Refresh] fails the moment the user clicks it, the registry flips to `last_refresh_status: error`, and the dashboard surfaces a `FileNotFoundError` directly in the in-browser error modal (Section 12.3a) -- the failure is loud and PRISM-recoverable, not silent.

**Rule 5 -- every CSV lives at `{DASHBOARD_PATH}/data/<dataset>.csv`, period.** Inside `pull_data.py`, every pull-function call and every `save_artifact(...)` call MUST pass `output_path=f'{SESSION_PATH}/data'`. The refresh runner injects `SESSION_PATH = dashboard_folder` (= `{DASHBOARD_PATH}`) into the script's namespace at exec time, so `f'{SESSION_PATH}/data'` resolves to the same S3 folder both at build time (Tool 1's exec from S3) and at refresh time (Section 12.1a). That is the only routing that lands the CSVs in the flat `data/` folder where `build.py` reads them back. Without `output_path`, `pull_market_data` writes to `{DASHBOARD_PATH}/market_data/`, `pull_haver_data` to `{DASHBOARD_PATH}/haver/`, `pull_plottool_data` to `{DASHBOARD_PATH}/plottool_data/` -- subfolders that `build.py` does not look in, so refresh fails on `FileNotFoundError`.

The dataset key in `manifest.datasets` matches the on-disk CSV stem byte-for-byte. For `pull_market_data` the function ALWAYS appends `_eod` (or `_intraday`) to the CSV filename; pass `name='rates'` (no suffix), get `data/rates_eod.csv` on disk, and use `'rates_eod'` as the dataset key in the manifest. Pass `name='rates_eod'` and you get the doubly-suffixed `data/rates_eod_eod.csv`, which is uniformly the wrong answer. Section 12.1a has the full per-source pattern.

**The build flow IS the refresh path** (Section 12.1). PRISM does NOT pull data in the ephemeral session and then persist a script after the fact; PRISM does NOT compile in the ephemeral session and then persist a script after the fact. PRISM authors each script as a Python string, persists it to S3, and `exec`s it FROM S3 with the same namespace shape the refresh runner uses. This collapses two would-be-different code paths (build-time and refresh-time) into one: what runs during the initial build is byte-identical to what runs every refresh. No drift is possible, no double work happens, and the build itself doubles as the refresh smoke test (Section 12.6).

```python
df_rates_eod, _ = pull_market_data(
    coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
    start='2020-01-01', name='rates', mode='eod')
df_rates_eod.columns = ['us_2y', 'us_10y']            # plain English (Rule 1)
manifest = {
    "schema_version": 1, "id": "rates", "title": "US Rates",
    "datasets": {"rates_eod": df_rates_eod.reset_index()},
    "layout": {"rows": [[{"widget": "chart", "id": "curve", "w": 12,
        "spec": {"chart_type": "multi_line", "dataset": "rates_eod",
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

For **persistent user dashboards** the unit of organisation is `users/{kerberos}/dashboards/{name}/`; everything that belongs to a dashboard lives inside it. **This layout is non-negotiable (Rule 4, Section 0).** Every artefact tagged `[REQUIRED]` below must be present on S3 by the end of the build, or the dashboard is broken even if `dashboard.html` renders:

```
users/{kerberos}/dashboards/{dashboard_name}/
  manifest_template.json    [REQUIRED] SOURCE OF TRUTH (LLM-editable spec, NO data)
  manifest.json             [REQUIRED] BUILD ARTIFACT (template + fresh data, embedded)
  dashboard.html            [REQUIRED] DELIVERABLE (compile_dashboard output)
  refresh_status.json       STATE (status, started_at, errors[], pid, auto_healed)
  thumbnail.png             optional
  scripts/                  [REQUIRED] without these the refresh pipeline has nothing to run
    pull_data.py            [REQUIRED] data acquisition (~50-150 lines). Refresh runner re-executes verbatim
    build.py                [REQUIRED] ~12 lines: load data, populate_template, compile. Refresh runner re-executes verbatim
  data/                     [REQUIRED] populated by pull_data.py via output_path=f'{SESSION_PATH}/data' (Rule 5; SESSION_PATH = DASHBOARD_PATH at refresh time)
    rates_eod.csv           one CSV per dataset; build.py reads these back. Stem matches manifest dataset key
    rates_intraday.csv      pull_market_data ALWAYS appends _eod / _intraday to the filename
    rates_metadata.json     metadata sidecar; same name= base, NO _eod / _intraday suffix
    cpi.csv                 pull_haver_data: no suffix
    cpi_metadata.json
    swap_curve.csv          pull_plottool_data: no suffix
    swap_curve_metadata.json
    fdic_gs_bank.csv        save_artifact (alt-data): no suffix
  history/                  optional snapshots when keep_history=true
```

**Why every `[REQUIRED]` artefact actually has to be there.** Refresh works (Section 12.3) because the runner re-executes the persisted `scripts/pull_data.py` and `scripts/build.py` on a schedule -- it does not call PRISM, does not store any LLM state, does not have access to whatever was in the conversation that built the dashboard the first time. If `scripts/pull_data.py` is missing on S3, the runner has nothing to run, the [Refresh] button POSTs and immediately fails, the registry's `last_refresh_status` flips to `error`, and -- critically -- the dashboard surfaces this to the user via the in-browser error modal (Section 12.3a) with a `FileNotFoundError: ...scripts/pull_data.py` message and a one-click `[Copy markdown for PRISM]` button. The user pastes that report into PRISM and PRISM is expected to fix it on the spot (the manifest template is intact; only the missing script needs re-uploading). Same for `manifest_template.json`: `scripts/build.py` reads it back to know the structural shape; without it, build.py can't run. Same for `data/*.csv`: build.py reads CSVs that pull_data.py wrote; without them, build.py can't run. Skipping any one of these is **silent at build time, surfaced loudly the moment the user clicks Refresh, and PRISM-fixable from the modal output without rebuilding from scratch**.

Forbidden: HTML / CSS / JS in any `.py` file (`rendering.py` owns it); `scripts/build_dashboard.py` (renamed to `build.py`); per-source folders (`haver/`, `market_data/` -- everything goes to `data/`); timestamped scripts (`20260424_*.py`); session-only artifacts at dashboard scope (`*_results.md`, `*_artifacts.json`); multiple data JSONs (only `manifest.json`); inline `<script>const DATA = {}` in HTML; legacy helpers (`sanitize_html_booleans()`); building a "persistent" dashboard whose `scripts/` folder is empty or missing on S3 (see "Why every `[REQUIRED]` artefact actually has to be there" above).

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
| `show_values` / `value_decimals` | Print correlation in each cell (default `True` / `2`; values clamped to the global decimal cap, see Section 3.3) |
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

**Heatmap-style charts** (`heatmap`, `correlation_matrix`, `calendar_heatmap`) accept these cell-label / color keys: `show_values` (default `True` for heatmap / correlation_matrix, `False` for calendar_heatmap), `value_decimals` (auto-picked from data magnitude; clamped to the global decimal cap, Section 3.3), `value_formatter` (raw ECharts function string -- suppresses auto-contrast and the cap; you author what renders), `value_label_color` (`"auto"` / hex / `False`), `value_label_size` (default 11), `colors`, `color_palette`, `color_scale` (`sequential` / `diverging` / `auto` -- diverging when data crosses zero), `value_min` / `value_max` (pin visualMap range so colors stay interpretable across reruns).

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

**Global decimal cap.** Every numeric value rendered anywhere in a dashboard -- value-axis tick labels, tooltips, KPI tiles, table cells, heatmap cell labels, correlation coefficients, regression statistics, the "View raw data" modal -- is hard-capped at 2 decimal places. Author-supplied precision options (`value_decimals`, `decimals`, `delta_decimals`, `tooltip.decimals`, table format suffixes like `"number:5"`) are silently coerced down to the cap; passing `value_decimals: 5` produces the same output as `value_decimals: 2`. Value axes that the builder didn't already attach an explicit `axisLabel.formatter` to inherit a default formatter capped at 2 decimals so tightly-zoomed axes can't bleed extra digits. The cap is a non-negotiable house rule (config.MAX_DASHBOARD_DECIMALS); raise it in `config.py` if the policy ever changes. Author-supplied raw JS function strings (`value_formatter`, `tooltip.formatter`, `axisLabel.formatter`) are NOT inspected -- if you hand-write a formatter that emits 4 decimals it will render 4 decimals. Use the structured `value_decimals` / `tooltip.decimals` knobs and the cap protects you.

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
| `delta_label` / `delta_decimals` | Label after delta / precision (default 2; clamped to the global cap, Section 3.3) |
| `prefix` / `suffix` / `decimals` | Prepended / appended (`$`, `%`, `bp`); precision for value (default 2 for <1000, else 0; clamped to the global cap) |
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
| `format` | `text` / `number[:d]` / `integer` / `percent[:d]` / `currency[:d]` / `bps[:d]` / `signed[:d]` / `delta[:d]` / `date` / `datetime` / `link`. The `:d` suffix is clamped to the global decimal cap (Section 3.3) -- `"number:5"` renders identically to `"number:2"` |
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
| `row_default` / `col_default` / `value_default` / `agg_default` / `decimals` | no | Initial selections; cell precision (default 2; clamped to the global cap, Section 3.3) |
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

NON-NEGOTIABLE: every user-requested dashboard persists to `users/{kerberos}/dashboards/{name}/`, and that folder MUST contain `dashboard.html`, `manifest.json`, `manifest_template.json`, `scripts/pull_data.py`, `scripts/build.py`, and the raw CSVs in `data/` (Section 2.2, Rule 4 of Section 0). A dashboard living only in `SESSION_PATH` won't refresh, won't appear in the user's list, and is lost when the conversation ends. A dashboard at the right path but missing `scripts/` is equally broken: the [Refresh] button has nothing to call, the registry flips to `last_refresh_status: error`, and the user has no recovery path.

NON-NEGOTIABLE: every CSV referenced by `build.py` lives at `{DASHBOARD_PATH}/data/<dataset>.csv`. Inside `pull_data.py`, every `pull_*_data(...)` and `save_artifact(...)` call MUST pass `output_path=f'{SESSION_PATH}/data'` (Rule 5 of Section 0); the refresh runner pins `SESSION_PATH = {DASHBOARD_PATH}` so the same string resolves correctly at build time and refresh time. The dataset key in `manifest.datasets` matches the on-disk CSV stem. Section 12.1a is the per-source pattern for the four pull primitives plus `save_artifact()` for everything else.

### 12.1 Three-tool-call build model

```
Tool 1: pull_data.py   Author pull_data.py as a string, persist to
                       {DASHBOARD_PATH}/scripts/pull_data.py, then exec FROM S3
                       with the refresh-runner namespace. The exec writes
                       raw CSVs to {DASHBOARD_PATH}/data/. Read CSVs back
                       to verify shapes/heads/dtypes for Tool 2.
Tool 2: build.py       Compose the initial manifest (with embedded data, just
                       to derive the template), persist
                       {DASHBOARD_PATH}/manifest_template.json, author
                       build.py as a string, persist to
                       {DASHBOARD_PATH}/scripts/build.py, then exec build.py
                       FROM S3. The exec writes manifest.json + dashboard.html.
Tool 3: register       Upsert entry in dashboards_registry.json; call
                       update_user_manifest(kerberos, artifact_type='dashboard');
                       print portal URL.
```

**The persisted script is the source of truth -- write it first, then run it from S3.** PRISM does NOT pull data in the ephemeral session and then write a script that "would do the same thing"; PRISM does NOT call `compile_dashboard` directly in the ephemeral session and then write a build script that "would re-compile". PRISM authors each script as a Python string, `s3_manager.put`s it to `{DASHBOARD_PATH}/scripts/<name>.py`, then `s3_manager.get`s it back and runs it via `exec(compile(src, ...), ns)` with the same namespace shape the refresh runner uses (Section 12.3). Two consequences:

1. **No double work.** The pull happens once -- inside Tool 1's exec from S3. The compile happens once -- inside Tool 2's exec from S3. Pulling data in-session and then re-pulling at refresh would do the same work twice; same for compile.
2. **No drift.** What runs at build time is byte-identical to what the refresh runner will execute every morning. If the persisted script would break tomorrow, it breaks during Tool 1 or Tool 2 today, while PRISM still has the build context in scope. PRISM fixes it before the user ever sees a refresh error modal (Section 12.3a). This is also why no separate "Tool 4 smoke test" is needed: the build flow IS the smoke test (Section 12.6).

Order is still non-negotiable (Section 0): Tool 1 must complete with verified DataFrames -- read back from S3 CSVs after the exec, with `df.shape` / `df.head()` / `df.dtypes` printed -- before Tool 2 authors `build.py` against those columns.

**Tool 1 -- author + persist + exec `pull_data.py` FROM S3.**

```python
DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# 1. Author pull_data.py as a string. THIS is the source of truth --
#    the refresh runner will re-exec these exact bytes daily.
#    Every pull function call passes output_path=f'{SESSION_PATH}/data'
#    (Rule 5 of Section 0). At refresh time SESSION_PATH IS DASHBOARD_PATH
#    -- the refresh runner injects DASHBOARD_PATH as SESSION_PATH so the
#    same string resolves to the same S3 folder.
pull_data_py = '''
"""pull_data.py -- daily refresh of rates monitor data."""
from datetime import datetime
print(f"[pull_data.py] starting at {datetime.now().isoformat()}")

# pass name='rates' (no _eod suffix); pull_market_data appends it.
# Resulting on-disk: {SESSION_PATH}/data/rates_eod.csv
#                    {SESSION_PATH}/data/rates_metadata.json
pull_market_data(
    coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
    start='2020-01-01',
    name='rates',
    mode='eod',
    output_path=f'{SESSION_PATH}/data',
)

# Defensive intraday fallback (Section 12.4) goes here when needed.
print("[pull_data.py] done")
'''.lstrip()

# 2. Persist verbatim
s3_manager.put(pull_data_py.encode(), f'{DASHBOARD_PATH}/scripts/pull_data.py')

# 3. Exec FROM S3 with the refresh-runner namespace. Writes CSVs to
#    {DASHBOARD_PATH}/data/.
import io as _io
src = s3_manager.get(f'{DASHBOARD_PATH}/scripts/pull_data.py').decode('utf-8')
ns = {
    'pd': pd, 'np': np, 'io': _io, 'json': json, 'os': os,
    'datetime': datetime,
    's3_manager': s3_manager,
    'SESSION_PATH': DASHBOARD_PATH.rstrip('/'),
    'pull_haver_data':   pull_haver_data,
    'pull_market_data':  pull_market_data,
    'pull_plottool_data': pull_plottool_data,
    'pull_fred_data':    pull_fred_data,
    'save_artifact':     save_artifact,
}
exec(compile(src, f'{DASHBOARD_PATH}/scripts/pull_data.py', 'exec'), ns)

# 4. Verify by reading the CSVs back from S3. PRISM uses these shapes
#    when authoring build.py in Tool 2. The read path here is the
#    SAME path the refresh-time build.py will read tomorrow morning.
df = pd.read_csv(_io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                  index_col=0, parse_dates=True)
print(f'[verify] rates_eod: shape={df.shape}')
print(df.head())
print(df.dtypes)
```

**Tool 2 -- author + persist + exec `build.py` FROM S3.**

```python
import io
df = pd.read_csv(io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                  index_col=0, parse_dates=True)
df.columns = ['us_2y', 'us_10y']      # plain English (Rule 1)

# 1. Compose the initial manifest (with embedded data, just to derive
#    the structural template). PRISM does NOT compile this manifest --
#    build.py does, when it is exec'd from S3 below. Dataset key
#    'rates_eod' matches the on-disk CSV stem (Rule 5).
initial_manifest = {
    "schema_version": 1, "id": DASHBOARD_NAME, "title": "Rates Monitor",
    "metadata": {"kerberos": KERBEROS, "dashboard_id": DASHBOARD_NAME,
                  "data_as_of": str(df.index.max().date()),
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "sources": ["GS Market Data"], "refresh_frequency": "daily",
                  "refresh_enabled": True, "tags": ["rates"]},
    "datasets": {"rates_eod": df.reset_index()},
    "layout": {"rows": [[{"widget": "chart", "id": "curve", "w": 12,
        "title": "UST Curve",
        "spec": {"chart_type": "multi_line", "dataset": "rates_eod",
                  "mapping": {"x": "date",
                               "y": ["us_2y", "us_10y"]}}}]]}
}

tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(),
                f'{DASHBOARD_PATH}/manifest_template.json')

# 2. Author build.py as a string (~12 lines: load template + load CSVs +
#    populate_template + compile + upload). THIS is the refresh-time
#    build.py the runner will re-exec daily. The CSV path it reads
#    (`{SESSION_PATH}/data/rates_eod.csv`) is byte-identical to what
#    Tool 1's pull_data.py wrote.
build_py = '''import io, json, pandas as pd
from datetime import datetime, timezone

tpl = json.loads(s3_manager.get(f"{SESSION_PATH}/manifest_template.json"))
df = pd.read_csv(io.BytesIO(s3_manager.get(f"{SESSION_PATH}/data/rates_eod.csv")),
                  index_col=0, parse_dates=True)
df.columns = ["us_2y", "us_10y"]
m = populate_template(tpl, {"rates_eod": df.reset_index()},
                       metadata={"data_as_of": str(df.index.max().date()),
                                  "generated_at": datetime.now(timezone.utc).isoformat()},
                       require_all_slots=True)
r = compile_dashboard(m, write_html=False, write_json=False, strict=True)
if not r.success:
    raise ValueError(f"compile failed: {r.error_message}")
s3_manager.put(r.html.encode("utf-8"), f"{SESSION_PATH}/dashboard.html")
s3_manager.put(json.dumps(m, indent=2).encode("utf-8"), f"{SESSION_PATH}/manifest.json")
print("[build.py] success")
'''
s3_manager.put(build_py.encode(), f'{DASHBOARD_PATH}/scripts/build.py')

# 3. Exec build.py FROM S3 with the refresh-runner namespace. The exec
#    writes manifest.json + dashboard.html as side effects.
src = s3_manager.get(f'{DASHBOARD_PATH}/scripts/build.py').decode('utf-8')
ns = {
    'pd': pd, 'np': np, 'io': io, 'json': json, 'os': os,
    'datetime': datetime, 'timezone': timezone,
    's3_manager': s3_manager,
    'SESSION_PATH': DASHBOARD_PATH.rstrip('/'),
    'compile_dashboard': compile_dashboard,
    'populate_template': populate_template,
    'manifest_template': manifest_template,
    'validate_manifest': validate_manifest,
}
exec(compile(src, f'{DASHBOARD_PATH}/scripts/build.py', 'exec'), ns)

# 4. Confirm every required artefact landed on S3 (Rule 4 of Section 0).
for sub in ['scripts/pull_data.py', 'scripts/build.py',
            'manifest_template.json', 'manifest.json', 'dashboard.html']:
    if not s3_manager.exists(f'{DASHBOARD_PATH}/{sub}'):
        raise FileNotFoundError(f'[Tool 2] missing on S3: {sub}')
print('[Tool 2] complete; ready for Tool 3 (register)')
```

A failure in either Tool 1 or Tool 2 surfaces the same exception the refresh runner would surface tomorrow morning. Iterate on the script string + re-run the tool until both Tool 1 and Tool 2 succeed end-to-end. There is no separate "verify the refresh works" step because the build IS that verification (Section 12.6).

**Tool 3 -- register:** writes the per-dashboard pipeline manifest, upserts an entry into `users/{kerberos}/dashboards/dashboards_registry.json` (`id`, `name`, `description`, `created_at`, `last_refreshed`, `last_refresh_status`, `refresh_enabled`, `refresh_frequency`, `folder`, `html_path`, `data_path`, `tags`, `keep_history`, `history_retention_days`), then calls `update_user_manifest(kerberos, artifact_type='dashboard')`. Print the portal URL (`http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{DASHBOARD_NAME}/`) -- the persistent, auto-refreshing link.

### 12.1a Data sources for `pull_data.py`

Five primitives cover every dashboard. Inside `pull_data.py` they all
land their CSVs in the same flat folder by passing `output_path=
f'{SESSION_PATH}/data'`. At refresh time the runner injects
`SESSION_PATH = {DASHBOARD_PATH}` into `pull_data.py`'s namespace, so
the same string resolves to the same S3 folder both at build time
(Tool 1's exec from S3) and at refresh time. There is no separate
`DASHBOARD_PATH` reference inside `pull_data.py` -- it uses
`SESSION_PATH`, the runner injects the right value.

#### Pull primitive cheat sheet

| Function              | Call                                                                                                                  | On-disk CSV                          | Metadata sidecar                       | Manifest dataset key |
|-----------------------|-----------------------------------------------------------------------------------------------------------------------|--------------------------------------|----------------------------------------|----------------------|
| `pull_haver_data`     | `pull_haver_data(codes=[...], start='YYYY-MM-DD', name='cpi', output_path=f'{SESSION_PATH}/data')`                    | `data/cpi.csv`                       | `data/cpi_metadata.json`               | `'cpi'`              |
| `pull_market_data`    | `pull_market_data(coordinates=[...], start='YYYY-MM-DD', name='rates', mode='eod', output_path=f'{SESSION_PATH}/data')` | `data/rates_eod.csv` (always `_eod` suffix) | `data/rates_metadata.json` (no suffix) | `'rates_eod'`        |
| `pull_market_data` (intraday) | same but `mode='iday'`                                                                                          | `data/rates_intraday.csv`            | `data/rates_metadata.json`             | `'rates_intraday'`   |
| `pull_plottool_data`  | `pull_plottool_data(expressions=[...], labels=[...], start='YYYY-MM-DD', name='swap_curve', output_path=f'{SESSION_PATH}/data')` | `data/swap_curve.csv` | `data/swap_curve_metadata.json` | `'swap_curve'` |
| `pull_fred_data`      | `pull_fred_data(series=[...], start='YYYY-MM-DD', name='unrate', output_path=f'{SESSION_PATH}/data')`                 | `data/unrate.csv`                    | `data/unrate_metadata.json`            | `'unrate'`           |
| `save_artifact` (alt-data, see below) | `save_artifact(data, name='gs_bank', output_path=f'{SESSION_PATH}/data')`                              | `data/gs_bank.csv` (or `.json` if dict) | (no sidecar)                        | `'gs_bank'`          |

Three rules from the table that are easy to get wrong:

1. **`name=` does NOT include `_eod` / `_intraday`.** `pull_market_data` appends them. Pass `name='rates'` -> `data/rates_eod.csv`. Pass `name='rates_eod'` -> `data/rates_eod_eod.csv` (broken).
2. **`pull_market_data` metadata sidecar uses the bare `name`,** not the suffixed CSV stem. So `name='rates'` produces `data/rates_metadata.json` (one file even when both eod and intraday CSVs exist).
3. **`mode='eod'` is the default** but pass it explicitly anyway. The intraday CSV is only written when `mode in ('iday', 'both')`. See Section 12.4 for the defensive try/except wrap that handles overnight / weekend intraday gaps.

#### Reading the CSVs back in `build.py`

```python
import io
df = pd.read_csv(io.BytesIO(s3_manager.get(f'{SESSION_PATH}/data/rates_eod.csv')),
                 index_col=0, parse_dates=True)
df.columns = ['us_2y', 'us_10y']        # rename to plain English (Rule 1)

# repeat for each other CSV the manifest needs
```

The path `{SESSION_PATH}/data/rates_eod.csv` is byte-identical to what
`pull_data.py` wrote because both scripts reference `SESSION_PATH`,
which the refresh runner pins to `{DASHBOARD_PATH}` for both execs.
The dataset key (`rates_eod`) matches the CSV stem; `populate_template`
maps the cleaned DataFrame back into the template by that key.

#### `save_artifact()` for alternative data sources

The four pull primitives only cover Haver / GS Market Data / TSDB
expressions / FRED. For everything else (FDIC, SEC EDGAR, BIS,
Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI,
Substack, Wikipedia, Pure / Alloy, scraped tables, hand-built
DataFrames) -- `save_artifact()` is the universal save helper. Same
`output_path` semantics as the pulls; it lands a CSV (or JSON for
`dict` payloads) at `{output_path}/{name}.{ext}` and is idempotent on
re-run.

```python
# inside pull_data.py
fdic_records = fdic_client.get_bank_financials(cert=33124, quarters=8)
save_artifact(
    fdic_records,
    name='gs_bank',
    output_path=f'{SESSION_PATH}/data',
)
# -> {SESSION_PATH}/data/gs_bank.csv

sec_data = sec_edgar_client.cmd_company_financials('AAPL', 'default')
save_artifact(
    sec_data,
    name='aapl_financials',
    output_path=f'{SESSION_PATH}/data',
)
# dict -> {SESSION_PATH}/data/aapl_financials.json (build.py reads json.loads(...))

ny_df = pull_nyfed_data('rates')   # not auto-saving; returns a DataFrame
save_artifact(ny_df, name='nyfed_rates', output_path=f'{SESSION_PATH}/data')
# DataFrame -> {SESSION_PATH}/data/nyfed_rates.csv
```

`save_artifact()`'s output extension follows the input type:
`pandas.DataFrame` / `list[dict]` / object-with-`.to_frame()` -> CSV;
`dict` (or empty list) -> JSON. `build.py` reads JSON via
`json.loads(s3_manager.get(...).decode('utf-8'))` and converts to a
DataFrame at populate time. See `prism/data-functions.md` Section 9
for the full polymorphism table.

#### Refresh-runner namespace caveat

The refresh runner's `_build_exec_namespace` (per
`prism/dashboard-refresh.md` Section 5.3) injects `pd`, `np`, `io`,
`json`, `os`, `datetime`, `s3_manager`, `SESSION_PATH`, the four pull
primitives, `compile_dashboard`, `populate_template`,
`manifest_template`, `validate_manifest`. Anything else used in
`pull_data.py` or `build.py` -- including `save_artifact`, the
alt-data clients (`fdic_client`, `sec_edgar_client`, `bis_client`,
`treasury_client`, `treasury_direct_client`, `nyfed_client`,
`prediction_markets_client`, `openfigi_client`, `substack_client`,
`wikipedia_client`), `pull_nyfed_data`, `pull_pure_data`,
`pull_stacked_data`, and the Coalition / Inquiry helpers -- has to
also be in the refresh-runner namespace. **As of 2026-04-27, the
runner does NOT inject these.** A dashboard whose `pull_data.py`
calls `save_artifact()` or `fdic_client.get_bank_financials()`
builds cleanly (those names ARE in the build-time
`execute_analysis_script` namespace), but the daily refresh raises
`NameError` against the missing helper. The browser then renders the
modal in Section 12.3a with `errors[].classification ==
'unknown'`.

Until the PRISM-side runner namespace catches up, dashboards that
need alt-data are session-only safe but refresh-fragile. Two work-
arounds while the gap closes:

1. **Single-source dashboards using only the four pull primitives**
   refresh cleanly with no caveat. Build those when the user wants a
   persistent auto-refresh.
2. **Multi-source dashboards that need alt-data** can still be built
   today (the build flow runs in the sandbox where `save_artifact` +
   alt-data clients are injected), but `metadata.refresh_enabled`
   should be `False` until the runner namespace is expanded. Surface
   this trade-off explicitly to the user.

The structural fix is PRISM-side: add `save_artifact` and the
alt-data client modules to `_build_exec_namespace` in
`jobs/hourly/refresh_dashboards.py`. Tracked as a known gap in
`prism/_changelog.md` (entry C25 / 2026-04-27).

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

API contract: HTTP 409 (already running) → switch to status polling; `status: "success"` → reload after ~1s; `status: "error"` / `"partial"` → open the error modal (see 12.3a) and keep a persistent "Error details" pill in the header until the next successful refresh. `metadata.api_url` / `metadata.status_url` override the default endpoints.

The dashboard also fires one `GET /api/dashboard/refresh/status/?dashboard_id=...` on initial page load. If `refresh_status.json` reports `error` / `partial`, the persistent "Error details" pill lights up immediately so a user landing on a stale dashboard sees the failure without having to click [Refresh] first.

### 12.3a Refresh error modal (the contract)

A refresh that fails is recoverable from the browser without a developer console. Every failure path -- runner-side error, runner-side partial, polling timeout, network error reaching the API, spawn-time rejection (4xx / 5xx) -- pops a modal carrying the full failure context plus a one-click `[Copy markdown for PRISM]` button that copies a self-contained markdown report for the user to paste back into PRISM. The same modal is reachable any time afterwards via the persistent "! Error details" pill the runtime parks next to the [Refresh] button.

| Failure kind | Trigger | Modal pill |
|---|---|---|
| `runner_error` | `refresh_status.json.status == "error"` | red `REFRESH FAILED` |
| `runner_partial` | `refresh_status.json.status == "partial"` -- some scripts succeeded, some failed | amber `PARTIAL REFRESH` (extra `[Reload anyway]` button alongside `[Try again]`) |
| `timeout` | poll loop hit 60 polls × 3 s without a terminal status | red `POLLING TIMEOUT` |
| `network` | browser `fetch` to `api_url` rejected before the server replied | red `NETWORK ERROR` |
| `spawn_fail` | API responded 4xx / 5xx, or `result.status` neither `refreshing` nor `success` / `partial` | red `SPAWN FAILED` |

The "Copy markdown for PRISM" payload is everything PRISM needs to triage the failure without round-trips. The exact structure (this is the **stable** template -- PRISM-side prompts can pattern-match against it):

```
## Dashboard refresh failure

| Field | Value |
| --- | --- |
| Failure kind | `runner_error` (REFRESH FAILED) |
| Dashboard ID | `<id>` |
| Kerberos | `<kerberos>` |
| Folder | `users/<kerberos>/dashboards/<id>/` |
| `refresh_status.json` status | `error` |
| HTTP status | `200` |
| Started at | `2026-04-26T19:30:00Z` |
| Completed at | `2026-04-26T19:30:14Z` |
| Elapsed | 14.0s |
| Runner PID | `12345` |
| Server log | `/tmp/dashboard_refresh/<kerberos>_<id>_<ts>.log` |
| Captured at | `<browser-now>` |
| Page URL | `<dashboard URL>` |
| User agent | `<UA string>` |

### Errors (`refresh_status.json.errors[]`)

**Error 1**
- script: `pull_data.py`
- classification: `data_pull_empty`

```
<error message>
```

(plus optional traceback block)

### Raw response

```json
<full refresh_status.json or POST response>
```

### What PRISM should check

1. `users/<kerberos>/dashboards/<id>/scripts/pull_data.py` exists on S3 and runs cleanly.
2. `users/<kerberos>/dashboards/<id>/scripts/build.py` exists on S3 and runs cleanly.
3. `users/<kerberos>/dashboards/<id>/manifest_template.json` exists.
4. `users/<kerberos>/dashboards/<id>/data/*.csv` reflects the columns build.py expects.
5. `users/<kerberos>/dashboards/<id>/refresh_status.json` matches the snapshot above.
6. The dashboard is registered in `users/<kerberos>/dashboards/dashboards_registry.json` with `refresh_enabled: true`.
```

PRISM contract: when a user pastes a "Dashboard refresh failure" report, treat it as a triage prompt -- read the named scripts on S3, identify the failing line, fix the script (and only the script unless data shape changed), re-upload. The dashboard does not need to be rebuilt from scratch; the manifest template is intact.

PRISM-side helpers driving the modal (the runtime relies on these existing in `refresh_status.json`):

| Field | Required | Notes |
|---|---|---|
| `status` | yes | `"running"` / `"success"` / `"error"` / `"partial"` |
| `errors` | error/partial | List of strings OR list of dicts. Dicts: `{script, classification, message, traceback?}`. Both shapes are rendered without code change |
| `started_at` / `completed_at` | recommended | ISO-8601 UTC; the modal shows elapsed when both are present |
| `pid` | recommended | Surfaced so PRISM can grep server logs |
| `log_path` (alias `log`) | recommended | Filesystem path of the runner's log; surfaced verbatim. The browser cannot read it; this is for PRISM-side triage |
| `auto_healed` | optional | When the polling endpoint replaces a stale "running" lock with an "error" status |

The runtime also supports `errors` being a single string (legacy shape) or a single dict; both are normalised to the list shape before rendering.

### 12.4 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_data.py` that fetches intraday MUST wrap it in `try/except` with EOD fallback. Every `build.py` must handle missing intraday file defensively. The convention from Section 12.1a still applies: `name='rates'` (no suffix), `output_path=f'{SESSION_PATH}/data'`, dataset keys `'rates_eod'` / `'rates_intraday'` matching the on-disk CSV stems.

```python
# pull_data.py
pull_market_data(
    coordinates=[...], start='2020-01-01',
    name='rates', mode='eod',
    output_path=f'{SESSION_PATH}/data',
)
# -> {SESSION_PATH}/data/rates_eod.csv
try:
    pull_market_data(
        coordinates=[...], mode='iday',
        start=datetime.now().strftime('%Y-%m-%d'),
        name='rates',
        output_path=f'{SESSION_PATH}/data',
    )
    # -> {SESSION_PATH}/data/rates_intraday.csv (only on success)
except Exception as e:
    print(f"Intraday unavailable (normal overnight/weekends): {e}")

# build.py
eod_df = pd.read_csv(io.BytesIO(s3_manager.get(f'{SESSION_PATH}/data/rates_eod.csv')),
                      index_col=0, parse_dates=True)
try:
    iday_df = pd.read_csv(io.BytesIO(s3_manager.get(f'{SESSION_PATH}/data/rates_intraday.csv')),
                          index_col=0, parse_dates=True)
except Exception:
    iday_df = None
current = (iday_df.ffill().iloc[-1] if iday_df is not None and len(iday_df) > 0
           else eod_df.iloc[-1])
```

Both `pull_market_data` calls share `name='rates'`, so the metadata
sidecar (`{SESSION_PATH}/data/rates_metadata.json`) is written /
overwritten by whichever call wrote last. That is the intended shape;
both calls describe the same coordinates, so a single sidecar is
correct.

### 12.5 Common failures → fix

What the user sees in the browser is the modal in 12.3a. The table below maps the most common error messages (rendered verbatim under "Errors" in that modal, also pasted into PRISM via "Copy markdown for PRISM") to root causes and fixes.

| Modal shows (`errors[].message` / classification) | Root cause | Fix |
|---|---|---|
| "No data successfully fetched" / `data_pull_empty` | Intraday unavailable (overnight / weekend) | `try/except` + EOD fallback in `pull_data.py` (12.4) |
| `KeyError: '<col>'` / `data_schema_error` | Schema drift between `pull_data.py` writes and `build.py` reads | Defensive `col in df.columns` checks; resync the column rename in build.py |
| `IndexError: .iloc[-1]` / `data_schema_error` | Empty DataFrame | Guard `len(df) > 0` before `.iloc[-1]` |
| Empty DataFrame after merge | Inner-join dropped every row | Switch to outer join, handle NaNs |
| `FileNotFoundError: ...scripts/pull_data.py` (or `.../scripts/build.py`) | The dashboard was built without persisting the scripts to `{DASHBOARD_PATH}/scripts/` (Rule 4 of Section 0). The runner has nothing to execute | Re-run the build flow with the **required** `s3_manager.put(SCRIPT_TEXT.encode(), '<...>/scripts/<name>.py')` step at the end of every `execute_analysis_script` call. See Section 12.1 |
| `FileNotFoundError: ...manifest_template.json` | Tool 2's `s3_manager.put()` for the template was skipped | Re-run Tool 2; persist the template returned by `manifest_template(initial_manifest)` (Section 12.1) |
| `FileNotFoundError: ...data/<name>.csv` | `pull_data.py` did not write a CSV that `build.py` then tried to read | Confirm `pull_data.py` writes one CSV per dataset to `{DASHBOARD_PATH}/data/`; confirm the names match what `build.py` reads back |
| `FileNotFoundError: ...data/<name>.csv` AND the CSV exists at `{DASHBOARD_PATH}/market_data/<name>_eod.csv` (or `haver/<name>.csv`, `plottool_data/<name>.csv`) | `pull_*_data` was called WITHOUT `output_path=f'{SESSION_PATH}/data'`, so the CSV landed in the per-source default subfolder (Rule 5 of Section 0) | Add `output_path=f'{SESSION_PATH}/data'` to the pull call; rerun Tool 1; confirm CSV moves to `data/`. The previous file in the per-source subfolder is harmless but can be deleted or left as is |
| `FileNotFoundError: ...data/<name>_eod.csv` AND `data/<name>_eod_eod.csv` exists | `pull_market_data` was called with `name='<name>_eod'` -- the function appended `_eod` again, producing the doubly-suffixed filename | Drop the `_eod` suffix from `name=`. Pass `name='<base>'` -> on-disk `data/<base>_eod.csv`. Manifest dataset key stays `'<base>_eod'` |
| `NameError: name 'save_artifact' is not defined` (during refresh; the build worked) | `pull_data.py` uses `save_artifact` but the refresh runner's `_build_exec_namespace` doesn't inject it (Section 12.1a) | Either (a) wait for the PRISM-side runner namespace expansion (tracked in `prism/_changelog.md` 2026-04-27), (b) flip `metadata.refresh_enabled = False` until then, or (c) replace the `save_artifact` calls with one of the four pull primitives if the data source supports it |
| `NameError: name 'fdic_client' is not defined` (or `sec_edgar_client`, `bis_client`, `treasury_client`, `nyfed_client`, `prediction_markets_client`, `pull_nyfed_data`, etc.) | Same shape as the `save_artifact` case: the alt-data client is not in the refresh-runner namespace as of 2026-04-27 | Same options |
| `Connection` / `Timeout` / `network_error` | Transient network failure to a vendor API | Retry the manual refresh; check vendor availability |
| Modal shows `NETWORK ERROR` (browser-side fetch failed) | The PRISM web server is offline or the request was blocked at the network layer | Operations issue; report the URL + status |
| Modal shows `SPAWN FAILED` with `Dashboard <id> not found` | The dashboard is missing from `dashboards_registry.json` (Tool 3 was skipped) | Add the registry entry with `refresh_enabled: true` and call `update_user_manifest(kerberos, artifact_type='dashboard')` |
| Modal shows `POLLING TIMEOUT` after 3 minutes | Runner hung during a slow pull or compilation | Check the server log path the modal lists (`/tmp/dashboard_refresh/...`); usually self-resolves on the next attempt; `auto_healed: true` confirms the lock was reset |
| `[Refresh]` button absent on the dashboard entirely | `metadata.kerberos` or `metadata.dashboard_id` missing, or `metadata.refresh_enabled: false` | Set both fields; redeploy `manifest.json` + `dashboard.html` |
| Header pill says "! Error details" on a freshly loaded dashboard | A previous refresh failed; the on-load status check surfaced it | Click the pill to read the modal; the report is unchanged from the last failure |
| Dashboard renders but a tile shows `(no data)` | A specific chart's `mapping` could not bind to the dataset (compile-time, not refresh-time) | Read `compile_dashboard().diagnostics` (Section 11.2); the diagnostic carries the exact column / dataset that's missing |

When a refresh is broken: the user pastes the "Copy markdown for PRISM" report (12.3a) into PRISM and PRISM does the rest -- read the registry (`last_refresh_status`, `last_refreshed`), confirm `refresh_status.json` matches the snapshot, fix the failing script in `{DASHBOARD_PATH}/scripts/`, re-upload via `s3_manager.put`. **Do not rebuild from scratch** unless the scripts themselves are missing (in which case the modal will say `FileNotFoundError`).

### 12.6 Why the build IS the refresh smoke test

PRISM MUST be confident that when the user clicks [Refresh] tomorrow morning, the refresh will succeed. The Section 12.1 build flow guarantees that without a separate verification tool call.

Tool 1 and Tool 2 don't just author and persist scripts -- they each `s3_manager.get` the persisted script and `exec(compile(...))` it with the same namespace shape the refresh runner uses (Section 12.3). The build-time exec and the refresh-time exec are running the same bytes from the same S3 path with the same injected helpers. Three things follow:

1. **If the script would raise on tomorrow's cron, it raises during Tool 1 or Tool 2 today** -- missing column, NameError on a session-only variable PRISM forgot to inline, FileNotFoundError on a sibling artefact, schema drift between what `pull_data.py` writes and what `build.py` reads. PRISM sees the exception in the same `execute_analysis_script` invocation that authored the script, fixes the script string, and re-runs the tool until it succeeds.
2. **There is no "PRISM ran the logic in-session but persisted something different" failure mode.** The exec reads from S3, not from PRISM's session variables. If you've never typed the words "the script would do this" but then written something else into S3, the exec catches it.
3. **The refresh path is the only path.** Build-time and refresh-time are not two separate code paths that need to be kept in sync; they are the same path running on different schedules.

So: if Tool 1's verify lines print and Tool 2 ends with `[Tool 2] complete`, the dashboard's refresh pipeline is provably stable. Tool 3 registers, prints the portal URL, and the dashboard is shipped. There is no Tool 4.

**Anti-pattern (do not do this).** PRISM pulls data via `pull_market_data(...)` directly in the session, then composes a manifest, then calls `compile_dashboard(...)` directly in the session, then -- as an afterthought -- writes a `pull_data.py` and `build.py` string and `s3_manager.put`s them. Now the in-session execution and the on-S3 scripts are *two different things*, and only the in-session one has been exercised. The persisted scripts may compile cleanly but reference a session-only variable, write to a CSV name the build script doesn't read, or simply not exist. Any of those means the user sees the refresh error modal on their first [Refresh] click. The fix is structural: write the script first, exec it from S3, period.

**Optional: live-API verification.** When the Django half of the contract is part of what you want to verify (the `/api/dashboard/refresh/` endpoint, the runner subprocess spawn, the `dashboards_registry.json` lookup, the auth path), POST to `metadata.api_url` and poll `metadata.status_url` for up to ~90 s:

```python
import json, time, urllib.request

req = urllib.request.Request(
    metadata.get('api_url', '/api/dashboard/refresh/'),
    data=json.dumps({'kerberos': KERBEROS, 'dashboard_id': DASHBOARD_NAME}).encode(),
    headers={'Content-Type': 'application/json'}, method='POST',
)
with urllib.request.urlopen(req, timeout=10) as r:
    body = json.loads(r.read())

status_url = metadata.get('status_url', '/api/dashboard/refresh/status/')
for _ in range(30):  # ~90 s cap
    time.sleep(3)
    with urllib.request.urlopen(f"{status_url}?dashboard_id={DASHBOARD_NAME}") as r:
        st = json.loads(r.read())
    if st['status'] == 'success': break
    if st['status'] in ('error', 'partial'):
        raise RuntimeError(f'live-API smoke test failed: {st}')
```

This is the only way to verify the Django subprocess spawn and the registry-lookup-and-auth path exactly. It is OPTIONAL because the Django half is a stable PRISM deployment concern, not a per-dashboard build concern -- the in-tool exec-from-S3 pattern in 12.1 catches everything dashboard-specific. Add the live-API ping when you want extra paranoia, when you've changed something in the registry contract, or when you want to confirm the dashboard is reachable through the user-facing URL.

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
| Building a "persistent" dashboard whose `scripts/pull_data.py` and `scripts/build.py` aren't actually on S3 -- common silent failure where the dashboard ships fine but the [Refresh] button breaks 24h later | Tools 1 and 2 (Section 12.1) persist the scripts to `{DASHBOARD_PATH}/scripts/<name>.py` and then exec them FROM S3. The exec reads from S3, not from session variables, so missing-script bugs surface immediately during the build (a `NoSuchKey` / `FileNotFoundError` on `s3_manager.get`) rather than 24h later in the refresh modal |
| Pulling data in the ephemeral session via `pull_market_data(...)` and *then* writing a `pull_data.py` string to S3 that's supposed to do the same thing -- two separate code paths that may diverge silently | Section 12.1's pattern: write `pull_data.py` to S3 FIRST, then `s3_manager.get` it back and `exec` it. The script is the source of truth; the in-session execution is just running that exact script. There is no "the LLM did one thing, the script does another" failure mode possible |
| Calling `compile_dashboard(manifest)` directly in the session, then writing a `build.py` string that calls `compile_dashboard` again -- compiles twice, opens room for drift between the in-session manifest and the on-S3 build script | Section 12.1 Tool 2 pattern: derive the template once via `manifest_template(initial_manifest)`, write `build.py` to S3, exec build.py FROM S3. The compile happens exactly once -- inside the exec'd build.py -- using the on-S3 template + on-S3 CSVs. Refresh-time and build-time use the same code path |
| Inlining data pull + manifest build into a single tool call so neither `pull_data.py` nor `build.py` exist as standalone files | Three-tool-call build model is the contract (Section 12.1). Tool 1 persists + execs `pull_data.py` from S3 (writes CSVs); Tool 2 persists + execs `build.py` from S3 (writes manifest + html); Tool 3 registers. The CSV handoff between Tools 1 and 2 is what makes the refresh runner able to re-execute build.py independently |
| Saving `pull_data.py` / `build.py` to `SESSION_PATH/scripts/` instead of `{DASHBOARD_PATH}/scripts/` | Refresh runner only looks at `{DASHBOARD_PATH}/scripts/`. SESSION_PATH artefacts are gone the moment the conversation ends |
| Calling `pull_market_data` / `pull_haver_data` / `pull_plottool_data` / `pull_fred_data` inside `pull_data.py` WITHOUT `output_path=f'{SESSION_PATH}/data'` | Always pass `output_path` (Rule 5 of Section 0). Without it, the CSV lands in the per-source subfolder (`market_data/`, `haver/`, `plottool_data/`) and `build.py`'s read at `data/<name>.csv` raises `FileNotFoundError` on every refresh |
| Passing `name='rates_eod'` to `pull_market_data` (function appends another `_eod`, producing `data/rates_eod_eod.csv`) | Pass `name='rates'` (no suffix). `pull_market_data` ALWAYS appends `_eod` / `_intraday`. The same convention applies to the metadata sidecar -- `name='rates'` -> `data/rates_metadata.json` (one file across both modes). See Section 12.1a |
| Hand-rolling `s3_manager.put(df.to_csv().encode(), '...')` for FDIC / SEC EDGAR / BIS / Treasury / NY Fed / scraper output instead of `save_artifact()` | Use `save_artifact(data, name='...', output_path=f'{SESSION_PATH}/data')`. `save_artifact` is polymorphic (DataFrame -> CSV, dict -> JSON, list[dict] -> CSV), idempotent on re-run, and follows the same convention as the four pull primitives |
| Letting `manifest.datasets` keys NOT match the on-disk CSV stems (e.g. dataset key `'rates'` while the CSV is `data/rates_eod.csv`) | Make the dataset key the CSV stem: `'rates_eod'` for `data/rates_eod.csv`, `'rates_intraday'` for `data/rates_intraday.csv`, `'cpi'` for `data/cpi.csv`. `populate_template` looks up by exact key match |
| Using `pull_data.py` namespace names that the refresh runner does not inject (`save_artifact`, `fdic_client`, `sec_edgar_client`, `bis_client`, `treasury_client`, `nyfed_client`, `pull_nyfed_data`, etc.) and shipping the dashboard with `refresh_enabled: True` | Either restrict `pull_data.py` to the four pull primitives the runner knows (Section 12.1a's caveat), or set `metadata.refresh_enabled = False` until the runner namespace expands (tracked in `prism/_changelog.md` 2026-04-27) |

---

## 17. Pre-flight checklist

**Canonical layout (Rule 4, Section 0) -- every line MUST be verifiable on S3 before the dashboard ships. Run an `s3_manager.list()` on `{DASHBOARD_PATH}` and confirm each path concretely; do not assume the build flow wrote them:**

- `users/{kerberos}/dashboards/{name}/dashboard.html` -- compiled HTML (the file rendered to the user)
- `users/{kerberos}/dashboards/{name}/manifest.json` -- compiled manifest with embedded data (drives the dashboard's runtime state)
- `users/{kerberos}/dashboards/{name}/manifest_template.json` -- structural template, no data (read by `scripts/build.py` on every refresh)
- `users/{kerberos}/dashboards/{name}/scripts/pull_data.py` -- exact verbatim of Tool 1's script (refresh runner re-executes this; missing → `FileNotFoundError` in the modal)
- `users/{kerberos}/dashboards/{name}/scripts/build.py` -- exact verbatim of Tool 2's refresh-time script (~12 lines: load template, load CSVs, populate, compile, upload)
- `users/{kerberos}/dashboards/{name}/data/<dataset>.csv` -- one CSV per dataset, flat folder, written by `pull_data.py` via `output_path=f'{SESSION_PATH}/data'` (Rule 5), read back by `build.py`. Stem matches `manifest.datasets` key. For `pull_market_data` the on-disk stems carry the `_eod` / `_intraday` suffix the function auto-appends; pass `name='<base>'` so the suffix lands cleanly

`refresh_status.json` is **not** a build-time artefact -- the refresh runner writes it on the first refresh attempt, and the in-browser status check (Section 12.3) tolerates its absence (treated as "no prior refresh"). Do not pre-create it.

**Configuration:**

- `metadata.kerberos` + `dashboard_id` + `data_as_of` set; `refresh_frequency` set; `refresh_enabled` defaults to `True`
- Registry entry added to `users/{kerberos}/dashboards/dashboards_registry.json`; `update_user_manifest(kerberos, artifact_type='dashboard')` called

**Data integrity:**

- Every dataset traces to a real pull (Rule 1, Section 0); zero `np.random` / `np.linspace`-as-data / hand-typed arrays
- Every `pull_*_data(...)` call in `pull_data.py` passes `output_path=f'{SESSION_PATH}/data'` (Rule 5, Section 0); every `save_artifact(...)` call passes the same
- Every `pull_market_data` `name=` argument is the bare base (no `_eod` / `_intraday` suffix); the function appends them
- Every `manifest.datasets` key matches the on-disk CSV stem byte-for-byte (`rates_eod` for `data/rates_eod.csv`, `cpi` for `data/cpi.csv`, etc.)
- `pull_data.py` printed real shapes/heads/dtypes before `build.py` was authored; handles intraday failures defensively
- If `pull_data.py` uses `save_artifact` or any alt-data client, `metadata.refresh_enabled = False` until the runner namespace catches up (Section 12.1a caveat)
- Every dataset cleaned: `df.reset_index()` for DTI-keyed frames, plain English columns, no MultiIndex
- Every dataset backing a chart/table carries `field_provenance` (per-column `system` + `symbol`)
- Every dataset under budget: <50K rows, <2 MB; total manifest <5 MB
- Time-series pulls preserve full back-history (Section 19); never clip to "just the visible window"

**Build mechanics (Section 12.1):**

- Tool 1 authored `pull_data.py` as a string, `s3_manager.put`-ed it to `{DASHBOARD_PATH}/scripts/pull_data.py`, then `s3_manager.get`-ed it back and `exec`-ed it from S3 with the refresh-runner namespace -- the in-session pull happened *via* the persisted script, not before it
- Tool 1's `pull_data.py` lands every CSV in `{DASHBOARD_PATH}/data/` (Section 12.1a): `pull_*_data(..., output_path=f'{SESSION_PATH}/data')` for the four pull primitives, `save_artifact(..., output_path=f'{SESSION_PATH}/data')` for everything else
- Tool 1 read CSVs back from S3 and printed shapes/heads/dtypes against which Tool 2 then authored the manifest
- Tool 2 derived the template once (via `manifest_template(initial_manifest)`), authored `build.py` as a string, persisted it to `{DASHBOARD_PATH}/scripts/build.py`, then exec-ed it from S3 -- the compile happened *via* the persisted script, not directly via `compile_dashboard()` in the session
- `build.py` is thin (~12 lines: load template + load CSVs + `populate_template` + `compile_dashboard(..., write_html=False, write_json=False, strict=True)` + `s3_manager.put`)
- Both Tool 1 and Tool 2 ran cleanly to completion -- the build IS the refresh smoke test (Section 12.6); no separate verification step is required

**Hand-off:**

- Portal URL (`http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{name}/`) printed only after Tool 3 (registration) succeeds
- Download link delivered to the user

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

**Pull deep history. The defaults below are initial zoom windows, not data-layer caps.** Every time-series chart ships with a per-chart `dataZoom` slider (5.1) carrying the full dataset, and `dateRange` filters operate in view-mode by default (5) with selectable intervals (`1M/3M/6M/YTD/1Y/2Y/5Y/All`) -- but both reach back only as far as the data goes. If `pull_data.py` clips a 30-year FRED series to 2 years before persisting (or `build.py` slices / resamples / inner-joins it post-merge), those extra years are gone for good; the slider can't scroll into history that was never pulled. Loss of back-history at the PRISM data transformation layer is irreversible from the dashboard side. Pull the full series (or as far back as the source allows), keep transformations non-destructive on the time axis, and let the lookback below pick the *initial* visible window.

| Frequency | Initial zoom (default) | Rationale |
|-----------|------------------------|-----------|
| Quarterly/monthly | 10 years | Full business cycle |
| Weekly | 5 years | Trend + cycle |
| Daily | 2 years | Regime without noise |
| Intraday | 5 trading days | Event reaction window |

Override: if narrative references "highest since X", the chart's initial window must include X (data still extends back as far as the source allows). For pre-pandemic comparisons set initial start ≥ 2015. Don't open at 12 months of monthly (hides cycle), 30 years of daily (noise), or different ranges for charts meant to be compared.
