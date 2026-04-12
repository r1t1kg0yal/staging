# Economics of Generative AI

> **Source:** Apoorv Agrawal / Altimeter Capital -- "Tailwinds" newsletter series + Stanford lecture (2024-2026)
> **Domain:** AI Industry Economics / Value Chain Analysis / Consumer AI Metrics / Platform Monetization
> **Last Updated:** April 2026
> **Source Files:** `papers/converted/economics_ai/`

---

## Core Thesis

The generative AI value chain is structurally inverted relative to every prior technology platform. Semiconductors capture ~70% of revenue and ~79% of gross profit -- the exact mirror image of cloud, where applications capture ~70% of profit. This inversion will correct over time, following the pattern of internet, mobile, and cloud platform shifts, but the timeline is likely 10-15 years, not 5. The most profitable strategy in AI today is selling the shovels. The biggest open opportunity is in the application layer.

Consumer AI has crossed 1 billion weekly active users, concentrated in a two-horse race between ChatGPT (~70% share) and Gemini (~20%). ChatGPT is the only AI product exhibiting both the scale and engagement trajectory to become a core utility. The advertising opportunity for leading AI apps may ultimately exceed the subscription opportunity.

---

## Axioms

| ID | Axiom | Implication |
|----|-------|-------------|
| A1 | The AI value chain is inverted: semis capture ~70% of revenue vs ~8% in cloud | Structural distortion between this supercycle and prior ones; the shape must change for AI to reach economic maturity |
| A2 | Every technology platform shift follows Semi -> Infra -> Apps value migration | Internet (10y), mobile (10y), cloud (15y) all exhibited this pattern; AI will too but may take longer |
| A3 | Semi is a one-player game. Apps is a two-player game. Infra is the only competitive layer. | NVIDIA dominates semis; OpenAI+Anthropic dominate apps (~75% of layer); infra has genuine multi-player competition |
| A4 | The incremental user of an AI application is not marginally free | Unlike SaaS at 80-90% gross margins, AI apps run at ~33% gross margins because every query burns GPUs -- this is the physics of the problem |
| A5 | Consumer markets follow a power law: each platform cycle produces one dominant winner | Google took search, Facebook took social, Apple took mobile profits; ChatGPT is on that trajectory for AI |
| A6 | Usage makes headlines; habits build franchises | Downloads spike on hype, usage accrues to apps that earn daily habits; stock (installed base) matters more than flow (downloads) |
| A7 | Time spent is the raw material of monetization | Subscription businesses convert time into willingness to pay; ad businesses convert time into inventory; both start with the same input |
| A8 | Stability in the inverted triangle depends on two variables: custom silicon success and hyperscaler capex discipline | If ASICs break NVIDIA's pricing power, profit migrates up-stack; if capex guidance drops, the current equilibrium breaks |
| A9 | Distribution advantages can be overcome by product quality at sufficient scale | ChatGPT built 900M WAU from scratch without a distribution platform; Gemini reached 200M only by riding Google's 4B existing users |

---

## The AI Value Chain

### Three-Layer Stack Model

