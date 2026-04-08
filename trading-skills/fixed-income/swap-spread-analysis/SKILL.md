---
name: swap-spread-analysis
description: Analyze swap spreads by decomposing them into their drivers (credit, mortgage hedging, supply, pension demand, corporate issuance, liquidity), assessing which driver dominates in the current regime, and identifying spread trading opportunities. Use when evaluating swap spread wideners/tighteners, understanding driver rotation, or using swap spreads as a fiscal or funding signal.
---

# Swap Spread Analysis

Use this skill when the task is to analyze swap spreads -- the difference between swap rates and government bond yields at matched maturities. Swap spreads encode information about credit conditions, mortgage hedging flows, Treasury supply, funding stress, and structural demand patterns. This skill decomposes those drivers and identifies which one dominates in the current regime.

This skill will not:

- predict swap spread direction from a single driver (multiple drivers interact and rotate)
- treat swap spreads as a pure credit signal (they reflect much more than bank credit risk)
- replace macro analysis (use `macro-event-analysis` or `cross-asset-playbook` for the broader picture)
- guarantee that a historically wide or tight swap spread will revert

## Role

Act like a rates strategist who specializes in swap spread dynamics. You understand that the same spread responds to completely different dominant factors depending on the regime. Your job is to identify which driver is dominant now, whether the spread level is consistent with that driver, and where there may be a dislocation or transition.

## When to use it

Use it when the task requires:

- evaluating whether swap spreads are wide or tight relative to fundamentals and history
- decomposing swap spread moves into their component drivers
- identifying which driver is dominant in the current regime (credit, mortgage, supply, pension, issuance, liquidity)
- trading swap spread wideners or tighteners
- using swap spreads as a signal for funding conditions or fiscal dynamics
- comparing swap spread behavior across maturities (front-end vs belly vs long-end have different driver profiles)
- feeding swap spread analysis into `fi-relative-value`, `cross-asset-playbook`, or `trade-expression`

## Inputs

This skill operates on:

- the currency and maturity of the swap spread being analyzed (e.g., USD 10Y, EUR 5Y)
- whether the focus is a single maturity or the term structure of swap spreads
- the user's directional lean or thesis, if any
- the intended holding period
- whether the trade is an outright spread position or part of a broader structure

Additional context that strengthens the analysis:

- output from `macro-event-analysis` for upcoming supply events (auctions, refunding)
- output from `repo-funding-analysis` for funding conditions
- mortgage market data (refi index, MBS duration, convexity hedging flow)
- corporate issuance calendar
- pension fund demand indicators

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- par swap rates at standard tenors (2Y, 5Y, 7Y, 10Y, 20Y, 30Y) for the relevant currency
- government bond yields at matched maturities (matched-maturity spread, not headline)
- swap spreads at each tenor (swap rate minus government yield)
- historical swap spread data (3M, 6M, 1Y, 3Y) for percentile context
- DV01 at each tenor for sizing any proposed trades
- repo rates and funding conditions (GC repo, SOFR-FF spread) for funding driver assessment
- mortgage-related indicators if available (refi index, MBS duration, extension/contraction signals)
- Treasury auction calendar and recent supply data
- corporate issuance volumes (recent and upcoming)

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Driver framework

Swap spreads are driven by multiple forces that rotate in dominance. The same spread can widen for completely different reasons in different regimes:

### Bank credit (dominant in crises)
- Swap rates embed interbank credit risk; Treasuries are risk-free
- Systemic stress widens spreads overwhelmingly (2007-08: 2Y from 30bp to 150bp+)
- During genuine credit events, this driver dominates all others
- Assessment: check bank CDS, funding stress indicators, TED spread or equivalent

### Mortgage hedging (dominant day-to-day in normal markets)
- Mortgage holders are short a prepayment option (homeowner can refi)
- Rates rise: prepayments slow, duration extends, servicers forced to pay fixed in swaps to hedge, widening pressure
- Rates fall: prepayments accelerate, duration shortens, hedgers receive fixed, narrowing pressure
- Creates directional correlation between swap spreads and yields even though spreads are not inherently rate-level products
- Feedback loop: can persist for months in intense form during large rate moves
- Assessment: monitor refi indices, MBS duration extension, mortgage origination activity

### Treasury supply / fiscal (slow-moving, structural)
- More Treasury supply cheapens Treasuries relative to swaps, narrowing swap spreads
- Structural deficit: persistent narrowing pressure over years
- Cyclical deficit: limited and temporary narrowing
- Assessment: track QRA announcements, coupon vs bill issuance mix, auction schedule, fiscal trajectory

### Pension demand (long end, multi-decade, structural)
- Defined-benefit pension funds receive fixed in long-dated swaps to match liabilities
- Structural receiving pressure in the 20Y-30Y sector
- Drove 30Y swap spreads negative (first time swap rate below Treasury yield) -- not a credit signal, a demographic one
- Assessment: pension deficit measures, liability-driven investment flows, insurance reserve activity

### Corporate issuance (seasonal)
- New corporate bond issuers often receive fixed in swaps to hedge their rate exposure
- Seasonal pattern: heavy in September and January, lighter in summer
- Assessment: track weekly issuance volumes, pipeline, and seasonal patterns

### Liquidity (transition periods)
- Improving liquidity (QE, reserve expansion) tends to narrow spreads
- Tightening liquidity (QT, reserve drainage) tends to widen spreads
- Assessment: reserve balances, TGA levels, RRP usage, SOFR-FF dynamics

## Analysis process

1. **Compute current swap spreads.** Use matched-maturity spreads (not headline) to avoid curve noise. Compare across the term structure.

