# 2-BM

*Operational bending-magnet micro-CT at APS. This page walks the beamline and how a measurement gets done on it.*

| Property | Value |
| --- | --- |
| Asset | `2-BM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 2` (organizational grouping; not a registered Asset) |
| Institution | Argonne (context; not modeled as an Asset or Facility) |
| Drawing | `(ICMS, A342-RT1000, 02)` (APS beamline layout drawing, Rev 02, May 2026) |

The configured zones below live in these docs: the beamline itself, what it can do, how it is operated, and who governs it. The live per-experiment data (subjects, runs, datasets) is served by the running app, not a doc page. Things CORA still needs the beamline team to confirm are collected on [Open questions](questions.md).

## The beamline

The systems you operate, in five areas: the three stations the beam passes through, plus the controls that drive them and the resources they draw on. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the front-end optics that deliver and condition the beam (mirror, monochromator, slits, filters), rendered as the generated source-stage device walk.
- [Sample](equipment/sample_tower.md): the positioning stack that places the specimen, a `SampleTower` [Assembly](../../catalog/assemblies.md) presenting the `Positioner` Role.
- [Detector](equipment/microscope.md): the imaging system, a `Microscope` Assembly over a reusable `Optics` sub-assembly, presenting the `Detector` Role.

Cutting across all three:

- [Controls](equipment/controls.md): the controllers and drive crates, related to the hardware by `controller_id`, with the trigger wiring that links them.
- Resources: the continuously-available supplies a run needs (beam, cooling, vacuum), tracked under [Operations > Supplies](operations.md#supplies).

The cross-cutting reference view is the [Inventory](inventory.md): the flat Asset tree by `parent_id` with vendor Models, settings, drawings, and signal wiring, plus the computed axes. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what 2-BM can do, each a portable [Catalog](../../catalog/methods.md) Method bound through an APS [Practice](../aps/index.md#the-techniques-adapted-here). The function view survives equipment swaps.

## Operations

[Operations](operations.md) is the runbook for getting ready and measuring. It ties together [Procedures](procedures.md) (alignment, characterization, recovery), [Recipes](recipes.md) (deployment-bound step sequences that expand into Procedures), [Enclosures](enclosures.md) (the two hutch permits, optics hutch `2-BM-A` and experiment hutch `2-BM-B`), and [Cautions](cautions.md). Clearances, the safety forms that must be Active to start, are issued at the [APS Site](../aps/index.md#the-safety-envelope).

## Experiment

[Experiment](experiment.md): the live per-experiment view, the subjects, runs, campaigns, datasets, and decisions of a beamtime. Described here as shape; the real instances are served live by the app.

## Governance

[Governance](governance.md): who may act at 2-BM and the trust policies (Zone, Conduit, Policy) that gate their commands. People and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here); on the beamline they surface through the actions they take.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's 2-BM content lives.
