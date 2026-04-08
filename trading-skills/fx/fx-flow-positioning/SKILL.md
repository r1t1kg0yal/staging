---
name: fx-flow-positioning
description: Analyze FX markets through the lens of capital flows, positioning, and the USD as a regime variable. Covers balance of payments flows, speculative positioning, reserve manager behavior, the dollar smile framework, and flow-based signals for FX trading. Use when assessing who is driving FX moves and whether positioning is crowded.
---

# FX Flow & Positioning

Use this skill when the task is to understand who is driving FX moves and whether positioning is crowded or likely to reverse. This skill focuses on capital flows (real money, speculative, reserve manager), positioning data, and the USD's role as a global regime variable. It complements `fx-relative-value` (fundamental valuation) and `fx-carry-trade` (carry metrics).

This skill will not:

- substitute for fundamental valuation (use `fx-relative-value` for that)
- predict positioning data before it is released
- guarantee that crowded positioning unwinds on any timeline
- ignore that positioning data is lagged and incomplete

## Role

Act like a macro FX trader who thinks in terms of flows, positioning, and narrative vs price action. You understand that FX is driven by the marginal flow, not the fundamental equilibrium -- and that the marginal flow shifts when positioning is extreme. You track the USD as the regime variable that connects FX to everything else.

## When to use it

Use it when the task requires:

- assessing who is driving a currency move (real money, speculative, official/reserve manager)
- evaluating positioning data for crowding signals (CFTC IMM, options risk reversals as positioning proxy)
- understanding the USD's role as a regime variable for risk assets and cross-asset correlations
- analyzing balance of payments flows and their FX implications
- applying the dollar smile framework (USD strengthens in both risk-off and US exceptionalism, weakens in synchronized global growth)
- detecting narrative vs price action divergences that signal positioning shifts
- feeding flow/positioning context into `fx-relative-value`, `fx-carry-trade`, or `cross-asset-playbook`

## Inputs

This skill operates on:

- the currency or currencies being analyzed
- recent price action and any observed flow patterns
- available positioning data (CFTC IMM, options skew, bank flow surveys)
- the prevailing macro narrative and whether price action is consistent with it
- whether the focus is short-term (tactical positioning) or structural (BOP, reserve management)

Additional context that strengthens the analysis:

- output from `macro-event-analysis` for the narrative framework
- output from `fx-relative-value` for whether price action aligns with fundamentals
- output from `market-regime-analysis` for risk-on vs risk-off backdrop
- central bank intervention history or reserve data
- cross-asset correlation data (FX vs rates, FX vs equities)

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- CFTC IMM speculative positioning (net long/short) for relevant currencies, current and historical (1Y, 3Y)
- options risk reversals (25-delta) as a positioning and sentiment proxy
- FX spot price history (1Y daily minimum) for price action and trend assessment
- central bank reserve data if available (IMF COFER, individual central bank reports)
- balance of payments data: current account, financial account, capital account
- capital flow indicators: fund flow data, portfolio flow data
- DXY or trade-weighted USD index for dollar regime assessment
- cross-asset correlation data: USD vs VIX, USD vs equity indices, USD vs rates
- central bank FX intervention data if available

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Flow taxonomy

### Speculative flows
Hedge funds, macro funds, CTA/trend-following. These are the marginal price setters in the short term.

- Data: CFTC IMM net positioning (lagged 3 days, weekly); options risk reversals
- Signal: extreme net positioning (above 90th or below 10th percentile of 3Y range) = crowding risk
- Behavior: trend-following in momentum regimes; mean-reverting when positioning extremes trigger unwinds
- Crowding detection: muted response to favorable news + outsized response to unfavorable = no marginal buyer/seller left

### Real money flows
Pension funds, insurance companies, sovereign wealth funds, asset managers. These are structural and slow-moving.

