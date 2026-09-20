# KB_V2_01 · Data semantics of the station input package

Knowledge base document 01 of 06 · version kb-v2.1 · issued 2026-09-18 · applies to the Miami demonstration (21 Metromover stations) · cite as `KB_V2_01 §DS-xx (kb-v2.1)`

This document tells the interpretation layer what each layer of the station input package means and, above all, what it does not mean. It restates the project's data-semantics rules; it introduces no threshold and no external standard.

## DS-01 Three provenance classes

Every value carries `provenance_class`: **observed** (a published record or estimate copied as is), **derived** (computed from observed values by a stated formula), **assumption** (a demonstration parameter chosen for this study). A statement about a site must rest on observed or derived facts; a statement that depends on an assumption must say so and name the assumption id.

## DS-02 Station reference point and bands

The station geometry is a GTFS reference point, not an entrance and not a platform centroid. The three bands (0–1/8, 1/8–1/4, 1/4–1/2 mile) and the half-mile cumulative disc are straight-line distances from that point. They are the analysis unit, not a walk catchment; `is_validated_walk_catchment` is false everywhere and the network walk model is not built. Do not say who "can walk to" the station.

## DS-03 Zoning is permission, not activity

Statutory zoning (Miami 21 transects and zones) describes what is permitted or constrained on land. It is not land use, not population, not jobs and not demand. No zone is excluded from analysis, and a zone's share of a band is never an allocation weight. An industrial or civic zone does not mean "no passengers".

## DS-04 Residents are five-year period estimates

Population, households, workers and their shares come from the American Community Survey 2020–2024 five-year estimates at block-group level, apportioned to the bands by land-area share. They are period estimates with a 90 % margin of error, not current population. Reliability flags: high (CV ≤ 0.12), medium (0.12–0.40), low (> 0.40). The apportionment assumes an even spread over land; that uncertainty is not inside the margin of error. Medians are never averaged; the median-income figure is an interpolated bracket estimate with a sensitivity range, not a confidence interval.

## DS-05 Jobs and job-to-home links are not trips

Job counts and origin-destination links come from LEHD LODES 8 (Florida, 2023, 2020 blocks). A job located in a band is a workplace; a link is a residence-workplace pair of one worker. Neither is a trip, a boarding or ridership. Residents of Florida who work out of state are not covered. The jobs-to-resident-workers ratio explains activity and direction; it never yields hourly flows by itself.

## DS-06 The timetable is supply, not demand

Scheduled departures per hour and implied headways come from the GTFS static feed for weekday service. They describe what the current Metromover schedules. They are not operated service, not capacity and not ridership.

## DS-07 Observed boardings are a reference, never a calibration target

Average weekday boardings per station come from the published DTPW monthly Ridership Technical Reports (ten months). They are boardings (entries) of the current Metromover, not trips, not origin-destination, not alightings, not hourly counts and not demand for a new system. They may be used to state the scale and the station-share shape of the scenarios; scaling a scenario to match them is calibration, which this study has not done.

## DS-08 Facilities are listings, not service levels

Schools, clinics, grocery stores and parks are counted from county, city and USDA listings inside the bands; distances are straight lines from the reference point. Absence means "not found in these sources", never "confirmed absent". No service-level score exists.

## DS-09 Density and accessibility maps are not persons per hour

A population or job density, or a facility count, must never be turned into passengers per hour. Peak boardings need time of day, trip purpose, mode choice, adoption and station allocation, each tagged; that chain is the scenario layer (KB_V2_02).

## DS-10 Income and land use never eliminate demand

Household income may inform affordability and price-sensitivity scenarios; it is not willingness to pay and never a demand or eligibility threshold. The low-income share uses a project convention (below $35,000), not an official definition. A zoning label never sets a population or a demand to zero.

## DS-11 Non-exclusive station profiles

Per-station bands overlap. Station profiles are non-exclusive; the network total is computed once on the union geometry. Summing station values double-counts by a known ratio (published as the duplication ratio); that ratio is not a demand multiplier.

## DS-12 What is not in the package

Not acquired: origin-destination and hourly ridership, station entrances and vertical circulation, constructible platform space, supplier vehicle operating data, a validated walk catchment, a measured activity or ridership heat map. Roads, rail, the guideway, land use and parcels are available as features for the reading agents (KB_V2_05); their roles are read by the agents and confirmed by people, not recorded as facts. Each is listed with its status; "not acquired" is never read as zero.
