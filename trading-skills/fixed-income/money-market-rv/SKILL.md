---
name: money-market-rv
description: Identify and structure relative value trades in money markets and the front end -- bill-repo spreads, specials vs GC, cross-segment repo arbitrage, term vs overnight, carry and tail trades, calendar effect trades, and RV trade financing mechanics. Use when looking for front-end dislocations, structuring carry trades through repo, or evaluating how repo financing economics affect any leveraged rates position.
---

# Money Market Relative Value

Use this skill when the task is to find and structure relative value trades in money markets and the front end. In money markets, the financing mechanics are the trade. The repo segment you choose, the term you lock, the haircut you negotiate, and the calendar effects you position around are first-class trading decisions, not afterthoughts. This skill covers the full RV toolkit from opportunity identification through financing structure and P&L decomposition.

This skill will not:

- diagnose the money market regime (use `repo-funding-analysis` for that; this skill consumes its output)
- replace broader rates strategy (use `fi-relative-value` or `curve-trading` for bond-level RV or curve trades)
- model option-embedded structures (use `rates-vol-swaptions` or `vol-framework`)
- guarantee convergence of any money market spread

## Role

Act like a front-end trader who lives in the repo market. You think in terms of matched book spreads, tail exposure, specials income, day-count anomalies, and calendar distortions. You know that every leveraged position embeds a funding decision, and the funding decision is often where the edge is. You understand that the same bond financed in different repo segments at different terms produces completely different risk-adjusted returns. You separate carry into its components: coupon carry, repo carry, specials carry, and day-count carry.

## When to use it

Use it when the task requires:

- identifying front-end relative value opportunities across bills, repo, discount notes, and commercial paper
- evaluating specials vs GC spreads and whether specialness is structural or transient
- structuring carry and tail trades with explicit repo financing assumptions
- positioning for calendar effects (quarter-end, year-end, month-end rate distortions)
- arbitraging cross-segment repo rate differentials (triparty vs GCF vs bilateral vs sponsored)
- structuring and sizing a leveraged RV trade financed in repo (long leg + short leg + dealer spread)
- decomposing P&L into MTM, financing cost, specials income, and day-count adjustments
- evaluating how the current money market regime (from `repo-funding-analysis`) maps to specific RV opportunities
- feeding a money market trade into `trade-expression`, `position-sizing`, or `risk-management`

## Inputs

This skill operates on:

- the specific RV opportunity or trade being evaluated
- the regime classification from `repo-funding-analysis` (S1-S6)
- the user's directional lean on short rates, if any
- the intended holding period
- whether the trade is a standalone money market position or the financing component of a broader rates trade

Additional context that strengthens the analysis:

- output from `repo-funding-analysis` for regime, corridor, and balance sheet constraint context
- specific repo rates by segment (triparty, GCF, bilateral, sponsored)
- T-bill yields across the maturity spectrum
- specials rates for specific issues
- auction calendar and settlement dates
- quarter-end or year-end proximity and severity
- MMF allocation data for flow context

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

### Front-end rates
- T-bill yields at standard maturities (1M, 2M, 3M, 6M, 1Y)
- SOFR rate and SOFR term structure (1M, 3M)
- Treasury GC repo rate (overnight, 1W, 1M, 3M if available)
- GCF repo rate
- Triparty repo rate
- Bilateral dealer-to-buyside repo rate where available
- FHLB discount note yields (overnight, 1M, 3M)
- A1/P1 commercial paper rates (1M, 3M)
- Fed RRP rate (administered floor)
- IORB rate (administered anchor)

### Specials and specific issues
- On-the-run Treasury repo rates (specials rates) at key tenors (2Y, 5Y, 10Y, 30Y OTR)
- GC repo rate for comparison (specials spread = GC minus specials rate)
- CTD bond repo rates for active futures contracts
- Auction calendar (upcoming new issues that will become OTR)
- Settlement dates for recent auctions (settlement day demand for specific issues)

### Calendar and structural
- Days until next quarter-end, year-end, month-end
- G-SIB reporting dates if approaching
- Historical quarter-end rate spike data for calibration
- Tax payment dates (estimated tax payments, April/June/Sept/Dec)
- Treasury settlement calendar

If specific data is unavailable, proceed with what is available and note the gap in the output.

