#!/usr/bin/env python3
"""Miami · scheduled service baseline — V2 step 5a, stage `service_baseline` (GTFS stop_times, Metromover routes).

Contract §8: `service_baseline` was `derivable_from_gtfs`; this stage derives it. Per station, for the feed's weekday
service: scheduled departures by clock hour and by route, first/last departure, departures per hour and implied
headway per period. Scheduled ≠ operated; departures ≠ capacity ≠ ridership — the values are an administrative record
of the timetable (data_nature administrative_record, provenance_class derived because they are aggregated from
stop_times through the stop→station crosswalk).
Publishes service_baseline/pkg-<id>/ atomically (R3); readiness by scripts/miami_readiness.py (R2).
"""
import csv, io, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

STAGE = "service_baseline"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_service_baseline.json", "service_baseline_validation.json"]
GTFS = ROOT / "raw/miami/2026-09-11/google_transit.zip"
INVENTORY = ROOT / "data/miami/2026-09-11/inventory.json"
CROSSWALK = DATA / "stop_to_station_crosswalk.json"
STATION_MASTER = DATA / "station_master.geojson"
PERIODS = {"early": (5, 7), "am_peak": (7, 9), "midday": (9, 16), "pm_peak": (16, 19), "evening": (19, 24)}   # [start, end) clock hours
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
SEMANTICS = {"provenance_class": "derived", "data_nature": "administrative_record", "source": "GTFS static feed (Miami-Dade Transit), Metromover routes",
             "is_operated_service": False, "is_capacity": False, "is_ridership": False,
             "note": "scheduled departures aggregated from stop_times through the stop-to-station crosswalk; the timetable is not evidence of operated "
                     "service, vehicle capacity or passenger demand"}

environment = lock_gate()
inv = load(INVENTORY)
if sha_file(GTFS) != inv["archive_sha256"]: raise SystemExit("HALT: GTFS archive sha256 != data/miami/2026-09-11/inventory.json")
consumed_inputs = [consumed_entry("gtfs_archive", GTFS), consumed_entry("gtfs_inventory", INVENTORY), consumed_entry("stop_to_station_crosswalk", CROSSWALK),
                   consumed_entry("station_master", STATION_MASTER)]
cw = load(CROSSWALK)["records"]; stop_station = {r["gtfs_stop_id"]: r["physical_station_id"] for r in cw}
stations = load(STATION_MASTER)["features"]; names = {f["properties"]["station_id"]: f["properties"]["name"] for f in stations}
ids = sorted(names)

z = zipfile.ZipFile(GTFS)
rd = lambda n: list(csv.DictReader(io.TextIOWrapper(z.open(n), encoding="utf-8-sig")))
routes = {r["route_id"]: r for r in rd("routes.txt") if "METROMOVER" in r["route_long_name"].upper()}
trips = {t["trip_id"]: t for t in rd("trips.txt") if t["route_id"] in routes}
calendar = rd("calendar.txt"); service_trip_counts = {}
for t in trips.values(): service_trip_counts[t["service_id"]] = service_trip_counts.get(t["service_id"], 0) + 1
weekday_services = [c for c in calendar if c["service_id"] in service_trip_counts and all(c[d] == "1" for d in WEEKDAYS)]
if not weekday_services: raise SystemExit("HALT: no calendar service runs Monday-Friday for the Metromover routes")
weekday = max(weekday_services, key=lambda c: service_trip_counts[c["service_id"]])
exceptions = [d for d in rd("calendar_dates.txt") if d["service_id"] == weekday["service_id"]] if "calendar_dates.txt" in z.namelist() else []
weekday_trips = {tid for tid, t in trips.items() if t["service_id"] == weekday["service_id"]}


def parse_time(s):
    h, m, sec = s.strip().split(":"); return int(h), int(m), int(sec)


rows_total = rows_weekday = 0; unmapped = set()
dep = {pid: {"by_hour": {}, "by_route_hour": {r: {} for r in routes}, "first": None, "last": None, "stop_ids": set()} for pid in ids}
for r in csv.DictReader(io.TextIOWrapper(z.open("stop_times.txt"), encoding="utf-8-sig")):
    if r["trip_id"] not in trips: continue
    rows_total += 1
    if r["trip_id"] not in weekday_trips: continue
    rows_weekday += 1
    pid = stop_station.get(r["stop_id"])
    if pid is None: unmapped.add(r["stop_id"]); continue
    h, m, s = parse_time(r["departure_time"]); t = h * 3600 + m * 60 + s; rid = trips[r["trip_id"]]["route_id"]
    d = dep[pid]; d["by_hour"][h] = d["by_hour"].get(h, 0) + 1; d["by_route_hour"][rid][h] = d["by_route_hour"][rid].get(h, 0) + 1
    d["first"] = t if d["first"] is None else min(d["first"], t); d["last"] = t if d["last"] is None else max(d["last"], t); d["stop_ids"].add(r["stop_id"])
