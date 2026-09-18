#!/usr/bin/env python3
"""Miami · station jobs profiles — V2 step 3, stage `jobs` (LODES 8, Florida 2023, 2020 census blocks).

Contract: V2_站点输入包字段契约.md §4 (J01-J10), §6 (shares), §7 (zero_absent_from_file). Rules doc 规则 2 (LODES is a
job-housing link, not ridership; block-level products only; OD subset with candidate stations, NO station-to-station
matrix), 规则 3 (overlap), 规则 5 (units).

What it does
  * Consumes the demography package: the same water-erased block land geometry and the same analysis targets
    (bands, cumulative discs, network union, multi-station area), so both layers share one geometry.
  * Block share in a target = area(block land ∩ target) / block land area. Values = Σ(share × block value).
  * WAC (jobs by workplace) and RAC (jobs held by residents) for JT00 all jobs and JT01 primary jobs; C000 is the
    publisher's "Total number of jobs" in both files — only JT01 approximates persons.
  * OD subset: every block-to-block link with at least one end in a candidate block (a block whose land touches a
    station's half-mile disc), tagged with candidate stations + land shares at both ends and a link category.
    Florida residents working out of state are not in the Florida files (declared gap).
  * No margins of error (administrative, modeled data). Publishes jobs/pkg-<id>/ atomically (R3); readiness by
    scripts/miami_readiness.py (R2).
"""
import csv, gzip, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

STAGE = "jobs"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_jobs_profile.json", "jobs_evidence.json", "block_values.json", "od_links_subset.csv.gz", "od_summary.json", "jobs_validation.json"]
BAND_KEYS, BAND_LABELS = ["b1", "b2", "b3"], ["0-1/8 mi", "1/8-1/4 mi", "1/4-1/2 mi"]
YEAR, JTS = 2023, ["JT00", "JT01"]
SECTORS = {"CNS01": "11 Agriculture, Forestry, Fishing and Hunting", "CNS02": "21 Mining, Quarrying, and Oil and Gas Extraction", "CNS03": "22 Utilities",
           "CNS04": "23 Construction", "CNS05": "31-33 Manufacturing", "CNS06": "42 Wholesale Trade", "CNS07": "44-45 Retail Trade",
           "CNS08": "48-49 Transportation and Warehousing", "CNS09": "51 Information", "CNS10": "52 Finance and Insurance",
           "CNS11": "53 Real Estate and Rental and Leasing", "CNS12": "54 Professional, Scientific, and Technical Services",
           "CNS13": "55 Management of Companies and Enterprises", "CNS14": "56 Administrative and Support and Waste Management and Remediation Services",
           "CNS15": "61 Educational Services", "CNS16": "62 Health Care and Social Assistance", "CNS17": "71 Arts, Entertainment, and Recreation",
           "CNS18": "72 Accommodation and Food Services", "CNS19": "81 Other Services (except Public Administration)", "CNS20": "92 Public Administration"}
EARNINGS = {"CE01": "earnings $1,250/month or less", "CE02": "earnings $1,251 to $3,333/month", "CE03": "earnings greater than $3,333/month"}
AGES = {"CA01": "workers age 29 or younger", "CA02": "workers age 30 to 54", "CA03": "workers age 55 or older"}
KEEP = ["C000"] + list(AGES) + list(EARNINGS) + list(SECTORS)
SEMANTICS = {"source": "LEHD LODES 8", "year": YEAR, "lodes_version": 8, "segment": "S000", "provenance_class": "observed", "data_nature": "administrative_modeled",
             "moe_status": "not_applicable", "is_ridership": False, "has_time_of_day": False, "is_allocation_weight": False,
             "c000_definition": "publisher definition: Total number of jobs (WAC by workplace block, RAC by residence block); JT01 primary jobs ≈ persons, JT00 all jobs counts multiple jobs per person",
             "areal_interpolation": {"method": "land_area_share", "land_geometry_method": "tiger_areawater_erased (from the demography package)", "weight_proxy": "land_area",
                                     "note": "block values are spread evenly over the block's LAND; an assumption"}}
