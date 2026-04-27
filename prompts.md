# Context-extraction: how dashboard registration works end-to-end

I am curating staging-side `dashboards.md` (the L2 module that teaches you
the build flow). Recent dashboards (`rates_fx_corr`, `bond_carry_roll`)
got registered with their metadata as TOP-LEVEL KEYS in
`dashboards_registry.json` instead of being appended to the `dashboards`
list array, which made the hourly refresh runner skip them and return
404. I need to rewrite Tool 3 in `dashboards.md` so this can't happen
again. Please introspect your own implementation and answer EXACTLY,
in the order below, with verbatim code / signatures / paths. Do not
paraphrase. If a question can't be answered, add a final
`## Could not resolve` section noting what you tried.

Use `list_ai_repo` and `execute_analysis_script` (read files via
`s3_manager.get` or read the on-disk source in `ai_development/`) to
ground every answer in actual code.

---

## 1. The canonical register helper (if one exists)

a. Search `ai_development/` for any function/class whose job is to
   upsert a dashboard entry into `dashboards_registry.json`. Likely
   names: `register_dashboard`, `DashboardRegistry`, `UserDashboardRegistry`,
   `DashboardRegistryManager`, `add_dashboard`, `upsert_dashboard`.
   Report:
   - Full file path (e.g. `ai_development/dashboards/registry.py`)
   - Verbatim signature(s) including type hints and defaults
   - Verbatim docstring(s)
   - Whether it reads-then-writes (full upsert) or assumes the file
     already exists
   - Whether it writes both the registry AND the user manifest, or
     only one of them

b. Is this helper injected into the `execute_analysis_script` sandbox
   namespace? Check the namespace builder (typically
   `ai_development/mcp/utils/` or wherever the sandbox is constructed)
   and report the full namespace dict literal verbatim, plus the names
   I'd actually be able to call from a script-exec tool call today.

c. Is it injected into the dashboard refresh runner's exec namespace
   (`_build_exec_namespace` in `jobs/hourly/refresh_dashboards.py` or
   wherever the runner lives)? Report the namespace dict literal
   verbatim.

## 2. `dashboards_registry.json` schema (verbatim from code)

Find the source of truth (a Pydantic model, dataclass, JSON schema,
constants module, or the registry helper itself) and paste:

a. The TOP-LEVEL shape - all keys, types, defaults. I expect:
   `schema_version`, `owner_kerberos`, `dashboards` (list), `last_updated`.
   Confirm or correct.

b. The PER-DASHBOARD entry shape - every field, type, default, and
   which fields are required vs optional. I expect: `id`, `name`,
   `description`, `created_at`, `last_refreshed`, `last_refresh_status`,
   `refresh_enabled`, `refresh_frequency`, `folder`, `html_path`,
   `data_path`, `tags`, `keep_history`, `history_retention_days`.
   Confirm or correct.

c. Paste a real, currently-live `dashboards_registry.json` for me
   (e.g. `users/goyalr/dashboards/dashboards_registry.json`) verbatim
   so I can see the exact shape after the manual repair.

## 3. `update_user_manifest` / `UserManifestManager`

a. Verbatim signature and docstring of `update_user_manifest` (or
   whatever the public function is). Where does it live?
b. Verbatim signature and docstring of
   `UserManifestManager.update_dashboard_pointer`.
c. When `artifact_type='dashboard'` is passed to `update_user_manifest`,
   does it ALSO upsert into `dashboards_registry.json`, or does it
   ONLY update `users/{kerberos}/manifest.json`'s pointer block? I
   need a clear yes/no, plus the line numbers in source that prove it.

## 4. Empty-registry initialisation

a. If `users/{kerberos}/dashboards/dashboards_registry.json` does not
   exist on S3 when Tool 3 runs, what is supposed to happen? Is there
   a `_load_or_create_registry` style helper? Paste it verbatim.
b. What does the canonical empty-state JSON look like (the seed shape
   written when there are zero dashboards)?

## 5. What you are reading TODAY

a. Read `context/modules/static/dashboards.md` and paste the entire
   "Tool 3 - register" subsection verbatim (it's inside §9.1 Three-
   tool-call build model). Use a fenced code block.
b. Report the file size and last-modified timestamp of that file (so
   I can tell whether the staging copy has been re-shipped recently).
c. Quote any other paragraph in `dashboards.md` that mentions
   "registry", "register", or "dashboards_registry.json" verbatim,
   with section headings.

## 6. The wrong-shape failure mode

Look at `users/goyalr/dashboards/dashboards_registry.json` history
(if you can access prior S3 versions, `s3_manager.list_versions` or
similar). If not, just answer from inspection:

a. What does the BROKEN shape look like - i.e. what code path
   produces `{ "dashboard_id_xxx": {...}, "schema_version": "1.0",
   "dashboards": [...] }` instead of appending into `dashboards[]`?
b. Walk me through which Tool 3 code, if executed naively from
   `dashboards.md`'s current text, would produce that broken shape.
   Paste the exact Python you would write today if I asked you to
   "register the dashboard" with no further hints.

## 7. The end-to-end Tool 3 you would WRITE today

Given everything above, paste the canonical, minimal, copy-pasteable
Python for Tool 3 - the version you wish `dashboards.md` had told you
to run. It should:

- Use the canonical register helper if one exists (call it by name),
- Otherwise hand-roll a load-then-upsert-then-save (read existing
  registry, append/replace by `id` in the `dashboards` list, write
  back) without touching top-level keys,
- Call `update_user_manifest(kerberos, artifact_type='dashboard')`,
- Print the portal URL.

This block becomes the Tool 3 code example I'll add verbatim to
`dashboards.md` §9.1.

---

Reminder: paste exact signatures, exact docstrings, exact dict /
JSON literals, exact file paths. Do not summarise. If something
isn't resolvable, end with a `## Could not resolve` section.