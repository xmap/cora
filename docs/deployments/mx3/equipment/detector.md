# Detector

*The DECTRIS Eiger and its support, the on-axis viewing, and the beam diagnostics. PVs / interfaces verified against `mx3_beamline_library/devices/{detectors,motors,beam}.py`.*

MX3's measurement is the rotation series of diffraction frames the Eiger reads as the crystal oscillates.

| Asset | Family | PV / interface | Role |
| --- | --- | --- | --- |
| `EigerDetector` | Camera | SIMPLON REST (no PV) | the rotation-MX area detector |
| `DetectorStage` | LinearStage | `MX3STG03MOT04` | sets the sample-to-detector distance |
| `FluxMonitor` | FluxMonitor | `MX3FLUXIOC:FLUX` | incident-flux normalization |
| `BeamPositionMonitor` | BeamPositionMonitor (loose) | `MX3DAQIOC04:` | beam position + closed-loop steering |
| `OAVCamera` | Camera | `MX3MD3ZOOM0` | on-axis viewing for centring |

## The Eiger over SIMPLON REST

The `EigerDetector` is a DECTRIS Eiger (16M / 4M). Unlike every prior deployment's detector, it is **not** an EPICS area-detector: it is driven over the DECTRIS SIMPLON REST API, where the acquisition lifecycle maps onto HTTP requests (arm / trigger / disarm and per-key config under `/detector/api/1.8.0/`). It reuses the `Camera` family, the new REST control plane is a `ControlPort` seam, not a new device shape, so it carries no PV; the endpoint base is deployment config (DET-1). The `DetectorStage` (an EPICS Power Brick stage) sets the sample-to-detector distance, read back at `MX3ES01:SAMPLE_DETECTOR_DISTANCE`.

## Diagnostics

The `FluxMonitor` reads incident flux for normalization (reuses `FluxMonitor`, graduated in #353). The `BeamPositionMonitor` pairs a beam-position monitor with a closed-loop PID steering DAC; the position-monitor half binds the loose `BeamPositionMonitor` family (held, DIAG-1), while the PID beam-steering controller fits no existing family cleanly and is a deferred new-device question (STEER-1). The `OAVCamera` (an EPICS BlackFly at the MD3 zoom optic) serves sample centring; an MD3 coaxial camera also streams over Redis.

## Reuse, not new vocabulary

The detector chain needs **no new Family**: the Eiger and the OAV reuse `Camera`, the distance stage `LinearStage`, the flux monitor `FluxMonitor`. The deployment's novelty is the Site and the heterogeneous control plane, not its device families; the SIMPLON-REST detector is the clearest instance of that, the same `Camera` Role reached over a new transport.
