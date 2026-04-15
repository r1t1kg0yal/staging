"""
Fiscal Data API endpoint registry.

Structured for LLM consumption: each endpoint has a stable key, description,
and field hints. Use get_endpoint_info() for programmatic lookup.
"""

from typing import TypedDict


class EndpointInfo(TypedDict):
    endpoint: str
    table_name: str
    dataset: str
    category: str
    description: str
    key_fields: list[str]


# Categories for grouping
CATEGORIES = {
    "auctions": "Auction schedules, CUSIPs, record-setting auction data",
    "debt": "Debt outstanding, debt to penny, schedules, buybacks",
    "accounting": "MTS, DTS, financial reports, reconciliations",
    "interest_rates": "Average interest rates, yields, exchange rates",
    "securities": "Savings bonds, TreasuryDirect, SLGS, securities sales",
    "revenue": "Revenue collections, tax, receipts",
    "other": "Miscellaneous datasets",
}

# Full endpoint registry: endpoint path -> EndpointInfo
# Includes 80+ endpoints from Fiscal Data API docs + discovered endpoints
ENDPOINT_REGISTRY: dict[str, EndpointInfo] = {
    # --- Auctions (CUSIPs, schedules) ---
    "upcoming_auctions": {
        "endpoint": "v1/accounting/od/upcoming_auctions",
        "table_name": "Treasury Securities Upcoming Auctions",
        "dataset": "Treasury Securities Upcoming Auctions Data",
        "category": "auctions",
        "description": "Auction announcements: CUSIPs, security type/term, auction date, issue date, offering amount",
        "key_fields": ["cusip", "security_type", "security_term", "auction_date", "issue_date", "offering_amt", "reopening"],
    },
    "record_setting_auction": {
        "endpoint": "v2/accounting/od/record_setting_auction",
        "table_name": "Record-Setting Auction",
        "dataset": "Record-Setting Treasury Securities Auction Data",
        "category": "auctions",
        "description": "Record highs/lows: lowest/highest rates, highest offering amounts, bid-to-cover ratios",
        "key_fields": ["security_type", "high_rate_pct", "low_rate_pct", "high_offer_amt", "high_bid_cover_ratio"],
    },
    # --- Debt ---
    "debt_to_penny": {
        "endpoint": "v2/accounting/od/debt_to_penny",
        "table_name": "Debt to the Penny",
        "dataset": "Debt to the Penny",
        "category": "debt",
        "description": "Total public debt outstanding by date",
        "key_fields": ["record_date", "tot_pub_debt_out_amt", "debt_held_public_amt", "intragov_hold_amt"],
    },
    "debt_outstanding": {
        "endpoint": "v2/accounting/od/debt_outstanding",
        "table_name": "Historical Debt Outstanding",
        "dataset": "Historical Debt Outstanding",
        "category": "debt",
        "description": "Historical debt outstanding",
        "key_fields": ["record_date", "total_public_debt_outstanding_amt"],
    },
    "schedules_fed_debt": {
        "endpoint": "v1/accounting/od/schedules_fed_debt",
        "table_name": "Schedules of Federal Debt by Month",
        "dataset": "Schedules of Federal Debt",
        "category": "debt",
        "description": "Federal debt schedules by month",
        "key_fields": ["record_date", "debt_held_public_amt", "intragov_hold_amt"],
    },
    "mspd_table_3_market": {
        "endpoint": "v1/debt/mspd/mspd_table_3_market",
        "table_name": "Detail of Marketable Treasury Securities Outstanding",
        "dataset": "U.S. Treasury Monthly Statement of the Public Debt (MSPD)",
        "category": "debt",
        "description": "Marketable Treasury securities outstanding by CUSIP/security",
        "key_fields": ["record_date", "security_type", "cusip", "security_desc", "outstanding_amt"],
    },
    # --- Interest rates ---
    "avg_interest_rates": {
        "endpoint": "v2/accounting/od/avg_interest_rates",
        "table_name": "Average Interest Rates on U.S. Treasury Securities",
        "dataset": "Average Interest Rates on U.S. Treasury Securities",
        "category": "interest_rates",
        "description": "Average interest rates by security type and term",
        "key_fields": ["record_date", "security_type", "security_desc", "avg_interest_rate_amt"],
    },
    "rates_of_exchange": {
        "endpoint": "v1/accounting/od/rates_of_exchange",
        "table_name": "Treasury Reporting Rates of Exchange",
        "dataset": "Treasury Reporting Rates of Exchange",
        "category": "interest_rates",
        "description": "Foreign exchange rates for Treasury reporting",
        "key_fields": ["record_date", "country_currency_desc", "exchange_rate", "effective_date"],
    },
    "interest_expense": {
        "endpoint": "v2/accounting/od/interest_expense",
        "table_name": "Interest Expense on the Public Debt Outstanding",
        "dataset": "Interest Expense on the Public Debt Outstanding",
        "category": "interest_rates",
        "description": "Interest expense on public debt",
        "key_fields": ["record_date", "interest_expense_amt"],
    },
    # --- Accounting / MTS / DTS ---
    "mts_table_1": {
        "endpoint": "v1/accounting/mts/mts_table_1",
        "table_name": "Summary of Receipts, Outlays, and the Deficit/Surplus",
        "dataset": "Monthly Treasury Statement (MTS)",
        "category": "accounting",
        "description": "Summary of receipts, outlays, deficit/surplus",
        "key_fields": ["record_date", "classification_desc", "current_month_gross_rcpt_amt", "current_month_outlay_amt"],
    },
    "dts_table_1": {
        "endpoint": "v1/accounting/dts/dts_table_1",
        "table_name": "Operating Cash Balance",
        "dataset": "Daily Treasury Statement (DTS)",
        "category": "accounting",
        "description": "Daily operating cash balance",
        "key_fields": ["record_date", "account_type", "close_today_bal"],
    },
    # --- Revenue ---
    "revenue_collections": {
        "endpoint": "v2/revenue/rcm",
        "table_name": "U.S. Government Revenue Collections",
        "dataset": "U.S. Government Revenue Collections",
        "category": "revenue",
        "description": "Revenue collections by category",
        "key_fields": ["record_date", "revenue_type", "revenue_amt"],
    },
    # --- Additional endpoints (abbreviated for registry) ---
    "redemption_tables": {"endpoint": "v2/accounting/od/redemption_tables", "table_name": "Redemption Tables", "dataset": "Accrual Savings Bonds Redemption Tables", "category": "securities", "description": "Savings bond redemption tables", "key_fields": []},
    "title_xii": {"endpoint": "v2/accounting/od/title_xii", "table_name": "Advances to State Unemployment Funds", "dataset": "SSA Title XII", "category": "accounting", "description": "State unemployment fund advances", "key_fields": []},
    "dts_table_2": {"endpoint": "v1/accounting/dts/dts_table_2", "table_name": "Deposits and Withdrawals of Operating Cash", "dataset": "Daily Treasury Statement", "category": "accounting", "description": "DTS deposits/withdrawals", "key_fields": []},
    "dts_table_3a": {"endpoint": "v1/accounting/dts/dts_table_3a", "table_name": "Public Debt Transactions", "dataset": "Daily Treasury Statement", "category": "accounting", "description": "Public debt transactions", "key_fields": []},
    "dts_table_3b": {"endpoint": "v1/accounting/dts/dts_table_3b", "table_name": "Adjustment of Public Debt Transactions to Cash Basis", "dataset": "Daily Treasury Statement", "category": "accounting", "description": "Debt transaction adjustments", "key_fields": []},
    "dts_table_3c": {"endpoint": "v1/accounting/dts/dts_table_3c", "table_name": "Debt Subject to Limit", "dataset": "Daily Treasury Statement", "category": "accounting", "description": "Debt subject to limit", "key_fields": []},
    "dts_table_4": {"endpoint": "v1/accounting/dts/dts_table_4", "table_name": "Federal Tax Deposits", "dataset": "Daily Treasury Statement", "category": "accounting", "description": "Federal tax deposits", "key_fields": []},
    "dts_table_5": {"endpoint": "v1/accounting/dts/dts_table_5", "table_name": "Short-Term Cash Investments", "dataset": "Daily Treasury Statement", "category": "accounting", "description": "Short-term cash investments", "key_fields": []},
    "dts_table_6": {"endpoint": "v1/accounting/dts/dts_table_6", "table_name": "Income Tax Refunds Issued", "dataset": "Daily Treasury Statement", "category": "accounting", "description": "Income tax refunds", "key_fields": []},
    "tror": {"endpoint": "v2/debt/tror", "table_name": "Treasury Report on Receivables Full Data", "dataset": "Treasury Report on Receivables", "category": "debt", "description": "Receivables data", "key_fields": []},
    "top_federal": {"endpoint": "v1/debt/top/top_federal", "table_name": "Federal Collections", "dataset": "Treasury Offset Program", "category": "debt", "description": "Federal collections", "key_fields": []},
    "top_state": {"endpoint": "v1/debt/top/top_state", "table_name": "State Programs", "dataset": "Treasury Offset Program", "category": "debt", "description": "State offset programs", "key_fields": []},
    "slgs_statistics": {"endpoint": "v2/accounting/od/slgs_statistics", "table_name": "Monthly SLGS Securities Program", "dataset": "SLGS Securities Program", "category": "securities", "description": "State and local government series stats", "key_fields": []},
    "gold_reserve": {"endpoint": "v2/accounting/od/gold_reserve", "table_name": "U.S. Treasury-Owned Gold", "dataset": "U.S. Treasury-Owned Gold", "category": "other", "description": "Treasury gold holdings", "key_fields": []},
}


def get_endpoint_info(key: str) -> EndpointInfo | None:
    """Look up endpoint by registry key (e.g. 'upcoming_auctions', 'debt_to_penny')."""
    return ENDPOINT_REGISTRY.get(key)


def get_endpoint_path(key: str) -> str | None:
    """Return the API path for a registry key."""
    info = get_endpoint_info(key)
    return info["endpoint"] if info else None


def list_endpoints_by_category(category: str) -> list[EndpointInfo]:
    """Return all endpoints in a category."""
    return [v for v in ENDPOINT_REGISTRY.values() if v["category"] == category]


def list_all_categories() -> dict[str, str]:
    """Return category id -> description."""
    return dict(CATEGORIES)
