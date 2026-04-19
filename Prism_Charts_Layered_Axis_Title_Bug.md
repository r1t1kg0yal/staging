# Layered Chart: Concatenated Y-Axis Title Bug ("value, y")

## Symptom

A layered chart (base chart + annotation layers) renders with a y-axis title
that looks like two field names joined by a comma, e.g.:

```
  ^
  |
  |  value, y
  |
  +--------------------->
```

Instead of the expected single, readable title (e.g. `%`, `bps`, `Yield`).

## Root Cause (Vega-Lite Layer Axis Resolution)

```
┌─ HOW VEGA-LITE RESOLVES A SHARED Y-AXIS TITLE IN A LAYERED SPEC ────────┐
│                                                                          │
│   For each layer i, compute the "effective title" of encoding.y:        │
│       if layer[i].encoding.y.title is set:                              │
│           title_i = layer[i].encoding.y.title                           │
│       elif layer[i].encoding.y.field is set:                            │
│           title_i = layer[i].encoding.y.field        <-- fallback       │
│       else:                                                              │
│           title_i = (no title, layer contributes nothing)               │
│                                                                          │
│   Collect the set of distinct title_i values across layers.             │
│                                                                          │
│   If the set has ONE element:                                            │
│       shared axis title = that single value                             │
│   If the set has MULTIPLE elements:                                      │
│       shared axis title = ", ".join(sorted-by-layer-order)              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

So you get "value, y" when:

1. The base chart layer has `y.field = "value"` and **no explicit y.title**
2. An annotation layer has `y.field = "y"` (or any other name) and **no
   explicit y.title**
3. Vega-Lite falls back to the field names `"value"` and `"y"`, sees they
   differ, and concatenates them

## Minimal Reproducer

```python
spec = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "width": 400, "height": 200,
    "data": {"values": [
        {"date": "2022-01-01", "value": 2.0},
        {"date": "2022-06-01", "value": 2.5},
        {"date": "2023-01-01", "value": 2.6},
    ]},
    "layer": [
        # BASE LAYER: y.field = "value", no y.title
        {
            "mark": "line",
            "encoding": {
                "x": {"field": "date", "type": "temporal"},
                "y": {"field": "value", "type": "quantitative"},
            },
        },
        # ANNOTATION LAYER: y.field = "y", no y.title
        {
            "data": {"values": [{"date": "2022-03-16", "y": 3.5, "event": "Fed hike"}]},
            "mark": "text",
            "encoding": {
                "x": {"field": "date", "type": "temporal"},
                "y": {"field": "y", "type": "quantitative"},
                "text": {"field": "event", "type": "nominal"},
            },
        },
    ],
}
# Compile result: y-axis title renders as "value, y"
```

```
┌─ OUTCOMES FOR EACH COMBINATION ────────────────────────────────────────┐
│                                                                         │
│  BASE y.field  BASE y.title   ANNOT y.field  ANNOT y.title   RENDERED  │
│  ─────────────────────────────────────────────────────────────────     │
│  "value"       <none>         "y"            <none>          value, y  │
│  "value"       "%"            "y"            <none>          %         │
│  "value"       "%"            "y"            "%"             %         │
│  "value"       <none>         "value"        <none>          value     │
│  "value"       "%"            "value"        <none>          %         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Why PRISM Hits This

`chart_functions.py` builds base charts via `_build_multi_line()`,
`_build_scatter()`, etc. Each builder sets the base chart's y encoding
from the mapping. The y-axis title comes from `mapping["y_title"]` (if
set) or defaults to the y field name.

The annotation system (`Annotation` base class with `VLine`, `HLine`,
`Band`, `Arrow`, `PointLabel`, `TrendLine` subclasses) produces layers
via `to_layer() -> alt.Chart`. These layers carry their own y encoding:

