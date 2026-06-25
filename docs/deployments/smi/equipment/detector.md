# Detector

*The simultaneous SAXS and WAXS area detectors, the camera-length stage, the beamstops, and the diagnostics. PVs verified against `startup/smibase/pilatus.py`, `beamstop.py`, `electrometers.py`, `amptek.py`, `prosilica.py`.*

SMI's measurement is the scattering pattern on two Pilatus detectors read at once: the SAXS detector down an in-vacuum flight path for low Q, the WAXS detector on a swing arc for wide Q. Reading both together is the routine mode.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `SAXSDetector` | Camera | `XF:12ID2-ES{Pilatus:Det-2M}` | Pilatus 2M, low-Q (SAXS) |
| `WAXSDetector` | Camera | `XF:12IDC-ES:2{Det:900KW}` | Pilatus 900KW on a swing arc, wide-Q (WAXS) |
| `SAXSDetectorStage` | LinearStage | `XF:12IDC-ES:2{Det:1M-Ax:}` | sets the SAXS camera length (Q) |
| `SAXSBeamStop` | BeamStop | `XF:12IDC-ES:2{BS:SAXS}` | blocks the SAXS direct beam |
| `FluxMonitor` | FluxMonitor | `XF:12ID:2{EM:Tetr1}` | I0 normalization |
| `FluorescenceSpectrometer` | EnergyDispersiveSpectrometer | `XF:12IDC-ES:2{Det-Amptek:1}` | element-sensitive Amptek MCA |
| `BeamViewingCamera` | Camera | `XF:12IDC-BI{Cam:SAM}` | on-axis sample viewing |

## Two detectors, one measurement; the camera length

The `SAXSDetector` (Pilatus 2M) sits down the in-vacuum flight path; the `SAXSDetectorStage` Z axis translates it to set the sample-to-detector camera length and hence the accessible Q. The `WAXSDetector` (Pilatus 900KW) rides a swing arc (`XF:12IDC-ES:2{WAXS:1-Ax:Arc}`): swung out for GISAXS, brought to zero for GIWAXS. The two are read at once, with their own beamstops blocking each direct beam (the `SAXSBeamStop` is a four-motor rod-and-pin-diode assembly; the WAXS detector has its own beamstop). Simultaneous SAXS+WAXS is modelled as coordinated Runs under one Campaign, not a third combined technique.

## Reuse, not new vocabulary

This is the reinforcement point of SMI as a CORA exercise: a scattering beamline with two area detectors, a camera-length stage, two beamstops, and a fluorescence channel that needs **no new Family**. The Pilatus detectors reuse `Camera` (the Eiger-to-Camera precedent at [CHX](../../chx/equipment/detector.md) and the i22 Detector-Role shape); the flux monitor reuses `FluxMonitor` (graduated in #353); the beamstops reuse `BeamStop`; the Amptek reuses `EnergyDispersiveSpectrometer` (graduated in #345). The detector chain is the same shape Diamond [I22](../../i22/index.md) carries (two Pilatus detectors at once distinguished by camera length); SMI shows it porting to a second facility, with the grazing-incidence swing arc added.
