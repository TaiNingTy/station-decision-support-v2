"""Build a versioned station crosswalk from reviewed source evidence, without AI or product changes.

Stage contract (station_master, upstream): publishes ONLY its own immutable outputs + build_manifest.json.
It does not write gis_data_readiness.json and does not compute downstream status — that derived view has a single
writer, scripts/miami_readiness.py, which is invoked at the end of this stage (R1/R2 after the 2026-09-14 recheck).
"""
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw/miami/2026-09-14"
OUT = ROOT / "data/miami/2026-09-14"
REGISTRY = ROOT / "config/miami_station_registry_v1.json"
ARCHIVE = ROOT / "raw/miami/2026-09-11/google_transit.zip"
STOPS = ROOT / "data/miami/2026-09-11/metromover_stop_records.geojson"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    registry = read(REGISTRY)
    raw_stops = read(STOPS)["features"]
    stops = {f["properties"]["stop_id"]: f for f in raw_stops}
    inv = read(STOPS.parent / "inventory.json")
    require(sha(ARCHIVE) == inv["archive_sha256"], "GTFS archive differs from inventory")
    require(len(stops) == len(raw_stops), "Duplicate stop IDs in input")
    assigned = [sid for s in registry["stations"] for sid in s["gtfs_stop_ids"]]
    require(len(assigned) == len(set(assigned)), "A stop is assigned to multiple entities")
    require(set(assigned) == set(stops), "Registry and feed differ; review new or missing records")
    require(len(registry["stations"]) == 21, "Registry differs from reviewed 21-station baseline")
    require(len({s["station_id"] for s in registry["stations"]}) == 21, "Duplicate entity IDs")
    require(len({tuple(f["geometry"]["coordinates"]) for f in raw_stops}) == 21,
            "Snapshot no longer contains exactly 21 distinct coordinate pairs; review required")

    features, crosswalk = [], []
    entity_for = {}
    for s in registry["stations"]:
        coords = {tuple(stops[sid]["geometry"]["coordinates"]) for sid in s["gtfs_stop_ids"]}
        require(len(coords) == 1, "Conflicting coordinates within " + s["station_id"])
        for sid in s["gtfs_stop_ids"]:
            f = stops[sid]
            entity_for[sid] = s["station_id"]
            anomaly = sid in s.get("anomalous_stop_ids", [])
            crosswalk.append({
                "gtfs_stop_id": sid, "gtfs_stop_name": f["properties"]["stop_name"],
                "physical_station_id": s["station_id"], "station_name": s["name"],
                "mapping_status": "SUPPORTED_WITH_SOURCE_NAME_ANOMALY" if anomaly else "SUPPORTED_BY_MAP_AND_FEED",
                "evidence": ["official_map_station", "same_exact_feed_coordinates", "ordered_service_patterns"],
                "source_name_anomaly": anomaly, "agency_mapping_confirmation": False,
                "note": s.get("name_note"), "registry_version": registry["schema_version"],
            })
        properties = {
            **s, "entity_id_namespace": "project_owned_not_agency_id",
            "geometry_role": "gtfs_station_reference_point_not_entrance_or_platform_centroid",
            "geometry_source": "GTFS snapshot 2026-09-11",
            "classification": {"existing_asset": "metromover_station", "study_role": "candidate_conversion_site",
                               "demand_origin_or_destination": "TO_BE_EVALUATED", "automatic_demand_exclusion": False},
            "mapping_status": "SUPPORTED_WITH_SOURCE_NAME_ANOMALY" if s.get("anomalous_stop_ids") else "SUPPORTED_BY_MAP_AND_FEED",
            "agency_mapping_confirmation": False, "source_evidence": ["official_metromover_map.pdf", "GTFS 2026-09-11"],
            "design_inputs": {
                "boarding_demand_pax_per_hour": None, "alighting_demand_pax_per_hour": None,
                "platform_footprint_m2": None, "platform_usable_length_m": None,
                "platform_usable_width_m": None, "guideway_structural_reuse_status": "NOT_ASSESSED",
                "accessible_entrances": None, "pedestrian_network_catchment": None,
                "construction_feasibility_status": "NEEDS_REVIEW",
            },
            "configuration": {"boarding_berths": None, "staging_bays": None,
                              "platform_length_m": None, "platform_width_m": None, "layout_type": None,
                              "status": "NOT_CALCULATED"},
            "ai_analysis_status": "NOT_RUN", "internal_length_unit": "m", "display_length_unit": "ft",
        }
        features.append({"type": "Feature", "id": s["station_id"],
                         "geometry": {"type": "Point", "coordinates": list(next(iter(coords)))}, "properties": properties})

    # Keep schedule patterns separate from physical guideway geometry and observed demand.
    with zipfile.ZipFile(ARCHIVE) as z:
        def rows(name):
            return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))
        routes = {r["route_id"] for r in rows("routes.txt") if "METROMOVER" in r["route_long_name"]}
        trips = {r["trip_id"]: r for r in rows("trips.txt") if r["route_id"] in routes}
        seq = defaultdict(list)
        for r in rows("stop_times.txt"):
            if r["trip_id"] in trips:
                seq[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"]))
        patterns = Counter((trips[t]["route_id"], trips[t]["shape_id"], tuple(sid for _, sid in sorted(v))) for t, v in seq.items())
    pattern_records = [{"route_id": route, "shape_id": shape, "gtfs_stop_sequence": list(ids),
                        "station_sequence": [entity_for[sid] for sid in ids],
                        "trip_records_all_calendar_patterns": count,
                        "interpretation": "scheduled_sequence_not_demand_or_surveyed_guideway"}
                       for (route, shape, ids), count in sorted(patterns.items())]
    anomaly_patterns = [p for p in pattern_records if "832" in p["gtfs_stop_sequence"]]
    require(len(anomaly_patterns) == 1 and anomaly_patterns[0]["gtfs_stop_sequence"] == ["832", "833", "834", "813"],
            "The reviewed evidence for stop 832 changed; mapping must be re-reviewed")
    station_names = {s["station_id"]: s["name"] for s in registry["stations"]}
    for p in pattern_records:
        p["station_name_sequence"] = [station_names[sid] for sid in p["station_sequence"]]

    zoning = read(RAW / "zoning_study_window.geojson")
    esri = read(RAW / "zoning_study_window.esri.json")
    ids = read(RAW / "zoning_query_ids.json")["objectIds"]
    require(zoning.get("type") == "FeatureCollection", "Source is not GeoJSON")
    require(not esri.get("exceededTransferLimit", False), "Zoning query was truncated")
    geo_ids = [f["properties"]["FID"] for f in zoning["features"]]
    esri_ids = [f["attributes"]["FID"] for f in esri["features"]]
    require(len(geo_ids) == len(set(geo_ids)) and set(geo_ids) == set(ids) == set(esri_ids),
            "Zoning IDs differ across independent ID, Esri JSON and GeoJSON requests")
    require(all(f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in zoning["features"]), "Unexpected geometry")
    require(all(f["properties"] == esri["features"][i]["attributes"] for i, f in enumerate(zoning["features"])),
            "Esri and GeoJSON attributes differ")

    OUT.mkdir(parents=True, exist_ok=True)
    write("station_master.geojson", {"type": "FeatureCollection", "schema_version": "miami-station-master/1.0", "features": features})
    write("stop_to_station_crosswalk.json", {"input_gtfs_sha256": sha(ARCHIVE), "registry_sha256": sha(REGISTRY), "records": crosswalk})
    write("service_patterns.json", {"records": pattern_records})
    bbox = read(RAW / "source_manifest.json")["study_bbox_wgs84"]
    west, south, east, north = bbox
    write("study_window.geojson", {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {
        "role": "data_extraction_window", "definition": "Analyst-selected rectangle surrounding the station reference points",
        "is_walk_catchment": False, "is_approved_project_boundary": False, "crs": "EPSG:4326"},
        "geometry": {"type": "Polygon", "coordinates": [[[west,south],[east,south],[east,north],[west,north],[west,south]]]}}]})
    # R1/R2: this stage neither computes downstream status nor writes gis_data_readiness.json. It publishes an
    # immutable GIS inventory; scripts/miami_readiness.py (single writer) derives readiness + freshness from manifests.
    gis_inventory = {
        "schema_version": "miami-gis-inventory/1.1", "snapshot_date": "2026-09-14",
        "role": "immutable output of the station_master stage; the current downstream status lives in gis_data_readiness.json (derived)",
        "zoning": {"feature_count": len(geo_ids), "full_query_result_verified": True,
                   "raw_geojson": "../../../raw/miami/2026-09-14/zoning_study_window.geojson",
                   "extraction": "Full zone polygons intersecting study rectangle; not clipped to rectangle or catchments",
                   "crs": "EPSG:4326", "source_crs": "EPSG:3857",
                   "source_publisher": "CityMiamiFL", "license": "CC-BY-4.0",
                   "original_zoning_codes": dict(sorted(Counter(f["properties"]["M21_ZONE"] for f in zoning["features"]).items())),
                   "original_transect_descriptions": dict(sorted(Counter(f["properties"]["Transect_D"] for f in zoning["features"]).items())),
                   "use_code_crosswalk_status": "NOT_REVIEWED",
                   "area_policy": "Preserve source area fields; do not equate them with buildable area or compute areas from WGS84 degrees",
                   "automatic_industrial_exclusion": False},
        "demography": {"status": "NOT_DOWNLOADED", "preferred_source_family": "US Census ACS 5-year estimates with geography and margins of error", "values": None},
        "jobs_and_commute": {"status": "NOT_DOWNLOADED", "preferred_source_family": "Census LEHD LODES and ACS with compatible geography, years and denominators", "values": None},
        "pois": {"status": "NOT_DOWNLOADED", "required_analysis_categories": ["school", "clinic", "grocery", "park"], "is_mandatory_local_standard": False},
        "walk_network": {"status": "NOT_DOWNLOADED", "target_time_minutes": 15, "distance_proxy_m": 1200,
                         "note": "distance_proxy_m=1200 is an unexecuted walk-analysis concept (15-min target); it is NOT the imperial band parameter used by the spatial-join stage (660/1320/2640 ft)",
                         "proxy_is_validated_walk_catchment": False, "needs": ["entrances", "legal crossings", "barriers", "vertical access", "walk speed assumptions"]},
        "roads_and_guideways": {"status": "NOT_DOWNLOADED", "gtfs_shapes_replace_asset_survey": False,
                               "separate_fields_needed": ["road_function", "vertical_level", "mode", "truck_restriction", "observed_truck_use", "conversion_asset_role"]},
        "demand": {"observed_station_boardings_status": "NOT_DOWNLOADED", "observed_od_status": "NOT_DOWNLOADED",
                   "forecast_status": "NOT_RUN", "gtfs_counts_are_ridership": False},
        "served_hubs": {"status": "MAP_CONNECTION_CANDIDATES_ONLY", "connections": [
            {"station_id": s["station_id"], "modes": s["external_connections_on_map"], "walk_link_and_demand_verified": False}
            for s in registry["stations"] if s.get("external_connections_on_map")], "airport_is_inside_metromover_network": False},
        "engineering": {"platform_footprints": "NOT_ACQUIRED", "structural_reuse": "NOT_ASSESSED", "vehicle_parameters": "NOT_APPROVED"},
    }
    write("gis_inventory.json", gis_inventory)
    input_paths = [ARCHIVE, STOPS, STOPS.parent / "inventory.json", REGISTRY, RAW / "official_metromover_map.pdf",
                   RAW / "source_manifest.json", RAW / "zoning_study_window.geojson", RAW / "zoning_study_window.esri.json",
                   RAW / "zoning_query_ids.json", RAW / "zoning_item_metadata.json", Path(__file__).resolve()]   # resolved: ROOT is resolved, and a symlinked temp dir (/var -> /private/var) otherwise breaks relative_to
    validation = {"status": "PASS_WITH_DOCUMENTED_SOURCE_NAME_ANOMALY", "input_stop_records": len(stops),
                  "physical_station_entities": len(features), "mapped_stop_records": len(crosswalk),
                  "unmapped_stop_records": 0, "duplicate_assignments": 0, "source_name_anomaly_stop_ids": ["832"],
                  "service_patterns": len(pattern_records), "zoning_polygons": len(geo_ids),
                  "official_agency_confirmation": False, "engineering_validation": "NOT_PERFORMED", "ai_run": "NOT_PERFORMED"}
    write("validation.json", validation)
    # F3/R2: this stage lists ONLY its own immutable outputs (no directory glob, no shared mutable file).
    own_outputs = ["station_master.geojson", "stop_to_station_crosswalk.json", "service_patterns.json",
                   "study_window.geojson", "gis_inventory.json", "validation.json"]
    write("build_manifest.json", {"stage": "station_master", "schema_version": "miami-station-master-manifest/1.1",
        "built_on": "2026-09-14",
        "inputs": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in input_paths],
        "outputs": [{"file": f, "sha256": sha(OUT / f)} for f in own_outputs],
        "readiness_note": "gis_data_readiness.json is a DERIVED status view written only by scripts/miami_readiness.py; it is not an "
                          "output of this stage and is not hash-listed here. Downstream freshness is decided there from the inputs "
                          "the spatial-join stage actually consumed (station_master, study_window, raw zoning)."})
    print(json.dumps(validation, indent=2))
    # Single writer of readiness: derive the current status view from the stage manifests (marks the spatial join
    # STALE when any input it consumed changed, without touching that stage's package).
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from miami_readiness import aggregate
    aggregate()


if __name__ == "__main__":
    main()
