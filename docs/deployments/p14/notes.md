# Notes

## Techniques

*What the modelled part of P14 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P14 runs macromolecular crystallography across two endstations, reusing a Method the fleet already carries pending, so the Method below renders unlinked until a technique enters scope (`TECH-1`).

### Macromolecular crystallography

P14 mounts a crystal on a diffractometer (with cryostream cooling), rotates it through an oscillation, and reads frames on an area detector, across two experiment hutches: EH1 on the [EMBLMiniDiff + Eiger detectors](detector.md), EH2 on the [EMBLBSD + Pilatus 2M](detector.md). The EH1 CdTe Eiger variants extend the technique to high-energy data collection, and the X-ray imaging camera supports in-situ centring.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the EMBLMiniDiff (EH1) / EMBLBSD (EH2) reading the Eiger / Pilatus, with cryostream cooling; reuses the i03 Method (also at FMX / AMX / MX3 / MANACA / TPS / P11 / P13), a further consumer (`TECH-1`) |

### A familiar technique across two hutches

P14 is the fleet's eighth macromolecular-crystallography beamline and CORA's second at EMBL Hamburg. It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy, here run through EMBL's MXCuBE over Exporter + TINE (`SEAM-1`). What is distinctive is the two-endstation layout, one source feeding two hutches each running rotation MX, and the high-energy CdTe detector variants in EH1. It reuses the `mx_data_collection` Method directly (carried pending across the MX fleet); it forces no new device Family. The automated sample changer is a Procedure, not a new device (the i03 / MX3 / MANACA `ROBOT-1` precedent).

### Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the high-energy CdTe collection, the anomalous-edge scans, the X-ray imaging centring, the sample-changer custody loop) are not written yet; they join as the deployment approaches the point where CORA drives P14. Whether the MX Method enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P14, and the trust shape that will gate it. First cut.*

Governance at P14 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P14 is CORA's second EMBL Hamburg beamline, the sibling of [P13](../p13/notes.md#governance) and, like it, a **sub-operator** on the PETRA III Site: the beamline shares the ring and Facility with the DESY beamlines but is operated by EMBL Hamburg, with its own staff and its own MXCuBE control domain. The EMBL Hamburg operator pool and safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), distinct from the DESY pool and shared with P13, until EMBL staff confirm them (`GOV-1`). P14 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P14, following the [2-BM governance](../2-bm/governance.md) shape.

The two-hutch layout adds a governance nuance: EH1 and EH2 are separate experiment hutches under one beamline, so the trust shape would scope per hutch (each hutch its own Zone of resources and its own access state) while sharing the source / optics chain. That per-hutch scoping is carried as part of the enclosure question (`EH-1`).

The safety tier is the other piece that is not yet settled. The MXCuBE configs carry beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). The interlock is operated by DESY (the ring host) even where EMBL operates the beamline, so the boundary between the DESY-issued site clearance and the EMBL-operated experiment is itself a question (`GOV-1`). What is already settled is the shape: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

P14 also carries the hazard classes that come with an MX endstation: a cryostream and its liquid-nitrogen supply, and an automated sample changer moving in the experiment hutches. Those land with the instruments that bring them; the sample-changer custody loop, if modelled, would be a Procedure with a Subject thread (`ROBOT-1`), not an Asset CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the EMBL operator pool, land when the deployment approaches the point where CORA drives P14, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P14 content lives, the multi-endstation topology it exercises, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P14 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P14 new

P14 is CORA's second EMBL Hamburg beamline (the sibling of P13) and the **first two-endstation MX beamline** CORA models: one source / optics chain feeding two experiment hutches, EH1 (the EMBLMiniDiff + Eiger detectors) and EH2 (the EMBLBSD + Pilatus 2M). At the vocabulary level it is a reuse-and-reinforce deployment; the new thing it exercises is the **multi-endstation topology under one beamline**, plus the high-energy CdTe detector variants and the X-ray imaging camera.

### Two endstations, one source (the new modelling exercise)

P13 established the EMBL sub-operator control-domain; P14 reuses it and adds the multi-hutch shape. The optics chain (KB mirrors, CRL transfocator, beam-defining slits, shared photon energy) feeds two experiment hutches, each with its own diffractometer host. CORA models this as three enclosures (`p14-oh`, `p14-eh1`, `p14-eh2`) under one root Asset, with the energy and CRL services shared and each hutch carrying its own goniometer, detector, and sample optics (`EH-1`). The trust shape would scope per hutch while sharing the source, a governance nuance carried with the enclosure question.

