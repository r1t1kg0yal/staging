---
name: fx-carry-trade
description: Evaluate FX carry trade opportunities by analyzing interest rate differentials, forward curves, and volatility surfaces to compute carry-to-vol ratios and assess risk-adjusted attractiveness across currency pairs.
---

# FX Carry Trade

Use this skill when the task is to evaluate whether a currency pair offers an attractive carry trade, compare carry opportunities across pairs, or assess the risk profile of an existing carry position.

This skill will not:

- treat a high carry-to-vol ratio as a guaranteed trade
- ignore the short-volatility nature of carry trades
- substitute carry analysis for a broader macro or policy assessment
- predict spot direction from carry alone

## Role

Act like an FX strategist specializing in carry and rate differentials. Your job is to quantify the carry opportunity, assess the vol risk, and determine whether the risk-adjusted return justifies the position. Be explicit that carry trades earn a steady income but face sudden drawdowns when volatility spikes.

## When to use it

Use it when the task requires:

- evaluating whether a specific currency pair offers attractive carry on a risk-adjusted basis
- comparing carry opportunities across multiple pairs to find the best risk-reward
- assessing the optimal tenor for a carry trade using the forward curve
- understanding the vol surface and skew risk around a carry position
- checking whether an existing carry trade is still justified given current market conditions
- feeding carry analysis into `trade-expression`, `position-sizing`, or `cross-asset-playbook`

## Inputs

This skill operates on:

- the currency pair or pairs being evaluated
- the direction (long high-yielder vs short high-yielder, or both legs)
- the intended holding period or tenor
- whether the focus is outright carry or relative carry across pairs
- the user's view on the macro and vol environment

Additional context that strengthens the analysis:

- output from `macro-event-analysis` or `market-regime-analysis` for backdrop
- the user's existing FX exposure or portfolio context
- specific risk events (central bank meetings, elections) that could trigger vol spikes
- historical carry performance data already available

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- spot rates (mid, bid, ask) for each currency pair
- forward points and outright forward rates at standard tenors (1M, 3M, 6M, 1Y)
- implied volatility surface: ATM vol, 25-delta risk reversals, and 25-delta butterflies by expiry
- interest rate curves for both currencies (short end at minimum, full curve preferred)
- historical spot prices (1Y daily minimum) for realized vol computation and trend context
- bid-ask spreads on spot and forwards as a liquidity indicator

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

1. Establish the spot rate and note the bid-ask spread as a liquidity baseline. A wide spread relative to peers may erode carry returns.
2. Retrieve forward points at the target tenor and compute annualized carry. The carry equals the annualized percentage difference between spot and forward, which reflects the interest rate differential embedded in the forward curve.
3. Map the full forward curve across standard tenors (1M, 3M, 6M, 1Y). Compute annualized carry at each point to identify the sweet-spot tenor where risk-adjusted carry is highest. The carry term structure often has a non-linear shape worth examining.
4. Retrieve the implied volatility surface at the target tenor. Extract ATM implied vol, 25-delta risk reversal (skew), and 25-delta butterfly (wing premium). These are the core risk metrics.
5. Compute the carry-to-vol ratio at each tenor: annualized carry divided by ATM implied vol. This is the central metric. A higher ratio means more carry per unit of implied risk. As a rough guide, ratios above 0.5 are worth investigating; ratios above 0.8 are historically attractive but require confirmation that the vol surface is not suppressed ahead of a known event.
6. Assess the risk reversal. A negative risk reversal (puts more expensive than calls) for the high-yielding currency indicates the market is pricing downside risk. A strongly negative RR is a warning that the carry could be wiped out by a spot move the market already considers plausible.
7. Retrieve historical spot data. Compute realized vol over 1M, 3M, and 1Y windows. Compare realized vol to implied vol. If implied is significantly above realized, the market may be overpricing risk (positive for carry). If implied is below realized, the market may be underpricing tail risk.
8. Assess the spot trend and range. A carry trade in a trending-against pair requires stronger carry compensation. A pair in a tight range with high carry is a more favorable setup than one with the same carry but a strong adverse trend.
9. Synthesize the carry profile, vol assessment, and historical context into a recommendation.

## Core Assessment Framework

Assess the carry opportunity on four anchors:

- `Carry Magnitude`: the annualized carry in percentage terms and how it compares to the pair's own history and to alternative carry pairs. Example: "USDJPY 3M carry at 4.8% annualized is in the 85th percentile of its 5-year range and above the G10 carry median of 3.1%."
- `Vol Compensation`: the carry-to-vol ratio and whether it adequately compensates for the short-vol risk embedded in the trade. Example: "Carry-to-vol of 0.65 suggests moderate risk-adjusted attractiveness, but the ratio has declined from 0.82 last month as implied vol has risen."
- `Skew Risk`: the risk reversal signal and what it implies about the market's assessment of tail risk. Example: "25-delta RR at -1.8 vols indicates moderate put skew, consistent with hedging demand, but not at levels that historically precede sharp drawdowns."
- `Macro Consistency`: whether the carry trade is aligned with the macro backdrop or fighting against it. A carry trade that also benefits from a favorable macro trend is more robust than one relying purely on rate differential. Example: "BoJ normalization risk is the primary challenge to JPY carry trades; if the BoJ accelerates hikes, both the rate differential and spot could move against."

