# Notes

## Techniques

*What Alvra is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

Alvra runs three technique families, none of which fits the catalog's tomography Methods, so each is carried pending on the [PSI Practices](../psi/index.md) until it is earned. They reuse the same pending Methods CORA's first XFEL, [LCLS-MFX](../lcls-mfx/notes.md#techniques), introduced; Alvra is the second deployment to need them, which is part of the point. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

### Femtosecond optical pump-probe

Alvra's reason for existing. An optical laser pulse excites the sample a controlled femtoseconds before (or after) the X-ray probe pulse; scanning the delay resolves the dynamics in time. The PALM (THz-streaking) and PSEN (spectral-encoding) arrival-time monitors correct the residual laser-to-X-ray jitter shot by shot.

- **Spine shape:** a `pump_probe` Method that scans the laser-to-X-ray delay (a `LinearStage` delay axis on the experiment laser) while acquiring per-shot, with the PSEN / PALM monitors correcting jitter.
- **Gap it leans on:** the cross-timing-domain synchronization (LASER-1). The delay axis itself is a positioner; what CORA cannot express is the femtosecond synchronization between the optical-laser and FEL timing domains (the `eco` `lxt` timing chain). This is the same gap LCLS-MFX's `lxt_ttc` SyncAxis exposed, now seen at a second XFEL.

### Time-resolved X-ray absorption and emission (XAS / XES / HERFD)

Alvra measures how a sample's electronic structure evolves after the pump: transient X-ray absorption through the incident energy (the double-crystal mono), and X-ray emission through the von Hamos spectrometer. In HERFD mode the incident energy is scanned at a fixed emission line.

- **Spine shape:** an `xas_spectroscopy` Method binding the `Monochromator` for the incident-energy choreography and the `EmissionSpectrometer` for the emitted spectrum, over a per-shot acquisition.
- **Gap it leans on:** the von Hamos binds the graduated `EmissionSpectrometer` Family (Alvra is a fourth sighting; SPEC-1 now tracks only the analyzer-crystal composition), and the HERFD incident-energy scan reuses the energy-change choreography CORA already models well. The time-resolution makes the acquisition per-shot, which leans on the DAQ gap (DAQ-1).

### Serial femtosecond crystallography (SFX)

On the Prime endstation Alvra also runs time-resolved serial crystallography: a stream of microcrystals is delivered into the focused FEL beam; each pulse records a single-shot diffraction pattern before destroying its crystal. The dataset is many single-shot patterns, indexed and merged downstream.

- **Spine shape:** a `serial_crystallography` Method binding the KB focusing, the sample delivery, the pulse picker, and the Jungfrau detector, over a Run that is a free-running per-shot acquisition rather than a trajectory of points.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). As at LCLS-MFX, this is the technique that most exposes the acquisition-ontology gap: there is no trajectory to walk, only a shot stream to tag and reference.

### Why none is in the catalog yet

The catalog's Methods are all tomography-family (`tomography`, `dark_field`, `flat_field`, the alignment and energy-change methods). An XFEL pump-probe station shares none of them: there is no rotation, no flat / dark frame pairing, no storage-ring energy ramp. Coining XFEL Methods now, before the acquisition axis they depend on exists, would be inventing recipes for a spine that cannot yet run them. So each is carried pending, reusing the Method name LCLS-MFX named for it, and the deepest dependency (the event-stream acquisition axis, DAQ-1) is sketched as a design note rather than built. That the same three Methods are now needed at a second, independently-built XFEL is the strongest argument yet that they are real Methods to earn, not LCLS-specific. See [Model](#model) for the gap register.

## Governance

*Who would act at Alvra and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

Alvra's principals are facility principals at the [PSI Site](../psi/index.md), not beamline-local: the SwissFEL instrument-scientist and operator pool, and the PSI safety-review body. Both are carried pending in the [site descriptor](../psi/index.md) until the PSI structure is confirmed; the `eco` device library is a controls library, not an organizational record, so it exposes no human roster (GOV-1). CORA's role kernel (the five-role authorization model) is facility-invariant, so Alvra inherits it; what Alvra adds to think about is the same two hazard gates LCLS-MFX raised, now at a second XFEL.

