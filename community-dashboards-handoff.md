# Handoff: Community Dashboards -- design session

You are picking up a design effort that already has substantial
groundwork. Your job in this session is to **lock in the end-to-end
design** for renaming the existing "Macro Dashboards" portal section
to **Example Dashboards**, adding a new **Community Dashboards**
section that any user can publish their own dashboards to (with
attribution and author-only edit/refresh), and producing the
staging-side payload changes that go with it. PRISM-side Django edits
(`views.py` / `urls.py` / templates) are the user's hand and not part
of this session, but you will produce a clean spec for them.

The ground truth is fully audited and documented in `prism/`. Read it
first; do not guess. The audit trail (4 PRISM context-extraction
prompts and their replies) is parked at
`staging/community-dashboards-prompts.md` for reference.

---

## 1. Mandatory reading (in this order)

| # | File | Why |
|---|------|-----|
| 1 | `.cursor/rules/prism.mdc` (always-applied) | The orientation discipline. Re-list `prism/` and pick relevant files; do not trust memory. |
| 2 | `.cursor/rules/viz-platforms.mdc` (always-applied) | The drag-and-drop contract for `GS/viz/echarts/echarts-payload/`. Anything we change in `rendering.py` or `dashboards.md` ships byte-identical to PRISM. |
| 3 | `prism/README.md` | Catalog + routing. |
| 4 | `prism/dashboards-portal.md` | The portal page itself: listing views, click-through, three dashboard categories, identity model, access control, cross-user visibility status. **THIS IS THE PRIMARY DOC FOR THIS SESSION.** |
| 5 | `prism/dashboard-refresh.md` | The refresh pipeline. §2.4 shows the `refresh_dashboard_api` body verbatim including the auth gap (Section 4 below). §5 shows discovery + scheduling. §6 has the registry schema. |
| 6 | `GS/viz/echarts/echarts-payload/dashboards.md` | Dashboard authoring (manifest, `compile_dashboard`, three-tool build flow). §2.3 metadata block + §9.1 Tool 3 are where PRISM-build-time awareness of the new `shared` / `example` fields needs to land. |
| 7 | `prism/architecture.md` §7 (Observatory), §10 (User system) | The Observatory's role + user-manifest schema + pointer dispatch table. |
| 8 | `staging/community-dashboards-prompts.md` | The four context-extraction prompts that produced the verbatim source quoted across `prism/`. Useful when you want to verify a claim against the underlying introspection. |

`prism/_changelog.md` has a 2026-04-27 entry summarising the audit. If
you're pressed for time, that entry is a fast index into what changed
and where.

---

## 2. The end-state we're building

```
+--------------------------------------------------------------------+
|  /dashboards/    (consume / browse)                                |
|  +--------------------------------------------------------------+  |
|  |  FRANCHISE       3 hardcoded, API-served, access_group       |  |
|  |                  gated. UNTOUCHED by this work.              |  |
|  +--------------------------------------------------------------+  |
|  |  EXAMPLE         5 curated. (Renamed from "Macro".)          |  |
|  |                  Stored uniformly with user dashboards under |  |
|  |                  users/_prism_examples/dashboards/{id}/      |  |
|  |                  with shared=true + example=true.            |  |
|  +--------------------------------------------------------------+  |
|  |  COMMUNITY       N user-published dashboards. Author opts in |  |
|  |                  via [Share] button -> registry shared=true. |  |
|  |                  Discovered via secondary/community/         |  |
|  |                  dashboards_index.json (rebuilt hourly +     |  |
|  |                  on-share).                                  |  |
|  +--------------------------------------------------------------+  |
|                                                                    |
+--------------------------------------------------------------------+
+--------------------------------------------------------------------+
|  /profile/dashboards/    (edit / refresh)                          |
|  +--------------------------------------------------------------+  |
|  |  MY DASHBOARDS   The viewer's own (unchanged shape, plus a   |  |
|  |                  [Share] button per card and a "shared with  |  |
|  |                  community" pill when applicable).           |  |
|  +--------------------------------------------------------------+  |
+--------------------------------------------------------------------+
```

This is the **strong lean**, not yet locked. Section 5 lists the
remaining open decisions.

---

## 3. State of the world today (post-audit summary)

The full source is in `prism/dashboards-portal.md`; this is a
distilled cheat sheet so you don't have to re-derive it.

