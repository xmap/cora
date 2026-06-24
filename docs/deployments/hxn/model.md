# Model

*The developer's by-kind index: where each CORA aggregate's HXN content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at HXN |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (3-ID-A optics, 3-ID-C endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring 32-ID and 7-BM. Left out on purpose:

- **The scanning / ptychography Capabilities.** Coined when a real conduct-path consumes a raster, not at scaffold time (see [Techniques](techniques.md)). HXN is the first scanning-probe deployment, so this is the live earn-the-abstraction question, deferred deliberately.
- **`MultilayerLaueLens` catalog graduation.** A loose family at its first sighting (OPTIC-3); graduates at a second MLL beamline.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
