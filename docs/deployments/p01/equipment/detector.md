# Detector

*The detector positioning Assets in P01's EH2 and EH3 hutches, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P01's OnlineXML registry lists detector **positioning stages** (the carriages that move a detector through theta / x / y), but not the detector **devices** themselves: an avalanche photodiode for the NRS time spectrum, or an area detector for diffraction / RIXS, is not a motor row in the registry. CORA models the stages here and carries the detector devices pending (`DET-1`).

## EH2 diffraction

- `DetectorStage` binds `LinearStage`: the EH2 detector positioning stage (x / y). The detector device it carries (an APD or an area detector) is not in the motor registry (`DET-1`).

## EH3 resonant inelastic X-ray scattering

- `DetectorStage` binds `LinearStage`: the EH3 main detector positioning stage (theta / x / y), carrying the RIXS spectrometer detector.
- `SecondaryDetectorStage` binds `LinearStage`: a second EH3 detector arm stage (theta / x / y); its role and detector are pending (`DET-1`).

## Families and confirmations

The detector stages bind the catalog `LinearStage` Family; no new Family is coined. The detector devices (the APD for NRS, the RIXS spectrometer detector, the diffraction detector) are named but not bound, because the OnlineXML carries their positioning stages, not the detector device servers. The operative detector models per endstation are the key open item here (`DET-1`); see [Open questions](../questions.md).
