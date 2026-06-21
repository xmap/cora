# TomoWise

*Planned microtomography and nanotomography beamline at MAX IV. This page walks the beamline as it is designed; everything here is a TDR design specification, not a commissioned measurement.*

| Property | Value |
| --- | --- |
| Asset | `TomoWISE` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [MAX IV](../maxiv/index.md) (bound via `facility_code = "maxiv"`, `FacilityKind = Site`) |
| Status | In design (Technical Design Report phase) |
| Sources | CPMU14 cryo-undulator and 3T3PW wiggler, switchable per operation mode |
| Control stack | MAX IV Tango / Sardana (not EPICS); device handles to be assigned |

!!! warning "Design phase"
    TomoWISE is under design. Every value on these pages is a design target taken from the Technical Design Report, carried as `confirm` until the beamline team verifies it. The things CORA still needs the team to confirm are collected on [Open questions](questions.md); they are long on purpose.

## The beamline

The systems in three areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

Along the beam, in order:

- [Source](beamline.md): the beam delivery shared by both endstations (insertion devices, front-end masks, optics-hutch filters and multilayer monochromator, safety shutters), rendered as the generated source-stage device walk.
- [Endstations](equipment/endstations.md): the two experiment stations, microtomography (~45 m) and nanotomography (~49 m, KB-focused), and the sample environment each carries.
- [Detector](equipment/detector.md): one detector gantry on 7 m rails serving both stations, with interchangeable microscopes and cameras.

Cutting across all three:

- [Controls](equipment/controls.md): the Tango/Sardana control stack and the rotary-stage-master trigger scheme.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with families and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/tomowise/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what TomoWISE is designed to do, as design intent. Each is a portable [Catalog](../../catalog/methods.md) Method that a MAX IV [Practice](../maxiv/index.md#the-techniques-adapted-here) would adapt once the beamline is operating.

## Governance

[Governance](governance.md): who will act at TomoWISE and the trust shape that gates their commands. People and agents are facility principals at the [MAX IV Site](../maxiv/index.md#who-acts-here).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's TomoWISE content lives.

## Not yet documented

TomoWISE is pre-build, so the operations runbook (procedures, recipes, cautions) and the live experiment view are deliberately not written yet: a runbook for an unbuilt beamline would be invention, not record. They join these pages as the beamline approaches commissioning. The 2-BM deployment shows the shape they will take.
