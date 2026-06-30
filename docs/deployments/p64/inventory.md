# Inventory

*The CORA Asset model for the operational core of P64 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics (the undulator, the Tsai DCM, the mirror pair, the slits) and the experiment endstation (the sample bank, the DAC sub-stage, the picomotors, the detectors). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p64/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P64 **coins no new Family**: it reuses the optics / motion / detector Families. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P64` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P64` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p64-oh | undulator; energy axis coupled to mono; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p64-oh | Tsai DCM (monotheta + energy + coupled energy_all); cut pending (OPT-1) |
| `Mirror1` | `Device` | Mirror | p64-oh | first OH mirror (hor / ver / tilt / yaw); coating pending (OPT-1) |
| `Mirror2` | `Device` | Mirror | p64-oh | second OH mirror (hor / ver / tilt / yaw); coating pending (OPT-1) |
| `DefiningSlits` | `Device` | Slit | p64-oh | s3 / s4 beam-defining slits (OPT-1) |
| `SampleStage` | `Device` | LinearStage | p64-eh | sample bank (exp_mot* + dac_* DAC sub-stage); grouped (GROUP-1) |
| `PicomotorStage` | `Device` | LinearStage | p64-eh | NewFocus 8742 picomotor fine stages (GROUP-1) |
| `LambdaDetectors` | `Device` | Camera | p64-eh | two Lambda 750k area detectors (DET-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | p64-eh | multi-element fluorescence detector (104-ch SIS3302, grouped) (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Slit`, `LinearStage`, `Camera`, `EnergyDispersiveSpectrometer`. No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + sample banks) (CTRL-1) |
| `PicomotorControllers` | MotionController | Tango_newfocuspico8742 | NewFocus 8742 picomotor controllers (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | Tsai mono + coupled energy axis (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (optics + experiment) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The Tsai DCM crystal cut and the mirror coatings | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the sample bank and DAC sub-stage | `SampleStage`, `PicomotorStage` | `unknown-pending-confirmation` | (GROUP-1) |
| The detector roster, the multi-element element count, the ion chambers | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
