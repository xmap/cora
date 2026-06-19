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

Things CORA still needs the beamline team to confirm are collected on [Open questions](questions.md).

## The beamline

The systems you operate, in five areas: the three stations the beam passes through, plus the controls that drive them and the resources they draw on. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](equipment/source.md): the front-end optics that deliver and condition the beam (mirror, monochromator, slits, filters).
- [Sample](equipment/sample_tower.md): the positioning stack that places the specimen, a `SampleTower` [Assembly](../../catalog/assemblies.md) presenting the `Positioner` Role.
- [Detector](equipment/microscope.md): the imaging system, a `Microscope` Assembly over a reusable `Optics` sub-assembly, presenting the `Detector` Role.

Cutting across all three:

- [Controls](equipment/controls.md): the controllers and drive crates, related to the hardware by `controller_id`, with the trigger wiring that links them.
- [Resources](supplies.md): the continuously-available supplies a run needs (beam, cooling, vacuum).

The cross-cutting reference views: the [Layout](beamline.md) walk generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) descriptor, the [Assets](assets.md) inventory (the flat tree by `parent_id`, Family affordances, vendor Models, settings), and the [Computed axes](computed-axes.md).

## Getting ready

Setup before a scan.

- [Procedures](procedures.md): alignment, characterization, and recovery routines (Operation BC).
- [Recipes](recipes.md): deployment-bound recipe designs (set-energy, hexapod reboot) that expand into Procedures (Recipe BC).
- [Enclosures](enclosures.md): two hutch permits, optics hutch `2-BM-A` and experiment hutch `2-BM-B`, each gating its hutch's devices through the located-in pre-flight chain walk (Enclosure BC).
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
