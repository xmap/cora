# Notes

## Techniques

*What 19-BM is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 19-BM is pre-build, so the techniques below are design intent: the APS Practices that will bind them are carried pending on the [APS site page](../aps/index.md#the-techniques-adapted-here). The function view survives the eventual equipment choices, which is why it can be written before the hardware is procured.

19-BM is a single-mode beamline: filtered white-beam tomography. There is no monochromator and no mirror, so unlike 2-BM there is no beam-mode or energy-change technique. The beam spectrum is set by selecting filters in the F3-30 unit, and the science variety is in the acquisition cadence, not the optics.

| Technique | Catalog Method | What it is for |
| --- | --- | --- |
| Filtered white-beam tomography | `tomography` | the standard micron-resolution CT scan |
| Continuous-rotation tomography | `continuous_rotation_tomography` | high-throughput acquisition, the autonomous workhorse |
| Streaming tomography | `streaming_tomography` | live reconstruction feedback |
| Dark / flat fields | `dark_field`, `flat_field` | the reference frames every reconstruction needs |
| First light | `first_light` | commissioning the beam onto the detector |

A few points of intent shape the model:

- **Autonomy and throughput are the point.** 19-BM is built to run unattended at a high scan cadence with a robotic sample changer feeding it. The technique layer is ordinary tomography; what is distinctive is the autonomous operation around it (see [Governance](#governance)) and the sample-exchange loop (see [Sample](sample.md)).
- **Spectrum is set by filtering, not optics.** Selecting Si / Ge / Cu filters in the F3-30 unit hardens or softens the white-beam spectrum. This replaces the energy-selection techniques 2-BM has, which depend on its monochromator.
- **Single beam mode.** There is one set of optics and one mode, so there is no beam-mode-change technique to model.

The concrete acquisition recipes (scan sequences, exposure, filter choices) are not written yet; they join as the beamline approaches commissioning. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who will act at 19-BM, and the trust shape that will gate it. Design-phase.*

Governance at 19-BM follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

19-BM is pre-build, so this shape is not yet instantiated. The concrete Zone, Conduit, and Policy instances, and the 19-BM operator pool, land when the beamline approaches commissioning, following the [2-BM governance](../2-bm/governance.md) shape. The APS clearances (the safety forms that must be active to start) are issued at the APS Site, not on the beamline, and the beamline links up to them.

### Autonomy is first-class here

19-BM is "Fast Autonomous Computed Tomography": running unattended at a high scan cadence with a robotic sample changer is the reason the beamline exists. That makes it the deployment where CORA's supervisory agents are intended to go from seeded-but-dormant to operational. The agents are already facility principals at APS, carried pending on the [APS site page](../aps/index.md#safety-and-governance):

- The `RunSupervisor` watches a running scan and can hold it; 19-BM is where that supervision is expected to be enabled and to climb from observe-and-advise toward holding and truncating stalled runs.
- The autonomous loop also needs a way to **start** runs without an operator (queue the next sample, start its scan), which the spine does not yet expose to an agent. 19-BM is the forcing case for that capability; it is a design question, not a copy from 2-BM.

Like every agent in CORA, these act only by issuing a command the spine already exposes, through the same authorized path a person uses. None of this is built yet; 19-BM reserves the seam.

### The robotic sample changer gate

The robotic sample changer requires a separate safety review before implementation (recorded in the FDR). In CORA terms that review issues a Clearance that must be Active before the changer may operate, so autonomous loading cannot start until the review is on file. The changer Asset, its Clearance gate, and the autonomous loading flow are carried as an [open question](#open-questions) (ROBOT-1) until the design and the review land.

## Model

*The developer's by-kind index: where each CORA aggregate's 19-BM content lives, a second BM beamline that reuses the families 2-BM established and coins none of its own, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 19-BM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What is deliberately not here yet

- **Integration scenarios.** No `test_19bm_*.py` registers 19-BM Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, moving-target beamline would commit speculative structure. It lands when the design firms and the team approves.
- **Vendor Models.** No catalog Model is bound: the sample stages, the detector hardware, and the robotic changer are all procured after the FDR and are carried as [open questions](#open-questions), not bindings.
- **New catalog Families.** 19-BM coins none of its own. The two passive families it pushed past the rule-of-three threshold (`Window`, with two more Be windows; `Collimator`, with two more Pb collimators) have since been promoted to catalog Families under the passive beam-path tier; 19-BM's windows and collimators now bind them.
- **The autonomy build.** The `RunSupervisor` enablement and the missing run-start capability that 19-BM's autonomous operation needs are real CORA work, not documentation; see [Governance](#governance). They land as their own slices.
- **The robotic sample changer.** Deferred behind its separate safety review (ROBOT-1).
- **Operations and experiment views.** A runbook and live experiment view for an unbuilt beamline would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the 19-BM team to confirm before the model can be trusted.*

19-BM is in the design phase, so almost every value on the [device pages](index.md) is a Final Design Report specification, not a commissioned measurement. Each row below is a fact the beamline team or the FDR owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the EPICS PV names for each device, and does 19-BM follow the 2-BM TomoScan / MCTOptics IOC layout? | Control handles are unassigned; CORA leaves each device handle empty (no PV) until the control system is up. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-build | What are the PSS permit signals and access-interlock names for 19-BM-A, 19-BM-C, and 19-BM-D? | Each enclosure exists with a permit signal to be named (ICMS APS_1181415). | The Enclosure permit signals. |
| ENC-1 | Blocks-build | 19-BM-C and 19-BM-D share a downstream-wall guillotine held open during operation, so they act as one shielded volume. Do they share a single PSS search-and-secure, and should CORA model them as one Enclosure or two coupled ones? | Modelled as two Enclosures today (19-BM-C carries no Assets); the coupling is noted, not yet a structural link. | The Enclosure shape for the C and D volumes. |
| BLEPS-1 | Blocks-go-live | How should the BLEPS equipment-protection chain (beamline vacuum, and the cooling water plumbed in series across the Be window and the photon stop) map onto CORA Supplies and the beam-availability signal? | Vacuum and cooling water are beamline-scope Supplies, one each, whose faults the BLEPS also folds into beam availability, following 2-BM; no separate equipment-protection aggregate. | The BLEPS-to-Supply mapping. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FILTER-1 | Nice-to-have | How should the F3-30 two-bank Si/Ge/Cu filter unit be modelled: one selector over the combinatorial effective thicknesses, or one selector per bank? And what fills bank 2 slot 5? | One `Filter` Asset whose selectable foils are a per-Asset setting plus a position-to-thickness calibration, as at 2-BM; the combinatorial map is a setting, not a family split. | The filter selector modelling and the bank 2 slot 5 value. |

### Endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | What are the sample rotary and linear positioning stages (the manipulator design was out of FDR scope)? | A rotary stage plus a linear positioning stage, reusing the `RotaryStage` and `LinearStage` Families, models unbound. | The sample stage Model bindings. |
| ROBOT-1 | Blocks-go-live | What is the robotic sample changer, and what is the separate safety review it requires before implementation? How should CORA gate autonomous loading on it? | The changer is one Positioner Asset that loads and unloads Subjects; its operation is gated by a Clearance that must be Active, issued after the separate safety review. Modelled when the design and review land. | The sample-changer Asset, its Clearance gate, and the autonomous loading flow. |
| TRIG-1 | Blocks-go-live | What is the high-throughput trigger and sync scheme: is the sample rotary TTL encoder the master clock, and is PSO-style fly-scan triggering used? | A single `TimingController` carries the scheme; the rotary encoder is the candidate master clock; conditioner and PSO use to be confirmed. | The trigger / sync chain. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which scintillator, microscope optics, and camera will be procured for the indirect-detection system? | A scintillator, a visible-light microscope (composed as the cross-facility `Microscope` Assembly presenting the Detector Role), and a camera; models unbound until procurement. | The detector hardware Model bindings. |
