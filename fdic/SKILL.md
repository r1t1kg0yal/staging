# FDIC BankFind Suite

Script: `GS/data/apis/fdic/fdic.py`
Base URL: `https://api.fdic.gov/banks`
Docs: `https://api.fdic.gov/banks/docs/`
Auth: None required
Rate limit: No formal limit (max 10,000 records per request; offset-based pagination)
Dependencies: `requests`


## Triggers

Use for: individual bank financials (balance sheet, income, credit quality, deposits, capital), banking system aggregates (1934-present), bank failures and resolution details, CRE concentration screening, uninsured deposit risk, NIM and funding cost analysis, peer comparison across any Call Report field, branch locations with lat/lng, M&A and structure change history, deposit market share (SOD), state-level and community bank analysis.

Not for: bank holding company consolidated data (FFIEC FR Y-9C), weekly banking aggregates (FRED H.8), bank stock prices (market data), 10-K/10-Q text (SEC EDGAR), non-US banks (BIS), Treasury auctions (TreasuryDirect), overnight funding rates (NY Fed), commercial paper / CD rates (FRED).


## Data Catalog

### Endpoints

| Endpoint | ~Records | Description |
|----------|----------|-------------|
| `/institutions` | ~14,000 | Bank demographics: name, location, charter, assets, deposits, ROA/ROE |
| `/financials` | millions | Quarterly Call Report data (RISVIEW): 1,000+ fields per CERT+REPDTE |
| `/failures` | ~4,100 | Every bank failure 1934-present with resolution type and DIF cost |
| `/summary` | ~5,000 | Industry aggregates by year from 1934 (filterable by state, type) |
| `/locations` | ~80,000 | Branch locations with lat/lng, service type, main office flag |
| `/sod` | millions | Summary of Deposits: branch-level annual deposit data from ~1994 |
| `/history` | ~200,000 | Structure events: mergers, acquisitions, name changes, charter conversions |
| `/demographics` | sparse | Community demographics tied to CERT + REPDTE |

### Monetary Units

All dollar amounts are in **thousands** ($000s):

| API Value | Actual Dollars |
|-----------|---------------|
| ASSET: 3752662000 | $3.75 TRILLION |
| DEP: 438331000 | $438 BILLION |
| NETINC: 8737000 | $8.7 BILLION |
| COST: 23460 | $23.5 MILLION |

### Filter Syntax

Elasticsearch query string syntax. All field names and values must be UPPERCASE.

```
NAME:"First Bank"                         Exact phrase match
STALP:NY AND ACTIVE:1                    Boolean AND
NAME:"First Bank" OR NAME:"Unibank"      Boolean OR
STNAME:("West Virginia","Delaware")       Multi-value (any of)
!(STNAME:"Virginia")                      Exclusion (NOT)
DEP:[50000 TO *]                          Numeric range inclusive ($000s)
DATEUPDT:["2010-01-01" TO "2010-12-31"]   Date range inclusive
FAILYR:{2015 TO 2016}                     Range exclusive
```

### Key Identifiers

| Field | Description |
|-------|-------------|
| CERT | FDIC certificate number (primary key across all endpoints) |
| REPDTE | Report date YYYYMMDD (quarter ends: 0331, 0630, 0930, 1231) |
| UNINUM | FDIC unique number for branches |
| NAME | Legal institution name |
| ACTIVE | 1 = open and insured, 0 = closed |

### Balance Sheet Fields

| Field | Description |
|-------|-------------|
| ASSET | Total assets ($000s) |
| DEP | Total deposits ($000s) |
| DEPDOM | Domestic deposits ($000s) |
| EQTOT | Total equity capital ($000s) |
| SC | Total securities ($000s) |
| LNLSNET | Net loans and leases ($000s) |
| INTBLIB | Interest-bearing liabilities ($000s) |

### Income Statement Fields (YTD cumulative)

| Field | Description |
|-------|-------------|
| INTINC | Total interest income ($000s) |
| EINTEXP | Total interest expense ($000s) |
| NITEFN | Net interest income ($000s) |
| NONII | Non-interest income ($000s) |
| NONIX | Non-interest expense ($000s) |
| NETINC | Net income ($000s) |
| ELNATR | Provision for loan losses ($000s) |

### Loan Composition Fields

