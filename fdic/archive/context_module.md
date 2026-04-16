# FDIC BankFind Suite API -- Data Awareness Guide

PRISM data source for US banking system monitoring. Covers every FDIC-insured institution from 1934 to present: balance sheets, income statements, credit quality, deposit flows, branch networks, failures, and structural changes.

Script: `GS/data/apis/fdic/fdic_demo.py`
Base URL: `https://api.fdic.gov/banks`
Auth: None required
Rate limit: No formal limit


## Coverage

- ~4,300 active FDIC-insured institutions (every insured bank in the US)
- ~10,000+ inactive/historical institutions (merged, failed, closed)
- Quarterly Call Report data (FFIEC 031/041) going back 60-80+ quarters per bank
- Industry aggregates from 1934 to present (91 years)
- ~80,000+ branch locations with lat/lng
- 4,100+ bank failures with resolution details and DIF cost estimates
- Summary of Deposits: branch-level annual deposit data from ~1994


## Endpoints (8)

| Endpoint | What | Records |
|----------|------|---------|
| `/institutions` | Bank demographics: name, location, charter, assets, deposits, ROA/ROE, regulator | ~14,000 |
| `/financials` | Quarterly Call Reports: 1,000+ fields (balance sheet, income, loans, credit quality, capital, ratios, deposits) | Millions |
| `/failures` | Every bank failure since 1934: resolution type, acquirer, DIF loss | ~4,100 |
| `/summary` | Industry aggregates by year (1934-present): assets, deposits, income | ~5,000 |
| `/locations` | Branch locations with address, lat/lng, service type | ~80,000 |
| `/sod` | Summary of Deposits: branch-level deposit data by year | Millions |
| `/history` | Structure changes: mergers, acquisitions, name changes, charter conversions | ~200,000 |
| `/demographics` | Community demographics tied to institution reporting | Sparse |


## Critical: Monetary Units

ALL dollar amounts are in **thousands** ($000s).

| API Value | Actual |
|-----------|--------|
| ASSET: 3752662000 | $3.75 trillion |
| DEP: 438331000 | $438 billion |
| NETINC: 8737000 | $8.7 billion |
| COST: 23460 | $23.5 million |


## Filter Syntax

Elasticsearch query strings. Field names and values must be UPPERCASE.

```
NAME:"JPMorgan"                         Exact phrase
STALP:NY AND ACTIVE:1                  Boolean AND
STNAME:("New York","California")        Multi-value
DEP:[50000 TO *]                        Numeric range ($000s)
DATEUPDT:["2020-01-01" TO "2024-12-31"] Date range
!(STNAME:"Virginia")                    NOT
```


## Key Identifiers

| Field | Description |
|-------|-------------|
| CERT | FDIC certificate number (primary key across all endpoints) |
| REPDTE | Report date YYYYMMDD (quarter ends: 0331, 0630, 0930, 1231) |
| UNINUM | Unique branch number |
| ACTIVE | 1 = open, 0 = closed |


## Financial Field Reference

### Balance Sheet
ASSET (total assets), DEP (total deposits), DEPDOM (domestic deposits), EQTOT (total equity), SC (total securities), LNLSNET (net loans), INTBLIB (interest-bearing liabilities)

### Income Statement (YTD cumulative)
INTINC (interest income), EINTEXP (interest expense), NITEFN (net interest income), NONII (non-interest income), NONIX (non-interest expense), NETINC (net income), ELNATR (provision for loan losses)

### Loan Composition
LNRE (real estate), LNRECONS (construction), LNRENRES (non-residential CRE), LNREMULT (multifamily), LNCI (C&I), LNCRCD (credit card), LNCONOTH (other consumer), LNREAG (agricultural RE)

### Credit Quality
NCLNLS (net charge-offs $), NCLNLSR (NCL rate %), LNATRES (loan loss allowance), P3ASSET (30-89 day past due), P9ASSET (90+ past due), NAESSION (non-accrual loans)

### Capital & Ratios
ROA, ROE, NIMY (net interest margin), EEFFR (efficiency ratio), IDT1CER (Tier 1 capital ratio), IDT1LER (Tier 1 leverage), LNLSDEPR (loans-to-deposits)

### Deposits (granular)
DEPUNA (uninsured deposits), BRO (brokered deposits), DDT (demand deposits), NTRSMMDA (MMDA), NTRTMLG (time deposits >$250K)

### Failure-Specific
FAILDATE, FAILYR, QBFASSET (assets at failure), QBFDEP (deposits at failure), COST (DIF loss), RESTYPE1 (resolution type: PA, PI, PO, IDT)


## Financial Presets

