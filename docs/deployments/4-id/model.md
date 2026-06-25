# Model

*The developer's index into where 4-ID POLAR content lives, the loose-Family graduation plan, and the record of what is deliberately deferred. First cut.*

4-ID POLAR is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's instrument repo: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/4-id/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/4-id/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface, shared with 2-BM; `4-ID` added to its beamline list, with POLAR Practices |
| Extraction provenance | [`research/aps-reverse-engineering/extracted/polar-bits/`](https://github.com/xmap/cora/tree/main/research/aps-reverse-engineering) | the facts report and candidate the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | no new Family added; POLAR reuses existing Families and binds new device classes to loose Family strings (see below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the diffraction / magnetism / polarization Methods are not yet coined (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 4-ID Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## Loose-Family graduation

POLAR introduced eight device classes CORA had not earned into the catalog. Graduation needs two or more independent CORA deployments AND a settled abstraction. The 8-ID XPCS deployment adds the second independent beamline for `TemperatureController`, `Transfocator`, and `BeamPositionMonitor`, but `main` deliberately holds all three loose pending cross-facility abstraction reviews opened by the parallel Diamond deployments (settable-actuator `ENV-1`; CRL catalog home `CRL-1`; sensor fold-vs-promote `DIAG-1` / `FLUX-1`), so they stay loose here too, allowlisted and recorded in the promotion register. The `Diffractometer` is the one that landed: as the `Assembly(Diffractometer)` blueprint (4-ID + 8-ID), which composes the catalog `Goniometer` Family, with an 8-ID Fixture scenario. The remaining four (`PhaseRetarder`, `PolarizationAnalyzer`, `Magnet`, `Laser`) are single-beamline loose. All names were cleared by the naming-r3 review during the catalog-graduation pass.

| Loose Family | Presents (when graduated) | Status |
| --- | --- | --- |
| `TemperatureController` | Controller | HELD loose: 2nd beamline (LakeShore + QNW) but abstraction open (ENV-1) |
| `Transfocator` | Positioner | HELD loose: 2nd beamline (two CRL transfocators) but no catalog home yet (CRL-1) |
| `BeamPositionMonitor` | Sensor | HELD loose: 2nd beamline (Sydor + TetrAMM) but fold-vs-promote open (DIAG-1/FLUX-1) |
| `PhaseRetarder` | Positioner | loose: a second polarization beamline, or POLAR registration |
| `PolarizationAnalyzer` | Positioner | loose: a second polarization beamline |
| `Magnet` | confirm (Positioner or Sensor) | loose: needs a second magnetism beamline (8-ID has no sample magnet) |
| `Laser` | confirm | loose: a second deployment, or the SAMPLE-1 model-versus-hazard decision |
| `Diffractometer` | Positioner (Assembly) | LANDED as `Assembly(Diffractometer)` in the catalog, composing `Goniometer` (4-ID + 8-ID); 8-ID Fixture scenario landed, the 4-ID Fixture is the follow-on |

## Deliberately not here yet

These are the parts of 4-ID this cut leaves out on purpose. Each is a CORA scope decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](questions.md).

- **The 4-ID Diffractometer Fixture.** The `Assembly(Diffractometer)` is now in the catalog (composing the `Goniometer` Family) and materialized by the 8-ID Fixture scenario (see the [8-ID model page](../8-id/model.md#the-diffractometer-assembly-landed)). 4-ID's two Huber diffractometers (the Eulerian cradle and the high-pressure diffractometer) are still modelled here as plain devices with their circle axis maps; decomposing them into a `Goniometer` Asset (the sample circles plus centring) plus any detector-arm `RotaryStage` circles and binding a 4-ID Fixture is the follow-on, gated on the circle-role confirmation (`DIFF-1`). The Assembly is the shared blueprint; the Fixture is per-beamline.

- **The Raman station.** `4-ID-Raman` is out of this cut because its device config did not extract (a symlink that did not resolve in the source clone). Its devices and whether it is a fifth enclosure are `TOPO-2`; it is a world-fact gap, tracked on [Open questions](questions.md), not a scope decision.

- **The 6-ID-B fork and the psic diffractometer.** A second instrument repo, `BCDA-APS/6idb-bits`, is a fork of `polar-bits`: its devices are almost entirely the same `4id*` PVs, with a grafted 6-ID-B endstation (a `psic` six-circle diffractometer at `6idb1:`, a CRL at `6idbSoft:TRANS:`). It is not an independent beamline, so it was used only as a second source to enrich this 4-ID descriptor (the `emag` magnet axes, the Euler diffractometer chi/phi circles), not to build a 6-ID-B deployment. The genuine 6-ID-B endstation (the `psic` diffractometer) is a future deployment, not modelled here. This fork also means the fleet recurrence report counts `polar-bits` and `6idb-bits` as two beamlines when they are one physical beamline, so the `Magnet` / `TemperatureController` / `Diffractometer` graduation signal rests on a single beamline; see [`catalog-graduation-decisions.md`](https://github.com/xmap/cora/blob/main/research/aps-reverse-engineering/catalog-graduation-decisions.md).

- **The diffraction / magnetism / polarization Methods.** Whether these techniques enter CORA's catalog (which has been all-imaging) is an owner decision. The Practices are registered pending and render unlinked; no Method is coined until the technique enters the pilot scope (`TECH-1`).

- **Peripheral electronics.** The preamplifiers, lock-in amplifier, LabJacks, and high-pressure-cell controllers are present in the beamline config but not modelled as Assets in this cut (`SAMPLE-2`). They join if they prove to be beamline equipment CORA should track.

- **Integration scenarios and vendor Models.** No `test_4id_*.py` registers 4-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real; hard-registering a first-cut, confirm-pending beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
