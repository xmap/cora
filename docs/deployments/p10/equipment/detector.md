# Detector

*The detection Assets across P10's experiment areas, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P10 carries the fleet's widest detector suite, reflecting its coherence-applications role: high-frame-rate area detectors for XPCS, large-area detectors for coherent diffraction, and fluorescence detectors. Several detectors report on a bare `p10` host and are homed in the endstation that operates them with the host flagged (`HOST-1`).

## E1: coherent imaging

- `QuadroDetector` binds `Camera`: the E1 Quadro area detector (ccdpvcam); coherent-imaging detection (`DET-1`).
- `FluorescenceDetectors` binds `EnergyDispersiveSpectrometer`: the E1 MCA fluorescence detectors (`DET-1`).

## E2: XPCS / diffraction

- `PilatusDetectors` binds `Camera`: the E2 Pilatus area detectors (100k / 1M / 300k); XPCS / coherent-diffraction detection (`DET-1`).
- `PCODetector` binds `Camera`: the E2 PCO edge sCMOS camera; fast imaging (`DET-1`).
- `LCXCamera` binds `Camera`: the E2 LCX camera; beam / sample diagnostics (`DET-1`).
- `LambdaDetector` binds `Camera`: the shared X-Spectrum Lambda detectors (`l01 / l02 / ldev`); the high-frame-rate XPCS detector, reporting on the bare `p10` host (`HOST-1`, `DET-1`).
- `LimaCameras` binds `Camera`: the shared Lima-controlled cameras (`MAX22 / MAX51`, limaccd / limampx), reporting on the bare `p10` host (`HOST-1`, `DET-1`).

## LAB: offline

- `EigerDetector` binds `Camera`: the LAB DECTRIS Eiger 4M area detector (`DET-1`).
- `AndorCamera` binds `Camera`: the LAB Andor camera (andor / Lima-controlled andorccd) (`DET-1`).
- `MythenDetector` binds `Camera`: the LAB Mythen strip detector; one-dimensional diffraction (`DET-1`).

## Families and confirmations

The area / strip detectors all bind the catalog `Camera` Family; the MCA fluorescence detectors bind `EnergyDispersiveSpectrometer`. No new Family is coined. The operative detector roster per experiment, the high-frame-rate XPCS detector assignment (Lambda vs Eiger), and the detector models are not fully in the registry and are pending (`DET-1`). The Mythen is a one-dimensional strip detector modelled as a `Camera` for now (its readout is a line, not an area); whether that warrants a distinct Family is a fold-vs-promote question deferred to the catalog owner (`DET-1`). See [Open questions](../questions.md).
