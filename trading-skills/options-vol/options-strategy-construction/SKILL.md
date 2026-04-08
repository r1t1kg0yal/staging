---
name: options-strategy-construction
description: Choose and construct options strategies -- spreads, straddles, condors, calendars, diagonals, ratio spreads -- matched to the user's market view and vol regime. Use when the view is formed and the question is which options structure best expresses it given current vol, skew, and term structure conditions.
---

# Options Strategy Construction

Use this skill when the view is formed and the question is how to express it using options. This skill maps directional, volatility, and range views to specific multi-leg options structures, accounting for the current vol surface, skew, term structure, and carry profile. It is the strategy-selection layer between having a view and entering a position.

This skill will not:

- form the market view (use `trader-thinking`, `macro-event-analysis`, or relevant domain skill)
- interpret the vol surface (use `vol-framework` for that)
- compute precise option prices (the user provides or retrieves pricing data)
- manage open options positions (use `position-management` and `greeks-pnl-management`)

## Role

Act like an options strategist who thinks of options as building blocks that can be assembled to match any payoff profile. You call them LEGOs. Your job is to match the user's view to the structure that best expresses it, considering premium cost, Greeks profile, breakevens, max profit, max loss, and how the vol surface affects each structure.

## When to use it

Use it when the task requires:

- choosing between single-leg and multi-leg options structures for a given view
- constructing a spread, straddle, strangle, condor, butterfly, calendar, diagonal, or ratio spread
- comparing strategies on a risk-adjusted basis (premium, breakevens, max loss, Greeks)
- selecting the optimal expiry and strike given the vol term structure and skew
- understanding how the current vol regime affects strategy selection
- feeding a strategy choice into `position-sizing`, `execution-plan-check`, or `greeks-pnl-management`

## Strategy menu

### Directional views (bullish or bearish)

| Strategy | Structure | Best When | Key Tradeoff |
|----------|-----------|-----------|--------------|
| Long call/put | Buy single option | High conviction, vol cheap, catalyst imminent | Unlimited upside but full premium at risk; theta bleeds daily |
| Vertical spread (debit) | Buy ATM/ITM, sell OTM same expiry | Moderate conviction, want to reduce premium | Capped profit but lower cost and breakeven |
| Vertical spread (credit) | Sell ATM/OTM, buy further OTM same expiry | Vol expensive, want income with defined risk | Limited premium collected; wider max loss |
| Ratio spread | Buy 1 ATM, sell 2+ OTM | Moderate move expected, vol expensive for OTM | Free or credit entry; naked short risk beyond sold strikes |
| Risk reversal | Buy call, sell put (or vice versa) | Strong directional conviction, willing to accept downside | Zero or near-zero premium; unlimited risk on the sold side |
| Diagonal | Buy longer-dated, sell shorter-dated different strike | Directional with time decay capture | Complex Greeks; benefits from term structure steepness |

### Volatility views (long or short vol)

| Strategy | Structure | Best When | Key Tradeoff |
|----------|-----------|-----------|--------------|
| Long straddle | Buy ATM call + ATM put | Big move expected, direction uncertain | Expensive premium; needs large move to profit |
| Long strangle | Buy OTM call + OTM put | Big move expected, willing to accept wider breakevens for lower cost | Cheaper than straddle but needs even larger move |
| Short straddle | Sell ATM call + ATM put | Low vol expected, range-bound market | Unlimited risk; steady theta income if quiet |
| Short strangle | Sell OTM call + OTM put | Range expected, vol overpriced | Lower premium than straddle but wider profit range |
| Iron condor | Sell OTM put + sell OTM call, buy further OTM put + call | Range expected, want defined risk | Defined max loss; lower margin than naked short |
| Iron butterfly | Sell ATM straddle + buy OTM strangle | Range expected, centered, defined risk | Sharper P/L profile than condor; max profit at ATM |

### Time decay views (term structure plays)

| Strategy | Structure | Best When | Key Tradeoff |
|----------|-----------|-----------|--------------|
| Calendar spread | Buy longer-dated, sell shorter-dated, same strike | Term structure steep (front vol high), expect front to decay faster | Benefits from vol term structure normalization; vega-exposed |
| Double calendar | Calendars at two strikes (one call, one put) | Range view with term structure play | More complex; wider profit zone but higher premium |
| Diagonal spread | Calendar with different strikes | Directional bias + time decay capture | Combines directional and calendar elements |

### Event trades

| Strategy | Structure | Best When | Key Tradeoff |
|----------|-----------|-----------|--------------|
| Pre-event straddle/strangle | Buy straddle before catalyst, sell after | Event vol underpriced relative to expected move | Expensive if event vol already elevated; vol crush risk |
| Post-event credit spread | Sell premium after event resolves | Vol crush expected, range established | Risk of second catalyst or delayed reaction |
| Event butterfly | Buy body at expected post-event level | Precise post-event target, cheap structure | Narrow profit zone; must be right on magnitude |

## Analysis process

1. **Clarify the view.** What does the user expect?
   - Directional (up or down) with magnitude estimate
   - Volatility (big move expected, or range-bound)
   - Time-dependent (catalyst timing, term structure play)
   - Combination (directional with vol view overlay)

