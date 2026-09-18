#!/usr/bin/env python3
"""Miami · station statutory-zoning profiles — spatial-join stage (v1.2, post-recheck).

Stage contract
  * Products are published as an IMMUTABLE, content-addressed package data/miami/2026-09-14/spatial_join/pkg-<id>/
    (8 outputs + spatial_join_manifest.json). The only mutable file is spatial_join_current.json, switched with ONE
    atomic os.replace after the whole package is written and verified (R3). Previous packages stay as the archive
    (update-build + archive, F2): every package records the actual script sha256 + config sha256.
  * Build in a staging dir inside spatial_join/; publish ONLY if validation passes (F1). On a validation failure or
    an interrupted publish: failure log under failed/, current package and pointer untouched, exit 1.
  * Records the sha256 of EVERY input it consumed (station_master, study_window, raw zoning). scripts/miami_readiness.py
    compares each with the current file and marks this stage STALE when any of them changes (R1, F3).
  * Does NOT write gis_data_readiness.json; that derived view has a single writer, scripts/miami_readiness.py (R2).
  * Dependency lock enforced from requirements-gis.lock.txt (U3). Test hook: SPATIAL_JOIN_FORCE_FAIL=1.

Semantics locked with the reviewer (2026-09-14)
  * Imperial-defined bands 1/8, 1/4, 1/2 mile (660/1320/2640 ft), international foot 0.3048 m exact;
    Euclidean distance bands from the GTFS reference point — NOT walk catchments.
  * EPSG:26917; the actual datum operation, its reported accuracy and grid use are recorded from PROJ.
  * Clipped geometry; coverage = union area / band area; per original M21_ZONE / Transect_D; no use
    mapping; no exclusion. Coverage ratios are NON-EXCLUSIVE and are NOT allocation weights (U1).
  * Per-band, per-FID evidence rows are saved for click-through provenance (U2).
"""
import json, hashlib, sys, os, math, platform, shutil, time
from pathlib import Path
from collections import defaultdict
import shapely
from shapely import make_valid, geos_version_string
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import transform as shp_transform, unary_union
from shapely.validation import explain_validity
import pyproj
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/miami/2026-09-14"
RAW = ROOT / "raw/miami/2026-09-14"
SJ_DIR = DATA / "spatial_join"                 # immutable content-addressed packages: spatial_join/pkg-<id>/
STAGING = SJ_DIR / ".staging"                  # same filesystem as SJ_DIR, so the final os.rename is atomic
FAILED_DIR = DATA / "failed"
POINTER = DATA / "spatial_join_current.json"   # the ONLY mutable file of this stage
MANIFEST_NAME = "spatial_join_manifest.json"
LOCK = ROOT / "requirements-gis.lock.txt"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_readiness import aggregate, verify_package   # single writer of readiness; whole-package verifier

# ---------------- configuration (imperial is the single source of truth) ----------------
RADII_FT = [660, 1320, 2640]
FOOT_M = 0.3048
RADII_M = [r * FOOT_M for r in RADII_FT]
BAND_KEYS = ["b1", "b2", "b3"]
BAND_LABELS = ["0-1/8 mi", "1/8-1/4 mi", "1/4-1/2 mi"]
QUAD_SEGS = 64
AREA_TOL_M2 = 1e-6
SRC_CRS, DST_CRS = "EPSG:4326", "EPSG:26917"
SQFT_PER_M2 = 1.0 / (FOOT_M ** 2)
ACRE_M2 = 43560.0 * FOOT_M ** 2
SQMI_M2 = (5280.0 * FOOT_M) ** 2
BUILT_ON = "2026-09-14"
OUTPUT_FILES = ["station_zoning_profile.json", "station_catchments.geojson", "station_overlap.json",
                "network_half_mile_union.geojson", "station_zoning_evidence.json",
                "station_point_zoning_match.json", "spatial_join_validation.json", "geometry_quality_report.json"]
SEMANTIC_FLAGS = {"catchment_type": "euclidean_distance_band_from_gtfs_reference_point",
                  "is_validated_walk_catchment": False, "demand_origin_or_destination": "TO_BE_EVALUATED",
                  "is_population_allocation_weight": False}

