# Station brief · Tenth Street Promenade (MIA-MM-19) · kit ai-kit-v2.1 · KB kb-v2.1 · rules rules-v2.0

Use only these facts and the knowledge base kb-v2.1. Cite fact ids for site facts, rule result ids for normative statements, KB sections for guidance. Do not write numbers that are not here. Answer as the JSON object of config/ai_output_schema_v2.json.

## Facts (cite by fact_id)

| fact_id | label | value | unit | provenance | reliability / MOE |
|---|---|---|---|---|---|
| MIA-MM-19.F001 | GTFS stop ids mapped to this station | ["803", "819"] |  | observed |  |
| MIA-MM-19.F002 | existing asset and study role | metromover_station → candidate_conversion_site |  | observed |  |
| MIA-MM-19.F003 | external connections on the official map | none |  | observed |  |
| MIA-MM-19.F004 | zoning at the reference point | ["T6-48A-O"] |  | observed |  |
| MIA-MM-19.F005 | geometry role | GTFS reference point; not an entrance, not a platform centroid |  | observed |  |
| MIA-MM-19.F006 | half-mile disc: land area | 405.38 | acres | derived |  |
| MIA-MM-19.F007 | half-mile disc: zoned share of area | 0.783 |  | observed |  |
| MIA-MM-19.F008 | half-mile disc: largest zoning transects by share of area | [["Urban Core Zone", 0.7], ["Civic Institution Zone", 0.021], ["Natural Zone", 0.019]] |  | observed |  |
| MIA-MM-19.F009 | half-mile disc: population (ACS 2020–2024 period estimate) | 32551 | persons | derived | high / ±2220.01 |
| MIA-MM-19.F010 | half-mile disc: households | 18413 | households | derived | high / ±1206.79 |
| MIA-MM-19.F011 | half-mile disc: workers 16+ | 22711 | workers | derived | high / ±1949.09 |
| MIA-MM-19.F012 | half-mile disc: zero-vehicle household share | 15.4 | percent | derived | high / ±2.5 |
| MIA-MM-19.F013 | half-mile disc: public-transportation commute share (reference only) | 4.9 | percent | derived | medium / ±1.4 |
| MIA-MM-19.F014 | half-mile disc: worked-from-home share | 30.8 | percent | derived | high / ±2.8 |
| MIA-MM-19.F015 | half-mile disc: households below $35,000 share (project convention, not a demand indicator) | 15.1 | percent | derived | high / ±2.8 |
| MIA-MM-19.F016 | half-mile disc: population 65+ share | 8.4 | percent | derived | medium / ±1.7 |
| MIA-MM-19.F017 | half-mile disc: median household income estimate (bracket interpolation; sensitivity range, not a confidence interval) | {"value_usd": 119703, "range_usd": [100000, 125000], "open_ended": false} |  | derived |  |
| MIA-MM-19.F018 | half-mile disc: population density | 51390.2 | persons per sq mi | derived |  |
| MIA-MM-19.F019 | half-mile disc: all jobs located here (LODES 2023, C000 JT00) | 41700 | jobs | derived |  |
| MIA-MM-19.F020 | half-mile disc: primary jobs located here (JT01) | 39192 | jobs | derived |  |
| MIA-MM-19.F021 | half-mile disc: primary jobs held by residents (≈ resident workers) | 14759 | jobs | derived |  |
| MIA-MM-19.F022 | half-mile disc: jobs-to-resident-workers ratio (JT01) | 2.66 |  | derived |  |
| MIA-MM-19.F023 | half-mile disc: jobs per acre of land | 102.866 | jobs per acre | derived |  |
| MIA-MM-19.F024 | inner band (0–1/8 mi): population | 4714 | persons | derived | high / ±730.63 |
| MIA-MM-19.F025 | inner band (0–1/8 mi): all jobs located here | 4722 | jobs | derived |  |
| MIA-MM-19.F026 | half-mile disc: school facilities listed | 7 | facilities | observed |  |
| MIA-MM-19.F027 | nearest school by straight line | {"name": "WorldEd International School", "distance_ft": 503.3, "within_half_mile": true} |  | observed |  |
| MIA-MM-19.F028 | half-mile disc: clinic facilities listed | 0 | facilities | observed |  |
| MIA-MM-19.F029 | nearest clinic by straight line | {"name": "JHS - Downtown Medical Center", "distance_ft": 4412.4, "within_half_mile": false} |  | observed |  |
| MIA-MM-19.F030 | half-mile disc: grocery facilities listed | 3 | facilities | observed |  |
| MIA-MM-19.F031 | nearest grocery by straight line | {"name": "PUBLIX 1009", "distance_ft": 966.9, "within_half_mile": true} |  | observed |  |
| MIA-MM-19.F032 | half-mile disc: park facilities listed | 6 | facilities | observed |  |
| MIA-MM-19.F033 | nearest park by straight line | {"name": "Allen Morris Brickell Plaza", "distance_ft": 112.1, "within_half_mile": true} |  | observed |  |
| MIA-MM-19.F034 | current timetable: scheduled departures per hour, 7–9 a.m. (all routes) | 24.0 | departures per hour | derived |  |
| MIA-MM-19.F035 | current timetable: implied AM-peak headway | 2.5 | minutes | derived |  |
| MIA-MM-19.F036 | current timetable: weekday scheduled departures and span | {"departures": 398, "first": "05:32", "last": "22:06"} |  | derived |  |
| MIA-MM-19.F037 | observed boardings of the current Metromover: average weekday, 10-month mean (2025-10 to 2026-07) | 886.4 | boardings per weekday | observed |  |
| MIA-MM-19.F038 | observed boardings: share of system average weekday boardings | 0.0349 |  | derived |  |
| MIA-MM-19.F039 | observed boardings: report station name and mapping basis | {"report_station_name": "Tenth Street", "mapping_basis": "same_name_extended", "mapping_confirmed_by_owner": false} |  | observed |  |
| MIA-MM-19.F040 | observed boardings: system average weekday, 10-month mean | 25401.8 | boardings per weekday | observed |  |
| MIA-MM-19.F041 | job-link potential, home side (Σ primary links × land share; not trips, non-exclusive) | 14576 | links | derived |  |
| MIA-MM-19.F042 | job-link potential, workplace side (Σ primary links × land share; not trips, non-exclusive) | 39192 | links | derived |  |
| MIA-MM-19.F043 | network half-mile union: population (deduplicated) | 76357 | persons | derived |  |
| MIA-MM-19.F044 | network half-mile union: all jobs (deduplicated) | 180847 | jobs | derived |  |
| MIA-MM-19.F045 | network half-mile union: area | 3.57 | sq mi | derived |  |
| MIA-MM-19.F046 | low scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 0.5, "A03": 0.05} |  | assumption |  |
| MIA-MM-19.F047 | low scenario: network AM-peak PRT person trips | 144.94 | person trips per hour | derived |  |
| MIA-MM-19.F048 | low scenario: this station's AM-peak boardings | 13.68 | person trips per hour | derived |  |
| MIA-MM-19.F049 | low scenario: this station's AM-peak alightings | 13.36 | person trips per hour | derived |  |
| MIA-MM-19.F050 | low scenario: this station's share of network AM boardings | 0.0944 |  | derived |  |
| MIA-MM-19.F051 | low scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 10.52, "arrivals": 10.28} | vehicle trips per hour | derived |  |
| MIA-MM-19.F052 | low scenario: empty vehicles required in / leaving per hour | {"required_in": 0.25, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-19.F053 | low scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 10.52, "design_cycles": 13.15, "usable_cycles_per_berth_hour": 64.0, "berths_required": 1} |  | derived |  |
| MIA-MM-19.F054 | low scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-19.F055 | low scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-19.F056 | low scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.093 |  | derived |  |
| MIA-MM-19.F057 | medium scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 1.0, "A03": 0.15} |  | assumption |  |
| MIA-MM-19.F058 | medium scenario: network AM-peak PRT person trips | 579.76 | person trips per hour | derived |  |
| MIA-MM-19.F059 | medium scenario: this station's AM-peak boardings | 54.72 | person trips per hour | derived |  |
| MIA-MM-19.F060 | medium scenario: this station's AM-peak alightings | 53.44 | person trips per hour | derived |  |
| MIA-MM-19.F061 | medium scenario: this station's share of network AM boardings | 0.0944 |  | derived |  |
| MIA-MM-19.F062 | medium scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 42.09, "arrivals": 41.11} | vehicle trips per hour | derived |  |
| MIA-MM-19.F063 | medium scenario: empty vehicles required in / leaving per hour | {"required_in": 0.98, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-19.F064 | medium scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 42.09, "design_cycles": 52.62, "usable_cycles_per_berth_hour": 64.0, "berths_required": 1} |  | derived |  |
| MIA-MM-19.F065 | medium scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-19.F066 | medium scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-19.F067 | medium scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.372 |  | derived |  |
| MIA-MM-19.F068 | high scenario: assumptions A01 attendance / A02 non-commute per commute / A03 adoption | {"A01": 0.85, "A02": 1.5, "A03": 0.3} |  | assumption |  |
| MIA-MM-19.F069 | high scenario: network AM-peak PRT person trips | 1449.39 | person trips per hour | derived |  |
| MIA-MM-19.F070 | high scenario: this station's AM-peak boardings | 136.79 | person trips per hour | derived |  |
| MIA-MM-19.F071 | high scenario: this station's AM-peak alightings | 133.59 | person trips per hour | derived |  |
| MIA-MM-19.F072 | high scenario: this station's share of network AM boardings | 0.0944 |  | derived |  |
| MIA-MM-19.F073 | high scenario: vehicle departures / arrivals per hour (person trips ÷ C01) | {"departures": 105.22, "arrivals": 102.76} | vehicle trips per hour | derived |  |
| MIA-MM-19.F074 | high scenario: empty vehicles required in / leaving per hour | {"required_in": 2.46, "leaving": 0.0} | vehicles per hour | derived |  |
| MIA-MM-19.F075 | high scenario: berth cycles → design cycles (× C04) → berths required | {"berth_cycles": 105.22, "design_cycles": 131.53, "usable_cycles_per_berth_hour": 64.0, "berths_required": 3} |  | derived |  |
| MIA-MM-19.F076 | high scenario: platform module and footprint | {"module": "M1_double_sided_6_berth", "berths_provided": 6, "footprint_ft2": 3908, "fits_single_module": true} |  | observed |  |
| MIA-MM-19.F077 | high scenario: site fit status | assumed_sufficient |  | assumption |  |
| MIA-MM-19.F078 | high scenario: network vehicle trips ÷ one lane's throughput at minimum headway | 0.929 |  | derived |  |
| MIA-MM-19.F079 | C01_average_party_size_pax_per_vehicle_trip: average occupancy of a PRT vehicle trip in the commute peak; commuters mostly travel alone | 1.3 | persons per vehicle trip | assumption |  |
| MIA-MM-19.F080 | C02_berth_cycle_s: one berth cycle = vehicle entry, alighting, boarding, exit | 45 | seconds | assumption |  |
| MIA-MM-19.F081 | C03_berth_utilization_max: design margin: a berth is sized for at most 80 % of its theoretical cycle throughput | 0.8 | ratio | assumption |  |
| MIA-MM-19.F082 | C04_within_hour_peaking_factor: peak-15-minute flow x 4 divided by the hourly flow; applied to berth sizing ONLY, never to the demand chain (it is not a second peak-hour share) | 1.25 | ratio | assumption |  |
| MIA-MM-19.F083 | C05_min_guideway_headway_s: minimum operating headway between vehicles on the guideway; lane throughput = 3600 / headway | 3.0 | seconds | assumption |  |

