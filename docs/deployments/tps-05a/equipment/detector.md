# Detector

*The DECTRIS EIGER2 X 9M and its support, the on-axis viewing, and the beam diagnostics. The detector model is read from the SPXF facility pages; the control path is inherited from the [TPS 07A](../../tps-07a/equipment/detector.md) reading.*

TPS 05A's measurement is the rotation series of diffraction frames the EIGER2 reads as the crystal oscillates.

| Asset | Family | PV / interface | Role |
| --- | --- | --- | --- |
| `EigerDetector` | Camera | DCSS workflow over EPICS (PV pending) | the rotation-MX area detector |
| `DetectorStage` | LinearStage | EPICS (PV pending) | sets the sample-to-detector distance |
| `BeamPositionMonitor` | PositionMonitor | EPICS (PV pending) | beam-position diagnostic |
| `OAVCamera` | Camera | EPICS (PV pending) | on-axis viewing for centring |

## The EIGER2 X 9M over the DCSS workflow

The `EigerDetector` is a DECTRIS **EIGER2 X 9M** (the [SPXF page](https://nsrrcspxf.github.io/nsrrcspxf/index.html) names the 9M for 05A, against 07A's 16M). Its acquisition is **commanded through the Blu-Ice/DCSS workflow** over the EPICS floor, the same path as [TPS 07A](../../tps-07a/equipment/detector.md): CORA treats the frame egress as a `TransferPort` leg into its Dataset of record, and any spot-scoring / indexing as `ComputePort` work, an **Observe / Compute leg off the control seam**. It reuses the `Camera` family; the detector PVs and the SIMPLON endpoint are not in public source (DET-1).

## Diagnostics

The `DetectorStage` sets the sample-to-detector distance (any minimum-distance interlock like 07A's 139 mm is pending, DET-1). The `BeamPositionMonitor` binds the graduated catalog `PositionMonitor` Family (presents `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux; the per-Asset channel map stays open, DIAG-1); the `OAVCamera` serves sample centring on the MD3 and reuses `Camera`.

## Reuse, not new vocabulary

The detector chain needs **no new Family**: the EIGER2 and the OAV reuse `Camera`, the distance stage `LinearStage`. The only difference from 07A is the detector size (9M vs 16M), a per-Asset fact, not a vocabulary change. TPS 05A reinforces that the `Camera` Role plus the DCSS-over-EPICS control path covers the NSRRC MX cluster.