## RV opportunity taxonomy

### Bill-repo spread
Bills consistently yield below repo for the same maturity. The spread exists because many investors (state and local governments, regulated funds, certain institutional mandates) cannot transact in repo and must hold bills, creating captive demand that pushes bill yields below the repo alternative.

- The spread is structural and persistent, but its magnitude varies with regime and risk appetite
- Flight-to-safety widens the spread (captive demand intensifies, bills bid aggressively)
- In flat or inverted curves, overnight repo competes with or beats bills, pushing portfolio managers to sell bills and invest in repo (self-reinforcing)
- In steep curves, bills become attractive for rolldown while term repo locks in the short rate

**Assessment:** compare bill yield to matched-maturity repo rate. A bill-repo spread wider than its 1Y average in a regime where there is no fundamental reason for flight-to-safety is a potential RV signal (bills too rich). A compressed spread in a risk-off environment may indicate bills are not yet fully pricing the safety premium.

### Specials vs GC
An issue trades "special" when borrowing demand drives its repo rate below the GC rate. The holder earns a lending fee equal to (GC rate minus specials rate) times notional times days/360.

**Triggers for specialness:**
- On-the-run status (heavy shorting by dealers and hedge funds against the most liquid issue)
- CTD for futures (basis trade demand to borrow the cheapest-to-deliver bond)
- Settlement needs (fails on specific issues create delivery urgency)
- Auction cycle: new issue goes on-the-run, becomes most shorted, goes special; as it ages off-the-run, specialness declines; the cycle is predictable

**Extreme specialness:** demand can drive the specials rate negative (borrower pays to obtain the issue). Near-zero policy rates make this more likely because the fails charge (max(0, target rate minus 300bp)) becomes zero, making fails costless and reducing the incentive to resolve delivery failures.

**Trading specialness:** owning a bond that goes special in repo earns an additional lending fee independent of the bond's market value P&L. For on-the-run bonds, specialness is predictable and persistent. Owning OTR is a carry trade with a specials income overlay. Basis traders must separate specials carry from bond carry when computing the true economics of a basis position.

### Cross-segment arbitrage
The same collateral can trade at different repo rates across segments because balance sheet costs, clearing treatment, and counterparty risk differ. The GCF-triparty spread, the bilateral-GCF spread, and the sponsored-vs-uncleared spread each represent a distinct balance sheet premium.

- Normal: GCF trades above triparty by the balance sheet cost of intermediation (post-SLR, this is approximately 10-15bp)
- Quarter-end: segment differentials blow out as dealers shed unnettable positions. Bilateral rates spike most, GCF rises moderately, triparty is suppressed as MMFs have nowhere to lend
- The arbitrage: borrow in the cheap segment, lend in the expensive segment, earn the spread. The constraint is balance sheet capacity to warehouse the gross position

**Assessment:** compare current segment spreads to their non-calendar-period averages and to their historical calendar-period averages. A segment spread at the 90th percentile outside a calendar period may indicate a structural shift in balance sheet capacity or a positioning imbalance.

### Term repo vs overnight
The term repo rate versus the overnight rate reflects the market's expectation of the overnight rate path plus a term premium.

- If you expect rates to stay lower than the term rate implies: lock in term repo and earn the term premium
- If you expect rates to rise faster than the term rate implies: stay rolling overnight and avoid overpaying
- The term-versus-overnight decision is a rates view embedded inside every leveraged position

In steep curves, term repo locks in a known rate and provides certainty; bills become attractive for rolldown. In flat or inverted curves, overnight repo may be the superior instrument because it adjusts immediately to rate changes and competes directly with bills.

### DN-bill and CP-bill spreads
FHLB discount notes yield above bills at matched maturities because they carry agency credit risk and are less liquid. The DN-bill spread is driven by the FHLB funding cycle (continuous issuance to fund the FHLB-FBO-IORB chain) and MMF allocation decisions.

CP-bill spreads embed credit risk (A1/P1 issuers vs Treasury) and liquidity premium. The spread widens in stress as MMFs flee to government-only instruments and narrows in calm as yield-seeking allocators return to prime.

Both spreads are regime-sensitive: wider in S3, S5, S6 (stress); narrower in S1 (ample).

