#!/usr/bin/env python3
"""
U.S. Treasury Fiscal Data API - single script.

Full interaction with 80+ Fiscal Data API endpoints: CUSIPs, auctions, debt,
MTS, DTS, MSPD, revenue, interest rates, exchange rates, securities, TROR,
and more. Interactive mode (no args) or non-interactive subcommands.

Base: https://api.fiscaldata.treasury.gov/services/api/fiscal_service/
Docs: https://fiscaldata.treasury.gov/api-documentation/

LLM / programmatic use:
  Discovery: get_registry(), list_keys(category), search_endpoints(q), get_manifest(), get_examples()
  Schema: discover_fields(key), discover_schema(key) -> {fields, labels, dataTypes}
  Query: get_endpoint(), query(), request_page()
  Filters: filter_eq, filter_in, filter_gte, filter_lte, build_filter, filter_date_range
  Domain getters: get_cusips, get_debt_to_penny, get_mts_table, get_dts_table, etc.
  Errors: FiscalDataError (http_status, api_error, api_message)
  CLI: manifest, search <q>, list [category], examples, fields <key> [--schema]
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

__all__ = [
    "BASE_URL", "CATEGORIES", "ENDPOINT_REGISTRY", "FILTER_OPERATORS",
    "filter_eq", "filter_in", "filter_gte", "filter_gt", "filter_lte", "filter_lt",
    "build_filter", "filter_date_range",
    "get_registry", "list_keys", "get_manifest", "search_endpoints",
    "request_page", "discover_fields", "discover_schema",
    "get_endpoint", "query",
    "get_cusips", "get_unique_cusips", "get_upcoming_auctions", "get_record_setting_auctions",
    "get_debt_to_penny", "get_avg_interest_rates", "get_rates_of_exchange",
    "get_revenue_collections", "get_mts_table", "get_dts_table",
    "get_examples", "FiscalDataError",
]

# API filter operators: eq, in, gte, gt, lte, lt. Format: field:op:value, multi: field:op:val,field2:op:val
FILTER_OPERATORS = ("eq", "in", "gte", "gt", "lte", "lt")

CATEGORIES = {
    "auctions": "Auction schedules, CUSIPs, record-setting auction data",
    "debt": "Debt to penny, outstanding, schedules, MSPD, TROR, TOP",
    "accounting": "MTS, DTS, financial reports, reconciliations",
    "interest_rates": "Average rates, exchange rates, yields",
    "securities": "Savings bonds, TreasuryDirect, SLGS, redemption tables",
    "revenue": "Revenue collections, tax receipts",
    "payments": "Judgment Fund, advances",
    "other": "Gold reserve, gift contributions, misc",
}

# Full endpoint registry: 80+ endpoints. date_field = primary date filter field for generic queries.
ENDPOINT_REGISTRY: dict[str, dict] = {
    # Auctions
    "upcoming_auctions": {"endpoint": "v1/accounting/od/upcoming_auctions", "table_name": "Treasury Securities Upcoming Auctions", "category": "auctions", "date_field": "record_date"},
    "record_setting_auction": {"endpoint": "v2/accounting/od/record_setting_auction", "table_name": "Record-Setting Auction", "category": "auctions"},
    # Debt
    "debt_to_penny": {"endpoint": "v2/accounting/od/debt_to_penny", "table_name": "Debt to the Penny", "category": "debt", "date_field": "record_date"},
    "debt_outstanding": {"endpoint": "v2/accounting/od/debt_outstanding", "table_name": "Historical Debt Outstanding", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt": {"endpoint": "v1/accounting/od/schedules_fed_debt", "table_name": "Schedules of Federal Debt by Month", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt_fytd": {"endpoint": "v1/accounting/od/schedules_fed_debt_fytd", "table_name": "Schedules of Federal Debt Fiscal Year-to-Date", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt_daily_activity": {"endpoint": "v1/accounting/od/schedules_fed_debt_daily_activity", "table_name": "Schedules of Federal Debt Daily Activity", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt_daily_summary": {"endpoint": "v1/accounting/od/schedules_fed_debt_daily_summary", "table_name": "Schedules of Federal Debt Daily Summary", "category": "debt", "date_field": "record_date"},
    "mspd_table_1": {"endpoint": "v1/debt/mspd/mspd_table_1", "table_name": "Summary of Treasury Securities Outstanding", "category": "debt", "date_field": "record_date"},
    "mspd_table_2": {"endpoint": "v1/debt/mspd/mspd_table_2", "table_name": "Statutory Debt Limit", "category": "debt", "date_field": "record_date"},
    "mspd_table_3_market": {"endpoint": "v1/debt/mspd/mspd_table_3_market", "table_name": "Detail of Marketable Treasury Securities Outstanding", "category": "debt", "date_field": "record_date"},
    "mspd_table_3_nonmarket": {"endpoint": "v1/debt/mspd/mspd_table_3_nonmarket", "table_name": "Detail of Non-Marketable Treasury Securities Outstanding", "category": "debt", "date_field": "record_date"},
    "mspd_table_4": {"endpoint": "v1/debt/mspd/mspd_table_4", "table_name": "MSPD Historical Data", "category": "debt", "date_field": "record_date"},
    "mspd_table_5": {"endpoint": "v1/debt/mspd/mspd_table_5", "table_name": "Holdings of Treasury Securities in Stripped Form", "category": "debt", "date_field": "record_date"},
    "tror": {"endpoint": "v2/debt/tror", "table_name": "Treasury Report on Receivables Full Data", "category": "debt"},
    "tror_collected_outstanding": {"endpoint": "v2/debt/tror/collected_outstanding_recv", "table_name": "Collected and Outstanding Receivables", "category": "debt"},
    "tror_delinquent_debt": {"endpoint": "v2/debt/tror/delinquent_debt", "table_name": "Delinquent Debt", "category": "debt"},
    "tror_collections_delinquent": {"endpoint": "v2/debt/tror/collections_delinquent_debt", "table_name": "Collections on Delinquent Debt", "category": "debt"},
    "tror_written_off": {"endpoint": "v2/debt/tror/written_off_delinquent_debt", "table_name": "Written Off Delinquent Debt", "category": "debt"},
    "tror_data_act_compliance": {"endpoint": "v2/debt/tror/data_act_compliance", "table_name": "120 Day Delinquent Debt Referral Compliance", "category": "debt"},
    "top_federal": {"endpoint": "v1/debt/top/top_federal", "table_name": "Treasury Offset Program - Federal Collections", "category": "debt"},
    "top_state": {"endpoint": "v1/debt/top/top_state", "table_name": "Treasury Offset Program - State Programs", "category": "debt"},
    "title_xii": {"endpoint": "v2/accounting/od/title_xii", "table_name": "Advances to State Unemployment Funds (SSA Title XII)", "category": "debt", "date_field": "record_date"},
    "interest_uninvested": {"endpoint": "v2/accounting/od/interest_uninvested", "table_name": "Federal Borrowings Program: Interest on Uninvested Funds", "category": "debt", "date_field": "record_date"},
    "interest_cost_fund": {"endpoint": "v2/accounting/od/interest_cost_fund", "table_name": "Federal Investments Program: Interest Cost by Fund", "category": "debt", "date_field": "record_date"},
    # Accounting - MTS
    "mts_table_1": {"endpoint": "v1/accounting/mts/mts_table_1", "table_name": "Summary of Receipts, Outlays, Deficit/Surplus", "category": "accounting", "date_field": "record_date"},
    "mts_table_2": {"endpoint": "v1/accounting/mts/mts_table_2", "table_name": "Summary of Budget and Off-Budget Results", "category": "accounting", "date_field": "record_date"},
    "mts_table_3": {"endpoint": "v1/accounting/mts/mts_table_3", "table_name": "Summary of Receipts and Outlays", "category": "accounting", "date_field": "record_date"},
    "mts_table_4": {"endpoint": "v1/accounting/mts/mts_table_4", "table_name": "Receipts of the U.S. Government", "category": "accounting", "date_field": "record_date"},
    "mts_table_5": {"endpoint": "v1/accounting/mts/mts_table_5", "table_name": "Outlays of the U.S. Government", "category": "accounting", "date_field": "record_date"},
    "mts_table_6": {"endpoint": "v1/accounting/mts/mts_table_6", "table_name": "Means of Financing the Deficit", "category": "accounting", "date_field": "record_date"},
    "mts_table_6a": {"endpoint": "v1/accounting/mts/mts_table_6a", "table_name": "Analysis of Change in Excess of Liabilities", "category": "accounting", "date_field": "record_date"},
    "mts_table_6b": {"endpoint": "v1/accounting/mts/mts_table_6b", "table_name": "Securities Issued by Federal Agencies", "category": "accounting", "date_field": "record_date"},
    "mts_table_6c": {"endpoint": "v1/accounting/mts/mts_table_6c", "table_name": "Federal Agency Borrowing via Treasury Securities", "category": "accounting", "date_field": "record_date"},
    "mts_table_6d": {"endpoint": "v1/accounting/mts/mts_table_6d", "table_name": "Investments of Federal Government Accounts", "category": "accounting", "date_field": "record_date"},
    "mts_table_6e": {"endpoint": "v1/accounting/mts/mts_table_6e", "table_name": "Guaranteed and Direct Loan Financing", "category": "accounting", "date_field": "record_date"},
    "mts_table_7": {"endpoint": "v1/accounting/mts/mts_table_7", "table_name": "Receipts and Outlays by Month", "category": "accounting", "date_field": "record_date"},
    "mts_table_8": {"endpoint": "v1/accounting/mts/mts_table_8", "table_name": "Trust Fund Impact on Budget Results", "category": "accounting", "date_field": "record_date"},
    "mts_table_9": {"endpoint": "v1/accounting/mts/mts_table_9", "table_name": "Receipts by Source, Outlays by Function", "category": "accounting", "date_field": "record_date"},
    # Accounting - DTS
    "dts_table_1": {"endpoint": "v1/accounting/dts/dts_table_1", "table_name": "Operating Cash Balance", "category": "accounting", "date_field": "record_date"},
    "dts_table_2": {"endpoint": "v1/accounting/dts/dts_table_2", "table_name": "Deposits and Withdrawals of Operating Cash", "category": "accounting", "date_field": "record_date"},
    "dts_table_3a": {"endpoint": "v1/accounting/dts/dts_table_3a", "table_name": "Public Debt Transactions", "category": "accounting", "date_field": "record_date"},
    "dts_table_3b": {"endpoint": "v1/accounting/dts/dts_table_3b", "table_name": "Adjustment of Public Debt to Cash Basis", "category": "accounting", "date_field": "record_date"},
    "dts_table_3c": {"endpoint": "v1/accounting/dts/dts_table_3c", "table_name": "Debt Subject to Limit", "category": "accounting", "date_field": "record_date"},
    "dts_table_4": {"endpoint": "v1/accounting/dts/dts_table_4", "table_name": "Federal Tax Deposits (Inter-agency Tax Transfers)", "category": "accounting", "date_field": "record_date"},
    "dts_table_5": {"endpoint": "v1/accounting/dts/dts_table_5", "table_name": "Short-Term Cash Investments", "category": "accounting", "date_field": "record_date"},
    "dts_table_6": {"endpoint": "v1/accounting/dts/dts_table_6", "table_name": "Income Tax Refunds Issued", "category": "accounting", "date_field": "record_date"},
    # Accounting - Financial Report
    "statement_net_cost": {"endpoint": "v2/accounting/od/statement_net_cost", "table_name": "Statements of Net Cost", "category": "accounting", "date_field": "record_date"},
    "net_position": {"endpoint": "v1/accounting/od/net_position", "table_name": "Statements of Operations and Changes in Net Position", "category": "accounting", "date_field": "record_date"},
    "reconciliations": {"endpoint": "v1/accounting/od/reconciliations", "table_name": "Reconciliations of Net Operating Cost", "category": "accounting", "date_field": "record_date"},
    "cash_balance": {"endpoint": "v1/accounting/od/cash_balance", "table_name": "Statements of Changes in Cash Balance", "category": "accounting", "date_field": "record_date"},
    "balance_sheets": {"endpoint": "v2/accounting/od/balance_sheets", "table_name": "Balance Sheets", "category": "accounting", "date_field": "record_date"},
    "long_term_projections": {"endpoint": "v1/accounting/od/long_term_projections", "table_name": "Statements of Long-Term Fiscal Projections", "category": "accounting", "date_field": "record_date"},
    "social_insurance": {"endpoint": "v1/accounting/od/social_insurance", "table_name": "Statements of Social Insurance", "category": "accounting", "date_field": "record_date"},
    "insurance_amounts": {"endpoint": "v1/accounting/od/insurance_amounts", "table_name": "Statements of Changes in Social Insurance Amounts", "category": "accounting", "date_field": "record_date"},
    # Interest rates
    "avg_interest_rates": {"endpoint": "v2/accounting/od/avg_interest_rates", "table_name": "Average Interest Rates on U.S. Treasury Securities", "category": "interest_rates", "date_field": "record_date"},
    "rates_of_exchange": {"endpoint": "v1/accounting/od/rates_of_exchange", "table_name": "Treasury Reporting Rates of Exchange", "category": "interest_rates", "date_field": "record_date"},
    "interest_expense": {"endpoint": "v2/accounting/od/interest_expense", "table_name": "Interest Expense on the Public Debt Outstanding", "category": "interest_rates", "date_field": "record_date"},
    "qualified_tax": {"endpoint": "v2/accounting/od/qualified_tax", "table_name": "Historical Qualified Tax Credit Bond Interest Rates", "category": "interest_rates", "date_field": "record_date"},
    "utf_qtr_yields": {"endpoint": "v2/accounting/od/utf_qtr_yields", "table_name": "Unemployment Trust Fund Quarterly Yields", "category": "interest_rates", "date_field": "record_date"},
    # Securities
    "redemption_tables": {"endpoint": "v2/accounting/od/redemption_tables", "table_name": "Accrual Savings Bonds Redemption Tables", "category": "securities"},
    "slgs_statistics": {"endpoint": "v2/accounting/od/slgs_statistics", "table_name": "Monthly SLGS Securities Program", "category": "securities", "date_field": "record_date"},
    "slgs_savings_bonds": {"endpoint": "v1/accounting/od/slgs_savings_bonds", "table_name": "Savings Bonds Securities Sold", "category": "securities", "date_field": "record_date"},
    "sb_value": {"endpoint": "v2/accounting/od/sb_value", "table_name": "Savings Bonds Value Files", "category": "securities"},
    "slgs_securities": {"endpoint": "v1/accounting/od/slgs_securities", "table_name": "State and Local Government Series Securities", "category": "securities", "date_field": "record_date"},
    "securities_sales": {"endpoint": "v1/accounting/od/securities_sales", "table_name": "Securities Issued in TreasuryDirect - Sales", "category": "securities", "date_field": "record_date"},
    "securities_sales_term": {"endpoint": "v1/accounting/od/securities_sales_term", "table_name": "Securities Sales by Term", "category": "securities", "date_field": "record_date"},
    "securities_transfers": {"endpoint": "v1/accounting/od/securities_transfers", "table_name": "Transfers of Marketable Securities", "category": "securities", "date_field": "record_date"},
    "securities_conversions": {"endpoint": "v1/accounting/od/securities_conversions", "table_name": "Conversions of Paper Savings Bonds", "category": "securities", "date_field": "record_date"},
    "securities_redemptions": {"endpoint": "v1/accounting/od/securities_redemptions", "table_name": "Securities Redemptions", "category": "securities", "date_field": "record_date"},
    "securities_outstanding": {"endpoint": "v1/accounting/od/securities_outstanding", "table_name": "Securities Outstanding", "category": "securities", "date_field": "record_date"},
    "securities_c_of_i": {"endpoint": "v1/accounting/od/securities_c_of_i", "table_name": "Certificates of Indebtedness", "category": "securities", "date_field": "record_date"},
    "securities_accounts": {"endpoint": "v1/accounting/od/securities_accounts", "table_name": "Securities Accounts", "category": "securities", "date_field": "record_date"},
    "savings_bonds_report": {"endpoint": "v1/accounting/od/savings_bonds_report", "table_name": "Paper Savings Bonds Issues, Redemptions, Maturities by Series", "category": "securities", "date_field": "record_date"},
    "savings_bonds_mud": {"endpoint": "v1/accounting/od/savings_bonds_mud", "table_name": "Matured Unredeemed Debt", "category": "securities", "date_field": "record_date"},
    "savings_bonds_pcs": {"endpoint": "v1/accounting/od/savings_bonds_pcs", "table_name": "Piece Information by Series", "category": "securities", "date_field": "record_date"},
    # Revenue
    "revenue_collections": {"endpoint": "v2/revenue/rcm", "table_name": "U.S. Government Revenue Collections", "category": "revenue", "date_field": "record_date"},
    # Payments
    "jfics_congress_report": {"endpoint": "v2/payments/jfics/jfics_congress_report", "table_name": "Judgment Fund: Annual Report to Congress", "category": "payments", "date_field": "record_date"},
    # Other
    "gold_reserve": {"endpoint": "v2/accounting/od/gold_reserve", "table_name": "U.S. Treasury-Owned Gold", "category": "other", "date_field": "record_date"},
    "gift_contributions": {"endpoint": "v2/accounting/od/gift_contributions", "table_name": "Gift Contributions to Reduce the Public Debt", "category": "other", "date_field": "record_date"},
}


class FiscalDataError(Exception):
    """Raised when the Fiscal Data API returns an error or request fails."""
    def __init__(self, message: str, *, http_status: Optional[int] = None, api_error: Optional[str] = None, api_message: Optional[str] = None):
        super().__init__(message)
        self.http_status = http_status
        self.api_error = api_error
        self.api_message = api_message


def get_registry() -> dict[str, dict]:
    """Return full endpoint registry. LLM can inspect keys, categories, date_field, table_name."""
    return dict(ENDPOINT_REGISTRY)


def list_keys(category: Optional[str] = None) -> list[str]:
    """List endpoint keys. category: auctions|debt|accounting|interest_rates|securities|revenue|payments|other."""
    if category:
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category: {category}. Valid: {list(CATEGORIES.keys())}")
        return sorted(k for k, v in ENDPOINT_REGISTRY.items() if v.get("category") == category)
    return sorted(ENDPOINT_REGISTRY.keys())


def search_endpoints(q: str) -> list[dict[str, Any]]:
    """Search endpoints by key or table_name. Returns list of {key, table_name, category, endpoint}."""
    q = q.lower()
    out = []
    for key, info in ENDPOINT_REGISTRY.items():
        if q in key.lower() or q in info.get("table_name", "").lower():
            out.append({"key": key, "table_name": info["table_name"], "category": info.get("category", ""), "endpoint": info["endpoint"]})
    return out


SAMPLE_QUERIES: list[dict[str, Any]] = [
    {"desc": "Debt to penny, recent 10 rows", "key": "debt_to_penny", "fields": ["record_date", "tot_pub_debt_out_amt"], "sort": "-record_date", "max_rows": 10},
    {"desc": "MTS table 9, line 120 (receipts total)", "key": "mts_table_9", "filter": "line_code_nbr:eq:120", "fields": ["record_date", "classification_desc", "current_month_rcpt_outly_amt"]},
    {"desc": "Exchange rates Canada/Mexico 2024", "key": "rates_of_exchange", "filter": "country_currency_desc:in:(Canada-Dollar,Mexico-Peso),record_date:gte:2024-01-01", "fields": ["country_currency_desc", "exchange_rate", "record_date"]},
    {"desc": "Revenue collections by tax category", "key": "revenue_collections", "filter": "tax_category_id:eq:3", "fields": ["record_date", "net_collections_amt", "tax_category_desc"]},
    {"desc": "Average interest rates, Bills only", "key": "avg_interest_rates", "filter": "security_type:eq:Bill", "fields": ["record_date", "security_term", "avg_interest_rate_amt"]},
    {"desc": "CUSIPs for upcoming TIPS auctions", "key": "upcoming_auctions", "filter": "security_type:eq:TIPS", "fields": ["cusip", "auction_date", "offering_amt"]},
    {"desc": "DTS operating cash balance", "key": "dts_table_1", "fields": ["record_date", "account_type", "close_today_bal", "open_today_bal"]},
    {"desc": "Gold reserve", "key": "gold_reserve", "fields": ["record_date", "fine_troy_oz", "book_value_amt"]},
]


def get_examples() -> list[dict[str, Any]]:
    """Return sample query patterns. LLM can adapt these for its needs."""
    return list(SAMPLE_QUERIES)


def get_manifest() -> dict[str, Any]:
    """Full manifest for LLM: categories, endpoints by category, filter format, base URL."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for key, info in ENDPOINT_REGISTRY.items():
        cat = info.get("category", "other")
        by_cat.setdefault(cat, []).append({"key": key, "table_name": info["table_name"], "endpoint": info["endpoint"], "date_field": info.get("date_field")})
    return {
        "base_url": BASE_URL,
        "categories": dict(CATEGORIES),
        "endpoints_by_category": by_cat,
        "filter_format": "field:op:value; ops: eq,in,gte,gt,lte,lt; multi: field:op:val,field2:op:val",
        "date_format": "YYYY-MM-DD",
        "total_endpoints": len(ENDPOINT_REGISTRY),
    }


