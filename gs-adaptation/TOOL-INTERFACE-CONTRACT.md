# Tool Interface Contract -- Complete Specification

This document specifies the exact input/output contract for every tool referenced by the LSEG financial analytics skills and commands. An internal data layer must implement these 23 interfaces. For each tool: the interaction pattern, required inputs, output fields, behavioral notes, which skills/commands depend on it, and a placeholder for the internal mapping.

The source of truth for these specifications is the skill files themselves (which were authored by LSEG to drive actual tool calls), supplemented by LSEG developer documentation.

---

## Reading This Document

Each tool entry follows this structure:

```
TOOL NAME                          [PATTERN: Direct | Two-Phase]
  Input:      what the caller sends
  Output:     what the tool returns
  Behavior:   interaction notes
  Used by:    which skills and commands call this tool
  Internal:   << PLACEHOLDER: your internal data source mapping >>
```

For two-phase tools, both phases are specified separately.

---

## 1. Bond Pricing Domain

### 1.1 bond_price

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Bond identifier: ISIN, RIC, CUSIP, or AssetId. Comma-separated for batch. |
| priceOverride | float | no | What-if clean price (solves for yield). |
| yieldOverride | float | no | What-if yield (solves for price). Mutually exclusive with priceOverride. |
| valuationDate | date | no | Pricing date. Defaults to today. |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| cleanPrice | float | Clean price (ex-accrued) |
| dirtyPrice | float | Dirty price (cum-accrued) |
| yieldToMaturity | float | YTM as percentage |
| modifiedDuration | float | Modified duration in years |
| convexity | float | Convexity |
| dv01 | float | Dollar value of 1bp |
| accruedInterest | float | Accrued interest |
| zSpread | float | Z-spread in basis points |
| currency | string | ISO currency code |

**Behavior:**
- Supports fixed-rate bonds, floating-rate notes, municipals, inflation-linked
- What-if mode: provide priceOverride OR yieldOverride to solve for the other
- Batch mode: comma-separated identifiers return an array of results
- Underlying model: Refinitiv Adfin / Price-It analytics engine

**Used by:**
- Skills: `bond-relative-value`, `bond-futures-basis`, `fixed-income-portfolio`
- Commands: `/analyze-bond-rv`, `/analyze-bond-basis`, `/review-fi-portfolio`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< INTERNAL_API:  ________________________________________________ >>
<< IDENTIFIER_FORMAT: ____________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 1.2 bond_future_price

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| contractRic | string | yes | Futures contract RIC (e.g., "TYA" for US 10Y, "RXA" for Bund) |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| fairPrice | float | Theoretical fair value |
| ctdBond | string | Identifier of cheapest-to-deliver bond |
| deliveryBasket | array | All deliverable bonds with conversion factors |
| deliveryBasket[].bondId | string | Bond identifier |
| deliveryBasket[].conversionFactor | float | Conversion factor for delivery |
| contractDv01 | float | DV01 of the futures contract |
| deliveryDates | object | First/last delivery dates |

**Behavior:**
- Returns the full delivery basket, not just CTD
- Conversion factors are critical for basis computation: gross basis = cash price - (futures price x CF)
- Use the ctdBond output as input to `bond_price` to get full cash bond analytics

**Used by:**
- Skills: `bond-futures-basis`
- Commands: `/analyze-bond-basis`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< INTERNAL_API:  ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 2. FX Pricing Domain

### 2.1 fx_spot_price

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| currencyPair | string | yes | ISO currency pair (e.g., "EURUSD", "USDJPY", "AUDUSD") |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| mid | float | Mid-market spot rate |
| bid | float | Bid rate |
| ask | float | Ask rate |

**Behavior:**
- Bid-ask spread is a liquidity indicator (wider = less liquid)
- Standard FX quoting conventions apply (EURUSD = EUR per 1 USD, etc.)

**Used by:**
- Skills: `fx-carry-trade`
- Commands: `/analyze-fx-carry`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 2.2 fx_forward_price

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| currencyPair | string | yes | ISO currency pair |
| tenor | string | yes | Forward tenor (e.g., "1M", "3M", "6M", "1Y") or specific date |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| forwardPoints | float | Forward points (pips) |
| outrightRate | float | Outright forward rate (spot + points) |
| carry | float | Annualized carry implied by forward points |

**Behavior:**
- Forward points reflect interest rate differential between the two currencies
- Annualized carry = (forward points / spot) x (365 / days to tenor) x 100

