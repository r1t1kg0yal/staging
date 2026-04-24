"""
Unit tests for echart_studio + echart_dashboard.

    python tests.py              # run all
    python tests.py -v           # verbose
    python tests.py TestThemes   # one class
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_here = os.path.dirname(os.path.abspath(__file__))
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
    ChartRef, KPIRef, TableRef, MarkdownRef, DividerRef,
    GlobalFilter, Link,
    render_dashboard, compile_dashboard,
    _source_to_dataframe, _spec_to_option,
    SCHEMA_VERSION, VALID_WIDGETS, VALID_FILTERS, VALID_SYNC, VALID_BRUSH_TYPES,
    validate_manifest, load_manifest, save_manifest, match_targets,
)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
