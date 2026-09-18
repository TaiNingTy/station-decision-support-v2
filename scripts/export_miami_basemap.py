#!/usr/bin/env python3
"""Build an offline vector basemap for the presentation, using existing local GIS.

Presentation geometry only: never changes analytical packages or readiness. Roads
are OSM linework, water is TIGER/Line, blocks are census land polygons (not building
footprints), parks are the published POI geometry, routes are GTFS shape geometry.
All layers are projected into EPSG:26917, clipped, then simplified for display.
"""
import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from miami_v2_common import read_shapefile_zip, lock_gate
from pyproj import CRS, Transformer
from shapely import make_valid
from shapely.geometry import shape, box, LineString
from shapely.ops import transform, unary_union, linemerge

OUT = ROOT / "docs/data"
DATA = ROOT / "data/miami/2026-09-14"
load = lambda p: json.loads(p.read_text(encoding="utf-8"))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
environment = lock_gate()
demo_path = OUT / "demo_data.json"
demo = load(demo_path)
fwd = Transformer.from_crs(4326, 26917, always_xy=True)
window = transform(fwd.transform, shape(demo["geometry"]["window"]))
minx, miny, maxx, maxy = window.bounds
extent = box(minx, miny, maxx, maxy)
width, height = maxx - minx, maxy - miny


def xy(p):
    return [round(p[0] - minx, 1), round(maxy - p[1], 1)]


def path(g):
    if g.is_empty:
        return ""
    if g.geom_type in ("LineString", "LinearRing"):
        return "M" + "L".join(",".join(f"{v:g}" for v in xy(p)) for p in g.coords)
    if g.geom_type == "Polygon":
        return path(g.exterior) + "Z" + "".join(path(r) + "Z" for r in g.interiors)
    return "".join(path(part) for part in g.geoms)


def clip(g, tolerance=1.5):
    if not g.is_valid:
        g = make_valid(g)
    return g.intersection(extent).simplify(tolerance, preserve_topology=True)


water_zip = ROOT / "raw/miami/2026-09-15/tiger/tl_2024_12086_areawater.zip"
with zipfile.ZipFile(water_zip) as z:
    prj = z.read(next(n for n in z.namelist() if n.endswith(".prj"))).decode()
water_fwd = Transformer.from_crs(CRS.from_wkt(prj), 26917, always_xy=True)
water_geoms, water_names = [], defaultdict(list)
view_wgs = shape(demo["geometry"]["window"])
for attrs, g in read_shapefile_zip(water_zip):
    # TIGER's NAD83 bounds are suitable for this loose prefilter; projection below
    # uses the source .prj. A small margin avoids discarding edge features.
    if not box(*g.bounds).intersects(view_wgs.buffer(.001)):
        continue
    g = clip(transform(water_fwd.transform, g))
    if g.is_empty:
        continue
    water_geoms.append(g)
    if attrs.get("FULLNAME"):
        water_names[attrs["FULLNAME"]].append(g)
water = unary_union(water_geoms)

dem_ptr_path = DATA / "demography_current.json"
dem_ptr = load(dem_ptr_path)
blocks_path = DATA / dem_ptr["package_dir"] / "block_land_geometry.json"
blocks = []
for record in load(blocks_path)["blocks"].values():
    g = clip(shape(record["geometry"]))
    if g.is_empty or g.area < 80:
        continue
    # A visual gap differentiates street blocks; it is not a parcel setback.
    inset = g.buffer(-4)
    if not inset.is_empty:
        blocks.append(inset)

osm_path = ROOT / "raw/miami/2026-09-17/osm/walk_network_overpass.json"
osm = load(osm_path)
nodes = {r["id"]: fwd.transform(r["lon"], r["lat"]) for r in osm["elements"] if r["type"] == "node"}
roads = defaultdict(list)
named_roads = defaultdict(list)
class_by_tag = {
    **{k: "highway" for k in ("motorway", "motorway_link", "trunk", "trunk_link")},
    **{k: "arterial" for k in ("primary", "primary_link", "secondary", "secondary_link")},
    **{k: "local" for k in ("tertiary", "tertiary_link", "residential", "unclassified", "living_street")},
    "service": "service",
    **{k: "path" for k in ("footway", "pedestrian", "path", "cycleway", "steps")},
}
road_count = 0
for way in osm["elements"]:
    if way["type"] != "way":
        continue
    tags = way.get("tags", {})
    kind = class_by_tag.get(tags.get("highway"))
    if not kind:
        continue
    points = [nodes[n] for n in way["nodes"] if n in nodes]
    if len(points) < 2:
        continue
    g = clip(LineString(points), 2)
    if g.is_empty:
        continue
    road_count += 1
    roads[kind].append(g)
    if tags.get("name") and kind in ("arterial", "local", "highway"):
        named_roads[tags["name"]].append(g)

