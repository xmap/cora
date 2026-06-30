# Inventory

*The CORA Asset model for PDF: the device tree read from the profile collection and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/pdf/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md) and carry real EPICS PVs (verified against `NSLS2/pdf-profile-collection` and `NSLS2/pdftools`). No vendor Model is bound: part numbers are not in the profile collection. PDF introduces **no new catalog family**: every device reuses an existing Family. Most are the same Families its twin [XPD](../xpd/inventory.md) carries (`Camera` for the flat-panel and pixel detectors, `FluxMonitor` for the photodiode, `TemperatureController` for the thermal cluster, `Monochromator` for the high-energy Laue mono, `Mirror` for the focusing mirror); the capillary `Goniometer` spinner and the `BeamStop` reuse existing Families that XPD does not happen to bind. One loose family is bound: the `StorageRing` supply observation (machine state, never an Asset Family).

## The Asset tree

Root Asset `PDF` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Family | PV (verified) | What it is |
| --- | --- | --- | --- |
| `PDF` | (root) | `XF:28ID1*` | bound to the NSLS-II Site |
| `Source` | InsertionDevice | (no PV in config) | shared 28-ID damping wiggler |
| `StorageRing` | StorageRing (loose) | `SR:OPS-BI{DCCT:1}` | storage-ring current readback (machine state) |
| `Monochromator` | Monochromator | `XF:28ID1A-OP{Mono:SBM}` | side-bounce (single-Laue) monochromator |
| `VerticalFocusingMirror` | Mirror | `XF:28ID1A-OP{Mir:VFM}` | vertical focusing mirror (benders) |
| `WhiteBeamSlit` | Slit | `XF:28ID1A-OP{Slt:0}` | white-beam-defining slit |
| `EnergyAxis` | PseudoAxis | (computed) | master energy (side-bounce mono) |
| `CleanupSlit` | Slit | `XF:28ID1B-OP{Slt:AS}` | endstation cleanup / guard slit |
| `FastShutter` | Shutter | `XF:28ID1B-OP{PSh:1}` | fast exposure shutter |
| `SpinnerGoniohead` | Goniometer | `XF:28ID1B-ES{Stg:Smpl}` | capillary-spinner sample goniohead |
| `SampleEnvironmentStage` | LinearStage | `XF:28ID1B-ES{Env:1}` | sample-environment positioning stage |
| `SampleTemperature` | TemperatureController | `XF:28ID1-ES:1{Env:01}` | cryostream / cryostat / furnace cluster |
| `AreaDetector` | Camera | `XF:28ID1-ES{Det:PE1}` | PerkinElmer flat panel (primary PDF detector) |
| `PixelDetector` | Camera | `XF:28ID1-ES{Det:Pilatus}` | Pilatus photon-counting pixel detector |
| `DetectorStage1` | LinearStage | `XF:28ID1B-ES{Det:1}` | first detector tower (static distance) |
| `DetectorStage2` | LinearStage | `XF:28ID1B-ES{Det:2}` | second detector tower (moving distance) |
| `BeamStop` | BeamStop | `XF:28ID1B-ES{BS:1}` | direct-beam stop |
| `FluxMonitor` | FluxMonitor | `XF:28ID1B-OP{Det:1-Det:2}` | background photodiode (I0) |
| `EndstationMotionController` | MotionController | (pending) | optics / endstation / detector-tower motion |

Every family is in the catalog except the loose `StorageRing` supply; PDF coins none. Notably the area detectors reuse `Camera` (the flat-panel precedent XPD already carries), the thermal cluster reuses `TemperatureController` (graduated in #350, the same Family Diamond i11 graduated for variable-temperature powder work), the photodiode reuses `FluxMonitor` (graduated in #353), and the spinner reuses `Goniometer`, so PDF is a clean reuse-and-reinforce deployment, the twin of XPD.

## Pending confirmations

Every value below is read from the profile collection or inferred, awaiting the PDF team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Damping-wiggler identity and parameters | `Source` | `unknown-pending-confirmation` | (SRC-1) |
| PSS permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Side-bounce mono crystal cut and energy range | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Whether incident energy is ever scanned as the measurement | `EnergyAxis` | `unknown-pending-confirmation` | (ENERGY-1) |
| Full spinner / analyzer axis set; Goniometer vs Assembly modelling | `SpinnerGoniohead` | `unknown-pending-confirmation` | (STAGE-1) |
| Which thermal units are live (cryostream make, cryostat, furnace) | `SampleTemperature` | `unknown-pending-confirmation` | (TEMP-1) |
| The gas-handling and humidity rig (present in source, not modelled) | `SampleEnvironmentStage` | `unknown-pending-confirmation` | (ENV-1) |
| Which panels are live vs the spare set | `AreaDetector` / `PixelDetector` | `unknown-pending-confirmation` | (DET-1) |
| The two-detector / two-distance geometry and near / far merge | `DetectorStage1` / `DetectorStage2` | `unknown-pending-confirmation` | (DIST-1) |
| Photodiode / flux channel map | `FluxMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box models / firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
| Whether the powder / total-scattering Methods enter the catalog | techniques | `unknown-pending-confirmation` | (TECH-1) |