| Field | Description |
|-------|-------------|
| LNRE | Real estate loans ($000s) |
| LNRECONS | Construction & land dev loans ($000s) |
| LNRENRES | Non-residential RE loans ($000s) |
| LNREMULT | Multifamily RE loans ($000s) |
| LNCI | Commercial & industrial loans ($000s) |
| LNCRCD | Credit card loans ($000s) |
| LNCONOTH | Other consumer loans ($000s) |
| LNREAG | Agricultural RE loans ($000s) |

### Credit Quality Fields

| Field | Description |
|-------|-------------|
| NCLNLS | Net charge-offs ($000s) |
| NCLNLSR | Net charge-off rate (%) |
| NTLNLSR | Net loan loss rate (%) |
| LNATRES | Allowance for loan losses ($000s) |
| P3ASSET | Assets 30-89 days past due ($000s) |
| P9ASSET | Assets 90+ days past due ($000s) |
| NAESSION | Non-accrual loans ($000s) |

### Capital & Ratio Fields

| Field | Description |
|-------|-------------|
| ROA | Return on assets (annualized %) |
| ROE | Return on equity (annualized %) |
| NIMY | Net interest margin (annualized %) |
| EEFFR | Efficiency ratio (%) |
| IDT1CER | Tier 1 capital ratio (%) |
| IDT1LER | Tier 1 leverage ratio (%) |
| LNLSDEPR | Loans-to-deposits ratio (%) |

### Deposit Fields

| Field | Description |
|-------|-------------|
| DEPUNA | Uninsured deposits ($000s) |
| BRO | Brokered deposits ($000s) |
| DDT | Demand deposits ($000s) |
| NTRSMMDA | Money market deposit accounts ($000s) |
| NTRTMLG | Time deposits >$250K ($000s) |

### Failure-Specific Fields

| Field | Description |
|-------|-------------|
| FAILDATE | Date of failure |
| FAILYR | Year of failure |
| QBFASSET | Total assets at failure ($000s) |
| QBFDEP | Total deposits at failure ($000s) |
| COST | Estimated loss to DIF ($000s) |
| RESTYPE1 | Resolution type (PA, PI, PO, A/A, IDT, etc.) |
| SAVR | Insurance fund (DIF, BIF, SAIF, RTC, FSLIC) |

### Financial Presets

The `/financials` endpoint has 1,000+ fields. These presets select commonly needed subsets:

| Preset | Fields | Use Case |
|--------|--------|----------|
| default | ASSET, DEP, NETINC, ROA, ROE, NIM, provision | Quick overview |
| balance_sheet | ASSET, DEP, DEPDOM, EQTOT, SC, LNLSNET, borrowings | Asset/liability structure |
| income | INTINC, EINTEXP, NII, NONII, NONIX, NETINC, provision | Revenue decomposition |
| ratios | ROA, ROE, NIM, efficiency, NCL rate, loan/dep, Tier 1 | Performance benchmarking |
| loans | Net loans, RE, construction, C&I, consumer, credit card, reserves, NCLs | Credit composition |
| deposits | DEP, DEPDOM, DEPFOR, DDT, MMDA, time, uninsured, brokered, funding cost | Deposit franchise |
| credit_quality | NCLs by type (RE, C&I, consumer, credit card), past-dues, non-accruals, reserves | Asset quality |
| capital | Equity, Tier 1, Total RBC, leverage ratio, RWA, dividends | Capital adequacy |
| securities | Total SC, UST, munis, MBS, ABS | Investment portfolio |
| cre | RE loans by type (construction, non-res, multifamily, resi, ag), equity, Tier 1 | CRE concentration |
| past_due | 30-89 day, 90+ day, non-accrual (total and by RE, C&I) | Delinquency detail |
| minimal | ASSET, DEP, NETINC | Bare minimum |

For any field not in a preset, pass `--fields FIELD1,FIELD2,...` directly. Full field schema: `https://api.fdic.gov/banks/docs/risview_properties.yaml`

### Notable CERT Numbers

| CERT | Institution | Notes |
|------|-------------|-------|
| 628 | JPMorgan Chase Bank NA | Largest US bank ($3.75T assets) |
| 3510 | Bank of America NA | #2 ($2.64T) |
| 7213 | Citibank NA | #3 ($1.84T) |
| 3511 | Wells Fargo Bank NA | #4 ($1.82T) |
| 33124 | Goldman Sachs Bank USA | Bank sub (Marcus, Apple Card, institutional) |
| 34221 | Morgan Stanley Private Bank NA | Bank sub (wealth management) |
| 6548 | U.S. Bank NA | #5 ($676B) |
| 4297 | Capital One NA | Major consumer bank |
| 9846 | Truist Bank | Regional ($540B) |
| 6384 | PNC Bank NA | Regional ($568B) |
| 24735 | Silicon Valley Bank | Failed 3/10/2023 (ACTIVE:0) |
| 59017 | First Republic Bank | Failed 5/1/2023 (ACTIVE:0) |
| 57053 | Signature Bank | Failed 3/12/2023 (ACTIVE:0) |


