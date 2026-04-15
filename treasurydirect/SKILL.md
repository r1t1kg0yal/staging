# TreasuryDirect.gov Comprehensive Scraper

Script: `GS/data/apis/treasurydirect/treasurydirect.py`
Base URL: `https://www.treasurydirect.gov`
Auth: None required
Rate limit: ~0.5s between calls (polite usage)
Dependencies: `requests`, `beautifulsoup4`, `lxml`, `openpyxl`; optional `pdftotext` (from `poppler-utils`) for PDF-to-markdown conversion


## Triggers

Use for: Treasury auction results (Bill/Note/Bond/TIPS/FRN/CMB), CUSIP-level auction lookup, bid-to-cover ratios, auction tails, direct/indirect/dealer allocation, debt-to-the-penny (current + historical), MSPD reports, savings bond rate tables, quarterly refunding documents, auction announcement/result PDFs, historical XML auction files, RSS feed monitoring.

Not for: overnight reference rates (NY Fed), yield curve / term structure (Treasury Fiscal Data / FRED), OTC derivatives volumes (DTCC), futures positioning (CFTC), bank-level financials (FDIC), primary dealer positioning (NY Fed), TGA cash balances (Treasury Fiscal Data DTS), commercial paper / CD rates (FRED).


## Data Catalog

### Security Types

| Key | Description |
|-----|-------------|
| `Bill` | Treasury Bills (4w, 8w, 13w, 17w, 26w, 52w) |
| `Note` | Treasury Notes (2y, 3y, 5y, 7y, 10y) |
| `Bond` | Treasury Bonds (20y, 30y) |
| `TIPS` | Treasury Inflation-Protected Securities (5y, 10y, 30y) |
| `FRN` | Floating Rate Notes (2y) |
| `CMB` | Cash Management Bills (irregular) |

### Securities API Endpoints

| Key | URL | Description |
|-----|-----|-------------|
| `announced` | `/TA_WS/securities/announced` | Upcoming auctions |
| `auctioned` | `/TA_WS/securities/auctioned` | Completed auctions |
| `search` | `/TA_WS/securities/search` | Search by type, date range, CUSIP |

### Debt API Endpoints

| Key | URL | Description |
|-----|-----|-------------|
| `current` | `/NP_WS/debt/current` | Latest debt-to-the-penny |
| `search` | `/NP_WS/debt/search` | Historical debt by date range |

### RSS Feeds

| Label | URL |
|-------|-----|
| Treasury Offering Announcements | `/TA_WS/securities/announced/rss` |
| Treasury Auction Results | `/TA_WS/securities/auctioned/rss` |
| Debt to the Penny | `/NP_WS/debt/feeds/recent` |
| Monthly Statement Public Debt | `/rss/mspd.xml` |
| Savings Bonds Pro Updates | `/rss/sbpro.xml` |

### Report Pages

| Label | Path |
|-------|------|
| Public Debt Reports | `/government/public-debt-reports/` |
| SBN Tables & Downloads | `/government/public-debt-reports/us-savings-bonds-and-notes/` |
| Federal Investment Reports | `/government/federal-investments-program/federal-investments-reports/` |
| Savings Bonds Rates | `/savings-bonds/i-bonds/i-bonds-interest-rates/` |
| EE Bonds Rates | `/savings-bonds/ee-bonds/ee-bonds-interest-rates/` |
| Useful Research Data | `/auctions/announcements-data-results/useful-data-for-research/` |

### Forms Pages

| Label | Path |
|-------|------|
| Marketable Securities Forms | `/marketable-securities/forms/` |
| General Forms | `/forms/` |

### Auction Record Fields (per security)

