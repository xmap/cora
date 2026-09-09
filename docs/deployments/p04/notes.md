# Notes

## Techniques

*What the modelled part of P04 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P04 runs soft X-ray spectroscopy, which earns no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

### Soft X-ray absorption spectroscopy

P04 sets the photon energy (250-3000 eV) by coupling the [variable-polarization undulator](source.md) and the [plane-grating monochromator](source.md), then scans it across an absorption edge while reading the sample drain current on the [electrometer](detector.md) (total electron yield).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Soft X-ray absorption (XAS / NEXAFS) | `xas_spectroscopy` | the undulator + PGM photon-energy scan reading the Keithley electrometer; reuses the `xas_spectroscopy` slug four sites share, a further consumer (`TECH-1`) |

### Photoemission

P04's variable polarization and soft X-ray energy range suit photoemission on the EXP endstations (the analyzer is an endstation instrument not exposed as a motor in the registry).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Soft X-ray photoemission | `angle_resolved_photoemission` | photoemission on the EXP endstations; reuses the `angle_resolved_photoemission` slug, a further consumer (`TECH-1`) |

### A new technique regime on mostly familiar vocabulary

P04 is the fleet's soft X-ray spectroscopy beamline. Its energy regime is new (250-3000 eV, below the hard X-ray beamlines), and it forces the one genuinely new device binding, the `GratingMonochromator` (the soft X-ray analog of the crystal `Monochromator`). The techniques themselves reuse the `xas_spectroscopy` and `angle_resolved_photoemission` slugs already carried pending across the fleet, so neither forces a new Method to be coined now. The rest of the instrument anatomy reuses existing Families: the undulator binds `InsertionDevice`, the mirrors `Mirror`, the slits `Slit`, the manipulators `Manipulator`, the diagnostics `Camera` / `FluxMonitor` / `Screen`.

### Not modelled yet

The concrete acquisition recipes (the photon-energy-scan sequences and their dwell times, the polarization switching, the photoemission analyzer sweeps) are not written yet; they join as the deployment approaches the point where CORA drives P04. Whether the soft X-ray Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P04, and the trust shape that will gate it. First cut.*

Governance at P04 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P04 is CORA's second PETRA III beamline, not its first: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines (with P01), until DESY staff confirm them (`GOV-1`). P04 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P04, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the optics section and the two experiment endstations) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P04, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P04 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P04 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (incident-energy axis) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P04 new

P04 is a second beamline at an existing Site, and PETRA III's entry into the soft X-ray regime (the fleet's soft X-ray line was opened by NSLS-II SIX). It **binds the catalog `GratingMonochromator` Family** (introduced at SIX, graduated at CSX): its monochromator is a plane-grating monochromator (the soft X-ray analog of the crystal `Monochromator`), not the Bragg crystal mono the hard X-ray beamlines use. Its science is soft X-ray spectroscopy at 250-3000 eV (XAS via total electron yield, and photoemission), fed by a variable-polarization APPLE-II-type undulator.

### No new families (the one new binding is already in the catalog)

P04 coins no new Family. The plane-grating monochromator binds the catalog `GratingMonochromator` (its first deployment, but the Family exists); the undulator binds `InsertionDevice`; the mirrors bind `Mirror`; the slits bind `Slit`; the sample manipulators bind `Manipulator`; the diagnostic cameras bind `Camera`; the electrometers bind `FluxMonitor`; the virtual axes bind `PseudoAxis`; and the motorized phosphor screens bind the catalog `Screen` Family (the 2-BM `FLAG-1` precedent). Nothing in the catalog changes.

### The control plane

P04 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as P01. The soft X-ray specifics are the device classes (the `MonoP04` plane-grating monochromator, the `UndulatorP04` variable-polarization undulator, the SmarPod-style `spk` mirror controllers, the `Keithley6517A` electrometers, the `TangoVimba` diagnostic cameras). The handles are read from P04's public OnlineXML registry and carried confirm (`CTRL-1`); some optics report on the `haspp04exp2` host but are the optics section (`HOST-1`). The soft X-ray absorption acquisition (the undulator + PGM photon-energy scan read against the electrometer) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The undulator polarization control (`SRC-1`).** The OnlineXML exposes the gap, not the APPLE-II row-phase / polarization axes; carried pending.
- **The optics physical detail (`OPT-1`).** The grating line densities, the included-angle / c-value mode, the mirror coatings, and the exit-slit calibration are carried confirm-pending.
- **The manipulator axis roles (`GROUP-1`).** The `exp1_mot01..16` and `ps2.01..14` banks carry no per-axis role in the registry; grouped as `Manipulator` Assets, roles pending.
- **The EXSU2 sub-roles (`EXSU-1`).** The exit-shutter unit's slit / bpm / baffle breakdown is pending.
- **The detection channels (`DET-1`).** The electrometer measured channels and the photoemission analyzer (not a motor row) are named, not bound.
- **The host mapping (`HOST-1`).** The optics report on the experiment host; whether this is a shared Tango DB or a registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The soft X-ray Methods (`TECH-1`).** Whether XAS and photoemission enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p04_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P04 team to confirm before the model can be trusted.*

P04 was reverse-engineered from P04's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no grating line densities, polarization modes, or energy calibration. P04 is CORA's second PETRA III beamline and PETRA III's first soft X-ray / grating-monochromator deployment. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a soft X-ray optics section feeding two experiment endstations (EXP1, EXP2)? | A `p04-optics` section and two `p04-exp*` endstations, read from the OnlineXML host names. | The Enclosure grouping. |
| HOST-1 | Nice-to-have | The optics (undulator, PGM, mirrors, exit slits) report on the `haspp04exp2` Tango host. Is that a shared Tango DB host for the optics, or a registry artifact? | The optics are the optics section (`p04-optics`); the host is flagged. | The optics-to-host mapping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the manipulator banks (`exp1_mot01..16`, `ps2.01..14`, `exp2_mot06/08`). | Grouped as `Manipulator` Assets carrying the handles; per-axis roles pending. | The sample-stage Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The variable-polarization undulator: the polarization modes (H / V / circular) and the row-phase axes that set them. | An APPLE-II-type undulator, 250-3000 eV; gap read, row-phase axes pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The plane-grating monochromator grating line densities and mode (included angle / c-value), the three mirror coatings and roles, and the exit-slit calibration. | A `GratingMonochromator`, three `Mirror`s, and exit `Slit`s; handles read, physical detail pending. | The optics modelling. |

### Sample and detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| EXSU-1 | Nice-to-have | The EXP2 exit-shutter unit (EXSU2) sub-roles: slit (Spalt), translation, beam-position monitor, baffle. | Modelled as a beam-defining `Slit`; the bpm / baffle roles pending. | The EXSU2 modelling. |
| DET-1 | Blocks-go-live | The electrometer measured channels (drain current vs I0) and the photoemission analyzer (the endstation spectrometer, not a motor row). | `FluxMonitor` electrometers; the analyzer named, not bound. | The detection modelling. |
| DIAG-1 | Nice-to-have | The EXP2 diagnostic-screen positions and the camera-to-screen mapping. | Motorized `Screen`s imaged by `Camera`s; positions pending. | The diagnostics modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P04 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do soft X-ray absorption and photoemission enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `xas_spectroscopy` and `angle_resolved_photoemission` slugs; none coined. | The technique Capabilities. |
