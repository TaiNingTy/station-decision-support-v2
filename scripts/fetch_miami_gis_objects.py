#!/usr/bin/env python3
"""Acquire the feature-level GIS layers the V2 reading agents work on (step 11): parcels, existing land use, rail lines,
and 2020 Census block counts for the activity-density heat proxy. Roads come from the OpenStreetMap extract that is
already archived (raw/miami/2026-09-17/osm); zoning from the 2026-09-14 acquisition.

Privacy rule: the county's property-record layer (owner names, mailing addresses) is NOT fetched, and the parcel layer is
requested WITHOUT site address and legal description. A parcel keeps only its public folio number, land-use code and
description, lot size, year built, condo flag and municipality code.

ArcGIS layers are read id-first (returnIdsOnly, then chunks of object ids), so the feature count can be checked against
the id count and no transfer limit can silently truncate a layer. Everything lands under raw/miami/2026-09-20/gis_objects/
with url, bytes, sha256 and retrieval time. The Census API key is read from .secrets/census_api_key or CENSUS_API_KEY,
passed to curl through stdin and never stored.
    python3 scripts/fetch_miami_gis_objects.py [--validate-only]
"""
import hashlib, json, os, subprocess, sys, time
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw/miami/2026-09-20/gis_objects"
MANIFEST, VALIDATION = RAW / "gis_objects_source_manifest.json", RAW / "gis_objects_acquisition_validation.json"
STUDY_BBOX = json.loads((ROOT / "raw/miami/2026-09-14/source_manifest.json").read_text(encoding="utf-8"))["study_bbox_wgs84"]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
COUNTY = "https://gisweb.miamidade.gov/arcgis/rest/services/MD_Emaps/MapServer"
CHUNK = 300
LAYERS = [
    {"layer_id": "parcels", "url": f"{COUNTY}/72", "publisher": "Miami-Dade County (MD_Emaps: Parcels @ PaParcel)", "out_fields": "OBJECTID,FOLIO,CONDO_FLAG,MUNICIPALITY_CODE,DOR_CODE_CUR,DOR_DESC,LOT_SIZE,YEAR_BUILT",
     "privacy_note": "site address, legal description and every owner field intentionally not requested; the property-record layer (owner names) is not fetched"},
    {"layer_id": "land_use", "url": f"{COUNTY}/13", "publisher": "Miami-Dade County (MD_Emaps: Land Use @ LUMALanduse)", "out_fields": "OBJECTID,LU,DESCR"},
    {"layer_id": "railroads", "url": f"{COUNTY}/105", "publisher": "Miami-Dade County (MD_Emaps: Railroads)", "out_fields": "OBJECTID"},
    {"layer_id": "metrorail_line", "url": f"{COUNTY}/98", "publisher": "Miami-Dade County (MD_Emaps: MetroRail Line)", "out_fields": "OBJECTID,ROUTE,R_TYPE"},
    {"layer_id": "trirail", "url": f"{COUNTY}/106", "publisher": "Miami-Dade County (MD_Emaps: Tri-rail System)", "out_fields": "*"},
]
PL_URL = "https://api.census.gov/data/2020/dec/pl?get=P1_001N,H1_001N,H1_002N&for=block:*&in=state:12%20county:086%20tract:*"


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p, o): Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def curl_json(url, form=None):
    cmd = ["curl", "--fail", "--location", "--silent", "--show-error", "-A", UA, "--max-time", "240", "--retry", "3"]
    for k, v in (form or {}).items(): cmd += ["--data-urlencode", f"{k}={v}"]
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    if r.returncode != 0: raise SystemExit(f"request failed: {url[:90]}: {r.stderr.strip()[:200]}")
    try: return json.loads(r.stdout)
    except Exception: raise SystemExit(f"response is not JSON: {url[:90]}: {r.stdout[:200]}")


def census_api_key():
    k = os.environ.get("CENSUS_API_KEY", "").strip(); f = ROOT / ".secrets/census_api_key"
    if not k and f.exists() and f.read_text(encoding="utf-8").strip(): k = f.read_text(encoding="utf-8").strip().splitlines()[0].strip()
    return k or None


