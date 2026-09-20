#!/usr/bin/env python3
"""Miami · feature-level GIS objects for the reading agents — V2 step 11, stage `gis_objects`.

The V2 reading agents (G1 roads / zoning / parcels, G2 heat + residents) read FEATURES, not conclusions. This stage only
clips, measures, joins and counts, and gives every feature a citable object id:
    <station>.RDnn road group      <station>.RLnn rail / Metrorail     <station>.GW01 existing Metromover guideway
    <station>.ZN<FID> zoning polygon   <station>.LU<code> land-use class   <station>.PCnnn parcel
    <station>.HC<row>_<col> heat cell  <station>.BG<geoid> block group      <station>.Gnnn code-computed summary fact
Heat = an ACTIVITY-DENSITY PROXY (2020 Census residents + 2023 LODES jobs per acre of land, 500 ft cells). It is not a
measured heat map and not persons per hour. Heat and zoning are read together and are auxiliary evidence only
(config/gis_objects_v1.json). Role hints are computed for evaluation and are NOT shown to the agents.
Privacy: parcels carry no owner, mailing, site-address or legal-description field.
Publishes gis_objects/pkg-<id>/ atomically (R3); readiness by scripts/miami_readiness.py (R2).
"""
import csv, io, sys, zipfile
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403
from shapely import make_valid
from shapely.geometry import Point, LineString, MultiLineString, box
from shapely.ops import nearest_points
from shapely.prepared import prep

STAGE = "gis_objects"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_gis_objects.json", "heat_grid.json", "object_role_hints.json", "gis_objects_validation.json"]
CFG_FILE = ROOT / "config/gis_objects_v1.json"
RAW20 = RAW15.parent / "2026-09-20/gis_objects"
OSM_FILE = RAW15.parent / "2026-09-17/osm/walk_network_overpass.json"
ZONING_FILE = RAW15.parent / "2026-09-14/zoning_study_window.geojson"
GTFS_ZIP = RAW15.parent / "2026-09-11/google_transit.zip"
SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

cfg = load(CFG_FILE); HP, RC, PC = cfg["heat_proxy"], cfg["roads"], cfg["parcels"]
CELL_M = HP["cell_size_ft"] * FOOT_M
environment = lock_gate()
fwd, inv, transform_record = projection()
proj = lambda g: shp_transform(fwd.transform, g)
clean = lambda g: g if g.is_valid else polygonal(make_valid(g))

# ---------------- consumed inputs + packages ----------------
src20 = load(RAW20 / "gis_objects_source_manifest.json"); raw20 = {}
for s in src20["sources"]:
    for kind, f in s["files"].items():
        p = RAW15.parent / "2026-09-20" / f["file"]
        if sha_file(p) != f["sha256"]: raise SystemExit(f"HALT: {f['file']} sha256 != gis_objects_source_manifest.json")
        raw20[(s["layer_id"], kind)] = p
consumed_inputs = [consumed_entry("gis_objects_config", CFG_FILE), consumed_entry("gis_objects_source_manifest", RAW20 / "gis_objects_source_manifest.json"),
                   consumed_entry("osm_extract", OSM_FILE), consumed_entry("zoning_raw", ZONING_FILE), consumed_entry("gtfs_archive", GTFS_ZIP),
                   consumed_entry("station_master", DATA / "station_master.geojson"), consumed_entry("service_patterns", DATA / "service_patterns.json")] + \
                  [consumed_entry(f"{lid}.{kind}", p) for (lid, kind), p in sorted(raw20.items()) if kind in ("geojson", "response")]
pk = {}
for stage, mname in (("demography", "manifest.json"), ("jobs", "manifest.json"), ("spatial_join", "spatial_join_manifest.json")):
    ptr = load(DATA / f"{stage}_current.json"); d = DATA / ptr["package_dir"]; ok, m, problems = verify_package(d, mname)
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    pk[stage] = {"dir": d, "ptr": ptr}
tg = load(pk["demography"]["dir"] / "analysis_targets_26917.json"); RADII_M = [r * FOOT_M for r in tg["bands"]["radii_ft"]]
disc = {t["station_id"]: shape(t["geometry"]) for t in tg["targets"].values() if t["band_id"] == "cum"}
union = shape(tg["targets"]["net|net"]["geometry"])
blg = load(pk["demography"]["dir"] / "block_land_geometry.json"); bgv = load(pk["demography"]["dir"] / "block_group_values.json")
dem_ev = load(pk["demography"]["dir"] / "demography_evidence.json")["rows"]
jobs_blocks = load(pk["jobs"]["dir"] / "block_values.json")["blocks"]
sj_profile = {s["station_id"]: s for s in load(pk["spatial_join"]["dir"] / "station_zoning_profile.json")["stations"]}
stations = load(DATA / "station_master.geojson")["features"]
st_pt = {f["properties"]["station_id"]: proj(shape(f["geometry"])) for f in stations}; names = {f["properties"]["station_id"]: f["properties"]["name"] for f in stations}
ids = sorted(st_pt)


