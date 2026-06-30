# Detector

*The detection Assets at P64, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P64's detection is built for dilute, high-rate fluorescence EXAFS: two Lambda 750k area detectors for transmission / total fluorescence, and a large multi-element fluorescence detector.

- `LambdaDetectors` binds `Camera`: the two X-Spectrum Lambda 750k area detectors; transmission / total-fluorescence imaging (`DET-1`).
- `FluorescenceDetector` binds `EnergyDispersiveSpectrometer`: the P64 multi-element fluorescence detector, a 104-channel SIS3302 digitizer. The registry exposes it as 104 ROI / channel devices; grouped here as one Asset (`DET-1`).

## Families and confirmations

The Lambda detectors bind the catalog `Camera` Family; the multi-element fluorescence detector binds `EnergyDispersiveSpectrometer`. No new Family is coined. The detector is modelled as one Asset carrying its primary handle rather than 104 channel Assets, because the channels are facets of one multi-element detector, not independent instruments; the element count and the deadtime / ROI handling are pending (`DET-1`). The transmission ion chambers (I0 / I1) are not exposed as devices in this registry slice and are carried implicitly with the Lambda transmission path (`DET-1`). See [Open questions](../questions.md).
