# BIS SDMX Statistics API

Script: `GS/data/apis/bis/bis.py`
Base URL: `https://stats.bis.org/api/v2`
Auth: None required
Rate limit: ~0.5s between calls (polite usage)
Dependencies: `requests`
Ontology: `ontology/bis_ontology.json` (7MB, 29 dataflows, 108 codelists, 7,280 codes)
LBS Index: `ontology/lbs_deep_index.json` (1.4MB, cross-border matrix)


## Triggers

Use for: cross-border banking exposure (LBS/CBS), total credit-to-GDP, credit-to-GDP gaps, debt service ratios, central bank policy rates, effective exchange rates (REER/NEER), residential/commercial property prices, global dollar/euro/yen liquidity, OTC/exchange-traded derivatives, international debt securities, CPI long series, financial stability early-warning.

Not for: US high-frequency data (FRED), individual US bank data (FDIC), company fundamentals (SEC EDGAR), US fiscal data (Treasury), OIS swap volumes (DTCC), futures positioning (CFTC), event probabilities (prediction markets), intraday or daily data (BIS is mostly quarterly/monthly with 3-6 month lag).


## Data Catalog

### SDMX Key Syntax

```
{DIM1}.{DIM2}.{DIM3}...       Period-separated dimension values
M.US                           Monthly, United States
Q.US+GB+JP                     Quarterly, US OR UK OR Japan (+ = OR within dim)
Q..US                          Quarterly, skip dim 2 (wildcard), US
all                            Everything in the dataflow (can be huge)
```

`+` = OR within dimension. `.` separates dimensions. `..` skips (wildcards) a dimension.

API URL pattern: `https://stats.bis.org/api/v2/data/dataflow/BIS/{FLOW_ID}/1.0/{KEY}?startPeriod={YYYY}&format=sdmx-json`

### Dataflow Aliases

| Alias | Flow ID | Name |
|-------|---------|------|
| `lbs` | WS_LBS_D_PUB | Locational Banking Statistics |
| `cbs` | WS_CBS_PUB | Consolidated Banking Statistics |
| `credit` | WS_TC | Total Credit to Non-Financial Sector |
| `credit-gap` | WS_CREDIT_GAP | Credit-to-GDP Gaps |
| `dsr` | WS_DSR | Debt Service Ratios |
| `property` | WS_SPP | Selected Residential Property Prices |
| `commercial-property` | WS_CPP | Commercial Property Prices |
| `eer` | WS_EER | Effective Exchange Rates |
| `policy-rates` | WS_CBPOL | Central Bank Policy Rates |
| `etd` | WS_XTD_DERIV | Exchange-Traded Derivatives |
| `otc` | WS_OTC_DERIV2 | OTC Derivatives Outstanding |
| `liquidity` | WS_GLI | Global Liquidity Indicators |
| `debt-securities` | WS_DEBT_SEC2_PUB | Debt Securities Statistics |
| `fx` | WS_EER | Effective Exchange Rates (alias) |
| `cpi` | WS_LONG_CPI | Consumer Prices (Long Series) |

### Datasets

#### Tier 1: Core Analytical Datasets

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

#### Tier 2: Market Structure & Securities

| Alias | Flow ID | Name | Freq | Dims |
|-------|---------|------|------|------|
| property | WS_SPP | Selected Residential Property Prices | Q | 4 |
| commercial-property | WS_CPP | Commercial Property Prices | Q | 8 |
| etd | WS_XTD_DERIV | Exchange-Traded Derivatives | Q | 6 |
| otc | WS_OTC_DERIV2 | OTC Derivatives Outstanding | H | 14 |
| debt-securities | WS_DEBT_SEC2_PUB | Debt Securities Statistics | Q | 15 |
| cpi | WS_LONG_CPI | Consumer Prices (Long Series) | M | 2 |

#### Tier 3: Supplementary

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

### Full Dataflow Reference

#### WS_LBS_D_PUB -- Locational Banking Statistics

**Key:** `FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE`

158,856 total series. 50 reporting countries. 226 counterparty countries.

| Pos | Dim | Codelist | Codes |
|-----|-----|----------|-------|
| 1 | FREQ | CL_FREQ | Q=Quarterly, M=Monthly, A=Annual |
| 2 | L_MEASURE | CL_STOCK_FLOW | S=Stocks, F=FX-adjusted change, G=Annual growth, B=Break, R=Revisions |
| 3 | L_POSITION | CL_L_POSITION | **C=Total claims, L=Total liabilities**, D=Cross-border claims, B=Local claims, I=International claims, N=Net positions, K=Capital/equity, S=Foreign Claims, M=Local liabilities, + 7 more |
| 4 | L_INSTR | CL_L_INSTR | **A=All instruments, G=Loans & deposits, D=Debt securities, B=Credit (loans+debt)**, I=Derivatives+Other, V=Derivatives, M=Short-term debt, L=Long-term debt, E=RWA, R=Tier 1, S=Tier 2, + 12 more |
| 5 | L_DENOM | CL_CURRENCY_3POS | **USD, EUR, GBP, JPY, CHF, TO1=All currencies, TO3=Foreign currencies, UN9=Unallocated** + 318 others |
| 6 | L_CURR_TYPE | CL_L_CURR_TYPE | A=All currencies, D=Domestic, F=Foreign, U=Unclassified |
| 7 | L_PARENT_CTY | CL_BIS_IF_REF_AREA | **5J=All parent countries**, US, GB, JP, DE, FR, CH, + 426 others |
| 8 | L_REP_BANK_TYPE | CL_L_BANK_TYPE | **A=All banks**, D=Domestic, B=Foreign branches, S=Foreign subsidiaries, U=Consortium |
| 9 | L_REP_CTY | CL_BIS_IF_REF_AREA | 50 reporters: US, GB, JP, DE, FR, CH, HK, SG, CA, AU, AT, BE, BH, BM, BR, BS, CL, CN, CW, CY, DK, ES, FI, GG, GR, ID, IE, IM, IN, IT, JE, KR, KY, LU, MO, MX, MY, NL, NO, PA, PH, PT, RU, SA, SE, TR, TW, ZA. Aggregates: 5A=All, 5C=Euro area |
| 10 | L_CP_SECTOR | CL_L_SECTOR | **A=All sectors, B=Banks total, N=Non-banks total**, I=Related offices, M=Central banks, F=Non-bank financial, C=Non-financial corps, G=General govt, H=Households, + 11 more |
| 11 | L_CP_COUNTRY | CL_BIS_IF_REF_AREA | 226 ISO codes + aggregates. 5J=All countries, 5A=All reporting, 5C=Euro area |
| 12 | L_POS_TYPE | CL_L_POS_TYPE | **N=Cross-border, R=Local, I=Cross-border+Local in FCY, A=All**, D=Domestic collateral, F=Foreign collateral |