### No new families (the MX spine reuses the i03 precedent)

P14 coins no new Family. Both diffractometers bind the graduated `Goniometer`; the area detectors bind `Camera`; the XRF detector binds `EnergyDispersiveSpectrometer`; the CRL binds `Transfocator`; the slits bind `Slit`; the focusing optic binds `Mirror`; the sample illumination binds the catalog `Backlight` (graduated across the MX / imaging fleet); the optics motions bind `LinearStage`, the energy and detector distance `PseudoAxis`. Nothing in the catalog changes. The MX technique reuses the pending i03 `mx_data_collection` Method (as P13 and the wider MX fleet do).

### The honest limitation: published mockups

The EH2 config (`embl_hh_pe2`) publishes some axes as `MotorMockup`, a simulation placeholder rather than a live device handle. Rather than present these as real, the EH2 diffractometer and table are carried with a caution marker (`MOCK-1`): the instrument is named and bound, but whether each axis is live on the floor or a config stub is a confirm. This is the same "model what the source supports, flag the rest" posture P11 and P13 take, applied to a source that mixes live and simulated entries.

### The control plane

P14 sits on EMBL Hamburg's MXCuBE + Exporter + TINE domain, distinct from the DESY Tango / Sardana floor, with the diffractometer motions Exporter-hosted (`p14md301` / `p14md302` for EH1, `pe2bsd01` for EH2) and the detector / energy / beam services on TINE (`/P14/...`, `/PE2/...`). The handles are read from EMBL's public MXCuBE configs and carried confirm (`CTRL-1`). The rotation-MX acquisition runs as an MXCuBE data-collection routine; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A and its sibling P13.

### Deliberately not here yet

