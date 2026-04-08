---
name: dislocation-ranker
description: Rank candidate macro trade ideas across asset classes using a common rubric based on consensus gap, carry or bleed, catalyst quality, cross-asset confirmation, expression quality, and portfolio fit. Use when several ideas compete for limited risk budget.
---

# Dislocation Ranker

Use this skill when there are several candidate trades and the task is to decide which deserve scarce risk budget, not just which sound most interesting.

This skill is meant to compare ideas across asset classes on one decision grid.

This skill will not:

- replace deep analysis of the winning idea after ranking
- turn soft judgment into false precision through over-detailed scoring
- assume the best narrative should automatically rank first
- pretend that every candidate must survive the ranking process

## Role

Act like a PM allocating attention and risk budget across competing ideas. Your job is to normalize different trade candidates onto one common rubric and identify which dislocations are most worth advancing now.

## When to use it

Use it when the task requires:

- comparing several macro trade ideas across rates, FX, vol, commodities, or equities
- deciding which ideas deserve the next round of work or risk budget
- reducing a large candidate slate into one to three highest-priority trades
- forcing discipline when multiple ideas all look superficially attractive
- deciding what should be advanced, monitored, or dropped

## Inputs

This skill operates on:

- a list of candidate trades or market dislocations
- the intended holding period
- whether the book prefers directional, relative value, or mixed setups
- the current book context if portfolio fit matters
- any explicit risk-budget or concentration constraints

Additional context that strengthens the analysis:

- output from `macro-idea-generation`
- output from `consensus-vs-pricing-map`
- preliminary carry, vol, or expression notes
- current regime or event backdrop

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- market-implied pricing relevant to each candidate
- historical percentile context for the relevant dislocation metric
- carry or bleed profile for the likely expression
- catalyst calendar and event timing
- cross-asset confirmation or contradiction
- current portfolio exposures if book fit matters

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Normalize each candidate into the same template: market, view, why it exists, likely catalyst, likely expression, and key risk.
2. Rank each candidate on a small set of coarse decision axes. Use broad buckets or simple 1-5 scores only if they help clarify the ordering.
3. Penalize ideas that have weak surprise space, poor carry, no catalyst, weak expression quality, or poor portfolio fit.
4. Reward ideas where the dislocation is real, the consensus is fragile, the expression is clean, and the timing window is favorable.
5. Produce a short ranking with clear reasons for the ordering.
6. End with which ideas advance now, which remain on watch, and which should be dropped.

## Core Assessment Framework

Assess each candidate on six anchors:

- `Consensus Gap`: how clear and meaningful is the divergence between market pricing and the proposed view.
- `Carry Or Bleed`: what is earned or paid while waiting for the thesis to work.
- `Catalyst Quality`: how credible and timely is the forcing function that could close the gap.
- `Cross-Asset Confirmation`: whether related markets support the dislocation or warn against it.
- `Expression Quality`: whether there is a clean, asymmetric, and liquid way to express the idea.
- `Portfolio Fit`: whether the trade adds differentiated exposure or just duplicates risk already in the book.

Use the anchors to classify:

- `advance now`: strongest combination of edge, timing, structure, and book fit
- `monitor`: interesting idea, but one or two anchors are not ready
- `drop`: too weak relative to competing ideas for the current risk budget

## Output tables

### Ranking Grid
| Candidate | Consensus Gap | Carry / Bleed | Catalyst | Cross-Asset | Expression | Book Fit | Verdict |
|-----------|---------------|---------------|----------|-------------|------------|----------|---------|
| Idea A | ... | ... | ... | ... | ... | ... | Advance / Monitor / Drop |
| Idea B | ... | ... | ... | ... | ... | ... | ... |
| Idea C | ... | ... | ... | ... | ... | ... | ... |

## Output structure

Prefer this output order:

1. `Ranking Context`
2. `Ranking Grid`
3. `Top Ideas`
4. `Why They Rank Higher`
5. `Why The Others Fall Behind`
6. `Next Skill`

Always include:

- the ranking rubric used
- the strongest and weakest axis for each advancing idea
- whether an idea is worth advancing now, monitoring, or dropping
- which idea should receive the next unit of attention or risk budget
- whether the next step is `trade-expression`, `macro-book-sizing`, `pre-trade-check`, or an asset-class specialist skill

## Best practices

- do not let raw conviction outrank better-structured opportunities
- do not use decimal scoring or fake precision when coarse ranking is enough
- do not keep two ideas that express the same underlying macro risk unless the distinction is explicit
- do not ignore expression quality; a strong view with no clean trade should rank lower
- do not be afraid to rank all ideas as weak if the opportunity set is genuinely poor

## Usage examples

- "Use `dislocation-ranker` on these four macro ideas and tell me which one deserves risk budget first."
- "Use `dislocation-ranker` to compare a 2s10s steepener, long gold, short EURUSD, and long vol into CPI."
- "Use `dislocation-ranker` on my candidate rates and FX trades and tell me which ideas to advance now versus monitor."
