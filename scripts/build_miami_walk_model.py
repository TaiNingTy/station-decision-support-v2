#!/usr/bin/env python3
"""Miami · network walk model — V2 step 7c, stage `walk_model` (optional layer for AI interpretation).

Contract §5 (W01 = 15-minute walk isochrone area, W02 = population and jobs inside it with the §6 apportionment) and
rules doc 规则 6: a MODEL ESTIMATE, `catchment_type: network_walk_model`, `is_validated_walk_catchment: false`. Nothing
here proves that a passenger can enter the platform; entrances, legal crossings, vertical connections, access rights and
critical gaps are all `not_verified`.

What it does
  * Graph: OSM ways with a highway tag (raw/miami/2026-09-17/osm) filtered by a recorded walkability rule (W-A02); one
    edge per consecutive node pair, lengths in EPSG:26917; only the largest connected component is used.
  * Origin: the GTFS station reference point joined by a STRAIGHT line to the nearest walkable edge of the main component
    (entrance unknown, W-A03); the join length counts as walked distance.
  * Dijkstra at an assumed 3.0 mph (W-A01) with no crossing delay, slope or weather effect (W-A05). The reached network is
    the set of edge parts inside the time budget (partial edges cut exactly). Isochrone polygon = reached network buffered
    by 50 m (W-A04; 25 m and 100 m kept as a sensitivity range) for 5 / 10 / 15 minutes.
  * Population, households, workers: block-group ACS estimates × (block-group land inside the polygon ÷ block-group land),
    MOE by RSS — the demography stage's rule on the demography stage's land geometry. Jobs: LODES WAC C000 (JT00) × block
    land share — the jobs stage's rule. The half-mile Euclidean disc is recomputed with the same code and checked against
    the published profiles; the 10-minute polygon (= 0.5 mi of walking at 3 mph) is compared with that disc.
  * Nearest facility per POI category by NETWORK distance (poi package), next to the poi stage's straight-line value.
Publishes walk_model/pkg-<id>/ atomically (R3); readiness by scripts/miami_readiness.py (R2).
"""
import heapq, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403
from shapely import make_valid
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import nearest_points

STAGE = "walk_model"
STAGE_DIR = DATA / STAGE
STAGING = STAGE_DIR / ".staging"
OUTPUT_FILES = ["station_walk_profile.json", "walk_isochrones.geojson", "walk_network_summary.json", "walk_model_evidence.json", "walk_model_validation.json"]
OSM_RAW = RAW15.parent / "2026-09-17/osm"
WALK_SPEED_MPH = 3.0
WALK_SPEED_MPS = WALK_SPEED_MPH * 1609.344 / 3600.0
THRESHOLDS_MIN = [5, 10, 15]
BUFFER_M, BUFFER_SENS_M = 50.0, [25.0, 100.0]
POI_CUTOFF_M = 4000.0
SNAP_MAX_M = 200.0
PARK_NODE_TOL_M = 15.0
MIN_REACH_MI_15 = 3.0
CATEGORIES = ["school", "clinic", "grocery", "park"]
WALKABLE = {"footway", "path", "pedestrian", "steps", "living_street", "residential", "unclassified", "tertiary", "tertiary_link", "secondary", "secondary_link",
            "primary", "primary_link", "service", "track", "cycleway", "corridor", "crossing", "road"}
ASSUMPTIONS = {
    "W-A01": {"name": "walk_speed", "value": WALK_SPEED_MPH, "unit": "mph", "note": "average adult walking speed used by many US transit sketch tools; not measured locally"},
    "W-A02": {"name": "walkable_way_rule", "value": "highway tag in the walkable set; excluded when foot=no|private, or access=no|private without foot=yes|designated|permissive",
              "walkable_set": sorted(WALKABLE), "note": "motorway/trunk (and links), construction, proposed, busway, raceway, bridleway are never walkable; sidewalk=no is NOT used to exclude a road"},
    "W-A03": {"name": "origin_and_snapping", "value": "GTFS reference point joined by a straight line to the nearest walkable edge of the main network component; the join length is walked",
              "note": "the reference point is not an entrance; elevated platforms, stairs and elevators are not modelled"},
    "W-A04": {"name": "isochrone_polygon", "value": BUFFER_M, "unit": "m buffer around the reached network", "sensitivity_m": BUFFER_SENS_M,
              "note": "the polygon area and the counts inside it depend on this width; the reached network length does not"},
    "W-A05": {"name": "no_delays", "value": "no waiting at crossings, no slope, no weather, no crowding", "note": "so every time is a lower bound on real walking time"},
    "W-A06": {"name": "osm_completeness", "value": "OpenStreetMap as of the response's osm_base timestamp (Overpass mirror, lags the live map)", "note": "unmapped paths or barriers change the result"},
    "W-A07": {"name": "areal_interpolation", "value": "block-group / block estimates spread evenly over their LAND (water erased)", "note": "identical to the demography and jobs stages (rules doc 规则 4)"}}
