# Inventory

*The CORA Asset model for the operational core of SIX modelled today: the planned device tree and what still needs confirming.*

This cut models the `XF:02IDA/B/C` optics and the `XF:02IDD-ES` RIXS endstation; the legacy end-station PGM and the simulated devices are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/six/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. SIX, as the first soft X-ray beamline, introduces three device classes no existing Family covers: they bind loose families held at n=1 and graduate nothing (see [Model](model.md#new-loose-families)). Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `SIX` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `SIX` | `Unit` | (root) | - | bound to the NSLS-II Site; sector 2-ID |
| `Undulator` | `Device` | InsertionDevice | 2-ID-A | EPU, gap + polarization phase (SRC-1) |
| `Mirror_1` | `Device` | Mirror | 2-ID-A | first mirror M1 (OPT-1) |
| `FrontEndSlit` | `Device` | Slit | 2-ID-A | front-end baffle slit (OPT-2) |
| `PolarizationDiagnostic` | `Device` | GenericProbe | 2-ID-A | DIAGON polarization diagnostic (DIAG-1) |
| `FrontEndShutter` / `PhotonShutter_A` | `Device` | Shutter | 2-ID-A | front-end + 2-ID-A shutters |
| `Monochromator` | `Device` | GratingMonochromator (loose) | 2-ID-B | plane-grating mono, 3 gratings (MONO-1) |
| `MonoSlit_Upstream/Downstream` | `Device` | Slit | 2-ID-B | PGM baffle slits (OPT-2) |
| `PhotonShutter_B` | `Device` | Shutter | 2-ID-B | 2-ID-B photon shutter |
| `Mirror_3` / `Mirror_4` | `Device` | Mirror | 2-ID-C | hexapod refocusing mirrors (OPT-1) |
| `MirrorSlit_3` / `MirrorSlit_4` | `Device` | Slit | 2-ID-C | refocusing-mirror slits (OPT-2) |
| `ExitSlit` | `Device` | Slit | 2-ID-C | exit slit, sets energy resolution (OPT-2) |
| `SampleManipulator` | `Device` | Manipulator (loose) | 2-ID-D | UHV cryostat x/y/z/theta (SAMPLE-1) |
| `SampleChamber` | `Device` | LinearStage | 2-ID-D | sample-chamber pivot translation (RIXS-1) |
| `Mirror_5` / `Mirror_6` | `Device` | Mirror | 2-ID-D | endstation mirrors (OPT-1) |
| `MirrorMask_5` | `Device` | Aperture | 2-ID-D | single-axis mask at M5 (OPT-2) |
| `SampleTemperature` | `Device` | TemperatureController | 2-ID-D | Lakeshore 336 (SAMPLE-1) |
| `RIXSSpectrometer` | `Device` | SpectrometerArm (loose) | 2-ID-D | energy-dispersive RIXS arm, 3 chambers (RIXS-1) |
| `RIXSCamera` | `Device` | Camera | 2-ID-D | photon-counting RIXS camera (RIXS-2, DET-1) |
| `DetectorSlit` | `Device` | Slit | 2-ID-D | detector-chamber slit (OPT-2) |
| `Scaler` / `Electrometer` | `Device` | FluxMonitor | 2-ID-D | counting scaler + Femto electrometer (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Mirror`, `Slit`, `Shutter`, `GenericProbe`, `Aperture`, `LinearStage`, `TemperatureController`, `Camera`, `FluxMonitor`. Held loose at n=1 (new to the catalog, graduate nothing): `GratingMonochromator`, `SpectrometerArm`, `Manipulator`.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Canted-straight / sibling beamline | the root and source | `unknown-pending-confirmation` | (TOPO-1) |
| Hutch grouping of the PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PSS permit signals | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| EPU type, period, polarization model | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| PGM energy range and grating set | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | the mirrors | `unknown-pending-confirmation` | (OPT-1) |
| Slit and exit-slit axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| RIXS spectrometer-arm geometry | `RIXSSpectrometer`, `SampleChamber` | `unknown-pending-confirmation` | (RIXS-1) |
| RIXS-camera photon-counting model | `RIXSCamera` | `unknown-pending-confirmation` | (RIXS-2) |
| Cryostat-manipulator UHV / cryo spec | `SampleManipulator`, `SampleTemperature` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Counter and electrometer channels | `Scaler`, `Electrometer`, `RIXSCamera` | `unknown-pending-confirmation` | (DET-1) |
| Polarization-diagnostic classification | `PolarizationDiagnostic` | `unknown-pending-confirmation` | (DIAG-1) |
| Vacuum and cryogen supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
