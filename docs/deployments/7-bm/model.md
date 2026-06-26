# Model

*The developer's index into where 7-BM content lives. Design-phase.*

7-BM is a documentation-and-descriptor scaffold today: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/7-bm/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/7-bm/beamline.yaml) | the device walk; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface, shared with 2-BM; 7-BM is added to its beamlines and Sector 7, with 7-BM Practices, Supplies, Clearances, and Cautions carried pending |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | 7-BM reuses existing Families including `EnergyDispersiveSpectrometer` (graduated once 2-ID and 7-BM shared it) and the graduated `FlowController` Family (presents the Regulator Role, the settable-actuator sibling of TemperatureController, earned across i22 / 7-BM / LIX / XFP); it carries two loose design-intent families (`Chopper`, `Photodiode`) that render as plain text until earned |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | tomography reuses the existing Methods; the high-speed-imaging, radiography, and EDD Methods are deferred until the techniques enter scope (TECH-1) |
| Catalog Model | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none bound; the 7-BM docs name vendors but no part is procured into the catalog |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 7-BM Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What is deliberately not here yet

- **New catalog Families and Methods.** 7-BM does not earn new catalog kinds in this scaffold. The genuinely-new device anatomies are carried as loose families with a tracking question; the new techniques are carried as pending Methods. They are added to the catalog only when a confirmed device or technique and the naming review settle them. This follows the "pilots earn the abstractions" rule: a beamline that is not yet onboarded does not get to mint cross-facility vocabulary.
- **Integration scenarios.** No `test_7bm_*.py` registers 7-BM Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, partly-documented beamline would commit speculative structure. It lands when the techniques enter the pilot scope and the team approves.
- **Vendor Models.** No catalog Model is bound. The vendors named in the docs (Photron, Sierra, Kaeser, IDT, Rigaku) are recorded in the descriptor notes, not bound, because no part is procured into the catalog.
- **Operations and experiment views.** A runbook and live experiment view for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies.** The tomography detector is left as plain devices (scintillator plus camera). It could later compose the cross-facility `Microscope` Assembly that 2-BM and TomoWISE use, once a scenario registers it.

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
