# BIS SDMX Statistics API -- Data Awareness Guide

PRISM data source for global macro-financial data from the Bank for International Settlements. 29 datasets covering cross-border banking flows, total credit aggregates, credit-to-GDP gaps, debt service ratios, property prices, effective exchange rates, central bank policy rates, global liquidity, derivatives, and debt securities across 60+ countries.

Script: `GS/data/apis/bis/bis_ontology_scraper.py`
API: `https://stats.bis.org/api/v2`
Auth: None required
Format: SDMX-JSON
Ontology: `ontology/bis_ontology.json` (7MB, 29 dataflows, 108 codelists, 7,280 codes)


## SDMX Key Syntax

Queries use period-separated dimension keys matching the dimension order of each dataflow:
```
M.US              → Monthly, United States
Q.US+GB+JP        → Quarterly, US + UK + Japan (OR within dimension)
Q..US             → Quarterly, wildcard first dim, US
all               → All series (can be large)
```
`+` = OR within dimension. `.` separates dimensions. `..` skips (wildcards) a dimension.

API URL pattern: `https://stats.bis.org/api/v2/data/dataflow/BIS/{FLOW_ID}/1.0/{KEY}?startPeriod={YYYY}&format=sdmx-json`


## Full Dataflow Ontology

### WS_LBS_D_PUB -- Locational Banking Statistics

The flagship cross-border banking dataset. Reports claims and liabilities of banks in each reporting country vis-a-vis counterparty countries, broken down by instrument, currency, sector, and bank nationality. Quarterly.

**Key:** `FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE`

**158,856 total series. 50 reporting countries. 226 counterparty countries.**

| Pos | Dim | Codelist | Codes |
|-----|-----|----------|-------|
| 1 | FREQ | CL_FREQ | Q=Quarterly, M=Monthly, A=Annual |
| 2 | L_MEASURE | CL_STOCK_FLOW | S=Stocks, F=FX-adjusted change, G=Annual growth, B=Break, R=Revisions |
| 3 | L_POSITION | CL_L_POSITION | **C=Total claims, L=Total liabilities**, D=Cross-border claims, B=Local claims, I=International claims, N=Net positions, K=Capital/equity, S=Foreign Claims, M=Local liabilities, + 7 more |
| 4 | L_INSTR | CL_L_INSTR | **A=All instruments, G=Loans & deposits, D=Debt securities, B=Credit (loans+debt)**, I=Derivatives+Other, V=Derivatives, M=Short-term debt, L=Long-term debt, E=RWA, R=Tier 1, S=Tier 2, + 12 more |
| 5 | L_DENOM | CL_CURRENCY_3POS | **USD, EUR, GBP, JPY, CHF, TO1=All currencies, TO3=Foreign currencies, UN9=Unallocated** + 318 others |
| 6 | L_CURR_TYPE | CL_L_CURR_TYPE | A=All currencies, D=Domestic, F=Foreign, U=Unclassified |
| 7 | L_PARENT_CTY | CL_BIS_IF_REF_AREA | **5J=All parent countries**, US, GB, JP, DE, FR, CH, + 426 others. Bank nationality (parent HQ country) |
| 8 | L_REP_BANK_TYPE | CL_L_BANK_TYPE | **A=All banks**, D=Domestic, B=Foreign branches, S=Foreign subsidiaries, U=Consortium |
| 9 | L_REP_CTY | CL_BIS_IF_REF_AREA | Reporting country (where bank is located). 50 actual reporters: US, GB, JP, DE, FR, CH, HK, SG, CA, AU, etc. |
| 10 | L_CP_SECTOR | CL_L_SECTOR | **A=All sectors, B=Banks total, N=Non-banks total**, I=Related offices, M=Central banks, F=Non-bank financial, C=Non-financial corps, G=General govt, H=Households, + 11 more |
| 11 | L_CP_COUNTRY | CL_BIS_IF_REF_AREA | Counterparty country (who the bank is lending to / borrowing from). 226 ISO codes + aggregates |
| 12 | L_POS_TYPE | CL_L_POS_TYPE | **N=Cross-border, R=Local, I=Cross-border+Local in FCY, A=All**, D=Domestic collateral, F=Foreign collateral |

**Example queries:**
```
Q.S.C.A.TO1.A.5J.A.US.A..N     US banks, total claims, all instruments, all currencies, cross-border
Q.S.L.G.USD.A.5J.A.GB.B..N     UK banks, liabilities, loans+deposits, USD, to banks, cross-border
Q.S.C.A.TO1.A.5J.A.US.N.CN.N   US banks, claims on Chinese non-banks, cross-border
```