### Day-count arbitrages
The agency 30/360 day-count convention creates directly tradeable anomalies:

- July 31 is a non-day under 30/360 (no interest accrues)
- February 29 exists under 30/360 in non-leap years (phantom accrual day)
- February 30 exists under 30/360 (fictional day with real accrual)
- February 28 to March 1 produces 3 days of 30/360 accrual in 1 calendar day

These create cross-instrument anomalies when one leg of a trade uses actual/360 and the other uses 30/360. Dealer quote sheets often do not adjust for these differences, creating an edge for correct computation. The anomalies are small per day but compound in size for larger positions and longer holding periods.

## Carry and tail trade mechanics

### The tail trade
Financing a long bond position with shorter-term repo creates an unfinanced residual: the "tail." If you buy a 90-day bill and finance it with 30-day term repo, you have locked carry for 30 days but are exposed to whatever the repo rate is when you must refinance for the remaining 60 days. The tail IS the trade.

**Effective purchase yield of the tail:**
- Carry earned over N days modifies the effective purchase yield of the remaining M-day position by (carry x N/M)
- The entire P&L depends on the tail's value at the refinancing date
- Term repo eliminates carry uncertainty for N days; the trade is actually a bet on what happens during the remaining M minus N days

### Matched book mismatching
The matched book is the central transmission mechanism of the repo market: dealers bridge segmented markets that cannot transact directly. The spread compensates for balance sheet, counterparty, and operational risk.

But the real money comes from mismatching the book: deliberate maturity mismatch creates pure short-rate risk without market risk on the collateral. Borrow overnight, lend term (or vice versa). This is why the matched book is a profit center, not just plumbing.

### Structural dealer long bias
Shorting requires both a buyer and a source (reverse in or borrow). Only government securities and agencies are homogeneous enough to short in size. At equal conviction, dealers short less than they go long, creating a persistent long bid at the front end. This is structural, not a directional signal.

## Calendar and window dressing trades

Calendar distortions are predictable in timing, direction, and approximate magnitude. They create systematic trading opportunities:

### Tradeable patterns
- **Pre-quarter-end:** lend cash at elevated repo rates as dealers scramble for funding. Repo rates spike in bilateral and triparty; the spike is most severe in non-nettable segments.
- **Post-quarter-end:** borrow at depressed rates as balance sheets re-expand. Rates normalize within 1-3 business days of the reporting snapshot.
- **Nettable vs unnettable spread:** position for widening between cleared and uncleared segment rates at reporting dates. The bilateral-GCF spread is the clearest expression.
- **Futures calendar spread:** sell front-month futures near quarter-end as shorts roll to avoid delivery in a constrained environment.
- **Month-end GCF spike:** Fannie Mae pays monthly MBS coupons at month-end, depleting its cash and withdrawing from GCF lending. GCF rates spike as dealers must fill the gap. The intra-month pattern (low rates mid-month as Fannie accumulates cash, high rates at month-end as Fannie pays out) is highly predictable.

### Severity calibration
- Year-end (G-SIB snapshot): most severe. G-SIB surcharge is calculated from year-end balance sheet across 5 categories. Banks face the strongest incentive to shrink.
- Quarter-end: moderate. Regulatory reporting drives balance sheet optimization but no G-SIB score impact.
- Month-end: mild. Driven primarily by the Fannie Mae payment cycle in GCF and general reporting cleanup.
- Foreign bank reporting dates (various): create an additional distortion layer that can compound with US reporting dates.

### Regime interaction
Calendar effects amplify the base regime. A quarter-end in regime S1 (ample reserves) produces mild rate spikes (5-15bp above normal in bilateral). A quarter-end in regime S3 (scarce reserves) produces severe dislocations (50bp+ spikes, possible SRF usage). Always assess calendar severity conditional on the base regime from `repo-funding-analysis`.

## RV trade financing mechanics

### Leveraged RV trade structure
A leveraged Treasury relative value trade is financed through repo on both legs:

**Long leg:** enter a repo agreement (borrow cash from dealer, pledge the long bond as collateral). Use the cash to purchase the bond. The fund is long the bond, financed at the repo lending rate.

