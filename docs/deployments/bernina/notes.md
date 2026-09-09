# Notes

## Techniques

*What Bernina is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

Bernina runs two technique families, neither of which fits the catalog's tomography Methods, so each is carried pending on the [PSI Practices](../psi/index.md) until it is earned. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

### Femtosecond optical pump-probe

The shared SwissFEL technique, the same one [Alvra](../alvra/notes.md#techniques) and [LCLS-MFX](../lcls-mfx/notes.md#techniques) run. An optical laser pulse excites the sample a controlled femtoseconds before (or after) the X-ray probe pulse; scanning the delay resolves the dynamics in time. The PSEN spectral-encoding arrival-time monitor corrects the residual laser-to-X-ray jitter shot by shot.

- **Spine shape:** a `pump_probe` Method that scans the laser-to-X-ray delay (a `LinearStage` delay axis on the experiment laser) while acquiring per-shot, with the PSEN monitor correcting jitter.
- **Gap it leans on:** the cross-timing-domain synchronization (LASER-1). The delay axis itself is a positioner; what CORA cannot express is the femtosecond synchronization between the optical-laser and FEL timing domains (the `eco` `lxt` timing chain). Bernina is the third deployment to reach this gap (after LCLS-MFX and Alvra).

### Time-resolved hard X-ray diffraction and scattering

Bernina's reason for existing, and what distinguishes it from Alvra. After the pump, the sample's structural response is read by diffraction: Bragg peaks and diffuse scattering recorded shot by shot on the area detector, as a function of pump-probe delay. The sample is oriented and the detector positioned by the GPS six-circle or XRD You-geometry diffractometer.

- **Spine shape:** a `diffraction` Method binding the diffractometer (a `Goniometer` for the sample circles, a `RotaryStage` 2-theta detector arm, and a reciprocal-space `PseudoAxis`), composed through the graduated `Diffractometer` Assembly (DIFF-1), over a per-shot acquisition. The reciprocal-space layer resolves the hkl inverse kinematics, and for the XRD platform the kappa-to-Eulerian conversion (DIFF-2).
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). A time-resolved diffraction run is a free-running shot stream tagged by pulse-ID and delay, not a trajectory of points the spine walks. The diffractometer itself is fully covered by the existing Assembly; the acquisition is the gap.

### Why neither is in the catalog yet

The catalog's Methods are all tomography-family (`tomography`, `dark_field`, `flat_field`, the alignment and energy-change methods). An XFEL diffraction station shares none of them: there is no rotation tomography, no flat / dark frame pairing, no storage-ring energy ramp. The `diffraction` Method is genuinely new for the fleet (the synchrotron diffractometers at 4-ID and 8-ID carry their own pending Methods), and coining it now, before the per-shot acquisition axis it depends on exists (DAQ-1), would be inventing a recipe for a spine that cannot yet run it. So it is carried pending. That a diffraction technique reaches the **same** acquisition gaps a spectroscopy technique (Alvra) and a crystallography technique (LCLS-MFX) reached is the reinforcement Bernina adds: the gaps are about the XFEL acquisition paradigm, not about any one technique. See [Model](#model) for the gap register and the `Diffractometer` Assembly design.

## Governance

*Who would act at Bernina and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

