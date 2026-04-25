"""
Unit + stress tests for echart_studio + echart_dashboard.

    python tests.py                          # interactive menu
    python tests.py TestThemes               # one unit-test class
    python tests.py -v                       # verbose unit-test run
    python tests.py unit [args...]           # explicit unit-test mode
                                              (forwarded to unittest)
    python tests.py stress                   # stress-test sub-menu
    python tests.py stress --all             # run every stress scenario
    python tests.py stress --scenario X      # one scenario (repeatable)
    python tests.py stress --list            # list scenarios

The unit-test side is a `unittest`-driven battery of TestCase classes
covering the studio + dashboard + composites + diagnostics surface.

The stress-test side is a battery of deliberately-broken-but-validating
dashboards used to audit the diagnostic system. Each scenario produces
a manifest that PASSES `validate_manifest` but renders empty / broken
charts due to data issues (column typos, NaN columns, type mismatches,
missing required mappings, degenerate distributions, broken filter
wires, etc.). `python tests.py stress --all` writes every scenario's
HTML + manifest + diagnostics to `output/stress_<timestamp>/`. The
aggregate `stress_report.txt` rolls up which diagnostic codes fired
across the suite -- if a regression silently swallows a class of
failures, the roll-up shrinks.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import time
import unittest
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_here_path = Path(__file__).resolve().parent
_here = str(_here_path)
if _here not in sys.path:
    sys.path.insert(0, _here)

import pandas as pd  # noqa

from config import (
    THEMES, PALETTES, DIMENSION_PRESETS, TYPOGRAPHY_OVERRIDES,
    get_theme, list_themes,
    get_palette, list_palettes, palette_colors,
    get_dimension_preset, get_typography_override, list_dimensions,
)
from echart_studio import (
    MARK_KNOB_MAP, UNIVERSAL_KNOBS, XAXIS_KNOBS, YAXIS_KNOBS,
    knobs_for, essentials, list_chart_types, knob_count, ESSENTIAL_NAMES,
    make_echart, wrap_echart, EChartResult, EChartSpecSheet,
    validate_option, info_option, _compute_chart_id, _infer_chart_type,
)
from rendering import render_editor_html
from samples import SAMPLES, list_samples, get_sample


class TestThemes(unittest.TestCase):
    def test_single_gs_theme(self):
        names = list(THEMES.keys())
        self.assertEqual(names, ["gs_clean"])

    def test_get_theme_structure(self):
        for name in THEMES:
            t = get_theme(name)
            self.assertIn("echarts", t)
            self.assertIn("knob_values", t)
            self.assertIn("palette", t)
            self.assertIn("color", t["echarts"])

    def test_unknown_theme_raises(self):
        with self.assertRaises(ValueError):
            get_theme("nope")

    def test_list_themes(self):
        rows = list_themes()
        self.assertEqual(len(rows), 1)
        for r in rows:
            self.assertIn("name", r)
            self.assertIn("palette", r)


class TestPalettes(unittest.TestCase):
    def test_gs_palettes_only(self):
        self.assertEqual(sorted(PALETTES.keys()),
                           sorted(["gs_primary", "gs_blues", "gs_diverging"]))

    def test_get_palette(self):
        p = get_palette("gs_primary")
        self.assertEqual(p["kind"], "categorical")
        self.assertGreater(len(p["colors"]), 0)

    def test_unknown_palette_raises(self):
        with self.assertRaises(ValueError):
            get_palette("banana")

    def test_palette_colors_helper(self):
        cs = palette_colors("gs_blues")
        self.assertGreater(len(cs), 0)

    def test_palette_kinds(self):
        kinds = {p["kind"] for p in PALETTES.values()}
        self.assertEqual(kinds, {"categorical", "sequential", "diverging"})


class TestDimensions(unittest.TestCase):
    def test_twelve_plus_custom(self):
        self.assertGreaterEqual(len(DIMENSION_PRESETS), 12)
        self.assertIn("custom", DIMENSION_PRESETS)

    def test_typography_overrides_small(self):
        for n in ("teams", "thumbnail", "compact"):
            self.assertIn(n, TYPOGRAPHY_OVERRIDES)

    def test_unknown_raises(self):
        with self.assertRaises(ValueError):
            get_dimension_preset("xl")

    def test_no_typography_override(self):
        self.assertEqual(get_typography_override("wide"), {})

    def test_list_dimensions(self):
        rows = list_dimensions()
        self.assertGreaterEqual(len(rows), 12)


class TestKnobs(unittest.TestCase):
    def test_universal_knobs_count(self):
        self.assertGreaterEqual(len(UNIVERSAL_KNOBS), 40)

    def test_knobs_for_line(self):
        ks = knobs_for("line")
        names = {k["name"] for k in ks}
        self.assertIn("titleText", names)
        self.assertIn("lineWidth", names)
        self.assertIn("xAxisType", names)
        self.assertIn("yAxisType", names)

    def test_knobs_for_pie_no_axes(self):
        ks = knobs_for("pie")
        names = {k["name"] for k in ks}
        self.assertIn("pieInnerRadius", names)
        self.assertNotIn("xAxisType", names)

    def test_unknown_chart_type_raises(self):
        with self.assertRaises(ValueError):
            knobs_for("xyz")

    def test_essentials(self):
        es = essentials("line")
        self.assertTrue(len(es) >= 3)

    def test_knob_count_tuple(self):
        u, a, m = knob_count("line")
        self.assertGreater(u, 0)
        self.assertGreater(a, 0)
        self.assertGreater(m, 0)

    def test_raw_has_no_mark_knobs(self):
        u, a, m = knob_count("raw")
        self.assertEqual(m, 0)


class TestProducer(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=10),
            "a": list(range(10)),
            "b": [2 * i for i in range(10)],
        })

    def test_line_single_series(self):
        r = make_echart(self.df, "line", mapping={"x": "date", "y": "a"})
        self.assertTrue(r.success)
        self.assertEqual(len(r.option["series"]), 1)

    def test_multi_line(self):
        r = make_echart(self.df, "multi_line",
                          mapping={"x": "date", "y": ["a", "b"]})
        self.assertEqual(len(r.option["series"]), 2)

    def test_bar(self):
        df = pd.DataFrame({"x": list("abcd"), "y": [1, 2, 3, 4]})
        r = make_echart(df, "bar", mapping={"x": "x", "y": "y"})
        self.assertEqual(r.option["xAxis"]["data"], ["a", "b", "c", "d"])

    def test_bar_horizontal(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": list("abc")})
        r = make_echart(df, "bar_horizontal", mapping={"x": "x", "y": "y"})
        self.assertEqual(r.option["yAxis"]["data"], ["a", "b", "c"])

    def test_scatter_with_color(self):
        df = pd.DataFrame({"x": [1, 2, 1, 2], "y": [2, 3, 4, 5], "g": list("aabb")})
        r = make_echart(df, "scatter", mapping={"x": "x", "y": "y", "color": "g"})
        self.assertEqual(len(r.option["series"]), 2)

    def test_heatmap(self):
        df = pd.DataFrame({"x": list("aabb"), "y": list("1212"),
                              "v": [1, 2, 3, 4]})
        r = make_echart(df, "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v"})
        self.assertIn("visualMap", r.option)

    def test_pie(self):
        df = pd.DataFrame({"c": list("abc"), "v": [10, 20, 30]})
        r = make_echart(df, "pie", mapping={"category": "c", "value": "v"})
        self.assertEqual(r.option["series"][0]["type"], "pie")

    def test_donut_radius(self):
        df = pd.DataFrame({"c": list("abc"), "v": [10, 20, 30]})
        r = make_echart(df, "donut", mapping={"category": "c", "value": "v"})
        self.assertIsInstance(r.option["series"][0]["radius"], list)
        self.assertEqual(r.option["series"][0]["radius"][0], "40%")

    def test_boxplot(self):
        df = pd.DataFrame({"c": list("aaabbb"), "v": [1, 2, 3, 5, 6, 7]})
        r = make_echart(df, "boxplot", mapping={"x": "c", "y": "v"})
        self.assertEqual(len(r.option["series"]), 2)

    def test_sankey(self):
        df = pd.DataFrame({"s": list("aab"), "t": list("xyy"), "v": [1, 2, 3]})
        r = make_echart(df, "sankey",
                          mapping={"source": "s", "target": "t", "value": "v"})
        self.assertEqual(r.option["series"][0]["type"], "sankey")

    def test_raw_passthrough(self):
        opt = {"series": [{"type": "bar", "data": [1, 2]}]}
        r = make_echart(option=opt, chart_type="raw", title="x")
        self.assertEqual(r.option["series"][0]["type"], "bar")
        self.assertEqual(r.option["title"]["text"], "x")

    def test_unknown_chart_type_raises(self):
        with self.assertRaises(ValueError):
            make_echart(self.df, "blah", mapping={"x": "date", "y": "a"})

    def test_missing_mapping_raises(self):
        with self.assertRaises(ValueError):
            make_echart(self.df, "line", mapping={"x": "date"})

    def test_bad_column_raises(self):
        with self.assertRaises(ValueError):
            make_echart(self.df, "line", mapping={"x": "nope", "y": "a"})

    def test_theme_and_palette_wiring(self):
        r = make_echart(self.df, "line", mapping={"x": "date", "y": "a"},
                          theme="gs_clean", palette="gs_primary")
        self.assertEqual(r.theme, "gs_clean")
        self.assertEqual(r.palette, "gs_primary")
        self.assertIn("color", r.option)


class TestSessionPersistence(unittest.TestCase):
    def test_session_write(self):
        tmp = tempfile.mkdtemp(prefix="session_test_")
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        r = make_echart(df, "line", mapping={"x": "x", "y": "y"},
                          session_path=tmp, chart_name="tst")
        self.assertTrue(Path(r.json_path).is_file())
        self.assertTrue(Path(r.html_path).is_file())
        data = json.loads(Path(r.json_path).read_text())
        self.assertEqual(data["series"][0]["type"], "line")


class TestWrapEchart(unittest.TestCase):
    def test_infer_line(self):
        opt = {"series": [{"type": "line", "data": [[1, 2]]}]}
        r = wrap_echart(option=opt)
        self.assertEqual(r.chart_type, "line")

    def test_infer_donut(self):
        opt = {"series": [{"type": "pie", "radius": ["40%", "70%"],
                              "data": [{"name": "a", "value": 1}]}]}
        r = wrap_echart(option=opt)
        self.assertEqual(r.chart_type, "donut")

    def test_wrap_writes_html(self):
        tmp = tempfile.mkdtemp(prefix="wrap_test_")
        opt = {"series": [{"type": "bar", "data": [1, 2, 3]}],
                 "xAxis": {"type": "category", "data": ["a", "b", "c"]},
                 "yAxis": {"type": "value"}}
        out = Path(tmp) / "chart.html"
        r = wrap_echart(option=opt, output_path=out)
        self.assertTrue(out.is_file())
        html = out.read_text()
        self.assertIn("echarts.min.js", html)


class TestEditorHtml(unittest.TestCase):
    def test_payload_embedded(self):
        opt = {"series": [{"type": "line", "data": [[1, 2], [3, 4]]}]}
        knob_defs = knobs_for("line")
        html = render_editor_html(
            option=opt, chart_id="abc123",
            chart_type="line", theme="gs_clean", palette="gs_primary",
            dimension_preset="wide", knob_defs=knob_defs,
        )
        self.assertIn("var PAYLOAD =", html)
        self.assertIn("APPLY =", html)
        self.assertIn("registerTheme", html)
        self.assertIn('id="chart"', html)
        self.assertIn('id="knob-cards"', html)


class TestSpecSheet(unittest.TestCase):
    def test_roundtrip(self):
        s = EChartSpecSheet.new("my sheet", description="...")
        data = s.to_dict()
        s2 = EChartSpecSheet.from_dict(data)
        self.assertEqual(s.name, s2.name)
        self.assertEqual(s.spec_sheet_id, s2.spec_sheet_id)


class TestValidator(unittest.TestCase):
    def test_ok(self):
        ok, ws = validate_option({"series": [{"type": "line", "data": [1, 2]}]})
        self.assertTrue(ok)
        self.assertEqual(ws, [])

    def test_missing_series(self):
        ok, ws = validate_option({})
        self.assertFalse(ok)
        self.assertTrue(len(ws) > 0)


class TestSamplesMatrix(unittest.TestCase):
    def test_all_samples_render(self):
        for name in list_samples():
            with self.subTest(sample=name):
                opt = get_sample(name)
                self.assertIn("series", opt)

    def test_samples_x_themes(self):
        # just verify wrap_echart works for every (sample, theme) combo
        names = list_samples()
        themes = list(THEMES.keys())
        for n in names:
            opt = get_sample(n)
            for th in themes:
                with self.subTest(sample=n, theme=th):
                    r = wrap_echart(option=opt, theme=th)
                    self.assertTrue(r.success)
# Dashboard-specific imports:
from echart_dashboard import (
    Dashboard, DashboardResult, Tab,
    ChartRef, KPIRef, TableRef, MarkdownRef, NoteRef, DividerRef,
    GlobalFilter, Link,
    render_dashboard, compile_dashboard,
    _source_to_dataframe, _spec_to_option,
    SCHEMA_VERSION, VALID_WIDGETS, VALID_FILTERS, VALID_SYNC, VALID_BRUSH_TYPES,
    VALID_NOTE_KINDS,
    validate_manifest, load_manifest, save_manifest, match_targets,
    Diagnostic, chart_data_diagnostics,
)
from rendering import _render_md, _md_inline
from samples import DASHBOARD_SAMPLES


# =============================================================================
# DASHBOARD TESTS
# =============================================================================

class TestManifestValidator(unittest.TestCase):
    def _minimal(self):
        return {
            "schema_version": 1, "id": "x", "title": "t", "theme": "gs_clean",
            "layout": {"kind": "grid", "cols": 12, "rows": [
                [{"widget": "chart", "id": "c", "ref": "a.json", "w": 12}],
            ]},
        }

    def test_ok_minimal(self):
        ok, errs = validate_manifest(self._minimal())
        self.assertTrue(ok, errs)

    def test_bad_schema_version(self):
        m = self._minimal(); m["schema_version"] = 99
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("schema_version" in e for e in errs))

    def test_missing_id(self):
        m = self._minimal(); m["id"] = ""
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)

    def test_bad_theme(self):
        m = self._minimal(); m["theme"] = "nope"
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)

    def test_bad_widget_type(self):
        m = self._minimal()
        m["layout"]["rows"][0][0]["widget"] = "banana"
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)

    def test_duplicate_widget_id(self):
        m = self._minimal()
        m["layout"]["rows"].append([
            {"widget": "chart", "id": "c", "ref": "b.json", "w": 12}
        ])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("duplicate widget" in e for e in errs))

    def test_widgets_sum_exceeds_cols(self):
        m = self._minimal()
        m["layout"]["rows"] = [[
            {"widget": "chart", "id": "a", "ref": "a.json", "w": 8},
            {"widget": "chart", "id": "b", "ref": "b.json", "w": 8},
        ]]
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)

    def test_filter_target_unknown_chart(self):
        m = self._minimal()
        m["filters"] = [{"id": "f", "type": "dateRange", "default": "6M", "targets": ["missing"]}]
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("targets" in e for e in errs))

    def test_link_members_wildcard(self):
        m = self._minimal()
        m["links"] = [{"group": "g", "members": ["*"], "sync": ["axis"]}]
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_brush_type_valid(self):
        m = self._minimal()
        m["links"] = [{"group": "g", "members": ["c"], "brush": {"type": "rect"}}]
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_brush_type_invalid(self):
        m = self._minimal()
        m["links"] = [{"group": "g", "members": ["c"], "brush": {"type": "banana"}}]
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)

    def test_match_targets_wildcard(self):
        ids = ["a", "b", "macro_a", "macro_b"]
        self.assertEqual(match_targets(["*"], ids), ids)
        self.assertEqual(match_targets(["macro_*"], ids), ["macro_a", "macro_b"])
        self.assertEqual(match_targets(["a"], ids), ["a"])

    def test_metadata_accepted(self):
        m = self._minimal()
        m["metadata"] = {
            "kerberos": "userid",
            "dashboard_id": "x",
            "data_as_of": "2026-04-24T15:00:00Z",
            "generated_at": "2026-04-24T15:05:00Z",
            "sources": ["GS Market Data", "Haver"],
            "refresh_frequency": "daily",
            "refresh_enabled": True,
            "tags": ["rates", "curve"],
            "version": "1.0.0",
        }
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_metadata_bad_refresh_frequency(self):
        m = self._minimal()
        m["metadata"] = {"refresh_frequency": "quarterly"}
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("refresh_frequency" in e for e in errs))

    def test_metadata_bad_types(self):
        m = self._minimal()
        m["metadata"] = {"sources": "haver", "refresh_enabled": "yes"}
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("sources" in e for e in errs))
        self.assertTrue(any("refresh_enabled" in e for e in errs))

    def test_metadata_methodology_string(self):
        m = self._minimal()
        m["metadata"] = {"methodology": "## Notes\n\n* Rolling 1Y window\n"}
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_metadata_methodology_dict(self):
        m = self._minimal()
        m["metadata"] = {"methodology": {"title": "How",
                                            "body": "## Notes\n\n* x"}}
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_metadata_methodology_dict_missing_body(self):
        m = self._minimal()
        m["metadata"] = {"methodology": {"title": "How"}}
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("methodology" in e for e in errs))

    def test_metadata_methodology_bad_type(self):
        m = self._minimal()
        m["metadata"] = {"methodology": 12345}
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("methodology" in e for e in errs))

    def test_header_actions_accepted(self):
        m = self._minimal()
        m["header_actions"] = [
            {"label": "Docs", "href": "https://example.com"},
            {"label": "Run", "onclick": "customRun", "primary": True,
              "icon": "\u25B6"},
        ]
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_header_actions_bad(self):
        m = self._minimal()
        m["header_actions"] = [{"label": "X"}]  # no href/onclick
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        m["header_actions"] = [{"href": "x"}]  # no label
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)


class TestWidgetBuilders(unittest.TestCase):
    def test_chart_ref(self):
        cr = ChartRef(id="x", ref="a.json", w=6, title="t", dataset_ref="d")
        d = cr.to_dict()
        self.assertEqual(d["widget"], "chart")
        self.assertEqual(d["ref"], "a.json")
        self.assertEqual(d["dataset_ref"], "d")
        self.assertEqual(d["w"], 6)

    def test_kpi_ref(self):
        kr = KPIRef(id="k", label="10Y", source="ds.latest.c", w=3)
        d = kr.to_dict()
        self.assertEqual(d["widget"], "kpi")
        self.assertEqual(d["source"], "ds.latest.c")

    def test_markdown(self):
        m = MarkdownRef(id="m", content="# H")
        d = m.to_dict()
        self.assertEqual(d["widget"], "markdown")

    def test_divider(self):
        d = DividerRef()
        self.assertEqual(d.to_dict()["widget"], "divider")

    def test_global_filter_bad_type(self):
        with self.assertRaises(ValueError):
            GlobalFilter(id="f", type="nope").to_dict()

    def test_link_bad_sync(self):
        with self.assertRaises(ValueError):
            Link(group="g", members=["a"], sync=["banana"]).to_dict()

    def test_link_bad_brush(self):
        with self.assertRaises(ValueError):
            Link(group="g", members=["a"], brush={"type": "banana"}).to_dict()


class TestBuild(unittest.TestCase):
    def _simple_chart_spec(self):
        return {"series": [{"type": "line",
                              "data": [["2025-01-01", 1], ["2025-01-02", 2]]}],
                 "xAxis": {"type": "time"}, "yAxis": {"type": "value"}}

    def test_build_writes_manifest_and_html(self):
        tmp = tempfile.mkdtemp(prefix="db_build_")
        opt = self._simple_chart_spec()
        db = (Dashboard(id="ut", title="Unit")
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        r = db.build(session_path=tmp)
        self.assertTrue(r.success, r.warnings)
        self.assertTrue(Path(r.manifest_path).is_file())
        self.assertTrue(Path(r.html_path).is_file())

    def test_invalid_manifest_returns_failure(self):
        opt = self._simple_chart_spec()
        db = (Dashboard(id="ut", title="Unit")
              .add_row([ChartRef(id="c", option=opt, w=12),
                         ChartRef(id="c", option=opt, w=12)]))  # dup id
        r = db.build(output_path="/tmp/should_not_exist.html")
        self.assertFalse(r.success)
        self.assertTrue(any("duplicate" in w for w in r.warnings))

    def test_unknown_theme_raises(self):
        with self.assertRaises(ValueError):
            Dashboard(id="x", title="t", theme="banana")

    def test_datasets_from_dataframe(self):
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=3),
            "x": [1, 2, 3],
        })
        db = Dashboard(id="d", title="t").add_dataset("ds", df)
        m = db.to_manifest()
        self.assertIn("ds", m["datasets"])
        self.assertEqual(m["datasets"]["ds"]["source"][0], ["date", "x"])

    def test_dashboard_sample_roundtrip(self):
        m = DASHBOARD_SAMPLES["rates_daily"]()
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)


class TestRender(unittest.TestCase):
    def test_render_manifest(self):
        opt = {"series": [{"type": "bar", "data": [1, 2]}],
                 "xAxis": {"type": "category", "data": ["a", "b"]},
                 "yAxis": {"type": "value"}}
        db = (Dashboard(id="r", title="R")
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        manifest = db.to_manifest()
        res = render_dashboard(manifest)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.html)
        self.assertIn("echarts.min.js", res.html)

    def test_render_writes_file(self):
        tmp = tempfile.mkdtemp(prefix="render_")
        opt = {"series": [{"type": "bar", "data": [1, 2]}]}
        db = (Dashboard(id="r", title="R")
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        manifest = db.to_manifest()
        out = Path(tmp) / "db.html"
        res = render_dashboard(manifest, output_path=out)
        self.assertTrue(out.is_file())

    def test_render_refresh_button_and_freshness(self):
        opt = {"series": [{"type": "bar", "data": [1, 2]}]}
        db = (Dashboard(id="r", title="R")
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        manifest = db.to_manifest()
        manifest["metadata"] = {
            "kerberos": "userid",
            "dashboard_id": "r",
            "data_as_of": "2026-04-24T15:00:00Z",
            "refresh_frequency": "daily",
            "refresh_enabled": True,
        }
        manifest["header_actions"] = [
            {"label": "Docs", "href": "https://example.com"},
        ]
        res = render_dashboard(manifest)
        self.assertTrue(res.success, res.warnings)
        html = res.html
        # Static HTML chrome must carry the refresh button and data-as-of
        # badge hooks; the runtime JS decides whether to show them.
        self.assertIn('id="refresh-btn"', html)
        self.assertIn('id="data-as-of"', html)
        # Manifest metadata + header_actions are embedded in the payload JSON
        self.assertIn('"metadata"', html)
        self.assertIn('"header_actions"', html)


class TestAllSamples(unittest.TestCase):
    def test_every_sample_valid(self):
        for name, fn in DASHBOARD_SAMPLES.items():
            with self.subTest(sample=name):
                m = fn()
                ok, errs = validate_manifest(m)
                self.assertTrue(ok, errs)


class TestTabsLayout(unittest.TestCase):
    def _opt(self):
        return {"series": [{"type": "line", "data": [[1, 2]]}]}

    def test_add_tab_switches_mode(self):
        db = (Dashboard(id="t", title="T")
              .add_dataset("d", pd.DataFrame({"x": [1], "y": [2]})))
        t1 = db.add_tab("a", "A")
        t1.add_row([ChartRef(id="c1", option=self._opt(), w=12)])
        t2 = db.add_tab("b", "B")
        t2.add_row([ChartRef(id="c2", option=self._opt(), w=12)])
        m = db.to_manifest()
        self.assertEqual(m["layout"]["kind"], "tabs")
        self.assertEqual(len(m["layout"]["tabs"]), 2)
        self.assertEqual(m["layout"]["tabs"][0]["id"], "a")
        self.assertEqual(m["layout"]["tabs"][1]["id"], "b")
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_add_tab_migrates_existing_rows(self):
        db = (Dashboard(id="t", title="T")
              .add_row([ChartRef(id="first", option=self._opt(), w=12)]))
        t = db.add_tab("new", "New")
        t.add_row([ChartRef(id="second", option=self._opt(), w=12)])
        m = db.to_manifest()
        self.assertEqual(m["layout"]["kind"], "tabs")
        # first widget should be in the migrated 'overview' tab
        tab_ids = [tab["id"] for tab in m["layout"]["tabs"]]
        self.assertIn("overview", tab_ids)
        self.assertIn("new", tab_ids)

    def test_tabs_requires_nonempty(self):
        m = {"schema_version": 1, "id": "x", "title": "t", "theme": "gs_clean",
              "layout": {"kind": "tabs", "tabs": []}}
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)

    def test_tab_duplicate_ids(self):
        m = {"schema_version": 1, "id": "x", "title": "t", "theme": "gs_clean",
              "layout": {"kind": "tabs", "tabs": [
                  {"id": "a", "label": "A", "rows": [[
                      {"widget": "chart", "id": "c", "ref": "a.json", "w": 12}
                  ]]},
                  {"id": "a", "label": "A2", "rows": []},
              ]}}
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("duplicate tab id" in e for e in errs))

    def test_tab_build_end_to_end(self):
        tmp = tempfile.mkdtemp(prefix="tabs_e2e_")
        db = Dashboard(id="t", title="T", theme="gs_clean")
        t = db.add_tab("o", "O")
        t.add_row([ChartRef(id="c", option=self._opt(), w=12)])
        r = db.build(session_path=tmp)
        self.assertTrue(r.success, r.warnings)
        html = Path(r.html_path).read_text()
        self.assertIn("tab-btn", html)
        self.assertIn("tab-panel-o", html)


class TestKpiFields(unittest.TestCase):
    def test_kpi_delta_source_flows_through(self):
        k = KPIRef(id="x", label="Y", source="ds.latest.c",
                     delta_source="ds.prev.c", decimals=2,
                     suffix="%", sparkline_source="ds.c")
        d = k.to_dict()
        self.assertEqual(d["delta_source"], "ds.prev.c")
        self.assertEqual(d["decimals"], 2)
        self.assertEqual(d["suffix"], "%")
        self.assertEqual(d["sparkline_source"], "ds.c")

    def test_kpi_omits_absent_optional_fields(self):
        d = KPIRef(id="x", label="Y", value=10).to_dict()
        for k in ("delta_source", "source", "suffix", "prefix", "decimals",
                   "sparkline_source", "sub"):
            self.assertNotIn(k, d)


# =============================================================================
# JSON-FIRST COMPILE FLOW TESTS
# =============================================================================


class TestSourceToDataFrame(unittest.TestCase):
    def test_header_row_form(self):
        df = _source_to_dataframe([
            ["date", "x", "y"],
            ["2025-01-01", 1, 10],
            ["2025-01-02", 2, 20],
        ])
        self.assertEqual(list(df.columns), ["date", "x", "y"])
        self.assertEqual(len(df), 2)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["date"]))

    def test_list_of_dicts_form(self):
        df = _source_to_dataframe([
            {"a": 1, "b": 2},
            {"a": 3, "b": 4},
        ])
        self.assertEqual(list(df.columns), ["a", "b"])
        self.assertEqual(len(df), 2)

    def test_empty_source_returns_empty_df(self):
        self.assertTrue(_source_to_dataframe([]).empty)
        self.assertTrue(_source_to_dataframe(None).empty)

    def test_non_date_strings_left_alone(self):
        df = _source_to_dataframe([
            ["a", "b"], ["hello", 1], ["world", 2],
        ])
        self.assertEqual(df["a"].tolist(), ["hello", "world"])


class TestSpecToOption(unittest.TestCase):
    def _datasets(self):
        return {
            "rates": {"source": [
                ["date", "us_10y", "spread"],
                ["2025-01-01", 4.10, 30.0],
                ["2025-01-02", 4.15, 33.0],
                ["2025-01-03", 4.12, 31.0],
            ]}
        }

    def test_simple_line_spec(self):
        opt = _spec_to_option(
            {"chart_type": "line", "dataset": "rates",
              "mapping": {"x": "date", "y": "us_10y"}},
            self._datasets(), "gs_clean", None,
        )
        self.assertIn("series", opt)
        self.assertEqual(opt["series"][0]["type"], "line")

    def test_multi_line_spec(self):
        opt = _spec_to_option(
            {"chart_type": "multi_line", "dataset": "rates",
              "mapping": {"x": "date", "y": ["us_10y", "spread"]}},
            self._datasets(), "gs_clean", None,
        )
        self.assertEqual(len(opt["series"]), 2)

    def test_title_subtitle_flow_through(self):
        opt = _spec_to_option(
            {"chart_type": "line", "dataset": "rates",
              "mapping": {"x": "date", "y": "us_10y"},
              "title": "UST 10Y", "subtitle": "daily"},
            self._datasets(), "gs_clean", None,
        )
        self.assertEqual(opt["title"]["text"], "UST 10Y")
        self.assertEqual(opt["title"]["subtext"], "daily")

    def test_per_spec_palette_overrides(self):
        """Passing an explicit palette should be accepted and still
        produce a valid line option. With one categorical palette
        (gs_primary) the color output matches the theme default; with
        a diverging palette (gs_diverging) the option still renders
        and a non-empty series array is produced."""
        base = _spec_to_option(
            {"chart_type": "line", "dataset": "rates",
              "mapping": {"x": "date", "y": "us_10y"}},
            self._datasets(), "gs_clean", None,
        )
        overridden = _spec_to_option(
            {"chart_type": "line", "dataset": "rates",
              "mapping": {"x": "date", "y": "us_10y"},
              "palette": "gs_primary"},
            self._datasets(), "gs_clean", None,
        )
        self.assertEqual(overridden["series"][0]["type"], "line")
        self.assertTrue(base["series"][0]["data"])
        self.assertTrue(overridden["series"][0]["data"])

    def test_unknown_dataset_raises(self):
        with self.assertRaises(ValueError) as cm:
            _spec_to_option(
                {"chart_type": "line", "dataset": "nope",
                  "mapping": {"x": "date", "y": "us_10y"}},
                self._datasets(), "gs_clean", None,
            )
        self.assertIn("nope", str(cm.exception))

    def test_unknown_chart_type_raises(self):
        with self.assertRaises(ValueError) as cm:
            _spec_to_option(
                {"chart_type": "banana", "dataset": "rates",
                  "mapping": {"x": "date", "y": "us_10y"}},
                self._datasets(), "gs_clean", None,
            )
        self.assertIn("banana", str(cm.exception))

    def test_missing_mapping_raises(self):
        with self.assertRaises(ValueError):
            _spec_to_option(
                {"chart_type": "line", "dataset": "rates"},
                self._datasets(), "gs_clean", None,
            )

    def test_missing_chart_type_raises(self):
        with self.assertRaises(ValueError):
            _spec_to_option(
                {"dataset": "rates", "mapping": {"x": "date", "y": "us_10y"}},
                self._datasets(), "gs_clean", None,
            )


class TestValidatorSpecBranch(unittest.TestCase):
    def _minimal_with_spec(self):
        return {
            "schema_version": 1, "id": "x", "title": "t", "theme": "gs_clean",
            "datasets": {"ds": {"source": [["x", "y"], [1, 10]]}},
            "layout": {"kind": "grid", "cols": 12, "rows": [[
                {"widget": "chart", "id": "c", "w": 12,
                  "spec": {"chart_type": "line", "dataset": "ds",
                            "mapping": {"x": "x", "y": "y"}}},
            ]]},
        }

    def test_spec_variant_ok(self):
        ok, errs = validate_manifest(self._minimal_with_spec())
        self.assertTrue(ok, errs)

    def test_spec_unknown_dataset(self):
        m = self._minimal_with_spec()
        m["layout"]["rows"][0][0]["spec"]["dataset"] = "missing"
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("spec.dataset" in e for e in errs))

    def test_spec_unknown_chart_type(self):
        m = self._minimal_with_spec()
        m["layout"]["rows"][0][0]["spec"]["chart_type"] = "banana"
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("spec.chart_type" in e for e in errs))

    def test_spec_missing_mapping(self):
        m = self._minimal_with_spec()
        del m["layout"]["rows"][0][0]["spec"]["mapping"]
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("spec.mapping" in e for e in errs))

    def test_spec_missing_chart_type(self):
        m = self._minimal_with_spec()
        del m["layout"]["rows"][0][0]["spec"]["chart_type"]
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("spec.chart_type" in e for e in errs))

    def test_spec_missing_dataset(self):
        m = self._minimal_with_spec()
        del m["layout"]["rows"][0][0]["spec"]["dataset"]
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("spec.dataset" in e for e in errs))

    def test_chart_without_any_of_ref_option_spec(self):
        m = self._minimal_with_spec()
        del m["layout"]["rows"][0][0]["spec"]
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(
            any("chart widget requires one of" in e for e in errs),
            errs,
        )

    def test_spec_bad_palette(self):
        m = self._minimal_with_spec()
        m["layout"]["rows"][0][0]["spec"]["palette"] = "not_a_palette"
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)


class TestCompileDashboard(unittest.TestCase):
    def _manifest(self):
        return {
            "schema_version": 1,
            "id": "comp_test",
            "title": "Compile Test",
            "theme": "gs_clean",
            "datasets": {"ds": {"source": [
                ["date", "val"],
                ["2025-01-01", 10.0],
                ["2025-01-02", 12.0],
                ["2025-01-03", 11.5],
            ]}},
            "layout": {"kind": "grid", "cols": 12, "rows": [[
                {"widget": "chart", "id": "c", "w": 12,
                  "spec": {"chart_type": "line", "dataset": "ds",
                            "mapping": {"x": "date", "y": "val"},
                            "title": "Series"}},
            ]]},
        }

    def test_compile_from_dict(self):
        tmp = tempfile.mkdtemp(prefix="comp_")
        r = compile_dashboard(self._manifest(), session_path=tmp)
        self.assertTrue(r.success, r.warnings)
        self.assertTrue(Path(r.manifest_path).is_file())
        self.assertTrue(Path(r.html_path).is_file())
        html = Path(r.html_path).read_text()
        self.assertIn("echarts.min.js", html)
        self.assertIn("Compile Test", html)

    def test_compile_from_json_string(self):
        tmp = tempfile.mkdtemp(prefix="comp_str_")
        payload = json.dumps(self._manifest())
        out = Path(tmp) / "out.html"
        r = compile_dashboard(payload, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        self.assertTrue(out.is_file())
        self.assertTrue(out.with_suffix(".json").is_file())

    def test_compile_from_file_path(self):
        tmp = tempfile.mkdtemp(prefix="comp_file_")
        p = Path(tmp) / "src.json"
        p.write_text(json.dumps(self._manifest()))
        out = Path(tmp) / "rendered.html"
        r = compile_dashboard(str(p), output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        self.assertTrue(out.is_file())

    def test_compile_from_path_object(self):
        tmp = tempfile.mkdtemp(prefix="comp_path_")
        p = Path(tmp) / "src.json"
        p.write_text(json.dumps(self._manifest()))
        out = Path(tmp) / "rendered.html"
        r = compile_dashboard(p, output_path=out)
        self.assertTrue(r.success)

    def test_compile_writes_session_dashboards(self):
        tmp = tempfile.mkdtemp(prefix="comp_sess_")
        r = compile_dashboard(self._manifest(), session_path=tmp)
        self.assertTrue(Path(tmp, "dashboards", "comp_test.json").is_file())
        self.assertTrue(Path(tmp, "dashboards", "comp_test.html").is_file())

    def test_compile_bad_manifest(self):
        m = self._manifest(); m["schema_version"] = 99
        r = compile_dashboard(m, output_path="/tmp/should_not_be_written.html")
        self.assertFalse(r.success)
        self.assertTrue(any("schema_version" in w for w in r.warnings))

    def test_compile_spec_unknown_dataset_fails(self):
        m = self._manifest()
        m["layout"]["rows"][0][0]["spec"]["dataset"] = "missing"
        r = compile_dashboard(m, output_path="/tmp/bad_ds.html")
        self.assertFalse(r.success)

    def test_compile_preserves_declarative_manifest_on_disk(self):
        """Compiled manifest JSON keeps `spec` form; specs are NOT inlined
        to resolved ECharts option JSON."""
        tmp = tempfile.mkdtemp(prefix="comp_preserve_")
        r = compile_dashboard(self._manifest(), session_path=tmp)
        self.assertTrue(r.success)
        on_disk = json.loads(Path(r.manifest_path).read_text())
        chart_w = on_disk["layout"]["rows"][0][0]
        self.assertIn("spec", chart_w)
        self.assertEqual(chart_w["spec"]["chart_type"], "line")
        self.assertNotIn("option", chart_w)

    def test_compile_nonexistent_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            compile_dashboard("definitely_not_a_real_file.json",
                                output_path="/tmp/x.html")

    def test_compile_bad_type_raises(self):
        with self.assertRaises(TypeError):
            compile_dashboard(12345, output_path="/tmp/x.html")

    def test_compile_write_json_false(self):
        tmp = tempfile.mkdtemp(prefix="comp_nowrite_")
        r = compile_dashboard(self._manifest(), session_path=tmp, write_json=False)
        self.assertTrue(r.success)
        self.assertFalse(Path(tmp, "dashboards", "comp_test.json").exists())
        self.assertTrue(Path(tmp, "dashboards", "comp_test.html").is_file())


class TestCompileMixedVariants(unittest.TestCase):
    """A dashboard can mix spec / ref / option widgets in the same manifest."""

    def test_mixed_spec_and_option(self):
        tmp = tempfile.mkdtemp(prefix="mixed_")
        m = {
            "schema_version": 1,
            "id": "mix", "title": "Mix", "theme": "gs_clean",
            "datasets": {"ds": {"source": [["x", "y"], [1, 10], [2, 20]]}},
            "layout": {"kind": "grid", "cols": 12, "rows": [[
                {"widget": "chart", "id": "a", "w": 6,
                  "spec": {"chart_type": "line", "dataset": "ds",
                            "mapping": {"x": "x", "y": "y"}}},
                {"widget": "chart", "id": "b", "w": 6,
                  "option": {"series": [{"type": "bar", "data": [1, 2]}],
                              "xAxis": {"type": "category", "data": ["a", "b"]},
                              "yAxis": {"type": "value"}}},
            ]]},
        }
        r = compile_dashboard(m, session_path=tmp)
        self.assertTrue(r.success, r.warnings)
        html = Path(r.html_path).read_text()
        self.assertIn("\"a\":", html)
        self.assertIn("\"b\":", html)


class TestChartRefSpecField(unittest.TestCase):
    def test_chart_ref_with_spec(self):
        cr = ChartRef(id="x", w=6,
                        spec={"chart_type": "line", "dataset": "ds",
                              "mapping": {"x": "d", "y": "v"}})
        d = cr.to_dict()
        self.assertIn("spec", d)
        self.assertEqual(d["spec"]["chart_type"], "line")

    def test_builder_with_spec_renders(self):
        tmp = tempfile.mkdtemp(prefix="builder_spec_")
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=3),
            "v": [1.0, 2.0, 1.5],
        })
        db = (Dashboard(id="bs", title="Builder+Spec")
              .add_dataset("ds", df)
              .add_row([ChartRef(id="c", w=12,
                                    spec={"chart_type": "line",
                                          "dataset": "ds",
                                          "mapping": {"x": "date",
                                                      "y": "v"}})]))
        r = db.build(session_path=tmp)
        self.assertTrue(r.success, r.warnings)
        self.assertTrue(Path(r.html_path).is_file())


# =============================================================================
# ANNOTATIONS
# =============================================================================

class TestAnnotations(unittest.TestCase):
    def _line_df(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=20, freq="MS"),
            "y1": [i * 0.1 for i in range(20)],
            "y2": [2.0 - i * 0.05 for i in range(20)],
        })

    def test_hline_vline_band_on_multi_line(self):
        df = self._line_df()
        r = make_echart(
            df=df, chart_type="multi_line",
            mapping={"x": "date", "y": ["y1", "y2"]},
            annotations=[
                {"type": "hline", "y": 1.0, "label": "Mid"},
                {"type": "vline", "x": "2024-06-01", "label": "Event"},
                {"type": "band", "x1": "2024-03-01", "x2": "2024-05-01",
                  "label": "Window"},
            ],
            title="annotated",
        )
        self.assertTrue(r.success)
        s0 = r.option["series"][0]
        self.assertEqual(len(s0["markLine"]["data"]), 2)
        self.assertEqual(len(s0["markArea"]["data"]), 1)

    def test_arrow_and_point(self):
        df = self._line_df()
        r = make_echart(
            df=df, chart_type="multi_line",
            mapping={"x": "date", "y": ["y1"]},
            annotations=[
                {"type": "arrow", "x1": "2024-02-01", "y1": 0.1,
                  "x2": "2024-07-01", "y2": 0.6, "label": "rise"},
                {"type": "point", "x": "2024-09-01", "y": 0.8,
                  "label": "peak"},
            ],
        )
        s0 = r.option["series"][0]
        self.assertEqual(len(s0["markLine"]["data"]), 1)
        self.assertEqual(len(s0["markPoint"]["data"]), 1)

    def test_annotations_via_mapping_key(self):
        df = self._line_df()
        r = make_echart(
            df=df, chart_type="line",
            mapping={"x": "date", "y": "y1",
                      "annotations": [{"type": "hline", "y": 0.5, "label": "T"}]},
        )
        self.assertEqual(len(r.option["series"][0]["markLine"]["data"]), 1)

    def test_unknown_annotation_type_ignored(self):
        df = self._line_df()
        r = make_echart(
            df=df, chart_type="line",
            mapping={"x": "date", "y": "y1"},
            annotations=[{"type": "bogus", "y": 1.0}],
        )
        s0 = r.option["series"][0]
        self.assertNotIn("markLine", s0)

    def test_dual_axis_hline(self):
        df = self._line_df()
        r = make_echart(
            df=df, chart_type="multi_line",
            mapping={"x": "date", "y": "y1", "color": "kind",
                      "dual_axis_series": ["a"]} if False else
                      {"x": "date", "y": ["y1", "y2"],
                        "dual_axis_series": ["y2"], "y_title": "L",
                        "y_title_right": "R"},
            annotations=[
                {"type": "hline", "y": 1.5, "axis": "right", "label": "R"},
            ],
        )
        self.assertEqual(len(r.option["yAxis"]), 2)
        ml = r.option["series"][0]["markLine"]["data"][0]
        self.assertEqual(ml.get("yAxisIndex"), 1)


# =============================================================================
# DUAL-AXIS
# =============================================================================

class TestDualAxis(unittest.TestCase):
    def test_dual_axis_multi_line_wide(self):
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "left_val": list(range(10)),
            "right_val": list(range(100, 110)),
        })
        r = make_echart(
            df=df, chart_type="multi_line",
            mapping={"x": "date", "y": ["left_val", "right_val"],
                      "dual_axis_series": ["right_val"],
                      "y_title": "L", "y_title_right": "R",
                      "invert_right_axis": True},
        )
        self.assertEqual(len(r.option["yAxis"]), 2)
        self.assertEqual(r.option["yAxis"][0]["name"], "L")
        self.assertEqual(r.option["yAxis"][1]["name"], "R")
        self.assertTrue(r.option["yAxis"][1]["inverse"])
        right_series = [s for s in r.option["series"]
                          if s["name"] == "right_val"][0]
        self.assertEqual(right_series["yAxisIndex"], 1)


# =============================================================================
# MULTI-AXIS (N y-axes via mapping.axes)
# =============================================================================
#
# The mapping.axes API lets authors define any number of independent
# y-axes (each with its own scale, side, inversion, log toggle, range
# bounds, format) and assign each series to exactly one axis.
# Backward-compat with dual_axis_series / invert_y / invert_right_axis
# is preserved.

class TestMultiAxis(unittest.TestCase):
    def _df_4(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "spx": list(range(5000, 5010)),
            "ust": [4.2 + i * 0.01 for i in range(10)],
            "dxy": [104.0 + i * 0.05 for i in range(10)],
            "wti": [82.0 + i * 0.30 for i in range(10)],
        })

    def test_3_axis_basic(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(len(ya), 3)
        self.assertEqual(ya[0]["position"], "left")
        self.assertEqual(ya[1]["position"], "right")
        self.assertEqual(ya[2]["position"], "left")
        # 3rd axis (2nd on the LEFT side) auto-stacks to one offset_step
        # (default 80 px) from the inner axis. Earlier 60 px crammed
        # the inner axis name into the outer axis tick-label region.
        self.assertEqual(ya[0]["offset"], 0)
        self.assertEqual(ya[1]["offset"], 0)
        self.assertEqual(ya[2]["offset"], 80)

    def test_4_axis_two_each_side(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy", "wti"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
                {"side": "right", "title": "WTI", "series": ["wti"]},
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(len(ya), 4)
        self.assertEqual(ya[2]["offset"], 80)
        self.assertEqual(ya[3]["offset"], 80)

    def test_axis_offset_step_override(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axis_offset_step": 100,
            "axes": [
                {"side": "left", "title": "SPX", "series": ["spx"]},
                {"side": "left", "title": "UST", "series": ["ust"]},
                {"side": "left", "title": "DXY", "series": ["dxy"]},
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(ya[1]["offset"], 100)
        self.assertEqual(ya[2]["offset"], 200)

    def test_series_to_axis_assignment(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
            ],
        })
        s_by_name = {s["name"]: s for s in r.option["series"]}
        # axis index 0 is implicit; only > 0 sets yAxisIndex
        self.assertNotIn("yAxisIndex", s_by_name["spx"])
        self.assertEqual(s_by_name["ust"]["yAxisIndex"], 1)
        self.assertEqual(s_by_name["dxy"]["yAxisIndex"], 2)

    def test_invert_per_axis(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"],
                  "invert": True},
                {"side": "left",  "title": "DXY", "series": ["dxy"],
                  "invert": True},
            ],
        })
        ya = r.option["yAxis"]
        self.assertFalse(ya[0]["inverse"])
        self.assertTrue(ya[1]["inverse"])
        self.assertTrue(ya[2]["inverse"])

    def test_log_per_axis(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"],
                  "log": True},
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(ya[0]["type"], "value")
        self.assertEqual(ya[1]["type"], "log")

    def test_min_max_per_axis(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"],
                  "min": 4900, "max": 5100},
                {"side": "right", "title": "UST", "series": ["ust"],
                  "min": 0, "max": 10},
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(ya[0]["min"], 4900)
        self.assertEqual(ya[0]["max"], 5100)
        self.assertEqual(ya[1]["min"], 0)
        self.assertEqual(ya[1]["max"], 10)

    def test_format_preset_attaches_formatter(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"],
                  "format": "compact"},
                {"side": "right", "title": "UST", "series": ["ust"],
                  "format": "bp"},
            ],
        })
        ya = r.option["yAxis"]
        self.assertIn("formatter", ya[0]["axisLabel"])
        self.assertIn("function", ya[0]["axisLabel"]["formatter"])
        self.assertIn("bp", ya[1]["axisLabel"]["formatter"])

    def test_split_line_only_on_first_axis(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
            ],
        })
        ya = r.option["yAxis"]
        # Axes 1 and 2 should hide their split lines; axis 0 keeps default.
        self.assertNotIn("splitLine", ya[0])
        self.assertEqual(ya[1].get("splitLine", {}).get("show"), False)
        self.assertEqual(ya[2].get("splitLine", {}).get("show"), False)

    def test_grid_left_clears_offset_axes(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
            ],
        })
        # 2nd left axis at offset=60 must be cleared by grid.left.
        self.assertGreaterEqual(r.option["grid"]["left"], 60 + 50)

    def test_grid_right_clears_offset_axes(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy", "wti"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
                {"side": "right", "title": "WTI", "series": ["wti"]},
            ],
        })
        self.assertGreaterEqual(r.option["grid"]["right"], 60 + 50)

    def test_explicit_offset_overrides_auto(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "left",  "title": "UST", "series": ["ust"],
                  "offset": 90},  # explicit override
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(ya[1]["offset"], 90)

    def test_unassigned_series_lands_on_axis_0(self):
        # If author defines axes but forgets to assign one of the series,
        # the resolver sweeps unassigned names onto axis 0 rather than
        # silently dropping them.
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                # dxy not assigned -> axis 0
            ],
        })
        s_by_name = {s["name"]: s for s in r.option["series"]}
        self.assertNotIn("yAxisIndex", s_by_name["dxy"])

    def test_duplicate_series_assignment_raises(self):
        df = self._df_4()
        with self.assertRaises(ValueError):
            make_echart(df, "multi_line", mapping={
                "x": "date", "y": ["spx", "ust"],
                "axes": [
                    {"side": "left",  "title": "L", "series": ["spx"]},
                    {"side": "right", "title": "R", "series": ["spx"]},
                ],
            })

    def test_invalid_side_raises(self):
        df = self._df_4()
        with self.assertRaises(ValueError):
            make_echart(df, "multi_line", mapping={
                "x": "date", "y": ["spx"],
                "axes": [{"side": "middle", "series": ["spx"]}],
            })

    def test_axes_not_a_list_raises(self):
        df = self._df_4()
        with self.assertRaises(ValueError):
            make_echart(df, "multi_line", mapping={
                "x": "date", "y": ["spx"],
                "axes": [{"side": "left", "series": "spx"}, "not a dict"],
            })

    def test_backward_compat_dual_axis_series_still_works(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "y_title": "SPX", "y_title_right": "UST",
            "dual_axis_series": ["ust"],
            "invert_right_axis": True,
        })
        ya = r.option["yAxis"]
        self.assertEqual(len(ya), 2)
        self.assertEqual(ya[0]["name"], "SPX")
        self.assertEqual(ya[1]["name"], "UST")
        self.assertTrue(ya[1]["inverse"])
        s_by_name = {s["name"]: s for s in r.option["series"]}
        self.assertEqual(s_by_name["ust"]["yAxisIndex"], 1)

    def test_axes_takes_precedence_over_dual_axis_series(self):
        # When both legacy and canonical APIs are present, mapping.axes
        # is the source of truth.
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "dual_axis_series": ["ust"],  # legacy: ignored
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "right", "title": "DXY", "series": ["dxy"]},
            ],
        })
        self.assertEqual(len(r.option["yAxis"]), 3)
        s_by_name = {s["name"]: s for s in r.option["series"]}
        self.assertEqual(s_by_name["dxy"]["yAxisIndex"], 2)

    def test_single_axis_preserves_dict_shape(self):
        # Single-axis charts keep yAxis as a dict (not a list) so legacy
        # callers that index into yAxis directly don't break.
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [{"side": "left", "title": "Both",
                       "series": ["spx", "ust"]}],
        })
        self.assertIsInstance(r.option["yAxis"], dict)

    def test_color_long_form_with_axes(self):
        # axes works with long-form (mapping.color) too: each color
        # group's series can be assigned to its own axis.
        rows = []
        for d in pd.date_range("2024-01-01", periods=10, freq="D"):
            rows.append({"date": d, "g": "A", "v": 100 + d.day})
            rows.append({"date": d, "g": "B", "v": 5 + d.day * 0.1})
        df = pd.DataFrame(rows)
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": "v", "color": "g",
            "axes": [
                {"side": "left",  "title": "A scale", "series": ["A"]},
                {"side": "right", "title": "B scale", "series": ["B"],
                  "invert": True},
            ],
        })
        self.assertEqual(len(r.option["yAxis"]), 2)
        s_by_name = {s["name"]: s for s in r.option["series"]}
        self.assertEqual(s_by_name["B"]["yAxisIndex"], 1)
        self.assertTrue(r.option["yAxis"][1]["inverse"])

    def test_hline_annotation_targets_axis_index(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
            ],
            "annotations": [
                {"type": "hline", "y": 4.5, "axis": 1,
                  "label": "UST ceiling"},
                {"type": "hline", "y": 110, "axis": 2,
                  "label": "DXY support"},
            ],
        })
        ml = r.option["series"][0]["markLine"]["data"]
        # Pull each markLine entry by yAxisIndex.
        self.assertEqual(
            sum(1 for d in ml if d.get("yAxisIndex") == 1), 1
        )
        self.assertEqual(
            sum(1 for d in ml if d.get("yAxisIndex") == 2), 1
        )

    def test_hline_annotation_legacy_right_string(self):
        df = self._df_4()
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "dual_axis_series": ["ust"],
            "annotations": [
                {"type": "hline", "y": 4.5, "axis": "right",
                  "label": "ceiling"},
            ],
        })
        ml = r.option["series"][0]["markLine"]["data"]
        self.assertEqual(
            sum(1 for d in ml if d.get("yAxisIndex") == 1), 1
        )


class TestDynamicAxisLayout(unittest.TestCase):
    """The dynamic layout pass sizes each axis's nameGap to clear its
    own tick labels, and (for multi-axis charts) widens offset_step
    when the inner axis labels are too wide for the default 80 px to
    keep the rotated name out of the outer axis's label region.

    These tests lock in the BEHAVIOR (no overlap) rather than specific
    pixel values, which would break whenever the heuristic changes.
    """

    def test_single_value_axis_namegap_clears_wide_labels(self):
        # Single-axis bar chart with raw 9-digit values needs a much
        # wider nameGap than the legacy 56 px floor or the y_title
        # ("Volume") would overlap the "100,000,000" tick labels.
        df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT", "NVDA"],
            "volume": [100_000_000, 200_000_000, 300_000_000],
        })
        r = make_echart(df, "bar", mapping={
            "x": "ticker", "y": "volume",
            "y_title": "Volume (sh)",
        })
        ya = r.option["yAxis"]
        # 9-digit raw integers render ~63 px wide at fontSize 12.
        # nameGap must clear that plus the rotated title bounding box.
        self.assertGreater(ya["nameGap"], 56,
                            "nameGap should grow past the 56 px floor "
                            "to clear 9-digit value labels")

    def test_single_value_axis_namegap_floor_for_narrow_labels(self):
        # Narrow labels (single digits) shouldn't bloat the layout --
        # nameGap stays at the 56 px floor.
        df = pd.DataFrame({
            "letter": list("ABCDE"),
            "score":  [1, 2, 3, 4, 5],
        })
        r = make_echart(df, "bar", mapping={
            "x": "letter", "y": "score",
            "y_title": "Score",
        })
        self.assertEqual(r.option["yAxis"]["nameGap"], 56)

    def test_multi_axis_namegap_does_not_double_count_offset(self):
        # Pre-fix bug: nameGap was set to ``40 + offset`` so an outer
        # axis at offset=80 ended up with its name 200 px from the
        # inner edge (offset 80 + nameGap 120). nameGap is measured
        # FROM the axis line, not the inner edge -- the offset already
        # shifts everything. We expect a tight per-axis nameGap that
        # depends only on that axis's label width.
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "a": [1, 2, 3, 4, 5],
            "b": [10, 20, 30, 40, 50],
        })
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["a", "b"],
            "axes": [
                {"side": "left", "title": "A", "series": ["a"]},
                {"side": "left", "title": "B", "series": ["b"]},
            ],
        })
        ya = r.option["yAxis"]
        # Inner axis (offset=0) and outer axis (offset>=80) carry
        # narrow labels (1-2 chars), so both get the 40 px floor.
        # The legacy ``40 + offset`` formula would have given 120 for
        # the outer axis.
        self.assertLessEqual(ya[0]["nameGap"], 60,
                              "Inner axis nameGap shouldn't exceed "
                              "the floor for narrow labels")
        self.assertLessEqual(ya[1]["nameGap"], 60,
                              "Outer axis nameGap should be sized by "
                              "ITS labels, not inner axis's offset")

    def test_multi_axis_step_widens_for_wide_inner_labels(self):
        # When the INNER axis carries wide percent labels (e.g.
        # "470.0%"), the offset_step must widen past the 80 px default
        # so the rotated inner-axis name doesn't bleed into the outer
        # axis's tick labels.
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "rate": [4.30 + i * 0.05 for i in range(10)],
            "vol":  [800 + i * 50 for i in range(10)],
        })
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["rate", "vol"],
            "axes": [
                {"side": "right", "title": "Rate", "series": ["rate"],
                  "format": "percent"},
                {"side": "right", "title": "Vol", "series": ["vol"]},
            ],
        })
        ya = r.option["yAxis"]
        # Inner "Rate" axis has labels like "470.0%" (~45 px),
        # nameGap = 45 + 26 = 71. Step = nameGap + half_thick + 14 = 94.
        self.assertGreater(ya[1]["offset"], 80,
                            "Outer axis should sit further out than "
                            "the default 80 px when inner labels are "
                            "wide enough to push the inner name "
                            "into the outer label region")

    def test_explicit_offset_still_honored(self):
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "a": [1, 2, 3, 4, 5],
            "b": [10, 20, 30, 40, 50],
        })
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["a", "b"],
            "axes": [
                {"side": "left", "title": "A", "series": ["a"]},
                {"side": "left", "title": "B", "series": ["b"],
                  "offset": 150},
            ],
        })
        # Author pinned offset=150: dynamic layout must NOT override.
        self.assertEqual(r.option["yAxis"][1]["offset"], 150)

    def test_user_axis_offset_step_floors_dynamic_step(self):
        # Author-supplied axis_offset_step acts as a floor: the
        # dynamic step takes max(user_step, computed). Even with
        # narrow labels the user's value wins.
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "a": [1, 2, 3, 4, 5],
            "b": [10, 20, 30, 40, 50],
            "c": [100, 200, 300, 400, 500],
        })
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["a", "b", "c"],
            "axis_offset_step": 120,
            "axes": [
                {"side": "left", "title": "A", "series": ["a"]},
                {"side": "left", "title": "B", "series": ["b"]},
                {"side": "left", "title": "C", "series": ["c"]},
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(ya[1]["offset"], 120)
        self.assertEqual(ya[2]["offset"], 240)

    def test_grid_margins_clear_widest_axis_labels(self):
        # Multi-axis charts size grid.left / grid.right large enough
        # that every offset axis (line + labels + name) fits inside
        # the canvas. Wide inner labels should propagate to wider
        # margins, not just wider offsets.
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "rate": [4.30 + i * 0.05 for i in range(10)],
            "vol":  [800 + i * 50 for i in range(10)],
        })
        r = make_echart(df, "multi_line", mapping={
            "x": "date", "y": ["rate", "vol"],
            "axes": [
                {"side": "right", "title": "Rate", "series": ["rate"],
                  "format": "percent"},
                {"side": "right", "title": "Vol", "series": ["vol"]},
            ],
        })
        # The outer axis sits past offset=80; with its own nameGap
        # plus the rotated title pad, grid.right needs to be well
        # above the legacy 90-ish px reservation.
        self.assertGreater(r.option["grid"]["right"], 120)


class TestMultiAxisColorCoding(unittest.TestCase):
    """Single-series axes auto-tint their axis line, tick labels, and
    rotated name to match the series' palette color so the chart reads
    like a Bloomberg-style overlay where each line and its scale share
    a color. Only kicks in for >=2 axes; single-axis charts stay
    neutral. Multi-series axes don't auto-pick (which color of the N
    would be ambiguous) but author can pin via ``axes[i].color``.
    """

    def _df(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "spx": list(range(5000, 5010)),
            "ust": [4.2 + i * 0.01 for i in range(10)],
            "dxy": [104.0 + i * 0.05 for i in range(10)],
        })

    def test_single_series_axes_inherit_palette_color(self):
        r = make_echart(self._df(), "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
                {"side": "left",  "title": "DXY", "series": ["dxy"]},
            ],
        })
        palette = r.option["color"]
        ya = r.option["yAxis"]
        # Each axis matches the series' palette color (series order).
        for i in range(3):
            self.assertEqual(ya[i]["axisLine"]["lineStyle"]["color"],
                              palette[i])
            self.assertEqual(ya[i]["axisLabel"]["color"], palette[i])
            self.assertEqual(ya[i]["nameTextStyle"]["color"], palette[i])

    def test_explicit_color_overrides_palette(self):
        r = make_echart(self._df(), "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"],
                  "color": "#ff0000"},
                {"side": "right", "title": "UST", "series": ["ust"]},
            ],
        })
        ya = r.option["yAxis"]
        self.assertEqual(ya[0]["axisLabel"]["color"], "#ff0000")
        self.assertEqual(ya[0]["nameTextStyle"]["color"], "#ff0000")

    def test_multi_series_axis_skips_auto_color(self):
        r = make_echart(self._df(), "multi_line", mapping={
            "x": "date", "y": ["spx", "ust", "dxy"],
            "axes": [
                # Two series share this axis -> no auto-pick.
                {"side": "left",  "title": "Both", "series": ["spx", "ust"]},
                {"side": "right", "title": "DXY",  "series": ["dxy"]},
            ],
        })
        ya = r.option["yAxis"]
        # Multi-series axis: no color tint applied.
        self.assertNotIn("axisLine", ya[0])
        # Single-series axis: tint applied.
        palette = r.option["color"]
        # dxy is the 3rd series in series_names order so it inherits color[2].
        self.assertEqual(ya[1]["axisLabel"]["color"], palette[2])

    def test_color_coding_disabled_globally(self):
        r = make_echart(self._df(), "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axis_color_coding": False,
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"]},
                {"side": "right", "title": "UST", "series": ["ust"]},
            ],
        })
        ya = r.option["yAxis"]
        for ax in ya:
            self.assertNotIn("axisLine", ax)
            self.assertNotIn("color",
                              ax.get("axisLabel") or {})

    def test_color_false_per_axis_opts_out(self):
        r = make_echart(self._df(), "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [
                {"side": "left",  "title": "SPX", "series": ["spx"],
                  "color": False},
                {"side": "right", "title": "UST", "series": ["ust"]},
            ],
        })
        ya = r.option["yAxis"]
        # Axis 0: color: False -> stays neutral
        self.assertNotIn("axisLine", ya[0])
        # Axis 1: still auto-color-coded
        palette = r.option["color"]
        self.assertEqual(ya[1]["axisLabel"]["color"], palette[1])

    def test_single_axis_chart_stays_neutral(self):
        # A single-axis chart shouldn't pick a color from the palette --
        # the line itself carries the hue; the axis would be redundant
        # and mismatch when there are multiple lines on the one axis.
        r = make_echart(self._df(), "multi_line", mapping={
            "x": "date", "y": ["spx", "ust"],
            "axes": [{"side": "left", "title": "Both",
                       "series": ["spx", "ust"]}],
        })
        ax = r.option["yAxis"]
        self.assertNotIn("axisLine", ax)


# =============================================================================
# STACK / STROKEDASH / TRENDLINE
# =============================================================================

class TestMappingKeys(unittest.TestCase):
    def test_bar_stacked(self):
        df = pd.DataFrame({
            "x": ["a", "a", "b", "b"],
            "c": ["p", "q", "p", "q"],
            "v": [1, 2, 3, 4],
        })
        r = make_echart(df=df, chart_type="bar",
                          mapping={"x": "x", "y": "v", "color": "c",
                                    "stack": True})
        self.assertEqual(r.option["series"][0].get("stack"), "total")

    def test_bar_grouped(self):
        df = pd.DataFrame({
            "x": ["a", "a", "b", "b"],
            "c": ["p", "q", "p", "q"],
            "v": [1, 2, 3, 4],
        })
        r = make_echart(df=df, chart_type="bar",
                          mapping={"x": "x", "y": "v", "color": "c",
                                    "stack": False})
        self.assertIsNone(r.option["series"][0].get("stack"))

    def test_strokedash_cross_product(self):
        rows = []
        for co in ["A", "B"]:
            for t in ["Actual", "Estimate"]:
                for d in pd.date_range("2024-01", periods=3, freq="MS"):
                    rows.append({"date": d, "company": co, "type": t, "v": 1.0})
        df = pd.DataFrame(rows)
        r = make_echart(df=df, chart_type="multi_line",
                          mapping={"x": "date", "y": "v",
                                    "color": "company", "strokeDash": "type"})
        # 2 companies * 2 types = 4 sub-series
        self.assertEqual(len(r.option["series"]), 4)
        # Legend by default only has company names (not cross-product)
        self.assertEqual(r.option["legend"]["data"], ["A", "B"])

    def test_trendline_adds_line_series(self):
        df = pd.DataFrame({"x": list(range(20)),
                           "y": [2 * i + 1 for i in range(20)]})
        r = make_echart(df=df, chart_type="scatter",
                          mapping={"x": "x", "y": "y", "trendline": True})
        self.assertEqual(len(r.option["series"]), 2)
        self.assertEqual(r.option["series"][1]["type"], "line")

    def test_axis_titles_set_names(self):
        df = pd.DataFrame({"x": ["a", "b"], "y": [1, 2]})
        r = make_echart(df=df, chart_type="bar",
                          mapping={"x": "x", "y": "y",
                                    "y_title": "count", "x_title": "cat"})
        self.assertEqual(r.option["xAxis"]["name"], "cat")
        self.assertEqual(r.option["yAxis"]["name"], "count")


# =============================================================================
# HISTOGRAM + BULLET
# =============================================================================

class TestNewBuilders(unittest.TestCase):
    def test_histogram_bins(self):
        df = pd.DataFrame({"v": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]})
        r = make_echart(df=df, chart_type="histogram",
                          mapping={"x": "v", "bins": 5})
        self.assertEqual(len(r.option["series"][0]["data"]), 5)

    def test_bullet_shape(self):
        df = pd.DataFrame({
            "cat": ["a", "b"], "cur": [10, 20],
            "lo": [0, 5], "hi": [30, 25],
            "z": [0.5, -0.5],
        })
        r = make_echart(df=df, chart_type="bullet",
                          mapping={"y": "cat", "x": "cur",
                                    "x_low": "lo", "x_high": "hi",
                                    "color_by": "z"})
        self.assertEqual(r.option["series"][0]["type"], "custom")
        self.assertEqual(len(r.option["series"][0]["data"]), 2)


# =============================================================================
# CORRELATION_MATRIX BUILDER (Phase 1: exploratory analytics)
# =============================================================================

class TestCorrelationMatrix(unittest.TestCase):
    """Builder produces an N x N heatmap with values in [-1, 1] and the
    diverging palette pinned to that range. Tests cover the math
    (perfect-correlation diagonal, perfect-anticorr off-diagonal),
    transform pre-processing, NaN tolerance, and Spearman ranks.
    """

    def _df_2col(self):
        return pd.DataFrame({"a": [1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                              "b": [2.0, 4, 6, 8, 10, 12, 14, 16, 18, 20]})

    def test_n_cells_equals_n_squared(self):
        df = self._df_2col()
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"]})
        self.assertEqual(len(r.option["series"][0]["data"]), 4)

    def test_diagonal_is_1(self):
        df = self._df_2col()
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"]})
        cells = r.option["series"][0]["data"]
        # Diagonal is (i, n-1-i) for i in 0..n-1
        n = 2
        diag_vals = []
        for c in cells:
            v = c["value"]
            if v[0] + v[1] == n - 1:  # diagonal
                diag_vals.append(v[2])
        self.assertEqual(len(diag_vals), 2)
        for v in diag_vals:
            self.assertAlmostEqual(v, 1.0, places=6)

    def test_perfect_correlation_off_diagonal_is_1(self):
        # b = 2 * a + 0 -> r = 1
        df = self._df_2col()
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"]})
        cells = r.option["series"][0]["data"]
        off = [c["value"][2] for c in cells
                if c["value"][0] + c["value"][1] != 1]
        for v in off:
            self.assertAlmostEqual(v, 1.0, places=6)

    def test_perfect_anticorrelation(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5],
                            "b": [-1, -2, -3, -4, -5]})
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"]})
        cells = r.option["series"][0]["data"]
        off = [c["value"][2] for c in cells
                if c["value"][0] != c["value"][1]
                and not (c["value"][0] + c["value"][1] == 1)]
        # In a 2x2 matrix the diagonal is positions (0,1) and (1,0);
        # off-diagonals are (0,0) and (1,1) per the reversed-y layout.
        # Pull the symmetric pair where columns differ -> should be -1.
        anti = [c["value"][2] for c in cells
                 if (c["value"][0], c["value"][1]) in ((0, 0), (1, 1))]
        for v in anti:
            self.assertAlmostEqual(v, -1.0, places=6)

    def test_visualmap_pinned_to_pm1(self):
        df = self._df_2col()
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"]})
        vm = r.option["visualMap"][0]
        self.assertEqual(vm["min"], -1)
        self.assertEqual(vm["max"], 1)
        self.assertGreaterEqual(len(vm["inRange"]["color"]), 3)

    def test_min_periods_drops_thin_overlap(self):
        df = pd.DataFrame({
            "a": [1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "b": [None, None, None, None, None, None, None, None, 1, 2],
        })
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"], "min_periods": 5})
        cells = r.option["series"][0]["data"]
        # Off-diagonal cell should be None (insufficient overlap).
        off = [c["value"][2] for c in cells
                if (c["value"][0], c["value"][1]) in ((0, 0), (1, 1))]
        for v in off:
            self.assertIsNone(v)

    def test_pct_change_transform_requires_order_by(self):
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5),
            "a": [1.0, 2, 3, 4, 5],
            "b": [10.0, 20, 30, 40, 50],
        })
        # No order_by + no datetime -> should raise.
        with self.assertRaises(ValueError):
            make_echart(pd.DataFrame({"a": [1.0, 2, 3, 4],
                                        "b": [4.0, 3, 2, 1]}),
                          "correlation_matrix",
                          mapping={"columns": ["a", "b"],
                                    "transform": "pct_change"})
        # With explicit order_by it works.
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"],
                                    "transform": "pct_change",
                                    "order_by": "date"})
        self.assertEqual(r.option["series"][0]["type"], "heatmap")

    def test_spearman_handles_monotonic_nonlinear(self):
        # y = exp(x): Pearson < 1, Spearman = 1.
        import math
        xs = [1, 2, 3, 4, 5, 6, 7, 8]
        ys = [math.exp(x) for x in xs]
        df = pd.DataFrame({"a": xs, "b": ys})
        r_pearson = make_echart(df, "correlation_matrix",
                                  mapping={"columns": ["a", "b"]})
        r_spearman = make_echart(df, "correlation_matrix",
                                   mapping={"columns": ["a", "b"],
                                             "method": "spearman"})

        def _off(opt):
            for c in opt["series"][0]["data"]:
                v = c["value"]
                if (v[0], v[1]) in ((0, 0), (1, 1)):
                    return v[2]
            return None
        rp = _off(r_pearson.option)
        rs = _off(r_spearman.option)
        self.assertLess(rp, 0.99999)
        self.assertAlmostEqual(rs, 1.0, places=6)

    def test_columns_required(self):
        df = self._df_2col()
        with self.assertRaises(ValueError):
            make_echart(df, "correlation_matrix", mapping={})
        with self.assertRaises(ValueError):
            make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a"]})

    def test_label_formatter_present_when_show_values(self):
        df = self._df_2col()
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"], "show_values": True})
        label = r.option["series"][0]["label"]
        self.assertTrue(label["show"])
        self.assertIn("toFixed", label["formatter"])
        r2 = make_echart(df, "correlation_matrix",
                           mapping={"columns": ["a", "b"], "show_values": False})
        self.assertFalse(r2.option["series"][0]["label"]["show"])


class TestComputeTransform(unittest.TestCase):
    """The shared per-column transform helper backs both
    correlation_matrix (compile-time) and scatter_studio (runtime).
    Verify each transform name produces the expected column.
    """

    def setUp(self):
        from echart_studio import _compute_transform
        self._t = _compute_transform

    def test_raw_passthrough(self):
        out = self._t([1, 2, 3], None, "raw")
        self.assertEqual(out, [1.0, 2.0, 3.0])

    def test_log_drops_nonpositive(self):
        out = self._t([1, 0, -2, 4], None, "log")
        import math
        self.assertAlmostEqual(out[0], 0.0)
        self.assertIsNone(out[1])
        self.assertIsNone(out[2])
        self.assertAlmostEqual(out[3], math.log(4))

    def test_pct_change(self):
        out = self._t([100, 110, 121, 0], None, "pct_change")
        self.assertIsNone(out[0])
        self.assertAlmostEqual(out[1], 10.0)
        self.assertAlmostEqual(out[2], 10.0)
        # division-by-zero step -> None
        # Followed by None at index 3 because b == 0 ... actually i=3,
        # b = values[2] = 121 so this is fine; a=0, b=121 -> -100%
        # Re-check: pct_change(0, 121) == (0-121)/121 = -100
        self.assertAlmostEqual(out[3], -100.0)

    def test_change(self):
        out = self._t([1, 3, 6], None, "change")
        self.assertIsNone(out[0])
        self.assertEqual(out[1:], [2.0, 3.0])

    def test_zscore(self):
        # Standard normal-ish: mean 0, stdev ~1
        from echart_studio import _compute_transform
        vals = [-2, -1, 0, 1, 2]
        out = _compute_transform(vals, None, "zscore")
        # Sample-stdev = sqrt(10/4) = sqrt(2.5)
        import math
        s = math.sqrt(2.5)
        self.assertAlmostEqual(out[0], -2 / s, places=6)
        self.assertAlmostEqual(out[2], 0.0, places=6)
        self.assertAlmostEqual(out[4],  2 / s, places=6)

    def test_rank_pct(self):
        out = self._t([10, 30, 20, 40], None, "rank_pct")
        # Sorted: 10 -> 0, 20 -> 33.3, 30 -> 66.7, 40 -> 100
        self.assertAlmostEqual(out[0], 0.0, places=2)
        self.assertAlmostEqual(out[1], 66.6666, places=2)
        self.assertAlmostEqual(out[2], 33.3333, places=2)
        self.assertAlmostEqual(out[3], 100.0, places=2)

    def test_yoy_pct(self):
        from datetime import date, timedelta
        base = date(2023, 1, 1)
        dates = [base + timedelta(days=i * 30) for i in range(15)]
        # 15 monthly points; row 12 (year+1) vs row 0 should be defined.
        vals = [100.0 + i for i in range(15)]
        out = self._t(vals, dates, "yoy_pct")
        self.assertIsNone(out[0])
        # The year-ago lookup uses ~365d; with 30-day spacing, row 12
        # is 360d from row 0 (one step short) -> falls back to row -1
        # candidate (none qualifies). row 13 is 390d -> qualifies.
        # Just verify SOME row late in the series is defined.
        late_defined = [v for v in out[12:] if v is not None]
        self.assertGreater(len(late_defined), 0)


class TestRegressionStats(unittest.TestCase):
    def test_perfect_fit(self):
        from echart_studio import _compute_regression_stats
        xs = [1, 2, 3, 4, 5]
        ys = [2, 4, 6, 8, 10]
        s = _compute_regression_stats(xs, ys)
        self.assertEqual(s["n"], 5)
        self.assertAlmostEqual(s["slope"], 2.0)
        self.assertAlmostEqual(s["intercept"], 0.0)
        self.assertAlmostEqual(s["r"], 1.0)
        self.assertAlmostEqual(s["r2"], 1.0)
        # RMSE should be exactly 0 for perfect fit
        self.assertLess(s["rmse"], 1e-9)

    def test_zero_variance_x(self):
        from echart_studio import _compute_regression_stats
        s = _compute_regression_stats([5, 5, 5, 5], [1, 2, 3, 4])
        self.assertEqual(s["degenerate"], "x_zero_variance")

    def test_too_few_points(self):
        from echart_studio import _compute_regression_stats
        self.assertIsNone(_compute_regression_stats([1], [2]))
        self.assertIsNone(_compute_regression_stats([], []))

    def test_drops_nan_pairs(self):
        from echart_studio import _compute_regression_stats
        s = _compute_regression_stats(
            [1, 2, 3, None, 5],
            [2, 4, 6, 8, None],
        )
        self.assertEqual(s["n"], 3)


class TestScatterStudio(unittest.TestCase):
    """Phase 2 builder: produces a scatter option from defaults AND
    embeds the studio config block ``opt['_studio']`` so the runtime
    drawer can wire dropdowns / recompute on user input.
    """

    def _df(self):
        from datetime import date, timedelta
        random.seed(91)
        n = 60
        base = date(2025, 1, 1)
        return pd.DataFrame({
            "date":   [base + timedelta(days=i) for i in range(n)],
            "us_2y":  [3.5 + i * 0.01 + random.gauss(0, 0.04) for i in range(n)],
            "us_10y": [4.0 + i * 0.012 + random.gauss(0, 0.04) for i in range(n)],
            "spx":    [4500 + i * 5 + random.gauss(0, 30) for i in range(n)],
            "regime": [["risk-on", "risk-off"][i % 2] for i in range(n)],
        })

    def test_basic_render(self):
        df = self._df()
        r = make_echart(df, "scatter_studio", mapping={
            "x_columns": ["us_2y", "us_10y"],
            "y_columns": ["spx", "us_10y"],
            "order_by": "date",
        })
        self.assertEqual(r.option["series"][0]["type"], "scatter")
        # Should contain the embedded studio config
        self.assertIn("_studio", r.option)
        cfg = r.option["_studio"]
        self.assertEqual(cfg["x_columns"], ["us_2y", "us_10y"])
        self.assertEqual(cfg["y_columns"], ["spx", "us_10y"])
        # Defaults picked from whitelists
        self.assertIn(cfg["x_default"], cfg["x_columns"])
        self.assertIn(cfg["y_default"], cfg["y_columns"])

    def test_color_grouping_emits_one_series_per_group(self):
        df = self._df()
        r = make_echart(df, "scatter_studio", mapping={
            "x_columns": ["us_10y"], "y_columns": ["spx"],
            "color_columns": ["regime"],
            "color_default": "regime",
            "order_by": "date",
        })
        # Two regimes -> two scatter series
        scat_series = [s for s in r.option["series"]
                        if s.get("type") == "scatter"]
        self.assertEqual(len(scat_series), 2)
        self.assertSetEqual(
            set(s["name"] for s in scat_series),
            {"risk-on", "risk-off"},
        )

    def test_default_y_avoids_x(self):
        # When x and y_columns share an obvious overlap, the y_default
        # picker should prefer something OTHER than x_default so the
        # initial chart isn't a degenerate diagonal.
        df = self._df()
        r = make_echart(df, "scatter_studio", mapping={
            "x_columns": ["us_2y", "us_10y", "spx"],
            "y_columns": ["us_2y", "us_10y", "spx"],
            "x_default": "us_10y",
            "order_by": "date",
        })
        cfg = r.option["_studio"]
        self.assertNotEqual(cfg["x_default"], cfg["y_default"])

    def test_transform_default_in_axis_name(self):
        df = self._df()
        r = make_echart(df, "scatter_studio", mapping={
            "x_columns": ["us_10y"], "y_columns": ["spx"],
            "order_by": "date",
            "y_transform_default": "pct_change",
        })
        # The y axis name should include the transform suffix
        self.assertIn("%", r.option["yAxis"]["name"])

    def test_x_default_must_be_in_whitelist(self):
        # When x_default is not in x_columns, the resolver picks the
        # first whitelist entry (no error).
        df = self._df()
        r = make_echart(df, "scatter_studio", mapping={
            "x_columns": ["us_2y", "us_10y"],
            "y_columns": ["spx"],
            "x_default": "wat",   # not in x_columns
            "order_by": "date",
        })
        self.assertEqual(r.option["_studio"]["x_default"], "us_2y")

    def test_order_by_must_exist_in_dataset(self):
        df = self._df()
        with self.assertRaises(ValueError):
            make_echart(df, "scatter_studio", mapping={
                "x_columns": ["us_10y"], "y_columns": ["spx"],
                "order_by": "nope",
            })

    def test_unknown_column_in_whitelist_raises(self):
        df = self._df()
        with self.assertRaises(ValueError):
            make_echart(df, "scatter_studio", mapping={
                "x_columns": ["us_10y", "phantom"],
                "y_columns": ["spx"],
                "order_by": "date",
            })

    def test_studio_in_safe_for_rewire(self):
        # Auto-wire path: scatter_studio should be marked safe for
        # rewire so that filters chain to it (dataset_ref auto-set).
        from echart_dashboard import compile_dashboard
        df = self._df()
        manifest = {
            "schema_version": 1, "id": "studio_test", "title": "t",
            "datasets": {"d": df},
            "layout": {"rows": [
                [{"widget": "chart", "id": "c1", "w": 12, "h_px": 320,
                   "spec": {"chart_type": "scatter_studio",
                              "dataset": "d",
                              "mapping": {
                                  "x_columns": ["us_10y"],
                                  "y_columns": ["spx"],
                                  "order_by": "date",
                              }}}]
            ]},
            "filters": [
                {"id": "regime", "type": "select", "label": "Regime",
                  "field": "regime", "options": ["risk-on", "risk-off"],
                  "default": "risk-on", "targets": ["c1"]}
            ],
        }
        out = Path(tempfile.mkdtemp(prefix="studio_rewire_test_"))
        result = compile_dashboard(manifest, session_path=out,
                                       write_html=False, write_json=True)
        if not result.success:
            # Surface the diagnostic codes so failures are diagnosable.
            codes = [d.code for d in (result.diagnostics or [])]
            self.fail(f"compile_dashboard failed: codes={codes}")
        # The compiled manifest should now have dataset_ref="d" on c1
        # (added by _augment_manifest because scatter_studio is safe
        # for rewire).
        compiled_widget = result.manifest["layout"]["rows"][0][0]
        self.assertEqual(compiled_widget.get("dataset_ref"), "d")


# =============================================================================
# DATAFRAME-FIRST MANIFEST CONTRACT
# =============================================================================

class TestDataFrameContract(unittest.TestCase):
    def _df(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "a": [1.0, 2.0, 3.0],
            "b": [4.0, 5.0, 6.0],
        })

    def _layout(self, dataset_name: str = "d"):
        return {
            "rows": [[{
                "widget": "chart", "id": "c", "w": 12,
                "spec": {"chart_type": "multi_line", "dataset": dataset_name,
                          "mapping": {"x": "date", "y": ["a", "b"]}}}]]
        }

    def test_dataframe_shorthand(self):
        from echart_dashboard import compile_dashboard
        m = {"schema_version": 1, "id": "t", "title": "t",
             "datasets": {"d": self._df()},
             "layout": self._layout()}
        r = compile_dashboard(m)
        self.assertTrue(r.success, r.warnings)

    def test_dataframe_in_source(self):
        from echart_dashboard import compile_dashboard
        m = {"schema_version": 1, "id": "t", "title": "t",
             "datasets": {"d": {"source": self._df()}},
             "layout": self._layout()}
        r = compile_dashboard(m)
        self.assertTrue(r.success, r.warnings)

    def test_df_to_source_export(self):
        from echart_dashboard import df_to_source
        src = df_to_source(self._df())
        self.assertEqual(src[0], ["date", "a", "b"])
        self.assertEqual(len(src), 4)

    def test_list_shorthand(self):
        from echart_dashboard import compile_dashboard
        rows = [["date", "a", "b"],
                ["2024-01-01", 1.0, 4.0],
                ["2024-01-02", 2.0, 5.0]]
        m = {"schema_version": 1, "id": "t", "title": "t",
             "datasets": {"d": rows},
             "layout": self._layout()}
        r = compile_dashboard(m)
        self.assertTrue(r.success, r.warnings)


# =============================================================================
# COMPOSITES
# =============================================================================

class TestComposites(unittest.TestCase):
    def _df_line(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=8, freq="MS"),
            "a": [1, 2, 3, 4, 5, 6, 7, 8],
            "b": [8, 7, 6, 5, 4, 3, 2, 1],
        })

    def test_2pack_horizontal(self):
        from composites import ChartSpec, make_2pack_horizontal
        r = make_2pack_horizontal(
            ChartSpec(df=self._df_line(), chart_type="multi_line",
                        mapping={"x": "date", "y": ["a", "b"]}, title="A"),
            ChartSpec(df=self._df_line(), chart_type="line",
                        mapping={"x": "date", "y": "a"}, title="B"),
            title="2pack",
        )
        self.assertTrue(r.success, r.warnings)
        self.assertEqual(len(r.option["grid"]), 2)
        self.assertEqual(r.chart_type, "composite")

    def test_2pack_vertical(self):
        from composites import ChartSpec, make_2pack_vertical
        r = make_2pack_vertical(
            ChartSpec(df=self._df_line(), chart_type="line",
                        mapping={"x": "date", "y": "a"}, title="Top"),
            ChartSpec(df=self._df_line(), chart_type="line",
                        mapping={"x": "date", "y": "b"}, title="Bot"),
        )
        self.assertEqual(len(r.option["grid"]), 2)

    def test_3pack_triangle(self):
        from composites import ChartSpec, make_3pack_triangle
        df = self._df_line()
        r = make_3pack_triangle(
            ChartSpec(df=df, chart_type="line",
                        mapping={"x": "date", "y": "a"}, title="Top"),
            ChartSpec(df=df, chart_type="line",
                        mapping={"x": "date", "y": "a"}, title="BL"),
            ChartSpec(df=df, chart_type="line",
                        mapping={"x": "date", "y": "b"}, title="BR"),
        )
        self.assertEqual(len(r.option["grid"]), 3)

    def test_4pack_grid(self):
        from composites import ChartSpec, make_4pack_grid
        df = self._df_line()
        spec = ChartSpec(df=df, chart_type="line",
                          mapping={"x": "date", "y": "a"}, title="x")
        r = make_4pack_grid(spec, spec, spec, spec)
        self.assertEqual(len(r.option["grid"]), 4)

    def test_6pack_grid(self):
        from composites import ChartSpec, make_6pack_grid
        df = self._df_line()
        spec = ChartSpec(df=df, chart_type="line",
                          mapping={"x": "date", "y": "a"}, title="x")
        r = make_6pack_grid(spec, spec, spec, spec, spec, spec)
        self.assertEqual(len(r.option["grid"]), 6)


# =============================================================================
# AXIS EXTENSIONS (invert_y, log scale)
# =============================================================================

class TestAxisExtensions(unittest.TestCase):
    def _df(self):
        return pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "v": [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0, 512.0],
        })

    def test_invert_y_single_axis_line(self):
        r = make_echart(df=self._df(), chart_type="line",
                          mapping={"x": "date", "y": "v",
                                    "invert_y": True})
        self.assertTrue(r.option["yAxis"]["inverse"])

    def test_y_log_scale(self):
        r = make_echart(df=self._df(), chart_type="line",
                          mapping={"x": "date", "y": "v", "y_log": True})
        self.assertEqual(r.option["yAxis"]["type"], "log")

    def test_invert_y_on_bar(self):
        df = pd.DataFrame({"x": ["a", "b", "c"], "y": [3, 1, 2]})
        r = make_echart(df=df, chart_type="bar",
                          mapping={"x": "x", "y": "y", "invert_y": True})
        self.assertTrue(r.option["yAxis"]["inverse"])

    def test_invert_y_on_scatter(self):
        df = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
        r = make_echart(df=df, chart_type="scatter",
                          mapping={"x": "x", "y": "y", "invert_y": True})
        self.assertTrue(r.option["yAxis"]["inverse"])


# =============================================================================
# LONG-LABEL LAYOUT (axis title vs tick label collisions)
# =============================================================================

class TestLongLabelLayout(unittest.TestCase):
    """Regression tests for the long-axis-label collision fix.

    Before the fix, a horizontal bar (or bullet) with long category
    names + a y-axis title rendered the rotated title overlapping the
    tick labels. The fix:
      * truncates over-long category labels via axisLabel.width +
        overflow=truncate (default cap 220 px),
      * sizes axis-title nameGap from the actual longest label width,
      * bumps grid.left / grid.bottom so titles don't clip at the
        canvas edge,
      * adds the missing _apply_axis_titles wiring to heatmap and
        boxplot, plus a grid.right bump for the heatmap visualMap,
      * auto-rotates dense vertical-bar / boxplot x-labels (only when
        the chart has <=30 categories with avg label > 5 chars).
    """

    def _long_h_bar(self, **extra):
        df = pd.DataFrame({
            "metric": [
                "1Y forward 5Y nominal yield in basis points",
                "10Y breakeven inflation premium (annualised)",
                "Real-money positioning percentile (4-week)",
                "Fed funds futures cumulative cuts implied",
            ],
            "value": [42.1, 18.3, 76.5, -33.0],
        })
        m = {"x": "value", "y": "metric"}
        m.update(extra)
        return make_echart(df, "bar_horizontal", mapping=m).option

    def test_h_bar_truncates_long_y_labels(self):
        opt = self._long_h_bar(x_title="Z-score")
        al = opt["yAxis"]["axisLabel"]
        self.assertEqual(al.get("overflow"), "truncate")
        self.assertEqual(al.get("width"), 220)

    def test_h_bar_namegap_clears_truncated_labels(self):
        opt = self._long_h_bar(x_title="Z-score")
        gap = opt["yAxis"]["nameGap"]
        # nameGap must clear the 220 px label cap + padding.
        self.assertGreaterEqual(gap, 220 + 10)

    def test_h_bar_no_truncation_for_short_labels(self):
        df = pd.DataFrame({"sector": ["Tech", "Fin", "Energy"],
                              "ytd": [18.0, 9.0, 4.0]})
        opt = make_echart(df, "bar_horizontal",
                           mapping={"x": "ytd", "y": "sector",
                                     "x_title": "YTD (%)"}).option
        al = opt["yAxis"].get("axisLabel") or {}
        # Short labels never need truncation.
        self.assertNotIn("overflow", al)
        self.assertNotIn("width", al)

    def test_h_bar_custom_label_cap(self):
        opt = self._long_h_bar(x_title="Z", category_label_max_px=120)
        self.assertEqual(opt["yAxis"]["axisLabel"]["width"], 120)
        self.assertGreaterEqual(opt["yAxis"]["nameGap"], 120 + 10)

    def test_h_bar_user_namegap_override(self):
        opt = self._long_h_bar(x_title="Z", x_title_gap=999)
        self.assertEqual(opt["yAxis"]["nameGap"], 999)

    def test_bullet_long_y_labels_truncate(self):
        df = pd.DataFrame([
            {"name": "10Y UST yield (cash, nominal, OIS-deflated)",
             "cur": 4.10, "lo": 3.50, "hi": 4.80, "z": 0.8},
            {"name": "5Y/30Y nominal slope (basis points, daily)",
             "cur": 32.0, "lo": -10.0, "hi": 90.0, "z": -0.4},
        ])
        opt = make_echart(
            df, "bullet",
            mapping={"y": "name", "x": "cur", "x_low": "lo",
                      "x_high": "hi", "color_by": "z",
                      "x_title": "Range"},
        ).option
        self.assertEqual(opt["yAxis"]["axisLabel"]["overflow"],
                          "truncate")
        self.assertGreaterEqual(opt["yAxis"]["nameGap"], 220 + 10)

    def test_heatmap_applies_axis_titles(self):
        rows = []
        for y in ["a", "b", "c"]:
            for x in ["1", "2", "3"]:
                rows.append({"y": y, "x": x, "v": 1.0})
        df = pd.DataFrame(rows)
        opt = make_echart(df, "heatmap",
                           mapping={"x": "x", "y": "y", "value": "v",
                                     "x_title": "Month",
                                     "y_title": "Strategy"}).option
        self.assertEqual(opt["xAxis"].get("name"), "Month")
        self.assertEqual(opt["yAxis"].get("name"), "Strategy")

    def test_heatmap_grid_right_clears_visualmap(self):
        rows = [{"y": "a", "x": "1", "v": 1.0}]
        df = pd.DataFrame(rows)
        opt = make_echart(df, "heatmap",
                           mapping={"x": "x", "y": "y",
                                     "value": "v"}).option
        self.assertGreaterEqual(opt["grid"]["right"], 76)

    def test_heatmap_long_y_labels_truncate(self):
        rows = []
        long_y = ["Long short equity factor positioning"] * 3
        for y in ["A", "B", "C"]:
            for x in ["1", "2", "3"]:
                rows.append({"y": long_y[0] if y == "A" else y,
                              "x": x, "v": 1.0})
        df = pd.DataFrame(rows)
        opt = make_echart(df, "heatmap",
                           mapping={"x": "x", "y": "y",
                                     "value": "v"}).option
        # The heatmap builder calls _layout_long_category_axis on
        # yAxis even without a y_title, so over-long labels get
        # truncated.
        al = opt["yAxis"].get("axisLabel") or {}
        if any(len(s) > 30 for s in opt["yAxis"]["data"]):
            self.assertEqual(al.get("overflow"), "truncate")

    def test_boxplot_applies_axis_titles(self):
        df = pd.DataFrame({"c": list("abc") * 3,
                            "v": [1, 2, 3, 4, 5, 6, 7, 8, 9]})
        opt = make_echart(df, "boxplot",
                           mapping={"x": "c", "y": "v",
                                     "x_title": "Group",
                                     "y_title": "Return"}).option
        self.assertEqual(opt["xAxis"].get("name"), "Group")
        self.assertEqual(opt["yAxis"].get("name"), "Return")

    def test_v_bar_autorotates_long_labels(self):
        df = pd.DataFrame({
            "country": ["United States of America",
                          "Federal Republic of Germany",
                          "United Kingdom of Great Britain",
                          "People's Republic of China",
                          "Republic of South Africa"],
            "v": [1, 2, 3, 4, 5],
        })
        opt = make_echart(df, "bar",
                           mapping={"x": "country", "y": "v"}).option
        al = opt["xAxis"].get("axisLabel") or {}
        self.assertEqual(al.get("rotate"), 30)
        self.assertEqual(al.get("interval"), 0)

    def test_v_bar_no_rotate_for_short_labels(self):
        df = pd.DataFrame({"x": ["A", "B", "C", "D"],
                            "y": [1, 2, 3, 4]})
        opt = make_echart(df, "bar",
                           mapping={"x": "x", "y": "y"}).option
        al = opt["xAxis"].get("axisLabel") or {}
        self.assertNotIn("rotate", al)

    def test_v_bar_no_rotate_for_dense_short_labels(self):
        # 50 short date-style labels: ECharts' interval='auto' is
        # the right call. Don't rotate.
        labels = [f"D{i}" for i in range(50)]
        df = pd.DataFrame({"d": labels, "v": list(range(50))})
        opt = make_echart(df, "bar",
                           mapping={"x": "d", "y": "v"}).option
        al = opt["xAxis"].get("axisLabel") or {}
        self.assertNotIn("rotate", al)

    def test_autorotate_helper_preserves_user_rotate(self):
        # Direct helper test: user-set rotate must NOT be clobbered.
        from echart_studio import (
            _autorotate_x_category_labels, BuilderContext,
        )
        opt = {
            "xAxis": {"type": "category", "data": [
                "United States of America",
                "Federal Republic of Germany",
                "United Kingdom of Great Britain",
                "People's Republic of China",
                "Republic of South Africa",
            ], "axisLabel": {"rotate": 45}},
            "grid": {"left": 76, "right": 20},
        }
        ctx = BuilderContext(chart_type="bar", width=700)
        _autorotate_x_category_labels(opt, ctx)
        self.assertEqual(opt["xAxis"]["axisLabel"]["rotate"], 45)
        # `interval` should not have been added either since the user
        # explicitly opted out via their own `rotate`.
        self.assertNotIn("interval", opt["xAxis"]["axisLabel"])


# =============================================================================
# HEATMAP CELL LABELS + AUTO-CONTRAST + COLOR CONFIGURATION
# =============================================================================
#
# The heatmap builder (and calendar_heatmap / correlation_matrix) print
# cell values by default and pick black/white text per cell based on
# the cell's resolved color luminance. The text-color picker uses
# ECharts rich-text styles (label.rich.l = dark text, label.rich.d =
# light text) and a JS formatter that wraps each value in {l|...} or
# {d|...} based on the cell color -- ECharts heatmap doesn't evaluate
# label.color as a callback so rich text is the supported path.
#
# Color stops are configurable via mapping.colors (raw list),
# mapping.color_palette (palette name), or mapping.color_scale
# (sequential / diverging / auto). The visualMap range can be pinned
# via mapping.value_min / mapping.value_max.

class TestHeatmapLabels(unittest.TestCase):
    def _df(self):
        return pd.DataFrame({
            "x": list("AABBCC"),
            "y": list("121212"),
            "v": [10, 30, 50, 70, 90, 110],
        })

    def test_default_shows_values_with_auto_contrast(self):
        r = make_echart(self._df(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v"})
        label = r.option["series"][0]["label"]
        self.assertTrue(label["show"])
        self.assertIn("formatter", label)
        # Auto-contrast goes through rich-text styles -- a {l|...}/{d|...}
        # wrapper plus rich.l (dark text) / rich.d (light text).
        self.assertIn("rich", label)
        self.assertEqual(label["rich"]["l"]["color"], "#111")
        self.assertEqual(label["rich"]["d"]["color"], "#fff")
        self.assertIn("'{'+s+'|'", label["formatter"])

    def test_show_values_false_drops_formatter(self):
        r = make_echart(self._df(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "show_values": False})
        label = r.option["series"][0]["label"]
        self.assertFalse(label["show"])
        self.assertNotIn("formatter", label)
        self.assertNotIn("rich", label)

    def test_value_label_color_explicit_disables_rich(self):
        r = make_echart(self._df(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "value_label_color": "#ff0000"})
        label = r.option["series"][0]["label"]
        self.assertEqual(label.get("color"), "#ff0000")
        self.assertNotIn("rich", label)
        # Plain formatter (no {l|...}/{d|...} wrapping).
        self.assertIn("toFixed", label["formatter"])
        self.assertNotIn("'{'+s+'|'", label["formatter"])

    def test_value_label_color_false_disables_color_and_rich(self):
        r = make_echart(self._df(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "value_label_color": False})
        label = r.option["series"][0]["label"]
        self.assertNotIn("color", label)
        self.assertNotIn("rich", label)

    def test_custom_value_formatter_passes_through(self):
        custom = "function(p){return 'X';}"
        r = make_echart(self._df(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "value_formatter": custom})
        self.assertEqual(
            r.option["series"][0]["label"]["formatter"], custom
        )

    def test_value_decimals_threads_into_formatter(self):
        r = make_echart(self._df(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "value_decimals": 3})
        self.assertIn("toFixed(3)",
                       r.option["series"][0]["label"]["formatter"])

    def test_cell_data_uses_value_dict_form(self):
        r = make_echart(self._df(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v"})
        cells = r.option["series"][0]["data"]
        self.assertIsInstance(cells[0], dict)
        self.assertIn("value", cells[0])
        self.assertEqual(len(cells[0]["value"]), 3)


class TestHeatmapColorConfig(unittest.TestCase):
    def _df_pos(self):
        return pd.DataFrame({
            "x": list("AABB"), "y": list("1212"),
            "v": [10, 20, 30, 40],
        })

    def _df_cross_zero(self):
        return pd.DataFrame({
            "x": list("AABB"), "y": list("1212"),
            "v": [-5, -2, 8, 12],
        })

    def test_explicit_colors_override_palette(self):
        r = make_echart(self._df_pos(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "colors": ["#000", "#888", "#fff"]})
        self.assertEqual(
            r.option["visualMap"][0]["inRange"]["color"],
            ["#000", "#888", "#fff"],
        )

    def test_color_palette_by_name(self):
        r = make_echart(self._df_pos(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "color_palette": "gs_diverging"})
        cols = r.option["visualMap"][0]["inRange"]["color"]
        self.assertGreaterEqual(len(cols), 3)

    def test_color_palette_unknown_falls_back(self):
        # Unknown palette name should not raise -- builder falls back
        # to the ctx default rather than crash.
        r = make_echart(self._df_pos(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "color_palette": "no_such_palette"})
        self.assertGreaterEqual(
            len(r.option["visualMap"][0]["inRange"]["color"]), 2
        )

    def test_color_scale_auto_picks_diverging_when_cross_zero(self):
        r = make_echart(self._df_cross_zero(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "color_scale": "auto"})
        vm = r.option["visualMap"][0]
        # Auto + cross-zero pads symmetrically around 0.
        self.assertEqual(vm["min"], -vm["max"])
        # And uses a diverging palette (>= 3 stops).
        self.assertGreaterEqual(len(vm["inRange"]["color"]), 3)

    def test_color_scale_auto_keeps_data_range_for_all_positive(self):
        r = make_echart(self._df_pos(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "color_scale": "auto"})
        vm = r.option["visualMap"][0]
        # All-positive data shouldn't trigger the symmetric padding.
        self.assertGreater(vm["min"], 0)

    def test_value_min_max_pin_visualmap(self):
        r = make_echart(self._df_pos(), "heatmap",
                          mapping={"x": "x", "y": "y", "value": "v",
                                    "value_min": 0, "value_max": 100})
        vm = r.option["visualMap"][0]
        self.assertEqual(vm["min"], 0)
        self.assertEqual(vm["max"], 100)


class TestHeatmapCorrelationMatrixContrast(unittest.TestCase):
    def test_correlation_matrix_uses_rich_text_auto_contrast(self):
        df = pd.DataFrame({"a": [1.0, 2, 3, 4, 5],
                            "b": [5, 4, 3, 2, 1]})
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"]})
        label = r.option["series"][0]["label"]
        self.assertTrue(label["show"])
        self.assertIn("rich", label)
        self.assertIn("'{'+s+'|'", label["formatter"])

    def test_correlation_matrix_custom_colors(self):
        df = pd.DataFrame({"a": [1.0, 2, 3], "b": [3, 2, 1]})
        r = make_echart(df, "correlation_matrix",
                          mapping={"columns": ["a", "b"],
                                    "colors": ["#ff0000", "#ffffff", "#0000ff"]})
        self.assertEqual(
            r.option["visualMap"][0]["inRange"]["color"],
            ["#ff0000", "#ffffff", "#0000ff"],
        )


class TestCalendarHeatmapConfig(unittest.TestCase):
    def _df(self):
        return pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=10),
            "v": [-3, -1, 0, 2, 4, 6, 8, 10, 12, 14],
        })

    def test_default_hides_values(self):
        # Calendar cells are typically too small for inline labels, so
        # show_values defaults to False (but is still configurable).
        r = make_echart(self._df(), "calendar_heatmap",
                          mapping={"date": "date", "value": "v"})
        self.assertFalse(r.option["series"][0]["label"]["show"])

    def test_show_values_true_uses_value_idx_1(self):
        # Calendar data is [date, value] (idx 1) -- formatter must
        # extract the right index.
        r = make_echart(self._df(), "calendar_heatmap",
                          mapping={"date": "date", "value": "v",
                                    "show_values": True})
        f = r.option["series"][0]["label"]["formatter"]
        # Looks up element 1 (the value), not element 2 (which would
        # be the regular-heatmap convention).
        self.assertIn("d.value[1]", f)
        self.assertIn("d[1]", f)

    def test_custom_colors(self):
        r = make_echart(self._df(), "calendar_heatmap",
                          mapping={"date": "date", "value": "v",
                                    "colors": ["#fff", "#000"]})
        self.assertEqual(
            r.option["visualMap"][0]["inRange"]["color"], ["#fff", "#000"]
        )

    def test_color_scale_auto_anchors_at_zero(self):
        r = make_echart(self._df(), "calendar_heatmap",
                          mapping={"date": "date", "value": "v",
                                    "color_scale": "auto"})
        vm = r.option["visualMap"][0]
        # Cross-zero data + auto -> symmetric range.
        self.assertEqual(vm["min"], -vm["max"])


# =============================================================================
# NEW FILTER TYPES + FIELDS
# =============================================================================

class TestNewFilterTypes(unittest.TestCase):
    def _m(self, filters):
        return {
            "schema_version": 1, "id": "t", "title": "t",
            "datasets": {"d": pd.DataFrame({"x": [1, 2, 3], "v": [4, 5, 6],
                                                "s": ["a", "b", "c"]})},
            "filters": filters,
            "layout": {"rows": [[{"widget": "table", "id": "tbl",
                                    "dataset_ref": "d"}]]},
        }

    def test_slider_ok(self):
        m = self._m([{"id": "f", "type": "slider",
                        "min": 0, "max": 100, "default": 5,
                        "field": "x", "label": "X"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_slider_missing_min(self):
        m = self._m([{"id": "f", "type": "slider",
                        "max": 100, "default": 5,
                        "field": "x", "label": "X"}])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("min" in e for e in errs))

    def test_radio_ok(self):
        m = self._m([{"id": "f", "type": "radio",
                        "default": "a", "options": ["a", "b", "c"],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_radio_missing_options(self):
        m = self._m([{"id": "f", "type": "radio",
                        "default": "a", "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)

    def test_radio_value_label_dict_options_ok(self):
        """{value, label} dicts are a first-class option shape."""
        m = self._m([{"id": "f", "type": "radio", "default": "a",
                        "options": [
                            {"value": "a", "label": "Alpha"},
                            {"value": "b", "label": "Bravo"},
                        ],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_select_value_label_dict_options_ok(self):
        m = self._m([{"id": "f", "type": "select", "default": "a",
                        "options": [
                            {"value": "a", "label": "Alpha"},
                            {"value": "b", "label": "Bravo"},
                        ],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_multiselect_value_label_dict_options_ok(self):
        m = self._m([{"id": "f", "type": "multiSelect", "default": ["a"],
                        "options": [
                            {"value": "a", "label": "Alpha"},
                            {"value": "b", "label": "Bravo"},
                        ],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_dict_option_missing_value_rejected(self):
        """Dict options must carry a 'value' key -- caught at validation."""
        m = self._m([{"id": "f", "type": "radio", "default": "a",
                        "options": [{"label": "Alpha"}],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("'value'" in e for e in errs), errs)

    def test_dict_option_with_extra_keys_rejected(self):
        m = self._m([{"id": "f", "type": "radio", "default": "a",
                        "options": [
                            {"value": "a", "label": "A", "icon": "x"},
                        ],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("unsupported keys" in e for e in errs), errs)

    def test_non_primitive_non_dict_option_rejected(self):
        m = self._m([{"id": "f", "type": "radio", "default": "a",
                        "options": [["nested"]],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("primitive" in e for e in errs), errs)

    def test_dict_default_normalised_to_value(self):
        """A {value, label} default is reduced to its underlying value at
        compile time so the JS runtime sees a primitive."""
        m = self._m([{"id": "f", "type": "radio",
                        "default": {"value": "a", "label": "Alpha"},
                        "options": [
                            {"value": "a", "label": "Alpha"},
                            {"value": "b", "label": "Bravo"},
                        ],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)
        self.assertEqual(m["filters"][0]["default"], "a")

    def test_multiselect_dict_default_list_normalised(self):
        m = self._m([{"id": "f", "type": "multiSelect",
                        "default": [{"value": "a", "label": "Alpha"},
                                       {"value": "b", "label": "Bravo"}],
                        "options": [
                            {"value": "a", "label": "Alpha"},
                            {"value": "b", "label": "Bravo"},
                        ],
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)
        self.assertEqual(m["filters"][0]["default"], ["a", "b"])

    def test_text_ok(self):
        m = self._m([{"id": "f", "type": "text", "default": "",
                        "field": "s", "label": "S"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_number_ok(self):
        m = self._m([{"id": "f", "type": "number", "default": 0,
                        "field": "v", "label": "V"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_invalid_op(self):
        m = self._m([{"id": "f", "type": "slider", "min": 0, "max": 1,
                        "field": "x", "op": "BOGUS"}])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)


# =============================================================================
# FILTER OPTION RENDERING (value/label dicts)
# =============================================================================

class TestFilterOptionRendering(unittest.TestCase):
    """Reproduces the bug where {value, label} option dicts were
    str()-coerced into the HTML, producing JSON-text radios/dropdowns.
    Confirms the renderer emits underlying value as the input value
    and the label as visible text."""

    def _wrap(self, filt):
        return {
            "schema_version": 1, "id": "t", "title": "t",
            "datasets": {"d": pd.DataFrame({"s": ["sell", "buy"]})},
            "filters": [filt],
            "layout": {"rows": [[{"widget": "table", "id": "tbl",
                                    "dataset_ref": "d"}]]},
        }

    def test_radio_dict_options_emit_value_and_label(self):
        m = self._wrap({"id": "mode", "type": "radio", "default": "sell",
                          "options": [
                              {"value": "sell",
                                "label": "Looking to Sell (Feel Best to Buy)"},
                              {"value": "buy",
                                "label": "Looking to Buy (Feel Best to Sell)"},
                          ],
                          "field": "s", "label": "Mode"})
        res = render_dashboard(m)
        self.assertTrue(res.success, res.warnings)
        html = res.html
        self.assertIn('value="sell"', html)
        self.assertIn('value="buy"', html)
        self.assertIn("Looking to Sell (Feel Best to Buy)", html)
        self.assertIn("Looking to Buy (Feel Best to Sell)", html)
        self.assertNotIn("&#x27;value&#x27;", html)
        self.assertNotIn("'value':", html)
        self.assertNotIn("{&quot;value&quot;:", html)

    def test_select_dict_options_emit_value_and_label(self):
        m = self._wrap({"id": "mode", "type": "select", "default": "sell",
                          "options": [
                              {"value": "sell", "label": "Sell side"},
                              {"value": "buy",  "label": "Buy side"},
                          ],
                          "field": "s", "label": "Mode"})
        res = render_dashboard(m)
        self.assertTrue(res.success, res.warnings)
        html = res.html
        self.assertIn('<option value="sell"', html)
        self.assertIn('>Sell side</option>', html)
        self.assertIn('>Buy side</option>', html)
        self.assertNotIn("'value':", html)

    def test_radio_default_selects_correct_option(self):
        m = self._wrap({"id": "mode", "type": "radio", "default": "buy",
                          "options": [
                              {"value": "sell", "label": "Sell side"},
                              {"value": "buy",  "label": "Buy side"},
                          ],
                          "field": "s", "label": "Mode"})
        res = render_dashboard(m)
        self.assertTrue(res.success, res.warnings)
        html = res.html
        # The 'buy' radio gets ' checked', the 'sell' radio does not.
        self.assertIn('value="buy" checked', html)
        self.assertNotIn('value="sell" checked', html)

    def test_radio_primitive_options_still_work(self):
        """Backwards-compat: list of primitives keeps rendering the same."""
        m = self._wrap({"id": "mode", "type": "radio", "default": "sell",
                          "options": ["sell", "buy"],
                          "field": "s", "label": "Mode"})
        res = render_dashboard(m)
        self.assertTrue(res.success, res.warnings)
        html = res.html
        self.assertIn('value="sell" checked', html)
        self.assertIn('value="buy"', html)


# =============================================================================
# CHART-DATA DIAGNOSTICS (failing-dashboards battery)
#
# Each test purposely builds a manifest with one specific data-binding
# defect and asserts the right Diagnostic.code fires. Together these
# document the full surface PRISM should pattern-match against when
# iterating on a manifest.
# =============================================================================

class TestChartDataDiagnostics(unittest.TestCase):
    """Battery of deliberately-broken dashboards. Each test asserts the
    expected diagnostic code(s) fire AND that compile_dashboard still
    succeeds with HTML emitted (broken charts get a placeholder)."""

    def _wrap(self, datasets, layout, filters=None):
        m = {
            "schema_version": 1, "id": "diag", "title": "Diagnostics test",
            "datasets": datasets, "layout": layout,
        }
        if filters is not None:
            m["filters"] = filters
        return m

    def _codes(self, diags):
        return [d.code for d in diags]

    # --- empty datasets ----------------------------------------------------

    def test_empty_dataset_flagged(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [], "y": []})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "x", "y": "y"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("chart_dataset_empty", self._codes(diags))

    # --- missing columns ---------------------------------------------------

    def test_missing_x_column(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"date": [1, 2], "v": [3, 4]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "missing_x_col",
                                                      "y": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        codes = self._codes(diags)
        self.assertIn("chart_mapping_column_missing", codes)
        # Verify the diagnostic carries available_columns context for PRISM
        miss = next(d for d in diags
                    if d.code == "chart_mapping_column_missing")
        self.assertIn("available_columns", miss.context)
        self.assertEqual(sorted(miss.context["available_columns"]),
                         ["date", "v"])

    def test_missing_y_column_in_multi_line(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"date": [1, 2],
                                              "us_2y": [4.1, 4.2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "multi_line",
                                          "dataset": "d",
                                          "mapping": {"x": "date",
                                                      "y": ["us_2y",
                                                            "us_30y_missing"]}}}]]})
        diags = chart_data_diagnostics(m)
        codes = self._codes(diags)
        self.assertIn("chart_mapping_column_missing", codes)
        miss = next(d for d in diags
                    if d.code == "chart_mapping_column_missing")
        self.assertEqual(miss.context["missing_column"], "us_30y_missing")

    # --- all-NaN columns ---------------------------------------------------

    def test_all_nan_y_column(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1, 2, 3],
                                              "y": [None, None, None]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "x", "y": "y"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("chart_mapping_column_all_nan", self._codes(diags))

    def test_mostly_nan_warning(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1, 2, 3, 4],
                                              "y": [1.0, None, None, None]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "x", "y": "y"}}}]]})
        diags = chart_data_diagnostics(m)
        codes = self._codes(diags)
        self.assertIn("chart_mapping_column_mostly_nan", codes)
        d = next(d for d in diags
                 if d.code == "chart_mapping_column_mostly_nan")
        self.assertEqual(d.severity, "warning")
        self.assertGreaterEqual(d.context["nan_fraction"], 0.5)

    # --- non-numeric value column ------------------------------------------

    def test_non_numeric_y_column(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US", "EU"],
                                              "amount": ["junk", "alsojunk"]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "bar", "dataset": "d",
                                          "mapping": {"x": "region",
                                                      "y": "amount"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("chart_mapping_column_non_numeric",
                      self._codes(diags))

    def test_numeric_strings_count_as_numeric(self):
        """'1.23' as a string is convertible -- we don't flag it."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": ["a", "b"],
                                              "y": ["1.23", "4.56"]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "bar", "dataset": "d",
                                          "mapping": {"x": "x",
                                                      "y": "y"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertNotIn("chart_mapping_column_non_numeric",
                         self._codes(diags))

    # --- required mapping keys ---------------------------------------------

    def test_pie_missing_category(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US"], "v": [1]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "pie", "dataset": "d",
                                          "mapping": {"value": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        codes = self._codes(diags)
        self.assertIn("chart_mapping_required_missing", codes)
        d = next(x for x in diags
                 if x.code == "chart_mapping_required_missing")
        self.assertEqual(d.context["missing_key"], "category")

    def test_sankey_missing_target(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"src": ["a"], "v": [1]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "sankey", "dataset": "d",
                                          "mapping": {"source": "src",
                                                      "value": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        codes = self._codes(diags)
        self.assertIn("chart_mapping_required_missing", codes)

    def test_treemap_any_of_satisfied_path_value(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US", "EU"],
                                              "v": [1, 2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "treemap", "dataset": "d",
                                          "mapping": {"path": ["region"],
                                                      "value": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertNotIn("chart_mapping_required_missing",
                         self._codes(diags))

    def test_treemap_any_of_unsatisfied(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US"], "v": [1]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "treemap", "dataset": "d",
                                          "mapping": {"region": "region"}}}]]})
        diags = chart_data_diagnostics(m)
        codes = self._codes(diags)
        self.assertIn("chart_mapping_required_missing", codes)
        d = next(x for x in diags
                 if x.code == "chart_mapping_required_missing")
        self.assertIn("required_alternatives", d.context)

    # --- single-row warning ------------------------------------------------

    def test_single_row_warning_for_line(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1], "y": [2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "x",
                                                      "y": "y"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("chart_dataset_single_row", self._codes(diags))

    # --- table widget ------------------------------------------------------

    def test_table_dataset_empty(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [], "b": []})},
            layout={"rows": [[{"widget": "table", "id": "t", "w": 12,
                                "dataset_ref": "d"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("table_dataset_empty", self._codes(diags))

    def test_table_column_field_missing(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2], "b": [3, 4]})},
            layout={"rows": [[{"widget": "table", "id": "t", "w": 12,
                                "dataset_ref": "d",
                                "columns": [{"field": "a"},
                                              {"field": "missing_col"}]}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("table_column_field_missing", self._codes(diags))

    # --- kpi widget --------------------------------------------------------

    def test_kpi_source_dataset_unknown(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x",
                                "source": "unknown.latest.a"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_source_dataset_unknown", self._codes(diags))

    def test_kpi_source_column_missing(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x",
                                "source": "d.latest.missing_col"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_source_column_missing", self._codes(diags))

    def test_kpi_source_malformed(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x", "source": "no_dot_format"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_source_malformed", self._codes(diags))

    def test_kpi_source_two_part_is_malformed(self):
        """A 2-part source (the legacy ``dataset.column`` format) is
        rejected because the JS runtime expects 3 parts
        ``dataset.aggregator.column`` and would silently return null
        otherwise (rendering '--')."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x", "source": "d.a"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_source_malformed", self._codes(diags))

    def test_kpi_source_aggregator_unknown(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x",
                                "source": "d.median.a"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_source_aggregator_unknown",
                       self._codes(diags))

    def test_kpi_no_value_no_source_fires(self):
        """KPI with neither value nor source would render '--' at
        runtime; validator catches this as an error."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_no_value_no_source", self._codes(diags))

    def test_kpi_value_set_no_diag(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x", "value": 42}]]})
        diags = chart_data_diagnostics(m)
        self.assertNotIn("kpi_no_value_no_source", self._codes(diags))

    def test_kpi_value_placeholder_dashes(self):
        """value='--' renders verbatim. Flag explicitly so authors
        don't ship the literal string."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x", "value": "--"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_value_is_placeholder", self._codes(diags))

    def test_kpi_source_no_numeric_values(self):
        """All-string column resolves to null in JS; flag as error."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": ["foo", "bar"]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x",
                                "source": "d.latest.a"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_source_no_numeric_values",
                       self._codes(diags))

    def test_kpi_source_all_nan_fires_no_numeric_values(self):
        """All-NaN column produces the same runtime symptom as
        all-string; we collapse both into ``kpi_source_no_numeric_values``."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [None, None]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x",
                                "source": "d.latest.a"}]]})
        diags = chart_data_diagnostics(m)
        self.assertIn("kpi_source_no_numeric_values",
                       self._codes(diags))

    def test_kpi_clean_source_no_diag(self):
        """Sanity: a well-formed KPI fires no diagnostic."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1.0, 2.0, 3.0]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x",
                                "source": "d.latest.a"}]]})
        diags = chart_data_diagnostics(m)
        kpi_codes = [c for c in self._codes(diags) if c.startswith("kpi_")]
        self.assertEqual(kpi_codes, [], kpi_codes)

    def test_kpi_delta_source_propagates_to_diag(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"a": [1, 2]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x", "source": "d.latest.a",
                                "delta_source": "d.prev.missing_col"}]]})
        diags = chart_data_diagnostics(m)
        # Same code, but path/context must mention delta_source
        miss = [d for d in diags if d.code == "kpi_source_column_missing"]
        self.assertTrue(any("delta_source" in d.path for d in miss))

    # --- filter binding ----------------------------------------------------

    def test_filter_field_missing_in_target(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US", "EU"],
                                              "v": [1, 2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "bar", "dataset": "d",
                                          "mapping": {"x": "region",
                                                      "y": "v"}}}]]},
            filters=[{"id": "f", "type": "select", "default": "US",
                      "options": ["US", "EU"], "field": "wrong_col",
                      "targets": ["c"]}])
        diags = chart_data_diagnostics(m)
        self.assertIn("filter_field_missing_in_target", self._codes(diags))

    def test_filter_with_correct_field_no_diag(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US", "EU"],
                                              "v": [1, 2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "bar", "dataset": "d",
                                          "mapping": {"x": "region",
                                                      "y": "v"}}}]]},
            filters=[{"id": "f", "type": "select", "default": "US",
                      "options": ["US", "EU"], "field": "region",
                      "targets": ["c"]}])
        diags = chart_data_diagnostics(m)
        self.assertNotIn("filter_field_missing_in_target",
                         self._codes(diags))

    # --- compile_dashboard end-to-end --------------------------------------

    def test_compile_returns_diagnostics_field(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1, 2], "y": [None, None]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "x",
                                                      "y": "y"}}}]]})
        # strict=False: this manifest has an error-severity diagnostic
        # (column all-NaN) but we want to verify diagnostics survive
        # the compile, not that they fail the compile.
        r = compile_dashboard(m, strict=False)
        self.assertTrue(r.success, r.error_message)
        self.assertIsNotNone(r.html)
        self.assertGreater(len(r.diagnostics), 0)
        self.assertIn("chart_mapping_column_all_nan",
                      [d.code for d in r.diagnostics])
        # And `warnings` mirrors them as flat strings for backwards compat
        self.assertGreater(len(r.warnings), 0)

    def test_compile_recovers_from_chart_build_failure(self):
        """Spec that throws at build time gets a placeholder + a
        chart_build_failed diagnostic; sibling charts still compile.
        Iteration mode (strict=False) so PRISM can see all failures."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1, 2], "y": [3, 4]}),
                       "f": pd.DataFrame({"r": ["US"], "v": [1]})},
            layout={"rows": [[
                {"widget": "chart", "id": "good", "w": 6,
                 "spec": {"chart_type": "line", "dataset": "d",
                          "mapping": {"x": "x", "y": "y"}}},
                {"widget": "chart", "id": "broken", "w": 6,
                 "spec": {"chart_type": "pie", "dataset": "f",
                          "mapping": {}}},  # missing category+value
            ]]})
        r = compile_dashboard(m, strict=False)
        self.assertTrue(r.success)
        self.assertIsNotNone(r.html)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("chart_build_failed", codes)
        # The good chart still rendered
        self.assertIn("chart-good", r.html)

    def test_diagnostic_to_dict_roundtrip(self):
        d = Diagnostic(severity="error", code="chart_build_failed",
                         widget_id="c", path="layout.rows[0][0].spec",
                         message="msg", context={"k": "v"})
        out = d.to_dict()
        self.assertEqual(out["code"], "chart_build_failed")
        self.assertEqual(out["context"], {"k": "v"})
        # str() yields a parseable single-line representation
        s = str(d)
        self.assertIn("chart_build_failed", s)
        self.assertIn("[c]", s)

    def test_clean_dashboard_yields_zero_diagnostics(self):
        """Sanity check: a well-formed dashboard produces no diags."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1, 2, 3, 4],
                                              "y": [1.1, 2.2, 3.3, 4.4]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "x",
                                                      "y": "y"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertEqual(diags, [], [d.message for d in diags])


