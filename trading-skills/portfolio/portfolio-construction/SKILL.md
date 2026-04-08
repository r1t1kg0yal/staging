---
name: portfolio-construction
description: Build a portfolio from scratch or restructure an existing book by allocating risk budget across themes, balancing factor exposures, controlling gross and net, and selecting positions that provide real diversification. Use when the task requires constructing or redesigning a trading book, not just reviewing concentration.
---

# Portfolio Construction

Use this skill when the task requires building a portfolio from scratch, restructuring an existing book, or evaluating whether a current portfolio is constructed intentionally rather than accumulated by accident.

This skill will not:

- recommend specific securities or assets to buy
- replace individual trade thesis validation or research
- build a passive wealth management allocation or retirement plan
- guarantee that a well-constructed portfolio will be profitable
- provide rebalancing on a fixed calendar without thesis review

## Role

Act like a portfolio manager constructing a macro trading book. Your job is to ensure the portfolio has an intentional risk architecture -- that every position earns its place, that the overall factor and exposure profile is deliberate, and that the book can survive being wrong on any single idea.

## When to use it

Use it when the task requires:

- building a new trading book from a set of ideas and a risk budget
- restructuring an existing portfolio that has grown organically without a clear framework
- evaluating whether the current book has the right balance of directional and relative value positions
- checking whether factor exposures (carry, value, momentum) are intentional or accidental
- deciding how to allocate risk budget across themes and asset classes
- assessing whether the portfolio's gross and net exposure match the intended risk profile

## Inputs

This skill operates on:

- total capital and risk budget (max drawdown tolerance or target volatility)
- current holdings if restructuring, with approximate sizes and directions
- the set of trade ideas or themes to be expressed
- conviction level for each idea (high, medium, low)
- preferred time horizon for the overall book
- whether the book is directional, relative value, or mixed
- any constraints (max single position size, sector limits, leverage limits, liquidity requirements)

Additional context that strengthens the analysis:

- correlation estimates between positions or themes
- factor exposure tags (which positions carry positive carry, which are value plays, which are momentum-driven)
- historical performance or drawdown data for the current book
- benchmark or peer comparison if relevant

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- total capital and stated risk budget or drawdown tolerance
- current holdings with sizes, directions, and entry rationale if restructuring
- correlation estimates or factor tags for key positions
- gross and net exposure breakdown by asset class
- carry profile of existing or planned positions (which earn carry, which bleed)
- any hard constraints (regulatory, mandate, liquidity, leverage limits)

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Analysis process

### Risk budget architecture

1. Start from the total risk budget. This is the maximum drawdown or volatility the user is willing to tolerate. Everything downstream follows from this number. If no risk budget is stated, establishing one is the first task.
2. Allocate the risk budget across themes or macro views, not individual positions. A theme might be "long US tech on AI capex" or "short duration on sticky inflation." Each theme receives a share of the total risk budget based on conviction and edge quality.
3. Within each theme, allocate to individual positions. The best idea within a theme gets the largest share. Lower-conviction ideas within the same theme get smaller allocations or are expressed through less capital-intensive structures.
4. Reserve unallocated risk capacity. A fully invested book with no reserve forces exits from existing positions to pursue new opportunities. Maintaining 20-30% unallocated risk capacity is a reasonable base case for a trading book.

### Factor exposure design

5. Map each position to the carry, value, and momentum framework from `trader-thinking`. A well-constructed book should have conscious exposure to these factors, not accidental tilts. If positions cannot be tagged with their primary factor driver, the portfolio's factor profile is unknown and should be mapped before proceeding.
6. Check whether the portfolio is overloaded on one factor. A book that is entirely momentum-driven will suffer in a regime change. A book that is entirely value-driven may underperform for extended periods. A book that is entirely carry-driven earns steady income but bears tail risk. Diversification across factors provides resilience across regimes.
7. Identify positions where carry, value, and momentum align -- these are the highest-conviction positions and should receive the most risk budget. Positions where the factors conflict deserve smaller sizing and closer monitoring.
8. Assess the portfolio's aggregate carry. Sum the carry contribution of all positions to determine whether the book earns or bleeds while theses develop. A portfolio with significant negative aggregate carry requires catalysts to arrive within the holding period to avoid erosion of capital. A portfolio with positive aggregate carry can afford to be patient but must respect the tail risks that generate that carry.

### Gross and net exposure

9. Set gross exposure intentionally. Gross is the sum of all long and short exposure as a percentage of capital. Higher gross amplifies returns but also amplifies losses and reduces the portfolio's shock-absorption capacity. Gross exposure should reflect the quality of the opportunity set, not a fixed target.
10. Set net exposure intentionally. Net is longs minus shorts as a percentage of capital. A net long book has directional equity-like risk. A net flat book isolates relative value. The choice should reflect the macro view and risk mandate, not accidental drift from winners and losers.
11. Define when to adjust gross and net. Gross should decrease when opportunity quality declines, when correlations are rising, or when drawdown thresholds are approached. Net should reflect current directional conviction, adjusted for regime and risk tolerance.
12. Track gross and net by asset class, not just in aggregate. A book that is gross 150% in equities and 20% in rates has a very different risk profile from one that is gross 85% in each. Asset class decomposition reveals where the risk is actually concentrated.

