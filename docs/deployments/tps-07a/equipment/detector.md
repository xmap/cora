# Detector

*The DECTRIS EIGER2 X 16M and its support, the on-axis viewing, and the beam diagnostics. Interfaces read from `light911/NSRRC_TPS07A` and `light911/TPS07A-Meshbest`.*

TPS 07A's measurement is the rotation series of diffraction frames the EIGER2 reads as the crystal oscillates.

| Asset | Family | PV / interface | Role |
| --- | --- | --- | --- |
| `EigerDetector` | Camera | DCSS workflow over EPICS; ZMQ frame egress (PV pending) | the rotation-MX area detector |
| `DetectorStage` | LinearStage | EPICS (PV pending); 139 mm min-distance interlock | sets the sample-to-detector distance |
| `BeamPositionMonitor` | PositionMonitor | EPICS (PV pending) | beam-position diagnostic |
| `OAVCamera` | Camera | EPICS (PV pending) | on-axis viewing for centring |

## The EIGER2 over the DCSS workflow

The `EigerDetector` is a DECTRIS EIGER2 X 16M running at up to 130 Hz. Its acquisition is **commanded through the Blu-Ice/DCSS workflow** (the EPICS floor), not driven directly by CORA today; frames **egress over a ZMQ stream**, with file writers for HDF5/NeXus, CBF, and TIFF. A late-2025 path adds DESY **ASAP::O** frame ingestion feeding **Dozor** spot scoring and **CHiMP** crystal detection for mesh scans (the [`TPS07A-Meshbest`](https://github.com/light911/TPS07A-Meshbest) app).

This is the clearest place the 07A seam differs from MX3's. MX3's EIGER is a `ControlPort` adapter over SIMPLON REST; at 07A the detector is commanded through DCSS over EPICS, and the frame egress + Dozor/CHiMP scoring is **Observe / Compute work, off the control seam**: CORA treats the ZMQ/ASAP::O frame stream as a `TransferPort` leg into its Dataset of record, and the Dozor/CHiMP indexing/scoring as `ComputePort` work, not part of the Actuate/conduct path. It reuses the `Camera` family; the detector PVs and the SIMPLON endpoint are pending (DET-1).

## Diagnostics and the distance interlock

The `DetectorStage` sets the sample-to-detector distance and carries a **hard minimum-distance interlock at 139 mm**, a safety limit read directly from the control tree (it bounds how close the detector may approach the sample). The `BeamPositionMonitor` binds the graduated catalog `PositionMonitor` Family (presents `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux; the per-Asset channel map stays open, DIAG-1); the `OAVCamera` serves sample centring on the MD3 and reuses `Camera`.

## Reuse, not new vocabulary

The detector chain needs **no new Family**: the EIGER2 and the OAV reuse `Camera`, the distance stage `LinearStage`. The deployment's novelty is the Site and the DCSS-over-EPICS seam, not its device families; the EIGER2-through-DCSS path is the clearest instance of that, the same `Camera` Role reached through an orchestration layer CORA would replace rather than a new transport.
