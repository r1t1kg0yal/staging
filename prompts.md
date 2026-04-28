# Context-extraction: dashboard validation bypass investigation
I'm hitting `(no data)` placeholder cards on dashboards I built recently with these
exact subtexts (rendered inside the chart card on `dashboard.html`):
  1. `(no data) bar: mapping.x='outcome' is not a column in dataset 'next_meeting_probs'`
  2. `(no data) bar: mapping.x='meeeting' is not a column in dataset 'fomc_jumps_eod'`
  3. `(no data) bullet: mapping.x_low='low_1y' is not a column in dataset 'rv_screen'`
That subtext is the diagnostic message from `chart_data_diagnostics`. It means the
chart spec references a column that does not exist in the dataset. With
`compile_dashboard(strict=True)` (the default per `dashboards.md`) this should
hard-fail at compile time, not render a placeholder. The fact that I am SEEING the
placeholder card means the build path is bypassing the strict gate.
Investigate which of my dashboards are affected and tell me, verbatim, what the
build flow actually does.
This is a context-extraction prompt. Do not run pulls. Do not call
`compile_dashboard`. Do not modify anything. Read-only S3 inspection only via
`execute_analysis_script` + `s3_manager.get`. Reply with verbatim file contents
and exact S3 paths.
KERBEROS = `goyalri`        (replace if different)
## Phase A: enumerate all dashboards
Read `users/{KERBEROS}/dashboards/dashboards_registry.json`. For each entry in
`registry["dashboards"]`, print one row:
| id | last_refreshed | last_refresh_status | refresh_enabled | refresh_frequency |

Plus call out any dashboard whose `id` matches or seems to host one of the three
dataset names above (`next_meeting_probs`, `fomc_jumps_eod`, `rv_screen`).
## Phase B: locate the implicated dashboards
For each dashboard in the registry, fetch:
  - `users/{KERBEROS}/dashboards/{id}/manifest.json`
Walk `manifest.datasets` keys and `manifest.layout` (or `manifest.layout.tabs[].rows`)
chart `spec.dataset` references. Identify every dashboard whose manifest
references ANY of: `next_meeting_probs`, `fomc_jumps_eod`, `rv_screen`.
For each implicated dashboard, for the matching widget, print:
dashboard_id = ... widget id = ... widget chart_type = ... spec.dataset = ... spec.mapping = {... verbatim from manifest ...}

## Phase C: dump scripts/build.py verbatim for each implicated dashboard
For each implicated dashboard, fetch:
  - `users/{KERBEROS}/dashboards/{id}/scripts/build.py`
  - `users/{KERBEROS}/dashboards/{id}/scripts/pull_data.py`
Print the full contents of each, verbatim, in a fenced code block. Do not
paraphrase. Do not redact.
After printing each `build.py`, answer these four yes/no/quote questions:
  1. Does it call `compile_dashboard(...)` ? Quote the exact call line(s).
  2. Is `strict=` passed explicitly in that call ? If yes, quote the value.
     If no, note that the default (`True`) applies.
  3. Is the `compile_dashboard(...)` call wrapped in a `try` / `except` block ?
     Quote it if so.
  4. Does it use `Dashboard(...)` constructor + `.build()` instead of the
     dict-based `compile_dashboard()` flow ? Quote it if so.
  5. Does it check `r.success` (or equivalent) before writing
     `dashboard.html` / `manifest.json` to S3 ? Quote it.
## Phase D: column-vs-mapping reality check
For each implicated dashboard, list the files under
`users/{KERBEROS}/dashboards/{id}/data/` (use `s3_manager.list_objects` or the
equivalent). For each CSV file present, read it back and print:
file = data/.csv shape = (rows, cols) columns = [...] dtypes = {...}

Then for every chart `spec` in the manifest whose `spec.dataset` matches one of
those CSV stems, list:
mapping_key → mapping_value (column name) → IN dataset? (yes / NO)

so we can see exactly which `mapping.x` / `mapping.y` / `mapping.x_low` /
`mapping.color` etc. references are pointing at columns that don't exist in
the on-disk data.
## Phase E: refresh_status.json snapshot
For each implicated dashboard, fetch:
  - `users/{KERBEROS}/dashboards/{id}/refresh_status.json`
Print verbatim. We're looking for `status`, `errors[]`, `auto_healed`,
`completed_at`.
## Phase F: summary
Single table with one row per implicated dashboard:
| id | strict_mode | wraps_compile_in_try | uses_Dashboard_class | checks_r.success | last_refresh_status | broken_charts |

Where `broken_charts` is the list of widget ids whose `mapping` references a
column that's not in the on-disk CSV (from Phase D).
Do not propose fixes. Do not edit anything. Just report.
ASCII summary of what this gathers and why it's enough to lock down the cause:

                EVIDENCE             →    DECISIVE FOR
                ────────                  ─────────────
  Phase A (registry)               →   which dashboards exist + last status
  Phase B (manifest)               →   which dashboards host the failing specs
  Phase C (build.py verbatim)      →   strict=False vs try/except vs Dashboard()
                                       ── this single phase tells us which of the
                                       three deviations is happening
  Phase D (CSV columns)            →   confirms typo vs schema-drift root cause
                                       (e.g. column was renamed; manifest stale)
  Phase E (refresh_status.json)    →   confirms whether last refresh "succeeded"
                                       even though charts are broken
  Phase F (summary)                →   one-table verdict per dashboard
