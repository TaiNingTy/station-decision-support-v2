#!/usr/bin/env node
// Runnable evals for the two V2 code nodes (same spirit as V1.1's `node evals/run.js`).
//   node coze/v2/evals/run.js                  run the cases
//   node coze/v2/evals/run.js --write-fixtures also write the fixture briefs used for the Coze trial runs
// The cases use a REAL compact brief (ai/miami/briefs/MIA-MM-12.coze.json) and mutate it in memory; the parts of a
// well-formed answer come from the hand-written format example (not a model output).
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(__dirname, "../../..");
const { evaluateBrief } = require("../nodes/brief_gate.js");
const { assemble } = require("../nodes/assemble_and_validate.js");

const briefText = fs.readFileSync(path.join(ROOT, "ai/miami/briefs/MIA-MM-12.coze.json"), "utf8");
const brief = () => JSON.parse(briefText);
const example = JSON.parse(fs.readFileSync(path.join(ROOT, "ai/miami/examples/EXAMPLE_format_only_not_a_model_output.json"), "utf8"));
const parts = () => ({
  site_json: JSON.stringify({ site_reading: example.site_reading, role_proposal: example.role_proposal }),
  review_json: JSON.stringify({ data_gaps_and_reliability: example.data_gaps_and_reliability, rule_explanations: [{ rule_result_id: "MIA-MM-12|-|RC-07", explanation: "site fit is assumed", kb_refs: ["KB_V2_04 §OI-01"] }], not_covered_by_knowledge_base: example.not_covered_by_knowledge_base }),
  config_json: JSON.stringify({ configuration_reading: example.configuration_reading, questions_for_owner: example.questions_for_owner }),
});

// fixtures -----------------------------------------------------------------------------------------------------------
const injectedCritical = (() => { const b = brief(); b._notice = "TEST FIXTURE: NET|high|RC-05 forced to critical (ratio 1.05) to prove the gate blocks generation. Not a real result.";
  const r = b.rule_results.network.find((x) => x.rule_result_id === "NET|high|RC-05"); r.status = "critical"; r.message = "TEST FIXTURE: network vehicle trips exceed one lane's throughput at the minimum headway; infeasible as computed"; return b; })();
const missingRule = (() => { const b = brief(); b._notice = "TEST FIXTURE: RC-07 removed to prove that a missing rule result is not a pass."; b.rule_results.station = b.rule_results.station.filter((x) => x.rule_id !== "RC-07"); return b; })();

