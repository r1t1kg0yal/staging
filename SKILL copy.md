# OpenFIGI -- Financial Instrument Identifier Mapping

Script: `GS/data/apis/openfigi/openfigi.py`
Base URL: `https://api.openfigi.com/v3`
Auth: Optional API key via `OPENFIGI_API_KEY` env var (higher rate limits with key; works without)
Rate limits: Without key: 10 jobs/request, 25 requests/minute. With key: 100 jobs/request, 25 requests/6s.
Dependencies: `requests`


## Triggers

Use for: identifier resolution (CUSIP/ISIN/SEDOL/FIGI/ticker cross-mapping), Treasury CUSIP -> Bloomberg ticker, batch portfolio mapping, exchange listing discovery, issuer bond stacks, capital structure mapping, maturity wall analysis, sector-wide bond comparison, Treasury universe enumeration, preferred stock and loan facility discovery.

Not for: price data or time series (market data APIs), company fundamentals (EDGAR), real-time instrument creation, historical identifier changes, OTC instruments without FIGI assignments, instruments already in the format your downstream system needs.


## Data Catalog

### Identifier Types (Most Used)

| ID Type | Description | Example | When Needed |
|---------|-------------|---------|-------------|
| `TICKER` | Ticker symbol | IBM, AAPL | Equity lookups, EDGAR cross-reference |
| `ID_CUSIP` | CUSIP (9-char) | 459200101 | Treasury/bond data from TreasuryDirect |
| `ID_ISIN` | ISIN (12-char) | US4592001014 | International cross-reference, BIS data |
| `ID_SEDOL` | SEDOL (7-char) | 2005973 | UK/European instruments |
| `ID_BB_GLOBAL` | Bloomberg FIGI | BBG000BLNNH6 | When you already have a FIGI |
| `COMPOSITE_ID_BB_GLOBAL` | Composite FIGI | BBG000BLNNH6 | Country-level aggregate |
| `ID_BB_GLOBAL_SHARE_CLASS_LEVEL` | Share Class FIGI | BBG001S5S399 | Global aggregate across all exchanges |

### Additional Identifier Types

| ID Type | Description |
|---------|-------------|
| `BASE_TICKER` | Base ticker (for options, bonds, pools: e.g. "IBM 7 10/30/25") |
| `ID_CUSIP_8_CHR` | CUSIP issuer-level (first 8 chars) |
| `ID_BB_UNIQUE` | Legacy Bloomberg unique ID |
| `ID_TRACE` | FINRA TRACE identifier |
| `ID_COMMON` | Common Code (9-digit) |
| `ID_WERTPAPIER` | WKN (German securities ID) |
| `ID_CINS` | CINS (international CUSIP) |
| `ID_EXCH_SYMBOL` | Exchange-specific symbol |
| `ID_FULL_EXCHANGE_SYMBOL` | Full exchange symbol (futures/options) |
| `ID_BB_SEC_NUM_DES` | Bloomberg security number description |
| `OCC_SYMBOL` | OCC option symbol (21-char) |
| `UNIQUE_ID_FUT_OPT` | Bloomberg future/option unique ID |
| `OPRA_SYMBOL` | OPRA option symbol |
| `TRADING_SYSTEM_IDENTIFIER` | Trading system ID |
| `ID_SHORT_CODE` | Short code (Asian fixed income) |
| `VENDOR_INDEX_CODE` | Index provider code |

### Response Fields

| Field | Description |
|-------|-------------|
| `figi` | FIGI for this specific listing |
| `compositeFIGI` | Country-level aggregate FIGI |
| `shareClassFIGI` | Global aggregate FIGI (all listings worldwide) |
| `ticker` | Ticker symbol |
| `name` | Instrument name |
| `exchCode` | Exchange code |
| `marketSector` | Equity, Corp, Govt, Comdty, Curncy, Index, M-Mkt, Mtge, Muni, Pfd |
| `securityType` | Specific security type (Common Stock, US GOVERNMENT, etc.) |
| `securityType2` | Broader type (Common Stock, Option, Note, Pool, etc.) |
| `securityDescription` | Short description |

### FIGI Hierarchy

