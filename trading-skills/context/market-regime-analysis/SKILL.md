---
name: market-regime-analysis
description: Analyze current market context through trend, volatility, breadth, and event backdrop so the user can choose tactics that fit the environment without relying on black-box regime claims.
---

# Market Regime Analysis

Use this skill when you need a disciplined read on market context before selecting tactics, sizing, or holding period.

This skill will not:

- forecast market returns from a label
- assign fake confidence percentages to limited evidence
- replace instrument-specific trade planning or risk limits

## Role

Act like a market structure analyst. Your job is to classify the environment conservatively, explain the evidence, and highlight what would invalidate that view.

## When to use it

Use it when the task requires:

- deciding whether trend-following, mean reversion, or caution is the better default
- understanding whether a market is healthy, fragile, defensive, or in transition
- adapting size and expectations to changing breadth or volatility
- pressure-testing a market read before committing capital

## Inputs

This skill operates on:

- trend observations
- volatility readings
- breadth or participation data
- leadership quality or concentration
- liquidity and event backdrop
- relevant timeframe and market focus

If the available context is insufficient, work with the minimum evidence available instead of forcing a fake label.

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:
- Price data: index levels and returns over multiple timeframes (daily, weekly, monthly)
- Volatility measures: VIX or equivalent implied vol, realized volatility
- Breadth data: advance-decline ratios, new highs vs new lows, sector performance dispersion
- Event calendar: upcoming macro releases and policy decisions

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Assess trend, volatility, breadth, and event backdrop separately.
2. Look for agreement or conflict across those dimensions.
3. Classify the environment conservatively.
4. Explain which tactics fit the environment and which become fragile.
5. State what evidence would change the classification.

## Core Assessment Framework

Score the environment on four anchors before choosing a label:

- `Trend`: higher highs and higher lows on the user's timeframe, or repeated failure at support and resistance. Example: 20-day trend up but 5-day momentum flattening means the trend anchor is positive but weakening.
- `Volatility`: realized range and gap behavior relative to the recent norm. Example: daily ranges expanding from 1.1% to 2.0% means tactics should become more defensive even if price is still trending.
- `Breadth`: participation across sectors, index members, or the user's watchlist. Example: index up while only megacap tech participates counts as narrow breadth, not healthy breadth.
- `Event Backdrop`: whether macro releases, earnings clusters, or policy headlines can invalidate the read quickly. Example: CPI tomorrow and a central-bank speaker today should push the backdrop toward heavy even if tape action is calm.

Use these anchors to classify:

- `healthy trend`: trend positive, volatility contained or normal, breadth broad enough, event backdrop not immediately disruptive
- `fragile trend`: trend positive, but breadth narrow or volatility elevated
- `transition`: anchors conflict meaningfully and no single tactic deserves high conviction
- `defensive`: trend negative or unstable, volatility elevated, breadth weak, or event backdrop heavy enough to shrink decision time

## Evidence That Would Invalidate This Analysis

- the next session or two reverses the trend anchor with a decisive break of the key level the analysis relied on
- breadth expands or collapses enough to contradict the current participation read
- volatility contracts or explodes enough to make the current tactic set inappropriate
- a new macro or earnings event changes the backdrop from manageable to heavy, or the reverse
- the user's timeframe changes materially, because intraday and swing regime reads should not be treated as interchangeable

## Output structure

Prefer this output order:

1. `Regime Summary`
2. `Core Assessment Framework`
3. `Tactical Implications`
4. `Evidence That Would Invalidate This Analysis`
5. `Caveats`

Always include:

- regime classification in plain language
- key evidence used
- what weakens or invalidates the current read
- tactical implications for risk-taking, trade duration, and expectation-setting

Avoid fake certainty or theatrical confidence percentages.

## Best practices

- do not forecast returns from a single regime label
- do not turn limited evidence into precise confidence scores
- do not replace instrument-specific trade planning

## Usage examples

- "Use `market-regime-analysis` from these observations: uptrend intact, breadth narrowing, volatility elevated, CPI tomorrow."
- "Use `market-regime-analysis` on my notes from this week and tell me whether trend-following or mean reversion is the safer default."
