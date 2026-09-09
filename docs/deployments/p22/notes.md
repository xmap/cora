# Notes

## Techniques

*What the modelled part of P22 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P22's HAXPES technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

### Hard X-ray photoelectron spectroscopy

P22 illuminates the sample with a monochromatic hard X-ray beam (the shared P09 optics, with the phase retarder setting polarization) and measures the kinetic-energy spectrum of the emitted photoelectrons on the [electron analyzer](detector.md), probing bulk / buried electronic structure (the hard X-ray depth advantage over soft X-ray photoemission).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Hard X-ray photoelectron spectroscopy (HAXPES) | `angle_resolved_photoemission` | photoemission on the HAXPS electron analyzer over the shared P09 optics; reuses the `angle_resolved_photoemission` slug P04 shares, a further consumer (`TECH-1`) |

### A photoemission beamline on familiar vocabulary

P22 is the fleet's hard X-ray photoemission beamline. Its technique reuses the `angle_resolved_photoemission` slug already carried pending (P04, NSLS-II ESM), so it forces no new Method. The instrument anatomy reuses existing Families: the shared optics bind `Monochromator` / `Mirror` / the catalog `PhaseRetarder`, the sample stage `Manipulator`, and the electron analyzer the catalog `ElectronAnalyzer` (graduated at NSLS-II ESM, carried pending here since not exposed in the registry). The HAXPES depth sensitivity is a physics consequence of the hard X-ray energy, not a new device.

### Not modelled yet

The concrete acquisition recipes (the analyzer energy sweeps, the depth-profiling / standing-wave HAXPES, the polarization-dependent measurements) are not written yet; they join as the deployment approaches the point where CORA drives P22. Whether `angle_resolved_photoemission` enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P22, and the trust shape that will gate it. First cut.*

Governance at P22 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P22 is CORA's fourteenth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P22 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P22, following the [2-BM governance](../2-bm/governance.md) shape.

A P22-specific governance wrinkle: P22 **shares its optics chain with P09** (`SHARED-1`). The undulator, monochromator, mirrors, and phase retarder are P09 devices, so the optics-enclosure access state and the source-conditioning commands couple the two beamlines. How CORA's Federation / Trust model carries that coupling (a shared Zone, or a coordination Conduit between the two beamlines) is part of the open question; for this first cut the shared optics are homed in the P22 optics enclosure with the relationship flagged.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). The shared optics mean the optics-enclosure permit is coupled with P09.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P22, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P22 content lives, the shared-optics relationship with P09, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P22 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P22 new

P22 is a fourteenth beamline at an existing Site, the facility's hard X-ray photoemission (HAXPES) beamline. Its distinguishing structural fact is that it **shares its optics chain with P09**: the undulator, DCM, mirrors, phase retarder, and absorber are P09 devices, and P22 is the HAXPES branch off that chain. At the modelling level it is a reuse-and-reinforce deployment, plus a shared-optics relationship the Federation / Trust model would carry.

### No new families

P22 coins no new Family. The shared optics bind `Monochromator` / `Mirror` / `Filter` and the catalog `PhaseRetarder` (P22 is the third consumer, the one that completed the 4-ID/P09/P22 rule-of-three); the HAXPS sample stage binds `Manipulator` (the NSLS-II ESM Family); the electron analyzer binds the catalog `ElectronAnalyzer` (also ESM, carried pending here). Nothing in the catalog changes.

### The control plane

P22 sits on the PETRA III Tango device floor with Sardana as the scan layer. Its defining control fact is the shared P09 optics (the `p09/` addresses), so P22's source-conditioning state is coupled to P09 (`SHARED-1`). The handles are read from P22's public OnlineXML registry and carried confirm (`CTRL-1`); the electron analyzer is a self-contained instrument not in the registry slice (`DET-1`). The HAXPES acquisition runs as a Sardana macro coordinated with the analyzer; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The shared-optics relationship (`SHARED-1`).** P22 and P09 share the undulator / DCM / mirrors / phase retarder; how that maps to CORA's Federation / Trust coordination (two beamlines, one optics chain) is pending.
- **The undulator parameters (`SRC-1`).** The gap is read; the period is not exposed.
- **The optics detail (`OPT-1`).** The DCM crystal cut, the mirror coatings, and the phase-retarder geometry are carried confirm-pending.
- **The manipulator axis roles (`GROUP-1`).** The `p22/motor` bank carries no per-axis role; grouped as one `Manipulator`.
- **The electron analyzer (`DET-1`).** The defining HAXPES detector is named (bound to `ElectronAnalyzer`) but its model / control interface is not in the registry; carried pending.
- **The dummy stubs (`STUB-1`).** The `haxps_dmy*` placeholder devices are noted, not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The HAXPES Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p22_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P22 team to confirm before the model can be trusted.*

P22 was reverse-engineered from P22's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry shows P22 sharing the P09 optics chain, with the HAXPS endstation as a grouped bank and the electron analyzer not exposed. P22 is CORA's fourteenth PETRA III beamline, the HAXPES beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: shared P09 optics feeding the HAXPS experiment endstation? | A `p22-optics` (shared with P09) and a `p22-haxps` endstation. | The Enclosure grouping. |
| SHARED-1 | Blocks-go-live | The P22 / P09 shared optics: the undulator, DCM, mirrors, and phase retarder are P09 devices. How are the two beamlines coordinated (shared straight, switched source, simultaneous operation)? | The optics are shared, homed in `p22-optics` with the relationship flagged. | The shared-optics coordination model. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | A shared P09 undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the HAXPS manipulator bank (the polar / azimuthal / translation axes). | Grouped as one `Manipulator` Asset; per-axis roles pending. | The manipulator Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The shared DCM crystal cut, the mirror coatings, and the phase-retarder geometry. | A DCM `Monochromator`, two `Mirror`s, and a catalog `PhaseRetarder`; physical detail pending. | The optics modelling. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The HAXPES electron analyzer model (a hemispherical analyzer, e.g. SPECS / Scienta), its lens modes, and its control interface (absent from this registry slice). | An `ElectronAnalyzer` Asset (the NSLS-II ESM Family); model and control pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P22 device, the shared P09 optics handles, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; optics shared with P09. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics permit coupling with P09, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (HAXPES needs UHV at the analyzer) and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does hard X-ray photoelectron spectroscopy enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `angle_resolved_photoemission` slug P04 shares; none coined. | The technique Capability. |
