# echarts

JSON-first ECharts producer + dashboard compiler for PRISM. Callers emit a
manifest (dict or JSON) or, for single charts, a DataFrame + mapping; the
compiler writes a fully-interactive HTML document alongside the persisted
manifest.

**Design rule: callers never write HTML.** PRISM emits structured JSON; the
compiler does everything else.

```
GS/viz/
  chart_studio.py       (Altair, existing, UNCHANGED)
  chart_functions.py    (PRISM make_chart, existing, UNCHANGED)
  echarts/              <- this folder
    config.py             GS brand tokens + one theme + 3 palettes + dims
    echart_studio.py      single-chart producer: builders + knobs + CLI
    echart_dashboard.py   dashboard compiler: manifest validator + CLI
    composites.py         multi-grid layouts (2/3/4/6-pack composition)
    rendering.py          HTML templates + headless-Chrome PNG export
    samples.py            chart + dashboard sample registry (test fixtures)
    demos.py              5 consolidated end-to-end demo scenarios + CLI
    tests.py              all tests (171 total)
    README.md             this file
    archive/              legacy files kept for reference
```

`rendering.py` merges what used to be three separate files: the single-chart
editor HTML template, the dashboard HTML template, and the PNG-export
module. See the `PART 1 / PART 2 / PART 3` banners inside it. The public
interface is a single import surface:

```python
from rendering import (
    render_editor_html, render_dashboard_html,
    save_chart_png, save_dashboard_pngs, save_dashboard_html_png,
    find_chrome,
)
```

There is exactly one visual style, the Goldman Sachs brand: GS Navy
`#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans typeface stack,
thin grey grid on paper-white. No theme switcher, no alternates.

## Table of contents

1. [Quick start](#quick-start)
2. [Style config (one file, one theme)](#style-config-one-file-one-theme)
3. [PNG export (Python-side)](#png-export-python-side)
4. [Chart types](#chart-types)
5. [Dashboard manifest](#dashboard-manifest)
6. [Widgets](#widgets)
7. [Filters](#filters)
8. [Links (connect + brush)](#links-connect--brush)
9. [Datasets](#datasets)
10. [Validation](#validation)
11. [CLI](#cli)
12. [PRISM integration](#prism-integration)
13. [Extending](#extending)
14. [Testing](#testing)

---

## Quick start

### Dashboard (JSON-first, PRISM's preferred shape)

```python
from echart_dashboard import compile_dashboard

manifest = {
    "schema_version": 1,
    "id": "rates_daily",
    "title": "US Rates Daily",
    "theme": "gs_clean",
    "datasets": {
        "rates": {"source": [
            ["date", "us_2y", "us_10y", "2s10s"],
            ["2026-04-20", 4.15, 4.48, 33.0],
            ["2026-04-21", 4.17, 4.50, 33.0],
            ["2026-04-22", 4.19, 4.52, 33.0],
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
            "rows": [
                [{"widget": "kpi", "id": "k10y", "label": "10Y",
                   "source": "rates.latest.us_10y",
                   "sparkline_source": "rates.us_10y",
                   "suffix": "%", "decimals": 2, "w": 12}],
                [{"widget": "chart", "id": "curve", "w": 12, "h_px": 380,
                   "spec": {
                       "chart_type": "multi_line",
                       "dataset": "rates",
                       "mapping": {"x": "date",
                                    "y": ["us_2y", "us_10y"]},
                       "title": "UST curve"}}]
            ]
        }]
    },
}

r = compile_dashboard(manifest, session_path=SESSION_PATH)
# r.manifest_path  session/.../dashboards/rates_daily.json
# r.html_path      session/.../dashboards/rates_daily.html
```

`compile_dashboard` accepts a dict, a JSON string, or a path to a JSON
file. The written manifest preserves the high-level `spec` form; resolution
to ECharts option JSON happens in-memory for the HTML payload.

### Dashboard (Python builder, optional)

```python
from echart_dashboard import (
    Dashboard, ChartRef, KPIRef, GlobalFilter, Link,
)

