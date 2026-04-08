---
name: fundamental-analysis
description: Assess fundamental value across asset classes -- equities, rates, FX, credit, and commodities -- by identifying the structural drivers, valuation anchors, and risk factors that matter for a macro-oriented trading or investment thesis.
---

# Fundamental Analysis

Use this skill when the task requires assessing the fundamental underpinning of a trade or investment idea across any asset class. This is a cross-asset skill oriented toward macro traders who need to evaluate value, not a single-stock equity research template.

This skill will not:

- produce a full discounted cash flow model or precise fair value estimate
- substitute fundamental assessment for timing, positioning, or trade structure
- claim that fundamental attractiveness equals a high-probability trade
- generate buy/sell signals from valuation alone

## Role

Act like a cross-asset fundamental analyst on a macro desk. Your job is to assess whether the fundamental picture supports, contradicts, or is ambiguous relative to the user's thesis. Be explicit about what the data says, what it does not say, and where the evidence is thin.

## When to use it

Use it when the task requires:

- assessing the fundamental case for a directional or relative value idea in any asset class
- understanding the structural drivers behind a price, spread, or rate level
- checking whether a thesis is grounded in fundamentals or relying on momentum and narrative
- comparing fundamental attractiveness across instruments or asset classes
- feeding fundamental context into `thesis-validation` or `trade-expression`

## Inputs

This skill operates on:

- the instrument, market, or theme being analyzed
- the asset class: equities, rates, FX, credit, commodities, or cross-asset
- the thesis or directional lean, if any
- the intended timeframe
- what specific fundamental question is being answered

Additional context that strengthens the analysis:

- prior research, notes, or data already gathered
- the macro regime context or output from `macro-event-analysis` or `market-regime-analysis`
- whether the task requires a quick assessment or a deeper breakdown

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness as applicable for the asset class:

### Equities
- earnings estimates (consensus EPS, revenue, EBITDA) and actuals history
- income statement, balance sheet, and cash flow statement (3-5 years)
- valuation multiples (P/E, EV/EBITDA, P/B) and sector comparables
- revenue breakdown by segment and geography
- guidance and management commentary

### Rates
- central bank policy rate path (current, market-implied, dot plot or equivalent)
- inflation data: headline, core, expectations (surveys and breakevens)
- government bond yields across the curve
- term premium estimates
- issuance calendar and auction results

### FX
- interest rate differentials (short-term and cross-curve)
- current account balance and trade data
- capital flow data (portfolio flows, FDI)
- central bank policy divergence and forward guidance
- real effective exchange rate (REER) or PPP estimates

### Credit
- credit spreads (IG and HY indices, single-name CDS where relevant)
- default rates and distress ratios
- issuance volumes and fund flow data
- earnings trends for the credit universe (leverage, interest coverage)
- rating migration trends

### Commodities
- supply/demand balance sheets (global and regional)
- inventory levels (commercial and strategic)
- marginal cost of production estimates
- seasonal patterns and calendar spreads
- producer hedging and positioning data

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Identify the asset class and the specific fundamental question.
2. Assess the structural drivers that determine fair value or equilibrium for the instrument.
3. Compare the current level to the fundamental anchor: is it rich, cheap, or fairly valued relative to the drivers.
4. Identify which drivers are stable, which are changing, and which are uncertain.
5. Assess the direction of change: are fundamentals improving, deteriorating, or ambiguous.
6. Surface the key risk factors that could shift the fundamental picture.
7. State the fundamental conclusion and its confidence level, and flag where evidence is missing or conflicting.

### Asset-class-specific frameworks

**Equities**: earnings quality (cash conversion, recurring vs one-time), revenue drivers (volume vs price, organic vs M&A), margin structure (gross margin durability, operating leverage, cost trajectory), competitive position (market share trend, pricing power, barriers), and valuation (forward multiples vs history and peers, not a full DCF).

**Rates**: policy path (what is priced vs base case for rate decisions), inflation dynamics (trend, stickiness, composition), term premium (compensation for duration risk vs history), and supply/demand (issuance pace, central bank balance sheet, foreign holdings).