## CLI Recipes

All recipe commands support `--json` for structured output. Direct endpoint queries also support `--export csv|json`.

### Direct Endpoint Queries

```bash
# Institutions: search by state, charter, size
python fdic.py institutions --filters 'STALP:NY AND ACTIVE:1' --limit 10
python fdic.py institutions --filters 'STALP:NY AND ACTIVE:1' --fields CERT,NAME,ASSET,DEP --sort-by ASSET --limit 10 --json
python fdic.py institutions --search 'NAME:JPMorgan' --limit 5 --json
python fdic.py institutions --filters 'ACTIVE:1 AND ASSET:[10000000 TO *]' --sort-by ASSET --sort-order DESC --limit 50 --export csv

# Financials: quarterly Call Report data by CERT + REPDTE
python fdic.py financials --filters 'CERT:628' --fields CERT,REPDTE,ASSET,DEP,NETINC,ROA,ROE --sort-by REPDTE --limit 8 --json
python fdic.py financials --filters 'CERT:628' --sort-by REPDTE --limit 20 --export csv
python fdic.py financials --filters 'REPDTE:20251231 AND ASSET:[10000000 TO *]' --fields CERT,REPDTE,ASSET,NIMY,ROA --sort-by ASSET --limit 50 --json

# Failures: all failures or filtered by year/state
python fdic.py failures --sort-by FAILDATE --sort-order DESC --limit 20 --json
python fdic.py failures --filters 'FAILYR:2023' --fields NAME,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1 --json
python fdic.py failures --agg-by FAILYR --agg-sum-fields QBFASSET,COST --agg-limit 50 --json

# Summary: industry aggregates by year
python fdic.py summary --filters 'YEAR:2024' --fields STNAME,YEAR,NETINC,ASSET --json
python fdic.py summary --filters 'STNAME:"United States"' --sort-by YEAR --sort-order DESC --limit 50 --json

# Locations: branch network with lat/lng
python fdic.py locations --filters 'CERT:628 AND STALP:CA' --fields NAME,OFFNAME,CITY,LATITUDE,LONGITUDE --limit 100 --json

# SOD: Summary of Deposits (branch-level annual)
python fdic.py sod --filters 'CERT:628 AND YEAR:2023' --fields NAMEFULL,STALPBR,CITYBR,DEPSUMBR --limit 50 --json

# History: structure change events
python fdic.py history --filters 'CERT:628' --sort-by PROCDATE --sort-order DESC --limit 100 --json
python fdic.py history --search 'INSTNAME:Goldman' --limit 20 --json

# Demographics
python fdic.py demographics --filters 'CERT:628 AND REPDTE:20230630' --json
```

### General Recipes

```bash
# Top banks by total assets (US or by state)
python fdic.py largest-banks
python fdic.py largest-banks --top 20
python fdic.py largest-banks --top 10 --state TX
python fdic.py largest-banks --top 5 --json

# Fuzzy bank name search (returns CERT numbers)
python fdic.py bank-lookup --name "Wells Fargo"
python fdic.py bank-lookup --name "Goldman Sachs" --json
python fdic.py bank-lookup --name "JPMorgan" --limit 5

# Quarterly financial time series for a single bank
# preset choices: default, balance_sheet, income, ratios, loans, deposits,
#   credit_quality, capital, securities, cre, past_due, minimal
python fdic.py bank-financials --cert 628 --quarters 20 --preset default
python fdic.py bank-financials --cert 628 --quarters 40 --preset balance_sheet
python fdic.py bank-financials --cert 628 --quarters 20 --preset income --json
python fdic.py bank-financials --cert 628 --quarters 20 --preset ratios
python fdic.py bank-financials --cert 628 --quarters 20 --preset loans
python fdic.py bank-financials --cert 628 --quarters 20 --preset deposits
python fdic.py bank-financials --cert 628 --quarters 20 --preset credit_quality
python fdic.py bank-financials --cert 628 --quarters 20 --preset capital
python fdic.py bank-financials --cert 628 --quarters 20 --preset securities
python fdic.py bank-financials --cert 628 --quarters 20 --preset cre
python fdic.py bank-financials --cert 628 --quarters 12 --preset past_due
python fdic.py bank-financials --cert 33124 --quarters 4 --preset minimal --json

# Recent failures
python fdic.py recent-failures
python fdic.py recent-failures --top 25
python fdic.py recent-failures --top 10 --json

# Failures aggregated by year
python fdic.py failures-by-year
python fdic.py failures-by-year --json

# State banking summary for a year
python fdic.py state-summary
python fdic.py state-summary --year 2024
python fdic.py state-summary --year 2023 --json

# All branch locations for a bank
python fdic.py branches --cert 628
python fdic.py branches --cert 628 --json

# Structure change history (mergers, acquisitions, name changes)
python fdic.py bank-history --cert 628
python fdic.py bank-history --cert 628 --json

# SOD deposit rankings by year/state
python fdic.py deposit-rankings
python fdic.py deposit-rankings --year 2024
python fdic.py deposit-rankings --year 2023 --state CA
python fdic.py deposit-rankings --year 2023 --state CA --json

# Community banks by state
python fdic.py community-banks
python fdic.py community-banks --state TX
python fdic.py community-banks --state TX --json

# Show all field presets for all endpoints
python fdic.py field-catalog
```

