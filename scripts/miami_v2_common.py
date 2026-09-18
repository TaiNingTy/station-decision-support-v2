#!/usr/bin/env python3
"""Shared helpers for the Miami V2 data layers (step 3+): dependency lock gate, projection record, TIGER readers,
land geometry (water erased), source-unit shares, ACS parsing with special values, MOE arithmetic, imperial display,
and the generic content-addressed package publish (R3) with pointer switch + readiness aggregation (R2).

Every layer script imports this module; its sha256 is recorded in each package manifest under `code`."""
import hashlib, io, json, math, os, platform, shutil, sys, time, zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/miami/2026-09-14"
RAW15 = ROOT / "raw/miami/2026-09-15"
LOCK = ROOT / "requirements-gis.lock.txt"
FAILED_DIR = DATA / "failed"
sys.path.insert(0, str(ROOT / "vendor")); sys.path.insert(0, str(ROOT / "scripts"))
import shapely, pyproj, shapefile
from shapely import geos_version_string
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely.ops import transform as shp_transform, unary_union
from shapely.strtree import STRtree
from pyproj import Transformer
from miami_readiness import aggregate, verify_package

BUILT_ON = "2026-09-15"
FOOT_M = 0.3048
ACRE_M2 = 43560.0 * FOOT_M ** 2
SQMI_M2 = (5280.0 * FOOT_M) ** 2
SQFT_PER_M2 = 1.0 / FOOT_M ** 2
STATE, COUNTY = "12", "086"
Z90 = 1.645   # ACS margins of error are published at the 90 % confidence level
ACS_VINTAGE = 2024


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sha_obj(o): return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p, obj): Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def r6(x): return round(float(x), 6)
def r2(x): return round(float(x), 2)
def rel(p): return str(Path(p).resolve().relative_to(ROOT))
def disp_area(m2): return {"sq_ft": round(m2 * SQFT_PER_M2), "acres": round(m2 / ACRE_M2, 2), "sq_mi": round(m2 / SQMI_M2, 3)}
def per_sq_mi(count, m2): return round(count / (m2 / SQMI_M2), 1) if m2 > 0 else None
def per_acre(count, m2): return round(count / (m2 / ACRE_M2), 3) if m2 > 0 else None


# ---------------------------------------------------------------- lock gate + environment ----------------------------------------------------------------
def lock_gate():
    expected = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line: continue
        k, v = (line.split("==") if "==" in line else line.split("="))[:2]
        expected[k.strip().lower()] = v.strip()
    actual = {"shapely": shapely.__version__, "pyproj": pyproj.__version__, "geos": geos_version_string,
              "proj": pyproj.proj_version_str, "pyshp": shapefile.__version__}
    mismatch = {k: {"locked": expected.get(k), "actual": v} for k, v in actual.items() if expected.get(k) != v}
    if mismatch: raise SystemExit(f"HALT: dependency lock mismatch (edit {LOCK.name} deliberately to change): {mismatch}")
    return {"interpreter": sys.executable, "python": platform.python_version(), **actual, "lock_file": LOCK.name, "lock_sha256": sha_file(LOCK)}


def projection():
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:26917", always_xy=True)
    inv = Transformer.from_crs("EPSG:26917", "EPSG:4326", always_xy=True)
    pipeline = fwd.definition or ""
    record = {"source_crs": "EPSG:4326", "target_crs": "EPSG:26917", "always_xy": True, "operation": fwd.description,
              "reported_accuracy_m": fwd.accuracy, "pipeline": pipeline,
              "grid_used": any(t in pipeline for t in ("hgridshift", "vgridshift", "nadgrids", "+grids=", "geoidgrids")),
              "network_enabled": fwd.is_network_enabled,
              "accuracy_note": "PROJ-reported accuracy of the datum operation selected in THIS environment; not the precision of the "
                               "source geometries or of the model"}
    return fwd, inv, record


# ---------------------------------------------------------------- TIGER readers ----------------------------------------------------------------
def read_shapefile_zip(zip_path):
    """Yield (attributes dict, shapely geometry in the file's CRS) for every record of the shapefile inside the zip."""
    z = zipfile.ZipFile(zip_path); names = z.namelist()
    pick = lambda ext: io.BytesIO(z.read(next(n for n in names if n.lower().endswith(ext))))
    r = shapefile.Reader(shp=pick(".shp"), shx=pick(".shx"), dbf=pick(".dbf"))
    fields = [f[0] for f in r.fields if f[0] != "DeletionFlag"]
    for sr in r.iterShapeRecords():
        yield dict(zip(fields, list(sr.record))), shape(sr.shape.__geo_interface__)