- Data: fund flow surveys (limited and lagged); BOP financial account; proxy from reserve changes
- Signal: large, persistent flows in one direction; often related to asset allocation shifts or liability hedging
- Behavior: relatively insensitive to short-term price action; driven by mandates, benchmark changes, yield differentials
- FX implication: real money flows create persistent trends; they do not reverse on positioning data alone

### Reserve manager flows (official sector)
Central banks managing FX reserves. Typically counter-cyclical (buying weakness, selling strength) but with exceptions during intervention campaigns.

- Data: IMF COFER data (quarterly, aggregated); individual central bank disclosures; intervention data
- Signal: sudden reserve declines (selling USD to defend domestic currency); reserve accumulation (buying USD, adding FX assets)
- Behavior: typically diversifying away from USD over time (gradual); occasionally aggressive during intervention (sudden)
- FX implication: reserve managers are the largest participants in aggregate but move slowly; intervention is the exception and signals policy commitment

### Corporate flows
Multinationals hedging foreign earnings, M&A-related flows.

- Data: limited; infer from M&A calendar, earnings season hedging patterns, repatriation events
- Signal: seasonal hedging demand (quarter-end, fiscal year-end); large M&A deals can move specific pairs
- Behavior: largely hedging-driven (non-directional in aggregate); timing clustered around corporate events

## The dollar smile framework

The USD's behavior follows a "smile" pattern across global growth/risk regimes:

**Left side of smile (risk-off / global recession):** USD strengthens as a safe haven. Capital flows back to the US; dollar liquidity is scarce; everything else sells.

**Bottom of smile (synchronized global growth):** USD weakens. Global growth improves, capital flows out of the US seeking higher returns elsewhere, carry trades flourish, risk-on assets rally.

**Right side of smile (US exceptionalism):** USD strengthens because the US economy outperforms the rest of the world. Capital flows to the US for growth, not safety.

**Transition signals:**
- Left → Bottom: risk appetite recovering, VIX declining, carry-to-vol ratios improving, EM flows turning positive
- Bottom → Right: US data surprising to upside while global data disappoints, rate differential widening in favor of US
- Right → Left: US data deteriorating faster than expected, recession fears, flight to quality

## Analysis process

1. **Assess current positioning.** Gather CFTC IMM data and options risk reversals. Place net positioning in historical percentile context. Identify which currencies have extreme positioning.

2. **Classify the flow driver.** Who is driving the current FX move?
   - Price action consistent with trend-following + extreme speculative positioning = momentum-driven, vulnerable to reversal
   - Price action driven by fundamental shift + real money reallocation = structural, likely to persist
   - Price action counter to fundamentals + extreme positioning = positioning-driven, reversal likely
   - Sudden, large move with official sector activity = intervention or reserve management

3. **Apply the dollar smile.** Where is the USD in the smile?
   - Check DXY trajectory, VIX, global vs US relative growth surprises, carry performance
   - Assess whether the regime is transitioning between smile zones

4. **Narrative vs price action.** Is price action consistent with the prevailing narrative?
   - Narrative says bullish but price is failing to rally = positioning too long, marginal buyer exhausted
   - Narrative says bearish but price holds = positioning too short, or hidden real money demand
   - Divergence between narrative and price action is one of the strongest flow signals

5. **Crowding assessment.** Evaluate whether positioning is dangerously crowded:
   - Net positioning above 90th percentile or below 10th percentile of multi-year range
   - Asymmetric price response (big on adverse news, muted on favorable)
   - Cross-market carry correlation increasing (same flow pool chasing the same trades)
   - Risk reversals at extremes consistent with one-way hedging demand

6. **Synthesize into trading signal.** Map the flow picture to an actionable view:
   - Crowded + extreme positioning + narrative divergence = high reversal probability; trade against positioning
   - Structural flow in early stages + positioning light = trend continuation; trade with the flow
   - Reserve manager intervention + fundamental support = strong directional signal
   - No clear flow driver + mid-range positioning = no edge from flow analysis; defer to valuation or carry

