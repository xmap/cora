# 19-BM-FACT

*Planned filtered white-beam bending-magnet CT beamline at APS Sector 19, built for high-throughput autonomous tomography with robotic sample handling. This page walks the beamline as it is designed; everything here is a Final Design Report specification, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `19-BM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`), Sector 19 |
| Status | In design (Final Design Report, 6 June 2026); first light targeted 2026-3 cycle |
| Source | APS bending magnet (M3); filtered white beam only, no monochromator |
| Control stack | EPICS (APS standard); PV names to be assigned |

!!! warning "Design phase"
    19-BM-FACT was under construction when the FDR was written. Every value on these pages is a design specification, carried as `confirm` until the beamline team verifies it. The things CORA still needs the team to confirm are collected on [Open questions](questions.md).

## The beamline

19-BM-FACT is a sibling of the operational [2-BM](../2-bm/index.md): both are APS bending-magnet, indirect-detection, micron-CT beamlines. 19-BM differs in three ways that shape the model: it is filtered **white-beam only** (no monochromator or mirror optics, so the spectrum is set by filter selection), it runs in **three enclosures** (a front-end optics enclosure, a pure shielded transport, and the endstation), and it is built for **autonomous high-throughput operation** with a robotic sample changer.

Along the beam, in order:

- [Source](beamline.md): the bending-magnet beam delivery and conditioning in 19-BM-A (the exit Be window and mask, the bremsstrahlung collimators, the white-beam slits, the F3-30 filter unit, and the vacuum isolation), rendered as the generated source-stage device walk.
- [Sample](equipment/sample.md): the in-air endstation in 19-BM-D, where the beam transitions through a water-cooled Be window and a Kapton window to the sample stage that hosts the robotic sample changer.
- [Detector](equipment/detector.md): the indirect-detection imaging system (scintillator, microscope optics, camera) and the downstream beam stops.

Cutting across all three:

- [Controls](equipment/controls.md): the EPICS control stack and the high-throughput trigger scheme.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/19-bm/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what 19-BM is designed to do, as design intent. Each is a portable [Catalog](../../catalog/methods.md) Method that an APS [Practice](../aps/index.md#the-techniques-adapted-here) adapts once the beamline is operating.

## Governance

[Governance](governance.md): who will act at 19-BM and the trust shape that gates their commands. People and agents are facility principals at the [APS Site](../aps/index.md#who-acts-here); autonomy is first-class here, so this is the deployment where CORA's supervisory agents are intended to go operational.

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's 19-BM content lives.

## Not yet documented

19-BM is pre-build, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written yet: a runbook for an unbuilt beamline would be invention, not record. They join these pages as the beamline approaches commissioning. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
