---
name: macro-book-sizing
description: Size macro trades at the book level by allocating risk budget across ideas, converting exposures into comparable risk units such as DV01, vega, beta-adjusted notional, and dollar vol, and enforcing correlation, carry, and liquidity constraints. Use when the task is about portfolio risk allocation rather than stop-based arithmetic on a single trade.
---

# Macro Book Sizing

Use this skill when the task is to decide how much risk a macro book should allocate to a trade or theme, not just how many units fit a stop.

This is the PM sizing layer. It sits above `position-sizing`.

This skill will not:

- validate whether the underlying idea is actually good
- replace a clean expression or clear invalidation
- claim that one sizing model can make a bad trade safe
- produce fake precision through overly complex covariance math
- assume correlations or liquidity stay stable in stress

## Role

Act like a macro PM allocating scarce risk budget. Your job is to translate conviction into book-level risk, normalize exposures across asset classes, and keep the book inside its true capacity for drawdown, carry bleed, and event risk.

## When to use it

Use it when the task requires:

- deciding how much risk budget a candidate trade deserves
- comparing trades expressed in different risk units such as `DV01`, `vega`, beta-adjusted notional, or FX notional
- checking whether a new trade duplicates an existing correlation cluster
- sizing a starter, add, or full position within a macro book
- controlling gross, net, sleeve-level, and theme-level risk
- limiting aggregate carry bleed from negative-carry structures
- adjusting size for event density, liquidity, or regime fragility

## Inputs

This skill operates on:

- total capital, risk budget, and target drawdown or volatility
- current portfolio positions with approximate size and direction
- the candidate trade or theme being sized
- conviction level and time horizon
- the likely expression and primary risk unit
- any relevant sleeve caps, leverage limits, or mandate constraints

Additional context that strengthens the analysis:

- gross and net exposure by asset class
- correlation clusters or shared macro drivers
- carry profile of both the candidate trade and the book
- upcoming catalysts and event density
- liquidity and gap-risk characteristics of the instrument

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- current portfolio holdings and sizes
- realized and implied volatility estimates where relevant
- correlation or factor overlap data across current and proposed positions
- carry or bleed profile for the candidate expression
- liquidity measures such as average volume, open interest, or market depth
- asset-class risk-unit measures such as `DV01`, `vega`, beta, spread duration, or dollar vol
- upcoming event calendar if the trade will pass through catalysts

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Risk-unit normalization

Convert the candidate and the relevant existing positions into comparable risk units before choosing notional.

| Asset Class | Primary Risk Unit | Secondary Control | Typical Sizing Question |
|-------------|-------------------|-------------------|-------------------------|
| Rates | `DV01` | curve bucket and carry/rolldown | How much rate risk can the book add at this tenor or structure |
| FX | dollar vol or vol-adjusted notional | carry and event risk | How much FX risk fits the sleeve and the current USD regime |
| Equities / Indices | beta-adjusted notional or dollar vol | sector and factor overlap | How much equity risk is really being added after beta and theme overlap |
| Options / Vol | premium-at-risk and `vega` | theta bleed and event calendar | How much optionality can the book pay for or short safely |
| Credit | spread `DV01` or spread duration | default and liquidity tail risk | How much spread risk fits the book after correlation clustering |
| Commodities | dollar vol or curve-adjusted notional | carry and inventory/event risk | How much commodity risk fits after curve shape and event risk |

## Analysis process

1. Reconstruct the current risk budget. How much risk is already deployed, how much is unallocated, and where the largest clusters already sit.
2. Identify the candidate trade's primary risk unit and convert it into the same framework used for the rest of the relevant sleeve.
3. Group the candidate with any overlapping positions by theme, factor, and macro driver. Treat correlated trades as one risk event unless there is strong evidence otherwise.
4. Adjust the raw sizing range for carry profile:
   - positive carry or carry-neutral trades can consume more time budget
   - negative-carry trades consume time budget and should face tighter size discipline
