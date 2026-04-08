---
name: greeks-pnl-management
description: Manage options positions through practical Greeks interpretation, P/L decomposition, delta hedging, gamma/theta trade-offs, and roll decisions. Use when an options position is open and needs ongoing management -- understanding what is driving P/L, when to hedge, when to roll, and how Greeks change as the underlying moves.
---

# Greeks & P/L Management

Use this skill when the task is to manage an open options position -- understanding what is driving P/L, deciding when and how to hedge, managing gamma/theta trade-offs, and making roll decisions. This is the ongoing management companion to `options-strategy-construction` (which selects the initial structure) and `vol-framework` (which interprets the surface).

This skill will not:

- select the initial options strategy (use `options-strategy-construction`)
- interpret the vol surface from scratch (use `vol-framework`)
- size the position (use `position-sizing`)
- make the hold/close decision at a portfolio level (use `position-management`)

## Role

Act like an options portfolio manager who monitors positions through the lens of Greeks, P/L attribution, and hedging decisions. You decompose P/L into its components (delta, gamma, theta, vega, rho, and higher-order) and use that decomposition to decide the next action. You understand that managing options is not set-and-forget -- it requires ongoing decisions about hedging frequency, roll timing, and risk limits.

## When to use it

Use it when the task requires:

- decomposing an options position's P/L into Greek components
- deciding whether and how to delta hedge (and at what frequency)
- managing gamma/theta trade-offs (the fundamental tension in options positions)
- deciding when to roll a position (expiry approaching, strike drifting, theta accelerating)
- understanding how Greeks change as the underlying moves, time passes, or vol shifts
- assessing portfolio-level Greeks across multiple options positions
- feeding Greeks analysis into `position-management` or `risk-management`

## Greek definitions and practical interpretation

### Delta
Sensitivity of option price to underlying price change. First-order directional exposure.
- Long call: positive delta (profits as underlying rises)
- Long put: negative delta (profits as underlying falls)
- ATM options: delta near 0.50 (calls) or -0.50 (puts)
- OTM options: delta approaches 0 as you move further out
- Delta is not constant; it changes with underlying price (gamma), time (charm), and vol (vanna)

### Gamma
Rate of change of delta as the underlying moves. Second-order price sensitivity.
- Long options have positive gamma: delta moves in your favor (becomes more long as underlying rises, more short as it falls)
- Short options have negative gamma: delta moves against you
- Gamma is highest for ATM options near expiry (gamma risk concentrates as time decays)
- Gamma is your friend when the market moves and your enemy when it doesn't

### Theta
Time decay -- the cost of holding an option position per day.
- Long options have negative theta: position loses value each day (paying rent for the right to benefit from moves)
- Short options have positive theta: position gains value each day (collecting rent for bearing the risk of moves)
- Theta accelerates as expiry approaches, especially for ATM options
- Theta is the direct counterpart to gamma: high gamma = high theta cost

### Vega
Sensitivity to changes in implied volatility.
- Long options have positive vega: profit from vol increases
- Short options have negative vega: profit from vol decreases
- Vega is highest for ATM, long-dated options
- For short-dated options, gamma dominates; for long-dated, vega dominates

### Rho
Sensitivity to interest rate changes. Usually small for equity options but can matter for long-dated or deep ITM positions, and is significant for rates options (swaptions, caps/floors).

## P/L decomposition

Every options P/L can be decomposed into its Greek components:

**P/L = Delta P/L + Gamma P/L + Theta P/L + Vega P/L + Rho P/L + Residual**

- Delta P/L = delta x change in underlying price
- Gamma P/L = 0.5 x gamma x (change in underlying price)^2
- Theta P/L = theta x days elapsed
- Vega P/L = vega x change in implied vol
- Residual captures higher-order effects (vanna, charm, volga) and bid-ask friction

**The core relationship (delta-hedged):**
When delta is hedged, P/L simplifies to:
- P/L approximately equals f(realized vol - implied vol)
- Long option + delta hedge: profitable when realized vol > implied vol
- Short option + delta hedge: profitable when realized vol < implied vol
- Implied vol is the breakeven: the level of underlying movement needed for gamma P/L to overcome theta decay

## Delta hedging decisions

### When to hedge
- **Fixed interval:** hedge at set times (daily, twice daily). Simple to implement, may miss intraday moves.
- **Delta threshold:** hedge when delta has drifted by a specified amount (e.g., 5 delta points). Responsive but can lead to over-trading in choppy markets.
- **Regime-dependent:** adjust frequency based on market character.

### Hedging frequency and market regime
- **Mean-reverting market (high intraday vol, low multi-day vol):**
  - Long options: hedge frequently to capture high realized vol on short timeframes
  - Short options: hedge infrequently to avoid buying high and selling low repeatedly
- **Trending market (low intraday vol, high multi-day vol):**
  - Long options: hedge infrequently to let the trend accumulate larger gamma P/L
  - Short options: hedge frequently to limit the damage from the directional trend
- In practice, the regime is unknown in advance; use guidelines with regime-aware adjustments

### Transaction cost consideration
Each hedge incurs bid-ask cost. Over-hedging in a choppy market can bleed the position through transaction costs even if the option position is theoretically profitable. Balance precision against cost.

## Gamma/theta trade-off

This is the fundamental tension:

- Gamma P/L = 0.5 x gamma x (move)^2 -- earned from market moves
- Theta P/L = theta x days -- paid as time passes

For a long option position: gamma pays when the market moves, theta charges every day regardless. The question is whether realized moves are large enough to overcome the daily theta cost.

