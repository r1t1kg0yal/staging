---
name: fi-relative-value
description: Analyze fixed income relative value across bonds, futures basis, and swap curves by decomposing spreads, assessing richness or cheapness, and identifying dislocations that may represent trading opportunities.
---

# Fixed Income Relative Value

Use this skill when the task is to evaluate whether a bond, spread, basis, or curve position is rich, cheap, or fair relative to its fundamental and technical drivers. This skill covers the core relative value toolkit for rates markets.

This skill will not:

- guarantee that a cheap bond will converge to fair value on any timeline
- substitute spread analysis for macro or policy assessment
- replace risk management or position sizing
- treat a historically wide spread as automatically attractive without examining why

## Role

Act like a rates strategist on a relative value desk. Your job is to decompose spreads into their components, compare instruments on a like-for-like basis, and identify where the market may be mispricing risk. Be precise about what the spread is telling you and what it is not.

## When to use it

Use it when the task requires:

- assessing whether a bond is rich or cheap relative to the curve, peers, or its own history
- analyzing the cash-futures basis and delivery option value
- evaluating swap spreads, cross-currency basis, or asset swap levels
- identifying curve trades (steepeners, flatteners, butterflies) with a relative value rationale
- decomposing a total spread into risk-free, credit, and residual components
- feeding a relative value view into `trade-expression`, `thesis-validation`, or `position-sizing`

## Inputs

This skill operates on:

- the instrument or trade structure being evaluated
- the currency and market (e.g., US Treasuries, EUR govvies, USD swaps)
- whether the focus is cash bonds, futures basis, swap curve, or a combination
- the user's thesis or directional lean, if any
- the intended holding period
- any benchmark or comparison set relevant to the analysis

Additional context that strengthens the analysis:

- recent output from `macro-event-analysis` or `market-regime-analysis` for context
- specific bonds, contracts, or tenors being compared
- historical spread data or charts already available

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

### Bond relative value
- bond prices: clean and dirty price, yield to maturity, duration, convexity, DV01
- government yield curve at standard tenors for the relevant currency
- credit spread curves by issuer type (sovereign, agency, corporate) for credit bonds
- Z-spread or OAS for structured or callable bonds
- historical spread data for percentile context (3M, 6M, 1Y, 3Y lookbacks)

### Futures basis
- bond futures price, fair value, and delivery basket with conversion factors
- cheapest-to-deliver (CTD) bond identification and analytics
- CTD cash bond price, yield, duration, DV01
- short-term repo or funding rate for implied repo comparison
- historical basis and implied repo data for trend and percentile context

### Swap curve
- par swap rates at standard tenors (2Y, 5Y, 7Y, 10Y, 20Y, 30Y)
- government yield curve for swap spread computation
- inflation breakeven curve for real rate decomposition
- DV01 at each tenor for hedge ratio and trade sizing
- historical curve slope data (2s10s, 5s30s, butterfly) for context

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

### Bond relative value

1. Price the target and comparison bonds. Extract yield, spread, duration, and convexity.
2. Compute the G-spread (spread over the interpolated government curve) for each bond.
3. If credit bonds, isolate the credit component using the relevant credit curve. Compute residual spread (G-spread minus credit curve spread). The residual captures liquidity premium, technicals, and potential mispricing.
4. Compare the residual spread to its own history. A residual in the top or bottom decile relative to the past 1-3 years is a stronger signal than one near the median.
5. Run scenario analysis: compute price change under parallel shifts of -100bp, -50bp, +50bp, +100bp. Assess asymmetry in the P&L profile.
6. Synthesize into a rich/cheap assessment. State the primary spread metric, its historical percentile, the residual signal, and how many basis points of spread move would change the conclusion.

### Futures basis

1. Identify the CTD bond for the futures contract. Note the conversion factor and delivery dates.
2. Price both the future and the CTD cash bond. Compute gross basis (cash price minus futures price times conversion factor).
3. Compute carry (coupon accrual minus financing cost over the delivery period). Derive net basis (gross basis minus carry), which represents the embedded delivery option value.
4. Compute implied repo rate from the basis. Compare to the prevailing short-term funding rate. If implied repo is below market repo, the future is rich (expensive relative to cash). If above, the future is cheap.
5. Assess the historical context of the net basis and implied repo. A net basis at extreme percentiles may indicate a trading opportunity, but also check whether structural factors (squeeze risk, supply, regulation) explain the dislocation.
6. Evaluate CTD stability: how close are the next-cheapest bonds to switching. A tight CTD race increases delivery option value and can widen the net basis independent of directional views.

### Swap curve

1. Build the swap curve at standard tenors. Compute the swap rate, DV01, and if available, NPV at each point.
2. Overlay the government curve. Compute swap spreads (swap rate minus government yield) at each tenor. Assess whether swap spreads are wide or tight versus history and whether the term structure of swap spreads is normal.
3. If inflation data is available, decompose nominal swap rates into real rate and inflation breakeven components. Assess whether real rates are restrictive or accommodative relative to the central bank's stated stance.
4. Compute curve metrics: 2s10s slope, 5s30s slope, 2s5s10s butterfly. Compare to historical ranges.
5. For any identified curve trade, compute DV01-neutral sizing across the legs. Estimate 3-month carry and roll-down. Calculate the breakeven curve move (how much the curve must move against the trade before carry is exhausted).
6. State the curve shape classification (normal, flat, inverted, humped) and whether the shape is consistent with the macro backdrop from available context.

