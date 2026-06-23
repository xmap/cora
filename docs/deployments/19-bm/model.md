# Model

*The developer's index into where 19-BM content lives. Design-phase.*

19-BM is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/19-bm/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/19-bm/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface, shared with 2-BM; 19-BM is added there as a second beamline |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added: 19-BM reuses the active families 2-BM established (`Slit`, `Filter`, `Shutter`, `RotaryStage`, `LinearStage`, `Table`, `Camera`, `Scintillator`, `TimingController`) |
| Catalog Assembly | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | the indirect detector reuses the cross-facility `Microscope` / `Optics` Assemblies (shared with 2-BM and TomoWISE) |
| Catalog Model | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none bound: 19-BM hardware is not yet procured |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 19-BM Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What is deliberately not here yet

- **Integration scenarios.** No `test_19bm_*.py` registers 19-BM Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** No catalog Model is bound: the sample stages, the detector hardware, and the robotic changer are all procured after the FDR and are carried as [open questions](questions.md), not bindings.
- **New catalog Families.** 19-BM needs none for first light. It does push two loose passive families past the rule-of-three threshold (`Window`, with two more Be windows; `Collimator`, with two more Pb collimators); whether either is promoted to a catalog Family is a separate decision tracked with the passive beam-path tier, not part of this scaffold.
- **The autonomy build.** The `RunSupervisor` enablement and the missing run-start capability that 19-BM's autonomous operation needs are real CORA work, not documentation; see [Governance](governance.md). They land as their own slices.
- **The robotic sample changer.** Deferred behind its separate safety review (ROBOT-1).
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