def sector(origin, target):
    dx, dy = target.x - origin.x, target.y - origin.y
    if abs(dx) < 1e-9 and abs(dy) < 1e-9: return "at station"
    return SECTORS[int(((math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0 + 22.5) // 45) % 8]
def band_of(d): return "b1" if d <= RADII_M[0] else ("b2" if d <= RADII_M[1] else ("b3" if d <= RADII_M[2] else "outside"))
ft = lambda m: round(m / FOOT_M, 1)
mi = lambda m: round(m / FOOT_M / 5280.0, 3)
acres = lambda m2: round(m2 / ACRE_M2, 3)


def near(origin, geom):
    d = origin.distance(geom); p = nearest_points(origin, geom)[1]
    return {"nearest_ft": ft(d), "nearest_band": band_of(d), "nearest_sector": sector(origin, p)}


# ---------------- layers ----------------
osm = load(OSM_FILE); node_ll = {e["id"]: (e["lon"], e["lat"]) for e in osm["elements"] if e["type"] == "node"}
nid = sorted(node_ll); xs, ys = fwd.transform([node_ll[n][0] for n in nid], [node_ll[n][1] for n in nid]); xy = {n: (x, y) for n, x, y in zip(nid, xs, ys)}
ways = []
for e in osm["elements"]:
    if e["type"] != "way": continue
    pts = [xy[n] for n in e["nodes"] if n in xy]
    if len(pts) < 2: continue
    t = e.get("tags", {}); ways.append({"id": e["id"], "cls": t.get("highway"), "name": t.get("name") or t.get("ref") or "(unnamed)", "geom": LineString(pts), "bridge": t.get("bridge") not in (None, "no"),
                                         "tunnel": t.get("tunnel") not in (None, "no"), "lanes": t.get("lanes"), "oneway": t.get("oneway") == "yes"})
way_tree = STRtree([w["geom"] for w in ways])
def lines_of(path):
    gs = [proj(shape(f["geometry"])) for f in load(path)["features"] if f.get("geometry")]
    return unary_union(gs) if gs else LineString()
railroads, metrorail = lines_of(raw20[("railroads", "geojson")]), lines_of(raw20[("metrorail_line", "geojson")])
patterns = load(DATA / "service_patterns.json")["records"]; shape_ids = sorted({str(r["shape_id"]) for r in patterns if r.get("shape_id")})
with zipfile.ZipFile(GTFS_ZIP) as zf:
    rows = [r for r in csv.DictReader(io.TextIOWrapper(zf.open("shapes.txt"), encoding="utf-8-sig")) if r["shape_id"] in set(shape_ids)]
by_shape = defaultdict(list)
for r in rows: by_shape[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
guideway = unary_union([LineString([fwd.transform(lon, lat) for _, lon, lat in sorted(v)]) for v in by_shape.values() if len(v) >= 2])
SPLIT_M = cfg["rail"]["split_buffer_m"]; _gwb, _mrb = guideway.buffer(SPLIT_M), metrorail.buffer(SPLIT_M)
rail_on_guideway = railroads.intersection(_gwb); rail_on_metrorail = railroads.difference(_gwb).intersection(_mrb); rail_other = railroads.difference(_gwb).difference(_mrb)
zoning = [{"p": f["properties"], "geom": clean(polygonal(proj(shape(f["geometry"]))))} for f in load(ZONING_FILE)["features"]]
zon_tree = STRtree([z["geom"] for z in zoning])
landuse = [{"lu": str(f["properties"].get("LU")), "descr": (f["properties"].get("DESCR") or "").strip(), "geom": clean(polygonal(proj(shape(f["geometry"]))))} for f in load(raw20[("land_use", "geojson")])["features"]]
lu_tree = STRtree([l["geom"] for l in landuse]); LU_DESCR = {}
for l in landuse: LU_DESCR.setdefault(l["lu"], l["descr"])
PREFIX_GROUP = {pref: g for g, prefs in PC["groups_by_dor_desc_prefix"].items() for pref in prefs}
parcels, unseen_prefix = [], Counter()
for f in load(raw20[("parcels", "geojson")])["features"]:
    p = f["properties"]; desc = (p.get("DOR_DESC") or "").strip(); prefix = desc.split(" : ")[0].strip() if desc else ""
    grp = PREFIX_GROUP.get(prefix, "attributes_missing" if not desc else "other")
    if grp == "other": unseen_prefix[prefix] += 1
    g = clean(polygonal(proj(shape(f["geometry"]))))
    parcels.append({"folio": p.get("FOLIO"), "dor_code": p.get("DOR_CODE_CUR"), "dor_desc": desc or None, "group": grp, "lot_size_sqft": p.get("LOT_SIZE"), "year_built": p.get("YEAR_BUILT") or None,
                    "condo_flag": p.get("CONDO_FLAG"), "geom": g})
par_tree = STRtree([p["geom"] for p in parcels])
WATER_LU = {k for k, v in LU_DESCR.items() if "water" in v.lower() or "rivers and canals" in v.lower()}
NONPAX_LU = {k for k, v in LU_DESCR.items() if any(w in v.lower() for w in ("industrial", "expressway", "railroads", "electric power", "utilities", "airports", "seaport", "terminals"))}

# ---------------- heat proxy grid ----------------
pl = load(raw20[("census_2020_pl_blocks", "response")]); hdr = pl[0]; ix = {c: i for i, c in enumerate(hdr)}
pop20 = {r[ix["state"]] + r[ix["county"]] + r[ix["tract"]] + r[ix["block"]]: int(r[ix["P1_001N"]]) for r in pl[1:]}
land = {b: shape(r["geometry"]) for b, r in blg["blocks"].items()}; land_area = {b: r["land_area_m2"] for b, r in blg["blocks"].items()}
missing_pl = [b for b in land if b not in pop20]
def block_jobs(b):
    r = jobs_blocks.get(b); return float(r["wac"]["JT00"]["values"]["C000"]) if r and r["wac"]["JT00"]["value_status"] == "value" else 0.0
bl_ids = sorted(land); bl_tree = STRtree([land[b] for b in bl_ids])
minx, miny, maxx, maxy = union.bounds; x0, y0 = math.floor(minx / CELL_M) * CELL_M, math.floor(miny / CELL_M) * CELL_M
ncol, nrow = int(math.ceil((maxx - x0) / CELL_M)), int(math.ceil((maxy - y0) / CELL_M)); punion = prep(union); cells = {}
for r in range(nrow):
    for c in range(ncol):
        g = box(x0 + c * CELL_M, y0 + r * CELL_M, x0 + (c + 1) * CELL_M, y0 + (r + 1) * CELL_M)
        if not punion.intersects(g): continue
        res = job = la = 0.0
        for i in bl_tree.query(g):
            b = bl_ids[int(i)]; a = polygonal(land[b].intersection(g)).area
            if a <= 0 or land_area[b] <= 0: continue
            w = a / land_area[b]; res += w * pop20.get(b, 0); job += w * block_jobs(b); la += a
        zsh = defaultdict(float)
        for i in zon_tree.query(g):
            z = zoning[int(i)]; a = z["geom"].intersection(g).area
            if a > 0: zsh[z["p"].get("Transect_D") or "unlabelled"] += a
        lsh = defaultdict(float)
        for i in lu_tree.query(g):
            l = landuse[int(i)]; a = l["geom"].intersection(g).area
            if a > 0: lsh[l["lu"]] += a
        best_rank, best_cls = 99, None
        for i in way_tree.query(g):
            w = ways[int(i)]; rk = RC["class_rank"].get(w["cls"])
            if rk is not None and rk < best_rank and w["geom"].intersects(g): best_rank, best_cls = rk, w["cls"]
        la_ac = la / ACRE_M2; dens = (res + job) / la_ac if la_ac >= HP["min_land_acres_for_density"] else None
        ztop = max(zsh.items(), key=lambda kv: kv[1]) if zsh else (None, 0.0); ltop = max(lsh.items(), key=lambda kv: kv[1]) if lsh else (None, 0.0)
        cells[(r, c)] = {"cell_id": f"HC{r:02d}_{c:02d}", "row": r, "col": c, "geom": g, "land_acres": round(la_ac, 3), "residents_2020": round(res, 1), "jobs_2023": round(job, 1),
                         "activity_density_per_acre": (round(dens, 1) if dens is not None else None), "jobs_share_of_activity": (round(job / (res + job), 3) if res + job > 0 else None),
                         "dominant_zoning_transect": ztop[0], "dominant_zoning_share_of_cell": round(ztop[1] / g.area, 3), "zoned_share_of_cell": round(sum(zsh.values()) / g.area, 3),
                         "dominant_land_use": ({"code": ltop[0], "descr": LU_DESCR.get(ltop[0], "")[:90]} if ltop[0] else None), "dominant_land_use_share_of_cell": round(ltop[1] / g.area, 3),
                         "highest_road_class": best_cls, "rail_in_cell": bool(rail_other.intersects(g) or metrorail.intersects(g)), "guideway_in_cell": bool(guideway.intersects(g))}
ranked = sorted((c["activity_density_per_acre"], k) for k, c in cells.items() if c["activity_density_per_acre"] is not None)
for n, (_, k) in enumerate(ranked):
    pr = (n + 0.5) / len(ranked); cells[k]["network_percentile"] = round(pr, 3); cells[k]["network_quintile"] = min(5, int(pr * 5) + 1); cells[k]["is_hot"] = pr >= 0.8
for c in cells.values(): c.setdefault("network_percentile", None); c.setdefault("network_quintile", None); c.setdefault("is_hot", False)
cell_keys = sorted(cells); cell_tree = STRtree([cells[k]["geom"] for k in cell_keys])
# conservation of the apportionment over the WHOLE grid is not expected (cells cover only the union); check it inside one disc instead (validation)

# ---------------- per station ----------------
hints, station_blocks, zon_dev_max, heat_dev = [], [], 0.0, {}
for pid in ids:
    D, O = disc[pid], st_pt[pid]; pD = prep(D); disc_area = D.area; objs = {}; facts = []; nfact = [0]
    def G(group, label, value, unit=None, **meta):
        nfact[0] += 1; facts.append({"fact_id": f"{pid}.G{nfact[0]:03d}", "group": group, "label": label, "value": value, **({"unit": unit} if unit else {}), "provenance_class": "derived", **meta})
    def hint(oid, role, rule): hints.append({"object_id": oid, "station_id": pid, "role_hint": role, "hint_rule_id": rule})

    # roads
    groups, summary_len = {}, defaultdict(float)
    for i in way_tree.query(D):
        w = ways[int(i)]
        if not pD.intersects(w["geom"]): continue
        inside = w["geom"].intersection(D).length
        if inside <= 0: continue
        summary_len[w["cls"]] += inside
        if w["cls"] not in RC["object_classes"]: continue
        g = groups.setdefault((w["name"], w["cls"]), {"len": 0.0, "geoms": [], "ways": [], "bridge": False, "tunnel": False, "lanes": [], "oneway": 0})
        g["len"] += inside; g["geoms"].append(w["geom"]); g["ways"].append(w["id"]); g["bridge"] |= w["bridge"]; g["tunnel"] |= w["tunnel"]; g["oneway"] += int(w["oneway"])
        if w["lanes"] and str(w["lanes"]).isdigit(): g["lanes"].append(int(w["lanes"]))
    rows = []
    for (name, cls), g in groups.items():
        rk = RC["class_rank"][cls]
        if rk >= 12 and g["len"] < RC["minor_min_length_ft"] * FOOT_M: continue
        rows.append({"name": name, "highway_class": cls, "class_rank": rk, "length_inside_disc_ft": ft(g["len"]), "bridge": g["bridge"], "tunnel": g["tunnel"], "lanes_max": (max(g["lanes"]) if g["lanes"] else None),
                     "oneway_ways": g["oneway"], "osm_way_count": len(g["ways"]), "osm_way_ids_sample": sorted(g["ways"])[:6], **near(O, unary_union(g["geoms"]))})
    rows.sort(key=lambda r: (r["class_rank"], -r["length_inside_disc_ft"], r["name"])); dropped_roads = max(0, len(rows) - RC["max_rows"]); rows = rows[:RC["max_rows"]]
    for n, r in enumerate(rows, 1):
        r["object_id"] = f"{pid}.RD{n:02d}"
        if r["highway_class"] in ("motorway", "motorway_link", "trunk", "trunk_link"): hint(r["object_id"], "obstacle", "GH-01")
    objs["roads"] = rows
    # rail + guideway
    rl = []
    for label, geom, kind in (("railroad trackage other than the Metromover guideway and the Metrorail line (county Railroads layer has no attributes; split geometrically, see config rail.split_rule)", rail_other, "railroad_other"), ("Metrorail line (heavy rail, county MetroRail layer)", metrorail, "metrorail")):
        inside = geom.intersection(D).length if not geom.is_empty else 0.0
        if inside > 0: rl.append({"object_id": f"{pid}.RL{len(rl) + 1:02d}", "kind": kind, "label": label, "length_inside_disc_ft": ft(inside), **near(O, geom.intersection(D))})
    for r in rl: hint(r["object_id"], "obstacle", "GH-02")
    objs["rail"] = rl
    gw_in = guideway.intersection(D).length
    objs["guideway"] = [{"object_id": f"{pid}.GW01", "kind": "existing_metromover_guideway", "label": "existing Metromover guideway (GTFS shape geometry, overlapping loops merged)", "length_inside_disc_ft": ft(gw_in), "county_rail_layer_track_drawn_on_it_ft": ft(rail_on_guideway.intersection(D).length), **near(O, guideway)}] if gw_in > 0 else []
    for r in objs["guideway"]: hint(r["object_id"], "facility_to_convert", "GH-03")
    # zoning
    zr, by_zone = [], defaultdict(float)
    for i in zon_tree.query(D):
        z = zoning[int(i)]; a = z["geom"].intersection(D).area
        if a <= 0: continue
        by_zone[z["p"].get("M21_ZONE")] += a
        if a < cfg["zoning"]["min_clipped_area_m2"]: continue
        clip = z["geom"].intersection(D); p = z["p"]
        zr.append({"object_id": f"{pid}.ZN{p.get('FID')}", "FID": p.get("FID"), "M21_ZONE": p.get("M21_ZONE"), "Transect": p.get("Transect"), "Transect_D": p.get("Transect_D"), "Bldg_Heigh": p.get("Bldg_Heigh"),
                   "Intensity": p.get("Intensity"), "FLR": p.get("FLR"), "acres_inside_disc": acres(a), "share_of_disc": round(a / disc_area, 4), "contains_reference_point": bool(z["geom"].contains(O)),
                   "nearest_ft": ft(O.distance(z["geom"])), "sector_of_clipped_part": sector(O, clip.centroid)})
    zr.sort(key=lambda r: -r["share_of_disc"]); objs["zoning"] = zr
    pub = sj_profile[pid]["cumulative_0_to_half_mile"]["by_M21_ZONE"]
    for zone, rec in pub.items(): zon_dev_max = max(zon_dev_max, abs(by_zone.get(zone, 0.0) - rec["union_area_m2"]) / disc_area)
    # land use
    lu_area, lu_n = defaultdict(float), Counter()
    for i in lu_tree.query(D):
        l = landuse[int(i)]; a = l["geom"].intersection(D).area
        if a > 0: lu_area[l["lu"]] += a; lu_n[l["lu"]] += 1
    lur = [{"object_id": f"{pid}.LU{code}", "LU": code, "DESCR": LU_DESCR.get(code, ""), "acres_inside_disc": acres(a), "share_of_disc": round(a / disc_area, 4), "polygons": lu_n[code]} for code, a in lu_area.items()]
    lur.sort(key=lambda r: -r["share_of_disc"]); objs["land_use"] = lur
    for r in lur:
        if r["LU"] in WATER_LU: hint(r["object_id"], "obstacle", "GH-08")
    # parcels
    inside_p, group_stat = [], defaultdict(lambda: {"parcels": 0, "acres": 0.0})
    for i in par_tree.query(D):
        p = parcels[int(i)]; g = p["geom"]
        if g.is_empty or not pD.intersects(g): continue
        if not (pD.contains(g.centroid) or g.intersection(D).area >= 0.5 * g.area): continue
        d = O.distance(g); group_stat[p["group"]]["parcels"] += 1; group_stat[p["group"]]["acres"] += g.area / ACRE_M2
        zi = [zoning[int(k)]["p"].get("M21_ZONE") for k in zon_tree.query(g.centroid) if zoning[int(k)]["geom"].contains(g.centroid)]
        inside_p.append({**{k: p[k] for k in ("folio", "dor_code", "dor_desc", "group", "lot_size_sqft", "year_built", "condo_flag")}, "geometry_area_sqft": round(g.area / FOOT_M ** 2),
                         "nearest_ft": ft(d), "band": band_of(O.distance(g.centroid)), "sector": sector(O, g.centroid), "zoning_at_centroid": (zi[0] if zi else None), "_d": d})
    listed_groups = set(PC["listed_groups"])
    sel = [p for p in inside_p if p["group"] != "attributes_missing" and (p["nearest_ft"] <= tg["bands"]["radii_ft"][0] or p["group"] in listed_groups or (p["lot_size_sqft"] or 0) >= PC["large_lot_sqft"])]
    sel.sort(key=lambda p: (p["_d"], p["folio"] or "")); dropped_parcels = max(0, len(sel) - PC["max_rows"]); sel = sel[:PC["max_rows"]]
    for n, p in enumerate(sel, 1):
        p["object_id"] = f"{pid}.PC{n:03d}"; p.pop("_d")
        if p["group"] in ("vacant", "parking") and (p["lot_size_sqft"] or 0) >= PC["module_footprint_sqft"]: hint(p["object_id"], "candidate_site", "GH-04")
        elif p["group"] == "governmental": hint(p["object_id"], "context_public_owner", "GH-05")
    objs["parcels"] = sel
    objs["parcel_groups_all_parcels"] = [{"group": g, "parcels": v["parcels"], "acres": round(v["acres"], 2)} for g, v in sorted(group_stat.items(), key=lambda kv: -kv[1]["parcels"])]
    # heat cells
    hc = []
    for i in cell_tree.query(D):
        k = cell_keys[int(i)]; c = cells[k]; g = c["geom"]
        if not (pD.contains(g.centroid) or g.intersection(D).area >= 0.25 * g.area): continue
        d = O.distance(g.centroid)
        hc.append({"object_id": f"{pid}.{c['cell_id']}", **{kk: vv for kk, vv in c.items() if kk not in ("geom", "row", "col")}, "center_distance_ft": ft(d), "center_band": band_of(d), "center_sector": sector(O, g.centroid)})
    hc.sort(key=lambda r: (-(r["activity_density_per_acre"] or -1), r["object_id"])); objs["heat_cells"] = hc
    for r in hc:
        if not r["is_hot"]: continue
        js = r["jobs_share_of_activity"]
        if js is not None: hint(r["object_id"], "destination_context" if js >= 0.7 else ("origin_context" if js <= 0.3 else "mixed_context"), "GH-06")
        if r["highest_road_class"] in ("motorway", "motorway_link", "trunk", "trunk_link") or r["rail_in_cell"] or (r["dominant_land_use"] and r["dominant_land_use"]["code"] in NONPAX_LU): hint(r["object_id"], "screen_possible_non_passenger_activity", "GH-07")
    # block groups (ACS, from the demography package)
    bgr = []
    for e in dem_ev:
        if e["station_id"] != pid or e["band_id"] != "cum" or e["unit_type"] != "block_group": continue
        ind = bgv["block_groups"][e["unit_id"]]["indicators"]; v = lambda k: ind[k]["value"]
        bgr.append({"object_id": f"{pid}.BG{e['unit_id']}", "geoid": e["unit_id"], "share_of_block_group_land_inside_disc": e["share_of_unit_land_in_target"], "population_estimate": v("D01"), "population_moe_90": ind["D01"]["moe"],
                    "households_estimate": v("D02"), "workers_estimate": v("D06"), "zero_vehicle_households_estimate": v("D09"), "median_household_income_published": ind["D11"]["value"],
                    "median_status": ind["D11"]["value_status"], "period": "ACS 2020-2024 (period estimate)"})
    bgr.sort(key=lambda r: -r["share_of_block_group_land_inside_disc"]); objs["block_groups"] = bgr

    # code-computed summary facts (citable; the agents may restate these numbers, nothing else)
    cls_len = {c: v for c, v in summary_len.items()}
    for c in ("motorway", "trunk", "primary", "secondary", "tertiary", "residential"):
        G("roads", f"road length inside the half-mile disc, class {c} (incl. links)", mi(cls_len.get(c, 0.0) + cls_len.get(c + "_link", 0.0)), "mi")
    G("roads", "pedestrian-only network length inside the disc (footway + path + steps + pedestrian); not a walk model", mi(sum(cls_len.get(c, 0.0) for c in ("footway", "path", "steps", "pedestrian"))), "mi")
    big = [r for r in rows if r["class_rank"] <= 4]
    G("roads", "nearest motorway or trunk road (incl. links)", ({"name": min(big, key=lambda r: r["nearest_ft"])["name"], "nearest_ft": min(r["nearest_ft"] for r in big)} if big else "none inside the half-mile disc"))
    G("roads", "road groups crossing a bridge inside the disc", sum(1 for r in rows if r["bridge"]), "road groups")
    G("rail", "railroad trackage inside the disc, excluding track drawn on the Metromover guideway or the Metrorail line", ft(rail_other.intersection(D).length), "ft")
    G("rail", "track of the county Railroads layer that coincides with the Metromover guideway inside the disc (the layer does not label it)", ft(rail_on_guideway.intersection(D).length), "ft")
    G("rail", "Metrorail line inside the disc", (ft(metrorail.intersection(D).length) if not metrorail.is_empty else 0.0), "ft")
    G("rail", "existing Metromover guideway inside the disc (GTFS shapes, loops merged)", ft(gw_in), "ft")
    tshare = defaultdict(float)
    for r in zr: tshare[r["Transect_D"] or "unlabelled"] += r["share_of_disc"]
    G("zoning", "share of the disc by zoning transect (clipped polygons; unzoned remainder = water, right-of-way or layer gaps)", [[k, round(v, 3)] for k, v in sorted(tshare.items(), key=lambda kv: -kv[1])][:6])
    G("zoning", "zoning polygons listed", len(zr), "polygons")
    G("land_use", "largest existing land-use classes by share of the disc (county land-use layer)", [[r["LU"], r["DESCR"][:70], r["share_of_disc"]] for r in lur[:6]])
    G("land_use", "share of the disc that is water (land-use classes naming water)", round(sum(r["share_of_disc"] for r in lur if r["LU"] in WATER_LU), 3))
    G("parcels", "parcels inside the disc by land-use group (all parcels)", {g["group"]: g["parcels"] for g in objs["parcel_groups_all_parcels"]}, "parcels")
    G("parcels", "parcels listed individually / not listed because of the row cap", {"listed": len(sel), "cut_by_row_cap": dropped_parcels}, "parcels")
    cand = [p for p in sel if p["group"] in ("vacant", "parking") and (p["lot_size_sqft"] or 0) >= PC["module_footprint_sqft"]]
    G("parcels", f"listed vacant or parking parcels with a lot of at least {PC['module_footprint_sqft']} sq ft (the smallest platform module footprint); a count, not a site finding", len(cand), "parcels")
    res_t, job_t = sum(r["residents_2020"] for r in hc), sum(r["jobs_2023"] for r in hc); q = [r for r in hc if r["center_band"] in ("b1", "b2")]
    G("heat", "activity-density proxy: 2020 residents and 2023 jobs inside the listed cells (cells overlap the disc edge)", {"residents_2020": round(res_t), "jobs_2023": round(job_t)}, "count")
    G("heat", "jobs share of activity inside the listed cells", (round(job_t / (res_t + job_t), 3) if res_t + job_t > 0 else None))
    G("heat", "share of the listed cells' activity lying within a quarter mile of the reference point", (round(sum(r["residents_2020"] + r["jobs_2023"] for r in q) / (res_t + job_t), 3) if res_t + job_t > 0 else None))
    hot = [r for r in hc if r["is_hot"]]
    G("heat", "cells in the network top quintile of activity density (hot cells) among the listed cells", {"hot": len(hot), "listed": len(hc)}, "cells")
    G("heat", "hot cells by dominant zoning transect (heat and zoning read together; auxiliary evidence)", dict(Counter(r["dominant_zoning_transect"] or "unzoned" for r in hot).most_common()), "cells")
    G("heat", "hot cells touching a motorway / trunk road or rail", sum(1 for r in hot if r["highest_road_class"] in ("motorway", "motorway_link", "trunk", "trunk_link") or r["rail_in_cell"]), "cells")
    heat_dev[pid] = {"residents_cells": round(res_t), "jobs_cells": round(job_t)}
    station_blocks.append({"station_id": pid, "name": names[pid], "reference_point_note": "GTFS reference point; not an entrance", "objects": objs, "summary_facts": facts,
                           "counts": {k: len(v) for k, v in objs.items()}, "rows_cut": {"roads": dropped_roads, "parcels": dropped_parcels}})

# ---------------- validation ----------------
all_ids = [o["object_id"] for b in station_blocks for k, v in b["objects"].items() if k != "parcel_groups_all_parcels" for o in v] + [f["fact_id"] for b in station_blocks for f in b["summary_facts"]]
leak = [k for b in station_blocks for p in b["objects"]["parcels"] for k in p if any(w in k.lower() for w in ("owner", "mailing", "addr", "legal"))]
grid_res, grid_job = sum(c["residents_2020"] for c in cells.values()), sum(c["jobs_2023"] for c in cells.values())
blocks_in_union = [b for b in land if land[b].intersects(union)]
upper_res = sum(pop20.get(b, 0) for b in blocks_in_union)
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "stations": len(station_blocks), "object_ids_unique": len(all_ids) == len(set(all_ids)), "objects_total": len(all_ids),
       "every_station_has_roads_zoning_parcels_heat_blockgroups": all(all(b["counts"][k] > 0 for k in ("roads", "zoning", "parcels", "heat_cells", "block_groups", "land_use", "guideway")) for b in station_blocks),
       "zoning_clip_matches_spatial_join_package": {"max_deviation_share_of_disc": r6(zon_dev_max), "pass": zon_dev_max < 0.005},
       "parcels_carry_no_owner_or_address_fields": not leak, "blocks_without_2020_count": len(missing_pl),
       "heat_grid": {"cells": len(cells), "cells_with_density": len(ranked), "hot_cells": sum(1 for c in cells.values() if c["is_hot"]), "cell_size_ft": HP["cell_size_ft"],
                     "residents_in_grid": round(grid_res), "jobs_in_grid": round(grid_job), "residents_upper_bound_blocks_touching_union": upper_res},
       "heat_grid_residents_not_above_touching_blocks": grid_res <= upper_res + 1e-6, "every_cell_value_non_negative": all(c["residents_2020"] >= 0 and c["jobs_2023"] >= 0 for c in cells.values()),
       "dor_prefixes_not_in_config": dict(unseen_prefix), "county_rail_layer_split_mi": {"on_metromover_guideway": mi(rail_on_guideway.length), "on_metrorail": mi(rail_on_metrorail.length), "other_railroad": mi(rail_other.length)}, "role_hints": len(hints), "role_hints_shown_to_agents": False,
       "scope_statement": "PASS means the layers were clipped, joined and counted consistently and the privacy rule holds. The heat grid is a proxy built from public counts, not a measurement. "
                          "Object roles are read by the agents and confirmed by people; the hints here are only an evaluation aid."}
ok = (val["object_ids_unique"] and val["every_station_has_roads_zoning_parcels_heat_blockgroups"] and val["zoning_clip_matches_spatial_join_package"]["pass"] and val["parcels_carry_no_owner_or_address_fields"]
      and val["blocks_without_2020_count"] == 0 and val["heat_grid_residents_not_above_touching_blocks"] and val["every_cell_value_non_negative"] and len(station_blocks) == 21)
if os.environ.get("GIS_OBJECTS_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

cfg_sha = sha_file(CFG_FILE)
common = {"built_on": BUILT_ON, "config_version": cfg["version"], "config_sha256": cfg_sha, "demography_package": pk["demography"]["ptr"]["package_id"], "jobs_package": pk["jobs"]["ptr"]["package_id"],
          "spatial_join_package": pk["spatial_join"]["ptr"]["package_id"]}
SEM = {"provenance_class": "observed (features) + derived (clips, lengths, shares, proxy)", "principle": cfg["principle"], "heat_proxy": {k: HP[k] for k in ("metric", "label", "is_measured_ridership_heat", "is_persons_per_hour", "residents_source", "jobs_source", "hot_definition")},
       "parcel_privacy": PC["privacy"], "attribution": ["© OpenStreetMap contributors (ODbL)", "Miami-Dade County GIS", "City of Miami (Miami 21 zoning, CC-BY-4.0)", "U.S. Census Bureau (2020 P.L. 94-171, ACS, LEHD LODES)", "Miami-Dade Transit GTFS"]}
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_gis_objects.json", {"schema_version": "miami-station-gis-objects/1.0", **common, **SEM, "transform": transform_record, "environment": environment, "stations": station_blocks})
dump(STAGING / "heat_grid.json", {"schema_version": "miami-heat-proxy-grid/1.0", **common, **SEM["heat_proxy"], "crs": "EPSG:26917", "origin_m": [x0, y0], "cell_size_m": r6(CELL_M), "rows": nrow, "cols": ncol,
     "cells": [{**{k: v for k, v in c.items() if k != "geom"}, "bounds_m": [r2(x) for x in c["geom"].bounds]} for _, c in sorted(cells.items())]})
dump(STAGING / "object_role_hints.json", {"schema_version": "miami-object-role-hints/1.0", **common, **cfg["role_hints"], "hints": hints})
dump(STAGING / "gis_objects_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-gis-objects-manifest/1.0", "built_on": BUILT_ON, "build_status": val["build_status"], "validation_status": val["validation_status"],
            "ready_for_downstream": val["ready_for_downstream"], "consumed_inputs": consumed_inputs, "consumed_packages": [package_entry("demography"), package_entry("jobs"), package_entry("spatial_join")],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"), "config_sha256": cfg_sha, "config": cfg, "environment": environment, "transform": transform_record,
            "method_summary": "OSM roads, county rail, GTFS guideway shapes, Miami 21 zoning, county land use and parcels clipped to each half-mile disc with citable object ids; an activity-density heat proxy "
                              "(2020 block residents + 2023 block jobs per acre, 500 ft cells) with zoning, land use and road context per cell; role hints kept apart for evaluation",
            "contract": "coze/v2/DESIGN.md (reading agents G1, G2); rules doc 规则 4, 6", "publish_policy": "content-addressed immutable package dir gis_objects/pkg-<id>"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
c0 = station_blocks[11]["counts"]
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} stations={len(station_blocks)} objects={len(all_ids)} "
      f"grid={nrow}x{ncol} cells={len(cells)} hot={val['heat_grid']['hot_cells']} hints={len(hints)} zoning_dev={zon_dev_max:.5f} sample_counts_MM12={c0} unseen_dor_prefixes={dict(unseen_prefix)}")
