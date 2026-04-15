# U.S. Treasury Fiscal Data

Script: `GS/data/apis/treasury/treasury.py`
Base URL: `https://api.fiscaldata.treasury.gov/services/api/fiscal_service`
Docs: `https://fiscaldata.treasury.gov/api-documentation/`
Auth: None required
Rate limit: None documented (be polite, ~0.2s between bursts)
Dependencies: stdlib only (`urllib`, `json`, `argparse`)


## Triggers

Use for: Treasury CUSIPs and auction schedules, debt to the penny, historical debt outstanding, MSPD (marketable securities outstanding detail), MTS (Monthly Treasury Statement) receipts/outlays/deficit, DTS (Daily Treasury Statement) operating cash balance and deposits/withdrawals, average interest rates on Treasury securities, Treasury reporting exchange rates, revenue collections, interest expense on public debt, federal debt schedules, TROR (Treasury Report on Receivables), Treasury Offset Program data, savings bonds, SLGS, gold reserve, financial statements (balance sheets, net cost, net position), long-term fiscal projections, social insurance, FRN daily indexes.

Not for: overnight reference rates / SOFR / EFFR (NY Fed), SOMA holdings / QT (NY Fed), auction results with bid-to-cover / tails (TreasuryDirect), yield curve / par yields (TreasuryDirect or FRED), OTC swap volumes (DTCC), futures positioning (CFTC), bank-level financials (FDIC), commercial paper / CD rates (FRED), prediction markets (prediction_markets), primary dealer positioning (NY Fed).


## Data Catalog

### Categories

| Category | Description |
|----------|-------------|
| `auctions` | Auction schedules, CUSIPs, record-setting auction data |
| `debt` | Debt to penny, outstanding, schedules, MSPD, TROR, TOP |
| `accounting` | MTS, DTS, financial reports, reconciliations |
| `interest_rates` | Average rates, exchange rates, yields |
| `securities` | Savings bonds, TreasuryDirect, SLGS, redemption tables |
| `revenue` | Revenue collections, tax receipts |
| `payments` | Judgment Fund, advances |
| `other` | Gold reserve, gift contributions, misc |

### Endpoint Registry -- Auctions (3 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `upcoming_auctions` | `v1/accounting/od/upcoming_auctions` | Treasury Securities Upcoming Auctions |
| `record_setting_auction` | `v2/accounting/od/record_setting_auction` | Record-Setting Auction |
| `frn_daily_indexes` | `v1/accounting/od/frn_daily_indexes` | FRN Daily Indexes |

### Endpoint Registry -- Debt (22 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `debt_to_penny` | `v2/accounting/od/debt_to_penny` | Debt to the Penny |
| `debt_outstanding` | `v2/accounting/od/debt_outstanding` | Historical Debt Outstanding |
| `schedules_fed_debt` | `v1/accounting/od/schedules_fed_debt` | Schedules of Federal Debt by Month |
| `schedules_fed_debt_fytd` | `v1/accounting/od/schedules_fed_debt_fytd` | Schedules of Federal Debt Fiscal Year-to-Date |
| `schedules_fed_debt_daily_activity` | `v1/accounting/od/schedules_fed_debt_daily_activity` | Schedules of Federal Debt Daily Activity |
| `schedules_fed_debt_daily_summary` | `v1/accounting/od/schedules_fed_debt_daily_summary` | Schedules of Federal Debt Daily Summary |
| `mspd_table_1` | `v1/debt/mspd/mspd_table_1` | Summary of Treasury Securities Outstanding |
| `mspd_table_2` | `v1/debt/mspd/mspd_table_2` | Statutory Debt Limit |
| `mspd_table_3_market` | `v1/debt/mspd/mspd_table_3_market` | Detail of Marketable Treasury Securities Outstanding |
| `mspd_table_3_nonmarket` | `v1/debt/mspd/mspd_table_3_nonmarket` | Detail of Non-Marketable Treasury Securities Outstanding |
| `mspd_table_4` | `v1/debt/mspd/mspd_table_4` | MSPD Historical Data |
| `mspd_table_5` | `v1/debt/mspd/mspd_table_5` | Holdings of Treasury Securities in Stripped Form |
| `tror` | `v2/debt/tror` | Treasury Report on Receivables Full Data |
| `tror_collected_outstanding` | `v2/debt/tror/collected_outstanding_recv` | Collected and Outstanding Receivables |
| `tror_delinquent_debt` | `v2/debt/tror/delinquent_debt` | Delinquent Debt |
| `tror_collections_delinquent` | `v2/debt/tror/collections_delinquent_debt` | Collections on Delinquent Debt |
| `tror_written_off` | `v2/debt/tror/written_off_delinquent_debt` | Written Off Delinquent Debt |
| `tror_data_act_compliance` | `v2/debt/tror/data_act_compliance` | 120 Day Delinquent Debt Referral Compliance |
| `top_federal` | `v1/debt/top/top_federal` | Treasury Offset Program - Federal Collections |
| `top_state` | `v1/debt/top/top_state` | Treasury Offset Program - State Programs |
| `title_xii` | `v2/accounting/od/title_xii` | Advances to State Unemployment Funds (SSA Title XII) |
| `interest_uninvested` | `v2/accounting/od/interest_uninvested` | Federal Borrowings Program: Interest on Uninvested Funds |
| `interest_cost_fund` | `v2/accounting/od/interest_cost_fund` | Federal Investments Program: Interest Cost by Fund |

### Endpoint Registry -- Accounting / MTS (15 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `mts_table_1` | `v1/accounting/mts/mts_table_1` | Summary of Receipts, Outlays, Deficit/Surplus |
| `mts_table_2` | `v1/accounting/mts/mts_table_2` | Summary of Budget and Off-Budget Results |
| `mts_table_3` | `v1/accounting/mts/mts_table_3` | Summary of Receipts and Outlays |
| `mts_table_4` | `v1/accounting/mts/mts_table_4` | Receipts of the U.S. Government |
| `mts_table_5` | `v1/accounting/mts/mts_table_5` | Outlays of the U.S. Government |
| `mts_table_6` | `v1/accounting/mts/mts_table_6` | Means of Financing the Deficit |
| `mts_table_6a` | `v1/accounting/mts/mts_table_6a` | Analysis of Change in Excess of Liabilities |
| `mts_table_6b` | `v1/accounting/mts/mts_table_6b` | Securities Issued by Federal Agencies |
| `mts_table_6c` | `v1/accounting/mts/mts_table_6c` | Federal Agency Borrowing via Treasury Securities |
| `mts_table_6d` | `v1/accounting/mts/mts_table_6d` | Investments of Federal Government Accounts |
| `mts_table_6e` | `v1/accounting/mts/mts_table_6e` | Guaranteed and Direct Loan Financing |
| `mts_table_7` | `v1/accounting/mts/mts_table_7` | Receipts and Outlays by Month |
| `mts_table_8` | `v1/accounting/mts/mts_table_8` | Trust Fund Impact on Budget Results |
| `mts_table_9` | `v1/accounting/mts/mts_table_9` | Receipts by Source, Outlays by Function |

