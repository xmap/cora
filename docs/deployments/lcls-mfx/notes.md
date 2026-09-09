# Notes

## Techniques

*What MFX is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

MFX runs three technique families, none of which fits the catalog's tomography Methods, so each is carried pending on the [SLAC Practices](../slac/index.md) until it is earned. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

### Serial femtosecond crystallography (SFX)

A stream of microcrystals is delivered into the focused FEL beam (liquid jet or fixed target); each X-ray pulse destroys its crystal but records a diffraction pattern first ("diffraction before destruction"). The dataset is millions of single-shot patterns, indexed and merged downstream.

- **Spine shape:** a `serial_crystallography` Method binding the focusing lenses, the sample delivery, the pulse picker, and the area detector, over a Run that is a free-running per-shot acquisition rather than a trajectory of points.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). This is the technique that most exposes the acquisition-ontology gap: there is no trajectory to walk, only a shot stream to tag and reference.

### Femtosecond optical pump-probe

An optical laser pulse excites the sample a controlled femtoseconds before (or after) the X-ray probe pulse; scanning the delay resolves dynamics in time.

- **Spine shape:** a `pump_probe` Method that scans the laser-to-X-ray delay (a `LinearStage` delay axis) while acquiring per-shot, with the timetool correcting residual jitter shot by shot.
- **Gap it leans on:** the cross-timing-domain synchronization (LASER-1). The delay axis itself is a positioner; what CORA cannot express is the femtosecond synchronization between the optical-laser and FEL timing domains (the `lxt_ttc` SyncAxis).

### X-ray emission spectroscopy (XES / HERFD)

The von Hamos 6-crystal spectrometer disperses the X-ray fluorescence emitted by the sample onto a 2D detector, resolving emission energy; in HERFD mode the incident energy is scanned at a fixed emission line.

- **Spine shape:** an `xas_spectroscopy` Method binding the emission spectrometer and, for HERFD, the incident-energy choreography (the DCCM), over a per-shot acquisition.
- **Gap it leans on:** the emission spectrometer binds the `EmissionSpectrometer` family it introduced, since graduated once ISS earned the 2nd sighting (SPEC-1 now tracks only the analyzer-crystal composition), and HERFD's incident-energy scan reuses the energy-change choreography CORA already models well.

### Why none is in the catalog yet

The catalog's Methods are all tomography-family (`tomography`, `dark_field`, `flat_field`, the alignment and energy-change methods). An XFEL shares none of them: there is no rotation, no flat / dark frame pairing, no storage-ring energy ramp. Coining XFEL Methods now, before the acquisition axis they depend on exists, would be inventing recipes for a spine that cannot yet run them. So each is carried pending, naming the Method it would earn, and the deepest dependency (the event-stream acquisition axis, DAQ-1) is sketched as a design note rather than built. See [Model](#model) for the gap register.

## Governance

*Who would act at MFX and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

MFX's principals are facility principals at the [SLAC Site](../slac/index.md), not beamline-local: the LCLS instrument-scientist and operator pool, and the LCLS safety-review body. Both are carried pending in the [site descriptor](../slac/index.md) until the LCLS structure is confirmed. CORA's role kernel (the five-role authorization model) is facility-invariant, so MFX inherits it; what MFX adds to think about is two hazard gates the storage-ring exercises do not have.

### The pump-probe laser Clearance

MFX runs a class-4 optical laser for pump-probe, governed at LCLS by the Beam Transport Protection System (BTPS). CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before laser-on work), the same posture 32-ID takes for its additive-manufacturing laser. This is distinct from whether the laser is a driven Asset: the device folds into the catalog `Laser` Family (the 4-ID precedent), while the personnel-safety permit is a Clearance. The two coexist (LASER-1).

### The PPS permit

As at every beamline, beam-on work in an enclosure is gated by the facility personnel protection system (PPS). The LCLS PPS search-and-secure permit signals are not in `pcdshub` and are carried pending (PSS-1). MFX's enclosure structure (a shared front-end / transport zone plus the MFX experiment hutch) is itself carried `confirm` because the `pcdshub` PV prefixes encode beamline-line zones, not access-gated hutches (ENC-1).

### What is not modelled

