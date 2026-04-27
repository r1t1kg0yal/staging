# Context-extraction: dashboards portal + community-publishing groundwork

Four sequential context-extraction prompts. Cursor is designing a
"Community Dashboards" feature on top of the existing dashboards portal.
Before touching anything, Cursor needs verbatim ground truth on how the
portal works today, where the franchise / macro / observatory dashboards
actually live, and what (if any) cross-user visibility surface already
exists.

Paste each numbered section below as a separate prompt to PRISM. Each
section is a pure context-extraction prompt -- mirror the reply rules
in `_prompting-guide.md`: exact signatures, exact docstrings, exact
file paths, exact dict / JSON literals, no paraphrasing. End each
reply with `## Could not resolve` if anything was unanswerable.

---

## Prompt 1 of 3 -- The dashboards portal page (views, urls, template)

Cursor is designing a Community Dashboards feature on the existing
dashboards portal. I need verbatim ground truth on how the portal page
works today before changing anything. Use `list_ai_repo` and
`execute_analysis_script` (read on-disk source in `mysite/`,
`ai_development/`, and any templates dir) to ground every answer.

### 1.1 The listing view function

a. Find the Django view function that renders the dashboards landing
   page (the page with the franchise / macro / my-dashboards sections,
   typically reached via `/profile/dashboards/` or similar). Report:
   - Full file path (likely `mysite/news/views.py` or sibling)
   - Verbatim function source, including decorators and the full body
   - The template name it renders
   - The full context dict it builds and passes to the template

b. List every function in that views.py file whose name suggests it
   handles a dashboard-related route (rendering, listing, refresh,
   share, status). For each, paste the verbatim signature + first
   3 lines of body.

### 1.2 URL patterns for dashboards

a. Open `mysite/news/urls.py` (or wherever `urlpatterns` for the
   dashboards module lives) and paste verbatim every entry whose path
   contains "dashboard". Include the full `path(...)` / `re_path(...)`
   call with the view reference and the `name=` kwarg.

b. If the listing page is served by a different `urls.py` than the
   refresh API, paste both verbatim.

### 1.3 The Django template

a. Find the template file that the listing view renders (likely
   `templates/dashboards.html` or `mysite/news/templates/...`).
   Report the full file path and total line count.

b. Paste verbatim the HTML chunk that renders each of the existing
   sections. Specifically I need to see:
   - The "franchise" section block (any `{% for %}` / hardcoded HTML)
   - The "macro" section block
   - The "my dashboards" / user dashboards section block
   - Any header / nav that wraps them

c. Paste verbatim every Django template tag (`{% ... %}`) and template
   variable (`{{ ... }}`) used in those section blocks. I want to know
   exactly which context variables drive each section's render.

### 1.4 Where each section's data comes from

For each of the three sections (franchise, macro, my dashboards), tell
me how the listing view computes the section's contents:

a. Is it a hardcoded Python list / dict in views.py or a settings file?
   If yes, paste it verbatim with full file path.

b. Is it loaded from a JSON / YAML config on disk? If yes, paste the
   file path and the file contents verbatim.

c. Is it loaded from S3 (e.g. by listing `users/{kerberos}/dashboards/`
   or reading `dashboards_registry.json`)? If yes, paste the verbatim
   Python that does the loading.

d. Is it loaded from a database model? If yes, paste the model + queryset.

### 1.5 Per-dashboard view (the click-through)

When a user clicks a dashboard tile in the listing page:

a. What URL does it navigate to? Paste the `<a href="...">` template
   substitution verbatim and the matching `urls.py` entry.

b. What view function serves that URL? Paste it verbatim.

c. How does the response body land in the browser? Specifically:
   - Does the view fetch the compiled `dashboard.html` from S3 via
     `s3_manager.get(...)` and return it as `HttpResponse(html)`?
   - Or is there a redirect / proxy / static-file mount?
   - Or are dashboards served directly from S3 with a presigned URL?

d. Does the click-through URL embed the kerberos of the OWNER, or only
   the dashboard id, or both? E.g.
   - `/profile/dashboards/{dashboard_id}/`  (viewer-implicit)
   - `/users/{kerberos}/dashboards/{dashboard_id}/`  (explicit owner)
   - Something else

   Paste the canonical pattern verbatim.

### 1.6 Auth + identity

a. How does the listing view determine which user is making the request?
   Paste verbatim the function (`get_kerberos(request)` or equivalent)
   that resolves the kerberos, including its full body.

