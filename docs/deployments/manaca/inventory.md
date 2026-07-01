# Inventory

*The CORA Asset model for the operational core of MANACA modelled today: the planned device tree and what still needs confirming.*

This cut models the optics (the storage-ring state, the front-end shutter, the monochromator, the energy axis, the attenuators) and the MX experiment endstation (the goniometer, the cryostream, the backlight, the beamstop, the area detector and its stage, the on-axis camera, the flux monitor). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/manaca/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits. MANACA, Sirius's first MX beamline (after the [MOGNO](../mogno/index.md) tomography scaffold), **coins no new Family and changes nothing in the catalog**: it is an MX beamline that reuses the macromolecular-crystallography Families graduated at i03 and exercised at FMX / AMX / MX3. LNLS publishes no per-beamline EPICS PV manifest, so no control handles and no vendor Models are bound.

## The Asset tree

Root Asset `MANACA` (`tier = Unit`, `facility_code = sirius`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `MANACA` | `Unit` | (root) | - | bound to the Sirius Site |
| `StorageRing` | `Device` | StorageRing (loose) | - | Sirius 3 GeV ring state, observe-only (MACHINE-1) |
| `WhiteBeamShutter` | `Device` | Shutter | manaca-optics | front-end PSS photon shutter (PSS-1) |
| `Monochromator` | `Device` | Monochromator | manaca-optics | monochromator, 5-20 keV; crystal type pending (MONO-1) |
| `EnergyAxis` | `Device` | PseudoAxis | manaca-optics | master energy axis the monochromator tracks (ENERGY-1) |
| `Attenuators` | `Device` | Filter | manaca-optics | attenuator / transmission unit; foil set pending (FILT-1) |
| `Goniometer` | `Device` | Goniometer | manaca-experiment | MX goniometer, serial / room-temperature; axes pending (GONIO-1) |
| `SampleTemperature` | `Device` | TemperatureController | manaca-experiment | cryostream sample cooling (TEMP-1) |
| `Backlight` | `Device` | Backlight | manaca-experiment | on-axis viewing / centring illumination (DET-1) |
| `BeamStop` | `Device` | BeamStop | manaca-experiment | direct-beam stop at the sample (SAMPLE-1) |
| `AreaDetector` | `Device` | Camera | manaca-experiment | MX area detector (Pilatus / Eiger-class); model not published (DET-1) |
| `DetectorStage` | `Device` | LinearStage | manaca-experiment | detector translation setting sample-to-detector distance (DET-1) |
| `FluxMonitor` | `Device` | FluxMonitor | manaca-experiment | incident-flux monitor (DIAG-1) |
| `OnAxisCamera` | `Device` | Camera | manaca-experiment | on-axis viewing camera for centring (DET-1) |

Families reused from the catalog: `Shutter`, `Monochromator`, `PseudoAxis`, `Filter`, `Goniometer`, `TemperatureController`, `BeamStop`, `Camera`, `LinearStage`, `FluxMonitor`, `Backlight` (the on-axis illumination affordance, graduated across the MX / imaging fleet, DET-1). Loose families reused from siblings: `StorageRing` (machine-state observe-only). No new family is coined and nothing graduates. The automated 48-pin sample changer is modelled as a deferred sample-exchange Procedure, not a device (ROBOT-1).

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Hutch grouping of the endstation | the enclosures | `unknown-pending-confirmation` | (ENC-1) |
| Undulator period and parameters | `StorageRing` | `unknown-pending-confirmation` | (SRC-1) |
| Storage-ring state read | `StorageRing` | `unknown-pending-confirmation` | (MACHINE-1) |
| Monochromator crystal type and handles | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Energy-scan-as-measurement (anomalous MX) | `EnergyAxis` | `unknown-pending-confirmation` | (ENERGY-1) |
| Attenuator foil set | `Attenuators` | `unknown-pending-confirmation` | (FILT-1) |
| Focusing mirrors / slits presence | the optics | `unknown-pending-confirmation` | (OPT-1) |
| Goniometer geometry and axes | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| Cryostream sensor / setpoint handles | `SampleTemperature` | `unknown-pending-confirmation` | (TEMP-1) |
| Beamstop axes and sample environment | `BeamStop` | `unknown-pending-confirmation` | (SAMPLE-1) |
| 48-pin sample-changer loop | the sample exchange | `unknown-pending-confirmation` | (ROBOT-1) |
| Area-detector model, stage, on-axis camera | `AreaDetector`, `DetectorStage`, `OnAxisCamera` | `unknown-pending-confirmation` | (DET-1) |
| Flux-monitor handles | `FluxMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| EPICS / MXCuBE control handles | all devices | `unknown-pending-confirmation` | (CTRL-1) |
| Sirius PSS permit signals and shutters | the enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Vacuum extent and supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
