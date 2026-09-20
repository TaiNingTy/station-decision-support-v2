// Coze Code node · V2 input gate  (workflow station_decision_v2, node "brief-gate")
// ---------------------------------------------------------------------------------------------
// Same contract as the V1.1 site gate: code decides, the LLM only explains.
//   PASS          the brief is complete and carries no critical rule result  -> interpretation may run
//   BLOCKED       at least one critical rule result                           -> no LLM node runs (0 tokens)
//   NEEDS_REVIEW  the brief is malformed or a required rule result is missing -> no LLM node runs
// A missing rule result is NOT a pass (V1.1 semantics: NOT_EVALUATED never silently passes).
//
// Input  params.station_brief  String  the compact brief  ai/miami/briefs/<station>.coze.json
// Output workflow_status, allow_interpretation, blocked_reasons, station_id, station_name, versions,
//        facts_table, rules_table, caveats, kb_query, allowed_fact_ids, allowed_rule_result_ids, kb_sections
// Paste the whole file into the Coze Code node (JavaScript). Runnable in Node for local evals.
// ---------------------------------------------------------------------------------------------
const SCEN = ["low", "medium", "high"];
const REQUIRED = {
  station: { per_scenario: ["RC-03", "RC-04", "RC-10"], once: ["RC-07", "RC-08", "RC-09", "RC-11", "RC-12", "RC-13"] },
  network: { per_scenario: ["RC-01", "RC-02", "RC-05"], once: ["RC-06"] },
};
const MIN_FACTS = 60;

const show = (v) => (v !== null && typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));

function evaluateBrief(text) {
  const out = {
    workflow_status: "NEEDS_REVIEW", allow_interpretation: false, blocked_reasons: [], station_id: "", station_name: "", versions: {},
    facts_table: "", rules_table: "", caveats: "", kb_query: "", allowed_fact_ids: [], allowed_rule_result_ids: [], kb_sections: [],
  };
  const review = (reason) => { out.blocked_reasons.push({ status: "NOT_EVALUATED", reason }); return out; };

  let b;
  try { b = typeof text === "string" ? JSON.parse(text) : text; } catch (e) { return review("station_brief is not valid JSON"); }
  if (!b || typeof b !== "object") return review("station_brief is empty");
  for (const k of ["station_id", "name", "kit_version", "kb_version", "rule_pack_version", "prompt_version", "facts", "rule_results", "kb_sections"]) {
    if (b[k] == null) return review(`brief field missing: ${k}`);
  }
  const pid = b.station_id;
  const facts = Array.isArray(b.facts) ? b.facts : [];
  const ids = facts.map((f) => f && f.fact_id);
  if (facts.length < MIN_FACTS) return review(`brief has ${facts.length} facts; at least ${MIN_FACTS} expected`);
  if (new Set(ids).size !== ids.length || ids.some((x) => typeof x !== "string" || !x.startsWith(pid + ".F"))) return review("fact ids are not unique or do not belong to this station");

  const st = (b.rule_results && b.rule_results.station) || [];
  const net = (b.rule_results && b.rule_results.network) || [];
  const all = [...st, ...net];
  const have = new Set(all.map((r) => r.rule_result_id));
  const missing = [];
  for (const rid of REQUIRED.station.per_scenario) for (const s of SCEN) if (!have.has(`${pid}|${s}|${rid}`)) missing.push(`${pid}|${s}|${rid}`);
  for (const rid of REQUIRED.station.once) if (!have.has(`${pid}|-|${rid}`)) missing.push(`${pid}|-|${rid}`);
  for (const rid of REQUIRED.network.per_scenario) for (const s of SCEN) if (!have.has(`NET|${s}|${rid}`)) missing.push(`NET|${s}|${rid}`);
  for (const rid of REQUIRED.network.once) if (!have.has(`NET|-|${rid}`)) missing.push(`NET|-|${rid}`);
  if (missing.length) { missing.forEach((m) => out.blocked_reasons.push({ status: "NOT_EVALUATED", rule_result_id: m, reason: "required rule result missing from the brief" })); return out; }

  out.station_id = pid; out.station_name = b.name;
  out.versions = { kit_version: b.kit_version, kb_version: b.kb_version, rule_pack_version: b.rule_pack_version, prompt_version: b.prompt_version };
  const critical = all.filter((r) => r.status === "critical");
  if (critical.length) {
    out.workflow_status = "BLOCKED";
    out.blocked_reasons = critical.map((r) => ({ status: "CRITICAL", rule_result_id: r.rule_result_id, rule_id: r.rule_id, reason: r.message }));
    return out;
  }

  out.workflow_status = "PASS"; out.allow_interpretation = true;
  out.allowed_fact_ids = ids; out.allowed_rule_result_ids = all.map((r) => r.rule_result_id); out.kb_sections = b.kb_sections;
  out.facts_table = ["fact_id | label | value | unit | provenance | reliability / MOE"].concat(facts.map((f) => {
    const rel = [f.reliability, f.moe_90 != null ? `±${f.moe_90}${f.moe_unit ? " " + f.moe_unit : ""}` : ""].filter(Boolean).join(" / ");
    return `${f.fact_id} | ${f.label} | ${show(f.value)} | ${f.unit || ""} | ${f.provenance_class || ""} | ${rel}`;
  })).join("\n");
  out.rules_table = ["rule_result_id | status | basis | message"].concat(all.map((r) => `${r.rule_result_id} | ${r.status} | ${r.basis} | ${r.message}`)).join("\n");
  const nonPass = all.filter((r) => r.status !== "pass");
  out.caveats = nonPass.map((r) => `${r.rule_result_id} (${r.status}): ${r.message}`).join("\n");
  out.kb_query = ["data semantics provenance period estimate jobs are not trips observed boardings reference", "PRT configuration berths module empty vehicles site fit assumed",
    "interpretation guidance role proposal citation duty questions for the owner", "open items ownership confirmation"].concat(nonPass.map((r) => r.rule_name || r.rule_id)).join("; ");
  return out;
}

async function main({ params }) {
  return evaluateBrief(params.station_brief);
}

if (typeof module !== "undefined" && module.exports) module.exports = { evaluateBrief, main, REQUIRED, SCEN };
