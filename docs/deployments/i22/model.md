# Model

*The developer's index into where I22 content lives. Design-phase.*

I22 is a documentation-and-descriptor scaffold: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives.

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/i22/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/i22/beamline.yaml) | the device walk, with the dodal-derived EPICS PV handles; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/diamond/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/diamond/site.yaml) | the Diamond facility surface, the third Site; I22 practices, supplies, and the PSS clearance carried pending |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | no new Family added by I22 itself; it reuses existing Families and carries the loose design-intent family (`StorageRing`). `TemperatureController` (the Linkam) was carried loose here too but has since graduated to a catalog Family (presenting the `Regulator` Role) once it reached the rule-of-three at i11; `FluxMonitor` (the I0 / It ion chambers) likewise graduated, presenting the Sensor Role, on the i22/i03/i15-1 rule-of-three; `Transfocator` (the CRL focusing optic here) likewise graduated as a catalog Family in its own right, distinct from `Mirror` / `ZonePlate` / `Condenser`; `FlowController` (the peristaltic pump here) likewise graduated as a catalog Family presenting the `Regulator` Role, the `TemperatureController` sibling, earned across i22 / 7-BM / LIX / XFP |
| Catalog Capability / Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the SAXS / WAXS scattering Capabilities are new vocabulary deferred until the technique enters scope (TECH-1) |
| Catalog Model | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none bound; dodal names hardware but no part is procured into the catalog |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers I22 Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## What is deliberately not here yet

- **New catalog Families, Capabilities, and Methods.** I22 does not earn new catalog kinds in this scaffold. An adversarial new-kind review refuted all five proposed device anatomies as catalog Families on the strength of I22 alone; four (`TemperatureController`, `FluxMonitor`, `Transfocator`, `FlowController`) have since graduated to the catalog once a rule-of-three across deployments settled them, and the remaining one (`StorageRing`) is still carried as a loose family with a tracking question. The new scattering Capabilities are carried as pending Practices. A kind is added to the catalog only when a confirmed device or technique and the naming review settle it. This follows the "pilots earn the abstractions" rule, and I22 is explicitly not a pilot (SCOPE-1).
- **Integration scenarios.** No `test_i22_*.py` registers I22 Assets into the event store. Hard-registering a design-phase, off-roadmap beamline would commit speculative structure.
- **Vendor Models.** No catalog Model is bound. The hardware dodal names (Dectris, AVT, Watson-Marlow, Linkam) is recorded in the descriptor notes, not bound.
- **Operations and experiment views.** A runbook and live experiment view for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies.** The two detectors are left as plain `Camera` devices. Whether the SAXS detector composes an Assembly with its beamstops and base is deferred (GROUP-1).

What is genuinely new here versus the other scaffolds: the descriptor carries real EPICS control handles (from dodal), and the open questions are about the layers dodal cannot reach (calibration, safety, technique), not about the PVs. The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
