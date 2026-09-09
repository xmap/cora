# Notes

## Techniques

*What the modelled part of LIX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. LIX measures biological structure three ways: biological solution scattering (bio-SAXS / WAXS), in-line size-exclusion-chromatography-coupled scattering (SEC-SAXS), and scanning-microbeam mapping of cells and tissue. The Methods below render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings any of them into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Biological solution scattering (bio-SAXS / WAXS) | `solution_scattering` | small- and wide-angle scattering from a protein in solution in the [flow cell](sample.md), read on the [SAXS Pilatus 1M](detector.md); the fleet's first solution-scattering Method, new to the catalog (`TECH-1`) |
| In-line SEC-SAXS | `solution_scattering` | the [HPLC delivery pump](sample.md) flows an eluting size-exclusion peak through the cell while the SAXS detector reads; the same `solution_scattering` Method with the chromatographic elution as the acquisition axis (`TECH-1`, `FLUID-1`) |
| Scanning-microbeam mapping | `scanning_fluorescence_microscopy` | raster the microbeam across a cell or tissue section on the [scanning goniometer](sample.md), reading scattering and fluorescence per point; reuses the existing pending Method (`TECH-1`) |

All three techniques need the [incident-beam chain](source.md) (the undulator and DCM for energy, the mirrors and transfocator for focus, the slits), the [sample side](sample.md) (the positioning stack or scanning goniometer, and for the solution modes the fluidic delivery chain), and the [endstation detectors](detector.md) (the Pilatus heads, beamstop, flux monitors).

### Where the novelty is: the Subject, not the Method

LIX's measurement, small- and wide-angle X-ray scattering, is a science axis the fleet already speaks. The materials-scattering beamlines [SMI](../smi/notes.md#techniques), [CMS](../cms/notes.md#techniques), Diamond [I22](../i22/notes.md#techniques), and APS [9-ID](../9-id/notes.md#techniques) / [12-ID](../12-id/notes.md#techniques) all run small- and wide-angle scattering on the same `Camera` / `FluxMonitor` / `BeamStop` vocabulary. So the scattering hardware and detection are reinforcement, not novelty.

What LIX adds is a new **Subject** and a new **sample-delivery** shape, not a new detector. The specimen is a protein in solution rather than a solid mount, and for SEC-SAXS it is an eluting chromatographic peak whose elution profile is the acquisition axis. That is why `solution_scattering` is proposed as a Method distinct from the materials `small_angle_scattering`: not because the optics differ, but because the Subject and the acquisition (a flowing, time-resolved liquid correlated to chromatography) differ. Whether the catalog ultimately holds one scattering Capability with solution-versus-solid as a Practice adaptation, or a distinct `solution_scattering` Capability, is the owner-scope decision (`TECH-1`); LIX records the case, it does not mint the vocabulary.

