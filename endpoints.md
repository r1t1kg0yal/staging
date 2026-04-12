━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FULL ENDPOINT REGISTRY -- 21 APIs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 #   API                     Base URL                                    Endpoints / CLI Commands
 ──   ─────────────────────   ──────────────────────────────────────────   ──────────────────────────────

 1.  Treasury Fiscal Data    api.fiscaldata.treasury.gov                  81 endpoints in ENDPOINT_REGISTRY
     treasury/treasury.py                                                 DTS, MTS, debt, rates, CUSIP,
                                                                          auctions, revenue, field discovery

 2.  TreasuryDirect          treasurydirect.gov                           REST endpoints:
     treasurydirect/                                                       - Securities: announced/auctioned/search
     treasurydirect.py                                                     - Debt-to-the-Penny
                                                                           - RSS, reports, forms
                                                                           + bulk jobs + site crawl

 3.  FDIC BankFind           api.fdic.gov/banks                           8 endpoints:
     fdic/fdic.py                                                          - /institutions
                                                                           - /financials (Call Reports)
                                                                           - /failures
                                                                           - /sod (Summary of Deposits)
                                                                           - /demographics
                                                                           + branches, history

 4.  SEC EDGAR               data.sec.gov + efts.sec.gov                  Endpoints:
     sec_edgar/sec_edgar.py                                                - /submissions (company filings)
                                                                           - /api/xbrl/companyfacts (XBRL data)
                                                                           - /api/xbrl/frames (cross-company)
                                                                           - /efts/search (full-text search)
                                                                           - /Archives (filing documents)
                                                                           17 CLI commands

 5.  Prediction Markets      api.elections.kalshi.com                     Kalshi endpoints:
     prediction_markets/     gamma-api.polymarket.com                      - Events, contracts, orderbooks
     prediction_markets.py                                                 - Price history
                                                                          Polymarket endpoints:
                                                                           - Events, markets, prices
                                                                          11 CLI commands + autopilot

 6.  BIS SDMX                stats.bis.org/api/v2                         SDMX endpoints:
     bis/bis.py                                                            - /dataflow (list datasets)
                                                                           - /data/{dataflow} (observations)
                                                                           - /structure/dimensions
                                                                           - /structure/codelists
                                                                           - /structure/codes
                                                                           29 datasets (LBS, credit, debt,
                                                                           property, FX, derivatives)

 7.  Substack                {subdomain}.substack.com/api/v1              Endpoints:
     substack/substack.py                                                  - /archive (post listing)
                                                                           - /posts/{slug} (full body)
                                                                           - /publication/search
                                                                           - /category/public/{id}/all
                                                                           46 curated finance Substacks

 8.  CFTC COT                publicreporting.cftc.gov                     Socrata endpoints:
     cftc/cftc.py            (Socrata API)                                 - gpe5-46if (TFF futures)
                                                                           - 72hh-3qpy (Disaggregated)
                                                                           25 curated contracts
                                                                           14 CLI commands

 9.  EIA Energy              api.eia.gov/v2                               Hierarchical route endpoints:
     eia/eia.py                                                            - /petroleum (inventories, production)
                                                                           - /natural-gas (storage, prices)
                                                                           - /steo (supply/demand forecasts)
                                                                           14 curated series
                                                                           12 CLI commands

10.  OpenFIGI               api.openfigi.com/v3                           Endpoints:
     openfigi/openfigi.py                                                  - /mapping (batch identifier map)
                                                                           - /search (free-text search)
                                                                           - /filter (structured filter)
                                                                           - /mapping/values (enum reference)
                                                                           11 CLI commands

11.  NY Fed Markets          markets.newyorkfed.org/api                   Endpoints:
     nyfed/nyfed.py                                                        - /rates (SOFR, BGCR, TGCR, OBFR, EFFR)
                                                                           - /rates/sofr (30/90/180-day avg + index)
                                                                           - /soma (holdings summary, weekly)
                                                                           - /repo (daily operations)
                                                                           - /rrp (reverse repo)
                                                                           - /pd (primary dealer stats)
                                                                           12 CLI commands

