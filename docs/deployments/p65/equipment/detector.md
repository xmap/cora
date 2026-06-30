# Detector

*The detection Assets at P65, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P65's standard applied-XAS detection (ion chambers for transmission, a fluorescence detector) is not exposed as a device in this OnlineXML registry slice. CORA models it as a pending placeholder rather than inventing the chain.

- `AbsorptionDetectors` binds `FluxMonitor`: the P65 absorption-spectroscopy detection (ion chambers I0 / I1 / I2 for transmission XAS, and any fluorescence detector). Not in the registry slice; carried as a pending `FluxMonitor` placeholder (`DET-1`).

## Families and confirmations

The detection placeholder binds the catalog `FluxMonitor` Family. No new Family is coined. The actual XAS detection chain (the ion-chamber count, the fluorescence detector model, the digitizer) is the key open item here, carried pending until P65 staff confirm it (`DET-1`). This is the honest model-what-the-source-supports posture: the registry slice does not name the detectors, so they are flagged as a question rather than invented. See [Open questions](../questions.md).