| Category | Storage | Served by | Built via | Refreshes? |
|----------|---------|-----------|-----------|------------|
| Franchise | NOT on S3 -- HTTP fetch from `REPORT_SERVER_BASE` | `dashboard_detail()` -> `requests.get(...)` | bespoke (NOT `compile_dashboard`) | API server owns it |
| Observatory | `secondary/prism_observations/dashboards/` (5 dashboards) | (would be `dashboard_detail`; not currently rendered) | `compile_dashboard()` | NO -- `OBSERVATORY_DASHBOARD_IDS = []` is empty |
| User | `users/{kerberos}/dashboards/{id}/` | `user_dashboard_detail()` -> `s3_manager.get(...)`, ALWAYS reads `users/{viewer}/...` | `compile_dashboard()` | YES -- Phase 2 of hourly runner walks all users |

The 5 Observatory dashboards are static legacy:
- `flow_of_funds`, `money_markets`, `rates_rv` -- complete artefact set
- `leading_indicators` -- MISSING `scripts/` folder
- `macro_lead_lags` -- MISSING `scripts/pull_data.py`

The portal shows zero dashboards in the "Macro" section today
(`COMMUNITY_DASHBOARDS_CONFIG = []` in `views.py`). Only the 3
franchise tiles render, filtered by `access_group`.

Identity model:
- Django portal: `get_kerberos(request)` -> GSSSO cookie -> gsweb-kerberos cookie -> `os.getlogin()` -> env vars
- MCP HTTP API: `resolve_kerberos_info_from_baggage()` over W3C baggage tiers (0, 2.6, 2.79, 2.8, 3)

Access control:
- `PAGE_ACCESS_RULES` dict in `views.py`. Today only `irp_inquiries` and `coalition` are restricted (to `strats_trading`).
- `check_page_access(kerberos, page_id)` defaults to **allow** for unlisted page_ids.
- "Allow any authenticated user" pattern = just don't add the page_id to the rules.

Cross-user visibility status: **GREENFIELD**. No `shared` / `public` /
`community` / `visibility` flags exist anywhere. No URL pattern
carries another user's kerberos. No user-facing aggregation across
users today (the only cross-user iteration is server-side, in
`refresh_all_user_dashboards()` and `observatory_snapshot.py`).

---

## 4. Two load-bearing constraints surfaced by the audit

These are P0 for the design.

### Constraint A -- viewer-implicit S3 path

`user_dashboard_detail(request, dashboard_id)` hardcodes the path
`users/{viewer_kerberos}/dashboards/{id}/dashboard.html`. There is **no
URL grammar in PRISM today** that carries an owner kerberos. To let
user A view user B's S3 dashboard, the design **must** introduce a new
URL pattern (e.g. `/community/dashboards/<author>/<id>/`). See
`prism/dashboards-portal.md` §6.3.

### Constraint B -- `refresh_dashboard_api` auth gap

`refresh_dashboard_api` resolves the OWNER kerberos via
`data.get('kerberos') or get_kerberos(request)`. Whatever lands there
is what the spawned runner is parameterised with
(`--kerberos {kerberos}`, writing back to `users/{kerberos}/...`).
There is **no `viewer_kerberos == owner_kerberos` check**. As of
2026-04-27, an authenticated user A on the prism-users allowlist can
trigger a refresh of any user's dashboard by passing that user's
kerberos in the POST body. See `prism/dashboard-refresh.md` §2.4
for the verbatim function and the three behavioural facts called out.

The community-dashboards design needs this hardened: at the API layer,
add a `viewer_kerberos == owner_kerberos` enforcement so non-authors
cannot refresh.

---

## 5. Strong design leans (carried over from previous session)

The previous session's design discussion produced these directional
decisions. **Treat them as proposals, not commitments**; the user
explicitly wants this fresh session to revisit them with full context.

### 5.1 Storage: one path shape for all user-authored dashboards

```
users/{kerberos}/dashboards/{id}/         personal (private)
users/{kerberos}/dashboards/{id}/         personal (shared) -- same path
users/_prism_examples/dashboards/{id}/    example -- system kerberos namespace
```

The "system kerberos" `_prism_examples` would hold the 5 curated
Examples. It's a regular S3 prefix; no Django user object needed since
it never logs in. Refresh Phase 2 picks it up for free since it walks
all kerberos prefixes under `users/`.

