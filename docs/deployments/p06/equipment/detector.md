# Detector

*The detector pool at P06: the Maia XRF array, the area detectors, and the fluorescence detectors. First cut, reverse-engineered from the OnlineXML.*

P06's detection is the richest in the PETRA III set: a high-rate Maia XRF array for fluorescence mapping, four area detectors (Eiger, Lambda, Pilatus, PCO) for diffraction / imaging, and XIA multi-channel-analyzer fluorescence detectors. The detectors serve both endstations per experiment; several report on a bare `p06` / `petra3` Tango host and are homed in the detection stage with the host flagged (`HOST-1`).

## Energy-dispersive (fluorescence)

- `MaiaDetector` binds `EnergyDispersiveSpectrometer`: the Maia high-rate XRF detector array, exposed as several Tango devices (`maiadimension` / `maiaflux` / `maiasensor` / `maiainterlock` / `maialogger` / `maiaprocessing`), modelled as one Asset carrying its sub-device handles. This is the scanning-fluorescence-microscopy mapping detector (`DET-1`).
- `XIAFluorescence` binds `EnergyDispersiveSpectrometer`: the XIA multi-channel-analyzer fluorescence detectors (`p06_xia01..04` plus the lab unit) (`DET-1`).

## Area detectors

- `EigerDetector` binds `Camera`: the DECTRIS Eiger area detector; diffraction / scanning-diffraction imaging (`DET-1`).
- `LambdaDetector` binds `Camera`: the X-Spectrum Lambda area detector; reports on the `petra3` host (`HOST-1`) (`DET-1`).
- `PilatusDetector` binds `Camera`: the DECTRIS Pilatus 300k area detectors (two units) (`DET-1`).
- `PCODetector` binds `Camera`: the PCO 4000 CCD camera; imaging / visible-light diagnostics (`DET-1`).
- `XrayEyeCamera` binds `Camera`: the X-ray-eye Prosilica viewing camera; beam / sample viewing (`DET-1`).

## Families and confirmations

The Maia and XIA detectors bind the catalog `EnergyDispersiveSpectrometer` Family; the area and view cameras bind `Camera`. No new Family is coined. The Maia is modelled as one Asset carrying its six sub-device handles rather than six separate Assets, because the sub-devices (dimension / flux / sensor / interlock / logger / processing) are facets of one detector array, not independent instruments; whether CORA later splits them is a modelling question. The operative detector roster per experiment, the Maia element count, and the area-detector models are not fully in the registry and are pending (`DET-1`). See [Open questions](../questions.md).
