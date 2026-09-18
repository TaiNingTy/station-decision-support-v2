#!/usr/bin/env python3
"""Acquire the POI sources for the Miami study window (contract §5): schools, parks, clinics, grocery stores.

Per ArcGIS layer: layer metadata (f=pjson), the id list (returnIdsOnly) and the full features as GeoJSON in WGS84 for the
study window envelope; validation checks that the feature count equals the id count and that no transfer limit was hit
(the same pattern as the zoning acquisition). Grocery comes from the USDA SNAP retailer locator (all store types kept
raw; the grocery definition is applied in the layer stage). OpenStreetMap (Overpass mirror) is kept only as a
cross-check for grocery, with the query text and the data timestamp. Everything lands under raw/miami/2026-09-17/poi/
with url, bytes, sha256, retrieval time and terms in poi_source_manifest.json.
    python3 scripts/fetch_miami_poi.py [--validate-only]
"""
import hashlib, json, os, subprocess, sys, time, urllib.parse
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw/miami/2026-09-17/poi"
MANIFEST = RAW / "poi_source_manifest.json"
VALIDATION = RAW / "poi_acquisition_validation.json"
BBOX = "-80.209,25.749,-80.175,25.801"   # the spatial-join study window (raw/miami/2026-09-14/source_manifest.json study_bbox_wgs84)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
COUNTY = "https://gisweb.miamidade.gov/arcgis/rest/services/MD_Emaps/MapServer"
CITY = "https://services1.arcgis.com/CvuPhqcTQpZPT9qY/arcgis/rest/services"
SNAP = "https://services1.arcgis.com/RLQu0rK7h4kbsBq5/arcgis/rest/services/snap_retailer_location_data/FeatureServer/0"
OVERPASS = "https://overpass.kumi.systems/api/interpreter"   # overpass-api.de answers 406 to this client; the mirror lags the main instance
LAYERS = [
    {"layer_id": "school_public", "category": "school", "url": f"{COUNTY}/25", "publisher": "Miami-Dade County (MD_Emaps: Public Schools @ SchoolSite)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "school_charter", "category": "school", "url": f"{COUNTY}/23", "publisher": "Miami-Dade County (MD_Emaps: Charter Schools)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "school_private", "category": "school", "url": f"{COUNTY}/24", "publisher": "Miami-Dade County (MD_Emaps: Private Schools)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "park_city", "category": "park", "url": f"{CITY}/Park_Boundary_Base_Layer/FeatureServer/0", "publisher": "City of Miami (Park_Boundary_Base_Layer)", "terms": "City of Miami open GIS service (same publisher as the M21 zoning layer, CC-BY-4.0 there)"},
    {"layer_id": "park_county", "category": "park", "url": f"{COUNTY}/2", "publisher": "Miami-Dade County (MD_Emaps: County Park Boundaries)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "clinic_fqhc", "category": "clinic", "url": f"{COUNTY}/40", "publisher": "Miami-Dade County (MD_Emaps: Federally Qualified Health Centers)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "clinic_free_standing", "category": "clinic", "url": f"{COUNTY}/41", "publisher": "Miami-Dade County (MD_Emaps: Free Standing Clinics)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "clinic_jhs_primary_care", "category": "clinic", "url": f"{COUNTY}/43", "publisher": "Miami-Dade County (MD_Emaps: Jackson Health System Primary Care Centers)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "clinic_mental_health", "category": "clinic", "url": f"{COUNTY}/44", "publisher": "Miami-Dade County (MD_Emaps: Community Mental Health Centers)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "clinic_school_based", "category": "clinic", "url": f"{COUNTY}/45", "publisher": "Miami-Dade County (MD_Emaps: School-Based Health Clinics)", "terms": "Miami-Dade County public GIS service"},
    {"layer_id": "grocery_snap_all_types", "category": "grocery", "url": SNAP, "publisher": "USDA Food and Nutrition Service, SNAP retailer location data (ArcGIS)", "terms": "U.S. federal public data; all store types kept raw, grocery filter applied downstream"},
]
OSM_QUERY = ('[out:json][timeout:60];(node["shop"~"^(supermarket|grocery|greengrocer)$"](25.749,-80.209,25.801,-80.175);'
             'way["shop"~"^(supermarket|grocery|greengrocer)$"](25.749,-80.209,25.801,-80.175);'
             'relation["shop"~"^(supermarket|grocery|greengrocer)$"](25.749,-80.209,25.801,-80.175););out center;')


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p, o): Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(url, dest, data=None):
    part = Path(str(dest) + ".part"); cmd = ["curl", "--fail", "--location", "--silent", "--show-error", "-A", UA, "--max-time", "180", "--retry", "3", "--output", str(part)]
    if data is not None: cmd += ["--data-urlencode", data]
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not part.exists() or part.stat().st_size == 0: raise SystemExit(f"download failed: {dest.name}: {r.stderr.strip()[:200]}")
    try: json.loads(part.read_text(encoding="utf-8"))
    except Exception: raise SystemExit(f"response is not JSON: {dest.name}: {part.read_text(errors='replace')[:200]}")
    os.replace(part, dest)
    return {"bytes": dest.stat().st_size, "sha256": sha_file(dest), "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def arcgis_urls(base):
    env = urllib.parse.quote(BBOX)
    common = f"where=1%3D1&geometry={env}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects"
    return {"metadata": f"{base}?f=pjson", "ids": f"{base}/query?{common}&returnIdsOnly=true&f=json",
            "geojson": f"{base}/query?{common}&outFields=%2A&outSR=4326&returnGeometry=true&resultRecordCount=2000&f=geojson"}


def main():
    validate_only = "--validate-only" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    if not validate_only:
        sources = []
        for L in LAYERS:
            urls = arcgis_urls(L["url"]); files = {}
            for kind, url in urls.items():
                dest = RAW / f"{L['layer_id']}.{kind}.json"; info = fetch(url, dest)
                files[kind] = {"file": f"poi/{dest.name}", "url": url, **info}
            oid = load(RAW / f"{L['layer_id']}.metadata.json").get("objectIdField")
            if oid:   # deterministic order for the archive: re-fetch ordered by the object id field
                url = urls["geojson"] + f"&orderByFields={urllib.parse.quote(oid)}"; dest = RAW / f"{L['layer_id']}.geojson.json"
                info = fetch(url, dest); files["geojson"] = {"file": f"poi/{dest.name}", "url": url, **info}
            sources.append({**{k: v for k, v in L.items() if k != "url"}, "service_url": L["url"], "files": files})
            print(f"fetched  {L['layer_id']:26s} features={len(load(RAW / (L['layer_id'] + '.geojson.json')).get('features', []))}")
        dest = RAW / "osm_grocery_overpass.json"; info = fetch(OVERPASS, dest, data="data=" + OSM_QUERY)
        osm = load(dest)
        sources.append({"layer_id": "osm_grocery_crosscheck", "category": "grocery", "publisher": "OpenStreetMap contributors via Overpass mirror overpass.kumi.systems",
                        "terms": "ODbL 1.0 — attribution '© OpenStreetMap contributors' required; cross-check only, not merged", "service_url": OVERPASS, "query": OSM_QUERY,
                        "osm_data_timestamp": osm.get("osm3s", {}).get("timestamp_osm_base"), "files": {"response": {"file": f"poi/{dest.name}", "url": OVERPASS, **info}}})
        print(f"fetched  osm_grocery_crosscheck      elements={len(osm.get('elements', []))} osm_base={osm.get('osm3s', {}).get('timestamp_osm_base')}")
        dump(MANIFEST, {"retrieved_on": "2026-09-17", "acquisition_stage": "miami_poi", "study_bbox_wgs84": [float(x) for x in BBOX.split(",")],
                        "bbox_note": "the spatial-join extraction window; every station band lies inside it with margin, so POIs inside any band are inside the window; "
                                     "'nearest facility' searches are limited to this window",
                        "category_sources": {"school": ["school_public", "school_charter", "school_private"], "park": ["park_city", "park_county"],
                                             "clinic": ["clinic_fqhc", "clinic_free_standing", "clinic_jhs_primary_care", "clinic_mental_health", "clinic_school_based"],
                                             "grocery": ["grocery_snap_all_types (filtered to supermarket / super store / grocery store downstream)"], "grocery_crosscheck": ["osm_grocery_crosscheck"]},
                        "fetch_script": {"path": "scripts/fetch_miami_poi.py", "sha256": sha_file(Path(__file__))}, "sources": sources})
    manifest = load(MANIFEST); checks, hard_fail = {}, []
    def hard(name, ok, detail=None):
        checks[name] = {"pass": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok: hard_fail.append(name)
    summary = {}
    for s in manifest["sources"]:
        for kind, f in s["files"].items():
            p = ROOT / "raw/miami/2026-09-17" / f["file"]; hard(f"{s['layer_id']}_{kind}_present_and_sha256_matches", p.exists() and sha_file(p) == f["sha256"])
        if s["layer_id"].startswith("osm"):
            osm = load(ROOT / "raw/miami/2026-09-17" / s["files"]["response"]["file"]); summary[s["layer_id"]] = {"elements": len(osm.get("elements", [])), "osm_base": osm.get("osm3s", {}).get("timestamp_osm_base")}
            hard("osm_crosscheck_has_timestamp", bool(summary[s["layer_id"]]["osm_base"])); continue
        ids = load(ROOT / "raw/miami/2026-09-17" / s["files"]["ids"]["file"]); gj = load(ROOT / "raw/miami/2026-09-17" / s["files"]["geojson"]["file"]); meta = load(ROOT / "raw/miami/2026-09-17" / s["files"]["metadata"]["file"])
        n_ids = len(ids.get("objectIds") or []); feats = gj.get("features", []); oid = ids.get("objectIdFieldName") or meta.get("objectIdField")
        fid = {f.get("id") if f.get("id") is not None else f["properties"].get(oid) for f in feats}
        summary[s["layer_id"]] = {"ids": n_ids, "features": len(feats), "geometry_type": meta.get("geometryType"), "object_id_field": oid, "exceeded_transfer_limit": gj.get("exceededTransferLimit", False),
                                  "geometry_types_in_file": sorted({f["geometry"]["type"] for f in feats if f.get("geometry")})}
        hard(f"{s['layer_id']}_feature_count_equals_id_count", len(feats) == n_ids, {"ids": n_ids, "features": len(feats)})
        hard(f"{s['layer_id']}_no_transfer_limit", not gj.get("exceededTransferLimit", False))
        hard(f"{s['layer_id']}_all_features_have_geometry", all(f.get("geometry") for f in feats))
        hard(f"{s['layer_id']}_ids_match", set(ids.get("objectIds") or []) == fid, {"only_ids": sorted(set(ids.get("objectIds") or []) - fid)[:5], "only_features": sorted(fid - set(ids.get("objectIds") or []), key=str)[:5]})
    v = {"status": "PASS" if not hard_fail else "FAIL", "failed_checks": hard_fail, "checked_on": "2026-09-17", "layers": summary, "checks": checks,
         "scope": "acquisition integrity only: counts, ids, transfer limits, geometry presence; category definitions are applied in the POI stage"}
    dump(VALIDATION, v); print(f"validation: {v['status']} failed={hard_fail}")
    sys.exit(0 if v["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
