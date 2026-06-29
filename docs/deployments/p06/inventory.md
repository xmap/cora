# Inventory

*The CORA Asset model for the operational core of P06 modelled today: the planned device tree and what still needs confirming.*

This cut models the optics / mono hutch (the undulator, the DCM, the multilayer monochromator, the slits, the quad BPM) and the two scanning-probe endstations (MC01 micro-probe, NC1 nano-probe) with their hexapods, focusing and sample stages, and the shared detector pool (the Maia array, the area detectors, the fluorescence detectors). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p06/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. P06, CORA's third PETRA III beamline, **coins no new Family**: it is the fleet's fullest reuse of the catalog, binding `Hexapod`, `EnergyDispersiveSpectrometer`, and the optics / motion / camera Families. The Tango device handles are read from the public OnlineXML registry; no vendor Models are bound.

## The Asset tree

Root Asset `P06` (`tier = Unit`, `facility_code = petra-iii`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `P06` | `Unit` | (root) | - | bound to the PETRA III Site |
| `Undulator` | `Device` | InsertionDevice | p06-mono | undulator; gap / harmonic / taper axes; period pending (SRC-1) |
| `Monochromator` | `Device` | Monochromator | p06-mono | double-crystal monochromator + coupled energy; crystal cut pending (OPT-1) |
| `MultilayerMonochromator` | `Device` | Monochromator | p06-mono | multilayer mono (lom), higher-flux branch; d-spacing pending (OPT-1) |
| `MonochromatorStages` | `Device` | LinearStage | p06-mono | mono-hutch motor bank (mono_mot, 29 axes); roles grouped (GROUP-1) |
| `OpticsHutchSlits` | `Device` | Slit | p06-mono | optics-hutch defining slit (virtual h/v gap+offset) |
| `SecondarySlit` | `Device` | Slit | p06-mono | secondary slit (ps2) |
| `QuadrantBPM` | `Device` | FluxMonitor | p06-mono | mono-hutch quadrant BPM (i404) |
| `Hexapod` | `Device` | Hexapod | p06-mc01 | MC01 six-axis hexapod; coarse sample orientation |
| `SampleStage` (MC01) | `Device` | LinearStage | p06-mc01 | MC01 sample stack (mi_mot 46 axes + piezo/hydra); roles grouped (GROUP-1) |
| `ScanStage` (MC01) | `Device` | LinearStage | p06-mc01 | MC01 Aerotech raster scan stage (SCAN-1) |
| `PinAlignment` | `Device` | LinearStage | p06-mc01 | MC01 pin alignment SmarAct piezos |
| `VirtualStages` | `Device` | PseudoAxis | p06-mc01 | MC01 virtual coupled axes (GROUP-1) |
| `QuadrantBPM` (MC01) | `Device` | FluxMonitor | p06-mc01 | MC01 quadrant BPM (i404) |
| `KBLensHexapodHorizontal` | `Device` | Hexapod | p06-nc1 | NC1 horizontal KB-lens SmarAct hexapod (OPT-1) |
| `KBLensHexapodVertical` | `Device` | Hexapod | p06-nc1 | NC1 vertical KB-lens SmarAct hexapod (OPT-1) |
| `LensFineStages` | `Device` | PseudoAxis | p06-nc1 | NC1 KB-lens virtual fine axes (OPT-1) |
| `SamplePiezo` | `Device` | LinearStage | p06-nc1 | NC1 SmarAct sample / phase / interferometer piezos (SAMPLE-1) |
| `SampleRotation` | `Device` | RotaryStage | p06-nc1 | NC1 sample rotation (Pegasus samr); nano-tomography axis (SAMPLE-1) |
| `CentringPiezo` | `Device` | LinearStage | p06-nc1 | NC1 sample-centring piezos (PI E-871) |
| `ScanStage` (NC1) | `Device` | LinearStage | p06-nc1 | NC1 Aerotech raster scan stage (SCAN-1) |
| `NanoPositioningStage` | `Device` | LinearStage | p06-nc1 | NC1 nano-positioning bank (nat_mot, 20 axes); roles grouped (GROUP-1) |
| `NC1Slits` | `Device` | Slit | p06-nc1 | NC1 defining slit (virtual h/v gap+offset) |
| `MaiaDetector` | `Device` | EnergyDispersiveSpectrometer | p06-mc01 | Maia high-rate XRF array (6 sub-devices); mapping detector (DET-1) |
| `XIAFluorescence` | `Device` | EnergyDispersiveSpectrometer | p06-mc01 | XIA MCA fluorescence detectors (DET-1) |
| `EigerDetector` | `Device` | Camera | p06-mc01 | DECTRIS Eiger area detector (DET-1) |
| `LambdaDetector` | `Device` | Camera | p06-mc01 | X-Spectrum Lambda; reports on petra3 host (HOST-1, DET-1) |
| `PilatusDetector` | `Device` | Camera | p06-mc01 | DECTRIS Pilatus 300k (two units) (DET-1) |
| `PCODetector` | `Device` | Camera | p06-mc01 | PCO 4000 CCD (DET-1) |
| `XrayEyeCamera` | `Device` | Camera | p06-mc01 | X-ray-eye Prosilica viewing camera (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `LinearStage`, `Slit`, `FluxMonitor`, `Hexapod`, `PseudoAxis`, `RotaryStage`, `EnergyDispersiveSpectrometer`, `Camera`. No new family is coined and nothing graduates. The Maia array is modelled as one `EnergyDispersiveSpectrometer` Asset carrying its six sub-device handles.

## Cross-cutting controllers

| Asset | Family | Protocol | Note |
| --- | --- | --- | --- |
| `OMS58Controllers` | MotionController | Tango_oms58 | OMS MAXv-58 steppers (mono, mi, nat banks) (CTRL-1) |
| `AerotechControllers` | MotionController | Tango_aerotech | Aerotech fly-scan stages (SCAN-1, CTRL-1) |
| `SmarActControllers` | MotionController | Tango_smaract | SmarAct piezo / hexapod controllers (CTRL-1) |
| `HexapodControllers` | MotionController | Tango_hexapod | MC01 hexapod controller (CTRL-1) |
| `PiezoControllers` | MotionController | Tango_piezo | PI piezo + SMC-Hydra fine stages (CTRL-1) |
| `TangoMotorControllers` | MotionController | Tango_motor_tango | mono / undulator / virtual / Pegasus axes (CTRL-1) |

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| The hutch grouping (mono + two probe endstations) | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| The undulator period / parameters | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| The DCM crystal cut, multilayer d-spacing, KB focal sizes | the optics Assets | `unknown-pending-confirmation` | (OPT-1) |
| The per-axis roles of the motor banks | `MonochromatorStages`, `SampleStage`, `NanoPositioningStage`, `VirtualStages` | `unknown-pending-confirmation` | (GROUP-1) |
| The Aerotech fly-scan raster parameters | the `ScanStage` Assets | `unknown-pending-confirmation` | (SCAN-1) |
| The NC1 sample-piezo and rotation detail | `SamplePiezo`, `SampleRotation` | `unknown-pending-confirmation` | (SAMPLE-1) |
| The detector roster, Maia element count, area-detector models | the detector Assets | `unknown-pending-confirmation` | (DET-1) |
| The detectors reporting on a bare p06 / petra3 host | `LambdaDetector`, the detector pool | `unknown-pending-confirmation` | (HOST-1) |
| The Tango handle freshness vs the live database | all Assets | `unknown-pending-confirmation` | (CTRL-1) |
| The PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| The vacuum extent and supplies | the supplies | `unknown-pending-confirmation` | (SUP-1) |
