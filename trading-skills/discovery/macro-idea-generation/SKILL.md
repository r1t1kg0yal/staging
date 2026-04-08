---
name: macro-idea-generation
description: Generate a short ranked slate of macro trade ideas by starting from what markets are pricing, where consensus is fragile, which dislocations have catalysts, and which setups fit the existing book. Use when the task is to originate ideas, not just analyze one trade already in hand.
---

# Macro Idea Generation

Use this skill when the task is to originate macro trade ideas from pricing, positioning, carry, and dislocations rather than from a watchlist of names.

The goal is not to produce more ideas. The goal is to surface the few ideas that deserve real attention.

This skill will not:

- turn a broad market scan into a shopping list of weak trades
- confuse a macro narrative with a priced edge
- recommend immediate sizing without moving into structure and risk review
- pretend that every market must offer an opportunity right now

## Role

Act like a discretionary macro PM in an idea meeting. Start with what is priced in, identify where consensus is fragile or internally inconsistent, and narrow the opportunity set to a short ranked slate that is worth further work.

## When to use it

Use it when the task requires:

- generating fresh trade ideas across rates, FX, equities, commodities, or vol
- deciding which current dislocations deserve the team's time
- triaging a large macro opportunity set into a small active slate
- translating a regime view into specific candidate trades
- refreshing the opportunity set before a new week, month, or catalyst window

## Inputs

This skill operates on:

- the markets or asset classes to scan
- the intended horizon: intraday, event window, tactical, or medium-term
- any existing macro thesis, regime view, or catalyst focus
- the current book context if portfolio fit matters
- whether the mandate is directional, relative value, or mixed

Additional context that strengthens the analysis:

- what the market is believed to be pricing already
- known positioning extremes
- known carry-rich or carry-poor areas
- major upcoming catalysts
- current gross, net, or sleeve-level portfolio constraints

If the user provides only a vague macro theme with no time horizon or markets of interest, state that clearly and keep the slate provisional rather than pretending to scan every market equally well.

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- forward curves, futures curves, or market-implied paths for the relevant asset classes
- implied vol, skew, and term structure where optionality matters
- positioning and flow data where available
- historical percentile context for key spreads, slopes, basis levels, and vol levels
- carry metrics or bleed profile for candidate expressions
- upcoming macro and event calendar for the decision horizon
- current portfolio exposures if book fit matters

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Start with the market's base case. What is already priced across the relevant curves, vol surfaces, and positioning data.
2. Identify where pricing looks fragile, internally inconsistent, or too one-sided.
3. Translate those dislocations into candidate ideas using the carry, value, and momentum lenses from `trader-thinking`.
4. Check whether each candidate is supported or contradicted by the cross-asset picture.
5. Identify the catalyst or timing window that could force the market to reprice.
6. Assess whether each candidate can be expressed cleanly and whether the likely carry profile is acceptable.
7. Rank the ideas and keep only the few that are scarce enough to deserve more work.

## Core Assessment Framework

Assess each candidate on six anchors before keeping it on the slate:

- `Consensus Fragility`: how clear and vulnerable is the current market base case. A trade with no identifiable priced consensus is weak idea-generation material.
- `Dislocation Quality`: how large and real is the mispricing or inconsistency. Prefer actual dislocations over generic narratives.
- `Carry Or Bleed`: what is earned or paid while waiting. Negative-carry ideas need a catalyst with urgency.
- `Catalyst Quality`: whether there is a credible timing mechanism for repricing. A clean catalyst beats a vague "eventually."
- `Cross-Asset Confirmation`: whether related markets support or challenge the idea. A macro idea with no confirmation needs a stronger explanation.
- `Portfolio Fit`: whether the idea adds a differentiated source of return or merely duplicates risk the book already owns.

Use the anchors to classify:

- `top-tier idea`: clear dislocation, fragile consensus, acceptable carry profile, identifiable catalyst, and good book fit
- `watch closely`: interesting setup, but one or two anchors are still weak
- `pass for now`: narrative exists, but the dislocation, catalyst, or portfolio fit is not good enough

## Output tables

### Ranked Idea Slate
| Rank | Idea | Core View | Why It Exists | Carry / Bleed | Catalyst | Book Fit | Priority |
|------|------|-----------|---------------|---------------|----------|----------|----------|
| 1 | ... | ... | ... | ... | ... | ... | Top-tier / Watch / Pass |
| 2 | ... | ... | ... | ... | ... | ... | ... |
| 3 | ... | ... | ... | ... | ... | ... | ... |

## Output structure

Prefer this output order:

1. `Backdrop`
2. `What Looks Priced In`
3. `Ranked Idea Slate`
4. `Why These Ideas Survive`
5. `Why Other Ideas Were Rejected`
6. `Next Skill`

Always include:

- the macro backdrop used for the scan
- the main priced-in assumption or dislocation behind each surviving idea
- the expected carry or bleed profile
- the catalyst or forcing function
- whether each idea should move next to `consensus-vs-pricing-map`, `trade-expression`, `dislocation-ranker`, or an asset-class specialist skill

## Best practices

- do not reward ideas just because they sound intelligent in macro language
- do not keep more ideas than can realistically be monitored and advanced
- do not ignore carry cost just because the narrative is attractive
- do not pass through ideas that duplicate existing portfolio risk without saying so clearly
- do not force symmetry across asset classes; some weeks the best ideas may cluster in one area

## Usage examples

- "Use `macro-idea-generation` to scan rates, FX, and gold for the next two weeks around CPI and the FOMC."
- "Use `macro-idea-generation` on my current macro backdrop and tell me which three trade ideas deserve the desk's time."
- "Use `macro-idea-generation` for a medium-term cross-asset book and focus on carry-rich relative value trades rather than outright directionals."