def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sha_obj(o): return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p, obj): Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def die(msg):
    print("HALT:", msg); sys.exit(1)
def r6(x): return round(float(x), 6)
def disp_len(m): return {"ft": round(m / FOOT_M, 1), "mi": round(m / FOOT_M / 5280.0, 3)}
def disp_area(m2): return {"sq_ft": round(m2 * SQFT_PER_M2), "acres": round(m2 / ACRE_M2, 2), "sq_mi": round(m2 / SQMI_M2, 3)}
DISPLAY_PRECISION_NOTE = ("display values are rounded (ft 0.1, sq ft 1, acres 0.01); internal values keep 6 decimals for "
                          "reproducibility only — that is numeric precision, not measurement accuracy")

# ---------------- U3: dependency lock ----------------
expected = {}
for line in LOCK.read_text(encoding="utf-8").splitlines():
    line = line.split("#", 1)[0].strip()
    if not line: continue
    k, v = (line.split("==") if "==" in line else line.split("="))[:2]
    expected[k.strip().lower()] = v.strip()
actual = {"shapely": shapely.__version__, "pyproj": pyproj.__version__,
          "geos": geos_version_string, "proj": pyproj.proj_version_str}
mismatch = {k: {"locked": expected.get(k), "actual": v} for k, v in actual.items() if expected.get(k) != v}
if mismatch: die(f"dependency lock mismatch (edit {LOCK.name} deliberately to change): {mismatch}")
environment = {"interpreter": sys.executable, "python": platform.python_version(), **actual, "lock_file": LOCK.name,
               "lock_sha256": sha_file(LOCK)}

# ---------------- inputs + hash gate against the UPSTREAM stage manifest ----------------
up_manifest_path = DATA / "build_manifest.json"
up_manifest = load(up_manifest_path)
up_out = {o["file"]: o["sha256"] for o in up_manifest["outputs"]}
up_in = {Path(i["path"]).name: i["sha256"] for i in up_manifest["inputs"]}
hash_checks = {}
for f in ["station_master.geojson", "study_window.geojson"]:
    got = sha_file(DATA / f); hash_checks[f] = (got == up_out.get(f))
    if not hash_checks[f]: die(f"{f} sha256 {got} != upstream manifest {up_out.get(f)}")
zon_path = RAW / "zoning_study_window.geojson"
got = sha_file(zon_path); hash_checks["zoning_study_window.geojson"] = (got == up_in.get("zoning_study_window.geojson"))
if not hash_checks["zoning_study_window.geojson"]: die("raw zoning sha256 != upstream manifest")
upstream_record = {"stage": "station_master", "manifest": "build_manifest.json", "manifest_sha256": sha_file(up_manifest_path),
                   "station_master_sha256": up_out["station_master.geojson"], "study_window_sha256": up_out["study_window.geojson"],
                   "zoning_raw_sha256": up_in["zoning_study_window.geojson"]}

stations = load(DATA / "station_master.geojson")["features"]
zoning = load(zon_path)["features"]
window = load(DATA / "study_window.geojson")["features"][0]
if len(stations) != 21 or len(zoning) != 235: die(f"expected 21 stations / 235 polygons, got {len(stations)}/{len(zoning)}")

# ---------------- projection: record the ACTUAL operation, derive grid use ----------------
fwd = Transformer.from_crs(SRC_CRS, DST_CRS, always_xy=True)
inv = Transformer.from_crs(DST_CRS, SRC_CRS, always_xy=True)
pipeline = fwd.definition or ""
grid_used = any(t in pipeline for t in ("hgridshift", "vgridshift", "nadgrids", "+grids=", "geoidgrids"))
transform_record = {
    "source_crs": SRC_CRS, "target_crs": DST_CRS, "always_xy": True,
    "operation": fwd.description, "reported_accuracy_m": fwd.accuracy,
    "reported_accuracy_ft": (round(fwd.accuracy / FOOT_M, 2) if fwd.accuracy is not None else None),
    "pipeline": pipeline, "grid_used": grid_used, "network_enabled": fwd.is_network_enabled,
    "accuracy_note": "reported_accuracy is the accuracy PROJ reports for the datum operation it selected in THIS environment; "
                     "it is not the precision of GTFS reference points, of zoning boundaries, or of the model as a whole. "
                     "Re-verify if the environment, projection or grid availability changes.",
}
proj = lambda g: shp_transform(fwd.transform, g)
unproj = lambda g: shp_transform(inv.transform, g)

