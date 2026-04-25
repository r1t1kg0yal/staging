## DATA_SHAPES.md -- organizing DataFrames for echarts

**Module:** `GS/viz/echarts`
**Audience:** PRISM (the LLM authoring `execute_analysis_script` code), developers extending the chart system, anyone wiring real data into a manifest.
**Scope:** the *data side* of the JSON. The README covers chart types, knobs, widgets, dashboards, refresh, etc. This doc covers the **prior question**: how do you organise the DataFrames that feed all of the above so that wiring them into the manifest is mechanical rather than puzzle-solving.

This is a context module, not an API reference. Read once, internalise the model, then refer back to the cheat-sheet (Section 13) when you're authoring a manifest.

---

## 0. The one mental model

```
+-------------------------+        +---------------------------+        +-----------------------+
|  Real-world data        |        |  Tidy DataFrames (named)  |        |  manifest.datasets    |
|  pulls + transforms     | -----> |  one row = one observation| -----> |  {name: df}           |
|  pull_market_data,      |        |  one col = one variable   |        |  (compiler converts   |
|  pull_haver_data, FRED, |        |  plain English columns    |        |   each df once to     |
|  Treasury, ...          |        |  date as a column, not an |        |   [header, ...rows])  |
|                         |        |  index                    |        |                       |
+-------------------------+        +---------------------------+        +-----------+-----------+
                                                                                    |
                                                                                    |  per widget,
                                                                                    |  spec.dataset
                                                                                    |  picks columns
                                                                                    v
                                                          +--------------------------------------+
                                                          |  spec.mapping = {x: ..., y: ...}     |
                                                          |  spec.chart_type = 'multi_line', ... |
                                                          |  KPI source = "rates.latest.us_10y"  |
                                                          |  Table dataset_ref = "rv"            |
                                                          |  Filter field = "region"             |
                                                          +--------------------------------------+
```

**One sentence.** Every chart, KPI, table, sparkline, and stat in this module is fed by one or more **named tidy DataFrames** registered in `manifest.datasets`. Each widget reaches into a dataset by name and selects/aggregates columns by name through its `spec.mapping` (charts) or its dotted source string (KPIs). The compiler converts each DataFrame to the canonical `[header, row, row, ...]` list of lists exactly once. Same DataFrame can feed many widgets.

**The five non-negotiables:**

1. **Tidy.** One row = one observation, one column = one variable. No multi-index, no embedded headers, no "totals" row.
2. **Date as a column.** Never as a `DatetimeIndex`. The compiler emits a `date` column to ISO-8601; ECharts auto-detects time-axis from that column.
3. **Plain-English columns.** `us_10y`, not `USGG10YR Index`. `unemployment_rate`, not `UNRATE@FRED`. The editor humanizes `us_10y` -> `US 10Y` and uses your column name in legends, tooltips, axis hints.
4. **Datasets are named like nouns, not series codes.** `rates`, `cpi`, `flows`, `bond_screen` -- not `df1`, not `usggt10y_panel`.
5. **A dataset earns its name.** It's worth registering in `manifest.datasets` if (a) more than one widget reads from it, OR (b) a single widget needs filter-aware re-rendering, OR (c) the table widget displays the rows verbatim. Otherwise inline a one-shot DataFrame is fine.

Everything else in this doc is consequence of those five.

---

## 1. The dataset is the unit of organisation

PRISM-side, you build a small number of well-shaped DataFrames per dashboard, not one DataFrame per chart. The manifest then composes views by referencing those datasets from many widgets.

```
                    ONE DATASET -> MANY WIDGETS

                       datasets["rates"]
                       date | us_2y | us_5y | us_10y | us_30y | 2s10s
                       -----+-------+-------+--------+--------+------
                       2024-01-02  ...  4.20    4.05    ...    -15
                       2024-01-03  ...  4.18    4.07    ...    -11
                       ...
                              |
              +---------------+---------------+--------------+--------------+
              |               |               |              |              |
              v               v               v              v              v
     [chart curve]    [kpi k10y]      [kpi k2s10s]    [sparkline]    [table snapshot]
     multi_line       latest.us_10y   latest.2s10s    rates.us_10y   rv table cols
     y=[us_2y,us_5y,                                                  filtered to last
        us_10y,us_30y]
```

Bad: a separate `rates_curve_df`, `rates_k10y_df`, `rates_k2s10s_df`, `rates_sparkline_df`. That proliferates datasets, breaks filter joins ("region" filter only updates whichever dataset has it), and turns the dashboard into a mess of tiny snapshots that all need to be pulled and refreshed independently.

**Heuristic for splitting datasets.** Keep one DataFrame per *domain + primary key*. Different primary keys -> different datasets. Same primary key, different metrics -> wide-form columns on the same DataFrame.

```
+--------------------------+----------------------------+--------------------------+
| Primary key              | Domain                     | Dataset name             |
+--------------------------+----------------------------+--------------------------+
| date                     | rates curve + spreads      | rates                    |
| date                     | inflation series           | cpi                      |
| date, ticker             | equity panel               | equities                 |
| ticker                   | latest snapshot per name   | screen                   |
| (source, target)         | flows                      | flows                    |
| date, year_idx           | calendar values            | calendar                 |
+--------------------------+----------------------------+--------------------------+
```

When two domains share a primary key but diverge on cadence (rates daily vs CPI monthly), keep them separate -- merging produces NaN gaps that visually break wide-form charts.

---

## 2. Tidy long-form vs wide-form: when to use each

Most chart types accept *both* shapes. The right choice is about who knows what at design time.

```
+---------------------------------------------------------------------------+
|                            WIDE FORM                                       |
|  date       | us_2y | us_5y | us_10y | us_30y                              |
|  -----------|-------|-------|--------|-------                              |
|  2024-01-02 | 4.40  | 4.20  | 4.10   | 4.30                              |
|  2024-01-03 | 4.41  | 4.18  | 4.07   | 4.32                              |
|  ...                                                                       |
|                                                                            |
|  Use when:                                                                 |
|    - The set of series is small + stable (curve points, FX majors).        |
|    - The columns are the natural names you'd put in a legend.              |
|    - You need every series visible by default with no filtering.           |
|    - You want the wide-form "free filter rewire" path (line/bar/area       |
|      multi_line without color/stack/trendline).                            |
|                                                                            |
|  mapping = {x: 'date', y: ['us_2y', 'us_5y', 'us_10y', 'us_30y']}          |
+---------------------------------------------------------------------------+

+---------------------------------------------------------------------------+
|                            LONG FORM (TIDY MELTED)                         |
|  date       | tenor | yield                                                |
|  -----------|-------|------                                                |
|  2024-01-02 | 2Y    | 4.40                                                |
|  2024-01-02 | 5Y    | 4.20                                                |
|  2024-01-02 | 10Y   | 4.10                                                |
|  2024-01-02 | 30Y   | 4.30                                                |
|  ...                                                                       |
|                                                                            |
|  Use when:                                                                 |
|    - The number of groups is dynamic / data-driven.                        |
|    - You need to color, facet, dual-axis, stack, dash by a category.       |
|    - You'll filter on the group column (e.g. multiSelect of tenors).       |
|    - You want to feed a table that lists every (date, tenor, yield) row.   |
|                                                                            |
|  mapping = {x: 'date', y: 'yield', color: 'tenor'}                         |
+---------------------------------------------------------------------------+
```

**Default rule.** If the columns you want to plot are a *known short list* you'd hand-type into the manifest, store them wide. Otherwise melt to long form. Wide is shorter to author; long is more reshapable downstream.

**Crossover quirks.**
- `multi_line`, `line`, `bar`, `area` accept both. `multi_line` with `y=[...]` is wide; with `color=` is long.
- `scatter` long form (`color=`) gives you `scatter_multi` for free; wide-form scatter doesn't exist (a single scatter is always one (x, y) pair from one DataFrame).
- `boxplot`, `bullet`, `histogram` are inherently long form: each row is one observation in the value column.
- `heatmap`, `sankey`, `graph`, `treemap`, `sunburst`, `parallel_coords`, `radar` are inherently long form (or hierarchical -- see Section 4).
- `candlestick` is necessarily wide (one row per period with columns `open / close / low / high`).
- `stacked_bar` works in both; long form (`x=cat, y=val, color=group`) is the cleaner authoring path.

**Filter compatibility.** When PRISM lets the user filter on a category, the dataset must carry that category as a column -- which forces long form. So if you anticipate a `select` or `multiSelect` filter on `tenor`, store the rates dataset long-form, not wide.

---

## 3. Data archetypes mapped to chart types

This is the lookup table you'll use most often. Every PRISM chart-or-table request fits one of these archetypes; once you know the archetype, the DataFrame shape and chart type are determined.