- **The source (`SRC-1`).** The MXCuBE config exposes the energy service, not the undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`, `ENERGY-1`).** The monochromator and KB mirror Assets are not individually labelled; the motions are grouped, the energy carried as a pseudo-axis, the CRL and slits bound but uncharacterized.
- **The goniometer geometries (`MX-1`).** Both diffractometers are named and bound to `Goniometer`, but their kappa ranges and axis offsets are not in the configs.
- **The EH2 mockups (`MOCK-1`).** Some EH2 axes are `MotorMockup`; whether each is live or simulated is a confirm.
- **The EH2 table handle (`TABLE-1`).** The EH2 positioning table carries no control handle in the config object.
- **The cryostream (`CRYO-1`).** Not a labelled device in the configs; carried as a question, with the liquid nitrogen a Supply.
- **The sample changer (`ROBOT-1`).** MXCuBE bookkeeping, not a device; a deferred sample-exchange Procedure.
- **The detector model detail (`DET-1`).** The Eiger variants and Pilatus 2M are named; the ROI modes and geometry are pending.
- **The imaging / on-axis camera handles (`OAV-1`, `IMG-1`).** The viewing and X-ray imaging cameras carry no control handle in the config objects.
- **The handle freshness (`CTRL-1`).** The configs are the upstream `develop` branch; some handles may lag the live beamline.
- **The operator / safety boundary (`GOV-1`).** The EMBL-operated beamline on the DESY-hosted ring splits operator from interlock host; the boundary is pending.
- **The MX Method (`TECH-1`).** Whether MX enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the existing slug.
- **The PSS permit signals (`PSS-1`).** Not in the configs; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p14_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P14 team to confirm before the model can be trusted.*

P14 was reverse-engineered from EMBL Hamburg's own public MXCuBE HardwareObjects configuration ([github.com/mxcube/mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p14), `configuration/embl_hh_p14` for EH1 and `configuration/embl_hh_pe2` for EH2), not from a live connection. EMBL publishes both endstation configs, so the two diffractometers and their axes are named (each experiment hutch resolves into a real `Goniometer`), but the exact geometry, the optics breakdown, the live-vs-mockup status of the EH2 axes, and the safety / operator boundary are not in them. P14 is CORA's second EMBL Hamburg beamline (the sibling of P13) and the first two-endstation MX beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: one optics hutch and two experiment hutches? The split is inferred from the device prefixes and the MX layout. | A `p14-oh` optics hutch feeding `p14-eh1` and `p14-eh2` experiment hutches. | The Enclosure grouping. |
| EH-1 | Blocks-go-live | The two-endstation layout: do EH1 and EH2 share one source / optics chain (energy + CRL), each with its own diffractometer host? | One shared optics chain feeding two hutches; per-hutch diffractometer and detector. | The multi-endstation topology and per-hutch trust scoping. |
| SRC-1 | Nice-to-have | The undulator source (the MXCuBE config exposes the energy service, not the undulator device). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the KB mirror and slit motions (the P14KB / P14Atto motor groups). | Grouped as the optics-hutch focusing and slit stages; per-axis roles pending. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and KB mirrors, the CRL lens count / material, and the aperture / slit-size tables. | Grouped `LinearStage` motions, a `Mirror` focusing optic, a `Transfocator` CRL, and `Slit` beam-defining boxes; the breakdown pending. | The optics modelling. |
| ENERGY-1 | Nice-to-have | The energy / monochromator coupling behind the `TINEEnergy` service (`/P14/Energy/P14Energy`), shared by both hutches. | A `PseudoAxis` energy service; the mono motions it drives pending. | The energy modelling. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MX-1 | Blocks-build | The goniometer geometries of both endstations (the EH1 EMBLMiniDiff and the EH2 EMBLBSD): kappa range, axis offsets, the omega / kappa / centring axis assignment. | Both bound to the graduated `Goniometer` with named axes; the geometries carried as questions. | The MX instrument modelling. |
| MOCK-1 | Blocks-build | The EH2 axes published as `MotorMockup`: which are live on the floor and which are simulation placeholders in the config? | The EH2 diffractometer and table named and bound, but carried with a caution marker. | Whether the EH2 instrument is modelled live. |
| TABLE-1 | Nice-to-have | The EH2 experiment-table control handles (the EMBLTableMotor table_hor / table_ver carry no handle in the config object). | A `LinearStage` EH2 table; the handle pending. | The EH2 table modelling. |
| OAV-1 | Nice-to-have | The on-axis viewing objectives (MicrodiffZoom / ExporterZoom) magnification and the on-axis / sample-changer camera handles, both hutches. | `Objective` zooms plus `Camera` viewing; the camera handles pending. | The OAV modelling. |
| IMG-1 | Nice-to-have | The EH1 X-ray imaging camera (EMBLXrayImaging) control handle and role. | A `Camera` X-ray imaging device for centring; the handle pending. | The imaging modelling. |
| CRYO-1 | Nice-to-have | The cryostream (cooler model, sensor / setpoint handles); it is not a labelled device in the MXCuBE configs. | Carried as a question; the liquid nitrogen a Supply observation, not a device. | The temperature-control modelling. |
| ROBOT-1 | Blocks-go-live | The automated sample changer (load / centre / collect / unmount loop), per hutch. | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family; MXCuBE bookkeeping, not a device. | The sample-exchange modelling. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector models (Eiger 16M silicon, Eiger 16M / 4M CdTe in EH1, Pilatus 2M in EH2, read from the configs), their ROI modes, and the sample-to-detector geometries. | `Camera` area detectors plus derived `PseudoAxis` distances; the geometries pending. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-diagnostic service split (the beam intensity / centring services and the pin-diode flux). | Grouped `FluxMonitor` diagnostics; the per-service split pending. | The diagnostic modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Exporter / TINE control handles per P14 device across the three diffractometer hosts, and whether the upstream MXCuBE `develop` configs match the live beamline. | The handles read from the public MXCuBE configs, carried pending; the floor is MXCuBE over Exporter + TINE. | Binding each Asset's control handle. |
| SEAM-1 | Blocks-go-live | The EMBL Hamburg control domain: MXCuBE over Exporter (microdiff) + TINE, distinct from the DESY Tango / Sardana floor (shared with P13). | A sub-operator control-domain within the PETRA III Site; EMBL's house style recorded on the Site. | The seam and Site modelling. |
| GOV-1 | Blocks-go-live | The EMBL Hamburg operator pool, the safety-review structure, and the boundary between the DESY-hosted ring interlock and the EMBL-operated beamline. | Carried pending on the PETRA III Site, shared with P13; the operator / interlock boundary a question. | The governance principals. |
| PSS-1 | Blocks-go-live | The personnel-safety permit signals and the photon / front-end shutters (absent from the MXCuBE configs), per hutch. | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does rotation MX enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the i03 `mx_data_collection` slug; none coined. | The technique Capability. |