### Deposit & Funding Recipes

```bash
# Granular deposit composition: demand, MMDA, time, uninsured, brokered
python fdic.py deposit-mix --cert 628
python fdic.py deposit-mix --cert 628 --quarters 20
python fdic.py deposit-mix --cert 628 --quarters 20 --json

# Uninsured deposit concentration screen
python fdic.py uninsured-screen
python fdic.py uninsured-screen --min-assets 10000000
python fdic.py uninsured-screen --min-assets 1000000 --json

# System-wide deposit trends (from /summary, 1934-present)
python fdic.py system-deposits
python fdic.py system-deposits --years 20
python fdic.py system-deposits --years 40 --json

# Funding cost comparison across banks
python fdic.py funding-costs
python fdic.py funding-costs --certs '628,3510,7213,3511,33124'
python fdic.py funding-costs --certs '628,3510,7213,3511,33124' --json

# Geographic deposit market share
python fdic.py geo-deposits --state CA
python fdic.py geo-deposits --year 2023 --state CA
python fdic.py geo-deposits --year 2023 --state CA --json
```

### Credit & System Health Recipes

```bash
# System health: assets, deposits, income, provisions from 1934
python fdic.py system-health
python fdic.py system-health --json

# Failure waves: count + total assets + DIF cost by year
python fdic.py failure-waves
python fdic.py failure-waves --json

# Credit cycle: NCL rates, provisions, past-dues across large banks
python fdic.py credit-cycle
python fdic.py credit-cycle --min-assets 10000000
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json

# NIM regime across top banks
python fdic.py nim-regime
python fdic.py nim-regime --top 50
python fdic.py nim-regime --top 50 --repdte 20251231
python fdic.py nim-regime --top 50 --repdte 20251231 --json

# Capital ratio distribution (sorted weakest first)
python fdic.py capital-distribution
python fdic.py capital-distribution --min-assets 1000000
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231 --json
```

### Balance Sheet & Loan Recipes

```bash
# CRE concentration screen
python fdic.py cre-screen
python fdic.py cre-screen --min-assets 1000000
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json

# Loan growth decomposition time series
python fdic.py loan-growth --cert 33124
python fdic.py loan-growth --cert 33124 --quarters 40
python fdic.py loan-growth --cert 33124 --quarters 40 --json

# Reserve adequacy: reserves vs NCLs vs past-dues
python fdic.py reserve-adequacy
python fdic.py reserve-adequacy --min-assets 10000000
python fdic.py reserve-adequacy --min-assets 10000000 --repdte 20251231
python fdic.py reserve-adequacy --min-assets 10000000 --repdte 20251231 --json

# Securities portfolio composition (single bank or top banks by size)
python fdic.py securities-portfolio --cert 628
python fdic.py securities-portfolio --cert 628 --quarters 20
python fdic.py securities-portfolio --cert 628 --quarters 20 --json
python fdic.py securities-portfolio --quarters 20 --json

# Multi-bank peer comparison on any preset
python fdic.py peer-comparison --certs '628,3510,7213,3511'
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset default
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset ratios
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset deposits
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset credit_quality
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset capital
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset cre
python fdic.py peer-comparison --certs '628,3510,7213,3511' --repdte 20251231 --preset ratios --json

# Past-due and non-accrual detail by loan type
python fdic.py past-due-detail --cert 628
python fdic.py past-due-detail --cert 628 --quarters 12
python fdic.py past-due-detail --cert 628 --quarters 12 --json
```

