# Notes

## Techniques

*What I11 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I11 does high-resolution powder diffraction, a new science domain for CORA. Which Methods enter scope is an open question (TECH-1).

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| High-resolution powder diffraction | monochromatic (DCM) | `Mythen3` strip detector on the two-theta arm, capillary `Spinner` for averaging | new Capability, pending (TECH-1) |
| Variable-temperature powder diffraction | monochromatic | same, over a temperature ramp on the thermal actuators | the variable-temperature axis that earns TemperatureController (TEMP-1) |
| Autonomous sample exchange | n/a | n/a | a Procedure over the spine + a Subject custody thread, pending (ROBOT-1) |

A few points of intent shape the model:

- **Powder diffraction is a new Capability, not a new device shape.** A measurement spins a capillary sample for powder averaging and sweeps the detector arm while the Mythen3 strip captures the diffraction pattern. The device Roles already exist (the diffractometer and spinner present Positioner, the Mythen3 presents Detector); what is new is the science Capability binding them (TECH-1).
- **Variable temperature is the genuinely new operating axis, and it earns an abstraction.** Powder diffraction at I11 routinely runs over a temperature ramp using the Cyberstar/Eurotherm blowers and the cryostreams. These are continuous-setpoint actuators (`set(value)`/`ramprate`), the first such cluster CORA has at rule-of-three. That earned the `TemperatureController` Family graduation and the `Regulator` Role, which landed via gate-review (TEMP-1).
- **The diffractometer is not goniometry.** Unlike I03's MX goniometer (a sample-orientation cradle, the graduated Goniometer Family), I11's theta/two_theta/delta are a sample rotation plus detector-arm angles, modelled as per-axis RotaryStage (GONIO-1).

The concrete recipes (two-theta ranges, exposure, temperature ramps) are calibration the deployment must supply. See [Open questions](#open-questions).

## Governance

*Who would act at I11, and the trust shape that would gate it. Design-phase.*

Governance at I11 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take, gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the command surfaces, and Policies).

I11 is the fourth beamline at the Diamond Site (after I22, I03, and I15-1), so it reuses the Diamond facility envelope: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited. I11 adds only its own beamline-bound principals, carried pending on the [Diamond Site page](../diamond/index.md).

Two governance notes at I11:

- **Autonomous sample loading is gated by a Clearance.** Like I03, the sample-changing robot + carousel would run unattended, so its operation is gated by a Clearance that must be Active, issued after a safety review; the robot is one Positioner Asset and the sample it carries is a `Subject` (ROBOT-1).
- **The TemperatureController earn touched governed vocabulary.** I11 was the rule-of-three that earned graduating the `TemperatureController` Family and a new settable-actuator Role. Because a new Role is a code change to a core BC aggregate (`SEED_ROLES`), that change was routed through the gate-review panel (3 baseline + specialist reviewers) rather than slipped into this scaffold (TEMP-1), and has since landed: `TemperatureController` is a catalog Family presenting the `Regulator` Role. The scaffold cadence stayed clean; the core-vocabulary change got its proper governance.

Because I11 is a modelling exercise, the concrete Zone, Conduit, and Policy instances are not instantiated; the off-roadmap question SCOPE-1 applies as at the other Diamond beamlines. They would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's I11 content lives, the settable-continuous-setpoint actuator Role it earns, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I11 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### The earn, and why it is not in this PR

I11 is the deployment that genuinely earns an abstraction CORA has deferred since 7-BM: a **settable-continuous-setpoint actuator**. Its four thermal actuators (two Cyberstar/Eurotherm blowers, two Oxford cryostreams) are `Locatable[float]` with `set(value)`/`setpoint`/`ramprate`/PID. After the loose `TemperatureController` family was carried at I22 and I03, I11 is the rule-of-three.

That earns two things:

