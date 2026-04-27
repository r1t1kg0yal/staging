# ECharts Dashboards

- **Module:** `dashboards`
- **Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
- **Tier:** 2 (on-demand)
- **Scope:** ALL dashboard construction in PRISM. (One-off PNG charts in chat / email / report use Altair `make_chart()`, a separate module.)

A dashboard is a JSON manifest. PRISM never writes HTML, CSS, or JS. PRISM emits structured JSON; the compiler does the rest.

One visual style only — Goldman Sachs brand: GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans, thin grey grid on paper-white. No theme switcher.

`compile_dashboard(manifest)` is the only PRISM-facing entry point. It validates a manifest, lowers each `widget: chart` through internal builders, and emits an interactive dashboard HTML + manifest JSON.

For refresh-pipeline operations / failure modal / runner internals see `prism/dashboard-refresh.md`. This file is purely about authoring.

---

## 0. Contract: five rules

All five absolute. A dashboard violating any of them is broken even if `dashboard.html` renders.

### Rule 1 — real data only

- Auto-saving primitives: `pull_market_data`, `pull_haver_data`, `pull_plottool_data`, `pull_fred_data`.
- Everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, Coalition, Inquiry, scraped DataFrames) lands via `save_artifact()` (§9.2).
- Forbidden: `np.random.*`, `np.linspace` / `np.arange` as data, hand-typed numeric arrays, synthetic fill for missing values, invented dates / labels.
- If no source exists, do not build the panel — add a data source first.

### Rule 2 — no literal data inside the manifest JSON

- Pass DataFrames; the compiler converts them to canonical on-disk shape.
- Three accepted dataset entry shapes (all normalised):

| Shape | When |
|-------|------|
| `datasets["rates"] = df` | Most common. Zero ceremony. |
| `datasets["rates"] = {"source": df}` | When attaching metadata to the entry. |
| `datasets["rates"] = {"source": df_to_source(df)}` | When the manifest is saved/read before the compiler touches it. |

### Rule 3 — order is non-negotiable

- `pull_data.py` must complete with real DataFrames (printed `df.shape` / `df.head()` / `df.dtypes`) before `build.py` is authored.
- Write the manifest against verified shapes, not imagined columns.
- Inheriting a non-compliant dashboard (bypasses `compile_dashboard()`, hand-writes HTML/CSS/JS, types numbers into `datasets[*].source`, skips persistence) → bringing it back to spec takes priority over whatever surface change was originally asked for. Surface the trade transparently.

### Rule 4 — canonical layout, scripts on disk

- Every persistent user dashboard lands at `users/{kerberos}/dashboards/{name}/` with the full artefact set in §2.2.
- Required: `dashboard.html`, `manifest.json`, `manifest_template.json`, `scripts/pull_data.py`, `scripts/build.py`, raw CSVs in `data/`.
- The two `.py` files under `scripts/` are exactly what the refresh runner re-executes on schedule.
- Missing scripts → the [Refresh] button fails immediately with `FileNotFoundError`.

### Rule 5 — every CSV at `{DASHBOARD_PATH}/data/<dataset>.csv`

- Inside `pull_data.py`, every pull-function call AND every `save_artifact(...)` MUST pass `output_path=f'{SESSION_PATH}/data'`.
- The refresh runner injects `SESSION_PATH = {DASHBOARD_PATH}` so the same string resolves identically at build time and refresh time.
- Without `output_path`, CSVs land in per-source subfolders (`market_data/`, `haver/`, `plottool_data/`) — `build.py` does not look there → refresh fails.
- `pull_market_data` ALWAYS appends `_eod` / `_intraday` to the filename. Pass `name='rates'` → `data/rates_eod.csv`. Use `'rates_eod'` as the manifest dataset key. Pass `name='rates_eod'` → broken `data/rates_eod_eod.csv`.
- The dataset key in `manifest.datasets` matches the on-disk CSV stem byte-for-byte. §9.2 has the per-source pattern.

### The build flow IS the refresh path

PRISM authors each script as a Python string, persists to S3, then execs from S3 with the refresh-runner namespace. Build-time and refresh-time run the same bytes from the same path. No drift, no double work, no separate verification step.

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

---

## 1. Injected namespace

Inside `execute_analysis_script`:

```python
compile_dashboard       # manifest -> interactive HTML + manifest JSON (+ optional PNGs)
manifest_template       # strip data from a manifest -> reusable template
populate_template       # template + fresh DataFrames -> ready-to-compile manifest
validate_manifest       # dry-run validation without rendering
chart_data_diagnostics  # check data wires up (missing columns, size limits, etc.)
load_manifest           # path -> manifest dict (used by refresh)
save_manifest           # manifest -> JSON file
df_to_source            # DataFrame -> canonical row-of-lists source form
```

`compile_dashboard()` raises by default (`strict=True`) on any error-severity diagnostic; `strict=False` keeps going so PRISM gets a single round-trip list of fixes. One theme (`gs_clean`); three palettes (`gs_primary`, `gs_blues`, `gs_diverging`).

---

## 2. Manifest

### 2.1 Shape

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
| `metadata` | Provenance + refresh block (§2.3) |
| `header_actions` | Custom header buttons (§8) |
| `datasets` | `{name: DataFrame \| {"source": ...}}` |
| `filters` / `layout` / `links` | §5 / §7 / §6 |

### 2.2 Folder structure

For **conversational (session-only)** dashboards:

```
{SESSION_PATH}/dashboards/{id}.json     compiled manifest
{SESSION_PATH}/dashboards/{id}.html     compiled dashboard
```

For **persistent user dashboards** (Rule 4) — every artefact tagged `[REQUIRED]` must be present on S3 by the end of the build:

```
users/{kerberos}/dashboards/{dashboard_name}/
  manifest_template.json    [REQUIRED] LLM-editable spec, NO data
  manifest.json             [REQUIRED] template + fresh data, embedded
  dashboard.html            [REQUIRED] compile_dashboard output
  refresh_status.json       runtime state (status, errors[], pid, auto_healed)
  thumbnail.png             optional
  scripts/                  [REQUIRED]
    pull_data.py            [REQUIRED] data acquisition (~50-150 lines)
    build.py                [REQUIRED] ~12 lines: load + populate + compile
  data/                     [REQUIRED] populated by pull_data.py via output_path=f'{SESSION_PATH}/data'
    rates_eod.csv           one CSV per dataset; stem matches manifest key
    rates_intraday.csv      pull_market_data appends _eod / _intraday
    rates_metadata.json     pull_market_data sidecar uses the bare name
    cpi.csv                 pull_haver_data: no suffix
    cpi_metadata.json
    swap_curve.csv          pull_plottool_data: no suffix
    fdic_gs_bank.csv        save_artifact: no suffix
  history/                  optional snapshots when keep_history=true
```

**Why every required artefact has to be there.** The refresh runner has no PRISM state and no conversation memory — it re-executes the persisted scripts on a schedule. Missing `scripts/*.py` → runner has nothing to call. Missing `manifest_template.json` → `build.py` can't load the template. Missing `data/*.csv` → `build.py` can't read what `pull_data.py` was supposed to write.

**Forbidden:**

- HTML / CSS / JS in any `.py` file (`rendering.py` owns it)
- `scripts/build_dashboard.py` (renamed to `build.py`)
- Per-source folders (`haver/`, `market_data/` — everything goes to `data/`)
- Timestamped scripts (`20260424_*.py`)
- Session-only artifacts at dashboard scope (`*_results.md`, `*_artifacts.json`)
- Multiple data JSONs (only `manifest.json`)
- Inline `<script>const DATA = {}` in HTML
- Legacy helpers (`sanitize_html_booleans()`)
- A "persistent" dashboard whose `scripts/` folder is empty

### 2.3 Metadata block

Drives the data-freshness badge, methodology popup, summary banner, and refresh button. All fields optional — omit for session artifacts, set for persistent dashboards.

