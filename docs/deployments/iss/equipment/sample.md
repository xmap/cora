# Sample

*The sample stage, the energy-calibration reference foil wheel, and the in-situ environment. PVs verified against the iss-profile-collection startup files.*

ISS presents the sample to the beam on a multi-axis stage and a goniometer, with an upstream reference foil wheel that provides a metal-foil standard for per-scan energy calibration.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleStage` | LinearStage | `XF:08IDB-OP{Stage:Sample}` | X / Y / Z sample translation |
| `SampleGoniometer` | Goniometer | `XF:08IDB-OP{Gon:Th}` | sets the sample angle to the beam |
| `ReferenceFoilWheel` | RotaryStage | `XF:08IDB-OP{FoilWheel1:Rot}` | presents foil standards for energy calibration |
| `SampleTemperature` | TemperatureController | `XF:08ID-ES{LS:331-1}:` | in-situ thermal environment |

## The sample stages

The `SampleStage` reuses the `LinearStage` family (X / Y at `XF:08IDB-OP{Stage:Sample-Ax:X / Y}Mtr`, Z at `XF:08IDB-OP{Misc-Ax:2}Mtr`, with a finer SampleXY and an auxiliary stage on it), and the `SampleGoniometer` the `Goniometer` family (`XF:08IDB-OP{Gon:Th:1 / :2}Mtr`) for the sample angle. The `ReferenceFoilWheel` reuses the `RotaryStage` family (`XF:08IDB-OP{FoilWheel1:Rot}Mtr`, with a second wheel on the SampleXY stage): it rotates a metal-foil standard into a reference ion chamber so every energy scan carries an absolute-energy calibration. None of these is new vocabulary.

## Sample environment

The `SampleTemperature` Lakeshore 331 reuses the `TemperatureController` family (graduated in #350). ISS's ion chambers are filled and purged through He / N2 mass-flow controllers (`XF:08IDB-OP{IC}FLW:`), and the beamline runs a range of in-situ sample environments; the fill-gas flow would bind the graduated `FlowController` Family but, with the broader in-situ environment, is deferred to a named question (ENV-1) rather than modelled at this design phase.