def fetch_layer(L):
    env = ",".join(str(x) for x in STUDY_BBOX)
    base_q = {"where": "1=1", "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects"}
    meta = curl_json(L["url"] + "?f=pjson"); dump(RAW / f"{L['layer_id']}.metadata.json", meta)
    ids_doc = curl_json(L["url"] + "/query", {**base_q, "returnIdsOnly": "true", "f": "json"}); ids = sorted(ids_doc.get("objectIds") or [])
    dump(RAW / f"{L['layer_id']}.ids.json", {"objectIdFieldName": ids_doc.get("objectIdFieldName"), "objectIds": ids})
    feats = []
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        gj = curl_json(L["url"] + "/query", {"objectIds": ",".join(str(x) for x in chunk), "outFields": L["out_fields"], "outSR": "4326", "returnGeometry": "true", "f": "geojson"})
        if gj.get("exceededTransferLimit"): raise SystemExit(f"{L['layer_id']}: transfer limit hit inside a chunk of {len(chunk)} ids")
        feats += gj.get("features", [])
    oid = ids_doc.get("objectIdFieldName") or "OBJECTID"
    feats.sort(key=lambda f: (f.get("id") if f.get("id") is not None else f["properties"].get(oid)))
    dest = RAW / f"{L['layer_id']}.geojson.json"
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {**{k: v for k, v in L.items() if k != "url"}, "service_url": L["url"], "terms": "Miami-Dade County public GIS service", "study_bbox_wgs84": STUDY_BBOX, "object_ids": len(ids), "features": len(feats),
            "files": {k: {"file": f"gis_objects/{L['layer_id']}.{k}.json", "bytes": (RAW / f"{L['layer_id']}.{k}.json").stat().st_size, "sha256": sha_file(RAW / f"{L['layer_id']}.{k}.json")} for k in ("metadata", "ids", "geojson")},
            "retrieved_at_utc": now()}


def fetch_pl():
    key = census_api_key()
    if not key: return {"layer_id": "census_2020_pl_blocks", "status": "blocked_missing_api_key", "url": PL_URL}
    dest = RAW / "dec_pl_2020_blocks_12086.json"; part = dest.with_name(dest.name + ".part")
    r = subprocess.run(["curl", "-K", "-", "--fail", "--location", "--silent", "--show-error", "--max-time", "600", "--retry", "3", "--output", str(part)], input=f'url = "{PL_URL}&key={key}"\n', capture_output=True, text=True)
    if r.returncode != 0 or not part.exists() or part.read_bytes()[:1] != b"[":
        msg = part.read_text(errors="replace")[:160] if part.exists() else r.stderr[:160]
        if part.exists(): part.unlink()
        raise SystemExit(f"2020 PL pull failed (the key is never stored): {msg!r}")
    os.replace(part, dest)
    return {"layer_id": "census_2020_pl_blocks", "publisher": "U.S. Census Bureau, 2020 Census Redistricting Data (P.L. 94-171), blocks of Miami-Dade County", "url": PL_URL, "api_key_used": True,
            "variables": {"P1_001N": "total population", "H1_001N": "housing units", "H1_002N": "occupied housing units"},
            "note": "2020 Census counts carry disclosure-avoidance noise at block level; used only to shape the activity-density proxy, never as current population",
            "files": {"response": {"file": f"gis_objects/{dest.name}", "bytes": dest.stat().st_size, "sha256": sha_file(dest)}}, "retrieved_at_utc": now(), "status": "downloaded"}


