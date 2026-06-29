# Inventory

*The CORA Asset model for the operational core of P65 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics (the undulator, the CDCM energy axis, the optics / front-end banks) and the experiment endstation (the sample bank, the slit, the table). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p65/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P65 **coins no new Family**: it is a thin applied-XAS station reusing the optics / motion Families. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P65` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P65` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p65-oh | undulator; energy axis read; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p65-oh | channel-cut DCM energy axis (cdcmenergy); on shared P64 host (HOST-1, OPT-1) |
| `OpticsStages` | `Device` | LinearStage | p65-oh | optics (oh_*) + front-end (fe_*) banks; grouped (OPT-1, GROUP-1, HOST-1) |
| `SampleStage` | `Device` | LinearStage | p65-eh | experiment sample bank (a2_mot01..20); grouped (GROUP-1) |
| `ExperimentSlit` | `Device` | Slit | p65-eh | experiment slit (eh_slit center x / y) |
| `ExperimentTable` | `Device` | Table | p65-eh | experiment table (eh_table height / vertical) |
| `AbsorptionDetectors` | `Device` | FluxMonitor | p65-eh | XAS ion chambers / fluorescence; pending placeholder (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `LinearStage`, `Slit`, `Table`, `FluxMonitor`. No new family is coined and nothing graduates. The `a2_dmy*` dummy stubs are noted, not modelled (`STUB-1`).

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + sample banks) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | CDCM energy axis + a2 dummy stubs (CTRL-1, STUB-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (optics + experiment, optics shared with P64) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The CDCM crystal cut and the optics breakdown | `Monochromator`, `OpticsStages` | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the banks | `OpticsStages`, `SampleStage` | `unknown-pending-confirmation` | (GROUP-1) |
| The XAS detection chain (ion chambers / fluorescence) | `AbsorptionDetectors` | `unknown-pending-confirmation` | (DET-1) |
| The shared P64 / P65 optics host | `Monochromator`, `OpticsStages` | `unknown-pending-confirmation` | (HOST-1) |
| The a2 dummy-stub status | the controllers | `unknown-pending-confirmation` | (STUB-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
