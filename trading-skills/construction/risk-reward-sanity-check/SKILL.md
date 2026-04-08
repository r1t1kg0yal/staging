---
name: risk-reward-sanity-check
description: Use when the task requires testing whether a proposed entry, stop, and target structure is coherent, asymmetric enough, and vulnerable to obvious failure modes before the trade is placed.
---

# Risk Reward Sanity Check

Use this skill when a trade idea exists but the structure needs inspection before committing capital.

This skill does not predict whether the trade will work. It checks whether the plan is internally coherent.

This skill will not:

- tell the user a positive ratio makes the trade good
- replace thesis quality with a single numeric multiple
- assume the stop or target is valid just because it is mathematically neat

## Role

Act like a skeptical pre-trade reviewer. Challenge the structure before money is at risk.

## When to use it

Use it when the task requires checking whether:

- the stop and target make sense together
- the proposed asymmetry is real or just cosmetic
- the thesis actually supports the target
- obvious structural issues are hiding behind attractive math

## Inputs

This skill operates on:

- direction
- entry
- stop
- one or more targets
- thesis in one or two sentences
- optional context such as time horizon, catalyst, or nearby event risk

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- current price for the instrument
- ATR or recent range for noise calibration
- nearby support and resistance levels from technical context

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Calculate distance from entry to stop and from entry to target.
2. Express the raw risk-reward ratio.
3. Check for structural issues such as targets inside noise, stops placed at obvious liquidity pools, or targets with no thesis support.
4. Explain what would invalidate the structure even if the ratio looks attractive on paper.
5. Separate "good ratio" from "good trade." They are not the same thing.

## Core Assessment Framework

Assess the structure on four anchors before calling it sound:

- `Ratio Quality`: whether the raw R:R ratio is meaningful or cosmetic. A 3:1 ratio where the target requires a move three times the instrument's normal range is cosmetic. A 2:1 ratio with a target at a clear structural level is more meaningful than a 5:1 ratio reaching into empty space.
- `Target Plausibility`: whether the thesis supports reaching the target. The target must be connected to a structural level, measured move, or catalyst outcome -- not a round number or a wish. If the thesis cannot explain why price should reach the target, the ratio is fiction.
- `Stop Coherence`: whether the stop is at a thesis-invalidation level or an arbitrary loss limit. A stop should mark the price at which the original idea is broken, not a dollar amount the user is willing to lose. A stop placed 2% below entry because "that's my rule" may have no relationship to the structure.
- `Structural Vulnerability`: whether event risk, gap risk, or timing mismatch can break the planned structure before the thesis is tested. A trade with a tight stop into an earnings print has structural vulnerability regardless of the ratio.

Classify as:

- `structurally sound`: the ratio is supported by the thesis, the stop marks invalidation, the target is plausible, and no obvious structural vulnerability exists
- `has fixable issues`: the ratio may be reasonable but the stop, target, or timing needs adjustment before the structure is trustworthy
- `structurally flawed`: the ratio is cosmetic, the target is unsupported, the stop is arbitrary, or structural vulnerability makes the plan unreliable

## Evidence That Would Invalidate This Analysis

- the thesis changes materially after the structure was assessed
- the vol environment shifts enough to invalidate the stop distance (what was a reasonable stop in low vol becomes too tight in high vol, or vice versa)
- a catalyst appears or moves in timing that makes the planned structure unsafe
- support or resistance levels that anchored the target or stop are broken before entry
- the instrument's liquidity profile changes enough to affect stop execution reliability

## Output structure

Prefer this output order:

1. `Setup Summary`
2. `Risk Reward Math`
3. `Structural Review`
4. `Decision Risk`
5. `What Must Be True`

Always include:

- raw risk-reward math
- asymmetry assessment
- the main structural concern
- what would need to be true for the target to be plausible
- any mismatch between thesis, stop, and holding period

## Best practices

- do not tell the user a trade will win because the ratio looks attractive
- do not replace thesis quality with a single numeric multiple
- do not ignore catalyst or event risk that can break the planned structure

## Usage examples

- "Use `risk-reward-sanity-check` on a long entry at 58.20, stop 55.90, target 65.50, thesis: breakout continuation if software leadership holds."
- "Use `risk-reward-sanity-check` for a short at 412.80 with stop 418.10 and two targets at 406.00 and 399.50 ahead of payrolls."
