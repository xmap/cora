# Detector

*The SPECS hemispherical analyzer, the fluorescence detectors, and the electron-yield chain. First cut; PVs read from the profile collection, carried confirm.*

IOS detection is photon-in / electron-out and photon-in / photon-out at once: the SPECS hemispherical analyzer records the photoelectron spectrum for ambient-pressure photoemission, while the Vortex and Xspress3 silicon-drift detectors and the scaler-read electron-yield channels record the soft NEXAFS / XAS signal. They are modelled in the detection stage of the [descriptor](../inventory.md).

The analyzer binds the catalog `ElectronAnalyzer` Family (the third sighting after ESM and SST, and the first non-Scienta and first ambient-pressure one); the silicon-drift detectors bind `EnergyDispersiveSpectrometer`; the scaler and the Au-mesh I0 reference bind `FluxMonitor`; the exit-slit diagnostic camera binds `Camera`. No new family is introduced (see [Model](../model.md#no-new-families)).

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `ElectronAnalyzer` | `ElectronAnalyzer` | SPECS hemispherical analyzer, the AP-PES detector; pass energy / lens mode / kinetic energy / acquisition mode are settings (`DET-1`) |
| `FluorescenceDetector` | `EnergyDispersiveSpectrometer` | Vortex silicon-drift detector + MCA, partial-fluorescence-yield XAS (`DET-2`) |
| `FluorescenceArray` | `EnergyDispersiveSpectrometer` | Xspress3 four-channel silicon-drift detector (`DET-2`) |
| `Scaler` | `FluxMonitor` | electron-yield (TEY / PEY) counting electronics behind the `CurrAmp:1/2/3` current amplifiers (`DET-3`) |
| `IncidentFluxMonitor` | `FluxMonitor` | gold-mesh I0 reference for incident-flux normalization (`DET-3`) |
| `DiagnosticCamera` | `Camera` | exit-slit YAG centroid diagnostic camera |

## The analyzer and the yield chain

The SPECS analyzer (`XF:23ID2-ES{SPECS}`) disperses photoelectrons by kinetic energy over a window set by the pass energy and lens mode, acquiring either a full spectrum or a single counting channel. It measures electrons out, not photons, so no photon-detector Family fits; it binds `ElectronAnalyzer`, the same Family the ESM ARPES and SST HAXPES Scienta analyzers bind. IOS is the third sighting and the first non-Scienta and first ambient-pressure one; the analyzer make, the lens-mode set, and the pass-energy range are a per-Asset settings or bound-Model difference, not a Family split (`DET-1`).

The soft NEXAFS / XAS signal is read three ways, all as settings on the same chain rather than as separate devices: **TEY** (total electron yield, the sample drain current through the scaler and the `CurrAmp` amplifiers), **PEY** (partial electron yield, kinetic-energy-selected electrons through the analyzer), and **PFY** (partial fluorescence yield, a region-of-interest on the Vortex or Xspress3 silicon-drift detector). The Au mesh (`XF:23ID2-BI{AuMesh:1`) is the I0 reference for normalization. The scaler and the Au mesh both bind `FluxMonitor`; the silicon-drift detectors bind `EnergyDispersiveSpectrometer` (`DET-2`, `DET-3`).

## Why no new detector family

IOS detection is reinforcement: the analyzer reuses `ElectronAnalyzer` (third sighting), the silicon-drift detectors reuse `EnergyDispersiveSpectrometer`, the counters reuse `FluxMonitor`, and the diagnostic camera reuses `Camera`. The TEY / PEY / PFY detection modes are carried as per-Asset settings, not new Families; the detector models and channel maps are `DET-1`, `DET-2`, and `DET-3`. See [Inventory](../inventory.md) for the Asset tree.
