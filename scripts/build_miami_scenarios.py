#!/usr/bin/env python3
"""Miami · low / medium / high peak-hour scenarios — V2 step 5b, stage `scenarios`.

Rules doc 规则 5 chain, exactly one step at a time:
    job links (internal, both ends inside the network)  ->  weekday commute person trips  ->  all-purpose trips
    ->  peak-hour trips  ->  PRT trips (adoption)  ->  station boardings / alightings (allocation, conservation)
Decisions applied (2026-09-15): base = all-mode commute trips; adoption = share of all-mode trips; current transit share
is only a reference bound for the LOW scenario; hub transfer inflow is NOT modeled (field kept); return trips mirror the
AM peak; ONE peak-hour parameter (derived from ACS B08302), never multiplied by a second peak factor.
Every parameter carries provenance_class / data_nature and the assumption ids it depends on; the three scenarios differ
ONLY in assumption-class parameters. Results are model outputs for the interview demonstration of the chain; they are
not observed ridership and are not calibrated (ridership baseline not acquired).
Publishes scenarios/pkg-<id>/ atomically (R3); readiness by scripts/miami_readiness.py (R2).
"""
import csv, gzip, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

STAGE = "scenarios"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["scenario_results.json", "scenario_parameters.json", "station_scenario_table.json", "scenario_validation.json"]
SCENARIOS = ["low", "medium", "high"]
ASSUMPTIONS = {
    "A01_attendance_rate": {"value": 0.85, "statement": "85 % of primary-job holders who do not work from home make a commute trip on a typical weekday",
                            "reference": "leave/absence and shift patterns are not observed locally; a single value for all scenarios"},
    "A02_non_commute_trips_per_commute_trip": {"low": 0.5, "medium": 1.0, "high": 1.5,
                                               "statement": "non-commute trips inside the network per commute trip",
                                               "reference": "NHTS national purpose shares show work trips are a minority of person trips; the corridor-relevant fraction and the "
                                                            "Miami transfer coefficient are NOT observed — the whole ratio is an assumption"},
    "A03_prt_adoption_share_of_all_mode_trips": {"low": 0.05, "medium": 0.15, "high": 0.30,
                                                      "statement": "share of ALL-MODE trips that would use the PRT service",
                                                      "reference_bound": "low must not exceed the observed network public-transportation commute share (R01, ACS)"},
    "A04_station_allocation_rule": {"statement": "each block-to-block link is split among the candidate stations at each end in proportion to the block's land share "
                                                 "inside each station's half-mile disc, normalised to 1 (conservation by construction)"},
    "A05_direction_and_return": {"statement": "AM peak: home -> work; PM peak mirrors the AM peak (boardings <-> alightings); returns equal outbound trips"},
    "A06_non_commute_pattern": {"statement": "non-commute trips follow the commute OD pattern and the same station allocation"},
    "A07_departure_window_equals_station_window": {"statement": "the ACS departure-from-home hour is treated as the station arrival hour; B08302 has no return-trip distribution"},
}
ASSUMPTION_IDS = sorted(ASSUMPTIONS)
RESULT_SEMANTICS = {"provenance_class": "derived", "data_nature": "model_output", "is_observed_ridership": False, "is_calibrated": False,
                    "calibration_note": "ridership_baseline not acquired; no calibration against Metromover counts",
                    "purpose": "interview demonstration of the calculation chain with explicit parameter provenance; not a forecast",
                    "excludes": ["hub_transfer_inflow (not modeled in the Miami case)", "links with one end outside the network's half-mile discs",
                                 "the uncovered fraction of links in blocks that only partly lie inside the network union",
                                 "Florida residents working out of state", "visitors and non-resident non-work trips"]}

environment = lock_gate()

# ---------------- consumed packages ----------------
def layer(stage, manifest_name="manifest.json"):
    ptr = load(DATA / f"{stage}_current.json"); d = DATA / ptr["package_dir"]; ok, m, problems = verify_package(d, manifest_name)
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    if not m.get("ready_for_downstream"): raise SystemExit(f"HALT: {stage} package is not ready_for_downstream")
    return {"dir": d, "manifest": m, "pin": {"stage": stage, "package_id": ptr["package_id"], "package_dir": ptr["package_dir"], "manifest_sha256": ptr["manifest_sha256"]}}


