# Detector

*The detection Assets at P08, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P08 carries a rich detector set spanning the breadth of high-resolution diffraction modes: photon-counting area detectors, a strip detector for high-resolution powder / reflectivity, a flat-panel, and a fluorescence detector.

- `EigerDetector` binds `Camera`: the DECTRIS Eiger 1M area detector; high-resolution diffraction imaging (`DET-1`).
- `PilatusDetectors` binds `Camera`: the DECTRIS Pilatus 100k / 300k area detectors (`DET-1`).
- `MythenDetector` binds `Camera`: the DECTRIS Mythen2 one-dimensional strip detector; high-resolution powder / reflectivity (`DET-1`).
- `PerkinElmerDetector` binds `Camera`: the PerkinElmer flat-panel area detector (`DET-1`).
- `VortexDetector` binds `EnergyDispersiveSpectrometer`: the Vortex silicon-drift fluorescence detector (read by a SIS3302 digitizer) (`DET-1`).
- `LambdaDetector` binds `Camera`: a shared X-Spectrum Lambda detector, reporting on the bare `petra3` host (`HOST-1`, `DET-1`).

## Families and confirmations

The area / strip detectors bind the catalog `Camera` Family; the Vortex SDD binds `EnergyDispersiveSpectrometer`. No new Family is coined. The Mythen2 is a one-dimensional strip detector modelled as a `Camera` for now (a fold-vs-promote question for the catalog owner, the P10 precedent). The operative detector roster per experiment and the detector models are pending (`DET-1`). See [Open questions](../questions.md).
