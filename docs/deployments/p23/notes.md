# Notes

## Techniques

*What the modelled part of P23 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P23's diffraction technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### In-situ X-ray diffraction

P23 measures diffraction (and imaging) of samples under in-situ / operando conditions, electrochemistry, thin-film growth, and controlled sample environments, on the [experiment diffractometer](sample.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| In-situ / operando X-ray diffraction | `diffraction` | diffraction of samples under in-situ conditions; reuses the `diffraction` slug P07 / P08 / P21 share, a further consumer (`TECH-1`) |

### A thin in-situ diffraction beamline

P23 is a thin in-situ diffraction beamline. Its technique reuses the `diffraction` slug already carried across the fleet, so it forces no new Method. The instrument anatomy reuses existing Families (`LinearStage`); the sparse registry slice means the model is deliberately thin, with the optics / diffractometer grouped and the detectors carried pending. The in-situ sample environments (the operando cells), if present, would be sample-environment Assets bound when the registry exposes them.

### Not modelled yet

The concrete acquisition recipes (the diffraction scans, the in-situ / operando time series, the environment-coupled measurements) are not written yet; they join as the deployment approaches the point where CORA drives P23. Whether the diffraction Method enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P23, and the trust shape that will gate it. First cut.*

Governance at P23 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P23 is CORA's fifteenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P23 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P23, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). P23's in-situ / operando sample environments (electrochemical cells, growth chambers) may carry their own hazards; those land with the instruments that bring them when the deployment firms up.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P23, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P23 content lives, a deliberately thin in-situ / operando diffraction model, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P23 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P23 new

P23 is a fifteenth beamline at an existing Site, the facility's in-situ / operando diffraction beamline. At the modelling level it is a reuse-and-reinforce deployment, and a deliberately thin one given its sparse registry slice (one generic motor bank).

### No new families (a thin, honest model)

P23 coins no new Family. The motor bank binds `LinearStage`; the detectors are a pending `Camera` placeholder. Nothing in the catalog changes. The P23 registry slice exposes little beyond the grouped motor bank, so the optics / diffractometer breakdown and the detectors are carried grouped / pending rather than invented (`OPT-1`, `DIFF-1`, `DET-1`), the same model-what-the-source-supports posture as P11 / P21 / P65.

### The control plane

P23 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. The handles are read from P23's public OnlineXML registry and carried confirm (`CTRL-1`). The in-situ diffraction acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The source (`SRC-1`).** The OnlineXML slice exposes no undulator device; the source is carried pending.
- **The optics / diffractometer breakdown (`OPT-1`, `DIFF-1`).** The mono, mirrors, and diffractometer within the bank are not labelled; grouped.
- **The motor-bank axis roles (`GROUP-1`).** The `eh_mot*` bank carries no per-axis role; grouped as one stage.
- **The dev stub (`STUB-1`).** The single `hasep23dev` axis is a dev / commissioning device, noted.
- **The detectors (`DET-1`).** Not in the registry slice; carried as a pending `Camera` placeholder.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p23_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P23 team to confirm before the model can be trusted.*

P23 was reverse-engineered from P23's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23), branch `debian/jessie`) and a verified research brief, not from a live connection. The P23 registry is thin: one area-grouped generic motor bank, no detectors exposed. P23 is CORA's fifteenth PETRA III beamline, the in-situ diffraction beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a single experiment hutch (the registry exposes one host)? Is there a separate optics hutch? | A `p23-eh` experiment hutch, from the OnlineXML `hasep23oh` host. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (absent from this slice). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the `eh_mot*` motor bank. | Grouped as one `LinearStage` stage carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The single `hasep23dev` axis: a dev / commissioning device, or a real channel? | Noted as a dev / commissioning stage. | The dev-stub status. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and mirrors within the bank. | Grouped into the experiment stage; the breakdown pending. | The optics modelling. |
| DIFF-1 | Blocks-build | The diffractometer geometry within the bank. | Grouped into the experiment stage; the diffractometer pending. | The diffractometer modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The in-situ diffraction detectors (area detectors, any fluorescence detectors), absent from this registry slice. | A pending `Camera` placeholder; the detectors not invented. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P23 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent, the cooling / beam supplies, and the in-situ sample-environment supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does in-situ X-ray diffraction enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `diffraction` slug; none coined. | The technique Capability. |