Franchise stays untouched (separate code path).

### 5.2 Registry schema: 3 fields added, nothing removed

Per-dashboard entry in `users/{k}/dashboards/dashboards_registry.json`
(canonical schema in `prism/dashboard-refresh.md` §6.2):

```json
{
    "...existing fields...": "...",
    "shared":     false,    // NEW. user opted into Community section
    "shared_at":  null,     // NEW. ISO timestamp; null when private
    "example":    false     // NEW. true only on _prism_examples entries
}
```

All defaults false/null; backwards compatible
(`entry.get("shared", False)` works on existing registries).

### 5.3 Discovery: one global index

```
secondary/community/dashboards_index.json
```

PRISM-recommended path (Prompt 4 §4.6a). Mirrors the canonical writer
pattern in `jobs/minutely/observatory_snapshot.py`
(`build_snapshot()`): scan -> parse -> aggregate -> write.

```json
{
    "last_updated": "ISO",
    "dashboards": [
        {
            "author_kerberos": "goyalri",
            "id":              "bond_carry_roll",
            "name":            "...",
            "description":     "...",
            "tags":            [...],
            "shared_at":       "ISO",
            "last_refreshed":  "ISO",
            "example":         false
        },
        ...
    ]
}
```

Rebuild triggers:
1. Hourly: end-of-run hook in `refresh_all_user_dashboards()`.
2. On-share: synchronously inside the `/api/dashboard/share/`
   handler before returning.

Listing view does ONE `s3_manager.get` on the index, splits into
Example (filter `example=true`) and Community (filter `example=false`)
sections. No per-user walks at request time.

### 5.4 URL grammar

Existing routes unchanged. Two new routes:

| URL | Purpose |
|-----|---------|
| `/community/dashboards/<author>/<id>/` | view a community OR example dashboard. Reads `users/{author}/dashboards/{id}/dashboard.html`. Visible to any authenticated user. |
| `/api/dashboard/share/` | POST `{dashboard_id, shared: bool}` -- author-only enforcement. Updates registry + rebuilds community index inline. |

`/community/...` namespace separates these from `/profile/...`
(private) and `/dashboards/{id}/` (franchise API). One URL -> exactly
one S3 path resolution rule, no overloading.

### 5.5 Share UX

Button in dashboard header (rendered by `rendering.py` when
`metadata.kerberos` is set on the manifest). Click -> bare-minimum
modal (no css beyond what's already there per the user's HTML
constraint):

```
+-----------------------------------------------------------+
| Share with the Community                                  |
|                                                           |
| When you share, this dashboard becomes visible to         |
| everyone in the Community section of the portal. Only     |
| you can edit or refresh it.                               |
|                                                           |
| Status: [private | shared with community]                 |
|                                                           |
|                            [ Cancel ]  [ Share ]          |
+-----------------------------------------------------------+
```

POST `/api/dashboard/share/`. Server:
1. Auth: `get_kerberos(request) == owner_kerberos`, else 403.
2. Load `users/{k}/dashboards/dashboards_registry.json`.
3. Find entry by id, set `shared` + `shared_at`.
4. Save registry.
5. Rebuild `secondary/community/dashboards_index.json`.
6. Return `{ ok: true, shared, shared_at }`.

Visibility of [Share] button itself:
- Author viewing their own (at `/profile/dashboards/{id}/`): visible.
- Anyone viewing community (at `/community/dashboards/{author}/{id}/`):
  hidden if viewer != author.

Implementation: `rendering.py` emits a hidden button + a small inline
script. The Django serving view injects
`<script>window.PRISM_VIEWER='<kerberos>';</script>` into the served
HTML. Button reveals iff `PRISM_VIEWER === metadata.kerberos`.

### 5.6 Refresh authority

Same `/api/dashboard/refresh/` endpoint. Add the missing viewer-author
check (Section 4 / Constraint B). Non-authors:
- Don't see the [Refresh] button (UX).
- Get 403 if they craft the API call directly (defence in depth).

### 5.7 Attribution on community dashboards

Subtitle line under the dashboard title (rendered by `rendering.py`
when `metadata.shared = true` AND viewer != author):

```
by goyalri  ·  shared 2026-04-25  ·  last refreshed 2026-04-27 17:27 UTC
```

Suppressed when viewer == author (redundant). For example dashboards
(`metadata.example = true`) the line becomes:

```
Example dashboard  ·  last refreshed 2026-04-27 17:27 UTC
```

---

## 6. Open design decisions (need user's call)

These were left unresolved at the end of the previous session. Walk
through them with the user; do not assume the leans above are final.

1. **Listing layout.** 4 sections on a single `/dashboards/` page
   (Franchise + Example + Community + My) vs. the current 3+1 split
   (`/dashboards/` for shared, `/profile/dashboards/` for personal)?
   The previous session leaned 3+1 because the mental models differ
   (consume vs. edit) but the user has not confirmed.

2. **Example dashboards path.** Migrate the 5 to
   `users/_prism_examples/dashboards/` (uniform shape, no special
   code path, refresh Phase 2 picks them up for free) vs. keep them
   at `secondary/prism_observations/dashboards/` and bolt on a
   second discovery code path? Strong lean is migrate; user has not
   confirmed. Either way, the 2 broken dashboards
   (`leading_indicators`, `macro_lead_lags`) need rebuilding via
   Tool 1/2/3 to be made example-eligible.

3. **URL grammar.** `/community/dashboards/<author>/<id>/` (new
   namespace, viewer-explicit) vs. `/dashboards/<author>/<id>/`
   (extends existing namespace; works because Django disambiguates
   on path-segment count) vs. `/u/<kerberos>/dashboards/<id>/`
   (general user-namespace pattern that could host other artefact
   types later)? Lean is the first; alternatives have merit.

4. **Community-index location.** PRISM recommended
   `secondary/community/dashboards_index.json`. Confirm or pick a
   different convention.

5. **Share UX trigger.** Out-of-band [Share] button only (lean) vs.
   PRISM proactively asks during the build flow (Tool 3) vs. both
   (button always available; PRISM also asks when the user has
   explicitly indicated intent, e.g. "build and share")? Lean is
   button-only with PRISM honouring an explicit-share request from
   the user during build.

6. **Refresh authority on community dashboards.** Hide button +
   server 403 (lean) vs. show button to non-authors but route refresh
   to author's path (anyone can trigger a refresh) vs. show
   "Fork to my dashboards" CTA instead? Lean is hide+403 because the
   user explicitly said "only that user can edit/update."

7. **Attribution rendering details.** Header subtitle line (lean) vs.
   footer line vs. badge/pill in header? Where in the dashboard.html
   should the "by goyalri" line surface?

8. **Unsharing semantics.** When a user un-shares, do we:
   (a) delete the entry from the community index immediately and
   keep the dashboard data intact (lean), or
   (b) move the dashboard to a "snoozed" state so the URL still
   resolves but is access-gated, or
   (c) hard-delete?

9. **Tags / categories on community dashboards.** Use the existing
   `tags` field in registry entries (lean), or add an explicit
   `category` field for portal grouping?

---

## 7. Deliverables this session should produce

After the design is locked, write the following **on the staging
side** so PRISM can drag-and-drop them. Per the user rule, do NOT
write a "what we just did" summary doc -- the deliverables ARE the
output.