db = (Dashboard(id="rates_daily", title="US Rates Daily")
      .add_dataset("rates", rates_df)
      .add_filter(GlobalFilter(id="dt", type="dateRange", default="6M",
                                 targets=["*"], field="date"))
      .add_row([
          KPIRef(id="k10y", label="10Y",
                  source="rates.latest.us_10y",
                  sparkline_source="rates.us_10y", w=12),
      ])
      .add_row([
          ChartRef(id="curve", w=12, h_px=380,
                    spec={"chart_type": "multi_line",
                          "dataset": "rates",
                          "mapping": {"x": "date",
                                      "y": ["us_2y", "us_10y"]}}),
      ])
      .add_link(Link(group="sync", members=["curve"],
                       sync=["axis", "tooltip"])))

res = db.build(session_path=SESSION_PATH)
```

### Single chart

```python
from echart_studio import make_echart

r = make_echart(
    df=df, chart_type="sankey",
    mapping={"source": "src", "target": "tgt", "value": "v"},
    title="Trade flows", theme="gs_clean", dimensions="wide",
    session_path=SESSION_PATH, chart_name="trade_flows",
)
# r.option, r.json_path, r.html_path, r.chart_id
```

---

## Style config (one file, one theme)

Everything aesthetic -- the Goldman Sachs brand palette, the single
canonical theme, dimension presets, and small-preset typography
overrides -- lives in a single file: `config.py`. Edit that file and
every chart/dashboard picks up the change.

```python
from config import (
    # brand tokens (navy, sky, gold, etc. + font stacks)
    GS_NAVY, GS_SKY, GS_GOLD, GS_INK, GS_PAPER,
    GS_FONT_SANS, GS_FONT_SERIF,
    # config API
    PALETTES,                 # 3 GS palettes (categorical/sequential/diverging)
    THEMES,                   # 1 theme: gs_clean
    DIMENSION_PRESETS,        # 12 (w, h) presets
    TYPOGRAPHY_OVERRIDES,     # small-preset font-size overrides
    get_palette, palette_colors, list_palettes,
    get_theme, list_themes,
    get_dimension_preset, get_typography_override, list_dimensions,
)
```

### Theme

One theme, always: **`gs_clean`**. Navy primary series, sky-blue
secondary, Goldman Sans typeface stack, paper-white background with a
thin grey grid. Derived from the published GS brand guidelines (PMS
652 sky blue + GS Navy + Goldman Sans / GS Sans).

| Name       | Font family           | Title | Palette        | Description        |
|------------|-----------------------|-------|----------------|--------------------|
| `gs_clean` | Goldman Sans / GS Sans| 18    | `gs_primary`   | GS canonical look  |

The theme dict has two top-level parts:

- `echarts`: the theme JSON registered in-browser via `echarts.registerTheme`
- `knob_values`: flat knob-name -> value overrides applied by the editor

Unknown theme raises `ValueError`.

### Palettes

Three GS palettes -- one per kind.

| Palette         | Kind        | Colors                                              |
|-----------------|-------------|-----------------------------------------------------|
| `gs_primary`    | categorical | Navy, Sky, Gold, Burgundy, Forest, Slate, Plum, ... |
| `gs_blues`      | sequential  | paper -> sky -> navy (6-stop monochrome ramp)       |
| `gs_diverging`  | diverging   | Burgundy -> Gold -> White -> Sky -> Navy (5 stops)  |

**Categorical** goes into `option.color`. **Sequential** and
**diverging** go into `visualMap.inRange.color` (used for heatmaps and
correlation matrices).

### Dimension presets

12 presets mirroring chart_studio:

`wide` (700x350), `square` (450x450), `tall` (400x550), `compact` (400x300),
`presentation` (900x500), `thumbnail` (300x200), `teams` (420x210),
`report` (600x400), `dashboard` (800x500), `widescreen` (1200x500),
`twopack` (540x360), `fourpack` (420x280), `custom` (600x400).

Small presets (`teams`, `thumbnail`, `compact`) activate a typography
override pushing down `titleSize`, `labelSize`, `strokeWidth`, etc. See
`TYPOGRAPHY_OVERRIDES` in `config.py`.

---

## PNG export (Python-side)

Every chart can be rendered to a PNG without opening a browser. The
`rendering` module (Part 3) invokes headless Chrome against a tiny
self-hosted HTML harness that loads ECharts and calls `setOption`. Zero
extra Python dependencies; only requires a Chrome/Chromium binary
(auto-detected on macOS at `/Applications/Google Chrome.app/...`,
overridable via the `CHROME_BIN` env var).

```python
from rendering import save_chart_png

