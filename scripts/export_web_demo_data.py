#!/usr/bin/env python3
"""Export the compact, self-contained dataset behind the static web demo (docs/index.html).

Reads ONLY published packages through their pointers (verifying each package), the readiness view and the latest
regression results, and writes docs/data/demo_data.js (`window.DEMO_DATA = {...}`) plus the same JSON next to it.
Nothing is recomputed here: every number is copied from a package together with the package id it came from, so the
page can show provenance for any value. Geometry is simplified for drawing only (the packages keep the exact shapes).

    python3 scripts/export_web_demo_data.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

OUT_DIR = ROOT / "docs/data"
HARNESS = ROOT / "reviews/2026-09-18_step9_ai_layer_prep/regression_results.json"   # the latest full run; earlier runs stay in their own review folders
BAND_KEYS = ["b1", "b2", "b3", "cum"]
CATS = ["school", "clinic", "grocery", "park"]
SCEN = ["low", "medium", "high"]


def pkg(stage, manifest_name="manifest.json"):
    ptr = load(DATA / f"{stage}_current.json"); d = DATA / ptr["package_dir"]
    ok, m, problems = verify_package(d, manifest_name)
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    return ptr["package_id"], d, m


ids, dirs, manifests = {}, {}, {}
for stage, mname in (("spatial_join", "spatial_join_manifest.json"), ("demography", "manifest.json"), ("jobs", "manifest.json"), ("service_baseline", "manifest.json"),
                     ("ridership_reference", "manifest.json"), ("poi", "manifest.json"), ("input_package", "manifest.json"), ("scenarios", "manifest.json"), ("config", "manifest.json"),
                     ("rules", "manifest.json")):
    ids[stage], dirs[stage], manifests[stage] = pkg(stage, mname)
rules_doc = load(dirs["rules"] / "rule_results.json"); rules_by = {b["station_id"]: b for b in rules_doc["stations"]}
def rule_items(rows): return [{"id": r["rule_result_id"], "rule_id": r["rule_id"], "name": r["rule_name"], "scenario": r["scenario"], "status": r["status"], "basis": r["basis"], "message": r["message"]} for r in rows if r["status"] != "pass"]
kit_path = ROOT / "ai/miami/kit_manifest.json"; kit = load(kit_path) if kit_path.exists() else None

fwd, inv, _ = projection()
readiness = load(DATA / "gis_data_readiness.json")
stations_master = load(DATA / "station_master.geojson")["features"]
patterns = load(DATA / "service_patterns.json")["records"]
sj = load(dirs["spatial_join"] / "station_zoning_profile.json")
dem = load(dirs["demography"] / "station_demography_profile.json")
jobs = load(dirs["jobs"] / "station_jobs_profile.json")
svc = {s["station_id"]: s for s in load(dirs["service_baseline"] / "station_service_baseline.json")["stations"]}
rr_doc = load(dirs["ridership_reference"] / "station_ridership_reference.json"); rr = {s["station_id"]: s for s in rr_doc["stations"]}
poi_doc = load(dirs["poi"] / "poi_features.json")
sc = load(dirs["scenarios"] / "scenario_results.json"); sc_params = load(dirs["scenarios"] / "scenario_parameters.json")
cf = load(dirs["config"] / "station_config_results.json"); cf_params = load(dirs["config"] / "config_parameters.json")
cf_st = {s: {r["station_id"]: r for r in cf["scenarios"][s]["stations"]} for s in SCEN}
sc_st = {s: sc["scenarios"][s]["per_station"] for s in SCEN}
ip_dir = dirs["input_package"]


def env(e):
    """Compact value envelope: display value + uncertainty; None-safe."""
    if e is None: return None
    return {k: v for k, v in {"v": e.get("display_value", e.get("value")), "raw": e.get("value"), "moe": e.get("moe_90"), "cv": e.get("cv"), "rel": e.get("reliability_flag"),
                              "status": e.get("value_status"), "pct": e.get("display_percent"), "unit": e.get("unit")}.items() if v is not None}


def band_block(b):
    z, d, j = b["zoning"], b["demography"], b["jobs"]
    transects = sorted(((k, v["share_of_band"]) for k, v in z["by_Transect_D"].items()), key=lambda x: -x[1])
    med = d["median_household_income"]
    return {"label": b.get("band", "0-1/2 mi cumulative"), "inner_ft": b.get("inner_ft", 0), "outer_ft": b["outer_ft"], "ring_acres": b["display"]["ring_area"]["acres"], "land_acres": b["display"]["land_area"]["acres"],
            "zoning": {"zoned_share": z["zoned_area_share"], "uncovered_share": z["uncovered_area_share"], "polygon_count": z["polygon_count"],
                       "by_transect": [[k, round(s, 4)] for k, s in transects], "point_match_note": None},
            "demography": {"population": env(d["counts"]["D01"]), "households": env(d["counts"]["D02"]), "workers": env(d["counts"]["D06"]),
                           "under_18": env(d["counts"].get("D04")), "age_65_plus": env(d["counts"].get("D05")),
                           "transit_commute_share": env(d["ratios"]["R01"]), "wfh_share": env(d["ratios"]["R02"]), "zero_vehicle_share": env(d["ratios"]["R03"]),
                           "low_income_share": env(d["ratios"]["R04"]), "poverty_share": env(d["ratios"]["R05"]), "disability_share": env(d["ratios"]["R06"]), "age_65_share": env(d["ratios"]["R07"]),
                           "median_income": {"v": med.get("value"), "status": med.get("value_status"), "range": med.get("sensitivity_range"), "open_ended": med.get("open_ended"),
                                             "bg_without_median": med.get("block_groups_without_published_median")},
                           "density_per_sq_mi": d["density"]["R09_population_density"].get("value_persons_per_sq_mi"), "block_groups": d["source_units"]["block_groups"]},
            "jobs": {"jobs_all": env(j["jobs_by_workplace"]["JT00"]["C000"]), "jobs_primary": env(j["jobs_by_workplace"]["JT01"]["C000"]),
                     "resident_workers_primary": env(j["jobs_held_by_residents"]["JT01"]["C000"]),
                     "jobs_housing_ratio": {"v": j["ratios"]["J09_jobs_housing_ratio_primary"].get("value"), "status": j["ratios"]["J09_jobs_housing_ratio_primary"].get("value_status")},
                     "jobs_per_acre": j["density"]["J08_jobs_per_acre_JT00"].get("value") if isinstance(j["density"]["J08_jobs_per_acre_JT00"], dict) else j["density"]["J08_jobs_per_acre_JT00"],
                     "blocks": j["source_units"]["blocks"]},
            "poi": {c: b["poi"]["counts"][c]["count"] for c in CATS} if "poi" in b else None}


stations = []
for f in stations_master:
    p = f["properties"]; pid = p["station_id"]
    s = load(ip_dir / "stations" / f"{pid}.json")["station"]
    bands = {k: band_block(b) for k, b in zip(BAND_KEYS[:3], s["bands"])}; bands["cum"] = band_block(s["cumulative_0_to_half_mile"])
    sv = svc[pid]; am = sv["periods"]["am_peak"]; r = rr[pid]; rb = s["miami_specific_inputs"]["ridership_baseline"]
    stations.append({
        "id": pid, "name": p["name"], "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1], "gtfs_stop_ids": p.get("gtfs_stop_ids"), "loops": p.get("loops"),
        "geometry_role": p.get("geometry_role"), "mapping_status": s.get("mapping_status"), "existing": s.get("existing_classification"), "role": s.get("role_classification", {}).get("status"),
        "bands": bands,
        "point_zoning": {"status": s["point_zoning_match"]["status"], "zones": s["point_zoning_match"].get("matched_M21_ZONE")},
        "poi_nearest": {c: {k: v for k, v in s["poi_nearest_by_category"][c].items() if k in ("name", "distance_ft", "display_mi", "within_half_mile", "value_status", "poi_id")} for c in CATS},
        "service": {"am_peak_departures_per_hour": am["departures_per_hour"], "am_peak_headway_min": am["implied_headway_min_all_routes"], "am_peak_scheduled_departures": am["scheduled_departures"],
                    "weekday_scheduled_departures": sv["scheduled_departures_weekday_total"], "first_departure": sv["first_departure"], "last_departure": sv["last_departure"],
                    "routes": sv.get("routes"), "service_id": sv["day_type"]["service_id"]},
        "observed": {"avg_weekday_boardings_10mo_mean": r["avg_weekday_boardings_10_month_mean"], "min_max": r["avg_weekday_boardings_min_max"],
                     "latest": (r["avg_weekday_boardings_latest"]["value"] if isinstance(r["avg_weekday_boardings_latest"], dict) else r["avg_weekday_boardings_latest"]),
                     "latest_month": rb["value"]["avg_weekday_boardings_latest_month"], "share_of_system": r["share_of_system_avg_weekday_10_month_mean"],
                     "report_station_name": r["report_station_name"], "mapping_basis": r["mapping_basis"], "mapping_confirmed_by_owner": r["mapping_confirmed_by_owner"]},
        "scenarios": {sname: next(({"boardings": x["am_peak_hour"]["boardings"], "alightings": x["am_peak_hour"]["alightings"], "share_of_network_am_boardings": x["share_of_network_am_boardings"]}
                                   for x in sc_st[sname] if x["station_id"] == pid), None) for sname in SCEN},
        "config": {sname: {"vehicle_departures": cf_st[sname][pid]["vehicle_trips_am_peak_hour"]["departures"], "vehicle_arrivals": cf_st[sname][pid]["vehicle_trips_am_peak_hour"]["arrivals"],
                           "empty_vehicles_in": cf_st[sname][pid]["empty_vehicle_balance_per_hour"]["empty_vehicles_required_in"], "empty_vehicles_out": cf_st[sname][pid]["empty_vehicle_balance_per_hour"]["empty_vehicles_leaving"],
                           "berth_cycles": cf_st[sname][pid]["berths"]["berth_cycles_per_hour"], "design_cycles": cf_st[sname][pid]["berths"]["design_cycles_per_hour_with_within_hour_peaking"],
                           "usable_cycles_per_berth_hour": cf_st[sname][pid]["berths"]["usable_cycles_per_berth_hour"], "berths": cf_st[sname][pid]["berths"]["berths_required"],
                           "module": cf_st[sname][pid]["module"]["module_id"], "modules_needed": cf_st[sname][pid]["module"]["modules_needed"], "berths_provided": cf_st[sname][pid]["module"]["berths_provided"],
                           "footprint_ft2": cf_st[sname][pid]["module"]["footprint_ft2"], "fits_single_module": cf_st[sname][pid]["module"]["fits_single_module"],
                           "site_fit": cf_st[sname][pid]["site_fit"]["status"]} for sname in SCEN},
        "od_link_potential": {"home_side_JT01": s["od_link_potential"]["home_side"]["JT01"], "work_side_JT01": s["od_link_potential"]["work_side"]["JT01"]},
        "rules": {"version": rules_doc["rule_pack_version"], "summary": rules_by[pid]["summary"], "by_scenario": rules_by[pid]["by_scenario"], "items": rule_items(rules_by[pid]["results"])},
        "ai_analysis_status": s.get("ai_analysis_status"), "optional_layers": {k: v.get("status") for k, v in s["optional_layers"].items()}})
missing_scen = [(st["id"], k) for st in stations for k in SCEN if st["scenarios"][k] is None]
if missing_scen: raise SystemExit(f"HALT: scenario rows missing for {missing_scen[:3]}")

# ---------------- geometry for the schematic map (WGS84, simplified for drawing only) ----------------
def to_wgs84(geom):
    xs = list(geom.exterior.coords)[0] if geom.geom_type == "Polygon" else list(list(geom.geoms)[0].exterior.coords)[0]
    return shp_transform(inv.transform, geom) if abs(xs[0]) > 1000 else geom
union_doc = load(dirs["spatial_join"] / "network_half_mile_union.geojson")
union_geom = to_wgs84(unary_union([shape(ft["geometry"]) for ft in union_doc["features"]]))
window = shape(load(DATA / "study_window.geojson")["features"][0]["geometry"])
parks = [{"name": r["name"], "acres": r.get("area_acres"), "geometry": mapping(shape(r["geometry_wgs84"]).simplify(0.00003, preserve_topology=True))}
         for r in poi_doc["features"] if r["category"] == "park" and r.get("geometry_wgs84")]
pois_pts = [{"cat": r["category"], "name": r["name"], "lon": r["lon"], "lat": r["lat"]} for r in poi_doc["features"] if r["category"] != "park"]
seen, loops = set(), []
for rec in patterns:
    seq = rec["station_sequence"]; pairs = tuple(zip(seq, seq[1:]))
    if pairs in seen: continue
    seen.add(pairs); loops.append({"route_id": rec["route_id"], "shape_id": rec.get("shape_id"), "station_sequence": seq, "interpretation": rec.get("interpretation")})

# ---------------- network-level facts ----------------
netd, netj = dem["network"], jobs["network"]
network = {"union_sq_mi": sj["network"]["display"]["union"]["sq_mi"], "union_acres": sj["network"]["display"]["union"]["acres"], "sum_of_discs_sq_mi": sj["network"]["display"]["sum_of_discs"]["sq_mi"],
           "area_duplication_ratio": sj["network"]["area_duplication_ratio"],
           "population_dedup": env(netd["deduplicated"]["counts"]["D01"]), "households_dedup": env(netd["deduplicated"]["counts"]["D02"]), "workers_dedup": env(netd["deduplicated"]["counts"]["D06"]),
           "sum_of_station_cum_population": netd["sum_of_21_station_cumulative_discs"]["D01"], "population_duplication_ratio": netd["duplication_ratio"]["D01"],
           "transit_commute_share_dedup": env(netd["deduplicated"]["ratios"]["R01"]), "wfh_share_dedup": env(netd["deduplicated"]["ratios"]["R02"]),
           "jobs_all_dedup": env(netj["deduplicated"]["jobs_by_workplace"]["JT00"]["C000"]) if "deduplicated" in netj and "jobs_by_workplace" in netj["deduplicated"] else None,
           "poi_unique": load(dirs["poi"] / "station_poi_profile.json")["network"]["unique_facilities_in_network_half_mile_union"],
           "poi_in_window": load(dirs["poi"] / "station_poi_profile.json")["network"]["facilities_in_window"],
           "observed_system_avg_weekday_boardings": rr_doc["system"], "scenario_totals": {s: sc["scenarios"][s]["totals"] for s in SCEN},
           "config_network": {s: cf["scenarios"][s]["network"] for s in SCEN},
           "rules": {"version": rules_doc["rule_pack_version"], "summary": rules_doc["network"]["summary"], "items": rule_items(rules_doc["network"]["results"]),
                     "all": [{"id": r["rule_result_id"], "status": r["status"], "scenario": r["scenario"], "rule_id": r["rule_id"]} for r in rules_doc["network"]["results"]]}}
if network["jobs_all_dedup"] is None:   # jobs network block layout differs; copy whatever the package exposes
    network["jobs_network_block"] = {k: v for k, v in netj.items() if k not in ("source_units",)}

harness = None
if HARNESS.exists():
    h = load(HARNESS); n_checks = sum(len(s["checks"]) for s in h["scenarios"].values())
    harness = {"scenarios": len(h["scenarios"]), "checks": n_checks, "passed": h["passed"], "run_at": h["run_at"], "results_file": str(HARNESS.relative_to(ROOT))}

provenance = {
    "zoning": {"provenance_class": "observed", "data_nature": "administrative_record", "source": "City of Miami · Miami 21 zoning layer (CC-BY-4.0), snapshot 2026-09-14",
               "semantics": "statutory zoning = what is permitted or constrained; not land use, not population, not demand; no zone is excluded", "package": ids["spatial_join"],
               "evidence": "spatial_join/station_zoning_evidence.json → <station>|<band>|<FID>"},
    "demography": {"provenance_class": "observed (estimate) → derived (apportioned)", "data_nature": "survey_estimate", "source": "U.S. Census Bureau · ACS 2020–2024 5-year, block groups (vintage 2024); B18101 at tract level",
                   "period_note": "a five-year period estimate, not current population", "uncertainty": "90 % margin of error, root-sum-square over units; excludes the apportionment uncertainty",
                   "weighting": "block-group land area inside the band ÷ block-group land (TIGER water erased) — an assumption of even spread", "package": ids["demography"],
                   "evidence": "demography/demography_evidence.json → <station>|<band>|BG<block group>"},
    "jobs": {"provenance_class": "observed (administrative, modeled) → derived (apportioned)", "data_nature": "administrative_modeled", "source": "U.S. Census Bureau · LEHD LODES 8, Florida 2023, 2020 blocks (WAC / RAC / OD)",
             "semantics": "job counts and job-to-home links; never trips, never ridership; Florida residents working out of state are not covered", "weighting": "block land share, same rule as demography",
             "package": ids["jobs"], "evidence": "jobs/jobs_evidence.json → <station>|<band>|BLK<block>"},
    "poi": {"provenance_class": "observed", "data_nature": "administrative_record", "source": "Miami-Dade County GIS (schools, health facilities, county parks) · City of Miami (park boundaries) · USDA SNAP retailer locations; OpenStreetMap only as a grocery cross-check",
            "semantics": "facilities listed by the sources; straight-line distances from the reference point; absence = not found in these sources", "package": ids["poi"], "evidence": "poi/poi_evidence.json → <station>|<band>|<poi_id>"},
    "service": {"provenance_class": "derived", "data_nature": "administrative_record", "source": "Miami-Dade Transit GTFS static feed, weekday service, Metromover routes",
                "semantics": "scheduled departures at the station's stops; not operated service, not capacity, not ridership", "package": ids["service_baseline"]},
    "observed": {"provenance_class": "observed", "data_nature": "measured", "source": "Miami-Dade DTPW monthly Ridership Technical Reports, 2025-10 to 2026-07 (10 months)",
                 "semantics": "boardings (entries) of the current Metromover per average weekday; not trips, not OD, not alightings, not hourly, not demand for a new system; a reference, never a calibration target",
                 "package": ids["ridership_reference"]},
    "scenarios": {"provenance_class": "derived", "data_nature": "model_output", "source": "scenario chain over the input package (parameters P01/P02/P05 derived from LODES + ACS; A01–A07 assumptions)",
                  "semantics": "uncalibrated low / medium / high AM-peak person trips for links inside the network; excludes regional inflow and hub transfers; not a forecast", "package": ids["scenarios"]},
    "config": {"provenance_class": "derived", "data_nature": "model_output", "source": "PRT configuration chain (C01–C07 assumptions; platform modules from owner drawings)",
               "semantics": "berths, module and footprint per station per scenario; site fit assumed (C06); not an engineering design, not a capacity proof", "package": ids["config"]},
    "rules": {"provenance_class": "derived", "data_nature": "model_output", "source": f"rule pack {rules_doc['rule_pack_version']} (config/rules_v2.json) evaluated over the packages",
              "semantics": "arithmetic identities, project conventions, data-quality flags and scope limitations written for this study; not statutes, agency standards or supplier specifications", "package": ids["rules"]}}
ai_layer = {"status": "NOT_RUN", "note": "no model output exists yet", "kit": ({"kit_version": kit["kit_version"], "kb_version": kit["kb_version"], "prompt_version": kit["prompt_version"], "rule_pack_version": kit["rule_pack_version"],
                                                                         "briefs": len(kit["briefs"]), "facts_per_brief": kit["briefs"][0]["facts"] if kit["briefs"] else None} if kit else None)}

demo = {"schema_version": "miami-web-demo-data/1.0", "generated_on": "2026-09-17", "case": "Miami Metromover · 21 stations · full-line conversion study (demonstration)",
        "units": "computed in EPSG:26917 metres; displayed in feet, miles, acres and square miles",
        "packages": ids, "readiness": {"snapshot_date": readiness.get("snapshot_date"), "stages": {k: v["status"] for k, v in readiness["stages"].items()},
                                       "layers": {k: v.get("status") for k, v in readiness["layers"].items()}, "flags": {k: v for k, v in readiness["readiness_flags"].items() if k != "definitions"}},
        "harness": harness, "provenance": provenance, "ai_layer": ai_layer, "bands": {"radii_ft": [660, 1320, 2640], "labels": ["0–⅛ mi", "⅛–¼ mi", "¼–½ mi", "0–½ mi cumulative"]},
        "stations": stations, "network": network,
        "scenario_chain": {s: {"assumption_values": sc["scenarios"][s]["assumption_values"], "chain": sc["scenarios"][s]["chain"], "totals": sc["scenarios"][s]["totals"]} for s in SCEN},
        "scenario_parameters": sc_params, "scenario_meta": {k: sc[k] for k in ("is_observed_ridership", "is_calibrated", "calibration_note", "purpose", "excludes", "assumption_parameter_ids")},
        "observed_reference": sc.get("observed_reference"),
        "config_parameters": cf_params, "config_meta": {k: cf[k] for k in ("is_engineering_design", "is_capacity_proof", "purpose", "site_fit", "assumption_parameter_ids")},
        "geometry": {"window": mapping(window), "network_union": mapping(union_geom.simplify(0.00005, preserve_topology=True)), "parks": parks, "pois": pois_pts, "loops": loops},
        "attribution": ["U.S. Census Bureau (ACS, TIGER/Line, LEHD LODES)", "Miami-Dade County (GTFS, DTPW ridership reports, county GIS layers)", "City of Miami (Miami 21 zoning, park boundaries; CC-BY-4.0)",
                        "USDA FNS (SNAP retailer locations)", "© OpenStreetMap contributors (ODbL; cross-check only)"]}
OUT_DIR.mkdir(parents=True, exist_ok=True)
txt = json.dumps(demo, ensure_ascii=False, separators=(",", ":"))
(OUT_DIR / "demo_data.js").write_text("window.DEMO_DATA = " + txt + ";\n", encoding="utf-8")
(OUT_DIR / "demo_data.json").write_text(txt + "\n", encoding="utf-8")
print(f"exported stations={len(stations)} loops={len(loops)} parks={len(parks)} pois={len(pois_pts)} bytes={len(txt)} harness={harness} packages={ids}")
