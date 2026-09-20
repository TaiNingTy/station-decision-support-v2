// Coze Code node · V2 verification of the GIS readings  (workflow station_decision_v2, node "gis-verify")
// ---------------------------------------------------------------------------------------------
// The reading agents (G1, G2) interpret; this node checks what code can check, and passes the readings on only as
// AUXILIARY evidence. Any hard problem rejects the spatial evidence as a whole: the workflow then continues on the
// brief alone and the final output records the rejection. Nothing is silently dropped or repaired.
//
// Hard checks  every object id and fact id exists in the inputs; roles and levels are in the enums; every motorway /
//              trunk road group, every rail object and the guideway have been read; the existing guideway is never
//              read as an obstacle; candidate sites are parcels and carry caveats; G2 declares auxiliary_only = true;
//              screening concerns are in the enum; a picture-only observation carries no number.
// Soft checks  numbers that are not in the inputs; zoning polygons / land-use classes of 2 % or more left unread;
//              a statement that cites a heat cell and a block group together (two different populations).
//
// Input  params.g1_input, params.g2_input, params.g1_json, params.g2_json   String
// Output evidence_status "VALID" | "INVALID", allow_evidence, evidence_problems, evidence_soft_warnings,
//        spatial_evidence_json, evidence_digest, evidence_object_ids
// ---------------------------------------------------------------------------------------------
const ROLES = ["origin", "destination", "facility_to_convert", "obstacle", "candidate_site", "context", "not_relevant"];
const LEVELS = ["high", "medium", "low"];
const CONCERNS = ["possible_non_passenger_or_through_activity", "even_spread_artefact", "none"];
const BIG_ROADS = ["motorway", "motorway_link", "trunk", "trunk_link"];

function parseLoose(s, name, problems) {
  if (s && typeof s === "object") return s;
  if (typeof s !== "string" || !s.trim()) { problems.push(`${name}: empty output`); return null; }
  const t = s.trim().replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim(); const a = t.indexOf("{"), z = t.lastIndexOf("}");
  if (a < 0 || z <= a) { problems.push(`${name}: no JSON object found`); return null; }
  try { return JSON.parse(t.slice(a, z + 1)); } catch (e) { problems.push(`${name}: not valid JSON`); return null; }
}
function numbersIn(text) { return (String(text).match(/(?<![\w.])\d[\d,]*\.?\d*(?![\w])/g) || []).map((n) => String(parseFloat(n.replace(/,/g, "")))).filter((n) => n !== "NaN"); }
function collectNumbers(v, out) {
  if (v === null || v === undefined) return;
  if (Array.isArray(v)) return v.forEach((x) => collectNumbers(x, out));
  if (typeof v === "object") return Object.values(v).forEach((x) => collectNumbers(x, out));
  if (typeof v === "number") { [v, Math.round(v), +v.toFixed(1), +v.toFixed(2)].forEach((x) => out.add(String(x))); if (v < 1) { out.add(String(+(v * 100).toFixed(1))); out.add(String(Math.round(v * 100))); } }
  if (typeof v === "string") numbersIn(v).forEach((n) => out.add(n));
}

