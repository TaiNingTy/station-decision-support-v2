#!/usr/bin/env python3
"""Miami · station input package — V2 step 4, stage `input_package`.

One package that the AI layer (batch reasoning) and the deterministic configuration rules both read. Per station it
assembles, without recomputing anything:
  * identity + geometry + classification placeholders from station_master.geojson
  * statutory zoning profile per band            (spatial_join package)
  * ACS demography profile per band              (demography package)
  * LODES jobs profile per band + OD link potential (jobs package)
  * Miami-specific inputs with acquisition status (contract §8) — none acquired yet, fields kept
  * role classification placeholder (analysis-layer output; NOT decided here)
Every numeric block keeps the producing layer's value envelope (value_status, provenance_class, data_nature, MOE fields)
and an `evidence_source` pointing at that layer's evidence file + id pattern, so a reader can click through.
The package pins the package id + manifest sha256 of every layer it consumed (contract §11); the manifest carries the
`config_inputs` summary that scripts/miami_readiness.py uses for the two configuration-readiness booleans (§10).
Facts only: no conclusions, no allocation, no ridership (rules doc 总原则).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

STAGE = "input_package"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
BAND_KEYS = ["b1", "b2", "b3"]
REQUIRED_LAYERS = ["spatial_join", "demography", "jobs"]
OPTIONAL_LAYERS = ["poi", "walk_model"]
DATA_NATURE = {"spatial_join": "administrative_record", "demography": "survey_estimate", "jobs": "administrative_modeled"}
CONFIG_INPUTS = {  # contract §8; acquisition_status is input-level, value_status is value-level
    "ridership_baseline": {"content": "Metromover boardings/alightings by station and hour", "expected_source": "Miami-Dade DTPW ridership reports", "acquisition_status": "not_acquired"},
    "service_baseline": {"content": "scheduled headways by period per station", "expected_source": "GTFS stop_times (raw/miami/2026-09-11/google_transit.zip)", "acquisition_status": "derivable_from_gtfs"},
    "hub_transfer_inflow": {"content": "transfer entrances and volumes from Metrorail, Brightline etc.", "expected_source": "agency data", "acquisition_status": "not_acquired",
                            "scope_decision": "kept as a field, NOT modeled in the Miami V2 case (Melbourne covers hub inflow); results cannot prove full-line replacement capacity under all existing demand"},
    "road_guideway_roles": {"content": "road function, vertical level, mode, truck restrictions per segment", "expected_source": "county GIS + survey", "acquisition_status": "not_acquired"},
    "platform_constructible_space": {"content": "platform footprint and constructible space per station", "expected_source": "survey / drawings", "acquisition_status": "not_acquired"},
    "vehicle_parameters": {"content": "vehicle capacity, dwell, berth geometry", "expected_source": "approved vehicle spec", "acquisition_status": "not_approved"},
}
AI_USAGE_RULES = {"site_facts": "cite evidence_id from the layer evidence files named in evidence_source; do not restate or invent sources",
                  "normative_judgements": "cite rule_id + knowledge-base document version (to be pinned in the rules/KB stage)",
                  "option_comparisons": "cite calculation result ids from the scenarios/rules stage",
                  "forbidden": ["treating density or accessibility as persons/hour", "using coverage shares as allocation weights", "averaging medians",
                                "reading LODES counts as trips or ridership", "inferring willingness to pay from income", "excluding zoning codes wholesale"]}
SEMANTICS = {"is_ridership": False, "is_allocation_weight": False, "contains_conclusions": False, "role_classification_decided": False,
             "units": {"length": "ft / mi (display), m (internal)", "area": "sq ft / acres / sq mi (display), m2 (internal)", "density": "persons per sq mi, jobs per acre, households per acre"}}

environment = lock_gate()
MODULES_FILE, OPS_FILE = ROOT / "config/station_platform_modules_v1.json", ROOT / "config/prt_operations_assumptions_v1.json"
MODULES = load(MODULES_FILE) if MODULES_FILE.exists() else None      # owner-provided platform module drawings (step 6)
OPS = load(OPS_FILE) if OPS_FILE.exists() else None                  # generic PRT operating assumptions (step 6)

# ---------------- consumed layers (verified) + pins ----------------
def layer(stage, manifest_name="manifest.json"):
    ptr_path = DATA / f"{stage}_current.json"
    if not ptr_path.exists(): return None
    ptr = load(ptr_path); d = DATA / ptr["package_dir"]; ok, m, problems = verify_package(d, manifest_name)
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    if not m.get("ready_for_downstream"): raise SystemExit(f"HALT: {stage} package is not ready_for_downstream")
    return {"stage": stage, "dir": d, "manifest": m, "pointer": ptr, "pin": {"stage": stage, "package_id": ptr["package_id"], "package_dir": ptr["package_dir"], "manifest_sha256": ptr["manifest_sha256"]}}


L = {"spatial_join": layer("spatial_join", "spatial_join_manifest.json"), "demography": layer("demography"), "jobs": layer("jobs")}
for s in REQUIRED_LAYERS:
    if L[s] is None: raise SystemExit(f"HALT: required layer {s} has no published package")
optional = {s: layer(s) for s in OPTIONAL_LAYERS}
L.update({s: v for s, v in optional.items() if v})   # so evidence_source() can point at optional layers too
sb = layer("service_baseline")   # config input derived from GTFS (step 5a); absent -> derivable_from_gtfs / missing
sb_by = {s["station_id"]: s for s in load(sb["dir"] / "station_service_baseline.json")["stations"]} if sb else {}
poi_doc = load(optional["poi"]["dir"] / "station_poi_profile.json") if optional["poi"] else None   # step 7b optional layer
poi_by = {s["station_id"]: s for s in poi_doc["stations"]} if poi_doc else {}
walk_doc = (load(optional["walk_model"]["dir"] / "station_walk_profile.json")   # step 7c optional layer (paused); a real package always carries the profile,
            if optional["walk_model"] and (optional["walk_model"]["dir"] / "station_walk_profile.json").exists() else None)   # a regression fixture only pins the layer
walk_by = {s["station_id"]: s for s in walk_doc["stations"]} if walk_doc else {}
WALK_KEEP = ("catchment_type", "is_validated_walk_catchment", "provenance_class", "data_nature", "distance_type", "distance_origin", "validation_checklist", "attribution",
             "walk_speed_mph", "snap", "isochrones", "equal_distance_comparison", "nearest_by_category_network")


def walk_block(pid):
    s = walk_by[pid]
    return {**{k: s[k] for k in WALK_KEEP}, "assumption_ids": walk_doc["config"]["assumption_parameter_ids"] if "assumption_parameter_ids" in walk_doc["config"] else sorted(walk_doc["config"]["assumptions"]),
            "assumptions_recorded_in": "walk_model package station_walk_profile.json -> config.assumptions", "isochrone_geometry_file": "walk_isochrones.geojson",
            "semantics": "model estimate on OpenStreetMap at an assumed speed with no delays; Euclidean bands above stay the analysis unit, this layer sits beside them and never replaces them",
            "evidence_source": evidence_source("walk_model", "walk_model_evidence.json", f"{pid}|iso<minutes>|BG<block_group> or {pid}|iso<minutes>|BLK<block>")}
rr = layer("ridership_reference")   # observed DTPW boardings by station (step 7a); reference only, never calibration
rr_doc = load(rr["dir"] / "station_ridership_reference.json") if rr else None
rr_by = {s["station_id"]: s for s in rr_doc["stations"]} if rr_doc else {}
sm_path = DATA / "station_master.geojson"
stations = load(sm_path)["features"]
if len(stations) != 21: raise SystemExit(f"HALT: expected 21 stations, got {len(stations)}")
sj = load(L["spatial_join"]["dir"] / "station_zoning_profile.json"); pm = load(L["spatial_join"]["dir"] / "station_point_zoning_match.json")
dem = load(L["demography"]["dir"] / "station_demography_profile.json")
jobs = load(L["jobs"]["dir"] / "station_jobs_profile.json"); od = load(L["jobs"]["dir"] / "od_summary.json")
sj_by = {s["station_id"]: s for s in sj["stations"]}; pm_by = {s["station_id"]: s for s in pm["stations"]}
dem_by = {s["station_id"]: s for s in dem["stations"]}; jobs_by = {s["station_id"]: s for s in jobs["stations"]}
ids = sorted(f["properties"]["station_id"] for f in stations)
if not (set(ids) == set(sj_by) == set(dem_by) == set(jobs_by)): raise SystemExit("HALT: station id sets differ across layers")
consumed_inputs = [consumed_entry("station_master", sm_path)] + ([consumed_entry("platform_modules", MODULES_FILE)] if MODULES else []) + ([consumed_entry("operations_assumptions", OPS_FILE)] if OPS else [])
consumed_packages = [L[s]["pin"] for s in REQUIRED_LAYERS] + ([sb["pin"]] if sb else []) + ([rr["pin"]] if rr else []) + [v["pin"] for v in optional.values() if v]
BAND_IDENTITY = ("band_id", "band", "inner_ft", "outer_ft", "ring_area_m2")


def strip(d, drop):
    return {k: v for k, v in d.items() if k not in drop}


def evidence_source(stage, file, pattern):
    return {"package": L[stage]["pin"]["package_dir"], "file": file, "evidence_id_pattern": pattern}


def zoning_block(pid, band):
    src = sj_by[pid]["bands"][BAND_KEYS.index(band)] if band != "cum" else sj_by[pid]["cumulative_0_to_half_mile"]
    return {"provenance_class": "observed", "data_nature": DATA_NATURE["spatial_join"], "source": "City of Miami M21 zoning (CC-BY-4.0) joined in EPSG:26917",
            "semantics": "statutory zoning = permitted/constrained use; NOT observed land use, population, jobs or demand; no use mapping; no exclusion; coverage shares are NOT allocation weights",
            **strip(src, BAND_IDENTITY), "evidence_source": evidence_source("spatial_join", "station_zoning_evidence.json", f"{pid}|{band}|FID<fid>")}


def demography_block(pid, band):
    src = dem_by[pid]["bands"][BAND_KEYS.index(band)] if band != "cum" else dem_by[pid]["cumulative_0_to_half_mile"]
    return {**strip(src, BAND_IDENTITY), "evidence_source": evidence_source("demography", "demography_evidence.json", f"{pid}|{band}|BG<geoid> and {pid}|{band}|TR<tract>"),
            "unit_values_file": "block_group_values.json"}


def jobs_block(pid, band):
    src = jobs_by[pid]["bands"][BAND_KEYS.index(band)] if band != "cum" else jobs_by[pid]["cumulative_0_to_half_mile"]
    return {**strip(src, BAND_IDENTITY), "evidence_source": evidence_source("jobs", "jobs_evidence.json", f"{pid}|{band}|BLK<geoid20>"), "unit_values_file": "block_values.json"}


def poi_block(pid, band):
    if not poi_doc or pid not in poi_by: return None
    s = poi_by[pid]; src = s["cumulative_0_to_half_mile"] if band == "cum" else s["bands"][BAND_KEYS.index(band)]
    return {"counts": src["counts"], "poi_ids": src["poi_ids"], "provenance_class": "observed", "data_nature": "administrative_record",
            "semantics": "facilities listed by the sources inside the band (points inside, park polygons intersecting); not a service-level score; absence = not found in these sources",
            "evidence_source": evidence_source("poi", "poi_evidence.json", f"{pid}|{band}|<poi_id>"), "features_file": "poi_features.json"}


def config_input_fields(pid):
    fields = {k: {**v, "value": None, "value_status": "missing", "missing_reason": v["acquisition_status"] if v["acquisition_status"] != "derivable_from_gtfs" else "not_derived_yet",
                  "provenance_class": None, "data_nature": None} for k, v in CONFIG_INPUTS.items()}
    if sb and pid in sb_by:
        s = sb_by[pid]
        fields["service_baseline"] = {**CONFIG_INPUTS["service_baseline"], "acquisition_status": "derived", "value_status": "value", "missing_reason": None,
                                      "provenance_class": "derived", "data_nature": "administrative_record", "source_package": sb["pin"],
                                      "value": {"day_type": s["day_type"], "scheduled_departures_weekday_total": s["scheduled_departures_weekday_total"],
                                                "first_departure": s["first_departure"], "last_departure": s["last_departure"],
                                                "periods": {name: {"departures_per_hour": p["departures_per_hour"], "implied_headway_min_all_routes": p["implied_headway_min_all_routes"],
                                                                   "by_route": {r: x["implied_headway_min"] for r, x in p["by_route"].items()}} for name, p in s["periods"].items()}},
                                      "evidence_source": {"package": sb["pin"]["package_dir"], "file": "station_service_baseline.json", "evidence_id_pattern": f"station_id={pid}"},
                                      "note": "scheduled, not operated; not capacity; not ridership"}
    if rr and pid in rr_by:
        s = rr_by[pid]
        fields["ridership_baseline"] = {**CONFIG_INPUTS["ridership_baseline"], "acquisition_status": "acquired", "value_status": "value", "missing_reason": None,
                                        "provenance_class": "observed", "data_nature": "measured", "source_package": rr["pin"],
                                        "value": {"avg_weekday_boardings_10_month_mean": s["avg_weekday_boardings_10_month_mean"], "avg_weekday_boardings_min_max": s["avg_weekday_boardings_min_max"],
                                                  "avg_weekday_boardings_latest_month": s["avg_weekday_boardings_latest"]["month"], "avg_weekday_boardings_latest": s["avg_weekday_boardings_latest"]["value"],
                                                  "share_of_system_avg_weekday": s["share_of_system_avg_weekday_10_month_mean"],
                                                  "system_avg_weekday_boardings_10_month_mean": rr_doc["system"]["avg_weekday_boardings_10_month_mean"], "window": rr_doc["system"]["window"],
                                                  "report_station_name": s["report_station_name"], "mapping_basis": s["mapping_basis"], "mapping_confirmed_by_owner": s["mapping_confirmed_by_owner"]},
                                        "evidence_source": {"package": rr["pin"]["package_dir"], "file": "station_ridership_reference.json", "evidence_id_pattern": f"station_id={pid}; monthly_series[<YYYY-MM>]"},
                                        "note": "published boardings of the CURRENT Metromover per average weekday (DTPW); not trips, not OD, not alightings, not peak hour; "
                                                "an observed reference for scale and station-share shape, never a calibration target for the scenarios"}
    if MODULES and OPS:
        A = OPS["assumptions"]
        fields["platform_module_specification"] = {"content": "station platform modules as drawn: layout, berths, footprint", "acquisition_status": "acquired", "value_status": "value",
                                                   "missing_reason": None, "provenance_class": "observed", "data_nature": "design_specification",
                                                   "source": MODULES["provided_by"], "source_file": "config/station_platform_modules_v1.json",
                                                   "value": {"modules": [{k: m.get(k) for k in ("module_id", "layout", "berths", "width_ft_in", "length_ft_in", "width_ft", "length_ft", "area_ft2_as_drawn",
                                                                                                "width_m_derived", "length_m_derived", "area_m2_derived_from_ft2", "metric_drawing_as_provided")} for m in MODULES["modules"]],
                                                             "canonical_units": MODULES["canonical_units"], "vehicle_fit_statement": MODULES["vehicle_fit_statement"],
                                                             "not_specified_in_drawings": MODULES["not_specified_in_drawings"]}}
        fields["platform_constructible_space"] = {**CONFIG_INPUTS["platform_constructible_space"], "acquisition_status": "assumed", "value_status": "value", "missing_reason": None,
                                                  "provenance_class": "assumption", "data_nature": "assumption",
                                                  "value": {"assumption_id": "C06_site_footprint_available", "statement": A["C06_site_footprint_available"]["statement"]},
                                                  "note": "per-station constructible space has NOT been acquired; the module footprint is assumed available so the configuration chain can run"}
        fields["vehicle_parameters"] = {**CONFIG_INPUTS["vehicle_parameters"], "acquisition_status": "assumed", "value_status": "value", "missing_reason": None,
                                        "provenance_class": "assumption", "data_nature": "assumption",
                                        "value": {"vehicle_fits_berth": True, "vehicle_fit_source": "owner statement 2026-09-17 (observed)", "vehicle_capacity_pax_max": MODULES["vehicle_capacity_pax_max"],
                                                  "operations": {k: {"value": v["value"], "unit": v.get("unit")} for k, v in A.items() if k[:3] in ("C01", "C02", "C03", "C04", "C05", "C07")}},
                                        "note": "geometry fit is an owner statement; operating values are generic PRT assumptions, replaceable by specified values"}
    return fields


station_pkgs = []
consistency = {"max_ring_area_dev_m2": 0.0, "max_land_area_dev_m2": 0.0}
for f in sorted(stations, key=lambda x: x["properties"]["station_id"]):
    p = f["properties"]; pid = p["station_id"]
    bands = []
    for i, k in enumerate(BAND_KEYS):
        zb, db, jb = sj_by[pid]["bands"][i], dem_by[pid]["bands"][i], jobs_by[pid]["bands"][i]
        consistency["max_ring_area_dev_m2"] = max(consistency["max_ring_area_dev_m2"], abs(zb["ring_area_m2"] - db["ring_area_m2"]), abs(zb["ring_area_m2"] - jb["ring_area_m2"]))
        consistency["max_land_area_dev_m2"] = max(consistency["max_land_area_dev_m2"], abs(db["land_area_m2"] - jb["land_area_m2"]))
        bands.append({"band_id": k, "band": db["band"], "inner_ft": db["inner_ft"], "outer_ft": db["outer_ft"], "ring_area_m2": db["ring_area_m2"],
                      "land_area_m2": db["land_area_m2"], "display": {"ring_area": zb["display"]["ring_area"], "land_area": db["display"]["land_area"]},
                      "catchment_type": "euclidean_distance_band_from_gtfs_reference_point", "is_validated_walk_catchment": False,
                      "zoning": zoning_block(pid, k), "demography": demography_block(pid, k), "jobs": jobs_block(pid, k),
                      **({"poi": poi_block(pid, k)} if poi_doc else {})})
    cz, cd, cj = sj_by[pid]["cumulative_0_to_half_mile"], dem_by[pid]["cumulative_0_to_half_mile"], jobs_by[pid]["cumulative_0_to_half_mile"]
    consistency["max_ring_area_dev_m2"] = max(consistency["max_ring_area_dev_m2"], abs(cz["ring_area_m2"] - cd["ring_area_m2"]), abs(cz["ring_area_m2"] - cj["ring_area_m2"]))
    consistency["max_land_area_dev_m2"] = max(consistency["max_land_area_dev_m2"], abs(cd["land_area_m2"] - cj["land_area_m2"]))
    station_pkgs.append({
        "station_id": pid, "name": p["name"], "gtfs_stop_ids": p.get("gtfs_stop_ids"), "geometry_wgs84": f["geometry"],
        "geometry_role": p.get("geometry_role"), "geometry_source": p.get("geometry_source"), "mapping_status": p.get("mapping_status"),
        "agency_mapping_confirmation": p.get("agency_mapping_confirmation", False), "external_connections_on_map": p.get("external_connections_on_map", []),
        "existing_classification": p.get("classification"),
        "role_classification": {"status": "NOT_CLASSIFIED", "candidate_roles": ["origin", "destination", "facility_to_convert", "obstacle", "candidate_site"],
                                "note": "role-based classification is an analysis-layer output of the V2 pivot; the data layer records facts only"},
        "bands": bands,
        "cumulative_0_to_half_mile": {"band_id": "cum", "outer_ft": cd["outer_ft"], "ring_area_m2": cd["ring_area_m2"], "land_area_m2": cd["land_area_m2"],
                                      "display": {"ring_area": cz["display"]["ring_area"], "land_area": cd["display"]["land_area"]},
                                      "catchment_type": "euclidean_distance_band_from_gtfs_reference_point", "is_validated_walk_catchment": False,
                                      "zoning": zoning_block(pid, "cum"), "demography": demography_block(pid, "cum"), "jobs": jobs_block(pid, "cum"),
                                      **({"poi": poi_block(pid, "cum")} if poi_doc else {})},
        **({"poi_nearest_by_category": {**poi_by[pid]["nearest_by_category"], "distance_type": "straight_line", "origin": "GTFS reference point", "search_extent": "study window",
                                        "provenance_class": "observed", "data_nature": "administrative_record", "note": "straight-line distances, not walking distances; absence = not found in the sources inside the window"}}
           if poi_doc and pid in poi_by else {}),
        **({"walk_model": walk_block(pid)} if walk_doc and pid in walk_by else {}),
        "point_zoning_match": {**strip(pm_by[pid], ("station_id", "name")), "note": pm["note"], "provenance_class": "observed", "data_nature": DATA_NATURE["spatial_join"]},
        "od_link_potential": {**od["per_station_share_weighted_link_potential"][pid], "note": od["per_station_note"], "provenance_class": "derived",
                              "data_nature": DATA_NATURE["jobs"], "depends_on": ["jobs.od_links_subset", "jobs.candidate_stations"],
                              "excludes": ["hub_transfer_inflow", "Florida residents working out of state"], "is_trips": False},
        "design_inputs": {**p.get("design_inputs", {}), "acquisition_status": "not_acquired", "value_status": "missing"},
        "configuration": {**p.get("configuration", {}), "note": "configuration is an output of the rules stage; kept here as the NOT_CALCULATED placeholder"},
        "miami_specific_inputs": config_input_fields(pid),
        "optional_layers": {s: ({"status": "acquired", "package": optional[s]["pin"]} if optional[s] else {"status": "not_acquired", "acquisition_status": "not_acquired",
                                "note": "optional for AI interpretation; listed in readiness ai_missing_optional"}) for s in OPTIONAL_LAYERS},
        "ai_analysis_status": "NOT_RUN", "provenance_class_default": "observed", "assumption_ids": [],
    })

network = {"zoning": {"network_half_mile_union": sj["network"], "provenance_class": "observed", "data_nature": DATA_NATURE["spatial_join"]},
           "demography": {**dem["network"], "provenance_class": "observed", "data_nature": DATA_NATURE["demography"],
                          "evidence_source": evidence_source("demography", "demography_evidence.json", "net|net|BG<geoid>")},
           "jobs": {**jobs["network"], "provenance_class": "observed", "data_nature": DATA_NATURE["jobs"]},
           "od": {k: od[k] for k in ("candidate_blocks", "links_kept", "totals_S000_by_category", "reconciliation", "link_categories")},
           "note": "network totals are deduplicated on the union geometry; per-station blocks are non-exclusive; the duplication ratios are not demand multipliers"}
component_versions = {"station_master_sha256": sha_file(sm_path), "packages": consumed_packages,
                      "policy": "pinned at build time; scripts/miami_readiness.py marks this package STALE when any pinned layer republishes"}
config = {"required_layers": REQUIRED_LAYERS, "optional_layers": OPTIONAL_LAYERS, "config_input_layers": ["service_baseline"], "bands": BAND_KEYS + ["cum"],
          "config_inputs": {k: v["acquisition_status"] for k, v in config_input_fields(ids[0]).items()},
          "data_nature_by_layer": DATA_NATURE, "assembly_rule": "copy the producing layer's value envelopes verbatim; recompute nothing; add evidence_source and pins",
          "contract": "V2_站点输入包字段契约.md §2, §8, §10, §11"}
config_sha = sha_obj(config)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "component_versions": component_versions}
header = {"schema_version": "miami-station-input-package/1.0", **common, **SEMANTICS, "ai_usage_rules": AI_USAGE_RULES,
          "field_tags": {"provenance_class": ["observed", "derived", "assumption"],
                         "data_nature": ["measured", "survey_estimate", "administrative_record", "administrative_modeled", "model_output", "assumption"],
                         "value_status": ["value", "missing", "suppressed", "not_applicable", "confirmed_zero", "zero_absent_from_file"],
                         "acquisition_status": ["acquired", "assumed", "not_acquired", "derivable_from_gtfs", "not_approved"]},
          "readers": ["AI layer (batch reasoning; cite evidence ids)", "deterministic configuration rules (read config_inputs + scenario results)", "static web demo (per-station files)"]}

# ---------------- validation ----------------
def has_status(d):
    """every dict that carries 'value' must carry 'value_status' (structural check over the assembled package)"""
    if isinstance(d, dict):
        if "value" in d and "value_status" not in d and "ratio_id" not in d and "indicator_id" not in d and "unit" not in d: return False
        return all(has_status(v) for v in d.values())
    if isinstance(d, list): return all(has_status(v) for v in d)
    return True


pins_current = all((load(DATA / f"{c['stage']}_current.json")["package_id"] == c["package_id"]) for c in consumed_packages)
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "stations": len(station_pkgs), "station_ids_consistent_across_layers": set(ids) == set(sj_by) == set(dem_by) == set(jobs_by),
       "band_ring_areas_agree_across_layers": {"max_deviation_m2": r6(consistency["max_ring_area_dev_m2"]), "pass": consistency["max_ring_area_dev_m2"] < 1e-3},
       "land_areas_agree_demography_vs_jobs": {"max_deviation_m2": r6(consistency["max_land_area_dev_m2"]), "pass": consistency["max_land_area_dev_m2"] < 1e-3},
       "every_value_carries_value_status": has_status(station_pkgs),
       "pins_equal_current_pointers_at_build": pins_current,
       "required_layers_ready": all(L[s]["manifest"].get("ready_for_downstream") for s in REQUIRED_LAYERS),
       "optional_layers_present": {s: bool(optional[s]) for s in OPTIONAL_LAYERS},
       "config_inputs_acquired": {k: v["acquisition_status"] for k, v in station_pkgs[0]["miami_specific_inputs"].items()},
       "scope_statement": "PASS means the assembly is structurally consistent with its pinned layers. It is not a validation of the layers' numbers, "
                          "not ridership, not a configuration result; the configuration inputs are not acquired."}
ok = (val["station_ids_consistent_across_layers"] and val["band_ring_areas_agree_across_layers"]["pass"] and val["land_areas_agree_demography_vs_jobs"]["pass"]
      and val["every_value_carries_value_status"] and val["pins_equal_current_pointers_at_build"] and val["required_layers_ready"] and len(station_pkgs) == 21)
if os.environ.get("INPUT_PACKAGE_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

# ---------------- outputs, manifest, publish ----------------
if STAGING.exists(): shutil.rmtree(STAGING)
(STAGING / "stations").mkdir(parents=True)
OUTPUT_FILES = ["station_input_package.json", "input_package_index.json", "input_package_validation.json"] + [f"stations/{pid}.json" for pid in ids]
dump(STAGING / "station_input_package.json", {**header, "network": network, "stations": station_pkgs})
for s in station_pkgs: dump(STAGING / "stations" / f"{s['station_id']}.json", {**header, "station": s})
dump(STAGING / "input_package_index.json", {"schema_version": "miami-input-package-index/1.0", **common,
     "stations": [{"station_id": s["station_id"], "name": s["name"], "file": f"stations/{s['station_id']}.json", "lon": s["geometry_wgs84"]["coordinates"][0], "lat": s["geometry_wgs84"]["coordinates"][1]} for s in station_pkgs],
     "network_file": "station_input_package.json#network", "config_inputs": {k: v["acquisition_status"] for k, v in CONFIG_INPUTS.items()},
     "optional_layers": {s: bool(optional[s]) for s in OPTIONAL_LAYERS}})
dump(STAGING / "input_package_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-input-package-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": consumed_packages,
            "optional_layers_absent_at_build": [s for s in OPTIONAL_LAYERS if not optional[s]],   # readiness marks this package STALE once one of them is DONE
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment,
            "config_inputs": {k: ({"acquisition_status": "derived", "value_status": "value", "provenance_class": "derived", "source_package": sb["pin"]["package_id"]}
                                  if (k == "service_baseline" and sb)
                                  else ({"acquisition_status": "assumed", "value_status": "value", "provenance_class": "assumption", "source_file": "config/prt_operations_assumptions_v1.json"}
                                        if (MODULES and OPS) else {"acquisition_status": v["acquisition_status"], "value_status": "missing", "provenance_class": None}))
                              for k, v in CONFIG_INPUTS.items() if k in ("platform_constructible_space", "vehicle_parameters", "service_baseline")},
            "config_input_extras": {**({"platform_module_specification": {"acquisition_status": "acquired", "value_status": "value", "provenance_class": "observed",
                                                                          "data_nature": "design_specification", "source_file": "config/station_platform_modules_v1.json"}} if MODULES else {}),
                                    **({"ridership_baseline": {"acquisition_status": "acquired", "value_status": "value", "provenance_class": "observed", "data_nature": "measured",
                                                               "source_package": rr["pin"]["package_id"], "scope": "station-level average weekday boardings, reference only"}} if rr else {})},
            "method_summary": "assembles station_master + spatial_join + demography + jobs into per-station input packages with verbatim value envelopes, "
                              "evidence pointers, pinned layer versions and Miami-specific input placeholders; recomputes nothing",
            "contract": "V2_站点输入包字段契约.md §2, §8, §10, §11",
            "publish_policy": "content-addressed immutable package dir input_package/pkg-<id>; readers resolve input_package_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} stations={len(station_pkgs)} "
      f"files={len(OUTPUT_FILES)} pins={[c['package_id'] for c in consumed_packages]} optional_present={[s for s in OPTIONAL_LAYERS if optional[s]]}")