### WS_CBS_PUB -- Consolidated Banking Statistics

Banks' worldwide consolidated claims, eliminating intra-group positions. Can be on immediate counterparty basis or ultimate risk (guarantor) basis. Quarterly.

**Key:** `FREQ.L_MEASURE.L_REP_CTY.CBS_BANK_TYPE.CBS_BASIS.L_POSITION.L_INSTR.REM_MATURITY.CURR_TYPE_BOOK.L_CP_SECTOR.L_CP_COUNTRY`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 5 | CBS_BASIS | F=Immediate counterparty, U=Guarantor basis, R=Guarantor calculated |
| 8 | REM_MATURITY | A=All, U=Up to 1yr, W=Over 1yr, D=1-5yr, F=Over 5yr |
| 9 | CURR_TYPE_BOOK | All 326 currencies. Key: TO1=All, USD, EUR, GBP, JPY |

**Example:** `Q.S.US.A.U.C.A.A.TO1.A.5J` -- US banks, guarantor basis, total claims, all instruments, all maturities, all currencies, all counterparties


### WS_TC -- Total Credit to Non-Financial Sector

Credit/GDP, nominal credit levels. The core credit cycle dataset. Quarterly.

**Key:** `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE.TC_ADJUST`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | BORROWERS_CTY | CL_AREA: US, GB, JP, DE, FR, CN, CA, AU, + 93 others. Includes XM=Euro area, 5A=All, G2=G20 |
| 3 | TC_BORROWERS | **P=Private non-financial, C=Non-financial sector, G=General govt, H=Households, N=Non-financial corps** |
| 4 | TC_LENDERS | A=All sectors, B=Banks domestic |
| 5 | VALUATION | M=Market value, N=Nominal |
| 6 | UNIT_TYPE | CL_BIS_UNIT: XDC=Domestic currency, USD=US dollar, 770=% of GDP, + 1092 others |
| 7 | TC_ADJUST | A=Adjusted for breaks, 0=Non-seasonally adjusted, 1=Seasonally adjusted |

**Example:** `Q.US.P.A.M.770.A` -- US, private non-financial sector, all lenders, market value, % of GDP, break-adjusted


### WS_CREDIT_GAP -- Credit-to-GDP Gaps

BIS flagship early-warning indicator. Deviation of credit/GDP from HP-filtered trend. Gap >10pp historically precedes financial crises with 2-3 year lead. Quarterly.

**Key:** `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.CG_DTYPE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | BORROWERS_CTY | CL_BIS_GL_REF_AREA: 239 countries/aggregates |
| 5 | CG_DTYPE | **A=Credit-to-GDP ratios (actual), B=Credit-to-GDP trend (HP filter), C=Credit-to-GDP gaps (actual minus trend)** |

**Example:** `Q.US.P.A.C` -- US, private non-financial, all lenders, CREDIT GAP


### WS_DSR -- Debt Service Ratios

Share of income devoted to debt service (principal + interest). Measures rate sensitivity of the private sector. Quarterly.

**Key:** `FREQ.BORROWERS_CTY.DSR_BORROWERS`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | BORROWERS_CTY | CL_AREA: 101 countries |
| 3 | DSR_BORROWERS | P=Private non-financial, H=Households, N=Non-financial corps, C=Non-financial sector, G=General govt |

**Example:** `Q.US.P` -- US, private non-financial debt service ratio


### WS_CBPOL -- Central Bank Policy Rates

Official policy rates for 239 central banks. Monthly.

**Key:** `FREQ.REF_AREA`

**Example:** `M.US+GB+JP+DE+CH+CA+AU` -- Monthly policy rates for major DM central banks


### WS_EER -- Effective Exchange Rates

Real and nominal effective exchange rates. Broad (64 economies) and narrow (27) baskets. Monthly.

**Key:** `FREQ.EER_TYPE.EER_BASKET.REF_AREA`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | EER_TYPE | **R=Real, N=Nominal** |
| 3 | EER_BASKET | **B=Broad (64 economies), N=Narrow (27 economies)** |
| 4 | REF_AREA | CL_AREA: 101 countries |

**Example:** `M.R.B.US+GB+JP+CN` -- Monthly REER, broad basket, for US/UK/Japan/China


### WS_GLI -- Global Liquidity Indicators

USD/EUR/JPY credit to non-bank borrowers outside the currency's home country. Measures global dollar/euro/yen funding conditions. Quarterly.

**Key:** `FREQ.CURR_DENOM.BORROWERS_CTY.BORROWERS_SECTOR.LENDERS_SECTOR.L_POS_TYPE.L_INSTR.UNIT_MEASURE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | CURR_DENOM | USD, EUR, JPY (+ all 326 currencies) |
| 3 | BORROWERS_CTY | 432 countries |
| 4-5 | SECTORS | CL_L_SECTOR: A=All, B=Banks, N=Non-banks |
| 6 | L_POS_TYPE | N=Cross-border, R=Local, I=Cross-border+Local FCY |
| 7 | L_INSTR | A=All, G=Loans, D=Debt securities, B=Credit |