### Endpoint Registry -- Accounting / DTS (7 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `dts_table_1` | `v1/accounting/dts/dts_table_1` | Operating Cash Balance |
| `dts_table_2` | `v1/accounting/dts/dts_table_2` | Deposits and Withdrawals of Operating Cash |
| `dts_table_3a` | `v1/accounting/dts/dts_table_3a` | Public Debt Transactions |
| `dts_table_3b` | `v1/accounting/dts/dts_table_3b` | Adjustment of Public Debt to Cash Basis |
| `dts_table_3c` | `v1/accounting/dts/dts_table_3c` | Debt Subject to Limit |
| `dts_table_4` | `v1/accounting/dts/dts_table_4` | Federal Tax Deposits (Inter-agency Tax Transfers) |
| `dts_table_5` | `v1/accounting/dts/dts_table_5` | Short-Term Cash Investments |
| `dts_table_6` | `v1/accounting/dts/dts_table_6` | Income Tax Refunds Issued |

### Endpoint Registry -- Accounting / Financial Reports (8 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `statement_net_cost` | `v2/accounting/od/statement_net_cost` | Statements of Net Cost |
| `net_position` | `v1/accounting/od/net_position` | Statements of Operations and Changes in Net Position |
| `reconciliations` | `v1/accounting/od/reconciliations` | Reconciliations of Net Operating Cost |
| `cash_balance` | `v1/accounting/od/cash_balance` | Statements of Changes in Cash Balance |
| `balance_sheets` | `v2/accounting/od/balance_sheets` | Balance Sheets |
| `long_term_projections` | `v1/accounting/od/long_term_projections` | Statements of Long-Term Fiscal Projections |
| `social_insurance` | `v1/accounting/od/social_insurance` | Statements of Social Insurance |
| `insurance_amounts` | `v1/accounting/od/insurance_amounts` | Statements of Changes in Social Insurance Amounts |

### Endpoint Registry -- Interest Rates (5 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `avg_interest_rates` | `v2/accounting/od/avg_interest_rates` | Average Interest Rates on U.S. Treasury Securities |
| `rates_of_exchange` | `v1/accounting/od/rates_of_exchange` | Treasury Reporting Rates of Exchange |
| `interest_expense` | `v2/accounting/od/interest_expense` | Interest Expense on the Public Debt Outstanding |
| `qualified_tax` | `v2/accounting/od/qualified_tax` | Historical Qualified Tax Credit Bond Interest Rates |
| `utf_qtr_yields` | `v2/accounting/od/utf_qtr_yields` | Unemployment Trust Fund Quarterly Yields |

### Endpoint Registry -- Securities (14 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `redemption_tables` | `v2/accounting/od/redemption_tables` | Accrual Savings Bonds Redemption Tables |
| `slgs_statistics` | `v2/accounting/od/slgs_statistics` | Monthly SLGS Securities Program |
| `slgs_savings_bonds` | `v1/accounting/od/slgs_savings_bonds` | Savings Bonds Securities Sold |
| `sb_value` | `v2/accounting/od/sb_value` | Savings Bonds Value Files |
| `slgs_securities` | `v1/accounting/od/slgs_securities` | State and Local Government Series Securities |
| `securities_sales` | `v1/accounting/od/securities_sales` | Securities Issued in TreasuryDirect - Sales |
| `securities_sales_term` | `v1/accounting/od/securities_sales_term` | Securities Sales by Term |
| `securities_transfers` | `v1/accounting/od/securities_transfers` | Transfers of Marketable Securities |
| `securities_conversions` | `v1/accounting/od/securities_conversions` | Conversions of Paper Savings Bonds |
| `securities_redemptions` | `v1/accounting/od/securities_redemptions` | Securities Redemptions |
| `securities_outstanding` | `v1/accounting/od/securities_outstanding` | Securities Outstanding |
| `securities_c_of_i` | `v1/accounting/od/securities_c_of_i` | Certificates of Indebtedness |
| `securities_accounts` | `v1/accounting/od/securities_accounts` | Securities Accounts |
| `savings_bonds_report` | `v1/accounting/od/savings_bonds_report` | Paper Savings Bonds Issues, Redemptions, Maturities by Series |
| `savings_bonds_mud` | `v1/accounting/od/savings_bonds_mud` | Matured Unredeemed Debt |
| `savings_bonds_pcs` | `v1/accounting/od/savings_bonds_pcs` | Piece Information by Series |

### Endpoint Registry -- Revenue (1 endpoint)

| Key | API Path | Table Name |
|-----|----------|------------|
| `revenue_collections` | `v2/revenue/rcm` | U.S. Government Revenue Collections |

### Endpoint Registry -- Payments (1 endpoint)

| Key | API Path | Table Name |
|-----|----------|------------|
| `jfics_congress_report` | `v2/payments/jfics/jfics_congress_report` | Judgment Fund: Annual Report to Congress |

### Endpoint Registry -- Other (2 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `gold_reserve` | `v2/accounting/od/gold_reserve` | U.S. Treasury-Owned Gold |
| `gift_contributions` | `v2/accounting/od/gift_contributions` | Gift Contributions to Reduce the Public Debt |

### Filter Syntax

Format: `field:operator:value`. Multiple filters are comma-separated.

| Operator | Meaning | Example |
|----------|---------|---------|
| `eq` | Equals | `security_type:eq:Bill` |
| `in` | In set | `country_currency_desc:in:(Canada-Dollar,Mexico-Peso)` |
| `gte` | Greater than or equal | `record_date:gte:2024-01-01` |
| `gt` | Greater than | `record_date:gt:2024-01-01` |
| `lte` | Less than or equal | `record_date:lte:2025-12-31` |
| `lt` | Less than | `record_date:lt:2025-01-01` |

Combined example: `security_type:eq:Bill,record_date:gte:2024-01-01,record_date:lte:2025-12-31`

### Sort Syntax

Prefix field name with `-` for descending. Default sort is `-record_date` (newest first).

| Sort | Meaning |
|------|---------|
| `-record_date` | Newest first |
| `record_date` | Oldest first |
| `-tot_pub_debt_out_amt` | Largest debt first |

### Sample Query Patterns