**Used by:**
- Skills: `fx-carry-trade`
- Commands: `/analyze-fx-carry`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 3. Curves Domain

### 3.1 interest_rate_curve

**Pattern:** Two-Phase (List then Calculate)

**Phase 1 -- List Available Curves:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| currency | string | yes | ISO currency code (e.g., "USD", "EUR", "GBP") |

Output:
| Field | Type | Description |
|-------|------|-------------|
| curves | array | Available curve identifiers |
| curves[].id | string | Curve identifier for Phase 2 |
| curves[].name | string | Human-readable name (e.g., "USD SOFR", "USD Treasury") |
| curves[].description | string | Curve description |

**Phase 2 -- Calculate Curve:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| curveId | string | yes | Curve identifier from Phase 1 |
| valuationDate | date | no | Defaults to today |

Output (array of tenor points):
| Field | Type | Description |
|-------|------|-------------|
| tenor | string | Tenor label (e.g., "3M", "1Y", "5Y", "10Y", "30Y") |
| parRate | float | Par yield (%) |
| zeroRate | float | Zero-coupon rate (%) |
| discountFactor | float | Discount factor (0 to 1) |
| forwardRate | float | Instantaneous forward rate (%) |

**Behavior:**
- Two-phase is required because curve identifiers vary by currency and source
- Returns the full term structure at all available tenor points
- Use short-end rates (3M, 6M) as repo rate proxy for basis analysis
- Interpolation between tenor points can be done by the skill (linear or cubic)
- If your internal system already knows curve identifiers, Phase 1 can be skipped

**Used by:**
- Skills: `bond-relative-value`, `bond-futures-basis`, `fx-carry-trade`, `swap-curve-strategy`, `fixed-income-portfolio`, `macro-rates-monitor`
- Commands: `/analyze-bond-rv`, `/analyze-bond-basis`, `/analyze-fx-carry`, `/analyze-swap-curve`, `/review-fi-portfolio`, `/macro-rates`

This is the **most widely used tool** -- referenced by 6 of 8 skills.

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< CURVE_ID_FORMAT: ______________________________________________ >>
<< AVAILABLE_CURVES: _____________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 3.2 credit_curve

**Pattern:** Two-Phase (Search then Calculate)

**Phase 1 -- Search:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| country | string | yes | Country code or name |
| issuerType | string | yes | "Corporate", "Sovereign", "Agency", "Supranational", etc. |

Output:
| Field | Type | Description |
|-------|------|-------------|
| curves | array | Matching credit curve identifiers |
| curves[].id | string | Curve identifier for Phase 2 |
| curves[].description | string | Curve description |

**Phase 2 -- Calculate:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| curveId | string | yes | Credit curve identifier from Phase 1 |

Output (array of maturity points):
| Field | Type | Description |
|-------|------|-------------|
| maturity | string | Maturity bucket (e.g., "1Y", "3Y", "5Y", "10Y") |
| spread | float | Credit spread in basis points |

**Behavior:**
- Used to isolate the credit component of a bond's total spread
- Residual spread = bond G-spread minus credit curve spread at matching maturity
- Positive residual = cheap (bond spread wider than credit curve implies)
- Negative residual = rich

**Used by:**
- Skills: `bond-relative-value`, `bond-futures-basis`
- Commands: `/analyze-bond-rv`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 3.3 inflation_curve

**Pattern:** Two-Phase (Search then Calculate)

**Phase 1 -- Search:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| country | string | no | Country code or name |
| currency | string | no | ISO currency (at least one of country/currency required) |

Output:
| Field | Type | Description |
|-------|------|-------------|
| curves | array | Available inflation curve identifiers |
| curves[].id | string | Curve identifier for Phase 2 |

**Phase 2 -- Calculate:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| curveId | string | yes | Inflation curve identifier from Phase 1 |

Output (array of tenor points):
| Field | Type | Description |
|-------|------|-------------|
| tenor | string | Tenor label |
| breakevenRate | float | Breakeven inflation rate (%) |
| realYield | float | Real yield (%) |

**Behavior:**
- Real rate = nominal rate - breakeven inflation at same tenor
- Real rate > ~1.5-2% is generally considered "restrictive"
- Used alongside interest_rate_curve for full rate decomposition

**Used by:**
- Skills: `swap-curve-strategy`, `macro-rates-monitor`
- Commands: `/analyze-swap-curve`, `/macro-rates`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 3.4 fx_forward_curve

**Pattern:** Two-Phase (List then Calculate)

