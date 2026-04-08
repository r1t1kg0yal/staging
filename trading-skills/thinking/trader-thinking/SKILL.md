---
name: trader-thinking
description: >-
  Teaches a structured trader mental model for analyzing markets: start from
  consensus (what is priced in), identify divergence (where your view differs),
  and structure an expression. Uses carry, value, and momentum as core lenses.
  Use when the user asks about trade ideas, market analysis, what is priced in,
  consensus views, positioning, or how to think about a macro or single-name
  trade setup.
---

# Trader Thinking Framework

A professional trader does not start from "I think X will happen." A professional trader starts from "the market thinks X will happen" and then asks "where am I different, why, and how do I express it?"

This skill encodes that mental model.

## The Core Loop

```
  ┌──────────────────┐
  │  1. CONSENSUS    │  What does the market already expect?
  │     (Priced In)  │  Surveys, forwards, options, positioning, estimates
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  2. LENS         │  Carry, Value, Momentum
  │     (Analyze)    │  What do the systematic factors say?
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  3. DIVERGENCE   │  Where is my view different from consensus?
  │     (Edge)       │  What do I see that the market is mispricing?
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  4. STRUCTURE    │  How do I express the divergence?
  │     (Trade)      │  Instrument, sizing, timing, asymmetry
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  5. INVALIDATION │  What would prove me wrong?
  │     (Risk)       │  Kill criteria, stop logic, time decay
  └──────────────────┘
```

Always work top-down. Never skip to structure without establishing consensus first.

## Step 1: Establish Consensus (What Is Priced In)

Before forming any view, map what the market already expects. The market's expectation is embedded across multiple surfaces -- no single source is sufficient.

### Consensus Surfaces

| Surface | What It Tells You | Examples |
|---------|-------------------|----------|
| **Forwards / Futures** | Expected path of rates, FX, commodities | Fed funds futures imply 3 cuts by Dec; oil curve in backwardation |
| **Options / Implied Vol** | Expected magnitude and direction of moves | SPX implied move for FOMC is 1.2%; put skew elevated |
| **Surveys** | Economist and fund manager consensus | Bloomberg survey median CPI 3.1%; AAII bulls at 45% |
| **Analyst Estimates** | Earnings and revenue expectations | NVDA consensus EPS $0.85, whisper $0.92 |
| **Positioning Data** | Where money is actually allocated | CFTC net short EUR; GS Prime shows HFs max long tech |
| **Credit / Vol Markets** | Risk appetite and tail expectations | IG spreads tight at 85bp; VIX term structure in contango |
| **Price Action** | What has already moved and been absorbed | SPX rallied through CPI, suggesting dovish interpretation priced |

### How to Synthesize Consensus

Do not just list data points. Construct a narrative:

> "The market is pricing [X scenario] as the base case, evidenced by [forwards showing A], [options implying B], [positioning at C]. The consensus surprise would be [Y]."

Key questions:
- What is the market's base case scenario?
- How confident is the market in that scenario? (low vol = high confidence)
- What would genuinely surprise the market vs. what is already discounted?
- Where is consensus most fragile (tight dispersion, extreme positioning)?

### Consensus Fragility Signals

Fragile consensus = opportunity. Look for:
- Very low dispersion in survey forecasts (everyone agrees)
- Extreme positioning in one direction
- Vol compression before a catalyst
- Price insensitivity to contrary data (market ignoring disconfirming evidence)

## Step 2: Apply the Lenses (Carry, Value, Momentum)

These three factors are the workhorse toolkit of systematic and discretionary macro. Each answers a distinct question.

### Carry

**Question: What do I earn (or pay) for holding this position over time?**

Carry is the return you receive if nothing changes. It is the market's compensation for bearing risk or providing liquidity.

| Asset Class | Carry Signal |
|-------------|-------------|
| FX | Interest rate differential between currencies |
| Rates | Roll-down on the yield curve (buy steep part, earn as it rolls) |
| Commodities | Curve shape: backwardation = positive carry, contango = negative |
| Equities | Dividend yield minus funding cost; earnings yield vs. risk-free |
| Credit | Spread over risk-free rate (compensation for default risk) |
| Vol | Short vol earns carry if realized < implied (variance risk premium) |

Carry is your "paid to wait" signal. High carry means you earn while the thesis develops. Negative carry means the position bleeds if nothing happens -- requiring a catalyst with urgency.

### Value

**Question: Is the asset cheap or expensive relative to a fundamental anchor?**

Value compares the current price to where fundamentals suggest it should trade. The anchor varies by asset class.

| Asset Class | Value Anchor |
|-------------|-------------|
| FX | PPP, REER, terms of trade, productivity-adjusted fair value |
| Rates | R-star, Taylor rule, inflation breakeven decomposition |
| Commodities | Marginal cost of production, inventory levels vs. history |
| Equities | P/E vs. growth, EV/EBITDA vs. sector, FCF yield vs. bond yield |
| Credit | Spread vs. default probability implied by fundamentals |
| Vol | Implied vol vs. realized vol; vol percentile rank |

Value is necessary but not sufficient. Cheap assets can stay cheap. Value identifies WHERE the mispricing exists; carry and momentum help with WHEN.

### Momentum

**Question: What is the trend, and is it accelerating or decelerating?**

Momentum captures the tendency of assets that have been moving in a direction to continue. It is the market's revealed preference.