2. **Historical context.** Place current levels in historical percentile context (3M, 6M, 1Y, 3Y). Note whether spreads are at extremes or mid-range.

3. **Identify the dominant driver.** Assess which driver framework best explains the current spread level and recent trajectory:
   - If spreads are moving with yields (widening in selloffs, narrowing in rallies): mortgage hedging likely dominant
   - If spreads are widening independent of yield direction with credit stress indicators rising: bank credit
   - If spreads are narrowing despite other forces, check supply calendar and issuance pipeline
   - If long-end spreads are persistently negative or near-negative: pension demand structural
   - If funding conditions (repo, reserves) are shifting: liquidity channel

4. **Cross-check across maturities.** Different drivers dominate at different points:
   - Front-end (2Y-5Y): more sensitive to credit and funding conditions
   - Belly (5Y-10Y): mortgage hedging and supply most impactful
   - Long-end (20Y-30Y): pension demand and structural forces dominate

5. **Assess consistency.** Is the current spread level consistent with the dominant driver, or is there a disconnect? A disconnect between the spread level and the driver's signal is the basis for a trade.

6. **Trade structure.** For any identified opportunity:
   - DV01-match the swap and Treasury legs (notionals will differ due to different DV01/unit)
   - Estimate carry from the swap spread position
   - Compute breakeven spread move (how much must the spread move against before carry is exhausted)
   - Consider conditional expressions if the view is rate-direction-dependent (e.g., conditional widener using payer swaptions)

## Core Assessment Framework

Assess the swap spread on four anchors:

- `Spread Level`: where is the swap spread relative to its historical distribution at each maturity. State the percentile.
- `Dominant Driver`: which driver framework best explains current levels and trajectory. Is it transitioning?
- `Driver Consistency`: does the spread level make sense given the dominant driver's current signal. A spread that is wide while its dominant driver says narrow is a potential opportunity.
- `Term Structure Signal`: is the term structure of swap spreads (front vs belly vs long-end) consistent, or is one sector dislocated relative to others?

Use the anchors to classify:

- `actionable dislocation`: spread is at an extreme, driver analysis suggests the extreme is unjustified or the driver is transitioning, and the term structure confirms the signal
- `interesting but watch`: spread is extended but the driver supports it, or the driver is ambiguous, requiring patience before entry
- `fair value`: spread is mid-range and consistent with the driver picture

## Output tables

### Swap Spread Term Structure
| Tenor | Swap Rate (%) | Govt Yield (%) | Swap Spread (bp) | 1Y Percentile | Dominant Driver |
|-------|---------------|----------------|-------------------|---------------|-----------------|
| 2Y | ... | ... | ... | ...th | ... |
| 5Y | ... | ... | ... | ...th | ... |
| 10Y | ... | ... | ... | ...th | ... |
| 30Y | ... | ... | ... | ...th | ... |

### Driver Assessment
| Driver | Current Signal | Strength | Spread Implication |
|--------|---------------|----------|-------------------|
| Bank credit | ... | Low / Moderate / High | Widen / Neutral / Narrow |
| Mortgage hedging | ... | ... | ... |
| Treasury supply | ... | ... | ... |
| Pension demand | ... | ... | ... |
| Corporate issuance | ... | ... | ... |
| Liquidity | ... | ... | ... |
| **Net assessment** | ... | ... | ... |

## Evidence that would invalidate this analysis

- a credit event or systemic stress overwhelms all other drivers
- a regime change in monetary policy (QE/QT shift) changes the liquidity channel fundamentally
- a structural shift in mortgage market (product mix, hedging behavior) alters the mortgage channel
- an unanticipated change in Treasury issuance strategy (bill vs coupon mix, buybacks) changes supply dynamics
- regulatory changes affecting bank balance sheets or swap clearing alter the structural spread level

## Output structure

Prefer this output order:

1. `Swap Spread Summary`
2. `Term Structure Analysis` (table)
3. `Driver Assessment` (table)
4. `Historical Context`
5. `Dominant Driver Identification`
6. `Trade Opportunity Assessment`
7. `Key Risk Factors`
8. `Next Skill`

Always include:

- the current swap spread level and historical percentile
- the dominant driver and its current signal
- whether the spread level is consistent with the driver picture
- any cross-maturity dislocations
- whether the idea should move to `trade-expression`, `position-sizing`, or needs more context from `repo-funding-analysis` or `macro-event-analysis`

## Best practices

- always use matched-maturity swap spreads, not headline; in steep curves the difference matters
- remember that the same spread responds to completely different drivers in different regimes -- do not assume today's driver was yesterday's
- mortgage hedging is the dominant short-term driver in normal markets; learn to read the refi index and duration extension signals
- 30Y negative swap spreads are structural (pension demand), not a credit distortion
- swap spreads isolate fiscal views more efficiently than outright Treasury shorts (the swap leg removes rate-level noise)
- heavy Treasury supply tends to narrow spreads (cheapens Treasuries), not widen them
- monitor seasonal patterns: corporate issuance heavy in September and January drives narrowing

## Usage examples

- "Use `swap-spread-analysis` to evaluate 10Y USD swap spreads. They've widened 15bp over the past month and I want to understand which driver is responsible."
- "Use `swap-spread-analysis` to compare the term structure of swap spreads. The front-end is at the 90th percentile but the long-end is near median -- is the front-end dislocated?"
- "Use `swap-spread-analysis` to assess whether mortgage hedging is the dominant force right now. Rates have sold off 50bp and spreads are widening."
- "Use `swap-spread-analysis` as a fiscal signal. Heavy supply is coming via the QRA and I want to understand the swap spread implications."
