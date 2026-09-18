#!/usr/bin/env python3
"""Acquire the OpenStreetMap street / path network for the Miami walk model (contract §5 W01–W02, rules doc 规则 6).

One Overpass query: every way carrying a `highway` tag inside the study window expanded by 0.01° (about 1 km), plus every
node those ways reference (`>`), so that paths leaving and re-entering the window are complete near its edge. The
walkability filter is NOT applied here (raw stays raw; the walk-model stage applies it and records the rule). Everything
lands under raw/miami/2026-09-17/osm/ with the query text, the Overpass data timestamp (osm_base), bytes, sha256,
retrieval time and the ODbL attribution in osm_source_manifest.json.
    python3 scripts/fetch_miami_osm_walk_network.py [--validate-only]
The main Overpass endpoints answer HTTP 406 to this client; the kumi.systems mirror is used and its data lags the main
instance (the osm_base timestamp in the response is the truth about data age).
"""
import hashlib, json, os, subprocess, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw/miami/2026-09-17/osm"
MANIFEST = RAW / "osm_source_manifest.json"
VALIDATION = RAW / "osm_acquisition_validation.json"
RESPONSE = RAW / "walk_network_overpass.json"
STUDY_MANIFEST = ROOT / "raw/miami/2026-09-14/source_manifest.json"   # study_bbox_wgs84 = [W, S, E, N]
MARGIN_DEG = 0.01
OVERPASS = "https://overpass.kumi.systems/api/interpreter"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p, o): Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def query_text(bbox):
    w, s, e, n = bbox
    return f'[out:json][timeout:180];(way["highway"]({s},{w},{n},{e}););out body;>;out skel qt;'


def fetch(url, dest, data):
    part = Path(str(dest) + ".part")
    cmd = ["curl", "--fail", "--location", "--silent", "--show-error", "-A", UA, "--max-time", "600", "--retry", "2", "--data-urlencode", data, "--output", str(part), url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not part.exists() or part.stat().st_size == 0: raise SystemExit(f"download failed: {dest.name}: {r.stderr.strip()[:200]}")
    try: json.loads(part.read_text(encoding="utf-8"))
    except Exception: raise SystemExit(f"response is not JSON: {dest.name}: {part.read_text(errors='replace')[:200]}")
    os.replace(part, dest)
    return {"bytes": dest.stat().st_size, "sha256": sha_file(dest), "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def main():
    validate_only = "--validate-only" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    study_bbox = load(STUDY_MANIFEST)["study_bbox_wgs84"]
    fetch_bbox = [round(study_bbox[0] - MARGIN_DEG, 6), round(study_bbox[1] - MARGIN_DEG, 6), round(study_bbox[2] + MARGIN_DEG, 6), round(study_bbox[3] + MARGIN_DEG, 6)]
    q = query_text(fetch_bbox)
    if not validate_only:
        info = fetch(OVERPASS, RESPONSE, "data=" + q)
        osm = load(RESPONSE)
        dump(MANIFEST, {"retrieved_on": "2026-09-17", "acquisition_stage": "miami_osm_walk_network", "study_bbox_wgs84": study_bbox, "margin_deg": MARGIN_DEG, "fetch_bbox_wgs84": fetch_bbox,
                        "bbox_note": "study window expanded by the margin so the network is complete for 15-minute isochrones (which stay inside the window) and for nearest-facility searches inside it; "
                                     "`>` also returns way nodes that lie outside the fetch bbox",
                        "publisher": "OpenStreetMap contributors via Overpass mirror overpass.kumi.systems", "terms": "ODbL 1.0 — attribution '© OpenStreetMap contributors' required",
                        "service_url": OVERPASS, "query": q, "osm_data_timestamp": osm.get("osm3s", {}).get("timestamp_osm_base"), "overpass_generator": osm.get("generator"),
                        "files": {"response": {"file": f"osm/{RESPONSE.name}", "url": OVERPASS, **info}},
                        "fetch_script": {"path": "scripts/fetch_miami_osm_walk_network.py", "sha256": sha_file(Path(__file__))}})
        print(f"fetched  walk_network_overpass  bytes={info['bytes']} osm_base={osm.get('osm3s', {}).get('timestamp_osm_base')}")
    manifest = load(MANIFEST); checks, hard_fail = {}, []
    def hard(name, ok, detail=None):
        checks[name] = {"pass": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok: hard_fail.append(name)
    f = manifest["files"]["response"]; p = ROOT / "raw/miami/2026-09-17" / f["file"]
    hard("response_present_and_sha256_matches", p.exists() and sha_file(p) == f["sha256"])
    osm = load(p); els = osm.get("elements", [])
    ways = [e for e in els if e.get("type") == "way"]; nodes = {e["id"]: e for e in els if e.get("type") == "node"}
    refs_missing = sum(1 for w in ways for n in w.get("nodes", []) if n not in nodes)
    hw = Counter(w.get("tags", {}).get("highway") for w in ways)
    summary = {"ways": len(ways), "nodes": len(nodes), "osm_base": osm.get("osm3s", {}).get("timestamp_osm_base"), "highway_tags": dict(hw.most_common()),
               "foot_tags": dict(Counter(w.get("tags", {}).get("foot") for w in ways).most_common()), "access_tags": dict(Counter(w.get("tags", {}).get("access") for w in ways).most_common()),
               "way_node_references_missing": refs_missing, "fetch_bbox_wgs84": manifest["fetch_bbox_wgs84"]}
    hard("osm_base_timestamp_present", bool(summary["osm_base"]))
    hard("query_matches_study_bbox_plus_margin", manifest["query"] == query_text(manifest["fetch_bbox_wgs84"]) and manifest["study_bbox_wgs84"] == load(STUDY_MANIFEST)["study_bbox_wgs84"])
    hard("at_least_5000_ways", len(ways) >= 5000, len(ways)); hard("at_least_20000_nodes", len(nodes) >= 20000, len(nodes))
    hard("every_way_has_highway_tag", all(w.get("tags", {}).get("highway") for w in ways))
    hard("every_way_node_reference_resolves", refs_missing == 0, refs_missing)
    hard("every_node_has_coordinates", all("lat" in n and "lon" in n for n in nodes.values()))
    v = {"status": "PASS" if not hard_fail else "FAIL", "failed_checks": hard_fail, "checked_on": "2026-09-17", "summary": summary, "checks": checks,
         "scope": "acquisition integrity only: hash, query, counts, referential integrity; the walkability rule is applied and recorded in the walk-model stage"}
    dump(VALIDATION, v); print(f"validation: {v['status']} failed={hard_fail} ways={len(ways)} nodes={len(nodes)} osm_base={summary['osm_base']}")
    sys.exit(0 if v["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