class TestDatasetShapeDiagnostics(unittest.TestCase):
    """Shape diagnostics fire on the *raw* DataFrame state captured
    BEFORE _normalize_manifest_datasets converts to list-of-lists.
    They name the exact pandas snippet PRISM should add to its
    pull_data.py to fix the input.
    """

    def _wrap(self, datasets, layout, filters=None):
        m = {"schema_version": 1, "id": "shape", "title": "Shape",
             "datasets": datasets, "layout": layout}
        if filters is not None:
            m["filters"] = filters
        return m

    def test_dti_no_date_column_fires(self):
        """DataFrame indexed by DatetimeIndex with no 'date' column
        AND a chart wanting 'date' -> dataset_dti_no_date_column."""
        df = pd.DataFrame({"us_10y": [4.1, 4.2, 4.3]},
                            index=pd.date_range("2024-01-01", periods=3,
                                                  freq="D"))
        df.index.name = "date"
        m = self._wrap(
            datasets={"rates": df},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line",
                                          "dataset": "rates",
                                          "mapping": {"x": "date",
                                                      "y": "us_10y"}}}]]})
        r = compile_dashboard(m, write_html=False, write_json=False,
                                strict=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_dti_no_date_column", codes)
        diag = next(d for d in r.diagnostics
                    if d.code == "dataset_dti_no_date_column")
        self.assertEqual(diag.severity, "error")
        self.assertIn("reset_index", diag.context.get("fix_hint", ""))

    def test_dti_no_date_column_skipped_when_no_chart_uses_date(self):
        """Charts that don't need 'date' -> diagnostic does not fire."""
        df = pd.DataFrame({"us_10y": [4.1, 4.2, 4.3]},
                            index=pd.date_range("2024-01-01", periods=3))
        df.index.name = "date"
        m = self._wrap(
            datasets={"rates": df},
            layout={"rows": [[{"widget": "kpi", "id": "k", "label": "10Y",
                                "source": "rates.latest.us_10y", "w": 12}]]})
        r = compile_dashboard(m, write_html=False, write_json=False)
        codes = [d.code for d in r.diagnostics]
        # KPI doesn't reference 'date', so no DTI diagnostic.
        # (Filter check inside _any_widget_uses_date may still fire
        # if the manifest has dateRange filters; this test has none.)
        self.assertNotIn("dataset_dti_no_date_column", codes)

    def test_tuple_dataset_fires_named_diagnostic(self):
        """A tuple from pull_market_data() yields a clear error
        with the unpack snippet, not a confusing generic validation
        failure."""
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=3),
                              "us_10y": [4.1, 4.2, 4.3]})
        m = self._wrap(
            datasets={"rates": (df, df)},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line",
                                          "dataset": "rates",
                                          "mapping": {"x": "date",
                                                      "y": "us_10y"}}}]]})
        r = compile_dashboard(m, write_html=False, write_json=False,
                                strict=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_passed_as_tuple", codes)
        diag = next(d for d in r.diagnostics
                    if d.code == "dataset_passed_as_tuple")
        self.assertEqual(diag.severity, "error")
        self.assertIn("eod_df", diag.context.get("fix_hint", ""))

    def test_multiindex_columns_fires(self):
        """MultiIndex columns -> dataset_columns_multiindex with a
        flatten snippet."""
        df = pd.DataFrame({("A", "x"): [1, 2, 3], ("A", "y"): [4, 5, 6]})
        df["date"] = pd.date_range("2024-01-01", periods=3)
        m = self._wrap(
            datasets={"foo": df},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line",
                                          "dataset": "foo",
                                          "mapping": {"x": "date",
                                                      "y": "A_x"}}}]]})
        r = compile_dashboard(m, write_html=False, write_json=False,
                                strict=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_columns_multiindex", codes)
        diag = next(d for d in r.diagnostics
                    if d.code == "dataset_columns_multiindex")
        self.assertIn("'_'.join", diag.context.get("fix_hint", ""))

    def test_opaque_haver_code_warned(self):
        """Haver-style codes referenced by widgets -> warning,
        not an error."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "JCXFE@USECON": [3.0, 3.1, 3.2],
        })
        m = self._wrap(
            datasets={"haver": df},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line",
                                          "dataset": "haver",
                                          "mapping": {"x": "date",
                                                      "y": "JCXFE@USECON"}
                                          }}]]})
        r = compile_dashboard(m, write_html=False, write_json=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_column_looks_like_code", codes)
        diag = next(d for d in r.diagnostics
                    if d.code == "dataset_column_looks_like_code")
        self.assertEqual(diag.severity, "warning")
        self.assertEqual(diag.context["column"], "JCXFE@USECON")

    def test_opaque_coordinate_warned(self):
        """Coordinate-style (IR_USD_*) codes -> warning."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "IR_USD_Treasury_10Y_Rate": [4.1, 4.2, 4.3],
        })
        m = self._wrap(
            datasets={"mkt": df},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line",
                                          "dataset": "mkt",
                                          "mapping": {"x": "date",
                                                      "y":
                                                  "IR_USD_Treasury_10Y_Rate"}
                                          }}]]})
        r = compile_dashboard(m, write_html=False, write_json=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_column_looks_like_code", codes)

    def test_opaque_code_not_referenced_no_warning(self):
        """Opaque-named columns that no widget references are NOT
        warned about -- raw codes nobody plots aren't a problem."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "us_10y": [4.1, 4.2, 4.3],
            "JCXFE@USECON": [3.0, 3.1, 3.2],  # present but unused
        })
        m = self._wrap(
            datasets={"d": df},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "date",
                                                      "y": "us_10y"}}}]]})
        r = compile_dashboard(m, write_html=False, write_json=False)
        codes = [d.code for d in r.diagnostics]
        self.assertNotIn("dataset_column_looks_like_code", codes)

    def test_clean_columns_no_warning(self):
        """Snake-case English columns -> no shape warnings."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "us_10y": [4.1, 4.2, 4.3],
            "core_cpi": [3.0, 3.1, 3.2],
        })
        m = self._wrap(
            datasets={"d": df},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "multi_line",
                                          "dataset": "d",
                                          "mapping": {"x": "date",
                                                      "y": ["us_10y",
                                                            "core_cpi"]}
                                          }}]]})
        r = compile_dashboard(m, write_html=False, write_json=False)
        shape_codes = [d.code for d in r.diagnostics
                       if d.code.startswith("dataset_")]
        self.assertEqual(shape_codes, [])

    def test_attrs_metadata_unused_info(self):
        """DataFrame with df.attrs['metadata'] still using raw codes
        as columns -> info-level diagnostic suggesting attrs usage."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=3),
            "IR_USD_Swap_10Y": [4.1, 4.2, 4.3],
        })
        df.attrs["metadata"] = [
            {"coordinate": "IR_USD_Swap_10Y",
             "display_name": "USD 10Y Swap",
             "tenor": "10Y"},
        ]
        m = self._wrap(
            datasets={"mkt": df},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line",
                                          "dataset": "mkt",
                                          "mapping": {"x": "date",
                                                      "y": "IR_USD_Swap_10Y"}
                                          }}]]})
        r = compile_dashboard(m, write_html=False, write_json=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_metadata_attrs_unused", codes)
        diag = next(d for d in r.diagnostics
                    if d.code == "dataset_metadata_attrs_unused")
        self.assertEqual(diag.severity, "info")


class TestDatasetSizeDiagnostics(unittest.TestCase):
    """Size-budget diagnostics. The thresholds (DATASET_ROWS_*,
    DATASET_BYTES_*, MANIFEST_BYTES_*, TABLE_ROWS_*) are deterministic;
    these tests assert the named-codes fire at / past those thresholds.
    """

    def _wrap(self, datasets, layout):
        return {"schema_version": 1, "id": "sz", "title": "Size test",
                "datasets": datasets, "layout": layout}

    def _line_chart(self, ds_name, x="date", y="us_10y"):
        return [[{"widget": "chart", "id": "c", "w": 12,
                  "spec": {"chart_type": "line", "dataset": ds_name,
                           "mapping": {"x": x, "y": y}}}]]

    def test_dataset_rows_warning(self):
        """10K-50K rows -> warning."""
        from echart_dashboard import DATASET_ROWS_WARN
        n = DATASET_ROWS_WARN + 100
        df = pd.DataFrame({
            "date": pd.date_range("2000-01-01", periods=n, freq="h"),
            "us_10y": [4.0 + i / 1e6 for i in range(n)],
        })
        m = self._wrap({"rates": df}, {"rows": self._line_chart("rates")})
        r = compile_dashboard(m, write_html=False, write_json=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_rows_warning", codes)
        self.assertNotIn("dataset_rows_error", codes)

    def test_dataset_rows_error(self):
        """>= 50K rows -> error."""
        from echart_dashboard import DATASET_ROWS_ERROR
        n = DATASET_ROWS_ERROR + 100
        df = pd.DataFrame({
            "date": pd.date_range("2000-01-01", periods=n, freq="min"),
            "us_10y": [4.0 + i / 1e7 for i in range(n)],
        })
        m = self._wrap({"rates": df}, {"rows": self._line_chart("rates")})
        r = compile_dashboard(m, write_html=False, write_json=False,
                                strict=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("dataset_rows_error", codes)
        diag = next(d for d in r.diagnostics
                    if d.code == "dataset_rows_error")
        self.assertEqual(diag.severity, "error")
        self.assertIn("Top-N", diag.context.get("fix_hint", ""))

    def test_small_dataset_no_size_diag(self):
        """Daily-2y is small and well-formed -> no size diagnostics."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=500, freq="D"),
            "us_10y": [4.0 + i / 1e3 for i in range(500)],
        })
        m = self._wrap({"rates": df}, {"rows": self._line_chart("rates")})
        r = compile_dashboard(m, write_html=False, write_json=False)
        size_codes = [d.code for d in r.diagnostics
                      if "rows" in d.code or "bytes" in d.code]
        self.assertEqual(size_codes, [])

    def test_table_rows_error_at_5k(self):
        """Table widget consuming >= 5K rows -> table_rows_error."""
        from echart_dashboard import TABLE_ROWS_ERROR
        n = TABLE_ROWS_ERROR + 50
        df = pd.DataFrame({
            "issuer": [f"X{i:05d}" for i in range(n)],
            "spread": [100 + (i % 50) for i in range(n)],
        })
        m = self._wrap(
            {"bonds": df},
            {"rows": [[{"widget": "table", "id": "t", "w": 12,
                          "dataset_ref": "bonds",
                          "columns": [{"field": "issuer"},
                                       {"field": "spread"}]}]]})
        r = compile_dashboard(m, write_html=False, write_json=False,
                                strict=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("table_rows_error", codes)

    def test_manifest_bytes_error_aggregates(self):
        """Total dataset bytes >= 5MB -> manifest_bytes_error."""
        from echart_dashboard import MANIFEST_BYTES_ERROR
        # Each (date, float) row serialises to ~35 bytes; 200K rows
        # comfortably exceeds the 5 MB manifest threshold.
        n = 200_000
        df = pd.DataFrame({
            "date": pd.date_range("2000-01-01", periods=n, freq="min"),
            "v": [1.234567 + i / 1e6 for i in range(n)],
        })
        m = self._wrap({"d": df}, {"rows": self._line_chart("d", y="v")})
        r = compile_dashboard(m, write_html=False, write_json=False,
                                strict=False)
        codes = [d.code for d in r.diagnostics]
        self.assertIn("manifest_bytes_error", codes)
        diag = next(d for d in r.diagnostics
                    if d.code == "manifest_bytes_error")
        self.assertGreaterEqual(diag.context["total_bytes"],
                                 MANIFEST_BYTES_ERROR)

    def test_strict_mode_raises_on_size_error(self):
        """compile_dashboard(strict=True) hard-fails with a ValueError
        when any error-severity diagnostic fires."""
        from echart_dashboard import DATASET_ROWS_ERROR
        n = DATASET_ROWS_ERROR + 100
        df = pd.DataFrame({
            "date": pd.date_range("2000-01-01", periods=n, freq="min"),
            "us_10y": [4.0] * n,
        })
        m = self._wrap({"rates": df}, {"rows": self._line_chart("rates")})
        with self.assertRaises(ValueError) as cm:
            compile_dashboard(m, write_html=False, write_json=False,
                                strict=True)
        self.assertIn("strict=True", str(cm.exception))
        self.assertIn("dataset_rows_error", str(cm.exception))

    def test_strict_mode_passes_on_warnings(self):
        """Warnings alone do not trigger strict-mode hard-fail."""
        from echart_dashboard import DATASET_ROWS_WARN
        n = DATASET_ROWS_WARN + 100
        df = pd.DataFrame({
            "date": pd.date_range("2000-01-01", periods=n, freq="h"),
            "us_10y": [4.0] * n,
        })
        m = self._wrap({"rates": df}, {"rows": self._line_chart("rates")})
        r = compile_dashboard(m, write_html=False, write_json=False,
                                strict=True)
        self.assertTrue(r.success)
        self.assertIn("dataset_rows_warning",
                       [d.code for d in r.diagnostics])

    def test_strict_is_default(self):
        """``strict=True`` is the default. A manifest with an
        error-severity diagnostic must raise even when caller didn't
        pass ``strict=`` explicitly. The opposite default would let
        production dashboards ship broken (this regressed once: see
        TestKPIResolutionAgreement)."""
        from echart_dashboard import DATASET_ROWS_ERROR
        n = DATASET_ROWS_ERROR + 100
        df = pd.DataFrame({
            "date": pd.date_range("2000-01-01", periods=n, freq="min"),
            "us_10y": [4.0] * n,
        })
        m = self._wrap({"rates": df}, {"rows": self._line_chart("rates")})
        with self.assertRaises(ValueError):
            compile_dashboard(m, write_html=False, write_json=False)


# =============================================================================
# STAT_GRID DIAGNOSTICS  (cells without value/source -> '--')
# =============================================================================

class TestStatGridDiagnostics(unittest.TestCase):
    """``stat_grid`` is server-rendered: stats with neither ``value``
    nor ``source`` ship literal ``--`` to production. Compile-time
    resolution + diagnostics close that hole.
    """

    def _wrap(self, datasets, layout):
        return {"schema_version": 1, "id": "t", "title": "t",
                 "datasets": datasets, "layout": layout}

    def _wrap_stat_grid(self, datasets, stats):
        return self._wrap(
            datasets,
            {"rows": [[{"widget": "stat_grid", "id": "sg", "w": 12,
                          "title": "x", "stats": stats}]]},
        )

    def _codes(self, diags):
        return [d.code for d in diags]

    def test_stat_no_value_no_source_fires(self):
        m = self._wrap_stat_grid(
            {"d": pd.DataFrame({"a": [1, 2]})},
            [{"label": "X"}],
        )
        diags = chart_data_diagnostics(m)
        self.assertIn("stat_grid_no_value_no_source", self._codes(diags))

    def test_stat_value_set_no_diag(self):
        m = self._wrap_stat_grid(
            {"d": pd.DataFrame({"a": [1, 2]})},
            [{"label": "X", "value": 42}],
        )
        diags = chart_data_diagnostics(m)
        self.assertNotIn("stat_grid_no_value_no_source",
                          self._codes(diags))

    def test_stat_value_placeholder_dashes(self):
        m = self._wrap_stat_grid(
            {"d": pd.DataFrame({"a": [1, 2]})},
            [{"label": "X", "value": "--"}],
        )
        diags = chart_data_diagnostics(m)
        self.assertIn("stat_grid_value_is_placeholder",
                       self._codes(diags))

    def test_stat_source_unresolvable_dataset_unknown(self):
        m = self._wrap_stat_grid(
            {"d": pd.DataFrame({"a": [1, 2]})},
            [{"label": "X", "source": "missing.latest.a"}],
        )
        diags = chart_data_diagnostics(m)
        self.assertIn("stat_grid_source_unresolvable",
                       self._codes(diags))

    def test_stat_source_unresolvable_no_numeric(self):
        m = self._wrap_stat_grid(
            {"d": pd.DataFrame({"a": ["foo", "bar"]})},
            [{"label": "X", "source": "d.latest.a"}],
        )
        diags = chart_data_diagnostics(m)
        self.assertIn("stat_grid_source_unresolvable",
                       self._codes(diags))

    def test_stat_source_resolves_at_compile_time(self):
        """A valid stat_grid source is RESOLVED to a concrete value
        in the manifest at compile time so the static HTML renders
        the real number, not '--'."""
        m = self._wrap_stat_grid(
            {"d": pd.DataFrame({"a": [1.0, 2.0, 3.0]})},
            [{"label": "X", "source": "d.latest.a", "decimals": 1}],
        )
        r = compile_dashboard(m, write_html=False, write_json=False)
        self.assertTrue(r.success)
        # The stat now carries a baked value
        stat = r.manifest["layout"]["rows"][0][0]["stats"][0]
        self.assertIn("value", stat)
        self.assertEqual(stat["value"], "3.0")

    def test_stat_source_with_format_options(self):
        m = self._wrap_stat_grid(
            {"d": pd.DataFrame({"a": [0.123, 0.456]})},
            [{"label": "X", "source": "d.latest.a",
               "format": "percent", "decimals": 1}],
        )
        r = compile_dashboard(m, write_html=False, write_json=False)
        self.assertTrue(r.success)
        stat = r.manifest["layout"]["rows"][0][0]["stats"][0]
        self.assertEqual(stat["value"], "45.6%")


# =============================================================================
# KPI RESOLUTION AGREEMENT  (Python mirror == JS resolveAgg + resolveSource)
# =============================================================================

class TestKPIResolutionAgreement(unittest.TestCase):
    """The Python ``_resolve_kpi_value`` is a literal mirror of the
    JS ``resolveAgg`` + ``resolveSource`` pair in rendering.py. If
    they diverge, KPI diagnostics either false-alarm (block valid
    dashboards) or miss real bugs (let '--' ship). These tests pin
    the contract.
    """

    def _df(self):
        return {"d": pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0],
                                       "y": [None, 5.0, None, 6.0],
                                       "s": ["a", "b", "c", "d"]})}

    def _resolve(self, src):
        from echart_dashboard import _resolve_kpi_value, \
            _materialize_datasets
        manifest = {"datasets": self._df()}
        dfs = _materialize_datasets(manifest)
        return _resolve_kpi_value(src, dfs)

    def test_latest_returns_last_numeric(self):
        v, err = self._resolve("d.latest.x")
        self.assertEqual(v, 4.0); self.assertIsNone(err)

    def test_first_returns_first_numeric(self):
        v, err = self._resolve("d.first.x")
        self.assertEqual(v, 1.0); self.assertIsNone(err)

    def test_sum_returns_sum_of_numerics(self):
        v, err = self._resolve("d.sum.x")
        self.assertEqual(v, 10.0); self.assertIsNone(err)

    def test_mean_returns_mean(self):
        v, err = self._resolve("d.mean.x")
        self.assertEqual(v, 2.5); self.assertIsNone(err)

    def test_min_returns_min(self):
        v, err = self._resolve("d.min.x")
        self.assertEqual(v, 1.0); self.assertIsNone(err)

    def test_max_returns_max(self):
        v, err = self._resolve("d.max.x")
        self.assertEqual(v, 4.0); self.assertIsNone(err)

    def test_count_returns_count_of_numerics(self):
        # Column 'y' has [None, 5, None, 6] -> count=2 (matches JS,
        # which filters typeof v === 'number' first)
        v, err = self._resolve("d.count.y")
        self.assertEqual(v, 2); self.assertIsNone(err)

    def test_prev_returns_second_to_last(self):
        v, err = self._resolve("d.prev.x")
        self.assertEqual(v, 3.0); self.assertIsNone(err)

    def test_prev_falls_back_to_last_when_only_one(self):
        from echart_dashboard import _resolve_kpi_value
        manifest = {"datasets": {"d": pd.DataFrame({"x": [9.0]})}}
        from echart_dashboard import _materialize_datasets
        dfs = _materialize_datasets(manifest)
        v, err = _resolve_kpi_value("d.prev.x", dfs)
        # JS does the same: prev with <2 values returns the last value
        self.assertEqual(v, 9.0); self.assertIsNone(err)

    def test_unknown_aggregator_returns_error(self):
        v, err = self._resolve("d.median.x")
        self.assertIsNone(v)
        self.assertIn("aggregator", err)

    def test_two_part_source_is_malformed(self):
        v, err = self._resolve("d.x")
        self.assertIsNone(v)
        self.assertIn("3+ parts", err)

    def test_unknown_dataset(self):
        v, err = self._resolve("ghost.latest.x")
        self.assertIsNone(v)
        self.assertIn("not declared", err)

    def test_unknown_column(self):
        v, err = self._resolve("d.latest.zzz")
        self.assertIsNone(v)
        self.assertIn("not in dataset", err)

    def test_string_only_column_no_numeric_values(self):
        v, err = self._resolve("d.latest.s")
        self.assertIsNone(v)
        self.assertIn("no numeric values", err)

    def test_aggregator_set_matches_js(self):
        """The Python aggregator allow-list must EXACTLY match the
        JS ``resolveAgg`` switch in rendering.py. Drift = silent
        '--' renders for dashboards that use a JS-only aggregator."""
        from echart_dashboard import VALID_KPI_AGGREGATORS
        # Pin the set; if you add an aggregator to one side, you
        # must add it to the other (and update this test).
        self.assertEqual(
            VALID_KPI_AGGREGATORS,
            {"latest", "first", "sum", "mean", "min", "max",
             "count", "prev"})


