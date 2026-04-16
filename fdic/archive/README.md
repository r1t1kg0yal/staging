# FDIC BankFind Suite API Explorer

Complete programmatic access to the FDIC's public banking data -- the canonical dataset used by bank regulators and Treasury officials to monitor the health of the US banking system.

**Base URL:** `https://api.fdic.gov/banks`
**Docs:** `https://api.fdic.gov/banks/docs/`
**Auth:** None required
**Script:** `fdic_demo.py`


## What This Data Covers

The FDIC BankFind Suite exposes Call Report data (FFIEC forms 031/041) filed quarterly by every FDIC-insured institution in the United States. This is the same data that FDIC examiners, the OCC, the Fed, and Treasury use to monitor banking system health.

- **~4,300 active institutions** (every FDIC-insured bank in the US)
- **~10,000+ inactive/historical institutions** (merged, failed, voluntarily closed)
- **Quarterly financial data** going back 60-80+ quarters per institution
- **Industry aggregates from 1934 to present** (91 years of banking history)
- **~80,000+ branch locations** with lat/lng coordinates
- **4,100+ bank failures** with full resolution details and DIF cost estimates


## Endpoints

### /institutions
Financial institution demographics: name, location, charter class, assets, deposits, income, ROA/ROE, regulator. Supports both exact filters and fuzzy text search. This is the entry point -- use it to find a bank's CERT number, which is the primary key across all other endpoints.

### /locations
Branch and office locations with full address, lat/lng, service type (full-service, drive-thru, mobile, etc.), and main office flag. Use for geographic footprint analysis and branch network mapping.

### /financials
The deepest dataset. 1,000+ fields from quarterly Call Reports (RISVIEW system) covering:
- **Balance sheet:** assets, liabilities, equity, securities (HTM vs AFS), borrowings
- **Income statement:** NII, non-interest income/expense, provisions, net income
- **Loan composition:** CRE (by property type), C&I, residential, consumer, credit card, agricultural
- **Credit quality:** net charge-offs (by loan type), past-dues, non-accruals, TDRs, reserves
- **Capital:** Tier 1, Total RBC, Leverage ratio, risk-weighted assets, tangible equity
- **Ratios:** ROA, ROE, NIM, efficiency ratio, loan-to-deposit, NCL rate
- **Liquidity:** brokered deposits, uninsured deposits, FHLB advances, fed funds

Each record keyed by CERT + REPDTE (quarter-end in YYYYMMDD format).

### /summary
Historical aggregate data from 1934 to present, subtotaled by year. Industry-level totals for assets, deposits, income, provisions. Filterable by state and institution type (community bank vs savings institution).

### /failures
Every FDIC bank failure from 1934 to present. Includes resolution type (P&A, payout, open bank assistance), acquiring institution, total deposits/assets at failure, estimated loss to the Deposit Insurance Fund. Supports aggregation by year for trend analysis.

### /history
Structure change events: mergers, acquisitions, name changes, charter conversions, branch openings/closings. Each event has a CHANGECODE. Use to trace corporate lineage or track M&A system-wide.

### /sod
Summary of Deposits: branch-level deposit data published annually. Each record is one branch for one year. Aggregate by CERT for institutional totals; slice by geography for deposit market share analysis.

### /demographics
Community demographics tied to institution reporting. Sparse; primarily useful cross-referenced with CERT and REPDTE.


## Monetary Units

All dollar amounts are in **thousands** ($000s). This is critical to understand:

| API Value | Actual Dollars |
|-----------|---------------|
| ASSET: 3752662000 | $3.75 TRILLION |
| DEP: 438331000 | $438 BILLION |
| NETINC: 8737000 | $8.7 BILLION |
| COST: 23460 | $23.5 MILLION |


## Filter Syntax

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


## Key Field Reference

### Identifiers
| Field | Description |
|-------|-------------|
| CERT | FDIC certificate number (primary key) |
| REPDTE | Report date YYYYMMDD (quarter ends: 0331, 0630, 0930, 1231) |
| UNINUM | FDIC unique number for branches |
| NAME | Legal institution name |
| ACTIVE | 1 = open and insured, 0 = closed |

### Balance Sheet
| Field | Description |
|-------|-------------|
| ASSET | Total assets ($000s) |
| DEP | Total deposits ($000s) |
| DEPDOM | Domestic deposits ($000s) |
| EQTOT | Total equity capital ($000s) |
| SC | Total securities ($000s) |
| LNLSNET | Net loans and leases ($000s) |
| INTBLIB | Interest-bearing liabilities ($000s) |

