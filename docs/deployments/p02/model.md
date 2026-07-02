# Model

*The developer's by-kind index: where each CORA aggregate's P02 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P02 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What makes P02 new

P02 is an eighth beamline at an existing Site, and the fleet's high-energy diffraction beamline with two branches: P02.1 (powder / total scattering / PDF, ~60 keV) and P02.2 (extreme conditions, diamond-anvil cell). At the modelling level it brings the fleet's **second diamond-anvil-cell** endstation, binding the catalog `PressureCell` Family (graduated across 13-id and P02, with P02 the second consumer that earned it).

## No new families (the DAC reuses the 13-id PressureCell)

P02 coins no new Family. The monochromator binds `Monochromator`; the bendable HFM / VFM mirrors bind `Mirror`; the slits bind `Slit`; the sample stages bind `LinearStage`; the sample environment binds `TemperatureController`; the detectors bind `Camera` / `EnergyDispersiveSpectrometer`; the beam monitor binds `FluxMonitor`; and the diamond-anvil cell binds the catalog `PressureCell`.

Adding P02 as `PressureCell`'s second consumer crossed the rule-of-three promotion threshold, so the Family graduated to the catalog (earned across 13-id and P02, `PRESSURE-1`), following the path the POLAR-family `PhaseRetarder`, `PolarizationAnalyzer`, and `Magnet` siblings took to catalog Families. This is the graduation guard working as designed.

## The control plane

P02 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the bendable HFM / VFM mirrors (curvature / ellipticity attribute motors), the Pilatus 1M + PerkinElmer high-energy detectors, and the Anton-Paar / Lakeshore sample environment. The handles are read from P02's public OnlineXML registry and carried confirm (`CTRL-1`). P02 owns the OH1 high-heatload optics hutch shared with P03. The powder / total-scattering / high-pressure acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

## Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics detail (`OPT-1`).** The DCM crystal cut and the bendable-mirror coatings / focusing recipes are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The eh1a/b and eh2a/b banks carry no per-axis role; grouped as stage Assets.
- **The pressure-cell control (`PRESSURE-1`).** The diamond-anvil-cell membrane / gas-loading / pressure control is not in the registry; the `PressureCell` Family is the catalog one (graduated across 13-id and P02), with the membrane / load control detail pending.
- **The detector roster (`DET-1`).** The detector models, the powder-vs-PDF detector roles, and the P02.2 diffraction area detector are named, not fully bound.
- **The CH dummy stubs (`STUB-1`).** The CH1 / CH2 `tangomotor` dummies are test / placeholder devices, noted not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Methods (`TECH-1`).** Whether powder diffraction / total scattering enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p02_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
