# Notes

## Techniques

*What the modelled part of P24 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P24's chemical crystallography earns no dedicated catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Chemical crystallography

P24 mounts a single crystal on the [diffractometer](sample.md) and collects single-crystal diffraction on the area detector to solve small-molecule / chemical structures (including at non-ambient conditions).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Single-crystal / chemical crystallography | `diffraction` | single-crystal diffraction on the EH2 diffractometer + area detector; reuses the `diffraction` slug (no dedicated chemical-crystallography Method exists), a further consumer (`TECH-1`) |

### A chemical crystallography beamline on familiar vocabulary

P24 is PETRA III's chemical (small-molecule) crystallography beamline, the fleet's second after Diamond [I19](../i19/index.md). It is distinct from the macromolecular-crystallography beamlines (P11, i03, FMX / AMX, MANACA, TPS): those bind the `Goniometer` Family and the `mx_data_collection` Method, while P24 does small-molecule chemical crystallography, which CORA models as `diffraction` for now (no dedicated chemical-crystallography Method exists, and the registry does not expose a labelled goniometer). The instrument anatomy reuses existing Families (`LinearStage`, `Slit`, `EnergyDispersiveSpectrometer`); the area detector is carried pending.

### Not modelled yet

The concrete acquisition recipes (the single-crystal data-collection strategies, the multi-temperature / variable-condition collection) are not written yet; they join as the deployment approaches the point where CORA drives P24. Whether a dedicated chemical-crystallography Method (vs reusing `diffraction`) enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P24, and the trust shape that will gate it. First cut.*

Governance at P24 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P24 is CORA's sixteenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P24 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P24, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the optics and the two experiment hutches) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P24, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P24 content lives, its single-crystal chemical crystallography distinct from the MX beamlines, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P24 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P24 new

P24 is a sixteenth beamline at an existing Site, the facility's single-crystal / small-molecule chemical crystallography beamline. It is distinct from the macromolecular-crystallography beamlines (P11, i03, FMX / AMX, MANACA, TPS), which bind `Goniometer` and `mx_data_collection`: P24 does small-molecule chemical crystallography, modelled as `diffraction` for now. At the modelling level it is a reuse-and-reinforce deployment.

### No new families

P24 coins no new Family. The optics / sample banks bind `LinearStage`; the slits `Slit`; the coupled axes `PseudoAxis`; the MCA `EnergyDispersiveSpectrometer`; the area detector `Camera` (carried pending). Nothing in the catalog changes. Whether the diffractometer, once labelled, warrants a `Goniometer` / `Diffractometer` binding is carried `DIFF-1`.

### The control plane

P24 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. The handles are read from P24's public OnlineXML registry and carried confirm (`CTRL-1`); the area detector is not exposed in this slice (`DET-1`). The chemical-crystallography acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML slice exposes no undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`).** The monochromator and mirrors within the optics bank are not labelled; grouped.
- **The diffractometer geometry (`DIFF-1`).** Not labelled in the registry; grouped into the sample stage, the goniometer-vs-diffractometer binding pending.
- **The motor-bank axis roles (`GROUP-1`).** The `oh_mot*` / `mot*` banks carry no per-axis role; grouped as stage Assets.
- **The area detector (`DET-1`).** The single-crystal area detector is not in the registry slice; carried as a pending `Camera` placeholder.
- **The dummy stubs (`STUB-1`).** The `eh2_dmy*` placeholder devices are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The chemical-crystallography Method (`TECH-1`).** Whether a dedicated Method (vs reusing `diffraction`) enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p24_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P24 team to confirm before the model can be trusted.*

P24 was reverse-engineered from P24's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p24](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p24), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry exposes generic motor banks and the MCAs, but not the diffractometer geometry or the area detector. P24 is CORA's sixteenth PETRA III beamline, the chemical crystallography beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding an EH2 main and an EH1 experiment hutch? | A `p24-oh` optics hutch and `p24-eh2` / `p24-eh1` endstations. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (absent from this slice). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`oh_mot*`, `mot*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The `eh2_dmy*` dummy stubs: test / placeholder devices, or real channels? | Noted as dummy stubs, not modelled. | The stub status. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and mirrors within the optics bank. | Grouped `LinearStage` optics stages; the breakdown pending. | The optics modelling. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The chemical-crystallography diffractometer geometry (and whether it warrants a `Goniometer` / `Diffractometer` binding once labelled). | A grouped `LinearStage` sample stage; the diffractometer binding pending. | The diffractometer modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The single-crystal area detector (a Pilatus / Eiger-class photon-counting detector), absent from this registry slice. | A pending `Camera` placeholder plus the `EnergyDispersiveSpectrometer` MCAs. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P24 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does chemical crystallography enter CORA's catalog as a dedicated Capability / Method (vs reusing `diffraction`)? | Deferred: carried as a pending Practice reusing the `diffraction` slug; none coined. | The technique Capability. |
