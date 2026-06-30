# Inventory

*The CORA Asset model for the operational core of IOS modelled today: the planned device tree and what still needs confirming.*

This cut models the `XF:23IDA` / `XF:23ID2-OP` optics and the `XF:23ID2-ES` / `XF:23ID2-BI` endstation; the ambient-pressure reaction cell and the sample-transfer load-lock are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/ios/beamline.yaml) descriptor.

IOS adds **no new family**: every device binds an existing catalog [Family](../../catalog/families.md). Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `IOS` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `IOS` | `Unit` | (root) | - | bound to the NSLS-II Site; 23-ID-2 branch of the canted straight |
| `Undulator_1` / `Undulator_2` | `Device` | InsertionDevice | 23-ID-A | two canted EPUs, the CSX straight (SRC-1, TOPO-1) |
| `Mirror_1` | `Device` | Mirror | 23-ID-A | front-end mirror M1A (OPT-1) |
| `Mirror_1b1` / `Mirror_1b2` | `Device` | Mirror | 23-ID-A | sector-A deflecting mirrors, M1B1 with feedback (OPT-1) |
| `FrontEndShutter` | `Device` | Shutter | 23-ID-A | front-end photon shutter |
| `Monochromator` | `Device` | GratingMonochromator | 23-ID-2 | VLS-PGM, 200-2200 eV; energy fly-scan (MONO-1) |
| `Mirror_3b` | `Device` | Mirror | 23-ID-2 | branch mirror M3B (OPT-1) |
| `DeflectingMirror` | `Device` | Mirror | 23-ID-2 | downstream deflecting mirror DM1 (OPT-1) |
| `KBMirror_Horizontal` / `KBMirror_Vertical` | `Device` | Mirror | 23-ID-2 | Kirkpatrick-Baez focusing pair (OPT-1) |
| `Slit_1` / `Slit_2` | `Device` | Slit | 23-ID-2 | branch slits (OPT-2) |
| `BranchShutter` | `Device` | Shutter | 23-ID-2 | branch photon shutter (PSS-1) |
| `SampleManipulator` | `Device` | Manipulator | 23-ID-2 | AP-PES four-axis stage (SAMPLE-1) |
| `XasSampleStage` | `Device` | LinearStage | 23-ID-2 | XAS-endstation translation (SAMPLE-1) |
| `SputterGun` | `Device` | GenericProbe | 23-ID-2 | surface-prep sputter / ion gun (SAMPLE-2) |
| `ElectronAnalyzer` | `Device` | ElectronAnalyzer | 23-ID-2 | SPECS hemispherical analyzer, AP-PES (DET-1) |
| `FluorescenceDetector` | `Device` | EnergyDispersiveSpectrometer | 23-ID-2 | Vortex silicon-drift detector + MCA (DET-2) |
| `FluorescenceArray` | `Device` | EnergyDispersiveSpectrometer | 23-ID-2 | Xspress3 four-channel silicon-drift (DET-2) |
| `Scaler` | `Device` | FluxMonitor | 23-ID-2 | electron-yield counting electronics (DET-3) |
| `IncidentFluxMonitor` | `Device` | FluxMonitor | 23-ID-2 | gold-mesh I0 reference (DET-3) |
| `DiagnosticCamera` | `Device` | Camera | 23-ID-2 | exit-slit YAG centroid camera |

Families reused from the catalog: `InsertionDevice`, `Mirror`, `Shutter`, `GratingMonochromator`, `Slit`, `Manipulator`, `LinearStage`, `GenericProbe`, `ElectronAnalyzer`, `EnergyDispersiveSpectrometer`, `FluxMonitor`, `Camera`. IOS introduces **no loose family of its own**.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Canted-straight topology | the root and source | `unknown-pending-confirmation` | (TOPO-1) |
| Hutch grouping of the PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| PSS permit signals | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| EPU type, period, polarization, edge table | `Undulator_1/2` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) and queue server | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PGM energy range and grating set | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | the mirrors and KB pair | `unknown-pending-confirmation` | (OPT-1) |
| Slit axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| Manipulator axes and sample transfer | `SampleManipulator`, `XasSampleStage` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Surface-prep ion-gun model | `SputterGun` | `unknown-pending-confirmation` | (SAMPLE-2) |
| The ambient-pressure cell, gas, and heating | the AP sample environment | `unknown-pending-confirmation` | (INSITU-1) |
| Analyzer model and pass-energy range | `ElectronAnalyzer` | `unknown-pending-confirmation` | (DET-1) |
| Fluorescence-detector models and channels | `FluorescenceDetector`, `FluorescenceArray` | `unknown-pending-confirmation` | (DET-2) |
| Electron-yield channel wiring | `Scaler`, `IncidentFluxMonitor` | `unknown-pending-confirmation` | (DET-3) |
| NEXAFS energy-scan mode | the energy sweep | `unknown-pending-confirmation` | (ENERGY-1) |
| Vacuum and cooling supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
