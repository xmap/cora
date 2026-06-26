# Model

*The developer's by-kind index: where each CORA aggregate's ISS content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ISS |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (8-ID-A optics, 8-ID-B experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What this deployment graduates

ISS earns one catalog change: the **`EmissionSpectrometer`** Family GRADUATED. LCLS-MFX introduced it for its von Hamos six-crystal XES spectrometer and carried it loose at n=1 (SPEC-1, with MAX IV Balder noted as a near-sighting). ISS's Johann and von Hamos crystal emission spectrometers are the **second** sighting, earning the rule-of-three the way `GratingMonochromator` (CSX), `Manipulator` (ESM), and `ElectronAnalyzer` (SST) graduated at their second sighting. The abstraction is settled (a crystal-analyzer emission spectrometer composing analyzer crystals and a 2D detector along a Rowland-circle or wavelength-dispersive geometry is a distinct, recurring device, not a point Sensor and not a beam-conditioning Monochromator), so it GRADUATED into the catalog (SPEC-1); LCLS-MFX's references were swept loose to graduated alongside. It stays distinct from the still-loose `EnergyAnalyzer` (the IXS diced-crystal energy-selecting analyzer, ANALYZER-1) and `SpectrometerArm` (the SIX soft X-ray grating dispersive RIXS arm, RIXS-1), which graduate nothing until their own rule-of-three.

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new loose Family.** ISS is otherwise a reuse deployment: the trajectory and high-resolution monochromators bind `Monochromator`, the mirrors `Mirror`, the filter box `Filter`, the slits `Slit`, the shutters `Shutter`, the energy axis `PseudoAxis`, the sample stage `LinearStage`, the goniometer `Goniometer`, the reference foil wheel `RotaryStage`, the thermal stage `TemperatureController`, the ion chambers `FluxMonitor`, the Xspress3 SDD `EnergyDispersiveSpectrometer`, the Pilatus `Camera`, the trajectory controller `MotionController`, the analog pizza box `TimingController`.
- **The held `BeamPositionMonitor`.** The beam-position diagnostics bind the loose `BeamPositionMonitor` family that several deployments use; it stays loose pending the sensor fold-vs-promote decision (`DIAG-1`).
- **No new Capability or Method.** EXAFS leans on the deferred `energy_scan` Capability (ENERGY-1, the BMM question; ISS strengthens it as a further consumer without forcing it); XES / HERFD reuse the `xas_spectroscopy` Method LCLS-MFX left pending, the second consumer (TECH-1). ISS records that one pending Practice and coins nothing. The per-technique reduction is `ComputePort` work.
- **The deferred in-situ environment.** The ion-chamber fill-gas mass-flow controllers (He / N2) and the broader in-situ sample environment fit no catalog family cleanly (the loose FlowController) and are named in a question (`ENV-1`) rather than modelled at this design phase. ISS models the main transmission / fluorescence / emission legs as the representative configuration.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
