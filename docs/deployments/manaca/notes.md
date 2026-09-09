# Notes

## Techniques

*What the modelled part of MANACA is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../sirius/index.md#the-techniques-adapted-here) is how a facility adapts it. MANACA runs macromolecular crystallography, reusing the same cross-facility MX Methods Diamond i03 introduced, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`, `ROBOT-1`).

### Macromolecular crystallography

MANACA sets the X-ray energy (5-20 keV) with the undulator and the monochromator, mounts a crystal on the goniometer (from the automated 48-pin sample changer), and rotates it through an oscillation while the area detector reads frames. It supports serial and room-temperature MX in addition to standard cryocooled rotation collection.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Rotation MX data collection | `mx_data_collection` | oscillation collection on the [goniometer](sample.md) reading the [area detector](detector.md); reuses the i03 Method (also at FMX / AMX / MX3), not yet in the catalog (`TECH-1`) |
| Grid scan | `grid_scan` | fast grid scan for sample location and centring on the [goniometer](sample.md); reuses the i03 Method; pending (`TECH-1`) |
| Sample exchange | `sample_exchange` | the automated 48-pin changer load / centre / collect / unmount loop, modelled as a Procedure over the spine; reuses the i03 / MX3 Method; pending (`ROBOT-1`) |

Rotation MX needs the [incident energy](source.md) set by the [monochromator](source.md), the [goniometer and cryostream](sample.md), and the [area detector](detector.md). Serial and room-temperature MX reuse the same chain with the sample-delivery and environment varied.

### A new beamline on familiar vocabulary

MANACA is a further macromolecular-crystallography beamline after Diamond i03, NSLS-II FMX / AMX, and the Australian Synchrotron MX3, and Sirius's first MX beamline (its [MOGNO](../mogno/index.md) sibling is tomography). It ties into the MX lineage CORA already models: the same goniometer / detector / cryostream anatomy, driven here through the Sirius EPICS floor and MXCuBE3. It reuses the `mx_data_collection`, `grid_scan`, and `sample_exchange` Methods directly (all carried pending across the MX fleet); none forces a new device family, and the 48-pin sample changer is a Procedure, not a new device.

### Not modelled yet

The concrete acquisition recipes (the oscillation sequences and their exposures, the grid-scan centring, the sample-changer custody loop, the serial / room-temperature delivery) are not written yet; they join as the deployment approaches the point where CORA drives MANACA. Whether the MX Methods enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at MANACA, and the trust shape that will gate it. First cut.*

