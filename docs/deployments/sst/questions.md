# Open questions

*What CORA needs the SST team to confirm. This model is reverse-engineered from public open source (the `NSLS2/sst-*-profile-collection` endstation repos and the shared `NSLS-II-SST/sst-base` package): the EPICS PVs are read from the TOML device manifests and the sst-base device classes, but vendor identities, physical positions, and the per-endstation configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The two undulator periods and gap / phase ranges (soft EPU60, tender U42). The devices (`SR:C07-ID:G1A{SST1:1}`, `{SST2:1}`) are confirmed from the sst-base energy classes; soft range about 71-2250 eV. | Two insertion devices, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:07ID-PPS{Sh:FE}`, `XF:07IDA-PPS{PSh:n}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The branch-to-hutch mapping and the physical hutch names / numbering (not in source): which endstations (RSoXS, NEXAFS on the soft SST-1 branch; HAXPES on the tender SST-2 branch; plus UCAL, VPPEM) sit in which enclosures? The PV zone numbers (07ID1 / 07ID2 / 07ID6) do not map one-to-one to a branch. | An optics hutch plus a soft (SST-1) and a tender (SST-2) experiment enclosure. | The Enclosure set and roles. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The soft PGM grating set and the tender DCM crystal cut and ranges. Both monochromators (`Mono:PGM1`, `Mono:DCM1`) are in source. | One GratingMonochromator and one Monochromator Asset, settings blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | Is energy scanned as the measurement (NEXAFS absorption sweeps the soft PGM across an edge), warranting the energy-scan Capability the catalog anticipates? | NEXAFS mapped to deferred Capabilities; energy-scan deferred (the BMM question). | The spectroscopy Capability decision. |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ARPES-1 | Blocks-go-live | The HAXPES Scienta SES hemispherical analyzer model, lens modes, and pass-energy / kinetic-energy controls. | An `ElectronAnalyzer` Asset (catalog Family, graduated at this 2nd sighting after ESM) presenting the Detector Role. | The analyzer model. |
| DET-1 | Blocks-go-live | Which detectors are live per endstation: the RSoXS Greateyes WAXS CCD (a second SAXS-arm CCD is commented out), the HAXPES analyzer, the NEXAFS microcalorimeter and drain-current / partial-electron-yield channels. | The WAXS CCD, the analyzer, and the microcalorimeter modelled; the SAXS arm excluded. | The detector roster per endstation. |
| TEMP-1 | Nice-to-have | Which sample-environment thermal units are live per endstation (the Lakeshore controllers). | One `TemperatureController` Asset; the others noted. | The sample-environment Assets. |
| DIAG-1 | Nice-to-have | The flux-channel map (the I0 mesh / diode, the drain-current and ion-chamber SR570 channels) and the `BeamPositionMonitor` sensor fold-vs-promote hold. | Read-only flux (`FluxMonitor`) and beam-position (loose `BeamPositionMonitor`) probes; channel maps blank. | The FluxMonitor and BeamPositionMonitor bindings. |
| INSITU-1 | Nice-to-have | The endstations and in-situ accessories deferred at this design phase: the NEXAFS endstation detail (drain-current / partial-electron-yield channels), the UCAL microcalorimeter ADR cryostat, the VPPEM microscope, the HAXPES flood gun and source-measure unit, and the RSoXS syringe pump. None fits an existing family cleanly. How does CORA model these? | Deferred; the main RSoXS / HAXPES / NEXAFS-TES legs are modelled; the rest are named here. | The deferred endstation and in-situ Assets. |

## Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs across the branches. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the soft-scattering (RSoXS), absorption (NEXAFS), and photoemission (HAXPES) Capabilities enter CORA's catalog, or stay deferred? This is the same owner-scope decision the other scattering / spectroscopy / photoemission beamlines opened. | Capabilities deferred (rendered unlinked), no Practice recorded. | The technique Capability scope. |