# ---------------- geometry quality: validate first, repair with provenance (U4) ----------------
def polygonal(g):
    if g.geom_type in ("Polygon", "MultiPolygon"): return g, []
    if g.geom_type == "GeometryCollection":
        keep = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        drop = [p.geom_type for p in g.geoms if p.geom_type not in ("Polygon", "MultiPolygon")]
        return (unary_union(keep) if keep else Polygon()), drop
    return Polygon(), [g.geom_type]

repairs, zon, invalid_after_projection = [], [], []
for f in zoning:
    p = f["properties"]; fid = p["FID"]
    g = shape(f["geometry"])
    if not g.is_valid:
        reason = explain_validity(g)
        fixed = make_valid(g)
        fixed_poly, dropped = polygonal(fixed)
        # Diagnostic baseline = buffer(0) of the invalid input. An invalid polygon has no well-defined area, so this
        # is NOT the unmodified source geometry and must not be read as its "true" area: it compares one repair
        # (make_valid) with another (buffer(0)).
        g_proj_buffer0 = proj(g.buffer(0)) if not g.is_empty else Polygon()
        g_proj_after = proj(fixed_poly)
        repairs.append({"FID": fid, "reason": reason, "method": "shapely.make_valid + keep polygonal parts",
                        "input_type": g.geom_type, "make_valid_type": fixed.geom_type, "kept_type": fixed_poly.geom_type,
                        "dropped_parts": dropped,
                        "baseline_method": "shapely buffer(0) of the invalid input geometry — a diagnostic baseline, not the raw geometry's true area",
                        "input_area_deg2_diagnostic_only": g.area, "make_valid_area_deg2_diagnostic_only": fixed_poly.area,
                        "projected_area_buffer0_baseline_m2": r6(g_proj_buffer0.area),
                        "projected_area_after_make_valid_m2": r6(g_proj_after.area),
                        "projected_area_delta_vs_buffer0_baseline_m2": r6(g_proj_after.area - g_proj_buffer0.area),
                        "valid_after_repair": bool(fixed_poly.is_valid), "valid_after_projection": bool(g_proj_after.is_valid)})
        g = fixed_poly
    if g.is_empty: die(f"FID {fid} has no polygonal geometry after repair")
    gp = proj(g)
    if not gp.is_valid: invalid_after_projection.append(fid)
    zon.append((fid, p["M21_ZONE"], p["Transect_D"], gp))
if invalid_after_projection: die(f"invalid geometry after projection: {invalid_after_projection}")

# ---------------- window margin gate: all 21 stations, actual max radius ----------------
win_proj = proj(shape(window["geometry"]))
st, margins = [], []
for f in stations:
    pid = f["properties"]["station_id"]; name = f["properties"]["name"]
    pt = proj(shape(f["geometry"]))
    disc_max = pt.buffer(RADII_M[2], quad_segs=QUAD_SEGS)
    contained = win_proj.contains(disc_max)
    margin = win_proj.exterior.distance(pt) - RADII_M[2]
    margins.append({"station_id": pid, "margin_m": r6(margin), "margin_ft": round(margin / FOOT_M, 2), "band_inside_window": bool(contained)})
    if not contained: die(f"{pid} outer band is not inside the study window (margin {margin:.2f} m)")
    st.append((pid, name, pt))

# ---------------- clipping + union-based metrics ----------------
def clip_pieces(region):
    out = []
    for fid, code, tr, g in zon:
        inter = region.intersection(g)
        if not inter.is_empty and inter.area > 0:
            ip, _ = polygonal(inter)
            if ip.area > 0: out.append((fid, code, tr, ip))
    return out

def conflict_union_area(union_geoms):
    keys = list(union_geoms); inter = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            g = union_geoms[keys[i]].intersection(union_geoms[keys[j]])
            if not g.is_empty and g.area > 0: inter.append(g)
    return unary_union(inter).area if inter else 0.0

