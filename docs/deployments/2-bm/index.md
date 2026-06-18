# 2-BM

*Operational bending-magnet micro-CT at APS. Start here, then follow the zone that matches what you need.*

| Property | Value |
| --- | --- |
| Asset | `2-BM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 2` (organizational grouping; not a registered Asset) |
| Institution | Argonne (context; not modeled as an Asset or Facility) |
| Drawing | `(ICMS, A342-RT1000, 02)` (APS beamline layout drawing, Rev 02, May 2026) |

## How to read these pages

The deployment separates what is configured from what is live. The configured zones are static: they describe the
beamline as it is built and operated, and they live in these docs. The live zone is per-experiment data whose
system of record is CORA's running read-API; the docs describe only its shape. The reader's journey runs across
the static zones and into the live one:

- [As-built](as-built.md): the equipment actually installed, its measured state, and the composed fixtures. The
  asset-tree backbone of the beamline.
- [Techniques](techniques.md): what 2-BM can do, each technique linking up to the cross-facility Catalog.
- [Operations](operations.md): the task-keyed runbook, from readying the beam to recovery, with the procedures,
  recipes, hutch permits, and cautions under it.
- [Governance](governance.md): the static authorization boundary, the operator pool and the trust zones and
  policies that gate commands.
- [The experiment](experiment.md): the live operational view, subjects, runs, campaigns, datasets, and decisions,
  described in shape here and served live by the app.

Two cross-cutting pages sit beside the journey:

- [Open questions](questions.md): what CORA still needs the beamline team to confirm.
- [How 2-BM is modeled](model.md): the developer's by-kind index, mapping each CORA aggregate to where its 2-BM
  instances are documented.

## Catalog and deployment

The generic, cross-facility vocabulary (Capabilities, Methods, Families, Models, Assemblies) lives in the
[Catalog](../../catalog/index.md). This deployment names those types and records only 2-BM's specifics: a Fixture
materializes an [Assembly](../../catalog/assemblies.md) as a Recipe materializes a
[Method](../../catalog/methods.md), and an Asset binds a [Model](../../catalog/models.md) to fill a Family. The
deployment restates none of the generic shape; it links up to it.