LINK_CATEGORIES = {"both_in": "residence and workplace both in candidate blocks",
                   "home_in_work_elsewhere_in_state": "residence in a candidate block, workplace elsewhere in Florida (main file)",
                   "work_in_home_elsewhere_in_state": "workplace in a candidate block, residence elsewhere in Florida (main file)",
                   "work_in_home_out_of_state": "workplace in a candidate block, residence outside Florida (aux file)"}

environment = lock_gate()

# ---------------- consumed: demography package (geometry + targets + D03), raw LODES ----------------
dem_ptr = load(DATA / "demography_current.json"); dem_dir = DATA / dem_ptr["package_dir"]
ok, dem_manifest, problems = verify_package(dem_dir, "manifest.json")
if not ok: raise SystemExit(f"HALT: demography package does not verify: {problems}")
blg = load(dem_dir / "block_land_geometry.json"); tg = load(dem_dir / "analysis_targets_26917.json"); dem_profile = load(dem_dir / "station_demography_profile.json")
land = {bid: shape(b["geometry"]) for bid, b in blg["blocks"].items()}
block_attr = {bid: {"bg": b["bg"], "land_area_m2": b["land_area_m2"], "ALAND20_m2": b["ALAND20_m2"]} for bid, b in blg["blocks"].items()}
targets = {(t["station_id"], t["band_id"]): shape(t["geometry"]) for t in tg["targets"].values()}
target_area = {(t["station_id"], t["band_id"]): t["area_m2"] for t in tg["targets"].values()}
RADII_FT = tg["bands"]["radii_ft"]
ids = sorted({k[0] for k in targets if k[0] != "net"})
raw_manifest = load(RAW15 / "source_manifest.json"); raw_by_file = {s["file"]: s for s in raw_manifest["sources"]}
lodes_files = {f"{kind}_{jt}": f"lodes/fl_{kind}_S000_{jt}_{YEAR}.csv.gz" for kind in ("wac", "rac") for jt in JTS}
lodes_files.update({f"od_{part}_{jt}": f"lodes/fl_od_{part}_{jt}_{YEAR}.csv.gz" for part in ("main", "aux") for jt in JTS})
for f in lodes_files.values():
    if sha_file(RAW15 / f) != raw_by_file[f]["sha256"]: raise SystemExit(f"HALT: raw file {f} sha256 != raw source_manifest.json")
    if raw_by_file[f].get("publisher_sha256_verified") is not True: raise SystemExit(f"HALT: {f} not verified against the publisher checksum")
consumed_inputs = [consumed_entry("raw_source_manifest", RAW15 / "source_manifest.json")] + [consumed_entry(k, RAW15 / f) for k, f in sorted(lodes_files.items())]
D03 = {}   # housing units per target from the demography package (J10 secondary ratio; mixed period)
for s in dem_profile["stations"]:
    for b in s["bands"]: D03[(s["station_id"], b["band_id"])] = b["counts"]["D03"]
    D03[(s["station_id"], "cum")] = s["cumulative_0_to_half_mile"]["counts"]["D03"]
D03[("net", "net")] = dem_profile["network"]["deduplicated"]["counts"]["D03"]

# ---------------- LODES values for scope blocks ----------------
scope = set(land)


