# Station brief · Financial District (MIA-MM-21) · kit ai-kit-v2.1 · KB kb-v2.1 · rules rules-v2.0

Use only these facts and the knowledge base kb-v2.1. Cite fact ids for site facts, rule result ids for normative statements, KB sections for guidance. Do not write numbers that are not here. Answer as the JSON object of config/ai_output_schema_v2.json.

## Facts (cite by fact_id)

| fact_id | label | value | unit | provenance | reliability / MOE |
|---|---|---|---|---|---|
| MIA-MM-21.F001 | GTFS stop ids mapped to this station | ["801", "821"] |  | observed |  |
| MIA-MM-21.F002 | existing asset and study role | metromover_station → candidate_conversion_site |  | observed |  |
| MIA-MM-21.F003 | external connections on the official map | none |  | observed |  |
| MIA-MM-21.F004 | zoning at the reference point | ["T6-48A-O"] |  | observed |  |
| MIA-MM-21.F005 | geometry role | GTFS reference point; not an entrance, not a platform centroid |  | observed |  |
| MIA-MM-21.F006 | half-mile disc: land area | 361.75 | acres | derived |  |
| MIA-MM-21.F007 | half-mile disc: zoned share of area | 0.68 |  | observed |  |
| MIA-MM-21.F008 | half-mile disc: largest zoning transects by share of area | [["Urban Core Zone", 0.563], ["Sub-Urban Zone", 0.061], ["Urban Center Zone", 0.02]] |  | observed |  |
| MIA-MM-21.F009 | half-mile disc: population (ACS 2020–2024 period estimate) | 28289 | persons | derived | high / ±2222.02 |
| MIA-MM-21.F010 | half-mile disc: households | 16007 | households | derived | high / ±1218.17 |
| MIA-MM-21.F011 | half-mile disc: workers 16+ | 19228 | workers | derived | high / ±1917.21 |
| MIA-MM-21.F012 | half-mile disc: zero-vehicle household share | 14.4 | percent | derived | high / ±2.6 |
| MIA-MM-21.F013 | half-mile disc: public-transportation commute share (reference only) | 4.9 | percent | derived | medium / ±1.6 |
| MIA-MM-21.F014 | half-mile disc: worked-from-home share | 28.4 | percent | derived | high / ±2.3 |
| MIA-MM-21.F015 | half-mile disc: households below $35,000 share (project convention, not a demand indicator) | 15.9 | percent | derived | high / ±3.0 |
| MIA-MM-21.F016 | half-mile disc: population 65+ share | 9.5 | percent | derived | high / ±1.9 |
| MIA-MM-21.F017 | half-mile disc: median household income estimate (bracket interpolation; sensitivity range, not a confidence interval) | {"value_usd": 115577, "range_usd": [100000, 125000], "open_ended": false} |  | derived |  |
| MIA-MM-21.F018 | half-mile disc: population density | 50047.2 | persons per sq mi | derived |  |
| MIA-MM-21.F019 | half-mile disc: all jobs located here (LODES 2023, C000 JT00) | 29953 | jobs | derived |  |
| MIA-MM-21.F020 | half-mile disc: primary jobs located here (JT01) | 28071 | jobs | derived |  |
| MIA-MM-21.F021 | half-mile disc: primary jobs held by residents (≈ resident workers) | 12072 | jobs | derived |  |
| MIA-MM-21.F022 | half-mile disc: jobs-to-resident-workers ratio (JT01) | 2.33 |  | derived |  |
| MIA-MM-21.F023 | half-mile disc: jobs per acre of land | 82.799 | jobs per acre | derived |  |
| MIA-MM-21.F024 | inner band (0–1/8 mi): population | 2053 | persons | derived | high / ±242.92 |
| MIA-MM-21.F025 | inner band (0–1/8 mi): all jobs located here | 5024 | jobs | derived |  |
| MIA-MM-21.F026 | half-mile disc: school facilities listed | 5 | facilities | observed |  |
| MIA-MM-21.F027 | nearest school by straight line | {"name": "Kingsbury Academy", "distance_ft": 395.6, "within_half_mile": true} |  | observed |  |
| MIA-MM-21.F028 | half-mile disc: clinic facilities listed | 0 | facilities | observed |  |
| MIA-MM-21.F029 | nearest clinic by straight line | {"name": "Comprehensive Examination of Vision and Ocular Health", "distance_ft": 5389.9, "within_half_mile": false} |  | observed |  |
| MIA-MM-21.F030 | half-mile disc: grocery facilities listed | 2 | facilities | observed |  |
| MIA-MM-21.F031 | nearest grocery by straight line | {"name": "PUBLIX 581", "distance_ft": 1347.9, "within_half_mile": true} |  | observed |  |
| MIA-MM-21.F032 | half-mile disc: park facilities listed | 4 | facilities | observed |  |
| MIA-MM-21.F033 | nearest park by straight line | {"name": "Simpson Park", "distance_ft": 803.1, "within_half_mile": true} |  | observed |  |
| MIA-MM-21.F034 | current timetable: scheduled departures per hour, 7–9 a.m. (all routes) | 24.0 | departures per hour | derived |  |
| MIA-MM-21.F035 | current timetable: implied AM-peak headway | 2.5 | minutes | derived |  |
| MIA-MM-21.F036 | current timetable: weekday scheduled departures and span | {"departures": 398, "first": "05:30", "last": "22:08"} |  | derived |  |
| MIA-MM-21.F037 | observed boardings of the current Metromover: average weekday, 10-month mean (2025-10 to 2026-07) | 966.8 | boardings per weekday | observed |  |
| MIA-MM-21.F038 | observed boardings: share of system average weekday boardings | 0.0381 |  | derived |  |
| MIA-MM-21.F039 | observed boardings: report station name and mapping basis | {"report_station_name": "Financial District", "mapping_basis": "same_name", "mapping_confirmed_by_owner": false} |  | observed |  |
| MIA-MM-21.F040 | observed boardings: system average weekday, 10-month mean | 25401.8 | boardings per weekday | observed |  |
| MIA-MM-21.F041 | job-link potential, home side (Σ primary links × land share; not trips, non-exclusive) | 11933 | links | derived |  |
| MIA-MM-21.F042 | job-link potential, workplace side (Σ primary links × land share; not trips, non-exclusive) | 28071 | links | derived |  |
| MIA-MM-21.F043 | network half-mile union: population (deduplicated) | 76357 | persons | derived |  |
| MIA-MM-21.F044 | network half-mile union: all jobs (deduplicated) | 180847 | jobs | derived |  |
| MIA-MM-21.F045 | network half-mile union: area | 3.57 | sq mi | derived |  |
| MIA-MM-21.F046 | low scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 0.5, "A03": 0.05} |  | assumption |  |
| MIA-MM-21.F047 | low scenario: network AM-peak PRT person trips | 144.94 | person trips per hour | derived |  |
| MIA-MM-21.F048 | low scenario: this station's AM-peak boardings | 14.17 | person trips per hour | derived |  |
| MIA-MM-21.F049 | low scenario: this station's AM-peak alightings | 10.38 | person trips per hour | derived |  |
| MIA-MM-21.F050 | low scenario: this station's share of network AM boardings | 0.0977 |  | derived |  |
| MIA-MM-21.F051 | low scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 10.9, "arrivals": 7.98} | vehicle trips per hour | derived |  |
| MIA-MM-21.F052 | low scenario: empty vehicles required in / leaving per hour | {"required_in": 2.92, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-21.F053 | low scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 10.9, "design_cycles": 13.62, "usable_cycles_per_berth_hour": 64.0, "berths_required": 1} |  | derived |  |
| MIA-MM-21.F054 | low scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-21.F055 | low scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-21.F056 | low scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.093 |  | derived |  |
| MIA-MM-21.F057 | medium scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 1.0, "A03": 0.15} |  | assumption |  |
| MIA-MM-21.F058 | medium scenario: network AM-peak PRT person trips | 579.76 | person trips per hour | derived |  |
| MIA-MM-21.F059 | medium scenario: this station's AM-peak boardings | 56.67 | person trips per hour | derived |  |
| MIA-MM-21.F060 | medium scenario: this station's AM-peak alightings | 41.51 | person trips per hour | derived |  |
| MIA-MM-21.F061 | medium scenario: this station's share of network AM boardings | 0.0977 |  | derived |  |
| MIA-MM-21.F062 | medium scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 43.59, "arrivals": 31.93} | vehicle trips per hour | derived |  |
| MIA-MM-21.F063 | medium scenario: empty vehicles required in / leaving per hour | {"required_in": 11.66, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-21.F064 | medium scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 43.59, "design_cycles": 54.49, "usable_cycles_per_berth_hour": 64.0, "berths_required": 1} |  | derived |  |
| MIA-MM-21.F065 | medium scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-21.F066 | medium scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-21.F067 | medium scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.372 |  | derived |  |
| MIA-MM-21.F068 | high scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 1.5, "A03": 0.3} |  | assumption |  |
| MIA-MM-21.F069 | high scenario: network AM-peak PRT person trips | 1449.39 | person trips per hour | derived |  |
| MIA-MM-21.F070 | high scenario: this station's AM-peak boardings | 141.67 | person trips per hour | derived |  |
| MIA-MM-21.F071 | high scenario: this station's AM-peak alightings | 103.77 | person trips per hour | derived |  |
| MIA-MM-21.F072 | high scenario: this station's share of network AM boardings | 0.0977 |  | derived |  |
| MIA-MM-21.F073 | high scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 108.98, "arrivals": 79.82} | vehicle trips per hour | derived |  |
| MIA-MM-21.F074 | high scenario: empty vehicles required in / leaving per hour | {"required_in": 29.15, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-21.F075 | high scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 108.98, "design_cycles": 136.22, "usable_cycles_per_berth_hour": 64.0, "berths_required": 3} |  | derived |  |
| MIA-MM-21.F076 | high scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-21.F077 | high scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-21.F078 | high scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.929 |  | derived |  |
| MIA-MM-21.F079 | C01_average_party_size_pax_per_vehicle_trip: average occupancy of a PRT vehicle trip in the commute peak; commuters mostly travel alone | 1.3 | persons per vehicle trip | assumption |  |
| MIA-MM-21.F080 | C02_berth_cycle_s: one berth cycle = vehicle entry, alighting, boarding, exit | 45 | seconds | assumption |  |
| MIA-MM-21.F081 | C03_berth_utilization_max: design margin: a berth is sized for at most 80 % of its theoretical cycle throughput | 0.8 | ratio | assumption |  |
| MIA-MM-21.F082 | C04_within_hour_peaking_factor: peak-15-minute flow x 4 divided by the hourly flow; applied to berth sizing ONLY, never to the demand chain (it is not a second peak-hour share) | 1.25 | ratio | assumption |  |
| MIA-MM-21.F083 | C05_min_guideway_headway_s: minimum operating headway between vehicles on the guideway; lane throughput = 3600 / headway | 3.0 | seconds | assumption |  |

