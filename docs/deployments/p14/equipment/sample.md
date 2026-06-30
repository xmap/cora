# Sample

*The two-endstation instruments and sample-environment Assets at P14, as CORA models them today. First cut, reverse-engineered from the MXCuBE config.*

P14's two experiment hutches each carry a macromolecular-crystallography sample environment. EH1 is built around the EMBLMiniDiff microdiffractometer (the main MX instrument, cryo-cooled, for rotation MX); EH2 around the EMBLBSD diffractometer with its own beam-defining optics and a positioning table. Because EMBL publishes the MXCuBE configs, both diffractometers and their axes are named, so each resolves into a real `Goniometer` Asset, with the omega / kappa / sample-centring axes carried as its axis bank (`MX-1`).

## EH1: the main diffractometer

- `DiffractometerEH1` binds the graduated `Goniometer`: the EH1 EMBLMiniDiff microdiffractometer (Exporter-hosted on `p14md302.embl-hamburg.de:9001`); the main MX sample-orientation instrument carrying the omega rotation, the kappa / kappa-phi mini-kappa, the sample x / y / z centring (phix / phiy / phiz / sampx / sampy), and the focus / holder-length axes. The goniometer geometry is carried confirm (`MX-1`).
- `BeamApertureEH1` binds `Aperture`: the EH1 beam-defining aperture on the microdiff (EMBLAperture, Exporter-hosted); the aperture-size table is carried confirm (`OPT-1`).
- `BeamstopEH1` binds `BeamStop`: the EH1 microdiff beamstop (EMBLBeamstop, Exporter-hosted); the direct-beam stop in front of the sample.
- `SampleObjectiveEH1` binds `Objective`: the EH1 on-axis sample-viewing zoom objective (MicrodiffZoom, Exporter-hosted); the OAV magnification path (`OAV-1`).
- `SampleIlluminationEH1` binds `Backlight`: the EH1 microdiff sample illumination (MicrodiffLight back / front lights, Exporter-hosted); the on-axis viewing illumination, the `Backlight` affordance shared with i03 / i24 / FMX / i19 / P13 (`DET-1`).

## EH2: the second diffractometer

- `DiffractometerEH2` binds the graduated `Goniometer`: the EH2 EMBLBSD diffractometer (Exporter-hosted on `pe2bsd01.embl-hamburg.de:9001`); the second-endstation MX instrument with its own omega / kappa / centring axes. Some axes are published as `MotorMockup` in the config (simulation placeholders), so the EH2 motions are carried with caution (`MX-1`, `MOCK-1`).
- `BeamApertureEH2` binds `Aperture`: the EH2 beam-defining aperture (EMBLAperture on `pe2bsd01`); the aperture-size table is carried confirm (`OPT-1`).
- `BeamstopEH2` binds `BeamStop`: the EH2 beamstop (EMBLBeamstop on `pe2bsd01`); the direct-beam stop in front of the EH2 sample.
- `SampleObjectiveEH2` binds `Objective`: the EH2 on-axis sample-viewing zoom objective (ExporterZoom on `pe2bsd01`); the EH2 OAV magnification path (`OAV-1`).
- `SampleIlluminationEH2` binds `Backlight`: the EH2 sample illumination (MicrodiffLight back / front lights on `pe2bsd01`); the EH2 on-axis viewing illumination (`DET-1`).
- `ExperimentTableEH2` binds `LinearStage`: the EH2 experiment-table horizontal / vertical positioning (EMBLTableMotor table_hor / table_ver); the endstation table carrying the EH2 diffractometer. No Exporter / TINE handle is in the config object, so the table motions are carried confirm (`TABLE-1`, `MOCK-1`).

## Sample environment

The cryostream that cools the crystals is not labelled as a device in the MXCuBE configs (MXCuBE drives it through a separate service), so it is carried as a question rather than modelled here (`CRYO-1`). Its liquid-nitrogen supply is carried as a Supply observation (`SUP-1`).

## Families and confirmations

Every Asset here binds an existing catalog Family (`Goniometer`, `Aperture`, `BeamStop`, `Objective`, `Backlight`, `LinearStage`); P14 coins none. `Backlight` is the one loose (not-yet-catalog) Family, a sample-illumination affordance held for graduation across i03 / i24 / FMX / i19 / P13 and now P14 (`DET-1`). The axis maps are read from the MXCuBE configs and carried confirm; the goniometer geometries, the aperture-size tables, the EH2 table handle, and the cryostream service are pending (`MX-1`, `OPT-1`, `TABLE-1`, `CRYO-1`), and the EH2 mockup axes are flagged (`MOCK-1`). The automated sample changer is MXCuBE bookkeeping, not a device, and would be a deferred sample-exchange Procedure (`ROBOT-1`). See [Open questions](../questions.md) and the [Inventory](../inventory.md).