| Preset | Fields | Use Case |
|--------|--------|----------|
| default | ASSET, DEP, NETINC, ROA, ROE, NIM, provision | Quick overview |
| balance_sheet | ASSET, DEP, DEPDOM, EQTOT, SC, LNLSNET, borrowings | Asset/liability structure |
| income | INTINC, EINTEXP, NII, NONII, NONIX, NETINC, provision | Revenue decomposition |
| ratios | ROA, ROE, NIM, efficiency, NCL rate, loan/dep, Tier 1 | Benchmarking |
| loans | Net loans, RE, construction, C&I, consumer, reserves, NCLs | Credit composition |
| deposits | DEP, DDT, MMDA, time, uninsured, brokered, funding cost | Deposit franchise |
| credit_quality | NCLs by type, past-dues, non-accruals, reserves | Asset quality |
| capital | Equity, Tier 1, Total RBC, leverage ratio, RWA | Capital adequacy |
| securities | Total SC, UST, munis, MBS, ABS | Investment portfolio |
| cre | RE loans by type, equity, Tier 1 | CRE concentration |
| past_due | 30-89d, 90+d, non-accrual (total and by RE, C&I) | Delinquency |


## Notable CERT Numbers

| CERT | Institution | Assets |
|------|-------------|--------|
| 628 | JPMorgan Chase Bank NA | $3.75T |
| 3510 | Bank of America NA | $2.64T |
| 7213 | Citibank NA | $1.84T |
| 3511 | Wells Fargo Bank NA | $1.82T |
| 33124 | Goldman Sachs Bank USA | ~$550B |
| 34221 | Morgan Stanley Private Bank NA | ~$200B |
| 24735 | Silicon Valley Bank | Failed 3/10/2023 |
| 59017 | First Republic Bank | Failed 5/1/2023 |


## Code Examples for execute_analysis_script

### Import and basic query
```python
import subprocess, json

def fdic_query(command, args_str=""):
    cmd = f"python GS/data/apis/fdic/fdic_demo.py {command} {args_str} --json"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout else None

# Top 20 largest US banks
largest = fdic_query("largest-banks", "--top 20")

# JPMorgan quarterly financials (last 20 quarters)
jpm = fdic_query("bank-financials", "--cert 628 --quarters 20 --preset default")

# Recent failures
failures = fdic_query("recent-failures", "--top 25")
```

### Direct API access (no subprocess)
```python
import requests

BASE = "https://api.fdic.gov/banks"

def fdic_get(endpoint, filters=None, fields=None, sort_by=None, limit=100):
    params = {"limit": limit}
    if filters:
        params["filters"] = filters
    if fields:
        params["fields"] = fields
    if sort_by:
        params["sort_by"] = sort_by
    resp = requests.get(f"{BASE}/{endpoint}", params=params)
    return resp.json()

# All active banks in California sorted by assets
ca_banks = fdic_get("institutions",
    filters='STALP:CA AND ACTIVE:1',
    fields='CERT,NAME,ASSET,DEP,ROA',
    sort_by='ASSET',
    limit=50)

# JPMorgan last 8 quarters
jpm_fins = fdic_get("financials",
    filters='CERT:628',
    fields='CERT,REPDTE,ASSET,DEP,NETINC,ROA,ROE,NIMY',
    sort_by='REPDTE',
    limit=8)

# Bank failures in 2023
failures_2023 = fdic_get("failures",
    filters='FAILYR:2023',
    fields='NAME,FAILDATE,QBFASSET,QBFDEP,COST,RESTYPE1',
    sort_by='FAILDATE')

# Industry summary for 2024
summary = fdic_get("summary",
    filters='YEAR:2024',
    fields='STNAME,YEAR,ASSET,DEP,NETINC,INTINC,EINTEXP')
```


## Analytical Framework

### When to use FDIC data
- Banking system health monitoring (credit cycle, capital, deposits)
- Individual bank deep dives (balance sheet, income, credit quality)
- Peer comparison across banks
- Historical failure analysis and early-warning indicators
- Deposit flow tracking and funding cost analysis
- CRE concentration screening
- Geographic banking market share analysis

### When NOT to use (use these instead)
- Weekly banking aggregates → FRED H.8 series
- Treasury auctions/debt → TreasuryDirect API
- Federal fiscal data → Treasury Fiscal Data API
- Bank holding company consolidated → FFIEC FR Y-9C (not yet available)
- Public company 10-K/10-Q → SEC EDGAR


## Recipe Commands (CLI)

```
largest-banks [--top N] [--state XX]          Top banks by assets
bank-lookup --name "Wells Fargo"              Fuzzy name search
bank-financials --cert 628 --preset ratios    Time series by preset
recent-failures [--top N]                     Latest failures
failures-by-year                              Historical failure counts
state-summary --year 2024                     State-level aggregates
deposit-mix --cert 628 --quarters 20          Deposit composition
uninsured-screen --min-assets 10000000        Uninsured deposit risk
system-health                                 90 years of banking data
credit-cycle --min-assets 10000000            NCLs, past-dues, provisions
nim-regime --top 50                           NIM across largest banks
capital-distribution --min-assets 1000000     Tier 1 ratios, weakest first
cre-screen --min-assets 1000000               CRE concentration risk
peer-comparison --certs '628,3510,7213'       Side-by-side comparison
```
