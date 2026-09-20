# Coze V2 · workflow `station_decision_v2` — design

Status 2026-09-20: designed; four code nodes written and evaluated locally (32/32 cases); **not built on Coze yet, no model run exists**. The V1 Bot and the V1.1 workflow `station_gate_v1` stay on Coze untouched; V2 is a new, separate workflow with its own knowledge base.

## Principle

**AI reads and interprets, code verifies, people decide.** Two reading agents read the GIS features themselves: roads, rail, the existing guideway, zoning polygons, land-use classes, parcels, a heat proxy and block groups. Code has only clipped, measured, joined and counted those features and given each one an id. Three further agents, kept from the V1 skeleton, turn the sourced facts, the rule results and the spatial evidence into a site reading, a grounded review and an explanation of the computed configuration. Every citation is checked by code, and every judgement is handed to a person.

The heat map is a **proxy** built from public counts (2020 Census residents + 2023 LODES jobs per acre, 500 ft cells), labelled as such in the data, in the picture and in every prompt. Heat and zoning are read **together** and are **auxiliary evidence**: they support, qualify or question a reading; they decide neither demand, nor a station role, nor a configuration.

## What stays from V1 / V1.1, and what changes

| Part | V1 / V1.1 | V2 |
|---|---|---|
| Input | free-text site brief typed by the user | fetched by station id: feature tables for the reading agents (`g1_input.json`, `g2_input.json`, `heat.png`) and a structured brief with 83 sourced facts and all rule results (`brief.coze.json`) |
| GIS reading | out of scope (V1); planned as pre-structured features (V1.1 roadmap) | **new agents G1 and G2** read feature-level GIS data and the heat-proxy picture, assign roles to objects, read heat with zoning, screen heat for service relevance and report data anomalies |
| Agent 1 | Requirement Analysis: parse the brief, grade S/A/B/C from a typed peak flow | **Site Reading**: what the sourced facts and the spatial evidence show; a role hypothesis that a person must confirm |
| Agent 2 | Retrieval + Rule Evaluation: the LLM judged compliance (V1); one hard constraint in code (V1.1) | **Grounded Rule & Evidence Review**: every rule is already evaluated by code; the agent explains results, gaps and screening findings with KB citations, or says "not covered" |
| Agent 3 | Configuration + Documentation: recommended values with a confidence column | **Configuration Explanation & Decision Brief**: the configuration is computed by code; the agent explains drivers, assumptions, risks and the owner's questions, pointing at candidate parcels where the readers found some |
| Knowledge base | KB_01–04, Chinese, synthetic rules and cases | kb-v2.1, six documents: data semantics, scenario chain and PRT method, interpretation guidance, open items, **GIS reading guidance**, **layer legends generated from the layers themselves** |
| Gates (code + selector) | `site-gate`: curve radius → BLOCKED / NEEDS_REVIEW / PASS | `gis-gate` (inputs belong together, heat labelled proxy, no owner or address field) · `gis-verify` (ids exist, roles in the enum, required objects read, guideway never an obstacle, heat declared auxiliary) · `brief-gate` (critical rule result → BLOCKED, missing rule result → NEEDS_REVIEW) · `assemble-and-validate` (invented citation → rejected) |
| Human review | flagged at the top of the delivery document | roles and candidate sites are hypotheses with evidence levels; `requires_human_confirmation`; owner questions; run record with a review status |
| Proof | 27 m → BLOCKED, generator 0 tokens; 35 m → PASS | injected-critical brief → BLOCKED, 0 tokens; guideway read as obstacle → evidence rejected; invented id → answer rejected |

## Workflow

