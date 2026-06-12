# 2-BM

*Operational bending-magnet micro-CT at APS.*

CORA's pilot deployment. The scenario corpus that grounds the domain model runs against real 2-BM operations.

| Property | Value |
| --- | --- |
| Asset | `2-BM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 2` (organizational grouping; not a registered Asset) |
| Institution | [Argonne](../argonne/index.md) (context; not modeled as an Asset or Facility) |
| Drawing | `(ICMS, A342-RT1000, 02)` (APS beamline layout drawing, Rev 02, May 2026) |

Single-valued per the [Drawing VO](../../architecture/modules/equipment/index.md); the legacy Beam Component Reference Table `APS_1404611` is the natural carrier for upstream-optics Mounts and defers until those Assets register. See per-Asset drawings on [Assets](assets.md#engineering-drawings) and Assembly / Mount drawings on [MCTOptics](equipment/mctoptics.md#engineering-drawings).

## Inventories

- [Beam path](beamline.md) (the equipment walk source to detector, generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) descriptor)
- [Assets](assets.md) (flat inventory of all 2-BM sub-Assets: Components and Devices nested via `parent_id`)
- [Calibrations](calibrations.md)
- [Actors](actors.md)
- [Procedures](procedures.md)
- [Subjects](subjects.md)
- [Runs](runs.md)
- [Campaigns](campaigns.md)
- [Datasets](datasets.md)
- [Decisions](decisions.md)
- [Cautions](cautions.md)
- [Enclosures](enclosures.md)
- [Supplies](supplies.md)
- [Policies](policies.md)

## Equipment deployments

- [MCTOptics](equipment/mctoptics.md) (Optique Peter detector: Assembly + Fixture + 7 bound Assets + PseudoAxis lens selector)

Methods are cross-facility vocabulary in the [Catalog](../../catalog/methods.md); the Practices 2-BM consumes are APS Site Recipes in [APS](../aps/practices.md).
