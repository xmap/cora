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

POLAR introduces eight device classes CORA has not earned into the catalog. They are bound to loose Family strings here, not graduated, because graduation needs two or more CORA deployments to reference a Family (the rule the passive beam-path tier followed). POLAR is the first deployment to reference most of them; each graduates in the commit that a second deployment (or, for `BeamPositionMonitor`, the existing 2-BM loose use) makes concrete. The names below were cleared by the naming-r3 review during the catalog-graduation pass, so the graduating commit carries no naming risk.

| Loose Family | Presents (when graduated) | Graduation trigger |
| --- | --- | --- |
| `BeamPositionMonitor` | Sensor | already loose at 2-BM; POLAR is the second reference, so this is the closest to graduating |
| `PhaseRetarder` | Positioner | a second polarization beamline, or POLAR registration |
| `PolarizationAnalyzer` | Positioner | a second polarization beamline |
| `Magnet` | confirm (Positioner or Sensor) | a second magnetism beamline |
| `TemperatureController` | Controller | a second deployment with a sample temperature controller |
| `Transfocator` | Positioner | a second deployment with a CRL transfocator |
| `Preamplifier` | Sensor | deferred (not modelled in this cut; SAMPLE-2) |
| `Laser` | confirm | a second deployment, or the SAMPLE-1 model-versus-hazard decision |

## Deliberately not here yet

These are the parts of 4-ID this cut leaves out on purpose. Each is a CORA scope decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](questions.md).

- **The Diffractometer Assembly.** The two Huber diffractometers are modelled as plain devices with their circle axis maps. The reusable shape is an `Assembly(Diffractometer)` presenting the Positioner Role, mirroring the 2-BM `Microscope` Assembly: omega / chi / phi circle slots bound to `RotaryStage` (and a `TiltStage` where range is limited), a `sample_table` slot bound to `LinearStage`, and a `reciprocal_space` slot bound to the existing `PseudoAxis` Family (its `partition_rule` resolving the hklpy2 inverse kinematics, the same mechanism as the 2-BM `objective_selector`). All slot families already exist, so no new Family is needed for the Assembly. It is deferred until the circle geometry confirms (`DIFF-1`) and a scenario registers a Fixture; the design-phase convention defers Assemblies until a Fixture is registered.

- **The Raman station.** `4-ID-Raman` is out of this cut because its device config did not extract (a symlink that did not resolve in the source clone). Its devices and whether it is a fifth enclosure are `TOPO-2`; it is a world-fact gap, tracked on [Open questions](questions.md), not a scope decision.

- **The 6-ID-B fork and the psic diffractometer.** A second instrument repo, `BCDA-APS/6idb-bits`, is a fork of `polar-bits`: its devices are almost entirely the same `4id*` PVs, with a grafted 6-ID-B endstation (a `psic` six-circle diffractometer at `6idb1:`, a CRL at `6idbSoft:TRANS:`). It is not an independent beamline, so it was used only as a second source to enrich this 4-ID descriptor (the `emag` magnet axes, the Euler diffractometer chi/phi circles), not to build a 6-ID-B deployment. The genuine 6-ID-B endstation (the `psic` diffractometer) is a future deployment, not modelled here. This fork also means the fleet recurrence report counts `polar-bits` and `6idb-bits` as two beamlines when they are one physical beamline, so the `Magnet` / `TemperatureController` / `Diffractometer` graduation signal rests on a single beamline; see [`catalog-graduation-decisions.md`](https://github.com/xmap/cora/blob/main/research/aps-reverse-engineering/catalog-graduation-decisions.md).

- **The diffraction / magnetism / polarization Methods.** Whether these techniques enter CORA's catalog (which has been all-imaging) is an owner decision. The Practices are registered pending and render unlinked; no Method is coined until the technique enters the pilot scope (`TECH-1`).

- **Peripheral electronics.** The preamplifiers, lock-in amplifier, LabJacks, and high-pressure-cell controllers are present in the beamline config but not modelled as Assets in this cut (`SAMPLE-2`). They join if they prove to be beamline equipment CORA should track.

- **Integration scenarios and vendor Models.** No `test_4id_*.py` registers 4-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real; hard-registering a first-cut, confirm-pending beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