**Phase 1 -- List:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| currencyPair | string | yes | ISO currency pair |

Output:
| Field | Type | Description |
|-------|------|-------------|
| curves | array | Available forward curve identifiers |

**Phase 2 -- Calculate:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| curveId | string | yes | Forward curve identifier from Phase 1 |
| valuationDate | date | no | Defaults to today |

Output (array across standard tenors):
| Field | Type | Description |
|-------|------|-------------|
| tenor | string | Standard tenor (O/N, T/N, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, ...) |
| forwardPoints | float | Forward points (pips) |

**Behavior:**
- Returns the FULL forward curve across all standard tenors in one call
- Skills compute annualized carry at each tenor from the forward points
- Optimal carry tenor = tenor with best carry-to-vol ratio

**Used by:**
- Skills: `fx-carry-trade`
- Commands: `/analyze-fx-carry`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 4. Swaps Domain

### 4.1 ir_swap

**Pattern:** Two-Phase (List Templates then Price)

**Phase 1 -- List Templates:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| currency | string | yes | ISO currency (e.g., "USD", "EUR") |
| index | string | no | Rate index filter (e.g., "SOFR", "ESTR", "SONIA") |

Output:
| Field | Type | Description |
|-------|------|-------------|
| templates | array | Available swap templates |
| templates[].id | string | Template identifier for Phase 2 |
| templates[].index | string | Reference rate index |
| templates[].conventions | string | Day count, payment frequency, etc. |

**Phase 2 -- Price:**

Input:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| templateId | string | yes | Swap template from Phase 1 |
| tenors | array[string] | yes | Tenors to price (e.g., ["2Y", "5Y", "7Y", "10Y", "20Y", "30Y"]) |

Output (per tenor):
| Field | Type | Description |
|-------|------|-------------|
| tenor | string | Requested tenor |
| parSwapRate | float | Par swap rate (%) |
| dv01 | float | DV01 of the swap |
| npv | float | Net present value |

**Behavior:**
- Swap spread = par swap rate - government yield at same tenor (from interest_rate_curve)
- Elevated swap spreads signal credit/funding stress in the financial system
- Skills request standard tenors (2Y, 5Y, 10Y, 30Y) to build the full swap curve

**Used by:**
- Skills: `swap-curve-strategy`, `macro-rates-monitor`
- Commands: `/analyze-swap-curve`, `/macro-rates`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 5. Options Domain

### 5.1 option_value

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| underlying | string | yes | Underlying identifier |
| optionType | string | yes | "vanilla", "barrier", "binary", "asian" |
| putCall | string | yes | "put" or "call" |
| strike | float | yes | Strike price |
| expiry | date/string | yes | Expiration date or tenor |
| (additional params) | varies | varies | Barrier levels, averaging params, etc. depending on optionType |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| premium | float | Option premium |
| delta | float | Delta |
| gamma | float | Gamma |
| vega | float | Vega |
| theta | float | Theta |
| rho | float | Rho |
| impliedVol | float | Implied volatility used in pricing |

**Behavior:**
- Covers equity, FX, and IR options
- Supports exotic types (barrier, binary, Asian) beyond vanilla
- Use after `option_template_list` to discover valid strikes/expiries

**Used by:**
- Skills: `option-vol-analysis`
- Commands: `/analyze-option-vol`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 5.2 option_template_list

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| underlying | string | yes | Underlying identifier |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| templates | array | Available option templates |
| templates[].type | string | Option type |
| templates[].expiries | array | Available expiration dates |
| templates[].strikes | array | Available strikes (if listed) |

**Behavior:**
- Discovery tool: call before `option_value` to find valid parameters
- Not all underlyings support all option types

**Used by:**
- Skills: `option-vol-analysis`
- Commands: `/analyze-option-vol`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 6. Volatility Domain

### 6.1 fx_vol_surface

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| currencyPair | string | yes | ISO pair (e.g., "EURUSD") |

**Output (matrix: tenor x delta):**
| Field | Type | Description |
|-------|------|-------------|
| tenor | string | Expiry tenor (1W, 1M, 2M, 3M, 6M, 1Y, 2Y) |
| atmVol | float | At-the-money volatility (%) |
| put25dVol | float | 25-delta put implied vol (%) |
| call25dVol | float | 25-delta call implied vol (%) |
| riskReversal25d | float | 25d RR = call vol - put vol (skew measure) |
| butterfly25d | float | 25d BF = (call + put)/2 - ATM (smile curvature) |