```
+----+---------------------------+-------------------------+----------------------------+
| #  | Archetype                 | Natural DataFrame shape | Chart types                |
+----+---------------------------+-------------------------+----------------------------+
| 1  | Univariate time series    | (date, value)           | line                       |
| 2  | Multi-variable TS         | (date, v1, v2, ...) wide| multi_line, area           |
|    |  fixed/known set          |                         |                            |
| 3  | Multi-variable TS         | (date, group, value)    | multi_line color=, area    |
|    |  dynamic groups           | long                    | color=                     |
| 4  | Cross-section, 1 metric   | (cat, value)            | bar, bar_horizontal, pie,  |
|    |                           |                         | donut, funnel              |
| 5  | Cross-section, grouped    | (cat, group, value)     | bar stack=True, scatter    |
|    |                           | long                    | color=                     |
| 6  | Bivariate scatter         | (x_num, y_num, [color]) | scatter, scatter_multi     |
| 7  | Distribution / sample     | (value) one column      | histogram                  |
| 8  | Distribution by group     | (group, value) long     | boxplot                    |
| 9  | Range + current marker    | (cat, lo, hi, cur, ...) | bullet                     |
| 10 | OHLC time series          | (date, open, close,     | candlestick                |
|    |                           |  low, high) wide        |                            |
| 11 | Daily scalar over a year  | (date, value)           | calendar_heatmap           |
| 12 | Cat x cat matrix          | (x_cat, y_cat, value)   | heatmap                    |
|    |  (e.g. correlations,      | long                    |                            |
|    |   cross-tabs)             |                         |                            |
| 13 | Hierarchy (tree of parts) | (level1, level2, ...,   | treemap, sunburst (path)   |
|    |                           |  value) OR              |                            |
|    |                           | (name, parent, value)   | treemap, sunburst (parent) |
|    |                           |                         | tree (no value column      |
|    |                           |                         | needed)                    |
| 14 | Flow / network            | (source, target, value) | sankey, graph              |
| 15 | Multi-dim comparison      | (entity, dim, value)    | radar series=entity        |
|    |  by entity                | long                    | parallel_coords dims=[...] |
| 16 | Single scalar             | one number              | gauge                      |
| 17 | Rich row-per-entity table | (id, attr1, attr2, ...) | table widget               |
|    |  (RV screen, watchlist,   | wide                    |                            |
|    |   bond panel)             |                         |                            |
| 18 | Latest snapshot from TS   | (any TS DataFrame)      | KPI source =               |
|    |                           |                         |   "<ds>.latest.<col>"      |
| 19 | Sparse event list         | (date, label, [color])  | annotations (vline/        |
|    |                           |                         |   band/point/arrow) on     |
|    |                           |                         |   another chart            |
| 20 | Schedule / agenda         | (date, time, event,     | table widget               |
|    |  (data list)              |  attendees, ...)        |                            |
+----+---------------------------+-------------------------+----------------------------+
```

The progression #18-#20 is important: not every "data thing" is a chart. KPIs/sparklines extract scalars or arrays from existing time-series datasets; annotations layer event lists onto time-series charts; schedules are just tables. Don't invent a new chart for them.

---

## 4. Per-archetype DataFrame templates

For each archetype, the template is **(a)** the column layout you should produce in pandas, **(b)** the manifest mapping that consumes it. ASCII previews are 3-4 rows; real DataFrames have hundreds-thousands of rows but the *shape* is fixed.

### 4.1 Univariate time series (#1)

```
df_unrate
+-----------+------------+
| date      | unrate_pct |
+-----------+------------+
| 2024-01-31|       3.7  |
| 2024-02-29|       3.9  |
| 2024-03-31|       3.8  |
+-----------+------------+

mapping = {x: 'date', y: 'unrate_pct', y_title: 'U-rate (%)'}
chart_type = 'line'
```

### 4.2 Multi-variable TS, fixed columns (#2)

```
df_rates
+-----------+-------+-------+--------+--------+
| date      | us_2y | us_5y | us_10y | us_30y |
+-----------+-------+-------+--------+--------+
| 2024-01-02|  4.40 |  4.20 |   4.10 |   4.30 |
| 2024-01-03|  4.41 |  4.18 |   4.07 |   4.32 |
+-----------+-------+-------+--------+--------+

mapping = {x: 'date', y: ['us_2y','us_5y','us_10y','us_30y'],
           y_title: 'Yield (%)'}
chart_type = 'multi_line'   # or 'area' for stacked area
```

`humanize` (default on) renders the legend as `US 2Y / US 5Y / US 10Y / US 30Y`.

### 4.3 Multi-variable TS, dynamic groups (#3)

```
df_yields_long = df_rates.melt(
    id_vars='date', var_name='tenor', value_name='yield'
)
+-----------+--------+--------+
| date      | tenor  | yield  |
+-----------+--------+--------+
| 2024-01-02| us_2y  |  4.40  |
| 2024-01-02| us_5y  |  4.20  |
| 2024-01-02| us_10y |  4.10  |
| 2024-01-02| us_30y |  4.30  |
+-----------+--------+--------+

mapping = {x: 'date', y: 'yield', color: 'tenor', y_title: 'Yield (%)'}
chart_type = 'multi_line'
```

Use this shape if: you'll add a `multiSelect` filter on `tenor`, you want to dual-axis one tenor (`dual_axis_series=['us_30y']`), or the set of tenors is data-driven.

### 4.4 Cross-section, one metric (#4)

```
df_gdp
+--------+-----------+
| region | gdp_usdtn |
+--------+-----------+
| US     |     26.9  |
| EU     |     18.3  |
| JP     |      4.2  |
| UK     |      3.1  |
+--------+-----------+

mapping = {x: 'region', y: 'gdp_usdtn', y_title: 'GDP (USDtn)'}
chart_type = 'bar'                 # or 'bar_horizontal' (swap x/y)
                                   # or 'pie' / 'donut': category=region, value=gdp_usdtn
                                   # or 'funnel': category=region, value=gdp_usdtn
```

`x_sort=['US','EU','JP','UK']` to force the order.

### 4.5 Cross-section, grouped (#5)

```
df_trade_long
+--------+----------+-----+
| region | kind     | val |
+--------+----------+-----+
| US     | goods    |  10 |
| US     | services |  15 |
| EU     | goods    |   8 |
| EU     | services |   9 |
+--------+----------+-----+

mapping = {x: 'region', y: 'val', color: 'kind', stack: True}
chart_type = 'bar'
```

For a *grouped* (side-by-side) bar instead of stacked, set `stack: False`. For categorical scatter (`scatter_multi`), the same long-form shape with numeric x/y plus `color: kind` works.

### 4.6 Bivariate scatter (#6)

```
df_phillips
+--------------+-----------+--------+
| unemployment | core_cpi  | decade |
+--------------+-----------+--------+
|         3.7  |     2.4   | 2020s  |
|         5.1  |     1.8   | 2010s  |
|         4.4  |     2.6   | 1990s  |
+--------------+-----------+--------+

mapping = {x: 'unemployment', y: 'core_cpi', color: 'decade',
           trendlines: True,
           x_title: 'U-rate (%)', y_title: 'Core CPI YoY (%)'}
chart_type = 'scatter'
```

`size: 'mkt_cap'` adds a third numeric encoding (bubble chart).

### 4.7 Distribution -- one numeric column (#7)

```
df_returns
+--------+
| ret    |
+--------+
| -1.2   |
|  0.4   |
|  2.1   |
| ...    |
+--------+

mapping = {x: 'ret', bins: 30, density: False}
chart_type = 'histogram'
```

The builder bins the values and emits a bar series. Don't pre-bin yourself.

### 4.8 Distribution by group (#8)

```
df_sector_returns_long
+------------+--------+
| sector     | ret    |
+------------+--------+
| Tech       |  1.2   |
| Tech       |  0.4   |
| Financials | -0.6   |
| Energy     |  2.5   |
| ...        |        |
+------------+--------+

mapping = {x: 'sector', y: 'ret', y_title: 'Daily return (%)'}
chart_type = 'boxplot'
```

The builder computes Q1/median/Q3/whiskers/outliers per group; you don't pre-aggregate. Same DataFrame can feed `make_echart('histogram', ...)` filtered to one sector, or a `multi_line` if you also have a date column.

### 4.9 Range + current marker -- the RV pattern (#9)

```
df_rv
+-----------+---------+--------+--------+------+--------+
| metric    | current | low_5y | high_5y| z    | pct    |
+-----------+---------+--------+--------+------+--------+
| 2s10s     |    38   |   -20  |    45  |  1.2 | '85th' |
| 5s30s     |    -5   |   -10  |    60  | -1.5 | '12th' |
| 10Y real  |   1.85  |   0.5  |   2.4  |  0.1 | '45th' |
+-----------+---------+--------+--------+------+--------+

mapping = {y: 'metric', x: 'current',
           x_low: 'low_5y', x_high: 'high_5y',
           color_by: 'z', label: 'pct'}
chart_type = 'bullet'
```