fmt = lambda t: None if t is None else f"{t // 3600:02d}:{(t % 3600) // 60:02d}"
out = []
for pid in ids:
    d = dep[pid]; periods = {}
    for name, (a, b) in PERIODS.items():
        hrs = b - a; n = sum(v for h, v in d["by_hour"].items() if a <= h < b)
        by_route = {routes[r]["route_short_name"]: sum(v for h, v in d["by_route_hour"][r].items() if a <= h < b) for r in routes}
        periods[name] = {"hours": [a, b], "scheduled_departures": n, "departures_per_hour": round(n / hrs, 2),
                         "implied_headway_min_all_routes": (round(60.0 * hrs / n, 2) if n else None),
                         "by_route": {k: {"scheduled_departures": v, "departures_per_hour": round(v / hrs, 2), "implied_headway_min": (round(60.0 * hrs / v, 2) if v else None)} for k, v in by_route.items()},
                         "value_status": "value" if n else "confirmed_zero"}
    out.append({"station_id": pid, "name": names[pid], "gtfs_stop_ids_observed": sorted(d["stop_ids"]), **SEMANTICS,
                "day_type": {"service_id": weekday["service_id"], "days": WEEKDAYS, "valid_from": weekday["start_date"], "valid_to": weekday["end_date"], "calendar_exceptions": len(exceptions)},
                "scheduled_departures_weekday_total": sum(d["by_hour"].values()), "first_departure": fmt(d["first"]), "last_departure": fmt(d["last"]),
                "by_hour": {str(h): d["by_hour"][h] for h in sorted(d["by_hour"])},
                "by_route_hour": {routes[r]["route_short_name"]: {str(h): v for h, v in sorted(d["by_route_hour"][r].items())} for r in routes},
                "periods": periods,
                "routes": {r["route_short_name"]: r["route_long_name"] for r in routes.values()},
                "direction_note": "loop routes; the feed does not state platform/direction per stop — headways are per route as scheduled at the station's stops"})

val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "stations": len(out), "metromover_routes": {r["route_short_name"]: r["route_long_name"] for r in routes.values()},
       "weekday_service": {"service_id": weekday["service_id"], "trips": service_trip_counts[weekday["service_id"]], "calendar_exceptions": len(exceptions)},
       "stop_times_rows_metromover": rows_total, "stop_times_rows_weekday": rows_weekday,
       "all_weekday_stops_mapped_to_stations": not unmapped, "unmapped_stop_ids": sorted(unmapped),
       "departures_reconcile_with_stop_times": sum(s["scheduled_departures_weekday_total"] for s in out) == rows_weekday - 0,
       "every_station_has_am_peak_departures": all(s["periods"]["am_peak"]["scheduled_departures"] > 0 for s in out),
       "every_station_served_by_both_routes_in_am_peak": all(all(v["scheduled_departures"] > 0 for v in s["periods"]["am_peak"]["by_route"].values()) for s in out),
       "scope_statement": "PASS means the timetable aggregation reconciles with the feed. Scheduled departures are not operated service, capacity or ridership."}
ok = val["all_weekday_stops_mapped_to_stations"] and val["departures_reconcile_with_stop_times"] and val["every_station_has_am_peak_departures"] and len(out) == 21
if os.environ.get("SERVICE_BASELINE_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

config = {"periods": PERIODS, "weekday_rule": "calendar service with all Monday-Friday flags, most trips", "routes_rule": "route_long_name contains METROMOVER",
          "headway_definition": "60 × hours in period ÷ scheduled departures at the station's stops in the period (per route and all routes)"}
config_sha = sha_obj(config)
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_service_baseline.json", {"schema_version": "miami-station-service-baseline/1.0", "built_on": BUILT_ON, "config_sha256": config_sha, **SEMANTICS,
     "gtfs_archive_sha256": inv["archive_sha256"], "config": config, "environment": environment, "stations": out})
dump(STAGING / "service_baseline_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-service-baseline-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": [],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment,
            "method_summary": "GTFS weekday stop_times aggregated per station (via the stop-to-station crosswalk) into departures by hour/route and period headways",
            "contract": "V2_站点输入包字段契约.md §8 (service_baseline)",
            "publish_policy": "content-addressed immutable package dir service_baseline/pkg-<id>; readers resolve service_baseline_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} stations={len(out)} "
      f"weekday_service={weekday['service_id']} rows_weekday={rows_weekday} am_peak_departures_station01={out[0]['periods']['am_peak']['scheduled_departures']}")
