# Inventory

*The CORA Asset model for the operational core of 8-ID modelled today: the planned device tree and what still needs confirming.*

This cut models the 8-ID-A/D optics and focusing, the 8-ID-E six-circle diffractometer endstation, and the 8-ID-I XPCS endstation; the robotic sample changer and the full softGlue timing graph are deferred (see [Model](model.md#deliberately-not-here-yet)). It is the cross-cutting reference view of the [Source](beamline.md) walk and the [Sample](equipment/sample.md) and [Detector](equipment/detector.md) pages, authored from the same [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/8-id/beamline.yaml) descriptor.

Devices bind to a catalog [Family](../../catalog/families.md) where one fits. Of the device classes 8-ID shares with 4-ID, `Transfocator` and `BeamPositionMonitor` are held loose pending a cross-facility gate-review, even though 8-ID is the second independent beamline to use them; `TemperatureController` has since graduated to a catalog Family (presents `Regulator`) on the Diamond rule-of-three (see [Model](model.md#loose-families-held-for-gate-review)). The rest of 8-ID's new classes (`Diffractometer`, `Rheometer`, `FlightPath`) stay loose. Control handles are filled from the beamline config; no vendor Models are bound.

## The Asset tree

Root Asset `8-ID` (`tier = Unit`, `facility_code = aps`); sub-systems nest below by `parent_id`.

| Asset | Tier | Family | Enclosure | Design spec / note |
| --- | --- | --- | --- | --- |
| `8-ID` | `Unit` | (root) | - | bound to the APS Site; four hutches |
| `Undulator_Downstream/Upstream` | `Device` | InsertionDevice | 8-ID-A | undulator pair (`S08ID:`) |
| `Monochromator` | `Device` | Monochromator | 8-ID-A | MN1 monochromator (MONO-1) |
| `Mirror_1/2` | `Device` | Mirror | 8-ID-A | FMBO mirrors, coarse + piezo pitch (OPT-1) |
| `WhiteBeamSlit` / `MonoSlit` | `Device` | Slit | 8-ID-A | optics slits |
| `Transfocator_1/2` | `Device` | Transfocator | 8-ID-D | CRL transfocators, ten lenses each (OPT-3) |
| `Slit_8idd` | `Device` | Slit | 8-ID-D | focusing-station slit |
| `Diffractometer_SixCircle` | `Device` | Goniometer | 8-ID-E | six-circle Huber; goniometer of the Diffractometer Assembly (DIFF-1) |
| `ReciprocalSpace` | `Device` | PseudoAxis | 8-ID-E | hklpy2 reciprocal-space layer (DIFF-2) |
| `TemperatureController_1/2` | `Device` | TemperatureController | 8-ID-E | LakeShore 336 controllers (TEMP-1) |
| `BeamPositionMonitor_E` | `Device` | BeamPositionMonitor | 8-ID-E | Sydor TetrAMM monitor (BPM-1) |
| `FastShutter` | `Device` | Shutter | 8-ID-E | XPCS exposure shutter (XPCS-1) |
| `SampleStage` | `Device` | LinearStage | 8-ID-I | Aerotech XPCS sample stage |
| `Rheometer` | `Device` | Rheometer (loose) | 8-ID-I | six-axis shear-cell environment (SAMPLE-1) |
| `SampleHolder_QNW` | `Device` | TemperatureController | 8-ID-I | Quantum Northwest holders (TEMP-1) |
| `SampleSlit` | `Device` | Slit | 8-ID-I | sample slit |
| `Eiger4M` / `Lambda2M` / `Rigaku3M` | `Device` | Camera | 8-ID-I | coherent-scattering area detectors (DET-1) |
| `DetectorStage` | `Device` | LinearStage | 8-ID-I | Aerotech detector stage |
| `FlightPath` | `Device` | FlightPath (loose) | 8-ID-I | evacuated flight path (XPCS-2) |
| `BeamStop` | `Device` | BeamStop | 8-ID-I | flight-tube beam stop |
| `TetrAMM_QUAD1` | `Device` | BeamPositionMonitor | 8-ID-I | TetrAMM channels (BPM-1) |
| `Timing` | `Device` | TimingController | - | softGlue timing fabric (XPCS-3) |

Families reused from the catalog: `InsertionDevice`, `Monochromator`, `Mirror`, `Slit`, `PseudoAxis`, `Shutter`, `LinearStage`, `Camera`, `BeamStop`, `TimingController`. Held loose pending gate-review (the second independent beamline, but the abstraction is open): `Transfocator`, `BeamPositionMonitor`. Graduated to a catalog Family (presents `Regulator`): `TemperatureController`. Also loose (single beamline): `Rheometer`, `FlightPath`. The diffractometer is not a loose family: its sample circles bind the catalog `Goniometer` Family, and the composed `Assembly(Diffractometer)` is in the catalog (see [Model](model.md#the-diffractometer-assembly-landed)).

## Pending confirmations

| Value to confirm | Applies to | Status | Tracking |
| --- | --- | --- | --- |
| Beam topology (canted, stations in series) | the root and optics spine | `unknown-pending-confirmation` | (TOPO-1) |
| Control handles (EPICS PVs) | all devices | `read-from-config-pending-confirmation` | (CTRL-1) |
| Hutch PSS permit signals | the four enclosures | `unknown-pending-confirmation` | (PSS-1) |
| Undulator types and periods | the undulators | `unknown-pending-confirmation` | (SRC-1) |
| Monochromator energy model | `Monochromator` | `unknown-pending-confirmation` | (MONO-1) |
| Mirror coatings and axis roles | `Mirror_1/2` | `unknown-pending-confirmation` | (OPT-1) |
| Transfocator lens spec | `Transfocator_1/2` | `unknown-pending-confirmation` | (OPT-3) |
| Six-circle geometry and Assembly slots | `Diffractometer_SixCircle` | `unknown-pending-confirmation` | (DIFF-1) |
| Reciprocal-space pseudo-axis model | `ReciprocalSpace` | `unknown-pending-confirmation` | (DIFF-2) |
| Temperature-controller channels | the temperature controllers | `unknown-pending-confirmation` | (TEMP-1) |
| Rheometer axes and modes | `Rheometer` | `unknown-pending-confirmation` | (SAMPLE-1) |
| Detector models | the area detectors | `unknown-pending-confirmation` | (DET-1) |
| Beam-position vs intensity monitor split | the monitors | `unknown-pending-confirmation` | (BPM-1) |
| Flight-path geometry | `FlightPath` | `unknown-pending-confirmation` | (XPCS-2) |
| softGlue timing graph | `Timing` | `unknown-pending-confirmation` | (XPCS-3) |
| Vacuum and process-gas supplies | `resources` | `unknown-pending-confirmation` | (SUP-1) |