| # | Path | Purpose |
|---|------|---------|
| 1 | `prism/community-dashboards.md` (new) | The SSoT for this feature. Every PRISM-side change references this doc. Sections: storage model, registry schema additions, discovery + index rebuild, URL grammar, share API contract, refresh authority hardening, attribution semantics, migration plan. |
| 2 | `prism/dashboard-refresh.md` updates | §6.2 registry schema: add `shared` / `shared_at` / `example` rows to the per-dashboard entry table. §6.3 Tool 3 example: include the three new fields in the entry dict (so when PRISM hand-rolls registration it doesn't accidentally omit them). |
| 3 | `GS/viz/echarts/echarts-payload/dashboards.md` updates | §2.3 metadata block table: `shared` / `example` field rows. §9.1 Tool 3 example: include the three new fields. New short subsection (§11A or similar) on sharing semantics: PRISM defaults private; PRISM does NOT proactively ask; PRISM may set `shared=true` if user explicitly requests; sharing toggle is reversible via the [Share] button. |
| 4 | `GS/viz/echarts/echarts-payload/rendering.py` updates | [Share] button in header. Share modal HTML (bare-minimum, no styling beyond existing). Viewer-author check (reveals [Share] / [Refresh] iff `window.PRISM_VIEWER === metadata.kerberos`). Attribution subtitle for community/example dashboards. |
| 5 | A short PRISM-side spec doc (could live at `staging/community-dashboards-prism-side.md`) | Step-by-step blueprint of the Django edits Ritik will do himself: new `community_dashboard_detail()` view, new `share` API endpoint, harden `refresh_dashboard_api` viewer-author check, `dashboards()` view rewrite to read the community index, `dashboards.html` template changes (rename Macro -> Example, add Community section), `urls.py` additions, `refresh_all_user_dashboards()` hook to rebuild the community index. Verbatim-style: "edit X.py, replace Y with Z." |

After the staging-side payload lands, the user does the PRISM-side
edits + the one-time data migration of the 5 Observatory dashboards.

---

## 8. The migration (one-time, PRISM-side, after design is locked)

```
+----------------------------------------------------------------------+
|  STEP 1.  Create users/_prism_examples/                              |
|           (just an S3 prefix; no Django user object needed)          |
|                                                                      |
|  STEP 2.  Move the 3 complete Observatory dashboards:                |
|             flow_of_funds  ->  users/_prism_examples/dashboards/...  |
|             money_markets  ->  users/_prism_examples/dashboards/...  |
|             rates_rv       ->  users/_prism_examples/dashboards/...  |
|           Prefix-rename in S3 (s3_manager.list + put + del).         |
|                                                                      |
|  STEP 3.  Rebuild the 2 broken dashboards via Tool 1/2/3:            |
|             leading_indicators (missing scripts/ entirely)           |
|             macro_lead_lags    (missing scripts/pull_data.py)        |
|           Run a PRISM session for each, target                       |
|             users/_prism_examples/dashboards/{id}/                   |
|                                                                      |
|  STEP 4.  Author the registry:                                       |
|             users/_prism_examples/dashboards/dashboards_registry.json|
|           with 5 entries each having                                 |
|             shared: true, shared_at: now, example: true              |
|                                                                      |
|  STEP 5.  In jobs/hourly/refresh_dashboards.py:                      |
|             - Drop OBSERVATORY_DASHBOARD_IDS list (Phase 1 dies)     |
|             - Phase 2 walks _prism_examples for free                 |
|             - Add the community-index rebuild hook at end of Phase 2 |
|                                                                      |
|  STEP 6.  (Optional) Move secondary/prism_observations/dashboards/   |
|           to secondary/prism_observations/_archive_dashboards/       |
|           so the path stops looking like a live SoT.                 |
|                                                                      |
+----------------------------------------------------------------------+
```

---

## 9. What NOT to do this session

- Do NOT touch Franchise dashboards. They are API-served from a
  separate report server; out of scope.
- Do NOT alter `/dashboards/<id>/` or `/franchise/<id>/` URL patterns
  for franchise dashboards. They are stable.
- Do NOT redesign the refresh runner. Add the community-index hook,
  add the auth-gap fix; nothing more.
- Do NOT try to make community dashboards forkable / clonable in v1.
  That's a follow-up.
- Do NOT introduce a new database. Everything stays JSON-on-S3.
- Do NOT add CSS / styling beyond what `rendering.py` already emits
  (per the user's bare-minimum-HTML standing rule).
- Do NOT use emojis in any deliverable.
- Do NOT write a summary markdown after the work is done -- the
  deliverables ARE the summary.

---

## 10. Quick reference -- where things live

| Need | File |
|------|------|
| Portal architecture (consume side) | `prism/dashboards-portal.md` |
| Refresh pipeline + registry schema | `prism/dashboard-refresh.md` |
| Dashboard authoring (PRISM-build side) | `GS/viz/echarts/echarts-payload/dashboards.md` |
| User manifest + pointer dispatch | `prism/architecture.md` §10 |
| The Observatory subsystem | `prism/architecture.md` §7 |
| The audit trail (4 PRISM prompts) | `staging/community-dashboards-prompts.md` |
| Recent changes summary | `prism/_changelog.md` (top entry, 2026-04-27 portal audit) |
| The drag-and-drop contract for staging payload | `.cursor/rules/viz-platforms.mdc` |

Start with `prism/dashboards-portal.md`. It is the one doc that
synthesises everything you need to know about the portal side
end-to-end. Open it, read it cover to cover, and only then engage
with the user on the open decisions in Section 6 above.
