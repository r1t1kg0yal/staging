# PRISM dashboard build — eval prompt set

End-to-end checklist for putting PRISM to work building dashboards and grading the result. Each prompt is paste-and-go into PRISM. After PRISM finishes, walk the matching inspection checklist below.

The four chrome buttons (Methodology / Refresh / Share / Download dropdown) are auto-injected by the rendering shell — PRISM does NOT add them to the JSON. The validator now hard-rejects manifests that do not set `metadata.kerberos`, `metadata.dashboard_id`, or `metadata.methodology`. So a "missing button" is no longer a chrome bug — it's metadata PRISM forgot, and validation should have caught it. These tests are designed to surface any place that contract is still leaky.

---

## A. Pre-flight

Before running any prompt:

- [ ] You are signed in via GSSSO (DevTools → Cookies shows a `GSSSO` value)
- [ ] `/profile/dashboards/` loads and lists existing dashboards
- [ ] `/dashboards/` loads (Franchise + Community + Observatory sections render)
- [ ] DevTools open, Console tab visible — you'll watch for `[prism]` warnings during inspection

Pick a kerberos for the prompts below. Replace `{KERBEROS}` everywhere it appears, or rely on PRISM's session identity.

---

## B. Build prompts

Each numbered prompt is a single PRISM message. Paste exactly. After PRISM reports success, jump to **C. Post-build inspection** for that prompt.

### B1. Simplest possible — single chart, daily

**Purpose:** smoke-test the happy path. Tests build mechanics, all four chrome buttons, refresh button works, methodology has content.

```
Build me a daily personal dashboard called "us_10y_pulse" tracking the US 10Y
Treasury yield over the last 5 years. One line chart, full back-history, daily
frequency. Refresh daily. Surface the dashboard for me when done.
```

**What to check:**

- [ ] PRISM did NOT inline `<script>` / HTML / CSS in any `.py` file
- [ ] PRISM persisted scripts to S3 BEFORE running them (`s3_manager.put` then `s3_manager.get` then `exec`)
- [ ] PRISM hand-off message leads with the **portal URL** (`/profile/dashboards/us_10y_pulse/`), not the S3 path of `dashboard.html`
- [ ] All four chrome buttons render (Methodology, Refresh, Share, Download v)
- [ ] DevTools console shows NO `[prism] Refresh button hidden:` warning
- [ ] Click Methodology → markdown popup with non-empty body
- [ ] Click Refresh → modal pops with running → success transition
- [ ] Click Download → dropdown opens with Panel + Charts (Excel item NOT shown — no table widget)

### B2. Multi-chart with KPIs and table — exercises Excel item

**Purpose:** force a `widget: table` so the Download dropdown surfaces the Excel item. Also tests KPI tile data flow.

```
Build me a daily personal dashboard called "rates_dashboard" with:
- two KPI tiles (US 2Y current + delta vs prior day, US 10Y current + delta)
- a multi-line chart of the 2Y / 5Y / 10Y / 30Y curve over 5 years
- a table of the latest 20 daily values across those four tenors

Refresh daily. Surface the portal URL when done.
```

**What to check:**

- [ ] Two KPI tiles render with current value + delta + sparkline
- [ ] Multi-line chart renders 4 series, each humanized in legend ("US 2Y", not "us_2y")
- [ ] Table widget renders with sort + search + per-column formatting
- [ ] Click Download → dropdown shows Panel + Charts + **Excel** (because of the table)
- [ ] Excel download produces a valid `.xlsx` with one sheet named after the table widget
- [ ] All other Methodology / Refresh / Share button checks from B1 still pass

### B3. Tabbed dashboard — exercises tabs + cross-tab Excel

**Purpose:** test the tabs layout, ensure chrome behaves identically across tab switches.

```
Build me a daily personal dashboard called "rates_fx_overview" with two tabs:

Tab 1 "Rates": multi-line chart of US 2s10s and 5s30s spreads (5Y daily), KPIs
for each spread.

Tab 2 "FX": multi-line chart of EUR/USD and USD/JPY spot (5Y daily), KPIs for
each pair.

Refresh daily. Surface the portal URL when done.
```

**What to check:**

- [ ] Tab bar renders with both tabs
- [ ] Switching tabs preserves chrome state (Refresh / Share / Download still in DOM)
- [ ] Click Refresh from Tab 2 — modal still works, polls correctly
- [ ] Excel download captures BOTH KPI tabs' source data correctly (Excel scans entire dashboard, not just active tab)

### B4. Dashboard with methodology depth

**Purpose:** test that PRISM authors a non-trivial methodology block (not a placeholder).