The matching Site Practices (`LIX_solution_scattering_practice`, `LIX_sec_saxs_practice`, `LIX_microbeam_scanning_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

### SEC-SAXS is a Procedure over the fluidic seam

In-line SEC-SAXS is the technique that most exercises the fluidic delivery chain, and CORA models it as a **Procedure**, not a new device. The run equilibrates the size-exclusion column, injects the sample, and reads SAXS frames continuously while the peak elutes through the [flow cell](sample.md). The actuators it drives, the [HPLC delivery pump](sample.md) (the graduated `FlowController`) and the selector valves (the seam), are conducted over the `ControlPort`; the [column and buffers](sample.md) are Supply; the eluting peak is a Subject; the frames correlated to the elution are the Dataset. The technique's identity in CORA's record lives in the Subject, Supply, and Procedure, not in a device or a new detector (`FLUID-1`, `SEC-1`, `SUBJECT-1`).

### Not modelled yet

The concrete acquisition recipes are not written yet. For solution scattering that is the per-frame exposures, the buffer-subtraction sequence, and the azimuthal integration that turns 2D frames into I(Q) curves (the integration and reduction are `ComputePort` work, not beamline Methods). For SEC-SAXS it is the column-equilibration and injection steps, the flow program, and the peak-fraction model that maps frames to elution. For the scanning mode it is the raster trajectory and the per-point reduction. These join as the deployment approaches the point where CORA drives LIX.

Whether any of these techniques enters CORA's catalog is an owner-scope decision on [Model](#model): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at LIX, and the trust shape that will gate it. First cut.*

Governance at LIX follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

LIX is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The profile collection's access model is a POSIX-ACL `login` keyed to a proposal id, not a facility role roster, so the NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#safety-and-governance), shared with the rest of the fleet (`GOV-1`).

### The safety boundary

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are largely absent from the beamline's profile collection (only the photon-shutter enable status is present), so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

LIX adds the hazard classes that come with its instruments, and one that is distinctive: a wet, biological sample environment. Those land with the equipment and the samples that bring them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| Hard X-ray beam | the [optics](index.md) and [endstation](index.md) enclosures (XF:16IDA / B / C) (`ENC-1`) | (`PSS-1`) |
| Vacuum optics and the SAXS flight path | the [Source](source.md) walk and the detector translations | (`SUP-1`) |
| Biological samples, buffers, and pressurized fluidics | the [Sample](sample.md) delivery chain (the HPLC pump, the buffers, the flow cell) | (`FLUID-1`, `SEC-1`) |

The hard X-ray beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The vacuum extent and the cooling supply that the optics and flight path depend on are carried pending (`SUP-1`). The biological-sample and pressurized-fluidics hazards are distinctive to a life-science solution beamline and travel with the delivery chain and the Subject; they are carried pending against the fluidic questions, not invented (`FLUID-1`, `SEC-1`).

### When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives LIX, following the [2-BM governance](../2-bm/governance.md) shape. Because LIX shares the NSLS-II EPICS and ophyd floor with the rest of the fleet, it re-tests the Site and Federation kernel rather than introducing a new trust model. The one new wrinkle is the fluidic delivery chain: a Conduit would have to bind the HPLC cart's heterogeneous surfaces (the soft-IOC, the Moxa sockets) as command surfaces alongside EPICS, the same multi-transport Conduit shape the [MX3](../mx3/notes.md#governance) deployment first surfaced. The Zone groups the same optics and endstation resources the [inventory](index.md) lists; the Policies bind to the NSLS-II operator roles carried pending at the Site (`GOV-1`).

## Model

*The developer's by-kind index: where each CORA aggregate's LIX content lives, how it models a solution beamline's fluidic delivery without inventing device vocabulary, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at LIX |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes LIX new

The honest answer is: not the detector, and one real thing on the sample side. LIX measures biological structure by small- and wide-angle X-ray scattering (bio-SAXS / WAXS), in-line size-exclusion-chromatography-coupled scattering (SEC-SAXS), and scanning-microbeam mapping. The scattering hardware overlaps the fleet heavily: LIX shares its science axis and its `Camera` / `FluxMonitor` / `BeamStop` vocabulary with the materials-scattering beamlines SMI, CMS, I22, and 9-ID, and contributes reinforcement there, not novelty.

LIX's genuinely distinct contributions are above the detector and beside the sample:

- **The solution Subject.** The fleet's first life-science solution-scattering beamline measures a buffer-borne macromolecule, often an eluting chromatographic peak, rather than a solid mount. That is a new Subject shape, with its own provenance, not a new device (`SUBJECT-1`).
- **The fluidic sample-delivery chain.** An HPLC delivery pump, selector valves, a size-exclusion column, buffers, and a flow cell move the sample into the beam in lockstep with the exposure. It is the fleet's first fluidic delivery plane, and it is heterogeneous (a Moxa terminal server, the Agilent OpenLAB .NET SDK, a pcaspy soft-IOC), the MX3 non-EPICS shape extended to fluidics (`FLUID-1`).
- **The SEC-SAXS Procedure.** The run is a flow program correlated to the chromatographic elution, a Procedure over the seam plus a Subject / Supply shape, not a device (`FLUID-1`, `SEC-1`).

### No new families

LIX coins no new Family and changes nothing in the catalog.

- **16-ID is an undulator beamline** (unlike the bending-magnet CMS), so it carries an `InsertionDevice` on the spine; the machine state is also observed through the loose `StorageRing`, and the undulator detail is `SRC-1`.
- **The DCM binds `Monochromator`** (a silicon double-crystal optic, the energy law implies Si(111)); the incident energy is a `PseudoAxis` over its Bragg angle and the undulator gap.
- **The optics and detectors all reuse:** the white-beam and KB mirrors bind `Mirror`; the slits bind `Slit`; the compound refractive lens binds the graduated `Transfocator`; the shutters bind `Shutter`; the solution positioning stack binds the graduated `Manipulator`; the scanning goniometer binds `Goniometer`; the Pilatus detectors bind `Camera`; the Xspress3 binds the graduated `EnergyDispersiveSpectrometer`; the detector translations bind `LinearStage`; the beamstop binds `BeamStop`; the TetrAMM electrometers bind `FluxMonitor`; the diamond-diode / Best beam-position monitor binds the graduated catalog `PositionMonitor` (presenting `Sensor`, earned across the wide fleet that shares it, distinct from `FluxMonitor` by measuring beam position rather than flux, `DIAG-1`); the Zebra binds `TimingController`.

### The graduated FlowController Family

The one reuse worth spelling out is the HPLC delivery pump. Its CORA-facing anatomy is a settable flow / pump actuator presenting `Regulator`: a flowrate setpoint and readback, a pressure readback, and run / stop. That is exactly the graduated catalog `FlowController` Family, the continuous-setpoint flow / pump actuator that presents `Regulator` and is the settable-actuator sibling of `TemperatureController`. So the pump **reuses** the graduated `FlowController`; it coins nothing.

`FlowController` graduated into the catalog on the rule-of-three across Diamond i22, APS 7-BM, NSLS-II LIX, and NSLS-II XFP, the same way `TemperatureController`, `FluxMonitor`, and `EmissionSpectrometer` did: presenting the existing `Regulator` Role, so a YAML-and-docs change with no new Role or affordance. LIX is one of the four consumers that earned the graduation, and it now simply **binds the catalog `FlowController` Family (graduated; presents `Regulator`)**. The wider fluidic chain stays deferred (`FLUID-1`, `FLOW-1`).

### How the fluidic chain is modelled (mostly not a device)

The fluidic delivery chain is the novel axis, and only one piece of it is a device:

- the **delivery pump** is the `DeliveryPump`, binding the graduated `FlowController` (above);
- the **selector valves** (VICI column / purge / detector, the Aurora buffer valve) are the ControlPort **seam**: discrete N-position routers over Moxa TCP sockets, with no existing Family, conducted over the seam and not coined at n=1 (`FLUID-1`);
- the **SEC column and buffers** are **Supply** consumables (`SEC-1`);
- the **flow cell** is sample environment, living in an external library (lixtools), not a catalog device here (`SEC-1`, `FLUID-1`);
- the **sample robot and autosampler** are a **Procedure** over the spine plus a **Subject** custody thread, the i03 / MX3 robot precedent, not a device Family (`ROBOT-1`);
- the **solution sample / eluting peak** is a **Subject** (`SUBJECT-1`).

This is the CORA-lens decision for a solution beamline: the experiment's identity lives in the Subject (which protein, which peak), the Supply (which column, which buffers), and the Procedure (the flow program), with the pump and valves as actuators conducted over the seam. Coining `Pump` and `Valve` device Families at n=1 would mint federation vocabulary one deployment cannot earn alone; the pump reuses the graduated `FlowController` Family instead, and the valves stay in the seam pending a second fluidic beamline (`FLUID-1`).

### Deliberately not here yet

- **The selector-valve Family (`FLUID-1`).** The VICI and Aurora valves are discrete-position routers with no existing Family. Per earn-the-abstraction they are carried in the seam at n=1, no `Valve` / `SelectorValve` Family coined; a second fluidic beamline would earn the abstraction.
- **The disabled attenuator and the deferred temperature controllers.** The `Fltr:Attn` attenuator and its lookup tables are commented out in the profile collection, so no attenuator is modelled, not invented (`ATTN-1`). The sample-cell temperature controllers (the FTC100D and the SMC chiller) have their module-level instances commented out, though a solution mode instantiates an FTC100D, so this is a scope deferral; the autosampler tray temperature (`SAMPLER:TEMP`) is folded into the same deferral (`TEMP-1`).
- **The Methods.** Whether `solution_scattering` and the scanning Method enter CORA's catalog is an owner decision; the Practices render unlinked, pending. `solution_scattering` is new and `scanning_fluorescence_microscopy` is reused pending (`TECH-1`).
- **The multi-mode endstation rebinding.** The solution, scanning, and vacuum-scan modes rebind the logical sample axes across physical PVs and controllers (EPICS, XPS trajectory, SmarAct) at startup; CORA models the logical stacks and carries the active binding as a setting (`SAMPLE-1`, `SCAN-1`), not as separate Assets.
- **The third Pilatus, the Kinetix, and the viewing cameras.** The 300K WAXS1 head is disabled, the Xspress3 is optional, and the Kinetix and Prosilica cameras are not modelled in this cut (`DET-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_lix_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the LIX team to confirm before the model can be trusted.*

LIX was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/lix-profile-collection](https://github.com/NSLS2/lix-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones XF:16IDA (optics), XF:16IDB (transport), and XF:16IDC (endstation) three separate hutches? | Two enclosures: a `lix-optics` zone (folding A and B) and the `lix-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The in-vacuum undulator model, period, and length (the profile collection fits an empirical Keff(gap) curve, a 23 mm period implied, but names no device). | An `InsertionDevice` undulator, observed gap; parameters pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state LIX reads (current, fill, status); only the ring current PV is read for beam suspenders. | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut (the energy law implies Si(111)), the energy range, and the energy-partition rule coupling the Bragg angle to the undulator gap. | A double-crystal `Monochromator`; the energy is a `PseudoAxis` over the Bragg angle and the gap; the crystal cut pending. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The white-beam and KB mirror coatings, whether the KB pair is bimorph, and the bend mechanisms. | Focusing mirrors bound to `Mirror`; coatings and bend pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of each slit (the mono slit, the secondary-source aperture, the endstation guard slit). | Four-blade and center / gap slits bound to `Slit`. | The slit Asset detail. |
| CRL-1 | Nice-to-have | The compound refractive lens lens-group configuration (nine selectable groups, in / out per group) and the focal-length map. | A `Transfocator` reusing the graduated Family; the lens-group set carried as settings. | The transfocator Asset detail. |
| ATTN-1 | Nice-to-have | Is an attenuator live (the `Fltr:Attn` motors and the `Attenuator` class are commented out in the profile collection)? | No attenuator modelled; not invented. | Whether an attenuator Asset exists. |

### Sample and delivery

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The solution-mode positioning stack axes (the coarse x and z pusher are EPICS; the scan x / y are Newport-XPS trajectory axes), and how the flow cell mounts on it. | A `Manipulator` for the positioning stack; the flow cell is the fluidic seam. | The solution-stage modelling. |
| SCAN-1 | Blocks-go-live | The scanning-microbeam goniometer axes (the SmarAct stack), the fast raster axes (the XPS scan.X / scan.Y trajectory), and the tomo rotation (the XPS rot.rY). | A `Goniometer` for the SmarAct stack; the XPS trajectory axes carried as the motion-controller seam. | The scanning-stage modelling. |
| FLUID-1 | Blocks-go-live | The fluidic sample-delivery chain: the HPLC delivery pump (an Agilent quaternary pump over the .NET SDK plus a regeneration pump over a Moxa socket, fronted by the `XF:16IDC-ES{HPLC}` soft-IOC), the VICI and Aurora selector valves (Moxa TCP sockets, no EPICS), and whether the valve actuators earn a Family. | The pump binds the graduated catalog `FlowController` (presents Regulator; earned across i22 / 7-BM / LIX / XFP); the valves stay in the seam; no Valve Family coined. | The fluidic-delivery modelling; the CORA decisions are on [Model](#deliberately-not-here-yet). |
| SEC-1 | Nice-to-have | The size-exclusion column types, the buffers, the needle wash, and the X-ray flow cell (the flow cell lives in an external library, lixtools). | The column and buffers are Supply consumables; the flow cell is sample environment, not a device. | The consumable / flow-cell modelling. |
| ROBOT-1 | Nice-to-have | The sample-handling robot (the `SW:` method soft-IOC, task-verb-driven) and the Agilent autosampler, and whether they earn a Family. | Modelled as a Procedure over the spine and a Subject custody thread, the i03 / MX3 robot precedent; no `SampleExchanger` Family coined. | The sample-handling modelling. |
| SUBJECT-1 | Nice-to-have | The solution Subject: a buffer-borne macromolecule or an eluting SEC peak, with its own provenance, distinct from a solid mount. | A liquid Subject; the chromatographic peak as the acquisition axis for SEC-SAXS. | The Subject modelling. |
| TEMP-1 | Nice-to-have | The sample-cell temperature control (the FTC100D and SMC chiller module-level instances are commented out, though a solution mode instantiates an FTC100D; plus the autosampler tray temperature SAMPLER:TEMP). | No temperature-controller device modelled in this cut; the in-situ environment pending. | The temperature-environment modelling. |

### Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The SAXS / WAXS Pilatus detector models and sizes (a 1M SAXS, a 900K WAXS; a 300K WAXS1 is disabled), the Xspress3 per-run availability (initialized in a try / except), the detector-distance calibrations, and the flux / beam-position channel map. | Two `Camera` Assets (Pilatus 1M SAXS, 900K WAXS); the Xspress3 binds `EnergyDispersiveSpectrometer`; the monitors bind `FluxMonitor` and the graduated catalog `PositionMonitor`. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-position monitor: the Best aggregator deriving x / y from the TetrAMM quadrant currents, and the position-versus-intensity channel split. The Family is settled (graduated catalog Family presenting `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux). | The graduated catalog `PositionMonitor`, earned across the wide fleet that shares it; the per-Asset channel split is the residual. | The beam-position channel split. |
| TRIG-1 | Blocks-go-live | The exposure triggering: the Zebra soft-input pulse and position capture, gated from the Newport XPS, and the fast-shutter TTL. | A `TimingController` (the Zebra); the fast shutter a `Shutter` on the timing seam. | The triggering modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and is the data plane Kafka plus Redis plus a custom packing queue (no Tiled, no queueserver in the profile collection)? | The handles in the descriptor are taken from the profile collection and carried confirm; the data plane is the seam CORA's edge replaces. | Verifying each Asset's control handle and the data plane. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals, the front-end and photon shutters (only the photon-shutter enable status is in the profile collection; the security model there is a POSIX-ACL login). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the optics, the SAXS flight path) and the cooling supply. | Photon beam, cooling water, and vacuum on the optics and flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do the solution-scattering and scanning techniques (bio-SAXS / WAXS, SEC-SAXS, microbeam mapping) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; `solution_scattering` is new and `scanning_fluorescence_microscopy` is reused pending; none coined. | The technique Capabilities. |