| Description | Key | Filter | Fields |
|-------------|-----|--------|--------|
| Debt to penny, recent 10 | `debt_to_penny` | | `record_date, tot_pub_debt_out_amt` |
| MTS table 9, line 120 (receipts total) | `mts_table_9` | `line_code_nbr:eq:120` | `record_date, classification_desc, current_month_rcpt_outly_amt` |
| Exchange rates Canada/Mexico 2024 | `rates_of_exchange` | `country_currency_desc:in:(Canada-Dollar,Mexico-Peso),record_date:gte:2024-01-01` | `country_currency_desc, exchange_rate, record_date` |
| Revenue by tax category | `revenue_collections` | `tax_category_id:eq:3` | `record_date, net_collections_amt, tax_category_desc` |
| Average rates, Bills only | `avg_interest_rates` | `security_type:eq:Bill` | `record_date, security_term, avg_interest_rate_amt` |
| CUSIPs for TIPS auctions | `upcoming_auctions` | `security_type:eq:TIPS` | `cusip, auction_date, offering_amt` |
| DTS operating cash balance | `dts_table_1` | | `record_date, account_type, close_today_bal, open_today_bal` |
| Gold reserve | `gold_reserve` | | `record_date, fine_troy_oz, book_value_amt` |


## CLI Recipes

All commands support `--json` for structured output. Run without args for interactive menu.

### CUSIPs

```bash
# Full CUSIP universe (upcoming_auctions + frn_daily_indexes)
python treasury.py cusips --full-universe
python treasury.py cusips --full-universe --json
python treasury.py cusips --full-universe --progress

# Unique CUSIPs only
python treasury.py cusips --unique
python treasury.py cusips --unique --json

# Filter by security type
python treasury.py cusips --security-type Bill
python treasury.py cusips --security-type TIPS --json
python treasury.py cusips -s Note --unique

# Date range filter
python treasury.py cusips --from-date 2024-01-01 --to-date 2025-12-31
python treasury.py cusips -s Bond --from-date 2024-06-01 --json

# Raw API filter
python treasury.py cusips --filter "security_type:eq:FRN"
python treasury.py cusips -f "offering_amt:gte:50000" --json

# Custom fields
python treasury.py cusips --fields "cusip,security_type,auction_date,offering_amt"

# Limit rows
python treasury.py cusips --limit 50
python treasury.py cusips --full-universe --limit 200
```

### Auctions

```bash
# Upcoming auctions
python treasury.py auctions
python treasury.py auctions --json

# Filter by security type
python treasury.py auctions --security-type Bill
python treasury.py auctions -s Bond --json
python treasury.py auctions -s TIPS

# Date range
python treasury.py auctions --from-date 2025-01-01 --to-date 2025-12-31
python treasury.py auctions -s Note --from-date 2025-06-01 --json

# Record-setting auctions
python treasury.py auctions --record-setting
python treasury.py auctions --record-setting -s Bond --json

# Raw filter
python treasury.py auctions --filter "offering_amt:gte:100000" --json
```

### Treasury Buybacks

```bash
# All buyback operations (191 total, 2000-present)
python treasury.py buybacks
python treasury.py buybacks --json

# Liquidity Support only (off-the-run repurchases for market liquidity)
python treasury.py buybacks --operation-type "Liquidity Support"

# Cash Management only (managing Treasury cash balance / bill issuance)
python treasury.py buybacks --operation-type "Cash Management"

# TIPS buybacks
python treasury.py buybacks --security-type TIPS

# Only operations with completed results
python treasury.py buybacks --results-only

# Date range
python treasury.py buybacks --from-date 2024-01-01 --to-date 2025-12-31 --json

# Raw filter
python treasury.py buybacks --filter "maturity_bucket:eq:10Y to 20Y" --json
```

### Auction Data (Full Pricing)

```bash
# Full auction data with pricing, rates, bid-to-cover
python treasury.py auctions-data
python treasury.py auctions-data --json

# Filter by security type
python treasury.py auctions-data --security-type Bill
python treasury.py auctions-data --security-type Bond --json

# By CUSIP
python treasury.py auctions-data --cusip 91282CQJ3

# Date range
python treasury.py auctions-data --from-date 2025-01-01 --to-date 2026-04-01
```

### Debt

```bash
# Debt to the Penny (recent)
python treasury.py debt
python treasury.py debt --json

# Date range
python treasury.py debt --from-date 2024-01-01 --to-date 2025-12-31
python treasury.py debt --from-date 2020-01-01 --json

# Specific fields
python treasury.py debt --fields "record_date,tot_pub_debt_out_amt,intragov_hold_amt"
python treasury.py debt --fields "record_date,tot_pub_debt_out_amt" --json

# Raw filter
python treasury.py debt --filter "tot_pub_debt_out_amt:gte:30000000000000" --json

# Limit
python treasury.py debt --limit 30
```

### Interest Rates

```bash
# Average interest rates (recent)
python treasury.py interest-rates
python treasury.py interest-rates --json

# Filter by security type
python treasury.py interest-rates --security-type Bill
python treasury.py interest-rates -s Note --json
python treasury.py interest-rates -s Bond

# Date range
python treasury.py interest-rates --from-date 2024-01-01 --to-date 2025-12-31
python treasury.py interest-rates -s Bill --from-date 2024-06-01 --json

# Raw filter
python treasury.py interest-rates --filter "avg_interest_rate_amt:gte:4.0" --json

# Custom fields
python treasury.py interest-rates --fields "record_date,security_type,security_term,avg_interest_rate_amt"
```

### Exchange Rates

```bash
# All exchange rates (recent)
python treasury.py exchange
python treasury.py exchange --json

# Filter by currencies
python treasury.py exchange --currencies "Canada-Dollar,Mexico-Peso"
python treasury.py exchange -c "Japan-Yen" --json
python treasury.py exchange -c "Euro Zone-Euro,United Kingdom-Pound" --json

# Date range
python treasury.py exchange --from-date 2024-01-01 --to-date 2025-12-31
python treasury.py exchange -c "China-Yuan" --from-date 2024-01-01 --json

# Raw filter
python treasury.py exchange --filter "exchange_rate:gte:100" --json

# Custom fields
python treasury.py exchange --fields "country_currency_desc,exchange_rate,record_date"
```

### Revenue

```bash
# Revenue collections (recent)
python treasury.py revenue
python treasury.py revenue --json

# Date range
python treasury.py revenue --from-date 2024-01-01 --to-date 2025-12-31
python treasury.py revenue --from-date 2023-01-01 --json

# Filter by tax category
python treasury.py revenue --filter "tax_category_id:eq:3"
python treasury.py revenue -f "tax_category_id:eq:3" --json

# Custom fields
python treasury.py revenue --fields "record_date,net_collections_amt,tax_category_desc"
```