def _build_url(endpoint: str, *, fields: Optional[list[str]] = None, filter_expr: Optional[str] = None, sort: Optional[str] = None, page_number: int = 1, page_size: int = 100) -> str:
    params: dict[str, str] = {"format": "json", "page[number]": str(page_number), "page[size]": str(page_size)}
    if fields:
        params["fields"] = ",".join(fields)
    if filter_expr:
        params["filter"] = filter_expr
    if sort:
        params["sort"] = sort
    return f"{BASE_URL}/{endpoint.lstrip('/')}?{urllib.parse.urlencode(params)}"


def _request(endpoint: str, *, fields: Optional[list[str]] = None, filter_expr: Optional[str] = None, sort: Optional[str] = None, page_number: int = 1, page_size: int = 100, timeout: float = 30.0) -> dict[str, Any]:
    url = _build_url(endpoint, fields=fields, filter_expr=filter_expr, sort=sort, page_number=page_number, page_size=page_size)
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            out = json.loads(body)
            if "error" in out:
                raise FiscalDataError(
                    out.get("message", out.get("error", "API error")),
                    api_error=str(out.get("error", "")),
                    api_message=str(out.get("message", "")),
                )
            return out
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            err_body = json.loads(body)
            msg = err_body.get("message", err_body.get("error", str(e)))
        except json.JSONDecodeError:
            msg = f"HTTP {e.code}: {e.reason}"
        raise FiscalDataError(msg, http_status=e.code)
    except urllib.error.URLError as e:
        raise FiscalDataError(f"Request failed: {e.reason}")


