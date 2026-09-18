#!/usr/bin/env python3
"""Miami · station configuration under PRT semantics — V2 step 6, stage `config`.

Chain (rules doc 规则 7), one parameter per step, every parameter tagged:
    person trips per AM peak hour (scenarios)  ->  vehicle trips (C01 average party size, NOT the 4-6 pax maximum)
    ->  berth cycles per hour = max(vehicle arrivals, vehicle departures)   (one cycle = one arrival + one departure, loaded or empty)
    ->  design cycles = cycles × C04 within-hour peaking (berth sizing only; never applied to the demand chain)
    ->  berths required = ceil(design cycles / (3600 / C02 berth cycle × C03 utilization))
    ->  smallest platform module whose berth count covers the requirement (owner-provided module drawings)
    ->  footprint (ft², m²); site fit = C06 assumption (constructible space per station not acquired)
    plus the empty-vehicle balance (|departures − arrivals| per hour) and a network-level guideway headway check (C05).
PM peak mirrors AM (scenario assumption A05), so berth requirements are identical for the PM peak.
The V1.1 "passengers per hour per berth" convention is NOT used; everything derives from the parameters above.
Publishes config/pkg-<id>/ atomically (R3); readiness by scripts/miami_readiness.py (R2).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

STAGE = "config"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_config_results.json", "config_parameters.json", "station_config_table.json", "config_validation.json"]
MODULES_FILE = ROOT / "config/station_platform_modules_v1.json"
OPS_FILE = ROOT / "config/prt_operations_assumptions_v1.json"
SCENARIOS = ["low", "medium", "high"]
RESULT_SEMANTICS = {"provenance_class": "derived", "data_nature": "model_output", "is_engineering_design": False, "is_capacity_proof": False,
                    "purpose": "demonstration of the configuration chain under PRT semantics with explicit parameter provenance; not a design and not a "
                               "proof that a full-line replacement is adequate (regional inflow and hub transfers are excluded from the demand)",
                    "site_fit": "assumed (C06): per-station constructible space has not been acquired"}

environment = lock_gate()


def layer(stage, manifest_name="manifest.json"):
    ptr = load(DATA / f"{stage}_current.json"); d = DATA / ptr["package_dir"]; ok, m, problems = verify_package(d, manifest_name)
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    if not m.get("ready_for_downstream"): raise SystemExit(f"HALT: {stage} package is not ready_for_downstream")
    return {"dir": d, "manifest": m, "pin": {"stage": stage, "package_id": ptr["package_id"], "package_dir": ptr["package_dir"], "manifest_sha256": ptr["manifest_sha256"]}}


sc, ip = layer("scenarios"), layer("input_package")
if not any(p["stage"] == "input_package" and p["package_id"] == ip["pin"]["package_id"] for p in sc["manifest"]["consumed_packages"]):
    raise SystemExit("HALT: the scenarios package was built against a different input package than the current one")
res = load(sc["dir"] / "scenario_results.json")
modules_spec = load(MODULES_FILE); ops_spec = load(OPS_FILE)
OPS = {k: v["value"] for k, v in ops_spec["assumptions"].items()}
C01 = OPS["C01_average_party_size_pax_per_vehicle_trip"]; C02 = OPS["C02_berth_cycle_s"]; C03 = OPS["C03_berth_utilization_max"]
C04 = OPS["C04_within_hour_peaking_factor"]; C05 = OPS["C05_min_guideway_headway_s"]
if C01 > modules_spec["vehicle_capacity_pax_max"]: raise SystemExit("HALT: average party size exceeds the vehicle capacity")
BERTH_CYCLES_PER_HOUR = 3600.0 / C02 * C03          # usable berth cycles per berth-hour
LANE_VEHICLES_PER_HOUR = 3600.0 / C05                # guideway throughput at the minimum headway
modules = sorted(modules_spec["modules"], key=lambda m: m["berths"])
largest = modules[-1]


def select_module(berths):
    if berths == 0: return {"module_id": None, "modules_needed": 0, "berths_provided": 0, "footprint_ft2": 0, "footprint_m2": 0.0, "fits_single_module": True}
    for m in modules:
        if m["berths"] >= berths:
            return {"module_id": m["module_id"], "layout": m["layout"], "modules_needed": 1, "berths_provided": m["berths"], "footprint_ft2": m["area_ft2_as_drawn"],
                    "footprint_m2": m["area_m2_derived_from_ft2"], "width_ft_in": m["width_ft_in"], "length_ft_in": m["length_ft_in"], "fits_single_module": True}
    n = math.ceil(berths / largest["berths"])
    return {"module_id": largest["module_id"], "layout": largest["layout"], "modules_needed": n, "berths_provided": n * largest["berths"],
            "footprint_ft2": n * largest["area_ft2_as_drawn"], "footprint_m2": r2(n * largest["area_m2_derived_from_ft2"]), "fits_single_module": False,
            "note": "requirement exceeds the largest drawn module; combining modules at one station is not covered by the drawings — flagged, not designed"}


def station_config(p):
    b, a = p["am_peak_hour"]["boardings"], p["am_peak_hour"]["alightings"]
    vd, va = b / C01, a / C01
    cycles = max(vd, va); design = cycles * C04
    berths = math.ceil(design / BERTH_CYCLES_PER_HOUR - 1e-9) if design > 0 else 0
    sel = select_module(berths)
    return {"station_id": p["station_id"], "name": p["name"],
            "person_trips_am_peak_hour": {"boardings": b, "alightings": a, "source": "scenarios package"},
            "vehicle_trips_am_peak_hour": {"departures": r2(vd), "arrivals": r2(va), "parameter": "C01_average_party_size_pax_per_vehicle_trip"},
            "empty_vehicle_balance_per_hour": {"empty_vehicles_required_in": r2(max(vd - va, 0.0)), "empty_vehicles_leaving": r2(max(va - vd, 0.0)),
                                               "note": "departures above arrivals must be fed by empty vehicles from the guideway (C07: no staging berths drawn)"},
            "berths": {"berth_cycles_per_hour": r2(cycles), "design_cycles_per_hour_with_within_hour_peaking": r2(design), "usable_cycles_per_berth_hour": r2(BERTH_CYCLES_PER_HOUR),
                       "berths_required": berths, "parameters": ["C02_berth_cycle_s", "C03_berth_utilization_max", "C04_within_hour_peaking_factor"],
                       "pm_peak_note": "PM mirrors AM (scenario assumption A05): identical berth requirement"},
            "module": sel, "site_fit": {"status": "assumed_sufficient", "assumption_id": "C06_site_footprint_available", "constructible_space_acquired": False},
            "reference_scheduled_departures_am_peak_per_hour": p.get("reference_scheduled_departures_am_peak_per_hour"),
            "reference_note": "current Metromover scheduled departures per hour (GTFS); a schedule reference, not a capacity comparison"}


results = {}
for scen in SCENARIOS:
    stations = [station_config(p) for p in res["scenarios"][scen]["per_station"]]
    total_dep = sum(s["vehicle_trips_am_peak_hour"]["departures"] for s in stations); total_arr = sum(s["vehicle_trips_am_peak_hour"]["arrivals"] for s in stations)
    results[scen] = {"scenario_id": scen, **RESULT_SEMANTICS, "stations": stations,
                     "network": {"vehicle_trips_am_peak_hour": r2(total_dep), "vehicle_arrivals_am_peak_hour": r2(total_arr),
                                 "guideway_lane_throughput_vehicles_per_hour_at_min_headway": r2(LANE_VEHICLES_PER_HOUR),
                                 "network_vehicle_trips_over_lane_throughput": r6(total_dep / LANE_VEHICLES_PER_HOUR),
                                 "headway_note": "network-level ratio only; which guideway link carries which trips needs a line model that does not exist here",
                                 "berths_required_total": sum(s["berths"]["berths_required"] for s in stations),
                                 "modules": {m["module_id"]: sum(1 for s in stations if s["module"]["module_id"] == m["module_id"]) for m in modules},
                                 "stations_exceeding_single_module": [s["station_id"] for s in stations if not s["module"]["fits_single_module"]],
                                 "footprint_total_ft2": sum(s["module"]["footprint_ft2"] for s in stations)},
                     "conservation_check": {"vehicle_departures": r2(total_dep), "vehicle_arrivals": r2(total_arr),
                                            "tolerance_vehicles": r2(len(stations) * 0.01 / C01),
                                            "tolerance_note": "the scenarios package publishes per-station person trips rounded to 0.01; 21 stations × 0.01 ÷ party size bounds the rounding gap",
                                            "pass": abs(total_dep - total_arr) <= len(stations) * 0.01 / C01}}
table = {"schema_version": "miami-station-config-table/1.0", **RESULT_SEMANTICS,
         "columns": ["station_id", "name"] + [f"{s}_{k}" for s in SCENARIOS for k in ("vehicle_departures_per_hour", "berths_required", "module", "footprint_ft2", "empty_vehicles_in_per_hour")] + ["reference_scheduled_departures_am_peak_per_hour"],
         "rows": [[st["station_id"], st["name"]] + [x for s in SCENARIOS for x in (results[s]["stations"][i]["vehicle_trips_am_peak_hour"]["departures"], results[s]["stations"][i]["berths"]["berths_required"],
                                                                                    results[s]["stations"][i]["module"]["module_id"], results[s]["stations"][i]["module"]["footprint_ft2"],
                                                                                    results[s]["stations"][i]["empty_vehicle_balance_per_hour"]["empty_vehicles_required_in"])]
                  + [st["reference_scheduled_departures_am_peak_per_hour"]] for i, st in enumerate(results["low"]["stations"])]}
parameters = {"schema_version": "miami-config-parameters/1.0",
              "platform_modules": {"acquisition_status": "acquired", "provenance_class": "observed", "data_nature": "design_specification", "source_file": rel(MODULES_FILE),
                                   "modules": [{k: m.get(k) for k in ("module_id", "layout", "berths", "width_ft_in", "length_ft_in", "area_ft2_as_drawn", "area_m2_derived_from_ft2", "metric_drawing_as_provided")} for m in modules],
                                   "vehicle_fit_statement": modules_spec["vehicle_fit_statement"], "vehicle_capacity_pax_max": modules_spec["vehicle_capacity_pax_max"]},
              "operations_assumptions": {k: {**v, "provenance_class": "assumption", "data_nature": "assumption"} for k, v in ops_spec["assumptions"].items()},
              "derived_constants": {"usable_berth_cycles_per_berth_hour": r2(BERTH_CYCLES_PER_HOUR), "lane_vehicles_per_hour": r2(LANE_VEHICLES_PER_HOUR)},
              "chain": "person trips -> vehicle trips (C01) -> berth cycles = max(arrivals, departures) -> × C04 -> ÷ (3600/C02 × C03) -> berths -> module -> footprint -> site fit (C06)",
              "not_in_chain": ["vehicle maximum capacity as a load", "V1.1 passengers-per-hour-per-berth convention", "a second demand peak factor"]}
tot_berths = [results[s]["network"]["berths_required_total"] for s in SCENARIOS]
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "conservation_all_scenarios": {s: results[s]["conservation_check"]["pass"] for s in SCENARIOS},
       "berths_are_nonnegative_integers": all(isinstance(st["berths"]["berths_required"], int) and st["berths"]["berths_required"] >= 0 for s in SCENARIOS for st in results[s]["stations"]),
       "monotonic_berths_low_le_medium_le_high": tot_berths[0] <= tot_berths[1] <= tot_berths[2],
       "every_station_present": all(len(results[s]["stations"]) == 21 for s in SCENARIOS),
       "party_size_within_vehicle_capacity": C01 <= modules_spec["vehicle_capacity_pax_max"],
       "module_selection_valid": all(st["module"]["berths_provided"] >= st["berths"]["berths_required"] for s in SCENARIOS for st in results[s]["stations"]),
       "no_nan": all(not math.isnan(st["vehicle_trips_am_peak_hour"]["departures"]) for s in SCENARIOS for st in results[s]["stations"]),
       "berths_total_by_scenario": dict(zip(SCENARIOS, tot_berths)), "stations_exceeding_single_module": {s: results[s]["network"]["stations_exceeding_single_module"] for s in SCENARIOS},
       "assumption_ids": sorted(ops_spec["assumptions"]),
       "scope_statement": "PASS means the configuration arithmetic is consistent with its inputs. Berth counts and footprints are model outputs on assumed PRT "
                          "operating values and an assumed site fit; they are not a design and not a capacity proof."}
ok = (all(val["conservation_all_scenarios"].values()) and val["berths_are_nonnegative_integers"] and val["monotonic_berths_low_le_medium_le_high"]
      and val["every_station_present"] and val["party_size_within_vehicle_capacity"] and val["module_selection_valid"] and val["no_nan"])
if os.environ.get("CONFIG_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

config = {"modules_file_sha256": sha_file(MODULES_FILE), "operations_file_sha256": sha_file(OPS_FILE), "scenarios": SCENARIOS, "chain": parameters["chain"]}
config_sha = sha_obj(config)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "scenarios_package": sc["pin"]["package_id"], "input_package": ip["pin"]["package_id"]}
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_config_results.json", {"schema_version": "miami-station-config-results/1.0", **common, **RESULT_SEMANTICS, "assumption_parameter_ids": val["assumption_ids"], "scenarios": results})
dump(STAGING / "config_parameters.json", {**parameters, **common})
dump(STAGING / "station_config_table.json", {**table, **common})
dump(STAGING / "config_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-config-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": [consumed_entry("platform_modules", MODULES_FILE), consumed_entry("operations_assumptions", OPS_FILE)],
            "consumed_packages": [sc["pin"], ip["pin"]],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment, "assumption_parameter_ids": val["assumption_ids"],
            "method_summary": "PRT configuration: scenario person trips -> vehicle trips (party size) -> berth cycles with within-hour peaking and utilization -> berths -> "
                              "owner-drawn platform module -> footprint; empty-vehicle balance; network headway ratio; site fit assumed",
            "contract": "V2_站点输入包字段契约.md §8, §10; rules doc 规则 7",
            "publish_policy": "content-addressed immutable package dir config/pkg-<id>; readers resolve config_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} berths_total={dict(zip(SCENARIOS, tot_berths))} "
      f"exceeding_single_module={val['stations_exceeding_single_module']['high']} lane_ratio_high={results['high']['network']['network_vehicle_trips_over_lane_throughput']}")