Bernina's principals are facility principals at the [PSI Site](../psi/index.md), not beamline-local: the SwissFEL instrument-scientist and operator pool, and the PSI safety-review body. Both are carried pending in the [site descriptor](../psi/index.md) until the PSI structure is confirmed; the `eco` device library is a controls library, not an organizational record, so it exposes no human roster (GOV-1). CORA's role kernel (the five-role authorization model) is facility-invariant, so Bernina inherits it. Bernina shares its Site, its Aramis source, and its safety posture with the sibling [Alvra](../alvra/notes.md#governance) station, so most of the governance shape is the PSI-Site shape already described there; what is worth drawing out is the shared-source boundary and the laser Clearance.

### The shared Aramis source and the optics zone

Bernina is one of three co-equal stations (with Alvra and Cristallina) on one Aramis source, beam routed to one at a time (TOPO-1). The `SAROP21` optics hutch conditions the beam on the way to Bernina, but the source upstream of it is shared. That makes the optics-hutch Zone a shared-access boundary, the same question Alvra's optics hutch and LCLS-MFX's front-end / transport zone raise: who holds the permit when the beam is routed to a neighbour, and how the routing state gates each station's commands. The SwissFEL PSS search-and-secure permit signals are not in the `eco` manifest and are carried pending (PSS-1). Bernina's enclosure structure (the shared `SAROP21` optics hutch plus the Bernina experiment hutch) is carried `confirm` because the `eco` PV prefixes encode beamline-line zones, not access-gated hutches (ENC-1).

### The pump-probe laser Clearance

Bernina runs a class-4 optical laser for pump-probe. CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before laser-on work), the same posture Alvra, LCLS-MFX, and 32-ID take. This is distinct from whether the laser is a driven Asset: the device folds into the catalog `Laser` Family, while the personnel-safety permit is a Clearance. The two coexist (LASER-1).

### What is not modelled