- **Trust instantiation.** No scenario instantiates MFX trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded.
- **The DAQ and analysis software as principals.** The LCLS DAQ, `psana`, and the bluesky-based scan suite are control-system software on the floor, not CORA actors (see [Controls](controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [SLAC Site](../slac/index.md); see [Open questions](#open-questions) for the governance items still to confirm.

## Model

*The developer's by-kind index: where each CORA aggregate's LCLS-MFX content lives, how the device families fold while the gaps stay architectural, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at LCLS-MFX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### The headline: the families fold, the gaps are architectural

I03 graduated a device Family (Goniometer). MFX coined exactly one new family and reused everything else, and that is the finding. Of MFX's full device set, one type had no CORA Family, the von Hamos emission spectrometer; it introduced `EmissionSpectrometer`, which has since GRADUATED into the catalog once NSLS-II ISS (8-ID) earned the second sighting (SPEC-1). Everything else reuses an existing Family: the offset mirrors fold into `Mirror`, the solid-Si attenuators into `Filter`, the JAWS into `Slit`, the pulse picker into `Shutter` (PULSE-1), the profile imagers into `Scintillator` + `Camera`, the intensity-position monitors into `FluxMonitor` + `Diagnostic`, the channel-cut into `Monochromator`, the lens stacks into the graduated `Transfocator` catalog Family, the EventSequencer into `TimingController`, the pump-probe laser into the catalog `Laser` Family (the 4-ID precedent), and the area detector into `Camera`. Each fold was reviewed against coining a synonym and rejected.

So the device taxonomy generalizes from storage rings to an XFEL almost untouched. What does not generalize is the **acquisition ontology**. That is the product of this exercise, recorded next.

### Deliberately not here yet (the architectural gap register)

These are the parts of MFX this scaffold leaves out on purpose. Unlike the open questions (facts the LCLS team owns), each of these is a CORA scope decision: a shape the model does not yet have, with the seam it would extend named. None is built speculatively; an XFEL is the trigger that would justify the work.

- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The load-bearing gap. CORA's acquisition is a single-detector poll-to-Done loop (`apps/api/src/cora/operation/acquisitions.py`) plus a sub-Hz scalar observation logbook with no pulse-ID key (`apps/api/src/cora/run/aggregates/run/entries.py`). An XFEL collects a free-running stream of per-shot frames correlated by fiducial at beam rate. The Run-as-provenance-envelope survives and the per-shot data plane lives in `psana` (CORA references a `Dataset`, as it does for reconstructions via `ComputePort`), but representing a DAQ run as an actuation is a new event-stream axis. Its shape is sketched as a forward-looking design note in CORA's design memory (gated, not built).
- **Beam-synchronous event-code timing (TIMING-1).** The EventSequencer plays a sequence of `[beam_code, delta_beam, delta_fiducial, burst_count]` lines that gate acquisition at beam rate. CORA's `TimingController` Family carries the device, but "acquire on event-code N at rate R, burst B" has no typed parameter home; today it would be opaque setpoints.
- **Femtosecond pump-probe synchronization (LASER-1).** The optical laser and the FEL are two synchronized timing domains (the `lxt_ttc` SyncAxis holds a ~50 fs deadband; the timetool corrects residual jitter). CORA's `PartitionRule` is single-domain spatial math; a cross-timing-domain synchronization is a relationship it cannot express. The laser device itself folds (catalog `Laser`, 4-ID precedent); the sync is the gap.
- **One switched FEL source feeding co-equal instruments (TOPO-1).** One linac and undulator line serve many instruments, beam routed one at a time by the transport mirrors. CORA models each beamline as a root Unit owning its source; a shared, switched source feeding co-equal Units has no home except the `Supply("PhotonBeam")` seam, and the routing state ("which instrument has beam now") is new.
- **Attenuator transmission solver (ATT-1).** The solid-Si attenuators solve a foil combination for a requested transmission, energy-dependent (the `AttBase` solver). CORA's `Filter` covers the discrete selection; the solve is the deferred `Attenuable` + `SolverReference` leg (`apps/api/src/cora/operation/_partition_rule_eval.py` defers SolverReference evaluation). MFX, with the same focus solver on the `Transfocator` lens stacks, is the rule-of-three trigger.
- **Computed device-state to path-transmission lightpath (LIGHTPATH-1).** `pcdshub`'s `lightpath` walks the z-ordered beam path and computes path-level transmission and the first blocking device from each device's inserted / removed state. CORA already has the static z-ordered walk and the location-not-identity discipline; only the dynamic computed half is deferred (the passive-beam-path tier). `lightpath/path.py` is a ready precedent.

### What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** MFX earns no catalog change; the XFEL recipes are carried pending on the [SLAC Practices](../slac/index.md). No catalog Model is bound.
- **The von Hamos as a graduated Family.** `EmissionSpectrometer` GRADUATED into the catalog once NSLS-II ISS (8-ID) earned the second sighting (its Johann + von Hamos XES / HERFD spectrometers); MAX IV Balder (SCANIA-2D) is a third near-sighting. The residual open question is whether each analyzer crystal is a child Asset (SPEC-1).
- **Sample delivery and the Subject custody thread.** The liquid jet / fixed target is endstation-specific and deferred (SAMPLE-1); no Family is coined.
- **Integration scenarios.** No `test_lcls_mfx_*.py` registers MFX Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.

## Open questions

*What CORA needs the LCLS team (and SLAC's documentation) to confirm before the model can be trusted.*

MFX is modelled from SLAC's open [`pcdshub`](https://github.com/pcdshub) stack, treated as a dry, correct DATA source: the `happi` device database ([`device_config/db.json`](https://github.com/pcdshub/device_config)), the worked hutch config ([`mfx/beamline.py`](https://github.com/pcdshub/mfx)), the [`lightpath`](https://github.com/pcdshub/lightpath) beam-walk engine, and `pcdsdevices`. That gives the device shape and the EPICS PV prefixes at high confidence; it does not give the calibrated numbers, the PPS safety structure, the undulator specifics, or the Capability / Method binding. This page collects what `pcdshub` cannot supply. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

As at the Diamond exercises, the EPICS PV prefix for every device is already recorded in the descriptor, so wiring handles is not a question here. The questions concentrate on the one thing the storage-ring exercises never reached: the XFEL acquisition paradigm.

### Scope, topology, and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is MFX (or any LCLS instrument) actually intended to enter CORA scope, or is this a generalization exercise against an open controls source? | A generalization exercise: MFX tests the XFEL acquisition paradigm; it is not on the pilot roadmap. | Whether SLAC is a real Site or a modelling fixture. |
| TOPO-1 | Blocks-build | One linac and undulator line feed many co-equal instruments (CXI/XPP/XCS/MEC/MFX, plus the LCLS-II soft-X-ray instruments), beam routed to one at a time. Should each instrument be its own root Unit sharing an upstream source, and where does the shared switched source live? | One `LCLS-MFX` root Unit owning its source for now; the shared, switched FEL source has no model and is carried as this question. The `Supply("PhotonBeam")` seam is the candidate home. | One-vs-many root Units and where the shared source and its routing state are modelled. |
| PSS-1 | Blocks-build | What are the LCLS PPS search-and-secure permit signals, and the BTPS interlock for the pump-probe laser? | Both enclosures exist with permit signals to be named; `pcdshub` does not carry them. | The Enclosure permit signals and the laser-safety interlock. |
| ENC-1 | Blocks-build | Which enclosure does each device sit in? `pcdshub` prefixes encode beamline-line zones (FEE, XRT, HFX, MFX:DG1/DG2/DIA), not the access-gated hutch or its safety meaning. | The shared front-end / transport zone plus the MFX experiment hutch. | The per-device Enclosure assignment. |

### Source, optics, and attenuation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the HXR undulator line parameters and the per-shot photon-energy mechanism (vernier vs undulator), and is the beam SASE or self-seeded? `pcdshub` carries the device handles, not the source curve. | A SASE FEL undulator; per-shot photon energy is a DAQ datum, not a standing setpoint; energy-to-gap control is deferred. | The `Undulator` parameters and the per-shot energy mechanism. |
| MACHINE-1 | Nice-to-have | LCLS is a linac, not a storage ring, so the loose `StorageRing` family used by the synchrotron exercises does not fit. How should machine beam be modelled? | A `PhotonBeam` Supply, not a `StorageRing` device; the per-shot pulse energy is read via a `FluxMonitor` gas detector. | The linac machine-state modelling boundary. |
| ATT-1 | Blocks-go-live | The solid-Si attenuators select a foil combination for a requested transmission (energy-dependent, the `AttBase` solver). CORA's `Filter` covers the discrete selection but not the solve. Should the deferred `Attenuable` + `SolverReference` leg graduate? | `Filter` for the discrete selection; the target-transmission solver is the deferred `Attenuable` leg, and MFX is its rule-of-three trigger. | Whether the transmission solver is built and where. |
| MONO-1 | Nice-to-have | The diamond double-channel-cut mono (DCCM) is used for some modes; MFX also runs pink / SASE beam mono-out. What are the crystal and axis details, and the pink-vs-mono mode boundary? | A `Monochromator` Asset, used in some modes; mode and crystal details are settings to supply. | The DCCM internals and the pink-vs-mono mode model. |

### Acquisition and timing (the architectural core)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DAQ-1 | Blocks-build | The LCLS DAQ records a free-running stream of per-shot frames tagged by pulse-ID / fiducial at beam rate (120 Hz to ~1 MHz), correlated downstream by pulse-ID. CORA's acquisition is a single-detector poll-to-Done loop plus a sub-Hz scalar observation logbook with no pulse-ID key. How does CORA represent a DAQ run? | The Run-as-provenance-envelope is kept; the per-shot data plane lives in `psana`, and CORA references a `Dataset`, exactly as it does for reconstructions via `ComputePort`. A per-shot event-stream actuation axis is the gap, sketched in the design note, not built. | Whether CORA gains an event-stream acquisition axis or remains a record-keeping shell for MFX. |
| TIMING-1 | Blocks-go-live | The EventSequencer plays a beam-synchronous sequence (each line `[beam_code, delta_beam, delta_fiducial, burst_count]`) to gate acquisition. CORA's `TimingController` carries the device but has no typed home for an event-code sequence. Where does the sequence parameter live? | `TimingController` for the device; the event-code sequence is carried as opaque setpoints until a typed parameter shape is earned. | The event-code-sequence parameter model. |
| LASER-1 | Blocks-go-live | The fs pump-probe needs laser-to-X-ray synchronization (the `lxt_ttc` SyncAxis, ~50 fs deadband) and timetool jitter correction. CORA's `PartitionRule` is single-domain spatial math, with no cross-timing-domain sync; and is the laser a driven Asset or a hazard? | The laser is carried as a catalog `Laser` Family device (the 4-ID precedent, model-vs-hazard open); the delay stage is a `LinearStage`; the fs synchronization has no CORA model. | The pump-probe synchronization model and the laser's model-vs-hazard status. |
| LIGHTPATH-1 | Nice-to-have | `lightpath` computes path-level transmission and the first blocking device from each device's inserted / removed state along the z-walk. CORA has the static z-ordered walk and location-not-identity, but not the dynamic device-state-to-path-transmission computation (the passive-beam-path tier defers the beam effect). Should it graduate? | The static walk is modelled; the dynamic computed transmission is deferred under the passive-beam-path tier; `lightpath/path.py` is the precedent. | Whether the computed lightpath beam-effect is built. |

### Diagnostics, sample, and detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIAG-1 | Blocks-go-live | How are the intensity-position monitors (IPM), the gas detector, the Wave8, and the timetool modelled? They present the Sensor Role; the gas detector is a `BeamStats` PV, not a happi device. | The loose `FluxMonitor` and `Diagnostic` Sensor families reused from I22 / 2-BM; per-shot intensity normalization is a DAQ-plane concern (DAQ-1). | The diagnostics modelling boundary. |
| SAMPLE-1 | Blocks-go-live | What is the sample-delivery shape (liquid jet, fixed target), and the `Subject` custody lifecycle for serial crystallography? | Sample delivery is endstation-specific and deferred; no Family is coined yet; the `Subject` thread is carried as this question. | The sample-delivery model and the `Subject` custody thread. |
| SPEC-1 | Nice-to-have | The von Hamos 6-crystal spectrometer is a crystal-analyzer X-ray emission spectrometer composing analyzer crystals and a 2D detector along a dispersive geometry. The Family question is resolved: `EmissionSpectrometer` GRADUATED into the catalog once NSLS-II ISS (8-ID) earned the second sighting. The residual question is whether each of the six analyzer crystals is a child Asset or a setting on the one spectrometer Asset. | The six analyzer crystals carried as settings on the one `EmissionSpectrometer` Asset for now; child-Asset-per-crystal deferred. | The analyzer-crystal composition (child-Asset vs setting). |
| DET-1 | Blocks-go-live | What is the MFX area detector (Rayonix MX340-XFEL, ePix10k, Jungfrau), and its threshold / geometry? `pcdshub` manages it through the DAQ, not as a polled happi device. | The detector reuses `Camera`; per-shot frames flow through the DAQ data plane (DAQ-1); the model and calibration are to supply. | The detector model and how its per-shot frames are referenced. |
| PULSE-1 | Nice-to-have | The pulse picker is a fast single-pulse selector folded into `Shutter`. Is a rotary pulse-picking chopper a distinct Family (the loose `Chopper` shape)? | `Shutter` Role; the Shutter-vs-Chopper distinction is carried as this question. | Whether the pulse picker earns its own Family. |