12.  RSS Aggregator          feedparser (19 curated feeds)                 Feed categories:
     rss/rss.py                                                            - Fed blogs (6): Liberty St, FEDS Notes,
                                                                             Chicago, StL, SF, Richmond
                                                                           - Think tanks (5): Brookings, PIIE,
                                                                             Cato, AEI, Heritage
                                                                           - Academic (3): NBER, VoxEU, IMF Blog
                                                                           - Central bank (3): ECB, BoE, BIS
                                                                           - Macro analysis (2): Calc Risk, Econbrowser
                                                                           10 CLI commands

13.  GDELT                   api.gdeltproject.org/api/v2/                 4 API endpoints:
     gdelt/gdelt.py                                                        - DOC 2.0 (full-text news, 3mo rolling)
                                                                           - TV 2.0 (163 TV stations, 2009+)
                                                                           - Context 2.0 (sentence-level, 72hr)
                                                                           - GEO 2.0 (geographic event mapping)
                                                                           18 CLI commands

14.  Federal Register        federalregister.gov/api/v1                   Endpoints:
     federal_register/                                                     - /documents.json (search/list)
     federal_register.py                                                   - /documents/{id}.json (detail)
                                                                           - /public-inspection-documents.json
                                                                           - /agencies.json (registry)
                                                                           17 curated agencies
                                                                           11 CLI commands

15.  Congress.gov            api.congress.gov/v3                           Endpoints:
     congress/congress.py                                                  - /bill (list/search)
                                                                           - /bill/{congress}/{type}/{num}
                                                                             (detail, actions, cosponsors,
                                                                              summaries, text)
                                                                           - /member
                                                                           - /nomination
                                                                           - /amendment
                                                                           10 curated macro topics
                                                                           11 CLI commands

16.  DTCC SDR                kgc0418-tdw-data-0.s3.amazonaws.com          S3 bulk data (daily zips):
     dtcc/dtcc.py                                                          - Interest Rates (CFTC + SEC)
                                                                           - Credits/CDS (CFTC + SEC)
                                                                           - FX (CFTC + SEC)
                                                                           - Equities (CFTC + SEC)
                                                                           - Commodities (CFTC + SEC)
                                                                           12 CLI commands

17.  USASpending.gov         api.usaspending.gov/api/v2                   Endpoints:
     usaspending/                                                          - /agency/ (budget by agency)
     usaspending.py                                                        - /spending/ (aggregate spending)
                                                                           - /recipient/ (award search)
                                                                           - /awards/ (award detail)
                                                                           - /search/ (full-text awards)
                                                                           17 curated agencies, 9 groups
                                                                           12 CLI commands

18.  Wikipedia Pageviews     wikimedia.org/api/rest_v1/metrics/pageviews  Endpoints:
     wikipedia/wikipedia.py                                                - /per-article (daily/monthly views)
                                                                           - /aggregate (all-wiki totals)
                                                                           - /top (most viewed)
                                                                           36 curated macro articles, 7 themes
                                                                           12 CLI commands

19.  USITC Tariff (HTS)     hts.usitc.gov/reststop                       Endpoints:
     tariffs/tariffs.py                                                    - Chapter listing (99 chapters)
                                                                           - Tariff line lookup
                                                                           - Search, rate queries
                                                                           8 curated macro sectors
                                                                           12 CLI commands

20.  OFAC Sanctions          treasury.gov/ofac/downloads                  Data files:
     ofac/ofac.py                                                          - SDN list (CSV, ~12k entities)
                                                                           - Alt names, addresses
                                                                           8 curated program groups
                                                                           12 CLI commands

21.  Electricity Grids       api.eia.gov/v2/electricity/rto               Endpoints:
     electricity/                                                          - /demand (hourly demand)
     electricity.py                                                        - /fuel-type-data (generation by fuel)
                                                                           - /interchange (regional flows)
                                                                           14 curated balancing authorities
                                                                           12 CLI commands

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TOTALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 APIs:              21
 CLI commands:      ~240 (interactive + argparse mirrored)
 REST endpoints:    ~150+ distinct HTTP routes (Treasury alone = 81)
 Datasets:          29 (BIS) + 25 contracts (CFTC) + 14 series (EIA)
                    + 46 Substacks + 19 RSS feeds + 36 Wiki articles
 Auth required:     3 (EIA key, Congress key, SEC User-Agent header)
 Fully public:      18 (no auth at all)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━