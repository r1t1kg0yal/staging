---
name: risk-management
description: A proactive risk management thinking framework covering position-level stop logic, portfolio-level exposure control, risk budgeting, drawdown management, tail risk awareness, and whole-book risk review routing. Use when the task requires assessing, structuring, or tightening risk before or during live exposure at any level from single position to full book.
---

# Risk Management

Use this skill when a structured approach to managing risk is needed across positions and the portfolio, whether before entering new risk, while managing existing exposure, or conducting a whole-book risk review.

This skill will not:

- compute VaR, CVaR, or other statistical risk measures mechanically
- replace judgment with a formula or a single number
- tell the user whether a specific trade thesis is good or bad
- guarantee that following a process prevents losses
- turn an oversized position into a safe one through stop placement alone
- build a long-term strategic financial plan
- assume a portfolio is safe just because no single holding looks extreme in isolation

## Role

Act like a disciplined risk manager who prioritizes survival over performance. The base case assumption is that any single position can go to zero and any correlation assumption can break under stress. Your job is to ensure the process accounts for this before the loss arrives, not after. When reviewing the whole book, act like a macro PM reviewing risk before adding or defending exposure.

## When to use it

Use it when the task requires:

- evaluating whether current risk exposure is appropriate before adding new positions
- defining stop logic, loss limits, or drawdown rules for a trade or portfolio
- assessing whether multiple positions share hidden risk factors
- deciding whether to reduce gross exposure, tighten stops, or flatten during a drawdown
- building a risk budgeting framework that allocates risk capacity across ideas
- stress-testing whether the portfolio survives a plausible tail scenario
- reviewing whether the portfolio's risk profile matches the user's stated risk tolerance
- conducting a whole-book risk review before adding, holding, or reducing risk
- understanding where concentration, gross or net drift, and overlap are hiding
- assessing whether upcoming catalysts create too much clustered exposure across the book
- translating a market view into a portfolio action rather than just a position-level action

## Inputs

This skill operates on:

- current portfolio positions with approximate sizes and directions
- recent P&L and drawdown context if relevant
- gross and net exposure if known
- sector, theme, or factor tags for positions
- any existing risk rules already in place
- whether the assessment is about a single position, the portfolio, or both
- whether the snapshot is the full portfolio, one account, or only the active risk sleeve
- any planned new add or reduction
- upcoming catalysts already known

Additional context that strengthens the analysis:

- correlation estimates or known risk factor overlaps
- recent vol or beta for key positions
- drawdown history or max tolerable drawdown
- upcoming catalysts or events that could drive gap risk
- leverage or margin utilization
- current regime view or macro concern
- carry profile or bleed profile of the book
- cross-asset drivers shared by multiple positions
- which positions are already under pressure or near key catalysts
- any known liquidity or execution constraints

If the snapshot is partial, say so clearly and keep the result provisional.

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- portfolio holdings with position sizes, directions, and entry prices
- P&L history, at minimum current drawdown from peak
- correlation matrix or factor exposure breakdown for key positions
- gross and net exposure by sector, theme, geography, and asset class
- volatility estimates for individual positions and the portfolio

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

Work through each section in order. Not every section applies to every query -- if the query concerns a single position, position-level risk is the focus; if the query concerns the book, start at portfolio-level.

### Position-level risk

1. Review stop logic for each position. A stop should represent thesis invalidation -- the price or condition at which the original idea is broken. Arbitrary dollar loss limits that bear no relationship to the thesis create noise exits and false discipline. Use `position-sizing` for stop-based trade math and `macro-book-sizing` when the real question is book-level allocation.
2. Compute max loss per position from entry to stop. Verify it fits within the per-trade risk budget. If the stop is so wide that the position must be tiny to fit the budget, the trade may not be worth the capital allocation.
3. Identify positions that share the same underlying risk factor. Correlated positions must be treated as a single risk event for sizing purposes, not independent bets. Three long positions in semiconductor names is one semiconductor bet with three implementation legs, not three separate ideas.
4. Flag any position without a defined invalidation point. Open-ended risk is the most dangerous kind because there is no predetermined framework for when to exit.
5. Assess whether any position has become too large relative to the portfolio through appreciation. A position that was appropriately sized at entry but has doubled may now represent outsized risk even though the thesis is intact. Winners create concentration risk that requires active monitoring.

### Portfolio-level risk

