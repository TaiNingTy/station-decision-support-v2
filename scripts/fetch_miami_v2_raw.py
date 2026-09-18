#!/usr/bin/env python3
"""Step 2 · Acquire the V2 raw sources for Miami with a hash manifest and integrity checks.

Contract: V2_站点输入包字段契约.md §1 (versions locked there). Everything lands under raw/miami/2026-09-15/:
  tiger/   TIGER/Line 2024 block groups (FL), TIGER/Line 2020 P.L. 94-171 tabulation blocks (Miami-Dade),
           TIGER/Line 2024 area hydrography (Miami-Dade)
  acs/     ACS 2020-2024 5-year, vintage 2024, block groups of Miami-Dade: one raw API response per table
           (get=group(<table>): every E/M/EA/MA column) + the table's variable dictionary (groups/<table>.json)
  lodes/   LODES 8, Florida, 2023: WAC/RAC S000 JT00+JT01, OD main+aux JT00+JT01, geography crosswalk,
           the publisher's sha256sum file, version.txt and the technical document 8.4
  source_manifest.json        url, bytes, sha256, HTTP Last-Modified/ETag, retrieval time, publisher checksum status
  acquisition_validation.json integrity + contract-variable checks (PASS/FAIL)

Idempotent: a file whose sha256 already matches the manifest is kept and re-verified, not re-downloaded.
The Census API requires a key for data pulls. It is read from the environment variable CENSUS_API_KEY or from the
local file .secrets/census_api_key (one line, git-ignored); it is passed to curl via stdin config (not argv) and is
never written to the manifest. Without a key the ACS data pulls are recorded as blocked_missing_api_key and the
validation ends PARTIAL instead of FAIL; rerun after adding the key to complete the acquisition.

    python3 scripts/fetch_miami_v2_raw.py                # download (skip verified files) + validate
    python3 scripts/fetch_miami_v2_raw.py --validate-only
"""
import gzip, hashlib, io, json, os, subprocess, sys, time, zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw/miami/2026-09-15"
MANIFEST = RAW / "source_manifest.json"
VALIDATION = RAW / "acquisition_validation.json"
LOCK = ROOT / "requirements-gis.lock.txt"
sys.path.insert(0, str(ROOT / "vendor"))

STATE, COUNTY, ACS_VINTAGE = "12", "086", 2024
ACS_TABLES = ["B01003", "B01001", "B25003", "B25001", "B08301", "B08302", "B25044", "B19001", "B19013", "B17017", "B18101"]
# Contract §3: variable suffixes each table must provide (E and M columns). Verified against the raw API JSON on 2026-09-15.
CONTRACT_VARS = {
    "B01003": ["001"],
    "B01001": ["001", "002", "003", "004", "005", "006", "020", "021", "022", "023", "024", "025",
               "026", "027", "028", "029", "030", "044", "045", "046", "047", "048", "049"],
    "B25003": ["001", "002", "003"], "B25001": ["001"],
    "B08301": [f"{i:03d}" for i in range(1, 22)], "B08302": [f"{i:03d}" for i in range(1, 16)],
    "B25044": [f"{i:03d}" for i in range(1, 16)], "B19001": [f"{i:03d}" for i in range(1, 18)],
    "B19013": ["001"], "B17017": ["001", "002", "031"],
    "B18101": ["001", "004", "007", "010", "013", "016", "019", "023", "026", "029", "032", "035", "038"],
}
# Labels that the earlier (wrong) mapping got backwards; re-asserted from the variable dictionary at acquisition time.
LABEL_ASSERTS = {("B08301", "B08301_003E"): "Drove alone", ("B08301", "B08301_004E"): "Carpooled",
                 ("B08301", "B08301_010E"): "Public transportation", ("B08301", "B08301_017E"): "Motorcycle",
                 ("B08301", "B08301_018E"): "Bicycle", ("B08301", "B08301_019E"): "Walked",
                 ("B08301", "B08301_021E"): "Worked from home",
                 ("B25044", "B25044_003E"): "Owner occupied:!!No vehicle available",
                 ("B25044", "B25044_010E"): "Renter occupied:!!No vehicle available",
                 ("B17017", "B17017_002E"): "below poverty level", ("B18101", "B18101_004E"): "With a disability"}
