// Coze Code node · V2 GIS input gate  (workflow station_decision_v2, node "gis-gate")
// ---------------------------------------------------------------------------------------------
// Parses the two reading-agent inputs fetched by the HTTP nodes (g1_input.json, g2_input.json), checks that they
// belong together and respect the privacy and proxy rules, and turns the feature lists into compact tables for the
// prompts. Spatial evidence is AUXILIARY: when this gate does not pass, the workflow skips G1 / G2 and continues on the
// brief alone, recording why. It never blocks the station.
//
// Input  params.g1_input, params.g2_input  String
// Output gis_status "PASS" | "NEEDS_REVIEW", allow_reading, gis_problems, station_id, station_name, heat_image_url,
//        g1_roads_table, g1_rail_table, g1_zoning_table, g1_landuse_table, g1_parcels_table, g1_parcel_groups,
//        g1_facts_table, g2_cells_table, g2_blockgroups_table, g2_zoning_table, g2_facts_table, kb_query_gis
// ---------------------------------------------------------------------------------------------
const show = (v) => (v !== null && typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));
const table = (head, rows, cols) => [head.join(" | ")].concat(rows.map((r) => cols.map((c) => show(typeof c === "function" ? c(r) : r[c])).join(" | "))).join("\n");
const FORBIDDEN_KEYS = ["owner", "mailing", "addr", "legal"];

