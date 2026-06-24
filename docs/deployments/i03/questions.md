# Open questions

*What CORA needs the I03 team (and Diamond's documentation) to confirm before the model can be trusted.*

I03 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles at high confidence; it does not give the calibrated numbers, the hutch / PSS safety structure, the passive beam-path tier, or the Capability / Method binding. This page collects what dodal cannot supply. Each row is a fact the beamline team (or a Diamond drawing / the published I03 beamline paper) owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

As at I22, the EPICS PV prefix for every device is already recorded in the descriptor (the dodal dry fact), so wiring handles is not a question here. The questions are the layers above that, concentrated on the two new MX shapes: the goniometer and the autonomous sample-exchange robot.

## Scope and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I03 (or any Diamond beamline) actually intended to enter CORA scope, or is this a generalization exercise against an open controls source? | A generalization exercise: I03 graduates the Goniometer Family and stresses autonomous sample handling; it is not on the pilot roadmap. | Whether Diamond is a real Site or a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the optics and experiment hutches? | Both hutches exist with permit signals to be named; dodal does not carry them. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones (OP, MO, EA, DI), not the access-gated hutch or its safety meaning. | The standard Diamond MX optics + experiment hutch split. | The per-device Enclosure assignment. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the undulator energy range, period, minimum gap, harmonic, and gap-to-energy curve? dodal carries only the lookup-table path and harmonic ~3. | An undulator source with the dodal harmonic; energy range and curve are calibration to supply. | The `Undulator` parameters and the beamline energy range. |
| ENERGY-1 | Nice-to-have | dodal couples the undulator and DCM (the UndulatorDCM composite, itself being retired upstream). Should CORA model energy change as one Method binding the undulator gap + DCM energy + perp/offset compensation? | Yes: an `energy_change` Method over the two real Assets, not a device; the composite dissolves. | The energy-change seam shape. |
| OPT-1 | Nice-to-have | What are the mirror coating stripes and bimorph (22-channel) calibration, and the DCM crystal cut, d-spacing, and thermal model? dodal exposes the axes, the Si crystal, and the channel/temperature counts, not the calibrated settings. | The optic internals are per-Asset settings or a bound Model on the existing `Mirror` / `Monochromator` Families. | Which optic internals are modelled and where. |
| MACHINE-1 | Nice-to-have | How should the machine-level storage-ring state be modelled: a loose `StorageRing` source, an observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, reused from I22. | The machine-state modelling boundary. |

## Diagnostics and feedback

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIAG-1 | Blocks-go-live | How are the beam-position (QBPM) and flux (Flux, IPin) monitors modelled: the loose `Diagnostic` / `FluxMonitor` Sensor families, and what beam-center calibration do they need? | The existing Sensor Role, carried as the loose families reused from 2-BM (Diagnostic) and I22 (FluxMonitor); beam-center is calibration to supply. | The diagnostics modelling boundary and beam-center. |
| FEEDBACK-1 | Nice-to-have | Is the XBPM feedback loop a modelled CORA construct, or floor (an EPICS control loop CORA observes but does not own)? | Floor: the feedback loop is not a CORA Asset; carried with its modelling deferred. | Whether the feedback loop is modelled or stays on the floor. |

## Sample and the autonomous loop

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | What are the Smargon axis details (omega / chi / phi + x / y / z, centre-of-rotation control, wrapped omega), and is the chi axis a mini-kappa? The Goniometer Family is graduated; the per-axis decomposition and CoR calibration are pending. | One `Goniometer` Asset with per-axis children; chi-vs-kappa and axis-count are settings, not Family splits; CoR is a calibration. | The goniometer per-axis Assets and CoR calibration. |
| ROBOT-1 | Blocks-go-live | What is the sample-changing robot, how is autonomous loading gated, and what is the Subject custody lifecycle (dewar / puck / pin queue)? | One Positioner-presenting Asset loading / unloading a `Subject`, gated by a Clearance that must be Active, vendor in a bound Model (the 19-BM ROBOT-1 shape); not a new Family. | The robot Asset, its Clearance gate, the Subject custody thread, and the autonomous loop. |
| ENV-1 | Blocks-go-live | Must CORA command the sample-environment setpoints (the cryostream temperature, the thawer), or only read them back? | The settable-actuator shape is now settled: both bind the graduated `TemperatureController` Family (presents `Regulator`, requires `Settable`). What is open is whether CORA commands the setpoints. | The command-vs-read decision. |
| ASSEMBLY-1 | Nice-to-have | Should the goniometer + aperture-scatterguard + backlight + cryostream compose an MX-endstation Assembly (the analogue of 2-BM's SampleTower), and is the cryostream inside it or co-located? | Carried flat in this scaffold; an Assembly is promoted only when a feature must act on the whole. | The endstation `parent_id` grouping. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | What are the Eiger threshold energy and beam-center, the detector-translation axis ranges, and how is the retractable fluorescence detector (and the sample backlight) modelled? | The Eiger reuses `Camera`; the fluorescence detector presents Sensor (loose); the backlight is a loose `Backlight` family; calibration to supply. | The detector calibration and the loose fluorescence / backlight modelling. |

## Techniques, triggering, identity

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Which MX Capabilities and Methods are in scope (rotation data collection binding Goniometer + Eiger + Shutter; grid scan; OAV pin-tip centring), and are they new Capabilities or Methods under existing ones? | New Methods over the spine, carried pending on the [Diamond Practices](../diamond/index.md); the catalog tomography Methods do not fit MX as-is. | Which Capabilities and Methods the catalog earns. |
| TRIG-1 | Nice-to-have | How do the Zebra and PandABox bind to the goniometer, detector, and shutter, and is the fast grid scan a Method (not a device)? dodal exposes grid scan only as devices. | One or two `TimingController` devices carry the scheme; the fast grid scan is a Method / Plan, not a device. | The triggering binding and the grid-scan modelling. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags) for the devices? dodal carries none. | Assets carry no part / serial identity until supplied. | The Asset hardware-identity fields. |
