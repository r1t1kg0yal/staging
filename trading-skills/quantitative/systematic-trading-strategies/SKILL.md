---
name: systematic-trading-strategies
description: Design and evaluate systematic trading strategies -- signal construction, portfolio formation, execution rules, and performance evaluation. Covers momentum, mean-reversion, breakout, trend-following, and statistical arbitrage across asset classes. Use when building or assessing a rules-based trading system from signal to execution.
---

# Systematic Trading Strategies

Use this skill when the task is to design, evaluate, or improve a systematic (rules-based) trading strategy. This covers the full pipeline from signal definition through portfolio construction to execution and performance evaluation. It applies across asset classes and strategy types: momentum, mean-reversion, trend-following, breakout, statistical arbitrage, and systematic macro.

This skill will not:

- replace discretionary judgment about market context (use `trader-thinking` and `market-regime-analysis` for that)
- perform backtests computationally (use `backtesting-methodology` for backtest design and the user's backtesting tools for execution)
- guarantee that backtested performance continues in live trading
- build the data pipeline (it assumes the user has or can obtain the necessary data)

## Role

Act like a quantitative strategist who designs systematic trading systems. You think in terms of signal, portfolio construction, and execution as distinct modules. You understand that most systematic strategy failures come from overfitting, transaction cost underestimation, and regime dependence -- not from bad signals. You evaluate strategies with skepticism, not optimism.

## When to use it

Use it when the task requires:

- designing a new systematic strategy from scratch (signal definition, portfolio rules, execution logic)
- evaluating an existing strategy's signal quality, turnover, capacity, and robustness
- choosing between strategy types (momentum vs mean-reversion vs trend-following) for a given asset class
- understanding signal decay, holding period optimization, and turnover management
- combining multiple signals into a composite (multi-factor, multi-signal blending)
- assessing strategy capacity and scalability
- feeding strategy design into `backtesting-methodology` for testing or `factor-investing` for systematic factor implementation

## Strategy taxonomy

### Momentum / trend-following
- **Signal:** price momentum (returns over lookback window), moving average crossovers, breakout above/below range
- **Logic:** assets that have been going up tend to keep going up (and vice versa) over medium time horizons
- **Best in:** directional trending markets, macro regimes with persistent policy divergence
- **Worst in:** choppy, range-bound markets; regime reversals
- **Key parameters:** lookback window (typically 3-12 months), holding period, volatility scaling

### Mean-reversion
- **Signal:** deviation from fair value, Z-score of spread vs history, Bollinger band extremes, RSI oversold/overbought
- **Logic:** prices that deviate from equilibrium tend to revert
- **Best in:** range-bound markets, pairs/spreads with strong fundamental anchor, liquid markets with tight bid-ask
- **Worst in:** trending markets, regime changes where the "mean" itself shifts
- **Key parameters:** lookback for mean estimation, entry/exit thresholds, stop-loss (critical -- prevents riding a broken mean)

### Breakout
- **Signal:** price breaking above/below a defined range (N-day high/low, volatility channel, support/resistance)
- **Logic:** range compression precedes range expansion; breakout signals the start of a new trend
- **Best in:** markets transitioning from compression to expansion, event-driven catalysts
- **Worst in:** markets with frequent false breakouts (choppy, no follow-through)
- **Key parameters:** range definition, confirmation rules (volume, close vs intraday), stop placement

### Statistical arbitrage (stat arb)
- **Signal:** pairs or basket mean-reversion, cointegration residual, factor-neutral spread deviations
- **Logic:** related instruments that deviate from their historical relationship tend to converge
- **Best in:** liquid, correlated markets; stable relationships; short holding periods
- **Worst in:** regime changes that break relationships; illiquid markets; crowded pairs
- **Key parameters:** cointegration window, half-life of mean reversion, entry/exit Z-score, hedge ratio

### Systematic macro
- **Signal:** macro indicators (growth, inflation, policy), factor signals (carry, value, momentum), cross-asset relative value
- **Logic:** macro regimes drive asset class returns in predictable ways; systematic factor exposure captures risk premia
- **Best in:** environments with clear macro trends and persistent factor premia
- **Worst in:** regime transitions, factor crowding, sudden correlation breakdown
- **Key parameters:** factor definitions, rebalancing frequency, risk allocation, drawdown rules

## Strategy design pipeline

### 1. Signal definition
The signal is the core alpha source. It must be:
- **Measurable:** computed from observable data without future information
- **Timely:** available when the trading decision must be made
- **Predictive:** has statistical relationship to future returns (even if weak)
- **Robust:** works across multiple markets, time periods, and parameter choices (not overfit to one dataset)

**Signal construction checklist:**
- Define the raw input data (prices, fundamentals, flows, etc.)
- Define the transformation (moving average, Z-score, regression residual, etc.)
- Define the direction (positive signal = long, negative = short, or more nuanced)
- Define the signal strength (continuous score vs binary)
- Test for information decay: how quickly does the signal's predictive power decline after generation?

### 2. Portfolio construction
Convert signals into positions:

- **Position sizing:** volatility-targeted sizing (scale position inversely to recent vol) is the most common approach. Ensures equal risk contribution across positions.
- **Signal weighting:** stronger signals get larger positions. Linear scaling (position proportional to signal Z-score) or non-linear (threshold-based).
- **Cross-sectional vs time-series:** cross-sectional strategies rank assets and go long top / short bottom. Time-series strategies go long/short each asset independently based on its own signal.
- **Sector/factor neutrality:** decide whether to neutralize sector, market, or factor exposure. More neutrality = purer alpha but lower gross exposure.
- **Gross and net exposure:** total long + short (gross) and long minus short (net). Higher gross = more alpha opportunity but more cost and risk.

### 3. Execution rules
- **Entry rules:** signal threshold for entering a new position. Avoid marginal signals that generate turnover without sufficient expected return.
- **Exit rules:** signal reversal, stop-loss, time-based exit, or profit target. Always have a defined exit.
- **Rebalancing frequency:** daily, weekly, monthly. Higher frequency = more responsive but higher transaction costs.
- **Transaction cost budget:** estimate costs (bid-ask, market impact, commissions) and ensure expected alpha exceeds them.

### 4. Risk controls
- **Position limits:** maximum position size per asset (e.g., 5% of capital)
- **Sector/factor limits:** maximum exposure to any single sector or factor
- **Drawdown rules:** reduce gross exposure or de-risk when drawdown exceeds threshold
- **Turnover limits:** cap annual turnover to control transaction costs
- **Regime filters:** reduce or eliminate positions when the market regime is unfavorable for the strategy type

## Evaluation framework

Evaluate a systematic strategy on these dimensions:

### Signal quality
- **Information coefficient (IC):** correlation between signal and subsequent returns. IC of 0.05-0.10 is typical for good systematic signals.
- **IC decay:** how quickly IC declines over holding periods. Faster decay = shorter optimal holding period.
- **Breadth:** number of independent bets per period. Higher breadth (more instruments, more frequent rebalancing) compensates for low IC per bet.
- **Fundamental Law of Active Management:** IR approximately equals IC x sqrt(Breadth). A low-IC signal applied broadly can be competitive with a high-IC signal applied narrowly.

### Robustness
- **Parameter sensitivity:** does performance degrade smoothly as parameters change, or cliff-edge? Smooth degradation = robust; cliff-edge = overfit.
- **Out-of-sample performance:** how does the strategy perform on data not used for design? Walk-forward testing is mandatory.
- **Regime stability:** does the strategy perform reasonably across different market regimes (trending, range, crisis)?
- **Cross-market applicability:** does the signal work across multiple markets or asset classes? Broader applicability = less likely overfit.

### Capacity and scalability
- **Market impact:** how much would the strategy move prices when trading at target size?
- **Turnover:** annual portfolio turnover. Higher turnover = higher costs, lower capacity.
- **Liquidity:** are the instruments liquid enough to execute the strategy at scale?
- **Capacity estimate:** the maximum capital the strategy can absorb before market impact erodes returns.

### Cost-adjusted performance
- **Gross alpha:** returns before transaction costs
- **Net alpha:** returns after realistic transaction costs (bid-ask, market impact, commissions, financing)
- **Breakeven cost:** the transaction cost level at which net alpha goes to zero
- **Sharpe ratio (net):** the risk-adjusted performance metric that matters

## Analysis process

1. **Clarify the objective.** What is the user trying to build?
   - New strategy from scratch
   - Improvement to existing strategy
   - Evaluation of a specific signal
   - Combination of multiple signals

2. **Strategy type selection.** Based on the asset class, market environment, and user's edge:
   - Trending assets / macro trends: momentum, trend-following
   - Mean-reverting spreads / relative value: mean-reversion, stat arb
   - Event-driven catalysts: breakout
   - Multi-asset risk premia: systematic macro, factor investing

3. **Signal design.** Define the signal using the checklist above. Ensure it passes basic quality filters (measurability, timeliness, no look-ahead bias).

4. **Portfolio construction.** Define sizing rules, neutrality constraints, and exposure limits.

5. **Execution and cost.** Define entry/exit rules, rebalancing frequency, and estimate transaction costs.

6. **Evaluation.** Assess signal quality (IC, decay, breadth), robustness (parameter sensitivity, regime stability), and capacity.

7. **Iterate.** Identify weaknesses and propose modifications. Do not accept the first iteration as final.

## Output tables

### Strategy Summary
| Parameter | Value |
|-----------|-------|
| Strategy Type | ... |
| Signal | ... |
| Asset Class | ... |
| Lookback | ... |
| Holding Period | ... |
| Rebalancing | ... |
| Sizing Method | ... |
| Universe | ... instruments |

### Expected Performance (Backtest)
| Metric | Value |
|--------|-------|
| Gross Annual Return | ...% |
| Net Annual Return | ...% |
| Sharpe Ratio (Net) | ... |
| Max Drawdown | ...% |
| Annual Turnover | ...x |
| IC (avg) | ... |
| IC Decay (half-life) | ... periods |
| Win Rate | ...% |

### Robustness Assessment
| Test | Result | Signal |
|------|--------|--------|
| Parameter sensitivity | Smooth / Cliff-edge | Robust / Fragile |
| Out-of-sample | ...% of in-sample Sharpe | Strong / Weak |
| Regime stability | Performs in N/M regimes | Broad / Narrow |
| Cross-market | Works in N/M markets | Universal / Specific |

## Evidence that would invalidate this analysis

- the signal's alpha source is arbitraged away (too many participants, capacity exhausted)
- a structural market change (regulation, product innovation) breaks the signal
- transaction costs increase beyond the breakeven level
- the market regime shifts permanently to one unfavorable for the strategy type
- the signal was overfit to the in-sample period and degrades out-of-sample

## Output structure

Prefer this output order:

1. `Strategy Design Summary`
2. `Signal Definition`
3. `Portfolio Construction Rules`
4. `Execution And Risk Controls`
5. `Strategy Summary` (table)
6. `Performance Evaluation` (table)
7. `Robustness Assessment` (table)
8. `Improvements And Next Steps`
9. `Next Skill`

Always include:

- the signal definition in precise, implementable terms
- portfolio construction and sizing rules
- transaction cost estimate and net performance
- robustness assessment (parameter sensitivity, regime stability)
- whether the strategy should be backtested (use `backtesting-methodology`), combined with other signals, or refined

## Best practices

- most systematic strategy failures come from overfitting, not bad signals; always test out-of-sample
- transaction costs kill more strategies than bad alpha; estimate costs realistically and include market impact
- the Fundamental Law of Active Management matters: moderate IC x high breadth beats high IC x low breadth
- signal decay determines optimal holding period; do not hold positions beyond the signal's predictive horizon
- volatility-target sizing is the standard approach because it equalizes risk contribution across assets
- regime filters (reducing exposure in unfavorable regimes) improve risk-adjusted returns but reduce gross exposure
- avoid data-mining: if you tested 100 signals and picked the best one, you found noise, not alpha
- always know why the signal should work (economic rationale); signals without rationale are more likely to be spurious

## Usage examples

- "Use `systematic-trading-strategies` to design a momentum strategy for G10 FX. I want to capture trending behavior in FX crosses."
- "Use `systematic-trading-strategies` to evaluate a mean-reversion signal on Treasury 2s10s. Is the Z-score approach robust?"
- "Use `systematic-trading-strategies` to help me combine my momentum signal with a carry signal into a composite. How should I blend them?"
- "Use `systematic-trading-strategies` to assess the capacity of a stat arb strategy I backtested on US equity pairs."
