# BIS SDMX Statistics API

Complete programmatic access to the Bank for International Settlements statistical data via the SDMX API: 29 datasets, 108 codelists, 7,280 dimension codes covering cross-border banking, total credit, credit-to-GDP gaps, debt service ratios, property prices, effective exchange rates, central bank policy rates, global liquidity, derivatives, and debt securities.

```
Script:     bis_ontology_scraper.py (1,300+ lines)
API Base:   https://stats.bis.org/api/v2
Auth:       None required
Format:     SDMX-JSON
Dependency: pip install requests
Ontology:   ontology/bis_ontology.json (7MB, full metadata)
LBS Index:  ontology/lbs_deep_index.json (1.4MB, cross-border matrix)
```


## What This Data Covers

The BIS collects data that no single national statistics agency can produce: cross-border financial flows, global credit aggregates, and international banking activity. This is what central banks and the IMF use for financial stability monitoring.

- **29 statistical datasets** (dataflows) covering macro-financial aggregates
- **108 unique codelists** with 7,280 dimension codes
- **Quarterly** frequency for most datasets, **monthly** for policy rates and exchange rates
- **Global coverage**: 50 reporting countries for banking, 101 for credit/property, 239 for policy rates
- **History**: Most series back to 1990s or earlier
- **158,856 cross-border banking series** (LBS alone)


## SDMX Key Syntax

```
{DIM1}.{DIM2}.{DIM3}...       Period-separated dimension values
M.US                           Monthly, United States
Q.US+GB+JP                     Quarterly, US OR UK OR Japan (+ = OR within dim)
Q..US                          Quarterly, skip dim 2 (wildcard), US
all                            Everything in the dataflow (can be huge)
```

API URL: `https://stats.bis.org/api/v2/data/dataflow/BIS/{FLOW_ID}/1.0/{KEY}?startPeriod=YYYY&format=sdmx-json`


## Datasets

### Tier 1: Core Analytical Datasets

| Alias | Flow ID | Name | Freq | Dims |
|-------|---------|------|------|------|
| lbs | WS_LBS_D_PUB | Locational Banking Statistics | Q | 12 |
| cbs | WS_CBS_PUB | Consolidated Banking Statistics | Q | 11 |
| credit | WS_TC | Total Credit to Non-Financial Sector | Q | 7 |
| credit-gap | WS_CREDIT_GAP | Credit-to-GDP Gaps | Q | 5 |
| dsr | WS_DSR | Debt Service Ratios | Q | 3 |
| policy-rates | WS_CBPOL | Central Bank Policy Rates | M | 2 |
| eer | WS_EER | Effective Exchange Rates | M | 4 |
| liquidity | WS_GLI | Global Liquidity Indicators | Q | 8 |

### Tier 2: Market Structure & Securities

| Alias | Flow ID | Name | Freq | Dims |
|-------|---------|------|------|------|
| property | WS_SPP | Selected Residential Property Prices | Q | 4 |
| commercial-property | WS_CPP | Commercial Property Prices | Q | 8 |
| etd | WS_XTD_DERIV | Exchange-Traded Derivatives | Q | 6 |
| otc | WS_OTC_DERIV2 | OTC Derivatives Outstanding | H | 14 |
| debt-securities | WS_DEBT_SEC2_PUB | Debt Securities Statistics | Q | 15 |
| cpi | WS_LONG_CPI | Consumer Prices (Long Series) | M | 2 |

### Tier 3: Supplementary

| Flow ID | Name |
|---------|------|
| WS_CB_TA | Central Bank Total Assets |
| WS_DPP | Detailed Residential Property Prices |
| WS_IDS_PUB | International Debt Securities |
| WS_XRU | US Dollar Exchange Rates |
| WS_DER_OTC_TOV | OTC Derivatives Turnover |
| WS_NA_SEC_C3 | National Securities Statistics |
| WS_NA_SEC_DSS | National Debt Securities Statistics |
| BIS_REL_CAL | BIS Release Calendar |
| WS_CPMI_* | Payment System Statistics (6 dataflows) |


## Key Pattern Reference