This same DataFrame is the **canonical RV screen shape** -- it also drives an entire rich `table` widget (Section 4.17) without modification.

### 4.10 OHLC time series (#10)

```
df_ohlc
+------------+-------+-------+-------+-------+
| date       | open  | close | low   | high  |
+------------+-------+-------+-------+-------+
| 2024-04-15 | 412.5 | 415.1 | 410.8 | 416.3 |
| 2024-04-16 | 415.1 | 413.4 | 412.0 | 415.9 |
+------------+-------+-------+-------+-------+

mapping = {x: 'date', open: 'open', close: 'close',
           low: 'low', high: 'high'}
chart_type = 'candlestick'
```

Always wide; long form is meaningless here.

### 4.11 Daily scalar over a year (#11)

```
df_daily_returns
+------------+--------+
| date       | ret    |
+------------+--------+
| 2025-01-02 |  0.12  |
| 2025-01-03 | -0.04  |
| 2025-01-06 |  0.31  |
| ...        |  ...   |
+------------+--------+

mapping = {date: 'date', value: 'ret', year: '2025'}
chart_type = 'calendar_heatmap'
```

One row per calendar day. If you only have month-end data, calendar_heatmap is the wrong viz -- use a bar by month instead. The compiler picks the year automatically; pass `year='2025'` only when the dataset spans multiple years.

### 4.12 Categorical x categorical matrix (#12)

The "matrix as long table" rule: never pass a 2-D numpy array. Always melt to (x_cat, y_cat, value).

```
df_corr
+--------+--------+-------+
| asset1 | asset2 | corr  |
+--------+--------+-------+
| SPX    | UST10Y | -0.42 |
| SPX    | DXY    | -0.18 |
| UST10Y | DXY    |  0.55 |
| ...    | ...    |  ...  |
+--------+--------+-------+

mapping = {x: 'asset1', y: 'asset2', value: 'corr'}
chart_type = 'heatmap'
palette = 'gs_diverging'   # for correlations / z-scores
                            # use 'gs_blues' (sequential) for densities
```

Same shape works for cross-tab counts (regime x sector), z-score panels, etc.

### 4.13 Hierarchies -- two interchangeable shapes (#13)

```
PATH SHAPE                            PARENT SHAPE
+--------+-----------+-----+          +-----------+-----------+-----+
| region | sector    | cap |          | name      | parent    | cap |
+--------+-----------+-----+          +-----------+-----------+-----+
| US     | Tech      |2200 |          | US        |           |     |
| US     | Financials|1400 |          | Tech US   | US        |2200 |
| EU     | Industries| 800 |          | Fin US    | US        |1400 |
+--------+-----------+-----+          | EU        |           |     |
                                      | Industries| EU        | 800 |
mapping = {path:                      +-----------+-----------+-----+
  ['region','sector'],
  value: 'cap'}                       mapping = {name:'name',
chart_type = 'treemap'                  parent:'parent',
                          OR            value:'cap'}
                                      chart_type = 'treemap'
```

Path shape is more natural for static hierarchies (region -> sector -> stock). Parent shape is more flexible for arbitrary trees (FOMC committee, supply chain, dependency graph) -- and is the only shape `tree` accepts.

For `tree` (org chart) drop the `value` column entirely:

```
df_committee
+--------------+--------------+
| name         | parent       |
+--------------+--------------+
| Fed Chair    |              |  <-- root: empty parent
| Vice Chair   | Fed Chair    |
| Governor 1   | Fed Chair    |
| FOMC Hawk    | Vice Chair   |
+--------------+--------------+

mapping = {name: 'name', parent: 'parent'}
chart_type = 'tree'
```

### 4.14 Flow / network (#14)

```
df_flows
+--------+--------+-----+
| src    | tgt    | v   |
+--------+--------+-----+
| US     | EU     | 12  |
| US     | JP     |  6  |
| EU     | US     |  9  |
+--------+--------+-----+

mapping = {source: 'src', target: 'tgt', value: 'v'}
chart_type = 'sankey'              # for left->right multi-stage flow
            'graph'                # for force-directed network
```

`sankey` requires the graph to be a DAG (no cycles); `graph` doesn't. For multi-stage flows (countries -> sectors -> regions), keep the same long shape and let the path of (src,tgt) edges define the stages.

### 4.15 Multi-dim comparison (#15)

```
df_factors_long
+--------------+----------+-------+
| portfolio    | factor   | score |
+--------------+----------+-------+
| Portfolio A  | Quality  |  4.2  |
| Portfolio A  | Momentum |  3.5  |
| Portfolio A  | Value    |  2.1  |
| Portfolio B  | Quality  |  3.0  |
| Portfolio B  | Momentum |  4.8  |
| Portfolio B  | Value    |  3.2  |
+--------------+----------+-------+

mapping = {category: 'factor', value: 'score', series: 'portfolio'}
chart_type = 'radar'
```

Radar wants long form with `category=` on the axis dimension and `series=` on the entity. `parallel_coords` instead wants `dims=[col1, col2, col3, col4]` (wide) with one row per entity, optional `color=` for grouping.

### 4.16 Single scalar (#16)

```
df_risk = pd.DataFrame({'risk_idx': [72]})

mapping = {value: 'risk_idx', name: 'Risk index', min: 0, max: 100}
chart_type = 'gauge'
```

Often you skip the dataset and pass `value: 72` literally -- this is the *one* case where literal numbers in the spec are fine, because the value comes from PRISM's just-pulled scalar.

### 4.17 Rich row-per-entity table (#17)

The same `df_rv` from #9 (and many like it -- watchlists, bond panels, screener results) is consumed by the table widget as is:

```
{"widget": "table", "id": "rv_screen", "dataset_ref": "rv",
  "columns": [
    {"field": "metric",  "label": "Metric"},
    {"field": "current", "label": "Cur",  "format": "number:2", "align":"right"},
    {"field": "z",       "label": "Z",    "format": "signed:2",
      "color_scale": {"min": -2, "max": 2, "palette": "gs_diverging"}},
    {"field": "pct",     "label": "Pctl"},
  ],
  "row_click": {"title_field": "metric",
                  "popup_fields": ["metric","current","low_5y","high_5y","z","pct"]}}
```