#### WS_CBS_PUB -- Consolidated Banking Statistics

**Key:** `FREQ.L_MEASURE.L_REP_CTY.CBS_BANK_TYPE.CBS_BASIS.L_POSITION.L_INSTR.REM_MATURITY.CURR_TYPE_BOOK.L_CP_SECTOR.L_CP_COUNTRY`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 5 | CBS_BASIS | F=Immediate counterparty, U=Guarantor basis, R=Guarantor calculated |
| 8 | REM_MATURITY | A=All, U=Up to 1yr, W=Over 1yr, D=1-5yr, F=Over 5yr |
| 9 | CURR_TYPE_BOOK | TO1=All, USD, EUR, GBP, JPY + 326 currencies |

#### WS_TC -- Total Credit to Non-Financial Sector

**Key:** `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE.TC_ADJUST`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | BORROWERS_CTY | US, GB, JP, DE, FR, CN, CA, AU + 93 others. XM=Euro area, 5A=All, G2=G20 |
| 3 | TC_BORROWERS | **P=Private non-financial, C=Non-financial sector, G=General govt, H=Households, N=Non-financial corps** |
| 4 | TC_LENDERS | A=All sectors, B=Banks domestic |
| 5 | VALUATION | M=Market value, N=Nominal |
| 6 | UNIT_TYPE | XDC=Domestic currency, USD=US dollar, 770=% of GDP + 1092 others |
| 7 | TC_ADJUST | A=Adjusted for breaks, 0=Non-seasonally adjusted, 1=Seasonally adjusted |

#### WS_CREDIT_GAP -- Credit-to-GDP Gaps

**Key:** `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.CG_DTYPE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | BORROWERS_CTY | 239 countries/aggregates |
| 5 | CG_DTYPE | **A=Credit-to-GDP ratios (actual), B=Credit-to-GDP trend (HP filter), C=Credit-to-GDP gaps (actual minus trend)** |

#### WS_DSR -- Debt Service Ratios

**Key:** `FREQ.BORROWERS_CTY.DSR_BORROWERS`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | BORROWERS_CTY | 101 countries |
| 3 | DSR_BORROWERS | P=Private non-financial, H=Households, N=Non-financial corps, C=Non-financial sector, G=General govt |

#### WS_CBPOL -- Central Bank Policy Rates

**Key:** `FREQ.REF_AREA`

239 central banks. Monthly.

#### WS_EER -- Effective Exchange Rates

**Key:** `FREQ.EER_TYPE.EER_BASKET.REF_AREA`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | EER_TYPE | **R=Real, N=Nominal** |
| 3 | EER_BASKET | **B=Broad (64 economies), N=Narrow (27 economies)** |
| 4 | REF_AREA | 101 countries |

#### WS_GLI -- Global Liquidity Indicators

**Key:** `FREQ.CURR_DENOM.BORROWERS_CTY.BORROWERS_SECTOR.LENDERS_SECTOR.L_POS_TYPE.L_INSTR.UNIT_MEASURE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | CURR_DENOM | USD, EUR, JPY + 326 currencies |
| 3 | BORROWERS_CTY | 432 countries |
| 4-5 | SECTORS | A=All, B=Banks, N=Non-banks |
| 6 | L_POS_TYPE | N=Cross-border, R=Local, I=Cross-border+Local FCY |
| 7 | L_INSTR | A=All, G=Loans, D=Debt securities, B=Credit |

#### WS_SPP -- Selected Residential Property Prices

**Key:** `FREQ.REF_AREA.VALUE.UNIT_MEASURE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 3 | VALUE | **R=Real, N=Nominal** |

#### WS_CPP -- Commercial Property Prices

**Key:** `FREQ.REF_AREA.COVERED_AREA.RE_TYPE.RE_VINTAGE.COMPILING_ORG.PRICED_UNIT.ADJUST_CODED`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 3 | COVERED_AREA | 0=Whole country, 2=Capital city, 4=Big cities, 9=Urban |
| 4 | RE_TYPE | **A=Commercial property, B=Office, C=Retail**, G=Industrial, 0=All properties, 1=All dwellings |

#### WS_XTD_DERIV -- Exchange-Traded Derivatives

**Key:** `FREQ.OD_TYPE.OD_RISK_CAT.OD_INSTR.ISSUE_CUR.XD_EXCHANGE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | OD_TYPE | A=Notional outstanding, B=Gross positive MV, K=Turnover, L=Num contracts, U=Turnover daily avg |
| 3 | OD_RISK_CAT | A=All, B=FX, C=Interest rate, D=Equity, H=All commodities, Y=Credit derivatives |
| 4 | OD_INSTR | A=All, C=Forwards+swaps, H=Options total, T=Futures |
| 5 | ISSUE_CUR | 131 currencies |
| 6 | XD_EXCHANGE | 432 exchanges/countries |

#### WS_OTC_DERIV2 -- OTC Derivatives Outstanding

