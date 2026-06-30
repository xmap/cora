# Detector

*The detectors that make ISS an absorption + emission beamline. PVs verified against the iss-profile-collection startup files.*

Which detector is read decides the measurement: the ion chambers for transmission EXAFS, the silicon-drift array for fluorescence EXAFS, and the crystal emission spectrometers for XES and HERFD.

| Asset | Family | PV | Technique it serves |
| --- | --- | --- | --- |
| `IonChambers` | FluxMonitor | `XF:08IDB-CT{Amp-I0}` | transmission EXAFS (I0 / It / Ir / If) |
| `FluorescenceDetector` | EnergyDispersiveSpectrometer | `XF:08IDB-ES{Xsp:1}:` | fluorescence EXAFS (Xspress3 SDD) |
| `AreaDetector` | Camera | `XF:08IDB-ES{Det:PIL1}:` | emission-spectrometer focus / 2D patterns |
| `JohannSpectrometer` | EmissionSpectrometer | `XF:08IDB-OP{HRS:1}` | XES / HERFD (back-scattering) |
| `VonHamosSpectrometer` | EmissionSpectrometer | `XF:08IDB-OP{MC:3-Ax}` | XES (wavelength-dispersive) |

## Absorption detectors

The `IonChambers` are the I0 / It / Ir / If transmission and reference chambers, read through configurable amplifiers (the in-house ICAmplifier at `XF:08IDB-CT{Amp-I0 / It / Ir / If}` and, currently, Keithley 428 preamps at `XF:08ID-ES:{K428}:A-D:`) and digitized synchronously by the analog pizza box during the fly-scan; they reuse `FluxMonitor` (graduated in #353). The `FluorescenceDetector` is a four-channel Xspress3 silicon-drift array (`XF:08IDB-ES{Xsp:1}:` channels C1-C4) for fluorescence EXAFS, reusing `EnergyDispersiveSpectrometer`. The exact channel-to-chamber map and Xspress3 element count are DET-1.

## The emission spectrometers: a graduation

The signature ISS instruments are two crystal **emission** spectrometers. The `JohannSpectrometer` is a Rowland-circle back-scattering analyzer composing a main crystal plus four auxiliary crystals (`XF:08IDB-OP{HRS:1-Stk:1-5}`) on a two-theta detector arm (`XF:08IDB-OP{HRS:1-Det:Gon:Theta1 / Theta2}`), for high-energy-resolution XES and HERFD. The `VonHamosSpectrometer` is a wavelength-dispersive analyzer (`XF:08IDB-OP{MC:3-Ax}`, sharing the detector arm) that spreads the emitted spectrum onto the `AreaDetector` (a Pilatus 100k, reusing `Camera`).

Both bind the `EmissionSpectrometer` family that LCLS-MFX introduced for its von Hamos XES spectrometer. ISS is the **second** sighting of that family, so it earned the rule-of-three; the abstraction is settled (a crystal-analyzer emission spectrometer is a distinct, recurring device, not a point Sensor and not a beam-conditioning Monochromator), so it GRADUATED into the catalog (SPEC-1), LCLS-MFX's references swept alongside. Whether each of the Johann's analyzer crystals is a child Asset or a setting is the residual SPEC-1 question. It stays distinct from the still-loose `EnergyAnalyzer` (the IXS diced-crystal energy-selecting analyzer) and `SpectrometerArm` (the SIX grating RIXS arm).