### Bulk Export

```bash
python fdic.py bulk-export --endpoint institutions --filters 'ACTIVE:1 AND STALP:CA' --format csv
python fdic.py bulk-export --endpoint financials --filters 'REPDTE:20251231' --max-records 5000 --format json
python fdic.py bulk-export --endpoint financials --filters 'REPDTE:20251231' --fields CERT,REPDTE,ASSET,DEP,ROA --format csv
python fdic.py bulk-export --endpoint failures --format csv
python fdic.py bulk-export --endpoint institutions --filters 'ACTIVE:1' --max-records 0 --format json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | Endpoint queries |
| `--export json` | Export to JSON file | Endpoint queries |
| `--filters EXPR` | Elasticsearch filter expression | Endpoint queries |
| `--fields F1,F2,...` | Comma-separated field list (UPPERCASE) | Endpoint queries |
| `--sort-by FIELD` | Sort field (UPPERCASE) | Endpoint queries |
| `--sort-order ASC\|DESC` | Sort direction (default: DESC) | Endpoint queries |
| `--limit N` | Max records (max 10,000) | Endpoint queries |
| `--offset N` | Skip N records (pagination) | Endpoint queries |
| `--search TEXT` | Fuzzy text search | institutions, history |
| `--cert N` | FDIC certificate number | Bank-specific recipes |
| `--quarters N` | Number of quarters | Financial time series |
| `--preset NAME` | Field preset name | bank-financials, peer-comparison |
| `--top N` | Number of results | largest-banks, recent-failures, nim-regime |
| `--state XX` | State abbreviation | largest-banks, deposit-rankings, community-banks, geo-deposits |
| `--year YYYY` | Year | state-summary, deposit-rankings, geo-deposits |
| `--certs 'N,N,...'` | Comma-separated CERTs | funding-costs, peer-comparison |
| `--min-assets N` | Minimum assets in $000s | Screen commands |
| `--repdte YYYYMMDD` | Report date | credit-cycle, nim-regime, capital-distribution, cre-screen, reserve-adequacy |
| `--agg-by FIELD` | Aggregate by field | Endpoint queries (financials, summary, failures, history, sod) |
| `--agg-sum-fields F1,F2` | Fields to sum in aggregation | Endpoint queries |
| `--agg-limit N` | Aggregation bucket limit | Endpoint queries |
| `--max-records N` | Max records for bulk export (0=all) | bulk-export |
| `--format csv\|json` | Output format for bulk export | bulk-export |


## Python Recipes

### Direct API via Internal Helpers

```python
from fdic import _get, _get_all, _extract_rows, FINANCIAL_FIELDS, INSTITUTION_FIELDS

# Single bank latest quarter
resp = _get("financials", {
    "filters": "CERT:628",
    "fields": FINANCIAL_FIELDS["default"],
    "sort_by": "REPDTE",
    "sort_order": "DESC",
    "limit": 1,
})
rows, total = _extract_rows(resp)

# All active institutions in a state
resp = _get("institutions", {
    "filters": "STALP:NY AND ACTIVE:1",
    "fields": INSTITUTION_FIELDS["default"],
    "sort_by": "ASSET",
    "sort_order": "DESC",
    "limit": 50,
})
rows, total = _extract_rows(resp)

# Bank financial time series (20 quarters, any preset)
for preset in ["default", "balance_sheet", "income", "ratios", "loans",
               "deposits", "credit_quality", "capital", "securities", "cre"]:
    resp = _get("financials", {
        "filters": "CERT:628",
        "fields": FINANCIAL_FIELDS[preset],
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": 20,
    })
    rows, total = _extract_rows(resp)

# Failures in 2023
resp = _get("failures", {
    "filters": "FAILYR:2023",
    "fields": "NAME,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1",
    "sort_by": "FAILDATE",
    "sort_order": "DESC",
    "limit": 25,
})
rows, total = _extract_rows(resp)

# Industry aggregates
resp = _get("summary", {
    "filters": 'STNAME:"United States"',
    "fields": "STNAME,YEAR,ASSET,DEP,INTINC,EINTEXP,NIM,NETINC",
    "sort_by": "YEAR",
    "sort_order": "DESC",
    "limit": 50,
})
rows, total = _extract_rows(resp)