| Field | Type | Purpose |
|-------|------|---------|
| `kerberos` / `dashboard_id` | str | Required for refresh button (`dashboard_id` defaults to `manifest.id`) |
| `data_as_of` / `generated_at` | str (ISO) | Header badge `Data as of YYYY-MM-DD HH:MM:SS UTC`; compile-time fallback |
| `sources` | list[str] | Source names (`["GS Market Data", "Haver"]`) |
| `summary` | str \| `{title, body}` | Always-visible markdown banner above row 1 (today's read) |
| `methodology` | str \| `{title, body}` | Click-to-open markdown popup (header button) |
| `refresh_frequency` / `refresh_enabled` | str / bool | `hourly` / `daily` / `weekly` / `manual`; `False` hides refresh button |
| `tags` / `version` | list[str] / str | Echoed into the registry; manifest version string |
| `api_url` / `status_url` | str | Refresh / status endpoint overrides |

`summary` and `methodology` accept the shared markdown grammar (§4.9). `summary` is always-visible above row 1 (today's read); `methodology` is click-to-open via the header button (how the data is constructed).

```python
metadata = {
    "data_as_of": "2026-04-24T15:00:00Z",
    "methodology": "## Sources\n* US Treasury OTR yields (FRED H.15)\n## Construction\n"
                    "* 2s10s, 5s30s = simple cash differences in bp",
    "summary": {"title": "Today's read",
                 "body": "Front-end has richened ~6bp on a softer print. Curve "
                          "**bull-steepened**, 2s10s out of inversion."},
}
```

**Standard top-right protocol** (left-to-right, each auto-shows when its enabling config is present):

| # | Element | Visible when |
|---|---------|--------------|
| 1 | `Data as of <ts>` | `metadata.data_as_of` or `generated_at` set |
| 2 | `Methodology` | `metadata.methodology` set |
| 3 | `Refresh` | `metadata.kerberos` + `dashboard_id` set, `refresh_enabled != False` |
| 4 | `Download Charts` | always (one PNG per `widget: chart`) |
| 5 | `Download Panel` | always (full view as single PNG) |
| 6 | `Download Excel` | dashboard has at least one `widget: table` |

`header_actions[]` (§8) injects custom buttons in front of this bar.

### 2.4 `compile_dashboard` parameters

| Parameter | Purpose |
|-----------|---------|
| `manifest` | Dict, JSON string, or path to manifest JSON |
| `session_path` | Writes `{sp}/dashboards/{id}.json` + `{id}.html` |
| `output_path` | Explicit HTML path; the `.json` is written alongside |
| `base_dir` | Resolves `widget.ref` paths (defaults: arg, manifest's parent, cwd) |
| `write_html` / `write_json` | Default `True`. `False` in sandbox so PRISM writes via `s3_manager.put()` |
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

### 3.1 Chart-type catalog (30)

| chart_type | Required mapping keys |
|------------|------------------------|
| `line` | `x`, `y`, optional `color` |
| `multi_line` | `x`, `y` (list) OR `x`, `y`, `color` |
| `bar` | `x` (category), `y`, optional `color`, `stack` (bool) |
| `bar_horizontal` | `x` (value), `y` (category), optional `color`, `stack` |
| `scatter` | `x`, `y`, optional `color`, `size`, `trendline` |
| `scatter_multi` | `x`, `y`, `color`, optional `trendlines` |
| `scatter_studio` | none required; author-supplied whitelists drive runtime picker (§3.5) |
| `area` | `x`, `y` (stacked area) |
| `heatmap` | `x`, `y`, `value` |
| `correlation_matrix` | `columns` (≥2 numeric), optional `transform`, `method`, `order_by` (§3.6) |
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
| `marimekko` | `x` (col-axis cat), `y` (row-axis cat), `value`, optional `order_x`, `order_y` |
| `raw` | pass `option=...` directly (passthrough) |

Unknown `chart_type` raises `ValueError`. Datetime cols auto-resolve to `xAxis.type='time'`; numeric to `'value'`; everything else to `'category'`. Missing columns raise `ValueError` listing actual DataFrame columns — no silent fallback.

**Finance-flavoured shapes:**

| Type | What it draws | Example uses |
|------|---------------|--------------|
| `waterfall` | Incremental deltas (green +, red −), full-height bar when `is_total` | P&L bridges, attribution, factor decomp |
| `slope` | N categories at two snapshots joined by sloped lines + right-edge labels | "month-end vs latest", "before vs after" |
| `fan_cone` | Central path + N stacked confidence bands, opacity declines outside-in | FOMC dot-plot fans, scenario cones |
| `marimekko` | 2D categorical proportions: x-col widths = share of total; y-cats stack proportionally | Cap-weighted allocation by sector × size |

### 3.2 Mapping keys (XY chart types)

| Key | Purpose |
|-----|---------|
| `x`, `y` | Required. `y` can be a list (wide-form multi_line) |
| `color` | Grouping column (multi-series long form) |
| `y_title` / `x_title` / `y_title_right` | Plain-English axis titles. Right-axis title for dual-axis |
| `x_sort` | Explicit category order (list of values) |
| `x_type` | Force `'category'` / `'value'` / `'time'` on ambiguous columns |
| `invert_y` / `y_log` / `x_log` | Invert single-axis y; log scale on respective axis |
| `stack` (bar) | `True` (default) = stacked, `False` = grouped |
| `dual_axis_series` / `invert_right_axis` | Right-axis series list; flip right axis (rates "up = bullish") |
| `axes` | List of axis spec dicts for N-axis time series. Takes precedence over the legacy 2-axis API |
| `strokeDash` / `strokeDashScale` / `strokeDashLegend` | Column controlling per-series dash pattern; `{"domain": [...], "range": [[1,0], [8,3]]}` explicit mapping; legend cross-product |
| `trendline` / `trendlines` (scatter) | `True` adds overall / per-group OLS line |
| `size` (scatter) | Column driving marker size |
| `bins` / `density` (histogram) | Int or list of bin edges (default 20); `True` normalises counts to density |

**Chart-specific shapes:**

| Chart | Mapping keys |
|-------|--------------|
| `sankey` / `graph` | `source`, `target`, `value`; `graph` adds `node_category` |
| `treemap` / `sunburst` | `path` + `value`, OR `name` + `parent` + `value` |
| `candlestick` | `x`, `open`, `close`, `low`, `high` |
| `radar` | `category`, `value`, optional `series` |
| `gauge` | `value`, optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`, optional `year` |
| `parallel_coords` | `dims` (list), optional `color` |
| `tree` | `name`, `parent` |

**Heatmap-style** (`heatmap`, `correlation_matrix`, `calendar_heatmap`) cell-label / color keys: `show_values`, `value_decimals` (auto, clamped to global cap §3.3), `value_formatter` (raw JS — suppresses auto-contrast + cap), `value_label_color` (`"auto"` / hex / `False`), `value_label_size` (default 11), `colors` / `color_palette`, `color_scale` (`sequential` / `diverging` / `auto`), `value_min` / `value_max` (pin visualMap range across reruns).

**Multi-axis time series (`mapping.axes`).** Line / multi_line / area accept arbitrary independent y-axes:

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

Per-axis keys: `side` (`left`/`right`, req), `title`, `series`, `invert`, `log`, `min`/`max`, `format` (`percent`/`bp`/`usd`/`compact` or raw JS string), `offset` (auto-stacked at 0, 80, 160, …), `scale` (default `True`), `color` (auto-tints to series' palette color for single-series axes, Bloomberg-style). Mapping-level: `axis_offset_step` (default 80), `axis_color_coding` (default `True`). Annotations target an axis via `axis: <index>` (0..N-1).

When to use: 2 axes → prefer `dual_axis_series`; 3+ across asset classes → `axes`; 3+ same unit → one axis right; 3+ different units comparing patterns → consider Index=100 normalisation instead.

### 3.3 Cosmetic / layout knobs (every chart type)

| Key | Purpose |
|-----|---------|
| `legend_position` / `legend_show` | `"top"` (default), `"bottom"`, `"left"`, `"right"`, `"none"`; explicit `True`/`False` override |
| `series_labels` / `humanize` | `{raw_name: display_name}` overrides auto-humanise; `humanize: False` disables `us_10y` → `US 10Y` |
| `x_date_format` | `"auto"` for compact `MMM D`; raw JS string for custom |
| `show_slice_labels` (pie/donut) | Keep per-slice edge labels even with top/bottom legend |
| `y_min` / `y_max` / `x_min` / `x_max` | Force axis range |
| `y_format` / `x_format` | `"percent"` / `"bp"` / `"usd"` / `"compact"` (K/M/B) or raw JS |
| `y_title_gap` / `x_title_gap` / `y_title_right_gap` | Pixels between tick labels and axis title (auto-sized by default) |
| `category_label_max_px` | Max pixel width for category-axis tick labels (default 220); longer get ellipsis |
| `grid_padding` | `{top, right, bottom, left}` overriding plot-area margins |
| `show_grid` / `show_axis_line` / `show_axis_ticks` | `False` to suppress |
| `series_colors` | `{col_name: "#hex"}` overrides palette for specific series (raw or post-humanise name) |
| `tooltip` | `{"trigger": "axis"\|"item"\|"none", "decimals": 2, "formatter": "<JS fn>", "show": False}` |

The compiler truncates long category labels to `category_label_max_px`, sizes `nameGap` from real label widths, bumps `grid.left` / `grid.bottom` for rotated axis names, auto-rotates vertical-bar / boxplot x-labels when crowded, and bumps heatmap `grid.right` to 76px for visualMap clearance.

**Per-spec overrides.** `palette`, `theme`, `annotations` may live on `spec` to override manifest defaults. Required keys: `chart_type`, `dataset`, `mapping`. Titles / subtitles live at the widget level only — `spec.title` / `spec.subtitle` are rejected by the validator.

**Global decimal cap.** Every numeric value rendered anywhere — value-axis tick labels, tooltips, KPI tiles, table cells, heatmap labels, correlation coefficients, regression statistics, "View raw data" modal — is hard-capped at 2 decimal places. Author-supplied precision options (`value_decimals`, `decimals`, `delta_decimals`, `tooltip.decimals`, table `"number:5"`) silently coerce down to the cap. Author-supplied raw JS function strings (`value_formatter`, `tooltip.formatter`, `axisLabel.formatter`) are NOT inspected. The cap is `config.MAX_DASHBOARD_DECIMALS`.

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

Common keys: `label`, `color`, `style` (`'solid'|'dashed'|'dotted'`), `stroke_dash` (`[4,4]`), `stroke_width`, `label_color`, `label_position`, `opacity` (band), `head_size` / `head_type` (arrow), `font_size` (point). `band` accepts `y1`/`y2` (horizontal band) and aliases `x_start`/`x_end`, `y_start`/`y_end`. Dual-axis: `hline` accepts `"axis": "right"`. Charts without axes (pie / donut / sankey / treemap / sunburst / radar / gauge / funnel / parallel_coords / tree) silently ignore annotations.

Annotate regime changes, policy shifts, event dates, structural breaks. Don't annotate self-evident facts (zero line on a spread, target on every CPI chart).

### 3.5 `scatter_studio` — exploratory bivariate

Use when the analyst should pick X / Y / color / size / per-axis transform / regression interactively. Author whitelists columns; regression line, R², p-value, window slicer wired automatically.

| Mapping key | Purpose |
|-------------|---------|
| `x_columns` / `y_columns` / `color_columns` / `size_columns` | Whitelisted numeric / categorical columns. Default: every numeric col for X/Y, empty for color/size |
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
| `show_stats` | `True`. Stats strip below canvas: `n`, Pearson `r`, `R²`, slope `beta` (SE), intercept `alpha`, RMSE, p-value |

Per-axis transforms: `raw`, `log` (drops non-positive), `change`, `pct_change`, `yoy_change`, `yoy_pct`, `zscore`, `rolling_zscore_<N>`, `rank_pct`, `index100`. Order-aware (`change`, `pct_change`, `yoy_*`, `rolling_zscore_*`) require `order_by`.

Stats strip example: `n=247  r=0.68***  R²=0.46  beta=0.42 (SE 0.03)  alpha=1.18  RMSE=0.31  p=4.2e-9`. Stars: `***` p<0.001 / `**` p<0.01 / `*` p<0.05 / `·` p<0.10. With `regression: ols_per_group` the strip lists per-color stats below the overall row. Edge cases: `n<2` → unavailable; zero X-variance suppresses the line; `log` drops negatives; filter narrowing recomputes against the filtered subset.

### 3.6 `correlation_matrix` — N×N heatmap from a column list

"How do these N series co-move?" Builder applies a per-column transform, computes the correlation matrix, emits a diverging heatmap pinned to `[-1, 1]`.

| Mapping key | Purpose |
|-------------|---------|
| `columns` (req) | Numeric column names, length ≥ 2 |
| `method` | `'pearson'` (default) or `'spearman'` (rank correlation; robust to monotonic non-linearity) |
| `transform` | Per-column transform before correlation (default `'raw'`; same names as scatter_studio) |
| `order_by` | Required when `transform` is order-aware. Default: first datetime-like col |
| `min_periods` | Min overlapping non-null pairs to report (default 5); below threshold renders blank |
| `show_values` / `value_decimals` | Print correlation in cell (default `True` / `2`; clamped to global cap) |
| `value_label_color` | `"auto"` (B/W contrast), hex, or `False` |
| `colors` / `color_palette` | Override palette (default `gs_diverging`) |

Cell tooltip prints `<row name> × <col name>: r=0.xx`. Diagonal is always `1.0`. Use `correlation_matrix` for wide-form time-series panels (author gives columns; builder does math + visualMap). Use `heatmap` for pre-computed bivariate cells (cross-asset returns by month, hit-rate by quintile).

### 3.7 Computed columns (manifest-level expressions)

A dataset entry can declare a `compute` block of named expressions evaluated against an existing source dataset. Use this instead of computing spreads / ratios / z-scores in `build.py`. The compiler runs an AST-level whitelist (no `eval`, no `__import__`, no attribute access), materialises each output column, and auto-stamps `field_provenance` with `system: "computed"`, the recipe string, and the upstream column list.

```python
"datasets": {
    "rates": df_rates,
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

| Group | Functions |
|-------|-----------|
| Arithmetic | `+ - * / % ** //`, unary `+ -` |
| Numeric | `log`, `log10`, `log2`, `exp`, `sqrt`, `abs`, `sign`, `round` |
| Aggregate | `mean`, `std`, `min`, `max`, `sum` (broadcast scalar) |
| Series | `zscore(x, window?)`, `rolling_mean(x, n)`, `rolling_std(x, n)`, `pct_change(x, periods?)`, `diff(x, periods?)`, `shift(x, periods?)`, `clip(x, lo?, hi?)`, `index100(x)`, `rank_pct(x)` |

Column names referenced in expressions must start with letter or underscore (no digits, no spaces / dots / dashes). Inferred units: `* 100` on percent inputs → `bp`; `zscore(...)` → `z`; `pct_change(...)` / `yoy_pct(...)` / `index100(...)` → `percent`; otherwise inherit when every referenced column shares units.

The popup Sources footer on any chart point surfaces the recipe directly.

---

## 4. Widgets

### 4.1 Catalog + presentation knobs

| Widget | Required | Purpose |
|--------|----------|---------|
| `chart` | `id`, one of `spec` / `ref` / `option` | ECharts canvas tile |
| `kpi` | `id`, `label` | Big-number tile + delta + sparkline |
| `table` | `id`, `ref` or `dataset_ref` | Rich table with sort / search / format / popup |
| `pivot` | `id`, `dataset_ref`, `row_dim_columns`, `col_dim_columns`, `value_columns` | Crosstab with row/col/value/agg dropdowns (§4.6) |
| `stat_grid` | `id`, `stats[]` | Dense grid of label/value stats |
| `image` | `id`, `src` or `url` | Embed static image or logo |
| `markdown` | `id`, `content` | Freeform markdown block (transparent) |
| `note` | `id`, `body` | Semantic callout: tinted card, colored left-edge stripe by `kind` |
| `divider` | `id` | Horizontal rule, forces row break |

Common optional fields: `w` (1-12 grid span), `h_px` (chart only; default 280), `title`, `show_when` (§4.10).

**Widget presentation knobs** (every tile type):

| Field | Purpose |
|-------|---------|
| `title` / `subtitle` | Card header at widget level (never in `spec`). Italic secondary line. PNG export bakes title in |
| `footer` (alias `footnote`) | Small text below tile body, dashed-border separator. Source attribution |
| `info` / `popup` | Short help (info icon: hover tooltip + click modal). `popup: {title, body}` markdown overrides modal content |
| `badge` / `badge_color` | Short pill (1-6 chars) next to title; color ∈ `"gs-navy"` (default) / `"sky"` / `"pos"` / `"neg"` / `"muted"` |
| `emphasis` / `pinned` | Thicker navy border + shadow (KPIs: sky-blue top border) / sticky to viewport top |
| `action_buttons` | List of toolbar buttons: `{label, icon?, href?, onclick?, primary?, title?}` |
| `click_emit_filter` (chart) | Data-point clicks → filter changes (§5.4) |
| `click_popup` (chart) | Data-point clicks → per-row detail popup. Same grammar as table `row_click` (§4.3) |

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

### 4.2 KPI

**Source path syntax.** `source` (and `delta_source`) use `<dataset>.<aggregator>.<column>`. `sparkline_source` drops the aggregator: `<dataset>.<column>`. Aggregators: `latest` / `first` / `sum` / `mean` / `min` / `max` / `count` / `prev`.

For time-series datasets:
- `rates.latest.us_10y` — last numeric value
- `rates.prev.us_10y` — second-to-last (drives delta vs prev)

For categorical / summary datasets, source paths still work but the aggregator collapses N rows to one — rarely what you want. Either pivot to a single-row "latest" snapshot, or skip `source` and pass `value` directly:

```python
{"widget": "kpi", "id": "kpi_aapl", "label": "AAPL NTM EPS", "value": 8.98, "w": 3}
```

| Key | Purpose |
|-----|---------|
| `value` / `source` | Direct override; or dotted `<dataset>.<agg>.<column>` |
| `sub` | Subtext under the value |
| `delta` / `delta_source` / `delta_pct` | Direct delta or dotted source (delta = current − prev); `delta_pct` auto-computed from `delta_source` if absent |
| `delta_label` / `delta_decimals` | Label after delta / precision (default 2; clamped to global cap) |
| `prefix` / `suffix` / `decimals` | Prepended / appended (`$`, `%`, `bp`); precision (default 2 for <1000, else 0; clamped) |
| `sparkline_source` | Dotted: `<dataset>.<column>` for inline sparkline (no aggregator) |
| `format` | `"auto"` (default; `2820` → `2,820`), `"compact"` (K/M/B/T), `"comma"`, `"percent"`, `"raw"` |

```json
{"widget": "kpi", "id": "k10y", "label": "10Y", "w": 3,
  "source": "rates.latest.us_10y", "suffix": "%",
  "delta_source": "rates.prev.us_10y", "delta_label": "vs prev",
  "sparkline_source": "rates.us_10y"}
```

### 4.3 Table

Pass `dataset_ref` and the table renders every column by default. For production dashboards, declare `columns[]` for per-column labels, formatters, tooltips, conditional formatting, color scales, plus search / sort / row-click popups.

```json
{"widget": "table", "id": "rv_table", "w": 12, "dataset_ref": "rv",
  "title": "RV screen (click a row for detail)",
  "searchable": true, "sortable": true,
  "max_rows": 50, "row_height": "compact",
  "empty_message": "No metrics match the current filters.",
  "columns": [
    {"field": "metric", "label": "Metric", "align": "left"},
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
| `format` | `text` / `number[:d]` / `integer` / `percent[:d]` / `currency[:d]` / `bps[:d]` / `signed[:d]` / `delta[:d]` / `date` / `datetime` / `link`. The `:d` suffix is clamped to the global cap |
| `align` / `sortable` / `tooltip` | `left` / `center` / `right` (auto-right for numeric); defaults to table-level; hover text |
| `conditional` | First-match-wins rules: `{op, value, background?, color?, bold?}` (op from filter ops set) |
| `color_scale` | Continuous heatmap: `{min, max, palette}` (`gs_diverging` / `gs_blues`) |
| `in_cell` | `"bar"` (proportional bar inside cell, anchored at zero when col crosses zero) or `"sparkline"` (inline 80×16 SVG, requires `from_dataset` + `row_key` + `filter_field`; optional `value`, `show_text: false`) |

**Table-level fields:** `searchable`, `sortable`, `downloadable` (XLSX button; default `true`), `row_height` (`compact` / default), `max_rows` (default 100), `empty_message`.

**Row-level highlighting** (`row_highlight`): list of rules evaluated per row; first match wins. `{field, op, value, class}` where `op` ∈ `==, !=, >, >=, <, <=, contains, startsWith, endsWith` and `class` ∈ `"pos"` / `"neg"` / `"warn"` / `"info"` / `"muted"`. Row gets tinted background + left-edge accent.

#### `row_click` and chart `click_popup` — same grammar

Two modes: simple (key/value table) or rich drill-down (mini-dashboard inside the modal).

*Simple:*

```json
"row_click": {"title_field": "ticker", "popup_fields": ["ticker", "sector", "last", "d1_pct"]}
```

*Rich drill-down* — modal widens to 880px when `detail.wide: True`:

```json
"row_click": {
  "title_field": "issuer",
  "subtitle_template": "CUSIP {cusip} - {coupon_pct:number:2}% coupon - matures {maturity}",
  "detail": {"wide": true, "sections": [
    {"type": "stats", "fields": [
      {"field": "price", "label": "Price", "format": "number:2"},
      {"field": "ytm_pct", "label": "YTM", "format": "number:2", "suffix": "%"}]},
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
| `markdown` | Paragraph with `{field}` / `{field:format}` template substitution. Full markdown grammar (§4.9) |
| `chart` | Embedded mini-chart. `chart_type` ∈ `line` / `bar` / `area`; dataset + `filter_field` / `row_key` to scope. Supports `mapping.y` (col or list), `annotations`, numeric `height` |
| `table` | Sub-table from filtered manifest dataset. `max_rows` caps length |
| `kv` / `kv_table` | Key/value table for subset of `row` fields |

Template substitution `{field:format}` matches column formats (`number:N`, `signed:N`, `percent:N`, `currency:N`, `bps:N`, `delta:N`, `date`). Unknown fields pass through.

**Chart `click_popup`** uses identical grammar. Click any point in scatter / line / bar / area / candlestick / bullet / pie / donut / funnel / treemap / sunburst / heatmap / calendar_heatmap → corresponding row opens in the same modal grammar.

**Row resolution** (chart click → dataset row):

| Chart type | params → row |
|------------|--------------|
| line / multi_line / area / bar / bar_horizontal / scatter / scatter_multi / candlestick / bullet | `rows[dataIndex]` of (filter-stripped) dataset; with `mapping.color`, filter by `color_col == params.seriesName` first |
| pie / donut / funnel / treemap / sunburst | match `mapping.category` / `mapping.name` cell `== params.name` |
| heatmap / calendar_heatmap | reconstruct unique x/y categories and match pair / match `mapping.date` cell `== params.value[0]` |
| histogram / radar / gauge / sankey / graph / tree / parallel_coords / boxplot | not row-resolvable; click is a no-op |

### 4.4 Provenance

Every line / bar / point / row / cell carries the upstream identifier plus source system. The compiler does NOT introspect `df.attrs`; PRISM cleans upstream metadata into the canonical shape and passes it explicitly. Vendor-agnostic — the renderer treats `system` as opaque, so adding a new data source is one PRISM-side adapter (~10 lines), no echarts code change.

**The contract:** attach `field_provenance` (and optionally `row_provenance_field` + `row_provenance` for mixed-vendor columns) alongside `source`.

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

**Per-column keys** (`system` and `symbol` always populate; rest optional, all free-form strings):

| Key | Purpose |
|-----|---------|
| `system` | Source slug: `haver`, `market_data`, `plottool`, `fred`, `bloomberg`, `refinitiv`, `factset`, `csv`, `computed`, `manual`, or any string PRISM picks for a new vendor. Renderer treats as opaque |
| `symbol` | Universal primary identifier — pass the exact upstream string (`GDP@USECON`, `IR_USD_Treasury_10Y_Rate`, `DGS10`, `USGG10YR Index`, `AAPL-US.GAAP.EPS_DILUTED`) |
| `display_name` / `units` / `source_label` | Human-readable footer label; `percent` / `bp` / etc.; vendor attribution |
| `recipe` / `computed_from` | For `system: "computed"`: free-form formula + list of source columns referenced |
| `as_of` | ISO timestamp of latest tick at column level |
| `<vendor_alt>` | System-specific alternate id: `haver_code`, `tsdb_symbol`, `fred_series`, `bloomberg_ticker`, `refinitiv_ric`, `factset_id` |

**Mixed-vendor columns** (one column, different upstream per row) override per row via `row_provenance_field` + `row_provenance`:

```python
{"source": df_screener,
 "field_provenance": {"last": {"system": "market_data", "source_label": "GS Market Data"}},
 "row_provenance_field": "ticker",
 "row_provenance": {
    "AAPL": {"last": {"system": "market_data", "symbol": "EQ_US_AAPL_Last"}},
    "TSLA": {"last": {"system": "bloomberg", "symbol": "TSLA US Equity"}}}}
```

**Where it surfaces:** auto-default popup when `field_provenance` is set but no `click_popup` / `row_click` declared (minimal modal + Sources footer); Sources footer auto-appended to every explicit popup (suppress per popup with `show_provenance: false`); inline source line under `detail.sections[type=stats]` via `show_source: true`. Opt-out per widget: `click_popup: false` / `row_click: false`.

PRISM rule: every dataset backing a chart or table carries `field_provenance`.

### 4.5 stat_grid

Dense grid of label / value stats — for when a row of KPIs would take too much vertical space.

```json
{"widget": "stat_grid", "id": "summary", "w": 12, "title": "Risk summary",
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

### 4.6 Pivot

Long-form dataset → interactive crosstab. Viewer picks row dim, col dim, value column, aggregator from author-supplied whitelists.

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
| `row_default` / `col_default` / `value_default` / `agg_default` / `decimals` | no | Initial selections; cell precision (default 2; clamped) |
| `color_scale` / `show_totals` | no | `"sequential"` / `"diverging"` / `"auto"` (diverging when crosses 0) / `false`; row/col totals (recomputed, not summed; default `True`) |

Filters targeting `dataset_ref` flow through naturally. User's last selections survive URL state encoding (`#p.<id>.r=...&p.<id>.c=...`).

### 4.7 image / markdown / divider

```json
{"widget": "image", "id": "logo", "w": 3,
  "src": "https://.../gs_logo.png", "alt": "Goldman Sachs", "link": "https://..."}

{"widget": "markdown", "id": "md", "w": 12,
  "content": "### Method\nSynthetic UST panel. **Brush** the curve to cross-filter."}

{"widget": "divider", "id": "sep"}
```

### 4.8 Note (semantic callout)

Tinted card with colored left-edge stripe keyed by `kind`. Use when a paragraph is load-bearing — the thesis, the risk, the watch level.

Required: `id`, `body` (markdown). Optional: `kind` (default `insight`) / `title` / `icon` (1-2 char glyph) / `w` (default 12) / `footer` / `popup` / `info`.

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

### 4.9 Markdown grammar (shared)

Same grammar applies to: `widget: markdown`, `widget: note` body, `metadata.summary`, `metadata.methodology`, `popup: {body}` on any tile / filter / stat, per-row `markdown` sections (§4.3). Tab `subtitle` / `description` is plain text, not markdown.

| Block | Syntax |
|-------|--------|
| Headings | `# H1` … `##### H5` (deeper clamped to h5) |
| Paragraph | Lines separated by blank line; lines within a para joined with single space |
| Unordered / ordered list | `-` or `*` (UL); `1.` / `2.` / … (OL; numbers don't have to be sequential) |
| Nested list | Indent by **2 spaces** per level. Mix `ul`/`ol` freely |
| Blockquote / code block | `> ...` (multi-line accumulates) / triple-backtick fenced (optional language tag) |
| Table | GFM: header row, separator `\| --- \| --- \|`, body rows. Alignment hints `:---` / `---:` / `:---:` |
| Horizontal rule | A line containing only `---`, `***`, or `___` |
| Inline | `**bold**` / `*italic*` / `~~strike~~` / `` `code` `` / `[label](url)` (opens in new tab) |

Anything that does not match is escaped as plain text — including raw HTML.

### 4.10 show_when, initial_state, stat strip

#### `show_when` — conditional widget visibility

A widget can declare `show_when`; if it fails the widget is removed (compile-time data conditions) or hidden via CSS (runtime filter conditions).

- **Data condition** (compile-time) — `{"data": "<dotted_source> <op> <value>"}`. Source uses KPI dotted shape (`dataset.aggregator.column`); ops: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`. Widget removed from layout when condition fails.
- **Filter condition** (runtime) — `{"filter": "<filter_id>", "value": <v>}`, `{"filter": "<filter_id>", "in": [<v>, ...]}`, or `{"filter": "<filter_id>", "op": ">", "value": 25}`. JS toggles widget visibility on filter change.
- **Compound** — `{"all": [...]}` (AND), `{"any": [...]}` (OR). Mix data and filter clauses freely; compile-time pass evaluates only data sub-conditions.

```python
{"widget": "note", "id": "vol_warning", "kind": "risk",
  "body": "Vol regime elevated; tighten stops...",
  "show_when": {"data": "rates.latest.vix > 25"}}              # compile-time

{"widget": "chart", "id": "fed_path",
  "show_when": {"filter": "scope", "value": "domestic"}}        # runtime

{"widget": "pivot", "id": "global_pivot",
  "show_when": {"all": [{"data": "market.latest.vix < 30"},
                          {"filter": "scope", "in": ["us", "eu"]}]}}
```

#### `initial_state` — seed the controls drawer

Every chart / table / KPI carries a controls drawer. `initial_state` seeds it so a chart opens in YoY % instead of raw levels (etc.) without an extra click. Mirrors drawer state shape; unknown keys are ignored.

```python
"spec": {"chart_type": "line", "dataset": "rates", "mapping": {"x": "date", "y": "us_10y"},
          "initial_state": {
              "transform": "yoy_pct", "smoothing": 5,
              "y_scale": "log", "y_range": "from_zero",
              "shape": {"lineStyleType": "dashed", "step": "middle",
                         "width": 2, "areaFill": True, "stack": "percent"},
              "series": {"us_10y": {"transform": "log", "visible": True}},
              "trendline": "linear", "color_scale": "diverging"}}

{"widget": "table", "initial_state": {"search": "tech", "sort_by": "z", "sort_dir": "desc",
    "hidden_columns": ["legacy_col"], "density": "compact",
    "freeze_first_col": True, "decimals": 2}}

{"widget": "kpi", "initial_state": {"compare_period": "1m", "sparkline_visible": True,
    "delta_visible": True, "decimals": 1}}
```

#### Auto stat strip (`Σ` button)

Every supported time-series chart (`line`, `multi_line`, `area`) gets a `Σ` button in its toolbar. The popup carries one row per visible series with current value, deltas at `1d` / `5d` / `1m` / `3m` / `YTD` / `1Y`, 1Y high-low range, 1Y percentile rank. Computed on-demand — always reflects current state including drawer transforms or filter state.

Format choice (bp / pct+abs / pp / arithmetic) follows `field_provenance.units`:

| units | delta format | example |
|-------|--------------|---------|
| `percent` / `pct` / `%` | bp arithmetic | `4.07%  Δ5d -6bp` |
| `bp` / `basis_points` | bp arithmetic | `-28bp  Δ5d +4bp` |
| `index` / `usd` / `eur` | pct + abs | `4,869  Δ5d +1.5% (+71)` |
| `z` / `zscore` / `sigma` | arithmetic | `1.8  Δ5d +0.6` |
| `pp` / `percentage_points` | pp arithmetic | `+18.4%  Δ5d +1.2pp` |
| (missing) | magnitude heuristic | falls back to pct |

Per-spec overrides: `"stat_strip": False` to suppress; or `"stat_strip": {"horizons": ["1d","5d","1m","YTD","1Y"], "delta_format": "bp", "show_range": True, "show_percentile": True}`. Σ button auto-suppressed for chart types where the strip doesn't apply.

---

## 5. Filters

```json
{"id": "region", "type": "multiSelect", "default": ["US", "EU"],
  "options": ["US", "EU", "JP", "UK"],
  "targets": ["*"], "field": "region", "label": "Region"}
```

`options` can also be `{value, label}` dicts when visible text differs from underlying value.

### 5.1 Types and fields

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

**`dateRange` semantics on charts.** Time-series charts ship with their own `dataZoom` (§5.3). A `dateRange` filter is a global "initial lookback" knob, not a data filter — changing the dropdown moves every targeted chart's visible window via `dispatchAction({type:'dataZoom'})` and leaves the underlying dataset untouched. Tables / KPIs / stat_grids targeted by the same filter still see real row-filtering. Pass `"mode": "filter"` to force row-filter on charts (e.g. histograms / aggregates that must recompute over the window).

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
| `placeholder` / `all_value` | Placeholder text; "no filter" sentinel (`"All"`, `"Any"`) |
| `targets` | List of widget ids to refresh. `"*"` = all data-bound. Wildcards: `"prefix_*"`, `"*_suffix"` |
| `description` (aliases `help`, `info`) / `popup` | Help text + info icon; `{title, body}` markdown popup for click |
| `scope` | `"global"` (top filter bar) or `"tab:<id>"` (inline). Auto-inferred from targets |

**Filter placement is auto-scoped.** Filters targeting multiple tabs or `"*"` go in the global bar; filters whose targets all resolve to a single tab go in a tab-inline bar. Override with explicit `scope`.

**Which chart types reshape on filter change.** Auto-wire happens for `line` / `multi_line` / `bar` / `area` with simple wide-form mapping (no `color` long-form, no `stack`, no `trendline`). Tables, KPIs, stat_grids, and chart types with computed series data (histograms, bullets, candlesticks, heatmaps, scatter-with-trendline, radar, gauge, sankey, treemap, sunburst, funnel, parallel_coords, tree, graph, boxplot) keep their baseline data.

### 5.2 Cascading filters (`depends_on` + `options_from`)

A filter declares `depends_on: <upstream_filter_id>` + `options_from: {dataset, key, where?}`. When the upstream changes, the dependent rebuilds options from the named dataset, optionally filtered by `where` substituting upstream values via `${filter_id}`.

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

Supported `where` ops: `==`, `!=`, `>`, `>=`, `<`, `<=`. Dependent filter's existing value is preserved when valid in the new option set; otherwise falls back to first new option (or empty for `multiSelect`). Cascades chain: when region changes, both country and ticker rebuild in dependency order.

### 5.3 Per-chart zoom (in-chart `dataZoom`)

Every chart with `time` x-axis ships with two `dataZoom` controls injected at compile time (independent of any `dateRange` filter): `type: "inside"` (mouse wheel / pinch zoom + click-and-drag pan) and `type: "slider"` (draggable slider beneath the grid). Full dataset embedded; slider clips visible window. `grid.bottom` auto-bumps. Opt-out for sparkline-style tiles via `chart_zoom: false` on `spec` (or `mapping`); builders that already declared their own `dataZoom` (e.g. candlestick) are left alone.

```json
{"widget": "chart", "id": "tiny_sparkline", "w": 3,
  "spec": {"chart_type": "line", "dataset": "rates",
            "mapping": {"x": "date", "y": "us_2y"}, "chart_zoom": false}}
```

### 5.4 `click_emit_filter`

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

`brush.type`: `rect`, `polygon`, `lineX`, `lineY`. When user brushes on any member chart, runtime extracts `coordRange`, filters linked charts' datasets to brushed range on x axis, re-renders all linked charts. Clearing brush resets dataset.

`members` accepts widget ids or wildcards.

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

## 9. Persistence + refresh (the build flow)

For browser-side refresh failure modal / runner internals / registry schema see `prism/dashboard-refresh.md`. This section is purely about the PRISM-side build flow.

### 9.1 Three-tool-call build model

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
Tool 3: register       Load dashboards_registry.json (seed if missing),
                       append/replace entry by id in registry['dashboards']
                       (NOT as a top-level key — runner only iterates the
                       list), save, verify by re-load, then call
                       update_user_manifest(kerberos, artifact_type='dashboard')
                       and print portal URL.
```

**The persisted script is the source of truth — write it first, then run it from S3.** PRISM authors each script as a Python string, `s3_manager.put`s it to `{DASHBOARD_PATH}/scripts/<name>.py`, then `s3_manager.get`s it back and runs it via `exec(compile(src, ...), ns)` with the same namespace shape the refresh runner uses. The pull happens once (inside Tool 1's exec); the compile happens once (inside Tool 2's exec); build-time and refresh-time are byte-identical.

If Tool 1's verify lines print and Tool 2 ends with `[Tool 2] complete`, the refresh pipeline is provably stable: build-time and refresh-time run the same bytes from the same S3 path with the same helpers. There is no separate verification step. Iterate on the script string + re-run until both succeed end-to-end.

**Anti-pattern:** PRISM pulls data in-session via `pull_market_data(...)`, composes a manifest, calls `compile_dashboard(...)` in-session, *then* writes `pull_data.py` / `build.py` strings as an afterthought. The in-session execution and the on-S3 scripts are two different things; only the in-session one has been exercised. Fix: write the script first, exec it from S3.

#### Tool 1 — author + persist + exec `pull_data.py` FROM S3

```python
DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# Author pull_data.py as a string. Refresh runner re-execs these exact bytes daily.
# Every pull function call passes output_path=f'{SESSION_PATH}/data' (Rule 5).
pull_data_py = '''
"""pull_data.py -- daily refresh of rates monitor data."""
from datetime import datetime
print(f"[pull_data.py] starting at {datetime.now().isoformat()}")

# name='rates' (no _eod suffix); pull_market_data appends it.
# On-disk: {SESSION_PATH}/data/rates_eod.csv + {SESSION_PATH}/data/rates_metadata.json
pull_market_data(
    coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
    start='2020-01-01', name='rates', mode='eod',
    output_path=f'{SESSION_PATH}/data',
)
print("[pull_data.py] done")
'''.lstrip()

s3_manager.put(pull_data_py.encode(), f'{DASHBOARD_PATH}/scripts/pull_data.py')

# Exec FROM S3 with the refresh-runner namespace
import io as _io
src = s3_manager.get(f'{DASHBOARD_PATH}/scripts/pull_data.py').decode('utf-8')
ns = {
    'pd': pd, 'np': np, 'io': _io, 'json': json, 'os': os, 'datetime': datetime,
    's3_manager': s3_manager,
    'SESSION_PATH': DASHBOARD_PATH.rstrip('/'),
    'pull_haver_data':   pull_haver_data,
    'pull_market_data':  pull_market_data,
    'pull_plottool_data': pull_plottool_data,
    'pull_fred_data':    pull_fred_data,
    'save_artifact':     save_artifact,
}
exec(compile(src, f'{DASHBOARD_PATH}/scripts/pull_data.py', 'exec'), ns)

# Verify by reading the CSVs back from S3 -- same path build.py will read tomorrow
df = pd.read_csv(_io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                  index_col=0, parse_dates=True)
print(f'[verify] rates_eod: shape={df.shape}'); print(df.head()); print(df.dtypes)
```

#### Tool 2 — author + persist + exec `build.py` FROM S3

```python
import io
df = pd.read_csv(io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                  index_col=0, parse_dates=True)
df.columns = ['us_2y', 'us_10y']      # plain English (Rule 1)

# Compose initial manifest (with embedded data) just to derive the template.
# Dataset key 'rates_eod' matches the on-disk CSV stem (Rule 5).
initial_manifest = {
    "schema_version": 1, "id": DASHBOARD_NAME, "title": "Rates Monitor",
    "metadata": {"kerberos": KERBEROS, "dashboard_id": DASHBOARD_NAME,
                  "data_as_of": str(df.index.max().date()),
                  "generated_at": datetime.now(timezone.utc).isoformat(),
                  "sources": ["GS Market Data"], "refresh_frequency": "daily",
                  "refresh_enabled": True, "tags": ["rates"]},
    "datasets": {"rates_eod": df.reset_index()},
    "layout": {"rows": [[{"widget": "chart", "id": "curve", "w": 12, "title": "UST Curve",
        "spec": {"chart_type": "multi_line", "dataset": "rates_eod",
                  "mapping": {"x": "date", "y": ["us_2y", "us_10y"]}}}]]}
}

tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(),
                f'{DASHBOARD_PATH}/manifest_template.json')

# Author build.py as a string (~12 lines: load template + load CSVs + populate + compile + upload).
# Refresh runner re-execs this daily.
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

# Exec build.py FROM S3 with refresh-runner namespace
src = s3_manager.get(f'{DASHBOARD_PATH}/scripts/build.py').decode('utf-8')
ns = {
    'pd': pd, 'np': np, 'io': io, 'json': json, 'os': os,
    'datetime': datetime, 'timezone': timezone,
    's3_manager': s3_manager, 'SESSION_PATH': DASHBOARD_PATH.rstrip('/'),
    'compile_dashboard': compile_dashboard,
    'populate_template': populate_template,
    'manifest_template': manifest_template,
    'validate_manifest': validate_manifest,
}
exec(compile(src, f'{DASHBOARD_PATH}/scripts/build.py', 'exec'), ns)

# Confirm every required artefact landed (Rule 4)
for sub in ['scripts/pull_data.py', 'scripts/build.py',
            'manifest_template.json', 'manifest.json', 'dashboard.html']:
    if not s3_manager.exists(f'{DASHBOARD_PATH}/{sub}'):
        raise FileNotFoundError(f'[Tool 2] missing on S3: {sub}')
print('[Tool 2] complete; ready for Tool 3 (register)')
```

#### Tool 3 — register

**There is no `register_dashboard()` helper.** Neither the sandbox nor the refresh runner injects a registry-writing function — Tool 3 hand-rolls a load → list-append → save → pointer-update from scratch. The hourly refresh runner iterates `registry["dashboards"]`; a top-level-keyed entry (`registry[DASHBOARD_NAME] = {...}`) is invisible to it, returns 404 on every refresh, and never produces a `refresh_status.json`. Schema reference for the field shapes lives in `prism/dashboard-refresh.md` §6; the only fields a builder owns are below — `last_refreshed` and `last_refresh_status` are runner-owned and stay `null` until the first real refresh.

```python
import json
from datetime import datetime, timezone

REGISTRY_PATH = f'users/{KERBEROS}/dashboards/dashboards_registry.json'
PORTAL_URL    = f'http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{DASHBOARD_NAME}/'

now_iso = datetime.now(timezone.utc).isoformat()

try:
    registry = json.loads(s3_manager.get(REGISTRY_PATH).rstrip(b'\x00').decode('utf-8'))
except Exception:
    registry = {'dashboards': [], 'last_updated': now_iso}

if 'dashboards' not in registry or not isinstance(registry['dashboards'], list):
    registry['dashboards'] = []

new_entry = {
    'id':                  DASHBOARD_NAME,
    'name':                'Rates Monitor',
    'description':         'Daily monitor of the US rates curve.',
    'created_at':          now_iso,
    'last_refreshed':      None,
    'last_refresh_status': None,
    'refresh_enabled':     True,
    'refresh_frequency':   'daily',
    'folder':              DASHBOARD_PATH,
    'html_path':           f'{DASHBOARD_PATH}/dashboard.html',
    'data_path':           f'{DASHBOARD_PATH}/data',
    'tags':                ['rates'],
    'keep_history':        False,
}

existing_ids = [d.get('id') for d in registry['dashboards']]
if DASHBOARD_NAME in existing_ids:
    idx = existing_ids.index(DASHBOARD_NAME)
    new_entry['created_at'] = registry['dashboards'][idx].get('created_at', now_iso)
    registry['dashboards'][idx] = new_entry
else:
    registry['dashboards'].append(new_entry)

registry['last_updated'] = now_iso
s3_manager.put(json.dumps(registry, indent=2).encode('utf-8'), REGISTRY_PATH)

verify = json.loads(s3_manager.get(REGISTRY_PATH).rstrip(b'\x00').decode('utf-8'))
if DASHBOARD_NAME not in [d.get('id') for d in verify.get('dashboards', [])]:
    raise RuntimeError(f'[Tool 3] {DASHBOARD_NAME} not in registry["dashboards"] after write')

update_user_manifest(KERBEROS, artifact_type='dashboard')
print(f'[Tool 3] registered {DASHBOARD_NAME}; portal: {PORTAL_URL}')
```

Path conventions (verified against live registries): paths have **no leading slash** (`users/...`, not `/users/...`); `folder` has **no trailing slash**; `data_path` is the **`data/` directory**, not `manifest.json`. `data_path` is optional but the portal uses it to surface the dashboard's data folder, so set it.

**Anti-pattern.** Do NOT write the new entry as a top-level key:

```python
# BROKEN — runner ignores this entry, refresh returns 404 forever
registry[DASHBOARD_NAME] = new_entry
s3_manager.put(json.dumps(registry).encode(), REGISTRY_PATH)
```

The resulting registry looks structurally fine (`{"dashboards": [], "last_updated": "...", "<id>": {...}}`) but the dashboard is invisible to `jobs/hourly/refresh_dashboards.py`, which iterates `registry["dashboards"]` only. Two real dashboards (`rates_fx_corr`, `bond_carry_roll`) hit this on 2026-04-27 and required hand-repair. The verify-by-re-load step in the canonical Tool 3 above catches this immediately.

**`update_user_manifest` is NOT a registry-write step.** It only updates `users/{kerberos}/manifest.json`'s `pointers.dashboards` block (count, active_count, last_refreshed, registry_path). It reads the registry to compute those numbers but never writes the registry. The registry must already be saved on S3 with the new entry appended into `dashboards[]` before this call — which is why the canonical Tool 3 runs the put → verify → `update_user_manifest` sequence in that order.

### 9.2 Pull primitives + `save_artifact` cheat sheet

Inside `pull_data.py` they all land their CSVs in the same flat folder by passing `output_path=f'{SESSION_PATH}/data'`. At refresh time the runner injects `SESSION_PATH = {DASHBOARD_PATH}` so the same string resolves to the same S3 folder both at build time and refresh time. There is no separate `DASHBOARD_PATH` reference inside `pull_data.py`.

| Function | Call | On-disk CSV | Metadata sidecar | Manifest key |
|---|---|---|---|---|
| `pull_haver_data` | `pull_haver_data(codes=[...], start='YYYY-MM-DD', name='cpi', output_path=f'{SESSION_PATH}/data')` | `data/cpi.csv` | `data/cpi_metadata.json` | `'cpi'` |
| `pull_market_data` (eod) | `pull_market_data(coordinates=[...], start='YYYY-MM-DD', name='rates', mode='eod', output_path=f'{SESSION_PATH}/data')` | `data/rates_eod.csv` (always `_eod` suffix) | `data/rates_metadata.json` (no suffix) | `'rates_eod'` |
| `pull_market_data` (intraday) | same but `mode='iday'` | `data/rates_intraday.csv` | `data/rates_metadata.json` | `'rates_intraday'` |
| `pull_plottool_data` | `pull_plottool_data(expressions=[...], labels=[...], start='YYYY-MM-DD', name='swap_curve', output_path=f'{SESSION_PATH}/data')` | `data/swap_curve.csv` | `data/swap_curve_metadata.json` | `'swap_curve'` |
| `pull_fred_data` | `pull_fred_data(series=[...], start='YYYY-MM-DD', name='unrate', output_path=f'{SESSION_PATH}/data')` | `data/unrate.csv` | `data/unrate_metadata.json` | `'unrate'` |
| `save_artifact` | `save_artifact(data, name='gs_bank', output_path=f'{SESSION_PATH}/data')` | `data/gs_bank.csv` (or `.json` if dict) | none | `'gs_bank'` |

Three rules from the table that are easy to get wrong:

1. **`name=` does NOT include `_eod` / `_intraday`.** `pull_market_data` appends them. Pass `name='rates'` → `data/rates_eod.csv`. Pass `name='rates_eod'` → `data/rates_eod_eod.csv` (broken).
2. **`pull_market_data` metadata sidecar uses the bare `name`,** not the suffixed CSV stem. So `name='rates'` produces `data/rates_metadata.json` (one file even when both eod and intraday CSVs exist).
3. **`mode='eod'` is the default** but pass it explicitly. The intraday CSV is only written when `mode in ('iday', 'both')`. See §9.4 for the defensive try/except wrap.

#### Reading the CSVs back in `build.py`

```python
import io
df = pd.read_csv(io.BytesIO(s3_manager.get(f'{SESSION_PATH}/data/rates_eod.csv')),
                 index_col=0, parse_dates=True)
df.columns = ['us_2y', 'us_10y']        # rename to plain English (Rule 1)
```

The path `{SESSION_PATH}/data/rates_eod.csv` is byte-identical to what `pull_data.py` wrote because both scripts reference `SESSION_PATH`, which the refresh runner pins to `{DASHBOARD_PATH}` for both execs. The dataset key (`rates_eod`) matches the CSV stem; `populate_template` maps the cleaned DataFrame back into the template by that key.

#### `save_artifact()` for alternative data sources

The four pull primitives only cover Haver / GS Market Data / TSDB expressions / FRED. For everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, scraped tables, hand-built DataFrames), `save_artifact()` is the universal save helper. Same `output_path` semantics; lands a CSV (or JSON for `dict` payloads) at `{output_path}/{name}.{ext}` and is idempotent on re-run.

```python
# inside pull_data.py
fdic_records = fdic_client.get_bank_financials(cert=33124, quarters=8)
save_artifact(fdic_records, name='gs_bank', output_path=f'{SESSION_PATH}/data')
# -> {SESSION_PATH}/data/gs_bank.csv

sec_data = sec_edgar_client.cmd_company_financials('AAPL', 'default')
save_artifact(sec_data, name='aapl_financials', output_path=f'{SESSION_PATH}/data')
# dict -> {SESSION_PATH}/data/aapl_financials.json (build.py reads json.loads(...))

ny_df = pull_nyfed_data('rates')   # not auto-saving; returns a DataFrame
save_artifact(ny_df, name='nyfed_rates', output_path=f'{SESSION_PATH}/data')
```

`save_artifact()`'s output extension follows the input: DataFrame / `list[dict]` / object-with-`.to_frame()` → CSV; `dict` (or empty list) → JSON. `build.py` reads JSON via `json.loads(s3_manager.get(...).decode('utf-8'))` and converts to a DataFrame at populate time.

### 9.3 Templates: `manifest_template` + `populate_template`

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

### 9.4 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_data.py` that fetches intraday MUST wrap it in `try/except` with EOD fallback. Every `build.py` must handle missing intraday file defensively.

```python
# pull_data.py
pull_market_data(
    coordinates=[...], start='2020-01-01',
    name='rates', mode='eod', output_path=f'{SESSION_PATH}/data')
try:
    pull_market_data(
        coordinates=[...], mode='iday',
        start=datetime.now().strftime('%Y-%m-%d'),
        name='rates', output_path=f'{SESSION_PATH}/data')
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

Both `pull_market_data` calls share `name='rates'`, so the metadata sidecar (`rates_metadata.json`) is written / overwritten by whichever call wrote last — both calls describe the same coordinates, so a single sidecar is correct.

### 9.5 Refresh-runner namespace gap

The refresh runner's `_build_exec_namespace` injects `pd`, `np`, `io`, `json`, `os`, `datetime`, `s3_manager`, `SESSION_PATH`, the four pull primitives, `compile_dashboard`, `populate_template`, `manifest_template`, `validate_manifest`. As of 2026-04-27, it does NOT inject `save_artifact`, `pull_nyfed_data`, `pull_pure_data`, `pull_stacked_data`, or any of the alt-data clients (`fdic_client`, `sec_edgar_client`, `bis_client`, `treasury_client`, `treasury_direct_client`, `nyfed_client`, `prediction_markets_client`, `openfigi_client`, `substack_client`, `wikipedia_client`, Coalition / Inquiry helpers).

Consequence: a `pull_data.py` using any of those builds cleanly during the in-session Tool 1 exec (the build-time exec runs in the sandbox, where they ARE injected) but the daily refresh raises `NameError`.

Workarounds while the gap closes:

- **Single-source dashboards using only the four pull primitives** refresh cleanly with no caveat.
- **Multi-source dashboards needing alt-data** are buildable today but should set `metadata.refresh_enabled = False` until the runner namespace expands. Surface this trade-off explicitly.

Structural fix is PRISM-side: extend `_build_exec_namespace` to mirror the `execute_analysis_script` sandbox's data-retrieval bundle. Tracked in `prism/_changelog.md`.

---

## 10. Sandbox patterns

`compile_dashboard`, `manifest_template`, `populate_template`, `validate_manifest`, `df_to_source`, `chart_data_diagnostics`, `load_manifest`, `save_manifest` are auto-injected into both `execute_analysis_script` and the refresh-runner namespace. Never write `from echart_dashboard import ...` or `sys.path.insert(0, ...)`.

In the sandbox, `compile_dashboard` writes to local FS if `output_path` is given — which is blocked by the AST checks. For persistent user dashboards, the right pattern is `write_html=False, write_json=False` and `s3_manager.put()` manually so the artifact lands at `{DASHBOARD_PATH}/dashboard.html` rather than the compiler's default `{session_path}/dashboards/{id}.html`:

```python
r = compile_dashboard(manifest, write_html=False, write_json=False, strict=True)
if not r.success: raise ValueError(f"COMPILE FAILED: {r.error_message}")
s3_manager.put(r.html.encode('utf-8'), f'{DASHBOARD_PATH}/dashboard.html')
s3_manager.put(json.dumps(manifest, indent=2).encode('utf-8'),
                f'{DASHBOARD_PATH}/manifest.json')
```

---

## 11. Common patterns (recipes)

Same chart-type names + mapping keys as §3.

### 11.1 Long-form `multi_line` with color

```python
datasets["rates_long"] = df.melt(id_vars=['date'], var_name='series', value_name='yield')
```

```json
{"widget": "chart", "id": "curve", "w": 12, "h_px": 380, "title": "UST curve",
  "spec": {"chart_type": "multi_line", "dataset": "rates_long",
            "mapping": {"x": "date", "y": "yield", "color": "series",
                        "y_title": "Yield (%)"}}}
```

### 11.2 Actuals vs estimates via `strokeDash`

```json
{"widget": "chart", "id": "capex", "w": 12, "h_px": 380,
  "title": "Big Tech capex", "subtitle": "solid = actual, dashed = estimate",
  "spec": {"chart_type": "multi_line", "dataset": "capex",
            "mapping": {"x": "date", "y": "capex", "color": "company",
                        "strokeDash": "type", "y_title": "Capex ($B)"}}}
```

### 11.3 Dual axis

```json
{"widget": "chart", "id": "spx_ism", "w": 12, "h_px": 380, "title": "Equities vs ISM",
  "spec": {"chart_type": "multi_line", "dataset": "macro",
            "mapping": {"x": "date", "y": "value", "color": "series",
                        "dual_axis_series": ["ISM Manufacturing"],
                        "y_title": "S&P 500", "y_title_right": "ISM Index",
                        "invert_right_axis": false}}}
```

Before dual-axis: print `df['series'].unique()` and assert the right-axis name is present. Name mismatch is the #1 failure mode.

### 11.4 Bullet: rates RV screen

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

### 11.5 Pairing thesis + watch notes (high-leverage opening)

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

## 12. Palettes

| Palette | Kind | Use |
|---------|------|-----|
| `gs_primary` | categorical | Default (navy, sky, gold, burgundy, …) |
| `gs_blues` | sequential | Heatmaps, calendar heatmaps, gradients |
| `gs_diverging` | diverging | Correlation matrices, z-score heatmaps |

Categorical → `option.color`. Sequential / diverging → `visualMap.inRange.color` (heatmaps, correlation matrices).

Brand hex anchors for `series_colors`: GS Navy `#002F6C`, GS Sky `#7399C6`, GS Gold `#B08D3F`, GS Burgundy `#8C1D40`, GS Forest `#3E7C17`, GS Positive `#2E7D32`, GS Negative `#B3261E`.

---

## 13. Anti-patterns

**Data integrity:**

| Anti-pattern | Do instead |
|--------------|-----------|
| `np.random.*` / `np.linspace` / `np.arange` / hand-typed arrays as data; `np.zeros()` fill for missing values | Pull real data first (§9.1). If no source, don't build the panel; render a note or use a small real slice |
| Authoring `build.py` before `pull_data.py` produced real DataFrames | Run pulls first, print shapes / heads / dtypes, write manifest against verified columns |
| Literal numbers in manifest JSON | Pass the DataFrame; compiler converts |
| PRISM hand-writing HTML / CSS / JS, or `build.py` >50 lines | Emit manifest; `compile_dashboard()` does the rest |
| Source attribution in title / subtitle | `metadata.sources` for dashboard-level; `field_provenance` per-column (§4.4) |
| Dropping provenance because vendor isn't standard | `system: "computed"` + `recipe`, or `system: "csv"` + path. Never drop |
| Annotating self-evident facts (zero on a spread) | Omit |
| Hand-tuning `y_title_gap` / `grid.left` | Just set `x_title` / `y_title`; compiler sizes from real label widths |

**Persistence + the build flow:**

| Anti-pattern | Do instead |
|--------------|-----------|
| Saving a user dashboard only to `SESSION_PATH`; skipping the refresh button by editing HTML | Persist to `users/{kerberos}/dashboards/...`; set `metadata.kerberos` + `dashboard_id` |
| Pulling data and/or compiling in-session, *then* writing scripts to S3 as an afterthought — two divergent code paths | Write the script to S3 first, `s3_manager.get` it back, `exec` it |
| Inlining data pull + manifest build into one tool call so neither `pull_data.py` nor `build.py` exist as standalone files | Use the three-tool model: Tool 1 persists+execs `pull_data.py`; Tool 2 persists+execs `build.py`; Tool 3 registers |
| Saving scripts to `SESSION_PATH/scripts/` instead of `{DASHBOARD_PATH}/scripts/` | Refresh runner only looks at `{DASHBOARD_PATH}/scripts/` |
| `registry[DASHBOARD_NAME] = entry` — writing the new dashboard as a TOP-LEVEL key in `dashboards_registry.json` | `registry['dashboards'].append(entry)` (or replace-by-id). The hourly refresh runner only iterates `registry['dashboards']`; a top-level-keyed entry is invisible → 404 → no `refresh_status.json`. There is no `register_dashboard()` helper; the canonical hand-rolled upsert lives in §9.1 Tool 3 |
| Treating `update_user_manifest(kerberos, artifact_type='dashboard')` as the registry-write step | It only updates `users/{kerberos}/manifest.json`'s pointer block. Save the registry with `s3_manager.put(...)` FIRST, then call the wrapper |
| Setting `last_refreshed` / `last_refresh_status` to the build timestamp at registration time | Leave both as `null` at registration; the refresh runner owns those fields and overwrites them on the first real refresh |
| Writing `history_retention_days` into the registry entry | Field is not part of the live schema (2026-04-27); treat as planned/unimplemented, do not write it |
| S3 paths with leading slash (`/users/...`) or `folder` with trailing slash | Live registry convention: no leading slash, no trailing slash on `folder`; `data_path` points to the `data/` directory, not `manifest.json` |

**Data routing (Rule 5 + `pull_*_data` quirks):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Calling any `pull_*_data` / `save_artifact` WITHOUT `output_path=f'{SESSION_PATH}/data'` | Always pass `output_path`. Otherwise CSVs land in per-source subfolders and `build.py`'s `data/<name>.csv` read raises `FileNotFoundError` on every refresh |
| Passing `name='rates_eod'` to `pull_market_data` (function appends another `_eod` → `data/rates_eod_eod.csv`) | Pass `name='rates'`. Sidecar uses the bare name (`data/rates_metadata.json`) |
| Hand-rolling `s3_manager.put(df.to_csv().encode(), ...)` for FDIC / SEC EDGAR / BIS / Treasury / NY Fed / scraper output | Use `save_artifact(data, name='...', output_path=f'{SESSION_PATH}/data')`. Polymorphic, idempotent |
| `manifest.datasets` keys NOT matching on-disk CSV stems (key `'rates'` while CSV is `data/rates_eod.csv`) | Make the dataset key the CSV stem byte-for-byte: `'rates_eod'`, `'rates_intraday'`, `'cpi'` |
| `pull_data.py` uses names the runner doesn't inject (`save_artifact`, alt-data clients) AND ships with `refresh_enabled: True` | Restrict to the four pull primitives, OR set `metadata.refresh_enabled = False` until the runner namespace expands (§9.5) |

---

## 14. Pre-flight checklist

Run `s3_manager.list()` on `{DASHBOARD_PATH}` and verify each path:

- `dashboard.html` — compiled HTML
- `manifest.json` — compiled manifest with embedded data
- `manifest_template.json` — structural template, no data
- `scripts/pull_data.py` — verbatim Tool 1 script
- `scripts/build.py` — verbatim Tool 2 script (~12 lines)
- `data/<dataset>.csv` — one CSV per dataset, flat folder. Stem matches `manifest.datasets` key. `pull_market_data` auto-appends `_eod` / `_intraday`

`refresh_status.json` is NOT a build-time artefact — the refresh runner writes it on first refresh attempt.

**Configuration:**

- `metadata.kerberos` + `dashboard_id` + `data_as_of` set; `refresh_frequency` set; `refresh_enabled` defaults to `True`
- Registry entry **appended into `registry['dashboards']`** (not written as a top-level key); verify by re-loading and asserting `DASHBOARD_NAME in [d['id'] for d in registry['dashboards']]`
- `update_user_manifest(kerberos, artifact_type='dashboard')` called AFTER the registry write succeeds (the wrapper updates the user manifest pointer block, it does not write the registry itself)

**Data integrity:**

- Every dataset traces to a real pull (Rule 1)
- Every `pull_*_data(...)` and `save_artifact(...)` passes `output_path=f'{SESSION_PATH}/data'` (Rule 5)
- Every `pull_market_data` `name=` is the bare base (no `_eod` / `_intraday`)
- Every `manifest.datasets` key matches the on-disk CSV stem byte-for-byte
- `pull_data.py` printed real shapes / heads / dtypes before `build.py` was authored; intraday handled defensively
- If `pull_data.py` uses `save_artifact` or any alt-data client, `metadata.refresh_enabled = False` (§9.5)
- Datasets cleaned: `df.reset_index()` for DTI-keyed frames, plain English columns, no MultiIndex
- Every dataset backing a chart / table carries `field_provenance` (per-column `system` + `symbol`)
- Time-series pulls preserve full back-history (§16); never clip to the visible window

**Build mechanics:**

- Tool 1 authored as string, persisted to S3, then `s3_manager.get`-ed and `exec`-ed
- Tool 2 same pattern; `build.py` is thin (~12 lines)
- Both ran cleanly to completion — the build IS the refresh smoke test

**Hand-off:** portal URL printed only after Tool 3 succeeds.

---

## 15. Data shape prep + archetypes

**Five non-negotiables for DataFrames:**

1. **Tidy.** One row = one observation, one column = one variable. No multi-index, no embedded headers, no totals row.
2. **Date as a column.** Never as `DatetimeIndex`. Use `df.reset_index()`. Compiler emits `date` to ISO-8601; ECharts auto-detects time-axis.
3. **Plain-English columns.** `us_10y`, not `USGG10YR Index`. Compiler humanises `us_10y` → `US 10Y` for legends, tooltips, axis hints.
4. **Datasets named like nouns.** `rates`, `cpi`, `flows`, `bond_screen` — not `df1`, not `usggt10y_panel`.
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

- `df.reset_index()` before passing DTI-keyed frame
- Unpack `pull_market_data` tuples: `eod_df, _ = pull_market_data(...)`
- Flatten MultiIndex: `df.columns = ['_'.join(c) for c in df.columns]`
- Rename opaque API codes to plain English
- Resample to native frequency per series

**Data budgets** (enforced by `strict=True`): single dataset 10K rows (warn) / 50K (err); single dataset 1 MB / 2 MB; total manifest 3 MB / 5 MB; table-widget 1K / 5K rows.

**Frequency-mixing trap.** Haver stores many monthly / quarterly series at business-daily granularity. Symptom: stair-step lines. Fix: resample to true native frequency before charting; never chart a DataFrame with mixed-frequency NaN gaps.

```python
starts = starts.resample('M').last()   # stock: last-of-month
claims = claims.resample('M').mean()   # flow: mean
cpi    = cpi.resample('Q').last()      # rate: last-of-quarter
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
```

---

## 16. Time horizons

**Pull deep history.** The defaults below are initial zoom windows, not data-layer caps. Every time-series chart ships with a per-chart `dataZoom` slider (§5.3) carrying the full dataset, and `dateRange` filters operate in view-mode by default with intervals `1M/3M/6M/YTD/1Y/2Y/5Y/All` — but both reach back only as far as the data goes.

If `pull_data.py` clips a 30-year FRED series to 2 years before persisting (or `build.py` slices / resamples / inner-joins it post-merge), those years are gone; the slider can't scroll into history that was never pulled. Loss of back-history at the PRISM transformation layer is irreversible from the dashboard side.

| Frequency | Initial zoom (default) | Rationale |
|-----------|------------------------|-----------|
| Quarterly / monthly | 10 years | Full business cycle |
| Weekly | 5 years | Trend + cycle |
| Daily | 2 years | Regime without noise |
| Intraday | 5 trading days | Event reaction window |

Override: if narrative references "highest since X", the initial window must include X (data still extends back as far as the source allows). For pre-pandemic comparisons set initial start ≥ 2015. Don't open at 12 months of monthly (hides cycle), 30 years of daily (noise), or different ranges for charts meant to be compared.
