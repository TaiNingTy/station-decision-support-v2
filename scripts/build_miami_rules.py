#!/usr/bin/env python3
"""Miami · deterministic rule results — V2 step 9a, stage `rules`.

Evaluates the versioned rule pack config/rules_v2.json over the published input-package, scenarios and config packages
and publishes one result per (station or network, scenario or -, rule) with a citable `rule_result_id`. The rule pack
holds arithmetic identities, project conventions, data-quality flags and scope limitations written for this study;
nothing here is a statute, an agency standard or a supplier specification (rules doc 规则 7; architecture note: the rule
engine runs versioned, confirmed rules — retrieved text never replaces a threshold).

The AI layer cites rule_result_id + rule pack version for every normative statement; a `critical` result means the
configuration must not be presented as usable. Publishes rules/pkg-<id>/ atomically (R3); readiness by
scripts/miami_readiness.py (R2).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

STAGE = "rules"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["rule_results.json", "rule_pack.json", "rules_validation.json"]
RULES_FILE = ROOT / "config/rules_v2.json"
SCEN = ["low", "medium", "high"]
ORDER = {"pass": 0, "info": 1, "warning": 2, "critical": 3}

pack = load(RULES_FILE); rules = {r["rule_id"]: r for r in pack["rules"]}
pkg = {}
for stage in ("input_package", "scenarios", "config"):
    ptr = load(DATA / f"{stage}_current.json"); d = DATA / ptr["package_dir"]; ok, m, problems = verify_package(d, "manifest.json")
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    pkg[stage] = {"dir": d, "ptr": ptr, "manifest": m}
ip_dir = pkg["input_package"]["dir"]
sc = load(pkg["scenarios"]["dir"] / "scenario_results.json"); sc_by = {s: {x["station_id"]: x for x in sc["scenarios"][s]["per_station"]} for s in SCEN}
cf = load(pkg["config"]["dir"] / "station_config_results.json"); cf_by = {s: {x["station_id"]: x for x in cf["scenarios"][s]["stations"]} for s in SCEN}
cf_params = load(pkg["config"]["dir"] / "config_parameters.json"); ops = cf_params["operations_assumptions"]
largest_module = max(m["berths"] for m in cf_params["platform_modules"]["modules"])
observed_share = (sc.get("observed_reference") or {}).get("observed", {}).get("station_share_of_system", {})
index = load(ip_dir / "index.json") if (ip_dir / "index.json").exists() else None
station_ids = sorted(p.stem for p in (ip_dir / "stations").glob("MIA-MM-*.json"))
stations = {pid: load(ip_dir / "stations" / f"{pid}.json")["station"] for pid in station_ids}
consumed_inputs = [consumed_entry("rule_pack", RULES_FILE)]
results = []


def emit(subject, scenario, rule_id, status, values, message):
    r = rules[rule_id]
    results.append({"rule_result_id": f"{subject}|{scenario or '-'}|{rule_id}", "subject": subject, "scenario": scenario, "rule_id": rule_id, "rule_name": r["name"],
                    "rule_pack_version": pack["version"], "basis": r["basis"], "status": status, "values": values, "message": message})


# ---------------- network rules ----------------
for s in SCEN:
    c1 = sc["scenarios"][s]["conservation_check"]
    emit("NET", s, "RC-01", "pass" if c1["pass"] else "critical", {"sum_boardings": c1["sum_boardings"], "sum_alightings": c1["sum_alightings"], "expected": c1["expected"]},
         "boardings and alightings both sum to the network AM-peak trips" if c1["pass"] else "allocation does not conserve trips; scenario result invalid")
    c2 = cf["scenarios"][s]["conservation_check"]
    emit("NET", s, "RC-02", "pass" if c2["pass"] else "critical", {"vehicle_departures": c2["vehicle_departures"], "vehicle_arrivals": c2["vehicle_arrivals"], "tolerance_vehicles": c2["tolerance_vehicles"]},
         "vehicle departures equal arrivals within tolerance" if c2["pass"] else "vehicle flows do not balance; configuration result invalid")
    net = cf["scenarios"][s]["network"]; ratio = net["network_vehicle_trips_over_lane_throughput"]; p = rules["RC-05"]["parameters"]
    st = "critical" if ratio >= p["critical_at"] else ("warning" if ratio >= p["warning_at"] else "pass")
    emit("NET", s, "RC-05", st, {"ratio": ratio, "vehicle_trips_per_hour": net["vehicle_trips_am_peak_hour"], "lane_throughput_per_hour": net["guideway_lane_throughput_vehicles_per_hour_at_min_headway"], "min_headway_s": ops["C05_min_guideway_headway_s"]["value"]},
         {"critical": "network vehicle trips exceed one lane's throughput at the minimum headway; infeasible as computed", "warning": "network vehicle trips are at or above 80 % of one lane's throughput; a line model is required before any capacity claim",
          "pass": "network vehicle trips are below 80 % of one lane's throughput (network-level ratio only)"}[st])
a03_low = sc["scenarios"]["low"]["assumption_values"]["A03_prt_adoption_share_of_all_mode_trips"]
r01 = next((p for p in load(pkg["scenarios"]["dir"] / "scenario_parameters.json").get("observed_or_derived_shared_by_all_scenarios", []) if p["id"].startswith("P06")), None)
r01_value = r01["value"] if r01 else None
if r01_value is None:   # fall back to the demography package's deduplicated network ratio
    dem = load(DATA / load(DATA / "demography_current.json")["package_dir"] / "station_demography_profile.json"); r01_value = dem["network"]["deduplicated"]["ratios"]["R01"]["value"]
emit("NET", None, "RC-06", "pass" if a03_low <= r01_value + 1e-9 else "warning", {"A03_low": a03_low, "observed_transit_commute_share_network": r01_value},
     "low adoption stays at or below the observed public-transportation commute share" if a03_low <= r01_value + 1e-9 else "low adoption exceeds the observed transit share; the low case is not a floor")

# ---------------- station rules ----------------
for pid in station_ids:
    s_ip = stations[pid]
    for s in SCEN:
        c = cf_by[s][pid]; v = c["vehicle_trips_am_peak_hour"]; b = c["berths"]; tol = rules["RC-03"]["parameters"]["tolerance_cycles"]
        cycles = max(v["departures"], v["arrivals"]); c04 = ops["C04_within_hour_peaking_factor"]["value"]
        design = cycles * c04; usable = b["usable_cycles_per_berth_hour"]; berths = math.ceil(design / usable - 1e-9) if usable > 0 else None
        ok = abs(cycles - b["berth_cycles_per_hour"]) <= tol and abs(design - b["design_cycles_per_hour_with_within_hour_peaking"]) <= tol and berths == b["berths_required"]
        emit(pid, s, "RC-03", "pass" if ok else "critical", {"recomputed": {"berth_cycles": r2(cycles), "design_cycles": r2(design), "berths": berths}, "published": {"berth_cycles": b["berth_cycles_per_hour"], "design_cycles": b["design_cycles_per_hour_with_within_hour_peaking"], "berths": b["berths_required"]}},
             "published berth arithmetic reproduces" if ok else "published berth numbers do not reproduce from the stated formula; result invalid")
        fits = c["module"]["fits_single_module"] and b["berths_required"] <= largest_module
        emit(pid, s, "RC-04", "pass" if fits else "warning", {"berths_required": b["berths_required"], "largest_module_berths": largest_module, "module": c["module"]["module_id"]},
             "requirement fits one drawn module" if fits else "requirement exceeds the largest drawn module; more than one module or another layout is needed")
        big = max(v["departures"], v["arrivals"]); imb = (abs(v["departures"] - v["arrivals"]) / big) if big > 0 else 0.0
        trig = imb > rules["RC-10"]["parameters"]["imbalance_share_at"]
        emit(pid, s, "RC-10", "info" if trig else "pass", {"vehicle_departures": v["departures"], "vehicle_arrivals": v["arrivals"], "imbalance_share": r6(imb), "empty_vehicles_in": c["empty_vehicle_balance_per_hour"]["empty_vehicles_required_in"], "empty_vehicles_out": c["empty_vehicle_balance_per_hour"]["empty_vehicles_leaving"]},
             "flows are strongly one-directional; the station depends on empty vehicles fed or removed by the guideway (no staging berths, C07)" if trig else "departures and arrivals are within the balance convention")
    site = cf_by["low"][pid]["site_fit"]
    emit(pid, None, "RC-07", "warning" if site["status"] == "assumed_sufficient" else "pass", {"site_fit_status": site["status"], "assumption_id": site.get("assumption_id")},
         "constructible platform space not acquired; site fit is assumed (C06) and must be confirmed by the owner" if site["status"] == "assumed_sufficient" else "site fit recorded")
    d01 = s_ip["cumulative_0_to_half_mile"]["demography"]["counts"]["D01"]; flag = d01.get("reliability_flag")
    emit(pid, None, "RC-08", {"low": "warning", "medium": "info", "high": "pass"}.get(flag, "warning"), {"population_display": d01.get("display_value"), "moe_90": d01.get("moe_90"), "cv": d01.get("cv"), "reliability_flag": flag},
         {"low": "half-mile population estimate is statistically unreliable (CV > 0.40); do not lean on its magnitude", "medium": "half-mile population estimate has medium reliability (CV 0.12-0.40)", "high": "half-mile population estimate has high reliability (CV <= 0.12)"}.get(flag, "reliability flag missing"))
    rb = s_ip["miami_specific_inputs"]["ridership_baseline"]["value"]
    renamed = rb.get("mapping_basis") != "same_name"
    emit(pid, None, "RC-09", "warning" if renamed else "pass", {"report_station_name": rb.get("report_station_name"), "mapping_basis": rb.get("mapping_basis"), "mapping_confirmed_by_owner": rb.get("mapping_confirmed_by_owner")},
         "published-boardings row matched by location under an older report name; owner confirmation required before use" if renamed else "same-name match with the published report (owner confirmation still pending, as for every station)")
    obs_share = observed_share.get(pid); diffs = {}
    for s in SCEN:
        sh = sc_by[s][pid]["share_of_network_am_boardings"]; diffs[s] = r6(sh - obs_share) if obs_share is not None else None
    worst = max((abs(x) for x in diffs.values() if x is not None), default=None)
    trig = worst is not None and worst > rules["RC-11"]["parameters"]["difference_at"]
    emit(pid, None, "RC-11", "info" if trig else "pass", {"scenario_share_minus_observed_share": diffs, "observed_share_of_system": obs_share},
         "the station's scenario share differs from its observed share by more than 5 points: a shape difference of an uncalibrated model against a reference, not an error to scale away" if trig else "scenario share is within 5 points of the observed share")
    ext = s_ip.get("external_connections_on_map") or []
    emit(pid, None, "RC-12", "info" if ext else "pass", {"external_connections_on_map": ext},
         f"external connections on the official map ({', '.join(ext)}): transfer inflow is excluded from the scenario boardings, which understate activity here" if ext else "no external connection on the official map; the exclusion of regional inflow still applies network-wide")
    emit(pid, None, "RC-13", "info", {"catchment_type": s_ip["cumulative_0_to_half_mile"].get("catchment_type"), "is_validated_walk_catchment": s_ip["cumulative_0_to_half_mile"].get("is_validated_walk_catchment"), "walk_model": s_ip["optional_layers"].get("walk_model", {}).get("status")},
         "bands are straight-line distances from a reference point that is not an entrance; no walk catchment is validated and the walk model is not built")

# ---------------- summaries + validation ----------------
def summarize(rows):
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ORDER}
    worst = max((r["status"] for r in rows), key=lambda k: ORDER[k], default="pass")
    return {"counts": counts, "overall": worst, "usable_as_computed": worst != "critical"}
by_station = {pid: [r for r in results if r["subject"] == pid] for pid in station_ids}
net_rows = [r for r in results if r["subject"] == "NET"]
station_blocks = [{"station_id": pid, "name": stations[pid]["name"], "summary": summarize(rows), "by_scenario": {s: summarize([r for r in rows if r["scenario"] == s]) for s in SCEN}, "results": rows} for pid, rows in by_station.items()]
ids = [r["rule_result_id"] for r in results]
expected_station_rules = {"station_x_scenario": ["RC-03", "RC-04", "RC-10"], "station": ["RC-07", "RC-08", "RC-09", "RC-11", "RC-12", "RC-13"]}
per_station_count = len(expected_station_rules["station_x_scenario"]) * len(SCEN) + len(expected_station_rules["station"])
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "rule_pack_version": pack["version"], "rules_in_pack": len(pack["rules"]), "results": len(results), "stations": len(station_ids),
       "ids_unique": len(ids) == len(set(ids)), "every_station_has_every_station_rule": all(len(rows) == per_station_count for rows in by_station.values()),
       "network_rules_per_scenario": all(sum(1 for r in net_rows if r["scenario"] == s) == 3 for s in SCEN) and sum(1 for r in net_rows if r["scenario"] is None) == 1,
       "every_rule_id_in_pack": all(r["rule_id"] in rules for r in results), "statuses_valid": all(r["status"] in ORDER for r in results),
       "critical_results": [r["rule_result_id"] for r in results if r["status"] == "critical"],
       "summary": {"network": summarize(net_rows), "stations_overall": {k: sum(1 for b in station_blocks if b["summary"]["overall"] == k) for k in ORDER}},
       "scope_statement": "PASS means the rule pack was evaluated completely and consistently over the packages; it says nothing about the rules being legally or technically sufficient. "
                          "A critical result is reported, not hidden, and does not fail this stage."}
ok = val["ids_unique"] and val["every_station_has_every_station_rule"] and val["network_rules_per_scenario"] and val["every_rule_id_in_pack"] and val["statuses_valid"] and len(station_ids) == 21
if os.environ.get("RULES_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

pack_sha = sha_file(RULES_FILE)
common = {"built_on": BUILT_ON, "rule_pack_version": pack["version"], "rule_pack_sha256": pack_sha, "input_package": pkg["input_package"]["ptr"]["package_id"],
          "scenarios_package": pkg["scenarios"]["ptr"]["package_id"], "config_package": pkg["config"]["ptr"]["package_id"]}
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "rule_results.json", {"schema_version": "miami-rule-results/1.0", **common, "provenance_class": "derived", "data_nature": "model_output",
     "is_legal_or_agency_standard": False, "severity_semantics": pack["severity_semantics"], "citation_format": pack["citation_format"],
     "network": {"summary": summarize(net_rows), "results": net_rows}, "stations": station_blocks})
dump(STAGING / "rule_pack.json", {**pack, "sha256_of_config_file": pack_sha})
dump(STAGING / "rules_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-rules-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": [package_entry("input_package"), package_entry("scenarios"), package_entry("config")],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": pack_sha, "config": {"rule_pack_id": pack["rule_pack_id"], "version": pack["version"], "rules": [r["rule_id"] for r in pack["rules"]]},
            "method_summary": "versioned rule pack evaluated over the input-package, scenarios and config packages; one citable result per (subject, scenario, rule); "
                              "critical results are reported and never hidden", "contract": "architecture note §1 (versioned rules); rules doc 规则 5, 7",
            "publish_policy": "content-addressed immutable package dir rules/pkg-<id>; readers resolve rules_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} results={len(results)} "
      f"network={val['summary']['network']['counts']} stations_overall={val['summary']['stations_overall']} critical={val['critical_results']}")