save_chart_png(option, "chart.png",
               width=1000, height=520, theme="gs_clean", scale=2)
```

```python
# or from an EChartResult
r = make_echart(df, "multi_line", mapping=..., title="UST yields")
r.save_png("yields.png", scale=2)
```

Dashboards can bulk-export one PNG per chart widget:

```python
from echart_dashboard import compile_dashboard

compile_dashboard(
    manifest,
    output_path="out/macro.html",
    save_pngs=True,          # writes PNG per chart widget
    png_scale=2,
)
# -> out/macro.html, out/macro.json, out/macro_pngs/{widget_id}.png
```

From the CLI:

```bash
# single chart
python echart_studio.py png option.json -o chart.png --scale 2

# dashboard -- also dump PNGs for every chart
python echart_dashboard.py compile manifest.json -o out/dash.html --pngs

# every packaged chart sample at once
python rendering.py samples --output-dir pngs_demo
```

---

## Chart types

22 supported types via `make_echart(df, chart_type, mapping)` + a `raw`
passthrough for hand-rolled options.

| Chart type        | Required mapping keys                                   |
|-------------------|---------------------------------------------------------|
| `line`            | `x`, `y`, optional `color`                              |
| `multi_line`      | `x`, `y` (list of columns)                              |
| `bar`             | `x` (category), `y`, optional `color` (grouping/stack)  |
| `bar_horizontal`  | `x` (value), `y` (category), optional `color`           |
| `scatter`         | `x`, `y`, optional `color`, `size`                      |
| `scatter_multi`   | `x`, `y`, `color`                                       |
| `area`            | `x`, `y`, optional `color` (stacked)                    |
| `heatmap`         | `x`, `y`, `value`                                       |
| `pie`             | `category`, `value`                                     |
| `donut`           | `category`, `value` (same as pie, rendered as ring)     |
| `boxplot`         | `x` (category), `y` (values)                            |
| `sankey`          | `source`, `target`, `value`                             |
| `treemap`         | `path` (list of cols) + `value`, or `name`+`parent`+`value` |
| `sunburst`        | same as `treemap`                                       |
| `graph`           | `source` + `target` + optional `value`, `node_category` |
| `candlestick`     | `x`, `open`, `close`, `low`, `high`                     |
| `radar`           | `category`, `value`, optional `series`                  |
| `gauge`           | `value` (number or column), optional `min`, `max`       |
| `calendar_heatmap`| `date`, `value`, optional `year`                        |
| `funnel`          | `category`, `value`                                     |
| `parallel_coords` | `dims` (list), optional `color`                         |
| `tree`            | `name`, `parent`                                        |
| `raw`             | pass `option=...` directly                              |

Unknown chart type raises `ValueError` with the full list.

### Datetime handling

Columns with pandas datetime dtype are converted to ISO-8601 strings. The x
axis auto-selects `type: "time"` for datetime columns, `"value"` for numeric,
`"category"` otherwise.

### Column sanitation

The producer reads columns by exact name. Missing columns raise `ValueError`
with the dataframe column list -- no silent fallback.

### `make_echart(...)`

```python
def make_echart(
    df: Any = None,
    chart_type: str = "line",
    mapping: Optional[Dict[str, Any]] = None,
    option: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    theme: str = "gs_clean",
    palette: Optional[str] = None,
    dimensions: str = "wide",
    session_path: Optional[Union[str, Path]] = None,
    chart_name: Optional[str] = None,
    save_as: Optional[str] = None,
    write_html: bool = True,
    write_json: bool = True,
    spec_sheets: Optional[Dict[str, Dict[str, Any]]] = None,
    active_spec_sheet: Optional[str] = None,
    user_id: Optional[str] = None,
) -> EChartResult
```

Two invocation modes:

- **Builder mode:** pass `df` + `chart_type` + `mapping`. The per-type
  builder translates the inputs to an ECharts option.
- **Passthrough mode:** pass `option=...` and `chart_type="raw"` (or any
  type). The passed option is deep-copied, theme/palette are applied, and
  the wrap proceeds as usual.

`EChartResult` fields (mirror PRISM's `ChartResult`):

| Field               | Purpose                                            |
|---------------------|----------------------------------------------------|
| `option`            | ECharts option dict                                |
| `chart_id`          | 12-char SHA-1 hash of canonical option             |
| `chart_type`        | Normalized chart type                              |
| `theme`, `palette`, `dimension_preset` | Inputs echoed back           |
| `width`, `height`   | Preset-driven dimensions                           |
| `json_path`, `html_path`, `html` | Paths + HTML content (when saved)    |
| `success`, `error_message`, `warnings` | Standard PRISM contract      |
| `knob_names`        | Names of knobs exposed in the editor UI            |

### `wrap_echart(option, ...)`

Takes a pre-built ECharts option dict and returns the editor HTML. Good for
rehydrating a saved spec or wrapping a hand-rolled option.

---

## Dashboard manifest

A "manifest" is a JSON document that fully defines a dashboard. Three
shapes are supported for chart widgets (lowest ceremony first):

```json
{
  "schema_version": 1,
  "id": "rates_daily",
  "title": "US Rates Daily",
  "description": "Curve, spread, and snapshot KPIs.",
  "theme": "gs_clean",
  "palette": "gs_primary",

  "datasets": {
    "rates": {
      "source": [
        ["date", "us_2y", "us_10y"],
        ["2025-01-01", 4.0, 4.2],
        ["2025-01-02", 4.01, 4.205]
      ]
    }
  },

  "filters": [
    { "id": "dt",  "type": "dateRange", "default": "6M",
       "targets": ["*"], "label": "Date", "field": "date" }
  ],

  "layout": {
    "kind": "grid",
    "cols": 12,
    "rows": [
      [ {"widget": "chart", "id": "curve", "w": 6,
          "spec": {"chart_type": "multi_line", "dataset": "rates",
                    "mapping": {"x": "date",
                                 "y": ["us_2y", "us_10y"]}}},
        {"widget": "chart", "id": "spread", "w": 6,
          "spec": {"chart_type": "line", "dataset": "rates",
                    "mapping": {"x": "date", "y": "us_10y"}}} ],
      [ {"widget": "kpi", "id": "k10y", "label": "10Y",
          "source": "rates.latest.us_10y", "w": 4},
        {"widget": "chart", "id": "cand", "w": 8,
          "option": {"series": [...]}} ],
      [ {"widget": "markdown", "id": "notes",
          "content": "## Notes\n..."} ]
    ]
  },

  "links": [
    { "group": "rates_sync", "members": ["curve", "spread"],
       "sync": ["axis", "tooltip"] },
    { "group": "rates_brush", "members": ["curve", "spread"],
       "brush": {"type": "rect", "xAxisIndex": 0} }
  ]
}
```

All keys except `layout.rows` are optional at the schema level. Validation
enforces stricter rules (see [Validation](#validation)).

### Chart widget variants: `spec` / `ref` / `option`

Every `widget: chart` must declare one of three variants. Use the lowest
ceremony that fits.

| Variant   | Shape                                                  | When to use                                             |
|-----------|--------------------------------------------------------|---------------------------------------------------------|
| `spec`    | `{chart_type, dataset, mapping, [title, palette, ...]}` | **Preferred.** LLM-friendly. Data lives in manifest.   |
| `ref`     | `"echarts/mychart.json"`                                | When you have pre-emitted spec JSON from `make_echart`. |
| `option`  | raw ECharts option dict                                | Passthrough for hand-crafted options / tests.           |

#### `spec` variant (recommended)

```json
{
  "widget": "chart",
  "id": "curve",
  "w": 12, "h_px": 380,
  "title": "UST yield curve",
  "spec": {
    "chart_type": "multi_line",
    "dataset": "rates",
    "mapping": {"x": "date", "y": ["us_2y", "us_5y", "us_10y", "us_30y"]},
    "title": "UST curve (daily close)",
    "subtitle": "points",
    "palette": "gs_primary"
  }
}
```

`spec.dataset` references `manifest.datasets.<name>`. At compile time the
source rows are materialized into a pandas DataFrame and fed into the same
`_BUILDER_DISPATCH` that `make_echart()` uses. `spec.chart_type` must be one
of the 22 supported types.

Per-spec `palette`, `theme`, `subtitle`, `title`, `dimensions` override the
manifest-level defaults. Required keys: `chart_type`, `dataset`, `mapping`.

#### `ref` variant

```json
{"widget": "chart", "id": "curve", "w": 12, "ref": "echarts/curve.json"}
```

Path is resolved relative to:
1. `base_dir` argument (if supplied to `render_dashboard`)
2. The loaded manifest file's parent directory (`compile_dashboard(path)`)
3. Current working directory

#### `option` variant

```json
{
  "widget": "chart", "id": "curve", "w": 12,
  "option": {"series": [...], "xAxis": {...}, "yAxis": {...}}
}
```

Use when you want to drop a raw ECharts option straight in. Legacy alias
`option_inline` also works.

### `compile_dashboard(manifest, session_path=None, output_path=None, write_html=True, write_json=True)`

JSON-first compiler. Accepts:

- `dict`       -- an in-memory manifest
- `str`        -- either a path to a JSON file OR a raw JSON string
- `Path`       -- a path to a JSON file

Side effects:

- `session_path` given: writes `{session_path}/dashboards/{manifest.id}.json`
  and `{id}.html`
- `output_path` given: writes `{output_path}.html` and `{output_path}.json`
- Neither: returns a `DashboardResult` with `html` set but no IO

Chart widgets with a high-level `spec` block are lowered to ECharts option
JSON at compile time via the same builder dispatch `make_echart()` uses. The
written manifest preserves the declarative `spec` form (specs are NOT
inlined into the written manifest; only the HTML payload sees the resolved
options). This keeps the on-disk manifest compact and editable.

### `Dashboard(id, title, description, theme, palette)`

Python builder class. Mutator chain: `add_dataset`, `add_filter`, `add_row`,
`add_tab`, `add_link`, `set_cols`. Terminal: `to_manifest()` -> dict, or
`build(session_path=..., output_path=...)` -> `DashboardResult`.

Internally, `build()` runs the same validator + spec resolver +
`render_dashboard_html` pipeline that `compile_dashboard()` uses.

---

## Widgets

| Widget     | Required fields                                     | Purpose                          |
|------------|-----------------------------------------------------|----------------------------------|
| `chart`    | `id`, one of `spec` / `ref` / `option`              | ECharts canvas tile              |
| `kpi`      | `id`, `label`                                       | Big-number tile + optional delta |
| `table`    | `id`, `ref` or `dataset_ref`                        | Simple HTML table                |
| `markdown` | `id`, `content`                                     | Minimal markdown text block      |
| `divider`  | `id`                                                | Horizontal rule row-spanner      |

Common optional fields: `w` (grid span 1..cols), `h_px` (chart only;
default 320), `title`, `theme` (per-tile theme override).

### KPI widget

`source` uses dotted aggregation syntax over a dataset:

```
<dataset>.<agg>.<column>
```

Aggregations: `latest`, `sum`, `mean`, `min`, `max`, `count`.

Example: `rates.latest.us_10y`.

Plain `value` overrides the source. Use `sparkline_source` to add a tiny
inline chart. Use `delta` / `delta_source` for comparison arrows.

### Table widget

Renders the first `max_rows` rows (default 50) of a dataset.

### Markdown widget

Small markdown parser supporting `#`/`##`/`###` headings and paragraphs.
Keep it short.