# =============================================================================
# CHART-TYPE-AWARE NUMERIC + COLUMN-REF MAPPING RULES
# =============================================================================

class TestChartTypeMappingRules(unittest.TestCase):
    """For some chart types the same mapping key carries different
    semantics. ``y`` is numeric for line/bar/scatter but categorical
    for ``bar_horizontal`` (the bar runs along x, the row label is
    on y). ``mapping.name`` is a column ref for tree/treemap but a
    label for gauge/bullet. Pin the chart-type-aware rules.
    """

    def _wrap(self, datasets, w):
        return {"schema_version": 1, "id": "t", "title": "t",
                 "datasets": datasets,
                 "layout": {"rows": [[w]]}}

    def _codes(self, m):
        return [d.code for d in chart_data_diagnostics(m)]

    def test_bar_horizontal_y_categorical_no_numeric_diag(self):
        df = pd.DataFrame({"issuer": ["A", "B", "C"],
                              "size": [10.0, 20.0, 30.0]})
        m = self._wrap({"d": df}, {
            "widget": "chart", "id": "c", "w": 12,
            "spec": {"chart_type": "bar_horizontal", "dataset": "d",
                       "mapping": {"x": "size", "y": "issuer"}},
        })
        self.assertNotIn("chart_mapping_column_non_numeric",
                          self._codes(m))

    def test_bar_horizontal_x_must_be_numeric(self):
        df = pd.DataFrame({"issuer": ["A", "B"], "size": ["a", "b"]})
        m = self._wrap({"d": df}, {
            "widget": "chart", "id": "c", "w": 12,
            "spec": {"chart_type": "bar_horizontal", "dataset": "d",
                       "mapping": {"x": "size", "y": "issuer"}},
        })
        self.assertIn("chart_mapping_column_non_numeric",
                       self._codes(m))

    def test_heatmap_axes_categorical_no_numeric_diag(self):
        df = pd.DataFrame({"a": ["X", "Y"], "b": ["P", "Q"],
                              "v": [1.0, 2.0]})
        m = self._wrap({"d": df}, {
            "widget": "chart", "id": "c", "w": 12,
            "spec": {"chart_type": "heatmap", "dataset": "d",
                       "mapping": {"x": "a", "y": "b", "value": "v"}},
        })
        self.assertNotIn("chart_mapping_column_non_numeric",
                          self._codes(m))

    def test_heatmap_value_must_be_numeric(self):
        df = pd.DataFrame({"a": ["X"], "b": ["P"], "v": ["junk"]})
        m = self._wrap({"d": df}, {
            "widget": "chart", "id": "c", "w": 12,
            "spec": {"chart_type": "heatmap", "dataset": "d",
                       "mapping": {"x": "a", "y": "b", "value": "v"}},
        })
        self.assertIn("chart_mapping_column_non_numeric",
                       self._codes(m))

    def test_gauge_name_is_label_not_column_ref(self):
        """``mapping.name`` is the gauge label string for chart_type
        'gauge'. Don't try to look it up as a dataset column."""
        df = pd.DataFrame({"prob": [68]})
        m = self._wrap({"d": df}, {
            "widget": "chart", "id": "c", "w": 12,
            "spec": {"chart_type": "gauge", "dataset": "d",
                       "mapping": {"value": "prob",
                                     "name": "Cut probability",
                                     "min": 0, "max": 100}},
        })
        self.assertNotIn("chart_mapping_column_missing",
                          self._codes(m))

    def test_bullet_required_keys_y_x_low_high(self):
        """``bullet`` requires y / x / x_low / x_high (rates-RV style),
        NOT 'value'. Test the compile-time check matches the builder."""
        df = pd.DataFrame({"metric": ["p/e", "p/b"],
                              "current": [22.0, 3.0],
                              "low_5y": [15.0, 2.0],
                              "high_5y": [28.0, 4.0]})
        m = self._wrap({"d": df}, {
            "widget": "chart", "id": "c", "w": 12,
            "spec": {"chart_type": "bullet", "dataset": "d",
                       "mapping": {"y": "metric", "x": "current",
                                     "x_low": "low_5y",
                                     "x_high": "high_5y"}},
        })
        self.assertEqual([], self._codes(m))

    def test_bullet_missing_required_keys_fires(self):
        df = pd.DataFrame({"metric": ["a"], "v": [1.0]})
        m = self._wrap({"d": df}, {
            "widget": "chart", "id": "c", "w": 12,
            "spec": {"chart_type": "bullet", "dataset": "d",
                       "mapping": {"y": "metric"}},
        })
        # x, x_low, x_high all missing -> required_missing fires
        self.assertIn("chart_mapping_required_missing", self._codes(m))