### The pump-probe laser Clearance

Alvra runs a class-4 optical laser for pump-probe. CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before laser-on work), the same posture LCLS-MFX takes for its pump-probe laser and 32-ID takes for its additive-manufacturing laser. This is distinct from whether the laser is a driven Asset: the device folds into the catalog `Laser` Family (the LCLS-MFX / 4-ID precedent), while the personnel-safety permit is a Clearance. The two coexist (LASER-1).

### The PSS permit

As at every beamline, beam-on work in an enclosure is gated by the facility personnel safety system (PSS). The SwissFEL PSS search-and-secure permit signals are not in the `eco` manifest and are carried pending (PSS-1). Alvra's enclosure structure (a shared Aramis optics hutch plus the Alvra experiment hutch) is itself carried `confirm` because the `eco` PV prefixes encode beamline-line zones (`SARFE10` front end, `SAROP11` optics, `SARES11` endstation), not the access-gated hutch or its safety meaning (ENC-1). The shared optics hutch is the same shared-zone question LCLS-MFX's front-end / transport zone raised, because the Aramis source feeds the Alvra, Bernina, and Cristallina stations (TOPO-1).

### What is not modelled

- **Trust instantiation.** No scenario instantiates Alvra trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.
- **The DAQ and acquisition software as principals.** The SwissFEL `sf-daq`, `bsread`, and the `eco` / `slic` scan suite are control-system software on the floor, not CORA actors (see [Controls](controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [PSI Site](../psi/index.md); see [Open questions](#open-questions) for the governance items still to confirm.

## Model

*The developer's by-kind index: where each CORA aggregate's Alvra content lives, how the device families fold at a second XFEL, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at Alvra |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### The headline: the families fold again, at a second XFEL

[LCLS-MFX](../lcls-mfx/notes.md#model) found that an XFEL's device families fold and its gaps are architectural. Alvra re-runs that test against an independently-built free-electron laser, mined from PSI's `eco` rather than SLAC's `pcdshub`, and reaches the same finding. Of Alvra's full `eco` device set, **none** had no CORA Family: every device reuses an existing one. The offset and KB mirrors fold into `Mirror`, the solid attenuators into `Filter`, the slits into `Slit`, the pulse picker into `Shutter` (PULSE-1), the profile monitors into `Scintillator` + `Camera`, the PBPS / PBIG monitors into `FluxMonitor` + `Diagnostic`, the double-crystal mono into `Monochromator`, the Huber sample stage into `LinearStage`, the optical table into `Table`, the sample microscope and the Jungfrau into `Camera`, and the pump-probe and reference lasers into the catalog `Laser` Family (the LCLS-MFX / 4-ID precedent). The von Hamos spectrometer binds the graduated `EmissionSpectrometer` Family, a **fourth sighting** after LCLS-MFX (which introduced it), NSLS-II ISS (which graduated it), and the MAX IV Balder near-sighting (SPEC-1). Each fold was reviewed against coining a synonym and rejected.

So the device taxonomy generalizes from storage rings to an XFEL almost untouched, and that result is now confirmed at two independent XFELs. What does not generalize is the **acquisition ontology**, the same as at LCLS-MFX. That is the product of this exercise, recorded next.

### Deliberately not here yet (the architectural gap register)

These are the parts of Alvra this scaffold leaves out on purpose. Unlike the open questions (facts the PSI team owns), each is a CORA scope decision: a shape the model does not yet have, with the seam it would extend named. None is built speculatively; an XFEL is the trigger that would justify the work, and Alvra is the second sighting of each gap, strengthening the case that the work is real and not LCLS-specific.

- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The load-bearing gap, re-confirmed. CORA's acquisition is a single-detector poll-to-Done loop plus a sub-Hz scalar observation logbook with no pulse-ID key. SwissFEL's `sf-daq` collects a free-running `bsread` stream of per-shot frames correlated by pulse-ID at beam rate, exactly the shape LCLS's DAQ has. The Run-as-provenance-envelope survives and the per-shot data plane lives in the SwissFEL data API (CORA references a `Dataset`, as it does for reconstructions via `ComputePort`), but representing a DAQ run as an actuation is a new event-stream axis. Its shape is sketched as a forward-looking design note in CORA's design memory (gated, not built); Alvra is the second deployment to need it.
- **Beam-synchronous event-system timing (TIMING-1).** The SwissFEL event system (EVR receivers, e.g. `SLAAR11-LTIM01-EVR0`) gates acquisition at beam rate, the analog of LCLS's EventSequencer. CORA's `TimingController` Family carries the device, but "acquire on event-code N at rate R" has no typed parameter home; today it would be opaque setpoints.
- **Femtosecond pump-probe synchronization (LASER-1).** The optical pump-probe laser and the FEL are two synchronized timing domains; the `eco` `lxt` timing chain holds them together and the PALM / PSEN arrival-time monitors correct the residual jitter. CORA's `PartitionRule` is single-domain spatial math; a cross-timing-domain synchronization is a relationship it cannot express. The laser device itself folds (catalog `Laser`); the sync is the gap, and Alvra is the second XFEL to expose it (LCLS-MFX's TimeTool is the same role as Alvra's PSEN).
- **One switched Aramis source feeding co-equal stations (TOPO-1).** One linac and Aramis undulator line serve the Alvra, Bernina, and Cristallina stations, beam routed one at a time. CORA models each beamline as a root Unit owning its source; a shared, switched source feeding co-equal Units has no home except the `Supply("PhotonBeam")` seam, and the routing state has no model. This is the same gap LCLS-MFX's shared-linac topology exposed.
- **Attenuator transmission solver (ATT-1).** The `eco` `AttenuatorAramis` driver solves a foil combination for a requested transmission, energy-dependent. CORA's `Filter` covers the discrete selection; the solve is the deferred `Attenuable` + `SolverReference` leg. With both LCLS-MFX and Alvra carrying the same energy-dependent attenuator solve, the rule-of-three for this leg is well past its trigger.

### What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** Alvra earns no catalog change; the XFEL recipes are carried pending on the [PSI Practices](../psi/index.md), reusing the pending LCLS-MFX Methods. No catalog Model is bound.
- **Sample delivery and the Subject custody thread.** The fixed-target / liquid-jet delivery on the Prime sample stage is endstation-specific and deferred (SAMPLE-1); no Family is coined, mirroring how LCLS-MFX carries its liquid jet.
- **The eco cross-line references (XREF-1).** Several Alvra `eco` drivers reference `SAROP21-*` PVs (a sibling Aramis line) for an aperture and an energy readback. Whether that is correct for Alvra or a copy-paste artifact is not determinable from source; carried as an open question, not silently modelled.
- **Integration scenarios.** No `test_alvra_*.py` registers Alvra Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.

## Open questions

*What CORA needs the PSI team (and PSI's documentation) to confirm before the model can be trusted.*

Alvra is modelled from PSI's open [`eco`](https://github.com/paulscherrerinstitute/eco) controls library, treated as a dry, correct DATA source: the Alvra manifest is the `aliases` dict in `eco/alvra/config.py`, and the per-device driver classes derive the motor axes from each PV prefix. That gives the device shape and the EPICS PV prefixes at high confidence; it does not give the motor units or limits, the Aramis source parameters, the PSS safety structure, or the Capability / Method binding, none of which is in the manifest. This page collects what `eco` cannot supply. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

As at the LCLS-MFX and Diamond exercises, the EPICS PV prefix for every device is already recorded in the descriptor, so wiring handles is not a question here. The questions concentrate on the XFEL acquisition paradigm and on the few `eco`-specific ambiguities the source itself leaves open.

### Scope, topology, and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is Alvra (or any SwissFEL station) actually intended to enter CORA scope, or is this a generalization exercise against an open controls source? | A generalization exercise: Alvra is CORA's second XFEL, testing whether the XFEL findings generalize across facilities; it is not on the pilot roadmap. | Whether PSI is a real Site or a modelling fixture. |
| TOPO-1 | Blocks-build | One linac and Aramis undulator line feed the Alvra, Bernina, and Cristallina stations, beam routed to one at a time. Should each station be its own root Unit sharing an upstream source, and where does the shared switched source live? | One `Alvra` root Unit owning its source for now; the shared, switched FEL source has no model and is carried as this question. The `Supply("PhotonBeam")` seam is the candidate home. | One-vs-many root Units and where the shared source and its routing state are modelled. |
| PSS-1 | Blocks-build | What are the SwissFEL PSS search-and-secure permit signals, and the interlock for the pump-probe laser? | Both enclosures exist with permit signals to be named; `eco` does not carry them. | The Enclosure permit signals and the laser-safety interlock. |
| ENC-1 | Blocks-build | Which enclosure does each device sit in? `eco` prefixes encode beamline-line zones (`SARFE10`, `SAROP11`, `SARES11` / `SLAAR11`), not the access-gated hutch or its safety meaning. | The shared Aramis optics hutch plus the Alvra experiment hutch. | The per-device Enclosure assignment. |

### Source, optics, and attenuation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the Aramis undulator line parameters and the per-shot photon-energy mechanism? The `eco` manifest carries the downstream device handles, not the source. | A SASE FEL undulator; per-shot photon energy is a DAQ datum, not a standing setpoint; energy-to-gap control is deferred. | The `Undulator` parameters and the per-shot energy mechanism. |
| MACHINE-1 | Nice-to-have | SwissFEL is a linac, not a storage ring, so the loose `StorageRing` family used by the synchrotron exercises does not fit. How should machine beam be modelled? | A `PhotonBeam` Supply, not a `StorageRing` device; the per-shot pulse energy is read via the `FluxMonitor` gas / intensity monitors. | The linac machine-state modelling boundary. |
| ATT-1 | Blocks-go-live | The `AttenuatorAramis` driver selects a foil combination for a requested transmission (energy-dependent). CORA's `Filter` covers the discrete selection but not the solve. Should the deferred `Attenuable` + `SolverReference` leg graduate? | `Filter` for the discrete selection; the target-transmission solver is the deferred `Attenuable` leg. With LCLS-MFX carrying the same solve, the rule-of-three is well past its trigger. | Whether the transmission solver is built and where. |
| MONO-1 | Nice-to-have | The double-crystal mono (ODCM105) is used for monochromatic / spectroscopy modes; Alvra also runs pink / SASE beam mono-out. What are the crystal and axis details, and the pink-vs-mono mode boundary? | A `Monochromator` Asset, used in some modes; mode and crystal details are settings to supply. | The DCM internals and the pink-vs-mono mode model. |
| XREF-1 | Blocks-go-live | Several Alvra `eco` drivers reference `SAROP21-*` PVs (a sibling Aramis line): the reference laser hardcodes an aperture on `SAROP21-OLIR134`, and the joint mono+FEL energy device reads `SAROP21-ODCM098:ENERGY`. Is this correct for Alvra, or a copy-paste artifact in the library? | The Alvra-line PVs (`SAROP11-*`) are authoritative; the `SAROP21-*` references are carried `confirm`, not silently modelled. | Whether the cross-line references are real Alvra dependencies. |

### Acquisition and timing (the architectural core)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DAQ-1 | Blocks-build | The SwissFEL `sf-daq` records a free-running `bsread` stream of per-shot frames tagged by pulse-ID at beam rate, correlated downstream. CORA's acquisition is a single-detector poll-to-Done loop plus a sub-Hz scalar observation logbook with no pulse-ID key. How does CORA represent a DAQ run? | The Run-as-provenance-envelope is kept; the per-shot data plane lives in the SwissFEL data API, and CORA references a `Dataset`, exactly as it does for reconstructions via `ComputePort`. A per-shot event-stream actuation axis is the gap, sketched in the design note, not built. This is the same gap LCLS-MFX exposed; Alvra is the second sighting. | Whether CORA gains an event-stream acquisition axis or remains a record-keeping shell for Alvra. |
| TIMING-1 | Blocks-go-live | The SwissFEL event system (EVR receivers, e.g. `SLAAR11-LTIM01-EVR0`) gates acquisition at beam rate. CORA's `TimingController` carries the device but has no typed home for an event trigger pattern. Where does the pattern parameter live? | `TimingController` for the device; the trigger pattern is carried as opaque setpoints until a typed parameter shape is earned. | The event-system trigger-pattern parameter model. |
| LASER-1 | Blocks-go-live | The fs pump-probe needs laser-to-X-ray synchronization (the `eco` `lxt` timing chain) and PALM / PSEN jitter correction. CORA's `PartitionRule` is single-domain spatial math, with no cross-timing-domain sync; and is the laser a driven Asset or a hazard? | The laser is carried as a catalog `Laser` Family device (the LCLS-MFX / 4-ID precedent, model-vs-hazard open); the delay stage is a `LinearStage`; the fs synchronization has no CORA model. | The pump-probe synchronization model and the laser's model-vs-hazard status. |

### Diagnostics, sample, and detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIAG-1 | Blocks-go-live | How are the intensity-position monitors (PBPS), the gas monitor (PBIG), and the PALM / PSEN arrival-time monitors modelled? They present the Sensor Role. | The loose `FluxMonitor` and `Diagnostic` Sensor families reused from I22 / 2-BM / LCLS-MFX; per-shot intensity normalization is a DAQ-plane concern (DAQ-1). | The diagnostics modelling boundary. |
| SAMPLE-1 | Blocks-go-live | What is the sample-delivery shape on the Prime endstation (fixed target, liquid jet), and the `Subject` custody lifecycle for serial crystallography? | Sample delivery is endstation-specific and deferred; no Family is coined yet; the `Subject` thread is carried as this question. | The sample-delivery model and the `Subject` custody thread. |
| SPEC-1 | Nice-to-have | The von Hamos spectrometer is a crystal-analyzer X-ray emission spectrometer composing analyzer crystals and a 2D detector. The Family question is resolved: `EmissionSpectrometer` is in the catalog (Alvra is a fourth sighting). The residual question is whether each analyzer crystal is a child Asset or a setting on the one spectrometer Asset. | The analyzer crystals carried as settings on the one `EmissionSpectrometer` Asset for now; child-Asset-per-crystal deferred. | The analyzer-crystal composition (child-Asset vs setting). |
| DET-1 | Blocks-go-live | What is the Alvra science detector? `eco` binds a Jungfrau named `JF_4.5M` (the von Hamos 4.5M, serial `JF02T09V03` inferred via `sf_daq_broker`), and the broker lists further Alvra options (16M, 4M, 2M TXS, 0.5M variants). Which is in use, and its threshold / geometry? | The detector reuses `Camera`; per-shot frames flow through the `sf-daq` data plane (DAQ-1); the model, the active variant, and the calibration are to supply. | The detector model and how its per-shot frames are referenced. |
| PULSE-1 | Nice-to-have | The X-ray pulse picker is a fast single-pulse selector folded into `Shutter`. Is a rotary pulse-picking chopper a distinct Family (the loose `Chopper` shape)? | `Shutter` Role; the Shutter-vs-Chopper distinction is carried as this question, the same one LCLS-MFX raised. | Whether the pulse picker earns its own Family. |
