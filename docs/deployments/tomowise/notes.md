# Notes

## Techniques

*What TomoWISE is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../maxiv/index.md#the-techniques-adapted-here) is how a facility adapts it. TomoWISE is pre-build, so the techniques below are design intent: the MAX IV Practices that will bind them are carried pending on the [MAX IV site page](../maxiv/index.md#the-techniques-adapted-here). The function view survives the eventual equipment choices, which is why it can be written before the hardware is procured.

The beamline's five operation modes (TDR) select the source, filtering, monochromator, and KB optics for a given technique:

| Technique | Source | Monochromator | KB | What it is for |
| --- | --- | --- | --- | --- |
| Standard microtomography | CPMU14 | MLM | no | high-throughput monochromatic CT |
| High-speed microtomography (small FOV) | CPMU14 | MLM or none | no | sub-micron pixel, fast dynamics |
| Large-FOV / white-beam microtomography | 3T3PW | none | no | large or highly attenuating samples |
| Nanotomography | CPMU14 | MLM | yes | 200-nm-class cone-beam imaging |
| Laminography | CPMU14 | MLM | no | flat, extended samples (tilt axis, not a separate fixture) |

A few points of intent shape the model:

- **Source switching is first-class.** Two insertion devices (one `InsertionDevice` Family, two Assets) are selected per mode, unlike the single bending-magnet source at 2-BM. The mode determines which is in the beam.
- **Laminography is a tilt setpoint, not a separate station.** It runs on the microtomography endstation's tilt axis, mirroring the 2-BM laminography decision: the same installed stack, a different Method, not a new Fixture.
- **Monochromatic and white-beam are the same beamline.** Inserting or bypassing the MLM (and the filter chain) picks the spectrum; it is an operation mode over one set of optics, not two beamlines.

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join as the beamline approaches commissioning. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who will act at TomoWISE, and the trust shape that will gate it. Design-phase.*

Governance at TomoWISE follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [MAX IV Site](../maxiv/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

TomoWISE is pre-build, so this shape is not yet instantiated. The MAX IV operator and safety-review structure is still being defined and is carried pending on the [MAX IV site page](../maxiv/index.md#safety-and-governance); CORA does not invent a MAX IV operator pool or review chain ahead of confirmation.

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the MAX IV Site, not on the beamline, and the beamline links up to them rather than restating them. The MAX IV safety-form names themselves are an open question (PSS-1 on [Open questions](#open-questions)).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the beamline approaches commissioning, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's TomoWISE content lives, the cross-facility `Microscope` / `Optics` Assemblies it reuses with 2-BM, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at TomoWISE |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What is deliberately not here yet

- **Integration scenarios.** No `test_tomowise_*.py` registers TomoWISE Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** Only one catalog Model is bound: `optique_peter_micrx080` on the microscope Housings (reused from 2-BM, pending confirmation, DET-2). The remaining "(target)" models in the TDR are [open questions](#open-questions), not bindings, because part numbers are not yet procured.
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies (done).** The two microscopes now compose the cross-facility `Microscope` / `Optics` Assemblies that 2-BM uses (Housing-anchored: turret + objectives + selector over a scintillator), rather than a loose family. The catalog assembly was generalized (`camera` and `propagation_distance` made `ZeroOrOne`) so TomoWISE can share its four cameras and the one gantry propagation rail across both microscopes. This also removed the prior name collision between the loose `Microscope` family and the catalog `Microscope` Assembly. What remains deferred is the integration scenario that registers the Fixture (slot -> Asset bindings) and a standalone fixture page; both wait until the design firms.

## Open questions

*What CORA needs the TomoWISE team to confirm before the model can be trusted.*

TomoWISE is in the design phase, so this page is long by design: almost every value on the [device pages](index.md) is a TDR design specification, not a commissioned measurement. Each row below is a fact the beamline team or the TDR owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the Tango/Sardana device and attribute names for each device? | Control handles are unassigned; CORA leaves the device handle empty (no EPICS PV). | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-build | What are the PSS permit signals and access-interlock names for the optics and experiment hutches? | Both hutches exist with permit signals to be named. | The Enclosure permit signals. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Nice-to-have | Which MLM coating is selected? The TDR text lists W/SiC or W/B4C; Table 8.3 lists W/Si. | The MLM is one Monochromator Asset; coating is a setting. | The MLM coating setting. |
| LAYOUT-1 | Nice-to-have | What is the single z-coordinate reference for the layout? The TDR mixes "from the CPMU14 source" (front end) and "from the straight-section centre" (optics and downstream), about 505 mm apart. | z values are carried as approximate from-source and flagged confirm. | Exact device z positions. |

### Endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| NANO-1 | Blocks-go-live | Are the nanotomography sample-manipulator model bindings final? The TDR specifies the six-axis stack in Table 9.5 (tilt, coarse X/Y/Z, continuous rotary, fine Xs/Zs); only the per-axis model procurement remains. | The TDR-specified stack, reusing the micro-endstation Families, with a "(target)" model per axis carried unbound. | The nanotomography stage Model bindings. |
| STAGE-1 | Blocks-go-live | Is the rotary stage the Lab Motion Systems RT100AX, and are its specs final? | The "(target)" RT100AX, used as the trigger master clock. | The rotary stage Model binding. |
| STAGE-2 | Nice-to-have | Is the sample positioning stage the Lab Motion Systems XY150B-12? | The "(target)" XY150B-12. | The sample positioning Model binding. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which camera models will be procured for cameras I to IV? (Chosen in project year 2.) | Four cameras at the stated design-target sensors/speeds; models unbound. | The camera Model bindings. |
| DET-2 | Blocks-go-live | Confirm the microscope optics model. Each Housing binds the 2-BM candidate `optique_peter_micrx080`; the TDR names only the vendor (Optique Peter), so confirm this model or name the procured alternative (project year 2). | Two microscopes (MicLFOV, MicHR) composed as `Microscope` Assemblies, Housing model bound to `optique_peter_micrx080` pending confirmation. | The microscope Model confirmation. |
| TRIG-1 | Blocks-go-live | Will the rotary TTL (3600 pulses/rev) feed the camera triggers directly, or is an FPGA conditioner needed? | Direct TTL, no conditioner; may evolve once camera trigger requirements are firm. | The trigger/sync chain. |
