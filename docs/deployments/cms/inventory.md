# Inventory

*The CORA Asset model for the operational core of CMS modelled today: the planned device tree and what still needs confirming.*

This cut models the XF:11BMA optics and the XF:11BMB scattering / reflectivity endstation; the simulated devices, the viewing cameras, and the auxiliary analog I/O are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/cms/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. CMS, the NSLS-II twin of SMI, coins **no new Family and changes nothing in the catalog**: the scattering reuses the existing `Camera` / `Goniometer` / `Slit` / `BeamStop` / `FluxMonitor` / `Monochromator` / `Mirror` vocabulary, and the specular reflectivity (XR) is a Method over those, not a device (see [Model](model.md#what-makes-cms-new)). Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `CMS` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `CMS` | `Unit` | (root) | - | bound to the NSLS-II Site; 11-BM |
| `StorageRing` | `Device` | StorageRing (loose) | - | machine-level ring state, observe-only; bending-magnet source (MACHINE-1, SRC-1) |
| `Monochromator` | `Device` | Monochromator | cms-optics | double-multilayer monochromator (DMM), `XF:11BMA-OP{Mono:DMM-Ax:Bragg}` (MONO-1) |
| `ToroidalMirror` | `Device` | Mirror | cms-optics | FOE toroidal focusing mirror + bender, `XF:11BMA-OP{Mir:Tor}` (OPT-1) |
| `EllipticalMirror` | `Device` | Mirror | cms-optics | 1D elliptical focusing mirror, `XF:11BM1-OP{MDrive}` (OPT-1) |
| `FoeSlit` | `Device` | Slit | cms-optics | FOE four-blade defining slit, `XF:11BMA-OP{Slt:0}` (OPT-2) |
| `AttenuatorFoils` | `Device` | Filter | cms-optics | eight pneumatic absorber foils, `XF:11BMB-OP{Fltr:1-8}` (ATTN-1) |
| `BeamEnergy` | `Device` | PseudoAxis | cms-optics | incident-energy axis over the DMM Bragg angle (MONO-1) |
| `FoeFluxMonitor` | `Device` | FluxMonitor | cms-optics | FOE incident-flux quad electrometers, `XF:11BMA-BI{IM:1}` (DET-1) |
| `SampleGoniometer` | `Device` | Goniometer | cms-endstation | sample circles (x / y, sth incidence, schi, sphi), `XF:11BMB-ES{Chm:Smpl}` (SAMPLE-1) |
| `SurfaceStage` | `Device` | TiltStage | cms-endstation | thin-film surface-leveling sub-stage, `XF:11BMB-ES{SM:1}` (SAMPLE-1) |
| `SampleExchangeArm` | `Device` | LinearStage | cms-endstation | GIBar sample-exchange arm (x / y / z + yaw); no SampleExchanger Family coined (ROBOT-1) |
| `TemperatureStage` | `Device` | TemperatureController | cms-endstation | Linkam thermal / tensile stage (TEMP-1) |
| `SaxsDetector` | `Device` | Camera | cms-endstation | Pilatus 2M SAXS area detector + the XR detector, `XF:11BMB-ES{Det:PIL2M}` (DET-1, XR-1) |
| `WaxsDetector` | `Device` | Camera | cms-endstation | Pilatus 800K WAXS area detector, `XF:11BMB-ES{Det:PIL800K}` (DET-1) |
| `MaxsDetector` | `Device` | Camera | cms-endstation | second Pilatus 800K at the MAXS position, `XF:11BMB-ES{Det:PIL800K2}` (DET-1) |
| `DetectorStage` | `Device` | LinearStage | cms-endstation | SAXS / WAXS / MAXS detector translations + the telescoping flight path (DET-1) |
| `Beamstop` | `Device` | BeamStop | cms-endstation | SAXS beamstop (x / y / phi), `XF:11BMB-ES{BS:SAXS}` (DET-1) |
| `EndstationFluxMonitor` | `Device` | FluxMonitor | cms-endstation | ion chamber + scintillation counter + electrometer, `XF:11BMB-BI{IM:2-4}` (DET-1) |
| `BeamPositionMonitor` | `Device` | BeamPositionMonitor (loose) | cms-endstation | BIM5 four-quadrant diamond-diode BPM, `XF:11BMB-BI{BPM:1}` (DIAG-1) |
| `SupportTable` | `Device` | Table | cms-endstation | endstation modular support table on three jacks, `XF:11BMB-ES{Tbl}` |

Families reused from the catalog: `Monochromator`, `Mirror`, `Slit`, `Filter`, `PseudoAxis`, `Goniometer`, `TiltStage`, `LinearStage`, `TemperatureController`, `Camera`, `BeamStop`, `FluxMonitor`, `Table`. Loose families reused from siblings: `StorageRing` (supply), `BeamPositionMonitor` (already held under review, DIAG-1). No new family is coined and nothing graduates.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Optics-vs-endstation hutch grouping | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Bending-magnet versus wiggler source | the source | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| DMM d-spacing, energy range, partition rule | `Monochromator`, `BeamEnergy` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and bend | `ToroidalMirror`, `EllipticalMirror` | `unknown-pending-confirmation` | (OPT-1) |
| Slit blade-axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| Attenuator foil set and catalog home | `AttenuatorFoils` | `unknown-pending-confirmation` | (ATTN-1) |
| Goniometer axes, sth / schi swap, rebinding | `SampleGoniometer`, `SurfaceStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Sample-exchange arm Family | `SampleExchangeArm` | `unknown-pending-confirmation` | (ROBOT-1) |
| Linkam range and tensile axis | `TemperatureStage` | `unknown-pending-confirmation` | (TEMP-1) |
| Detector assignment, distances, channel map | `SaxsDetector`, `WaxsDetector`, `MaxsDetector`, `EndstationFluxMonitor` | `unknown-pending-confirmation` | (DET-1) |
| Reflectivity (XR) region-of-interest mechanism | `SaxsDetector` | `unknown-pending-confirmation` | (XR-1) |
| Vacuum extent and cooling supply | `resources` | `unknown-pending-confirmation` | (SUP-1) |
