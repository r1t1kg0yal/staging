# SOMA Holdings - NY Fed API Reference

A focused guide to pulling System Open Market Account (SOMA) holdings from
`GS/data/apis/nyfed/nyfed.py`. Complements `SKILL.md` which covers the full NY
Fed API surface. This doc goes deep on SOMA specifically: endpoint map, schema
quirks, recipes, and gotchas verified against live data (as of 2026-04-15).


## What SOMA Is

The System Open Market Account is the Fed's portfolio of securities. It is the
asset side of the Fed balance sheet that monetary policy is conducted through.
At latest release the composition looks like:

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │                   SOMA Portfolio (2026-04-15)                       │
 │                                                                     │
 │                        TOTAL: $6,305.8 B                            │
 ├──────────────────────┬────────────────────┬─────────────────────────┤
 │  Treasury (Nominal)  │      Agency        │        Other            │
 │  ───────────────     │  ───────────────   │  ────────────────       │
 │  Notes+Bonds $3,602B │  MBS      $1,989B  │  TIPS        $276B      │
 │  Bills         $413B │  CMBS        $8B   │  FRN          $16B      │
 │                      │  Agency Debt $2B   │  TIPS ICP    $100B      │
 │                      │                    │                         │
 │  Count: 380 CUSIPs   │  Count: 8,453      │  Count: 56 CUSIPs       │
 │                      │  CUSIPs            │  (TIPS 48, FRN 8)       │
 └──────────────────────┴────────────────────┴─────────────────────────┘
                                │
                                ▼
                428 Treasury + 8,452 Agency = ~8,880 CUSIPs
                    refreshed weekly (Wed snapshot,
                    released Thursday ~4:15pm ET)
```

Two facts drive the entire API design:
1. **Weekly cadence.** Snapshots are taken Wednesday, published Thursday. No
   intraday data. Release log gives the publication dates.
2. **Two distinct asset classes with distinct schemas.** Treasury and Agency
   Debt share a field set. Agency MBS uses a completely different field set
   (see Schema Reference).


## Decision Matrix: Which Function Do I Want?

```
 ┌────────────────────────────────┬──────────────────────┬────────────────┐
 │  Goal                          │  Function            │  Axis          │
 ├────────────────────────────────┼──────────────────────┼────────────────┤
 │  Headline aggregate ($ by      │  cmd_soma            │  cross-section │
 │  category), current            │                      │                │
 │                                │                      │                │
 │  Aggregate $ time series       │  cmd_soma_history    │  time series   │
 │  (weekly, up to 22+ years)     │                      │                │
 │                                │                      │                │
 │  Every Treasury CUSIP on       │  cmd_soma_holdings   │  cross-section │
 │  one date (428 rows)           │                      │                │
 │                                │                      │                │
 │  Every Agency/MBS CUSIP on     │  cmd_soma_agency     │  cross-section │
 │  one date (8,452 rows)         │                      │                │
 │                                │                      │                │
 │  One CUSIP, every weekly       │  cmd_soma_cusip      │  time series   │
 │  snapshot (up to 896 obs)      │                      │                │
 │                                │                      │                │
 │  Weighted avg maturity         │  cmd_soma_wam        │  snapshot      │
 │  by security type              │                      │                │
 │                                │                      │                │
 │  Monthly aggregated Tsy        │  cmd_soma_monthly    │  time series   │
 │  holdings (coarser grain)      │                      │                │
 └────────────────────────────────┴──────────────────────┴────────────────┘
