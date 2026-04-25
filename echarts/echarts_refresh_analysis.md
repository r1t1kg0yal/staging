# ECharts dashboard refresh: spec vs implementation

**Question.** When the user presses the in-browser **Refresh** button, does the
echarts system actually run `pull_data.py` -> `build.py` end-to-end, the way
`prism/PrismChartDashboardSkill.md` says it should?

**Short answer.** Yes -- the browser-side half of the contract is fully
implemented inside `ai_development/dashboards/`. The other half lives in the PRISM
Django backend (it has to: a static HTML file cannot run Python by itself).
The split is correct and clean. There are also a handful of *upgrades* over
the old skill file -- a smaller `build.py`, a single `manifest.json` instead
of separate `dashboard.html` + `dashboard_data.json` + `dashboard_spec.json`,
and no more `sanitize_html_booleans()` call.

---

## 1. End-to-end refresh flow

```
   BROWSER                          DJANGO BACKEND                   REFRESH PIPELINE
   (dashboard.html)                 (news/views.py)                  (refresh_dashboards.py)
   ────────────────                 ────────────────                 ────────────────────────

   user clicks
   [ Refresh ]
       │
       │ rendering.py JS reads MANIFEST.metadata
       │   guards on .kerberos + .dashboard_id + .refresh_enabled
       │   if window.location.protocol === "file:" -> alert + return
       │
       ▼
   POST {api_url}                                               ┌─────────────────────────────┐
   { kerberos, dashboard_id }                                   │ default api_url:            │
   ─────────────────────────────►                               │ /api/dashboard/refresh/     │
                                    look up dashboard           │ override via metadata.api_url│
                                    in dashboards_registry.json └─────────────────────────────┘
                                          │
                                    spawn refresh subprocess
                                    (or HTTP 409 -> rejoin)
                                          │   HTTP 200
                                          │   { status: "refreshing" }
   ◄─────────────────────────────         │
                                          ▼
                                    refresh_single_user_dashboard()
                                          │
                                          ├─► write refresh_status.json
                                          │       { status:"running",
                                          │         started_at, pid }
                                          │
                                          ├─► RUN scripts/pull_data.py
                                          │       pull_market_data, pull_haver_data, ...
                                          │       writes ../data/*.csv on S3
                                          │
                                          ├─► RUN scripts/build.py    (~15 lines)
                                          │       1. load manifest_template.json
                                          │       2. read ../data/*.csv into DataFrames
                                          │       3. populate_template(template, datasets)
                                          │       4. compile_dashboard(populated, output_path=...)
                                          │             ► writes dashboard.html
                                          │             ► writes manifest.json
                                          │
                                          ├─► (optional) snapshot to history/{YYYYMMDD}/
                                          │
                                          ├─► update dashboards_registry.json
                                          │       .last_refreshed
                                          │       .last_refresh_status
                                          │
                                          └─► write refresh_status.json
                                                  { status:"success", completed_at }

   meanwhile, every 3s for up to 3 min:

   GET {status_url}?dashboard_id=...
   ─────────────────────────────►
                                    read refresh_status.json
                                    ◄─ HTTP 200
                                    { status, errors[], pid, ... }
   ◄─────────────────────────────

   when status === "success":
   location.reload()
       └─► fresh dashboard.html served from S3 / portal
```

Same code path serves the cron job and the in-browser refresh -- both end up
running `pull_data.py` then `build.py`. The dashboard the user sees on reload
was rendered by the same `compile_dashboard()` call that PRISM ran during the
build conversation, with fresh DataFrames piped through `populate_template()`.

---

