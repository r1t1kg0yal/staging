# Context-extraction: structure of the Intraday Rates Monitor dashboard

I have a persistent dashboard titled **"Intraday Rates Monitor"** under
`users/goyalri/dashboards/`. As of today (2026-04-27) the EOD widgets
("Today's Read" KPI block: UST 10Y, 2s10s, 10Y swap spread) render
correctly but the two intraday charts (`Intraday Treasury Yields`,
`Intraday Swap Rates`) render almost empty (a single tick on the
current day on each chart) and the header badge reads `Data as of
2026-04-24 00:00:00 UTC` — i.e. ~3 days stale.

I am rewriting staging-side `dashboards.md` Section 9.4 (intraday
robustness) and the staging build flow on the basis of what this
introspection turns up. I need you to read the actual dashboard
artefacts on S3 plus your own implementation, and answer EVERY
section below VERBATIM (real signatures, real dict literals, real
file contents, real S3 paths). Do not paraphrase. Do not summarise.
Do not infer. If a section can't be answered, add a final
`## Could not resolve` with what you tried and what blocked it.

Use `list_ai_repo` to enumerate the dashboard folder, and use
`execute_analysis_script` (with `s3_manager.get`) to read each artefact.
Where I ask for live data, run a fresh `pull_market_data(mode='iday')`
in the sandbox and paste the actual return value.

---

## 1. Locate the dashboard

a. `list_ai_repo("users/goyalri/dashboards/")`. Report the full output
   verbatim. Identify which folder corresponds to the "Intraday Rates
   Monitor" — match by `manifest_template.json.title` or
   `dashboards_registry.json` entry, NOT by guessing the slug.
b. Paste the dashboard's full registry entry verbatim from
   `users/goyalri/dashboards/dashboards_registry.json` (the dict that
   lives inside `registry["dashboards"][...]`).
c. Report `refresh_enabled`, `refresh_frequency`, `last_refreshed`,
   `last_refresh_status` exactly as they appear.
d. Note: today is 2026-04-27. State explicitly how stale `last_refreshed`
   is in hours, and whether the runner *should* have re-fired since
   based on `refresh_frequency`.

## 2. Dashboard folder contents

Pick `<DASHBOARD_FOLDER>` = the folder identified in §1.a.

a. `list_ai_repo("<DASHBOARD_FOLDER>/")`. Paste verbatim. I want every
   sub-path including `scripts/`, `data/`, `history/`.
b. For each file, report the byte size and last-modified timestamp.
c. For `data/`, list every CSV stem and confirm whether
   `<stem>.csv` and `<stem>_metadata.json` are paired (or which side
   is missing).