b. Where does that kerberos come from -- session cookie, custom header,
   query string, OS user, hardcoded? Tell me by reading the function
   body.

c. Are there any auth decorators (`@login_required`, `@require_auth`,
   etc.) on the dashboard views? List each one and paste its verbatim
   definition (it might be a custom decorator).

---

End-of-prompt reminder: if anything cannot be answered, end with a
`## Could not resolve` section listing what you tried and what blocked
it. Verbatim code only -- no paraphrasing.

---

## Prompt 2 of 3 -- Where franchise / macro / observatory dashboards actually live

Cursor needs to know exactly where the 3 franchise dashboards (inquiry,
coalition, flows) and the 5 "macro" dashboards live on S3, who owns
them, whether they go through the same `compile_dashboard` pipeline as
user dashboards, and what's at `secondary/prism_observations/dashboards/`.

This is a pure context-extraction prompt. Use `list_ai_repo`,
`execute_analysis_script`, and `s3_manager.list(...)` /
`s3_manager.get(...)` to ground every answer in real on-disk and on-S3
state.

### 2.1 Franchise dashboards (inquiry, coalition, flows)

For each of the 3 franchise dashboards, report:

a. Display name as shown in the portal
b. Internal id / slug
c. Full S3 folder path (e.g. `users/{kerberos}/dashboards/{id}/` or
   `franchise/dashboards/{id}/`, etc.)
d. Owner kerberos (if any), or "n/a -- not owned by any user"
e. The output of `s3_manager.list(<that folder>)` verbatim, so I can
   see which artefacts are present (`manifest.json`,
   `manifest_template.json`, `dashboard.html`, `scripts/pull_data.py`,
   `scripts/build.py`, `data/*.csv`, `refresh_status.json`)
f. Whether it has a registry entry, and if yes, paste the verbatim
   entry from whatever registry it sits in
g. Whether it was built via the standard `compile_dashboard()` flow
   (three-tool model in `dashboards.md` §9.1), or via bespoke
   hand-written HTML / a different builder. If bespoke, point at the
   builder file with a verbatim path.
h. Whether it refreshes -- if yes, via the standard
   `jobs/hourly/refresh_dashboards.py` runner, or a different cron job.
   Paste the relevant scheduling code verbatim.

### 2.2 "Macro" dashboards (the 5 the user wants to rename to "Example")

Same structure as 2.1 -- for each of the 5 dashboards, report a-h.
List every macro dashboard PRISM is currently rendering in the portal's
Macro section.

### 2.3 The hardcoded list (or not) of franchise + macro dashboards

a. Find wherever the portal's listing view enumerates these 8
   dashboards (3 franchise + 5 macro). It is almost certainly a
   Python list / dict literal in `mysite/news/views.py`,
   `ai_development/dashboards/__init__.py`, a settings module, a JSON
   config, or similar.

b. Paste the verbatim source -- full file path, exact list / dict
   literal -- whatever the listing view actually iterates over to
   build the franchise + macro sections.

c. If there is more than one source of truth (e.g. one list for
   franchise, one for macro), paste each.

### 2.4 secondary/prism_observations/dashboards/

`prism/architecture.md` §7.3 says this path holds "per-framework
dashboards" owned by the Observatory. I need to understand what's
actually there and whether it overlaps with the portal's franchise /
macro lists.

a. Paste verbatim the output of
   `s3_manager.list('secondary/prism_observations/dashboards/')`
   (top level only).

b. For each subfolder at that path, paste the output of
   `s3_manager.list(<subfolder>)` so I can see the artefact set.

c. Are any of these subfolder dashboards rendered in the portal? If
   yes, which ones, and through what code path -- the franchise list,
   the macro list, or a separate Observatory section?

d. If the Observatory dashboards are NOT rendered in the user-facing
   portal at all, say so explicitly -- the portal sections may be
   sourced from a different S3 path entirely (e.g. user folders).

### 2.5 Refresh model for non-user dashboards

a. Does `jobs/hourly/refresh_dashboards.py`'s user-iteration loop pick
   up franchise / macro / observatory dashboards? Or is there a
   separate cron job for them? Paste the relevant code.

b. If franchise / macro dashboards live under a non-`users/{kerberos}/`
   path, does the refresh runner know to look there? Paste the
   discovery code verbatim.