# Bulk export: paginate through all active CA banks
all_rows = list(_get_all("institutions", {
    "filters": "ACTIVE:1 AND STALP:CA",
    "fields": "CERT,NAME,ASSET,DEP,ROA",
}, max_records=5000))

# Peer comparison: multiple CERTs, latest quarter
cert_filter = " OR ".join(f"CERT:{c}" for c in [628, 3510, 7213, 3511])
resp = _get("financials", {
    "filters": f"REPDTE:20251231 AND ({cert_filter})",
    "fields": FINANCIAL_FIELDS["ratios"],
    "sort_by": "ASSET",
    "sort_order": "DESC",
    "limit": 20,
})
rows, total = _extract_rows(resp)
```

### Direct API via Requests

```python
import requests

BASE = "https://api.fdic.gov/banks"

def fdic_get(endpoint, filters=None, fields=None, sort_by=None,
             sort_order="DESC", limit=100):
    params = {"limit": limit, "sort_order": sort_order}
    if filters:
        params["filters"] = filters
    if fields:
        params["fields"] = fields
    if sort_by:
        params["sort_by"] = sort_by
    resp = requests.get(f"{BASE}/{endpoint}", params=params)
    data = resp.json()
    rows = [r.get("data", r) for r in data.get("data", [])]
    total = data.get("meta", {}).get("total", 0)
    return rows, total

# Top 20 largest banks
rows, total = fdic_get("institutions",
    filters="ACTIVE:1",
    fields="CERT,NAME,ASSET,DEP,ROA",
    sort_by="ASSET",
    limit=20)

# JPMorgan last 8 quarters
rows, total = fdic_get("financials",
    filters="CERT:628",
    fields="CERT,REPDTE,ASSET,DEP,NETINC,ROA,ROE,NIMY",
    sort_by="REPDTE",
    limit=8)

# Bank failures in 2023
rows, total = fdic_get("failures",
    filters="FAILYR:2023",
    fields="NAME,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1",
    sort_by="FAILDATE")

# All active banks in California
rows, total = fdic_get("institutions",
    filters='STALP:CA AND ACTIVE:1',
    fields='CERT,NAME,ASSET,DEP,ROA',
    sort_by='ASSET',
    limit=50)

# Industry summary for a year
rows, total = fdic_get("summary",
    filters='YEAR:2024',
    fields='STNAME,YEAR,ASSET,DEP,NETINC,INTINC,EINTEXP')
```

### Subprocess Wrapper

```python
import subprocess, json

def fdic_query(command, args_str=""):
    cmd = f"python GS/data/apis/fdic/fdic.py {command} {args_str} --json"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout else None

# Top 20 largest US banks
largest = fdic_query("largest-banks", "--top 20")

# JPMorgan quarterly financials (default preset)
jpm = fdic_query("bank-financials", "--cert 628 --quarters 20 --preset default")

# JPMorgan deposit composition
deposits = fdic_query("deposit-mix", "--cert 628 --quarters 20")

# Recent failures
failures = fdic_query("recent-failures", "--top 25")

# System health (1934-present)
health = fdic_query("system-health")

# Credit cycle indicators
credit = fdic_query("credit-cycle", "--min-assets 10000000 --repdte 20251231")

# CRE concentration screen
cre = fdic_query("cre-screen", "--min-assets 1000000 --repdte 20251231")

# Peer comparison on ratios
peers = fdic_query("peer-comparison",
    "--certs '628,3510,7213,3511' --preset ratios --repdte 20251231")

# Uninsured deposit screen
uninsured = fdic_query("uninsured-screen", "--min-assets 10000000")

# NIM regime
nim = fdic_query("nim-regime", "--top 50 --repdte 20251231")

# Failure waves
waves = fdic_query("failure-waves")

# Capital distribution
capital = fdic_query("capital-distribution", "--min-assets 1000000 --repdte 20251231")

# Loan growth decomposition
loans = fdic_query("loan-growth", "--cert 33124 --quarters 40")

# Reserve adequacy
reserves = fdic_query("reserve-adequacy", "--min-assets 10000000 --repdte 20251231")

# Securities portfolio
securities = fdic_query("securities-portfolio", "--cert 628 --quarters 20")

# Past-due detail
pastdue = fdic_query("past-due-detail", "--cert 628 --quarters 12")

