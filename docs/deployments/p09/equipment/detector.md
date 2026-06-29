# Detector

*The detection Assets across P09's three areas, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P09 pairs area detectors for the scattering / diffraction signal with energy-dispersive fluorescence detectors for element / edge identification, across the MONO and MAG areas.

## MONO: resonant scattering

- `PerkinElmerDetector` binds `Camera`: the MONO PerkinElmer flat-panel area detector (`pectrl` / `pedetector`); resonant-diffraction imaging (`DET-1`).
- `PilatusDetector` binds `Camera`: the MONO Pilatus 300k area detector (`DET-1`).
- `FluorescenceDetector` binds `EnergyDispersiveSpectrometer`: the MONO SIS3302 fluorescence digitizer plus the MCA. The SIS3302 is exposed as many ROI sub-channels in the registry; grouped here as one Asset (`DET-1`).

## MAG: high-field magnetism

- `PilatusDetector` binds `Camera`: the MAG Pilatus 100k area detector (`DET-1`).
- `AndorCamera` binds `Camera`: the MAG Andor camera (Lima-controlled); imaging / diagnostics (`DET-1`).

## Families and confirmations

The area detectors all bind the catalog `Camera` Family; the SIS3302 / MCA fluorescence detectors bind `EnergyDispersiveSpectrometer`. No new Family is coined. The detector roster per experiment, the PerkinElmer / Pilatus model detail, and the SIS3302 channel count (collapsed from the registry's ROI explosion) are not fully in the registry and are pending (`DET-1`). A shared Lambda detector (`petra3/lambda/01`) reports on the bare `petra3` host and is noted but not bound to a specific area (`HOST-1`). See [Open questions](../questions.md).
