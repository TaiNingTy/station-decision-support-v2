# KB_V2_03 · Interpretation guidance for a station brief

Knowledge base document 03 of 06 · version kb-v2.1 · issued 2026-09-18 · cite as `KB_V2_03 §IG-xx (kb-v2.1)`

This document tells the interpretation layer what it may conclude from a station brief, how to phrase it, and what it must hand to people. It is guidance, not a threshold set; the thresholds are in the rule pack.

## IG-01 Citation duty

Every statement of fact about the site cites at least one fact id from the brief (`<station>.Fnnn`). Every normative statement (should, must, cannot, is feasible) cites a rule result id (`<subject>|<scenario>|RC-xx`) with the rule pack version, or a section of this knowledge base. Every comparison between scenarios cites the fact ids of the compared values. A statement with no citation is not allowed; if no basis exists in the brief or the knowledge base, write it under "not covered by knowledge base".

## IG-02 Role proposal

Propose one role for the station as a hypothesis for human confirmation, using these readings of the brief:
- **destination_dominant**: the jobs-to-resident-workers ratio in the half-mile disc is well above 1, AM-peak alightings exceed boardings in the scenarios, and workplace-side link potential exceeds home-side potential.
- **origin_dominant**: the ratio is well below 1, AM-peak boardings exceed alightings, and home-side potential exceeds workplace-side potential.
- **mixed**: neither side dominates, or the indicators disagree.
- **hub_connection_dependent**: the station has external connections on the official map, and its observed share of system boardings is far above its scenario share (rule RC-11 with RC-12); the scenarios understate it by design.
- **insufficient_evidence**: the population estimate is unreliable (RC-08 warning) or the observed mapping is unconfirmed (RC-09 warning) and the remaining indicators do not agree.

State the evidence level as high / medium / low; it is a self-reported evidence level, not a probability. `requires_human_confirmation` is always true: the role is an analysis-layer decision, not a data-layer fact.

## IG-03 Reading residents and jobs together

Use population, households, workers, zero-vehicle share and transit-commute share to describe who lives near the station; use jobs, primary jobs and the jobs-to-resident-workers ratio to describe who works there. Say "an estimated" and give the margin of error or the reliability flag when a count is medium or low reliability. Never convert any of these into passengers per hour (DS-09). Never present the low-income share as a demand indicator (DS-10).

## IG-04 Reading facilities

Facility counts and nearest distances describe what the listings contain near the reference point. Say "listed", give straight-line distances, and do not infer walking access (DS-08, DS-02). A category with zero listings is "not found in these sources".

## IG-05 Reading the timetable and observed boardings

The current timetable and observed boardings describe the existing Metromover. Use them for context and scale only: the scenario's share of observed boardings (a few percent to about a third network-wide) shows how much the scenarios leave out, not how wrong they are. Never propose scaling a scenario to the observed count (DS-07).

## IG-06 Explaining a configuration result

For each scenario, explain which side (departures or arrivals) sets the berth cycles, how many empty vehicles the guideway must feed or remove, why the module was chosen, and which assumptions dominate the result (C01 party size, C04 peaking, A03 adoption). Quote the rule results that apply, including RC-07 (site fit assumed). When the network ratio RC-05 is a warning, say that a line model is needed before any capacity claim. Never call the result a design or a proof.

## IG-07 Risks and gaps

List the data gaps and reliability limits that matter for this station: unreliable estimates, unconfirmed name mapping, excluded transfer inflow, straight-line bands, absent site space, absent origin-destination and hourly data. Each with its fact id or rule result id.

## IG-08 Questions for the owner

End with the questions a human must answer before the configuration is used, each with why it matters: constructible space at this station, confirmation of the platform module berth counts, confirmation of renamed-station mappings, whether transfer inflow should be modeled here, whether the demonstration assumptions match the intended service.

## IG-09 What the interpretation layer must never do

Invent a number that is not in the brief; cite a standard, code or regulation that is not in this knowledge base; treat density or facility counts as demand; use zoning to exclude an area; infer willingness to pay from income; average medians; read job links as trips; scale scenarios to observed counts; call an assumption an observation; call a result a design, a forecast or a proof; present a critical rule result as usable.

## IG-10 Form of the answer

Return the JSON object defined by `config/ai_output_schema_v2.json`, in English, with no text outside the JSON. Keep statements short and specific. Where the knowledge base has nothing to say, use the `not_covered_by_knowledge_base` list rather than improvising.
