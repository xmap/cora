# Model

*The developer's index into where TomoWISE content lives. Design-phase.*

TomoWISE is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/tomowise/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/tomowise/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/maxiv/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/maxiv/site.yaml) | the MAX IV facility surface |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | `InsertionDevice` added for the two sources; other devices reuse existing Families |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers TomoWISE Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What is deliberately not here yet

- **Integration scenarios.** No `test_tomowise_*.py` registers TomoWISE Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** No catalog Models are bound: part numbers are not yet procured. The "(target)" models in the TDR are [open questions](questions.md), not bindings.
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
