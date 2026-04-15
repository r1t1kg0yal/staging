I want to be able to get
- List of available CUSIPs
- Auction schedules
- Anything else - all of the datasets basically

Everything must be hyper organized and structured - want an LLM to be able to use this API

https://fiscaldata.treasury.gov/api-documentation/

---

## Integration (fiscal_data_api.py)

Single script for full interaction with 80+ Fiscal Data API endpoints.

**Usage:** `python fiscal_data_api.py` (interactive) or:

- `python fiscal_data_api.py cusips|auctions|debt|interest-rates|exchange|revenue|get|endpoints|fields|manifest|search|list|examples [args]`
- `python fiscal_data_api.py get <key>` -- universal query (--filter, --fields, --page-number, --no-date-filters)
- `python fiscal_data_api.py manifest` -- full manifest for LLM (categories, endpoints, filter format)
- `python fiscal_data_api.py search <q>` -- find endpoints by keyword
- `python fiscal_data_api.py list [category]` -- list keys, optionally by category
- `python fiscal_data_api.py examples` -- sample query patterns
- `python fiscal_data_api.py fields <key> [--schema]` -- field names or full schema (labels, dataTypes)

**LLM programmatic API:** get_registry, list_keys, search_endpoints, get_manifest, get_examples, discover_fields, discover_schema, query, get_endpoint, filter utilities, FiscalDataError. See `__all__` and module docstring.

**Note:** Treasury Securities Auctions Data (historical 1979-present) is on the website but has no public API endpoint. Full CUSIP universe via API: `get_full_cusip_universe()` combines upcoming_auctions + frn_daily_indexes (max coverage). CLI: `cusips --full-universe`.