### WS_SPP -- Selected Residential Property Prices

Property price indices for 101 economies. Real and nominal. Quarterly.

**Key:** `FREQ.REF_AREA.VALUE.UNIT_MEASURE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 3 | VALUE | **R=Real, N=Nominal** |

**Example:** `Q.US+GB+CN+AU.R.771` -- Quarterly real property prices, index


### WS_CPP -- Commercial Property Prices

Commercial (office, retail, industrial) property prices. Quarterly.

**Key:** `FREQ.REF_AREA.COVERED_AREA.RE_TYPE.RE_VINTAGE.COMPILING_ORG.PRICED_UNIT.ADJUST_CODED`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 3 | COVERED_AREA | 0=Whole country, 2=Capital city, 4=Big cities, 9=Urban |
| 4 | RE_TYPE | **A=Commercial property, B=Office, C=Retail**, G=Industrial, 0=All properties, 1=All dwellings |


### WS_XTD_DERIV -- Exchange-Traded Derivatives

Futures and options on exchanges. Quarterly.

**Key:** `FREQ.OD_TYPE.OD_RISK_CAT.OD_INSTR.ISSUE_CUR.XD_EXCHANGE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | OD_TYPE | A=Notional outstanding, B=Gross positive MV, K=Turnover, L=Num contracts, U=Turnover daily avg |
| 3 | OD_RISK_CAT | A=All, B=FX, C=Interest rate, D=Equity, H=All commodities, Y=Credit derivatives |
| 4 | OD_INSTR | A=All, C=Forwards+swaps, H=Options total, T=Futures |
| 5 | ISSUE_CUR | 131 currencies |
| 6 | XD_EXCHANGE | 432 exchanges/countries |


### WS_OTC_DERIV2 -- OTC Derivatives Outstanding

Over-the-counter derivatives: notional amounts, market values, credit exposure. Semi-annual.

**Key:** `FREQ.DER_TYPE.DER_INSTR.DER_RISK.DER_REP_CTY.DER_SECTOR_CPY.DER_CPC.DER_SECTOR_UDL.DER_CURR_LEG1.DER_CURR_LEG2.DER_ISSUE_MAT.DER_RATING.DER_EX_METHOD.DER_BASIS`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 2 | DER_TYPE | A=Notional, B=Gross positive MV, D=Gross MV, H=Gross credit exposure |
| 3 | DER_INSTR | A=All, B=FX incl gold, C=Forwards+swaps, G=Interest rate swaps, S=CDS, + 30 more |
| 4 | DER_RISK | A=All, B=FX, C=Interest rate, D=Equity, F=Precious metals, H=All commodities, Y=Credit |
| 6 | DER_SECTOR_CPY | A=All, B=Reporting dealers, C=Other financial, K=CCPs, R=Other customers, U=Non-financial |


### WS_DEBT_SEC2_PUB -- Debt Securities Statistics

International and domestic debt securities issuance. Quarterly.

**Key:** `FREQ.ISSUER_RES.ISSUER_NAT.ISSUER_BUS_IMM.ISSUER_BUS_ULT.MARKET.ISSUE_TYPE.ISSUE_CUR_GROUP.ISSUE_CUR.ISSUE_OR_MAT.ISSUE_RE_MAT.ISSUE_RATE.ISSUE_RISK.ISSUE_COL.MEASURE`

