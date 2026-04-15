#!/usr/bin/env python3
"""
TreasuryDirect.gov Comprehensive Scraper

Scrapes everything available on TreasuryDirect.gov:
  - Securities API (announced, auctioned, search by type/date/CUSIP)
  - Debt-to-the-Penny API (current + historical)
  - Auction pages (results, record-setting data, tentative schedule, FRN daily indexes)
  - Reports & publications (MSPD, public debt, savings bonds tables, quarterly refunding)
  - Forms (marketable securities, savings bonds -- all PDFs)
  - XML auction data directory (historical XML files)
  - RSS feeds (all available feeds)
  - Full site crawl (discovers and downloads all PDFs, Excel, CSV, XML files)

REQUIREMENTS:
  - pdftotext (from poppler-utils)
    macOS: brew install poppler
    Ubuntu/Debian: sudo apt-get install poppler-utils
  - pip: requests beautifulsoup4 lxml openpyxl

USAGE:
    # Interactive mode (run without arguments)
    python treasurydirect_scraper.py

    # API -- quick lookups
    python treasurydirect_scraper.py api cusip 91282CQJ3
    python treasurydirect_scraper.py api auctions --type Bill --days 30
    python treasurydirect_scraper.py api debt
    python treasurydirect_scraper.py api debt --start 2024-01-01

    # JOBS -- bulk downloads
    python treasurydirect_scraper.py job history
    python treasurydirect_scraper.py job history --type Note --download-pdfs
    python treasurydirect_scraper.py job debt
    python treasurydirect_scraper.py job reports
    python treasurydirect_scraper.py job forms
    python treasurydirect_scraper.py job xml
    python treasurydirect_scraper.py job rss
    python treasurydirect_scraper.py job crawl --max-pages 1000
    python treasurydirect_scraper.py job all
"""

import os
import re
import sys
import csv
import json
import argparse
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
from time import sleep, time
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from collections import defaultdict
from typing import Optional, List, Dict, Set, Tuple

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests beautifulsoup4 lxml openpyxl")
    sys.exit(1)


# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://www.treasurydirect.gov"

SECURITIES_API = f"{BASE_URL}/TA_WS/securities"
DEBT_API = f"{BASE_URL}/NP_WS/debt"

SECURITY_TYPES = ["Bill", "Note", "Bond", "TIPS", "FRN", "CMB"]

SECURITIES_ENDPOINTS = {
    "announced": f"{SECURITIES_API}/announced",
    "auctioned": f"{SECURITIES_API}/auctioned",
    "search":    f"{SECURITIES_API}/search",
}

DEBT_ENDPOINTS = {
    "current": f"{DEBT_API}/current",
    "search":  f"{DEBT_API}/search",
}

RSS_FEEDS = {
    "Treasury Offering Announcements": f"{BASE_URL}/TA_WS/securities/announced/rss",
    "Treasury Auction Results":        f"{BASE_URL}/TA_WS/securities/auctioned/rss",
    "Debt to the Penny":               f"{BASE_URL}/NP_WS/debt/feeds/recent",
    "Monthly Statement Public Debt":   f"{BASE_URL}/rss/mspd.xml",
    "Savings Bonds Pro Updates":       f"{BASE_URL}/rss/sbpro.xml",
}

REPORT_PAGES = {
    "Public Debt Reports":         "/government/public-debt-reports/",
    "SBN Tables & Downloads":      "/government/public-debt-reports/us-savings-bonds-and-notes/",
    "Federal Investment Reports":  "/government/federal-investments-program/federal-investments-reports/",
    "Savings Bonds Rates":         "/savings-bonds/i-bonds/i-bonds-interest-rates/",
    "EE Bonds Rates":              "/savings-bonds/ee-bonds/ee-bonds-interest-rates/",
    "Useful Research Data":        "/auctions/announcements-data-results/useful-data-for-research/",
}

FORMS_PAGES = {
    "Marketable Securities Forms": "/marketable-securities/forms/",
    "General Forms":               "/forms/",
}

XML_DIR_URL = f"{BASE_URL}/xml/"

CRAWL_SEED_URLS = [
    "/",
    "/auctions/",
    "/auctions/results/",
    "/auctions/announcements-data-results/",
    "/auctions/announcements-data-results/useful-data-for-research/",
    "/auctions/announcements-data-results/frn-daily/",
    "/auctions/quarterly-refunding/",
    "/auctions/auction-query/results/",
    "/marketable-securities/",
    "/marketable-securities/treasury-bills/",
    "/marketable-securities/treasury-notes/",
    "/marketable-securities/treasury-bonds/",
    "/marketable-securities/tips/",
    "/marketable-securities/floating-rate-notes/",
    "/marketable-securities/forms/",
    "/savings-bonds/",
    "/savings-bonds/i-bonds/",
    "/savings-bonds/i-bonds/i-bonds-interest-rates/",
    "/savings-bonds/ee-bonds/",
    "/savings-bonds/ee-bonds/ee-bonds-interest-rates/",
    "/government/",
    "/government/public-debt-reports/",
    "/government/public-debt-reports/us-savings-bonds-and-notes/",
    "/government/federal-investments-program/",
    "/government/federal-investments-program/federal-investments-reports/",
    "/forms/",
    "/instit/annceresult/annceresult.htm",
    "/instit/annceresult/auctdata/auctdata.htm",
    "/instit/annceresult/annceresult_research.htm",
    "/webapis/webapisindex.htm",
    "/webapis/webapisecurities.htm",
    "/webapis/webapisdebt.htm",
    "/rss/index.htm",
    "/legal-information/",
    "/legal-information/developers/",
]

DOWNLOADABLE_EXTENSIONS = {
    ".pdf", ".xls", ".xlsx", ".csv", ".xml", ".json",
    ".doc", ".docx", ".txt", ".zip", ".gz",
}

DEFAULT_OUTPUT_DIR = "apis/treasurydirect"
AUCTION_PDF_BASE = f"{BASE_URL}/instit/annceresult/press/preanre"

API_PAGE_SIZE = 250
MAX_API_PAGES = 200
RATE_LIMIT_SECONDS = 0.5

FULL_HISTORY_START = "01/01/1997"