| Flow | Key Pattern |
|------|-------------|
| WS_LBS_D_PUB | `FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE` |
| WS_CBS_PUB | `FREQ.L_MEASURE.L_REP_CTY.CBS_BANK_TYPE.CBS_BASIS.L_POSITION.L_INSTR.REM_MATURITY.CURR_TYPE_BOOK.L_CP_SECTOR.L_CP_COUNTRY` |
| WS_TC | `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE.TC_ADJUST` |
| WS_CREDIT_GAP | `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.CG_DTYPE` |
| WS_DSR | `FREQ.BORROWERS_CTY.DSR_BORROWERS` |
| WS_CBPOL | `FREQ.REF_AREA` |
| WS_EER | `FREQ.EER_TYPE.EER_BASKET.REF_AREA` |
| WS_GLI | `FREQ.CURR_DENOM.BORROWERS_CTY.BORROWERS_SECTOR.LENDERS_SECTOR.L_POS_TYPE.L_INSTR.UNIT_MEASURE` |
| WS_SPP | `FREQ.REF_AREA.VALUE.UNIT_MEASURE` |
| WS_CPP | `FREQ.REF_AREA.COVERED_AREA.RE_TYPE.RE_VINTAGE.COMPILING_ORG.PRICED_UNIT.ADJUST_CODED` |
| WS_XTD_DERIV | `FREQ.OD_TYPE.OD_RISK_CAT.OD_INSTR.ISSUE_CUR.XD_EXCHANGE` |
| WS_OTC_DERIV2 | `FREQ.DER_TYPE.DER_INSTR.DER_RISK.DER_REP_CTY.DER_SECTOR_CPY.DER_CPC.DER_SECTOR_UDL.DER_CURR_LEG1.DER_CURR_LEG2.DER_ISSUE_MAT.DER_RATING.DER_EX_METHOD.DER_BASIS` |
| WS_DEBT_SEC2_PUB | `FREQ.ISSUER_RES.ISSUER_NAT.ISSUER_BUS_IMM.ISSUER_BUS_ULT.MARKET.ISSUE_TYPE.ISSUE_CUR_GROUP.ISSUE_CUR.ISSUE_OR_MAT.ISSUE_RE_MAT.ISSUE_RATE.ISSUE_RISK.ISSUE_COL.MEASURE` |


## Dimension Code Reference (LBS -- Most Complex Dataset)

### L_MEASURE (CL_STOCK_FLOW)
S=Stocks, F=FX-adjusted change, G=Annual growth, B=Break, R=Revisions

### L_POSITION (CL_L_POSITION)
C=Total claims, L=Total liabilities, D=Cross-border claims, I=International claims, B=Local claims, M=Local liabilities, N=Net positions, S=Foreign Claims, K=Capital/equity, + 7 more

### L_INSTR (CL_L_INSTR)
A=All, G=Loans & deposits, D=Debt securities, B=Credit (loans+debt), V=Derivatives, I=Derivatives+Other, M=Short-term debt, L=Long-term debt, E=RWA, R=Tier 1, S=Tier 2, + 12 more

### L_DENOM (CL_CURRENCY_3POS -- 326 currencies)
TO1=All currencies, USD, EUR, GBP, JPY, CHF, TO3=Foreign currencies, UN9=Unallocated, + 318 others

### L_CURR_TYPE
A=All, D=Domestic, F=Foreign, U=Unclassified

### L_PARENT_CTY (CL_BIS_IF_REF_AREA -- 432 codes)
5J=All parent countries, US, GB, JP, DE, FR, CH, + 426 others. Bank nationality.

### L_REP_BANK_TYPE
A=All banks, D=Domestic, B=Foreign branches, S=Foreign subsidiaries, U=Consortium

### L_REP_CTY (50 reporting countries)
US, GB, JP, DE, FR, CH, HK, SG, CA, AU, AT, BE, BH, BM, BR, BS, CL, CN, CW, CY, DK, ES, FI, GG, GR, ID, IE, IM, IN, IT, JE, KR, KY, LU, MO, MX, MY, NL, NO, PA, PH, PT, RU, SA, SE, TR, TW, ZA. Aggregates: 5A=All, 5C=Euro area.

### L_CP_SECTOR (CL_L_SECTOR)
A=All, B=Banks total, N=Non-banks total, I=Related offices, M=Central banks, F=Non-bank financial, C=Non-financial corps, G=General govt, H=Households, + 11 more

### L_CP_COUNTRY (CL_BIS_IF_REF_AREA -- 432 codes)
All ISO country codes + aggregates. 226 actual counterparty countries in LBS data.