### Generic Get (Universal Endpoint Access)

```bash
# Query any endpoint by registry key
python treasury.py get debt_to_penny
python treasury.py get debt_to_penny --json
python treasury.py get mts_table_1 --json
python treasury.py get dts_table_1 --json

# Date range
python treasury.py get debt_to_penny --from-date 2024-01-01 --to-date 2025-12-31
python treasury.py get mts_table_9 --from-date 2024-01-01 --json

# Filter
python treasury.py get mts_table_9 --filter "line_code_nbr:eq:120" --json
python treasury.py get avg_interest_rates --filter "security_type:eq:Bill" --json
python treasury.py get rates_of_exchange --filter "country_currency_desc:in:(Canada-Dollar,Mexico-Peso)" --json

# Sort
python treasury.py get debt_to_penny --sort "-record_date" --json
python treasury.py get debt_outstanding --sort "record_date" --json

# Select fields
python treasury.py get debt_to_penny --fields "record_date,tot_pub_debt_out_amt"
python treasury.py get mts_table_9 --fields "record_date,classification_desc,current_month_rcpt_outly_amt" --json

# Pagination
python treasury.py get mspd_table_3_market --page-number 1 --page-size 50 --json
python treasury.py get mspd_table_3_market -p 2 --page-size 50 --json

# Fetch all pages
python treasury.py get debt_to_penny --from-date 2020-01-01 --all --progress --json

# Disable automatic date filters
python treasury.py get record_setting_auction --no-date-filters --json
python treasury.py get redemption_tables --no-date-filters --limit 50

# Limit rows
python treasury.py get gold_reserve --limit 10
python treasury.py get dts_table_2 --limit 50 --json

# Complex: DTS operating cash balance for Q1 2025
python treasury.py get dts_table_1 --from-date 2025-01-01 --to-date 2025-03-31 --fields "record_date,account_type,close_today_bal,open_today_bal" --json

# Complex: MSPD marketable securities, specific date
python treasury.py get mspd_table_3_market --filter "record_date:eq:2025-01-31" --json

# Complex: debt schedules daily activity
python treasury.py get schedules_fed_debt_daily_activity --from-date 2025-03-01 --json
```

### Field Discovery

```bash
# List field names for an endpoint
python treasury.py fields debt_to_penny
python treasury.py fields mts_table_1
python treasury.py fields dts_table_1

# Full schema (labels + dataTypes)
python treasury.py fields debt_to_penny --schema
python treasury.py fields avg_interest_rates --schema --json
python treasury.py fields mts_table_9 --schema --json

# With filter (samples a filtered row)
python treasury.py fields mts_table_9 --filter "line_code_nbr:eq:120"
python treasury.py fields avg_interest_rates --filter "security_type:eq:Bill" --schema

# JSON output
python treasury.py fields rates_of_exchange --json
python treasury.py fields revenue_collections --schema --json
```

### Manifest, Search, List, Examples

```bash
# Full manifest (all categories, endpoints, filter format)
python treasury.py manifest
python treasury.py manifest --json

# Search endpoints by keyword
python treasury.py search debt
python treasury.py search "interest" --json
python treasury.py search mts
python treasury.py search exchange
python treasury.py search savings
python treasury.py search gold

# List endpoint keys
python treasury.py list
python treasury.py list --json
python treasury.py list debt
python treasury.py list accounting
python treasury.py list interest_rates
python treasury.py list securities
python treasury.py list revenue
python treasury.py list other --json

# Sample query patterns
python treasury.py examples
python treasury.py examples --json
```

### Endpoints Browser

```bash
# List all endpoints grouped by category
python treasury.py endpoints
python treasury.py endpoints list

# Get data from an endpoint
python treasury.py endpoints get debt_to_penny
python treasury.py endpoints get debt_to_penny --json
python treasury.py endpoints get mts_table_1 --from-date 2024-01-01 --json
python treasury.py endpoints get dts_table_1 --page-size 20 --json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--limit N` | Max rows in output | cusips, auctions, debt, interest-rates, exchange, revenue, get |
| `--from-date YYYY-MM-DD` | Filter records from date | cusips, auctions, debt, interest-rates, exchange, revenue, get |
| `--to-date YYYY-MM-DD` | Filter records to date | cusips, auctions, debt, interest-rates, exchange, revenue, get |
| `--filter EXPR` / `-f` | Raw API filter (`field:op:value`) | cusips, auctions, debt, interest-rates, exchange, revenue, get, fields |
| `--fields F1,F2,...` | Select columns (comma-separated) | cusips, debt, interest-rates, exchange, revenue, get |
| `--security-type T` / `-s` | Filter by security type | cusips, auctions, interest-rates |
| `--sort EXPR` | Sort expression (prefix `-` for desc) | get |
| `--page-number N` / `-p` | Fetch specific page (1-based) | get |
| `--page-size N` | Rows per page | get, endpoints |
| `--all` | Fetch all pages (paginate fully) | get |
| `--progress` | Show progress for long fetches | cusips (full-universe), get |
| `--no-date-filters` | Ignore from/to-date; use --filter only | get |
| `--unique` | Output unique CUSIPs only | cusips |
| `--full-universe` | Full CUSIP universe across endpoints | cusips |
| `--record-setting` | Record-setting auctions | auctions |
| `--currencies C1,C2` / `-c` | Country-currency filter | exchange |
| `--schema` | Full schema with labels and dataTypes | fields |
| `--query TEXT` | Search term | search (positional) |


## Python Recipes

### Treasury Buybacks

```python
from treasury import get_buybacks, get_auctions_data

# All buyback operations (191 total, 2000-present + 2024-present restart)
all_buybacks = get_buybacks()

# Liquidity Support operations only
liq = get_buybacks(operation_type="Liquidity Support")

# Cash Management operations
cash = get_buybacks(operation_type="Cash Management")

# TIPS buybacks
tips_bb = get_buybacks(security_type="TIPS")

# Only completed operations with results
completed = get_buybacks(with_results_only=True)

# Date range
recent = get_buybacks(from_date="2025-01-01", to_date="2026-04-15")

# Buyback fields: operation_date, operation_type, security_type, maturity_bucket,
# total_par_amt_offered, total_par_amt_accepted, nbr_issues_accepted,
# nbr_issues_eligible, max_par_amt_redeemed, settlement_date, par_amt_per_offer

# Full auction pricing data (bills, notes, bonds, TIPS, FRN)
auction_data = get_auctions_data(security_type="Note", from_date="2025-01-01")
by_cusip = get_auctions_data(cusip="91282CQJ3")
```