```
Share Class FIGI (BBG001S5S399) -- global aggregate, one per share class
    |
    +-- Composite FIGI (BBG000BLNNH6) -- country-level aggregate
    |       |
    |       +-- FIGI (BBG000BLNNH6) -- specific exchange listing (NYSE)
    |       +-- FIGI (BBG000NHN466) -- specific exchange listing (LSE)
    |
    +-- Composite FIGI (BBG000NHN304) -- another country
            |
            +-- FIGI (...) -- listing on that country's exchange
```

### Mapping Job Filters

| Filter | Type | Description |
|--------|------|-------------|
| `exchCode` | String | Exchange code (cannot combine with micCode) |
| `micCode` | String | ISO MIC code (cannot combine with exchCode) |
| `currency` | String | Currency (e.g. USD, EUR, GBP) |
| `marketSecDes` | String | Market sector (Equity, Govt, Corp, etc.) |
| `securityType` | String | Specific security type |
| `securityType2` | String | Broader security type |
| `includeUnlistedEquities` | Boolean | Include unlisted equities |
| `strike` | [min, max] | Option strike range |
| `coupon` | [min, max] | Bond coupon range |
| `expiration` | [date, date] | Option expiration range (YYYY-MM-DD) |
| `maturity` | [date, date] | Bond/pool maturity range (YYYY-MM-DD) |

### Curated Issuer Lists

| List | Tickers |
|------|---------|
| `banks` | JPM, BAC, C, GS, MS, WFC |
| `tech` | AAPL, MSFT, GOOG, AMZN, META, INTC |
| `energy` | XOM, CVX, COP, SLB, EOG |
| `pharma` | JNJ, PFE, MRK, ABBV, LLY |
| `telco` | T, VZ, TMUS |
| `auto` | F, GM, TSLA |

### Bond Ticker Parsing

| Raw Ticker | Coupon | Rate Type | Maturity | Suffix |
|------------|--------|-----------|----------|--------|
| `INTC 3.7 07/29/25` | 3.7% | fixed | 2025-07-29 | |
| `INTC F 05/11/27` | -- | floating | 2027-05-11 | |
| `INTC V3.22 03/01/25` | 3.22% | variable | 2025-03-01 | |
| `JPM 4.25 11/30/25 GMTN` | 4.25% | fixed | 2025-11-30 | GMTN |
| `INTC 0 02/01/04 144A` | 0% | zero | 2004-02-01 | 144A |

Suffixes: 144A (private placement), REGS (Regulation S), AI (accredited investor), GMTN (global MTN), * (defaulted).

### Enum Keys

Valid keys for `enums` command: `idType`, `exchCode`, `micCode`, `currency`, `marketSecDes`, `securityType`, `securityType2`, `stateCode`.


## CLI Recipes

All commands support `--json` for structured output. Most support `--export csv|json` for file export.

### Single Identifier Mapping

```bash
# Ticker -> FIGI
python openfigi.py map TICKER IBM
python openfigi.py map TICKER IBM --json
python openfigi.py map TICKER IBM --export csv

# CUSIP -> FIGI (Treasury bonds, corporate bonds)
python openfigi.py map ID_CUSIP 912810SZ9
python openfigi.py map ID_CUSIP 912810SZ9 --json

# ISIN -> FIGI (international instruments)
python openfigi.py map ID_ISIN US4592001014
python openfigi.py map ID_ISIN US4592001014 --json

# Map with filters
python openfigi.py map TICKER IBM --exch US
python openfigi.py map TICKER IBM --exch US --currency USD
python openfigi.py map TICKER IBM --sector Equity
python openfigi.py map ID_CUSIP 912810SZ9 --sector Govt
```

### Quick Lookups

```bash
# Equity lookup (ticker -> all exchange listings)
python openfigi.py equity AAPL
python openfigi.py equity AAPL --json
python openfigi.py equity AAPL --exch US --json
python openfigi.py equity AAPL --export csv

# Bond lookup (auto-detects CUSIP vs ISIN by length)
python openfigi.py bond 912810SZ9
python openfigi.py bond 912810SZ9 --json
python openfigi.py bond US4592001014 --json

# Cross-reference (all identifiers for an instrument)
python openfigi.py cross-ref TICKER AAPL
python openfigi.py cross-ref TICKER AAPL --json
python openfigi.py cross-ref ID_CUSIP 912810SZ9
python openfigi.py cross-ref ID_ISIN US0378331005 --json
python openfigi.py cross-ref ID_ISIN US0378331005 --export csv
```

