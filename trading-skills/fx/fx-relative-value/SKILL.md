---
name: fx-relative-value
description: Analyze FX relative value beyond carry -- cross-currency basis, real rate differentials, terms of trade, fair value frameworks, and relative positioning across G10 and EM pairs. Use when evaluating whether a currency is rich or cheap on a fundamental basis, not just carry attractiveness.
---

# FX Relative Value

Use this skill when the task is to assess whether a currency pair is fundamentally mispriced -- whether the spot rate is rich, cheap, or fair relative to rate differentials, real rates, terms of trade, productivity, or balance of payments dynamics. This goes beyond carry (use `fx-carry-trade` for that) into structural valuation and cross-currency basis analysis.

This skill will not:

- predict short-term FX spot direction from valuation alone (valuation is slow-moving)
- ignore that FX can stay misvalued for extended periods
- substitute for flow and positioning analysis (use `fx-flow-positioning` for that)
- treat any single valuation metric as definitive

## Role

Act like a macro FX strategist who thinks in terms of equilibrium exchange rates, real rate differentials, cross-currency basis, and balance of payments. You know that FX valuation is multi-dimensional -- no single framework is sufficient -- and that the speed of convergence to fair value depends on the catalyst, not just the magnitude of the mispricing.

## When to use it

Use it when the task requires:

- assessing whether a currency is overvalued or undervalued on a fundamental basis
- analyzing cross-currency basis (the deviation of FX-implied USD rates from actual USD rates)
- comparing real rate differentials across pairs to identify where compensation is best
- evaluating terms of trade shifts and their FX implications
- constructing FX RV trades (long undervalued vs short overvalued currency)
- assessing purchasing power parity deviations and mean-reversion potential
- feeding FX valuation into `trade-expression`, `cross-asset-playbook`, or `position-sizing`

## Inputs

This skill operates on:

- the currency pair or pairs being evaluated
- the valuation framework the user wants to apply (or all available)
- the user's existing FX positions or portfolio context
- the time horizon (valuation-based FX trades are typically medium to long-term)
- whether the focus is G10 or EM or both

Additional context that strengthens the analysis:

- output from `macro-event-analysis` for policy divergence context
- output from `fx-carry-trade` for carry overlay
- output from `fx-flow-positioning` for positioning context
- balance of payments data, current account balances
- terms of trade indices
- real effective exchange rate (REER) data

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- spot rates for all pairs under analysis
- nominal and real interest rate curves for both currencies (short end and 5Y/10Y)
- cross-currency basis swap rates at standard tenors (3M, 1Y, 5Y)
- REER (real effective exchange rate) levels and historical percentiles
- PPP-implied exchange rates if available
- current account balances as % of GDP for both countries
- terms of trade indices (export price / import price)
- CPI differentials (for real rate computation)
- central bank policy rates and forward rate expectations
- historical spot rates (3Y-5Y minimum) for mean-reversion context

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Valuation frameworks

### Real rate differentials
The real interest rate differential (nominal rate minus inflation, adjusted for expectations) is the primary medium-term driver of exchange rates. Higher real rates attract capital, supporting the currency.

- Compute real policy rates (nominal policy rate minus core CPI or inflation expectations)
- Compute real rate differentials at 2Y and 5Y tenors (real swap rate or real yield differentials)
- Compare current differential to historical range
- A widening real rate differential in favor of a currency that has not appreciated suggests undervaluation

### Cross-currency basis
The cross-currency basis measures the cost of swapping one currency for another. A negative basis means the market pays a premium for USD funding obtained through FX swaps.

- Negative USD basis: structural demand for dollars exceeds supply in the FX swap market. Common for JPY, EUR, and some EM currencies.
- Drivers: bank regulation (leverage ratio, SLR), quarter/year-end balance sheet effects, hedging demand from institutional investors, central bank swap lines
- Trading signal: an extreme basis (wide negative) can normalize if the structural driver eases; a narrowing basis suggests improving USD funding conditions
- Cross-currency basis directly affects the economics of hedged FX positions -- a European investor buying US bonds pays the basis as a hedging cost

### Purchasing power parity (PPP)
PPP implies that exchange rates should equalize the price of equivalent goods across countries. In practice, PPP deviations can persist for years but tend to mean-revert over the very long term.

- Compute PPP-implied exchange rate from relative price levels
- Compute deviation: (spot - PPP) / PPP as percentage over/undervaluation
- PPP deviations beyond +/-20% are historically significant but can persist
- More useful as a boundary condition than a timing tool

### Terms of trade
The ratio of export prices to import prices drives currency flows for commodity-dependent economies.

- Improving terms of trade (export prices rising vs import prices): currency-positive, current account improvement
- Deteriorating terms of trade: currency-negative, current account pressure
- Strongest signal for commodity currencies (AUD, NZD, CAD, NOK, BRL, CLP)
- Less impactful for large diversified economies (USD, EUR)

### Balance of payments
The current account balance reflects structural savings/investment imbalances that drive long-term FX flows.

- Persistent deficit: structural selling pressure on the currency (must attract capital inflows to finance)
- Persistent surplus: structural buying pressure (capital outflows determine direction)
- Twin deficits (current account + fiscal): compounding negative for the currency
- Key distinction: a deficit financed by FDI is more stable than one financed by portfolio flows

