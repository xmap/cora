# Notes

## Techniques

*What ISR is designed to do, as intent. A deliberately partial first cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. ISR's mission is hard X-ray resonant scattering and surface / interface diffraction, with in-situ sample environments. The Methods below render unlinked and are **doubly deferred**: the Methods themselves are pending, and the multi-circle diffractometer they run on is absent from the source (`TECH-1`, `DIFF-1`).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant scattering | `resonant_scattering` | resonant elastic scattering near an absorption edge; reuses the Method APS [4-ID](../4-id/notes.md#techniques) (POLAR) and [CSX](../csx/notes.md#techniques) left pending; needs a tunable energy axis and a diffractometer, both absent from source (`TECH-1`, `RESONANT-1`, `DIFF-1`) |
| Surface / interface diffraction | `diffraction` | crystal truncation rods and surface structure; reuses the `diffraction` Method 4-ID / [8-ID](../8-id/notes.md#techniques) left pending; needs the multi-circle diffractometer, absent from source (`TECH-1`, `DIFF-1`) |

Both techniques would need the [incident-beam chain](source.md) (the undulator, the DCM for energy, the focusing mirrors, the attenuator), a multi-circle [sample diffractometer](sample.md), and the [Eiger area detector](detector.md). The first two of those are partly modelled; the diffractometer is not.

### Reuse, not new vocabulary

ISR coins **no new Method**. Its resonant scattering reuses the `resonant_scattering` Method that APS 4-ID brought and CSX shares; its surface / CTR diffraction reuses the `diffraction` Method that 4-ID / 8-ID share. So ISR adds, when it lands, further consumers of two pending Methods, strengthening the case for cataloging them, but it does not mint vocabulary. The matching Site Practices (`ISR_resonant_scattering_practice`, `ISR_surface_diffraction_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here).

### Why these are doubly deferred

For every other beamline the technique Methods are deferred because the Capability is not yet in the catalog (the owner-scope decision). At ISR there is a second, harder deferral: the **devices** the techniques run on are not in the public source. Resonant scattering needs a tunable energy axis (a non-functional stub here, `RESONANT-1`) and surface diffraction needs a multi-circle diffractometer (only two axes bound, `DIFF-1`). So these Practices are intent recorded against a partial scaffold, not a capability CORA could drive today. They firm up as the diffractometer and the energy axis enter the source.

### Not modelled yet

The concrete acquisition recipes are not written yet, and cannot be until the diffractometer lands: the reciprocal-space (hkl) scans, the rocking-curve and CTR trajectories, the energy scans across an edge for resonant work, and the in-situ environment programs. The integration and reduction (azimuthal / CTR rod integration) are `ComputePort` work, not beamline Methods. These join as ISR's profile collection grows past its current optics-first state.

See [Open questions](#open-questions) for the world-facts to confirm first, especially the diffractometer (`DIFF-1`) and the in-situ environment (`INSITU-1`).

## Governance

*Who will act at ISR, and the trust shape that will gate it. A deliberately partial first cut.*

Governance at ISR follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

ISR is not yet driven by CORA, so this shape is not yet instantiated. As a partial modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#safety-and-governance), shared with the rest of the fleet (`GOV-1`).

### The safety boundary

The safety tier is the other piece that is not yet settled, and the source is especially thin here: **no PSS search-and-secure permit signal, photon shutter, or hutch-interlock device is in the profile collection** (the only two-button-shutter use is the filter-bank actuation, not a beam shutter). So the Enclosure permit leaves and the interlock structure are carried pending and not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

ISR adds the hazard classes that come with its instruments. Those land with the equipment that brings them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| Hard X-ray beam | the [optics](index.md) and [endstation](index.md) enclosures (XF:04ID) (`ENC-1`) | (`PSS-1`) |
| Vacuum optics | the [Source](source.md) walk | (`SUP-1`) |
| In-situ sample environments (when present) | the [Sample](sample.md) side | (`INSITU-1`) |

The hard X-ray beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (`PSS-1`). The in-situ sample environments that ISR's name implies (electrochemistry, gas, temperature, cryostat) would each bring their own hazards, but none is in the source yet, so they are carried against the in-situ question, not invented (`INSITU-1`).

### When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when ISR's profile collection firms up past its current optics-first state and the deployment approaches the point where CORA drives ISR, following the [2-BM governance](../2-bm/governance.md) shape. Because ISR shares the NSLS-II EPICS and ophyd floor with the rest of the fleet, it re-tests the Site and Federation kernel rather than introducing a new trust model. The Zone groups the same optics and endstation resources the [inventory](index.md) lists; the Policies bind to the NSLS-II operator roles carried pending at the Site (`GOV-1`).

## Model

*The developer's by-kind index: where each CORA aggregate's ISR content lives, why this deployment is deliberately partial, and the record of what is deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at ISR |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### Why ISR is partial

ISR's name, In Situ and Resonant, promises a multi-circle diffractometer, a tunable resonant energy axis, in-situ sample environments, and often polarization analysis. The public profile collection does not yet contain them. It is an optics-and-detectors-first scaffold: the front-end slit, the undulator gap (read-only), the DCM, the focusing and harmonic-rejection mirrors, the attenuator bank, the Eiger 1M, the diagnostic screen cameras, and only two bound sample axes (`th`, `zeta`). The flux-monitor electrometers are commented out, the energy axis is a non-functional stub, and the databroker catalog has a placeholder name, all commissioning signals.

CORA models what is PV-bound and routes the four mission-critical gaps to open questions rather than inventing them. This is the same discipline the [i20-1](../i20-1/notes.md#model) (EDE) partial uses: where the source is thin, model the real handles and name the absences, never fabricate the headline device.

### No new families

ISR coins no new Family and changes nothing in the catalog.

- **4-ID is an undulator beamline** (read-only gap in source); machine state is observed through the loose `StorageRing`, and the undulator detail is `SRC-1`.
- **The optics reuse the catalog:** the DCM binds `Monochromator`; the bendable focusing pair and the harmonic-rejection mirror bind `Mirror`; the front-end slit binds `Slit`; the attenuator bank binds `Filter`.
- **The one bound sample rotation binds `RotaryStage`, not `Goniometer`.** With only `th` + `zeta` bound and no detector arm or reciprocal-space engine, there is no basis for a multi-circle `Goniometer`; it is one `RotaryStage` Asset with the full diffractometer deferred (`DIFF-1`).
- **The Eiger 1M and the screen cameras bind `Camera`; the motorized BPM stage binds the graduated catalog `PositionMonitor`** (presents `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux; the per-Asset channel map stays open, `DIAG-1`). The flux-monitor electrometers are commented out, so no `FluxMonitor` Asset is modelled (`DET-1`).

### No new Methods

ISR's science reuses two pending Methods rather than coining: `resonant_scattering` (APS 4-ID, CSX) and `diffraction` (4-ID, 8-ID). Both are doubly deferred here because the diffractometer they run on is absent from source (`TECH-1`, `DIFF-1`). When ISR's diffractometer lands and the techniques are driven, ISR becomes a further consumer of each, strengthening the case for cataloging them, an owner decision, not an automatic one.

### Deliberately not here yet

- **The multi-circle diffractometer (`DIFF-1`).** Only `th` + `zeta` are bound under the `Dif:ISD` IOC; the orientation circles, the detector two-theta arm, and the reciprocal-space / hkl engine are absent from source and not invented. When they land, the sample side would be a `Goniometer` plus reciprocal-space `PseudoAxis` (the IXS six-circle / CSX TARDIS precedent), with a detector-arm `RotaryStage` / `LinearStage`.
- **The in-situ sample environment (`INSITU-1`).** No temperature / electrochemistry / gas / cryostat device is PV-bound. When it lands it reuses `TemperatureController` / the graduated `FlowController` and the Subject / Supply / Procedure seam, not a new family.
- **The resonant energy axis and polarization analysis (`RESONANT-1`).** The energy axis is a non-functional stub; no polarization analyzer or phase retarder is bound. When wired, the energy axis is a `PseudoAxis` over the DCM and polarization hardware reuses the catalog `PhaseRetarder` and `PolarizationAnalyzer` (4-ID).
- **The flux monitors (`DET-1`).** The QuadEM electrometers and the secondary-source slit are defined but commented out in source; not modelled until live.
- **The Methods.** Whether `resonant_scattering` and `diffraction` enter CORA's catalog is an owner decision; the Practices render unlinked, pending (`TECH-1`).
- **The simulated devices and full asset-tree scenarios.** No `test_isr_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive, and whose primary instrument is not even in source, would be invention; they land when the diffractometer is bound and the team confirms.

## Open questions

*What CORA needs the ISR team to confirm before the model can be trusted.*

ISR was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/isr-profile-collection](https://github.com/NSLS2/isr-profile-collection)), which is an early / commissioning, optics-first scaffold. The control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/` files rather than confirmed by staff, and the devices ISR's mission implies are largely absent from the source. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### The mission gaps (the headline)

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-go-live | The multi-circle diffractometer: only two axes (`th`, `zeta`) are bound under the `Dif:ISD` IOC. What are the full sample-orientation circles, the detector two-theta arm, and the reciprocal-space / hkl engine that resonant and surface (CTR) diffraction need? | One `RotaryStage` for the two bound axes; the full diffractometer is absent and not modelled. | The sample-orientation and detection-geometry modelling. |
| INSITU-1 | Blocks-go-live | The in-situ sample environment: despite In Situ being the beamline's name, no temperature controller, electrochemistry / potentiostat, gas / flow, or cryostat is PV-bound. Which in-situ environments exist and what are their PVs? | No in-situ device modelled; carried as a named gap. | The in-situ sample-environment modelling. |
| RESONANT-1 | Blocks-go-live | The resonant energy axis and polarization analysis: the DCM Bragg is the physical energy axis but a wired energy pseudo-axis is only a non-functional stub, and no polarization analyzer or phase retarder is bound. How is energy scanned for resonant work, and is polarization analyzed? | Energy via the DCM Bragg; no energy pseudo-axis or polarization device modelled. | The resonant-scattering modelling. |

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the optics zones (FE:C04A, XF:04IDA-OP, XF:04IDB-OP) and the zone-D endstation (XF:04IDD-ES) separate hutches? | Two enclosures: an `isr-optics` zone and the `isr-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The in-vacuum undulator model and energy range (only a read-only gap encoder is bound; no gap-drive setpoint). | An `InsertionDevice` undulator, observed gap; parameters pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state ISR reads (only the ring current is bound). | Observe-only machine state, a loose `StorageRing`; the rest pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DCM crystal cut (Si(111) / Si(311)) and the energy range. | A double-crystal `Monochromator`; the crystal cut and range pending. | The monochromator Asset. |
| OPT-1 | Nice-to-have | The focusing-mirror pair (HFM / VFM) and harmonic-rejection mirror (DHRM) coatings and bend mechanisms. | Bendable focusing + harmonic-rejection mirrors bound to `Mirror`; coatings pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The front-end slit blade-axis map, and the secondary-source (SSA) slit (defined but commented out in source). | A front-end `Slit`; the SSA carried as a deferred gap. | The slit Asset detail. |
| ATTN-1 | Nice-to-have | The four-foil attenuator bank (bit-encoded transmission level) and its calibration. | The foils bound to `Filter`. | The attenuator Asset. |

### Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Eiger 1M model and the write path (a commissioning `testing/` path in source), and the flux monitors (the QuadEM electrometers are defined but commented out; there is no point / scaler detector for diffraction counting). | One `Camera` Asset (Eiger 1M); no `FluxMonitor` Asset modelled until the electrometers are live. | The detector and flux-monitor modelling. |
| DIAG-1 | Nice-to-have | The diagnostic screen cameras and the motorized beam-position monitor (only its stage motors are bound; the electrometers are commented out), and the position-versus-intensity split (the fleet-wide question). | `Camera` for the screens; the graduated catalog `PositionMonitor` for the BPM stage (presents Sensor, distinct from `FluxMonitor` by measuring beam position). | The diagnostic modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct, and is the profile representative of production (the databroker catalog is a placeholder name and several devices are commented out, both commissioning signals)? | The handles in the descriptor are taken from the profile collection and carried confirm; the data plane (bluesky-queueserver + Tiled) is the seam CORA's edge replaces. | Verifying each Asset's control handle and the data plane. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (no PSS / shutter / hutch-interlock device is in the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the optics) and the cooling supply. | Photon beam, cooling water, and vacuum on the optics. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do resonant scattering and surface (CTR) diffraction enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the 4-ID / CSX `resonant_scattering` and 4-ID / 8-ID `diffraction` Methods; doubly deferred because the diffractometer is absent from source (DIFF-1). | The technique Capabilities. |
