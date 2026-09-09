# Notes

## Techniques

*What the modelled part of FAXTOR is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../alba/index.md#the-techniques-adapted-here) is how a facility adapts it. FAXTOR is a fast-imaging beamline: its tomography techniques reuse Methods CORA's catalog already carries, and its radiography is carried pending until it enters scope (`TECH-1`).

### Fast tomography and radiography

FAXTOR sets the X-ray energy with the multipole wiggler and the double multilayer monochromator (8-50 keV mono) or the filter set (30-70 keV filtered white beam), then rotates the sample on the experiment endstation while the scintillator and fast camera record projections. Continuous-rotation acquisition reaches up to 20 Hz, at 0.5-10 um pixel size, with absorption, propagation-phase, and grating-based contrast.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Tomography | [`tomography`](../../catalog/methods.md) | absorption and propagation-phase micro-CT on the [experiment endstation](sample.md), the [rotary stage](sample.md) stepped against the [scintillator + camera](detector.md); reuses the catalog tomography Method (the 2-BM pilot) |
| Continuous-rotation tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | fast fly-scan tomography up to 20 Hz, the [rotary stage](sample.md) in continuous rotation as the trigger master (`TRIG-1`); reuses the catalog continuous-rotation Method |
| Radiography | `radiography` | time-resolved single-projection radiography; reuses the 7-BM `radiography` slug, no portable Method in the catalog yet; pending (`TECH-1`) |

Tomography needs the [incident energy](source.md) set by the [monochromator or filters](source.md), the [rotary stage and sample positioning](sample.md), and the [scintillator + fast camera](detector.md). Radiography needs the same beam and detector without the rotation sweep.

### A new Site on familiar vocabulary

FAXTOR is the fleet's fast-imaging beamline at ALBA, and it ties into the tomography lineage CORA already models: the same imaging device anatomy as the 2-BM pilot and the MAX IV TomoWISE design (a wiggler or undulator source, a multilayer monochromator, a rotary-stage endstation, and an indirect scintillator + camera detector). It reuses the `tomography` and `continuous_rotation_tomography` Methods directly; only radiography is carried pending, and none forces a new device family.

### Not modelled yet

The concrete acquisition recipes (the fly-scan tomography sequences and their counting times, the flat / dark sequencing, the phase-contrast and grating-based setups) are not written yet; they join as the deployment approaches the point where CORA drives FAXTOR. Whether radiography enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at FAXTOR, and the trust shape that will gate it. First cut.*