**Key:** `FREQ.DER_TYPE.DER_INSTR.DER_RISK.DER_REP_CTY.DER_SECTOR_CPY.DER_CPC.DER_SECTOR_UDL.DER_CURR_LEG1.DER_CURR_LEG2.DER_ISSUE_MAT.DER_RATING.DER_EX_METHOD.DER_BASIS`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | DER_TYPE | A=Notional, B=Gross positive MV, D=Gross MV, H=Gross credit exposure |
| 3 | DER_INSTR | A=All, B=FX incl gold, C=Forwards+swaps, G=Interest rate swaps, S=CDS + 30 more |
| 4 | DER_RISK | A=All, B=FX, C=Interest rate, D=Equity, F=Precious metals, H=All commodities, Y=Credit |
| 6 | DER_SECTOR_CPY | A=All, B=Reporting dealers, C=Other financial, K=CCPs, R=Other customers, U=Non-financial |

#### WS_DEBT_SEC2_PUB -- Debt Securities Statistics

**Key:** `FREQ.ISSUER_RES.ISSUER_NAT.ISSUER_BUS_IMM.ISSUER_BUS_ULT.MARKET.ISSUE_TYPE.ISSUE_CUR_GROUP.ISSUE_CUR.ISSUE_OR_MAT.ISSUE_RE_MAT.ISSUE_RATE.ISSUE_RISK.ISSUE_COL.MEASURE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 6 | MARKET | 1=All markets, A=Domestic, C=International |
| 12 | ISSUE_RATE | A=All, C=Fixed, E=Variable, M=Inflation-linked, G=Equity-related |
| 15 | MEASURE | **I=Outstanding, G=Net issues, C=Gross issues, E=Redemptions**, A=Announced, N=Avg original maturity |

#### Other Dataflows

| Flow ID | Name | Key Pattern |
|---------|------|-------------|
| WS_CB_TA | Central bank total assets | FREQ.REF_AREA.UNIT_MEASURE |
| WS_LONG_CPI | Consumer prices (long) | FREQ.REF_AREA.UNIT_MEASURE |
| WS_DPP | Detailed residential property | FREQ.REF_AREA.COVERED_AREA.RE_TYPE.RE_VINTAGE.COMPILING_ORG.PRICED_UNIT.ADJUST_CODED |
| WS_IDS_PUB | International debt securities | Same as DEBT_SEC2_PUB |
| WS_XRU | USD exchange rates | FREQ.CURRENCY.TIME_PERIOD |
| WS_DER_OTC_TOV | OTC derivatives turnover | Same dims as OTC_DERIV2 |
| WS_NA_SEC_C3 / WS_NA_SEC_DSS | National securities stats | Complex multi-dim |
| BIS_REL_CAL | Release calendar | FREQ.CATEGORY.RELEASE_TYPE |
| WS_CPMI_* (6 flows) | Payment system statistics | Specialized CPMI dims |

### Shared Dimension Codelists

**CL_AREA (101 codes)** -- Used by: TC, DSR, SPP, EER, CPP

Major: US, GB, JP, DE, FR, CN, CA, AU, CH, SE, NO, NZ, KR, IN, BR, MX, IT, ES, NL, IE, SG, HK, TW, TH, MY, ID, PH, PL, CZ, HU, RO, RU, TR, ZA, SA, AE, IL, AR, CL, CO, PE, EG, NG, PK

Aggregates: XM=Euro area, 5A=All reporting, 5R=Advanced, 4T=Emerging, G2=G20, XW=World, 1X=ECB

**CL_BIS_IF_REF_AREA (432 codes)** -- Used by: LBS, CBS, GLI, XTD, OTC, DEBT_SEC

All 226 ISO country codes + offshore centers, aggregates, defunct states, institutional groupings. Superset of CL_AREA.

**CL_BIS_GL_REF_AREA (239 codes)** -- Used by: CBPOL, CREDIT_GAP

239 countries and aggregates with central bank coverage.

### LBS Query Construction Guide

**Key pattern:**
```
FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE
```

**1. FREQ** -- Always `Q` for quarterly LBS data.

**2. L_MEASURE** -- What type of number?
- `S` = Amounts outstanding (stocks) -- most common
- `F` = FX and break-adjusted change (preferred for flows)
- `G` = Annual growth rate

**3. L_POSITION** -- Claims or liabilities?
- `C` = Total claims (what banks are OWED)
- `L` = Total liabilities (what banks OWE)
- `D` = Cross-border claims only
- `I` = International claims (cross-border + local in foreign currency)
- `N` = Net positions (claims minus liabilities)

**4. L_INSTR** -- What financial instrument?
- `A` = All instruments
- `G` = Loans and deposits
- `D` = Debt securities
- `B` = Credit (loans + debt securities)
- `V` = Derivatives
- `I` = Derivatives + Other

**5. L_DENOM** -- Currency denomination?
- `TO1` = All currencies (total)
- `USD` = US dollar, `EUR` = Euro, `GBP` = Sterling, `JPY` = Yen, `CHF` = Swiss franc
- `TO3` = Foreign currencies only
- `UN9` = Unallocated

**6. L_CURR_TYPE** -- Domestic or foreign?
- `A` = All (domestic + foreign)
- `D` = Domestic currency (of reporting country)
- `F` = Foreign currency

**7. L_PARENT_CTY** -- Bank nationality (parent HQ country)
- `5J` = All parent countries (most common)
- `US`, `GB`, `JP`, etc. = Only banks with parent HQ in that country

**8. L_REP_BANK_TYPE** -- Type of reporting bank
- `A` = All banks (most common)
- `D` = Domestic banks only
- `B` = Foreign branches only
- `S` = Foreign subsidiaries only

**9. L_REP_CTY** -- Reporting country (where bank physically operates)
- 50 BIS reporters: US, GB, JP, DE, FR, CH, HK, SG, CA, AU, AT, BE, BH, BM, BR, BS, CL, CN, CW, CY, DK, ES, FI, GG, GR, ID, IE, IM, IN, IT, JE, KR, KY, LU, MO, MX, MY, NL, NO, PA, PH, PT, RU, SA, SE, TR, TW, ZA
- Aggregates: `5A`=All reporting countries, `5C`=Euro area

**10. L_CP_SECTOR** -- Counterparty sector
- `A` = All sectors
- `B` = Banks total
- `N` = Non-banks total
- `I` = Related offices (intra-group)
- `M` = Central banks
- `F` = Non-bank financial institutions
- `C` = Non-financial corporations
- `G` = General government
- `H` = Households

**11. L_CP_COUNTRY** -- Counterparty country (who banks lend to / borrow from)
- Any of 432 countries in CL_BIS_IF_REF_AREA
- Key aggregates: `5J`=All countries, `5A`=All reporting, `5C`=Euro area

**12. L_POS_TYPE** -- Position type
- `N` = Cross-border (pure international exposure)
- `R` = Local (booked in counterparty's country)
- `I` = Cross-border + Local in foreign currency
- `A` = All

### LBS Worked Examples

```
# US banks, total claims, all instruments, all currencies, cross-border
Q.S.C.A.TO1.A.5J.A.US.A..N