### Divider widget

Zero-height row separator; forces a grid row break.

---

## Filters

Five filter types. All filters listen for user input, update the shared
filter state, and broadcast to charts whose `targets` pattern matches.

| Type           | Default | UI                              | Applies to                                    |
|----------------|---------|---------------------------------|-----------------------------------------------|
| `dateRange`    | `"6M"`  | select of `1M/3M/6M/YTD/1Y/...` | dataset column (usually `date`) within range  |
| `select`       | `""`    | `<select>`                      | `rows[field] == value`                        |
| `multiSelect`  | `[]`    | `<select multiple>`             | `rows[field] in [values]`                     |
| `numberRange`  | `[a,b]` | text `min,max`                  | `a <= rows[field] <= b`                       |
| `toggle`       | `false` | checkbox                        | `rows[field]` truthy when checked             |

### Schema

```json
{
  "id": "dt", "type": "dateRange", "default": "6M",
  "targets": ["*"],
  "label": "Date range",
  "field": "date",
  "options": ["US", "EU", "JP"]
}
```

`targets` supports `"*"`, `"prefix_*"`, `"*_suffix"`, `"exact_id"`.

---

## Links (connect + brush)

### connect()

```json
{ "group": "rates_sync", "members": ["curve", "spread"],
   "sync": ["axis", "tooltip"] }
```

