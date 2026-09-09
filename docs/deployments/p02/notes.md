# Notes

## Techniques

*What the modelled part of P02 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P02's diffraction techniques reuse Methods the fleet already carries pending, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

### Powder diffraction (P02.1)

P02.1 illuminates a powder / polycrystalline sample with a high-energy (~60 keV) monochromatic beam and reads the Debye-Scherrer rings on the [Pilatus 1M area detector](detector.md), with in-situ temperature control for parametric studies.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-energy powder diffraction | `powder_diffraction` | the powder sample read by the Pilatus 1M; reuses the `powder_diffraction` slug i11 / XPD share, a further consumer (`TECH-1`) |

### Total scattering / PDF (P02.1)

P02.1 also collects total scattering to high momentum transfer (the high-energy beam plus the [PerkinElmer flat-panel](detector.md)) for pair-distribution-function analysis of local / disordered structure.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Total scattering / pair-distribution-function | `total_scattering` | high-Q total scattering on the PerkinElmer flat-panel; reuses the `total_scattering` slug i15-1 / XPD share, a further consumer (`TECH-1`) |

### High-pressure diffraction (P02.2)

P02.2 puts the sample in a [diamond-anvil cell](sample.md) and collects diffraction under high pressure (and variable temperature), for extreme-conditions studies.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Diamond-anvil-cell high-pressure diffraction | `powder_diffraction` | high-pressure diffraction in the DAC; reuses the `powder_diffraction` slug, a further consumer (`TECH-1`, `PRESSURE-1`) |

### A high-energy diffraction beamline on familiar vocabulary

P02 is the fleet's high-energy powder / total-scattering beamline and its first diamond-anvil-cell extreme-conditions endstation. Its techniques reuse the `powder_diffraction` and `total_scattering` slugs already carried pending across the fleet (Diamond i11 / i15-1, NSLS-II XPD), so none forces a new Method now. The instrument anatomy reuses existing Families end to end: the monochromator binds `Monochromator`, the bendable mirrors `Mirror`, the detectors `Camera`, the sample environment `TemperatureController`, and the high-pressure cell the catalog `PressureCell` (graduated across 13-id and P02, with P02 the second consumer that earned it).

### Not modelled yet

The concrete acquisition recipes (the powder-ring integration sequences, the high-Q PDF collection, the pressure-ramp diffraction loops) are not written yet; they join as the deployment approaches the point where CORA drives P02. Whether the diffraction Methods or the PressureCell Family enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P02, and the trust shape that will gate it. First cut.*

Governance at P02 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P02 is CORA's eighth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P02 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P02, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the OH1 optics and the two endstations) and the interlock structure are carried pending and are not invented here (`PSS-1`). A P02-specific note: P02 owns the OH1 high-heatload optics hutch shared with P03, so the optics enclosure's access state couples to the neighbouring beamline, part of the `PSS-1` question.

P02 also carries the hazard classes that come with its endstations: a high-energy (~60 keV) beam, in-situ furnaces (the Anton-Paar) at P02.1, and the diamond-anvil-cell high-pressure environment at P02.2. Those land with the instruments that bring them when the deployment firms up; the pressure cell is modelled as a sample-environment `PressureCell` Asset, not a beam-steering device CORA drives.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P02, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P02 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P02 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P02 new

P02 is an eighth beamline at an existing Site, and the fleet's high-energy diffraction beamline with two branches: P02.1 (powder / total scattering / PDF, ~60 keV) and P02.2 (extreme conditions, diamond-anvil cell). At the modelling level it brings the fleet's **second diamond-anvil-cell** endstation, binding the catalog `PressureCell` Family (graduated across 13-id and P02, with P02 the second consumer that earned it).

### No new families (the DAC reuses the 13-id PressureCell)

