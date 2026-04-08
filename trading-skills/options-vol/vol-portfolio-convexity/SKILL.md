---
name: vol-portfolio-convexity
description: Construct and manage portfolios that use volatility as an asset class -- long-vol strategies, convexity harvesting, short-vol income, and regime-diversified vol allocations. Use when thinking about vol as a strategic allocation rather than a tactical trade, or when building a portfolio designed to profit from vol regime changes.
---

# Vol Portfolio & Convexity

Use this skill when the task is to think about volatility as a portfolio allocation, not just a tactical trade. This covers long-vol strategies (buying convexity to protect against tail events), short-vol income strategies (harvesting the variance risk premium), and regime-diversified portfolios that blend both. It addresses the strategic question: how much convexity does a portfolio need, and how should it be sourced?

This skill will not:

- construct specific options strategies (use `options-strategy-construction`)
- interpret a single vol surface (use `vol-framework`)
- manage individual option positions (use `greeks-pnl-management`)
- predict when the next vol spike will occur

## Role

Act like a portfolio allocator who views volatility as an asset class with its own return characteristics, regime dependencies, and portfolio role. You understand that the variance risk premium (implied vol structurally exceeds realized vol) creates a persistent income opportunity for vol sellers, but that selling vol is a concave strategy that accumulates small gains and suffers large, sudden losses. Long vol is the opposite: persistent cost (negative carry) but convex payoff in tail events. The portfolio question is how to blend these exposures.

## When to use it

Use it when the task requires:

- deciding how much long-vol (convexity) a portfolio needs as tail protection
- evaluating short-vol strategies and their risk characteristics
- understanding the variance risk premium and how to harvest it (or decide not to)
- constructing a regime-diversified vol allocation (long vol in some scenarios, short in others)
- assessing whether current vol levels represent a strategic buying or selling opportunity
- evaluating vol products (VIX futures, variance swaps, vol ETPs) as portfolio building blocks
- feeding vol allocation decisions into `portfolio-construction`, `scenario-analysis`, or `risk-management`

## The variance risk premium

Implied volatility is structurally higher than realized volatility on average. This gap is the variance risk premium (VRP). It exists because investors are willing to pay for protection against uncertainty.

**Short vol earns the VRP over time:**
- Selling options (straddles, strangles, puts) collects premium that exceeds the average realized move
- The income is steady in calm markets but reversed sharply in stress
- Sharpe ratio of short-vol strategies is attractive in calm regimes but the distribution has fat left tails
- Selling vol is economically equivalent to selling insurance: profitable in aggregate, catastrophic in the tail event

**Long vol pays the VRP as a cost:**
- Buying options (puts, straddles, VIX calls) costs more than the average realized move
- The cost is persistent negative carry (theta decay)
- But the payoff in tail events is convex: large, sudden gains that offset the accumulated carry cost
- Buying vol is economically equivalent to buying insurance: costly in calm, essential in crisis

**The VRP is not free money:**
- Short-vol strategies blow up periodically (Feb 2018, March 2020)
- The "steady income + sudden loss" profile is psychologically seductive but structurally dangerous at scale
- Survivors bias in short-vol track records is extreme

## Convexity as portfolio allocation

### Why portfolios need convexity
Traditional portfolios (stocks, bonds) are concave -- they perform linearly in normal markets but suffer outsized losses in tail events (correlations spike, diversification fails). Adding convexity (long vol) improves the portfolio's tail behavior:

- Convexity pays off precisely when the rest of the portfolio is losing money
- The cost of convexity (negative carry) is the "insurance premium" for tail protection
- A portfolio with convexity can take more risk in the core allocation because the tail is protected

### The convexity budget
How much to spend on convexity protection depends on:

- Portfolio size and risk tolerance
- The cost of convexity (current vol levels -- cheaper when vol is low, expensive when vol is high)
- Correlation between vol payoffs and portfolio losses (higher correlation = more efficient protection)
- Holding period (longer horizons require more sustained protection, which is more expensive)
- Whether the protection is for a specific event or ongoing

