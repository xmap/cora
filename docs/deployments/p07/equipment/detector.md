# Detector

*The detection Assets at P07, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P07's detection pairs area detectors for high-energy diffraction / imaging with fluorescence detectors, in the EH2 main hutch.

- `PilatusDetector` binds `Camera`: the EH2 Pilatus area detector; diffraction imaging (`DET-1`).
- `PerkinElmerDetector` binds `Camera`: the EH2 PerkinElmer flat-panel area detector (`pectrl_old` / `pedetector_old`); high-energy diffraction / imaging (`DET-1`).
- `FluorescenceDetectors` binds `EnergyDispersiveSpectrometer`: the EH2 MCA fluorescence detectors (`DET-1`).

## Families and confirmations

The area detectors bind the catalog `Camera` Family; the MCA fluorescence detectors bind `EnergyDispersiveSpectrometer`. No new Family is coined. The detector roster per experiment, the PerkinElmer / Pilatus model detail (the `_old` suffix suggests a legacy controller, possibly superseded), and the EH2B detection (not in this slice) are pending (`DET-1`). See [Open questions](../questions.md).
