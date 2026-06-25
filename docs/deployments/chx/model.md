# Model

*The developer's by-kind index: where each CORA aggregate's CHX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at CHX |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (11-ID-A optics, 11-ID-B endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring HXN, BMM, SRX, and the Diamond beamlines. Left out on purpose:

- **No new Family.** CHX is a reuse-and-reinforce deployment: the area detectors bind `Camera`, the flux counter `FluxMonitor`, the thermal stage `TemperatureController`, the fluorescence detector `EnergyDispersiveSpectrometer`, the beamstop `BeamStop`, the mirrors `Mirror`, both monochromators `Monochromator`, and the coherence-defining and guard slits `Slit`.
- **The held loose families.** Two devices bind loose families that other deployments also use and that are held for gate-review: the compound-refractive-lens `Transfocator` (4-ID, 8-ID, 9-ID, i22) and the `BeamPositionMonitor` (4-ID, 8-ID, 9-ID). Both stay loose. For the `Transfocator` the hold is not about the count (which is long past any rule-of-three) but about the abstraction, whether the catalog home is a CRL-specific Family or a more general focusing optic, which is `CRL-1`'s for gate-review to settle. CHX sharpens that question: it carries a **second** kind of refractive focusing optic, the endstation kinoform lenses (`k1`/`k2`), distinct from the FOE transfocator, so the transfocator is not the only focusing optic and the abstraction has to cover both. The kinoform is named in `CRL-1` and not separately modelled (modelling it would coin a new loose family at a single sighting). Both held families are recorded in the promotion-review register.
- **No new Capability or Method.** XPCS and small-angle scattering sit on the deferred `xpcs` / `small_angle_scattering` Methods 8-ID left pending (`TECH-1`); CHX reinforces both without coining either, and records no Practice until they land. The correlation analysis is `ComputePort` work, not a Method.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