### Batch Resolution

```bash
# Batch resolve Treasury CUSIPs
python openfigi.py treasury 912810SZ9 912810TA3 912810TB1
python openfigi.py treasury 912810SZ9 912810TA3 912810TB1 --json
python openfigi.py treasury 912810SZ9 912810TA3 --export csv

# Batch from file (one ID per line or CSV first column)
python openfigi.py batch tickers.txt --id-type TICKER
python openfigi.py batch tickers.txt --id-type TICKER --exch US --json
python openfigi.py batch bonds.txt --id-type ID_CUSIP --sector Govt --export csv
python openfigi.py batch portfolio.txt --id-type TICKER --exch US --export csv
```

### Search & Discovery

```bash
# Keyword search
python openfigi.py search "apple" --sector Equity
python openfigi.py search "apple" --sector Equity --json
python openfigi.py search "treasury 10 year" --sector Govt
python openfigi.py search "treasury 10 year" --sector Govt --exch US --json
python openfigi.py search "apple" --sector Equity --pages 5 --export csv

# Filtered search (alphabetical by FIGI, with total count)
python openfigi.py filter --query "apple" --sector Equity
python openfigi.py filter --sector Govt --exch US --json

# List valid enum values
python openfigi.py enums
python openfigi.py enums exchCode
python openfigi.py enums idType --json
python openfigi.py enums currency
python openfigi.py enums securityType

# List all 25+ supported identifier types
python openfigi.py id-types
python openfigi.py id-types --json
```

### Issuer Bond Analysis

```bash
# Full bond stack for an issuer
python openfigi.py issuer-bonds INTC
python openfigi.py issuer-bonds INTC --json
python openfigi.py issuer-bonds INTC --maturity 2025-2035
python openfigi.py issuer-bonds INTC --maturity 2025-2035 --json
python openfigi.py issuer-bonds AAPL --export csv
python openfigi.py issuer-bonds JPM --maturity 2025-2030 --sec-type GLOBAL --json

# Capital structure (equity + bonds + pfds + loans in one view)
python openfigi.py capital-structure INTC
python openfigi.py capital-structure INTC --json
python openfigi.py capital-structure JPM --json
python openfigi.py capital-structure JPM --export csv

# Maturity wall / profile by year
python openfigi.py maturity-profile INTC --start 2025 --end 2035
python openfigi.py maturity-profile INTC --start 2025 --end 2035 --json
python openfigi.py maturity-profile JPM --start 2025 --end 2030 --export csv

# Compare bond stacks across issuers
python openfigi.py compare-issuers AAPL MSFT GOOG AMZN META INTC
python openfigi.py compare-issuers AAPL MSFT GOOG AMZN META INTC --json
python openfigi.py compare-issuers JPM BAC C GS MS WFC --export csv

# Sector scan with curated issuer list
python openfigi.py sector-scan --list banks
python openfigi.py sector-scan --list tech --json
python openfigi.py sector-scan --list energy
python openfigi.py sector-scan --list pharma --json
python openfigi.py sector-scan --list telco
python openfigi.py sector-scan --list auto
python openfigi.py sector-scan --tickers NVDA AMD QCOM --json
```

### Treasury & Specialized

```bash
# Treasury universe by maturity range
python openfigi.py treasury-universe --maturity 2025-2035 --type notes
python openfigi.py treasury-universe --maturity 2025-2035 --type notes --json
python openfigi.py treasury-universe --maturity 2030-2031 --type all --export csv
python openfigi.py treasury-universe --maturity 2025-2035 --type bonds --json
python openfigi.py treasury-universe --type bills --json

# Preferred stock / hybrid capital
python openfigi.py preferred JPM
python openfigi.py preferred JPM --json
python openfigi.py preferred BAC --export csv

# Loan facilities (term, revolver, delay-draw)
python openfigi.py loans INTC
python openfigi.py loans INTC --json
python openfigi.py loans GE --export csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | Most commands |
| `--export json` | Export to JSON file | Most commands |
| `--exch CODE` | Exchange code filter | map, batch, equity |
| `--currency CUR` | Currency filter | map, batch |
| `--sector SEC` | Market sector filter (Equity, Govt, Corp) | map, batch, search, filter |
| `--sec-type TYPE` | Security type filter | map, search, filter, issuer-bonds |
| `--pages N` | Max pages to fetch | search, filter |
| `--maturity YYYY-YYYY` | Maturity range | issuer-bonds, treasury-universe |
| `--id-type TYPE` | Identifier type for batch | batch |
| `--start YYYY` | Start year | maturity-profile |
| `--end YYYY` | End year | maturity-profile |
| `--list NAME` | Curated issuer list | sector-scan |
| `--type TYPE` | notes/bonds/bills/all | treasury-universe |


## Python Recipes

### Single Identifier Resolution

```python
from openfigi import cmd_map, cmd_equity, cmd_bond, cmd_cross_ref