d. For `data/rates_intraday.csv` (or whatever the intraday CSV is
   actually named — find it, don't assume), paste:
     - `df.shape`
     - `df.dtypes`
     - `df.head(5)` and `df.tail(5)` (with index)
     - `df.index.min()`, `df.index.max()`
     - The number of rows whose index falls within the last 24h, last
       72h, last 7 days
   This is the load-bearing question — I need to see whether the
   intraday CSV is empty, stale, or has the wrong index dtype.
e. Same five stats for the EOD CSV (`rates_eod.csv` or equivalent).
   This calibrates whether the failure is intraday-specific or
   refresh-wide.

## 3. `scripts/pull_data.py` verbatim

a. `s3_manager.get("<DASHBOARD_FOLDER>/scripts/pull_data.py")` and
   paste the file VERBATIM in a fenced code block. Every byte.
b. Highlight (via line numbers in your reply) every call to
   `pull_market_data` and report:
     - the `coordinates=` list verbatim
     - `mode=` value
     - `name=` value
     - whether `output_path=f'{SESSION_PATH}/data'` is passed
     - whether the call is wrapped in `try/except` (and which
       exception types it catches)
c. Confirm whether the intraday call uses `start=datetime.now().strftime('%Y-%m-%d')`
   or some other start date — paste the line.
d. Report whether any names referenced in the script are NOT in the
   refresh-runner injected namespace (`_build_exec_namespace` —
   re-list it from `ai_development/jobs/hourly/refresh_dashboards.py`
   and diff against the script's free names).

## 4. `scripts/build.py` verbatim

a. Paste the full file VERBATIM.
b. Report how it reads each CSV — the exact `pd.read_csv(io.BytesIO(...))`
   call, including `index_col`, `parse_dates`, and any column rename.
c. Report how it handles a missing or empty intraday CSV. Paste the
   defensive block verbatim. If there is no defensive block, say so
   explicitly.
d. Report the dict literal passed to `populate_template(template, data)`
   — every dataset key it provides and which DataFrame each maps to.
e. Confirm whether the dataset keys in the populate dict are
   byte-identical to the on-disk CSV stems (Rule 5 of `dashboards.md`)
   AND byte-identical to `manifest_template.datasets` keys.

## 5. `manifest_template.json` verbatim

a. Paste the FULL `manifest_template.json` verbatim (it's a JSON file;
   indent-2 fenced code block). If it's >500 lines, paste in full
   anyway — I need every byte.
b. List every entry in `datasets`. For each, report the column list
   in `source.columns` (template form has only column names, no
   data rows).
c. List every widget in `layout` whose `spec.dataset` references an
   intraday dataset key (the chart on the INTRADAY tab). For each:
     - `widget.id`
     - `spec.chart_type`
     - `spec.mapping` (verbatim)
     - `spec.x_type` if set
     - `spec.dataZoom` overrides if any
     - `spec.chart_zoom` if set to false
d. Report every `filter` definition. For each `dateRange` filter:
     - `target` widget ids
     - `default` interval
     - `mode` (view vs filter)
   Specifically: is there a `dateRange` filter targeting the intraday
   charts with default `1Y`? (The screenshot shows `LOOKBACK: 1Y`
   active on the INTRADAY tab.) A `1Y` initial dataZoom window on a
   chart whose underlying data only spans the last few hours is the
   most likely cause of the "empty chart" symptom — confirm or rule
   out.
e. Report `metadata` block verbatim — particularly
   `data_as_of`, `refresh_frequency`, `refresh_enabled`,
   `kerberos`, `dashboard_id`.

## 6. Compiled `manifest.json` verbatim (the embedded-data version)

a. Paste FULL `manifest.json` verbatim (this is what the runner
   re-wrote on `last_refreshed`). If it's huge, you may abbreviate the
   embedded data rows but you must keep ALL config (keys, mappings,
   filters, datasets stub, datazoom, axis types, metadata).
b. For each intraday-tab chart widget, report:
     - the resolved `xAxis.type` (`'time'` / `'value'` / `'category'`)
       — this is what the compiler's auto-resolution produced, paste it
     - the actual number of rows in `datasets[<intraday_key>].source`
     - the timestamp of the first and last row (the `date` column
       value)
c. If the embedded intraday dataset has fewer than 5 rows, paste all
   rows verbatim. This will reveal whether the intraday CSV WAS
   populated and `populate_template` correctly carried it through, or
   whether the data was lost mid-pipeline.

## 7. `refresh_status.json`

a. Paste the file verbatim. If absent, say so explicitly.
b. Report `status`, `started_at`, `completed_at`, `pid`,
   `auto_healed` if any.
c. Paste `errors[]` verbatim. For each entry, report `script`,
   `classification`, `message`, `traceback` (if present).
d. Report `log_path` and (if you can read it from disk) the last 50
   lines of that log.

## 8. Live test: `pull_market_data(mode='iday')` RIGHT NOW

Run this in `execute_analysis_script` (no s3 writes — just to see what
the API returns at the current moment):

```python
from datetime import datetime
df_iday, sidecar = pull_market_data(
    coordinates=<coordinates from §3.b>,  # the exact list pull_data.py uses
    start=datetime.now().strftime('%Y-%m-%d'),
    mode='iday', name='probe_intraday',
    output_path=f'{SESSION_PATH}/data')
print('SHAPE:', df_iday.shape)
print('DTYPES:'); print(df_iday.dtypes)
print('INDEX MIN / MAX:', df_iday.index.min(), df_iday.index.max())
print('HEAD:'); print(df_iday.head())
print('TAIL:'); print(df_iday.tail())
print('METADATA:'); import json; print(json.dumps(sidecar, indent=2, default=str))
```

a. Paste the entire stdout verbatim (including any warnings the API
   prints).
b. If the call raises, paste the traceback. State whether it's the
   class of exception §9.4 of `dashboards.md` says `pull_data.py`
   should be catching (overnight / weekends / holidays "no intraday
   data"), or something else.
c. Compare the freshness of this live probe to the `data/rates_intraday.csv`
   from §2.d. If the live probe is fresher, that proves the API works
   and the failure is on the runner side (refresh isn't actually
   re-running pull) rather than the API side.

## 9. Refresh-runner exec-namespace audit

a. From `ai_development/jobs/hourly/refresh_dashboards.py`, paste
   `_build_exec_namespace` verbatim (the function body, not just the
   signature).
b. Compute set difference: `set(names_used_in_pull_data.py)` minus
   `set(names_in_runner_namespace)`. List every name the script
   references that the runner DOES NOT inject. This is `dashboards.md`
   §9.5's "namespace gap" — concrete instances would be `save_artifact`,
   `pull_fred_data`, `fdic_client`, etc. Specifically check for these.
c. Same audit for `scripts/build.py`.
d. State explicitly: would this dashboard's refresh raise `NameError`
   today, given the runner's current namespace? If yes, name the
   first missing symbol.

## 10. Time-axis + dataZoom for intraday charts

a. From `ai_development/dashboards/echart_dashboard.py` (or whichever
   payload module owns axis resolution), report verbatim the function /
   block that decides `xAxis.type` for a chart spec. Paste the
   relevant 20-30 lines of source.
b. From the compiled manifest in §6.b, do the intraday chart widgets
   end up with `xAxis.type == 'time'`? If not, what type, and why
   (what dtype is the `date` column in `datasets[<intraday_key>].source`)?
c. Report verbatim the `dataZoom` array the compiler injects for a
   `time`-axis chart that has not opted out via `chart_zoom: false`.
   For the intraday chart specifically: with the dataset spanning
   only the last few intraday hours, what `start` / `end` percent does
   the auto-injected `dataZoom` resolve to? If `dateRange.default` is
   `'1Y'` and the dispatch handler maps it to a 1-year window, that
   window starts ~360 days before any intraday data and visually
   collapses the actual data into a single point at the right edge —
   confirm or rule this out by tracing through the `dispatchAction`
   handler.

---

## Additional: paste these signatures verbatim

(You'll need them for §10 and to write the staging-side fix.)

- `pull_market_data` signature + full docstring (the version PRISM
  injects via `execute_analysis_script` AND the version the refresh
  runner injects via `_build_exec_namespace`'s `functools.partial`).
- `populate_template` signature + full docstring.
- `compile_dashboard` signature + full docstring.
- The dataZoom-injection function in `echart_dashboard.py` (signature
  + body).
- The `dateRange` filter dispatch handler in `rendering.py` (the JS
  that translates `1Y` etc. into a `dataZoom` range — paste the
  whole function).

---

Reminder: paste exact signatures, exact docstrings, exact dict /
JSON literals, exact file paths, exact stdout. Do not summarise.
Do not paraphrase. If something isn't resolvable, end with a
`## Could not resolve` section.