- `VLine` -- no y encoding (only x=rule), safe.
- `HLine` -- y encoding with a literal value (via `alt.datum` or
  a synthesized field like `y_value` or `y`). If the synthesized field
  name differs from the base chart's y field, and no explicit title is
  set, the axis merges to "value, y_value" or similar.
- `Band` -- y1/y2 encoding on a synthesized field; same risk as HLine.
- `PointLabel` -- y encoding on a synthesized field (e.g. `y`); same
  risk.
- `TrendLine` -- y encoding typically on the same field as the base
  (it's a regression of the base data), usually safe.
- `Arrow` -- y encoding on synthesized `y0`/`y1`; same risk.

The bug surfaces when:
- A trader passes `annotations=[PointLabel(...)]` or `HLine(...)` or
  similar
- The annotation's `to_layer()` generates an encoding with a y field name
  that differs from the base chart's y field
- Neither layer sets an explicit `title=`

## Fix Patterns (Ranked from Cleanest to Most Specific)

### Fix A: Always set `axis=alt.Axis(title=None)` on annotation layers [RECOMMENDED]

When an annotation layer is purely visual (a rule, a label, a band) and
shouldn't contribute to the shared axis title at all, tell Vega-Lite so
explicitly:

```python
def to_layer(self, base_y_field, base_y_title):
    return alt.Chart(df).mark_text(...).encode(
        x=alt.X("date:T"),
        y=alt.Y("y_pos:Q", axis=alt.Axis(title=None)),   # <-- suppress
        text="label:N",
    )
```

In raw Vega-Lite JSON:

```json
"y": {"field": "y", "type": "quantitative", "axis": {"title": null}}
```

This makes the annotation's y encoding render without contributing to
the shared axis title. The base chart's y title wins. Works whether or
not the base has an explicit title.

### Fix B: Reuse the base chart's y field name

If the annotation value is in the same units as the base chart (a
horizontal reference line at y=100bps on a yield chart, for example),
store it under the SAME field name as the base chart's y:

```python
# Base chart has y.field = "value"
# So the HLine label also stores its y under "value":
hline_df = pd.DataFrame([{"date": "...", "value": 100.0, "label": "100bps"}])
```

One field name across all layers -> Vega-Lite merges to that one name.
If the base also has an explicit title, that title wins.

### Fix C: Force the same title on every layer

Producer-side: when the builder appends annotation layers, also stamp
the base chart's y title on every one:

```python
base_y_title = mapping.get("y_title") or mapping["y"]
for annotation in annotations:
    layer = annotation.to_layer()
    # Normalize: force the layer's y.title to match the base
    _walk_encoding(layer, "y", lambda enc: enc.setdefault("title", base_y_title))
    layered.append(layer)
```

Works regardless of what field name the annotation uses.

### Fix D: `resolve.axis.y = "independent"`

Last resort. Gives each layer its own axis. Usually breaks the visual
(you get two y-axes, one per unique field name). Only useful when the
annotation genuinely represents a different measure on a different
scale -- which is rare for text/line annotations.

## Concrete PRISM Action Items

```
┌─ FILES TO AUDIT ────────────────────────────────────────────────────────┐
│                                                                          │
│  chart_functions.py                                                      │
│    Annotation classes -- ensure each to_layer() implementation sets     │
│    axis=alt.Axis(title=None) on non-primary encodings (Fix A).          │
│                                                                          │
│    Specifically:                                                         │
│      HLine.to_layer()         -> y axis must be title=None              │
│      PointLabel.to_layer()    -> y axis must be title=None              │
│      Band.to_layer()          -> y, y2 axis must be title=None          │
│      Arrow.to_layer()         -> y, y2 axis must be title=None          │
│                                                                          │
│    VLine.to_layer()           -> already safe (no y encoding)           │
│    TrendLine.to_layer()       -> usually safe if it reuses base y field │
│                                                                          │
│  chart_functions.py -> render_annotations()                              │
│    As belt-and-suspenders, after composing layers, run a walk that      │
│    normalizes every non-primary layer's y.axis.title to None. This      │
│    prevents regressions when new annotation types are added.            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Proposed normalization helper (drop into chart_functions.py)

```python
def _suppress_annotation_axis_titles(spec_dict, primary_layer_index=0):
    """After layering, set axis.title = None on every non-primary layer's
    y encoding. Prevents Vega-Lite from concatenating layer field names
    when titles are missing.

    Call this right before handing the spec to the renderer.
    """
    if not isinstance(spec_dict, dict):
        return
    layers = spec_dict.get("layer")
    if not isinstance(layers, list):
        return
    for i, layer in enumerate(layers):
        if i == primary_layer_index:
            continue  # keep the base layer's title
        enc = layer.get("encoding")
        if not isinstance(enc, dict):
            continue
        for channel in ("y", "y2"):
            ch = enc.get(channel)
            if isinstance(ch, dict):
                ax = ch.get("axis")
                if ax is None:
                    ch["axis"] = {"title": None}
                elif isinstance(ax, dict):
                    ax.setdefault("title", None)
```

### Test pattern (pytest)

```python
def test_hline_annotation_does_not_merge_y_axis_title():
    df = pd.DataFrame([
        {"date": "2022-01-01", "value": 2.0},
        {"date": "2023-01-01", "value": 2.6},
    ])
    result = make_chart(
        df=df,
        chart_type="multi_line",
        mapping={"x": "date", "y": "value", "y_title": "%"},
        title="test",
        annotations=[HLine(y=2.5, label="midpoint")],
        session_path=TEMP_SESSION,
    )
    # vl-convert-python compiles the spec; the resulting SVG's y-axis
    # title text must be exactly '%' -- no merging, no 'value, y' etc.
    svg = vl_convert.vegalite_to_svg(vl_spec=result.vega_lite_spec)
    y_titles = re.findall(r'role-axis-title.*?>([^<]+)<', svg, re.S)
    assert "%" in y_titles, f"expected '%' in y titles, got {y_titles}"
    for t in y_titles:
        assert "," not in t, f"axis title '{t}' looks concatenated (merged from layers)"
```

Add similar tests for every annotation class to prevent regressions.

## Related chart_studio Bug (fixed upstream)

The interactive `chart_studio.py` companion previously had a bug where
its `setYAxisTitle("")` / `setXAxisTitle("")` / `setLegendTitle("")`
apply functions would **delete** titles from every encoding in the spec
on init (because the default `yAxisTitle` knob value is empty string).

This hid any producer-set titles and surfaced the layer-concatenation
bug described above. The fix: treat empty-string knob values as a
no-op, not a destructive clear. Already applied in
`GS/viz/chart_studio.py`.

```javascript
// before: destroyed producer titles
setYAxisTitle: (spec, value) => {
  walkEncoding(spec, "y", enc => {
    if (value) enc.title = value; else delete enc.title;  // <-- destructive
  });
},
// after: no-op on empty
setYAxisTitle: (spec, value) => {
  if (!value) return;
  walkEncoding(spec, "y", enc => { enc.title = value; });
},
```

If you see "value, y" type titles in a PRISM-rendered static PNG
(from `vl-convert-python`, not the chart_studio editor), the issue is
entirely PRISM-side and the fixes above are what you need. If you see
it ONLY in the interactive editor, pull the latest chart_studio.py.

## TL;DR

```
┌─ ONE-LINE FIXES ────────────────────────────────────────────────────────┐
│                                                                          │
│  BEST:    Put  axis=alt.Axis(title=None)  on every annotation           │
│           layer's y encoding (and y2, when present).                    │
│                                                                          │
│  BACKUP:  Add _suppress_annotation_axis_titles() as a post-compose      │
│           pass in render_annotations() to normalize the spec before     │
│           export.                                                        │
│                                                                          │
│  TEST:    Add a regression check that compiles each annotation type     │
│           via vl_convert.vegalite_to_svg() and asserts the y-axis      │
│           title has no comma in it.                                     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```