5. Adjust for catalyst density and regime fragility. Event-heavy or fragile regimes justify smaller starter size and slower scaling.
6. Adjust for liquidity and gap risk. A thin or gap-prone instrument deserves smaller size than a liquid future with the same modeled risk.
7. Translate the result into a sizing plan:
   - starter size
   - add level or scaling condition
   - max size
   - hard reasons not to scale further

## Conviction tiers

Use conviction tiers to map idea quality into risk budget, but only after correlation and portfolio fit are checked.

| Conviction Tier | Typical Book Treatment |
|-----------------|------------------------|
| High | eligible for full planned risk, but still capped by cluster, carry, and event constraints |
| Medium | usually partial size unless confirmation improves or the book has unusually spare capacity |
| Low | starter only, optionality only, or no trade |

## Core Assessment Framework

Assess the sizing decision on six anchors:

- `Risk Budget Availability`: whether the book actually has unused capacity for this kind of risk.
- `Risk-Unit Fit`: whether the trade is sized in the right unit for its asset class rather than in raw notional alone.
- `Correlation Cluster Load`: whether the candidate meaningfully increases an existing cluster rather than adding independent exposure.
- `Carry Bleed Tolerance`: whether the book can afford the time decay or financing cost if the trade takes longer than expected.
- `Liquidity And Gap Risk`: whether the market can absorb the planned size, especially around catalysts or stress.
- `Scaling Discipline`: whether there is a clear starter, add, and max-size framework instead of one all-in decision.

Use the anchors to classify:

- `full risk justified`: the idea fits the book, risk unit, carry profile, and liquidity constraints well enough for a full planned size
- `starter only`: the idea is interesting, but one or more constraints argue for partial size and proof before scaling
- `do not add`: the book lacks the right capacity, the cluster is already full, the bleed is too expensive, or liquidity is too weak

## Output tables

### Book Risk Snapshot
| Bucket | Current | Limit | Headroom | Comment |
|--------|---------|-------|----------|---------|
| Total risk budget | ... | ... | ... | ... |
| Relevant sleeve | ... | ... | ... | ... |
| Correlation cluster | ... | ... | ... | ... |
| Carry bleed | ... | ... | ... | ... |

### Proposed Sizing Plan
| Item | Value |
|------|-------|
| Primary risk unit | ... |
| Starter size | ... |
| Add condition | ... |
| Max size | ... |
| Main cluster impact | ... |
| Carry impact | ... |
| Liquidity constraint | ... |

## Output structure

Prefer this output order:

1. `Sizing Summary`
2. `Book Risk Snapshot`
3. `Risk-Unit Normalization`
4. `Correlation And Cluster Impact`
5. `Carry And Liquidity Constraints`
6. `Proposed Sizing Plan`
7. `What Would Justify Scaling`
8. `Next Skill`

Always include:

- the primary risk unit used
- the relevant remaining risk budget or why none is truly available
- whether the trade is additive or duplicative relative to the existing book
- the expected carry or bleed impact
- a starter size, add condition, and max-size framework
- whether the next step is `execution-plan-check`, `pre-trade-check`, `risk-management`, or no additional sizing step

## Best practices

- do not size cross-asset trades in raw notional when the true risk units differ
- do not let conviction override cluster caps or gross limits
- do not ignore carry bleed; negative carry is a real consumer of risk budget
- do not scale a position just because it is working if the cluster is already full
- do not assume liquid conditions survive a catalyst or stress regime
- do not use the same sizing template for outrights, spreads, and long optionality

## Usage examples

- "Use `macro-book-sizing` to decide how much `DV01` my book can add through a 2s10s steepener."
- "Use `macro-book-sizing` to compare a long gold trade, short EURUSD trade, and long rates expression for the next unit of risk budget."
- "Use `macro-book-sizing` on this long-vol idea. I need to know whether the book can afford the theta bleed into CPI and the FOMC."
