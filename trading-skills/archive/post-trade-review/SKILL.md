---
name: post-trade-review
description: Guide a disciplined post-trade review across thesis quality, execution, adherence, mistakes, lessons, and pattern detection by reconstructing the original plan and what was priced in, then deciding whether the lesson is trade-specific or part of a recurring pattern.
---

# Post Trade Review

Use this skill after a trade closes or after a meaningful trade sequence to conduct an honest process review and determine whether the lesson is trade-specific or part of a recurring pattern.

The objective is to improve repeatability, not to rewrite history.

This skill will not:

- grade the trade only by PnL
- excuse rule-breaking because the outcome was positive
- turn hindsight into a fake lesson
- force pattern analysis when the sample is still too small
- skip the original plan reconstruction just because the outcome is remembered vividly

## Role

Act like a process-focused trading coach on a macro desk. Reconstruct the plan, reconstruct what was priced in, separate decision quality from outcome, identify where the miss occurred, and finish with concrete process improvements and pattern assessment.

## When to use it

Use it when the task requires:

- reviewing a closed trade end to end
- whether the thesis was sound
- whether execution matched the plan
- whether size and rule adherence were acceptable
- what mistake or strong decision mattered most
- converting one trade outcome into a concrete lesson
- deciding whether a mistake is isolated or part of a recurring pattern
- understanding whether the miss came from the view, the regime read, the structure, the size, or execution discipline

## Inputs

This skill operates on:

- instrument and direction
- original thesis, divergence, or view
- planned entry, stop, target, expression, and size
- actual entry, exit, and size
- whether rules were followed
- what happened around the trade, including catalyst or regime context
- initial lesson or takeaway

Additional context that strengthens the analysis:

- what the market was pricing at entry
- whether the cross-asset picture confirmed or contradicted the thesis
- whether the trade was part of a larger theme in the book
- prior review notes
- whether similar trades exist in the journal
- setup tags, timeframe tags, or catalyst tags
- whether there is reason to suspect this trade reflects a recurring issue

If the original plan is missing, say that clearly and keep the review provisional rather than inventing it.

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- historical price chart covering the trade period
- trade log entry with entry/exit dates and prices
- market context during the trade (regime, events)

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Reconstruct the original plan before judging the outcome.
2. Reconstruct what was priced in at the time of entry to assess whether a real divergence from consensus existed.
3. Separate thesis quality from execution quality.
4. Identify rule adherence or violations.
5. Classify mistakes as analytical, emotional, procedural, sizing, or market-environment related.
6. Determine where the miss primarily occurred: the view itself, the regime read, the trade structure or expression, the size, or execution discipline.
7. Assess whether the issue appears isolated or may be part of a recurring pattern based on available journal history.
8. End with one or two actionable process changes, not a motivational speech.

## Routing

Use the smallest useful chain. Most reviews need only the core analysis above, but escalate when the evidence points to a deeper issue:

- If the original edge was weak or misread, run `trader-thinking` on the original setup to test whether a real divergence from consensus ever existed.
- If the miss may have come from the macro backdrop, run `market-regime-analysis` or `cross-asset-playbook` on the original environment.
- If the trade lived or died around a catalyst, run `macro-event-analysis` on the relevant event window.
- If the review shows a structural flaw in the original setup, run `risk-reward-sanity-check` on the original structure.
- If the review shows the expression choice was suboptimal, run `trade-expression` on what the better structure would have been.
- If the review shows sizing or book-fit problems, run `position-sizing`, `macro-book-sizing`, or `risk-management` on what should have been done.
- If the review exposes a recurring-looking mistake and enough history exists, run `journal-pattern-analyzer`.

Stop the review once the clearest lesson and one concrete process change are established.

## Core Assessment Framework

Assess the closed trade on four anchors before drawing conclusions:

- `Thesis Quality`: whether the original claim was clear, evidence-based, and falsifiable. Example: "I think NVDA breaks out because AI capex is accelerating and the chart is consolidating at highs" is a testable thesis. "I think NVDA goes up" is not.
- `Execution Quality`: whether the actual entry, exit, and size matched the plan. Example: entering at the planned level with planned size is good execution even if the trade lost money. Chasing an entry 2% above the plan is poor execution even if the trade was profitable.
- `Rule Adherence`: whether stops, targets, and process rules were followed. Example: honoring the original stop is adherence. Widening the stop after entry without a new thesis is a violation.
- `Mistake Classification`: classify the primary mistake (if any) as analytical (wrong thesis), emotional (fear or greed drove the decision), procedural (skipped a step in the process), sizing (too large or too small for the setup), or environment-related (the regime changed in a way the plan could not have anticipated).

Use the anchors to classify process quality:

- `process win`: good process was followed regardless of outcome -- the trade may have lost money but the decisions were sound
- `process failure with positive outcome`: rules were broken but the trade was profitable -- this is dangerous because it reinforces bad habits
- `process failure with negative outcome`: rules were broken and the trade lost money -- the clearest signal for a process change
- `process success with negative outcome`: rules were followed, the thesis was reasonable, but the trade lost money -- this is variance, not a mistake

Then classify pattern status:

- `single-trade lesson`: the issue is important, but it belongs to this trade only for now
- `pattern worth tracking`: the issue may recur and should be monitored in future reviews
- `pattern confirmed`: the issue is strong enough to justify immediate journal-level rule changes

## Evidence That Would Invalidate This Analysis

- the original plan was remembered incorrectly
- the market context during the trade was different from what was described
- the trade log data is incomplete

## Output structure

Prefer this output order:

1. `Original Plan And Priced-In Context`
2. `Execution Review`
3. `Rule Adherence`
4. `Main Mistake Or Best Decision`
5. `Where The Miss Occurred`
6. `Process Classification`
7. `Pattern Assessment`
8. `Process Change`
9. `Next Skill Or Action`

Always include:

- original thesis summary and what was priced in at entry
- setup quality assessment
- execution quality assessment
- what was done as planned
- what was not done as planned
- whether the miss was mainly in the view, regime read, structure, size, or discipline
- process classification (process win, process failure with positive outcome, process failure with negative outcome, or process success with negative outcome)
- biggest mistake or best process decision
- whether the issue is isolated or part of a broader pattern
- one concrete lesson to carry forward
- the next process change to test
- whether to escalate to `journal-pattern-analyzer` for batch pattern review or stop here

## Best practices

- do not grade the trade only by PnL
- do not excuse broken process because the outcome happened to be positive
- do not rewrite the original thesis with hindsight
- do not let the review jump straight to pattern claims from one trade
- do not skip reconstructing the original plan
- do not turn the review into a motivational speech
- do not recommend more than one or two process changes at once

## Usage examples

- "Use `post-trade-review` on my NVDA swing long where I sized correctly but moved the stop wider after entry."
- "Use `post-trade-review` for a EURUSD short that hit target, but only after I chased the entry and doubled the original risk."
- "Use `post-trade-review` on this closed rates trade loss and tell me whether the mistake was the view, the timing, or the structure."
- "Use `post-trade-review` on this trade and tell me whether it is just one mistake or part of a repeatable sizing problem."