def _fetch_all_pages(
    endpoint: str,
    *,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> list[dict[str, Any]]:
    all_data: list[dict[str, Any]] = []
    page, total_pages = 1, 1
    last_progress_time = 0.0
    while page <= total_pages:
        resp = _request(endpoint, fields=fields, filter_expr=filter_expr, sort=sort, page_number=page, page_size=page_size)
        all_data.extend(resp.get("data", []))
        total_pages = resp.get("meta", {}).get("total-pages", 1)
        if progress_callback and (page == 1 or time.monotonic() - last_progress_time >= 5.0):
            progress_callback(len(all_data), page, total_pages)
            last_progress_time = time.monotonic()
        if max_pages and page >= max_pages:
            break
        if page >= total_pages:
            break
        page += 1
    return all_data


def _get_endpoint_path(key: str) -> str | None:
    info = ENDPOINT_REGISTRY.get(key)
    return info["endpoint"] if info else None


# --- Filter utilities (LLM-friendly) ---

def filter_eq(field: str, value: str) -> str:
    """Build filter: field equals value. Example: filter_eq('security_type', 'Bill')"""
    return f"{field}:eq:{value}"


def filter_in(field: str, values: list[str]) -> str:
    """Build filter: field in set. Example: filter_in('country_currency_desc', ['Canada-Dollar','Mexico-Peso'])"""
    return f"{field}:in:({','.join(values)})"


def filter_gte(field: str, value: str) -> str:
    """Build filter: field >= value. Example: filter_gte('record_date', '2024-01-01')"""
    return f"{field}:gte:{value}"


def filter_gt(field: str, value: str) -> str:
    """Build filter: field > value."""
    return f"{field}:gt:{value}"


def filter_lte(field: str, value: str) -> str:
    """Build filter: field <= value."""
    return f"{field}:lte:{value}"


def filter_lt(field: str, value: str) -> str:
    """Build filter: field < value."""
    return f"{field}:lt:{value}"


def build_filter(*clauses: str) -> str:
    """Combine filter clauses with comma. Example: build_filter(filter_gte('record_date','2024-01-01'), filter_eq('security_type','Bill'))"""
    return ",".join(c for c in clauses if c)


def filter_date_range(field: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
    """Build date range filter. Returns combined clause or empty string."""
    clauses = []
    if from_date:
        clauses.append(filter_gte(field, from_date))
    if to_date:
        clauses.append(filter_lte(field, to_date))
    return build_filter(*clauses) if clauses else ""


def request_page(
    key: str,
    *,
    page_number: int = 1,
    page_size: int = 100,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch a single page. Returns full API response (data + meta + links). Use for slicing or exploring."""
    info = ENDPOINT_REGISTRY.get(key)
    if not info:
        raise ValueError(f"Unknown endpoint key: {key}")
    return _request(
        info["endpoint"],
        fields=fields,
        filter_expr=filter_expr,
        sort=sort,
        page_number=page_number,
        page_size=page_size,
    )


def discover_fields(key: str, *, sample_filter: Optional[str] = None) -> list[str]:
    """Fetch one row and return field names for the endpoint. Helps LLM choose fields for queries."""
    schema = discover_schema(key, sample_filter=sample_filter)
    return schema["fields"]


def discover_schema(key: str, *, sample_filter: Optional[str] = None) -> dict[str, Any]:
    """Fetch schema: fields, labels (display names), dataTypes. Use for building queries."""
    resp = request_page(key, page_size=1, filter_expr=sample_filter)
    rows = resp.get("data", [])
    meta = resp.get("meta", {})
    labels = meta.get("labels", {}) or {}
    data_types = meta.get("dataTypes", {}) or {}
    if rows:
        fields = list(rows[0].keys())
    else:
        fields = list(labels.keys()) if labels else []
    return {
        "key": key,
        "fields": fields,
        "labels": labels,
        "dataTypes": data_types,
    }


def get_endpoint(
    key: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
    use_date_filters: bool = True,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    """
    Generic fetcher for any registered endpoint.
    - filter_expr: Raw API filter (field:op:value). Combined with date filters unless use_date_filters=False.
    - page_number: If set, fetch only that page (1-based). Ignores max_pages.
    - use_date_filters: If False, from_date/to_date are ignored; use filter_expr for full control.
    """
    info = ENDPOINT_REGISTRY.get(key)
    if not info:
        raise ValueError(f"Unknown endpoint key: {key}. Available: {list(ENDPOINT_REGISTRY.keys())}")
    endpoint = info["endpoint"]
    filters: list[str] = []
    if filter_expr:
        filters.append(filter_expr)
    if use_date_filters:
        date_field = info.get("date_field")
        if date_field and from_date:
            filters.append(f"{date_field}:gte:{from_date}")
        if date_field and to_date:
            filters.append(f"{date_field}:lte:{to_date}")
    combined_filter = ",".join(filters) if filters else None
    default_sort = f"-{info.get('date_field', 'record_date')}" if info.get("date_field") and not sort else sort

    if page_number is not None:
        resp = _request(endpoint, fields=fields, filter_expr=combined_filter, sort=default_sort, page_number=page_number, page_size=page_size)
        return resp.get("data", [])

    def _progress(n: int, p: int, total: int) -> None:
        print(f"  Fetched {n} rows (page {p}/{total})...", flush=True)

    return _fetch_all_pages(
        endpoint,
        fields=fields,
        filter_expr=combined_filter,
        sort=default_sort,
        page_size=page_size,
        max_pages=max_pages,
        progress_callback=_progress if show_progress else None,
    )


def query(
    key: str,
    *,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_number: Optional[int] = None,
    page_size: int = 100,
    max_rows: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    use_date_filters: bool = True,
) -> dict[str, Any]:
    """
    Maximum-flexibility query. Returns dict with 'data' and optionally 'meta'.
    - page_number: Fetch single page (1-based).
    - max_rows: Cap total rows when paginating (stops after enough rows).
    - All filter/sort/field params passed through to API.
    """
    info = ENDPOINT_REGISTRY.get(key)
    if not info:
        raise ValueError(f"Unknown endpoint key: {key}")
    filters: list[str] = []
    if filter_expr:
        filters.append(filter_expr)
    if use_date_filters and info.get("date_field"):
        df = info["date_field"]
        if from_date:
            filters.append(f"{df}:gte:{from_date}")
        if to_date:
            filters.append(f"{df}:lte:{to_date}")
    comb = ",".join(filters) if filters else None
    default_sort = f"-{info.get('date_field', 'record_date')}" if info.get("date_field") and not sort else sort

    if page_number is not None:
        resp = _request(info["endpoint"], fields=fields, filter_expr=comb, sort=default_sort or "-record_date", page_number=page_number, page_size=page_size)
        return {"data": resp.get("data", []), "meta": resp.get("meta", {})}

    all_rows: list[dict[str, Any]] = []
    page = 1
    last_resp: dict[str, Any] = {}
    while True:
        resp = _request(info["endpoint"], fields=fields, filter_expr=comb, sort=default_sort or "-record_date", page_number=page, page_size=page_size)
        last_resp = resp
        rows = resp.get("data", [])
        all_rows.extend(rows)
        total_pages = resp.get("meta", {}).get("total-pages", 1)
        if max_rows and len(all_rows) >= max_rows:
            all_rows = all_rows[:max_rows]
            break
        if page >= total_pages or not rows:
            break
        page += 1
    return {"data": all_rows, "meta": last_resp.get("meta", {})}


def get_cusips(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """CUSIPs from upcoming auctions. Pass filter_expr for arbitrary API filters."""
    endpoint = _get_endpoint_path("upcoming_auctions")
    if not endpoint:
        raise ValueError("upcoming_auctions endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    flds = fields or ["cusip", "security_type", "security_term", "auction_date", "issue_date", "offering_amt", "reopening"]
    return _fetch_all_pages(endpoint, fields=flds, filter_expr=fe, sort=sort, page_size=page_size, max_pages=max_pages)


def get_unique_cusips(*, security_type: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list[str]:
    rows = get_cusips(security_type=security_type, from_date=from_date, to_date=to_date)
    return sorted(set(r.get("cusip") for r in rows if r.get("cusip")))


def get_upcoming_auctions(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Upcoming auctions. Pass filter_expr for arbitrary filters (e.g. auction_date:gte:2024-01-01)."""
    endpoint = _get_endpoint_path("upcoming_auctions")
    if not endpoint:
        raise ValueError("upcoming_auctions endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"auction_date:gte:{from_date}")
    if to_date:
        filters.append(f"auction_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort, page_size=page_size, max_pages=max_pages)


def get_record_setting_auctions(
    *,
    security_type: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Record-setting auctions. Pass filter_expr for additional filters."""
    endpoint = _get_endpoint_path("record_setting_auction")
    if not endpoint:
        raise ValueError("record_setting_auction endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort, page_size=page_size, max_pages=max_pages)


def get_debt_to_penny(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Debt to the Penny. Pass filter_expr for arbitrary filters, fields to select columns."""
    return get_endpoint(
        "debt_to_penny",
        from_date=from_date,
        to_date=to_date,
        filter_expr=filter_expr,
        fields=fields,
        sort=sort or "-record_date",
        page_size=page_size,
        max_pages=max_pages,
        page_number=page_number,
    )


def get_avg_interest_rates(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Average interest rates. Pass filter_expr for arbitrary filters."""
    endpoint = _get_endpoint_path("avg_interest_rates")
    if not endpoint:
        raise ValueError("avg_interest_rates endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages)


def get_rates_of_exchange(
    *,
    country_currency: Optional[list[str]] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Exchange rates. Pass filter_expr for arbitrary filters (e.g. country_currency_desc:in:(...))."""
    endpoint = _get_endpoint_path("rates_of_exchange")
    if not endpoint:
        raise ValueError("rates_of_exchange endpoint not in registry")
    filters = []
    if country_currency:
        filters.append(f"country_currency_desc:in:({','.join(country_currency)})")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages)


def get_revenue_collections(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Revenue collections. Pass filter_expr (e.g. tax_category_id:eq:3) or fields for specific columns."""
    return get_endpoint(
        "revenue_collections",
        from_date=from_date,
        to_date=to_date,
        filter_expr=filter_expr,
        fields=fields,
        sort=sort or "-record_date",
        page_size=page_size,
        max_pages=max_pages,
        page_number=page_number,
    )


def get_mts_table(
    table: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch MTS table. table: 1-9, 6a, 6b, 6c, 6d, 6e. filter_expr e.g. line_code_nbr:eq:120 for specific line."""
    key = f"mts_table_{table}"
    if key not in ENDPOINT_REGISTRY:
        raise ValueError(f"Unknown MTS table: {table}. Valid: 1-9, 6a, 6b, 6c, 6d, 6e")
    return get_endpoint(key, from_date=from_date, to_date=to_date, filter_expr=filter_expr, fields=fields, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages, page_number=page_number)


def get_dts_table(
    table: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch DTS table. table: 1-6, 3a, 3b, 3c. filter_expr for account_type, etc."""
    key = f"dts_table_{table}"
    if key not in ENDPOINT_REGISTRY:
        raise ValueError(f"Unknown DTS table: {table}. Valid: 1-6, 3a, 3b, 3c")
    return get_endpoint(key, from_date=from_date, to_date=to_date, filter_expr=filter_expr, fields=fields, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages, page_number=page_number)


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2))


def _print_table(rows: list[dict], limit: int = 20) -> None:
    if not rows:
        print("(no rows)")
        return
    keys = list(rows[0].keys())
    print(" | ".join(keys))
    print("-" * 60)
    for r in rows[:limit]:
        print(" | ".join(str(r.get(k, ""))[:20] for k in keys))
    if len(rows) > limit:
        print(f"... and {len(rows) - limit} more rows")


def _list_endpoints_by_category(category: str) -> list[dict]:
    return [v for v in ENDPOINT_REGISTRY.values() if v["category"] == category]


def _menu_cusips() -> None:
    print("\n--- CUSIPs ---")
    print("1. List unique CUSIPs (all)")
    print("2. List unique CUSIPs (filter by security type)")
    print("3. Full CUSIP records (with auction dates)")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        cusips = get_unique_cusips()
        print(f"Unique CUSIPs: {len(cusips)}")
        _print_table([{"cusip": c} for c in cusips[:50]])
    elif choice == "2":
        st = input("Security type (Bill/Note/Bond/FRN/TIPS): ").strip() or None
        cusips = get_unique_cusips(security_type=st)
        print(f"Unique CUSIPs: {len(cusips)}")
        _print_table([{"cusip": c} for c in cusips[:50]])
    elif choice == "3":
        st = input("Security type (optional): ").strip() or None
        rows = get_cusips(security_type=st, max_pages=5, page_size=100)
        print(f"Rows: {len(rows)}")
        _print_table(rows)


def _menu_auctions() -> None:
    print("\n--- Auction Schedules ---")
    print("1. Upcoming auctions (full)")
    print("2. Upcoming auctions (filter by security type)")
    print("3. Record-setting auctions")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        rows = get_upcoming_auctions(max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "2":
        st = input("Security type (Bill/Note/Bond/FRN/TIPS): ").strip() or None
        rows = get_upcoming_auctions(security_type=st, max_pages=5)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "3":
        st = input("Security type (optional): ").strip() or None
        rows = get_record_setting_auctions(security_type=st)
        print(f"Rows: {len(rows)}")
        _print_table(rows)


def _menu_debt() -> None:
    print("\n--- Debt ---")
    print("1. Debt to the Penny (recent)")
    print("2. Debt to the Penny (date range)")
    print("3. Historical Debt Outstanding")
    print("4. Schedules of Federal Debt")
    print("5. MSPD (Marketable Securities)")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        rows = get_debt_to_penny(max_pages=2)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "2":
        fd = input("From date (YYYY-MM-DD): ").strip() or None
        td = input("To date (YYYY-MM-DD): ").strip() or None
        rows = get_debt_to_penny(from_date=fd, to_date=td, max_pages=10)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "3":
        rows = get_endpoint("debt_outstanding", max_pages=5)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "4":
        rows = get_endpoint("schedules_fed_debt", max_pages=5)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "5":
        rows = get_endpoint("mspd_table_3_market", max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)


def _menu_accounting() -> None:
    print("\n--- Accounting (MTS / DTS) ---")
    print("1. MTS Table 1 (Receipts, Outlays, Deficit)")
    print("2. MTS Table 9 (Receipts by Source, Outlays by Function)")
    print("3. DTS Table 1 (Operating Cash Balance)")
    print("4. Query any MTS/DTS table by key")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        rows = get_mts_table("1", max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "2":
        rows = get_mts_table("9", max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "3":
        rows = get_dts_table("1", max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "4":
        key = input("Table key (e.g. mts_table_1, dts_table_2): ").strip()
        if key in ENDPOINT_REGISTRY:
            rows = get_endpoint(key, max_pages=3)
            print(f"Rows: {len(rows)}")
            _print_table(rows)
        else:
            print(f"Unknown key. Examples: {[k for k in ENDPOINT_REGISTRY if k.startswith('mts_') or k.startswith('dts_')][:10]}")


def _menu_interest_rates() -> None:
    print("\n--- Interest Rates ---")
    print("1. Average interest rates (recent)")
    print("2. Rates of exchange")
    print("3. Interest expense on public debt")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        st = input("Security type (optional): ").strip() or None
        rows = get_avg_interest_rates(security_type=st, max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "2":
        cc = input("Country-currency (comma-separated, e.g. Canada-Dollar,Mexico-Peso): ").strip()
        currencies = [x.strip() for x in cc.split(",")] if cc else None
        rows = get_rates_of_exchange(country_currency=currencies, max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "3":
        rows = get_endpoint("interest_expense", max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)


def _menu_revenue() -> None:
    print("\n--- Revenue ---")
    print("1. U.S. Government Revenue Collections (recent)")
    print("2. Revenue Collections (date range)")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        rows = get_revenue_collections(max_pages=3)
        print(f"Rows: {len(rows)}")
        _print_table(rows)
    elif choice == "2":
        fd = input("From date (YYYY-MM-DD): ").strip() or None
        td = input("To date (YYYY-MM-DD): ").strip() or None
        rows = get_revenue_collections(from_date=fd, to_date=td, max_pages=10)
        print(f"Rows: {len(rows)}")
        _print_table(rows)


def _menu_endpoints() -> None:
    print("\n--- Endpoint Registry ---")
    print("1. List all by category")
    print("2. Search endpoints by keyword")
    print("3. Show sample query patterns")
    print("4. Query any endpoint by key")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        for cat_id, desc in CATEGORIES.items():
            eps = _list_endpoints_by_category(cat_id)
            if not eps:
                continue
            print(f"\n{cat_id}: {desc}")
            for e in eps:
                print(f"  {e['endpoint']} -> {e['table_name']}")
    elif choice == "2":
        q = input("Search term: ").strip()
        if q:
            for r in search_endpoints(q):
                print(f"  {r['key']}: {r['table_name']} [{r['category']}]")
    elif choice == "3":
        for i, e in enumerate(get_examples(), 1):
            print(f"{i}. {e['desc']}")
            print(f"   key={e['key']} filter={e.get('filter','')} fields={e.get('fields',[])}")
    elif choice == "4":
        keys = sorted(ENDPOINT_REGISTRY.keys())
        print(f"Available keys ({len(keys)}): {', '.join(keys[:20])}...")
        key = input("Endpoint key: ").strip()
        info = ENDPOINT_REGISTRY.get(key)
        if not info:
            print(f"Unknown key.")
            return
        from_d = input("From date (optional, YYYY-MM-DD): ").strip() or None
        to_d = input("To date (optional): ").strip() or None
        try:
            rows = get_endpoint(key, from_date=from_d, to_date=to_d, max_pages=3)
            print(f"Rows: {len(rows)}")
            _print_table(rows)
        except FiscalDataError as err:
            print(f"Error: {err}")


def _interactive_main() -> None:
    while True:
        print("\n=== Fiscal Data API ===")
        print("1. CUSIPs")
        print("2. Auction schedules")
        print("3. Debt")
        print("4. Accounting (MTS / DTS)")
        print("5. Interest rates / exchange rates")
        print("6. Revenue")
        print("7. Endpoint registry / query any endpoint")
        print("0. Exit")
        choice = input("Choice: ").strip()
        if choice == "0":
            break
        if choice == "1":
            _menu_cusips()
        elif choice == "2":
            _menu_auctions()
        elif choice == "3":
            _menu_debt()
        elif choice == "4":
            _menu_accounting()
        elif choice == "5":
            _menu_interest_rates()
        elif choice == "6":
            _menu_revenue()
        elif choice == "7":
            _menu_endpoints()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fiscal Data API - full interaction with 80+ Treasury endpoints",
        epilog="Run without args for interactive menu. Use 'get <key>' to query any endpoint.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    p_cusips = subparsers.add_parser("cusips", help="Fetch CUSIPs from upcoming auctions")
    p_cusips.add_argument("--security-type", "-s", help="Filter by security type")
    p_cusips.add_argument("--from-date", help="Filter from date (YYYY-MM-DD)")
    p_cusips.add_argument("--to-date", help="Filter to date (YYYY-MM-DD)")
    p_cusips.add_argument("--filter", "-f", help="Raw filter (field:op:value)")
    p_cusips.add_argument("--fields", help="Comma-separated fields")
    p_cusips.add_argument("--unique", action="store_true", help="Output unique CUSIPs only")
    p_cusips.add_argument("--json", action="store_true", help="Output JSON")
    p_cusips.add_argument("--limit", type=int, default=100, help="Max rows")

    p_auctions = subparsers.add_parser("auctions", help="Fetch auction schedules")
    p_auctions.add_argument("--security-type", "-s", help="Filter by security type")
    p_auctions.add_argument("--from-date", help="Auction date from (YYYY-MM-DD)")
    p_auctions.add_argument("--to-date", help="Auction date to (YYYY-MM-DD)")
    p_auctions.add_argument("--filter", "-f", help="Raw filter (field:op:value)")
    p_auctions.add_argument("--record-setting", action="store_true", help="Record-setting auctions")
    p_auctions.add_argument("--json", action="store_true", help="Output JSON")
    p_auctions.add_argument("--limit", type=int, default=100, help="Max rows")

    p_debt = subparsers.add_parser("debt", help="Debt to the Penny")
    p_debt.add_argument("--from-date", help="From date (YYYY-MM-DD)")
    p_debt.add_argument("--to-date", help="To date (YYYY-MM-DD)")
    p_debt.add_argument("--filter", "-f", help="Raw filter")
    p_debt.add_argument("--fields", help="Comma-separated fields")
    p_debt.add_argument("--json", action="store_true", help="Output JSON")
    p_debt.add_argument("--limit", type=int, default=100, help="Max rows")

    p_ir = subparsers.add_parser("interest-rates", help="Average interest rates")
    p_ir.add_argument("--security-type", "-s", help="Filter by security type")
    p_ir.add_argument("--from-date", help="From date")
    p_ir.add_argument("--to-date", help="To date")
    p_ir.add_argument("--filter", "-f", help="Raw filter")
    p_ir.add_argument("--fields", help="Comma-separated fields")
    p_ir.add_argument("--json", action="store_true", help="Output JSON")
    p_ir.add_argument("--limit", type=int, default=100, help="Max rows")

    p_ex = subparsers.add_parser("exchange", help="Rates of exchange")
    p_ex.add_argument("--currencies", "-c", help="Comma-separated country-currency")
    p_ex.add_argument("--from-date", help="From date")
    p_ex.add_argument("--to-date", help="To date")
    p_ex.add_argument("--filter", "-f", help="Raw filter")
    p_ex.add_argument("--fields", help="Comma-separated fields")
    p_ex.add_argument("--json", action="store_true", help="Output JSON")
    p_ex.add_argument("--limit", type=int, default=100, help="Max rows")

    p_revenue = subparsers.add_parser("revenue", help="U.S. Government Revenue Collections")
    p_revenue.add_argument("--from-date", help="From date (YYYY-MM-DD)")
    p_revenue.add_argument("--to-date", help="To date (YYYY-MM-DD)")
    p_revenue.add_argument("--filter", "-f", help="Raw filter (e.g. tax_category_id:eq:3)")
    p_revenue.add_argument("--fields", help="Comma-separated fields")
    p_revenue.add_argument("--json", action="store_true", help="Output JSON")
    p_revenue.add_argument("--limit", type=int, default=100, help="Max rows")

    p_get = subparsers.add_parser("get", help="Query any endpoint by key (universal access)")
    p_get.add_argument("key", help="Endpoint key from registry (e.g. debt_to_penny, mts_table_1)")
    p_get.add_argument("--from-date", help="From date (YYYY-MM-DD)")
    p_get.add_argument("--to-date", help="To date (YYYY-MM-DD)")
    p_get.add_argument("--filter", "-f", help="Filter (field:op:value, multi with comma)")
    p_get.add_argument("--sort", help="Sort (e.g. -record_date)")
    p_get.add_argument("--fields", help="Comma-separated fields (slice columns)")
    p_get.add_argument("--limit", type=int, default=100, help="Max rows")
    p_get.add_argument("--page-number", "-p", type=int, help="Fetch specific page only (1-based)")
    p_get.add_argument("--page-size", type=int, default=100, help="Rows per page")
    p_get.add_argument("--no-date-filters", action="store_true", help="Ignore from/to-date; use --filter for full control")
    p_get.add_argument("--all", action="store_true", help="Fetch all pages")
    p_get.add_argument("--progress", action="store_true", help="Show progress for long fetches")
    p_get.add_argument("--json", action="store_true", help="Output JSON")

    p_fields = subparsers.add_parser("fields", help="Discover field names for an endpoint")
    p_fields.add_argument("key", help="Endpoint key")
    p_fields.add_argument("--filter", help="Optional filter to apply when sampling")
    p_fields.add_argument("--schema", action="store_true", help="Full schema (labels, dataTypes)")
    p_fields.add_argument("--json", action="store_true", help="Output JSON")

    p_manifest = subparsers.add_parser("manifest", help="Full manifest (categories, endpoints, filter format)")
    p_manifest.add_argument("--json", action="store_true", help="Output JSON")

    p_search = subparsers.add_parser("search", help="Search endpoints by keyword")
    p_search.add_argument("query", help="Search term (matches key or table name)")
    p_search.add_argument("--json", action="store_true", help="Output JSON")

    p_list = subparsers.add_parser("list", help="List endpoint keys by category")
    p_list.add_argument("category", nargs="?", help="Category filter")
    p_list.add_argument("--json", action="store_true", help="Output JSON")

    p_examples = subparsers.add_parser("examples", help="Sample query patterns")
    p_examples.add_argument("--json", action="store_true", help="Output JSON")

    p_ep = subparsers.add_parser("endpoints", help="Endpoint registry - list or get")
    p_ep.add_argument("action", choices=["list", "get"], nargs="?", default="list", help="list or get")
    p_ep.add_argument("key", nargs="?", help="Endpoint key for 'get'")
    p_ep.add_argument("--from-date", help="From date for get")
    p_ep.add_argument("--to-date", help="To date for get")
    p_ep.add_argument("--page-size", type=int, default=10, help="Page size for get")
    p_ep.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if not args.command:
        _interactive_main()
        return

    if args.command == "cusips":
        flds = [x.strip() for x in args.fields.split(",")] if getattr(args, "fields", None) else None
        if args.unique:
            data = [{"cusip": c} for c in get_unique_cusips(security_type=args.security_type, from_date=args.from_date, to_date=args.to_date)]
        else:
            data = get_cusips(security_type=args.security_type, from_date=args.from_date, to_date=args.to_date, filter_expr=getattr(args, "filter", None), fields=flds, max_pages=max(1, args.limit // 100))
        _print_json(data) if args.json else _print_table(data, limit=args.limit)

    elif args.command == "auctions":
        flds = [x.strip() for x in args.fields.split(",")] if getattr(args, "fields", None) else None
        if args.record_setting:
            data = get_record_setting_auctions(security_type=args.security_type, filter_expr=getattr(args, "filter", None), fields=flds, max_pages=max(1, args.limit // 100))
        else:
            data = get_upcoming_auctions(security_type=args.security_type, from_date=args.from_date, to_date=args.to_date, filter_expr=getattr(args, "filter", None), fields=flds, max_pages=max(1, args.limit // 100))
        _print_json(data) if args.json else _print_table(data, limit=args.limit)

    elif args.command == "debt":
        flds = [x.strip() for x in args.fields.split(",")] if getattr(args, "fields", None) else None
        data = get_debt_to_penny(from_date=args.from_date, to_date=args.to_date, filter_expr=getattr(args, "filter", None), fields=flds, max_pages=max(1, args.limit // 100))
        _print_json(data) if args.json else _print_table(data, limit=args.limit)

    elif args.command == "interest-rates":
        flds = [x.strip() for x in args.fields.split(",")] if getattr(args, "fields", None) else None
        data = get_avg_interest_rates(security_type=args.security_type, from_date=args.from_date, to_date=args.to_date, filter_expr=getattr(args, "filter", None), fields=flds, max_pages=max(1, args.limit // 100))
        _print_json(data) if args.json else _print_table(data, limit=args.limit)

    elif args.command == "exchange":
        currencies = [x.strip() for x in args.currencies.split(",")] if args.currencies else None
        flds = [x.strip() for x in args.fields.split(",")] if getattr(args, "fields", None) else None
        data = get_rates_of_exchange(country_currency=currencies, from_date=args.from_date, to_date=args.to_date, filter_expr=getattr(args, "filter", None), fields=flds, max_pages=max(1, args.limit // 100))
        _print_json(data) if args.json else _print_table(data, limit=args.limit)

    elif args.command == "revenue":
        flds = [x.strip() for x in args.fields.split(",")] if getattr(args, "fields", None) else None
        data = get_revenue_collections(from_date=args.from_date, to_date=args.to_date, filter_expr=getattr(args, "filter", None), fields=flds, max_pages=max(1, args.limit // 100))
        _print_json(data) if args.json else _print_table(data, limit=args.limit)

    elif args.command == "get":
        info = ENDPOINT_REGISTRY.get(args.key)
        if not info:
            print(f"Unknown key: {args.key}")
            print("Use 'endpoints list' to see all keys.")
            sys.exit(1)
        page_num = getattr(args, "page_number", None)
        max_p = None if args.all else (1 if not page_num else None)
        page_sz = getattr(args, "page_size", 100) if not page_num else getattr(args, "page_size", 100)
        if not args.all and not page_num:
            page_sz = min(1000, max(1, args.limit))
        fields = [f.strip() for f in args.fields.split(",")] if args.fields else None
        data = get_endpoint(
            args.key,
            from_date=args.from_date,
            to_date=args.to_date,
            filter_expr=args.filter,
            fields=fields,
            sort=args.sort,
            page_size=page_sz,
            max_pages=max_p,
            page_number=page_num,
            use_date_filters=not getattr(args, "no_date_filters", False),
            show_progress=args.progress,
        )
        _print_json(data) if args.json else _print_table(data, limit=args.limit)

    elif args.command == "fields":
        try:
            if getattr(args, "schema", False):
                schema = discover_schema(args.key, sample_filter=args.filter)
                _print_json(schema) if args.json else _print_json(schema)
            else:
                flds = discover_fields(args.key, sample_filter=args.filter)
                if args.json:
                    _print_json(flds)
                else:
                    print(f"Fields for {args.key}: {', '.join(flds)}")
        except (ValueError, FiscalDataError) as e:
            print(str(e))
            sys.exit(1)

    elif args.command == "manifest":
        m = get_manifest()
        _print_json(m)

    elif args.command == "search":
        results = search_endpoints(args.query)
        if args.json:
            _print_json(results)
        else:
            for r in results:
                print(f"  {r['key']}: {r['table_name']} [{r['category']}]")

    elif args.command == "list":
        try:
            keys = list_keys(getattr(args, "category", None))
            if args.json:
                _print_json(keys)
            else:
                for k in keys:
                    print(k)
        except ValueError as e:
            print(str(e))
            sys.exit(1)

    elif args.command == "examples":
        ex = get_examples()
        if args.json:
            _print_json(ex)
        else:
            for i, e in enumerate(ex, 1):
                print(f"{i}. {e['desc']}")
                print(f"   key={e['key']} filter={e.get('filter','')} fields={e.get('fields',[])}")

    elif args.command == "endpoints":
        if args.action == "list" or not args.key:
            for cat_id, desc in CATEGORIES.items():
                eps = _list_endpoints_by_category(cat_id)
                if not eps:
                    continue
                print(f"\n{cat_id}: {desc}")
                for e in eps:
                    print(f"  {e['endpoint']} -> {e['table_name']}")
        elif args.action == "get":
            if not args.key:
                print("Error: endpoint key required for 'get'")
                sys.exit(1)
            info = ENDPOINT_REGISTRY.get(args.key)
            if not info:
                print(f"Unknown key: {args.key}")
                sys.exit(1)
            data = get_endpoint(args.key, from_date=args.from_date, to_date=args.to_date, max_pages=1, page_size=max(1, args.page_size))
            _print_json(data) if args.json else _print_table(data, limit=args.page_size)


if __name__ == "__main__":
    try:
        main()
    except FiscalDataError as e:
        print(f"FiscalDataError: {e}", file=sys.stderr)
        sys.exit(1)