def read_lodes(path, geocol):
    out = {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            g = row[geocol]
            if g in scope: out[g] = {c: int(row[c]) for c in KEEP}
    return out


wac = {jt: read_lodes(RAW15 / lodes_files[f"wac_{jt}"], "w_geocode") for jt in JTS}
rac = {jt: read_lodes(RAW15 / lodes_files[f"rac_{jt}"], "h_geocode") for jt in JTS}
ZERO = {c: 0 for c in KEEP}
blockv = {}
for bid in sorted(scope):
    blockv[bid] = {"wac": {jt: {"values": wac[jt].get(bid, ZERO), "value_status": ("value" if bid in wac[jt] else "zero_absent_from_file")} for jt in JTS},
                   "rac": {jt: {"values": rac[jt].get(bid, ZERO), "value_status": ("value" if bid in rac[jt] else "zero_absent_from_file")} for jt in JTS}}

# ---------------- shares ----------------
inter = intersections_by_target(land, targets)
# share of each block's LAND inside the network half-mile union: the fraction of its links that counts as "inside the network"
cov = {b: (a / block_attr[b]["land_area_m2"] if block_attr[b]["land_area_m2"] > 0 else 0.0) for b, a in inter[("net", "net")].items()}


def raw_shares(key): return {b: a / block_attr[b]["land_area_m2"] for b, a in inter[key].items() if block_attr[b]["land_area_m2"] > 0}


def env(value, unit="jobs", **extra):
    return {"value": r2(value), "display_value": round(value), "unit": unit, "value_status": "value", **extra}


def aggregate_target(key):
    shares = raw_shares(key); land_m2 = sum(inter[key].values())
    out = {"land_area_m2": r6(land_m2), "display": {"land_area": disp_area(land_m2)},
           "source_units": {"blocks": len(shares), "blocks_with_wac_row_JT00": sum(1 for b in shares if blockv[b]["wac"]["JT00"]["value_status"] == "value"),
                            "blocks_with_rac_row_JT00": sum(1 for b in shares if blockv[b]["rac"]["JT00"]["value_status"] == "value"),
                            "block_shares": {b: r6(w) for b, w in sorted(shares.items())}}}
    for kind, label in (("wac", "jobs_by_workplace"), ("rac", "jobs_held_by_residents")):
        out[label] = {}
        for jt in JTS:
            tot = {c: sum(w * blockv[b][kind][jt]["values"][c] for b, w in shares.items()) for c in KEEP}
            out[label][jt] = {"job_type": jt, "C000": env(tot["C000"], indicator_id=("J01" if kind == "wac" else "J04"),
                                                          name=("all_jobs" if jt == "JT00" else "primary_jobs_approx_persons") if kind == "wac" else ("resident_all_jobs" if jt == "JT00" else "resident_primary_jobs_approx_workers")),
                              "by_earnings": {c: env(tot[c], indicator_id=("J02" if kind == "wac" else "J05"), label=EARNINGS[c]) for c in EARNINGS},
                              "by_age": {c: env(tot[c], label=AGES[c]) for c in AGES},
                              "by_sector": {c: env(tot[c], indicator_id="J03", label=SECTORS[c]) for c in SECTORS}}
    w00, w01 = out["jobs_by_workplace"]["JT00"]["C000"]["value"], out["jobs_by_workplace"]["JT01"]["C000"]["value"]
    r01 = out["jobs_held_by_residents"]["JT01"]["C000"]["value"]
    hu = D03[key]["value"] if key in D03 else None
    vs = "value" if land_m2 > 0 else "not_applicable"
    out["density"] = {"J08_jobs_per_acre_JT00": {"value": per_acre(w00, land_m2), "value_status": vs, "denominator": "land_area_m2 (water erased)", "provenance_class": "derived"},
                      "J08_jobs_per_acre_JT01": {"value": per_acre(w01, land_m2), "value_status": vs, "denominator": "land_area_m2 (water erased)", "provenance_class": "derived"},
                      "jobs_per_sq_mi_JT00": per_sq_mi(w00, land_m2)}
    out["ratios"] = {"J09_jobs_housing_ratio_primary": {"value": (r6(w01 / r01) if r01 and r01 > 0 else None), "value_status": ("value" if r01 and r01 > 0 else "not_applicable"),
                                                        "numerator": "WAC C000 JT01 (primary jobs located here)", "denominator": "RAC C000 JT01 (primary jobs held by residents ≈ resident workers)",
                                                        "same_year_same_job_type": True, "provenance_class": "derived"},
                     "J09_variant_JT00": {"value": (r6(w00 / out["jobs_held_by_residents"]["JT00"]["C000"]["value"]) if out["jobs_held_by_residents"]["JT00"]["C000"]["value"] > 0 else None),
                                          "value_status": ("value" if out["jobs_held_by_residents"]["JT00"]["C000"]["value"] > 0 else "not_applicable"),
                                          "note": "all jobs / resident all jobs; both sides count multiple jobs per person", "provenance_class": "derived"},
                     "J10_jobs_housing_ratio_secondary": {"value": (r6(w01 / hu) if hu else None), "value_status": ("value" if hu else "not_applicable"),
                                                          "numerator": "WAC C000 JT01 (2023)", "denominator": "D03 housing units (ACS 2020-2024, demography package)",
                                                          "mixed_period": True, "provenance_class": "derived", "depends_on": ["J01", "D03"]}}
    return out


profiles, evidence = [], []
for pid in ids:
    bands_out = []
    for i, k in enumerate(BAND_KEYS):
        agg = aggregate_target((pid, k))
        bands_out.append({"band_id": k, "band": BAND_LABELS[i], "inner_ft": 0 if i == 0 else RADII_FT[i - 1], "outer_ft": RADII_FT[i], "ring_area_m2": r6(target_area[(pid, k)]), **SEMANTICS, **agg})
        for b, w in agg["source_units"]["block_shares"].items():
            evidence.append({"evidence_id": f"{pid}|{k}|BLK{b}", "station_id": pid, "band_id": k, "block": b, "share_of_block_land_in_target": w,
                             "block_land_area_m2": block_attr[b]["land_area_m2"], "land_area_in_target_m2": r6(w * block_attr[b]["land_area_m2"]),
                             "wac_row_JT00": blockv[b]["wac"]["JT00"]["value_status"], "rac_row_JT00": blockv[b]["rac"]["JT00"]["value_status"],
                             "source_snapshot": f"lodes8_fl_{YEAR}@{raw_by_file[lodes_files['wac_JT00']]['sha256'][:12]}"})
    cum = aggregate_target((pid, "cum"))
    for b, w in cum["source_units"]["block_shares"].items():
        evidence.append({"evidence_id": f"{pid}|cum|BLK{b}", "station_id": pid, "band_id": "cum", "block": b, "share_of_block_land_in_target": w,
                         "block_land_area_m2": block_attr[b]["land_area_m2"], "land_area_in_target_m2": r6(w * block_attr[b]["land_area_m2"]),
                         "wac_row_JT00": blockv[b]["wac"]["JT00"]["value_status"], "rac_row_JT00": blockv[b]["rac"]["JT00"]["value_status"],
                         "source_snapshot": f"lodes8_fl_{YEAR}@{raw_by_file[lodes_files['wac_JT00']]['sha256'][:12]}"})
    profiles.append({"station_id": pid, **SEMANTICS, "bands": bands_out,
                     "cumulative_0_to_half_mile": {"band_id": "cum", "outer_ft": RADII_FT[2], "ring_area_m2": r6(target_area[(pid, "cum")]), **SEMANTICS, **cum},
                     "classification_note": "job-housing link around the station reference point; annual job counts, not trips, not ridership"})
net_agg, multi_agg = aggregate_target(("net", "net")), aggregate_target(("net", "multi"))
sum_cum = {jt: r2(sum(p["cumulative_0_to_half_mile"]["jobs_by_workplace"][jt]["C000"]["value"] for p in profiles)) for jt in JTS}
sum_cum_rac = {jt: r2(sum(p["cumulative_0_to_half_mile"]["jobs_held_by_residents"][jt]["C000"]["value"] for p in profiles)) for jt in JTS}
network_block = {"network_half_mile_union_area_m2": r6(target_area[("net", "net")]), "land_area_m2": net_agg["land_area_m2"],
                 "deduplicated": {k: net_agg[k] for k in ("jobs_by_workplace", "jobs_held_by_residents", "density", "ratios", "source_units")},
                 "sum_of_21_station_cumulative_discs": {"jobs_by_workplace_C000": sum_cum, "jobs_held_by_residents_C000": sum_cum_rac},
                 "duplication_ratio_jobs_by_workplace": {jt: (r6(sum_cum[jt] / net_agg["jobs_by_workplace"][jt]["C000"]["value"]) if net_agg["jobs_by_workplace"][jt]["C000"]["value"] else None) for jt in JTS},
                 "covered_by_2_or_more_stations": {"land_area_m2": multi_agg["land_area_m2"], "jobs_by_workplace_C000": {jt: multi_agg["jobs_by_workplace"][jt]["C000"] for jt in JTS},
                                                   "jobs_held_by_residents_C000": {jt: multi_agg["jobs_held_by_residents"][jt]["C000"] for jt in JTS}},
                 "note": "per-station profiles are NON-exclusive; network totals are computed once on the union geometry; the duplication ratio is not a demand multiplier"}

# ---------------- OD subset: block-to-block links touching candidate blocks, with candidate stations ----------------
cand = defaultdict(dict)   # block -> {station: share of block land inside that station's half-mile disc}
for pid in ids:
    for b, w in raw_shares((pid, "cum")).items(): cand[b][pid] = r6(w)
S = set(cand)
fmt = lambda d: "|".join(f"{k}:{v}" for k, v in sorted(d.items()))
links = {}   # (h, w, part) -> {"JT00": S000, "JT01": S000}


def scan_od(path, part, jt):
    n_rows = 0
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split(","); iw, ih, iS = header.index("w_geocode"), header.index("h_geocode"), header.index("S000")
        for line in fh:
            n_rows += 1; p = line.split(",", 3); w, h = p[iw], p[ih]
            if w in S or h in S:
                links.setdefault((h, w, part), {})[jt] = int(p[iS])
    return n_rows


od_rows_scanned = {f"{part}_{jt}": scan_od(RAW15 / lodes_files[f"od_{part}_{jt}"], part, jt) for part in ("main", "aux") for jt in JTS}


def category(h, w, part):
    if part == "aux": return "work_in_home_out_of_state"
    if h in S and w in S: return "both_in"
    return "home_in_work_elsewhere_in_state" if h in S else "work_in_home_elsewhere_in_state"


totals = {c: {jt: 0 for jt in JTS} for c in LINK_CATEGORIES}
both_in_weighted = {jt: 0.0 for jt in JTS}   # Σ S000 × cov_h × cov_w over both_in links: the covered fraction, not whole blocks
station_side = {pid: {"home_side": {jt: 0.0 for jt in JTS}, "work_side": {jt: 0.0 for jt in JTS}} for pid in ids}
rows_out = []
for (h, w, part) in sorted(links):
    v = links[(h, w, part)]; c = category(h, w, part)
    for jt in JTS: totals[c][jt] += v.get(jt, 0)
    if c == "both_in":
        for jt in JTS: both_in_weighted[jt] += v.get(jt, 0) * cov.get(h, 0.0) * cov.get(w, 0.0)
    hc, wc = cand.get(h, {}), cand.get(w, {})
    for pid, sh in hc.items():
        for jt in JTS: station_side[pid]["home_side"][jt] += sh * v.get(jt, 0)
    for pid, sh in wc.items():
        for jt in JTS: station_side[pid]["work_side"][jt] += sh * v.get(jt, 0)
    rows_out.append([h, w, part, c, v.get("JT00", 0), v.get("JT01", 0), fmt(hc), fmt(wc)])
wac_in_S = {jt: sum(blockv[b]["wac"][jt]["values"]["C000"] for b in S) for jt in JTS}
rac_in_S = {jt: sum(blockv[b]["rac"][jt]["values"]["C000"] for b in S) for jt in JTS}
od_work_in_S = {jt: totals["both_in"][jt] + totals["work_in_home_elsewhere_in_state"][jt] + totals["work_in_home_out_of_state"][jt] for jt in JTS}
od_home_in_S = {jt: totals["both_in"][jt] + totals["home_in_work_elsewhere_in_state"][jt] for jt in JTS}
od_summary = {"schema_version": "miami-od-summary/1.0", "built_on": BUILT_ON, **SEMANTICS, "candidate_blocks": len(S), "links_kept": len(rows_out),
              "od_rows_scanned": od_rows_scanned, "link_categories": LINK_CATEGORIES, "totals_S000_by_category": totals,
              "both_in_coverage_weighted_S000": {jt: r6(v) for jt, v in both_in_weighted.items()},
              "coverage_rule": "totals_S000_by_category.both_in counts WHOLE blocks that merely touch a station's half-mile disc (upper bound); "
                               "both_in_coverage_weighted_S000 counts each link for cov_h × cov_w, cov = share of the block's land inside the network "
                               "half-mile union (the same land-share convention as the demography and jobs profiles). Blocks' cov values are in block_values.json",
              "reconciliation": {"wac_C000_in_candidate_blocks": wac_in_S, "od_S000_work_in_candidate_blocks_main_plus_aux": od_work_in_S,
                                 "identity_holds": {jt: wac_in_S[jt] == od_work_in_S[jt] for jt in JTS},
                                 "rac_C000_in_candidate_blocks": rac_in_S, "od_S000_home_in_candidate_blocks_main_only": od_home_in_S,
                                 "resident_jobs_out_of_state_not_in_florida_files": {jt: rac_in_S[jt] - od_home_in_S[jt] for jt in JTS},
                                 "note": "WAC = OD(main)+OD(aux) at the workplace is an exact identity of the LODES files; RAC exceeds OD(main) at the residence "
                                         "by the residents' out-of-state jobs, which live in other states' aux files (declared gap)"},
              "per_station_share_weighted_link_potential": {pid: {side: {jt: r2(v) for jt, v in d.items()} for side, d in s.items()} for pid, s in station_side.items()},
              "per_station_note": "Σ S000 × (share of the end block's land inside the station's half-mile disc); NON-exclusive across stations, not an allocation, "
                                  "not trips; station-to-station allocation with conservation checks is an analysis-layer task",
              "columns": ["h_geocode", "w_geocode", "file_part", "link_category", "S000_JT00", "S000_JT01", "h_candidate_stations", "w_candidate_stations"],
              "candidate_format": "station_id:share_of_block_land_inside_that_station_half_mile_disc, '|'-separated"}

# ---------------- validation ----------------
share_dev = 0.0
for pid in ids:
    cs = raw_shares((pid, "cum")); bs = [raw_shares((pid, k)) for k in BAND_KEYS]
    for b in cs: share_dev = max(share_dev, abs(sum(x.get(b, 0.0) for x in bs) - cs[b]))
all_shares = [w for k in targets for w in raw_shares(k).values()]
dem_by = {s["station_id"]: s for s in dem_profile["stations"]}
land_dev = max(abs(p["cumulative_0_to_half_mile"]["land_area_m2"] - dem_by[p["station_id"]]["cumulative_0_to_half_mile"]["land_area_m2"]) for p in profiles)
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "geometry_from_demography_package": {"package_id": dem_ptr["package_id"], "max_cum_land_area_deviation_m2": r6(land_dev), "pass": land_dev < 1e-3},
       "shares_in_unit_interval": all(0.0 <= w <= 1.0 + 1e-9 for w in all_shares),
       "band_shares_add_up_to_cum": {"max_deviation": r6(share_dev), "pass": share_dev < 1e-9},
       "every_target_has_land": all(b["land_area_m2"] > 0 for p in profiles for b in p["bands"] + [p["cumulative_0_to_half_mile"]]),
       "network_dedup_not_above_sum": all(net_agg["jobs_by_workplace"][jt]["C000"]["value"] <= sum_cum[jt] + 1e-6 for jt in JTS),
       "od_identity_wac_equals_od_at_workplace": od_summary["reconciliation"]["identity_holds"],
       "od_rows_kept_have_candidate_end": all((r[0] in S) or (r[1] in S) for r in rows_out),
       "od_categories_partition_links": sum(totals[c]["JT00"] for c in totals) == sum(v.get("JT00", 0) for v in links.values()),
       "j09_finite_where_defined": all((p["cumulative_0_to_half_mile"]["ratios"]["J09_jobs_housing_ratio_primary"]["value"] or 0) >= 0 for p in profiles),
       "no_nan": all(not (isinstance(x, float) and math.isnan(x)) for p in profiles for x in (p["cumulative_0_to_half_mile"]["jobs_by_workplace"]["JT00"]["C000"]["value"],)),
       "stations": len(profiles), "evidence_rows": len(evidence), "candidate_blocks": len(S), "od_links_kept": len(rows_out),
       "scope_statement": "PASS means geometry, share, file-identity and input-integrity checks passed. LODES is modeled administrative data without "
                          "sampling error; nothing here is ridership, a trip count or a station allocation."}