### Discovery and Schema

```python
from treasury import (
    get_registry, list_keys, search_endpoints, get_manifest, get_examples,
    discover_fields, discover_schema, CATEGORIES, ENDPOINT_REGISTRY,
)

# Full endpoint registry (80+ entries)
# Returns: dict[str, dict] with endpoint, table_name, category, date_field
registry = get_registry()

# List all keys or keys for a category
# category: "auctions"|"debt"|"accounting"|"interest_rates"|"securities"|"revenue"|"payments"|"other"
all_keys = list_keys()
debt_keys = list_keys("debt")
acct_keys = list_keys("accounting")

# Search endpoints by keyword (matches key or table_name)
# Returns: list of {key, table_name, category, endpoint}
results = search_endpoints("debt")
results = search_endpoints("interest")
results = search_endpoints("mts")
results = search_endpoints("exchange")

# Full manifest for LLM consumption
# Returns: {base_url, categories, endpoints_by_category, filter_format, date_format, total_endpoints}
manifest = get_manifest()

# Sample query patterns
# Returns: list of {desc, key, filter, fields, sort, max_rows}
examples = get_examples()

# Discover field names for any endpoint
# Returns: list[str] of field names
fields = discover_fields("debt_to_penny")
fields = discover_fields("mts_table_9")
fields = discover_fields("avg_interest_rates", sample_filter="security_type:eq:Bill")

# Full schema: fields + labels (display names) + dataTypes
# Returns: {key, fields, labels, dataTypes}
schema = discover_schema("debt_to_penny")
schema = discover_schema("dts_table_1")
schema = discover_schema("rates_of_exchange")
```

### Filter Utilities

```python
from treasury import (
    filter_eq, filter_in, filter_gte, filter_gt, filter_lte, filter_lt,
    build_filter, filter_date_range, FILTER_OPERATORS,
)

# Single field equals value
f = filter_eq("security_type", "Bill")           # "security_type:eq:Bill"

# Field in set of values
f = filter_in("country_currency_desc", ["Canada-Dollar", "Mexico-Peso"])
# "country_currency_desc:in:(Canada-Dollar,Mexico-Peso)"

# Comparison operators
f = filter_gte("record_date", "2024-01-01")       # "record_date:gte:2024-01-01"
f = filter_gt("avg_interest_rate_amt", "4.0")      # "avg_interest_rate_amt:gt:4.0"
f = filter_lte("record_date", "2025-12-31")        # "record_date:lte:2025-12-31"
f = filter_lt("tot_pub_debt_out_amt", "30000000")   # "tot_pub_debt_out_amt:lt:30000000"

# Combine multiple filters
f = build_filter(
    filter_eq("security_type", "Bill"),
    filter_gte("record_date", "2024-01-01"),
    filter_lte("record_date", "2025-12-31"),
)
# "security_type:eq:Bill,record_date:gte:2024-01-01,record_date:lte:2025-12-31"

# Date range shorthand
f = filter_date_range("record_date", from_date="2024-01-01", to_date="2025-12-31")
# "record_date:gte:2024-01-01,record_date:lte:2025-12-31"

f = filter_date_range("record_date", from_date="2024-01-01")
# "record_date:gte:2024-01-01"
```

### Generic Endpoint Access

```python
from treasury import get_endpoint, query, request_page

# get_endpoint: Fetch all rows (auto-paginates) for any registered key
# Returns: list[dict]
rows = get_endpoint("debt_to_penny", from_date="2024-01-01", to_date="2025-12-31")
rows = get_endpoint("mts_table_1", from_date="2024-01-01", max_pages=5)
rows = get_endpoint("dts_table_1", from_date="2025-01-01", fields=["record_date", "account_type", "close_today_bal"])
rows = get_endpoint("gold_reserve", max_pages=2)
rows = get_endpoint("avg_interest_rates", filter_expr="security_type:eq:Bill", from_date="2024-01-01")

# get_endpoint with sort, pagination control
rows = get_endpoint("debt_to_penny", sort="-record_date", page_size=500, max_pages=3)
rows = get_endpoint("mspd_table_3_market", page_number=1, page_size=50)

# get_endpoint with use_date_filters=False to bypass auto date filtering
rows = get_endpoint("record_setting_auction", use_date_filters=False, max_pages=2)
rows = get_endpoint("redemption_tables", use_date_filters=False, max_pages=1)

# get_endpoint with progress callback for long fetches
rows = get_endpoint("debt_to_penny", from_date="2000-01-01", show_progress=True)

# query: Maximum flexibility, returns {data, meta}
result = query("debt_to_penny", max_rows=10)
# result["data"] = list of row dicts, result["meta"] = API metadata

result = query("mts_table_9", filter_expr="line_code_nbr:eq:120",
               fields=["record_date", "classification_desc", "current_month_rcpt_outly_amt"],
               from_date="2024-01-01", max_rows=50)

result = query("rates_of_exchange",
               filter_expr="country_currency_desc:in:(Canada-Dollar,Mexico-Peso)",
               from_date="2024-01-01", max_rows=100)

result = query("avg_interest_rates", filter_expr="security_type:eq:Bill",
               page_number=1, page_size=20)

# request_page: Single page fetch, returns full API response (data + meta + links)
resp = request_page("debt_to_penny", page_number=1, page_size=10)
# resp["data"], resp["meta"], resp["links"]

resp = request_page("mts_table_9", page_number=1, page_size=50,
                     filter_expr="line_code_nbr:eq:120",
                     fields=["record_date", "classification_desc", "current_month_rcpt_outly_amt"])
```

### CUSIPs and Auctions

```python
from treasury import (
    get_cusips, get_unique_cusips, get_full_cusip_universe,
    get_upcoming_auctions, get_record_setting_auctions,
)

# CUSIPs from upcoming auctions
# Returns: list of dicts with cusip, security_type, security_term, auction_date, issue_date, offering_amt, reopening
rows = get_cusips()
rows = get_cusips(security_type="Bill")
rows = get_cusips(security_type="TIPS", from_date="2024-01-01")
rows = get_cusips(filter_expr="offering_amt:gte:50000", max_pages=5)
rows = get_cusips(fields=["cusip", "security_type", "auction_date"])

# Unique CUSIPs only
# Returns: sorted list[str]
cusips = get_unique_cusips()
cusips = get_unique_cusips(security_type="Note")
cusips = get_unique_cusips(from_date="2024-01-01", to_date="2025-12-31")

# Full CUSIP universe (upcoming_auctions + frn_daily_indexes)
# Returns: sorted list[str] -- maximizes API coverage
cusips = get_full_cusip_universe()
cusips = get_full_cusip_universe(show_progress=True)
cusips = get_full_cusip_universe(max_pages=10)

# Upcoming auctions
# Returns: list of dicts with full auction schedule fields
auctions = get_upcoming_auctions()
auctions = get_upcoming_auctions(security_type="Bond")
auctions = get_upcoming_auctions(from_date="2025-01-01", to_date="2025-12-31")
auctions = get_upcoming_auctions(filter_expr="offering_amt:gte:100000")

# Record-setting auctions
# Returns: list of dicts
records = get_record_setting_auctions()
records = get_record_setting_auctions(security_type="Bond")
records = get_record_setting_auctions(filter_expr="security_type:in:(Bill,Note)")
```

