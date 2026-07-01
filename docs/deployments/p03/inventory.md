# Inventory

*The CORA Asset model for the operational core of P03 modelled today: the planned device tree and what still needs confirming.*

This cut models the shared optics (the undulator, the multilayer monochromator, the two mirrors, the defining slits, the quad BPMs) and the two endstations (the P03 microfocus and the P03-NANO GINIX nanofocus) with their focusing, sample stages, and detectors. It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p03/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P03, PETRA III's first SAXS / WAXS beamline, **coins no new Family**: it reuses the optics / motion / detector Families across a two-endstation layout. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P03` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P03` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p03-optics | undulator; gap axis; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p03-optics | multilayer mono (lom) + coupled energy; d-spacing pending (OPT-1) |
| `Mirror1` | `Device` | Mirror | p03-optics | first mirror (pitch / transx / table); coating pending (OPT-1) |
| `Mirror2` | `Device` | Mirror | p03-optics | second mirror; coating pending (OPT-1) |
| `DefiningSlit1` | `Device` | Slit | p03-optics | first defining slit; reports on the P02 host (HOST-1) |
| `DefiningSlit2` | `Device` | Slit | p03-optics | second defining slit |
| `QuadrantBPMs` | `Device` | FluxMonitor | p03-optics | optics + experiment quadrant BPMs (i404) |
| `CRLHexapod` | `Device` | Hexapod | p03-microfocus | microfocus CRL focusing hexapod + z-stage (OPT-1) |
| `GuardSlit` (micro) | `Device` | Slit | p03-microfocus | microfocus guard slit (G1, Galil) (OPT-1) |
| `BeamlineSlit4` | `Device` | Slit | p03-microfocus | slit4 (S4_X/Y/Z) (OPT-1) |
| `SampleStage` (micro) | `Device` | LinearStage | p03-microfocus | microfocus sample bank (expmi_mot01..64); grouped (GROUP-1) |
| `SampleTemperature` | `Device` | TemperatureController | p03-microfocus | Eurotherm 2604 sample environment (TEMP-1) |
| `PilatusDetectors` | `Device` | Camera | p03-microfocus | Pilatus 300k + 1M (SAXS / WAXS) (DET-1) |
| `LambdaDetector` | `Device` | Camera | p03-microfocus | Lambda; reports on petra3 host (HOST-1, DET-1) |
| `FluorescenceDetectors` (micro) | `Device` | EnergyDispersiveSpectrometer | p03-microfocus | MCA + XIA fluorescence (DET-1) |
| `WaveguideSmarPod` | `Device` | Hexapod | p03-nanofocus | GINIX waveguide SmarPod (hexa3) (OPT-1) |
| `SampleHexapod` | `Device` | Hexapod | p03-nanofocus | GINIX sample hexapod (hexa2) + cube (SAMPLE-1) |
| `SampleRotation` | `Device` | RotaryStage | p03-nanofocus | GINIX sample rotation (Smaract ROT_PHI/X) (SAMPLE-1) |
| `WaveguideLinearStages` | `Device` | LinearStage | p03-nanofocus | GINIX waveguide stages (LLS1/2) (OPT-1) |
| `GuardSlit` (nano) | `Device` | Slit | p03-nanofocus | nanofocus guard slit (S6, Galil) (OPT-1) |
| `SampleStage` (nano) | `Device` | LinearStage | p03-nanofocus | nanofocus sample bank (mot01..40); grouped (GROUP-1) |
| `SampleIllumination` | `Device` | Camera | p03-nanofocus | GINIX LEDs + PS-camera-VHR viewing (DET-1) |
| `PilatusDetector` (nano) | `Device` | Camera | p03-nanofocus | nanofocus Pilatus 300k (DET-1) |
| `FluorescenceDetectors` (nano) | `Device` | EnergyDispersiveSpectrometer | p03-nanofocus | nanofocus MCA + SIS3302 (DET-1) |
| `ExperimentShutter` | `Device` | Shutter | p03-nanofocus | GINIX experiment / fast shutter (DET-1, PSS-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Slit`, `FluxMonitor`, `Hexapod`, `LinearStage`, `RotaryStage`, `TemperatureController`, `Camera`, `EnergyDispersiveSpectrometer`, `Shutter`. No new family is coined and nothing graduates.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (sample / instrument banks) (CTRL-1) |
| `GalilSlitControllers` | MotionController | Tango_galildmcslit | Galil DMC slit controllers (guard slits) (CTRL-1) |
| `SmarPodControllers` | MotionController | Tango_smarpodmotor | SmarPod controllers (GINIX waveguide) (CTRL-1) |
| `HexapodControllers` | MotionController | Tango_hexapod | hexapod controllers (CRL + GINIX sample hexapods) (CTRL-1) |
| `SmarActControllers` | MotionController | Tango_smaract | SmarAct controllers (GINIX rotation) (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | mono / mirrors / coupled axes (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (shared optics + two endstations) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The shared P02 / P03 optics host mapping and the Lambda host | `DefiningSlit1`, `LambdaDetector` | `unknown-pending-confirmation` | (HOST-1) |
| The multilayer d-spacing, mirror coatings, CRL / waveguide focal sizes | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the motor banks | `SampleStage` (micro and nano) | `unknown-pending-confirmation` | (GROUP-1) |
| The GINIX geometry and sample-hexapod / rotation detail | `SampleHexapod`, `SampleRotation` | `unknown-pending-confirmation` | (SAMPLE-1) |
| The cryo / heater sensor / setpoint handles | `SampleTemperature` | `unknown-pending-confirmation` | (TEMP-1) |
| The detector roster, SAXS-vs-WAXS assignment, models | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