**Rule of thumb:** 1-3% of portfolio NAV per year spent on rolling tail hedges provides meaningful protection without excessive carry drag. But the exact amount depends on the portfolio's specific risk profile.

## Short-vol crowding dynamics

Short-vol strategies are subject to crowding dynamics identical to carry trade crowding:

1. Calm markets make short-vol returns attractive (low realized vol, steady income)
2. Capital flows into short-vol strategies, compressing the VRP
3. Realized vol stays low because short-vol hedging flows dampen market moves (dealers long gamma)
4. The VRP appears stable but fragile -- supported by positioning, not fundamentals
5. A spark (data surprise, geopolitical event, liquidity event) triggers vol spike
6. Short-vol positions liquidate simultaneously, amplifying the spike
7. Months or years of short-vol income erased in days

**Detection:** the same signals as carry trade crowding:
- VIX at historical lows with VIX futures in steep contango (crowded roll income)
- Implied-realized spread compressed (VRP smaller, less compensation for risk)
- Cross-asset vol correlation high (same capital pool short vol in everything)
- Options market put skew steep but expensive (protection demand visible but supply absorbed)

## Regime-diversified vol allocation

Rather than being purely long or short vol, a regime-diversified approach blends:

- **Long vol allocation:** funded through rolling OTM puts, VIX calls, variance swap receivers, or systematic tail hedge overlays. Positioned to profit from vol spikes and correlation breakdowns.
- **Short vol allocation:** funded through selling OTM puts (cash-secured), iron condors, or variance swap payers. Positioned to harvest VRP in calm markets.
- **Regime signals:** adjust the blend based on vol regime indicators:
  - Vol below 20th percentile: increase long-vol allocation (cheap to buy, crowded short-vol)
  - Vol between 20th-80th percentile: balanced allocation
  - Vol above 80th percentile: increase short-vol allocation (expensive to buy, unwind pressure from longs)
  - But: do not sell vol into a genuine regime change just because "IV is high"

## Vol products as building blocks

### VIX futures
- Trade the expected future level of VIX, not VIX itself
- Term structure: typically in contango (front month below back months); backwardation during stress
- Roll yield: contango creates negative roll for longs (buy high, sell low), positive roll for shorts
- VIX futures are not the same as VIX; basis between spot VIX and futures can be large

### Variance swaps
- Pay the difference between realized variance and a fixed strike
- Payer profits from high realized vol; receiver profits from low realized vol
- Variance (vol^2) payoff is convex: more sensitive to large moves than options
- Historically used by sophisticated vol traders; less accessible but cleaner exposure

### Vol ETPs (VXX, SVXY, UVXY, etc.)
- ETPs that track VIX futures (long or short)
- Long VIX ETPs: persistent negative roll yield (contango bleed); useful only for short-term hedging
- Short VIX ETPs: positive roll yield in calm; catastrophic in vol spikes (XIV termination, Feb 2018)
- Not suitable for strategic allocation due to path dependency and roll costs

## Analysis process

1. **Assess current vol regime.** Where is implied vol in historical percentile? What is the VRP (implied minus realized)? Is the VRP compressed or wide?

2. **Evaluate portfolio convexity need.** What is the portfolio's current tail exposure? How would it perform in a 3-sigma event? Is there existing convexity (explicit tail hedges, long vol positions)?

3. **Cost the protection.** What does rolling tail protection cost per year? Compare across instruments:
   - OTM puts (SPX, specific names)
   - VIX calls
   - Variance swap receivers
   - Systematic overlay strategies

4. **Assess short-vol opportunity.** If considering short-vol allocation:
   - Is the VRP wide enough to compensate for the tail risk?
   - Is there crowding in short-vol (compressed VRP, low VIX, steep contango)?
   - Can the short-vol position be sized to survive a 2008 or March 2020 scenario?