### Debt

```python
from treasury import get_debt_to_penny, get_endpoint

# Debt to the Penny
# Returns: list of dicts with record_date, tot_pub_debt_out_amt, intragov_hold_amt, etc.
rows = get_debt_to_penny()
rows = get_debt_to_penny(from_date="2024-01-01", to_date="2025-12-31")
rows = get_debt_to_penny(fields=["record_date", "tot_pub_debt_out_amt"])
rows = get_debt_to_penny(filter_expr="tot_pub_debt_out_amt:gte:34000000000000", max_pages=5)
rows = get_debt_to_penny(page_number=1, page_size=10)

# Historical Debt Outstanding
rows = get_endpoint("debt_outstanding", max_pages=5)

# Schedules of Federal Debt
rows = get_endpoint("schedules_fed_debt", from_date="2024-01-01", max_pages=3)
rows = get_endpoint("schedules_fed_debt_fytd", from_date="2024-01-01")

# MSPD tables
rows = get_endpoint("mspd_table_1", from_date="2024-01-01")
rows = get_endpoint("mspd_table_3_market", from_date="2025-01-01", max_pages=2)
rows = get_endpoint("mspd_table_3_nonmarket", from_date="2025-01-01")

# Statutory Debt Limit
rows = get_endpoint("mspd_table_2", max_pages=3)

# TROR
rows = get_endpoint("tror", use_date_filters=False, max_pages=2)
rows = get_endpoint("tror_delinquent_debt", use_date_filters=False, max_pages=2)

# Treasury Offset Program
rows = get_endpoint("top_federal", use_date_filters=False, max_pages=2)
```

### Accounting -- MTS and DTS

```python
from treasury import get_mts_table, get_dts_table

# MTS tables: table param is "1"-"9", "6a", "6b", "6c", "6d", "6e"
# Returns: list of dicts

# Receipts, Outlays, Deficit/Surplus
rows = get_mts_table("1", from_date="2024-01-01")

# Receipts by Source, Outlays by Function
rows = get_mts_table("9", from_date="2024-01-01")
rows = get_mts_table("9", filter_expr="line_code_nbr:eq:120",
                     fields=["record_date", "classification_desc", "current_month_rcpt_outly_amt"])

# Means of Financing the Deficit
rows = get_mts_table("6", from_date="2024-01-01")

# Receipts and Outlays by Month
rows = get_mts_table("7", from_date="2023-01-01", max_pages=5)

# Trust Fund Impact
rows = get_mts_table("8", from_date="2024-01-01")

# DTS tables: table param is "1"-"6", "3a", "3b", "3c"
# Returns: list of dicts

# Operating Cash Balance (TGA balance)
rows = get_dts_table("1", from_date="2025-01-01")
rows = get_dts_table("1", from_date="2025-01-01",
                     fields=["record_date", "account_type", "close_today_bal", "open_today_bal"])

# Deposits and Withdrawals
rows = get_dts_table("2", from_date="2025-03-01", max_pages=3)

# Public Debt Transactions
rows = get_dts_table("3a", from_date="2025-01-01")

# Debt Subject to Limit
rows = get_dts_table("3c", from_date="2025-01-01")

# Federal Tax Deposits
rows = get_dts_table("4", from_date="2025-01-01")

# Income Tax Refunds Issued
rows = get_dts_table("6", from_date="2025-01-01", to_date="2025-04-30")
```

### Interest Rates and Exchange Rates

```python
from treasury import get_avg_interest_rates, get_rates_of_exchange, get_endpoint

# Average interest rates on Treasury securities
# Returns: list of dicts with record_date, security_type, security_term, avg_interest_rate_amt, etc.
rows = get_avg_interest_rates()
rows = get_avg_interest_rates(security_type="Bill")
rows = get_avg_interest_rates(security_type="Note", from_date="2024-01-01")
rows = get_avg_interest_rates(filter_expr="avg_interest_rate_amt:gte:4.0", from_date="2024-01-01")

# Exchange rates
# Returns: list of dicts with country_currency_desc, exchange_rate, record_date, etc.
rows = get_rates_of_exchange()
rows = get_rates_of_exchange(country_currency=["Canada-Dollar", "Mexico-Peso"])
rows = get_rates_of_exchange(country_currency=["Japan-Yen"], from_date="2024-01-01")
rows = get_rates_of_exchange(country_currency=["Euro Zone-Euro", "United Kingdom-Pound"],
                              from_date="2024-01-01", to_date="2025-12-31")

# Interest expense on public debt
rows = get_endpoint("interest_expense", from_date="2020-01-01", max_pages=5)

# Qualified tax credit bond rates
rows = get_endpoint("qualified_tax", max_pages=3)

# Unemployment Trust Fund quarterly yields
rows = get_endpoint("utf_qtr_yields", from_date="2020-01-01")
```

### Revenue

```python
from treasury import get_revenue_collections

# Revenue collections
# Returns: list of dicts with record_date, net_collections_amt, tax_category_desc, etc.
rows = get_revenue_collections()
rows = get_revenue_collections(from_date="2024-01-01", to_date="2025-12-31")
rows = get_revenue_collections(filter_expr="tax_category_id:eq:3")
rows = get_revenue_collections(fields=["record_date", "net_collections_amt", "tax_category_desc"],
                                from_date="2024-01-01")
rows = get_revenue_collections(page_number=1, page_size=50)
```

### Other Endpoints