# Funding costs
funding = fdic_query("funding-costs", "--certs '628,3510,7213,3511,33124'")
```


## Composite Recipes

### Individual Bank Deep Dive

```bash
python fdic.py bank-lookup --name "Goldman Sachs" --json
python fdic.py bank-financials --cert 33124 --quarters 4 --preset default --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset balance_sheet --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset credit_quality --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset deposits --json
python fdic.py bank-financials --cert 33124 --quarters 20 --preset cre --json
python fdic.py bank-history --cert 33124 --json
```

PRISM receives: CERT identification, 4Q overview (assets, deposits, income, ROA, ROE, NIM, provisions), 20Q balance sheet trajectory (asset growth, securities vs loans mix, equity), 20Q credit quality (NCLs by type, past-dues, non-accruals, reserves), 20Q deposit franchise (demand vs MMDA vs time vs uninsured vs brokered), 20Q CRE composition (construction, non-res, multifamily, resi, ag vs capital), corporate lineage and M&A history.

### Banking System Health Check

```bash
python fdic.py system-health --json
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json
python fdic.py nim-regime --top 50 --repdte 20251231 --json
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231 --json
python fdic.py failure-waves --json
```

PRISM receives: 90-year industry aggregates (assets, deposits, income, provisions), current credit cycle (NCL rates, past-dues, provisions across large banks), NIM regime (margin, funding cost, ROA/ROE for top 50), capital distribution (Tier 1 ratios sorted weakest first), historical failure counts and asset totals by year.

### Deposit & Funding Analysis

```bash
python fdic.py system-deposits --years 20 --json
python fdic.py uninsured-screen --min-assets 10000000 --json
python fdic.py funding-costs --certs '628,3510,7213,3511,33124' --json
python fdic.py geo-deposits --year 2023 --state CA --json
python fdic.py peer-comparison --certs '628,3510,7213,3511,33124' --preset deposits --json
```

PRISM receives: 20-year system deposit trends (total, composition, NIM, funding costs), uninsured deposit concentrations for large banks (DEPUNA as % of DEP), funding cost comparison for Big 5 (interest expense on deposits, NIM, brokered share), California deposit market share rankings, peer deposit franchise breakdown (demand vs MMDA vs time vs brokered vs uninsured).

### Peer Comparison (Multi-Dimensional)

```bash
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset default --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset ratios --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset deposits --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset credit_quality --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset capital --json
python fdic.py peer-comparison --certs '628,3510,7213,3511' --preset cre --json
```

PRISM receives: overview (assets, deposits, income, ROA, ROE, NIM), performance ratios (ROA, ROE, NIM, efficiency, NCL rate, Tier 1), deposit franchise (demand, MMDA, time, uninsured, brokered, funding cost), asset quality (NCLs by type, past-dues, non-accruals), capital (equity, Tier 1, leverage, RWA, dividends), CRE (real estate loans by type vs equity and capital).

### CRE Concentration Deep Dive

```bash
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json
python fdic.py bank-financials --cert {flagged_cert} --quarters 20 --preset cre --json
python fdic.py bank-financials --cert {flagged_cert} --quarters 12 --preset past_due --json
python fdic.py bank-financials --cert {flagged_cert} --quarters 12 --preset capital --json
```

PRISM receives: system-wide CRE screen (RE loans by type, equity, Tier 1 for banks >$1B), 20Q CRE composition for flagged bank (construction, non-res, multifamily, resi, ag), past-due progression by loan type, capital adequacy vs CRE exposure.

### Failure Analysis

```bash
python fdic.py failure-waves --json
python fdic.py recent-failures --top 25 --json
python fdic.py bank-financials --cert 24735 --quarters 20 --preset ratios --json
python fdic.py capital-distribution --min-assets 1000000 --repdte 20251231 --json
python fdic.py uninsured-screen --min-assets 10000000 --json
python fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json
```

PRISM receives: historical failure counts by year (S&L crisis, GFC, 2023 regional), recent failures with resolution details and DIF cost, pre-failure financial trajectory for SVB (CERT 24735), current capital distribution (weakest buffers), uninsured deposit concentrations, CRE concentration screen.

### Credit Cycle Monitor

```bash
python fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json
python fdic.py reserve-adequacy --min-assets 10000000 --repdte 20251231 --json
python fdic.py bank-financials --cert 628 --quarters 20 --preset credit_quality --json
python fdic.py bank-financials --cert 3510 --quarters 20 --preset credit_quality --json
```

PRISM receives: system-wide NCL rates, provisions, past-dues for large banks, reserve coverage ratios (allowance vs NCLs vs past-dues), 20Q credit quality time series for JPMorgan and BofA as bellwethers.


## Cross-Source Recipes

### Bank Health + QT Pace

```bash
python GS/data/apis/fdic/fdic.py credit-cycle --min-assets 10000000 --repdte 20251231 --json
python GS/data/apis/nyfed/nyfed.py qt-monitor --weeks 26 --json
```

PRISM receives: bank-level credit quality indicators (NCLs, provisions, past-dues) + Fed balance sheet runoff pace. Reserve tightening impact on bank funding.

### Bank Deposits + Overnight Funding

```bash
python GS/data/apis/fdic/fdic.py funding-costs --certs '628,3510,7213,3511,33124' --json
python GS/data/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: bank-level deposit costs and NIM + overnight rate complex (SOFR, EFFR, OBFR). Calibrates bank funding costs against prevailing overnight rates.

