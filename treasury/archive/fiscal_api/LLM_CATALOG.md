# Fiscal Data API - LLM Catalog

Structured reference for LLM consumption. Use this to understand available datasets and how to query them.

## Base URL

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/
```

No authentication. GET requests only. JSON response by default.

## Parameters

| Param | Description | Example |
|-------|-------------|---------|
| `fields` | Comma-separated field names | `fields=cusip,auction_date,security_type` |
| `filter` | Filter expression | `filter=record_date:gte:2024-01-01` |
| `sort` | Sort field (prefix `-` for desc) | `sort=-record_date` |
| `page[number]` | Page index (1-based) | `page[number]=1` |
| `page[size]` | Rows per page | `page[size]=100` |
| `format` | json, csv, xml | `format=json` |

### Filter operators

- `eq` = equal
- `in` = in list, e.g. `filter=security_type:in:(Bill,Note)`
- `gte` = greater than or equal
- `lte` = less than or equal
- `gt`, `lt`

## Key Endpoints (by use case)

### CUSIPs and auction schedules

| Key | Endpoint | Description |
|-----|----------|-------------|
| `upcoming_auctions` | `v1/accounting/od/upcoming_auctions` | Auction announcements with CUSIP, security type/term, auction date, issue date, offering amount |
| `record_setting_auction` | `v2/accounting/od/record_setting_auction` | Record highs/lows: rates, offering amounts, bid-to-cover |

### Debt

| Key | Endpoint | Description |
|-----|----------|-------------|
| `debt_to_penny` | `v2/accounting/od/debt_to_penny` | Total public debt outstanding by date |
| `debt_outstanding` | `v2/accounting/od/debt_outstanding` | Historical debt outstanding |
| `mspd_table_3_market` | `v1/debt/mspd/mspd_table_3_market` | Marketable Treasury securities outstanding (by CUSIP) |

### Interest rates

| Key | Endpoint | Description |
|-----|----------|-------------|
| `avg_interest_rates` | `v2/accounting/od/avg_interest_rates` | Average interest rates on Treasury securities |
| `rates_of_exchange` | `v1/accounting/od/rates_of_exchange` | Foreign exchange rates |
| `interest_expense` | `v2/accounting/od/interest_expense` | Interest expense on public debt |

### Accounting (MTS, DTS)

| Key | Endpoint | Description |
|-----|----------|-------------|
| `mts_table_1` | `v1/accounting/mts/mts_table_1` | Summary receipts, outlays, deficit/surplus |
| `dts_table_1` | `v1/accounting/dts/dts_table_1` | Operating cash balance |
| `dts_table_2` | `v1/accounting/dts/dts_table_2` | Deposits and withdrawals of operating cash |

### Revenue

| Key | Endpoint | Description |
|-----|----------|-------------|
| `revenue_collections` | `v2/revenue/rcm` | U.S. government revenue collections |

## Python usage

```python
from fiscal_api import (
    get_cusips,
    get_unique_cusips,
    get_upcoming_auctions,
    get_record_setting_auctions,
    get_debt_to_penny,
    get_avg_interest_rates,
    get_rates_of_exchange,
    FiscalDataClient,
    get_endpoint_info,
)

# CUSIPs
cusips = get_unique_cusips(security_type="Bill")
rows = get_cusips(security_type="Note", from_date="2024-01-01")

# Auction schedule
auctions = get_upcoming_auctions(security_type="Bond", from_date="2024-01-01")

# Debt
debt = get_debt_to_penny(from_date="2024-01-01", to_date="2024-12-31")

# Arbitrary endpoint
info = get_endpoint_info("debt_to_penny")
client = FiscalDataClient()
resp = client.get(info["endpoint"], page_size=10)
```

## Response structure

```json
{
  "data": [ { "field1": "val1", ... } ],
  "meta": {
    "count": 10,
    "total-count": 101,
    "total-pages": 11,
    "labels": { "field1": "Display Name" },
    "dataTypes": { "field1": "STRING" }
  },
  "links": { "self": "...", "next": "...", "last": "..." }
}
```

## Notes

- Treasury Securities Auctions Data (historical, 1979-present) is listed on fiscaldata.treasury.gov but does not appear to have a public API endpoint; use `upcoming_auctions` for announced auctions and CUSIPs.
- Some endpoints reject the `sort` parameter; omit it if you get 400.
- Date format: `YYYY-MM-DD`.