```
    ┌─────────────────────────────────────────────────┐
    │                                                 │
    │   ┌─────────────────────────────────────────┐   │
    │   │  APPLICATIONS                           │   │
    │   │  Revenue: $60B  |  GM: ~33%  |  GP: $20B│   │
    │   │  OpenAI, Anthropic = 75% of layer       │   │
    │   │  Then: Cursor, ElevenLabs, Glean, etc.  │   │
    │   └─────────────────────────────────────────┘   │
    │                                                 │
    │   ┌─────────────────────────────────────────┐   │
    │   │  INFRASTRUCTURE                         │   │
    │   │  Revenue: $75B  |  GM: ~55%  |  GP: $40B│   │
    │   │  Azure, AWS, GCP, Oracle ($10-20B each) │   │
    │   │  CoreWeave ~$6B + inference startups    │   │
    │   │  Most competitive layer in the stack    │   │
    │   └─────────────────────────────────────────┘   │
    │                                                 │
    │   ┌─────────────────────────────────────────┐   │
    │   │  SEMICONDUCTORS                         │   │
    │   │  Revenue: $300B  |  GM: ~73%  |  GP:$225│   │
    │   │  NVIDIA ~$250B (data center annualized) │   │
    │   │  Broadcom ~$34B (custom accelerators)   │   │
    │   │  HBM direct purchases ~$25B             │   │
    │   └─────────────────────────────────────────┘   │
    │                                                 │
    │   Total Ecosystem: ~$435B (Q1 2026)             │
    │   Semi captures 70% revenue, 79% gross profit   │
    └─────────────────────────────────────────────────┘

    vs. CLOUD STACK (for comparison):

    ┌─────────────────────────────────────────────────┐
    │  Apps:  $600B revenue  |  70% of gross profit   │
    │  Infra: $300B revenue  |  24% of gross profit   │
    │  Semi:  $80B revenue   |   6% of gross profit   │
    └─────────────────────────────────────────────────┘
```

### Revenue Evolution (Q1 2024 -> Q1 2026)

| Layer | Q1 2024 | Q1 2026 | Growth | $ Added |
|-------|---------|---------|--------|---------|
| Semi | $75B | $300B | 4.0x | $225B |
| Infra | $10B | $75B | 7.5x | $65B |
| Apps | $5B | $60B | 12.0x | $55B |
| **Total** | **$90B** | **$435B** | **4.8x** | **$345B** |

Apps grew fastest in percentage terms (12x). But in absolute dollars, NVIDIA alone added $175B -- roughly 3x the entire app layer.

### Gross Profit Share Evolution

| Layer | 2024 Share | 2026 Share | Cloud Software |
|-------|-----------|-----------|----------------|
| Semi | 87% | 79% | 6% |
| Infra | 10% | 14% | 24% |
| Apps | 3% | 7% | 70% |

At 4 points of profit share gain per 2 years, it would take well over a decade for the app layer to reach cloud-like proportions.

### Gross Margin by Layer

| Layer | AI Stack | Cloud Stack |
|-------|----------|-------------|
| Semi | ~73-85% | ~45% |
| Infra | ~55% (excl. depreciation) / ~25-30% (incl.) | ~63% |
| Apps | ~33% (range: 0-50%) | ~77% |

---

## Semiconductor Layer Deep Dive

### NVIDIA Dominance

```
    NVIDIA Data Center Revenue (annualized)
    ────────────────────────────────────────
    Q1 2024:  ~$75B
    Q1 2026:  ~$250B  ($62B last quarter x 4)

    NVIDIA captures:
    - ~83% of all semi layer revenue
    - Data center GM: ~73-75%
    - ~50% of GPU sales go to top 5 hyperscalers
    - Training : Inference split ≈ 60:40 (shifting toward inference)
```

### Custom Silicon Programs (sorted by maturity)

| Program | Owner | Status | Key Data |
|---------|-------|--------|----------|
| TPU (Ironwood, 7th gen) | Google | Most mature, generally available | Forced NVIDIA to cut pricing ~30% for some customers; Anthropic ordered up to 1M chips |
| Trainium | Amazon | Scaling fast | 1.4M Trainium2 chips deployed; custom chips business >$10B ARR, triple-digit growth; Trainium3 (3nm) in production |
| Custom ASICs | OpenAI + Broadcom | New entrant | Multiyear deal for 10GW of custom accelerators starting 2026; separate 6C deal with AMD for MI450 |
| Maia 200 | Microsoft | Deployed Jan 2026 | Claims 3x inference performance vs Trainium3; powering portion of ChatGPT workloads |
| MTIA v3 | Meta | Internal only | Deployed for internal inference; acquired Rivos (Sept 2025) for RISC-V designs targeting 2026 |

Jensen Huang has dismissed custom ASICs as "noncompetitive," noting "a lot of ASICs get canceled."