# Map any identifier type to FIGI(s)
# Returns: dict with "data" (list of instruments) or "warning"/"error"
result = cmd_map("TICKER", "IBM", as_json=True)
result = cmd_map("ID_CUSIP", "912810SZ9", as_json=True)
result = cmd_map("ID_ISIN", "US4592001014", as_json=True)
result = cmd_map("TICKER", "IBM", exch_code="US", sector="Equity", as_json=True)

# Quick equity lookup
# Returns: dict with "data" -> list of instruments across exchanges
eq = cmd_equity("AAPL", as_json=True)
eq = cmd_equity("AAPL", exch_code="US", as_json=True)

# Bond lookup (auto-detects CUSIP vs ISIN)
# Returns: dict with "data" -> instrument details
bond = cmd_bond("912810SZ9", as_json=True)
bond = cmd_bond("US4592001014", as_json=True)

# Cross-reference (all identifiers for an instrument)
# Returns: list of instruments with full identifier sets per exchange listing
xref = cmd_cross_ref("TICKER", "AAPL", as_json=True)
xref = cmd_cross_ref("ID_ISIN", "US0378331005", as_json=True)
```

### Batch Resolution

```python
from openfigi import cmd_batch, cmd_batch_file, cmd_treasury_cusips

# Batch resolve multiple identifiers
# Returns: list of {query: ..., result: ...} dicts
batch = cmd_batch(["AAPL", "MSFT", "GOOG"], id_type="TICKER", as_json=True)
batch = cmd_batch(["AAPL", "MSFT"], id_type="TICKER", exch_code="US", as_json=True)

# Batch from file
# Returns: list of resolved instrument dicts
result = cmd_batch_file("tickers.txt", id_type="TICKER", as_json=True)
result = cmd_batch_file("bonds.txt", id_type="ID_CUSIP", sector="Govt", as_json=True)

# Treasury CUSIP batch resolve
# Returns: list of {cusip: ..., result: ...} dicts
tsy = cmd_treasury_cusips(["912810SZ9", "912810TA3", "912810TB1"], as_json=True)
```

### Search & Discovery

```python
from openfigi import cmd_search, cmd_filter, cmd_enums, cmd_id_types

# Keyword search
# Returns: list of instrument dicts
results = cmd_search("apple", sector="Equity", as_json=True)
results = cmd_search("treasury 10 year", sector="Govt", exch_code="US", as_json=True)

# Filtered search (with total count)
# Returns: (list of instruments, total_count)
data, total = cmd_filter(query="apple", sector="Equity", as_json=True)

# Valid enum values
# Returns: list of valid values for the key
exchanges = cmd_enums("exchCode", as_json=True)
currencies = cmd_enums("currency", as_json=True)
sec_types = cmd_enums("securityType", as_json=True)

# All identifier types
# Returns: dict of {id_type: description}
types = cmd_id_types(as_json=True)
```

### Issuer Bond Analysis

```python
from openfigi import (cmd_issuer_bonds, cmd_capital_structure,
                      cmd_maturity_profile, cmd_compare_issuers,
                      cmd_sector_scan, cmd_preferred, cmd_loans)

# Full bond stack (parsed coupon/maturity/rate_type/suffix per bond)
# Returns: list of bond dicts with parsed_coupon, parsed_maturity, etc.
bonds = cmd_issuer_bonds("INTC", as_json=True)
bonds = cmd_issuer_bonds("INTC", maturity_start="2025-01-01",
                         maturity_end="2035-12-31", as_json=True)
bonds = cmd_issuer_bonds("JPM", maturity_start="2025-01-01",
                         maturity_end="2030-12-31", as_json=True)

