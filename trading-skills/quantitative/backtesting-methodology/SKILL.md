---
name: backtesting-methodology
description: Vendor-agnostic principles for rigorously testing trading strategies against historical data -- focused on what a backtest can and cannot prove, common biases, and when results deserve trust.
---

# Backtesting Methodology

Use this skill when the task is to test a trading strategy against historical data rigorously, or when backtest results need evaluation for trustworthiness.

This skill will not:

- recommend specific backtesting software or platforms
- provide code implementations for any particular language or framework
- claim that any backtest result predicts future performance
- substitute for forward testing or live paper trading

## Role

Act as a methodological auditor. Your job is to ensure the backtest is designed to minimize self-deception: realistic assumptions, proper data handling, honest evaluation, and clear-eyed interpretation of results.

## When to use it

Use it when the task requires:

- designing a backtest for a new strategy before running it
- evaluating whether existing backtest results are trustworthy
- identifying sources of bias in a backtest that looks "too good"
- understanding why a strategy that backtested well is failing in live trading
- pairing with `factor-investing` to test systematic factor strategies or with `risk-management` to validate risk parameters

## Data requirements

Retrieve from the data harness:

- historical price data for the strategy universe
- factor or signal data if applicable
- transaction cost estimates
- market regime indicators for period classification

If specific data is unavailable, proceed with what is available and note the gap in the output.

## What a Backtest Can and Cannot Prove

A backtest can demonstrate that a strategy **would have** generated certain returns under certain assumptions over a historical period. It cannot prove the strategy will work going forward, that the historical period is representative, that the edge is structural rather than coincidental, or that live execution will match simulation.

The value of a backtest is in **disproving** bad strategies, not in **proving** good ones. A strategy that fails in backtest is almost certainly bad. A strategy that succeeds is a candidate that deserves further scrutiny, not a validated edge.

## Data Integrity

### Survivorship bias

Testing a strategy only on assets that still exist today systematically overstates returns. Companies that went bankrupt, were delisted, or were acquired are excluded from most readily available datasets. These are precisely the names that would have generated the largest losses.

The requirement: use data that includes all securities that existed during the test period, regardless of whether they exist today.

### Look-ahead bias

Using information that was not available at the time of the simulated decision. Common sources: fundamental data with reporting lags (using Q1 earnings as of March 31 when reported in May), corporate action adjustments known only after the fact, testing on current index members when membership was different historically, and using revised economic data rather than initial releases.

The requirement: for every data point used in a decision, verify that it was available to market participants at the simulated decision time.

The gold standard is point-in-time data: databases that store data as it was known on each historical date, including initial releases, revisions, and restatements. If point-in-time data is not available, build in conservative reporting lags.

## In-Sample vs. Out-of-Sample

### Why splitting data matters

If you develop a strategy on data from 2010-2020 and test it on the same 2010-2020 data, you have proven nothing. The strategy was designed to fit that data. The question is whether it works on data it has never seen.

### Standard approach

- **In-sample (training)**: the data used to develop and calibrate the strategy
- **Out-of-sample (test)**: data held back, never used during development, used only for final evaluation
- **Walk-forward**: rolling the in-sample window forward and testing on successive out-of-sample periods. This simulates how the strategy would have been managed in real time, including periodic recalibration

The critical discipline: never touch out-of-sample data during strategy development. Once contaminated, it loses all validation power. If you modify the strategy after seeing out-of-sample results and re-test, you have converted out-of-sample into in-sample -- start over with fresh holdout data. Walk-forward validation is the closest approximation to live trading; prefer it when data history allows.

## Overfitting

The most dangerous failure mode in backtesting. Overfitting occurs when a strategy captures noise in the training data rather than genuine patterns.

### Signs of overfitting

- Exceptional in-sample performance, poor out-of-sample
- Sensitivity to small parameter changes (shifting a lookback by one day destroys results)
- Many tunable parameters relative to independent observations
- Reliance on quirks of specific historical periods unlikely to repeat
- Suspiciously smooth equity curve with no meaningful drawdowns

### Defenses against overfitting

- **Fewer parameters**: a strategy with 3 parameters deserves more trust than one with 15. Each parameter is a degree of freedom for fitting noise
- **Economic rationale**: can you explain WHY the strategy works, not just THAT it worked? A plausible mechanism (carry premium, behavioral bias, structural flow) provides independent support
- **Robustness testing**: does the strategy still work with slightly different parameters? If moving a 20-day lookback to 18 or 22 days destroys results, the signal is fragile
- **Multiple regimes**: does it work across different environments (trending, mean-reverting, high vol, low vol)?