geometry_pass = (val["geometry_from_demography_package"]["pass"] and val["shares_in_unit_interval"] and val["band_shares_add_up_to_cum"]["pass"] and val["every_target_has_land"]
                 and val["network_dedup_not_above_sum"] and all(val["od_identity_wac_equals_od_at_workplace"].values()) and val["od_rows_kept_have_candidate_end"]
                 and val["od_categories_partition_links"] and val["j09_finite_where_defined"] and val["no_nan"])
if os.environ.get("JOBS_FORCE_FAIL") == "1": geometry_pass = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if geometry_pass else "FAIL"; val["build_status"] = "COMPLETED" if geometry_pass else "FAILED"; val["ready_for_downstream"] = bool(geometry_pass)

# ---------------- outputs, manifest, publish ----------------
config = {"lodes": {"version": 8, "state": "fl", "year": YEAR, "segment": "S000", "job_types": JTS, "columns_kept": KEEP, "sectors": SECTORS, "earnings": EARNINGS, "ages": AGES},
          "geometry_source": "demography package block_land_geometry.json + analysis_targets_26917.json (EPSG:26917, metres)",
          "scope_rule": "blocks of the demography scope (tract-complete); candidate blocks = land touches any station's half-mile disc",
          "link_categories": LINK_CATEGORIES, "coverage_gap": "Florida residents working out of state are in other states' aux files and are not covered",
          "ratios": {"J09": "WAC C000 JT01 / RAC C000 JT01, same year and job type", "J10": "WAC C000 JT01 / ACS D03 housing units (mixed period)"}}
