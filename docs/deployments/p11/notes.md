# Notes

## Techniques

*What the modelled part of P11 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P11 runs macromolecular crystallography and bio-imaging, reusing Methods the fleet already carries pending, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

### Macromolecular crystallography

P11 mounts a crystal on the goniometer (with cryostream cooling), rotates it through an oscillation, and reads frames on the [Pilatus area detector](detector.md). It is a high-throughput rotation-MX beamline.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the goniometer reading the Pilatus, with cryostream cooling; reuses the i03 Method (also at FMX / AMX / MX3 / MANACA / TPS), a further consumer (`TECH-1`) |

### Bio-imaging

P11 also runs coherent / full-field bio-imaging on the experiment-hutch stages reading the area detector.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Bio-imaging | `tomography` | full-field / coherent imaging on the experiment-hutch stages + Pilatus; reuses the catalog `tomography` Method (the 2-BM / FXI lineage), a further consumer (`TECH-1`) |

### A familiar beamline on familiar vocabulary

P11 is the fleet's fourth-plus macromolecular-crystallography beamline and PETRA III's first. It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy, driven here through the PETRA III Tango / Sardana floor. It reuses the `mx_data_collection` Method directly (carried pending across the MX fleet), and the bio-imaging reuses `tomography`; neither forces a new device Family. The automated sample changer, if present, would be a Procedure, not a new device (the i03 / MX3 / MANACA `ROBOT-1` precedent).

### Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the bio-imaging scans, the sample-changer custody loop) are not written yet; they join as the deployment approaches the point where CORA drives P11. Whether the MX Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P11, and the trust shape that will gate it. First cut.*

Governance at P11 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P11 is CORA's fourth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines (with P01, P04, P06), until DESY staff confirm them (`GOV-1`). P11 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P11, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

P11 also carries the hazard classes that come with an MX endstation: a cryostream and its liquid-nitrogen supply, and (if present) an automated sample changer moving in the experiment hutch. Those land with the instruments that bring them; the sample-changer custody loop, if modelled, would be a Procedure with a Subject thread (`ROBOT-1`), not an Asset CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P11, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P11 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P11 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P11 new

P11 is a fourth beamline at an existing Site, and PETRA III's first macromolecular-crystallography beamline. Its science is high-throughput rotation MX (a crystal on a goniometer, cryostream-cooled, read by a Pilatus) plus coherent / full-field bio-imaging. At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level.

### No new families (the MX spine reuses the i03 precedent)

P11 coins no new Family. The cryostream binds the graduated `TemperatureController`; the area detector binds `Camera`; the fluorescence detector binds `EnergyDispersiveSpectrometer`; the optics and experiment-hutch motions bind `LinearStage`. Nothing in the catalog changes. The MX technique reuses the pending i03 `mx_data_collection` Method (as MANACA and TPS 07A do), and the bio-imaging reuses `tomography`.

### The honest limitation: a sparse registry

Unlike P01 (named monochromators, KB mirrors) and P06 (named hexapods, Maia), the P11 OnlineXML does not label its goniometer or MX instruments: most of its devices are area-grouped motor banks (`oh_mot*`, `eh1/eh2/eh3_mot*`, the piezo bank). So this cut models the experiment hutch as grouped positioning stages with the MX instrument structure carried as a question (`MX-1`), rather than inventing a goniometer the registry does not name. This is the same posture the thinner reverse-engineered scaffolds take (FAXTOR's no-manifest, TPS 05A's inferred namespace): model what the source supports, flag the rest.

### The control plane

P11 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, with the whole beamline on one Tango host (`haspp11oh`). The handles are read from P11's public OnlineXML registry and carried confirm (`CTRL-1`). The rotation-MX acquisition (the goniometer oscillation coupled to the Pilatus) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the MX cluster seams at i03 / MANACA / TPS 07A.

### Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML exposes no undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`).** The monochromator, mirrors, and slits are not individually labelled; the oh bank is grouped.
- **The goniometer / MX structure (`MX-1`).** The registry does not name the goniometer; the eh banks are grouped, the MX instrument carried as a question.
- **The motor-bank axis roles (`GROUP-1`).** The banks carry no per-axis role; grouped as stage Assets.
- **The sample changer (`ROBOT-1`).** Not in the registry; would be a deferred sample-exchange Procedure, not a device.
- **The detector model (`DET-1`).** The Pilatus variant and the geometry are named, not bound.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The MX Methods (`TECH-1`).** Whether MX and bio-imaging enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p11_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P11 team to confirm before the model can be trusted.*

P11 was reverse-engineered from P11's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11), branch `debian/jessie`) and a verified research brief, not from a live connection. The P11 registry is sparser in labelling than the other PETRA III beamlines: most devices are area-grouped motor banks whose per-axis roles are not exposed, so the goniometer and MX instruments are not individually resolvable. P11 is CORA's fourth PETRA III beamline and its first macromolecular-crystallography beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch and an experiment hutch? The registry exposes one Tango host (`haspp11oh`), so the split is inferred from device-name prefixes. | A `p11-oh` optics hutch and a `p11-eh` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (the OnlineXML exposes no undulator device). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`oh_mot*`, `granite_mot*`, `eh1/eh2/eh3_mot*`, the piezo bank). | Grouped as area positioning stages carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator, mirrors, and slits within the oh / granite banks. | Grouped `LinearStage` optics stages; the breakdown pending. | The optics modelling. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MX-1 | Blocks-build | The goniometer geometry and the MX instrument structure within the eh1 / eh2 / eh3 banks (the registry does not label them). | Grouped `LinearStage` experiment-hutch stages; the goniometer carried as a question. | The MX instrument modelling. |
| TEMP-1 | Nice-to-have | The cryostream sensor / setpoint handles. | An Oxford Cryostream 700 bound to `TemperatureController`. | The temperature-control modelling. |
| ROBOT-1 | Blocks-go-live | The automated sample changer (load / centre / collect / unmount loop), if present. | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family; not in the registry. | The sample-exchange modelling. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Pilatus detector variant (300k / 1M / 2M / 6M), the sample-to-detector geometry, and the XIA fluorescence detector channel count. | A `Camera` Pilatus plus an `EnergyDispersiveSpectrometer` XIA detector; model pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P11 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do rotation MX and bio-imaging enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the i03 `mx_data_collection` and the `tomography` slugs; none coined. | The technique Capabilities. |