Governance at FAXTOR follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [ALBA Site](../alba/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

FAXTOR is CORA's first ALBA deployment, so ALBA is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [ALBA Site](../alba/index.md#safety-and-governance), shared across the facility's beamlines, until ALBA staff confirm them (`GOV-1`). FAXTOR is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives FAXTOR, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. ALBA publishes no per-beamline personnel-safety permit signals or photon / front-end shutters, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [ALBA Site](../alba/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives FAXTOR, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's FAXTOR content lives, the new ALBA Site and Tango / Sardana control house-style it introduces, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at FAXTOR |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes FAXTOR new

FAXTOR is two things at the Site level and nothing new at the vocabulary level. It is CORA's **ninth Site** (ALBA, Barcelona), a re-test of the Site and Federation kernel, and the **second Tango / Sardana / Taurus** control plane CORA models. ALBA is the originating institution of Sardana (and of the Taurus GUI framework and the IcePAP motion controller), so this is the controls house-style's home facility; MAX IV (TomoWISE) was the first consumer CORA modelled. Its science is fast X-ray tomography and radiography on a multipole-wiggler source.

### No new families (the imaging spine reuses the 2-BM / TomoWISE precedent)

FAXTOR coins no new Family. The multipole wiggler binds the catalog `InsertionDevice`; the double multilayer monochromator binds `Monochromator`; the filters bind `Filter` and the slits bind `Slit`; the focusing mirrors bind `Mirror` (deferred, `OPT-1`); the experiment endstation binds `Table`, `RotaryStage`, `LinearStage`, and `Shutter`; the detector binds `Scintillator` and `Camera`; the machine state binds the loose `StorageRing`. Nothing in the catalog changes.

### The Tango / Sardana control plane

FAXTOR is the second Tango / Sardana / Taurus controls house-style in the fleet, after MAX IV TomoWISE. Device IO is a layer of Tango device servers (motors over IcePAP-class controllers, detectors via the Lima framework); Sardana provides the experiment-orchestration layer (a Pool of controllers / motors / measurement groups, plus a MacroServer running scan macros), and Taurus is the operator UI. ALBA publishes no per-beamline device manifest, so CORA does not bind the Tango / Sardana / IcePAP handles here; when bound they would be modelled as opaque edge strings over the `ControlPort`, the way the MX3 and ID32 heterogeneous-control precedents do (`CTRL-1`). The fast continuous-rotation tomography acquisition runs through Sardana macros; that orchestration is the seam CORA's edge replaces, conducting over Tango / IcePAP rather than replacing Sardana. The Lima detector file-writing to the ALBA data store is plumbing CORA observes, not data it owns.

### Deliberately not here yet

- **The control handles (`CTRL-1`).** No public per-beamline Tango / Sardana / IcePAP manifest exists; the handles are carried pending, not invented.
- **The detector model (`DET-1`).** The fast camera and scintillator are bound to `Camera` and `Scintillator` but their models are unpublished, carried fully pending.
- **The exact optics detail (`MONO-1`, `FILT-1`, `OPT-1`, `OPT-2`).** The DMM coating and energy partition, the filter set, the mirrors, and the slit blade map are carried confirm-pending.
- **The endstation stage stack (`SAMPLE-1`, `TRIG-1`).** The rotary, positioning, table, and shutter are named; their axis sets, models, and the trigger scheme are pending.
- **Radiography as a Method (`TECH-1`).** Whether it enters CORA's catalog is an owner decision; the Practice renders unlinked, pending, reusing the 7-BM `radiography` slug. Fast tomography reuses the catalog Methods directly.
- **The simulated devices and full asset-tree scenarios.** No `test_faxtor_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the FAXTOR team to confirm before the model can be trusted.*

FAXTOR was reverse-engineered from ALBA's public facility pages ([cells.es/en/beamlines/bl31-faxtor](https://www.cells.es/en/beamlines/bl31-faxtor)) and a verified research brief, not from a live connection. ALBA publishes no per-beamline device manifest, so the [device pages](index.md) carry a planned shape with control handles unbound. This is CORA's first ALBA Site and its second Tango / Sardana / Taurus controls house-style after MAX IV. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared optics hutch feeding one experiment hutch, or a different layout? | A `faxtor-optics` zone and a `faxtor-experiment` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The multipole-wiggler period, pole count, and field. | A multipole-wiggler source; period and field pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ALBA storage-ring state FAXTOR reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The double multilayer monochromator coating, d-spacing, and the monochromatic / filtered-white energy partition. | A DMM bound to `Monochromator`; 8-50 keV mono, 30-70 keV filtered white. | The monochromator and energy modelling. |
| FILT-1 | Nice-to-have | The filtered-white-beam filter materials and thicknesses. | A filter set bound to `Filter`. | The filter Asset detail. |
| OPT-1 | Nice-to-have | The focusing / harmonic-rejection mirrors (presence, coatings, handles). | Mirrors bound to `Mirror`; absent from public sources, deferred. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The beam-defining slit blade-axis map and handles. | Slits bound to `Slit`. | The slit Asset detail. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The experiment-endstation stage stack: the rotary, the sample positioning, the table degrees of freedom, and the fast shutter. | A `RotaryStage`, `LinearStage`, `Table`, and `Shutter`; axis sets and models pending. | The sample-stage modelling. |
| TRIG-1 | Nice-to-have | The triggering / synchronization scheme for continuous-rotation tomography. | The rotary stage is the master clock feeding the camera trigger. | The trigger wiring. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The fast imaging detector: the camera sensor, frame rate, and model, and the scintillator material and thickness. | A `Scintillator` plus a `Camera` supporting up to 20 Hz tomography; model not published, carried pending. | The detector modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango / Sardana / IcePAP device handles per FAXTOR device (absent from any public manifest). | The handles are unbound, carried pending; the control plane is ALBA Tango / Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ALBA personnel-safety permit signals and the photon / front-end shutters (not published per beamline). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling-water / beam supplies. | Photon beam, cooling water, and vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The ALBA operator pool and safety-review structure (site-level). | Carried pending on the ALBA Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does radiography enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the 7-BM `radiography` slug; fast tomography reuses the catalog tomography Methods. | The technique Capabilities. |
