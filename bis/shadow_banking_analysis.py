#!/usr/bin/env python3
"""
Shadow Banking, Eurodollar System & Cross-Border Repo Analysis
==============================================================
Comprehensive analysis using BIS Locational Banking Statistics (LBS),
Global Liquidity Indicators (GLI), and Debt Securities data.

Covers:
  1. Eurodollar system: USD-denominated cross-border claims/liabilities
  2. Shadow banking: Non-bank financial sector cross-border exposures
  3. Repo/money market proxy: Loans & deposits vs debt securities by currency
  4. Offshore center intermediation: London, HK, SG, Caymans, Jersey
  5. Global dollar liquidity: USD credit to non-residents
  6. Currency mismatch: Foreign currency positions by reporting country
  7. Bank nationality vs location: Who owns the offshore dollar pipes
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    print("ERROR: 'requests' required. pip install requests")
    sys.exit(1)

BASE_URL = "https://stats.bis.org/api/v2"
DATA_HEADERS = {
    "Accept": "application/vnd.sdmx.data+json;version=1.0.0",
    "User-Agent": "BIS-ShadowBanking-Analysis/1.0",
}
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "shadow_banking"

MAJOR_REPORTERS = ["US", "GB", "JP", "DE", "FR", "CH", "HK", "SG", "CA", "AU", "NL", "IE", "LU"]
OFFSHORE_CENTERS = ["GB", "HK", "SG", "KY", "BS", "JE", "GG", "IM", "LU", "IE", "BH", "PA", "BM", "CW", "MO"]
KEY_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CHF"]

COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "JP": "Japan",
    "DE": "Germany", "FR": "France", "CH": "Switzerland",
    "HK": "Hong Kong", "SG": "Singapore", "CA": "Canada",
    "AU": "Australia", "NL": "Netherlands", "IE": "Ireland",
    "LU": "Luxembourg", "KY": "Cayman Islands", "BS": "Bahamas",
    "JE": "Jersey", "GG": "Guernsey", "IM": "Isle of Man",
    "BH": "Bahrain", "PA": "Panama", "BM": "Bermuda",
    "CW": "Curacao", "MO": "Macao", "CN": "China",
    "BR": "Brazil", "IN": "India", "KR": "Korea",
    "MX": "Mexico", "TR": "Turkey", "RU": "Russia",
    "ZA": "South Africa", "SE": "Sweden", "NO": "Norway",
    "IT": "Italy", "ES": "Spain", "BE": "Belgium",
    "AT": "Austria", "DK": "Denmark", "FI": "Finland",
    "PT": "Portugal", "GR": "Greece", "TW": "Chinese Taipei",
    "5A": "All reporters", "5C": "Euro area", "5J": "All countries",
}

query_count = 0
query_start_time = None


def cn(code):
    return COUNTRY_NAMES.get(code, code)


def data_query(dataflow, key, start_period="2000", end_period=None, max_retries=3):
    global query_count, query_start_time
    if query_start_time is None:
        query_start_time = time.time()
    query_count += 1

    url = f"{BASE_URL}/data/dataflow/BIS/{dataflow}/1.0/{key}"
    params = {"format": "sdmx-json", "detail": "full"}
    if start_period:
        params["startPeriod"] = start_period
    if end_period:
        params["endPeriod"] = end_period

    elapsed = time.time() - query_start_time
    print(f"  [{query_count:3d}] {dataflow}/{key[:60]:<60s} [{elapsed:.0f}s elapsed]")

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=DATA_HEADERS, params=params, timeout=120)
            if resp.status_code == 200:
                return _parse_sdmx(resp.json())
            elif resp.status_code == 404:
                return []
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"        Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"        HTTP {resp.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return []
        except requests.exceptions.Timeout:
            print(f"        Timeout, retry {attempt+1}/{max_retries}")
            time.sleep(3)
        except Exception as e:
            print(f"        Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return []
    return []


def _parse_sdmx(raw):
    datasets = raw.get("data", {}).get("dataSets", [])
    if not datasets:
        return []
    structure = raw.get("data", {}).get("structure", {})
    dim_defs = structure.get("dimensions", {}).get("series", [])
    obs_dim = structure.get("dimensions", {}).get("observation", [])
    attr_defs = structure.get("attributes", {}).get("series", [])

    time_values = []
    if obs_dim:
        time_values = [v.get("id", v.get("name", str(i)))
                       for i, v in enumerate(obs_dim[0].get("values", []))]

    series_list = []
    ds = datasets[0]
    for series_key_str, series_obj in ds.get("series", {}).items():
        key_indices = [int(k) for k in series_key_str.split(":")]
        dimensions = {}
        key_parts = []
        for i, dim_def in enumerate(dim_defs):
            idx = key_indices[i] if i < len(key_indices) else 0
            values = dim_def.get("values", [])
            if idx < len(values):
                val = values[idx]
                dimensions[dim_def.get("id", f"dim_{i}")] = {
                    "id": val.get("id", ""),
                    "name": val.get("name", ""),
                }
                key_parts.append(val.get("id", ""))
            else:
                key_parts.append("?")

        observations = {}
        for obs_key, obs_val in series_obj.get("observations", {}).items():
            obs_idx = int(obs_key)
            period = time_values[obs_idx] if obs_idx < len(time_values) else obs_key
            value = obs_val[0] if obs_val else None
            observations[period] = value

        series_list.append({
            "key": ".".join(key_parts),
            "dimensions": dimensions,
            "observations": observations,
        })
    return series_list


def latest_value(series_list):
    """Get the latest observation value from a list of series."""
    if not series_list:
        return None
    obs = series_list[0].get("observations", {})
    if not obs:
        return None
    latest_period = max(obs.keys())
    return to_num(obs[latest_period]), latest_period


def series_to_timeseries(series_list):
    """Convert series list to {label: {period: value}} dict."""
    result = {}
    for s in series_list:
        dims = s["dimensions"]
        label_parts = [v["name"] for v in dims.values() if v.get("name")]
        label = " | ".join(label_parts)
        result[label] = s["observations"]
    return result


def latest_values_table(series_list, label_dims=None):
    """Extract latest value per series, return list of (label, value, period)."""
    rows = []
    for s in series_list:
        dims = s["dimensions"]
        if label_dims:
            label = " | ".join(dims.get(d, {}).get("name", dims.get(d, {}).get("id", "?")) for d in label_dims)
        else:
            label = " | ".join(v["name"] for v in dims.values() if v.get("name"))
        obs = s.get("observations", {})
        if obs:
            latest_p = max(obs.keys())
            rows.append((label, to_num(obs[latest_p]), latest_p))
    return rows


def to_num(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def format_usd_bn(val):
    val = to_num(val)
    if val is None:
        return "N/A"
    return f"${val/1e3:,.0f}bn" if abs(val) >= 1000 else f"${val:,.0f}mn"


def print_section(title):
    width = 78
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_subsection(title):
    print(f"\n  --- {title} ---")


# ── Analysis Modules ──────────────────────────────────────────────────────────

def analyze_eurodollar_system(start="2000"):
    """
    Module 1: Eurodollar System
    USD-denominated cross-border claims and liabilities by major centers.
    This IS the offshore dollar market.
    """
    print_section("MODULE 1: EURODOLLAR SYSTEM -- USD Cross-Border Claims & Liabilities")
    results = {}

    # 1a. Aggregate USD cross-border claims/liabilities (all reporters)
    print_subsection("1a. Global USD cross-border positions (all reporters)")
    usd_claims = data_query("WS_LBS_D_PUB", f"Q.S.C.A.USD.A.5J.A.5A.A.5J.N", start)
    usd_liabs = data_query("WS_LBS_D_PUB", f"Q.S.L.A.USD.A.5J.A.5A.A.5J.N", start)
    results["global_usd_claims"] = usd_claims
    results["global_usd_liabs"] = usd_liabs

    for label, series in [("USD Claims", usd_claims), ("USD Liabilities", usd_liabs)]:
        lv = latest_value(series)
        if lv:
            print(f"    {label}: {format_usd_bn(lv[0])} (as of {lv[1]})")

    # 1b-1d. Foreign currency cross-border claims/liabilities by center
    # BIS doesn't publish per-reporter USD with aggregate counterparty.
    # Foreign currency (L_CURR_TYPE=F) captures eurodollar intermediation:
    # non-USD centers operating in FCY = mostly USD = the eurodollar system.
    print_subsection("1b. FOREIGN CURRENCY cross-border claims & liabilities BY CENTER")
    print("    (Foreign currency = proxy for eurodollar intermediation)")
    reporters_for_usd = ["GB", "JP", "FR", "DE", "CH", "HK", "SG", "CA", "AU",
                         "NL", "IE", "LU", "US", "KY"]
    claims_map = {}
    liabs_map = {}
    for rep in reporters_for_usd:
        c_series = data_query("WS_LBS_D_PUB", f"Q.S.C.A.TO1.F.5J.A.{rep}.A.5J.N", start)
        l_series = data_query("WS_LBS_D_PUB", f"Q.S.L.A.TO1.F.5J.A.{rep}.A.5J.N", start)
        c_val = latest_value(c_series)
        l_val = latest_value(l_series)
        claims_map[rep] = c_val[0] if c_val and c_val[0] else 0
        liabs_map[rep] = l_val[0] if l_val and l_val[0] else 0
        time.sleep(0.2)
    results["fcy_claims_by_reporter"] = claims_map
    results["fcy_liabs_by_reporter"] = liabs_map

    net_positions = []
    for rep in reporters_for_usd:
        c = claims_map.get(rep, 0)
        l = liabs_map.get(rep, 0)
        net_positions.append((rep, c, l, c - l))
    net_positions.sort(key=lambda x: -(x[1] or 0))

    print(f"    {'Center':<20s} {'FCY Claims':>12s} {'FCY Liabs':>12s} {'Net':>12s}  Role")
    print(f"    {'-'*20} {'-'*12} {'-'*12} {'-'*12}  {'-'*14}")
    for rep, c, l, n in net_positions:
        if c == 0 and l == 0:
            continue
        role = "FCY SUPPLIER" if n > 0 else "FCY BORROWER"
        print(f"    {cn(rep):<20s} {format_usd_bn(c):>12s} {format_usd_bn(l):>12s} {format_usd_bn(n):>12s}  {role}")

    # 1e. Currency comparison: USD vs EUR vs JPY vs GBP cross-border
    print_subsection("1e. Cross-border claims by currency denomination (all reporters)")
    for ccy in KEY_CURRENCIES:
        ccy_series = data_query("WS_LBS_D_PUB", f"Q.S.C.A.{ccy}.A.5J.A.5A.A.5J.N", start)
        lv = latest_value(ccy_series)
        if lv:
            print(f"    {ccy} claims: {format_usd_bn(lv[0])} ({lv[1]})")
        results[f"global_{ccy.lower()}_claims"] = ccy_series
        time.sleep(0.3)

    # 1f. Total cross-border (all currencies) for comparison
    all_ccy_claims = data_query("WS_LBS_D_PUB", f"Q.S.C.A.TO1.A.5J.A.5A.A.5J.N", start)
    lv = latest_value(all_ccy_claims)
    if lv:
        print(f"    ALL currencies claims: {format_usd_bn(lv[0])} ({lv[1]})")
    results["global_all_ccy_claims"] = all_ccy_claims

    # 1g. Growth rates in USD cross-border claims
    print_subsection("1f. Annual growth in USD cross-border claims (all reporters)")
    usd_growth = data_query("WS_LBS_D_PUB", f"Q.G.C.A.USD.A.5J.A.5A.A.5J.N", start)
    results["usd_claims_growth"] = usd_growth
    if usd_growth:
        obs = usd_growth[0].get("observations", {})
        recent = sorted(obs.keys())[-8:]
        print(f"    Recent quarters:")
        for p in recent:
            v = to_num(obs[p])
            print(f"      {p}: {v:.1f}%" if v is not None else f"      {p}: N/A")

    return results


def analyze_shadow_banking(start="2000"):
    """
    Module 2: Shadow Banking / Non-Bank Financial Intermediation
    Cross-border claims on non-bank financial institutions vs banks vs non-financial.
    """
    print_section("MODULE 2: SHADOW BANKING -- Non-Bank Financial Sector Cross-Border")
    results = {}

    # 2a. All reporters: claims on banks vs non-bank financial vs non-financial corps
    print_subsection("2a. Cross-border claims by counterparty sector (all reporters, all ccy)")
    sectors = {
        "B": "Banks",
        "F": "Non-bank financial",
        "N": "Non-banks total",
        "C": "Non-financial corps",
        "G": "General govt",
        "H": "Households",
    }
    for sector_code, sector_name in sectors.items():
        s = data_query("WS_LBS_D_PUB", f"Q.S.C.A.TO1.A.5J.A.5A.{sector_code}.5J.N", start)
        lv = latest_value(s)
        if lv:
            print(f"    {sector_name:<25s}: {format_usd_bn(lv[0])} ({lv[1]})")
        results[f"sector_{sector_code}"] = s
        time.sleep(0.3)

    # 2b. Non-bank financial claims in USD specifically
    print_subsection("2b. USD-denominated claims on non-bank financial sector")
    nbfi_usd = data_query("WS_LBS_D_PUB", f"Q.S.C.A.USD.A.5J.A.5A.F.5J.N", start)
    lv = latest_value(nbfi_usd)
    if lv:
        print(f"    USD claims on NBFI (all reporters): {format_usd_bn(lv[0])} ({lv[1]})")
    results["nbfi_usd_global"] = nbfi_usd

    # 2c. NBFI claims by major reporting center
    print_subsection("2c. Non-bank financial claims by reporting center")
    reporters_str = "+".join(MAJOR_REPORTERS)
    nbfi_by_reporter = data_query(
        "WS_LBS_D_PUB",
        f"Q.S.C.A.TO1.A.5J.A.{reporters_str}.F.5J.N",
        start
    )
    results["nbfi_by_reporter"] = nbfi_by_reporter

    rows = latest_values_table(nbfi_by_reporter, label_dims=["L_REP_CTY"])
    rows.sort(key=lambda x: -(x[1] or 0))
    print(f"    {'Reporter':<25s} {'NBFI Claims':>15s}  Period")
    print(f"    {'-'*25} {'-'*15}  {'-'*7}")
    for label, val, period in rows[:15]:
        print(f"    {label:<25s} {format_usd_bn(val):>15s}  {period}")

    # 2d. Non-bank financial LIABILITIES (funding side)
    print_subsection("2d. Non-bank financial sector: liabilities (funding to NBFI)")
    nbfi_liabs = data_query(
        "WS_LBS_D_PUB",
        f"Q.S.L.A.TO1.A.5J.A.{reporters_str}.F.5J.N",
        start
    )
    results["nbfi_liabs_by_reporter"] = nbfi_liabs

    rows = latest_values_table(nbfi_liabs, label_dims=["L_REP_CTY"])
    rows.sort(key=lambda x: -(x[1] or 0))
    print(f"    {'Reporter':<25s} {'NBFI Liabilities':>15s}")
    print(f"    {'-'*25} {'-'*15}")
    for label, val, period in rows[:15]:
        print(f"    {label:<25s} {format_usd_bn(val):>15s}")

    # 2e. Growth in NBFI cross-border claims
    print_subsection("2e. Annual growth in cross-border claims on NBFI")
    nbfi_growth = data_query("WS_LBS_D_PUB", f"Q.G.C.A.TO1.A.5J.A.5A.F.5J.N", start)
    results["nbfi_growth"] = nbfi_growth
    if nbfi_growth:
        obs = nbfi_growth[0].get("observations", {})
        recent = sorted(obs.keys())[-8:]
        for p in recent:
            v = to_num(obs[p])
            print(f"      {p}: {v:.1f}%" if v is not None else f"      {p}: N/A")

    return results


def analyze_repo_money_market(start="2000"):
    """
    Module 3: Repo / Money Market Proxy
    Loans & deposits vs debt securities -- instrument decomposition.
    Short-term lending = proxy for repo/money market activity.
    """
    print_section("MODULE 3: REPO / MONEY MARKET PROXY -- Instrument Decomposition")
    results = {}

    # 3a. Global: Loans & deposits vs debt securities vs derivatives (all ccy)
    print_subsection("3a. Global cross-border claims by instrument")
    instruments = {
        "A": "All instruments",
        "G": "Loans & deposits",
        "D": "Debt securities",
        "V": "Derivatives",
        "B": "Credit (loans+debt)",
    }
    for instr_code, instr_name in instruments.items():
        s = data_query("WS_LBS_D_PUB", f"Q.S.C.{instr_code}.TO1.A.5J.A.5A.A.5J.N", start)
        lv = latest_value(s)
        if lv:
            print(f"    {instr_name:<25s}: {format_usd_bn(lv[0])} ({lv[1]})")
        results[f"instr_{instr_code}"] = s
        time.sleep(0.3)

    # 3b. USD-denominated loans & deposits (interbank = repo/money market proxy)
    print_subsection("3b. USD loans & deposits to BANKS (interbank/repo proxy)")
    usd_loans_banks = data_query("WS_LBS_D_PUB", f"Q.S.C.G.USD.A.5J.A.5A.B.5J.N", start)
    lv = latest_value(usd_loans_banks)
    if lv:
        print(f"    USD interbank loans+deposits (all reporters): {format_usd_bn(lv[0])} ({lv[1]})")
    results["usd_interbank_loans"] = usd_loans_banks

    # 3c. USD loans & deposits to non-banks
    usd_loans_nonbanks = data_query("WS_LBS_D_PUB", f"Q.S.C.G.USD.A.5J.A.5A.N.5J.N", start)
    lv = latest_value(usd_loans_nonbanks)
    if lv:
        print(f"    USD non-bank loans+deposits: {format_usd_bn(lv[0])} ({lv[1]})")
    results["usd_nonbank_loans"] = usd_loans_nonbanks

    # 3d. Interbank loans by reporting center
    print_subsection("3c. USD interbank loans & deposits by reporting center")
    interbank_reporters = ["US", "GB", "JP", "FR", "DE", "CH", "HK", "SG", "CA", "KY"]
    interbank_rows = []
    for rep in interbank_reporters:
        s = data_query("WS_LBS_D_PUB", f"Q.S.C.G.USD.A.5J.A.{rep}.B.5J.N", start)
        lv = latest_value(s)
        if lv and lv[0]:
            interbank_rows.append((cn(rep), lv[0], lv[1]))
        time.sleep(0.2)
    interbank_rows.sort(key=lambda x: -(x[1] or 0))
    results["usd_interbank_by_reporter"] = interbank_rows
    print(f"    {'Center':<25s} {'USD Interbank':>15s}")
    print(f"    {'-'*25} {'-'*15}")
    for label, val, period in interbank_rows:
        print(f"    {label:<25s} {format_usd_bn(val):>15s}")

    # 3e. Debt securities cross-border by currency
    print_subsection("3d. Cross-border debt securities holdings by currency")
    for ccy in ["USD", "EUR", "GBP", "JPY"]:
        s = data_query("WS_LBS_D_PUB", f"Q.S.C.D.{ccy}.A.5J.A.5A.A.5J.N", start)
        lv = latest_value(s)
        if lv:
            print(f"    {ccy} debt securities: {format_usd_bn(lv[0])} ({lv[1]})")
        results[f"debt_sec_{ccy.lower()}"] = s
        time.sleep(0.3)

    # 3f. Intra-group (related offices) positions -- proxy for internal liquidity transfer
    print_subsection("3e. Intra-group (related offices) positions")
    intragroup_claims = data_query("WS_LBS_D_PUB", f"Q.S.C.A.USD.A.5J.A.5A.I.5J.N", start)
    intragroup_liabs = data_query("WS_LBS_D_PUB", f"Q.S.L.A.USD.A.5J.A.5A.I.5J.N", start)
    for label, series in [("USD intra-group claims", intragroup_claims),
                          ("USD intra-group liabilities", intragroup_liabs)]:
        lv = latest_value(series)
        if lv:
            print(f"    {label}: {format_usd_bn(lv[0])} ({lv[1]})")
    results["intragroup_usd_claims"] = intragroup_claims
    results["intragroup_usd_liabs"] = intragroup_liabs

    return results


def analyze_offshore_centers(start="2000"):
    """
    Module 4: Offshore Center Intermediation
    How London, HK, Singapore, Caymans serve as USD intermediation nodes.
    """
    print_section("MODULE 4: OFFSHORE CENTER INTERMEDIATION")
    results = {}

    centers = ["GB", "HK", "SG", "KY", "JP", "CH", "LU", "IE"]

    # 4a. Each center: total cross-border claims and liabilities (all ccy)
    print_subsection("4a. Total cross-border positions by offshore center")
    print(f"    {'Center':<20s} {'Claims':>12s} {'Liabilities':>12s} {'Net':>12s}")
    print(f"    {'-'*20} {'-'*12} {'-'*12} {'-'*12}")

    for center in centers:
        claims = data_query("WS_LBS_D_PUB", f"Q.S.C.A.TO1.A.5J.A.{center}.A.5J.N", start)
        liabs = data_query("WS_LBS_D_PUB", f"Q.S.L.A.TO1.A.5J.A.{center}.A.5J.N", start)
        c_val = latest_value(claims)
        l_val = latest_value(liabs)
        c = (c_val[0] if c_val else 0) or 0
        l = (l_val[0] if l_val else 0) or 0
        n = float(c) - float(l)
        print(f"    {cn(center):<20s} {format_usd_bn(c):>12s} {format_usd_bn(l):>12s} {format_usd_bn(n):>12s}")
        results[f"{center}_total"] = {"claims": claims, "liabilities": liabs}
        time.sleep(0.3)

    # 4b. Foreign branches vs domestic banks in key centers
    print_subsection("4b. Foreign branches vs domestic banks (USD claims)")
    print(f"    {'Center':<20s} {'Domestic':>12s} {'Foreign Br':>12s} {'Foreign Sub':>12s}")
    print(f"    {'-'*20} {'-'*12} {'-'*12} {'-'*12}")
    for center in ["GB", "HK", "SG", "US", "JP"]:
        dom = data_query("WS_LBS_D_PUB", f"Q.S.C.A.USD.A.5J.D.{center}.A.5J.N", start)
        fbr = data_query("WS_LBS_D_PUB", f"Q.S.C.A.USD.A.5J.B.{center}.A.5J.N", start)
        fsub = data_query("WS_LBS_D_PUB", f"Q.S.C.A.USD.A.5J.S.{center}.A.5J.N", start)
        d_val = latest_value(dom)
        b_val = latest_value(fbr)
        s_val = latest_value(fsub)
        d_v = d_val[0] if d_val else 0
        b_v = b_val[0] if b_val else 0
        s_v = s_val[0] if s_val else 0
        print(f"    {cn(center):<20s} {format_usd_bn(d_v):>12s} "
              f"{format_usd_bn(b_v):>12s} "
              f"{format_usd_bn(s_v):>12s}")
        results[f"{center}_bank_types"] = {"domestic": dom, "foreign_branch": fbr, "foreign_sub": fsub}
        time.sleep(0.3)

    # 4c. Bank nationality: who owns the USD pipes through London?
    print_subsection("4c. Bank nationality in London (USD claims by parent country)")
    nationalities = ["US", "JP", "DE", "FR", "CH", "CN"]
    for nat in nationalities:
        s = data_query("WS_LBS_D_PUB", f"Q.S.C.A.USD.A.{nat}.A.GB.A.5J.N", start)
        lv = latest_value(s)
        if lv:
            print(f"    {cn(nat)}-parented banks in London, USD claims: {format_usd_bn(lv[0])} ({lv[1]})")
        results[f"london_nat_{nat}"] = s
        time.sleep(0.3)

    return results


def analyze_global_dollar_liquidity(start="2000"):
    """
    Module 5: Global Dollar Liquidity
    BIS Global Liquidity Indicators -- USD credit to non-bank borrowers outside US.
    """
    print_section("MODULE 5: GLOBAL DOLLAR LIQUIDITY (GLI)")
    results = {}

    # 5a. USD credit to non-banks outside US: bank loans vs debt securities
    print_subsection("5a. USD credit to non-bank borrowers outside US")
    gli_usd_all = data_query("WS_GLI", f"Q.USD.5J.N.A.I.B.USD", start)
    gli_usd_loans = data_query("WS_GLI", f"Q.USD.5J.N.A.I.G.USD", start)
    gli_usd_debt = data_query("WS_GLI", f"Q.USD.5J.N.A.I.D.USD", start)

    for label, s in [("Total USD credit", gli_usd_all),
                     ("  Bank loans", gli_usd_loans),
                     ("  Debt securities", gli_usd_debt)]:
        lv = latest_value(s)
        if lv:
            print(f"    {label}: {format_usd_bn(lv[0])} ({lv[1]})")
    results["gli_usd_total"] = gli_usd_all
    results["gli_usd_loans"] = gli_usd_loans
    results["gli_usd_debt"] = gli_usd_debt

    # 5b. EUR credit to non-banks outside Euro area
    print_subsection("5b. EUR credit to non-banks outside Euro area")
    gli_eur = data_query("WS_GLI", f"Q.EUR.5J.N.A.I.B.USD", start)
    lv = latest_value(gli_eur)
    if lv:
        print(f"    Total EUR credit (in USD): {format_usd_bn(lv[0])} ({lv[1]})")
    results["gli_eur_total"] = gli_eur

    # 5c. Growth in global USD credit
    print_subsection("5c. Growth trajectory")
    if gli_usd_all:
        obs = gli_usd_all[0].get("observations", {})
        sorted_periods = sorted(obs.keys())
        recent_16 = sorted_periods[-16:]
        print(f"    Recent USD credit to non-US non-banks:")
        for p in recent_16:
            v = to_num(obs.get(p))
            print(f"      {p}: {format_usd_bn(v)}" if v is not None else f"      {p}: N/A")

    return results


def analyze_currency_mismatch(start="2000"):
    """
    Module 6: Currency Mismatch / Foreign Currency Exposure
    Foreign currency positions by reporting country -- vulnerability indicator.
    """
    print_section("MODULE 6: CURRENCY MISMATCH -- Foreign Currency Positions")
    results = {}

    # 6a. Foreign currency claims vs domestic currency claims
    print_subsection("6a. Domestic vs foreign currency cross-border claims by center")
    reporters = ["US", "GB", "JP", "DE", "FR", "CH", "AU", "CA"]
    print(f"    {'Center':<20s} {'All CCY':>12s} {'Domestic':>12s} {'Foreign':>12s} {'FCY %':>8s}")
    print(f"    {'-'*20} {'-'*12} {'-'*12} {'-'*12} {'-'*8}")
    for rep in reporters:
        all_ccy = data_query("WS_LBS_D_PUB", f"Q.S.C.A.TO1.A.5J.A.{rep}.A.5J.N", start)
        dom_ccy = data_query("WS_LBS_D_PUB", f"Q.S.C.A.TO1.D.5J.A.{rep}.A.5J.N", start)
        fgn_ccy = data_query("WS_LBS_D_PUB", f"Q.S.C.A.TO1.F.5J.A.{rep}.A.5J.N", start)

        a_val = latest_value(all_ccy)
        d_val = latest_value(dom_ccy)
        f_val = latest_value(fgn_ccy)
        a = (a_val[0] if a_val else 0) or 0
        d = (d_val[0] if d_val else 0) or 0
        f = (f_val[0] if f_val else 0) or 0
        pct = f"{float(f)/float(a)*100:.0f}%" if a and f else "N/A"
        print(f"    {cn(rep):<20s} {format_usd_bn(a):>12s} {format_usd_bn(d):>12s} {format_usd_bn(f):>12s} {pct:>8s}")
        results[f"{rep}_ccy_split"] = {"all": all_ccy, "domestic": dom_ccy, "foreign": fgn_ccy}
        time.sleep(0.3)

    return results


def analyze_debt_securities(start="2000"):
    """
    Module 7: International Debt Securities
    Cross-border debt issuance -- the bond market leg of shadow banking.
    """
    print_section("MODULE 7: INTERNATIONAL DEBT SECURITIES")
    results = {}

    # 7a. International debt outstanding by major countries
    print_subsection("7a. International debt securities outstanding")
    intl_debt = data_query(
        "WS_DEBT_SEC2_PUB",
        f"Q.5J.5J.A.A.C.A.A.A.A.A.A.A.A.I",
        start
    )
    lv = latest_value(intl_debt)
    if lv:
        print(f"    Global international debt outstanding: {format_usd_bn(lv[0])} ({lv[1]})")
    results["intl_debt_global"] = intl_debt

    # 7b. By issuer residence (major countries)
    print_subsection("7b. International debt by issuer residence")
    countries = ["US", "GB", "DE", "FR", "JP", "CN", "CA", "AU", "NL", "IE", "LU", "KY"]
    for cty in countries:
        s = data_query(
            "WS_DEBT_SEC2_PUB",
            f"Q.{cty}..A.A.C.A.A.A.A.A.A.A.A.I",
            start
        )
        lv = latest_value(s)
        if lv:
            print(f"    {cn(cty):<20s}: {format_usd_bn(lv[0])}")
        results[f"intl_debt_{cty}"] = s
        time.sleep(0.3)

    return results


def run_full_analysis(start="2000", modules=None):
    """Run all analysis modules."""
    global query_count, query_start_time
    query_count = 0
    query_start_time = time.time()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")

    print("\n" + "#" * 78)
    print("#" + " " * 76 + "#")
    print("#   SHADOW BANKING, EURODOLLAR SYSTEM & CROSS-BORDER REPO ANALYSIS" + " " * 9 + "#")
    print("#   Data Source: BIS Locational Banking Statistics + Global Liquidity" + " " * 7 + "#")
    print(f"#   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}" + " " * 42 + "#")
    print("#" + " " * 76 + "#")
    print("#" * 78)

    all_modules = {
        "eurodollar": ("Eurodollar System", analyze_eurodollar_system),
        "shadow": ("Shadow Banking", analyze_shadow_banking),
        "repo": ("Repo/Money Market", analyze_repo_money_market),
        "offshore": ("Offshore Centers", analyze_offshore_centers),
        "liquidity": ("Global Dollar Liquidity", analyze_global_dollar_liquidity),
        "mismatch": ("Currency Mismatch", analyze_currency_mismatch),
        "debt": ("Debt Securities", analyze_debt_securities),
    }

    if modules:
        selected = {k: v for k, v in all_modules.items() if k in modules}
    else:
        selected = all_modules

    all_results = {}
    for key, (name, func) in selected.items():
        print(f"\n\n  Starting {name}...")
        try:
            all_results[key] = func(start)
        except Exception as e:
            print(f"  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            all_results[key] = {"error": str(e)}

    # Save raw results
    output_path = OUTPUT_DIR / f"shadow_banking_analysis_{ts}.json"
    serializable = {}
    for mod_key, mod_data in all_results.items():
        serializable[mod_key] = {}
        if isinstance(mod_data, dict):
            for k, v in mod_data.items():
                if isinstance(v, list):
                    serializable[mod_key][k] = v
                elif isinstance(v, dict):
                    inner = {}
                    for ik, iv in v.items():
                        inner[ik] = iv if isinstance(iv, list) else iv
                    serializable[mod_key][k] = inner

    with open(output_path, "w") as f:
        json.dump(serializable, f, indent=2, default=str)

    total_time = time.time() - query_start_time
    print(f"\n\n{'='*78}")
    print(f"  ANALYSIS COMPLETE")
    print(f"  Total API queries: {query_count}")
    print(f"  Total time: {total_time:.0f}s ({total_time/60:.1f}min)")
    print(f"  Raw data saved: {output_path}")
    print(f"{'='*78}\n")

    return all_results


# ── CLI ───────────────────────────────────────────────────────────────────────

def interactive_menu():
    while True:
        print("\n" + "=" * 60)
        print("  Shadow Banking & Eurodollar Analysis")
        print("=" * 60)
        print()
        print("  Full Analysis")
        print("    1) Run ALL modules (comprehensive)")
        print()
        print("  Individual Modules")
        print("    2) Eurodollar system (USD cross-border)")
        print("    3) Shadow banking (non-bank financial sector)")
        print("    4) Repo / money market proxy (instruments)")
        print("    5) Offshore center intermediation")
        print("    6) Global dollar liquidity (GLI)")
        print("    7) Currency mismatch / foreign currency")
        print("    8) International debt securities")
        print()
        print("  Custom")
        print("    9) Select multiple modules")
        print()
        print("    q) Quit")
        print()
        choice = input("Select: ").strip().lower()

        if choice == "q":
            break

        start = input("  Start period [2000]: ").strip() or "2000"

        if choice == "1":
            run_full_analysis(start=start)
        elif choice == "2":
            analyze_eurodollar_system(start)
        elif choice == "3":
            analyze_shadow_banking(start)
        elif choice == "4":
            analyze_repo_money_market(start)
        elif choice == "5":
            analyze_offshore_centers(start)
        elif choice == "6":
            analyze_global_dollar_liquidity(start)
        elif choice == "7":
            analyze_currency_mismatch(start)
        elif choice == "8":
            analyze_debt_securities(start)
        elif choice == "9":
            print("  Available modules: eurodollar, shadow, repo, offshore, liquidity, mismatch, debt")
            mods = input("  Select (comma-separated): ").strip()
            mod_list = [m.strip() for m in mods.split(",") if m.strip()]
            run_full_analysis(start=start, modules=mod_list)
        else:
            print("  Invalid choice.")


def main():
    parser = argparse.ArgumentParser(
        description="Shadow Banking, Eurodollar System & Cross-Border Repo Analysis (BIS data)"
    )
    subparsers = parser.add_subparsers(dest="command")

    full_p = subparsers.add_parser("full", help="Run all analysis modules")
    full_p.add_argument("--start", default="2000", help="Start period")

    for mod_key, mod_name in [
        ("eurodollar", "Eurodollar system analysis"),
        ("shadow", "Shadow banking / NBFI analysis"),
        ("repo", "Repo / money market proxy"),
        ("offshore", "Offshore center intermediation"),
        ("liquidity", "Global dollar liquidity"),
        ("mismatch", "Currency mismatch analysis"),
        ("debt", "International debt securities"),
    ]:
        p = subparsers.add_parser(mod_key, help=mod_name)
        p.add_argument("--start", default="2000", help="Start period")

    args = parser.parse_args()

    if args.command == "full":
        run_full_analysis(start=args.start)
    elif args.command == "eurodollar":
        analyze_eurodollar_system(args.start)
    elif args.command == "shadow":
        analyze_shadow_banking(args.start)
    elif args.command == "repo":
        analyze_repo_money_market(args.start)
    elif args.command == "offshore":
        analyze_offshore_centers(args.start)
    elif args.command == "liquidity":
        analyze_global_dollar_liquidity(args.start)
    elif args.command == "mismatch":
        analyze_currency_mismatch(args.start)
    elif args.command == "debt":
        analyze_debt_securities(args.start)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
