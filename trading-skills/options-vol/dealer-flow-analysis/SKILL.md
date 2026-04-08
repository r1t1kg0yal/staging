---
name: dealer-flow-analysis
description: Analyze how dealer positioning and hedging flows affect market dynamics -- gamma exposure (GEX), vega exposure (VEX), dealer hedging mechanics, and flow-driven signals. Use when evaluating how market-maker positioning creates support/resistance, vol suppression, or convexity events.
---

# Dealer Flow Analysis

Use this skill when the task requires understanding how dealer/market-maker positioning and hedging flows affect market dynamics. When dealers are net long or short options, their hedging activity creates systematic price effects -- support/resistance at key strikes, vol suppression in positive gamma environments, and explosive moves when gamma flips negative. This skill reads the dealer positioning map and translates it into trading signals.

This skill will not:

- provide real-time dealer positioning data (the user supplies or retrieves this)
- predict dealer positioning changes from first principles
- replace fundamental or technical analysis
- guarantee that dealer hedging effects override macro drivers

## Role

Act like a derivatives-focused strategist who reads the options market as a positioning map. You understand that dealer hedging is not discretionary -- it is mechanical and rule-based. When dealers are long gamma, they buy dips and sell rallies (dampening moves). When dealers are short gamma, they sell into declines and buy into rallies (amplifying moves). The gamma profile of the dealer book creates predictable market behavior patterns.

## When to use it

Use it when the task requires:

- assessing whether dealers are net long or short gamma at current spot levels
- identifying key strike levels where dealer gamma concentrations create support or resistance
- evaluating whether dealer hedging is suppressing or amplifying realized vol
- understanding the transition from positive to negative gamma (the "gamma flip" level)
- interpreting VEX (vega exposure) and its implications for vol dynamics
- reading options open interest and volume patterns for positioning signals
- feeding dealer positioning context into `vol-framework`, `options-strategy-construction`, or `market-regime-analysis`

## Key concepts

### Gamma Exposure (GEX)
GEX measures the aggregate gamma exposure of dealers across all strikes for a given underlying. It tells you whether dealers need to buy or sell the underlying as it moves.

- **Positive GEX (dealers long gamma):** dealers buy as the market falls and sell as it rises. This creates a dampening effect -- realized vol is suppressed, the market tends to mean-revert around high-GEX strikes, and large directional moves are resisted.
- **Negative GEX (dealers short gamma):** dealers sell as the market falls and buy as it rises. This creates an amplifying effect -- realized vol is elevated, the market tends to trend, and moves become self-reinforcing.
- **Gamma flip level:** the price level at which aggregate dealer gamma transitions from positive to negative. This is often a critical support/resistance level.

### Vega Exposure (VEX)
VEX measures the aggregate vega exposure of dealers. It tells you how dealer P/L changes with implied vol shifts.

- **Positive VEX (dealers long vega):** dealers profit from vol increases. They may sell vol to reduce exposure, creating supply pressure on implied vol.
- **Negative VEX (dealers short vega):** dealers profit from vol decreases. They may buy vol to reduce risk, creating demand for implied vol.
- VEX is more relevant for understanding implied vol dynamics; GEX is more relevant for realized vol and spot dynamics.

### Dealer hedging mechanics
Dealers do not take directional views; they hedge mechanically based on their Greeks:

1. Customer buys calls: dealer is short calls, needs to buy underlying (positive delta) and manage negative gamma
2. Customer buys puts: dealer is short puts, needs to sell underlying (negative delta) and manage negative gamma
3. As market moves: dealer must rebalance delta continuously. The direction and size of rebalancing depends on the aggregate gamma profile.
4. At expiry: gamma concentrates at strikes with large open interest, creating "pinning" effects where the underlying gravitates toward max-pain levels

### Pin risk and max pain
Near options expiry, the underlying tends to gravitate toward strikes with the largest open interest. This is because dealers hedging expiring options create flows that push the price toward the level where the most options expire worthless (minimizing payout, which is "max pain" for option buyers).

## Analysis process

1. **Map the gamma profile.** Gather GEX data across strikes for the underlying. Identify:
   - Total net GEX (positive or negative)
   - The gamma flip level (where GEX transitions from positive to negative)
   - Key strike levels with large gamma concentrations
   - Whether gamma is concentrated in calls or puts

2. **Assess the current regime.**
   - Market above gamma flip: positive GEX environment. Expect mean-reversion, vol suppression, support at high-gamma strikes.
   - Market below gamma flip: negative GEX environment. Expect trending behavior, vol amplification, potential for cascading moves.
   - Market near gamma flip: transitional. Small moves can shift the regime; high uncertainty.

3. **Evaluate VEX implications.** Assess whether dealers are long or short vega:
   - Long VEX: dealers may sell vol, creating supply. Implied vol likely to be compressed.
   - Short VEX: dealers may buy vol, creating demand. Implied vol may find support or spike.

