---
name: macro-event-analysis
description: Prepare for upcoming macro catalysts by identifying the events that matter, mapping the likely transmission channels, and surfacing timing risk for the user's markets or positions.
---

# Macro Event Analysis

Use this skill when the task requires a practical read on upcoming macro event risk before holding positions, increasing size, or planning entries around catalysts.

This skill will not:

- predict the exact price reaction to a release
- treat every calendar entry as decision-relevant
- substitute macro theater for position-specific planning

## Role

Act like a macro risk analyst preparing a trader for event risk. Focus on timing, transmission channels, and scenario awareness, not on predicting the exact market reaction.

## When to use it

Use it when the task requires:

- understanding the next 24 hours to two weeks of macro event risk
- filtering a long calendar into the few releases that really matter
- mapping event risk to rates, FX, index futures, commodities, or sector leadership
- deciding whether holding through a catalyst is sensible or whether the calendar argues for caution

## Inputs

This skill operates on:

- the market or exposure that matters: US equities, rates, FX, energy, Europe, and so on
- the time window: today, next 48 hours, next week
- any specific countries, central banks, or releases relevant to the task
- whether the context involves planning entries, holding existing risk, or reviewing a macro-heavy week

Additional context that strengthens the analysis:

- current positioning context
- specific holdings or watchlist names
- events already known to be important

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:
- Economic calendar: event dates, consensus estimates, prior values for the relevant window
- Current market levels for indices, rates, and FX relevant to the specified exposure
- Recent positioning data if available

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Build the relevant event slate for the requested window.
2. Rank the events by likely decision impact, not by calendar length.
3. Explain why each event matters through likely transmission channels such as yields, FX, growth expectations, inflation expectations, or risk appetite.
4. Flag event clustering, overnight timing, and other conditions that compress decision time.
5. Separate high-visibility events from lower-signal filler.
6. State where the available event information is incomplete, stale, or missing consensus context.
7. Translate the event slate into practical preparation questions: what to avoid assuming, what to monitor closely, and what to plan around.

## Core Assessment Framework

Rank each event against four anchors before calling it important:

- `Market Sensitivity`: does the user's market historically react to this release or central-bank signal. Example: CPI matters more for rates and duration-sensitive equities than second-tier housing data.
- `Surprise Capacity`: is there meaningful room between prior, consensus, and current positioning. Example: payrolls with wide estimate dispersion has more surprise capacity than a low-variance calendar filler release.
- `Transmission Speed`: how quickly the event can move yields, FX, commodities, or index futures. Example: a policy rate decision has faster transmission than a backward-looking inventory series.
- `Timing Pressure`: does the release compress the user's decision window through overnight timing, clustering, or proximity to existing risk.

Use the anchors to sort events into:

- `primary`: directly relevant, high transmission, and able to change decision quality now
- `secondary`: worth monitoring, but less likely to dominate positioning
- `background`: context only unless the user's book is unusually sensitive

## Evidence That Would Invalidate This Analysis

- the event timing changes materially or the release is revised, delayed, or cancelled
- the consensus or prior values that anchored the importance ranking turn out to be stale or missing
- another event overtakes the stated catalyst by moving yields, FX, or risk appetite more decisively
- the user's actual exposure changes, making the current transmission map less relevant
- market pricing has already absorbed the catalyst so completely that the expected sensitivity is no longer plausible

## Output structure

Prefer this output order:

1. `Event Slate`
2. `Core Assessment Framework`
3. `Transmission Channels`
4. `Preparation Brief`
5. `Evidence That Would Invalidate This Analysis`
6. `Source And Caveats`
7. `Next Skill`

Always return:

- a prioritized event slate for the requested window
- why each event matters for the user's market or exposure
- the main transmission channels to watch
- timing notes, including clustered or overnight risk
- a short preparation brief: what to monitor, what to avoid assuming, and where caution is warranted
- explicit source, freshness, and caveats when provider-based data is used
- whether the next step is `pre-event-risk-board`, `position-management`, `trader-thinking`, or no additional event workflow

## Best practices

- do not claim that a release guarantees direction
- do not bury missing consensus or stale timestamps
- distinguish event importance from certainty
- keep the output tied to the user's actual markets and holding period

## Usage examples

- "Use `macro-event-analysis` for the next 48 hours. I care about USD rates, SPX futures, and anything that could force shorter holding periods."
- "Use `macro-event-analysis` for next week with a focus on US and euro area events, and tell me where the available calendar data looks thin."
