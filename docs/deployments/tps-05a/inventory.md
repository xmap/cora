# Inventory

*The CORA Asset model for TPS 05A: the device tree read from the public facility pages and inherited from the [TPS 07A](../tps-07a/inventory.md) reading, and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/tps-05a/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md), the same set as TPS 07A. Every device is on the EPICS floor reached through the EPICS Device Handler Server. Unlike 07A, the 05A PV namespace is **inferred (`05a:` / `05a-ES:`), not verified against a control tree** (PV-1), so no PV record is asserted, this is the fleet's most conservative PV posture, set by the thin source. No vendor Model is bound. TPS 05A introduces **no new catalog family**: every device reuses an existing Family, including the graduated `BeamPositionMonitor` (a catalog Family presenting `Sensor`, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux). One device binds a loose family, allowlisted: `StorageRing`; see [Model](model.md#deliberately-not-here-yet).

## The Asset tree

Root Asset `TPS 05A` (`tier = Unit`, `facility_code = nsrrc`); sub-systems nest below by `parent_id`.

| Asset | Family | PV / interface | What it is |
| --- | --- | --- | --- |
| `TPS 05A` | (root) | `05a:` (inferred) | bound to the NSRRC Site |
| `StorageRing` | StorageRing (loose) | EPICS (PV pending) | storage-ring current monitor (source repr) |
| `WhiteBeamShutter` | Shutter | EPICS (PV pending) | front-end PSS photon shutter |
| `Monochromator` | Monochromator | EPICS (PV pending) | double-crystal monochromator (~5.7-20 keV) |
| `EnergyAxis` | PseudoAxis | EPICS (PV pending) | master energy setpoint |
| `Attenuators` | Filter | EPICS (PV pending) | attenuator / transmission filter |
| `KBMirrors` | Mirror | EPICS (PV pending) | focusing mirrors |
| `Goniometer` | Goniometer | EPICS via DHS (`05a-ES:` inferred) | MD3 microdiffractometer (omega / kappa / phi) |
| `SampleTemperature` | TemperatureController | EPICS (PV pending) | cryostream sample cooling |
| `BeamStop` | BeamStop | EPICS (PV pending) | beamstop at the sample |
| `EigerDetector` | Camera | DCSS workflow over EPICS | DECTRIS EIGER2 X 9M |
| `DetectorStage` | LinearStage | EPICS (PV pending) | detector translation |
| `BeamPositionMonitor` | BeamPositionMonitor | EPICS (PV pending) | beam-position diagnostic |
| `OAVCamera` | Camera | EPICS (PV pending) | on-axis viewing camera |
| `FastShutter` | Shutter | EPICS (PV pending) | per-oscillation exposure shutter |
| `EndstationMotionController` | MotionController | EPICS via DHS | stage motion controllers |

Every family is in the catalog except the loose `StorageRing` (shared and allowlisted); the `BeamPositionMonitor` binds the graduated catalog Family (presents `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux), and TPS 05A coins none. The Asset tree is the [TPS 07A](../tps-07a/inventory.md#the-asset-tree) tree with the EIGER2 sized at 9M instead of 16M, a per-Asset fact, not a vocabulary change. The ISARA sample robot is not a device here: it is a deferred autonomous-exchange Procedure (ROBOT-1).

## Pending confirmations

TPS 05A carries **more** pending values than 07A because its source is thinner (no dedicated control tree). Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| EPICS PV namespace (`05a:` / `05a-ES:` inferred) | all devices | `unknown-pending-confirmation` | (PV-1) |
| Insertion-device / source PV | `StorageRing` (source repr) | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| DCM crystal cut / range and attenuator foils | `Monochromator` / `Attenuators` | `unknown-pending-confirmation` | (DCM-1) |
| Focusing-mirror configuration, spot size, PVs | `KBMirrors` | `unknown-pending-confirmation` | (OPT-1) |
| MD3 axis PV records and DCSS-vs-MXCuBE | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| EIGER2 X 9M detector PVs and SIMPLON endpoint | `EigerDetector` | `unknown-pending-confirmation` | (DET-1) |
| Cryostream vendor and PV | `SampleTemperature` | `unknown-pending-confirmation` | (ENV-1) |
| Diagnostic channel maps / PVs | `BeamPositionMonitor` / `OAVCamera` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
| Energy scanned (anomalous / MAD) vs fixed | `EnergyAxis` | `unknown-pending-confirmation` | (ENERGY-1) |
