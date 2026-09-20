#!/usr/bin/env python3
"""Build the AI interpretation kit for Miami (V2 step 9b): knowledge-base manifest + one brief per station with citable
fact ids + kit manifest. Nothing is recomputed: every fact is copied from a verified package and points back to it.

Outputs
  kb/v2/manifest.json                 kb_version, sha256 of every KB document, the agent prompt and the output schema
  ai/miami/briefs/<station>.json      the brief the model reads (facts with ids, rule results, assumptions, not-available list)
  ai/miami/briefs/<station>.md        the same brief rendered for pasting into the Coze UI
  ai/miami/kit_manifest.json          kit_version, package ids, sha256 of every brief
    python3 scripts/build_miami_ai_kit.py
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

KIT_VERSION, KB_VERSION, PROMPT_VERSION = "ai-kit-v2.1", "kb-v2.1", "prompt-v2.1"
KB_DIR, OUT = ROOT / "kb/v2", ROOT / "ai/miami"
PROMPT, SCHEMA = KB_DIR / "AGENT_PROMPT_v2.md", ROOT / "config/ai_output_schema_v2.json"
SCEN = ["low", "medium", "high"]
CATS = ["school", "clinic", "grocery", "park"]


def pkg(stage, manifest_name="manifest.json"):
    ptr = load(DATA / f"{stage}_current.json"); d = DATA / ptr["package_dir"]; ok, m, problems = verify_package(d, manifest_name)
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    return ptr["package_id"], d


ids, dirs = {}, {}
for stage, mname in (("spatial_join", "spatial_join_manifest.json"), ("demography", "manifest.json"), ("jobs", "manifest.json"), ("service_baseline", "manifest.json"),
                     ("ridership_reference", "manifest.json"), ("poi", "manifest.json"), ("input_package", "manifest.json"), ("scenarios", "manifest.json"), ("config", "manifest.json"), ("rules", "manifest.json")):
    ids[stage], dirs[stage] = pkg(stage, mname)

# ---------------- knowledge base manifest ----------------
kb_docs = sorted(KB_DIR.glob("KB_V2_*.md"))
def sections(p): return re.findall(r"^## ((?:DS|CM|IG|OI|GR|LG)-\d{2})", p.read_text(encoding="utf-8"), flags=re.M)
kb_manifest = {"kb_version": KB_VERSION, "issued_on": "2026-09-20", "language": "en",
               "documents": [{"file": p.name, "doc_id": p.name.split("_")[0] + "_" + p.name.split("_")[1] + "_" + p.name.split("_")[2], "title": p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip(),
                              "sections": sections(p), "sha256": sha_file(p)} for p in kb_docs],
               "agent_prompt": {"file": PROMPT.name, "version": PROMPT_VERSION, "sha256": sha_file(PROMPT)},
               "output_schema": {"file": "config/ai_output_schema_v2.json", "sha256": sha_file(SCHEMA)},
               "rule_pack": {"file": "config/rules_v2.json", "version": load(ROOT / "config/rules_v2.json")["version"], "sha256": sha_file(ROOT / "config/rules_v2.json")},
               "usage": "upload the six KB documents as the knowledge base of a NEW Coze bot/workflow (never the V1.1 one); paste the agent prompt as the system prompt; "
                        "the model cites 'KB_V2_0n §XX-nn (kb-v2.1)'; retrieval must be auto-called and citation restricted to these documents"}
dump(KB_DIR / "manifest.json", kb_manifest)

# ---------------- packages ----------------
sc = load(dirs["scenarios"] / "scenario_results.json"); sc_by = {s: {x["station_id"]: x for x in sc["scenarios"][s]["per_station"]} for s in SCEN}
sc_params = load(dirs["scenarios"] / "scenario_parameters.json")
cf = load(dirs["config"] / "station_config_results.json"); cf_by = {s: {x["station_id"]: x for x in cf["scenarios"][s]["stations"]} for s in SCEN}
cf_params = load(dirs["config"] / "config_parameters.json")
rules = load(dirs["rules"] / "rule_results.json"); rules_by = {b["station_id"]: b for b in rules["stations"]}
dem = load(dirs["demography"] / "station_demography_profile.json"); jobs = load(dirs["jobs"] / "station_jobs_profile.json")
svc = {s["station_id"]: s for s in load(dirs["service_baseline"] / "station_service_baseline.json")["stations"]}
rr_doc = load(dirs["ridership_reference"] / "station_ridership_reference.json")
sj = load(dirs["spatial_join"] / "station_zoning_profile.json")
ip_dir = dirs["input_package"]
station_ids = sorted(p.stem for p in (ip_dir / "stations").glob("MIA-MM-*.json"))


class Brief:
    def __init__(self, pid):
        self.pid, self.facts, self.n = pid, [], 0

    def add(self, group, label, value, unit=None, **meta):
        self.n += 1; fid = f"{self.pid}.F{self.n:03d}"
        self.facts.append({"fact_id": fid, "group": group, "label": label, "value": value, **({"unit": unit} if unit else {}), **{k: v for k, v in meta.items() if v is not None}})
        return fid


SRC = {"zoning": {"package": "spatial_join", "file": "station_zoning_evidence.json", "evidence_id_pattern": "<station>|<band>|<FID>"},
       "demography": {"package": "demography", "file": "demography_evidence.json", "evidence_id_pattern": "<station>|<band>|BG<block group>"},
       "jobs": {"package": "jobs", "file": "jobs_evidence.json", "evidence_id_pattern": "<station>|<band>|BLK<block>"},
       "poi": {"package": "poi", "file": "poi_evidence.json", "evidence_id_pattern": "<station>|<band>|<poi_id>"},
       "service": {"package": "service_baseline", "file": "station_service_baseline.json", "evidence_id_pattern": "station record"},
       "observed": {"package": "ridership_reference", "file": "station_ridership_reference.json", "evidence_id_pattern": "station record + monthly PDFs listed in evidence_source"},
       "scenarios": {"package": "scenarios", "file": "scenario_results.json", "evidence_id_pattern": "scenarios.<scenario>.per_station[<station>]"},
       "config": {"package": "config", "file": "station_config_results.json", "evidence_id_pattern": "scenarios.<scenario>.stations[<station>]"},
       "station_master": {"package": "input_package", "file": "stations/<station>.json", "evidence_id_pattern": "station record"}}
def src(layer, **extra): return {**SRC[layer], "package_id": ids[SRC[layer]["package"]], **extra}


def env_meta(e, layer, **extra):
    return {"provenance_class": e.get("provenance_class", "observed" if layer in ("zoning", "poi", "observed") else "derived"), "moe_90": e.get("moe_90"), "cv": e.get("cv"),
            "reliability": e.get("reliability_flag"), "value_status": e.get("value_status"), "source": src(layer), **extra}


def build(pid):
    s = load(ip_dir / "stations" / f"{pid}.json")["station"]; cum = s["cumulative_0_to_half_mile"]; b1 = s["bands"][0]; B = Brief(pid)
    ext = s.get("external_connections_on_map") or []
    B.add("identity", "GTFS stop ids mapped to this station", s.get("gtfs_stop_ids"), provenance_class="observed", source=src("station_master"))
    B.add("identity", "existing asset and study role", f"{s['existing_classification']['existing_asset']} → {s['existing_classification']['study_role']}", provenance_class="observed", source=src("station_master"))
    B.add("identity", "external connections on the official map", ext or "none", provenance_class="observed", source=src("station_master"), semantics="transfer inflow from these connections is excluded from the scenarios")
    B.add("identity", "zoning at the reference point", s["point_zoning_match"].get("matched_M21_ZONE") or s["point_zoning_match"]["status"], provenance_class="observed", source=src("zoning"))
    B.add("identity", "geometry role", "GTFS reference point; not an entrance, not a platform centroid", provenance_class="observed", source=src("station_master"))
    z = cum["zoning"]; top = sorted(z["by_Transect_D"].items(), key=lambda kv: -kv[1]["share_of_band"])[:3]
    B.add("bands_cum", "half-mile disc: land area", cum["display"]["land_area"]["acres"], "acres", provenance_class="derived", source=src("zoning"))
    B.add("bands_cum", "half-mile disc: zoned share of area", round(z["zoned_area_share"], 3), provenance_class="observed", source=src("zoning"), semantics="statutory zoning; not land use or demand (KB_V2_01 §DS-03)")
    B.add("bands_cum", "half-mile disc: largest zoning transects by share of area", [[k, round(v["share_of_band"], 3)] for k, v in top], provenance_class="observed", source=src("zoning"))
    d = cum["demography"]
    for iid, lab in (("D01", "half-mile disc: population (ACS 2020–2024 period estimate)"), ("D02", "half-mile disc: households"), ("D06", "half-mile disc: workers 16+")):
        e = d["counts"][iid]; B.add("bands_cum", lab, e.get("display_value"), e.get("unit"), **env_meta(e, "demography", period="2020-2024", semantics="period estimate apportioned by land share; not current population (KB_V2_01 §DS-04)"))
    for rid, lab in (("R03", "half-mile disc: zero-vehicle household share"), ("R01", "half-mile disc: public-transportation commute share (reference only)"), ("R02", "half-mile disc: worked-from-home share"),
                     ("R04", "half-mile disc: households below $35,000 share (project convention, not a demand indicator)"), ("R07", "half-mile disc: population 65+ share")):
        e = d["ratios"][rid]; meta = env_meta(e, "demography", provenance_class="derived")
        if meta.get("moe_90") is not None: meta["moe_90"] = round(meta["moe_90"] * 100, 1); meta["moe_unit"] = "percentage points"
        B.add("bands_cum", lab, e.get("display_percent"), "percent", **meta)
    mi = d["median_household_income"]
    B.add("bands_cum", "half-mile disc: median household income estimate (bracket interpolation; sensitivity range, not a confidence interval)", {"value_usd": mi.get("value"), "range_usd": mi.get("sensitivity_range"), "open_ended": mi.get("open_ended")}, provenance_class="derived", source=src("demography"))
    B.add("bands_cum", "half-mile disc: population density", d["density"]["R09_population_density"].get("value_persons_per_sq_mi"), "persons per sq mi", provenance_class="derived", source=src("demography"), semantics="never persons per hour (KB_V2_01 §DS-09)")
    j = cum["jobs"]
    B.add("bands_cum", "half-mile disc: all jobs located here (LODES 2023, C000 JT00)", j["jobs_by_workplace"]["JT00"]["C000"].get("display_value"), "jobs", provenance_class="derived", source=src("jobs"), semantics="jobs, not trips (KB_V2_01 §DS-05)")
    B.add("bands_cum", "half-mile disc: primary jobs located here (JT01)", j["jobs_by_workplace"]["JT01"]["C000"].get("display_value"), "jobs", provenance_class="derived", source=src("jobs"))
    B.add("bands_cum", "half-mile disc: primary jobs held by residents (≈ resident workers)", j["jobs_held_by_residents"]["JT01"]["C000"].get("display_value"), "jobs", provenance_class="derived", source=src("jobs"))
    B.add("bands_cum", "half-mile disc: jobs-to-resident-workers ratio (JT01)", round(j["ratios"]["J09_jobs_housing_ratio_primary"].get("value"), 2) if j["ratios"]["J09_jobs_housing_ratio_primary"].get("value") is not None else None, provenance_class="derived", source=src("jobs"), semantics="explains activity and direction; never hourly flows")
    B.add("bands_cum", "half-mile disc: jobs per acre of land", j["density"]["J08_jobs_per_acre_JT00"].get("value"), "jobs per acre", provenance_class="derived", source=src("jobs"))
    B.add("bands_b1", "inner band (0–1/8 mi): population", b1["demography"]["counts"]["D01"].get("display_value"), "persons", **env_meta(b1["demography"]["counts"]["D01"], "demography"))
    B.add("bands_b1", "inner band (0–1/8 mi): all jobs located here", b1["jobs"]["jobs_by_workplace"]["JT00"]["C000"].get("display_value"), "jobs", provenance_class="derived", source=src("jobs"))
    for c in CATS:
        B.add("facilities", f"half-mile disc: {c} facilities listed", cum["poi"]["counts"][c]["count"], "facilities", provenance_class="observed", value_status=cum["poi"]["counts"][c]["value_status"], source=src("poi"), semantics="listings; absence = not found in sources (KB_V2_01 §DS-08)")
        n = s["poi_nearest_by_category"][c]
        B.add("facilities", f"nearest {c} by straight line", ({"name": n.get("name"), "distance_ft": n.get("distance_ft"), "within_half_mile": n.get("within_half_mile")} if n.get("value_status") == "value" else "not found in the sources inside the study window"), provenance_class="observed", source=src("poi"), semantics="straight line from the reference point; not a walking distance")
    v = svc[pid]; am = v["periods"]["am_peak"]
    B.add("service", "current timetable: scheduled departures per hour, 7–9 a.m. (all routes)", am["departures_per_hour"], "departures per hour", provenance_class="derived", source=src("service"), semantics="scheduled, not operated; not capacity; not ridership (KB_V2_01 §DS-06)")
    B.add("service", "current timetable: implied AM-peak headway", am["implied_headway_min_all_routes"], "minutes", provenance_class="derived", source=src("service"))
    B.add("service", "current timetable: weekday scheduled departures and span", {"departures": v["scheduled_departures_weekday_total"], "first": v["first_departure"], "last": v["last_departure"]}, provenance_class="derived", source=src("service"))
    rb = s["miami_specific_inputs"]["ridership_baseline"]["value"]
    B.add("observed", "observed boardings of the current Metromover: average weekday, 10-month mean (2025-10 to 2026-07)", rb["avg_weekday_boardings_10_month_mean"], "boardings per weekday", provenance_class="observed", source=src("observed"), semantics="entries of the current system; not trips, not OD, not hourly, not demand for a new system; reference, never calibration (KB_V2_01 §DS-07)")
    B.add("observed", "observed boardings: share of system average weekday boardings", round(rb["share_of_system_avg_weekday"], 4), provenance_class="derived", source=src("observed"))
    B.add("observed", "observed boardings: report station name and mapping basis", {"report_station_name": rb["report_station_name"], "mapping_basis": rb["mapping_basis"], "mapping_confirmed_by_owner": rb["mapping_confirmed_by_owner"]}, provenance_class="observed", source=src("observed"))
    B.add("observed", "observed boardings: system average weekday, 10-month mean", rb["system_avg_weekday_boardings_10_month_mean"], "boardings per weekday", provenance_class="observed", source=src("observed"))
    od = s["od_link_potential"]
    B.add("links", "job-link potential, home side (Σ primary links × land share; not trips, non-exclusive)", round(od["home_side"]["JT01"]), "links", provenance_class="derived", source=src("jobs"), semantics=od["note"])
    B.add("links", "job-link potential, workplace side (Σ primary links × land share; not trips, non-exclusive)", round(od["work_side"]["JT01"]), "links", provenance_class="derived", source=src("jobs"))
    netd = dem["network"]["deduplicated"]["counts"]; netj = jobs["network"]["deduplicated"]["jobs_by_workplace"]["JT00"]["C000"]
    B.add("network", "network half-mile union: population (deduplicated)", netd["D01"].get("display_value"), "persons", provenance_class="derived", source=src("demography"))
    B.add("network", "network half-mile union: all jobs (deduplicated)", netj.get("display_value"), "jobs", provenance_class="derived", source=src("jobs"))
    B.add("network", "network half-mile union: area", sj["network"]["display"]["union"]["sq_mi"], "sq mi", provenance_class="derived", source=src("zoning"))
    for sname in SCEN:
        ch = sc["scenarios"][sname]; a = ch["assumption_values"]
        B.add(f"scenario_{sname}", f"{sname} scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption", {"A01": a["A01_attendance_rate"], "A02": a["A02_non_commute_trips_per_commute_trip"], "A03": a["A03_prt_adoption_share_of_all_mode_trips"]}, provenance_class="assumption", source=src("scenarios"), semantics="demonstration assumptions (KB_V2_02 §CM-02)")
        B.add(f"scenario_{sname}", f"{sname} scenario: network AM-peak PRT person trips", ch["totals"]["prt_am_peak_hour_trips"], "person trips per hour", provenance_class="derived", source=src("scenarios"), semantics="uncalibrated; internal links only; not a forecast (KB_V2_02 §CM-01)")
        x = sc_by[sname][pid]
        B.add(f"scenario_{sname}", f"{sname} scenario: this station's AM-peak boardings", x["am_peak_hour"]["boardings"], "person trips per hour", provenance_class="derived", source=src("scenarios"))
        B.add(f"scenario_{sname}", f"{sname} scenario: this station's AM-peak alightings", x["am_peak_hour"]["alightings"], "person trips per hour", provenance_class="derived", source=src("scenarios"))
        B.add(f"scenario_{sname}", f"{sname} scenario: this station's share of network AM boardings", round(x["share_of_network_am_boardings"], 4), provenance_class="derived", source=src("scenarios"))
        c = cf_by[sname][pid]; vt = c["vehicle_trips_am_peak_hour"]; eb = c["empty_vehicle_balance_per_hour"]; b = c["berths"]; m = c["module"]
        B.add(f"config_{sname}", f"{sname} scenario: vehicle departures / arrivals per hour (person trips ÷ C01)", {"departures": vt["departures"], "arrivals": vt["arrivals"]}, "vehicle trips per hour", provenance_class="derived", source=src("config"))
        B.add(f"config_{sname}", f"{sname} scenario: empty vehicles required in / leaving per hour", {"required_in": eb["empty_vehicles_required_in"], "leaving": eb["empty_vehicles_leaving"]}, "vehicles per hour", provenance_class="derived", source=src("config"), semantics="no staging berths drawn (C07)")
        B.add(f"config_{sname}", f"{sname} scenario: berth cycles → design cycles (× C04) → berths required", {"berth_cycles": b["berth_cycles_per_hour"], "design_cycles": b["design_cycles_per_hour_with_within_hour_peaking"], "usable_cycles_per_berth_hour": b["usable_cycles_per_berth_hour"], "berths_required": b["berths_required"]}, provenance_class="derived", source=src("config"), semantics="KB_V2_02 §CM-04")
        B.add(f"config_{sname}", f"{sname} scenario: platform module and footprint", {"module": m["module_id"], "berths_provided": m["berths_provided"], "footprint_ft2": m["footprint_ft2"], "fits_single_module": m["fits_single_module"]}, provenance_class="observed", source=src("config"), semantics="module from owner drawings (design specification); berth counts await confirmation (KB_V2_04 §OI-02)")
        B.add(f"config_{sname}", f"{sname} scenario: site fit status", c["site_fit"]["status"], provenance_class="assumption", source=src("config"), semantics="C06: constructible space not acquired (KB_V2_04 §OI-01)")
        net = cf["scenarios"][sname]["network"]
        B.add(f"config_{sname}", f"{sname} scenario: network vehicle trips ÷ one lane's throughput at minimum headway", round(net["network_vehicle_trips_over_lane_throughput"], 3), provenance_class="derived", source=src("config"), semantics="network-level ratio only (KB_V2_02 §CM-06)")
    ops = cf_params["operations_assumptions"]
    for k in ("C01_average_party_size_pax_per_vehicle_trip", "C02_berth_cycle_s", "C03_berth_utilization_max", "C04_within_hour_peaking_factor", "C05_min_guideway_headway_s"):
        o = ops[k]; B.add("assumptions", f"{k}: {o['statement']}", o["value"], o.get("unit"), provenance_class="assumption", source=src("config"))
    rb_ = rules_by[pid]
    return {"brief_id": pid, "station_id": pid, "name": s["name"], "generated_on": "2026-09-18", "kit_version": KIT_VERSION, "kb_version": KB_VERSION, "prompt_version": PROMPT_VERSION,
            "rule_pack_version": rules["rule_pack_version"], "packages": ids,
            "instructions_for_the_model": "Use only these facts and the knowledge base kb-v2.1. Cite fact ids for site facts, rule result ids for normative statements, KB sections for guidance. "
                                          "Do not write numbers that are not here. Answer as the JSON object of config/ai_output_schema_v2.json.",
            "facts": B.facts,
            "rule_results": {"station": [{k: r[k] for k in ("rule_result_id", "rule_id", "rule_name", "scenario", "status", "basis", "message")} for r in rb_["results"]],
                             "network": [{k: r[k] for k in ("rule_result_id", "rule_id", "rule_name", "scenario", "status", "basis", "message")} for r in rules["network"]["results"]],
                             "station_summary": rb_["summary"], "severity_semantics": rules["severity_semantics"]},
            "not_available": ["origin-destination and hourly ridership (no calibration; peak-hour share is a census proxy)", "station entrances, crossings, vertical circulation (bands are straight-line)",
                              "constructible platform space (site fit assumed, C06)", "supplier vehicle operating data (generic assumptions C01–C05)", "network walk model (not built)",
                              "role classification (to be proposed here, confirmed by people)", "engineering validation (not performed)"],
            "forbidden": ["numbers not in this brief", "external standards or codes", "density or facility counts as passengers per hour", "scaling scenarios to observed boardings",
                          "zoning or income as exclusion", "averaging medians", "job links as trips", "calling assumptions observations", "calling results designs, forecasts or proofs"]}


def render_md(b):
    L = [f"# Station brief · {b['name']} ({b['station_id']}) · kit {b['kit_version']} · KB {b['kb_version']} · rules {b['rule_pack_version']}", "",
         b["instructions_for_the_model"], "", "## Facts (cite by fact_id)", "", "| fact_id | label | value | unit | provenance | reliability / MOE |", "|---|---|---|---|---|---|"]
    fmt = lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else ("" if v is None else str(v))
    for f in b["facts"]:
        rel = " / ".join(x for x in ((f"{f['reliability']}" if f.get("reliability") else ""), (f"±{f['moe_90']}" if f.get("moe_90") is not None else "")) if x)
        L.append(f"| {f['fact_id']} | {f['label']} | {fmt(f['value'])} | {f.get('unit', '')} | {f.get('provenance_class', '')} | {rel} |")
    L += ["", "## Rule results (cite by rule_result_id, rule pack " + b["rule_pack_version"] + ")", "", "| rule_result_id | status | basis | message |", "|---|---|---|---|"]
    for r in b["rule_results"]["station"] + b["rule_results"]["network"]: L.append(f"| {r['rule_result_id']} | {r['status']} | {r['basis']} | {r['message']} |")
    L += ["", "Severity: " + "; ".join(f"{k} = {v}" for k, v in b["rule_results"]["severity_semantics"].items()), "", "## Not available", ""] + [f"- {x}" for x in b["not_available"]]
    L += ["", "## Forbidden", ""] + [f"- {x}" for x in b["forbidden"]] + [""]
    return "\n".join(L)


(OUT / "briefs").mkdir(parents=True, exist_ok=True)
KB_SECTIONS = [f"{d['doc_id']} §{s}" for d in kb_manifest["documents"] for s in d["sections"]]
briefs = []
for pid in station_ids:
    b = build(pid); dump(OUT / "briefs" / f"{pid}.json", b); (OUT / "briefs" / f"{pid}.md").write_text(render_md(b), encoding="utf-8")
    # compact variant = the Start-node input of the Coze workflow coze/v2 (no per-fact source pointers; the KB section list lets the output gate validate KB references)
    compact = {**{k: v for k, v in b.items() if k not in ("facts", "packages")}, "facts": [{k: v for k, v in f.items() if k != "source"} for f in b["facts"]], "kb_sections": KB_SECTIONS}
    (OUT / "briefs" / f"{pid}.coze.json").write_text(json.dumps(compact, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    briefs.append({"station_id": pid, "name": b["name"], "facts": len(b["facts"]), "json": f"ai/miami/briefs/{pid}.json", "md": f"ai/miami/briefs/{pid}.md", "coze_json": f"ai/miami/briefs/{pid}.coze.json",
                   "sha256_json": sha_file(OUT / "briefs" / f"{pid}.json"), "sha256_coze_json": sha_file(OUT / "briefs" / f"{pid}.coze.json")})
kit = {"kit_version": KIT_VERSION, "generated_on": "2026-09-18", "kb_version": KB_VERSION, "prompt_version": PROMPT_VERSION, "rule_pack_version": rules["rule_pack_version"],
       "packages": ids, "kb_manifest_sha256": sha_file(KB_DIR / "manifest.json"), "agent_prompt_sha256": sha_file(PROMPT), "output_schema_sha256": sha_file(SCHEMA),
       "briefs": briefs, "runs_dir": "ai/miami/runs/<station_id>/<YYYYMMDD-HHMM>.json", "checker": "scripts/check_miami_ai_output.py",
       "representative_stations_first": ["MIA-MM-09", "MIA-MM-12", "MIA-MM-21", "MIA-MM-01", "MIA-MM-02"],
       "ai_status": "NOT_RUN: no model output exists yet; briefs and knowledge base prepared"}
dump(OUT / "kit_manifest.json", kit)
print(f"kit {KIT_VERSION}: briefs={len(briefs)} facts_per_station={briefs[0]['facts']} kb_docs={len(kb_docs)} rules={rules['rule_pack_version']} packages={ids}")