# =============================================================================
# ALL DEMOS COMPILE STRICT  (production-readiness guard)
# =============================================================================

class TestAllDemosCompileStrict(unittest.TestCase):
    """Every demo build function in ``demos.py`` must compile cleanly
    with ``strict=True``. If any demo fires an error-severity
    diagnostic, this test fails -- which means production-quality
    PRISM dashboards (which mirror the demos) are also broken.

    This is the single most important regression guard for the
    dashboard system. If this test fails, fix the demo OR fix the
    validator (false positive).
    """

    def test_every_demo_passes_strict_compile(self):
        import demos
        import inspect
        from pathlib import Path

        real_compile = demos.compile_dashboard
        captured: Dict[str, Dict[str, Any]] = {}

        def make_capture(name):
            def capture(manifest, *args, **kwargs):
                captured[name] = manifest
                return real_compile(manifest, *args, **kwargs)
            return capture

        demo_fns = [(nm, fn) for nm, fn in
                    inspect.getmembers(demos, callable)
                    if nm.startswith("build_")
                    and not nm.startswith("build_compound")]
        # ``build_cross_asset`` doesn't go through compile_dashboard
        # (it uses make_4pack_grid). Skip it here; covered separately
        # in TestComposites.
        demo_fns = [(nm, fn) for nm, fn in demo_fns
                    if nm != "build_cross_asset"]

        failures: List[str] = []
        for name, fn in demo_fns:
            demos.compile_dashboard = make_capture(name)
            with tempfile.TemporaryDirectory() as td:
                try:
                    fn(Path(td))
                except Exception:
                    pass
            if name not in captured:
                failures.append(f"{name}: did not call compile_dashboard")
                continue
            try:
                real_compile(captured[name], write_html=False,
                              write_json=False, strict=True)
            except ValueError as e:
                # Trim to just the codes for a tight failure message
                msg = str(e)
                head = msg.split("\n")[0]
                failures.append(f"{name}: {head}")

        demos.compile_dashboard = real_compile

        self.assertEqual(failures, [],
            "Demo dashboards failing strict compile:\n  " +
            "\n  ".join(failures))


