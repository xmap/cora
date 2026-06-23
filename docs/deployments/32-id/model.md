# Model

*The developer's index into where 32-ID content lives, and the record of what is deliberately deferred. Design-phase.*

32-ID is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/32-id/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/32-id/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface, shared with 2-BM; `32-ID` added to its beamline list |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | no new Family added; the spine and TXM reuse existing Families, and the new device classes are bound to loose Family strings pending registration |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; TXM nano-tomography reuses `tomography` |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 32-ID Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## Deliberately not here yet

These are the parts of 32-ID this scaffold leaves out on purpose. Each is a CORA scope decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](questions.md).

- **The canted branch structure.** The descriptor models one root Unit Asset and one optics train. Whether 32-ID becomes two root Assets (per branch) is held until `TOPO-1` resolves the canted geometry. The root identity and `facility_code` binding do not migrate when it does: a one-to-two split adds Component sub-trees, it does not re-home the root.

- **The white-to-mono beam-mode vocabulary.** Whether the mode switch is a new Capability or an extension of the existing `energy_change` Capability is decided when the mode is modelled, not now. The world-fact half (the switch structure and sequence) is `MODE-1`; the vocabulary half is this decision.

- **High-speed imaging and ultrafast diffraction (32-ID-B).** White-beam high-speed imaging reuses the imaging spine, but ultrafast white-beam diffraction (HSID) produces diffraction patterns, which have no precedent in CORA's all-imaging catalog. Whether diffraction is in CORA's scope is an owner decision; until it is made, neither instrument is modelled and no diffraction Capability is coined.

- **The additive-manufacturing laser rig (32-ID-B).** The powder-bed-fusion rig is a user-brought, actuated, non-X-ray energy source with no Family or Role precedent. The default is to model the class-4 laser as a `Clearance` hazard on an experiment, not as an Asset CORA drives. Whether CORA ever orchestrates the laser is an owner decision.

- **The projection microscope (PM).** The source docs for the PM are still "space holder", and its most distinctive parts (a helium-atmosphere KB system, a robotic sample-exchange arm) are the least documented. Modelling it now would be invention. The robotic sample changer in particular would force a sample-changer shape CORA does not have; it waits until the PM is documented and a real device list exists.

- **TXM optic Families.** `Condenser`, `ZonePlate`, and `PhaseRing` are bound to loose Family strings, not coined as catalog Families. A design-phase scaffold registers no Assets, so nothing earns a Family yet; whether `ZonePlate` is one Family (condenser-vs-objective as a setting) or more is a naming-review decision taken when a confirmed TXM device registers.

- **Integration scenarios and vendor Models.** No `test_32id_*.py` registers 32-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real, and hard-registering a design-phase, pre-APS-U-mixed beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
