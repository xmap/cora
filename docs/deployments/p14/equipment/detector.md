# Detector

*The detection Assets at P14: the EH1 Eiger detectors and X-ray imaging, the EH2 Pilatus, the flux monitor, and the XRF detector. First cut, reverse-engineered from the MXCuBE config.*

P14's detection spans both experiment hutches. EH1 carries three Dectris Eiger area detectors (a 16M silicon and two CdTe high-energy variants, 16M and 4M) for MX diffraction across energy ranges, plus an X-ray imaging camera and the on-axis viewing cameras; EH2 carries a Dectris Pilatus 2M. The flux monitor and the XRF fluorescence detector serve the MX data collection.

## EH1 area detectors

- `EigerDetector` binds `Camera`: the Dectris Eiger 16M silicon area detector (EMBLDetector, TINE channel `/P14/detector/eiger16m`, model read `16M`); the primary MX diffraction detector (`DET-1`).
- `EigerCdTe16MDetector` binds `Camera`: the Dectris Eiger 16M CdTe area detector (EMBLDetector, `/P14/detector/eiger16m-cdte`, model read `16M`); the high-energy CdTe-sensor MX detector variant (`DET-1`).
- `EigerCdTe4MDetector` binds `Camera`: the Dectris Eiger 4M CdTe area detector (EMBLDetector, `/P14/detector/eiger4m-cdte`, model read `4M`); the smaller high-energy CdTe MX detector variant (`DET-1`).

## EH2 area detector

- `PilatusDetectorEH2` binds `Camera`: the Dectris Pilatus 2M area detector (EMBLDetector, TINE channel `/PE2/detector/pilatus2m`, model read `2M`); the EH2 MX diffraction detector (`DET-1`).

## Distance, flux, and viewing

- `DetectorDistance` binds `PseudoAxis`: the EH1 detector-distance virtual axis (`/P14/collection/distance`) and the coupled resolution axis (`/P14/collection/resolution`); the sample-to-detector geometry as a derived axis. EH2 carries its own `/PE2/collection/*` pair (`DET-1`).
- `FluxMonitor` binds `FluxMonitor`: the pin-diode flux monitor (EMBLFlux, `/P14/PinDiode/Device0`); incident-flux normalization for MX data collection (`DIAG-1`).
- `OnAxisCamera` binds `Camera`: the EH1 on-axis sample-viewing video camera and the sample-changer camera (VimbaVideo / QtAxisCamera); the MX centring / loop-inspection video. No Exporter / TINE handle is in the config object, so the video source is carried confirm (`OAV-1`).
- `XrayImagingCamera` binds `Camera`: the EH1 X-ray imaging camera (EMBLXrayImaging); in-situ sample / loop X-ray imaging for centring. No control handle is in the config object, carried confirm (`IMG-1`).

## Fluorescence detector

- `FluorescenceDetector` binds `EnergyDispersiveSpectrometer`: the energy-dispersive XRF detector (EMBLXRFSpectrum, `/P14/fluorescence-scan/fls-scan`); element identification / absorption-edge scanning for anomalous MX (`DET-1`).

## Families and confirmations

The Eiger variants, the Pilatus, and the viewing / imaging cameras bind the catalog `Camera` Family; the XRF detector binds `EnergyDispersiveSpectrometer`; the detector distance binds `PseudoAxis`; the flux monitor binds `FluxMonitor`. No new Family is coined. The detector models are read from the configs (Eiger 16M silicon, Eiger 16M / 4M CdTe, Pilatus 2M); the sample-to-detector geometry, the ROI modes, and the imaging / on-axis camera handles are pending (`DET-1`, `OAV-1`, `IMG-1`). See [Open questions](../questions.md).