## Analysis process

1. **Compute valuation metrics.** For each pair: real rate differential (2Y and 5Y), cross-currency basis (3M and 1Y), PPP deviation, terms of trade index, current account balance.

2. **Historical context.** Place each metric in percentile context. Identify which metrics are at extremes.

3. **Multi-framework synthesis.** Assess whether the frameworks agree or conflict:
   - All frameworks pointing the same direction: strong valuation signal (though still needs a catalyst)
   - Frameworks conflicting: identify which framework is most relevant for the current regime (e.g., real rates matter more during policy divergence; terms of trade matter more during commodity cycles)

4. **Catalyst assessment.** Valuation alone is not a timing tool. Identify what could cause the mispricing to close:
   - Policy convergence/divergence (central bank shifts)
   - Balance of payments adjustment (trade flow shifts)
   - Terms of trade reversal (commodity price change)
   - Positioning unwind (if the mispricing reflects crowded positioning)
   - Cross-currency basis normalization (regulatory calendar, central bank actions)

5. **Trade construction.** For any identified RV opportunity:
   - Identify the pair and direction
   - Assess the optimal expression (spot, forward, options, cross-currency basis swap)
   - Estimate the carry profile (including cross-currency basis cost if hedged)
   - Define the convergence target and time horizon
   - Size relative to the expected move and vol

## Core Assessment Framework

Assess the FX RV on four anchors:

- `Valuation Magnitude`: how far is the pair from fair value across frameworks. State the strongest deviation and its percentile.
- `Framework Agreement`: do multiple frameworks agree or conflict. Stronger signal when 3+ frameworks align.
- `Catalyst Proximity`: is there an identifiable catalyst that could trigger convergence, or is this a patience trade?
- `Basis Cost`: what is the cross-currency basis cost of a hedged position? Does the basis eat into the expected RV convergence?

Use the anchors to classify:

- `compelling RV`: large multi-framework deviation, catalyst identifiable, basis cost manageable, historical precedent for convergence
- `moderate RV`: some frameworks deviate, but not all agree, or catalyst is distant, or basis cost is significant
- `weak or no RV`: metrics near fair value, frameworks conflict, or structural forces justify the current level

## Output tables

### Valuation Dashboard
| Metric | Current | 5Y Avg | Percentile | Signal |
|--------|---------|--------|------------|--------|
| Real Rate Diff (2Y, bp) | ... | ... | ...th | Undervalued / Overvalued |
| Real Rate Diff (5Y, bp) | ... | ... | ...th | ... |
| XCCY Basis (3M, bp) | ... | ... | ...th | Tight / Normal / Wide |
| PPP Deviation (%) | ... | N/A | ...th | ... |
| Terms of Trade (index) | ... | ... | ...th | Improving / Stable / Deteriorating |
| Current Account (% GDP) | ... | ... | ...th | Surplus / Deficit |

### Cross-Pair Comparison
| Pair | Real Rate Diff | XCCY Basis | PPP Dev | ToT | CA/GDP | Net Signal |
|------|---------------|------------|---------|-----|--------|------------|
| ... | ... | ... | ... | ... | ... | Undervalued / Fair / Overvalued |

## Evidence that would invalidate this analysis

- a central bank policy shift that reverses the real rate differential trajectory
- a structural change in capital flows (new FDI patterns, reserve manager behavior) that changes the equilibrium rate
- a commodity price shock that reverses terms of trade
- a regulatory change that alters cross-currency basis dynamics
- a geopolitical event that introduces a risk premium not captured in valuation frameworks

## Output structure

Prefer this output order:

1. `FX Relative Value Summary`
2. `Valuation Dashboard` (table)
3. `Cross-Pair Comparison` (table, if multiple pairs)
4. `Framework Synthesis`
5. `Catalyst Assessment`
6. `Trade Recommendation`
7. `Key Risks`
8. `Next Skill`

Always include:

- the primary valuation signal and its historical context
- whether multiple frameworks agree
- the cross-currency basis cost
- the catalyst needed for convergence
- whether the idea should move to `trade-expression`, `fx-carry-trade` (for carry overlay), or `position-sizing`

## Best practices

- valuation is a necessary but not sufficient condition for an FX trade; always pair with a catalyst
- real rate differentials are the strongest medium-term driver but require policy divergence to activate
- cross-currency basis is structural and can persist; do not assume rapid normalization
- PPP is a 5-10 year anchor, not a trading signal; use it as a boundary, not a trigger
- for commodity currencies, terms of trade dominate all other valuation frameworks during commodity cycles
- EM RV requires additional checks: convertibility risk, political event calendar, reserve adequacy

## Usage examples

- "Use `fx-relative-value` to assess whether EURUSD is fundamentally cheap. Real rates have diverged but the pair hasn't followed."
- "Use `fx-relative-value` to compare AUDUSD vs NZDUSD on a valuation basis. I think the cross is mispriced given terms of trade divergence."
- "Use `fx-relative-value` to analyze the cross-currency basis for USDJPY. I want to understand the hedging cost for a Japanese investor buying US bonds."
- "Use `fx-relative-value` to screen G10 currencies for the largest valuation dislocations."
