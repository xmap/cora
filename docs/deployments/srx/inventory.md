# Inventory

*The CORA Asset model for SRX: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/srx/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/srx-profile-collection`). No vendor Model is bound: part numbers are not in the profile collection. SRX introduces **no new family**: every device reuses an existing catalog Family, including the ones recently graduated from earlier reverse-engineered deployments (`EnergyDispersiveSpectrometer` for the fluorescence detector, `FluxMonitor` for the ion chambers, `TemperatureController` for the sample-environment stage).

## The Asset tree

Root Asset `SRX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `SRX` | (root) | `XF:05ID*` | bound to the NSLS-II Site |
| `Source` | InsertionDevice | `SR:C5-ID:G1{IVU21:1}` | IVU21 in-vacuum undulator |
| `WhiteBeamShutter` | Shutter | `XF:05ID-PPS{Sh:WB}` | white-beam front-end shutter |
| `Monochromator` | Monochromator | `XF:05IDA-OP:1{Mono:HDCM}` | high-heat-load DCM; Bragg = energy actuator |
| `FocusingMirror` | Mirror | `XF:05IDA-OP:1{Mir:1}` | horizontal focusing mirror |
| `WhiteBeamSlit` | Slit | `XF:05IDA-OP:1{Slt:1}` | white-beam-defining slit |
| `SecondarySourceAperture` | Slit | `XF:05IDB-OP:1{Slt:SSA}` | coherence-defining secondary source |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (drives Bragg + undulator) |
| `BeamPositionMonitor` | GenericProbe | `XF:05IDA-BI:1{BPM:1}` | beam-position monitors |
| `NanoKBMirror` | Mirror | `XF:05IDD-ES:1{nKB}` | Kirkpatrick-Baez nanofocus mirror pair |
| `SampleStage` | LinearStage | `XF:05IDD-ES:1{nKB:Smpl}` | nano-endstation sample raster stack |
| `SampleRotary` | RotaryStage | `XF:05IDD-ES:1{nKB:Smpl}` | sample rotation (XRF-tomography) |
| `Attenuators` | Filter | `XF:05IDD-ES{IO:4}DO:` | pneumatic attenuator foils |
| `SampleTemperature` | TemperatureController | `XF:05IDD-ES{LS:1-Chan:}` | sample-environment thermal control |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:05IDD-ES{Xsp:3}` | Xspress3 XRF detector (Sensor Role) |
| `MerlinDetector` | Camera | `XF:05IDD-ES{Merlin:1}` | Merlin pixel detector (diffraction) |
| `DexelaDetector` | Camera | `XF:05IDD-ES{Dexela:1}` | Dexela flat-panel detector |
| `EigerDetector` | Camera | `XF:05IDD-ES{Det:Eig1M}` | Eiger 1M pixel detector |
| `ImagingCamera` | Camera | `XF:05IDD-ES{Det:3}` | PCO Edge full-field imaging camera |
| `FluxCounter` | FluxMonitor | `XF:05IDD-ES:1{Sclr:1}` | scaler ion-chamber flux channels |
| `Zebra` | TimingController | `XF:05IDD-ES:1{Dev:Zebra1}` | position-capture trigger box |
| `EndstationMotionController` | MotionController | (pending) | nano-stage / KB motion controllers |

Every family is in the catalog; SRX coins none. Notably the fluorescence detector reuses `EnergyDispersiveSpectrometer` (graduated when 2-ID and 7-BM shared it), the ion chambers reuse `FluxMonitor` (graduated in #353), and the thermal stage reuses `TemperatureController` (graduated in #350), so SRX is a clean reuse-and-reinforce deployment.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the SRX team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator period / gap range | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| HDCM crystal cut and energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| XRF-tomography rotary hardware / encoder | `SampleRotary` | `unknown-pending-confirmation` | (STAGE-1) |
| Fluorescence detector element count and vendor | `FluorescenceSpectrometer` | `unknown-pending-confirmation` | (DET-1) |
| Pixel/area detector roster (live vs legacy) | `MerlinDetector` / `DexelaDetector` / `EigerDetector` / `ImagingCamera` | `unknown-pending-confirmation` | (CAM-1) |
| Scaler / I0 flux channel map | `FluxCounter` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box models / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