function verify(params) {
  const problems = [], soft = [];
  let g1, g2;
  try { g1 = typeof params.g1_input === "string" ? JSON.parse(params.g1_input) : params.g1_input; g2 = typeof params.g2_input === "string" ? JSON.parse(params.g2_input) : params.g2_input; } catch (e) { g1 = g2 = null; }
  if (!g1 || !g2) return { evidence_status: "INVALID", allow_evidence: false, evidence_problems: ["reading-agent inputs unreadable in gis-verify"], evidence_soft_warnings: [], spatial_evidence_json: "", evidence_digest: "", evidence_object_ids: [] };
  const o1 = g1.objects, o2 = g2.objects, pid = g1.station_id;
  const byId = {}; ["roads", "rail", "guideway", "zoning", "land_use", "parcels"].forEach((k) => (o1[k] || []).forEach((r) => { byId[r.object_id] = { kind: k, row: r }; }));
  ["heat_cells", "block_groups"].forEach((k) => (o2[k] || []).forEach((r) => { byId[r.object_id] = { kind: k, row: r }; }));
  const FACTS = new Set([...(g1.summary_facts || []), ...(g2.summary_facts || [])].map((f) => f.fact_id));
  const numbers = new Set(); collectNumbers([o1, o2, g1.summary_facts, g2.summary_facts], numbers);
  const A = parseLoose(params.g1_json, "G1 GIS reader", problems) || {}, B = parseLoose(params.g2_json, "G2 heat and residents reader", problems) || {};
  const show = (x) => (typeof x === "string" ? x : JSON.stringify(x));
  const objs = (lst, where) => { if (lst == null) return []; if (!Array.isArray(lst)) { problems.push(`${where}: object_ids must be a list`); return []; } lst.forEach((x) => { if (!byId[x]) problems.push(`${where}: object id does not exist: ${show(x)}`); }); return lst; };
  const facts = (lst, where) => { (Array.isArray(lst) ? lst : []).forEach((x) => { if (!FACTS.has(x)) problems.push(`${where}: fact id does not exist: ${show(x)}`); }); return Array.isArray(lst) ? lst : []; };
  const text = (s, where) => { if (typeof s !== "string" || !s.trim()) { problems.push(`${where}: text missing`); return; } numbersIn(s).filter((n) => n.replace(".", "").length >= 2 && !numbers.has(n)).forEach((n) => soft.push(`${where}: number ${n} is not in the inputs`)); };

  // ---- G1
  const read = new Set();
  (Array.isArray(A.object_readings) ? A.object_readings : (problems.push("G1 object_readings must be a list"), [])).forEach((r, i) => {
    const w = `G1.object_readings[${i}]`;
    if (!r || !byId[r.object_id]) { problems.push(`${w}: object id does not exist: ${show(r && r.object_id)}`); return; }
    read.add(r.object_id);
    if (!ROLES.includes(r.role)) problems.push(`${w}: role not allowed: ${show(r.role)}`);
    if (!LEVELS.includes(r.evidence_level)) problems.push(`${w}: evidence_level must be high / medium / low`);
    if (byId[r.object_id].kind === "guideway" && r.role === "obstacle") problems.push(`${w}: the existing Metromover guideway is the facility to convert and must not be read as an obstacle`);
    if (r.role === "candidate_site" && byId[r.object_id].kind !== "parcels") problems.push(`${w}: only a parcel can be a candidate site`);
    text(r.reading, w);
  });
  const mustRead = [...(o1.roads || []).filter((r) => BIG_ROADS.includes(r.highway_class)), ...(o1.rail || []), ...(o1.guideway || [])].map((r) => r.object_id);
  mustRead.filter((x) => !read.has(x)).forEach((x) => problems.push(`G1 did not read a required object (motorway / trunk road, rail or guideway): ${x}`));
  [...(o1.zoning || []), ...(o1.land_use || [])].filter((r) => r.share_of_disc >= 0.02 && !read.has(r.object_id)).forEach((r) => soft.push(`G1 left unread an object covering ${Math.round(r.share_of_disc * 100)} % of the disc: ${r.object_id}`));
  (Array.isArray(A.patterns) ? A.patterns : []).forEach((p, i) => { text(p && p.statement, `G1.patterns[${i}]`); const a = objs(p && p.object_ids, `G1.patterns[${i}]`), b = facts(p && p.fact_ids, `G1.patterns[${i}]`); if (!a.length && !b.length) problems.push(`G1.patterns[${i}]: needs an object id or a fact id`); });
  (Array.isArray(A.candidate_sites) ? A.candidate_sites : []).forEach((c, i) => {
    const w = `G1.candidate_sites[${i}]`;
    if (!c || !byId[c.object_id] || byId[c.object_id].kind !== "parcels") problems.push(`${w}: must name an existing parcel object`);
    if (!c || !Array.isArray(c.caveats) || !c.caveats.length) problems.push(`${w}: a candidate site needs its caveats (space, ownership, access, approvals unknown)`);
    text(c && c.why, w);
  });
  (Array.isArray(A.data_anomalies) ? A.data_anomalies : []).forEach((x, i) => { text(x && x.statement, `G1.data_anomalies[${i}]`); objs(x && x.object_ids, `G1.data_anomalies[${i}]`); });

  // ---- G2
  if (B.auxiliary_only !== true) problems.push("G2.auxiliary_only must be true: heat and zoning are auxiliary evidence");
  const g2block = (lst, where, needLevel) => (Array.isArray(lst) ? lst : (problems.push(`${where} must be a list`), [])).forEach((x, i) => {
    const w = `${where}[${i}]`; text(x && x.statement, w); const a = objs(x && x.object_ids, w), b = facts(x && x.fact_ids, w);
    if (!a.length && !b.length) problems.push(`${w}: needs an object id or a fact id`);
    if (needLevel && !LEVELS.includes(x && x.evidence_level)) problems.push(`${w}: evidence_level must be high / medium / low`);
    const kinds = new Set(a.filter((id) => byId[id]).map((id) => byId[id].kind));
    if (kinds.has("heat_cells") && kinds.has("block_groups") && numbersIn(x.statement || "").length) soft.push(`${w}: cites a heat cell and a block group with a number; the two populations come from different sources and years`);
  });
  g2block(B.heat_reading, "G2.heat_reading", false); g2block(B.heat_zoning_joint_reading, "G2.heat_zoning_joint_reading", true); g2block(B.residents_reading, "G2.residents_reading", false);
  (Array.isArray(B.service_relevance_screening) ? B.service_relevance_screening : (problems.push("G2.service_relevance_screening must be a list"), [])).forEach((x, i) => {
    const w = `G2.service_relevance_screening[${i}]`; text(x && x.statement, w); objs(x && x.object_ids, w);
    if (!CONCERNS.includes(x && x.concern)) problems.push(`${w}: concern not allowed: ${show(x && x.concern)}`);
  });
  (Array.isArray(B.visual_observations_unverified) ? B.visual_observations_unverified : []).forEach((s, i) => { if (/\d/.test(String(s))) problems.push(`G2.visual_observations_unverified[${i}]: a picture-only observation must not carry a number`); });

  const status = problems.length ? "INVALID" : "VALID";
  const evidence = { status: status === "VALID" ? "verified_ids_only" : "rejected", auxiliary_only: true, station_id: pid, gis_objects_package: g1.gis_objects_package, gis_config_version: g1.gis_config_version,
    note: "spatial evidence supports or questions the site reading; it decides neither demand, nor a role, nor a configuration. Verification covers ids, enums and required coverage, not the correctness of an interpretation.",
    heat_proxy_label: (g2.heat_proxy || {}).label, g1: status === "VALID" ? A : null, g2: status === "VALID" ? B : null, problems, soft_warnings: soft };
  let digest = "";
  if (status === "VALID") {
    const L = ["SPATIAL EVIDENCE (auxiliary; read by agents G1 and G2; ids verified by code; roles are hypotheses for human confirmation)"];
    (A.object_readings || []).filter((r) => ["obstacle", "facility_to_convert", "candidate_site"].includes(r.role)).slice(0, 14).forEach((r) => L.push(`- ${r.object_id} · ${r.role} (${r.evidence_level}): ${r.reading}`));
    (A.patterns || []).slice(0, 6).forEach((p) => L.push(`- pattern [${(p.object_ids || []).concat(p.fact_ids || []).join(", ")}]: ${p.statement}`));
    (B.heat_zoning_joint_reading || []).slice(0, 5).forEach((x) => L.push(`- heat with zoning (${x.evidence_level}) [${(x.object_ids || []).concat(x.fact_ids || []).join(", ")}]: ${x.statement}`));
    (B.service_relevance_screening || []).filter((x) => x.concern !== "none").slice(0, 5).forEach((x) => L.push(`- screening · ${x.concern} [${(x.object_ids || []).join(", ")}]: ${x.statement}`));
    (A.data_anomalies || []).slice(0, 4).forEach((x) => L.push(`- data anomaly [${(x.object_ids || []).join(", ")}]: ${x.statement}`));
    digest = L.join("\n");
  } else digest = `SPATIAL EVIDENCE NOT AVAILABLE: the GIS readings were rejected by verification (${problems.length} problems). Continue on the brief alone and say so.`;
  return { evidence_status: status, allow_evidence: status === "VALID", evidence_problems: problems, evidence_soft_warnings: soft, spatial_evidence_json: JSON.stringify(evidence, null, 2), evidence_digest: digest,
    evidence_object_ids: status === "VALID" ? Object.keys(byId) : [] };
}

async function main({ params }) {
  return verify(params);
}

if (typeof module !== "undefined" && module.exports) module.exports = { verify, main, ROLES, CONCERNS };