At load, the runtime sets `chart.group = group` for each member and calls
`echarts.connect(group)`. Supported sync entries: `axis`, `tooltip`,
`legend`, `dataZoom`.

### brush cross-filter

```json
{ "group": "rates_brush", "members": ["curve", "spread"],
   "brush": {"type": "rect", "xAxisIndex": 0} }
```

When a user brushes on any member chart, the runtime extracts the
`coordRange` from the brush selection, filters the linked chart's dataset
to the brushed range on the x axis, and re-renders all other linked
charts. Clearing the brush resets the dataset to its original contents.

Brush types: `rect`, `polygon`, `lineX`, `lineY`. Unknown types raise
validation errors.

---

## Datasets

Shared dataset scopes enable filter + brush cross-filter to reach multiple
charts.

### Shape

```json
"datasets": {
  "name": {
    "source": [["col1", "col2", ...], [val, val, ...], ...],
    "field_types": {"col1": "date", "col2": "number"}
  }
}
```

The first row of `source` is the header. All subsequent rows are data rows.

### From a DataFrame

```python
db.add_dataset("rates", rates_df)
```

pandas datetime columns are converted to ISO-8601 strings automatically.
NaN values become null.

### Referencing from charts

```json
{"widget":"chart", "id":"curve", "ref":"echarts/curve.json",
  "dataset_ref": "rates"}
```