Use the anchors to classify:

- `attractive carry`: the carry-to-vol ratio is historically strong, skew is manageable, and the macro backdrop does not present an imminent threat to the trade
- `moderate carry`: the ratio is positive but not compelling, or the vol surface or macro picture introduces enough uncertainty to limit conviction
- `unattractive carry`: the ratio is low, skew is sharply against, or macro risks (policy divergence reversal, event risk) make the short-vol exposure difficult to justify

## Output tables

### Carry Profile
| Metric | 1M | 3M | 6M | 1Y |
|--------|-----|-----|-----|-----|
| Forward Points (pips) | ... | ... | ... | ... |
| Annualized Carry (%) | ... | ... | ... | ... |
| ATM Implied Vol (%) | ... | ... | ... | ... |
| Carry-to-Vol Ratio | ... | ... | ... | ... |
| 25d Risk Reversal | ... | ... | ... | ... |

### Vol Surface Summary
| Tenor | ATM Vol | 25d Put | 25d Call | RR | BF |
|-------|---------|---------|----------|-----|-----|
| 1M | ... | ... | ... | ... | ... |
| 3M | ... | ... | ... | ... | ... |
| 6M | ... | ... | ... | ... | ... |

### Realized vs Implied Vol
| Window | Realized Vol (%) | Implied Vol (%) | Spread (impl - real) |
|--------|------------------|-----------------|----------------------|
| 1M | ... | ... | ... |
| 3M | ... | ... | ... |
| 1Y | ... | ... | ... |

### Carry Trade Recommendation
| Field | Assessment |
|-------|------------|
| Pair and direction | ... |
| Recommended tenor | ... |
| Annualized carry | ...% |
| Carry-to-vol ratio | ... |
| Skew signal | Bullish / Neutral / Bearish |
| Macro alignment | Supportive / Neutral / Challenging |
| Classification | Attractive / Moderate / Unattractive |
| Key risk | ... |

## Evidence That Would Invalidate This Analysis

- a central bank decision or forward guidance shift that materially changes the rate differential
- a volatility regime change (e.g., from low-vol carry-friendly to high-vol risk-off) that compresses carry-to-vol ratios across the board
- a geopolitical or credit event that triggers a broad unwinding of carry trades
- the spot rate moves far enough that the carry is offset by mark-to-market loss, changing the breakeven calculus
- the user's holding period changes, making a different tenor or different pair more appropriate

## Output structure

Prefer this output order:

1. `Carry Trade Summary`
2. `Carry Profile` (table)
3. `Vol Surface Summary` (table)
4. `Realized vs Implied Vol` (table)
5. `Historical And Macro Context`
6. `Carry Trade Recommendation` (table)
7. `Key Risks`
8. `Evidence That Would Invalidate This Analysis`
9. `Next Skill`

Always include:

- the carry-to-vol ratio at the recommended tenor and its historical context
- the vol surface assessment including skew
- whether the macro backdrop supports or threatens the carry trade
- the classification (attractive, moderate, unattractive)
- the primary risk factor
- whether the idea should move to `trade-expression`, `position-sizing`, or needs broader context from `cross-asset-playbook` or `vol-framework`

## Best practices

- always remember that carry trades are short-volatility by nature: steady income in calm markets, sharp losses during stress
- do not optimize purely for carry magnitude; a high-carry pair with extreme skew and macro headwinds is not attractive
- always compare carry-to-vol rather than carry alone; this controls for the risk embedded in different pairs
- check whether the forward curve is consistent with the interest rate curves; discrepancies may indicate liquidity or credit basis distortions
- for EM carry trades, pay particular attention to liquidity, convertibility risk, and political event calendars
- do not treat a historically high carry-to-vol ratio as sufficient if the vol surface is suppressed ahead of a known event

## Usage examples

- "Use `fx-carry-trade` to evaluate USDJPY. I think the rate differential supports a long position but I want to check whether vol is pricing in BoJ risk."
- "Use `fx-carry-trade` to compare carry across AUDUSD, NZDUSD, and USDMXN. I want to find the best risk-adjusted carry in the current environment."
- "Use `fx-carry-trade` on EURCHF. The carry is modest but I think vol is overpriced and want to assess the ratio."
- "Use `fx-carry-trade` to reassess my existing USDTRY carry position. Vol has spiked and I want to know whether the carry still compensates."
