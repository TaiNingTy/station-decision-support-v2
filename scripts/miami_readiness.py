#!/usr/bin/env python3
"""Miami readiness aggregator — the ONLY writer of data/miami/2026-09-14/gis_data_readiness.json (R2).

Generic over a STAGE REGISTRY (V2 step 1, 2026-09-15). Every stage keeps immutable products plus its own manifest;
this script only READS them and derives the current status view. It never modifies a stage's outputs or manifests,
and readiness itself is not listed in any stage manifest (it carries its own lineage block instead).

Stage kinds
  manifest_only  flat outputs listed in build_manifest.json (station_master). Fresh while every recorded DATA input
                 still has its recorded sha256.
  package        <stage>_current.json pointer -> <stage>/pkg-<id>/ (whole package verified against its manifest and the
                 pointer). Fresh while every `consumed_inputs` file still matches its recorded sha256, every
                 `consumed_packages` entry still names the CURRENT package id of that stage, and every consumed stage is
                 itself DONE (staleness propagates down the build order). The spatial_join manifest schema 2.0
                 (`upstream` block) is read through a compatibility mapping until that stage republishes with the
                 generic blocks.

Status per stage: NOT_RUN | CORRUPT_PACKAGE | STALE | DONE.
Code changes are NOT staleness: a package records the script sha256 that produced it (provenance). If the current
script differs, `code_matches_current` is false and a rebuild is suggested, but the published results remain
consistent with their recorded inputs.

Readiness flags (field contract §10; booleans plus lists, never strings):
  ready_for_ai_interpretation   every stage flagged required_for_ai is DONE
  ai_missing_optional           optional stages (poi, walk_model) that are not DONE
  config_inputs_complete        scenario results + the three engineering/service inputs all have a value
  config_inputs_all_observed    ...and none of them is assumption-backed
  config_missing_inputs / config_assumption_backed_inputs
The input_package manifest carries a `config_inputs` summary {name: {acquisition_status, value_status,
provenance_class}}; the scenarios manifest carries `assumption_parameter_ids`.

Deterministic (no timestamps). Written atomically (temp file + one os.replace).
    python3 scripts/miami_readiness.py             # (re)aggregate and print
    python3 scripts/miami_readiness.py --check     # exit 1 unless the spatial join is DONE and verified
    python3 scripts/miami_readiness.py --check-ai  # exit 1 unless ready_for_ai_interpretation is true
"""
import hashlib, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/miami/2026-09-14"
RAW = ROOT / "raw/miami/2026-09-14"
READINESS = DATA / "gis_data_readiness.json"
MANIFEST_NAME = "spatial_join_manifest.json"   # legacy manifest name of the spatial_join stage
SCHEMA = "miami-gis-readiness/2.2"

# Registry order = build order; dependencies only point backwards, so one pass propagates staleness.
STAGES = [
    {"stage": "station_master", "kind": "manifest_only", "manifest": "build_manifest.json", "required_for_ai": True},
    {"stage": "spatial_join", "kind": "package", "pointer": "spatial_join_current.json", "manifest_name": MANIFEST_NAME, "required_for_ai": True},
    {"stage": "demography", "kind": "package", "pointer": "demography_current.json", "manifest_name": "manifest.json", "required_for_ai": True},
    {"stage": "jobs", "kind": "package", "pointer": "jobs_current.json", "manifest_name": "manifest.json", "required_for_ai": True},
    {"stage": "service_baseline", "kind": "package", "pointer": "service_baseline_current.json", "manifest_name": "manifest.json"},   # config input (GTFS), not required for AI
    {"stage": "ridership_reference", "kind": "package", "pointer": "ridership_reference_current.json", "manifest_name": "manifest.json"},   # observed DTPW boardings, reference only
    {"stage": "poi", "kind": "package", "pointer": "poi_current.json", "manifest_name": "manifest.json", "optional_for_ai": True},
    {"stage": "walk_model", "kind": "package", "pointer": "walk_model_current.json", "manifest_name": "manifest.json", "optional_for_ai": True},
    {"stage": "input_package", "kind": "package", "pointer": "input_package_current.json", "manifest_name": "manifest.json", "required_for_ai": True},
    {"stage": "scenarios", "kind": "package", "pointer": "scenarios_current.json", "manifest_name": "manifest.json"},
    {"stage": "config", "kind": "package", "pointer": "config_current.json", "manifest_name": "manifest.json"},   # step 6: PRT berths/modules per scenario
    {"stage": "rules", "kind": "package", "pointer": "rules_current.json", "manifest_name": "manifest.json"},     # step 9a: versioned rule results (citable rule_result_id) for the AI layer
]
CONFIG_INPUT_FIELDS = ["platform_constructible_space", "vehicle_parameters", "service_baseline"]
# Compatibility mapping for the spatial_join manifest schema 2.0 (`upstream` block) -> ROOT-relative files.
LEGACY_CONSUMED = {"station_master_sha256": "data/miami/2026-09-14/station_master.geojson",
                   "study_window_sha256": "data/miami/2026-09-14/study_window.geojson",
                   "zoning_raw_sha256": "raw/miami/2026-09-14/zoning_study_window.geojson"}
