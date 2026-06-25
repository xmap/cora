# Model

*The developer's index into where 9-ID content lives, the catalog reuse this deployment proves, the metadata seam, and the record of what is deliberately deferred. First cut.*

9-ID is a descriptor-and-docs scaffold today, reverse-engineered from the beamline's instrument repo: it exists as the descriptor and docs below, not yet as registered events or integration scenarios. This page points to where each piece lives, and records the scope decisions that are CORA's to make (kept off the staff [Open questions](questions.md), which carry only world-facts).

| Kind | Where | Notes |
| --- | --- | --- |
| Beamline descriptor | [`deployments/9-id/beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/9-id/beamline.yaml) | the device walk with bound PVs; source of the generated [Source](beamline.md) page |
| Site descriptor | [`deployments/aps/site.yaml`](https://github.com/xmap/cora/blob/main/deployments/aps/site.yaml) | the APS facility surface; `9-ID` added to its beamline list, with CSSI Practices |
| Extraction provenance | [`research/aps-reverse-engineering/extracted/9id_bits/`](https://github.com/xmap/cora/tree/main/research/aps-reverse-engineering) | the facts report and candidate the descriptor was curated from |
| Catalog Family | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; 9-ID is pure reuse, plus two loose families it shares with 4-ID / 8-ID (below) |
| Catalog Method | [`catalog/catalog.yaml`](https://github.com/xmap/cora/blob/main/catalog/catalog.yaml) | none added; the surface-scattering / scattering / XPCS Methods are not yet coined (TECH-1) |
| Equipment Assets | not yet registered | the [Inventory](inventory.md) is the planned shape; no scenario registers 9-ID Assets yet |
| Trust / governance | not yet instantiated | see [Governance](governance.md) |

## Catalog reuse (what this deployment proves)

9-ID is the cleanest reuse case in the APS fleet: a coherent-scattering beamline outside the imaging and diffraction cores, and yet every optic and detector binds a Family the catalog already had. `InsertionDevice`, `Monochromator`, `Mirror` (twice: the FMBO pair and the KB pair), `Aperture`, `Filter`, `Slit`, `Hexapod`, `Camera`, `BeamStop`, `LinearStage`, `RotaryStage`, and `GenericProbe` all carry it with no new abstraction. That 9-ID needs no new Family is the evidence: the families earned on 2-BM, the diffraction beamlines, and the Diamond deployments cover a beamline none of them were derived from. So this cut adds nothing to `catalog.yaml`.

## Loose families held for gate-review

9-ID adds a further independent APS beamline to two device classes that recur widely. The CRL `Transfocator` now appears at 4-ID, 8-ID, i22, and 9-ID; the `BeamPositionMonitor` at 4-ID, 8-ID, and 9-ID. The count is well past the promotion threshold, but `main` deliberately holds both loose pending the cross-facility abstraction reviews the Diamond deployments opened: the CRL optic's catalog home (`CRL-1`) and the beam-position sensor's fold-vs-promote question against the held `Diagnostic` / `FluxMonitor` families (`DIAG-1` / `FLUX-1`). The trigger is the abstraction question, not the count, so they stay loose here too, allowlisted and recorded in the promotion-review register. Their naming-r3 review is done; the abstraction decision is gate-review's, not this PR's.

| Loose family | Presents (when graduated) | At 9-ID | Also at |
| --- | --- | --- | --- |
| `Transfocator` | Positioner | JJ CRL transfocator (9-ID-D) | 4-ID, 8-ID, i22 |
| `BeamPositionMonitor` | Sensor | TetrAMM + two XBPMs (9-ID-D) | 4-ID, 8-ID |

That a fourth beamline cannot graduate the `Transfocator` on count alone is the point of the hold: the open question is what the abstraction is (a CRL-specific Family, or a more general focusing optic), and that is `CRL-1`'s to settle.

## The metadata and Data Management seam

The 9-ID instrument config carries a large set of metadata PVs (`experiment_name`, `sample_name`, `file_path`, `qmap_file`, `workflow_name`, `measurement_num`, and more) and a `DM_WorkflowConnector` that triggers APS Data Management workflows. These are not beamline hardware: they are where the beamline records what an experiment is and hands its data to downstream processing. That is exactly the job CORA's event-sourced system of record does. So they are modelled as a **seam, not as Assets**: CORA's Run and experiment record subsume the metadata bookkeeping, and the Data Management workflow trigger is the compute seam CORA's conduct path drives over (the same shape as the `DM_WorkflowConnector` that recurs in the APS fleet). Modelling these PVs as devices would mistake the bookkeeping CORA replaces for hardware it observes.

## Deliberately not here yet

- **The grazing-incidence sample Assembly.** The CSSI stack (translation, incidence rotation, hexapods, viewing microscope) is modelled as plain devices. Whether it composes into a sample Assembly, the way the 2-BM sample tower and the Diffractometer do, is deferred until a second grazing-incidence beamline gives the abstraction a rule-of-three (`CSSI-1`).

- **The diagnostic flags and the DAMM mask.** `flag1-3` and the DAMM mask carried only their insertion-motor PVs in the config; they are folded into a descriptor note pending identification, not modelled as Assets (`DIAG-1`).

- **The surface-scattering / scattering / XPCS Methods.** Whether coherent surface scattering, grazing-incidence scattering, and XPCS enter CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`). 9-ID's XPCS Practice shares the 8-ID XPCS Method and its WAXS Practice shares the i22 one.

- **The simulated devices.** The instrument config carries simulated motors and detectors (`sim_motor_cssi`, `sim_det_saxs`, and so on) for offline testing; they are excluded from the model.

- **Full asset-tree scenarios and vendor Models.** No `test_9id_*.py` registers the 9-ID asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

The [2-BM Model page](../2-bm/model.md) shows the by-kind index a fully-modelled deployment carries.