2. **Assess the vol surface.** Pull from `vol-framework` or available data:
   - ATM vol level: is overall vol cheap or expensive? High vol favors selling premium; low vol favors buying.
   - Skew: steep negative skew makes puts expensive, favoring put spreads over outright puts. Flat skew reduces the penalty for outright options.
   - Term structure: steep (front high) favors calendars and selling near-dated. Flat or inverted favors buying near-dated.

3. **Match view to structure.** Using the strategy menu:
   - Strong directional + cheap vol: outright options or risk reversals
   - Strong directional + expensive vol: vertical spreads or ratio spreads
   - Moderate directional: debit spreads
   - Big move, direction uncertain: straddles or strangles
   - Range-bound + expensive vol: iron condors, short strangles, credit spreads
   - Term structure steep + range view: calendar spreads
   - Event-driven: event straddle (pre) or credit structure (post)

4. **Select strikes and expiry.**
   - Strike selection: based on delta targets (e.g., 25-delta for OTM wings, ATM for body), support/resistance levels, or breakeven targets
   - Expiry selection: match to the catalyst timeline. Too short = insufficient time for thesis to play out. Too long = overpaying for time value. Sweet spot is typically 1.5-2x the expected catalyst horizon.
   - For multi-leg: ensure strikes provide adequate risk/reward. For spreads, the width between strikes determines max profit and max loss.

5. **Compute structure metrics.** For the chosen strategy:
   - Net premium (debit or credit)
   - Breakeven point(s)
   - Max profit and the underlying level(s) that produce it
   - Max loss and when it occurs
   - Key Greeks at entry: delta, gamma, theta, vega
   - P/L at key price levels (current, +/-5%, +/-10%, +/-20%)

6. **Compare alternatives.** Present 2-3 structure options with their metrics side by side. Let the user choose based on their risk preference and premium budget.

## Core Assessment Framework

Assess the strategy choice on four dimensions:

- `View-Structure Alignment`: does the structure's payoff profile match what the user expects to happen?
- `Vol Surface Efficiency`: does the strategy buy cheap vol and sell expensive vol, given current skew and term structure?
- `Premium Budget`: is the cost acceptable given the expected payoff? What is the breakeven as a percentage of the underlying?
- `Risk Definition`: is the max loss defined and acceptable? Does the user understand the tail risk of any naked legs?

## Output tables

### Strategy Comparison
| Strategy | Premium | Breakeven(s) | Max Profit | Max Loss | Delta | Theta/Day | Vega |
|----------|---------|-------------|------------|----------|-------|-----------|------|
| Option A | ... | ... | ... | ... | ... | ... | ... |
| Option B | ... | ... | ... | ... | ... | ... | ... |
| Option C | ... | ... | ... | ... | ... | ... | ... |

### Recommended Structure
| Parameter | Value |
|-----------|-------|
| Strategy | ... |
| Legs | ... (strike, expiry, buy/sell, quantity for each) |
| Net Premium | ... (debit/credit) |
| Breakeven(s) | ... |
| Max Profit | ... at ... |
| Max Loss | ... |
| Key Greeks | Delta ..., Gamma ..., Theta ..., Vega ... |
| Vol Surface Note | ... (e.g., "skew favors put spread over outright put") |

## Evidence that would invalidate this analysis

- the user's view changes (direction, magnitude, timing)
- vol surface shifts materially (ATM level, skew, term structure) changing the relative attractiveness of structures
- liquidity deteriorates in the chosen strikes/expiries, widening bid-ask beyond acceptable levels
- a new catalyst or event changes the timing assumption
- correlation between the underlying and vol changes (e.g., if selling puts on a name whose vol spikes with price drops, the P/L is worse than the static analysis suggests)

## Output structure

Prefer this output order:

1. `View Summary`
2. `Vol Surface Context`
3. `Strategy Selection Rationale`
4. `Strategy Comparison` (table)
5. `Recommended Structure` (table)
6. `P/L Scenarios`
7. `Key Risks`
8. `Next Skill`

Always include:

- the view-to-structure mapping rationale
- how the vol surface influenced the choice
- breakevens and max loss clearly stated
- key Greeks at entry
- whether the next step is `position-sizing`, `greeks-pnl-management`, or `execution-plan-check`

## Best practices

- options are building blocks (LEGOs); combine them to match any payoff profile rather than forcing a view into a standard structure
- always check the vol surface before choosing a structure; buying outright options when vol is expensive wastes premium
- steep skew makes put spreads more efficient than outright puts and call spreads less efficient than outright calls
- calendar spreads only work when the term structure is steep enough to provide an edge; check before entering
- for event trades, compare the implied move (from ATM straddle pricing) to your expected move; if the market already prices a large move, selling into it may be better
- ratio spreads can be free or credit but create naked short risk; always know where the risk begins
- the max profit of a butterfly occurs at a single point; in practice, you need to be approximately right, not precisely right

## Usage examples

- "Use `options-strategy-construction` to choose a structure for my bearish view on XYZ. I think it drops 10-15% over 2 months. Vol is at the 70th percentile."
- "Use `options-strategy-construction` to build an iron condor on SPX. I think we stay range-bound for the next 4 weeks and vol is overpriced."
- "Use `options-strategy-construction` to compare a long straddle vs a long strangle for an earnings play where I expect a big move but have no directional view."
- "Use `options-strategy-construction` to design a calendar spread on AAPL. Front-month vol is elevated from earnings and I want to capture the vol crush."