P02 coins no new Family. The monochromator binds `Monochromator`; the bendable HFM / VFM mirrors bind `Mirror`; the slits bind `Slit`; the sample stages bind `LinearStage`; the sample environment binds `TemperatureController`; the detectors bind `Camera` / `EnergyDispersiveSpectrometer`; the beam monitor binds `FluxMonitor`; and the diamond-anvil cell binds the catalog `PressureCell`.

Adding P02 as `PressureCell`'s second consumer crossed the rule-of-three promotion threshold, so the Family graduated to the catalog (earned across 13-id and P02, `PRESSURE-1`), following the path the POLAR-family `PhaseRetarder`, `PolarizationAnalyzer`, and `Magnet` siblings took to catalog Families. This is the graduation guard working as designed.

### The control plane

P02 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines. Its distinctive devices are the bendable HFM / VFM mirrors (curvature / ellipticity attribute motors), the Pilatus 1M + PerkinElmer high-energy detectors, and the Anton-Paar / Lakeshore sample environment. The handles are read from P02's public OnlineXML registry and carried confirm (`CTRL-1`). P02 owns the OH1 high-heatload optics hutch shared with P03. The powder / total-scattering / high-pressure acquisition runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics detail (`OPT-1`).** The DCM crystal cut and the bendable-mirror coatings / focusing recipes are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The eh1a/b and eh2a/b banks carry no per-axis role; grouped as stage Assets.
- **The pressure-cell control (`PRESSURE-1`).** The diamond-anvil-cell membrane / gas-loading / pressure control is not in the registry; the `PressureCell` Family is the catalog one (graduated across 13-id and P02), with the membrane / load control detail pending.
- **The detector roster (`DET-1`).** The detector models, the powder-vs-PDF detector roles, and the P02.2 diffraction area detector are named, not fully bound.
- **The CH dummy stubs (`STUB-1`).** The CH1 / CH2 `tangomotor` dummies are test / placeholder devices, noted not modelled.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The diffraction Methods (`TECH-1`).** Whether powder diffraction / total scattering enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p02_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P02 team to confirm before the model can be trusted.*

P02 was reverse-engineered from P02's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, pressure-cell detail, or energy calibration. P02 is CORA's eighth PETRA III beamline and the fleet's second diamond-anvil-cell deployment. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared OH1 optics hutch feeding a P02.1 powder endstation and a P02.2 extreme-conditions endstation? | A `p02-oh1` optics hutch and `p02-1-powder` / `p02-2-extreme` endstations, read from the device-name prefixes. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`eh1a/b`, `eh2a/b`, the OH1 bank). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The CH1 / CH2 `tangomotor` dummy stubs: test / placeholder devices, or real channels? | Noted as dummy stubs, not modelled. | The CH stub status. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the bendable HFM / VFM mirror coatings and focusing recipes, and the slit / CRL detail. | A DCM `Monochromator`, two bendable `Mirror`s, and `Slit`s; physical detail pending. | The optics modelling. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PRESSURE-1 | Blocks-go-live | The P02.2 diamond-anvil-cell control: the membrane / gas-loading / pressure-ramp interface, and the cell's positioning stages. | A `PressureCell` Asset (the catalog Family, graduated across 13-id and P02); membrane / load control pending. | The pressure-cell modelling. |
| TEMP-1 | Nice-to-have | The P02.1 sample-environment sensor / setpoint handles (Anton-Paar, Eurotherm, Lakeshore). | `TemperatureController` controllers; in-situ furnace / cryo. | The sample-environment modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per branch, the powder-vs-PDF detector roles (Pilatus 1M vs PerkinElmer), and the P02.2 high-pressure diffraction area detector. | `Camera` area detectors plus `EnergyDispersiveSpectrometer` fluorescence; roles pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P02 device, the shared OH1 optics with P03, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; OH1 shared with P03. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics access coupling with P03, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do powder diffraction and total scattering / PDF enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `powder_diffraction` / `total_scattering` slugs i11 / i15-1 / XPD share; none coined. | The technique Capabilities. |
