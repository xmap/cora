# Detector

*The detection Assets across P03's two scattering endstations, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P03's detection is the SAXS / WAXS pairing of large-area Pilatus detectors with fluorescence detectors, at both the microfocus and nanofocus endstations.

## Microfocus endstation

- `PilatusDetectors` binds `Camera`: the microfocus Pilatus 300k and Pilatus 1M area detectors (`p03/pilatus/300k`, `p03/pilatus/1M`); the 300k for SAXS and the 1M for WAXS, interchangeable per experiment (`DET-1`).
- `LambdaDetector` binds `Camera`: an X-Spectrum Lambda area detector reporting on the bare `petra3` host (`HOST-1`, `DET-1`).
- `FluorescenceDetectors` binds `EnergyDispersiveSpectrometer`: the microfocus MCA and XIA multi-channel-analyzer fluorescence detectors (`DET-1`).

## Nanofocus GINIX endstation

- `PilatusDetector` binds `Camera`: the nanofocus Pilatus 300k (`p03nano/pilatus/300k`); nano-imaging / scattering (`DET-1`).
- `FluorescenceDetectors` binds `EnergyDispersiveSpectrometer`: the nanofocus MCA fluorescence detectors and a SIS3302 digitizer (`DET-1`).
- `ExperimentShutter` binds `Shutter`: the nanofocus experiment / fast shutter (the GINIX exposure shutter) (`DET-1`, `PSS-1`).

## Families and confirmations

The Pilatus and Lambda detectors bind the catalog `Camera` Family; the MCA / XIA fluorescence detectors bind `EnergyDispersiveSpectrometer`; the experiment shutter binds `Shutter`. No new Family is coined. The detector roster per experiment, the SAXS-vs-WAXS detector assignment, the sample-to-detector distance, and the Pilatus / MCA channel detail are not fully in the registry and are pending (`DET-1`). See [Open questions](../questions.md).