## Core Assessment Framework

Assess the relative value picture on four anchors:

- `Spread Level`: where is the spread, basis, or curve metric relative to its historical distribution. State the percentile and the lookback period. Example: "The 2s10s swap curve slope at -15bp is in the 10th percentile of the past 5 years, suggesting it is unusually flat."
- `Spread Direction`: is the spread widening, tightening, or range-bound. Recent trajectory matters because a cheap spread that is still cheapening may require patience. Example: "Net basis has been widening for 3 weeks, driven by increased hedging demand from dealers."
- `Fundamental Consistency`: does the spread level make sense given the macro and policy environment, or is there a disconnect. Example: "Swap spreads are tight, but issuance is heavy and reserve balances are declining -- the fundamental picture suggests spreads should be wider."
- `Structural Or Technical Factors`: are there non-fundamental forces (regulation, positioning, supply, central bank operations) that explain the dislocation and may persist. Example: "The negative cross-currency basis partly reflects structural dollar funding demand from Japanese insurers, which is unlikely to reverse quickly."

Use the anchors to classify:

- `actionable dislocation`: the spread or basis is at an extreme level, the direction is stabilizing or reversing, the fundamental picture supports convergence, and structural factors are not expected to persist
- `interesting but not yet actionable`: the level looks attractive, but the direction is still moving against, the fundamental picture is mixed, or structural forces may sustain the dislocation
- `fair value or no edge`: the spread is near its historical median, consistent with fundamentals, and does not offer a compelling risk-adjusted opportunity

## Output tables

### Spread Decomposition
| Component | Spread (bp) | % of Total |
|-----------|-------------|------------|
| G-spread (total over govt) | ... | 100% |
| Credit curve spread | ... | ...% |
| Residual (liquidity + technicals) | ... | ...% |

### Basis Summary
| Metric | Value |
|--------|-------|
| Gross Basis | ... ticks |
| Carry | ... ticks |
| Net Basis (BNOC) | ... ticks |
| Implied Repo | ...% |
| Market Repo (approx) | ...% |
| Net Basis Percentile (vs 1Y) | ...th |
| Assessment | Rich / Fair / Cheap |

### Swap Curve Table
| Tenor | Swap Rate (%) | Govt Yield (%) | Swap Spread (bp) | DV01 |
|-------|---------------|----------------|-------------------|------|
| 2Y | ... | ... | ... | ... |
| 5Y | ... | ... | ... | ... |
| 10Y | ... | ... | ... | ... |
| 30Y | ... | ... | ... | ... |

### Curve Metrics
| Metric | Current | 1Y Avg | Percentile |
|--------|---------|--------|------------|
| 2s10s slope (bp) | ... | ... | ...th |
| 5s30s slope (bp) | ... | ... | ...th |
| 2s5s10s butterfly (bp) | ... | ... | ...th |

### Scenario P&L
| Scenario | Price Change | P&L (per 100 notional) |
|----------|-------------|------------------------|
| -100bp | ... | ... |
| -50bp | ... | ... |
| Base | ... | ... |
| +50bp | ... | ... |
| +100bp | ... | ... |

## Evidence That Would Invalidate This Analysis

- a central bank policy decision or communication that materially shifts the rate environment
- a change in issuance patterns, regulation, or market structure that alters the structural component of spreads
- the CTD bond switches, changing the basis dynamics for a futures trade
- the user's holding period changes enough that carry and roll-down assumptions no longer apply
- discovery that historical data used for percentile context was from a structurally different regime (e.g., pre-QE vs post-QE)

## Output structure

Prefer this output order:

1. `Relative Value Summary`
2. `Instrument And Market`
3. `Spread Decomposition` or `Basis Summary` or `Swap Curve Table` (as applicable)
4. `Historical Context`
5. `Scenario Analysis`
6. `Assessment And Classification`
7. `Key Risk Factors`
8. `Next Skill`

Always include:

- the primary spread or basis metric and its current level
- the historical percentile and lookback period
- the decomposition into components (risk-free, credit, residual, or carry, basis, delivery option)
- whether the dislocation is fundamental, technical, or structural in nature
- the main risk that could prevent convergence
- whether the idea should move to `trade-expression`, `position-sizing`, or needs more context from `macro-event-analysis`

## Best practices

- do not assume mean reversion without checking whether the structural environment has changed
- do not conflate a wide spread with a cheap spread if the credit or fundamental risk has also increased
- always state the comparison set and time window when citing percentiles
- distinguish between relative value within a curve and relative value across markets
- for basis trades, always check CTD stability before sizing
- for curve trades, always compute carry and roll-down alongside the directional view

## Usage examples

- "Use `fi-relative-value` to assess whether 10Y Treasuries are cheap vs the curve and vs history. I think yields have overshot the move."
- "Use `fi-relative-value` on the UST 10Y futures basis. I want to know whether the basis is offering a good entry for a long-basis trade."
- "Use `fi-relative-value` on the EUR swap curve. I am looking at a 2s10s steepener and want to understand carry, roll-down, and historical context."
- "Use `fi-relative-value` to compare Bund-Treasury spread dynamics. I think the cross-market spread is too wide given ECB-Fed convergence."