### Leading Indicators of NVIDIA Supremacy

1. GPU supply lead times (were ~6 weeks as of original 2024 analysis)
2. Trends in GPU rental pricing
3. Custom silicon competitive traction
4. Training-to-inference ratio shifts

---

## Capex Cycle

### Hyperscaler Capital Expenditure

| Year | Total Capex | AI-Directed (est.) |
|------|------------|-------------------|
| 2024 | $256B | ~$190B |
| 2025 | $443B (+73% YoY) | ~$330B |
| 2026E | >$600B | ~$450B (~75%) |

### CEO Quotes on Capex ROI (Q4 2025 Earnings)

- **Andy Jassy (Amazon):** "As fast as we're adding capacity right now, we're monetizing it."
- **Sundar Pichai (Alphabet):** "We are seeing our AI investments and infrastructure drive revenue and growth across the board." (Also acknowledged "elements of irrationality" in current AI investing scale.)
- **Mark Zuckerberg (Meta):** "I think it's the right strategy to aggressively front load building capacity. In the worst case, we would just slow building new infrastructure for some period while we grow into what we build."

### Compute Capacity Growth

Global AI computing capacity is doubling every 7 months (3.4x/year, 90% CI: 2.8-4.1x/year). Measured in H100-equivalents. Source: Epoch AI.

---

## Stack Flip Timeline

### Historical Platform Shift Durations

```
    Platform Shift        Semi->Apps Value Migration
    ──────────────────    ────────────────────────────
    Internet              ~10 years
    Mobile                ~10 years (Jan 2010 - Nov 2015 for stock perf rotation)
    Cloud                 ~15 years (AWS started 2004, first customer 2010,
                          Amazon on AWS 2012, app-dominated by ~2019)
    AI (projected)        10-15+ years from ~2023 start
```

### Mobile Era Monetization Cycle (Case Study)

```
    2010-2012:  Semiconductors outperform (Qualcomm, ARM)
         │
         ▼
    2012-2014:  Infrastructure / Devices (Samsung, Apple)
         │
         ▼
    2014-2016+: Software + Services (Google, Amazon)
```

The same semi -> infra -> apps rotation is expected in AI, placing us in "Inning 1" as of 2026.

### What Accelerates the Flip

1. Successful custom silicon programs compressing NVIDIA margins
2. Hyperscaler capex guidance declining (implies current equilibrium unsustainable)
3. Inference cost reduction through architecture improvements (SSMs, MoE, quantization, batching, distillation)
4. Application layer achieving positive unit economics at scale

### What Delays the Flip

1. Training compute demand continues growing (new modalities, larger models)
2. Custom silicon programs fail to compete at scale for training
3. App layer gross margins remain structurally low (GPU COGS per user)
4. NVIDIA maintains pricing power through CUDA ecosystem lock-in

---

## Consumer AI Analytics

### Consumer App Tier Framework

```
    ┌──────────────────────────────────────────────────────────────┐
    │  CORE UTILITY (~2-3B WAU)                                    │
    │  YouTube, Chrome, WhatsApp                                   │
    │  Infrastructure-grade. Growth driven by smartphone            │
    │  penetration, not viral loops. Slow and steady.              │
    │                                                              │
    ├──────────────────────────────────────────────────────────────┤
    │  SOCIAL PLATFORMS (~1-1.5B WAU)                              │
    │  Facebook, Instagram, TikTok                                 │
    │  Habitual use driven by content graphs + social              │
    │  reinforcement. Took years to climb here. Plateaued.         │
    │                                                              │
    ├──────────────────────────────────────────────────────────────┤
    │  NICHE APPS (~300-600M WAU)                                  │
    │  Spotify, Amazon, X                                          │
    │  Category leaders serving specific needs.                    │
    │  Frequent but not universal.                                 │
    │                                                              │
    ├──────────────────────────────────────────────────────────────┤
    │  AI STATUS (as of Q1 2026):                                  │
    │  ChatGPT (~900M WAU) -- cleared Niche, entering Social tier  │
    │  Gemini (~200M WAU) -- entering Niche tier from below        │
    │  Everyone else (<50M WAU) -- fighting over scraps            │
    │                                                              │
    │  ChatGPT reached Social tier in ~3 years                     │
    │  (Instagram took 5, TikTok took 4)                           │
    └──────────────────────────────────────────────────────────────┘
```

