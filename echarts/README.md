# Dashboards

**Module:** dashboards
**Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
**Tier:** 2 (on-demand)
**Scope:** ALL **dashboard** construction in PRISM (interactive HTML manifests with charts, KPIs, tables, filters, links, refresh wiring). One-off chat / email / PNG charts use **Altair** via `make_chart()` -- not covered here.
**Engine:** ECharts (`ai_development/dashboards/`)

`compile_dashboard(manifest)` is the only user-facing entry point. PRISM never writes HTML. PRISM emits a structured JSON manifest; the compiler validates, lowers each chart widget through internal builders, and emits the interactive dashboard.

The `make_echart()` and composite (`make_2pack_*` / `make_3pack_triangle` / `make_4pack_grid` / `make_6pack_grid`) helpers in this module are **internal builders** -- the dashboard compiler calls them under the hood for chart widgets. They are NOT the path PRISM uses to ship a one-off chart to a user. For PNGs in chat / email / report, PRISM uses Altair (`make_chart()`); for interactive analysis, PRISM ships a dashboard. Sections 2, 2.7, 6 below document the builder surface for completeness, but every PRISM-facing example in this README assumes the dashboard manifest path.

## Module file map

```
ai_development/dashboards/
  config.py             GS brand tokens + one theme + 3 palettes + dimensions
  echart_studio.py      single-chart producer: builders + knobs + CLI
  echart_dashboard.py   dashboard compiler: validator + manifest_template +
                          populate_template + Dashboard builder + CLI
  composites.py         multi-grid layouts (2/3/4/6-pack composition)
  rendering.py          single-chart editor HTML + dashboard HTML +
                          dashboard runtime JS + headless-Chrome PNG export
  samples.py            chart + dashboard samples + PRISM roleplay demos
  demos.py              12 end-to-end demo scenarios + CLI + gallery
  inspect_dashboard.py  visual diagnostics for compiled dashboards
  tests.py              unit + stress test suite (348 unit tests +
                          11 stress scenarios) with interactive CLI
  README.md             this file
  DATA_SHAPES.md        DataFrame organisation + tidy/wide forms +
                          per-archetype templates + reuse + filter alignment +
                          pull_* -> manifest pipeline + size budget limits
  output/               generated demo dashboards (one folder per timestamp)
  inspect/              generated inspection artifacts
  archive/              legacy files kept for reference
```

For the prior question -- *what does the DataFrame fed into a manifest look like* -- read `DATA_SHAPES.md`. The README covers chart types, knobs, widgets, dashboards, refresh; `DATA_SHAPES.md` covers how to structure pandas DataFrames so wiring them into manifest specs is mechanical.

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

## 1. Entry points + helpers

```python
# PRISM-facing (injected into execute_analysis_script's namespace):
compile_dashboard       # manifest -> interactive dashboard HTML + manifest JSON (+ optional PNGs)
df_to_source            # DataFrame -> list-of-lists (rarely called directly)
manifest_template       # strip data from a manifest -> reusable template
populate_template       # template + fresh DataFrames -> ready-to-compile manifest
validate_manifest       # dry-run the validator without rendering
chart_data_diagnostics  # second-pass lint: empty datasets, missing columns, size budget, etc.

# Internal builders (the dashboard compiler calls these for chart widgets;
# PRISM does NOT call them directly when shipping artifacts):
make_echart             # single-chart builder -- consumed inside compile_dashboard
ChartSpec, make_2pack_horizontal, make_2pack_vertical,
make_3pack_triangle, make_4pack_grid, make_6pack_grid    # composite layouts (legacy)
```

One theme (`gs_clean`), three palettes (`gs_primary`, `gs_blues`, `gs_diverging`), twelve dimension presets + `custom`. No theme switcher. No skin config.

---

## 2. Single-chart builder: `make_echart()` (internal)

> `make_echart()` is the per-chart builder the dashboard compiler invokes for every `widget: chart` (`spec.chart_type` + `spec.mapping` flow into this function). It exists as a public symbol so the editor HTML / passthrough mode are testable in isolation and so the composite helpers (2.7) can call it. **PRISM does not ship one-off charts via `make_echart()`** -- one-off PNGs go through Altair `make_chart()`, interactive analysis goes through `compile_dashboard()`. This section documents the builder surface so the chart-type catalogue / mapping keys / annotations work uniformly inside dashboard widget specs (section 3.5).

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
| `y_title_gap` / `x_title_gap` | Pixels between axis tick labels and axis title. Auto-sized from the longest category-axis label by default (so a horizontal bar with 38-char strategy names gets a `nameGap` of ~250 px instead of 56). Override here when the auto value is wrong. |
| `y_title_right_gap`           | Same, for the right y-axis on dual-axis charts.                                         |
| `category_label_max_px`       | Max pixel width for category-axis tick labels (default `220`). Labels longer than this are truncated with an ellipsis (`axisLabel.width` + `overflow: "truncate"`). Set higher when you want long labels rendered in full and have the canvas room for them; set lower for very narrow tile widths. |
| `grid_padding`                | Dict `{top, right, bottom, left}` overriding the plot-area margins. Auto-bumps `right` to 56 when a right-axis name is present, and to `76` for heatmaps (so the visualMap legend never crops the right cell column). |
| `show_grid` / `show_axis_line` / `show_axis_ticks` | `False` to suppress the corresponding axis chrome (split lines, axis line, tick marks). Applies uniformly to x and y unless you gate them via `spec` vs `mapping`. |
| `series_colors`               | Dict `{col_name: "#hex"}`. Overrides the palette for specific series. Column name can be the raw column (`"us_2y"`) or the post-humanise display name (`"US 2Y"`). |
| `tooltip`                     | Spec-level tooltip override. Either a full ECharts `tooltip` dict, or a sugared form: `{"trigger": "axis" \| "item" \| "none", "decimals": 2, "formatter": "<JS fn string>", "show": False}`. `decimals` controls numeric-value rounding without writing a function. |

**Axis titles never collide with tick labels.** Long category names (horizontal bar of strategy descriptions, bullet of yield-curve points, heatmap rows of factor exposures) used to either overlap a rotated `yAxis.name`, or get silently dropped by ECharts' default `interval: 'auto'` thinning. The compiler now does layout-aware sizing automatically:

- **Truncate long category labels.** Any tick label longer than `category_label_max_px` (default `220` px) gets `axisLabel.width` + `overflow: "truncate"` + ellipsis. The full string is still in the underlying data, so tooltips / interactions are intact.
- **Size `nameGap` from real labels.** `yAxis.nameGap` (and `xAxis.nameGap` on rotated bottom labels) is computed from the longest label width plus padding for the rotated title's bounding box, instead of a fixed 56 / 40 px. This applies to BOTH category axes (longest text) and value axes (formatted extremes of `opt.series` data) -- so a vertical bar with 9-digit volume labels gets a `nameGap` of ~90 px instead of clipping the rotated title.
- **Bump `grid.left` / `grid.bottom`.** With `containLabel: true`, the axis name still sits outside the grid box. The compiler bumps `grid.left` to fit the rotated `yAxis.name` and `grid.bottom` (~`nameGap + 80` px empirically) so the `xAxis.name` doesn't get clipped at the canvas edge.
- **Auto-rotate vertical-bar / boxplot x-labels** when (a) there are <=30 categories, (b) average label length > 5 chars, and (c) the unrotated total label width would exceed the inner plot width. The compiler sets `rotate: 30` and `interval: 0` so every category renders. For dense time-series-like axes (e.g. a daily volume bar with 250+ bars), the threshold check kicks the chart back to ECharts' default thinning, which is the right call there.
- **Heatmap visualMap clearance.** `grid.right` is bumped to `76` px so the vertical visualMap legend never crops the rightmost cell column.
- **Heatmap and boxplot now honor `x_title` / `y_title`.** Previously these builders silently dropped the axis-title mapping keys; both now route through the same `_apply_axis_titles` pipeline as line / bar / scatter / bullet.

Per-spec overrides remain available: `y_title_gap`, `x_title_gap`, `y_title_right_gap`, `category_label_max_px`. If you've manually set `axisLabel.rotate` upstream, the auto-rotate path is a no-op (idempotent).

### 2.3 Chart types (25 builders + `raw` passthrough)

> The 25 entries below are the registered builders -- valid values for `spec.chart_type` inside dashboard chart widgets. The 26th conceptual type, `raw`, is **not** a `chart_type` value; it's the dashboard's `option` / `ref` widget variants (3.4) and the `make_echart(option=..., chart_type='raw')` passthrough call. Use those when you need an ECharts option the builder catalogue doesn't cover.

| chart_type         | Required mapping keys                                     |
|--------------------|-----------------------------------------------------------|
| `line`             | `x`, `y`, optional `color`                                |
| `multi_line`       | `x`, `y` (list) OR `x`, `y`, `color`                      |
| `bar`              | `x` (category), `y`, optional `color`, `stack` (bool)     |
| `bar_horizontal`   | `x` (value), `y` (category), optional `color`, `stack`    |
| `scatter`          | `x`, `y`, optional `color`, `size`, `trendline`           |
| `scatter_multi`    | `x`, `y`, `color`, optional `trendlines`                  |
| `scatter_studio`   | none required; `x_columns` / `y_columns` / `color_columns` whitelist drives runtime X/Y picker. See 6.6 |
| `area`             | `x`, `y` (stacked area)                                   |
| `heatmap`          | `x`, `y`, `value`                                         |
| `correlation_matrix` | `columns` (list of >=2 numeric columns), optional `transform`, `method`, `order_by`. See 6.7 |
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
| `dual_axis_series`   | (legacy) List of series-name strings to render on the right axis. Use `axes` for >2 axes. |
| `invert_right_axis`  | (legacy) Flip the right axis (rates-style "up = bullish"). Use `axes[i].invert` for >2 axes. |
| `axes`               | List of axis spec dicts for N-axis time series (canonical, supports any number of independent y-axes). See "Multi-axis time series" below. |
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

Heatmap-style charts (`heatmap`, `correlation_matrix`, `calendar_heatmap`) accept these additional mapping keys for value labels and color configuration:

| Key                  | Purpose                                                  |
|----------------------|----------------------------------------------------------|
| `show_values`        | Print each cell's numeric value. Default `True` for `heatmap` / `correlation_matrix`, `False` for `calendar_heatmap` (cells are tiny). |
| `value_decimals`     | Decimals on the cell label. Auto-picked from data magnitude when omitted (3 for sub-unit values, 0 for >=100). |
| `value_formatter`    | Explicit JS formatter string (overrides the built-in). Auto-contrast is suppressed because the wrapping format is opaque to the builder. |
| `value_label_color`  | `"auto"` (default): black on light cells, white on dark cells via WCAG sRGB luminance. Any hex / rgb string sets a fixed color. `False` leaves the ECharts default. |
| `value_label_size`   | Cell-label font size (default 11).                       |
| `colors`             | Explicit list of color stops, e.g. `["#fff", "#08306b"]`. Highest-priority override.       |
| `color_palette`      | Palette name from `PALETTES` (e.g. `gs_blues`, `gs_diverging`).                            |
| `color_scale`        | `sequential` / `diverging` / `auto`. `auto` picks a diverging palette anchored at 0 when the data crosses zero. |
| `value_min`, `value_max` | Pin the visualMap range so colors stay interpretable across reruns with different data spreads. |

Auto-contrast text is implemented through ECharts rich-text styles (`label.rich.l` for dark text on light cells, `label.rich.d` for light text on dark cells). The label formatter is a JS function that picks the right style per cell from `params.color`'s relative luminance. ECharts heatmap series do **not** evaluate `label.color` as a callback -- that path is static-only -- which is why auto-contrast routes through the rich-text formatter instead.

#### Multi-axis time series (`mapping.axes`)

Line / multi_line / area charts support any number of independent y-axes via `mapping.axes`. Each axis gets its own scale, side (left/right), inversion, log toggle, range bounds, and tick formatter. This generalises the legacy 2-axis API (`dual_axis_series` + `invert_right_axis`) -- both still work, and `axes` takes precedence when both are present.

```python
make_echart(df, "multi_line", mapping={
    "x": "date",
    "y": ["spx", "ust", "dxy", "wti"],
    "axes": [
        {"side": "left",  "title": "SPX",     "series": ["spx"], "format": "compact"},
        {"side": "right", "title": "UST 10Y", "series": ["ust"], "invert": True, "format": "percent"},
        {"side": "left",  "title": "DXY",     "series": ["dxy"]},
        {"side": "right", "title": "WTI",     "series": ["wti"], "format": "usd"},
    ],
})
```

Per-axis spec keys:

| Key             | Purpose                                                                                  |
|-----------------|------------------------------------------------------------------------------------------|
| `side`          | `"left"` or `"right"`. Required.                                                         |
| `title`         | Axis name printed alongside.                                                             |
| `series`        | List of series names assigned to this axis. Each series belongs to exactly one axis.     |
| `invert`        | Flip top<->bottom (default False).                                                       |
| `log`           | Log scale (default False).                                                               |
| `min`, `max`    | Pin range explicitly.                                                                    |
| `format`        | Tick formatter preset (`percent` / `bp` / `usd` / `compact`) or raw ECharts function string. |
| `offset`        | Pixel offset from the inner edge. Auto-computed (0, 80, 160, ...) when omitted so axes on the same side stack outward without overlapping. |
| `scale`         | Default `True`: ECharts auto-fits the range; set `False` to anchor at zero.              |
| `color`         | Explicit hex / rgb for the axis line, ticks, label color, and rotated name color. Defaults to the assigned series' palette color when the axis carries exactly one series. Set `False` to opt this axis out of color-coding. |