FRESHNESS_RULE = ("a package stage is DONE only if its whole package verifies, every consumed input file still has the recorded "
                  "sha256, every consumed package is still the current package of its stage, and every consumed stage is DONE; "
                  "a manifest_only stage is DONE only if its outputs verify and its recorded data inputs are unchanged")
CODE_RULE = "code changes never mark a stage STALE; they set code_matches_current=false (rebuild suggested, provenance intact)"


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))


def safe_load(p):
    """(obj, None) or (None, error). A corrupt file degrades ONE stage to CORRUPT_PACKAGE; it must never crash the aggregator."""
    try: return load(p), None
    except Exception as e: return None, f"{Path(p).name} is not valid JSON: {type(e).__name__}: {str(e)[:120]}"


def _cur(rel):
    p = ROOT / rel; return sha_file(p) if p.exists() else None


def dump_atomic(p, obj):
    p = Path(p); tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)  # single-file atomic switch


def verify_package(pkg_dir, manifest_name=MANIFEST_NAME):
    """Whole-package check: manifest present, every listed output present with the recorded sha256.
    Returns (ok, manifest | None, problems)."""
    pkg_dir = Path(pkg_dir); mpath = pkg_dir / manifest_name
    if not mpath.exists(): return False, None, [f"missing {manifest_name}"]
    m, err = safe_load(mpath)
    if err or not isinstance(m, dict): return False, None, [err or f"{manifest_name} is not a JSON object"]
    problems = []
    if not m.get("outputs"): problems.append("manifest lists no outputs")
    for o in m.get("outputs", []):
        f = pkg_dir / o["file"]
        if not f.exists(): problems.append(f"missing {o['file']}")
        elif sha_file(f) != o["sha256"]: problems.append(f"sha256 mismatch: {o['file']}")
    return not problems, m, problems


def consumed_inputs_of(m):
    """[(name, ROOT-relative path, recorded sha256)] — generic block, else the legacy `upstream` mapping."""
    if "consumed_inputs" in m: return [(c["name"], c["path"], c["sha256"]) for c in m["consumed_inputs"]]
    up = m.get("upstream", {})
    return [(k, rel, up[k]) for k, rel in LEGACY_CONSUMED.items() if k in up]


def code_entries_of(m):
    if "code" in m: return [(c["path"], c["sha256"]) for c in m["code"]]
    s = m.get("script"); return [(s["path"], s["sha256"])] if s else []


def eval_manifest_only(spec):
    mpath = DATA / spec["manifest"]
    if not mpath.exists(): return {"status": "NOT_RUN", "reason": f"no {spec['manifest']}", "ready_for_downstream": False}
    m, err = safe_load(mpath)
    if err or not isinstance(m, dict):
        return {"status": "CORRUPT_PACKAGE", "manifest": spec["manifest"], "problems": [err or "manifest is not a JSON object"], "ready_for_downstream": False}
    problems = []
    for o in m.get("outputs", []):
        f = DATA / o["file"]
        if not f.exists(): problems.append(f"missing {o['file']}")
        elif sha_file(f) != o["sha256"]: problems.append(f"sha256 mismatch: {o['file']}")
    if problems: return {"status": "CORRUPT_PACKAGE", "manifest": spec["manifest"], "problems": problems, "ready_for_downstream": False}
    inputs = m.get("inputs", [])
    data_changed = [i["path"] for i in inputs if not i["path"].startswith("scripts/") and _cur(i["path"]) != i["sha256"]]
    code_ok = all(_cur(i["path"]) == i["sha256"] for i in inputs if i["path"].startswith("scripts/"))
    st = "DONE" if not data_changed else "STALE"
    return {"status": st, "manifest": spec["manifest"], "manifest_sha256": sha_file(mpath), "built_on": m.get("built_on"),
            "ready_for_downstream": st == "DONE", "inputs_changed": data_changed,
            "freshness": "FRESH" if st == "DONE" else "STALE_recorded_inputs_changed_rerun_stage",
            "code_matches_current": code_ok}