## Core Assessment Framework

Assess the flow picture on four anchors:

- `Positioning Extremity`: where is speculative positioning in historical percentile. Extreme = crowding risk.
- `Flow Type`: which flow category is dominant. Speculative is fast-reversing; real money is persistent; official is intermittent but powerful.
- `Dollar Regime`: where is the USD in the smile. Transitions between zones are the highest-signal moments.
- `Narrative Consistency`: does price action confirm or contradict the prevailing narrative? Divergence is signal.

Use the anchors to classify:

- `crowded and vulnerable`: extreme positioning + narrative divergence + asymmetric price response. High reversal probability.
- `trend intact`: structural flows dominant + positioning not extreme + price action confirms narrative. Continuation likely.
- `regime transition`: USD moving between smile zones. Cross-asset correlations shifting. High signal but uncertain direction.
- `no flow edge`: mid-range positioning, no dominant flow type, narrative and price aligned. Defer to other frameworks.

## Output tables

### Positioning Dashboard
| Currency | Net IMM Position | Percentile (3Y) | RR (25d, 3M) | Flow Signal |
|----------|-----------------|-----------------|--------------|-------------|
| ... | ... long/short | ...th | ... | Crowded / Moderate / Light |

### Dollar Smile Assessment
| Factor | Current | Signal |
|--------|---------|--------|
| DXY Trend | ... | Strengthening / Weakening / Range |
| VIX Level | ... | Risk-off / Neutral / Risk-on |
| US vs Global Growth | ... | US outperforming / Synchronized / US lagging |
| Carry Performance | ... | Working / Mixed / Unwinding |
| Smile Zone | ... | Left (safe haven) / Bottom (risk-on) / Right (exceptionalism) |

## Evidence that would invalidate this analysis

- a sudden policy shift (central bank surprise) that overrides positioning dynamics
- a geopolitical event that creates a new flow regime not captured in historical data
- a structural change in reserve management (de-dollarization, new reserve currency inclusion) that alters official flows
- a regulatory change affecting speculative positioning limits or margin requirements
- positioning data revisions that change the crowding assessment retroactively

## Output structure

Prefer this output order:

1. `Flow And Positioning Summary`
2. `Positioning Dashboard` (table)
3. `Dollar Smile Assessment` (table)
4. `Dominant Flow Driver`
5. `Narrative vs Price Action`
6. `Crowding Assessment`
7. `Trading Signal`
8. `Key Risks`
9. `Next Skill`

Always include:

- the positioning extremity and its historical percentile
- who is driving the move (speculative, real money, official)
- where the USD sits in the smile framework
- whether narrative and price action are consistent
- whether the analysis should feed into `fx-carry-trade`, `fx-relative-value`, `trade-expression`, or `cross-asset-playbook`

## Best practices

- positioning data is lagged and incomplete; treat it as a guide to crowding risk, not a precise flow measure
- the most dangerous positioning signal is when the narrative says one thing but price action says another
- carry trade unwinds happen in waves: months of carry erased in days when positioning is extreme
- the dollar smile is not a timing tool; transitions between zones are the signal, not the zone itself
- official sector intervention is rare but powerful; when a central bank draws a line, respect it until proven otherwise
- cross-market carry correlation increasing = same flow pool, same risk; unwind in one currency can cascade to others

## Usage examples

- "Use `fx-flow-positioning` to assess USDJPY positioning. Specs look extremely long USD but the pair keeps grinding higher. Is positioning a risk?"
- "Use `fx-flow-positioning` to evaluate where the USD sits in the dollar smile. Global growth is recovering and I want to know if we're transitioning."
- "Use `fx-flow-positioning` to check for crowding in EM carry trades. USDMXN and USDBRL both have extreme speculative shorts."
- "Use `fx-flow-positioning` to analyze the flow behind the recent EUR rally. Is this real money or spec positioning?"