At runtime, the chart's `series[*].data` is replaced with an encoded
reference to the dataset's (filtered) source. Your saved spec should have
the same column names as the dataset header; the runtime auto-encodes
`x = header[0]`, `y = header[1+i]` if the series lacks an explicit
`encode`.

---

## Validation

```python
from echart_dashboard import validate_manifest
ok, errs = validate_manifest(manifest)
```

Rules:

- `schema_version` must equal `1`
- `id`, `title` must be present
- `theme`, `palette` must be registered names
- Each dataset entry must be `{"source": [...]}`
- Filter `id` must be unique; `type` must be in the valid set
- `select`/`multiSelect` require `options`
- Each widget `id` must be unique; widths must sum to at most `cols`
- Widget-specific required fields enforced:
    - `chart` requires one of `spec` / `ref` / `option`
    - `kpi` requires `label`
    - `table` requires `ref` or `dataset_ref`
    - `markdown` requires `content`
- Chart `spec` blocks require `chart_type` (in `VALID_CHART_TYPES`),
  `dataset` (must reference a declared dataset), and `mapping` dict. Per-spec
  `palette` / `theme` overrides must be registered names.
- Filter `targets` must match real chart widget ids (wildcards OK)
- Link members must match real chart widget ids (wildcards OK)
- `sync` values must be in `{axis, tooltip, legend, dataZoom}`
- `brush.type` must be in `{rect, polygon, lineX, lineY}`