SEMANTICS = {"catchment_type": "network_walk_model", "is_validated_walk_catchment": False, "provenance_class": "derived", "data_nature": "model_output",
             "distance_type": "network_walk", "distance_origin": "GTFS station reference point joined by a straight line to the nearest walkable OSM edge (not an entrance)",
             "validation_checklist": {k: "not_verified" for k in ("entrance", "legal_crossings", "vertical_connections", "access_rights", "critical_gaps")},
             "attribution": "© OpenStreetMap contributors (ODbL 1.0)", "is_ridership": False}

environment = lock_gate()
fwd, inv, transform_record = projection()
proj = lambda g: shp_transform(fwd.transform, g)
unproj = lambda g: shp_transform(inv.transform, g)

# ---------------- consumed inputs + packages ----------------
osm_manifest = load(OSM_RAW / "osm_source_manifest.json"); osm_file = OSM_RAW.parent / osm_manifest["files"]["response"]["file"]
if sha_file(osm_file) != osm_manifest["files"]["response"]["sha256"]: raise SystemExit("HALT: OSM response sha256 != osm_source_manifest.json")
consumed_inputs = [consumed_entry("osm_source_manifest", OSM_RAW / "osm_source_manifest.json"), consumed_entry("osm_walk_network_response", osm_file),
                   consumed_entry("station_master", DATA / "station_master.geojson"), consumed_entry("study_window", DATA / "study_window.geojson")]
pkg = {}
for stage, mname in (("demography", "manifest.json"), ("jobs", "manifest.json"), ("poi", "manifest.json")):
    ptr = load(DATA / f"{stage}_current.json"); d = DATA / ptr["package_dir"]; ok, m, problems = verify_package(d, mname)
    if not ok: raise SystemExit(f"HALT: {stage} package does not verify: {problems}")
    pkg[stage] = {"dir": d, "ptr": ptr}
dem_dir, jobs_dir, poi_dir = pkg["demography"]["dir"], pkg["jobs"]["dir"], pkg["poi"]["dir"]
tg = load(dem_dir / "analysis_targets_26917.json"); RADII_FT = tg["bands"]["radii_ft"]; HALF_MILE_M = RADII_FT[2] * FOOT_M
disc = {t["station_id"]: shape(t["geometry"]) for t in tg["targets"].values() if t["band_id"] == "cum"}
blg = load(dem_dir / "block_land_geometry.json"); bgv = load(dem_dir / "block_group_values.json"); dem_profile = load(dem_dir / "station_demography_profile.json")
land = {bid: shape(b["geometry"]) for bid, b in blg["blocks"].items()}; block_bg = {bid: b["bg"] for bid, b in blg["blocks"].items()}
bg_land = {bg: rec["land_area_m2_erased"] for bg, rec in bgv["block_groups"].items()}
jobs_values = load(jobs_dir / "block_values.json"); jobs_profile = load(jobs_dir / "station_jobs_profile.json")
poi_feats = load(poi_dir / "poi_features.json"); poi_profile = load(poi_dir / "station_poi_profile.json")
stations = load(DATA / "station_master.geojson")["features"]
st_pt = {f["properties"]["station_id"]: proj(shape(f["geometry"])) for f in stations}; names = {f["properties"]["station_id"]: f["properties"]["name"] for f in stations}
ids = sorted(st_pt)
window = proj(shape(load(DATA / "study_window.geojson")["features"][0]["geometry"]))
ACS_IND = {"D01": ("population_total", "persons"), "D02": ("households", "households"), "D06": ("workers_16_plus", "workers")}

# ---------------- OSM graph ----------------
osm = load(osm_file); els = osm["elements"]
node_ll = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
ways = [e for e in els if e["type"] == "way"]
nid = sorted(node_ll); xs, ys = fwd.transform([node_ll[n][0] for n in nid], [node_ll[n][1] for n in nid])
xy = {n: (x, y) for n, x, y in zip(nid, xs, ys)}


def walkable(tags):
    hw = tags.get("highway"); foot = tags.get("foot"); access = tags.get("access")
    if hw not in WALKABLE: return False, f"highway={hw}"
    if foot in ("no", "private"): return False, f"foot={foot}"
    if access in ("no", "private") and foot not in ("yes", "designated", "permissive"): return False, f"access={access}"
    return True, None


