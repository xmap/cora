# Inventory

*The CORA Asset model for SMI: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/smi/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/smi-profile-collection`). No vendor Model is bound: part numbers are not in the profile collection. SMI introduces **no new catalog family**: every device reuses an existing Family, including the ones graduated from earlier deployments (`Camera` for the Pilatus detectors, `FluxMonitor` for the flux monitor, `TemperatureController` for the sample environment, `EnergyDispersiveSpectrometer` for the fluorescence detector). Two devices bind loose families shared across deployments and held for gate-review: the compound-refractive-lens `Transfocator` (4-ID, 8-ID, 9-ID, i22, CHX) and the `BeamPositionMonitor` (4-ID, 8-ID, 9-ID), both recorded in the promotion-review register (see [Model](model.md#deliberately-not-here-yet)).

## The Asset tree

Root Asset `SMI` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `SMI` | (root) | `XF:12ID*` | bound to the NSLS-II Site |
| `Source` | InsertionDevice | `SR:C12-ID:G1{IVU:1}` | in-vacuum undulator |
| `PhotonShutter` | Shutter | `XF:12IDA-PPS:2{PSh}` | front-end photon shutter |
| `Monochromator` | Monochromator | `XF:12ID:m65` | double-crystal mono (coupled energy) |
| `HorizontalFocusingMirror` | Mirror | `XF:12IDA-OP:2{Mir:HF}` | horizontal focusing mirror |
| `VerticalFocusingMirror` | Mirror | `XF:12IDA-OP:2{Mir:VF}` | vertical focusing mirror |
| `Transfocator` | Transfocator (loose) | `XF:12IDC-OP:2{Lens:CRL}` | compound-refractive-lens focusing |
| `WhiteBeamSlit` | Slit | `XF:12IDA-OP:2{Slt:WB}` | white-beam-defining slit |
| `SecondarySourceAperture` | Slit | `XF:12IDB1-OP:2{Slt:SSA}` | coherence-matched secondary source |
| `Attenuators` | Filter | `XF:12IDC-OP:2{Fltr:1}` | two banks of insertable foils |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (undulator + DCM) |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:12IDA-BI:2{EM:BPM1}` | beam-position monitors |
| `BeamDefiningSlit` | Slit | `XF:12IDC-OP:2{Slt:C}` | experiment-hutch beam-defining slit |
| `GuardSlit` | Slit | `XF:12IDC-OP:2{Slt:E}` | experiment-hutch guard slit |
| `SampleStage` | LinearStage | `XF:12IDC-OP:2{HUB:Stg}` | HUB sample stack (grazing-incidence axes) |
| `SampleTemperature` | TemperatureController | `XF:12ID-ES{LINKAM}:` | Linkam / LakeShore thermal control |
| `SAXSDetector` | Camera | `XF:12ID2-ES{Pilatus:Det-2M}` | Pilatus 2M (SAXS) |
| `WAXSDetector` | Camera | `XF:12IDC-ES:2{Det:900KW}` | Pilatus 900KW (WAXS, swing arc) |
| `SAXSDetectorStage` | LinearStage | `XF:12IDC-ES:2{Det:1M-Ax:}` | SAXS camera-length stage (sets Q) |
| `SAXSBeamStop` | BeamStop | `XF:12IDC-ES:2{BS:SAXS}` | SAXS direct-beam stop |
| `FluxMonitor` | FluxMonitor | `XF:12ID:2{EM:Tetr1}` | TetrAMM pin-diode flux monitor |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:12IDC-ES:2{Det-Amptek:1}` | Amptek fluorescence MCA |
| `BeamViewingCamera` | Camera | `XF:12IDC-BI{Cam:SAM}` | on-axis sample-viewing camera |
| `FastShutter` | Shutter | `XF:12IDC-ES:2{PSh:ES}` | endstation exposure shutter |
| `EndstationMotionController` | MotionController | (pending) | sample / detector / beamstop controllers |

Every family is in the catalog except the loose `Transfocator` and `BeamPositionMonitor` (both shared and held); SMI coins none. Notably the Pilatus detectors reuse `Camera`, the flux monitor reuses `FluxMonitor` (graduated in #353), the sample environment reuses `TemperatureController` (graduated in #350), and the fluorescence detector reuses `EnergyDispersiveSpectrometer` (graduated in #345), so SMI is a clean reuse-and-reinforce deployment, the NSLS-II twin of i22.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the SMI team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator period / gap range | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| DCM crystal and energy range | `Monochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Transfocator lens material / count and catalog home | `Transfocator` | `unknown-pending-confirmation` | (CRL-1) |
| Full HUB axis set; Goniometer / Assembly modelling | `SampleStage` | `unknown-pending-confirmation` | (STAGE-1) |
| Live Pilatus set and SAXS camera-length range | `SAXSDetector` / `WAXSDetector` / `SAXSDetectorStage` | `unknown-pending-confirmation` | (DET-1) |
| Live sample-environment thermal units | `SampleTemperature` | `unknown-pending-confirmation` | (TEMP-1) |
| Flux / beam-position channel maps | `FluxMonitor` / `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box models / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
