#!/usr/bin/env python3
"""Export the inputs of the two GIS reading agents (V2 step 11): per station g1_input.json (roads, rail, guideway, zoning,
land use, parcels), g2_input.json (heat-proxy cells, block groups, zoning for the joint reading) and heat.png (the
proxy map the vision model looks at), plus a mirror under docs/gis/ so the Coze HTTP node can fetch them from the public
site. Nothing is recomputed: tables are copied from the verified gis_objects package; geometry is reloaded only to draw.

    python3 scripts/export_miami_gis_agent_inputs.py
"""
import csv, io, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.lines import Line2D
from shapely.geometry import LineString

PUBLIC_BASE = "https://tainingty.github.io/station-decision-support-v2/gis"
OUT, MIRROR = ROOT / "ai/miami/gis", ROOT / "docs/gis"
QCOL = {1: "#F1EEF6", 2: "#D4B9DA", 3: "#C994C7", 4: "#DF65B0", 5: "#980043"}
ptr = load(DATA / "gis_objects_current.json"); pdir = DATA / ptr["package_dir"]; ok, m, problems = verify_package(pdir, "manifest.json")
if not ok: raise SystemExit(f"HALT: gis_objects package does not verify: {problems}")
G = load(pdir / "station_gis_objects.json"); grid = load(pdir / "heat_grid.json"); cfg = load(ROOT / "config/gis_objects_v1.json")
kit = load(ROOT / "ai/miami/kit_manifest.json") if (ROOT / "ai/miami/kit_manifest.json").exists() else {}
fwd, inv, _ = projection(); proj = lambda g: shp_transform(fwd.transform, g)
tg = load(DATA / load(DATA / "demography_current.json")["package_dir"] / "analysis_targets_26917.json"); RADII_M = [r * FOOT_M for r in tg["bands"]["radii_ft"]]
st_pt = {f["properties"]["station_id"]: proj(shape(f["geometry"])) for f in load(DATA / "station_master.geojson")["features"]}
# drawing geometry only
RAW20 = RAW15.parent / "2026-09-20/gis_objects"
zoning = [polygonal(proj(shape(f["geometry"]))) for f in load(RAW15.parent / "2026-09-14/zoning_study_window.geojson")["features"]]
osm = load(RAW15.parent / "2026-09-17/osm/walk_network_overpass.json"); ll = {e["id"]: (e["lon"], e["lat"]) for e in osm["elements"] if e["type"] == "node"}
nid = sorted(ll); xs, ys = fwd.transform([ll[n][0] for n in nid], [ll[n][1] for n in nid]); xy = {n: (x, y) for n, x, y in zip(nid, xs, ys)}
ROAD_W = {"motorway": 2.2, "motorway_link": 1.4, "trunk": 2.0, "trunk_link": 1.3, "primary": 1.6, "secondary": 1.2, "tertiary": 0.9}
roads = [(e["tags"]["highway"], [xy[n] for n in e["nodes"] if n in xy]) for e in osm["elements"] if e["type"] == "way" and e.get("tags", {}).get("highway") in ROAD_W]
rail = unary_union([proj(shape(f["geometry"])) for f in load(RAW20 / "railroads.geojson.json")["features"]])
shape_ids = {str(r["shape_id"]) for r in load(DATA / "service_patterns.json")["records"] if r.get("shape_id")}
with zipfile.ZipFile(RAW15.parent / "2026-09-11/google_transit.zip") as zf:
    rows = [r for r in csv.DictReader(io.TextIOWrapper(zf.open("shapes.txt"), encoding="utf-8-sig")) if r["shape_id"] in shape_ids]