**Short leg:** enter a reverse repo agreement (lend cash to dealer, receive the short bond as collateral). Sell the bond in the cash market. The fund is short the bond, earning the reverse repo rate on the cash.

**Dealer role:** the dealer packages this as a "netted package," earning the spread between the repo lending rate on the long leg and the reverse repo borrowing rate on the short leg. The dealer spread is the cost of leverage for the RV trade.

### Leverage mechanics
- Maximum leverage = 1 / haircut
- Zero haircut (common in Treasury repo for strong counterparties) implies theoretically unlimited leverage
- 2% haircut per leg means $4M in margin supports $200M gross exposure (50x)
- The haircut is not just risk management; it is a binding capital constraint that determines the trade's size envelope

### Segment selection as trade decision
Where the trade is financed matters as much as what is traded:

- **Bilateral DVP (NCCBR):** specific collateral, not centrally cleared, not nettable. Most expensive balance sheet treatment. Used for specific issues (specials, CTD).
- **Sponsored DVP:** same specific collateral but centrally cleared via a sponsor. Nettable on the sponsor's balance sheet. Cheaper for the sponsor, better rates for the fund.
- **GCF:** general collateral, inter-dealer, centrally cleared, nettable. Cheapest balance sheet treatment but only available to members and their sponsored counterparties.

Moving from bilateral to sponsored/cleared reduces the dealer's balance sheet cost, which should flow through as a tighter financing spread for the fund. In practice, the pass-through is partial and varies by dealer relationship, size, and market conditions.

### P&L decomposition
Total P&L of a financed RV trade breaks into five components:

1. **MTM gain on long leg:** price appreciation of the long bond
2. **MTM gain on short leg:** price depreciation of the short bond (profit from the short)
3. **Net financing cost:** (repo rate on long minus reverse repo rate on short) times notional times days/360. This is the hurdle rate. The trade is profitable when convergence exceeds net financing cost.
4. **Specials income:** if either leg is trading special in repo, there is an additional income or cost stream. Long a bond on special = earn lending fee. Short a bond on special = pay elevated borrowing cost.
5. **Day-count adjustments:** cross-instrument day-count differences (actual/360 vs 30/360) create small but real P&L items that are often missed.

## Regime-contingent strategy

Each RV opportunity behaves differently across the six money market regimes:

| Trade | S1 (Ample) | S2 (Transitional) | S3 (Scarce) | S4 (Calendar) | S5 (Offshore) | S6 (Stress) |
|-------|-----------|-------------------|-------------|---------------|---------------|-------------|
| Bill-repo spread | Stable, narrow | Widening as bills bid | Wide, volatile | Compressed (bills scarce) | Wider (flight to safety) | Blowout |
| Specials-GC | Normal, predictable | Normal, wider on OTR | Elevated (delivery fails) | Compressed (all rates spike) | Normal | Specials can go negative |
| Cross-segment arb | Tight, steady | Widening gradually | Wide, volatile | Peak opportunity | Disrupted | Frozen |
| Term vs overnight | Term premium modest | Term premium rising | Term premium elevated | Distorted by calendar | Elevated uncertainty | Inverted (cash hoarding) |
| Calendar trades | Mild effect | Moderate effect | Severe effect | Peak expression | Compound with offshore | Overwhelmed by stress |
| DN-bill, CP-bill | Tight | Stable | Widening | Volatile | Widening (credit) | Blowout |

Use the regime classification from `repo-funding-analysis` to filter which RV trades are attractive in the current environment and which should be avoided.

## Core assessment framework

Assess each money market RV opportunity on four anchors:

- `Spread Level`: where is the spread relative to its historical distribution. State the percentile and the lookback period used. Distinguish between calendar-period and non-calendar-period distributions (a spread at the 90th percentile during a quarter-end may be normal; the same spread mid-quarter may be extreme).
- `Regime Consistency`: does the spread level make sense given the current regime (S1-S6) from `repo-funding-analysis`, or is there a disconnect? A spread that is wide while the regime says narrow is a potential opportunity. A spread that is wide because the regime justifies it is not.
- `Carry Profile`: is the trade positive or negative carry? What is the tail exposure? What is the breakeven (how much must the spread move against before carry is exhausted)? A positive-carry trade with a large breakeven buffer is structurally more attractive.
- `Calendar Proximity`: are there upcoming calendar events (quarter-end, year-end, auction settlement, tax dates) that will amplify or compress the dislocation? Calendar events are predictable in direction and approximate timing. Position with the calendar, not against it.

