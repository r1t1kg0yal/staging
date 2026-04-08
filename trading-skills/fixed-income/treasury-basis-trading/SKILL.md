---
name: treasury-basis-trading
description: Analyze Treasury futures basis trades by decomposing the basis into carry and delivery option value, identifying the cheapest-to-deliver, computing implied repo rates, and assessing whether the basis is rich or cheap for trading. Use when evaluating basis trades, CTD dynamics, squeeze risk, or basis as synthetic volatility.
---

# Treasury Basis Trading

Use this skill when the task is to analyze Treasury futures basis positions -- whether to evaluate a long or short basis trade, assess CTD dynamics, compute implied repo, or understand the basis as a synthetic volatility instrument. This is the specialized skill for cash-futures basis mechanics in US Treasuries and similar government bond futures.

This skill will not:

- substitute basis analysis for a broader rates view (use `fi-relative-value` or `curve-trading` for that)
- price delivery options with a formal model (it provides the analytical framework; the user supplies or retrieves pricing data)
- guarantee that a cheap basis converges before delivery
- ignore squeeze risk because the basis looks attractive on paper

## Role

Act like a basis trader on a rates prop desk. You think in terms of carry, BNOC, implied repo, and delivery option value. You respect the mechanical relationships that govern basis pricing and know that the most attractive-looking short basis trade is often the one with the greatest squeeze risk.

## When to use it

Use it when the task requires:

- decomposing the basis into carry and BNOC for a specific Treasury futures contract
- identifying the CTD and assessing CTD stability (how close is the next cheapest bond to switching)
- computing implied repo rate and comparing it to market repo to assess richness or cheapness
- understanding the delivery options (quality/switch, end-of-month, timing) and their current value
- evaluating whether to go long basis (buy cash, sell futures) or short basis (sell cash, buy futures)
- assessing squeeze risk when OI is high relative to deliverable supply
- using basis as a synthetic options position (long basis = long vol, short basis = short vol)
- feeding a basis view into `trade-expression`, `position-sizing`, or `fi-relative-value`

## Inputs

This skill operates on:

- the specific futures contract (e.g., TYH6, USM6, FVZ5)
- the deliverable basket and current CTD bond
- current basis levels (gross basis, net basis/BNOC, implied repo)
- whether the user has a directional rates view or is purely trading basis RV
- the intended holding period (to delivery, or shorter)

Additional context that strengthens the analysis:

- term repo rates for the CTD and nearby bonds
- CTD specialness in repo (if any)
- open interest relative to deliverable supply
- recent basis history and trend
- output from `vol-framework` if the user is treating basis as a vol position
- output from `macro-event-analysis` for upcoming supply or policy events

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- bond futures price and fair value for the contract
- delivery basket: all deliverable bonds with conversion factors, yields, durations
- CTD identification: the bond with the highest implied repo rate (or equivalently, lowest BNOC)
- CTD cash bond price (clean and dirty), yield, duration, DV01
- gross basis (cash price minus CF times futures price) for CTD and nearby bonds
- carry (coupon accrual minus financing cost) over the delivery period
- net basis / BNOC (gross basis minus carry) for CTD and nearby bonds
- implied repo rate for CTD and nearby bonds
- prevailing term repo rate and GC repo rate for comparison
- open interest and deliverable float for squeeze assessment
- historical net basis and implied repo (3M, 6M minimum) for percentile context

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Basis decomposition

The basis identity is exact and exhaustive:

**Basis = Carry + BNOC**

- Basis = cash price minus (conversion factor times futures price)
- Carry = coupon income minus financing cost over the delivery period. Deterministic and lockable via term repo.
- BNOC (basis net of carry) = the market price of the short's delivery options. Stochastic.

If carry is locked via term repo, all basis uncertainty resides in BNOC. This is the foundation of every basis trade.

## Analysis process

1. **Identify the CTD.** The CTD is the bond with the highest implied repo rate. This is equivalent to the bond with the lowest BNOC. Note the conversion factor and delivery dates.

