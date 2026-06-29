# Inventory

*The CORA Asset model for the operational core of P07 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics (the undulator, the multi-bounce DCM, the slits) and the two experiment hutches (EH2 main with the diffractometer / magnet / detectors, EH2B secondary). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p07/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P07 **coins no new Family**: it reuses the optics / motion / detector Families and the allowlisted-loose `Magnet` Family. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P07` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P07` | `Unit` | (root) | - | bound to the PETRA III Site; Hereon / DESY joint operation (OPERATOR-1) |
| `Undulator` | `Device` | InsertionDevice | p07-oh2 | undulator; gap / taper; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p07-oh2 | multi-bounce DCM (1st / 2nd crystal bend/pitch/roll/yaw + energy); cut pending (OPT-1) |
| `OpticsZStage` | `Device` | LinearStage | p07-oh2 | OH1 component z-stage (Beckhoff) (OPT-1) |
| `DefiningSlits` | `Device` | Slit | p07-oh2 | OH2 slits (slt1 / slt2 + G_oh2 Galil) (OPT-1) |
| `OpticsStages` | `Device` | LinearStage | p07-oh2 | OH2 optics bank (oh01..16); grouped (OPT-1, GROUP-1) |
| `Goniometer` | `Device` | Goniometer | p07-eh2 | four-circle Eulerian (e4cv) + two-theta arm; not the Diffractometer Assembly (DIFF-1) |
| `SampleHexapod` | `Device` | Hexapod | p07-eh2 | EH2 sample hexapod (hx-hrz) (SAMPLE-1) |
| `Magnet` | `Device` | Magnet (loose) | p07-eh2 | 17 T superconducting sample-environment magnet (MAG-1) |
| `SampleEnvironment` | `Device` | TemperatureController | p07-eh2 | Linkam T95 programmable temperature stage (TEMP-1) |
| `SampleStage` (EH2) | `Device` | LinearStage | p07-eh2 | EH2 sample bank (exp33..64); grouped (GROUP-1) |
| `DetectorSlit` | `Device` | Slit | p07-eh2 | EH2/EH3 detector slit (g_eh3, Galil) (OPT-1) |
| `PilatusDetector` | `Device` | Camera | p07-eh2 | EH2 Pilatus area detector (DET-1) |
| `PerkinElmerDetector` | `Device` | Camera | p07-eh2 | EH2 PerkinElmer flat-panel (legacy controller) (DET-1) |
| `FluorescenceDetectors` | `Device` | EnergyDispersiveSpectrometer | p07-eh2 | EH2 MCA fluorescence (DET-1) |
| `SampleStage` (EH2B) | `Device` | LinearStage | p07-eh2b | EH2B sample bank (exp01..64); grouped (GROUP-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `LinearStage`, `Slit`, `Goniometer`, `Hexapod`, `TemperatureController`, `Camera`, `EnergyDispersiveSpectrometer`. Allowlisted-loose Family reused: `Magnet` (the 4-ID POLAR precedent, a further consumer, `MAG-1`). No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + sample banks) (CTRL-1) |
| `GalilSlitControllers` | MotionController | Tango_galildmcslit | Galil DMC slit controllers (OH2 + EH detector slits) (CTRL-1) |
| `HexapodControllers` | MotionController | Tango_hexapod | hexapod controllers (EH2 hexapod) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | multi-bounce DCM, OH z-stage, coupled axes (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (optics + EH2 + EH2B; other hutches) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The Hereon / DESY joint operation governance | `P07` | `unknown-pending-confirmation` | (OPERATOR-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The multi-bounce DCM crystal cut and the OH optics | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The diffractometer circle count and detector arm | `Goniometer` | `unknown-pending-confirmation` | (DIFF-1) |
| The per-axis roles of the motor banks | the `SampleStage` / `OpticsStages` Assets | `unknown-pending-confirmation` | (GROUP-1) |
| The 17 T magnet field and control detail | `Magnet` | `unknown-pending-confirmation` | (MAG-1) |
| The detector roster and models | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The other P07 hutches (EH1 / EH3 / EH4) | the beamline | `unknown-pending-confirmation` | (HOST-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies (incl. magnet He) | the supplies | `unknown-pending-confirmation` | (SUP-1) |
