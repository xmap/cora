# Notes

## Techniques

*What I15-1 is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../diamond/index.md) is how a facility adapts it. I15-1 does total scattering / pair distribution function (PDF), a new science domain for CORA. Which Methods enter scope is an open question (TECH-1).

| Technique | Beam | Detector | Status in CORA |
| --- | --- | --- | --- |
| Total scattering / PDF | fixed-energy, bent-Laue mono | `Eiger` (Detector Role), wide-Q on the two-theta arm | new Capability, pending (TECH-1) |
| Autonomous powder/capillary exchange | n/a | n/a | a Procedure over the spine + a Subject custody thread, pending (ROBOT-1) |

A few points of intent shape the model:

- **Total scattering is a new Capability, not a new device shape.** A PDF measurement captures wide-Q scattering on the Eiger across the two-theta arm at a fixed high energy. The device Roles already exist (Camera presents Detector, the mono and arm present Positioner); what is new is the science Capability binding them. Carried pending on the [Diamond Practices](../diamond/index.md) (TECH-1).
- **Energy scanning is explicitly NOT in scope here.** I15-1's bent-Laue monochromator selects a fixed energy: dodal exposes `energy_kev` as a read-only readback derived from the crystal y position via a lookup table, not a commanded or swept axis. So the pending `energy_scan` Capability is **not** earnable from I15-1's source; it must wait for a tunable XAS/EXAFS beamline whose scanning monochromator is actually instantiated in dodal (ENERGY-1).
- **The autonomous loop reuses the I03 shape.** The powder/capillary robot exchange is a Procedure over the spine threaded through the `Subject` aggregate and gated by a Clearance, the same shape as the I03 MX loop, with a powder/capillary twist instead of MX pins (ROBOT-1).

The concrete recipes (q-ranges, exposure, the exchange sequence) are calibration the deployment must supply. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who would act at I15-1, and the trust shape that would gate it. Design-phase.*

Governance at I15-1 follows the same model as the CORA pilots: people and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md), and on the beamline they surface through the actions they take, gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the command surfaces, and Policies).

I15-1 is the third beamline at the Diamond Site (after I22 and I03), so it reuses the Diamond facility envelope: the operator pool, the safety review structure, and the safety forms are facility-wide and inherited. I15-1 adds only its own beamline-bound principals, carried pending on the [Diamond Site page](../diamond/index.md).

Two governance points are worth noting at I15-1:

- **The interlocks are governance data, not equipment.** dodal exposes a PSS hutch interlock and a goniometer interlock. CORA does not model these as Assets: an interlock is the read-only permit behind the **Enclosure** aggregate (the shipped Enclosure BC), so it is carried as the Enclosure `permit_signal`, mutated by the safety system, not by CORA (INTERLOCK-1). dodal even gives real interlock PVs here (unlike I22 / I03), carried as the permit-signal candidates pending confirmation (PSS-1).
- **Autonomous sample loading is gated by a Clearance.** Like I03, the powder/capillary robot would run unattended, so its operation is gated by a Clearance that must be Active, issued after a safety review; the robot is one Positioner Asset and the sample it carries is a `Subject` (ROBOT-1).

Because I15-1 is a modelling exercise, the concrete Zone, Conduit, and Policy instances are not instantiated; the off-roadmap question SCOPE-1 applies as at I22 / I03. They would land if the beamline approaches real scope, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's I15-1 content lives, why it adds no catalog kinds and reinforces the existing model, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I15-1 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Why I15-1 adds no catalog kinds

I15-1 was picked partly expecting it to graduate the open settable-actuator affordance from its `SafeOrBeamPositioner` sample-environment devices. A source-level adversarial eval **refuted that**, and the refutation is the modelling content of this deployment:

- **`SafeOrBeamPositioner` folds into Positioner.** It is a `Movable` that drives a motor to two named positions (SAFE / BEAM), which is the existing Positioner Role with Indexable named positions, not a new affordance. It is also **not** a `TemperatureController`: the dodal classes are named for temperature controllers (blower / cobra / cryostream) but model only the in/out-of-beam move, so calling them `TemperatureController` would mirror the class name rather than the behaviour (intentional-modelling-not-mirroring). Modelled as `LinearStage` + Positioner / Indexable (SAFEBEAM-1).
- **The `rail` folds into Table** (the TomoWISE DetectorGantry precedent), not a new `Rail` Family (RAIL-1).
- **The interlocks fold into the Enclosure permit**, not an equipment Family (INTERLOCK-1).

So I15-1 is a reuse + reinforce deployment: it provides the third `FluxMonitor` deployment that completed its rule-of-three graduation into the catalog, and adds a third robot-as-Positioner instance, while coining no new vocabulary of its own. That is a result, not a gap: the value is confirming the existing model absorbs a new technique cleanly.

### What is deliberately not here yet

