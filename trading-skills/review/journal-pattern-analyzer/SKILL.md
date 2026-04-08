---
name: journal-pattern-analyzer
description: Use when a trade journal or trade log is available and the task requires identifying repeated strengths, mistakes, environment-dependent patterns, and process changes without turning the review into hindsight theater.
---

# Journal Pattern Analyzer

Use this skill when a set of trades, journal notes, or review entries is available and the task requires identifying patterns repeating across them.

This skill will not:

- grade the user only by total PnL
- pretend a small sample proves a durable edge
- replace single-trade post-mortems when the problem is still one specific position

## Role

Act like a process analyst reviewing a journal, not a cheerleader reviewing outcomes. Your job is to identify repeatable strengths, repeatable mistakes, and where the process breaks down under specific conditions.

## When to use it

Use it when the task requires:

- reviewing a batch of trades instead of one trade
- identifying recurring mistakes in entries, exits, sizing, timing, or catalyst handling
- determining whether performance changes by setup, regime, instrument, or time horizon
- converting raw journal notes into one or two high-value process changes

## Inputs

This skill operates on:

- a trade log, journal entries, or a summarized set of closed trades
- the sample window: last 10 trades, last month, last quarter, earnings season, and so on
- what fields exist: setup type, thesis, entry, stop, target, size, result, notes, adherence, catalyst context
- whether the focus should be on behavioral patterns, setup quality, sizing quality, or environment fit

Additional context that strengthens the analysis:

- regime notes
- sector or instrument tags
- whether results are in dollars, percentages, or R multiples
- any pattern already suspected

If the sample is very small, say so clearly and keep the conclusions provisional.

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- trade journal or log data covering the sample period
- market regime data for the periods covered if available for environment-conditional analysis

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Reconstruct the journal sample and what needs to be learned from the data.
2. Group trades by setup, environment, mistake type, instrument, or catalyst context when the data supports it.
3. Separate outcome patterns from process patterns.
4. Identify recurring strengths and recurring mistakes.
5. Check whether mistakes cluster around specific conditions such as open entries, event holds, oversizing, or late exits.
6. Distill the findings into one or two process changes that are specific enough to test.
7. End with what should be kept, stopped, and monitored next.

## Core Assessment Framework

Assess the journal on five anchors before drawing conclusions:

- `Sample Quality`: whether there are enough trades and enough detail to support pattern claims. Example: 20 tagged trades with notes is more informative than 4 trades with only PnL.
- `Process Consistency`: whether a recognizable process was actually followed. Example: repeated pre-trade planning and post-trade notes make the patterns easier to trust.
- `Mistake Recurrence`: whether the same type of error appears multiple times. Example: widening stops after entry in several trades is a stronger signal than one isolated lapse.
- `Environment Fit`: whether results change across regimes, catalysts, timeframes, or instruments. Example: momentum setups may work in healthy trend conditions but degrade around heavy event risk.
- `Actionability`: whether the output can be turned into a specific rule, checklist item, or monitoring metric. Example: "do not enter breakouts in the first 15 minutes" is more actionable than "be more patient."

Use the anchors to classify:

- `useful pattern set`: the journal is detailed enough to support actionable conclusions
- `suggestive but thin`: there may be a pattern, but the sample or tagging quality is too weak for strong claims
- `not analyzable yet`: the notes are too sparse or the sample is too small to draw meaningful process conclusions

## Evidence That Would Invalidate This Analysis

- the sample is incomplete or selectively chosen
- key fields such as setup type, adherence, or notes were missing or mis-tagged
- the results mix different strategies or timeframes that should not have been analyzed together
- later entries show that the apparent pattern was only a short-lived cluster
- the user changes process materially, making the historical pattern less relevant

## Output structure

Prefer this output order:

1. `Pattern Summary`
2. `What Is Working`
3. `What Keeps Going Wrong`
4. `Where The Pattern Appears`
5. `Process Change To Test`
6. `What To Track Next`
7. `Next Skill`

Always include:

- whether the sample is strong enough for conclusions
- the clearest repeated strength
- the clearest repeated mistake
- where the pattern clusters: setup, timeframe, catalyst, instrument, or regime
- one or two process changes to test next
- whether the next step is `post-trade-review`, a revised rule in the journal, or no additional skill yet

## Best practices

- do not confuse outcome streaks with process quality
- do not draw strong conclusions from tiny samples
- do not hide repeated discipline failures behind a positive net PnL
- do not recommend more than one or two process changes at once

## Usage examples

- "Use `journal-pattern-analyzer` on my last 25 swing trades and tell me what mistake keeps repeating."
- "Use `journal-pattern-analyzer` on my trade journal from earnings season and show me whether event holds improved or hurt my process."
