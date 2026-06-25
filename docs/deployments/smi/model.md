# Model

*The developer's by-kind index: where each CORA aggregate's SMI content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SMI |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (12-ID-A optics, 12-ID-C experiment) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other NSLS-II and Diamond beamlines. Left out on purpose:

- **No new Family.** SMI is a reuse-and-reinforce deployment, the NSLS-II twin of Diamond i22 (SAXS / WAXS): the Pilatus detectors bind `Camera`, the flux monitor `FluxMonitor`, the sample environment `TemperatureController`, the fluorescence MCA `EnergyDispersiveSpectrometer`, the beamstops `BeamStop`, the mirrors `Mirror`, the monochromator `Monochromator`, the slits `Slit`, the attenuators `Filter`.
- **The held loose families.** Two devices bind loose families that other deployments also use and that are held for gate-review: the compound-refractive-lens `Transfocator` and the `BeamPositionMonitor`. SMI is the **sixth** Transfocator sighting (after 4-ID, 8-ID, 9-ID, i22, CHX); it stays loose because the hold is the abstraction (CRL-specific Family vs general focusing optic, `CRL-1`), not the count. The `BeamPositionMonitor` stays loose pending the sensor fold-vs-promote decision (`DIAG-1`). Both are recorded in the promotion-review register.
- **No new Capability or Method.** SAXS, WAXS, and GISAXS sit on the deferred scattering Capabilities Diamond i22 left pending (`TECH-1`); SMI reinforces them without coining any, and records no Practice. Grazing incidence is a sample-orientation variant, not a new Capability; simultaneous SAXS+WAXS is coordinated Runs, not a combined technique. The integration and reduction are `ComputePort` work.
- **The in-situ soft-matter cells.** The humidity cell (driven via Moxa analog IO, relative humidity computed in software) and the blade coater (a SmarAct stage plus a syringe pump) are SMI's specialty; they would each need their own family or Procedure decision, so they are deferred to a named question (`INSITU-1`) rather than modelled.
- **The in-vacuum WAXS / SAXS chamber.** The active sample chamber (pressure gauges, gate valves, turbo pump, pump / vent automation) is carried as the facility `Vacuum` Supply, the i22 precedent; whether the active chamber enters CORA as its own device is the named question `VAC-1`.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
