# Coze V2 · workflow `station_decision_v2` — design

Status 2026-09-20: designed, code nodes written and evaluated locally (15/15); **not built on Coze yet, no model run exists**. The V1 Bot and the V1.1 workflow `station_gate_v1` stay on Coze untouched; V2 is a new, separate workflow with its own knowledge base.

## What stays from V1 / V1.1, and what changes

V2 keeps the V1 skeleton on purpose: three specialised agents in a fixed pipeline, a knowledge base that must be retrieved and is the only thing that may be cited, a deterministic code gate with a conditional branch that physically blocks generation, and an explicit hand-off to people. What changes is what each part is allowed to do.

| Part | V1 / V1.1 | V2 |
|---|---|---|
| Input | free-text site brief typed by the user | a structured station brief built from verified data packages: 83 facts with `fact_id`, all rule results with `rule_result_id`, versions (`ai/miami/briefs/<station>.coze.json`) |
| Agent 1 | Requirement Analysis: parse the brief, assign a grade S/A/B/C from a typed peak flow | **Site Reading**: say what the sourced facts show; propose a role (enum) that a person must confirm; no grade, no arithmetic |
| Agent 2 | Retrieval + Rule Evaluation: the LLM judged compliance from the KB (V1); hard constraint moved to code (V1.1) | **Grounded Rule & Evidence Review**: every rule is already evaluated by code; the agent explains the results and the data gaps with KB citations, or says "not covered" |
| Agent 3 | Configuration + Documentation: recommended values with a confidence column, delivery document | **Configuration Explanation & Decision Brief**: the configuration is computed by code; the agent explains drivers, assumptions and risks and lists the owner's questions |
| Knowledge base | KB_01–04, Chinese, synthetic planning / engineering rules and cases | kb-v2.0: KB_V2_01 data semantics, 02 scenario chain and PRT method, 03 interpretation guidance, 04 open items and ownership (English, 41 citable sections) |
| Input gate (code + selector) | `site-gate`: curve radius < 30 m → BLOCKED; missing → NEEDS_REVIEW; PASS otherwise | `brief-gate`: any critical rule result → BLOCKED; malformed brief or a missing required rule result → NEEDS_REVIEW; PASS otherwise. Same three statuses, same "a missing input is not a pass" |
| Output gate | planned in V1.1 (config rules after LLM3), not built | **new** `assemble-and-validate`: merges the three outputs and rejects the answer when any cited fact id, rule result id or KB section does not exist, when a scenario omits RC-03 / RC-07, or when the role is not flagged for human confirmation |
| Human review | flagged at the top of the delivery document | `requires_human_confirmation`, `questions_for_owner`, and a run record whose review status starts as `unreviewed`; only reviewed outputs are published |
| Proof | token accounting: 27 m → BLOCKED, generator 0 tokens; 35 m → PASS, 1431 tokens | the same method with a labelled test fixture (a brief whose `NET|high|RC-05` is forced to critical): BLOCKED, 0 tokens; a real brief: PASS; a tampered agent output: INVALID |

## Workflow

```
开始  station_brief : String                      (paste ai/miami/briefs/<station>.coze.json)
  → Code  brief-gate            → workflow_status, allow_interpretation, blocked_reasons,
  │                               station_id, station_name, facts_table, rules_table, caveats, kb_query, …
  → 条件分支  allow_interpretation is True ?
      ├─ yes → LLM1  Site Reading                 (facts_table, rules_table, caveats)            → site_json
      │        知识库  kb-v2.0                     (query = kb_query)                              → kb_chunks
      │        LLM2  Grounded Review              (facts_table, rules_table, caveats, site_json, kb_chunks) → review_json
      │        LLM3  Configuration Brief          (facts_table, rules_table, caveats, site_json, review_json, kb_chunks) → config_json
      │        Code  assemble-and-validate        (station_brief, site_json, review_json, config_json)
      │                                           → output_status, allow_output, problems, soft_warnings, final_json
      │        条件分支  allow_output is True ?
      │            ├─ yes → 结束  final_json                       (draft; review status "unreviewed")
      │            └─ no  → 结束  "REJECTED BY OUTPUT GATE" + problems      (nothing is emitted as an answer)
      └─ no  → 结束  workflow_status + blocked_reasons              (BLOCKED or NEEDS_REVIEW; no LLM node runs)
```

Node files: [`nodes/brief_gate.js`](nodes/brief_gate.js), [`nodes/assemble_and_validate.js`](nodes/assemble_and_validate.js). Agent specs and prompts: [`agents/`](agents/). Step-by-step build guide (Chinese): [`BUILD_PLAYBOOK.zh.md`](BUILD_PLAYBOOK.zh.md). Local evals: `node coze/v2/evals/run.js` (15 cases).

## Decisions

- **D1′ Fixed pipeline again.** Controllability, evaluability and error localisation still beat autonomy; each agent has one contract and one failure mode to test.
- **D2′ Code decides every rule, not just one.** V1.1 moved one hard constraint into code. V2 evaluates the whole rule pack (rules-v2.0) before any model runs; the model receives statuses as facts. The gate blocks on `critical`, and treats a missing rule result as NEEDS_REVIEW.
- **D3′ Grounding is now checkable, not just requested.** V1 asked the model to cite only the KB and caught violations by reading. V2 gives every fact, rule result and KB section an id, and code rejects an answer that cites an id that does not exist. "Will it admit when it doesn't know" becomes "can it get an invented citation past the gate" — it cannot.
- **D4′ The model never computes.** Numbers live in the brief; the output gate lists numbers that are not in the brief as soft warnings for the reviewer (soft, because a model may legitimately restate a rounded value).
- **D5′ Grounding and generation stay separated.** Agent 2 explains rules and gaps with the KB; Agent 3 explains the computed configuration. Neither recommends a value.
- **D6′ Evidence level, not probability.** Kept from V1: high / medium / low is a self-reported evidence level.
- **D7′ Two artifacts on Coze, both kept.** V1 Bot + V1.1 workflow remain as the record of the first build; V2 is a third artifact. Nothing in V1 is edited.
- **D8′ Manual runs are labelled manual.** A trial run in the Coze UI is recorded as `coze_ui_manual`; a run id is recorded only if the platform returns one.

## What the design does not claim

The rule pack is a set of project conventions, arithmetic identities and scope flags, not a standard. The output gate proves that citations exist, not that the reasoning is right; that is what the human review and the Python checker's soft warnings are for. No V2 run exists yet, so nothing here is "verified on Coze" until the trial runs in the playbook are done and their records are saved.