- **Trust instantiation.** No scenario instantiates Bernina trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.
- **The Staeubli sample / detector robot as a principal or driven Asset.** The robot runs over PShell (HTTP), not EPICS, and its modelling is deferred (ROBOT-1); when it is modelled, whether an autonomous sample-handling Agent acts through it is part of that work.
- **The DAQ and acquisition software as principals.** The SwissFEL `sf-daq`, `bsread`, and the `eco` / `slic` scan suite are control-system software on the floor, not CORA actors (see [Controls](controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [PSI Site](../psi/index.md); see [Open questions](#open-questions) for the governance items still to confirm.

## Model

*The developer's by-kind index: where each CORA aggregate's Bernina content lives, how the diffraction platform composes as an Assembly rather than a Family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at Bernina |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the reciprocal-space `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### The headline: the diffraction platform is an Assembly, not a Family

Bernina's defining endstation is two reconfigurable diffraction platforms: GPS (`SARES22-GPS`, a six-circle station) and XRD (`SARES21-XRD`, a You-geometry station). The `eco` driver `bernina_diffractometers.py` builds, from literal PV suffixes, a base (gamma / mu plus translations and tilts), a 2-theta detector arm (delta / detector translation), a polarization-analyzer branch (pol / pthe / ptth), a kappa goniometer (with on-the-fly kappa-to-Eulerian eta / chi / phi conversion), a heavy-load goniometer table, and a PI hexapod, with an optional Staeubli robot contributing gamma / delta.

That is far more than the catalog `Goniometer`, the integrated single-device sample orienter that [I03](../i03/notes.md#model) graduated and [MX3](../mx3/notes.md#model) reused. But it is **exactly the graduated `Diffractometer` Assembly** that 4-ID and 8-ID earned: a composed scattering instrument that

- binds **one `Goniometer`** for the sample-orientation circles plus x / y / z centring,
- binds **zero or more `RotaryStage`** detector-arm circles (here the `delta` 2-theta arm), and
- binds **one reciprocal-space `PseudoAxis`** whose partition rule resolves the inverse kinematics (here the `SixCircleBernina` and kappa-to-You conversions).

So Bernina coins **no new Family and adds no new Assembly**. Each platform is modelled as a `Goniometer` Asset + a `PseudoAxis` Asset (and, for XRD, a `RotaryStage` detector-arm Asset), composed through the existing `Diffractometer` Assembly. The GPS and XRD platforms are its third and fourth bindings, reinforcing the 4-ID / 8-ID graduation from a third facility and, for the first time, at an XFEL (DIFF-1). The reciprocal-space partition rule (the hkl inverse kinematics, and the kappa-to-Eulerian conversion XRD adds) is the same `PartitionRule` design the synchrotron diffractometers carry, deferred here as DIFF-2.

### Deliberately not here yet: the externalized configuration (CONFIG-1)

This is the boundary that makes Bernina a partial first cut, and it is a different boundary from i13-1's. At i13-1 the upstream source was simply absent from the public module. At Bernina the device **list** and the diffractometer **axis topology** are public (in `bernina.py` and `bernina_diffractometers.py`), but the **configuration state** is loaded at runtime from non-public PSI files:

- `eco/bernina/config.py`'s entire `components` device list is commented out and `extend`-ed from `/sf/bernina/config/eco/bernina_config_eco.json` (not in the repo).
- `bernina.py` reads `/sf/bernina/config/eco/configuration/bernina_config.json` for the per-diffractometer flags that decide **which sub-assemblies are mounted** (base / arm / polana / kappa / heavy-load / hexapod / robot) and **which detectors attach to each diffractometer**.

So CORA can model the platforms' shape but not their current instantiation: the inventory carries the recoverable devices, and the mount state and detector wiring are carried unknown, not guessed (CONFIG-1). This is the honest scope line, and it is recorded so a later cut (or a staff confirmation) can fill it without re-deriving the topology.

### The architectural gap register (shared with the other XFELs)

These are the same deferrals Alvra and LCLS-MFX recorded; Bernina re-confirms them on a diffraction platform rather than a spectroscopy one, which is itself the point (the gaps are about acquisition, not technique).

- **One switched Aramis source feeding co-equal stations (TOPO-1).** Now concrete: Bernina is the second root Unit on the same source as Alvra. Two co-equal Units sharing one upstream source has no home except the `Supply("PhotonBeam")` seam, and the routing state has no model.
- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The `sf-daq` records a free-running `bsread` stream of per-shot frames correlated by pulse-ID; CORA's poll-to-Done acquisition has no representation for it. The Run stays the provenance envelope and the per-shot plane is a referenced `Dataset`.
- **Beam-synchronous event-system timing (TIMING-1).** The SwissFEL master timing, CTA sequencer, and EVR receivers gate acquisition at beam rate; `TimingController` carries the device but the trigger pattern has no typed home.
- **Femtosecond pump-probe synchronization (LASER-1).** The `eco` `lxt` timing chain and the PSEN arrival-time monitor hold and correct the laser-to-X-ray delay; CORA's single-domain `PartitionRule` cannot express the cross-timing-domain sync. The laser folds (catalog `Laser`); the sync is the gap.

### What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** Bernina earns no catalog change; the pump-probe and diffraction recipes are carried pending on the [PSI Practices](../psi/index.md). No catalog Model is bound.
- **The Staeubli TX200 robot (ROBOT-1).** The sample / detector handling robot runs over PShell (HTTP), not EPICS, and its modelling is deferred, the same posture I03 and MX3 take for their sample-exchange arms.
- **The RIXS / tape-drive / liquid-jet sample environments (ENV-1).** `eco` defines these but their appends are commented out, so they are not in the live module; deferred, not invented.
- **The eco cross-line reference (XREF-1).** A live Bernina profile monitor (`prof_mirr_alv1`) carries an Alvra-line PV (`SAROP11-PPRM066`); whether that is a real shared device or a copy-paste residue is carried as an open question.
- **Integration scenarios.** No `test_bernina_*.py` registers Bernina Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.

## Open questions

*What CORA needs the PSI team (and PSI's documentation) to confirm before the model can be trusted.*

Bernina is modelled from PSI's open [`eco`](https://github.com/paulscherrerinstitute/eco) controls library, treated as a dry, correct DATA source: the device list with PV prefixes comes from the live `eco/bernina/bernina.py`, and the diffractometer motor-axis topology from `eco/endstations/bernina_diffractometers.py`. That gives the device shape and the EPICS PV prefixes at high confidence. It does not give the configuration state, the motor units or limits, the Aramis source parameters, the PSS safety structure, or the Capability / Method binding. This page collects what `eco` cannot supply. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

The defining Bernina question is **CONFIG-1**: unlike Alvra, Bernina's live device list and per-diffractometer configuration are loaded from non-public PSI files, so this is a deliberately partial first cut.

### Scope, configuration, topology, and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is Bernina (or any SwissFEL station) actually intended to enter CORA scope, or is this a generalization exercise against an open controls source? | A generalization exercise: Bernina extends the PSI / XFEL exercise to a second station on the shared source and to a diffraction platform; it is not on the pilot roadmap. | Whether PSI is a real Site or a modelling fixture. |
| CONFIG-1 | Blocks-build | `eco` loads Bernina's authoritative device list from `/sf/bernina/config/eco/bernina_config_eco.json` and the per-diffractometer configuration (which of base / arm / polana / kappa / heavy-load / hexapod / robot sub-assemblies are mounted, and which detector attaches to each) from `/sf/bernina/config/eco/configuration/bernina_config.json`, neither in the public repo. What is the current configuration? | The device list and diffractometer axis topology are taken from the public inline source; the mount state and detector wiring are carried unknown, not invented. | The full device list and the per-diffractometer mount + detector state. |
| TOPO-1 | Blocks-build | One linac and Aramis undulator line feed the Alvra, Bernina, and Cristallina stations, beam routed to one at a time. Should each station be its own root Unit sharing an upstream source, and where does the shared switched source live? Bernina is the second such station, so this is now concrete, not hypothetical. | One `Bernina` root Unit owning its source for now; the shared, switched FEL source has no model and is carried as this question. The `Supply("PhotonBeam")` seam is the candidate home. | One-vs-many root Units and where the shared source and its routing state are modelled. |
| PSS-1 | Blocks-build | What are the SwissFEL PSS search-and-secure permit signals, and the interlock for the pump-probe laser? | Both enclosures exist with permit signals to be named; `eco` does not carry them. | The Enclosure permit signals and the laser-safety interlock. |
| ENC-1 | Blocks-build | Which enclosure does each device sit in? `eco` prefixes encode beamline-line zones (`SARFE10`, `SAROP21`, `SARES2x` / `SLAAR21`), not the access-gated hutch or its safety meaning. | The shared `SAROP21` optics hutch plus the Bernina experiment hutch. | The per-device Enclosure assignment. |

### Source, optics, and attenuation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the Aramis undulator line parameters and the per-shot photon-energy mechanism? The `eco` manifest carries the downstream device handles, not the source. | A SASE FEL undulator; per-shot photon energy is a DAQ datum, not a standing setpoint; energy-to-gap control is deferred. | The `Undulator` parameters and the per-shot energy mechanism. |
| MACHINE-1 | Nice-to-have | SwissFEL is a linac, not a storage ring, so the loose `StorageRing` family does not fit. How should machine beam be modelled? | A `PhotonBeam` Supply, not a `StorageRing` device; the per-shot pulse energy is read via the `FluxMonitor` gas / intensity monitors. | The linac machine-state modelling boundary. |
| ATT-1 | Blocks-go-live | The `AttenuatorAramis` driver selects a foil combination for a requested transmission (energy-dependent). CORA's `Filter` covers the discrete selection but not the solve. Should the deferred `Attenuable` + `SolverReference` leg graduate? | `Filter` for the discrete selection; the target-transmission solver is the deferred `Attenuable` leg. With LCLS-MFX and Alvra carrying the same solve, the rule-of-three is well past its trigger. | Whether the transmission solver is built and where. |
| MONO-1 | Nice-to-have | The double-crystal mono (ODCM098) is used for monochromatic modes; Bernina also runs pink / SASE beam mono-out. What are the crystal and axis details, and the pink-vs-mono mode boundary? | A `Monochromator` Asset, used in some modes; mode and crystal details are settings to supply. | The DCM internals and the pink-vs-mono mode model. |
| XREF-1 | Blocks-go-live | A live Bernina profile monitor (`prof_mirr_alv1`) carries an Alvra-line PV (`SAROP11-PPRM066`). Is this a real shared device, or a copy-paste residue in the library? | The Bernina-line PVs (`SAROP21-*`) are authoritative; the `SAROP11-*` reference is carried `confirm`, not silently modelled. | Whether the cross-line reference is a real Bernina dependency. |

### Endstation: the diffractometers

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The GPS six-circle and XRD You-geometry platforms compose a goniometer, a 2-theta detector arm, a polarization-analyzer branch, a kappa goniometer, a heavy-load table, and a PI hexapod. Are they correctly modelled as the graduated `Diffractometer` Assembly (Goniometer + RotaryStage detector arm + reciprocal-space PseudoAxis), and which sub-assemblies does each carry? | Both reuse the `Diffractometer` Assembly (4-ID / 8-ID), no new Family; the mounted sub-assemblies are read from the external config (CONFIG-1). | The Assembly composition and the per-platform slot bindings. |
| DIFF-2 | Nice-to-have | The reciprocal-space layer resolves hkl inverse kinematics (`SixCircleBernina`), and the XRD platform adds a kappa-to-Eulerian conversion. What is the `PartitionRule` shape for the `PseudoAxis`? | The reciprocal-space `PseudoAxis` carries a partition rule like the synchrotron diffractometers'; the kappa-to-You conversion is part of it. | The reciprocal-space partition rule. |
| ROBOT-1 | Nice-to-have | The Staeubli TX200 robot handles samples / the detector over PShell (HTTP), not EPICS. How is it modelled? | Deferred; the robot is not modelled in this cut, the same posture I03 and MX3 take for their sample-exchange arms. | The robot's modelling and its `Subject` custody thread. |
| ENV-1 | Nice-to-have | `eco` defines RIXS, tape-drive, and liquid-jet sample environments but their appends are commented out. Are they current Bernina endstation options? | Deferred; not in the live module, so not modelled, not invented. | The sample-environment variants. |

### Acquisition, timing, diagnostics, and detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DAQ-1 | Blocks-build | The SwissFEL `sf-daq` records a free-running `bsread` stream of per-shot frames tagged by pulse-ID at beam rate, correlated downstream. CORA's acquisition is a single-detector poll-to-Done loop with no pulse-ID key. How does CORA represent a DAQ run? | The Run-as-provenance-envelope is kept; the per-shot data plane lives in the SwissFEL data API, and CORA references a `Dataset`. A per-shot event-stream actuation axis is the gap, sketched in the design note, not built. Bernina is the third sighting (after LCLS-MFX and Alvra). | Whether CORA gains an event-stream acquisition axis. |
| TIMING-1 | Blocks-go-live | The SwissFEL event system (master timing, CTA sequencer, EVR receivers) gates acquisition at beam rate. CORA's `TimingController` carries the device but has no typed home for an event trigger pattern. Where does the pattern parameter live? | `TimingController` for the device; the trigger pattern is carried as opaque setpoints until a typed parameter shape is earned. | The event-system trigger-pattern parameter model. |
| LASER-1 | Blocks-go-live | The fs pump-probe needs laser-to-X-ray synchronization (the `eco` `lxt` timing chain) and PSEN jitter correction. CORA's `PartitionRule` is single-domain spatial math, with no cross-timing-domain sync; and is the laser a driven Asset or a hazard? | The laser is carried as a catalog `Laser` Family device (model-vs-hazard open); the delay stage is a `LinearStage`; the fs synchronization has no CORA model. | The pump-probe synchronization model and the laser's model-vs-hazard status. |
| DIAG-1 | Blocks-go-live | How are the intensity-position monitors (PBPS), the gas monitor, and the PSEN arrival-time monitor modelled? They present the Sensor Role. | The loose `FluxMonitor` and `Diagnostic` Sensor families reused from Alvra / I22 / 2-BM; per-shot intensity normalization is a DAQ-plane concern (DAQ-1). | The diagnostics modelling boundary. |
| DET-1 | Blocks-go-live | What is the Bernina science detector? `eco` wires a 1.5M Jungfrau (`JF01T03V01`) inline; `sf_daq_broker` lists a 16M (`JF07T32V02`) plus I0 / vacuum / fluorescence / RIXS 0.5M variants, and the `eco` / broker version strings differ (V01 vs V02). Which is in use per diffractometer? | The detector reuses `Camera`; per-shot frames flow through the `sf-daq` data plane (DAQ-1); the active variant and wiring are external (CONFIG-1) and to supply. | The detector model, the per-diffractometer wiring, and the version mismatch. |
| PULSE-1 | Nice-to-have | The X-ray pulse picker is a fast single-pulse selector folded into `Shutter`. Is a rotary pulse-picking chopper a distinct Family (the loose `Chopper` shape)? | `Shutter` Role; the Shutter-vs-Chopper distinction is carried as this question, the same one Alvra and LCLS-MFX raised. | Whether the pulse picker earns its own Family. |