```
开始  station_id : String                                   e.g. MIA-MM-12
  → HTTP ×3  GET {base}/{station_id}/g1_input.json · g2_input.json · brief.coze.json
             base = https://tainingty.github.io/station-decision-support-v2/gis
  → Code  gis-gate        (g1_input, g2_input)               → gis_status, allow_reading, tables for G1 / G2, heat_image_url
  → 条件分支  allow_reading ?
      ├─ yes → 知识库 kb-v2.1 (kb_query_gis)                  → kb_chunks_gis
      │        LLM G1  GIS Reader          (roads, rail, zoning, land-use, parcel tables + facts)        → g1_json
      │        LLM G2  Heat & Residents    (heat.png + cell table, block groups, zoning + facts)         → g2_json
      │        Code  gis-verify  (g1_input, g2_input, g1_json, g2_json) → evidence_status, spatial_evidence_json, evidence_digest, evidence_object_ids
      └─ no  → (skip; evidence_digest = "spatial evidence not available")          ← auxiliary: never blocks the station
  → Code  brief-gate      (station_brief)                     → workflow_status, allow_interpretation, facts_table, rules_table, caveats, kb_query
  → 条件分支  allow_interpretation ?
      ├─ yes → LLM1 Site Reading   (facts, rules, caveats, evidence_digest)                    → site_json
      │        知识库 kb-v2.1 (kb_query)                                                        → kb_chunks
      │        LLM2 Grounded Review (facts, rules, caveats, site_json, evidence_digest, kb_chunks) → review_json
      │        LLM3 Configuration Brief (facts, rules, site_json, review_json, evidence_digest, kb_chunks) → config_json
      │        Code  assemble-and-validate (station_brief, site_json, review_json, config_json, spatial_evidence_json, evidence_object_ids, gis_status)
      │        条件分支  allow_output ?  ├─ yes → 结束 final_json (draft, "unreviewed")
      │                                 └─ no  → 结束 "REJECTED BY OUTPUT GATE" + problems
      └─ no  → 结束  workflow_status + blocked_reasons       (BLOCKED or NEEDS_REVIEW; LLM1–3 never run: 0 tokens)
```

Node files: [`nodes/gis_gate.js`](nodes/gis_gate.js), [`nodes/gis_verify.js`](nodes/gis_verify.js), [`nodes/brief_gate.js`](nodes/brief_gate.js), [`nodes/assemble_and_validate.js`](nodes/assemble_and_validate.js). Agent specs and prompts: [`agents/`](agents/) (G1, G2, 01, 02, 03). Build guide (Chinese): [`BUILD_PLAYBOOK.zh.md`](BUILD_PLAYBOOK.zh.md). Local evals: `node coze/v2/evals/run.js` (32 cases). The inputs are produced by `scripts/build_miami_gis_objects.py` (stage `gis_objects`) and `scripts/export_miami_gis_agent_inputs.py`.

## What the reading agents receive, and what they do not

They receive features with attributes as the sources carry them: a road group with its OpenStreetMap class, bridge flag and distance; a zoning polygon with its zone name, transect description, height figure and letters; a parcel with the appraiser's land-use description, lot size and year built; a heat cell with its activity density, jobs share, dominant transect, dominant land use and highest road class. They also receive code-computed summary numbers (`.Gnnn`) that they may restate.

They do not receive roles, hints, recommendations or conclusions. Rule-based role hints exist in the data package and are used afterwards to measure how often the agents agree with simple rules and to queue disagreements for a person. Parcels carry no owner, mailing, site-address or legal-description field, and the county layer that holds owner names is never fetched.

## Decisions

- **D1′ Fixed pipeline again.** Controllability, evaluability and error localisation still beat autonomy; each agent has one contract and one failure mode to test.
- **D2′ Reading is the model's job, measuring is code's job.** Decoding a zone name, recognising that a "railroad" is the transit guideway, noticing that a downtown parcel is classified as cropland, relating a hot cell to the park it sits on: these are semantic, cross-layer judgements a model does well and rules do badly. Lengths, areas, shares and counts are computed once, by code.
- **D3′ Spatial evidence is auxiliary by contract.** `auxiliary_only` must be true, the digest is labelled, a failed GIS gate or a rejected reading never blocks the station, and heat or zoning alone may not set a role.
- **D4′ Code decides every rule.** The whole rule pack (rules-v2.0) is evaluated before any model runs; `critical` blocks, a missing rule result is NEEDS_REVIEW.
- **D5′ Grounding is checkable.** Every fact, rule result, KB section and spatial object has an id; an answer that cites an id that does not exist is rejected by code.
- **D6′ Known traps are encoded as checks.** The county rail layer draws the Metromover guideway as rail; reading the guideway as an obstacle rejects the evidence. A picture-only observation may not carry a number. A candidate site must be a parcel and must carry its caveats.
- **D7′ The model never computes;** numbers outside the inputs are soft warnings for the reviewer.
- **D8′ Evidence level, not probability;** manual runs are labelled manual; V1 artifacts are never edited.

## What the design does not claim

The heat layer is a proxy, not a measurement. Verification proves that ids exist, enums hold and required objects were read; it does not prove an interpretation right, which is what the human review, the hint-agreement report and the soft warnings are for. The rule pack is a set of project conventions and identities, not a standard. No V2 run exists yet; nothing here is "verified on Coze" until the trial runs in the playbook are done and their records are saved.
