# Inventory

*The CORA Asset model for MX3: the device tree read from the device library and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/mx3/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md). Most carry real EPICS PVs (verified against `AustralianSynchrotron/mx3-beamline-library`); three do not, because they sit on non-EPICS control planes (see [Controls](equipment/controls.md)): the `Goniometer` (MXCuBE Exporter), the `EigerDetector` (SIMPLON REST), and the MD3 `Backlight` / `BeamStop` (Exporter). No vendor Model is bound. MX3 introduces **no new catalog family**: every device reuses an existing Family, notably the graduated `Goniometer` (the i03 MX precedent). Three devices bind loose families, all allowlisted: `StorageRing` (the ring-current monitor), `BeamPositionMonitor`, and `Backlight`; see [Model](model.md#deliberately-not-here-yet).

## The Asset tree

Root Asset `MX3` (`tier = Unit`, `facility_code = as`); sub-systems nest below by `parent_id`.

| Asset | Family | PV / interface | What it is |
| --- | --- | --- | --- |
| `MX3` | (root) | `MX3*` | bound to the Australian Synchrotron Site |
| `StorageRing` | StorageRing (loose) | `SR11BCM01:CURRENT_MONITOR` | storage-ring current monitor (source repr) |
| `WhiteBeamShutter` | Shutter | `MX3FE01SHT01` | front-end PSS photon shutter |
| `Monochromator` | Monochromator | `MX3MONO01:` | double-multilayer mono (stripe-selectable) |
| `EnergyAxis` | PseudoAxis | `MX3:MASTER_ENERGY_SP` | master energy setpoint |
| `Attenuators` | Filter | `MX3FLT05:` | attenuator / transmission filter wheel |
| `Goniometer` | Goniometer | MXCuBE Exporter (no PV) | MD3 microdiffractometer (omega / kappa / phi) |
| `SampleTemperature` | TemperatureController | `MX3CRYOJET01:` | cryojet sample cooling |
| `Backlight` | Backlight (loose) | MD3 Exporter (no PV) | MD3 sample backlight |
| `BeamStop` | BeamStop | MD3 Exporter (no PV) | MD3 beamstop (x / y / z) |
| `EigerDetector` | Camera | SIMPLON REST (no PV) | DECTRIS Eiger (16M / 4M) |
| `DetectorStage` | LinearStage | `MX3STG03MOT04` | detector translation (sample-detector distance) |
| `FluxMonitor` | FluxMonitor | `MX3FLUXIOC:FLUX` | incident-flux monitor |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `MX3DAQIOC04:` | beam-position monitor + PID steering |
| `OAVCamera` | Camera | `MX3MD3ZOOM0` | on-axis viewing camera (BlackFly) |
| `MonoBeamShutter` | Shutter | `MX3BLSH01SHT01` | mono-beam PSS shutter |
| `EndstationMotionController` | MotionController | `MX3STG` (PMAC) | Power Brick stage controllers |

Every family is in the catalog except the loose `StorageRing`, `BeamPositionMonitor`, and `Backlight` (all shared and allowlisted); MX3 coins none. Notably the MD3 goniometer reuses the graduated `Goniometer` family (the i03 Smargon precedent), the cryojet reuses `TemperatureController` (graduated in #350), and the detectors reuse `Camera`, so MX3 is a clean reuse deployment whose novelty is the Site and its control plane, not its device vocabulary. The ISARA sample robot is not a device here: it is a deferred autonomous-exchange Procedure (ROBOT-1).

## Pending confirmations

Every value below is read from the device library or inferred, awaiting the team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Insertion-device / source PV | `StorageRing` (source repr) | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| DMM stripes / range and attenuator foils | `Monochromator` / `Attenuators` | `unknown-pending-confirmation` | (DCM-1) |
| MD3 Exporter host / port and full axis set | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| Eiger model and SIMPLON REST endpoint | `EigerDetector` | `unknown-pending-confirmation` | (DET-1) |
| Flux / beam-position channel maps | `FluxMonitor` / `BeamPositionMonitor` | `unknown-pending-confirmation` | (DIAG-1) |
| Beam-steering controller device boundary | `BeamPositionMonitor` | `unknown-pending-confirmation` | (STEER-1) |
| Motion-controller box firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
