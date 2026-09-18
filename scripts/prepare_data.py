"""Read the downloaded public sources and create auditable JSON, using stdlib only.

This is a preparation CLI, not an integration into the user's unidentified app.
VISTA outputs are survey estimates at their supported geography, never grid demand.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISTA_URL = "https://opendata.transport.vic.gov.au/dataset/victorian-integrated-survey-of-travel-and-activity-vista"
ABS_URL = "https://www.abs.gov.au/census/find-census-data/quickstats/2021/SAL22757"
WEIGHT = "trippoststratweight"
REPLICATES = [f"{WEIGHT}_GROUP_{i}" for i in range(1, 11)]


class TableReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def number(value, field):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Missing or invalid {field}: {value!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Non-finite or negative {field}: {value!r}")
    return result


def day_factor(day_type):
    # Explanatory document, printed p7 / PDF p8. Do not divide again by sample days.
    return {"All": 1.0, "Weekday": 7 / 5, "Weekend": 7 / 2}[day_type]


def ratio(numerator, denominator):
    return numerator / denominator if denominator > 0 else None


def logistic(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    ex = math.exp(value)
    return ex / (1 + ex)


def logit_jackknife_ci(point, replicates):
    """VISTA's ten-group logit interval, document printed p8 / PDF p9."""
    if len(replicates) != 10:
        raise ValueError("VISTA requires all ten replicate estimates")
    if any(p is None or not 0 < p < 1 for p in [point, *replicates]):
        return {"interval_95": None, "reason": "Undefined logit or zero denominator; no artificial epsilon added"}
    transform = lambda p: math.log(p / (1 - p))
    center = transform(point)
    variance = 9 / 10 * sum((transform(p) - center) ** 2 for p in replicates)
    se = math.sqrt(variance)
    return {"interval_95": [logistic(center - 2.26 * se), logistic(center + 2.26 * se)],
            "method": "VISTA ten-group jackknife logit, t multiplier 2.26"}


