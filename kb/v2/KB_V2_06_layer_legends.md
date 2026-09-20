# KB_V2_06 · Legends of the GIS layers

Knowledge base document 06 of 06 · version kb-v2.1 · issued 2026-09-20 · generated from the archived layers by `scripts/build_miami_kb_legends.py` · cite as `KB_V2_06 §LG-xx (kb-v2.1)`

Every entry below is an attribute value carried by a source layer inside the Miami study window, or a rule recorded in `config/gis_objects_v1.json`. Where a source does not define a symbol, this document says so; the reading agents must then treat the symbol as a label and write "not covered by knowledge base" if its meaning matters.

## LG-01 Zoning transects (City of Miami, Miami 21 layer)

The layer describes itself as the spatial representation of the transect zones of the Miami 21 form-based code, areas of varying density whose character is set by requirements for use, height, setback and building form. Transect codes and the descriptions the layer carries:

| Transect | Description in the layer | Polygons in the window |
|---|---|---|
| T6 | Urban Core Zone | 98 |
| T5 | Urban Center Zone | 38 |
| CS | Civic Space Zone | 26 |
| CI | Civic Institution Zone | 24 |
| T4 | General Urban Zone | 15 |
| D1 | Work Place District Zone | 12 |
| T3 | Sub-Urban Zone | 11 |
| D2 | Industrial District Zone | 4 |
| T1 | Natural Zone | 3 |
| D3 | Waterfront Industrial District Zone | 3 |
| CI-HD | Civic Institution - Health District Zone | 1 |

## LG-02 Zone names, height figure, intensity letter, FLR letter

Zone names present in the window: CI, CI-HD, CS, D1, D2, D3, T1, T3-O, T3-R, T4-L, T4-O, T4-R, T5-L, T5-O, T5-R, T6-12-O, T6-24A-O, T6-24A-R, T6-24B-O, T6-36A-L, T6-36A-O, T6-36B-L, T6-36B-O, T6-48A-O, T6-48B-O, T6-60A-O, T6-8-L, T6-8-O, T6-8-R, T6-80-O, T6-8A-O, T6-8B-O.

A zone name combines the transect, a height figure and letters, all of which the layer also carries as separate fields:

- `Bldg_Heigh` values present: 8, 12, 24, 36, 48, 60, 80. The layer does not state the unit of this figure; treat it as the height class named in the zone and do not convert it.
- `Intensity` letters present: L, O, R. The layer carries the letters without defining them, and their definition has not been verified against the code text for this study. Treat them as labels.
- `FLR` letters present: A, B. The official Miami 21 glossary defines Floor Lot Ratio as a multiplier on lot area that sets the maximum building area allowed above grade; what the letters A and B stand for is not defined in the layer.

Zoning is permission, not activity (KB_V2_01 §DS-03): none of these figures says what is built or who travels.

## LG-03 Existing land-use classes (Miami-Dade County land-use layer)

Class codes and the descriptions the layer carries, for classes present in the study window:

| LU | Description in the layer | Polygons |
|---|---|---|
| 804 | Vacant, Non-Protected, Privately-Owned. | 370 |
| 30 | Multi-Family, Low-Density (Under 25 DU/Gross Acre). | 348 |
| 110 | Sales and Services (Wholesale facilities, Spot commercial, strip commercial, neighborhood shopping centers/plazas). Excludes office facilities. | 281 |
| 10 | Single-Family, Med.-Density (2-5 DU/Gross Acre). | 263 |
| 35 | Multi-Family, High Density (Over 25 DU/Gross Acre). | 201 |
| 20 | Two-Family (Duplexes). | 183 |
| 320 | Industrial Intensive, heavy-light manufacturing, and warehousing-storage type of use | 147 |
| 645 | Highways and Expressways right-of-way and associated open and landscaped areas excluding paved expressways and ramps. | 143 |
| 113 | Office Building. | 121 |
| 640 | Streets and Roads, except Expressways and Private Drives. | 117 |
| 11 | Single-Family, High Density (Over 5 DU/Gross Acre, other than Townhouses, Duplexes and Mobile Homes). | 112 |
| 646 | Street right-of-way and entrance features both public and private, and utility easements. | 104 |
| 517 | Private Recreational Facilities Associated with private Residential Developments, except marinas/yacht basins, includes landscape and open spaces associated to residential, commercial and office developments. | 102 |
| 650 | Parking - Public and Private Garages and Lots. | 92 |
| 620 | Railroads - Terminals, Trackage, and Yards. | 76 |
| 801 | Vacant Government owned or controlled. | 71 |
| 180 | Residential predominantly (condominium/ rental apartments with lower floors Office and/or Retail.  High density > 15 dwelling units per ac, multi-story buildings  (Generally more than 5 stories). | 63 |
| 510 | Municipal Operated Parks | 60 |
| 450 | Governmental/Public Administration (Other than Military or Penal). | 59 |
| 440 | Houses of Worship and Religious, and associated uses (parking, retreat houses, residencies, childcare, etc.). | 51 |
| 200 | TRANSIENT-RESIDENTIAL (HOTEL-MOTEL) | 45 |
| 805 | Major Approved Projects. | 37 |
| 527 | Marina complexes (docks, piers, moorings, ramps, boat lifts and hoists, boat maintenance and repair, boat storage, fueling operations) for recreational craft located within Parks and Preserves and other small craft harbor complexes used primarily for recr | 34 |
| 641 | Paved Highways, Expressways and Ramps. | 25 |
| 932 | Coastal Water (Bay only) within the Biscayne Bay Urban Aquatic Preserve (Excluding Ocean Waters). | 22 |
| 412 | Private Schools, Including Playgrounds (K-12, Vocational Ed., Day Care and Child Nurseries). | 20 |
| 910 | Rivers and Canals.(Water) | 20 |
| 170 | Office and/or Business and other services (ground level) / Residential (upper levels). Low-density < 15 dwellings per acre or 4 floors. | 17 |
| 414 | Colleges and Universities, Including Research Centers, Public and Private. | 17 |
| 630 | Electric Power (Generator and Substation, and Service Yards). | 16 |
| 12 | Townhouses. | 15 |
| 430 | Hospitals, clinics, medical offices and/or dental facilities | 15 |
| 112 | Marine commercial (includes private commercial [non-recreational] marinas and repair yards on public or private land). | 13 |
| 411 | Public Schools, Including Playgrounds (K-12, Vocational Ed., Day Care and Child Nurseries). | 13 |
| 642 | Private Drives. | 13 |
| 339 | Industrial Extensive | 12 |
| 420 | Cultural (auditoriums, convention centers, exhibition centers, museums, art galleries, libraries). | 12 |
| 69 | Residential MF-- government-owned or government subsidized multi-family residential or elderly housing | 12 |
| 435 | Nursing homes, Assisted living facilities, and Adult congregate living quarters | 9 |
| 470 | Social Services, and Charitable institutions (Shrines, Elks, Moose, Lions Club). | 9 |
| 65 | Residential SF--government-owned or government subsidized multi-family residential or elderly housing | 9 |
| 920 | Other inland water bodies (Lakes, Ponds, Watercourses other than rivers and canals), including road borrow pits. | 9 |
| 160 | Office/Business/Hotel/Residential. Substantial components of each use present,    Treated as any combination of the mentioned uses with a hotel as part of development. | 8 |
| 13 | Single-Family, Low-Density (Under 2 DU/Gross Acre). | 7 |
| 612 | Ocean Ship Terminals and Port Facilities, Bay and River Based. | 7 |
| 633 | Communications (Radio, TV, Cable, and Phone), excluding Antenna Arrays. | 7 |
| 115 | Sports Stadiums, Arenas, and Tracks. | 4 |
| 460 | Penal and Correctional. | 4 |
| 310 | Extraction, Excavation, Quarrying, Rock-Mining, excluding the resulting water body (see 917). | 3 |
| 670 | Road Maintenance and Storage Yards, and Motor Pools. | 3 |
| 935 | Remaining Bay Waters (Excluding Ocean). | 3 |
| 613 | Bus/Truck/Freight Forwarding Terminals. | 2 |
| 342 | Industrial Intensive, Office type of use | 1 |
| 518 | Private Recreational Camps/Areas not associated with private Residential Developments (Boy Scout/Girl Scout Camps, Private Recreational Camps).  Includes private tennis courts and pools that are part of the recreational complex. | 1 |
| 540 | Cemeteries. | 1 |
| 636 | Sewerage Treatment Plants. | 1 |

## LG-04 Road classes (OpenStreetMap `highway` tag)

Paraphrased from the OpenStreetMap wiki page Key:highway; consult the wiki for the exact definitions. Classes express the importance of a road in the network, not its width or traffic:

- `motorway`: controlled-access divided highway; `motorway_link`: its ramps and slip roads.
- `trunk`: the most important roads that are not motorways; `trunk_link`: their ramps.
- `primary`, `secondary`, `tertiary`: roads of decreasing importance linking districts and neighbourhoods; `*_link`: their connecting ramps.
- `residential`, `unclassified`, `living_street`: local access streets.
- `pedestrian`: streets or plazas mainly for walking; `busway`: a road for buses only.
- `bridge` and `tunnel` flags mark ways tagged as such in OpenStreetMap; `lanes_max` is the largest lanes tag among the grouped ways and is often missing.

Listed as objects: motorway, motorway_link, trunk, trunk_link, primary, primary_link, secondary, secondary_link, tertiary, tertiary_link, residential, unclassified, living_street, pedestrian, busway. Reported only as summary lengths: footway, path, steps, cycleway, service, corridor, track, construction, proposed. ways grouped by (name or ref, highway class) inside the half-mile disc; minor classes (rank >= 12) listed only when at least 330 ft lie inside the disc.

## LG-05 Rail layers

the county Railroads layer draws the Metromover guideway and the Metrorail line as rail without any attribute; trackage within 20 m of the GTFS Metromover shapes is reported as the existing guideway (facility to convert), trackage within 20 m of the Metrorail line as Metrorail, and only the remainder as other railroad trackage. read as it comes, about three quarters of the 'railroad' length in the study window would be the transit lines themselves.

## LG-06 Parcel land-use descriptions and groups (Miami-Dade County parcel layer)

The parcel layer carries a four-digit land-use code and a description of the form `CLASS : SUBCLASS`. This study groups parcels by the class text as it appears in the layer. groups are defined on the description strings carried by the county layer itself (the text before ' : ' in DOR_DESC); a prefix that is not listed falls into 'other' and is reported; 'agricultural_classification' is a tax classification that appears on a few downtown parcels and is kept as the source gives it.

| Class text in the layer | Group in this study | Parcels in the window |
|---|---|---|
| RESIDENTIAL - SINGLE FAMILY | residential | 1112 |
| VACANT LAND - COMMERCIAL | vacant | 1027 |
| MULTIFAMILY 2-9 UNITS | residential | 725 |
| VACANT GOVERNMENTAL | vacant | 368 |
| MULTIFAMILY 10 UNITS PLUS | residential | 325 |
| REFERENCE FOLIO | reference_folio | 321 |
| STORE | commercial | 283 |
| PARKING LOT/MOBILE HOME PARK | parking | 159 |
| RESIDENTIAL - TOTAL VALUE | residential | 157 |
| OFFICE BUILDING - MULTISTORY | commercial | 135 |
| VACANT LAND - INDUSTRIAL | vacant | 128 |
| VACANT RESIDENTIAL | vacant | 127 |
| WAREHOUSE TERMINAL OR STG | industrial | 119 |
| MIXED USE-STORE/RESIDENTIAL | mixed_use | 103 |
| LIGHT MANUFACTURING | industrial | 81 |
| COUNTY | governmental | 70 |
| AUTOMOTIVE OR MARINE | commercial | 53 |
| PVT PARK -REC AREA -ROADWAY | common_area | 49 |
| RESTAURANT OR CAFETERIA | commercial | 47 |
| MUNICIPAL | governmental | 44 |
| HOTEL OR MOTEL | commercial | 43 |
| RELIGIOUS - EXEMPT | institutional | 32 |
| PROFESSIONAL SERVICE BLDG | commercial | 26 |
| LEASEHOLD INTEREST | common_area | 25 |
| CENTRALLY ASSESSED | utility_or_rail | 20 |
| OFFICE BUILDING - ONE STORY | commercial | 20 |
| BOARD OF PUBLIC INSTRUCTION | governmental | 20 |
| VACANT LAND - INSTITUTIONAL | vacant | 19 |
| UTILITY | utility_or_rail | 17 |
| EDUCATIONAL/SCIENTIFIC - EX | institutional | 14 |
| WHOLESALE OUTLET | commercial | 11 |
| SERVICE STATION | commercial | 9 |
| TOURIST ATTRACTION/EXHIBIT | commercial | 8 |
| VEG CROPLANDS MIXED/ROTATED | agricultural_classification | 8 |
| FEDERAL | governmental | 8 |
| COMMUNITY SHOPPING CENTER | commercial | 7 |
| NIGHTCLUB LOUNGE OR BAR | commercial | 7 |
| CHARITABLE - EXEMPT | institutional | 7 |
| STATE | governmental | 6 |
| COMMON AREAS | common_area | 6 |
| BENEVOLENT - EXEMPT | institutional | 5 |
| REGIONAL SHOPPING CENTER | commercial | 5 |
| AIRPORT/TERMINAL OR MARINA | commercial | 5 |
| SUPERMARKET | commercial | 5 |
| HEAVY INDUSTRIAL | industrial | 5 |
| MINERAL PROCESSING | industrial | 5 |
| DRIVE-IN RESTAURANT | commercial | 4 |
| FOOD PROCESSING | industrial | 4 |
| REPAIR SHOP/NON AUTOMOTIVE | commercial | 4 |
| ENCLOSED RECEATIONAL ARENA | commercial | 4 |
| OPEN STORAGE | industrial | 3 |
| HOME FOR THE AGED | institutional | 3 |
| ENCLOSED THEATER/AUDITORIUM | commercial | 2 |
| UNIVERSITY OR COLLEGE | institutional | 2 |
| DEPARTMENT STORE | commercial | 2 |
| MISCELLANEOUS - RESIDENTIAL | residential | 2 |
| FINANCIAL INSTITUTION | commercial | 2 |
| PACKING PLANT | industrial | 2 |
| HOSPITAL - GOVERNMENTAL | governmental | 2 |
| LITERARY - EXEMPT | institutional | 1 |
| PARKING LOT/COMMERCIAL CONDO | parking | 1 |
| CONTAINER NURSERY ABOVE-GR | agricultural_classification | 1 |
| CROPLAND - SOIL CLASS III | agricultural_classification | 1 |
| LEASEHOLD INTEREST: LEASEHOLD INTEREST | common_area | 1 |
| RIVER LAKE OR SUBMERGED LAND | water_or_submerged | 1 |
| RETIREMENT HOME | residential | 1 |

Parcels without any attribute in the source: 16; they are counted and never read as parcels with a use. A parcel is listed individually when it lies in the inner band (within 660 ft), or its land-use group is one of listed_groups, or its lot is at least 20,000 sq ft; all other parcels appear only in the per-group summary; rows are ordered by distance and capped at max_rows.

Privacy: no owner, mailing, site-address or legal-description field is requested or stored.

## LG-07 Heat proxy

Metric: activity density = (2020 Census residents + 2023 LODES jobs located in the cell) per acre of land in the cell. Cell size 500 ft. PROXY built from public counts; not a measured activity or ridership heat map. Residents: 2020 Census P.L. 94-171 block counts (P1_001N), carry disclosure-avoidance noise; a different source and year than the ACS 2020-2024 estimates of the demography layer and never mixed with them. Jobs: LEHD LODES 8 Florida 2023 WAC C000 JT00 by block (jobs package). Apportionment: block value x (block land inside the cell / block land), water erased; the same land-share convention as the other layers. Hot: network top quintile of activity density among cells with land. Known limitation: block values are spread evenly over the block's land; a park, plaza or parking structure inside a block inherits the block's density, so a hot cell must be read together with its zoning and land use before it is interpreted.

## LG-08 Role hints are not in the agents' input

An independent, rule-based reading used only to measure how often the agents agree with simple rules and to queue disagreements for human review; hints never override an agent and never decide anything.
