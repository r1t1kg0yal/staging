# Prediction Markets -- Context Wiring Design

This API produces two outputs: a light context snapshot for get_context injection, and a full briefing JSON for code execution analysis.


## Context Layer (get_context)

**File**: `briefings/CONTEXT.md`
**Size**: ~2-4K tokens
**Contents**: Current probabilities + 1d deltas + volume, grouped by topic. No time series, no trajectories, no biggest moves, no outcome distributions.

This is the ambient awareness payload. It tells PRISM what the crowd is pricing and what moved, at a glance. Enough to inform any macro analysis without consuming significant context budget.


## Code Execution Layer (execute_analysis_script)

Everything beyond the snapshot -- time series, weekly trajectories, biggest single-day moves, outcome distributions (e.g., 1/2/3 cuts or 48/49/50 seats), cross-event correlation, phase detection -- is a code execution question. PRISM runs the scraper or reads the full briefing JSON.

Available via code execution:
- Full briefing JSON: `briefings/briefing_{ts}.json` (histories, movers, all outcomes)
- Scraper commands: `search`, `price-history`, `autopilot --focus`, `render`
- Direct API access: Kalshi + Polymarket public endpoints


## Trigger Logic

Load prediction markets context when the user query touches:

- "What is priced in" / "what are markets expecting"
- Fed/FOMC rate expectations
- Geopolitical event probabilities (Iran, Russia, China, Israel, etc.)
- Election or political outcome expectations
- Scenario calibration or probability-weighted analysis
- Any "state of the world" or briefing request
- Trade idea generation involving crowd-implied probabilities
- Change detection ("what moved", "what repriced", "what changed")


## Freshness Model

- **Source**: `briefings/CONTEXT.md` (static file, refreshed by running autopilot)
- **Staleness**: Acceptable up to ~24 hours for general macro context. For time-sensitive questions (e.g., "what changed today"), run autopilot fresh before loading.
- **Refresh command**: `python prediction_markets_scraper.py autopilot --focus all`
- **Refresh time**: ~60-90 seconds


## Context Tier

- **Tier 2 (on-demand)**: Load when triggered by query relevance, not always-on.
- Could be promoted to Tier 1 if configured for "macro analyst" mode where ambient awareness of crowd pricing is always valuable.


## Dependencies

- Requires periodic autopilot runs to keep CONTEXT.md fresh
- No API keys or auth needed (both Kalshi and Polymarket are public APIs)
- Only Python dependency: `requests`


## Integration Points

| Pair With | Integration Value |
|-----------|-------------------|
| FRED / Haver | "Data vs crowd" divergence analysis -- compare actual macro indicators against crowd-implied probabilities |
| Treasury Fiscal Data | Debt ceiling and government shutdown event context |
| FDIC | Banking stress event probabilities |
| BIS | Cross-border flow data for geopolitical risk context |
| CNBC / News | Narrative context for probability moves |