2. **Assess CTD stability.** How close are the next-cheapest bonds to switching? The CTD selection depends on two orthogonal forces:
   - Duration rule (yield level): yields above the contract's reference yield favor high-duration CTDs; yields below favor low-duration CTDs. Near the reference yield, multiple bonds compete and the switch option is most valuable.
   - Yield rule (spread): among similar-duration bonds, the highest-yielding bond is CTD. Spread changes can trigger switches without level changes.
   - If multiple bonds are within a few ticks of CTD status, the switch option is valuable and BNOC should be materially positive.

3. **Compute basis metrics.** For the CTD and the 2-3 nearest competitors:
   - Gross basis in ticks
   - Carry in ticks (accounting for any intervening coupon)
   - Net basis (BNOC) in ticks
   - Implied repo rate (the financing rate that makes basis equal to zero)

4. **Compare implied repo to market repo.** This is the key richness/cheapness signal:
   - IRR > term repo: BNOC is below theoretical option value, basis is cheap, futures are rich. Favors buying basis (long cash, short futures).
   - IRR < term repo: BNOC is above theoretical option value, basis is rich, futures are cheap. Favors selling basis (short cash, long futures).
   - IRR approximately equal to term repo: basis is fairly priced.

5. **Assess the delivery options.**
   - Quality (switch) option: depends on proximity to crossover yield, yield vol, and the spread dampener effect (systematic curve behavior that moves the effective crossover yield). When spread-yield correlation is high, the switch option is suppressed ("gamma death").
   - End-of-month option: after the last trading day, invoice price is locked but the short chooses the delivery bond. Selection metric changes from duration to BPV (absolute dollar sensitivity). High-coupon bonds can become CTD post-expiry, reversing normal ordering.
   - Timing option: choice of delivery day within the month. Positive carry favors late delivery; negative carry (inverted curve) favors early delivery. Wild card component exists between settlement price fixing and delivery declaration deadline.

6. **Evaluate squeeze risk.** Check open interest relative to deliverable float of the CTD:
   - If OI approaches or exceeds deliverable supply, squeeze risk is real
   - Pre-squeeze: CTD goes special in repo, borrowing demand exceeds supply, repo rate spirals toward zero or negative
   - Squeeze signs: BNOC going negative (pricing delivery failure probability, not free money), calendar spread dislocation
   - The paradox: the most attractive short basis trade (highest carry, cheapest-looking) attracts the most positioning and creates the scarcity it seeks to exploit

7. **Frame as synthetic options position.** The basis at expiry maps to standard option payoffs:
   - Low-duration CTD: net basis behaves like a call on yields (profits as yields rise past switchover)
   - High-duration CTD: net basis behaves like a put on yields (profits as yields fall past switchover)
   - Medium-duration CTD: net basis behaves like a straddle (profits from large moves in either direction)
   - Long basis = long volatility; short basis = short volatility. Every basis trade is a vol position.

8. **Historical context.** Compare current net basis and implied repo to their own 3M, 6M, and 1Y distributions. A net basis at extreme percentiles may indicate a trading opportunity, but check whether structural factors explain the dislocation.

## Core Assessment Framework

Assess the basis trade on four anchors:

- `Basis Level`: where is the net basis relative to its historical distribution. A net basis in the top or bottom decile is a stronger signal than one near the median.
- `IRR vs Repo`: the implied repo rate relative to the market repo rate. This is the primary richness/cheapness metric. State the spread in basis points.
- `CTD Stability`: how likely is a CTD switch. A stable CTD means BNOC will be small and the trade is primarily about carry. An unstable CTD means option value is high and the trade has more convexity.
- `Squeeze Risk`: the ratio of open interest to deliverable supply. High OI/supply ratio with CTD on special is a warning sign regardless of how attractive the basis metrics look.

Use the anchors to classify:

