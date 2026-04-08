---
name: weekly-theme-review
description: Orchestrate a weekly macro PM review by reassessing the book's major themes, how markets are pricing them, whether conviction still deserves current risk budget, and which new dislocations are worth promoting into active work. Use when the task is to reset the book's theme map for the coming week.
---

# Weekly Theme Review

Use this workflow skill when the task is to review the book at the theme level rather than at the single-position level.

This is the weekly underwriting meeting for the book.

This workflow will not:

- replace daily risk management on urgent positions
- assume a profitable theme still deserves the same risk budget
- keep old themes alive just because they were once high conviction
- force thematic balance when the opportunity set is genuinely narrow

## Role

Act like a macro PM reviewing the book for the coming week. Your job is to reassess the major themes, ask what is now priced in, judge which themes deserve more or less risk, and decide which fresh dislocations belong in the next week's active slate.

## When to use it

Use it when the task requires:

- re-underwriting the book's major themes for the next week or two
- deciding whether conviction still matches current risk budget
- identifying crowded or stale themes that should be reduced
- promoting new dislocations into the active work queue
- resetting sleeve allocations after a material change in regime or event calendar

## Inputs

This workflow operates on:

- the current book grouped by theme, sleeve, or macro driver
- recent PnL, drawdown, or performance by theme if available
- the next week's catalyst calendar
- any active regime view or regime concern
- whether the review is risk-first, opportunity-first, or both

Additional context that strengthens the workflow:

- current consensus and pricing around the main themes
- known crowding or positioning extremes
- carry profile of the current book
- themes that have outgrown their intended weight
- new candidate trades competing for next week's risk budget

Use any context already available in the conversation. Each underlying skill retrieves its own data needs from the data harness autonomously.

## Data requirements

Each underlying skill in the routing chain retrieves its own data from the data harness. This workflow only needs enough initial context to determine routing: the main themes in the book, the next week's event window, and any candidate ideas competing for risk budget.

## Workflow routing

Use the smallest useful chain:

1. Run `consensus-vs-pricing-map` on the main themes or drivers in the book.
2. Run `cross-asset-playbook` to check whether the book's core narratives are still being confirmed across markets.
3. Run `market-regime-analysis` if the current regime may be shifting.
4. Run `risk-management` to identify which themes or clusters already dominate the book.
5. Run `macro-idea-generation` to refresh the opportunity set.
6. Run `dislocation-ranker` if several candidate ideas are competing for limited risk budget.
7. Run `scenario-analysis` when next week's calendar or regime risk could force large reallocations.
8. Run `macro-book-sizing` on themes or trades that deserve capital reallocation.

Stop the workflow once the next week's theme map and risk-budget changes are clear.

## Decision logic

Classify each major theme as:

- `press`: conviction, pricing, and book fit still justify or increase risk budget
- `maintain`: the theme still belongs in the book at roughly current size
- `de-risk`: the theme is more crowded, more priced in, or less well supported than before
- `retire`: the theme is stale, broken, or no longer a good use of capital
- `research`: interesting, but not yet ready for risk budget

## Output structure

Prefer this output order:

1. `Weekly Theme Map`
2. `What Changed Since Last Review`
3. `Themes To Press`
4. `Themes To De-Risk Or Retire`
5. `New Themes Worth Advancing`
6. `Risk Budget Reallocations`
7. `Key Catalysts For The Week`
8. `Next Skill Or Action`

Always include:

- the main themes currently driving the book
- what is newly priced in or newly fragile
- which themes deserve more risk, less risk, or no risk
- the one to three freshest dislocations worth promoting into active work
- the catalyst calendar that could force re-underwriting during the week

## Updated Weekly Context

When enough context exists, carry forward a compact block like this:

```markdown
## Weekly Theme Context

- review_window:
- core_themes:
- themes_to_press:
- themes_to_maintain:
- themes_to_derisk:
- themes_to_retire:
- candidate_new_themes:
- risk_budget_changes:
- key_weekly_catalysts:
- carry_profile:
- open_questions:
- next_recommended_skill:
```

Only populate the fields supported by the checks that actually ran.

## Best practices

- do not let last week's PnL decide next week's conviction by itself
- do not keep legacy themes alive without a fresh priced-in review
- do not ignore how much of the book is really one macro driver in multiple wrappers
- do not promote a new theme into the book without saying what gets crowded out

## Usage examples

- "Use `weekly-theme-review` on my macro book and tell me which themes deserve more risk next week."
- "Use `weekly-theme-review` after payrolls and tell me which themes are now stale versus freshly interesting."
- "Use `weekly-theme-review` on my cross-asset book with a focus on re-allocating risk budget ahead of CPI and the FOMC."