Use the anchors to classify:

- `actionable dislocation`: spread at historical extreme, regime does not justify the level, positive carry or breakeven buffer, calendar supports convergence
- `interesting but watch`: spread is extended but regime partially justifies it, or carry is negative, or a calendar event may temporarily push the spread further before it converges
- `fair value or no edge`: spread is mid-range and consistent with the regime, or carry does not compensate for the risk

## Output tables

### Front-End Rate Matrix
| Instrument | Rate (%) | vs GC (bp) | vs SOFR (bp) | 3M Avg | Percentile |
|------------|----------|-----------|-------------|--------|------------|
| T-Bill (1M) | ... | ... | ... | ... | ...th |
| T-Bill (3M) | ... | ... | ... | ... | ...th |
| FHLB DN (1M) | ... | ... | ... | ... | ...th |
| FHLB DN (3M) | ... | ... | ... | ... | ...th |
| CP A1/P1 (1M) | ... | ... | ... | ... | ...th |
| CP A1/P1 (3M) | ... | ... | ... | ... | ...th |
| Triparty repo (O/N) | ... | N/A | ... | ... | ...th |
| GCF repo (O/N) | ... | ... | ... | ... | ...th |
| Bilateral HF (O/N) | ... | ... | ... | ... | ...th |
| Term repo (1M) | ... | ... | ... | ... | ...th |
| Term repo (3M) | ... | ... | ... | ... | ...th |

### RV Opportunity Table
| Spread / Trade | Current (bp) | 3M Avg (bp) | Percentile | Regime Signal | Calendar Sensitivity |
|----------------|-------------|-------------|------------|---------------|---------------------|
| Bill-repo (1M) | ... | ... | ...th | ... | Low / Moderate / High |
| Bill-repo (3M) | ... | ... | ...th | ... | ... |
| Specials-GC (OTR 10Y) | ... | ... | ...th | ... | ... |
| GCF - Triparty | ... | ... | ...th | ... | ... |
| Bilateral - GCF | ... | ... | ...th | ... | ... |
| Term (1M) - O/N | ... | ... | ...th | ... | ... |
| DN - Bill (1M) | ... | ... | ...th | ... | ... |
| CP - Bill (1M) | ... | ... | ...th | ... | ... |

### Carry & Tail Analysis
| Component | Long Leg | Short Leg | Net |
|-----------|----------|-----------|-----|
| Bond yield / rate (%) | ... | ... | ... |
| Repo financing rate (%) | ... | ... | ... |
| Net carry (bp/day) | ... | ... | ... |
| Specials income (bp/day) | ... | ... | ... |
| Total carry (bp/day) | ... | ... | **...** |
| Term repo locked (days) | ... | ... | |
| Tail exposure (days) | ... | ... | |
| Breakeven spread move (bp) | | | **...** |

### Calendar Trade Calendar
| Date | Event | Expected Impact | Historical Pattern | Severity (given regime) |
|------|-------|-----------------|--------------------|-----------------------|
| ... | Quarter-end | Bilateral spike, GCF-TRP widening | +15-50bp bilateral | S1: mild / S3: severe |
| ... | Year-end / G-SIB | Peak shrinkage, all segments spike | +25-75bp bilateral | ... |
| ... | Auction settlement | OTR specials demand | Specials tighten 5-15bp | ... |
| ... | Tax payment date | TGA rebuilds, reserves drain | Front-end tightening | ... |
| ... | Month-end | Fannie MBS coupon payout, GCF spike | GCF +5-10bp | ... |

### Trade Financing Structure
| Parameter | Long Leg | Short Leg |
|-----------|----------|-----------|
| Bond / instrument | ... | ... |
| Direction | Repo (borrow cash) | Reverse repo (lend cash) |
| Repo segment | DVP / Sponsored / GCF | DVP / Sponsored / GCF |
| Repo rate (%) | ... | ... |
| Haircut (%) | ... | ... |
| Notional ($) | ... | ... |
| Leverage (x) | ... | ... |
| Balance sheet cost (nettable?) | Yes / No | Yes / No |
| Dealer spread (bp) | ... | ... |