4. **Identify key levels.** Map the high-concentration strikes:
   - Large call OI strikes above current spot: potential resistance (dealers sell as market approaches)
   - Large put OI strikes below current spot: potential support (dealers buy as market approaches)
   - Upcoming expiry dates: near-expiry gamma is highest, making pinning effects strongest

5. **Assess flow signals.** Look at recent options volume and open interest changes:
   - Unusual volume at specific strikes: new positioning being established
   - OI increase with price move: new positions (confirmation)
   - OI decrease with price move: closing positions (potential reversal)
   - Put/call ratio shifts: sentiment indicator

6. **Translate to trading signals.** Map the dealer positioning picture to actionable views:
   - Positive GEX + market above flip: low-vol environment; selling premium may work; directional moves likely to be faded
   - Negative GEX + market below flip: high-vol environment; buying premium may work; directional moves likely to extend
   - Large gamma at specific strike near expiry: potential magnet/pin
   - GEX transitioning (market approaching flip level): regime change imminent; position for vol expansion

## Core Assessment Framework

Assess the dealer positioning on four anchors:

- `Gamma Regime`: is aggregate GEX positive or negative at current spot? Is the market above or below the gamma flip level?
- `Gamma Concentration`: where are the largest gamma concentrations? Are they in calls (above) or puts (below)? Do they create clear support/resistance?
- `Vega Signal`: is VEX positive or negative? What does this imply for implied vol dynamics?
- `Expiry Dynamics`: are there near-term expirations with large OI that could create pinning or gamma events?

Use the anchors to classify:

- `dampened/pinned`: positive GEX, large gamma concentrations, near-expiry effects active. Market likely range-bound. Favor selling vol, fading moves.
- `transitional`: market near gamma flip, regime about to change. Favor buying vol or reducing risk.
- `amplified/trending`: negative GEX, dealer hedging reinforcing moves. Market likely to trend. Favor buying vol, trend-following, avoiding mean-reversion.

## Output tables

### GEX Summary
| Metric | Value |
|--------|-------|
| Net GEX | Positive / Negative |
| Gamma Flip Level | ... |
| Current Spot vs Flip | Above / Below / Near |
| Regime | Dampened / Transitional / Amplified |

### Key Gamma Strikes
| Strike | GEX ($M per 1%) | Type (Call/Put) | Expiry | Signal |
|--------|-----------------|-----------------|--------|--------|
| ... | ... | ... | ... | Support / Resistance / Pin |

### VEX Assessment
| Metric | Value |
|--------|-------|
| Net VEX | Positive / Negative |
| Implied Vol Signal | Supply pressure / Demand pressure |

## Evidence that would invalidate this analysis

- a macro event overwhelms dealer hedging effects (in a genuine crisis, dealer gamma is irrelevant)
- positioning data is stale or inaccurate (GEX estimates depend on assumptions about dealer vs customer positioning)
- a large options expiry resets the gamma profile materially
- dealers offload risk to other dealers or through OTC markets in ways not visible in exchange data
- the underlying's options market is too illiquid for dealer hedging to affect spot materially

## Output structure

Prefer this output order:

1. `Dealer Positioning Summary`
2. `GEX Summary` (table)
3. `Key Gamma Strikes` (table)
4. `VEX Assessment` (table)
5. `Regime Classification`
6. `Expiry Dynamics`
7. `Trading Implications`
8. `Key Risks And Limitations`
9. `Next Skill`

Always include:

- whether GEX is positive or negative and the gamma flip level
- key support/resistance strikes from gamma concentrations
- the regime classification (dampened, transitional, amplified)
- how the positioning picture affects the vol outlook
- whether the analysis should feed into `vol-framework`, `options-strategy-construction`, `market-regime-analysis`, or `trade-expression`

## Best practices

- dealer hedging effects are strongest in liquid, index-level markets (SPX, QQQ) and weaker in single stocks with lower options OI
- GEX estimates are approximations; they depend on assumptions about who is long and short at each strike
- positive GEX environments can persist for weeks; do not assume a regime flip is imminent just because GEX is high
- the gamma flip level is a critical reference point but is not static; it changes daily as options decay and new positions are established
- near expiry, gamma effects are amplified but expire quickly; pin effects are strongest on the day of expiry
- in a genuine macro shock, dealer positioning is overwhelmed; do not rely on GEX levels during systemic events
- always combine dealer flow analysis with fundamental and vol surface analysis; positioning alone is not sufficient

## Usage examples

- "Use `dealer-flow-analysis` to assess SPX dealer gamma at current levels. I want to know whether dealers are suppressing vol or amplifying it."
- "Use `dealer-flow-analysis` to identify the gamma flip level for QQQ. The market has been declining and I want to know where the regime changes."
- "Use `dealer-flow-analysis` to evaluate expiry dynamics. Large OI at the 4500 strike expires Friday and I want to understand the pinning risk."
- "Use `dealer-flow-analysis` to assess whether dealer VEX is creating supply pressure on implied vol. VIX seems suppressed given the macro uncertainty."
