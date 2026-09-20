# KB_V2_05 · How the reading agents read GIS features

Knowledge base document 05 of 06 · version kb-v2.1 · issued 2026-09-20 · cite as `KB_V2_05 §GR-xx (kb-v2.1)`

The reading agents receive feature tables, not conclusions: road groups, rail, the existing guideway, zoning polygons, land-use classes, parcels, heat-proxy cells and block groups, each with an object id. This document says how to read them. Code has only clipped, measured, joined and counted; interpretation is the agents' work, and every interpretation is checked for the ids it cites and handed to people for confirmation.

## GR-01 The standing of spatial evidence

The heat proxy and zoning are read together, and both are auxiliary evidence. Neither decides demand, a station role or a configuration. They support, qualify or question what the residents, jobs, observed boardings and scenario results show. A reading that rests on heat or zoning alone must say so and carry a low evidence level.

## GR-02 Roles an object may play

Each feature may be read as one of: `origin` (where trips plausibly start: residential blocks, residential parcels), `destination` (where trips plausibly end: offices, retail, civic, institutional, event and visitor places), `facility_to_convert` (the existing Metromover station and guideway), `obstacle` (something that cuts walking access or constrains a station: a motorway, a rail corridor at grade, a river or bay, a fenced utility site), `candidate_site` (land that could physically host a platform module, subject to every confirmation in KB_V2_04), `context` (relevant background that is none of the above), `not_relevant`. A role is a hypothesis with an evidence level (high / medium / low), never a decision. One object may be an obstacle for walking and a connection for transfers; say both.

## GR-03 Reading roads

Road classes are OpenStreetMap highway classes (KB_V2_06 §LG-04). Motorways, trunk roads and their links are obstacle candidates for walking; bridges mark a water or rail crossing and are the few places a barrier can be crossed. Primary and secondary streets are frontage and crossing context, not barriers by themselves. Distances are straight lines from the reference point, which is not an entrance. Do not describe a walking route, a crossing time or a level of service: no walk model exists.

## GR-04 Reading rail and the guideway

The county Railroads layer has no attributes and draws the Metromover guideway and the Metrorail line as rail. The tables already separate three things (KB_V2_06 §LG-05): the existing Metromover guideway, which is the facility to convert and never an obstacle to itself; the Metrorail line, which is a transfer connection and may also be a barrier; and other railroad trackage, which is an obstacle candidate. Transfer inflow from Metrorail is excluded from the scenarios (KB_V2_04 §OI-07).

## GR-05 Reading zoning

Zoning is permission, not activity (KB_V2_01 §DS-03). Read the transect description, the height figure and the letters the layer carries (KB_V2_06 §LG-01, §LG-02). A high-intensity urban core transect says that dense development is permitted, not that it exists or generates trips. A civic space or civic institution zone near the station signals parks, plazas and public buildings: visitor and event activity that the commute-based scenarios do not contain. Never use a zone to exclude people or to set demand to zero.

## GR-06 Reading land use and parcels

The county land-use layer describes existing use by class; parcels carry the property appraiser's land-use description, lot size and year built, and no owner or address information. Use them to say what is actually on the ground near the station: vacant and parking parcels, government-owned land, institutions, residential and commercial stock. A parcel that is vacant or a parking lot and at least as large as the smallest platform module footprint may be read as a `candidate_site`, always with the caveats that constructible space, ownership, access, structure and approvals are unknown (KB_V2_04 §OI-01). Notice and report what looks wrong in the data: a tax classification that does not match the place, attribute-less slivers, a reference folio with no lot size, a name that contradicts a category.

## GR-07 Reading the heat proxy

The heat layer is an activity-density proxy: 2020 Census residents plus 2023 LODES jobs per acre of land in 500 ft cells, ranked across the network; "hot" means the network top quintile. It is not a measured heat map, not ridership and not persons per hour. Values are spread evenly over each census block's land, so a park or plaza inside a block inherits the block's density. The residents come from the 2020 Census, a different source and year than the ACS estimates in the block-group table; never add or compare them as if they were the same thing.

## GR-08 Reading heat and zoning together

For every cluster of hot cells, say what zoning transect and what existing land use it sits on, and whether the jobs share says work or home. Hot cells on an urban core or urban centre transect with office or retail land use support a destination reading; hot cells on residential land use support an origin reading; a hot cell on a civic space, a park, water edge or parking land use is probably an artefact of the even spread and must be flagged, not interpreted. The joint reading is auxiliary (§GR-01).

## GR-09 Screening heat for service relevance

Activity is not the same as passengers for this station. Flag, and never delete, hot cells that touch a motorway, trunk road or rail corridor, or sit on industrial, utility, port or transport land use: they may hold freight, through traffic or activity that cannot reach the station on foot. Use the wording "possible non-passenger or through activity; needs checking". Workers in industrial and logistics areas are passengers like anyone else (KB_V2_01 §DS-10).

## GR-10 What the picture is for

The heat image shows the same cells as the table, with zoning outlines, major roads, the guideway, other rail and the distance rings. Use it for pattern: clusters, corridors, edges, which side of a barrier the activity lies on. Anything seen only in the picture and not supported by a table row goes under `visual_observations_unverified` and must not carry a number.

## GR-11 Citation duty and limits

Cite an object id for every feature statement and a summary fact id (`.Gnnn`) for every number; write no number that is not in the input. Parcels are cited by object id; do not reproduce long lists of folio numbers. If the tables cannot answer something, say so under `not_determinable`. Never state an owner, an address, a walking time, a capacity, a forecast or a design.
