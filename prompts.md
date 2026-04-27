# Context-extraction: live Intraday Rates Monitor browser-runtime probe

I shipped a staging-side fix for an empty-intraday-charts bug
(four hard-coded `strftime('%Y-%m-%d')` calls in `echart_dashboard.py`
+ `echart_studio.py` that truncated sub-day timestamps; replaced with
a conditional formatter that emits full ISO-8601 with time + tz when
any sub-day component is present, date-only otherwise). All 502 unit
tests pass and 15 demo dashboards still build cleanly. Synthetic
intraday repro (`dev/intraday_diag.py`, 12 variants) also all pass.

The live "Intraday Rates Monitor" dashboard at
`users/goyalri/dashboards/intraday_rates_monitor/` was broken
yesterday in a way that staging's pre-fix repro matched. I want to
confirm whether the live PRISM has the SAME four-callsite drift
staging had, by reading what the chart's actual ECharts option looks
like in the rendered browser. If yes, the next staging -> PRISM
drag-and-drop will land my fix and the live dashboard recovers. If
no (PRISM has only some subset of the callsites broken / fixed),
that's information I need.

Please run the introspection below and answer EVERY question
verbatim. Do not paraphrase. Do not summarise. If a section can't
be answered, add a final `## Could not resolve` with what you tried.

Use `execute_analysis_script` for the file-read parts. For the
browser-runtime parts, you'll need to render the dashboard's
compiled HTML. If you can't drive a browser from PRISM directly,
fall back to reading the compiled `manifest.json` from S3 and
inferring what `series[0].data` would be at compile time --
explicitly note when you're inferring vs. measuring.

---

## 1. Browser-runtime probe of the live dashboard

a. Render `users/goyalri/dashboards/intraday_rates_monitor/dashboard.html`
   in whatever programmatic-browser surface you have available
   (selenium / playwright / puppeteer / something else). Switch to
   the `intraday` tab. Wait for the chart instances to settle (1.5s
   is enough). Then evaluate this JS in the page context and paste
   the entire output verbatim:

```javascript
() => {
  const D = window.DASHBOARD || {};
  const charts   = D.charts   || {};
  const datasets = D.datasets || {};
  const out = {_meta: {url: location.href}};

  // Manifest dataset shape (after JS-side normalisation).
  const idy   = datasets.rates_intraday;
  const idySrc  = (idy && (idy.source || idy)) || [];
  const idyBody = Array.isArray(idySrc) ? idySrc.slice(1) : [];
  const distinct = (() => {
    const s = new Set();
    idyBody.forEach(r => s.add(String(r[0])));
    return s.size;
  })();
  out._dataset = {
    rows:        idyBody.length,
    distinct_x:  distinct,
    first_x:     idyBody.length ? String(idyBody[0][0]) : null,
    last_x:      idyBody.length ? String(idyBody[idyBody.length-1][0]) : null,
    first_x_full: idyBody.length ? idyBody[0] : null,
    last_x_full:  idyBody.length ? idyBody[idyBody.length-1] : null,
  };

  // Per-chart probe: for each intraday widget, capture both
  // dataset-route (opt.dataset[0].source) and inline-route
  // (opt.series[N].data) shapes. The two diverge if some widgets
  // are dataset-rewired and others aren't, which is exactly what
  // staging's analysis predicted.
  ['intraday_treasuries', 'intraday_swaps'].forEach(cid => {
    const rec = charts[cid];
    if (!rec || !rec.inst) { out[cid] = null; return; }
    const opt = rec.inst.getOption();
    const xAxis = (opt.xAxis || [])[0] || {};
    const dz0 = (opt.dataZoom || [])[0] || {};
    const dz1 = (opt.dataZoom || [])[1] || {};

    // Dataset route
    const ds = (opt.dataset || [])[0] || {};
    const dsSrc = ds.source || [];
    const dsBody = Array.isArray(dsSrc) ? dsSrc.slice(1) : [];
    const dsDistinctX = (() => {
      const s = new Set();
      dsBody.forEach(r => s.add(String(r[0])));
      return s.size;
    })();

    // Inline-series route
    const series = opt.series || [];
    const s0 = series[0] || {};
    const sd = Array.isArray(s0.data) ? s0.data : [];
    const seriesDistinctX = (() => {
      const s = new Set();
      sd.forEach(p => s.add(String(Array.isArray(p) ? p[0] : (p && p.value ? p.value[0] : ''))));
      return s.size;
    })();

    out[cid] = {
      x_axis_type:    xAxis.type || null,
      x_axis_min:     xAxis.min  != null ? String(xAxis.min) : null,
      x_axis_max:     xAxis.max  != null ? String(xAxis.max) : null,
      dz0_type:       dz0.type        || null,
      dz0_start_pct:  dz0.start       != null ? dz0.start    : null,
      dz0_end_pct:    dz0.end         != null ? dz0.end      : null,
      dz0_startValue: dz0.startValue  != null ? String(dz0.startValue) : null,
      dz0_endValue:   dz0.endValue    != null ? String(dz0.endValue)   : null,
      dz1_type:       dz1.type        || null,

      // Dataset route
      dataset_rows:        dsBody.length,
      dataset_distinct_x:  dsDistinctX,
      dataset_first_row:   dsBody.length ? dsBody[0] : null,
      dataset_last_row:    dsBody.length ? dsBody[dsBody.length-1] : null,

      // Inline-series route
      n_series:            series.length,
      series0_type:        s0.type || null,
      series0_encode:      s0.encode || null,
      series0_data_len:    sd.length,
      series0_data_sample: sd.slice(0, 3),
      series0_data_tail:   sd.slice(-3),

      // Widget metadata
      dataset_ref:         (D.WIDGET_META || {})[cid] && (D.WIDGET_META || {})[cid].dataset_ref || null,
    };
  });

  return out;
}
```