c. Print the registry path(s) the runner reads for each non-user
   dashboard category, if any.

---

End-of-prompt reminder: if anything cannot be answered, end with a
`## Could not resolve` section. Exact paths, exact list / dict
literals, exact registry JSONs.

---

## Prompt 3 of 3 -- Identity, permissions, and existing cross-user visibility

Cursor is adding a "share this dashboard with the community" flag.
Before designing it, Cursor needs to know what cross-user visibility
already exists in PRISM (across cabinets, knowledge bases, reports,
anything), how the auth model handles "viewer != author", and how the
per-dashboard URL handles ownership.

Pure context-extraction. Use `list_ai_repo`, file reads, and grep over
`ai_development/` + `mysite/`.

### 3.1 Identity resolution end-to-end

a. The function that returns the current request's kerberos -- paste
   verbatim with file path and full body. Include any helpers it
   calls.

b. List every place in `mysite/` and `ai_development/` that calls
   that function. Paste a one-line summary of each call site (file
   path + line number + surrounding context).

c. How does kerberos get into the request in the first place? Headers
   added by a reverse proxy? Django session middleware? OS env? Paste
   the relevant middleware / authentication backend verbatim.

### 3.2 Per-dashboard URL: viewer-implicit vs explicit-owner

a. Today, when a user clicks a dashboard in the portal, does the URL
   carry the OWNER kerberos or only the dashboard id? Paste the URL
   pattern verbatim from `urls.py` + the matching view's first 10
   lines (so I can see how it resolves the owning user).

b. Is there ANY URL pattern in PRISM today that includes another
   user's kerberos in the path so that user A can view user B's
   content? E.g. `/users/{kerberos}/dashboards/...`,
   `/u/{kerberos}/cabinet/...`, etc. List every such pattern with
   the matching view's first 10 lines.

c. If no such pattern exists today, say so explicitly. That tells me
   the URL grammar will need a new shape for community dashboards.

### 3.3 Existing visibility / sharing surface area

I want to know whether PRISM already has any concept of "shared with
others" / "public" / "community" / "discoverable" anywhere -- not just
for dashboards, but for any artefact type.

a. Grep `ai_development/` and `mysite/` for the strings: `shared`,
   `public`, `community`, `visibility`, `discoverable`, `published`.
   For each match, report file path + line number + the surrounding
   3 lines verbatim. (Skip obvious noise like `publication`,
   `publisher`, log lines.)

b. For any match that looks structural (a flag in a dataclass / Pydantic
   model / JSON schema; a column in a Django model; a permission check
   in a view), paste the full enclosing definition verbatim.

c. Does the user manifest (`users/{kerberos}/manifest.json`) have a
   pointer block for any cross-user-visible artefact today (e.g. a
   `pointers.shared_*` block, or a `community` / `published` field)?
   Paste a real `manifest.json` verbatim and call out any such block.

### 3.4 User manifest pointers block

a. Paste a verbatim real `users/goyalri/manifest.json` (or similar
   live user) so I can see the exact `pointers` block shape.

b. List every `artifact_type` argument value that
   `update_user_manifest(kerberos, artifact_type=...)` knows about,
   from reading the source. Paste the dispatch / branching code
   verbatim.

c. For each artifact_type, paste the matching `update_*_pointer`
   classmethod's verbatim code (so I can see what each one writes
   into the manifest's `pointers.<type>` block).

### 3.5 Aggregation surface today

a. Is there ANY page in the portal today that aggregates content
   across users -- a "discover" page, a "team" page, an "all reports"
   page, anything? If yes, paste the view + template + the aggregation
   code (the bit that fans out across users).

b. Has the codebase implemented anything like
   `walk_all_user_registries()` or similar -- where one process reads
   every `users/*/dashboards/dashboards_registry.json` (or any
   per-user file) to build a global view? If yes, paste it verbatim.
   `jobs/hourly/refresh_dashboards.py` does iterate users; is anything
   else doing that?

c. If nothing aggregates across users today, say so explicitly -- I
   need to know whether community-dashboard discovery is greenfield or
   has prior art to follow.

---

End-of-prompt reminder: if anything cannot be answered, end with a
`## Could not resolve` section. Exact paths, exact code, exact JSONs --
no paraphrasing.

---

## Prompt 4 of 4 -- Final residuals: access rules, nav, refresh internals, registries

