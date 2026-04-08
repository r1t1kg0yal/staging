---
name: cross-asset-playbook
description: Map how macro forces transmit across asset classes -- rates, FX, credit, equities, commodities -- to validate or challenge single-asset theses using intermarket confirmation and divergence signals.
---

# Cross-Asset Playbook

Use this skill when the task requires understanding how a macro development in one asset class propagates to others, or when a single-asset thesis requires cross-asset confirmation before it deserves full conviction.

This skill will not:

- generate specific trade recommendations or position sizing
- replace dedicated analysis of any single asset class
- predict the timing of regime transitions
- claim causal certainty where only correlation exists

## Role

Act as a macro strategist who connects the dots across asset classes. Your job is to map transmission channels, identify confirmation or divergence across markets, and flag when the cross-asset picture strengthens or undermines a thesis.

## When to use it

Use it when the task requires:

- understanding how a rate move, policy shift, or growth shock ripples across markets
- checking whether signals from credit, FX, or commodities confirm or contradict an equity thesis
- identifying which asset class is leading and which is lagging in a regime transition
- building a macro view that integrates multiple markets rather than relying on one
- pairing with `macro-event-analysis` to assess second-order effects of a policy decision

## Data requirements

Retrieve from the data harness:

- Sovereign yield curves (front-end, belly, long-end) across major economies
- FX spot and forward rates for G10 and key EM pairs
- Credit spreads: investment grade, high yield, CDS indices
- Equity indices: broad market, sector-level, and regional
- Commodity prices: energy, metals, agriculture, and their futures curves
- Cross-asset correlation matrices (rolling windows, multiple horizons)
- Positioning data where available (futures positioning, fund flow data)

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Macro Transmission Channels

Macro forces do not arrive in one market and stay there. They cascade. The canonical transmission chain runs:

```
  Central bank policy / fiscal impulse
           |
           v
  Front-end rates (policy expectations)
           |
           v
  Yield curve shape (term premium, growth expectations)
           |
           v
  FX (rate differentials, capital flows, risk appetite)
           |
           v
  Credit spreads (funding conditions, default risk repricing)
           |
           v
  Equity multiples (discount rate, earnings expectations)
           |
           v
  Commodity demand (real economy, inventory cycle)
```

This is the base case ordering. In practice, shocks can enter at any point in the chain and propagate in both directions. A commodity supply shock transmits upward through inflation expectations to rates. A credit event transmits sideways into equities and FX simultaneously.

The key discipline is tracing the chain: if you believe rates are moving, ask what that implies for every link downstream. If equities are moving but rates and credit are not confirming, ask why.

## Correlation Regimes

Cross-asset relationships are not static. They cluster into recognizable regimes:

| Regime | Rates | Equities | Credit | FX (USD) | Commodities | Signature |
|--------|-------|----------|--------|-----------|-------------|-----------|
| Risk-on / risk-off | Driven by risk appetite | Correlate with credit | Tracks equity | Safe haven bid or sell | Pro-cyclical | Everything correlates; diversification fails |
| Tightening | Rising, front-end leads | Fragile, multiple compression | Spreads widen gradually | USD strengthens | Mixed, demand pressure | Policy is the dominant driver |
| Easing | Falling, curve steepens | Supported, multiple expansion | Spreads tighten | USD weakens | Supported by growth hopes | Liquidity is the dominant driver |
| Reflation | Rising modestly, curve steepens | Up, cyclicals lead | Tightening | USD mixed to weak | Rising, demand-driven | Growth optimism, commodity demand |
| Deflation | Falling sharply, curve flattens | Down, defensives outperform | Widening sharply | Safe haven bid | Falling, demand collapse | Growth pessimism, flight to safety |
| Stagflation | Rising despite weak growth | Down, no safe sector | Widening | USD mixed | Commodities up (supply-driven) | Hardest regime for portfolios |

Regime identification is the first step. The second step is asking: is the current regime stable, or are we transitioning? Transitions are where the largest dislocations and opportunities appear.

## Intermarket Signals and Divergences

### Credit leads equity

Credit markets typically price stress before equity markets. When investment grade or high yield spreads widen materially while equities remain near highs, this divergence is a warning signal. Credit investors are closer to cash flow and balance sheet reality; equity investors are more influenced by narrative and momentum.

### Yield curve as recession signal

A deeply inverted curve reflects expectations that policy rates will need to fall -- which historically requires an economic downturn. The signal is not the inversion itself but the subsequent steepening, which often coincides with the recession arriving and rate cuts beginning.