def polygonal(g):
    """Keep polygonal parts only (a difference/intersection can leave lines or points)."""
    if g.geom_type in ("Polygon", "MultiPolygon"): return g
    if g.geom_type == "GeometryCollection":
        keep = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        return unary_union(keep) if keep else Polygon()
    return Polygon()


def erase_water(block_geoms, water_geoms):
    """block_geoms: {id: projected polygon}; water_geoms: list of projected polygons.
    Returns {id: land polygon} using an STRtree so each block only sees the water features that touch it."""
    tree = STRtree(water_geoms); land = {}
    for bid in sorted(block_geoms):
        g = block_geoms[bid]
        idx = tree.query(g)
        cands = [water_geoms[i] for i in idx if water_geoms[i].intersects(g)]
        land[bid] = polygonal(g.difference(unary_union(cands))) if cands else g
    return land


def intersections_by_target(land, targets):
    """land: {block id: land polygon}; targets: {target key: polygon}.
    Returns {target key: {block id: intersection area m2}} for positive intersections only."""
    ids = sorted(land); geoms = [land[i] for i in ids]; tree = STRtree(geoms); out = {}
    for key in targets:
        t = targets[key]; hits = {}
        for i in tree.query(t):
            g = geoms[i]
            if g.is_empty: continue
            a = polygonal(g.intersection(t)).area
            if a > 0: hits[ids[i]] = a
        out[key] = hits
    return out


# ---------------------------------------------------------------- ACS parsing ----------------------------------------------------------------
ACS_SPECIAL_EST = {"-666666666": ("missing", "insufficient_sample"), "-999999999": ("suppressed", "not_published"),
                   "-888888888": ("not_applicable", None)}
ACS_SPECIAL_MOE = {"-222222222": "insufficient_sample", "-333333333": "open_ended_interval", "-555555555": "exact_source",
                   "-666666666": "insufficient_sample", "-999999999": "not_published", "-888888888": "not_applicable"}


def acs_raw_file(table, geo="bg"): return RAW15 / f"acs/acs5_{ACS_VINTAGE}_{geo}_{STATE}{COUNTY}_{table}.json"


def parse_acs_table(table, geo="bg"):
    """-> {geoid: {var_base (e.g. 'B08301_003'): {'value': float|None, 'moe': float|None, 'value_status': str,
    'missing_reason': str|None, 'moe_status': str}}} for every geography unit (geo = 'bg' or 'tract') in the raw response."""
    data = load(acs_raw_file(table, geo)); header, rows = data[0], data[1:]
    col = {h: i for i, h in enumerate(header)}; bases = sorted({h[:-1] for h in header if h.startswith(table) and h.endswith("E") and h[-2] != "E"})
    out = {}
    for row in rows:
        geoid = row[col["GEO_ID"]].split("US")[-1]; rec = {}
        for b in bases:
            e, m = row[col[b + "E"]], row[col.get(b + "M", -1)] if (b + "M") in col else None
            if e is None or e in ACS_SPECIAL_EST:
                st, why = ACS_SPECIAL_EST.get(e, ("missing", "null_response")); val = None
            else:
                val, st, why = float(e), "value", None
            if m is None or m in ACS_SPECIAL_MOE:
                moe, mst = None, ACS_SPECIAL_MOE.get(m, "not_published")
            else:
                moe, mst = float(m), "exact_source"
            rec[b] = {"value": val, "moe": moe, "value_status": st, "missing_reason": why, "moe_status": mst}
        out[geoid] = rec
    return out


# ---------------------------------------------------------------- MOE arithmetic ----------------------------------------------------------------
def combine_sum(items):
    """items: iterable of (weight, value, moe). Weighted sum with the Census RSS approximation for the MOE.
    Units with a missing value are skipped and counted. Returns (est, moe, n_used, n_missing, any_moe_missing)."""
    est = 0.0; var = 0.0; used = missing = 0; moe_missing = False
    for w, v, m in items:
        if v is None: missing += 1; continue
        est += w * v; used += 1
        if m is None: moe_missing = True
        else: var += (w * m) ** 2
    return est, math.sqrt(var), used, missing, moe_missing


