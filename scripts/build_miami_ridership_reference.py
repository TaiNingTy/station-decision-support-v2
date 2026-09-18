#!/usr/bin/env python3
"""Miami · observed Metromover boardings by station — V2 step 7a, stage `ridership_reference`.

Source: DTPW monthly Ridership Technical Reports (raw/miami/2026-09-17/dtpw_rtr/, ten reports 2025-10..2026-07), table
"METROMOVER MONTHLY AND AVERAGE DAILY BOARDINGS BY STATION". Per station: the monthly series (average weekday /
Saturday / Sunday boardings, monthly total), the ten-month mean of average weekday boardings, the latest month, and the
station's share of the system. Station names are mapped to the station master through an explicit crosswalk; three
stations were renamed (same location) and are flagged for confirmation.
What these numbers are: published boardings (entries) per average day of the CURRENT Metromover. What they are not:
trips, origin-destination pairs, alightings, peak-hour flows, or demand for a new service. They serve as an observed
REFERENCE for the scenario chain (scale and station-share shape), never as a calibration target.
Publishes ridership_reference/pkg-<id>/ atomically (R3); readiness by scripts/miami_readiness.py (R2).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403
from fetch_miami_ridership_reports import parse_metromover_table, MONTHS   # same parser as the acquisition validation

STAGE = "ridership_reference"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_ridership_reference.json", "ridership_reference_validation.json"]
RAW17 = ROOT / "raw/miami/2026-09-17"
STATION_MASTER = DATA / "station_master.geojson"
# report name -> station master name; basis: same_name, or renamed_station_same_location (confirm with the owner)
CROSSWALK = {"School Board": ("School Board", "same_name"), "Omni": ("Adrienne Arsht Center", "renamed_station_same_location"),
             "Museum Park": ("Museum Park", "same_name"), "Eleventh Street": ("Eleventh Street", "same_name"),
             "Park West": ("Miami Worldcenter", "renamed_station_same_location"), "Freedom Tower": ("Freedom Tower", "same_name"),
             "College North": ("College North", "same_name"), "Wilkie D. Ferguson": ("Wilkie D. Ferguson, Jr.", "same_name_punctuation"),
             "Government Center": ("Government Center", "same_name"), "College/Bayside": ("College Bayside", "same_name_punctuation"),
             "First Street": ("First Street", "same_name"), "Bayfront Park": ("Bayfront Park", "same_name"), "Knight Center": ("Knight Center", "same_name"),
             "Miami Avenue": ("Miami Avenue", "same_name"), "Third Street": ("Third Street", "same_name"), "Riverwalk": ("Riverwalk", "same_name"),
             "Fifth Street": ("Fifth Street", "same_name"), "Eighth Street": ("Brickell City Centre", "renamed_station_same_location"),
             "Tenth Street": ("Tenth Street Promenade", "same_name_extended"), "Brickell": ("Brickell", "same_name"), "Financial District": ("Financial District", "same_name")}
SEMANTICS = {"provenance_class": "observed", "data_nature": "measured", "source": "Miami-Dade DTPW monthly Ridership Technical Reports (published boardings)",
             "unit": "boardings (entries) per average day of the stated day type; monthly totals are all days",
             "is_trips": False, "is_od": False, "is_alightings": False, "is_peak_hour": False, "is_demand_for_new_service": False,
             "counting_note": "as published by DTPW; the reports state that average ridership is computed only for days and stations with nontrivial reported data; "
                              "the counting method is not described in the table",
             "role": "observed REFERENCE for scale and station-share shape; NOT a calibration target and NOT the demand of the scenarios (which cover internal links only)"}

environment = lock_gate()
raw_manifest = load(RAW17 / "source_manifest.json"); raw_by_file = {s["file"]: s for s in raw_manifest["sources"]}
files = [f"dtpw_rtr/{m}-monthly-ridership-report.pdf" for m in MONTHS]
for f in files:
    if sha_file(RAW17 / f) != raw_by_file[f]["sha256"]: raise SystemExit(f"HALT: {f} sha256 != raw source_manifest.json")
consumed_inputs = [consumed_entry("raw_source_manifest", RAW17 / "source_manifest.json"), consumed_entry("station_master", STATION_MASTER)] + [consumed_entry(f, RAW17 / f) for f in files]
stations = load(STATION_MASTER)["features"]; id_by_name = {f["properties"]["name"]: f["properties"]["station_id"] for f in stations}
if len(stations) != 21: raise SystemExit("HALT: expected 21 stations")

monthly = {}   # month -> {station master id: row}
system = {}    # month -> TOTAL row
pages = {}
unmapped, missing_master = set(), set(id_by_name)
for m, f in zip(MONTHS, files):
    t = parse_metromover_table(RAW17 / f)
    if not t: raise SystemExit(f"HALT: Metromover station table not found in {f}")
    pages[m] = t["page"]; monthly[m] = {}
    for name, row in t["rows"].items():
        if name.upper() == "TOTAL": system[m] = row; continue
        if name not in CROSSWALK: unmapped.add(name); continue
        master, basis = CROSSWALK[name]; pid = id_by_name.get(master)
        if pid is None: unmapped.add(name); continue
        monthly[m][pid] = {**row, "report_station_name": name, "mapping_basis": basis}; missing_master.discard(master)
if unmapped or missing_master: raise SystemExit(f"HALT: crosswalk incomplete: unmapped {sorted(unmapped)} / master without report row {sorted(missing_master)}")

ids = sorted(id_by_name.values()); latest = MONTHS[-1]
out = []
for pid in ids:
    series = {m: {k: monthly[m][pid][k] for k in ("avg_weekday", "avg_saturday", "avg_sunday", "total_monthly")} for m in MONTHS}
    wk = [monthly[m][pid]["avg_weekday"] for m in MONTHS]
    name = next(f["properties"]["name"] for f in stations if f["properties"]["station_id"] == pid)
    out.append({"station_id": pid, "name": name, "report_station_name": monthly[latest][pid]["report_station_name"], "mapping_basis": monthly[latest][pid]["mapping_basis"],
                "mapping_confirmed_by_owner": False, **SEMANTICS,
                "avg_weekday_boardings_10_month_mean": r2(sum(wk) / len(wk)), "avg_weekday_boardings_min_max": [min(wk), max(wk)],
                "avg_weekday_boardings_latest": {"month": latest, "value": monthly[latest][pid]["avg_weekday"]},
                "share_of_system_avg_weekday_10_month_mean": None, "monthly_series": series,
                "evidence_source": {"files": files, "table": "METROMOVER MONTHLY AND AVERAGE DAILY BOARDINGS BY STATION", "pages_by_month": pages}})
sys_wk = [system[m]["avg_weekday"] for m in MONTHS]; sys_mean = sum(sys_wk) / len(sys_wk)
sum_station_means = sum(s["avg_weekday_boardings_10_month_mean"] for s in out)
for s in out: s["share_of_system_avg_weekday_10_month_mean"] = r6(s["avg_weekday_boardings_10_month_mean"] / sum_station_means)
system_block = {"avg_weekday_boardings_10_month_mean": r2(sys_mean), "avg_weekday_boardings_by_month": dict(zip(MONTHS, sys_wk)),
                "sum_of_station_means": r2(sum_station_means), "total_monthly_boardings_by_month": {m: system[m]["total_monthly"] for m in MONTHS},
                "avg_saturday_boardings_10_month_mean": r2(sum(system[m]["avg_saturday"] for m in MONTHS) / len(MONTHS)),
                "avg_sunday_boardings_10_month_mean": r2(sum(system[m]["avg_sunday"] for m in MONTHS) / len(MONTHS)),
                "window": {"from": MONTHS[0], "to": MONTHS[-1], "months": len(MONTHS)}, **SEMANTICS}

val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "months": len(MONTHS), "stations": len(out), "all_21_stations_mapped_every_month": all(len(monthly[m]) == 21 for m in MONTHS),
       "station_sums_match_published_totals_within_3": all(abs(sum(monthly[m][p]["avg_weekday"] for p in ids) - system[m]["avg_weekday"]) <= 3 for m in MONTHS),
       "renamed_stations_flagged": [s["station_id"] for s in out if s["mapping_basis"] == "renamed_station_same_location"],
       "shares_sum_to_one": abs(sum(s["share_of_system_avg_weekday_10_month_mean"] for s in out) - 1.0) < 1e-4,
       "no_zero_station": all(s["avg_weekday_boardings_10_month_mean"] > 0 for s in out),
       "scope_statement": "PASS means the published tables were read consistently and mapped one-to-one to the 21 stations. The values are boardings of the "
                          "current Metromover, not trips, not OD, not peak-hour and not the demand of the scenarios."}
ok = val["all_21_stations_mapped_every_month"] and val["station_sums_match_published_totals_within_3"] and val["shares_sum_to_one"] and val["no_zero_station"]
if os.environ.get("RIDERSHIP_REFERENCE_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

config = {"window": MONTHS, "crosswalk": {k: {"station_master_name": v[0], "basis": v[1]} for k, v in CROSSWALK.items()}, "table": "METROMOVER MONTHLY AND AVERAGE DAILY BOARDINGS BY STATION",
          "aggregation": "arithmetic mean of the monthly average-weekday values over the window; shares from the sum of station means"}
config_sha = sha_obj(config)
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_ridership_reference.json", {"schema_version": "miami-station-ridership-reference/1.0", "built_on": BUILT_ON, "config_sha256": config_sha, **SEMANTICS,
     "config": config, "environment": environment, "system": system_block, "stations": out})
dump(STAGING / "ridership_reference_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-ridership-reference-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": [],
            "code": code_entries(Path(__file__), ROOT / "scripts/fetch_miami_ridership_reports.py", ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment,
            "method_summary": "DTPW monthly Ridership Technical Reports parsed (pypdf text) into per-station average weekday/Saturday/Sunday boardings and monthly totals over "
                              "ten months; mapped to the 21 stations by an explicit crosswalk; observed reference only",
            "contract": "V2_站点输入包字段契约.md §8 (ridership_baseline)",
            "publish_policy": "content-addressed immutable package dir ridership_reference/pkg-<id>; readers resolve ridership_reference_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} months={len(MONTHS)} "
      f"system_avg_weekday_mean={system_block['avg_weekday_boardings_10_month_mean']} renamed_flagged={val['renamed_stations_flagged']}")
