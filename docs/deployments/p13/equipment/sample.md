# Sample

*The experiment-hutch instrument and sample-environment Assets at P13, as CORA models them today. First cut, reverse-engineered from the MXCuBE config.*

P13's experiment hutch carries the macromolecular-crystallography sample environment built around the EMBLMiniDiff microdiffractometer: a goniometer (cryo-cooled) for rotation MX, with on-axis viewing and a beam-defining aperture and beamstop. Because EMBL publishes the MXCuBE config, the diffractometer and its axes are named (unlike P11's grouped banks), so the instrument resolves into a real `Goniometer` Asset, with the omega / kappa / sample-centring axes carried as its axis bank (`MX-1`).

## The diffractometer

- `Diffractometer` binds the graduated `Goniometer`: the EMBLMiniDiff microdiffractometer (Exporter-hosted on `p13md201.embl-hamburg.de:9001`); the MX sample-orientation instrument carrying the omega rotation, the kappa / kappa-phi mini-kappa, the sample x / y / z centring, and the focus / holder-length axes. The goniometer geometry is carried confirm (`MX-1`).
- `MDCentringStage` binds `LinearStage`: the diffractometer vertical centring axis (`/P13/MD/MD_0`) and the coupled microdiff centring motions; grouped with the goniometer as the sample-centring stage (`MX-1`).

## The sample-defining optics

- `BeamAperture` binds `Aperture`: the beam-defining aperture on the microdiff (EMBLAperture, Exporter-hosted); the aperture-size table is carried confirm (`OPT-1`).
- `Beamstop` binds `BeamStop`: the microdiff beamstop (EMBLBeamstop, Exporter-hosted); the direct-beam stop in front of the sample.
- `SampleObjective` binds `Objective`: the on-axis sample-viewing zoom objective (MicrodiffZoom, Exporter-hosted); the OAV magnification path (`OAV-1`).
- `SampleIllumination` binds `Backlight`: the microdiff sample illumination (MicrodiffLight back / front lights, Exporter-hosted); the on-axis viewing illumination, the `Backlight` affordance shared with i03 / i24 / FMX / i19 (`DET-1`).

## Sample environment

The cryostream that cools the crystal is not labelled as a device in the MXCuBE config (MXCuBE drives it through a separate service), so it is carried as a question rather than modelled here (`CRYO-1`). Its liquid-nitrogen supply is carried as a Supply observation (`SUP-1`).

## Families and confirmations

Every Asset here binds an existing catalog Family (`Goniometer`, `LinearStage`, `Aperture`, `BeamStop`, `Objective`, `Backlight`); P13 coins none. `Backlight` is the one loose (not-yet-catalog) Family, a sample-illumination affordance held for graduation across i03 / i24 / FMX / i19 and now P13 (`DET-1`). The axis maps are read from the MXCuBE config and carried confirm; the goniometer geometry, the aperture-size table, and the cryostream service are pending (`MX-1`, `OPT-1`, `CRYO-1`). The automated sample changer is MXCuBE bookkeeping, not a device, and would be a deferred sample-exchange Procedure (`ROBOT-1`). See [Open questions](../questions.md) and the [Inventory](../inventory.md).
