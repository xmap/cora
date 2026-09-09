# Notes

## Techniques

*What the modelled part of P03 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P03 runs small- and wide-angle X-ray scattering, which earns no catalog Method today, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

### Small-angle X-ray scattering

P03 focuses the beam (the multilayer monochromator feeding the CRL or the GINIX waveguide) to a micro or nano spot, illuminates the sample, and reads the small-angle scattering on the [Pilatus area detector](detector.md) at a distance.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Small-angle X-ray scattering (SAXS) | `small_angle_scattering` | the focused beam on the sample read by the Pilatus at a SAXS distance; reuses the `small_angle_scattering` slug, a further consumer (`TECH-1`) |

### Wide-angle X-ray scattering

The microfocus endstation's Pilatus 1M reads the wide-angle scattering simultaneously with the SAXS signal.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Wide-angle X-ray scattering (WAXS) | `wide_angle_scattering` | the Pilatus 1M reading the wide-angle signal; reuses the `wide_angle_scattering` slug, a further consumer (`TECH-1`) |

### A new technique family on familiar vocabulary

P03 is PETRA III's first SAXS / WAXS beamline. Its techniques reuse the `small_angle_scattering` and `wide_angle_scattering` slugs already in the catalog's method vocabulary (the same slugs the NSLS-II SMI / CMS and Diamond i22 scattering beamlines carry), so neither forces a new Method to be coined now. The instrument anatomy reuses existing Families: the monochromator binds `Monochromator`, the mirrors `Mirror`, the CRL and GINIX hexapods `Hexapod`, the slits `Slit`, the detectors `Camera`. The GINIX nanofocus adds a waveguide (modelled as a `Hexapod` carrier plus `LinearStage` waveguide stages) and a sample rotation (`RotaryStage`) that suits scanning / nano-imaging, but no new Family.

### Not modelled yet

The concrete acquisition recipes (the SAXS / WAXS exposure sequences, the GINIX scanning / waveguide alignment, the grazing-incidence variants) are not written yet; they join as the deployment approaches the point where CORA drives P03. Whether the scattering Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P03, and the trust shape that will gate it. First cut.*

Governance at P03 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P03 is CORA's fifth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines (with P01, P04, P06, P11), until DESY staff confirm them (`GOV-1`). P03 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P03, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the shared optics and the two endstations) and the interlock structure are carried pending and are not invented here (`PSS-1`). The nanofocus GINIX experiment shutter is read from the registry but its safety role is not (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

A P03-specific governance note: P03 shares its high-heatload optics with P02, so the optics enclosure's safety and access state is coupled to the neighbouring beamline; how the shared-optics permit is modelled is part of the `HOST-1` / `PSS-1` questions.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P03, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P03 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P03 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P03 new

P03 is a fifth beamline at an existing Site, and the fleet's entry into small-angle / wide-angle scattering. It is the MiNaXS beamline: micro- and nanofocus SAXS / WAXS at 9-23 keV across two endstations (the microfocus endstation and the nanofocus GINIX endstation with its waveguide nano-focusing). It brings a two-endstation-sharing-one-optics-chain layout, the shared P02 / P03 high-heatload optics, and two new Tango motion-controller protocols (Galil DMC slit controllers, SmarPod controllers), but no new Family or Method.

### No new families (the scattering instrument reuses existing vocabulary)

P03 coins no new Family. The multilayer monochromator binds `Monochromator`; the mirrors bind `Mirror`; the CRL and GINIX hexapods bind `Hexapod`; the waveguide stages bind `LinearStage`; the slits bind `Slit`; the sample rotation binds `RotaryStage`; the sample environment binds `TemperatureController`; the detectors bind `Camera` / `EnergyDispersiveSpectrometer`; the shutter binds `Shutter`. Nothing in the catalog changes.

### The control plane

P03 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, and adds two controller protocols new to the set: Galil DMC slit controllers and SmarPod controllers (the GINIX waveguide). The handles are read from P03's public OnlineXML registry and carried confirm (`CTRL-1`); the shared P02 / P03 optics mean the first defining slit reports on the P02 host (`HOST-1`). The SAXS / WAXS acquisition (the sample scan coupled to the Pilatus, the GINIX waveguide-scanning nano-imaging) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics physical detail (`OPT-1`).** The multilayer d-spacing, the mirror coatings, and the CRL / waveguide focal sizes are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The `expmi_mot` and `mot` banks carry no per-axis role in the registry; grouped as sample-stage Assets, roles pending.
- **The GINIX geometry (`SAMPLE-1`).** The waveguide-to-sample geometry and the sample-hexapod / rotation detail are pending.
- **The detector roster (`DET-1`).** The SAXS-vs-WAXS detector assignment, the sample-to-detector distance, and the detector models are named, not fully bound.
- **The host mapping (`HOST-1`).** The shared P02 / P03 optics host and the bare-host Lambda are flagged; whether shared Tango DB or registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The scattering Methods (`TECH-1`).** Whether SAXS / WAXS enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p03_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P03 team to confirm before the model can be trusted.*

P03 was reverse-engineered from P03's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no focal sizes, multilayer d-spacing, or energy calibration. P03 is CORA's fifth PETRA III beamline and its first SAXS / WAXS beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: shared optics feeding a microfocus endstation and a nanofocus GINIX endstation? | A `p03-optics` section (shared with P02) and two `p03-microfocus` / `p03-nanofocus` endstations. | The Enclosure grouping. |
| HOST-1 | Nice-to-have | The first defining slit reports on the P02 optics host (`haspp02oh1`) and a Lambda on the bare `petra3` host. Shared Tango DB hosts, or registry artifacts? | The shared P02 / P03 optics are homed in `p03-optics`; the hosts are flagged. | The device-to-host mapping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`expmi_mot01..64` microfocus, `mot01..40` nanofocus). | Grouped as sample-stage Assets carrying the bank prefix; per-axis roles pending. | The sample-stage Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The multilayer monochromator d-spacing, the mirror coatings, and the CRL / GINIX-waveguide focal sizes. | A multilayer `Monochromator`, two `Mirror`s, a CRL `Hexapod`, and the GINIX waveguide; handles read, physical detail pending. | The optics modelling. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Nice-to-have | The GINIX waveguide-to-sample geometry and the sample-hexapod / rotation detail. | A `Hexapod` sample stage and a `RotaryStage` rotation; geometry pending. | The GINIX sample modelling. |
| TEMP-1 | Nice-to-have | The Eurotherm 2604 sample-environment sensor / setpoint handles. | A `TemperatureController` sample environment. | The temperature-control modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the SAXS-vs-WAXS assignment (Pilatus 300k / 1M), the sample-to-detector distance, and the fluorescence-detector channel count. | `Camera` Pilatus detectors plus `EnergyDispersiveSpectrometer` MCA / XIA detectors; assignment pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P03 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the photon / front-end shutters, and the role of the GINIX experiment shutter (absent / partial in the OnlineXML). | Permit leaves and shutters to be named; the GINIX shutter bound to `Shutter`, safety role pending. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level), and the shared-optics permit coupling with P02. | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do small-angle and wide-angle X-ray scattering enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `small_angle_scattering` and `wide_angle_scattering` slugs; none coined. | The technique Capabilities. |
