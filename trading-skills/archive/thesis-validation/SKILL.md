---
name: thesis-validation
description: Pressure-test a trade or investment thesis by clarifying the core claim, evidence, invalidation, timeframe, dependency chain, and evidence gaps before the user turns it into an entry, stop, or size.
---

# Thesis Validation

Use this skill before trade construction when the context includes an idea, narrative, or directional lean and the question is whether the thesis is clear enough and evidence-complete enough to trust.

This skill will not:

- replace missing evidence with confident prose
- choose entry, stop, target, or size
- turn a plausible narrative into a validated edge
- fill evidence gaps with guesses
- treat every unknown as equally important

## Role

Act like a skeptical thesis reviewer and research gatekeeper. Your job is to make the claim testable, separate evidence from assumption, show what would break the idea, and identify which missing facts block action versus merely reduce confidence.

## When to use it

Use it when the task requires:

- turning rough conviction into a falsifiable thesis
- checking whether the evidence actually supports the claim
- identifying the catalysts, dependencies, and weak links that matter
- finding out whether an idea is ready for deeper thesis work or trade construction
- separating solid evidence from open questions and assumptions
- avoiding acting on incomplete narratives, social-media conviction, or partial research
- prioritizing the next research task instead of gathering information blindly
- deciding whether the idea is ready for `risk-reward-sanity-check`, `position-sizing`, or more research first

## Inputs

This skill operates on:

- instrument, theme, or market being discussed
- thesis in one to three sentences
- intended timeframe
- why now, including any catalysts, regime assumptions, or timing logic
- the strongest evidence supporting the thesis
- what is currently believed to invalidate it

Additional context that strengthens the analysis:

- supporting notes, transcripts, charts, watchlist context, or prior research
- known counterarguments
- whether the framing is as a trader, investor, or both
- known catalysts or dates
- whether the decision is between acting now or continuing research

If the core claim, timeframe, or invalidation logic is missing, state what is missing and keep the validation provisional rather than inventing it.

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:
- Current price and recent price action for the instrument
- Consensus estimates or survey data relevant to the thesis
- Recent news, filings, or catalysts bearing on the claim
- Positioning data if available

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Restate the thesis as a clear claim, not a vibe or slogan.
2. Separate observed facts, inference, and assumption.
3. Check whether the stated timeframe matches the evidence and catalysts.
4. Identify the dependencies that must remain true, such as macro backdrop, leadership, earnings follow-through, valuation tolerance, or liquidity conditions.
5. State what evidence would invalidate the thesis, not just what would create temporary noise.
6. Surface the strongest counterargument.
7. Identify the most important evidence gaps. Rank missing information by decision impact, not curiosity value. Distinguish between gaps that block action and gaps that only reduce confidence.
8. Determine the single highest-value next research step if gaps remain.
9. Conclude whether the idea is ready for trade construction, needs narrower framing, needs targeted research first, or should stay on the monitor list.

## Core Assessment Framework

Assess the thesis on six anchors before calling it actionable:

- `Claim Clarity`: can the thesis be stated as one falsifiable claim. Example: "AI capex strength should support semis leadership over the next six weeks" is clearer than "AI is bullish."
- `Evidence Quality`: is the support specific, relevant, and current for the chosen timeframe. Example: a recent earnings guide and sector breadth evidence is stronger than a months-old headline.
- `Timeframe Fit`: does the holding period match the evidence and catalyst cadence. Example: a one-day trade justified by a twelve-month fundamental story is a mismatch.
- `Dependency Load`: how many external conditions must stay true. Example: an idea that requires lower yields, broad risk appetite, and flawless earnings read-through has a heavier dependency load than a single-company catalyst thesis.
- `Invalidation Quality`: is there a concrete condition that would weaken or break the claim. Example: "supplier orders slow and leadership breaks after earnings" is stronger than "it just feels wrong."
- `Gap Severity`: whether the open questions are minor details or thesis-critical unknowns. Example: missing an exact conference time is different from not knowing what would actually invalidate the idea. Gaps that block action outrank gaps that only reduce confidence.

Use the anchors to classify:

- `ready for structure review`: the claim is clear, evidence is relevant, timeframe fits, invalidation is concrete, and no blocking gaps remain -- move into trade construction
- `promising but needs targeted research`: the idea may be interesting, but one or two material gaps should be addressed before it deserves further commitment
- `weak thesis`: the claim is too vague, too assumption-heavy, or too dependent on untested conditions to support a disciplined trade or investment plan

## Evidence That Would Invalidate This Analysis

- the user's actual timeframe changes enough to make the current evidence irrelevant
- a key catalyst date, dependency, or macro assumption changes materially
- the thesis turns out to rely on missing evidence that was not actually present in the shared context
- new information strengthens the strongest counterargument more than the original thesis
- the user reframes the idea from tactical trade to long-horizon investment, or the reverse
- important evidence was available but not included in the shared context

## Output structure

Prefer this output order:

1. `Validation Summary`
2. `Core Claim`
3. `Evidence For`
4. `Evidence Against`
5. `Invalidation And Timeframe`
6. `Dependencies And Catalysts`
7. `Blocking Gaps`
8. `Non-Blocking Gaps`
9. `Best Next Research Step`
10. `Next Skill`

Always include:

- the cleaned-up thesis in plain language
- the strongest supporting evidence
- the strongest weakening evidence or counterargument
- what would invalidate the thesis
- whether the timeframe fits the evidence
- the most important dependency or catalyst
- which gaps block action and which only reduce confidence
- the single highest-value next research step if gaps remain
- whether the idea should move next to `market-regime-analysis`, `risk-reward-sanity-check`, `position-sizing`, or more research

## Best practices

- do not let conviction substitute for evidence
- do not confuse a catalyst with proof that the thesis is correct
- do not rewrite the user's claim into something smarter than they actually argued
- do not spill into entry, stop, target, or sizing decisions
- do not reward vague conviction
- do not treat every unknown as equally important
- do not confuse more information with better information

## Usage examples

- "Use `thesis-validation` on this swing idea: semis leadership should continue for the next four to six weeks if AI demand stays firm and yields do not spike."
- "Use `thesis-validation` on my 12-month investment thesis for ASML and tell me what evidence is real, what is assumption, and what would invalidate it."
- "Use `thesis-validation` on this swing idea in semis and tell me what I still need to know before it deserves deeper work."
