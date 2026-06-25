# Detector

*The flat-panel area detectors, the distance stage, and the flux diagnostics. PVs verified against `startup/80-areadetector.py`, `startup/18-ion-chamber.py`, `startup/16-electrometer.py`, `startup/10-motors.py`.*

XPD's measurement is the diffraction pattern on a large flat-panel detector. For powder diffraction the panel records the Debye-Scherrer rings; for total scattering / PDF it sits close to reach the wide Q that a pair distribution function needs.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `AreaDetector` | Camera | `XF:28IDC-ES:1{Det:PE1}` | primary PerkinElmer flat panel |
| `DexelaDetector` | Camera | `XF:28IDC-ES:1{Det:DEX}` | Dexela flat panel (commented-out in source) |
| `DetectorStage` | LinearStage | `XF:28IDC-ES:1{Det:PE1-Ax:}` | sets the sample-to-detector distance (Q) |
| `IonChamber` | FluxMonitor | `XF:28IDC-BI{IC101}` | incident-flux normalization |
| `QuadElectrometer` | FluxMonitor | `XF:28IDC-BI{IM:02}EM180:` | I0 intensity |
| `ExposureShutter` | Shutter | `XF:28IDC-ES:1{Sh:Exp}` | gates the detector exposure |

## The distance stage and the Q-range

Unlike a fixed flight tube, the `DetectorStage` Z axis (`pe1_z`) genuinely translates the panel along the beam, setting the sample-to-detector distance and hence the accessible Q. A PDF measurement uses this directly: a close distance reaches the high Q the Fourier transform into a pair distribution function needs, and the two-distance acquisition combines a near and a far position. The `ExposureShutter` gates each frame.

## Reuse, not new vocabulary

This is the reinforcement point of XPD as a CORA exercise: a powder / PDF beamline with a flat panel (the PerkinElmer; a Dexela panel is defined but currently commented out in source, DET-1), a distance stage, and flux counters that needs **no new Family**. The flat panels reuse `Camera` (also the Eiger-to-Camera precedent at [CHX](../../chx/equipment/detector.md) and SRX); the ion chamber and quad electrometer reuse `FluxMonitor` (graduated in #353); the exposure shutter reuses `Shutter`. The detector chain is the same shape Diamond [I15-1](../../i15-1/index.md) carries for PDF (a large detector on the two-theta arm at fixed high energy); XPD shows it porting to a second facility unchanged.