| Field | Type | Description |
|-------|------|-------------|
| `auctionDate` | string | Date of auction |
| `cusip` | string | CUSIP identifier |
| `securityType` | string | Bill, Note, Bond, TIPS, FRN, CMB |
| `securityTerm` | string | Maturity term (e.g. "13-Week", "10-Year") |
| `interestRate` | string | Coupon rate |
| `highYield` | string | Stop-out yield (highest accepted) |
| `averageMedianYield` | string | Average/median yield |
| `lowYield` | string | Lowest yield bid |
| `tailBps` | float | Computed: (highYield - averageMedianYield) * 100 bp |
| `pricePer100` | string | Price per $100 par |
| `bidToCoverRatio` | string | Total tendered / total accepted |
| `offeringAmount` | string | Total offering amount |
| `totalAccepted` | string | Total accepted at auction |
| `totalTendered` | string | Total tendered at auction |
| `competitiveAccepted` | string | Competitive bids accepted |
| `competitiveTendered` | string | Competitive bids tendered |
| `directBidderAccepted` | string | Direct bidder allocation |
| `directBidderTendered` | string | Direct bidder tendered |
| `indirectBidderAccepted` | string | Indirect bidder allocation |
| `indirectBidderTendered` | string | Indirect bidder tendered |
| `primaryDealerAccepted` | string | Primary dealer allocation |
| `primaryDealerTendered` | string | Primary dealer tendered |
| `allocationPercentage` | string | Allocation percentage |
| `somaAccepted` | string | SOMA (Fed) accepted amount |
| `maturityDate` | string | Maturity date |
| `issueDate` | string | Issue/settlement date |
| `reopening` | string | Whether this is a reopening |

### Auction PDF Fields

| Field | Description |
|-------|-------------|
| `pdfFilenameAnnouncement` | Auction announcement PDF filename |
| `pdfFilenameCompetitiveResults` | Competitive results PDF filename |
| `pdfFilenameNoncompetitiveResults` | Noncompetitive results PDF filename |
| `pdfFilenameSpecialAnnouncement` | Special announcement PDF filename |

### Debt Record Fields

| Field | Type | Description |
|-------|------|-------------|
| `totalDebt` | string | Total public debt outstanding |
| `totalPublicDebtOutstanding` | string | Total public debt outstanding (alt key) |
| `tot_pub_debt_out_amt` | string | Total public debt outstanding (alt key) |


## CLI Recipes

Two command modes: `api` for quick lookups, `job` for bulk downloads. Global flags: `--output DIR`, `--quiet`.

### API -- CUSIP Lookup

```bash
# Look up a single CUSIP (auction details, yield, bid-to-cover, tail)
python treasurydirect.py api cusip 91282CQJ3
python treasurydirect.py api cusip 912797LN1
python treasurydirect.py api cusip 91282CHR1
```

### API -- Recent Auctions

```bash
# All types, last 365 days (default)
python treasurydirect.py api auctions

# Filter by type
python treasurydirect.py api auctions --type Bill
python treasurydirect.py api auctions --type Note
python treasurydirect.py api auctions --type Bond
python treasurydirect.py api auctions --type TIPS
python treasurydirect.py api auctions --type FRN
python treasurydirect.py api auctions --type CMB

# Control date window
python treasurydirect.py api auctions --type Bill --days 30
python treasurydirect.py api auctions --type Note --days 90
python treasurydirect.py api auctions --days 7

# Combine type + window
python treasurydirect.py api auctions --type Bond --days 180
```

### API -- Debt to the Penny

```bash
# Current debt snapshot
python treasurydirect.py api debt

# Historical debt by date range
python treasurydirect.py api debt --start 2024-01-01
python treasurydirect.py api debt --start 2024-01-01 --end 2024-12-31
python treasurydirect.py api debt --start 2020-01-01 --end 2025-01-01
```

### API -- Treasury Buybacks

```bash
# All buyback operations (from Treasury Fiscal Data API)
python treasurydirect.py api buybacks

# Liquidity Support only (off-the-run repurchases)
python treasurydirect.py api buybacks --type "Liquidity Support"

# Cash Management only
python treasurydirect.py api buybacks --type "Cash Management"

# Only operations with completed results
python treasurydirect.py api buybacks --results-only

# Date range
python treasurydirect.py api buybacks --from-date 2025-01-01 --to-date 2026-04-01
```

### Job -- Treasury Buybacks

```bash
# Full buyback history download
python treasurydirect.py job buybacks

# Filtered by operation type
python treasurydirect.py job buybacks --type "Liquidity Support"
python treasurydirect.py job buybacks --type "Cash Management"

# Only completed operations
python treasurydirect.py job buybacks --results-only
```

