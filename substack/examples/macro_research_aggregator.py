#!/usr/bin/env python3
"""
Macro Research Aggregator
=========================
Pulls latest posts from curated macro-related Substack publications, grouped by
category, with optional single-publication deep dive (full post text).

Usage:
    python macro_research_aggregator.py
    python macro_research_aggregator.py run
    python macro_research_aggregator.py run --per-pub 5 --export json
    python macro_research_aggregator.py publication apricitas --limit 8 --slug my-post
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from substack import (
    PUBLICATIONS,
    _PUB_INDEX,
    _all_pub_ids,
    get_archive,
    get_post,
    html_to_text,
)

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


def _print_grouped(grouped, per_cat_limit=None):
    for cat in PUBLICATIONS.keys():
        posts = grouped.get(cat) or []
        if per_cat_limit:
            posts = posts[:per_cat_limit]
        if not posts:
            continue
        print(f"\n  [{cat.upper()}]  ({len(posts)} posts)")
        print("  " + "-" * 72)
        for p in posts:
            title = p.get("title", "(untitled)")
            sub = (p.get("subtitle") or "").strip()
            d = _format_date(p.get("post_date"))
            pub = p.get("_pub_name") or p.get("_pub_id", "")
            print(f"  {d}  [{pub}] {title}")
            if sub:
                print(f"         {sub[:120]}{'...' if len(sub) > 120 else ''}")
            print()


def cmd_run(per_pub=4, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    pub_ids = _all_pub_ids()
    grouped = {cat: [] for cat in PUBLICATIONS}
    total = len(pub_ids)
    print(f"\n  Fetching up to {per_pub} posts from {total} publications ...")

    for i, pid in enumerate(pub_ids, 1):
        _progress(f"archive {i}/{total} ({pid})", t0, last)
        name = _PUB_INDEX.get(pid, {}).get("name", pid)
        cat = _PUB_INDEX.get(pid, {}).get("category", "macro")
        print(f"  [{i}/{total}] {name} ({pid}) ...", flush=True)
        try:
            posts = get_archive(pid, limit=per_pub)
        except Exception as e:
            print(f"       error: {e}")
            continue
        for p in posts or []:
            p = dict(p)
            p["_pub_id"] = pid
            p["_pub_name"] = name
            p["_category"] = cat
            grouped.setdefault(cat, []).append(p)

    for cat in grouped:
        grouped[cat].sort(key=lambda x: x.get("post_date", ""), reverse=True)

    flat = []
    for cat, plist in grouped.items():
        for p in plist:
            q = dict(p)
            q["category"] = cat
            flat.append(q)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "per_publication_limit": per_pub,
        "grouped_by_category": grouped,
        "flat_posts": flat,
    }

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        _print_grouped(grouped)

    elapsed = int(time.time() - t0)
    print(f"  Completed in {elapsed}s")

    if export_fmt:
        _export(payload, "macro_research_aggregator", export_fmt)
    return payload


def cmd_publication(subdomain, limit=10, slug=None, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    if subdomain not in _PUB_INDEX:
        print(f"  Unknown subdomain '{subdomain}'. Use a curated id from PUBLICATIONS.")
        return None

    info = _PUB_INDEX[subdomain]
    print(f"\n  Publication: {info.get('name')} ({subdomain})")

    _progress("fetch archive", t0, last)
    posts = get_archive(subdomain, limit=limit)
    if posts is None:
        posts = []

    if slug:
        _progress(f"fetch post {slug}", t0, last)
        post = get_post(subdomain, slug)
        body = post.get("body_html", "") if post else ""
        text = html_to_text(body) if body else ""
        out = {
            "subdomain": subdomain,
            "archive_sample": posts,
            "deep_dive": post,
            "body_plain": text,
        }
        if as_json:
            print(json.dumps(out, indent=2, default=str))
        else:
            for p in posts[: min(15, len(posts))]:
                print(
                    f"  {_format_date(p.get('post_date'))}  {p.get('title', '')}  "
                    f"slug={p.get('slug')}"
                )
            if post:
                print(f"\n  --- full text: {slug} ---\n")
                print(text[:12000])
                if len(text) > 12000:
                    print(f"\n  [... truncated, total {len(text)} chars]")
        elapsed = int(time.time() - t0)
        print(f"  Completed in {elapsed}s")
        if export_fmt:
            _export(out, f"macro_pub_{subdomain}_{slug or 'archive'}", export_fmt)
        return out

    out = {"subdomain": subdomain, "posts": posts}
    if as_json:
        print(json.dumps(out, indent=2, default=str))
    else:
        for p in posts:
            title = p.get("title", "(untitled)")
            sub = (p.get("subtitle") or "").strip()
            d = _format_date(p.get("post_date"))
            print(f"  {d}  {title}")
            if sub:
                print(f"         {sub}")
            print()

    elapsed = int(time.time() - t0)
    print(f"  Completed in {elapsed}s")
    if export_fmt:
        _export(out, f"macro_pub_{subdomain}", export_fmt)
    return out


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = data.get("flat_posts") or data.get("posts") or []
        if not rows and isinstance(data, dict):
            rows = data.get("archive_sample") or []
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
   Macro Research Aggregator (Substack curated publications)
  ============================================================

   1) run           Latest posts from all curated pubs (grouped by category)
   2) publication  Single publication archive or --slug deep dive

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
            pp = _prompt("Posts per publication", "4")
            per = int(pp) if str(pp).isdigit() else 4
            cmd_run(per_pub=per)
        elif c in ("2", "publication"):
            sub = _prompt("Subdomain (e.g. apricitas)")
            if not sub:
                continue
            lim = _prompt("Archive limit", "10")
            limit = int(lim) if str(lim).isdigit() else 10
            sl = _prompt("Optional slug for full text (empty=skip)", "")
            slug = sl.strip() or None
            cmd_publication(sub, limit=limit, slug=slug)
        else:
            print(f"  Unknown: {c}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="macro_research_aggregator.py",
        description="Aggregate latest macro newsletter posts from curated Substacks",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Latest from all curated publications")
    s.add_argument("--per-pub", type=int, default=4, help="Posts per publication")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("publication", help="Single publication archive or full post")
    s.add_argument("subdomain", help="Publication subdomain")
    s.add_argument("--limit", type=int, default=10, help="Archive posts to fetch")
    s.add_argument("--slug", default=None, help="If set, fetch full post body as text")
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
            per_pub=args.per_pub,
            as_json=args.json,
            export_fmt=args.export,
        )
    elif args.command == "publication":
        cmd_publication(
            args.subdomain,
            limit=args.limit,
            slug=args.slug,
            as_json=args.json,
            export_fmt=args.export,
        )


if __name__ == "__main__":
    main()
