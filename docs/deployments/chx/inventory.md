# Inventory

*The CORA Asset model for CHX: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/chx/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/chx-profile-collection`). No vendor Model is bound: part numbers are not in the profile collection. CHX introduces **no new catalog family**: every device reuses an existing Family, including the ones recently graduated from earlier reverse-engineered deployments (`Camera` for the Eiger detectors, `FluxMonitor` for the flux counter, `TemperatureController` for the thermal stage, `EnergyDispersiveSpectrometer` for the occasional fluorescence detector). Two devices bind loose families shared across deployments and held for gate-review: the compound-refractive-lens `Transfocator` (4-ID, 8-ID, 9-ID, i22) and the `BeamPositionMonitor` (4-ID, 8-ID, 9-ID), both recorded in the promotion-review register (see [Model](model.md#deliberately-not-here-yet)).

## The Asset tree

Root Asset `CHX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `CHX` | (root) | `XF:11ID*` | bound to the NSLS-II Site |
| `Source` | InsertionDevice | `SR:C11-ID:G1{IVU20:1}` | IVU20 in-vacuum undulator |
| `FrontEndShutter` | Shutter | `XF:11ID-PPS{Sh:FE}` | front-end photon shutter |
| `Monochromator` | Monochromator | `XF:11IDA-OP{Mono:DCM}` | silicon double-crystal monochromator |
| `MultilayerMonochromator` | Monochromator | `XF:11IDA-OP{Mono:DMM}` | double-multilayer mono (high coherent flux) |
| `HorizontalMirror` | Mirror | `XF:11IDA-OP{Mir:HDM}` | horizontal-deflecting focusing mirror |
| `Transfocator` | Transfocator (loose) | `XF:11IDA-OP{Lens:}` | compound-refractive-lens focusing stack |
| `PinkBeamSlit` | Slit | `XF:11IDA-OP{Slt:PB}` | pink-beam-defining slit |
| `MonoBeamSlit` | Slit | `XF:11IDA-OP{Slt:MB}` | coherence-matched mono-beam slit |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (DCM energy axis) |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `XF:11IDA-BI{Bpm:1}` | beam-position monitor and electrometer |
| `BeamDefiningSlit` | Slit | `XF:11IDB-OP{Slt:BDS}` | endstation coherence-defining slit |
| `GuardSlit` | Slit | `XF:11IDB-OP{Slt:Guard}` | guard slit (parasitic-scatter clean-up) |
| `GrazingIncidenceMirror` | Mirror | `XF:11IDB-OP{Mir:GI}` | grazing-incidence mirror (GISAXS) |
| `SampleStage` | LinearStage | `XF:11IDB-ES{Dif-Ax:}` | sample stack on the diffractometer base |
| `SampleTemperature` | TemperatureController | `XF:11ID-ES{LINKAM}:` | Linkam thermal / tensile stage |
| `Eiger4M` | Camera | `XF:11IDB-ES{Det:Eig4M}` | Eiger 4M, primary XPCS detector |
| `Eiger1M` | Camera | `XF:11IDB-ES{Det:Eig1M}` | Eiger 1M pixel detector |
| `Eiger500K` | Camera | `XF:11IDB-ES{Det:Eig500K}` | Eiger 500K pixel detector |
| `SAXSDetectorStage` | LinearStage | `XF:11IDB-ES{Det:SAXS}` | transverse detector centering (X/Y) |
| `SAXSBeamStop` | BeamStop | `XF:11IDB-ES{BS:SAXS}` | direct-beam stop ahead of the detector |
| `FluxCounter` | FluxMonitor | `XF:11IDB-ES{Sclr:1}` | scaler flux channels (I0) |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:11IDB-ES{Xsp:1}` | Xspress3 (anomalous / element-sensitive) |
| `BeamViewingCamera` | Camera | `XF:11IDB-BI{Cam:10}` | on-axis beam-viewing camera (OAV) |
| `Zebra` | TimingController | `XF:11IDB-ES{Zebra}` | fast-shutter / frame trigger box |
| `EndstationMotionController` | MotionController | (pending) | sample / optics motion controllers |

Every family is in the catalog except the loose `Transfocator` and `BeamPositionMonitor` (both shared and held); CHX coins none. Notably the area detectors reuse `Camera` (the Diamond Eiger-to-Camera precedent), the flux counter reuses `FluxMonitor` (graduated in #353), the thermal stage reuses `TemperatureController` (graduated in #350), and the fluorescence detector reuses `EnergyDispersiveSpectrometer` (graduated in #345), so CHX is a clean reuse-and-reinforce deployment.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the CHX team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Undulator period / gap range | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| DCM cryo detail / range (Si(111) cut is read from source) and DMM coating | `Monochromator` / `MultilayerMonochromator` | `unknown-pending-confirmation` | (DCM-1) |
| Focusing-optic catalog home; transfocator and kinoform lens material / count | `Transfocator` | `unknown-pending-confirmation` | (CRL-1) |
| Whether GISAXS is a live routine | `GrazingIncidenceMirror` | `unknown-pending-confirmation` | (GI-1) |
| Diffractometer axis set; Goniometer / Assembly modelling | `SampleStage` | `unknown-pending-confirmation` | (STAGE-1) |
| Primary Eiger, whether an along-beam distance stage exists, Xspress3 element count | `Eiger4M` / `SAXSDetectorStage` / `FluorescenceSpectrometer` | `unknown-pending-confirmation` | (DET-1) |
| Live beam-viewing camera set | `BeamViewingCamera` | `unknown-pending-confirmation` | (CAM-1) |
| Scaler flux / BPM electrometer channel map | `FluxCounter` / `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| XPCS exposure-gating chain (Zebra / delay-gen / fast shutter) | `Zebra` | `unknown-pending-confirmation` | (TIMING-1) |
| Motion-controller box models / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