### FX as risk appetite barometer

Certain FX pairs function as real-time risk appetite gauges. High-carry EM currencies weaken in risk-off. Safe haven currencies (historically JPY, CHF, USD in acute stress) strengthen. When carry currencies diverge from equity direction, one market is wrong about risk appetite.

### Commodity curves as growth signal

Commodity futures curves contain information about supply-demand balance and growth expectations. Broad backwardation in industrial commodities suggests genuine physical demand. Contango suggests oversupply or weak demand. The shape of the oil curve is a widely watched cyclical indicator.

### When divergences appear

Divergences between asset classes mean one of three things:

1. One market is leading and the others will follow
2. One market is wrong and will correct
3. A structural change is underway and historical relationships are shifting

The base case should be option 1 or 2. Option 3 requires strong evidence before accepting it.

## Leading vs. Lagging in Regime Transitions

Not all asset classes move simultaneously when regimes shift:

```
  Typical ordering in a growth slowdown:

  FIRST    Credit spreads widen (3-6 months lead)
    |      Yield curve flattens / inverts
    v      Commodity demand softens
  MIDDLE   Equity volatility rises
    |      FX carry trades underperform
    v      Equity indices decline
  LAST     Policy response (rate cuts, fiscal)
           Equity capitulation
```

```
  Typical ordering in a recovery:

  FIRST    Policy easing (rate cuts, liquidity)
    |      Credit spreads stabilize and tighten
    v      Yield curve steepens
  MIDDLE   Commodity curves shift to backwardation
    |      Equity indices bottom and rally
    v      FX carry trade resumes
  LAST     Broad-based earnings recovery
           Inflation pressures rebuild
```

These orderings are base cases, not guarantees. Each cycle has idiosyncratic features. The value is in having a mental map to compare against, not in treating the sequence as mechanical.

## Practical Application

When using cross-asset signals to validate or challenge a single-asset thesis:

1. **State the thesis and its asset class.** Example: "I am bullish equities because earnings growth is accelerating."
2. **Check the other links in the chain.** Are rates consistent with this growth view? Is credit confirming? Are commodities reflecting demand strength? Is FX behaving as expected for this regime?
3. **Identify confirmation.** If credit is tightening, commodities are bid, and the curve is steepening -- the cross-asset picture supports the equity bull thesis.
4. **Identify divergence.** If credit is widening, commodities are rolling over, and the curve is flattening -- the cross-asset picture is warning you. The equity bull thesis requires an explanation for why these markets are wrong.
5. **Assess conviction accordingly.** Full cross-asset confirmation warrants higher conviction. Material divergence warrants reduced sizing, tighter stops, or pausing until the divergence resolves.

High conviction requires multiple asset classes telling the same macro story. When they disagree, something is mispriced or a transition is underway -- and the burden of proof falls on the thesis holder to explain the disagreement.

## Evidence That Would Invalidate This Framework

- Structural changes in market microstructure that permanently alter cross-asset transmission (e.g., central bank balance sheet policies that suppress volatility in one asset class indefinitely)
- Sustained breakdown of historical correlation regimes with no reversion
- New asset classes or instruments that create transmission channels not captured in the canonical chain

## Output structure

When applying this skill, prefer this order:

1. `Current Regime Assessment` -- which correlation regime best describes the present environment
2. `Transmission Chain` -- how the relevant macro force is propagating
3. `Cross-Asset Confirmation` -- which markets confirm the thesis
4. `Cross-Asset Divergence` -- which markets contradict or fail to confirm
5. `Leading / Lagging Assessment` -- which market is likely leading
6. `Conviction Adjustment` -- how the cross-asset picture modifies conviction
7. `Next Skill` -- suggest `macro-event-analysis`, `fi-relative-value`, `fx-carry-trade`, `scenario-analysis`, or `fundamental-analysis` as appropriate

## Best practices

- do not treat cross-asset correlations as stable constants; they shift with regimes
- do not ignore divergences because the primary thesis "feels right"
- do not assume the asset class you are focused on is the one leading
- do not confuse correlation with causation -- transmission channels are probabilistic, not mechanical
- do not use cross-asset signals to override strong single-asset evidence; use them to calibrate conviction

## Usage examples

- "Use `cross-asset-playbook` to check whether the rates market is confirming my equity bear thesis before I size the position."
- "Use `cross-asset-playbook` to map how the ECB rate decision might transmit from EUR rates to European credit and equity indices."
- "Use `cross-asset-playbook` to assess whether commodity strength is consistent with the reflation narrative or is supply-driven."
