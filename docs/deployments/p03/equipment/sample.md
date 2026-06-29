# Sample

*The sample-stage and focusing Assets across P03's two scattering endstations, as CORA models them today. First cut, reverse-engineered from the OnlineXML.*

P03 has two endstations sharing the optics chain: a microfocus endstation (CRL focusing) and the nanofocus GINIX endstation (waveguide focusing). The sample positioning at each is exposed as a generically-named motor bank (`expmi_mot01..64` microfocus, `mot01..40` nanofocus), grouped as a stage Asset carrying the bank prefix, per-axis roles pending (`GROUP-1`).

## Microfocus endstation

- `CRLHexapod` binds `Hexapod`: the microfocus CRL focusing hexapod (`crl1hex`, six axes) plus the CRL z-stage; the compound-refractive-lens positioning (`OPT-1`).
- `GuardSlit` binds `Slit`: the microfocus guard slit (`G1`, a Galil DMC slit controller: blades + center / gap virtual axes); the SAXS beam-defining / guard slit (`OPT-1`).
- `BeamlineSlit4` binds `Slit`: the slit4 positioning (`S4_X / Y / Z`) (`OPT-1`).
- `SampleStage` binds `LinearStage`: the microfocus sample / instrument motor bank (`expmi_mot01..64`); per-axis roles grouped (`GROUP-1`).
- `SampleTemperature` binds `TemperatureController`: the sample-environment Eurotherm 2604 (`TEMP-1`).

## Nanofocus GINIX endstation

- `WaveguideSmarPod` binds `Hexapod`: the GINIX waveguide SmarPod (`hexa3`, six axes); positions the nano-focusing waveguide (`OPT-1`).
- `SampleHexapod` binds `Hexapod`: the GINIX sample hexapod (`hexa2`) plus the cube stage (`cube1`); coarse sample positioning (`SAMPLE-1`).
- `SampleRotation` binds `RotaryStage`: the GINIX sample rotation (`ROT_PHI / ROT_X`, Smaract); the nano-tomography / scanning rotation (`SAMPLE-1`).
- `WaveguideLinearStages` binds `LinearStage`: the GINIX waveguide linear stages (`LLS1 / LLS2`) (`OPT-1`).
- `GuardSlit` binds `Slit`: the nanofocus guard slit (`S6`, Galil DMC slit controller) (`OPT-1`).
- `SampleStage` binds `LinearStage`: the nanofocus sample / instrument motor bank (`mot01..40`); per-axis roles grouped (`GROUP-1`).
- `SampleIllumination` binds `Camera`: the GINIX sample LED illumination and the PS-camera-VHR viewing camera for centring (`DET-1`).

## Families and confirmations

Every Asset here binds an existing catalog Family (`Hexapod`, `Slit`, `LinearStage`, `RotaryStage`, `TemperatureController`, `Camera`); P03 coins none at the sample stage. The axis maps are read from the OnlineXML and carried confirm; the per-axis roles of the motor banks, the CRL / waveguide focal sizes, and the GINIX geometry are not in the registry and are pending. See [Open questions](../questions.md) and the [Inventory](../inventory.md).
