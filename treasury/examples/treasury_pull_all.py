#!/usr/bin/env python3
"""
Treasury Fiscal Data downloader and CSV/metadata writer.

Features:
- Define conceptual groups (each with 1+ Treasury Fiscal Data endpoints)
- For each endpoint:
  - Page through all results (resume-light via append mode optional)
  - Write a CSV with all returned fields (no aggregation by default)
  - Write a metadata JSON capturing labels, dataTypes, dataFormats, and run info
- Write a master catalog across processed endpoints

Operational:
- Open API (no key needed)
- Verbose CLI progress with periodic heartbeats every N seconds
- Global rate limiting between HTTP requests with exponential backoff on errors/429

CLI examples:
- List available groups and endpoints:
  ./treasury_pull_all.py --list-groups --list-endpoints

- Pull everything (all groups) with default settings:
  ./treasury_pull_all.py

- Pull specific groups with slower rate and only recent records:
  ./treasury_pull_all.py --groups dts --since 2024-01-01 --min-interval-sec 0.8

- Pull specific endpoints, limit pages and increase page size:
  ./treasury_pull_all.py --endpoints v1/accounting/dts/operating_cash_balance --page-size 1000 --max-pages 5
"""

import argparse
import csv
import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from time import monotonic
from typing import Dict, List, Tuple, Any, Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


# =====================
# Configuration
# =====================

BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_DATA_DIR = os.path.join(API_DIR, "data")
DEFAULT_META_DIR = os.path.join(API_DIR, "metadata")

# Global rate limiter
_LAST_REQUEST_TS = 0.0
_MIN_INTERVAL_SEC = 1.0
_HEARTBEAT_SEC = 5.0


# =====================
# Groups and endpoints (starter set)
# =====================

# These are commonly used datasets; expand as needed.
GROUPS: Dict[str, Dict[str, List[str]]] = {
    "dts": {
        "endpoints": [
            "v1/accounting/dts/operating_cash_balance",
            "v1/accounting/dts/deposits_withdrawals_operating_cash",
            "v1/accounting/dts/public_debt_transactions",
            "v1/accounting/dts/adjustment_public_debt_transactions_cash_basis",
            "v1/accounting/dts/debt_subject_to_limit",
            "v1/accounting/dts/inter_agency_tax_transfers",
        ]
    },
    "od": {
        "endpoints": [
            "v2/accounting/od/avg_interest_rates",
            "v1/accounting/od/rates_of_exchange",
            "v2/accounting/od/debt_to_penny",
        ]
    },
    "mts": {
        "endpoints": [
            "v1/accounting/mts/mts_table_1",
            "v1/accounting/mts/mts_table_2",
            "v1/accounting/mts/mts_table_3",
            "v1/accounting/mts/mts_table_9",
        ]
    },
}


# =====================
# Utilities
# =====================

def _ensure_dirs(*paths: str) -> None:
    for p in paths:
        if not p:
            continue
        os.makedirs(p, exist_ok=True)


def _rate_limit_sleep(min_interval: float = None) -> None:
    global _LAST_REQUEST_TS
    interval = _MIN_INTERVAL_SEC if min_interval is None else float(min_interval)
    now = monotonic()
    to_sleep = max(0.0, (interval - (now - _LAST_REQUEST_TS)))
    if to_sleep > 0:
        time.sleep(to_sleep)
    _LAST_REQUEST_TS = monotonic()


class Heartbeat:
    def __init__(self, label: str, interval: float) -> None:
        self._label = label
        self._interval = max(1.0, float(interval))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def __enter__(self):
        def _run():
            last = monotonic()
            while not self._stop.wait(0.2):
                now = monotonic()
                if now - last >= self._interval:
                    print(self._label)
                    last = now
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._thread:
            self._stop.set()
            self._thread.join(timeout=0.5)


def _safe_filename_from_endpoint(endpoint: str) -> str:
    # Example: v1/accounting/dts/operating_cash_balance -> dts_operating_cash_balance
    parts = [p for p in endpoint.strip("/").split("/") if p]
    if not parts:
        return "endpoint"
    # Prefer dataset and table name segments
    if len(parts) >= 4:
        return f"{parts[2]}_{parts[3]}"
    return "_".join(parts)


def _build_url(endpoint: str, fields: List[str], filters: Dict[str, str], sort: str, page_number: int, page_size: int, fmt: str = "json") -> str:
    params: Dict[str, Any] = {}
    if fields:
        params["fields"] = ",".join(fields)
    if filters:
        # &filter=field:prm:value,field:prm:value
        flist: List[str] = []
        for k, v in filters.items():
            flist.append(f"{k}")
        # Caller must pass already formatted "field:op:value" strings in values; we just join
        params["filter"] = ",".join(filters.values())
    if sort:
        params["sort"] = sort
    params["format"] = fmt
    params["page[number]"] = str(page_number)
    params["page[size]"] = str(page_size)
    qs = urlencode(params)
    return f"{BASE_URL}{endpoint}?{qs}"


