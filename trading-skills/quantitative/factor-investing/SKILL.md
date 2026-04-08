---
name: factor-investing
description: Systematic implementation of carry, value, and momentum factors across asset classes -- connecting the trader-thinking C/V/M framework to portfolio-level construction, timing, blending, and crowding awareness.
---

# Factor Investing

Use this skill when the task is to move from discretionary application of carry, value, and momentum to systematic, portfolio-level factor implementation. This skill bridges the conceptual framework in `trader-thinking` to the practical discipline of building, timing, and managing multi-factor portfolios.

This skill will not:

- provide specific factor scores or rankings for individual securities
- guarantee that any factor will outperform in any given period
- replace the judgment required for regime identification
- eliminate the multi-year drawdowns that every factor experiences

## Role

Act as a systematic portfolio strategist. Your job is to help define factors rigorously, understand when and why each factor works or fails, construct multi-factor portfolios, and manage the behavioral challenges of factor cyclicality.

## When to use it

Use it when the task requires:

- implementing carry, value, or momentum systematically across one or more asset classes
- understanding factor definitions beyond the single-asset level
- building a multi-factor portfolio that diversifies across factor exposures
- assessing whether a factor is crowded or in a favorable part of its cycle
- pairing with `backtesting-methodology` to test factor strategies or with `portfolio-construction` to integrate factors into a broader portfolio

## Data requirements

Retrieve from the data harness:

- Factor scores by asset and asset class (carry, value, momentum signals for each instrument)
- Cross-sectional rankings within each asset class (for long-short portfolio construction)
- Factor return histories (long-short factor portfolio returns over extended periods)
- Crowding indicators: positioning data, factor return correlations, dispersion measures
- Volatility and correlation data for risk-based weighting
- Transaction cost estimates by asset class and instrument for turnover management

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Factor Definitions by Asset Class

The three core factors -- carry, value, momentum -- are defined differently in each asset class. Precision in definition is essential; a factor strategy is only as good as its signal construction.

### Carry

Carry is the return earned from holding a position if nothing changes. It is compensation for providing liquidity, bearing risk, or being patient.

| Asset Class | Carry Signal | What It Captures |
|-------------|-------------|------------------|
| FX | Interest rate differential between currencies | Compensation for holding higher-yielding currency risk |
| Rates | Roll-down on the yield curve | Return from holding bonds that "roll" to lower yields as they age |
| Commodities | Futures curve shape (backwardation vs. contango) | Compensation for bearing spot price risk; storage economics |
| Equities | Dividend yield or earnings yield minus funding cost | Cash flow return to equity holders net of financing |
| Credit | Spread over risk-free rate | Compensation for bearing default and liquidity risk |
| Volatility | Variance risk premium (implied minus realized) | Compensation for providing insurance against tail events |

### Value

Value compares the current price to a fundamental anchor. It identifies assets that are cheap or expensive relative to where fundamentals suggest they should trade.

| Asset Class | Value Anchor | What It Captures |
|-------------|-------------|------------------|
| FX | PPP, REER, productivity-adjusted fair value | Deviation from long-run equilibrium exchange rate |
| Rates | R-star estimate, Taylor rule implied rate | Whether market rates are above or below policy-neutral level |
| Commodities | Marginal cost of production, inventory vs. history | Whether price is above or below the level that balances supply and demand |
| Equities | P/E, EV/EBITDA, FCF yield vs. history and peers | Whether the market is over- or under-paying for earnings and cash flow |
| Credit | Spread vs. fundamental default probability | Whether spread compensation exceeds or falls short of actual default risk |
| Volatility | Implied vs. realized, vol percentile rank | Whether options are expensive or cheap relative to actual price movement |

### Momentum

Momentum captures the tendency of assets moving in one direction to continue. It reflects the market's revealed preference and information diffusion.