Mapping-level extras:

| Key                      | Purpose                                                                              |
|--------------------------|--------------------------------------------------------------------------------------|
| `axis_offset_step`       | Floor (in px) for the spacing between successive axes on the same side. Default 80 (clears 4-5 digit tick labels comfortably). The compiler dynamically widens the step when the inner axis's tick labels are wide enough (e.g. `"470.0%"` percent labels) that 80 px would crowd the rotated inner-axis name into the outer axis's labels. Bump only when you want a more spacious layout than the auto-computed one. |
| `axis_color_coding`      | Default `True`: single-series axes auto-tint axis line / labels / name to match the series color (Bloomberg-style). Set `False` to disable globally. |

**Color-coding.** When `axis_color_coding` is on (default), every axis that carries exactly one series picks up that series' palette color across its axis line, tick labels, and rotated name. Axes carrying 2+ series leave styling neutral because there's no single color to bind to -- pin one explicitly via `axes[i].color`. The line and its scale share the hue, so a glance at the axis tells you which series it belongs to without legend lookup.

Layout sizing is automatic and data-aware: after the series are built, the compiler walks each axis to estimate the longest tick-label width (using the format preset and the series' actual min/max), sets per-axis `nameGap` to clear those labels plus the rotated title's bounding box, and widens the per-side `offset_step` whenever the inner-axis name would otherwise bleed into the outer axis's labels. `grid.left` / `grid.right` are then sized to fit every axis's offset + label band + name without clipping. Only the first axis on the chart shows split lines (`splitLine`) -- additional axes hide them so the plot area doesn't drown in overlapping gridlines.

Annotations target a specific axis via `axis: <index>` (0..N-1). The legacy `axis: "right"` shorthand still resolves to index 1 for backward compat:

```python
annotations=[
    {"type": "hline", "y": 4.5, "axis": 1, "label": "UST ceiling"},
    {"type": "hline", "y": 110, "axis": 2, "label": "DXY support"},
]
```

When to use `mapping.axes` vs alternatives:

- **2 axes, simple case**: `dual_axis_series` + `invert_right_axis` is shorter -- prefer it.
- **3+ axes, comparing values across asset classes**: `mapping.axes` -- but consider whether normalisation (`Index = 100` via the controls drawer) or `make_4pack_grid` would read better. 4 axes can become hard to scan visually even when laid out cleanly.
- **3+ series in the same units**: don't add axes -- one axis is right.

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

### 2.7 Composites (legacy multi-chart single-artifact)

> The composite helpers below produce a single multi-grid PNG-style ECharts canvas with N sub-charts laid out for you. They predate the dashboard compiler and are kept for backwards compatibility, but are **NOT a path PRISM uses** -- PRISM ships interactive dashboards (this module) or Altair PNGs (the other module). Documented here for completeness; `demos.py` does not include any composite scenarios in the gallery.

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

### 2.9 PNG export

Two complementary paths: server-side (headless Chrome, runs from Python with no browser open) and browser-side (live "Download Dashboard" button in the header of every compiled dashboard). They serve different workflows and are independent.

#### 2.9.1 Server-side: headless Chrome

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

A whole compiled dashboard HTML file can also be screenshotted to a single PNG (used by `demos.py` to generate gallery thumbnails):

```python
from rendering import save_dashboard_html_png

save_dashboard_html_png(
    "out/dashboard.html", "out/thumbnail.png",
    width=1500, height=1300, scale=1,
)
```

Caveat: the viewport is fixed at the supplied `height`; content past that is clipped. Set `height` generous enough to fit the entire dashboard, or use the browser-side button (2.9.2) which captures full scrollable height automatically.

#### 2.9.2 Browser-side: "Download Dashboard" button

Every compiled dashboard ships with a `Download Dashboard` button in the top-right header that captures the entire current view (header + tabs + filter bar + active tab panel + footer) as a single full-page PNG. This is the workflow path for "I want to drop the dashboard into a vision model and ask questions about it" -- open dashboard, click button, paste PNG into PRISM (or any vision-capable LLM).

Powered by `html2canvas@1.4.1` (CDN), **lazy-loaded on first click** (~32 KB) so dashboards that never use it pay zero cost. The handler waits for every ECharts `finished` event before rasterizing so partial / mid-animation captures are avoided. Output filename: `<MANIFEST.id>_YYYY-MM-DD-HH-MM-SS.png`.

For tabbed dashboards the button captures the **currently visible tab**; switch tabs and click again to capture another. Open modals are captured as-is -- close them first for a clean dashboard view.

When serving from `file://`, Chrome prints a benign `'file:' URLs are treated as unique security origins` console warning. The export still succeeds; the warning disappears entirely if you serve over HTTP (`python3 -m http.server` in the dashboard folder, then open via `http://localhost:8000/dashboard.html`).

> **CSS constraint** -- `html2canvas@1.4.1` does not parse modern CSS color functions like `color-mix()`, `color(srgb ...)`, `oklch()`, `oklab()`, etc. The dashboard stylesheet deliberately avoids these. If you add new CSS rules to `rendering.py`, stick to `rgba()`, `hsl()`, `hsla()`, hex, and named colors so the browser-side export keeps working. (This is documented inline as a comment on the `.row-hl-pos` / `.row-hl-neg` CSS rules.)

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
        "methodology": (              # optional; markdown; see 3.3.1
            "## Sources\n\n* US Treasury OTR yields (FRED H.15)\n\n"
            "## Construction\n\n* 2s10s = 10Y minus 2Y in basis points"
        ),
    },

    "header_actions": [               # optional; see 3.10
        {"label": "Open registry",
          "href": "/users/goyairl/dashboards/", "icon": "\u2198"},
    ],

    "datasets": {
        "rates": df_rates,            # DataFrame -> auto-converted
        "cpi":   {"source": df_cpi},  # explicit form works too

        # Per-column source attribution; PRISM cleans upstream
        # metadata into this shape and passes it explicitly. The
        # compiler does NOT introspect df.attrs. See 3.6 for the
        # popup integration.
        "fx": {
            "source": df_fx,
            "field_provenance": {
                "EURUSD": {"system": "market_data",
                            "symbol": "FX_EURUSD_Spot_Rate",
                            "source_label": "GS Market Data",
                            "units": "rate"},
            },
        },
    },

    "filters": [                      # optional
        # dateRange in view mode (default): sets the initial dataZoom
        # window on every targeted chart. Charts always render full
        # history -- the dropdown is a "default lookback", not a
        # data filter. Tables and KPIs that target the same filter
        # still get real row-level filtering.
        {"id": "lookback", "type": "dateRange", "default": "6M",
          "targets": ["*"], "field": "date",
          "label": "Initial range"},
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

### 3.3 Metadata block (refresh + provenance + methodology)

The optional `manifest.metadata` block is the single place where data provenance, refresh configuration, and dashboard methodology live. It drives the **data-freshness badge**, the **methodology popup**, and the **refresh button** in the header. All fields are optional -- omit them for pure session-scope artifacts, set them for persistent dashboards.

| Field                    | Type                          | Purpose                                                             |
|--------------------------|-------------------------------|---------------------------------------------------------------------|
| `kerberos`               | `str`                         | User kerberos; required for the refresh button to render.           |
| `dashboard_id`           | `str`                         | Id for the refresh API; defaults to `manifest.id`.                  |
| `data_as_of`             | `str` (ISO)                   | Timestamp of the underlying data -- renders in the header badge as `Data as of YYYY-MM-DD HH:MM:SS UTC`. |
| `generated_at`           | `str` (ISO)                   | When this manifest was compiled. Used as a fallback for the badge.  |
| `sources`                | `list[str]`                   | Data source names (e.g. `["GS Market Data", "Haver"]`).             |
| `summary`                | `str` \| `{title?, body}` dict | Markdown rendered as a top-of-dashboard prose banner above the first row -- the "today's read" / executive summary slot PRISM uses to frame the page before any chart loads. See 3.3.2. |
| `methodology`            | `str` \| `{title?, body}` dict | Markdown describing how the dashboard's data is sourced, constructed, and refreshed. Drives the header **Methodology** button + popup. See 3.3.1. |
| `refresh_frequency`      | `str`                         | One of `hourly | daily | weekly | manual`.                          |
| `refresh_enabled`        | `bool`                        | Set `False` to hide the refresh button (even if kerberos is set).   |
| `tags`                   | `list[str]`                   | Free-form tags; echoed into the registry.                           |
| `version`                | `str`                         | Manifest version string.                                            |
| `api_url`                | `str`                         | Refresh endpoint override (default `/api/dashboard/refresh/`).      |
| `status_url`             | `str`                         | Status endpoint override (default `/api/dashboard/refresh/status/`).|

#### 3.3.1 Methodology popup

Set `metadata.methodology` to a markdown string -- or a `{title, body}` dict -- and a **Methodology** button appears in the standard top-right protocol. Clicking it opens a centered modal rendered with the shared markdown grammar (full table in 3.6: h1-h5, paragraphs, ordered + unordered lists with nesting, blockquotes, fenced code, GFM tables, horizontal rules, inline bold / italic / strike / code / link).

```python
metadata = {
    "data_as_of": "2026-04-24T15:00:00Z",
    "methodology": (
        "## Sources\n\n"
        "* US Treasury OTR yields (FRED H.15)\n"
        "* Global central-bank policy rates (BIS, ECB SDW)\n\n"
        "## Construction\n\n"
        "* Spreads (2s10s, 5s30s) are simple cash differences in basis points\n"
        "* 10Y real yield = 10Y nominal minus 10Y breakeven\n\n"
        "## Refresh\n\n"
        "* Daily after US cash close (~16:00 ET)"
    ),
}
```

Use the dict form when you want a custom modal title:

```python
"methodology": {
    "title": "FOMC monitor methodology",
    "body":  "## Cut probability gauge\n\nImplied probability...",
}
```

#### 3.3.2 Summary banner ("today's read")

Set `metadata.summary` to a markdown string -- or a `{title, body}` dict -- and a prose strip renders below the global filter bar, above the first row / tab bar. This is the slot for the dashboard's executive summary: the one paragraph PRISM uses to frame what changed before the reader scans the charts.

Distinct from the methodology popup in two ways: (1) the summary is **always visible** (no click to open) and (2) it's about the data's current state, not how the data is constructed. Use methodology for "here's how 2s10s is computed", use summary for "today the curve bull-steepened on a soft print".

```python
metadata = {
    "summary": {
        "title": "Today's read",
        "body": (
            "Front-end has richened ~6bp on a softer print and a "
            "dovish-leaning Fed speaker. The curve "
            "**bull-steepened**, with 2s10s widening out of the "
            "inversion zone for the first time in three weeks.\n\n"
            "1. 2Y -6bp, 10Y -3bp: classic bull-steepener\n"
            "2. 5s30s flatter on long-end demand into auction\n"
            "3. Real yields barely moved; the move is nominal-led\n\n"
            "> Watch the 4.10% 10Y level into tomorrow's PCE."
        ),
    },
}
```

The bare-string form `"summary": "..."` is also accepted; the modal-title slot just stays empty.

The body uses the full markdown grammar (see 3.6) -- ordered lists, blockquotes, tables, code, headings -- so it carries the same expressive ceiling as the markdown widget. Skip it for purely interactive utility dashboards; set it for daily/weekly reports where the prose framing is the lead.

#### 3.3.3 Standard top-right protocol

Every compiled dashboard places the same elements in the top-right header, in this fixed left-to-right order. Each piece is auto-shown only when its enabling configuration is present, so a minimal manifest still produces a clean header.

| Position | Element              | Visible when                                                       |
|----------|----------------------|--------------------------------------------------------------------|
| 1        | `Data as of <ts>`    | `metadata.data_as_of` or `metadata.generated_at` is set            |
| 2        | `Methodology`        | `metadata.methodology` is set                                      |
| 3        | `Refresh`            | `metadata.kerberos` + `dashboard_id` set, `refresh_enabled != False` |
| 4        | `Download PNGs`      | always (one file per chart widget)                                 |
| 5        | `Download Dashboard` | always (one file: the entire current view as a single PNG)         |
| 6        | `Download Excel`     | dashboard contains at least one `widget: table`                    |

`header_actions[]` (3.10) injects custom buttons in front of this protocol bar.

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
| `markdown`  | `id`, `content`                         | Freeform markdown prose block (transparent) |
| `note`      | `id`, `body`                            | **Semantic callout** for narrative writing -- tinted card with a colored left-edge stripe keyed by `kind` (insight / thesis / watch / risk / context / fact). See 3.6. |
| `divider`   | `id`                                    | Horizontal rule, forces row break    |

Common optional fields: `w` (1-12 grid span), `h_px` (chart only; default 280), `title`.

**Widget presentation knobs (apply to every tile type):**

| Field            | Purpose                                                                                   |
|------------------|-------------------------------------------------------------------------------------------|
| `title`          | Card header text. When set on a chart, the internal ECharts title is auto-suppressed so the chart doesn't show a duplicate headline. Set `spec.keep_title: True` to opt out. |
| `subtitle`       | Secondary italic text rendered under the title in the tile header. Great for methodology notes, data vintage, scope disclaimers ("daily OHLC", "3Y rolling window"). |
| `footer`         | Small text rendered below the tile body, separated by a dashed border. Useful for source attribution, methodology caveats, refresh cadence notes. `footnote` is accepted as an alias. |
| `info`           | Short help string. Renders an `\u24D8` icon; hover shows it as a native tooltip, **clicking opens a modal** with the same text (so long blurbs are still readable + dismissable). |
| `popup`          | `{title, body}` for the modal when the `\u24D8` icon is clicked. `body` is markdown using the shared grammar (3.6: headings / lists with nesting / blockquotes / tables / fenced code / inline bold / italic / strike / code / links). Takes precedence over `info` for the modal content; `info` stays as the hover tooltip. |
| `badge`          | Short string (1-6 characters) rendered as a pill next to the title -- e.g. `"LIVE"`, `"BETA"`, `"NEW"`. Pair with `badge_color` (`"gs-navy"` default / `"sky"` / `"pos"` / `"neg"` / `"muted"`). |
| `emphasis`       | `True` highlights the tile with a thicker navy border + subtle shadow. KPIs get a sky-blue top border accent. Use sparingly for the one stat that matters most. |
| `pinned`         | `True` makes the tile sticky to the top of the viewport while the user scrolls. Good for a KPI row the reader always needs in view. |
| `action_buttons` | List of extra buttons rendered in the chart toolbar alongside the built-in PNG / fullscreen buttons. Each is `{label, icon?, href?, onclick?, primary?, title?}`. `href` opens a new tab; `onclick` names a global JS function (e.g. `"customRun"`) called with the widget id. |
| `click_emit_filter` | (chart widgets only) Turn data-point clicks into filter changes. Either a bare filter id string, or `{filter_id, value_from, toggle}` where `value_from` is `"name"` (default), `"value"`, or `"seriesName"` and `toggle` defaults `True` (re-clicking the same value clears the filter). Wire this to a `select` / `radio` filter whose `targets` point at downstream widgets for click-through filtering. |
| `click_popup`    | (chart widgets only) Turn data-point clicks into a per-row detail popup. **Same grammar as table `row_click`** -- simple `popup_fields` mode for a key/value table, or rich `detail.sections[]` mode (stats / markdown / chart / table). Use this when each data point represents a distinct entity (a bond on a carry/roll scatter, a name on a top-movers bar, a sector on a donut) and the reader wants details on demand. See the **Chart click popups** subsection in 3.6. |

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

### 3.6 KPI / table / stat_grid / image / markdown / note / divider

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

Table-level fields: `searchable` (search input + row count), `sortable` (header click reorders), `downloadable` (XLSX button in toolbar; default `true`), `row_height` (`compact` / default), `max_rows` (viewport cap, default 100), `empty_message`.

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
| `markdown`   | Paragraph with `{field}` / `{field:format}` template substitution. Uses the shared markdown grammar (3.6) -- headings, ordered + unordered lists with nesting, blockquotes, tables, fenced code, inline bold / italic / strike / code / link. |
| `chart`      | Embedded mini-chart. `chart_type` one of `line` / `bar` / `area`; dataset + filter_field / row_key to scope to the clicked row. Supports `mapping.y` as a column or a list of columns, `annotations` (hline / vline / band), and a numeric `height`. |
| `table`      | Sub-table driven by a filtered manifest dataset, same filter_field / row_key pattern. `max_rows` caps length. |
| `kv` / `kv_table` | Key/value table for a subset of `row` fields (useful to split the row into multiple themed panels). |

**Template substitution** (`{field:format}`):

Template strings in `subtitle_template` / markdown section `template` / stats field `sub` support placeholders like `{field}` and `{field:format}`. Formats match the column formats: `number:N`, `signed:N`, `percent:N`, `currency:N`, `bps:N`, `delta:N`, `date`. Unknown fields pass through untouched.

**Modal close** (same as simple mode): X button, ESC, or overlay click.

`row_click.extra_content` (HTML string) is still honored as a postscript on simple mode. On rich mode it's ignored -- use a `markdown` section instead.

#### Chart click popups (`click_popup`)

`click_popup` on a chart widget is the data-point analog of `row_click`. Click any point in a scatter, line, bar, area, candlestick, bullet, pie, donut, funnel, treemap, sunburst, heatmap, or calendar_heatmap and the corresponding row in the chart's `dataset` opens in the same modal grammar tables use. Same simple / rich modes, same template substitution, same modal close behaviour. The clear use case is a bond carry-and-roll scatter where each point is a bond and the popup shows the bond's profile: stats, issuer blurb, spread + price history filtered to that CUSIP, recent events. Clicking is the lowest-friction way to drill from a chart point into the row that drives it -- otherwise the same data has to live duplicated in a sibling table just to surface row identity.

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
    "subtitle_template": "CUSIP {cusip} \u00B7 {sector} \u00B7 {coupon_pct:number:2}% coupon \u00B7 matures {maturity}",
    "detail": {
      "wide": true,
      "sections": [
        {"type": "stats",
          "fields": [
            {"field": "carry_bp",     "label": "Carry",    "format": "number:1", "suffix": " bp"},
            {"field": "roll_bp",      "label": "Roll",     "format": "number:1", "suffix": " bp"},
            {"field": "ytm_pct",      "label": "YTM",      "format": "number:2", "suffix": "%"},
            {"field": "duration_yrs", "label": "Duration", "format": "number:2", "suffix": " yrs"},
            {"field": "rating",       "label": "Rating"}
          ]},
        {"type": "markdown",
          "template": "**{issuer}** \u00B7 *{sector}*\n\n{blurb}\n\nSpread **{spread_bp:number:0} bp**, matures **{maturity}**."},
        {"type": "chart",
          "title": "OAS spread history",  "chart_type": "line",
          "dataset": "bond_hist", "row_key": "cusip", "filter_field": "cusip",
          "mapping": {"x": "date", "y": "spread_bp"}, "height": 220},
        {"type": "table",
          "title": "Recent events",  "dataset": "bond_events",
          "row_key": "issuer", "filter_field": "issuer", "max_rows": 6,
          "columns": [{"field": "date"}, {"field": "event"}, {"field": "reaction"}]}
      ]
    }
  }
}
```

Simple mode is the lighter alternative when you only need a key/value table:

```json
"click_popup": {
  "title_field": "issuer",
  "subtitle_template": "{sector} \u00B7 {rating} \u00B7 matures {maturity}",
  "popup_fields": [
    {"field": "carry_bp", "label": "Carry", "format": "number:1", "suffix": " bp"},
    {"field": "roll_bp",  "label": "Roll",  "format": "number:1", "suffix": " bp"},
    {"field": "ytm_pct",  "label": "YTM",   "format": "number:2", "suffix": "%"}
  ]
}
```

`popup_fields` accepts plain field-name strings OR `{field, label, format, prefix, suffix}` dicts -- mix freely. Chart popups don't have a column config to inherit formats from (tables do), so reach for the dict form when the bare value isn't readable on its own (`4.55` is fine, `0.0455` needs `format: "percent:2"`).

**Row resolution.** ECharts hands the click handler `params.dataIndex`, `params.seriesIndex`, `params.seriesName`, `params.name`, `params.value`. The compiler maps that back to a dataset row using rules keyed off `chart_type` and `mapping`:

| Chart type                                              | How `params` -> row                                 |
|---------------------------------------------------------|-----------------------------------------------------|
| `line` / `multi_line` / `area` / `bar` / `bar_horizontal` / `scatter` / `scatter_multi` / `candlestick` / `bullet` (no `mapping.color`) | `rows[dataIndex]` of the (filter-stripped) dataset |
| Same chart types with `mapping.color` set               | filter dataset by `color_col == params.seriesName`, then take `dataIndex`-th row of that subset |
| `pie` / `donut` / `funnel` / `treemap` / `sunburst`     | match `mapping.category` (or `mapping.name`) cell `== params.name` |
| `heatmap`                                               | reconstruct unique x/y category lists, match the `(x_cat, y_cat)` cell pair |
| `calendar_heatmap`                                      | match `mapping.date` cell `== params.value[0]`     |
| `histogram` / `radar` / `gauge` / `sankey` / `graph` / `tree` / `parallel_coords` / `boxplot` | not row-resolvable -- the click is a no-op (the chart shape doesn't have row identity) |

For grouped charts (`mapping.color` set), ECharts reports `params.seriesName` as the post-humanize legend label (`Investment Grade`, not `investment_grade`). The compiler reads the raw column value off the live ECharts option (`series._column`, set by post-build polish when humanise renames the series) so the lookup matches the dataset cell exactly.

**Filter awareness.** The popup pulls the current filter-stripped view (the same view that's painted on screen) for charts that auto-rewire on filter change (line / multi_line / bar / area without color grouping). Other charts pull from the unfiltered dataset, mirroring the chart's own state.

**Cursor affordance.** When `click_popup` is configured, ECharts' default emphasis (highlight on hover, pointer cursor on data point) tells the reader the chart is interactive. No extra CSS needed.

**Modal grammar** is shared with `row_click`: same `title_field`, `subtitle_template`, `popup_fields`, `detail.sections[]` (stats / markdown / chart / table), same template substitution rules, same X / ESC / overlay-click close. See 3.6 for the section types and template substitution syntax.

#### Data provenance & source attribution

Every chart line / bar / point / heatmap cell and every table row/cell can carry the upstream identifier (Haver code, plottool/TSDB ticker, FRED series, Bloomberg ticker, market_data coordinate, computed-recipe formula, etc.) plus the source system that produced it. The compiler surfaces that lineage in two places automatically:

1. **Auto-default click popup** -- when a chart's `click_popup` (or a table's `row_click`) is *not declared*, but the dataset carries `field_provenance`, clicking a point / row opens a minimal modal showing the row's relevant fields plus a "Sources" footer. No extra config required -- traceability is the gimme.
2. **Sources footer on every popup** -- whenever an explicit `click_popup` / `row_click` IS declared, the same Sources footer auto-appends after the body. Suppressible per popup with `show_provenance: false`.

Suppress the auto-default per widget with `click_popup: false` (chart) or `row_click: false` (table). Set `click_popup: true` to force the default even when no explicit config is given (useful when you want to be explicit about opting in).

**Schema** -- attach to a dataset entry alongside `source`:

```json
"datasets": {
  "rates": {
    "source": [["date", "UST10Y", "UST2Y"], ["2026-04-24", 4.30, 4.15]],
    "field_provenance": {
      "UST10Y": {
        "system": "market_data",
        "symbol": "IR_USD_Treasury_10Y_Rate",
        "tsdb_symbol": "ustsy10y",
        "display_name": "US 10Y Treasury Rate",
        "units": "percent",
        "source_label": "GS Market Data"
      },
      "UST2Y": {
        "system": "market_data",
        "symbol": "IR_USD_Treasury_2Y_Rate",
        "tsdb_symbol": "ustsy2y",
        "source_label": "GS Market Data"
      }
    },
    "row_provenance_field": "ticker",
    "row_provenance": {
      "GS": {"last": {"system": "bloomberg",
                       "symbol": "GS US Equity",
                       "source_label": "Bloomberg"}}
    }
  }
}
```

**Per-column provenance dict** (`field_provenance.<column>`):

| Key             | Required        | Purpose                                                                              |
|-----------------|-----------------|--------------------------------------------------------------------------------------|
| `system`        | strongly recommended | Source system identifier: `haver`, `market_data`, `plottool`, `fred`, `bloomberg`, `refinitiv`, `csv`, `computed`, or any free-form string PRISM wants to use. |
| `symbol`        | strongly recommended | Canonical identifier in that system. Free-form so PRISM can pass the exact upstream string (`GDP@USECON`, `IR_USD_Treasury_10Y_Rate`, `sofrswp10y - sofrswp2y`, `DGS10`, `USGG10YR Index`, ...). |
| `display_name`  | optional        | Human-readable label rendered in the footer (defaults to the column name).            |
| `units`         | optional        | `percent`, `bp`, `USD billion (SAAR)`, etc. Rendered as a small italic tag.           |
| `source_label`  | optional        | Vendor/desk attribution for the footer (e.g. `GS Market Data`, `Haver Economics`).    |
| `recipe`        | optional        | For `system: "computed"`. Free-form formula string rendered in the footer (e.g. `UST10Y - UST2Y`). |
| `computed_from` | optional        | List of source column names the recipe references (so transitive provenance can be resolved later if needed). |
| `as_of`         | optional        | ISO timestamp of the latest tick for the column (mirrors `manifest.metadata.data_as_of` at the column level). |
| `<vendor_alt>`  | optional        | System-specific alternate IDs (`haver_code`, `tsdb_symbol`, `fred_series`, `bloomberg_ticker`, `refinitiv_ric`, ...). The footer surfaces the first present in priority order: `symbol` > `coordinate` > `expression` > `haver_code` > `tsdb_symbol` > `fred_series` > `bloomberg_ticker` > `refinitiv_ric`. |

The validator only enforces shape (must be a dict of dicts). The inner keys are intentionally free-form so PRISM can carry whatever the upstream system emits without us having to enumerate every vendor.

**Per-row overrides** (entity tables where each row may pull from a different system):

`row_provenance_field` names a column whose cell value keys into `row_provenance`. Each entry under `row_provenance` is a dict of `column_name -> provenance_dict` that *overrides* the column-level entry for that row. Use this on screener/top-movers tables where AAPL might come from market_data and TSLA from Bloomberg.

```json
"row_provenance_field": "ticker",
"row_provenance": {
  "AAPL": {"last": {"system": "market_data",
                      "symbol": "EQ_US_AAPL_Last",
                      "source_label": "GS Market Data"}},
  "TSLA": {"last": {"system": "bloomberg",
                      "symbol": "TSLA US Equity",
                      "source_label": "Bloomberg"}}
}
```

**Where the footer surfaces**:

- Below the body of every `_openPopupModal` (simple `popup_fields`) -- one row per relevant column.
- At the end of every `openRichRowModal` (rich `detail.sections[]`) -- after every section.
- Inline subline beneath any `stats` section field that sets `show_source: true` (compact alternative to the full footer):

```json
{"type": "stats",
  "fields": [
    {"field": "UST10Y", "label": "10Y", "format": "number:2",
      "suffix": "%", "show_source": true}
  ]}
