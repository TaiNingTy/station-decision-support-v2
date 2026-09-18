#!/usr/bin/env python3
"""Check one AI interpretation output against the brief, the rule results, the knowledge base and the output schema.

    python3 scripts/check_miami_ai_output.py ai/miami/runs/MIA-MM-12/20260920-1015.json [more files]

Hard checks (any failure = FAIL): schema shape and enums, versions match the kit / KB / rule pack, every fact id exists in
the station's brief, every rule result id exists in the rules package, every KB reference exists in the KB documents,
RC-03 (per scenario) and RC-07 are cited in each configuration reading, requires_human_confirmation is true, run_record
mode and review status are valid, run_id is null unless the platform returned one (cannot be verified here — recorded).
Soft checks (reported as warnings for the reviewer): numbers in statements that do not appear among the brief's values,
phrases that suggest a forbidden inference (willingness to pay, forecast, calibrated, per hour from density, standards).
Writes <file>.check.json next to the output and exits 1 on FAIL. Example outputs (execution_mode
example_not_a_model_output) are checked like any other but flagged as never publishable.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from miami_v2_common import *   # noqa: E402,F401,F403

KIT = load(ROOT / "ai/miami/kit_manifest.json"); KB = load(ROOT / "kb/v2/manifest.json"); SCHEMA = load(ROOT / "config/ai_output_schema_v2.json")
rules_dir = DATA / load(DATA / "rules_current.json")["package_dir"]; RULES = load(rules_dir / "rule_results.json")
RULE_IDS = {r["rule_result_id"] for b in RULES["stations"] for r in b["results"]} | {r["rule_result_id"] for r in RULES["network"]["results"]}
KB_REFS = {f"{d['doc_id']} §{s}" for d in KB["documents"] for s in d["sections"]}
FACT_RE, RULE_RE, KB_RE = re.compile(r"^MIA-MM-\d{2}\.F\d{3}$"), re.compile(r"^(MIA-MM-\d{2}|NET)\|(low|medium|high|-)\|RC-\d{2}$"), re.compile(r"^KB_V2_0[1-4] §(DS|CM|IG|OI)-\d{2}$")
ROLES = {"origin_dominant", "destination_dominant", "mixed", "hub_connection_dependent", "insufficient_evidence"}
SOFT = [(r"willingness to pay", "income read as willingness to pay (KB_V2_01 §DS-10)"), (r"\bforecast", "scenario called a forecast (KB_V2_02 §CM-08)"), (r"(?<!un)calibrat", "calibration claimed or proposed (KB_V2_01 §DS-07)"),
        (r"(persons|people|passengers)\s*(per|/)\s*hour", "a per-hour flow stated; verify it comes from the scenario facts, not from density (§DS-09)"),
        (r"\b(GB/T|CJJ|NFPA|ADA|AASHTO|NACTO|TCRP)\b", "external standard named (not in the knowledge base)"), (r"\bguarantee|\bwill attract|\bproven\b", "overclaim wording"),
        (r"\btrips?\b[^.]{0,40}\b(LODES|job links?|job-to-home)", "job links described as trips (§DS-05)")]


def numbers_in(text):
    return {n.replace(",", "") for n in re.findall(r"(?<![\w.])\d[\d,]*\.?\d*(?![\w])", text)}


def flatten_values(v, out):
    if isinstance(v, dict): [flatten_values(x, out) for x in v.values()]
    elif isinstance(v, list): [flatten_values(x, out) for x in v]
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        out.add(f"{v}"); out.add(f"{round(v)}"); out.add(f"{round(v, 1)}"); out.add(f"{round(v, 2)}")
        if isinstance(v, float) and v < 1: out.add(f"{round(v * 100, 1)}"); out.add(f"{round(v * 100)}")
    elif isinstance(v, str): [out.add(n) for n in numbers_in(v)]


def check(path):
    hard, soft = [], []
    try: o = load(path)
    except Exception as e: return {"file": str(path), "verdict": "FAIL", "hard_failures": [f"not valid JSON: {e}"], "warnings": []}
    H = lambda cond, msg: (None if cond else hard.append(msg))
    for k in SCHEMA["required_top_level"]: H(k in o, f"missing top-level field {k}")
    if hard: return {"file": str(path), "verdict": "FAIL", "hard_failures": hard, "warnings": soft}
    pid = o["station_id"]; brief_path = ROOT / "ai/miami/briefs" / f"{pid}.json"
    H(o["schema_version"] == "miami-ai-output/1.0", "schema_version must be miami-ai-output/1.0"); H(bool(re.match(r"^MIA-MM-\d{2}$", str(pid))), "station_id malformed")
    H(o["brief_id"] == pid, "brief_id must equal station_id"); H(brief_path.exists(), f"no brief for {pid}")
    H(o["kit_version"] == KIT["kit_version"], f"kit_version {o['kit_version']} != {KIT['kit_version']}"); H(o["kb_version"] == KB["kb_version"], f"kb_version != {KB['kb_version']}")
    H(o["rule_pack_version"] == RULES["rule_pack_version"], f"rule_pack_version != {RULES['rule_pack_version']}"); H(o["prompt_version"] == KB["agent_prompt"]["version"], f"prompt_version != {KB['agent_prompt']['version']}")
    facts = {f["fact_id"] for f in load(brief_path)["facts"]} if brief_path.exists() else set()
    brief_numbers = set(); flatten_values([f["value"] for f in load(brief_path)["facts"]] if brief_path.exists() else [], brief_numbers)

    def ids_ok(lst, kind, where):
        if not isinstance(lst, list): hard.append(f"{where}: {kind} must be a list"); return
        for x in lst:
            if kind == "fact": H(isinstance(x, str) and FACT_RE.match(x) and x in facts, f"{where}: unknown fact id {x}")
            elif kind == "rule": H(isinstance(x, str) and RULE_RE.match(x) and x in RULE_IDS, f"{where}: unknown rule result id {x}")
            elif kind == "kb": H(isinstance(x, str) and KB_RE.match(x) and x in KB_REFS, f"{where}: unknown KB reference {x}")
            elif kind == "any": H(isinstance(x, str) and (x in facts or x in RULE_IDS or x in KB_REFS), f"{where}: unknown id {x}")

    def statements(lst, where, need_fact=True):
        H(isinstance(lst, list) and len(lst) >= 1, f"{where}: at least one entry");
        for i, st in enumerate(lst if isinstance(lst, list) else []):
            H(isinstance(st, dict) and isinstance(st.get("statement"), str) and st["statement"].strip(), f"{where}[{i}]: statement text missing")
            ids_ok(st.get("fact_ids", []), "fact", f"{where}[{i}]"); ids_ok(st.get("rule_result_ids", []), "rule", f"{where}[{i}]"); ids_ok(st.get("kb_refs", []), "kb", f"{where}[{i}]")
            if need_fact: H(len(st.get("fact_ids", [])) >= 1, f"{where}[{i}]: a site statement needs at least one fact id")
            else: H(any(st.get(k) for k in ("fact_ids", "rule_result_ids", "kb_refs")), f"{where}[{i}]: needs a fact id, rule result id or KB reference")
            txt = st.get("statement", "") if isinstance(st, dict) else ""
            for n in numbers_in(txt) - brief_numbers:
                if len(n.replace(".", "")) >= 2: soft.append(f"{where}[{i}]: number {n} is not among the brief's values")
            for pat, msg in SOFT:
                if re.search(pat, txt, flags=re.I): soft.append(f"{where}[{i}]: {msg}")
    statements(o["site_reading"], "site_reading"); H(3 <= len(o["site_reading"]) <= 8, "site_reading must hold 3 to 8 statements")
    statements(o["data_gaps_and_reliability"], "data_gaps_and_reliability", need_fact=False)
    rp = o["role_proposal"]; H(isinstance(rp, dict) and rp.get("role") in ROLES, "role_proposal.role not in the allowed set")
    H(rp.get("requires_human_confirmation") is True, "role_proposal.requires_human_confirmation must be true"); H(rp.get("evidence_level") in ("high", "medium", "low"), "role_proposal.evidence_level invalid")
    ids_ok(rp.get("basis_fact_ids", []), "fact", "role_proposal"); H(len(rp.get("basis_fact_ids", [])) >= 1, "role_proposal needs basis fact ids"); ids_ok(rp.get("rule_result_ids", []), "rule", "role_proposal")
    H(isinstance(rp.get("rationale"), str) and rp["rationale"].strip(), "role_proposal.rationale missing")
    cr = o["configuration_reading"]; H(isinstance(cr, dict) and set(cr) == {"low", "medium", "high"}, "configuration_reading must have low, medium, high")
    for s in ("low", "medium", "high"):
        blk = cr.get(s, {}) if isinstance(cr, dict) else {}
        statements(blk.get("drivers", []), f"configuration_reading.{s}.drivers"); ids_ok(blk.get("rule_result_ids", []), "rule", f"configuration_reading.{s}"); ids_ok(blk.get("kb_refs", []), "kb", f"configuration_reading.{s}")
        H(f"{pid}|{s}|RC-03" in blk.get("rule_result_ids", []), f"configuration_reading.{s} must cite {pid}|{s}|RC-03"); H(f"{pid}|-|RC-07" in blk.get("rule_result_ids", []), f"configuration_reading.{s} must cite {pid}|-|RC-07")
        for r in blk.get("risks", []):
            for pat, msg in SOFT:
                if re.search(pat, str(r), flags=re.I): soft.append(f"configuration_reading.{s}.risks: {msg}")
    q = o["questions_for_owner"]; H(isinstance(q, list) and len(q) >= 1, "questions_for_owner needs at least one entry")
    for i, x in enumerate(q if isinstance(q, list) else []):
        H(isinstance(x, dict) and x.get("question") and x.get("why_it_matters"), f"questions_for_owner[{i}] incomplete"); ids_ok(x.get("related_ids", []), "any", f"questions_for_owner[{i}]")
    H(isinstance(o["not_covered_by_knowledge_base"], list), "not_covered_by_knowledge_base must be a list")
    rr = o["run_record"]; H(isinstance(rr, dict) and rr.get("execution_mode") in ("coze_ui_manual", "coze_api", "example_not_a_model_output"), "run_record.execution_mode invalid")
    rv = rr.get("review", {}) if isinstance(rr, dict) else {}; H(rv.get("status") in ("unreviewed", "reviewed_ok", "reviewed_with_edits", "rejected"), "run_record.review.status invalid")
    H(rr.get("run_id") is None or isinstance(rr.get("run_id"), str), "run_record.run_id must be null or a string")
    publishable = (not hard) and rr.get("execution_mode") != "example_not_a_model_output" and rv.get("status") in ("reviewed_ok", "reviewed_with_edits")
    # critical results must not be presented as usable: any station critical result must appear in the gaps or risks
    crit = [r["rule_result_id"] for b in RULES["stations"] if b["station_id"] == pid for r in b["results"] if r["status"] == "critical"]
    cited = set(sum([blk.get("rule_result_ids", []) for blk in cr.values()], []) + sum([st.get("rule_result_ids", []) for st in o["data_gaps_and_reliability"]], [])) if isinstance(cr, dict) else set()
    for c in crit: H(c in cited, f"critical rule result {c} is not acknowledged")
    return {"file": str(path), "station_id": pid, "verdict": "PASS" if not hard else "FAIL", "publishable": publishable, "execution_mode": rr.get("execution_mode"), "review_status": rv.get("status"),
            "hard_failures": hard, "warnings": soft, "counts": {"site_statements": len(o["site_reading"]), "gaps": len(o["data_gaps_and_reliability"]), "questions": len(q) if isinstance(q, list) else 0},
            "checked_against": {"kit_version": KIT["kit_version"], "kb_version": KB["kb_version"], "rule_pack_version": RULES["rule_pack_version"], "rules_package": load(DATA / "rules_current.json")["package_id"]}}


if __name__ == "__main__":
    files = [Path(a) for a in sys.argv[1:]]
    if not files: raise SystemExit(__doc__)
    bad = 0
    for p in files:
        r = check(p); dump(Path(str(p) + ".check.json"), r); bad += r["verdict"] != "PASS"
        print(f"{r['verdict']} {p} publishable={r.get('publishable')} hard={len(r['hard_failures'])} warnings={len(r['warnings'])}")
        for h in r["hard_failures"]: print("   HARD:", h)
        for w in r["warnings"][:12]: print("   warn:", w)
    sys.exit(1 if bad else 0)