# US banks, claims on Chinese non-banks, cross-border
Q.S.C.A.TO1.A.5J.A.US.N.CN.N

# UK banks, liabilities, loans+deposits, USD, to banks, cross-border
Q.S.L.G.USD.A.5J.A.GB.B..N

# Japanese-owned banks (wherever located), claims on US, loans only
Q.S.C.G.TO1.A.JP.A..A.US.N

# All reporting countries, claims on Turkey, all instruments
Q.S.C.A.TO1.A.5J.A.5A.A.TR.N

# Swiss banks, net position vis-a-vis Cayman Islands
Q.S.N.A.TO1.A.5J.A.CH.A.KY.N

# Annual growth in US banks' cross-border claims
Q.G.C.A.TO1.A.5J.A.US.A..N

# FX-adjusted changes (flows) in UK banks' liabilities
Q.F.L.A.TO1.A.5J.A.GB.A..N
```

### Key Dimension Quick Reference

| Category | Codes |
|----------|-------|
| Positions (L_POSITION) | C=Claims, L=Liabilities, D=Cross-border claims, I=International claims, N=Net |
| Instruments (L_INSTR) | A=All, G=Loans+deposits, D=Debt securities, B=Credit, V=Derivatives |
| Currencies (L_DENOM) | TO1=All, USD, EUR, GBP, JPY, CHF, TO3=Foreign only |
| Sectors (L_CP_SECTOR) | A=All, B=Banks, N=Non-banks, F=Non-bank financial, C=Non-financial corps, G=Govt, H=Households |
| Position Types (L_POS_TYPE) | N=Cross-border, R=Local, I=Cross-border+Local FCY, A=All |
| Measures (L_MEASURE) | S=Stocks, F=FX-adjusted flows, G=Annual growth |
| Bank Types (L_REP_BANK_TYPE) | A=All, D=Domestic, B=Foreign branches, S=Foreign subsidiaries |
| Credit Gap Types (CG_DTYPE) | A=Actual ratio, B=HP-filter trend, C=Gap (A minus B) |
| TC Borrowers | P=Private non-financial, C=Non-financial sector, G=Govt, H=Households, N=Non-financial corps |
| EER Types | R=Real, N=Nominal. Baskets: B=Broad (64), N=Narrow (27) |
| OTC DER_TYPE | A=Notional, B=Gross positive MV, D=Gross MV, H=Gross credit exposure |
| OTC DER_RISK | A=All, B=FX, C=Interest rate, D=Equity, H=Commodities, Y=Credit |
| OTC DER_SECTOR_CPY | A=All, B=Reporting dealers, C=Other financial, K=CCPs, U=Non-financial |
| CBS Basis | F=Immediate counterparty, U=Guarantor basis, R=Guarantor calculated |
| Remaining Maturity | A=All, U=Up to 1yr, W=Over 1yr, D=1-5yr, F=Over 5yr |
| Credit-to-GDP Gap | < -10pp deleveraging, 0-5pp neutral, 5-10pp watch, >10pp warning, >20pp extreme |


## Output Schema

### Series Object (returned by all data commands)

Each command returns a list of series dicts:

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Period-separated dimension values (e.g. `Q.S.C.A.TO1.A.5J.A.US.A..N`) |
| `dimensions` | dict | `{dim_id: {id: str, name: str}}` for each dimension |
| `attributes` | dict | `{attr_id: str}` series-level attributes |
| `observations` | dict | `{period: value}` time series data (e.g. `{"2024-Q1": 1234.56}`) |

### Saved Output Files

All data commands auto-save to `GS/data/apis/bis/data/` as JSON:

| Command | Filename Pattern |
|---------|-----------------|
| `policy-rates` | `policy_rates_{timestamp}.json` |
| `total-credit` | `total_credit_{timestamp}.json` |
| `credit-gap` | `credit_gap_{timestamp}.json` |
| `dsr` | `dsr_{timestamp}.json` |
| `property-prices` | `property_prices_{timestamp}.json` |
| `eer` | `eer_{timestamp}.json` |
| `global-liquidity` | `global_liquidity_{timestamp}.json` |
| `lbs` | `lbs_{reporter}_{position}_{timestamp}.json` |
| `query` | `query_{flow_id}_{timestamp}.json` |


## CLI Recipes

### Ontology & Metadata

```bash
# Scrape full BIS ontology (29 dataflows, 108 codelists -> ontology/bis_ontology.json)
python bis.py scrape
python bis.py scrape --output custom_path.json
python bis.py scrape --skip-existing

# Interactively explore ontology (list flows, inspect dimensions, search codelists)
python bis.py explore
python bis.py explore --input custom_path.json

# Build deep LBS cross-border index (50 reporters x counterparties -> ontology/lbs_deep_index.json)
python bis.py deep-index
python bis.py deep-index --output custom_path.json