def eval_package(spec, current_ids, stages_so_far):
    ptr_path = DATA / spec["pointer"]
    if not ptr_path.exists(): return {"status": "NOT_RUN", "reason": f"no {spec['pointer']} pointer", "ready_for_downstream": False}
    ptr, err = safe_load(ptr_path)
    if err or not isinstance(ptr, dict) or not ptr.get("package_dir"):
        return {"status": "CORRUPT_PACKAGE", "pointer": spec["pointer"], "ready_for_downstream": False,
                "problems": [err or f"{spec['pointer']} has no package_dir"], "action": "rerun the stage; its publish rewrites the pointer atomically"}
    pkg = DATA / ptr["package_dir"]; mname = spec["manifest_name"]
    block = {"pointer": spec["pointer"], "package_dir": ptr["package_dir"], "package_id": ptr.get("package_id"),
             "stage_manifest": f"{ptr['package_dir']}/{mname}"}
    if not pkg.is_dir():
        return {"status": "CORRUPT_PACKAGE", **block, "ready_for_downstream": False, "problems": [f"package dir missing: {ptr['package_dir']}"]}
    ok, m, problems = verify_package(pkg, mname)
    if m is not None and sha_file(pkg / mname) != ptr.get("manifest_sha256"):
        problems.append("package manifest sha256 != pointer.manifest_sha256")
    if problems or m is None:
        return {"status": "CORRUPT_PACKAGE", **block, "ready_for_downstream": False, "problems": problems,
                "action": "do not consume; rerun the stage (it republishes a whole package atomically)"}
    consumed = consumed_inputs_of(m)
    changed_inputs = [name for name, rel, rec in consumed if _cur(rel) != rec]
    pkgs = m.get("consumed_packages", [])
    changed_pkgs = [c["stage"] for c in pkgs if current_ids.get(c["stage"]) != c.get("package_id")]
    not_done = [c["stage"] for c in pkgs if stages_so_far.get(c["stage"], {}).get("status") != "DONE"]
    # an optional layer that was absent when this package was built and is DONE now => rebuild to include it
    newly = [s for s in m.get("optional_layers_absent_at_build", []) if stages_so_far.get(s, {}).get("status") == "DONE"]
    fresh = not changed_inputs and not changed_pkgs and not not_done and not newly
    ready = bool(fresh and m.get("ready_for_downstream"))
    code_ok = all(_cur(rel) == rec for rel, rec in code_entries_of(m))
    if fresh: freshness = "FRESH"
    elif newly and not (changed_inputs or changed_pkgs or not_done): freshness = "STALE_optional_layer_now_available_rebuild_stage_to_include_it"
    else: freshness = "STALE_consumed_inputs_or_packages_changed_rerun_stage"
    block.update({"built_on": m.get("built_on"), "build_status": m.get("build_status"),
                  "geometry_validation_status": m.get("geometry_validation_status"), "ready_for_downstream": ready,
                  "freshness": freshness,
                  "consumed_inputs_changed": changed_inputs, "consumed_packages_changed": changed_pkgs,
                  "consumed_stages_not_done": not_done, "optional_layers_now_available": newly,
                  "optional_layers_absent_at_build": m.get("optional_layers_absent_at_build", []),
                  "consumed_inputs_recorded_sha256": {name: rec for name, rel, rec in consumed},
                  "consumed_packages_recorded": pkgs, "manifest_sha256": sha_file(pkg / mname),
                  "code_matches_current": code_ok, "method": m.get("method_summary")})
    if "upstream" in m:   # spatial_join schema 2.0 compatibility fields
        bm = DATA / "build_manifest.json"
        block.update({"upstream_manifest_sha256_matches_current": bool(bm.exists() and sha_file(bm) == m["upstream"].get("manifest_sha256")),
                      "upstream_manifest_note": "informational only: freshness is decided by the consumed inputs, not by the upstream manifest hash",
                      "profile_file": f"{ptr['package_dir']}/station_zoning_profile.json"})
    for k in ("config_inputs", "assumption_parameter_ids"):
        if k in m: block[k] = m[k]
    return {"status": "DONE" if ready else "STALE", **block}


