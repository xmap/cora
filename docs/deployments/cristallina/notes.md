# Notes

## Techniques

*What Cristallina is designed to do, as design intent. Design-phase: these are Methods CORA would earn, not Methods it has.*

Cristallina runs two technique families, neither of which fits the catalog's tomography Methods, so each is carried pending on the [PSI Practices](../psi/index.md) until it is earned. They are listed here as design intent, with the shape each would take over the spine and the gap each leans on.

### Time-resolved hard X-ray diffraction and scattering (quantum materials)

Cristallina's reason for existing. The Cristallina-Q endstation studies quantum materials: their structural and electronic response is read by diffraction and scattering, shot by shot, in a controlled low-temperature, high-magnetic-field environment. The sample is oriented and the detector positioned by the DM1 dilution-fridge or DM2 pulsed-magnet diffractometer, inside the DilSc dilution refrigerator and its vector superconducting magnet.

- **Spine shape:** a `diffraction` Method binding the diffractometer (a `Goniometer` for the sample circles, a `RotaryStage` 2-theta detector arm, and a reciprocal-space `PseudoAxis`), composed through the graduated `Diffractometer` Assembly (DIFF-1), over a per-shot acquisition, with the sample-environment state (temperature from the LakeShore 372, field from the vector magnet) as conditions. It shares the `diffraction` Method Bernina introduced.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1). A time-resolved diffraction run is a free-running shot stream tagged by pulse-ID, not a trajectory of points. The diffractometer is covered by the existing Assembly, and the sample environment by the `TemperatureController` Family and the graduated `Magnet` Family; the acquisition is the gap.

The vector magnet is what distinguishes Cristallina-Q from Bernina's diffraction: the experiment sweeps not just delay and orientation but a three-axis magnetic field, in a dilution-fridge temperature regime. That sample environment is modelled (the LakeShore as `TemperatureController`, the magnet as the graduated `Magnet` Family, a further consumer, MAG-1) and gated by a Clearance hazard, but it adds no new technique-modelling shape beyond the conditions a Run already carries.

### Serial femtosecond crystallography

The Cristallina-MX endstation runs serial crystallography: microcrystals are delivered onto the fast XY sample stage and each X-ray pulse records a single-shot diffraction pattern. It shares the `serial_crystallography` Method LCLS-MFX and Alvra carry.

- **Spine shape:** a `serial_crystallography` Method binding the fast sample stage, the focusing optics, and the 8M Jungfrau, over a free-running per-shot acquisition.
- **Gap it leans on:** the per-shot, pulse-ID-tagged event DAQ (DAQ-1), the same as for the other XFEL serial-crystallography exercises. The sample delivery beyond the fast stage is endstation-specific and deferred (SAMPLE-1).

### Why neither is in the catalog yet

The catalog's Methods are all tomography-family. An XFEL diffraction / crystallography station shares none of them, and coining XFEL Methods now, before the per-shot acquisition axis they depend on exists (DAQ-1), would be inventing recipes for a spine that cannot yet run them. So each is carried pending, reusing the Method name Bernina or LCLS-MFX named for it. That a third PSI station, on a different controls library (`slic`) and with a novel sample environment (the vector magnet), reaches the same acquisition gaps is the reinforcement Cristallina adds: the gaps are about the XFEL acquisition paradigm, not the technique or the controls house style. See [Model](#model) for the gap register, the `Diffractometer` Assembly design, and the `Magnet` rule-of-three.

## Governance

*Who would act at Cristallina and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