### Diversification that works

13. Distinguish real diversification from holding many correlated positions. Five long positions in the same sector provide ticker diversification but not risk diversification. Real diversification means the positions respond to different risk factors.
14. Use correlation awareness to select positions. When adding a new position, ask: "does this add a new source of return, or does it just increase exposure to a risk factor the book already owns?" Use `portfolio-concentration` for detailed overlap analysis.
15. Include positions that are expected to perform well in different scenarios. A portfolio that only works in a risk-on environment is a concentrated bet on risk appetite, regardless of how many positions it holds.

### Top-down vs bottom-up

Two valid approaches exist, and most traders use a blend:

- Top-down: the macro view drives asset class allocation first (overweight equities, underweight bonds, long commodities), then the best ideas within each class fill the allocation. This ensures the portfolio's overall positioning reflects a coherent macro thesis.
- Bottom-up: the best individual ideas are selected first, then the portfolio is checked for unintended factor or sector tilts. This ensures each position earns its place on individual merit.

The risk is that pure top-down forces weak ideas into the portfolio to fill an allocation, and pure bottom-up creates unintended macro bets. Check the portfolio from both directions.

### Relative value vs directional balance

16. Evaluate the balance between outright directional positions and relative value pairs. Directional positions provide the potential for large absolute returns but bear full market risk. Relative value positions isolate specific divergences and are less sensitive to broad market moves but have lower absolute return potential.
17. A portfolio that is entirely directional is making a concentrated bet on market direction. A portfolio that is entirely relative value may underperform when markets trend strongly. The blend should reflect where the analytical advantage is strongest.

### Rebalancing framework

18. Define when to rebalance based on thesis and risk, not calendar. Rebalancing triggers should include: a position has drifted beyond its intended risk allocation, the thesis behind a position has changed, correlation structure has shifted materially, or the portfolio has hit a drawdown threshold that requires gross reduction.
19. Do not automatically trim winners and add to losers. "Mean-reversion rebalancing" assumes the original weights were optimal and that deviations are noise. In a trading book, a winner may be winning because the thesis is playing out -- cutting it mechanically is counterproductive. Rebalancing should be thesis-driven.
20. Reassess construction when the macro regime changes. A portfolio built for a risk-on, low-vol environment may be poorly suited for a tightening cycle or a liquidity withdrawal. Regime changes require reviewing the entire construction, not just individual positions.

## Evidence that would invalidate this analysis

- the user's risk budget or drawdown tolerance changes materially
- correlation assumptions were based on a period that no longer represents current market conditions
- the macro regime has shifted enough that factor exposure targets should change
- one or more core theses have been invalidated, requiring position removal rather than rebalancing
- the user's capital base, leverage constraints, or liquidity requirements have changed
- the opportunity set has changed enough that the original theme allocation no longer reflects relative conviction

## Output structure

Prefer this output order:

1. `Portfolio Construction Summary`
2. `Risk Budget Allocation`
3. `Factor Exposure Map`
4. `Gross And Net Targets`
5. `Diversification Assessment`
6. `Rebalancing Triggers`
7. `Open Questions`
8. `Next Skill`

Always include:

- total risk budget and how it is allocated across themes
- factor exposure profile (carry, value, momentum balance)
- gross and net exposure targets with rationale
- whether diversification is real or superficial
- rebalancing triggers that are thesis-driven, not calendar-driven
- whether the next step is `risk-management`, `scenario-analysis`, `macro-book-sizing`, `position-sizing`, or `trade-expression`

## Best practices

- do not fill allocation slots with weak ideas just to diversify
- do not treat gross exposure as a fixed number; it should reflect opportunity quality
- do not assume more positions means better diversification
- do not rebalance mechanically without checking whether theses have changed
- do not ignore the carry cost of the overall portfolio
- do not construct a book that only works in one macro regime
- do not translate theme budgets into raw notional without first normalizing the relevant risk units

## Usage examples

- "Use `portfolio-construction` to build a macro trading book from these five themes: long US tech on AI capex, short duration on sticky inflation, long Japan equities on corporate reform, short EUR/USD on rate differentials, long gold on central bank demand. Total capital $1M, max drawdown tolerance 15%."
- "Use `portfolio-construction` to restructure my current book. I have 12 positions that accumulated over six months without a clear framework. Help me evaluate whether this is a coherent portfolio or a collection of trades."
- "Use `portfolio-construction` to check whether my portfolio has any factor exposure to carry, value, and momentum or is entirely a momentum bet."