class TreasuryDirectScraper:

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR, verbose: bool = True):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

        self.stats: Dict[str, int] = defaultdict(int)
        self._visited_urls: Set[str] = set()
        self._has_pdftotext: Optional[bool] = None

    # ── helpers ──────────────────────────────────────────────────────────

    def log(self, msg: str, force: bool = False):
        if self.verbose or force:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")
            sys.stdout.flush()

    def _progress(self, current: int, total: int, label: str = ""):
        if not self.verbose:
            return
        pct = current / total * 100 if total else 0
        bar_len = 30
        filled = int(bar_len * current / total) if total else 0
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r  [{bar}] {pct:5.1f}% ({current}/{total}) {label}", end="", flush=True)
        if current >= total:
            print()

    def _check_pdftotext(self) -> bool:
        if self._has_pdftotext is not None:
            return self._has_pdftotext
        try:
            subprocess.run(["pdftotext", "-v"], capture_output=True, check=False)
            self._has_pdftotext = True
        except FileNotFoundError:
            self._has_pdftotext = False
            self.log("WARNING: pdftotext not found. PDFs will be saved raw (not converted).", force=True)
            self.log("  Install: brew install poppler  (macOS)", force=True)
        return self._has_pdftotext

    def _fetch(self, url: str, timeout: int = 30, retries: int = 3) -> Optional[requests.Response]:
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=timeout)
                if resp.status_code == 403:
                    self.session.headers["Accept"] = "*/*"
                    sleep(2)
                    resp = self.session.get(url, timeout=timeout)
                if resp.status_code == 200:
                    return resp
                if resp.status_code == 404:
                    return None
                self.log(f"  HTTP {resp.status_code} for {url}")
            except requests.exceptions.Timeout:
                self.log(f"  Timeout (attempt {attempt + 1}/{retries}): {url}")
                sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                self.log(f"  Request error: {e}")
                sleep(2 ** attempt)
        return None

    def _fetch_json(self, url: str) -> Optional[dict]:
        resp = self._fetch(url)
        if resp is None:
            return None
        try:
            return resp.json()
        except json.JSONDecodeError:
            self.log(f"  Invalid JSON from {url}")
            return None

    def _save_json(self, data, filepath: Path):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        self.stats["json_saved"] += 1

    def _save_text(self, text: str, filepath: Path):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)

    def _download_file(self, url: str, dest_dir: Path, filename: Optional[str] = None,
                       convert_pdf: bool = True) -> Optional[Path]:
        if not filename:
            parsed = urlparse(url)
            filename = Path(parsed.path).name
            if not filename or filename == "/":
                filename = "index.html"

        dest_dir.mkdir(parents=True, exist_ok=True)
        filepath = dest_dir / filename

        if filepath.exists() and filepath.stat().st_size > 0:
            self.stats["skipped_existing"] += 1
            return filepath

        resp = self._fetch(url, timeout=60)
        if resp is None:
            self.stats["download_errors"] += 1
            return None

        with open(filepath, "wb") as f:
            f.write(resp.content)
        self.stats["files_downloaded"] += 1

        ext = filepath.suffix.lower()
        if ext == ".pdf" and convert_pdf and self._check_pdftotext():
            md_path = filepath.with_suffix(".md")
            if not md_path.exists():
                result = subprocess.run(
                    ["pdftotext", "-layout", str(filepath), str(md_path)],
                    capture_output=True, text=True,
                )
                if result.returncode == 0 and md_path.exists() and md_path.stat().st_size > 0:
                    frontmatter = (
                        f"---\n"
                        f'title: "{filename}"\n'
                        f"date: {datetime.now().strftime('%Y-%m-%d')}\n"
                        f'url: "{url}"\n'
                        f"---\n\n"
                    )
                    content = md_path.read_text(encoding="utf-8", errors="replace")
                    md_path.write_text(frontmatter + content, encoding="utf-8")
                    self.stats["pdfs_converted"] += 1
                else:
                    self.log(f"  pdftotext failed for {filename}")

        return filepath

    def _extract_links(self, soup: BeautifulSoup, base_url: str,
                       extensions: Optional[Set[str]] = None) -> List[Tuple[str, str]]:
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            if "treasurydirect.gov" not in parsed.netloc and not parsed.netloc == "":
                continue
            if extensions:
                ext = Path(parsed.path).suffix.lower()
                if ext not in extensions:
                    continue
            text = a.get_text(strip=True) or Path(parsed.path).name
            links.append((full_url, text))
        return links

    def _scrape_page_for_downloads(self, url: str, dest_dir: Path, label: str = "") -> int:
        resp = self._fetch(url)
        if resp is None:
            self.log(f"  Could not fetch: {url}")
            return 0

        soup = BeautifulSoup(resp.text, "html.parser")
        file_links = self._extract_links(soup, url, DOWNLOADABLE_EXTENSIONS)
        count = 0

        if file_links:
            self.log(f"  Found {len(file_links)} downloadable files on {label or url}")
            for i, (file_url, text) in enumerate(file_links):
                self._progress(i + 1, len(file_links), Path(urlparse(file_url).path).name)
                self._download_file(file_url, dest_dir)
                sleep(RATE_LIMIT_SECONDS)
                count += 1
        else:
            self.log(f"  No downloadable files found on {label or url}")

        return count

    # ── Securities API ───────────────────────────────────────────────────

    def scrape_securities_api(self, security_type: Optional[str] = None,
                              days: int = 365, cusip: Optional[str] = None,
                              full_history: bool = False,
                              download_pdfs: bool = False):
        self.log("=" * 80)
        self.log("SECURITIES API -- AUCTION DATA")
        self.log("=" * 80)

        out_dir = self.output_dir / "securities_api"
        out_dir.mkdir(parents=True, exist_ok=True)

        if cusip:
            self._fetch_securities_by_cusip(cusip, out_dir)
            return

        types_to_fetch = [security_type] if security_type and security_type != "all" else SECURITY_TYPES

        if full_history:
            start_date = FULL_HISTORY_START
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%m/%d/%Y")
        end_date = datetime.now().strftime("%m/%d/%Y")

        all_combined: List[dict] = []

        for sec_type in types_to_fetch:
            records = self._fetch_full_auction_history(sec_type, start_date, end_date, out_dir)
            if records:
                all_combined.extend(records)

        if all_combined:
            self.log(f"\n  Combined total: {len(all_combined)} records across {len(types_to_fetch)} types")

            all_combined.sort(key=lambda r: r.get("auctionDate", ""), reverse=True)
            self._save_json(all_combined, out_dir / "all_auctions.json")
            self._json_records_to_csv(all_combined, out_dir / "all_auctions.csv")

            self._build_auction_summary(all_combined, out_dir)

        if download_pdfs and all_combined:
            self._download_auction_pdfs(all_combined, out_dir / "pdfs")

    def _fetch_full_auction_history(self, sec_type: str, start_date: str,
                                     end_date: str, out_dir: Path) -> List[dict]:
        """Fetch auction history for a security type using date-range chunking.

        The search endpoint returns all matching records in one response
        (up to ~2000) but fails on very wide ranges for high-volume types.
        Chunk into 2-year windows to stay safe.
        """
        self.log(f"\n  {sec_type}: fetching {start_date} to {end_date}")

        try:
            start_dt = datetime.strptime(start_date, "%m/%d/%Y")
        except ValueError:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        try:
            end_dt = datetime.strptime(end_date, "%m/%d/%Y")
        except ValueError:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        chunk_years = 2 if sec_type == "Bill" else 5
        chunk_delta = timedelta(days=chunk_years * 365)

        all_records: List[dict] = []
        seen_cusip_dates: Set[str] = set()
        current_start = start_dt

        while current_start < end_dt:
            current_end = min(current_start + chunk_delta, end_dt)

            params = {
                "format": "json",
                "type": sec_type,
                "startDate": current_start.strftime("%m/%d/%Y"),
                "endDate": current_end.strftime("%m/%d/%Y"),
                "pagesize": "250",
            }
            url = f"{SECURITIES_ENDPOINTS['search']}?{urlencode(params)}"
            data = self._fetch_json(url)

            if data and isinstance(data, list):
                new_count = 0
                for rec in data:
                    if not isinstance(rec, dict):
                        continue
                    dedup_key = f"{rec.get('cusip', '')}_{rec.get('auctionDate', '')}"
                    if dedup_key not in seen_cusip_dates:
                        seen_cusip_dates.add(dedup_key)
                        all_records.append(rec)
                        new_count += 1

                self.log(
                    f"    {current_start.strftime('%Y-%m-%d')} to "
                    f"{current_end.strftime('%Y-%m-%d')}: "
                    f"{len(data)} returned, {new_count} new (total: {len(all_records)})"
                )
            else:
                self.log(f"    {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}: no data")

            current_start = current_end + timedelta(days=1)
            sleep(RATE_LIMIT_SECONDS)

        if all_records:
            all_records.sort(key=lambda r: r.get("auctionDate", ""), reverse=True)

            for rec in all_records:
                self._compute_tail(rec)

            filepath = out_dir / f"{sec_type.lower()}_auctions.json"
            self._save_json(all_records, filepath)
            csv_path = filepath.with_suffix(".csv")
            self._json_records_to_csv(all_records, csv_path)

            oldest = all_records[-1].get("auctionDate", "?")[:10]
            newest = all_records[0].get("auctionDate", "?")[:10]
            self.log(f"    Saved {len(all_records)} {sec_type} records [{newest} to {oldest}]")
            self.stats["securities_records"] += len(all_records)

        return all_records

    @staticmethod
    def _compute_tail(rec: dict):
        """Compute auction tail = highYield - averageMedianYield (bp).

        The true tail is stop-out vs when-issued, but the API doesn't carry
        WI yields. highYield vs median is a useful intra-auction dispersion
        measure available from the data.
        """
        try:
            high = rec.get("highYield")
            median = rec.get("averageMedianYield")
            if high and median:
                high_f = float(str(high).strip())
                median_f = float(str(median).strip())
                rec["tailBps"] = round((high_f - median_f) * 100, 2)
            else:
                rec["tailBps"] = None
        except (ValueError, TypeError):
            rec["tailBps"] = None

    def _download_auction_pdfs(self, records: List[dict], pdf_dir: Path):
        """Download announcement and result PDFs referenced in auction records."""
        self.log(f"\n  Downloading auction PDFs...")
        pdf_dir.mkdir(parents=True, exist_ok=True)

        pdf_fields = [
            "pdfFilenameAnnouncement",
            "pdfFilenameCompetitiveResults",
            "pdfFilenameNoncompetitiveResults",
            "pdfFilenameSpecialAnnouncement",
        ]
        to_download: List[Tuple[str, str]] = []

        for rec in records:
            for field in pdf_fields:
                fname = rec.get(field)
                if fname and isinstance(fname, str) and fname.strip():
                    fname = fname.strip()
                    date_match = re.search(r"_(\d{4})\d{4}_", fname)
                    year = date_match.group(1) if date_match else "unknown"
                    url = f"{AUCTION_PDF_BASE}/{year}/{fname}"
                    to_download.append((url, fname))

        unique_downloads = list(dict(to_download).items())
        self.log(f"    {len(unique_downloads)} unique PDFs to download")

        for i, (url, fname) in enumerate(unique_downloads):
            self._progress(i + 1, len(unique_downloads), fname[:40])
            self._download_file(url, pdf_dir, filename=fname)
            sleep(RATE_LIMIT_SECONDS)

    def _fetch_securities_by_cusip(self, cusip: str, out_dir: Path):
        self.log(f"\n  Searching by CUSIP: {cusip}")
        url = f"{SECURITIES_ENDPOINTS['search']}?cusip={cusip}&format=json"
        data = self._fetch_json(url)
        if not data:
            url = f"{SECURITIES_API}/{cusip}?format=json"
            data = self._fetch_json(url)
        if data:
            records = data if isinstance(data, list) else [data]
            for rec in records:
                if isinstance(rec, dict):
                    self._compute_tail(rec)
            filepath = out_dir / f"cusip_{cusip}.json"
            self._save_json(records if len(records) > 1 else records[0], filepath)
            self._json_records_to_csv(records, out_dir / f"cusip_{cusip}.csv")
            rec = records[0] if records else {}
            self.log(f"  {rec.get('securityType', '?')} {rec.get('securityTerm', '?')}  "
                     f"auction={str(rec.get('auctionDate', '?'))[:10]}  "
                     f"yield={rec.get('highYield', '?')}  "
                     f"b/c={rec.get('bidToCoverRatio', '?')}  "
                     f"tail={rec.get('tailBps', '?')}bp")
        else:
            self.log(f"  No data found for CUSIP {cusip}", force=True)

    def _build_auction_summary(self, records: List[dict], out_dir: Path):
        """Build a compact summary CSV focused on key auction metrics."""
        summary_fields = [
            "auctionDate", "cusip", "securityType", "securityTerm",
            "interestRate", "highYield", "averageMedianYield", "lowYield",
            "tailBps", "pricePer100", "bidToCoverRatio",
            "offeringAmount", "totalAccepted", "totalTendered",
            "competitiveAccepted", "competitiveTendered",
            "directBidderAccepted", "directBidderTendered",
            "indirectBidderAccepted", "indirectBidderTendered",
            "primaryDealerAccepted", "primaryDealerTendered",
            "allocationPercentage", "somaAccepted",
            "maturityDate", "issueDate", "reopening",
        ]
        summary_path = out_dir / "auction_summary.csv"
        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=summary_fields, extrasaction="ignore")
            writer.writeheader()
            for rec in records:
                row = {}
                for field in summary_fields:
                    val = rec.get(field, "")
                    if isinstance(val, str) and "T00:00:00" in val:
                        val = val[:10]
                    row[field] = val
                writer.writerow(row)
        self.stats["csv_saved"] += 1
        self.log(f"  Auction summary CSV saved ({len(records)} rows, {len(summary_fields)} key fields)")

    def _json_records_to_csv(self, records: list, filepath: Path):
        if not records:
            return
        sample = records[0] if isinstance(records[0], dict) else {}
        if not sample:
            return
        fieldnames = list(sample.keys())
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for rec in records:
                if isinstance(rec, dict):
                    writer.writerow(rec)
        self.stats["csv_saved"] += 1

    # ── Debt API ─────────────────────────────────────────────────────────

    def scrape_debt_api(self, start_date: Optional[str] = None,
                        end_date: Optional[str] = None, current_only: bool = False):
        self.log("=" * 80)
        self.log("DEBT-TO-THE-PENNY API")
        self.log("=" * 80)

        out_dir = self.output_dir / "debt_api"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Current debt
        self.log("\n  Fetching current debt...")
        url = f"{DEBT_ENDPOINTS['current']}?format=json"
        data = self._fetch_json(url)
        if data:
            self._save_json(data, out_dir / "debt_current.json")
            self.log(f"  Current debt data saved")
            self.stats["debt_records"] += 1
            if isinstance(data, dict):
                for key in ["totalDebt", "totalPublicDebtOutstanding", "tot_pub_debt_out_amt"]:
                    if key in data:
                        self.log(f"    {key}: {data[key]}")

        if current_only:
            return

        # Historical debt
        if not start_date:
            start_date = "2000-01-01"
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        self.log(f"\n  Fetching historical debt: {start_date} to {end_date}")

        all_records = []
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        chunk_months = 12

        current_start = start_dt
        total_chunks = max(1, int((end_dt - start_dt).days / (chunk_months * 30)))
        chunk_num = 0

        while current_start < end_dt:
            current_end = min(
                current_start + timedelta(days=chunk_months * 30),
                end_dt,
            )
            chunk_num += 1

            params = {
                "startdate": current_start.strftime("%Y-%m-%d"),
                "enddate": current_end.strftime("%Y-%m-%d"),
                "format": "json",
            }
            url = f"{DEBT_ENDPOINTS['search']}?{urlencode(params)}"
            data = self._fetch_json(url)

            if data:
                records = data if isinstance(data, list) else data.get("data", data.get("entries", []))
                if isinstance(records, list):
                    all_records.extend(records)
                    self._progress(chunk_num, total_chunks, f"{len(all_records)} total records")

            current_start = current_end + timedelta(days=1)
            sleep(RATE_LIMIT_SECONDS)

        if all_records:
            filepath = out_dir / "debt_historical.json"
            self._save_json(all_records, filepath)
            csv_path = filepath.with_suffix(".csv")
            self._json_records_to_csv(all_records, csv_path)
            self.log(f"  Historical debt: {len(all_records)} records saved")
            self.stats["debt_records"] += len(all_records)

    # ── Treasury Buybacks (via Fiscal Data API) ────────────────────────

    def scrape_buybacks(self, from_date: Optional[str] = None,
                        to_date: Optional[str] = None,
                        operation_type: Optional[str] = None,
                        results_only: bool = False):
        self.log("=" * 80)
        self.log("TREASURY BUYBACK OPERATIONS")
        self.log("=" * 80)

        out_dir = self.output_dir / "buybacks"
        out_dir.mkdir(parents=True, exist_ok=True)

        BUYBACK_API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/buybacks_operations"
        params = {
            "sort": "-operation_date",
            "page[size]": "500",
            "format": "json",
        }
        filters = []
        if from_date:
            filters.append(f"operation_date:gte:{from_date}")
        if to_date:
            filters.append(f"operation_date:lte:{to_date}")
        if operation_type:
            filters.append(f"operation_type:eq:{operation_type}")
        if filters:
            params["filter"] = ",".join(filters)

        all_records = []
        page = 1
        while True:
            params["page[number]"] = str(page)
            url = f"{BUYBACK_API}?{urlencode(params)}"
            data = self._fetch_json(url)
            if not data or "data" not in data:
                break
            rows = data["data"]
            all_records.extend(rows)
            total_pages = data.get("meta", {}).get("total-pages", 1)
            self._progress(page, total_pages, f"{len(all_records)} buyback records")
            if page >= total_pages:
                break
            page += 1
            sleep(RATE_LIMIT_SECONDS)

        if results_only:
            all_records = [r for r in all_records
                           if r.get("total_par_amt_accepted") and r["total_par_amt_accepted"] != "null"]

        if all_records:
            self._save_json(all_records, out_dir / "buybacks_operations.json")
            self._json_records_to_csv(all_records, out_dir / "buybacks_operations.csv")
            self.log(f"\n  Buyback operations: {len(all_records)} records saved")

            by_type = defaultdict(list)
            for r in all_records:
                by_type[r.get("operation_type", "Unknown")].append(r)
            for otype, ops in sorted(by_type.items()):
                with_results = [o for o in ops if o.get("total_par_amt_accepted") and o["total_par_amt_accepted"] != "null"]
                total_accepted = sum(float(o["total_par_amt_accepted"]) for o in with_results)
                self.log(f"    {otype}: {len(ops)} operations, {len(with_results)} with results, "
                         f"${total_accepted/1e9:.1f}B total accepted")

            self.stats.setdefault("buyback_records", 0)
            self.stats["buyback_records"] += len(all_records)
        else:
            self.log("  No buyback data returned.")

        return all_records

    def _scrape_page_html_content(self, url: str, dest_dir: Path, label: str):
        resp = self._fetch(url)
        if resp is None:
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup.find_all(["script", "style", "nav", "footer"]):
            tag.decompose()

        main = soup.find("main") or soup.find("article") or soup.find("div", {"role": "main"})
        if not main:
            main = soup.find("div", class_=lambda x: x and "content" in str(x).lower())
        if not main:
            main = soup.body or soup

        text = main.get_text(separator="\n\n", strip=True)
        if text and len(text) > 100:
            filepath = dest_dir / f"{self._slugify(label)}_content.md"
            frontmatter = (
                f"---\n"
                f'title: "{label}"\n'
                f"date: {datetime.now().strftime('%Y-%m-%d')}\n"
                f'url: "{url}"\n'
                f"---\n\n"
            )
            self._save_text(frontmatter + text, filepath)
            self.stats["pages_saved"] += 1

        tables = main.find_all("table") if main else []
        for i, table in enumerate(tables):
            rows = []
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if headers:
                rows.append(headers)
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td"])]
                if cells:
                    rows.append(cells)
            if rows:
                csv_path = dest_dir / f"{self._slugify(label)}_table_{i + 1}.csv"
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                self.stats["tables_extracted"] += 1

    # ── Reports & Publications ───────────────────────────────────────────

    def scrape_reports(self):
        self.log("=" * 80)
        self.log("REPORTS & PUBLICATIONS")
        self.log("=" * 80)

        out_dir = self.output_dir / "reports"

        for label, path in REPORT_PAGES.items():
            url = urljoin(BASE_URL, path)
            self.log(f"\n  {label}: {url}")
            sub_dir = out_dir / self._slugify(label)
            self._scrape_page_for_downloads(url, sub_dir, label)
            self._scrape_page_html_content(url, sub_dir, label)
            sleep(RATE_LIMIT_SECONDS)

        self._scrape_mspd(out_dir)
        self._scrape_savings_bonds_tables(out_dir)

    def _scrape_mspd(self, out_dir: Path):
        self.log("\n  Monthly Statement of the Public Debt (MSPD)")
        mspd_urls = [
            "/government/public-debt-reports/",
        ]
        dest = out_dir / "mspd"
        for path in mspd_urls:
            url = urljoin(BASE_URL, path)
            resp = self._fetch(url)
            if resp is None:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            file_links = self._extract_links(soup, url, DOWNLOADABLE_EXTENSIONS)
            for file_url, text in file_links:
                if any(kw in file_url.lower() for kw in ["mspd", "opds", "debt", "statement"]):
                    self._download_file(file_url, dest)
                    sleep(RATE_LIMIT_SECONDS)

    def _scrape_savings_bonds_tables(self, out_dir: Path):
        self.log("\n  Savings Bonds & Notes (SBN) Tables")
        url = urljoin(BASE_URL, "/government/public-debt-reports/us-savings-bonds-and-notes/")
        dest = out_dir / "savings_bonds_tables"
        self._scrape_page_for_downloads(url, dest, "SBN Tables")

    # ── Forms (PDFs) ─────────────────────────────────────────────────────

    def scrape_forms(self):
        self.log("=" * 80)
        self.log("FORMS (PDFs)")
        self.log("=" * 80)

        out_dir = self.output_dir / "forms"

        for label, path in FORMS_PAGES.items():
            url = urljoin(BASE_URL, path)
            self.log(f"\n  {label}: {url}")
            sub_dir = out_dir / self._slugify(label)
            self._scrape_page_for_downloads(url, sub_dir, label)

            resp = self._fetch(url)
            if resp:
                soup = BeautifulSoup(resp.text, "html.parser")
                sub_links = self._extract_links(soup, url)
                for sub_url, text in sub_links:
                    parsed = urlparse(sub_url)
                    if (
                        "treasurydirect.gov" in parsed.netloc
                        and parsed.path != urlparse(url).path
                        and ("form" in parsed.path.lower() or "pdf" in parsed.path.lower())
                    ):
                        self._scrape_page_for_downloads(sub_url, sub_dir, text)
                        sleep(RATE_LIMIT_SECONDS)

    # ── XML Data Directory ───────────────────────────────────────────────

    def scrape_xml_data(self):
        self.log("=" * 80)
        self.log("XML AUCTION DATA DIRECTORY")
        self.log("=" * 80)

        out_dir = self.output_dir / "xml_data"
        out_dir.mkdir(parents=True, exist_ok=True)

        resp = self._fetch(XML_DIR_URL)
        if resp is None:
            self.log("  Could not access XML directory, trying known patterns...")
            self._fetch_xml_by_pattern(out_dir)
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        xml_links = self._extract_links(soup, XML_DIR_URL, {".xml"})

        if xml_links:
            self.log(f"  Found {len(xml_links)} XML files in directory")
            for i, (xml_url, text) in enumerate(xml_links):
                self._progress(i + 1, len(xml_links), Path(urlparse(xml_url).path).name)
                self._download_file(xml_url, out_dir, convert_pdf=False)
                sleep(RATE_LIMIT_SECONDS)
        else:
            self.log("  No XML links found in directory listing, trying known patterns...")
            all_links = self._extract_links(soup, XML_DIR_URL)
            sub_dirs = [u for u, t in all_links if u.rstrip("/") != XML_DIR_URL.rstrip("/")]

            if sub_dirs:
                self.log(f"  Found {len(sub_dirs)} subdirectories, crawling...")
                for sub_url in sub_dirs:
                    sub_resp = self._fetch(sub_url)
                    if sub_resp:
                        sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
                        sub_xml_links = self._extract_links(sub_soup, sub_url, {".xml"})
                        for xml_url, text in sub_xml_links:
                            self._download_file(xml_url, out_dir, convert_pdf=False)
                            sleep(RATE_LIMIT_SECONDS)
                    sleep(RATE_LIMIT_SECONDS)
            else:
                self._fetch_xml_by_pattern(out_dir)

    def _fetch_xml_by_pattern(self, out_dir: Path):
        self.log("  Trying known XML URL patterns...")
        now = datetime.now()
        count = 0
        for year in range(2008, now.year + 1):
            for month in range(1, 13):
                if year == now.year and month > now.month:
                    break
                for day in [1, 15]:
                    url = f"{XML_DIR_URL}A_{year}{month:02d}{day:02d}_1.xml"
                    resp = self._fetch(url, retries=1)
                    if resp and resp.status_code == 200:
                        filepath = out_dir / f"A_{year}{month:02d}{day:02d}_1.xml"
                        filepath.write_bytes(resp.content)
                        count += 1
                        self._progress(count, 1, f"Found: A_{year}{month:02d}{day:02d}_1.xml")
            sleep(RATE_LIMIT_SECONDS)
        self.log(f"\n  Fetched {count} XML files by pattern")

    # ── RSS Feeds ────────────────────────────────────────────────────────

    def scrape_rss_feeds(self):
        self.log("=" * 80)
        self.log("RSS / XML FEEDS")
        self.log("=" * 80)

        out_dir = self.output_dir / "rss_feeds"
        out_dir.mkdir(parents=True, exist_ok=True)

        rss_index_url = urljoin(BASE_URL, "/rss/index.htm")
        resp = self._fetch(rss_index_url)
        discovered_feeds: Dict[str, str] = dict(RSS_FEEDS)

        if resp:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if any(ext in href.lower() for ext in [".xml", "rss", "feed", "atom"]):
                    full_url = urljoin(rss_index_url, href)
                    text = a.get_text(strip=True) or Path(urlparse(full_url).path).name
                    discovered_feeds[text] = full_url

        self.log(f"  Found {len(discovered_feeds)} feeds total")

        for label, feed_url in discovered_feeds.items():
            self.log(f"\n    {label}: {feed_url}")
            resp = self._fetch(feed_url)
            if resp is None:
                continue

            filename = self._slugify(label) + ".xml"
            filepath = out_dir / filename
            filepath.write_bytes(resp.content)
            self.stats["feeds_saved"] += 1

            try:
                root = ET.fromstring(resp.content)
                json_data = self._xml_to_dict(root)
                json_path = filepath.with_suffix(".json")
                self._save_json(json_data, json_path)
            except ET.ParseError:
                self.log(f"    Could not parse XML for {label}")

            sleep(RATE_LIMIT_SECONDS)

    def _xml_to_dict(self, element) -> dict:
        result = {}
        if element.text and element.text.strip():
            result["_text"] = element.text.strip()
        for key, val in element.attrib.items():
            result[f"@{key}"] = val
        children = defaultdict(list)
        for child in element:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            children[tag].append(self._xml_to_dict(child))
        for tag, items in children.items():
            result[tag] = items if len(items) > 1 else items[0]
        return result

    # ── Full Site Crawl ──────────────────────────────────────────────────

    def scrape_crawl(self, max_pages: int = 500):
        self.log("=" * 80)
        self.log("FULL SITE CRAWL")
        self.log("=" * 80)

        out_dir = self.output_dir / "crawl"
        downloads_dir = out_dir / "downloads"
        pages_dir = out_dir / "pages"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        pages_dir.mkdir(parents=True, exist_ok=True)

        queue = [urljoin(BASE_URL, path) for path in CRAWL_SEED_URLS]
        visited: Set[str] = set()
        all_file_urls: Set[str] = set()
        all_page_links: List[Tuple[str, str]] = []
        pages_crawled = 0

        self.log(f"  Starting crawl with {len(queue)} seed URLs, max {max_pages} pages")

        while queue and pages_crawled < max_pages:
            url = queue.pop(0)
            normalized = url.split("?")[0].split("#")[0].rstrip("/")

            if normalized in visited:
                continue
            visited.add(normalized)

            resp = self._fetch(url, retries=1)
            if resp is None:
                continue

            content_type = resp.headers.get("Content-Type", "")
            if "html" not in content_type and "xml" not in content_type:
                ext = Path(urlparse(url).path).suffix.lower()
                if ext in DOWNLOADABLE_EXTENSIONS:
                    all_file_urls.add(url)
                continue

            pages_crawled += 1
            self._progress(pages_crawled, max_pages, urlparse(url).path[:50])

            soup = BeautifulSoup(resp.text, "html.parser")

            file_links = self._extract_links(soup, url, DOWNLOADABLE_EXTENSIONS)
            for file_url, text in file_links:
                all_file_urls.add(file_url)

            page_links = self._extract_links(soup, url)
            for link_url, text in page_links:
                parsed = urlparse(link_url)
                if "treasurydirect.gov" not in parsed.netloc:
                    continue
                link_normalized = link_url.split("?")[0].split("#")[0].rstrip("/")
                if link_normalized not in visited:
                    queue.append(link_url)
                    all_page_links.append((link_url, text))

            tables = soup.find_all("table")
            if tables:
                page_slug = self._slugify(urlparse(url).path.strip("/") or "index")
                for i, table in enumerate(tables):
                    rows = []
                    headers = [th.get_text(strip=True) for th in table.find_all("th")]
                    if headers:
                        rows.append(headers)
                    for tr in table.find_all("tr"):
                        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                        if cells:
                            rows.append(cells)
                    if len(rows) > 1:
                        csv_path = pages_dir / f"{page_slug}_table_{i + 1}.csv"
                        with open(csv_path, "w", newline="", encoding="utf-8") as f:
                            csv.writer(f).writerows(rows)
                        self.stats["tables_extracted"] += 1

            sleep(RATE_LIMIT_SECONDS)

        self.log(f"\n  Crawled {pages_crawled} pages, found {len(all_file_urls)} downloadable files")

        if all_file_urls:
            self.log(f"\n  Downloading {len(all_file_urls)} files...")
            for i, file_url in enumerate(sorted(all_file_urls)):
                ext = Path(urlparse(file_url).path).suffix.lower()
                ext_dir = downloads_dir / ext.lstrip(".")
                self._progress(i + 1, len(all_file_urls), Path(urlparse(file_url).path).name[:40])
                self._download_file(file_url, ext_dir)
                sleep(RATE_LIMIT_SECONDS)

        sitemap_path = out_dir / "sitemap.json"
        sitemap_data = {
            "crawl_date": datetime.now().isoformat(),
            "pages_crawled": pages_crawled,
            "files_found": len(all_file_urls),
            "file_urls": sorted(all_file_urls),
            "page_links": [{"url": u, "text": t} for u, t in all_page_links[:5000]],
        }
        self._save_json(sitemap_data, sitemap_path)
        self.log(f"  Sitemap saved to {sitemap_path}")

    # ── Run All ──────────────────────────────────────────────────────────

    def run_all(self, days: int = 365, full_history: bool = False,
                download_pdfs: bool = False):
        start_time = time()
        self.log("=" * 80)
        self.log("TREASURYDIRECT.GOV -- FULL SCRAPE")
        self.log("=" * 80)

        self.scrape_securities_api(security_type="all", days=days,
                                   full_history=full_history,
                                   download_pdfs=download_pdfs)
        self.scrape_debt_api()
        self.scrape_reports()
        self.scrape_forms()
        self.scrape_xml_data()
        self.scrape_rss_feeds()
        self.scrape_crawl()

        self._print_summary(time() - start_time)

    def _print_summary(self, elapsed: float):
        self.log("\n" + "=" * 80, force=True)
        self.log("SCRAPE COMPLETE", force=True)
        self.log("=" * 80, force=True)
        self.log(f"  Time elapsed: {elapsed:.1f}s", force=True)
        self.log(f"  Output directory: {self.output_dir.resolve()}", force=True)
        self.log("", force=True)
        for key, val in sorted(self.stats.items()):
            self.log(f"  {key}: {val}", force=True)
        self.log("=" * 80, force=True)

    @staticmethod
    def _slugify(text: str) -> str:
        text = re.sub(r"[^\w\s-]", "", text.lower())
        return re.sub(r"[\s_]+", "_", text).strip("_")[:80]


