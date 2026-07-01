# Extracted facts: I04

Candidate device facts for `i04` (Diamond Light Source I04, macromolecular crystallography: rotation MX with autonomous sample exchange). Candidates only; confirm every row before modeling. Source: the public `DiamondLightSource/dodal` controls library (`src/dodal/beamlines/i04.py`, read 2026-06). Every value is carried `confirm` until I04 staff verify it: dodal is strong evidence, not a CORA-owned fact.

!!! note "dodal PV idiom"
    dodal device PVs are built as `{PREFIX.beamline_prefix}-XX-YYY-NN:`, where `beamline_prefix` resolves to **`BL04I`** at runtime from the `BEAMLINE` env var. The PV-prefix column below shows the resolved root + the literal suffix read verbatim from source (e.g. `BL04I-MO-SGON-01:`); where dodal hard-codes a full literal (the Eiger), it is shown as-is. The insertion-device prefix resolves to `SR04I` via `PREFIX.insertion_prefix`.

## Device inventory

Asset granularity: one row per stage / assembly, device-level PV prefix the descriptor binds, the dodal device class as sub-detail. A family ending in `(?)` is a name-fallback, resolve against `catalog/catalog.yaml` before binding.

| Device | Suggested family | PV prefix | dodal class | Stage | Confirm |
| --- | --- | --- | --- | --- | --- |
| Smargon | Goniometer | `BL04I-MO-SGON-01:` | Smargon | sample | yes |
| GonioPositioner | LinearStage | (XYZStage; gonio xyz) | XYZStage | sample | yes |
| SampleDeliverySystem | LinearStage | (XYZStage) | XYZStage | sample | yes |
| DCM | Monochromator | `BL04I-MO-DCM-01:` | DCM (i03 shared) | source | yes |
| Transfocator | Transfocator | `BL04I-MO-FSWT-01:` | Transfocator (i04) | source | yes |
| Attenuator | Filter | `BL04I-EA-ATTN-01:` | BinaryFilterAttenuator | source | yes |
| DiamondFilter | Filter | (DiamondFilter[I04Filters]) | DiamondFilter | source | yes |
| ApertureScatterguard | Aperture | aperture `BL04I-MO-MAPT-01:`; scatterguard `BL04I-MO-SCAT-01:` | ApertureScatterguard | source | yes |
| Backlight | Backlight | `BL04I` (bare beamline_prefix) | Backlight | sample | yes |
| Thawer | TemperatureController (?) | `BL04I-EA-THAW-01` | Thawer | sample | yes |
| SampleShutter | Shutter | `BL04I-EA-SHTR-01:` | MXZebraShutter | source | yes |
| Robot | Positioner | `BL04I-MO-ROBOT-01:` | BartRobot | sample | yes |
| EigerDetector | Camera | `BL04I-EA-EIGER-01:` | EigerDetector | detection | yes |
| DetectorMotion | LinearStage | device `BL04I-MO-DET-01:`; pmac `BL04I-MO-PMAC-02:` | DetectorMotion | detection | yes |
| Beamstop | BeamStop | `BL04I-MO-BS-01:` | Beamstop | detection | yes |
| IPin | FluxMonitor (?) | `BL04I-EA-PIN-01:` | IPin | detection | yes |
| Flux | FluxMonitor | `BL04I-MO-FLUX-01:` | Flux | detection | yes |
| Zebra | TimingController (?) | `BL04I-EA-ZEBRA-01:` | Zebra | detection | yes |
| ZebraFastGridScan | TimingController (?) | `BL04I-MO-SGON-01:` | ZebraFastGridScanThreeD | detection | yes |
| OAV | Camera | `BL04I-DI-OAV-01:` | OAV (on-axis view) | sample | yes |
| Undulator | InsertionDevice | `SR04I-MO-SERVC-01:` | UndulatorInKeV | source | yes |
| Synchrotron | GenericProbe (?) | (Synchrotron machine status) | Synchrotron | source | yes |
| XBPMFeedback | GenericProbe (?) | `BL04I-EA-FDBK-01:` | XBPMFeedback | source | yes |
| PinTipDetection | GenericProbe (?) | (vision pin-tip find) | PinTipDetection | sample | yes |

Device-level prefixes read verbatim from source: `smargon = Smargon("{beamline_prefix}-MO-SGON-01:")`, `dcm = DCM("...-MO-DCM-01:")`, `transfocator = Transfocator("...-MO-FSWT-01:")`, the literal `EigerDetector(prefix="BL04I-EA-EIGER-01:")`, the aperture/scatterguard MAPT/SCAT prefixes, `Zebra("...-EA-ZEBRA-01:")`, `UndulatorInKeV(prefix="{insertion_prefix}-MO-SERVC-01:")`.

## Role hints

- **Positioner**: Smargon goniometer, gonio/sample-delivery XYZ stages, DCM, transfocator, aperture-scatterguard, detector motion, robot.
- **Sensor**: IPin, Flux, XBPM feedback.
- **Detector**: Eiger, OAV (on-axis viewing camera).
- **Timing**: Zebra (+ fast-grid-scan), the MX fly/grid acquisition engine.
- **Sample handling**: BartRobot folds to Positioner + Clearance + Subject custody (the i03/FMX pattern), NOT a SampleChanger Family.

## Trust hints

dodal is a controls library, not a queue-server config; Diamond runs bluesky plans / GDA over dodal devices (the BlueAPI lineage). That orchestration layer is what CORA's EdgeConductor would conduct over. No per-beamline permission file in dodal (Trust modeled CORA-native).

## New-family watch

No new coining. Strong reuse (this is the MX consolidation pick that earns nothing new, as flagged in the survey):
- **Smargon -> Goniometer** (graduated via i03): I04 is a further MX consumer; bind directly. Same canonical six-axis Smargon as i03.
- **DCM -> Monochromator**, **Transfocator** (graduated), **Eiger -> Camera**, **Attenuator/DiamondFilter -> Filter**, **ApertureScatterguard -> Aperture** (graduated): bind directly.
- **Thawer -> TemperatureController (?)**: a sample-thawing device; confirm whether it presents a settable thermal setpoint (Regulator) or is a momentary actuator. Likely not a true TemperatureController.
- **Zebra -> TimingController (?)**: the fleet-wide gating question (matches NSLS-II).
- **IPin/Flux -> FluxMonitor**, **XBPM/Synchrotron/PinTip -> GenericProbe (loose)**: DIAG-1 cluster.

## Deferred / absent

- **Software/vision devices** (MurkoResults, Zocalo, MaxPixel, CentreEllipse, ZoomController, beamsize) are analysis/compute, not physical devices; not modeled as Assets.
- **PSS / hutch safety and the passive beam-path tier** are not in dodal (SCOPE-1); open questions.
- The synchrotron/undulator source detail beyond the prefix is machine-side; `SRC-1`.
