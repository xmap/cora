# Detector

*The detection Assets at P13: the Eiger and Pilatus area detectors, the flux monitor, the cameras, and the XRF detector. First cut, reverse-engineered from the MXCuBE config.*

P13's detection is the standard MX pairing, with two area detectors selectable for diffraction: a Dectris Eiger 16M and a Dectris Pilatus 6M, plus a pin-diode flux monitor, the on-axis sample-viewing cameras, and an XRF fluorescence detector for element identification and anomalous MX.

## Area detectors

- `EigerDetector` binds `Camera`: the Dectris Eiger 16M area detector (EMBLDetector, TINE channel `/P13/detector/eiger16m`, model read `16M` from the config); the primary MX diffraction detector (`DET-1`).
- `PilatusDetector` binds `Camera`: the Dectris Pilatus 6M area detector (EMBLDetector, TINE channel `/P13/detector/pilatus6m`, model read `6M_F` from the config); the alternative MX diffraction detector (`DET-1`).
- `DetectorDistance` binds `PseudoAxis`: the detector-distance virtual axis (`/P13/collection/distance`) and the coupled resolution axis (`/P13/collection/resolution`); the sample-to-detector geometry as a derived axis (`DET-1`).

## Flux and viewing

- `FluxMonitor` binds `FluxMonitor`: the pin-diode flux monitor (EMBLFlux, `/P13/PinDiode/Device0`); incident-flux normalization for MX data collection (`DIAG-1`).
- `OnAxisCamera` binds `Camera`: the on-axis sample-viewing video camera and the sample-changer camera (VimbaVideo / QtAxisCamera); the MX centring / loop-inspection video. No Exporter / TINE handle is in the config object, so the video source is carried confirm (`OAV-1`).

## Fluorescence detector

- `FluorescenceDetector` binds `EnergyDispersiveSpectrometer`: the energy-dispersive XRF detector (EMBLXRFSpectrum, `/P13/fluorescence-scan/fls-scan`); element identification / absorption-edge scanning for anomalous MX (`DET-1`).

## Families and confirmations

The Eiger, Pilatus, and viewing cameras bind the catalog `Camera` Family; the XRF detector binds `EnergyDispersiveSpectrometer`; the detector distance binds `PseudoAxis`; the flux monitor binds `FluxMonitor`. No new Family is coined. The detector models are read from the config (Eiger 16M, Pilatus 6M); the sample-to-detector geometry, the ROI modes, and the on-axis camera handle are pending (`DET-1`, `OAV-1`). See [Open questions](../questions.md).