**Behavior:**
- FX vol surfaces are quoted in delta space (not strike space)
- Model: SABR (Stochastic Alpha Beta Rho)
- Positive risk reversal = market paying up for upside (calls expensive)
- Carry-to-vol ratio = annualized carry / ATM implied vol (key metric for carry trades)

**Used by:**
- Skills: `fx-carry-trade`, `option-vol-analysis`
- Commands: `/analyze-fx-carry`, `/analyze-option-vol`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 6.2 equity_vol_surface

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| ric | string | conditional | RIC for equities/indices (e.g., ".SPX@RIC"). Use for cash. |
| ricroot | string | conditional | RICROOT for futures (e.g., "ES@RICROOT"). Use for futures. One of ric/ricroot required. |

**Output (matrix: tenor x strike/delta):**
| Field | Type | Description |
|-------|------|-------------|
| tenor | string | Expiry tenor |
| atmVol | float | ATM implied vol (%) |
| strikeVols | array | Vol at various strikes or deltas |
| riskReversal25d | float | Skew measure |
| butterfly25d | float | Smile curvature |

**Behavior:**
- Equity surfaces may be in strike space or delta space depending on instrument
- Use with `tscc_historical_pricing_summaries` to compute realized vol for IV-RV comparison

**Used by:**
- Skills: `option-vol-analysis`
- Commands: `/analyze-option-vol`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 7. Quantitative Analytics Domain

### 7.1 qa_ibes_consensus

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Company identifier (ticker, RIC, ISIN) |
| metrics | array[string] | no | Which estimates: "EPS", "Revenue", "EBITDA", "DPS". Default: all. |
| periods | array[string] | no | Fiscal periods: "FY1", "FY2", "FQ1", etc. Default: FY1, FY2. |

**Output (per metric per period):**
| Field | Type | Description |
|-------|------|-------------|
| metric | string | Estimate type (EPS, Revenue, etc.) |
| period | string | Fiscal period label |
| median | float | Median analyst estimate |
| mean | float | Mean analyst estimate |
| high | float | Highest estimate |
| low | float | Lowest estimate |
| analystCount | int | Number of contributing analysts |
| dispersion | float | Standard deviation / mean (%) |
| actual | float | Actual reported value (for completed periods) |