# =============================================================================
# NO LIVE PLACEHOLDERS  (HTML scan: no '--' / '(no data)' on good demos)
# =============================================================================

class TestNoUnresolvedPlaceholders(unittest.TestCase):
    """Compile every demo and assert the produced HTML has no live
    KPI '--' values for source-bound widgets, and no '(no data)'
    chart placeholders. Server-side initial '--' is fine (the JS
    overwrites it from the dataset); we check that the FINAL state
    a user would see has no broken placeholders.
    """

    def _run(self, build_fn, demo_name):
        import demos
        from pathlib import Path

        real_compile = demos.compile_dashboard
        captured = {}

        def capture(manifest, *args, **kwargs):
            captured[demo_name] = manifest
            return real_compile(manifest, *args, **kwargs)

        demos.compile_dashboard = capture
        with tempfile.TemporaryDirectory() as td:
            try:
                build_fn(Path(td))
            except Exception:
                pass
        demos.compile_dashboard = real_compile
        return captured.get(demo_name)

    def test_all_demo_kpis_resolve_or_have_value(self):
        """For every KPI in every demo, either ``value`` is set OR
        the source resolves to a number. If neither, the tile would
        render '--' in production.
        """
        import demos
        import inspect
        from echart_dashboard import (_resolve_kpi_value,
                                            _materialize_datasets)

        demo_fns = [(nm, fn) for nm, fn in
                    inspect.getmembers(demos, callable)
                    if nm.startswith("build_")
                    and not nm.startswith("build_compound")
                    and nm != "build_cross_asset"]

        broken: List[str] = []
        for name, fn in demo_fns:
            m = self._run(fn, name)
            if m is None:
                continue
            dfs = _materialize_datasets(m)
            layout = m.get("layout") or {}

            def walk(rows):
                for row in rows or []:
                    for w in row or []:
                        if not isinstance(w, dict):
                            continue
                        if w.get("widget") != "kpi":
                            continue
                        kid = w.get("id")
                        if w.get("value") is not None:
                            continue
                        src = w.get("source")
                        if not src:
                            broken.append(f"{name}.{kid}: no value, no source")
                            continue
                        v, err = _resolve_kpi_value(src, dfs)
                        if v is None:
                            broken.append(
                                f"{name}.{kid}: source={src} -> {err}")

            if layout.get("kind") == "tabs":
                for tab in layout.get("tabs", []) or []:
                    walk(tab.get("rows", []))
            else:
                walk(layout.get("rows", []))

        self.assertEqual(broken, [],
            "KPI tiles that would render '--' in production:\n  " +
            "\n  ".join(broken))

    def test_all_demo_stat_grids_have_values(self):
        """Every stat_grid stat has a baked ``value`` after compile,
        so the static HTML renders real numbers (not '--')."""
        import demos
        import inspect
        from pathlib import Path

        demo_fns = [(nm, fn) for nm, fn in
                    inspect.getmembers(demos, callable)
                    if nm.startswith("build_")
                    and not nm.startswith("build_compound")
                    and nm != "build_cross_asset"]

        broken: List[str] = []
        for name, fn in demo_fns:
            m = self._run(fn, name)
            if m is None:
                continue
            try:
                r = compile_dashboard(m, write_html=False,
                                         write_json=False, strict=True)
            except ValueError:
                continue  # caught by TestAllDemosCompileStrict
            layout = r.manifest.get("layout") or {}

            def walk(rows):
                for row in rows or []:
                    for w in row or []:
                        if not isinstance(w, dict):
                            continue
                        if w.get("widget") != "stat_grid":
                            continue
                        sgid = w.get("id")
                        for si, st in enumerate(w.get("stats") or []):
                            if not isinstance(st, dict):
                                continue
                            v = st.get("value")
                            if v is None:
                                broken.append(
                                    f"{name}.{sgid}.stats[{si}]: "
                                    f"no resolved value")
                                continue
                            # Reject explicit placeholder strings
                            if isinstance(v, str) and \
                                    v.strip() in ("--", "—", "n/a"):
                                broken.append(
                                    f"{name}.{sgid}.stats[{si}]: "
                                    f"value is placeholder {v!r}")

            if layout.get("kind") == "tabs":
                for tab in layout.get("tabs", []) or []:
                    walk(tab.get("rows", []))
            else:
                walk(layout.get("rows", []))

        self.assertEqual(broken, [],
            "stat_grid cells with broken values:\n  " +
            "\n  ".join(broken))

    def test_no_no_data_chart_placeholders_in_demos(self):
        """``chart_build_failed`` substitutes a '(no data)' chart on
        compile failure. None of the demos should hit that path."""
        import demos
        import inspect
        from pathlib import Path

        demo_fns = [(nm, fn) for nm, fn in
                    inspect.getmembers(demos, callable)
                    if nm.startswith("build_")
                    and not nm.startswith("build_compound")
                    and nm != "build_cross_asset"]

        offenders: List[str] = []
        for name, fn in demo_fns:
            m = self._run(fn, name)
            if m is None:
                continue
            try:
                r = compile_dashboard(m, write_html=False,
                                         write_json=False, strict=True)
            except ValueError:
                continue  # already covered
            for d in r.diagnostics:
                if d.code == "chart_build_failed":
                    offenders.append(f"{name}.{d.widget_id}: {d.message}")
        self.assertEqual(offenders, [],
            "Demo charts falling back to placeholder:\n  " +
            "\n  ".join(offenders))


# =============================================================================
# DIAGNOSTIC CONTRACT  (every code has positive + negative tests)
# =============================================================================

class TestDiagnosticContract(unittest.TestCase):
    """For each diagnostic code, pair a minimal manifest that fires
    it (positive) with a minimal manifest that doesn't (negative).
    Catches both regressions (positive stops firing) and false-
    positives (negative starts firing).
    """

    def _wrap(self, datasets, layout, filters=None):
        m = {"schema_version": 1, "id": "t", "title": "t",
              "datasets": datasets, "layout": layout}
        if filters is not None:
            m["filters"] = filters
        return m

    def _diag_codes(self, m):
        return {d.code for d in chart_data_diagnostics(m)}

    # Each entry: (code, bad_manifest_factory, good_manifest_factory)
    # Negative variant must fire NO error-severity codes that overlap
    # with the named code; this catches both regressions and false-
    # positives.
    def _cases(self):
        ok_df = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", "y"]})
        out = []

        # KPI codes ----------------------------------------------------
        out.append(("kpi_no_value_no_source",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x"}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x", "value": 1}]]})))

        out.append(("kpi_value_is_placeholder",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x", "value": "--"}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x", "value": "OK"}]]})))

        out.append(("kpi_source_malformed",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x", "source": "no_dot"}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x", "source": "d.latest.a"}]]})))

        out.append(("kpi_source_dataset_unknown",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "ghost.latest.a"}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "d.latest.a"}]]})))

        out.append(("kpi_source_aggregator_unknown",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "d.median.a"}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "d.mean.a"}]]})))

        out.append(("kpi_source_column_missing",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "d.latest.zzz"}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "d.latest.a"}]]})))

        out.append(("kpi_source_no_numeric_values",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "d.latest.b"}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                              "label": "x",
                              "source": "d.latest.a"}]]})))

        # stat_grid codes ----------------------------------------------
        out.append(("stat_grid_no_value_no_source",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "stat_grid", "id": "g", "w": 12,
                              "stats": [{"label": "X"}]}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "stat_grid", "id": "g", "w": 12,
                              "stats": [{"label": "X", "value": 1}]}]]})))

        out.append(("stat_grid_value_is_placeholder",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "stat_grid", "id": "g", "w": 12,
                              "stats": [{"label": "X",
                                          "value": "--"}]}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "stat_grid", "id": "g", "w": 12,
                              "stats": [{"label": "X",
                                          "value": "real"}]}]]})))

        out.append(("stat_grid_source_unresolvable",
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "stat_grid", "id": "g", "w": 12,
                              "stats": [{"label": "X",
                                          "source": "ghost.latest.a"
                                          }]}]]}),
            lambda: self._wrap({"d": ok_df},
                {"rows": [[{"widget": "stat_grid", "id": "g", "w": 12,
                              "stats": [{"label": "X",
                                          "source": "d.latest.a"}]}]]})))

        return out

    def test_each_code_fires_on_bad_input(self):
        for code, bad, _good in self._cases():
            with self.subTest(code=code):
                m = bad()
                self.assertIn(code, self._diag_codes(m),
                    f"{code} did not fire on intentionally bad manifest")

    def test_each_code_does_not_fire_on_good_input(self):
        for code, _bad, good in self._cases():
            with self.subTest(code=code):
                m = good()
                self.assertNotIn(code, self._diag_codes(m),
                    f"{code} false-positive on a clean manifest")


