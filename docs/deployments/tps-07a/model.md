# Model

*The developer's by-kind index: where each CORA aggregate's TPS 07A content lives. It hosts no content of its own. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC
[modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at TPS 07A |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (EnergyAxis) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [The beamline](index.md#enclosures) (TPS-07A-OH optics, TPS-07A-EH experiment) |
| Facility (Federation); Zone, Conduit, Policy (Trust); Actor (Access) | [NSRRC Site](../nsrrc/index.md), [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

This is a design-phase scaffold (descriptor + docs), mirroring the other reverse-engineered beamlines. Left out on purpose:

- **No new Family.** TPS 07A's novelty is the Site and the seam, not its devices: the MD3 goniometer binds the graduated `Goniometer` (the i03 / MX3 MX precedent), the detectors `Camera`, the DCM `Monochromator`, the cryostream `TemperatureController`, the attenuator `Filter`, the beamstop `BeamStop`, the shutters `Shutter`, the mirrors `Mirror`, the stages `LinearStage` / `MotionController`.
- **The reused loose families.** `StorageRing` (the ring-current monitor) and `BeamPositionMonitor` (the beam-position diagnostic) are bound loose, each already allowlisted from earlier deployments; TPS 07A coins no new loose family.
- **The DCSS-over-EPICS seam.** TPS 07A drives a single EPICS floor with a Blu-Ice/DCSS orchestration layer above it, reached through an EPICS Device Handler Server. This is modelled as `ControlPort` actuation over EPICS plus a CORA EdgeConductor that replaces the DCSS orchestration, not new aggregates; it is the 2-BM TomoScan seam, not the MX3 multi-transport seam. See [Controls](controls.md). The MD3 axis PV records and the DCSS-vs-MXCuBE confirmation are GONIO-1.
- **The ISARA robot as a Procedure.** Autonomous sample exchange is a deferred Procedure over the spine threaded through `Subject` custody (ROBOT-1), reusing the i03 / i24 / MX3 shape, not a new device family.
- **The frame egress and mesh-scan compute.** The EIGER2 ZMQ / ASAP::O frame stream is a `TransferPort` leg into the Dataset of record; the Dozor spot-scoring and CHiMP crystal-detection are `ComputePort` work, an Observe / Compute leg off the control seam, not beamline Methods or Assets (DET-1).
- **No new Capability or Method.** Rotation MX reuses the pending i03 Methods (`mx_data_collection` / `grid_scan` / `sample_exchange`), recorded as Practices on the Site; TPS 07A reinforces the case at a further MX facility without coining any (TECH-1).
- **Operations and experiment views, integration scenarios, vendor Models.** A runbook and registered Assets for a beamline CORA does not yet drive would be invention; they land when the design firms and the team confirms.