DataFrame design rules for tables:
- One row per entity (issuer, ticker, metric, country).
- Plain English column names; the table uses `field` to match them.
- Numbers stay as numbers (don't pre-format with `'1,234'` strings); column `format` does the formatting at render time.
- Add columns whose only purpose is conditional formatting / row highlighting (`d1_pct`, `regime`, `is_breaking`).

### 4.18 Latest snapshot from TS -- KPIs and sparklines (#18)

KPIs DON'T have their own dataset. They reach into existing time-series datasets via dotted source strings. Adding a KPI doesn't require new data; it requires you to designed the time-series DataFrame so that the column is already there.

```
KPI source         <dataset>.<agg>.<column>
                                    rates.latest.us_10y       <-- last value
                                    rates.prev.us_10y         <-- second-to-last
                                    rates.first.us_10y        <-- first value
                                    rates.mean.us_10y         <-- mean
                                    rates.min/max.us_10y      <-- range
                                    rates.sum.flows           <-- aggregator

Sparkline source   <dataset>.<column>      (entire column as a series)
                                    rates.us_10y
```

So if you want a KPI for `2s10s`, your `df_rates` had better have a `2s10s` column. Compute it once when you build the DataFrame:

```python
df_rates['2s10s'] = (df_rates['us_10y'] - df_rates['us_2y']) * 100  # bps
```

`stat_grid` follows the same model: each stat has either `value` (literal) or `source` (dotted). KPIs and stat_grid stats are scalars derived from the time-series datasets, never their own datasets.

### 4.19 Sparse event list -> annotations (#19)

Don't put events in their own chart. Put them as annotations on whichever chart they're context for.

```
events = [
    {"type": "vline", "x": "2022-03-15", "label": "Fed liftoff"},
    {"type": "vline", "x": "2023-03-10", "label": "SVB", "color": "#c53030"},
    {"type": "band",  "x1": "2020-03-01", "x2": "2020-06-01", "label": "COVID"},
    {"type": "point", "x": "2023-07-26", "y": 5.5, "label": "peak"},
]
make_echart(df_rates, "multi_line", mapping={...}, annotations=events)
```

When the event list is dynamic (e.g. earnings calendar, FOMC dates pulled from the data layer), build it in Python from a small DataFrame of events and pass the resulting list to `annotations=`. Don't try to register the event DataFrame as a `manifest.datasets` entry -- annotations don't read from there.

### 4.20 Schedule / agenda -> table widget (#20)

A schedule is a calendar view crossed with metadata. The right viz is almost always a table:

```
df_fomc_calendar
+------------+-------+--------------+-----------------+--------+
| date       | time  | event        | speaker         | tone   |
+------------+-------+--------------+-----------------+--------+
| 2024-05-01 | 14:00 | FOMC meeting | Powell          | hawkish|
| 2024-05-15 | 09:30 | speech       | Williams        | neutral|
| 2024-06-12 | 14:00 | FOMC + SEP   | Powell          | dovish |
+------------+-------+--------------+-----------------+--------+

{"widget": "table", "id": "fomc", "dataset_ref": "fomc_calendar",
  "columns": [
    {"field": "date",    "label": "Date",    "format": "date"},
    {"field": "time",    "label": "Time"},
    {"field": "event",   "label": "Event"},
    {"field": "speaker", "label": "Speaker"},
    {"field": "tone",    "label": "Tone",
      "conditional": [
        {"op": "==", "value": "hawkish", "background": "#fed7d7", "color": "#742a2a"},
        {"op": "==", "value": "dovish",  "background": "#bee3f8", "color": "#1a365d"},
      ]},
  ],
  "row_click": {"title_field": "event",
                  "popup_fields": ["date","time","event","speaker","tone"]}}
```

If you also want to show density on a calendar grid, layer a `calendar_heatmap` on a derived (date, count) DataFrame -- but the schedule itself stays in the table.

---

## 5. Reusing one DataFrame across widgets

The reuse pattern is the heart of why tidy + named matters. A single `rates` DataFrame can power: a multi-line chart, three KPIs, a sparkline, a row-per-day table, and an annotation source -- all without copying the data.

```
datasets["rates"]  (long-form is most flexible: date, tenor, yield, plus computed cols)
  date | tenor | yield | 2s10s_bps | regime
  ...

WIDGET                 PULLED FROM                                CONSUMES
multi_line chart       y=yield, color=tenor                       all rows
kpi 10Y                rates.latest.yield WHERE tenor='us_10y'    one scalar
                        (or rates.latest.us_10y on the wide form)
kpi 2s10s              rates.latest.2s10s_bps                     one scalar
sparkline 10Y          rates.yield WHERE tenor='us_10y'           one column
table snapshot         rates filtered to today                    today's rows
annotation source      events derived in Python from rates        list[dict]
filter on tenor        field='tenor', multiSelect                  long form req'd
```

In practice you often compute *both* a wide-form view and keep the long-form events separate, and pick the form per widget. That's fine. The key is that you produce these DataFrames *once* in `pull_data.py`, save them to `data/`, and `build.py` reads them back; no widget rebuilds the underlying data.

```
+--------------------+              +--------------------------+
| pull_data.py       |              | build.py                 |
| pull_market_data,  |    raw data  | load CSVs                |
| compute spreads,   | -----------> | manifest.datasets={      |
| build wide+long,   |              |   "rates": df_rates_wide,|
| save to data/*.csv |              |   "yields": df_long,     |
+--------------------+              |   "events": df_events    |
                                    | }                        |
                                    | compile_dashboard(...)   |
                                    +--------------------------+
```

---

## 6. From pull_* outputs to a manifest dataset

PRISM's data pulls do not return manifest-ready DataFrames. Each upstream function (`pull_haver_data`, `pull_market_data`, `pull_plottool_data`, FRED, Treasury, plus other API clients) emits its data in the shape that's natural for the source system, not for the dashboard compiler. Bridging the gap is **PRISM's job** -- the compiler does NOT auto-coerce input. It does emit precise diagnostics (see Section 17) when the input shape is wrong, but it never silently fixes it.

### 6.1 Output shapes from the standard pull functions

```
+--------------------+---------+---------------------------------------+
| Function           | Returns | DataFrame contract                    |
+--------------------+---------+---------------------------------------+
| pull_haver_data    | DF      | index: DatetimeIndex(name='date')     |
|                    |         | columns: Haver codes                  |
|                    |         |   ('GDP@USECON', 'JCXFE@USECON')      |
|                    |         | df.attrs['metadata']: list of dicts   |
|                    |         |   per series (display_name, units,    |
|                    |         |   freq, ...)                          |
+--------------------+---------+---------------------------------------+
| pull_market_data   | tuple   | (eod_df, intraday_df) -- TWO frames!  |
|                    |         | Each:                                 |
|                    |         |   index: DatetimeIndex(name='date')   |
|                    |         |   columns: coordinate strings         |
|                    |         |     ('IR_USD_Treasury_10Y_Rate', ...) |
|                    |         |   df.attrs['metadata']: list of dicts |
|                    |         |     per coordinate (display_name,     |
|                    |         |     asset, class, currency, tenor,    |
|                    |         |     units, is_derived, tsdb_symbol)   |
+--------------------+---------+---------------------------------------+
| pull_plottool_data | DF      | index: DatetimeIndex(name='date')     |
|                    |         | columns: labels (or auto from         |
|                    |         |   expressions)                        |
|                    |         | df.attrs['metadata']: list of dicts   |
|                    |         | df.attrs['reverse_lookup']: dict      |
+--------------------+---------+---------------------------------------+
```

Other API clients across `GS/data/apis/` and `GS/data/scrapers/` follow similar conventions: a DataFrame keyed by some natural index (date, ticker, both), columns that match the source's identifier scheme, and a metadata side-channel via `df.attrs`. The cleaning steps below apply to every such pull.

### 6.2 The standard cleaning pipeline

Six steps, applied in order:

```
+-----+-----------------------------+-----------------------------------------+
| #   | Step                        | Code                                    |
+-----+-----------------------------+-----------------------------------------+
| 0   | Unpack tuple                | eod_df, _ = pull_market_data(...)       |
|     | (market only)               |                                         |
+-----+-----------------------------+-----------------------------------------+
| 1   | Reset index                 | df = df.reset_index()                   |
|     | (DatetimeIndex -> column)   |                                         |
+-----+-----------------------------+-----------------------------------------+
| 2   | Rename columns to plain     | df = df.rename(columns={                |
|     | English                     |   'IR_USD_Treasury_10Y_Rate': 'us_10y', |
|     |                             |   'JCXFE@USECON': 'core_cpi'})          |
+-----+-----------------------------+-----------------------------------------+
| 3   | Compute derived columns     | df['2s10s_bps'] = (df.us_10y -          |
|     | (spreads, levels)           |   df.us_2y) * 100                       |
+-----+-----------------------------+-----------------------------------------+
| 4   | Resample to native          | df = df.resample('M').last()            |
|     | frequency                   | (see Section 7 for stock vs flow rules) |
+-----+-----------------------------+-----------------------------------------+
| 5   | Long-form melt (optional)   | df = df.melt(id_vars='date',            |
|     | when filter on group        |   var_name='tenor', value_name='yield') |
+-----+-----------------------------+-----------------------------------------+
| 6   | Drop unused columns         | df = df[['date', 'us_2y', 'us_10y',     |
|     | (keep only what widgets     |   '2s10s_bps']]                         |
|     | reference)                  |                                         |
+-----+-----------------------------+-----------------------------------------+
```

### 6.3 Using pull-time metadata for renames

`df.attrs['metadata']` carries the raw API metadata. PRISM can mine it to build the rename map without hand-coding every coordinate:

```python
df.attrs['metadata'] = [
    {"coordinate": "IR_USD_Treasury_10Y_Rate", "tenor": "10Y", "class": "IR"},
    {"coordinate": "IR_USD_Treasury_2Y_Rate",  "tenor": "2Y",  "class": "IR"},
]

rename = {m['coordinate']: f"us_{m['tenor'].lower()}"
          for m in df.attrs['metadata'] if m['class'] == 'IR'}
df = df.rename(columns=rename)
# columns: 'us_10y', 'us_2y'
```

For Haver, `df.attrs['metadata']` typically has `code` and `display_name`; for plottool, `label` and `expression`. The mapping is contextual -- "US 10Y Treasury Rate" reads well in a tooltip but `us_10y` reads better as an axis tick label after `humanize`. PRISM picks the snake_case form deliberately.

### 6.4 The non-coerce contract

Five things the compiler will NOT do for you:

```
+----+---------------------------------+-------------------------------------+
| #  | What PRISM must do              | What happens otherwise              |
+----+---------------------------------+-------------------------------------+
| 1  | reset_index() before passing    | dataset_dti_no_date_column          |
|    | a DTI-keyed DataFrame           | error names the fix verbatim        |
+----+---------------------------------+-------------------------------------+
| 2  | unpack pull_market_data tuples  | dataset_passed_as_tuple             |
+----+---------------------------------+-------------------------------------+
| 3  | flatten MultiIndex columns      | dataset_columns_multiindex          |
+----+---------------------------------+-------------------------------------+
| 4  | rename opaque codes to plain    | dataset_column_looks_like_code      |
|    | English (legends/tooltips)      | warning (codes appear verbatim)     |
+----+---------------------------------+-------------------------------------+
| 5  | resample to native frequency    | mixed-freq NaN gaps render as       |
|    | per series                      | broken stair-step lines             |
+----+---------------------------------+-------------------------------------+
```

The contract is strict-but-helpful: the compiler refuses to silently auto-coerce because (a) the heuristics are fragile (which DTI becomes the `date` column when the DataFrame already has a `date` column?), (b) shape drift gets papered over and breaks weeks later, (c) the diagnostic system already names the fix precisely. PRISM does the cleaning; the compiler validates it was done.

### 6.5 Worked translation: pull_market_data -> manifest

```python
eod_df, _ = pull_market_data(
    coordinates=['IR_USD_Swap_2Y', 'IR_USD_Swap_10Y'],
    start='2022-01-01', name='rates_eod')

# Step 1: reset DatetimeIndex -> 'date' column
df = eod_df.reset_index()

# Step 2: rename via attrs metadata
rename = {m['coordinate']: f"us_{m['tenor'].lower()}"
          for m in eod_df.attrs['metadata']}
df = df.rename(columns=rename)

# Step 3: compute spreads
df['2s10s_bps'] = (df['us_10y'] - df['us_2y']) * 100

# Step 6: drop unused columns
df = df[['date', 'us_2y', 'us_10y', '2s10s_bps']]

manifest = {..., 'datasets': {'rates': df}, ...}
compile_dashboard(manifest)
```

Three lines of pandas converts the raw `pull_market_data` output to a manifest-ready DataFrame. The compiler accepts it without modification; every chart, KPI, and table reads from the cleaned columns.

---

## 7. Frequency, dates, and the time axis

Time-axis chart types (`line`, `multi_line`, `bar` with date x, `area`, `candlestick`, `calendar_heatmap`) all auto-detect `xAxis.type='time'` from a datetime column. That makes a few preconditions non-negotiable:

1. **Date is a column, not an index.** Reset the index before adding to manifest.
   ```python
   df = df.reset_index().rename(columns={'index': 'date'})
   ```

2. **Resample mixed-frequency data to a single native frequency.** Haver and FRED frequently store monthly/quarterly series at business-day granularity (forward-filled). Plotting raw produces stair-step lines. Pick the right aggregation per series type:
   ```python
   stocks = stocks.resample('M').last()    # stock variables: last value of period
   flows  = flows.resample('M').sum()      # flow variables: sum of period
   rates  = rates.resample('Q').last()     # rate variables: last value of period
   counts = counts.resample('W').sum()     # weekly counts: sum
   ```
   Never plot a wide DataFrame with mixed-frequency NaN gaps -- the line chart breaks visually and the wide-form filter rewire path can't reshape it.

3. **The compiler emits ISO-8601 strings.** When you store a DataFrame in `datasets`, `df_to_source()` formats date columns as `YYYY-MM-DD`. Don't pre-format yourself.

4. **The lookback rule (from README Section 7).** Quarterly/monthly -> 10y. Weekly -> 5y. Daily -> 2y. Intraday -> 5 trading days. Override only when the narrative references "highest since X" -- then start the data at X.

5. **Intraday is fragile.** Wrap intraday pulls in try/except (README 4.5) and let `build.py` fall back to EOD when the intraday DataFrame is missing. The dashboard auto-refresh runs unattended; silent failures cascade.

---

## 8. Naming hygiene and humanize

The editor and the chart builders use your column names directly in three places that are visible to the human reader: legends, tooltips, and table headers. So column names *are* part of the chart.

```
+-------------------------+--------------------------------+
| BAD                     | GOOD                           |
+-------------------------+--------------------------------+
| USGG10YR Index          | us_10y         (or 'US 10Y')   |
| @JCXFE@USECON           | core_cpi_yoy                   |
| FFER@FOMC               | fed_funds                      |
| 1                       | 'q1'                           |
| 'Total'                 | (drop totals row entirely)     |
| ' Region '              | 'region'  (no padding)         |
| ('GDP', 'USDtn')        | 'gdp_usdtn'  (no MultiIndex)   |
| df.index = 'date'       | df['date'] = ...; df.reset_index()|
+-------------------------+--------------------------------+
```

`humanize: True` (default) on chart specs converts:

- `us_10y` -> `US 10Y`
- `core_cpi_yoy` -> `Core CPI YoY`
- `volume_m` -> `Volume M` (hint: include the unit in the name, not a paren)
- `2s10s` -> `2s10s` (already good)
- `gdp_usdtn` -> `Gdp Usdtn` (better: rename the column to `gdp` and use `y_title='GDP (USDtn)'`)

Heuristic: column names should be *what you'd say aloud*. If the legend reading aloud sounds bad, rename the column.

**Units belong on the axis, not in the column name** for non-self-explanatory cases:

```python
# Choice A (acceptable for short labels)
df.columns = ['date', 'us_2y_pct', 'us_10y_pct']
mapping = {x:'date', y:['us_2y_pct','us_10y_pct'], y_title:'Yield (%)'}

# Choice B (preferred -- humanize works better)
df.columns = ['date', 'us_2y', 'us_10y']
mapping = {x:'date', y:['us_2y','us_10y'], y_title:'Yield (%)',
            y_format:'percent'}    # let the formatter handle the unit
```

---

## 9. Filter alignment

A filter is a tiny rule that, at render time, throws out rows from a dataset where `field <op> value` is False. Two implications for DataFrame design:

1. **The filter `field` must be a real column on the dataset.** A `multiSelect` on `region` requires `df['region']`. A `dateRange` on `date` requires `df['date']`. Plan the columns to support every filter you anticipate; if a chart is currently wide-form but you anticipate a filter on series, melt to long form *before* exposing it to the manifest.

2. **The "rewire on filter" path only works for safe shapes.** When a filter targets a chart whose `(chart_type, mapping)` is in the safe set (`line/bar/area/multi_line` wide-form with no `color`, no `stack`, no `trendline`, no `dual_axis_series` for `bar`), the runtime re-renders the chart from the filtered dataset. Otherwise the chart keeps its baseline render but the filter still applies to tables, KPIs, stat_grids on the same dataset.

   Concretely: if you want a filter to *visually reshape* a multi-line, keep it wide-form. If you want it to filter a long-form colored chart, accept that the chart won't auto-rewire -- and either
   (a) live with that (table/KPIs still update), or
   (b) emit two charts side by side (one per common subset).

3. **`dateRange` is auto-resolved against `field='date'`** by default and doesn't need a `default` value (the dropdown defaults to `6M`). The dataset just needs a `date` column.

```
+-----------------------------------------+----------------------------------------------------+
| Filter                                  | DataFrame implication                              |
+-----------------------------------------+----------------------------------------------------+
| {type:'dateRange', field:'date'}        | df has 'date' column with datetime dtype           |
| {type:'multiSelect', field:'tenor'}     | df has 'tenor' column (long form)                  |
| {type:'select', field:'sector',         | df has 'sector', option labels exactly match       |
|   options:['Tech','Financials',...]}    | the values you expect (case-sensitive)             |
| {type:'numberRange', field:'pct'}       | df has 'pct' as numeric                            |
| {type:'slider', field:'z',              | df has 'z' as numeric                              |
|   min:-3, max:3, op:'>='}               |                                                    |
| {type:'toggle', field:'is_breaking'}    | df has 'is_breaking' as bool / 0-1                 |
+-----------------------------------------+----------------------------------------------------+
```

---

## 10. Joins / merges: keep one or split many

```
+-------------------------------------------+-------------------------------------------+
| Pattern                                   | Decision                                  |
+-------------------------------------------+-------------------------------------------+
| Same primary key, same cadence            | Wide DataFrame, columns side by side.     |
| (date, daily) -- e.g. UST 2Y/5Y/10Y/30Y   | One dataset.                              |
+-------------------------------------------+-------------------------------------------+
| Same primary key, different cadence       | Two datasets, no merge. Each chart picks  |
| (rates daily, CPI monthly)                | one. KPI/sparkline/chart per dataset.     |
+-------------------------------------------+-------------------------------------------+
| Different primary keys                    | Two datasets. The drill-down pattern      |
| (rv panel keyed by metric;                | (Section 14) joins them at render time    |
|  rv history keyed by metric+date)         | via row_key + filter_field.               |
+-------------------------------------------+-------------------------------------------+
| Combined panel (date x sector)            | Long form: (date, sector, value).         |
|                                           | One dataset, both filters available.      |
+-------------------------------------------+-------------------------------------------+
| One-off comparison (today vs prior month) | Compute the comparison column (`d1_chg`,  |
|                                           | `mtd_chg`, `z`, `pct`) into the same      |
|                                           | DataFrame. Don't keep two snapshots.      |
+-------------------------------------------+-------------------------------------------+
```

The general rule: **don't merge to merge. Merge only if a single widget needs a column that lives on both inputs.** Otherwise keeping them separate makes refresh cheaper (you re-pull only the side that changed) and filter scopes clearer.

---

## 11. Templates and refresh: data-free shape preserved

For persistent dashboards (README Section 4), the manifest is split into a **template** (data-free) and a **populated manifest** (data-injected). The template lives at `manifest_template.json`; refresh runs `populate_template(template, datasets)` to inject fresh DataFrames keyed by name.

```
manifest_template.json (committed, edited by PRISM)
  datasets:
    rates:  {source: [["date","us_2y","us_5y","us_10y","us_30y","2s10s"]],
             template: True}
    cpi:    {source: [["date","headline","core","trimmed","median"]],
             template: True}
                              |
                              |  populate_template(tpl, {
                              |      "rates": df_rates_today,
                              |      "cpi":   df_cpi_today,
                              |  })
                              v
manifest.json (rebuilt every refresh)
  datasets:
    rates: {source: [["date","us_2y","us_5y","us_10y","us_30y","2s10s"],
                      ["2024-04-22", 4.9, 4.62, 4.55, 4.71, -35],
                      ...]}
    cpi:   {source: [["date","headline","core","trimmed","median"],
                      ...]}
```

What this implies for DataFrame design:

- **Dataset names are stable across refreshes.** `rates` today, `rates` tomorrow. Don't suffix names with timestamps.
- **Column shape is stable across refreshes.** `df_rates` produced by `pull_data.py` always has the same columns. If you add a column, update both `pull_data.py` and the template (and any spec mappings that reference it).
- **`require_all_slots=True`** is your friend in `populate_template`: it raises if a template slot has no fresh DataFrame, catching pull regressions before the dashboard silently shows stale data.

`pull_data.py` is the single owner of "what the DataFrames look like". `build.py` is wire-up only -- it should never compute new columns or transform data.

---

## 12. Common anti-patterns

```
+--------------------------------------------------+--------------------------------------------+
| Anti-pattern                                     | Do instead                                 |
+--------------------------------------------------+--------------------------------------------+
| Literal data rows in the manifest JSON           | Pass DataFrame; compiler converts.         |
| "datasets":{"rates":{"source":[["d","y"],        |                                            |
|  ["2024-01-02",4.4],...]}}                       |                                            |
+--------------------------------------------------+--------------------------------------------+
| Date as DatetimeIndex                            | df.reset_index().rename(columns=...)       |
+--------------------------------------------------+--------------------------------------------+
| Opaque codes as columns                          | Rename to plain English BEFORE charting    |
| "JCXFE@USECON", "USGG10YR"                       | "core_cpi", "us_10y"                       |
+--------------------------------------------------+--------------------------------------------+
| MultiIndex columns                               | df.columns = ['_'.join(c) for c in df.columns]|
| df.columns = MultiIndex.from_tuples(...)         | Then keep names short.                     |
+--------------------------------------------------+--------------------------------------------+
| One DataFrame per chart                          | One DataFrame per (domain, primary key);   |
| df_curve, df_k10y, df_spark, df_table            | many widgets reference it.                  |
+--------------------------------------------------+--------------------------------------------+
| One mega DataFrame with everything               | Split by primary key. Daily rates and      |
|                                                  | monthly CPI don't belong in one frame.     |
+--------------------------------------------------+--------------------------------------------+
| Mixed-frequency NaN gaps                         | Resample to a single native frequency      |
| daily-merged-with-monthly                        | per dataset before charting.               |
+--------------------------------------------------+--------------------------------------------+
| Pre-formatted strings ('1,234')                  | Keep numbers numeric. Use column           |
|                                                  | format='number:0' on the table.            |
+--------------------------------------------------+--------------------------------------------+
| Pre-binned histograms                            | Pass raw observations; use bins= mapping.  |
+--------------------------------------------------+--------------------------------------------+
| 2-D numpy correlation matrix                     | Melt to (asset1, asset2, corr).            |
+--------------------------------------------------+--------------------------------------------+
| KPI dataset of one row of one column             | Reuse the time-series dataset. KPI =       |
|                                                  | <ts_dataset>.latest.<column>.              |
+--------------------------------------------------+--------------------------------------------+
| Per-event chart                                  | Use annotations on the host chart.         |
+--------------------------------------------------+--------------------------------------------+
| Filter targets a column the dataset doesn't have | Add the column to the source DataFrame in  |
|                                                  | pull_data.py.                              |
+--------------------------------------------------+--------------------------------------------+
| Long-form chart with color= and a filter         | Either (a) accept that the chart keeps its |
|  expecting visual rewire on filter               | baseline (filters still affect KPIs/       |
|                                                  | tables on same dataset), or (b) switch to  |
|                                                  | wide-form for that chart.                  |
+--------------------------------------------------+--------------------------------------------+
| Dataset name changes per refresh                 | Names are nouns: rates / cpi / equities.   |
| 'rates_2024_04_22' -> 'rates_2024_04_23'         | The template references stable names.      |
+--------------------------------------------------+--------------------------------------------+
| Hand-edits to manifest.json (the build artifact) | Edit manifest_template.json. Refresh       |
|                                                  | rebuilds manifest.json from it.            |
+--------------------------------------------------+--------------------------------------------+
```

---

## 13. Cheat-sheet: archetype -> chart -> mapping

Pin this. It's the answer to "I have a DataFrame shaped X, what chart do I build?"

```
+----+-----------------------+------------------------+----------------------------------------+
| #  | Archetype             | Mapping (key=col)      | chart_type                             |
+----+-----------------------+------------------------+----------------------------------------+
| 1  | (date, value)         | x=date, y=value        | line                                   |
| 2  | (date, v1, v2, ...)   | x=date, y=[v1,v2,...]  | multi_line, area                       |
| 3  | (date, group, value)  | x=date, y=value,       | multi_line, area                       |
|    |  long                 | color=group            |                                        |
| 4  | (cat, value)          | x=cat, y=value         | bar / bar_horizontal                   |
|    |                       | category=cat,          | pie / donut / funnel                   |
|    |                       |  value=value           |                                        |
| 5  | (cat, group, value)   | x=cat, y=value,        | bar (stack=True | False)               |
|    |                       | color=group            | scatter color=group                    |
| 6  | (x_num, y_num,        | x, y, color, [size,    | scatter, scatter_multi                 |
|    |  [color])             |  trendlines]           |                                        |
| 7  | (value)               | x=value, bins=N        | histogram                              |
| 8  | (group, value)        | x=group, y=value       | boxplot                                |
| 9  | (cat, lo, hi, cur,    | y=cat, x=cur,          | bullet                                 |
|    |  [color_by, label])   | x_low, x_high          |                                        |
| 10 | (date, o, c, l, h)    | x, open, close, low,   | candlestick                            |
|    |                       | high                   |                                        |
| 11 | (date, value) one yr  | date, value, [year]    | calendar_heatmap                       |
| 12 | (xc, yc, value) long  | x, y, value            | heatmap                                |
| 13a| (l1, l2, ..., value)  | path=[l1,l2,...],      | treemap, sunburst                      |
|    |  hierarchy by path    | value                  |                                        |
| 13b| (name, parent,        | name, parent, [value]  | treemap, sunburst, tree                |
|    |  [value])             |                        |                                        |
| 14 | (src, tgt, value)     | source, target, value  | sankey, graph                          |
| 15a| (entity, dim, value)  | category=dim,          | radar                                  |
|    |  long                 | value=value,           |                                        |
|    |                       | series=entity          |                                        |
| 15b| (entity, d1, d2, ...) | dims=[d1,d2,...],      | parallel_coords                        |
|    |  wide                 | color=group            |                                        |
| 16 | scalar                | value                  | gauge                                  |
| 17 | (entity, attr1, ...)  | columns[]              | table widget (not a chart)             |
| 18 | (any TS DataFrame)    | source =               | KPI / stat_grid (not a chart)          |
|    |                       | "<ds>.<agg>.<col>"     |                                        |
| 19 | (date, label, ...)    | annotations=[...]      | overlays on another chart              |
| 20 | schedule rows         | columns[]              | table widget                           |
+----+-----------------------+------------------------+----------------------------------------+
```

---

## 14. Drill-down: the row_click + dataset pattern

The richest dashboard pattern is "click a table row -> see a mini chart of just that entity's history." It requires *two* datasets that share a primary key, and a small bridge in the table widget.

```
PRIMARY DATASET (driver of the table)
 datasets["bonds"]
  cusip      | issuer  | sector  | rating | spread_bp | duration | ...
  -----------+---------+---------+--------+-----------+----------+
  912828ABC  | UST     | Govt    | AAA    |   0       |   2.0    |
  912810XYZ  | UST     | Govt    | AAA    |   0       |  10.0    |
  ...

DETAIL DATASET (history per row)
 datasets["bond_hist"]
  cusip      | date       | price   | spread_bp
  -----------+------------+---------+----------
  912828ABC  | 2024-01-02 | 99.50   |   0
  912828ABC  | 2024-01-03 | 99.55   |   0
  912810XYZ  | 2024-01-02 | 95.20   |   0
  ...

WIRING
 table.row_click.detail.sections = [
   {"type": "chart", "chart_type": "line",
     "dataset": "bond_hist",        // detail dataset
     "row_key": "cusip",            // PK column on the table dataset
     "filter_field": "cusip",       // PK column on the detail dataset
     "mapping": {"x":"date", "y":"price"}}
 ]
```

So the template for any drill-down is: **two datasets, one per granularity, sharing a primary key column with the same name.** Don't try to embed mini-time-series inside the primary dataset's cells; keep the long-form history separate.

The same pattern extends to sub-tables (`{"type":"table", "dataset":"bond_events", "filter_field":"cusip"}`), per-row stats, per-row markdown templates -- the only requirement is that the secondary dataset has a column matching `row_key`.

### Sizing the detail dataset

The detail dataset's row count is `entities x history_length`. This is where drill-down dashboards blow past the row budget (Section 17):

```
+----+--------------------------+---------+----------+--------+----------------+
| #  | Universe                 | History | History  | Total  | Budget         |
|    |                          | freq    | length   | rows   | status         |
+----+--------------------------+---------+----------+--------+----------------+
| 1  | 250 bonds (full)         | daily   | 2y/500d  | 125k   | ERROR (>50k)   |
| 2  | 250 bonds, 6M lookback   | daily   | 6m/125d  |  31k   | warn (>10k)    |
| 3  | top-30 bonds, 2Y         | daily   | 2y/500d  |  15k   | warn (>10k)    |
| 4  | top-30 bonds, 6M         | daily   | 6m/125d  |   3.7k | clean          |
| 5  | 50 metrics, 5Y           | daily   | 5y/1250d |  62k   | ERROR (>50k)   |
| 6  | 50 metrics, 2Y           | daily   | 2y/500d  |  25k   | warn (>10k)    |
+----+--------------------------+---------+----------+--------+----------------+
```

The screening principle: a drill-down only matters for the rows the table actually surfaces. If the table shows the top 30 hits out of 250 candidates, the detail dataset only needs the history for those 30. Filter at pull time -- not in `build.py`, where the data has already been pulled -- so the dashboard refresh stays fast and the manifest stays under budget.

For the rare case where the table needs the full universe AND the drill-down needs full history, the lazy-load pattern (an API endpoint that returns per-entity history on demand) is the only clean answer. That requires a backend endpoint outside the scope of `compile_dashboard`.

---

## 15. Schedules, calendars, and event-list patterns

Schedules are not a chart type; they're the table widget. Calendar-style densities (one cell per day) are `calendar_heatmap`. Sparse events on a time axis are annotations. Use whichever matches the question.

```
+------------------------------+------------------------+----------------------------------+
| Question the user is asking  | Right viz              | DataFrame shape                  |
+------------------------------+------------------------+----------------------------------+
| When did things happen?      | table widget           | (date, time, event, attrs...)    |
| Sorted, scrollable           |                        | one row per event                |
| (FOMC meetings, earnings,    |                        |                                  |
|  econ calendar)              |                        |                                  |
+------------------------------+------------------------+----------------------------------+
| How dense was activity day   | calendar_heatmap       | (date, value)                    |
| by day over a year?          |                        | one row per calendar day         |
| (trade volume, news count,   |                        |                                  |
|  daily returns)              |                        |                                  |
+------------------------------+------------------------+----------------------------------+
| Where on the price chart     | line + annotations     | underlying TS unchanged;         |
| did key events land?         |                        | events as list[dict]              |
| (vlines for FOMC, bands      |                        | ({"type":"vline", "x":...,       |
|  for COVID, points for       |                        |   "label":...})                  |
|  earnings beats)             |                        |                                  |
+------------------------------+------------------------+----------------------------------+
| Days-until / countdown to    | KPI                    | one scalar + a delta_source for  |
| next event                   | source =               | "days since prior event" if      |
|                              |  "events.latest.days_until"| useful                       |
+------------------------------+------------------------+----------------------------------+
| Monthly distribution of      | bar by month from      | pre-aggregate to                 |
| events                       | (month, count)         | (month, count); bar              |
+------------------------------+------------------------+----------------------------------+
```

Two specific gotchas:

- **Calendar heatmap requires one row per day** in the date range, even days with `value=0`. If you only have 100 events in a year, build the daily zero-padded panel before charting:
  ```python
  daily = (pd.date_range('2025-01-01','2025-12-31')
              .to_frame(index=False, name='date'))
  daily = daily.merge(events.groupby('date').size().rename('count'),
                       on='date', how='left').fillna({'count': 0})
  ```
- **Annotations are per-chart, not per-dataset.** If three charts on the dashboard should all show the same FOMC vlines, pass the same `annotations=` list into all three chart specs (or build the list once in `build.py` and reuse).

---

## 16. Worked examples (full DataFrame -> manifest)

### 15.1 Macro dashboard (curve + spread KPI + table)

```python
# pull_data.py
df_rates = pull_market_data(
    coordinates=['IR_USD_Swap_2Y','IR_USD_Swap_5Y',
                  'IR_USD_Swap_10Y','IR_USD_Swap_30Y'],
    start_date='2022-01-01', name='rates_eod',
).rename(columns={'IR_USD_Swap_2Y':'us_2y',
                    'IR_USD_Swap_5Y':'us_5y',
                    'IR_USD_Swap_10Y':'us_10y',
                    'IR_USD_Swap_30Y':'us_30y'})
df_rates['2s10s_bps'] = (df_rates['us_10y'] - df_rates['us_2y']) * 100
df_rates['5s30s_bps'] = (df_rates['us_30y'] - df_rates['us_5y']) * 100
df_rates = df_rates.reset_index().rename(columns={'index':'date'})

# At this point df_rates is one tidy wide-form DataFrame:
#   date | us_2y | us_5y | us_10y | us_30y | 2s10s_bps | 5s30s_bps
# saved to data/rates_eod.csv.

# build.py (loads df, populate_template, compile_dashboard)
manifest = {
  "schema_version": 1, "id": "rates_monitor", "title": "Rates monitor",
  "metadata": {"kerberos":"...", "dashboard_id":"rates_monitor",
                "data_as_of": str(df_rates['date'].max()),
                "refresh_frequency":"daily"},
  "datasets": {"rates": df_rates},   # ONE dataset, many widgets
  "filters": [
    {"id":"dt", "type":"dateRange", "field":"date",
      "default":"6M", "targets":["*"]}
  ],
  "layout": {"kind":"grid", "cols":12, "rows":[
    [{"widget":"kpi", "id":"k2y",  "label":"2Y",
       "source":"rates.latest.us_2y", "suffix":"%",
       "delta_source":"rates.prev.us_2y", "delta_label":"vs prev",
       "sparkline_source":"rates.us_2y", "w":3},
     {"widget":"kpi", "id":"k10y", "label":"10Y",
       "source":"rates.latest.us_10y", "suffix":"%",
       "delta_source":"rates.prev.us_10y", "delta_label":"vs prev",
       "sparkline_source":"rates.us_10y", "w":3},
     {"widget":"kpi", "id":"k2s10s","label":"2s10s",
       "source":"rates.latest.2s10s_bps", "suffix":"bp",
       "delta_source":"rates.prev.2s10s_bps", "delta_label":"vs prev",
       "sparkline_source":"rates.2s10s_bps", "w":3},
     {"widget":"kpi", "id":"k5s30s","label":"5s30s",
       "source":"rates.latest.5s30s_bps", "suffix":"bp", "w":3}],
    [{"widget":"chart", "id":"curve", "w":12, "h_px":380,
       "spec":{"chart_type":"multi_line", "dataset":"rates",
                "mapping":{"x":"date",
                            "y":["us_2y","us_5y","us_10y","us_30y"],
                            "y_title":"Yield (%)"},
                "title":"UST curve"}}],
    [{"widget":"chart", "id":"spread", "w":12, "h_px":280,
       "spec":{"chart_type":"line", "dataset":"rates",
                "mapping":{"x":"date", "y":"2s10s_bps",
                            "y_title":"2s10s (bps)"},
                "title":"2s10s curve slope",
                "annotations":[{"type":"hline","y":0,
                                  "label":"flat","style":"dashed"}]}}],
  ]},
  "links":[{"group":"sync","members":["curve","spread"],
             "sync":["axis","tooltip","dataZoom"]}],
}

compile_dashboard(manifest, output_path='users/.../dashboard.html')
```

ONE DataFrame. SEVEN widgets. The dateRange filter rewires both line charts (wide-form, no color/stack -> safe). The KPIs/sparklines re-evaluate against the filtered dataset automatically. No data was duplicated, no widget computed its own values.

### 15.2 RV screen + drill-down

```python
# Two datasets, same primary key 'metric'
df_rv = pd.DataFrame([
    {"metric":"2s10s",     "current":  38, "low_5y":-20, "high_5y":  45,
     "z": 1.2, "pct":0.85, "ytd_chg":-12, "regime":"steepening"},
    {"metric":"5s30s",     "current":  -5, "low_5y":-10, "high_5y":  60,
     "z":-1.5, "pct":0.12, "ytd_chg": -8, "regime":"steepening"},
    {"metric":"10Y real",  "current":1.85, "low_5y":0.5, "high_5y":2.4,
     "z": 0.1, "pct":0.45, "ytd_chg":  0.2,"regime":"neutral"},
])

# History per metric:
df_rv_hist = pd.concat([
    pd.DataFrame({"metric":"2s10s",
                   "date":pd.date_range("2022-01-01", periods=600, freq="B"),
                   "value": ...}),
    pd.DataFrame({"metric":"5s30s",
                   "date":pd.date_range("2022-01-01", periods=600, freq="B"),
                   "value": ...}),
    pd.DataFrame({"metric":"10Y real",
                   "date":pd.date_range("2022-01-01", periods=600, freq="B"),
                   "value": ...}),
])

manifest = {
  "schema_version":1, "id":"rv","title":"Rates RV",
  "datasets": {"rv": df_rv, "rv_hist": df_rv_hist},
  "layout":{"kind":"grid","cols":12,"rows":[
    [{"widget":"chart","id":"bullet","w":12,"h_px":260,
       "spec":{"chart_type":"bullet","dataset":"rv",
                "mapping":{"y":"metric","x":"current",
                            "x_low":"low_5y","x_high":"high_5y",
                            "color_by":"z","label":"pct"},
                "title":"5Y range"}}],
    [{"widget":"table","id":"rv_table","w":12,"dataset_ref":"rv",
       "columns":[
         {"field":"metric",  "label":"Metric"},
         {"field":"current", "label":"Cur",   "format":"number:2","align":"right"},
         {"field":"z",       "label":"Z",     "format":"signed:2",
           "color_scale":{"min":-2,"max":2,"palette":"gs_diverging"}},
         {"field":"pct",     "label":"Pctl",  "format":"percent:0"},
         {"field":"ytd_chg", "label":"YTD",   "format":"delta:2"},
         {"field":"regime",  "label":"Regime"},
       ],
       "row_click":{
         "title_field":"metric",
         "subtitle_template":"z={z:signed:2} ; pctile={pct:percent:0}",
         "detail":{
           "wide":True,
           "sections":[
             {"type":"stats","fields":[
                {"field":"current","label":"Cur","format":"number:2"},
                {"field":"z","label":"Z","format":"signed:2"},
                {"field":"pct","label":"Pctl","format":"percent:0"},
             ]},
             {"type":"chart","title":"5Y history",
               "chart_type":"line",
               "dataset":"rv_hist",
               "row_key":"metric",
               "filter_field":"metric",
               "mapping":{"x":"date","y":"value"}},
           ]}}
     }],
  ]}
}
```

The bullet, table, and drill-down chart all read from the same shape; no data is restructured per widget.

---

## 17. Data budget limits

The compiler embeds every dataset's rows in the dashboard HTML. A dashboard with too many rows -- or rows with too many bytes each -- produces a multi-MB HTML payload that takes seconds to parse, megabytes of S3 storage per refresh, and a sluggish browser. Size budgets are enforced as deterministic diagnostic codes (Section 17 of the README's diagnostic registry):