# Full pipeline: scrape then deep-index (use interactive menu option 5)
python bis.py
# -> select option 5
```

### Central Bank Policy Rates

```bash
python bis.py policy-rates
python bis.py policy-rates --countries US+GB+JP+DE+CH+CA+AU+SE+NO+NZ
python bis.py policy-rates --countries US+GB+JP --start 2020
python bis.py policy-rates --countries US+GB+JP+DE+FR+CN+CA+AU+SE+NO+NZ+KR+IN+BR+MX+ZA --start 2015
python bis.py policy-rates --start 2000
```

PRISM receives: monthly policy rate for each country, time series from start period to latest.

### Total Credit to Non-Financial Sector

```bash
python bis.py total-credit
python bis.py total-credit --countries US+GB+JP+DE+FR+CN+CA+AU
python bis.py total-credit --countries US+CN+GB+JP --start 2010
python bis.py total-credit --countries US --start 2000
python bis.py total-credit --countries XM+US+CN+JP --start 2005
```

PRISM receives: quarterly total credit (domestic currency, nominal), private non-financial sector, break-adjusted.

### Credit-to-GDP Gaps

```bash
python bis.py credit-gap
python bis.py credit-gap --countries US+GB+JP+DE+FR+CN+CA+AU
python bis.py credit-gap --countries US+CN --start 2000
python bis.py credit-gap --countries US+GB+JP+DE+FR+CN+CA+AU+KR+IN+BR+MX --start 1995
python bis.py credit-gap --start 2000
```

PRISM receives: quarterly credit-to-GDP gap series (actual, trend, gap values). Gap >10pp = BIS warning threshold.

### Debt Service Ratios

```bash
python bis.py dsr
python bis.py dsr --countries US+GB+JP+DE+FR+CN+CA+AU
python bis.py dsr --countries US+GB+JP+DE --start 2005
python bis.py dsr --countries US --start 2000
```

PRISM receives: quarterly private non-financial sector DSR (share of income devoted to debt service).

### Residential Property Prices

```bash
python bis.py property-prices
python bis.py property-prices --countries US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR
python bis.py property-prices --countries US+GB+CN+AU+CA --start 2005
python bis.py property-prices --start 2000
```

PRISM receives: quarterly nominal property price index for each country.

### Effective Exchange Rates

```bash
python bis.py eer
python bis.py eer --countries US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX
python bis.py eer --countries US+GB+JP+CN+DE --start 2010
python bis.py eer --countries US --start 2000
```

PRISM receives: monthly REER (real effective exchange rate), broad basket (64 economies).

### Global Liquidity Indicators

```bash
python bis.py global-liquidity
python bis.py global-liquidity --start 2010
python bis.py global-liquidity --start 2005
```

PRISM receives: quarterly global liquidity indicators (USD/EUR/JPY credit to non-bank borrowers outside home country).

### LBS Cross-Border Banking

```bash
python bis.py lbs
python bis.py lbs --reporter US --position C --start 2010
python bis.py lbs --reporter US --position L --start 2010
python bis.py lbs --reporter GB --position C --start 2015
python bis.py lbs --reporter JP --position C --start 2010
python bis.py lbs --reporter DE --position L --start 2015
python bis.py lbs --reporter CH --position C --start 2010
python bis.py lbs --reporter HK --position C --start 2015
python bis.py lbs --reporter SG --position L --start 2015
```

PRISM receives: quarterly cross-border claims or liabilities for the reporting country, all instruments, all currencies, all counterparties, all sectors, all bank nationalities.

### Generic Query (any dataflow, any key)

```bash
# Query by alias
python bis.py query policy-rates --key "M.US+GB+JP" --start 2020
python bis.py query credit --key "Q.US.P.A.M.770.A" --start 2000
python bis.py query credit-gap --key "Q.US.P.A.C" --start 2000
python bis.py query dsr --key "Q.US.P" --start 2005
python bis.py query eer --key "M.R.B.US+GB+JP+CN" --start 2010
python bis.py query property --key "Q.US+GB+CN+AU.R.771" --start 2005

# Query by flow ID
python bis.py query WS_CBPOL --key "M.US+GB+JP" --start 2020
python bis.py query WS_TC --key "Q.US+CN.P.A.M.770.A" --start 2000
python bis.py query WS_CREDIT_GAP --key "Q.US+CN.P.A.C" --start 2000
python bis.py query WS_DSR --key "Q.US+GB+JP.P" --start 2005
python bis.py query WS_EER --key "M.R.B.US+GB+JP+CN+DE" --start 2010
python bis.py query WS_SPP --key "Q.US+GB+CN+AU.R.771" --start 2005

# LBS via generic query
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.A..N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.N.CN.N" --start 2015
python bis.py query lbs --key "Q.S.L.A.USD.A.5J.A.GB.A..N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.5A.A.TR.N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.JP.A..A.US.N" --start 2015

# CBS via generic query
python bis.py query WS_CBS_PUB --key "Q.S.US.A.U.C.A.A.TO1.A.5J" --start 2015

# OTC derivatives
python bis.py query WS_OTC_DERIV2 --key "H.A.A.A..A....TO1.TO1.A.A.3.A" --start 2010

# Exchange-traded derivatives
python bis.py query WS_XTD_DERIV --key "Q.A.A.A.TO1.5J" --start 2010

# Commercial property
python bis.py query WS_CPP --key "Q.US+GB+DE.0.A.0.0.0.0" --start 2005

# Debt securities
python bis.py query WS_DEBT_SEC2_PUB --key "Q.US......1......I" --start 2010

# CPI long series
python bis.py query WS_LONG_CPI --key "M.US+GB+JP.771" --start 2000

# Central bank total assets
python bis.py query WS_CB_TA --key "M.US+GB+JP+XM" --start 2008

# Global liquidity: USD credit specifically
python bis.py query WS_GLI --key "Q.USD...." --start 2010

# With date range
python bis.py query WS_CBPOL --key "M.US" --start 2020 --end 2024
python bis.py query WS_TC --key "Q.US.P.A.M.770.A" --start 2000 --end 2020

# Full dataflow (caution: large)
python bis.py query WS_DSR --key all --start 2020
```

PRISM receives: list of series objects with key, dimensions, attributes, observations.

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--countries CC+CC+CC` | `+`-separated country codes | policy-rates, total-credit, credit-gap, dsr, property-prices, eer |
| `--start YYYY` | Start period (year or YYYY-QN or YYYY-MM) | All data commands |
| `--end YYYY` | End period | query |
| `--key KEY` | SDMX dimension key filter | query |
| `--reporter CC` | Reporting country | lbs |
| `--position C\|L` | Claims or Liabilities | lbs |
| `--output PATH` | Custom output path | scrape, deep-index |
| `--input PATH` | Custom input path | explore |
| `--skip-existing` | Skip if ontology file exists | scrape |


