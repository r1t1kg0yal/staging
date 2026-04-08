---
name: scenario-analysis
description: Construct coherent macro-driven scenarios, assign rough probabilities, estimate directional portfolio impact, and surface tail risks -- focused on the thinking process rather than false precision.
---

# Scenario Analysis

Use this skill when a portfolio or set of positions exists and the task requires thinking through what could happen, how each scenario would affect the book, and where the hidden risks are. This is the discipline of asking "what if" rigorously rather than hoping for the base case.

This skill will not:

- produce precise P&L estimates for each scenario
- replace proper risk management or position sizing
- assign probabilities with false precision
- turn uncertainty into certainty through modeling

## Role

Act as a scenario planning analyst. Your job is to force intellectual honesty about what could go wrong, what could go right for the wrong reasons, and what tail risks the current portfolio is silently exposed to.

## When to use it

Use it when the task requires:

- stress testing a portfolio against multiple macro outcomes before a catalyst
- thinking through second-order effects of a policy decision, geopolitical event, or data surprise
- identifying which positions are most vulnerable and which provide natural hedging
- challenging the base case by examining alternatives honestly
- pairing with `risk-management` or `portfolio-construction` to adjust exposures based on scenario work

## Inputs

This skill operates on:

- current portfolio positions (or the key positions under consideration)
- the macro drivers considered most important for the current environment
- the base case view and rough confidence level
- time horizon for the analysis
- any specific catalysts or event dates on the horizon

Additional context that strengthens the analysis:

- historical analogues relevant to the current situation
- positioning and consensus data for relevant markets
- correlation assumptions or regime view

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

- current portfolio positions and sizes
- historical scenario data for relevant macro shocks
- cross-asset correlation data
- macro indicators relevant to the scenarios under consideration

If specific data is unavailable, proceed with what is available and note the gap in the output.

## Scenario Construction

### Start from drivers, not price targets

A scenario is a coherent story about how macro variables evolve, not a price target wearing a label. "SPX goes to 5500" is not a scenario. "Growth reaccelerates, the Fed delays cuts, and multiples compress slightly but earnings growth more than compensates" is a scenario.

The primary macro drivers to consider:

- **Monetary policy**: rate path, balance sheet, forward guidance tone
- **Growth**: real GDP trajectory, labor market, capex and consumption
- **Inflation**: direction and composition (sticky vs. transient, demand vs. supply)
- **Geopolitics**: trade policy, military conflict, sanctions, supply chain disruption
- **Financial conditions**: credit availability, funding markets, risk appetite
- **Fiscal policy**: spending trajectory, deficit dynamics, political constraints

Each scenario should specify a coherent combination of these drivers. Not every driver needs to be extreme -- most scenarios have some drivers moving and others roughly stable.

### Build 3-5 scenarios minimum

| Scenario Type | Purpose |
|---------------|---------|
| Base case | The most likely path -- what you would bet on if forced to pick one |
| Bull case | What goes right beyond the base case; where positive surprises come from |
| Bear case | What goes wrong; the recession, the policy mistake, the external shock |
| Tail scenario | The outcome nobody is preparing for; the consensus-breaking event |
| Stagflation / mixed | The uncomfortable scenario where growth and inflation move in the wrong combination |

The tail scenario is the most important one to think through honestly. It is the scenario where the portfolio takes maximum damage and there is no plan.

## Probability Weighting

Assign rough probabilities. The goal is not precision -- it is honesty about conviction distribution.

```
  Example distribution:

  Base case (soft landing, gradual easing)     40%
  Bull case (reacceleration, no cuts needed)   25%
  Bear case (recession, aggressive cuts)       20%
  Tail (financial accident / geopolitical)     10%
  Stagflation (inflation sticky, growth weak)   5%
                                              ────
                                              100%
```

Rules for probability assignment:

- If the base case is above 60%, check whether that reflects genuine evidence or anchoring to the consensus
- If no scenario is below 10%, check whether tail risks are being acknowledged honestly
- If the reasoning for why one scenario is more likely than another is unclear, the probabilities are not ready
- Probabilities should shift as evidence arrives -- they are not permanent

## Portfolio Impact Estimation

For each scenario, assess the impact on each major position. Do not attempt precise P&L. Focus on sign and relative magnitude.

```
  Position       Base Case    Bull Case    Bear Case    Tail
  ─────────────────────────────────────────────────────────────
  Long equities     +           ++           --          ---
  Short duration    +           ++            -           --
  Long gold         ~           -             +           ++
  IG credit         +           +            --          ---
  FX carry          +           +             -          ---
```