def band_metrics(region):
    band_area = region.area
    pieces = clip_pieces(region)
    clipped_sum = sum(p[3].area for p in pieces)
    union_all = unary_union([p[3] for p in pieces]).area if pieces else 0.0
    def agg(idx):
        groups = defaultdict(list)
        for pc in pieces: groups[pc[idx]].append(pc)
        out, geoms = {}, {}
        for k in sorted(groups):
            u = unary_union([pc[3] for pc in groups[k]]); geoms[k] = u
            out[k] = {"union_area_m2": r6(u.area), "share_of_band": r6(u.area / band_area) if band_area else 0.0,
                      "polygon_count": len({pc[0] for pc in groups[k]}), "display": disp_area(u.area)}
        return out, geoms
    code_agg, code_geoms = agg(1)
    tr_agg, tr_geoms = agg(2)
    metrics = {
        "ring_area_m2": r6(band_area), "zoned_union_area_m2": r6(union_all),
        "zoned_area_share": r6(union_all / band_area) if band_area else 0.0,
        "uncovered_area_share": r6(1 - union_all / band_area) if band_area else 0.0,
        "uncovered_note": "uncovered = not in the zoning layer; may be water, right-of-way, layer gaps or unrecorded parcels — cause not determined here",
        "zoning_overlap_excess_area_m2": r6(clipped_sum - union_all),
        "code_overlap_excess_area_m2": r6(max(sum(v["union_area_m2"] for v in code_agg.values()) - union_all, 0.0)),
        "code_conflict_union_area_m2": r6(conflict_union_area(code_geoms)),
        "transect_overlap_excess_area_m2": r6(max(sum(v["union_area_m2"] for v in tr_agg.values()) - union_all, 0.0)),
        "transect_conflict_union_area_m2": r6(conflict_union_area(tr_geoms)),
        "polygon_count": len({p[0] for p in pieces}),
        "min_clipped_fragment_m2": r6(min(p[3].area for p in pieces)) if pieces else None,
        "display": {"ring_area": disp_area(band_area), "zoned_union_area": disp_area(union_all)},
        "by_M21_ZONE": code_agg, "by_Transect_D": tr_agg,
        "shares_note": "per-code shares are unions within each code; they need not sum to zoned_area_share when codes overlap "
                       "(overlap_excess = repeat-counted area; conflict_union = actual area covered by >=2 codes)",
        "small_fragment_note": "tiny fragments are kept for audit; they must not be read as meaningful use or demand",
    }
    return metrics, pieces

profiles, catch_feats, band_checks, approx, evidence = [], [], [], [], []
disc_by_station, cum_pieces_by_station = {}, {}
for pid, name, pt in st:
    discs = [pt.buffer(r, quad_segs=QUAD_SEGS) for r in RADII_M]
    bands = [discs[0], discs[1].difference(discs[0]), discs[2].difference(discs[1])]
    ov = max(bands[i].intersection(bands[j]).area for i in range(3) for j in range(i + 1, 3))
    add_err = abs(sum(b.area for b in bands) - discs[2].area)
    band_checks.append({"station_id": pid, "max_pairwise_overlap_m2": r6(ov), "band_sum_minus_disc_m2": r6(add_err),
                        "pass": ov < AREA_TOL_M2 and add_err < AREA_TOL_M2})
    approx.append({"station_id": pid, "buffer_area_over_true_circle": r6(discs[2].area / (math.pi * RADII_M[2] ** 2))})
    disc_by_station[pid] = discs[2]
    band_out = []
    for i, b in enumerate(bands):
        m, pieces = band_metrics(b)
        band_out.append({"band_id": BAND_KEYS[i], "band": BAND_LABELS[i], "inner_ft": 0 if i == 0 else RADII_FT[i - 1],
                         "outer_ft": RADII_FT[i], "inner_m": 0.0 if i == 0 else r6(RADII_M[i - 1]), "outer_m": r6(RADII_M[i]),
                         **SEMANTIC_FLAGS, **m})
        for fid, code, tr, g in pieces:
            evidence.append({"evidence_id": f"{pid}|{BAND_KEYS[i]}|FID{fid}", "station_id": pid, "band_id": BAND_KEYS[i],
                             "band": BAND_LABELS[i], "FID": fid, "M21_ZONE": code, "Transect_D": tr,
                             "clipped_area_m2": r6(g.area), "source_snapshot": "zoning_study_window.geojson@" + upstream_record["zoning_raw_sha256"][:12]})
        catch_feats.append({"type": "Feature", "geometry": mapping(unproj(b)), "properties": {
            "station_id": pid, "name": name, "band_id": BAND_KEYS[i], "band": BAND_LABELS[i],
            "inner_ft": 0 if i == 0 else RADII_FT[i - 1], "outer_ft": RADII_FT[i], **SEMANTIC_FLAGS,
            "geometry_note": f"polygon approximation of a circle, quad_segs={QUAD_SEGS}; reprojected to WGS84 for display"}})
    cum, cpieces = band_metrics(discs[2])
    cum_pieces_by_station[pid] = cpieces
    for fid, code, tr, g in cpieces:
        evidence.append({"evidence_id": f"{pid}|cum|FID{fid}", "station_id": pid, "band_id": "cum", "band": "0-1/2 mi cumulative",
                         "FID": fid, "M21_ZONE": code, "Transect_D": tr, "clipped_area_m2": r6(g.area),
                         "source_snapshot": "zoning_study_window.geojson@" + upstream_record["zoning_raw_sha256"][:12]})
    profiles.append({"station_id": pid, "name": name, **SEMANTIC_FLAGS, "bands": band_out,
                     "cumulative_0_to_half_mile": {"band_id": "cum", "outer_ft": RADII_FT[2], "outer_m": r6(RADII_M[2]), **SEMANTIC_FLAGS, **cum},
                     "classification_note": "statutory zoning profile — permitted/constrained use, not observed land use, population, jobs or demand"})