```
+---------------------------+----------+----------+---------------------------+
| Metric                    | Warning  | Error    | Notes                     |
+---------------------------+----------+----------+---------------------------+
| Single dataset rows       |  10,000  |  50,000  | daily-2y is ~500 rows;    |
|                           |          |          | daily-10y is ~2,500       |
+---------------------------+----------+----------+---------------------------+
| Single dataset bytes      |   1 MB   |   2 MB   | serialised JSON cost      |
+---------------------------+----------+----------+---------------------------+
| Total manifest bytes      |   3 MB   |   5 MB   | 5 MB+ HTML feels sluggish |
+---------------------------+----------+----------+---------------------------+
| Table widget rows         |   1,000  |   5,000  | every row renders to the  |
|                           |          |          | DOM regardless of         |
|                           |          |          | max_rows (viewport cap)   |
+---------------------------+----------+----------+---------------------------+
```

Default behaviour: warnings + errors are emitted as diagnostics; compile still produces HTML so PRISM can iterate. `compile_dashboard(strict=True)` raises a `ValueError` on any error-severity diagnostic -- use this in refresh pipelines and CI so a bloated dashboard never gets published.

When a dataset trips the row error, three repair strategies in preference order:

```
+------+-----------------------+----------------------------------------------+
| Pref | Strategy              | When                                         |
+------+-----------------------+----------------------------------------------+
| 1    | Top-N filter at       | Universe < 500 entities, history < 2Y        |
|      | pull time             | Only fetch history for the top 20-50 by the  |
|      |                       | screening metric.                            |
+------+-----------------------+----------------------------------------------+
| 2    | Reduce lookback       | Universe < 200 entities                      |
|      |                       | 2Y -> 6M halves the rows. 1Y intraday-1m ->  |
|      |                       | EOD daily reduces 100x.                      |
+------+-----------------------+----------------------------------------------+
| 3    | Lazy-load via API     | Universe > 500 entities OR history > 2Y      |
|      |                       | Don't embed; the drill-down chart calls      |
|      |                       | per-entity history on demand. (Requires a    |
|      |                       | backend endpoint.)                           |
+------+-----------------------+----------------------------------------------+
```

