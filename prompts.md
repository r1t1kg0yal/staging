## Context extraction: local echarts.js inlining (rendering.py)

Recent change in `ai_development/dashboards/rendering.py` replaced the
CDN-hosted echarts.min.js script tag with an inlined load of a local
file at `ai_development/mysite/news/static/js/echarts.js` (resolved
via `os.path.join(os.getcwd(), ...)`). I'm rebuilding the same change
in staging and need to make it plug-and-play -- which means I need
ground truth on every place this code path runs and what `os.getcwd()`
actually is at each of those moments.

Use `list_ai_repo` and `execute_analysis_script` as needed. Reply
verbatim, no paraphrasing.

### 1. Verbatim current state of rendering.py

1. Print the FULL `HTML_SHELL` triple-quoted string in
   `ai_development/dashboards/rendering.py` (the single-chart editor
   shell). I need exact byte-for-byte content -- no truncation.
2. Print the FULL `DASHBOARD_SHELL` triple-quoted string in the same
   file (the dashboard shell). Same -- exact, no truncation.
3. Print the full body of the `_get_echarts_js()` helper (and the
   `_ECHARTS_JS_CACHE` module-level definition) verbatim, including
   the `try` / `except` block and the warning string.
4. Print the full body of `render_editor_html` and `render_dashboard_html`
   verbatim. Show every `.replace(...)` chain on the HTML in each.
5. Print the full body of the `_HARNESS` triple-quoted string at the
   bottom of `rendering.py` (PNG-export headless-Chrome harness). I
   want to confirm whether its `<script src=...echarts.min.js>` tag
   was changed in this same edit or deliberately left as CDN.

### 2. The local echarts.js asset itself

6. Confirm `ai_development/mysite/news/static/js/echarts.js` exists.
   Return: file size in bytes, sha256, and the FIRST 200 bytes
   (verbatim, the licence header). Also `grep` for a `version:"`
   substring and return whatever comes after it on that line, so I
   can match versions.
7. List every other file under `ai_development/mysite/news/static/js/`.
   Path + size for each.
8. Is this file checked into git, or .gitignored? (Run
   `git check-ignore` or `git ls-files` on it from the repo root.)

### 3. Call sites: who invokes render_dashboard_html / render_editor_html

9. Grep the entire `ai_development/` tree for callers of
   `render_dashboard_html(`, `render_editor_html(`, and
   `_get_echarts_js(`. For every hit, return:
   - file path + line number
   - the calling function's name
   - 5 lines of context above and below
10. For each calling function found in step 9, walk one level up and
    list the entry points that reach it. Specifically I want to know,
    for each of these three paths, whether they reach
    `render_dashboard_html`:
    - the build-time exec inside `execute_analysis_script` (i.e. when
      PRISM's Tool 3 calls `compile_dashboard()` during a fresh
      dashboard build)
    - the hourly cron refresh runner
      `ai_development/jobs/hourly/refresh_dashboards.py` (specifically
      via `refresh_user_dashboards` -> `refresh_single_user_dashboard`
      -> exec'd `build.py` -> `compile_dashboard()`)
    - the on-demand refresh subprocess
      `ai_development/jobs/refresh_runner.py` spawned by the Django
      `/api/dashboard/refresh/` POST endpoint
    - any Django view rendering HTML at request time

### 4. cwd at each call site (the load-bearing question)

11. For EACH of the three execution paths above (build-flow sandbox,
    hourly cron, on-demand subprocess), tell me what `os.getcwd()`
    actually is at the moment `_get_echarts_js()` runs. Either:
    (a) point me at the line in the runner / view / sandbox that
        explicitly sets cwd (e.g. `cwd=repo_root` in the `Popen`
        call, or `os.chdir(...)` somewhere), and quote that line; OR
    (b) trace the cwd inheritance from the Django parent process or
        gunicorn / uwsgi config and tell me what that root resolves
        to in the running deployment.
12. Specifically: in `subprocess.Popen([...refresh_runner_path, ...],
    cwd=repo_root, ...)` inside `refresh_dashboard_api`, what does
    `repo_root` resolve to at runtime? Print the line that computes
    it and the resolved string.
13. In `entrypoint.py`'s `fifteen_minute_context_generator()` (which
    invokes `refresh_dashboards.main()`), what is the cwd when that
    function runs? Same in the gunicorn / Django startup path.
