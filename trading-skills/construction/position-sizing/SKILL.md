---
name: position-sizing
description: Use when a narrow trade-level position size is needed from account equity, per-trade risk budget, entry, stop, and trading friction after the structure is already defined.
---

# Position Sizing

Use this skill before entering a trade when a defensible size is needed instead of a gut-feel size.

This skill will not:

- tell the user whether the trade thesis is good
- override liquidity, gap, or event-risk judgment with a formula
- turn an aggressive stop or oversized conviction into a safe trade
- allocate risk across a macro book or normalize exposure across `DV01`, `vega`, beta-adjusted notional, or correlation clusters

## Role

Act like a conservative trade-level risk manager. Survival comes before conviction, and arithmetic comes after the thesis, structure, and book fit are already good enough.

## When to use it

Use it when the task requires determining:

- how many shares, units, or contracts fit the risk budget
- how slippage, fees, or contract multipliers change the math
- whether the planned stop makes the size impractical
- whether the trade is arithmetically small enough before asking whether it is strategically worth taking

Use `macro-book-sizing` instead when the real question is how much portfolio risk, `DV01`, `vega`, beta-adjusted notional, or correlation-cluster capacity should be allocated to the idea.

## Inputs

This skill operates on:

- account size or equity
- max risk as percent or cash amount
- entry price
- stop price
- instrument type if it affects contract value
- contract multiplier if applicable
- optional slippage, commission, or "extra buffer" assumptions

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- current price for the instrument
- account equity or available capital
- volatility data (ATR) if vol-adjusted sizing is requested
- contract specifications if futures

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Compute the per-unit risk from entry to stop.
2. Add friction assumptions if they materially increase realized risk.
3. Compute the maximum position size that stays inside the risk budget.
4. Report the rounded-down size, estimated total risk, and any caveats.
5. Flag cases where the stop is too tight, too wide, or structurally unclear.
6. Escalate to `macro-book-sizing` if the real bottleneck is portfolio fit, risk-unit normalization, or correlated exposure rather than stop-based arithmetic.

## Core Assessment Framework

Assess the sizing on four anchors before calling it defensible:

- `Budget Adherence`: whether the size fits the stated risk budget. A position that consumes more than the intended per-trade risk allocation is oversized regardless of conviction. If the arithmetic risk exceeds the budget, the size must decrease or the stop must move.
- `Stop Distance`: whether the stop is far enough to be meaningful but close enough to be practical. A stop that is too tight generates noise exits. A stop that is too wide forces the size so small that the trade cannot meaningfully contribute to the portfolio.
- `Friction Reality`: whether slippage and commission materially change the math. In liquid large-cap equities, friction is negligible. In options, futures, thin names, or extended-hours trading, friction can represent a significant percentage of the per-unit risk and must be included.
- `Portfolio Context`: whether this size makes sense relative to existing exposure. A position that fits the per-trade risk budget but pushes total portfolio exposure into concentration territory is problematic. Cross-reference with `portfolio-concentration` when relevant.

Classify as:

- `size is defensible`: the position fits the risk budget, the stop is at a thesis-invalidation level, friction is accounted for, and portfolio context is reasonable
- `size needs adjustment`: the arithmetic works but the stop distance, friction, or portfolio overlap creates a problem that sizing alone cannot solve
- `size is problematic`: the position exceeds the risk budget, the stop is structurally unsound, or portfolio context makes this size untenable

## Evidence That Would Invalidate This Analysis

- account size or available capital changes materially
- the stop price moves, invalidating the per-unit risk calculation
- the entry price changes enough to alter the risk-reward structure
- friction assumptions are wrong (wider spreads, higher commissions, or worse slippage than assumed)
- the instrument's liquidity profile differs from what was assumed, affecting execution reliability
- existing portfolio exposure changes in a way that alters the portfolio context assessment

## Output structure

Prefer this output order:

1. `Inputs Used`
2. `Sizing Method`
3. `Sizing Math`
4. `Position Recommendation`
5. `Risk Caveats`

Always include:

- position size
- total dollar risk
- percent of account at risk
- assumptions used
- caveats about slippage, gaps, leverage, or contract multipliers
- whether this arithmetic answer is sufficient on its own or should move next to `macro-book-sizing`

Do not imply the size is "safe" just because it fits the arithmetic.

## Best practices

- do not promise that a mathematically valid size is strategically appropriate
- do not ignore contract multipliers or event risk when they materially change exposure
- do not replace the need for liquidation planning in fast or illiquid markets
- do not use this skill as a substitute for whole-book risk budgeting

## Usage examples

- "Use `position-sizing` for a $150,000 account risking 0.4% on a long entry at 84.20 with a stop at 81.90 and 0.10 slippage."
- "Use `position-sizing` on ES futures with account size $80,000, max loss $500, long entry 5210.25, and stop 5199.75."
