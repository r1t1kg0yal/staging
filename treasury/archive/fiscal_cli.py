#!/usr/bin/env python3
"""
Fiscal Data API CLI.

Interactive mode (run with no args): nested menus for CUSIPs, auction schedules,
debt, interest rates, and arbitrary endpoint queries.

Non-interactive mode: use subcommands and flags for scripting.
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure fiscal_api is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fiscal_api import (
    FiscalDataClient,
    ENDPOINT_REGISTRY,
    get_endpoint_info,
    get_cusips,
    get_unique_cusips,
    get_upcoming_auctions,
    get_record_setting_auctions,
    get_debt_to_penny,
    get_avg_interest_rates,
    get_rates_of_exchange,
)
from fiscal_api.endpoints import CATEGORIES, list_endpoints_by_category


def _progress(page: int, total: int, rows: int) -> None:
    print(f"  Page {page}/{total} | {rows} rows fetched...", flush=True)


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


def menu_cusips() -> None:
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


def menu_auctions() -> None:
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


def menu_debt() -> None:
    print("\n--- Debt ---")
    print("1. Debt to the Penny (recent)")
    print("2. Debt to the Penny (date range)")
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


def menu_interest_rates() -> None:
    print("\n--- Interest Rates ---")
    print("1. Average interest rates (recent)")
    print("2. Rates of exchange")
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


def menu_endpoints() -> None:
    print("\n--- Endpoint Registry ---")
    print("1. List by category")
    print("2. Query arbitrary endpoint")
    print("0. Back")
    choice = input("Choice: ").strip()
    if choice == "0":
        return
    if choice == "1":
        for cat_id, desc in CATEGORIES.items():
            eps = list_endpoints_by_category(cat_id)
            print(f"\n{cat_id}: {desc}")
            for e in eps[:5]:
                print(f"  - {e['endpoint']} ({e['table_name']})")
    elif choice == "2":
        key = input("Endpoint key (e.g. upcoming_auctions, debt_to_penny): ").strip()
        info = get_endpoint_info(key)
        if not info:
            print(f"Unknown key. Available: {list(ENDPOINT_REGISTRY.keys())[:15]}...")
            return
        client = FiscalDataClient()
        resp = client.get(info["endpoint"], page_size=5)
        print(f"Endpoint: {info['endpoint']}")
        print(f"Rows in this page: {len(resp.get('data', []))}")
        _print_table(resp.get("data", []))


def interactive_main() -> None:
    while True:
        print("\n=== Fiscal Data API ===")
        print("1. CUSIPs")
        print("2. Auction schedules")
        print("3. Debt")
        print("4. Interest rates / exchange rates")
        print("5. Endpoint registry / arbitrary query")
        print("0. Exit")
        choice = input("Choice: ").strip()
        if choice == "0":
            break
        if choice == "1":
            menu_cusips()
        elif choice == "2":
            menu_auctions()
        elif choice == "3":
            menu_debt()
        elif choice == "4":
            menu_interest_rates()
        elif choice == "5":
            menu_endpoints()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fiscal Data API CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fiscal_cli.py cusips
  python fiscal_cli.py cusips --security-type Bill
  python fiscal_cli.py auctions
  python fiscal_cli.py auctions --security-type Note
  python fiscal_cli.py debt --from-date 2024-01-01 --to-date 2024-12-31
  python fiscal_cli.py endpoints list
  python fiscal_cli.py endpoints get debt_to_penny --page-size 5
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # cusips
    p_cusips = subparsers.add_parser("cusips", help="Fetch CUSIPs from upcoming auctions")
    p_cusips.add_argument("--security-type", "-s", help="Filter by security type")
    p_cusips.add_argument("--from-date", help="Filter from date (YYYY-MM-DD)")
    p_cusips.add_argument("--to-date", help="Filter to date (YYYY-MM-DD)")
    p_cusips.add_argument("--unique", action="store_true", help="Output unique CUSIPs only")
    p_cusips.add_argument("--json", action="store_true", help="Output JSON")
    p_cusips.add_argument("--limit", type=int, default=100, help="Max rows (via max_pages)")

    # auctions
    p_auctions = subparsers.add_parser("auctions", help="Fetch auction schedules")
    p_auctions.add_argument("--security-type", "-s", help="Filter by security type")
    p_auctions.add_argument("--from-date", help="Auction date from (YYYY-MM-DD)")
    p_auctions.add_argument("--to-date", help="Auction date to (YYYY-MM-DD)")
    p_auctions.add_argument("--record-setting", action="store_true", help="Record-setting auctions")
    p_auctions.add_argument("--json", action="store_true", help="Output JSON")
    p_auctions.add_argument("--limit", type=int, default=100, help="Max rows")

    # debt
    p_debt = subparsers.add_parser("debt", help="Debt to the Penny")
    p_debt.add_argument("--from-date", help="From date (YYYY-MM-DD)")
    p_debt.add_argument("--to-date", help="To date (YYYY-MM-DD)")
    p_debt.add_argument("--json", action="store_true", help="Output JSON")
    p_debt.add_argument("--limit", type=int, default=100, help="Max rows")

    # interest-rates
    p_ir = subparsers.add_parser("interest-rates", help="Average interest rates")
    p_ir.add_argument("--security-type", "-s", help="Filter by security type")
    p_ir.add_argument("--from-date", help="From date")
    p_ir.add_argument("--to-date", help="To date")
    p_ir.add_argument("--json", action="store_true", help="Output JSON")
    p_ir.add_argument("--limit", type=int, default=100, help="Max rows")

    # exchange
    p_ex = subparsers.add_parser("exchange", help="Rates of exchange")
    p_ex.add_argument("--currencies", "-c", help="Comma-separated country-currency (e.g. Canada-Dollar,Mexico-Peso)")
    p_ex.add_argument("--from-date", help="From date")
    p_ex.add_argument("--to-date", help="To date")
    p_ex.add_argument("--json", action="store_true", help="Output JSON")
    p_ex.add_argument("--limit", type=int, default=100, help="Max rows")

    # endpoints
    p_ep = subparsers.add_parser("endpoints", help="Endpoint registry")
    p_ep.add_argument("action", choices=["list", "get"], nargs="?", help="list or get")
    p_ep.add_argument("key", nargs="?", help="Endpoint key for 'get'")
    p_ep.add_argument("--page-size", type=int, default=10, help="Page size for get")
    p_ep.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    if not args.command:
        interactive_main()
        return

    if args.command == "cusips":
        if args.unique:
            data = get_unique_cusips(
                security_type=args.security_type,
                from_date=args.from_date,
                to_date=args.to_date,
            )
            data = [{"cusip": c} for c in data]
        else:
            max_pages = max(1, args.limit // 100)
            data = get_cusips(
                security_type=args.security_type,
                from_date=args.from_date,
                to_date=args.to_date,
                max_pages=max_pages,
            )
        if args.json:
            _print_json(data)
        else:
            _print_table(data, limit=args.limit)

    elif args.command == "auctions":
        if args.record_setting:
            data = get_record_setting_auctions(security_type=args.security_type)
        else:
            max_pages = max(1, args.limit // 100)
            data = get_upcoming_auctions(
                security_type=args.security_type,
                from_date=args.from_date,
                to_date=args.to_date,
                max_pages=max_pages,
            )
        if args.json:
            _print_json(data)
        else:
            _print_table(data, limit=args.limit)

    elif args.command == "debt":
        max_pages = max(1, args.limit // 100)
        data = get_debt_to_penny(
            from_date=args.from_date,
            to_date=args.to_date,
            max_pages=max_pages,
        )
        if args.json:
            _print_json(data)
        else:
            _print_table(data, limit=args.limit)

    elif args.command == "interest-rates":
        max_pages = max(1, args.limit // 100)
        data = get_avg_interest_rates(
            security_type=args.security_type,
            from_date=args.from_date,
            to_date=args.to_date,
            max_pages=max_pages,
        )
        if args.json:
            _print_json(data)
        else:
            _print_table(data, limit=args.limit)

    elif args.command == "exchange":
        currencies = [x.strip() for x in args.currencies.split(",")] if args.currencies else None
        max_pages = max(1, args.limit // 100)
        data = get_rates_of_exchange(
            country_currency=currencies,
            from_date=args.from_date,
            to_date=args.to_date,
            max_pages=max_pages,
        )
        if args.json:
            _print_json(data)
        else:
            _print_table(data, limit=args.limit)

    elif args.command == "endpoints":
        if args.action == "list" or not args.action:
            for cat_id, desc in CATEGORIES.items():
                eps = list_endpoints_by_category(cat_id)
                print(f"\n{cat_id}: {desc}")
                for e in eps:
                    print(f"  {e['endpoint']} -> {e['table_name']}")
        elif args.action == "get":
            if not args.key:
                print("Error: endpoint key required for 'get'")
                sys.exit(1)
            info = get_endpoint_info(args.key)
            if not info:
                print(f"Unknown key: {args.key}")
                sys.exit(1)
            from fiscal_api.client import request
            resp = request(info["endpoint"], page_size=args.page_size)
            if args.json:
                _print_json(resp)
            else:
                _print_table(resp.get("data", []), limit=args.page_size)


if __name__ == "__main__":
    main()
