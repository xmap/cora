# Notes

## Techniques

*What 7-BM is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 7-BM is multi-technique, and which techniques enter the CORA pilot scope is itself an open question (TECH-1). The function view below survives the eventual equipment choices, which is why it can be written before the hardware is confirmed.

The beam mode is selected per technique over one set of optics, not a fixed source property (BEAM-1):

| Technique | Beam mode | Detector modality | Status in CORA |
| --- | --- | --- | --- |
| Tomography | monochromatic | 2D area camera (scintillator-coupled) | reuses the 2-BM Methods unchanged |
| High-speed imaging | white | high-speed movie camera, chopper-gated | new acquisition Method, pending |
| Radiography | focused (~8 keV) | point photodiode, digitizer-read | new acquisition Method, pending |
| Energy-dispersive diffraction | white | germanium energy-dispersive detector | new Method, pending |
| Confocal fluorescence | (docs stub) | spectroscopic detector | deferred until confirmed (the docs page is empty) |

A few points of intent shape the model:

- **Tomography is pure reuse.** 7-BM runs the same tomoScan engine as 2-BM (single, vertical, horizontal, mosaic scans), so its tomography binds the existing `tomography` and `mosaic_tomography` Methods and the 2-BM detector shape. No new tomography vocabulary is earned.
- **The new techniques are new acquisition Methods, not new Capabilities.** High-speed movie bursts, point-detector radiography traces, and the energy-to-q EDD measurement are new `Method` rows under the existing `acquisition` and `characterization` Capabilities. They are deployment vocabulary; the device Roles (Detector, Sensor) already exist. They are carried pending until the technique enters scope and its data unit is confirmed (HSI-1, RAD-1, DET-1).
- **Beam mode is an operation mode over one beamline.** Inserting or bypassing the monochromator, filtering the white beam, or focusing with the KB pair picks the spectrum for a technique; it is a mode over one set of optics, not separate beamlines (BEAM-1).
- **Techniques can combine.** The docs note energy-dispersive diffraction running simultaneously with tomography through shared optics; CORA models that as coordinated Runs under one Campaign, not a new combined technique (TECH-1).

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join as the techniques enter the pilot scope. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who will act at 7-BM, and the trust shape that will gate it. Design-phase.*

Governance at 7-BM follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