def _http_get_json(url: str, max_retries: int = 5) -> Dict[str, Any]:
    for attempt in range(max_retries):
        try:
            _rate_limit_sleep()
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=60) as resp:
                data = resp.read()
                return json.loads(data)
        except (HTTPError, URLError) as e:
            code = getattr(e, "code", None)
            if code in (400, 404):
                print(f"  Error {code} for URL: {url}")
                return {"data": [], "meta": {"count": 0, "total-pages": 0}}
            # Backoff heavier on 429
            backoff = 5 if code == 429 else (2 ** attempt)
            if attempt == max_retries - 1:
                print(f"  Warning: request failed after {max_retries} attempts ({e}).")
                return {"data": [], "meta": {"count": 0, "total-pages": 0}}
            time.sleep(max(1, backoff))
    return {"data": [], "meta": {"count": 0, "total-pages": 0}}


def fetch_endpoint_all(endpoint: str, out_csv_path: str, meta_dir: str, page_size: int, max_pages: int, fields: List[str], filters: Dict[str, str], sort: str, heartbeat_sec: float, summary: bool) -> Dict[str, Any]:
    # Prepare temp file for atomic write
    _ensure_dirs(os.path.dirname(out_csv_path) or ".")
    tmp_csv = out_csv_path + ".tmp"
    total_rows = 0
    total_pages_seen = 0
    labels: Dict[str, str] = {}
    data_types: Dict[str, str] = {}
    data_formats: Dict[str, str] = {}
    header_written = False
    header_fields: List[str] = []

    with Heartbeat(label=f"    Still downloading {endpoint}...", interval=heartbeat_sec):
        with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            page = 1
            while True:
                if max_pages > 0 and page > max_pages:
                    break
                url = _build_url(endpoint=endpoint, fields=fields, filters=filters, sort=sort, page_number=page, page_size=page_size)
                if not summary:
                    print(f"    GET page {page}: {url}")
                payload = _http_get_json(url)
                rows: List[Dict[str, Any]] = payload.get("data") or []
                meta: Dict[str, Any] = payload.get("meta") or {}
                total_pages = int(str(meta.get("total-pages") or meta.get("total_pages") or 0) or 0)
                if not labels:
                    labels = meta.get("labels") or {}
                if not data_types:
                    data_types = meta.get("dataTypes") or {}
                if not data_formats:
                    data_formats = meta.get("dataFormats") or {}

                if rows:
                    # Determine header once from first row
                    if not header_written:
                        header_fields = list(rows[0].keys())
                        writer.writerow(header_fields)
                        header_written = True
                    for r in rows:
                        writer.writerow([r.get(k, "") for k in header_fields])
                    total_rows += len(rows)
                    total_pages_seen += 1
                    if not summary:
                        print(f"      Wrote {len(rows)} rows from page {page} (total so far: {total_rows})")
                else:
                    if not summary:
                        print(f"      No rows on page {page}.")

                if total_pages and page >= total_pages:
                    break
                # Stop if API indicates no more pages (defensive)
                if not rows and total_pages == 0:
                    break
                page += 1

    os.replace(tmp_csv, out_csv_path)
    print(f"    CSV written: {out_csv_path} (rows={total_rows})")

    # Prepare metadata JSON
    meta_out = {
        "endpoint": endpoint,
        "base_url": BASE_URL,
        "output_csv": out_csv_path,
        "labels": labels,
        "dataTypes": data_types,
        "dataFormats": data_formats,
        "fields": header_fields,
        "filters": filters,
        "sort": sort,
        "page_size": page_size,
        "pages_fetched": total_pages_seen,
        "rows_written": total_rows,
        "last_run_at": datetime.now(timezone.utc).isoformat(),
    }
    _ensure_dirs(meta_dir)
    meta_path = os.path.join(meta_dir, f"{_safe_filename_from_endpoint(endpoint)}_metadata.json")
    with open(meta_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(meta_out, f, indent=2, ensure_ascii=False)
    os.replace(meta_path + ".tmp", meta_path)
    print(f"    Metadata written: {meta_path}")
    return meta_out


def list_available_groups() -> None:
    print("Available groups:")
    for g, meta in GROUPS.items():
        eps = meta.get("endpoints", [])
        print(f"- {g} ({len(eps)} endpoints)")


def list_available_endpoints() -> None:
    print("Available endpoints:")
    for g, meta in GROUPS.items():
        print(f"\n[{g}]")
        for ep in meta.get("endpoints", []):
            print(f"  {ep}")


# =====================
# Main
# =====================

def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Treasury Fiscal Data puller: endpoints to CSV + metadata")
    parser.add_argument("--groups", default="all", help="Comma-separated groups to pull, or 'all' (default)")
    parser.add_argument("--endpoints", default="", help="Comma-separated explicit endpoints to pull (overrides --groups if set)")
    parser.add_argument("--output-data-dir", default=DEFAULT_DATA_DIR, help="Directory for CSV outputs (default: %(default)s)")
    parser.add_argument("--output-metadata-dir", default=DEFAULT_META_DIR, help="Directory for metadata outputs (default: %(default)s)")
    parser.add_argument("--page-size", type=int, default=500, help="Page size per request (default: 500)")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages per endpoint (0 = all available)")
    parser.add_argument("--fields", default="", help="Comma-separated field list to request (blank = all fields)")
    parser.add_argument("--since", default="", help="Optional record_date gte filter (YYYY-MM-DD)")
    parser.add_argument("--sort", default="", help="Sort expression, e.g., -record_date")
    parser.add_argument("--min-interval-sec", type=float, default=float(os.getenv("TREASURY_MIN_INTERVAL_SEC", "1.0")), help="Minimum seconds between API requests (default from env or 1.0)")
    parser.add_argument("--heartbeat-sec", type=float, default=5.0, help="Minimum seconds between progress heartbeats (default: 5.0)")
    parser.add_argument("--summary", action="store_true", help="Print summary progress only (suppress per-page lines)")
    parser.add_argument("--list-groups", action="store_true", help="List available groups and exit")
    parser.add_argument("--list-endpoints", action="store_true", help="List available endpoints and exit")
    args = parser.parse_args(argv)

    if args.list_groups:
        list_available_groups()
        if args.list_endpoints:
            list_available_endpoints()
        return 0
    if args.list_endpoints and not args.list_groups:
        list_available_endpoints()
        return 0

    global _MIN_INTERVAL_SEC, _HEARTBEAT_SEC
    _MIN_INTERVAL_SEC = max(0.1, float(args.min_interval_sec))
    _HEARTBEAT_SEC = max(1.0, float(args.heartbeat_sec))
    print(f"Rate limit: min interval {_MIN_INTERVAL_SEC:.2f}s between requests")

    data_dir = os.path.abspath(os.path.expanduser(args.output_data_dir))
    meta_dir = os.path.abspath(os.path.expanduser(args.output_metadata_dir))
    _ensure_dirs(data_dir, meta_dir)

    # Resolve endpoints list
    selected_endpoints: List[str] = []
    if args.endpoints.strip():
        selected_endpoints = [e.strip() for e in args.endpoints.split(",") if e.strip()]
    else:
        selected_groups: List[str]
        if args.groups.strip().lower() == "all":
            selected_groups = sorted(GROUPS.keys())
        else:
            selected_groups = [g.strip() for g in args.groups.split(",") if g.strip()]
            unknown = [g for g in selected_groups if g not in GROUPS]
            if unknown:
                print(f"Unknown groups: {', '.join(unknown)}", file=sys.stderr)
                list_available_groups()
                return 2
        for g in selected_groups:
            eps = GROUPS[g].get("endpoints", [])
            for ep in eps:
                if ep not in selected_endpoints:
                    selected_endpoints.append(ep)

    if not selected_endpoints:
        print("No endpoints selected.")
        return 0

    fields: List[str] = [s.strip() for s in args.fields.split(",") if s.strip()] if args.fields.strip() else []
    filters: Dict[str, str] = {}
    if args.since.strip():
        # Many endpoints use record_date; users can customize further with --fields and --sort
        filters["record_date_gte"] = f"record_date:gte:{args.since.strip()}"

    start_all = monotonic()
    master_catalog: Dict[str, Dict[str, Any]] = {}

    for idx, endpoint in enumerate(selected_endpoints, start=1):
        print("")
        print(f"=== [{idx}/{len(selected_endpoints)}] Endpoint: {endpoint} ===")
        out_csv = os.path.join(data_dir, f"{_safe_filename_from_endpoint(endpoint)}.csv")
        meta_out = fetch_endpoint_all(
            endpoint=endpoint,
            out_csv_path=out_csv,
            meta_dir=meta_dir,
            page_size=max(1, int(args.page_size)),
            max_pages=max(0, int(args.max_pages)),
            fields=fields,
            filters=filters,
            sort=args.sort.strip(),
            heartbeat_sec=_HEARTBEAT_SEC,
            summary=bool(args.summary),
        )
        # Merge into master catalog
        master_catalog[_safe_filename_from_endpoint(endpoint)] = {
            k: v for k, v in meta_out.items() if k not in ("output_csv",)
        }
        print(f"=== Completed endpoint: {endpoint} (rows={meta_out.get('rows_written', 0)}) ===")

    print("")
    master_catalog_path = os.path.join(meta_dir, "master_catalog.json")
    with open(master_catalog_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(master_catalog, f, indent=2, ensure_ascii=False)
    os.replace(master_catalog_path + ".tmp", master_catalog_path)
    print(f"Wrote master catalog to {master_catalog_path} (endpoints={len(master_catalog)}).")
    print(f"All done in {monotonic() - start_all:0.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