| Pos | Dim | Key Codes |
|-----|-----|-----------|
| 6 | MARKET | 1=All markets, A=Domestic, C=International |
| 12 | ISSUE_RATE | A=All, C=Fixed, E=Variable, M=Inflation-linked, G=Equity-related |
| 15 | MEASURE | **I=Outstanding, G=Net issues, C=Gross issues, E=Redemptions**, A=Announced, N=Avg original maturity |


### Other Dataflows (less commonly queried)

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


## Shared Dimension Codelists

### CL_AREA (101 codes) -- Used by: TC, DSR, SPP, EER, CPP

Major economies: US, GB, JP, DE, FR, CN, CA, AU, CH, SE, NO, NZ, KR, IN, BR, MX, IT, ES, NL, IE, SG, HK, TW, TH, MY, ID, PH, PL, CZ, HU, RO, RU, TR, ZA, SA, AE, IL, AR, CL, CO, PE, EG, NG, PK

Aggregates: XM=Euro area, 5A=All reporting, 5R=Advanced, 4T=Emerging, G2=G20, XW=World, 1X=ECB

### CL_BIS_IF_REF_AREA (432 codes) -- Used by: LBS, CBS, GLI, XTD, OTC, DEBT_SEC

All 226 ISO country codes plus offshore centers, aggregates, defunct states, and institutional groupings. Superset of CL_AREA.

### CL_BIS_GL_REF_AREA (239 codes) -- Used by: CBPOL, CREDIT_GAP

239 countries and aggregates with central bank coverage.


## Code Examples for execute_analysis_script

```python
import subprocess, json

def bis_query(command, args_str=""):
    cmd = f"python GS/data/apis/bis/bis_ontology_scraper.py {command} {args_str}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout

# Central bank policy rates
bis_query("policy-rates", "--countries US+GB+JP+DE+CH --start 2020")

# Total credit as % of GDP
bis_query("total-credit", "--countries US+CN+GB+JP --start 2010")

# Credit-to-GDP gaps (early warning)
bis_query("credit-gap", "--countries US+CN+GB+JP --start 2000")

# Debt service ratios
bis_query("dsr", "--countries US+GB+JP+DE --start 2005")

# Residential property prices (real)
bis_query("property-prices", "--countries US+GB+CN+AU+CA --start 2005")

# Real effective exchange rates
bis_query("eer", "--countries US+GB+JP+CN+DE --start 2010")

# Cross-border banking: US claims
bis_query("lbs", "--reporter US --position C --start 2015")

# Global liquidity
bis_query("global-liquidity", "--start 2010")

# Generic query: any dataflow
bis_query("query", "WS_OTC_DERIV2 --key 'H.A.A.A..A....TO1.TO1.A.A.3.A' --start 2010")
```

### Direct API access
```python
import requests
BASE = "https://stats.bis.org/api/v2"
HEADERS = {"Accept": "application/vnd.sdmx.data+json;version=1.0.0"}

# LBS: US banks, total cross-border claims, all instruments, all currencies
resp = requests.get(f"{BASE}/data/dataflow/BIS/WS_LBS_D_PUB/1.0/Q.S.C.A.TO1.A.5J.A.US.A..N",
    headers=HEADERS, params={"startPeriod": "2015", "format": "sdmx-json"})

# Credit gap: US private sector
resp = requests.get(f"{BASE}/data/dataflow/BIS/WS_CREDIT_GAP/1.0/Q.US.P.A.C",
    headers=HEADERS, params={"startPeriod": "2000", "format": "sdmx-json"})
```


## Analytical Framework

### When to use BIS data
- Cross-border banking exposure (who lends to whom, what instruments, what currencies)
- Global credit cycle (total credit/GDP, gaps, debt service ratios)
- Central bank rate cycle comparison
- Property prices across countries
- Real effective exchange rates (competitiveness)
- Global dollar liquidity conditions
- OTC/exchange-traded derivatives market structure
- International debt securities issuance
- Financial stability early-warning (credit-to-GDP gap >10pp threshold)

### When NOT to use
- US-specific high-frequency data → FRED
- Individual US bank data → FDIC BankFind
- Company fundamentals → SEC EDGAR
- US fiscal data → Treasury
- Event probabilities → Prediction Markets

### Credit-to-GDP Gap Reference
| Gap | Signal |
|-----|--------|
| < -10pp | Deep deleveraging, post-crisis |
| 0 to +5pp | Neutral |
| +5 to +10pp | Watch zone |
| > +10pp | Warning: pre-crisis (2-3yr lead) |
| > +20pp | Extreme: China 2009, Ireland 2007 |