# ---------------- U1: overlap = actual geometry; coverage ratios are NON-exclusive; network union ----------------
ids = [s[0] for s in st]
pairs = []
for i in range(len(ids)):
    for j in range(i + 1, len(ids)):
        a = disc_by_station[ids[i]].intersection(disc_by_station[ids[j]]).area
        if a > 0: pairs.append({"station_a": ids[i], "station_b": ids[j], "intersection_area_m2": r6(a), "display": disp_area(a)})
network_union = unary_union(list(disc_by_station.values()))
sum_discs = sum(d.area for d in disc_by_station.values())
per_poly = {}
for pid, pieces in cum_pieces_by_station.items():
    for fid, _, _, g in pieces: per_poly.setdefault(fid, {})[pid] = r6(g.area)
assignments = []
for fid, code, tr, g in zon:
    hits = per_poly.get(fid, {})
    assignments.append({"FID": fid, "M21_ZONE": code, "polygon_area_m2": r6(g.area),
                        "clipped_area_by_station_m2": hits,
                        "coverage_ratio_by_station_nonexclusive": {k: r6(v / g.area) for k, v in hits.items()} if g.area else {},
                        "sum_of_coverage_ratios": r6(sum(v / g.area for v in hits.values())) if g.area else 0.0,
                        "is_allocation_weight": False, "station_hits": len(hits)})
unassigned = [a["FID"] for a in assignments if a["station_hits"] == 0]
multi = [a["FID"] for a in assignments if a["station_hits"] >= 2]
network_block = {"network_half_mile_union_area_m2": r6(network_union.area), "sum_of_21_station_discs_m2": r6(sum_discs),
                 "area_duplication_ratio": r6(sum_discs / network_union.area), "display": {"union": disp_area(network_union.area), "sum_of_discs": disp_area(sum_discs)},
                 "note": "the network union is computed directly as a geometric union; it cannot be derived from the sum of discs minus pairwise "
                         "intersections because three or more discs overlap (inclusion-exclusion truncated at pairs goes negative on this data)"}

# ---------------- U4: station reference point vs zoning polygon (separate sub-task) ----------------
point_match = []
for pid, name, pt in st:
    hits = [(fid, code) for fid, code, _, g in zon if g.covers(pt)]
    point_match.append({"station_id": pid, "name": name, "matched": bool(hits),
                        "matched_FIDs": [h[0] for h in hits], "matched_M21_ZONE": sorted({h[1] for h in hits}),
                        "status": "MATCHED" if hits else "NOT_COVERED_BY_ANY_SOURCE_POLYGON"})
