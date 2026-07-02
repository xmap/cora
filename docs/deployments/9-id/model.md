# Model

*The developer's by-kind index: where each CORA aggregate's 9-ID content lives, the cleanest pure-reuse case in the APS fleet whose metadata and Data Management PVs are a CORA seam not Assets, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 9-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](techniques.md) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](governance.md) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

## Catalog reuse (what this deployment proves)

9-ID is the cleanest reuse case in the APS fleet: a coherent-scattering beamline outside the imaging and diffraction cores, and yet every optic and detector binds a Family the catalog already had. `InsertionDevice`, `Monochromator`, `Mirror` (twice: the FMBO pair and the KB pair), `Aperture`, `Filter`, `Slit`, `Hexapod`, `Camera`, `BeamStop`, `LinearStage`, `RotaryStage`, `GenericProbe`, and the graduated `Transfocator` (the CRL focusing optic) all carry it with no new abstraction. That 9-ID needs no new Family is the evidence: the families earned on 2-BM, the diffraction beamlines, and the Diamond deployments cover a beamline none of them were derived from. So this cut adds nothing to `catalog.yaml`.

## A loose family still held for gate-review

9-ID's CRL `Transfocator` binds the graduated catalog Family (a CRL focusing optic) that 4-ID, 8-ID, and i22 also use. The cross-facility abstraction review settled the question of its catalog home: it is a CRL-specific Family, not a fold into a general focusing optic, so 9-ID's transfocator is plain catalog reuse now, like its mirrors. What graduation does not resolve is the per-Asset lens spec, the material and lenslet count of this transfocator, which stays open as `OPT-3`.

The `PositionMonitor`, which appears at 4-ID, 8-ID, and 9-ID, has since graduated into the catalog as its own Family presenting the `Sensor` Role, earned across the wide fleet that shares it (APS 4-ID/8-ID/9-ID, the NSLS-II beamlines, and the imaging and MX beamlines). The fold-vs-promote question that once held it is resolved in favour of promote: it is distinct from the graduated `FluxMonitor` by what it measures, beam position and centroid rather than flux or intensity (`FLUX-1` graduated `FluxMonitor`). Its naming-r3 review was done during that pass. The still-loose `Diagnostic` family (arrival-time and photon-spectrum monitors) is a separate abstraction that measures timing and spectrum, not position, and stays loose; only the per-Asset beam-center calibration and the position-versus-intensity channel split stay open here (`DIAG-1`).

| Loose family | Presents (when graduated) | At 9-ID | Also at |
| --- | --- | --- | --- |
| `PositionMonitor` | Sensor | TetrAMM + two XBPMs (9-ID-D) | 4-ID, 8-ID |

## The metadata and Data Management seam

The 9-ID instrument config carries a large set of metadata PVs (`experiment_name`, `sample_name`, `file_path`, `qmap_file`, `workflow_name`, `measurement_num`, and more) and a `DM_WorkflowConnector` that triggers APS Data Management workflows. These are not beamline hardware: they are where the beamline records what an experiment is and hands its data to downstream processing. That is exactly the job CORA's event-sourced system of record does. So they are modelled as a **seam, not as Assets**: CORA's Run and experiment record subsume the metadata bookkeeping, and the Data Management workflow trigger is the compute seam CORA's conduct path drives over (the same shape as the `DM_WorkflowConnector` that recurs in the APS fleet). Modelling these PVs as devices would mistake the bookkeeping CORA replaces for hardware it observes.

## Deliberately not here yet

- **The grazing-incidence sample Assembly.** The CSSI stack (translation, incidence rotation, hexapods, viewing microscope) is modelled as plain devices. Whether it composes into a sample Assembly, the way the 2-BM sample tower and the Diffractometer do, is deferred until a second grazing-incidence beamline gives the abstraction a rule-of-three (`CSSI-1`).

- **The diagnostic flags and the DAMM mask.** `flag1-3` and the DAMM mask carried only their insertion-motor PVs in the config; they are folded into a descriptor note pending identification, not modelled as Assets (`DIAG-1`).

- **The remaining scattering Methods.** 9-ID's surface-XPCS Practice now links to the catalog `xpcs` Method (shared with 8-ID; its DAQ-owned high-rate-stream execution is the event-stream axis, Stage 1). Whether coherent surface scattering and grazing-incidence scattering enter the catalog stays an owner decision; those Practices render unlinked, pending (`TECH-1`), and the WAXS Practice shares the i22 one.

- **The simulated devices.** The instrument config carries simulated motors and detectors (`sim_motor_cssi`, `sim_det_saxs`, and so on) for offline testing; they are excluded from the model.

- **Full asset-tree scenarios and vendor Models.** No `test_9id_*.py` registers the 9-ID asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).