Returns `(ok, [errors...])`. Each error is a human-readable string
identifying the offending path.

---

## CLI

Running any script without arguments launches its interactive menu.
Argparse mirrors every option for non-interactive / CI use.

```
python echart_studio.py                        # interactive menu
python echart_studio.py wrap spec.json --open  # wrap JSON to HTML
python echart_studio.py demo --matrix          # 23 samples x 5 themes
python echart_studio.py list types|themes|palettes|dimensions|knobs|samples
python echart_studio.py info spec.json         # summarize a spec file
python echart_studio.py test                   # run unit tests
```

```
python echart_dashboard.py                                    # interactive menu
python echart_dashboard.py compile manifest.json -o out.html --open
python echart_dashboard.py compile manifest.json -s SESSION_DIR
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

`demos.py` bundles five end-to-end scenarios that collectively exercise
every capability in the stack:

| Name              | Kind      | Highlights                                                   |
|-------------------|-----------|--------------------------------------------------------------|
| `rates_daily`     | dashboard | Tabs, KPIs with sparklines + deltas, brush cross-filter      |
| `cross_asset`     | composite | 4-pack grid, event annotations per panel (vline/band/point)  |
| `risk_regime`     | dashboard | Correlation heatmap (diverging), VIX term, boxplot, drawdown |
| `rv_table`        | dashboard | Rich table w/ conditional fmt + color scale + row popup      |
| `filter_showcase` | dashboard | All 9 filter types wired to the same dataset                 |

Each demo writes its output under `output/<timestamp>/<name>/` alongside
a combined `gallery.html` page with PNG thumbnails + links to every
interactive artifact.

---

## PRISM integration

### Recommended flow (JSON-first)

PRISM emits **one JSON manifest** inside `execute_analysis_script`, then
calls `compile_dashboard(manifest, session_path=SESSION_PATH)`. No HTML,
no Python builder objects, no intermediate chart JSON files.

```python
df_rates = pull_market_data(coordinates=[...])
df_xa    = pull_market_data(coordinates=[...])

manifest = {
    "schema_version": 1,
    "id": "daily_macro",
    "title": "Daily Macro",
    "theme": "gs_clean",
    "datasets": {
        "rates": {"source": df_to_source(df_rates)},
        "xa":    {"source": df_to_source(df_xa)},
    },
    "filters": [
        {"id": "dt", "type": "dateRange", "default": "6M",
          "targets": ["*"], "field": "date"},
    ],
    "layout": {
        "kind": "tabs",
        "tabs": [
            {"id": "curve", "label": "Curve", "rows": [[
                {"widget": "chart", "id": "c", "w": 12,
                  "spec": {"chart_type": "multi_line", "dataset": "rates",
                            "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"]},
                            "title": "UST curve"}},
            ]]},
            {"id": "xa", "label": "Cross-asset", "rows": [[
                {"widget": "chart", "id": "spx", "w": 6,
                  "spec": {"chart_type": "line", "dataset": "xa",
                            "mapping": {"x": "date", "y": "spx"}}},
                {"widget": "chart", "id": "oil", "w": 6,
                  "spec": {"chart_type": "line", "dataset": "xa",
                            "mapping": {"x": "date", "y": "wti"}}},
            ]]},
        ],
    },
    "links": [
        {"group": "sync", "members": ["spx", "oil"],
          "sync": ["axis", "tooltip", "dataZoom"]},
    ],
}

