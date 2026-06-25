# Inventory

*The CORA Asset model for the operational core of CSX modelled today: the planned device tree and what still needs confirming.*

This cut models the `XF:23IDA` / `XF:23ID1-OP` optics and the `XF:23ID1-ES` TARDIS endstation; the fine piezo nanopositioner and the simulated devices are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/csx/beamline.yaml) descriptor.

CSX adds **no new family**: every device binds an existing catalog [Family](../../catalog/families.md), including `GratingMonochromator`, which graduates into the catalog with this deployment (the second soft X-ray PGM after SIX). Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `CSX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `CSX` | `Unit` | (root) | - | bound to the NSLS-II Site; 23-ID-1 branch of the canted straight |
| `Undulator_1` / `Undulator_2` | `Device` | InsertionDevice | 23-ID-A | two canted EPUs (SRC-1) |
| `Mirror_1` | `Device` | Mirror | 23-ID-A | FMB hexapod front-end mirror M1A (OPT-1) |
| `FrontEndShutter` | `Device` | Shutter | 23-ID-A | front-end photon shutter |
| `Monochromator` | `Device` | GratingMonochromator | 23-ID-1 | VLS-PGM, 200-2200 eV; graduates the Family (MONO-1) |
| `Mirror_3` | `Device` | Mirror | 23-ID-1 | branch refocusing mirror M3A (OPT-1) |
| `Slit_1` / `Slit_2` / `Slit_3` | `Device` | Slit | 23-ID-1 | branch slits (OPT-2) |
| `Diffractometer` | `Device` | Goniometer | 23-ID-1 | TARDIS E6C circles; composes the Diffractometer Assembly (DIFF-1) |
| `ReciprocalSpace` | `Device` | PseudoAxis | 23-ID-1 | hkl reciprocal-space layer (DIFF-2) |
| `SampleStage` | `Device` | LinearStage | 23-ID-1 | sample translation + holography stage (SAMPLE-1) |
| `SampleTemperature` | `Device` | TemperatureController | 23-ID-1 | Lakeshore 336 cryostat (SAMPLE-1) |
| `FastCCD` / `AxisDetector` | `Device` | Camera | 23-ID-1 | coherent-scattering area detectors (DET-1) |
| `DiagnosticCamera` | `Device` | Camera | 23-ID-1 | beam-view diagnostic camera |
| `Scaler` | `Device` | FluxMonitor | 23-ID-1 | scaler / MCS counting electronics (DET-1) |
| `DiffractometerDiode` | `Device` | GenericProbe | 23-ID-1 | diffractometer absorber / diode (DET-1) |
| `FastShutter` | `Device` | Shutter | 23-ID-1 | exposure fast shutter |

Families reused from the catalog: `InsertionDevice`, `Mirror`, `GratingMonochromator` (graduated with this deployment), `Slit`, `Shutter`, `Goniometer`, `PseudoAxis`, `LinearStage`, `TemperatureController`, `Camera`, `FluxMonitor`, `GenericProbe`. CSX introduces **no loose family of its own**.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Canted-straight topology | the root and source | `unknown-pending-confirmation` | (TOPO-1) |
| Hutch grouping of the PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| PSS permit signals | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| EPU type, period, polarization model | `Undulator_1/2` | `unknown-pending-confirmation` | (SRC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PGM energy range and grating set | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | `Mirror_1`, `Mirror_3` | `unknown-pending-confirmation` | (OPT-1) |
| Slit axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| TARDIS E6C circle roles | `Diffractometer` | `unknown-pending-confirmation` | (DIFF-1) |
| Reciprocal-space pseudo-axis model | `ReciprocalSpace` | `unknown-pending-confirmation` | (DIFF-2) |
| Sample-stage and cryostat spec | `SampleStage`, `SampleTemperature` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Detector models and channels | the detectors and scaler | `unknown-pending-confirmation` | (DET-1) |
| Vacuum and cryogen supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