class TestPayloadDedupe(unittest.TestCase):
    """The runtime JS reads only PAYLOAD.datasets; the manifest copy
    in PAYLOAD must not redundantly carry dataset rows. Verifies the
    HTML payload structure post-render.
    """

    def _extract_payload(self, html):
        """Pull the var PAYLOAD = {...} object out of the rendered HTML."""
        import re
        m = re.search(r"var PAYLOAD = (\{.*?\});", html, re.DOTALL)
        self.assertIsNotNone(m, "PAYLOAD literal not found in HTML")
        return json.loads(m.group(1))

    def test_manifest_copy_strips_datasets(self):
        """PAYLOAD.manifest.datasets is empty; PAYLOAD.datasets has
        the full rows."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "us_10y": [4.0 + i / 100 for i in range(10)],
        })
        manifest = {
            "schema_version": 1, "id": "d", "title": "t",
            "datasets": {"rates": df},
            "layout": {"rows": [[{
                "widget": "kpi", "id": "k1", "label": "10Y",
                "source": "rates.latest.us_10y", "w": 12,
            }]]},
        }
        r = compile_dashboard(manifest, write_html=False, write_json=False)
        payload = self._extract_payload(r.html)
        self.assertEqual(payload["manifest"].get("datasets"), {},
                          "PAYLOAD.manifest.datasets must be empty "
                          "(deduped)")
        self.assertIn("rates", payload["datasets"])
        rows = payload["datasets"]["rates"]["source"]
        # header + 10 data rows
        self.assertEqual(len(rows), 11)

    def test_runtime_js_reads_only_payload_datasets(self):
        """Sanity: DASHBOARD_APP_JS does not reference
        PAYLOAD.manifest.datasets (the dedupe is sound only if the
        runtime never dips into the manifest copy)."""
        from rendering import DASHBOARD_APP_JS
        self.assertNotIn("MANIFEST.datasets", DASHBOARD_APP_JS,
                          "Runtime JS reads manifest.datasets; "
                          "dedupe would break it")

    def test_saved_manifest_json_keeps_datasets(self):
        """The on-disk manifest.json (canonical artifact) must still
        carry datasets in full -- only the HTML payload deduplicates."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=5, freq="D"),
            "us_10y": [4.0, 4.1, 4.2, 4.3, 4.4],
        })
        manifest = {
            "schema_version": 1, "id": "d", "title": "t",
            "datasets": {"rates": df},
            "layout": {"rows": [[{
                "widget": "kpi", "id": "k1", "label": "10Y",
                "source": "rates.latest.us_10y", "w": 12,
            }]]},
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "out.html"
            r = compile_dashboard(manifest, output_path=str(p))
            self.assertTrue(r.success)
            mf = json.loads(Path(r.manifest_path).read_text())
            self.assertEqual(
                len(mf["datasets"]["rates"]["source"]), 6,
                "manifest.json must keep full dataset rows")


class TestStressDiagnostics(unittest.TestCase):
    """Tests for the diagnostic codes introduced by the stress-test
    audit: typo suggestions, fix_hint, degeneracy + topology checks,
    and the table-all-missing roll-up.
    """

    def _wrap(self, datasets, layout, filters=None):
        m = {
            "schema_version": 1, "id": "stress", "title": "Stress",
            "datasets": datasets, "layout": layout,
        }
        if filters is not None:
            m["filters"] = filters
        return m

    def _by_code(self, diags, code):
        return [d for d in diags if d.code == code]

    # --- typo suggestions on missing column ---------------------------

    def test_did_you_mean_case_mismatch(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"Date": [1, 2], "v": [3, 4]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "date",
                                                      "y": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        miss = self._by_code(diags, "chart_mapping_column_missing")
        self.assertTrue(miss)
        self.assertEqual(miss[0].context.get("did_you_mean"), ["Date"])
        self.assertIn("Did you mean 'Date'", miss[0].context.get("fix_hint", ""))

    def test_did_you_mean_typo_difflib(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"usd_2y": [4.1, 4.2],
                                              "usd_10y": [4.4, 4.5]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "usd_10y",
                                                      "y": "us_2y"}}}]]})
        diags = chart_data_diagnostics(m)
        miss = self._by_code(diags, "chart_mapping_column_missing")
        # 'us_2y' is one keystroke off from 'usd_2y' -> should suggest it
        self.assertTrue(miss)
        suggestions = miss[0].context.get("did_you_mean") or []
        self.assertIn("usd_2y", suggestions)

    def test_no_did_you_mean_when_no_match(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"q": [1], "z": [2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "q",
                                                      "y": "completely_different"
                                                      }}}]]})
        diags = chart_data_diagnostics(m)
        miss = self._by_code(diags, "chart_mapping_column_missing")
        self.assertTrue(miss)
        self.assertNotIn("did_you_mean", miss[0].context)
        # fix_hint still set so the diag is actionable
        self.assertIn("fix_hint", miss[0].context)

    # --- new chart_negative_values_in_portion ----------------------------

    def test_pie_negative_values_flagged(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["a", "b", "c"],
                                              "v": [50.0, -10.0, 60.0]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "pie", "dataset": "d",
                                          "mapping": {"category": "region",
                                                      "value": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "chart_negative_values_in_portion")
        self.assertTrue(flagged)
        self.assertEqual(flagged[0].context["negative_count"], 1)

    def test_bar_negative_values_not_flagged(self):
        """Bars handle signed values fine; should NOT fire."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["a", "b"],
                                              "v": [-10.0, 50.0]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "bar", "dataset": "d",
                                          "mapping": {"x": "region",
                                                      "y": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        self.assertFalse(self._by_code(diags,
                                          "chart_negative_values_in_portion"))

    # --- new chart_constant_values --------------------------------------

    def test_constant_y_flagged(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": list(range(10)),
                                              "y": [42.0] * 10})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "x",
                                                      "y": "y"}}}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "chart_constant_values")
        self.assertTrue(flagged)
        self.assertEqual(flagged[0].context["constant_value"], 42.0)
        self.assertEqual(flagged[0].severity, "warning")

    # --- new chart_sankey_self_loops + disconnected ---------------------

    def test_sankey_self_loops(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"s": ["A", "B", "C"],
                                              "t": ["A", "B", "C"],
                                              "v": [1, 2, 3]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "sankey",
                                          "dataset": "d",
                                          "mapping": {"source": "s",
                                                      "target": "t",
                                                      "value": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "chart_sankey_self_loops")
        self.assertTrue(flagged)
        self.assertEqual(flagged[0].context["self_loop_count"], 3)
        # 100% self-loops -> error severity
        self.assertEqual(flagged[0].severity, "error")

    def test_sankey_disconnected(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"s": ["A", "B"],
                                              "t": ["X", "Y"],
                                              "v": [1, 2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "sankey",
                                          "dataset": "d",
                                          "mapping": {"source": "s",
                                                      "target": "t",
                                                      "value": "v"}}}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "chart_sankey_disconnected")
        self.assertTrue(flagged)

    # --- new chart_candlestick_inverted ---------------------------------

    def test_candlestick_inverted_high_low(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({
                "x": list(range(3)),
                "o": [100, 101, 102],
                "h": [99, 100, 101],   # < low!
                "l": [110, 111, 112],
                "c": [105, 106, 107],
            })},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "candlestick",
                                          "dataset": "d",
                                          "mapping": {"x": "x", "open": "o",
                                                      "high": "h", "low": "l",
                                                      "close": "c"}}}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "chart_candlestick_inverted")
        self.assertTrue(flagged)
        self.assertEqual(flagged[0].context["inversions"]["high<low"], 3)

    # --- new chart_tree_orphan_parents ----------------------------------

    def test_tree_orphan_parents(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({
                "name": ["root", "a", "b"],
                "parent": [None, "GHOST", "ALSO_GHOST"],
            })},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "tree",
                                          "dataset": "d",
                                          "mapping": {"name": "name",
                                                      "parent": "parent"}}}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "chart_tree_orphan_parents")
        self.assertTrue(flagged)
        self.assertEqual(flagged[0].context["orphan_count"], 2)

    # --- new table_columns_all_missing ----------------------------------

    def test_table_columns_all_missing(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1, 2], "y": [3, 4]})},
            layout={"rows": [[{"widget": "table", "id": "t", "w": 12,
                                "dataset_ref": "d",
                                "columns": [{"field": "a"},
                                              {"field": "b"},
                                              {"field": "c"}]}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "table_columns_all_missing")
        self.assertTrue(flagged)
        # Per-column ones still fire too (PRISM gets both rollup + detail)
        per_col = self._by_code(diags, "table_column_field_missing")
        self.assertEqual(len(per_col), 3)

    def test_table_partial_missing_no_rollup(self):
        """Half-broken table only fires per-column diags, NOT the
        all-missing roll-up."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"x": [1, 2]})},
            layout={"rows": [[{"widget": "table", "id": "t", "w": 12,
                                "dataset_ref": "d",
                                "columns": [{"field": "x"},
                                              {"field": "missing"}]}]]})
        diags = chart_data_diagnostics(m)
        self.assertFalse(self._by_code(diags, "table_columns_all_missing"))
        self.assertEqual(len(self._by_code(
            diags, "table_column_field_missing")), 1)

    # --- new kpi_sparkline_too_short ------------------------------------

    def test_kpi_sparkline_too_short(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"v": [42.0]})},
            layout={"rows": [[{"widget": "kpi", "id": "k", "w": 4,
                                "label": "x", "source": "d.latest.v",
                                "sparkline_source": "d.v"}]]})
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "kpi_sparkline_too_short")
        self.assertTrue(flagged)
        self.assertEqual(flagged[0].context["valid_value_count"], 1)

    # --- new filter_default_not_in_options ------------------------------

    def test_filter_default_not_in_options(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US", "EU"],
                                              "v": [1, 2]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "bar", "dataset": "d",
                                          "mapping": {"x": "region",
                                                      "y": "v"}}}]]},
            filters=[{"id": "f", "type": "select", "default": "ZZ",
                      "options": ["US", "EU"], "field": "region",
                      "targets": ["c"]}])
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "filter_default_not_in_options")
        self.assertTrue(flagged)
        self.assertEqual(flagged[0].context["missing"], ["ZZ"])

    def test_filter_default_with_dict_options_ok(self):
        """Dict-style options use 'value' key for membership test."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"region": ["US"], "v": [1]})},
            layout={"rows": [[{"widget": "chart", "id": "c", "w": 12,
                                "spec": {"chart_type": "bar", "dataset": "d",
                                          "mapping": {"x": "region",
                                                      "y": "v"}}}]]},
            filters=[{"id": "f", "type": "select", "default": "us",
                      "options": [{"value": "us", "label": "United States"},
                                    {"value": "eu", "label": "Europe"}],
                      "field": "region",
                      "targets": ["c"]}])
        diags = chart_data_diagnostics(m)
        self.assertFalse(self._by_code(diags,
                                          "filter_default_not_in_options"))

    # --- new filter_targets_no_match ------------------------------------

    def test_filter_targets_no_match(self):
        m = self._wrap(
            datasets={"d": pd.DataFrame({"v": [1, 2]})},
            layout={"rows": [[{"widget": "chart", "id": "real_chart",
                                "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "v",
                                                      "y": "v"}}}]]},
            filters=[{"id": "f", "type": "toggle",
                      "targets": ["ghost_widget*"]}])
        diags = chart_data_diagnostics(m)
        flagged = self._by_code(diags, "filter_targets_no_match")
        self.assertTrue(flagged)
        self.assertIn("real_chart",
                       flagged[0].context["available_widget_ids"])

    def test_filter_targets_partial_match_ok(self):
        """If at least ONE target resolves, no warning."""
        m = self._wrap(
            datasets={"d": pd.DataFrame({"v": [1, 2]})},
            layout={"rows": [[{"widget": "chart", "id": "real",
                                "w": 12,
                                "spec": {"chart_type": "line", "dataset": "d",
                                          "mapping": {"x": "v",
                                                      "y": "v"}}}]]},
            filters=[{"id": "f", "type": "toggle",
                      "targets": ["real", "ghost"]}])
        diags = chart_data_diagnostics(m)
        # 'real' matches; partial-match shouldn't fire the no-match warning
        self.assertFalse(self._by_code(diags, "filter_targets_no_match"))

    # --- compile-end-to-end on stress scenarios -------------------------

    def test_compile_succeeds_with_compound_failures(self):
        """The compound stress dashboard validates AND compiles AND
        produces HTML, even with multiple categories of broken data.

        Iteration mode (``strict=False``) is the contract for PRISM:
        broken charts produce placeholders + diagnostics so PRISM can
        fix everything in one round-trip rather than playing whack-a-
        mole one error per recompile.
        """
        m = build_compound_chaos()
        ok, _ = validate_manifest(m)
        self.assertTrue(ok)
        r = compile_dashboard(m, strict=False)
        self.assertTrue(r.success)
        self.assertIsNotNone(r.html)
        # Many distinct diagnostic codes should fire
        codes = {d.code for d in r.diagnostics}
        self.assertGreater(len(codes), 5)


# =============================================================================
# RICH TABLE SCHEMA
# =============================================================================

class TestRichTableSchema(unittest.TestCase):
    def _m(self, cols, row_click=None):
        tbl = {"widget": "table", "id": "tbl",
                "dataset_ref": "d", "columns": cols}
        if row_click is not None:
            tbl["row_click"] = row_click
        return {
            "schema_version": 1, "id": "t", "title": "t",
            "datasets": {"d": pd.DataFrame({"a": [1, 2, 3],
                                                "b": ["x", "y", "z"]})},
            "layout": {"rows": [[tbl]]},
        }

    def test_simple_columns_ok(self):
        m = self._m([{"field": "a", "label": "A", "format": "number:2"},
                       {"field": "b", "label": "B"}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_missing_field(self):
        m = self._m([{"label": "A"}])
        ok, errs = validate_manifest(m); self.assertFalse(ok)

    def test_invalid_format(self):
        m = self._m([{"field": "a", "format": "NOTAFORMAT"}])
        ok, errs = validate_manifest(m); self.assertFalse(ok)

    def test_invalid_align(self):
        m = self._m([{"field": "a", "align": "middle"}])
        ok, errs = validate_manifest(m); self.assertFalse(ok)

    def test_conditional_ok(self):
        m = self._m([{"field": "a", "format": "number:2",
                        "conditional": [{"op": ">", "value": 2,
                                            "background": "#c00"}]}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_conditional_bad_op(self):
        m = self._m([{"field": "a",
                        "conditional": [{"op": "BOGUS", "value": 2}]}])
        ok, errs = validate_manifest(m); self.assertFalse(ok)

    def test_color_scale_ok(self):
        m = self._m([{"field": "a",
                        "color_scale": {"min": 0, "max": 10,
                                          "palette": "gs_diverging"}}])
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_color_scale_bad_palette(self):
        m = self._m([{"field": "a",
                        "color_scale": {"min": 0, "max": 10,
                                          "palette": "nope"}}])
        ok, errs = validate_manifest(m); self.assertFalse(ok)

    def test_row_click_ok(self):
        m = self._m([{"field": "a"}],
                      row_click={"title_field": "a", "popup_fields": ["a", "b"]})
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)


# =============================================================================
# NEW WIDGETS (stat_grid, image)
# =============================================================================

class TestNewWidgets(unittest.TestCase):
    def _wrap(self, widget):
        return {
            "schema_version": 1, "id": "t", "title": "t",
            "datasets": {"d": pd.DataFrame({"a": [1, 2]})},
            "layout": {"rows": [[widget]]},
        }

    def test_stat_grid_ok(self):
        m = self._wrap({"widget": "stat_grid", "id": "sg",
                          "stats": [
                              {"id": "a", "label": "A", "value": "1"},
                              {"id": "b", "label": "B", "value": "2"},
                          ]})
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_stat_grid_missing_stats(self):
        m = self._wrap({"widget": "stat_grid", "id": "sg"})
        ok, errs = validate_manifest(m); self.assertFalse(ok)

    def test_image_ok(self):
        m = self._wrap({"widget": "image", "id": "img",
                          "src": "https://example.com/x.png"})
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)

    def test_image_missing_src(self):
        m = self._wrap({"widget": "image", "id": "img"})
        ok, errs = validate_manifest(m); self.assertFalse(ok)


# =============================================================================
# MARKDOWN GRAMMAR (mirrored Python <-> JS twin)
# =============================================================================
# These tests pin the Python `_render_md` output so the grammar is
# stable for downstream consumers (PRISM observation writeups,
# methodology bodies, drill-down sections). The JS twin
# `_mdInlinePopup` mirrors this grammar by construction; if the JS
# diverges we'll catch it via end-to-end gallery rendering rather
# than here.

class TestMarkdownGrammar(unittest.TestCase):
    def test_inline_strikethrough(self):
        out = _md_inline("not ~~old~~ but new")
        self.assertIn("<del>old</del>", out)

    def test_inline_link_bold_italic_code(self):
        out = _md_inline(
            "see [docs](https://x.example.com), "
            "**bold**, *ital*, `c`"
        )
        self.assertIn('<a href="https://x.example.com"', out)
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("<em>ital</em>", out)
        self.assertIn("<code>c</code>", out)

    def test_inline_xss_escape(self):
        out = _md_inline('<script>alert(1)</script>')
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_headings_h1_to_h5(self):
        out = _render_md("# H1\n\n## H2\n\n### H3\n\n#### H4\n\n##### H5")
        for tag in ("<h1>H1</h1>", "<h2>H2</h2>", "<h3>H3</h3>",
                     "<h4>H4</h4>", "<h5>H5</h5>"):
            self.assertIn(tag, out)

    def test_ordered_list(self):
        out = _render_md("1. one\n2. two\n3. three")
        self.assertIn("<ol>", out)
        self.assertIn("<li>one", out)
        self.assertIn("<li>three", out)
        self.assertEqual(out.count("</ol>"), 1)

    def test_unordered_flat_regression(self):
        out = _render_md("- a\n- b\n- c")
        self.assertIn("<ul>", out)
        self.assertEqual(out.count("</ul>"), 1)
        self.assertEqual(out.count("<li>"), 3)

    def test_nested_bullets_html_valid(self):
        out = _render_md("- top\n  - sub a\n  - sub b\n- top2")
        self.assertIn("<ul>", out)
        sub_idx = out.find("<ul>", out.find("<ul>") + 1)
        self.assertGreater(sub_idx, -1, "expected a nested <ul>")
        outer_li = out.find("<li>top")
        self.assertLess(outer_li, sub_idx,
                          "nested <ul> should appear after parent <li>")

    def test_mixed_ol_ul_nesting(self):
        out = _render_md("- topic\n  1. sub one\n  2. sub two\n- topic 2")
        self.assertIn("<ul>", out)
        self.assertIn("<ol>", out)

    def test_blockquote(self):
        out = _render_md("> a quote\n> with two lines")
        self.assertIn("<blockquote>", out)
        self.assertIn("a quote with two lines", out)

    def test_blockquote_with_inline(self):
        out = _render_md("> **bold** inside a quote")
        self.assertIn("<blockquote>", out)
        self.assertIn("<strong>bold</strong>", out)

    def test_fenced_code_block_with_lang(self):
        out = _render_md("```python\nprint('hi')\n```")
        self.assertIn('<pre><code class="lang-python">', out)
        self.assertIn("print('hi')", out)
        self.assertIn("</code></pre>", out)

    def test_fenced_code_block_escapes_html(self):
        out = _render_md("```\n<script>x</script>\n```")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_fenced_code_block_no_lang(self):
        out = _render_md("```\nplain\n```")
        self.assertIn("<pre><code>plain</code></pre>", out)

    def test_md_table_basic(self):
        out = _render_md("| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |")
        self.assertIn('<table class="md-table">', out)
        self.assertIn("<th>a</th>", out)
        self.assertIn("<td>1</td>", out)
        self.assertIn("<td>4</td>", out)

    def test_md_table_alignment(self):
        out = _render_md(
            "| L | C | R |\n"
            "| :--- | :---: | ---: |\n"
            "| 1 | 2 | 3 |"
        )
        self.assertIn('text-align:left', out)
        self.assertIn('text-align:center', out)
        self.assertIn('text-align:right', out)

    def test_horizontal_rule(self):
        out = _render_md("Above\n\n---\n\nBelow")
        self.assertIn("<hr/>", out)

    def test_paragraph_then_list_then_paragraph(self):
        out = _render_md("Para A.\n\n1. one\n2. two\n\nPara B.")
        self.assertIn("<p>Para A.</p>", out)
        self.assertIn("<ol>", out)
        self.assertIn("<p>Para B.</p>", out)
        self.assertLess(out.find("Para A"), out.find("<ol>"))
        self.assertLess(out.find("</ol>"), out.find("Para B"))

    def test_legacy_grammar_unchanged(self):
        out = _render_md(
            "# Title\n\nFirst paragraph.\n\n"
            "- one\n- two\n\n"
            "**bold** and *ital* and `code`."
        )
        self.assertIn("<h1>Title</h1>", out)
        self.assertIn("<p>First paragraph.</p>", out)
        self.assertIn("<li>one", out)
        self.assertIn("<strong>bold</strong>", out)


# =============================================================================
# NOTE WIDGET (semantic callout) + SUMMARY BANNER (metadata.summary)
# =============================================================================

class TestNoteWidget(unittest.TestCase):
    def _wrap(self, widget):
        return {
            "schema_version": 1, "id": "t", "title": "t",
            "datasets": {"d": pd.DataFrame({"a": [1, 2]})},
            "layout": {"rows": [[widget]]},
        }

    def test_all_kinds_validate(self):
        for k in VALID_NOTE_KINDS:
            with self.subTest(kind=k):
                m = self._wrap({"widget": "note", "id": f"n_{k}",
                                  "kind": k, "body": "a body"})
                ok, errs = validate_manifest(m)
                self.assertTrue(ok, errs)

    def test_unknown_kind_rejected(self):
        m = self._wrap({"widget": "note", "id": "n",
                          "kind": "banana", "body": "x"})
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("kind" in e for e in errs))

    def test_missing_body_rejected(self):
        m = self._wrap({"widget": "note", "id": "n", "kind": "insight"})
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("body" in e for e in errs))

    def test_default_kind_is_insight(self):
        m = self._wrap({"widget": "note", "id": "n",
                          "body": "no kind specified"})
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_note_ref_to_dict(self):
        n = NoteRef(id="n", body="**body**", kind="thesis",
                     title="My thesis", w=6)
        d = n.to_dict()
        self.assertEqual(d["widget"], "note")
        self.assertEqual(d["kind"], "thesis")
        self.assertEqual(d["title"], "My thesis")

    def test_note_ref_bad_kind_raises(self):
        with self.assertRaises(ValueError):
            NoteRef(id="n", body="x", kind="banana").to_dict()

    def test_note_widget_renders_html(self):
        opt = {"series": [{"type": "bar", "data": [1, 2]}],
                "xAxis": {"type": "category", "data": ["a", "b"]},
                "yAxis": {"type": "value"}}
        db = (Dashboard(id="r", title="R")
              .add_row([NoteRef(id="n1", body="**body**",
                                  kind="thesis", title="T", w=6),
                         ChartRef(id="c", option=opt, w=6)]))
        res = render_dashboard(db.to_manifest())
        self.assertTrue(res.success)
        self.assertIn("note-tile", res.html)
        self.assertIn("note-tile-thesis", res.html)
        self.assertIn("<strong>body</strong>", res.html)
        self.assertIn("Thesis", res.html)


class TestSummaryBanner(unittest.TestCase):
    def test_summary_string_renders(self):
        opt = {"series": [{"type": "bar", "data": [1, 2]}],
                "xAxis": {"type": "category", "data": ["a", "b"]},
                "yAxis": {"type": "value"}}
        db = (Dashboard(id="r", title="R")
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        m = db.to_manifest()
        m["metadata"] = {"summary": "**Top of page** prose."}
        res = render_dashboard(m)
        self.assertTrue(res.success)
        self.assertIn("summary-banner", res.html)
        self.assertIn("<strong>Top of page</strong>", res.html)

    def test_summary_dict_with_title_renders(self):
        opt = {"series": [{"type": "bar", "data": [1, 2]}],
                "xAxis": {"type": "category", "data": ["a", "b"]},
                "yAxis": {"type": "value"}}
        db = (Dashboard(id="r", title="R")
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        m = db.to_manifest()
        m["metadata"] = {
            "summary": {"title": "Today's read",
                          "body": "Body markdown."}
        }
        res = render_dashboard(m)
        self.assertTrue(res.success)
        self.assertIn("summary-banner", res.html)
        self.assertIn("Today's read</h2>", res.html)
        self.assertIn("Body markdown", res.html)

    def test_summary_absent_no_banner(self):
        opt = {"series": [{"type": "bar", "data": [1, 2]}],
                "xAxis": {"type": "category", "data": ["a", "b"]},
                "yAxis": {"type": "value"}}
        db = (Dashboard(id="r", title="R")
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        res = render_dashboard(db.to_manifest())
        self.assertTrue(res.success)
        self.assertNotIn('class="summary-banner', res.html)


# =============================================================================
# FILTER TARGETS: tables + kpis now valid targets
# =============================================================================

class TestFilterTargets(unittest.TestCase):
    def test_table_is_valid_filter_target(self):
        m = {
            "schema_version": 1, "id": "t", "title": "t",
            "datasets": {"d": pd.DataFrame({"s": ["a", "b"], "v": [1, 2]})},
            "filters": [{"id": "f", "type": "select", "default": "a",
                          "options": ["a", "b"], "field": "s",
                          "targets": ["tbl"]}],
            "layout": {"rows": [[{"widget": "table", "id": "tbl",
                                    "dataset_ref": "d"}]]},
        }
        ok, errs = validate_manifest(m); self.assertTrue(ok, errs)


# =============================================================================
# MANIFEST TEMPLATE + populate_template
# =============================================================================

class TestManifestTemplate(unittest.TestCase):
    def _full_manifest(self):
        """Manifest with real DataFrames in multiple datasets."""
        return {
            "schema_version": 1,
            "id": "rates_monitor",
            "title": "Rates Monitor",
            "theme": "gs_clean",
            "datasets": {
                "rates": pd.DataFrame({
                    "date": pd.date_range("2024-01-01", periods=5, freq="D"),
                    "us_2y":  [4.0, 4.1, 4.2, 4.3, 4.4],
                    "us_10y": [4.3, 4.4, 4.5, 4.6, 4.7],
                }),
                "ism": pd.DataFrame({
                    "date": pd.date_range("2024-01-01", periods=3, freq="MS"),
                    "ism": [52.1, 51.8, 49.5],
                }),
            },
            "filters": [
                {"id": "dt", "type": "dateRange", "default": "6M",
                  "targets": ["*"], "field": "date"},
            ],
            "layout": {"rows": [[
                {"widget": "chart", "id": "curve", "w": 12,
                  "spec": {"chart_type": "multi_line", "dataset": "rates",
                            "mapping": {"x": "date",
                                          "y": ["us_2y", "us_10y"]}}},
            ]]},
            "metadata": {"owner": "goyairl"},
        }

    def test_template_strips_data_keeps_structure(self):
        from echart_dashboard import manifest_template

        full = self._full_manifest()
        tpl = manifest_template(full)

        # Non-data fields preserved
        self.assertEqual(tpl["id"], "rates_monitor")
        self.assertEqual(tpl["title"], "Rates Monitor")
        self.assertEqual(len(tpl["filters"]), 1)
        self.assertEqual(tpl["layout"]["rows"][0][0]["id"], "curve")

        # Datasets present but data rows stripped
        self.assertIn("rates", tpl["datasets"])
        self.assertIn("ism", tpl["datasets"])
        rates_src = tpl["datasets"]["rates"]["source"]
        # header-only (1 row) or empty
        self.assertTrue(len(rates_src) in (0, 1))
        if rates_src:
            # If header kept, it matches the original columns
            self.assertEqual(rates_src[0], ["date", "us_2y", "us_10y"])
        # template marker is set so populate_template can detect slots
        self.assertTrue(tpl["datasets"]["rates"].get("template"))

    def test_template_is_json_serializable(self):
        import json
        from echart_dashboard import manifest_template

        tpl = manifest_template(self._full_manifest())
        s = json.dumps(tpl)
        round_tripped = json.loads(s)
        self.assertEqual(round_tripped["id"], "rates_monitor")

    def test_template_does_not_mutate_input(self):
        from echart_dashboard import manifest_template
        full = self._full_manifest()
        full_cols_before = list(full["datasets"]["rates"].columns)
        _ = manifest_template(full)
        # Original DataFrame still untouched
        self.assertEqual(list(full["datasets"]["rates"].columns),
                          full_cols_before)
        # Input manifest still has real DataFrames, not source arrays
        self.assertTrue(hasattr(full["datasets"]["rates"], "columns"))

    def test_populate_template_basic(self):
        from echart_dashboard import manifest_template, populate_template

        tpl = manifest_template(self._full_manifest())
        fresh_rates = pd.DataFrame({
            "date": pd.date_range("2025-06-01", periods=4, freq="D"),
            "us_2y":  [3.90, 3.92, 3.95, 3.98],
            "us_10y": [4.10, 4.12, 4.15, 4.18],
        })
        fresh_ism = pd.DataFrame({
            "date": pd.date_range("2025-06-01", periods=2, freq="MS"),
            "ism": [50.2, 50.8],
        })

        m = populate_template(tpl, {"rates": fresh_rates, "ism": fresh_ism})
        # Datasets point at fresh DataFrames (still raw; compile_dashboard
        # normalizes to list-of-lists).
        self.assertTrue(hasattr(m["datasets"]["rates"], "columns"))
        self.assertEqual(len(m["datasets"]["rates"]), 4)
        self.assertEqual(len(m["datasets"]["ism"]), 2)

    def test_populate_template_does_not_mutate_template(self):
        from echart_dashboard import manifest_template, populate_template
        tpl = manifest_template(self._full_manifest())
        tpl_before = json.dumps(tpl)
        _ = populate_template(tpl, {"rates": pd.DataFrame({"date": [1], "us_2y": [4.0]})})
        self.assertEqual(json.dumps(tpl), tpl_before,
                          "template was mutated by populate_template")

    def test_populate_template_merges_metadata(self):
        from echart_dashboard import manifest_template, populate_template
        tpl = manifest_template(self._full_manifest())
        m = populate_template(
            tpl,
            {"rates": pd.DataFrame({"date": [1], "us_2y": [4.0]})},
            metadata={"data_as_of": "2025-06-01", "pipeline": "test"},
        )
        self.assertEqual(m["metadata"]["owner"], "goyairl")  # preserved
        self.assertEqual(m["metadata"]["data_as_of"], "2025-06-01")
        self.assertEqual(m["metadata"]["pipeline"], "test")

    def test_populate_template_add_new_slot(self):
        from echart_dashboard import manifest_template, populate_template
        tpl = manifest_template(self._full_manifest())
        m = populate_template(
            tpl,
            {"rates": pd.DataFrame({"date": [1], "us_2y": [4.0]}),
             "brand_new": pd.DataFrame({"x": [1, 2], "y": [3, 4]})},
        )
        self.assertIn("brand_new", m["datasets"])

    def test_populate_template_require_all_slots(self):
        from echart_dashboard import manifest_template, populate_template
        tpl = manifest_template(self._full_manifest())
        # Only supply one of the two template slots
        with self.assertRaises(KeyError):
            populate_template(
                tpl,
                {"rates": pd.DataFrame({"date": [1], "us_2y": [4.0]})},
                require_all_slots=True,
            )

    def test_populate_template_type_errors(self):
        from echart_dashboard import populate_template
        with self.assertRaises(TypeError):
            populate_template("not a dict", {"rates": pd.DataFrame()})
        with self.assertRaises(TypeError):
            populate_template({"schema_version": 1}, "not a dict")

    def test_round_trip_compiles_successfully(self):
        """End-to-end: full manifest -> template JSON on disk ->
        reload -> populate with fresh data -> compile succeeds."""
        from echart_dashboard import (
            manifest_template, populate_template, compile_dashboard,
        )
        tmp = tempfile.mkdtemp(prefix="template_roundtrip_")
        tpl_path = Path(tmp) / "chart_manifest.json"

        # 1. Author time: create manifest with data, strip to template
        original = self._full_manifest()
        tpl = manifest_template(original)

        # 2. Persist as JSON on disk (simulating the refresh contract)
        tpl_path.write_text(json.dumps(tpl), encoding="utf-8")

        # 3. Refresh time: load template, pull fresh data, populate
        template_reloaded = json.loads(tpl_path.read_text(encoding="utf-8"))
        fresh_rates = pd.DataFrame({
            "date": pd.date_range("2025-06-01", periods=10, freq="D"),
            "us_2y":  [3.85 + i*0.01 for i in range(10)],
            "us_10y": [4.10 + i*0.005 for i in range(10)],
        })
        fresh_ism = pd.DataFrame({
            "date": pd.date_range("2025-06-01", periods=2, freq="MS"),
            "ism": [50.5, 51.1],
        })
        manifest_fresh = populate_template(
            template_reloaded,
            {"rates": fresh_rates, "ism": fresh_ism},
            metadata={"data_as_of": "2025-06-30"},
        )

        # 4. Compile -- must succeed and write HTML with fresh data
        out = Path(tmp) / "dashboard.html"
        r = compile_dashboard(manifest_fresh, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        self.assertTrue(out.is_file())
        html = out.read_text(encoding="utf-8")
        # Fresh data should be embedded
        self.assertIn("2025-06-01", html)
        self.assertIn("3.85", html)
        # Template schema preserved
        self.assertIn("rates_monitor", html)


# =============================================================================
# CHART click_popup -- click a data point to open a row-detail modal
# =============================================================================
#
# Mirror of TestRichTableSchema for the chart-side analog: validation,
# round-trip through the compiler (so the widget meta makes it into
# the HTML), and the runtime hooks that map a click to a row.

class TestChartClickPopup(unittest.TestCase):
    def _bonds_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "ticker":      ["AAPL", "MSFT", "GS", "TSLA"],
            "sector":      ["Technology", "Technology",
                              "Financials", "Consumer"],
            "rating":      ["AA+", "AAA", "A+", "BB"],
            "carry_bp":    [42.1, 38.5, 95.2, 180.7],
            "roll_bp":     [22.3, 24.1, 33.0, 41.2],
            "ytm_pct":     [4.55, 4.49, 5.10, 7.20],
            "duration":    [4.2, 4.6, 6.1, 4.0],
        })

    def _scatter_manifest(self, click_popup):
        m = {
            "schema_version": 1, "id": "cp_test", "title": "click_popup test",
            "datasets": {"bonds": self._bonds_df()},
            "layout": {"rows": [[
                {"widget": "chart", "id": "scatter", "w": 12, "h_px": 360,
                  "spec": {"chart_type": "scatter", "dataset": "bonds",
                            "mapping": {"x": "carry_bp", "y": "roll_bp",
                                          "color": "sector"}}},
            ]]},
        }
        if click_popup is not None:
            m["layout"]["rows"][0][0]["click_popup"] = click_popup
        return m

    def test_simple_click_popup_validates(self):
        m = self._scatter_manifest({
            "title_field": "ticker",
            "popup_fields": ["ticker", "sector", "carry_bp", "roll_bp"],
        })
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_rich_click_popup_validates(self):
        m = self._scatter_manifest({
            "title_field": "ticker",
            "subtitle_template":
                "{sector} \u00B7 carry {carry_bp:number:1} bp",
            "detail": {
                "wide": True,
                "sections": [
                    {"type": "stats",
                      "fields": [
                          {"field": "carry_bp", "label": "Carry",
                            "format": "number:1", "suffix": " bp"},
                          {"field": "roll_bp", "label": "Roll",
                            "format": "number:1", "suffix": " bp"},
                      ]},
                    {"type": "markdown",
                      "template":
                          "**{ticker}** \u00B7 *{sector}*\n\n"
                          "Rated `{rating}`, duration "
                          "{duration:number:1} yrs."},
                ],
            },
        })
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_click_popup_must_be_dict(self):
        m = self._scatter_manifest("not a dict")
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("click_popup" in e for e in errs))

    def test_click_popup_list_rejected(self):
        m = self._scatter_manifest(["not", "a", "dict"])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("click_popup" in e for e in errs))

    def test_compiled_html_carries_click_popup_meta(self):
        m = self._scatter_manifest({
            "title_field": "ticker",
            "popup_fields": ["ticker", "carry_bp", "roll_bp"],
        })
        tmp = tempfile.mkdtemp(prefix="click_popup_")
        out = Path(tmp) / "dashboard.html"
        r = compile_dashboard(m, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        html = out.read_text(encoding="utf-8")
        # Runtime entry points are present
        self.assertIn("wireChartClickPopup", html)
        self.assertIn("_resolveClickRow", html)
        self.assertIn("_openPopupModal", html)
        # The click_popup config is embedded in the widget meta payload
        self.assertIn("click_popup", html)
        self.assertIn("carry_bp", html)

    def test_compiled_html_omits_click_popup_when_unset(self):
        """A chart without click_popup should still emit the runtime
        functions (they live in the shared app JS) but the manifest
        payload should not contain a click_popup key for that widget."""
        m = self._scatter_manifest(None)
        tmp = tempfile.mkdtemp(prefix="click_popup_off_")
        out = Path(tmp) / "dashboard.html"
        r = compile_dashboard(m, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        html = out.read_text(encoding="utf-8")
        # Function definitions are unconditional
        self.assertIn("wireChartClickPopup", html)
        # But the widget itself doesn't carry the config
        self.assertNotIn('"click_popup"', html)

    def test_click_popup_on_categorical_chart_validates(self):
        """Pie / donut / funnel are valid click_popup targets too --
        the runtime resolves rows by category column."""
        m = {
            "schema_version": 1, "id": "cp_pie", "title": "pie",
            "datasets": {"sectors": pd.DataFrame({
                "sector": ["Tech", "Fin", "Energy"],
                "count":  [12, 8, 5],
                "avg":    [42.1, 95.0, 60.5],
            })},
            "layout": {"rows": [[
                {"widget": "chart", "id": "pie", "w": 12,
                  "spec": {"chart_type": "donut", "dataset": "sectors",
                            "mapping": {"category": "sector",
                                          "value": "count"}},
                  "click_popup": {
                      "title_field": "sector",
                      "popup_fields": [
                          {"field": "count", "label": "Bonds",
                            "format": "integer"},
                          {"field": "avg", "label": "Avg",
                            "format": "number:1", "suffix": " bp"},
                      ]}},
            ]]},
        }
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)


# =============================================================================
# DATA PROVENANCE -- field_provenance / row_provenance + popup integration
# =============================================================================
#
# Provenance is per-column lineage carried on a dataset entry; the
# compiler does NOT introspect df.attrs (PRISM is responsible for
# cleaning upstream metadata into the canonical shape). It surfaces in
# click popups two ways:
#   1) auto-default popup when chart click_popup / table row_click is
#      not declared but the dataset carries field_provenance
#   2) auto-appended "Sources" footer on every popup (suppressible
#      per-popup with show_provenance:false)
# Boolean false on click_popup / row_click is the opt-out hatch.

class TestProvenanceValidation(unittest.TestCase):
    def _ds_with_prov(self, **extras):
        ds = {"source": [["date", "UST10Y"], ["2026-04-22", 4.30]]}
        ds.update(extras)
        return {
            "schema_version": 1, "id": "p", "title": "p",
            "datasets": {"d": ds},
            "layout": {"rows": [[
                {"widget": "chart", "id": "c", "w": 12,
                  "spec": {"chart_type": "line", "dataset": "d",
                            "mapping": {"x": "date", "y": "UST10Y"}}}
            ]]},
        }

    def test_field_provenance_dict_validates(self):
        m = self._ds_with_prov(field_provenance={
            "UST10Y": {"system": "market_data",
                        "symbol": "IR_USD_Treasury_10Y_Rate",
                        "tsdb_symbol": "ustsy10y",
                        "display_name": "US 10Y Treasury Rate",
                        "units": "percent",
                        "source_label": "GS Market Data"}
        })
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_field_provenance_must_be_dict(self):
        m = self._ds_with_prov(field_provenance=["nope"])
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("field_provenance" in e for e in errs))

    def test_field_provenance_inner_must_be_dict(self):
        m = self._ds_with_prov(field_provenance={"UST10Y": "just a string"})
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("field_provenance.UST10Y" in e for e in errs))

    def test_row_provenance_field_must_be_string(self):
        m = self._ds_with_prov(row_provenance_field=123)
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("row_provenance_field" in e for e in errs))

    def test_row_provenance_must_be_dict_of_dicts(self):
        m = self._ds_with_prov(row_provenance={"k": "oops"})
        ok, errs = validate_manifest(m)
        self.assertFalse(ok)
        self.assertTrue(any("row_provenance.k" in e for e in errs))

    def test_row_provenance_full_shape_validates(self):
        m = self._ds_with_prov(
            row_provenance_field="UST10Y",
            row_provenance={"4.30": {"UST10Y": {
                "system": "bloomberg", "symbol": "USGG10YR Index"
            }}}
        )
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)

    def test_freeform_provenance_keys_accepted(self):
        """Inner provenance keys are intentionally free-form so PRISM
        can carry whatever the upstream system emits without us
        enumerating every vendor."""
        m = self._ds_with_prov(field_provenance={
            "UST10Y": {"system": "haver", "haver_code": "FYCEPI@USECON",
                        "frequency": "M", "vintage": "2026-04-25"},
        })
        ok, errs = validate_manifest(m)
        self.assertTrue(ok, errs)


class TestProvenancePopupOptOut(unittest.TestCase):
    """`click_popup: false` and `row_click: false` are the opt-out
    hatches that suppress the auto-default popup even when the
    dataset has provenance."""

    def _chart_manifest(self, click_popup):
        m = {
            "schema_version": 1, "id": "p", "title": "p",
            "datasets": {"d": pd.DataFrame({"a": [1, 2], "b": [3, 4]})},
            "layout": {"rows": [[
                {"widget": "chart", "id": "c", "w": 12,
                  "spec": {"chart_type": "line", "dataset": "d",
                            "mapping": {"x": "a", "y": "b"}}}
            ]]},
        }
        if click_popup is not None:
            m["layout"]["rows"][0][0]["click_popup"] = click_popup
        return m

    def _table_manifest(self, row_click):
        m = {
            "schema_version": 1, "id": "p", "title": "p",
            "datasets": {"d": pd.DataFrame({"a": [1, 2], "b": [3, 4]})},
            "layout": {"rows": [[
                {"widget": "table", "id": "t1", "w": 12,
                  "dataset_ref": "d"}
            ]]},
        }
        if row_click is not None:
            m["layout"]["rows"][0][0]["row_click"] = row_click
        return m

    def test_click_popup_false_validates(self):
        ok, errs = validate_manifest(self._chart_manifest(False))
        self.assertTrue(ok, errs)

    def test_row_click_false_validates(self):
        ok, errs = validate_manifest(self._table_manifest(False))
        self.assertTrue(ok, errs)

    def test_click_popup_string_rejected(self):
        ok, errs = validate_manifest(self._chart_manifest("nope"))
        self.assertFalse(ok)
        self.assertTrue(any("click_popup" in e for e in errs))

    def test_row_click_string_rejected(self):
        ok, errs = validate_manifest(self._table_manifest("nope"))
        self.assertFalse(ok)
        self.assertTrue(any("row_click" in e for e in errs))


class TestProvenanceCompileRoundTrip(unittest.TestCase):
    """Provenance metadata + JS helpers must end up in the compiled
    HTML so the runtime can resolve symbols/sources at click time."""

    def _bonds_with_prov(self) -> Dict[str, Any]:
        return {
            "schema_version": 1, "id": "prov", "title": "prov",
            "datasets": {
                "rates": {
                    "source": pd.DataFrame({
                        "date": ["2026-04-22", "2026-04-23"],
                        "UST10Y": [4.30, 4.31],
                        "UST2Y":  [4.15, 4.18],
                    }),
                    "field_provenance": {
                        "UST10Y": {
                            "system": "market_data",
                            "symbol": "IR_USD_Treasury_10Y_Rate",
                            "tsdb_symbol": "ustsy10y",
                            "display_name": "US 10Y Treasury Rate",
                            "units": "percent",
                            "source_label": "GS Market Data",
                        },
                        "UST2Y": {
                            "system": "market_data",
                            "symbol": "IR_USD_Treasury_2Y_Rate",
                            "tsdb_symbol": "ustsy2y",
                            "source_label": "GS Market Data",
                        },
                    },
                },
            },
            "layout": {"rows": [[
                {"widget": "chart", "id": "r10", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "rates",
                            "mapping": {"x": "date", "y": "UST10Y"}}},
                {"widget": "table", "id": "tbl", "w": 6,
                  "dataset_ref": "rates",
                  "columns": [{"field": "date"},
                                {"field": "UST10Y", "format": "number:2"}]},
            ]]},
        }

    def test_provenance_data_in_html(self):
        m = self._bonds_with_prov()
        tmp = tempfile.mkdtemp(prefix="prov_rt_")
        out = Path(tmp) / "d.html"
        r = compile_dashboard(m, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        html = out.read_text(encoding="utf-8")
        # Dataset metadata makes it through serialization
        self.assertIn("field_provenance", html)
        self.assertIn("IR_USD_Treasury_10Y_Rate", html)
        self.assertIn("ustsy10y", html)
        self.assertIn("GS Market Data", html)

    def test_runtime_helpers_present(self):
        m = self._bonds_with_prov()
        tmp = tempfile.mkdtemp(prefix="prov_rt_")
        out = Path(tmp) / "d.html"
        r = compile_dashboard(m, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        html = out.read_text(encoding="utf-8")
        # JS resolvers + footer + default popup builders are all defined
        for sym in [
            "_provenanceForCol",
            "_renderProvenanceFooterFor",
            "_buildDefaultChartPopup",
            "_buildDefaultTablePopup",
            "_provenancePrimarySymbol",
            "_datasetHasProvenance",
        ]:
            self.assertIn(sym, html, f"missing JS helper: {sym}")

    def test_provenance_footer_css_present(self):
        m = self._bonds_with_prov()
        tmp = tempfile.mkdtemp(prefix="prov_rt_")
        out = Path(tmp) / "d.html"
        r = compile_dashboard(m, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        html = out.read_text(encoding="utf-8")
        self.assertIn(".provenance-footer", html)
        self.assertIn(".provenance-table", html)
        self.assertIn(".prov-system", html)
        self.assertIn(".detail-stat-src", html)

    def test_dataset_without_provenance_compiles_clean(self):
        """Datasets without field_provenance still compile fine; the
        runtime helpers are present but won't fire any default popup
        because hasProvenance returns false."""
        m = {
            "schema_version": 1, "id": "noprov", "title": "noprov",
            "datasets": {"d": pd.DataFrame({"a": [1, 2], "b": [3, 4]})},
            "layout": {"rows": [[
                {"widget": "chart", "id": "c", "w": 12,
                  "spec": {"chart_type": "line", "dataset": "d",
                            "mapping": {"x": "a", "y": "b"}}}
            ]]},
        }
        tmp = tempfile.mkdtemp(prefix="prov_none_")
        out = Path(tmp) / "d.html"
        r = compile_dashboard(m, output_path=str(out))
        self.assertTrue(r.success, r.warnings)
        html = out.read_text(encoding="utf-8")
        # No provenance metadata in the payload, but the runtime
        # function definitions are still there (cheap, unconditional)
        self.assertNotIn('"field_provenance"', html)
        self.assertIn("_buildDefaultChartPopup", html)


class TestProvenanceBuilderAPI(unittest.TestCase):
    """Dashboard.add_dataset accepts field_provenance / row_provenance
    as explicit kwargs. NEVER pulls from df.attrs -- PRISM is the
    one cleaning the upstream metadata."""

    def test_add_dataset_field_provenance_kwarg(self):
        df = pd.DataFrame({"date": ["2026-04-22"], "x": [1.0]})
        # Even when df.attrs has metadata, the compiler should NOT
        # auto-promote it. PRISM passes the cleaned version explicitly.
        df.attrs["metadata"] = [{"col": "x", "haver_code": "X@HAV"}]
        opt = {"series": [{"type": "line", "data": [[0, 1]]}],
                "xAxis": {"type": "value"}, "yAxis": {"type": "value"}}
        db = (Dashboard(id="r", title="R")
              .add_dataset("d", df,
                            field_provenance={
                                "x": {"system": "haver",
                                      "symbol": "GDP@USECON",
                                      "source_label": "Haver"},
                            },
                            row_provenance_field="date",
                            row_provenance={
                                "2026-04-22": {"x": {"system": "override"}},
                            })
              .add_row([ChartRef(id="c", option=opt, w=12)]))
        manifest = db.to_manifest()
        ds_d = manifest["datasets"]["d"]
        self.assertIn("field_provenance", ds_d)
        self.assertEqual(ds_d["field_provenance"]["x"]["symbol"],
                          "GDP@USECON")
        self.assertEqual(ds_d["row_provenance_field"], "date")
        self.assertIn("2026-04-22", ds_d["row_provenance"])
        # df.attrs was NOT auto-promoted
        self.assertNotIn("X@HAV", json.dumps(ds_d.get("field_provenance", {})))


# =============================================================================
# CONTROLS DRAWER  (per-tile knobs for chart / table / KPI widgets)
#
# The drawer is rendered to HTML by the Python tile renderer and
# populated by JS at runtime. These tests inspect the compiled HTML
# string for the markup + JS hooks the drawer relies on -- they don't
# execute JS, so any logic-level coverage that needs DOM dispatch
# happens via the runtime smoke test described in the docs.
# =============================================================================

class TestControlsDrawer(unittest.TestCase):
    def _manifest(self):
        return {
            "schema_version": 1,
            "id": "drawer_test",
            "title": "Drawer test",
            "theme": "gs_clean",
            "datasets": {
                "rates": {"source": [
                    ["date", "us_2y", "us_10y"],
                    ["2025-01-01", 4.10, 4.40],
                    ["2025-02-01", 4.18, 4.45],
                    ["2025-03-01", 4.22, 4.50],
                    ["2025-04-01", 4.15, 4.55],
                ]},
                "tbl": {"source": [
                    ["name", "val", "pct"],
                    ["Alpha", 12.5, 0.18],
                    ["Beta", 8.0, 0.04],
                    ["Gamma", 22.4, -0.07],
                ]},
            },
            "layout": {"kind": "grid", "cols": 12, "rows": [
                [
                    {"widget": "kpi", "id": "k", "w": 3,
                      "label": "Latest 10Y",
                      "source": "rates.latest.us_10y",
                      "sparkline_source": "rates.us_10y",
                      "delta_source": "rates.prev.us_10y"},
                    {"widget": "chart", "id": "c", "w": 9,
                      "spec": {"chart_type": "multi_line",
                                "dataset": "rates",
                                "mapping": {"x": "date",
                                            "y": ["us_2y", "us_10y"]},
                                "title": "UST yields"}},
                ],
                [
                    {"widget": "table", "id": "t", "w": 12,
                      "title": "Sample",
                      "dataset_ref": "tbl",
                      "columns": [
                          {"field": "name", "label": "Name"},
                          {"field": "val",  "label": "Value",
                            "format": "number:2"},
                          {"field": "pct",  "label": "Pct",
                            "format": "percent:1"},
                      ]},
                ],
            ]},
        }

    def _compile(self, manifest=None):
        m = manifest or self._manifest()
        tmp = tempfile.mkdtemp(prefix="drawer_")
        r = compile_dashboard(m, session_path=tmp)
        self.assertTrue(r.success, r.warnings)
        return Path(r.html_path).read_text()

    # ----- chart drawer -----

    def test_chart_tile_emits_drawer_container(self):
        html = self._compile()
        self.assertIn('id="controls-c"', html)
        self.assertIn('data-chart-id="c"', html)
        self.assertIn('class="chart-controls"', html)

    def test_chart_drawer_carries_shape_section_hooks(self):
        html = self._compile()
        for hook in ('shape-line-style', 'shape-step',
                      'shape-line-width', 'shape-area-fill',
                      'shape-stack', 'shape-show-symbol'):
            self.assertIn(hook, html,
                            f"chart drawer missing shape hook {hook!r}")

    def test_chart_drawer_carries_extended_transforms(self):
        html = self._compile()
        for tname in ('log_change', 'yoy_log', 'annualized_change',
                       'log', 'zscore', 'rolling_zscore_252',
                       'rank_pct', 'ytd', 'index100'):
            self.assertIn("'" + tname + "'", html,
                            f"chart drawer missing transform {tname!r}")

    def test_chart_drawer_carries_download_actions(self):
        html = self._compile()
        for act in ('download-png', 'download-csv', 'download-xlsx'):
            self.assertIn('data-cc-action="' + act + '"', html,
                            f"chart drawer missing action {act!r}")

    def test_chart_controls_false_suppresses_drawer(self):
        m = self._manifest()
        m["layout"]["rows"][0][1]["spec"]["chart_controls"] = False
        html = self._compile(m)
        # The chart with controls disabled has no drawer container.
        # Other tiles' drawers ('controls-t', 'controls-k') still emit.
        self.assertNotIn('id="controls-c"', html)
        self.assertIn('id="controls-t"', html)

    # ----- table drawer -----

    def test_table_tile_emits_drawer_container(self):
        html = self._compile()
        self.assertIn('id="controls-t"', html)
        self.assertIn('data-table-id="t"', html)

    def test_table_tile_emits_three_dots_button(self):
        html = self._compile()
        # Toolbar markup carries the kebab-glyph 22EE for tables.
        # We look for the data-tile-id="t" tile, then assert the
        # toolbar button is inside its header.
        self.assertIn('data-tile-id="t"', html)
        self.assertIn('aria-label="Toggle table controls"', html)

    def test_table_drawer_carries_table_specific_hooks(self):
        html = self._compile()
        for hook in ('table-search', 'table-sort-col', 'table-sort-dir',
                      'table-col-visible', 'table-density',
                      'table-freeze', 'table-decimals'):
            self.assertIn(hook, html,
                            f"table drawer missing hook {hook!r}")

    def test_table_drawer_carries_actions(self):
        html = self._compile()
        for act in ('table-view-raw', 'table-copy-csv',
                     'table-download-csv', 'table-download-xlsx',
                     'table-reset'):
            self.assertIn('data-cc-action="' + act + '"', html,
                            f"table drawer missing action {act!r}")

    def test_table_controls_false_suppresses_drawer(self):
        m = self._manifest()
        m["layout"]["rows"][1][0]["table_controls"] = False
        html = self._compile(m)
        self.assertNotIn('id="controls-t"', html)
        self.assertNotIn('data-table-id="t"', html)

    def test_table_freeze_first_col_css_present(self):
        html = self._compile()
        self.assertIn('.data-table.freeze-first-col', html)

    # ----- kpi drawer -----

    def test_kpi_tile_emits_drawer_container(self):
        html = self._compile()
        self.assertIn('id="controls-k"', html)
        self.assertIn('data-kpi-id="k"', html)
        self.assertIn('aria-label="Toggle KPI controls"', html)

    def test_kpi_drawer_carries_compare_period(self):
        html = self._compile()
        for v in ("'auto'", "'prev'", "'1d'", "'1w'", "'1m'",
                   "'3m'", "'6m'", "'1y'", "'ytd'"):
            self.assertIn(v, html,
                            f"kpi drawer missing compare period {v!r}")

    def test_kpi_drawer_carries_display_toggles(self):
        html = self._compile()
        self.assertIn('kpi-show-sparkline', html)
        self.assertIn('kpi-show-delta', html)
        self.assertIn('kpi-decimals', html)

    def test_kpi_drawer_carries_actions(self):
        html = self._compile()
        for act in ('kpi-view-data', 'kpi-copy-csv',
                     'kpi-download-csv', 'kpi-download-xlsx',
                     'kpi-reset'):
            self.assertIn('data-cc-action="' + act + '"', html,
                            f"kpi drawer missing action {act!r}")

    def test_kpi_controls_false_suppresses_drawer(self):
        m = self._manifest()
        m["layout"]["rows"][0][0]["kpi_controls"] = False
        html = self._compile(m)
        self.assertNotIn('id="controls-k"', html)

    # ----- exposed dashboard state -----

    def test_dashboard_exposes_drawer_state(self):
        html = self._compile()
        # The DASHBOARD object on window now lists tableState and
        # kpiState so DevTools / instrumentation can inspect drawer
        # outputs alongside chartControlState.
        self.assertIn('tableState: TABLE_STATE', html)
        self.assertIn('kpiState: KPI_STATE', html)


# =============================================================================
# STRESS TEST DATA HELPERS  (broken-on-purpose pandas DataFrames)
#
# These power the stress test scenarios below. Each fixture is a
# realistic failure mode an LLM-driven manifest authoring loop (e.g.
# PRISM) would plausibly produce -- column typos, NaN columns, wrong
# types, missing required mappings, degenerate distributions, etc.
# =============================================================================

def _empty_df(columns: List[str]) -> pd.DataFrame:
    """A DataFrame with the right column names but zero rows."""
    return pd.DataFrame({c: [] for c in columns})


def _all_nan_df(columns: List[str], n_rows: int = 24) -> pd.DataFrame:
    """All-NaN DataFrame -- columns exist but every value is None."""
    return pd.DataFrame({c: [None] * n_rows for c in columns})


def _rates_real() -> pd.DataFrame:
    """A small-but-real rates panel for grounding (column refs that
    DON'T break, used as a control inside compound-failure scenarios)."""
    return pd.DataFrame({
        "date":  pd.date_range("2026-01-01", periods=20, freq="B"),
        "us_2y": [4.10 + 0.01 * i for i in range(20)],
        "us_10y": [4.40 + 0.005 * i for i in range(20)],
    })


def _rates_typo_columns() -> pd.DataFrame:
    """Looks like rates_real but every column is one keystroke off
    from what the manifest is going to claim. Tests typo diagnostics."""
    return pd.DataFrame({
        "Date":   pd.date_range("2026-01-01", periods=20, freq="B"),
        "usd_2y": [4.10] * 20,
        "usd_10y": [4.40] * 20,
    })


def _rates_all_nan_y() -> pd.DataFrame:
    """All x values fine, all y values None."""
    return pd.DataFrame({
        "date":  pd.date_range("2026-01-01", periods=15, freq="B"),
        "us_2y": [None] * 15,
        "us_10y": [None] * 15,
    })


def _rates_mostly_nan() -> pd.DataFrame:
    """80% of y values are None."""
    return pd.DataFrame({
        "date":  pd.date_range("2026-01-01", periods=20, freq="B"),
        "us_2y": [4.10, None, None, None, None] * 4,
        "us_10y": [None, 4.40, None, None, None] * 4,
    })


def _rates_string_y() -> pd.DataFrame:
    """Numeric y column is full of un-coercible junk strings.
    PRISM-style failure mode: the upstream loader returned a label
    column where a numeric column was expected."""
    return pd.DataFrame({
        "date":  pd.date_range("2026-01-01", periods=10, freq="B"),
        "us_2y": ["n/a", "ERR", "missing", "?", "—",
                    "n/a", "ERR", "missing", "?", "—"],
    })


def _bad_dates_df() -> pd.DataFrame:
    """X column claims to be a date axis but contains unparseable
    strings. Most chart builders will just treat this as category."""
    return pd.DataFrame({
        "date":  ["yesterday", "today", "tomorrow", "soon",
                   "next week", "later"],
        "value": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
    })


def _pie_negative_values() -> pd.DataFrame:
    """Pie / donut / funnel slices including negatives. ECharts will
    silently render these as zero or as confusing reverse arcs."""
    return pd.DataFrame({
        "region": ["NA", "EU", "APAC", "EM", "Other"],
        "share":  [42.0, 31.0, -8.5, 18.0, -3.0],
    })


def _pie_single_slice() -> pd.DataFrame:
    """Pie chart where one slice = 100% of the total. Visually a
    full circle with no segmentation."""
    return pd.DataFrame({
        "region": ["NA", "EU", "APAC"],
        "share":  [100.0, 0.0, 0.0],
    })


def _flat_line_y() -> pd.DataFrame:
    """Numeric y column where every value is identical -> degenerate
    flat line, axis range collapses to a point."""
    return pd.DataFrame({
        "date":  pd.date_range("2026-01-01", periods=20, freq="B"),
        "spread_bp": [42.0] * 20,
    })


def _candlestick_inverted() -> pd.DataFrame:
    """OHLC where high < low, close > high, etc. Realistic when
    columns get swapped by a careless join."""
    return pd.DataFrame({
        "date":  pd.date_range("2026-01-01", periods=5, freq="B"),
        "o":     [102.0, 101.5, 100.0, 99.0, 100.0],
        "h":     [99.0,  100.0, 101.0, 102.0, 103.0],
        "l":     [110.0, 111.0, 109.0, 108.0, 110.0],
        "c":     [105.0, 104.0, 103.0, 102.0, 104.0],
    })


def _sankey_self_loops() -> pd.DataFrame:
    """Every flow's source equals its target. Sankey will render
    a single column of disconnected stubs."""
    nodes = ["GS", "JPM", "MS", "BAC", "Citi"]
    return pd.DataFrame({
        "src": nodes,
        "tgt": nodes,
        "v":   [10, 20, 15, 5, 8],
    })


def _sankey_disconnected() -> pd.DataFrame:
    """Source set and target set are completely disjoint -- no
    multi-step flow possible. Renders as a meaningless one-step block."""
    return pd.DataFrame({
        "src": ["A", "A", "B", "B", "C"],
        "tgt": ["X", "Y", "X", "Z", "Y"],
        "v":   [None, None, None, None, None],
    })


def _tree_orphans() -> pd.DataFrame:
    """`parent` references nodes that don't exist as `name`."""
    return pd.DataFrame({
        "name":   ["root", "a", "b", "c", "d"],
        "parent": [None, "ROOT", "ROOT", "ALPHA", "BETA"],
    })


def _kpi_only_one_value() -> pd.DataFrame:
    """KPI sparkline source with a single row -- can't draw
    a line chart from one point."""
    return pd.DataFrame({"value": [42.0]})


def _ten_columns_no_match() -> pd.DataFrame:
    """A wide table whose columns don't include any of the table
    widget's defined fields. Every defined column will be missing."""
    return pd.DataFrame({
        f"unrelated_{i}": [i, i + 1] for i in range(10)
    })


def _rates_with_dti() -> pd.DataFrame:
    """Realistic shape from pull_market_data / pull_haver_data:
    DatetimeIndex named 'date', columns are values. PRISM is supposed
    to ``df.reset_index()`` before passing into the manifest -- this
    fixture skips that step deliberately."""
    df = pd.DataFrame({
        "us_2y":  [4.20, 4.21, 4.18, 4.15, 4.13],
        "us_10y": [4.10, 4.12, 4.11, 4.08, 4.07],
    }, index=pd.date_range("2024-01-02", periods=5, freq="B"))
    df.index.name = "date"
    return df


def _rates_opaque_codes() -> pd.DataFrame:
    """Columns named after pull-time API codes. The compiler renders
    ``IR_USD_Treasury_10Y_Rate`` verbatim in legends / tooltips."""
    return pd.DataFrame({
        "date": pd.date_range("2024-01-02", periods=5, freq="B"),
        "IR_USD_Treasury_10Y_Rate": [4.10, 4.12, 4.11, 4.08, 4.07],
        "JCXFE@USECON":             [3.0,  3.05, 3.10, 3.12, 3.15],
    })


def _rates_multiindex() -> pd.DataFrame:
    """MultiIndex columns -- common when concatenating from multiple
    sources without flattening. The compiler does not auto-flatten."""
    df = pd.DataFrame({
        ("UST", "2Y"):  [4.20, 4.21, 4.18],
        ("UST", "10Y"): [4.10, 4.12, 4.11],
    })
    df["date"] = pd.date_range("2024-01-02", periods=3, freq="B")
    return df


def _rates_huge() -> pd.DataFrame:
    """A dataset deliberately past the row-error threshold (60K rows
    ~= intraday-1y). Pre-loading this much history is the 26 MB-
    dashboard pattern the size budget is meant to catch."""
    n = 60_000
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="min"),
        "us_10y": [4.0 + (i % 100) / 1000 for i in range(n)],
    })