### AI App Market Share (WAU, Q1 2026)

| App | WAU | Share | Notes |
|-----|-----|-------|-------|
| ChatGPT | ~900M | ~70% | Built from scratch, no distribution platform |
| Gemini | ~200-250M | ~15-20% | Riding Google's 4B user distribution |
| DeepSeek | <50M | ~3% | Spike in Jan 2025, faded quickly |
| Character AI | <50M | ~2% | Entertainment/persona use case |
| Grok | <50M | ~2% | Distribution through X |
| Perplexity | <50M | ~2% | Search-focused |
| Claude | <50M | ~1% | Recently hit #1 in App Store |

Total AI app WAUs: ~1.2B (Feb 2026). Up ~20x from ~100M in Jan 2024.

### The Four Seasons Pattern (Challenger Waves)

```
    WINTER 2025: China (DeepSeek)
    ├── 25M+ weekly downloads, briefly rivaled ChatGPT
    ├── Open-source performance caught industry off guard
    └── Downloads collapsed within weeks

    SPRING 2025: XAI (Grok)
    ├── Distribution through X + model updates
    ├── Downloads spiked, press followed
    └── Sustained usage never materialized

    SUMMER 2025: Google (Gemini)
    ├── Weekly downloads surged >20M around Google I/O
    ├── Driven by nano banana viral image generation
    └── Model moment, not behavioral shift

    EVERY SEASON: OpenAI (ChatGPT)
    ├── Consistent downloads at or near top, week after week
    ├── No volatility; steady compounding
    └── Attention is easy to capture; daily habits are hard to build
```

---

## Engagement Metrics

### DAU:MAU Ratio (AI Apps)

| App | DAU:MAU | Interpretation |
|-----|---------|---------------|
| ChatGPT | 45% | 2x gap over next competitor |
| Claude | 37% | Quiet standout, huge recent leap |
| Character AI | 36% | Entertainment-driven engagement |
| DeepSeek | 29% | |
| Grok | 24% | |
| Gemini | 22% | Despite 750M reported MAU, depth of daily use is low |
| Perplexity | 20% | |

### WAU:MAU Ratio (Cross-Category Comparison)

| Category | App | WAU:MAU |
|----------|-----|---------|
| **Gen AI** | ChatGPT | 82% |
| | Claude | 70% |
| | DeepSeek | 65% |
| | Character AI | 63% |
| | Grok | 59% |
| | Gemini | 57% |
| | Perplexity | 57% |
| **Consumer** | WhatsApp | 96% |
| | Chrome | 95% |
| | YouTube | 92% |
| | Instagram | 92% |
| | Facebook | 87% |
| | TikTok | 80% |
| | Spotify | 79% |
| | X | 77% |
| | Amazon | 74% |
| **Enterprise** | Slack | 82% |
| | Outlook | 80% |
| | Gmail | 78% |
| | Teams | 71% |
| | G Calendar | 67% |
| | Notion | 56% |
| | G Docs | 55% |
| | Zoom | 47% |

ChatGPT's WAU:MAU improved from ~50% (mid-2023) to 82% (Q1 2026). A 30+ point improvement. No other AI app has achieved this except Claude (recent sharp rise).

Threshold insight: apps need 80%+ WAU:MAU to reach 1B users.

### Retention

#### 4-Week Retention

| App | 4-Week Retention |
|-----|-----------------|
| ChatGPT | 66% |
| Character AI | 48% |
| Gemini | 44% |
| Claude | 41% |
| DeepSeek | 37% |
| Grok | 37% |
| Perplexity | 24% |