# Capital structure (equity + bonds + pfds + loans)
# Returns: {ticker, equity_count, bond_count, preferred_count, loan_count,
#           equity: [...], bonds_sample: [...], preferred_sample: [...], loans_sample: [...]}
cap = cmd_capital_structure("INTC", as_json=True)
cap = cmd_capital_structure("JPM", as_json=True)

# Maturity profile (bond wall bucketed by year)
# Returns: {year: {count, avg_coupon, min_coupon, max_coupon, bonds: [...]}}
wall = cmd_maturity_profile("INTC", start_year=2025, end_year=2035, as_json=True)

# Compare issuers (side-by-side bond stack comparison)
# Returns: list of {ticker, name, count, avg_coupon, min_coupon, max_coupon, earliest, latest, types}
comp = cmd_compare_issuers(["AAPL", "MSFT", "GOOG", "AMZN"], as_json=True)

# Sector scan (curated list or custom tickers)
# Returns: same as compare_issuers
scan = cmd_sector_scan(list_name="banks", as_json=True)
scan = cmd_sector_scan(list_name="tech", as_json=True)
scan = cmd_sector_scan(tickers=["NVDA", "AMD", "QCOM"], as_json=True)

# Preferred stock
# Returns: list of preferred instrument dicts
pfds = cmd_preferred("JPM", as_json=True)

# Loan facilities
# Returns: list of loan instrument dicts (term, revolver, delay-draw)
loans = cmd_loans("INTC", as_json=True)
```

### Treasury Universe

```python
from openfigi import cmd_treasury_universe

# Enumerate outstanding Treasury securities by maturity range
# Returns: list of {ticker, figi, name, type, coupon, maturity}
tsy = cmd_treasury_universe(maturity_start="2025-01-01",
                            maturity_end="2035-12-31",
                            instrument_type="notes", as_json=True)
tsy = cmd_treasury_universe(maturity_start="2030-01-01",
                            maturity_end="2031-12-31",
                            instrument_type="all", as_json=True)
```

### Core API Functions

```python
from openfigi import api_map, api_map_single, api_search, api_filter, api_enum_values

# Batch mapping (raw API, respects rate limits and job chunking)
jobs = [{"idType": "TICKER", "idValue": "IBM"},
        {"idType": "TICKER", "idValue": "AAPL", "exchCode": "US"}]
results = api_map(jobs)

# Single mapping
result = api_map_single("TICKER", "IBM", exchCode="US", marketSecDes="Equity")

# Keyword search (paginated)
instruments = api_search("apple", max_pages=3, marketSecDes="Equity")

# Filtered search (paginated, alphabetical)
instruments, total = api_filter(query="apple", max_pages=3, marketSecDes="Equity")

# Enum values
exchanges = api_enum_values("exchCode")
```


## Composite Recipes

### Treasury Auction Cross-Reference

```bash
python openfigi.py treasury 912810SZ9 912810TA3 912810TB1 --json
```

PRISM receives: Bloomberg ticker (e.g. "T 4.5 11/15/33"), FIGI, composite FIGI, security type, and name for each CUSIP. Links TreasuryDirect auction data to Bloomberg identifiers.

### EDGAR Filing -> Instrument Identifier

```bash
python openfigi.py equity AAPL --json
python openfigi.py cross-ref TICKER AAPL --json
```

PRISM receives: composite FIGI, share class FIGI, all exchange listings globally. Links EDGAR filings to Bloomberg identifier system.

### Issuer Credit Profile

```bash
python openfigi.py capital-structure INTC --json
python openfigi.py maturity-profile INTC --start 2025 --end 2035 --json
```

PRISM receives: equity listing count, total bonds outstanding, preferred count, loan facility count, maturity wall with per-year bond count and average coupon.

### Sector Bond Comparison

```bash
python openfigi.py sector-scan --list banks --json
python openfigi.py sector-scan --list tech --json
```

PRISM receives: per-issuer bond count, average coupon, coupon range, maturity range. Side-by-side comparison of 6 banks or 6 tech issuers.

### Treasury Curve Reference Points

```bash
python openfigi.py treasury-universe --maturity 2025-2035 --type notes --json
python openfigi.py treasury-universe --maturity 2025-2035 --type bonds --json
```

PRISM receives: every outstanding Treasury note and bond with coupon, maturity date, and FIGI. For building yield curve reference points and linking to TreasuryDirect auction data.

### Full Identifier Resolution Pipeline

```bash
python openfigi.py map TICKER IBM --json
python openfigi.py cross-ref TICKER IBM --json
python openfigi.py issuer-bonds IBM --maturity 2025-2035 --json
```

PRISM receives: primary FIGI set for equity, all global exchange listings, full corporate bond stack with parsed coupon/maturity.


## Cross-Source Recipes

### CUSIP Resolution + Treasury Auction Data

```bash
python openfigi.py treasury 912810SZ9 912810TA3 --json
python GS/data/apis/treasurydirect/treasurydirect.py api auctions --days 30
```

PRISM receives: Bloomberg tickers for auction CUSIPs + recent auction results. Links identifiers to supply data.

### Equity Resolution + SEC Filings

```bash
python openfigi.py equity AAPL --json
python GS/data/apis/sec_edgar/sec_edgar.py company-facts --ticker AAPL --json
```

PRISM receives: full FIGI set (FIGI, composite, share class) + company fundamentals. Cross-system instrument linkage.

### Bond Stack + Credit Spreads

```bash
python openfigi.py issuer-bonds INTC --maturity 2025-2035 --json
python GS/data/apis/nyfed/nyfed.py rates --json
```

PRISM receives: issuer bond universe with coupon/maturity + current risk-free reference rates. Basis for credit spread estimation.

### Capital Structure + Bank Health

```bash
python openfigi.py capital-structure JPM --json
python GS/data/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: full capital stack (equity + bonds + pfds + loans) + bank-level stress indicators. Capital adequacy context.

