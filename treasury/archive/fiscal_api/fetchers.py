"""
High-level fetchers for common Fiscal Data use cases.

Designed for LLM and script consumption: simple function calls return
structured data. Each fetcher documents its endpoint and parameters.
"""

from typing import Any, Optional

from .client import FiscalDataClient, request
from .endpoints import get_endpoint_path


def get_cusips(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Fetch unique CUSIPs from Treasury Securities Upcoming Auctions.

    CUSIPs are available in upcoming_auctions (announced auctions).
    Filter by security_type (optional), e.g. 'Bill', 'Note', 'Bond', 'FRN', 'TIPS'.
    Date filter uses record_date (publication date).
    """
    endpoint = get_endpoint_path("upcoming_auctions")
    if not endpoint:
        raise ValueError("upcoming_auctions endpoint not in registry")

    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    filter_expr = ",".join(filters) if filters else None

    client = FiscalDataClient()
    return client.get_all(
        endpoint,
        fields=["cusip", "security_type", "security_term", "auction_date", "issue_date", "offering_amt", "reopening"],
        filter_expr=filter_expr,
        sort=None,  # some endpoints reject sort; use default ordering
        page_size=page_size,
        max_pages=max_pages,
    )


def get_unique_cusips(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[str]:
    """Return unique CUSIP strings (sorted)."""
    rows = get_cusips(security_type=security_type, from_date=from_date, to_date=to_date)
    cusips = sorted(set(r.get("cusip") for r in rows if r.get("cusip")))
    return cusips


def get_upcoming_auctions(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Fetch auction schedule (announcements) from Treasury Securities Upcoming Auctions.

    Returns: record_date, security_type, security_term, reopening, cusip,
    offering_amt, announcemt_date, auction_date, issue_date.
    """
    endpoint = get_endpoint_path("upcoming_auctions")
    if not endpoint:
        raise ValueError("upcoming_auctions endpoint not in registry")

    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"auction_date:gte:{from_date}")
    if to_date:
        filters.append(f"auction_date:lte:{to_date}")
    filter_expr = ",".join(filters) if filters else None

    client = FiscalDataClient()
    return client.get_all(
        endpoint,
        filter_expr=filter_expr,
        sort=None,
        page_size=page_size,
        max_pages=max_pages,
    )


def get_record_setting_auctions(
    *,
    security_type: Optional[str] = None,
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """
    Fetch record-setting auction data (highs/lows by security type).

    Fields: security_type, high_rate_pct, low_rate_pct, high_offer_amt,
    high_bid_cover_ratio, first_auc_date_*.
    """
    endpoint = get_endpoint_path("record_setting_auction")
    if not endpoint:
        raise ValueError("record_setting_auction endpoint not in registry")

    filter_expr = f"security_type:eq:{security_type}" if security_type else None
    client = FiscalDataClient()
    return client.get_all(endpoint, filter_expr=filter_expr, page_size=page_size)


def get_debt_to_penny(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Fetch Debt to the Penny (total public debt outstanding by date).
    """
    endpoint = get_endpoint_path("debt_to_penny")
    if not endpoint:
        raise ValueError("debt_to_penny endpoint not in registry")

    filters = []
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    filter_expr = ",".join(filters) if filters else None

    client = FiscalDataClient()
    return client.get_all(
        endpoint,
        filter_expr=filter_expr,
        sort="-record_date",
        page_size=page_size,
        max_pages=max_pages,
    )


def get_avg_interest_rates(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Fetch average interest rates on U.S. Treasury securities.
    """
    endpoint = get_endpoint_path("avg_interest_rates")
    if not endpoint:
        raise ValueError("avg_interest_rates endpoint not in registry")

    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    filter_expr = ",".join(filters) if filters else None

    client = FiscalDataClient()
    return client.get_all(
        endpoint,
        filter_expr=filter_expr,
        sort="-record_date",
        page_size=page_size,
        max_pages=max_pages,
    )


def get_rates_of_exchange(
    *,
    country_currency: Optional[list[str]] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """
    Fetch Treasury reporting rates of exchange.

    country_currency: e.g. ['Canada-Dollar', 'Mexico-Peso'] for filter.
    """
    endpoint = get_endpoint_path("rates_of_exchange")
    if not endpoint:
        raise ValueError("rates_of_exchange endpoint not in registry")

    filters = []
    if country_currency:
        vals = ",".join(country_currency)
        filters.append(f"country_currency_desc:in:({vals})")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    filter_expr = ",".join(filters) if filters else None

    client = FiscalDataClient()
    return client.get_all(
        endpoint,
        filter_expr=filter_expr,
        sort="-record_date",
        page_size=page_size,
        max_pages=max_pages,
    )


def get_arbitrary_endpoint(
    endpoint_key: str,
    *,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
    page_number: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """
    Fetch any registered endpoint by key.

    Use for one-off or exploratory queries. Returns full API response.
    """
    path = get_endpoint_path(endpoint_key)
    if not path:
        raise ValueError(f"Unknown endpoint key: {endpoint_key}")
    return request(
        path,
        fields=fields,
        filter_expr=filter_expr,
        sort=sort,
        page_number=page_number,
        page_size=page_size,
    )