### Job -- Full Auction History

```bash
# All types since 1997 (~9000+ records)
python treasurydirect.py job history

# Filter by type
python treasurydirect.py job history --type Bill
python treasurydirect.py job history --type Note
python treasurydirect.py job history --type Bond
python treasurydirect.py job history --type TIPS
python treasurydirect.py job history --type FRN
python treasurydirect.py job history --type CMB

# Include announcement and result PDFs
python treasurydirect.py job history --download-pdfs
python treasurydirect.py job history --type Note --download-pdfs
```

### Job -- Historical Debt

```bash
# Full debt history (2000-present)
python treasurydirect.py job debt
```

### Job -- Reports & Publications

```bash
# MSPD, SBN tables, savings bond rates, quarterly refunding, research data
python treasurydirect.py job reports
```

### Job -- Forms

```bash
# All PDF forms (marketable securities + general)
python treasurydirect.py job forms
```

### Job -- XML Auction Data

```bash
# Historical XML auction data directory
python treasurydirect.py job xml
```

### Job -- RSS Feeds

```bash
# All RSS/XML feeds (announced, auctioned, debt, MSPD, savings bonds)
python treasurydirect.py job rss
```

### Job -- Site Crawl

```bash
# Full site crawl (default 500 pages)
python treasurydirect.py job crawl

# Control crawl depth
python treasurydirect.py job crawl --max-pages 100
python treasurydirect.py job crawl --max-pages 1000
python treasurydirect.py job crawl --max-pages 2000
```

### Job -- Run All

```bash
# Execute all jobs: history, debt, reports, forms, xml, rss, crawl
python treasurydirect.py job all
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--output DIR` | Output directory (default: `apis/treasurydirect`) | All commands |
| `--quiet` | Minimal output | All commands |
| `--type TYPE` | Security type: Bill, Note, Bond, TIPS, FRN, CMB, all | api auctions, job history |
| `--days N` | Days of history (default: 365) | api auctions |
| `--start YYYY-MM-DD` | Start date for debt range | api debt |
| `--end YYYY-MM-DD` | End date for debt range | api debt |
| `--download-pdfs` | Download announcement + result PDFs | job history |
| `--max-pages N` | Max pages to crawl (default: 500) | job crawl |


## Python Recipes

### Securities API -- CUSIP Lookup

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Look up a single CUSIP
# Saves: securities_api/cusip_{CUSIP}.json, cusip_{CUSIP}.csv
# Fields: securityType, securityTerm, auctionDate, highYield, bidToCoverRatio, tailBps
scraper.scrape_securities_api(cusip="91282CQJ3")
```

### Securities API -- Recent Auctions

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# All types, last 365 days
# Saves: securities_api/{type}_auctions.json, {type}_auctions.csv, all_auctions.json,
#         all_auctions.csv, auction_summary.csv
scraper.scrape_securities_api()

# Filter by type and window
scraper.scrape_securities_api(security_type="Bill", days=30)
scraper.scrape_securities_api(security_type="Note", days=90)
scraper.scrape_securities_api(security_type="Bond", days=180)
scraper.scrape_securities_api(security_type="TIPS", days=365)
scraper.scrape_securities_api(security_type="FRN", days=365)

# All types for a specific window
scraper.scrape_securities_api(security_type="all", days=7)
```

### Securities API -- Full History

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Full history since 01/01/1997, all types
# Uses 2-year chunks for Bills, 5-year chunks for others
# Deduplicates by CUSIP + auctionDate
scraper.scrape_securities_api(security_type="all", full_history=True)

# Single type
scraper.scrape_securities_api(security_type="Note", full_history=True)

# With PDF downloads (announcement + competitive/noncompetitive results)
scraper.scrape_securities_api(security_type="all", full_history=True, download_pdfs=True)
```

### Debt API

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Current debt snapshot only
# Saves: debt_api/debt_current.json
scraper.scrape_debt_api(current_only=True)

# Historical debt (default: 2000-01-01 to today)
# Chunks into 12-month windows
# Saves: debt_api/debt_historical.json, debt_historical.csv
scraper.scrape_debt_api()

# Custom date range
scraper.scrape_debt_api(start_date="2024-01-01", end_date="2024-12-31")
scraper.scrape_debt_api(start_date="2020-01-01")
```