config_sha = sha_obj(config)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "demography_package": dem_ptr["package_id"]}
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_jobs_profile.json", {"schema_version": "miami-station-jobs-profile/1.0", **common, **SEMANTICS, "config": config, "environment": environment,
     "network": network_block, "stations": profiles})
dump(STAGING / "jobs_evidence.json", {"schema_version": "miami-jobs-evidence/1.0", **common, "rows": evidence,
     "note": "One row per (station, band, block) with positive land intersection; share × block value is the contribution; block values in block_values.json. Cite evidence_id."})
dump(STAGING / "block_values.json", {"schema_version": "miami-block-values/1.0", **common, **{k: SEMANTICS[k] for k in ("source", "year", "lodes_version", "data_nature")},
     "columns": {"C000": "Total number of jobs", **AGES, **EARNINGS, **SECTORS},
     "blocks": {b: {**block_attr[b], "candidate_stations": cand.get(b, {}), "share_in_network_union": r6(cov.get(b, 0.0)), **blockv[b]} for b in sorted(scope)}})
with open(STAGING / "od_links_subset.csv.gz", "wb") as raw_f:
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, mtime=0) as gz:   # mtime=0 keeps the bytes deterministic
        text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
        wr = csv.writer(text); wr.writerow(od_summary["columns"]); wr.writerows(rows_out); text.flush(); text.detach()
dump(STAGING / "od_summary.json", od_summary)
dump(STAGING / "jobs_validation.json", val)
if not geometry_pass: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-jobs-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": [package_entry("demography")],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment,
            "method_summary": "LODES 8 (2023) WAC/RAC block counts apportioned to imperial station bands by land share on the demography package's water-erased "
                              "geometry; block-level OD subset with candidate stations; network dedup on the union; no station-to-station matrix",
            "contract": "V2_站点输入包字段契约.md §4, §6, §7",
            "publish_policy": "content-addressed immutable package dir jobs/pkg-<id>; readers resolve jobs_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} stations={len(profiles)} "
      f"candidate_blocks={len(S)} od_links={len(rows_out)} evidence_rows={len(evidence)} net_jobs_JT00={net_agg['jobs_by_workplace']['JT00']['C000']['display_value']} "
      f"sum_cum_JT00={sum_cum['JT00']} identity={od_summary['reconciliation']['identity_holds']}")