```

All commands accept `as_json=True` to return list[dict] and `export_fmt="csv"`
or `"json"` to write a file.


## Endpoint Map

```
 BASE_URL = https://markets.newyorkfed.org

 ┌─ SOMA Summary (total + category aggregates, 1,189 weeks of history) ──┐
 │                                                                       │
 │   /api/soma/summary.json              → cmd_soma, cmd_soma_history    │
 │   /api/soma/asofdates/latest.json     → latest release date helper    │
 │                                                                       │
 └───────────────────────────────────────────────────────────────────────┘

 ┌─ SOMA Treasury CUSIP-Level ──────────────────────────────────────────┐
 │                                                                      │
 │   /api/soma/tsy/get/asof/{date}.json                                 │
 │       → full snapshot, all Tsy types (~428 CUSIPs)                   │
 │                                                                      │
 │   /api/soma/tsy/get/{holdingtype}/asof/{date}.json                   │
 │       holdingtype ∈ {bills, notesbonds, tips, frn}                   │
 │       → type-filtered snapshot                                       │
 │                                                                      │
 │   /api/soma/tsy/get/cusip/{cusip}.json                               │
 │       → full weekly history of one CUSIP (since issuance acquired)   │
 │                                                                      │
 │   /api/soma/tsy/wam/{holdingtype}/asof/{date}.json                   │
 │       → weighted avg maturity                                        │
 │                                                                      │
 │   /api/soma/tsy/get/monthly.json                                     │
 │       → monthly snapshots (coarser time grid than weekly)            │
 │                                                                      │
 │   /api/soma/tsy/get/release_log.json                                 │
 │       → list of {releaseDate, asOfDate} pairs                        │
 │                                                                      │
 └──────────────────────────────────────────────────────────────────────┘

 ┌─ SOMA Agency CUSIP-Level ────────────────────────────────────────────┐
 │                                                                      │
 │   /api/soma/agency/get/asof/{date}.json                              │
 │       → full snapshot, all Agency types (~8,452 CUSIPs)              │
 │                                                                      │
 │   /api/soma/agency/get/{holdingtype}/asof/{date}.json                │
 │       holdingtype ∈ {mbs, cmbs, agency%20debts}                      │
 │       → type-filtered snapshot                                       │
 │                                                                      │
 │   /api/soma/agency/get/cusip/{cusip}.json                            │
 │       → full weekly history of one CUSIP                             │
 │                                                                      │
 │   /api/soma/agency/wam/agency%20debts/asof/{date}.json               │
 │       → WAM (Agency Debt only; MBS uses WAL elsewhere)               │
 │                                                                      │
 │   /api/soma/agency/get/release_log.json                              │
 │       → list of {releaseDate, asOfDate} pairs                        │
 │                                                                      │
 └──────────────────────────────────────────────────────────────────────┘
```

All paths are `GET`, return JSON, no auth required. The wrapper module handles
rate-limit backoff (429 → sleep 5s, 10s, 15s) and 30s request timeout.


## Function Reference

### Summary Aggregates

```python
from nyfed import cmd_soma, cmd_soma_history

# Current snapshot (4 most recent weekly obs for WoW change calc)
cmd_soma(as_json=True)

# Arbitrary window (full history available back to 2003)
cmd_soma_history(weeks=52, as_json=True)    # 1 year
cmd_soma_history(weeks=260, as_json=True)   # 5 years
cmd_soma_history(weeks=1000, as_json=True)  # nearly all of QE era
```

Returns records with fields `{asOfDate, total, notesbonds, bills, tips, frn,
mbs, cmbs, agencies, tipsInflationCompensation}`. All dollar values are
strings (API quirk - parse as float).


### CUSIP-Level Snapshots

Treasury side (428 rows at latest date):

```python
from nyfed import cmd_soma_holdings

# Full snapshot
tsy = cmd_soma_holdings(as_json=True)

# Server-side filter
bills    = cmd_soma_holdings(holding_type="bills",      as_json=True)  # 49
nb       = cmd_soma_holdings(holding_type="notesbonds", as_json=True)  # 323
tips     = cmd_soma_holdings(holding_type="tips",       as_json=True)  # 48
frn      = cmd_soma_holdings(holding_type="frn",        as_json=True)  # 8

# Historical snapshot (rewind to any weekly release date)
snap_dec = cmd_soma_holdings(date="2025-12-31", as_json=True)

# If date=None, auto-resolves via _fetch_soma_latest_date()
```

Agency side (8,452 rows at latest date):

```python
from nyfed import cmd_soma_agency

agency   = cmd_soma_agency(as_json=True)
mbs      = cmd_soma_agency(holding_type="mbs",          as_json=True)  # 8,446
cmbs     = cmd_soma_agency(holding_type="cmbs",         as_json=True)  # small
debts    = cmd_soma_agency(holding_type="agency debts", as_json=True)  # 6
```


### Single-CUSIP Time Series

```python
from nyfed import cmd_soma_cusip

# Treasury CUSIP - default asset_class="tsy"
hist = cmd_soma_cusip("912810QA9", as_json=True)
# Returns up to 896 weekly records (in this case, back to 2009-02-18)