edges, adj, excluded_ways, walk_ways = [], defaultdict(list), Counter(), Counter()
for w in ways:
    ok, why = walkable(w.get("tags", {}))
    if not ok: excluded_ways[why] += 1; continue
    walk_ways[w["tags"].get("highway")] += 1
    ns = [n for n in w["nodes"] if n in xy]
    for u, v in zip(ns, ns[1:]):
        if u == v: continue
        L = math.hypot(xy[v][0] - xy[u][0], xy[v][1] - xy[u][1])
        if L <= 0: continue
        eid = len(edges); edges.append((u, v, L, w["id"], w["tags"].get("highway"))); adj[u].append((v, L, eid)); adj[v].append((u, L, eid))
# connected components (by walkable length); only the largest is used
comp_of, comps = {}, []
for start in adj:
    if start in comp_of: continue
    cid = len(comps); stack = [start]; comp_of[start] = cid; length = 0.0; n_nodes = 0
    while stack:
        u = stack.pop(); n_nodes += 1
        for v, L, eid in adj[u]:
            length += L / 2.0
            if v not in comp_of: comp_of[v] = cid; stack.append(v)
    comps.append({"nodes": n_nodes, "length_m": length})
giant = max(range(len(comps)), key=lambda i: comps[i]["length_m"])
total_len = sum(c["length_m"] for c in comps); giant_share = comps[giant]["length_m"] / total_len if total_len else 0.0
g_edges = [eid for eid, (u, v, L, wid, hw) in enumerate(edges) if comp_of.get(u) == giant]
edge_geom = {eid: LineString([xy[edges[eid][0]], xy[edges[eid][1]]]) for eid in g_edges}
edge_tree = STRtree([edge_geom[eid] for eid in g_edges])
g_nodes = [n for n in adj if comp_of.get(n) == giant]; node_tree = STRtree([Point(xy[n]) for n in g_nodes])


def snap(pt):
    """Nearest walkable edge of the main component: (eid, straight-line snap distance, along-distance from u)."""
    i = int(edge_tree.query_nearest(pt)[0]); eid = g_edges[i]; line = edge_geom[eid]
    return eid, pt.distance(line), line.project(pt)


def dijkstra(pt, cutoff):
    """Network distance (m) from a point joined to the graph at its snap edge; the snap leg is walked in a straight line."""
    eid, ds, along = snap(pt); u, v, L, wid, hw = edges[eid]
    dist = {u: ds + along, v: ds + (L - along)}; heap = [(dist[u], u), (dist[v], v)]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist.get(n, math.inf) or d > cutoff: continue
        for m, L2, e2 in adj[n]:
            nd = d + L2
            if nd < dist.get(m, math.inf) and nd <= cutoff: dist[m] = nd; heapq.heappush(heap, (nd, m))
    return dist, (eid, ds, along)


def reached_pieces(dist, snap_info, budget):
    """Parts of edges within `budget` metres of the origin: list of (LineString, length)."""
    seid, ds, along = snap_info; pieces = []
    for eid in g_edges:
        u, v, L, wid, hw = edges[eid]; du, dv = dist.get(u), dist.get(v); ivs = []
        if eid == seid and budget > ds: ivs.append((max(0.0, along - (budget - ds)), min(L, along + (budget - ds))))
        if du is not None and du < budget: ivs.append((0.0, min(L, budget - du)))
        if dv is not None and dv < budget: ivs.append((max(0.0, L - (budget - dv)), L))
        if not ivs: continue
        ivs.sort(); merged = [list(ivs[0])]
        for a, b in ivs[1:]:
            if a <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], b)
            else: merged.append([a, b])
        (xu, yu), (xv, yv) = xy[u], xy[v]
        for a, b in merged:
            if b - a <= 0: continue
            p = lambda s: (xu + (xv - xu) * s / L, yu + (yv - yu) * s / L)
            pieces.append((LineString([p(a), p(b)]), b - a))
    return pieces


def polygon_of(pieces, buffer_m):
    g = polygonal(make_valid(MultiLineString([ln for ln, _ in pieces]).buffer(buffer_m, quad_segs=8)))
    return polygonal(make_valid(g.intersection(window)))


