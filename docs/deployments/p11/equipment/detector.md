# Detector

*The detection Assets at P11: the Pilatus area detector and the XIA fluorescence detector. First cut, reverse-engineered from the OnlineXML.*

P11's detection is the standard MX pairing: a Pilatus area detector for diffraction frames, and an XIA multi-channel-analyzer fluorescence detector for element identification and edge scanning.

## Area detector

- `AreaDetector` binds `Camera`: the experiment-hutch Pilatus area detector (`eh_pilatus01`, `p11/pilatus/eh.01`); MX diffraction imaging. The Pilatus variant (300k / 1M / 2M / 6M) is not in the registry (`DET-1`).

## Fluorescence detector

- `FluorescenceDetector` binds `EnergyDispersiveSpectrometer`: the XIA multi-channel-analyzer fluorescence detector (`eh_xia01`, `p11/xia/oh.1`); element identification / absorption-edge scanning for anomalous MX (`DET-1`).

## Families and confirmations

The Pilatus binds the catalog `Camera` Family; the XIA fluorescence detector binds `EnergyDispersiveSpectrometer`. No new Family is coined. The detector model, the sample-to-detector geometry, and the detector-positioning stage (if separate from the experiment banks) are not fully in the registry and are pending (`DET-1`). See [Open questions](../questions.md).
