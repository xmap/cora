# Detector

*The detection Assets at P23, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P23's in-situ diffraction detection (area detectors) is not exposed as a device in this OnlineXML registry slice. CORA models it as a pending placeholder rather than inventing it.

- `AreaDetectors` binds `Camera`: the P23 in-situ diffraction area detectors. Not in the registry slice; carried as a pending `Camera` placeholder (`DET-1`).

## Families and confirmations

The detection placeholder binds the catalog `Camera` Family. No new Family is coined. The actual detector roster (the area-detector models, the detector positioning, any energy-dispersive / fluorescence detectors for the in-situ work) is the key open item here, carried pending until P23 staff confirm it (`DET-1`). This is the honest model-what-the-source-supports posture: the registry slice does not name the detectors, so they are flagged as a question rather than invented. See [Open questions](../questions.md).
