---
name: pre-event-risk-board
description: Orchestrate a pre-event macro risk board by mapping what is priced in, which positions are exposed, how the surprise distribution could propagate across the book, and whether the right action is to hold, reduce, hedge, restructure, or flatten. Use before major macro or earnings catalysts.
---

# Pre Event Risk Board

Use this workflow skill when the task is to decide how the book should go into a major event window.

This is the event-risk meeting, not a generic event preview.

This workflow will not:

- predict the exact direction of the event outcome
- assume all event risk should be avoided
- replace single-position management on clearly broken trades
- treat optionality as free protection

## Role

Act like a PM chairing the event-risk board ahead of a major catalyst. Your job is to show what is priced in, which positions are truly exposed, how the surprise could transmit across the book, and whether the book should hold, reduce, hedge, restructure, or flatten.

## When to use it

Use it when the task requires:

- deciding how the book should go into CPI, payrolls, FOMC, ECB, BOJ, GDP, earnings clusters, or other major catalysts
- reviewing which positions are most exposed to the same event chain
- deciding whether to hold through, cut size, buy optionality, or change structure
- understanding how a single event could propagate across multiple sleeves in the book

## Inputs

This workflow operates on:

- the book snapshot or risk sleeve under review
- the event or event window
- any explicit hold-through rules or event-risk constraints
- known gross, net, or carry-bleed context
- whether the objective is capital defense, selective hold-through, or active event trading

Additional context that strengthens the workflow:

- what the market is believed to be pricing
- which positions share exposure to the same surprise vector
- whether the book already owns optionality or convex hedges
- liquidity constraints around the event
- planned post-event scenarios or reaction functions

Use any context already available in the conversation. Each underlying skill retrieves its own data needs from the data harness autonomously.

## Data requirements

Each underlying skill in the routing chain retrieves its own data from the data harness. This workflow only needs enough initial context to determine routing: the event window, the positions under review, and whether the question is about holding, de-risking, or restructuring.

## Workflow routing

Use the smallest useful chain:

1. Run `macro-event-analysis` on the event slate and timing window.
2. Run `consensus-vs-pricing-map` to identify what the market is pricing and where surprise space still exists.
3. Run `risk-management` to identify which positions or sleeves are most exposed to the event.
4. Run `cross-asset-playbook` if the event can transmit through multiple markets.
5. Run `scenario-analysis` to map base, upside, downside, and tail outcomes across the book.
6. Run `position-management` on the most fragile positions that may not justify an event hold.
7. Run `trade-expression` if the right answer may be to change structure rather than only change size.
8. Run `macro-book-sizing` if the right answer may be to reduce, hedge, or stagger size going into the event.

Stop the workflow once the pre-event action board is explicit.

## Decision logic

Classify each exposed position or sleeve as:

- `hold through`: current size and structure are acceptable into the event
- `reduce`: the exposure is directionally fine, but too large for the event distribution
- `hedge or restructure`: the thesis may stay alive, but the current instrument or payoff is wrong for the event
- `flatten`: the setup does not justify carrying the event risk

## Output structure

Prefer this output order:

1. `Event Board Summary`
2. `What Is Priced In`
3. `Book Exposures To The Event`
4. `Scenario Map`
5. `Positions To Hold, Reduce, Hedge, Or Flatten`
6. `Pre-Event Action Sheet`
7. `Post-Event Triggers`
8. `Next Skill Or Action`

Always include:

- the main priced-in base case and the real surprise vectors
- which positions are most exposed to the event chain
- whether the exposure is intentional or accidental
- what should be held, reduced, hedged, restructured, or flattened
- what post-event price or macro signals should trigger the next action

## Updated Event Context

When enough context exists, carry forward a compact block like this:

```markdown
## Event Risk Context

- event_window:
- priced_in_base_case:
- key_surprise_vectors:
- top_event_exposures:
- accidental_exposures:
- hold_through_positions:
- positions_to_reduce:
- positions_to_restructure:
- positions_to_flatten:
- post_event_triggers:
- open_questions:
- next_recommended_skill:
```

Only populate the fields supported by the checks that actually ran.

## Best practices

- do not frame the decision as hold everything or flatten everything
- do not ignore accidental event clustering across different asset classes
- do not buy optionality without checking whether the event premium is already expensive
- do not hold through an event by inertia; make the hold decision explicit

## Usage examples

- "Use `pre-event-risk-board` on my book before CPI and tell me what should be held, cut, or restructured."
- "Use `pre-event-risk-board` ahead of the FOMC on this rates and FX book and show me where the accidental overlap is."
- "Use `pre-event-risk-board` on my event-heavy week and tell me whether I should own less outright and more optionality."