UNIVERSE_ASSERTS = {"B08302": "did not work from home", "B25044": "Occupied housing units", "B19001": "Households",
                    "B18101": "Civilian noninstitutionalized population", "B08301": "Workers 16 years and over"}

TIGER_SOURCES = [
    ("tiger_bg_2024_fl", "tiger/tl_2024_12_bg.zip", "https://www2.census.gov/geo/tiger/TIGER2024/BG/tl_2024_12_bg.zip",
     "TIGER/Line 2024 block groups, Florida (2020 delineation) — ACS vintage 2024 geography; filtered to county 086 downstream"),
    ("tiger_tabblock20_2020pl_12086", "tiger/tl_2020_12086_tabblock20.zip",
     "https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/12_FLORIDA/12086/tl_2020_12086_tabblock20.zip",
     "TIGER/Line 2020 (P.L. 94-171 release) 2020 tabulation blocks, Miami-Dade County — LODES 8 geography (GEOID20, ALAND20, AWATER20)"),
    ("tiger_areawater_2024_12086", "tiger/tl_2024_12086_areawater.zip",
     "https://www2.census.gov/geo/tiger/TIGER2024/AREAWATER/tl_2024_12086_areawater.zip",
     "TIGER/Line 2024 area hydrography, Miami-Dade County — land geometry = block minus water (contract §6)"),
]
LODES_BASE = "https://lehd.ces.census.gov/data/lodes/LODES8/"
LODES_FILES = [("wac/", "fl_wac_S000_JT00_2023.csv.gz"), ("wac/", "fl_wac_S000_JT01_2023.csv.gz"),
               ("rac/", "fl_rac_S000_JT00_2023.csv.gz"), ("rac/", "fl_rac_S000_JT01_2023.csv.gz"),
               ("od/", "fl_od_main_JT00_2023.csv.gz"), ("od/", "fl_od_main_JT01_2023.csv.gz"),
               ("od/", "fl_od_aux_JT00_2023.csv.gz"), ("od/", "fl_od_aux_JT01_2023.csv.gz"),
               ("", "fl_xwalk.csv.gz"), ("", "lodes_fl.sha256sum"), ("", "version.txt")]
TERMS = "U.S. Census Bureau public data (U.S. government work, no copyright); cite the source and vintage"


def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def dump(p, o): Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def census_api_key():
    k = os.environ.get("CENSUS_API_KEY", "").strip()
    f = ROOT / ".secrets/census_api_key"
    if not k and f.exists(): k = f.read_text(encoding="utf-8").strip().splitlines()[0].strip() if f.read_text(encoding="utf-8").strip() else ""
    return k or None


def sources():
    out = [{"source_id": sid, "group": "tiger", "file": f, "url": u, "notes": n} for sid, f, u, n in TIGER_SOURCES]
    for sub, f in LODES_FILES:
        out.append({"source_id": f"lodes8_fl_{f.replace('.csv.gz', '').replace('.', '_')}", "group": "lodes", "file": f"lodes/{f}", "url": f"{LODES_BASE}fl/{sub}{f}",
                    "notes": "LODES 8, Florida, 2023" if "2023" in f else "LODES 8, Florida distribution file"})
    out.append({"source_id": "lodes8_techdoc_8_4", "group": "lodes", "file": "lodes/LODESTechDoc8.4.pdf", "url": f"{LODES_BASE}LODESTechDoc8.4.pdf",
                "notes": "LODES technical document 8.4 (2025-12-03): file definitions, main/aux, C000, job types"})
    for t in ACS_TABLES:
        out.append({"source_id": f"acs5_{ACS_VINTAGE}_{t}_bg_{STATE}{COUNTY}", "group": "acs", "file": f"acs/acs5_{ACS_VINTAGE}_bg_{STATE}{COUNTY}_{t}.json",
                    "url": f"https://api.census.gov/data/{ACS_VINTAGE}/acs/acs5?get=group({t})&for=block%20group:*&in=state:{STATE}%20county:{COUNTY}%20tract:*",
                    "notes": f"ACS 2020-{ACS_VINTAGE} 5-year, table {t}, all block groups of Miami-Dade; group() returns E/M/EA/MA columns", "api_key_used": None})
        out.append({"source_id": f"acs5_{ACS_VINTAGE}_{t}_dictionary", "group": "acs", "file": f"acs/groups/{t}.json",
                    "url": f"https://api.census.gov/data/{ACS_VINTAGE}/acs/acs5/groups/{t}.json", "notes": f"variable dictionary of {t} (labels, concept, universe)"})
    # B18101 (disability) is not published at block-group level (the BG pull returns null for every estimate): tract level for D13/R06.
    out.append({"source_id": f"acs5_{ACS_VINTAGE}_B18101_tract_{STATE}{COUNTY}", "group": "acs", "file": f"acs/acs5_{ACS_VINTAGE}_tract_{STATE}{COUNTY}_B18101.json",
                "url": f"https://api.census.gov/data/{ACS_VINTAGE}/acs/acs5?get=group(B18101)&for=tract:*&in=state:{STATE}%20county:{COUNTY}",
                "notes": "B18101 at TRACT level: the table is not published for block groups (all estimates null); D13/R06 are apportioned from tracts by land share",
                "api_key_used": None})
    return out