def flags(stages):
    req = [s["stage"] for s in STAGES if s.get("required_for_ai")]
    opt = [s["stage"] for s in STAGES if s.get("optional_for_ai")]
    req_not_done = [s for s in req if stages[s]["status"] != "DONE"]
    ip, sc = stages["input_package"], stages["scenarios"]
    cfg = ip.get("config_inputs", {}) if ip["status"] == "DONE" else {}
    missing, assumed = [], []
    for name in CONFIG_INPUT_FIELDS:
        c = cfg.get(name) or {}
        if c.get("value_status") != "value": missing.append(name)
        elif c.get("provenance_class") == "assumption" or c.get("acquisition_status") == "assumed": assumed.append(name)
    if sc["status"] != "DONE": missing.append("scenario_results")
    elif sc.get("assumption_parameter_ids"): assumed.append("scenario_results")
    complete = not missing
    return {"ready_for_ai_interpretation": not req_not_done, "ai_required_stages": req, "ai_required_not_done": req_not_done,
            "ai_missing_optional": [s for s in opt if stages[s]["status"] != "DONE"],
            "config_inputs_complete": complete, "config_inputs_all_observed": bool(complete and not assumed),
            "config_missing_inputs": missing, "config_assumption_backed_inputs": assumed,
            "definitions": {"ready_for_ai_interpretation": "every required stage DONE (station_master, spatial_join, demography, jobs, input_package)",
                            "config_inputs_complete": "scenario results and the three engineering/service inputs all have a value, observed or assumed",
                            "config_inputs_all_observed": "complete AND no input is assumption-backed; 'calculated with assumptions' = complete true, all_observed false",
                            "source": "input_package manifest -> config_inputs summary; scenarios manifest -> assumption_parameter_ids"}}


def derive_layers(stages, inv, ip_cfg):
    """One current status per data layer, derived ONLY from the stage registry (plus the input-package config summary).
    The legacy inventory keys (demography, jobs_and_commute, pois, ...) live here so a reader never meets two answers."""
    st = lambda s: stages.get(s, {}).get("status", "NOT_RUN"); pk = lambda s: stages.get(s, {}).get("package_dir")
    cfg = ip_cfg or {}
    return {
        "zoning": {"status": st("spatial_join"), "stage": "spatial_join", "package_dir": pk("spatial_join"), "meaning": "statutory zoning joined to the station bands (not land use, not demand)"},
        "demography": {"status": st("demography"), "stage": "demography", "package_dir": pk("demography"),
                       "meaning": "ACS 2020-2024 block-group period estimates apportioned to the bands; not current population"},
        "jobs_and_commute": {"status": st("jobs"), "stage": "jobs", "package_dir": pk("jobs"), "meaning": "LODES 8 (2023) job counts and block-level OD links; not trips, not ridership"},
        "service_baseline": {"status": st("service_baseline"), "stage": "service_baseline", "package_dir": pk("service_baseline"), "meaning": "GTFS weekday timetable per station; scheduled, not operated"},
        "pois": {"status": st("poi"), "stage": "poi", "package_dir": pk("poi"), "optional_for_ai": True},
        "walk_network": {"status": st("walk_model"), "stage": "walk_model", "package_dir": pk("walk_model"), "optional_for_ai": True,
                         "meaning": "network_walk_model when built; never a validated walk catchment by itself"},
        "input_package": {"status": st("input_package"), "stage": "input_package", "package_dir": pk("input_package")},
        "demand": {"observed_ridership_status": ("ACQUIRED_station_level_daily_boardings" if st("ridership_reference") == "DONE" else st("ridership_reference")),
                   "observed_ridership_stage": "ridership_reference", "observed_ridership_package_dir": pk("ridership_reference"),
                   "scenario_model_status": st("scenarios"), "stage": "scenarios", "package_dir": pk("scenarios"),
                   "meaning": "observed = DTPW published boardings of the current Metromover (reference only, not calibration); scenarios = low/medium/high uncalibrated "
                              "model outputs for internal links; GTFS counts are not ridership"},
        "configuration": {"status": st("config"), "stage": "config", "package_dir": pk("config"),
                          "meaning": "berths, platform module and footprint per station per scenario under PRT semantics; assumption-backed, not a design"},
        "rules": {"status": st("rules"), "stage": "rules", "package_dir": pk("rules"),
                  "meaning": "deterministic results of the versioned rule pack (arithmetic identities, project conventions, data-quality and scope flags) with citable ids; not legal or agency standards"},
        "engineering": {"platform_constructible_space": cfg.get("platform_constructible_space", {}).get("acquisition_status", "not_acquired"),
                        "vehicle_parameters": cfg.get("vehicle_parameters", {}).get("acquisition_status", "not_approved"),
                        "source": "input_package manifest config_inputs"},
        "served_hubs": {"status": (inv.get("served_hubs") or {}).get("status", "UNKNOWN"), "note": "map connection candidates from the station_master inventory; hub inflow is not modeled in the Miami case"},
        "roads_and_guideways": {"status": "NOT_ACQUIRED", "note": "road/guideway roles are a not-acquired input of the input package"},
    }