# Agency/MBS CUSIP
mbs_hist = cmd_soma_cusip("3132DVGB5", asset_class="agency", as_json=True)
```

No `date` parameter - the endpoint returns the entire held history for that
CUSIP. If Fed never held the CUSIP, returns `[]`.


### Derived Analytics

```python
from nyfed import cmd_soma_wam, cmd_soma_monthly

# WAM by security type
wam_all = cmd_soma_wam(as_json=True)                     # all Tsy
wam_nb  = cmd_soma_wam(holding_type="notesbonds", as_json=True)
wam_ad  = cmd_soma_wam(asset_class="agency", as_json=True)  # agency debt

# Monthly rollup (fewer obs per year, same CUSIP-level detail)
monthly = cmd_soma_monthly(last_n=24, as_json=True)   # last 24 months
```


### Low-Level Fetchers (Skip Pretty-Print)

When you want just the JSON without the CLI's formatted table printing to
stdout, use the private fetchers directly:

```python
from nyfed import (
    _fetch_soma_summary,
    _fetch_soma_latest_date,
    _fetch_soma_tsy_holdings,        # date -> list[dict]
    _fetch_soma_tsy_holdingtype,     # (type, date) -> list[dict]
    _fetch_soma_tsy_cusip,           # cusip -> list[dict]
    _fetch_soma_tsy_wam,
    _fetch_soma_tsy_monthly,
    _fetch_soma_tsy_release_log,
    _fetch_soma_agency_holdings,
    _fetch_soma_agency_holdingtype,
    _fetch_soma_agency_cusip,
    _fetch_soma_agency_wam,
    _fetch_soma_agency_release_log,
)

date = _fetch_soma_latest_date()            # "2026-04-15"
rows = _fetch_soma_tsy_holdings(date)       # list[dict]
hist = _fetch_soma_tsy_cusip("912810QA9")   # list[dict]
```

These are thin wrappers around `_request()` that dig into
`data["soma"]["holdings"]` (or `["summary"]` / `["dates"]`) and return the
inner list.


## Schema Reference

This is where live investigation matters. The API returns two distinct record
shapes that share only three fields.

### Treasury + Agency Debt Schema (shared)

Applies to: Bills, NotesBonds, TIPS, FRN, Agency Debts.

```
 ┌────────────────────────────┬─────────┬──────────────────────────────┐
 │ Field                      │ Type    │ Notes                        │
 ├────────────────────────────┼─────────┼──────────────────────────────┤
 │ asOfDate                   │ string  │ YYYY-MM-DD snapshot date     │
 │ cusip                      │ string  │ 9-char CUSIP                 │
 │ securityType               │ string  │ Bills / NotesBonds / TIPS /  │
 │                            │         │   FRN / Agency Debts         │
 │ maturityDate               │ string  │ YYYY-MM-DD                   │
 │ issuer                     │ string  │ "" for Tsy; FNMA/FHLMC/GNMA  │
 │                            │         │   for Agency Debts           │
 │ coupon                     │ string  │ "" for bills (zero-coupon);  │
 │                            │         │   else decimal like "3.500"  │
 │ parValue                   │ string  │ Dollars, parse as int/float  │
 │ spread                     │ string  │ FRN-specific, else ""        │
 │ inflationCompensation      │ string  │ TIPS-specific, else ""       │
 │ percentOutstanding         │ string  │ Fraction (e.g. "0.6975" =    │
 │                            │         │   69.75% of outstanding).    │
 │                            │         │   Can be "" for Agency Debt  │
 │ changeFromPriorWeek        │ string  │ Par $ WoW change             │
 │ changeFromPriorYear        │ string  │ Par $ YoY change (may be "") │
 └────────────────────────────┴─────────┴──────────────────────────────┘
