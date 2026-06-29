# Inventory

*The CORA Asset model for the operational core of P08 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics (the undulator, the DCM, the multilayer mono, the CRL, the absorber, the slits) and the experiment endstation (the six-circle diffractometer, the hexapod, the detectors). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p08/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P08 **coins no new Family**: it reuses the optics / motion / detector Families. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P08` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P08` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p08-oh | undulator; gap axis; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p08-oh | DCM (dcm_bragg / energyfmb); cut pending (OPT-1) |
| `MultilayerMonochromator` | `Device` | Monochromator | p08-oh | multilayer mono (lom* + table + coupled lomenergy); d-spacing pending (OPT-1) |
| `CompoundRefractiveLens` | `Device` | Transfocator | p08-oh | CRL control (lensctrl) (OPT-1) |
| `Absorber` | `Device` | Filter | p08-oh | beam absorber / attenuator (abs + atten) (OPT-1) |
| `DefiningSlits` | `Device` | Slit | p08-oh | beam-defining slits (sl3*) (OPT-1) |
| `Goniometer` | `Device` | Goniometer | p08-eh | six-circle Kohzu diffractometer (kozhue6cctrl + diff*); not the Diffractometer Assembly (DIFF-1, GROUP-1) |
| `SampleHexapod` | `Device` | Hexapod | p08-eh | experiment sample hexapod (hx-hrz) (SAMPLE-1) |
| `EigerDetector` | `Device` | Camera | p08-eh | DECTRIS Eiger 1M (DET-1) |
| `PilatusDetectors` | `Device` | Camera | p08-eh | DECTRIS Pilatus 100k / 300k (DET-1) |
| `MythenDetector` | `Device` | Camera | p08-eh | DECTRIS Mythen2 strip detector (DET-1) |
| `PerkinElmerDetector` | `Device` | Camera | p08-eh | PerkinElmer flat-panel (DET-1) |
| `VortexDetector` | `Device` | EnergyDispersiveSpectrometer | p08-eh | Vortex SDD (SIS3302-read) (DET-1) |
| `LambdaDetector` | `Device` | Camera | p08-eh | shared Lambda; bare petra3 host (HOST-1, DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Transfocator`, `Filter`, `Slit`, `Goniometer`, `Hexapod`, `Camera`, `EnergyDispersiveSpectrometer`. No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + diffractometer / sample banks) (CTRL-1) |
| `HexapodControllers` | MotionController | Tango_hexapod | hexapod controllers (sample hexapod) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | monochromators, Kohzu diffractometer, coupled axes (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (optics + experiment) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The DCM / multilayer crystal cut and the CRL detail | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The six-circle Kohzu geometry and detector arm | `Goniometer` | `unknown-pending-confirmation` | (DIFF-1) |
| The per-axis roles of the diff bank | `Goniometer` | `unknown-pending-confirmation` | (GROUP-1) |
| The sample hexapod geometry | `SampleHexapod` | `unknown-pending-confirmation` | (SAMPLE-1) |
| The detector roster and models | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The shared Lambda host | `LambdaDetector` | `unknown-pending-confirmation` | (HOST-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