1. **Graduating the `TemperatureController` Family** (catalog `families:` add, like I03's Goniometer).
2. **A new settable-continuous-setpoint actuator Role** (CORA had none at the time: Positioner is spatial, Controller supervises, GenericProbe is read-only).

The Role was a **code change** to `cora.equipment.aggregates.role.SEED_ROLES`, which is drift-guarded by an exact-match test (`test_roles_match_seed_roles`), and is core cross-facility vocabulary. Per the gate-review discipline, that did not belong in a families-only scaffold PR; it was routed to a **separate, gate-reviewed change** (TEMP-1). Graduating the Family is coupled to the Role (a `TemperatureController` Family presenting a non-existent Role would be hollow), so both landed together in that change: `TemperatureController` is now a catalog Family presenting the new `Regulator` Role. This scaffold carried the actuators loose, as I22 and I03 did, and recorded the trigger.

### What is deliberately not here yet

- **The TemperatureController graduation + `Regulator` Role**: not part of this families-only scaffold; landed via the gate-reviewed follow-up (TEMP-1).
- **New Capabilities / Methods and vendor Models.** The powder-diffraction Method is carried pending; no Model is bound.
- **The robot as a Family.** It presents the existing Positioner Role; shape deferred (ROBOT-1).
- **Integration scenarios.** No `test_i11_*.py` registers I11 Assets.
- **Operations and experiment views.** See the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the I11 team (and Diamond's documentation) to confirm before the model can be trusted.*

I11 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles; it does not give the calibrated numbers, the hutch / PSS safety meaning, or the Capability / Method binding. This is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Scope and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I11 (or any Diamond beamline) actually intended to enter CORA scope, or is this a generalization exercise? | A generalization exercise; not on the pilot roadmap. | Whether Diamond is a real Site or a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the two hutches? | Both hutches exist; permit signals to be named. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones, not the access-gated hutch. | The standard optics + experiment hutch split. | The per-device Enclosure assignment. |

*(TEMP-1, the thermal earn, is resolved: i11's four continuous-setpoint actuators triggered graduating the `TemperatureController` catalog Family and adding the `Regulator` Role with the `Settable` affordance, landed via a gate-reviewed change.)*

### Source, optics, diffractometer

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What is the I11 source and its energy range? dodal does not pin it (the Synchrotron device is facility-wide, observe-only). | A source carried `confirm`; energy range is calibration to supply. | The source and beamline energy range. |
| OPT-1 | Nice-to-have | What are the DCM crystal d-spacing and thermal model? dodal exposes the axes and the Si(111) default, not the calibrated values. | Settings / a bound Model on the existing Monochromator Family. | The mono calibration. |
| MACHINE-1 | Nice-to-have | How should the storage-ring state be modelled: loose `StorageRing`, observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, reused from I22. | The machine-state modelling boundary. |
| GONIO-1 | Nice-to-have | Is the diffractometer (theta / two_theta / delta) correctly modelled as per-axis `RotaryStage` (not the I03-graduated `Goniometer`)? | Yes: theta is a sample rotation and two_theta / delta are detector-arm angles, not an MX orientation cradle. | That the diffractometer stays RotaryStage, not Goniometer. |
| DIFF-1 | Blocks-go-live | What are the diffractometer axis PVs and ranges (the dodal class was not read axis-by-axis), and the detector-arm geometry? | Per-axis RotaryStage under a DiffractometerStage Assembly; axes to confirm. | The diffractometer per-axis Assets and geometry. |
| SPIN-1 | Nice-to-have | Is the capillary spinner correctly a `RotaryStage` (a sample-rotation device for powder averaging), and what speed range? | Yes, a RotaryStage; speed is calibration. | The spinner modelling and speed range. |

### Detector, robot, technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MYTHEN-1 | Blocks-go-live | How is the Mythen3 (a 1D position-sensitive strip detector) modelled: reuse `Camera` (Detector Role), or does a strip / PSD warrant a distinct shape? And what are its threshold / deadtime values? It is skip-flagged in dodal (issue I11-916). | Reuse `Camera` / Detector Role, with the strip-vs-2D nuance noted; calibration to supply. | The strip-detector Role choice and calibration. |
| ROBOT-1 | Blocks-go-live | What is the sample-changing robot + carousel, how is autonomous loading gated, and what is the sample custody lifecycle? | One Positioner-presenting Asset loading / unloading a `Subject`, gated by a Clearance, vendor in a bound Model (the I03 / 19-BM shape); not a new Family. | The robot Asset, its Clearance gate, and the Subject custody thread. |
| TECH-1 | Blocks-go-live | What is the powder-diffraction Capability and its Methods (binding the diffractometer + Mythen3 + spinner, often over a temperature ramp)? | A new powder-diffraction Capability not yet in the catalog, carried pending on the [Diamond Practices](../diamond/index.md). | Which Capabilities and Methods the catalog earns. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags)? dodal carries none. | Assets carry no part / serial identity until supplied. | The Asset hardware-identity fields. |