r = compile_dashboard(manifest, session_path=SESSION_PATH)
# r.manifest_path, r.html_path
```

The compiler handles validation, spec resolution (pulling dataset rows
through the builder dispatch), and HTML rendering. The caller writes ZERO
HTML.

### Session layout

Dashboards auto-save under the session when you pass `session_path`:

```
{SESSION_PATH}/dashboards/{id}.json        manifest (LLM-editable, source of truth)
{SESSION_PATH}/dashboards/{id}.html        compiled dashboard
{SESSION_PATH}/echarts/*.json              (optional) chart specs if using `ref`
{SESSION_PATH}/echarts/*.html              (optional) standalone chart editors
```

### Follow-up edits

Because the manifest is the source of truth on disk, subsequent turns can
read it, mutate it, and re-compile:

```python
import json
m = json.load(open(f"{SP}/dashboards/daily_macro.json"))
m["layout"]["tabs"].append({
    "id": "new_tab", "label": "FX",
    "rows": [[{"widget": "chart", "id": "fx", "w": 12,
                "spec": {"chart_type": "candlestick", ...}}]]
})
compile_dashboard(m, session_path=SP)
```

---

## Extending

### Add a chart type

1. Write a builder in `echart_studio.py` (section "BUILDER CONTEXT +
   PER-TYPE BUILDERS"): `build_mytype(df, mapping, ctx) -> option`.
2. Register it in `_BUILDER_DISPATCH` and add it to
   `VALID_CHART_TYPES` (in `echart_dashboard.py`).
3. Define per-type knobs in `echart_studio.py` (section "KNOB REGISTRY")
   and register in `MARK_KNOB_MAP`.
4. Add a sample in `samples.py` (use `@_register("mytype")`).
5. Add relevant `APPLY.*` functions in `rendering.py` (PART 1 - editor HTML)
   for complex knobs.

### Add a knob

Append to `UNIVERSAL_KNOBS` (applies everywhere) or to the appropriate
mark list in the "KNOB REGISTRY" section of `echart_studio.py`. Required
fields: `name`, `label`, `type`, `default`, `group`, and one of `path` or
`apply`.

### Add a theme / palette / dimension preset

See [Style config](#style-config-one-file) above. Append to the dict in
`config.py`.

---

## Single-chart editor HTML

The editor HTML wraps a spec for preview + interactive tweaking:

```
+-----------------------------------------------------------+
| title   spec-sheet [v]  Save SaveAs Delete DL UL  status  |
+------------------------+---------------------------------+-+
| CHART ZONE             | INFO SIDEBAR (440px)            | |
|  Reset Full PNG2x SVG  |  [Data][Code][Metadata][Export] | |
|                        |  [Raw]                          | |
|   live ECharts canvas  |                                 | |
|                        |  (tab contents)                 | |
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

### Spec sheets

Named bundle of user preferences -- saved via the editor, applied on load.
Stores styling only (title/subtitle text are chart-specific content, not
user prefs).

Stored in `localStorage` under `echart_studio_sheets_{user_id or 'anon'}`.
Precedence:

```
knob default -> theme -> dimension typography override -> spec sheet -> live edits
```

### Dashboard HTML runtime

- Loads ECharts from jsdelivr CDN
- Registers all five themes at init
- Iterates widgets, creates ECharts instances per chart tile
- Subscribes each chart to the filters whose `targets` match it
- Applies `echarts.connect()` groups after init
- Wires brush listeners per chart when `links[].brush` is present
- KPI tiles resolve their value via the dotted aggregation source
- Table tiles render the first N rows of their dataset
- Reset-filters button restores original filter defaults and resets all
  brushed datasets

In the browser console, inspect `window.DASHBOARD` for:

```
DASHBOARD.manifest   // original manifest
DASHBOARD.charts     // {id: {inst, datasetRef}}
DASHBOARD.filters    // current filter state
DASHBOARD.datasets   // current dataset copies (post-filter/brush)
```

---

## Testing

```
python tests.py                        # 171 tests (studio + dashboard + composites)
python tests.py TestThemes             # one test class
python echart_studio.py test           # shortcut: runs tests.py
```

The sample matrix (23 samples x 5 themes = 115 wraps) runs as part of
`TestSamplesMatrix`.