# ── Interactive CLI ──────────────────────────────────────────────────────────

def interactive_menu():
    print()
    print("=" * 80)
    print("  TREASURYDIRECT.GOV SCRAPER")
    print("=" * 80)
    print()
    print("  API  (quick lookups)")
    print("    1. Auction by CUSIP")
    print("    2. Recent auctions (last N days, by type)")
    print("    3. Current debt to the penny")
    print("    4. Debt for date range")
    print()
    print("  JOBS (bulk downloads)")
    print("    5. Full auction history since 1997 (~9000 records)")
    print("    6. Full auction history + result PDFs")
    print("    7. Full historical debt (2000-present)")
    print("    8. Reports & publications (MSPD, SBN tables, rates)")
    print("    9. Forms (all PDF forms)")
    print("   10. XML auction data directory")
    print("   11. RSS / XML feeds")
    print("   12. Full site crawl (discover + download everything)")
    print("   13. Run ALL jobs")
    print()
    print("  BUYBACKS")
    print("   14. Treasury buyback operations (all)")
    print("   15. Buybacks -- Liquidity Support only")
    print("   16. Buybacks -- Cash Management only")
    print()
    print("    0. Exit")
    print()
    print("-" * 80)

    scraper = TreasuryDirectScraper()

    while True:
        choice = input("\nSelect option: ").strip()

        if choice == "0":
            print("Exiting.")
            sys.exit(0)

        elif choice == "1":
            cusip = input("  CUSIP: ").strip()
            if cusip:
                scraper.scrape_securities_api(cusip=cusip)

        elif choice == "2":
            print(f"  Types: {', '.join(SECURITY_TYPES + ['all'])}")
            sec_type = input("  Type [all]: ").strip() or "all"
            days_str = input("  Days [365]: ").strip()
            days = int(days_str) if days_str else 365
            scraper.scrape_securities_api(security_type=sec_type, days=days)

        elif choice == "3":
            scraper.scrape_debt_api(current_only=True)

        elif choice == "4":
            start = input("  Start date (YYYY-MM-DD) [2000-01-01]: ").strip() or "2000-01-01"
            end = input("  End date (YYYY-MM-DD) [today]: ").strip()
            if not end:
                end = datetime.now().strftime("%Y-%m-%d")
            scraper.scrape_debt_api(start_date=start, end_date=end)

        elif choice == "5":
            print(f"  Types: {', '.join(SECURITY_TYPES + ['all'])}")
            sec_type = input("  Type [all]: ").strip() or "all"
            scraper.scrape_securities_api(security_type=sec_type, full_history=True)

        elif choice == "6":
            print(f"  Types: {', '.join(SECURITY_TYPES + ['all'])}")
            sec_type = input("  Type [all]: ").strip() or "all"
            scraper.scrape_securities_api(security_type=sec_type, full_history=True,
                                          download_pdfs=True)

        elif choice == "7":
            scraper.scrape_debt_api()

        elif choice == "8":
            scraper.scrape_reports()

        elif choice == "9":
            scraper.scrape_forms()

        elif choice == "10":
            scraper.scrape_xml_data()

        elif choice == "11":
            scraper.scrape_rss_feeds()

        elif choice == "12":
            pages_str = input("  Max pages to crawl [500]: ").strip()
            max_pages = int(pages_str) if pages_str else 500
            scraper.scrape_crawl(max_pages=max_pages)

        elif choice == "13":
            scraper.run_all(full_history=True)

        elif choice == "14":
            scraper.scrape_buybacks()

        elif choice == "15":
            scraper.scrape_buybacks(operation_type="Liquidity Support")

        elif choice == "16":
            scraper.scrape_buybacks(operation_type="Cash Management")

        else:
            print("  Invalid option.")
            continue

        scraper._print_summary(0)
        print()
        again = input("Run another? (y/n): ").strip().lower()
        if again != "y":
            break