# ---------------- POI snap points (network targets) ----------------
poi_pts, park_polys = {}, {}
for r in poi_feats["features"]:
    if r["category"] == "park" and r.get("geometry_wgs84"): park_polys[r["poi_id"]] = (r, proj(shape(r["geometry_wgs84"])))
    else: poi_pts[r["poi_id"]] = (r, Point(fwd.transform(r["lon"], r["lat"])))
poi_snap = {pid_: (snap(pt), pt) for pid_, (r, pt) in poi_pts.items()}
park_nodes = {}
for pid_, (r, poly) in park_polys.items():
    buf = poly.buffer(PARK_NODE_TOL_M); park_nodes[pid_] = [g_nodes[int(i)] for i in node_tree.query(buf) if buf.contains(Point(xy[g_nodes[int(i)]]))]


def network_to_point(dist, s, pt):
    (eid, ds, along), _ = s, None; u, v, L, wid, hw = edges[eid]; cands = []
    if dist.get(u) is not None: cands.append(dist[u] + along)
    if dist.get(v) is not None: cands.append(dist[v] + (L - along))
    return (min(cands) + ds) if cands else None


def nearest_by_network(pid, dist):
    out = {}; origin = st_pt[pid]; sl = poi_profile_by[pid]["nearest_by_category"]
    for c in CATEGORIES:
        best = None
        for pid_, (r, pt) in poi_pts.items():
            if r["category"] != c: continue
            d = network_to_point(dist, poi_snap[pid_][0], pt)
            if d is not None and (best is None or d < best[0]): best = (d, r, origin.distance(pt))
        if c == "park":
            for pid_, (r, poly) in park_polys.items():
                ds_ = [dist[n] for n in park_nodes[pid_] if n in dist]
                if ds_: d = min(ds_)
                else:
                    edge_pt = nearest_points(origin, poly)[1]; d = network_to_point(dist, snap(edge_pt), edge_pt)
                if d is not None and (best is None or d < best[0]): best = (d, r, origin.distance(poly))
        if best is None:
            out[c] = {"value_status": "not_reached_within_cutoff", "cutoff_ft": round(POI_CUTOFF_M / FOOT_M), "distance_type": "network_walk"}
        else:
            d, r, straight = best; slid = sl[c].get("poi_id")
            out[c] = {"poi_id": r["poi_id"], "name": r["name"], "network_distance_ft": round(d / FOOT_M, 1), "network_distance_m": r2(d), "display_mi": round(d / FOOT_M / 5280.0, 3),
                      "walk_minutes_at_assumed_speed": round(d / WALK_SPEED_MPS / 60.0, 1), "straight_line_ft_same_facility": round(straight / FOOT_M, 1),
                      "detour_ratio": (round(d / straight, 2) if straight > 0 else None), "same_facility_as_straight_line_nearest": (r["poi_id"] == slid),
                      "straight_line_nearest_poi_id": slid, "value_status": "value", "distance_type": "network_walk",
                      "note": ("park: network distance to the nearest walkable node inside or within 15 m of the park polygon" if c == "park" else
                               "network distance via the nearest walkable edges at both ends; both joins are straight lines")}
    return out


# ---------------- apportionment (same rule and geometry as the demography and jobs stages) ----------------
def acs_env(iid, shares):
    name, unit = ACS_IND[iid]
    est, moe, used, missing, moe_missing = combine_sum((w, bgv["block_groups"][bg]["indicators"][iid]["value"], bgv["block_groups"][bg]["indicators"][iid]["moe"]) for bg, w in shares.items())
    cv, flag = reliability(est if used else None, None if moe_missing else moe)
    return {"indicator_id": iid, "name": name, "unit": unit, "value": (r2(est) if used else None), "display_value": (round(est) if used else None),
            "moe_90": (r2(moe) if used and not moe_missing else None), "moe_status": ("approximate_sampling_only_excludes_interpolation" if used and not moe_missing else "not_applicable"),
            "cv": cv, "reliability_flag": flag, "value_status": ("value" if used else "missing"), "contributing_block_groups": used, "block_groups_missing_value": missing,
            "provenance_class": "derived", "data_nature": "survey_estimate", "period": "2020-2024", "is_current_population": False}


def jobs_env(block_shares):
    tot, n_rows, absent = 0.0, 0, 0
    for b, w in block_shares.items():
        rec = jobs_values["blocks"].get(b)
        if rec is None or rec["wac"]["JT00"]["value_status"] != "value": absent += 1; continue
        tot += w * rec["wac"]["JT00"]["values"]["C000"]; n_rows += 1
    return {"indicator_id": "W02_jobs", "name": "jobs_by_workplace_C000_JT00", "unit": "jobs", "value": r2(tot), "display_value": round(tot), "value_status": "value",
            "moe_status": "not_applicable", "blocks_with_wac_row": n_rows, "blocks_zero_absent_from_file": absent, "provenance_class": "derived", "data_nature": "administrative_modeled",
            "source": "LODES 8 (2023) WAC, all jobs, via the jobs package", "is_ridership": False}