## Realistic Assumptions

### Transaction costs

Every simulated trade must include realistic friction:

- **Commissions**: per-share or per-contract fees
- **Spread**: the bid-ask spread at the time of the simulated trade, not the midpoint
- **Slippage**: the difference between the intended execution price and the likely fill, which increases with position size and decreases with liquidity
- **Market impact**: for positions that are large relative to average daily volume, the act of entering or exiting moves the price against you

A strategy that generates 5% annual alpha before costs but trades frequently in illiquid names may generate negative alpha after costs.

### Other cost assumptions

- **Fill rates**: not every order fills. Simulating 100% fill rates on limit orders overstates returns. Assume partial fills or use market orders with realistic slippage
- **Funding and borrowing**: long positions have opportunity cost; short positions incur borrowing costs that vary by security and over time; leveraged strategies have financing costs that erode carry
- **Capacity**: a strategy that works with $1M may not work with $100M. Market impact scales with position size. Strategies in illiquid markets have natural capacity limits

## Regime Dependence

A strategy that works in trending markets may fail in mean-reverting ones. A carry strategy that profits in low-volatility environments may blow up in volatility spikes.

Test across multiple regimes explicitly: bull vs. bear, low vol vs. high vol, trending vs. range-bound, tightening vs. easing, risk-on vs. risk-off.

If the strategy only works in one regime, it is a regime-dependent strategy. This is not disqualifying -- but it requires regime identification as part of the trading system, and the strategy should be stopped or reduced when the regime shifts.

## Benchmark Comparison

A backtest result is meaningless without context. Compare the strategy to:

- **Buy and hold**: the simplest alternative. If the strategy does not beat holding the benchmark after costs, the complexity is not justified
- **Equal-weight portfolio**: a naive diversification approach
- **Random entry with same risk management**: does the alpha come from the entry signal or from the risk management rules? If random entries with the same stop-loss and take-profit generate similar returns, the signal has no edge
- **Simple factor exposures**: is the strategy just repackaging known factor premia (momentum, value, carry) with extra complexity?

## When to Trust a Backtest

A backtest result deserves conditional trust when it meets all of the following:

- Long history spanning multiple market regimes (not just one bull market)
- Genuine out-of-sample or walk-forward confirmation
- Realistic transaction costs, slippage, and capacity assumptions
- Few tunable parameters (parsimony)
- Works across reasonable parameter variations (robustness)
- Has a plausible economic explanation for why the edge exists
- Drawdown characteristics are survivable for the intended capital base
- Comparison to simple benchmarks shows genuine added value

A backtest result should be treated with skepticism when any of these conditions fail.

## Evidence That Would Invalidate This Framework

- Market microstructure changes that make historical transaction cost assumptions permanently unreliable
- Structural changes to data availability that eliminate survivorship or look-ahead bias concerns
- Development of testing methodologies that reliably distinguish signal from noise without out-of-sample holdout

## Output structure

When applying this skill, prefer this order:

1. `Strategy Description` -- what the strategy does in plain language
2. `Data Requirements and Integrity` -- what data is needed and what biases to guard against
3. `Test Design` -- in-sample/out-of-sample split, walk-forward plan
4. `Assumption Audit` -- transaction costs, fill rates, capacity, funding
5. `Overfitting Assessment` -- parameter count, robustness, regime dependence
6. `Benchmark Comparison` -- what simple alternatives to compare against
7. `Trust Assessment` -- overall evaluation of whether the results are credible
8. `Next Skill` -- suggest `factor-investing`, `risk-management`, or additional research as appropriate

## Best practices

- do not celebrate a backtest result before subjecting it to all the checks above
- do not add parameters to improve in-sample performance; this is almost always overfitting
- do not ignore transaction costs because the strategy "trades infrequently" -- verify this
- do not treat one market regime as representative of all conditions
- do not confuse a high Sharpe ratio with a trustworthy strategy; Sharpe is manipulable through leverage, frequency filtering, and survivorship bias
- do not skip the economic rationale; if you cannot explain why the edge exists, it probably does not

## Usage examples

- "Use `backtesting-methodology` to audit my momentum strategy backtest. It shows a 2.1 Sharpe over 2015-2024 but I have 8 parameters."
- "Use `backtesting-methodology` to design a proper test framework before I run my mean-reversion strategy on equity pairs."
- "Use `backtesting-methodology` to figure out why my carry strategy backtests well but has lost money for 6 months in live trading."
