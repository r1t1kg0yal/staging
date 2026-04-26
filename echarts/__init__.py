"""
ai_development/dashboards -- self-contained ECharts producer + dashboard compiler.

Public entry points:

    # Single chart  (DataFrame + chart_type + mapping -> option + HTML)
    from echarts.echart_studio import (
        make_echart, wrap_echart, EChartResult,
        validate_option, EChartSpecSheet,
    )

    # JSON-first dashboard compiler  (PRISM's preferred entry)
    from echarts.echart_dashboard import (
        compile_dashboard,
        df_to_source, manifest_template, populate_template,
        load_manifest, validate_manifest, save_manifest,
    )

    # Python builder (optional; useful for notebook / script authoring)
    from echarts.echart_dashboard import (
        Dashboard, DashboardResult,
        ChartRef, KPIRef, TableRef, MarkdownRef, DividerRef,
        GlobalFilter, Link,
        render_dashboard,
    )

    # Multi-grid composites (2pack / 3pack / 4pack / 6pack)
    from echarts.composites import (
        ChartSpec,
        make_2pack_horizontal, make_2pack_vertical,
        make_3pack_triangle, make_4pack_grid, make_6pack_grid,
    )

    # HTML templates + PNG export (all in one module)
    from echarts.rendering import (
        render_editor_html, render_dashboard_html,
        save_chart_png, save_dashboard_pngs, save_dashboard_html_png,
        find_chrome,
    )

    # Style config (edit these dicts to customize look-and-feel globally)
    from echarts.config import (
        THEMES, PALETTES, DIMENSION_PRESETS, TYPOGRAPHY_OVERRIDES,
    )

Layout (after consolidation):

    config.py              brand tokens + 1 theme + 3 palettes + dims
    echart_studio.py       single-chart producer (22 builders + knobs + CLI)
    echart_dashboard.py    dashboard compiler: manifest validator + CLI +
                            Python builder
    composites.py          multi-grid composite layouts
    rendering.py           editor HTML + dashboard HTML + PNG export
    samples.py             chart + dashboard sample registry (test fixtures)
    demos.py               5 end-to-end demo scenarios + CLI + gallery
    tests.py               unit tests + stress tests (interactive +
                            argparse CLI)
    README.md              full reference (chart types, knobs, dashboards,
                            refresh, anti-patterns)
    DATA_SHAPES.md         DataFrame organisation philosophy: tidy vs wide,
                            per-archetype templates, reuse, filter alignment,
                            drill-down patterns
    archive/               legacy files kept for reference

Design: the manifest.json is the source of truth. compile_dashboard() takes
that JSON (dict, path, or JSON string), validates, resolves high-level chart
specs, and emits manifest + interactive HTML to the session folder. Callers
never write HTML.

DataFrame contract: PRISM emits Python in execute_analysis_script that
builds DataFrames from real data functions (pull_market_data, pull_haver_data,
FRED, etc.) and passes them straight into the manifest datasets. Literal
numbers never appear in the JSON emitted by PRISM. Both shapes are accepted:

    manifest["datasets"]["rates"] = df_rates                    # shorthand
    manifest["datasets"]["rates"] = {"source": df_rates}        # explicit
    manifest["datasets"]["rates"] = {"source": df_to_source(df_rates)}  # manual

The compiler normalizes all three into the canonical list-of-lists form
before validation.

Zero runtime deps beyond Python stdlib + pandas for DataFrame conversion.
The emitted HTML loads ECharts from jsdelivr at render time.
"""

from __future__ import annotations

__version__ = "0.3.0"