| Momentum Type | Signal | What It Captures |
|---------------|--------|------------------|
| Price momentum | Trailing returns over defined lookback (3m, 6m, 12m) | Trend persistence, behavioral underreaction |
| Fundamental momentum | Direction of earnings revisions, economic surprise indices | Whether fundamental reality is improving or deteriorating |
| Flow momentum | Persistent fund flows, central bank operations, systematic rebalancing | Supply-demand imbalance in positioning |
| Cross-asset momentum | Confirmation or divergence across related markets | Whether the trend has broad support or is isolated |

## Factor Timing

### When each factor works

| Factor | Favorable Regime | Unfavorable Regime |
|--------|-----------------|-------------------|
| Carry | Low volatility, stable macro, positive risk appetite | Volatility spikes, crisis periods, sudden risk-off |
| Value | After valuation extremes, with patience, mean-reversion environments | Persistent trends, bubble dynamics, "this time is different" narratives |
| Momentum | Trending regimes, strong macro directionality, information diffusion periods | Sharp reversals, regime transitions, mean-reversion environments |

### When each factor fails

- **Carry**: carry trades are short volatility by nature. When volatility spikes -- financial crises, policy surprises, liquidity shocks -- carry positions unwind violently. The FX carry trade blowups of 2008 and the JGB carry unwind are canonical examples
- **Value**: value requires patience and can underperform for years when trends persist. The 2017-2020 growth-over-value regime in equities punished value strategies for an extended period. Value investing in a bubble is correct but early, and being early is indistinguishable from being wrong until the reversal
- **Momentum**: momentum fails at turning points. Reversals are fast and concentrated, and momentum portfolios are positioned maximally in the wrong direction at exactly the wrong time. Momentum crashes tend to be sharp, short, and correlated across asset classes

Understanding when factors fail is more important than understanding when they work. The failure modes determine the risk profile of the portfolio.

## Factor Blending

### Why blend

No single factor works all the time. The core insight of multi-factor investing is that carry, value, and momentum are driven by different economic forces and tend to fail at different times. Blending them reduces the probability and severity of any single-factor drawdown.

### Blending approaches

| Approach | Method | Trade-offs |
|----------|--------|------------|
| Equal weight | Allocate equal risk to each factor | Simple, robust, no timing required. Underperforms when one factor dominates |
| Regime-tilted | Overweight the factor favored by the current regime | Higher potential returns but requires accurate regime identification |
| Risk-parity | Weight factors inversely to their volatility | Equalizes risk contribution. May overweight low-vol factors in calm periods |
| Dynamic | Adjust weights based on factor valuations or crowding signals | Most complex. Requires disciplined signals and resists overfitting temptation |

The base case recommendation for most implementations is equal-weight or risk-parity blending. Tilting toward a favored factor requires high confidence in regime identification, and the evidence that factor timing adds value after costs is mixed.

### Factor correlations

The three factors are somewhat uncorrelated in normal environments, which is the entire basis for blending. Carry and momentum tend to have modest positive correlation (trending markets often reward carry). Value and momentum tend to have negative correlation (value is contrarian; momentum follows the trend). Carry and value have variable correlation depending on whether carry is compensating for real risk or is a crowded trade.

In crisis periods, correlations can spike as all factors sell off simultaneously. This is the risk that blending cannot fully diversify away.

## Implementation

### Long-short vs. long-only

- **Long-short factor portfolios**: the purest factor expression. Long the top quintile, short the bottom quintile. Captures the full factor premium. Requires the ability and willingness to short
- **Long-only tilts**: overweight high-factor-score assets, underweight low-score assets within a benchmark. Captures partial factor premium. Suitable when shorting is constrained or impractical
- **Factor-aware position weighting**: use factor scores as inputs to position sizing within a discretionary portfolio. Not a pure factor strategy but integrates systematic signals into judgment-based allocation

### Rebalancing and turnover

