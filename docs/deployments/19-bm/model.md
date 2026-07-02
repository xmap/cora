# Model

*The developer's by-kind index: where each CORA aggregate's 19-BM content lives, a second BM beamline that reuses the families 2-BM established and coins none of its own, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 19-BM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What is deliberately not here yet

- **Integration scenarios.** No `test_19bm_*.py` registers 19-BM Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** No catalog Model is bound: the sample stages, the detector hardware, and the robotic changer are all procured after the FDR and are carried as [open questions](questions.md), not bindings.
- **New catalog Families.** 19-BM coins none of its own. The two passive families it pushed past the rule-of-three threshold (`Window`, with two more Be windows; `Collimator`, with two more Pb collimators) have since been promoted to catalog Families under the passive beam-path tier; 19-BM's windows and collimators now bind them.
- **The autonomy build.** The `RunSupervisor` enablement and the missing run-start capability that 19-BM's autonomous operation needs are real CORA work, not documentation; see [Governance](governance.md). They land as their own slices.
- **The robotic sample changer.** Deferred behind its separate safety review (ROBOT-1).
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).
