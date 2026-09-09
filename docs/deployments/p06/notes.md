# Notes

## Techniques

*What the modelled part of P06 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P06 runs hard X-ray scanning-probe microscopy and nano-tomography, reusing Methods the fleet already carries pending, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

### Scanning fluorescence / diffraction microscopy

P06 focuses the beam (the multilayer or crystal monochromator feeding the KB optics) to a micro or nano spot, then rasters the sample across it with the [Aerotech scan stage](sample.md) while the [Maia XRF array](detector.md) reads the fluorescence at each point (and the area detectors read scattering / diffraction).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Scanning X-ray fluorescence / diffraction microscopy | `scanning_fluorescence_microscopy` | the Aerotech raster fly-scan over the micro / nano focus reading the Maia array; reuses the slug 2-ID / XFM / LIX / ESRF ID16B share, a further consumer (`TECH-1`) |

### Nano-tomography

The NC1 nano-probe carries a Pegasus sample rotation (`samr`); rotating the sample in the nano-focused beam while reading the area detector gives nano-tomography.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Hard X-ray nano-tomography | `tomography` | the NC1 sample rotation + area detector; reuses the catalog `tomography` Method (the 2-BM / FXI / ID19 lineage), a further consumer (`TECH-1`) |

### A dense instrument on familiar vocabulary

P06 is the fleet's fullest scanning-probe beamline, but it coins no new vocabulary. Its techniques reuse the `scanning_fluorescence_microscopy` and `tomography` slugs already carried across the fleet, and its instrument anatomy reuses existing Families: the monochromators bind `Monochromator`, the hexapods `Hexapod`, the scan stages `LinearStage`, the Maia array `EnergyDispersiveSpectrometer`, the area detectors `Camera`. The novelty is in the density and diversity of the device tree (six controller families, two endstations, the Maia array), not in any new Family or Method.

### Not modelled yet

The concrete acquisition recipes (the raster fly-scan trajectories and dwell times, the Maia mapping readout, the nano-tomography rotation sequences) are not written yet; they join as the deployment approaches the point where CORA drives P06. Whether the scanning / nano-tomography Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P06, and the trust shape that will gate it. First cut.*

Governance at P06 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P06 is CORA's third PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines (with P01 and P04), until DESY staff confirm them (`GOV-1`). P06 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P06, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals (across the mono hutch and the two probe endstations) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

P06 also carries the hazard classes that come with a dense nano-probe endstation: hexapods, KB-lens stacks, and piezo scanners moving in close quarters inside interlocked hutches. Those land with the instruments that bring them when the deployment firms up.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P06, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P06 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P06 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (KB lens fine axes) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P06 new

P06 is a third beamline at an existing Site, and the fleet's fullest scanning-probe instrument. It is a hard X-ray micro- and nano-probe: a focused beam rastered across a sample while a high-rate Maia XRF array and area detectors read each point, plus nano-tomography on the NC1 sample rotation. Its novelty is the density and diversity of the device tree (six motion-controller families, two endstations, the Maia array), not any new Family or Method.

### No new families (the fullest catalog reuse yet)

P06 coins no new Family. The Maia XRF array binds `EnergyDispersiveSpectrometer` (one Asset carrying its six sub-device handles); the hexapods (MC01 plus the two NC1 KB-lens carriers) bind `Hexapod`; the KB lens fine stages bind `PseudoAxis`; the scan, sample, pin, and nano stages bind `LinearStage`; the sample rotation binds `RotaryStage`; the monochromators bind `Monochromator`; the slits bind `Slit`; the undulator binds `InsertionDevice`; the BPMs bind `FluxMonitor`; and the area / view cameras bind `Camera`. Nothing in the catalog changes.

### The control plane

P06 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as P01 / P04, but with the most controller diversity yet: OMS steppers, Aerotech fly-scan controllers, SmarAct piezo / hexapod controllers, a hexapod controller, PI and SMC-Hydra fine-stage controllers, and a Pegasus rotation controller, reading the Maia array and the Eiger / Lambda / Pilatus / PCO detectors. The handles are read from P06's public OnlineXML registry and carried confirm (`CTRL-1`); several detectors report on a bare `p06` / `petra3` host (`HOST-1`). The scanning fluorescence acquisition is a continuous-motion Aerotech fly-scan coupled to the Maia readout; CORA's edge conducts that over its `ControlPort` and is barred from the deterministic real-time fly-scan loop by construction.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap / harmonic / taper, not the period; carried pending.
- **The optics physical detail (`OPT-1`).** The DCM crystal cut, the multilayer d-spacing, and the KB focal sizes are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The `mono_mot`, `mi_mot`, and `nat_mot` banks carry no per-axis role in the registry; grouped as stage Assets, roles pending.
- **The fly-scan parameters (`SCAN-1`).** The Aerotech raster trajectories and the motion-detector triggering coupling are not in the registry.
- **The detector roster (`DET-1`).** The operative detectors per experiment, the Maia element count, and the area-detector models are named, not fully bound; the Maia sub-device split is a modelling question.
- **The host mapping (`HOST-1`).** Several detectors report on a bare host; whether that is a shared Tango DB or a registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **The scanning / nano-tomography Methods (`TECH-1`).** Whether these enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the existing slugs.
- **The PSS permit signals (`PSS-1`).** Not in the OnlineXML; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p06_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P06 team to confirm before the model can be trusted.*

P06 was reverse-engineered from P06's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p06](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p06), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no focal sizes, detector models, or energy calibration. P06 is CORA's third PETRA III beamline and its fullest scanning-probe deployment. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics / mono hutch feeding two scanning-probe endstations (MC01 micro, NC1 nano)? | A `p06-mono` hutch and two `p06-mc01` / `p06-nc1` endstations, read from the OnlineXML host names. | The Enclosure grouping. |
| HOST-1 | Nice-to-have | Several detectors (Lambda, the detector pool) report on a bare `p06` / `petra3` Tango host. Is that a shared detector host, or a registry artifact? | The detectors are homed in the endstation that operates them; the host is flagged. | The detector-to-host mapping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`mono_mot`, `mi_mot01..84`, `nat_mot01..32`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The sample / instrument-stage Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap / harmonic / taper read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the multilayer monochromator d-spacing, and the KB-lens focal sizes (horizontal and vertical). | A DCM + a multilayer `Monochromator`, two KB `Hexapod` carriers; handles read, physical detail pending. | The optics modelling. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCAN-1 | Blocks-go-live | The Aerotech fly-scan raster trajectories and the motion-detector triggering coupling (MC01 and NC1). | `LinearStage` scan stages with a continuous fly-scan role; parameters pending. | The scanning-acquisition modelling. |
| SAMPLE-1 | Nice-to-have | The NC1 SmarAct sample-piezo axes and the Pegasus sample-rotation detail (the nano-tomography axis). | A `LinearStage` piezo stack and a `RotaryStage` rotation; axis set pending. | The sample-stage modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the Maia element count, and the area-detector models (Eiger / Lambda / Pilatus / PCO variants). | A Maia `EnergyDispersiveSpectrometer` (one Asset, six sub-devices), XIA fluorescence, and `Camera` area detectors; models pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P06 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do scanning fluorescence / diffraction microscopy and nano-tomography enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `scanning_fluorescence_microscopy` and `tomography` slugs; none coined. | The technique Capabilities. |