Worked example. A bond screen with 250 issuers and 2Y of daily price history would embed `250 * 500 = 125,000` rows -- past the row error. Top-N filtering down to 30 issuers (the screening hits) cuts to 15,000 (still warned, but well under the error). Reducing the lookback to 6M cuts further to 3,750 (clean). The compile-time diagnostic names this trade-off so PRISM sees the math without having to estimate.

The drill-down pattern (Section 14) is meant exactly to enable strategies 1 and 3. The detail dataset is keyed by the same primary key as the table dataset; the row-click chart filters at render time. **The data still has to be in the manifest** -- the compiler embeds whatever you pass. Top-N at pull time is the only way to keep the manifest small while still supporting drill-down on every screened row.

---

## 18. Quick checklist before you compile

1. Every `manifest.datasets[name]` is a tidy DataFrame with plain English columns.
2. Date columns are columns, not indexes (Section 6: PRISM runs `df.reset_index()`; the compiler does not). Resample to native frequency.
3. `pull_market_data` tuples are unpacked. MultiIndex columns are flattened. Opaque API codes are renamed before passing.
4. Every filter `field` is a real column on the targeted datasets.
5. No literal data rows in `mapping`. Every numeric value the chart shows comes from a `dataset` column.
6. KPIs reuse a time-series dataset via dotted source. No "kpi-only" datasets.
7. Tables reference an existing dataset via `dataset_ref`; columns are computed in `pull_data.py`, not hand-formatted.
8. Drill-down detail charts/tables use a separate dataset that shares the row's primary key as a column.
9. Dataset names are stable nouns. Templates reference them; refreshes preserve them.
10. If a chart needs to *visually* reshape on filter change, it's wide-form line/multi_line/bar/area without color/stack/trendline. Otherwise the chart keeps its baseline.
11. Schedules are tables; calendar densities are `calendar_heatmap`; events are annotations on host charts.
12. Every dataset is under the row + byte budget (Section 17): < 50k rows, < 2 MB serialised, total manifest < 5 MB. Refresh pipelines call `compile_dashboard(strict=True)` so a budget breach hard-fails before publication.

If all 12 are true, the manifest is mechanical to author and the refresh pipeline is deterministic.