def read_records(path, id_field, required):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(required) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        rows = list(reader)
    ids = [r[id_field] for r in rows]
    if any(not key for key in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{path.name}: empty or duplicate {id_field}")
    return rows


def weighted_proportion(rows, predicate):
    result = []
    for column in [WEIGHT, *REPLICATES]:
        denominator = math.fsum(number(r[column], column) for r in rows)
        numerator = math.fsum(number(r[column], column) for r in rows if predicate(r))
        result.append(ratio(numerator, denominator))
    return {"value": result[0], "replicate_estimates": result[1:],
            **logit_jackknife_ci(result[0], result[1:])}


def abs_observations(path):
    html = path.read_text(encoding="utf-8")
    if "SAL22757" not in html or "West Melbourne" not in html:
        raise ValueError("Expected the verified West Melbourne SAL22757 source")
    parser = TableReader()
    parser.feed(html)

    def find(label, width):
        found = [r for r in parser.rows if len(r) == width and r[0] == label]
        if len(found) != 1:
            raise ValueError(f"Expected one ABS row for {label!r}, got {len(found)}")
        return found[0]

    population = int(find("People", 2)[1].replace(",", ""))
    weekly = int(find("Median weekly household income", 2)[1].replace("$", "").replace(",", ""))
    income_row = find("More than $3,000 total household weekly income (a)", 7)
    share = number(income_row[2], "household income share") / 100
    common = {"source_url": ABS_URL, "source_year": 2021, "geography_id": "SAL22757",
              "geography_type": "Suburbs and Localities", "geography_name": "West Melbourne",
              "retrieved_on": "2026-09-11", "spatial_scope": "entire published SAL, not a station catchment",
              "method": "extracted from published ABS table", "status": "published_census_statistic"}
    return {"example_only": True, "production_region_confirmed": False,
            "note": "West Melbourne locality is not the whole western Melbourne corridor. ABS applies small random adjustments.",
            "observations": [
                {**common, "metric": "resident_population", "value": population, "unit": "persons",
                 "population_basis": "place of usual residence"},
                {**common, "metric": "median_weekly_household_income", "value": weekly, "unit": "AUD/household/week",
                 "population_basis": "households under ABS income definition", "price_basis": "2021 nominal AUD"},
                {**common, "metric": "annual_equivalent_of_weekly_household_median", "value": weekly * 52,
                 "unit": "AUD/household/year", "status": "derived", "method": "weekly median multiplied by 52",
                 "note": "Not an independently observed annual-income median; no inflation or FX adjustment"},
                {**common, "metric": "household_income_above_threshold_share", "value": share, "unit": "fraction",
                 "threshold": {"operator": ">", "value": 3000, "currency": "AUD", "period": "week", "basis": "household"},
                 "denominator": "occupied private dwellings, excluding visitor-only and other non-classifiable households, and partial/all income not stated",
                 "population_basis": "place of enumeration", "note": "Not a share of persons, nor a Meta employee eligibility measure"}],
            "unavailable": {"jobs_to_employed_residents_ratio": None, "commute_peak_share": None,
                            "reason": "Not supplied by these extracted ABS rows"}}


def vista_analysis(trips, journeys):
    for r in trips:
        if r["dayType"] not in ("Weekday", "Weekend"):
            raise ValueError("Unexpected VISTA dayType")
        for key in [WEIGHT, *REPLICATES, "startime", "starthour"]:
            number(r[key], key)
        if int(number(r["startime"], "startime") // 60) != int(number(r["starthour"], "starthour")):
            raise ValueError("Source start minute / hour mismatch")
    weekday = [r for r in trips if r["dayType"] == "Weekday" and r["homeregion_ASGS"] == "Greater Melbourne"]
    if not weekday:
        raise ValueError("No matching Greater Melbourne weekday observations")
    hourly = defaultdict(list)
    for r in weekday:
        hourly[int(r["starthour"])].append(r)
    profile = []
    total = math.fsum(number(r[WEIGHT], WEIGHT) for r in weekday) * day_factor("Weekday")
    for hour, rows in sorted(hourly.items()):
        expanded = math.fsum(number(r[WEIGHT], WEIGHT) for r in rows) * day_factor("Weekday")
        profile.append({"service_day_hour": hour, "sample_trips": len(rows),
                        "estimated_person_trips_in_hour_per_average_weekday": expanded,
                        "share_of_all_weekday_trips": ratio(expanded, total)})
    jtw = [r for r in journeys if r["dayType"] == "Weekday" and r["homeregion_ASGS"] == "Greater Melbourne"
           and r["start_loc"] == "FROM_HOME" and r["end_loc"] == "TO_WORK"]
    for r in journeys:
        number(r["journey_weight"], "journey_weight")
        number(r["start_time"], "start_time")
    peak = [r for r in jtw if 420 <= float(r["start_time"]) < 540]
    jtw_total = math.fsum(number(r["journey_weight"], "journey_weight") for r in jtw) * day_factor("Weekday")
    jtw_peak = math.fsum(number(r["journey_weight"], "journey_weight") for r in peak) * day_factor("Weekday")
    pt = weighted_proportion(weekday, lambda r: r["linkmode"] in {"Train", "Tram", "Public Bus"})
    return {"source_url": VISTA_URL, "source_period": "FY2024-2025", "retrieved_on": "2026-09-11",
            "status": "weighted_survey_estimate", "license": "CC BY 4.0, State of Victoria / DTP",
            "scope": "Trips made by surveyed Greater Melbourne residents; not all trips within a western corridor",
            "timezone": "Australia/Melbourne", "raw_trip_records": len(trips), "raw_journey_to_work_records": len(journeys),
            "weekday_trip_sample_size": len(weekday), "weekday_distinct_sample_persons": len({r['persid'] for r in weekday}),
            "weekday_weight_scale": day_factor("Weekday"), "estimated_all_purpose_trips_per_average_weekday": total,
            "hourly_profile": profile,
            "public_transport_main_mode_share": {**pt, "definition": "Train, Tram or Public Bus as longest-distance main mode, divided by all weekday trips; excludes School Bus"},
            "commute_departure_share_0700_0900": {"value": ratio(jtw_peak, jtw_total), "unit": "fraction",
                "numerator": "home-to-work journeys departing 07:00 inclusive to 09:00 exclusive",
                "denominator": "all sampled-day home-to-work journeys by Greater Melbourne residents on weekdays",
                "sample_journeys": len(jtw), "sample_journeys_in_peak": len(peak),
                "estimated_journeys_per_average_weekday": jtw_total, "estimated_peak_journeys_per_average_weekday": jtw_peak,
                "interval_95": None, "interval_unavailable_reason": "Journey table has one weight and no ten replicate columns; do not borrow unrelated trip weights",
                "assumption": "07:00-09:00 is this demonstration's chosen window, not a universal peak definition"},
            "limitations": ["Public OD geography is LGA; these records have no point or grid coordinates.",
                "Do not scatter LGA survey totals into fine cells and label them observed demand.",
                "Hours 24-27 are retained as extended service-day hours; no modulo-24 reassignment.",
                "Trips, travel legs and journeys overlap conceptually; their totals must not be added.",
                "Main mode is distance-based in 2021-26, unlike the earlier hierarchy-based series.",
                "Survey sample rows are not population counts; weighted totals are not observed boardings.",
                "This regional profile is not a local station forecast or a globally reusable default."]}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    raw = ROOT / "raw"
    trips = read_records(raw / "vista_trips_2024_2025.csv", "tripid", ["tripid", "persid", "dayType", "homeregion_ASGS", "startime", "starthour", "linkmode", WEIGHT, *REPLICATES])
    journeys = read_records(raw / "vista_journey_to_work_2024_2025.csv", "jtwid", ["jtwid", "dayType", "homeregion_ASGS", "start_loc", "end_loc", "start_time", "journey_weight"])
    abs_data = abs_observations(raw / "abs_west_melbourne_2021.html")
    vista = vista_analysis(trips, journeys)
    save(ROOT / "data/abs_west_melbourne_2021.json", abs_data)
    save(ROOT / "data/vista_melbourne_2024_2025.json", vista)
    hashes = [{"file": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size,
               "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(raw.iterdir()) if p.is_file() and p.suffix != '.txt']
    save(ROOT / "data/raw_manifest.json", {"retrieved_on": "2026-09-11", "files": hashes})
    print(json.dumps({"raw_trips": len(trips), "raw_journeys": len(journeys),
                      "weekday_trip_sample": vista['weekday_trip_sample_size'],
                      "commute_departure_share_0700_0900": vista['commute_departure_share_0700_0900'],
                      "public_transport_main_mode_share": vista['public_transport_main_mode_share'],
                      "abs_values": [x['value'] for x in abs_data['observations']]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
