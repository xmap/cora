# Notes

## Techniques

*What I03 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I03 is the first macromolecular-crystallography (MX) beamline CORA has looked at, so its techniques are new Methods over the spine. Which enter scope is an open question (TECH-1); the function view below survives the eventual vocabulary choices.

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Rotation (oscillation) data collection | monochromatic, focused | `Eiger` (Detector Role) | new Method binding Goniometer + Eiger + SampleShutter, pending (TECH-1) |
| Grid scan / sample location | monochromatic, focused | `Eiger` + `OAV` | new Method over the Zebra/PandA fast grid scan, pending (TRIG-1, TECH-1) |
| Autonomous sample exchange | n/a | n/a | a Procedure over the spine + a Subject custody thread, pending (ROBOT-1) |
| Fluorescence / anomalous element ID | monochromatic | `FluorescenceDetector` (Sensor) | deferred until the detector is modelled (DET-1) |

A few points of intent shape the model:

- **MX data collection is a new Method, not a new Capability shape.** A rotation data collection sweeps the goniometer omega while the Eiger captures frames, gated by the fast sample shutter. The device Roles already exist (the graduated Goniometer presents Positioner, the Eiger presents Detector); what is new is the recipe binding them. The catalog tomography Methods do not fit (they bind RotaryStage + Camera + Scintillator, not Goniometer + Eiger), so MX earns its own Methods (TECH-1).
- **The autonomous loop is a Procedure plus Subject custody, not a device.** The unattended exchange (load pin, thaw, centre, collect, unmount, next) is the genuinely new and non-obvious part of MX automation. CORA expresses it as an orchestrated Procedure over the spine, threaded through the `Subject` aggregate (custody Received to mounted-on-goniometer to measured to Returned / Stored) and gated by a Clearance issued after a safety review. The robot itself is just a Positioner; the workflow is the modelling (ROBOT-1).
- **Energy change is a Method, not the dodal composite.** dodal couples the undulator and DCM through the `UndulatorDCM` composite, which owns no motors and is being retired upstream. CORA dissolves it into an `energy_change` Method binding the undulator gap and the DCM energy with the lookup-table perp/offset compensation (ENERGY-1).
- **Grid scan is a Method, not a device.** dodal exposes the fast grid scan only as devices (`ZebraFastGridScan`, `PandAFastGridScan`); CORA models the scan as a Method over the goniometer + detector driven by the timing hardware, not as an Asset (TRIG-1).

The concrete recipes (oscillation ranges, exposure, grid parameters, the exchange sequence) are calibration the deployment must supply. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who would act at I03, and the trust shape that would gate it. Design-phase.*

Governance at I03 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

I03 is the second beamline at the Diamond Site (after I22), so it reuses the Diamond facility envelope rather than creating a new one: the Diamond operator pool, the safety review structure, and the safety forms are facility-wide and inherited. I03 adds only its own beamline-bound principals, carried pending on the [Diamond Site page](../diamond/index.md). This is the same reuse pattern 7-BM follows at APS, the opposite of the new-Site work I22 did.

Because I03 is a modelling exercise, the concrete trust shape is not instantiated. What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the Diamond Site, not on the beamline, and the beamline links up to them. The Diamond PSS clearance is carried pending because its form names are not confirmed (PSS-1).

One governance shape is sharper at I03 than at the other deployments: **autonomous sample handling**. The sample-changing robot would run unattended, so its operation must be gated. Following the 19-BM precedent (ROBOT-1), CORA models this as a Clearance that must be Active before the robot may load, issued after a separate safety review of the changer. The robot is one Positioner-presenting Asset; the autonomy is governed by the Clearance, and the sample it carries is tracked as a `Subject` through a custody lifecycle, not as part of the device. None of that is built yet; the seam is reserved, not invented (ROBOT-1).