ChatGPT's 4-week retention improved from ~40% (2023) to 66% (2026) -- a 25 point gain while adding hundreds of millions of users. Most apps see retention flatten or decline as user base matures.

#### Retention Curve Shapes

```
    Three shapes after initial drop-off:

    DECLINING        FLATTENING         SMILING
    ────────         ──────────         ───────
    ╲                ╲___________       ╲    ╱
     ╲                                   ╲  ╱
      ╲                                   ╲╱
       ╲
    Most apps        WhatsApp,           Gmail, ChatGPT,
                     Instagram,          Chrome
                     TikTok,
                     Spotify, Slack

    The smile curve is the rarest signal.
    It means product improvements are pulling lapsed users back.
    ChatGPT is doing this at 900M WAU scale.
```

---

## Time Spent Analysis

### Minutes Per Day Per User (Mobile, Q1 2026)

| Category | App | Min/Day |
|----------|-----|---------|
| **Gen AI** | Character AI | 83 |
| | DeepSeek | 25 |
| | Claude | 19 |
| | Gemini | 17 |
| | Grok | 17 |
| | ChatGPT | 16 |
| | Perplexity | 8 |
| **Consumer** | TikTok | 91 |
| | YouTube | 83 |
| | Instagram | 72 |
| | Facebook | 45 |
| | WhatsApp | 41 |
| | X | 34 |
| | Chrome | 26 |
| | Spotify | 8 |
| **Enterprise** | Zoom | 24 |
| | Microsoft | 8 |
| | Google Docs | 7 |
| | Notion | 6 |
| | Slack | 6 |
| | Microsoft 4 | 4 |
| | Gmail | 3 |
| | G Calendar | 2 |

Total AI app time grew ~10x over past 2 years, 3.6x in 2025 alone. ChatGPT owns 68% of total AI time spent.

ChatGPT lacks the two drivers of massive consumer time: (1) social network effects and (2) dopamine loops. It behaves more like a productivity tool than a social feed -- which is actually a strong signal for monetization.

---

## Monetization Framework

### Revenue = Price x Quantity

```
    PARTS 1 & 2 ESTABLISHED Q (QUANTITY):
    ┌─────────────────────────────────────────────┐
    │  Users:      900M WAU, ~70% market share    │
    │  Engagement: 45% DAU:MAU, 82% WAU:MAU       │
    │  Retention:  66% at 4-weeks, smile curve     │
    │  Time:       16 min/day, 68% of AI attention │
    └─────────────────────────────────────────────┘

    PART 3 ESTABLISHES P (PRICE):
    ┌─────────────────────────────────────────────┐
    │  Subscriptions vs Advertising                │
    │  Ad Revenue = Time x Ad Volume x Ad Price   │
    └─────────────────────────────────────────────┘
```

### Subscriptions vs Advertising (Scale Comparison)

| Company | Revenue Model | 2025 Revenue | Users | ARPU |
|---------|--------------|-------------|-------|------|
| **Ad-Dominant** | | | | |
| Google | Ads | ~$295B | ~3.3B DAU | ~$84/yr |
| Meta | Ads | ~$195B | ~3.6B DAP | ~$57/yr |
| Amazon (ads) | Ads | ~$65B | N/A | N/A |
| TikTok | Ads | ~$33B | ~0.9B DAU | ~$20/yr |
| **Sub-Dominant** | | | | |
| Amazon (Prime) | Subs | ~$50B | ~240M | ~$17/mo |
| Netflix | Subs | ~$45B | ~302M | ~$12/mo |
| Disney+ / Hulu | Subs | ~$25B | ~196M | ~$8-12/mo |
| Spotify | Subs | ~EUR16B | ~290M | ~EUR4.85/mo |
| **AI** | | | | |
| OpenAI | Subs + early ads | ~$25B (est.) | ~900M WAU | ~$10/yr |