### Treasury Universe + Funding Conditions

```bash
python openfigi.py treasury-universe --maturity 2025-2030 --type notes --json
python GS/data/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: outstanding Treasury supply by maturity + overnight rate complex. Supply vs funding conditions.

### Sector Scan + Positioning

```bash
python openfigi.py sector-scan --list banks --json
python GS/data/apis/nyfed/nyfed.py pd-positions --count 24 --json
```

PRISM receives: bank bond stack sizes + primary dealer net positions. Credit supply vs dealer inventory.


## Setup

1. `pip install requests`
2. Optional: `export OPENFIGI_API_KEY=your_key` (higher rate limits)
3. Test: `python openfigi.py equity AAPL`
4. Full test: `python openfigi.py capital-structure INTC`


## Architecture

```
openfigi.py
  Constants       BASE_URL, ID_TYPES (25+), ENUM_KEYS, MARKET_SECTORS, ISSUER_LISTS (6)
  Ticker Parser   _parse_bond_ticker(), _parse_maturity_year(), _fmt_coupon()
  HTTP            _post(), _get() with rate limiting, retries, 429 handling
  Core API        api_map(), api_map_single(), api_search(), api_filter(), api_enum_values()
  Display         _display_instruments(), _display_bond_table(), _display_mapping_result()
  Analytical      _fetch_issuer_bonds() with mega-issuer maturity chunking + FIGI dedup
  Commands (19)   map, batch, batch-file, search, filter, equity, bond, treasury,
                  cross-ref, enums, id-types, issuer-bonds, capital-structure,
                  maturity-profile, compare-issuers, treasury-universe, sector-scan,
                  preferred, loans
  Interactive     19-item menu -> interactive wrappers with prompts
  Argparse        19 subcommands, all with --json and --export
```

API endpoints:
```
POST /v3/mapping          -> batch identifier resolution (primary endpoint)
POST /v3/search           -> keyword search (paginated via next cursor)
POST /v3/filter           -> filtered search (alphabetical by FIGI, with total)
GET  /v3/mapping/values/  -> enum value reference (idType, exchCode, etc.)
```

Rate limit management:
```
cmd_*() -> api_*() -> _post()/_get() -> _rate_wait() -> SESSION.post/get()
                                         |
                                         +-- Tracks _last_request_time
                                         +-- Enforces min interval between requests
                                         +-- Handles 429 with ratelimit-reset header
                                         +-- Chunks batches into MAX_JOBS per request

Mega-issuer handling (banks with >15k bonds):
  cmd_issuer_bonds("JPM", maturity="2025-2035")
    -> _fetch_issuer_bonds() detects overflow
    -> Chunks by 1-year maturity windows
    -> Deduplicates by FIGI
    -> Sorts by maturity
    -> Attaches _parsed fields (coupon, rate_type, maturity, suffix)
```
