# Inventory

*The CORA Asset model for the operational core of P24 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics (the optics bank, the slits) and the two experiment hutches (EH2 diffractometer / MCA, EH1 sample bank). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p24/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P24 **coins no new Family**: it reuses `LinearStage` / `Slit` / `PseudoAxis` / `EnergyDispersiveSpectrometer` / `Camera`. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P24` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P24` | `Unit` | (root) | - | bound to the PETRA III Site |
| `OpticsStages` | `Device` | LinearStage | p24-oh | optics bank (oh_mot*, 20 axes); grouped (OPT-1, GROUP-1) |
| `DefiningSlits` | `Device` | Slit | p24-oh | primary / secondary slits (ps1 / ps2) (OPT-1) |
| `SampleStage` (EH2) | `Device` | LinearStage | p24-eh2 | EH2 diffractometer / sample bank (mot*, 40 axes); grouped (GROUP-1, DIFF-1) |
| `CoupledAxes` | `Device` | PseudoAxis | p24-eh2 | EH2 coupled / virtual axes (eh2_vm*) (GROUP-1) |
| `FluorescenceDetectors` | `Device` | EnergyDispersiveSpectrometer | p24-eh2 | EH2 MCA fluorescence detectors (DET-1) |
| `AreaDetector` | `Device` | Camera | p24-eh2 | single-crystal area detector; pending placeholder (DET-1) |
| `SampleStage` (EH1) | `Device` | LinearStage | p24-eh1 | EH1 sample bank (~16 axes); grouped (GROUP-1) |

Families reused from the catalog: `LinearStage`, `Slit`, `PseudoAxis`, `EnergyDispersiveSpectrometer`, `Camera`. No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + experiment banks) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | coupled / virtual axes + dummy stubs (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (optics + EH2 + EH1) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator source (absent from this slice) | `P24` | `unknown-pending-confirmation` | (SRC-1) |
| The optics breakdown (mono / mirrors) | `OpticsStages` | `unknown-pending-confirmation` | (OPT-1) |
| The diffractometer geometry (goniometer-vs-diffractometer once labelled) | `SampleStage` (EH2) | `unknown-pending-confirmation` | (DIFF-1) |
| The per-axis roles of the motor banks | the `SampleStage` Assets | `unknown-pending-confirmation` | (GROUP-1) |
| The single-crystal area detector model | `AreaDetector` | `unknown-pending-confirmation` | (DET-1) |
| The eh2_dmy dummy-stub status | the controllers | `unknown-pending-confirmation` | (STUB-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
