# Model

*The developer's index into where TomoWISE content lives. Design-phase.*

TomoWISE is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/tomowise/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/tomowise/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/maxiv/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/maxiv/site.yaml) | the MAX IV facility surface |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | `InsertionDevice` added for the two sources; `Mask` promoted to a shared Family (front-end masks, now shared with 2-BM); other devices reuse existing Families |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers TomoWISE Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What is deliberately not here yet

- **Integration scenarios.** No `test_tomowise_*.py` registers TomoWISE Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** No catalog Models are bound: part numbers are not yet procured. The "(target)" models in the TDR are [open questions](questions.md), not bindings.
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies (reuse opportunity).** The two microscopes bind a loose `Microscope` family and separate `Camera` devices, rather than composing the catalog `Microscope` / `Optics` Assemblies that 2-BM already uses. The shape is identical (an optics relay plus camera and scintillator leaves, presenting the Detector Role), so composing those Assemblies is the clearest catalog-reuse opportunity, deferred until the detector optics and camera models firm (DET-1, DET-2). It would also remove a name collision: the loose `Microscope` family currently shares its name with the catalog `Microscope` Assembly.

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