```
Build me a daily personal dashboard called "fed_pricing" tracking what the SOFR
futures market is pricing for the next 4 FOMC meetings. Show implied policy
rate path as a step chart. Methodology should explain how the implied path is
derived from contract prices in detail.
```

**What to check:**

- [ ] Methodology popup body is **substantive** — at least 3 paragraphs, names the data source, names the math, distinguishes between contract and implied rate. Not a one-line placeholder
- [ ] Methodology renders markdown (headings, bullets, bold, code) cleanly
- [ ] If markdown formatting looks wrong, that's a renderer bug — file separately

### B5. Force a real-data refusal

**Purpose:** verify PRISM doesn't make up data. From dashboards.md Rule 1.

```
Build me a daily personal dashboard called "shadow_funding" tracking shadow
funding rates across 12 emerging-market currencies for the last 5 years. Use
GS market data.
```

**Expected outcome:** PRISM should either (a) confirm it has real coordinates for these series and proceed, OR (b) refuse to build, citing that no such bulk data source exists, OR (c) build with a narrower scope and explain what was substituted. PRISM should NOT fabricate 12 EM funding rate series with synthetic numbers.

**What to check:**

- [ ] PRISM did not call `np.random` / `np.linspace` to fill data
- [ ] If PRISM proceeded, every dataset has real `field_provenance` pointing at a real source
- [ ] If PRISM refused / scoped down, the explanation is clear and surfaced before any code runs

---

## C. Post-build inspection (run for EVERY prompt B1–B4)

### C1. Chrome buttons rendered

Open the dashboard, look at the top-right of the header:

```
[Methodology]  [Refresh]  [Share]  [Download v]  [theme]  | Data as of <ts>
```

Pass = all four buttons present and clickable. Fail = any missing.

### C2. DevTools console

Open DevTools → Console. Reload the page. **No `[prism]` warnings**.

If you see `[prism] Refresh button hidden: metadata.kerberos`, that means the validator was bypassed (legacy dashboard or PRISM somehow shipped a manifest with no kerberos). Note which field is named in the warning.

### C3. Refresh round-trip

1. Click **Refresh** in the chrome
2. Modal pops (status running → success or running → error)
3. Page text "Last refreshed" timestamp updates
4. Reload — `Data as of <ts>` reflects the new time

If refresh fails, the modal should show the **structured failure modal** with: failure-kind pill, kerberos / dashboard_id / S3 folder, errors[] cards, and a "Copy markdown for PRISM" button. Copy that into PRISM and verify PRISM can repair without further context-stitching.

### C4. Share round-trip

1. Click **Share** — label flips to "Sharing"
2. Visit `/dashboards/` in a new tab
3. **Confirm** the dashboard appears in the **Community Dashboards** section, attributed to your kerberos
4. Open `/community/dashboards/{KERBEROS}/{dashboard_id}/` from another browser profile (or DevTools "view as different user" trick) — page should load
5. On the community view, the Refresh and Share buttons should be **hidden** (`PRISM_VIEWER !== metadata.kerberos`)
6. Return to your own view, click **Sharing** → confirm dialog → click confirm → label flips back to "Share"
7. Reload `/dashboards/` — community section no longer shows the entry

### C5. Methodology popup

1. Click **Methodology**
2. Popup opens with the markdown rendered (headings, bullets, bold)
3. Close popup with X or Esc
4. Body should match what PRISM authored in `metadata.methodology`

### C6. Download dropdown

1. Click **Download v**
2. Dropdown opens with **Panel**, **Charts**, **Excel** (Excel only when the dashboard has any `widget: table`)
3. Click outside the menu — closes
4. Re-open, click Panel — full-page PNG downloads
5. Re-open, click Charts — N PNGs download (one per `widget: chart`)
6. (B2/B3 only) Re-open, click Excel — `.xlsx` downloads with one sheet per table

### C7. Portal URL hand-off

In PRISM's chat output for the build, the **first** thing surfaced should be the portal URL (`http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{id}/`), NOT the S3 path of `dashboard.html`. PRISM should only mention the HTML path if you explicitly ask for it.

This is the most-checked thing per the user contract. If PRISM leads with "Your dashboard HTML is at users/.../dashboard.html" instead of the portal URL, fail.

---

## D. Cross-cutting tests

### D1. Listing-page sanity

Visit `/dashboards/`:

- [ ] Franchise section renders (3 hardcoded entries, possibly access-filtered)
- [ ] Community section renders (every shared dashboard from any kerberos that has flipped `shared: true`)
- [ ] Observatory section renders (5 system dashboards)
- [ ] Newly-built dashboard from B1–B4 appears in `/profile/dashboards/` (NOT in `/dashboards/` until shared)

### D2. Hourly refresh tick

(Optional, requires waiting for the hourly cron.) After a build:

1. Wait until the next hourly tick
2. `s3_manager.get(f'users/{KERBEROS}/dashboards/{id}/refresh_status.json')` shows recent `success` or `error`
3. Reload `/profile/dashboards/{id}/` — `Data as of <ts>` updates
4. Registry entry's `last_refreshed` field updates

### D3. Reserved-id collision (validator hardening)

Ask PRISM to do something that would clobber chrome:

```
Now add a Refresh button to that dashboard's header_actions.
```

**Expected:** PRISM refuses, citing the reserved-id rule. The chrome's Refresh button is non-author-able. PRISM may suggest renaming the custom button to something else (e.g. "Refresh data" with id `data-refresh-btn`).

### D4. Methodology required (validator hardening)

Ask PRISM to skip methodology:

```
Now build me a daily dashboard called "scratch_test" with one line chart of US
10Y and don't worry about the methodology -- I just want to see the chart.
```

**Expected:** PRISM either (a) refuses and explains that `metadata.methodology` is mandatory in the validator, OR (b) auto-populates a sensible methodology and notes that. PRISM should NOT submit the build only to have `compile_dashboard` reject it.

### D5. Anti-leak — HTML over portal

```
Just give me the raw HTML for that dashboard, I'll host it myself.
```

**Expected:** PRISM may surface the S3 path now, or it may push back ("the portal URL is the canonical surface; the raw HTML loses the JS-globals injection that drives the Refresh / Share buttons"). Either is OK as long as PRISM did not lead with the HTML in earlier responses.

---

## E. Failure-mode probes (regression tests for the contract)

### E1. Stale legacy dashboard

If you have a dashboard that was built BEFORE the validator update, it likely lacks `metadata.kerberos`. Visit `/profile/dashboards/{stale_id}/`:

- [ ] DevTools console shows `[prism] Refresh button hidden: metadata.kerberos`
- [ ] Refresh button is NOT in the DOM (the JS gate fired)
- [ ] Methodology / Share are also gated similarly

Ask PRISM to fix:

```
The dashboard at /profile/dashboards/{stale_id}/ has no Refresh button. Fix it.
```

PRISM should diagnose missing metadata, repopulate via Tool 2, and re-deliver the portal URL.

### E2. Manifest-only mutation (no rebuild)

```
Just edit metadata.kerberos directly on the existing manifest.json on S3 and
re-upload -- don't re-run the scripts.
```

**Expected:** PRISM should refuse this path or strongly warn. The build flow IS the refresh path (Rule 3) — script-less surgical edits leave the dashboard in a state where the next hourly refresh re-runs the old `build.py` and loses the manual edit.

### E3. Header action label collision (not blocked, but noteworthy)

```
Add a header_actions button labeled "Refresh data" with id "data-refresh-btn"
that links to my analytics page.
```

**Expected:** PRISM proceeds. `data-refresh-btn` is not a reserved id; the label "Refresh data" is allowed (the validator only enforces id collisions). The custom button should appear to the LEFT of the chrome.

---

## F. Grading rubric

For each prompt B1–B5, score across these axes:

| Axis | 0 | 1 | 2 |
|------|---|---|---|
| Build mechanics (3-tool flow, S3 layout, scripts on disk, Rule 5 output_path) | violated | partial | clean |
| Real data | invented values | borderline (one source unverified) | every series traces to real source |
| Chrome buttons all present | none / missing | refresh OR share missing | all four present, no console.warn |
| Methodology depth | placeholder | one paragraph | substantive markdown |
| Hand-off mentions portal URL first | HTML path led | mentioned both | portal URL first, HTML on request |
| Refresh round-trip works | fails / errors | partial | success in modal, status updates |
| Share round-trip works | broken | partial | full flow visible cross-user |
| Reserved-id / validator pushback | bypassed | warned but proceeded | refused with citation to dashboards.md |

A prompt counts as **passing** if every axis ≥ 1, and the build axis is at 2.

A regression has occurred if any axis previously at 2 drops to 1 or 0 in a re-run.

---

## G. What to file as a bug vs. what to file as a PRISM training gap

- **Bug** in `GS/viz/echarts/echarts-payload/`: chrome button code-path failure, validator missing a check, Excel export mangling a sheet name, dropdown not closing on click-outside. Open issue against the staging repo.
- **Bug** in `mysite/news/views.py`: `/community/dashboards/<author>/<id>/` 404s when it shouldn't, refresh API ignores allowlist, status API leaks. File against PRISM repo.
- **PRISM training gap**: PRISM made up data, PRISM led the hand-off with the HTML path, PRISM tried to add Refresh to header_actions, PRISM forgot methodology and didn't push back. Update `dashboards.md` (concise additions) so the next session inherits the fix; reproduce the prompt the next day to verify behaviour persists.
