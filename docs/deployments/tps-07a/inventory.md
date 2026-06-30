# Inventory

*The CORA Asset model for TPS 07A: the device tree read from the public control trees and what still needs confirming.*

This is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md), [Detector](equipment/detector.md), and [Controls](equipment/controls.md) pages. It is generated-honest: authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/tps-07a/beamline.yaml) descriptor the Source page renders from.

Devices bind to catalog [Families](../../catalog/families.md). Every device is on the EPICS floor (the `07a:` / `07a-ES:` namespace) reached through the EPICS Device Handler Server; the EPICS PV *namespace* is verified against the [`light911/NSRRC_TPS07A`](https://github.com/light911/NSRRC_TPS07A) control tree, but per-device PV *record* strings are not, so they are carried pending (a deliberate contrast with [MX3](../mx3/inventory.md), whose literal PVs were file-verified against a device library). No vendor Model is bound. TPS 07A introduces **no new catalog family**: every device reuses an existing Family, notably the graduated `Goniometer` (the i03 / MX3 MX precedent). Two devices bind loose families, both allowlisted: `StorageRing` (the ring-current monitor) and `BeamPositionMonitor`; see [Model](model.md#deliberately-not-here-yet).

## The Asset tree

Root Asset `TPS 07A` (`tier = Unit`, `facility_code = nsrrc`); sub-systems nest below by `parent_id`.

| Asset | Family | PV / interface | What it is |
| --- | --- | --- | --- |
| `TPS 07A` | (root) | `07a:` | bound to the NSRRC Site |
| `StorageRing` | StorageRing (loose) | EPICS (PV pending) | storage-ring current monitor (source repr) |
| `WhiteBeamShutter` | Shutter | EPICS (PV pending) | front-end PSS photon shutter |
| `Monochromator` | Monochromator | EPICS (PV pending) | double-crystal monochromator (6-20 keV) |
| `EnergyAxis` | PseudoAxis | EPICS (PV pending) | master energy setpoint |
| `Attenuators` | Filter | EPICS (PV pending) | attenuator / transmission filter |
| `KBMirrors` | Mirror | EPICS (PV pending) | micro-focus mirrors (~2.9 x 1.8 micron spot) |
| `Goniometer` | Goniometer | EPICS via DHS (`07a-ES:`) | MD3 microdiffractometer (omega / kappa / phi) |
| `SampleTemperature` | TemperatureController | EPICS (PV pending) | cryostream sample cooling |
| `BeamStop` | BeamStop | EPICS (PV pending) | beamstop at the sample |
| `EigerDetector` | Camera | DCSS workflow over EPICS; ZMQ egress | DECTRIS EIGER2 X 16M (~130 Hz) |
| `DetectorStage` | LinearStage | EPICS (PV pending) | detector translation (139 mm min-distance interlock) |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | EPICS (PV pending) | beam-position diagnostic |
| `OAVCamera` | Camera | EPICS (PV pending) | on-axis viewing camera |
| `FastShutter` | Shutter | EPICS (PV pending) | per-oscillation exposure shutter |
| `EndstationMotionController` | MotionController | EPICS via DHS | stage motion controllers |

Every family is in the catalog except the loose `StorageRing` and `BeamPositionMonitor` (both shared and allowlisted); TPS 07A coins none. Notably the MD3 goniometer reuses the graduated `Goniometer` family (the i03 Smargon / MX3 MD3 precedent), the cryostream reuses `TemperatureController` (graduated in #350), and the detectors reuse `Camera`, so TPS 07A is a clean reuse deployment whose novelty is the Site and the DCSS-over-EPICS seam, not its device vocabulary. The ISARA sample robot is not a device here: it is a deferred autonomous-exchange Procedure (ROBOT-1).

## Pending confirmations

Every value below is read from the public control trees or inferred, awaiting the team. Each is tracked by an [open question](questions.md).

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Insertion-device / source PV | `StorageRing` (source repr) | `unknown-pending-confirmation` | (SRC-1) |
| PSS search-and-secure permit-leaf PVs | both enclosures | `unknown-pending-confirmation` | (PSS-1) |
| DCM crystal cut / range and attenuator foils | `Monochromator` / `Attenuators` | `unknown-pending-confirmation` | (DCM-1) |
| Micro-focus mirror configuration and PVs | `KBMirrors` | `unknown-pending-confirmation` | (OPT-1) |
| MD3 axis PV records (`07a-ES:`) and DCSS-vs-MXCuBE | `Goniometer` | `unknown-pending-confirmation` | (GONIO-1) |
| EIGER2 detector PVs and SIMPLON endpoint | `EigerDetector` | `unknown-pending-confirmation` | (DET-1) |
| Cryostream vendor and PV | `SampleTemperature` | `unknown-pending-confirmation` | (ENV-1) |
| Diagnostic channel maps / PVs | `BeamPositionMonitor` / `OAVCamera` | `unknown-pending-confirmation` | (DIAG-1) |
| Motion-controller box firmware / IP | `EndstationMotionController` | `unknown-pending-confirmation` | (DRIVE-1) |
| Energy scanned (anomalous / MAD) vs fixed | `EnergyAxis` | `unknown-pending-confirmation` | (ENERGY-1) |