parks = []
for park in demo["geometry"]["parks"]:
    g = clip(transform(fwd.transform, shape(park["geometry"])))
    if not g.is_empty:
        parks.append({"name": park["name"], "path": path(g), "xy": xy(g.representative_point().coords[0]), "area_m2": round(g.area)})

gtfs_path = ROOT / "raw/miami/2026-09-11/google_transit.zip"
shape_ids = {r["shape_id"] for r in demo["geometry"]["loops"]}
route_points = defaultdict(list)
with zipfile.ZipFile(gtfs_path) as z:
    for row in csv.DictReader(io.TextIOWrapper(z.open("shapes.txt"), encoding="utf-8-sig")):
        if row["shape_id"] in shape_ids:
            route_points[row["shape_id"]].append((int(row["shape_pt_sequence"]), fwd.transform(float(row["shape_pt_lon"]), float(row["shape_pt_lat"]))))
routes = [{"shape_id": sid, "path": path(clip(LineString([p for _, p in sorted(points)]), 1))} for sid, points in sorted(route_points.items())]
assert set(route_points) == shape_ids, "Missing GTFS shapes"

labels = []
for name, lines in named_roads.items():
    merged = unary_union(lines)
    if merged.geom_type == "MultiLineString":
        merged = linemerge(merged)
    parts = [merged] if merged.geom_type == "LineString" else [g for g in merged.geoms if g.geom_type == "LineString"]
    if not parts:
        continue
    g = max(parts, key=lambda p: p.length)
    if g.length < 250:
        continue
    middle = g.interpolate(.5, normalized=True)
    a, b = g.interpolate(.43, normalized=True), g.interpolate(.57, normalized=True)
    angle = math.degrees(math.atan2(-(b.y - a.y), b.x - a.x))
    if angle > 90:
        angle -= 180
    if angle < -90:
        angle += 180
    short = name
    for before, after in (("Northeast", "NE"), ("Northwest", "NW"), ("Southeast", "SE"), ("Southwest", "SW"), ("Boulevard", "Blvd"), ("Avenue", "Ave"), ("Street", "St")):
        short = short.replace(before, after)
    priority = 2 if name in ("Biscayne Boulevard", "Brickell Avenue", "North Miami Avenue", "South Miami Avenue", "Southwest 8th Street", "Northeast 2nd Avenue") else 1
    labels.append({"name": short, "xy": xy(middle.coords[0]), "angle": round(angle, 1), "length_m": round(g.length), "priority": priority})
labels.sort(key=lambda r: (-r["priority"], -r["length_m"], r["name"]))
water_labels = []
for name, gs in water_names.items():
    g = unary_union(gs)
    if g.area > 150000:
        water_labels.append({"name": name, "xy": xy(g.representative_point().coords[0]), "area_m2": round(g.area)})

basemap = {
    "schema_version": "miami-presentation-basemap/1.0",
    "crs": "EPSG:26917",
    "coordinate_frame": {"x": "easting minus min_easting", "y": "max_northing minus northing", "units": "m", "origin": [minx, maxy]},
    "width": round(width, 1), "height": round(height, 1),
    "water": path(water), "blocks": "".join(path(b) for b in blocks),
    "roads": {k: "".join(path(g) for g in gs) for k, gs in roads.items()},
    "parks": parks, "routes": routes, "road_labels": labels, "water_labels": water_labels,
    "stations": {s["id"]: xy(fwd.transform(s["lon"], s["lat"])) for s in demo["stations"]},
    "osm_data_timestamp": osm.get("osm3s", {}).get("timestamp_osm_base"),
    "attribution": "© OpenStreetMap contributors (ODbL) · U.S. Census Bureau TIGER/Line · Miami-Dade Transit GTFS · City / County parks",
    "notes": ["Gray polygons show census street blocks, not individual buildings.", "Paths are cartographic context, not a validated walk network.", "Routes follow GTFS shapes, not surveyed guideway geometry."],
}
text = json.dumps(basemap, ensure_ascii=False, separators=(",", ":"))
output = OUT / "miami_basemap.js"
output.write_text("window.MIAMI_BASEMAP = " + text + ";\n", encoding="utf-8")
sources = [demo_path, blocks_path, osm_path, water_zip, gtfs_path]
manifest = {
    "purpose": "offline cartography only; no change to analysis packages",
    "sources": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p)} for p in sources],
    "output": {"path": str(output.relative_to(ROOT)), "sha256": sha(output), "bytes": output.stat().st_size},
    "script_sha256": sha(Path(__file__)), "environment": environment,
    "counts": {"census_blocks": len(blocks), "road_path_ways": road_count, "parks": len(parks), "gtfs_shapes": len(routes), "stations": len(basemap["stations"])},
    "simplification_m": {"polygons": 1.5, "roads": 2, "gtfs_shapes": 1},
    "geometry_scope": "station study window in EPSG:26917; display only", "notes": basemap["notes"],
}
(OUT / "miami_basemap_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": str(output), "bytes": output.stat().st_size, "counts": manifest["counts"]}))