```

The footer renders only columns the popup body actually references. For default popups built from `mapping`, that's the chart's mapped axes (e.g. `x`, `y`, `color`); for explicit popups, it's whatever `popup_fields` / stats / kv sections name. Markdown sections are ignored for the footer purposes (they reference fields freely; the union with stats/kv is enough signal in practice).

**Computed/derived columns** -- when a column was constructed in PRISM (e.g. `2s10s = UST10Y - UST2Y`), set `system: "computed"` and pass `recipe` + `computed_from`:

```json
"field_provenance": {
  "us_2s10s": {
    "system": "computed",
    "recipe": "UST10Y - UST2Y",
    "computed_from": ["UST10Y", "UST2Y"],
    "display_name": "2s10s spread", "units": "bp"
  }
}
```

**PRISM-side contract** (skill file):

PRISM is the one that cleans upstream metadata into this shape. The compiler does NOT introspect `df.attrs` or auto-derive provenance from anything -- because PRISM pulls from many systems beyond Haver/FRED/market_data and the cleaning step is system-specific. The `Dashboard.add_dataset` builder accepts `field_provenance=` / `row_provenance_field=` / `row_provenance=` as explicit kwargs; in the manifest dict form, attach them directly to each `datasets[name]` entry next to `source`.

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

**image / markdown / note / divider widgets**

```json
{"widget": "image", "id": "logo", "w": 3,
  "src": "https://.../gs_logo.png",
  "alt": "Goldman Sachs",
  "link": "https://..."}

