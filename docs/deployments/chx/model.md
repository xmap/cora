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

- **No new Family.** CHX is a reuse-and-reinforce deployment: the area detectors bind `Camera`, the flux counter `FluxMonitor`, the thermal stage `TemperatureController`, the fluorescence detector `EnergyDispersiveSpectrometer`, the beamstop `BeamStop`, the mirrors `Mirror`, both monochromators `Monochromator`, the coherence-defining and guard slits `Slit`, and the compound-refractive-lens focusing optic the graduated `Transfocator` catalog Family (a CRL focusing optic, also bound at 4-ID, 8-ID, 9-ID, i22). The `Transfocator` graduation settled the focusing-optic abstraction, so it is a normal catalog reuse like `Mirror`; what remains open for the transfocator is only its per-Asset lens material and count, tracked as `CRL-1`. CHX also carries a **second**, distinct kind of refractive focusing optic, the endstation kinoform lenses (`k1`/`k2`): a single profiled refractive lens, not a compound-lens transfocator, so it does not bind the `Transfocator` Family. It is named but not modelled as a device; whether a kinoform earns its own Family is a separate future question if a deployment binds one, not part of `CRL-1`.
- **The held loose family.** The `BeamPositionMonitor` (4-ID, 8-ID, 9-ID) binds a loose family that other deployments also use and that stays loose, matching the catalog note that position monitors stay loose; it is recorded in the promotion-review register.
- **No new Capability or Method.** XPCS and small-angle scattering sit on the deferred `xpcs` / `small_angle_scattering` Methods 8-ID left pending (`TECH-1`); CHX reinforces both without coining either, and records no Practice until they land. The correlation analysis is `ComputePort` work, not a Method.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