Cursor has the design pinned down based on Prompts 1-3. Six small but
load-bearing items remain. After this reply Cursor can finalise the
end-to-end design and the staging-side payload. Pure context-extraction
-- exact code, exact dict literals, exact JSONs.

### 4.1 Observatory dashboards path (registry + write provenance)

a. Paste verbatim the contents of
   `secondary/prism_observations/dashboards/dashboards_registry.json`.
   I want to see the full file so I can plan whether to migrate the 5
   dashboards to `users/_prism_examples/dashboards/` (a system kerberos
   namespace) or leave them where they are.

b. Grep `ai_development/jobs/`, `observatory_screen.py`,
   `observatory_snapshot.py`, and any cron-scheduled module for the
   string `secondary/prism_observations/dashboards`. For every match,
   report file path + line number + the surrounding 10 lines verbatim.
   I need to know whether ANY automated process writes to that path,
   or whether the 5 dashboards there are static legacy from a previous
   build that nothing maintains.

c. Are these 5 dashboards expected to be regenerated by an automated
   Observatory process going forward, or were they hand-built by a
   developer / past PRISM session and abandoned?

### 4.2 Access control internals

a. Find `PAGE_ACCESS_RULES`. Paste the full file path and the verbatim
   dict literal (no truncation). I need to see the actual rule shapes
   used today.

b. Paste the verbatim source of `check_page_access(kerberos, page_id)`
   -- full function body, all branches.

c. What is the default behaviour of `check_page_access()` when a
   `page_id` is NOT a key in `PAGE_ACCESS_RULES`? Read the source and
   tell me explicitly: does it return True (allow), False (deny), or
   something else?

d. Is there an "allow any authenticated user" rule pattern (e.g. a
   sentinel value, a wildcard, or a convention like `access_group:
   "all"`)? If yes, paste an example. If no, say so explicitly --
   community dashboards will need this pattern added.

### 4.3 Nav scaffolding

a. Paste the verbatim source of `_build_nav_context(kerberos)`
   (referenced in `views.dashboards()`).

b. The dashboards.html template uses `nav_franchise_dashboards`,
   `nav_community_dashboards`, `nav_recent_observations`. Find the
   template chunk that renders the nav (likely in `news/base.html` or a
   template include). Paste verbatim the lines that iterate / display
   each of those three lists.

### 4.4 Refresh runner internals

a. Paste the verbatim full body of `refresh_all_user_dashboards()` (or
   whatever the function in `jobs/hourly/refresh_dashboards.py` Phase 2
   is actually named that walks all users).

b. Paste the verbatim full body of `refresh_dashboard_api(request)`
   from `views.py`. I specifically need to confirm:
   - How it resolves which kerberos owns the dashboard being refreshed
   - Whether it enforces `viewer_kerberos == owner_kerberos`
   - Whether the spawned subprocess is parameterised with the OWNER's
     kerberos (so a refresh of user B's dashboard from user A's session
     would still write to B's S3 path) or the VIEWER's kerberos

c. Paste the verbatim source of `_should_refresh(dashboard_config)`
   from the runner (the per-dashboard scheduling decision documented in
   `prism/dashboard-refresh.md` §5.1).

### 4.5 Real-life user state

a. Paste verbatim contents of
   `users/goyalri/dashboards/dashboards_registry.json` (the FULL
   file -- top-level, every entry, no truncation). I have an entry
   shape from Prompt 2 but need to see the live file in full.

b. Confirm the `pointers.dashboards` block from `users/goyalri/
   manifest.json` is unchanged from what was pasted in Prompt 3 §3.3.
   If it has changed since (e.g. recent dashboard registration), paste
   the current version.

### 4.6 The community-index design check

a. Where on S3 would you put a global community dashboards index file?
   I am currently planning `secondary/community/dashboards_index.json`
   (mirroring how `secondary/prism_observations/observations/` and
   `secondary/prism_observations/reports/` are centralised). Is there
   any existing convention I should follow instead? Grep for any
   `_index.json` / `index.json` files under `secondary/` and report
   their paths.

b. Is there a writer/reader pattern PRISM already uses for "single JSON
   file aggregating across users, rebuilt by a scheduled job"? E.g. the
   observatory_snapshot.json. Paste the writer code path so I can
   mirror it for the community index.

---

End-of-prompt reminder: if anything cannot be answered, end with a
`## Could not resolve` section. Exact paths, exact code, exact JSONs --
no paraphrasing.
