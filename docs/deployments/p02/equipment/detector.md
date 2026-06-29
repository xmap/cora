# Detector

*The detection Assets across P02's two diffraction endstations, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P02's detection pairs large-area detectors for the diffraction / total-scattering signal with fluorescence detectors, across the P02.1 powder branch and the P02.2 extreme-conditions branch.

## P02.1: powder / total scattering

- `PilatusDetector` binds `Camera`: the P02.1 Pilatus 1M area detector; powder-diffraction rings (`DET-1`).
- `PerkinElmerDetector` binds `Camera`: the P02.1 PerkinElmer flat-panel area detector; high-energy total-scattering / PDF to high momentum transfer (`DET-1`).

## P02.2: extreme conditions

- `FluorescenceDetectors` binds `EnergyDispersiveSpectrometer`: the P02.2 MCA and SIS3302 fluorescence detectors (`DET-1`).

## Families and confirmations

The area detectors bind the catalog `Camera` Family; the fluorescence detectors bind `EnergyDispersiveSpectrometer`. No new Family is coined. The detector roster per branch, the SAXS-style detector-distance / role assignment (the Pilatus 1M for powder rings vs the PerkinElmer for high-Q PDF), and the high-pressure diffraction area detector for P02.2 (shared or not separately listed in this registry slice) are not fully resolved and are pending (`DET-1`). See [Open questions](../questions.md).
