#!/usr/bin/env python3
"""
inspect_dashboard -- Playwright-based runtime inspection harness for
GS/viz/echarts dashboards.

Purpose
-------
Give agents + humans a programmatic way to verify what a compiled
dashboard actually *does* in the browser:

  * tab switching renders the right charts
  * filter controls update the downstream widgets
  * brush cross-filtering reshapes linked charts
  * table row-click popups open
  * KPI sparklines are populated
  * filter placement (global bar vs per-tab) looks right

For every interaction the harness:

  * evaluates JS against the dashboard runtime to capture state
    (filter values, rendered chart counts, dataset row counts,
    active tab, etc.)
  * takes a numbered PNG screenshot (viewport + full-page)

The output is a per-dashboard directory with an index.html gallery
of every step so the user can flip through visually.

Usage
-----

    python inspect_dashboard.py                    interactive CLI
    python inspect_dashboard.py --all              rebuild demos + scan
    python inspect_dashboard.py --demo fomc_monitor
    python inspect_dashboard.py --html <path.html>
    python inspect_dashboard.py --list             list demos
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))


# ---------------------------------------------------------------------------
# JS probes evaluated inside the dashboard page
# ---------------------------------------------------------------------------

# A dashboard page always exposes `window.DASHBOARD = {manifest, charts,
# datasets}` after init; we probe that + DOM state.
JS_SNAPSHOT = """
() => {
  const D = window.DASHBOARD || {};
  const m = D.manifest || {};
  const charts = D.charts || {};
  const datasets = D.datasets || {};
  const activeTab = document.querySelector('.tab-btn.active')?.dataset?.tab
                 || null;
  const tabs = Array.from(document.querySelectorAll('.tab-btn'))
    .map(b => ({id: b.dataset.tab, label: b.textContent.trim(),
                active: b.classList.contains('active')}));
  const chartBoxes = Array.from(document.querySelectorAll('.chart-div'))
    .map(el => {
      const id = (el.id || '').replace(/^chart-/, '');
      const rect = el.getBoundingClientRect();
      return {id, visible: rect.width > 2 && rect.height > 2,
              width: Math.round(rect.width), height: Math.round(rect.height),
              inited: !!charts[id]};
    });
  const filterBar = {
    present: !!document.querySelector('.filter-bar'),
    items: Array.from(document.querySelectorAll('.filter-bar .filter-item'))
      .map(el => el.querySelector('label')?.textContent?.trim() || '?'),
  };
  const tabFilterBars = Array.from(
      document.querySelectorAll('.tab-panel .tab-filter-bar'))
    .map(el => ({
      panel: el.closest('.tab-panel')?.id?.replace(/^tab-panel-/, ''),
      items: Array.from(el.querySelectorAll('.filter-item'))
        .map(i => i.querySelector('label')?.textContent?.trim() || '?'),
    }));
  const filterState = (typeof window !== 'undefined'
                       && window.__FILTER_STATE__) || {};
  const datasetCounts = {};
  Object.keys(datasets || {}).forEach(k => {
    const d = datasets[k];
    const src = (d && d.source) ? d.source : d;
    datasetCounts[k] = Array.isArray(src) ? Math.max(0, src.length - 1) : 0;
  });
  const chartSeriesCounts = {};
  Object.keys(charts).forEach(id => {
    const inst = charts[id] && charts[id].inst;
    if (!inst) return;
    try {
      const opt = inst.getOption();
      chartSeriesCounts[id] = (opt.series || []).map(s => {
        if (Array.isArray(s.data)) return s.data.length;
        if (opt.dataset && opt.dataset[0] && Array.isArray(opt.dataset[0].source))
          return Math.max(0, opt.dataset[0].source.length - 1);
        return -1;
      });
    } catch (e) {
      chartSeriesCounts[id] = 'err:' + String(e);
    }
  });
  return {
    dashboard_id: m.id || null,
    dashboard_title: m.title || null,
    activeTab, tabs,
    chartBoxes, chartSeriesCounts,
    filterBar, tabFilterBars,
    filterState,
    datasetCounts,
    url: location.href,
  };
}
"""


# The dashboard runtime stores filterState as a module-local var. We can
# grab it by traversing the closure only via `window.DASHBOARD.filterState`
# if exposed, or by reading values directly from the DOM as a fallback.
JS_READ_FILTER_STATE = """
() => {
  const s = {};
  // Global bar + per-tab bars
  document.querySelectorAll('[id^=filter-]').forEach(el => {
    if (el.id.endsWith('-val')) return;
    const id = el.id.replace(/^filter-/, '');
    if (el.tagName === 'SELECT'){
      if (el.multiple) s[id] = Array.from(el.selectedOptions).map(o => o.value);
      else s[id] = el.value;
    } else if (el.type === 'checkbox'){
      s[id] = el.checked;
    } else {
      s[id] = el.value;
    }
  });
  document.querySelectorAll('input[type=radio]:checked').forEach(el => {
    const nm = el.name || '';
    if (nm.startsWith('filter-')) s[nm.replace(/^filter-/, '')] = el.value;
  });
  return s;
}
"""


# ---------------------------------------------------------------------------
# Core inspector
# ---------------------------------------------------------------------------


class DashboardInspector:
    """Wraps a Playwright browser + page and captures a structured set of
    snapshots/screenshots for a single dashboard HTML.

    Use as a context manager:

        with DashboardInspector(html_path, out_dir) as insp:
            insp.capture_baseline()
            insp.capture_all_tabs()
            insp.capture_filter_sweeps()
    """

    def __init__(self, html_path: Path, out_dir: Path,
                  viewport: Tuple[int, int] = (1500, 960),
                  wait_ms: int = 1500):
        self.html_path = html_path.resolve()
        self.out_dir = out_dir.resolve()
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.viewport = viewport
        self.wait_ms = wait_ms
        self._p = None
        self._browser = None
        self._context = None
        self.page = None
        self.steps: List[Dict[str, Any]] = []
        self._step_idx = 0

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._p = sync_playwright().start()
        self._browser = self._p.chromium.launch()
        self._context = self._browser.new_context(
            viewport={"width": self.viewport[0], "height": self.viewport[1]},
            device_scale_factor=1,
        )
        self.page = self._context.new_page()
        self.page.goto(f"file://{self.html_path}",
                         wait_until="networkidle")
        # Dashboard pages expose `.app-main`; composite / single-chart
        # pages emit a raw #chart div. Accept either so the harness
        # works on every emitted HTML.
        try:
            self.page.wait_for_selector(
                ".app-main, #chart", timeout=10_000)
        except Exception:
            pass
        self.page.wait_for_timeout(self.wait_ms)
        return self

    def __exit__(self, *exc):
        try:
            self._context.close()
            self._browser.close()
        finally:
            self._p.stop()

    def _step_name(self, label: str) -> str:
        self._step_idx += 1
        safe = "".join(c if c.isalnum() or c in "-_" else "_"
                         for c in label)[:90]
        return f"{self._step_idx:03d}_{safe}"

    def snapshot(self, label: str,
                  full_page: bool = True) -> Dict[str, Any]:
        """Take a screenshot + grab runtime JS state."""
        name = self._step_name(label)
        shot_vp = self.out_dir / f"{name}.png"
        shot_full = self.out_dir / f"{name}_full.png"
        self.page.wait_for_timeout(self.wait_ms)
        self.page.screenshot(path=str(shot_vp), full_page=False)
        if full_page:
            try:
                self.page.screenshot(path=str(shot_full), full_page=True)
            except Exception:
                shot_full = None
        state = self.page.evaluate(JS_SNAPSHOT)
        filters = self.page.evaluate(JS_READ_FILTER_STATE)
        state["dom_filter_state"] = filters
        step = {
            "idx": self._step_idx,
            "label": label,
            "screenshot": str(shot_vp.relative_to(self.out_dir)),
            "screenshot_full": (str(shot_full.relative_to(self.out_dir))
                                   if shot_full else None),
            "state": state,
        }
        self.steps.append(step)
        return step

    # --- high-level action helpers -----------------------------------------

    def click_tab(self, tab_id: str) -> None:
        self.page.click(f".tab-btn[data-tab='{tab_id}']")
        self.page.wait_for_timeout(self.wait_ms)

    def set_filter_value(self, filter_id: str, value: Any) -> None:
        """Set a filter control to a value and trigger its change event."""
        sel = f"#filter-{filter_id}"
        el = self.page.query_selector(sel)
        if el is None:
            radios = self.page.query_selector_all(
                f"input[type=radio][name='filter-{filter_id}']")
            for r in radios:
                if r.get_attribute("value") == str(value):
                    r.check()
                    self.page.wait_for_timeout(self.wait_ms)
                    return
            raise RuntimeError(
                f"no filter control found for id='{filter_id}'")
        tag = el.evaluate("e => e.tagName")
        typ = el.evaluate("e => e.type || ''")
        if tag == "SELECT":
            if el.evaluate("e => e.multiple"):
                self.page.select_option(sel, value=value)
            else:
                self.page.select_option(sel, value=str(value))
        elif typ == "checkbox":
            if bool(value) != el.is_checked():
                el.click()
        elif typ == "range":
            self.page.evaluate(
                "([sel, v]) => {"
                " const el = document.querySelector(sel);"
                " el.value = v;"
                " el.dispatchEvent(new Event('input', {bubbles:true}));"
                " el.dispatchEvent(new Event('change', {bubbles:true}));"
                "}", [sel, value])
        else:
            self.page.fill(sel, str(value))
            self.page.press(sel, "Enter")
        self.page.wait_for_timeout(self.wait_ms)

    def reset_filters(self) -> None:
        btn = self.page.query_selector("#filter-reset")
        if btn is not None:
            btn.click()
            self.page.wait_for_timeout(self.wait_ms)

    # --- canned sweeps -----------------------------------------------------

    def capture_baseline(self) -> None:
        """Step 1: first paint, default tab, default filter values."""
        self.snapshot("baseline")

    def capture_all_tabs(self) -> None:
        state = self.page.evaluate(JS_SNAPSHOT)
        tab_ids = [t["id"] for t in state.get("tabs", []) if t.get("id")]
        for tid in tab_ids:
            self.click_tab(tid)
            self.snapshot(f"tab_{tid}")

    def capture_filter_sweeps(
            self, manifest: Optional[Dict[str, Any]] = None) -> None:
        """For each filter in the manifest, flip it to one non-default
        value and screenshot. Filter controls rendered into tab panels
        live inside the DOM only when that tab is active, so we first
        activate the scope tab before manipulating the input.
        """
        if not manifest:
            try:
                manifest = self.page.evaluate(
                    "() => window.DASHBOARD ? "
                    "JSON.parse(JSON.stringify(window.DASHBOARD.manifest))"
                    " : {}")
            except Exception:
                manifest = {}
        filters = manifest.get("filters", []) or []
        for f in filters:
            fid = f.get("id")
            ftype = f.get("type")
            default = f.get("default", "")
            scope = str(f.get("scope") or "global")
            test_val = self._pick_non_default(f)
            if test_val is None:
                continue
            if scope.startswith("tab:"):
                try:
                    self.click_tab(scope[4:])
                except Exception:
                    pass
            try:
                self.set_filter_value(fid, test_val)
                self.snapshot(f"filter_{fid}_{ftype}")
            except Exception as e:
                self.steps.append({
                    "idx": self._step_idx,
                    "label": f"filter_{fid}_{ftype}_error",
                    "error": str(e)})
            try:
                self.set_filter_value(fid, default)
            except Exception:
                pass

    def _pick_non_default(self, f: Dict[str, Any]) -> Any:
        ftype = f.get("type")
        default = f.get("default")
        options = f.get("options") or []
        if ftype == "dateRange":
            for o in ["3M", "6M", "1Y", "All", "5Y"]:
                if o != str(default):
                    return o
            return "3M"
        if ftype in ("select", "radio"):
            for o in options:
                if str(o) != str(default) and o != f.get("all_value"):
                    return o
            return options[0] if options else None
        if ftype == "multiSelect":
            pick = next((o for o in options
                         if not isinstance(default, list) or o not in default),
                        None)
            return [pick] if pick is not None else None
        if ftype == "toggle":
            return not bool(default)
        if ftype == "slider":
            mx = f.get("max", 10)
            mn = f.get("min", 0)
            return float(mn + (mx - mn) * 0.5)
        if ftype == "number":
            mx = f.get("max")
            mn = f.get("min")
            if mx is None and mn is None:
                return 1
            return mx if mx is not None else mn
        if ftype == "numberRange":
            return [f.get("min", 0), f.get("max", 100)]
        if ftype == "text":
            return "a"
        return None

    def capture_row_click(self, table_id: str) -> None:
        """If the table has row_click configured, open the popup."""
        rows = self.page.query_selector_all(
            f".table-tile[data-tile-id='{table_id}'] tbody tr")
        if not rows:
            return
        rows[0].click()
        self.page.wait_for_timeout(self.wait_ms)
        self.snapshot(f"row_click_{table_id}")

    # --- gallery emission --------------------------------------------------

    def write_gallery(self, title: str) -> Path:
        rep = {"title": title, "html": str(self.html_path),
                "steps": self.steps,
                "generated_at": datetime.now().isoformat()}
        (self.out_dir / "report.json").write_text(
            json.dumps(rep, indent=2, default=str), encoding="utf-8")

        cards = []
        for s in self.steps:
            shot = s.get("screenshot")
            label = s.get("label")
            state = s.get("state") or {}
            err = s.get("error")
            tab = state.get("activeTab", "")
            filt = state.get("dom_filter_state", {})
            chart_counts = state.get("chartSeriesCounts", {})
            cc_html = "".join(
                f'<tr><td>{k}</td>'
                f'<td>{",".join(str(x) for x in (v if isinstance(v, list) else [v]))}</td></tr>'
                for k, v in chart_counts.items())
            fs_html = "".join(
                f'<tr><td>{k}</td><td>{v}</td></tr>'
                for k, v in filt.items())
            cards.append(
                '<section class="step">'
                f'<h2>{s["idx"]:03d} &middot; {label}</h2>'
                f'<div class="meta">tab: <b>{tab}</b></div>'
                + (f'<div class="err">ERROR: {err}</div>' if err else '')
                + (f'<img src="{shot}" alt="{label}"/>' if shot else '')
                + '<details><summary>chart series counts</summary>'
                f'<table>{cc_html}</table></details>'
                '<details><summary>DOM filter state</summary>'
                f'<table>{fs_html}</table></details>'
                '</section>')
        idx = self.out_dir / "index.html"
        idx.write_text(
            '<!doctype html><meta charset="utf-8"/>'
            f'<title>inspect: {title}</title>'
            '<style>body{font-family:-apple-system,sans-serif;margin:20px;'
            'background:#fafbfd;color:#2d3748}'
            'section.step{background:white;border:1px solid #e2e8f0;'
            'border-radius:6px;padding:14px 18px;margin:14px 0}'
            'section.step h2{margin:0 0 6px;font-size:15px;color:#1a365d}'
            'section.step .meta{color:#718096;font-size:12px;'
            'margin-bottom:10px}'
            'section.step img{max-width:100%;border:1px solid #e2e8f0;'
            'border-radius:4px}'
            'section.step table{font-size:12px;border-collapse:collapse}'
            'section.step td{padding:2px 10px 2px 0;'
            'border-bottom:1px dotted #edf2f7}'
            '.err{color:#c53030;font-weight:600;margin-bottom:10px}'
            'details{margin-top:8px;color:#4a5568}'
            'h1{color:#1a365d}</style>'
            f'<h1>inspect: {title}</h1>'
            f'<p>{self.html_path}</p>'
            + "".join(cards),
            encoding="utf-8")
        return idx


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _default_sweep(html: Path, out: Path, title: str,
                    do_open: bool = False,
                    visual_only: bool = False) -> Dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()
    last = [start]
    print(f"[inspect] {title}")
    print(f"  html   : {html}")
    print(f"  output : {out}")
    with DashboardInspector(html, out) as insp:
        insp.capture_baseline()
        _heartbeat("baseline", start, last)
        insp.capture_all_tabs()
        _heartbeat("tabs", start, last)
        if not visual_only:
            insp.capture_filter_sweeps()
            _heartbeat("filters", start, last)
        idx = insp.write_gallery(title)
    print(f"  steps  : {insp._step_idx}")
    print(f"  index  : {idx}")
    if do_open:
        webbrowser.open(f"file://{idx.resolve()}")
    return {"title": title, "html": str(html), "out": str(out),
             "index": str(idx), "steps": insp._step_idx,
             "elapsed_s": round(time.time() - start, 1)}


def _heartbeat(label: str, start: float, last: List[float]) -> None:
    now = time.time()
    if now - last[0] >= 5.0:
        print(f"  ... {label} ({int(now - start)}s elapsed)")
        last[0] = now


def _resolve_demo_html(demo: str,
                        demos_root: Optional[Path] = None) -> Path:
    """Find or (re-)build a demo dashboard and return its HTML path.

    Works for both dashboards (``dashboard.html``) and composite
    scenes (``echarts/composite.html``). Most recent output wins.
    """
    root = demos_root or (_here / "output")
    root.mkdir(parents=True, exist_ok=True)
    runs = sorted([p for p in root.iterdir() if p.is_dir()], reverse=True)
    candidates = [
        "dashboard.html",
        "echarts/composite.html",
        "composite.html",
    ]
    for r in runs:
        for rel in candidates:
            cand = r / demo / rel
            if cand.is_file():
                return cand
    from demos import DEMO_REGISTRY, run
    if demo not in DEMO_REGISTRY:
        raise ValueError(f"unknown demo '{demo}'. "
                          f"valid: {sorted(DEMO_REGISTRY.keys())}")
    out = root / datetime.now().strftime("%Y%m%d_%H%M%S")
    run(out, [demo], do_open=False)
    for rel in candidates:
        cand = out / demo / rel
        if cand.is_file():
            return cand
    raise RuntimeError(
        f"failed to build demo '{demo}'; expected html at one of "
        f"{[str(out / demo / r) for r in candidates]}"
    )


def _inspect_roots(names: List[str], out_root: Path,
                    do_open: bool = False,
                    visual_only: bool = False) -> int:
    out_root.mkdir(parents=True, exist_ok=True)
    results: List[Dict[str, Any]] = []
    start = time.time()
    last = [start]
    for n in names:
        print(f"\n[inspect] resolving demo: {n}")
        try:
            html = _resolve_demo_html(n)
        except Exception as e:
            print(f"  FAIL: {e}")
            continue
        res = _default_sweep(html, out_root / n, title=n,
                                do_open=False,
                                visual_only=visual_only)
        results.append({"name": n, **res})
        _heartbeat(f"after {n}", start, last)

    index = out_root / "index.html"
    cards = "".join(
        f'<div class="card"><h3><a href="{r["name"]}/index.html">'
        f'{r["title"]}</a></h3>'
        f'<p>{r["steps"]} steps &middot; {r["elapsed_s"]}s</p></div>'
        for r in results)
    index.write_text(
        '<!doctype html><meta charset="utf-8"/>'
        '<title>inspect gallery</title>'
        '<style>body{font-family:-apple-system,sans-serif;background:#fafbfd;'
        'margin:30px;color:#2d3748}.card{background:white;'
        'border:1px solid #e2e8f0;border-radius:6px;padding:14px 18px;'
        'margin:10px 0}a{color:#1a365d;font-weight:600}</style>'
        f'<h1>inspect gallery</h1>'
        f'<p>{len(results)} dashboards inspected</p>{cards}',
        encoding="utf-8")
    print(f"\n[inspect] index: {index}")
    if do_open:
        webbrowser.open(f"file://{index.resolve()}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _interactive() -> int:
    from demos import DEMO_REGISTRY
    names = list(DEMO_REGISTRY.keys())
    print("\ninspect_dashboard -- interactive")
    print("=" * 60)
    print("  a. scan all demos")
    for i, n in enumerate(names, 1):
        print(f"  {i:2d}. {n}")
    print(f"  h. specify an HTML path")
    print(f"  q. quit")
    raw = input("\nselect: ").strip().lower()
    if raw in ("q", "quit", ""):
        return 0
    out_root = _here / "inspect" / datetime.now().strftime("%Y%m%d_%H%M%S")
    if raw == "a":
        return _inspect_roots(names, out_root, do_open=True)
    if raw == "h":
        path = input("html path: ").strip()
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            print(f"  not found: {p}")
            return 1
        _default_sweep(p, out_root / p.stem, title=p.stem,
                        do_open=True)
        return 0
    try:
        i = int(raw) - 1
        if 0 <= i < len(names):
            return _inspect_roots([names[i]], out_root, do_open=True)
    except ValueError:
        if raw in DEMO_REGISTRY:
            return _inspect_roots([raw], out_root, do_open=True)
    print(f"  invalid: {raw}")
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    from demos import DEMO_REGISTRY

    parser = argparse.ArgumentParser(
        description="Playwright-based dashboard inspection harness."
    )
    parser.add_argument("--all", action="store_true",
                          help="inspect every demo")
    parser.add_argument("--demo", action="append", default=[],
                          help="demo name (repeatable)")
    parser.add_argument("--html", default=None,
                          help="explicit dashboard HTML path")
    parser.add_argument("--out", default=None,
                          help="output directory root")
    parser.add_argument("--open", action="store_true",
                          help="auto-open the gallery")
    parser.add_argument("--list", action="store_true",
                          help="list demos and exit")
    parser.add_argument("--visual-only", action="store_true",
                          help="skip filter sweeps; baseline + tabs only")
    args = parser.parse_args(argv)

    if args.list:
        for n, entry in DEMO_REGISTRY.items():
            print(f"{n:25s}  {entry['title']}")
        return 0

    out_root = (Path(args.out) if args.out
                 else _here / "inspect" /
                      datetime.now().strftime("%Y%m%d_%H%M%S"))

    if args.html:
        p = Path(args.html).expanduser().resolve()
        if not p.is_file():
            print(f"html not found: {p}")
            return 1
        _default_sweep(p, out_root / p.stem, title=p.stem,
                        do_open=args.open,
                        visual_only=args.visual_only)
        return 0

    if args.demo:
        picked = [d for d in args.demo if d in DEMO_REGISTRY]
        unknown = [d for d in args.demo if d not in DEMO_REGISTRY]
        for u in unknown:
            print(f"  unknown demo: {u}")
        if not picked:
            return 1
        return _inspect_roots(picked, out_root, do_open=args.open,
                                 visual_only=args.visual_only)

    if args.all:
        return _inspect_roots(list(DEMO_REGISTRY.keys()), out_root,
                                do_open=args.open,
                                visual_only=args.visual_only)

    return _interactive()


if __name__ == "__main__":
    sys.exit(main())