bs = defaultdict(list)
for r in rows: bs[r["shape_id"]].append((int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
guideway = [[fwd.transform(lo, la) for _, lo, la in sorted(v)] for v in bs.values()]
rail_other = rail.difference(unary_union([LineString(g) for g in guideway]).buffer(cfg["rail"]["split_buffer_m"]))


def lines(geom):
    if geom.is_empty: return []
    return [list(g.coords) for g in (geom.geoms if hasattr(geom, "geoms") else [geom]) if g.geom_type == "LineString"]


def draw(pid, name, path, extent_m):
    O = st_pt[pid]; x0, x1, y0, y1 = O.x - extent_m, O.x + extent_m, O.y - extent_m, O.y + extent_m
    fig, ax = plt.subplots(figsize=(8, 8.6), dpi=110); ax.set_facecolor("#DCE7F0")
    for c in grid["cells"]:
        bx0, by0, bx1, by1 = c["bounds_m"]
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1: continue
        q = c.get("network_quintile")
        ax.add_patch(Rectangle((bx0, by0), bx1 - bx0, by1 - by0, facecolor=(QCOL[q] if q else "#FFFFFF"), edgecolor="#FFFFFF", linewidth=0.4, alpha=(0.95 if q else 0.0), zorder=1))
    for z in zoning:
        for poly in (z.geoms if hasattr(z, "geoms") else [z]):
            if poly.is_empty or not poly.intersects(O.buffer(extent_m * 1.5)): continue
            xs_, ys_ = poly.exterior.xy; ax.plot(xs_, ys_, color="#1F3B57", linewidth=0.7, alpha=0.75, zorder=2)
    for cls, pts in roads:
        if len(pts) > 1: ax.plot([p[0] for p in pts], [p[1] for p in pts], color=("#5C4A1E" if cls.startswith(("motorway", "trunk")) else "#6B7280"), linewidth=ROAD_W[cls], alpha=0.85, zorder=3, solid_capstyle="round")
    for pts in lines(rail_other): ax.plot([p[0] for p in pts], [p[1] for p in pts], color="#111827", linewidth=1.3, linestyle=(0, (4, 3)), zorder=4)
    for pts in guideway: ax.plot([p[0] for p in pts], [p[1] for p in pts], color="#0B7285", linewidth=2.4, zorder=5)
    for r in RADII_M: ax.add_patch(Circle((O.x, O.y), r, fill=False, edgecolor="#111827", linewidth=1.0, linestyle=(0, (3, 3)), zorder=6))
    ax.plot([O.x], [O.y], marker="o", markersize=9, markerfacecolor="#FFFFFF", markeredgecolor="#111827", markeredgewidth=2, zorder=7)
    sb = 1000 * FOOT_M; sx, sy = x0 + 40, y0 + 45
    ax.plot([sx, sx + sb], [sy, sy], color="#111827", linewidth=3, zorder=8); ax.text(sx + sb / 2, sy + 22, "1,000 ft", ha="center", fontsize=9, zorder=8)
    ax.annotate("N", xy=(x1 - 60, y1 - 50), xytext=(x1 - 60, y1 - 190), ha="center", fontsize=11, arrowprops=dict(arrowstyle="-|>", color="#111827", lw=1.6), zorder=8)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"{name} ({pid}) · activity-density PROXY, 500 ft cells", fontsize=12, loc="left", pad=8)
    handles = [Rectangle((0, 0), 1, 1, facecolor=QCOL[q], edgecolor="none") for q in (1, 2, 3, 4, 5)] + [Line2D([0], [0], color="#1F3B57", lw=0.9), Line2D([0], [0], color="#5C4A1E", lw=2.2), Line2D([0], [0], color="#6B7280", lw=1.4),
               Line2D([0], [0], color="#0B7285", lw=2.4), Line2D([0], [0], color="#111827", lw=1.3, linestyle=(0, (4, 3))), Line2D([0], [0], color="#111827", lw=1.0, linestyle=(0, (3, 3)))]
    labels = ["network quintile 1 (lowest)", "quintile 2", "quintile 3", "quintile 4", "quintile 5 (hot)", "zoning polygon outline", "motorway / trunk", "primary / secondary / tertiary", "Metromover guideway", "other railroad", "1/8, 1/4, 1/2 mile rings"]
    ax.legend(handles, labels, loc="lower right", fontsize=7.5, framealpha=0.92, ncol=1)
    fig.text(0.02, 0.008, "PROXY: 2020 Census residents + 2023 LODES jobs per acre of land. Not measured activity, not ridership, not persons per hour.\n"
                          "Values are spread evenly over each census block's land, so a park or plaza inside a block inherits the block's density. Blank cells have no land (water).\n"
                          "Auxiliary evidence, to be read together with zoning and land use; it decides nothing. Roads (c) OpenStreetMap contributors; zoning City of Miami; rail Miami-Dade County.", fontsize=6.9, va="bottom")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.095)
    fig.savefig(path, dpi=110, metadata={"Software": None}); plt.close(fig)


