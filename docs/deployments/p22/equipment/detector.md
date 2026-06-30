# Detector

*The detection Asset at P22, as CORA models it today. First cut, reverse-engineered from the OnlineXML.*

P22's defining detector is the hard X-ray electron analyzer, which measures the kinetic-energy spectrum of photoelectrons. It is not exposed as a motor device in this OnlineXML registry slice (the analyzer is a self-contained instrument with its own control system), so CORA carries it pending against the catalog `ElectronAnalyzer` Family.

- `ElectronAnalyzer` binds the catalog `ElectronAnalyzer` Family: the HAXPES hard X-ray hemispherical electron analyzer. Not exposed in this registry slice; carried pending (`DET-1`).

## Families and confirmations

The electron analyzer binds the catalog `ElectronAnalyzer` Family (graduated at NSLS-II ESM, CORA's first photoemission beamline). No new Family is coined. The analyzer model (a hemispherical analyzer, e.g. SPECS / Scienta), its lens modes, and its control interface are the key open items here, carried pending until P22 staff confirm them (`DET-1`). This is the honest model-what-the-source-supports posture: the registry slice does not name the analyzer, so it is bound to the right Family but its detail is flagged as a question. See [Open questions](../questions.md).
