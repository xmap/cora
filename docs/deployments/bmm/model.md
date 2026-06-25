# Model

*The developer's by-kind index: where each CORA aggregate's BMM content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at BMM |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (6-BM-A optics, 6-BM-B endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring HXN and the Diamond beamlines. Left out on purpose:

- **The `energy_scan` Capability.** BMM is the first real consumer of the energy-scan sweep the catalog already anticipates (pending in code), but a Capability is coined when a conduct-path consumes it, not at scaffold time (see [Techniques](techniques.md), ENERGY-1). This is the live earn-the-abstraction question BMM surfaces.
- **No new Family.** BMM reuses existing catalog Families: the ion chambers reuse `FluxMonitor` (graduated in #353), the fluorescence detector the catalog `EnergyDispersiveSpectrometer`, plus the loose `Screen` (held, FLAG-1) for the diagnostic screens. The sample wheel reuses `RotaryStage`; whether a sample-changer Family is earned across BMM and the Diamond robots is open (WHEEL-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
