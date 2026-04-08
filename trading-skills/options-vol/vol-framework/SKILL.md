---
name: vol-framework
description: A thinking framework for interpreting volatility surfaces, assessing implied vs realized vol, reading vol regime signals, and using vol information in trading decisions. Use when the task requires understanding what the vol market is signaling, not computing Greeks or pricing options mechanically.
---

# Vol Framework

Use this skill when the task requires interpreting volatility as a market signal -- what the vol surface reveals about expectations, fear, and positioning -- and how to use that information in trade construction and risk assessment.

This skill will not:

- compute option prices or Greeks mechanically
- replace a proper options pricing model
- prescribe specific options to buy or sell
- guarantee that buying cheap vol or selling expensive vol is profitable
- provide real-time vol surface data

## Role

Act like a volatility-focused trader who reads the vol surface the way a macro trader reads the yield curve -- as a map of market expectations, not just a pricing input. Your job is to interpret what the vol market is saying and how that should inform trading decisions.

## When to use it

Use it when the task requires:

- understanding what implied vol levels are signaling about market expectations
- assessing whether options are cheap or expensive relative to realized vol history
- interpreting skew, term structure, or vol surface shape for trading signals
- deciding whether to buy or sell optionality in the current environment
- using vol information to inform timing or expression choices for non-options trades
- understanding the carry implications of long vs short vol positions

## Inputs

This skill operates on:

- the underlying asset or market being analyzed
- current implied vol level (ATM vol for the relevant tenor) if available
- any context on recent realized vol
- whether the context involves an options trade or vol is being used as an input for a different expression
- relevant time horizon
- any upcoming catalysts that might affect vol pricing

Additional context that strengthens the analysis:

- full vol surface data (ATM vol by tenor, skew by tenor)
- vol percentile or rank relative to history
- recent realized vol over multiple windows (20-day, 60-day, 90-day)
- options chain with representative Greeks

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- implied volatility surface: ATM vol across tenors, 25-delta risk reversals (skew), and 25-delta butterflies (smile curvature)
- realized volatility history: close-to-close realized vol computed over 20-day, 60-day, and 90-day windows
- vol percentile data: where current implied vol ranks relative to its own one-year or two-year history
- options chain with Greeks for specific structures under consideration
- event calendar: earnings dates, data releases, central bank meetings, and other catalysts that affect vol pricing

If the full vol surface is unavailable, the analysis can proceed with ATM vol and a rough sense of skew direction, but precision will be lower. If specific data is unavailable, proceed with what is available and note the gap in the output.

## Vol surface interpretation

The vol surface encodes the market's expectations about future uncertainty across strikes and expiries. Reading it correctly is the foundation of vol-informed trading.

### ATM implied vol

ATM vol represents the market's expectation of the magnitude of future price moves over a given period. Higher ATM vol means the market expects larger moves; lower ATM vol means the market expects smaller moves. ATM vol does not predict direction -- it prices the expected size of the move regardless of sign.

Context matters more than level. ATM vol of 20% is high for a utility stock and low for a biotech. Always compare the current level to the asset's own history, not to other assets.

### Skew (risk reversals)

Skew measures the difference in implied vol between out-of-the-money puts and out-of-the-money calls. In equity markets, skew is typically negative (puts are more expensive than calls), reflecting structural demand for downside protection.

What skew tells you:

- Steep negative skew: strong demand for downside protection. The market is willing to pay a premium for puts, signaling fear or hedging demand. This can indicate crowded positioning vulnerable to a short squeeze on the upside.
- Flat or positive skew: unusual in equities. May signal call demand from speculative positioning or corporate activity. In commodities, positive skew (calls more expensive) is more common and reflects supply disruption risk.
- Skew changes matter more than levels. A rapid steepening of skew signals a shift in positioning or sentiment that may precede a directional move.

### Term structure

The vol term structure shows how ATM implied vol varies across expiries. It reflects the market's view of when uncertainty is concentrated.

- Normal (upward-sloping): longer-dated vol is higher than shorter-dated vol. This is the typical shape, reflecting greater uncertainty over longer horizons. The market sees no unusual near-term risk.
- Inverted (downward-sloping): shorter-dated vol is higher than longer-dated vol. This signals a near-term event or stress that the market expects to resolve. Common ahead of earnings, elections, or central bank decisions.
- Flat: similar vol across tenors. This can signal regime uncertainty where the market is unsure whether near-term stress will persist or resolve.

An inverted term structure ahead of a known catalyst (earnings, FOMC) is normal and expected. An inverted term structure without an obvious catalyst is a warning signal that deserves investigation.

## Implied vs realized vol

The relationship between implied vol (what the market expects) and realized vol (what actually happened) is the central metric for assessing whether options are cheap or expensive.

### Variance risk premium

Implied vol is structurally higher than realized vol on average. This gap -- the variance risk premium -- exists because investors are willing to pay for protection against uncertainty. Short vol strategies earn this premium over time but bear tail risk during the periods when realized vol spikes above implied.

- When implied vol significantly exceeds realized vol: options are "expensive" relative to recent history. This favors vol sellers, but only if the conditions that justify elevated vol are expected to subside. Selling vol into a genuine regime change because "IV is high relative to RV" is a common and costly mistake.
- When implied vol is near or below realized vol: options are "cheap." This favors vol buyers, especially if there are catalysts ahead that could drive realized vol higher. Cheap vol before a known event is a potential opportunity; cheap vol in a quiet market may just reflect accurately low uncertainty.

### Comparing windows

Match the implied vol tenor to the realized vol window:

| Implied Tenor | Compare To | What It Tells You |
|---------------|------------|-------------------|
| 1-month implied | 20-day realized | Whether near-term options are pricing more or less move than recent history |
| 3-month implied | 60-day realized | Whether medium-term options reflect the recent vol regime |
| 6-month implied | 90-day realized | Whether longer-dated options embed a premium beyond recent experience |

A persistent gap where implied exceeds realized across all tenors suggests a structural demand for protection. A gap where realized exceeds implied suggests the market is underpricing current volatility.

## Vol as regime indicator

Vol levels and vol surface shape provide information about the market regime even for traders who never trade options.

- Compressed vol before a catalyst: the market is coiled. Positioning is complacent, and the move when it comes may be larger than implied because the market is caught offside. Watch for vol compression below the 20th percentile ahead of known catalysts.
- Elevated vol during transitions: uncertainty about the regime itself, not just the next data point. Elevated vol with a normal term structure suggests persistent uncertainty. Elevated vol with an inverted term structure suggests a specific event is driving the fear.
- Vol term structure inversion without a known catalyst: the market is pricing near-term stress that may not be visible in headlines. This is an early warning signal that deserves attention.

### Vol percentile and rank

Where current implied vol sits relative to its own history provides a quick read on whether the market is pricing unusual uncertainty.

- Below the 20th percentile: historically cheap. The market is pricing low uncertainty. This is a favorable environment for buying options if catalysts are ahead, but it can persist for extended periods in calm markets.
- 20th to 80th percentile: normal range. Vol is not providing a strong signal in either direction.
- Above the 80th percentile: historically elevated. The market is pricing significant uncertainty. This is a favorable environment for selling vol if the stress is expected to resolve, but selling into a genuine crisis or regime change is dangerous.

Percentile is necessary but not sufficient. Vol can remain cheap or expensive for longer than expected. Percentile identifies where the opportunity might exist; thesis and catalyst analysis determine whether it is actionable.

## Vol and carry

Volatility positions have explicit carry profiles that connect directly to the carry lens in `trader-thinking`.

- Short vol (selling options, selling straddles/strangles): earns positive carry through theta collection. Every day that passes without a large move, the position profits. The carry is compensation for bearing tail risk -- the risk of a move large enough to overwhelm the cumulative theta earned.
- Long vol (buying options, buying straddles/strangles): pays negative carry through theta decay. Every day that passes without a move, the position loses value. The cost is the price of convexity -- the ability to profit from a large move in either direction.
- Vol spreads (calendars, diagonals): can be constructed to be carry-neutral or carry-positive while expressing a view on term structure shape or the timing of a vol event.

The carry profile determines the urgency of the position. Short vol can afford to wait but must respect tail risk. Long vol must be right about the timing or the catalyst to overcome the bleed.

## Vol surface signals for trade expression

Vol surface information should inform expression choices even for non-options trades. Use `trade-expression` for the full expression decision.

- Steep skew: put demand is high, making outright puts expensive. Consider put spreads to reduce the premium cost, or express the bearish view through a short outright if conviction and risk tolerance support it.
- Flat term structure: no significant event premium in the near term. Calendar spreads that rely on term structure normalization are less attractive.
- Inverted term structure ahead of a catalyst: near-term options embed event premium. Consider selling near-term vol and buying longer-dated vol if the view is that the event resolves uncertainty.
- Cheap vol (low percentile): favorable for buying options. Long vol expressions are structurally cheaper. Outright options become more attractive relative to outrights.
- Expensive vol (high percentile): favorable for selling options if the vol is expected to compress. Consider defined-risk short vol expressions like iron condors or credit spreads.

## Evidence that would invalidate this analysis

- the vol data used was stale or from a period that no longer reflects current market conditions
- a regime change has occurred that makes historical vol comparisons unreliable
- the structural demand for options in this market has changed (new hedging mandates, index inclusion, regulatory changes)
- a catalyst that was driving elevated vol has been resolved or postponed
- liquidity in the options market has deteriorated, making the quoted vol surface less reliable

## Output structure

Prefer this output order:

1. `Vol Regime Summary`
2. `Surface Interpretation` (ATM, skew, term structure)
3. `Implied Vs Realized Assessment`
4. `Vol Percentile Context`
5. `Carry Implications`
6. `Trade Expression Signals`
7. `Next Skill`

Always include:

- current vol regime classification (compressed, normal, elevated, crisis)
- whether implied vol is rich or cheap relative to realized
- what skew and term structure signal about positioning and expectations
- carry implications for long vs short vol positions
- how the vol environment should inform the expression choice
- whether the next step is `trade-expression`, `risk-management`, or `trader-thinking`

## Best practices

- do not treat implied vol in isolation; always compare to realized vol and historical context
- do not assume cheap vol is automatically a buy or expensive vol is automatically a sell
- do not ignore skew and term structure; ATM vol alone is an incomplete picture
- do not sell vol into a genuine regime change because "IV is high"
- do not buy vol without a catalyst or thesis about what will drive realized vol higher
- do not confuse vol percentile rank with a timing signal; cheap vol can stay cheap

## Usage examples

- "Use `vol-framework` to interpret the current SPX vol surface. ATM 1-month vol is 14%, 20-day realized is 11%, skew is steep, and term structure is inverted around the FOMC date."
- "Use `vol-framework` to assess whether AAPL options are cheap or expensive ahead of earnings, given that 1-month implied is at the 35th percentile and earnings are in two weeks."
- "Use `vol-framework` to help me understand what the vol term structure inversion in crude oil is signaling about near-term supply risk."
