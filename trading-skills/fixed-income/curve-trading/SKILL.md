---
name: curve-trading
description: Analyze and construct yield curve trades -- steepeners, flatteners, and butterflies -- with DV01-neutral sizing, carry/rolldown estimation, and regression-based weight optimization. Use when evaluating curve shape, identifying curve dislocations, or constructing curve RV trades.
---

# Curve Trading

Use this skill when the task is to analyze yield curve shape and construct curve trades. This covers steepeners, flatteners, butterflies, and more complex curve structures with proper DV01-neutral sizing, carry and rolldown estimation, and regression-based weight optimization to isolate pure relative value from hidden factor exposures.

This skill will not:

- predict the direction of outright rates (use `trade-expression` for directional views)
- replace fundamental analysis of what drives the curve shape (use `macro-event-analysis` for that)
- guarantee that historically flat or steep curves will revert to historical norms
- treat 50:50 butterfly weights as correct without checking for hidden factor exposure

## Role

Act like a curve trader on a rates desk. You think in terms of DV01-neutral structures, carry/rolldown, and regression residuals. You know that most raw curve metrics embed hidden factor exposures (rate level, wing slope) that must be stripped out to isolate pure relative value. You size using DV01 weights, not notional weights.

## When to use it

Use it when the task requires:

- analyzing yield curve shape (normal, flat, inverted, humped) and what it signals
- constructing a steepener or flattener with proper DV01-neutral sizing
- building a butterfly trade with regression-based weights that neutralize hidden factor exposures
- estimating carry, rolldown, and breakeven curve moves for a proposed trade
- comparing curve metrics (2s10s, 5s30s, 2s5s10s) to historical ranges
- identifying curve dislocations between sectors or across markets
- feeding a curve view into `trade-expression`, `position-sizing`, or `fi-relative-value`

## Inputs

This skill operates on:

- the curve being analyzed (e.g., US Treasuries, USD swaps, Bunds, JGBs)
- the specific tenors involved (e.g., 2s10s, 5s30s, 2s5s10s butterfly)
- whether the focus is a two-leg curve trade or a three-leg butterfly
- the user's thesis on curve direction or RV
- the intended holding period
- whether this is a standalone curve trade or part of a broader structure

Additional context that strengthens the analysis:

- output from `macro-event-analysis` for policy and growth backdrop
- output from `fi-relative-value` for broader RV context
- historical regression parameters if available
- mortgage hedging or supply flow context

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- government bond or swap yields at all standard tenors (2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y)
- DV01 per unit notional at each tenor for sizing
- historical curve slopes and butterfly metrics (2s10s, 5s30s, 2s5s10s, and any custom metrics) over 1Y, 3Y, 5Y lookbacks
- carry and rolldown estimates at each tenor (from the forward curve or explicit calculation)
- for butterflies: historical regression data or sufficient price history to compute regression weights
- repo financing rates for carry calculation on cash bond positions

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Curve trade mechanics

### Steepeners and flatteners (two-leg)

A steepener profits when the yield curve steepens (short-end yields fall relative to long-end, or long-end rises relative to short-end). A flattener profits from the opposite.

**DV01-neutral construction:**
- Match the DV01 of both legs so the trade is immune to parallel rate shifts
- Notional of each leg = target DV01 / (DV01 per unit notional at that tenor)
- Because DV01/notional varies enormously across maturities, notionals will differ significantly

**Carry and rolldown:**
- Carry: net coupon income minus financing cost across both legs
- Rolldown: expected P/L from curve aging (bonds moving down the curve over time), assuming the curve shape persists
- Combined carry + rolldown is the income earned if the curve does not move
- Breakeven curve move: how much the slope must move against the trade before carry + rolldown is exhausted

### Butterflies (three-leg)

A butterfly trades the body (middle tenor) against the wings (short and long tenors). Standard expression: long wings, short body (profits if body cheapens relative to wings) or vice versa.

**The 50:50 butterfly problem:**
- Equal DV01 weighting (50% of body DV01 to each wing) is the default but embeds hidden factor exposures
- A 50:50 2s5s10s butterfly has exposure to: (a) the 5Y yield level, and (b) the 2s10s slope
- These hidden factors can dominate the butterfly, making a supposed RV trade actually a disguised directional or curve bet

**Regression-based weight optimization:**
1. Regress the 50:50 butterfly value against the body yield level and a wing curve metric (e.g., 2s10s slope)
2. The partial betas (beta1 for body yield, beta2 for wing curve) reveal the hidden factor sensitivities
3. Compute neutral weights:
   - Short-end wing weight = (0.5 + beta2) / (1 - beta1)
   - Long-end wing weight = (0.5 - beta2) / (1 - beta1)
4. These weights are DV01 weights, not notional weights. Convert to notionals using each leg's DV01/unit.
5. The residual from this regression is the pure RV component. Trade the residual, not the raw butterfly.

**Shortcut:** regress the body yield directly against both wing yields. The regression coefficients are the risk weights.

**Why equal weighting fails:** it implicitly assumes equal sector volatility. When the Fed is on hold, 2Y is far less volatile than 10Y, so 50:50 gives the 10Y leg too much implicit weight.

### Weighted carry trades

An outright carry trade (e.g., long 5Y) earns carry but takes full directional exposure. A curve combination (weighted steepener or butterfly) can maintain high carry while dramatically reducing vol through offsetting exposures.

**Weighting method for carry optimization:**
- Regress daily changes of one leg against the other; the beta is the weight that removes the vol differential
- The weighted trade's vol = standard deviation of the weighted spread's daily changes (much lower than either leg alone)
- A weighted trade often has a higher carry/vol ratio than the outright despite lower absolute carry

## Analysis process

