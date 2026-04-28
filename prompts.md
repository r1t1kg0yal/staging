## Context extraction: valuation-vs-earnings-revisions widget

I have a dashboard called something like "tech and semis earnings monitor"
(I am `goyalri`). It contains a widget titled approximately
**"VALUATION VS. EARNINGS REVISIONS"** -- three groups in the legend:
Software, Semiconductors, MegaCap Tech. Almost certainly chart_type
`scatter_multi` (x = valuation, y = earnings revisions, color = sub-industry).

Symptom: the chart's plot area renders as a single solid gold/khaki
rectangle. No visible axes, no visible points, no visible trendlines.
Either the axes are blown out so all points collapse into one pixel,
or one marker is being rendered the size of the whole plot, or a
visualMap / markArea is painting the grid. We need to figure out which.

Do the following introspection. Use `list_ai_repo` and
`execute_analysis_script` as needed. Reply with the requested artefacts
verbatim, no paraphrasing.

### 1. Locate the dashboard

1. List `users/goyalri/dashboards/dashboards_registry.json`. From the
   `dashboards[]` list, return the entry whose `name` / `id` matches
   "tech" + "semis" + "earnings". Return that entry verbatim
   (the full dict).
2. Confirm the dashboard's S3 folder. Print every file under
   `users/goyalri/dashboards/<id>/` and `users/goyalri/dashboards/<id>/scripts/`
   and `users/goyalri/dashboards/<id>/data/` (path + size).

### 2. Manifest spec for the widget

3. Read `users/goyalri/dashboards/<id>/manifest_template.json`. Find the
   widget whose `spec.title` matches "VALUATION VS. EARNINGS REVISIONS"
   (case-insensitive, allow for trailing periods). Return that single
   widget block verbatim -- the full `spec` dict, including
   `chart_type`, `dataset` (and any inline `dataset_ref`), `mapping`,
   `palette`, and any `options` / `chart_zoom` / `axes` keys.
4. Read `users/goyalri/dashboards/<id>/manifest.json` (the compiled,
   data-embedded artefact). Return the same widget's compiled block
   verbatim. We want to compare template vs compiled side by side.

### 3. Compiled ECharts option for the widget

5. From the compiled `manifest.json`, extract the ECharts `option` dict
   for that single chart and return it verbatim. Specifically include
   these subtrees in full:
   - `xAxis` (full dict, including `min`, `max`, `scale`, `nice`, `type`)
   - `yAxis` (same)
   - `series` (every series object: `type`, `name`, `symbol`, `symbolSize`,
     `itemStyle`, `data` length, plus the FIRST 10 and LAST 10 entries
     of `series[*].data` so we can see the actual numeric tuples)
   - `visualMap` (if present, the full block)
   - `dataZoom` (full list)
   - any `markArea` / `markPoint` / `markLine` blocks anywhere in series
6. For each `series` block, also return:
   - `len(series.data)`
   - `min(x)`, `max(x)`, `min(y)`, `max(y)` across `series.data`
     (treat `series.data` as `[[x, y, ...], ...]`)
   - count of any `null` / `None` / `NaN` / `Infinity` values that
     appear in any tuple position

### 4. Underlying dataset

7. The widget's `spec.dataset` references `manifest.datasets.<name>`.
   Locate that dataset in `manifest.json` (`datasets.<name>.rows` /
   `.columns`) and also locate the matching CSV under
   `users/goyalri/dashboards/<id>/data/`. For BOTH copies, return:
   - column list with dtypes
   - row count
   - `df.describe()` on every numeric column
   - count of NaN / Inf per column
   - the FIRST 5 and LAST 5 rows verbatim
   - the row(s) corresponding to `min(x)`, `max(x)`, `min(y)`, `max(y)`
     of whichever columns the widget's `mapping.x` and `mapping.y` point at
8. Print the values of `mapping.x`, `mapping.y`, `mapping.color`, and
   (if present) `mapping.size` and `mapping.trendlines` from the
   widget's spec.

### 5. Build script

9. Read `users/goyalri/dashboards/<id>/scripts/build.py`. Return the
   full block of code that constructs THIS widget's spec (the dict
   passed into the manifest under that title). Do not return the whole
   file -- just the relevant assignment / function for the
   valuation-vs-earnings widget.
10. Read `users/goyalri/dashboards/<id>/scripts/pull_data.py`. Return
    the section that produces the dataframe feeding the widget --
    specifically, the column-construction / formula for the valuation
    metric on `mapping.x` and the earnings-revisions metric on
    `mapping.y`. Quote the relevant lines verbatim.

### 6. Refresh state

11. Return the contents of
    `users/goyalri/dashboards/<id>/refresh_status.json` verbatim.

### Output format

Reply with one section per numbered item above. Use fenced code blocks
for every JSON/dict/dataframe payload. Do not summarise; we want raw
material.

If part of this prompt cannot be answered (file missing, widget title
doesn't match anything, dataset name not found), add a brief
`## Could not resolve` section at the end listing what you tried and
what blocked it.