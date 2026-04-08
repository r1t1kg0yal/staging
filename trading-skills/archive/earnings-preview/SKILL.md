---
name: earnings-preview
description: Prepare for an upcoming earnings report or earnings week by identifying the reports that matter, framing the key debates, and surfacing the read-through risk that could affect the user's watchlist or positions. Use as a specialist single-name or sector event tool, not as the default macro PM event workflow.
---

# Earnings Preview

Use this skill when the task requires preparation before one company reports or before an earnings-heavy week.

For whole-book event governance around macro-heavy calendars or clustered catalysts, use `pre-event-risk-board`. This skill is the specialist side branch for single-name or sector earnings work.

This skill will not:

- predict the post-report price move with certainty
- confuse a benchmark company's importance with a guaranteed read-through
- replace missing fundamentals with narrative filler

## Role

Act like a skeptical earnings prep analyst. Focus on what matters, what is already priced in, what could surprise, and where the read-through really matters.

## When to use it

Use it when the task requires:

- prioritizing which upcoming reports actually deserve attention
- preparing for a single company report with peer and sector context
- identifying likely read-through names around a benchmark report
- deciding whether a report is worth holding through, fading, or avoiding

## Inputs

This skill operates on:

- the company, peer group, sector, or watchlist
- the date window or specific report being discussed
- the thesis, exposure, or planned trade posture
- what matters most this quarter: growth, margins, guidance, backlog, capex, demand, pricing, AI spend, consumer health, and so on
- whether the focus is on the report itself, sector read-through, or index impact

Additional context that strengthens the analysis:

- consensus expectations or prior-quarter context
- known positioning or sentiment concerns
- whether the plan is to hold through the event

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:
- Earnings calendar: report dates and times for the relevant names
- Consensus estimates: EPS, revenue, and guidance expectations
- Earnings revision history: direction and magnitude of recent estimate changes
- Options-implied move for reporting companies
- Prior quarter results, guidance, and management commentary highlights

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Identify the reports that matter most for the user's names or theme.
2. Explain why each report matters: direct exposure, peer sympathy, benchmark status, or index weight.
3. Frame the key debates going into the report instead of defaulting to generic "beat or miss" language.
4. Separate pre-report setup risk from business-quality judgment.
5. Highlight the likely read-through paths, including supplier, customer, competitor, or sector ETF implications.
6. State what would actually change the thesis, not just what would create short-term noise.
7. If data was retrieved from the data harness, disclose source, freshness, and any coverage gaps.

## Core Assessment Framework

Assess each report on four anchors before ranking it:

- `Benchmark Relevance`: whether the company can move a sector, supplier chain, customer set, or broad index. Example: NVDA is benchmark-relevant for semis and AI infrastructure; a small software name usually is not.
- `Debate Intensity`: whether the quarter has one or two live disagreements that matter more than the headline beat or miss. Example: gross margin durability or cloud booking reacceleration counts as a real debate; generic "can they beat" does not.
- `Read-Through Strength`: whether peers or related industries will plausibly react to the same datapoints. Example: capex guidance from a hyperscaler may matter for semis, power, cooling, and networking.
- `Positioning Risk`: whether sentiment, recent price action, or the user's exposure makes the event more dangerous to hold through.

Use the anchors to classify:

- `must-watch`: benchmark relevance is high and at least one of debate intensity, read-through strength, or positioning risk is also high
- `watch`: relevant event, but consequences are narrower or easier to absorb
- `background`: useful context, but low priority unless it directly affects the user's book

## Evidence That Would Invalidate This Analysis

- the report date or session changes enough to alter the planning window
- the quarter's key debate changes because management, industry data, or a peer report reframes the issue
- read-through assumptions break because the peer set, supplier chain, or benchmark relationship was overstated
- the user's exposure or holding plan changes, making the current priority ranking less relevant
- estimate, guidance, or schedule fields turn out to be stale, incomplete, or sourced from an unreliable snapshot

## Output structure

Prefer this output order:

1. `Priority List`
2. `Core Assessment Framework`
3. `Key Debates`
4. `Read-Through Map`
5. `Plan Risk`
6. `Evidence That Would Invalidate This Analysis`
7. `Source And Caveats`

Always return:

- a prioritized report list or single-name preview
- why each report matters in plain language
- the key debates or watch items going into the print
- the likely read-through map for peers, suppliers, customers, or sector leadership
- the main pre-report risk to the user's plan
- explicit caveats around missing dates, incomplete estimates, stale data, or example-mode data when relevant
- whether the next step is `earnings-trade-prep`, `pre-event-risk-board`, or standalone prep is sufficient

## Best practices

- do not turn "important report" into "predictable trade"
- do not confuse sector importance with a guaranteed stock move
- distinguish between what matters for fundamentals and what matters for positioning
- if timing, estimates, or coverage are incomplete, say that early rather than burying it
- do not use a single-name earnings preview as a substitute for whole-book event governance

## Usage examples

- "Use `earnings-preview` for NVDA next week. I care about AI demand, gross margin durability, and read-through for semis."
- "Use `earnings-preview` for AAPL, AMZN, and COST over the next ten days and tell me which reports matter most for index and sector read-through."