- Rebalancing frequency should match the factor's characteristic horizon. Momentum strategies typically rebalance monthly. Value strategies can rebalance quarterly or less frequently
- Higher turnover means higher transaction costs. A factor strategy that generates 200% annual turnover must clear a much higher cost bar than one that generates 50%
- Buffer rules (only rebalance when an asset's factor score crosses a threshold, not on every small change) reduce turnover without materially sacrificing signal quality

## Capacity and Crowding

### Why crowding matters

When a factor strategy becomes popular, many participants hold similar positions. The expected return of the factor compresses (the opportunity is arbed away), and the risk of a synchronized unwind increases. Crowded factors have smaller premia and larger tail risks.

### Crowding signals

- **Positioning data**: when speculative positioning in carry trades or momentum trades reaches historical extremes
- **Valuation compression**: when the spread between cheap and expensive assets (the value spread) narrows because everyone is buying the cheap assets
- **Correlation convergence**: when assets within a factor portfolio become increasingly correlated, suggesting a common holder
- **Factor return correlation**: when previously uncorrelated factors start moving together, suggesting a common liquidation
- **New entrants**: when new products, funds, or systematic strategies explicitly target the same factor

### The crowding paradox

The factors that have performed best recently attract the most capital, become the most crowded, and offer the worst prospective returns. This is the mechanism by which factor premia are self-correcting over time -- but the correction can be violent.

## Factor Cyclicality

Factors have multi-year performance cycles. Value outperformed from 2000-2007, underperformed from 2017-2020, then recovered sharply. Momentum has periodic crashes followed by recoveries. Carry earns steadily then gives back gains in crises.

The behavioral challenge: abandoning a factor during its down cycle is the most common and most expensive mistake in factor investing. Switching from value to momentum after value has underperformed for three years is systematically buying high and selling low at the factor level.

The discipline required: maintain factor exposure through drawdowns unless the economic rationale for the factor has structurally changed. A factor underperforming its historical average is not evidence that the factor is broken -- it may be evidence that the factor is cheap and prospective returns are improving.

## Evidence That Would Invalidate This Framework

- Permanent structural changes that eliminate the economic basis for a factor premium (e.g., central bank policies that permanently eliminate the term premium, rendering rates carry meaningless)
- Crowding so persistent and widespread that factor premia are permanently arbed away with no cyclical recovery
- Changes in market structure that make systematic implementation infeasible (e.g., transaction cost changes that exceed factor premia)

## Output structure

When applying this skill, prefer this order:

1. `Factor Definitions` -- how carry, value, and momentum are measured for the relevant asset class
2. `Current Factor Signals` -- what each factor says now (based on available data)
3. `Regime Assessment` -- which factors are favored or disfavored by the current environment
4. `Crowding Check` -- whether any factor appears crowded
5. `Blending Recommendation` -- how to combine factors given the current assessment
6. `Implementation Plan` -- long-short vs. tilt, rebalancing frequency, turnover management
7. `Risk Factors` -- what could cause the factor portfolio to draw down
8. `Next Skill` -- suggest `trader-thinking`, `backtesting-methodology`, `portfolio-construction`, or `risk-management` as appropriate

## Best practices

- do not chase the factor that has performed best recently; mean-reversion in factor returns is one of the most reliable patterns
- do not add complexity to factor definitions without clear evidence that it improves out-of-sample performance
- do not ignore transaction costs; many factor strategies that look good gross-of-fees are mediocre net-of-fees
- do not treat factor exposures as static; monitor for crowding, regime shifts, and structural changes
- do not abandon a factor during a drawdown without evidence that the economic rationale has changed
- do not confuse factor exposure with alpha; earning the value premium is not the same as generating idiosyncratic returns

## Usage examples

- "Use `factor-investing` to define carry, value, and momentum signals for G10 FX and suggest a blending approach."
- "Use `factor-investing` to assess whether the equity momentum factor is crowded given current positioning data."
- "Use `factor-investing` to help me build a multi-factor portfolio across rates, FX, and commodities using equal-risk weighting."
