# Notes

## Techniques

*What the modelled part of P21 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P21's diffraction techniques earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

### High-energy diffraction

P21's P21.2 / EH3 branches use a high-energy monochromatic beam for bulk / engineering diffraction, residual stress, and texture studies on the [sample stages](sample.md), reading area detectors.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-energy diffraction | `diffraction` | bulk / engineering diffraction on the high-energy branches; reuses the `diffraction` slug P07 / P08 share, a further consumer (`TECH-1`) |

### Total scattering / PDF

P21's P21.1 branch collects total scattering to high momentum transfer for pair-distribution-function analysis.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Total scattering / pair-distribution-function | `total_scattering` | high-Q total scattering on the P21.1 branch; reuses the `total_scattering` slug i15-1 / XPD / P02 share, a further consumer (`TECH-1`) |

### A thin high-energy materials beamline

P21 is a Swedish-collaboration high-energy materials beamline. Its techniques reuse the `diffraction` and `total_scattering` slugs already carried across the fleet, so none forces a new Method. The instrument anatomy reuses existing Families (`LinearStage`, `Slit`); the sparse registry slice means the model is deliberately thin, with the detectors carried pending.

### Not modelled yet

The concrete acquisition recipes (the diffraction / stress-mapping scans, the high-Q PDF collection) are not written yet; they join as the deployment approaches the point where CORA drives P21. Whether the diffraction Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P21, and the trust shape that will gate it. First cut.*

Governance at P21 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P21 is CORA's thirteenth PETRA III beamline, a Swedish-collaboration beamline; the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). How the Swedish collaboration maps to operator / access governance is part of that question. P21 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P21, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the optics and the experiment stations) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P21, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P21 content lives, a deliberately thin Swedish-collaboration materials model, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P21 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P21 new

P21 is a thirteenth beamline at an existing Site, a Swedish-collaboration high-energy materials beamline (P21.1 powder / total scattering, P21.2 diffraction / imaging). At the modelling level it is a reuse-and-reinforce deployment, and a deliberately thin one given its sparse registry slice.

### No new families (a thin, honest model)

P21 coins no new Family. The motor banks bind `LinearStage`; the slits bind `Slit`; the detectors are a pending `Camera` placeholder. Nothing in the catalog changes. The P21 registry slice exposes little beyond grouped motor banks, so the detectors are carried pending rather than invented (`DET-1`), the same model-what-the-source-supports posture as P11 / P65.

### The control plane

P21 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, split across three Tango hosts (`hasep212oh`, `hasep21eh3`, `haspp21lab`). The handles are read from P21's public OnlineXML registry and carried confirm (`CTRL-1`). The high-energy diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML slice exposes no undulator device; the source is carried pending.
- **The optics breakdown (`OPT-1`).** The monochromator, mirrors, and slits within the optics bank are not labelled; grouped.
- **The motor-bank axis roles (`GROUP-1`).** The `oh_u*`, `eh3_u*`, `lab*` banks carry no per-axis role; grouped as stage Assets.
- **The detectors (`DET-1`).** Not in the registry slice; carried as a pending `Camera` placeholder.
- **The P21.1 station (`HOST-1`).** The `hasep211eh` host exposed only bookkeeping devices; noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Methods (`TECH-1`).** Whether they enter CORA's catalog is an owner decision; the Practices render unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p21_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P21 team to confirm before the model can be trusted.*

P21 was reverse-engineered from P21's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p21](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p21), branch `debian/jessie`) and a verified research brief, not from a live connection. The P21 registry is thin: area-grouped generic motor banks, no detectors exposed. P21 is CORA's thirteenth PETRA III beamline, the Swedish Materials Science beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a P21.2 optics hutch, an EH3 endstation, and a LAB station (plus the P21.1 branch)? | A `p21-oh` / `p21-eh3` / `p21-lab` grouping, from the OnlineXML host names. | The Enclosure grouping. |
| HOST-1 | Blocks-go-live | The P21.1 station (`hasep211eh`) exposed only bookkeeping devices in this slice. Where is its device tree, and how do P21.1 / P21.2 relate? | Only P21.2 optics / EH3 / LAB modelled; P21.1 noted, not modelled. | The full beamline roster. |
| SRC-1 | Nice-to-have | The undulator source (absent from this slice). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`oh_u*`, `eh3_u*`, `lab*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator, mirrors, and slits within the P21.2 optics bank. | Grouped `LinearStage` optics stages; the breakdown pending. | The optics modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The high-energy diffraction detectors (area detectors, the PerkinElmer / Varex flat-panels typical of high-energy beamlines), absent from this registry slice. | A pending `Camera` placeholder; the detectors not invented. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P21 device, the three-host split, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool, the Swedish collaboration's role, and the safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do high-energy diffraction and total scattering enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `diffraction` / `total_scattering` slugs; none coined. | The technique Capabilities. |