14. Inside `execute_analysis_script`'s exec namespace, what is
    `os.getcwd()` at the moment a sandbox script calls
    `compile_dashboard(...)`? (If the sandbox doesn't change cwd,
    answer with whatever the parent Django process's cwd is.)

### 5. The persistence model for dashboard.html

15. When `compile_dashboard(manifest)` runs, does it write the rendered
    HTML to S3 as `dashboard.html` once at build time, or is the HTML
    re-rendered on each browser request? Quote the line in
    `echart_dashboard.compile_dashboard` (or wherever the write
    happens) that calls `s3_manager.put(html, ...)`.
16. Once written, is `dashboard.html` ever re-rendered server-side, or
    is the S3 object the only copy the browser ever sees? In
    particular: when a Django view serves `dashboard.html`, does it
    re-call `render_dashboard_html`, or just stream the S3 object?
    Quote the relevant view body.
17. Sanity check the storage cost: what's the average size of an
    existing `users/<k>/dashboards/<id>/dashboard.html` on S3 today?
    Print sizes for 3-5 example dashboards under `users/goyalri/`.
    (We're about to inline ~1MB of echarts.js into every one of them
    on next refresh; I want a baseline.)

### 6. The PNG harness (line 13031, the _HARNESS string)

18. Was the `_HARNESS` triple-quoted string in `rendering.py`
    deliberately left pointing at the jsdelivr CDN, or was that an
    oversight in this change? Quote the relevant lines from
    `_HARNESS` verbatim. If deliberate, what's the rationale (does
    the headless-Chrome process have network access in the GS
    deployment)?
19. Is the PNG export path (`save_chart_png`,
    `save_dashboard_pngs`, `save_dashboard_html_png`) actually used
    anywhere in the production runtime today, or is it
    development-only? Grep the repo for callers.

### 7. Other CDN dependencies in the same shell

20. The `DASHBOARD_SHELL` also loads `xlsx@0.18.5/dist/xlsx.full.min.js`
    from jsdelivr (line ~1394 in old numbering). Is this also being
    moved local in a follow-up change, or is xlsx staying CDN? If
    staying CDN, why? (Same question for the lazy-loaded
    `html2canvas@1.4.1` referenced inside `DASHBOARD_APP_JS`.)
21. List every other `cdn.jsdelivr.net` / `unpkg.com` / external
    `<script src="https://...` reference in the entire
    `ai_development/dashboards/` tree. Path + line number for each.

### 8. The design choice: inline vs link

22. Why inline echarts.js into every `dashboard.html` (1MB per file
    on S3) instead of serving it from Django's static handler at e.g.
    `/static/news/js/echarts.js` and using a relative `<script src>`?
    Quote any commit message, comment, or design doc that motivates
    this choice. Specifically I want to know:
    - is the dashboard ever opened from `file://` (offline / scanned
      PDF / email attachment)? if so, the link approach wouldn't work
      and inlining is forced.
    - is the dashboard ever served from S3 directly (presigned URL,
      no Django in front)? same constraint.
    - or is the inlining purely about avoiding the CDN dependency
      (network policy, reliability, version pinning)?
23. Does Django actually serve `ai_development/mysite/news/static/`
    today? Print the relevant `STATIC_URL` / `STATICFILES_DIRS`
    / `urls.py` static-include lines from `mysite/`. Confirm whether
    a request to `/static/news/js/echarts.js` would 200 today.

### 9. Failure-mode visibility

24. The current `_get_echarts_js()` swallows file-not-found into a
    `print("Warning: ...")` plus a `/* echarts.js not found */`
    fallback string. Where does that `print` go in the production
    runtime? Specifically:
    - in the hourly refresh runner, does stdout end up in
      `/tmp/dashboard_refresh/*.log`? (quote the `Popen(stdout=...)`
      line that wires it up)
    - in the on-demand refresh subprocess, same question
    - in the build-flow sandbox, does stdout reach the user's PRISM
      session output, or get swallowed?
25. If `_get_echarts_js()` ever returns the `/* echarts.js not found */`
    fallback, the resulting `dashboard.html` will load with no charts
    at all (silent visual regression). Does anything in the runtime
    detect this and surface it -- e.g. via `refresh_status.json.errors`,
    the in-browser modal, or a dashboard-health check? Or is the user
    expected to notice from the rendered output?

### 10. Open follow-ups, if any

26. List any TODOs, open issues, design notes, or commit-message
    plans in the GS repo around this change. (Grep for `TODO`,
    `FIXME`, `XXX`, and recent commit messages mentioning
    `echarts.js` / `_get_echarts_js` / `__ECHARTS_SCRIPT__`.)

### Output format

Reply with one section per numbered item above. Use fenced code
blocks for every JSON/dict/python source/HTML payload. Do not
summarise; we want raw material.

If part of this prompt cannot be answered (file missing, function
not found, deployment cwd not introspectable), add a brief
`## Could not resolve` section at the end listing what you tried
and what blocked it.