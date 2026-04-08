---
name: rates-vol-swaptions
description: Analyze rates-specific volatility instruments -- swaptions, caps/floors, rate options -- and construct conditional rates trades. Covers normal vs lognormal vol conventions, swaption surface interpretation, vol spread trades, structural supply/demand for rates vol, and conditional steepener/flattener construction. Use when working with rates options specifically, not equity/FX vol.
---

# Rates Vol & Swaptions

Use this skill when the task involves rates-specific volatility instruments and conditional trades. The rates vol surface has its own conventions (normal vol, not lognormal), its own structural supply/demand dynamics (mortgage hedgers, callable issuers, exotics desks), and its own trade structures (conditional steepeners, vol spread trades, yield curve spread options). This skill handles all of those.

This skill will not:

- interpret equity or FX vol surfaces (use `vol-framework` for the general framework)
- construct generic options strategies (use `options-strategy-construction`)
- replace macro analysis of rate direction (use `macro-event-analysis` or `curve-trading`)
- price swaptions computationally (it provides the analytical framework; the user supplies or retrieves pricing data)

## Role

Act like a rates vol trader who thinks in terms of normal vol (bp/year), swaption expiry-tail grids, structural flows (mortgage, callable, exotics), and conditional trade construction. You understand that the rates vol surface is shaped by structural supply and demand at specific points, not just rate expectations, and that conditional trades are the highest-expression form of rates trading.

## When to use it

Use it when the task requires:

- interpreting the swaption vol surface (normal vol grid by expiry and tail)
- understanding structural supply/demand for rates vol (who is structurally long or short vol at which points)
- constructing conditional trades (steepeners, flatteners, spread trades that activate only in specific rate scenarios)
- analyzing vol spread trades (tail switches, expiry switches, vega-neutral vs gamma-neutral weighting)
- understanding caps vs swaptions and the correlation driver between them
- interpreting risk reversals and skew in rates space
- evaluating yield curve spread options (YCSOs)
- feeding rates vol analysis into `curve-trading`, `fi-relative-value`, or `vol-framework`

## Vol conventions in rates

**Normal (Bachelier) vol** is the standard convention for rates options. Expressed in basis points per year.
- Rates move in absolute terms (Fed hikes 25bp regardless of whether the level is 2% or 5%)
- Normal vol stays well-behaved near zero rates; lognormal vol explodes

**Lognormal (Black) vol** is sometimes quoted for comparison. Expressed in percent per year.
- Conversion: normal bp vol approximately equals lognormal % vol times the forward rate
- At 4% forward and 20% lognormal vol: normal vol = 80bp/yr
- Daily bp vol = annual / sqrt(251) approximately annual / 15.84

**Wrong convention = severe mispricing:** near-zero rates, lognormal vol becomes meaningless; at high rates, normal vol understates percentage-move risk. Always confirm which convention is being used.

## Swaption surface structure

The swaption surface is a grid of implied vol indexed by:
- **Expiry** (option maturity): 1M, 3M, 6M, 1Y, 2Y, 5Y, 10Y
- **Tail** (underlying swap tenor): 1Y, 2Y, 5Y, 10Y, 20Y, 30Y

**Notation:** expiry x tail. Example: 1Y x 10Y = 1-year option on a 10-year swap.

**Key surface features:**
- **Expiry term structure:** how vol varies across option expiries for a given tail. Normal: upward-sloping (longer expiry = more time for events). Inverted: near-term stress or catalyst.
- **Tail term structure:** how vol varies across swap tenors for a given expiry. Reflects where rate uncertainty concentrates.
- **Smile/skew:** vol varies by moneyness. In rates: near-zero rates produce steep positive skew (downside puts expensive); high rates produce more symmetric smile.

## Structural supply and demand

The rates vol surface is shaped by structural flows that create persistent richness or cheapness at specific grid points:

### Structural demand for vol (buyers)
- **Mortgage GSE portfolios:** short the prepayment option embedded in MBS. Buy long-expiry, intermediate-tail swaptions (e.g., 3Y x 10Y) to hedge. Supports vol in this sector.
- **Mortgage servicers:** short vol via prepayment sensitivity. Buy short-expiry, intermediate-tail options. Supports front-end of the vol surface for 5-10Y tails.

### Structural supply of vol (sellers)
- **Callable debt issuers:** issuing callable bonds = being long a call on rates. They sell swaptions to offset. Concentrated in 5Y x 30Y type structures when callable issuance is heavy.
- **Exotics desks:** depends on structured note flows. Range accrual notes (pay coupon if rate stays in range) leave dealers long caps, which they sell into the market, depressing cap vol vs swaption vol.

### Implication
The vol surface shape is not purely about rate expectations; it reflects mortgage hedging, callable issuance, and exotics recycling at specific expiry/tail points. Understanding who is structurally long or short at each point is essential for identifying cheap and expensive vol.

## Conditional trade construction

Conditional trades express curve or spread views that activate only in specific rate scenarios. They are the highest-expression form of rates trading.

### Conditional steepener (canonical example)
- Sell payer swaptions on the short-end + buy payer swaptions on the long-end (same expiry)
- Rates fall: both expire worthless (conditional protection -- you lose nothing)
- Rates rise: both exercised, investor enters a DV01-neutral steepener
- Net effect: curve steepens only if rates rise; zero exposure if rates fall

### Construction rules
1. DV01-weight option notionals so that exercise produces zero P/L for a parallel rate shift
2. Required notional ratio = long-end DV01 times notional / short-end DV01
3. Check premium: "at the forwards" = zero net premium (ideal). "Worse than forwards" = paying premium. If worse than forwards, just do the outright trade.
4. Compare implied vol of bought vs sold leg: higher implied on bought leg = net cost; higher on sold leg = net receipt
5. Expiry typically less than 3 months (hold-to-exercise design)

### Conditional spread trade
Same framework applies to swap spreads conditional on yield direction:
- Mortgage-driven widening in selloffs can be isolated via a conditional widener using payer swaptions
- This separates the spread view from the rally risk

## Vol spread trades

Express relative views on implied or realized vol between different parts of the surface:

### Tail switch (same expiry, different tails)
- Example: buy 6M x 2Y, sell 6M x 10Y
- Profits if short-tail vol rises relative to long-tail vol
- Vega-neutral weighting: equalize total vega of both legs
- For same-expiry switches: gamma-neutral approximately equals vega-neutral

### Expiry switch (same tail, different expiries)
- Example: buy 6M x 10Y, sell 3Y x 10Y
- Profits if short-expiry vol rises relative to long-expiry vol
- Vega-neutral vs gamma-neutral produce very different trades:
  - Short-dated options have high gamma, low vega
  - Long-dated options have low gamma, high vega
  - Vega-neutral: overweights short-dated leg, leaves trade long gamma
  - Gamma-neutral: overweights long-dated leg, leaves trade short vega
- When setting up any switch, track all risk parameters; neutralizing one can leave large unintended exposure on the other

### Caps vs swaptions
- Cap vol approximates average volatility of underlying forward rates (portfolio of caplets)
- Swaption vol approximates volatility of the average of forward rates (single option on swap rate)
- Difference is driven by correlation between forward rates
- Structured note issuance (range accruals) can depress cap vol vs swaption vol; track issuance

## Yield curve spread options (YCSOs)

Options on the spread between two yields (e.g., 3M x 2s/10s call struck at 150bp).
- Curve call = steepener with asymmetry; curve put = flattener with asymmetry
- Payoff is linear in yield spread (no convexity) but hedge uses swaps (which have convexity), requiring a convexity adjustment to the strike
- Convexity adjustment depends on vol of underlying rates
- Useful when the curve view is conditional on magnitude (want steepening but only if it goes beyond a threshold)

## Analysis process

1. **Map the vol surface.** Examine the swaption grid at key expiry/tail combinations. Identify where vol is rich or cheap relative to history and relative to other grid points.