```

### Agency MBS Schema (different!)

Applies to: MBS, CMBS. Note the completely different field set.

```
 ┌────────────────────────────┬─────────┬──────────────────────────────┐
 │ Field                      │ Type    │ Notes                        │
 ├────────────────────────────┼─────────┼──────────────────────────────┤
 │ asOfDate                   │ string  │ YYYY-MM-DD                   │
 │ cusip                      │ string  │ 9-char CUSIP                 │
 │ securityType               │ string  │ MBS / CMBS                   │
 │ securityDescription        │ string  │ Free text, e.g.              │
 │                            │         │   "UMBS MORTPASS 2% 10/51"   │
 │                            │         │   Contains coupon + maturity │
 │ term                       │ string  │ "30yr" / "15yr" etc          │
 │ currentFaceValue           │ string  │ Dollars (NOT parValue!)      │
 │ isAggregated               │ string  │ "Y"/"N" - multiple positions │
 │                            │         │   in the CUSIP rolled up     │
 └────────────────────────────┴─────────┴──────────────────────────────┘
```

### Schema Diff at a Glance

```
                    Tsy/AgencyDebt          Agency MBS
                    ───────────────         ──────────
 DOLLAR FIELD:      parValue                currentFaceValue
 COUPON/MATURITY:   separate fields         embedded in securityDescription
 FED SHARE:         percentOutstanding      (not provided)
 WEEKLY CHANGE:     changeFromPriorWeek     (not provided)
 ISSUER:            blank or F*MA           (not provided; implicit)
 AGGREGATION HINT:  (n/a - always 1)        isAggregated flag
```

**Practical implication:** If you are building a unified holdings dataframe
across Tsy and Agency MBS, you must normalize. Suggested approach:

```python
def normalize(row):
    if row["securityType"] in ("MBS", "CMBS"):
        return {
            "date":    row["asOfDate"],
            "cusip":   row["cusip"],
            "type":    row["securityType"],
            "par":     float(row["currentFaceValue"]),
            "desc":    row["securityDescription"],
            "pct_out": None,    # not provided for MBS
            "wk_chg":  None,    # not provided for MBS
        }
    return {
        "date":    row["asOfDate"],
        "cusip":   row["cusip"],
        "type":    row["securityType"],
        "par":     float(row["parValue"]) if row["parValue"] else 0.0,
        "desc":    f"{row['coupon']}% {row['maturityDate']}",
        "pct_out": float(row["percentOutstanding"]) if row["percentOutstanding"] else None,
        "wk_chg":  float(row["changeFromPriorWeek"]) if row["changeFromPriorWeek"] else 0.0,
    }
```

Do not attempt to derive `percentOutstanding` or weekly changes for MBS from
this endpoint alone - those analytics need to be computed from sequential
snapshot diffs or fetched from a different data source (Fed H.4.1 release,
Treasury Monthly Statement of the Public Debt, etc.).


## Gotchas

### 1. CLI commands print before they return

All `cmd_*` functions call `print()` (header + pretty table) even when
`as_json=True`. This is a side effect of using the same function for CLI and
programmatic use. If you are calling from a notebook, script, or web handler
and want clean output, suppress stdout:

```python
import io, contextlib
from nyfed import cmd_soma_holdings

with contextlib.redirect_stdout(io.StringIO()):
    rows = cmd_soma_holdings(as_json=True)
```

Or use the `_fetch_*` helpers which never print.

### 2. All numeric fields come back as strings

Parse at the edge:

```python
par = float(row.get("parValue") or 0)
pct = float(row.get("percentOutstanding") or 0)
```

Empty strings are common (bills have no coupon, Agency Debt sometimes has no
`percentOutstanding`, etc.). A blank coupon is NOT zero-coupon signalling -
bills genuinely discount-price with no coupon at all.

### 3. Dates are weekly Wednesdays

The snapshot date (`asOfDate`) is always a Wednesday. If you pass a Thursday
or weekend date to `cmd_soma_holdings(date="...")`, the endpoint returns
empty. To reliably get a historical snapshot, either:

- Use a known Wednesday date
- Pull the release log and pick an `asOfDate` from there:

```python
from nyfed import _fetch_soma_tsy_release_log
dates = [d["asOfDate"] for d in _fetch_soma_tsy_release_log()]
# ['2026-04-15', '2026-04-08', '2026-04-01', ...]
```

### 4. Agency Debt is tiny and shrinking

Only 6 Agency Debt CUSIPs remain (totaling ~$2.3B). The Fed is in runoff;
expect this to trend to zero. Don't build workflows that assume a
statistically meaningful cross-section here.

### 5. MBS "aggregated" rows combine multiple positions

The `isAggregated: "Y"` flag means the Fed holds multiple lots of that CUSIP
and they have been summed. You cannot reconstruct individual tranche-level
cost bases from this data.

### 6. Single-CUSIP endpoint depth varies

A CUSIP that was recently issued and purchased has a short history. A CUSIP
acquired during QE1 goes back 15+ years. The `912810QA9` example returned
896 weekly observations dating to 2009-02-18.

### 7. Rate limits

The module retries on HTTP 429 with 5s / 10s / 15s backoff. For large batch
workflows (e.g. pulling single-CUSIP history for every current holding),
throttle your own loop - the 8,446 MBS CUSIPs each requiring a separate
call would be slow and likely rate-limited.

### 8. No fallback data sources

The module talks directly to markets.newyorkfed.org. If the API is down,
there is no cache, no mirror, no FRED-style backup. For analytical workflows
that need resilience, export to CSV (`export_fmt="csv"`) and build your own
cache layer.


## Worked Example: Tracking a QE1-Era Bond Through QT

Question: How much of the 3.500% Feb-2039 bond has the Fed actually let run
off? (None, as it turns out - but here's how to verify.)

```python
import io, contextlib
from nyfed import cmd_soma_cusip