### Reports & Publications

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Downloads from all 6 report pages + MSPD + savings bond tables
# Saves: reports/{slugified_label}/ with PDFs, markdown conversions, tables as CSV
scraper.scrape_reports()
```

### Forms

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Downloads all PDF forms from marketable securities + general forms pages
# Follows sub-links containing "form" or "pdf" in path
# Saves: forms/{slugified_label}/
scraper.scrape_forms()
```

### XML Auction Data

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Crawls XML directory listing, falls back to known URL patterns (2008-present)
# Saves: xml_data/*.xml
scraper.scrape_xml_data()
```

### RSS Feeds

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Fetches all 5 known feeds + discovers additional feeds from RSS index page
# Saves each feed as .xml + parsed .json
# Saves: rss_feeds/{slugified_label}.xml, .json
scraper.scrape_rss_feeds()
```

### Site Crawl

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# BFS crawl from 29 seed URLs, downloads all files matching DOWNLOADABLE_EXTENSIONS
# Extracts HTML tables as CSV, builds sitemap.json
# Saves: crawl/downloads/{ext}/, crawl/pages/*_table_*.csv, crawl/sitemap.json
scraper.scrape_crawl(max_pages=500)
scraper.scrape_crawl(max_pages=1000)
```

### Run All

```python
from treasurydirect import TreasuryDirectScraper

scraper = TreasuryDirectScraper(output_dir="apis/treasurydirect", verbose=True)

# Executes in order: securities_api (all types, full history) -> debt_api ->
# reports -> forms -> xml_data -> rss_feeds -> crawl
scraper.run_all(full_history=True, download_pdfs=True)
scraper.run_all(days=365, full_history=False)
```


## Composite Recipes

### Recent Auction Snapshot (Last 7 Days, All Types)

```bash
python treasurydirect.py api auctions --days 7
```

PRISM receives: all auctions in the last 7 days across Bill/Note/Bond/TIPS/FRN/CMB with highYield, bidToCoverRatio, tailBps, direct/indirect/dealer allocation, SOMA accepted, offering amounts. Output in securities_api/all_auctions.json and auction_summary.csv.

### CUSIP Deep Dive

```bash
python treasurydirect.py api cusip 91282CQJ3
```

PRISM receives: full auction record for a single CUSIP -- yield, price, bid-to-cover, tail, competitive/noncompetitive breakdown, direct/indirect/dealer split, SOMA allocation, maturity, reopening status.

### Bill vs Coupon Supply Review

```bash
python treasurydirect.py api auctions --type Bill --days 90
python treasurydirect.py api auctions --type Note --days 90
python treasurydirect.py api auctions --type Bond --days 90
```

PRISM receives: 90-day auction histories for bills, notes, and bonds separately -- offering amounts, bid-to-cover trends, yield trajectories, allocation shifts across investor classes.

### Full History Build (One-Time Data Pull)

```bash
python treasurydirect.py job history --download-pdfs
python treasurydirect.py job debt
python treasurydirect.py job reports
python treasurydirect.py job rss
```

PRISM receives: complete auction database since 1997 with PDFs, full debt-to-the-penny series since 2000, all report downloads (MSPD, savings bond tables, refunding docs), RSS feed snapshots.

### Debt Level Monitoring

```bash
python treasurydirect.py api debt
python treasurydirect.py api debt --start $(date -v-1y +%Y-%m-%d)
```

PRISM receives: current total public debt outstanding + 1-year history of daily debt levels for trajectory analysis.

### Auction + Report Refresh

```bash
python treasurydirect.py api auctions --days 30
python treasurydirect.py job reports
python treasurydirect.py job rss
```

PRISM receives: last 30 days of auctions across all types, latest MSPD/savings bond/refunding publications, current RSS feed state for announcement monitoring.

### TIPS Auction History

```bash
python treasurydirect.py job history --type TIPS
python treasurydirect.py api auctions --type TIPS --days 365
```

PRISM receives: complete TIPS auction history since 1997 + recent 1-year detail. Real yield levels, bid-to-cover, dealer/indirect allocation for breakeven analysis inputs.

### FRN Auction + XML Data

```bash
python treasurydirect.py job history --type FRN
python treasurydirect.py job xml
```

PRISM receives: full FRN auction history + historical XML auction data files for cross-referencing spread and index rate data.


## Cross-Source Recipes

### Auction Absorption + Funding Conditions

```bash
python treasurydirect.py api auctions --days 30
python GS/data/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: recent auction results (bid-to-cover, tails, dealer takedown) + overnight funding rates (SOFR/EFFR/OBFR) and RRP usage. Connects primary market absorption to secondary market funding.

