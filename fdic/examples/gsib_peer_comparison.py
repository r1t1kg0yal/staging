#!/usr/bin/env python3
"""
GSIB Peer Comparison (FDIC Call Reports)
=========================================
Side-by-side snapshot of JPMorgan (628), Bank of America (3510), Citibank (7213),
Wells Fargo (3511), and Goldman Sachs (33124) on the latest quarter, using
multiple financial field presets. Optional eight-quarter time series for
assets, ROA, NIM, and net charge-off rate.

All dollar amounts from /financials are in $000s unless noted.

Usage:
    python gsib_peer_comparison.py
    python gsib_peer_comparison.py run
    python gsib_peer_comparison.py run --json
    python gsib_peer_comparison.py time-series --export json
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fdic import _get, _extract_rows, FINANCIAL_FIELDS

SCRIPT_DIR_LOCAL = os.path.dirname(os.path.abspath(__file__))

GSIB_PEERS = [
    ("628", "JPMorgan"),
    ("3510", "Bank of America"),
    ("7213", "Citibank"),
    ("3511", "Wells Fargo"),
    ("33124", "Goldman Sachs"),
]

PRESET_KEYS = ("default", "ratios", "deposits", "credit_quality", "capital")
PROGRESS_EVERY_S = 5.0

TS_FIELDS = "CERT,REPDTE,ASSET,ROA,NIMY,NCLNLSR"
TS_QUARTERS = 8


def _safe_float(x):
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _safe_int(x):
    if x is None or x == "":
        return None
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def _merge_financial_fields(preset_names):
    seen = set()
    out = []
    for name in preset_names:
        blob = FINANCIAL_FIELDS.get(name, "")
        for part in blob.split(","):
            p = part.strip()
            if p and p not in seen:
                seen.add(p)
                out.append(p)
    return ",".join(out)


def _latest_repdte():
    resp = _get(
        "financials",
        {
            "filters": "CERT:628",
            "fields": "REPDTE",
            "sort_by": "REPDTE",
            "sort_order": "DESC",
            "limit": 1,
        },
    )
    rows, _ = _extract_rows(resp)
    if not rows:
        return None
    return str(_safe_int(rows[0].get("REPDTE")))


def _peer_cert_filter():
    inner = " OR ".join(f"CERT:{c}" for c, _ in GSIB_PEERS)
    return f"({inner})"


def _print_progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        print(f"  ... {label} ({int(now - t0)}s)")
        last_print[0] = now


def _fetch_peer_snapshot(repdte, last_print, t0):
    fields = _merge_financial_fields(PRESET_KEYS)
    filt = f"REPDTE:{repdte} AND {_peer_cert_filter()}"
    resp = _get(
        "financials",
        {
            "filters": filt,
            "fields": fields,
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": len(GSIB_PEERS) + 2,
        },
    )
    _print_progress("peer snapshot", t0, last_print)
    rows, total = _extract_rows(resp)
    by_cert = {}
    for r in rows:
        c = r.get("CERT")
        if c is not None:
            by_cert[str(c)] = r
    return by_cert, total


def _row_get(row, key):
    if not row:
        return None
    return row.get(key)


def _side_by_side_tables(by_cert, repdte, as_json):
    order = [c for c, _ in GSIB_PEERS]
    labels = {c: lbl for c, lbl in GSIB_PEERS}

    sections = [
        (
            "DEFAULT (income / scale)",
            ["ASSET", "DEP", "NETINC", "ROA", "ROE", "NIMY", "ELNATR"],
        ),
        (
            "RATIOS",
            ["ROA", "ROE", "NIMY", "EEFFR", "NTLNLSR", "NCLNLSR", "LNLSDEPR", "EQCDIV", "IDT1CER"],
        ),
        (
            "DEPOSITS ($000s; ratios where noted)",
            ["DEP", "DEPDOM", "DEPFOR", "DEPUNA", "BRO", "EDEPDOM", "DDT", "NTRSMMDA", "NTRTMLG"],
        ),
        (
            "CREDIT QUALITY ($000s)",
            ["LNLSNET", "NCLNLS", "NTRE", "NTCI", "P3ASSET", "P9ASSET", "NAESSION", "LNATRES"],
        ),
        (
            "CAPITAL ($000s; ratios where noted)",
            ["EQTOT", "EQPP", "IDT1CER", "RBCT1J", "RBCT2", "IDT1LER", "RBCRWAJ", "EQCDIV"],
        ),
    ]

    matrices = []
    for title, keys in sections:
        mat = {"title": title, "metrics": {}}
        for k in keys:
            mat["metrics"][k] = {}
            for c in order:
                mat["metrics"][k][c] = _row_get(by_cert.get(c), k)
        matrices.append(mat)

    payload = {"repdte": repdte, "peers": labels, "sections": matrices, "rows_by_cert": by_cert}

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return payload

    print(f"\n  GSIB PEER SNAPSHOT  |  REPDTE={repdte}  |  amounts $000s unless %")
    col_w = 14
    cert_headers = [f"{labels[c][:10]}" for c in order]

    for title, keys in sections:
        print(f"\n  {title}")
        print("  " + "=" * (22 + len(order) * (col_w + 1)))
        hdr = f"  {'METRIC':<18}" + "".join(f"  {h:>{col_w}}" for h in cert_headers)
        print(hdr)
        print("  " + "-" * len(hdr))
        for k in keys:
            cells = []
            for c in order:
                v = _row_get(by_cert.get(c), k)
                if v is None:
                    s = "--"
                elif k in ("ASSET", "DEP", "DEPDOM", "NETINC", "EQTOT", "LNLSNET", "NCLNLS", "LNATRES", "EQCDIV", "ELNATR", "DEPUNA", "BRO", "EDEPDOM", "DDT", "NTRSMMDA", "NTRTMLG", "DEPFOR", "EQPP", "NTRE", "NTCI", "P3ASSET", "P9ASSET", "NAESSION"):
                    fv = _safe_float(v)
                    if fv is None:
                        s = "--"
                    elif abs(fv) >= 1e6:
                        s = f"{fv/1e6:,.2f}M"
                    else:
                        s = f"{fv:,.0f}"
                else:
                    fv = _safe_float(v)
                    s = f"{fv:.3f}" if fv is not None else str(v)
                cells.append(f"{s:>{col_w}}")
            print(f"  {k:<18}" + "".join(f"  {x}" for x in cells))

    return payload


def _fetch_ts_for_cert(cert, last_print, t0):
    resp = _get(
        "financials",
        {
            "filters": f"CERT:{cert}",
            "fields": TS_FIELDS,
            "sort_by": "REPDTE",
            "sort_order": "DESC",
            "limit": TS_QUARTERS,
        },
    )
    _print_progress(f"time series CERT {cert}", t0, last_print)
    rows, _ = _extract_rows(resp)
    rows.sort(key=lambda r: _safe_int(r.get("REPDTE")) or 0)
    return rows


def _time_series_payload():
    t0 = time.time()
    last = [t0]
    by_cert_ts = {}
    all_rep = set()
    for cert, _ in GSIB_PEERS:
        time.sleep(0.2)
        by_cert_ts[cert] = _fetch_ts_for_cert(cert, last, t0)
        for r in by_cert_ts[cert]:
            rd = r.get("REPDTE")
            if rd is not None:
                all_rep.add(_safe_int(rd))
    rep_sorted = sorted(all_rep)
    return {
        "quarters": [str(x) for x in rep_sorted],
        "series_by_cert": by_cert_ts,
    }


def _print_time_series(payload, as_json):
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return
    labels = {c: lbl for c, lbl in GSIB_PEERS}
    by_cert = payload["series_by_cert"]
    all_dates = sorted(
        {
            _safe_int(r.get("REPDTE"))
            for rows in by_cert.values()
            for r in rows
            if r.get("REPDTE") is not None
        }
    )

    metrics = [
        ("ASSET", "ASSET ($B)", 1e6),
        ("ROA", "ROA (%)", 1.0),
        ("NIMY", "NIM (%)", 1.0),
        ("NCLNLSR", "NCL rate (%)", 1.0),
    ]

    print(f"\n  GSIB 8-QUARTER TIME SERIES (assets in $B, from $000s)")
    for mkey, mlabel, scale in metrics:
        print(f"\n  {mlabel}")
        print("  " + "=" * 96)
        hdr = f"  {'REPDTE':>10}" + "".join(f"  {labels[c][:14]:>14}" for c, _ in GSIB_PEERS)
        print(hdr)
        print("  " + "-" * len(hdr))
        for d in all_dates:
            line = f"  {d:>10}"
            for cert, _ in GSIB_PEERS:
                row = next((r for r in by_cert[cert] if _safe_int(r.get("REPDTE")) == d), None)
                v = _row_get(row, mkey)
                fv = _safe_float(v)
                if fv is None:
                    line += f"  {'--':>14}"
                elif mkey == "ASSET":
                    line += f"  {fv / 1e6:>14,.2f}"
                else:
                    line += f"  {fv:>14,.3f}"
            print(line)


def cmd_run(repdte=None, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    rep = repdte or _latest_repdte()
    if not rep:
        print("  Could not resolve REPDTE.")
        return None
    print(f"\n  Fetching GSIB peer snapshot (REPDTE={rep}) ...")
    by_cert, total = _fetch_peer_snapshot(rep, last, t0)
    missing = [c for c, _ in GSIB_PEERS if c not in by_cert]
    if missing:
        print(f"  Warning: missing CERT rows: {missing} (meta total={total})")
    out = _side_by_side_tables(by_cert, rep, as_json)
    out["timestamp"] = datetime.now().isoformat()
    out["fetch_seconds"] = round(time.time() - t0, 2)
    if export_fmt:
        _export(out, "gsib_peer_snapshot", export_fmt)
    if not as_json:
        print(f"\n  Completed in {out['fetch_seconds']}s\n")
    return out


def cmd_time_series(as_json=False, export_fmt=None):
    t0 = time.time()
    print("\n  Fetching 8-quarter series per GSIB (sequential) ...")
    payload = _time_series_payload()
    payload["timestamp"] = datetime.now().isoformat()
    payload["fetch_seconds"] = round(time.time() - t0, 2)
    _print_time_series(payload, as_json)
    if not as_json:
        print(f"\n  Completed in {payload['fetch_seconds']}s\n")
    if export_fmt:
        if export_fmt == "json":
            _export(payload, "gsib_peer_timeseries", "json")
        else:
            flat = []
            for cert, rows in payload["series_by_cert"].items():
                for r in rows:
                    flat.append(dict(r, _PEER_CERT=cert))
            _export(flat, "gsib_peer_timeseries", "csv")
    return payload


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = data if isinstance(data, list) else None
        if rows and isinstance(rows[0], dict):
            with open(path, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        else:
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
    print(f"  Exported: {path}")


MENU = """
  ============================================================
   GSIB Peer Comparison (FDIC /financials)
  ============================================================

   1) run          Latest-quarter side-by-side tables
   2) time-series  Eight-quarter ASSET, ROA, NIM, NCL%

   q) quit
"""


def interactive_loop():
    print(MENU)
    while True:
        try:
            choice = input("\n  Command: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice in ("q", "quit", "exit"):
            break
        if choice in ("1", "run"):
            cmd_run()
        elif choice in ("2", "time-series", "ts"):
            cmd_time_series()
        else:
            print(f"  Unknown: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="gsib_peer_comparison.py",
        description="GSIB peer tables and time series via FDIC BankFind /financials",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Latest quarter multi-preset comparison")
    s.add_argument("--repdte", type=str, default=None)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("time-series", help="Eight-quarter key metrics per peer")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command == "run":
        cmd_run(
            repdte=getattr(args, "repdte", None),
            as_json=args.json,
            export_fmt=args.export,
        )
    elif args.command == "time-series":
        cmd_time_series(as_json=args.json, export_fmt=args.export)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