COMMON = {"principle": cfg["principle"], "gis_config_version": cfg["version"], "gis_objects_package": ptr["package_id"], "kit_version": kit.get("kit_version"),
          "id_rule": "cite object_id for features and fact_id (.Gnnn) for code-computed summary numbers; write no number that is not in this input",
          "roles_allowed": ["origin", "destination", "facility_to_convert", "obstacle", "candidate_site", "context", "not_relevant"]}
files = []
for b in G["stations"]:
    pid, name, o = b["station_id"], b["name"], b["objects"]; d = OUT / pid; d.mkdir(parents=True, exist_ok=True)
    fg = lambda groups: [f for f in b["summary_facts"] if f["group"] in groups]
    g1 = {"input_id": f"{pid}.G1", "agent": "G1 GIS reader (roads, rail, guideway, zoning, land use, parcels)", "station_id": pid, "name": name, **COMMON, "reference_point_note": b["reference_point_note"],
          "parcel_privacy": cfg["parcels"]["privacy"], "parcel_table_rule": cfg["parcels"]["table_rule"], "rail_split_rule": cfg["rail"]["split_rule"],
          "objects": {k: o[k] for k in ("roads", "rail", "guideway", "zoning", "land_use", "parcels", "parcel_groups_all_parcels")}, "summary_facts": fg(("roads", "rail", "zoning", "land_use", "parcels")), "rows_cut": b["rows_cut"]}
    g2 = {"input_id": f"{pid}.G2", "agent": "G2 heat and residents reader (heat-proxy cells + image, block groups, zoning for the joint reading)", "station_id": pid, "name": name, **COMMON,
          "heat_proxy": {k: cfg["heat_proxy"][k] for k in ("metric", "label", "is_measured_ridership_heat", "is_persons_per_hour", "residents_source", "jobs_source", "hot_definition", "cell_size_ft", "known_limitation")},
          "heat_image_url": f"{PUBLIC_BASE}/{pid}/heat.png", "objects": {"heat_cells": o["heat_cells"], "block_groups": o["block_groups"], "zoning": o["zoning"]}, "summary_facts": fg(("heat", "zoning", "land_use"))}
    for fn, obj in (("g1_input.json", g1), ("g2_input.json", g2)):
        (d / fn).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    draw(pid, name, d / "heat.png", RADII_M[2] + 90.0)
    brief = ROOT / "ai/miami/briefs" / f"{pid}.coze.json"
    if brief.exists(): shutil.copyfile(brief, d / "brief.coze.json")
    (MIRROR / pid).mkdir(parents=True, exist_ok=True)
    for fn in ("g1_input.json", "g2_input.json", "heat.png", "brief.coze.json"):
        if (d / fn).exists(): shutil.copyfile(d / fn, MIRROR / pid / fn); files.append({"station_id": pid, "file": f"ai/miami/gis/{pid}/{fn}", "public_url": f"{PUBLIC_BASE}/{pid}/{fn}", "bytes": (d / fn).stat().st_size, "sha256": sha_file(d / fn)})
man = {"schema_version": "miami-gis-agent-inputs/1.0", "generated_on": "2026-09-20", "gis_objects_package": ptr["package_id"], "gis_config_version": cfg["version"], "kit_version": kit.get("kit_version"),
       "public_base": PUBLIC_BASE, "note": "mirrored under docs/gis/ so the Coze HTTP node can fetch the inputs after the repository is pushed; the images are the heat PROXY, labelled as such inside the picture",
       "environment": {"matplotlib": matplotlib.__version__}, "files": files}
dump(OUT / "manifest.json", man); shutil.copyfile(OUT / "manifest.json", MIRROR / "manifest.json")
sz = lambda fn: sum(f["bytes"] for f in files if f["file"].endswith(fn))
print(f"exported stations={len(G['stations'])} files={len(files)} g1_total={sz('g1_input.json')} g2_total={sz('g2_input.json')} png_total={sz('heat.png')} package={ptr['package_id']}")