ip, jobs, sb = layer("input_package"), layer("jobs"), layer("service_baseline")
rr = layer("ridership_reference") if (DATA / "ridership_reference_current.json").exists() else None   # observed reference, optional
rr_doc = load(rr["dir"] / "station_ridership_reference.json") if rr else None
pkg = load(ip["dir"] / "station_input_package.json"); od = load(jobs["dir"] / "od_summary.json")
cov = {b: x.get("share_in_network_union", 0.0) for b, x in load(jobs["dir"] / "block_values.json")["blocks"].items()}
if not any(p["stage"] == "jobs" and p["package_id"] == jobs["pin"]["package_id"] for p in ip["manifest"]["consumed_packages"]):
    raise SystemExit("HALT: the input package was built against a different jobs package than the current one")
stations = {s["station_id"]: s for s in pkg["stations"]}; ids = sorted(stations)
net_dem = pkg["network"]["demography"]["deduplicated"]

# ---------------- observed / derived parameters (shared by all scenarios) ----------------
links_both_in = od["totals_S000_by_category"]["both_in"]
P01 = {"id": "P01_internal_commute_links_JT01_coverage_weighted", "value": od["both_in_coverage_weighted_S000"]["JT01"],
       "unit": "primary jobs (persons) with residence and workplace inside the network's half-mile union, counted for the covered fraction of each block",
       "whole_block_upper_bound": links_both_in["JT01"],
       "coverage_rule": "each both_in link counts for cov_h × cov_w, where cov is the share of the block's LAND inside the network half-mile union; "
                        "a block that only touches a disc does not bring all of its links (the whole-block count above is the upper bound)",
       "provenance_class": "derived", "data_nature": "administrative_modeled",
       "depends_on_assumptions": ["areal_interpolation_land_share (the same convention as the demography and jobs layers)"],
       "source": f"jobs package {jobs['pin']['package_id']} od_summary.both_in_coverage_weighted_S000.JT01 (block cov in block_values.json)",
       "note": "LODES 2023 job links, not trips; JT00 (all jobs) whole-block count would be " + str(links_both_in["JT00"])}
P02 = {"id": "P02_work_from_home_share", "value": net_dem["ratios"]["R02"]["value"], "moe_90": net_dem["ratios"]["R02"]["moe_90"], "provenance_class": "derived", "data_nature": "survey_estimate",
       "source": "demography network dedup R02 = B08301_021 / B08301_001 (ACS 2020-2024)", "note": "residence-based; applied to the residents' end of every link"}
bins = net_dem["departure_time_bins"]; total_non_wfh = net_dem["counts"]["D08_total"]["value"]
windows = []
half = ["003", "004", "005", "006", "007", "008", "009", "010"]
for i in range(len(half) - 1):
    a, b = half[i], half[i + 1]
    windows.append({"window": f"{bins[a]['label'].split(' to ')[0]} to {bins[b]['label'].split(' to ')[1]}", "bins": [a, b], "workers": (bins[a]["value"] or 0) + (bins[b]["value"] or 0)})
for k in ("011", "012", "013"): windows.append({"window": bins[k]["label"], "bins": [k], "workers": bins[k]["value"] or 0})
peak = max(windows, key=lambda w: w["workers"])
P05 = {"id": "P05_peak_hour_share", "value": r6(peak["workers"] / total_non_wfh) if total_non_wfh else None, "window": peak["window"], "bins": peak["bins"],
       "provenance_class": "derived", "data_nature": "survey_estimate", "depends_on_assumptions": ["A07_departure_window_equals_station_window"],
       "source": "demography network dedup departure_time_bins (B08302) — the 60-minute window with the most departures, over workers not working from home",
       "alternative_source_not_acquired": "Metromover hourly ridership report (observed) — would REPLACE this parameter, never multiply it",
       "candidates": windows}
P06_ref = {"id": "P06_reference_public_transportation_commute_share", "value": net_dem["ratios"]["R01"]["value"], "provenance_class": "observed", "data_nature": "survey_estimate",
           "source": "demography network dedup R01 = B08301_010 / B08301_001", "role": "reference bound for the LOW adoption assumption; NOT part of the multiplication chain"}

# ---------------- links with candidate stations ----------------
def parse_cands(s):
    return {p.split(":")[0]: float(p.split(":")[1]) for p in s.split("|")} if s else {}


def normalise(c):
    t = sum(c.values()); return {k: v / t for k, v in c.items()} if t > 0 else {}


links = []
with gzip.open(jobs["dir"] / "od_links_subset.csv.gz", "rt", encoding="utf-8", newline="") as fh:
    for row in csv.DictReader(fh):
        if row["link_category"] != "both_in": continue
        j = int(row["S000_JT01"])
        if j <= 0: continue
        links.append((row["h_geocode"], row["w_geocode"], j, normalise(parse_cands(row["h_candidate_stations"])), normalise(parse_cands(row["w_candidate_stations"])),
                      cov.get(row["h_geocode"], 0.0) * cov.get(row["w_geocode"], 0.0)))
