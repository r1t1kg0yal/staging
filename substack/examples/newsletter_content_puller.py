#!/usr/bin/env python3
"""
Newsletter Content Puller
=========================
Fetches recent posts for a publication, converts HTML bodies to plain text, and
exports structured excerpts. Includes publication search by keyword.

Usage:
    python newsletter_content_puller.py
    python newsletter_content_puller.py run apricitas --n 5 --export json
    python newsletter_content_puller.py search "macro" --limit 8 --json
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from substack import get_archive, get_post, html_to_text, search_publications

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))
PROGRESS_EVERY_S = 5.0


def _format_date(date_str):
    if not date_str:
        return "?"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return date_str[:10] if len(date_str) >= 10 else date_str


def _progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s elapsed)")
        last_print[0] = now


def _excerpt(text, max_chars=800):
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3] + "..."


def _normalize_search_results(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("publications") or raw.get("results") or []
    return []


def cmd_run(subdomain, n=6, excerpt_chars=800, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    print(f"\n  Pulling last {n} posts from '{subdomain}' ...")

    _progress("archive", t0, last)
    archive = get_archive(subdomain, limit=n) or []
    rows = []
    total = len(archive)

    for i, meta in enumerate(archive, 1):
        _progress(f"post {i}/{total}", t0, last)
        slug = meta.get("slug")
        title = meta.get("title", "(untitled)")
        post_date = _format_date(meta.get("post_date"))
        print(f"  [{i}/{total}] {post_date}  {title}  ({slug})", flush=True)
        text = ""
        if slug:
            try:
                full = get_post(subdomain, slug) or {}
                body = full.get("body_html") or ""
                text = html_to_text(body)
                if not text:
                    text = (full.get("truncated_body_text") or meta.get("truncated_body_text") or "").strip()
            except Exception as e:
                text = f"[fetch error: {e}]"
        else:
            text = (meta.get("truncated_body_text") or "").strip()

        excerpt = _excerpt(text, excerpt_chars)
        rows.append(
            {
                "title": title,
                "post_date": post_date,
                "slug": slug,
                "subdomain": subdomain,
                "text_excerpt": excerpt,
                "canonical_url": meta.get("canonical_url", ""),
            }
        )

    payload = {
        "generated_at": datetime.now().isoformat(),
        "subdomain": subdomain,
        "rows": rows,
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        for r in rows:
            print(f"\n  --- {r['post_date']} | {r['title']}")
            print(r["text_excerpt"])

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    if export_fmt:
        _export(payload, f"newsletter_pull_{subdomain}", export_fmt)
    return payload


def cmd_search(query, page=0, limit=10, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    print(f"\n  Searching publications for {query!r} ...")
    _progress("search request", t0, last)
    raw = search_publications(query, page=page, limit=limit)
    pubs = _normalize_search_results(raw)

    note = None
    if isinstance(raw, dict):
        note = raw.get("_note")

    payload = {
        "generated_at": datetime.now().isoformat(),
        "query": query,
        "page": page,
        "limit": limit,
        "publications": pubs,
        "raw_note": note,
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        if note:
            print(f"  Note: {note}")
        if not pubs:
            print("  No publications in response.")
        else:
            for i, p in enumerate(pubs, 1):
                name = p.get("name", "(unknown)")
                sub = p.get("subdomain", "?")
                print(f"  {i:2d}. {name}  ({sub}.substack.com)")

    elapsed = int(time.time() - t0)
    print(f"  Completed in {elapsed}s")
    if export_fmt:
        _export(payload, "newsletter_pub_search", export_fmt)
    return payload


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = data.get("rows") or data.get("publications") or []
        if rows and isinstance(rows[0], dict):
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        else:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["key", "value"])
                for k, v in data.items():
                    w.writerow([k, json.dumps(v, default=str)])
    print(f"  Exported: {path}")


MENU = """
  ============================================================
   Newsletter Content Puller (Substack)
  ============================================================

   1) run     Plain-text excerpts for recent N posts of a publication
   2) search  Search publications by keyword

   q) quit
"""


def _prompt(msg, default=None):
    suf = f" [{default}]" if default is not None else ""
    try:
        v = input(f"  {msg}{suf}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return v if v else (default if default is not None else "")


def interactive_loop():
    print(MENU)
    while True:
        try:
            c = input("\n  Command: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if c in ("q", "quit", "exit"):
            break
        if c in ("1", "run"):
            sub = _prompt("Subdomain")
            if not sub:
                continue
            n = _prompt("Number of posts", "6")
            nn = int(n) if str(n).isdigit() else 6
            ex = _prompt("Excerpt max chars", "800")
            ec = int(ex) if str(ex).isdigit() else 800
            cmd_run(sub, n=nn, excerpt_chars=ec)
        elif c in ("2", "search"):
            q = _prompt("Search query")
            if not q:
                continue
            lim = _prompt("Result limit", "10")
            ll = int(lim) if str(lim).isdigit() else 10
            cmd_search(q, limit=ll)
        else:
            print(f"  Unknown: {c}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="newsletter_content_puller.py",
        description="Pull Substack post bodies as plain text and search publications",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Recent posts with text excerpts for one publication")
    s.add_argument("subdomain", help="Publication subdomain")
    s.add_argument("-n", "--num", type=int, default=6, dest="n", help="Posts to fetch")
    s.add_argument("--excerpt-chars", type=int, default=800, help="Max excerpt length")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("search", help="Search Substack publications by keyword")
    s.add_argument("query", help="Search string")
    s.add_argument("--page", type=int, default=0)
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if not args.command:
        interactive_loop()
        return
    if args.command == "run":
        cmd_run(
            args.subdomain,
            n=args.n,
            excerpt_chars=args.excerpt_chars,
            as_json=args.json,
            export_fmt=args.export,
        )
    elif args.command == "search":
        cmd_search(
            args.query,
            page=args.page,
            limit=args.limit,
            as_json=args.json,
            export_fmt=args.export,
        )


if __name__ == "__main__":
    main()