2. **Identify structural influences.** Which structural flows (mortgage, callable, exotics) are active at the relevant grid points? Are they pushing vol higher or lower than fundamentals justify?

3. **Match view to structure.** Based on the user's rates/vol view:
   - Directional rate view with conditionality: conditional steepener/flattener
   - Vol view on specific grid point: buy/sell swaptions at that point
   - Relative vol view: tail switch or expiry switch
   - Curve view with asymmetry: YCSO
   - Rate-conditional spread view: conditional spread trade

4. **Construct and weight.** For the chosen structure:
   - Determine notionals (DV01-weighted for directional, vega or gamma-neutral for vol spread)
   - Compute net premium
   - Assess breakeven scenarios
   - Check premium neutrality (at the forwards vs worse than forwards)

5. **Risk assessment.** Identify what Greeks are left unhedged and what residual exposures remain after neutralizing the target dimension.

## Output tables

### Swaption Surface Snapshot
| Expiry \ Tail | 2Y | 5Y | 10Y | 30Y |
|---------------|-----|-----|------|------|
| 1M | ... | ... | ... | ... |
| 3M | ... | ... | ... | ... |
| 1Y | ... | ... | ... | ... |
| 5Y | ... | ... | ... | ... |

(Normal vol in bp/yr)

### Conditional Trade Structure
| Parameter | Value |
|-----------|-------|
| Type | Conditional steepener / flattener / spread |
| Bought leg | ... expiry x ... tail, payer/receiver, notional ... |
| Sold leg | ... expiry x ... tail, payer/receiver, notional ... |
| Net premium | ... (at the forwards / cost / receipt) |
| If rates fall | ... (both expire worthless / ...) |
| If rates rise | ... (exercised into DV01-neutral ...) |
| Breakeven | ... |

## Evidence that would invalidate this analysis

- a shift in mortgage hedging behavior (product mix, prepayment model changes) alters structural demand at key grid points
- a change in callable or structured note issuance patterns alters structural supply
- a vol regime change (crisis or calm) makes historical surface relationships unreliable
- a change in the rate level that shifts the relevance of normal vs lognormal conventions
- central bank forward guidance that anchors specific parts of the curve, suppressing vol at those points

## Output structure

Prefer this output order:

1. `Rates Vol Summary`
2. `Surface Snapshot` (table)
3. `Structural Flow Assessment`
4. `Trade Construction`
5. `Risk And Greeks`
6. `Historical Context`
7. `Key Risks`
8. `Next Skill`

Always include:

- vol convention used (normal bp/yr)
- which structural flows are active at the relevant grid points
- the trade structure with sizing and premium
- residual exposures after neutralization
- whether the analysis should feed into `curve-trading`, `fi-relative-value`, or `greeks-pnl-management`

## Best practices

- always use normal vol for rates options; confirm convention before comparing across sources
- remember that the vol surface reflects structural flows, not just rate expectations; understand who is long and short at each point
- conditional trades are superior to outright when the curve view depends on rate direction
- if the conditional trade costs premium (worse than forwards), consider the outright instead
- for vol spread trades, track all Greeks; neutralizing vega can leave gamma exposure and vice versa
- cap vs swaption vol spread is driven by forward rate correlation and structured note issuance; not a pure vol signal
- YCSOs require a convexity adjustment because the hedge (swaps) has convexity but the payoff (spread) is linear

## Usage examples

- "Use `rates-vol-swaptions` to evaluate the swaption surface for USD. I want to know where vol is cheap relative to history and structural flows."
- "Use `rates-vol-swaptions` to construct a conditional steepener for 2s10s. I want the steepening view only if rates sell off."
- "Use `rates-vol-swaptions` to analyze a vol tail switch: buy 3M x 2Y vs sell 3M x 10Y. Is the short-tail vol cheap enough?"
- "Use `rates-vol-swaptions` to assess whether mortgage hedging demand is supporting 1Y x 10Y swaption vol above fair value."