Because 7-BM runs at the same APS Site as 2-BM, it reuses the APS facility envelope rather than creating a new one: the APS operator pool, the experiment-safety review structure, and the seeded agents are facility-wide and are inherited unchanged. This is the opposite of the TomoWISE deployment, which had to create a new MAX IV Site. 7-BM adds only its own beamline-bound principals (the 7-BM beamline scientists and operators), carried pending on the [APS site page](../aps/index.md#safety-and-governance).

7-BM is pre-build for CORA, so the concrete trust shape is not yet instantiated. What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the APS Site, not on the beamline, and the beamline links up to them rather than restating them.

One governance question is sharper at 7-BM than at 2-BM: the flow and combustion hazard surface (flammable gas, fuel vapor, oxygen deficiency, a radioactive check source for detector calibration) is broader than the radiation-only hazard profile of micro-CT. CORA's current position is that this is handled by ESAF clearances plus operator Cautions plus the hutch alarms, not by a separate hazard aggregate. Whether combustion or flammable-gas work needs a review, approve, and expire workflow distinct from the standard ESAF clearance is the single question that would change that (HAZ-1).

The concrete Zone, Conduit, and Policy instances, and the beamline operator pool, land when the beamline approaches commissioning, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's 7-BM content lives, a flow / combustion deployment whose FlowController grounds the continuous-regulation gap, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at 7-BM |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What is deliberately not here yet

- **New catalog Families and Methods.** 7-BM does not earn new catalog kinds in this scaffold. The genuinely-new device anatomies are carried as loose families with a tracking question; the new techniques are carried as pending Methods. They are added to the catalog only when a confirmed device or technique and the naming review settle them. This follows the "pilots earn the abstractions" rule: a beamline that is not yet onboarded does not get to mint cross-facility vocabulary.
- **Integration scenarios.** No `test_7bm_*.py` registers 7-BM Assets into the event store. Scenario code is where Assets become real, and hard-registering a design-phase, partly-documented beamline would commit speculative structure. It lands when the techniques enter the pilot scope and the team approves.
- **Vendor Models.** No catalog Model is bound. The vendors named in the docs (Photron, Sierra, Kaeser, IDT, Rigaku) are recorded in the descriptor notes, not bound, because no part is procured into the catalog.
- **Operations and experiment views.** A runbook and live experiment view for an unmodelled beamline would be invention; see the note on the [index](index.md#not-yet-documented).
- **Detector assemblies.** The tomography detector is left as plain devices (scintillator plus camera). It could later compose the cross-facility `Microscope` Assembly that 2-BM and TomoWISE use, once a scenario registers it.

- **The continuous-regulation runtime (the FlowController setpoint program).** The `FlowController` presents the earned `Regulator` Role and CORA commands its setpoint (a one-shot `SetpointStep`), but a continuous setpoint PROGRAM, a hold or ramp held during a Run while the scan acquires, has no runtime today: the Conductor walks a finite step list, and `SetpointStep` / `ControlPort.write` are one-shot. The regulation loop itself stays device/IOC-owned (the Sierra controller runs it); CORA's gap is expressing and observing the program, not hosting the loop. This is the deepest cross-facility architectural gap the audit named; 7-BM (flow/combustion) is its grounding case alongside i11 / XPD thermal. It is the continuous-regulation axis, deferred to a Stage-0 research note and a later gate-reviewed build, exactly as the event-stream axis was for XFEL/XPCS acquisition (FLOW-1).

## Open questions

*What CORA needs the 7-BM team to confirm before the model can be trusted.*

7-BM is in the design phase and its operations documentation is partial, so this page is long by design: almost every value on the [device pages](index.md) is taken from the 7-BM docs or inferred, not confirmed with staff. Each row below is a fact the beamline team owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

A note on what 7-BM tests that 2-BM did not: 7-BM is multi-technique (high-speed imaging, radiography, tomography, energy-dispersive diffraction, fluorescence), runs white, monochromatic, and focused beam, and carries a flow and combustion sample environment. The questions below concentrate on the new shapes; the tomography path itself reuses the 2-BM model unchanged.

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the EPICS PV handles for each device? | Control handles are unassigned; CORA leaves the device handle empty. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-build | What are the PSS search-and-secure permit signals for the 7-BM-A and 7-BM-B hutches? | Both hutches exist with permit signals to be named. | The Enclosure permit signals. |
| HAZ-1 | Blocks-go-live | Do combustion, flammable-gas, or radioactive-check-source experiments need a review / approve / expire workflow distinct from the standard APS ESAF clearance? | The flow and combustion hazard surface is handled by ESAF clearances plus operator Cautions plus alarms, not a separate hazard aggregate. | Whether a Hazard lifecycle is earned beyond Clearance and Caution. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What is the 7-BM source after APS-U? The docs do not state it. | A bending-magnet source, carried `confirm`, mirroring the 2-BM source representation. | The `Source` device and beamline `source` field. |
| BEAM-1 | Blocks-build | Which beam mode (white, monochromatic via the DMM, or focused via the KB mirrors) is canonical for each technique, and is the DMM split-stripe dual-energy mode used routinely? | Beam mode is a per-technique choice over one set of optics, not a fixed source property. | Binding each technique and Practice to a beam mode. |
| OPT-1 | Nice-to-have | Which optics sit in the routine pilot path: the DMM, the multilayer mirror, the KB focusing pair, the polycapillary optics, and the channel-cut calibration crystals? | The DMM, multilayer mirror, and KB pair are modelled; the polycapillary and channel-cut crystals are deferred until a confirmed technique needs them. | Which optics are Assets and which stay deferred. |
| CHOP-1 | Blocks-go-live | Is the rotary chopper permanently installed or fitted per time-resolved run, is its duty cycle a commanded setting or a manual mechanical re-index, and is the photoeye a tracked Sensor or inseparable floor wiring? | A loose `Chopper` family, pending whether it is a new catalog Family or an existing `Shutter` / `RotaryStage` plus settings. | The chopper modelling boundary. |

### Techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Which techniques are in scope for the CORA pilot: tomography, high-speed imaging, radiography, energy-dispersive diffraction, confocal fluorescence, and which combine (the docs note EDD running simultaneously with tomography)? | Tomography reuses the 2-BM Methods; the other techniques are design intent, carried pending on the [APS site Practices](../aps/index.md#the-techniques-adapted-here). | Which Methods and Practices the pilot binds. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Is the germanium energy-dispersive detector the same physical device as the fluorescence MCA, and is XRF a routine standalone technique or only an EDD energy-scale calibration step? | One `EnergyDispersiveSpectrometer` device presenting the Sensor Role, with fluorescence as a calibration step, not a separate detector. | One versus two Sensor-backed detector Assets, and whether a spectroscopy Method is earned. |
| RAD-1 | Blocks-go-live | For time-resolved radiography, what is the point-detector chain (PIN diode plus ADQ14 digitizer or oscilloscope plus DataGrabber), and is one acquisition trace one Dataset? | A `Photodiode` device presenting the Sensor Role; the digitizer / scope / DataGrabber stay on the floor; the data unit is unconfirmed. | The radiography detector Family and the Run / Dataset shape. |
| HSI-1 | Blocks-go-live | For high-speed imaging, is one chopper-gated movie burst one Run / Dataset (and the N-sequence set one Campaign), and how are top-up-blanked frames represented (invalid-marked, dropped, gap)? | One high-speed `Camera`; the acquisition unit and blanking semantics are unconfirmed. | The Run / Dataset / Acquisition shape for time-resolved capture. |

### Sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| FLOW-1 | Nice-to-have | The command-vs-read half is settled: CORA COMMANDS the regulated flow / air setpoints (the graduated catalog `FlowController` Family presents the earned `Regulator` Role; a one-shot `SetpointStep`), not read-back-only. What remains open is the continuous-regulation runtime, a setpoint PROGRAM (a hold or ramp held during a Run, orthogonal to the scan step-list; the loop device/IOC-owned, CORA programs and observes), which no runtime expresses yet. | command-vs-read settled (commands); `FlowController` graduated (earned across i22 / 7-BM / LIX / XFP); the setpoint-program runtime is the continuous-regulation axis (see model.md + its Stage-0 research). | The continuous-regulation setpoint-program runtime primitive. |
| ENV-1 | Blocks-go-live | Is there an installed combustion, spray, or fuel-injection device at 7-BM, or is combustion an intended use served by the air, gas, and vacuum infrastructure? | No combustion rig Asset is modelled; combustion is served by the facility Supplies and bound to the specimen Subject. | Whether a combustion-rig Asset and a fuel-vapor Caution are modelled. |

### Controls and site

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TIMING-1 | Nice-to-have | Should the DG645 delay generators, softGlue FPGA, Machine Status Link P0 reference, and top-up inhibit be one `TimingController` device, or do any of them deserve separate modelling? | One `TimingController` carries the whole scheme, mirroring the 2-BM Timing device. | The timing-subsystem Asset shape. |
| SECTOR-1 | Nice-to-have | Confirm 7-BM is in Sector 7, and whether it shares any governed resource (optics, safety system, compute) with another APS beamline. | 7-BM is a separate beamline in Sector 7 under the APS Site, sharing no governed resource with 2-BM. | The sector label and any cross-beamline shared-resource governance. |
