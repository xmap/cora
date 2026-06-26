# Detector

*The detectors that make SST multi-technique. PVs verified against the RSoXS, HAXPES, and NEXAFS TOML device manifests.*

SST's three technique families show up in its detectors: which one is read decides whether the measurement is soft-X-ray scattering, photoemission, or energy-resolved absorption.

| Asset | Family | PV | Technique it serves |
| --- | --- | --- | --- |
| `ScatteringDetector` | Camera | `XF:07ID1-ES:1{GE:2}` | RSoXS soft-X-ray scattering |
| `ElectronAnalyzer` | ElectronAnalyzer | `XF:07ID-ES-SES` | HAXPES photoemission |
| `CalorimeterSpectrometer` | EnergyDispersiveSpectrometer | `XF:07ID-ES{UCAL}:` | NEXAFS energy-resolved fluorescence |
| `FluxMonitor` | FluxMonitor | `XF:07ID-ES1{DMR:I400-1}` | I0 / drain-current normalization |
| `BeamStop` | BeamStop | `XF:07ID2-ES1{BS-Ax:1}` | blocks the RSoXS direct beam |
| `SampleCamera` | Camera | `XF:07ID1-ES:1{Scr:4}` | on-axis sample viewing |

## Three detectors, three techniques

The `ScatteringDetector` is a Greateyes 4k x 4k CCD reading the soft-X-ray scattering pattern (a second SAXS-arm Greateyes is commented out in source, DET-1); it reuses `Camera`. The `CalorimeterSpectrometer` is a transition-edge-sensor (TES) microcalorimeter reading energy-resolved fluorescence for NEXAFS; it resolves photon energy per event to give a spectrum, so it reuses `EnergyDispersiveSpectrometer` (whether a cryogenic microcalorimeter is a per-Asset settings variant of that family, alongside the silicon-drift and germanium variants, or warrants its own Family is a question; carried as reuse for now). Absorption is also read as drain current and partial electron yield through the SR570 / ADC flux channels.

## The electron analyzer: a graduation

The `ElectronAnalyzer` is the HAXPES Scienta SES hemispherical electron analyzer (pass energy, lens mode, kinetic / excitation energy, acquisition mode). It is a photon-in / electron-out device that fits no photon-detector family, so it binds the `ElectronAnalyzer` family that NSLS-II [ESM](../../esm/index.md) introduced. SST-HAXPES is the **second** sighting of that family, the same Scienta SES analyzer type as ESM, so it earned the rule-of-three; the abstraction is settled (a hemispherical electron analyzer is a distinct, recurring device class), so it GRADUATED into the catalog (ARPES-1), ESM's references swept alongside. The flux channels reuse `FluxMonitor` (graduated in #353); the beamstop reuses `BeamStop`.
