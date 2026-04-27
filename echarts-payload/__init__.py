"""
ai_development/dashboards -- ECharts dashboard compiler.

Scope: dashboards only. ``compile_dashboard`` lowers a JSON manifest into
an interactive HTML dashboard. ECharts is NOT the path PRISM uses for
one-off charts in chat / email / report -- that surface lives in Altair
(``ai_development/mcp/utils/chart_functions.py``). The two engines must
not converge: do not surface ``make_echart``, ``EChartResult``,
``ChartSpec``, or any ``make_2pack_*`` / ``make_3pack_*`` /
``make_4pack_*`` / ``make_6pack_*`` symbol from this package as part of
the PRISM-injected runtime namespace; they are internal substrate for
``compile_dashboard``'s lowering pipeline only.

PRISM-bound public surface (what ``execute_analysis_script`` should
inject and what ``dashboards.md`` documents):

    from ai_development.dashboards.echart_dashboard import (
        compile_dashboard,         # JSON manifest -> dashboard HTML + JSON
        validate_manifest,         # dry-run structural validator
        manifest_template,         # strip data -> reusable template
        populate_template,         # template + fresh DataFrames -> manifest
        df_to_source,              # DataFrame -> canonical list-of-lists
        load_manifest,             # JSON path -> manifest dict
        save_manifest,             # manifest dict -> JSON file
    )
    # ``chart_data_diagnostics`` is exposed via the same module for
    # post-compile linting (empty datasets, all-NaN columns, etc.).

Internal-only modules (still drag-and-drop installed, not part of the
public injected surface):

    config.py            brand tokens + theme + palettes + dimensions
    echart_studio.py     single-chart builder (used internally by the
                          dashboard compiler when lowering each
                          ``widget: chart`` in the manifest)
    composites.py        multi-grid layouts (used internally by some
                          dashboard rendering paths)
    rendering.py         editor HTML + dashboard HTML + headless-Chrome
                          PNG export (driven by ``compile_dashboard``)

Design: the manifest.json is the source of truth. ``compile_dashboard``
takes that JSON (dict, path, or JSON string), validates, lowers each
``widget: chart`` through the internal builders, and writes manifest +
interactive HTML to the session folder. Callers never write HTML.

DataFrame contract: PRISM emits Python in ``execute_analysis_script``
that builds DataFrames from real data functions (``pull_market_data``,
``pull_haver_data``, FRED, etc.) and passes them straight into the
manifest datasets. Literal numbers never appear in the JSON emitted by
PRISM. Three accepted shapes for a dataset entry, all normalised to the
same on-disk form by the compiler:

    manifest["datasets"]["rates"] = df_rates                    # shorthand
    manifest["datasets"]["rates"] = {"source": df_rates}        # explicit
    manifest["datasets"]["rates"] = {"source": df_to_source(df_rates)}

Zero runtime deps beyond Python stdlib + pandas for DataFrame
conversion. The emitted HTML loads ECharts from jsdelivr at render time.
"""

from __future__ import annotations

__version__ = "0.3.0"
