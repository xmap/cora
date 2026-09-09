# Notes

## Techniques

*What the modelled part of P65 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P65's XAS technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Applied X-ray absorption spectroscopy

P65 scans the incident energy across an absorption edge (the channel-cut DCM) and reads the absorption in transmission (ion chambers) and fluorescence, for routine applied EXAFS / XANES (catalysis, batteries, environmental science).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray absorption spectroscopy (EXAFS / XANES) | `xas_spectroscopy` | the CDCM energy scan read against transmission / fluorescence; reuses the `xas_spectroscopy` slug BMM / ISS / i20-1 / P04 / P64 share, a further consumer (`TECH-1`) |

### The applied half of the XAS pair

P65 is the applied / high-throughput half of the PETRA III XAS pair, the sibling of the advanced [P64](../p64/index.md). Where P64 specialises in dilute high-rate fluorescence with a large multi-element detector, P65 serves routine transmission + fluorescence EXAFS. Both reuse the `xas_spectroscopy` slug; neither coins a new Family or Method. P65's instrument anatomy is deliberately thin (a `Monochromator` energy axis, `LinearStage` sample bank, `Slit`, `Table`), matching what the registry exposes.

### Not modelled yet

The concrete acquisition recipes (the step / continuous energy scans, the ion-chamber / fluorescence detection chain, the sample-changer throughput loop) are not written yet; they join as the deployment approaches the point where CORA drives P65. Whether `xas_spectroscopy` enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P65, and the trust shape that will gate it. First cut.*

Governance at P65 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P65 is CORA's tenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P65 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P65, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). P65 shares its optics hutch with the advanced-XAS sibling [P64](../p64/index.md), so the optics-enclosure access state couples to the neighbouring beamline, part of the `PSS-1` question.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P65, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P65 content lives, a deliberately thin applied / high-throughput XAS model, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P65 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P65 new

P65 is a tenth beamline at an existing Site, and the applied / high-throughput half of the PETRA III XAS pair (with the advanced [P64](../p64/index.md), sharing the optics host). Its science is routine transmission + fluorescence EXAFS / XANES. At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level, and a deliberately thin model matching its sparse registry slice.

### No new families (a thin, honest model)

P65 coins no new Family. The undulator binds `InsertionDevice`; the CDCM energy axis `Monochromator`; the stages `LinearStage`; the slit `Slit`; the table `Table`; the detection placeholder `FluxMonitor`. Nothing in the catalog changes. The P65 registry slice exposes little beyond the energy axis and the sample bank, so the detection chain is carried as a pending placeholder rather than invented (`DET-1`), the same model-what-the-source-supports posture as P11 and the thinner reverse-engineered scaffolds.

### The control plane

P65 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, sharing the optics host (`hasnp64`) with P64. The handles are read from P65's public OnlineXML registry and carried confirm (`CTRL-1`). The XAS acquisition (the CDCM energy scan read against transmission / fluorescence) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the BMM / ISS XAS seams.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The energy axis is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The CDCM crystal cut and the optics-bank breakdown are carried confirm-pending.
- **The bank axis roles (`GROUP-1`).** The `oh_*`, `fe_*`, and `a2_*` banks carry no per-axis role; grouped as stage Assets.
- **The detection chain (`DET-1`).** The ion chambers and fluorescence detector are not in the registry slice; carried as a pending `FluxMonitor` placeholder.
- **The host mapping (`HOST-1`).** The energy / optics report on the shared P64 host; modelled in the P65 optics enclosure with the host flagged.
- **The dummy stubs (`STUB-1`).** The `a2_dmy*` placeholder devices are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **`xas_spectroscopy` Method (`TECH-1`).** Whether XAS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p65_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P65 team to confirm before the model can be trusted.*

P65 was reverse-engineered from P65's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65), branch `debian/jessie`) and a verified research brief, not from a live connection. The P65 registry slice is thin: an energy axis, a sample bank, a slit / table, the undulator. The XAS detection is not exposed. P65 is CORA's tenth PETRA III beamline and the applied half of the PETRA III XAS pair. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch (shared with P64) feeding the experiment endstation? | A `p65-oh` optics hutch and a `p65-eh` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; energy axis read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the banks (`oh_*`, `fe_*`, `a2_*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The `a2_dmy*` dummy stubs: test / placeholder devices, or real channels? | Noted as dummy stubs, not modelled. | The stub status. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The CDCM crystal cut and energy range, and the optics-bank breakdown. | A channel-cut `Monochromator` energy axis and grouped optics stages; physical detail pending. | The optics modelling. |
| HOST-1 | Nice-to-have | The CDCM energy / optics report on the shared P64 host (`hasnp64`). How is the shared optics split between P64 and P65? | The P65 optics are homed in `p65-oh`; the host is flagged. | The shared-optics mapping. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The XAS detection chain: the transmission ion chambers (I0 / I1 / I2), the fluorescence detector model, and the digitizer (absent from this registry slice). | A pending `FluxMonitor` placeholder; the chain not invented. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P65 device, the shared P64 / P65 optics host, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; optics shared with P64. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics coupling with P64, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does X-ray absorption spectroscopy enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `xas_spectroscopy` slug; none coined. | The technique Capability. |