### P&L Decomposition
| Component | Value |
|-----------|-------|
| MTM gain on long leg | ... |
| MTM gain on short leg | ... |
| Net financing cost | ... |
| Specials income (net) | ... |
| Day-count adjustment | ... |
| **Total P&L** | **...** |

## Evidence that would invalidate this analysis

- a Fed policy decision that shifts the rate corridor or changes the overnight rate path
- a regulatory change (SLR treatment, central clearing mandate, MMF reform) that alters segment pricing or balance sheet economics
- a regime transition (e.g., S2 to S3) that changes which RV trades are attractive
- a change in the Treasury's issuance strategy (bill vs coupon mix, buyback program) that shifts front-end supply dynamics
- a calendar event of unexpected severity (or mildness) that dislocates the historical calibration
- a structural shift in MMF behavior or dealer balance sheet capacity that changes matched book economics
- a specific-issue event (CTD switch, new OTR auction, fails spike) that changes specials dynamics

## Output structure

Prefer this output order:

1. `Money Market RV Summary`
2. `Regime Context` (reference `repo-funding-analysis` output or summarize if not available)
3. `Front-End Rate Matrix` (table)
4. `RV Opportunity Table` (table)
5. `Carry & Tail Analysis` (table, for proposed or evaluated trades)
6. `Calendar Trade Calendar` (table)
7. `Trade Financing Structure` (table, for any financed RV position)
8. `P&L Decomposition` (table)
9. `Assessment And Classification`
10. `Key Risk Factors`
11. `Next Skill`

Always include:

- the current regime (from `repo-funding-analysis` or assessed inline) as context for all RV assessments
- the front-end rate matrix showing where every instrument trades relative to GC and SOFR
- the specific RV opportunity identified, its spread level, historical percentile, and regime consistency
- carry decomposition separating bond carry, repo carry, specials carry, and day-count effects
- calendar proximity and how it affects the trade's timing
- whether the idea should move to `trade-expression`, `position-sizing`, or needs more context from `repo-funding-analysis`

## Best practices

- every leveraged position embeds a funding decision; the funding decision is often where the edge is
- the tail IS the trade; always compute what happens when the repo matures, not just the carry during the repo term
- separate specials carry from bond carry; they have different drivers and different persistence
- the same bond financed in different repo segments produces different risk-adjusted returns because of balance sheet cost pass-through
- calendar effects are predictable in direction and approximate timing but vary in magnitude; calibrate severity to the base regime
- the bill-repo spread is structural, not a mispricing; trade it when the structural factors are amplified or compressed beyond normal
- cross-segment arbitrage is constrained by balance sheet; the opportunity and the constraint are the same variable
- day-count anomalies are small per trade but compound; correct computation creates edge over dealer quote sheets that ignore cross-instrument day-count differences
- matched book mismatching is pure short-rate risk; the real money comes from deliberately mismatching term, not from the spread alone
- do not assume any money market spread mean-reverts without checking whether the regime has changed; a wider bilateral-GCF spread may be the new normal if regulation has tightened
- structural dealer long bias creates a persistent bid at the front end; this is structural, not a signal to fade
- in regime S6 (shadow cash stress), all money market RV relationships break down; do not trade RV into a funding crisis

## Usage examples

- "Use `money-market-rv` to scan for front-end RV opportunities. We are in regime S2 heading into quarter-end and I want to know which spreads are dislocated."
- "Use `money-market-rv` to evaluate the bill-repo spread at 1M and 3M. Bills look cheap relative to repo and I want to understand if the spread is at a tradeable extreme."
- "Use `money-market-rv` to structure a calendar trade for the upcoming quarter-end. I want to lend cash at elevated rates and position for the bilateral-GCF spread widening."
- "Use `money-market-rv` to decompose the carry on my Treasury RV trade. I need to separate bond carry, repo carry, and specials carry to understand the true economics."
- "Use `money-market-rv` to evaluate whether I should finance my 10Y long in term repo or roll overnight. The curve is flat and I think the Fed holds for 6 months."
- "Use `money-market-rv` to assess the OTR 10Y specialness. The new issue just settled and I want to know if the specials income makes it worth owning versus the first off-the-run."
