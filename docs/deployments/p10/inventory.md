# Inventory

*The CORA Asset model for the operational core of P10 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics hutch (the undulator, the DCM, the optics stages, the beam shutter) and the three experiment areas (E1 coherent imaging, E2 XPCS / diffraction with the LCX piezo sub-station, LAB offline) with their sample stages, focusing, and the wide detector suite. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p10/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P10, CORA's second XPCS beamline, **coins no new Family**: it reuses the optics / motion / detector Families across a five-enclosure layout. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P10` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P10` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p10-opt | undulator; gap axis; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p10-opt | DCM (DCM_BRAGG / FMBENERGY + coupled P10ENERGY); cut pending (OPT-1) |
| `OpticsStages` | `Device` | LinearStage | p10-opt | optics bank (OPT_MOT, 32 axes); grouped (OPT-1, GROUP-1) |
| `OpticsVirtualStages` | `Device` | PseudoAxis | p10-opt | optics virtual / coupled axes (vm_opt_*) (GROUP-1) |
| `BeamShutter` | `Device` | Shutter | p10-opt | the P10 beam shutter (PSS-1) |
| `Hexapod` | `Device` | Hexapod | p10-e1 | E1 six-axis hexapod |
| `CompoundRefractiveLens` | `Device` | Transfocator | p10-e1 | E1 CRL box (EHCRL) (OPT-1) |
| `GuardSlit` (E1) | `Device` | Slit | p10-e1 | E1 guard slit (G1, Galil) (OPT-1) |
| `SampleStage` (E1) | `Device` | LinearStage | p10-e1 | E1 sample bank (E1_MOT, 97 axes incl. e6cctrl); grouped (GROUP-1) |
| `SampleVirtualStages` (E1) | `Device` | PseudoAxis | p10-e1 | E1 virtual axes (vm_e1_*) (GROUP-1) |
| `QuadroDetector` | `Device` | Camera | p10-e1 | E1 Quadro area detector (DET-1) |
| `FluorescenceDetectors` (E1) | `Device` | EnergyDispersiveSpectrometer | p10-e1 | E1 MCA fluorescence (DET-1) |
| `Mirrors` | `Device` | Mirror | p10-e2 | E2 mirror stages (mirror1 / mirror2 / mirrorz, spk) (OPT-1) |
| `SamplePiezo` (E2) | `Device` | LinearStage | p10-e2 | E2 SmarAct sample piezos (SPX/Y/Z) (SAMPLE-1) |
| `TwoThetaArm` | `Device` | RotaryStage | p10-e2 | E2 two-theta detector arm (eh2tthp10) (SAMPLE-1) |
| `GuardSlit` (E2) | `Device` | Slit | p10-e2 | E2 guard slit (G2, Galil) (OPT-1) |
| `SampleStage` (E2) | `Device` | LinearStage | p10-e2 | E2 sample bank (E2_MOT, 96 axes); grouped (GROUP-1) |
| `SampleVirtualStages` (E2) | `Device` | PseudoAxis | p10-e2 | E2 virtual axes (vm_e2_*) (GROUP-1) |
| `NanoPositioner` | `Device` | LinearStage | p10-e2 | LCX AttoCube + SmarAct piezos (LCX-1, SAMPLE-1) |
| `PilatusDetectors` | `Device` | Camera | p10-e2 | E2 Pilatus 100k / 1M / 300k (DET-1) |
| `PCODetector` | `Device` | Camera | p10-e2 | E2 PCO edge sCMOS (DET-1) |
| `LCXCamera` | `Device` | Camera | p10-e2 | E2 LCX diagnostics camera (DET-1) |
| `LambdaDetector` | `Device` | Camera | p10-e2 | shared Lambda; bare p10 host (HOST-1, DET-1) |
| `LimaCameras` | `Device` | Camera | p10-e2 | shared Lima MAX22 / MAX51; bare p10 host (HOST-1, DET-1) |
| `SimulatedDiffractometer` | `Device` | Goniometer | p10-lab | LAB simulated E6C diffractometer (LAB-1) |
| `EigerDetector` | `Device` | Camera | p10-lab | LAB Eiger 4M (DET-1) |
| `AndorCamera` | `Device` | Camera | p10-lab | LAB Andor camera (DET-1) |
| `MythenDetector` | `Device` | Camera | p10-lab | LAB Mythen strip detector (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `LinearStage`, `PseudoAxis`, `Shutter`, `Hexapod`, `Transfocator`, `Slit`, `Camera`, `EnergyDispersiveSpectrometer`, `Mirror`, `RotaryStage`, `Goniometer`. No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (optics + sample banks) (CTRL-1) |
| `GalilSlitControllers` | MotionController | Tango_galildmcslit | Galil DMC slit controllers (guard slits) (CTRL-1) |
| `SmarActControllers` | MotionController | Tango_smaract | SmarAct controllers (E2 / LCX piezos) (CTRL-1) |
| `AttoCubeControllers` | MotionController | Tango_attocube | AttoCube controllers (LCX piezos) (CTRL-1) |
| `HexapodControllers` | MotionController | Tango_hexapod | hexapod controllers (E1 hexapod) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | mono / mirrors / coupled axes (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (optics + three experiment areas) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The DCM crystal cut and the optics breakdown | `Monochromator`, `OpticsStages` | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the motor banks | the `SampleStage` / `OpticsStages` Assets | `unknown-pending-confirmation` | (GROUP-1) |
| The E2 sample-piezo and two-theta detail | `SamplePiezo`, `TwoThetaArm` | `unknown-pending-confirmation` | (SAMPLE-1) |
| The LCX piezo sub-station role | `NanoPositioner` | `unknown-pending-confirmation` | (LCX-1) |
| The LAB simulated diffractometer status | `SimulatedDiffractometer` | `unknown-pending-confirmation` | (LAB-1) |
| The detector roster, XPCS-detector assignment, models | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The Lambda / Lima cameras on the bare p10 host | `LambdaDetector`, `LimaCameras` | `unknown-pending-confirmation` | (HOST-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and the beam-shutter role | the enclosures, `BeamShutter` | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
