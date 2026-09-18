#!/usr/bin/env python3
"""Fault-injection regression for the Miami pipeline. Runs ONLY in temporary copies; never modifies this tree.

A "baseline" copy is built first with the ordered rebuild; every other scenario starts from a copy of that baseline.

  baseline_full_rebuild     ordered rebuild passes; readiness DONE; every manifest verifies; readiness listed nowhere;
                            (if this tree already has a published package) the package is byte-identical to it
  unchanged_rerun           second rebuild: no new package, every file under data/ byte-identical (determinism)
  station_change            registry name edit  -> upstream only -> STALE [station_master] -> downstream -> DONE
  window_change             bbox edit           -> upstream only -> STALE [study_window]   -> downstream -> DONE   (R1)
  zoning_change             FID 64 attribute edit in GeoJSON + Esri JSON -> STALE [zoning_raw] -> downstream -> DONE (R1)
  publish_failure_rename    config change + injected OSError at the package-dir rename: nothing published          (R3)
  publish_failure_pointer   config change + injected OSError at the pointer switch: package complete, pointer old,
                            a plain rerun recovers                                                                 (R3)
  validation_failure        SPATIAL_JOIN_FORCE_FAIL=1: exit 1, nothing published                                   (F1)
  lock_mismatch             edited lock file: exit 1, nothing published                                            (U3)
  corrupt_package_detected  one byte appended to a published output -> CORRUPT_PACKAGE, --check exits 1; rerun
                            quarantines the corrupt dir and republishes
  readiness_single_writer   readiness not in any manifest; lineage matches; aggregator rerun byte-identical;
                            no stage script writes readiness                                                       (R2)
  --- step 1 (2026-09-15): generic stage registry + readiness flags ---
  readiness_flags_baseline  8 stages listed in build order; unbuilt layers NOT_RUN; ai flag false with the three
                            required layers listed; optional layers listed; config incomplete with 4 missing; booleans
  future_layers_fixtures    fixture packages for demography / jobs / input_package -> ai flag true although poi and
                            walk_model are missing; a poi fixture removes itself from the optional-missing list
  assumption_backed_inputs  assumed engineering inputs + scenarios with assumption parameters -> complete true,
                            all_observed false, the assumed inputs listed; an all-observed variant -> both true
  stale_propagation         spatial join republished -> its consumers STALE (reason: spatial_join), scenarios STALE by
                            propagation, ai flag false again
  raw_change_station_master registry edited without rebuild -> station_master STALE naming the file, spatial_join still
                            DONE (its data unchanged); rebuild upstream -> spatial_join STALE; rebuild -> both DONE
  code_change_informational comment-only script edits -> stages stay DONE, code_matches_current false; rebuild -> true
  --- step 3 (2026-09-15): demography + jobs layers ---
  demography_jobs_layers    both layers DONE after the ordered rebuild; validation PASS; packages byte-identical to the
                            ones published in this tree (cross-copy determinism); LODES WAC = OD identity holds
  raw_change_layers_stale   one raw ACS file edited without re-acquisition -> demography STALE naming the file, jobs
                            STALE by propagation, ai flag false; a demography rebuild HALTs on the raw hash gate
  --- step 4 (2026-09-15): station input package ---
  input_package_build       input_package DONE, pins equal the current pointers of the four layers, 21 station files,
                            ai flag TRUE, config_inputs summary present, byte-identical to the published package
  --- step 5 (2026-09-15): service baseline + scenarios ---
  service_baseline_and_scenarios  both DONE; trips conserved in every scenario; low <= medium <= high; low adoption bounded by
                            the observed transit share; assumption ids in the manifest; readiness lists scenario_results
                            as assumption-backed and only platform space + vehicle parameters as missing; the scenario
                            base is coverage-weighted (partially covered blocks count for their covered fraction)
  --- review 3 (2026-09-17) ---
  optional_layer_added_marks_input_package_stale  a poi package appears after the input package was built -> input_package
                            STALE naming poi, scenarios STALE by propagation; rebuilding the input package pins poi
  corrupt_optional_layer_isolated  a corrupt manifest or pointer JSON in an optional layer -> that layer CORRUPT_PACKAGE, the
                            aggregator still exits 0 and every other stage keeps its status
  --- step 6 (2026-09-17): PRT configuration ---
  config_stage              config DONE; vehicle trips conserved; berths monotonic across scenarios; every station gets a module
                            that covers its berth requirement; 7 assumption ids; readiness: config inputs complete = true,
                            all observed = false, three assumption-backed inputs
  --- step 7a (2026-09-17): observed ridership reference ---
  ridership_reference_stage DTPW boardings by station DONE (21 stations every month, three renamed stations flagged); the input
                            package carries ridership_baseline as acquired/observed; the scenarios carry an observed_reference
                            block (scale ratios below one, rank correlation of station shares in range)

    python3 scripts/test_miami_pipeline_regression.py [--out results.json] [--base DIR] [--keep]
Exit code 1 if any check fails.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from miami_readiness import verify_package  # pure function on a path

DATA_REL, RAW_REL = Path("data/miami/2026-09-14"), Path("raw/miami/2026-09-14")
PY = sys.executable
IGNORE = shutil.ignore_patterns(".venv-gis", "__pycache__", ".DS_Store", "reviews", "evidence", "failed")
INJECT = r'''import os, sys, runpy
mode, script = sys.argv[1], sys.argv[2]
_rename, _replace = os.rename, os.replace
def rename(a, b):
    if mode == "rename" and "/pkg-" in str(b).replace("\\", "/"): raise OSError("injected failure: package dir rename")
    return _rename(a, b)
def replace(a, b):
    if mode == "pointer" and str(b).endswith("spatial_join_current.json"): raise OSError("injected failure: pointer switch")
    return _replace(a, b)
os.rename, os.replace = rename, replace
sys.argv = [script]; runpy.run_path(script, run_name="__main__")
'''


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def save(p, o, indent=2): Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
def sha_obj(o): return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

CFG = ["platform_constructible_space", "vehicle_parameters", "service_baseline"]
STAGE_ORDER = ["station_master", "spatial_join", "demography", "jobs", "service_baseline", "ridership_reference", "poi", "walk_model", "input_package", "scenarios", "config"]
FOUR = CFG + ["scenario_results"]
TWO = ["platform_constructible_space", "vehicle_parameters"]   # missing before step 6; now assumed (see THREE)
THREE = ["platform_constructible_space", "vehicle_parameters", "scenario_results"]   # assumption-backed config inputs since step 6


def consumed_files(c, names):
    return [{"name": n, "path": f"data/miami/2026-09-14/{n}", "sha256": sha(c.data / n)} for n in names]


def current_pkgs(c, stages):
    return [{"stage": s, "package_id": load(c.data / f"{s}_current.json")["package_id"]} for s in stages]


def fake_package(c, stage, consumed_inputs=None, consumed_packages=None, manifest_extra=None):
    """Publish a minimal but valid package for a stage that is not implemented yet (simulates a future layer):
    <stage>/pkg-<id>/{output.json, manifest.json} + <stage>_current.json pointer, following the contract §11 layout."""
    d = c.data / stage; d.mkdir(exist_ok=True); tmp = d / ".fixture"
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir()
    save(tmp / "output.json", {"stage": stage, "note": "regression fixture", "n": len(list(d.glob("pkg-*")))})
    m = {"stage": stage, "schema_version": "regression-fixture/1.0", "built_on": "2026-09-15", "ready_for_downstream": True,
         "outputs": [{"file": "output.json", "sha256": sha(tmp / "output.json")}],
         "consumed_inputs": consumed_inputs or [], "consumed_packages": consumed_packages or [], **(manifest_extra or {})}
    pid = "pkg-" + sha_obj(m)[:12]; m["package_id"] = pid; save(tmp / "manifest.json", m)
    pkg = d / pid
    if pkg.exists(): shutil.rmtree(pkg)
    tmp.rename(pkg)
    ptr = {"stage": stage, "package_id": pid, "package_dir": f"{stage}/{pid}", "manifest_sha256": sha(pkg / "manifest.json")}
    save(c.data / f"{stage}_current.json", ptr); return ptr


class Copy:
    def __init__(self, base, name, src=ROOT):
        self.root = base / name
        shutil.copytree(src, self.root, ignore=IGNORE)
        self.data, self.raw = self.root / DATA_REL, self.root / RAW_REL
        (self.root / "scripts/_inject.py").write_text(INJECT, encoding="utf-8")

    def run(self, script, *args, env=None, inject=None):
        cmd = [PY] + ([str(self.root / "scripts/_inject.py"), inject] if inject else []) + [str(self.root / script), *args]
        return subprocess.run(cmd, cwd=self.root, capture_output=True, text=True, env={**os.environ, **(env or {})})

    def readiness(self): return load(self.data / "gis_data_readiness.json")
    def sj(self):
        z = self.readiness()["zoning"]; return z["station_spatial_join_status"], z["station_spatial_join"]
    def pointer(self):
        p = self.data / "spatial_join_current.json"; return load(p) if p.exists() else None
    def packages(self):
        d = self.data / "spatial_join"; return sorted(x.name for x in d.glob("pkg-*") if x.is_dir()) if d.exists() else []
    def failed_logs(self):
        d = self.data / "failed"; return sorted(x.name for x in d.glob("spatial_join_failed_*.json")) if d.exists() else []
    def snapshot(self):  # every file under data/ except failure logs and staging
        return {str(p.relative_to(self.data)): sha(p) for p in self.data.rglob("*")
                if p.is_file() and "failed" not in p.parts and ".staging" not in p.parts}
    def unchanged(self, snap):  # every previously present file still present and byte-identical (new files allowed)
        return all((self.data / k).exists() and sha(self.data / k) == v for k, v in snap.items())
    def mismatches(self):  # (manifest, file) pairs whose recorded sha256 != file on disk
        out = []
        bm = load(self.data / "build_manifest.json")
        out += [("build_manifest.json", o["file"]) for o in bm["outputs"]
                if not (self.data / o["file"]).exists() or sha(self.data / o["file"]) != o["sha256"]]
        ptr = self.pointer()
        if ptr:
            d = self.data / ptr["package_dir"]; m = load(d / "spatial_join_manifest.json")
            out += [(ptr["package_dir"], o["file"]) for o in m["outputs"] if sha(d / o["file"]) != o["sha256"]]
            if sha(d / "spatial_join_manifest.json") != ptr["manifest_sha256"]: out.append(("pointer", "manifest_sha256"))
        return out


# ---------------- mutations (applied to a copy only) ----------------
def mutate_station(c):
    p = c.root / "config/miami_station_registry_v1.json"; r = load(p)
    r["stations"][0]["name"] += " (regression)"; save(p, r)

def mutate_window(c):
    p = c.raw / "source_manifest.json"; m = load(p)
    m["study_bbox_wgs84"][2] = round(m["study_bbox_wgs84"][2] + 0.001, 6); save(p, m)

def mutate_zoning(c):
    for name, key in (("zoning_study_window.geojson", "properties"), ("zoning_study_window.esri.json", "attributes")):
        p = c.raw / name; g = load(p)
        for f in g["features"]:
            if f[key]["FID"] == 64: f[key]["M21_ZONE"] = "T6-8-O"
        save(p, g, indent=None)

def mutate_config(c):
    p = c.root / "scripts/build_miami_station_zoning_profile.py"; s = p.read_text(encoding="utf-8")
    assert "QUAD_SEGS = 64" in s; p.write_text(s.replace("QUAD_SEGS = 64", "QUAD_SEGS = 48", 1), encoding="utf-8")

def mutate_lock(c):
    p = c.root / "requirements-gis.lock.txt"; s = p.read_text(encoding="utf-8")
    assert "geos=3.13.1" in s; p.write_text(s.replace("geos=3.13.1", "geos=3.12.0"), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out"); ap.add_argument("--base"); ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    base = (Path(a.base) if a.base else Path(tempfile.mkdtemp(prefix="miami-regression-"))).resolve()   # macOS TMPDIR is a symlink (/var -> /private/var); scripts resolve __file__, so copies must be canonical too
    base.mkdir(parents=True, exist_ok=True)
    results = {}

    def record(name, fn):
        t = time.time()
        try: checks, details = fn()
        except Exception as e: checks, details = {"scenario_ran_without_exception": False}, {"exception": repr(e)}
        results[name] = {"passed": all(checks.values()), "checks": checks, "details": details, "seconds": round(time.time() - t, 1)}
        failed = ", ".join(k for k, v in checks.items() if not v)
        print(f"{'PASS' if results[name]['passed'] else 'FAIL'}  {name:26s} {results[name]['seconds']:6.1f}s  {failed}")

    print(f"interpreter: {PY}\ncopies under: {base}")
    baseline = Copy(base, "baseline")

    def s_baseline():
        c = baseline; pk_before = c.packages(); r = c.run("scripts/build_all_miami.py")
        status, block = c.sj(); mm = c.mismatches(); ptr = c.pointer()
        # a deterministic rebuild reuses the tree's current package (count unchanged); a tree without a published package gains exactly one
        expected_new = 0 if (ROOT / DATA_REL / "spatial_join_current.json").exists() else 1
        bm = load(c.data / "build_manifest.json"); pm = load(c.data / ptr["package_dir"] / "spatial_join_manifest.json")
        listed = [o["file"] for o in bm["outputs"]] + [o["file"] for o in pm["outputs"]]
        checks = {"ordered_rebuild_exit_0": r.returncode == 0, "status_DONE": status == "DONE",
                  "ready_for_downstream_true": block.get("ready_for_downstream") is True, "no_manifest_mismatch": not mm,
                  "readiness_not_listed_in_any_manifest": "gis_data_readiness.json" not in listed,
                  "gis_inventory_listed_upstream": "gis_inventory.json" in listed,
                  "no_extra_package_created": len(c.packages()) == len(pk_before) + expected_new,
                  "check_mode_exit_0": c.run("scripts/miami_readiness.py", "--check").returncode == 0,
                  "no_staging_left": not (c.data / "spatial_join/.staging").exists()}
        details = {"status": status, "mismatches": mm, "package": ptr["package_dir"], "stdout_tail": r.stdout[-300:], "stderr_tail": r.stderr[-300:]}
        prod_ptr = ROOT / DATA_REL / "spatial_join_current.json"
        if prod_ptr.exists():
            pd = ROOT / DATA_REL / load(prod_ptr)["package_dir"]; here = c.data / ptr["package_dir"]
            checks["byte_identical_to_this_trees_published_package"] = (
                ptr["package_dir"] == load(prod_ptr)["package_dir"] and all(sha(pd / f) == sha(here / f) for f in os.listdir(pd)))
        else: details["note"] = "this tree has no published package yet; cross-copy determinism not compared"
        return checks, details
    record("baseline_full_rebuild", s_baseline)

    def s_rerun():
        c = baseline; snap = c.snapshot(); pk = c.packages(); r = c.run("scripts/build_all_miami.py")
        checks = {"exit_0": r.returncode == 0, "every_data_file_byte_identical": c.snapshot() == snap,
                  "no_new_package": c.packages() == pk, "package_reported_reused": "reused, byte-identical" in r.stdout}
        return checks, {"stdout_tail": r.stdout[-300:]}
    record("unchanged_rerun", s_rerun)

    def s_input_change(name, mutate, key):
        def run():
            c = Copy(base, name, baseline.root); before = c.pointer(); pk_before = c.packages(); mutate(c)
            r1 = c.run("scripts/build_miami_station_master.py"); s1, b1 = c.sj()
            checks = {"upstream_exit_0": r1.returncode == 0, "STALE_after_upstream_only": s1 == "STALE",
                      "ready_false_while_stale": b1.get("ready_for_downstream") is False,
                      f"changed_lists_exactly_{key}": b1.get("consumed_inputs_changed") == [key],
                      "check_mode_exit_1_while_stale": c.run("scripts/miami_readiness.py", "--check").returncode == 1,
                      "old_package_still_verifies": not c.mismatches(), "pointer_untouched_by_upstream": c.pointer() == before}
            r2 = c.run("scripts/build_miami_station_zoning_profile.py"); s2, b2 = c.sj(); after = c.pointer()
            checks.update({"downstream_exit_0": r2.returncode == 0, "DONE_after_downstream": s2 == "DONE",
                           "new_package_published": after["package_dir"] != before["package_dir"],
                           "pointer_records_previous_package": after["previous_package_dir"] == before["package_dir"],
                           "previous_packages_kept_plus_one_new": len(c.packages()) == len(pk_before) + 1, "no_manifest_mismatch": not c.mismatches()})
            return checks, {"stale_block": {k: b1.get(k) for k in ("freshness", "consumed_inputs_changed", "ready_for_downstream")},
                            "packages": c.packages(), "r1_stderr_tail": r1.stderr[-300:], "r2_stdout_tail": r2.stdout[-300:], "r2_stderr_tail": r2.stderr[-300:]}
        return run
    record("station_change", s_input_change("station_change", mutate_station, "station_master_sha256"))
    record("window_change", s_input_change("window_change", mutate_window, "study_window_sha256"))
    record("zoning_change", s_input_change("zoning_change", mutate_zoning, "zoning_raw_sha256"))

    def s_publish_failure(mode):
        def run():
            c = Copy(base, f"publish_failure_{mode}", baseline.root); mutate_config(c)
            snap = c.snapshot(); before = c.pointer(); pk = c.packages()
            r = c.run("scripts/build_miami_station_zoning_profile.py", inject=mode); s, b = c.sj()
            checks = {"exit_nonzero": r.returncode != 0, "injected_error_reported": "injected failure" in (r.stdout + r.stderr),
                      "pointer_unchanged": c.pointer() == before, "previously_published_files_unchanged": c.unchanged(snap),
                      "current_package_verifies": not c.mismatches(),
                      "readiness_DONE_on_old_package": s == "DONE" and b.get("package_dir") == before["package_dir"],
                      "no_staging_left": not (c.data / "spatial_join/.staging").exists(),
                      "no_pointer_tmp_left": not (c.data / "spatial_join_current.json.tmp").exists(),
                      "failure_log_written": len(c.failed_logs()) == 1}
            new = [p for p in c.packages() if p not in pk]
            if mode == "rename":
                checks["no_new_package_dir"] = not new
            else:
                checks["new_package_complete_but_not_current"] = (len(new) == 1 and verify_package(c.data / "spatial_join" / new[0])[0]
                                                                  and before["package_dir"] != f"spatial_join/{new[0]}")
                r2 = c.run("scripts/build_miami_station_zoning_profile.py"); s2, b2 = c.sj(); after = c.pointer()
                checks.update({"plain_rerun_recovers_exit_0": r2.returncode == 0, "DONE_after_recovery": s2 == "DONE",
                               "pointer_now_on_new_package": after["package_dir"] == f"spatial_join/{new[0]}",
                               "recovery_reused_complete_package": "reused, byte-identical" in r2.stdout,
                               "previous_recorded": after["previous_package_dir"] == before["package_dir"]})
            return checks, {"stdout_tail": r.stdout[-300:], "stderr_tail": r.stderr[-200:], "packages": c.packages(), "failed_logs": c.failed_logs()}
        return run
    record("publish_failure_rename", s_publish_failure("rename"))
    record("publish_failure_pointer", s_publish_failure("pointer"))

    def s_force_fail():
        c = Copy(base, "validation_failure", baseline.root); snap = c.snapshot(); before = c.pointer(); pk = c.packages()
        r = c.run("scripts/build_miami_station_zoning_profile.py", env={"SPATIAL_JOIN_FORCE_FAIL": "1"})
        checks = {"exit_1": r.returncode == 1, "every_data_file_unchanged": c.snapshot() == snap, "pointer_unchanged": c.pointer() == before,
                  "no_new_package": c.packages() == pk, "no_staging_left": not (c.data / "spatial_join/.staging").exists(),
                  "failure_log_written": len(c.failed_logs()) == 1, "readiness_still_DONE": c.sj()[0] == "DONE"}
        return checks, {"stdout_tail": r.stdout[-300:]}
    record("validation_failure", s_force_fail)

    def s_lock():
        c = Copy(base, "lock_mismatch", baseline.root); mutate_lock(c); snap = c.snapshot(); pk = c.packages()
        r = c.run("scripts/build_miami_station_zoning_profile.py")
        checks = {"exit_1": r.returncode == 1, "mismatch_reported": "dependency lock mismatch" in r.stdout,
                  "every_data_file_unchanged": c.snapshot() == snap, "no_new_package": c.packages() == pk}
        return checks, {"stdout_tail": r.stdout[-300:]}
    record("lock_mismatch", s_lock)

    def s_corrupt():
        c = Copy(base, "corrupt_package", baseline.root); ptr = c.pointer()
        f = c.data / ptr["package_dir"] / "station_overlap.json"; f.write_text(f.read_text(encoding="utf-8") + " ", encoding="utf-8")
        r = c.run("scripts/miami_readiness.py", "--check"); s, b = c.sj()
        checks = {"check_mode_exit_1": r.returncode == 1, "status_CORRUPT_PACKAGE": s == "CORRUPT_PACKAGE",
                  "ready_false": b.get("ready_for_downstream") is False,
                  "problem_names_the_file": any("station_overlap.json" in p for p in b.get("problems", []))}
        r2 = c.run("scripts/build_miami_station_zoning_profile.py"); s2, _ = c.sj()
        checks.update({"rerun_republishes_exit_0": r2.returncode == 0, "DONE_after_rerun": s2 == "DONE",
                       "corrupt_dir_quarantined": any(".corrupt-" in x.name for x in (c.data / "spatial_join").iterdir()),
                       "no_manifest_mismatch": not c.mismatches()})
        return checks, {"problems": b.get("problems"), "stdout_tail": r2.stdout[-300:]}
    record("corrupt_package_detected", s_corrupt)

    def s_single_writer():
        c = baseline; rd = c.readiness(); bm = c.data / "build_manifest.json"; ptr = c.pointer()
        pm = c.data / ptr["package_dir"] / "spatial_join_manifest.json"
        listed = [o["file"] for o in load(bm)["outputs"]] + [o["file"] for o in load(pm)["outputs"]]
        h1 = sha(c.data / "gis_data_readiness.json"); r = c.run("scripts/miami_readiness.py"); h2 = sha(c.data / "gis_data_readiness.json")
        up = (c.root / "scripts/build_miami_station_master.py").read_text(encoding="utf-8")
        down = (c.root / "scripts/build_miami_station_zoning_profile.py").read_text(encoding="utf-8")
        checks = {"readiness_not_listed_in_any_manifest": "gis_data_readiness.json" not in listed,
                  "lineage_matches_build_manifest": rd["lineage"]["build_manifest_sha256"] == sha(bm),
                  "lineage_matches_package_manifest": rd["lineage"]["spatial_join_manifest_sha256"] == sha(pm) == ptr["manifest_sha256"],
                  "aggregator_rerun_byte_identical": r.returncode == 0 and h1 == h2,
                  "stage_scripts_never_write_readiness": 'write("gis_data_readiness.json"' not in up and 'gis_data_readiness.json", readiness' not in down}
        return checks, {}
    record("readiness_single_writer", s_single_writer)

    # ---------------- step 1 (2026-09-15): generic stage registry + readiness flags ----------------
    def statuses(c): return {k: v["status"] for k, v in c.readiness()["stages"].items()}

    def s_flags_baseline():
        c = baseline; r = c.readiness(); fl = r["readiness_flags"]; st = {k: v["status"] for k, v in r["stages"].items()}
        checks = {"schema_2_2": r["schema_version"] == "miami-gis-readiness/2.2", "stages_in_build_order": list(st) == STAGE_ORDER,
                  "no_legacy_status_keys_at_top_level": not any(k in r for k in ("demography", "jobs_and_commute", "pois", "walk_network", "demand", "engineering")),
                  "layers_summary_matches_stages": r["layers"]["demography"]["status"] == "DONE" and r["layers"]["jobs_and_commute"]["status"] == "DONE"
                                                   and r["layers"]["pois"]["status"] == "DONE" and r["layers"]["walk_network"]["status"] == "NOT_RUN",
                  "upstream_inventory_nested_and_verified": r["upstream_inventory"]["verified_against_build_manifest"] is True and "status" not in r["upstream_inventory"],
                  "station_master_DONE": st["station_master"] == "DONE", "spatial_join_DONE": st["spatial_join"] == "DONE",
                  "built_stages_DONE": all(st[s] == "DONE" for s in ("demography", "jobs", "service_baseline", "input_package", "scenarios", "config")),
                  "unbuilt_layers_NOT_RUN": all(st[s] == "NOT_RUN" for s in ("walk_model",)), "poi_DONE": st["poi"] == "DONE",
                  "ai_flag_true": fl["ready_for_ai_interpretation"] is True,
                  "ai_required_not_done_empty": fl["ai_required_not_done"] == [],
                  "optional_missing_lists_walk_model_only": fl["ai_missing_optional"] == ["walk_model"],
                  "config_complete_true": fl["config_inputs_complete"] is True,
                  "config_all_observed_false": fl["config_inputs_all_observed"] is False,
                  "config_missing_none": fl["config_missing_inputs"] == [],
                  "assumption_backed_three": fl["config_assumption_backed_inputs"] == THREE,
                  "flags_are_booleans": all(isinstance(fl[k], bool) for k in ("ready_for_ai_interpretation", "config_inputs_complete", "config_inputs_all_observed")),
                  "code_matches_current_true": r["stages"]["spatial_join"]["code_matches_current"] is True and r["stages"]["station_master"]["code_matches_current"] is True,
                  "legacy_zoning_block_kept": r["zoning"]["station_spatial_join_status"] == "DONE" and r["zoning"]["station_spatial_join"]["consumed_inputs_changed"] == [],
                  "check_ai_exit_0": c.run("scripts/miami_readiness.py", "--check-ai").returncode == 0,
                  "check_exit_0": c.run("scripts/miami_readiness.py", "--check").returncode == 0}
        return checks, {"stages": st, "flags": {k: fl[k] for k in ("ready_for_ai_interpretation", "ai_missing_optional", "config_inputs_complete", "config_missing_inputs")}}
    record("readiness_flags_baseline", s_flags_baseline)

    shared = {}

    def s_future_layers():
        c = Copy(base, "future_layers", baseline.root); shared["c"] = c
        sj = c.pointer(); sjpkg = [{"stage": "spatial_join", "package_id": sj["package_id"]}]
        # demography, jobs and input_package are real packages since steps 3-4; fixtures are only used for poi below and for scenarios later
        r = c.run("scripts/miami_readiness.py"); rd = c.readiness(); fl = rd["readiness_flags"]; st = {k: v["status"] for k, v in rd["stages"].items()}
        checks = {"aggregator_exit_0": r.returncode == 0,
                  "real_layers_DONE": all(st[s] == "DONE" for s in ("demography", "jobs", "input_package")),
                  "ai_true_without_optional_layers": fl["ready_for_ai_interpretation"] is True,
                  "optional_missing_walk_model": fl["ai_missing_optional"] == ["walk_model"],
                  "config_complete_with_assumptions": fl["config_inputs_complete"] is True and fl["config_inputs_all_observed"] is False,
                  "check_ai_exit_0": c.run("scripts/miami_readiness.py", "--check-ai").returncode == 0}
        fake_package(c, "walk_model", consumed_packages=sjpkg); c.run("scripts/miami_readiness.py")
        checks["walk_model_fixture_clears_optional_missing"] = c.readiness()["readiness_flags"]["ai_missing_optional"] == []
        return checks, {"stages": st, "stdout": r.stdout[-300:]}
    record("future_layers_fixtures", s_future_layers)

    def s_assumption_backed():
        c = shared["c"]
        cfg_assumed = {"platform_constructible_space": {"acquisition_status": "assumed", "value_status": "value", "provenance_class": "assumption"},
                       "vehicle_parameters": {"acquisition_status": "assumed", "value_status": "value", "provenance_class": "assumption"},
                       "service_baseline": {"acquisition_status": "derivable_from_gtfs", "value_status": "value", "provenance_class": "derived"}}
        fake_package(c, "input_package", consumed_packages=current_pkgs(c, ["spatial_join", "demography", "jobs"]), manifest_extra={"config_inputs": cfg_assumed})
        fake_package(c, "scenarios", consumed_packages=current_pkgs(c, ["input_package"]), manifest_extra={"assumption_parameter_ids": ["prt_adoption_rate", "station_allocation"]})
        c.run("scripts/miami_readiness.py"); fl = c.readiness()["readiness_flags"]
        checks = {"complete_true": fl["config_inputs_complete"] is True, "all_observed_false": fl["config_inputs_all_observed"] is False,
                  "assumed_lists_three": fl["config_assumption_backed_inputs"] == ["platform_constructible_space", "vehicle_parameters", "scenario_results"],
                  "missing_empty": fl["config_missing_inputs"] == []}
        cfg_obs = {n: {"acquisition_status": "acquired", "value_status": "value", "provenance_class": "observed"} for n in CFG}
        fake_package(c, "input_package", consumed_packages=current_pkgs(c, ["spatial_join", "demography", "jobs"]), manifest_extra={"config_inputs": cfg_obs})
        fake_package(c, "scenarios", consumed_packages=current_pkgs(c, ["input_package"]), manifest_extra={"assumption_parameter_ids": []})
        c.run("scripts/miami_readiness.py"); fl2 = c.readiness()["readiness_flags"]
        checks.update({"observed_variant_complete_true": fl2["config_inputs_complete"] is True,
                       "observed_variant_all_observed_true": fl2["config_inputs_all_observed"] is True,
                       "observed_variant_no_assumed": fl2["config_assumption_backed_inputs"] == []})
        return checks, {"assumed_variant": {k: fl[k] for k in ("config_inputs_complete", "config_inputs_all_observed", "config_assumption_backed_inputs")}}
    record("assumption_backed_inputs", s_assumption_backed)

    def s_stale_propagation():
        c = shared["c"]; before = c.pointer(); mutate_config(c)
        r = c.run("scripts/build_miami_station_zoning_profile.py"); rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}; fl = rd["readiness_flags"]
        checks = {"spatial_join_republished": r.returncode == 0 and c.pointer()["package_id"] != before["package_id"],
                  "spatial_join_DONE": st["spatial_join"] == "DONE",
                  "direct_consumers_STALE": st["demography"] == "STALE" and st["jobs"] == "STALE" and st["input_package"] == "STALE",
                  "reason_names_spatial_join": rd["stages"]["demography"]["consumed_packages_changed"] == ["spatial_join"],
                  "propagates_to_scenarios": st["scenarios"] == "STALE" and rd["stages"]["scenarios"]["consumed_stages_not_done"] == ["input_package"],
                  "ai_flag_false_again": fl["ready_for_ai_interpretation"] is False,
                  "required_not_done_lists_three": fl["ai_required_not_done"] == ["demography", "jobs", "input_package"],
                  "config_incomplete_again": fl["config_inputs_complete"] is False and fl["config_missing_inputs"] == FOUR}
        return checks, {"stages": st}
    record("stale_propagation", s_stale_propagation)

    def s_raw_change_station_master():
        c = Copy(base, "raw_change", baseline.root); mutate_station(c)
        r = c.run("scripts/miami_readiness.py"); rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}; sm = rd["stages"]["station_master"]
        checks = {"aggregator_exit_0": r.returncode == 0, "station_master_STALE": st["station_master"] == "STALE",
                  "inputs_changed_names_registry": sm.get("inputs_changed") == ["config/miami_station_registry_v1.json"],
                  "spatial_join_still_DONE_data_unchanged": st["spatial_join"] == "DONE",
                  "ai_false_because_station_master": rd["readiness_flags"]["ready_for_ai_interpretation"] is False and "station_master" in rd["readiness_flags"]["ai_required_not_done"],
                  "check_exit_0_spatial_join_only": c.run("scripts/miami_readiness.py", "--check").returncode == 0}
        r2 = c.run("scripts/build_miami_station_master.py"); st2 = statuses(c)
        checks.update({"upstream_rebuild_exit_0": r2.returncode == 0, "station_master_DONE_after_rebuild": st2["station_master"] == "DONE",
                       "spatial_join_STALE_after_rebuild": st2["spatial_join"] == "STALE"})
        r3 = c.run("scripts/build_miami_station_zoning_profile.py"); st3 = statuses(c)
        checks["both_DONE_after_downstream"] = r3.returncode == 0 and st3["station_master"] == "DONE" and st3["spatial_join"] == "DONE"
        return checks, {"before": st, "after_upstream": st2, "after_downstream": st3}
    record("raw_change_station_master", s_raw_change_station_master)

    def s_code_change_informational():
        c = Copy(base, "code_change", baseline.root)
        for rel in ("scripts/build_miami_station_zoning_profile.py", "scripts/build_miami_station_master.py"):
            p = c.root / rel; p.write_text(p.read_text(encoding="utf-8") + "\n# regression: comment-only change\n", encoding="utf-8")
        r = c.run("scripts/miami_readiness.py"); rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}
        checks = {"aggregator_exit_0": r.returncode == 0, "spatial_join_still_DONE": st["spatial_join"] == "DONE",
                  "station_master_still_DONE": st["station_master"] == "DONE",
                  "code_flags_false": rd["stages"]["spatial_join"]["code_matches_current"] is False and rd["stages"]["station_master"]["code_matches_current"] is False,
                  "ai_required_not_done_unaffected": rd["readiness_flags"]["ai_required_not_done"] == []}
        before = c.pointer(); r2 = c.run("scripts/build_all_miami.py"); rd2 = c.readiness()
        checks.update({"rebuild_exit_0": r2.returncode == 0, "new_package_after_code_change": c.pointer()["package_id"] != before["package_id"],
                       "code_flags_true_after_rebuild": rd2["stages"]["spatial_join"]["code_matches_current"] is True and rd2["stages"]["station_master"]["code_matches_current"] is True})
        return checks, {"stages_before_rebuild": st}
    record("code_change_informational", s_code_change_informational)

    # ---------------- step 3 (2026-09-15): demography + jobs layers ----------------
    def package_identical(c, stage):
        prod_ptr = ROOT / DATA_REL / f"{stage}_current.json"
        if not prod_ptr.exists(): return None
        pd = ROOT / DATA_REL / load(prod_ptr)["package_dir"]; here = c.data / load(c.data / f"{stage}_current.json")["package_dir"]
        files = [p.relative_to(pd) for p in pd.rglob("*") if p.is_file()]
        return (load(prod_ptr)["package_id"] == load(c.data / f"{stage}_current.json")["package_id"]
                and all((here / f).exists() and sha(pd / f) == sha(here / f) for f in files))

    def s_layers():
        c = baseline; rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}
        dem = c.data / load(c.data / "demography_current.json")["package_dir"]; jobs = c.data / load(c.data / "jobs_current.json")["package_dir"]
        dv, jv = load(dem / "demography_validation.json"), load(jobs / "jobs_validation.json"); od = load(jobs / "od_summary.json")
        dp, jp = load(dem / "station_demography_profile.json"), load(jobs / "station_jobs_profile.json")
        checks = {"demography_DONE": st["demography"] == "DONE", "jobs_DONE": st["jobs"] == "DONE",
                  "demography_validation_PASS": dv["validation_status"] == "PASS", "jobs_validation_PASS": jv["validation_status"] == "PASS",
                  "demography_consumed_spatial_join": [x["stage"] for x in load(dem / "manifest.json")["consumed_packages"]] == ["spatial_join"],
                  "jobs_consumed_demography": [x["stage"] for x in load(jobs / "manifest.json")["consumed_packages"]] == ["demography"],
                  "lodes_wac_od_identity_holds": all(od["reconciliation"]["identity_holds"].values()),
                  "demography_net_dedup_not_above_sum": dp["network"]["deduplicated"]["counts"]["D01"]["value"] <= dp["network"]["sum_of_21_station_cumulative_discs"]["D01"],
                  "jobs_net_dedup_not_above_sum": jp["network"]["deduplicated"]["jobs_by_workplace"]["JT00"]["C000"]["value"] <= jp["network"]["sum_of_21_station_cumulative_discs"]["jobs_by_workplace_C000"]["JT00"],
                  "disability_indicator_is_tract_level": dp["stations"][0]["cumulative_0_to_half_mile"]["counts"]["D13"]["geography_unit"] == "tract",
                  "no_manifest_mismatch": not c.mismatches()}
        for stage in ("demography", "jobs"):
            ident = package_identical(c, stage)
            if ident is not None: checks[f"{stage}_byte_identical_to_published_package"] = ident
        return checks, {"stages": st, "od_links_kept": od["links_kept"], "net_population": dp["network"]["deduplicated"]["counts"]["D01"]["display_value"]}
    record("demography_jobs_layers", s_layers)

    def s_raw_change_layers():
        c = Copy(base, "raw_change_layers", baseline.root); before = load(c.data / "demography_current.json")
        f = c.root / "raw/miami/2026-09-15/acs/acs5_2024_bg_12086_B01003.json"; f.write_text(f.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        r = c.run("scripts/miami_readiness.py"); rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}
        checks = {"aggregator_exit_0": r.returncode == 0, "demography_STALE": st["demography"] == "STALE",
                  "reason_names_raw_file": any("B01003" in x for x in rd["stages"]["demography"]["consumed_inputs_changed"]),
                  "jobs_STALE_by_propagation": st["jobs"] == "STALE" and rd["stages"]["jobs"]["consumed_stages_not_done"] == ["demography"],
                  "spatial_join_still_DONE": st["spatial_join"] == "DONE", "ai_flag_false": rd["readiness_flags"]["ready_for_ai_interpretation"] is False}
        r2 = c.run("scripts/build_miami_demography.py")
        checks.update({"demography_rebuild_halts_on_raw_hash_gate": r2.returncode != 0 and "sha256 != raw source_manifest.json" in (r2.stdout + r2.stderr),
                       "pointer_unchanged_after_halt": load(c.data / "demography_current.json") == before})
        return checks, {"stages": st, "halt_message": (r2.stdout + r2.stderr).strip()[-200:]}
    record("raw_change_layers_stale", s_raw_change_layers)

    # ---------------- step 4 (2026-09-15): station input package ----------------
    def s_input_package():
        c = baseline; rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}; fl = rd["readiness_flags"]
        ptr = load(c.data / "input_package_current.json"); d = c.data / ptr["package_dir"]; m = load(d / "manifest.json"); v = load(d / "input_package_validation.json")
        pins_ok = all(load(c.data / f"{p['stage']}_current.json")["package_id"] == p["package_id"] for p in m["consumed_packages"])
        checks = {"input_package_DONE": st["input_package"] == "DONE", "validation_PASS": v["validation_status"] == "PASS",
                  "pins_equal_current_pointers": pins_ok,
                  "pins_cover_six_layers": sorted(p["stage"] for p in m["consumed_packages"]) == ["demography", "jobs", "poi", "ridership_reference", "service_baseline", "spatial_join"],
                  "21_station_files_listed": len(list((d / "stations").glob("*.json"))) == 21 and sum(1 for o in m["outputs"] if o["file"].startswith("stations/")) == 21,
                  "ai_flag_true": fl["ready_for_ai_interpretation"] is True, "config_inputs_summary_present": set(m["config_inputs"]) == set(CFG),
                  "config_missing_none": fl["config_missing_inputs"] == [], "every_value_has_status": v["every_value_carries_value_status"] is True,
                  "platform_and_vehicle_assumed": all(m["config_inputs"][k]["acquisition_status"] == "assumed" for k in ("platform_constructible_space", "vehicle_parameters")),
                  "module_spec_acquired": m["config_input_extras"]["platform_module_specification"]["acquisition_status"] == "acquired",
                  "service_baseline_field_derived": m["config_inputs"]["service_baseline"]["acquisition_status"] == "derived" and m["config_inputs"]["service_baseline"]["value_status"] == "value"}
        ident = package_identical(c, "input_package")
        if ident is not None: checks["byte_identical_to_published_package"] = ident
        return checks, {"package": ptr["package_id"], "pins": m["consumed_packages"]}
    record("input_package_build", s_input_package)

    # ---------------- step 5 (2026-09-15): service baseline + scenarios ----------------
    def s_scenarios():
        c = baseline; rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}; fl = rd["readiness_flags"]
        sb = c.data / load(c.data / "service_baseline_current.json")["package_dir"]; sc = c.data / load(c.data / "scenarios_current.json")["package_dir"]
        sv, cv = load(sb / "service_baseline_validation.json"), load(sc / "scenario_validation.json"); res = load(sc / "scenario_results.json"); m = load(sc / "manifest.json")
        tot = [res["scenarios"][s]["totals"]["prt_am_peak_hour_trips"] for s in ("low", "medium", "high")]
        params = load(sc / "scenario_parameters.json")
        checks = {"service_baseline_DONE": st["service_baseline"] == "DONE", "scenarios_DONE": st["scenarios"] == "DONE",
                  "service_validation_PASS": sv["validation_status"] == "PASS", "scenario_validation_PASS": cv["validation_status"] == "PASS",
                  "conservation_all_scenarios": all(cv["conservation_all_scenarios"].values()), "monotonic_low_medium_high": tot[0] <= tot[1] <= tot[2],
                  "low_adoption_bounded_by_observed_transit_share": cv["low_adoption_not_above_observed_transit_share"] is True,
                  "assumption_ids_in_manifest": len(m["assumption_parameter_ids"]) >= 5,
                  "every_shared_parameter_tagged": all(p.get("provenance_class") in ("observed", "derived") and p.get("data_nature") for p in params["observed_or_derived_shared_by_all_scenarios"]),
                  "scenarios_consume_input_jobs_service_reference": sorted(p["stage"] for p in m["consumed_packages"]) == ["input_package", "jobs", "ridership_reference", "service_baseline"],
                  "readiness_scenario_results_assumption_backed": "scenario_results" in fl["config_assumption_backed_inputs"],
                  "readiness_missing_none": fl["config_missing_inputs"] == [], "config_complete_true_with_assumptions": fl["config_inputs_complete"] is True and fl["config_inputs_all_observed"] is False,
                  "base_is_coverage_weighted": params["observed_or_derived_shared_by_all_scenarios"][0]["id"].endswith("coverage_weighted")
                                               and cv["coverage_weighting"]["coverage_weighted_links_JT01"] < cv["coverage_weighting"]["whole_block_links_JT01"]}
        for stage in ("service_baseline", "scenarios"):
            ident = package_identical(c, stage)
            if ident is not None: checks[f"{stage}_byte_identical_to_published_package"] = ident
        return checks, {"totals_am_peak": tot, "peak_window": cv["peak_window"], "coverage": cv["coverage_weighting"]}
    record("service_baseline_and_scenarios", s_scenarios)

    # ---------------- review 3 (2026-09-17): optional layer appearing later; corrupt optional layer isolated ----------------
    def s_optional_added():
        c = Copy(base, "optional_added", baseline.root); before = load(c.data / "input_package_current.json")
        fake_package(c, "walk_model", consumed_packages=current_pkgs(c, ["spatial_join"]))   # poi is real since step 7b; walk_model is still absent
        r = c.run("scripts/miami_readiness.py"); rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}
        checks = {"aggregator_exit_0": r.returncode == 0, "walk_model_DONE": st["walk_model"] == "DONE",
                  "input_package_STALE": st["input_package"] == "STALE",
                  "reason_names_walk_model": rd["stages"]["input_package"].get("optional_layers_now_available") == ["walk_model"],
                  "freshness_says_optional_layer": "optional_layer" in rd["stages"]["input_package"]["freshness"],
                  "scenarios_STALE_by_propagation": st["scenarios"] == "STALE",
                  "ai_flag_false_until_rebuild": rd["readiness_flags"]["ready_for_ai_interpretation"] is False}
        r2 = c.run("scripts/build_miami_input_package.py"); rd2 = c.readiness()
        m = load(c.data / load(c.data / "input_package_current.json")["package_dir"] / "manifest.json")
        checks.update({"rebuild_exit_0": r2.returncode == 0, "input_package_DONE_after_rebuild": rd2["stages"]["input_package"]["status"] == "DONE",
                       "walk_model_now_pinned": any(p["stage"] == "walk_model" for p in m["consumed_packages"]),
                       "absent_list_now_empty": m["optional_layers_absent_at_build"] == [],
                       "pointer_switched": load(c.data / "input_package_current.json")["package_id"] != before["package_id"]})
        return checks, {"freshness": rd["stages"]["input_package"]["freshness"]}
    record("optional_layer_added_marks_input_package_stale", s_optional_added)

    def s_corrupt_isolated():
        c = Copy(base, "corrupt_optional", baseline.root)
        fake_package(c, "walk_model", consumed_packages=current_pkgs(c, ["spatial_join"]))   # the still-absent optional layer
        d = c.data / load(c.data / "walk_model_current.json")["package_dir"]; (d / "manifest.json").write_text("{ this is not json", encoding="utf-8")
        r = c.run("scripts/miami_readiness.py"); rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}
        checks = {"aggregator_exit_0_with_corrupt_manifest": r.returncode == 0, "walk_model_CORRUPT_PACKAGE": st["walk_model"] == "CORRUPT_PACKAGE",
                  "problem_says_not_valid_json": any("not valid JSON" in p for p in rd["stages"]["walk_model"].get("problems", [])),
                  "other_stages_unaffected": st["input_package"] == "DONE" and st["scenarios"] == "DONE" and st["demography"] == "DONE" and st["poi"] == "DONE",
                  "ai_flag_still_true": rd["readiness_flags"]["ready_for_ai_interpretation"] is True}
        (c.data / "walk_model_current.json").write_text("{{ broken pointer", encoding="utf-8")
        r2 = c.run("scripts/miami_readiness.py"); rd2 = c.readiness()
        checks.update({"aggregator_exit_0_with_corrupt_pointer": r2.returncode == 0, "walk_model_CORRUPT_on_bad_pointer": rd2["stages"]["walk_model"]["status"] == "CORRUPT_PACKAGE",
                       "pointer_error_recorded": "walk_model" in rd2["lineage"]["pointer_errors"], "input_package_still_DONE": rd2["stages"]["input_package"]["status"] == "DONE"})
        return checks, {"problems": rd["stages"]["walk_model"].get("problems"), "pointer_errors": rd2["lineage"]["pointer_errors"]}
    record("corrupt_optional_layer_isolated", s_corrupt_isolated)

    # ---------------- step 6 (2026-09-17): PRT configuration stage ----------------
    def s_config():
        c = baseline; rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}; fl = rd["readiness_flags"]
        d = c.data / load(c.data / "config_current.json")["package_dir"]; v = load(d / "config_validation.json"); res = load(d / "station_config_results.json"); m = load(d / "manifest.json")
        tot = [v["berths_total_by_scenario"][s] for s in ("low", "medium", "high")]
        checks = {"config_DONE": st["config"] == "DONE", "validation_PASS": v["validation_status"] == "PASS",
                  "vehicle_conservation_all": all(res["scenarios"][s]["conservation_check"]["pass"] for s in ("low", "medium", "high")),
                  "berths_monotonic": tot[0] <= tot[1] <= tot[2],
                  "every_station_has_a_berth_in_low": all(x["berths"]["berths_required"] >= 1 for x in res["scenarios"]["low"]["stations"]),
                  "module_covers_requirement": all(x["module"]["berths_provided"] >= x["berths"]["berths_required"] for sc in ("low", "medium", "high") for x in res["scenarios"][sc]["stations"]),
                  "seven_assumption_ids_in_manifest": len(m["assumption_parameter_ids"]) == 7,
                  "consumes_scenarios_and_input_package": sorted(p["stage"] for p in m["consumed_packages"]) == ["input_package", "scenarios"],
                  "consumes_module_and_ops_files": sorted(x["name"] for x in m["consumed_inputs"]) == ["operations_assumptions", "platform_modules"],
                  "readiness_config_complete_true": fl["config_inputs_complete"] is True, "readiness_all_observed_false": fl["config_inputs_all_observed"] is False,
                  "readiness_assumption_backed_three": fl["config_assumption_backed_inputs"] == THREE,
                  "layers_configuration_DONE": rd["layers"]["configuration"]["status"] == "DONE"}
        ident = package_identical(c, "config")
        if ident is not None: checks["byte_identical_to_published_package"] = ident
        return checks, {"berths_total": v["berths_total_by_scenario"], "lane_ratio_high": res["scenarios"]["high"]["network"]["network_vehicle_trips_over_lane_throughput"]}
    record("config_stage", s_config)

    # ---------------- step 7a (2026-09-17): observed ridership reference ----------------
    def s_ridership_reference():
        c = baseline; rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}
        d = c.data / load(c.data / "ridership_reference_current.json")["package_dir"]; v = load(d / "ridership_reference_validation.json"); doc = load(d / "station_ridership_reference.json")
        sc = c.data / load(c.data / "scenarios_current.json")["package_dir"]; res = load(sc / "scenario_results.json"); ref = res.get("observed_reference")
        ip = load(c.data / load(c.data / "input_package_current.json")["package_dir"] / "stations" / "MIA-MM-09.json")["station"]["miami_specific_inputs"]["ridership_baseline"]
        checks = {"ridership_reference_DONE": st["ridership_reference"] == "DONE", "validation_PASS": v["validation_status"] == "PASS",
                  "21_stations_mapped_every_month": v["all_21_stations_mapped_every_month"] is True, "renamed_stations_flagged": len(v["renamed_stations_flagged"]) == 3,
                  "shares_sum_to_one": v["shares_sum_to_one"] is True, "semantics_not_trips_not_peak": doc["is_trips"] is False and doc["is_peak_hour"] is False,
                  "layers_demand_observed_acquired": rd["layers"]["demand"]["observed_ridership_status"].startswith("ACQUIRED"),
                  "input_package_ridership_baseline_acquired": ip["acquisition_status"] == "acquired" and ip["value_status"] == "value" and ip["provenance_class"] == "observed",
                  "scenarios_carry_observed_reference": ref is not None and ref["role"].startswith("observed REFERENCE"),
                  "reference_scale_ratios_below_one": all(x["ratio_scenario_over_observed"] < 1.0 for x in ref["scale"].values()) if ref else False,
                  "rank_correlation_in_range": v is not None and all(-1.0 <= (x["spearman_rank_correlation_station_shares"] or 0.0) <= 1.0 for x in ref["station_share_shape"].values()) if ref else False}
        ident = package_identical(c, "ridership_reference")
        if ident is not None: checks["byte_identical_to_published_package"] = ident
        return checks, {"system_mean": doc["system"]["avg_weekday_boardings_10_month_mean"], "rank_corr": {k: x["spearman_rank_correlation_station_shares"] for k, x in (ref or {}).get("station_share_shape", {}).items()}}
    record("ridership_reference_stage", s_ridership_reference)

    # ---------------- step 7b (2026-09-17): POI layer (optional for AI) ----------------
    def s_poi():
        c = baseline; rd = c.readiness(); st = {k: v["status"] for k, v in rd["stages"].items()}
        d = c.data / load(c.data / "poi_current.json")["package_dir"]; v = load(d / "poi_validation.json"); prof = load(d / "station_poi_profile.json"); feats = load(d / "poi_features.json")
        ipd = c.data / load(c.data / "input_package_current.json")["package_dir"]; st12 = load(ipd / "stations" / "MIA-MM-12.json")["station"]
        checks = {"poi_DONE": st["poi"] == "DONE", "validation_PASS": v["validation_status"] == "PASS",
                  "four_categories_present": sorted(prof["network"]["facilities_in_window"]) == ["clinic", "grocery", "park", "school"],
                  "counts_consistent": v["point_categories_cum_equals_band_sum"] is True and v["park_cum_between_max_band_and_sum"] is True and v["nearest_consistent_with_counts"] is True,
                  "excluded_records_documented": isinstance(feats["excluded_records"], list) and all("reason" in e for e in feats["excluded_records"]),
                  "straight_line_semantics": prof["distance_type"] == "straight_line" and prof["is_service_level_score"] is False,
                  "osm_crosscheck_recorded": prof["network"]["grocery_crosscheck_osm"]["osm_data_timestamp"] is not None,
                  "input_package_carries_poi_blocks": "poi" in st12["cumulative_0_to_half_mile"] and "poi_nearest_by_category" in st12,
                  "bayfront_park_nearest_park_is_bayfront_park": st12["poi_nearest_by_category"]["park"].get("name") == "Bayfront Park",
                  "readiness_optional_missing_walk_model_only": rd["readiness_flags"]["ai_missing_optional"] == ["walk_model"]}
        ident = package_identical(c, "poi")
        if ident is not None: checks["byte_identical_to_published_package"] = ident
        return checks, {"facilities_in_window": prof["network"]["facilities_in_window"], "network_unique": prof["network"]["unique_facilities_in_network_half_mile_union"]}
    record("poi_stage", s_poi)

    summary = {"passed": all(v["passed"] for v in results.values()), "scenarios": results,
               "interpreter": PY, "copies_base": str(base), "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "scripts_under_test": {p: sha(ROOT / p) for p in ["scripts/build_miami_station_master.py", "scripts/build_miami_station_zoning_profile.py",
                                                                    "scripts/build_miami_demography.py", "scripts/build_miami_jobs.py", "scripts/miami_v2_common.py",
                                                                    "scripts/miami_readiness.py", "scripts/build_all_miami.py"]},
               "method": "every scenario ran in an isolated copy under copies_base; the tree under test was only read"}
    if a.out: save(a.out, summary); print(f"results -> {a.out}")
    if not a.keep: shutil.rmtree(base, ignore_errors=True)
    print("ALL PASS" if summary["passed"] else "SOME FAILED"); sys.exit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
