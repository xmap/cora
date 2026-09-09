# Notes

## Techniques

*What the modelled part of P13 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P13 runs macromolecular crystallography, reusing a Method the fleet already carries pending, so the Method below renders unlinked until a technique enters scope (`TECH-1`).

### Macromolecular crystallography

P13 mounts a crystal on the EMBLMiniDiff microdiffractometer (with cryostream cooling), rotates it through an oscillation, and reads frames on the [Eiger or Pilatus area detector](detector.md). It is a high-throughput rotation-MX beamline, with an XRF detector for anomalous-edge identification.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the EMBLMiniDiff reading the Eiger / Pilatus, with cryostream cooling; reuses the i03 Method (also at FMX / AMX / MX3 / MANACA / TPS / P11), a further consumer (`TECH-1`) |

### A familiar beamline on an unfamiliar floor

P13 is the fleet's seventh macromolecular-crystallography beamline and CORA's first at EMBL Hamburg. It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy. What is new is not the technique but the floor it runs on: where P11 drives MX through the DESY Tango / Sardana stack, P13 drives it through EMBL's MXCuBE over Exporter + TINE (`SEAM-1`). It reuses the `mx_data_collection` Method directly (carried pending across the MX fleet); it forces no new device Family. The automated sample changer is a Procedure, not a new device (the i03 / MX3 / MANACA `ROBOT-1` precedent).

### Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the anomalous-edge scans, the sample-changer custody loop) are not written yet; they join as the deployment approaches the point where CORA drives P13. Whether the MX Method enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P13, and the trust shape that will gate it. First cut.*

Governance at P13 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P13 is CORA's first EMBL Hamburg beamline, and the first **sub-operator** on the PETRA III Site: the beamline shares the ring and Facility with the DESY beamlines but is operated by EMBL Hamburg, with its own staff and its own MXCuBE control domain. The EMBL Hamburg operator pool and safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), distinct from the DESY pool that P01 / P06 / P11 share, until EMBL staff confirm them (`GOV-1`). P13 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P13, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The MXCuBE config carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). The interlock at P13 is operated by DESY (the ring host) even where EMBL operates the beamline, so the boundary between the DESY-issued site clearance and the EMBL-operated experiment is itself a question (`GOV-1`). What is already settled is the shape: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

P13 also carries the hazard classes that come with an MX endstation: a cryostream and its liquid-nitrogen supply, and an automated sample changer moving in the experiment hutch. Those land with the instruments that bring them; the sample-changer custody loop, if modelled, would be a Procedure with a Subject thread (`ROBOT-1`), not an Asset CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the EMBL operator pool, land when the deployment approaches the point where CORA drives P13, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P13 content lives, the sub-operator seam it exercises, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P13 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P13 new

P13 is CORA's first EMBL Hamburg beamline, and the first **sub-operator** at an existing Site: it sits on the PETRA III ring but is operated by EMBL Hamburg, not DESY, with its own control domain. Its science is rotation MX (a crystal on the EMBLMiniDiff, cryo-cooled, read by an Eiger or Pilatus). At the vocabulary level it is a reuse-and-reinforce deployment; the new thing it exercises is the **sub-operator seam**, not a new device or technique.

### The sub-operator seam (the new modelling exercise)

The PETRA III Site already carries the DESY house style (Tango / Sardana / OnlineXML). P13 adds a distinct control-domain *within* the same Site and Facility: EMBL Hamburg runs MXCuBE over the Exporter protocol (the microdiff host) and TINE channels. This is recorded as an EMBL-Hamburg house-style section on the [PETRA III Site](../petra-iii/index.md) descriptor, so the Site now documents two operators with two control floors on one ring (`SEAM-1`). It is the first time CORA models operator and control-floor heterogeneity below the Site boundary; the [seam model](../../architecture/index.md) treats the floor (EPICS / Tango / MXCuBE+Exporter+TINE) as the wall CORA's edge conducts over, never owns.

### No new families (the MX spine reuses the i03 precedent)

P13 coins no new Family. The EMBLMiniDiff binds the graduated `Goniometer`; the area detectors bind `Camera`; the XRF detector binds `EnergyDispersiveSpectrometer`; the aperture / beamstop / objective bind `Aperture` / `BeamStop` / `Objective`; the sample illumination binds the catalog `Backlight` (graduated across the MX / imaging fleet); the optics motions bind `LinearStage`, the energy and detector distance `PseudoAxis`. Nothing in the catalog changes. The MX technique reuses the pending i03 `mx_data_collection` Method (as MANACA, TPS 07A, and P11 do).

### The gain over P11: a config that names the instrument

Unlike P11's OnlineXML (area-grouped motor banks, no named goniometer), EMBL's MXCuBE config names the EMBLMiniDiff and its omega / kappa / sample-centring axes, the aperture, the beamstop, the detectors by model. So P13's experiment hutch resolves into a real `Goniometer` instrument rather than grouped stages. This is the same "model what the source supports" posture P11 takes, but the richer source supports more: the limitation moves from "what is the instrument" to "what are its exact geometry and ranges" (`MX-1`).

### The control plane