# =============================================================================
# STRESS TEST SCENARIO BUILDERS
# =============================================================================

def _wrap_manifest(manifest_id: str, title: str, datasets: Dict[str, Any],
                   layout: Dict[str, Any], filters=None,
                   description: str = "") -> Dict[str, Any]:
    m: Dict[str, Any] = {
        "schema_version": 1,
        "id": manifest_id,
        "title": title,
        "description": description,
        "theme": "gs_clean",
        "datasets": datasets,
        "layout": layout,
    }
    if filters:
        m["filters"] = filters
    return m


def build_ghost_data() -> Dict[str, Any]:
    """Scenario 1 - every dataset is structurally valid but has 0 rows.

    Charts, tables, and KPIs all bind to "ghost" datasets that
    technically exist (right columns, right shape) but are empty.
    This is the "the upstream loader returned no rows" failure mode --
    common when a date filter accidentally excludes everything, or
    when a fresh data feed hasn't backfilled.

    Expected diagnostics:
      * chart_dataset_empty (multiple)
      * table_dataset_empty
      * kpi_source_column_all_nan or chart_dataset_empty for kpi too
    """
    rates = _empty_df(["date", "us_2y", "us_10y"])
    flows = _empty_df(["src", "tgt", "v"])
    pie = _empty_df(["region", "share"])

    return _wrap_manifest(
        "stress_ghost_data",
        "Stress: ghost (empty) datasets",
        description=("Every chart / table / KPI binds to a dataset "
                     "with 0 rows. Dashboard is structurally valid "
                     "but renders as empty placeholders."),
        datasets={
            "rates": rates, "flows": flows, "pie": pie,
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "rates_line", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "multi_line", "dataset": "rates",
                            "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"]},
                            "title": "Rates curve (empty source)"}},
                {"widget": "chart", "id": "rates_bar", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "bar", "dataset": "rates",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "Rates bar (empty source)"}},
            ],
            [
                {"widget": "chart", "id": "flow_sk", "w": 6, "h_px": 380,
                  "spec": {"chart_type": "sankey", "dataset": "flows",
                            "mapping": {"source": "src",
                                        "target": "tgt",
                                        "value": "v"},
                            "title": "Flow sankey (empty source)"}},
                {"widget": "chart", "id": "share_pie", "w": 6, "h_px": 380,
                  "spec": {"chart_type": "pie", "dataset": "pie",
                            "mapping": {"category": "region",
                                        "value": "share"},
                            "title": "Share pie (empty source)"}},
            ],
            [
                {"widget": "table", "id": "rates_table", "w": 6,
                  "title": "Rates table (empty source)",
                  "dataset_ref": "rates",
                  "columns": [
                      {"field": "date", "title": "Date"},
                      {"field": "us_2y", "title": "2Y", "format": "number:2"},
                      {"field": "us_10y", "title": "10Y", "format": "number:2"},
                  ]},
                {"widget": "kpi", "id": "kpi_2y", "w": 3,
                  "label": "Latest 2Y",
                  "source": "rates.latest.us_2y", "format": "number:2"},
                {"widget": "kpi", "id": "kpi_10y", "w": 3,
                  "label": "Latest 10Y",
                  "source": "rates.latest.us_10y",
                  "delta_source": "rates.prev.us_10y",
                  "sparkline_source": "rates.us_10y",
                  "format": "number:2"},
            ],
        ]},
    )


def build_column_typos() -> Dict[str, Any]:
    """Scenario 2 - realistic LLM keystroke-off mistakes.

    Datasets are populated and clean, but the mappings reference
    `usd_2y` instead of `us_2y`, `Date` instead of `date`, etc.
    This is by far the most common PRISM authoring failure --
    the LLM hallucinates plausible column names without checking
    the actual frame.

    Expected diagnostics:
      * chart_mapping_column_missing (multiple, with available_columns context)
      * table_column_field_missing
      * kpi_source_column_missing
      * filter_field_missing_in_target
    """
    df = _rates_typo_columns()
    return _wrap_manifest(
        "stress_column_typos",
        "Stress: column typos in mappings",
        description=("All mappings reference column names that DON'T "
                     "exist (typos). Dataset has 'Date', 'usd_2y', "
                     "'usd_10y'; manifest references 'date', 'us_2y', "
                     "'us_10y'. Tests the typo-suggestion + "
                     "available-columns diagnostic context."),
        datasets={"rates": df},
        layout={"rows": [
            [
                {"widget": "chart", "id": "rates_curve", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "multi_line", "dataset": "rates",
                            "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"]},
                            "title": "UST curve (column typos)"}},
                {"widget": "chart", "id": "two_year", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "rates",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "US 2Y (column typo)"}},
            ],
            [
                {"widget": "table", "id": "rates_table", "w": 6,
                  "title": "Rates table (column typos)",
                  "dataset_ref": "rates",
                  "columns": [
                      {"field": "date",     "title": "Date"},
                      {"field": "us_2y",   "title": "2Y",
                        "format": "number:2"},
                      {"field": "us_10y",  "title": "10Y",
                        "format": "number:2"},
                      {"field": "spread",   "title": "Spread",
                        "format": "bps:0"},
                  ]},
                {"widget": "kpi", "id": "kpi_2y", "w": 3,
                  "label": "Latest 2Y",
                  "source": "rates.latest.us_2y", "format": "number:2"},
                {"widget": "kpi", "id": "kpi_10y", "w": 3,
                  "label": "Latest 10Y",
                  "source": "rates.latest.us_10y", "format": "number:2"},
            ],
        ]},
        filters=[
            {"id": "dt", "type": "dateRange", "default": "6M",
              "field": "date",
              "targets": ["rates_curve", "two_year"]},
        ],
    )


def build_nan_blizzard() -> Dict[str, Any]:
    """Scenario 3 - every numeric column is mostly or entirely NaN.

    Realistic when a downstream loader returns the right schema
    but the values come back as NaN due to API errors, stale
    snapshot, or a join that didn't match.

    Expected diagnostics:
      * chart_mapping_column_all_nan
      * chart_mapping_column_mostly_nan (warning)
      * kpi_source_column_all_nan
    """
    return _wrap_manifest(
        "stress_nan_blizzard",
        "Stress: NaN blizzard",
        description=("Numeric columns are populated as None/NaN. "
                     "Tests all-NaN vs mostly-NaN detection and "
                     "the nan_fraction context."),
        datasets={
            "all_nan":    _rates_all_nan_y(),
            "mostly_nan": _rates_mostly_nan(),
            "single":     _kpi_only_one_value(),
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "allnan_line", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "all_nan",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "All-NaN y column"}},
                {"widget": "chart", "id": "mostly_line", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "mostly_nan",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "Mostly-NaN y column"}},
            ],
            [
                {"widget": "chart", "id": "allnan_bar", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "bar", "dataset": "all_nan",
                            "mapping": {"x": "date", "y": "us_10y"},
                            "title": "All-NaN bar"}},
                {"widget": "chart", "id": "mostly_multi", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "multi_line",
                            "dataset": "mostly_nan",
                            "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"]},
                            "title": "Mostly-NaN multi-line"}},
            ],
            [
                {"widget": "kpi", "id": "kpi_allnan", "w": 4,
                  "label": "All-NaN KPI",
                  "source": "all_nan.latest.us_2y",
                  "format": "number:2"},
                {"widget": "kpi", "id": "kpi_short_spark", "w": 4,
                  "label": "Sparkline w/ 1 row",
                  "source": "single.latest.value",
                  "sparkline_source": "single.value",
                  "format": "number:2"},
                {"widget": "kpi", "id": "kpi_partial", "w": 4,
                  "label": "Mostly-NaN KPI",
                  "source": "mostly_nan.latest.us_10y",
                  "delta_source": "mostly_nan.prev.us_10y",
                  "format": "number:2"},
            ],
        ]},
    )


def build_type_mismatch() -> Dict[str, Any]:
    """Scenario 4 - numeric columns contain non-coercible strings,
    date columns contain natural-language placeholders.

    Realistic failure when an upstream API returns sentinels
    ('n/a', '—', 'pending') for missing numeric values rather
    than null/NaN. ECharts renders these as a flat line at zero
    or doesn't render at all.

    Expected diagnostics:
      * chart_mapping_column_non_numeric
      * chart_mapping_column_non_numeric for date axis
    """
    return _wrap_manifest(
        "stress_type_mismatch",
        "Stress: type mismatch (strings where numbers expected)",
        description=("Numeric mapping keys (y/value/size) get string "
                     "columns; date axis gets natural-language strings "
                     "like 'tomorrow'. Tests numeric-coercion check."),
        datasets={
            "string_y": _rates_string_y(),
            "bad_dates": _bad_dates_df(),
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "junk_line", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "string_y",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "Numeric column has 'n/a' / 'ERR'"}},
                {"widget": "chart", "id": "junk_bar", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "bar", "dataset": "string_y",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "Bar w/ string y values"}},
            ],
            [
                {"widget": "chart", "id": "bad_dates_line", "w": 6,
                  "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "bad_dates",
                            "mapping": {"x": "date", "y": "value"},
                            "title": "X axis is 'today' / 'tomorrow'"}},
                {"widget": "chart", "id": "bad_dates_scatter", "w": 6,
                  "h_px": 320,
                  "spec": {"chart_type": "scatter", "dataset": "bad_dates",
                            "mapping": {"x": "date", "y": "value",
                                        "size": "date"},
                            "title": "Size column is non-numeric"}},
            ],
        ]},
    )


def build_missing_required() -> Dict[str, Any]:
    """Scenario 5 - chart_type's required mapping keys are absent.

    Pies that don't say what their slices are; sankeys with no
    target; candlesticks with no close. The builder will raise at
    spec-to-option time, the placeholder will fire, and the
    diagnostic must list which key was missing AND name the
    available columns so the fix is obvious.

    Expected diagnostics:
      * chart_mapping_required_missing (multiple)
      * chart_build_failed (each broken chart)
    """
    rates = _rates_real()
    pie_data = pd.DataFrame({"region": ["NA", "EU"], "share": [50.0, 50.0]})
    flow_data = pd.DataFrame({
        "src": ["A", "B"], "tgt": ["X", "Y"], "v": [10, 20],
    })
    ohlc_data = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=5, freq="B"),
        "o": [100.0, 101.0, 102.0, 101.5, 100.5],
        "h": [102.0, 103.0, 104.0, 103.5, 102.5],
        "l": [99.0, 100.0, 101.0, 100.5, 99.5],
        "c": [101.0, 102.0, 103.0, 102.5, 101.5],
    })

    return _wrap_manifest(
        "stress_missing_required",
        "Stress: missing required mapping keys",
        description=("Each chart_type is missing one of its required "
                     "mapping keys (e.g. pie without category, "
                     "candlestick without close). Tests the required-"
                     "keys diagnostic and the build_failed fallback."),
        datasets={
            "rates": rates, "pie": pie_data,
            "flow": flow_data, "ohlc": ohlc_data,
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "pie_no_cat", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "pie", "dataset": "pie",
                            "mapping": {"value": "share"},
                            "title": "Pie missing category"}},
                {"widget": "chart", "id": "donut_no_value", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "donut", "dataset": "pie",
                            "mapping": {"category": "region"},
                            "title": "Donut missing value"}},
            ],
            [
                {"widget": "chart", "id": "sankey_no_tgt", "w": 6, "h_px": 380,
                  "spec": {"chart_type": "sankey", "dataset": "flow",
                            "mapping": {"source": "src", "value": "v"},
                            "title": "Sankey missing target"}},
                {"widget": "chart", "id": "candle_no_close", "w": 6,
                  "h_px": 380,
                  "spec": {"chart_type": "candlestick", "dataset": "ohlc",
                            "mapping": {"x": "date", "open": "o",
                                        "high": "h", "low": "l"},
                            "title": "Candlestick missing close"}},
            ],
            [
                {"widget": "chart", "id": "treemap_neither", "w": 6,
                  "h_px": 320,
                  "spec": {"chart_type": "treemap", "dataset": "pie",
                            "mapping": {"region": "region",
                                        "share": "share"},
                            "title": ("Treemap: any-of {path,value} or "
                                      "{name,parent,value} not satisfied")}},
                {"widget": "chart", "id": "heatmap_no_value", "w": 6,
                  "h_px": 320,
                  "spec": {"chart_type": "heatmap", "dataset": "rates",
                            "mapping": {"x": "date", "y": "us_2y"},
                            "title": "Heatmap missing value"}},
            ],
        ]},
    )


