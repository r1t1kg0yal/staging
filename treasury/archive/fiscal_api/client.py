"""
Low-level Fiscal Data API client.

Handles HTTP requests, pagination, and response parsing.
"""

import urllib.request
import urllib.parse
import json
from typing import Any, Optional


BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


def _build_url(
    endpoint: str,
    *,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
    format: str = "json",
    page_number: int = 1,
    page_size: int = 100,
) -> str:
    """Build full API URL with query parameters."""
    params: dict[str, str] = {
        "format": format,
        "page[number]": str(page_number),
        "page[size]": str(page_size),
    }
    if fields:
        params["fields"] = ",".join(fields)
    if filter_expr:
        params["filter"] = filter_expr
    if sort:
        params["sort"] = sort

    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


def request(
    endpoint: str,
    *,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
    format: str = "json",
    page_number: int = 1,
    page_size: int = 100,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Execute a GET request to the Fiscal Data API.

    Returns the full response dict with keys: data, meta, links.
    """
    url = _build_url(
        endpoint,
        fields=fields,
        filter_expr=filter_expr,
        sort=sort,
        format=format,
        page_number=page_number,
        page_size=page_size,
    )
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def fetch_all_pages(
    endpoint: str,
    *,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    progress_callback: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """
    Fetch all pages of an endpoint, concatenating data rows.

    progress_callback(current_page, total_pages, rows_so_far) called every 5-6 sec.
    """
    all_data: list[dict[str, Any]] = []
    page = 1
    total_pages = 1
    last_progress = 0.0
    import time

    while page <= total_pages:
        resp = request(
            endpoint,
            fields=fields,
            filter_expr=filter_expr,
            sort=sort,
            page_number=page,
            page_size=page_size,
        )
        rows = resp.get("data", [])
        all_data.extend(rows)

        meta = resp.get("meta", {})
        total_pages = meta.get("total-pages", 1)

        now = time.time()
        if progress_callback and (now - last_progress >= 5):
            progress_callback(page, total_pages, len(all_data))
            last_progress = now

        if max_pages and page >= max_pages:
            break
        if page >= total_pages:
            break
        page += 1

    if progress_callback:
        progress_callback(page, total_pages, len(all_data))

    return all_data


class FiscalDataClient:
    """Client for the U.S. Treasury Fiscal Data API."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")

    def get(
        self,
        endpoint: str,
        *,
        fields: Optional[list[str]] = None,
        filter_expr: Optional[str] = None,
        sort: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Single-page request."""
        return request(
            endpoint,
            fields=fields,
            filter_expr=filter_expr,
            sort=sort,
            page_number=page_number,
            page_size=page_size,
        )

    def get_all(
        self,
        endpoint: str,
        *,
        fields: Optional[list[str]] = None,
        filter_expr: Optional[str] = None,
        sort: Optional[str] = None,
        page_size: int = 1000,
        max_pages: Optional[int] = None,
        progress_callback: Optional[Any] = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages."""
        return fetch_all_pages(
            endpoint,
            fields=fields,
            filter_expr=filter_expr,
            sort=sort,
            page_size=page_size,
            max_pages=max_pages,
            progress_callback=progress_callback,
        )