5. **Construct the blend.** Based on regime, cost, and portfolio need:
   - What percentage of NAV is allocated to long-vol protection?
   - What percentage to short-vol income?
   - What regime signals trigger rebalancing between the two?

6. **Stress test.** Run the portfolio through historical vol events (2008 GFC, 2018 Volmageddon, 2020 Covid) to assess whether the convexity allocation is sufficient.

## Core Assessment Framework

Assess the vol allocation on four dimensions:

- `Vol Regime`: current percentile, VRP level, and crowding assessment
- `Convexity Need`: how much tail protection the portfolio requires given its core exposures
- `Cost Efficiency`: which instruments provide the most convexity per unit of carry cost
- `Regime Sensitivity`: how the allocation performs across calm, transition, and crisis regimes

## Output tables

### Vol Regime Dashboard
| Metric | Current | Percentile | Signal |
|--------|---------|------------|--------|
| ATM Implied Vol | ... | ...th | Low / Normal / Elevated |
| 20d Realized Vol | ... | ...th | ... |
| VRP (IV - RV) | ... bp | ...th | Compressed / Normal / Wide |
| VIX Term Structure | ... | Contango / Flat / Backwardation | Crowded / Neutral / Stressed |

### Convexity Cost Comparison
| Instrument | Annual Cost (% NAV) | Convexity per Unit Cost | Liquidity | Complexity |
|------------|--------------------|-----------------------|-----------|-----------|
| SPX 3M 25d puts | ... | ... | High | Low |
| VIX 3M calls | ... | ... | Moderate | Moderate |
| Variance swap receiver | ... | ... | Low | High |
| Systematic tail overlay | ... | ... | Varies | High |

## Evidence that would invalidate this analysis

- a structural change in the VRP (regulatory, market structure) that alters the baseline relationship between implied and realized vol
- a change in the correlation between vol payoffs and portfolio losses
- a new vol product or market innovation that changes the cost of convexity
- a regime change that makes the historical vol distribution unreliable as a guide

## Output structure

Prefer this output order:

1. `Vol Regime Assessment`
2. `Vol Regime Dashboard` (table)
3. `Portfolio Convexity Need`
4. `Convexity Cost Comparison` (table)
5. `Short-Vol Assessment` (if relevant)
6. `Recommended Allocation`
7. `Stress Test Results`
8. `Key Risks`
9. `Next Skill`

Always include:

- the current vol regime and VRP assessment
- whether convexity is cheap or expensive
- the recommended allocation blend (long-vol %, short-vol %)
- the cost of protection per year
- stress test results under historical scenarios
- whether the analysis should feed into `portfolio-construction`, `risk-management`, or `scenario-analysis`

## Best practices

- never sell vol at scale without surviving a stress test through March 2020 and similar events
- the variance risk premium is real but not free; the distribution of short-vol returns has fat left tails
- buy convexity when it is cheap (vol at low percentile); this is counterintuitive because it feels unnecessary when everything is calm
- do not sell convexity into a genuine regime change because "IV is at the 90th percentile"; regime changes can push vol to the 99th percentile and beyond
- vol ETPs are trading instruments, not strategic allocations; roll costs and path dependency destroy long-term value
- the most dangerous state is compressed VRP with extreme short-vol positioning; the next vol spike will be amplified by the unwind
- convexity should be funded from the portfolio's risk budget, not treated as a separate cost center; it improves the portfolio's risk-adjusted return even though it has negative standalone carry

## Usage examples

- "Use `vol-portfolio-convexity` to assess how much tail protection my 60/40 portfolio needs. Vol is at the 15th percentile and I'm wondering if now is a good time to add puts."
- "Use `vol-portfolio-convexity` to evaluate a short-vol income strategy. I'm considering selling SPX puts for income and want to understand the risk."
- "Use `vol-portfolio-convexity` to design a regime-diversified vol allocation that blends long and short vol based on market conditions."
- "Use `vol-portfolio-convexity` to compare the cost of tail protection across instruments. I have a $10M portfolio and want to know the annual drag."