## Rule results (cite by rule_result_id, rule pack rules-v2.0)

| rule_result_id | status | basis | message |
|---|---|---|---|
| MIA-MM-19|low|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-19|low|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-19|low|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-19|medium|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-19|medium|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-19|medium|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-19|high|RC-03 | pass | arithmetic_identity | published berth arithmetic reproduces |
| MIA-MM-19|high|RC-04 | pass | project_convention | requirement fits one drawn module |
| MIA-MM-19|high|RC-10 | pass | project_convention | departures and arrivals are within the balance convention |
| MIA-MM-19|-|RC-07 | warning | scope_limitation | constructible platform space not acquired; site fit is assumed (C06) and must be confirmed by the owner |
| MIA-MM-19|-|RC-08 | pass | data_quality | half-mile population estimate has high reliability (CV <= 0.12) |
| MIA-MM-19|-|RC-09 | warning | data_quality | published-boardings row matched by location under an older report name; owner confirmation required before use |
| MIA-MM-19|-|RC-11 | info | scope_limitation | the station's scenario share differs from its observed share by more than 5 points: a shape difference of an uncalibrated model against a reference, not an error to scale away |
| MIA-MM-19|-|RC-12 | pass | scope_limitation | no external connection on the official map; the exclusion of regional inflow still applies network-wide |
| MIA-MM-19|-|RC-13 | info | scope_limitation | bands are straight-line distances from a reference point that is not an entrance; no walk catchment is validated and the walk model is not built |
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
