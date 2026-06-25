# Detector

*The detector set, where the choice of detector selects the technique. PVs verified against `startup/31-xspress3.py`, `34-merlin.py`, `35-dexela.py`, `36-eiger.py`, `30-scaler.py`.*

SRX's multi-technique nature lives in its detectors: at a given scan point, which detector is read decides whether the measurement is XRF, diffraction, or imaging. All reuse existing Families.

| Asset | Family | PV | Technique it serves |
| --- | --- | --- | --- |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:05IDD-ES{Xsp:3}` | XRF mapping, XANES, XRF-tomography |
| `MerlinDetector` | Camera | `XF:05IDD-ES{Merlin:1}` | diffraction / ptychography |
| `DexelaDetector` | Camera | `XF:05IDD-ES{Dexela:1}` | wide-field diffraction |
| `EigerDetector` | Camera | `XF:05IDD-ES{Det:Eig1M}` | diffraction |
| `ImagingCamera` | Camera | `XF:05IDD-ES{Det:3}` | full-field imaging (PCO Edge) |
| `FluxCounter` | FluxMonitor | `XF:05IDD-ES:1{Sclr:1}` | I0 normalization |

## Reuse, not new vocabulary

This is the point of SRX as a CORA exercise: a beamline with five detectors and four techniques that needs **no new Family**. The fluorescence detector reuses `EnergyDispersiveSpectrometer` (graduated when 2-ID and 7-BM shared it); the pixel and imaging detectors reuse `Camera` (the Diamond Eiger-to-Camera precedent); the ion-chamber flux counter reuses `FluxMonitor` (graduated in #353). Which detectors are live versus the legacy set in source is a staff question (CAM-1).

A single scan Method binds the detector(s) the technique needs from this set, the same heterogeneous-detector-slot shape HXN introduced; SRX shows it generalizing across more techniques on one beamline.