def apportion(hits):
    """hits: {block: land area inside target}. Returns block-group shares, block shares and the land area inside."""
    by_bg = defaultdict(float)
    for b, a in hits.items(): by_bg[block_bg[b]] += a
    bg_shares = {bg: (a / bg_land[bg] if bg_land[bg] > 0 else 0.0) for bg, a in sorted(by_bg.items())}
    blk_shares = {b: (a / blg["blocks"][b]["land_area_m2"] if blg["blocks"][b]["land_area_m2"] > 0 else 0.0) for b, a in sorted(hits.items())}
    return bg_shares, blk_shares, sum(hits.values())


def counts_block(hits):
    bg_shares, blk_shares, land_m2 = apportion(hits)
    return {"land_area_m2": r6(land_m2), "display": {"land_area": disp_area(land_m2)}, **{ACS_IND[i][0]: acs_env(i, bg_shares) for i in ACS_IND}, "jobs_wac_JT00": jobs_env(blk_shares),
            "source_units": {"block_groups": len(bg_shares), "blocks": len(blk_shares)}}, bg_shares, blk_shares


# ---------------- per station ----------------
poi_profile_by = {s["station_id"]: s for s in poi_profile["stations"]}
dem_by = {s["station_id"]: s for s in dem_profile["stations"]}; jobs_by = {s["station_id"]: s for s in jobs_profile["stations"]}
targets, iso_meta, station_tmp = {}, {}, {}
for pid in ids:
    dist, sinfo = dijkstra(st_pt[pid], POI_CUTOFF_M); eid, ds, along = sinfo
    station_tmp[pid] = {"dist": dist, "snap": sinfo, "pieces": {}}
    for T in THRESHOLDS_MIN:
        budget = T * 60.0 * WALK_SPEED_MPS; pieces = reached_pieces(dist, sinfo, budget); station_tmp[pid]["pieces"][T] = pieces
        poly = polygon_of(pieces, BUFFER_M); targets[(pid, T, BUFFER_M)] = poly
        iso_meta[(pid, T, BUFFER_M)] = {"network_length_m": sum(l for _, l in pieces), "polygon_area_m2": poly.area, "budget_m": budget}
        if T == THRESHOLDS_MIN[-1]:
            for bm in BUFFER_SENS_M:
                p2 = polygon_of(pieces, bm); targets[(pid, T, bm)] = p2; iso_meta[(pid, T, bm)] = {"network_length_m": iso_meta[(pid, T, BUFFER_M)]["network_length_m"], "polygon_area_m2": p2.area, "budget_m": budget}
    targets[(pid, "disc", None)] = disc[pid]
inter = intersections_by_target(land, targets)

profiles, evidence, geo_features = [], [], []
def published_cum(pid):
    d = dem_by[pid]["cumulative_0_to_half_mile"]["counts"]; j = jobs_by[pid]["cumulative_0_to_half_mile"]["jobs_by_workplace"]["JT00"]
    c000 = j.get("C000"); c000 = c000.get("value") if isinstance(c000, dict) else (j.get("values", {}).get("C000") if isinstance(j.get("values"), dict) else None)
    return {"population_total": d["D01"]["value"], "households": d["D02"]["value"], "workers_16_plus": d["D06"]["value"], "jobs_wac_JT00": c000}