6. Assess gross exposure. High gross magnifies both gains and losses and reduces the portfolio's capacity to absorb shocks. Gross exposure is a risk dial -- raising it increases the portfolio's sensitivity to everything, including scenarios not yet considered.
7. Assess net exposure. Distinguish between intentional directional bias and accidental drift. A portfolio that has become net long because winners ran is different from one deliberately positioned net long. Unintentional net exposure is uncompensated risk.
8. Check sector, factor, and theme concentration. Use `portfolio-concentration` if the overlap is complex. The question is not "how many positions" but "how many independent risk factors drive the P&L."
9. Evaluate correlation assumptions under stress. Correlations increase during drawdowns. Positions that appeared diversified in calm markets often move together during stress. The base case for risk management should assume correlations increase, not that they remain stable.
10. Check for offsetting positions that may not actually hedge. A long equity position and a short in a different equity are not necessarily a hedge -- they are two directional bets unless they share a clear common factor the spread isolates.
11. Assess whether the portfolio's risk profile has drifted from its intended design. Over time, winners grow, losers shrink, and new positions get added. The resulting portfolio may bear little resemblance to the one that was originally constructed. Periodic comparison of actual risk to intended risk is essential.

### Risk budgeting

12. Assess whether total risk is allocated intentionally across ideas or has accumulated through ad hoc sizing. Risk budgeting means deciding in advance: how much total risk capacity exists, how it divides across themes or asset classes, and how much remains unallocated as reserve.
13. Verify that the highest-conviction ideas receive the most risk budget and that lower-conviction positions are sized accordingly. Position size should reflect conviction and edge quality, not familiarity or comfort with the name.
14. Check whether the risk budget leaves room for new opportunities. A fully invested book with no unallocated risk capacity forces closing existing positions to pursue new ideas, which introduces forced decision-making under pressure.
15. Evaluate risk budget across time horizons. Short-term tactical positions, medium-term swing trades, and longer-horizon structural views should each have a dedicated allocation. A book that concentrates all risk in one time horizon is fragile to that horizon's specific risks.
16. Check whether the risk budget accounts for the carry cost of positions. A portfolio of negative-carry positions (long options, funding-intensive longs) consumes risk budget through time decay even when theses are intact. The total bleed rate should be tolerable for the expected holding period.

### Drawdown management

17. Evaluate whether predefined drawdown response rules exist. Effective drawdown management is a process defined before the drawdown begins, not a reaction improvised during it.
18. Assess the current drawdown against thresholds. A typical structure:

- Below 5% drawdown: normal variance, no action beyond standard monitoring
- 5-10% drawdown: review all positions for thesis integrity, tighten stops to invalidation levels, reduce gross if any position lacks current conviction
- 10-15% drawdown: mandatory gross reduction, flatten lowest-conviction positions, preserve capital for recovery
- Above 15% drawdown: significant capital impairment, flatten to minimal exposure, conduct full portfolio and process review before re-engaging

These thresholds are illustrative. The actual levels should reflect the strategy, volatility target, and capital base.

19. Distinguish drawdown as noise from drawdown as signal. A drawdown caused by broad market weakness while individual theses remain intact requires a different response than a drawdown caused by thesis failures. If theses are breaking, the drawdown is information. If theses are intact and the market is simply volatile, the drawdown may be tolerable.

### Tail risk

20. Identify the scenario the market is not pricing. Tail risk is not about expected outcomes but about the distribution of outcomes in the left tail that consensus has not discounted. What event would cause the largest portfolio loss? How large would that loss be? Is the portfolio prepared for it?
21. Assess gap risk. Overnight events, weekend risk, illiquid markets, and binary catalysts can produce losses larger than any stop would capture. When gap risk is material, position size is the only effective risk control -- stops cannot protect against gaps.
22. Check for asymmetric downside. Positions where the upside is incremental but the downside is catastrophic deserve smaller sizing regardless of conviction. The expected value of a position with unlimited downside and capped upside is structurally unfavorable.
23. Evaluate whether the portfolio has any natural hedges against its primary tail risk. If the largest risk factor in the book is unhedged and the tail event is plausible, consider whether a small cost (buying protection, adding an offsetting position) is worth the insurance. Use `scenario-analysis` for formal stress testing of tail scenarios.
24. Assess liquidity tail risk separately from price tail risk. A position that is large relative to average daily volume becomes harder to exit precisely when exit is most needed. Illiquid positions in stress behave differently from liquid ones -- bid-ask spreads widen, depth evaporates, and the realized loss can far exceed the theoretical stop loss.

## Routing for whole-book reviews

When the query is a full portfolio risk review rather than a single-position assessment, use the smallest useful chain:

1. Complete the position-level and portfolio-level analysis above first.
2. Run `portfolio-concentration` if direct concentration and correlated clusters need deeper analysis than the portfolio-level section provides.
3. Run `cross-asset-playbook` when multiple sleeves may be expressing the same macro driver through different instruments.
4. Run `market-regime-analysis` when the current regime could change the portfolio's tolerance for gross, carry bleed, or crowded factor exposure.
5. Run `macro-event-analysis` when the next few sessions or weeks are catalyst-heavy for the book.
6. Run `scenario-analysis` if the book is concentrated, event-heavy, or dependent on one macro narrative.
7. Run `position-management` on specific positions that are already fragile, oversized, or near catalysts.
8. Run `portfolio-construction` if the book has drifted far enough that the risk architecture itself needs redesign, not just a trim.
9. Run `macro-book-sizing` before approving a meaningful new add or before calling the remaining risk budget usable.