**Behavior:**
- Source: IBES (Institutional Brokers' Estimate System) -- the standard consensus database
- Dispersion is the key "uncertainty" signal: high dispersion = wide range of views
- Compare actual vs estimate for surprise analysis
- Forward P/E = current price / FY1 EPS estimate

**Used by:**
- Skills: `equity-research`
- Commands: `/research-equity`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 7.2 qa_company_fundamentals

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Company identifier |
| periods | int | no | Number of historical fiscal years. Default: 3-5. |

**Output (per fiscal year):**
| Field | Type | Description |
|-------|------|-------------|
| fiscalYear | string | Fiscal year label |
| revenue | float | Total revenue |
| grossProfit | float | Gross profit |
| ebitda | float | EBITDA |
| netIncome | float | Net income |
| totalAssets | float | Total assets |
| totalDebt | float | Total debt |
| equity | float | Shareholders' equity |
| cash | float | Cash and equivalents |
| grossMargin | float | Gross margin (%) |
| operatingMargin | float | Operating margin (%) |
| netMargin | float | Net margin (%) |
| roe | float | Return on equity (%) |
| roic | float | Return on invested capital (%) |
| netDebtToEbitda | float | Net debt / EBITDA ratio |

**Behavior:**
- Historical fiscal year data for trend analysis
- Skills use 3-5 year history to compute margin trends, revenue growth, leverage trajectory

**Used by:**
- Skills: `equity-research`
- Commands: `/research-equity`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 7.3 qa_historical_equity_price

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Company identifier |
| period | string | no | Lookback period (e.g., "1Y", "3M", "YTD") |
| startDate | date | no | Alternative to period: explicit start date |
| endDate | date | no | End date. Defaults to today. |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| prices | array | Time series of price data |
| prices[].date | date | Trading date |
| prices[].open | float | Open price |
| prices[].high | float | High price |
| prices[].low | float | Low price |
| prices[].close | float | Close price |
| prices[].volume | float | Trading volume |
| totalReturn | float | Total return over period (price + dividends) |
| beta | float | Beta vs market index |

**Behavior:**
- Alternative to `tscc_historical_pricing_summaries` for equity-specific history
- Includes total return (dividend-adjusted) which tscc may not
- Beta is pre-computed

**Used by:**
- Skills: `equity-research`, `option-vol-analysis`
- Commands: `/research-equity`, `/analyze-option-vol`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 7.4 qa_macroeconomic

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| search | string | conditional | Mnemonic pattern with wildcards (e.g., "US*GDP*", "EZ*HICP*") |
| description | string | conditional | Description keyword search. One of search/description required. |
| mode | string | no | "latest" (default) or "series" for time series |
| startDate | date | no | For series mode: start of time series |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| indicators | array | Matching macro indicators |
| indicators[].mnemonic | string | LSEG Datastream mnemonic |
| indicators[].description | string | Human-readable description |
| indicators[].value | float | Latest value (or array for series mode) |
| indicators[].date | date | Date of latest observation |
| indicators[].frequency | string | "monthly", "quarterly", "daily" |
| indicators[].units | string | Units (%, index, millions, etc.) |

**Behavior:**
- Backend: LSEG Datastream (33 petabytes of macro data)
- Wildcard search patterns: "US\*GDP\*", "US\*CPI\*", "UK\*UNEMP\*", "EZ\*HICP\*"
- Prefer seasonally adjusted series
- GDP = quarterly; most others = monthly
- Coverage: GDP, CPI, PCE, unemployment, payrolls, PMI, retail sales, industrial production, policy rates
- Countries: US, Eurozone, UK, Japan, China, and most EM economies

**Used by:**
- Skills: `equity-research`, `swap-curve-strategy`, `macro-rates-monitor`
- Commands: `/research-equity`, `/analyze-swap-curve`, `/macro-rates`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< MNEMONIC_FORMAT: ______________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 8. Time Series Domain

### 8.1 tscc_historical_pricing_summaries

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| ric | string | yes | RIC of any instrument (bonds, futures, FX, equities, indices) |
| interval | string | no | "daily" (default), "weekly", "monthly" for interday; "1min", "5min", "15min", "30min", "1hr" for intraday |
| startDate | date | no | Start of history window |
| endDate | date | no | End of history window. Defaults to today. |
| period | string | no | Alternative to start/end: lookback like "3M", "1Y" |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| summaries | array | Historical pricing records |
| summaries[].date | date | Period date |
| summaries[].open | float | Open price |
| summaries[].high | float | High price |
| summaries[].low | float | Low price |
| summaries[].close | float | Close price |

**Behavior:**
- Universal history tool: works for ANY RIC across all asset classes
- This is the most versatile tool for historical context
- Skills use it to compute: realized vol (from close-to-close returns), Z-scores, percentiles, trend direction, 52-week ranges
- For basis analysis: pull both futures and cash bond history to track basis evolution
- Intraday intervals available for recent periods only

**Used by:**
- Skills: `bond-relative-value`, `bond-futures-basis`, `fx-carry-trade`, `swap-curve-strategy`, `option-vol-analysis`, `macro-rates-monitor`
- Commands: `/analyze-bond-rv`, `/analyze-bond-basis`, `/analyze-fx-carry`, `/analyze-swap-curve`, `/analyze-option-vol`, `/macro-rates`

This is tied with `interest_rate_curve` as the **most widely used tool** -- referenced by 6 of 8 skills.

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< IDENTIFIER_FORMAT: ____________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## 9. Fixed Income Analytics Domain (YieldBook)

### 9.1 yieldbook_bond_reference

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Bond identifier(s). Comma-separated for batch. |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| securityType | string | Bond type classification |
| sector | string | Issuer sector |
| ratings | object | Credit ratings (S&P, Moody's, Fitch) |
| couponRate | float | Coupon rate (%) |
| couponFrequency | string | Payment frequency |
| maturityDate | date | Maturity date |
| issuer | string | Issuer name |
| currency | string | ISO currency |
| callProvisions | object | Embedded call schedule (if callable) |
| putProvisions | object | Embedded put schedule (if puttable) |

**Behavior:**
- Reference/static data, not pricing
- Used to build portfolio composition analysis: sector breakdown, rating distribution, maturity buckets
- Call provisions needed to determine if `fixed_income_risk_analytics` (OAS) is required

**Used by:**
- Skills: `fixed-income-portfolio`
- Commands: `/review-fi-portfolio`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 9.2 yieldbook_cashflow

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Bond identifier(s) |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| cashflows | array | Projected payment schedule |
| cashflows[].date | date | Payment date |
| cashflows[].coupon | float | Coupon payment amount |
| cashflows[].principal | float | Principal payment amount (redemption, amortization) |
| cashflows[].total | float | Total cash (coupon + principal) |

**Behavior:**
- Projects future coupon and principal payments
- Skills aggregate into quarterly cashflow waterfalls for portfolio analysis
- Flag concentration periods (e.g., large chunk of portfolio maturing in one quarter)

**Used by:**
- Skills: `fixed-income-portfolio`
- Commands: `/review-fi-portfolio`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 9.3 yieldbook_scenario

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Bond identifier(s) |
| scenarios | array[int] | yes | Parallel rate shifts in basis points (e.g., [-200, -100, -50, 0, 50, 100, 200]) |

**Output (per bond per scenario):**
| Field | Type | Description |
|-------|------|-------------|
| scenario | int | Rate shift applied (bp) |
| price | float | Bond price under scenario |
| yield | float | Bond yield under scenario |
| priceChange | float | Change from base price |
| pnl | float | P&L per 100 notional |

**Behavior:**
- Parallel shift scenarios: the entire curve moves up/down by the specified amount
- Standard set used by skills: -100bp, -50bp, 0bp, +50bp, +100bp
- Extended set for portfolio review: -200bp through +200bp
- Skills identify top risk contributors (bonds with largest scenario P&L)

**Used by:**
- Skills: `bond-relative-value`, `fixed-income-portfolio`
- Commands: `/analyze-bond-rv`, `/review-fi-portfolio`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

### 9.4 fixed_income_risk_analytics

**Pattern:** Direct

**Input:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| identifier | string | yes | Bond identifier(s) |

**Output:**
| Field | Type | Description |
|-------|------|-------------|
| oas | float | Option-adjusted spread (bp) |
| effectiveDuration | float | Effective duration (years) |
| keyRateDurations | object | Duration contribution at each tenor bucket |
| keyRateDurations.2Y | float | KRD at 2Y point |
| keyRateDurations.5Y | float | KRD at 5Y point |
| keyRateDurations.10Y | float | KRD at 10Y point |
| keyRateDurations.30Y | float | KRD at 30Y point |
| convexity | float | Effective convexity |

**Behavior:**
- Primarily for bonds with embedded options (callable, puttable) where modified duration is inadequate
- OAS removes the option component from the spread, giving "true" credit spread
- Key rate durations show exposure to specific points on the curve
- Model: Hull-White interest rate model (configurable mean reversion + vol parameters)

**Used by:**
- Skills: `bond-relative-value`, `fixed-income-portfolio`
- Commands: `/review-fi-portfolio`

**Internal Mapping:**
```
<< INTERNAL_TOOL: ________________________________________________ >>
<< NOTES: ________________________________________________________ >>
```

---

## Tool Dependency Matrix

Which tools each skill requires (X = primary dependency, o = optional/supplementary):

```
                          bond  bond   fx    fx    ir    cred  infl  fx    ir    opt   opt   fx    eq    ibes  co    hist  macro tscc  yb    yb    yb    fi
                          price fut    spot  fwd   curve curve curve fwd   swap  val   tmpl  vol   vol   cons  fund  eq    macro hist  ref   cf    scen  risk
                                price  price price                   curve                   surf  surf              price
bond-relative-value        X                       X     X                                                          X                       o     X     o
bond-futures-basis         X     X                 X     o                                                          X
fx-carry-trade                         X     X     X                 X                 X                            X
swap-curve-strategy                                X           X           X                                  X     X
option-vol-analysis                                                        X     X     X     X                X     X
equity-research                                                                                    X     X   X     X           X
fixed-income-portfolio     X                       X                                                                X     X     X     X     X
macro-rates-monitor                                X           X           X                                  X     X
```

## Minimum Viable Implementation

To get the maximum number of skills running with the fewest tools implemented:

| Priority | Tool | Enables |
|----------|------|---------|
| 1 | `interest_rate_curve` | Required by 6/8 skills |
| 2 | `tscc_historical_pricing_summaries` | Required by 6/8 skills |
| 3 | `bond_price` | Required by 3/8 skills (all FI skills) |
| 4 | `qa_macroeconomic` | Required by 3/8 skills |
| 5 | `ir_swap` | Required by 2/8 skills |
| 6 | `inflation_curve` | Required by 2/8 skills |

Implementing just these 6 tools enables partial functionality for 7 of 8 skills. The remaining 17 tools add depth (credit curves, vol surfaces, options, equity fundamentals, YieldBook analytics).
