# PRISM-side blueprint: Community Dashboards v0

This document is the step-by-step recipe to land community-dashboards
support in PRISM. The staging side
(`GS/viz/echarts/echarts-payload/rendering.py` + `dashboards.md`) is
already done -- every dashboard now ships with a `[Share]` /
`[Sharing]` button in the standard top-right header row alongside
Methodology / Refresh / Download. This doc covers the Django edits
that wire that button to a real backend, plus the two new portal
surfaces.

Read the staging-side facts in:

- `prism/dashboards-portal.md` (URLs, views, identity, access control)
- `prism/dashboard-refresh.md` (registry schema, refresh API, status API)
- `prism/architecture.md` §10.5 (`UserRegistry` semantics + the
  `secondary/sod/prism_users_list.json` source-of-truth)
- `GS/viz/echarts/echarts-payload/dashboards.md` §2.3 (the new
  `metadata.shared` / `metadata.shared_at` / `metadata.share_api_url`
  fields the rendering layer expects)

The whole thing is **4 file edits** in PRISM. No new files. No
schema migrations. No S3 layout changes. No edits to
`user_manifest.py`, `refresh_runner.py`, `_build_exec_namespace`, or
the auth allowlist.

---

## What you're building

Three behavioural changes:

1. The `/dashboards/` listing page Community section, currently
   empty, populates from a live walk over every user's
   `dashboards_registry.json`, filtered by `shared == true`. Each
   tile carries a `by <author>` attribution line.
2. A new URL `/community/dashboards/<author>/<dashboard_id>/` serves
   any user's shared dashboard to any authenticated PRISM user.
3. A new POST endpoint `/api/dashboard/share/` takes a
   `{dashboard_id, shared}` body and toggles the calling user's own
   registry entry. Author-only by construction (the registry it
   touches is always `users/{viewer}/dashboards/...`).

The `[Share]` button in every dashboard's header POSTs to that new
endpoint. The button is non-author-invisible because the
dashboard-serving view will inject `window.PRISM_VIEWER` so the
runtime can compare viewer vs author.

---

## Edit 1: `mysite/news/urls.py`

Add two routes. Position them next to the existing
`/api/dashboard/refresh/` and `/profile/dashboards/` entries -- the
exact ordering does not matter.

```python
# news/urls.py
urlpatterns = [
    # ... existing routes ...

    path('api/dashboard/share/',
         views.share_dashboard_api,
         name='share_dashboard_api'),

    path('community/dashboards/<str:author>/<str:dashboard_id>/',
         views.community_dashboard_detail,
         name='community_dashboard_detail'),
]
```

---

## Edit 2: `mysite/news/views.py`

Three additions:

1. New view `community_dashboard_detail` (~30 lines).
2. New view `share_dashboard_api` (~40 lines).
3. Rewrite of the existing `dashboards()` listing view (~25 lines
   replace the current empty `COMMUNITY_DASHBOARDS_CONFIG` filter).

### 2.1 `community_dashboard_detail`

Mirrors `user_dashboard_detail` but takes an explicit `author` from
the URL and verifies the entry has `shared: true` before serving. It
also injects `window.PRISM_VIEWER` and `window.PRISM_DASHBOARD_SHARED`
into the served HTML so the rendering-side share button knows who
the viewer is and what the live share state is.

```python
@require_auth
def community_dashboard_detail(request, author, dashboard_id):
    """Serve a shared dashboard from another user's S3 namespace.

    The dashboard.html embedded in users/{author}/dashboards/{id}/ is
    served verbatim, augmented with a one-line <script> tag that
    injects window.PRISM_VIEWER and window.PRISM_DASHBOARD_SHARED so
    the rendering-side [Share] button can decide visibility (viewer
    must equal author) and initial state (live registry truth).
    """
    viewer = get_kerberos(request)
    if not viewer:
        return HttpResponse("Unauthorized", status=401)

    try:
        from ai_development.core.s3_bucket_manager import s3_manager

        # Verify the dashboard is actually shared. Don't leak a non-
        # shared dashboard via URL guessing.
        reg_path = f"users/{author}/dashboards/dashboards_registry.json"
        raw      = s3_manager.get(reg_path)
        registry = json.loads(raw.rstrip(b'\x00').decode('utf-8'))
        entry    = next(
            (d for d in registry.get('dashboards', []) if d.get('id') == dashboard_id),
            None,
        )
        if not entry or not entry.get('shared', False):
            return HttpResponse("Dashboard not found", status=404)

        # Serve the dashboard.html, with viewer/shared context injected.
        html_path = f"users/{author}/dashboards/{dashboard_id}/dashboard.html"
        html_raw  = s3_manager.get(html_path)
        html      = html_raw.rstrip(b'\x00').decode('utf-8')
        injection = (
            f'<script>'
            f'window.PRISM_VIEWER={json.dumps(viewer)};'
            f'window.PRISM_DASHBOARD_SHARED={json.dumps(bool(entry.get("shared", False)))};'
            f'window.PRISM_DASHBOARD_AUTHOR={json.dumps(author)};'
            f'</script>'
        )
        # Inject right before </head> so the globals are set before the
        # dashboard's own <script> block runs.
        if '</head>' in html:
            html = html.replace('</head>', injection + '</head>', 1)
        else:
            html = injection + html

        return HttpResponse(html, content_type='text/html')
    except Exception:
        return HttpResponse("Dashboard not found", status=404)
```

