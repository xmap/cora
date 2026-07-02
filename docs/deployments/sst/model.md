# Model

*The developer's by-kind index: where each CORA aggregate's SST content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SST |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (7-ID-A optics, SST-1 soft, SST-2 tender) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new Family.** SST is a reuse-and-reinforce deployment at Site scale: the soft PGM binds `GratingMonochromator` (graduated across SIX / CSX / ESM, a fourth sighting), the tender DCM `Monochromator`, the sample manipulators `Manipulator` (graduated by ESM, bound twice more here), the soft-scattering CCD and viewing cameras `Camera`, the microcalorimeter `EnergyDispersiveSpectrometer`, the flux channels `FluxMonitor`, the thermal stage `TemperatureController`, the mirrors `Mirror`, the slits `Slit`, the shutters `Shutter`, the beamstop `BeamStop`.
- **The `ElectronAnalyzer` graduation.** The HAXPES Scienta SES hemispherical analyzer binds the `ElectronAnalyzer` family NSLS-II ESM introduced. SST-HAXPES is the **second** sighting (the same Scienta SES type), so it earned the rule-of-three, the way `GratingMonochromator` (CSX) and `Manipulator` (ESM) graduated at their second sighting. The abstraction is settled (a hemispherical electron analyzer is a distinct, recurring photon-in / electron-out device, not a photon detector), so it GRADUATED into the catalog (`ARPES-1`); ESM's references were swept loose to graduated alongside.
- **The graduated `PositionMonitor`.** The beam-position diagnostics bind the graduated catalog `PositionMonitor` Family that several deployments share: it presents the `Sensor` Role, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux. The per-Asset beam-position channel map stays open (`DIAG-1`).
- **No new Capability or Method.** Soft-scattering, absorption, and photoemission sit on deferred / pending Capabilities (TECH-1, ENERGY-1, the ESM `angle_resolved_photoemission`); SST reinforces all three without coining any, and records no Practice. The per-technique reduction is `ComputePort` work.
- **The deferred endstations and in-situ accessories.** The NEXAFS endstation detail (drain-current / partial-electron-yield channels), the UCAL microcalorimeter ADR cryostat, the VPPEM microscope, the HAXPES flood gun and source-measure unit, and the RSoXS syringe pump are named in a question (`INSITU-1`); none fits an existing family cleanly, so they are deferred rather than modelled. SST models the RSoXS, HAXPES, and NEXAFS-microcalorimeter legs as the representative endstations, the way SRX modelled one of its endstations and 32-ID one of several instruments.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.
