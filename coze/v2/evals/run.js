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

// ---- GIS reading: real inputs of the same station + the hand-written format example (not a model output)
const { evaluateGisInputs } = require("../nodes/gis_gate.js");
const { verify } = require("../nodes/gis_verify.js");
const g1Text = fs.readFileSync(path.join(ROOT, "ai/miami/gis/MIA-MM-12/g1_input.json"), "utf8");
const g2Text = fs.readFileSync(path.join(ROOT, "ai/miami/gis/MIA-MM-12/g2_input.json"), "utf8");
const gisExample = JSON.parse(fs.readFileSync(path.join(ROOT, "ai/miami/examples/EXAMPLE_gis_readings_format_only_not_a_model_output.json"), "utf8"));
const readings = () => JSON.parse(JSON.stringify({ g1: gisExample.g1_json, g2: gisExample.g2_json }));
const runVerify = (r) => verify({ g1_input: g1Text, g2_input: g2Text, g1_json: JSON.stringify(r.g1), g2_json: JSON.stringify(r.g2) });

const cases = [
  ["input gate: real brief passes", () => { const o = evaluateBrief(briefText); return o.workflow_status === "PASS" && o.allow_interpretation === true && o.allowed_fact_ids.length === 83 && o.facts_table.split("\n").length === 84 && o.caveats.includes("RC-07"); }],
  ["input gate: injected critical rule result blocks", () => { const o = evaluateBrief(JSON.stringify(injectedCritical)); return o.workflow_status === "BLOCKED" && o.allow_interpretation === false && o.blocked_reasons[0].rule_result_id === "NET|high|RC-05" && o.facts_table === ""; }],
  ["input gate: missing rule result needs review (never a pass)", () => { const o = evaluateBrief(JSON.stringify(missingRule)); return o.workflow_status === "NEEDS_REVIEW" && o.allow_interpretation === false && o.blocked_reasons.some((r) => r.rule_result_id === "MIA-MM-12|-|RC-07"); }],
  ["input gate: malformed JSON needs review", () => { const o = evaluateBrief("{ not json"); return o.workflow_status === "NEEDS_REVIEW" && o.allow_interpretation === false; }],
  ["input gate: empty input needs review", () => { const o = evaluateBrief(""); return o.workflow_status === "NEEDS_REVIEW"; }],
  ["input gate: too few facts needs review", () => { const b = brief(); b.facts = b.facts.slice(0, 10); return evaluateBrief(JSON.stringify(b)).workflow_status === "NEEDS_REVIEW"; }],
  ["output gate: well-formed parts assemble to VALID", () => { const o = assemble({ station_brief: briefText, ...parts() }); const f = JSON.parse(o.final_json); return o.output_status === "VALID" && o.allow_output === true && f.schema_version === "miami-ai-output/1.0" && f.kb_version === "kb-v2.1" && f.workflow.output_gate === "VALID"; }],
  ["output gate: an invented fact id is rejected and named", () => { const p = parts(); const s = JSON.parse(p.site_json); s.site_reading[0].fact_ids.push("MIA-MM-12.F999"); p.site_json = JSON.stringify(s); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "INVALID" && o.problems.some((x) => x.includes("MIA-MM-12.F999")); }],
  ["output gate: an invented rule result id is rejected", () => { const p = parts(); const c = JSON.parse(p.config_json); c.configuration_reading.low.rule_result_ids.push("MIA-MM-12|low|RC-99"); p.config_json = JSON.stringify(c); return assemble({ station_brief: briefText, ...p }).output_status === "INVALID"; }],
  ["output gate: an external standard cited as a KB reference is rejected", () => { const p = parts(); const r = JSON.parse(p.review_json); r.data_gaps_and_reliability[0].kb_refs = ["GB/T 50157"]; p.review_json = JSON.stringify(r); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "INVALID" && o.problems.some((x) => x.includes("GB/T")); }],
  ["output gate: role without human confirmation is rejected", () => { const p = parts(); const s = JSON.parse(p.site_json); s.role_proposal.requires_human_confirmation = false; p.site_json = JSON.stringify(s); return assemble({ station_brief: briefText, ...p }).output_status === "INVALID"; }],
  ["output gate: a scenario that omits the site-fit caveat RC-07 is rejected", () => { const p = parts(); const c = JSON.parse(p.config_json); c.configuration_reading.high.rule_result_ids = c.configuration_reading.high.rule_result_ids.filter((x) => !x.endsWith("RC-07")); p.config_json = JSON.stringify(c); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "INVALID" && o.problems.some((x) => x.includes("RC-07")); }],
  ["output gate: markdown code fences around the JSON are tolerated", () => { const p = parts(); p.site_json = "```json\n" + p.site_json + "\n```"; return assemble({ station_brief: briefText, ...p }).output_status === "VALID"; }],
  ["output gate: an unparseable agent output is rejected", () => { const p = parts(); p.config_json = "Sorry, I cannot"; return assemble({ station_brief: briefText, ...p }).output_status === "INVALID"; }],
  ["output gate: a number that is not in the brief raises a soft warning, not a rejection", () => { const p = parts(); const s = JSON.parse(p.site_json); s.site_reading[0].statement += " About 4321 people pass by."; p.site_json = JSON.stringify(s); const o = assemble({ station_brief: briefText, ...p }); return o.output_status === "VALID" && o.soft_warnings.some((x) => x.includes("4321")); }],
  ["gis gate: real reading-agent inputs pass and become tables", () => { const o = evaluateGisInputs(g1Text, g2Text); return o.gis_status === "PASS" && o.allow_reading === true && o.g1_parcels_table.split("\n").length > 100 && o.g2_cells_table.includes("HC16_09") && o.heat_image_url.endsWith("/MIA-MM-12/heat.png"); }],
  ["gis gate: inputs of two different stations need review", () => { const g2 = JSON.parse(g2Text); g2.station_id = "MIA-MM-09"; return evaluateGisInputs(g1Text, JSON.stringify(g2)).gis_status === "NEEDS_REVIEW"; }],
  ["gis gate: a parcel row carrying an owner field needs review (privacy guard)", () => { const g1 = JSON.parse(g1Text); g1.objects.parcels[0].TRUE_OWNER1 = "SOMEONE"; const o = evaluateGisInputs(JSON.stringify(g1), g2Text); return o.gis_status === "NEEDS_REVIEW" && o.gis_problems.some((x) => x.includes("owner")); }],
  ["gis gate: a heat layer not labelled as a proxy needs review", () => { const g2 = JSON.parse(g2Text); g2.heat_proxy.is_measured_ridership_heat = true; return evaluateGisInputs(g1Text, JSON.stringify(g2)).gis_status === "NEEDS_REVIEW"; }],
  ["gis verify: well-formed readings are accepted as auxiliary evidence", () => { const o = runVerify(readings()); const e = JSON.parse(o.spatial_evidence_json); return o.evidence_status === "VALID" && e.auxiliary_only === true && e.status === "verified_ids_only" && o.evidence_digest.includes("MIA-MM-12.GW01") && o.evidence_digest.includes("auxiliary"); }],
  ["gis verify: an invented object id rejects the evidence", () => { const r = readings(); r.g1.object_readings[0].object_id = "MIA-MM-12.RD99"; const o = runVerify(r); return o.evidence_status === "INVALID" && o.evidence_problems.some((x) => x.includes("RD99")) && o.evidence_digest.includes("NOT AVAILABLE"); }],
  ["gis verify: the guideway read as an obstacle is rejected", () => { const r = readings(); r.g1.object_readings.find((x) => x.object_id.endsWith("GW01")).role = "obstacle"; const o = runVerify(r); return o.evidence_status === "INVALID" && o.evidence_problems.some((x) => x.includes("facility to convert")); }],
  ["gis verify: an unread motorway ramp is rejected (required coverage)", () => { const r = readings(); r.g1.object_readings = r.g1.object_readings.filter((x) => !x.object_id.endsWith("RD02")); const o = runVerify(r); return o.evidence_status === "INVALID" && o.evidence_problems.some((x) => x.includes("RD02")); }],
  ["gis verify: a candidate site without caveats is rejected", () => { const r = readings(); r.g1.candidate_sites[0].caveats = []; return runVerify(r).evidence_status === "INVALID"; }],
  ["gis verify: a road proposed as a candidate site is rejected", () => { const r = readings(); r.g1.object_readings[0].role = "candidate_site"; return runVerify(r).evidence_status === "INVALID"; }],
  ["gis verify: heat not declared auxiliary is rejected", () => { const r = readings(); r.g2.auxiliary_only = false; const o = runVerify(r); return o.evidence_status === "INVALID" && o.evidence_problems.some((x) => x.includes("auxiliary")); }],
  ["gis verify: a picture-only observation with a number is rejected", () => { const r = readings(); r.g2.visual_observations_unverified.push("About 40 percent of the map is hot."); return runVerify(r).evidence_status === "INVALID"; }],
  ["gis verify: an unknown screening concern is rejected", () => { const r = readings(); r.g2.service_relevance_screening[0].concern = "delete_these_cells"; return runVerify(r).evidence_status === "INVALID"; }],
  ["gis verify: a number that is not in the inputs is a soft warning", () => { const r = readings(); r.g2.heat_reading[0].statement += " Roughly 98765 people."; const o = runVerify(r); return o.evidence_status === "VALID" && o.evidence_soft_warnings.some((x) => x.includes("98765")); }],
  ["output gate: verified spatial evidence is carried into the final object, labelled auxiliary", () => { const v = runVerify(readings()); const p = parts(); const s = JSON.parse(p.site_json); s.site_reading[1].object_ids = ["MIA-MM-12.ZN997"]; p.site_json = JSON.stringify(s);
      const o = assemble({ station_brief: briefText, ...p, spatial_evidence_json: v.spatial_evidence_json, evidence_object_ids: v.evidence_object_ids, gis_status: "PASS" }); const f = JSON.parse(o.final_json);
      return o.output_status === "VALID" && f.spatial_evidence.auxiliary_only === true && f.workflow.gis_verify === "verified_ids_only" && f.workflow.gis_gate === "PASS"; }],
  ["output gate: a statement citing a spatial object that was not verified is rejected", () => { const p = parts(); const s = JSON.parse(p.site_json); s.site_reading[1].object_ids = ["MIA-MM-12.ZN997"]; p.site_json = JSON.stringify(s); return assemble({ station_brief: briefText, ...p }).output_status === "INVALID"; }],
  ["output gate: without GIS readings the final object says the spatial evidence is not available", () => { const f = JSON.parse(assemble({ station_brief: briefText, ...parts(), gis_status: "NEEDS_REVIEW" }).final_json); return f.spatial_evidence.status === "not_available" && f.workflow.gis_gate === "NEEDS_REVIEW"; }],
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
  const bad = readings(); bad.g1.object_readings.find((x) => x.object_id.endsWith("GW01")).role = "obstacle";
  fs.writeFileSync(path.join(dir, "tampered_g1_json.guideway_as_obstacle.json"), JSON.stringify(bad.g1, null, 2) + "\n");
  fs.writeFileSync(path.join(dir, "wellformed_gis_readings.json"), JSON.stringify({ g1_json: JSON.stringify(gisExample.g1_json), g2_json: JSON.stringify(gisExample.g2_json) }, null, 2) + "\n");
  console.log("fixtures written to coze/v2/evals/fixtures/");
}
process.exit(ok === cases.length ? 0 : 1);