point_note = ("A reference point not covered by any zoning polygon (e.g. in right-of-way) does not invalidate the band profile and "
              "does not imply the station is unlawful or without demand; no nearest-neighbour fill is applied.")

# ---------------- validation (F1: nothing published until this passes) ----------------
val = {
    "build_status": None, "geometry_validation_status": None, "ready_for_downstream": False,
    "input_hash_checks": hash_checks, "dependency_lock_ok": True,
    "stations": len(st), "zoning_polygons": len(zon), "profiles_bands": len(profiles) * 3,
    "all_projected_geometries_valid": not invalid_after_projection,
    "window_margin_all_bands_inside": all(m["band_inside_window"] for m in margins),
    "min_margin_m": min(m["margin_m"] for m in margins), "min_margin_ft": min(m["margin_ft"] for m in margins),
    "band_non_overlap_and_additivity_pass": all(b["pass"] for b in band_checks),
    "every_station_has_polygons_in_half_mile": all(p["cumulative_0_to_half_mile"]["polygon_count"] > 0 for p in profiles),
    "clipped_never_exceeds_band": all(b["zoned_union_area_m2"] <= b["ring_area_m2"] + AREA_TOL_M2 for p in profiles for b in p["bands"]),
    "polygon_reconciliation": {"hit_by_at_least_one_station": len(zon) - len(unassigned), "unassigned_in_window": len(unassigned),
                               "multi_station": len(multi), "total": len(zon), "reconciles": (len(zon) - len(unassigned)) + len(unassigned) == len(zon)},
    "invalid_geometries_repaired": len(repairs), "evidence_rows": len(evidence),
    "scope_statement": "PASS means the geometry and input-integrity checks listed here passed. It is not acceptance of the whole V2 "
                       "input package, not agency confirmation, not a walk-catchment result and not an engineering validation.",
    "window_statement": "All analysis bands lie within the queried study window; no truncation detected. This does not certify that "
                        "every zoning polygon within the bands is complete or accurate, nor that uncovered area is water.",
    "not_performed": ["walk catchment", "use-code mapping", "demand allocation", "berth or platform sizing", "agency confirmation"],
}
geometry_pass = (val["window_margin_all_bands_inside"] and val["band_non_overlap_and_additivity_pass"]
                 and val["every_station_has_polygons_in_half_mile"] and val["clipped_never_exceeds_band"]
                 and val["all_projected_geometries_valid"] and all(hash_checks.values()) and val["polygon_reconciliation"]["reconciles"])
if os.environ.get("SPATIAL_JOIN_FORCE_FAIL") == "1":
    geometry_pass = False; val["injected_failure_for_test"] = True
val["geometry_validation_status"] = "PASS" if geometry_pass else "FAIL"
val["build_status"] = "COMPLETED" if geometry_pass else "FAILED"
val["ready_for_downstream"] = bool(geometry_pass)

config = {"radii_ft": RADII_FT, "radii_m_derived": [r6(r) for r in RADII_M], "band_ids": BAND_KEYS, "band_labels": BAND_LABELS,
          "foot_definition": "international_foot_0.3048m_exact (NIST revised factors, effective 2023)",
          "length_unit_internal": "m", "area_unit_internal": "m2",
          "display_units_miami": {"length": "ft / mi", "area": "sq ft / acres / sq mi", "acre_m2": r6(ACRE_M2), "sqft_per_m2": r6(SQFT_PER_M2), "sqmi_m2": r6(SQMI_M2)},
          "display_precision_note": DISPLAY_PRECISION_NOTE,
          "catchment_semantics": "Euclidean distance bands from the GTFS station reference point; NOT walk catchments; no travel-time meaning",
          "band_area_ratio_note": "band areas scale 1:3:12 — distance weighting is a separate calibrated parameter, not implied by area",
          "quad_segs": QUAD_SEGS, "area_tolerance_m2": AREA_TOL_M2,
          "aggregation": "original M21_ZONE and Transect_D only; union within code; cross-code overlap reported as excess and as conflict-union; no use mapping; no exclusion",
          "coverage_ratio_semantics": "coverage_ratio_by_station_nonexclusive = clipped area within a station's half-mile disc / polygon area; "
                                      "overlapping discs make these sum above 1; they are NOT allocation weights and must not be normalised into choice probabilities"}