if sum(l[2] for l in links) != P01["whole_block_upper_bound"]: raise SystemExit("HALT: both_in JT01 links do not reconcile with od_summary (whole-block count)")
if abs(sum(l[2] * l[5] for l in links) - P01["value"]) > 1e-6 * max(1.0, P01["value"]): raise SystemExit("HALT: coverage-weighted links do not reconcile with od_summary")
reference_departures = {pid: stations[pid]["miami_specific_inputs"]["service_baseline"]["value"]["periods"]["am_peak"]["departures_per_hour"]
                        if stations[pid]["miami_specific_inputs"]["service_baseline"]["value_status"] == "value" else None for pid in ids}


def run(scen):
    a02, a03 = ASSUMPTIONS["A02_non_commute_trips_per_commute_trip"][scen], ASSUMPTIONS["A03_prt_adoption_share_of_all_mode_trips"][scen]
    a01 = ASSUMPTIONS["A01_attendance_rate"]["value"]
    factor = (1 - P02["value"]) * a01 * (1 + a02) * P05["value"] * a03
    board = {pid: 0.0 for pid in ids}; alight = {pid: 0.0 for pid in ids}; unallocated = 0.0
    for h, w, j, hc, wc, cw in links:
        t = j * cw * factor   # covered fraction of the link × the scenario chain
        if not hc or not wc: unallocated += t; continue
        for pid, x in hc.items(): board[pid] += t * x
        for pid, x in wc.items(): alight[pid] += t * x
    commuters = P01["value"] * (1 - P02["value"]) * a01
    chain = [{"step": 1, "name": "internal commute links, coverage-weighted (persons with primary job, both ends inside the network union)", "value": P01["value"],
              "whole_block_upper_bound": P01["whole_block_upper_bound"], "parameter": "P01"},
             {"step": 2, "name": "weekday commute person trips, AM direction", "value": r2(commuters), "formula": "P01 × (1 − P02) × A01", "parameters": ["P01", "P02", "A01_attendance_rate"]},
             {"step": 3, "name": "all-purpose trips inside the network, AM direction", "value": r2(commuters * (1 + a02)), "formula": "step2 × (1 + A02)", "parameters": ["A02_non_commute_trips_per_commute_trip"]},
             {"step": 4, "name": "peak-hour trips, AM direction", "value": r2(commuters * (1 + a02) * P05["value"]), "formula": "step3 × P05", "parameters": ["P05_peak_hour_share"]},
             {"step": 5, "name": "PRT peak-hour trips, AM direction", "value": r2(commuters * (1 + a02) * P05["value"] * a03), "formula": "step4 × A03", "parameters": ["A03_prt_adoption_share_of_all_mode_trips"]},
             {"step": 6, "name": "station boardings / alightings (allocation)", "value": r2(sum(board.values())), "formula": "per-link split by A04; PM mirror by A05", "parameters": ["A04_station_allocation_rule", "A05_direction_and_return", "A06_non_commute_pattern"]}]
    expected = P01["value"] * factor   # unrounded; chain values are rounded for display only
    total = chain[4]["value"]
    per_station = [{"station_id": pid, "name": stations[pid]["name"],
                    "am_peak_hour": {"boardings": r2(board[pid]), "alightings": r2(alight[pid]), "activity": r2(board[pid] + alight[pid])},
                    "pm_peak_hour_mirror": {"boardings": r2(alight[pid]), "alightings": r2(board[pid]), "activity": r2(board[pid] + alight[pid])},
                    "share_of_network_am_boardings": (r6(board[pid] / sum(board.values())) if sum(board.values()) else None),
                    "reference_scheduled_departures_am_peak_per_hour": reference_departures[pid],
                    "reference_note": "scheduled Metromover departures per hour (GTFS, observed record); not capacity, not a comparison of adequacy"} for pid in ids]
    return {"scenario_id": scen, **RESULT_SEMANTICS, "assumption_values": {"A01_attendance_rate": a01, "A02_non_commute_trips_per_commute_trip": a02, "A03_prt_adoption_share_of_all_mode_trips": a03},
            "chain": chain, "totals": {"prt_am_peak_hour_trips": total, "prt_pm_peak_hour_trips_mirror": total,
                                       "prt_weekday_trips_both_directions": r2(2 * commuters * (1 + a02) * a03), "unit": "person trips"},
            "conservation_check": {"sum_boardings": r2(sum(board.values())), "sum_alightings": r2(sum(alight.values())), "expected": r2(expected),
                                   "unallocated_trips": r2(unallocated), "tolerance": "1e-6 relative on unrounded values",
                                   "pass": abs(sum(board.values()) - expected) < 1e-6 * max(1.0, expected) and abs(sum(alight.values()) - expected) < 1e-6 * max(1.0, expected) and unallocated == 0.0},
            "per_station": per_station}