### Income Statement (YTD cumulative)
| Field | Description |
|-------|-------------|
| INTINC | Total interest income ($000s) |
| EINTEXP | Total interest expense ($000s) |
| NITEFN | Net interest income ($000s) |
| NONII | Non-interest income ($000s) |
| NONIX | Non-interest expense ($000s) |
| NETINC | Net income ($000s) |
| ELNATR | Provision for loan losses ($000s) |

### Loan Composition
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

### Credit Quality
| Field | Description |
|-------|-------------|
| NCLNLS | Net charge-offs ($000s) |
| NCLNLSR | Net charge-off rate (%) |
| NTLNLSR | Net loan loss rate (%) |
| LNATRES | Allowance for loan losses ($000s) |
| P3ASSET | Assets 30-89 days past due ($000s) |
| P9ASSET | Assets 90+ days past due ($000s) |
| NAESSION | Non-accrual loans ($000s) |

### Capital & Ratios
| Field | Description |
|-------|-------------|
| ROA | Return on assets (annualized %) |
| ROE | Return on equity (annualized %) |
| NIMY | Net interest margin (annualized %) |
| EEFFR | Efficiency ratio (%) |
| IDT1CER | Tier 1 capital ratio (%) |
| IDT1LER | Tier 1 leverage ratio (%) |
| LNLSDEPR | Loans-to-deposits ratio (%) |

### Deposits (granular)
| Field | Description |
|-------|-------------|
| DEPUNA | Uninsured deposits ($000s) |
| BRO | Brokered deposits ($000s) |
| DDT | Demand deposits ($000s) |
| NTRSMMDA | Money market deposit accounts ($000s) |
| NTRTMLG | Time deposits >$250K ($000s) |

### Failure-Specific
| Field | Description |
|-------|-------------|
| FAILDATE | Date of failure |
| FAILYR | Year of failure |
| QBFASSET | Total assets at failure ($000s) |
| QBFDEP | Total deposits at failure ($000s) |
| COST | Estimated loss to DIF ($000s) |
| RESTYPE1 | Resolution type (PA, PI, PO, A/A, IDT, etc.) |
| SAVR | Insurance fund (DIF, BIF, SAIF, RTC, FSLIC) |


## Usage

### Interactive Mode

```bash
python fdic_demo.py
```

Launches a menu-driven CLI with all endpoints, recipes, and tools. No arguments needed.

### Non-Interactive Mode (for scripting / LLM tool use)

#### Direct Endpoint Queries

```bash
# Search institutions
python fdic_demo.py institutions --filters 'STALP:NY AND ACTIVE:1' --limit 10
python fdic_demo.py institutions --search 'NAME:JPMorgan' --limit 5

# Financial time series for a specific bank (CERT 628 = JPMorgan Chase Bank)
python fdic_demo.py financials --filters 'CERT:628' --fields CERT,REPDTE,ASSET,DEP --sort-by REPDTE --limit 8

# Recent bank failures
python fdic_demo.py failures --sort-by FAILDATE --sort-order DESC --limit 20

# Historical industry summary
python fdic_demo.py summary --filters 'YEAR:2024' --fields STNAME,YEAR,NETINC,ASSET

# Branch locations with lat/lng
python fdic_demo.py locations --filters 'CERT:628 AND STALP:CA' --fields NAME,OFFNAME,CITY,LATITUDE,LONGITUDE --limit 100

# Summary of deposits
python fdic_demo.py sod --filters 'CERT:628 AND YEAR:2023' --fields NAMEFULL,STALPBR,CITYBR,DEPSUMBR --limit 50
```

#### Recipe Commands

```bash
# Top 20 largest banks in the US
python fdic_demo.py largest-banks --top 20

# Top banks in a specific state
python fdic_demo.py largest-banks --top 10 --state TX

# Look up a bank by name (fuzzy search)
python fdic_demo.py bank-lookup --name "Wells Fargo"

# Quarterly financial time series with preset field selections
python fdic_demo.py bank-financials --cert 628 --quarters 20 --preset default
python fdic_demo.py bank-financials --cert 628 --quarters 40 --preset balance_sheet
python fdic_demo.py bank-financials --cert 628 --quarters 20 --preset income
python fdic_demo.py bank-financials --cert 628 --quarters 20 --preset ratios
python fdic_demo.py bank-financials --cert 628 --quarters 20 --preset loans

# Recent failures
python fdic_demo.py recent-failures --top 25

# Failure aggregates by year
python fdic_demo.py failures-by-year

# State-level banking summary
python fdic_demo.py state-summary --year 2024

# All branches for a bank
python fdic_demo.py branches --cert 628

# Structure change history
python fdic_demo.py bank-history --cert 628

# Deposit rankings by state
python fdic_demo.py deposit-rankings --year 2023 --state CA

# Community banks in a state
python fdic_demo.py community-banks --state TX

# Bulk export to CSV/JSON
python fdic_demo.py bulk-export --endpoint institutions --filters 'ACTIVE:1 AND STALP:CA' --format csv
python fdic_demo.py bulk-export --endpoint financials --filters 'REPDTE:20251231' --max-records 5000 --format json

# Show all field presets
python fdic_demo.py field-catalog
```