## Python Recipes

### Core Data Query

```python
from bis import data_query, _parse_sdmx_data, DATAFLOW_ALIASES

# Generic query: any dataflow, any key
# Returns: list of {key, dimensions, attributes, observations}
series = data_query("WS_CBPOL", key="M.US+GB+JP", start_period="2020")
series = data_query("policy-rates", key="M.US+GB+JP", start_period="2020")

# With full params
series = data_query(
    dataflow="WS_TC",           # flow ID or alias
    key="Q.US.P.A.M.770.A",    # SDMX key
    start_period="2000",        # start
    end_period="2024",          # end (optional)
    detail="full",              # "full" | "dataonly" | "serieskeysonly" | "nodata"
    max_retries=3               # retry count
)

# Access results
for s in series:
    print(s["key"])                    # "Q.US.P.A.M.770.A"
    print(s["dimensions"]["FREQ"])     # {"id": "Q", "name": "Quarterly"}
    print(s["observations"])           # {"2024-Q1": 250.3, "2024-Q2": 251.1, ...}
```

### Pre-Built Recipes

```python
from bis import (recipe_policy_rates, recipe_total_credit, recipe_credit_gap,
                 recipe_dsr, recipe_property_prices, recipe_eer,
                 recipe_global_liquidity, recipe_lbs_crossborder)

# Central bank policy rates
# Returns: list of series, auto-saves to data/policy_rates_{ts}.json
series = recipe_policy_rates()
series = recipe_policy_rates(countries="US+GB+JP+DE+CH+CA+AU+SE+NO+NZ", start="2000")
series = recipe_policy_rates(countries="US+GB+JP", start="2020", end="2024")

# Total credit to non-financial sector
# Returns: list of series (quarterly, domestic currency, nominal, break-adjusted)
series = recipe_total_credit()
series = recipe_total_credit(countries="US+GB+JP+DE+FR+CN+CA+AU", start="2000")
series = recipe_total_credit(countries="US+CN", start="2010", end=None)

# Credit-to-GDP gaps
# Returns: list of series (quarterly gap values, >10pp = warning)
series = recipe_credit_gap()
series = recipe_credit_gap(countries="US+GB+JP+DE+FR+CN+CA+AU", start="2000")
series = recipe_credit_gap(countries="US+CN+TR+KR", start="1995")

# Debt service ratios
# Returns: list of series (quarterly, private non-financial sector)
series = recipe_dsr()
series = recipe_dsr(countries="US+GB+JP+DE+FR+CN+CA+AU", start="2000")
series = recipe_dsr(countries="US+GB", start="2005", end="2024")

# Residential property prices
# Returns: list of series (quarterly, nominal, index)
series = recipe_property_prices()
series = recipe_property_prices(countries="US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR", start="2000")
series = recipe_property_prices(countries="US+GB+CN+AU+CA", start="2005")

# Effective exchange rates
# Returns: list of series (monthly, REER, broad basket)
series = recipe_eer()
series = recipe_eer(countries="US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX", start="2000")
series = recipe_eer(countries="US+JP+CN", start="2010")

# Global liquidity indicators
# Returns: list of series (quarterly, all currencies/borrowers)
series = recipe_global_liquidity()
series = recipe_global_liquidity(start="2010", end=None)

# LBS cross-border banking
# Returns: list of series (quarterly, all instruments, all currencies, cross-border)
series = recipe_lbs_crossborder()
series = recipe_lbs_crossborder(reporter="US", position="C", start="2010")
series = recipe_lbs_crossborder(reporter="GB", position="L", start="2015")
series = recipe_lbs_crossborder(reporter="JP", position="C", start="2010", end="2024")
```

### Generic Data Query Command

```python
from bis import _cmd_data_query

# CLI-equivalent wrapper (prints formatted table + auto-saves)
series = _cmd_data_query("policy-rates", key="M.US+GB+JP", start="2020")
series = _cmd_data_query("WS_TC", key="Q.US.P.A.M.770.A", start="2000", end="2024")
series = _cmd_data_query("lbs", key="Q.S.C.A.TO1.A.5J.A.US.A..N", start="2015")
series = _cmd_data_query("WS_OTC_DERIV2", key="H.A.A.A..A....TO1.TO1.A.A.3.A", start="2010")
series = _cmd_data_query("WS_CBS_PUB", key="Q.S.US.A.U.C.A.A.TO1.A.5J", start="2015")
series = _cmd_data_query("credit-gap", key="Q.US+CN.P.A.C", start="2000", save=True)
```

### Ontology Functions

```python
from bis import scrape_full_ontology, explore_ontology, deep_index_lbs

# Scrape full ontology -> ontology/bis_ontology.json
scrape_full_ontology()
scrape_full_ontology(output_path="custom.json")
scrape_full_ontology(output_path=None, skip_existing=True)

# Interactive ontology explorer
explore_ontology()
explore_ontology(ontology_path="custom.json")

# Deep-index LBS cross-border relations -> ontology/lbs_deep_index.json
deep_index_lbs()
deep_index_lbs(output_path="custom_lbs.json")
```

### Subprocess (via execute_analysis_script)

```python
import subprocess, json

def bis_query(command, args_str=""):
    cmd = f"python GS/data/apis/bis/bis.py {command} {args_str}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout

bis_query("policy-rates", "--countries US+GB+JP+DE+CH --start 2020")
bis_query("total-credit", "--countries US+CN+GB+JP --start 2010")
bis_query("credit-gap", "--countries US+CN+GB+JP --start 2000")
bis_query("dsr", "--countries US+GB+JP+DE --start 2005")
bis_query("property-prices", "--countries US+GB+CN+AU+CA --start 2005")
bis_query("eer", "--countries US+GB+JP+CN+DE --start 2010")
bis_query("global-liquidity", "--start 2010")
bis_query("lbs", "--reporter US --position C --start 2015")
bis_query("query", "WS_CBPOL --key 'M.US+GB+JP' --start 2020")
bis_query("query", "lbs --key 'Q.S.C.A.TO1.A.5J.A.US.N.CN.N' --start 2015")
bis_query("query", "WS_OTC_DERIV2 --key 'H.A.A.A..A....TO1.TO1.A.A.3.A' --start 2010")
```

