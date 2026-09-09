# Notes

## Techniques

*What I22 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I22 is the first scattering beamline CORA has looked at, so its techniques are the first that do not reduce to the existing tomography and acquisition Capabilities. Which scattering Capabilities and Methods the catalog earns is itself an open question (TECH-1); the function view below survives the eventual vocabulary choices, which is why it can be written before the catalog is extended.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Small-angle scattering (SAXS) | monochromatic, KB-focused | `SaxsDetector` (Pilatus3 2M, long camera length) | new Capability, pending (TECH-1) |
| Wide-angle scattering (WAXS) | monochromatic, KB-focused | `WaxsDetector` (Pilatus3 2M, short camera length) | new Capability, pending (TECH-1) |
| Simultaneous SAXS+WAXS | monochromatic, KB-focused | both detectors at once | coordinated Runs, the routine mode, pending (TECH-1) |
| Time-resolved SAXS/WAXS | monochromatic | both detectors, PandA-gated | new acquisition Method, deferred until confirmed |

A few points of intent shape the model:

- **The Capabilities are genuinely new.** Tomography reduces to the `tomography` and `acquisition` Capabilities the catalog already carries; SAXS and WAXS do not. They are the cleanest test of whether CORA's Capability layer generalizes past imaging. They are carried as pending Practices on the [Diamond Site](../diamond/index.md), not minted into the catalog, until the technique enters a real scope (TECH-1). A beamline that is a modelling exercise does not get to mint cross-facility vocabulary.
- **Simultaneous acquisition is coordinated Runs, not a combined technique.** The routine I22 mode reads the SAXS and WAXS detectors at once. CORA models that as coordinated Runs under one Campaign over a shared trigger, the same way 7-BM models energy-dispersive diffraction running alongside tomography, not as a third combined technique.
- **The detector Roles already exist.** Both detectors present the existing Detector Role; the flux monitors present the existing Sensor Role. No new Role is needed for scattering, only new science Capabilities. The device anatomy generalized cleanly; the technique vocabulary is what is new.
- **Beam mode is one focused, monochromatic path.** The undulator feeds the double-crystal monochromator and the KB mirror pair; SAXS and WAXS share that one conditioned beam, distinguished by detector position, not beam mode.

The concrete acquisition recipes (q-ranges, camera lengths, exposure, time-resolved sequences) are not written: they are calibration the deployment must supply. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who would act at I22, and the trust shape that would gate it. Design-phase.*

Governance at I22 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

I22 introduces the third Site CORA models, after APS and MAX IV. Unlike 7-BM (which reused the existing APS envelope) and like TomoWISE (which created MAX IV), I22 requires a new Diamond Site: the facility, its operator pool, its safety review structure, and its safety forms are all Diamond-specific and carried pending on the [Diamond Site page](../diamond/index.md) until staff confirm them. None of this is in dodal, which is a controls library, not an organizational record.

Because I22 is a modelling exercise rather than a pilot, the concrete trust shape is not instantiated. What is already settled is the boundary, the same as for every deployment: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them rather than restating them. The Diamond personnel safety system (PSS) clearance is carried pending because its form names are not confirmed (PSS-1).

One governance note is specific to the off-roadmap nature of this exercise: whether Diamond becomes a real CORA Site at all is itself an open question (SCOPE-1). Until it is answered, the Diamond Site exists as a design-phase fixture that exercises the second-Site machinery (a new Facility, new principals, new clearances) without committing CORA to operate there.

The concrete Zone, Conduit, and Policy instances, and the Diamond operator pool, would land if and when the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's I22 content lives, why it earns no catalog kinds and carries real EPICS handles, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I22 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What is deliberately not here yet

- **New catalog Families, Capabilities, and Methods.** I22 does not earn new catalog kinds in this scaffold. An adversarial new-kind review refuted all five proposed device anatomies as catalog Families on the strength of I22 alone; four (`TemperatureController`, `FluxMonitor`, `Transfocator`, `FlowController`) have since graduated to the catalog once a rule-of-three across deployments settled them, and the remaining one (`StorageRing`) is still carried as a loose family with a tracking question. The new scattering Capabilities are carried as pending Practices. A kind is added to the catalog only when a confirmed device or technique and the naming review settle it. This follows the "pilots earn the abstractions" rule, and I22 is explicitly not a pilot (SCOPE-1).
- **Integration scenarios.** No `test_i22_*.py` registers I22 Assets into the event store. Hard-registering a design-phase, off-roadmap beamline would commit speculative structure.
- **Vendor Models.** No catalog Model is bound. The hardware dodal names (Dectris, AVT, Watson-Marlow, Linkam) is recorded in the descriptor notes, not bound.
- **Operations and experiment views.** A runbook and live experiment view for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies.** The two detectors are left as plain `Camera` devices. Whether the SAXS detector composes an Assembly with its beamstops and base is deferred (GROUP-1).

What is genuinely new here versus the other scaffolds: the descriptor carries real EPICS control handles (from dodal), and the open questions are about the layers dodal cannot reach (calibration, safety, technique), not about the PVs.

## Open questions

