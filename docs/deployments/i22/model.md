# Model

*The developer's by-kind index: where each CORA aggregate's I22 content lives, why it earns no catalog kinds and carries real EPICS handles, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I22 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What is deliberately not here yet

- **New catalog Families, Capabilities, and Methods.** I22 does not earn new catalog kinds in this scaffold. An adversarial new-kind review refuted all five proposed device anatomies as catalog Families on the strength of I22 alone; four (`TemperatureController`, `FluxMonitor`, `Transfocator`, `FlowController`) have since graduated to the catalog once a rule-of-three across deployments settled them, and the remaining one (`StorageRing`) is still carried as a loose family with a tracking question. The new scattering Capabilities are carried as pending Practices. A kind is added to the catalog only when a confirmed device or technique and the naming review settle it. This follows the "pilots earn the abstractions" rule, and I22 is explicitly not a pilot (SCOPE-1).
- **Integration scenarios.** No `test_i22_*.py` registers I22 Assets into the event store. Hard-registering a design-phase, off-roadmap beamline would commit speculative structure.
- **Vendor Models.** No catalog Model is bound. The hardware dodal names (Dectris, AVT, Watson-Marlow, Linkam) is recorded in the descriptor notes, not bound.
- **Operations and experiment views.** A runbook and live experiment view for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies.** The two detectors are left as plain `Camera` devices. Whether the SAXS detector composes an Assembly with its beamstops and base is deferred (GROUP-1).

What is genuinely new here versus the other scaffolds: the descriptor carries real EPICS control handles (from dodal), and the open questions are about the layers dodal cannot reach (calibration, safety, technique), not about the PVs.