{"widget": "markdown", "id": "md", "w": 12,
  "content": "### Method\nSynthetic UST panel. **Brush** the curve to cross-filter.\n\n- Source: [GS Market Data](https://example.com)\n- Refresh: daily\n- Scope: US only"}

{"widget": "divider", "id": "sep"}
```

#### Note widget (semantic callout)

The `note` widget renders a **tinted card with a colored left-edge stripe** keyed by `kind`. Use it when a paragraph is load-bearing -- the thesis, the risk, the watch level -- and you want the reader to find it without re-reading the whole page. A flat markdown widget reads as flat prose; a note tells the reader "this is the claim".

| Field   | Required | Purpose                                                                                          |
|---------|----------|--------------------------------------------------------------------------------------------------|
| `id`    | yes      | Widget id.                                                                                       |
| `body`  | yes      | Markdown body. Full grammar (see below).                                                         |
| `kind`  | no       | One of `insight` / `thesis` / `watch` / `risk` / `context` / `fact`. Default `insight`.          |
| `title` | no       | Short title rendered next to the kind label.                                                     |
| `icon`  | no       | Optional 1-2 character glyph rendered to the left of the title (e.g. an arrow, asterisk, etc.).  |
| `w`     | no       | Grid span 1..12. Default 12.                                                                     |
| `footer` / `popup` / `info` | no | Standard widget knobs (3.5) work here too.                                              |

| Kind      | Visual                                  | Use for                                                  |
|-----------|-----------------------------------------|----------------------------------------------------------|
| `insight` | sky-blue stripe + sky tint (default)    | Observation / "the lightbulb"                            |
| `thesis`  | navy stripe + navy tint                 | The load-bearing claim of the dashboard                  |
| `watch`   | amber stripe + amber tint               | Levels / events to monitor                               |
| `risk`    | red stripe + red tint                   | Downside / pain trades                                   |
| `context` | grey stripe + grey tint                 | Background / setup info                                  |
| `fact`    | green stripe + green tint               | Established / point-in-time facts                        |

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

Pairing a `thesis` and `watch` note in a 6/6 row at the top of a dashboard is a high-leverage pattern: the reader gets the load-bearing claim and the "what would change my mind" criteria in one row, before any chart loads.

See `demos.py::build_news_wrap` for all six kinds in one dashboard, `demos.py::build_fomc_brief` for `thesis` + `watch` + `context` carrying a document-first narrative across tabs, and `demos.py::build_research_feed` for a `thesis` + `insight` + `watch` + `context` curator-commentary pattern paired with a markdown-bodied article feed.

#### Markdown grammar (shared)

The same grammar applies to **every** prose-rendering surface in the dashboard:

* `widget: markdown` -- the dedicated freeform tile (transparent on page).
* `widget: note` -- the `body` field of every callout kind.
* `metadata.summary` -- the top-of-dashboard banner (3.3.2).
* `metadata.methodology` -- the header methodology popup (3.3.1).
* `popup: {body}` -- click-popup body on any tile / filter / stat.
* Per-row drill-down `markdown` sections (3.6, table widget).
* The `subtitle` / `description` line on tabs is plain text, not markdown.

| Block          | Syntax                                                                                                |
|----------------|-------------------------------------------------------------------------------------------------------|
| Headings       | `# H1` ... `##### H5` (h1-h5; `######` and deeper are clamped to h5)                                  |
| Paragraph      | Lines separated by a blank line; lines within a paragraph are joined with a single space              |
| Unordered list | `-` or `*` at line start                                                                              |
| Ordered list   | `1.` / `2.` / ... at line start (numbers don't have to be sequential, the renderer ignores them)      |
| Nested list    | Indent by **2 spaces** per level. Mix `ul` and `ol` freely; nested lists live inside the parent `<li>` |
| Blockquote     | `> ...` at line start; multi-line blocks accumulate                                                    |
| Code block     | Triple-backtick fenced. Optional language tag: ```` ```python ```` -> `<pre><code class="lang-python">` |
| Table          | GFM: header row, separator row `| --- | --- |`, body rows. Alignment hints `:---` / `---:` / `:---:` |
| Horizontal rule| A line containing only `---`, `***`, or `___`                                                          |

| Inline      | Syntax            |
|-------------|-------------------|
| Bold        | `**bold**`        |
| Italic      | `*italic*`        |
| Strike      | `~~strike~~`      |
| Inline code | `` `code` ``      |
| Link        | `[label](url)` (always opens in a new tab; URLs are HTML-escaped but otherwise passed through) |

Anything that does not match is escaped as plain text -- including raw HTML. The grammar is implemented in two parallel parsers (`_render_md` in Python, `_mdInlinePopup` in JS) so the same input produces the same output server-side and client-side. They must be upgraded together when extending the grammar.

```python
content = """
### Today's read

The curve **bull-steepened** on a softer print.

#### Top movers

1. 2Y -6bp on the day
2. 10Y -3bp on the day
   - real component flat
   - breakeven did most of the work
3. 5s30s flatter into the auction

| Level     | Threshold | Meaning                |
|-----------|----------:|------------------------|
| 2s10s     | `0bp`     | flat -> recession watch|
| 5s30s     | `+50bp`   | normal carry regime    |
| 10Y real  | `+2.0%`   | restrictive territory  |

> Watch 4.10% on the 10Y into tomorrow's PCE; a clean break opens 4.00%.

Skip the dashed lines on the spread chart -- those are
~~policy targets~~ shape thresholds.
"""
```

### 3.7 Filters

```json
{"id": "region", "type": "multiSelect", "default": ["US", "EU"],
  "options": ["US", "EU", "JP", "UK"],
  "targets": ["*"], "field": "region", "label": "Region"}
```

`options` can also be a list of `{value, label}` dicts when the visible text needs to differ from the underlying filter value (e.g. user-friendly labels backing terse codes):

```json
{"id": "mode", "type": "radio", "default": "sell",
  "options": [
    {"value": "sell", "label": "Looking to Sell (Feel Best to Buy)"},
    {"value": "buy",  "label": "Looking to Buy (Feel Best to Sell)"}
  ],
  "targets": ["screener"], "field": "mode", "label": "Mode"}
```

The renderer extracts the underlying `value` for the input element and the `label` for the visible text. `default` may be either the underlying value (e.g. `"sell"`) or the same dict shape -- a `{value, label}` default is normalised to its `value` at compile time so the JS filter runtime stays primitive-only.

**Nine filter types:**

| Type          | UI                              | Applies to                                  |
|---------------|---------------------------------|---------------------------------------------|
| `dateRange`   | select of 1M/3M/6M/YTD/1Y/2Y/5Y/All | **Charts** (view-mode, default): sets initial dataZoom window. **Tables / KPIs**: filters `rows[field]` to range. Set `mode: "filter"` to row-filter charts too. |
| `select`      | `<select>`                      | `rows[field] == value`                      |
| `multiSelect` | `<select multiple>`             | `rows[field] in [values]`                   |
| `radio`       | radio button group              | same as `select`, different UI              |
| `numberRange` | text `min,max`                  | `min <= rows[field] <= max`                 |
| `slider`      | `<input type="range">` + value  | `rows[field] op value` (op defaults `>=`)   |
| `number`      | `<input type="number">`         | `rows[field] op value` (op defaults `>=`)   |
| `text`        | `<input type="text">`           | `rows[field] op value` (op defaults `contains`) |
| `toggle`      | checkbox                        | `rows[field]` truthy when checked           |

**dateRange semantics on charts.** Time-series charts ship with their own dataZoom controls (inside scroll/pinch + slider beneath the grid + drag-to-pan), so the user can zoom and pan every chart independently across the full history. A `dateRange` filter is therefore a global "initial lookback" knob, not a data filter -- changing the dropdown moves every targeted chart's visible window via `dispatchAction({type:'dataZoom'})` and leaves the underlying dataset untouched. Tables and KPIs targeted by the same filter still see the data filtered to the chosen range (e.g. "average over the last 6M"). To force the legacy row-filter behavior on charts (e.g. when you want a histogram or aggregate to recompute over the window), set `"mode": "filter"` on the filter declaration.

**Fields:**

| Field        | Purpose                                                       |
|--------------|---------------------------------------------------------------|
| `id`         | Required; unique within manifest.                             |
| `type`       | Required; one of the 9 above.                                 |
| `default`    | Initial value.                                                |
| `field`      | Dataset column to filter against.                             |
| `op`         | Comparator: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`. |
| `transform`  | `abs` / `neg` applied to the cell before compare (e.g. `|z|` filters). |
| `options`    | Required for `select`, `multiSelect`, `radio`. Two accepted shapes: list of primitives `["US", "EU", "JP"]`, or list of dicts `[{"value": "sell", "label": "Looking to Sell"}, ...]` when display text differs from the underlying filter value. **Anything else** (e.g. raw dicts without `value`, nested lists) raises a validation error -- this is the most common source of "JSON-text in radio buttons" rendering bugs. |
| `min`, `max`, `step` | Required for `slider`; optional for `number`.         |
| `placeholder`| Placeholder text for `text` / `number`.                       |
| `all_value`  | Sentinel that means "no filter" (e.g. `"All"` / `"Any"`). Lets radio/select have an explicit all option. |
| `targets`    | List of widget ids to refresh when this filter changes. `"*"` matches every data-bound widget (charts, tables, kpis, stat_grids). Wildcards: `"prefix_*"`, `"*_suffix"`. |
| `mode`       | `dateRange` only. `"view"` (default) -> sets initial dataZoom on chart targets without filtering data. `"filter"` -> filters chart rows by the selected window (legacy behavior; usually only needed for histograms / aggregates that must recompute over the window). |
| `label`      | Display label. `dateRange` filters in view-mode default to "Initial range" when no label is supplied so PRISM-emitted ids like `dt` or `fs_dt` don't leak into the UI as cryptic two-letter labels. |
| `description` | Short help text. Renders an `\u24D8` icon next to the filter label; hover shows it as a tooltip, **clicking opens a modal** with the same text. Aliases: `help`, `info`. |
| `popup`       | `{title, body}` markdown popup for click, same mechanism as widget popups. Use for long-form help that doesn't fit a tooltip. |
| `scope`      | `"global"` (default; top filter bar) or `"tab:<id>"` (render inline inside a tab panel). Auto-inferred from `targets`: when every target lives in the same tab, scope becomes `"tab:<that_tab>"`; any wildcard / cross-tab target stays global. |

Filters update the shared filter state and are applied client-side by the dashboard runtime on every bound widget.

**Filter placement is auto-scoped.** Every filter goes in one of two places:

- **Global filter bar** (top of the dashboard, below the header) -- for filters that span multiple tabs or use the `"*"` wildcard. Renders only when at least one global filter exists, so dashboards without global filters have no empty bar.
- **Tab-inline filter bar** (flush inside the tab panel) -- for filters whose `targets` all resolve to a single tab. The filter appears only when that tab is active.

Explicitly set `scope: "tab:<tab_id>"` to override the auto-inferred placement, or `scope: "global"` to force the top bar even when the filter could live in a tab.

**Which chart types reshape on filter change.** Auto-wire happens only when a filter targets the widget AND the chart_type + mapping is safe to re-shape client-side: `line` / `multi_line` / `bar` / `area` with simple wide-form mapping (no `color` long-form grouping, no `stack`, no `trendline`). Filtered tables, KPIs, stat_grids, and chart types with computed series data (histograms, bullets, candlesticks, heatmaps, scatter-with-trendline, radar, gauge, sankey, treemap, sunburst, funnel, parallel_coords, tree, graph, boxplot) keep rendering their baseline data -- the filter state still tracks but those charts don't visually reshape.

### 3.7.1 Per-chart zoom (in-chart x-axis scrolling)

Every chart whose x-axis resolves to `time` ships with two `dataZoom` controls injected at compile time:

- **`type: "inside"`** -- mouse wheel / pinch zoom + click-and-drag pan directly on the plot area
- **`type: "slider"`** -- a draggable slider beneath the grid with handles for fine-grained range control

This means a user can independently zoom and pan every chart across its full history without ever touching a global filter. The dashboard always embeds the full dataset; the slider just clips the visible window.

The grid's `bottom` padding is auto-bumped to make room for the slider, so existing charts don't need any layout changes.

Opt-out (e.g. for very small sparkline-style chart tiles where the slider would dominate):

```json
{"widget": "chart", "id": "tiny_sparkline", "w": 3,
  "spec": {"chart_type": "line", "dataset": "rates",
            "mapping": {"x": "date", "y": "us_2y"},
            "chart_zoom": false}}
```

`chart_zoom: false` on the spec (or on `mapping`) suppresses the auto-injection. Builders that already declared their own `dataZoom` (e.g. `candlestick`) are left alone.

### 3.7.2 Per-tile controls drawer

Every chart, table, and KPI tile ships with a `⋮` button in the tile toolbar that toggles a controls drawer between the title bar and the tile body. The drawer is populated lazily on first open and only renders the knobs the underlying widget can support.

#### Chart drawer

| Knob                           | Charts                            | Behavior                                                                         |
|--------------------------------|-----------------------------------|----------------------------------------------------------------------------------|
| Per-series transform           | line / multi_line / area          | `Raw` / `Δ` / `%Δ` / `log Δ` / `YoY Δ` / `YoY %` / `YoY log Δ` / `Annualized Δ` / `log` / `z-score` / `Rolling z (252)` / `Pct rank` / `YTD Δ` / `Index = 100`. Each series independently. Grouped under `Basic` / `Advanced` `<optgroup>` headers. |
| Smoothing                      | line / multi_line / area          | Off / 5 / 20 / 50 / 200-period rolling mean.                                     |
| Y-scale                        | line / multi_line / area / bar / scatter / scatter_studio | Linear / Log.                                                              |
| Y-range                        | line / multi_line / area          | Auto / From zero.                                                                |
| **Shape: Style**               | line / multi_line / area          | Inherit / Solid / Dotted / Dashed (mirrors Haver's chart-type strip; mutates `series.lineStyle.type`). |
| **Shape: Step**                | line / multi_line / area          | Inherit / Off / Start / Middle / End (mutates `series.step`).                    |
| **Shape: Width**               | line / multi_line / area          | Inherit / 1 px / 2 px / 3 px (mutates `series.lineStyle.width`).                 |
| **Shape: Area fill**           | line / multi_line / area          | Inherit / On / Off (toggles `series.areaStyle`, opacity 0.30).                   |
| **Shape: Stack**               | line / multi_line / area          | Inherit / Grouped / Stacked / 100% stacked (auto-rescales each x to a percent). |
| **Shape: Markers**             | line / multi_line / area          | Inherit / Show / Hide (toggles `series.showSymbol`).                             |
| Bar sort                       | bar / bar_horizontal              | Input order / Value desc / Value asc / Alphabetical.                             |
| Bar stack                      | bar / bar_horizontal              | Grouped / Stacked / 100% stacked (auto-rescales values, formats axis as `%`).    |
| Scatter trendline              | scatter / scatter_multi           | Off / Linear (OLS) — fitted client-side from `series.data`.                       |
| X-scale                        | scatter / scatter_multi / scatter_studio | Linear / Log.                                                                    |
| **Studio: X / Y / color / size column** | scatter_studio          | Dropdowns populated from the author's `x_columns` / `y_columns` / `color_columns` / `size_columns` whitelists. |
| **Studio: per-axis transform** | scatter_studio                    | `Raw` / `log` / `Δ` / `%Δ` / `YoY %` / `z-score` / `Rolling z (252d)` / `pct rank`. Applied to X and Y independently. |
| **Studio: window / outliers / regression** | scatter_studio        | `All` / `252d` / `504d` / `5y`; `Off` / `IQR×3` / `\|z\|>4`; `Off` / `OLS` / `OLS per color`. |
| Heatmap color scale            | heatmap / correlation_matrix      | Sequential / Diverging-around-zero (uses GS palette). Override defaults via mapping `colors` / `color_palette` / `color_scale`. |
| Heatmap labels + auto-contrast | heatmap / correlation_matrix / calendar_heatmap | Toggle cell values (default on for heatmap / correlation_matrix); auto-contrast picks black/white text per cell from background luminance via `label.rich`. |
| Pie sort + "Other" bucket      | pie / donut                       | Input order / Largest first; group slices below 1%/3%/5% as "Other".              |

**Universal action bar** (every chart):

- **View data** — opens a modal with the rows that produced the chart. Truncates at 1,000 rows; full dataset is in Copy CSV.
- **Copy CSV** — clipboard, full filtered dataset.
- **Download PNG / CSV / XLSX** — direct downloads of the chart image and underlying data. PNG bakes the title in (same path as the dashboard-level "Download PNGs" button); XLSX uses the SheetJS bundle that's already loaded for the dashboard-level Excel export.
- **Reset chart** — clears the per-chart state and re-renders with compile-time defaults.

**Transform semantics for time series.** All transforms run entirely client-side over the dataset already embedded in the dashboard — no PRISM round-trip.

| Transform                | Formula                                                                          |
|--------------------------|----------------------------------------------------------------------------------|
| `Δ`, `%Δ`, `log Δ`       | Period-over-period: `v[i] - v[i-1]`, `(v[i]-v[i-1])/v[i-1]*100`, `ln(v[i])-ln(v[i-1])`. |
| `YoY Δ`, `YoY %`, `YoY log Δ` | Compare against `v[j]` where `j` is the largest index with `time[j] <= time[i] - 365 days`. |
| `Annualized Δ`           | `Δ × f` where `f` is detected from the median gap between timestamps (≈daily → 252, weekly → 52, monthly → 12, quarterly → 4, semi → 2, annual → 1). |
| `log`                    | `ln(v[i])` for `v[i] > 0` else `null`.                                           |
| `z-score`                | `(v[i] - mean) / std` over the visible series.                                   |
| `Rolling z (252)`        | `(v[i] - rolling_mean_252) / rolling_std_252` with `min_periods=2` over the 252-day window. |
| `Pct rank`               | `0..100` percentile rank of `v[i]` within the visible series (ties get average rank). |
| `YTD Δ`                  | `v[i] - v[anchor]` where `anchor` is the first non-null point of the same calendar year. |
| `Index = 100`            | `v[i] / anchor * 100` where `anchor` is the first non-zero non-null point.       |

The rolling mean for the smoothing knob is computed left-to-right with a fixed-window queue. When the user picks a transform, the y-axis name is auto-tagged with the transform label (`YoY %`, `Δ`, etc.) when every visible series shares the same transform, and a `· Δ` / `· YoY %` / `· z` suffix is appended to each transformed series' legend entry so the chart's units are unambiguous after the change.

**Opt-out.** Set `chart_controls: false` on the spec (or the widget) to suppress the `⋮` button entirely. Useful for sparkline-style chart tiles where the drawer would dominate.

```json
{"widget": "chart", "id": "kpi_spark", "w": 3,
  "spec": {"chart_type": "line", "dataset": "rates",
            "mapping": {"x": "date", "y": "us_2y"},
            "chart_zoom": false, "chart_controls": false}}
```

#### Table drawer

Tables get the same `⋮` toolbar button, opening a drawer with table-specific knobs:

| Knob                | Behavior                                                                                       |
|---------------------|------------------------------------------------------------------------------------------------|
| Search              | Free-text filter; matches any cell substring (case-insensitive). Mirrors `searchable: true` toolbar. |
| Sort by column      | Dropdown of every column + Ascending / Descending. Equivalent to clicking the column header.    |
| Hide columns        | One checkbox per column; unchecked columns are dropped from the rendered table without affecting sort indices or downloads-via-`searchable`-toolbar. |
| Density             | Regular / Compact (mirrors `row_height: "compact"`).                                            |
| Freeze first column | Off / On — pins col 1 with `position: sticky` so wide tables stay readable on horizontal scroll. |
| Decimals            | Auto / 0 / 1 / 2 / 3 / 4 — splices the chosen precision into every numeric column's `format` string at render time, so `number:2` becomes `number:0` etc. Non-numeric formats (`text`, `date`, `link`) are untouched. |
| **View raw**        | Modal with the underlying dataset rows (no formatting). Truncates at 1,000 rows.               |
| **Copy / Download CSV / XLSX** | All honor the current sort + search + visible-column state (so the export matches what the user sees on screen). |
| **Reset table**     | Clears search / hidden / decimals / density / freeze / sort and re-renders.                     |

Suppress with `table_controls: false` on the table widget.

#### KPI drawer

KPI tiles also expose the `⋮` button. Knobs (rendered only when relevant):

| Knob              | Condition                  | Behavior                                                                          |
|-------------------|----------------------------|-----------------------------------------------------------------------------------|
| Compare period    | `sparkline_source` set      | `Auto (delta_source)` / `Previous point` / `1d` / `5d` / `1w` / `1m` / `3m` / `6m` / `1y` / `Year-to-date`. When set to anything other than Auto, the displayed delta is recomputed against the sparkline's time series (looking up the row at the requested offset, falling back to the earliest available point when history is short). |
| Sparkline toggle  | `sparkline_source` set      | Show / Hide. Persists for the session via `KPI_STATE`.                            |
| Delta toggle      | always                      | Show / Hide.                                                                      |
| Decimals override | always                      | Auto / 0 / 1 / 2 / 3 / 4. Overrides `widget.decimals` for the main value.         |
| **View data / Copy / Download CSV / XLSX** | when sparkline-backed | Exposes the underlying time series the KPI is computed from. |
| **Reset KPI**     | always                      | Clears the per-KPI state.                                                         |

Suppress with `kpi_controls: false` on the KPI widget.

#### Inspecting and scripting drawer state

Drawer state is stored on `window.DASHBOARD` for inspection or programmatic manipulation:

```js
window.DASHBOARD.chartControlState['curve'].series['us_10y'].transform = 'yoy_pct';
window.DASHBOARD.chartControlState['curve'].shape = {lineStyleType: 'dashed', step: 'middle'};
window.DASHBOARD.tableState['screener'].hidden = {2: true, 4: true};   // hide cols 2, 4
window.DASHBOARD.kpiState['fed_funds'].comparePeriod = '1m';
// then trigger a redraw via the dropdowns -- the wirers call rerenderChart /
// renderTables / renderKpis automatically on every change event.
```

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

Optional `manifest.header_actions[]` appends custom buttons/links to the header (left of the Refresh / Download PNGs / Download Dashboard / Download Excel buttons). Use for dashboard-specific escape hatches -- docs, related dashboards, run-a-script hooks, etc.

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
| Table row click (auto-default)   | dataset `field_provenance` set, `row_click` not declared | minimal popup with row data + Sources footer. Suppress with `row_click: false`. See 3.6 "Data provenance & source attribution". |
| stat_grid cell                   | `stats[i].info`, `stats[i].popup` | `\u24D8` next to label; click opens modal          |
| Filter control                   | `description` / `help` / `info`, `popup` | `\u24D8` icon next to the filter label      |
| Tab button                       | `tabs[i].description`          | hover tooltip + italic sub-line under tab bar         |
| Header action button             | `header_actions[i].title`      | native browser tooltip                                |
| Chart tile action buttons        | `action_buttons[i].title`      | native browser tooltip                                |
| Chart tooltip (on hover of data) | `spec.tooltip = {...}`         | ECharts tooltip with optional custom formatter        |
| Chart annotation label           | `annotations[i].label`         | permanent label on the annotation                     |
| Chart data-point click           | `click_popup` (simple)         | modal with configurable `popup_fields` (key/value), powered by the row resolver in 3.6 |
| Chart data-point click           | `click_popup.detail.sections[]`| rich drill-down modal, same grammar as table `row_click` rich mode (stats / markdown / per-row charts / sub-tables). See the **Carry & roll scatter** in the `bond_carry_roll` demo. |
| Chart data-point click (auto-default) | dataset `field_provenance` set, `click_popup` not declared | minimal popup with mapped axes + Sources footer. Suppress with `click_popup: false`. |
| Popup Sources footer             | dataset `field_provenance` (auto-appended on every popup) | trailing "Sources" table listing each referenced column's symbol / system / source. Suppress per popup with `show_provenance: false`. |

**Modal behavior** (applies to every click-popup and every table `row_click`):

- X button in the upper-right closes the modal
- ESC key closes the modal
- Clicking on the dim overlay closes the modal
- Only one modal is visible at a time; opening a new popup reuses the same modal element

Markdown in popups uses the shared grammar (3.6). Use sparingly. A dashboard with a `\u24D8` icon on every control is louder than one without.

### 3.12 Runtime features (free for every compiled dashboard)

Everything below is rendered by `compile_dashboard` automatically; PRISM doesn't configure anything extra.

- **Data freshness badge** -- header shows `Data as of YYYY-MM-DD HH:MM:SS UTC` from `metadata.data_as_of` (falls back to `generated_at`). Full second precision; explicit timezone label.
- **Methodology popup** -- header `Methodology` button opens a modal with `metadata.methodology` rendered as markdown. See 3.3.1.
- **Refresh button** -- visible when `metadata.kerberos` + `metadata.dashboard_id` are set and `metadata.refresh_enabled != False`. POSTs `{kerberos, dashboard_id}` to `/api/dashboard/refresh/` (override via `metadata.api_url`), polls `/api/dashboard/refresh/status/?dashboard_id=...` every 3 s up to 3 minutes, then reloads on success. Offline (`file://`) users see an explanatory alert. See Section 4.3.
- **Download PNGs** -- header button exports every chart on the current tab as a separate PNG (2x). Each PNG has the chart's title (and `subtitle`, when set) baked into the canvas in GS type styles, so the export is self-describing in slide decks, vision-model handoffs, or copy-pastes. The compiler normally strips the chart-internal title to avoid double headlines on screen (the tile chrome already shows it); the export path re-injects it for the snapshot, captures via `getDataURL()`, then immediately reverts -- no visual flicker for the user. Charts that already render their own title (`spec.keep_title: True`) are exported untouched.
- **Download Dashboard** -- header button captures the entire current dashboard view (header, tabs, filter bar, currently active tab panel, footer) as a single full-page PNG (2x). Designed for the "drop into a vision model" workflow: open the dashboard, click the button, paste the resulting PNG into PRISM (or any LLM with vision) to get an end-to-end read on what's on the screen. For tabbed dashboards, switch to the tab you want first. Powered by `html2canvas@1.4.1` via CDN, lazy-loaded on first click (~32 KB) so dashboards that never click it pay zero extra cost. The button waits for every chart's ECharts `finished` event before rasterizing, so partial / mid-animation captures are avoided. Filename: `<MANIFEST.id>_YYYY-MM-DD-HH-MM-SS.png`. Open modals are captured as-is (close them first if you want a clean dashboard view); when serving from `file://` Chrome prints a benign one-time `'file:' URLs are treated as unique security origins` console warning that does not affect the export -- it disappears entirely if the dashboard is served over HTTP.
- **Download Excel** -- header button (visible when the dashboard has at least one `widget: table`) packages every table into a single `.xlsx` workbook, one sheet per table. Sheet name is the widget title (truncated to Excel's 31-char limit; auto-uniquified on collision). Rows reflect the user's current filter, search, and sort state, so the export is exactly what's on screen. Powered by SheetJS via CDN (`xlsx@0.18.5`).
- **Per-table XLSX** -- each table widget shows a small `XLSX` button in its toolbar that exports just that table. Set `downloadable: False` on the widget to hide it.
- **Per-tile PNG** -- each chart tile has a `PNG` button in its toolbar (also includes the title / subtitle in the export, same as Download PNGs).
- **Fullscreen tile** -- each chart tile has a fullscreen toggle.
- **Tab persistence** -- last-active tab restored per dashboard id via `localStorage`.
- **Filter reset** -- filter bar includes a Reset button.
- **Brush cross-filter** -- drag-select in one chart filters all linked charts.
- **Chart sync (connect)** -- tooltips / axes / data zoom synchronised across members of a sync group.
- **Row-click modal** -- table rows open a detail modal when `row_click` is configured. When `row_click` is not configured but the dataset carries `field_provenance`, the runtime auto-wires a default popup (row data + Sources footer). Suppress with `row_click: false`.
- **Chart data-point click modal** -- clicking a point on a chart with `click_popup` configured opens the same modal grammar as `row_click`, with the row resolved from the click params (see the row-resolution table in 3.6). Supports both simple (`popup_fields`) and rich (`detail.sections[]`) modes. When `click_popup` is not configured but the dataset carries `field_provenance`, the runtime auto-wires a default popup (mapped axes + Sources footer). Suppress with `click_popup: false`.
- **Sources footer** -- every click popup auto-appends a "Sources" footer rendered from the dataset's `field_provenance` (per-column lineage: symbol, system, source, units, optional recipe). Suppress per popup with `show_provenance: false`. See 3.6 "Data provenance & source attribution".
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
- Optional `field_provenance` on a dataset entry must be a dict mapping column name to a provenance dict. Inner keys are free-form. `row_provenance_field` (string) and `row_provenance` (dict-of-dicts) are validated for shape only.
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
    - `note` requires `body`; `kind` (default `insight`) must be in `{insight, thesis, watch, risk, context, fact}`
- Chart `spec` blocks require `chart_type` (in the 24-type set), `dataset` (must reference a declared dataset), and `mapping` dict. Per-spec `palette` / `theme` overrides must be registered names.
- Chart `click_popup`, when present, must be a dict (mirrors the table `row_click` shape -- `title_field`, `subtitle_template`, `popup_fields`, or `detail.sections[]`) OR boolean `false` to suppress the auto-default provenance popup. Same rule for table `row_click`.
- Filter `targets` must match real chart widget ids (wildcards OK)
- Link members must match real chart widget ids (wildcards OK)
- `sync` values must be in `{axis, tooltip, legend, dataZoom}`
- `brush.type` must be in `{rect, polygon, lineX, lineY}`
- `metadata.refresh_frequency` must be in `{hourly, daily, weekly, manual}`

Returns `(ok, [errors...])`. Each error is a human-readable string identifying the offending path.

### 3.14 Chart-data diagnostics (the second-pass lint)

`validate_manifest` checks structure. **`chart_data_diagnostics(manifest)` checks that the data actually wires up** -- empty datasets, missing columns, all-NaN series, non-numeric value columns, missing required mapping keys for the chart type, filter fields that don't exist in the target widget's dataset, dataset shape mistakes (DatetimeIndex without `date` column, MultiIndex columns, opaque-code names, tuple-instead-of-DataFrame), and dataset / manifest size budget violations. Designed for PRISM iteration loops: the LLM compiles, reads diagnostics, fixes specific findings, recompiles.

```python
from echart_dashboard import compile_dashboard, chart_data_diagnostics

# Run as a standalone lint (no HTML produced)
diags = chart_data_diagnostics(manifest)
for d in diags:
    print(d.severity, d.code, d.widget_id, d.message)

# Default behavior: raise on any error-severity diagnostic. This is
# the "production" mode; a broken headline number or missing column
# is an error, full stop.
r = compile_dashboard(manifest)   # raises ValueError on error diags

# Iteration mode: keep going through errors so PRISM can fix them all
# in one round-trip. Broken charts get a "(no data)" placeholder, KPI
# tiles render '--', diagnostics carry every finding.
r = compile_dashboard(manifest, strict=False)
for d in r.diagnostics:
    print(d.to_dict())
```

**Strict mode** (`compile_dashboard(strict=True)`, the default) raises a `ValueError` listing every error-severity diagnostic instead of returning a `DashboardResult`. The opt-in `strict=False` keeps the resilient inner-loop model so PRISM can fix all findings in one round-trip; refresh pipelines and CI rely on the strict default so a budget breach, KPI source typo, or shape mistake hard-fails before the HTML gets published. Warnings + info diagnostics never trigger strict-mode failure.

The strict default flipped from `False` to `True` after production was discovered to be shipping dashboards with KPI tiles rendering `--` because the diagnostic layer was either silent or non-blocking. The new contract: a broken headline number is a broken dashboard.

**Shape diagnostics require pre-normalize DataFrame snapshots**, captured automatically by `compile_dashboard` and `render_dashboard`. The standalone `chart_data_diagnostics(manifest)` and the `diagnose` CLI work on already-normalised manifests (e.g. JSON files), so they emit binding + size diagnostics but skip shape codes -- shape mistakes are caught only when DataFrames flow through the live compile path.

`Diagnostic` is a structured dataclass with `severity` (`error` / `warning` / `info`), stable `code`, `widget_id`, dotted manifest `path`, `message`, and a `context` dict carrying actionable repair data (e.g. `available_columns`, `nan_fraction`, `required_alternatives`, `did_you_mean`, `fix_hint`).

**Actionable repair context.** Most codes carry two PRISM-friendly keys:

* `did_you_mean` -- close-match suggestions for typo'd column / dataset names (case-insensitive + difflib). Fires for `chart_mapping_column_missing`, `table_column_field_missing`, `kpi_source_column_missing`, `kpi_source_dataset_unknown`, `filter_field_missing_in_target`.
* `fix_hint` -- one-sentence repair instruction. Set on every code where the repair is unambiguous. Surfaced in the human-readable `_print_diagnostics` output as an indented `-> fix:` line under each diagnostic.

**Stable diagnostic codes** -- pattern-match on `code` for automated repair:

| Code | Severity | Fires when |
|---|---|---|
| `chart_dataset_empty` | error | Chart's dataset has 0 rows |
| `chart_dataset_single_row` | warning | Series chart (line/area/bar/scatter) has only 1 row |
| `chart_mapping_required_missing` | error | chart_type's required mapping key is absent (e.g. pie needs `category`+`value`); `context.required_keys` lists all required for the type |
| `chart_mapping_column_missing` | error | mapping references a column not in the dataset; `context.available_columns` + `did_you_mean` |
| `chart_mapping_column_all_nan` | error | mapping column exists but every value is NaN/None |
| `chart_mapping_column_mostly_nan` | warning | mapping column is >=50% NaN; `context.nan_fraction` is the exact ratio |
| `chart_mapping_column_non_numeric` | error | mapping key requires numeric values (y/value/size/weight/low/high/open/close) but the column isn't numeric-coercible; `context.sample_values` shows the offending strings |
| `chart_constant_values` | warning | numeric y column has a single unique value across all rows; chart renders as a flat line. Suggests switching to `kpi`/`gauge` or picking a column with variance |
| `chart_negative_values_in_portion` | error | pie/donut/funnel/sunburst/treemap value column contains negative values; ECharts renders these as 0 or reversed arcs |
| `chart_sankey_self_loops` | error if 100%, warning otherwise | sankey edges where source==target; renders as disconnected stubs |
| `chart_sankey_disconnected` | warning | source/target sets share no nodes; only a one-step bipartite flow is possible |
| `chart_candlestick_inverted` | error | OHLC inversions detected (high<low, open>high, etc.); `context.inversions` enumerates which type and how many |
| `chart_tree_orphan_parents` | error | `mapping.parent` values that don't appear in `mapping.name`; orphan rows won't render |
| `chart_build_failed` | error | builder raised at compile time; `context.exception_type` + the message carry the cause |
| `table_dataset_empty` | warning | table's `dataset_ref` has 0 rows |
| `table_column_field_missing` | error | `columns[].field` is not in the dataset; carries `did_you_mean` |
| `table_columns_all_missing` | error | EVERY defined column is missing from the dataset (one aggregate diagnostic instead of N near-identical ones); fired alongside the per-column diagnostics |
| `kpi_no_value_no_source` | error | KPI tile has neither `value` nor `source`; the runtime would render `--` |
| `kpi_value_is_placeholder` | error | `value` is a literal placeholder string (`--`, `n/a`, etc.) -- ship a real value or bind a source |
| `kpi_source_malformed` | error | `source` / `delta_source` is not in `dataset.aggregator.column` form (3 parts), or `sparkline_source` is not `dataset.column` (2 parts) |
| `kpi_source_dataset_unknown` | error | KPI source references an undeclared dataset; carries `did_you_mean` |
| `kpi_source_aggregator_unknown` | error | aggregator segment isn't in the runtime allow-list (`latest` / `first` / `sum` / `mean` / `min` / `max` / `count` / `prev`); carries `did_you_mean` |
| `kpi_source_column_missing` | error | KPI source column is not in its dataset; carries `did_you_mean` |
| `kpi_source_no_numeric_values` | error | KPI source column has zero numeric values (all-string OR all-NaN); the JS resolver returns null and the tile shows `--` |
| `kpi_sparkline_too_short` | warning | `sparkline_source` has <2 numeric values; sparkline can't render as a line |
| `stat_grid_no_value_no_source` | error | stat_grid cell has neither `value` nor `source`; cell would render `--` |
| `stat_grid_value_is_placeholder` | error | stat_grid `value` is a placeholder string |
| `stat_grid_source_unresolvable` | error | stat_grid `source` points at a dataset/column/aggregator the compile-time resolver cannot turn into a number |
| `filter_field_missing_in_target` | error | filter `field` is not a column in any of the target widgets' datasets; the filter would silently filter nothing |
| `filter_default_not_in_options` | warning | `default` is not in `options` for select/multiSelect/radio filters |
| `dataset_dti_no_date_column` | error | dataset DataFrame has a `DatetimeIndex` and no `date` column AND a chart/filter on this dataset references `date`; fires when PRISM forgets `df.reset_index()` (the compiler does NOT auto-reset). `context.fix_hint` carries the literal pandas snippet. |
| `dataset_passed_as_tuple` | error | dataset is a Python tuple instead of a DataFrame -- catches the `pull_market_data` "didn't unpack `(eod_df, intraday_df)`" mistake |
| `dataset_columns_multiindex` | error | DataFrame columns is a `pd.MultiIndex`; the compiler does not auto-flatten. `context.fix_hint` shows the join snippet |
| `dataset_column_looks_like_code` | warning | a column name referenced by a widget matches a known opaque-code pattern (Haver `X@Y`, coordinates `IR_USD_*`, whitespace, slashes); the legend / tooltip / table header reads it verbatim. PRISM should rename to plain English using `df.attrs['metadata']` |
| `dataset_metadata_attrs_unused` | info | DataFrame has `df.attrs['metadata']` (from a pull function) AND its columns still match the raw codes inside that metadata; suggests building a rename map from attrs |
| `filter_targets_no_match` | warning | every non-wildcard `targets` pattern resolves to no widget id; the filter is a no-op |
| `dataset_rows_warning` | warning | dataset has >= 10,000 rows; consider whether this much history is necessary (daily-10y is ~2,500) |
| `dataset_rows_error` | error | dataset has >= 50,000 rows; embedding this much in the HTML produces multi-MB payloads. Repair via top-N filter, shorter lookback, or lazy-load API (DATA_SHAPES Section 17) |
| `dataset_bytes_warning` | warning | dataset serialises to >= 1 MB |
| `dataset_bytes_error` | error | dataset serialises to >= 2 MB; the HTML payload will be sluggish to load |
| `manifest_bytes_warning` | warning | total dataset bytes across all of `manifest.datasets` >= 3 MB |
| `manifest_bytes_error` | error | total dataset bytes >= 5 MB; compiled HTML exceeds practical browser-load thresholds |
| `table_rows_warning` | warning | a dataset consumed by a table widget has >= 1,000 rows (the table widget renders every row to the DOM) |
| `table_rows_error` | error | a dataset consumed by a table widget has >= 5,000 rows; table will be unusable to scroll |

**CLI: `diagnose` subcommand** -- lint a manifest without compiling. Useful for tight inner loops where PRISM wants to validate-then-decide before paying the render cost.

```bash
# Human-readable, grouped by severity, exit code = 1 if any errors
python echart_dashboard.py diagnose path/to/manifest.json

# JSON-lines (one diagnostic per line) -- pipe into jq / grep / log scrapers
python echart_dashboard.py diagnose path/to/manifest.json --json

# Filter by severity (error | warning | info)
python echart_dashboard.py diagnose manifest.json --severity error

# `compile` accepts the same JSON-lines emit on stderr:
python echart_dashboard.py compile manifest.json -o out.html --diagnostics-json
```

Both `compile_dashboard` and `render_dashboard` are **resilient by design**: a chart that fails to build (missing column, malformed mapping, builder raise) gets a `(no data)` placeholder option and a `chart_build_failed` diagnostic. The dashboard still renders, sibling charts still work, and PRISM gets the full failure list in one round-trip instead of fixing one error and recompiling to discover the next.

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

sys.path.insert(0, '/ai_development/dashboards')
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

# Compile -- writes HTML + manifest to the dashboard folder on S3.
# strict=True hard-fails on any error-severity diagnostic (size budget,
# missing column, dataset shape mistake) so a broken dashboard never
# gets published to S3.
r = compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html',
                       strict=True)
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
| Chart shows "(no data)" placeholder | A specific chart spec failed to bind to data              | Read `compile_dashboard().diagnostics` or run `python echart_dashboard.py diagnose <manifest>`; the diagnostic carries the exact column / dataset that's missing (Section 3.14) |
| Several blank tiles after refresh   | Schema drift introduced missing columns or all-NaN cols   | Same -- diagnostics surface every binding failure in one pass |

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

## 5. When to build a dashboard (vs an Altair chart)

This module ships **dashboards only**. Reach for it when the analyst needs:

| Need                                                                | Build                                                                                  |
|---------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Multi-chart interactive HTML the user navigates                     | `compile_dashboard(manifest, session_path=...)` -- session-only artifact               |
| Persistent, refreshable, user-owned monitor                         | `compile_dashboard(manifest, ...)` then persist to `users/{kerberos}/dashboards/{name}/` (Section 4) |
| Report / email PNG snapshot of a compiled dashboard                 | `compile_dashboard(..., save_pngs=True)` for per-widget PNGs, or the browser-side `Download Dashboard` button |
| One-off chart PNG (chat, email, single-chart export)                | **Not this module** -- use Altair via `make_chart()` (separate module)                 |
| Pre-built single chart re-displayed inside a dashboard tile         | Express it as a `widget: chart` in a dashboard manifest -- the spec format is the same as `make_echart` mappings |

Section 3 covers manifests + widgets + filters + links. Section 4 covers persistence + the refresh pipeline. The chart-type catalogue (Section 2.3), mapping keys (Section 2.4), annotations (Section 2.5), and cosmetic knobs (Section 2.2) all apply to dashboard chart widgets verbatim.

---

## 6. Common chart-spec patterns

> Every snippet below is a **dashboard chart-widget `spec`** -- the same mapping keys, formatters, and annotation forms documented in Section 2 work verbatim inside a `widget: chart` block. PRISM only ships these by embedding them in a manifest passed to `compile_dashboard()`. The historical `make_echart()` calls have been replaced with the equivalent dashboard-widget shape.

### 6.1 Wide-form `multi_line` (fastest)

```json
{"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
  "title": "UST curve",
  "spec": {"chart_type": "multi_line", "dataset": "rates",
            "mapping": {"x": "date",
                          "y": ["us_2y", "us_5y", "us_10y", "us_30y"],
                          "y_title": "Yield (%)"}}}
```

### 6.2 Long-form `multi_line` with color

`datasets["rates_long"] = df.melt(id_vars=['date'], var_name='series', value_name='yield')`

```json
{"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
  "title": "UST curve",
  "spec": {"chart_type": "multi_line", "dataset": "rates_long",
            "mapping": {"x": "date", "y": "yield", "color": "series",
                          "y_title": "Yield (%)"}}}
```

### 6.3 Actuals vs estimates via `strokeDash`

```json
{"widget": "chart", "id": "capex", "w": 12, "h_px": 380,
  "title": "Big Tech capex",
  "subtitle": "solid = actual, dashed = estimate",
  "spec": {"chart_type": "multi_line", "dataset": "capex",
            "mapping": {"x": "date", "y": "capex", "color": "company",
                          "strokeDash": "type",
                          "y_title": "Capex ($B)"}}}
```

### 6.4 Dual axis

```json
{"widget": "chart", "id": "spx_ism", "w": 12, "h_px": 380,
  "title": "Equities vs ISM",
  "spec": {"chart_type": "multi_line", "dataset": "macro",
            "mapping": {"x": "date", "y": "value", "color": "series",
                          "dual_axis_series": ["ISM Manufacturing"],
                          "y_title": "S&P 500",
                          "y_title_right": "ISM Index",
                          "invert_right_axis": false}}}
```

Before dual-axis, print `df_long['series'].unique()` and assert the right-axis name is present. Name mismatch is the #1 failure mode.

### 6.5 Scatter with trendline

```json
{"widget": "chart", "id": "phillips", "w": 6, "h_px": 380,
  "title": "Phillips curve by decade",
  "spec": {"chart_type": "scatter", "dataset": "phillips",
            "mapping": {"x": "unemployment", "y": "cpi", "color": "decade",
                          "trendlines": true,
                          "x_title": "U-rate (%)", "y_title": "Core CPI YoY (%)"}}}
```

### 6.6 `scatter_studio`: interactive bivariate explorer

`scatter_studio` is the answer when the analyst wants to *pick* X and Y rather than have them pinned. Author whitelists the columns the viewer is allowed to plot; everything else (dropdowns, per-axis transforms, OLS line, Pearson r / R^2 / beta / p-value strip, window slicer, outlier filter) wires automatically. State lives in `chartControlState[cid].studio`; filters that target the studio's dataset_ref recompute the option from the filtered rows.

```json
{"widget": "chart", "id": "yields_vs_breakevens", "w": 12, "h_px": 480,
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
      "transforms": ["raw", "log", "pct_change", "yoy_pct", "zscore",
                      "rolling_zscore_252", "rank_pct"],
      "regression": ["off", "ols", "ols_per_group"],
      "show_stats": true
    }}}
```

The viewer's controls drawer (the `⋮` button on the chart tile) opens to:

| Studio knob              | Reads from                                     | Behavior |
|--------------------------|------------------------------------------------|----------|
| X axis                   | `mapping.x_columns`                            | Numeric column dropdown. |
| Y axis                   | `mapping.y_columns`                            | Numeric column dropdown. |
| Color                    | `mapping.color_columns`                        | Categorical group dropdown (with "— none —" option). |
| Size                     | `mapping.size_columns`                         | Numeric column for bubble size. |
| Per-axis transform       | `studio.transforms`                            | `Raw` / `log` / `Δ` / `%Δ` / `YoY %` / `z-score` / `Rolling z (Nd)` / `pct rank`. Applied independently to X and Y. |
| Window                   | `studio.windows` (only when `order_by` set)    | `All` / `252d` / `504d` / `5y` (or any `<digits>d` / `<digits>y` value). |
| Outliers                 | `studio.outliers`                              | `Off` / `IQR × 3` / `\|z\| > 4`. Applied AFTER transform. |
| Regression               | `studio.regression`                            | `Off` / `OLS` / `OLS per color`. |
| X-scale / Y-scale        | universal axis toggles                         | Linear / Log. |

Stats strip below the canvas reports `n`, Pearson `r` (with significance stars `***` / `**` / `*` / `·`), `R^2`, slope `β` and its standard error, intercept `α`, RMSE, and p-value. With `OLS per color` the strip also lists per-group `r` / `R^2` / `β` / `n`. Stars: `***` p<0.001, `**` p<0.01, `*` p<0.05, `·` p<0.10. p-value uses the normal-approximation tail of the t-statistic — adequate for display, not for citation.

Edge cases handled by the runtime:
- `n < 2` after window / outlier filtering → strip prints `n<2 — regression unavailable`.
- Selected X column has zero variance after transform → strip prints `zero x-variance, regression undefined`; the OLS line is suppressed.
- `log` transform on a column with non-positive values → those rows are dropped; the strip's `n` is the post-drop count.

### 6.7 `correlation_matrix`: N x N heatmap from a column list

Use when the question is "how do these N series co-move." The builder applies a per-column transform (so you can correlate `% changes` instead of levels), computes the correlation matrix, and emits a diverging heatmap pinned to `[-1, 1]`.

```json
{"widget": "chart", "id": "rates_corr", "w": 6, "h_px": 380,
  "spec": {
    "chart_type": "correlation_matrix",
    "dataset": "rates_panel",
    "title": "Rates correlation (% change)",
    "mapping": {
      "columns":        ["us_2y", "us_5y", "us_10y", "us_30y",
                          "real_10y", "breakeven_5y5y"],
      "method":         "pearson",
      "transform":      "pct_change",
      "order_by":       "date",
      "min_periods":    30,
      "show_values":    true,
      "value_decimals": 2
    }}}
```

Mapping keys:

| Key              | Purpose                                                                 |
|------------------|-------------------------------------------------------------------------|
| `columns`        | List of numeric column names, `len >= 2`. Required.                     |
| `method`         | `'pearson'` (default) or `'spearman'` (rank correlation; robust to monotonic non-linearity). |
| `transform`      | Per-column transform applied before correlation. Default `'raw'`. Same names as `scatter_studio`. |
| `order_by`       | Required when `transform` is order-aware (`pct_change` / `yoy_pct` / `change` / `rolling_zscore_*`). Default: first datetime-like column. |
| `min_periods`    | Minimum number of overlapping non-null pairs to report a correlation. Default 5. Cells below render blank. |
| `show_values`    | Bool, default `True`. Print the correlation in each cell.               |
| `value_decimals` | Int, default 2.                                                          |

When to pick `correlation_matrix` vs `heatmap`:
- `correlation_matrix` when the data is a wide-form time-series panel and the chart's job is to summarise pairwise co-movement. The author specifies columns; the builder owns the math, the visualMap, and the `[-1, 1]` bounds.
- `heatmap` when each cell is a distinct bivariate measurement (e.g. cross-asset returns by month-of-year, hit-rate by quintile-bucket). The author hands the builder pre-computed cell values.

### 6.8 Bullet: rates RV screen

`datasets["rv"] = pd.DataFrame({"metric": [...], "current": [...], "low_5y": [...], "high_5y": [...], "z": [...], "pct": [...]})`

```json
{"widget": "chart", "id": "rv_screen", "w": 6, "h_px": 480,
  "title": "Rates RV screen",
  "spec": {"chart_type": "bullet", "dataset": "rv",
            "mapping": {"y": "metric", "x": "current",
                          "x_low": "low_5y", "x_high": "high_5y",
                          "color_by": "z", "label": "pct"}}}
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

The compiler consumes tidy DataFrames; it does NOT auto-coerce input shape. PRISM owns the cleaning step. Five mistakes the compiler refuses to silently fix (and what each diagnostic is named):

| What PRISM must do | Diagnostic if skipped |
|---|---|
| `df.reset_index()` before passing a DatetimeIndex-keyed frame | `dataset_dti_no_date_column` |
| Unpack `pull_market_data` tuples: `eod_df, _ = pull_market_data(...)` | `dataset_passed_as_tuple` |
| Flatten MultiIndex columns: `df.columns = ['_'.join(c) for c in df.columns]` | `dataset_columns_multiindex` |
| Rename opaque API codes to plain English (use `df.attrs['metadata']`) | `dataset_column_looks_like_code` (warning) |
| Resample to native frequency per series | mixed-freq NaN gaps render as broken stair-steps |

`DATA_SHAPES.md` Section 6 walks the full pull-to-manifest pipeline including the `df.attrs['metadata']`-driven rename pattern; Section 17 covers the size budget.

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
| `make_echart()` or composite calls in PRISM-shipped artifacts | Use `compile_dashboard()` from this module for interactive analysis; use Altair `make_chart()` for one-off chart PNGs. The `make_echart` / composite helpers are internal builders only. |
| `matplotlib` / `plotly` / hand-rolled HTML charts        | Same -- one path: dashboards here, PNGs via Altair         |
| Source attribution in title/subtitle                      | Keep it in `metadata.sources`              |
| Annotating self-evident facts (zero line on a spread)     | Omit                                       |
| `np.zeros()` fill when data is missing                    | Skip the panel or add a text note          |
| Positive/negative color on bar charts                     | Bar's position vs zero already conveys sign |
| Horizontal rules on bar charts                            | Put threshold in title/subtitle/narrative  |
| Hand-tuning `y_title_gap` / `grid.left` to dodge a long-label collision | Just set `x_title` / `y_title` and let the compiler size from real label widths; only override when the auto value is wrong |
| Setting `axisLabel.show: false` to hide overflowing categories | Set `category_label_max_px` (or accept the 220 px default) -- labels truncate with an ellipsis and stay readable |
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
- [ ] Each dataset is cleaned before passing: `df.reset_index()` for DTI-keyed frames, plain English column names, no MultiIndex (DATA_SHAPES Section 6)
- [ ] Each dataset is under the size budget: < 50K rows, < 2 MB serialised; total manifest < 5 MB (DATA_SHAPES Section 17)
- [ ] `build.py` is thin (loads data + `populate_template` + `compile_dashboard`, nothing else)
- [ ] Refresh `build.py` calls `compile_dashboard(..., strict=True)` so size / shape errors hard-fail before publication
- [ ] Download link delivered to the user

---

## 12. CLI

Running any script without arguments launches its interactive menu. Argparse mirrors every option for non-interactive / CI use.

```
# Primary CLI -- the dashboard compiler (PRISM-facing path)
python echart_dashboard.py                                    # interactive menu
python echart_dashboard.py compile manifest.json -o out.html --open
python echart_dashboard.py compile manifest.json -s SESSION_DIR
python echart_dashboard.py compile manifest.json -o out/dash.html --pngs
python echart_dashboard.py validate manifest.json
python echart_dashboard.py diagnose manifest.json [--json] [--severity error]
python echart_dashboard.py demo
python echart_dashboard.py list widgets|filters|links|chart_types

# End-to-end demo gallery (all dashboard scenarios)
python demos.py                                   # interactive menu
python demos.py --all                             # run every demo
python demos.py --demo news_wrap                  # run one demo
python demos.py --list                            # list demos and exit
python demos.py --all --open                      # run all, auto-open gallery

# Internal-builder CLI (developers / tests; not used by PRISM artifacts)
python echart_studio.py                        # interactive menu (single-chart builder)
python echart_studio.py wrap spec.json --open  # wrap JSON to HTML
python echart_studio.py demo --matrix          # 23 samples x 5 themes
python echart_studio.py list types|themes|palettes|dimensions|knobs|samples
python echart_studio.py info spec.json         # summarize a spec file
python echart_studio.py test                   # run unit tests
python echart_studio.py png option.json -o chart.png --scale 2
```

`demos.py` bundles 14 end-to-end **dashboard** scenarios that collectively exercise every PRISM-facing capability in the stack -- 26 chart types, 8 widget kinds, 9 filter types, 4 brush types, 4 sync values, 5 annotation types, 3 chart-widget variants (`spec` / `ref` / `option`), persistence + diagnostics workflow, and the prose / markdown surfaces.

**Chart-driven**

| Name                  | Highlights                                                                                                        |
|-----------------------|-------------------------------------------------------------------------------------------------------------------|
| `rates_monitor`       | 8-tab rates monitor (US curve + 5 global central banks), brush, dual-axis, gauges, summary banner + 4 note kinds |
| `risk_regime`         | `correlation_matrix` (dedicated builder), `scatter_multi`, VIX term by regime, factor boxplots, drawdown band     |
| `fomc_monitor`        | Cut-prob gauge, FFR candlestick, dot-plot strokeDash, voter radar, decision calendar, `arrow` annotation          |
| `global_flows`        | Cross-border sankey + donut, treemap + sunburst, network graph, mandate funnel, hierarchical `tree`               |
| `equity_deep_dive`    | Single-name tear sheet: candlestick, EPS strokeDash, beta scatter-trendline, bullet; `y_log` toggle               |
| `portfolio_analytics` | Multi-asset book: VaR gauge, factor radar, allocation pie, parallel_coords, histogram; `pinned` KPI ribbon, `kv` section |
| `markets_wrap`        | 17-chart cross-asset wrap, click-emit-filter, conditional-formatted top movers; `image` widget, `divider`s, `legend` sync, filter `"*"` wildcard |
| `screener_studio`     | Three-tab toolbox: rich RV screen, all 9 filter types, bond drilldown w/ rich modal; `dateRange mode="filter"`    |
| `bond_carry_roll`     | Carry/roll scatter where every point is clickable: chart `click_popup` rich modal (per-bond stats, issuer blurb, spread + price history filtered to that CUSIP, recent events). Plus simple-mode click popups on a top-10 bar and a sector summary chart. |
| `macro_studio`        | Exploratory bivariate analysis: `scatter_studio` centerpiece (interactive X/Y/color/size, transforms, regression, stats strip), correlation_matrix on % changes, `mapping.axes` 4-axis macro overlay, polygon brush |

**Text-heavy** (built around the prose surface area: see 3.3.2, 3.6)

| Name             | Highlights                                                                                          |
|------------------|-----------------------------------------------------------------------------------------------------|
| `news_wrap`      | Intraday news desk: summary banner + all six note kinds + sortable headlines table with full-body markdown drilldown + per-asset commentary tiles + reading list |
| `fomc_brief`     | Document-first FOMC dashboard: statement-diff prose, minutes excerpts (verbatim blockquotes by topic), speakers quote-board with row-click verbatim modal, dot-plot panel with desk commentary |
| `research_feed`  | Substack-style aggregator: featured + theme notes, full article feed with row-click drilldown surfacing each piece's full markdown body (h2/h3/ordered lists/blockquotes/tables/strikethrough) |

**Workflow / diagnostics**

| Name           | Highlights                                                                                                        |
|----------------|-------------------------------------------------------------------------------------------------------------------|
| `dev_workflow` | Lifecycle showcase: `manifest_template` + `populate_template`, `validate_manifest` output, `chart_data_diagnostics` output (rendered into markdown widgets), `compile_dashboard(strict=False)` mode, `save_pngs=True`, `raw` chart_type, `option` chart variant, `header_actions` `onclick`, KPI direct-value/`format=raw`, opt-out flags (`chart_zoom`, `chart_controls`, `table_controls`, `kpi_controls`) |

### Gallery + thumbnails

Each `python demos.py --all` run writes a fresh `output/<timestamp>/` snapshot. Old runs are kept in place so successive runs accumulate (archive them by hand from `output/` when you want to clean up). The runner emits two top-level files plus one folder per demo:

```
output/20260424_233640/
├── gallery.html              <- card-grid index page
├── index.json                <- machine-readable run manifest (one entry per demo)
├── rates_monitor/
│   ├── dashboard.html        <- interactive
│   ├── dashboard.json        <- compiled manifest
│   └── thumbnail.png         <- screenshot shown on the gallery card
├── risk_regime/
│   └── ... (same shape)
└── ... (one folder per demo in DEMO_REGISTRY)
```

**How thumbnails are produced.** After each dashboard compiles, `_thumbnail()` in `demos.py` calls `rendering.save_dashboard_html_png(html_path, png_path, width=W, height=H, scale=1)`. That helper drives headless Chrome (`chrome --headless=new --window-size=W,H --virtual-time-budget=4500ms --screenshot=...`) against the local HTML file and writes one PNG per dashboard. Each demo passes its own `(width, height)` tuned to the layout -- `1500x1300` for `rates_monitor`, `1500x1100` for `risk_regime`, up to `1500x2400` for the 17-chart `markets_wrap`. The viewport is fixed; pick a `height` that comfortably exceeds the dashboard's full pixel height or the bottom is clipped. `scale=1` keeps the PNG light enough for an inline gallery card; bump to `2` (or use `compile_dashboard(save_pngs=True, png_scale=2)` for per-widget assets) when you need report-quality output.

**How `gallery.html` is composed.** `_gallery_html()` emits a self-contained, GS-branded card-grid page (header bar, summary pills for engine / theme / palettes / pass count, then a responsive grid of cards). One card per `index.json` entry:

| Card region   | Content                                                                                  |
|---------------|------------------------------------------------------------------------------------------|
| header        | demo title (red `FAILED` prefix if the build raised) + kind badge (`dashboard` / `error`) |
| body          | `<img>` pointing at the relative `thumbnail.png`, or a "PNG not generated (Chrome unavailable?)" placeholder |
| description   | the one-line scenario blurb from `DEMO_REGISTRY[name]["description"]`                    |
| actions       | `Open interactive` (HTML), `PNG`, `JSON manifest` -- plus the demo `name` and `elapsed_s` |

All `href` targets in the cards are relativized against `out_root` via `_rel()`, so the timestamp folder is fully portable -- zip it, send it to someone, the gallery still renders without absolute path rewrites.

**`index.json` is the programmatic companion.** Same one entry per demo, with absolute paths preserved (handy when feeding the run into a downstream eval). Each entry carries `html`, `png`, `manifest`, `success`, `warnings`, `title`, `description`, `kind`, `name`, `elapsed_s`. CI can diff `index.json` across runs to flag regressions -- a flipped `success`, a new entry in `warnings`, or a sudden 5x jump in `elapsed_s`.

**Caveats.**

- Chrome must be discoverable by `rendering.find_chrome()` (`CHROME_PATH` env var or platform-default). If Chrome is missing the dashboard build still succeeds (HTML / JSON are written), but the `_thumbnail` call prints a warning, the card on `gallery.html` shows the placeholder, and `index.json` records `png: null`.
- The viewport is fixed at the supplied `(width, height)`; full scroll-height auto-detect is not supported on the server-side path. For a true full-page capture use the browser-side `Download Dashboard` button (Section 2.9.2) instead.
- The runner heart-beats with `_heartbeat()` every five seconds (`... running <name> (Ns elapsed)`), so long demos like `rates_monitor` (eight tabs) and `markets_wrap` (17 charts) don't appear hung even when Chrome is taking its time on the screenshot.

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
2. Add a fluent `<Name>Ref` dataclass alongside `MarkdownRef` / `NoteRef` for ergonomic Python construction (optional but recommended).
3. Add the renderer in `rendering.py` PART 2 (dashboard HTML). For text/prose widgets that's just a static HTML branch in `_render_widget`; for interactive widgets you also need runtime JS that wires up data flow.
4. Add CSS in `rendering.py` -- if the widget renders prose, attach `.markdown-body` to its body div so it inherits the shared typography rules instead of redefining them.
5. Add tests in `tests.py` (validator + renderer) and at minimum one demo in `demos.py` exercising the widget end-to-end.
6. Document the widget in section 3.5 (registry table) + 3.6 (per-widget detail) of this README.

---

## 14. Testing

`tests.py` is the single entry point for both unit tests and stress tests, with a nested interactive CLI by default and explicit subcommands for non-interactive runs.

```
python tests.py                          # interactive top-level menu
python tests.py unit                     # all unit tests
python tests.py TestThemes               # one unit-test class (forwarded to unittest)
python tests.py TestMarkdownGrammar      # markdown grammar parity tests
python tests.py TestNoteWidget           # note widget validation + rendering
python tests.py TestSummaryBanner        # metadata.summary banner injection
python tests.py -v                       # verbose unit-test run
python echart_studio.py test             # shortcut: runs the unit-test suite

python tests.py stress                   # stress-test sub-menu (interactive)
python tests.py stress --all             # run every stress scenario
python tests.py stress --scenario nan_blizzard
python tests.py stress --list            # list scenarios + descriptions
```

The sample matrix (23 chart samples + dashboard fixtures) runs as part of `TestSamplesMatrix`. Demos in `demos.py` are integration tests with visual outputs; rerun them after behavioural changes to `rendering.py` and inspect the generated `gallery.html`.

The stress-test side is a battery of deliberately-broken-but-validating dashboards used to audit the diagnostic system. Each scenario produces a manifest that passes `validate_manifest` but renders empty or broken charts due to data issues (column typos, NaN columns, type mismatches, missing required mappings, degenerate distributions, broken filter wires, etc.). `python tests.py stress --all` writes every scenario's HTML + manifest + diagnostics to `output/stress_<timestamp>/`. The aggregate `stress_report.txt` rolls up which diagnostic codes fired across the suite -- if a regression silently swallows a class of failures, the roll-up shrinks. Detailed unit coverage lives in `TestStressDiagnostics`.

---

## 15. File reference

```
ai_development/dashboards/
  config.py             GS brand tokens, theme, palettes, dimensions
  echart_dashboard.py   compile_dashboard, manifest validator,
                          manifest_template / populate_template, Dashboard builder
                          (PRISM-FACING ENTRY POINT)
  echart_studio.py      make_echart, wrap_echart, EChartResult
                          (INTERNAL: used by the dashboard compiler for chart widgets)
  composites.py         make_2pack_*, make_3pack_triangle, make_4pack_grid,
                          make_6pack_grid (LEGACY: not used by PRISM)
  rendering.py          single-chart editor HTML + dashboard HTML +
                          dashboard runtime JS + PNG export
  samples.py            chart + dashboard samples + PRISM roleplay demos
  demos.py              end-to-end dashboard demo scenarios + CLI + gallery
  inspect_dashboard.py  visual diagnostics for compiled dashboards
  tests.py              unit tests + stress tests (deliberately-broken
                          dashboards stress-testing compile_dashboard
                          error logs); interactive + argparse CLI
  README.md             this file
```

For programmatic exploration of every supported capability:

```
python ai_development/dashboards/echart_dashboard.py                 # interactive CLI
python ai_development/dashboards/echart_dashboard.py demo            # render every sample
python ai_development/dashboards/samples.py --all                    # chart gallery
python ai_development/dashboards/tests.py                            # interactive runner
python ai_development/dashboards/tests.py unit                       # all unit tests
python ai_development/dashboards/tests.py stress --all               # all stress scenarios
```
