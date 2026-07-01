# Sample

*The sample-stage and sample-environment Assets across P09's three areas, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P09 carries three sample areas: the MONO resonant-scattering experiment, the DIF diffraction hutch, and the MAG high-field magnetism endstation. Each centres on a six-circle (E6C) diffractometer goniometer; the MONO and MAG areas add polarization and magnetism instruments.

## MONO: resonant scattering

- `PhaseRetarder` binds the catalog `PhaseRetarder` Family: the polarization phase-retarder circles (`phaseretardercircle1 / 2`) plus the AttoCube `pchi / pperp` fine axes; sets incident polarization (`POL-1`).
- `PolarizationAnalyzer` binds the allowlisted-loose `PolarizationAnalyzer` Family: the scattered-beam analyzer; resolves scattered polarization (`POL-2`).
- `Goniometer` binds the catalog `Goniometer` Family: the six-circle (E6C) diffractometer (`e6cctrl` + `diffrac_eh1`); modelled as a `Goniometer` Asset, not the composed `Diffractometer` Assembly (`DIFF-1`).
- `SampleTemperature` binds `TemperatureController`: the CryoCon 32, Lakeshore 336 / 340, and LSCI controllers; cryogenic sample cooling (`TEMP-1`).

## DIF: diffraction

- `Goniometer` binds the catalog `Goniometer` Family: the DIF six-circle (E6C) diffractometer (`e6cctrleh1 / eh2`, OMS VME58 controlled) (`DIFF-1`).
- `SampleStage` binds `LinearStage`: the DIF sample / instrument motor bank (~69 axes); per-axis roles grouped (`GROUP-1`).

## MAG: high-field magnetism

- `Magnet` binds the allowlisted-loose `Magnet` Family: the 14 T superconducting sample-environment magnet (`magnet14tf`) (`MAG-1`).
- `Goniometer` binds the catalog `Goniometer` Family: the MAG six-circle diffractometer (`diffrac_mag` + the `diffracmu` mu circle) (`DIFF-1`).
- `SampleHexapod` binds `Hexapod`: the MAG sample hexapod (`hexa_*`); coarse sample positioning within the magnet (`SAMPLE-1`).
- `SamplePiezo` binds `LinearStage`: the MAG sample piezos (PI E-710 scan + E-725 sample); fine positioning (`SAMPLE-1`).
- `PolarizationAnalyzer` binds the allowlisted-loose `PolarizationAnalyzer` Family: the MAG scattered-beam analyzer (`POL-2`).
- `Absorber` binds `Filter`: the MAG beam absorber / attenuator (`OPT-1`).
- `SampleTemperature` binds `TemperatureController`: the MAG Lakeshore 336 / 340 controllers (`TEMP-1`).

## Families and confirmations

The polarization / magnetism instruments bind the catalog `PhaseRetarder` Family plus the allowlisted-loose `PolarizationAnalyzer` and `Magnet` Families (the 4-ID precedent); the diffractometers bind the catalog `Goniometer`; the hexapod `Hexapod`, the piezos `LinearStage`, the cooling `TemperatureController`, the absorber `Filter`. P09 coins no new Family; it is the second consumer of the 4-ID vocabulary. The axis maps are read from the OnlineXML and carried confirm; the diffractometer circle counts, the magnet field, and the per-axis bank roles are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