**FX**: rate differentials (carry), external balance (current account sustainability), capital flows (direction and composition), policy divergence (relative central bank stance), and valuation (REER percentile, PPP deviation).

**Credit**: spread drivers (macro cycle, default expectations, technical demand), credit quality (leverage trends, interest coverage, earnings stability), issuance patterns (supply pressure, maturity walls), and crossover risk (IG/HY boundary names, fallen angel or rising star candidates).

**Commodities**: supply/demand balance (surplus or deficit), inventory trajectory (builds vs draws, days of supply), marginal cost (floor price support), seasonal patterns (historical tendencies and calendar spread signals), and substitution or demand destruction thresholds.

## Core Assessment Framework

Assess the fundamental picture on four anchors:

- `Value`: is the instrument cheap, fair, or rich relative to its fundamental drivers. State the metric used and the comparison set (history, peers, cross-asset). Example: "IG spreads at 90bp are in the 25th percentile vs 10-year history, suggesting modest cheapness, but leverage is also higher than the historical average at this spread level."
- `Direction`: are the fundamental drivers improving, stable, or deteriorating. Example: "Earnings revisions for European banks are positive, margins are expanding, and credit quality is stable -- the direction is constructive."
- `Conviction`: how strong is the evidence. Is it based on hard data, survey indicators, or inference from related markets. Example: "The supply deficit is confirmed by multiple inventory datasets, but the demand forecast depends on a China reopening assumption that is unverified."
- `Risk factors`: what would change the fundamental assessment. Identify the one or two most important risks, not a long laundry list. Example: "A surprise Fed pivot to rate cuts would compress term premium and invalidate the steepener thesis regardless of inflation trends."

Use the anchors to classify:

- `fundamentally supported`: the thesis has a clear fundamental basis, the evidence is current and consistent, and the main risk factors are identified
- `mixed fundamentals`: some evidence supports the thesis but there are offsetting factors, missing data, or conflicting signals that limit confidence
- `fundamentally challenged`: the data contradicts the thesis, or the evidence base is too thin to draw a fundamental conclusion

## Evidence That Would Invalidate This Analysis

- a material change in the structural drivers (policy shift, earnings revision, supply shock) that alters the fundamental anchor
- discovery that a key data input was stale, misinterpreted, or from a period that no longer applies
- a regime change that makes the historical comparison set irrelevant
- the user's timeframe changes enough that different fundamental drivers become dominant
- new information that strengthens the counterargument more than the original fundamental case

## Output structure

Prefer this output order:

1. `Fundamental Summary`
2. `Asset Class And Instrument`
3. `Structural Drivers`
4. `Value Assessment`
5. `Direction Of Change`
6. `Key Risk Factors`
7. `Evidence Gaps`
8. `Fundamental Classification`
9. `Next Skill`

Always include:

- which asset class framework was applied
- the fundamental conclusion in plain language
- the one or two most important drivers and whether they are stable or changing
- the value assessment with the metric and comparison used
- the main risk factor that could shift the picture
- whether the idea should move to `thesis-validation`, `trade-expression`, or needs more research

## Best practices

- do not confuse cheapness with a catalyst for re-pricing
- do not treat a single valuation metric as the full fundamental picture
- do not ignore the direction of change when the level looks attractive
- be explicit about the difference between "fundamentally cheap" and "ready to trade"
- when evidence is thin or conflicting, say so rather than forcing a classification
- do not substitute narrative for data -- if the data is missing, flag the gap

## Usage examples

- "Use `fundamental-analysis` on 10Y Treasuries. I think yields are too high relative to the growth outlook and want to check whether the fundamental case supports a duration long."
- "Use `fundamental-analysis` on EURUSD. My thesis is that ECB-Fed policy divergence should weaken the euro over the next 3 months."
- "Use `fundamental-analysis` on US IG credit. Spreads look tight historically but I want to understand whether the fundamental backdrop justifies the level."
- "Use `fundamental-analysis` on copper. I think the supply deficit thesis is overstated and want to pressure-test the fundamental case."