results = {scen: run(scen) for scen in SCENARIOS}
totals = [results[s]["totals"]["prt_am_peak_hour_trips"] for s in SCENARIOS]


def spearman(a, b):
    """Rank correlation (average ranks for ties) without scipy."""
    def ranks(x):
        order = sorted(range(len(x)), key=lambda i: x[i]); r = [0.0] * len(x); i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]: j += 1
            for k in range(i, j + 1): r[order[k]] = (i + j) / 2.0 + 1.0
            i = j + 1
        return r
    ra, rb = ranks(a), ranks(b); n = len(a); ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)); va = sum((x - ma) ** 2 for x in ra); vb = sum((y - mb) ** 2 for y in rb)
    return r6(cov / math.sqrt(va * vb)) if va and vb else None


observed_reference = None
if rr_doc:
    obs_share = {s["station_id"]: s["share_of_system_avg_weekday_10_month_mean"] for s in rr_doc["stations"]}
    obs_wk = {s["station_id"]: s["avg_weekday_boardings_10_month_mean"] for s in rr_doc["stations"]}
    sys_mean = rr_doc["system"]["avg_weekday_boardings_10_month_mean"]
    shape = {}
    for scen in SCENARIOS:
        sc_share = {p["station_id"]: (p["share_of_network_am_boardings"] or 0.0) for p in results[scen]["per_station"]}
        shape[scen] = {"spearman_rank_correlation_station_shares": spearman([sc_share[i] for i in ids], [obs_share[i] for i in ids]),
                       "max_abs_share_difference": r6(max(abs(sc_share[i] - obs_share[i]) for i in ids)),
                       "largest_differences": sorted(({"station_id": i, "scenario_share": r6(sc_share[i]), "observed_share": obs_share[i], "difference": r6(sc_share[i] - obs_share[i])} for i in ids),
                                                     key=lambda d: -abs(d["difference"]))[:5]}
    observed_reference = {"role": "observed REFERENCE for scale and station-share shape; NOT a calibration target", "source_package": rr["pin"],
                          "observed": {"system_avg_weekday_boardings_10_month_mean": sys_mean, "window": rr_doc["system"]["window"], "unit": "boardings of the current Metromover per average weekday",
                                       "station_avg_weekday_boardings": obs_wk, "station_share_of_system": obs_share},
                          "scale": {scen: {"scenario_weekday_trips_both_directions": results[scen]["totals"]["prt_weekday_trips_both_directions"],
                                           "observed_system_avg_weekday_boardings": sys_mean,
                                           "ratio_scenario_over_observed": r6(results[scen]["totals"]["prt_weekday_trips_both_directions"] / sys_mean)} for scen in SCENARIOS},
                          "station_share_shape": shape,
                          "reading": "the scale ratios are well below 1 because the scenarios cover internal links only (no regional inflow, no hub transfers, no visitors); "
                                     "the share comparison is unit-free and asks whether the allocation places trips at the stations where boardings are observed"}


table = {"schema_version": "miami-station-scenario-table/1.0", "built_on": BUILT_ON, **RESULT_SEMANTICS, "unit": "person trips per AM peak hour",
         "columns": ["station_id", "name", "low_boardings", "low_alightings", "medium_boardings", "medium_alightings", "high_boardings", "high_alightings", "reference_scheduled_departures_am_peak_per_hour"],
         "rows": [[pid, stations[pid]["name"]] + [x for s in SCENARIOS for x in (results[s]["per_station"][i]["am_peak_hour"]["boardings"], results[s]["per_station"][i]["am_peak_hour"]["alightings"])] + [reference_departures[pid]]
                  for i, pid in enumerate(ids)]}
