# Station brief · Wilkie D. Ferguson, Jr. (MIA-MM-08) · kit ai-kit-v2.1 · KB kb-v2.1 · rules rules-v2.0

Use only these facts and the knowledge base kb-v2.1. Cite fact ids for site facts, rule result ids for normative statements, KB sections for guidance. Do not write numbers that are not here. Answer as the JSON object of config/ai_output_schema_v2.json.

## Facts (cite by fact_id)

| fact_id | label | value | unit | provenance | reliability / MOE |
|---|---|---|---|---|---|
| MIA-MM-08.F001 | GTFS stop ids mapped to this station | ["812", "837"] |  | observed |  |
| MIA-MM-08.F002 | existing asset and study role | metromover_station → candidate_conversion_site |  | observed |  |
| MIA-MM-08.F003 | external connections on the official map | ["Brightline"] |  | observed |  |
| MIA-MM-08.F004 | zoning at the reference point | ["T6-80-O"] |  | observed |  |
| MIA-MM-08.F005 | geometry role | GTFS reference point; not an entrance, not a platform centroid |  | observed |  |
| MIA-MM-08.F006 | half-mile disc: land area | 498.46 | acres | derived |  |
| MIA-MM-08.F007 | half-mile disc: zoned share of area | 0.909 |  | observed |  |
| MIA-MM-08.F008 | half-mile disc: largest zoning transects by share of area | [["Urban Core Zone", 0.688], ["Civic Institution Zone", 0.131], ["Urban Center Zone", 0.045]] |  | observed |  |
| MIA-MM-08.F009 | half-mile disc: population (ACS 2020–2024 period estimate) | 15245 | persons | derived | high / ±1100.34 |
| MIA-MM-08.F010 | half-mile disc: households | 8161 | households | derived | high / ±500.76 |
| MIA-MM-08.F011 | half-mile disc: workers 16+ | 9590 | workers | derived | high / ±690.9 |
| MIA-MM-08.F012 | half-mile disc: zero-vehicle household share | 26.5 | percent | derived | high / ±3.9 |
| MIA-MM-08.F013 | half-mile disc: public-transportation commute share (reference only) | 12.3 | percent | derived | medium / ±3.0 |
| MIA-MM-08.F014 | half-mile disc: worked-from-home share | 23.4 | percent | derived | high / ±3.3 |
| MIA-MM-08.F015 | half-mile disc: households below $35,000 share (project convention, not a demand indicator) | 25.1 | percent | derived | high / ±3.7 |
| MIA-MM-08.F016 | half-mile disc: population 65+ share | 9.0 | percent | derived | medium / ±1.9 |
| MIA-MM-08.F017 | half-mile disc: median household income estimate (bracket interpolation; sensitivity range, not a confidence interval) | {"value_usd": 76150, "range_usd": [75000, 100000], "open_ended": false} |  | derived |  |
| MIA-MM-08.F018 | half-mile disc: population density | 19573.8 | persons per sq mi | derived |  |
| MIA-MM-08.F019 | half-mile disc: all jobs located here (LODES 2023, C000 JT00) | 64451 | jobs | derived |  |
| MIA-MM-08.F020 | half-mile disc: primary jobs located here (JT01) | 60185 | jobs | derived |  |
| MIA-MM-08.F021 | half-mile disc: primary jobs held by residents (≈ resident workers) | 6258 | jobs | derived |  |
| MIA-MM-08.F022 | half-mile disc: jobs-to-resident-workers ratio (JT01) | 9.62 |  | derived |  |
| MIA-MM-08.F023 | half-mile disc: jobs per acre of land | 129.299 | jobs per acre | derived |  |
| MIA-MM-08.F024 | inner band (0–1/8 mi): population | 1126 | persons | derived | high / ±108.01 |
| MIA-MM-08.F025 | inner band (0–1/8 mi): all jobs located here | 1897 | jobs | derived |  |
| MIA-MM-08.F026 | half-mile disc: school facilities listed | 5 | facilities | observed |  |
| MIA-MM-08.F027 | nearest school by straight line | {"name": "Law Enforcement Officers Memorial Senior High", "distance_ft": 1096.3, "within_half_mile": true} |  | observed |  |
| MIA-MM-08.F028 | half-mile disc: clinic facilities listed | 2 | facilities | observed |  |
| MIA-MM-08.F029 | nearest clinic by straight line | {"name": "JHS - Downtown Medical Center", "distance_ft": 1289.4, "within_half_mile": true} |  | observed |  |
| MIA-MM-08.F030 | half-mile disc: grocery facilities listed | 3 | facilities | observed |  |
| MIA-MM-08.F031 | nearest grocery by straight line | {"name": "Publix Super Markets Inc.1614 1614", "distance_ft": 883.1, "within_half_mile": true} |  | observed |  |
| MIA-MM-08.F032 | half-mile disc: park facilities listed | 7 | facilities | observed |  |
| MIA-MM-08.F033 | nearest park by straight line | {"name": "Paul S. Walker Urbanscape", "distance_ft": 1761.6, "within_half_mile": true} |  | observed |  |
| MIA-MM-08.F034 | current timetable: scheduled departures per hour, 7–9 a.m. (all routes) | 48.0 | departures per hour | derived |  |
| MIA-MM-08.F035 | current timetable: implied AM-peak headway | 1.25 | minutes | derived |  |
| MIA-MM-08.F036 | current timetable: weekday scheduled departures and span | {"departures": 794, "first": "05:31", "last": "22:11"} |  | derived |  |
| MIA-MM-08.F037 | observed boardings of the current Metromover: average weekday, 10-month mean (2025-10 to 2026-07) | 1576.9 | boardings per weekday | observed |  |
| MIA-MM-08.F038 | observed boardings: share of system average weekday boardings | 0.0621 |  | derived |  |
| MIA-MM-08.F039 | observed boardings: report station name and mapping basis | {"report_station_name": "Wilkie D. Ferguson", "mapping_basis": "same_name_punctuation", "mapping_confirmed_by_owner": false} |  | observed |  |
| MIA-MM-08.F040 | observed boardings: system average weekday, 10-month mean | 25401.8 | boardings per weekday | observed |  |
| MIA-MM-08.F041 | job-link potential, home side (Σ primary links × land share; not trips, non-exclusive) | 6213 | links | derived |  |
| MIA-MM-08.F042 | job-link potential, workplace side (Σ primary links × land share; not trips, non-exclusive) | 60185 | links | derived |  |
| MIA-MM-08.F043 | network half-mile union: population (deduplicated) | 76357 | persons | derived |  |
| MIA-MM-08.F044 | network half-mile union: all jobs (deduplicated) | 180847 | jobs | derived |  |
| MIA-MM-08.F045 | network half-mile union: area | 3.57 | sq mi | derived |  |
| MIA-MM-08.F046 | low scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 0.5, "A03": 0.05} |  | assumption |  |
| MIA-MM-08.F047 | low scenario: network AM-peak PRT person trips | 144.94 | person trips per hour | derived |  |
| MIA-MM-08.F048 | low scenario: this station's AM-peak boardings | 4.54 | person trips per hour | derived |  |
| MIA-MM-08.F049 | low scenario: this station's AM-peak alightings | 3.32 | person trips per hour | derived |  |
| MIA-MM-08.F050 | low scenario: this station's share of network AM boardings | 0.0313 |  | derived |  |
| MIA-MM-08.F051 | low scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 3.49, "arrivals": 2.55} | vehicle trips per hour | derived |  |
| MIA-MM-08.F052 | low scenario: empty vehicles required in / leaving per hour | {"required_in": 0.94, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-08.F053 | low scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 3.49, "design_cycles": 4.37, "usable_cycles_per_berth_hour": 64.0, "berths_required": 1} |  | derived |  |
| MIA-MM-08.F054 | low scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-08.F055 | low scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-08.F056 | low scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.093 |  | derived |  |
| MIA-MM-08.F057 | medium scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 1.0, "A03": 0.15} |  | assumption |  |
| MIA-MM-08.F058 | medium scenario: network AM-peak PRT person trips | 579.76 | person trips per hour | derived |  |
| MIA-MM-08.F059 | medium scenario: this station's AM-peak boardings | 18.14 | person trips per hour | derived |  |
| MIA-MM-08.F060 | medium scenario: this station's AM-peak alightings | 13.29 | person trips per hour | derived |  |
| MIA-MM-08.F061 | medium scenario: this station's share of network AM boardings | 0.0313 |  | derived |  |
| MIA-MM-08.F062 | medium scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 13.95, "arrivals": 10.22} | vehicle trips per hour | derived |  |
| MIA-MM-08.F063 | medium scenario: empty vehicles required in / leaving per hour | {"required_in": 3.73, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-08.F064 | medium scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 13.95, "design_cycles": 17.44, "usable_cycles_per_berth_hour": 64.0, "berths_required": 1} |  | derived |  |
| MIA-MM-08.F065 | medium scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-08.F066 | medium scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-08.F067 | medium scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.372 |  | derived |  |
| MIA-MM-08.F068 | high scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 1.5, "A03": 0.3} |  | assumption |  |
| MIA-MM-08.F069 | high scenario: network AM-peak PRT person trips | 1449.39 | person trips per hour | derived |  |
| MIA-MM-08.F070 | high scenario: this station's AM-peak boardings | 45.35 | person trips per hour | derived |  |
| MIA-MM-08.F071 | high scenario: this station's AM-peak alightings | 33.21 | person trips per hour | derived |  |
| MIA-MM-08.F072 | high scenario: this station's share of network AM boardings | 0.0313 |  | derived |  |
| MIA-MM-08.F073 | high scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 34.88, "arrivals": 25.55} | vehicle trips per hour | derived |  |
| MIA-MM-08.F074 | high scenario: empty vehicles required in / leaving per hour | {"required_in": 9.34, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-08.F075 | high scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 34.88, "design_cycles": 43.61, "usable_cycles_per_berth_hour": 64.0, "berths_required": 1} |  | derived |  |
| MIA-MM-08.F076 | high scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-08.F077 | high scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-08.F078 | high scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.929 |  | derived |  |
| MIA-MM-08.F079 | C01_average_party_size_pax_per_vehicle_trip: average occupancy of a PRT vehicle trip in the commute peak; commuters mostly travel alone | 1.3 | persons per vehicle trip | assumption |  |
| MIA-MM-08.F080 | C02_berth_cycle_s: one berth cycle = vehicle entry, alighting, boarding, exit | 45 | seconds | assumption |  |
| MIA-MM-08.F081 | C03_berth_utilization_max: design margin: a berth is sized for at most 80 % of its theoretical cycle throughput | 0.8 | ratio | assumption |  |
| MIA-MM-08.F082 | C04_within_hour_peaking_factor: peak-15-minute flow x 4 divided by the hourly flow; applied to berth sizing ONLY, never to the demand chain (it is not a second peak-hour share) | 1.25 | ratio | assumption |  |
| MIA-MM-08.F083 | C05_min_guideway_headway_s: minimum operating headway between vehicles on the guideway; lane throughput = 3600 / headway | 3.0 | seconds | assumption |  |

## Rule results (cite by rule_result_id, rule pack rules-v2.0)

| rule_result_id | status | basis | message |
|---|---|---|---|
| MIA-MM-08|low|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-08|low|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-08|low|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-08|medium|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-08|medium|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-08|medium|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-08|high|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-08|high|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-08|high|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-08|-|RC-07 | warning | scope_limitation | constructible platform space not acquired; site fit is assumed (C06) and must be confirmed by the owner |
| MIA-MM-08|-|RC-08 | pass | data_quality | half-mile population estimate has high reliability (CV <= 0.12) |
| MIA-MM-08|-|RC-09 | warning | data_quality | published-boardings row matched by location under an older report name; owner confirmation required before use |
| MIA-MM-08|-|RC-11 | pass | scope_limitation | scenario share is within 5 points of the observed share |
| MIA-MM-08|-|RC-12 | info | scope_limitation | external connections on the official map (Brightline): transfer inflow is excluded from the scenario boardings, which understate activity here |
| MIA-MM-08|-|RC-13 | info | scope_limitation | bands are straight-line distances from a reference point that is not an entrance; no walk catchment is validated and the walk model is not built |
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