def aggregate(write=True):
    bm_path = DATA / "build_manifest.json"
    if not bm_path.exists():
        raise SystemExit("HALT: build_manifest.json missing — run scripts/build_miami_station_master.py first")
    bm, bm_err = safe_load(bm_path); bm = bm if isinstance(bm, dict) else {}
    inv_path = DATA / "gis_inventory.json"
    recorded = {o["file"]: o["sha256"] for o in bm.get("outputs", [])}.get("gis_inventory.json")
    inv, inv_err = safe_load(inv_path) if inv_path.exists() else (None, "gis_inventory.json missing")
    inventory_verified = bool(inv and not inv_err and recorded and sha_file(inv_path) == recorded)
    inv = inv if isinstance(inv, dict) else {}
    pointers, pointer_errors = {}, {}
    for s in STAGES:
        if s["kind"] != "package": continue
        p = DATA / s["pointer"]
        if p.exists():
            obj, err = safe_load(p); pointers[s["stage"]] = obj if isinstance(obj, dict) else None
            if err: pointer_errors[s["stage"]] = err
        else: pointers[s["stage"]] = None
    current_ids = {k: (v or {}).get("package_id") for k, v in pointers.items()}
    stages = {}
    for s in STAGES:
        block = eval_manifest_only(s) if s["kind"] == "manifest_only" else eval_package(s, current_ids, stages)
        block["kind"] = s["kind"]
        block["role_for_ai"] = "required" if s.get("required_for_ai") else ("optional" if s.get("optional_for_ai") else "not_required")
        stages[s["stage"]] = block
    fl = flags(stages)
    sj = stages["spatial_join"]
    readiness = {
        "schema_version": SCHEMA, "snapshot_date": inv.get("snapshot_date"),
        "role": "DERIVED status view. Written only by scripts/miami_readiness.py; not a stage output; not hash-listed in any "
                "stage manifest; regenerate it from the stage manifests at any time. Current status: `stages` (per pipeline stage) and "
                "`layers` (per data layer). `upstream_inventory` is a dated snapshot and carries no current status.",
        "lineage": {"build_manifest_sha256": sha_file(bm_path), "build_manifest_error": bm_err,
                    "gis_inventory_sha256": (sha_file(inv_path) if inv_path.exists() else None), "inventory_verified_against_build_manifest": inventory_verified,
                    "spatial_join_pointer": pointers.get("spatial_join"),
                    "spatial_join_manifest_sha256": (pointers.get("spatial_join") or {}).get("manifest_sha256"),
                    "pointers": pointers, "pointer_errors": pointer_errors,
                    "stage_manifests_sha256": {k: v.get("manifest_sha256") for k, v in stages.items()}},
        "freshness_rule": FRESHNESS_RULE, "code_rule": CODE_RULE,
        "stages": stages, "readiness_flags": fl,
        "layers": derive_layers(stages, inv, stages["input_package"].get("config_inputs")),
        "zoning": {**(inv.get("zoning") or {}), "station_spatial_join_status": sj["status"], "station_spatial_join": sj},
        "upstream_inventory": {"_note": "static snapshot written by the station_master stage on its build date; statuses inside (e.g. NOT_DOWNLOADED) describe "
                                        "THAT moment and are superseded by `layers` and `stages` — never read a current status from here",
                               "verified_against_build_manifest": inventory_verified, "error": inv_err,
                               **{k: v for k, v in inv.items() if k not in ("schema_version", "snapshot_date", "role", "zoning")}},
    }
    if write: dump_atomic(READINESS, readiness)
    return readiness


if __name__ == "__main__":
    r = aggregate(); st = r["stages"]; fl = r["readiness_flags"]; sj = st["spatial_join"]
    print("stages: " + "  ".join(f"{k}={v['status']}" for k, v in st.items()))
    print(f"flags: ai={fl['ready_for_ai_interpretation']} required_not_done={fl['ai_required_not_done']} missing_optional={fl['ai_missing_optional']} "
          f"config_complete={fl['config_inputs_complete']} all_observed={fl['config_inputs_all_observed']} "
          f"missing={fl['config_missing_inputs']} assumed={fl['config_assumption_backed_inputs']}")
    print(f"spatial_join: ready_for_downstream={sj.get('ready_for_downstream')} changed={sj.get('consumed_inputs_changed')} "
          f"problems={sj.get('problems')} package={sj.get('package_dir')}")
    if "--check" in sys.argv and sj["status"] != "DONE": sys.exit(1)
    if "--check-ai" in sys.argv and not fl["ready_for_ai_interpretation"]: sys.exit(1)