Google's ad business alone is ~5x Netflix revenue. The magnitude gap at scale favors advertising.

### Ad Revenue Formula Applied to ChatGPT

```
    Ad Revenue = Total Time x Ad Volume x Price of Ads

    TOTAL TIME (known):
    ├── 900M WAU
    ├── 45% DAU:MAU
    └── 16 min/day on mobile

    AD VOLUME (currently minimal):
    ├── At most 1 ad per conversation
    ├── Only ~5% of mobile users see ads
    └── Enormous room to scale without matching Meta/Google loads

    PRICE OF ADS (CPM -- cost per thousand impressions):
    ├── Driven by: intent, attribution, audience quality
    ├── Google Search CPM: $15-200+ (high intent)
    ├── Meta CPM: lower intent, compensated by targeting precision
    ├── OpenAI early premium placements: ~$60 CPM
    └── AI queries often carry richer commercial context than search
```

### ChatGPT Ad Revenue Scenario

```
    ~800-900M free users (95% of WAU)
    x $30 annual ad revenue per free user
    ────────────────────────────────────
    = ~$25B in ad revenue at current scale

    Benchmark: Meta = $57/user, Google = $84/user
    $30 for a high-intent, logged-in product is not aggressive.
```

### Search Unit Economics

| Metric | Traditional Search | LLM-Based Search |
|--------|-------------------|------------------|
| Cost per query | 0.3 cents | 3-30 cents |
| Revenue per query | 4.5 cents | 2.5-3.5 cents |
| Profitability | Highly profitable | Currently unprofitable |

LLM queries are taking share from informational searches but are currently unprofitable on a per-query basis. The crossover depends on inference cost reduction and ad load scaling.

### Google's Strategic Luxury

Google can subsidize Gemini as a loss leader because it has a $295B ad cash machine in Search. It monetizes AI through AI Overviews and AI Mode in Search (which already carry ads), while keeping Gemini ad-free to grow users. OpenAI has no separate cash cow -- it must monetize the chat interface directly. Whether Google can maintain the ad-free Gemini stance as inference costs rise and MAU scales past 750M is an open question.

---

## Consumer AI Monetization Path

```
    TODAY'S EQUATION:
    ┌──────────────────────────────────────────────────────┐
    │  Alphabet:  ~4B users   x  ~$100/user/yr  =  ~$400B │
    │  Meta:      ~3.5B users x  ~$70/user/yr   =  ~$245B │
    │  OpenAI:    ~1B users   x  ~$10/user/yr    =  ~$10B  │
    └──────────────────────────────────────────────────────┘

    TWO GROWTH VECTORS:
    ────────────────────

    1. Users: 1B -> 4B
       Requires going beyond knowledge work.
       Knowledge workers are not 100% of online population.

    2. ARPU: $10 -> $100
       Subscriptions alone unlikely to bridge the gap.
       Ads appear necessary. Intent-rich conversational ads
       could command Google-like CPMs.

    EXECUTION CONSTRAINT:
    ─────────────────────
    Must monetize the habit without degrading the product
    that created it. Trust is the most valuable asset.
    Conversational ads that improve the experience
    (embedded recommendations vs. bolted-on banners)
    are the optimistic path.
```

---

## Key Data Points for Quick Reference

### Scale Milestones

| Metric | Value | Date |
|--------|-------|------|
| Total AI ecosystem revenue | ~$435B annualized | Q1 2026 |
| AI ecosystem revenue 2 years prior | ~$90B | Q1 2024 |
| NVIDIA data center revenue (quarterly) | ~$62B | Q1 2026 |
| Total hyperscaler capex (2025) | ~$443B | 2025 |
| Projected hyperscaler capex (2026) | >$600B | 2026E |
| Global compute capacity doubling time | ~7 months | 2025 |
| Total AI app WAU | ~1.2B | Feb 2026 |
| ChatGPT WAU | ~900M | Q1 2026 |
| ChatGPT DAU:MAU | 45% | Q1 2026 |
| ChatGPT WAU:MAU | 82% | Q1 2026 |
| ChatGPT 4-week retention | 66% | Q1 2026 |
| ChatGPT time per user (mobile) | 16 min/day | Q1 2026 |
| ChatGPT share of AI attention | 68% | Q1 2026 |
| OpenAI annualized revenue | ~$25B (est.) | Q1 2026 |
| OpenAI free user percentage | ~95% | Q1 2026 |

