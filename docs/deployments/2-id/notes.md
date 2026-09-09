# Notes

## Techniques

*What the modelled part of 2-ID is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. This scaffold models 2-ID's 2-ID-D microprobe hutch, so the technique below is the scanning fluorescence one, carried as design intent. The function view survives the eventual hardware choices, which is why it can be written before the optics are confirmed.

### Scanning fluorescence microscopy

The microprobe focuses the monochromatic beam through a Fresnel zone plate to a small spot and rasters the sample through it, recording an X-ray fluorescence spectrum at each point with an energy-dispersive detector. Element maps are fit from the per-point spectra downstream (the EAA `XRF-Maps` lineage: scan data to fitted maps).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Scanning XRF mapping | `scanning_fluorescence_microscopy` (pending) | 2D fly raster or 1D step scan of the sample through the focused spot; a fluorescence spectrum per point |

This is a **new modality** for CORA. Every other deployment images by full-field projection and a rotation; this one builds an image point by point from a focused probe. There is no catalog Method for point-raster scanning fluorescence, so `scanning_fluorescence_microscopy` is named here but **not coined**: it renders unlinked, and the [APS Practice](../aps/index.md#the-techniques-adapted-here) that adapts it is carried pending (`METHOD-1`). The Method is earned into the catalog when 2-ID enters the pilot scope and a naming review accepts it, not in a design-phase scaffold. The coining decision is recorded on [Model](#deliberately-not-here-yet).

### Energy

2-ID-D runs monochromatic, the energy set by the upstream monochromator (assumed double-crystal, range unconfirmed, `MONO-1`). Scanning XANES (stepping the energy across an absorption edge per pixel) is a world-fact capability of the beamline but is absent from EAA's `aps_mic` code path, so it is not modelled here (see [Not modelled yet](#not-modelled-yet)).

### Not modelled yet

These are techniques the beamline is known to do but that this scaffold defers, because EAA does not evidence them or because they need hardware not yet modelled:

- **Scanning fluorescence tomography.** A rotation over a sequence of XRF maps. This is a Plan setpoint over the scanning-XRF Method, not a separate Method (mirroring the 2-BM decision that laminography is a tomography Plan at a tilt setpoint), and it needs a rotation axis the endstation is not yet modelled with (`ENV-1`). It joins when the rotation axis is confirmed.
- **Micro-XANES and ptychography.** Named by world-facts about the beamline but absent from EAA's `aps_mic` code path. Ptychography in particular needs a coherent-diffraction (transmission) detector this scaffold does not model. Modelling either now would be invention.

The concrete acquisition recipes (scan ranges, dwell times, target elements, energies) are not written yet; they join as the deployment approaches the point where CORA drives 2-ID. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who will act at 2-ID, and the trust shape that will gate it. Design-phase.*

Governance at 2-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

2-ID is a design-phase scaffold in CORA, so this shape is not yet instantiated. The 2-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation; CORA does not invent a 2-ID operator roster.

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#safety-and-governance), not on the beamline, and the beamline links up to them rather than restating them.

2-ID-D adds one governance shape the tomography pilots do not have: an **autonomous alignment agent in the loop**. The EAA microprobe agent drives the zone-plate autofocus and drift-correction loop, and its own examples gate every action behind an operator confirmation, with motion and beam disabled by default. In CORA's model that maps cleanly: EAA registers as an [Agent](#how-eaa-fits) whose proposals become Decisions, and the permit and clearance adjudication is the interpose point where an agent's proposed move is allowed or denied. The default-deny posture EAA already carries is the shape CORA's Conduit and Policy would enforce, not a new invention.

The concrete Zone, Conduit, and Policy instances, the operator pool, and the agent-authority policy land when the deployment approaches the point where CORA drives 2-ID, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 2-ID content lives, a scanning-fluorescence microprobe whose EAA autofocus loop dissolves into a CORA-conducted Run with an agent in the loop, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 2-ID |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### How EAA fits

This scaffold is mined from the [Experiment Automation Agents (EAA)](https://github.com/AdvancedPhotonSource/EAA) APS-microprobe integration (`packages/eaa-imaging/.../tool/imaging/aps_mic`) and its [2-ID-D launcher](https://github.com/AdvancedPhotonSource/eaa_driver_scripts_aps_2idd). EAA is read as data about the beamline, not copied as a design. CORA does not add a "confirm the EAA tool" row anywhere; it dissolves EAA into three things it already models:

- **Conductor replaces the orchestration.** EAA's `scan_control` runs the autofocus loop (acquire a 2D map, take a line scan, register it, step the `zp_z` focus axis, minimise the spot width) and submits the `fly2d` / `step1d` rasters over the EPICS scanRecord. That set-then-measure-until-criterion sequencing is what CORA's Conductor takes over: CORA owns the [Run lifecycle](../../architecture/modules/run/index.md) (start, hold, abort, close), the durable scan state, and the stopping governance. EAA fuses policy and sequencing in one loop; CORA draws the seam through the middle.
- **EPICS stays floor.** The EPICS scanRecord and sscan IOC, the motor PVs, the hardware-triggered raster, and the downstream `XRF-Maps` fitting are the floor and the compute edge. CORA observes and conducts over them; it never replaces them.
- **EAA registers as an Agent.** EAA's tactical decide loops (the LLM agent loop and the deterministic Bayesian-optimization parameter tuner) register as an external [Agent](../../architecture/modules/agent/index.md). Each proposed move and objective value becomes a Decision, with the LLM route recorded through the inference-recorder provenance path. EAA's own per-tool default-deny gate (operator confirmation required, motion and beam disabled by default) is exactly the interpose point CORA's permit and clearance adjudication occupies.

The net is regime-2 for CORA's runtime model: a CORA-conducted, multi-step compute-and-move Run, with an external agent proposing inside the loop. That is the shape the edge-runtime work anticipates, surfacing here as a concrete first consumer rather than a hypothetical.

### Deliberately not here yet

These are the parts of 2-ID this scaffold leaves out on purpose. Each is a CORA scope or naming decision, not a fact the beamline team needs to supply, so it lives here rather than on [Open questions](#open-questions).

- **The sister experiment hutch and the hutch roster.** The descriptor models one root Unit Asset `2-ID` with one experiment hutch (`2-ID-D`). Whether the sector adds a sister station (a 2-ID-E-class hutch) as a second hutch sub-tree, and where the shared optics sit, is held until `TOPO-1` resolves the roster. The root identity and `facility_code` binding do not migrate when it does: adding a hutch adds Component sub-trees, it does not re-home the root. This mirrors the 32-ID scaffold modelling only 32-ID-C and deferring 32-ID-B.

- **Coining the scanning-fluorescence Method.** `scanning_fluorescence_microscopy` is a new modality (point-raster XRF, mechanistically unlike full-field projection). A design-phase scaffold coins no Method, so it is named and rendered unlinked, carried as a pending Practice (`METHOD-1`). It is earned into the catalog when a confirmed scenario uses it and a naming review accepts the name.

- **Scanning fluorescence tomography as a Plan, not a Method.** A rotation over a sequence of XRF maps is a Plan setpoint over the scanning-XRF Method, the same way laminography is a tomography Plan at a tilt setpoint at 2-BM. It is not a separate Method, and it waits on a confirmed rotation axis (`ENV-1`).

- **Micro-XANES and ptychography.** Named by world-facts but absent from EAA's `aps_mic` code path; ptychography also needs a coherent-diffraction detector this scaffold does not model. Modelling either now would be invention.

- **Integration scenarios and vendor Models.** No `test_2id_*.py` registers 2-ID Assets, and no vendor Models are bound. Scenario code is where Assets become real, and hard-registering a simulation-mined, pre-confirmation beamline would commit speculative structure. Both land when the design firms and the team approves.

- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the 2-ID team to confirm before the model can be trusted.*

2-ID is a design-phase scaffold mined from the [EAA](https://github.com/AdvancedPhotonSource/EAA) APS-microprobe integration and its [2-ID-D launcher](https://github.com/AdvancedPhotonSource/eaa_driver_scripts_aps_2idd). The launcher is a simulation and EAA does not describe the source optics, so almost every value on the [device pages](index.md) is carried as a fact still to confirm. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are recorded on [Model](#deliberately-not-here-yet) instead). It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed, with the reason in the commit. Priorities are `Blocks-build` (the answer changes the structure of the model, so CORA cannot finalize the shape without it), `Blocks-go-live` (a placeholder is fine for the description, but the real value is needed before CORA observes or drives the hardware), and `Nice-to-have`.

### Topology and scope

The one structural unknown: the Sector 2 hutch roster and where the shared optics sit. The answer decides how many experiment hutches hang off the `2-ID` root and whether the source optics are one shared train or per-hutch.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | What is Sector 2's experiment-hutch roster (2-ID-D plus which sister stations), which hutch do the source optics serve, what is the upstream optics-hutch identity, and what is the post-APS-U layout of the sector? | One root Unit Asset `2-ID` with one modelled experiment hutch `2-ID-D`; the sister hutch(es) and the optics-hutch are unmodelled pending this answer. | The hutch roster, the optics-hutch Enclosure, and one-vs-many hutch sub-trees in the [descriptor](index.md). |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | What are the EPICS PV handles (and drive crates / IOC hosts) for each modelled device, and the Bluesky / scanRecord configuration for the raster? | Control handles are unassigned; CORA leaves each device handle empty. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-go-live | What is the PSS search-and-secure permit signal for the 2-ID-D hutch (and the other hutches once `TOPO-1` resolves the roster)? | The 2-ID-D hutch exists with a permit signal to be named. | The Enclosure permit signal. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The Sector 2 insertion-device source: device type, period, gap, and whether one source feeds more than one hutch. | One `InsertionDevice` Asset (undulator); type and period unconfirmed. | The insertion-device specs. |
| SRC-2 | Nice-to-have | The front-end and beam-defining optics between the source and the zone plate (front-end mask, window, white-beam and beam-defining slits), which EAA does not describe. | None modelled; the source stretch from front end to zone plate is carried as undescribed. | The front-end and beam-defining optics. |
| MONO-1 | Blocks-go-live | The monochromator: is it a double-crystal Si monochromator, what is its crystal and energy range, what are its axes, and which optics hutch is it in? | One `Monochromator` Asset, double-crystal, energy range unconfirmed; located upstream. | The monochromator presence, crystal, axes, and energy model. |
| OPTICS-1 | Blocks-go-live | The probe-forming Fresnel zone plate parameters (outermost-zone width, diameter, material) that set the spot size, and the order-sorting aperture that pairs with it. | One `ZonePlate` Asset (catalog Family) with a `zp_z` focus axis; the order-sorting aperture is folded in, not separately modelled. | The zone-plate spec and the order-sorting aperture. |

### Sample-scanning endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| AXIS-1 | Blocks-go-live | The sample-scanning axis complement: the horizontal scan axis (EAA evidences vertical `samy` and standoff `samz` but not the horizontal raster axis), and the coarse-stage vs fine-piezo split a microprobe carries. | One coarse `SamplePositioning` stack (`LinearStage`); the horizontal scan axis and coarse/fine split unconfirmed. | The sample-stage axes and the coarse/fine model. |
| ENV-1 | Nice-to-have | The sample environment: any in-situ stage (cryo, heating), and whether the endstation carries a rotation axis (which scanning fluorescence tomography would need). | No sample environment and no rotation axis modelled. | The sample-environment Fixtures and any rotation axis. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The energy-dispersive fluorescence detector: model, number of elements / segmentation, and energy resolution. | One fluorescence-detector Asset bound to the catalog `EnergyDispersiveSpectrometer` Family; model and channels unconfirmed. | The detector Model binding. |
| DET-2 | Nice-to-have | The detection readout chain: the preamplifier (EAA names a `Preamp1`), the EPICS scalers, and the I0 flux monitors (ion chambers) the scan normalizes against. | A preamplifier, scalers, and flux monitors exist as the readout chain; identities unconfirmed and not separately modelled. | The readout-chain Assets and the normalization model. |

### Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | What continuously-available supplies does the 2-ID-D endstation draw on (cooling water, and any sample-environment gases)? | A photon beam and cooling water; sample-environment supplies unconfirmed. | The Supply records. |
