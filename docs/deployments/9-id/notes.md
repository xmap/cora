# Notes

## Techniques

*What the modelled part of 9-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 9-ID's techniques are coherent surface scattering and grazing-incidence scattering, new to CORA's imaging-heritage catalog, so the Methods below render unlinked and are carried pending until one enters scope (`TECH-1`).

### Coherent surface scattering

The CSSI signature: a coherent beam strikes the sample surface at a shallow grazing angle, so the scattered intensity is sensitive to surface structure and, over time, surface dynamics.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Coherent surface scattering | `coherent_surface_scattering` | the grazing-incidence coherent measurement on the area detectors; Method not yet in catalog |
| Surface XPCS | [`xpcs`](../../catalog/methods.md) | time-correlation of the surface speckle pattern; shares the 8-ID `xpcs` catalog Method (its DAQ-owned high-rate-stream execution is the event-stream axis, Stage 1) |

Both need the [grazing-incidence sample stack](sample.md) (the incidence rotation sets the angle) and the [coherent detectors](detector.md).

### Grazing-incidence scattering

GISAXS and GIWAXS read the small- and wide-angle scattering from the grazing-incidence geometry.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Grazing-incidence scattering | `grazing_incidence_scattering` | GISAXS on the Pilatus / Eiger and GIWAXS on the pedestal detector (`TECH-1`) |
| Wide-angle scattering | `wide_angle_scattering` | the GIWAXS leg; shares the i22 WAXS Method |

It needs the same sample stack and the [WAXS detector](detector.md) on its pedestal.

### Not modelled yet

The concrete acquisition recipes (incidence-angle scans, correlation time series, frame rates, exposures) are not written yet; they join as the deployment approaches the point where CORA drives 9-ID. Whether these Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at 9-ID, and the trust shape that will gate it. First cut.*

Governance at 9-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

