#!/usr/bin/env python3
"""Unified, ORDERED rebuild of the Miami data foundation.

    station_master -> spatial_join -> demography -> jobs -> service_baseline -> ridership_reference -> poi -> input_package -> scenarios -> config -> rules -> readiness --check
    (walk_model is written but paused; see the STAGES comment)

Runs every stage with the SAME interpreter that launched this script and stops at the first failure.
  * Each stage publishes only its own immutable products + its own manifest (F3).
  * gis_data_readiness.json is DERIVED by scripts/miami_readiness.py — its single writer (R2) — which decides
    freshness from the inputs the spatial join actually consumed: station_master, study_window, raw zoning (R1).
  * The spatial join publishes a whole content-addressed package and switches one pointer atomically (R3);
    it publishes nothing unless its validation passed (F1).

    python3 scripts/build_all_miami.py                          # full ordered rebuild
    python3 scripts/build_all_miami.py --skip-station_master    # downstream only (upstream unchanged)
"""
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = [("station_master", ["scripts/build_miami_station_master.py"]),
          ("spatial_join", ["scripts/build_miami_station_zoning_profile.py"]),
          ("demography", ["scripts/build_miami_demography.py"]),      # V2 step 3: ACS 2020-2024 block groups (needs raw/miami/2026-09-15)
          ("jobs", ["scripts/build_miami_jobs.py"]),                  # V2 step 3: LODES 8 2023 blocks (consumes the demography package)
          ("service_baseline", ["scripts/build_miami_service_baseline.py"]),  # V2 step 5a: GTFS weekday timetable per station
          ("ridership_reference", ["scripts/build_miami_ridership_reference.py"]),  # V2 step 7a: observed DTPW boardings by station (reference only)
          ("poi", ["scripts/build_miami_poi.py"]),                    # V2 step 7b: schools / clinics / grocery / parks (optional layer for AI)
          # ("walk_model", ["scripts/build_miami_walk_model.py"]),    # V2 step 7c PAUSED 2026-09-17: script + raw OSM exist, but the isochrone build is too slow (>10 min); not wired until optimised
          ("input_package", ["scripts/build_miami_input_package.py"]),  # V2 step 4: per-station input package pinned to the layers above
          ("scenarios", ["scripts/build_miami_scenarios.py"]),        # V2 step 5b: low/medium/high peak-hour chain with provenance tags
          ("config", ["scripts/build_miami_config.py"]),              # V2 step 6: PRT berths / modules / footprint per station per scenario
          ("rules", ["scripts/build_miami_rules.py"]),                # V2 step 9a: versioned rule pack evaluated over the packages (citable rule_result_id)
          ("readiness_check", ["scripts/miami_readiness.py", "--check"])]
skip = {a[len("--skip-"):] for a in sys.argv[1:] if a.startswith("--skip-")}

print(f"interpreter: {sys.executable}")
for name, cmd in STAGES:
    if name in skip:
        print(f"[{name}] skipped"); continue
    print(f"\n=== [{name}] {' '.join(cmd)} ===")
    r = subprocess.run([sys.executable, str(ROOT / cmd[0]), *cmd[1:]], cwd=ROOT)
    if r.returncode != 0:
        print(f"[{name}] FAILED (exit {r.returncode}) — stopping; later stages NOT run"); sys.exit(r.returncode)
    print(f"[{name}] OK")
print("\nall stages OK")