function evaluateGisInputs(g1Text, g2Text) {
  const out = { gis_status: "NEEDS_REVIEW", allow_reading: false, gis_problems: [], station_id: "", station_name: "", heat_image_url: "",
    g1_roads_table: "", g1_rail_table: "", g1_zoning_table: "", g1_landuse_table: "", g1_parcels_table: "", g1_parcel_groups: "", g1_facts_table: "",
    g2_cells_table: "", g2_blockgroups_table: "", g2_zoning_table: "", g2_facts_table: "", kb_query_gis: "" };
  const fail = (m) => { out.gis_problems.push(m); return out; };
  let g1, g2;
  try { g1 = typeof g1Text === "string" ? JSON.parse(g1Text) : g1Text; } catch (e) { return fail("g1_input is not valid JSON"); }
  try { g2 = typeof g2Text === "string" ? JSON.parse(g2Text) : g2Text; } catch (e) { return fail("g2_input is not valid JSON"); }
  if (!g1 || !g2 || !g1.objects || !g2.objects) return fail("g1_input or g2_input has no objects");
  if (g1.station_id !== g2.station_id) return fail(`g1 and g2 inputs belong to different stations: ${g1.station_id} / ${g2.station_id}`);
  if (g1.gis_objects_package !== g2.gis_objects_package) return fail("g1 and g2 inputs come from different gis_objects packages");
  const o1 = g1.objects, o2 = g2.objects;
  for (const k of ["roads", "zoning", "land_use", "parcels", "guideway"]) if (!Array.isArray(o1[k]) || !o1[k].length) out.gis_problems.push(`g1 objects.${k} is empty`);
  for (const k of ["heat_cells", "block_groups"]) if (!Array.isArray(o2[k]) || !o2[k].length) out.gis_problems.push(`g2 objects.${k} is empty`);
  const hp = g2.heat_proxy || {};
  if (hp.is_measured_ridership_heat !== false || hp.is_persons_per_hour !== false) out.gis_problems.push("heat layer is not labelled as a proxy (is_measured_ridership_heat / is_persons_per_hour must be false)");
  const leaked = new Set();
  (o1.parcels || []).forEach((p) => Object.keys(p).forEach((k) => { if (FORBIDDEN_KEYS.some((w) => k.toLowerCase().includes(w))) leaked.add(k); }));
  if (leaked.size) out.gis_problems.push(`parcel rows carry owner / address fields: ${[...leaked].join(", ")}`);
  const ids = [].concat(...["roads", "rail", "guideway", "zoning", "land_use", "parcels"].map((k) => (o1[k] || []).map((r) => r.object_id)), (o2.heat_cells || []).map((r) => r.object_id), (o2.block_groups || []).map((r) => r.object_id));
  if (new Set(ids).size !== ids.length || ids.some((x) => typeof x !== "string" || !x.startsWith(g1.station_id + "."))) out.gis_problems.push("object ids are not unique or do not belong to this station");
  if (out.gis_problems.length) return out;

  out.gis_status = "PASS"; out.allow_reading = true; out.station_id = g1.station_id; out.station_name = g1.name; out.heat_image_url = g2.heat_image_url || "";
  out.g1_roads_table = table(["object_id", "name", "highway_class", "length_inside_disc_ft", "bridge", "lanes_max", "nearest_ft", "nearest_band", "nearest_sector"], o1.roads,
    ["object_id", "name", "highway_class", "length_inside_disc_ft", "bridge", "lanes_max", "nearest_ft", "nearest_band", "nearest_sector"]);
  out.g1_rail_table = table(["object_id", "kind", "label", "length_inside_disc_ft", "nearest_ft", "nearest_sector"], [...(o1.rail || []), ...(o1.guideway || [])], ["object_id", "kind", "label", "length_inside_disc_ft", "nearest_ft", "nearest_sector"]);
  out.g1_zoning_table = table(["object_id", "M21_ZONE", "Transect_D", "Bldg_Heigh", "Intensity", "FLR", "acres_inside_disc", "share_of_disc", "contains_reference_point", "nearest_ft", "sector"], o1.zoning,
    ["object_id", "M21_ZONE", "Transect_D", "Bldg_Heigh", "Intensity", "FLR", "acres_inside_disc", "share_of_disc", "contains_reference_point", "nearest_ft", "sector_of_clipped_part"]);
  out.g1_landuse_table = table(["object_id", "LU", "DESCR", "acres_inside_disc", "share_of_disc", "polygons"], o1.land_use, ["object_id", "LU", (r) => String(r.DESCR || "").slice(0, 110), "acres_inside_disc", "share_of_disc", "polygons"]);
  out.g1_parcels_table = table(["object_id", "folio", "land_use_description", "group", "lot_size_sqft", "year_built", "nearest_ft", "band", "sector", "zoning_at_centroid"], o1.parcels,
    ["object_id", "folio", "dor_desc", "group", "lot_size_sqft", "year_built", "nearest_ft", "band", "sector", "zoning_at_centroid"]);
  out.g1_parcel_groups = table(["group", "parcels", "acres"], o1.parcel_groups_all_parcels || [], ["group", "parcels", "acres"]) + `\n(rows cut by the table cap: ${show(g1.rows_cut)}; rule: ${g1.parcel_table_rule})`;
  const facts = (fs) => table(["fact_id", "label", "value", "unit"], fs || [], ["fact_id", "label", "value", "unit"]);
  out.g1_facts_table = facts(g1.summary_facts); out.g2_facts_table = facts(g2.summary_facts);
  out.g2_cells_table = table(["object_id", "activity_density_per_acre", "network_quintile", "is_hot", "residents_2020", "jobs_2023", "jobs_share", "zoning_transect", "zoning_share_of_cell", "land_use", "highest_road_class", "rail_in_cell", "center_distance_ft", "band", "sector"], o2.heat_cells,
    ["object_id", "activity_density_per_acre", "network_quintile", "is_hot", "residents_2020", "jobs_2023", "jobs_share_of_activity", "dominant_zoning_transect", "dominant_zoning_share_of_cell", (r) => (r.dominant_land_use ? `${r.dominant_land_use.code} ${String(r.dominant_land_use.descr).slice(0, 60)}` : ""), "highest_road_class", "rail_in_cell", "center_distance_ft", "center_band", "center_sector"]);
  out.g2_blockgroups_table = table(["object_id", "share_of_block_group_land_inside_disc", "population_estimate", "population_moe_90", "households_estimate", "workers_estimate", "zero_vehicle_households_estimate", "median_household_income_published", "period"], o2.block_groups,
    ["object_id", "share_of_block_group_land_inside_disc", "population_estimate", "population_moe_90", "households_estimate", "workers_estimate", "zero_vehicle_households_estimate", "median_household_income_published", "period"]);
  out.g2_zoning_table = table(["object_id", "M21_ZONE", "Transect_D", "share_of_disc", "sector"], o2.zoning || [], ["object_id", "M21_ZONE", "Transect_D", "share_of_disc", "sector_of_clipped_part"]);
  out.kb_query_gis = "how to read GIS features roles obstacle candidate site facility to convert; zoning transects legend; land-use classes; parcel land-use groups; road classes; rail layers split; heat proxy read together with zoning auxiliary evidence; screening non-passenger activity";
  return out;
}

async function main({ params }) {
  return evaluateGisInputs(params.g1_input, params.g2_input);
}

if (typeof module !== "undefined" && module.exports) module.exports = { evaluateGisInputs, main };
