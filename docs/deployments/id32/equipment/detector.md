# Detector

*The RIXS and XES dispersive spectrometer arms, the scattered-beam polarimeter, and the two Andor CCDs. First cut; handles read from the BLISS Beacon config, carried confirm.*

ID32 detection is energy-dispersive and arm-borne: a long spectrometer arm carries a grating that disperses the scattered (RIXS) or emitted (XES) soft X-ray beam onto a CCD at its focus, and a polarimeter on the RIXS arm resolves the polarization of the scattered beam. They are modelled in the detection stage of the [descriptor](../inventory.md).

## Detection chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `RixsSpectrometerArm` | `SpectrometerArm` (loose) | the roughly 5 m dispersive RIXS arm (`rixs_spectro`, IcePAP `iceid324`): real axes `detx` / `detz` / `grtx` drive the virtual arm radii; grating modes RIXS_2500 (radius 122000) and RIXS_1400; held at the rule-of-three (`RIXS-1`) |
| `XesSpectrometerArm` | `SpectrometerArm` (loose) | the XES Rowland-geometry emission arm (`xes_spectro`, IcePAP `iceid329`): the same `SpectrometerArmsController` class, grating mode XES_1200 (radius 26055); the second arm that completes the rule-of-three (`RIXS-1`) |
| `Polarimeter` | `PolarizationAnalyzer` (catalog) | the scattered-beam polarization-analysis block on the RIXS arm (`iceid324` `thpol` / `chipol` / `tthpol`); binds the graduated catalog `PolarizationAnalyzer` across 4-ID / i10 / ID32 / P09 (`POL-2`) |
| `RixsDetector` | `Camera` | the Andor deep-depletion CCD at the RIXS arm focus (`id32/limaccds/andor_1`) (`DET-1`) |
| `XesDetector` | `Camera` | the Andor CCD at the XES / XMCD endstation (`id32/limaccds/andor_2`) (`DET-1`) |

The chain reads outward from the sample. The RIXS arm points its grating at the scattered beam and disperses it across the Andor CCD at the arm focus; the XES arm does the same for the emitted beam in a Rowland geometry; the polarimeter on the RIXS arm resolves the scattered-beam polarization. Detection is energy-dispersive, built by the arm geometry and the CCD readout, not by a point counter.

## The spectrometer arms: a loose family at its rule-of-three

The two dispersive arms are the heart of ID32's detection, and they are the device that brings the loose `SpectrometerArm` Family to a genuine rule-of-three. Both bind the **same** BLISS `SpectrometerArmsController` class (the RIXS `rixs_spectro` and the XES `xes_spectro`), differing only in geometry and grating mode; with the SIX soft-RIXS arm, the family is now sighted three times across two sites. `SpectrometerArm` was coined loose at SIX precisely because it fits no point-Sensor family: it is an arm that **positions** a grating and **carries** a `Camera` at its focus, so it presents the `Positioner` Role, not a scalar `FluxMonitor` / `EnergyDispersiveSpectrometer` reading. ID32 holds it loose and defers the graduation to a dedicated catalog PR per the owner decision (`RIXS-1`); see [Model](../model.md#loose-families-held-at-the-rule-of-three).

The scattered-beam polarimeter on the RIXS arm binds the graduated catalog `PolarizationAnalyzer` Family (earned across 4-ID / i10 / ID32 / P09, presenting Positioner, `POL-2`). The CCDs at the arm focuses reuse the catalog `Camera` (`DET-1`).

## Why no new detector family

The detection side coins no new Family. The CCDs are area detectors and bind `Camera`; the dispersive arms reuse the loose `SpectrometerArm` SIX coined; the polarimeter binds the graduated catalog `PolarizationAnalyzer` (earned across 4-ID / i10 / ID32 / P09). The genuinely new modelling at ID32 is not a device class but the rule-of-three the `SpectrometerArm` family reaches, held here and routed to a dedicated graduation PR.

## Families

Reused from the catalog: `Camera` (the two Andor CCDs) and `PolarizationAnalyzer` (the RIXS polarimeter; graduated across 4-ID / i10 / ID32 / P09, `POL-2`). Reused loose, held at its rule-of-three: `SpectrometerArm` (the RIXS and XES arms, `RIXS-1`). The diffractometer and reciprocal-space axis the arms read against live on the [Sample](sample.md) side. See [Inventory](../inventory.md) for the Asset tree and [Model](../model.md) for the graduation plan.
