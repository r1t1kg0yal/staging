---
name: repo-funding-analysis
description: Diagnose the money market regime by mapping the rate corridor, repo market segmentation, reserve adequacy, balance sheet constraints, shadow money dynamics, and funding transmission channels. Use when assessing how plumbing conditions affect rates trading, identifying which funding regime the system is in, or understanding how reserves, TGA, QT, and dealer capacity interact to produce the rate environment.
---

# Repo & Funding Analysis

Use this skill when the task requires diagnosing the state of the money market system and understanding how plumbing dynamics affect rates markets. The financial system is layered plumbing: settlement systems, balance sheets, and intermediation chains. The Fed is the sole entity combining settlement operator, lender of last resort, and rate corridor setter. The binding constraint on liquidity is dealer balance sheet capacity, not cash or reserves. When plumbing clogs, rates spike, liquidity fragments, and the Fed intervenes.

This skill will not:

- predict Fed policy decisions (use `macro-event-analysis` for that)
- substitute for rates strategy (use `curve-trading`, `fi-relative-value`, or `money-market-rv` for trade construction)
- model the full financial system balance sheet (this is a practitioner's diagnostic toolkit)
- guarantee that plumbing dislocations resolve on any timeline

## Role

Act like a money market strategist who reads the plumbing the way a rates trader reads the yield curve. You understand the hierarchy of dollar rates, how reserves flow through the system, how dealer balance sheet constraints create dislocations, and how TGA and QRA dynamics affect funding conditions. You understand that the same rate corridor produces completely different market behavior depending on reserve distribution, balance sheet capacity, and shadow money dynamics. You translate plumbing signals into regime classification and rates trading implications.

## When to use it

Use it when the task requires:

- classifying the current money market regime (ample, transitional, scarce, calendar-distorted, offshore stress, shadow cash stress)
- mapping the rate corridor and understanding where overnight rates sit within it
- understanding repo market segmentation and why different segments trade at different rates
- evaluating how TGA rebuilds/drawdowns, QRA announcements, or QT pace changes affect money markets
- assessing dealer balance sheet constraints and how SLR, netting, and central clearing affect market functioning
- diagnosing reserve adequacy and the QT drain sequence (what drains: RRP, reserves, or TGA)
- evaluating shadow money dynamics (collateral velocity, haircut trends, rehypothecation capacity)
- understanding how MMF allocation decisions transmit through the system
- feeding funding regime analysis into `money-market-rv`, `swap-spread-analysis`, `treasury-basis-trading`, or `cross-asset-playbook`

## Inputs

This skill operates on:

- the current funding environment (reserve levels, RRP usage, TGA balance)
- any specific repo market observation (rate spike, specialness, quarter-end dynamics, segment dislocation)
- the user's rates position or proposed trade that depends on funding conditions
- whether the focus is short-term (day/week), cyclical (QT trajectory, reserve adequacy), or structural (shadow money, regulatory regime)

Additional context that strengthens the analysis:

- output from `macro-event-analysis` for upcoming Fed decisions or QRA
- SOFR, EFFR, and Fed Funds data
- dealer balance sheet or positioning data
- RRP and SRF usage data
- upcoming Treasury settlement, tax dates, or auction calendar
- MMF allocation data (AUM breakdown by destination)

Use any context already available in the conversation. Retrieve remaining data needs from the data harness. If specific data is unavailable, proceed with what is available and flag the gap in the output.

## Data requirements

Retrieve from the data harness:

### Rate corridor
- SOFR rate and volume
- EFFR rate and EFFR-IORB spread
- Treasury GC repo rate (triparty)
- GCF repo rate
- Bilateral repo rates where available (dealer-to-buyside spread over GCF)
- SRF facility usage (if active)
- IORB rate (administered)
- RRP rate (administered)

### Reserve and facility balances
- Reserve balances at Federal Reserve Banks
- RRP facility usage (total and trend)
- TGA balance and trajectory
- Recent QRA announcements (bill vs coupon issuance mix, buyback plans)

### Balance sheet and structural
- Dealer balance sheet data (primary dealer positioning, financing volumes)
- Any bonds trading special in repo (and degree of specialness)
- Quarter-end or year-end approaching (regulatory reporting dates)
- G-SIB surcharge reporting dates if relevant
- MMF AUM and allocation breakdown (RRP, repo, bills, DN, CP)

If specific data is unavailable, proceed with what is available and note the gap in the output.

## The rate corridor

The Fed's operational framework creates a corridor for short-term rates:

**Floor: ON RRP rate.** The rate at which eligible counterparties (MMFs, GSEs) can deposit overnight at the Fed. Provides a hard lower bound on overnight rates. When RRP usage is high, excess cash is being parked here because private alternatives do not offer enough yield to compensate for counterparty risk.

**Ceiling: SRF rate (or discount window).** The rate at which eligible counterparties can borrow overnight from the Fed against eligible collateral. Provides an upper bound. Stigma makes this ceiling soft: emergency facilities exist but usage signals weakness, so rates can briefly breach the ceiling until desperation overcomes reputation cost.

**Within the corridor:** IORB anchors EFFR. Market rates (SOFR, GC repo) trade around IORB depending on reserve distribution and balance sheet frictions. A rate persistently outside the corridor indicates broken plumbing, not policy failure.

## The rate hierarchy

Every dollar money market rate in the world sits within a single hierarchy ordered by credit risk, collateral quality, and access:

RRP (floor, risk-free, access-limited) < EFFR (unsecured overnight, interbank) < SOFR/TGCR/BGCR (secured overnight, broad market) < IORB (Fed pays banks on reserves) < SRF (ceiling, Fed lending rate) < DW (stigma premium) < FX swap-implied USD rate (offshore, credit + basis) < Swap line rate (emergency offshore)

Rates outside this ordering indicate broken arbitrage, inaccessible facilities, or a regime transition.

## Repo market segmentation

The repo market is not one market but four distinct segments with different participants, clearing mechanisms, netting treatment, and balance sheet costs:

### Triparty repo
- Cash lenders (MMFs, GSEs, securities lenders) lend to dealers via a triparty agent (sole clearing bank)
- General collateral: dealers pledge securities from inventory without specific delivery
- Not centrally cleared, not nettable for balance sheet purposes
- Expensive for dealers under SLR
- Core funding rate for primary dealers (VWAP across all trades, non-uniform pricing)

### GCF (inter-dealer / inter-system)
- Dealers trade with each other, anonymous and blind-brokered
- Centrally cleared by FICC with novation (FICC becomes counterparty to both sides)
- Nettable: if a dealer both borrows and lends in GCF, only the net appears on the balance sheet
- Uniform price published by DTCC
- Core lending rate for primary dealers and basis for all other dealer lending

### Bilateral DVP (non-centrally cleared)
- Any two parties, specific collateral, settled via Fedwire (actual securities and cash movement)
- Not centrally cleared, not nettable
- Most expensive balance sheet treatment
- Includes dealer-to-buyside lending (hedge funds, REITs) at GCF plus a spread

### Sponsored/Centrally cleared
- Non-members (hedge funds, MMFs, smaller dealers) access central clearing via a sponsoring member
- CCP novation provides netting benefit on the sponsor's balance sheet
- Balance sheet cheap for the sponsor; access expansion for the sponsored member
- Growing rapidly as Basel III made balance sheet cost binding

The matched book spread between segments (triparty funding rate vs bilateral lending rate) compensates dealers for balance sheet consumption, counterparty risk, operational risk, and settlement timing mismatch. Spread blowout indicates impaired transmission: liquidity exists but cannot flow to where it is needed.

## Balance sheet as binding constraint

The supplementary leverage ratio (SLR) treats all assets at full notional: Treasuries, reserves, and repos receive zero risk-weighting benefit. Dealers face a flat balance sheet tax per dollar of repo regardless of collateral quality.

Netting requires both conditions simultaneously: (1) same counterparty or CCP novation to a single counterparty, and (2) same settlement date allowing right of offset. Failing either condition forces both legs to appear gross on the balance sheet, doubling leverage exposure. Central clearing solves condition (1) via novation. Overnight tenor solves condition (2) via maturity matching.

When balance sheets are constrained, dealers shed bilateral, term, and non-nettable positions first. Those segments see the sharpest rate spikes. This is why quarter-end repo rate spikes concentrate in bilateral markets while GCF remains calmer.

## FHLB-FBO-IORB arbitrage chain

This hidden chain is what anchors EFFR slightly below IORB:

1. FHLBs cannot earn IORB (GSE, wrong master account type) and must lend excess cash in fed funds below IORB
2. Foreign banking organizations (FBOs) are the primary borrowers because they have Fed master accounts, face no FDIC insurance assessment, and have minimal marginal G-SIB score impact from US fed funds activity
3. FBOs borrow below IORB, park at the Fed earning IORB, pocket the spread
4. The FHLB discount note cycle funds this chain: FHLB issues overnight DN to dealer, dealer places with MMF, FHLB receives cash and lends via fed funds to FBO, FBO deploys into reserves

FBO behavior is the invisible hand of EFFR: when FBOs park all reserves at the Fed, EFFR sits close to IORB minus the FHLB spread. When FBOs deploy into repos or FX swaps, EFFR tightens toward IORB. The park-versus-deploy decision sets the marginal fed funds rate daily.

## MMF allocation as regime indicator

Money market funds (~$6T in assets) are rate-maximizing allocators. Their allocation decision between repos, T-bills, agency discount notes, commercial paper, and the Fed RRP determines where system liquidity resides.

**Decision tree:**
- T-bill yield exceeds repo rate by threshold: buy bills, exit RRP, reduce repo lending
- Private repo rate exceeds RRP rate by threshold: lend in private repo, exit RRP
- Private repo approximately equals RRP: park at Fed (risk-free, zero counterparty risk)
- CP/DN yields attractive: diversify into credit instruments

**Behavioral patterns by regime:**
- Normal: spread across repos, bills, some RRP
- QT progressing: rotate from RRP to bills as bill supply rises from Treasury reissuance
- Quarter-end: shift to RRP as dealers shrink and cannot absorb MMF cash, parking at Fed becomes the residual
- Stress: flight to RRP or MMF redemptions, cash hoarding
- Rate cut expectations: front-run by buying longer bills, reducing excess liquidity in overnight markets

MMF allocation shifts are the most visible real-time indicator of regime transitions. When RRP declines because MMFs are buying bills, that is the "free" phase of QT. When RRP approaches zero and reserves begin draining, the system enters the painful phase.

## Shadow money and collateral dynamics

The money supply extends far beyond traditional aggregates. Shadow money is the quantity of instant cash embedded in holding collateral:

**Shadow money = outstanding notional x market price x (1 - haircut)**

The three factors are multiplicative: small moves in each compound into large swings in effective money supply. A simultaneous price decline, haircut increase, and velocity contraction produces a monetary shock that does not appear in any traditional aggregate.

**Collateral velocity** (rehypothecation churn) multiplies the effective shadow money stock. Controlled by approximately 10-14 large dealers globally, velocity contraction is an invisible monetary shock.

**Haircut procyclicality:** haircuts compress in booms (easy terms, confidence high) and spike in crises (tight terms, confidence evaporating). The haircut cycle leads the credit cycle and is a more sensitive leading indicator than interest rates.

**Shadow bank run mechanics:** MMFs refuse to roll repo, CP buyers disappear, securities lenders recall collateral. The Fed has progressively extended backstops (PDCF, MMLF, CPFF, SRF) because shadow banks are too interconnected to fail.

## Settlement timing

Settlement infrastructure operates on rigid, non-overlapping daily timing windows:

**Morning (6:00-10:00 AM):** Trade execution and DVP settlement. Fedwire opens at 8:30 AM. Bulk of repo activity completes by 10:00 AM. Clearing bank charges per-minute fees for negative clearing balances.

**Midday (12:45-1:45 PM):** Fed facility windows. RRP (12:45-1:15 PM) absorbs excess cash. SRF (1:30-1:45 PM) provides emergency collateralized borrowing.

**Afternoon -- the pivot (3:30 PM):** DVP settlement closes and triparty settlement begins simultaneously. This is the single most critical moment in the daily cycle. Securities and cash reposition across systems. The sole triparty agent extends intraday credit during this transition, creating a systemic single point of failure. Any delay cascades.

**Evening (3:30-7:00 PM):** Triparty settlement platform active. New triparty trades settle. Fed clearing accounts adjusted. Fedwire extended hours close at 7:00 PM.

Settlement timing, not end-of-day positions, drives real intraday liquidity risk.

**Settlement Wednesday:** Reserve maintenance periods settle biweekly. The final CHIPS and securities numbers arrive late afternoon. Foreign bank flows after 5 PM are the wild card. A very large share of daily fed funds volume trades in the last two hours before Fedwire close, making this window structurally volatile and positionable.

## QT drain sequencing

QT mechanically shrinks the Fed balance sheet. Three candidate liabilities absorb the drain: reserves, the RRP facility, and the TGA. What drains is the critical variable:

- **RRP drains** (MMFs buy T-bills instead of parking at Fed): painless, excess liquidity redirected. This is the "free" phase.
- **Reserves drain** (banks absorb securities): contractionary, intermediation capacity shrinks. This is the "painful" phase.
- **TGA drains** (Treasury spends down): temporarily adds reserves back to the banking system.

**Sequencing:** RRP drains first, then reserves. The transition occurs when RRP approaches zero. The transition from ample to scarce reserves can be abrupt and localized: aggregate reserves may appear adequate while distribution across institutions is not.

## Window dressing and calendar periodicity

Banks optimize regulatory scores at reporting snapshot dates by shrinking repo books, shifting bilateral to cleared, reducing interbank lending, and building HQLA buffers. Between snapshots, they re-expand.

**Severity gradient:** year-end (G-SIB surcharge snapshot, 5 categories, most intense shrinkage incentive) > quarter-end > month-end. Foreign bank reporting dates create an additional distortion layer.

Predictable distortions include: repo rate spikes, Fed facility usage rises, bid-ask spreads widen, intermediation capacity shrinks, and segment rate differentials blow out (unnettable bilateral segments spike while nettable GCF stays calmer).

## Regime taxonomy

Classify the current money market environment into one of six states:

| State | Name | Key Dynamic |
|-------|------|-------------|
| S1 | Ample Reserves | RRP high, reserves abundant, rates trade in narrow corridor band |
| S2 | Transitional Drain | RRP declining under QT, rates drifting toward upper corridor |
| S3 | Scarce Reserves | RRP near zero, reserves unevenly distributed, repo rates spike above IORB |
| S4 | Quarter/Year-End | Predictable calendar distortion: rate spike, balance sheet shrinkage, segment divergence |
| S5 | Offshore Dollar Shortage | FX swap rates spike above swap line rate, central banks activate swap lines |
| S6 | Shadow Cash Stress | MMF redemptions, repo freeze, CP seizure; Fed activates emergency facilities |

**Transition map:**
- S1 to S2: QT begins or accelerates
- S2 to S3: RRP approaches zero, reserve distribution becomes uneven
- Any state to S4: reporting dates, reverts after (overlay on underlying regime)
- Any state to S5: global dollar shortage, typically triggered by EM stress or geopolitical shock
- Any state to S6: shadow bank run, systemic credit event
- S6 to S1: Fed emergency intervention plus confidence restoration

S4 is an overlay that amplifies whichever base regime (S1, S2, S3) is active. A quarter-end in S1 produces mild distortion. A quarter-end in S3 produces severe dislocation.

## Historical regime episodes

**September 2019 SOFR spike (S2 to S3 transition):** Secured rates spiked above IORB, proving reserve scarcity. Demonstrated that the transition from ample to scarce can be abrupt and localized even when aggregate reserves appear adequate.

**March 2020 ETF discounts (S6):** Authorized participants could not fund arbitrage positions when repo seized. ETF discounts blew out. ETF liquidity is a derivative of repo and CP plumbing health.

**COVID SLR exemption (balance sheet constraint confirmed):** Temporary exclusion of reserves and Treasuries from SLR immediately expanded dealer capacity. Removal contracted it. Confirmed that SLR, not risk-weighted capital, is the binding constraint on dealer intermediation.

## Core assessment framework

Assess the funding environment on six anchors:

- `Reserve Regime`: classify as S1 through S6 using EFFR-IORB spread, RRP usage, reserve level, SOFR volatility, and the transition signals described above
- `Rate Hierarchy Integrity`: are all rates trading within the expected hierarchy, or are there breaks indicating impaired arbitrage, inaccessible facilities, or segment fragmentation
- `Flow Direction`: is the near-term trajectory adding or draining reserves (TGA, QT pace, issuance schedule, tax calendar), and which liability is absorbing the flow
- `Balance Sheet Capacity`: are there calendar-driven frictions (quarter-end, year-end) or structural frictions (regulation, dealer positioning) constraining intermediation, and which segments are most affected
- `Shadow Money Dynamics`: are collateral velocity, haircuts, and rehypothecation capacity expanding or contracting, and is the shadow money supply growing or shrinking
- `MMF Allocation`: where are money market funds deploying cash (RRP, repo, bills, DN, CP), what does the allocation pattern signal about relative rates and liquidity conditions, and is the allocation shifting

## Output tables

### Rate Corridor Dashboard
| Rate | Current | vs IORB (bp) | Hierarchy Signal |
|------|---------|-------------|------------------|
| RRP (floor) | ... | ... | ... |
| Triparty GC | ... | ... | Core dealer funding rate |
| EFFR | ... | ... | FHLB-FBO chain anchor |
| SOFR | ... | ... | Broad secured rate |
| GCF | ... | ... | Core dealer lending rate |
| Bilateral (dealer-to-buyside) | ... | ... | Balance sheet premium |
| IORB | ... | N/A | Administered anchor |
| SRF (ceiling) | ... | ... | Backstop rate |

### Reserve Regime Classification
| Indicator | Value | Regime Signal |
|-----------|-------|---------------|
| EFFR - IORB (bp) | ... | Narrow = ample; widening = scarce |
| RRP usage ($B) | ... | High = excess; declining = QT draining |
| Reserve balances ($T) | ... | Level + distribution |
| SOFR volatility | ... | Rising = scarcity; low = ample |
| Calendar proximity | ... | Next quarter/year-end |
| **Regime Classification** | ... | **S1 / S2 / S3 / S4 / S5 / S6** |

### QT / TGA / Supply Trajectory
| Factor | Current | Direction | Reserve Impact |
|--------|---------|-----------|----------------|
| QT pace ($/mo) | ... | ... | Draining |
| TGA balance ($B) | ... | Rebuilding / Drawing | Adding / Draining |
| RRP remaining ($B) | ... | Declining / Stable | Buffer capacity |
| Bill issuance (net) | ... | Rising / Falling | MMF allocation shift |
| **Net reserve trajectory** | ... | ... | **Adding / Draining / Neutral** |

### MMF Allocation Map
| Destination | Current ($B) | vs 3M Ago | Signal |
|-------------|-------------|-----------|--------|
| Fed RRP | ... | ... | Excess liquidity buffer |
| Private repo | ... | ... | Dealer funding demand |
| T-Bills | ... | ... | Relative yield signal |
| Agency DN | ... | ... | FHLB chain funding |
| CP/CD | ... | ... | Credit appetite |

### Shadow Money Assessment
| Factor | Signal | Direction |
|--------|--------|-----------|
| Collateral velocity | Expanding / Stable / Contracting | ... |
| Haircut trend | Compressing / Stable / Widening | ... |
| Shadow money supply (est.) | Growing / Stable / Shrinking | ... |
| Rehypothecation capacity | Ample / Adequate / Constrained | ... |

### Balance Sheet Constraint Assessment
| Factor | Signal | Implication |
|--------|--------|-------------|
| SLR headroom | Binding / Comfortable | Dealer capacity for unnettable repo |
| Calendar proximity | Days to Q-end/Y-end | Severity of window dressing |
| Netting environment | Cleared share rising/stable | Balance sheet efficiency trend |
| Segment spread (GCF - triparty) | Wide / Normal / Tight | Balance sheet premium |
| Bilateral spread (HF rate - GCF) | Wide / Normal / Tight | Counterparty risk premium |

### Rates Transmission Map
| Channel | Current Signal | Transmits To |
|---------|---------------|-------------|
| Front-end rates | Tightening / Easing / Neutral | Money market funds, front-end curve |
| Swap spreads | Widening / Narrowing / Stable | Front-end especially sensitive to funding |
| Basis trades | Financing cost rising / falling | IRR comparison, basis trade economics |
| Curve shape | Funding-driven steepening/flattening | Front-end anchoring vs uncertainty |
| Volatility | Front-end vol rising / stable | Funding uncertainty premium |
| Cross-currency basis | Widening / Stable / Narrowing | Offshore dollar conditions |

## Evidence that would invalidate this analysis

- a surprise Fed decision on QT pace, SRF terms, or standing facility eligibility changes the corridor dynamics
- a debt ceiling resolution or suspension changes the TGA trajectory
- a QRA announcement changes the issuance mix in ways not anticipated
- a regulatory change (SLR exemption, Basel III endgame, central clearing mandate) alters dealer balance sheet capacity
- a foreign central bank action (FIMA repo, FX intervention, swap line activation) shifts offshore dollar funding conditions
- MMF reform or behavioral shift changes the allocation framework
- a shadow bank stress event changes collateral velocity or haircut dynamics discontinuously

## Output structure

Prefer this output order:

1. `Funding Environment Summary`
2. `Rate Corridor Dashboard` (table)
3. `Reserve Regime Classification` (table with S1-S6 label)
4. `QT / TGA / Supply Trajectory` (table)
5. `MMF Allocation Assessment` (table)
6. `Balance Sheet And Segmentation Assessment` (table)
7. `Shadow Money Assessment` (table)
8. `Rates Transmission Map` (table)
9. `Regime Transition Signals`
10. `Trading Implications`
11. `Next Skill`

Always include:

- the current regime classification (S1-S6) with the key evidence supporting the classification
- whether the system is in transition between regimes and what the transition signals are
- the rate hierarchy and whether any breaks indicate impaired arbitrage or segment fragmentation
- which reserve liability is absorbing QT drain (RRP, reserves, or TGA) and the near-term trajectory
- specific rates transmission channels that are active and how they affect the user's positions
- whether the analysis should feed into `money-market-rv`, `swap-spread-analysis`, `treasury-basis-trading`, or `cross-asset-playbook`

## Best practices

- the plumbing always matters but its importance varies by regime; in ample reserves it is background noise, near scarcity it dominates everything
- the EFFR-IORB spread is the single most important early warning indicator for reserve scarcity
- balance sheet is the scarce resource, not cash; nettable is cheap, unnettable is expensive
- quarter-end and year-end effects are predictable but their magnitude varies; always check the calendar and assess severity relative to the base regime
- repo specialness in specific bonds directly affects basis trade economics; always check before sizing a basis trade
- TGA dynamics are mechanical and predictable given the issuance calendar and tax receipt schedule
- the global dollar rate hierarchy means US funding conditions transmit internationally via FX swap basis
- haircuts are a more sensitive leading indicator than interest rates; the haircut cycle leads the credit cycle
- when RRP approaches zero, the system is transitioning from the free phase to the painful phase of QT; this transition can be abrupt
- the 3:30 PM pivot is the single most critical daily moment; settlement timing, not end-of-day positions, drives intraday liquidity risk
- FBOs are the invisible hand of EFFR; their park-versus-deploy decision sets the marginal fed funds rate
- MMFs are the swing allocator; their behavior is the most visible real-time regime indicator
- do not assume plumbing dislocations resolve quickly; regulatory frictions can sustain them for extended periods
- window dressing is predictable and tradeable

## Usage examples

- "Use `repo-funding-analysis` to classify the current money market regime. SOFR has been volatile and I want to understand whether we are transitioning from S2 to S3."
- "Use `repo-funding-analysis` to evaluate how the upcoming TGA rebuild after the debt ceiling affects my front-end trades and which reserve liability absorbs the drain."
- "Use `repo-funding-analysis` to assess balance sheet constraints heading into quarter-end. I want to know which repo segments will see the largest rate spikes."
- "Use `repo-funding-analysis` to diagnose why the bilateral-GCF spread has blown out. Is it balance sheet or is it something structural?"
- "Use `repo-funding-analysis` to map the funding environment for `money-market-rv`. I need the regime classification and transmission channels before identifying RV opportunities."