### L_POS_TYPE
N=Cross-border, R=Local, I=Cross-border + Local in FCY, A=All, D=Domestic collateral, F=Foreign collateral


## Other Key Codelists

### CL_AREA (101 codes -- TC, DSR, SPP, EER, CPP)
Major: US, GB, JP, DE, FR, CN, CA, AU, CH, SE, NO, NZ, KR, IN, BR, MX, IT, ES, NL, IE, SG, HK, TW, TH, MY, ID, PL, CZ, HU, RO, RU, TR, ZA, SA
Aggregates: XM=Euro area, 5A=All, 5R=Advanced, 4T=Emerging, G2=G20, XW=World

### CL_TC_BORROWERS (5 codes)
P=Private non-financial, C=Non-financial sector, G=General govt, H=Households, N=Non-financial corps

### CL_CREDT_GAP_DTYPE (3 codes)
A=Actual credit/GDP ratio, B=HP-filter trend, C=Gap (A minus B)

### CL_EER_TYPE / CL_EER_BASKET
R=Real, N=Nominal. B=Broad (64 economies), N=Narrow (27)

### CL_CBS_BASIS (7 codes)
F=Immediate counterparty, U=Guarantor basis, R=Guarantor calculated, O=Outward risk transfers, P=Inward risk transfers, Q=Net risk transfers

### CL_ISSUE_MAT (31 codes -- CBS, Debt Securities)
A=All, U=Up to 1yr, W=Over 1yr, D=1-5yr, F=Over 5yr, K=Long-term, C=Short-term

### OTC Derivatives Dimensions
DER_TYPE: A=Notional, B=Gross positive MV, D=Gross MV, H=Gross credit exposure
DER_RISK: A=All, B=FX, C=Interest rate, D=Equity, H=Commodities, Y=Credit derivatives
DER_SECTOR_CPY: A=All, B=Reporting dealers, C=Other financial, K=CCPs, U=Non-financial


## LBS Worked Examples

```bash
# US banks' total cross-border claims
python bis_ontology_scraper.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.A..N" --start 2015

# US banks' claims on China (non-bank sector)
python bis_ontology_scraper.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.N.CN.N" --start 2015

# UK banks' USD liabilities
python bis_ontology_scraper.py query lbs --key "Q.S.L.A.USD.A.5J.A.GB.A..N" --start 2015

# All reporters' claims on Turkey
python bis_ontology_scraper.py query lbs --key "Q.S.C.A.TO1.A.5J.A.5A.A.TR.N" --start 2015

# Japanese-owned banks' claims globally
python bis_ontology_scraper.py query lbs --key "Q.S.C.A.TO1.A.JP.A..A..N" --start 2015
```


## Usage

### Interactive Mode
```bash
python bis_ontology_scraper.py
```
Menu: Ontology (1-5) + Data Queries (10-18)

### Non-Interactive Mode
```bash
# Pre-built recipes
python bis_ontology_scraper.py policy-rates --countries US+GB+JP --start 2020
python bis_ontology_scraper.py total-credit --countries US+CN --start 2000
python bis_ontology_scraper.py credit-gap --countries US+CN --start 2000
python bis_ontology_scraper.py dsr --countries US+GB+JP --start 2005
python bis_ontology_scraper.py property-prices --countries US+GB+AU --start 2005
python bis_ontology_scraper.py eer --countries US+GB+JP+CN --start 2010
python bis_ontology_scraper.py global-liquidity --start 2010
python bis_ontology_scraper.py lbs --reporter US --position C --start 2015

# Generic query (any dataflow, any key)
python bis_ontology_scraper.py query WS_CBPOL --key "M.US+GB+JP" --start 2020
python bis_ontology_scraper.py query WS_OTC_DERIV2 --key "H.A.A.A..A....TO1.TO1.A.A.3.A" --start 2010
```


## Architecture

```
bis_ontology_scraper.py
├── SDMX Metadata (scrape, explore, deep-index)
├── Data Query Engine
│   ├── data_query() -- fetch + parse SDMX-JSON time series
│   ├── _parse_sdmx_data() -- series extraction
│   └── 8 pre-built recipes + generic query command
├── 15 dataflow aliases
├── Interactive CLI (ontology 1-5, data 10-18)
└── Full argparse (12 subcommands)
```
