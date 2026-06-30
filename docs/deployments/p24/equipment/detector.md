# Detector

*The detection Assets at P24, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P24's detection pairs the fluorescence MCA detectors (exposed in the registry) with the single-crystal area detector (not exposed, carried pending).

- `FluorescenceDetectors` binds `EnergyDispersiveSpectrometer`: the EH2 MCA fluorescence detectors (`p24/mca/eh2.*`) (`DET-1`).
- `AreaDetector` binds `Camera`: the EH2 chemical-crystallography area detector (a Pilatus / Eiger-class photon-counting detector). Not exposed in this registry slice; carried as a pending `Camera` placeholder (`DET-1`).

## Families and confirmations

The MCA detectors bind the catalog `EnergyDispersiveSpectrometer` Family; the area detector binds `Camera`. No new Family is coined. The single-crystal area-detector model (the defining chemical-crystallography detector) is the key open item here, carried pending until P24 staff confirm it (`DET-1`). This is the honest model-what-the-source-supports posture: the registry slice names the MCAs but not the area detector, so the latter is flagged as a question rather than invented. See [Open questions](../questions.md).