Cristallina's principals are facility principals at the [PSI Site](../psi/index.md), not beamline-local: the SwissFEL instrument-scientist and operator pool, and the PSI safety-review body. Both are carried pending in the [site descriptor](../psi/index.md) until the PSI structure is confirmed; the `slic` device library is a controls library, not an organizational record, so it exposes no human roster (GOV-1). CORA's role kernel (the five-role authorization model) is facility-invariant, so Cristallina inherits it. Cristallina shares its Site, its Aramis source, and its safety posture with the sibling [Alvra](../alvra/notes.md#governance) and [Bernina](../bernina/notes.md#governance) stations, so most of the governance shape is the PSI-Site shape; what is worth drawing out is the shared-source boundary and the high-field-magnet hazard.

### The shared Aramis source and the optics zone

Cristallina is the third of three co-equal stations (with Alvra and Bernina) on one Aramis source, beam routed to one at a time (TOPO-1). The `SAROP31` optics hutch conditions the beam on the way to Cristallina, but the source upstream is shared. That makes the optics-hutch Zone a shared-access boundary, the same question Alvra and Bernina raise: who holds the permit when the beam is routed to a neighbour, and how the routing state gates each station's commands. With three stations now modelled on the one source, the routing state is a three-way selection, not a pair. The SwissFEL PSS search-and-secure permit signals are not in the `slic` manifest and are carried pending (PSS-1). Cristallina's enclosure structure (the shared `SAROP31` optics hutch plus the Cristallina experiment hutch) is carried `confirm` because the `slic` PV prefixes encode beamline-line zones, not access-gated hutches (ENC-1).

### The high-field-magnet Clearance

Cristallina's defining hazard is not a laser (the `slic` source has no pump-probe laser, LASER-1) but the **vector superconducting magnet** and its cryogens. The DilSc dilution refrigerator runs an Oxford Mercury iPS magnet to 5.2 Tesla on the z-axis, cooled by liquid helium. CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before high-field work), the same posture [ESRF ID32](../id32/notes.md#governance) takes for its 9 T XMCD magnet and its liquid-helium plant. This is distinct from whether the magnet is a driven Asset: the device binds the graduated `Magnet` Family (a further consumer, the per-Asset field detail pending, MAG-1), while the personnel- and quench-safety permit is a Clearance. The two coexist, the same way the laser device and the laser Clearance coexist at Alvra and Bernina.

### What is not modelled

- **Trust instantiation.** No scenario instantiates Cristallina trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.
- **The magnet as a safety-driven Asset.** The vector magnet is modelled as a hazard via a Clearance, not as an Asset CORA drives for safety (the ID32 magnet and the Alvra / Bernina laser precedent). Its field setpoints are an experiment concern; its safety is a permit.
- **The DAQ and acquisition software as principals.** The SwissFEL `sf-daq`, `bsread`, and the `slic` scan suite are control-system software on the floor, not CORA actors (see [Controls](controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [PSI Site](../psi/index.md); see [Open questions](#open-questions) for the governance items still to confirm.

## Model

*The developer's by-kind index: where each CORA aggregate's Cristallina content lives, how the diffractometers reuse the graduated Assembly and the vector magnet binds an earned Family, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at Cristallina |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the reciprocal-space `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### The headline: no new Family, three things tested

Cristallina coins **no new Family**, the same finding as Alvra and Bernina. But it tests the model against three things the prior PSI stations did not have, and the interest is in how each is absorbed by existing shapes.

#### The diffractometers reuse the graduated Assembly (DIFF-1)

Cristallina-Q has two diffraction platforms: DM1 (the dilution-fridge diffractometer, `SARES31-GPS`) and DM2 (the pulsed-magnet diffractometer, `SARES32-GPS`). Both are built by the `slic` `Diffractometer` driver from ECMC servo-motor axes (twotheta / theta plus base and sample translations; DM2 adds rot_x / rot_z swivels). As at [Bernina](../bernina/notes.md#model), each is the graduated [`Diffractometer` Assembly](../../catalog/assemblies.md): a composed `Goniometer` (the sample circles) plus a `RotaryStage` detector-arm circle plus a reciprocal-space `PseudoAxis`. The GPS / XRD platforms at Bernina were the Assembly's third and fourth bindings; the Cristallina DM1 / DM2 are its fifth and sixth. No new Family or Assembly is coined (DIFF-1; the reciprocal-space partition rule is DIFF-2). DM2's PV channels are commented out of the active `slic` config, so it is carried as present-hardware-not-acquired (DISABLED-1).

#### The vector magnet is a further `Magnet` consumer (MAG-1)

The DilSc sample environment is a dilution refrigerator with a 3-axis vector superconducting magnet (an Oxford Mercury iPS, field limits X,Y = ±0.6 T and Z = ±5.2 T). The magnet binds the **graduated `Magnet`** Family, whose rule-of-three was earned across 4-ID, i10-1, and ESRF ID32 (the 9 T XMCD magnet). Cristallina is a **further consumer**, binding the catalog Family like any other (MAG-1 now covers only the per-Asset field ranges and control handles). The `Magnet` Family presents the `Regulator` Role, the field a settable process variable, and the LakeShore 372 thermometry / heater binds the **graduated `TemperatureController`** Family (also presents the Regulator Role), the ID32 VTI precedent. The vector geometry (three independently-ramped field axes) is a richer setting than the single-axis magnets, but it is a per-Asset setting, not a Family split, the same way the diffractometer axis counts are.

#### The absent pump-probe laser (LASER-1, reframed)

Alvra and Bernina each carry a pump-probe `Laser` and an arrival-time monitor. Cristallina's `slic` source has neither: no `SLAAR` / `PALM` / `PSEN` devices appear, and the only laser is the X-ray alignment laser (`SAROP31-OLAS147`, a catalog `Laser`). Pump-probe timing is mediated by the CTA sequencer (`SAR-CCTA-ESC`) and the EVR, with a server-side pulse-tube synchronization service (`oscillations.psi.ch`). So this cut models no pump-probe-laser Asset. Whether Cristallina has a pump-probe laser in a different controls layer (as Alvra and Bernina do in `eco`'s `loptics`) is carried as an open question rather than invented (LASER-1).

### The provenance boundary: slic, in-repo

Cristallina is CORA's first deployment mined from `slic` rather than `eco`. The boundary is cleaner than Bernina's: where Bernina's `eco` config loaded its device list from a non-public JSON, Cristallina's `slic` repo keeps the device identities, axes, and PV prefixes as in-repo Python literals. What is non-public is only runtime state, not device definitions: the working directory and data paths, a PSSS motion helper script, the DilSc SECoP / Frappy magnet server (`dilsc.psi.ch:5000`, an alternative to the live EPICS driver), and the pulse-tube synchronization HTTP service (server-side). Those are recorded under `software_iocs_not_modeled` and ENV-1, not modelled.

One provenance caution shapes the inventory: many `slic` drivers are instantiated but their PV channels are commented out of the active tuples (DM2, several SmarAct stages, the Attocube, the PuMa stack, the cameras). These are carried as present-hardware-not-acquired where carried at all (DISABLED-1), not as live Assets.

### The architectural gap register (shared with the other XFELs)

These are the same deferrals Alvra and Bernina recorded; Cristallina re-confirms them a third time at PSI, now in a vector-magnet diffraction context.

- **One switched Aramis source feeding co-equal stations (TOPO-1).** Now the full triad: Cristallina is the third root Unit on the same source as Alvra and Bernina. Three co-equal Units sharing one upstream source has no home except the `Supply("PhotonBeam")` seam, and the routing state has no model.
- **Per-shot, pulse-ID-tagged event DAQ (DAQ-1).** The `sf-daq` records a free-running `bsread` stream of per-shot frames; CORA's poll-to-Done acquisition has no representation for it. The Run stays the provenance envelope and the per-shot plane is a referenced `Dataset`.
- **Beam-synchronous event timing (TIMING-1).** The CTA sequencer and EVR gate acquisition at beam rate (and here also mediate the pump-probe delay, in the absence of a laser device); `TimingController` carries the device but the trigger pattern has no typed home.

### What is deliberately not here yet (modelling, as at the other exercises)

- **New Capabilities / Methods and vendor Models.** Cristallina earns no catalog change; the diffraction and serial-crystallography recipes are carried pending on the [PSI Practices](../psi/index.md). No catalog Model is bound.
- **The pump-probe laser layer (LASER-1).** Absent from `slic`; not invented.
- **The vector-magnet field ranges and control handles (MAG-1).** The `Magnet` Family has graduated (Cristallina is a further consumer); only the per-Asset field detail stays pending.
- **The disabled stages (DISABLED-1).** DM2, the SmarAct / Attocube / PuMa stages, and the cameras are instantiated but commented out of the active config; carried as present-hardware, not live Assets.
- **The serial-crystallography sample delivery (SAMPLE-1).** Beyond the fast XY stage, the Cristallina-MX delivery is deferred.
- **The transmission-readback cross-reference (XREF-1).** The front-end attenuator's transmission readbacks alias to `SAROP31-OATT053`; carried `confirm`.
- **Integration scenarios.** No `test_cristallina_*.py` registers Cristallina Assets. Hard-registering a design-phase, off-roadmap, XFEL beamline would commit speculative structure.

## Open questions

*What CORA needs the PSI team (and PSI's documentation) to confirm before the model can be trusted.*

Cristallina is modelled from PSI's open [`slic`](https://gitea.psi.ch/slic/cristallina) controls library (on `gitea.psi.ch`, branch `master`), treated as a dry, correct DATA source: the device list with PV prefixes comes from the in-repo `channels/pv_channels.py`, and the diffractometer and sample-environment topology from the `beamline/` and `crq_exp/` driver classes. That gives the device shape and the EPICS PV prefixes at high confidence. It does not give most motor units or limits, the Aramis source parameters, the PSS safety structure, or the Capability / Method binding. This page collects what `slic` cannot supply. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

Unlike Bernina, Cristallina's device facts are in-repo (not externalized), so this is a fuller cut; the residual questions concentrate on the XFEL acquisition paradigm, the novel sample environment, and a few `slic`-specific provenance cautions.

### Scope, topology, and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCOPE-1 | Nice-to-have | Is Cristallina (or any SwissFEL station) actually intended to enter CORA scope, or is this a generalization exercise against an open controls source? | A generalization exercise: Cristallina closes the Aramis triad and tests a `slic`-mined deployment and a vector-magnet sample environment; it is not on the pilot roadmap. | Whether PSI is a real Site or a modelling fixture. |
| TOPO-1 | Blocks-build | One linac and Aramis undulator line feed the Alvra, Bernina, and Cristallina stations, beam routed to one at a time. With three co-equal stations now modelled, should each be its own root Unit sharing an upstream source, and where does the shared switched source and its three-way routing state live? | One `Cristallina` root Unit owning its source for now; the shared, switched FEL source has no model and is carried as this question. The `Supply("PhotonBeam")` seam is the candidate home. | One-vs-many root Units and where the shared source and its routing state are modelled. |
| PSS-1 | Blocks-build | What are the SwissFEL PSS search-and-secure permit signals, and the interlock for the high-field magnet? | Both enclosures exist with permit signals to be named; `slic` does not carry them. | The Enclosure permit signals and the magnet-safety interlock. |
| ENC-1 | Blocks-build | Which enclosure does each device sit in? `slic` separates an optics hutch from an experimental hutch but does not encode the access-gated safety meaning. | The shared `SAROP31` optics hutch plus the Cristallina experiment hutch. | The per-device Enclosure assignment. |
| MAG-1 | Blocks-go-live | The DilSc vector superconducting magnet (to 5.2 T) and its liquid-helium cryogens are a personnel- and quench-safety hazard. How is the hazard gated, and what are the per-axis field ranges and control handles? | The magnet is a `Clearance` hazard (the ID32 precedent), and binds the graduated `Magnet` Family (a further consumer); the per-Asset field detail stays pending. | The magnet-hazard Clearance and the per-Asset magnet field / control detail. |

### Source, optics, and attenuation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-build | What are the Aramis undulator gap tables and source size? `slic` carries the period (15 mm) and the K-to-energy constants but not the full source curve. | A SASE FEL undulator; per-shot photon energy (5-13 keV) is a DAQ datum, not a standing setpoint. | The `Undulator` source parameters. |
| MACHINE-1 | Nice-to-have | SwissFEL is a linac, not a storage ring. How should machine beam be modelled? | A `PhotonBeam` Supply, not a `StorageRing` device; the per-shot pulse energy is read via the gas monitor. | The linac machine-state modelling boundary. |
| ATT-1 | Blocks-go-live | The `aramis_attenuator` driver selects a foil combination for a requested transmission (energy-dependent). Should the deferred `Attenuable` + `SolverReference` leg graduate? | `Filter` for the discrete selection; the target-transmission solver is the deferred `Attenuable` leg. With Alvra, Bernina, and Cristallina all carrying it, the rule-of-three is well past its trigger. | Whether the transmission solver is built and where. |
| MONO-1 | Nice-to-have | The mono is a double-channel-cut (DCCM, `ODCC110`), distinct from Bernina's DCM. What are the crystal and axis details, and the pink-vs-mono mode boundary (the mono screen selects out / mono / pink)? | A `Monochromator` Asset, used in some modes; mode and crystal details are settings to supply. | The DCCM internals and the pink-vs-mono mode model. |
| XREF-1 | Nice-to-have | The front-end attenuator's transmission readbacks alias to `SAROP31-OATT053`. Is the front-end attenuator (`SARFE10-OATT053`) the same device read through the Cristallina-branch namespace, or two devices? | The `SARFE10-OATT053` front-end attenuator is the modelled device; the `SAROP31` alias is a readback, carried `confirm`. | Whether the attenuator readback alias is one device or two. |

### Endstation: diffractometers and the sample environment

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The DM1 (dilution-fridge) and DM2 (pulsed-magnet) platforms compose a goniometer, a 2-theta detector arm, and base / sample translations (DM2 adds swivels). Are they correctly modelled as the graduated `Diffractometer` Assembly, and is DM2 currently live? | Both reuse the `Diffractometer` Assembly (Bernina precedent), no new Family; DM2's PV channels are commented out in `slic`, so it is carried as present-hardware-not-acquired (DISABLED-1). | The Assembly composition and DM2's live status. |
| DIFF-2 | Nice-to-have | What is the `PartitionRule` shape for the reciprocal-space `PseudoAxis`? | The reciprocal-space `PseudoAxis` carries a partition rule like the synchrotron diffractometers'. | The reciprocal-space partition rule. |
| LASER-1 | Blocks-go-live | The `slic` source has no pump-probe laser (only the X-ray alignment laser `SAROP31-OLAS147`); pump-probe timing is mediated by the CTA sequencer and EVR. Does Cristallina have a pump-probe optical laser in another controls layer? | No pump-probe-laser Asset is modelled in this cut; the alignment laser is a catalog `Laser`. Whether a pump-probe laser exists elsewhere is carried as this question. | Whether a pump-probe laser exists and where it is controlled. |
| DISABLED-1 | Nice-to-have | Several `slic` drivers are instantiated but their PV channels are commented out of the active config (DM2, the SmarAct Juraj / mini stages, the Attocube, the PuMa stack, the cameras). Which are live hardware? | Carried as present-hardware-not-acquired; not modelled as live Assets in this cut. | Which disabled stages are current hardware. |
| ENV-1 | Nice-to-have | The DilSc magnet has an alternative SECoP / Frappy driver (`dilsc.psi.ch:5000`) and the pulsed-magnet uses a server-side pulse-tube synchronization service (`oscillations.psi.ch:8000`). Are these in the operational path? | The live EPICS magnet driver is modelled; the SECoP path and the sync service are server-side and not modelled. | The magnet control path and the pulse-tube sync. |

### Acquisition, timing, diagnostics, and detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DAQ-1 | Blocks-build | The SwissFEL `sf-daq` records a free-running `bsread` stream of per-shot frames tagged by pulse-ID at beam rate, correlated downstream. CORA's acquisition is a single-detector poll-to-Done loop with no pulse-ID key. How does CORA represent a DAQ run? | The Run-as-provenance-envelope is kept; the per-shot data plane lives in the SwissFEL data API, and CORA references a `Dataset`. A per-shot event-stream actuation axis is the gap, sketched in the design note, not built. Cristallina is the third PSI sighting. | Whether CORA gains an event-stream acquisition axis. |
| TIMING-1 | Blocks-go-live | The CTA sequencer (`SAR-CCTA-ESC`) and EVR gate acquisition at beam rate and mediate the pump-probe delay. CORA's `TimingController` carries the device but has no typed home for an event trigger pattern. Where does the pattern parameter live? | `TimingController` for the device; the trigger pattern is carried as opaque setpoints until a typed parameter shape is earned. | The event-system trigger-pattern parameter model. |
| DIAG-1 | Blocks-go-live | How are the intensity-position monitors (PBPS), the gas monitor (PBPG), and the photon single-shot spectrometer (PSSS) modelled? They present the Sensor Role. | The loose `FluxMonitor` and `Diagnostic` Sensor families reused from Alvra / Bernina / I22; per-shot intensity normalization is a DAQ-plane concern (DAQ-1). | The diagnostics modelling boundary. |
| DET-1 | Blocks-go-live | What are the Cristallina detectors per configuration? `slic` binds a 1.5M Jungfrau (`JF16T03V02`) + a 0.5M I0 (`JF20T01V01`) for Q and an 8M (`JF17T16V01`) for MX; the human-readable labels come from a commented `sf_daq_broker` block. Which is in use, and its geometry? | The detectors reuse `Camera`; per-shot frames flow through the `sf-daq` data plane (DAQ-1); the active config and geometry are to supply. | The detector models, the per-config wiring, and the labels. |
| SAMPLE-1 | Nice-to-have | What is the Cristallina-MX sample-delivery shape beyond the fast XY stage, and the `Subject` custody lifecycle? | Sample delivery beyond the fast stage is endstation-specific and deferred; no Family is coined. | The sample-delivery model and the `Subject` custody thread. |
| PULSE-1 | Nice-to-have | The X-ray pulse picker is a fast single-pulse selector folded into `Shutter`. Is a rotary pulse-picking chopper a distinct Family? | `Shutter` Role; the Shutter-vs-Chopper distinction is carried as this question, the same one Alvra and Bernina raised. | Whether the pulse picker earns its own Family. |