parameters = {"schema_version": "miami-scenario-parameters/1.0", "built_on": BUILT_ON,
              "observed_or_derived_shared_by_all_scenarios": [P01, P02, P05, P06_ref],
              "assumptions": {k: {**v, "provenance_class": "assumption", "data_nature": "assumption"} for k, v in ASSUMPTIONS.items()},
              "scenario_rule": "low / medium / high change ONLY A02 and A03; A01, A04-A07 and every observed/derived parameter are shared",
              "chain": "internal job links -> weekday commute trips -> all-purpose trips -> peak-hour trips -> PRT trips -> station boardings/alightings",
              "not_in_chain": ["current public-transportation share (reference bound only)", "a second peak factor (would double-count with P05)", "hub transfer inflow"]}

val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "conservation_all_scenarios": {s: results[s]["conservation_check"]["pass"] for s in SCENARIOS},
       "monotonic_low_le_medium_le_high": totals[0] <= totals[1] <= totals[2],
       "low_adoption_not_above_observed_transit_share": ASSUMPTIONS["A03_prt_adoption_share_of_all_mode_trips"]["low"] <= (P06_ref["value"] or 0),
       "single_peak_parameter": True, "links_used": len(links), "links_reconcile_with_od_summary": True,
       "coverage_weighting": {"whole_block_links_JT01": P01["whole_block_upper_bound"], "coverage_weighted_links_JT01": P01["value"],
                              "links_touching_partially_covered_blocks": sum(1 for l in links if l[5] < 0.999999),
                              "persons_in_those_links_whole_block": sum(l[2] for l in links if l[5] < 0.999999)},
       "every_station_present": all(len(results[s]["per_station"]) == 21 for s in SCENARIOS),
       "no_nan": all(not math.isnan(x) for s in SCENARIOS for p in results[s]["per_station"] for x in (p["am_peak_hour"]["boardings"], p["am_peak_hour"]["alightings"])),
       "assumption_ids": ASSUMPTION_IDS, "peak_window": P05["window"], "totals_am_peak": dict(zip(SCENARIOS, totals)),
       "observed_reference_present": observed_reference is not None,
       "observed_reference_rank_correlation_in_range": (all(-1.0 <= (v["spearman_rank_correlation_station_shares"] or 0.0) <= 1.0 for v in observed_reference["station_share_shape"].values()) if observed_reference else None),
       "scope_statement": "PASS means the chain is arithmetically consistent and conserves trips. The results are uncalibrated model outputs built on the listed "
                          "assumptions; they exclude every trip with one end outside the network and all hub transfer inflow."}
ok = (all(val["conservation_all_scenarios"].values()) and val["monotonic_low_le_medium_le_high"] and val["low_adoption_not_above_observed_transit_share"]
      and val["every_station_present"] and val["no_nan"] and P05["value"] is not None)
if os.environ.get("SCENARIOS_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

config = {"scenarios": SCENARIOS, "assumptions": ASSUMPTIONS, "chain": parameters["chain"], "base": "all-mode commute trips (decision 2026-09-15)",
          "hub_inflow": "kept as a field, not modeled", "peak_parameter": "P05 from ACS B08302 (single parameter)", "link_filter": "both_in, JT01 > 0"}
config_sha = sha_obj(config)
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "input_package": ip["pin"]["package_id"], "jobs_package": jobs["pin"]["package_id"], "service_baseline_package": sb["pin"]["package_id"]}
dump(STAGING / "scenario_results.json", {"schema_version": "miami-scenario-results/1.1", **common, **RESULT_SEMANTICS, "assumption_parameter_ids": ASSUMPTION_IDS, "scenarios": results,
                                          "observed_reference": observed_reference})
dump(STAGING / "scenario_parameters.json", {**parameters, **common})
dump(STAGING / "station_scenario_table.json", {**table, **common})
dump(STAGING / "scenario_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-scenarios-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": [], "consumed_packages": [ip["pin"], jobs["pin"], sb["pin"]] + ([rr["pin"]] if rr else []),
            "optional_layers_absent_at_build": ([] if rr else ["ridership_reference"]),
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment, "assumption_parameter_ids": ASSUMPTION_IDS,
            "method_summary": "internal LODES job links -> weekday commute trips (ACS WFH share, attendance assumption) -> all-purpose trips (assumption) -> peak hour "
                              "(single ACS-derived share) -> PRT adoption (assumption, low bounded by observed transit share) -> station allocation with conservation; PM mirror",
            "contract": "V2_站点输入包字段契约.md §9, §10; rules doc 规则 5",
            "publish_policy": "content-addressed immutable package dir scenarios/pkg-<id>; readers resolve scenarios_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} links={len(links)} "
      f"peak_window={P05['window']!r} share={P05['value']} totals_am_peak={dict(zip(SCENARIOS, totals))} conservation={val['conservation_all_scenarios']}")
