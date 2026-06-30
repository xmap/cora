# Detector

*The detection Assets at P61, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P61's detection for energy-dispersive diffraction (a germanium solid-state detector, and any area detectors) is not exposed as a device in this OnlineXML registry slice. CORA models it as a pending placeholder rather than inventing it.

- `EnergyDispersiveDetector` binds `EnergyDispersiveSpectrometer`: the P61 energy-dispersive (Ge solid-state) detector for energy-dispersive diffraction. Not in the registry slice; carried as a pending `EnergyDispersiveSpectrometer` placeholder (`DET-1`).

## Families and confirmations

The detection placeholder binds the catalog `EnergyDispersiveSpectrometer` Family. No new Family is coined. The actual detector chain (the Ge solid-state detector for energy-dispersive diffraction, any area detector for the white-beam / LVP work) is the key open item here, carried pending until P61 staff confirm it (`DET-1`). This is the honest model-what-the-source-supports posture: the registry slice does not name the detectors, so they are flagged as a question rather than invented. See [Open questions](../questions.md).