Symbols: `+++` large gain, `++` moderate gain, `+` small gain, `~` neutral, `-` small loss, `--` moderate loss, `---` large loss

What this exercise reveals:

- **Concentration of risk**: if most positions lose in the same scenario, the portfolio has a hidden correlation problem
- **Natural hedges**: positions that offset each other across scenarios
- **Tail vulnerability**: the scenario where everything goes wrong simultaneously
- **Asymmetry**: whether the portfolio has more upside in favorable scenarios than downside in adverse ones

## Tail Scenario Discipline

The tail scenario deserves disproportionate attention because:

- It is the scenario where losses are largest and least recoverable
- It is the scenario where correlations converge (diversification fails)
- It is the scenario where liquidity disappears and exits become expensive
- It is the scenario the portfolio was not built to survive

Questions to force honest tail thinking:

- What if the consensus is completely wrong about the macro regime?
- What if two risks materialize simultaneously?
- What if a position that is "hedging" fails to hedge because correlations shift?
- What if liquidity in a key position evaporates at the worst possible moment?
- What would cause the maximum drawdown on the current book?

## Second-Order Effects

First-order effects are the direct price moves from a scenario. Second-order effects are what happens next.

| Event | First Order | Second Order |
|-------|-------------|--------------|
| Sharp rate hike | Bond prices fall, equities reprice | Credit tightening, housing slows, bank stress |
| Oil supply shock | Energy prices spike | Inflation expectations rise, consumer spending shifts, central bank faces dilemma |
| Major credit event | Spreads blow out | Funding markets seize, risk appetite collapses, forced selling cascades |
| Currency crisis | FX collapses | Capital flight, imported inflation, emergency policy response |

Second-order effects are where the real portfolio damage often occurs. A 50bp rate shock is manageable. The credit tightening and housing slowdown it triggers may not be.

## Time Horizon Matching

Scenarios must match the portfolio's holding period:

- **Intraday / swing (days to weeks)**: scenarios focus on catalyst outcomes, positioning squeezes, technical levels, and near-term data. Macro regime scenarios are background context, not primary drivers.
- **Tactical (weeks to months)**: scenarios focus on policy decisions, earnings seasons, data trajectory, and flow dynamics. Regime transitions become relevant.
- **Strategic (months to years)**: scenarios focus on economic cycle positioning, structural policy shifts, secular trends. Short-term catalysts are noise.

A 6-month recession scenario is irrelevant for a 3-day swing trade. A single earnings print is irrelevant for a 2-year investment thesis. Match the scenario horizon to the position horizon.

## Evidence That Would Invalidate This Analysis

- A major driver that was not included in any scenario proves to be the dominant force
- Correlations across scenarios differ materially from what was assumed
- The probability distribution was anchored to consensus rather than independently assessed
- The time horizon of the scenarios does not match the actual holding period of the positions
- New information materially changes the base case after the analysis was completed

## Output structure

When applying this skill, prefer this order:

1. `Macro Drivers` -- the 3-5 drivers that matter most for this portfolio right now
2. `Scenario Definitions` -- each scenario as a coherent story, not a price target
3. `Probability Distribution` -- rough weights with reasoning
4. `Portfolio Impact Matrix` -- directional impact by position and scenario
5. `Tail Risk Assessment` -- the scenario nobody is preparing for
6. `Second-Order Effects` -- what happens after the first move
7. `Hedge Gaps` -- where the portfolio is unprotected
8. `Next Skill` -- suggest `risk-management`, `portfolio-construction`, `cross-asset-playbook`, `macro-book-sizing`, or `pre-event-risk-board` as appropriate

## Best practices

- do not let the base case consume all the analytical energy; the tail scenarios need the most work because they are the least intuitive
- do not confuse probability weighting with conviction; a 40% base case means a 60% chance of something else
- do not pursue false precision in impact estimation; directional magnitude is sufficient
- do not build scenarios around a single asset when the portfolio spans multiple asset classes
- do not ignore second-order effects; the cascade is often more damaging than the initial shock
- do not recycle old scenarios without updating them for new information

## Usage examples

- "Use `scenario-analysis` on my current portfolio ahead of the FOMC decision. I'm long equities, short duration, and have a small gold hedge."
- "Use `scenario-analysis` to stress test what happens to my EM FX positions if the dollar rally extends another 5%."
- "Use `scenario-analysis` to think through tail risks for a portfolio that is heavily concentrated in US tech."
