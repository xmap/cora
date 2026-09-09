# Notes

## Techniques

*What the modelled part of P08 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P08's diffraction technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### High-resolution diffraction

P08 uses a high-resolution monochromatic beam on a six-circle [diffractometer](sample.md) to measure surface / interface diffraction, reflectivity (XRR), and high-resolution powder / single-crystal diffraction, reading the [Eiger / Pilatus / Mythen detectors](detector.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-resolution diffraction / reflectivity | `diffraction` | surface / interface diffraction and reflectivity on the six-circle Kohzu diffractometer + area / strip detectors; reuses the `diffraction` slug P07 share, a further consumer (`TECH-1`) |

### A diffraction beamline on familiar vocabulary

P08 is the fleet's high-resolution diffraction beamline. Its technique reuses the `diffraction` slug already carried pending across the fleet, so it forces no new Method now. The instrument anatomy reuses existing Families: the monochromators bind `Monochromator`, the six-circle diffractometer `Goniometer`, the CRL `Transfocator`, the hexapod `Hexapod`, the detectors `Camera` / `EnergyDispersiveSpectrometer`. The rich detector set (Eiger / Pilatus / Mythen / PerkinElmer / Vortex) suits the breadth of diffraction modes but coins no new Family.

### Not modelled yet

The concrete acquisition recipes (the reflectivity / rocking-curve scans, the reciprocal-space mapping, the high-resolution powder collection) are not written yet; they join as the deployment approaches the point where CORA drives P08. Whether the diffraction Method enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P08, and the trust shape that will gate it. First cut.*

Governance at P08 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P08 is CORA's twelfth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P08 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P08, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the optics and the experiment endstation) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P08, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P08 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P08 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P08 new

P08 is a twelfth beamline at an existing Site, the facility's high-resolution diffraction beamline (surface / interface diffraction, reflectivity, high-resolution powder / single-crystal). At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level, distinguished mainly by its rich detector set.

### No new families

P08 coins no new Family. The DCM and multilayer mono bind `Monochromator`; the CRL `Transfocator`; the absorber `Filter`; the six-circle Kohzu diffractometer `Goniometer`; the hexapod `Hexapod`; the slits `Slit`; the detectors `Camera` / `EnergyDispersiveSpectrometer`. Nothing in the catalog changes. The Mythen2 strip detector is modelled as a `Camera` for now (a fold-vs-promote question for the catalog owner, the P10 precedent).

### The control plane

P08 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the Kohzu six-circle diffractometer controller and the breadth of detectors (Eiger / Pilatus / Mythen / PerkinElmer / Vortex). The handles are read from P08's public OnlineXML registry and carried confirm (`CTRL-1`). The high-resolution diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The gap is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The DCM / multilayer crystal cut and the CRL detail are carried confirm-pending.
- **The diffractometer structure (`DIFF-1`, `GROUP-1`).** The six-circle Kohzu geometry and the per-axis `diff*` bank roles are pending; modelled as a `Goniometer` Asset.
- **The sample hexapod geometry (`SAMPLE-1`).** Carried confirm-pending.
- **The detector roster (`DET-1`).** The models, the operative roster, and the Mythen fold-vs-promote are named, not fully bound.
- **The shared Lambda host (`HOST-1`).** A Lambda reports on the bare `petra3` host.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p08_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P08 team to confirm before the model can be trusted.*

P08 was reverse-engineered from P08's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts or energy calibration. P08 is CORA's twelfth PETRA III beamline, the high-resolution diffraction beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding the diffractometer experiment endstation? | A `p08-oh` optics hutch and a `p08-eh` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the `diff*` Kohzu diffractometer / sample bank. | Grouped as the `Goniometer` Asset carrying the bank prefix; per-axis roles pending. | The diffractometer Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The DCM and multilayer monochromator crystal cuts / d-spacing, and the CRL detail. | A DCM + a multilayer `Monochromator` and a `Transfocator` CRL; physical detail pending. | The optics modelling. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The six-circle Kohzu diffractometer geometry and whether it composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset (kozhue6cctrl + diff*), not the composed Diffractometer Assembly. | The diffractometer modelling. |
| SAMPLE-1 | Nice-to-have | The sample hexapod geometry. | A `Hexapod`; geometry pending. | The sample modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the models (Eiger 1M / Pilatus / Mythen2 / PerkinElmer / Vortex), and whether the Mythen strip detector warrants a distinct Family. | A `Camera` suite plus a `EnergyDispersiveSpectrometer` Vortex; the Mythen modelled as a `Camera` for now. | The detector modelling. |
| HOST-1 | Nice-to-have | A shared Lambda detector reports on the bare `petra3` host. Shared host, or registry artifact? | The Lambda is noted; the host is flagged. | The detector-to-host mapping. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P08 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does high-resolution diffraction enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `diffraction` slug; none coined. | The technique Capability. |
