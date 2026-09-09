# Notes

## Techniques

*What CORA would run at SST: soft-scattering, absorption, and photoemission techniques, each a [Catalog](../../catalog/methods.md) Method. SST spans three technique families on two branches, and follows the deferral discipline of the beamlines that brought each to CORA.*

SST's techniques are new-domain science (soft-X-ray scattering, absorption, photoemission), the families Diamond and the earlier NSLS-II soft-X-ray beamlines brought to CORA. The Methods below render unlinked and are carried pending until the owner-scope decision (TECH-1) brings them into the catalog.

| Technique | Branch / mode | Notes |
| --- | --- | --- |
| Resonant soft X-ray scattering (RSoXS) | soft, monochromatic | scattering pattern on the Greateyes CCD; the i22 / CSX scattering family, new Capability pending (TECH-1) |
| NEXAFS absorption | soft, energy sweep | drain current / partial electron yield / microcalorimeter fluorescence over an energy scan; the BMM energy-scan question (ENERGY-1, TECH-1) |
| HAXPES photoemission | tender, fixed energy | photoelectron spectra on the hemispherical analyzer; the ESM photoemission family, new Capability pending (TECH-1) |

All three need the per-endstation [sample manipulator](sample.md) and [detector](detector.md); the fast shutter gates the exposure, and the endstation in control selects the branch.

### Why the Capabilities stay deferred

Each of SST's three technique families sits on a Capability the catalog does not yet carry, and the discipline is the same one the originating beamlines applied: soft-X-ray scattering follows Diamond i22 and NSLS-II CSX (the scattering Capabilities are pending, TECH-1); NEXAFS absorption follows BMM (energy-scan-as-the-measurement, deferred at ENERGY-1); photoemission follows NSLS-II ESM (the `angle_resolved_photoemission` Method ESM coined is pending, and HAXPES is the hard / tender photoemission companion). The device Roles already exist (the CCD presents Detector, the manipulators present Positioner, the analyzer and microcalorimeter are the energy-resolving detectors); what is new is the science Capability, not a device shape. SST reinforces all three at one more, larger instrument without coining any, so it records **no Practice** in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

The per-technique reduction (scattering reduction, photoemission spectra, NEXAFS spectra) is `ComputePort` work, not beamline Methods.

## Governance

*Who may act at SST and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

### Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An SST beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

### The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may select the active branch and endstation, start an acquisition, sweep energy, run an in-situ program, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

### Two branches under one custody

SST's defining governance wrinkle is that two branches and several endstations share one sector and one beamtime allocation. CORA's Campaign and Trust shapes are where that resolves: the endstation in control is a beamline-state fact the trust boundary reads, so a command valid for the soft RSoXS endstation is not automatically valid when the tender HAXPES endstation is live. If an autonomous Agent were added to drive an endstation, it would be a facility principal scoped at the Site, governed by the same trust boundary, with each choice recorded as a [Decision](../../architecture/modules/decision/index.md). None is declared yet.

## Model

*The developer's by-kind index: where each CORA aggregate's SST content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SST |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (7-ID-A optics, SST-1 soft, SST-2 tender) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new Family.** SST is a reuse-and-reinforce deployment at Site scale: the soft PGM binds `GratingMonochromator` (graduated across SIX / CSX / ESM, a fourth sighting), the tender DCM `Monochromator`, the sample manipulators `Manipulator` (graduated by ESM, bound twice more here), the soft-scattering CCD and viewing cameras `Camera`, the microcalorimeter `EnergyDispersiveSpectrometer`, the flux channels `FluxMonitor`, the thermal stage `TemperatureController`, the mirrors `Mirror`, the slits `Slit`, the shutters `Shutter`, the beamstop `BeamStop`.
- **The `ElectronAnalyzer` graduation.** The HAXPES Scienta SES hemispherical analyzer binds the `ElectronAnalyzer` family NSLS-II ESM introduced. SST-HAXPES is the **second** sighting (the same Scienta SES type), so it earned the rule-of-three, the way `GratingMonochromator` (CSX) and `Manipulator` (ESM) graduated at their second sighting. The abstraction is settled (a hemispherical electron analyzer is a distinct, recurring photon-in / electron-out device, not a photon detector), so it GRADUATED into the catalog (`ARPES-1`); ESM's references were swept loose to graduated alongside.
- **The graduated `PositionMonitor`.** The beam-position diagnostics bind the graduated catalog `PositionMonitor` Family that several deployments share: it presents the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux. The per-Asset beam-position channel map stays open (`DIAG-1`).
- **No new Capability or Method.** Soft-scattering, absorption, and photoemission sit on deferred / pending Capabilities (TECH-1, ENERGY-1, the ESM `angle_resolved_photoemission`); SST reinforces all three without coining any, and records no Practice. The per-technique reduction is `ComputePort` work.
- **The deferred endstations and in-situ accessories.** The NEXAFS endstation detail (drain-current / partial-electron-yield channels), the UCAL microcalorimeter ADR cryostat, the VPPEM microscope, the HAXPES flood gun and source-measure unit, and the RSoXS syringe pump are named in a question (`INSITU-1`); none fits an existing family cleanly, so they are deferred rather than modelled. SST models the RSoXS, HAXPES, and NEXAFS-microcalorimeter legs as the representative endstations, the way SRX modelled one of its endstations and 32-ID one of several instruments.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.

