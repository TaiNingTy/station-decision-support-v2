// Coze Code node · V2 output gate  (workflow station_decision_v2, node "assemble-and-validate")
// ---------------------------------------------------------------------------------------------
// Merges the three agents' JSON into one miami-ai-output/1.0 object and refuses to emit it when a citation
// does not exist. New in V2: V1.1 gated the INPUT (infeasible site -> no generation); V2 also gates the OUTPUT
// (an answer that cites a fact id, rule result id or KB section that does not exist is rejected by code).
//
// Input  params.station_brief String (the same compact brief the input gate read)
//        params.site_json, params.review_json, params.config_json  String (raw outputs of LLM1 / LLM2 / LLM3)
//        params.spatial_evidence_json String, params.evidence_object_ids Array<String>, params.gis_status String  (optional; from gis-gate / gis-verify)
// Output output_status "VALID" | "INVALID", allow_output Boolean, problems Array<String>, soft_warnings Array<String>,
//        final_json String
// Paste the whole file into the Coze Code node (JavaScript). Runnable in Node for local evals.
// ---------------------------------------------------------------------------------------------
const SCEN = ["low", "medium", "high"];
const ROLES = ["origin_dominant", "destination_dominant", "mixed", "hub_connection_dependent", "insufficient_evidence"];
const LEVELS = ["high", "medium", "low"];

function parseLoose(s, name, problems) {
  if (s && typeof s === "object") return s;
  if (typeof s !== "string" || !s.trim()) { problems.push(`${name}: empty output`); return null; }
  let t = s.trim().replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
  const a = t.indexOf("{"), z = t.lastIndexOf("}");
  if (a < 0 || z <= a) { problems.push(`${name}: no JSON object found`); return null; }
  try { return JSON.parse(t.slice(a, z + 1)); } catch (e) { problems.push(`${name}: not valid JSON (${String(e.message).slice(0, 80)})`); return null; }
}

// numbers are compared by value, so "72.0", "72" and "15,975" / "15975" are the same number
function numbersIn(text) { return (String(text).match(/(?<![\w.])\d[\d,]*\.?\d*(?![\w])/g) || []).map((n) => String(parseFloat(n.replace(/,/g, "")))).filter((n) => n !== "NaN"); }
function collectNumbers(v, out) {
  if (v === null || v === undefined) return;
  if (Array.isArray(v)) return v.forEach((x) => collectNumbers(x, out));
  if (typeof v === "object") return Object.values(v).forEach((x) => collectNumbers(x, out));
  if (typeof v === "number") { [v, Math.round(v), +v.toFixed(1), +v.toFixed(2)].forEach((x) => out.add(String(x))); if (v < 1) { out.add(String(+(v * 100).toFixed(1))); out.add(String(Math.round(v * 100))); } }
  if (typeof v === "string") numbersIn(v).forEach((n) => out.add(n));
}

