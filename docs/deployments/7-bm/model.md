# Model

*The developer's by-kind index: where each CORA aggregate's 7-BM content lives, a flow / combustion deployment whose FlowController grounds the continuous-regulation gap, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 7-BM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## What is deliberately not here yet

- **New catalog Families and Methods.** 7-BM does not earn new catalog kinds in this scaffold. The genuinely-new device anatomies are carried as loose families with a tracking question; the new techniques are carried as pending Methods. They are added to the catalog only when a confirmed device or technique and the naming review settle them. This follows the "pilots earn the abstractions" rule: a beamline that is not yet onboarded does not get to mint cross-facility vocabulary.
- **Integration scenarios.** No `test_7bm_*.py` registers 7-BM Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, partly-documented beamline would commit speculative structure. It lands when the techniques enter the pilot scope and the team approves.
- **Vendor Models.** No catalog Model is bound. The vendors named in the docs (Photron, Sierra, Kaeser, IDT, Rigaku) are recorded in the descriptor notes, not bound, because no part is procured into the catalog.
- **Operations and experiment views.** A runbook and live experiment view for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies.** The tomography detector is left as plain devices (scintillator plus camera). It could later compose the cross-facility `Microscope` Assembly that 2-BM and TomoWISE use, once a scenario registers it.

- **The continuous-regulation runtime (the FlowController setpoint program).** The `FlowController` presents the earned `Regulator` Role and CORA commands its setpoint (a one-shot `SetpointStep`), but a continuous setpoint PROGRAM, a hold or ramp held during a Run while the scan acquires, has no runtime today: the Conductor walks a finite step list, and `SetpointStep` / `ControlPort.write` are one-shot. The regulation loop itself stays device/IOC-owned (the Sierra controller runs it); CORA's gap is expressing and observing the program, not hosting the loop. This is the deepest cross-facility architectural gap the audit named; 7-BM (flow/combustion) is its grounding case alongside i11 / XPD thermal. It is the continuous-regulation axis, deferred to a Stage-0 research note and a later gate-reviewed build, exactly as the event-stream axis was for XFEL/XPCS acquisition (FLOW-1).