const cases = [
  ["input gate: real brief passes", () => { const o = evaluateBrief(briefText); return o.workflow_status === "PASS" && o.allow_interpretation === true && o.allowed_fact_ids.length === 83 && o.facts_table.split("\n").length === 84 && o.caveats.includes("RC-07"); }],
  ["input gate: injected critical rule result blocks", () => { const o = evaluateBrief(JSON.stringify(injectedCritical)); return o.workflow_status === "BLOCKED" && o.allow_interpretation === false && o.blocked_reasons[0].rule_result_id === "NET|high|RC-05" && o.facts_table === ""; }],
  ["input gate: missing rule result needs review (never a pass)", () => { const o = evaluateBrief(JSON.stringify(missingRule)); return o.workflow_status === "NEEDS_REVIEW" && o.allow_interpretation === false && o.blocked_reasons.some((r) => r.rule_result_id === "MIA-MM-12|-|RC-07"); }],
  ["input gate: malformed JSON needs review", () => { const o = evaluateBrief("{ not json"); return o.workflow_status === "NEEDS_REVIEW" && o.allow_interpretation === false; }],
  ["input gate: empty input needs review", () => { const o = evaluateBrief(""); return o.workflow_status === "NEEDS_REVIEW"; }],
  ["input gate: too few facts needs review", () => { const b = brief(); b.facts = b.facts.slice(0, 10); return evaluateBrief(JSON.stringify(b)).workflow_status === "NEEDS_REVIEW"; }],
  ["output gate: well-formed parts assemble to VALID", () => { const o = assemble({ station_brief: briefText, ...parts() }); const f = JSON.parse(o.final_json); return o.output_status === "VALID" && o.allow_output === true && f.schema_version === "miami-ai-output/1.0" && f.kb_version === "kb-v2.0" && f.workflow.output_gate === "VALID"; }],
  ["output gate: an invented fact id is rejected and named", () => { const p = parts(); const s = JSON.parse(p.site_json); s.site_reading[0].fact_ids.push("MIA-MM-12.F999"); p.site_json = JSON.stringify(s); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "INVALID" && o.problems.some((x) => x.includes("MIA-MM-12.F999")); }],
  ["output gate: an invented rule result id is rejected", () => { const p = parts(); const c = JSON.parse(p.config_json); c.configuration_reading.low.rule_result_ids.push("MIA-MM-12|low|RC-99"); p.config_json = JSON.stringify(c); return assemble({ station_brief: briefText, ...p }).output_status === "INVALID"; }],
  ["output gate: an external standard cited as a KB reference is rejected", () => { const p = parts(); const r = JSON.parse(p.review_json); r.data_gaps_and_reliability[0].kb_refs = ["GB/T 50157"]; p.review_json = JSON.stringify(r); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "INVALID" && o.problems.some((x) => x.includes("GB/T")); }],
  ["output gate: role without human confirmation is rejected", () => { const p = parts(); const s = JSON.parse(p.site_json); s.role_proposal.requires_human_confirmation = false; p.site_json = JSON.stringify(s); return assemble({ station_brief: briefText, ...p }).output_status === "INVALID"; }],
  ["output gate: a scenario that omits the site-fit caveat RC-07 is rejected", () => { const p = parts(); const c = JSON.parse(p.config_json); c.configuration_reading.high.rule_result_ids = c.configuration_reading.high.rule_result_ids.filter((x) => !x.endsWith("RC-07")); p.config_json = JSON.stringify(c); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "INVALID" && o.problems.some((x) => x.includes("RC-07")); }],
  ["output gate: markdown code fences around the JSON are tolerated", () => { const p = parts(); p.site_json = "```json\n" + p.site_json + "\n```"; return assemble({ station_brief: briefText, ...p }).output_status === "VALID"; }],
  ["output gate: an unparseable agent output is rejected", () => { const p = parts(); p.config_json = "Sorry, I cannot"; return assemble({ station_brief: briefText, ...p }).output_status === "INVALID"; }],
  ["output gate: a number that is not in the brief raises a soft warning, not a rejection", () => { const p = parts(); const s = JSON.parse(p.site_json); s.site_reading[0].statement += " About 4321 people pass by."; p.site_json = JSON.stringify(s); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "VALID" && o.soft_warnings.some((x) => x.includes("4321")); }],
];

let ok = 0;
for (const [name, fn] of cases) { let pass = false; try { pass = fn() === true; } catch (e) { pass = false; console.log("   error:", e.message); } console.log(`${pass ? "PASS" : "FAIL"}  ${name}`); ok += pass ? 1 : 0; }
console.log(`${ok}/${cases.length} cases passed`);
if (process.argv.includes("--write-fixtures")) {
  const dir = path.join(__dirname, "fixtures"); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "MIA-MM-12.injected_critical.coze.json"), JSON.stringify(injectedCritical) + "\n");
  fs.writeFileSync(path.join(dir, "MIA-MM-12.missing_rule.coze.json"), JSON.stringify(missingRule) + "\n");
  const p = parts(); const s = JSON.parse(p.site_json); s.site_reading[0].fact_ids.push("MIA-MM-12.F999");
  fs.writeFileSync(path.join(dir, "tampered_site_json.invented_fact_id.json"), JSON.stringify(s, null, 2) + "\n");
  fs.writeFileSync(path.join(dir, "wellformed_parts.json"), JSON.stringify(parts(), null, 2) + "\n");
  console.log("fixtures written to coze/v2/evals/fixtures/");
}
process.exit(ok === cases.length ? 0 : 1);
