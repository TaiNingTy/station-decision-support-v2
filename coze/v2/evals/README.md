# Evals for the V2 code nodes

`node coze/v2/evals/run.js` runs 32 cases against the four code nodes exactly as they are pasted into Coze
(`nodes/gis_gate.js`, `nodes/gis_verify.js`, `nodes/brief_gate.js`, `nodes/assemble_and_validate.js`). `--write-fixtures` also writes the fixture files used by the
Coze trial runs in the playbook.

| Group | Cases |
|---|---|
| Input gate | a real brief passes · an injected critical rule result blocks · a missing rule result needs review (never a pass) · malformed JSON · empty input · too few facts |
| GIS gate | real reading-agent inputs become tables · inputs of two stations · a parcel row with an owner field (privacy guard) · a heat layer not labelled as a proxy |
| GIS verifier | well-formed readings accepted as auxiliary evidence · an invented object id · the guideway read as an obstacle · an unread motorway ramp · a candidate site without caveats · a road proposed as a candidate site · heat not declared auxiliary · a picture-only observation with a number · an unknown screening concern · a number not in the inputs is only a soft warning |
| Output gate | verified spatial evidence carried into the final object · a statement citing an unverified spatial object is rejected · without readings the final object says so · well-formed parts assemble to VALID · an invented fact id is rejected and named · an invented rule result id · an external standard cited as a KB reference · a role without human confirmation · a scenario that omits RC-07 · markdown fences tolerated · an unparseable agent output · a number that is not in the brief is a soft warning, not a rejection |

The cases mutate a **real** compact brief (`ai/miami/briefs/MIA-MM-12.coze.json`) in memory. The well-formed parts come
from the hand-written format example, which is not a model output. Fixture files carry a `_notice` field saying they are
test fixtures. Passing these evals proves the code nodes behave as specified; it proves nothing about a model run,
because no model run exists yet.