```python
from treasury import get_endpoint

# Gold reserve
rows = get_endpoint("gold_reserve", max_pages=2)
rows = get_endpoint("gold_reserve", fields=["record_date", "fine_troy_oz", "book_value_amt"])

# Gift contributions to reduce public debt
rows = get_endpoint("gift_contributions", max_pages=2)

# Balance sheets
rows = get_endpoint("balance_sheets", from_date="2020-01-01")

# Long-term fiscal projections
rows = get_endpoint("long_term_projections", max_pages=3)

# Social insurance
rows = get_endpoint("social_insurance", max_pages=3)

# Savings bonds
rows = get_endpoint("savings_bonds_report", from_date="2024-01-01")
rows = get_endpoint("savings_bonds_mud", from_date="2024-01-01")

# SLGS
rows = get_endpoint("slgs_statistics", from_date="2024-01-01")
rows = get_endpoint("slgs_securities", from_date="2024-01-01")

# Securities in TreasuryDirect
rows = get_endpoint("securities_sales", from_date="2024-01-01")
rows = get_endpoint("securities_outstanding", from_date="2024-01-01")

# Judgment Fund
rows = get_endpoint("jfics_congress_report", max_pages=3)
```

### Error Handling

```python
from treasury import FiscalDataError, get_endpoint, query

# FiscalDataError has: http_status, api_error, api_message
try:
    rows = get_endpoint("nonexistent_key")
except ValueError as e:
    # Unknown endpoint key
    pass

try:
    rows = get_endpoint("debt_to_penny", filter_expr="bad_field:eq:foo")
except FiscalDataError as e:
    print(e.http_status)    # e.g. 400
    print(e.api_error)      # API error code
    print(e.api_message)    # API error message
```


## Composite Recipes

### TGA Cash Balance Snapshot

```bash
python treasury.py get dts_table_1 --from-date $(date -v-30d +%Y-%m-%d) --fields "record_date,account_type,close_today_bal,open_today_bal" --json
```

PRISM receives: daily Treasury General Account balances for the past 30 days, opening and closing balances by account type.

### Deficit / Surplus Tracking

```bash
python treasury.py get mts_table_1 --from-date $(date -v-12m +%Y-%m-%d) --json
python treasury.py get mts_table_9 --from-date $(date -v-12m +%Y-%m-%d) --filter "line_code_nbr:eq:120" --fields "record_date,classification_desc,current_month_rcpt_outly_amt" --json
```

PRISM receives: 12 months of receipts/outlays/deficit summary from MTS Table 1, plus the line 120 receipts total from MTS Table 9 for source-level breakdown.

### Debt Level and Composition

```bash
python treasury.py debt --from-date $(date -v-12m +%Y-%m-%d) --fields "record_date,tot_pub_debt_out_amt,intragov_hold_amt" --json
python treasury.py get mspd_table_1 --from-date $(date -v-6m +%Y-%m-%d) --json
python treasury.py get mspd_table_3_market --from-date $(date -v-3m +%Y-%m-%d) --json
```

PRISM receives: debt to the penny trajectory over 12 months, summary of securities outstanding from MSPD Table 1, and detail of marketable securities for composition analysis.

### Treasury Issuance Pipeline

```bash
python treasury.py auctions --json
python treasury.py cusips --unique --json
python treasury.py get schedules_fed_debt --from-date $(date -v-3m +%Y-%m-%d) --json
```

PRISM receives: upcoming auction schedule with CUSIPs and offering amounts, unique CUSIP list, and recent federal debt schedules for issuance context.

### Interest Cost Monitor

```bash
python treasury.py interest-rates --from-date $(date -v-12m +%Y-%m-%d) --json
python treasury.py get interest_expense --from-date $(date -v-24m +%Y-%m-%d) --json
python treasury.py get avg_interest_rates --filter "security_type:eq:Bill" --from-date $(date -v-12m +%Y-%m-%d) --json
python treasury.py get avg_interest_rates --filter "security_type:eq:Note" --from-date $(date -v-12m +%Y-%m-%d) --json
```

PRISM receives: average interest rates across all security types over 12 months, interest expense on public debt over 24 months, plus Bill and Note rate histories separately.

### Fiscal Flow Analysis (DTS Deep Dive)

```bash
python treasury.py get dts_table_1 --from-date $(date -v-60d +%Y-%m-%d) --json
python treasury.py get dts_table_2 --from-date $(date -v-30d +%Y-%m-%d) --json
python treasury.py get dts_table_3a --from-date $(date -v-30d +%Y-%m-%d) --json
python treasury.py get dts_table_3c --from-date $(date -v-30d +%Y-%m-%d) --json
python treasury.py get dts_table_4 --from-date $(date -v-30d +%Y-%m-%d) --json
```

PRISM receives: 60-day TGA balance trajectory, 30 days of deposits/withdrawals, public debt transactions, debt subject to limit, and federal tax deposits.

### Revenue Deep Dive

```bash
python treasury.py revenue --from-date $(date -v-24m +%Y-%m-%d) --json
python treasury.py revenue --filter "tax_category_id:eq:1" --from-date $(date -v-24m +%Y-%m-%d) --json
python treasury.py revenue --filter "tax_category_id:eq:2" --from-date $(date -v-24m +%Y-%m-%d) --json
python treasury.py revenue --filter "tax_category_id:eq:3" --from-date $(date -v-24m +%Y-%m-%d) --json
```

PRISM receives: 24-month total revenue collections plus breakdowns by tax category ID (individual income, corporate income, excise, etc.).

### Exchange Rate Surveillance

```bash
python treasury.py exchange -c "Canada-Dollar,Mexico-Peso,Japan-Yen,Euro Zone-Euro,United Kingdom-Pound,China-Yuan" --from-date $(date -v-12m +%Y-%m-%d) --json
```

PRISM receives: 12-month exchange rate history for major currency pairs from Treasury reporting rates.

### Debt Limit Monitor

```bash
python treasury.py get mspd_table_2 --json
python treasury.py get dts_table_3c --from-date $(date -v-90d +%Y-%m-%d) --json
python treasury.py debt --from-date $(date -v-30d +%Y-%m-%d) --fields "record_date,tot_pub_debt_out_amt" --json
```

PRISM receives: statutory debt limit from MSPD Table 2, 90-day debt subject to limit from DTS, and 30-day debt to the penny trajectory.

### Full Endpoint Discovery

```bash
python treasury.py manifest --json
python treasury.py fields debt_to_penny --schema --json
python treasury.py fields mts_table_9 --schema --json
python treasury.py fields dts_table_1 --schema --json
python treasury.py fields avg_interest_rates --schema --json
python treasury.py fields rates_of_exchange --schema --json
```

PRISM receives: complete API manifest with all categories and endpoints, plus full schemas (field names, labels, data types) for key endpoints.


## Cross-Source Recipes

### Fiscal Drain + Funding Conditions

