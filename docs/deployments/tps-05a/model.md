# Model

*The developer's by-kind index: where each CORA aggregate's TPS 05A content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at TPS 05A |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (TPS-05A-OH optics, TPS-05A-EH experiment) |
| Facility (Federation); Zone, Conduit, Policy (Trust); Actor (Access) | [NSRRC Site](../nsrrc/index.md), [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other reverse-engineered beamlines and especially its sibling [TPS 07A](../tps-07a/model.md). Left out on purpose:

- **No new Family.** TPS 05A reuses every Family TPS 07A binds: the graduated `Goniometer` for the MD3, `Camera` for the EIGER2 / OAV, `Monochromator`, `Filter`, `BeamStop`, `Shutter`, `Mirror`, `TemperatureController`, `LinearStage` / `MotionController`, plus the loose `StorageRing` and `PositionMonitor`. The only device-level difference from 07A is the EIGER2 size (9M vs 16M), a per-Asset fact.
- **No new Site, principals, or seam.** The NSRRC Site, its Access principals, and the Blu-Ice/DCSS-over-EPICS seam were all created by 07A; 05A reuses them unchanged. This is the deployment's whole point: demonstrating that the Site, the device-library, and the seam generalize across the MX cluster.
- **The ISARA robot as a Procedure.** Autonomous sample exchange is a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i24 / 07A / MX3 shape.
- **The frame egress and any mesh-scan compute.** The EIGER2 frame stream is a `TransferPort` leg into the Dataset of record; spot-scoring / indexing is `ComputePort` work, an Observe / Compute leg off the control seam (DET-1).
- **No new Capability or Method.** Rotation MX reuses the pending i03 Methods, recorded as the `TPS05A_*` Practices on the Site; 05A reinforces the case at a further MX deployment without coining any (TECH-1).
- **A verified PV namespace.** Unlike 07A (whose `07a:` / `07a-ES:` namespace was read from its control tree), 05A has no dedicated public tree, so its `05a:` / `05a-ES:` namespace is inferred by cluster convention and carried pending (PV-1), the fleet's most conservative PV posture.
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.
