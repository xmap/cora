# Sample

*The sample-stage and beam-conditioning Assets across P01's three experiment hutches, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P01 has three experiment hutches, each with its own sample station. The beam-conditioning optics that define each technique (the high-resolution monochromators for NRS, the KB pair for RIXS) sit at the sample stage of their hutch, alongside the sample positioning.

## EH1: nuclear resonant scattering

The defining instrument of P01. Four **high-resolution monochromators** carve the meV / Moessbauer-energy bandwidth the NRS spectrum is scanned over; which is in beam depends on the isotope and the resolution wanted (`NRS-1`).

- The high-resolution monochromators bind `Monochromator`: `HighResMono400` (the 400 channel-cut, with piezo fine theta / tilt), `HighResMono1064` (the 1064 channel-cut, with piezo fine axes), `HighResMono3D` and `HighResMono3W` (the 3-bounce nested configurations). The coupled scan coordinate is `HighResMonoEnergy`, a `PseudoAxis` over the `hrm_ener` / `hrm_ener2` virtual motors (`NRS-1`).
- `CompoundRefractiveLens` binds `Transfocator`: the CRL focusing assembly (rotation / theta / x / y); the lens count and material are pending (`OPT-1`).
- `BeamDefiningSlit` binds `Slit`: the EH1 JJ slit (four blades plus virtual center / gap axes).
- `BeamPositionMonitor` and `IonChamber` bind `FluxMonitor`: the BPM and ion-chamber positioning stages for beam diagnostics and flux normalization (`DIAG-1`).
- `SampleTable` binds `Table`: the EH1 instrument table.

## EH2: diffraction

- `Goniometer` binds the catalog `Goniometer` Family: the sample-orientation circle (theta / two-theta). The registry exposes only these two axes, so it is modelled as a `Goniometer` Asset, not the composed `Diffractometer` Assembly, until the full circle count and a detector arm are confirmed (`DIFF-1`).
- `SampleStage` binds `LinearStage`: the EH2 sample positioning / centring stage (x / y / tilt).
- `DefiningSlit` and `DetectorSlit` bind `Slit`: the beam-defining and receiving slits.
- `DetectorTable` binds `Table`: the EH2 detector table.

## EH3: resonant inelastic X-ray scattering

- `KBMirrorHorizontal` and `KBMirrorVertical` bind `Mirror`: the Kirkpatrick-Baez focusing pair (each with upstream / downstream benders and theta / theta2). The bend radii and focal sizes are pending (`OPT-1`).
- `SampleStage` binds `LinearStage`: the EH3 sample stage (x / y / b / rotation / tilt) for RIXS sample positioning (`SAMPLE-1`).
- `DetectorSlit` binds `Slit`: the EH3 receiving slit.
- `InstrumentTable` binds `Table`: the EH3 spectrometer table (virtual x / y over the jack motors).

## Families and confirmations

Every Asset here binds an existing catalog Family (`Monochromator`, `Transfocator`, `Slit`, `FluxMonitor`, `Table`, `Goniometer`, `LinearStage`, `Mirror`); P01 coins none. The axis maps are read from the OnlineXML and carried confirm; the physical detail (crystal cuts, lens recipes, bend radii, the full goniometer circle count) is not in the registry and is pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