for pid in ids:
    t = station_tmp[pid]; eid, ds, along = t["snap"]; u, v, L, wid, hw = edges[eid]
    disc_block, _, _ = counts_block(inter[(pid, "disc", None)]); pub = published_cum(pid)
    disc_dev = {k: (None if pub[k] is None or disc_block[k]["value"] is None else r2(abs(disc_block[k]["value"] - pub[k]))) for k in pub}
    isos = {}
    for T in THRESHOLDS_MIN:
        key = (pid, T, BUFFER_M); blk, bg_shares, blk_shares = counts_block(inter[key]); meta = iso_meta[key]
        isos[f"{T}_min"] = {"minutes": T, "walk_distance_budget_ft": round(meta["budget_m"] / FOOT_M), "walk_distance_budget_mi": round(meta["budget_m"] / FOOT_M / 5280.0, 3),
                            **({"indicator_id": "W01"} if T == 15 else {}), "network_length_reached_mi": round(meta["network_length_m"] / FOOT_M / 5280.0, 3),
                            "polygon_area_m2": r6(meta["polygon_area_m2"]), "display_polygon_area": disp_area(meta["polygon_area_m2"]), "polygon_buffer_m": BUFFER_M, "value_status": "value", **blk}
        if T == 15:
            isos["15_min"]["sensitivity_by_buffer_m"] = {}
            for bm in [BUFFER_M] + BUFFER_SENS_M:
                b2, _, _ = counts_block(inter[(pid, T, bm)]); m2 = iso_meta[(pid, T, bm)]
                isos["15_min"]["sensitivity_by_buffer_m"][str(int(bm))] = {"polygon_area_acres": round(m2["polygon_area_m2"] / ACRE_M2, 2), "land_area_acres": round(b2["land_area_m2"] / ACRE_M2, 2),
                                                                             "population_total": b2["population_total"]["value"], "jobs_wac_JT00": b2["jobs_wac_JT00"]["value"]}
        for bg, w in bg_shares.items():
            evidence.append({"evidence_id": f"{pid}|iso{T}|BG{bg}", "station_id": pid, "isochrone_minutes": T, "unit_type": "block_group", "unit_id": bg, "share_of_unit_land_in_polygon": r6(w),
                             "used_for": "population_total, households, workers_16_plus"})
        for b, w in blk_shares.items():
            evidence.append({"evidence_id": f"{pid}|iso{T}|BLK{b}", "station_id": pid, "isochrone_minutes": T, "unit_type": "block", "unit_id": b, "share_of_unit_land_in_polygon": r6(w), "used_for": "jobs_wac_JT00"})
        geo_features.append({"type": "Feature", "properties": {"station_id": pid, "name": names[pid], "minutes": T, "walk_speed_mph": WALK_SPEED_MPH, "polygon_buffer_m": BUFFER_M,
                                                               "polygon_area_acres": round(meta["polygon_area_m2"] / ACRE_M2, 2), **SEMANTICS}, "geometry": mapping(unproj(targets[key]))})
    ten, disc_vals = isos["10_min"], disc_block
    ratio = lambda k: (r6(ten[k]["value"] / disc_vals[k]["value"]) if disc_vals[k]["value"] else None)
    profiles.append({"station_id": pid, "name": names[pid], **SEMANTICS, "walk_speed_mph": WALK_SPEED_MPH,
                     "snap": {"snap_distance_ft": round(ds / FOOT_M, 1), "snap_distance_m": r2(ds), "osm_way_id": wid, "highway": hw, "assumption_id": "W-A03",
                              "note": "straight line from the reference point to the nearest walkable edge of the main component; not an entrance"},
                     "isochrones": isos,
                     "half_mile_euclidean_disc_same_method": {**disc_vals, "cross_check_vs_published_profiles": {"abs_deviation": disc_dev, "published": pub},
                                                              "note": "the 0.5 mi straight-line disc apportioned by this script; deviations from the demography / jobs packages are rounding only"},
                     "equal_distance_comparison": {"note": f"10 minutes at {WALK_SPEED_MPH} mph = 0.5 mi of walking, the same distance budget as the 0.5 mi straight-line disc; ratios < 1 measure what the "
                                                           "street network, the river, the bay and the expressways take away from the disc",
                                                   "land_area_ratio": (r6(ten["land_area_m2"] / disc_vals["land_area_m2"]) if disc_vals["land_area_m2"] else None),
                                                   "population_ratio": ratio("population_total"), "households_ratio": ratio("households"), "workers_ratio": ratio("workers_16_plus"), "jobs_ratio": ratio("jobs_wac_JT00"),
                                                   "provenance_class": "derived", "value_status": "value"},
                     "nearest_by_category_network": nearest_by_network(pid, t["dist"])})

# ---------------- validation ----------------
def nested(p, key):
    vals = [p["isochrones"][f"{T}_min"][key] if not isinstance(p["isochrones"][f"{T}_min"][key], dict) else p["isochrones"][f"{T}_min"][key]["value"] for T in THRESHOLDS_MIN]
    return all(a <= b + 1e-6 for a, b in zip(vals, vals[1:]))
ten_inside = {}
for pid in ids:
    ds = station_tmp[pid]["snap"][1]; budget = 10 * 60.0 * WALK_SPEED_MPS
    allowed = st_pt[pid].buffer(budget + BUFFER_M + 1.0, quad_segs=64)   # every reached point is within `budget` straight-line of the origin (the snap leg is straight and counted)
    ten_inside[pid] = r6(targets[(pid, 10, BUFFER_M)].difference(allowed).area)
