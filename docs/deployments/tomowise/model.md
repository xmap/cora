# Model

*The developer's index into where TomoWISE content lives. Design-phase.*

TomoWISE is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/tomowise/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/tomowise/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/maxiv/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/maxiv/site.yaml) | the MAX IV facility surface |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | `InsertionDevice` added for the two sources; `Mask` promoted to a shared Family (front-end masks, now shared with 2-BM); other devices reuse existing Families |
| Catalog Assembly | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | the two microscopes reuse the cross-facility `Microscope` / `Optics` Assemblies (shared with 2-BM); the `camera` and `propagation_distance` slots were generalized to `ZeroOrOne` so TomoWISE can share cameras + the gantry rail |
| Catalog Model | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | one model bound: `optique_peter_micrx080` (the 2-BM Optique Peter housing) on both microscope Housings, as the design-target candidate (DET-2) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers TomoWISE Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What is deliberately not here yet

- **Integration scenarios.** No `test_tomowise_*.py` registers TomoWISE Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** Only one catalog Model is bound: `optique_peter_micrx080` on the microscope Housings (reused from 2-BM, pending confirmation, DET-2). The remaining "(target)" models in the TDR are [open questions](questions.md), not bindings, because part numbers are not yet procured.
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies (done).** The two microscopes now compose the cross-facility `Microscope` / `Optics` Assemblies that 2-BM uses (Housing-anchored: turret + objectives + selector over a scintillator), rather than a loose family. The catalog assembly was generalized (`camera` and `propagation_distance` made `ZeroOrOne`) so TomoWISE can share its four cameras and the one gantry propagation rail across both microscopes. This also removed the prior name collision between the loose `Microscope` family and the catalog `Microscope` Assembly. What remains deferred is the integration scenario that registers the Fixture (slot -> Asset bindings) and a standalone fixture page; both wait until the design firms.

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
