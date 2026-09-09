# Notes

## Techniques

*What the modelled part of P64 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P64's XAS technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Advanced X-ray absorption spectroscopy

P64 scans the incident energy across an absorption edge (the Tsai DCM coupled to the undulator) and reads the absorption in transmission (the Lambda detectors) and, for dilute samples, in fluorescence on the large [multi-element detector](detector.md), measuring EXAFS / XANES.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray absorption spectroscopy (EXAFS / XANES) | `xas_spectroscopy` | the coupled mono + undulator energy scan read against transmission / multi-element fluorescence; reuses the `xas_spectroscopy` slug BMM / ISS / i20-1 / P04 share, a further consumer (`TECH-1`) |

### A high-rate fluorescence EXAFS beamline on familiar vocabulary

P64 is the advanced half of the PETRA III XAS pair (with the applied [P65](../p65/index.md)). Its distinguishing capability is dilute, high-rate fluorescence detection via the large multi-element SIS3302 detector, but it coins no new vocabulary: it reuses the `xas_spectroscopy` slug already carried pending across the fleet, and its instrument anatomy reuses existing Families (the `Monochromator`, the `Mirror` pair, the `Camera` Lambda detectors, the `EnergyDispersiveSpectrometer` fluorescence detector). The continuous energy fly-scan is a control-plane detail, not a new Method.

### Not modelled yet

The concrete acquisition recipes (the QEXAFS / step-scan energy sequences, the multi-element detector deadtime handling, the DAC high-pressure XAS) are not written yet; they join as the deployment approaches the point where CORA drives P64. Whether `xas_spectroscopy` enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P64, and the trust shape that will gate it. First cut.*

Governance at P64 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P64 is CORA's ninth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P64 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P64, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). P64 shares its optics hutch with the applied-XAS sibling [P65](../p65/index.md), so the optics-enclosure access state couples to the neighbouring beamline, part of the `PSS-1` question.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P64, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P64 content lives, its dilute high-rate fluorescence EXAFS via a large multi-element detector, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P64 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P64 new

P64 is a ninth beamline at an existing Site, and the advanced half of the PETRA III XAS pair (with the applied [P65](../p65/index.md), sharing the optics host). Its distinguishing capability is dilute, high-rate fluorescence EXAFS via a large multi-element detector. At the modelling level it is a reuse-and-reinforce deployment: nothing new at the vocabulary level.

### No new families

P64 coins no new Family. The undulator binds `InsertionDevice`; the Tsai mono `Monochromator`; the mirrors `Mirror`; the slits `Slit`; the sample / picomotor stages `LinearStage`; the Lambda detectors `Camera`; the multi-element fluorescence detector `EnergyDispersiveSpectrometer`. Nothing in the catalog changes. The 104-channel SIS3302 is grouped into one `EnergyDispersiveSpectrometer` Asset, not 104 Assets.

### The control plane

P64 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the Tsai-geometry DCM with its coupled undulator energy axis, the NewFocus picomotors, and the multi-element SIS3302 fluorescence detector. The handles are read from P64's public OnlineXML registry and carried confirm (`CTRL-1`); the optics host is shared with P65. The XAS acquisition (the continuous energy fly-scan read against the multi-element fluorescence) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, the same shape as the BMM / ISS XAS seams.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The energy axis is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The Tsai DCM crystal cut and the mirror coatings are carried confirm-pending.
- **The sample-bank axis roles (`GROUP-1`).** The `exp_mot` / `dac_*` bank carries no per-axis role; grouped, with the DAC sub-stage noted.
- **The detector detail (`DET-1`).** The multi-element element count, the deadtime / ROI handling, and the transmission ion chambers are named, not fully bound.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **`xas_spectroscopy` Method (`TECH-1`).** Whether XAS enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p64_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P64 team to confirm before the model can be trusted.*

P64 was reverse-engineered from P64's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p64](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p64), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, detector element count, or energy calibration. P64 is CORA's ninth PETRA III beamline and the advanced half of the PETRA III XAS pair. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding the experiment endstation, sharing the optics with P65? | A `p64-oh` optics hutch and a `p64-eh` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; energy axis read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the sample bank (`exp_mot*`, `dac_*`) and the picomotor assignments. | Grouped as `LinearStage` Assets carrying the bank prefix; per-axis roles pending. | The sample-stage Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The Tsai DCM crystal cut and energy range, and the two mirror coatings / roles. | A Tsai `Monochromator` and two `Mirror`s; physical detail pending. | The optics modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The multi-element fluorescence detector element count (the 104-channel SIS3302), the deadtime / ROI handling, the two Lambda 750k roles, and the transmission ion chambers. | A grouped `EnergyDispersiveSpectrometer` + two `Camera` Lambdas; element count and ion chambers pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P64 device, the shared P64 / P65 optics host, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; optics shared with P65. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics coupling with P65, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does X-ray absorption spectroscopy enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `xas_spectroscopy` slug BMM / ISS / i20-1 / P04 share; none coined. | The technique Capability. |
