#!/usr/bin/env python3
"""Generate kb/v2/KB_V2_06_layer_legends.md from the layers themselves, so the reading agents decode codes against what
the sources actually carry. Every legend entry comes from an attribute of the archived layer or from config; where a
source does not define a symbol, the legend says so instead of filling the gap.
    python3 scripts/build_miami_kb_legends.py
"""
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

OUT = ROOT / "kb/v2/KB_V2_06_layer_legends.md"
cfg = load(ROOT / "config/gis_objects_v1.json")
zon = [f["properties"] for f in load(RAW15.parent / "2026-09-14/zoning_study_window.geojson")["features"]]
lu = [f["properties"] for f in load(RAW15.parent / "2026-09-20/gis_objects/land_use.geojson.json")["features"]]
par = [f["properties"] for f in load(RAW15.parent / "2026-09-20/gis_objects/parcels.geojson.json")["features"]]
s = lambda v: str(v or "").strip()
L = ["# KB_V2_06 · Legends of the GIS layers", "",
     "Knowledge base document 06 of 06 · version kb-v2.1 · issued 2026-09-20 · generated from the archived layers by `scripts/build_miami_kb_legends.py` · cite as `KB_V2_06 §LG-xx (kb-v2.1)`", "",
     "Every entry below is an attribute value carried by a source layer inside the Miami study window, or a rule recorded in `config/gis_objects_v1.json`. Where a source does not define a symbol, this document says so; the reading agents must then treat the symbol as a label and write \"not covered by knowledge base\" if its meaning matters.", ""]
tr = Counter((s(p.get("Transect")), s(p.get("Transect_D"))) for p in zon)
L += ["## LG-01 Zoning transects (City of Miami, Miami 21 layer)", "",
      "The layer describes itself as the spatial representation of the transect zones of the Miami 21 form-based code, areas of varying density whose character is set by requirements for use, height, setback and building form. Transect codes and the descriptions the layer carries:", "",
      "| Transect | Description in the layer | Polygons in the window |", "|---|---|---|"]
L += [f"| {t} | {d} | {n} |" for (t, d), n in sorted(tr.items(), key=lambda kv: -kv[1])]
zones = sorted({s(p.get("M21_ZONE")) for p in zon})
L += ["", "## LG-02 Zone names, height figure, intensity letter, FLR letter", "",
      f"Zone names present in the window: {', '.join(zones)}.", "",
      "A zone name combines the transect, a height figure and letters, all of which the layer also carries as separate fields:", "",
      f"- `Bldg_Heigh` values present: {', '.join(sorted({s(p.get('Bldg_Heigh')) for p in zon} - {''}, key=lambda x: int(x)))}. The layer does not state the unit of this figure; treat it as the height class named in the zone and do not convert it.",
      f"- `Intensity` letters present: {', '.join(sorted({s(p.get('Intensity')) for p in zon} - {''}))}. The layer carries the letters without defining them, and their definition has not been verified against the code text for this study. Treat them as labels.",
      f"- `FLR` letters present: {', '.join(sorted({s(p.get('FLR')) for p in zon} - {''}))}. The official Miami 21 glossary defines Floor Lot Ratio as a multiplier on lot area that sets the maximum building area allowed above grade; what the letters A and B stand for is not defined in the layer.",
      "", "Zoning is permission, not activity (KB_V2_01 §DS-03): none of these figures says what is built or who travels."]
lud = Counter((s(p.get("LU")), s(p.get("DESCR"))) for p in lu)
L += ["", "## LG-03 Existing land-use classes (Miami-Dade County land-use layer)", "", "Class codes and the descriptions the layer carries, for classes present in the study window:", "", "| LU | Description in the layer | Polygons |", "|---|---|---|"]
L += [f"| {c} | {d} | {n} |" for (c, d), n in sorted(lud.items(), key=lambda kv: (-kv[1], kv[0][0]))]
L += ["", "## LG-04 Road classes (OpenStreetMap `highway` tag)", "",
      "Paraphrased from the OpenStreetMap wiki page Key:highway; consult the wiki for the exact definitions. Classes express the importance of a road in the network, not its width or traffic:", "",
      "- `motorway`: controlled-access divided highway; `motorway_link`: its ramps and slip roads.", "- `trunk`: the most important roads that are not motorways; `trunk_link`: their ramps.",
      "- `primary`, `secondary`, `tertiary`: roads of decreasing importance linking districts and neighbourhoods; `*_link`: their connecting ramps.", "- `residential`, `unclassified`, `living_street`: local access streets.",
      "- `pedestrian`: streets or plazas mainly for walking; `busway`: a road for buses only.", "- `bridge` and `tunnel` flags mark ways tagged as such in OpenStreetMap; `lanes_max` is the largest lanes tag among the grouped ways and is often missing.",
      "", f"Listed as objects: {', '.join(cfg['roads']['object_classes'])}. Reported only as summary lengths: {', '.join(cfg['roads']['summary_only_classes'])}. {cfg['roads']['grouping']}."]
L += ["", "## LG-05 Rail layers", "", cfg["rail"]["split_rule"] + ". " + cfg["rail"]["why"] + "."]
pref = Counter(s(p.get("DOR_DESC")).split(" : ")[0] for p in par if s(p.get("DOR_DESC")))
grp_of = {p_: g for g, ps in cfg["parcels"]["groups_by_dor_desc_prefix"].items() for p_ in ps}
L += ["", "## LG-06 Parcel land-use descriptions and groups (Miami-Dade County parcel layer)", "",
      "The parcel layer carries a four-digit land-use code and a description of the form `CLASS : SUBCLASS`. This study groups parcels by the class text as it appears in the layer. " + cfg["parcels"]["grouping_note"] + ".", "",
      "| Class text in the layer | Group in this study | Parcels in the window |", "|---|---|---|"]
L += [f"| {p_} | {grp_of.get(p_, 'other')} | {n} |" for p_, n in sorted(pref.items(), key=lambda kv: -kv[1])]
L += ["", f"Parcels without any attribute in the source: {sum(1 for p in par if not s(p.get('DOR_DESC')))}; they are counted and never read as parcels with a use. {cfg['parcels']['table_rule'].capitalize()}.",
      "", "Privacy: " + cfg["parcels"]["privacy"] + "."]
hp = cfg["heat_proxy"]
L += ["", "## LG-07 Heat proxy", "", f"Metric: {hp['metric']}. Cell size {hp['cell_size_ft']} ft. {hp['label']}. Residents: {hp['residents_source']}. Jobs: {hp['jobs_source']}. Apportionment: {hp['apportionment']}. "
      f"Hot: {hp['hot_definition']}. Known limitation: {hp['known_limitation']}.", "",
      "## LG-08 Role hints are not in the agents' input", "", cfg["role_hints"]["purpose"].capitalize() + ".", ""]
OUT.write_text("\n".join(L), encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)} transects={len(tr)} zones={len(zones)} land_use_classes={len(lud)} parcel_classes={len(pref)}")