#### JSON Output (for programmatic use)

Add `--json` to any recipe command to get raw API JSON:

```bash
python fdic_demo.py bank-financials --cert 33124 --quarters 4 --preset balance_sheet --json
python fdic_demo.py largest-banks --top 5 --json
```


## Financial Presets

The `/financials` endpoint has 1,000+ fields. These presets select commonly needed subsets:

| Preset | Fields | Use Case |
|--------|--------|----------|
| default | ASSET, DEP, NETINC, ROA, ROE, NIM, provision | Quick overview |
| balance_sheet | ASSET, DEP, DEPDOM, EQTOT, SC, LNLSNET, borrowings | Asset/liability structure |
| income | INTINC, EINTEXP, NII, NONII, NONIX, NETINC, provision | Revenue decomposition |
| ratios | ROA, ROE, NIM, efficiency, NCL rate, loan/dep, Tier 1 | Performance benchmarking |
| loans | Net loans, RE, construction, C&I, consumer, credit card, reserves, NCLs | Credit composition |
| deposits | DEP, DEPDOM, DEPFOR, DDT, MMDA, time, uninsured, brokered, funding cost | Deposit franchise analysis |
| credit_quality | NCLs by type (RE, C&I, consumer, credit card), past-dues, non-accruals, reserves | Asset quality deep dive |
| capital | Equity, Tier 1, Total RBC, leverage ratio, RWA, dividends | Capital adequacy |
| securities | Total SC, UST, munis, MBS, ABS | Investment portfolio |
| cre | RE loans by type (construction, non-res, multifamily, resi, ag), equity, Tier 1 | CRE concentration |
| past_due | 30-89 day, 90+ day, non-accrual (total and by RE, C&I) | Delinquency detail |
| minimal | ASSET, DEP, NETINC | Bare minimum |

For any field not in a preset, pass `--fields FIELD1,FIELD2,...` directly. The full field schema is at: `https://api.fdic.gov/banks/docs/risview_properties.yaml`


## Notable CERT Numbers

| CERT | Institution | Notes |
|------|-------------|-------|
| 628 | JPMorgan Chase Bank NA | Largest US bank ($3.75T assets) |
| 3510 | Bank of America NA | #2 ($2.64T) |
| 7213 | Citibank NA | #3 ($1.84T) |
| 3511 | Wells Fargo Bank NA | #4 ($1.82T) |
| 33124 | Goldman Sachs Bank USA | Bank sub only (Marcus, Apple Card, institutional) |
| 34221 | Morgan Stanley Private Bank NA | Bank sub only (wealth management) |
| 6548 | U.S. Bank NA | #5 ($676B) |
| 4297 | Capital One NA | Major consumer bank |
| 9846 | Truist Bank | Regional ($540B) |
| 6384 | PNC Bank NA | Regional ($568B) |
| 24735 | Silicon Valley Bank | Failed 3/10/2023 (ACTIVE:0) |
| 59017 | First Republic Bank | Failed 5/1/2023 (ACTIVE:0) |
| 57053 | Signature Bank | Failed 3/12/2023 (ACTIVE:0) |


## Analytical Framework -- Treasury / Banking System Monitoring

This data is structured for the kinds of questions a chief treasurer or banking system monitor would ask:

### Deposit Flows & Funding
- Where are deposits moving across institutions and geographies?
- What's happening to uninsured deposit concentration? (DEPUNA)
- How much brokered / hot money is in the system? (BRO)
- What's the cost of funding? (EDEPDOM, INTBLIB)

### Credit Conditions
- System-wide loan growth by category?
- NCL rates by loan type (CRE, C&I, consumer)?
- CRE concentration risk by institution?
- Provision expense trends (leading indicator)?

### Interest Rate Risk
- NIM compression/expansion across the industry?
- Securities portfolio composition (HTM vs AFS)?
- Unrealized gains/losses in securities portfolios?