- When realized vol > implied vol: gamma P/L > theta cost, net positive
- When realized vol < implied vol: theta cost > gamma P/L, net negative
- ATM options have the highest gamma AND the highest theta -- these are not independent quantities

## Roll decisions

### When to roll
- **Theta acceleration:** as expiry approaches, theta for ATM options accelerates. If the view hasn't played out, rolling to a later expiry resets the theta clock.
- **Strike drift:** if the underlying has moved significantly, the original strike may be deep ITM or far OTM. Rolling to a new strike re-centers the Greeks.
- **Vol regime change:** if vol has spiked and you're long vol, consider rolling strikes or expiries to lock in the vol gain.
- **Liquidity deterioration:** as expiry approaches, bid-ask may widen for specific strikes. Roll before liquidity dries up.

### How to roll
- Same strike, later expiry (pure time extension): pay additional premium for more time
- Different strike, same expiry (strike adjustment): re-centers the position
- Different strike and expiry (full repositioning): essentially a new trade; evaluate as such

## Portfolio Greeks

For multiple options positions, aggregate Greeks by summing across positions:

- Portfolio delta = sum of all position deltas (in underlying-equivalent terms)
- Portfolio gamma = sum of all position gammas
- Portfolio theta = sum of all position thetas
- Portfolio vega = sum of all position vegas

**Cross-Greek exposure:** be aware that a portfolio may be delta-neutral but have large gamma or vega exposure. A "hedged" portfolio is only hedged along the dimension that was targeted.

## Analysis process

1. **Compute current Greeks.** For each position and the portfolio aggregate: delta, gamma, theta (daily), vega.

2. **P/L attribution.** Decompose recent P/L into delta, gamma, theta, vega, and residual components. Identify which Greek is driving results.

3. **Hedging assessment.** Is delta exposure within target range? If not, compute the hedge trade. Assess whether the current hedging frequency is appropriate for the market regime.

4. **Gamma/theta status.** Is the gamma/theta trade-off working in the position's favor?
   - Long options: is realized vol exceeding implied (gamma earning more than theta costs)?
   - Short options: is realized vol below implied (theta income exceeding gamma costs)?

5. **Roll assessment.** Should any positions be rolled?
   - Check theta acceleration (how many days until acceleration becomes punitive)
   - Check strike drift (is the position still expressing the original view?)
   - Check liquidity (are bid-asks still tight?)

6. **Risk check.** Are portfolio-level Greeks within acceptable bounds? Flag any concentration (e.g., all vega in one name, gamma concentrated near expiry).

## Output tables

### Position Greeks
| Position | Delta | Gamma | Theta/Day | Vega | DTE |
|----------|-------|-------|-----------|------|-----|
| ... | ... | ... | ... | ... | ... |
| **Portfolio** | **...** | **...** | **...** | **...** | |

### P/L Attribution
| Component | P/L ($) | P/L (%) | Driver |
|-----------|---------|---------|--------|
| Delta | ... | ... | Underlying moved ... |
| Gamma | ... | ... | Convexity from ... move |
| Theta | ... | ... | ... days elapsed |
| Vega | ... | ... | IV changed ... |
| Residual | ... | ... | Higher-order / friction |
| **Total** | **...** | **...** | |

### Action Recommendations
| Action | Rationale | Urgency |
|--------|-----------|---------|
| Delta hedge: ... | Delta drifted ... from target | High / Medium / Low |
| Roll: ... | Theta accelerating, DTE = ... | ... |
| Close: ... | View invalidated / target reached | ... |

## Evidence that would invalidate this analysis

- the user's view changes, making the current structure inappropriate
- a regime change (vol spike, correlation shift) makes historical Greeks behavior unreliable
- liquidity in the options deteriorates, making hedging or rolling impractical
- the P/L decomposition reveals the position is dominated by a Greek the user did not intend to be exposed to

## Output structure

Prefer this output order:

1. `Position Summary`
2. `Position Greeks` (table)
3. `P/L Attribution` (table)
4. `Delta Hedging Assessment`
5. `Gamma/Theta Status`
6. `Roll Assessment`
7. `Action Recommendations` (table)
8. `Next Skill`

Always include:

- current Greeks for each position and portfolio aggregate
- P/L decomposition showing which Greek is driving returns
- whether delta hedging is needed and the recommended trade
- whether any positions should be rolled
- whether the analysis should feed into `position-management`, `risk-management`, or `options-strategy-construction` (for restructuring)

## Best practices

- delta hedging is vol monetization: long option + hedge = buying low / selling high (if market moves enough); short option + hedge = buying high / selling low
- gamma and theta have identical shapes across strikes; high gamma always means high theta cost
- in mean-reverting markets, long options benefit from frequent hedging; in trending markets, benefit from infrequent hedging
- path dependency matters: gamma P/L depends not just on total realized vol but on where the vol occurs relative to your strike
- skew creates hidden delta: as the underlying moves, the implied vol at the new strike changes, creating additional P/L beyond pure Black-Scholes delta
- the standard delta underestimates true sensitivity when skew is steep

## Usage examples

- "Use `greeks-pnl-management` to decompose the P/L on my SPX put spread this week. The market moved down 2% but my P/L was less than expected."
- "Use `greeks-pnl-management` to evaluate whether I should hedge my AAPL call position. Delta has drifted significantly from my target."
- "Use `greeks-pnl-management` to assess my portfolio Greeks. I have several options positions across names and want to understand my aggregate exposure."
- "Use `greeks-pnl-management` to decide whether to roll my TSLA straddle. It expires in 5 days and the move hasn't happened yet."
