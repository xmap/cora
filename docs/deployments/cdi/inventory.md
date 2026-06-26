# Inventory

*The CORA Asset model for CDI: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/cdi/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/cdi-profile-collection` and `NSLS2/cditools`). No vendor Model is bound: part numbers are not in the profile collection. CDI introduces **no new catalog family**: every device reuses an existing Family, including the ones graduated from earlier reverse-engineered deployments (`Camera` for the Eiger2 and Merlin detectors and the diagnostic cameras, `FluxMonitor` for the foil intensity monitor, `Monochromator` for both monochromators, `Mirror` for the pre-mirrors and the KB pair, `Goniometer` for the sample stack). Two loose families are bound: the `BeamPositionMonitor` (shared with 4-ID, 8-ID, ISS, FMX, held for gate-review) and the `StorageRing` supply observation (machine state, never an Asset Family).

## The Asset tree

Root Asset `CDI` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `CDI` | (root) | `XF:09ID*` | bound to the NSLS-II Site |
| `Source` | InsertionDevice | `SR:C09-ID:G1{IVU18:1}` | IVU18 in-vacuum undulator |
| `StorageRing` | StorageRing (loose) | `SR:OPS-BI{DCCT:1}` | storage-ring current readback (machine state) |
| `WhiteBeamSlit` | Slit | `XF:09IDA-OP:1{Slt:WB1}` | DM1 white-beam-defining slit |
| `AttenuatorFoil` | Filter | `XF:09IDA-OP:1{Fltr:DM1}` | DM1 attenuator foil paddle |
| `VerticalPreMirror` | Mirror | `XF:09IDA-OP:1{Mir:VPM}` | vertical pre-mirror (pitch / roll / bend) |
| `HorizontalPreMirror` | Mirror | `XF:09IDA-OP:1{Mir:HPM}` | horizontal pre-mirror |
| `Monochromator` | Monochromator | `XF:09IDA-OP:1{Mono:HDCM}` | silicon double-crystal monochromator (Si(111)) |
| `MultilayerMonochromator` | Monochromator | `XF:09IDA-OP:1{Mono:DMM}` | double-multilayer mono (high coherent flux) |
| `IntensityMonitorFoil` | Filter | `XF:09IDA-OP:1{IM:DM2}` | DM2 intensity-monitor foil |
| `BranchSlit` | Slit | `XF:09IDB-OP:1{Slt:DM3}` | DM3 branch-defining slit (09IDB zone) |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (Si(111) Bragg + gap model) |
| `FluxMonitor` | FluxMonitor | `XF:09IDA-BI{i400:1}` | foil intensity monitor (I0) |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:09IDB-BI{i404:1}` | quadrant beam-position monitor |
| `KBMirror` | Mirror | `XF:09IDC-OP:1{Mir:KBv}` | KB nanofocusing mirror pair (VKB + HKB) |
| `ConditioningSlit` | Slit | `XF:09IDC-OP:1{Slt:BCUU}` | beam-conditioning-unit slits |
| `InlineCamera` | Camera | `XF:09IDC-BI{BCU-Cam:9}` | BCU inline beam-viewing camera |
| `Goniometer` | Goniometer | `XF:09IDC-OP:1{Gon:1}` | sample goniometer and stack |
| `SampleTower1` | LinearStage | `XF:09IDC-ES:1{TDMS:T1}` | endstation positioning tower 1 |
| `SampleTower2` | LinearStage | `XF:09IDC-ES:1{TDMS:T2}` | endstation positioning tower 2 |
| `DiamondBeamMonitor` | BeamPositionMonitor (loose) | `XF:09IDC-BI{BPM:1}` | transmissive diamond BPM (TetrAMM) |
| `SampleCamera` | Camera | `XF:09IDC-BI{SMPL-Cam:10}` | sample-viewing camera |
| `EigerDetector` | Camera | `XF:09ID1-ES{Det:Eig1}` | Eiger2, primary coherent-diffraction detector |
| `MerlinDetector` | Camera | `XF:09ID1-ES{Det:Merlin1}` | Merlin, second coherent-diffraction detector |
| `EndstationMotionController` | MotionController | (pending) | optics / KB / goniometer / tower motion |

Every family is in the catalog except the loose `BeamPositionMonitor` (shared and held) and the loose `StorageRing` supply; CDI coins none. Notably the area detectors reuse `Camera` (the Eiger-to-Camera precedent, also used at [CHX](../chx/equipment/detector.md) and [HXN](../hxn/equipment/detector.md)), the KB pair reuses `Mirror` (the [FMX](../fmx/equipment/sample.md) / SRX KB precedent), both monochromators reuse `Monochromator` (the CHX Si-DCM-plus-multilayer-DMM precedent), and the foil intensity monitor reuses `FluxMonitor`, so CDI is a clean reuse-and-reinforce deployment.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the CDI team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| IVU18 undulator period / gap range | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS permit-leaf PVs; the 09IDB branch as a distinct enclosure | both enclosures | `unknown-pending-confirmation` | (PSS-1) (ENC-1) |
| DCM cryo detail and full range (Si(111) is read from source); DMM coating and bandpass | `Monochromator` / `MultilayerMonochromator` | `unknown-pending-confirmation` | (DCM-1) |
| KB focal size, coating, and working distance | `KBMirror` | `unknown-pending-confirmation` | (KB-1) |
| Whether incident energy is ever scanned as the measurement (provisional 5-15 keV) | `EnergyAxis` | `unknown-pending-confirmation` | (ENERGY-1) |
| Which tower carries the sample vs the detector; sample-to-detector distance / q-range; full goniometer axis set | `SampleTower1` / `SampleTower2` / `Goniometer` | `unknown-pending-confirmation` | (STAGE-1) |
| Which detector is primary per technique; foil materials; whether a beamstop is installed | `EigerDetector` / `MerlinDetector` / `AttenuatorFoil` | `unknown-pending-confirmation` | (DET-1) |
| Live diagnostic-camera set | `InlineCamera` / `SampleCamera` | `unknown-pending-confirmation` | (CAM-1) |
| Foil-monitor and BPM channel maps | `FluxMonitor` / `BeamPositionMonitor` / `DiamondBeamMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| The exposure-gating chain (no trigger box in source) | detectors | `unknown-pending-confirmation` | (TIMING-1) |
| Motion-controller box models / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
| Whether the coherent-imaging Methods enter the catalog | techniques | `unknown-pending-confirmation` | (TECH-1) |