## Rule results (cite by rule_result_id, rule pack rules-v2.0)

| rule_result_id | status | basis | message |
|---|---|---|---|
| MIA-MM-21|low|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-21|low|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-21|low|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-21|medium|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-21|medium|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-21|medium|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-21|high|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-21|high|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-21|high|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-21|-|RC-07 | warning | scope_limitation | constructible platform space not acquired; site fit is assumed (C06) and must be confirmed by the owner |
| MIA-MM-21|-|RC-08 | pass | data_quality | half-mile population estimate has high reliability (CV <= 0.12) |
| MIA-MM-21|-|RC-09 | pass | data_quality | same-name match with the published report (owner confirmation still pending, as for every station) |
| MIA-MM-21|-|RC-11 | info | scope_limitation | the station's scenario share differs from its observed share by more than 5 points: a shape difference of an uncalibrated model against a reference, not an error to scale away |
| MIA-MM-21|-|RC-12 | pass | scope_limitation | no external connection on the official map; the exclusion of regional inflow still applies network-wide |
| MIA-MM-21|-|RC-13 | info | scope_limitation | bands are straight-line distances from a reference point that is not an entrance; no walk catchment is validated and the walk model is not built |
| NET|low|RC-01 | pass | arithmetic_identity | boardings and alightings both sum to the network AM-peak trips |
| NET|low|RC-02 | pass | arithmetic_identity | vehicle departures equal arrivals within tolerance |
| NET|low|RC-05 | pass | project_convention | network vehicle trips are below 80 % of one lane's throughput (network-level ratio only) |
| NET|medium|RC-01 | pass | arithmetic_identity | boardings and alightings both sum to the network AM-peak trips |
| NET|medium|RC-02 | pass | arithmetic_identity | vehicle departures equal arrivals within tolerance |
| NET|medium|RC-05 | pass | project_convention | network vehicle trips are below 80 % of one lane's throughput (network-level ratio only) |
| NET|high|RC-01 | pass | arithmetic_identity | boardings and alightings both sum to the network AM-peak trips |
| NET|high|RC-02 | pass | arithmetic_identity | vehicle departures equal arrivals within tolerance |
| NET|high|RC-05 | warning | project_convention | network vehicle trips are at or above 80 % of one lane's throughput; a line model is required before any capacity claim |
| NET|-|RC-06 | pass | project_convention | low adoption stays at or below the observed public-transportation commute share |

Severity: pass = the check holds; info = a limitation the reader must carry into any interpretation; the result stays usable; warning = the result may be used only with the stated caveat and the named owner confirmation; critical = the result is invalid or infeasible as computed; the AI layer must not present it as a usable configuration

## Not available

- origin-destination and hourly ridership (no calibration; peak-hour share is a census proxy)
- station entrances, crossings, vertical circulation (bands are straight-line)
- constructible platform space (site fit assumed, C06)
- supplier vehicle operating data (generic assumptions C01–C05)
- network walk model (not built)
- role classification (to be proposed here, confirmed by people)
- engineering validation (not performed)

## Forbidden

- numbers not in this brief
- external standards or codes
- density or facility counts as passengers per hour
- scaling scenarios to observed boardings
- zoning or income as exclusion
- averaging medians
- job links as trips
- calling assumptions observations
- calling results designs, forecasts or proofs
