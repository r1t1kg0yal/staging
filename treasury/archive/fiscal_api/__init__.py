"""
U.S. Treasury Fiscal Data API integration.

Provides structured access to federal financial data: debt, revenue, spending,
interest rates, savings bonds, auction schedules, CUSIPs, and more.

Base URL: https://api.fiscaldata.treasury.gov/services/api/fiscal_service/
No authentication required.
"""

from .client import FiscalDataClient
from .endpoints import ENDPOINT_REGISTRY, get_endpoint_info
from .fetchers import (
    get_cusips,
    get_unique_cusips,
    get_upcoming_auctions,
    get_record_setting_auctions,
    get_debt_to_penny,
    get_avg_interest_rates,
    get_rates_of_exchange,
)

__all__ = [
    "FiscalDataClient",
    "ENDPOINT_REGISTRY",
    "get_endpoint_info",
    "get_cusips",
    "get_unique_cusips",
    "get_upcoming_auctions",
    "get_record_setting_auctions",
    "get_debt_to_penny",
    "get_avg_interest_rates",
    "get_rates_of_exchange",
]
