#!/usr/bin/env python3
"""
BIS Data Ontology Scraper
=========================
Scrapes the full BIS SDMX API to build a comprehensive ontology of all
BIS statistical datasets, their dimensions, codelists, codes, and attributes.

Outputs a structured JSON ontology file similar to the FRED ontology format.

BIS API: https://stats.bis.org/api/v2/
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

BASE_URL = "https://stats.bis.org/api/v2"
OUTPUT_DIR = Path(__file__).parent / "data" / "ontology"
DEFAULT_OUTPUT = OUTPUT_DIR / "bis_ontology.json"

HEADERS = {
    "Accept": "application/vnd.sdmx.structure+json;version=1.0.0",
    "User-Agent": "BIS-Ontology-Scraper/1.0",
}

DATA_HEADERS = {
    "Accept": "application/vnd.sdmx.data+json;version=1.0.0",
    "User-Agent": "BIS-Ontology-Scraper/1.0",
}


def api_get(endpoint, params=None, max_retries=3):
    url = f"{BASE_URL}{endpoint}"
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"    HTTP {resp.status_code} for {url}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
        except requests.exceptions.Timeout:
            print(f"    Timeout for {url}, retry {attempt+1}/{max_retries}")
            time.sleep(3)
        except Exception as e:
            print(f"    Error fetching {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return None
    return None


def fetch_all_dataflows():
    print("Fetching all BIS dataflows...")
    data = api_get("/structure/dataflow/BIS", params={"format": "sdmx-json"})
    if not data:
        print("FATAL: Could not fetch dataflows")
        sys.exit(1)
    flows = data["data"]["dataflows"]
    print(f"  Found {len(flows)} dataflows")
    return flows


def parse_codelist(cl_raw):
    codelist = {
        "id": cl_raw["id"],
        "name": cl_raw.get("name", ""),
        "description": cl_raw.get("description", ""),
        "codes": {},
    }
    for code in cl_raw.get("codes", []):
        entry = {
            "id": code["id"],
            "name": code.get("name", ""),
        }
        if "description" in code:
            entry["description"] = code["description"]
        if "parent" in code:
            entry["parent"] = code["parent"]
        codelist["codes"][code["id"]] = entry
    return codelist


def extract_codelist_id_from_urn(urn):
    if not urn:
        return None
    try:
        part = urn.split("Codelist=")[1]
        cl_id = part.split(":")[1].split("(")[0]
        return cl_id
    except (IndexError, KeyError):
        return None


def parse_dimension(dim_raw, codelists_by_id):
    codelist_urn = dim_raw.get("localRepresentation", {}).get("enumeration", "")
    cl_id = extract_codelist_id_from_urn(codelist_urn)

    concept_urn = dim_raw.get("conceptIdentity", "")
    concept_name = concept_urn.split(".")[-1] if concept_urn else ""

    dim = {
        "id": dim_raw["id"],
        "position": dim_raw.get("position"),
        "concept": concept_name,
        "codelist_id": cl_id,
    }

    if cl_id and cl_id in codelists_by_id:
        cl = codelists_by_id[cl_id]
        dim["codelist_name"] = cl["name"]
        dim["num_codes"] = len(cl["codes"])
    return dim


def parse_attribute(attr_raw, codelists_by_id):
    codelist_urn = attr_raw.get("localRepresentation", {}).get("enumeration", "")
    cl_id = extract_codelist_id_from_urn(codelist_urn)

    concept_urn = attr_raw.get("conceptIdentity", "")
    concept_name = concept_urn.split(".")[-1] if concept_urn else ""

    attr = {
        "id": attr_raw["id"],
        "concept": concept_name,
        "codelist_id": cl_id,
        "assignment_status": attr_raw.get("assignmentStatus", ""),
        "relationship_type": attr_raw.get("attributeRelationship", {}).get("primaryMeasure")
        or (
            "dimensions"
            if attr_raw.get("attributeRelationship", {}).get("dimensions")
            else "observation"
            if attr_raw.get("attributeRelationship", {}).get("primaryMeasure")
            else "dataset"
        ),
    }
    if cl_id and cl_id in codelists_by_id:
        attr["codelist_name"] = codelists_by_id[cl_id]["name"]
        attr["num_codes"] = len(codelists_by_id[cl_id]["codes"])
    return attr


def fetch_and_parse_dsd(dsd_urn, flow_id):
    dsd_id_part = dsd_urn.split("DataStructure=BIS:")[1] if "DataStructure=BIS:" in dsd_urn else None
    if not dsd_id_part:
        print(f"  Could not parse DSD URN: {dsd_urn}")
        return None

    dsd_id = dsd_id_part.split("(")[0]
    version = dsd_id_part.split("(")[1].rstrip(")") if "(" in dsd_id_part else "1.0"

    print(f"  Fetching DSD: {dsd_id} v{version} (for {flow_id})...")
    data = api_get(
        f"/structure/datastructure/BIS/{dsd_id}/{version}",
        params={"format": "sdmx-json", "references": "children"},
    )
    if not data:
        print(f"    Failed to fetch DSD {dsd_id}")
        return None

    codelists_raw = data["data"].get("codelists", [])
    codelists_by_id = {}
    codelists_parsed = {}
    for cl_raw in codelists_raw:
        parsed = parse_codelist(cl_raw)
        codelists_by_id[cl_raw["id"]] = parsed
        codelists_parsed[cl_raw["id"]] = parsed

    ds = data["data"]["dataStructures"][0]
    components = ds["dataStructureComponents"]

    dims_raw = components.get("dimensionList", {}).get("dimensions", [])
    dimensions = []
    for d in sorted(dims_raw, key=lambda x: x.get("position", 0)):
        dimensions.append(parse_dimension(d, codelists_by_id))

    time_dim = components.get("dimensionList", {}).get("timeDimensions", [])
    for td in time_dim:
        dimensions.append({
            "id": td["id"],
            "position": td.get("position", len(dimensions) + 1),
            "concept": "TIME_PERIOD",
            "codelist_id": None,
            "is_time_dimension": True,
        })

    attrs_raw = components.get("attributeList", {}).get("attributes", [])
    attributes = []
    for a in attrs_raw:
        attributes.append(parse_attribute(a, codelists_by_id))

    concepts_raw = data["data"].get("conceptSchemes", [])
    concept_schemes = {}
    for cs in concepts_raw:
        scheme = {
            "id": cs["id"],
            "name": cs.get("name", ""),
            "concepts": {},
        }
        for concept in cs.get("concepts", []):
            scheme["concepts"][concept["id"]] = {
                "id": concept["id"],
                "name": concept.get("name", ""),
                "description": concept.get("description", ""),
            }
        concept_schemes[cs["id"]] = scheme

    result = {
        "dsd_id": dsd_id,
        "version": version,
        "name": ds.get("name", ""),
        "dimensions": dimensions,
        "attributes": attributes,
        "codelists": codelists_parsed,
        "concept_schemes": concept_schemes,
        "num_dimensions": len([d for d in dimensions if not d.get("is_time_dimension")]),
        "num_attributes": len(attributes),
        "num_codelists": len(codelists_parsed),
        "total_codes": sum(len(cl["codes"]) for cl in codelists_parsed.values()),
    }
    return result


def build_dataflow_entry(flow_raw, dsd_data):
    entry = {
        "id": flow_raw["id"],
        "name": flow_raw.get("name", ""),
        "description": flow_raw.get("description", ""),
        "dsd_ref": flow_raw.get("structure", ""),
    }
    if dsd_data:
        entry["structure"] = dsd_data
    return entry


def compute_stats(ontology):
    dataflows = ontology["dataflows"]
    total_dimensions = 0
    total_attributes = 0
    all_codelist_ids = set()
    total_codes = 0
    unique_dsds = set()
    domains = []

    for flow_id, flow in dataflows.items():
        domains.append(flow["name"])
        struct = flow.get("structure")
        if struct:
            unique_dsds.add(struct["dsd_id"])
            total_dimensions += struct["num_dimensions"]
            total_attributes += struct["num_attributes"]
            for cl_id, cl in struct["codelists"].items():
                if cl_id not in all_codelist_ids:
                    total_codes += len(cl["codes"])
                    all_codelist_ids.add(cl_id)

    return {
        "total_dataflows": len(dataflows),
        "unique_dsds": len(unique_dsds),
        "total_dimensions_across_flows": total_dimensions,
        "total_attributes_across_flows": total_attributes,
        "unique_codelists": len(all_codelist_ids),
        "total_unique_codes": total_codes,
        "domains": sorted(domains),
    }


def scrape_full_ontology(output_path=None, skip_existing=False):
    output_path = Path(output_path) if output_path else DEFAULT_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if skip_existing and output_path.exists():
        print(f"Output already exists at {output_path}, skipping (--skip-existing)")
        return

    flows = fetch_all_dataflows()

    seen_dsds = {}
    ontology = {
        "version": "1.0",
        "source": "Bank for International Settlements (BIS)",
        "api_base": BASE_URL,
        "generated": datetime.now(timezone.utc).isoformat(),
        "stats": {},
        "dataflows": {},
    }

    total = len(flows)
    for i, flow in enumerate(flows, 1):
        flow_id = flow["id"]
        flow_name = flow.get("name", "")
        dsd_urn = flow.get("structure", "")

        print(f"\n[{i}/{total}] {flow_id}: {flow_name}")

        dsd_key = dsd_urn.split("DataStructure=BIS:")[-1] if "DataStructure=BIS:" in dsd_urn else dsd_urn
        if dsd_key in seen_dsds:
            print(f"  DSD already fetched (shared with {seen_dsds[dsd_key]}), reusing...")
            dsd_data = ontology["dataflows"][seen_dsds[dsd_key]]["structure"]
        else:
            dsd_data = fetch_and_parse_dsd(dsd_urn, flow_id)
            seen_dsds[dsd_key] = flow_id
            time.sleep(0.5)

        ontology["dataflows"][flow_id] = build_dataflow_entry(flow, dsd_data)

    ontology["stats"] = compute_stats(ontology)

    print(f"\nWriting ontology to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(ontology, f, indent=2, ensure_ascii=False)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Done. Output: {output_path} ({size_mb:.1f} MB)")
    print(f"\nStats:")
    for k, v in ontology["stats"].items():
        if k != "domains":
            print(f"  {k}: {v}")
    print(f"  domains: {len(ontology['stats']['domains'])} datasets")


def explore_ontology(ontology_path=None):
    ontology_path = Path(ontology_path) if ontology_path else DEFAULT_OUTPUT
    if not ontology_path.exists():
        print(f"Ontology file not found at {ontology_path}")
        print("Run the scraper first: python bis_ontology_scraper.py scrape")
        return

    with open(ontology_path) as f:
        ont = json.load(f)

    while True:
        print("\n" + "=" * 60)
        print("BIS Data Ontology Explorer")
        print("=" * 60)
        print(f"Generated: {ont['generated']}")
        stats = ont["stats"]
        print(f"Dataflows: {stats['total_dataflows']}")
        print(f"Unique DSDs: {stats['unique_dsds']}")
        print(f"Unique codelists: {stats['unique_codelists']}")
        print(f"Total unique codes: {stats['total_unique_codes']}")
        print()
        print("Commands:")
        print("  1) List all dataflows")
        print("  2) Inspect a dataflow (dimensions, codelists)")
        print("  3) Search codelists by keyword")
        print("  4) Inspect a specific codelist")
        print("  5) Show dimensional cross-reference (which dims appear where)")
        print("  6) Export flat codelist summary")
        print("  q) Quit")
        print()

        choice = input("Select: ").strip().lower()
        if choice == "q":
            break
        elif choice == "1":
            _explore_list_flows(ont)
        elif choice == "2":
            _explore_inspect_flow(ont)
        elif choice == "3":
            _explore_search_codelists(ont)
        elif choice == "4":
            _explore_inspect_codelist(ont)
        elif choice == "5":
            _explore_dimension_xref(ont)
        elif choice == "6":
            _explore_export_flat(ont)
        else:
            print("Invalid choice.")


def _explore_list_flows(ont):
    print("\nAll BIS Dataflows:")
    print("-" * 80)
    for fid, flow in sorted(ont["dataflows"].items()):
        struct = flow.get("structure", {})
        ndim = struct.get("num_dimensions", "?")
        ncl = struct.get("num_codelists", "?")
        print(f"  {fid:<25s} {flow['name']:<45s} dims={ndim} codelists={ncl}")


def _explore_inspect_flow(ont):
    flow_ids = sorted(ont["dataflows"].keys())
    for i, fid in enumerate(flow_ids, 1):
        print(f"  {i:2d}) {fid}: {ont['dataflows'][fid]['name']}")
    sel = input("\nEnter number or flow ID: ").strip()
    try:
        idx = int(sel) - 1
        flow_id = flow_ids[idx]
    except (ValueError, IndexError):
        flow_id = sel

    if flow_id not in ont["dataflows"]:
        print(f"Unknown flow: {flow_id}")
        return

    flow = ont["dataflows"][flow_id]
    struct = flow.get("structure")
    print(f"\n{'=' * 60}")
    print(f"Dataflow: {flow_id}")
    print(f"Name: {flow['name']}")
    if flow.get("description"):
        print(f"Description: {flow['description']}")
    if not struct:
        print("  (No structure data available)")
        return

    print(f"\nDSD: {struct['dsd_id']} v{struct['version']}")
    print(f"Dimensions: {struct['num_dimensions']}  |  Attributes: {struct['num_attributes']}  |  Codelists: {struct['num_codelists']}")
    print(f"\nDIMENSIONS:")
    for d in struct["dimensions"]:
        if d.get("is_time_dimension"):
            print(f"  [{d['position']:2d}] {d['id']:<25s} (time dimension)")
        else:
            ncodes = d.get("num_codes", "?")
            cl_name = d.get("codelist_name", "")
            print(f"  [{d['position']:2d}] {d['id']:<25s} codelist={d.get('codelist_id',''):<25s} ({ncodes} codes) {cl_name}")

    print(f"\nATTRIBUTES:")
    for a in struct["attributes"]:
        cl_name = a.get("codelist_name", "")
        print(f"  {a['id']:<20s} codelist={a.get('codelist_id',''):<25s} {cl_name}")


def _explore_search_codelists(ont):
    keyword = input("Search keyword: ").strip().lower()
    if not keyword:
        return

    seen = set()
    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        for cl_id, cl in struct.get("codelists", {}).items():
            if cl_id in seen:
                continue
            match = keyword in cl_id.lower() or keyword in cl.get("name", "").lower()
            if not match:
                for code_id, code in cl.get("codes", {}).items():
                    if keyword in code_id.lower() or keyword in code.get("name", "").lower():
                        match = True
                        break
            if match:
                seen.add(cl_id)
                print(f"  {cl_id:<30s} {cl.get('name',''):<35s} ({len(cl.get('codes',{}))} codes)  [in {fid}]")


def _explore_inspect_codelist(ont):
    cl_target = input("Codelist ID (e.g. CL_L_INSTR): ").strip()
    if not cl_target:
        return

    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        if cl_target in struct.get("codelists", {}):
            cl = struct["codelists"][cl_target]
            print(f"\nCodelist: {cl['id']}")
            print(f"Name: {cl.get('name', '')}")
            if cl.get("description"):
                print(f"Description: {cl['description']}")
            print(f"Codes ({len(cl['codes'])}):")
            for code_id, code in sorted(cl["codes"].items()):
                parent_str = f"  [parent: {code['parent']}]" if code.get("parent") else ""
                print(f"  {code_id:<12s} {code.get('name','')}{parent_str}")
                if code.get("description"):
                    desc = code["description"][:120]
                    print(f"               {desc}{'...' if len(code.get('description',''))>120 else ''}")
            return
    print(f"Codelist {cl_target} not found in any dataflow.")


def _explore_dimension_xref(ont):
    dim_map = {}
    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        for d in struct.get("dimensions", []):
            did = d["id"]
            if did not in dim_map:
                dim_map[did] = {"codelist": d.get("codelist_id", ""), "flows": []}
            dim_map[did]["flows"].append(fid)

    print(f"\nDimension Cross-Reference ({len(dim_map)} unique dimensions):")
    print("-" * 90)
    for did in sorted(dim_map.keys()):
        info = dim_map[did]
        flows_str = ", ".join(info["flows"][:5])
        if len(info["flows"]) > 5:
            flows_str += f" (+{len(info['flows'])-5} more)"
        print(f"  {did:<25s} codelist={info['codelist']:<25s} used in {len(info['flows'])} flows: {flows_str}")


def _explore_export_flat(ont):
    out_path = OUTPUT_DIR / "bis_codelist_summary.json"
    all_codelists = {}
    for fid, flow in ont["dataflows"].items():
        struct = flow.get("structure")
        if not struct:
            continue
        for cl_id, cl in struct.get("codelists", {}).items():
            if cl_id not in all_codelists:
                all_codelists[cl_id] = cl

    with open(out_path, "w") as f:
        json.dump(
            {"total_codelists": len(all_codelists), "codelists": all_codelists},
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Exported {len(all_codelists)} unique codelists to {out_path}")


LBS_DEEP_OUTPUT = OUTPUT_DIR / "lbs_deep_index.json"

REPORTING_COUNTRIES_ACTUAL = [
    "AT", "AU", "BE", "BH", "BM", "BR", "BS", "CA", "CH", "CL", "CN", "CW",
    "CY", "DE", "DK", "ES", "FI", "FR", "GB", "GG", "GR", "HK", "ID", "IE",
    "IM", "IN", "IT", "JE", "JP", "KR", "KY", "LU", "MO", "MX", "MY", "NL",
    "NO", "PA", "PH", "PT", "RU", "SA", "SE", "SG", "TR", "TW", "US", "ZA",
]

LBS_COUNTRY_NAMES = {
    "AT": "Austria", "AU": "Australia", "BE": "Belgium", "BH": "Bahrain",
    "BM": "Bermuda", "BR": "Brazil", "BS": "Bahamas", "CA": "Canada",
    "CH": "Switzerland", "CL": "Chile", "CN": "China", "CW": "Curacao",
    "CY": "Cyprus", "DE": "Germany", "DK": "Denmark", "ES": "Spain",
    "FI": "Finland", "FR": "France", "GB": "United Kingdom", "GG": "Guernsey",
    "GR": "Greece", "HK": "Hong Kong SAR", "ID": "Indonesia", "IE": "Ireland",
    "IM": "Isle of Man", "IN": "India", "IT": "Italy", "JE": "Jersey",
    "JP": "Japan", "KR": "Korea", "KY": "Cayman Islands", "LU": "Luxembourg",
    "MO": "Macao SAR", "MX": "Mexico", "MY": "Malaysia", "NL": "Netherlands",
    "NO": "Norway", "PA": "Panama", "PH": "Philippines", "PT": "Portugal",
    "RU": "Russia", "SA": "Saudi Arabia", "SE": "Sweden", "SG": "Singapore",
    "TR": "Turkey", "TW": "Chinese Taipei", "US": "United States", "ZA": "South Africa",
    "5A": "All reporting countries", "5C": "Euro area",
}


def availability_query(key_filter, max_retries=3):
    url = f"{BASE_URL}/availability/dataflow/BIS/WS_LBS_D_PUB/1.0/{key_filter}"
    params = {"mode": "available", "references": "none", "format": "sdmx-json"}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                constraint = data["data"]["contentConstraints"][0]
                annots = {a["id"]: a["title"] for a in constraint.get("annotations", [])}
                series_count = int(annots.get("series_count", 0))
                kv_map = {}
                for kv in constraint.get("cubeRegions", [{}])[0].get("keyValues", []):
                    kv_map[kv["id"]] = kv["values"]
                return {"series_count": series_count, "dimensions": kv_map}
            elif resp.status_code == 404:
                return {"series_count": 0, "dimensions": {}}
            elif resp.status_code == 429:
                time.sleep(2 ** (attempt + 1))
                continue
            else:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"    Error: {e}")
                return None
    return None


def deep_index_lbs(output_path=None):
    output_path = Path(output_path) if output_path else LBS_DEEP_OUTPUT
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ontology_path = DEFAULT_OUTPUT
    cl_lookups = {}
    dim_to_codelist = {}
    if ontology_path.exists():
        with open(ontology_path) as f:
            ont = json.load(f)
        lbs_struct = ont.get("dataflows", {}).get("WS_LBS_D_PUB", {}).get("structure", {})
        for cl_id, cl in lbs_struct.get("codelists", {}).items():
            cl_lookups[cl_id] = {code_id: code.get("name", code_id) for code_id, code in cl.get("codes", {}).items()}
        for dim in lbs_struct.get("dimensions", []):
            if dim.get("codelist_id"):
                dim_to_codelist[dim["id"]] = dim["codelist_id"]

    def resolve(code, dim_id=None):
        if dim_id and dim_id in dim_to_codelist:
            cl_id = dim_to_codelist[dim_id]
            if cl_id in cl_lookups and code in cl_lookups[cl_id]:
                return cl_lookups[cl_id][code]
        for cl_id, codes in cl_lookups.items():
            if code in codes:
                return codes[code]
        return code

    def resolve_dim(codes, dim_id):
        return {c: resolve(c, dim_id) for c in codes}

    print("=" * 70)
    print("BIS Locational Banking Statistics - Deep Index Builder")
    print("=" * 70)

    # Key format: FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE

    print("\n[1/4] Querying global LBS availability...")
    global_avail = availability_query("Q.S....A.5J.A....") 
    if not global_avail or global_avail["series_count"] == 0:
        print("FATAL: Could not query global availability")
        return

    print(f"  Total LBS series (stocks, all banks, all parent=5J): {global_avail['series_count']}")
    rep_countries = global_avail["dimensions"].get("L_REP_CTY", [])
    cp_countries = global_avail["dimensions"].get("L_CP_COUNTRY", [])
    instruments = global_avail["dimensions"].get("L_INSTR", [])
    positions = global_avail["dimensions"].get("L_POSITION", [])
    sectors = global_avail["dimensions"].get("L_CP_SECTOR", [])
    currencies = global_avail["dimensions"].get("L_DENOM", [])

    iso_rep = [c for c in rep_countries if len(c) == 2]
    iso_cp = [c for c in cp_countries if len(c) == 2 and not c.startswith(("1", "2", "3", "4", "5", "6", "7", "8", "9"))]

    print(f"  Reporting countries: {len(iso_rep)}")
    print(f"  Counterparty countries (ISO): {len(iso_cp)}")
    instr_display = [f"{i}={resolve(i, 'L_INSTR')}" for i in instruments]
    pos_display = [f"{p}={resolve(p, 'L_POSITION')}" for p in positions]
    print(f"  Instruments available: {instr_display}")
    print(f"  Positions: {pos_display}")
    print(f"  Sectors: {len(sectors)}")
    print(f"  Currencies: {currencies}")

    index = {
        "version": "1.0",
        "source": "BIS Locational Banking Statistics (LBS)",
        "dataflow": "WS_LBS_D_PUB",
        "generated": datetime.now(timezone.utc).isoformat(),
        "global_summary": {
            "total_cross_border_series": global_avail["series_count"],
            "reporting_countries": len(iso_rep),
            "counterparty_countries_iso": len(iso_cp),
            "instruments": resolve_dim(instruments, "L_INSTR"),
            "positions": resolve_dim(positions, "L_POSITION"),
            "sectors": resolve_dim(sectors, "L_CP_SECTOR"),
            "currencies": currencies,
        },
        "reporting_countries": {},
        "cross_border_matrix": {},
    }

    print(f"\n[2/4] Querying per-reporting-country availability ({len(iso_rep)} countries)...")
    total = len(iso_rep)
    for idx, rep in enumerate(sorted(iso_rep), 1):
        rep_name = LBS_COUNTRY_NAMES.get(rep, rep)
        if idx % 5 == 1 or idx == total:
            print(f"  [{idx}/{total}] {rep} ({rep_name})...")

        # Claims: all instruments, all currencies, all sectors, cross-border only
        claims_avail = availability_query(f"Q.S.C..TO1.A.5J.A.{rep}...N")
        # Liabilities: same
        liab_avail = availability_query(f"Q.S.L..TO1.A.5J.A.{rep}...N")

        claims_cp = []
        claims_instruments = []
        claims_sectors = []
        claims_series = 0
        if claims_avail and claims_avail["series_count"] > 0:
            claims_cp = claims_avail["dimensions"].get("L_CP_COUNTRY", [])
            claims_instruments = claims_avail["dimensions"].get("L_INSTR", [])
            claims_sectors = claims_avail["dimensions"].get("L_CP_SECTOR", [])
            claims_series = claims_avail["series_count"]

        liab_cp = []
        liab_instruments = []
        liab_sectors = []
        liab_series = 0
        if liab_avail and liab_avail["series_count"] > 0:
            liab_cp = liab_avail["dimensions"].get("L_CP_COUNTRY", [])
            liab_instruments = liab_avail["dimensions"].get("L_INSTR", [])
            liab_sectors = liab_avail["dimensions"].get("L_CP_SECTOR", [])
            liab_series = liab_avail["series_count"]

        claims_cp_iso = sorted([c for c in claims_cp if len(c) == 2 and not c[0].isdigit()])
        liab_cp_iso = sorted([c for c in liab_cp if len(c) == 2 and not c[0].isdigit()])

        index["reporting_countries"][rep] = {
            "name": rep_name,
            "claims": {
                "series_count": claims_series,
                "counterparty_countries": claims_cp_iso,
                "counterparty_count": len(claims_cp_iso),
                "instruments": resolve_dim(claims_instruments, "L_INSTR"),
                "sectors": resolve_dim(claims_sectors, "L_CP_SECTOR"),
            },
            "liabilities": {
                "series_count": liab_series,
                "counterparty_countries": liab_cp_iso,
                "counterparty_count": len(liab_cp_iso),
                "instruments": resolve_dim(liab_instruments, "L_INSTR"),
                "sectors": resolve_dim(liab_sectors, "L_CP_SECTOR"),
            },
        }

        for cp in claims_cp_iso:
            key = f"{rep}->{cp}"
            if key not in index["cross_border_matrix"]:
                index["cross_border_matrix"][key] = {"from": rep, "from_name": rep_name, "to": cp, "to_name": resolve(cp, "L_CP_COUNTRY")}
            index["cross_border_matrix"][key]["has_claims"] = True

        for cp in liab_cp_iso:
            key = f"{rep}->{cp}"
            if key not in index["cross_border_matrix"]:
                index["cross_border_matrix"][key] = {"from": rep, "from_name": rep_name, "to": cp, "to_name": resolve(cp, "L_CP_COUNTRY")}
            index["cross_border_matrix"][key]["has_liabilities"] = True

        time.sleep(0.3)

    print(f"\n[3/4] Querying currency breakdowns for major reporting countries...")
    major_reporters = ["US", "GB", "JP", "DE", "FR", "CH", "HK", "SG", "CA", "AU"]
    for rep in major_reporters:
        if rep not in index["reporting_countries"]:
            continue
        rep_name = LBS_COUNTRY_NAMES.get(rep, rep)
        print(f"  {rep} ({rep_name}): currency breakdown...")
        ccy_avail = availability_query(f"Q.S...+TO1+USD+EUR+JPY+GBP+CHF+TO3+UN9.A+D+F.5J.A.{rep}....") 
        if ccy_avail and ccy_avail["series_count"] > 0:
            ccy_list = ccy_avail["dimensions"].get("L_DENOM", [])
            index["reporting_countries"][rep]["currency_breakdown"] = ccy_list
        time.sleep(0.3)

    # Bank nationality breakdown for key reporters
    print(f"\n[3b/4] Querying bank nationality breakdown for major reporters...")
    for rep in major_reporters:
        if rep not in index["reporting_countries"]:
            continue
        nat_avail = availability_query(f"Q.S.C.A.TO1.A..A+D+B+S.{rep}.A..N")
        if nat_avail and nat_avail["series_count"] > 0:
            parent_countries = nat_avail["dimensions"].get("L_PARENT_CTY", [])
            bank_types = nat_avail["dimensions"].get("L_REP_BANK_TYPE", [])
            index["reporting_countries"][rep]["bank_nationalities"] = sorted(parent_countries)
            index["reporting_countries"][rep]["bank_types"] = resolve_dim(bank_types, "L_REP_BANK_TYPE")
        time.sleep(0.3)

    print(f"\n[4/4] Computing statistics and writing output...")

    total_links = len(index["cross_border_matrix"])
    bidirectional = 0
    for key, link in index["cross_border_matrix"].items():
        if link.get("has_claims") and link.get("has_liabilities"):
            bidirectional += 1

    index["deep_stats"] = {
        "total_cross_border_links": total_links,
        "bidirectional_links": bidirectional,
        "claims_only_links": sum(1 for l in index["cross_border_matrix"].values() if l.get("has_claims") and not l.get("has_liabilities")),
        "liabilities_only_links": sum(1 for l in index["cross_border_matrix"].values() if l.get("has_liabilities") and not l.get("has_claims")),
        "avg_counterparties_per_reporter_claims": round(
            sum(r["claims"]["counterparty_count"] for r in index["reporting_countries"].values()) / max(len(index["reporting_countries"]), 1), 1
        ),
        "avg_counterparties_per_reporter_liabilities": round(
            sum(r["liabilities"]["counterparty_count"] for r in index["reporting_countries"].values()) / max(len(index["reporting_countries"]), 1), 1
        ),
        "top_reporters_by_claims_coverage": sorted(
            [(rep, data["claims"]["counterparty_count"]) for rep, data in index["reporting_countries"].items()],
            key=lambda x: -x[1],
        )[:15],
        "top_reporters_by_liabilities_coverage": sorted(
            [(rep, data["liabilities"]["counterparty_count"]) for rep, data in index["reporting_countries"].items()],
            key=lambda x: -x[1],
        )[:15],
    }

    with open(output_path, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nDone. Output: {output_path} ({size_mb:.1f} MB)")
    print(f"\nDeep Index Stats:")
    print(f"  Total cross-border links: {total_links}")
    print(f"  Bidirectional links: {bidirectional}")
    print(f"  Avg counterparties per reporter (claims): {index['deep_stats']['avg_counterparties_per_reporter_claims']}")
    print(f"  Avg counterparties per reporter (liabilities): {index['deep_stats']['avg_counterparties_per_reporter_liabilities']}")
    print(f"\n  Top 10 reporters by claims coverage:")
    for rep, cnt in index["deep_stats"]["top_reporters_by_claims_coverage"][:10]:
        print(f"    {rep} ({LBS_COUNTRY_NAMES.get(rep, rep)}): {cnt} counterparty countries")


# ── Data Query Engine ─────────────────────────────────────────────────────────

DATA_OUTPUT_DIR = Path(__file__).parent / "data"

DATAFLOW_ALIASES = {
    "lbs": "WS_LBS_D_PUB",
    "cbs": "WS_CBS_PUB",
    "credit": "WS_TC",
    "credit-gap": "WS_CREDIT_GAP",
    "dsr": "WS_DSR",
    "property": "WS_SPP",
    "commercial-property": "WS_CPP",
    "eer": "WS_EER",
    "policy-rates": "WS_CBPOL",
    "etd": "WS_XTD_DERIV",
    "otc": "WS_OTC_DERIV2",
    "liquidity": "WS_GLI",
    "debt-securities": "WS_DEBT_SEC2_PUB",
    "fx": "WS_EER",
    "cpi": "WS_LONG_CPI",
}


def data_query(dataflow, key="all", start_period=None, end_period=None,
               detail="full", max_retries=3):
    """Fetch actual BIS time series data via SDMX data API.

    Args:
        dataflow: Dataflow ID (e.g. 'WS_CBPOL') or alias (e.g. 'policy-rates')
        key: Dimension filter string. 'all' for everything, or period-separated
             dimension values (e.g. 'M...US' for monthly US data).
             Use '+' for OR within a dimension: 'M...US+GB+JP'
        start_period: Start period (e.g. '2020-Q1', '2020-01', '2020')
        end_period: End period
        detail: 'full' (data+attributes), 'dataonly', 'serieskeysonly', 'nodata'

    Returns:
        List of series dicts: {key, dimensions, attributes, observations}
    """
    flow_id = DATAFLOW_ALIASES.get(dataflow, dataflow)
    url = f"{BASE_URL}/data/dataflow/BIS/{flow_id}/1.0/{key}"

    params = {"format": "sdmx-json", "detail": detail}
    if start_period:
        params["startPeriod"] = start_period
    if end_period:
        params["endPeriod"] = end_period

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=DATA_HEADERS, params=params, timeout=120)
            if resp.status_code == 200:
                return _parse_sdmx_data(resp.json())
            elif resp.status_code == 404:
                print(f"  No data found for {flow_id} / {key}")
                return []
            elif resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  HTTP {resp.status_code} for data query: {flow_id}/{key}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return []
        except requests.exceptions.Timeout:
            print(f"  Timeout on data query, retry {attempt+1}/{max_retries}")
            time.sleep(3)
        except Exception as e:
            print(f"  Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                return []
    return []


def _parse_sdmx_data(raw):
    """Parse SDMX-JSON data response into a list of series."""
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
    series_data = ds.get("series", {})

    for series_key_str, series_obj in series_data.items():
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

        attributes = {}
        for i, attr_def in enumerate(attr_defs):
            attr_vals = attr_def.get("values", [])
            attr_indices = series_obj.get("attributes", [])
            if i < len(attr_indices) and attr_indices[i] is not None:
                aidx = attr_indices[i]
                if aidx < len(attr_vals):
                    attributes[attr_def.get("id", f"attr_{i}")] = attr_vals[aidx].get("name", "")

        observations = {}
        for obs_key, obs_val in series_obj.get("observations", {}).items():
            obs_idx = int(obs_key)
            period = time_values[obs_idx] if obs_idx < len(time_values) else obs_key
            value = obs_val[0] if obs_val else None
            observations[period] = value

        series_list.append({
            "key": ".".join(key_parts),
            "dimensions": dimensions,
            "attributes": attributes,
            "observations": observations,
        })

    return series_list


def _format_series_table(series_list, max_series=20, last_n_periods=12):
    """Format series data as readable output."""
    if not series_list:
        print("  No data returned.")
        return

    print(f"\n  {len(series_list)} series returned\n")

    for i, s in enumerate(series_list[:max_series]):
        dim_str = " | ".join(f"{v['name']}" for v in s["dimensions"].values() if v.get("name"))
        print(f"  [{i+1}] {dim_str}")
        print(f"      Key: {s['key']}")

        obs = s["observations"]
        if obs:
            sorted_periods = sorted(obs.keys())
            recent = sorted_periods[-last_n_periods:] if len(sorted_periods) > last_n_periods else sorted_periods
            values_str = "  ".join(
                f"{p}={obs[p]:.2f}" if obs[p] is not None else f"{p}=N/A"
                for p in recent
            )
            print(f"      {values_str}")
        print()

    if len(series_list) > max_series:
        print(f"  ... and {len(series_list) - max_series} more series")


def _save_data_json(data, filename):
    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_OUTPUT_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved {path}")
    return str(path)


def _series_to_csv_rows(series_list):
    rows = []
    for s in series_list:
        dim_flat = {k: v["id"] for k, v in s["dimensions"].items()}
        dim_names = {f"{k}_name": v["name"] for k, v in s["dimensions"].items()}
        for period, value in sorted(s["observations"].items()):
            row = {"period": period, "value": value, "key": s["key"]}
            row.update(dim_flat)
            row.update(dim_names)
            rows.append(row)
    return rows


# ── Pre-Built Data Recipes ────────────────────────────────────────────────────

def recipe_policy_rates(countries="US+GB+JP+DE+CH+CA+AU+SE+NO+NZ",
                        start="2000", end=None):
    """Central bank policy rates for major economies."""
    print(f"\n=== Central Bank Policy Rates ===\n")
    key = f"M.{countries}"
    series = data_query("WS_CBPOL", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=30, last_n_periods=12)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"policy-rates/{key}", "series": series},
                        f"policy_rates_{ts}.json")
    return series


def recipe_total_credit(countries="US+GB+JP+DE+FR+CN+CA+AU",
                        start="2000", end=None):
    """Total credit to non-financial sector (% of GDP and nominal)."""
    print(f"\n=== Total Credit to Non-Financial Sector ===\n")
    key = f"Q.{countries}.P.A.M.XDC.A"
    series = data_query("WS_TC", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"credit/{key}", "series": series},
                        f"total_credit_{ts}.json")
    return series


def recipe_credit_gap(countries="US+GB+JP+DE+FR+CN+CA+AU",
                      start="2000", end=None):
    """Credit-to-GDP gaps (BIS deviation from trend)."""
    print(f"\n=== Credit-to-GDP Gaps ===\n")
    key = f"Q.{countries}.B"
    series = data_query("WS_CREDIT_GAP", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"credit-gap/{key}", "series": series},
                        f"credit_gap_{ts}.json")
    return series


def recipe_dsr(countries="US+GB+JP+DE+FR+CN+CA+AU",
               start="2000", end=None):
    """Debt service ratios for the private non-financial sector."""
    print(f"\n=== Debt Service Ratios ===\n")
    key = f"Q.{countries}.P"
    series = data_query("WS_DSR", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"dsr/{key}", "series": series},
                        f"dsr_{ts}.json")
    return series


def recipe_property_prices(countries="US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR",
                           start="2000", end=None):
    """Residential property prices (real, index)."""
    print(f"\n=== Residential Property Prices ===\n")
    key = f"Q.N.{countries}"
    series = data_query("WS_SPP", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"property/{key}", "series": series},
                        f"property_prices_{ts}.json")
    return series


def recipe_eer(countries="US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX",
               start="2000", end=None):
    """Effective exchange rates (real and nominal, broad basket)."""
    print(f"\n=== Effective Exchange Rates ===\n")
    key = f"M.R.B.{countries}"
    series = data_query("WS_EER", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=12)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"eer/{key}", "series": series},
                        f"eer_{ts}.json")
    return series


def recipe_global_liquidity(start="2010", end=None):
    """Global liquidity indicators: USD credit to non-bank borrowers outside US."""
    print(f"\n=== Global Liquidity Indicators ===\n")
    series = data_query("WS_GLI", key="all", start_period=start, end_period=end)
    _format_series_table(series, max_series=30, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": "liquidity/all", "series": series},
                        f"global_liquidity_{ts}.json")
    return series


def recipe_lbs_crossborder(reporter="US", position="C", start="2010", end=None):
    """Locational banking: cross-border claims/liabilities for a reporting country."""
    print(f"\n=== LBS Cross-Border: {reporter} ({position}) ===\n")
    pos = "C" if position.upper().startswith("C") else "L"
    key = f"Q.S.{pos}.A.TO1.A.5J.A.{reporter}.A..N"
    series = data_query("WS_LBS_D_PUB", key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=20, last_n_periods=8)
    if series:
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json({"query": f"lbs/{key}", "series": series},
                        f"lbs_{reporter}_{pos}_{ts}.json")
    return series


def _cmd_data_query(dataflow, key="all", start=None, end=None, save=True):
    """Generic data query command."""
    print(f"\n=== BIS Data Query: {dataflow} / {key} ===\n")
    series = data_query(dataflow, key=key, start_period=start, end_period=end)
    _format_series_table(series, max_series=30, last_n_periods=12)
    if save and series:
        flow_id = DATAFLOW_ALIASES.get(dataflow, dataflow)
        ts = time.strftime("%Y%m%d_%H%M%S")
        _save_data_json(
            {"query": f"{flow_id}/{key}", "start": start, "end": end, "series": series},
            f"query_{flow_id}_{ts}.json")
    return series


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BIS Data Ontology Scraper, Explorer & Data Query Engine")
    subparsers = parser.add_subparsers(dest="command")

    scrape_p = subparsers.add_parser("scrape", help="Scrape full BIS ontology from SDMX API")
    scrape_p.add_argument("--output", "-o", help="Output JSON path")
    scrape_p.add_argument("--skip-existing", action="store_true", help="Skip if output already exists")

    explore_p = subparsers.add_parser("explore", help="Interactively explore the ontology")
    explore_p.add_argument("--input", "-i", help="Path to ontology JSON")

    deep_p = subparsers.add_parser("deep-index", help="Build deep LBS cross-border index")
    deep_p.add_argument("--output", "-o", help="Output JSON path")

    query_p = subparsers.add_parser("query", help="Query BIS time series data")
    query_p.add_argument("dataflow", help="Dataflow ID or alias (e.g. policy-rates, credit, lbs)")
    query_p.add_argument("--key", "-k", default="all", help="Dimension key filter (default: all)")
    query_p.add_argument("--start", "-s", help="Start period (e.g. 2020, 2020-Q1)")
    query_p.add_argument("--end", "-e", help="End period")

    sub_pr = subparsers.add_parser("policy-rates", help="Central bank policy rates")
    sub_pr.add_argument("--countries", default="US+GB+JP+DE+CH+CA+AU+SE+NO+NZ")
    sub_pr.add_argument("--start", default="2000")

    sub_tc = subparsers.add_parser("total-credit", help="Total credit to non-financial sector")
    sub_tc.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU")
    sub_tc.add_argument("--start", default="2000")

    sub_cg = subparsers.add_parser("credit-gap", help="Credit-to-GDP gaps")
    sub_cg.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU")
    sub_cg.add_argument("--start", default="2000")

    sub_dsr = subparsers.add_parser("dsr", help="Debt service ratios")
    sub_dsr.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU")
    sub_dsr.add_argument("--start", default="2000")

    sub_pp = subparsers.add_parser("property-prices", help="Residential property prices")
    sub_pp.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR")
    sub_pp.add_argument("--start", default="2000")

    sub_eer = subparsers.add_parser("eer", help="Effective exchange rates")
    sub_eer.add_argument("--countries", default="US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX")
    sub_eer.add_argument("--start", default="2000")

    sub_gli = subparsers.add_parser("global-liquidity", help="Global liquidity indicators")
    sub_gli.add_argument("--start", default="2010")

    sub_lbs = subparsers.add_parser("lbs", help="Locational banking cross-border data")
    sub_lbs.add_argument("--reporter", default="US", help="Reporting country (default: US)")
    sub_lbs.add_argument("--position", default="C", choices=["C", "L"], help="Claims or Liabilities")
    sub_lbs.add_argument("--start", default="2010")

    args = parser.parse_args()

    if args.command == "scrape":
        scrape_full_ontology(output_path=args.output, skip_existing=args.skip_existing)
    elif args.command == "explore":
        explore_ontology(ontology_path=args.input)
    elif args.command == "deep-index":
        deep_index_lbs(output_path=args.output)
    elif args.command == "query":
        _cmd_data_query(args.dataflow, key=args.key, start=args.start, end=args.end)
    elif args.command == "policy-rates":
        recipe_policy_rates(countries=args.countries, start=args.start)
    elif args.command == "total-credit":
        recipe_total_credit(countries=args.countries, start=args.start)
    elif args.command == "credit-gap":
        recipe_credit_gap(countries=args.countries, start=args.start)
    elif args.command == "dsr":
        recipe_dsr(countries=args.countries, start=args.start)
    elif args.command == "property-prices":
        recipe_property_prices(countries=args.countries, start=args.start)
    elif args.command == "eer":
        recipe_eer(countries=args.countries, start=args.start)
    elif args.command == "global-liquidity":
        recipe_global_liquidity(start=args.start)
    elif args.command == "lbs":
        recipe_lbs_crossborder(reporter=args.reporter, position=args.position, start=args.start)
    else:
        interactive_menu()


def interactive_menu():
    while True:
        print("\n" + "=" * 55)
        print("BIS Data: Ontology, Explorer & Data Query Engine")
        print("=" * 55)
        print()
        print("  Ontology & Metadata")
        print("    1) Scrape full BIS ontology from SDMX API")
        print("    2) Explore existing ontology")
        print("    3) Scrape + Explore")
        print("    4) Deep-index LBS (cross-border relations)")
        print("    5) Full pipeline (scrape + deep-index)")
        print()
        print("  Data Queries (time series)")
        print("   10) Central bank policy rates")
        print("   11) Total credit to non-financial sector")
        print("   12) Credit-to-GDP gaps")
        print("   13) Debt service ratios")
        print("   14) Residential property prices")
        print("   15) Effective exchange rates (REER/NEER)")
        print("   16) Global liquidity indicators")
        print("   17) LBS cross-border banking (claims/liabilities)")
        print("   18) Custom data query (any dataflow + key)")
        print()
        print("    q) Quit")
        print()
        choice = input("Select: ").strip().lower()
        if choice == "q":
            break
        elif choice == "1":
            scrape_full_ontology()
        elif choice == "2":
            explore_ontology()
        elif choice == "3":
            scrape_full_ontology()
            explore_ontology()
        elif choice == "4":
            deep_index_lbs()
        elif choice == "5":
            scrape_full_ontology()
            deep_index_lbs()
        elif choice == "10":
            countries = input("  Countries [US+GB+JP+DE+CH+CA+AU+SE+NO+NZ]: ").strip() or "US+GB+JP+DE+CH+CA+AU+SE+NO+NZ"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_policy_rates(countries=countries, start=start)
        elif choice == "11":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_total_credit(countries=countries, start=start)
        elif choice == "12":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_credit_gap(countries=countries, start=start)
        elif choice == "13":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_dsr(countries=countries, start=start)
        elif choice == "14":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR]: ").strip() or "US+GB+JP+DE+FR+CN+CA+AU+NZ+SE+NO+KR"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_property_prices(countries=countries, start=start)
        elif choice == "15":
            countries = input("  Countries [US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX]: ").strip() or "US+GB+JP+DE+FR+CN+CH+CA+AU+SE+NO+NZ+KR+IN+BR+MX"
            start = input("  Start period [2000]: ").strip() or "2000"
            recipe_eer(countries=countries, start=start)
        elif choice == "16":
            start = input("  Start period [2010]: ").strip() or "2010"
            recipe_global_liquidity(start=start)
        elif choice == "17":
            reporter = input("  Reporter country [US]: ").strip() or "US"
            pos = input("  Position [C=Claims, L=Liabilities]: ").strip() or "C"
            start = input("  Start period [2010]: ").strip() or "2010"
            recipe_lbs_crossborder(reporter=reporter, position=pos, start=start)
        elif choice == "18":
            print("  Available dataflow aliases: " + ", ".join(sorted(DATAFLOW_ALIASES.keys())))
            dataflow = input("  Dataflow (ID or alias): ").strip()
            if not dataflow:
                continue
            key = input("  Key filter [all]: ").strip() or "all"
            start = input("  Start period [2000]: ").strip() or "2000"
            end = input("  End period [latest]: ").strip() or None
            _cmd_data_query(dataflow, key=key, start=start, end=end)
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