Types of momentum:
- **Price momentum**: Trend in the asset price itself (moving averages, breakouts)
- **Fundamental momentum**: Direction of earnings revisions, economic surprises, policy shifts
- **Flow momentum**: Persistent buying/selling pressure (fund flows, central bank operations)
- **Cross-asset momentum**: Confirmation or divergence across related markets

Momentum is the timing signal. It tells you whether the value or carry thesis is being recognized by the market now or still fighting the tape.

### Combining the Lenses

The strongest setups occur when all three align:

```
  CARRY   VALUE   MOMENTUM   →   Signal Strength
  ──────────────────────────────────────────────
    +       +        +       →   Strongest (all confirming)
    +       +        -       →   Early / contrarian (painful but high payoff)
    -       +        +       →   Momentum-driven (watch carry bleed)
    +       -        +       →   Yield chase (late cycle, fragile)
    -       -        +       →   Pure trend-following (no fundamental anchor)
    +       -        -       →   Carry trap (value deteriorating)
```

When carry and value agree but momentum opposes, you are early. The question becomes: what catalyst closes the gap?

## Step 3: Identify the Divergence (Your Edge)

A trade requires a view that differs from consensus. If your view matches what is priced in, there is no trade -- you are just buying consensus at consensus prices.

### Divergence Sources

| Source | Description |
|--------|-------------|
| **Data interpretation** | Same data, different conclusion (e.g., "this CPI print looks hot but the composition is benign") |
| **Weight of evidence** | Market overweights one signal, underweights another |
| **Time horizon mismatch** | Market is pricing the next 3 months; your thesis is about the next 12 |
| **Structural blind spots** | Systematic flows creating dislocations (index rebalance, forced selling, regulatory constraints) |
| **Second-order effects** | Market prices the direct effect but misses the transmission channels |
| **Regime change** | Market is using the wrong model for the current environment |

### Articulating the Divergence

Be precise. State it as:

> "Consensus expects [X]. I expect [Y] because [evidence]. The gap will close when [catalyst]. My time horizon is [T]."

If you cannot fill in all four blanks, the trade idea is not ready.

### Conviction Calibration

Not all divergences deserve the same sizing:

| Conviction Level | Characteristics | Typical Sizing |
|-----------------|-----------------|----------------|
| **High** | Multiple confirming signals, clear catalyst, carry supports, positioning offside | Full position |
| **Medium** | Good thesis but catalyst timing uncertain, or one lens opposes | Half position |
| **Low** | Interesting divergence but evidence is thin or timing is ambiguous | Starter / option expression |

## Step 4: Structure the Expression

The same view can be expressed in radically different ways. Structure determines the risk/reward profile.

### Expression Hierarchy

Choose the instrument that best matches your conviction, time horizon, and risk tolerance:

| Expression | When to Use |
|-----------|------------|
| **Outright** (long/short the asset) | High conviction, clear timing, willing to take mark-to-market risk |
| **Spread** (long A vs. short B) | Relative value view, want to isolate the specific divergence |
| **Options** (calls/puts) | Timing uncertain, want defined risk, or paying for asymmetry |
| **Option spreads** (verticals, calendars) | Reduce premium cost, express a range-bound or directional view with cap |
| **Curve / cross-asset** | View is about shape or relative pricing, not direction |

### Asymmetry Checklist

Good trade structure creates asymmetry -- limited downside, significant upside relative to the probability:

- What is the most I can lose? (define max risk)
- What is the realistic upside if the thesis plays out?
- What is the payoff if nothing happens? (carry: positive or negative?)
- Am I paying for optionality or earning it?
- Does the structure survive being early by [N weeks/months]?

## Step 5: Define Invalidation

Every trade needs explicit kill criteria. Invalidation is not "I lost money." Invalidation is "the thesis is broken."

### Invalidation Framework

| Type | Question |
|------|----------|
| **Data invalidation** | What data release would disprove my thesis? |
| **Price invalidation** | At what level does the market's message override my view? |
| **Time invalidation** | If the catalyst hasn't arrived by [date], is the thesis still valid? |
| **Regime invalidation** | Has the macro/policy regime shifted enough to void the setup? |

Write these down BEFORE entering the trade. Revisit them only with new information, not with new emotions.

## Applying This Framework

When the task involves a market question, trade idea, or analysis request:

1. **Do not lead with an opinion.** Lead with consensus: "Here is what the market is currently pricing for X..."
2. **Map the lenses.** What do carry, value, and momentum say about X?
3. **Identify divergence.** Where might the market be wrong? What is underappreciated?
4. **Propose structure.** If there is a divergence worth expressing, how would you structure it?
5. **Define invalidation.** What breaks the thesis?

If there is no clear divergence from consensus, say so. "The market seems roughly correctly priced" is a valid and useful conclusion. Not every analysis produces a trade.

## Anti-Patterns

- Starting with "I think X will happen" without first establishing what is priced in
- Confusing a narrative with a trade (story is not edge)
- Ignoring carry cost (negative carry trades need a catalyst with urgency)
- Treating value alone as a timing signal (cheap can get cheaper)
- Conflating confidence with conviction (loud is not the same as calibrated)
- Expressing a nuanced view with a blunt instrument (directional outright for a relative value idea)
- No invalidation criteria (every position becomes a "long-term hold" when it goes against you)
- Anchoring to entry price instead of current information