def moe_ratio(num, moe_num, den, moe_den):
    """Census approximation for a proportion/ratio; the + form when the radicand is negative."""
    if den is None or den <= 0 or num is None: return None
    p = num / den; rad = moe_num ** 2 - (p ** 2) * moe_den ** 2
    if rad < 0: rad = moe_num ** 2 + (p ** 2) * moe_den ** 2
    return math.sqrt(rad) / den


def reliability(est, moe):
    if est is None or moe is None or est <= 0: return None, "undefined"
    cv = (moe / Z90) / est
    return round(cv, 4), ("high" if cv <= 0.12 else "medium" if cv <= 0.40 else "low")


# ---------------------------------------------------------------- generic publish (R3) ----------------------------------------------------------------
def fail_and_exit(stage, staging, reason, extra=None):
    FAILED_DIR.mkdir(exist_ok=True)
    log = FAILED_DIR / f"{stage}_failed_{time.strftime('%Y%m%dT%H%M%S')}.json"
    dump(log, {"stage": stage, "built_on": BUILT_ON, "reason": reason, "current_package_untouched": True, "current_pointer_untouched": True, **(extra or {})})
    if staging.exists(): shutil.rmtree(staging)
    for t in DATA.glob(f"{stage}_current.json.tmp"): t.unlink()
    print(f"status=FAIL — {reason}; nothing switched; current package and pointer untouched; log: {log.relative_to(ROOT)}")
    sys.exit(1)


def publish_package(stage, staging, output_files, manifest, manifest_name="manifest.json"):
    """Content-addressed immutable package dir + one atomic pointer switch + readiness aggregation.
    `manifest` must not yet contain package_id/package_dir/outputs; they are added here."""
    stage_dir = DATA / stage; pointer = DATA / f"{stage}_current.json"
    manifest["outputs"] = [{"file": f, "sha256": sha_file(staging / f)} for f in output_files]
    package_id = "pkg-" + sha_obj(manifest)[:12]
    manifest["package_id"] = package_id; manifest["package_dir"] = f"{stage}/{package_id}"
    dump(staging / manifest_name, manifest)
    ok, _, problems = verify_package(staging, manifest_name)
    if not ok: fail_and_exit(stage, staging, "staged package failed self-verification", {"problems": problems})
    pkg_dir = stage_dir / package_id; reused = False
    try:
        if pkg_dir.exists():
            diff = [f for f in output_files + [manifest_name] if not (pkg_dir / f).exists() or sha_file(pkg_dir / f) != sha_file(staging / f)]
            if diff:
                quarantine = stage_dir / f"{package_id}.corrupt-{time.strftime('%Y%m%dT%H%M%S')}"
                os.rename(pkg_dir, quarantine); os.rename(staging, pkg_dir)
                print(f"WARNING: existing {package_id} differed in {diff}; quarantined as {quarantine.name} and republished")
            else:
                shutil.rmtree(staging); reused = True
        else:
            os.rename(staging, pkg_dir)
        prev = load(pointer) if pointer.exists() else None
        switched = not (prev and prev.get("package_dir") == manifest["package_dir"])
        ptr = {"stage": stage, "schema_version": "miami-package-pointer/1.0", "package_id": package_id, "package_dir": manifest["package_dir"],
               "manifest": f"{manifest['package_dir']}/{manifest_name}", "manifest_sha256": sha_file(pkg_dir / manifest_name), "built_on": BUILT_ON,
               "previous_package_dir": (prev.get("package_dir") if (prev and switched) else (prev or {}).get("previous_package_dir")),
               "policy": "the only mutable file of this stage; switched with a single atomic os.replace after the whole package was written and "
                         "verified; readers must resolve this pointer and verify the package (scripts/miami_readiness.py)"}
        tmp = pointer.with_name(pointer.name + ".tmp"); dump(tmp, ptr); os.replace(tmp, pointer)
    except OSError as e:
        fail_and_exit(stage, staging, f"publish interrupted: {e}", {"package_dir_state": ("complete_but_not_current" if pkg_dir.exists() else "not_written")})
    aggregate()
    return package_id, reused, switched


def consumed_entry(name, path):
    return {"name": name, "path": rel(path), "sha256": sha_file(path)}


def package_entry(stage):
    ptr = load(DATA / f"{stage}_current.json")
    return {"stage": stage, "package_id": ptr["package_id"], "manifest_sha256": ptr["manifest_sha256"]}


def code_entries(*paths):
    return [{"path": rel(p), "sha256": sha_file(p)} for p in paths]