config_sha = sha_obj(config)

# ---------------- stage outputs into STAGING ----------------
if STAGING.exists(): shutil.rmtree(STAGING)
STAGING.mkdir(parents=True)
common = {"built_on": BUILT_ON, "config_sha256": config_sha, "upstream": upstream_record}
dump(STAGING / "station_zoning_profile.json", {"schema_version": "miami-station-zoning-profile/1.1", **common, "config": config,
     "transform": transform_record, "environment": environment, "network": network_block, "stations": profiles})
dump(STAGING / "station_catchments.geojson", {"type": "FeatureCollection", "schema_version": "miami-station-catchments/1.1",
     "crs_note": "WGS84 for display; computed in EPSG:26917", **common, "features": catch_feats})
dump(STAGING / "network_half_mile_union.geojson", {"type": "FeatureCollection", "schema_version": "miami-network-half-mile-union/1.0", **common,
     "features": [{"type": "Feature", "geometry": mapping(unproj(network_union)), "properties": {**network_block, **SEMANTIC_FLAGS, "radius_ft": RADII_FT[2]}}]})
dump(STAGING / "station_overlap.json", {"schema_version": "miami-station-overlap/1.1", **common, "network": network_block,
     "half_mile_disc_pairwise_intersections": pairs, "per_polygon_coverage": assignments,
     "unassigned_polygon_fids": unassigned, "multi_station_polygon_fids": multi,
     "note": "Overlap measured as actual intersecting geometry. Coverage ratios are non-exclusive and are NOT allocation weights; "
             "demand allocation needs its own rules (unallocated share, transfer roles, competition)."})
dump(STAGING / "station_zoning_evidence.json", {"schema_version": "miami-station-zoning-evidence/1.0", **common, "rows": evidence,
     "note": "One row per (station, band, source FID) with positive clipped area. Sums of clipped areas within a code may exceed the "
             "published union area (overlapping sources); aggregates in the profile remain union-based. Cite evidence_id, do not restate sources."})
dump(STAGING / "station_point_zoning_match.json", {"schema_version": "miami-station-point-zoning-match/1.0", **common, "note": point_note, "stations": point_match})
dump(STAGING / "spatial_join_validation.json", val)
dump(STAGING / "geometry_quality_report.json", {"environment": environment, "transform": transform_record, "quad_segs": QUAD_SEGS,
     "buffer_approximation": approx, "band_checks": band_checks, "window_margins": margins,
     "invalid_geometry_repairs": repairs, "all_projected_geometries_valid": not invalid_after_projection,
     "repair_policy": "validate first; make_valid only on invalid; keep polygonal parts; log FID, reason, type change, dropped parts, "
                      "projected-area delta versus a buffer(0) diagnostic baseline (not the raw area), post-repair and post-projection validity",
     "display_precision_note": DISPLAY_PRECISION_NOTE})

# ---------------- F1: gated publish — nothing leaves staging unless validation passed ----------------
def fail_and_exit(reason, extra=None):
    FAILED_DIR.mkdir(exist_ok=True)
    log = FAILED_DIR / f"spatial_join_failed_{time.strftime('%Y%m%dT%H%M%S')}.json"
    dump(log, {"built_on": BUILT_ON, "reason": reason, "validation": val, "script_sha256": sha_file(Path(__file__)),
               "config_sha256": config_sha, "upstream": upstream_record, "current_package_untouched": True,
               "current_pointer_untouched": True, **(extra or {})})
    if STAGING.exists(): shutil.rmtree(STAGING)
    for t in DATA.glob(POINTER.name + ".tmp"): t.unlink()
    print(f"status=FAIL — {reason}; nothing switched; current package and pointer untouched; log: {log.relative_to(ROOT)}")
    sys.exit(1)

if not geometry_pass:
    fail_and_exit("geometry/input validation failed", {"staged_outputs_discarded": OUTPUT_FILES})

