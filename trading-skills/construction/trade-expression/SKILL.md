---
name: trade-expression
description: Choose the right instrument and structure for a given market view by evaluating outright, spread, options, and cross-asset expressions against conviction, time horizon, carry cost, and asymmetry. Use when a thesis exists and the task requires deciding how to express it.
---

# Trade Expression

Use this skill when a market view or thesis exists and the task requires deciding how to express it -- which instrument, structure, and format best matches the conviction level, time horizon, and risk tolerance.

This skill will not:

- validate whether the underlying thesis is correct
- provide specific strike, expiry, or sizing recommendations
- replace `position-sizing`, `macro-book-sizing`, or `risk-reward-sanity-check`
- guarantee that a clever structure compensates for a wrong view
- recommend specific products, platforms, or vendors

## Role

Act like a structuring desk that translates views into trades. Your job is to ensure the expression matches the thesis -- that a nuanced view is not expressed with a blunt instrument, and that the carry cost, risk profile, and capital efficiency of the chosen structure are understood before entry.

## When to use it

Use it when the task requires:

- deciding whether to express a view through outrights, spreads, options, or cross-asset trades
- understanding the carry cost and time decay of different expression choices
- evaluating whether buying optionality or selling it better fits the situation
- engineering asymmetry in the risk/reward profile through structure rather than prediction
- comparing capital efficiency across expression alternatives
- avoiding common mistakes like overpaying for optionality or using leverage as a substitute for conviction

## Inputs

This skill operates on:

- the thesis or market view in one to three sentences
- intended time horizon
- conviction level (high, medium, low, or uncertain)
- whether the user prefers defined risk (capped loss) or is comfortable with open-ended exposure
- any relevant context about the vol environment, funding cost, or spread levels
- whether there are upcoming catalysts with known dates

Additional context that strengthens the analysis:

- current implied vol levels or vol percentile for the underlying
- skew and term structure context
- the user's existing portfolio exposure to related risk factors
- whether the user has a preference for or experience with certain instruments

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- implied volatility surface for the relevant underlying (ATM vol, skew, term structure)
- realized volatility history for comparison to implied levels
- funding rates or carry costs for outright positions
- spread levels if the thesis involves relative value
- options chain with representative Greeks if options expressions are under consideration

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Expression hierarchy

Evaluate each expression type against the thesis before recommending one.

### Outright (long or short the asset)

Best when conviction is high, timing is reasonably clear, and the user is willing to accept full mark-to-market risk. Outrights have no structural decay, but they also offer no structural protection. The carry cost is the funding rate or opportunity cost of capital. Outrights are the simplest expression and should be the default unless there is a specific reason to add structural complexity.

### Spread (long A vs short B)

Best when the view is relative rather than directional -- the user believes A will outperform B, regardless of the direction of the broader market. Spreads isolate the specific divergence and reduce exposure to common factors. The risk is that the correlation between A and B breaks down, turning a relative value trade into two directional bets. Spreads are also appropriate when the user wants to reduce net exposure while maintaining a view.

### Options (calls or puts)

Best when timing is uncertain, the user wants defined risk, or the thesis depends on a binary catalyst with uncertain outcome. Long options provide convexity -- the ability to participate in large moves while capping the downside at the premium paid. The cost is theta decay: the position bleeds value every day the thesis does not play out. Options are appropriate when the user would rather pay a known premium than manage an open-ended stop.

### Option spreads (verticals, calendars, diagonals)

Best when the user wants to reduce the premium cost of an options position by accepting a cap on the upside or by monetizing a view on term structure. Vertical spreads define both maximum gain and maximum loss. Calendar spreads express a view on the timing of a move or the shape of the vol term structure. Option spreads reduce the carry cost relative to outright options but add structural complexity.

### Curve and cross-asset expressions

Best when the view is about the shape of a curve (yield curve steepeners or flatteners, commodity curve plays) or the relative pricing between asset classes. These expressions require confidence in the relationship between the legs, not just the direction of either leg. They are capital-efficient but can be complex to manage.

## Decision framework

Evaluate the expression choice against these factors:

| Factor | Question |
|--------|----------|
| Conviction | How confident is the view on direction, magnitude, and timing? |
| Time horizon | How long must the expression survive before the thesis is tested? |
| Carry cost | Does the expression earn or bleed while waiting? |
| Vol environment | Is implied vol cheap, fair, or expensive relative to realized? |
| Defined risk | Is a hard cap on maximum loss required? |
| Capital efficiency | How much capital does the expression tie up relative to the potential payoff? |
| Catalyst timing | Is there a known date when the thesis will be tested? |

### Matching views to expressions