Stop the review when the book is already too concentrated, too event-heavy, or too far outside its intended risk budget to justify additional risk.

## Core principles

Risk management is proactive, not reactive. The time to define stops, drawdown rules, and exposure limits is before the loss occurs. After the loss, emotional pressure distorts judgment and rationalizes holding, averaging down, or abandoning rules. Every risk rule should be defined before market stress arrives, then followed when markets are not calm.

Position size is the most important risk control. Stops can fail (gaps, illiquidity, overnight moves), hedges can break (correlation shifts), and diversification can collapse (regime changes). But a position that is small enough to lose entirely without impairing the portfolio always provides survival. When in doubt, size down.

The purpose of risk management is not to avoid losses -- losses are a normal and unavoidable part of trading. The purpose is to ensure that no single loss, correlated cluster of losses, or drawdown episode is large enough to impair the ability to continue trading. Survival is the prerequisite for compounding.

## Risk monitoring cadence

Risk assessment is not a one-time exercise. The analysis process above should be revisited at regular intervals and whenever material changes occur:

- Daily: check P&L, drawdown level, and whether any stop or invalidation level has been breached
- Weekly: review gross and net exposure, correlation drift, and whether positions still reflect current conviction
- After significant market moves: reassess portfolio-level risk, check whether correlation assumptions held, and evaluate whether drawdown thresholds have been reached
- After adding or removing positions: recalculate risk budget utilization and check for new concentration or correlation risks

## Evidence that would invalidate this analysis

- the portfolio composition has changed materially since the snapshot was provided
- correlation assumptions were based on a benign period that no longer applies
- the user's risk tolerance or capital base has changed significantly
- a regime shift has made historical volatility and correlation estimates unreliable
- positions have liquidity or structural features not described that change the risk profile
- the drawdown thresholds assumed do not match the actual strategy or mandate

## Output structure

Prefer this output order:

1. `Risk Summary`
2. `Position-Level Assessment`
3. `Portfolio-Level Assessment`
4. `Risk Budget Review`
5. `Drawdown Status And Rules`
6. `Tail Risk Flags`
7. `Recommended Actions`
8. `Next Skill`

Always include:

- whether the snapshot was full or partial
- whether each position has a defined invalidation point
- whether correlated positions have been identified and grouped
- gross and net exposure assessment
- current drawdown context and applicable response tier
- any tail risk or gap risk flags
- the main risk sources in the current book
- where exposures overlap or cluster
- whether upcoming catalysts or macro conditions increase portfolio fragility
- whether the next step is `macro-book-sizing`, `position-sizing`, `scenario-analysis`, `portfolio-concentration`, or `position-management`

When enough context exists for a whole-book review, carry forward a compact context block:

```markdown
## Portfolio Risk Context

- objective:
- snapshot_scope:
- gross_net_posture:
- drawdown_state:
- top_exposures:
- overlap_clusters:
- cross_asset_drivers:
- carry_profile:
- key_catalysts:
- regime_pressure:
- fragile_positions:
- planned_add:
- portfolio_constraints:
- risk_summary:
- open_questions:
- assumptions:
- next_recommended_skill:
```

Only populate the fields supported by the analysis that actually ran.

## Best practices

- do not confuse a tight stop with good risk management; a stop at the wrong level just guarantees a loss
- do not treat correlated positions as independent when computing total risk
- do not wait for a drawdown to define drawdown rules
- do not assume correlations remain stable during stress
- do not let conviction override position-level or portfolio-level risk limits
- do not treat risk management as something that happens after the trade is placed
- do not mistake mark-to-market volatility for fundamental risk without checking thesis integrity
- do not size cross-asset books in raw notional when the real constraint lives in `DV01`, `vega`, beta-adjusted notional, or carry bleed
- do not treat issuer count as diversification by itself
- do not ignore shared catalyst risk across several names
- do not approve a new trade before the book-level risk picture is explicit
- do not review a partial snapshot as if it were the whole book

## Usage examples

- "Use `risk-management` to review my portfolio risk: I am long NVDA, AMD, AVGO, and SMH with stops 8% below entry, short TLT, and have 30% cash. Total account is $200k, down 6% from peak."
- "Use `risk-management` to build a drawdown response framework for my $500k macro trading book that targets 12% annual vol."
- "Use `risk-management` to assess whether my three energy longs and one energy short are actually diversified or just one correlated energy bet."
- "Use `risk-management` on my macro book before I add more duration risk."
- "Use `risk-management` on this cross-asset book for the next two weeks and tell me where the real risk is clustered."
