# Open questions

*What CORA needs the I22 team (and Diamond's documentation) to confirm before the model can be trusted.*

I22 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles at high confidence; it does not give the calibrated numbers, the hutch/safety structure, the passive beam-path tier, or the technique binding. This page collects what dodal cannot supply. Each row is a fact the beamline team (or a Diamond drawing / the published I22 beamline paper) owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

Note on what dodal already settled, so it is **not** a question here: the EPICS PV prefix for every device is recorded in the descriptor (this is the one thing I22 has that the TomoWISE scaffold did not), and the device-to-Family mapping is high-confidence. The questions below are the layers above that.

A note on what I22 tests that the tomography pilots did not: I22 is a SAXS/WAXS scattering beamline, so its science Capabilities are new, it runs two detectors simultaneously, and it carries quantitative flux monitors and sample-environment actuators. The questions concentrate on those new shapes.

## Scope and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I22 (or any Diamond beamline) actually intended to enter CORA scope, or is this purely a generalization exercise against an open controls source? | A generalization exercise: I22 proves the dodal-seed to intentional-model pipeline and stresses the non-tomography axis; it is not on the pilot roadmap. | Whether Diamond becomes a real Site or stays a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the optics and experiment hutches? | Both hutches exist with permit signals to be named; dodal does not carry them. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones (OP, MO, EA, DI), not the access-gated hutch or its safety meaning. | The standard Diamond optics + experiment hutch split, with conditioning optics upstream and sample + detectors downstream. | The per-device Enclosure assignment. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the undulator energy range, period, minimum gap, and gap-to-energy curve? dodal carries only 80 poles and 2.0 m length, plus a lookup-table path on the Diamond filesystem. | An undulator source with the dodal poles/length; the energy range and curve are calibration to supply. | The `Undulator` parameters and the beamline energy range. |
| MACHINE-1 | Nice-to-have | How should the machine-level storage-ring state (ring current, fill mode, top-up countdown) be modelled: a loose `StorageRing` source, an observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, mirroring the loose beam-source representation the APS deployments use. | The machine-state modelling boundary. |
| OPT-1 | Nice-to-have | What are the mirror coatings/stripes, the DCM crystal d-spacing and thermal model, and the bimorph channel calibration? dodal exposes the axes and the Si(111) crystal and channel counts, but not the calibrated optic settings. | The optic internals are per-Asset settings or a bound Model on the existing `Mirror` / `Monochromator` Families, not new Families. | Which optic internals are modelled and where they live. |
| CRL-1 | Blocks-go-live | Is the transfocator (compound refractive lens) a new catalog Family, or does it fold into an existing Family plus settings? An adversarial review deferred it as loose. | A loose `Transfocator` family, earned into the catalog only on a rule-of-three across deployments. | The transfocator modelling boundary. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Are the SAXS and WAXS camera lengths fixed mounts or settable axes (a movable detector / flight tube)? dodal carries a single distance snapshot for each. | The two detectors are one `Camera` Family at two positions; whether distance is a settable axis (warranting a detector-translation `LinearStage` Asset) is open. | Whether a detector-translation Asset is modelled. |
| DET-2 | Blocks-go-live | What are the Pilatus threshold energy and the per-detector beam-center? Both are `None` in dodal and are required for SAXS/WAXS data reduction. | Not modelled until supplied; these are calibrated, beam-energy-dependent values. | The detector calibration the data reduction needs. |
| OAV-1 | Blocks-go-live | What are the on-axis-view camera working distance and effective pixel size? dodal carries a sentinel distance (-1.0 m) and a pixel size flagged "double check". | Not modelled; both depend on viewing optics dodal does not model. | The OAV geometry. |

## Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FLUX-1 | Blocks-go-live | How are the incident and transmitted ion chambers (I0 / It) modelled: a new `FluxMonitor` Family, or the existing Sensor Role with a deployment-local device? And is the incident-vs-transmitted distinction a placement setting? | The existing Sensor Role (whose docstring names ion chambers), carried as a loose `FluxMonitor` family; incident vs transmitted is placement, not a Family split. | The flux-monitor modelling boundary. |
| ENV-1 | Blocks-go-live | Must CORA command the sample-environment setpoints (the Linkam temperature controller, the peristaltic pump), or only read them back? | The settable-actuator shape is now settled: the Linkam binds the graduated `TemperatureController` Family (presents `Regulator`, requires `Settable`); the pump is a loose `FlowController` that would present `Regulator` once it graduates. What is open is whether CORA commands the setpoints. | The command-vs-read decision (shared with 7-BM FLOW-1). |

## Techniques and identity

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Which scattering Capabilities and Methods are in scope (small-angle, wide-angle, simultaneous SAXS+WAXS, time-resolved), and how is a simultaneous SAXS+WAXS acquisition represented? | SAXS and WAXS are new Capabilities not yet in the catalog; simultaneous acquisition is coordinated Runs, carried pending on the [Diamond Practices](../diamond/index.md). | Which Capabilities and Methods the catalog earns. |
| TRIG-1 | Nice-to-have | How do the PandABox FPGA boxes bind to the detectors and flux monitors (trigger fan-out, gating, the master clock)? | One or two `TimingController` devices carry the scheme, mirroring the 2-BM Timing device; the detector/flux binding is a Method concern. | The triggering-subsystem binding. |
| GROUP-1 | Nice-to-have | Does the SAXS detector share an Assembly with its beamstops and base stage, or are they independent devices? dodal models them separately. | Independent devices in this scaffold; an Assembly is earned only when a feature must act on the whole. | The `parent_id` / Assembly grouping. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags) for the devices? dodal carries none. | Assets carry no part/serial identity until supplied. | The Asset hardware-identity fields. |