Governance at MANACA follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [Sirius Site](../sirius/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

MANACA is Sirius's first MX beamline but not CORA's first Sirius deployment (the [MOGNO](../mogno/index.md) tomography scaffold precedes it): the operator pool and the safety-review structure are carried pending on the [Sirius Site](../sirius/index.md#safety-and-governance), shared across the facility's beamlines, until LNLS staff confirm them (`GOV-1`). MANACA is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives MANACA, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. LNLS publishes no per-beamline personnel-safety permit signals or photon / front-end shutters, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [Sirius Site](../sirius/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

MANACA also carries the hazard classes that come with an MX endstation: a cryostream and its liquid-nitrogen supply, and an automated sample changer moving in the experiment hutch. Those land with the instruments that bring them; the sample-changer custody loop is modelled as a Procedure with a Subject thread (`ROBOT-1`), not as an Asset CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives MANACA, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's MANACA content lives, its place as Sirius's first MX beamline, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at MANACA |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes MANACA new

MANACA is a new beamline at an existing Site, and nothing new at the vocabulary level. It is **Sirius's first macromolecular-crystallography beamline**, CORA's second modelled Sirius beamline after the [MOGNO](../mogno/index.md) tomography scaffold. Its science is macromolecular crystallography (serial and room-temperature) at 5-20 keV: rotation MX on a goniometer reading an area detector, with an automated 48-pin sample changer. The control plane is the Sirius EPICS device floor with MXCuBE3 / MXCuBE Web as the MX experiment UI; Bluesky / Ophyd (the LNLS sophys family) is named as a facility orchestration direction, the same migration question MOGNO records (`ORCH-1`).

### No new families (the MX spine reuses the i03 / FMX / AMX / MX3 precedent)

MANACA coins no new Family. The goniometer binds the graduated `Goniometer`; the monochromator binds `Monochromator` and the energy is a `PseudoAxis`; the attenuators bind `Filter`; the cryostream binds the graduated `TemperatureController`; the beamstop binds `BeamStop`; the area detector and the on-axis camera bind `Camera`, the detector stage `LinearStage`, the flux monitor the graduated `FluxMonitor`; the shutters bind `Shutter`; the machine state binds the supply-loose `StorageRing`, and the sample backlight the catalog `Backlight` (graduated across the MX / imaging fleet, `DET-1`). Nothing in the catalog changes. The automated 48-pin sample changer is a deferred sample-exchange Procedure, not a device family (the i03 / i24 / MX3 `ROBOT-1` precedent).

### The control plane

MANACA sits on the Sirius EPICS device floor with MXCuBE3 / MXCuBE Web as the MX experiment UI driving the goniometer, the detector, and the sample changer. Sirius has named Bluesky / Ophyd (the LNLS sophys family: a RunEngine fronted by bluesky-queueserver and bluesky-httpserver) as a facility orchestration direction, and the MOGNO scaffold records the same migration question (`ORCH-1`); whether MANACA runs it today is not public. LNLS publishes its control software openly but no per-beamline PV manifest, so CORA does not bind the EPICS / MXCuBE handles here; when bound they would be modelled as opaque edge strings over the `ControlPort` (`CTRL-1`). The rotation-MX acquisition runs through MXCuBE and the beamline orchestration layer; that orchestration is the seam CORA's edge replaces or drives through, conducting over the EPICS floor rather than owning it. The detector file-writing to the Sirius data store is plumbing CORA observes, not data it owns.

### Deliberately not here yet

- **The control handles (`CTRL-1`).** No public per-beamline EPICS / MXCuBE manifest exists; the handles are carried pending, not invented.
- **The detector model (`DET-1`).** The area detector is bound to `Camera` but its model (a Pilatus / Eiger-class photon-counting detector) is unpublished, carried pending.
- **The sample-exchange Procedure (`ROBOT-1`).** The automated 48-pin changer is named as a deferred Procedure, not built, following the established MX robot precedent.
- **The exact optics and goniometer detail (`MONO-1`, `ENERGY-1`, `FILT-1`, `OPT-1`, `GONIO-1`).** The monochromator crystal, the energy axis, the attenuators, the mirrors / slits, and the goniometer axes are carried confirm-pending.
- **The MX Methods (`TECH-1`, `ROBOT-1`).** Whether rotation MX, grid scan, and sample exchange enter CORA's catalog is an owner decision; the Practices render unlinked, pending, reusing the i03 slugs.
- **The simulated devices and full asset-tree scenarios.** No `test_manaca_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the MANACA team to confirm before the model can be trusted.*

MANACA was reverse-engineered from Sirius's public facility pages ([lnls.cnpem.br/facilities/manaca](https://lnls.cnpem.br/facilities/manaca/)) and a verified research brief, not from a live connection. LNLS publishes its control software (the Bluesky-based sophys family) openly, but no per-beamline EPICS PV manifest, so the [device pages](index.md) carry a planned shape with control handles unbound. MANACA is Sirius's first macromolecular-crystallography beamline, CORA's second modelled Sirius beamline after the [MOGNO](../mogno/index.md) tomography scaffold. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared optics hutch feeding one experiment hutch, or a different layout? | A `manaca-optics` zone and a `manaca-experiment` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator source, 5-20 keV; period pending. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The Sirius storage-ring state MANACA reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The monochromator crystal / multilayer type and handles. | A monochromator bound to `Monochromator`; 5-20 keV. | The monochromator modelling. |
| ENERGY-1 | Nice-to-have | Whether energy is scanned as the measurement (anomalous MX). | A master energy `PseudoAxis` the monochromator tracks. | The energy-axis modelling. |
| FILT-1 | Nice-to-have | The attenuator / transmission foil set. | An attenuator unit bound to `Filter`. | The attenuator Asset detail. |
| OPT-1 | Nice-to-have | The focusing mirrors and beam-defining slits (presence, handles). | No standalone mirror / slit device published; deferred. | The optics Asset detail. |

### Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The goniometer geometry: the rotation, centring, and alignment axes. | A `Goniometer` (the graduated i03 family); axis set pending. | The goniometer modelling. |
| TEMP-1 | Nice-to-have | The cryostream sample-cooling sensor and setpoint handles. | A `TemperatureController` (the graduated family). | The temperature-control modelling. |
| SAMPLE-1 | Nice-to-have | The beamstop axes and the sample-environment detail. | A `BeamStop` at the sample; axis set pending. | The sample-stage modelling. |
| ROBOT-1 | Blocks-go-live | The automated 48-pin sample changer (load / centre / collect / unmount loop). | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family. | The sample-exchange modelling. |

### The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The area-detector model (a Pilatus / Eiger-class photon-counting detector), its translation stage, and the on-axis camera. | A `Camera` plus a `LinearStage` and an on-axis `Camera`; model not published, carried pending. | The detector modelling. |
| DIAG-1 | Nice-to-have | The incident-flux monitor handles. | A `FluxMonitor` (the graduated family). | The flux-monitor modelling. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The EPICS PV and MXCuBE device handles per MANACA device (absent from any public per-beamline manifest). | The handles are unbound, carried pending; the control plane is the Sirius EPICS floor + MXCuBE3. | Binding each Asset's control handle. |
| ORCH-1 | Nice-to-have | Does MANACA run the Bluesky / Ophyd (sophys) orchestration layer, or another scan engine under MXCuBE? | Bluesky / sophys is a named facility direction (as MOGNO records); the MANACA status is unconfirmed. | The orchestration-layer modelling. |
| PSS-1 | Blocks-go-live | The Sirius personnel-safety permit signals and the photon / front-end shutters (not published per beamline). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |
| GOV-1 | Nice-to-have | The Sirius operator pool and safety-review structure (site-level). | Carried pending on the Sirius Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do rotation MX and grid scan enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the i03 `mx_data_collection` and `grid_scan` slugs; none coined. | The technique Capabilities. |
