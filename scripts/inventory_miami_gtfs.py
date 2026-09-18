"""Read-only GTFS inventory and derived Metromover GIS samples; no station merging."""
import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--service-date", default="2026-09-14")
    args = parser.parse_args()
    day = datetime.strptime(args.service_date, "%Y-%m-%d").date()
    date_key = day.strftime("%Y%m%d")
    day_field = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[day.weekday()]
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = {
        "source_archive": args.archive.name,
        "source_url": "https://www.miamidade.gov/transit/googletransit/current/google_transit.zip",
        "source_download_date": "2026-09-11",
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "archive_bytes": args.archive.stat().st_size,
        "service_date": args.service_date,
        "analysis_type": "schedule_and_geometry_inventory_not_observed_ridership",
        "physical_station_mapping_status": "NOT_COMPLETED",
        "files": {},
    }
    with zipfile.ZipFile(args.archive) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Archive CRC failure: {bad}")
        members = {Path(n).name: n for n in archive.namelist() if not n.endswith("/")}

        def rows(name):
            member = members[name]
            with archive.open(member) as stream:
                reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
                count = 0
                fields = reader.fieldnames
                for row in reader:
                    count += 1
                    yield row
            inventory["files"][name] = {
                "row_count": count,
                "fields": fields,
                "uncompressed_bytes": archive.getinfo(member).file_size,
            }

        agencies = list(rows("agency.txt"))
        calendars = list(rows("calendar.txt"))
        exceptions = list(rows("calendar_dates.txt")) if "calendar_dates.txt" in members else []
        active_services = {r["service_id"] for r in calendars if r["start_date"] <= date_key <= r["end_date"] and r[day_field] == "1"}
        for row in exceptions:
            if row["date"] == date_key:
                if row["exception_type"] == "1":
                    active_services.add(row["service_id"])
                elif row["exception_type"] == "2":
                    active_services.discard(row["service_id"])
        routes = list(rows("routes.txt"))
        mover_routes = {r["route_id"]: r for r in routes if "METROMOVER" in r["route_long_name"].upper()}
        stop_rows = list(rows("stops.txt"))
        stops = {r["stop_id"]: r for r in stop_rows}
        trip_rows = list(rows("trips.txt"))
        all_trips = {r["trip_id"]: r for r in trip_rows}
        mover_trips = {k: r for k, r in all_trips.items() if r["route_id"] in mover_routes}
        active_trips = {k for k, r in mover_trips.items() if r["service_id"] in active_services}
        stop_usage = defaultdict(lambda: {"all_feed_stop_events": 0, "selected_day_stop_events": 0, "route_ids": set(), "service_ids": set()})
        per_trip_counts = Counter()
        time_count = 0
        extended_time_count = 0
        invalid_time_count = 0
        missing_stop_refs = set()
        missing_trip_refs = set()
        for row in rows("stop_times.txt"):
            tid = row["trip_id"]
            if tid not in all_trips:
                missing_trip_refs.add(tid)
            if row["stop_id"] not in stops:
                missing_stop_refs.add(row["stop_id"])
            if tid not in mover_trips:
                continue
            sid = row["stop_id"]
            item = stop_usage[sid]
            item["all_feed_stop_events"] += 1
            item["selected_day_stop_events"] += int(tid in active_trips)
            item["route_ids"].add(mover_trips[tid]["route_id"])
            item["service_ids"].add(mover_trips[tid]["service_id"])
            per_trip_counts[tid] += 1
            for field in ("arrival_time", "departure_time"):
                if not row[field]:
                    continue
                time_count += 1
                try:
                    h, m, s = map(int, row[field].split(":"))
                    if h < 0 or not (0 <= m < 60 and 0 <= s < 60):
                        raise ValueError("Invalid GTFS time")
                    extended_time_count += int(h >= 24)
                except ValueError:
                    invalid_time_count += 1

        shape_ids = {r["shape_id"] for r in mover_trips.values() if r.get("shape_id")}
        active_shape_ids = {mover_trips[k]["shape_id"] for k in active_trips if mover_trips[k].get("shape_id")}
        shape_points = defaultdict(list)
        all_shape_ids = set()
        for row in rows("shapes.txt"):
            shape_id = row["shape_id"]
            all_shape_ids.add(shape_id)
            if shape_id in shape_ids:
                shape_points[shape_id].append((int(row["shape_pt_sequence"]), float(row["shape_pt_lon"]), float(row["shape_pt_lat"])))

        features = []
        groups = defaultdict(list)
        invalid_coordinates = []
        for sid, usage in sorted(stop_usage.items()):
            row = stops.get(sid)
            if row is None:
                continue
            props = {**row, **{k: sorted(v) if isinstance(v, set) else v for k, v in usage.items()}, "physical_station_id": None, "mapping_status": "UNREVIEWED", "geometry_role": "gtfs_stop_record"}
            try:
                lon, lat = float(row["stop_lon"]), float(row["stop_lat"])
                if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
                    raise ValueError("Invalid WGS84 coordinate")
                geometry = {"type": "Point", "coordinates": [lon, lat]}
            except ValueError:
                invalid_coordinates.append(sid)
                geometry = None
            features.append({"type": "Feature", "id": sid, "geometry": geometry, "properties": props})
            groups[row["stop_name"]].append({"stop_id": sid, "stop_lat": row["stop_lat"], "stop_lon": row["stop_lon"], "location_type": row["location_type"], "parent_station": row["parent_station"], "active_on_selected_service_date": usage["selected_day_stop_events"] > 0})

        shape_features = []
        for shape_id, points in sorted(shape_points.items()):
            points.sort()
            coords = [[lon, lat] for _, lon, lat in points]
            shape_features.append({"type": "Feature", "id": shape_id, "properties": {"shape_id": shape_id, "geometry_role": "scheduled_service_shape_not_surveyed_guideway", "active_on_selected_service_date": shape_id in active_shape_ids}, "geometry": {"type": "LineString", "coordinates": coords}})

        inventory.update({
            "agencies": agencies,
            "calendar_ranges": calendars,
            "selected_day_active_service_ids": sorted(active_services),
            "metromover": {
                "selection_method": "route_long_name contains METROMOVER, joined to trips and stop_times",
                "routes": list(mover_routes.values()),
                "trip_records_all_calendar_patterns": len(mover_trips),
                "trip_records_selected_service_date": len(active_trips),
                "stop_records_all_calendar_patterns": len(stop_usage),
                "stop_records_selected_service_date": sum(v["selected_day_stop_events"] > 0 for v in stop_usage.values()),
                "distinct_stop_name_strings": len(groups),
                "shape_records_all_calendar_patterns": len(shape_ids),
                "shape_records_selected_service_date": len(active_shape_ids),
                "stop_events_all_calendar_patterns": sum(v["all_feed_stop_events"] for v in stop_usage.values()),
                "stop_events_selected_service_date": sum(v["selected_day_stop_events"] for v in stop_usage.values()),
                "location_type_counts": dict(Counter(f["properties"]["location_type"] or "blank" for f in features)),
                "records_with_parent_station": sum(bool(f["properties"]["parent_station"]) for f in features),
                "nonblank_arrival_and_departure_time_fields": time_count,
                "time_fields_hour_24_or_above": extended_time_count,
                "invalid_time_fields": invalid_time_count,
                "stop_records_with_invalid_coordinates": invalid_coordinates,
            },
            "integrity": {
                "archive_crc": "PASS",
                "duplicate_stop_id_rows": len(stop_rows) - len(stops),
                "duplicate_trip_id_rows": len(trip_rows) - len(all_trips),
                "unknown_stop_ids_referenced_by_stop_times": sorted(missing_stop_refs),
                "unknown_trip_ids_referenced_by_stop_times": sorted(missing_trip_refs),
                "missing_metromover_shape_ids": sorted(shape_ids - all_shape_ids),
            },
            "limitations": [
                "GTFS stop IDs and service shapes are not a physical asset inventory.",
                "Published 21-station baseline has not yet been reconciled with these records.",
                "Stop-event and trip counts are scheduled supply, not passenger counts or observed operations.",
                "An active service calendar does not verify actual service on that date.",
                "No platform footprint, surveyed guideway, structural feasibility, ridership, or berth capacity is supplied by this inventory.",
                "Redistribution terms must be recorded before publishing bundled source data.",
            ],
        })
    write_json(args.output / "inventory.json", inventory)
    write_json(args.output / "metromover_stop_records.geojson", {"type": "FeatureCollection", "features": features})
    write_json(args.output / "metromover_service_shapes.geojson", {"type": "FeatureCollection", "features": shape_features})
    write_json(args.output / "metromover_name_groups.json", dict(sorted(groups.items())))
    print(json.dumps({"metromover": inventory["metromover"], "integrity": inventory["integrity"], "files": {k: v["row_count"] for k, v in inventory["files"].items()}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