def main():
    validate_only = "--validate-only" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    if not validate_only:
        sources = []
        for L in LAYERS:
            s = fetch_layer(L); sources.append(s); print(f"fetched  {L['layer_id']:16s} ids={s['object_ids']} features={s['features']}")
        pl = fetch_pl(); sources.append(pl); print(f"fetched  census_2020_pl_blocks status={pl.get('status')}")
        dump(MANIFEST, {"retrieved_on": "2026-09-20", "acquisition_stage": "miami_gis_objects", "study_bbox_wgs84": STUDY_BBOX,
                        "roads_source": "raw/miami/2026-09-17/osm/walk_network_overpass.json (OpenStreetMap, already archived)", "zoning_source": "raw/miami/2026-09-14/zoning_study_window.geojson (already archived)",
                        "not_fetched_on_purpose": ["MD_Emaps layer 70 Property Records @ PaGIS (owner names and mailing addresses)", "parcel site address and legal description"],
                        "fetch_script": {"path": "scripts/fetch_miami_gis_objects.py", "sha256": sha_file(Path(__file__))}, "sources": sources})
    m = load(MANIFEST); checks, hard_fail, summary = {}, [], {}
    def hard(name, ok, detail=None):
        checks[name] = {"pass": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok: hard_fail.append(name)
    for s in m["sources"]:
        lid = s["layer_id"]
        if lid == "census_2020_pl_blocks":
            hard("pl_downloaded", s.get("status") == "downloaded", s.get("status"))
            if s.get("status") == "downloaded":
                p = ROOT / "raw/miami/2026-09-20" / s["files"]["response"]["file"]; hard("pl_sha256_matches", sha_file(p) == s["files"]["response"]["sha256"])
                rows = load(p); hdr, body = rows[0], rows[1:]; summary[lid] = {"rows": len(body), "header": hdr, "population_total": sum(int(r[0]) for r in body)}
                hard("pl_header_as_expected", hdr[:3] == ["P1_001N", "H1_001N", "H1_002N"] and hdr[-4:] == ["state", "county", "tract", "block"], hdr)
                hard("pl_at_least_30000_blocks", len(body) >= 30000, len(body)); hard("pl_no_key_in_manifest", "key=" not in json.dumps(m))
            continue
        for k, f in s["files"].items():
            p = ROOT / "raw/miami/2026-09-20" / f["file"]; hard(f"{lid}_{k}_sha256_matches", p.exists() and sha_file(p) == f["sha256"])
        gj = load(ROOT / "raw/miami/2026-09-20" / s["files"]["geojson"]["file"]); ids = load(ROOT / "raw/miami/2026-09-20" / s["files"]["ids"]["file"])["objectIds"]
        feats = gj["features"]; summary[lid] = {"ids": len(ids), "features": len(feats), "geometry_types": dict(Counter(f["geometry"]["type"] for f in feats if f.get("geometry")))}
        hard(f"{lid}_feature_count_equals_id_count", len(feats) == len(ids), {"ids": len(ids), "features": len(feats)})
        hard(f"{lid}_all_features_have_geometry", all(f.get("geometry") for f in feats))
        if lid == "parcels":
            props = [f["properties"] for f in feats]; summary[lid]["dor_codes"] = dict(Counter(f"{p.get('DOR_CODE_CUR')} {p.get('DOR_DESC')}" for p in props).most_common(40))
            no_folio = sum(1 for p in props if not p.get("FOLIO")); no_dor = sum(1 for p in props if p.get("DOR_CODE_CUR") in (None, ""))
            summary[lid]["without_folio"] = no_folio; summary[lid]["without_dor_code"] = no_dor   # attribute-less slivers exist in the source; kept, counted, never read as parcels with a use
            hard("parcels_missing_attributes_below_1_percent", no_folio < 0.01 * len(props) and no_dor < 0.01 * len(props), {"without_folio": no_folio, "without_dor_code": no_dor})
            forbidden = {"TRUE_OWNER1", "TRUE_OWNER2", "TRUE_OWNER3", "TRUE_MAILING_ADDR1", "TRUE_SITE_ADDR", "LEGAL"}
            hard("parcels_carry_no_owner_or_address_fields", not (forbidden & set().union(*[set(p) for p in props[:200]])))
        if lid == "land_use": summary[lid]["descriptions"] = dict(Counter(f["properties"].get("DESCR") for f in feats).most_common(40))
    v = {"status": "PASS" if not hard_fail else "FAIL", "failed_checks": hard_fail, "checked_on": "2026-09-20", "layers": summary, "checks": checks,
         "scope": "acquisition integrity and the privacy rule only; object roles are read by the agents and checked by code in the gis_objects stage"}
    dump(VALIDATION, v); print(f"validation: {v['status']} failed={hard_fail}")
    sys.exit(0 if v["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