### Capital & Systemic Health
- Tier 1 capital ratios across the system?
- Which institutions are thinly capitalized?
- Historical failure patterns and early-warning signals?

### Industry Structure
- M&A pace and branch consolidation trends?
- De novo bank formation rates?
- Community bank vs large bank divergence?


## Complementary Data Sources

The FDIC data covers the insured banking system comprehensively. For a complete treasury monitoring picture, pair with:

| Source | What It Adds | Already in Scraper Suite? |
|--------|-------------|--------------------------|
| FRED (Fed) | Macro rates, H.8 weekly banking aggregates, money supply | Yes (fred_puller.py) |
| TreasuryDirect | Govt securities auctions, outstanding debt, yield curves | Yes (treasurydirect_scraper.py) |
| Treasury Fiscal Data | Federal receipts/outlays, debt to the penny | Yes (fiscal_data_api.py) |
| FFIEC (FR Y-9C) | Bank holding company consolidated data | Not yet |
| SEC EDGAR | 10-K/10-Q for holding company segment detail | Not yet |
| Fed H.8 | Weekly aggregate banking data (faster than quarterly FDIC) | Via FRED |


## Persona: Global Treasurer

A treasurer monitors deposit flows, funding costs, liquidity risk, and deposit franchise health.

### Worked Examples

```bash
# What does JPMorgan's deposit base look like? Demand vs MMDA vs time vs brokered vs uninsured?
python fdic_demo.py deposit-mix --cert 628 --quarters 20

# Which large banks have the highest uninsured deposit concentration?
# (This is what killed SVB: $175B total deposits, ~$152B uninsured)
python fdic_demo.py uninsured-screen --min-assets 10000000

# How have system-wide deposits, NII, and funding costs evolved over 20 years?
python fdic_demo.py system-deposits --years 20

# Compare funding costs across the Big 5
python fdic_demo.py funding-costs --certs '628,3510,7213,3511,33124'

# Who dominates deposits in California?
python fdic_demo.py geo-deposits --state CA --year 2023

# Compare deposit franchise structure across peers (detailed deposit breakdown)
python fdic_demo.py peer-comparison --certs '628,3510,7213,3511,33124' --preset deposits
```

### Key Fields for Treasurers

| Field | What It Tells You |
|-------|------------------|
| DEP, DEPDOM, DEPFOR | Total / domestic / foreign deposits |
| DDT | Demand deposits (non-interest-bearing, sticky, zero-cost) |
| NTRSMMDA | Money market deposit accounts (rate-sensitive) |
| NTRTMLG | Large time deposits >$250K (hot money, rate-sensitive) |
| NTRSOTH | Other savings deposits |
| DEPUNA | Uninsured deposits (the SVB/Signature vulnerability metric) |
| BRO | Brokered deposits (wholesale funding, flightiest money) |
| EDEPDOM | Interest expense on domestic deposits (cost of funding) |
| NIMY | Net interest margin (spread between earning yield and funding cost) |


## Persona: Bank Macro Analyst

A macro analyst studies the banking system as a leading economic indicator -- credit cycles, failure waves, capital builds, NIM regimes, and systemic stress.

### Worked Examples

```bash
# 90 years of US banking: assets, deposits, income, provisions (1934-present)
python fdic_demo.py system-health

# Every failure wave in history: count and total assets by year
# Shows S&L crisis (1980s-90s), GFC (2008-12), regional bank crisis (2023)
python fdic_demo.py failure-waves

# Credit cycle right now: NCL rates, past-dues, provisions across top banks
python fdic_demo.py credit-cycle --min-assets 10000000 --repdte 20251231

# What does the NIM regime look like across the 50 largest banks?
python fdic_demo.py nim-regime --top 50 --repdte 20251231

# Capital distribution: who has the thinnest buffers?
# Sorted ascending by Tier 1 ratio -- weakest capitalized first
python fdic_demo.py capital-distribution --min-assets 1000000 --repdte 20251231

# Recent failures with full resolution detail
python fdic_demo.py recent-failures --top 25

# State-level comparison: which states have the most stressed banking sectors?
python fdic_demo.py state-summary --year 2024
```

### Key Fields for Macro Analysts

| Field | What It Tells You |
|-------|------------------|
| NCLNLS, NCLNLSR | Net charge-offs ($ and rate) -- realized credit losses |
| ELNATR | Provision expense -- forward-looking loss reserving |
| LNATRES | Allowance for loan losses -- cumulative reserve buffer |
| P3ASSET, P9ASSET | 30-89 day and 90+ day past-due assets (early-warning) |
| NAESSION | Non-accrual loans (worst credit quality bucket) |
| IDT1CER | Tier 1 capital ratio (buffer against losses) |
| RBCRWAJ | Total risk-based capital ratio |
| NIMY | Net interest margin (bank profitability proxy) |
| NIM | Net interest margin from /summary (system aggregate) |