The off-roadmap question SCOPE-1 applies here as at I22: whether Diamond becomes a real CORA Site is unanswered. The concrete Zone, Conduit, and Policy instances, the operator pool, and the robot Clearance would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's I03 content lives, the one catalog Family it graduates (`Goniometer`), and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I03 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### The one catalog change: graduating Goniometer

I03 is the first Diamond deployment to earn a new catalog Family. The catalog had carried `Goniometer` as pending (documented, not yet defined). I03's `Smargon` is CORA's first canonical six-axis MX goniometer (omega / chi / phi rotation plus x / y / z sample-centring, with centre-of-rotation control), so it is the deployment that graduates Goniometer from pending to a defined Family. The Family stays a bare role-noun; chi-vs-kappa and axis-count variants are per-Asset settings or a bound Model, not Family splits. The per-axis decomposition and centre-of-rotation calibration are carried pending (GONIO-1).

### What is deliberately not here yet

- **New Capabilities / Methods and vendor Models.** I03 graduates Goniometer (an already-pending Family with a canonical instance) but earns no new Capabilities or Methods in this scaffold; the MX recipes are carried pending. No catalog Model is bound.
- **The robot as a Family.** An adversarial new-kind review refuted a `SampleChanger` Family: the robot is one Positioner-presenting Asset (the 19-BM / 32-ID position), with the sample a `Subject` and autonomy a Clearance. The robot's shape is deferred to ROBOT-1, not minted.
- **Integration scenarios.** No `test_i03_*.py` registers I03 Assets. Hard-registering a design-phase, off-roadmap beamline would commit speculative structure.
- **The endstation Assembly.** The goniometer + aperture-scatterguard + backlight + cryostream are carried flat; an MX-endstation Assembly (the 2-BM SampleTower analogue) is promoted only when a feature must act on the whole (ASSEMBLY-1).
- **Operations and experiment views.** A runbook for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the I03 team (and Diamond's documentation) to confirm before the model can be trusted.*

I03 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles at high confidence; it does not give the calibrated numbers, the hutch / PSS safety structure, the passive beam-path tier, or the Capability / Method binding. This page collects what dodal cannot supply. Each row is a fact the beamline team (or a Diamond drawing / the published I03 beamline paper) owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

As at I22, the EPICS PV prefix for every device is already recorded in the descriptor (the dodal dry fact), so wiring handles is not a question here. The questions are the layers above that, concentrated on the two new MX shapes: the goniometer and the autonomous sample-exchange robot.

### Scope and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I03 (or any Diamond beamline) actually intended to enter CORA scope, or is this a generalization exercise against an open controls source? | A generalization exercise: I03 graduates the Goniometer Family and stresses autonomous sample handling; it is not on the pilot roadmap. | Whether Diamond is a real Site or a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the optics and experiment hutches? | Both hutches exist with permit signals to be named; dodal does not carry them. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones (OP, MO, EA, DI), not the access-gated hutch or its safety meaning. | The standard Diamond MX optics + experiment hutch split. | The per-device Enclosure assignment. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the undulator energy range, period, minimum gap, harmonic, and gap-to-energy curve? dodal carries only the lookup-table path and harmonic ~3. | An undulator source with the dodal harmonic; energy range and curve are calibration to supply. | The `Undulator` parameters and the beamline energy range. |
| ENERGY-1 | Nice-to-have | dodal couples the undulator and DCM (the UndulatorDCM composite, itself being retired upstream). Should CORA model energy change as one Method binding the undulator gap + DCM energy + perp/offset compensation? | Yes: an `energy_change` Method over the two real Assets, not a device; the composite dissolves. | The energy-change seam shape. |
| OPT-1 | Nice-to-have | What are the mirror coating stripes and bimorph (22-channel) calibration, and the DCM crystal cut, d-spacing, and thermal model? dodal exposes the axes, the Si crystal, and the channel/temperature counts, not the calibrated settings. | The optic internals are per-Asset settings or a bound Model on the existing `Mirror` / `Monochromator` Families. | Which optic internals are modelled and where. |
| MACHINE-1 | Nice-to-have | How should the machine-level storage-ring state be modelled: a loose `StorageRing` source, an observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, reused from I22. | The machine-state modelling boundary. |

### Diagnostics and feedback

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIAG-1 | Blocks-go-live | The beam-position (QBPM) and flux (Flux, IPin) monitors bind the graduated Sensor Families; what beam-center calibration do they need? | The existing Sensor Role: beam position via the graduated `PositionMonitor` catalog Family (distinct from `FluxMonitor` by measuring position rather than flux), flux via the graduated `FluxMonitor` catalog Family (rule-of-three i22/i03/i15-1); beam-center is calibration to supply. | The beam-center calibration for the diagnostics. |
| FEEDBACK-1 | Nice-to-have | Is the XBPM feedback loop a modelled CORA construct, or floor (an EPICS control loop CORA observes but does not own)? | Floor: the feedback loop is not a CORA Asset; carried with its modelling deferred. | Whether the feedback loop is modelled or stays on the floor. |

### Sample and the autonomous loop

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | What are the Smargon axis details (omega / chi / phi + x / y / z, centre-of-rotation control, wrapped omega), and is the chi axis a mini-kappa? The Goniometer Family is graduated; the per-axis decomposition and CoR calibration are pending. | One `Goniometer` Asset with per-axis children; chi-vs-kappa and axis-count are settings, not Family splits; CoR is a calibration. | The goniometer per-axis Assets and CoR calibration. |
| ROBOT-1 | Blocks-go-live | What is the sample-changing robot, how is autonomous loading gated, and what is the Subject custody lifecycle (dewar / puck / pin queue)? | One Positioner-presenting Asset loading / unloading a `Subject`, gated by a Clearance that must be Active, vendor in a bound Model (the 19-BM ROBOT-1 shape); not a new Family. | The robot Asset, its Clearance gate, the Subject custody thread, and the autonomous loop. |
| ENV-1 | Blocks-go-live | Must CORA command the sample-environment setpoints (the cryostream temperature, the thawer), or only read them back? | The settable-actuator shape is now settled: both bind the graduated `TemperatureController` Family (presents `Regulator`, requires `Settable`). What is open is whether CORA commands the setpoints. | The command-vs-read decision. |
| ASSEMBLY-1 | Nice-to-have | Should the goniometer + aperture-scatterguard + backlight + cryostream compose an MX-endstation Assembly (the analogue of 2-BM's SampleTower), and is the cryostream inside it or co-located? | Carried flat in this scaffold; an Assembly is promoted only when a feature must act on the whole. | The endstation `parent_id` grouping. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | What are the Eiger threshold energy and beam-center, the detector-translation axis ranges, and how is the retractable fluorescence detector (and the sample backlight) modelled? | The Eiger reuses `Camera`; the fluorescence detector presents Sensor (loose); the backlight binds the catalog `Backlight` Family; calibration to supply. | The detector calibration and the loose fluorescence modelling. |

### Techniques, triggering, identity

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Which MX Capabilities and Methods are in scope (rotation data collection binding Goniometer + Eiger + Shutter; grid scan; OAV pin-tip centring), and are they new Capabilities or Methods under existing ones? | New Methods over the spine, carried pending on the [Diamond Practices](../diamond/index.md); the catalog tomography Methods do not fit MX as-is. | Which Capabilities and Methods the catalog earns. |
| TRIG-1 | Nice-to-have | How do the Zebra and PandABox bind to the goniometer, detector, and shutter, and is the fast grid scan a Method (not a device)? dodal exposes grid scan only as devices. | One or two `TimingController` devices carry the scheme; the fast grid scan is a Method / Plan, not a device. | The triggering binding and the grid-scan modelling. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags) for the devices? dodal carries none. | Assets carry no part / serial identity until supplied. | The Asset hardware-identity fields. |
