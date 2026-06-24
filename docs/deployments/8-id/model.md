# Model

*The developer's index into where 8-ID content lives, the catalog graduation this deployment earns, and the record of what is deliberately deferred. First cut.*

8-ID is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's instrument repo: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/8-id/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/8-id/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface; `8-ID` added to its beamline list, with XPCS Practices |
| Extraction provenance | [`research/aps-reverse-engineering/extracted/8id-bits/`](https://github.com/xmap/cora/tree/main/research/aps-reverse-engineering) | the facts report and candidate the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | three Families graduate with this deployment (below); the rest of 8-ID's new classes stay loose |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; XPCS / scattering Methods are not yet coined (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 8-ID Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## Catalog graduation

8-ID is the second independent APS beamline (after 4-ID POLAR) to use three device classes 4-ID introduced as loose Families. Two independent beamlines is the graduation trigger, so they are earned into `catalog/catalog.yaml` with this deployment. Their names were cleared by the naming-r3 review during the [catalog-graduation pass](https://github.com/xmap/cora/blob/main/research/aps-reverse-engineering/catalog-graduation-decisions.md).

| Family | Presents | At 4-ID | At 8-ID |
| --- | --- | --- | --- |
| `TemperatureController` | Controller | LakeShore 336 / 340 | LakeShore 336 (8-ID-E) + Quantum Northwest holders (8-ID-I) |
| `Transfocator` | Positioner | CRL transfocator | two CRL transfocators (8-ID-D) |
| `BeamPositionMonitor` | Sensor | XBPM / Sydor / TetrAMM (and loose at 2-BM) | Sydor (8-ID-E) + TetrAMM (8-ID-I) |

`Magnet` and `Preamplifier` do NOT graduate: they rest on a single physical beamline (4-ID), since `6idb-bits` is a 4-ID fork (see the [4-ID model page](../4-id/model.md#deliberately-not-here-yet)). They wait for a genuinely independent beamline that uses them.

## Deliberately not here yet

- **The Diffractometer Assembly.** 4-ID and 8-ID both carry diffractometers, modelled as plain devices with their circle axis maps. The 8-ID six-circle Huber (mu, eta, chi, phi, nu, delta) plus 4-ID's Eulerian and high-pressure circles confirm the reusable shape: an `Assembly(Diffractometer)` presenting the Positioner Role, mirroring the 2-BM `Microscope` Assembly, with a `sample_circles` slot bound to `RotaryStage` at cardinality `OneOrMore` (to span the four-circle and six-circle geometries), a `sample_table` slot bound to `LinearStage`, and a `reciprocal_space` slot bound to the existing `PseudoAxis` Family (its `partition_rule` resolving the hklpy2 inverse kinematics). All slot families exist, so no new Family is needed. It is deferred from the catalog until a scenario registers a Fixture (the design-phase convention defers Assemblies to Fixture registration); the circle-role confirmation is `DIFF-1`.

- **The UR5 robotic sample changer.** `RobocartUR5` is a user-brought robotic arm; CORA has no sample-changer shape (the same gap the 32-ID projection-microscope changer raised). It is not modelled (`SAMPLE-2`).

- **The softGlue timing graph.** The XPCS exposure timing runs on a softGlueZynq FPGA fabric (`8idMZ1:`); it is modelled coarsely as one `TimingController`, not as its full signal graph (`XPCS-3`).

- **The XPCS / scattering Methods.** Whether XPCS and small-angle scattering enter CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).

- **Integration scenarios and vendor Models.** No `test_8id_*.py` registers 8-ID Assets, and no vendor Models are bound. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
