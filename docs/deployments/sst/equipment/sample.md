# Sample

*The endstation sample manipulators and the in-situ environment. PVs verified against the RSoXS and HAXPES TOML device manifests.*

SST holds samples in UHV manipulators, one per endstation, each presenting the beam to a different measurement: a solid-sample stage for soft-X-ray scattering, a multi-axis manipulator for photoemission.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `RSoXSManipulator` | Manipulator | `XF:07ID2-ES1{Stg-Ax:}` | orients the sample for soft scattering |
| `HAXPESManipulator` | Manipulator | `XF:07ID1-BI{HAX-Ax:}` | orients the sample for photoemission |
| `SampleTemperature` | TemperatureController | `XF:07ID2-ES1{TCtrl:1}LS336:` | in-situ thermal environment |

## The manipulators

Both manipulators reuse the `Manipulator` family that Diamond and NSLS-II ESM earned (a UHV multi-axis sample stage, distinct from a `Goniometer` or a `Hexapod`): the `RSoXSManipulator` is a four-axis solid-sample stage (X / Y / Z / Yaw), the `HAXPESManipulator` a multi-axis stage (X / Y / Z / R). This is the reuse point: ESM graduated `Manipulator` from the SIX and ESM UHV stages, and SST binds it twice more, one per endstation, without any new vocabulary. The NEXAFS endstation has its own manipulator (`XF:07ID1-BI{NXFS-Ax:}`), deferred (INSITU-1).

## Sample environment

The `SampleTemperature` Lakeshore controller reuses the `TemperatureController` family (graduated in #350). SST's soft-matter and surface science also use a set of in-situ accessories, a HAXPES flood gun (charge neutralizer) and source-measure unit (sample bias), a UCAL ADR cryostat, and an RSoXS syringe pump, each of which fits no existing family cleanly and is deferred to a named question (INSITU-1) rather than modelled at this design phase.