### Concentration Metrics

| Layer/Category | Top Player Share | Top 2 Share |
|---------------|-----------------|-------------|
| AI Semis (revenue) | NVIDIA ~83% | NVIDIA + Broadcom ~95% |
| AI Apps (revenue) | OpenAI ~50% | OpenAI + Anthropic ~75% |
| AI Apps (WAU) | ChatGPT ~70% | ChatGPT + Gemini ~90% |
| AI Apps (time spent) | ChatGPT ~68% | ChatGPT + Gemini ~84% |
| AI Infra (revenue) | No single dominant player | Relatively evenly distributed |

---

## Analytical Frameworks

### Framework 1: Value Chain Inversion Analysis

**Purpose:** Assess where value accrues in the AI stack relative to historical platform shifts.

**Process:**
1. Decompose the AI stack into Semi / Infra / Apps layers
2. Estimate revenue and gross margin for each layer
3. Compute gross profit share by layer
4. Compare current distribution to Cloud stack (the steady-state benchmark)
5. Track the delta over time -- rate of convergence toward cloud-like shape
6. Identify catalysts and inhibitors for the flip

**Key question:** At what rate is app-layer profit share growing? (Currently ~2 points/year)

### Framework 2: Consumer App Tier Classification

**Purpose:** Place any consumer product on the utility/social/niche spectrum to assess its growth ceiling and monetization path.

**Dimensions:**
- WAU absolute level (Core Utility >2B, Social 1-1.5B, Niche 300-600M)
- WAU:MAU engagement (>80% = utility grade)
- 4-week retention (>60% = franchise territory)
- Time per user per day
- Retention curve shape (declining / flat / smile)
- Stock vs flow (installed base vs new downloads)

### Framework 3: Ads vs Subs Monetization Sizing

**Purpose:** Estimate total addressable monetization for a consumer AI product.

**Formula:** `Ad Revenue = Total Time x Ad Volume x Price of Ads`

**Variables to track:**
- Total time = WAU x DAU:MAU x minutes/day
- Ad volume = ads per session (currently ~0 for most AI apps)
- Ad price = CPM, driven by intent quality, attribution, audience
- Benchmark against Google ($84 ARPU), Meta ($57 ARPU)
- Subscription overlay: paying subscribers x monthly ARPU

### Framework 4: Platform Shift Inning Detection

**Purpose:** Determine where we are in the AI platform shift.

```
    Inning 1 (Semi):      Value captured by hardware / compute providers
    Inning 2 (Infra):     Cloud / serving / orchestration layer captures share
    Inning 3 (Apps):      Application layer matures and captures majority

    CURRENT STATE: Late Inning 1 / Early Inning 2
    ──────────────────────────────────────────────
    - Semi still 70% of revenue, 79% of GP
    - But infra and apps each gained ~4 pts of profit share in 2 years
    - Custom silicon is the key transition variable
    - App layer profitability still structurally challenged (33% GM)
```

---

## Chart Specifications

Charts PRISM can reproduce from this data. Each uses the `make_chart()` system.

### Chart 1: AI Revenue Stacked Bar (2024 vs 2026)

```python
data = {
    'categories': ['Q1 2024', 'Q1 2026'],
    'Semi': [75, 300],
    'Infra': [10, 75],
    'Apps': [5, 60]
}
# Stacked bar, totals annotated: $90B and $435B
# Y-axis: AI Revenue ($B)
```

### Chart 2: Gross Profit Share (AI-2024, AI-2026, Cloud)