# ---------------- R3: whole-package publish — content-addressed immutable dir + ONE atomic pointer switch ----------------
manifest = {"stage": "spatial_join", "schema_version": "miami-spatial-join-manifest/2.0", "built_on": BUILT_ON,
            "build_status": val["build_status"], "geometry_validation_status": val["geometry_validation_status"],
            "ready_for_downstream": val["ready_for_downstream"],
            "script": {"path": "scripts/build_miami_station_zoning_profile.py", "sha256": sha_file(Path(__file__))},
            "config_sha256": config_sha, "config": config, "environment": environment, "transform": transform_record,
            "upstream": upstream_record,
            "consumed_inputs_note": "station_master_sha256 / study_window_sha256 / zoning_raw_sha256 are the ONLY inputs this stage "
                                    "reads; scripts/miami_readiness.py compares each with the current file to decide FRESH vs STALE (R1)",
            "method_summary": "imperial bands 1/8-1/4-1/2 mi; clip-to-band; union-based coverage; per original code; no use mapping; no exclusion",
            "publish_policy": "content-addressed immutable package dir spatial_join/pkg-<id> (id = sha256 of this manifest without the "
                              "package fields); readers resolve spatial_join_current.json (switched by one atomic os.replace) and verify "
                              "the whole package (R3). Previous packages are kept as the archive (update-build + archive, F2).",
            "outputs": [{"file": f, "sha256": sha_file(STAGING / f)} for f in OUTPUT_FILES]}
package_id = "pkg-" + sha_obj(manifest)[:12]
manifest["package_id"] = package_id; manifest["package_dir"] = f"spatial_join/{package_id}"
dump(STAGING / MANIFEST_NAME, manifest)
ok, _, problems = verify_package(STAGING)
if not ok: fail_and_exit("staged package failed self-verification", {"problems": problems})

pkg_dir = SJ_DIR / package_id
reused = False
try:
    if pkg_dir.exists():   # deterministic rerun: an identical build is already published — it must be byte-identical
        diff = [f for f in OUTPUT_FILES + [MANIFEST_NAME]
                if not (pkg_dir / f).exists() or sha_file(pkg_dir / f) != sha_file(STAGING / f)]
        if diff:   # same id but different bytes => the published dir is corrupt; quarantine it, never overwrite silently
            quarantine = SJ_DIR / f"{package_id}.corrupt-{time.strftime('%Y%m%dT%H%M%S')}"
            os.rename(pkg_dir, quarantine); os.rename(STAGING, pkg_dir)
            print(f"WARNING: existing {package_id} differed in {diff}; quarantined as {quarantine.name} and republished")
        else:
            shutil.rmtree(STAGING); reused = True
    else:
        os.rename(STAGING, pkg_dir)   # atomic directory rename on the same filesystem: the package appears whole or not at all
    prev = load(POINTER) if POINTER.exists() else None
    switched = not (prev and prev.get("package_dir") == manifest["package_dir"])
    pointer = {"stage": "spatial_join", "schema_version": "miami-spatial-join-pointer/1.0",
               "package_id": package_id, "package_dir": manifest["package_dir"],
               "manifest": f"{manifest['package_dir']}/{MANIFEST_NAME}", "manifest_sha256": sha_file(pkg_dir / MANIFEST_NAME),
               "built_on": BUILT_ON,
               "previous_package_dir": (prev.get("package_dir") if (prev and switched) else (prev or {}).get("previous_package_dir")),
               "policy": "the only mutable file of this stage; switched with a single atomic os.replace after the whole package was "
                         "written and verified; readers must resolve this pointer and verify the package (scripts/miami_readiness.py)"}
    tmp = POINTER.with_name(POINTER.name + ".tmp"); dump(tmp, pointer); os.replace(tmp, POINTER)
except OSError as e:
    fail_and_exit(f"publish interrupted: {e}",
                  {"package_dir_state": ("complete_but_not_current" if pkg_dir.exists() else "not_written")})
aggregate()   # readiness is derived by its single writer (R2); this stage never edits it directly

print(f"status=PASS package={package_id} ({'reused, byte-identical' if reused else 'new'}) pointer_switched={switched} "
      f"published={len(OUTPUT_FILES)} stations={len(st)} polygons={len(zon)} band_profiles={len(profiles)*3} "
      f"evidence_rows={len(evidence)} min_margin_ft={val['min_margin_ft']} repairs={len(repairs)} "
      f"unassigned={len(unassigned)} multi_station={len(multi)} network_union_sqmi={network_block['display']['union']['sq_mi']}")