The same injection trick should also be applied to
`user_dashboard_detail` (the author's own view), so the share button
appears with correct state when the author opens their own
`/profile/dashboards/<id>/` page. Two-line edit:

```python
@require_auth
def user_dashboard_detail(request, dashboard_id):
    """Serve a specific user dashboard HTML from S3."""
    kerberos = get_kerberos(request)
    if not kerberos:
        return HttpResponse("Unauthorized", status=401)
    try:
        from ai_development.core.s3_bucket_manager import s3_manager

        # Read the registry to learn current share state -- the manifest
        # snapshot in dashboard.html may be stale.
        shared = False
        try:
            reg_raw = s3_manager.get(f"users/{kerberos}/dashboards/dashboards_registry.json")
            reg     = json.loads(reg_raw.rstrip(b'\x00').decode('utf-8'))
            entry   = next((d for d in reg.get('dashboards', []) if d.get('id') == dashboard_id), None)
            if entry:
                shared = bool(entry.get('shared', False))
        except Exception:
            pass

        s3_path = f"users/{kerberos}/dashboards/{dashboard_id}/dashboard.html"
        raw     = s3_manager.get(s3_path)
        html    = raw.rstrip(b'\x00').decode('utf-8')
        injection = (
            f'<script>'
            f'window.PRISM_VIEWER={json.dumps(kerberos)};'
            f'window.PRISM_DASHBOARD_SHARED={json.dumps(shared)};'
            f'window.PRISM_DASHBOARD_AUTHOR={json.dumps(kerberos)};'
            f'</script>'
        )
        if '</head>' in html:
            html = html.replace('</head>', injection + '</head>', 1)
        else:
            html = injection + html
        return HttpResponse(html, content_type='text/html')
    except Exception:
        return HttpResponse("Dashboard not found", status=404)
```

The author viewing their own community URL
(`/community/dashboards/<them>/<id>/`) is fine -- the same script
tag fires, the button still shows because viewer == author. If you
prefer the author to be redirected to `/profile/dashboards/<id>/`
when they hit their own community URL, add this at the top of
`community_dashboard_detail` (optional polish):

```python
if viewer == author:
    return redirect('news:user_dashboard_detail', dashboard_id=dashboard_id)
```

### 2.2 `share_dashboard_api`

Author-only POST endpoint. The author identity is taken from the
session (`get_kerberos(request)`) and is the only kerberos that ever
addresses the registry -- no path parameter for "whose dashboard."

```python
@csrf_exempt
def share_dashboard_api(request):
    """Toggle the community-share flag on the caller's own dashboard.

    Body: {"dashboard_id": str, "shared": bool}
    Returns: {"ok": True, "shared": bool, "shared_at": str|null}

    Author-only by construction: the registry path is always
    users/{caller}/dashboards/dashboards_registry.json, so a non-author
    cannot toggle someone else's share state regardless of the body.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = get_kerberos(request)
    if not user:
        return JsonResponse({'error': 'Authentication required.'}, status=403)
    allowed = _get_prism_users()
    if allowed and user not in allowed:
        return JsonResponse({'error': f'User {user} is not authorized.'}, status=403)

    try:
        data = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid JSON body'}, status=400)

    dashboard_id = data.get('dashboard_id')
    target       = bool(data.get('shared', False))
    if not dashboard_id:
        return JsonResponse({'error': 'dashboard_id required'}, status=400)

    from ai_development.core.s3_bucket_manager import s3_manager
    registry_path = f"users/{user}/dashboards/dashboards_registry.json"

    try:
        raw      = s3_manager.get(registry_path)
        registry = json.loads(raw.rstrip(b'\x00').decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'No dashboards registry for this user'}, status=404)

    entry = next(
        (d for d in registry.get('dashboards', []) if d.get('id') == dashboard_id),
        None,
    )
    if entry is None:
        return JsonResponse({'error': f'Dashboard {dashboard_id} not found'}, status=404)

    now              = datetime.utcnow().isoformat() + "Z"
    entry['shared']    = target
    entry['shared_at'] = now if target else None
    registry['last_updated'] = now

    try:
        s3_manager.put(registry, registry_path)
    except Exception as e:
        return JsonResponse({'error': f'Failed to save registry: {e}'}, status=500)

    return JsonResponse({
        'ok':        True,
        'shared':    target,
        'shared_at': entry['shared_at'],
    })
```

### 2.3 Rewrite `dashboards()` listing

Drop the `COMMUNITY_DASHBOARDS_CONFIG` filter; replace with a live
walk over every registered kerberos. The hardcoded
`COMMUNITY_DASHBOARDS_CONFIG = []` constant + `STANDALONE_DASHBOARDS`
alias above can stay as dead code or be deleted -- nothing else
references them after this edit.

```python
@require_auth
def dashboards(request):
    """Dashboards listing page -- franchise dashboards first, then community.

    Community dashboards are discovered live: walk every registered
    kerberos in UserRegistry, read each user's
    dashboards_registry.json, keep entries with shared==true. Cached
    inline-only via the request lifecycle; with N users this is N
    s3_manager.get calls per page render. Add @lru_cache(ttl=60) when
    the user count grows past ~50.
    """
    kerberos = get_kerberos(request)

    visible_franchise = [
        d for d in FRANCHISE_DASHBOARDS_CONFIG
        if check_page_access(kerberos, d['id'])
    ]

    from ai_development.core.common              import UserRegistry
    from ai_development.core.s3_bucket_manager   import s3_manager
    community = []
    try:
        all_kerberos = sorted(UserRegistry.instance().get_all_kerberos_ids())
    except Exception:
        all_kerberos = []
    for k in all_kerberos:
        try:
            raw = s3_manager.get(f"users/{k}/dashboards/dashboards_registry.json")
            reg = json.loads(raw.rstrip(b'\x00').decode('utf-8'))
        except Exception:
            continue
        for d in reg.get('dashboards', []):
            if d.get('shared', False):
                community.append({
                    'author':         k,
                    'id':             d.get('id', ''),
                    'name':           d.get('name', d.get('id', '')),
                    'description':    d.get('description', ''),
                    'tags':           d.get('tags', []),
                    'last_refreshed': d.get('last_refreshed', ''),
                    'shared_at':      d.get('shared_at', ''),
                })

    # Sort: most recently shared first
    community.sort(key=lambda d: d.get('shared_at', '') or '', reverse=True)

    context = {
        "franchise_dashboards": visible_franchise,
        "community_dashboards": community,
        "kerberos":             kerberos,
        "display_name":         _get_user_display_name(kerberos),
        "s3_image1_url":        _get_s3_image_url(HERO_IMAGE_KEY),
    }
    context.update(_build_nav_context(kerberos))
    return render(request, "news/dashboards.html", context)
```

The same walk logic should ALSO replace the
`nav_community_dashboards` computation in `_build_nav_context` so the
top-bar dropdown surfaces community dashboards consistently:

```python
def _build_nav_context(kerberos):
    """Build context dict for navigation elements that need access filtering."""
    nav_franchise = [
        d for d in FRANCHISE_DASHBOARDS_CONFIG
        if check_page_access(kerberos, d['id'])
    ]

    # Community: same walk as dashboards() listing, capped to a small
    # number for the dropdown (no point listing 200 in a menu).
    from ai_development.core.common              import UserRegistry
    from ai_development.core.s3_bucket_manager   import s3_manager
    nav_community = []
    try:
        for k in sorted(UserRegistry.instance().get_all_kerberos_ids()):
            try:
                raw = s3_manager.get(f"users/{k}/dashboards/dashboards_registry.json")
                reg = json.loads(raw.rstrip(b'\x00').decode('utf-8'))
            except Exception:
                continue
            for d in reg.get('dashboards', []):
                if d.get('shared', False):
                    nav_community.append({
                        'author': k,
                        'id':     d.get('id', ''),
                        'name':   d.get('name', d.get('id', '')),
                    })
    except Exception:
        pass
    nav_community = nav_community[:12]   # cap dropdown length

    return {
        "nav_franchise_dashboards": nav_franchise,
        "nav_community_dashboards": nav_community,
        "nav_recent_observations":  _get_nav_recent_observations(),
    }
```

---

## Edit 3: `mysite/news/templates/news/dashboards.html`

Two changes to the existing template:

1. Rename the section heading "Macro Dashboards" -> "Community Dashboards".
2. Update the tile to:
   - Link to `community_dashboard_detail` (with author + id), not `dashboard_detail`.
   - Show the `by {{ dash.author }}` attribution line.

```html
<!-- Community Dashboards (was: "Macro Dashboards") -->
<h2 class="section-label" style="margin-top: 48px; margin-bottom: 20px;">Community Dashboards</h2>
<div class="obs-grid">
    {% for dash in community_dashboards %}
    <a href="{% url 'news:community_dashboard_detail' dash.author dash.id %}" class="observation-card" style="display:block;">
        <h3 class="obs-headline">{{ dash.name }}</h3>
        <p class="obs-body">{{ dash.description }}</p>
        <p class="obs-body" style="font-size: 0.78rem; color: #888; margin-top: 8px;">by {{ dash.author }}</p>
    </a>
    {% empty %}
    <div style="grid-column: 1 / -1;">
        <p class="empty-state">No community dashboards yet. Build one and click [Share] in the header to publish it here.</p>
    </div>
    {% endfor %}
</div>
```

## Edit 4: `mysite/news/templates/news/base.html` nav block

Same rename inside the dropdown. Lines 1056-1078 currently have a
"Macro Dashboards" sub-heading. Change one literal:

```html
<!-- Was: -->
<li style="...">Macro Dashboards</li>
<!-- Now: -->
<li style="...">Community Dashboards</li>
```

The `nav_community_dashboards` iteration block underneath stays as
is, and the link target should also update from
`{% url 'news:dashboard_detail' dash.id %}` to
`{% url 'news:community_dashboard_detail' dash.author dash.id %}` so
clicks from the dropdown route through the new view.

---

## How users use it (end-to-end)

```
+--------------------------------------------------------------------+
|  AUTHOR PUBLISHES                                                  |
|                                                                    |
|  goyalri opens /profile/dashboards/bond_carry_roll/                |
|  Sees standard header: Methodology | Refresh | [Share] | Download  |
|     ^^^^^^                                                         |
|     visible because window.PRISM_VIEWER == metadata.kerberos       |
|                                                                    |
|  Click [Share]                                                     |
|     -> POST /api/dashboard/share/                                  |
|        body {dashboard_id: "bond_carry_roll", shared: true}        |
|     -> Server flips entry in goyalri's registry                    |
|     -> Response {ok:true, shared:true, shared_at:"<ISO>"}          |
|     -> Button label flips to [Sharing] (sky-blue accent)           |
|                                                                    |
|  Tile now appears on /dashboards/ Community section.               |
|  Direct URL /community/dashboards/goyalri/bond_carry_roll/         |
|  now resolves to the same dashboard.html.                          |
+--------------------------------------------------------------------+

+--------------------------------------------------------------------+
|  ANOTHER USER VIEWS                                                |
|                                                                    |
|  desaku opens /dashboards/                                         |
|  Sees Franchise (3 tiles) + Community (N tiles).                   |
|  goyalri's "Bond Carry & Roll" tile shows "by goyalri".            |
|                                                                    |
|  Click the tile -> /community/dashboards/goyalri/bond_carry_roll/  |
|     -> community_dashboard_detail view                             |
|     -> Reads users/goyalri/dashboards/dashboards_registry.json     |
|     -> Confirms entry.shared == true                               |
|     -> Reads dashboard.html, injects:                              |
|        window.PRISM_VIEWER          = "desaku"                     |
|        window.PRISM_DASHBOARD_SHARED = true                        |
|        window.PRISM_DASHBOARD_AUTHOR = "goyalri"                   |
|     -> Returns the HTML                                            |
|                                                                    |
|  In desaku's browser:                                              |
|     - Methodology, Refresh, Download buttons are present (Refresh  |
|       works for non-authors today; tighten via a separate auth-gap |
|       fix if you want author-only refresh)                         |
|     - [Share] button is hidden (viewer != author)                  |
+--------------------------------------------------------------------+

+--------------------------------------------------------------------+
|  AUTHOR UNPUBLISHES                                                |
|                                                                    |
|  goyalri returns to /profile/dashboards/bond_carry_roll/           |
|  Header shows [Sharing] in sky-blue.                               |
|                                                                    |
|  Click [Sharing] -> confirm modal "Make this private?"             |
|  Click [Make private]                                              |
|     -> POST /api/dashboard/share/                                  |
|        body {dashboard_id: "bond_carry_roll", shared: false}       |
|     -> Server: entry.shared = false, shared_at = null              |
|     -> Response {ok:true, shared:false, shared_at:null}            |
|     -> Button label flips back to [Share]                          |
|                                                                    |
|  Tile disappears from /dashboards/ on next page load.              |
|  /community/dashboards/goyalri/bond_carry_roll/ now returns 404.   |
+--------------------------------------------------------------------+
```

---

## Quick verification checklist

After landing all four edits:

1. `python manage.py runserver`
2. Visit `/dashboards/`. Community section is empty (none of your
   test users have shared yet).
3. Visit `/profile/dashboards/<some_id>/`. Open the dashboard. The
   header has a `[Share]` button to the right of `[Refresh]`.
4. Click `[Share]`. Button flips to `[Sharing]` (sky-blue). Server
   logs show a POST to `/api/dashboard/share/` returning 200.
5. Refresh `/dashboards/`. The tile appears in Community with "by
   <your kerberos>".
6. Click the tile. The dashboard renders. `[Share]` is still visible
   to you (you're the author). Open a different browser session as
   another kerberos -- `[Share]` is hidden, but the dashboard
   renders identically.
7. Click `[Sharing]` in your session. Confirm modal opens. Click
   "Make private". Button reverts to `[Share]`. Refresh
   `/dashboards/` -- tile is gone.
8. Open `/community/dashboards/<your_kerberos>/<id>/` in an
   incognito/non-allowlisted session -- `@require_auth` should kick.
   In an allowlisted session -- 404 because shared==false now.

---

## Things explicitly out of scope for v0

- **Examples namespace** (`users/_prism_examples/dashboards/`,
  Macro->Example renaming, migrating the 5 dormant Observatory
  dashboards). Independent feature; ships separately.
- **Refresh-API author-only enforcement.** Today
  `/api/dashboard/refresh/` accepts any `kerberos` in the POST body.
  Community dashboards inherit this -- non-authors can refresh by
  calling the API by hand. The button itself is still owner-keyed
  via `metadata.kerberos`, so accidental triggers from a community
  viewer are limited to the case where the viewer happens to be in
  the PRISM allowlist AND knows the API contract. If the strict
  "only the author can refresh community dashboards" semantic is
  desired, fold in the 3-line viewer-author check in
  `refresh_dashboard_api` (see `prism/dashboards-portal.md` §6.3 +
  `prism/dashboard-refresh.md` §2.4 fact #2).
- **Initial-load status fetch on community URLs.** Non-authors
  viewing a community dashboard fire one
  `GET /api/dashboard/refresh/status/?dashboard_id=...` on page
  load. The endpoint constructs `users/{viewer}/...` and falls
  through to `{"status": "unknown"}`. Harmless; one wasted round
  trip. Optional polish: gate the initial-load fetch on
  `window.PRISM_VIEWER === window.PRISM_DASHBOARD_AUTHOR` in
  rendering.py, or extend the status endpoint to accept
  `author=<k>` and read from the author's namespace.
- **In-dashboard "by" subtitle.** v0 surfaces the by-tag on the
  listing tile only. If desired inside the dashboard header
  (between title and subtitle), add a small block in
  `rendering.py` reading `window.PRISM_DASHBOARD_AUTHOR` vs
  `window.PRISM_VIEWER`. ~5 lines.
- **PRISM auto-share on build.** Today PRISM creates dashboards
  with `shared: false` (default). If the user explicitly says
  "build and share", PRISM can set `shared: true` + `shared_at:
  now` directly in the registry entry during Tool 3 -- no API call
  required. The dashboards.md SSoT covers the metadata fields; no
  code change needed in PRISM.

---

## Total budget

| File | Lines added | Lines removed |
|------|-------------|---------------|
| `mysite/news/urls.py` | 2 | 0 |
| `mysite/news/views.py` | ~120 | ~12 (the `dashboards()` body) |
| `mysite/news/templates/news/dashboards.html` | ~6 | ~3 |
| `mysite/news/templates/news/base.html` | ~2 | ~2 |
| **Total** | **~130** | **~17** |

No new files in PRISM. No S3 layout changes. No edits to
`user_manifest.py`, `refresh_runner.py`, `refresh_dashboards.py`,
`_build_exec_namespace`, `_get_prism_users`, `PAGE_ACCESS_RULES`, or
`secondary/sod/prism_users_list.json`. The auth-gap fix and the
examples namespace migration are both opt-in follow-ups.