all_shares = [w for k in targets for w in apportion(inter[k])[0].values()] + [w for k in targets for w in apportion(inter[k])[1].values()]
max_disc_dev = max((v for p in profiles for v in p["half_mile_euclidean_disc_same_method"]["cross_check_vs_published_profiles"]["abs_deviation"].values() if v is not None), default=None)
disc_dev_missing = any(v is None for p in profiles for v in p["half_mile_euclidean_disc_same_method"]["cross_check_vs_published_profiles"]["abs_deviation"].values())
val = {"build_status": None, "validation_status": None, "ready_for_downstream": False,
       "graph": {"ways_total": len(ways), "ways_walkable": sum(walk_ways.values()), "ways_excluded": sum(excluded_ways.values()), "edges_main_component": len(g_edges),
                 "components": len(comps), "main_component_share_of_walkable_length": r6(giant_share), "walkable_length_mi": round(total_len / FOOT_M / 5280.0, 2)},
       "main_component_holds_at_least_90_percent": giant_share >= 0.9,
       "every_station_snapped_within_200m": all(p["snap"]["snap_distance_m"] <= SNAP_MAX_M for p in profiles), "max_snap_distance_m": max(p["snap"]["snap_distance_m"] for p in profiles),
       "every_station_reaches_min_network_in_15_min": all(p["isochrones"]["15_min"]["network_length_reached_mi"] >= MIN_REACH_MI_15 for p in profiles),
       "min_network_reached_mi_15": min(p["isochrones"]["15_min"]["network_length_reached_mi"] for p in profiles),
       "thresholds_nested": all(nested(p, "polygon_area_m2") and nested(p, "network_length_reached_mi") and nested(p, "population_total") and nested(p, "jobs_wac_JT00") for p in profiles),
       "ten_min_polygon_inside_half_mile_plus_buffer": {"max_outside_area_m2": max(ten_inside.values()), "pass": max(ten_inside.values()) < 1.0},
       "disc_recompute_matches_published_profiles": {"max_abs_deviation": max_disc_dev, "pass": (not disc_dev_missing) and max_disc_dev is not None and max_disc_dev <= 1.0},
       "shares_in_unit_interval": all(0.0 <= w <= 1.0 + 1e-9 for w in all_shares),
       "polygons_valid_nonempty": all(g.is_valid and not g.is_empty for k, g in targets.items() if k[1] != "disc"),
       "network_not_below_straight_line": all(n["network_distance_ft"] + 1e-6 >= n["straight_line_ft_same_facility"] for p in profiles for n in p["nearest_by_category_network"].values() if n["value_status"] == "value"),
       "every_station_present": len(profiles) == 21, "evidence_rows": len(evidence),
       "scope_statement": "PASS means the graph, snapping, nesting, geometric-bound, share and cross-check tests listed here passed. It is a model estimate on OpenStreetMap "
                          "with assumed speed and no delays; it is not a validated walk catchment, not an entrance survey, not ridership."}
ok = (val["main_component_holds_at_least_90_percent"] and val["every_station_snapped_within_200m"] and val["every_station_reaches_min_network_in_15_min"] and val["thresholds_nested"]
      and val["ten_min_polygon_inside_half_mile_plus_buffer"]["pass"] and val["disc_recompute_matches_published_profiles"]["pass"] and val["shares_in_unit_interval"]
      and val["polygons_valid_nonempty"] and val["network_not_below_straight_line"] and val["every_station_present"])
if os.environ.get("WALK_MODEL_FORCE_FAIL") == "1": ok = False; val["injected_failure_for_test"] = True
val["validation_status"] = "PASS" if ok else "FAIL"; val["build_status"] = "COMPLETED" if ok else "FAILED"; val["ready_for_downstream"] = bool(ok)

# ---------------- outputs ----------------
config = {"walk_speed_mph": WALK_SPEED_MPH, "walk_speed_m_per_s": r6(WALK_SPEED_MPS), "thresholds_min": THRESHOLDS_MIN, "polygon_buffer_m": BUFFER_M, "polygon_buffer_sensitivity_m": BUFFER_SENS_M,
          "poi_network_cutoff_m": POI_CUTOFF_M, "snap_max_m": SNAP_MAX_M, "park_node_tolerance_m": PARK_NODE_TOL_M, "min_network_reached_mi_15": MIN_REACH_MI_15,
          "walkable_rule": ASSUMPTIONS["W-A02"], "assumptions": ASSUMPTIONS, "osm": {"osm_base": osm_manifest["osm_data_timestamp"], "fetch_bbox_wgs84": osm_manifest["fetch_bbox_wgs84"], "query": osm_manifest["query"]},
          "geometry_source": "demography package block_land_geometry.json + analysis_targets_26917.json (EPSG:26917); jobs package block_values.json; poi package poi_features.json"}