def is_acs_data_pull(entry): return entry["group"] == "acs" and "acs5?get=" in entry["url"]


def http_headers(url):
    r = subprocess.run(["curl", "-sSI", "--location", "--max-time", "60", url], capture_output=True, text=True)
    h = {}
    for line in r.stdout.replace("\r", "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1); h[k.strip().lower()] = v.strip()
    return h


def download(entry, prev):
    dest = RAW / entry["file"]; dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and prev and prev.get("sha256") == sha_file(dest):
        return {**prev, "status": "kept_verified"}
    url = entry["url"]; fetch_url = url
    if is_acs_data_pull(entry):
        key = census_api_key()
        if not key:
            return {**entry, "status": "blocked_missing_api_key", "api_key_used": False,
                    "how_to_unblock": "get a free key at https://api.census.gov/data/key_signup.html, then export CENSUS_API_KEY or write it to .secrets/census_api_key and rerun"}
        fetch_url = url + "&key=" + key; entry["api_key_used"] = True
    part = dest.with_name(dest.name + ".part")
    # the URL (which may carry the key) goes to curl through a stdin config file, never through argv
    r = subprocess.run(["curl", "-K", "-", "--fail", "--location", "--silent", "--show-error", "--max-time", "900", "--retry", "3",
                        "--output", str(part)], input=f'url = "{fetch_url}"\n', capture_output=True, text=True)
    if r.returncode != 0 or not part.exists() or part.stat().st_size == 0:
        raise SystemExit(f"download failed: {entry['file']}: {r.stderr.strip()[:300]}")
    if entry["group"] == "acs":   # the API answers errors as HTML/text; a valid answer is a JSON array (data) or object (dictionary)
        head = part.read_bytes()[:1]
        if head not in (b"[", b"{"):
            title = part.read_text(errors="replace"); title = title[title.find("<title>") + 7:title.find("</title>")] if "<title>" in title else title[:120]
            part.unlink()
            raise SystemExit(f"ACS response is not JSON for {entry['file']} (API said: {title.strip()!r}); the key is never stored — check it and rerun")
    os.replace(part, dest)
    h = http_headers(url if entry["group"] != "acs" else url)
    return {**entry, "bytes": dest.stat().st_size, "sha256": sha_file(dest), "retrieved_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "http_last_modified": h.get("last-modified"), "http_etag": h.get("etag"), "http_content_type": h.get("content-type"),
            "terms": TERMS, "status": "downloaded"}


def official_lodes_checksums():
    """LEHD publishes sha256 of the UNCOMPRESSED csv files (names without .gz) -> {csv name: sha256}."""
    p = RAW / "lodes/lodes_fl.sha256sum"; out = {}
    if not p.exists(): return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2: out[Path(parts[-1]).name.lstrip("*")] = parts[0]
    return out


def sha_gunzip(p):
    """sha256 of the decompressed content of a .gz file (streamed)."""
    h = hashlib.sha256()
    with gzip.open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()


def official_name(gz_file): return Path(gz_file).name[:-3] if gz_file.endswith(".gz") else Path(gz_file).name


# ---------------------------------------------------------------- validation ----------------------------------------------------------------
def read_shapefile_zip(zip_path):
    import shapefile
    z = zipfile.ZipFile(zip_path); names = z.namelist()
    pick = lambda ext: io.BytesIO(z.read(next(n for n in names if n.lower().endswith(ext))))
    r = shapefile.Reader(shp=pick(".shp"), shx=pick(".shx"), dbf=pick(".dbf"))
    fields = [f[0] for f in r.fields if f[0] != "DeletionFlag"]
    prj = next((z.read(n).decode(errors="replace") for n in names if n.lower().endswith(".prj")), None)
    return r, fields, prj


def validate(manifest):
    from shapely.geometry import shape
    from shapely.ops import unary_union, transform as shp_transform
    from pyproj import Transformer
    import shapefile
    lock = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line: k, v = line.split("==", 1); lock[k.strip().lower()] = v.strip()
    checks, hard_fail = {}, []
    def hard(name, ok, detail=None):
        checks[name] = {"pass": bool(ok), **({"detail": detail} if detail is not None else {})}
        if not ok: hard_fail.append(name)
    hard("pyshp_version_matches_lock", shapefile.__version__ == lock.get("pyshp"), {"lock": lock.get("pyshp"), "actual": shapefile.__version__})
    blocked = [s["file"] for s in manifest["sources"] if s.get("status") == "blocked_missing_api_key"]
    by_file = {s["file"]: s for s in manifest["sources"] if s.get("sha256")}
    hard("every_acquired_source_present", all((RAW / f).exists() for f in by_file), [f for f in by_file if not (RAW / f).exists()])
    hard("every_sha256_matches_manifest", all(sha_file(RAW / f) == s["sha256"] for f, s in by_file.items() if (RAW / f).exists()))

    # ---- TIGER block groups (state file) ----
    r, fields, prj = read_shapefile_zip(RAW / "tiger/tl_2024_12_bg.zip")
    bg_geoms, bg_land, bg_water = {}, {}, {}
    n_state = 0
    for sr in r.iterShapeRecords():
        rec = dict(zip(fields, list(sr.record))); n_state += 1
        if rec["STATEFP"] == STATE and rec["COUNTYFP"] == COUNTY:
            bg_geoms[rec["GEOID"]] = shape(sr.shape.__geo_interface__); bg_land[rec["GEOID"]] = int(rec["ALAND"]); bg_water[rec["GEOID"]] = int(rec["AWATER"])
    checks["tiger_bg"] = {"state_features": n_state, "county_086_block_groups": len(bg_geoms), "fields": fields, "crs_prj_head": (prj or "")[:60],
                          "county_land_m2": sum(bg_land.values()), "county_water_m2": sum(bg_water.values())}
    hard("tiger_bg_county_count_plausible", 1000 <= len(bg_geoms) <= 3000, len(bg_geoms))
    hard("tiger_bg_geoid_12_digits", all(len(g) == 12 for g in bg_geoms))

    # ---- TIGER 2020 blocks (county PL file) ----
    r, fields, prj = read_shapefile_zip(RAW / "tiger/tl_2020_12086_tabblock20.zip")
    blk, blk_land, blk_water, blk_bg = {}, {}, {}, defaultdict(list); bad_county = 0
    for sr in r.iterShapeRecords():
        rec = dict(zip(fields, list(sr.record)))
        if rec["COUNTYFP20"] != COUNTY: bad_county += 1
        g = rec["GEOID20"]; blk[g] = shape(sr.shape.__geo_interface__); blk_land[g] = int(rec["ALAND20"]); blk_water[g] = int(rec["AWATER20"]); blk_bg[g[:12]].append(g)
    checks["tiger_blocks"] = {"county_blocks": len(blk), "fields": fields, "crs_prj_head": (prj or "")[:60], "water_only_blocks_ALAND20_zero": sum(1 for v in blk_land.values() if v == 0),
                              "county_land_m2": sum(blk_land.values()), "county_water_m2": sum(blk_water.values()), "features_not_in_county_086": bad_county}
    hard("tiger_blocks_all_in_county", bad_county == 0)
    hard("tiger_blocks_geoid_15_digits", all(len(g) == 15 for g in blk))
    missing_bg = sorted(set(blk_bg) - set(bg_geoms)); empty_bg = sorted(set(bg_geoms) - set(blk_bg))
    hard("block_bg_prefixes_match_2024_bg_set", not missing_bg and not empty_bg, {"block_prefixes_without_2024_bg": missing_bg[:10], "bgs_without_blocks": empty_bg[:10]})
    # geometry nesting: 2020-PL blocks unioned per BG vs 2024 BG polygon (symmetric difference share, projected)
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:26917", always_xy=True); proj = lambda g: shp_transform(fwd.transform, g)
    worst, flagged = 0.0, []
    for gid, geom in bg_geoms.items():
        if gid not in blk_bg: continue
        u = unary_union([blk[b] for b in blk_bg[gid]]); a = proj(geom); bu = proj(u)
        share = a.symmetric_difference(bu).area / a.area if a.area else 0.0
        worst = max(worst, share)
        if share > 0.005: flagged.append({"bg": gid, "sym_diff_share": round(share, 5)})
    checks["block_bg_geometry_nesting"] = {"bgs_checked": sum(1 for g in bg_geoms if g in blk_bg), "max_symmetric_difference_share": round(worst, 6),
                                           "bgs_over_0_5_percent": len(flagged), "examples": flagged[:10],
                                           "note": "2020 P.L. block geometry vs TIGER 2024 block-group geometry; boundary edits between vintages show up here"}
    hard("block_bg_nesting_within_1_percent_for_all_bgs", worst <= 0.01, round(worst, 6))
    # land totals vs attribute: Σ ALAND20 of blocks per BG vs BG ALAND (attribute consistency across vintages)
    diffs = [abs(sum(blk_land[b] for b in blk_bg[g]) - bg_land[g]) / bg_land[g] for g in bg_geoms if g in blk_bg and bg_land[g] > 0]
    checks["aland_consistency_blocks_vs_bg"] = {"max_relative_diff": round(max(diffs), 6) if diffs else None, "bgs_over_1_percent": sum(1 for d in diffs if d > 0.01)}

    # ---- TIGER area water ----
    r, fields, prj = read_shapefile_zip(RAW / "tiger/tl_2024_12086_areawater.zip")
    n_w, awater = 0, 0
    for sr in r.iterShapeRecords():
        rec = dict(zip(fields, list(sr.record))); n_w += 1; awater += int(rec.get("AWATER", 0) or 0)
    checks["tiger_areawater"] = {"features": n_w, "fields": fields, "sum_AWATER_m2": awater, "county_AWATER20_from_blocks_m2": sum(blk_water.values())}
    hard("areawater_has_features", n_w > 0)

    # ---- ACS ----
    acs = {}
    for t in ACS_TABLES:
        data_file = RAW / f"acs/acs5_{ACS_VINTAGE}_bg_{STATE}{COUNTY}_{t}.json"
        d = load(RAW / f"acs/groups/{t}.json")["variables"] if (RAW / f"acs/groups/{t}.json").exists() else {}
        if not data_file.exists():
            label_ok = {var: (exp.lower() in d.get(var, {}).get("label", "").lower()) for (tt, var), exp in LABEL_ASSERTS.items() if tt == t}
            universe = next((v.get("universe") for v in d.values() if v.get("universe")), None)
            acs[t] = {"status": "NOT_ACQUIRED_MISSING_API_KEY", "dictionary_present": bool(d), "label_asserts": label_ok, "universe": universe,
                      "contract_variables_in_dictionary": [v for s in CONTRACT_VARS[t] for k in ("E", "M") if (v := f"{t}_{s}{k}") not in d]}
            checks[f"acs_{t}_data"] = {"pass": None, "skipped": "blocked_missing_api_key"}
            if d:
                hard(f"acs_{t}_labels_as_contract", all(label_ok.values()), label_ok)
                hard(f"acs_{t}_dictionary_has_contract_variables", not acs[t]["contract_variables_in_dictionary"], acs[t]["contract_variables_in_dictionary"])
                if t in UNIVERSE_ASSERTS: hard(f"acs_{t}_universe_as_contract", UNIVERSE_ASSERTS[t].lower() in (universe or "").lower(), universe)
            continue
        data = load(data_file); header, rows = data[0], data[1:]
        geoids = {row[header.index("GEO_ID")].split("US")[-1] for row in rows}
        need = [f"{t}_{s}{k}" for s in CONTRACT_VARS[t] for k in ("E", "M")]
        missing = [v for v in need if v not in header]
        special = Counter()
        for row in rows:
            for i, v in enumerate(row):
                if header[i].endswith(("E", "M")) and header[i].startswith(t) and isinstance(v, str) and v.startswith("-") and len(v) >= 10: special[v] += 1
        label_ok = {var: (exp.lower() in d.get(var, {}).get("label", "").lower()) for (tt, var), exp in LABEL_ASSERTS.items() if tt == t}
        universe = next((v.get("universe") for v in d.values() if v.get("universe")), None)
        ecols = [i for i, h in enumerate(header) if h.startswith(t) and h.endswith("E") and h[-2] != "E"]
        all_null = sum(1 for r in rows if all(r[i] is None for i in ecols))
        acs[t] = {"rows": len(rows), "columns": len(header), "county_block_groups_in_response": len(geoids), "contract_variables_missing": missing,
                  "special_values": dict(special), "label_asserts": label_ok, "universe": universe,
                  "geoid_set_equals_tiger_2024_county_bgs": geoids == set(bg_geoms),
                  "rows_with_all_estimates_null": all_null, "published_at_block_group": all_null < len(rows)}
        hard(f"acs_{t}_contract_variables_present", not missing, missing)
        hard(f"acs_{t}_geoids_match_tiger_bgs", geoids == set(bg_geoms), {"only_in_acs": sorted(geoids - set(bg_geoms))[:5], "only_in_tiger": sorted(set(bg_geoms) - geoids)[:5]})
        hard(f"acs_{t}_labels_as_contract", all(label_ok.values()), label_ok)
        if t in UNIVERSE_ASSERTS: hard(f"acs_{t}_universe_as_contract", UNIVERSE_ASSERTS[t].lower() in (universe or "").lower(), universe)
        if t != "B18101": hard(f"acs_{t}_published_at_block_group", all_null == 0, all_null)
    # tract-level B18101 (D13/R06): tract GEOIDs must be exactly the 11-digit prefixes of the county block groups
    tp = RAW / f"acs/acs5_{ACS_VINTAGE}_tract_{STATE}{COUNTY}_B18101.json"
    if tp.exists():
        data = load(tp); header, rows = data[0], data[1:]
        tracts = {row[header.index("GEO_ID")].split("US")[-1] for row in rows}; prefixes = {g[:11] for g in bg_geoms}
        ecols = [i for i, h in enumerate(header) if h.startswith("B18101") and h.endswith("E") and h[-2] != "E"]
        all_null = sum(1 for r in rows if all(r[i] is None for i in ecols))
        need = [f"B18101_{s}{k}" for s in CONTRACT_VARS["B18101"] for k in ("E", "M")]
        acs["B18101_tract"] = {"rows": len(rows), "tracts_equal_bg_prefixes": tracts == prefixes, "rows_with_all_estimates_null": all_null,
                               "contract_variables_missing": [v for v in need if v not in header], "geography": "tract",
                               "reason": "B18101 is not published at block-group level; D13/R06 use tract estimates apportioned by land share"}
        hard("acs_B18101_tract_geoids_match_bg_prefixes", tracts == prefixes, {"only_tract": sorted(tracts - prefixes)[:5], "only_prefix": sorted(prefixes - tracts)[:5]})
        hard("acs_B18101_tract_has_estimates", all_null == 0, all_null)
        hard("acs_B18101_tract_contract_variables_present", not acs["B18101_tract"]["contract_variables_missing"], acs["B18101_tract"]["contract_variables_missing"])
    else:
        checks["acs_B18101_tract_data"] = {"pass": None, "skipped": "not acquired"}
    checks["acs"] = acs

    # ---- LODES ----
    official = official_lodes_checksums()
    lodes = {"version_txt": (RAW / "lodes/version.txt").read_text(encoding="utf-8", errors="replace").strip()[:200], "official_checksums_listed": len(official), "files": {}}
    for sub, f in LODES_FILES:
        if not f.endswith(".csv.gz"): continue
        local_gz = sha_file(RAW / "lodes" / f); local_csv = sha_gunzip(RAW / "lodes" / f); off = official.get(official_name(f))
        lodes["files"][f] = {"sha256_gz": local_gz, "sha256_uncompressed": local_csv, "publisher_sha256_uncompressed": off,
                             "publisher_verified": (off == local_csv) if off else None}
        hard(f"lodes_{f}_matches_publisher_sha256", off == local_csv, {"publisher_uncompressed": off, "local_uncompressed": local_csv})
    # crosswalk: county block universe
    xw_blocks, xw_rows = set(), 0
    with gzip.open(RAW / "lodes/fl_xwalk.csv.gz", "rt", encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split(","); i_blk, i_cty = header.index("tabblk2020"), header.index("cty")
        for line in fh:
            xw_rows += 1; parts = line.rstrip("\n").split(",")
            if parts[i_cty] == STATE + COUNTY: xw_blocks.add(parts[i_blk])
    lodes["xwalk"] = {"rows_state": xw_rows, "county_blocks": len(xw_blocks), "in_tiger_not_in_xwalk": len(set(blk) - xw_blocks), "in_xwalk_not_in_tiger": len(xw_blocks - set(blk))}
    hard("lodes_xwalk_county_blocks_equal_tiger_2020_blocks", xw_blocks == set(blk), lodes["xwalk"])
    def county_sum(fname, geocol):
        rows_c, jobs_c, rows_all = 0, 0, 0
        with gzip.open(RAW / "lodes" / fname, "rt", encoding="utf-8", errors="replace") as fh:
            header = fh.readline().rstrip("\n").split(","); ig, ic = header.index(geocol), header.index("C000")
            for line in fh:
                rows_all += 1; parts = line.split(",", max(ig, ic) + 1)
                if parts[ig].startswith(STATE + COUNTY): rows_c += 1; jobs_c += int(parts[ic])
        return {"rows_state": rows_all, "rows_county": rows_c, "C000_county": jobs_c}
    for f, col in [("fl_wac_S000_JT00_2023.csv.gz", "w_geocode"), ("fl_wac_S000_JT01_2023.csv.gz", "w_geocode"),
                   ("fl_rac_S000_JT00_2023.csv.gz", "h_geocode"), ("fl_rac_S000_JT01_2023.csv.gz", "h_geocode")]:
        lodes["files"][f].update(county_sum(f, col))
    def od_counts(fname):
        both = home = work = rows = 0
        with gzip.open(RAW / "lodes" / fname, "rt", encoding="utf-8", errors="replace") as fh:
            header = fh.readline().rstrip("\n").split(","); iw, ih, iS = header.index("w_geocode"), header.index("h_geocode"), header.index("S000")
            for line in fh:
                rows += 1; p = line.split(",", 3); w_in, h_in = p[iw].startswith(STATE + COUNTY), p[ih].startswith(STATE + COUNTY)
                if w_in and h_in: both += int(p[iS])
                elif h_in: home += int(p[iS])
                elif w_in: work += int(p[iS])
        return {"rows_state": rows, "S000_both_in_county": both, "S000_home_in_county_only": home, "S000_work_in_county_only": work}
    for f in ["fl_od_main_JT00_2023.csv.gz", "fl_od_main_JT01_2023.csv.gz", "fl_od_aux_JT00_2023.csv.gz", "fl_od_aux_JT01_2023.csv.gz"]:
        lodes["files"][f].update(od_counts(f))
    wac00, rac00 = lodes["files"]["fl_wac_S000_JT00_2023.csv.gz"]["C000_county"], lodes["files"]["fl_rac_S000_JT00_2023.csv.gz"]["C000_county"]
    od00 = lodes["files"]["fl_od_main_JT00_2023.csv.gz"]; aux00 = lodes["files"]["fl_od_aux_JT00_2023.csv.gz"]
    lodes["reconciliation_JT00"] = {"wac_C000_county": wac00, "od_main_S000_work_in_county": od00["S000_both_in_county"] + od00["S000_work_in_county_only"],
                                    "od_aux_S000_work_in_county": aux00["S000_both_in_county"] + aux00["S000_work_in_county_only"],
                                    "note": "WAC jobs in the county should equal OD main (work in county) + OD aux (work in county, residence out of state)"}
    hard("lodes_wac_equals_od_main_plus_aux_work_in_county", wac00 == lodes["reconciliation_JT00"]["od_main_S000_work_in_county"] + lodes["reconciliation_JT00"]["od_aux_S000_work_in_county"],
         lodes["reconciliation_JT00"])
    lodes["rac_vs_od_home_in_county_JT00"] = {"rac_C000_county": rac00, "od_main_S000_home_in_county": od00["S000_both_in_county"] + od00["S000_home_in_county_only"],
                                              "note": "RAC counts residents' jobs incl. those held out of state, which are NOT in the Florida main/aux files (declared gap); RAC >= OD main home-in-county"}
    checks["lodes"] = lodes
    status = "FAIL" if hard_fail else ("PARTIAL" if blocked else "PASS")
    return {"status": status, "failed_checks": hard_fail, "blocked_sources": blocked, "checked_on": "2026-09-15", "checks": checks,
            "scope": "acquisition integrity and contract-variable presence only; not an analysis result",
            "partial_note": ("ACS data pulls need a Census API key; TIGER, LODES and the ACS variable dictionaries are acquired and verified. "
                             "Rerun after providing the key (CENSUS_API_KEY or .secrets/census_api_key)." if blocked else None)}


def main():
    validate_only = "--validate-only" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    prev = {s["file"]: s for s in load(MANIFEST)["sources"]} if MANIFEST.exists() else {}
    entries = sources()
    if not validate_only:
        results = []
        for e in entries:
            res = download(e, prev.get(e["file"])); results.append(res)
            print(f"{res['status']:24s} {res.get('bytes', 0):>11,d}  {res['file']}")
        official = official_lodes_checksums()
        for res in results:
            if res["group"] == "lodes" and res["file"].endswith(".csv.gz"):
                off = official.get(official_name(res["file"])); unc = sha_gunzip(RAW / res["file"])
                res["sha256_uncompressed"] = unc; res["publisher_sha256_uncompressed"] = off
                res["publisher_sha256_verified"] = (off == unc) if off else None
                res["checksum_note"] = "the publisher's lodes_fl.sha256sum lists sha256 of the decompressed csv; sha256 above is of the .gz as downloaded"
        manifest = {"retrieved_on": "2026-09-15", "acquisition_stage": "miami_v2_raw", "contract": "V2_站点输入包字段契约.md §1",
                    "acs": {"dataset": "acs/acs5", "vintage": ACS_VINTAGE, "period": "2020-2024", "geography": "block group", "state": STATE, "county": COUNTY,
                            "api_key": "read from CENSUS_API_KEY at run time if set; never stored", "tables": ACS_TABLES},
                    "lodes": {"version": "LODES8", "state": "fl", "year": 2023, "job_types": ["JT00", "JT01"], "segment": "S000",
                              "publisher_checksum_file": "lodes/lodes_fl.sha256sum", "technical_document": "lodes/LODESTechDoc8.4.pdf",
                              "coverage_note": "main = residence and workplace in Florida; aux = workplace in Florida, residence out of state; "
                                               "Florida residents working out of state are NOT covered (declared gap)"},
                    "tiger": {"block_groups": "TIGER2024 BG (state file, 2020 delineation)", "blocks": "TIGER2020PL county tabblock20 (2020 census blocks)",
                              "water": "TIGER2024 AREAWATER (county)", "vintage_note": "2020-P.L. block geometry vs 2024 block-group geometry is cross-checked in acquisition_validation.json"},
                    "terms": TERMS, "fetch_script": {"path": "scripts/fetch_miami_v2_raw.py", "sha256": sha_file(Path(__file__))},
                    "sources": results}
        dump(MANIFEST, manifest)
        print(f"manifest -> {MANIFEST.relative_to(ROOT)} ({len(results)} sources)")
    manifest = load(MANIFEST)
    v = validate(manifest); dump(VALIDATION, v)
    print(f"validation: {v['status']} failed={v['failed_checks']} blocked={v['blocked_sources']} -> {VALIDATION.relative_to(ROOT)}")
    sys.exit(0 if v["status"] in ("PASS", "PARTIAL") else 1)


if __name__ == "__main__":
    main()