## Persona: Balance Sheet Economist

A balance sheet economist studies loan composition, CRE concentration, reserve adequacy, securities portfolios, and structural shifts in bank intermediation.

### Worked Examples

```bash
# CRE concentration screen: which banks are most exposed to commercial real estate?
# Regulators flag CRE > 300% of total capital as high concentration
python fdic_demo.py cre-screen --min-assets 1000000 --repdte 20251231

# How has Goldman Sachs Bank's loan book evolved? (loan growth by category)
python fdic_demo.py loan-growth --cert 33124 --quarters 40

# Reserve adequacy: are banks holding enough reserves against their loan losses?
python fdic_demo.py reserve-adequacy --min-assets 10000000 --repdte 20251231

# Securities portfolio: UST vs muni vs MBS vs ABS for a specific bank
python fdic_demo.py securities-portfolio --cert 628 --quarters 20

# Securities portfolio: cross-bank comparison of the top 50
python fdic_demo.py securities-portfolio --quarters 20

# Full peer comparison on any preset
python fdic_demo.py peer-comparison --certs '628,3510,7213,3511,33124,34221' --preset cre
python fdic_demo.py peer-comparison --certs '628,3510,7213,3511,33124,34221' --preset credit_quality
python fdic_demo.py peer-comparison --certs '628,3510,7213,3511,33124,34221' --preset capital

# Past-due and non-accrual detail by loan type (RE, C&I) for a bank
python fdic_demo.py past-due-detail --cert 628 --quarters 12

# Community banks in Texas: small bank health check
python fdic_demo.py community-banks --state TX
```

### Key Fields for Balance Sheet Economists

| Field | What It Tells You |
|-------|------------------|
| LNRE | Total real estate loans |
| LNRECONS | Construction & land development (most cyclical CRE) |
| LNRENRES | Non-residential CRE (office, retail, industrial) |
| LNREMULT | Multifamily residential (apartments) |
| LNRERES | 1-4 family residential mortgage |
| LNREAG | Agricultural real estate |
| LNCI | Commercial & industrial loans |
| LNCRCD | Credit card loans |
| LNCONOTH | Other consumer loans |
| LNATRES | Allowance / total loans = reserve coverage ratio |
| SC, SCUS, SCMUNI, SCMBS | Securities: total, UST, muni, MBS |
| EQTOT, EQPP | Total equity, perpetual preferred |
| P3RE, P9RE, P3CI, P9CI | Past-due by loan type (30-89d, 90+d) |
| NTRE, NTCI, NTCON, NTCRCD | NCLs by loan type (RE, C&I, consumer, credit card) |


## Architecture

```
fdic_demo.py
  |
  +-- Module docstring: full API documentation, field reference, filter syntax
  |
  +-- Field presets: curated field sets per endpoint for common use cases
  |
  +-- HTTP layer:
  |     _get()      Single API request with error handling
  |     _get_all()  Auto-paginating bulk fetcher with progress
  |
  +-- Display layer:
  |     _print_table()   ASCII table renderer
  |     _prompt_*()      Interactive input helpers
  |     _display_*()     Response formatting + optional CSV/JSON export
  |
  +-- Interactive commands (1-8): full query builders per endpoint
  |     Each prompts for filters, fields (with preset selection), sort, limit
  |
  +-- General recipes (10-20): largest-banks, bank-lookup, bank-financials,
  |     recent-failures, failures-by-year, state-summary, branches,
  |     bank-history, deposit-rankings, community-banks, bulk-export
  |
  +-- Treasurer recipes (40-44): deposit-mix, uninsured-screen,
  |     system-deposits, funding-costs, geo-deposits
  |
  +-- Macro analyst recipes (50-54): system-health, failure-waves,
  |     credit-cycle, nim-regime, capital-distribution
  |
  +-- Balance sheet economist recipes (60-65): cre-screen, loan-growth,
  |     reserve-adequacy, securities-portfolio, peer-comparison, past-due-detail
  |
  +-- Tools (90+): raw query builder, field catalog
  |
  +-- Non-interactive CLI: full argparse mirror of all commands
  |     Supports --json for raw output, --export for file export
  |
  +-- main(): routes to interactive or non-interactive based on sys.argv
```