with contextlib.redirect_stdout(io.StringIO()):
    hist = cmd_soma_cusip("912810QA9", as_json=True)

# Sort oldest to newest
hist_sorted = sorted(hist, key=lambda r: r["asOfDate"])

first = hist_sorted[0]
last  = hist_sorted[-1]

par_start = float(first["parValue"]) / 1e9
par_end   = float(last["parValue"])  / 1e9
pct_start = float(first["percentOutstanding"]) * 100
pct_end   = float(last["percentOutstanding"])  * 100

print(f"First held: {first['asOfDate']}")
print(f"  Par:  ${par_start:.1f}B")
print(f"  Pct:  {pct_start:.2f}% of outstanding")
print(f"Latest:     {last['asOfDate']}")
print(f"  Par:  ${par_end:.1f}B")
print(f"  Pct:  {pct_end:.2f}% of outstanding")
print(f"Weeks held: {len(hist_sorted)}")

# Output:
#   First held: 2009-02-18
#     Par:  $3.6B
#     Pct:  20.00% of outstanding
#   Latest:     2026-04-15
#     Par:  $18.1B
#     Pct:  69.75% of outstanding
#   Weeks held: 896
```

This tells you the Fed built up from 20% to 69.75% of this bond's outstanding
float over 2009-2014 (QE1-3 reopenings), then held flat through QT. Because
coupon securities held to maturity run off at maturity rather than through
active sales, and this bond matures 2039, it will stay on the balance sheet
under any plausible QT path.


## Worked Example: QT Runoff Decomposition

Question: Of the ~$4T Notes+Bonds runoff since 2022, how much was passive
(matured) vs active (sold back via buybacks)?

```python
from nyfed import _fetch_soma_summary

summary = _fetch_soma_summary()
records = sorted(summary, key=lambda r: r["asOfDate"])

def bn(s):
    return float(s) / 1e9

# Find specific dates
def at_date(target):
    return next(r for r in records if r["asOfDate"] >= target)

qt_start = at_date("2022-06-01")
current  = records[-1]

nb_start = bn(qt_start["notesbonds"])
nb_end   = bn(current["notesbonds"])
mbs_start = bn(qt_start["mbs"])
mbs_end   = bn(current["mbs"])

print(f"QT start  {qt_start['asOfDate']}")
print(f"  Notes+Bonds: ${nb_start:,.0f}B")
print(f"  MBS:         ${mbs_start:,.0f}B")
print(f"Current   {current['asOfDate']}")
print(f"  Notes+Bonds: ${nb_end:,.0f}B  (Δ {nb_end - nb_start:+,.0f}B)")
print(f"  MBS:         ${mbs_end:,.0f}B  (Δ {mbs_end - mbs_start:+,.0f}B)")
```

For deeper decomposition (passive vs active), pair this with:
- `cmd_tsy_ops(operation="sales")` - any outright sales (typically zero)
- `cmd_tsy_ops(operation="purchases")` - reinvestment purchases
- `cmd_ambs_ops()` - agency MBS operations


## Worked Example: Which Bonds Are Rolling Off Next?

Question: What CUSIPs mature in the next 90 days, and how much par does the
Fed hold in each?

```python
import io, contextlib
from datetime import date, timedelta
from nyfed import cmd_soma_holdings