# ── Non-interactive CLI ──────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="treasurydirect_scraper",
        description="Comprehensive scraper for TreasuryDirect.gov",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
API (quick lookups):
  python treasurydirect_scraper.py api cusip 91282CQJ3              # single CUSIP
  python treasurydirect_scraper.py api auctions --type Bill --days 30  # recent Bills
  python treasurydirect_scraper.py api auctions --days 7             # all types, 7 days
  python treasurydirect_scraper.py api debt                          # current debt
  python treasurydirect_scraper.py api debt --start 2024-01-01       # debt date range

JOBS (bulk downloads):
  python treasurydirect_scraper.py job history                       # all auctions since 1997
  python treasurydirect_scraper.py job history --type Note           # just Notes
  python treasurydirect_scraper.py job history --download-pdfs       # + result PDFs
  python treasurydirect_scraper.py job debt                          # full debt 2000-present
  python treasurydirect_scraper.py job reports                       # reports & publications
  python treasurydirect_scraper.py job forms                         # all PDF forms
  python treasurydirect_scraper.py job xml                           # XML auction files
  python treasurydirect_scraper.py job rss                           # RSS/XML feeds
  python treasurydirect_scraper.py job crawl --max-pages 1000        # full site crawl
  python treasurydirect_scraper.py job all                           # everything
        """,
    )

    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT_DIR,
                        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")

    sub = parser.add_subparsers(dest="mode")

    # ── api ──────────────────────────────────────────────────────────────
    api = sub.add_parser("api", help="Quick lookups (CUSIP, recent auctions, current debt)")
    api_sub = api.add_subparsers(dest="api_command")

    api_cusip = api_sub.add_parser("cusip", help="Look up a single CUSIP")
    api_cusip.add_argument("value", type=str, help="CUSIP to look up")

    api_auctions = api_sub.add_parser("auctions", help="Recent auctions")
    api_auctions.add_argument("--type", choices=SECURITY_TYPES + ["all"], default="all",
                              help="Security type (default: all)")
    api_auctions.add_argument("--days", type=int, default=365, help="Days of history (default: 365)")

    api_debt = api_sub.add_parser("debt", help="Debt to the penny")
    api_debt.add_argument("--start", type=str, help="Start date YYYY-MM-DD (omit for current only)")
    api_debt.add_argument("--end", type=str, help="End date YYYY-MM-DD (default: today)")

    api_bb = api_sub.add_parser("buybacks", help="Treasury buyback operations")
    api_bb.add_argument("--type", choices=["Cash Management", "Liquidity Support"],
                        help="Operation type filter")
    api_bb.add_argument("--from-date", type=str, help="From date YYYY-MM-DD")
    api_bb.add_argument("--to-date", type=str, help="To date YYYY-MM-DD")
    api_bb.add_argument("--results-only", action="store_true",
                        help="Only operations with results")

    # ── job ──────────────────────────────────────────────────────────────
    job = sub.add_parser("job", help="Bulk downloads (full history, reports, crawl)")
    job_sub = job.add_subparsers(dest="job_command")

    job_history = job_sub.add_parser("history", help="Full auction history since 1997")
    job_history.add_argument("--type", choices=SECURITY_TYPES + ["all"], default="all",
                             help="Security type (default: all)")
    job_history.add_argument("--download-pdfs", action="store_true",
                             help="Also download announcement & result PDFs")

    job_sub.add_parser("debt", help="Full historical debt (2000-present)")
    job_sub.add_parser("reports", help="Reports & publications")
    job_sub.add_parser("forms", help="All PDF forms")
    job_sub.add_parser("xml", help="XML auction data directory")
    job_sub.add_parser("rss", help="RSS / XML feeds")

    job_crawl = job_sub.add_parser("crawl", help="Full site crawl")
    job_crawl.add_argument("--max-pages", type=int, default=500,
                           help="Max pages to crawl (default: 500)")

    job_bb = job_sub.add_parser("buybacks", help="Full buyback operations history")
    job_bb.add_argument("--type", choices=["Cash Management", "Liquidity Support"],
                        help="Operation type filter")
    job_bb.add_argument("--results-only", action="store_true",
                        help="Only operations with results")

    job_sub.add_parser("all", help="Run ALL jobs")

    return parser


def main():
    if len(sys.argv) == 1:
        interactive_menu()
        return

    parser = build_parser()
    args = parser.parse_args()

    if not args.mode:
        interactive_menu()
        return

    verbose = not args.quiet
    scraper = TreasuryDirectScraper(output_dir=args.output, verbose=verbose)
    start_time = time()

    if args.mode == "api":
        if args.api_command == "cusip":
            scraper.scrape_securities_api(cusip=args.value)
        elif args.api_command == "auctions":
            scraper.scrape_securities_api(security_type=args.type, days=args.days)
        elif args.api_command == "debt":
            if args.start:
                scraper.scrape_debt_api(start_date=args.start, end_date=args.end)
            else:
                scraper.scrape_debt_api(current_only=True)
        elif args.api_command == "buybacks":
            scraper.scrape_buybacks(
                from_date=getattr(args, "from_date", None),
                to_date=getattr(args, "to_date", None),
                operation_type=getattr(args, "type", None),
                results_only=getattr(args, "results_only", False),
            )
        else:
            parser.parse_args(["api", "--help"])

    elif args.mode == "job":
        if args.job_command == "history":
            scraper.scrape_securities_api(security_type=args.type, full_history=True,
                                          download_pdfs=args.download_pdfs)
        elif args.job_command == "debt":
            scraper.scrape_debt_api()
        elif args.job_command == "reports":
            scraper.scrape_reports()
        elif args.job_command == "forms":
            scraper.scrape_forms()
        elif args.job_command == "xml":
            scraper.scrape_xml_data()
        elif args.job_command == "rss":
            scraper.scrape_rss_feeds()
        elif args.job_command == "crawl":
            scraper.scrape_crawl(max_pages=args.max_pages)
        elif args.job_command == "buybacks":
            scraper.scrape_buybacks(
                operation_type=getattr(args, "type", None),
                results_only=getattr(args, "results_only", False),
            )
        elif args.job_command == "all":
            scraper.run_all(full_history=True)
        else:
            parser.parse_args(["job", "--help"])

    scraper._print_summary(time() - start_time)


if __name__ == "__main__":
    main()