9-ID is not yet driven by CORA, so this shape is not yet instantiated. The 9-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation (a placeholder `9-ID Beamline Scientist` is carried pending on the [APS Site](../aps/index.md#safety-and-governance)).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#safety-and-governance), not on the beamline, and the beamline links up to them. 9-ID's hazard classes are within the X-ray and vacuum envelope of the optics-and-detector beamlines; user-brought sample environments on the CSSI stack would carry their own hazards on an experiment Clearance, landing with the instruments that bring them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives 9-ID, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 9-ID content lives, the cleanest pure-reuse case in the APS fleet whose metadata and Data Management PVs are a CORA seam not Assets, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 9-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Catalog reuse (what this deployment proves)

9-ID is the cleanest reuse case in the APS fleet: a coherent-scattering beamline outside the imaging and diffraction cores, and yet every optic and detector binds a Family the catalog already had. `InsertionDevice`, `Monochromator`, `Mirror` (twice: the FMBO pair and the KB pair), `Aperture`, `Filter`, `Slit`, `Hexapod`, `Camera`, `BeamStop`, `LinearStage`, `RotaryStage`, `GenericProbe`, and the graduated `Transfocator` (the CRL focusing optic) all carry it with no new abstraction. That 9-ID needs no new Family is the evidence: the families earned on 2-BM, the diffraction beamlines, and the Diamond deployments cover a beamline none of them were derived from. So this cut adds nothing to `catalog.yaml`.

### A loose family still held for gate-review

9-ID's CRL `Transfocator` binds the graduated catalog Family (a CRL focusing optic) that 4-ID, 8-ID, and i22 also use. The cross-facility abstraction review settled the question of its catalog home: it is a CRL-specific Family, not a fold into a general focusing optic, so 9-ID's transfocator is plain catalog reuse now, like its mirrors. What graduation does not resolve is the per-Asset lens spec, the material and lenslet count of this transfocator, which stays open as `OPT-3`.

The `PositionMonitor`, which appears at 4-ID, 8-ID, and 9-ID, has since graduated into the catalog as its own Family presenting the `Sensor` Role, earned across the wide fleet that shares it (APS 4-ID/8-ID/9-ID, the NSLS-II beamlines, and the imaging and MX beamlines). The fold-vs-promote question that once held it is resolved in favour of promote: it is distinct from the graduated `FluxMonitor` by what it measures, beam position and centroid rather than flux or intensity (`FLUX-1` graduated `FluxMonitor`). Its naming-r3 review was done during that pass. The still-loose `Diagnostic` family (arrival-time and photon-spectrum monitors) is a separate abstraction that measures timing and spectrum, not position, and stays loose; only the per-Asset beam-center calibration and the position-versus-intensity channel split stay open here (`DIAG-1`).

| Loose family | Presents (when graduated) | At 9-ID | Also at |
| --- | --- | --- | --- |
| `PositionMonitor` | Sensor | TetrAMM + two XBPMs (9-ID-D) | 4-ID, 8-ID |

### The metadata and Data Management seam

The 9-ID instrument config carries a large set of metadata PVs (`experiment_name`, `sample_name`, `file_path`, `qmap_file`, `workflow_name`, `measurement_num`, and more) and a `DM_WorkflowConnector` that triggers APS Data Management workflows. These are not beamline hardware: they are where the beamline records what an experiment is and hands its data to downstream processing. That is exactly the job CORA's event-sourced system of record does. So they are modelled as a **seam, not as Assets**: CORA's Run and experiment record subsume the metadata bookkeeping, and the Data Management workflow trigger is the compute seam CORA's conduct path drives over (the same shape as the `DM_WorkflowConnector` that recurs in the APS fleet). Modelling these PVs as devices would mistake the bookkeeping CORA replaces for hardware it observes.

### Deliberately not here yet

- **The grazing-incidence sample Assembly.** The CSSI stack (translation, incidence rotation, hexapods, viewing microscope) is modelled as plain devices. Whether it composes into a sample Assembly, the way the 2-BM sample tower and the Diffractometer do, is deferred until a second grazing-incidence beamline gives the abstraction a rule-of-three (`CSSI-1`).

- **The diagnostic flags and the DAMM mask.** `flag1-3` and the DAMM mask carried only their insertion-motor PVs in the config; they are folded into a descriptor note pending identification, not modelled as Assets (`DIAG-1`).

- **The remaining scattering Methods.** 9-ID's surface-XPCS Practice now links to the catalog `xpcs` Method (shared with 8-ID; its DAQ-owned high-rate-stream execution is the event-stream axis, Stage 1). Whether coherent surface scattering and grazing-incidence scattering enter the catalog stays an owner decision; those Practices render unlinked, pending (`TECH-1`), and the WAXS Practice shares the i22 one.

- **The simulated devices.** The instrument config carries simulated motors and detectors (`sim_motor_cssi`, `sim_det_saxs`, and so on) for offline testing; they are excluded from the model.

- **Full asset-tree scenarios and vendor Models.** No `test_9id_*.py` registers the 9-ID asset tree, and no vendor Models are bound. Those land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the 9-ID team to confirm before the model can be trusted.*

9-ID was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/9id_bits](https://github.com/BCDA-APS/9id_bits)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from a config snapshot rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet), including the metadata seam and the graduated `PositionMonitor` catalog Family). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | Do the two stations (`9-ID-A`, `9-ID-D`) run off one beam in series, and is there a single undulator or a canted pair? The config showed one undulator (`S09ID:DSID:`) and `9-ID-A` / `9-ID-D` prefixes. | One root Unit Asset `9-ID` with one optics spine feeding 9-ID-D in series; one undulator. | The beam walk and station count in the [descriptor](index.md). |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the 9id_bits config current and correct? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| CTRL-2 | Nice-to-have | The fly-scan timing: the multi-channel scaler (`9idCSSI:mcs2-01`) and any pulse routing that gates the grazing-incidence scans. | One `GenericProbe` scaler is modelled; the timing graph is not. | The fly-scan timing model. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals for the two hutches (`9-ID-A`, `9-ID-D`). | Two hutches exist with permit signals to be named. | The Enclosure permit signals. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The undulator on S09ID: type, period, and whether a second device or a canted pair exists. | One `InsertionDevice` Asset; period unconfirmed. | The insertion-device spec. |
| MONO-1 | Blocks-go-live | The Kohzu monochromator (`idt_mono`, `9ida:`): energy range, crystal set, and per-axis roles. | One `Monochromator` Asset; range unconfirmed. | The monochromator energy model. |
| OPT-1 | Nice-to-have | The two FMBO mirrors: coatings and the bender / piezo-pitch axis roles. | Two `Mirror` Assets with the config's axis maps; coatings unconfirmed. | The mirror specs. |
| OPT-2 | Nice-to-have | The white-beam apertures (`SL-1`, `SL-2`) and the guard slits (`Slit3/4/5`): the internal axis maps. | `Aperture` and `Slit` Assets with base PVs; per-blade axes partial. | The aperture and slit axis maps. |
| OPT-3 | Blocks-go-live | The JJ CRL transfocator (`9idPyCRL:CRL9ID:`): lens material, count, and which stations it focuses. | One `Transfocator` Asset (the graduated catalog Family). | The transfocator spec. |
| OPT-4 | Nice-to-have | The AVS attenuator (`9idPyFilter:FL1:`): the foil / absorber set. | One `Filter` Asset. | The attenuator model. |
| OPT-5 | Nice-to-have | The KB focusing pair (`9idKB:`): the per-mirror bender axes and the focal geometry (capacitive-sensor suffixes resolved at runtime). | One `Mirror` Asset with four bender axes plus a granite support. | The KB axis map. |

### Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CSSI-1 | Blocks-build | The grazing-incidence sample geometry: which motor sets the incidence angle, and the translation-vs-rotation roles of the CSSI stack (`9idCSSI:mcs2-01`, the Aerotech fly Z, the Kohzu stage). | A `LinearStage` for translation and a `RotaryStage` for the incidence angle; the Kohzu stage folded into a note. | The sample geometry and whether it composes into an Assembly. |
| CSSI-2 | Nice-to-have | The two Aerotech hexapods (`HP1`, `HP2`): what each aligns (sample, KB, detector). | Two `Hexapod` Assets for sample/optic alignment. | The hexapod roles. |
| CSSI-3 | Nice-to-have | The viewing microscope (`uscope`, `9idCSSI:CR9D1M2`): on-axis sample viewing or a separate optic. | One `Camera` Asset for sample viewing. | The microscope role. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The area detectors: the Pilatus 1M (`PILATUS_1MF:`), the Eiger (prefix a guess), and the WAXS / GIWAXS detector on its pedestal: models, sensors, frame rates. | `Camera` Assets; models unconfirmed. | The detector Model bindings. |
| BPM-1 | Nice-to-have | The TetrAMM (`9idTetra:QUAD1:`) and the two XBPMs (`xpbm1`, `xpbm2`): which are position monitors versus intensity (I0) normalizers? | Bound to the graduated catalog `PositionMonitor` Family presenting the Sensor Role. | The monitor classification. |
| DIAG-1 | Nice-to-have | The diagnostic flag cameras (`flag1-3`) and the DAMM mask (`9ida:CR9A1`): what each is, and whether the flags carry cameras CORA should model. | Folded into a descriptor note; not modelled as Assets (only insertion motors extracted). | The diagnostic identification. |

### Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | The vacuum and process-gas supplies the focusing optics and detector flight draw on. | Photon beam, cooling water, and vacuum carried in the descriptor. | The Supply records. |
