# Inventory

*The CORA Asset model for the operational core of 9-ID modelled today: the planned device tree and what still needs confirming.*

This cut models the 9-ID-A optics, the 9-ID-D focusing and guard slits, the grazing-incidence CSSI sample stack, and the detectors; the metadata / Data Management PVs and the simulated devices are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/9-id/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) wherever one fits, and for 9-ID one always does except for two classes. The CRL `Transfocator` and the `BeamPositionMonitor` monitors are held loose pending a cross-facility gate-review, the same Families 4-ID and 8-ID use (see [Model](model.md#loose-families-held-for-gate-review)). Control handles are filled from the beamline config; no vendor Models are bound.

## The Asset tree

Root Asset `9-ID` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `9-ID` | `Unit` | (root) | - | bound to the APS Site; two hutches |
| `Undulator` | `Device` | InsertionDevice | 9-ID-A | planar undulator (`S09ID:`, SRC-1) |
| `Monochromator` | `Device` | Monochromator | 9-ID-A | Kohzu DCM (MONO-1) |
| `Mirror_1/2` | `Device` | Mirror | 9-ID-A | FMBO mirrors, coarse + piezo pitch + bender (OPT-1) |
| `Aperture_1/2` | `Device` | Aperture | 9-ID-A | high-heat-load white-beam apertures (OPT-2) |
| `Filter` | `Device` | Filter | 9-ID-A | AVS attenuator bank (OPT-4) |
| `Transfocator` | `Device` | Transfocator (loose) | 9-ID-D | JJ CRL transfocator (OPT-3) |
| `KBMirror` | `Device` | Mirror | 9-ID-D | Kirkpatrick-Baez focusing pair (OPT-5) |
| `Slit_3/4/5` | `Device` | Slit | 9-ID-D | guard slits (OPT-2) |
| `CSSISampleStage` | `Device` | LinearStage | 9-ID-D | grazing-incidence sample translation + fly Z (CSSI-1) |
| `CSSIIncidence` | `Device` | RotaryStage | 9-ID-D | grazing-incidence angle rotation (CSSI-1) |
| `Hexapod_1/2` | `Device` | Hexapod | 9-ID-D | Aerotech six-axis alignment hexapods (CSSI-2) |
| `ViewingMicroscope` | `Device` | Camera | 9-ID-D | on-axis sample-viewing microscope (CSSI-3) |
| `Pilatus1M` | `Device` | Camera | 9-ID-D | Pilatus 1M coherent detector (DET-1) |
| `EigerDetector` | `Device` | Camera | 9-ID-D | Eiger coherent detector (DET-1) |
| `DetectorStage` | `Device` | LinearStage | 9-ID-D | Eiger positioning stage |
| `WAXSDetector` | `Device` | Camera | 9-ID-D | GIWAXS detector on its pedestal (DET-1) |
| `BeamStop` | `Device` | BeamStop | 9-ID-D | direct-beam stop and carriage |
| `TetrAMM` | `Device` | BeamPositionMonitor (loose) | 9-ID-D | TetrAMM picoammeter (BPM-1) |
| `XBPM_1/2` | `Device` | BeamPositionMonitor (loose) | 9-ID-D | X-ray beam-position monitors (BPM-1) |
| `FlyScanScaler` | `Device` | GenericProbe | 9-ID-D | multi-channel scaler gating the fly scans (CTRL-2) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Aperture`, `Filter`, `Slit`, `LinearStage`, `RotaryStage`, `Hexapod`, `Camera`, `BeamStop`, `GenericProbe`. Held loose pending gate-review (a third independent beamline, but the abstraction is open): `Transfocator`, `BeamPositionMonitor`. 9-ID adds **no new loose family of its own**.

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Beam topology (canted, stations in series) | the root and optics spine | `unknown-pending-confirmation` | (TOPO-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| Hutch PSS permit signals | the two enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Undulator type and period | `Undulator` | `unknown-pending-confirmation` | (SRC-1) |
| Monochromator energy model | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | `Mirror_1/2`, `KBMirror` | `unknown-pending-confirmation` | (OPT-1) (OPT-5) |
| Aperture and slit axis maps | `Aperture_1/2`, `Slit_3/4/5` | `unknown-pending-confirmation` | (OPT-2) |
| Transfocator lens spec | `Transfocator` | `unknown-pending-confirmation` | (OPT-3) |
| Attenuator foil set | `Filter` | `unknown-pending-confirmation` | (OPT-4) |
| Grazing-incidence sample geometry | `CSSISampleStage`, `CSSIIncidence` | `unknown-pending-confirmation` | (CSSI-1) |
| Alignment-hexapod roles | `Hexapod_1/2` | `unknown-pending-confirmation` | (CSSI-2) |
| Viewing-microscope role | `ViewingMicroscope` | `unknown-pending-confirmation` | (CSSI-3) |
| Detector models | the area detectors | `unknown-pending-confirmation` | (DET-1) |
| Beam-position vs intensity monitor split | the monitors | `unknown-pending-confirmation` | (BPM-1) |
| Diagnostic flags and DAMM mask | the 9-ID-A diagnostics | `unknown-pending-confirmation` | (DIAG-1) |
| Fly-scan timing graph | `FlyScanScaler` | `unknown-pending-confirmation` | (CTRL-2) |
| Vacuum and process-gas supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