```python
data = {
    'categories': ['AI - 2024', 'AI - 2026', 'Cloud Software'],
    'Semi': [87, 79, 6],
    'Infra': [10, 14, 24],
    'Apps': [3, 7, 70]
}
# Stacked bar, 100% scale
```

### Chart 3: AI App WAU Time Series

```python
# Line chart, weekly data from Mar 2023 to Apr 2026
# Series: ChatGPT (dominant, rising to 900M), Gemini (rising to ~200M), rest flat near bottom
# Y-axis: Weekly Active Users (log or linear)
```

### Chart 4: Consumer App Tier Comparison

```python
# Line chart overlaying AI apps on consumer app WAU history
# Annotated tier bands: Core Utility (2-3B), Social (1-1.5B), Niche (300-600M)
# ChatGPT trajectory crossing into Social tier
```

### Chart 5: Engagement Cross-Category Bar

```python
data = {
    'Gen AI': {'ChatGPT': 82, 'Claude': 70, 'DeepSeek': 65, 'Character AI': 63, 'Grok': 59, 'Gemini': 57, 'Perplexity': 57},
    'Consumer': {'WhatsApp': 96, 'Chrome': 95, 'YouTube': 92, 'Instagram': 92, 'Facebook': 87, 'TikTok': 80, 'Spotify': 79, 'X': 77, 'Amazon': 74},
    'Enterprise': {'Slack': 82, 'Outlook': 80, 'Gmail': 78, 'Teams': 71, 'G Calendar': 67, 'Notion': 56, 'G Docs': 55, 'Zoom': 47}
}
# Horizontal bar, color-coded by category
# Metric: WAU:MAU (%)
```

### Chart 6: Stock vs Flow Scatter

```python
# X-axis: Weekly Active User Base (installed stock)
# Y-axis: New Weekly Downloads (flow)
# Quadrants: ChatGPT (high stock, high flow), Social (high stock, moderate flow),
#            Core Utility (highest stock, lower flow), Niche (lower both)
```

### Chart 7: Time Spent Cross-Category Bar

```python
# Horizontal bar: Gen AI / Consumer / Enterprise apps
# Color-coded by category
# Metric: Minutes per day per user
# Character AI anomaly at 83 min (entertainment use case)
```

### Chart 8: Revenue Model Comparison (Ads vs Subs)

```python
# Horizontal stacked bar by company
# Segments: Advertising (blue), Subscriptions (green), Other (gray)
# Companies: Alphabet, Meta, Amazon, TikTok, Netflix, Disney, Spotify, OpenAI
```

---

## Source Index

| # | Title | Author | Date | Key Contribution |
|---|-------|--------|------|-----------------|
| 1 | The Economics of Generative AI | Apoorv Agrawal | Apr 2024 | Original inverted value chain framework; semi/infra/apps revenue and GP breakdown; mobile era case study |
| 2 | The Economics of Generative AI: Two Years Later | Apoorv Agrawal | Apr 2026 | Updated stack to $435B; NVIDIA $250B; custom silicon landscape; stack flip timeline revision |
| 3 | Stanford Lecture Transcript | Apoorv Agrawal | 2026 | Live Q&A; deeper discussion on training vs inference split, Gemini positioning, stable equilibrium debate |
| 4 | The State of Consumer AI Part 1: Usage | Apoorv Agrawal | Mar 2026 | 1B+ WAU milestone; consumer tier framework; four seasons pattern; ChatGPT as potential utility |
| 5 | The State of Consumer AI Part 2: Engagement and Retention | Apoorv Agrawal | Mar 2026 | DAU:MAU and WAU:MAU analysis; smile curve discovery; retention improving at scale; cross-category benchmarks |
| 6 | The State of Consumer AI Part 3: Time is Money | Apoorv Agrawal | Mar 2026 | Time spent analysis; ads vs subs framework; $25B ad revenue scenario; Google strategic luxury argument |