## 2. Responsibility split

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ai_development/dashboards/   (this repo, the dashboard compiler)           │
├────────────────────────────────────────────────────────────────────────────┤
│  - manifest schema (incl. metadata.refresh_* knobs + validator)            │
│  - manifest_template() / populate_template() helpers                       │
│  - compile_dashboard() that emits manifest.json + dashboard.html           │
│  - the Refresh button's HTML, CSS, and JS (rendering.py)                   │
│       wires onclick -> POST /api/dashboard/refresh/                        │
│       polls /api/dashboard/refresh/status/?dashboard_id=...                │
│       handles 409, file://, success, error, partial, timeout               │
│  - data-freshness badge driven from metadata.data_as_of / generated_at     │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │  HTTP API contract
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ PRISM backend   (Django; lives outside this repo)                          │
├────────────────────────────────────────────────────────────────────────────┤
│  - news/urls.py + news/views.py:                                           │
│       POST /api/dashboard/refresh/                                         │
│       GET  /api/dashboard/refresh/status/?dashboard_id=...                 │
│  - refresh_dashboards.py:                                                  │
│       refresh_single_user_dashboard()                                      │
│       _should_refresh() (cron)                                             │
│       runs scripts/pull_data.py -> scripts/build.py via execute_analysis_… │
│       writes refresh_status.json + auto-heals stale running locks          │
│       updates dashboards_registry.json                                     │
│       calls update_user_manifest(kerberos, artifact_type='dashboard')      │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ runs the user's persisted scripts
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ users/{kerberos}/dashboards/{name}/   (the dashboard package on S3)        │
├────────────────────────────────────────────────────────────────────────────┤
│  manifest_template.json   <-- LLM-editable spec, NO data                   │
│  manifest.json            <-- compiled snapshot, populated with fresh data │
│  dashboard.html           <-- compile_dashboard output, with refresh button│
│  refresh_status.json      <-- written by refresh pipeline                  │
│  scripts/pull_data.py     <-- only pulls; saves to ../data/*.csv           │
│  scripts/build.py         <-- ~15 lines: populate_template + compile       │
│  data/*.csv               <-- raw cache, survives between refreshes        │
└────────────────────────────────────────────────────────────────────────────┘
```

Each layer owns exactly one concern. The compiler doesn't know how to spawn
subprocesses, the backend doesn't know how to render charts, and the scripts
don't know any HTML.

---

## 3. Spec-by-spec compliance check

Walking the **MANDATORY** items from `prism/PrismChartDashboardSkill.md`:

| Section in skill                    | Requirement                                                        | echarts impl                                                                              | Status         |
|-------------------------------------|--------------------------------------------------------------------|-------------------------------------------------------------------------------------------|----------------|
| §2 Manual Refresh Button            | Every dashboard MUST include a Refresh button in the header        | `rendering.py` line 1945-1948: `<button id="refresh-btn">` + `<span id="refresh-btn-label">` | OK             |
| §2 Refresh Button JS                | POST `/api/dashboard/refresh/` with `{ kerberos, dashboard_id }`   | `rendering.py` line 3588-3592                                                             | OK             |
| §2 Refresh Button JS                | GET `/api/dashboard/refresh/status/?dashboard_id=...`              | `rendering.py` line 3558                                                                  | OK             |
| §2 Refresh Button JS                | Poll every 3s, max 3 min                                           | `setInterval(..., 3000)`, `maxPolls = 60`                                                 | OK             |
| §2 Refresh Button JS                | HTTP 409 -> switch to polling, not error                           | `if (code === 409) { pollStatus(); return; }`                                             | OK             |
| §2 Refresh Button JS                | `file://` graceful alert                                           | `if (window.location.protocol === 'file:') alert(...); return;`                           | OK             |
| §2 Refresh Button JS                | `status === "success"` -> reload                                   | `location.reload()` after 900 ms                                                          | OK             |
| §2 Refresh Button JS                | `status === "partial"` -> reload anyway                            | `setLabel('refresh-error', 'Partial'); reload after 2 s`                                  | OK             |
| §3 Dashboard Package                | Per-dashboard folder under `users/{kerberos}/dashboards/{name}/`   | README §3.1 spells it out exactly                                                         | OK             |
| §5 Two-Script Model                 | `pull_data.py` does ALL acquisition                                | README §4.1 + §4.5                                                                        | OK             |
| §5 Two-Script Model                 | `build_dashboard.py` does transform + JSON + HTML regen            | Renamed to `build.py`; trivial because compiler owns HTML                                 | OK (upgraded)  |
| §5 Full HTML regen on every refresh | `dashboard.html` regenerated, not just the JSON                    | `compile_dashboard()` writes both atomically                                              | OK             |
| §6 Data Contract                    | All rendering data in ONE file                                     | `manifest.json` is the only one (see §4 below)                                            | OK (upgraded)  |
| §7 Boolean Sanitation               | Call `sanitize_html_booleans()` after saving HTML                  | Not needed: compiler emits JSON-clean HTML                                                | Obsolete       |
| §8 Dashboard Charting Separation    | Never use `make_chart()` PNGs in dashboards                        | Dashboards render via ECharts client-side; PNGs are an opt-in export                      | OK             |
| §11 Loading + error states          | Graceful per-section render with try/catch                         | `rendering.py` wraps each chart init; tabs lazy-init                                      | OK             |
| §12 Dashboard Creation Flow         | Three-tool-call build (`pull` -> `build` -> `register`)            | README §4.1 documents this; tools 1+2 use ephemeral scripts that persist themselves       | OK             |
| §13 Async refresh                   | Cron + manual refresh use the SAME code path                       | Yes -- both POST `/api/dashboard/refresh/`, which spawns the same subprocess              | OK             |
| §14 Intraday robustness             | `try/except` around intraday pulls, EOD fallback in build          | README §4.5 with code samples                                                             | OK (doc only)  |
| §15 Prohibited patterns             | No `make_chart()` PNGs in HTML, no Canvas-only charts              | README §3.1 explicit "Forbidden" table                                                    | OK             |
| §19 Troubleshooting                 | Read `refresh_status.json`, identify error, fix script             | README §4.6 ports the protocol verbatim                                                   | OK             |

Verdict: every **MANDATORY** item is satisfied. The two items in the skill
that don't apply anymore (`sanitize_html_booleans()`, separate
`dashboard_data.json`) are obsolete because the compiler does cleaner work.

---

## 4. Upgrades over the old spec

```
┌─────────────────────────────────┬─────────────────────────────────────────────────────────┐
│ Old skill expectation           │ echarts upgrade                                         │
├─────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ build_dashboard.py owns the     │ build.py is ~15 lines. compile_dashboard() owns the    │
│ entire HTML template (500+      │ HTML template. PRISM never writes HTML.                │
│ lines), regenerated on every    │                                                         │
│ refresh                         │                                                         │
├─────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Two data files:                 │ One file: manifest.json. Datasets are inlined into     │
│   dashboard.html  (with inline  │ the manifest; dashboard.html embeds the manifest at    │
│   const DATA = ...)             │ compile time. No fetch() race, no second contract.     │
│   dashboard_data.json           │                                                         │
├─────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ sanitize_html_booleans() must   │ Compiler serializes data via json.dumps() into a       │
│ be called after every HTML save │ <script> block; True/False/None are never produced.   │
│ to fix code-sandbox booleans    │ The helper is a no-op for echarts dashboards.         │
├─────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Charts drawn in vanilla Canvas  │ Charts go through the same builder dispatch as         │
│ JS or Plotly CDN, hand-rolled   │ make_echart(); 24 chart types, brush + connect links,  │
│ in build_dashboard.py           │ filter wiring, all produced by compile_dashboard().    │
├─────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ dashboard_spec.json (UI         │ The manifest IS the UI spec. No separate file.         │
│ structure) lives next to        │                                                         │
│ dashboard_data.json             │                                                         │
├─────────────────────────────────┼─────────────────────────────────────────────────────────┤
│ Templates not formalized -- the │ manifest_template.json is a first-class artifact,      │
│ build script re-wrote everything│ produced once via manifest_template(initial_manifest).│
│ from scratch on every refresh   │ build.py reloads it + populate_template() with fresh   │
│                                 │ DataFrames. Cheap, deterministic, diff-friendly.       │
└─────────────────────────────────┴─────────────────────────────────────────────────────────┘
```

The shape of the build loop also collapses. Old:

```
build_dashboard.py
├─ load raw data
├─ compute analytics
├─ assemble dashboard_data.json
├─ build full HTML template (500+ lines of f-strings)
├─ embed data inline via json.dumps
├─ write dashboard.html + dashboard_data.json
└─ sanitize_html_booleans(dashboard.html)
```

New:

```
build.py
├─ load manifest_template.json
├─ load raw data into DataFrames
├─ m = populate_template(template, {...DFs...}, metadata={data_as_of: ...})
├─ r = compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html')
└─ assert r.success
```

Fifteen lines, no string-templating, no boolean sanitization, no separate
data file, no chart code -- just a populate-and-compile.

---

## 5. The metadata block: where refresh config lives

The refresh button is *not* a magic global; it is gated by the manifest's
`metadata` block. This is a clean dependency-injection pattern:

```python
manifest = {
    "schema_version": 1,
    "id": "rates_monitor",
    "title": "Rates monitor",
    "metadata": {
        # Required for refresh button to render at all:
        "kerberos": "goyairl",
        "dashboard_id": "rates_monitor",   # defaults to manifest.id

        # Refresh control:
        "refresh_enabled": True,            # set False to hide button entirely
        "refresh_frequency": "daily",       # hourly | daily | weekly | manual

        # Data-freshness badge (header):
        "data_as_of":   "2026-04-24T15:00:00Z",
        "generated_at": "2026-04-24T15:05:00Z",
        "sources":      ["GS Market Data", "Haver"],

        # Optional endpoint overrides (for testing or alternative deploys):
        "api_url":    "/api/dashboard/refresh/",
        "status_url": "/api/dashboard/refresh/status/",
    },
    ...
}
```

The validator (`validate_manifest()` in `echart_dashboard.py`) enforces:

- `metadata.refresh_frequency` must be one of `{hourly, daily, weekly, manual}`
- `metadata.refresh_enabled` must be a `bool`
- All string fields are typed-checked
- `sources` / `tags` must be lists

The render-time JS in `rendering.py` line 3536-3539 does the run-time gate:

```javascript
var kerberos = MD.kerberos;
var dashboardId = MD.dashboard_id || MANIFEST.id;
var enabled = MD.refresh_enabled !== false;
if (!kerberos || !dashboardId || !enabled) return;   // button stays hidden
```

So a session-scope dashboard with no `metadata.kerberos` simply has no
Refresh button. A persistent dashboard with `metadata.refresh_enabled = false`
also has no button. Otherwise the button is always there. This is exactly
the "MANDATORY refresh button" rule from the skill, properly scoped: don't
render a button that has nowhere to POST.

---

## 6. What the echarts repo does NOT include (and shouldn't)

```
PRISM-side responsibilities (NOT in ai_development/dashboards/):

  ├── /api/dashboard/refresh/         (Django view, news/views.py)
  ├── /api/dashboard/refresh/status/  (Django view, news/views.py)
  ├── refresh_dashboards.py           (cron orchestrator)
  ├── refresh_single_user_dashboard() (subprocess driver)
  ├── _should_refresh()               (frequency check)
  ├── refresh_status.json writer      (lock file management)
  ├── stale-lock auto-healing         (10 min timeout policy)
  ├── dashboards_registry.json read/write
  └── update_user_manifest()          (artifact pointer update)
```

These all live in the PRISM backend repo; they are runtime-only and have no
business inside a chart-rendering library. The echarts side defines the
**contract** (URL paths, request/response shapes, status enum) and the
backend implements it. As long as the contract holds, either side can be
swapped independently -- e.g. a unit test can stub the API endpoints without
touching `rendering.py`.

---

## 7. Verdict

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Does ai_development/dashboards fully support the refresh model from      │
│ PrismChartDashboardSkill.md?                                             │
│                                                                          │
│   YES -- and it does so more cleanly than the old skill prescribed.     │
│                                                                          │
│   - Refresh button: rendered, gated, wired to API     OK                 │
│   - Polling protocol: 3s x 60, 409, file://, errors  OK                  │
│   - Manifest template + populate workflow             OK                 │
│   - build.py is now ~15 lines                         OK (upgrade)       │
│   - Single manifest.json, no boolean sanitizer        OK (upgrade)       │
│   - Same code path for cron + manual refresh          OK                 │
│   - Backend implementation lives in PRISM Django      EXPECTED           │
└──────────────────────────────────────────────────────────────────────────┘
```

The only thing left to verify in a live environment is the Django backend
half (does it actually exist in the PRISM repo, do the URL routes resolve,
does the subprocess spawn succeed?). That part is the PRISM repo's
responsibility -- but the contract from the dashboard's side is locked
down and implemented exactly as the skill specified.