1. **Assess current curve shape.** Compute key slope metrics (2s10s, 5s30s, 2s5s10s butterfly, any custom combos). Classify: normal, flat, inverted, humped.

2. **Historical context.** Place current metrics in percentile context over 1Y, 3Y, and 5Y windows. Identify which sectors are at extremes.

3. **Fundamental consistency.** Does the curve shape make sense given the macro backdrop?
   - Fed on hold / easing: front-end anchored, steepening expected
   - Fed hiking: front-end leading, flattening expected
   - Recession pricing: inversion, especially 2s10s
   - Supply-driven: belly/long-end steepening from heavy issuance
   - Term premium: long-end steepening from risk premium expansion

4. **Construct the trade.** For the identified opportunity:
   - Choose the legs and determine DV01-neutral sizing
   - For butterflies: compute regression-based weights (not 50:50 unless confirmed neutral)
   - Convert DV01 weights to notional weights using each leg's DV01/unit
   - Estimate carry + rolldown for each leg and net
   - Compute breakeven curve move

5. **Risk assessment.** Identify what could move the curve against the trade beyond the carry buffer:
   - Policy surprise (hawkish/dovish shift)
   - Supply event (QRA, large auction)
   - Mortgage extension/contraction flow
   - Cross-market spillover (e.g., JGB curve move transmitting to UST)

## Core Assessment Framework

Assess the curve trade on four anchors:

- `Curve Level`: where is the slope or butterfly metric relative to history. State percentile and lookback.
- `Carry/Rolldown Profile`: is the trade positive or negative carry? What is the breakeven curve move? A positive-carry curve trade with a large breakeven is structurally more attractive.
- `Fundamental Alignment`: does the curve thesis align with the macro backdrop, or is it fighting the fundamental driver?
- `Hidden Factor Exposure`: for butterflies, are the weights properly optimized, or does the trade embed unwanted directional or slope exposure?

Use the anchors to classify:

- `attractive curve trade`: metric at historical extreme, positive carry, fundamental alignment, properly weighted
- `moderate conviction`: metric is extended but carry is flat or slightly negative, or fundamentals are mixed
- `avoid`: metric is mid-range, carry is negative, or the curve thesis fights the dominant fundamental driver

## Output tables

### Curve Metrics
| Metric | Current (bp) | 1Y Avg | 3Y Avg | 1Y Percentile | 3Y Percentile |
|--------|-------------|--------|--------|---------------|---------------|
| 2s10s | ... | ... | ... | ...th | ...th |
| 5s30s | ... | ... | ... | ...th | ...th |
| 2s5s10s BF | ... | ... | ... | ...th | ...th |

### Trade Construction
| Leg | Tenor | Direction | DV01 Weight | Notional | Carry (bp/3M) | Rolldown (bp/3M) |
|-----|-------|-----------|-------------|----------|---------------|------------------|
| Wing 1 | ... | ... | ...% | ... | ... | ... |
| Body | ... | ... | 100% | ... | ... | ... |
| Wing 2 | ... | ... | ...% | ... | ... | ... |
| **Net** | | | | | **...** | **...** |

### Risk Profile
| Metric | Value |
|--------|-------|
| Net Carry + Rolldown (bp/3M) | ... |
| Breakeven Curve Move (bp) | ... |
| Regression R-squared | ... |
| Hidden Factor Exposure | Neutralized / Residual ... |

## Evidence that would invalidate this analysis

- a policy surprise that changes the rate path embedded in the front-end
- a shift in issuance strategy that alters supply dynamics at specific tenors
- a regime change in mortgage hedging that shifts the curve's directional sensitivity
- the regression relationship between body and wings breaks down (structural change)
- cross-market spillover from a foreign curve move that overrides domestic fundamentals
- a change in the user's holding period that alters the carry/rolldown calculus

## Output structure

Prefer this output order:

1. `Curve Trade Summary`
2. `Current Curve Shape And Metrics` (table)
3. `Historical Context`
4. `Fundamental Assessment`
5. `Trade Construction` (table)
6. `Carry And Rolldown Analysis`
7. `Risk Profile` (table)
8. `Next Skill`

Always include:

- the specific curve metric and its current percentile
- DV01-neutral sizing (and regression-based weights for butterflies)
- carry + rolldown estimate and breakeven
- fundamental alignment assessment
- whether the idea should move to `position-sizing`, `execution-plan-check`, or needs more context

## Best practices

- always use DV01 weights, never notional weights, for curve trades; the difference can be enormous across maturities
- never use 50:50 butterfly weights without regression verification; hidden factor exposure can dominate the trade
- when the Fed is on hold, 2Y vol is suppressed, which distorts equal-weighted butterflies
- rolldown cannot be locked in (it depends on the curve shape persisting); carry can be locked via term repo
- a carry-efficient curve structure (weighted to minimize vol while preserving carry) often has a better carry/vol ratio than an outright position with higher absolute carry
- if mean reversion of a curve metric fails for an extended period, the long-run average itself may have moved; persistent non-reversion is an exit signal, not a patience signal
- cross-market curve correlation is increasing; monitor JGB, Bund, and Gilt curves for spillover

## Usage examples

- "Use `curve-trading` to evaluate a 2s10s steepener in US Treasuries. The curve is near its flattest in 3 years and I think the Fed is done hiking."
- "Use `curve-trading` to build a 2s5s10s butterfly with proper regression weights. I think the 5Y sector is cheap relative to 2s and 10s."
- "Use `curve-trading` to compare carry profiles across 2s10s, 5s30s, and 2s5s10s. I want the most carry-efficient curve expression."
- "Use `curve-trading` to assess whether the JGB 10s30s steepening is transmitting to US long-end curve metrics."