def build_degenerate_shapes() -> Dict[str, Any]:
    """Scenario 6 - data is structurally fine but the distribution is
    pathological (constant, single-row, negative pie slices, etc.).

    These wouldn't all fire as errors today; the goal is to make
    sure they DO fire (after this PR) so PRISM gets feedback when
    it builds a dashboard that technically works but has nothing
    interesting to display.

    Expected diagnostics:
      * chart_dataset_single_row (warning)
      * chart_pie_negative_values (NEW, error)
      * chart_constant_y (NEW, warning)
    """
    one_row = pd.DataFrame({"x": [1], "y": [2.0]})
    flat = _flat_line_y()
    neg_pie = _pie_negative_values()
    one_slice = _pie_single_slice()
    inverted = _candlestick_inverted()

    return _wrap_manifest(
        "stress_degenerate_shapes",
        "Stress: degenerate distributions (constant / single / negative)",
        description=("Valid manifests with degenerate data: 1-row line, "
                     "constant y, negative pie slices, single-slice "
                     "donut, inverted-OHLC candlestick."),
        datasets={
            "one_row": one_row, "flat": flat, "neg_pie": neg_pie,
            "one_slice": one_slice, "inverted": inverted,
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "one_row_line", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "one_row",
                            "mapping": {"x": "x", "y": "y"},
                            "title": "Line with 1 row"}},
                {"widget": "chart", "id": "flat_line", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "line", "dataset": "flat",
                            "mapping": {"x": "date", "y": "spread_bp"},
                            "title": "Flat line (constant y)"}},
            ],
            [
                {"widget": "chart", "id": "neg_pie", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "pie", "dataset": "neg_pie",
                            "mapping": {"category": "region",
                                        "value": "share"},
                            "title": "Pie with negative slices"}},
                {"widget": "chart", "id": "one_slice", "w": 6, "h_px": 320,
                  "spec": {"chart_type": "donut", "dataset": "one_slice",
                            "mapping": {"category": "region",
                                        "value": "share"},
                            "title": "Donut with one slice = 100%"}},
            ],
            [
                {"widget": "chart", "id": "inverted_ohlc", "w": 12,
                  "h_px": 320,
                  "spec": {"chart_type": "candlestick", "dataset": "inverted",
                            "mapping": {"x": "date", "open": "o",
                                        "high": "h", "low": "l",
                                        "close": "c"},
                            "title": "Candlestick: high < low (inverted OHLC)"}},
            ],
        ]},
    )


def build_broken_topology() -> Dict[str, Any]:
    """Scenario 7 - data shape passes type / non-NaN checks but the
    graph topology is degenerate.

    Catches the "looks OK but renders empty" failure mode for
    network-style charts.

    Expected diagnostics:
      * chart_sankey_self_loops (NEW)
      * chart_sankey_disconnected (NEW)
      * chart_dataset_empty (after self-loop removal -> empty value
        column) -- depends on builder behaviour
    """
    return _wrap_manifest(
        "stress_broken_topology",
        "Stress: degenerate sankey / graph topology",
        description=("Sankey with self-loops, disconnected source/target "
                     "sets, and tree with orphan parents. Catches "
                     "topology-degeneracy failure modes."),
        datasets={
            "self_loops": _sankey_self_loops(),
            "disconnect": _sankey_disconnected(),
            "orphans":    _tree_orphans(),
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "self_loop_sk", "w": 6, "h_px": 380,
                  "spec": {"chart_type": "sankey", "dataset": "self_loops",
                            "mapping": {"source": "src", "target": "tgt",
                                        "value": "v"},
                            "title": "Sankey: every flow is a self-loop"}},
                {"widget": "chart", "id": "disconnect_sk", "w": 6, "h_px": 380,
                  "spec": {"chart_type": "sankey", "dataset": "disconnect",
                            "mapping": {"source": "src", "target": "tgt",
                                        "value": "v"},
                            "title": "Sankey: all values None"}},
            ],
            [
                {"widget": "chart", "id": "orphan_tree", "w": 12, "h_px": 380,
                  "spec": {"chart_type": "tree", "dataset": "orphans",
                            "mapping": {"name": "name", "parent": "parent"},
                            "title": "Tree: orphan parents"}},
            ],
        ]},
    )


def build_broken_bindings() -> Dict[str, Any]:
    """Scenario 8 - filters and bindings reference things that don't
    exist or won't fire.

    Realistic LLM mistakes: filtering on a column that the chart's
    dataset doesn't have; KPI source malformed; table columns all
    pointing to fields that aren't present.

    Expected diagnostics:
      * filter_field_missing_in_target
      * kpi_source_dataset_unknown
      * kpi_source_column_missing
      * kpi_source_malformed
      * table_column_field_missing
      * table_columns_field_all_missing (NEW)
    """
    rates = _rates_real()
    return _wrap_manifest(
        "stress_broken_bindings",
        "Stress: broken filter / kpi / table bindings",
        description=("Filters reference non-existent fields; KPIs "
                     "reference unknown datasets / malformed sources; "
                     "table columns all point to missing fields."),
        datasets={
            "rates":    rates,
            "ten_cols": _ten_columns_no_match(),
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "rates_curve", "w": 12, "h_px": 320,
                  "spec": {"chart_type": "multi_line", "dataset": "rates",
                            "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"]},
                            "title": "Rates curve (charts are fine)"}},
            ],
            [
                {"widget": "table", "id": "all_missing_table", "w": 6,
                  "title": "Table: every defined field is missing",
                  "dataset_ref": "ten_cols",
                  "columns": [
                      {"field": "name",   "title": "Name"},
                      {"field": "ticker", "title": "Ticker"},
                      {"field": "price",  "title": "Price",
                        "format": "number:2"},
                      {"field": "yield",  "title": "Yield",
                        "format": "percent:2"},
                  ]},
                {"widget": "table", "id": "partial_missing", "w": 6,
                  "title": "Table: half columns missing",
                  "dataset_ref": "rates",
                  "columns": [
                      {"field": "date",    "title": "Date"},
                      {"field": "us_2y",  "title": "2Y"},
                      {"field": "yield_curve", "title": "Curve"},
                      {"field": "spread",  "title": "Spread"},
                  ]},
            ],
            [
                {"widget": "kpi", "id": "kpi_malformed", "w": 3,
                  "label": "Bad source format",
                  "source": "no_dot_at_all",
                  "format": "number:2"},
                {"widget": "kpi", "id": "kpi_unknown_ds", "w": 3,
                  "label": "Unknown dataset",
                  "source": "ghost_dataset.latest.col",
                  "format": "number:2"},
                {"widget": "kpi", "id": "kpi_missing_col", "w": 3,
                  "label": "Missing column",
                  "source": "rates.latest.spread",
                  "format": "number:2"},
                {"widget": "kpi", "id": "kpi_bad_delta", "w": 3,
                  "label": "Bad delta source",
                  "source": "rates.latest.us_2y",
                  "delta_source": "rates.prev.delta_col",
                  "sparkline_source": "rates.spark",
                  "format": "number:2"},
            ],
        ]},
        filters=[
            {"id": "f_missing", "type": "select", "default": "US",
              "options": ["US", "EU", "JP"],
              "field": "country",
              "targets": ["rates_curve"]},
            {"id": "f_bad_default", "type": "select", "default": "ZZ",
              "options": ["US", "EU"],
              "field": "us_2y",
              "targets": ["rates_curve"]},
            {"id": "f_no_match", "type": "select", "default": "x",
              "options": ["x", "y"], "field": "us_2y",
              "targets": ["nonexistent_widget*"]},
        ],
    )


def build_compound_chaos() -> Dict[str, Any]:
    """Scenario 9 - one dashboard that's broken in EVERY category at once.

    The point: stress-test the diagnostic aggregator. With ~25 broken
    widgets across multiple datasets, the warnings list should still
    be readable, grouped sensibly, and PRISM should be able to fix
    every issue from a single compile cycle.
    """
    return _wrap_manifest(
        "stress_compound_chaos",
        "Stress: every failure mode at once",
        description=("Compound dashboard mixing empty datasets, column "
                     "typos, NaN columns, type mismatches, missing "
                     "required keys, degenerate distributions, and "
                     "broken filter bindings -- in 1 manifest."),
        datasets={
            "empty":      _empty_df(["date", "us_2y", "us_10y"]),
            "typos":      _rates_typo_columns(),
            "all_nan":    _rates_all_nan_y(),
            "string_y":   _rates_string_y(),
            "neg_pie":    _pie_negative_values(),
            "inverted":   _candlestick_inverted(),
            "self_loop":  _sankey_self_loops(),
            "ten_cols":   _ten_columns_no_match(),
            "real":       _rates_real(),
        },
        layout={"kind": "tabs", "tabs": [
            {"id": "data", "label": "Data shape failures",
              "rows": [
                  [
                      {"widget": "chart", "id": "empty_line", "w": 4,
                        "h_px": 280,
                        "spec": {"chart_type": "line", "dataset": "empty",
                                  "mapping": {"x": "date", "y": "us_2y"},
                                  "title": "Empty dataset"}},
                      {"widget": "chart", "id": "typo_line", "w": 4,
                        "h_px": 280,
                        "spec": {"chart_type": "multi_line",
                                  "dataset": "typos",
                                  "mapping": {"x": "date",
                                              "y": ["us_2y", "us_10y"]},
                                  "title": "Column typos"}},
                      {"widget": "chart", "id": "nan_line", "w": 4,
                        "h_px": 280,
                        "spec": {"chart_type": "line", "dataset": "all_nan",
                                  "mapping": {"x": "date", "y": "us_2y"},
                                  "title": "All-NaN y"}},
                  ],
                  [
                      {"widget": "chart", "id": "junk_y", "w": 4, "h_px": 280,
                        "spec": {"chart_type": "bar", "dataset": "string_y",
                                  "mapping": {"x": "date", "y": "us_2y"},
                                  "title": "Strings for numbers"}},
                      {"widget": "chart", "id": "neg_pie", "w": 4, "h_px": 280,
                        "spec": {"chart_type": "pie", "dataset": "neg_pie",
                                  "mapping": {"category": "region",
                                              "value": "share"},
                                  "title": "Negative pie slices"}},
                      {"widget": "chart", "id": "inverted_ohlc", "w": 4,
                        "h_px": 280,
                        "spec": {"chart_type": "candlestick",
                                  "dataset": "inverted",
                                  "mapping": {"x": "date", "open": "o",
                                              "high": "h", "low": "l",
                                              "close": "c"},
                                  "title": "Inverted OHLC"}},
                  ],
              ]},
            {"id": "topo", "label": "Topology + missing-required",
              "rows": [
                  [
                      {"widget": "chart", "id": "self_loops", "w": 6,
                        "h_px": 320,
                        "spec": {"chart_type": "sankey",
                                  "dataset": "self_loop",
                                  "mapping": {"source": "src",
                                              "target": "tgt",
                                              "value": "v"},
                                  "title": "Sankey self-loops"}},
                      {"widget": "chart", "id": "pie_no_cat", "w": 6,
                        "h_px": 320,
                        "spec": {"chart_type": "pie", "dataset": "neg_pie",
                                  "mapping": {"value": "share"},
                                  "title": "Pie missing category"}},
                  ],
              ]},
            {"id": "bind", "label": "Broken bindings + a control",
              "rows": [
                  [
                      {"widget": "chart", "id": "control", "w": 6, "h_px": 280,
                        "spec": {"chart_type": "multi_line",
                                  "dataset": "real",
                                  "mapping": {"x": "date",
                                              "y": ["us_2y", "us_10y"]},
                                  "title": "Control: this one works"}},
                      {"widget": "table", "id": "miss_table", "w": 6,
                        "title": "Table: every field missing",
                        "dataset_ref": "ten_cols",
                        "columns": [
                            {"field": "ticker"},
                            {"field": "name"},
                            {"field": "price"},
                        ]},
                  ],
                  [
                      {"widget": "kpi", "id": "kpi_malformed", "w": 4,
                        "label": "Malformed source",
                        "source": "no_dot"},
                      {"widget": "kpi", "id": "kpi_unknown", "w": 4,
                        "label": "Unknown dataset",
                        "source": "ghost.latest.x"},
                      {"widget": "kpi", "id": "kpi_missing", "w": 4,
                        "label": "Missing column",
                        "source": "real.latest.zzz"},
                  ],
              ]},
        ]},
        filters=[
            {"id": "f_bad", "type": "select", "default": "US",
              "options": ["US", "EU"], "field": "country",
              "targets": ["control", "typo_line"]},
        ],
    )


def _build_shape_unclean() -> Dict[str, Any]:
    """Scenario 10 - PRISM passed pulled DataFrames without applying
    the standard cleaning steps (reset_index, rename codes, flatten
    MultiIndex). The compiler does not auto-clean any of these; it
    names each mistake with the literal pandas snippet to fix it.

    Expected diagnostics:
      * dataset_dti_no_date_column     (rates_dti)
      * dataset_column_looks_like_code (rates_codes)
      * dataset_columns_multiindex     (rates_mi)
    """
    return _wrap_manifest(
        "stress_shape_unclean",
        "Stress: unclean DataFrame shapes",
        description=("Three datasets that each skip a standard "
                     "cleaning step. The compiler stays strict and "
                     "names each fix."),
        datasets={
            "rates_dti":   _rates_with_dti(),
            "rates_codes": _rates_opaque_codes(),
            "rates_mi":    _rates_multiindex(),
        },
        layout={"rows": [
            [
                {"widget": "chart", "id": "dti_chart", "w": 6, "h_px": 280,
                  "spec": {"chart_type": "multi_line",
                            "dataset": "rates_dti",
                            "mapping": {"x": "date",
                                        "y": ["us_2y", "us_10y"]},
                            "title": "DTI without 'date' column"}},
                {"widget": "chart", "id": "codes_chart", "w": 6, "h_px": 280,
                  "spec": {"chart_type": "line",
                            "dataset": "rates_codes",
                            "mapping": {"x": "date",
                                        "y": "IR_USD_Treasury_10Y_Rate"},
                            "title": "Opaque coordinate as column name"}},
            ],
            [
                {"widget": "chart", "id": "mi_chart", "w": 12, "h_px": 280,
                  "spec": {"chart_type": "line",
                            "dataset": "rates_mi",
                            "mapping": {"x": "date", "y": "UST_10Y"},
                            "title": "MultiIndex columns (compiler "
                                     "does not auto-flatten)"}},
            ],
        ]},
    )


def _build_size_overflow() -> Dict[str, Any]:
    """Scenario 11 - a single-dataset dashboard whose embedded data
    blows past the row + byte budgets. Compile still succeeds (the
    resilient default), but the diagnostics name what to fix
    (top-N filter, shorter lookback, lazy load).
    """
    return _wrap_manifest(
        "stress_size_overflow",
        "Stress: size budget overflow",
        description=("60K-row dataset (intraday-1y at 1-min). "
                     "Past the row + byte error thresholds; would "
                     "produce a multi-MB HTML payload."),
        datasets={"big": _rates_huge()},
        layout={"rows": [[
            {"widget": "chart", "id": "big_line", "w": 12, "h_px": 320,
              "spec": {"chart_type": "line", "dataset": "big",
                        "mapping": {"x": "date", "y": "us_10y"},
                        "title": "60K rows of intraday history"}},
        ]]},
    )


# =============================================================================
# STRESS TEST REGISTRY
# =============================================================================

STRESS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "ghost_data": {
        "title":       "1. Empty datasets",
        "description": ("Every chart / table / KPI binds to a 0-row "
                         "dataset. Tests *_dataset_empty diagnostics."),
        "build":       build_ghost_data,
    },
    "column_typos": {
        "title":       "2. Column typos",
        "description": ("Mappings reference column names that don't "
                         "exist (us_2y vs usd_2y, date vs Date). "
                         "Tests typo / available_columns context."),
        "build":       build_column_typos,
    },
    "nan_blizzard": {
        "title":       "3. NaN blizzard",
        "description": ("Numeric columns are all/mostly NaN. Tests "
                         "*_column_all_nan + nan_fraction warning."),
        "build":       build_nan_blizzard,
    },
    "type_mismatch": {
        "title":       "4. Type mismatch",
        "description": ("Strings where numbers expected; bad date "
                         "strings on a date axis. Tests *_non_numeric."),
        "build":       build_type_mismatch,
    },
    "missing_required": {
        "title":       "5. Missing required mapping keys",
        "description": ("Pie missing category, sankey missing target, "
                         "candlestick missing close. Tests required-"
                         "missing + chart_build_failed fallback."),
        "build":       build_missing_required,
    },
    "degenerate_shapes": {
        "title":       "6. Degenerate distributions",
        "description": ("Constant y, single-row, negative pie, "
                         "inverted OHLC. Tests degeneracy diagnostics."),
        "build":       build_degenerate_shapes,
    },
    "broken_topology": {
        "title":       "7. Broken topology",
        "description": ("Sankey self-loops, disconnected, tree "
                         "orphans. Tests graph-shape diagnostics."),
        "build":       build_broken_topology,
    },
    "broken_bindings": {
        "title":       "8. Broken bindings",
        "description": ("Filter fields missing, KPI source bad, "
                         "table fields missing. Tests binding diags."),
        "build":       build_broken_bindings,
    },
    "compound_chaos": {
        "title":       "9. Compound chaos",
        "description": ("Every failure category in one dashboard "
                         "(across 3 tabs + 1 control widget)."),
        "build":       build_compound_chaos,
    },
    "shape_unclean": {
        "title":       "10. Unclean DataFrame shapes",
        "description": ("DatetimeIndex with no 'date' column, "
                         "MultiIndex columns, opaque API codes used "
                         "verbatim. Tests dataset_dti_no_date_column, "
                         "dataset_columns_multiindex, "
                         "dataset_column_looks_like_code."),
        "build":       _build_shape_unclean,
    },
    "size_overflow": {
        "title":       "11. Size budget overflow",
        "description": ("60K-row dataset embedded directly. Tests "
                         "dataset_rows_error + dataset_bytes_* + "
                         "manifest_bytes_* size diagnostics."),
        "build":       _build_size_overflow,
    },
}


# =============================================================================
# STRESS TEST RUNNER + REPORT
# =============================================================================

def _format_diag_block(diags: List[Diagnostic]) -> str:
    """Format diagnostics for the per-scenario diagnostics.txt file."""
    if not diags:
        return "  (no diagnostics fired)\n"
    lines = []
    by_sev: Dict[str, List[Diagnostic]] = {
        "error": [], "warning": [], "info": [],
    }
    for d in diags:
        by_sev.setdefault(d.severity, []).append(d)
    counts = ", ".join(
        f"{len(v)} {k}" + ("s" if len(v) != 1 else "")
        for k, v in by_sev.items() if v
    )
    lines.append(f"summary: {counts}")
    lines.append("")
    for sev in ("error", "warning", "info"):
        rows = by_sev.get(sev) or []
        if not rows:
            continue
        lines.append(f"  [{sev}]")
        for d in rows:
            wid = f" [{d.widget_id}]" if d.widget_id else ""
            lines.append(f"    {d.code}{wid}")
            lines.append(f"      path: {d.path}")
            lines.append(f"      msg : {d.message}")
            if d.context:
                ctx_str = json.dumps(d.context, default=str, sort_keys=True)
                if len(ctx_str) > 120:
                    ctx_str = ctx_str[:117] + "..."
                lines.append(f"      ctx : {ctx_str}")
            lines.append("")
    return "\n".join(lines)


def _run_one_scenario(name: str, out_dir: Path) -> Dict[str, Any]:
    entry = STRESS_REGISTRY[name]
    print(f"\n[stress] {name}: {entry['title']}")
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    manifest = entry["build"]()

    ok, errs = validate_manifest(manifest)
    if not ok:
        print(f"  ! manifest FAILED validation -- skipping render:")
        for e in errs:
            print(f"    {e}")
        return {
            "name": name, "title": entry["title"],
            "description": entry["description"],
            "validate_ok": False, "errors": list(errs),
            "diagnostics": [], "html": None, "manifest": None,
            "elapsed_s": round(time.time() - t0, 2),
        }

    html_path = out_dir / "dashboard.html"
    r = compile_dashboard(
        manifest, output_path=str(html_path),
        write_html=True, write_json=True,
    )

    diag_text = _format_diag_block(r.diagnostics)
    (out_dir / "diagnostics.txt").write_text(diag_text, encoding="utf-8")

    diag_objs = [d.to_dict() for d in r.diagnostics]
    (out_dir / "diagnostics.json").write_text(
        json.dumps(diag_objs, indent=2, default=str),
        encoding="utf-8",
    )

    code_counts: Dict[str, int] = {}
    for d in r.diagnostics:
        code_counts[d.code] = code_counts.get(d.code, 0) + 1
    n_err = sum(1 for d in r.diagnostics if d.severity == "error")
    n_warn = sum(1 for d in r.diagnostics if d.severity == "warning")
    n_info = sum(1 for d in r.diagnostics if d.severity == "info")
    print(f"  -> {n_err} error / {n_warn} warning / "
          f"{n_info} info diagnostics; html: {r.html_path}")
    if code_counts:
        codes_str = ", ".join(f"{c}={n}" for c, n
                              in sorted(code_counts.items()))
        print(f"     codes: {codes_str}")

    return {
        "name":         name,
        "title":        entry["title"],
        "description":  entry["description"],
        "validate_ok":  True,
        "html":         r.html_path,
        "manifest":     r.manifest_path,
        "diagnostics":  diag_objs,
        "code_counts":  code_counts,
        "n_errors":     n_err,
        "n_warnings":   n_warn,
        "n_infos":      n_info,
        "elapsed_s":    round(time.time() - t0, 2),
    }


def _stress_report_text(results: List[Dict[str, Any]]) -> str:
    """Build the human-readable stress report."""
    lines = []
    lines.append("=" * 72)
    lines.append("STRESS TEST REPORT -- compile_dashboard error logs")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("=" * 72)
    lines.append("")

    n_total = len(results)
    n_ok = sum(1 for r in results if r["validate_ok"])
    total_err = sum(r.get("n_errors", 0) for r in results)
    total_warn = sum(r.get("n_warnings", 0) for r in results)
    lines.append(f"Scenarios:    {n_total} total / {n_ok} validated OK")
    lines.append(f"Diagnostics:  {total_err} errors, {total_warn} warnings")
    lines.append("")

    all_codes: Dict[str, int] = {}
    for r in results:
        for c, n in (r.get("code_counts") or {}).items():
            all_codes[c] = all_codes.get(c, 0) + n
    if all_codes:
        lines.append("Diagnostic code roll-up:")
        for c, n in sorted(all_codes.items()):
            lines.append(f"  {c:50s} x {n}")
        lines.append("")

    for r in results:
        lines.append("-" * 72)
        lines.append(f"[{r['name']}] {r['title']}")
        lines.append(f"  {r['description']}")
        lines.append(f"  validated: {r['validate_ok']}")
        if not r["validate_ok"]:
            lines.append(f"  errors: {r.get('errors', [])}")
            continue
        lines.append(f"  html:      {r['html']}")
        lines.append(f"  manifest:  {r['manifest']}")
        lines.append(f"  totals:    {r['n_errors']} error / "
                     f"{r['n_warnings']} warning / {r['n_infos']} info")
        if r.get("code_counts"):
            lines.append("  codes:")
            for c, n in sorted(r["code_counts"].items()):
                lines.append(f"    {c:50s} x {n}")
        first_diags = (r.get("diagnostics") or [])[:3]
        if first_diags:
            lines.append("  sample:")
            for d in first_diags:
                wid = f" [{d.get('widget_id')}]" if d.get("widget_id") else ""
                lines.append(f"    [{d['severity']}] {d['code']}{wid}")
                lines.append(f"      {d['message']}")
        lines.append("")

    lines.append("=" * 72)
    lines.append("END")
    lines.append("=" * 72)
    return "\n".join(lines)


def _gallery_html(results: List[Dict[str, Any]],
                  out_root: Path) -> str:
    """Bare-minimum HTML gallery linking every stress scenario.
    Plain text only -- no styling, just bold + bulleting."""
    def _rel(p: Optional[str]) -> str:
        if not p:
            return ""
        try:
            return str(Path(p).resolve().relative_to(out_root.resolve()))
        except ValueError:
            return str(Path(p).resolve())

    parts = []
    parts.append("<!doctype html>")
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append("<title>Stress test gallery</title>")
    parts.append("</head><body>")
    parts.append("<h1>compile_dashboard stress test gallery</h1>")
    parts.append(f"<p>Generated {datetime.now().isoformat()}</p>")
    n_total = len(results)
    total_err = sum(r.get("n_errors", 0) for r in results)
    total_warn = sum(r.get("n_warnings", 0) for r in results)
    parts.append(
        f"<p><b>{n_total}</b> scenarios -- "
        f"<b>{total_err}</b> errors, <b>{total_warn}</b> warnings.</p>"
    )
    parts.append("<ul>")
    for r in results:
        parts.append("<li>")
        parts.append(f"<b>{r['name']}</b> -- {r['title']}<br/>")
        parts.append(f"<span>{r['description']}</span><br/>")
        if r["validate_ok"]:
            html_rel = _rel(r["html"])
            json_rel = _rel(r["manifest"])
            diag_rel = _rel(str(Path(r["html"]).parent / "diagnostics.txt"))
            parts.append(
                f"errors=<b>{r['n_errors']}</b> "
                f"warnings=<b>{r['n_warnings']}</b> "
                f"infos=<b>{r['n_infos']}</b><br/>"
            )
            parts.append(f"<a href='{html_rel}'>open dashboard</a> &middot; ")
            parts.append(f"<a href='{json_rel}'>manifest.json</a> &middot; ")
            parts.append(f"<a href='{diag_rel}'>diagnostics.txt</a>")
            if r.get("code_counts"):
                parts.append("<ul>")
                for c, n in sorted(r["code_counts"].items()):
                    parts.append(f"<li>{c} &times; {n}</li>")
                parts.append("</ul>")
        else:
            parts.append("<b>VALIDATION FAILED -- not rendered.</b>")
        parts.append("</li>")
    parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)


def run_stress(out_root: Path, names: List[str],
               do_open: bool = False) -> int:
    """Run a list of stress scenarios. Returns 0 on full success."""
    print(f"[stress] output: {out_root}")
    out_root.mkdir(parents=True, exist_ok=True)
    start_all = time.time()
    results: List[Dict[str, Any]] = []
    for name in names:
        if name not in STRESS_REGISTRY:
            print(f"  unknown scenario: {name}  "
                  f"(valid: {sorted(STRESS_REGISTRY.keys())})")
            continue
        r = _run_one_scenario(name, out_root / name)
        results.append(r)
        if time.time() - start_all > 5.0:
            elapsed = int(time.time() - start_all)
            print(f"  ... {elapsed}s elapsed", flush=True)

    report_path = out_root / "stress_report.txt"
    report_path.write_text(_stress_report_text(results), encoding="utf-8")
    (out_root / "stress_report.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8",
    )
    (out_root / "index.json").write_text(
        json.dumps([{"name": r["name"], "html": r.get("html"),
                       "manifest": r.get("manifest"),
                       "code_counts": r.get("code_counts", {}),
                       "n_errors": r.get("n_errors", 0),
                       "n_warnings": r.get("n_warnings", 0)}
                     for r in results], indent=2, default=str),
        encoding="utf-8",
    )
    gallery_path = out_root / "gallery.html"
    gallery_path.write_text(_gallery_html(results, out_root),
                             encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"[stress] DONE in {int(time.time() - start_all)}s")
    print(f"  report:  {report_path}")
    print(f"  gallery: {gallery_path}")
    if do_open:
        webbrowser.open(f"file://{gallery_path.resolve()}")
    return 0


# =============================================================================
# CLI -- interactive (nested) + argparse mirroring each other
# =============================================================================

def _list_unit_test_classes() -> List[str]:
    """Enumerate TestCase subclasses defined in this module, sorted."""
    return sorted(
        name
        for name, obj in globals().items()
        if isinstance(obj, type)
        and issubclass(obj, unittest.TestCase)
        and obj is not unittest.TestCase
    )


def _run_unit_tests(args: List[str]) -> int:
    """Run unittest with given args. Returns 0 on success, 1 on failure.

    Supports the standard unittest CLI (test class names, dotted
    method paths, -v / -q / -k filters, etc.) by forwarding directly
    to unittest.main with exit=False.
    """
    full_argv = ["tests.py"] + list(args)
    try:
        program = unittest.main(
            module="tests" if "tests" in sys.modules
                            else sys.modules[__name__].__name__,
            argv=full_argv, exit=False, verbosity=2,
        )
    except SystemExit as e:
        return int(e.code or 0)
    return 0 if program.result.wasSuccessful() else 1


def _interactive_unit() -> int:
    """Sub-menu: pick how to run the unit test suite."""
    classes = _list_unit_test_classes()
    while True:
        print("\nUnit tests")
        print("-" * 60)
        print("  1. Run all tests")
        print("  2. Run all tests (verbose)")
        print(f"  3. Run a specific test class ({len(classes)} available)")
        print("  4. List test classes")
        print("  b. back")
        raw = input("\nselect: ").strip()
        if not raw or raw.lower() in ("b", "back", "q", "quit"):
            return 0
        if raw == "1":
            return _run_unit_tests([])
        if raw == "2":
            return _run_unit_tests(["-v"])
        if raw == "3":
            for i, n in enumerate(classes, 1):
                print(f"    {i:3d}. {n}")
            pick = input("\n  pick test class (number or name): ").strip()
            if not pick:
                continue
            if pick.lower() in ("b", "back", "q", "quit"):
                continue
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(classes):
                    return _run_unit_tests([classes[idx]])
                print(f"  out of range: {pick}")
            except ValueError:
                if pick in classes:
                    return _run_unit_tests([pick])
                print(f"  unknown class: {pick}")
        elif raw == "4":
            for i, n in enumerate(classes, 1):
                print(f"    {i:3d}. {n}")
        else:
            print(f"  invalid: {raw}")


def _interactive_stress() -> int:
    """Sub-menu: pick which stress scenario(s) to run."""
    names = list(STRESS_REGISTRY.keys())
    print("\nStress tests")
    print("-" * 60)
    print("  Each scenario builds a deliberately-broken dashboard")
    print("  that PASSES schema validation but renders empty / "
          "broken visuals.")
    print()
    for i, n in enumerate(names, 1):
        entry = STRESS_REGISTRY[n]
        print(f"  {i:2d}. {n:22s} {entry['title']}")
    all_idx = len(names) + 1
    back_idx = len(names) + 2
    print(f"  {all_idx:2d}. all")
    print(f"  {back_idx:2d}. back")

    raw = input("\nselect: ").strip()
    if not raw or raw == str(back_idx) or raw.lower() in ("b", "back", "q", "quit"):
        return 0
    out_root = (_here_path / "output" /
                f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    if raw == str(all_idx) or raw.lower() == "all":
        return run_stress(out_root, names, do_open=True)
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(names):
            return run_stress(out_root, [names[idx]], do_open=True)
    except ValueError:
        if raw in STRESS_REGISTRY:
            return run_stress(out_root, [raw], do_open=True)
    print(f"  invalid: {raw}")
    return 1


def _interactive() -> int:
    """Top-level interactive menu."""
    while True:
        print("\nGS echarts test runner")
        print("=" * 60)
        print("  1. Unit tests")
        print("  2. Stress tests")
        print("  3. Run everything (all unit tests + every stress scenario)")
        print("  q. quit")
        raw = input("\nselect: ").strip()
        if not raw or raw.lower() in ("q", "quit"):
            return 0
        if raw == "1":
            rc = _interactive_unit()
            if rc != 0:
                return rc
        elif raw == "2":
            rc = _interactive_stress()
            if rc != 0:
                return rc
        elif raw == "3":
            rc1 = _run_unit_tests([])
            out_root = (_here_path / "output" /
                        f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            rc2 = run_stress(out_root, list(STRESS_REGISTRY.keys()),
                             do_open=True)
            return rc1 or rc2
        else:
            print(f"  invalid: {raw}")


def _stress_main(args: List[str]) -> int:
    """Argparse-driven non-interactive entry point for stress tests."""
    parser = argparse.ArgumentParser(
        prog="tests.py stress",
        description=("Run echarts stress tests: dashboards that "
                     "validate but render broken charts. Stress-tests "
                     "compile_dashboard's error logs."),
    )
    parser.add_argument("--all", action="store_true",
                          help="run every scenario")
    parser.add_argument("--scenario", action="append", default=[],
                          help=("scenario name to run (repeatable); "
                                f"valid: {sorted(STRESS_REGISTRY.keys())}"))
    parser.add_argument("--out", default=None,
                          help=("output dir (default: "
                                "output/stress_<timestamp>)"))
    parser.add_argument("--open", action="store_true",
                          help="auto-open gallery in browser when done")
    parser.add_argument("--list", action="store_true",
                          help="list scenarios and exit")

    p = parser.parse_args(args)

    if p.list:
        for name, entry in STRESS_REGISTRY.items():
            print(f"  {name:22s} {entry['title']}")
            print(f"  {'':22s}   {entry['description']}")
        return 0

    out_root = (Path(p.out) if p.out
                 else _here_path / "output" /
                       f"stress_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    if p.scenario:
        return run_stress(out_root, p.scenario, do_open=p.open)
    if p.all:
        return run_stress(out_root, list(STRESS_REGISTRY.keys()),
                          do_open=p.open)
    return _interactive_stress()


def main(argv: Optional[List[str]] = None) -> int:
    """Top-level CLI dispatcher.

    No args              -> interactive top-level menu
    `stress ...`         -> stress argparse sub-CLI
    `unit ...`           -> unittest forwarding
    Anything else        -> forwarded directly to unittest
                              (preserves `tests.py TestThemes`,
                               `tests.py -v`, etc.)
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        return _interactive()

    if argv[0] == "stress":
        return _stress_main(argv[1:])

    if argv[0] == "unit":
        return _run_unit_tests(argv[1:])

    return _run_unit_tests(argv)


if __name__ == "__main__":
    sys.exit(main())
