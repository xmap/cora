# Model

*The developer's by-kind index: where each CORA aggregate's CDI content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at CDI |
| --- | --- |
| Asset (Equipment) | [Inventory](inventory.md#the-asset-tree) (in this zone) |
| Computed / virtual axes (Equipment) | [Inventory](inventory.md#the-asset-tree) (`EnergyAxis`) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](equipment/index.md) (9-ID-A optics, 9-ID-C endstation) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring CHX, HXN, and the other reverse-engineered deployments. Left out on purpose:

- **No new Family.** CDI is a reuse-and-reinforce deployment: the area detectors and diagnostic cameras bind `Camera`, the foil intensity monitor `FluxMonitor`, the pre-mirrors and the KB nanofocus pair `Mirror`, both monochromators `Monochromator`, the sample stack `Goniometer`, the white-beam / branch / conditioning slits `Slit`, the attenuator foils `Filter`, the undulator `InsertionDevice`, the master energy a `PseudoAxis`, and the endstation towers `LinearStage`. Nothing graduates and the catalog is unchanged.
- **The held loose families.** The `BeamPositionMonitor` (shared with 4-ID, 8-ID, ISS, FMX) binds a loose family that stays loose, matching the catalog note that position monitors stay loose; it is recorded in the promotion-review register. The `StorageRing` current readback is a loose supply observation (machine state), never an Asset Family.
- **No new Capability or Method.** Ptychography reuses the pending `ptychography` Method Diamond i13-1 opened (the fleet's first coherent diffractive imaging); forward and Bragg CDI are the single-shot variants of the same deferred coherent-imaging cohort, not separately coined (`TECH-1`). CDI reinforces the Method without coining anything and records no Practice until the scope lands. The phase retrieval and ptychographic reconstruction are `ComputePort` work, not a Method.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms. The [2-BM Model page](../2-bm/model.md) shows the shape a fully-modelled deployment carries.