### Direct API Access

```python
import requests
BASE = "https://stats.bis.org/api/v2"
HEADERS = {"Accept": "application/vnd.sdmx.data+json;version=1.0.0"}

# LBS: US banks, total cross-border claims
resp = requests.get(f"{BASE}/data/dataflow/BIS/WS_LBS_D_PUB/1.0/Q.S.C.A.TO1.A.5J.A.US.A..N",
    headers=HEADERS, params={"startPeriod": "2015", "format": "sdmx-json"})

# Credit gap: US private sector
resp = requests.get(f"{BASE}/data/dataflow/BIS/WS_CREDIT_GAP/1.0/Q.US.P.A.C",
    headers=HEADERS, params={"startPeriod": "2000", "format": "sdmx-json"})

# Policy rates: major DM
resp = requests.get(f"{BASE}/data/dataflow/BIS/WS_CBPOL/1.0/M.US+GB+JP+DE+CH",
    headers=HEADERS, params={"startPeriod": "2020", "format": "sdmx-json"})
```


## Composite Recipes

### Global Credit Cycle Assessment

```bash
python bis.py total-credit --countries US+GB+JP+DE+FR+CN+CA+AU --start 2000
python bis.py credit-gap --countries US+GB+JP+DE+FR+CN+CA+AU --start 2000
python bis.py dsr --countries US+GB+JP+DE+FR+CN+CA+AU --start 2005
```

PRISM receives: credit/GDP levels, credit-to-GDP gaps (actual vs trend), debt service ratios across 8 major economies. Identifies vulnerability (high credit/GDP + positive gap + rising DSR) and resilience (low credit/GDP + negative gap + low DSR).

### Central Bank Rate Cycle

```bash
python bis.py policy-rates --countries US+GB+JP+DE+CH+CA+AU+SE+NO+NZ+BR+IN+MX+ZA --start 2015
python bis.py query WS_LONG_CPI --key "M.US+GB+JP+DE.771" --start 2015
python bis.py eer --countries US+GB+JP+CN --start 2015
```

PRISM receives: policy rates for 14 central banks (DM + EM), CPI for cross-referencing real rates, REER for exchange rate implications.

### Cross-Border Banking Exposure Drill-Down

```bash
# Total exposure
python bis.py lbs --reporter US --position C --start 2015

# By counterparty: China, Turkey, UK, Euro area
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.A.CN.N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.A.TR.N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.A.GB.N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.A.5C.N" --start 2015

# By instrument: loans vs debt securities vs derivatives
python bis.py query lbs --key "Q.S.C.G.TO1.A.5J.A.US.A.CN.N" --start 2015
python bis.py query lbs --key "Q.S.C.D.TO1.A.5J.A.US.A.CN.N" --start 2015
python bis.py query lbs --key "Q.S.C.V.TO1.A.5J.A.US.A.CN.N" --start 2015

# By currency: USD vs EUR
python bis.py query lbs --key "Q.S.C.A.USD.A.5J.A.US.A.CN.N" --start 2015
python bis.py query lbs --key "Q.S.C.A.EUR.A.5J.A.US.A.CN.N" --start 2015

# By sector: banks vs non-banks vs government
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.B.CN.N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.N.CN.N" --start 2015
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.G.CN.N" --start 2015

# Bank nationality: Japanese-parented banks in UK
python bis.py query lbs --key "Q.S.C.A.TO1.A.JP.A.GB.A..N" --start 2015

# Liabilities (reverse flow)
python bis.py lbs --reporter US --position L --start 2015
```

PRISM receives: total exposure, geographic breakdown, instrument decomposition, currency denomination, sector split, bank nationality analysis, reverse flow.

### Property Price + Credit Vulnerability

```bash
python bis.py property-prices --countries US+GB+CN+AU+CA+NZ+SE+NO+KR --start 2005
python bis.py total-credit --countries US+GB+CN+AU+CA+NZ+SE+NO+KR --start 2005
python bis.py credit-gap --countries US+GB+CN+AU+CA+NZ+SE+NO+KR --start 2005
python bis.py query WS_CPP --key "Q.US+GB+DE.0.A.0.0.0.0" --start 2005
```

PRISM receives: residential and commercial property indices alongside credit/GDP levels and gaps for vulnerability cross-referencing.

### Global Dollar Liquidity

```bash
python bis.py global-liquidity --start 2010
python bis.py query WS_GLI --key "Q.USD...." --start 2010
python bis.py query WS_GLI --key "Q.EUR...." --start 2010
python bis.py eer --countries US+GB+JP+CN+BR+IN+MX+TR --start 2010
python bis.py query lbs --key "Q.S.C.A.USD.A.5J.A.5A.A..N" --start 2010
```

PRISM receives: global liquidity indicators (all + USD-specific + EUR-specific), REER for EM countries, USD-denominated cross-border claims from all reporters.

### Contagion / Stress Test

```bash
# Stressed country fundamentals (e.g. Turkey)
python bis.py query credit-gap --key "Q.TR.P.A.C" --start 2000
python bis.py query dsr --key "Q.TR.P" --start 2005

# Who is exposed to Turkey?
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.5A.A.TR.N" --start 2010

# Decompose by reporter
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.US.A.TR.N" --start 2010
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.GB.A.TR.N" --start 2010
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.FR.A.TR.N" --start 2010
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.ES.A.TR.N" --start 2010

# USD-denominated exposure (double stress: FX + credit)
python bis.py query lbs --key "Q.S.C.A.USD.A.5J.A.5A.A.TR.N" --start 2010

# Second-order: who is exposed to Spain (largest Turkey exposurer)?
python bis.py query lbs --key "Q.S.C.A.TO1.A.5J.A.5A.A.ES.N" --start 2010
```