```bash
python treasury.py get dts_table_1 --from-date $(date -v-30d +%Y-%m-%d) --fields "record_date,account_type,close_today_bal" --json
python GS/data/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: TGA cash balance trajectory + overnight funding rates and RRP usage. Reserve flow tracking via fiscal drain/release against money market conditions.

### Issuance Supply + Auction Demand

```bash
python treasury.py auctions --json
python treasury.py cusips --json
python GS/data/apis/treasurydirect/treasurydirect.py api auctions --days 30
```

PRISM receives: upcoming Treasury auction schedule from Fiscal Data + recent auction results (bid-to-cover, tails) from TreasuryDirect. Supply pipeline vs absorption capacity.

### Debt Trajectory + Fed Balance Sheet

```bash
python treasury.py debt --from-date $(date -v-12m +%Y-%m-%d) --fields "record_date,tot_pub_debt_out_amt" --json
python GS/data/apis/nyfed/nyfed.py soma-history --weeks 52 --json
python GS/data/apis/nyfed/nyfed.py qt-monitor --weeks 26 --json
```

PRISM receives: 12-month debt to the penny + 52-week SOMA holdings history + QT runoff pace. Net supply context: new issuance pace vs Fed runoff.

### Interest Rates + Yield Curve

```bash
python treasury.py interest-rates --from-date $(date -v-12m +%Y-%m-%d) --json
python GS/data/apis/fred/fred.py rates --json
```

PRISM receives: Treasury average interest rates by security type + FRED term rates / yield curve. Weighted average cost of debt vs market rates.

### Exchange Rates + BIS Cross-Border

```bash
python treasury.py exchange -c "Japan-Yen,Euro Zone-Euro,United Kingdom-Pound,China-Yuan" --from-date $(date -v-12m +%Y-%m-%d) --json
python GS/data/apis/bis/bis.py get lbs --json
```

PRISM receives: Treasury FX rates for major pairs + BIS locational banking statistics for cross-border flow context.

### Revenue + Employment

```bash
python treasury.py revenue --from-date $(date -v-24m +%Y-%m-%d) --json
python GS/data/apis/fred/fred.py series PAYEMS --json
```

PRISM receives: 24-month revenue collections (tax receipts) + payroll employment data. Macro revenue linkage: employment drives income tax receipts.

### Deficit + CFTC Positioning

```bash
python treasury.py get mts_table_1 --from-date $(date -v-12m +%Y-%m-%d) --json
python treasury.py debt --from-date $(date -v-6m +%Y-%m-%d) --json
python GS/data/apis/cftc/cftc.py rates --json
```

PRISM receives: MTS deficit/surplus data + debt trajectory + CFTC speculative positioning in Treasuries. Fiscal backdrop against market positioning.

### TGA + RRP Liquidity Complex

```bash
python treasury.py get dts_table_1 --from-date $(date -v-60d +%Y-%m-%d) --fields "record_date,account_type,close_today_bal" --json
python GS/data/apis/nyfed/nyfed.py rrp --count 30 --json
python GS/data/apis/nyfed/nyfed.py rates --json
```

PRISM receives: 60-day TGA balance + 30-day ON RRP operations + current overnight rates. Full reserve flow picture: TGA drain/fill, RRP drainage, rate impact.

### Debt Limit + Prediction Markets

```bash
python treasury.py get mspd_table_2 --json
python treasury.py get dts_table_3c --from-date $(date -v-90d +%Y-%m-%d) --json
python GS/data/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: statutory debt limit + debt subject to limit trajectory + market-implied policy probabilities. Debt ceiling context against policy expectations.

### Gold Reserve + Exchange Rates

```bash
python treasury.py get gold_reserve --json
python treasury.py exchange -c "Euro Zone-Euro,Japan-Yen,China-Yuan" --from-date $(date -v-12m +%Y-%m-%d) --json
```

PRISM receives: U.S. Treasury gold holdings + major FX pair history. Reserve asset context.


## Setup

1. No API key required
2. No external dependencies (stdlib only: `urllib`, `json`, `argparse`)
3. Test: `python treasury.py list`
4. Full test: `python treasury.py get debt_to_penny --limit 5 --json`
5. Interactive: `python treasury.py` (launches menu)


## Architecture

```
treasury.py
  Constants       BASE_URL, CATEGORIES (8), ENDPOINT_REGISTRY (80+), FILTER_OPERATORS (6), SAMPLE_QUERIES (8)
  Errors          FiscalDataError (http_status, api_error, api_message)
  HTTP            _request() -> single page, _fetch_all_pages() -> auto-pagination with progress callback
  URL Builder     _build_url() with fields, filter, sort, page_number, page_size
  Discovery       get_registry(), list_keys(category), search_endpoints(q), get_manifest(), get_examples()
  Schema          discover_fields(key), discover_schema(key) -> {fields, labels, dataTypes}
  Filters         filter_eq, filter_in, filter_gte, filter_gt, filter_lte, filter_lt,
                  build_filter(*clauses), filter_date_range(field, from, to)
  Generic Query   get_endpoint(key, ...), query(key, ...), request_page(key, ...)
  Domain Getters  get_cusips, get_unique_cusips, get_full_cusip_universe,
                  get_upcoming_auctions, get_record_setting_auctions,
                  get_debt_to_penny, get_avg_interest_rates, get_rates_of_exchange,
                  get_revenue_collections, get_mts_table(table), get_dts_table(table)
  Display         _print_json(), _print_table(rows, limit)
  Interactive     7-item main menu -> 6 domain submenus + endpoint browser
  Argparse        12 subcommands: cusips, auctions, debt, interest-rates, exchange,
                  revenue, get, fields, manifest, search, list, examples, endpoints
```

Subcommands:
```
cusips         CUSIPs from upcoming auctions (--full-universe, --unique, -s, --from/to-date, -f, --fields, --limit, --progress)
auctions       Auction schedules (--record-setting, -s, --from/to-date, -f, --limit)
debt           Debt to the Penny (--from/to-date, -f, --fields, --limit)
interest-rates Average interest rates (-s, --from/to-date, -f, --fields, --limit)
exchange       Rates of exchange (-c, --from/to-date, -f, --fields, --limit)
revenue        Revenue collections (--from/to-date, -f, --fields, --limit)
get            Universal endpoint query (key, --from/to-date, -f, --sort, --fields, --limit, -p, --page-size, --all, --no-date-filters, --progress)
fields         Discover field names (key, --filter, --schema)
manifest       Full API manifest
search         Search endpoints by keyword (query)
list           List endpoint keys ([category])
examples       Sample query patterns
endpoints      Endpoint browser (list|get, key, --from/to-date, --page-size)
```

Filter format:
```
field:op:value
ops: eq, in, gte, gt, lte, lt
multi: field:op:val,field2:op:val
in-set: field:in:(val1,val2,val3)
dates: YYYY-MM-DD
```