config_sha = sha_obj(config)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "demography_package": pkg["demography"]["ptr"]["package_id"], "jobs_package": pkg["jobs"]["ptr"]["package_id"], "poi_package": pkg["poi"]["ptr"]["package_id"]}
network_summary = {"schema_version": "miami-walk-network-summary/1.0", **common, "osm_base": osm_manifest["osm_data_timestamp"], "attribution": SEMANTICS["attribution"],
                   "ways_total": len(ways), "ways_walkable_by_highway": dict(walk_ways.most_common()), "ways_excluded_by_reason": dict(excluded_ways.most_common()),
                   "nodes_total": len(node_ll), "edges_walkable": len(edges), "edges_main_component": len(g_edges), "components": len(comps),
                   "main_component": {"nodes": comps[giant]["nodes"], "length_mi": round(comps[giant]["length_m"] / FOOT_M / 5280.0, 2), "share_of_walkable_length": r6(giant_share)},
                   "walkable_length_mi": round(total_len / FOOT_M / 5280.0, 2), "walkable_rule": ASSUMPTIONS["W-A02"]}
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
dump(STAGING / "station_walk_profile.json", {"schema_version": "miami-station-walk-profile/1.0", **common, **SEMANTICS, "config": config, "transform": transform_record, "environment": environment,
     "network": {"stations": len(profiles), "summary_file": "walk_network_summary.json"}, "stations": profiles})
dump(STAGING / "walk_isochrones.geojson", {"type": "FeatureCollection", "name": "miami_walk_isochrones_network_walk_model", "crs_note": "WGS84 (EPSG:4326) for maps; computed in EPSG:26917",
     "attribution": SEMANTICS["attribution"], **{k: v for k, v in common.items()}, "features": geo_features})
dump(STAGING / "walk_network_summary.json", network_summary)
dump(STAGING / "walk_model_evidence.json", {"schema_version": "miami-walk-model-evidence/1.0", **common, "rows": evidence,
     "note": "one row per (station, isochrone, block group) for the ACS indicators and per (station, isochrone, block) for jobs; share × unit value is the contribution. Cite evidence_id."})
dump(STAGING / "walk_model_validation.json", val)
if not ok: fail_and_exit(STAGE, STAGING, "validation failed", {"validation": val})
manifest = {"stage": STAGE, "schema_version": "miami-walk-model-manifest/1.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "validation_status": val["validation_status"], "ready_for_downstream": val["ready_for_downstream"],
            "consumed_inputs": consumed_inputs, "consumed_packages": [package_entry("demography"), package_entry("jobs"), package_entry("poi")],
            "code": code_entries(Path(__file__), ROOT / "scripts/miami_v2_common.py", ROOT / "scripts/miami_readiness.py"),
            "config_sha256": config_sha, "config": config, "environment": environment, "transform": transform_record,
            "assumption_parameter_ids": sorted(ASSUMPTIONS),
            "method_summary": "OSM walkable graph, Dijkstra at an assumed 3 mph from the snapped reference point, 5/10/15-minute reached network buffered by 50 m; ACS and LODES "
                              "apportioned by land share exactly as the demography and jobs stages; network distance to the nearest facility per POI category",
            "contract": "V2_站点输入包字段契约.md §5 (W01, W02), §6; rules doc 规则 6",
            "publish_policy": "content-addressed immutable package dir walk_model/pkg-<id>; readers resolve walk_model_current.json and verify the whole package"}
package_id, reused, switched = publish_package(STAGE, STAGING, OUTPUT_FILES, manifest)
p15 = [p["isochrones"]["15_min"] for p in profiles]
print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} stations={len(profiles)} "
      f"walkable_ways={sum(walk_ways.values())}/{len(ways)} main_component_share={giant_share:.3f} max_snap_m={val['max_snap_distance_m']} "
      f"area15_acres=[{min(x['display_polygon_area']['acres'] for x in p15)}..{max(x['display_polygon_area']['acres'] for x in p15)}] "
      f"pop_ratio10=[{min(p['equal_distance_comparison']['population_ratio'] for p in profiles)}..{max(p['equal_distance_comparison']['population_ratio'] for p in profiles)}] evidence_rows={len(evidence)}")