### Auction Demand + Dealer Positioning

```bash
python treasurydirect.py api auctions --type Note --days 90
python GS/data/apis/nyfed/nyfed.py pd-positions --count 12 --json
```

PRISM receives: 90-day note auction demand metrics (direct/indirect/dealer allocation) + primary dealer net Treasury positions. Shows if dealers are warehousing or distributing supply.

### Debt Level + TGA Cash Flows

```bash
python treasurydirect.py api debt
python treasurydirect.py api debt --start $(date -v-6m +%Y-%m-%d)
python GS/data/apis/treasury/treasury.py get dts --json
```

PRISM receives: current + 6-month debt-to-the-penny trajectory + Daily Treasury Statement cash flows. Gross issuance vs net borrowing, TGA balance dynamics.

### Auction Supply + SOFR Futures Positioning

```bash
python treasurydirect.py api auctions --type Bill --days 30
python GS/data/apis/cftc/cftc.py rates --json
```

PRISM receives: recent bill auction sizes and yields + net speculative SOFR futures positioning. Front-end supply pressure vs rate expectations.

### Auction Results + OIS Swap Flow

```bash
python treasurydirect.py api auctions --days 7
python GS/data/apis/dtcc/dtcc.py latest irs --json
```

PRISM receives: latest auction results across all types + OIS swap volumes. Shows if derivative market is hedging around new supply.

### Debt Growth + QT Runoff

```bash
python treasurydirect.py api debt --start $(date -v-1y +%Y-%m-%d)
python GS/data/apis/nyfed/nyfed.py qt-monitor --weeks 52 --json
python GS/data/apis/nyfed/nyfed.py soma-history --weeks 52 --json
```

PRISM receives: 1-year debt-to-the-penny trajectory + SOMA balance sheet runoff pace and composition. Net supply = gross issuance - Fed runoff.

### Bill Auctions + RRP Drainage

```bash
python treasurydirect.py api auctions --type Bill --days 60
python GS/data/apis/nyfed/nyfed.py rrp --count 30 --json
```

PRISM receives: bill auction sizes, yields, and bid-to-cover + ON RRP accepted amounts and counterparty counts. Bill supply substitution for RRP.

### TIPS Auctions + Breakeven Context

```bash
python treasurydirect.py api auctions --type TIPS --days 365
python GS/data/apis/nyfed/nyfed.py rate-history sofr --start $(date -v-1y +%Y-%m-%d) --json
```

PRISM receives: 1-year TIPS auction results (real yields, bid-to-cover) + SOFR history for nominal rate context.

### Auction Tails + Prediction Market Pricing

