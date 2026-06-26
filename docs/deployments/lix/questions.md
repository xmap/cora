# Open questions

*What CORA needs the LIX team to confirm before the model can be trusted.*

LIX was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/lix-profile-collection](https://github.com/NSLS2/lix-profile-collection)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `startup/` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones XF:16IDA (optics), XF:16IDB (transport), and XF:16IDC (endstation) three separate hutches? | Two enclosures: a `lix-optics` zone (folding A and B) and the `lix-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The in-vacuum undulator model, period, and length (the profile collection fits an empirical Keff(gap) curve, a 23 mm period implied, but names no device). | An `InsertionDevice` undulator, observed gap; parameters pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state LIX reads (current, fill, status); only the ring current PV is read for beam suspenders. | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut (the energy law implies Si(111)), the energy range, and the energy-partition rule coupling the Bragg angle to the undulator gap. | A double-crystal `Monochromator`; the energy is a `PseudoAxis` over the Bragg angle and the gap; the crystal cut pending. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The white-beam and KB mirror coatings, whether the KB pair is bimorph, and the bend mechanisms. | Focusing mirrors bound to `Mirror`; coatings and bend pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of each slit (the mono slit, the secondary-source aperture, the endstation guard slit). | Four-blade and center / gap slits bound to `Slit`. | The slit Asset detail. |
| CRL-1 | Nice-to-have | The compound refractive lens lens-group configuration (nine selectable groups, in / out per group) and the focal-length map. | A `Transfocator` reusing the graduated Family; the lens-group set carried as settings. | The transfocator Asset detail. |
| ATTN-1 | Nice-to-have | Is an attenuator live (the `Fltr:Attn` motors and the `Attenuator` class are commented out in the profile collection)? | No attenuator modelled; not invented. | Whether an attenuator Asset exists. |

## Sample and delivery

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The solution-mode positioning stack axes (the coarse x and z pusher are EPICS; the scan x / y are Newport-XPS trajectory axes), and how the flow cell mounts on it. | A `Manipulator` for the positioning stack; the flow cell is the fluidic seam. | The solution-stage modelling. |
| SCAN-1 | Blocks-go-live | The scanning-microbeam goniometer axes (the SmarAct stack), the fast raster axes (the XPS scan.X / scan.Y trajectory), and the tomo rotation (the XPS rot.rY). | A `Goniometer` for the SmarAct stack; the XPS trajectory axes carried as the motion-controller seam. | The scanning-stage modelling. |
| FLUID-1 | Blocks-go-live | The fluidic sample-delivery chain: the HPLC delivery pump (an Agilent quaternary pump over the .NET SDK plus a regeneration pump over a Moxa socket, fronted by the `XF:16IDC-ES{HPLC}` soft-IOC), the VICI and Aurora selector valves (Moxa TCP sockets, no EPICS), and whether the pump / valve actuators earn a Family. | The pump binds the existing loose `FlowController` (i22 / 7-BM, n=3, graduation candidate); the valves stay in the seam; no Valve Family coined. | The fluidic-delivery modelling; the CORA decisions are on [Model](model.md#deliberately-not-here-yet). |
| SEC-1 | Nice-to-have | The size-exclusion column types, the buffers, the needle wash, and the X-ray flow cell (the flow cell lives in an external library, lixtools). | The column and buffers are Supply consumables; the flow cell is sample environment, not a device. | The consumable / flow-cell modelling. |
| ROBOT-1 | Nice-to-have | The sample-handling robot (the `SW:` method soft-IOC, task-verb-driven) and the Agilent autosampler, and whether they earn a Family. | Modelled as a Procedure over the spine and a Subject custody thread, the i03 / MX3 robot precedent; no `SampleExchanger` Family coined. | The sample-handling modelling. |
| SUBJECT-1 | Nice-to-have | The solution Subject: a buffer-borne macromolecule or an eluting SEC peak, with its own provenance, distinct from a solid mount. | A liquid Subject; the chromatographic peak as the acquisition axis for SEC-SAXS. | The Subject modelling. |
| TEMP-1 | Nice-to-have | The sample-cell temperature control (the FTC100D and SMC chiller module-level instances are commented out, though a solution mode instantiates an FTC100D; plus the autosampler tray temperature SAMPLER:TEMP). | No temperature-controller device modelled in this cut; the in-situ environment pending. | The temperature-environment modelling. |

## Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The SAXS / WAXS Pilatus detector models and sizes (a 1M SAXS, a 900K WAXS; a 300K WAXS1 is disabled), the Xspress3 per-run availability (initialized in a try / except), the detector-distance calibrations, and the flux / beam-position channel map. | Two `Camera` Assets (Pilatus 1M SAXS, 900K WAXS); the Xspress3 binds `EnergyDispersiveSpectrometer`; the monitors bind `FluxMonitor` and the loose `BeamPositionMonitor`. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-position monitor: the Best aggregator deriving x / y from the TetrAMM quadrant currents, and the position-versus-intensity split (the fleet-wide question). | A loose `BeamPositionMonitor` (held under review across 4-ID / 8-ID / 9-ID / ISS / FMX). | The beam-position-monitor catalog home. |
| TRIG-1 | Blocks-go-live | The exposure triggering: the Zebra soft-input pulse and position capture, gated from the Newport XPS, and the fast-shutter TTL. | A `TimingController` (the Zebra); the fast shutter a `Shutter` on the timing seam. | The triggering modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and is the data plane Kafka plus Redis plus a custom packing queue (no Tiled, no queueserver in the profile collection)? | The handles in the descriptor are taken from the profile collection and carried confirm; the data plane is the seam CORA's edge replaces. | Verifying each Asset's control handle and the data plane. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals, the front-end and photon shutters (only the photon-shutter enable status is in the profile collection; the security model there is a POSIX-ACL login). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the optics, the SAXS flight path) and the cooling supply. | Photon beam, cooling water, and vacuum on the optics and flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do the solution-scattering and scanning techniques (bio-SAXS / WAXS, SEC-SAXS, microbeam mapping) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; `solution_scattering` is new and `scanning_fluorescence_microscopy` is reused pending; none coined. | The technique Capabilities. |
