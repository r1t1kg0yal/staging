#!/usr/bin/env python3
"""
FDIC Bank Stress Monitor
========================
Screens large banks (assets >= $10B, amounts in $000s) on the latest published
Call Report quarter: credit-cycle metrics, NIM profitability for the top 50
by assets, uninsured and brokered deposit intensity, Tier 1 capital ordered
from weakest to strongest, and a composite stress score.

Usage:
    python bank_stress_monitor.py
    python bank_stress_monitor.py run
    python bank_stress_monitor.py run --json
    python bank_stress_monitor.py credit-cycle --export json
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

LARGE_BANK_ASSET_MIN = 10_000_000
PROGRESS_EVERY_S = 5.0

CREDIT_CYCLE_FIELDS = (
    "CERT,REPDTE,ASSET,NCLNLSR,NTLNLSR,NCLNLS,ELNATR,P3ASSET,P9ASSET,NAESSION,"
    "P3RE,P9RE,P3CI,P9CI,LNLSNET,LNATRES"
)


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


def _large_bank_filter(repdte):
    return f"REPDTE:{repdte} AND ASSET:[{LARGE_BANK_ASSET_MIN} TO *]"


def _fetch_institution_names(certs):
    if not certs:
        return {}
    out = {}
    chunk = 15
    for i in range(0, len(certs), chunk):
        part = certs[i : i + chunk]
        filt = "(" + " OR ".join(f"CERT:{c}" for c in part) + ")"
        resp = _get(
            "institutions",
            {
                "filters": filt,
                "fields": "CERT,NAME",
                "limit": len(part),
            },
        )
        rows, _ = _extract_rows(resp)
        for r in rows:
            c = r.get("CERT")
            if c is not None:
                out[str(c)] = (r.get("NAME") or "").strip()
        time.sleep(0.2)
    return out


def _mean(vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _pctile(vals, p):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    k = (len(v) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    w = k - lo
    return v[lo] * (1 - w) + v[hi] * w


def _past_due_pct(row):
    ast = _safe_float(row.get("ASSET"))
    if not ast or ast <= 0:
        return None
    p3 = _safe_float(row.get("P3ASSET")) or 0.0
    p9 = _safe_float(row.get("P9ASSET")) or 0.0
    return (p3 + p9) / ast * 100.0


def _composite_stress(credit_rows, nim_rows, un_rows, cap_rows):
    ncls = [_safe_float(r.get("NCLNLSR")) for r in credit_rows]
    pds = [_past_due_pct(r) for r in credit_rows]
    provs = []
    for r in credit_rows:
        ast = _safe_float(r.get("ASSET"))
        el = _safe_float(r.get("ELNATR"))
        if ast and ast > 0 and el is not None:
            provs.append(abs(el) / ast * 100.0)

    nims = [_safe_float(r.get("NIMY")) for r in nim_rows]
    un_rat = []
    bro_rat = []
    for r in un_rows:
        dep = _safe_float(r.get("DEP"))
        if dep and dep > 0:
            du = _safe_float(r.get("DEPUNA"))
            br = _safe_float(r.get("BRO"))
            if du is not None:
                un_rat.append(du / dep * 100.0)
            if br is not None:
                bro_rat.append(br / dep * 100.0)

    t1s = [_safe_float(r.get("IDT1CER")) for r in cap_rows if _safe_float(r.get("IDT1CER")) is not None]

    avg_ncl = _mean(ncls) or 0.0
    avg_pd = _mean(pds) or 0.0
    avg_prov = _mean(provs) or 0.0
    avg_nim = _mean(nims) or 0.0
    med_un = _mean(un_rat) if un_rat else None
    med_bro = _mean(bro_rat) if bro_rat else None
    p10_t1 = _pctile(t1s, 0.10) if t1s else None

    score = 0.0
    score += min(28.0, avg_ncl * 35.0)
    score += min(22.0, avg_pd * 2.5)
    score += min(18.0, avg_prov * 8.0)
    if avg_nim < 2.8:
        score += min(12.0, (2.8 - avg_nim) * 4.0)
    if med_un is not None and med_un > 15:
        score += min(10.0, (med_un - 15) * 0.25)
    if med_bro is not None and med_bro > 8:
        score += min(10.0, (med_bro - 8) * 0.35)
    if p10_t1 is not None and p10_t1 < 12:
        score += min(15.0, (12 - p10_t1) * 1.2)

    score = min(100.0, score)
    if score >= 55:
        label = "HIGH"
    elif score >= 38:
        label = "ELEVATED"
    elif score >= 22:
        label = "WATCH"
    else:
        label = "NORMAL"

    return {
        "stress_score": round(score, 1),
        "stress_label": label,
        "inputs": {
            "avg_nclnlsr_pct": round(avg_ncl, 4),
            "avg_past_due_to_assets_pct": round(avg_pd, 4),
            "avg_provision_to_assets_pct": round(avg_prov, 4),
            "avg_nimy_pct": round(avg_nim, 3) if nims else None,
            "avg_uninsured_to_dep_pct": round(med_un, 3) if med_un is not None else None,
            "avg_brokered_to_dep_pct": round(med_bro, 3) if med_bro is not None else None,
            "pct10_idt1cer": round(p10_t1, 3) if p10_t1 is not None else None,
        },
    }


def _print_progress(label, t0, last_print):
    now = time.time()
    if now - last_print[0] >= PROGRESS_EVERY_S:
        elapsed = int(now - t0)
        print(f"  ... {label} ({elapsed}s elapsed)")
        last_print[0] = now
    return last_print


def _pull_credit_cycle(repdte, limit=400, last_print=None, t0=None):
    if last_print is None:
        last_print = [time.time()]
    if t0 is None:
        t0 = time.time()
    resp = _get(
        "financials",
        {
            "filters": _large_bank_filter(repdte),
            "fields": CREDIT_CYCLE_FIELDS,
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": limit,
        },
    )
    _print_progress("credit-cycle financials", t0, last_print)
    rows, total = _extract_rows(resp)
    return rows, total


def _pull_nim_top50(repdte, last_print, t0):
    resp = _get(
        "financials",
        {
            "filters": _large_bank_filter(repdte),
            "fields": FINANCIAL_FIELDS["default"],
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": 50,
        },
    )
    _print_progress("NIM regime (top 50 assets)", t0, last_print)
    return _extract_rows(resp)[0]


def _pull_uninsured(repdte, limit=250, last_print=None, t0=None):
    resp = _get(
        "financials",
        {
            "filters": _large_bank_filter(repdte),
            "fields": FINANCIAL_FIELDS["deposits"],
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": limit,
        },
    )
    _print_progress("uninsured / brokered screen", t0, last_print)
    return _extract_rows(resp)[0]


def _pull_capital_sorted(repdte, limit=250, last_print=None, t0=None):
    resp = _get(
        "financials",
        {
            "filters": _large_bank_filter(repdte),
            "fields": FINANCIAL_FIELDS["capital"],
            "sort_by": "IDT1CER",
            "sort_order": "ASC",
            "limit": limit,
        },
    )
    _print_progress("capital distribution", t0, last_print)
    return _extract_rows(resp)[0]


def _attach_names(rows, name_map):
    for r in rows:
        c = str(r.get("CERT", ""))
        r["_NAME"] = name_map.get(c, "")


def _print_credit_table(rows, name_map, max_rows=35):
    _attach_names(rows, name_map)
    print(f"\n  CREDIT CYCLE (large banks, n={len(rows)})")
    print("  " + "=" * 96)
    hdr = f"  {'CERT':>6}  {'NAME':<28}  {'NCL%':>7}  {'Prov/AST%':>10}  {'PD/AST%':>9}"
    print(hdr)
    print("  " + "-" * 96)
    for r in rows[:max_rows]:
        cert = r.get("CERT", "")
        nm = (name_map.get(str(cert), r.get("_NAME", "")) or "")[:28]
        ncl = _safe_float(r.get("NCLNLSR"))
        ast = _safe_float(r.get("ASSET"))
        el = _safe_float(r.get("ELNATR"))
        prov_pct = (abs(el) / ast * 100.0) if ast and el is not None else None
        pd_pct = _past_due_pct(r)
        ns = f"{ncl:.3f}" if ncl is not None else "--"
        ps = f"{prov_pct:.3f}" if prov_pct is not None else "--"
        ds = f"{pd_pct:.3f}" if pd_pct is not None else "--"
        print(f"  {str(cert):>6}  {nm:<28}  {ns:>7}  {ps:>10}  {ds:>9}")
    if len(rows) > max_rows:
        print(f"  ... ({len(rows) - max_rows} more rows omitted in console view)")


def _print_nim_table(rows, name_map):
    _attach_names(rows, name_map)
    print(f"\n  NIM REGIME (top 50 by assets)")
    print("  " + "=" * 88)
    print(f"  {'CERT':>6}  {'NAME':<26}  {'ASSET$B':>10}  {'NIM%':>7}  {'ROA%':>7}  {'ROE%':>7}")
    print("  " + "-" * 88)
    for r in rows:
        cert = r.get("CERT", "")
        nm = (name_map.get(str(cert), "") or "")[:26]
        ast = _safe_float(r.get("ASSET"))
        ab = ast / 1e6 if ast else None
        nim = _safe_float(r.get("NIMY"))
        roa = _safe_float(r.get("ROA"))
        roe = _safe_float(r.get("ROE"))
        ab_s = f"{ab:,.2f}" if ab is not None else "--"
        print(
            f"  {str(cert):>6}  {nm:<26}  {ab_s:>10}  "
            f"{(f'{nim:.2f}' if nim is not None else '--'):>7}  "
            f"{(f'{roa:.2f}' if roa is not None else '--'):>7}  "
            f"{(f'{roe:.2f}' if roe is not None else '--'):>7}"
        )


def _print_uninsured_table(rows, name_map, max_rows=30):
    print(f"\n  UNINSURED DEPOSITS & BROKERED (large banks)")
    print("  " + "=" * 92)
    print(f"  {'CERT':>6}  {'NAME':<24}  {'DEPUNA/DEP%':>12}  {'BRO/DEP%':>10}  {'DEP$B':>10}")
    print("  " + "-" * 92)
    for r in rows[:max_rows]:
        cert = r.get("CERT", "")
        nm = (name_map.get(str(cert), "") or "")[:24]
        dep = _safe_float(r.get("DEP"))
        du = _safe_float(r.get("DEPUNA"))
        br = _safe_float(r.get("BRO"))
        ur = (du / dep * 100.0) if dep and du is not None else None
        brp = (br / dep * 100.0) if dep and br is not None else None
        db = dep / 1e6 if dep else None
        print(
            f"  {str(cert):>6}  {nm:<24}  "
            f"{(f'{ur:.2f}' if ur is not None else '--'):>12}  "
            f"{(f'{brp:.2f}' if brp is not None else '--'):>10}  "
            f"{(f'{db:,.2f}' if db is not None else '--'):>10}"
        )


def _print_capital_table(rows, name_map, max_rows=35):
    print(f"\n  TIER 1 RATIO (weakest first, IDT1CER)")
    print("  " + "=" * 72)
    print(f"  {'CERT':>6}  {'NAME':<28}  {'IDT1CER%':>10}  {'ASSET$B':>10}")
    print("  " + "-" * 72)
    for r in rows[:max_rows]:
        cert = r.get("CERT", "")
        nm = (name_map.get(str(cert), "") or "")[:28]
        t1 = _safe_float(r.get("IDT1CER"))
        ast = _safe_float(r.get("ASSET"))
        ab = ast / 1e6 if ast else None
        print(
            f"  {str(cert):>6}  {nm:<28}  "
            f"{(f'{t1:.2f}' if t1 is not None else '--'):>10}  "
            f"{(f'{ab:,.2f}' if ab is not None else '--'):>10}"
        )


def cmd_credit_cycle(repdte=None, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    rep = repdte or _latest_repdte()
    if not rep:
        print("  Could not resolve latest REPDTE.")
        return None
    print(f"\n  FDIC credit-cycle screen  |  REPDTE={rep}  |  dollars in $000s unless noted")
    print("  [1/1] Pulling credit-cycle financials for ASSET >= $10B ...")
    rows, total = _pull_credit_cycle(rep, last_print=last, t0=t0)
    if not rows:
        print("  No rows returned.")
        return None
    certs = list({str(r.get("CERT")) for r in rows if r.get("CERT") is not None})
    print(f"  Fetched {len(rows)} rows (meta total ~{total}). Resolving names ...")
    names = _fetch_institution_names(certs)
    out = {
        "repdte": rep,
        "filter": _large_bank_filter(rep),
        "credit_cycle": rows,
        "meta_total": total,
    }
    if as_json:
        print(json.dumps(out, indent=2, default=str))
    else:
        _print_credit_table(rows, names)
        elapsed = int(time.time() - t0)
        print(f"\n  Completed in {elapsed}s\n")
    if export_fmt:
        _export(out, "bank_stress_credit_cycle", export_fmt)
    return out


def cmd_run(repdte=None, as_json=False, export_fmt=None):
    t0 = time.time()
    last = [t0]
    rep = repdte or _latest_repdte()
    if not rep:
        print("  Could not resolve latest REPDTE.")
        return None

    print(f"\n  FDIC BANK STRESS MONITOR  |  REPDTE={rep}  |  $ amounts in $000s")
    print("  [1/4] Credit-cycle panel (NCL%, provisions, past-dues) ...")
    credit_rows, ct = _pull_credit_cycle(rep, last_print=last, t0=t0)
    time.sleep(0.25)
    print("  [2/4] NIM regime (top 50 by assets) ...")
    nim_rows = _pull_nim_top50(rep, last, t0)
    time.sleep(0.25)
    print("  [3/4] Uninsured / brokered deposit screen ...")
    un_rows = _pull_uninsured(rep, last_print=last, t0=t0)
    time.sleep(0.25)
    print("  [4/4] Capital distribution (Tier 1 ascending) ...")
    cap_rows = _pull_capital_sorted(rep, last_print=last, t0=t0)

    if not credit_rows:
        print("  No financial rows returned; aborting.")
        return None

    certs = list(
        {
            str(r.get("CERT"))
            for block in (credit_rows, nim_rows, un_rows, cap_rows)
            for r in block
            if r.get("CERT") is not None
        }
    )
    print(f"  Resolving institution names ({len(certs)} CERTs) ...")
    names = _fetch_institution_names(certs)
    composite = _composite_stress(credit_rows, nim_rows, un_rows, cap_rows)

    result = {
        "timestamp": datetime.now().isoformat(),
        "repdte": rep,
        "large_bank_asset_floor_000s": LARGE_BANK_ASSET_MIN,
        "credit_cycle": credit_rows,
        "credit_cycle_meta_total": ct,
        "nim_top50": nim_rows,
        "uninsured_brokered": un_rows,
        "capital_distribution": cap_rows,
        "composite": composite,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        if export_fmt:
            _export(result, "bank_stress_full", export_fmt)
        return result

    _print_credit_table(credit_rows, names)
    _print_nim_table(nim_rows, names)
    _print_uninsured_table(un_rows, names)
    _print_capital_table(cap_rows, names)

    print(f"\n  {'=' * 56}")
    print(
        f"  COMPOSITE STRESS: {composite['stress_score']:.1f} / 100  "
        f"[{composite['stress_label']}]"
    )
    print(f"  {'=' * 56}")
    ins = composite["inputs"]
    print(
        f"  Avg NCL rate: {ins['avg_nclnlsr_pct']:.4f}%  |  "
        f"Avg past-due / assets: {ins['avg_past_due_to_assets_pct']:.4f}%"
    )
    print(
        f"  Avg provision / assets: {ins['avg_provision_to_assets_pct']:.4f}%  |  "
        f"Avg NIM (top50): {ins['avg_nimy_pct']}"
    )
    print(
        f"  Uninsured / DEP (avg): {ins['avg_uninsured_to_dep_pct']}  |  "
        f"Brokered / DEP (avg): {ins['avg_brokered_to_dep_pct']}  |  "
        f"10th pct Tier1: {ins['pct10_idt1cer']}"
    )

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s\n")

    if export_fmt:
        _export(result, "bank_stress_full", export_fmt)
    return result


def _export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR_LOCAL, "..", "data"), exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCRIPT_DIR_LOCAL, "..", "data", f"{prefix}_{ts}.{fmt}")
    if fmt == "json":
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif fmt == "csv":
        rows = None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("credit_cycle", "nim_top50", "uninsured_brokered", "capital_distribution"):
                if isinstance(data.get(key), list) and data[key]:
                    rows = data[key]
                    break
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
   FDIC Bank Stress Monitor
  ============================================================

   1) run           Full assessment (credit, NIM, deposits, capital, composite)
   2) credit-cycle  NCL, provisions, past-dues for large banks

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
        elif choice in ("2", "credit-cycle"):
            cmd_credit_cycle()
        else:
            print(f"  Unknown: {choice}")


def build_argparse():
    p = argparse.ArgumentParser(
        prog="bank_stress_monitor.py",
        description="FDIC large-bank stress monitor (Call Report /financials)",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("run", help="Full stress assessment")
    s.add_argument("--repdte", type=str, default=None, help="Override report date YYYYMMDD")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("credit-cycle", help="Credit-cycle indicators for large banks")
    s.add_argument("--repdte", type=str, default=None)
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
    elif args.command == "credit-cycle":
        cmd_credit_cycle(
            repdte=getattr(args, "repdte", None),
            as_json=args.json,
            export_fmt=args.export,
        )
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