## Open questions

*What CORA needs the SST team to confirm. This model is reverse-engineered from public open source (the `NSLS2/sst-*-profile-collection` endstation repos and the shared `NSLS-II-SST/sst-base` package): the EPICS PVs are read from the TOML device manifests and the sst-base device classes, but vendor identities, physical positions, and the per-endstation configuration are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build`, `Blocks-go-live`, `Nice-to-have`.

### Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The two undulator periods and gap / phase ranges (soft EPU60, tender U42). The devices (`SR:C07-ID:G1A{SST1:1}`, `{SST2:1}`) are confirmed from the sst-base energy classes; soft range about 71-2250 eV. | Two insertion devices, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs. Only the shutters (`XF:07ID-PPS{Sh:FE}`, `XF:07IDA-PPS{PSh:n}`) are in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | The branch-to-hutch mapping and the physical hutch names / numbering (not in source): which endstations (RSoXS, NEXAFS on the soft SST-1 branch; HAXPES on the tender SST-2 branch; plus UCAL, VPPEM) sit in which enclosures? The PV zone numbers (07ID1 / 07ID2 / 07ID6) do not map one-to-one to a branch. | An optics hutch plus a soft (SST-1) and a tender (SST-2) experiment enclosure. | The Enclosure set and roles. |

### Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | The soft PGM grating set and the tender DCM crystal cut and ranges. Both monochromators (`Mono:PGM1`, `Mono:DCM1`) are in source. | One GratingMonochromator and one Monochromator Asset, settings blank. | The Monochromator settings. |
| ENERGY-1 | Nice-to-have | Is energy scanned as the measurement (NEXAFS absorption sweeps the soft PGM across an edge), warranting the energy-scan Capability the catalog anticipates? | NEXAFS mapped to deferred Capabilities; energy-scan deferred (the BMM question). | The spectroscopy Capability decision. |

### Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ARPES-1 | Blocks-go-live | The HAXPES Scienta SES hemispherical analyzer model, lens modes, and pass-energy / kinetic-energy controls. | An `ElectronAnalyzer` Asset (catalog Family, graduated at this 2nd sighting after ESM) presenting the Detector Role. | The analyzer model. |
| DET-1 | Blocks-go-live | Which detectors are live per endstation: the RSoXS Greateyes WAXS CCD (a second SAXS-arm CCD is commented out), the HAXPES analyzer, the NEXAFS microcalorimeter and drain-current / partial-electron-yield channels. | The WAXS CCD, the analyzer, and the microcalorimeter modelled; the SAXS arm excluded. | The detector roster per endstation. |
| TEMP-1 | Nice-to-have | Which sample-environment thermal units are live per endstation (the Lakeshore controllers). | One `TemperatureController` Asset; the others noted. | The sample-environment Assets. |
| DIAG-1 | Nice-to-have | The flux-channel map (the I0 mesh / diode, the drain-current and ion-chamber SR570 channels); the `PositionMonitor` Family is settled (graduated catalog Family presenting `Sensor`), so only the per-Asset channel map stays open. | Read-only flux (`FluxMonitor`) and beam-position (graduated catalog `PositionMonitor`) probes; channel maps blank. | The FluxMonitor and PositionMonitor channel-map bindings. |
| INSITU-1 | Nice-to-have | The endstations and in-situ accessories deferred at this design phase: the NEXAFS endstation detail (drain-current / partial-electron-yield channels), the UCAL microcalorimeter ADR cryostat, the VPPEM microscope, the HAXPES flood gun and source-measure unit, and the RSoXS syringe pump. None fits an existing family cleanly. How does CORA model these? | Deferred; the main RSoXS / HAXPES / NEXAFS-TES legs are modelled; the rest are named here. | The deferred endstation and in-situ Assets. |

### Controls and technique scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, IPs across the branches. | Families bound (MotionController), specifics blank. | The MotionController Models. |
| TECH-1 | Blocks-go-live | Do the soft-scattering (RSoXS), absorption (NEXAFS), and photoemission (HAXPES) Capabilities enter CORA's catalog, or stay deferred? This is the same owner-scope decision the other scattering / spectroscopy / photoemission beamlines opened. | Capabilities deferred (rendered unlinked), no Practice recorded. | The technique Capability scope. |