### Bank System + Weekly H.8

```bash
python GS/data/apis/fdic/fdic.py system-deposits --years 5 --json
python GS/data/apis/fred/fred.py series H8B1058NCBCMG --obs 52 --json
```

PRISM receives: quarterly FDIC deposit aggregates + weekly H.8 commercial bank deposits. Higher-frequency signal between quarterly FDIC filings.

### Bank Failures + Policy Expectations

```bash
python GS/data/apis/fdic/fdic.py recent-failures --top 10 --json
python GS/data/apis/fdic/fdic.py capital-distribution --min-assets 1000000 --json
python GS/data/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: recent failure details + capital distribution (weakest banks) + market-implied policy probabilities. Bank-level stress vs market expectations for rate relief.

### Bank CRE + BIS Cross-Border

```bash
python GS/data/apis/fdic/fdic.py cre-screen --min-assets 1000000 --repdte 20251231 --json
python GS/data/apis/bis/bis.py lbs --json
```

PRISM receives: US bank CRE concentration + BIS cross-border banking exposures. International transmission channels for CRE stress.

### Bank NIM + Treasury Curve

```bash
python GS/data/apis/fdic/fdic.py nim-regime --top 50 --repdte 20251231 --json
python GS/data/apis/treasury/treasury.py get rates --json
```

PRISM receives: bank NIM distribution + Treasury yield curve. Curve shape mapping to bank profitability.

### Bank Deposits + SEC Filings

```bash
python GS/data/apis/fdic/fdic.py deposit-mix --cert 628 --quarters 20 --json
python GS/data/apis/sec_edgar/sec_edgar.py filings --cik 0000019617 --form-type 10-K --json
```

PRISM receives: quarterly deposit composition from Call Reports + holding company 10-K narrative. Quantitative + qualitative deposit franchise assessment.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python fdic.py largest-banks --top 5`
4. Full test: `python fdic.py bank-financials --cert 628 --quarters 4 --preset default`


## Architecture

```
fdic.py
  Constants       BASE, FIELD_CATALOGS (8 endpoints), FINANCIAL_FIELDS (12 presets),
                  INSTITUTION_FIELDS, LOCATION_FIELDS, SUMMARY_FIELDS,
                  FAILURE_FIELDS, HISTORY_FIELDS, SOD_FIELDS, DEMOGRAPHICS_FIELDS
  HTTP            _get() single request, _get_all() auto-paginating bulk fetcher
  Extraction      _extract_rows() flattens FDIC response wrapper
  Display         _print_table(), _prompt(), _prompt_fields(), _display_response()
  Endpoints (8)   institutions, locations, financials, summary, failures,
                  history, sod, demographics
  General (11)    largest-banks, bank-lookup, bank-financials, recent-failures,
                  failures-by-year, state-summary, branches, bank-history,
                  deposit-rankings, community-banks, bulk-export
  Deposit (5)     deposit-mix, uninsured-screen, system-deposits,
                  funding-costs, geo-deposits
  Credit (5)      system-health, failure-waves, credit-cycle,
                  nim-regime, capital-distribution
  Balance (6)     cre-screen, loan-growth, reserve-adequacy,
                  securities-portfolio, peer-comparison, past-due-detail
  Tools (2)       raw-query (interactive only), field-catalog
  Interactive     Full menu-driven CLI (runs without arguments)
  Argparse        35+ subcommands, all with --json
```

API endpoints:
```
/institutions    -> bank demographics, assets, deposits, charter
/financials      -> quarterly Call Report data (1000+ RISVIEW fields)
/failures        -> bank failures with resolution details and DIF cost
/summary         -> industry aggregates by year from 1934
/locations       -> branch locations with lat/lng
/sod             -> Summary of Deposits (branch-level annual)
/history         -> structure change events (mergers, M&A)
/demographics    -> community demographics
```
