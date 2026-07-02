# Model

*The developer's by-kind index: where each CORA aggregate's TomoWISE content lives, the cross-facility `Microscope` / `Optics` Assemblies it reuses with 2-BM, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at TomoWISE |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What is deliberately not here yet

- **Integration scenarios.** No `test_tomowise_*.py` registers TomoWISE Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** Only one catalog Model is bound: `optique_peter_micrx080` on the microscope Housings (reused from 2-BM, pending confirmation, DET-2). The remaining "(target)" models in the TDR are [open questions](questions.md), not bindings, because part numbers are not yet procured.
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies (done).** The two microscopes now compose the cross-facility `Microscope` / `Optics` Assemblies that 2-BM uses (Housing-anchored: turret + objectives + selector over a scintillator), rather than a loose family. The catalog assembly was generalized (`camera` and `propagation_distance` made `ZeroOrOne`) so TomoWISE can share its four cameras and the one gantry propagation rail across both microscopes. This also removed the prior name collision between the loose `Microscope` family and the catalog `Microscope` Assembly. What remains deferred is the integration scenario that registers the Fixture (slot -> Asset bindings) and a standalone fixture page; both wait until the design firms.