- `attractive basis trade`: IRR vs repo spread is at historically wide levels, CTD is stable enough to limit option uncertainty, squeeze risk is low, and carry profile supports the holding period
- `interesting but requires caution`: metrics look favorable but one or more anchors flash warning (e.g., attractive IRR but CTD is unstable, or basis is cheap but squeeze risk is elevated)
- `avoid or wait`: squeeze risk is high, CTD is deeply unstable with binary outcomes, or the IRR/repo spread does not compensate for the risks involved

## Output tables

### Basis Decomposition
| Bond | CF | Gross Basis (ticks) | Carry (ticks) | BNOC (ticks) | Implied Repo (%) |
|------|-----|---------------------|---------------|--------------|-------------------|
| CTD: ... | ... | ... | ... | ... | ... |
| 2nd: ... | ... | ... | ... | ... | ... |
| 3rd: ... | ... | ... | ... | ... | ... |

### Richness/Cheapness
| Metric | Value |
|--------|-------|
| CTD Implied Repo | ...% |
| Term Repo Rate | ...% |
| IRR - Repo Spread | ... bp |
| Net Basis Percentile (vs 1Y) | ...th |
| Assessment | Rich / Fair / Cheap |

### Delivery Option Assessment
| Option | Value Signal | Key Driver |
|--------|-------------|------------|
| Quality (switch) | High / Moderate / Low | Proximity to crossover, spread dampener |
| End-of-month | High / Moderate / Low | BPV ranking vs duration ranking |
| Timing | Deliver early / late | Curve shape (positive / inverted) |

### Squeeze Risk
| Metric | Value |
|--------|-------|
| Open Interest | ... contracts |
| CTD Deliverable Float | ... bonds |
| OI / Float Ratio | ... |
| CTD Repo Rate | ...% (special / GC) |
| Risk Level | Low / Elevated / High |

## Evidence that would invalidate this analysis

- a CTD switch occurs, changing the option payoff structure of the basis
- the spread-yield correlation regime changes, either killing or restoring the switch option
- a repo market dislocation (year-end, quarter-end, regulatory change) disrupts the implied repo comparison
- open interest changes materially (new large shorts enter or exit)
- an upcoming auction adds new bonds to the deliverable basket, changing CTD dynamics
- the yield curve inverts or disinverts, changing the carry and timing option profile

## Output structure

Prefer this output order:

1. `Basis Trade Summary`
2. `Contract And CTD Identification`
3. `Basis Decomposition` (table)
4. `Richness/Cheapness Assessment`
5. `Delivery Option Assessment` (table)
6. `Squeeze Risk Assessment` (table)
7. `Synthetic Options Framing`
8. `Historical Context`
9. `Trade Recommendation`
10. `Next Skill`

Always include:

- the CTD bond and its implied repo rate
- the IRR vs repo spread as the primary rich/cheap signal
- CTD stability assessment
- squeeze risk assessment
- whether the basis position is long or short vol and what that implies
- whether the idea should move to `position-sizing`, `trade-expression`, or needs more context from `repo-funding-analysis`

## Best practices

- never ignore squeeze risk because the basis metrics look attractive; the most attractive short basis is the most squeezable
- always check CTD stability before sizing; a CTD switch changes the option payoff structure mid-trade
- remember that BNOC rankings can diverge from IRR rankings because BNOC ignores price levels; use IRR for richness/cheapness
- carry that appears on screen may differ from realized carry due to the repo/reverse repo spread (a hidden friction)
- cover the tail (the discrete hedge ratio jump from CF-weighted to 1:1 at futures expiry) as close to expiry as possible
- a negative net basis is not free money; it prices delivery failure probability
- calendar spread mispricing equals OAB with opposite sign

## Usage examples

- "Use `treasury-basis-trading` to analyze the TY basis. I think the 10Y futures are cheap relative to cash and want to evaluate a long basis trade."
- "Use `treasury-basis-trading` to assess squeeze risk in the US (bond) contract. OI looks high relative to deliverable supply."
- "Use `treasury-basis-trading` to evaluate the CTD switch dynamics for FV. Yields are near the crossover and I want to understand the option value."
- "Use `treasury-basis-trading` to frame my short basis position as a vol trade. I want to understand the payoff profile at delivery."
