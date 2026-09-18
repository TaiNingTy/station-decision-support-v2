#!/usr/bin/env python3
"""Miami · points of interest around the stations — V2 step 7b, stage `poi` (optional layer for AI interpretation).

Contract §5 and rules doc 规则 6: four product-analysis categories (school, clinic, grocery, park) — NOT a verified local
standard. Per station and band: the number of facilities (points inside the band; park polygons intersecting it) and, per
station and category, the nearest facility by STRAIGHT-LINE distance from the GTFS reference point, searched only inside
the study window. No service-level score. Absence inside the window is `not_found_in_source_within_window`, never
"confirmed absent".
Category rules (recorded in the manifest):
  school  = county public schools with enrollment or grades (administrative sites excluded) + charter + private
  park    = City of Miami park boundaries + county park boundaries that do not duplicate a city polygon
  clinic  = county-listed health facilities (FQHC, free-standing, JHS primary care, mental health, school-based), de-duplicated
  grocery = USDA SNAP retailers of type Supermarket / Super Store / Grocery Store; OpenStreetMap kept as a cross-check count
Publishes poi/pkg-<id>/ atomically (R3); readiness by scripts/miami_readiness.py (R2).
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403
from shapely import make_valid
from shapely.geometry import Point

STAGE = "poi"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_poi_profile.json", "poi_features.json", "poi_evidence.json", "poi_validation.json"]
POI_RAW = RAW15.parent / "2026-09-17/poi"
BAND_KEYS = ["b1", "b2", "b3"]
CATEGORIES = ["school", "clinic", "grocery", "park"]
GROCERY_TYPES = {"Supermarket", "Super Store", "Grocery Store"}
DUP_DISTANCE_M = 50.0
SEMANTICS = {"provenance_class": "observed", "data_nature": "administrative_record", "is_service_level_score": False, "distance_type": "straight_line",
             "distance_origin": "GTFS station reference point (not an entrance)", "search_extent": "study window only (raw/miami/2026-09-14 study_bbox_wgs84)",
             "categories_note": "school / clinic / grocery / park are product-analysis categories; not a verified local standard, not a completeness claim",
             "attribution": ["Miami-Dade County GIS (MD_Emaps)", "City of Miami GIS (Park_Boundary_Base_Layer)", "USDA FNS SNAP retailer location data",
                             "© OpenStreetMap contributors (ODbL), cross-check only"]}

environment = lock_gate()
fwd, inv, transform_record = projection()
proj = lambda g: shp_transform(fwd.transform, g)
src_manifest = load(POI_RAW / "poi_source_manifest.json")
consumed_inputs = [consumed_entry("poi_source_manifest", POI_RAW / "poi_source_manifest.json"), consumed_entry("station_master", DATA / "station_master.geojson")]
raw_files = {}
for s in src_manifest["sources"]:
    for kind, f in s["files"].items():
        p = RAW15.parent / "2026-09-17" / f["file"]
        if sha_file(p) != f["sha256"]: raise SystemExit(f"HALT: {f['file']} sha256 != poi_source_manifest.json")
        raw_files[(s["layer_id"], kind)] = p
        if kind in ("geojson", "response"): consumed_inputs.append(consumed_entry(f"{s['layer_id']}.{kind}", p))
features = lambda layer: load(raw_files[(layer, "geojson")])["features"]

# ---------------- targets (from the demography package) + station reference points ----------------
dem_ptr = load(DATA / "demography_current.json"); dem_dir = DATA / dem_ptr["package_dir"]
ok, dem_manifest, problems = verify_package(dem_dir, "manifest.json")
if not ok: raise SystemExit(f"HALT: demography package does not verify: {problems}")
tg = load(dem_dir / "analysis_targets_26917.json")
targets = {(t["station_id"], t["band_id"]): shape(t["geometry"]) for t in tg["targets"].values()}
RADII_FT = tg["bands"]["radii_ft"]
stations = load(DATA / "station_master.geojson")["features"]
st_pt = {f["properties"]["station_id"]: proj(shape(f["geometry"])) for f in stations}; names = {f["properties"]["station_id"]: f["properties"]["name"] for f in stations}
ids = sorted(st_pt)
window = proj(Polygon([(x, y) for x, y in [(src_manifest["study_bbox_wgs84"][0], src_manifest["study_bbox_wgs84"][1]), (src_manifest["study_bbox_wgs84"][2], src_manifest["study_bbox_wgs84"][1]),
                                            (src_manifest["study_bbox_wgs84"][2], src_manifest["study_bbox_wgs84"][3]), (src_manifest["study_bbox_wgs84"][0], src_manifest["study_bbox_wgs84"][3])]]))

# ---------------- POI records with category rules ----------------
pois, excluded = [], []
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def add(category, layer, f, name, subtype=None, attrs=None):
    g = shape(f["geometry"]); gp = proj(g)
    if not gp.is_valid: gp = polygonal(make_valid(gp))
    pid = f"{layer}:{f.get('id') if f.get('id') is not None else f['properties'].get('OBJECTID', f['properties'].get('FID'))}"
    rec = {"poi_id": pid, "category": category, "subtype": subtype or layer, "source_layer": layer, "name": name, "geometry_type": gp.geom_type,
           "lon": r6(g.centroid.x), "lat": r6(g.centroid.y), "attributes": attrs or {}, "_geom": gp}
    if gp.geom_type in ("Polygon", "MultiPolygon"): rec["area_acres"] = round(gp.area / ACRE_M2, 3); rec["geometry_wgs84"] = mapping(g)   # outline kept for the walk model + map
    pois.append(rec); return rec


for f in features("school_public"):
    p = f["properties"]; enroll = p.get("ENROLLMNT"); grades = (p.get("GRADES") or "").strip()
    # Public-school rule = ENROLLMNT > 0 in the county file. The file lists School Board offices, a garage, a telecom complex, an adult/technical
    # college and program sites with ENROLLMNT 0 (GRADES is '0' for most of them, 'K-12' for a distance-learning program), so "grades set" is not
    # a usable criterion. Virtual schools WITH enrollment stay in, because the source does not flag them — stated as a source limitation.
    if (enroll or 0) > 0: add("school", "school_public", f, p.get("NAME"), "public", {"grades": grades, "enrollment": enroll})
    else: excluded.append({"layer": "school_public", "name": p.get("NAME"), "reason": f"ENROLLMNT is {enroll!r} in the county file (GRADES {grades!r}): administrative, adult/technical or program site, not a school with enrolled students"})
for f in features("school_charter"): add("school", "school_charter", f, f["properties"].get("NAME"), "charter", {"grades": f["properties"].get("GRADES")})
for f in features("school_private"): add("school", "school_private", f, f["properties"].get("NAME"), "private", {"grade_level": f["properties"].get("GRDLEVEL")})
city_parks = [add("park", "park_city", f, f["properties"].get("PARKNAME"), "city", {"management_agency": f["properties"].get("Mgmt_Agcy"), "park_id": f["properties"].get("ParkID")}) for f in features("park_city")]
for f in features("park_county"):
    g = proj(shape(f["geometry"])); dup = next((c for c in city_parks if c["_geom"].intersection(g).area > 0.5 * g.area), None)
    if dup: excluded.append({"layer": "park_county", "name": f["properties"].get("NAME"), "reason": f"duplicates city park polygon '{dup['name']}' (overlap > 50 %)"})
    else: add("park", "park_county", f, f["properties"].get("NAME"), "county", {"class": f["properties"].get("CLASS"), "type": f["properties"].get("TYPE")})
clinic_layers = ["clinic_fqhc", "clinic_free_standing", "clinic_jhs_primary_care", "clinic_mental_health", "clinic_school_based"]
seen = []
for layer in clinic_layers:
    for f in features(layer):
        p = f["properties"]; name = (p.get("PROVIDER") or "").strip(); g = proj(shape(f["geometry"]))
        dup = next((s for s in seen if s["_geom"].distance(g) < DUP_DISTANCE_M and (norm(s["name"])[:12] == norm(name)[:12] or "jefferson reaves" in norm(name) and "jefferson reaves" in norm(s["name"]))), None)
        if dup: excluded.append({"layer": layer, "name": name, "reason": f"duplicate of '{dup['name']}' ({dup['source_layer']}) within {DUP_DISTANCE_M:.0f} m"}); continue
        seen.append(add("clinic", layer, f, name, layer.replace("clinic_", ""), {"address": p.get("ADDRESS")}))
for f in features("grocery_snap_all_types"):
    p = f["properties"]
    if p.get("Store_Type") in GROCERY_TYPES: add("grocery", "grocery_snap_all_types", f, p.get("Store_Name"), p.get("Store_Type"), {"store_type": p.get("Store_Type"), "record_id": p.get("Record_ID")})
    else: excluded.append({"layer": "grocery_snap_all_types", "name": p.get("Store_Name"), "reason": f"SNAP store type '{p.get('Store_Type')}' is not in the grocery definition"})
osm = load(raw_files[("osm_grocery_crosscheck", "response")])
osm_names = sorted({(e.get("tags", {}).get("name") or "(unnamed)") for e in osm.get("elements", [])})
for rec in pois:
    if not rec["_geom"].intersects(window): excluded.append({"layer": rec["source_layer"], "name": rec["name"], "reason": "outside the study window"})
pois = [r for r in pois if r["_geom"].intersects(window)]
by_cat = {c: [r for r in pois if r["category"] == c] for c in CATEGORIES}

# ---------------- counts per station/band, nearest per station/category ----------------
def inside(rec, geom):
    return geom.contains(rec["_geom"]) if rec["geometry_type"] == "Point" else geom.intersection(rec["_geom"]).area > 0


profiles, evidence = [], []
for pid in ids:
    bands_out = []
    for i, k in enumerate(BAND_KEYS + ["cum"]):
        geom = targets[(pid, k)]; counts, members = {}, {}
        for c in CATEGORIES:
            hits = [r for r in by_cat[c] if inside(r, geom)]
            counts[c] = {"count": len(hits), "value_status": ("value" if hits else "not_found_in_source_within_window"), "unit": "facilities", "provenance_class": "observed", "data_nature": "administrative_record"}
            members[c] = [r["poi_id"] for r in hits]
            for r in hits:
                evidence.append({"evidence_id": f"{pid}|{k}|{r['poi_id']}", "station_id": pid, "band_id": k, "poi_id": r["poi_id"], "category": c, "name": r["name"],
                                 "relation": ("inside_band" if r["geometry_type"] == "Point" else "polygon_intersects_band"),
                                 "distance_from_reference_point_ft": round(st_pt[pid].distance(r["_geom"]) / FOOT_M, 1), "source_layer": r["source_layer"]})
        bands_out.append({"band_id": k, "band": (["0-1/8 mi", "1/8-1/4 mi", "1/4-1/2 mi"][i] if k != "cum" else "0-1/2 mi cumulative"),
                          "outer_ft": RADII_FT[i] if k != "cum" else RADII_FT[2], "counts": counts, "poi_ids": members})
    nearest = {}
    for c in CATEGORIES:
        best = min(by_cat[c], key=lambda r: st_pt[pid].distance(r["_geom"]), default=None)
        if best is None: nearest[c] = {"value_status": "not_found_in_source_within_window", "absence_status": "not_found_in_source_within_window", "distance_ft": None}
        else:
            d = st_pt[pid].distance(best["_geom"])
            nearest[c] = {"poi_id": best["poi_id"], "name": best["name"], "distance_ft": round(d / FOOT_M, 1), "distance_m": r2(d), "display_mi": round(d / FOOT_M / 5280.0, 3),
                          "value_status": "value", "distance_type": "straight_line", "within_half_mile": d <= RADII_FT[2] * FOOT_M,
                          "note": ("inside the park polygon" if d == 0 else "straight line from the reference point; not a walking distance")}
    profiles.append({"station_id": pid, "name": names[pid], **SEMANTICS, "bands": bands_out[:3], "cumulative_0_to_half_mile": bands_out[3], "nearest_by_category": nearest})
net = targets[("net", "net")]
network = {"unique_facilities_in_network_half_mile_union": {c: len([r for r in by_cat[c] if inside(r, net)]) for c in CATEGORIES},
           "facilities_in_window": {c: len(by_cat[c]) for c in CATEGORIES},
           "grocery_crosscheck_osm": {"elements": len(osm.get("elements", [])), "names": osm_names, "osm_data_timestamp": osm.get("osm3s", {}).get("timestamp_osm_base"),
                                      "note": "OpenStreetMap supermarkets/grocery in the window (Overpass mirror, data lags); not merged, a plausibility check for the SNAP-based list"},
           "note": "per-station counts are non-exclusive across stations; the network count is a set of unique facilities inside the union"}

# ---------------- validation ----------------
def band_sum_ok(p, c):
    b = [x["counts"][c]["count"] for x in p["bands"]]; cum = p["cumulative_0_to_half_mile"]["counts"][c]["count"]
    return (cum == sum(b)) if c != "park" else (max(b) <= cum <= sum(b))
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "facilities_in_window": network["facilities_in_window"], "excluded_records": len(excluded),
       "point_categories_cum_equals_band_sum": all(band_sum_ok(p, c) for p in profiles for c in CATEGORIES if c != "park"),
       "park_cum_between_max_band_and_sum": all(band_sum_ok(p, "park") for p in profiles),
       "nearest_consistent_with_counts": all((p["nearest_by_category"][c]["distance_ft"] is not None and p["nearest_by_category"][c]["distance_ft"] <= RADII_FT[2] + 1e-6)
                                             == (p["cumulative_0_to_half_mile"]["counts"][c]["count"] > 0) for p in profiles for c in CATEGORIES if p["nearest_by_category"][c]["distance_ft"] is not None or p["cumulative_0_to_half_mile"]["counts"][c]["count"] == 0),
       "all_geometries_valid": all(r["_geom"].is_valid and not r["_geom"].is_empty for r in pois),
       "every_station_present": len(profiles) == 21, "evidence_rows": len(evidence),
       "scope_statement": "PASS means the source features were categorised by the recorded rules and counted consistently. Counts are facilities listed by the sources; "
                          "absence means not found in these sources inside the window, not confirmed absence; distances are straight lines, not walking distances."}
ok = val["point_categories_cum_equals_band_sum"] and val["park_cum_between_max_band_and_sum"] and val["nearest_consistent_with_counts"] and val["all_geometries_valid"] and val["every_station_present"]
if os.environ.get("POI_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

config = {"categories": CATEGORIES, "rules": {"school": "county public schools with ENROLLMNT > 0 (School Board offices, garage, telecom complex, adult/technical college and zero-enrollment program sites excluded; virtual schools with enrollment stay because the source does not flag them) + charter + private",
                                                "park": "City of Miami Park_Boundary_Base_Layer polygons + county park boundaries not overlapping a city polygon by more than 50 %",
                                                "clinic": "county health-facility layers (FQHC, free-standing, JHS primary care, mental health, school-based); duplicates within 50 m with matching names dropped",
                                                "grocery": f"USDA SNAP retailers with Store_Type in {sorted(GROCERY_TYPES)}; OSM cross-check only"},
          "distance": {"type": "straight_line", "origin": "GTFS reference point", "unit_display": "ft / mi", "search_extent": "study window"},
          "bands": {"radii_ft": RADII_FT, "source": "demography package analysis_targets_26917.json"}, "duplicate_distance_m": DUP_DISTANCE_M}
config_sha = sha_obj(config)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "demography_package": dem_ptr["package_id"]}
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_poi_profile.json", {"schema_version": "miami-station-poi-profile/1.0", **common, **SEMANTICS, "config": config, "transform": transform_record, "environment": environment,
     "network": network, "stations": profiles})
dump(STAGING / "poi_features.json", {"schema_version": "miami-poi-features/1.0", **common, **SEMANTICS, "sources": {s["layer_id"]: {k: v for k, v in s.items() if k in ("category", "publisher", "terms", "service_url", "osm_data_timestamp")} for s in src_manifest["sources"]},
     "features": [{k: v for k, v in r.items() if k != "_geom"} for r in pois], "excluded_records": excluded})
dump(STAGING / "poi_evidence.json", {"schema_version": "miami-poi-evidence/1.0", **common, "rows": evidence, "note": "one row per (station, band, facility); cite evidence_id"})
dump(STAGING / "poi_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-poi-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": [package_entry("demography")],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment, "transform": transform_record,
            "method_summary": "county/city/USDA facility layers categorised by recorded rules, counted per station band (points inside, park polygons intersecting) and "
                              "nearest by straight line inside the study window; OSM as a grocery cross-check",
            "contract": "V2_站点输入包字段契约.md §5; rules doc 规则 6",
            "publish_policy": "content-addressed immutable package dir poi/pkg-<id>; readers resolve poi_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} facilities={network['facilities_in_window']} "
      f"excluded={len(excluded)} evidence_rows={len(evidence)} network_unique={network['unique_facilities_in_network_half_mile_union']}")