function assemble(params) {
  const problems = [], soft = [];
  let brief;
  try { brief = typeof params.station_brief === "string" ? JSON.parse(params.station_brief) : params.station_brief; } catch (e) { brief = null; }
  if (!brief || !Array.isArray(brief.facts)) return { output_status: "INVALID", allow_output: false, problems: ["station_brief unreadable in the output gate"], soft_warnings: [], final_json: "" };
  const pid = brief.station_id;
  const FACTS = new Set(brief.facts.map((f) => f.fact_id));
  const RULES = new Set([...(brief.rule_results.station || []), ...(brief.rule_results.network || [])].map((r) => r.rule_result_id));
  const KB = new Set(brief.kb_sections || []);
  const OBJ = new Set(Array.isArray(params.evidence_object_ids) ? params.evidence_object_ids : []);
  let evidence = null; try { evidence = params.spatial_evidence_json ? (typeof params.spatial_evidence_json === "string" ? JSON.parse(params.spatial_evidence_json) : params.spatial_evidence_json) : null; } catch (e) { evidence = null; }
  const briefNumbers = new Set(); collectNumbers(brief.facts.map((f) => f.value), briefNumbers);

  const site = parseLoose(params.site_json, "LLM1 site reading", problems) || {};
  const review = parseLoose(params.review_json, "LLM2 grounded review", problems) || {};
  const config = parseLoose(params.config_json, "LLM3 configuration brief", problems) || {};

  const idList = (lst, set, kind, where) => {
    if (lst == null) return [];
    if (!Array.isArray(lst)) { problems.push(`${where}: ${kind} must be a list`); return []; }
    lst.forEach((x) => { if (typeof x !== "string" || !set.has(x)) problems.push(`${where}: ${kind} does not exist: ${show(x)}`); });
    return lst;
  };
  const show = (x) => (typeof x === "string" ? x : JSON.stringify(x));
  const anyId = (lst, where) => { (Array.isArray(lst) ? lst : []).forEach((x) => { if (!(FACTS.has(x) || RULES.has(x) || KB.has(x))) problems.push(`${where}: id does not exist: ${show(x)}`); }); };
  const text = (s, where) => {
    if (typeof s !== "string" || !s.trim()) { problems.push(`${where}: statement text missing`); return; }
    numbersIn(s).filter((n) => n.replace(".", "").length >= 2 && !briefNumbers.has(n)).forEach((n) => soft.push(`${where}: number ${n} is not among the brief's values`));
  };
  const statements = (lst, where, needFact) => {
    if (!Array.isArray(lst) || !lst.length) { problems.push(`${where}: at least one entry required`); return; }
    lst.forEach((st, i) => {
      const w = `${where}[${i}]`; if (!st || typeof st !== "object") { problems.push(`${w}: not an object`); return; }
      text(st.statement, w);
      const f = idList(st.fact_ids, FACTS, "fact id", w), r = idList(st.rule_result_ids, RULES, "rule result id", w), k = idList(st.kb_refs, KB, "KB reference", w);
      idList(st.object_ids, OBJ, "spatial object id", w);   // optional: objects of the verified spatial evidence (auxiliary)
      if (needFact && !f.length) problems.push(`${w}: a site statement needs at least one fact id`);
      if (!needFact && !(f.length || r.length || k.length)) problems.push(`${w}: needs a fact id, a rule result id or a KB reference`);
    });
  };

  statements(site.site_reading, "site_reading", true);
  if (Array.isArray(site.site_reading) && (site.site_reading.length < 3 || site.site_reading.length > 8)) problems.push("site_reading must hold 3 to 8 statements");
  const rp = site.role_proposal || {};
  if (!ROLES.includes(rp.role)) problems.push(`role_proposal.role not allowed: ${show(rp.role)}`);
  if (!LEVELS.includes(rp.evidence_level)) problems.push("role_proposal.evidence_level must be high / medium / low");
  if (rp.requires_human_confirmation !== true) problems.push("role_proposal.requires_human_confirmation must be true");
  if (!idList(rp.basis_fact_ids, FACTS, "fact id", "role_proposal").length) problems.push("role_proposal needs basis fact ids");
  idList(rp.rule_result_ids, RULES, "rule result id", "role_proposal");
  text(rp.rationale, "role_proposal.rationale");

  statements(review.data_gaps_and_reliability, "data_gaps_and_reliability", false);
  (Array.isArray(review.rule_explanations) ? review.rule_explanations : []).forEach((x, i) => {
    if (!x || !RULES.has(x.rule_result_id)) problems.push(`rule_explanations[${i}]: rule result id does not exist: ${show(x && x.rule_result_id)}`);
    idList(x && x.kb_refs, KB, "KB reference", `rule_explanations[${i}]`);
  });
  if (!Array.isArray(review.not_covered_by_knowledge_base)) problems.push("not_covered_by_knowledge_base must be a list (may be empty)");

  const cr = config.configuration_reading || {};
  if (Object.keys(cr).sort().join() !== [...SCEN].sort().join()) problems.push("configuration_reading must have exactly low, medium, high");
  SCEN.forEach((s) => {
    const blk = cr[s] || {}; const w = `configuration_reading.${s}`;
    statements(blk.drivers, `${w}.drivers`, true);
    const rr = idList(blk.rule_result_ids, RULES, "rule result id", w); idList(blk.kb_refs, KB, "KB reference", w);
    if (!rr.includes(`${pid}|${s}|RC-03`)) problems.push(`${w} must cite ${pid}|${s}|RC-03`);
    if (!rr.includes(`${pid}|-|RC-07`)) problems.push(`${w} must cite ${pid}|-|RC-07`);
    if (blk.risks != null && !Array.isArray(blk.risks)) problems.push(`${w}.risks must be a list`);
  });
  const q = config.questions_for_owner;
  if (!Array.isArray(q) || !q.length) problems.push("questions_for_owner needs at least one entry");
  (Array.isArray(q) ? q : []).forEach((x, i) => { if (!x || !x.question || !x.why_it_matters) problems.push(`questions_for_owner[${i}] incomplete`); anyId(x && x.related_ids, `questions_for_owner[${i}]`); });

  const status = problems.length ? "INVALID" : "VALID";
  const final = {
    schema_version: "miami-ai-output/1.0", station_id: pid, brief_id: pid, kit_version: brief.kit_version, kb_version: brief.kb_version,
    rule_pack_version: brief.rule_pack_version, prompt_version: brief.prompt_version,
    site_reading: site.site_reading || [], data_gaps_and_reliability: review.data_gaps_and_reliability || [], role_proposal: site.role_proposal || {},
    configuration_reading: config.configuration_reading || {}, questions_for_owner: config.questions_for_owner || [],
    not_covered_by_knowledge_base: review.not_covered_by_knowledge_base || [], rule_explanations: review.rule_explanations || [],
    spatial_evidence: evidence || { status: "not_available", auxiliary_only: true, reason: params.gis_status ? `gis-gate: ${params.gis_status}` : "the GIS reading agents were not run" },
    workflow: { name: "station_decision_v2", design: "coze/v2/DESIGN.md", input_gate: "PASS", gis_gate: params.gis_status || "not_run", gis_verify: evidence ? evidence.status : "not_run", output_gate: status, output_gate_problems: problems.length, soft_warnings: soft.length },
    run_record: { platform: "coze", execution_mode: "coze_ui_manual", workflow_or_bot: "station_decision_v2", model: "", run_id: null, run_at_utc: "", operator: "", retrieval_hits: [],
      review: { status: "unreviewed", reviewer: "", notes: "" } },
  };
  return { output_status: status, allow_output: status === "VALID", problems, soft_warnings: soft, final_json: JSON.stringify(final, null, 2) };
}

async function main({ params }) {
  return assemble(params);
}

if (typeof module !== "undefined" && module.exports) module.exports = { assemble, main, parseLoose };
