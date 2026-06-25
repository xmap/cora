# Inventory

*The CORA Asset model for the ARPES branch of ESM modelled today: the planned device tree and what still needs confirming.*

This cut models the `XF:21IDA/B/C` optics and the `XF:21ID1-ES` ARPES endstation; the XPEEM/LEEM branch and the simulated devices are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/esm/beamline.yaml) descriptor.

ESM introduces one new family (`ElectronAnalyzer`, since graduated once SST earned the 2nd SES), graduates `Manipulator` into the catalog (its 2nd UHV manipulator after SIX), and reuses the rest, including the graduated `GratingMonochromator` (its 3rd PGM). Control handles are filled from the profile collection; no vendor Models are bound.

## The Asset tree

Root Asset `ESM` (`tier = Unit`, `facility_code = nsls2`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `ESM` | `Unit` | (root) | - | bound to the NSLS-II Site; sector 21-ID |
| `Undulator_1` / `Undulator_2` | `Device` | InsertionDevice | 21-ID-A | EPU57 + EPU105 (SRC-1) |
| `Mirror_1` | `Device` | Mirror | 21-ID-A | first mirror M1 (OPT-1) |
| `PolarizationDiagnostic` | `Device` | GenericProbe | 21-ID-A | ESM Diagon polarization diagnostic (DIAG-1) |
| `FrontEndShutter` / `FOEShutter` | `Device` | Shutter | 21-ID-A | front-end + FOE shutters |
| `Monochromator` | `Device` | GratingMonochromator | 21-ID-B | plane-grating mono (3rd PGM) (MONO-1) |
| `Mirror_3` | `Device` | Mirror | 21-ID-B | hexapod mirror M3 (OPT-1) |
| `MonoSlit_Upstream/Downstream` | `Device` | Slit | 21-ID-B | PGM slits (OPT-2) |
| `MirrorSlit_3` | `Device` | Slit | 21-ID-B | M3 slit (OPT-2) |
| `Mirror_4A` | `Device` | Mirror | 21-ID-C | KB refocusing pair (OPT-1) |
| `Mirror_4B` | `Device` | Mirror | 21-ID-C | hexapod mirror M4B (OPT-1) |
| `ExitSlit_A` / `ExitSlit_B` | `Device` | Slit | 21-ID-C | branch exit slits, set resolution (OPT-2) |
| `PhotonShutter_A` / `PhotonShutter_B` | `Device` | Shutter | 21-ID-C | branch photon shutters |
| `SampleManipulator` | `Device` | Manipulator | 21-ID-D | LT six-axis UHV cryostat (graduates the Family) (SAMPLE-1) |
| `SampleTemperature` | `Device` | TemperatureController | 21-ID-D | Lakeshore cryostat (SAMPLE-1) |
| `ElectronAnalyzer` | `Device` | ElectronAnalyzer | 21-ID-D | Scienta SES hemispherical analyzer (ARPES-1) |
| `FluxMonitor_Upstream` / `FluxMonitor_Branch` | `Device` | FluxMonitor | 21-ID-D | QuadEM I0 monitors (DET-1) |

Families reused from the catalog: `InsertionDevice`, `Mirror`, `Slit`, `Shutter`, `GenericProbe`, `TemperatureController`, `FluxMonitor`, `GratingMonochromator` (3rd PGM), `Manipulator` (graduated with this deployment), and `ElectronAnalyzer` (graduated once SST earned the 2nd SES). No loose family remains.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Dual-EPU coordination, periods, polarization | `Undulator_1/2` | `unknown-pending-confirmation` | (SRC-1) |
| Hutch grouping of the PV zones | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| PSS permit signals | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| PGM energy range and grating set | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | the mirrors | `unknown-pending-confirmation` | (OPT-1) |
| Slit and exit-slit axis maps | the slits | `unknown-pending-confirmation` | (OPT-2) |
| Electron-analyzer model and controls | `ElectronAnalyzer` | `unknown-pending-confirmation` | (ARPES-1) |
| UHV manipulator prefix, axes, cryo range | `SampleManipulator`, `SampleTemperature` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Polarization-diagnostic classification | `PolarizationDiagnostic` | `unknown-pending-confirmation` | (DIAG-1) |
| Flux-monitor channels | the QuadEM monitors | `unknown-pending-confirmation` | (DET-1) |
| Vacuum and cryogen supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
