---
name: consensus-vs-pricing-map
description: Map what the market is pricing across forwards, vol, surveys, positioning, and price action, then identify where consensus is fragile, inconsistent, or vulnerable to surprise. Use when the task is to understand the market's base case before forming a trade view.
---

# Consensus Vs Pricing Map

Use this skill when the task is to establish what the market already expects before trying to generate or validate a trade idea.

This skill is the dedicated "priced in" layer. It goes deeper than a quick consensus summary and forces the expectation map to be explicit.

This skill will not:

- jump straight from market data to a trade recommendation
- treat one indicator as the whole market consensus
- confuse survey consensus with actual capital positioning
- force a surprise thesis when the market is already fairly balanced

## Role

Act like a macro strategist building the expectation map for a market. Your job is to show what the market is pricing, where the different expectation surfaces agree or disagree, and which surprise vectors are actually alive.

## When to use it

Use it when the task requires:

- understanding what is already priced into a market before taking a view
- preparing for a macro catalyst by identifying the real surprise space
- separating survey consensus from market pricing and actual positioning
- deciding whether a market's base case is fragile enough to offer opportunity
- feeding a clean expectation map into `trader-thinking` or `macro-idea-generation`

## Inputs

This skill operates on:

- the market, asset class, or event being analyzed
- the decision horizon: next session, next week, next month, or catalyst window
- whether the focus is one market or a small cross-asset cluster
- any event or macro question that motivates the mapping exercise

Additional context that strengthens the analysis:

- current narratives believed to dominate the market
- any suspected positioning extremes
- relevant cross-asset markets that should confirm or challenge the base case
- prior consensus estimates or desk expectations

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- forwards, futures curves, or market-implied policy paths
- implied vol, skew, term structure, and event-premium where relevant
- survey medians and dispersion where available
- positioning and flow data where available
- price action around recent confirming or disconfirming information
- related credit, vol, or cross-asset confirmation markets

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Define the horizon and the market question being mapped.
2. Collect the main expectation surfaces: forwards, options, surveys, positioning, and price action.
3. State the market's base case in plain language, not as a data dump.
4. Check whether the surfaces agree, disagree, or imply different time horizons.
5. Identify fragility signals such as one-way positioning, low vol before a catalyst, or price insensitivity to contrary information.
6. Define the genuine surprise vectors, including what would be upside surprise, downside surprise, and "no surprise."
7. End with whether the consensus is clear and fragile, clear but durable, muddled, or not offering a clean edge.

## Core Assessment Framework

Assess the expectation map on five anchors:

- `Base Case Clarity`: whether the market's main expectation can be stated clearly. If not, there may be no usable consensus to fade or reinforce.
- `Surface Agreement`: whether forwards, vol, surveys, positioning, and price action tell the same story or different stories.
- `Positioning Fragility`: whether real money or speculative positioning appears crowded enough to create asymmetric reactions.
- `Vol Pricing`: whether the options market is pricing a calm or fragile outcome relative to the event risk.
- `Surprise Space`: whether there is still meaningful room for a shock that the market is not already prepared for.

Use the anchors to classify:

- `consensus clear and fragile`: clear base case with meaningful one-way risk
- `consensus clear but durable`: clear base case, but little evidence of crowding or fragility
- `consensus muddled`: surfaces conflict enough that no single base case dominates
- `no clean surprise space`: the likely outcomes appear broadly well discounted

## Output tables

### Pricing Surfaces
| Surface | Current Signal | What It Implies | Fragility Signal |
|---------|----------------|-----------------|------------------|
| Forwards / Futures | ... | ... | ... |
| Options / Vol | ... | ... | ... |
| Surveys | ... | ... | ... |
| Positioning | ... | ... | ... |
| Price Action | ... | ... | ... |

## Output structure

Prefer this output order:

1. `Market And Horizon`
2. `Pricing Surfaces`
3. `Consensus Synthesis`
4. `Fragility Signals`
5. `Surprise Map`
6. `What Is Not A Surprise`
7. `Next Skill`

Always include:

- the market's base case in plain language
- the key surfaces used to infer that base case
- where the expectation map looks fragile or internally inconsistent
- the highest-signal surprise vector
- whether the next step is `trader-thinking`, `macro-idea-generation`, `macro-event-analysis`, or an asset-class specialist skill

## Best practices

- do not confuse what commentators say with what markets are actually pricing
- do not stop at surveys if forwards or options disagree
- do not infer fragility from price direction alone; you need positioning or event-pricing context
- do not force a contrarian view if the map says the market is broadly balanced

## Usage examples

- "Use `consensus-vs-pricing-map` on the next FOMC meeting and show me what rates, FX, and vol markets are already pricing."
- "Use `consensus-vs-pricing-map` on EURUSD for the next month and tell me whether the dollar base case looks fragile."
- "Use `consensus-vs-pricing-map` on crude oil and tell me what the curve, vol surface, and price action imply is already discounted."