- **New Capabilities / Methods and vendor Models.** The total-scattering Method is carried pending; no Model is bound.
- **The robot as a Family.** It presents the existing Positioner Role; shape deferred (ROBOT-1).
- **Integration scenarios.** No `test_i15_1_*.py` registers I15-1 Assets.
- **Operations and experiment views.** A runbook for an unmodelled beamline would be invention; see the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the I15-1 team (and Diamond's documentation) to confirm before the model can be trusted.*

I15-1 is modelled from Diamond's open [`dodal`](https://github.com/DiamondLightSource/dodal) controls library, treated as a dry, correct DATA source. dodal gives the device shape and the EPICS PV handles; it does not give the calibrated numbers, the hutch / PSS safety meaning, or the Capability / Method binding. This is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Scope, safety, and the modelling decisions

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is I15-1 (or any Diamond beamline) actually intended to enter CORA scope, or is this a generalization exercise? | A generalization exercise; not on the pilot roadmap. | Whether Diamond is a real Site or a modelling fixture. |
| PSS-1 | Blocks-build | What are the Diamond PSS search-and-secure permit signals for the two hutches? dodal records interlock readbacks (BL15I-PS-IOC-02:M11:LOP, BL15I-VA-OMRON-01:INT3:ILK) but not confirmed permits. | Both hutches exist; the dodal interlock readbacks are permit-signal candidates. | The Enclosure permit signals. |
| ENC-1 | Blocks-build | Which hutch does each device sit in? dodal PV prefixes encode functional zones, not the access-gated hutch. | The standard optics + experiment hutch split. | The per-device Enclosure assignment. |
| INTERLOCK-1 | Nice-to-have | Are the PSS / gonio interlocks correctly modelled as the Enclosure `permit_signal` (not as equipment devices)? | Yes: an interlock is the read-only permit behind the Enclosure aggregate, not an Asset. | That interlocks stay on the Enclosure, not the device walk. |
| SAFEBEAM-1 | Blocks-go-live | Are the blower / cobra / cryostream correctly modelled as Positioner + Indexable SAFE/BEAM (not TemperatureController), and is the cobra/cryostream rail-interchange a Fixture-style swap or an Assembly? | Positioner with two named positions; the interchange is a Fixture-style swap (they share the ENV:X rail motor). | The sample-environment actuator shape and the exchange modelling. |
| RAIL-1 | Nice-to-have | Is the rail correctly the existing Table Family, and what are its exchange semantics? | The existing Table Family (the TomoWISE DetectorGantry precedent), not a new Rail kind. | The rail Family and exchange shape. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What is the I15-1 source (it is a branch line) and its energy range? dodal does not pin it. | A source carried `confirm`; energy range is calibration to supply. | The source and beamline energy range. |
| ENERGY-1 | Blocks-go-live | Is the bent-Laue energy ever a goto-command (driving y to hit a target energy via inverse lookup), or only the fixed-selection read-only readback dodal exposes? | A read-only y-to-energy lookup readback; the pending energy_scan Capability is NOT earnable here. | Whether energy is a commandable axis and whether energy_scan applies. |
| OPT-1 | Nice-to-have | What are the bent-Laue crystal lookup table, the multilayer mirror coating, and the attenuator transmission-vs-foil table? dodal exposes the axes, not the calibrated values. | The optic internals are settings / a bound Model / a Calibration on the existing Families. | The optic calibration. |
| MACHINE-1 | Nice-to-have | How should the storage-ring state be modelled: loose `StorageRing`, observe-only `GenericProbe`, or a facility-shared read model? | A loose `StorageRing` family bound observe-only, reused from I22. | The machine-state modelling boundary. |
| ATTN-1 | Nice-to-have | Are the ATTN-01 three-stick stage and the ATTN-02 transmission selector two physically distinct attenuator stations, or two control surfaces of one unit? | Two distinct stations (separate EPICS roots), the selector folding into Filter via Indexable named positions. | The attenuator station topology. |

### Sample, detector, technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FLUX-1 | Blocks-go-live | How is the incident-flux monitor (the JBPM TetrAMM i0) modelled, and what beam-center calibration does it need? | The existing Sensor Role, via the `FluxMonitor` catalog Family (graduated on the i22/i03/i15-1 rule-of-three this deployment completes). | The flux-monitor modelling and beam-center. |
| ROBOT-1 | Blocks-go-live | What is the powder/capillary sample-changing robot, how is autonomous loading gated, and what is the puck custody lifecycle? | One Positioner-presenting Asset loading / unloading a `Subject`, gated by a Clearance, vendor in a bound Model (the I03 / 19-BM shape); not a new Family. | The robot Asset, its Clearance gate, and the Subject custody thread. |
| DET-1 | Blocks-go-live | What are the Eiger threshold energy and beam-center, the two-theta arm geometry, and the second detector translation ranges? | The Eiger reuses `Camera`; calibration to supply. | The detector calibration and arm geometry. |
| TECH-1 | Blocks-go-live | What are the total-scattering / PDF Capability and Methods (binding the mono + Eiger + two-theta arm + the powder robot exchange)? | A new total-scattering Capability not yet in the catalog, carried pending on the [Diamond Practices](../diamond/index.md). | Which Capabilities and Methods the catalog earns. |
| ID-1 | Nice-to-have | What are the hardware identities (serial numbers, asset tags)? dodal carries none. | Assets carry no part / serial identity until supplied. | The Asset hardware-identity fields. |
