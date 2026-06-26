# Inventory

*The CORA Asset model for SST: the device tree read from the profile collections and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/sst/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against the `NSLS2/sst-*-profile-collection` TOML manifests and the `NSLS-II-SST/sst-base` device classes). No vendor Model is bound: part numbers are not in the profile collection. SST introduces **no new catalog family**: every device reuses an existing Family, including the recently-graduated soft-X-ray ones (`GratingMonochromator` for the soft PGM, `Manipulator` for the sample stages, `EnergyDispersiveSpectrometer` for the microcalorimeter). The hemispherical `ElectronAnalyzer` (a second sighting after ESM) GRADUATED into the catalog (ARPES-1); one loose family remains, the `BeamPositionMonitor` (DIAG-1); see [Model](model.md#deliberately-not-here-yet).

## The Asset tree

Root Asset `SST` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `SST` | (root) | `XF:07ID*` | bound to the NSLS-II Site |
| `SoftUndulator` | InsertionDevice | `SR:C07-ID:G1A{SST1:1}` | EPU60 (soft branch) |
| `TenderUndulator` | InsertionDevice | `SR:C07-ID:G1A{SST2:1}` | U42 (tender branch) |
| `FrontEndShutter` | Shutter | `XF:07ID-PPS{Sh:FE}` | front-end photon shutter |
| `SoftMonochromator` | GratingMonochromator | `XF:07ID1-OP{Mono:PGM1}` | soft plane-grating mono |
| `TenderMonochromator` | Monochromator | `XF:07ID6-OP{Mono:DCM1}` | tender double-crystal mono |
| `FirstMirror` | Mirror | `XF:07IDA-OP{Mir:M1}` | front-optics mirror |
| `SoftMirror` | Mirror | `XF:07ID1-OP{Mir:M3ABC}` | soft-branch mirror |
| `TenderMirror` | Mirror | `XF:07IDA-OP{Mir:L1}` | tender-branch mirror |
| `WhiteBeamSlit` | Slit | `XF:07IDA-OP{Slt:01}` | FOE beam-defining slit |
| `ExitSlit` | Slit | `XF:07ID2-BI{Slt:11}` | soft mono exit slit (resolution) |
| `HAXPESSlit` | Slit | `XF:07ID2-OP{Slt:12}` | tender HAXPES beam-defining slit |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (per-branch coupled) |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:07ID-BI{BPM:4}` | beam-position diagnostics |
| `RSoXSManipulator` | Manipulator | `XF:07ID2-ES1{Stg-Ax:}` | soft-scattering sample stage |
| `HAXPESManipulator` | Manipulator | `XF:07ID1-BI{HAX-Ax:}` | photoemission sample stage |
| `SampleTemperature` | TemperatureController | `XF:07ID2-ES1{TCtrl:1}LS336:` | Lakeshore thermal control |
| `ScatteringDetector` | Camera | `XF:07ID1-ES:1{GE:2}` | Greateyes CCD (RSoXS) |
| `ElectronAnalyzer` | ElectronAnalyzer | `XF:07ID-ES-SES` | Scienta SES (HAXPES) |
| `CalorimeterSpectrometer` | EnergyDispersiveSpectrometer | `XF:07ID-ES{UCAL}:` | TES microcalorimeter (NEXAFS) |
| `FluxMonitor` | FluxMonitor | `XF:07ID-ES1{DMR:I400-1}` | I0 / drain-current channels |
| `BeamStop` | BeamStop | `XF:07ID2-ES1{BS-Ax:1}` | RSoXS direct-beam stop |
| `SampleCamera` | Camera | `XF:07ID1-ES:1{Scr:4}` | on-axis sample viewing |
| `FastShutter` | Shutter | `XF:07ID2-ES1{FSh-Ax:1}` | endstation exposure shutter |
| `EndstationMotionController` | MotionController | (pending) | branch / endstation controllers |

Every family is in the catalog except the loose `BeamPositionMonitor` (held); the `ElectronAnalyzer` graduated this PR (2nd sighting after ESM); SST coins none. Notably the soft PGM reuses `GratingMonochromator` (graduated across SIX / CSX / ESM, a fourth sighting), the sample manipulators reuse `Manipulator` (graduated by ESM), and the microcalorimeter reuses `EnergyDispersiveSpectrometer` (graduated in #345), so SST is a clean reuse-and-reinforce deployment that exercises the soft-X-ray vocabulary at Site scale.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the SST team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator periods / ranges (EPU60, U42) | `SoftUndulator` / `TenderUndulator` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | all enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Branch-to-hutch endstation mapping | enclosures | `unknown-pending-confirmation` | (ENC-1) |
| PGM grating set and DCM crystal / ranges | `SoftMonochromator` / `TenderMonochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Live detector roster per endstation | `ScatteringDetector` / `ElectronAnalyzer` / `CalorimeterSpectrometer` | `unknown-pending-confirmation` | (DET-1) |
| Flux / beam-position channel maps | `FluxMonitor` / `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box models / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