P13 sits on EMBL Hamburg's MXCuBE + Exporter + TINE domain, distinct from the DESY Tango / Sardana floor, with the diffractometer motions Exporter-hosted (`p13md201.embl-hamburg.de:9001`) and the detector / energy / beam services on TINE (`/P13/...`). The handles are read from EMBL's public MXCuBE config and carried confirm (`CTRL-1`). The rotation-MX acquisition (the goniometer oscillation coupled to the Eiger) runs as an MXCuBE data-collection routine; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A.

### Deliberately not here yet

- **The source (`SRC-1`).** The MXCuBE config exposes the energy service, not the undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`, `ENERGY-1`).** The monochromator and KB mirror Assets are not individually labelled; the motions are grouped, the energy carried as a pseudo-axis.
- **The goniometer geometry (`MX-1`).** The EMBLMiniDiff is named and bound to `Goniometer`, but its kappa range and axis offsets are not in the config.
- **The cryostream (`CRYO-1`).** Not a labelled device in the config; carried as a question, with the liquid nitrogen a Supply.
- **The sample changer (`ROBOT-1`).** MXCuBE bookkeeping, not a device; a deferred sample-exchange Procedure.
- **The detector model detail (`DET-1`).** The Eiger 16M and Pilatus 6M are named; the ROI modes and geometry are pending.
- **The on-axis camera handle (`OAV-1`).** The viewing cameras carry no control handle in the config object.
- **The handle freshness (`CTRL-1`).** The config is the upstream `develop` branch; some handles may lag the live beamline.
- **The operator / safety boundary (`GOV-1`).** The EMBL-operated beamline on the DESY-hosted ring splits operator from interlock host; the boundary is pending.
- **The MX Method (`TECH-1`).** Whether MX enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the existing slug.
- **The PSS permit signals (`PSS-1`).** Not in the config; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p13_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P13 team to confirm before the model can be trusted.*

P13 was reverse-engineered from EMBL Hamburg's own public MXCuBE HardwareObjects configuration ([github.com/mxcube/mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p13), `configuration/embl_hh_p13`), not from a live connection. EMBL publishes a richer config than the DESY OnlineXML, so the diffractometer and its axes are named (the experiment hutch resolves into a real `Goniometer`), but the exact geometry, the optics breakdown, and the safety / operator boundary are not in it. P13 is CORA's first EMBL Hamburg beamline and the first sub-operator on the PETRA III Site. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch and an experiment hutch? The split is inferred from the device prefixes and the MX layout. | A `p13-oh` optics hutch and a `p13-eh` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (the MXCuBE config exposes the energy service, not the undulator device). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the KB mirror motions (`/P13/P13Kb.CDI/*`). | Grouped as the optics-hutch focusing stage; per-mirror Assets pending. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and the KB mirrors within the focusing motions, and the aperture-size table. | Grouped `LinearStage` optics motions plus a beam-defining `Aperture`; the breakdown pending. | The optics modelling. |
| ENERGY-1 | Nice-to-have | The energy / monochromator coupling behind the `TINEEnergy` service (`/P13/Energy/P13Energy`). | A `PseudoAxis` energy service; the mono motions it drives pending. | The energy modelling. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MX-1 | Blocks-build | The EMBLMiniDiff goniometer geometry (kappa range, axis offsets, the omega / kappa / centring axis assignment). | The EMBLMiniDiff bound to the graduated `Goniometer` with its named axes; the geometry carried as a question. | The MX instrument modelling. |
| OAV-1 | Nice-to-have | The on-axis viewing objective (MicrodiffZoom) magnification and the on-axis / sample-changer camera handles. | An `Objective` zoom plus `Camera` viewing; the camera handle pending. | The OAV modelling. |
| CRYO-1 | Nice-to-have | The cryostream (cooler model, sensor / setpoint handles); it is not a labelled device in the MXCuBE config. | Carried as a question; the liquid nitrogen a Supply observation, not a device. | The temperature-control modelling. |
| ROBOT-1 | Blocks-go-live | The automated sample changer (load / centre / collect / unmount loop). | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family; MXCuBE bookkeeping, not a device. | The sample-exchange modelling. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector models (Eiger 16M, Pilatus 6M read from the config), their ROI modes, and the sample-to-detector geometry. | Two `Camera` area detectors plus a derived `PseudoAxis` distance; the geometry pending. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-diagnostic service split (the BCU intensity / centring services and the pin-diode flux). | Grouped `FluxMonitor` diagnostics; the per-service split pending. | The diagnostic modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Exporter / TINE control handles per P13 device, and whether the upstream MXCuBE `develop` config matches the live beamline. | The handles read from the public MXCuBE config, carried pending; the floor is MXCuBE over Exporter + TINE. | Binding each Asset's control handle. |
| SEAM-1 | Blocks-go-live | The EMBL Hamburg control domain: MXCuBE over Exporter (microdiff) + TINE, distinct from the DESY Tango / Sardana floor. | A sub-operator control-domain within the PETRA III Site; EMBL's house style recorded on the Site. | The seam and Site modelling. |
| GOV-1 | Blocks-go-live | The EMBL Hamburg operator pool, the safety-review structure, and the boundary between the DESY-hosted ring interlock and the EMBL-operated beamline. | Carried pending on the PETRA III Site, distinct from the DESY pool; the operator / interlock boundary a question. | The governance principals. |
| PSS-1 | Blocks-go-live | The personnel-safety permit signals and the photon / front-end shutters (absent from the MXCuBE config). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does rotation MX enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the i03 `mx_data_collection` slug; none coined. | The technique Capability. |