*What CORA needs the I22 team (and Diamond's documentation) to confirm before the model can be trusted.*

I22 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles at high confidence; it does not give the calibrated numbers, the hutch/safety structure, the passive beam-path tier, or the technique binding. This page collects what dodal cannot supply. Each row is a fact the beamline team (or a Diamond drawing / the published I22 beamline paper) owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

Note on what dodal already settled, so it is **not** a question here: the EPICS PV prefix for every device is recorded in the descriptor (this is the one thing I22 has that the TomoWISE scaffold did not), and the device-to-Family mapping is high-confidence. The questions below are the layers above that.

A note on what I22 tests that the tomography pilots did not: I22 is a SAXS/WAXS scattering beamline, so its science Capabilities are new, it runs two detectors simultaneously, and it carries quantitative flux monitors and sample-environment actuators. The questions concentrate on those new shapes.

### Scope and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I22 (or any Diamond beamline) actually intended to enter CORA scope, or is this purely a generalization exercise against an open controls source? | A generalization exercise: I22 proves the dodal-seed to intentional-model pipeline and stresses the non-tomography axis; it is not on the pilot roadmap. | Whether Diamond becomes a real Site or stays a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the optics and experiment hutches? | Both hutches exist with permit signals to be named; dodal does not carry them. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones (OP, MO, EA, DI), not the access-gated hutch or its safety meaning. | The standard Diamond optics + experiment hutch split, with conditioning optics upstream and sample + detectors downstream. | The per-device Enclosure assignment. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the undulator energy range, period, minimum gap, and gap-to-energy curve? dodal carries only 80 poles and 2.0 m length, plus a lookup-table path on the Diamond filesystem. | An undulator source with the dodal poles/length; the energy range and curve are calibration to supply. | The `Undulator` parameters and the beamline energy range. |
| MACHINE-1 | Nice-to-have | How should the machine-level storage-ring state (ring current, fill mode, top-up countdown) be modelled: a loose `StorageRing` source, an observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, mirroring the loose beam-source representation the APS deployments use. | The machine-state modelling boundary. |
| OPT-1 | Nice-to-have | What are the mirror coatings/stripes, the DCM crystal d-spacing and thermal model, and the bimorph channel calibration? dodal exposes the axes and the Si(111) crystal and channel counts, but not the calibrated optic settings. | The optic internals are per-Asset settings or a bound Model on the existing `Mirror` / `Monochromator` Families, not new Families. | Which optic internals are modelled and where they live. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Are the SAXS and WAXS camera lengths fixed mounts or settable axes (a movable detector / flight tube)? dodal carries a single distance snapshot for each. | The two detectors are one `Camera` Family at two positions; whether distance is a settable axis (warranting a detector-translation `LinearStage` Asset) is open. | Whether a detector-translation Asset is modelled. |
| DET-2 | Blocks-go-live | What are the Pilatus threshold energy and the per-detector beam-center? Both are `None` in dodal and are required for SAXS/WAXS data reduction. | Not modelled until supplied; these are calibrated, beam-energy-dependent values. | The detector calibration the data reduction needs. |
| OAV-1 | Blocks-go-live | What are the on-axis-view camera working distance and effective pixel size? dodal carries a sentinel distance (-1.0 m) and a pixel size flagged "double check". | Not modelled; both depend on viewing optics dodal does not model. | The OAV geometry. |

### Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FLUX-1 | Blocks-go-live | How are the incident and transmitted ion chambers (I0 / It) modelled: a new `FluxMonitor` Family, or the existing Sensor Role with a deployment-local device? And is the incident-vs-transmitted distinction a placement setting? | The existing Sensor Role (whose docstring names ion chambers), now via the graduated `FluxMonitor` catalog Family (rule-of-three i22/i03/i15-1); incident vs transmitted is placement, not a Family split. | The flux-monitor modelling boundary. |
| ENV-1 | Blocks-go-live | Must CORA command the sample-environment setpoints (the Linkam temperature controller, the peristaltic pump), or only read them back? | The settable-actuator shape is now settled: the Linkam binds the graduated `TemperatureController` Family (presents `Regulator`, requires `Settable`); the pump binds the graduated `FlowController` Family (presents `Regulator`, the `TemperatureController` sibling, earned across i22 / 7-BM / LIX / XFP). What is open is whether CORA commands the setpoints. | The command-vs-read decision (shared with 7-BM FLOW-1). |

### Techniques and identity

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Which scattering Capabilities and Methods are in scope (small-angle, wide-angle, simultaneous SAXS+WAXS, time-resolved), and how is a simultaneous SAXS+WAXS acquisition represented? | SAXS and WAXS are new Capabilities not yet in the catalog; simultaneous acquisition is coordinated Runs, carried pending on the [Diamond Practices](../diamond/index.md). | Which Capabilities and Methods the catalog earns. |
| TRIG-1 | Nice-to-have | How do the PandABox FPGA boxes bind to the detectors and flux monitors (trigger fan-out, gating, the master clock)? | One or two `TimingController` devices carry the scheme, mirroring the 2-BM Timing device; the detector/flux binding is a Method concern. | The triggering-subsystem binding. |
| GROUP-1 | Nice-to-have | Does the SAXS detector share an Assembly with its beamstops and base stage, or are they independent devices? dodal models them separately. | Independent devices in this scaffold; an Assembly is earned only when a feature must act on the whole. | The `parent_id` / Assembly grouping. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags) for the devices? dodal carries none. | Assets carry no part/serial identity until supplied. | The Asset hardware-identity fields. |
