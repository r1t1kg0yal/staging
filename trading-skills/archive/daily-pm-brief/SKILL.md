---
name: daily-pm-brief
description: Orchestrate a daily macro PM briefing by reviewing what changed in pricing, what the book owns, what matters today, and which positions or new dislocations deserve action. Use when the task is to start the trading day with a disciplined book-level action sheet.
---

# Daily PM Brief

Use this workflow skill when the task is to begin the trading day with one coherent answer to the question, "What matters for my book today?"

This is the daily operating cadence, not a one-off trade review.

This workflow will not:

- turn every overnight move into a required trade
- replace deeper specialist analysis when a specific market needs real work
- confuse a market recap with a PM action plan
- force new risk just because fresh dislocations appeared

## Role

Act like a macro PM chairing the morning risk and opportunity meeting. Your job is to identify what changed in pricing, which parts of the book are now at risk, where the catalyst calendar matters, and whether any new dislocation deserves attention today.

## When to use it

Use it when the task requires:

- setting the daily risk and opportunity agenda for a macro book
- deciding which open positions need immediate management attention
- identifying the events, prices, or cross-asset shifts that matter today
- distinguishing important overnight changes from noise
- deciding whether today is about defense, patience, or selective deployment of new risk

## Inputs

This workflow operates on:

- the current book snapshot
- the markets or themes that drive the book
- the relevant session and region
- today's event calendar or catalyst concerns
- whether the focus is risk defense, opportunity scan, or both

Additional context that strengthens the workflow:

- overnight price action and key level breaks
- current gross, net, and drawdown context
- positions with near-term catalysts or weak thesis integrity
- dry powder or spare risk budget
- any planned adds, trims, or event holds

Use any context already available in the conversation. Each underlying skill retrieves its own data needs from the data harness autonomously.

## Data requirements

Each underlying skill in the routing chain retrieves its own data from the data harness. This workflow only needs enough initial context to determine routing: the book snapshot, the markets that matter most today, and the event window under review.

## Workflow routing

Use the smallest useful chain:

1. Run `consensus-vs-pricing-map` on the markets that matter most to the book.
2. Run `market-regime-analysis` to classify the current tape and whether tactics should be aggressive, defensive, or selective.
3. Run `cross-asset-playbook` if leadership or transmission changed overnight.
4. Run `macro-event-analysis` on the day's event slate if the calendar matters.
5. Run `risk-management` if the book-level risk picture is unclear or newly stressed.
6. Run `position-management` on the fragile positions that are most exposed today.
7. If spare risk budget exists and new dislocations are real, run `macro-idea-generation` or `dislocation-ranker`.

Stop the workflow once the book has a clear daily action sheet.

## Decision logic

Classify the daily posture as:

- `stay the course`: no major change in pricing or book risk; manage normally
- `tighten and monitor`: key risks increased, but immediate de-risking is not yet mandatory
- `reduce risk now`: the tape, event slate, or book fragility warrants fast de-risking
- `selectively deploy`: the book is stable and one or more new opportunities deserve attention

## Output structure

Prefer this output order:

1. `Daily Posture`
2. `What Changed`
3. `What The Book Owns Into Today`
4. `Key Risks And Events`
5. `Positions Requiring Attention`
6. `New Dislocations Worth Watching`
7. `Action Sheet`
8. `Next Skill Or Action`

Always include:

- the most important change in pricing or regime
- the biggest risk to the current book today
- the events or levels that can force action
- whether today is mainly about defense, patience, or selective offense
- the one to three actions that matter most

## Updated Daily Context

When enough context exists, carry forward a compact block like this:

```markdown
## Daily PM Context

- session:
- book_posture:
- overnight_changes:
- priced_in_shift:
- top_book_risks:
- key_events_today:
- positions_to_manage:
- dry_powder:
- new_dislocations:
- hard_no_trade_zones:
- open_questions:
- next_recommended_skill:
```

Only populate the fields supported by the checks that actually ran.

## Best practices

- do not let the brief turn into a macro recap with no actions
- do not treat every gap or overnight headline as a meaningful repricing
- do not approve new risk before identifying the positions already demanding attention
- do not bury the event calendar if the book is catalyst-heavy

## Usage examples

- "Use `daily-pm-brief` on my macro book for today's session and tell me what actually matters."
- "Use `daily-pm-brief` after the Asia and Europe sessions. I need to know which positions are fragile into the US open."
- "Use `daily-pm-brief` on my cross-asset book and tell me whether today is a defend-capital day or a deploy-risk day."