PRISM receives: stressed country credit gap + DSR, all reporters' claims on stressed country, per-reporter breakdown, USD exposure, second-order contagion chain.

### Derivatives Market Structure

```bash
python bis.py query WS_OTC_DERIV2 --key "H.A.A.A..A....TO1.TO1.A.A.3.A" --start 2010
python bis.py query WS_OTC_DERIV2 --key "H.A.A.B..A....TO1.TO1.A.A.3.A" --start 2010
python bis.py query WS_OTC_DERIV2 --key "H.A.A.C..A....TO1.TO1.A.A.3.A" --start 2010
python bis.py query WS_OTC_DERIV2 --key "H.A.A.Y..A....TO1.TO1.A.A.3.A" --start 2010
python bis.py query WS_XTD_DERIV --key "Q.A.A.A.TO1.5J" --start 2010
```

PRISM receives: OTC notional outstanding (all risk categories, FX, interest rate, credit/CDS), exchange-traded totals.

### Event-Window Analysis (Quarter-End, FOMC, Tax Date)

```bash
python bis.py query WS_CBPOL --key "M.US" --start YYYY --end YYYY
python bis.py query credit --key "Q.US.P.A.M.770.A" --start YYYY --end YYYY
python bis.py policy-rates --countries US+GB+JP --start YYYY
```

PRISM receives: policy rate and credit levels across the event window for pre/post comparison.


## Cross-Source Recipes

### BIS Credit + FRED High-Frequency

```bash
python bis.py credit-gap --countries US --start 2000
python bis.py dsr --countries US --start 2005
python GS/data/apis/fred/fred.py query TOTBKCR --start 2020
```

PRISM receives: BIS structural credit gap + DSR (quarterly, lagged) alongside FRED real-time bank credit growth.

### BIS Rates + NY Fed Funding

```bash
python bis.py policy-rates --countries US+GB+JP+DE+CH --start 2020
python GS/data/apis/nyfed/nyfed.py rates --json
python GS/data/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: BIS policy rate cycle (monthly, cross-country) + NY Fed overnight funding complex (daily, US-specific).

### BIS LBS + FDIC Bank Health

```bash
python bis.py lbs --reporter US --position C --start 2015
python GS/data/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: US cross-border banking exposure (quarterly) + bank-level stress indicators from FDIC.

### BIS EER + CFTC Positioning

```bash
python bis.py eer --countries US+GB+JP+CN --start 2015
python GS/data/apis/cftc/cftc.py fx --json
```

PRISM receives: real effective exchange rates (monthly) + speculative FX futures positioning.

### BIS Property + Treasury Supply

```bash
python bis.py property-prices --countries US --start 2005
python bis.py credit-gap --countries US --start 2005
python GS/data/apis/treasury/treasury.py get dts --json
```

PRISM receives: property prices + credit gap (quarterly) alongside fiscal cash flows (daily).

### BIS Derivatives + DTCC Swap Flow

```bash
python bis.py query WS_OTC_DERIV2 --key "H.A.A.C..A....TO1.TO1.A.A.3.A" --start 2015
python GS/data/apis/dtcc/dtcc.py latest irs --json
```

PRISM receives: BIS semi-annual OTC interest rate derivatives outstanding + DTCC real-time swap volumes.

### BIS Credit + Prediction Markets

```bash
python bis.py credit-gap --countries US+CN+GB+JP --start 2000
python bis.py dsr --countries US+CN+GB+JP --start 2005
python GS/data/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: structural credit vulnerability (quarterly) + market-implied policy probability (real-time).

### BIS Global Liquidity + NY Fed QT

```bash
python bis.py global-liquidity --start 2015
python bis.py query lbs --key "Q.S.C.A.USD.A.5J.A.5A.A..N" --start 2015
python GS/data/apis/nyfed/nyfed.py qt-monitor --weeks 52 --json
```

PRISM receives: global dollar liquidity conditions (quarterly) + Fed balance sheet runoff pace (weekly).


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python bis.py policy-rates --countries US --start 2020`
4. Ontology build: `python bis.py scrape` (takes ~5 minutes, writes 7MB JSON)
5. Full test: `python bis.py` (launches interactive menu)


## Architecture

```
bis.py
  Constants       BASE_URL, HEADERS, DATA_HEADERS, DATAFLOW_ALIASES (15),
                  REPORTING_COUNTRIES_ACTUAL (48), LBS_COUNTRY_NAMES
  HTTP            api_get() with retries + rate limit handling (metadata)
                  data_query() with retries + rate limit handling (data)
  SDMX Parser     _parse_sdmx_data() -> list of {key, dimensions, attributes, observations}
  Ontology        scrape_full_ontology() -> ontology/bis_ontology.json
                  explore_ontology() -> interactive 6-option explorer
                  deep_index_lbs() -> ontology/lbs_deep_index.json
  Recipes (8)     recipe_policy_rates, recipe_total_credit, recipe_credit_gap,
                  recipe_dsr, recipe_property_prices, recipe_eer,
                  recipe_global_liquidity, recipe_lbs_crossborder
  Generic Query   _cmd_data_query() -> any dataflow + any key
  Output          _format_series_table(), _save_data_json(), _series_to_csv_rows()
  Interactive     18-item menu (ontology 1-5, data 10-18) with input prompts
  Argparse        12 subcommands: scrape, explore, deep-index, query,
                  policy-rates, total-credit, credit-gap, dsr,
                  property-prices, eer, global-liquidity, lbs
```

API endpoints:
```
/structure/dataflow/BIS                                    -> all dataflows
/structure/datastructure/BIS/{DSD}/{VER}                   -> DSD with codelists
/availability/dataflow/BIS/WS_LBS_D_PUB/1.0/{KEY}         -> LBS availability
/data/dataflow/BIS/{FLOW_ID}/1.0/{KEY}?startPeriod={YYYY}  -> time series data
```

Ontology files:
```
ontology/bis_ontology.json       7MB   29 dataflows, 108 codelists, 7,280 codes
ontology/lbs_deep_index.json     1.4MB 50 reporters, cross-border matrix
```