The most diagnostic field is `series0_data_sample` for each chart.
Two scenarios:

  * **All x-values are date-only** (`"2026-04-27"` repeated 722 times)
    -> the chart-builder strftime callsites are still date-truncating.
    Fix the next drag-and-drop will deliver lands.
  * **All x-values are full ISO** (`"2026-04-27 06:38:00-04:00"` etc.)
    -> the inline-series path has been independently fixed PRISM-side
    too. Probably means PRISM-side has its own divergent fix that
    needs reconciling with staging's.

`dataset_distinct_x` vs `series0_data_len` discrepancies tell us
which path the chart is actually using at render time.

## 2. Source-file confirmation (from `ai_development/dashboards/`)

Read these files on S3 (or wherever PRISM-side `ai_development/`
lives) and paste each function's BODY verbatim. The fix below is
what staging now ships; I want to know how PRISM's current code
differs.

a. `ai_development/dashboards/echart_dashboard.py::df_to_source`
   (signature + body). I expect this to have been hand-fixed
   PRISM-side (live `manifest.json.datasets.rates_intraday.source`
   has full ISO timestamps per yesterday's introspection).

b. `ai_development/dashboards/echart_dashboard.py::_columns_to_source`
   (signature + body). Same: did PRISM hand-fix this?

c. `ai_development/dashboards/echart_studio.py::_rows`
   (signature + body). This is the inline-series path.

d. `ai_development/dashboards/echart_studio.py::_col_to_list`
   (signature + body).

For each, report:
  * Whether the function calls `strftime("%Y-%m-%d")` unconditionally
  * Whether it has been replaced by a conditional helper
  * Line numbers of any datetime formatting in the body

## 3. The staging fix (for cross-reference)

For your reference, here is what staging now ships in
`echart_studio.py`. The four call-sites all delegate to these helpers:

```python
def _format_datetime_series(ser):
    """Convert a datetime64 Series to ISO-8601 strings, preserving sub-day
    component when present.

    Output formats:
      * date-only (every value is calendar-day-aligned)  -> "%Y-%m-%d"
      * sub-day, tz-naive                                -> "%Y-%m-%d %H:%M:%S"
      * sub-day, tz-aware                                -> isoformat(sep=' ')
                                                            e.g. "2026-04-27 06:38:00-04:00"
    """
    import pandas as pd
    if not pd.api.types.is_datetime64_any_dtype(ser):
        return ser
    valid = ser.dropna()
    if len(valid) == 0:
        return ser.dt.strftime("%Y-%m-%d")
    has_sub_day = bool(((valid.dt.hour != 0)
                          | (valid.dt.minute != 0)
                          | (valid.dt.second != 0)
                          | (valid.dt.microsecond != 0)
                          | (valid.dt.nanosecond != 0)).any())
    if not has_sub_day:
        return ser.dt.strftime("%Y-%m-%d")
    if ser.dt.tz is not None:
        return ser.apply(
            lambda x: None if pd.isna(x) else x.isoformat(sep=' '))
    return ser.dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_datetime_value(v):
    """Per-value version of `_format_datetime_series`."""
    import pandas as pd
    if not isinstance(v, pd.Timestamp):
        return v
    if pd.isna(v):
        return None
    has_sub_day = bool(v.hour or v.minute or v.second
                          or v.microsecond or v.nanosecond)
    if not has_sub_day:
        return v.strftime("%Y-%m-%d")
    if v.tz is not None:
        return v.isoformat(sep=' ')
    return v.strftime("%Y-%m-%d %H:%M:%S")
```

If your introspection in §2 reveals PRISM has a different fix
(different format string, different conditional logic, different
helper name, etc.), paste it verbatim so I can decide whether to
align staging to PRISM's choice or vice versa before the next
drag-and-drop.

---

Reminder: paste exact JS output, exact source bodies, exact line
numbers. Do not summarise. If something isn't resolvable, end
with a `## Could not resolve` section.
