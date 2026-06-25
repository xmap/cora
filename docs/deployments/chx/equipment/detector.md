# Detector

*The coherent area detectors, the detector positioner, and the diagnostics. PVs verified against `startup/20-area-detectors.py`, `10-optics.py`, `26-scalers.py`, `98-xspress3.py`.*

CHX's measurement lives on its area detectors. For XPCS the Eiger records a long, fast time series of the coherent speckle pattern; for static scattering it records a single SAXS/WAXS frame. The same detector serves both, the technique is the acquisition, not the hardware.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `Eiger4M` | Camera | `XF:11IDB-ES{Det:Eig4M}` | primary XPCS / scattering detector |
| `Eiger1M` | Camera | `XF:11IDB-ES{Det:Eig1M}` | pixel detector |
| `Eiger500K` | Camera | `XF:11IDB-ES{Det:Eig500K}` | pixel detector |
| `SAXSDetectorStage` | LinearStage | `XF:11IDB-ES{Det:SAXS}` | centers the detector transversely on the beam (X/Y) |
| `SAXSBeamStop` | BeamStop | `XF:11IDB-ES{BS:SAXS}` | blocks the direct beam |
| `FluxCounter` | FluxMonitor | `XF:11IDB-ES{Sclr:1}` | I0 normalization |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:11IDB-ES{Xsp:1}` | occasional anomalous / element-sensitive |
| `BeamViewingCamera` | Camera | `XF:11IDB-BI{Cam:10}` | on-axis beam-viewing (OAV) |

## Centering and the beamstop

The `SAXSDetectorStage` is a transverse X/Y positioner (an `XYMotor` in source) that centers the area detector on the scattered beam; it does not move along the beam. Whether a separate along-beam stage sets the sample-to-detector distance (and hence the q-range) is not in the public config, so that, and which Eiger is primary, are staff questions (DET-1). The `SAXSBeamStop` blocks the direct beam ahead of the detector so the weak scattered signal is not swamped.

## Reuse, not new vocabulary

This is the reinforcement point of CHX as a CORA exercise: a coherence beamline with three area detectors, a detector positioner, and a beamstop that needs **no new Family**. The Eiger detectors reuse `Camera` (the Diamond Eiger-to-Camera precedent, also used at [SRX](../../srx/equipment/detector.md)); the flux counter reuses `FluxMonitor` (graduated in #353); the beamstop reuses `BeamStop`; the occasional fluorescence detector reuses `EnergyDispersiveSpectrometer` (graduated in #345). The `BeamViewingCamera` (an on-axis Prosilica OAV; x-ray-eye Prosilicas and a PointGrey serve alignment views) is another `Camera`. The live set is CAM-1.

The coherent detector chain is the same shape APS [8-ID](../../8-id/equipment/detector.md) carries: an area detector under a gated exposure recording a time series. CHX shows it porting to a second facility unchanged.