```bash
python treasurydirect.py api auctions --days 14
python GS/data/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: recent auction tails and demand metrics + market-implied Fed policy path. Weak auctions near policy transitions signal regime friction.

### Full Supply Picture

```bash
python treasurydirect.py api auctions --days 30
python treasurydirect.py api debt
python GS/data/apis/nyfed/nyfed.py soma-history --weeks 12 --json
python GS/data/apis/nyfed/nyfed.py pd-positions --count 12 --json
python GS/data/apis/nyfed/nyfed.py rrp --count 10 --json
```

PRISM receives: recent auction supply + total debt level + Fed balance sheet trajectory + dealer inventory + RRP drainage. Complete supply/demand/absorption picture.


## Setup

1. No API key required
2. `pip install requests beautifulsoup4 lxml openpyxl`
3. Optional (PDF conversion): `brew install poppler` (macOS) or `apt-get install poppler-utils` (Linux)
4. Test: `python treasurydirect.py api debt`
5. Full test: `python treasurydirect.py api auctions --type Bill --days 7`


## Architecture

```
treasurydirect.py
  Constants       BASE_URL, SECURITY_TYPES (6), SECURITIES_ENDPOINTS (3),
                  DEBT_ENDPOINTS (2), RSS_FEEDS (5), REPORT_PAGES (6),
                  FORMS_PAGES (2), CRAWL_SEED_URLS (29),
                  DOWNLOADABLE_EXTENSIONS, API_PAGE_SIZE (250),
                  RATE_LIMIT_SECONDS (0.5), FULL_HISTORY_START (01/01/1997)
  HTTP            _fetch() with retries + 403 recovery, _fetch_json(),
                  _download_file() with PDF-to-markdown conversion
  Helpers         _extract_links(), _scrape_page_for_downloads(),
                  _scrape_page_html_content(), _xml_to_dict(),
                  _json_records_to_csv(), _compute_tail(),
                  _build_auction_summary()
  Securities API  scrape_securities_api() -> _fetch_full_auction_history()
                  (date-range chunked, deduped by CUSIP+date),
                  _fetch_securities_by_cusip(), _download_auction_pdfs()
  Debt API        scrape_debt_api() -> chunked 12-month windows (2000-present)
  Reports         scrape_reports() -> _scrape_mspd(), _scrape_savings_bonds_tables()
  Forms           scrape_forms() -> follows sub-links for PDF forms
  XML Data        scrape_xml_data() -> _fetch_xml_by_pattern() fallback
  RSS Feeds       scrape_rss_feeds() -> discovers additional feeds from index
  Site Crawl      scrape_crawl() -> BFS from 29 seed URLs, table extraction
  Run All         run_all() -> securities + debt + reports + forms + xml + rss + crawl
  Interactive     13-item menu -> interactive wrappers with prompts
  Argparse        api {cusip,auctions,debt} + job {history,debt,reports,forms,xml,rss,crawl,all}
                  Global: --output, --quiet
```

API endpoints:
```
/TA_WS/securities/announced?format=json          -> upcoming auctions
/TA_WS/securities/auctioned?format=json          -> completed auctions
/TA_WS/securities/search?type=X&startDate=&endDate=&format=json  -> search by type/date
/TA_WS/securities/search?cusip=X&format=json     -> search by CUSIP
/TA_WS/securities/{cusip}?format=json            -> direct CUSIP lookup (fallback)
/NP_WS/debt/current?format=json                  -> current debt to the penny
/NP_WS/debt/search?startdate=&enddate=&format=json  -> historical debt by date range
/TA_WS/securities/announced/rss                  -> offering announcements RSS
/TA_WS/securities/auctioned/rss                  -> auction results RSS
/NP_WS/debt/feeds/recent                         -> debt RSS
/rss/mspd.xml                                    -> MSPD RSS
/rss/sbpro.xml                                   -> savings bonds RSS
/xml/                                            -> XML auction data directory
```

Output structure:
```
apis/treasurydirect/
  securities_api/
    bill_auctions.json, .csv
    note_auctions.json, .csv
    bond_auctions.json, .csv
    tips_auctions.json, .csv
    frn_auctions.json, .csv
    cmb_auctions.json, .csv
    all_auctions.json, .csv
    auction_summary.csv
    cusip_{CUSIP}.json, .csv
    pdfs/                         (with --download-pdfs)
  debt_api/
    debt_current.json
    debt_historical.json, .csv
  reports/
    {slugified_label}/            (PDFs, markdown conversions, table CSVs)
    mspd/
    savings_bonds_tables/
  forms/
    {slugified_label}/            (PDF forms)
  xml_data/
    *.xml
  rss_feeds/
    *.xml, *.json
  crawl/
    downloads/{ext}/              (pdf/, xlsx/, csv/, xml/, etc.)
    pages/*_table_*.csv
    sitemap.json
```
