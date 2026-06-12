# 2-BM

*Operational bending-magnet micro-CT at APS. This page walks the beamline and how a measurement gets done on it.*

| Property | Value |
| --- | --- |
| Asset | `2-BM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 2` (organizational grouping; not a registered Asset) |
| Institution | Argonne (context; not modeled as an Asset or Facility) |
| Drawing | `(ICMS, A342-RT1000, 02)` (APS beamline layout drawing, Rev 02, May 2026) |

The measurement lifecycle below is the reading order: the beamline itself, then getting it ready, running a measurement, the results, and the envelope that governs it. The physical layer is generated from the descriptor; the operational stages are hand-authored today and become CORA-projection-generated in a later phase.

## The beamline

What 2-BM physically is, walked source to detector.

- [Layout](beamline.md): the equipment walk source to detector, every device with its calibration and condition, generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) descriptor.
- [Assets](assets.md): the CORA Asset model view (flat tree by `parent_id`, Family affordances, vendor Models, settings schemas, drawings).
- [MCTOptics](equipment/mctoptics.md): the Optique Peter detector as an Assembly + Fixture.

## Getting ready

Setup before a scan.

- [Procedures](procedures.md): alignment, calibration, and recovery routines (Operation BC).
- [Supplies](supplies.md): the resources a run needs available (beam, cooling, vacuum).
- [Enclosures](enclosures.md): the hutch permit that gates runs and procedures, covering every device through the pre-flight chain walk (Enclosure BC).
- Clearances: the safety forms that must be Active to start, issued at the [APS Site](../aps/index.md#the-safety-envelope).

## Running a measurement

The act of measuring.

- [Subjects](subjects.md): the samples mounted and measured.
- [Runs](runs.md): execution instances and their state.
- [Campaigns](campaigns.md): series that group many runs.
- The recipe a run executes is a [Method](../../catalog/methods.md) (cross-facility) bound through an APS [Practice](../aps/index.md#the-techniques-adapted-here).

## Results

What came out and whether it is trustworthy.

- [Datasets](datasets.md): the data products, with lineage back to the run, subject, and equipment.

## Operating envelope

Who and what governs.

- [Decisions](decisions.md): the accountability ledger (overrides, steering).
- [Policies](policies.md): the authorization rules in effect at the beamline.
- [Cautions](cautions.md): operator advisories and tribal knowledge.
- People and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here); on the beamline they surface only through the actions they take above.