with contextlib.redirect_stdout(io.StringIO()):
    holdings = cmd_soma_holdings(as_json=True)

today  = date.today()
cutoff = today + timedelta(days=90)

upcoming = [
    h for h in holdings
    if date.fromisoformat(h["maturityDate"]) <= cutoff
    and h["securityType"] != "FRN"
]

upcoming.sort(key=lambda h: h["maturityDate"])

total_par = sum(float(h["parValue"]) for h in upcoming) / 1e9
print(f"Maturing in next 90 days: {len(upcoming)} CUSIPs, "
      f"${total_par:,.1f}B par")

for h in upcoming[:20]:
    par_bn = float(h["parValue"]) / 1e9
    pct    = float(h["percentOutstanding"]) * 100
    print(f"  {h['cusip']}  {h['maturityDate']}  "
          f"{h['securityType']:<10}  ${par_bn:6.1f}B  {pct:5.1f}% of outstanding")
```

This is the single most useful query for QT cap-vs-maturity analysis - it
tells you how much Treasury would naturally run off at each maturity date,
which you then compare against the $25B/month cap to see how much
reinvestment is required.


## CLI Cheatsheet

```bash
cd GS/data/apis/nyfed

# Summary
python nyfed.py soma
python nyfed.py soma-history --weeks 52
python nyfed.py soma-history --weeks 260 --export csv

# CUSIP-level Treasury
python nyfed.py soma-holdings
python nyfed.py soma-holdings --type bills
python nyfed.py soma-holdings --type notesbonds --json
python nyfed.py soma-holdings --type tips
python nyfed.py soma-holdings --type frn
python nyfed.py soma-holdings --date 2025-12-31

# CUSIP-level Agency
python nyfed.py soma-agency
python nyfed.py soma-agency --type mbs
python nyfed.py soma-agency --type "agency debts"

# Single CUSIP history
python nyfed.py soma-cusip 912810QA9
python nyfed.py soma-cusip 912810QA9 --export csv
python nyfed.py soma-cusip 3132DVGB5 --asset-class agency

# WAM
python nyfed.py soma-wam
python nyfed.py soma-wam --type notesbonds
python nyfed.py soma-wam --asset-class agency

# Monthly rollup
python nyfed.py soma-monthly --last 48 --export csv

# Interactive mode (no args launches menu)
python nyfed.py
```


## Live Data Snapshot (2026-04-15)

Pulled while writing this doc, for reality-check:

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                  SOMA Snapshot - 2026-04-15                      │
 ├─────────────────────────┬─────────────┬──────────────────────────┤
 │ Category                │ Value ($B)  │ CUSIP Count              │
 ├─────────────────────────┼─────────────┼──────────────────────────┤
 │ Total                   │   6,305.8   │                          │
 │                         │             │                          │
 │ Notes + Bonds           │   3,602.3   │   323                    │
 │ Bills                   │     412.6   │    49                    │
 │ TIPS (ex-ICP)           │     275.8   │    48                    │
 │ TIPS Inflation Comp     │     100.2   │   (part of TIPS)         │
 │ FRN                     │      16.4   │     8                    │
 │ MBS                     │   1,988.8   │ 8,446                    │
 │ CMBS                    │       7.7   │   (small)                │
 │ Agency Debt             │       2.3   │     6                    │
 ├─────────────────────────┼─────────────┼──────────────────────────┤
 │ Treasury subtotal       │   4,307.1   │   428                    │
 │ Agency subtotal         │   1,998.8   │ 8,452+                   │
 │ Weekly summary history  │             │ 1,189 obs (back to 2003) │
 └─────────────────────────┴─────────────┴──────────────────────────┘
```


## See Also

- `GS/data/apis/nyfed/SKILL.md` - full nyfed API reference (rates, repo, PDs,
  operations, fxswaps, etc.)
- `GS/data/apis/nyfed/examples/qt_balance_sheet_analysis.py` - end-to-end
  QT analysis script
- `GS/data/apis/nyfed/examples/funding_stress_monitor.py` - repo/RRP dashboard
- `GS/data/apis/treasury/SKILL.md` - complementary Treasury Fiscal Data API
  for debt outstanding (the denominator of `percentOutstanding`)
