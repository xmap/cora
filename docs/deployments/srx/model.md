# Model

*The developer's by-kind index: where each CORA aggregate's SRX content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SRX |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (5-ID-A optics, 5-ID-D nano endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring HXN, BMM, and the Diamond beamlines. Left out on purpose:

- **No new Family or Capability.** SRX is the reuse-and-reinforce deployment: every device binds an existing catalog Family (`EnergyDispersiveSpectrometer`, `FluxMonitor`, `TemperatureController` among the recently-graduated ones), and the techniques compose from existing Capabilities. The deferred `scanning` (HXN) and `energy_scan` (BMM) Capabilities are reinforced, not coined, here.
- **The micro endstation.** SRX has a micro endstation (05IDB) alongside the nano (KB) endstation modelled here; it is noted and deferred (ENDSTATION-1), the way 32-ID modelled one of several instruments.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
