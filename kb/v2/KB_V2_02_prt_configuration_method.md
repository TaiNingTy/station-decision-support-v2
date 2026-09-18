# KB_V2_02 · Scenario chain and PRT configuration method

Knowledge base document 02 of 04 · version kb-v2.0 · issued 2026-09-18 · cite as `KB_V2_02 §CM-xx (kb-v2.0)`

This document explains how the scenario and configuration numbers in a station brief were produced, so that the interpretation layer can explain them faithfully. The numbers themselves live in the brief with fact ids; the thresholds live in the rule pack (rules-v2.0). Nothing here replaces either.

## CM-01 The scenario chain (network level)

1. Internal commute links: primary-job links whose residence and workplace both lie inside the network's half-mile union, counted for the covered fraction of each block (P01, derived from LODES).
2. Weekday commute person trips, AM direction = P01 × (1 − work-from-home share P02) × attendance rate A01.
3. All-purpose trips = step 2 × (1 + non-commute trips per commute trip A02).
4. Peak-hour trips = step 3 × peak-hour share P05 (the 8:00–8:59 a.m. window from ACS departure times, an observed proxy for arrival times, assumption A07).
5. PRT peak-hour person trips = step 4 × adoption share A03.
6. Station boardings and alightings: each link is split across candidate stations by land share (A04); PM mirrors AM (A05); conservation is checked.

Low / medium / high differ only in A02 and A03. The chain excludes regional inflow, hub transfers, links with one end outside the network, out-of-state workers, visitors and non-resident non-work trips. It is an uncalibrated order of magnitude, not a forecast (DS-07).

## CM-02 Parameters and their classes

P01, P02, P05 are derived from the census layers and carry their sources. A01–A07 are demonstration assumptions; A03 (adoption) is the most consequential and its low value is kept at or below the observed transit commute share (rule RC-06). When explaining a result, name the assumption that drives it.

## CM-03 From person trips to vehicle trips

Vehicle trips = person trips ÷ average party size C01 (1.3 persons per vehicle trip, assumption). The vehicle's maximum capacity (up to 6) is never the load; using it would understate vehicle movements by a factor of four or more.

## CM-04 From vehicle trips to berths

Berth cycles per hour = max(vehicle departures, vehicle arrivals). Design cycles = berth cycles × within-hour peaking factor C04 (applies to berths only, never back to demand). Usable cycles per berth-hour = 3600 ÷ berth cycle time C02 × utilization C03. Berths required = ceiling(design cycles ÷ usable cycles). All four parameters are assumptions with stated orders of magnitude, not measured values.

## CM-05 Modules and footprint

Two platform modules come from the owner's drawings (imperial as drawn): M1, double-sided, 6 berths, 3,908 sq ft; M2, single-sided, 7 berths, 4,271 sq ft. The smallest module whose berth count covers the requirement is selected; a requirement above 7 berths is flagged, not designed. Berth counts were read from the drawings and await owner confirmation. Vehicles fit entirely within a berth as drawn, so vehicle dimensions do not enter the platform geometry.

## CM-06 Empty vehicles and the guideway

Where departures exceed arrivals, the difference is the number of empty vehicles per hour the guideway must deliver; where arrivals exceed departures, empty vehicles leave. No staging berths are drawn (C07). Network vehicle trips divided by one lane's throughput at the minimum headway C05 (3 s → 1,200 vehicles per hour) is a network-level ratio only; which link carries which trips needs a line model that does not exist.

## CM-07 Site fit is assumed

Per-station constructible space has not been acquired. Every module recommendation is made under assumption C06 (the space is available) and carries rule result RC-07 as a warning until the owner confirms the space.

## CM-08 What a configuration result is and is not

It is a demonstration of the calculation chain with explicit parameter provenance. It is not an engineering design, not a capacity proof for a full-line replacement, and not a statement that the current Metromover can or should be replaced. Any comparison with the current schedule is a reference, not an adequacy test.

## CM-09 Reading the rule results

A `critical` result means the computed configuration is invalid or infeasible and must not be presented as usable. A `warning` means the result may be used only with the named caveat and the named owner confirmation. An `info` result is a limitation to carry into every statement about the station. `pass` means the check holds. The rule pack is a set of project conventions and arithmetic identities, not a standard.
