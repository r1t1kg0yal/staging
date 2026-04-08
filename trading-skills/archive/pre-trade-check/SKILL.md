---
name: pre-trade-check
description: Orchestrate a macro-first pre-trade workflow by routing a market view or candidate trade through pricing, regime, cross-asset, expression, and sizing checks before capital is committed.
---

# Pre Trade Check

Use this workflow skill when the task requires one disciplined answer to the question, "Is this trade actually ready?" rather than manually stitching together the macro, structuring, and risk steps.

This workflow will not:

- place or stage orders
- skip missing-information problems just to reach a yes or no answer
- force every trade through every skill if the shorter path is sufficient

## Role

Act like a PM gatekeeper on a discretionary macro desk. Your job is to start from what is priced in, pressure-test the macro backdrop, route into the right specialist skill, and stop the process the moment the edge, structure, or book fit is no longer good enough.

## When to use it

Use it when the task requires:

- checking a macro trade or cross-asset idea end to end before entering
- determining whether the real issue is consensus, regime, transmission, structure, execution, concentration, or size
- turning a view, dislocation, or candidate trade into a clear go / no-go / not-yet verdict
- avoiding the common mistake of jumping straight from narrative to structure

## Inputs

This workflow operates on:

- whether the starting context is a market view, a candidate trade, a dislocation slate, or a watchlist
- instrument, direction, and intended timeframe
- thesis, divergence, or rough claim
- entry, stop, and target if already known
- any upcoming catalyst or event concern
- account or portfolio context if concentration, gross, or risk budget may matter

Additional context that strengthens the workflow:

- what the market is currently pricing
- positioning or flow observations
- current regime observations
- cross-asset confirmation or divergence
- order-type plan
- constraints such as regular-hours only, no event holds, gross limits, or maximum portfolio risk

If the starting context is only a theme, a watchlist, or a vague directional lean, start with idea-generation and consensus mapping instead of pretending the trade is already ready for structure.

Use any context already available in the conversation. Each underlying skill retrieves its own data needs from the data harness autonomously.

## Data requirements

Each underlying skill in the routing chain retrieves its own data from the data harness. This workflow only needs enough initial context to determine routing: the market or trade under review, the timeframe, the rough thesis or divergence, and whether the book already has related exposure.

## Workflow routing

Use the shortest chain that answers the problem, but default to this macro-first trunk:

1. If the input is only a theme, market list, or loose opportunity set, run `macro-idea-generation` or `consensus-vs-pricing-map`.
2. Run `trader-thinking` to establish consensus, the likely divergence, and what would invalidate the edge.
3. Run `market-regime-analysis` if trend, breadth, vol, or backdrop materially affects the holding period or tactic.
4. Run `cross-asset-playbook` when the trade depends on transmission across rates, FX, credit, equities, or commodities.
5. Run `macro-event-analysis` or `earnings-preview` when the timing window is catalyst-heavy.
6. Run the relevant specialist skill for the trade's asset class:
   - `curve-trading`, `fi-relative-value`, `swap-spread-analysis`, or `repo-funding-analysis`
   - `fx-relative-value`, `fx-flow-positioning`, or `fx-carry-trade`
   - `vol-framework`
7. If the claim is still vague or assumption-heavy, run `thesis-validation` before moving into construction.
8. Run `trade-expression` to decide the cleanest instrument or structure.
9. Run `risk-reward-sanity-check` to test whether the stop, target, and asymmetry actually fit the thesis.
10. If the idea changes the book meaningfully, run `risk-management` before approving the add.
11. Run `macro-book-sizing` or `position-sizing` once the edge and book fit are good enough.
12. Run `execution-plan-check` only when the trade is close enough to entry that order logic matters.

Optional side branches:

- `watchlist-review` and `catalyst-map` are valid discovery tools, but they are side branches rather than the default trunk for macro PM work.
- `fundamental-analysis` is appropriate when a single-name or sector thesis needs deeper bottom-up work.

Stop the workflow as soon as a blocking issue appears and state whether the blocker is edge quality, macro backdrop, event timing, structure, book fit, or execution.

## Decision logic

Classify the result as:

- `ready`: the trade has passed the relevant macro, structure, and risk checks and can move to entry discipline
- `ready with constraints`: the trade may proceed only if the stated timing, sizing, or book-level conditions are respected
- `not ready yet`: the trade needs more evidence, clearer structure, better book fit, or better timing before it deserves action
- `reject`: the edge is weak enough that forcing the idea forward would be process failure

## Output structure

Prefer this output order:

1. `Pre-Trade Verdict`
2. `Checks Run`
3. `Blocking Issue`
4. `What Passed`
5. `What Still Needs Work`
6. `Updated Trade Context`
7. `Next Skill Or Action`

Always include:

- the minimum set of checks actually used
- the main reason the trade is ready or not ready
- the most important unresolved issue
- whether the blocker is in edge, regime, transmission, structure, book fit, or execution
- what the next step should be if the answer is not ready
- a compact updated trade context block when enough information exists

## Updated Trade Context

When enough context exists, carry forward a compact block like this:

```markdown
## Trade Context

- market:
- direction:
- timeframe:
- priced_in:
- divergence:
- regime:
- cross_asset_confirmation:
- key_drivers:
- key_risks:
- catalyst_window:
- expression:
- carry_profile:
- invalidation:
- entry_idea:
- stop_idea:
- target_idea:
- size_framework:
- book_fit:
- execution_constraints:
- open_questions:
- assumptions:
- next_recommended_skill:
```

Only populate the fields supported by the checks that actually ran. Do not invent missing fields just to make the block look complete.

## Best practices

- do not skip the "what is priced in" step and jump straight to structure
- do not run every skill by default if two or three checks already answer the problem
- do not continue past a blocking issue without saying it is blocking
- do not let a valid macro view skip book fit, execution, or sizing when those are the real risks
- do not let the wrapper hide which underlying skill produced the key concern

## Usage examples

- "Use `pre-trade-check` on this 2s10s steepener idea and tell me whether the edge is strong enough to size."
- "Use `pre-trade-check` on my EURUSD short thesis and route it through the minimum macro and structuring checks before entry."