- High conviction with clear timing: outright is the cleanest expression. Adding structural complexity dilutes the payoff when the view is right.
- High conviction with uncertain timing: options provide staying power. The premium buys the right to be early without being stopped out.
- Relative value view: spread isolates the divergence. An outright position on one leg introduces unwanted market risk.
- Range-bound or mean-reversion view: short vol expressions (selling options or spreads) earn carry in the base case but require discipline about tail risk.
- Binary catalyst with asymmetric payoff: options or option spreads define the risk and let the structure do the work.
- View on curve shape or cross-asset relationship: curve or cross-asset expression. Outrights on individual legs introduce directional noise.

## Carry cost of expressions

Every expression has a carry profile -- what is earned or paid for holding the position if nothing changes.

- Long outright: funding cost (borrowing rate, opportunity cost of capital). In some assets, positive carry from dividends, coupons, or backwardation offsets this.
- Short outright: earn the asset's yield but pay borrowing costs and face unlimited upside risk.
- Long options: negative carry from theta decay. The position loses value every day the move does not happen.
- Short options: positive carry from theta collection. The position earns each day but bears tail risk.
- Spreads: carry depends on the relative carry of each leg. Well-constructed spreads can be carry-neutral.

The carry profile determines urgency. Negative carry expressions require a catalyst within the time horizon to justify the bleed. Positive carry expressions can afford to wait but must respect the tail risk they are bearing.

## Asymmetry engineering

The goal of structuring is not just to express a view but to create a risk/reward profile where the potential gain significantly exceeds the potential loss relative to probability. Structure creates asymmetry independent of prediction accuracy:

- Buying options when vol is cheap creates convexity at a low cost
- Selling options when vol is expensive earns carry with favorable odds
- Spreads that isolate a specific mispricing remove unrewarded risk from the expression
- Calendar spreads that buy cheap long-dated vol and sell expensive short-dated vol benefit from term structure normalization

Asymmetry is not free. It comes from accepting some constraint -- a cap on upside, a time limit, or a narrower payoff range. The skill is choosing which constraint is tolerable given the thesis.

## Common mistakes

- Expressing a nuanced view with a blunt instrument. A relative value thesis expressed as an outright long on one leg introduces unwanted market risk.
- Overpaying for optionality. Buying options when implied vol is at the 90th percentile means paying for protection that is already expensive. Check `vol-framework` for vol context.
- Confusing leverage with conviction. Using options or futures for leverage rather than for structural reasons increases risk without improving the thesis.
- Ignoring carry cost. A long options position on a thesis that takes six months to play out may bleed away the entire premium before the catalyst arrives.
- Defaulting to complexity. If the view is simple and conviction is high, an outright position is often the best expression. Structure should serve the thesis, not demonstrate sophistication.
- Failing to match time horizon to instrument. Short-dated options on a long-horizon thesis will expire before the thesis is tested. Long-dated options on a short-term catalyst overpay for time value.

## Evidence that would invalidate this analysis

- the conviction level or time horizon changes materially after the expression is chosen
- the vol environment shifts enough to change the relative attractiveness of options vs outrights
- correlation between spread legs breaks down, invalidating the relative value premise
- liquidity in the chosen instrument deteriorates, changing the execution cost assumptions
- the thesis itself changes in a way that requires a different expression entirely

## Output structure

Prefer this output order:

1. `Thesis Summary`
2. `Expression Options` (evaluate two to three alternatives)
3. `Recommended Expression`
4. `Carry Profile`
5. `Asymmetry Assessment`
6. `Key Risks Of This Structure`
7. `Next Skill`

Always include:

- the thesis restated in one sentence
- at least two expression alternatives with trade-offs
- the carry cost of the recommended expression
- what the expression earns or loses if the thesis takes longer than expected
- whether the next step is `risk-reward-sanity-check`, `macro-book-sizing`, `position-sizing`, or `vol-framework`

## Best practices

- do not recommend complex structures when a simple outright serves the thesis equally well
- do not ignore carry cost when recommending long options positions
- do not treat options as "free" leverage; the premium is a real cost
- do not assume the user understands Greeks without checking
- do not recommend selling options without explicitly addressing tail risk
- do not confuse capital efficiency with permission to oversize; move next to `macro-book-sizing` when book risk is the real question

## Usage examples

- "Use `trade-expression` for my thesis that the yield curve will steepen over the next three months as the front end rallies more than the long end."
- "Use `trade-expression` to decide whether I should buy puts, buy a put spread, or short the stock to express my bearish view on XYZ ahead of earnings in two weeks."
- "Use `trade-expression` to evaluate how to express a long copper vs short gold relative value view with a six-month horizon."
