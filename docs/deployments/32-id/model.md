# Model

*The developer's by-kind index: where each CORA aggregate's 32-ID content lives, a TXM nano-tomography beamline whose optic classes graduated once FXI shared them, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 32-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Deliberately not here yet

These are the parts of 32-ID this scaffold leaves out on purpose. Each is a CORA scope decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](questions.md).

- **The canted branch structure.** The descriptor models one root Unit Asset and one optics train. Whether 32-ID becomes two root Assets (per branch) is held until `TOPO-1` resolves the canted geometry. The root identity and `facility_code` binding do not migrate when it does: a one-to-two split adds Component sub-trees, it does not re-home the root.

- **The white-to-mono beam-mode vocabulary.** Whether the mode switch is a new Capability or an extension of the existing `energy_change` Capability is decided when the mode is modelled, not now. The world-fact half (the switch structure and sequence) is `MODE-1`; the vocabulary half is this decision.

- **High-speed imaging and ultrafast diffraction (32-ID-B).** White-beam high-speed imaging reuses the imaging spine, but ultrafast white-beam diffraction (HSID) produces diffraction patterns, which have no precedent in CORA's all-imaging catalog. Whether diffraction is in CORA's scope is an owner decision; until it is made, neither instrument is modelled and no diffraction Capability is coined.

- **The additive-manufacturing laser rig (32-ID-B).** The powder-bed-fusion rig is a user-brought, actuated, non-X-ray energy source with no Family or Role precedent. The default is to model the class-4 laser as a `Clearance` hazard on an experiment, not as an Asset CORA drives. Whether CORA ever orchestrates the laser is an owner decision.

- **The projection microscope (PM).** The source docs for the PM are still "space holder", and its most distinctive parts (a helium-atmosphere KB system, a robotic sample-exchange arm) are the least documented. Modelling it now would be invention. The robotic sample changer in particular would force a sample-changer shape CORA does not have; it waits until the PM is documented and a real device list exists.

- **Integration scenarios and vendor Models.** No `test_32id_*.py` registers 32-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real, and hard-registering a design-phase, pre-APS-U-mixed beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
