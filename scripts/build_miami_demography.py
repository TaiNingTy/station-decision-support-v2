#!/usr/bin/env python3
"""Miami · station demography profiles — V2 step 3, stage `demography` (ACS 2020-2024 5-year, block groups).

Contract: V2_站点输入包字段契约.md §2 (value envelope), §3 (indicators D01-D13, R01-R09), §6 (land-geometry shares,
MOE rules), §7 (missing states). Rules doc: 规则 1 (period estimates), 3 (overlap), 4 (medians, weights), 5 (units).

What it does
  * Rebuilds the 21 stations' imperial bands (1/8, 1/4, 1/2 mi) from station_master + the spatial-join package config
    and checks them against that package's published areas, so both layers use identical geometry.
  * Land geometry: TIGER 2020 P.L. blocks minus TIGER 2024 area hydrography (STRtree), for every block of every block
    group that touches the network half-mile union. Block-group land = union of its blocks' land.
  * Shares: block-group share in a target = Σ(block land ∩ target) / Σ(block land) over the block group's blocks
    (numerator and denominator from the same land geometry; denominator never clipped).
  * Counts: Σ(share × estimate); MOE = √Σ(share × MOE)²  (approximate sampling MOE only; excludes interpolation).
    Ratios: numerator and denominator aggregated separately, Census ratio approximation for the MOE.
    Median income: share-weighted B19001 brackets + linear interpolation; open top bracket → lower bound.
  * Per-station bands are non-exclusive; the network total is computed once on the union geometry (dedup).
  * Publishes an immutable package demography/pkg-<id>/ and switches demography_current.json atomically (R3);
    readiness is derived by scripts/miami_readiness.py (R2).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403
from shapely import make_valid

STAGE = "demography"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_demography_profile.json", "demography_evidence.json", "block_group_values.json",
                "block_land_geometry.json", "analysis_targets_26917.json", "land_geometry_report.json", "demography_validation.json"]
BAND_KEYS, BAND_LABELS = ["b1", "b2", "b3"], ["0-1/8 mi", "1/8-1/4 mi", "1/4-1/2 mi"]
LOW_INCOME_THRESHOLD_USD = 35000
INCOME_BRACKETS = [(2, 0, 10000), (3, 10000, 15000), (4, 15000, 20000), (5, 20000, 25000), (6, 25000, 30000), (7, 30000, 35000),
                   (8, 35000, 40000), (9, 40000, 45000), (10, 45000, 50000), (11, 50000, 60000), (12, 60000, 75000), (13, 75000, 100000),
                   (14, 100000, 125000), (15, 125000, 150000), (16, 150000, 200000), (17, 200000, None)]
COMMUTE = {"car_truck_van": "002", "drove_alone": "003", "carpooled": "004", "public_transportation": "010", "taxi_or_ride_hailing": "016",
           "motorcycle": "017", "bicycle": "018", "walked": "019", "other_means": "020", "worked_from_home": "021"}
DEPARTURE = {"002": "12:00 a.m. to 4:59 a.m.", "003": "5:00 a.m. to 5:29 a.m.", "004": "5:30 a.m. to 5:59 a.m.", "005": "6:00 a.m. to 6:29 a.m.",
             "006": "6:30 a.m. to 6:59 a.m.", "007": "7:00 a.m. to 7:29 a.m.", "008": "7:30 a.m. to 7:59 a.m.", "009": "8:00 a.m. to 8:29 a.m.",
             "010": "8:30 a.m. to 8:59 a.m.", "011": "9:00 a.m. to 9:59 a.m.", "012": "10:00 a.m. to 10:59 a.m.", "013": "11:00 a.m. to 11:59 a.m.",
             "014": "12:00 p.m. to 3:59 p.m.", "015": "4:00 p.m. to 11:59 p.m."}
V = lambda t, codes: [f"{t}_{c:03d}" if isinstance(c, int) else f"{t}_{c}" for c in codes]
COUNT_INDICATORS = {
    "D01": ("population_total", V("B01003", [1]), "persons", "B01003", "Total population"),
    "D02": ("households", V("B25003", [1]), "households", "B25003", "Occupied housing units"),
    "D03": ("housing_units", V("B25001", [1]), "housing_units", "B25001", "Housing units"),
    "D04": ("population_under_18", V("B01001", [3, 4, 5, 6, 27, 28, 29, 30]), "persons", "B01001", "Total population"),
    "D05": ("population_65_plus", V("B01001", [20, 21, 22, 23, 24, 25, 44, 45, 46, 47, 48, 49]), "persons", "B01001", "Total population"),
    "D06": ("workers_16_plus", V("B08301", [1]), "workers", "B08301", "Workers 16 years and over"),
    "D08_total": ("workers_not_working_from_home", V("B08302", [1]), "workers", "B08302", "Workers 16 years and over who did not work from home"),
    "D09": ("zero_vehicle_households", V("B25044", [3, 10]), "households", "B25044", "Occupied housing units"),
    "D09_den": ("occupied_housing_units_B25044", V("B25044", [1]), "households", "B25044", "Occupied housing units"),
    "D10_low": (f"households_income_below_{LOW_INCOME_THRESHOLD_USD}", V("B19001", [2, 3, 4, 5, 6, 7]), "households", "B19001", "Households"),
    "D10_den": ("households_B19001", V("B19001", [1]), "households", "B19001", "Households"),
    "D12": ("households_below_poverty", V("B17017", [2]), "households", "B17017", "Households"),
    "D12_den": ("households_B17017", V("B17017", [1]), "households", "B17017", "Households"),
    "D13": ("population_with_disability", V("B18101", [4, 7, 10, 13, 16, 19, 23, 26, 29, 32, 35, 38]), "persons", "B18101", "Civilian noninstitutionalized population"),
    "D13_den": ("civilian_noninstitutionalized_population", V("B18101", [1]), "persons", "B18101", "Civilian noninstitutionalized population"),
}
for mode, code in COMMUTE.items(): COUNT_INDICATORS[f"D07_{mode}"] = (f"commute_{mode}", [f"B08301_{code}"], "workers", "B08301", "Workers 16 years and over")
for code in DEPARTURE: COUNT_INDICATORS[f"D08_{code}"] = (f"departure_{code}", [f"B08302_{code}"], "workers", "B08302", "Workers 16 years and over who did not work from home")
for code, lo, hi in INCOME_BRACKETS: COUNT_INDICATORS[f"D10_{code:03d}"] = (f"households_income_{lo}_{hi if hi else 'plus'}", [f"B19001_{code:03d}"], "households", "B19001", "Households")
TABLES_BG = ["B01003", "B01001", "B25003", "B25001", "B08301", "B08302", "B25044", "B19001", "B19013", "B17017"]
TABLES_TRACT = ["B18101"]   # not published at block-group level (every estimate null in the BG pull); tract estimates apportioned by land share
INDICATOR_GEO = {"D13": "tract", "D13_den": "tract"}   # default: block_group
SEMANTICS = {"estimate_type": "period_estimate", "period": "2020-2024", "vintage": f"ACS {ACS_VINTAGE} 5-year", "is_current_population": False,
             "provenance_class": "observed", "data_nature": "survey_estimate", "is_ridership": False, "is_allocation_weight": False,
             "areal_interpolation": {"method": "land_area_share", "land_geometry_method": "tiger_areawater_erased", "weight_proxy": "land_area",
                                     "note": "shares assume the block group's estimate is spread evenly over its LAND; this is an assumption, "
                                             "and the MOE shown excludes it"}}

environment = lock_gate()
fwd, inv, transform_record = projection()
proj = lambda g: shp_transform(fwd.transform, g)

# ---------------- consumed inputs + hash gates ----------------
sj_ptr = load(DATA / "spatial_join_current.json"); sj_dir = DATA / sj_ptr["package_dir"]
ok, sj_manifest, problems = verify_package(sj_dir, "spatial_join_manifest.json")
if not ok: raise SystemExit(f"HALT: spatial_join package does not verify: {problems}")
sj_profile = load(sj_dir / "station_zoning_profile.json")
RADII_FT, QUAD_SEGS = sj_manifest["config"]["radii_ft"], sj_manifest["config"]["quad_segs"]
RADII_M = [r * FOOT_M for r in RADII_FT]
raw_manifest = load(RAW15 / "source_manifest.json"); raw_by_file = {s["file"]: s for s in raw_manifest["sources"]}
raw_files = ["tiger/tl_2024_12_bg.zip", "tiger/tl_2020_12086_tabblock20.zip", "tiger/tl_2024_12086_areawater.zip"] + \
            [f"acs/acs5_{ACS_VINTAGE}_bg_{STATE}{COUNTY}_{t}.json" for t in TABLES_BG] + \
            [f"acs/acs5_{ACS_VINTAGE}_tract_{STATE}{COUNTY}_{t}.json" for t in TABLES_TRACT] + [f"acs/groups/{t}.json" for t in TABLES_BG + TABLES_TRACT]
for f in raw_files:
    if sha_file(RAW15 / f) != raw_by_file[f]["sha256"]: raise SystemExit(f"HALT: raw file {f} sha256 != raw source_manifest.json")
consumed_inputs = [consumed_entry("station_master", DATA / "station_master.geojson"), consumed_entry("raw_source_manifest", RAW15 / "source_manifest.json")] + \
                  [consumed_entry(f, RAW15 / f) for f in raw_files]
stations = load(DATA / "station_master.geojson")["features"]
if len(stations) != 21: raise SystemExit(f"HALT: expected 21 stations, got {len(stations)}")

# ---------------- bands (identical construction to the spatial-join stage) ----------------
st, targets, cum_by_station = [], {}, {}
for f in stations:
    pid, name = f["properties"]["station_id"], f["properties"]["name"]; pt = proj(shape(f["geometry"]))
    discs = [pt.buffer(r, quad_segs=QUAD_SEGS) for r in RADII_M]
    bands = [discs[0], discs[1].difference(discs[0]), discs[2].difference(discs[1])]
    for k, b in zip(BAND_KEYS, bands): targets[(pid, k)] = b
    targets[(pid, "cum")] = discs[2]; cum_by_station[pid] = discs[2]; st.append((pid, name))
ids = [s[0] for s in st]
net = unary_union(list(cum_by_station.values()))
multi = unary_union([cum_by_station[a].intersection(cum_by_station[b]) for i, a in enumerate(ids) for b in ids[i + 1:]
                     if cum_by_station[a].intersects(cum_by_station[b])])
targets[("net", "net")] = net; targets[("net", "multi")] = multi
sj_by_id = {s["station_id"]: s for s in sj_profile["stations"]}
band_area_dev = max(abs(targets[(pid, k)].area - sj_by_id[pid]["bands"][i]["ring_area_m2"]) for pid in ids for i, k in enumerate(BAND_KEYS))
cum_area_dev = max(abs(targets[(pid, "cum")].area - sj_by_id[pid]["cumulative_0_to_half_mile"]["ring_area_m2"]) for pid in ids)
net_area_dev = abs(net.area - sj_profile["network"]["network_half_mile_union_area_m2"])

# ---------------- TIGER: block groups, blocks, water; scope; land geometry ----------------
bg_attr = {}
for rec, g in read_shapefile_zip(RAW15 / "tiger/tl_2024_12_bg.zip"):
    if rec["STATEFP"] == STATE and rec["COUNTYFP"] == COUNTY: bg_attr[rec["GEOID"]] = {"ALAND": int(rec["ALAND"]), "AWATER": int(rec["AWATER"])}
blocks = {}
for rec, g in read_shapefile_zip(RAW15 / "tiger/tl_2020_12086_tabblock20.zip"):
    blocks[rec["GEOID20"]] = {"geom": proj(g), "ALAND20": int(rec["ALAND20"]), "AWATER20": int(rec["AWATER20"]), "bg": rec["GEOID20"][:12]}
water = [proj(g) for _, g in read_shapefile_zip(RAW15 / "tiger/tl_2024_12086_areawater.zip")]
# scope = every block of every TRACT that has a block touching the network union (tract-complete, so neither the tract
# nor the block-group denominators are ever clipped); the block groups inside those tracts are the block-group scope
touched = {b["bg"] for b in blocks.values() if b["geom"].intersects(net)}
scope_tracts = sorted({bg[:11] for bg in touched})
scope_blocks = {bid: b for bid, b in blocks.items() if b["bg"][:11] in set(scope_tracts)}
scope_bgs = sorted({b["bg"] for b in scope_blocks.values()})
land = erase_water({bid: b["geom"] for bid, b in scope_blocks.items()}, water)
repaired = []
for bid, g in land.items():
    if not g.is_valid:
        fixed = polygonal(make_valid(g)); repaired.append({"block": bid, "area_before_m2": r6(g.area), "area_after_m2": r6(fixed.area)}); land[bid] = fixed
bg_land = defaultdict(float); bg_blocks = defaultdict(list); tract_land = defaultdict(float)
for bid in sorted(scope_blocks):
    bg = scope_blocks[bid]["bg"]; bg_land[bg] += land[bid].area; bg_blocks[bg].append(bid); tract_land[bg[:11]] += land[bid].area
land_report_rows = []
for bid in sorted(scope_blocks):
    b = scope_blocks[bid]; a = land[bid].area
    land_report_rows.append({"block": bid, "bg": b["bg"], "ALAND20_m2": b["ALAND20"], "AWATER20_m2": b["AWATER20"], "land_area_erased_m2": r6(a),
                             "delta_vs_ALAND20_m2": r6(a - b["ALAND20"]), "delta_share": (r6((a - b["ALAND20"]) / b["ALAND20"]) if b["ALAND20"] else None),
                             "water_erased": a < b["geom"].area - 1e-6})

# ---------------- ACS values per block group ----------------
acs = {t: parse_acs_table(t) for t in TABLES_BG}
acs_tract = {t: parse_acs_table(t, "tract") for t in TABLES_TRACT}
missing_bgs = sorted({bg for t in TABLES_BG for bg in scope_bgs if bg not in acs[t]})
missing_tracts = sorted({tr for t in TABLES_TRACT for tr in scope_tracts if tr not in acs_tract[t]})
if missing_bgs or missing_tracts: raise SystemExit(f"HALT: units without ACS rows: block groups {missing_bgs[:5]} tracts {missing_tracts[:5]}")
table_of = lambda var: var.split("_")[0]


def unit_values(source, unit_id, indicator_ids):
    """Indicator values of one geography unit: component variables summed, MOE = RSS of the component MOEs."""
    rec = {}
    for iid in indicator_ids:
        name, vars_, unit, table, universe = COUNT_INDICATORS[iid]
        cells = [source[table_of(v)][unit_id][v] for v in vars_]
        if any(c["value"] is None for c in cells):
            bad = next(c for c in cells if c["value"] is None)
            rec[iid] = {"value": None, "moe": None, "value_status": bad["value_status"], "missing_reason": bad["missing_reason"], "moe_status": bad["moe_status"]}
        else:
            moes = [c["moe"] for c in cells]
            rec[iid] = {"value": sum(c["value"] for c in cells), "moe": (math.sqrt(sum(m ** 2 for m in moes)) if all(m is not None for m in moes) else None),
                        "value_status": "value", "missing_reason": None,
                        "moe_status": ("exact_source" if len(cells) == 1 and moes[0] is not None else "rss_of_components" if all(m is not None for m in moes) else "insufficient_sample")}
    return rec


BG_INDICATORS = [iid for iid in COUNT_INDICATORS if INDICATOR_GEO.get(iid, "bg") == "bg"]
TRACT_INDICATORS = [iid for iid in COUNT_INDICATORS if INDICATOR_GEO.get(iid) == "tract"]
bgv = {bg: unit_values(acs, bg, BG_INDICATORS) for bg in scope_bgs}
for bg in scope_bgs:
    med = acs["B19013"][bg]["B19013_001"]
    bgv[bg]["D11"] = {"value": med["value"], "moe": med["moe"], "value_status": med["value_status"], "missing_reason": med["missing_reason"], "moe_status": med["moe_status"]}
tv = {tr: unit_values(acs_tract, tr, TRACT_INDICATORS) for tr in scope_tracts}

# ---------------- shares + aggregation ----------------
inter = intersections_by_target(land, targets)


def envelope(iid, est, moe, used, missing, moe_missing, unit):
    cv, flag = reliability(est if used else None, None if moe_missing else moe)
    return {"indicator_id": iid, "name": COUNT_INDICATORS[iid][0], "unit": unit, "value": (r2(est) if used else None), "display_value": (round(est) if used else None),
            "moe_90": (r2(moe) if used and not moe_missing else None),
            "moe_status": ("approximate_sampling_only_excludes_interpolation" if used and not moe_missing else ("insufficient_sample" if used else "not_applicable")),
            "cv": cv, "reliability_flag": flag, "value_status": ("value" if used else "missing"), "missing_reason": (None if used else "all_source_units_missing"),
            "contributing_units": used, "units_missing_value": missing}


def ratio_env(rid, name, num, den):
    if num["value"] is None or den["value"] in (None, 0):
        return {"ratio_id": rid, "name": name, "numerator": num["indicator_id"], "denominator": den["indicator_id"], "value": None, "value_status": "not_applicable",
                "missing_reason": "numerator_or_denominator_unavailable"}
    p = num["value"] / den["value"]
    moe = moe_ratio(num["value"], num["moe_90"], den["value"], den["moe_90"]) if (num["moe_90"] is not None and den["moe_90"] is not None) else None
    cv, flag = reliability(p, moe)
    return {"ratio_id": rid, "name": name, "numerator": num["indicator_id"], "denominator": den["indicator_id"], "value": r6(p), "display_percent": round(p * 100, 1),
            "moe_90": (r6(moe) if moe is not None else None), "moe_status": ("ratio_approximation" if moe is not None else "not_applicable"),
            "cv": cv, "reliability_flag": flag, "value_status": "value", "provenance_class": "derived", "depends_on": [num["indicator_id"], den["indicator_id"]]}


def bracket_median(counts):
    """counts: list of (lo, hi|None, weighted household count) in bracket order."""
    N = sum(c for _, _, c in counts)
    if N <= 0: return {"ratio_id": "R08", "name": "median_household_income_estimate", "value": None, "value_status": "missing", "missing_reason": "no_households"}
    half, cum = N / 2.0, 0.0
    for lo, hi, c in counts:
        if c > 0 and cum + c >= half:
            base = {"ratio_id": "R08", "name": "median_household_income_estimate", "unit": "usd_2024_inflation_adjusted", "estimated_from_aggregated_brackets": True,
                    "method": "share-weighted B19001 bracket counts; linear interpolation within the bracket holding the 50th-percentile household",
                    "households_weighted_total": r2(N), "provenance_class": "derived", "depends_on": ["D10_002..D10_017"], "moe_status": "sensitivity_range",
                    "sensitivity_note": "sensitivity_range is the income bracket containing the median, NOT a confidence interval"}
            if hi is None:
                return {**base, "value": lo, "value_status": "value", "open_ended": True, "sensitivity_range": [lo, None],
                        "note": "median falls in the top open-ended bracket ($200,000 or more); only the lower bound is reported"}
            return {**base, "value": round(lo + (half - cum) / c * (hi - lo)), "value_status": "value", "open_ended": False, "sensitivity_range": [lo, hi]}
        cum += c
    return {"ratio_id": "R08", "name": "median_household_income_estimate", "value": None, "value_status": "missing", "missing_reason": "interpolation_failed"}


def aggregate_target(key):
    hits = inter[key]; land_m2 = sum(hits.values())
    by_bg, by_tr = defaultdict(float), defaultdict(float)
    for blk, a in hits.items(): by_bg[scope_blocks[blk]["bg"]] += a; by_tr[scope_blocks[blk]["bg"][:11]] += a
    shares = {bg: (a / bg_land[bg] if bg_land[bg] > 0 else 0.0) for bg, a in sorted(by_bg.items())}
    tr_shares = {tr: (a / tract_land[tr] if tract_land[tr] > 0 else 0.0) for tr, a in sorted(by_tr.items())}
    counts = {}
    for iid, (name, vars_, unit, table, universe) in COUNT_INDICATORS.items():
        if INDICATOR_GEO.get(iid, "bg") == "tract":
            est, moe, used, missing, moe_missing = combine_sum((w, tv[tr][iid]["value"], tv[tr][iid]["moe"]) for tr, w in tr_shares.items())
            counts[iid] = {**envelope(iid, est, moe, used, missing, moe_missing, unit), "geography_unit": "tract",
                           "geography_note": "table not published at block-group level; tract estimate apportioned by land share (coarser than the other indicators)"}
        else:
            est, moe, used, missing, moe_missing = combine_sum((w, bgv[bg][iid]["value"], bgv[bg][iid]["moe"]) for bg, w in shares.items())
            counts[iid] = {**envelope(iid, est, moe, used, missing, moe_missing, unit), "geography_unit": "block_group"}
    ratios = {"R01": ratio_env("R01", "public_transportation_commute_share_reference", counts["D07_public_transportation"], counts["D06"]),
              "R02": ratio_env("R02", "worked_from_home_share", counts["D07_worked_from_home"], counts["D06"]),
              "R03": ratio_env("R03", "zero_vehicle_household_share", counts["D09"], counts["D09_den"]),
              "R04": ratio_env("R04", f"low_income_household_share_below_{LOW_INCOME_THRESHOLD_USD}", counts["D10_low"], counts["D10_den"]),
              "R05": ratio_env("R05", "households_below_poverty_share", counts["D12"], counts["D12_den"]),
              "R06": ratio_env("R06", "population_with_disability_share", counts["D13"], counts["D13_den"]),
              "R07": ratio_env("R07", "population_65_plus_share", counts["D05"], counts["D01"])}
    ratios["R04"]["threshold_note"] = f"below ${LOW_INCOME_THRESHOLD_USD:,} household income (brackets 002-007) is a project convention, not an official low-income definition"
    ratios["R01"]["note"] = "reference only; not part of the ridership calculation chain (rules doc 规则 5)"
    median = bracket_median([(lo, hi, counts[f"D10_{code:03d}"]["value"] or 0.0) for code, lo, hi in INCOME_BRACKETS])
    d01, d02 = counts["D01"]["value"] or 0.0, counts["D02"]["value"] or 0.0
    vs = "value" if land_m2 > 0 else "not_applicable"
    density = {"R09_population_density": {"ratio_id": "R09", "value_persons_per_sq_mi": per_sq_mi(d01, land_m2), "value_persons_per_km2": (round(d01 / (land_m2 / 1e6), 1) if land_m2 > 0 else None),
                                          "value_status": vs, "denominator": "land_area_m2 (water erased)", "is_ridership": False, "provenance_class": "derived", "depends_on": ["D01", "land_area_m2"]},
               "households_per_acre": {"value": per_acre(d02, land_m2), "value_status": vs, "denominator": "land_area_m2 (water erased)", "provenance_class": "derived", "depends_on": ["D02", "land_area_m2"]}}
    d11 = [bg for bg in shares if bgv[bg]["D11"]["value"] is not None]
    return {"land_area_m2": r6(land_m2), "display": {"land_area": disp_area(land_m2)},
            "source_units": {"block_groups": len(shares), "tracts": len(tr_shares), "blocks": len(hits),
                             "block_group_shares": {bg: r6(w) for bg, w in shares.items()}, "tract_shares": {tr: r6(w) for tr, w in tr_shares.items()}},
            "counts": {k: v for k, v in counts.items() if not k.startswith(("D07_", "D08_0", "D10_0"))},
            "commute_modes": {mode: counts[f"D07_{mode}"] for mode in COMMUTE},
            "departure_time_bins": {code: {"label": DEPARTURE[code], **counts[f"D08_{code}"]} for code in DEPARTURE},
            "income_brackets": {f"{code:03d}": {"lower_usd": lo, "upper_usd": hi, **counts[f"D10_{code:03d}"]} for code, lo, hi in INCOME_BRACKETS},
            "ratios": ratios, "median_household_income": {**median, "block_groups_with_published_median": len(d11), "block_groups_without_published_median": len(shares) - len(d11),
                                                           "per_block_group_medians": "see block_group_values.json (D11); never averaged"},
            "density": density}


SNAPSHOT_BG = f"acs5_{ACS_VINTAGE}_bg_{STATE}{COUNTY}@{raw_by_file[f'acs/acs5_{ACS_VINTAGE}_bg_{STATE}{COUNTY}_B01003.json']['sha256'][:12]}"
SNAPSHOT_TRACT = f"acs5_{ACS_VINTAGE}_tract_{STATE}{COUNTY}_B18101@{raw_by_file[f'acs/acs5_{ACS_VINTAGE}_tract_{STATE}{COUNTY}_B18101.json']['sha256'][:12]}"
profiles, evidence = [], []


def add_evidence(pid, k, agg):
    for bg, w in agg["source_units"]["block_group_shares"].items():
        evidence.append({"evidence_id": f"{pid}|{k}|BG{bg}", "station_id": pid, "band_id": k, "unit_type": "block_group", "unit_id": bg,
                         "share_of_unit_land_in_target": w, "unit_land_area_m2": r6(bg_land[bg]), "land_area_in_target_m2": r6(w * bg_land[bg]),
                         "used_for": "all block-group indicators (D01-D12)", "source_snapshot": SNAPSHOT_BG})
    for tr, w in agg["source_units"]["tract_shares"].items():
        evidence.append({"evidence_id": f"{pid}|{k}|TR{tr}", "station_id": pid, "band_id": k, "unit_type": "tract", "unit_id": tr,
                         "share_of_unit_land_in_target": w, "unit_land_area_m2": r6(tract_land[tr]), "land_area_in_target_m2": r6(w * tract_land[tr]),
                         "used_for": "tract-level indicators only (D13, D13_den, R06)", "source_snapshot": SNAPSHOT_TRACT})


for pid, name in st:
    bands_out = []
    for i, k in enumerate(BAND_KEYS):
        agg = aggregate_target((pid, k))
        bands_out.append({"band_id": k, "band": BAND_LABELS[i], "inner_ft": 0 if i == 0 else RADII_FT[i - 1], "outer_ft": RADII_FT[i],
                          "ring_area_m2": r6(targets[(pid, k)].area), **SEMANTICS, **agg})
        add_evidence(pid, k, agg)
    cum = aggregate_target((pid, "cum")); add_evidence(pid, "cum", cum)
    profiles.append({"station_id": pid, "name": name, **SEMANTICS, "bands": bands_out,
                     "cumulative_0_to_half_mile": {"band_id": "cum", "outer_ft": RADII_FT[2], "ring_area_m2": r6(targets[(pid, "cum")].area), **SEMANTICS, **cum},
                     "classification_note": "residence-based survey estimates around the station reference point; not observed ridership, not a walk catchment"})

net_agg = aggregate_target(("net", "net")); multi_agg = aggregate_target(("net", "multi"))
add_evidence("net", "net", net_agg)
sum_cum = {iid: r2(sum((p["cumulative_0_to_half_mile"]["counts"][iid]["value"] or 0.0) for p in profiles)) for iid in ("D01", "D02", "D06")}
network_block = {"network_half_mile_union_area_m2": r6(net.area), "land_area_m2": net_agg["land_area_m2"], "display": {"union_area": disp_area(net.area), "land_area": disp_area(net_agg["land_area_m2"])},
                 "deduplicated": {"counts": net_agg["counts"], "commute_modes": net_agg["commute_modes"], "departure_time_bins": net_agg["departure_time_bins"],
                                  "income_brackets": net_agg["income_brackets"], "ratios": net_agg["ratios"], "median_household_income": net_agg["median_household_income"],
                                  "density": net_agg["density"], "source_units": net_agg["source_units"]},
                 "sum_of_21_station_cumulative_discs": sum_cum,
                 "duplication_ratio": {iid: (r6(sum_cum[iid] / net_agg["counts"][iid]["value"]) if net_agg["counts"][iid]["value"] else None) for iid in sum_cum},
                 "covered_by_2_or_more_stations": {"area_m2": r6(multi.area), "land_area_m2": multi_agg["land_area_m2"],
                                                   "population_total": multi_agg["counts"]["D01"], "households": multi_agg["counts"]["D02"], "workers_16_plus": multi_agg["counts"]["D06"]},
                 "note": "per-station profiles are NON-exclusive (overlapping discs); network totals are computed once on the union geometry. "
                         "The duplication ratio is area/estimate repetition, not a demand multiplier. Allocation of the overlap to stations is an analysis-layer assumption."}

# ---------------- validation ----------------
def raw_shares(key):   # unrounded block-group shares, straight from the intersection areas
    by_bg = defaultdict(float)
    for blk, a in inter[key].items(): by_bg[scope_blocks[blk]["bg"]] += a
    return {bg: (a / bg_land[bg] if bg_land[bg] > 0 else 0.0) for bg, a in by_bg.items()}
share_dev = 0.0
for pid in ids:
    cs = raw_shares((pid, "cum")); bs = [raw_shares((pid, k)) for k in BAND_KEYS]
    for bg in cs: share_dev = max(share_dev, abs(sum(b.get(bg, 0.0) for b in bs) - cs[bg]))
all_shares = [w for p in profiles for b in p["bands"] + [p["cumulative_0_to_half_mile"]] for w in b["source_units"]["block_group_shares"].values()] + list(net_agg["source_units"]["block_group_shares"].values())
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "bands_match_spatial_join_package": {"max_band_area_deviation_m2": r6(band_area_dev), "max_cum_area_deviation_m2": r6(cum_area_dev), "net_area_deviation_m2": r6(net_area_dev), "pass": band_area_dev < 1e-4 and cum_area_dev < 1e-4 and net_area_dev < 1e-3},
       "shares_in_unit_interval": all(0.0 <= w <= 1.0 + 1e-9 for w in all_shares),
       "band_shares_add_up_to_cum": {"max_deviation": r6(share_dev), "pass": share_dev < 1e-9},
       "every_target_has_land": all(b["land_area_m2"] > 0 for p in profiles for b in p["bands"] + [p["cumulative_0_to_half_mile"]]),
       "every_station_cum_has_population": all((p["cumulative_0_to_half_mile"]["counts"]["D01"]["value"] or 0) > 0 for p in profiles),
       "network_dedup_not_above_sum": all(net_agg["counts"][i]["value"] <= sum_cum[i] + 1e-6 for i in sum_cum),
       "network_dedup_not_below_max_station": all(net_agg["counts"][i]["value"] >= max((p["cumulative_0_to_half_mile"]["counts"][i]["value"] or 0) for p in profiles) - 1e-6 for i in sum_cum),
       "acs_rows_for_every_scope_block_group": not missing_bgs, "acs_rows_for_every_scope_tract": not missing_tracts,
       "tract_level_indicators": {"ids": TRACT_INDICATORS, "reason": "B18101 not published at block-group level"},
       "land_geometry_all_valid_after_repair": all(g.is_valid for g in land.values()), "land_polygons_repaired": len(repaired),
       "median_estimates_in_range": all((p["cumulative_0_to_half_mile"]["median_household_income"]["value"] or 0) >= 0 for p in profiles),
       "no_nan": all(not (isinstance(v, float) and math.isnan(v)) for p in profiles for b in p["bands"] for v in (c["value"] for c in b["counts"].values()) if v is not None),
       "scope": {"tracts": len(scope_tracts), "block_groups": len(scope_bgs), "blocks": len(scope_blocks), "blocks_with_water_erased": sum(1 for r in land_report_rows if r["water_erased"])},
       "stations": len(profiles), "profiles_bands": len(profiles) * 3, "evidence_rows": len(evidence),
       "scope_statement": "PASS means geometry, share and input-integrity checks listed here passed. It is not a statement about the accuracy of ACS "
                          "estimates for small areas, not a walk-catchment result, not ridership and not an acceptance of the whole V2 input package."}
geometry_pass = (val["bands_match_spatial_join_package"]["pass"] and val["shares_in_unit_interval"] and val["band_shares_add_up_to_cum"]["pass"] and val["every_target_has_land"]
                 and val["network_dedup_not_above_sum"] and val["network_dedup_not_below_max_station"] and val["acs_rows_for_every_scope_block_group"] and val["acs_rows_for_every_scope_tract"]
                 and val["land_geometry_all_valid_after_repair"] and val["median_estimates_in_range"] and val["no_nan"])
if os.environ.get("DEMOGRAPHY_FORCE_FAIL") == "1": geometry_pass = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if geometry_pass else "FAIL"; val["build_status"] = "COMPLETED" if geometry_pass else "FAILED"; val["ready_for_downstream"] = bool(geometry_pass)

# ---------------- config, outputs, manifest, publish ----------------
config = {"bands": {"radii_ft": RADII_FT, "quad_segs": QUAD_SEGS, "foot_m": FOOT_M, "source": "spatial_join package config"},
          "scope_rule": "all blocks of every 2020 tract that has a block intersecting the network half-mile union (tract-complete); block groups inside those tracts",
          "default_geography": "block_group", "indicator_geography_exceptions": INDICATOR_GEO,
          "geography_exception_reason": "B18101 (disability) is not published at block-group level; tract estimates are apportioned by tract land share",
          "land_geometry_method": "tiger_areawater_erased", "weight_proxy": "land_area", "low_income_threshold_usd": LOW_INCOME_THRESHOLD_USD,
          "reliability_cv_thresholds": {"high_max": 0.12, "medium_max": 0.40}, "moe_confidence": "90 percent (z=1.645)",
          "indicators": {iid: {"name": v[0], "variables": v[1], "unit": v[2], "table": v[3], "universe": v[4]} for iid, v in COUNT_INDICATORS.items()},
          "median": {"D11": {"variable": "B19013_001", "aggregation": "not_aggregatable; per block group only"}, "R08": "bracket interpolation over B19001"},
          "income_brackets": [{"code": f"{c:03d}", "lower_usd": lo, "upper_usd": hi} for c, lo, hi in INCOME_BRACKETS],
          "acs": {"dataset": "acs/acs5", "vintage": ACS_VINTAGE, "period": "2020-2024", "geography": "block group", "state": STATE, "county": COUNTY}}
config_sha = sha_obj(config)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "spatial_join_package": sj_ptr["package_id"]}
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_demography_profile.json", {"schema_version": "miami-station-demography-profile/1.0", **common, **SEMANTICS, "config": config,
     "transform": transform_record, "environment": environment, "network": network_block, "stations": profiles})
dump(STAGING / "demography_evidence.json", {"schema_version": "miami-demography-evidence/1.0", **common, "rows": evidence,
     "note": "One row per (station, band, block group) with positive land intersection. share × block-group estimate is the contribution; "
             "cum rows equal the sum of the three band rows; net rows are the deduplicated network shares. Cite evidence_id."})
dump(STAGING / "block_group_values.json", {"schema_version": "miami-block-group-values/1.0", **common, **{k: SEMANTICS[k] for k in ("period", "vintage", "estimate_type")},
     "indicator_metadata": config["indicators"], "geography_exceptions": config["indicator_geography_exceptions"],
     "tracts": {tr: {"land_area_m2_erased": r6(tract_land[tr]), "block_groups": sorted({bg for bg in scope_bgs if bg[:11] == tr}),
                     "indicators": {iid: {**v, "value": (r2(v["value"]) if v["value"] is not None else None), "moe": (r2(v["moe"]) if v["moe"] is not None else None)} for iid, v in tv[tr].items()}}
                for tr in scope_tracts},
     "block_groups": {bg: {"land_area_m2_erased": r6(bg_land[bg]), "ALAND_2024_attr_m2": bg_attr.get(bg, {}).get("ALAND"),
                                                                      "AWATER_2024_attr_m2": bg_attr.get(bg, {}).get("AWATER"), "blocks": len(bg_blocks[bg]),
                                                                      "indicators": {iid: {**v, "value": (r2(v["value"]) if v["value"] is not None else None), "moe": (r2(v["moe"]) if v["moe"] is not None else None)} for iid, v in bgv[bg].items()}}
                                                                 for bg in scope_bgs}})
dump(STAGING / "block_land_geometry.json", {"schema_version": "miami-block-land-geometry/1.0", **common, "crs": "EPSG:26917", "units": "m",
     "note": "2020 P.L. block polygons minus TIGER 2024 area hydrography, projected; NOT WGS84 GeoJSON. Consumed by the jobs stage so both layers use one land geometry.",
     "blocks": {bid: {"bg": scope_blocks[bid]["bg"], "ALAND20_m2": scope_blocks[bid]["ALAND20"], "AWATER20_m2": scope_blocks[bid]["AWATER20"],
                      "land_area_m2": r6(land[bid].area), "geometry": mapping(land[bid])} for bid in sorted(scope_blocks)}})
dump(STAGING / "analysis_targets_26917.json", {"schema_version": "miami-analysis-targets/1.0", **common, "crs": "EPSG:26917", "bands": config["bands"],
     "targets": {f"{k[0]}|{k[1]}": {"station_id": k[0], "band_id": k[1], "area_m2": r6(g.area), "geometry": mapping(g)} for k, g in targets.items()}})
dump(STAGING / "land_geometry_report.json", {"schema_version": "miami-land-geometry-report/1.0", **common, "environment": environment, "transform": transform_record,
     "summary": {"blocks_in_scope": len(scope_blocks), "block_groups_in_scope": len(scope_bgs), "blocks_with_water_erased": sum(1 for r in land_report_rows if r["water_erased"]),
                 "max_abs_delta_share_vs_ALAND20": max((abs(r["delta_share"]) for r in land_report_rows if r["delta_share"] is not None), default=None),
                 "blocks_delta_over_5_percent": sum(1 for r in land_report_rows if r["delta_share"] is not None and abs(r["delta_share"]) > 0.05),
                 "invalid_land_polygons_repaired": repaired,
                 "vintage_note": "blocks are TIGER 2020 P.L.; hydrography is TIGER 2024; ALAND20 is the 2020 attribute — deltas reflect vintage differences and are recorded, not corrected"},
     "blocks": land_report_rows})
dump(STAGING / "demography_validation.json", val)

if not geometry_pass:
    fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-demography-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": [package_entry("spatial_join")],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py", ROOT / "vendor/shapefile.py"),
            "config_sha256": config_sha, "config": config, "environment": environment, "transform": transform_record,
            "method_summary": "ACS 2020-2024 block-group estimates apportioned to imperial station bands by land-area share (water erased); "
                              "RSS MOE excluding interpolation; ratios via Census approximation; medians from brackets; network dedup on the union",
            "contract": "V2_站点输入包字段契约.md §2, §3, §6, §7",
            "publish_policy": "content-addressed immutable package dir demography/pkg-<id>; readers resolve demography_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} stations={len(profiles)} "
      f"scope_bgs={len(scope_bgs)} scope_blocks={len(scope_blocks)} evidence_rows={len(evidence)} "
      f"net_population={net_agg['counts']['D01']['display_value']} sum_cum_population={sum_cum['D01']} land_repairs={len(repaired)}")
