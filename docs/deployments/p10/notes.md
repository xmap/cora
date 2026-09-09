# Notes

## Techniques

*What the modelled part of P10 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P10's primary technique, XPCS, is a graduated catalog Method (earned at the APS 8-ID), so its practice binds it directly; the coherent-imaging techniques reuse pending slugs (`TECH-1`).

### X-ray photon correlation spectroscopy

P10 illuminates the sample with a coherent beam and reads the speckle pattern on a high-frame-rate area detector (Lambda / Eiger); the intensity autocorrelation over time measures the sample dynamics.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray photon correlation spectroscopy (XPCS) | [`xpcs`](../../catalog/methods.md) | the coherent beam on the sample read by the high-frame-rate Lambda / Eiger, the correlation computed downstream; binds the graduated `xpcs` Method (earned at APS 8-ID), the second consumer |

### Coherent diffraction imaging

P10's E1 endstation focuses the coherent beam (the CRL) and records coherent diffraction patterns (the Quadro / Eiger) for ptychographic / coherent-diffraction reconstruction.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Coherent diffraction imaging / ptychography | `ptychography` | the focused coherent beam scanned across the sample, the diffraction recorded for phase retrieval; reuses the pending `ptychography` slug, a further consumer (`TECH-1`) |

### A graduated Method meets a new facility

P10 is a further XPCS beamline (after APS 8-ID and NSLS-II CHX). Unlike the other PETRA III beamlines (whose techniques are not yet earned and carry pending practices), P10's XPCS practice binds the graduated `xpcs` Method directly, reusing the abstraction the APS 8-ID deployment forced into the catalog. This is the reuse-earns-the-abstraction principle working as intended: a technique graduated at one facility carries cleanly to another on a different control plane. The coherent-imaging side reuses the pending `ptychography` slug; the instrument anatomy reuses existing Families (the CRL `Transfocator`, the hexapod `Hexapod`, the detector suite `Camera`).

### Not modelled yet

The concrete acquisition recipes (the XPCS multi-tau / correlation sequences, the ptychographic scan trajectories, the coherent-diffraction exposures) are not written yet; they join as the deployment approaches the point where CORA drives P10. Whether `ptychography` enters CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at P10, and the trust shape that will gate it. First cut.*

Governance at P10 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P10 is CORA's sixth PETRA III beamline: the DESY operator pool and the safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#safety-and-governance), shared across the facility's beamlines, until DESY staff confirm them (`GOV-1`). P10 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P10, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The OnlineXML carries beamline devices, including the P10 beam shutter, but not the personnel-safety interlock leaves, so the Enclosure permit signals (across the optics and the three experiment areas) and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives P10, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's P10 content lives, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at P10 |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (coupled axes) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes P10 new

P10 is a sixth beamline at an existing Site, and a further XPCS beamline after the APS 8-ID and NSLS-II CHX exercises. Its science is coherent hard X-ray applications: XPCS, coherent diffraction imaging / ptychography, and coherent-beam diffraction, across three experiment areas. Its modelling first is the practice binding: P10's XPCS practice binds the **graduated** catalog `xpcs` Method directly, the first PETRA III practice whose Method is already earned (the others all carry pending practices). This is the reuse-earns-the-abstraction principle in action: a technique graduated at one facility (8-ID, EPICS) carries cleanly to another (PETRA III, Tango) without re-coining.

### No new families

P10 coins no new Family. The undulator binds `InsertionDevice`; the mono `Monochromator`; the CRL `Transfocator`; the hexapod `Hexapod`; the slits `Slit`; the mirrors `Mirror`; the two-theta arm `RotaryStage`; the sample / optics / nano stages `LinearStage`; the coupled axes `PseudoAxis`; the beam shutter `Shutter`; the wide detector suite `Camera`; the fluorescence detectors `EnergyDispersiveSpectrometer`; the LAB simulated diffractometer `Goniometer`. Nothing in the catalog changes. The Mythen strip detector is modelled as a `Camera` for now (a fold-vs-promote question deferred to the catalog owner, `DET-1`).

### The control plane

P10 sits on the PETRA III Tango device floor with Sardana as the scan layer, the same as the other PETRA III beamlines, with the widest controller and detector diversity in the set (OMS, Galil DMC, SmarAct, AttoCube, hexapod, spk; Pilatus / Eiger / Lambda / PCO / Andor / Mythen / Quadro / Lima). The handles are read from P10's public OnlineXML registry and carried confirm (`CTRL-1`); the Lambda and Lima cameras report on a bare `p10` host (`HOST-1`). The XPCS acquisition (the coherent beam read by the high-frame-rate detector, the correlation computed downstream) runs as a Sardana macro; that orchestration is the seam CORA's edge replaces or drives through over its `ControlPort`, and the correlation compute is `ComputePort` work, the same shape as the 8-ID XPCS seam.

### Deliberately not here yet

- **The undulator parameters (`SRC-1`).** The OnlineXML exposes the gap, not the period; carried pending.
- **The optics detail (`OPT-1`).** The DCM crystal cut, the optics-bank breakdown, the CRL focal sizes, and the mirror coatings are carried confirm-pending.
- **The motor-bank axis roles (`GROUP-1`).** The `OPT_MOT`, `E1_MOT`, `E2_MOT` banks carry no per-axis role; grouped as stage Assets.
- **The E2 / LCX sample detail (`SAMPLE-1`, `LCX-1`).** The sample-piezo / two-theta geometry and the LCX sub-station role are pending.
- **The LAB status (`LAB-1`).** The LAB devices are simulation / test units; whether they are modelled as a live offline endstation or excluded is pending.
- **The detector roster (`DET-1`).** The XPCS-detector assignment (Lambda vs Eiger), the detector models, and the Mythen fold-vs-promote are named, not fully bound.
- **The host mapping (`HOST-1`).** The Lambda / Lima cameras report on a bare host; whether shared Tango DB or registry artifact is pending.
- **The handle freshness (`CTRL-1`).** The OnlineXML branch is `debian/jessie`; some handles may lag the live Tango database.
- **`ptychography` Method (`TECH-1`).** Whether coherent imaging enters CORA's catalog is an owner decision; the practice renders unlinked, pending. (XPCS already binds the graduated Method.)
- **The PSS permit signals (`PSS-1`).** The beam shutter is read but the permit leaves are not; carried pending, not invented.
- **The simulated devices and full asset-tree scenarios.** No `test_p10_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the P10 team to confirm before the model can be trusted.*

P10 was reverse-engineered from P10's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p10](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p10), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no coherence lengths, energy calibration, or physical positions. P10 is CORA's sixth PETRA III beamline and a further XPCS beamline (after APS 8-ID and NSLS-II CHX). Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding three experiment areas (E1 coherent imaging, E2 XPCS / diffraction, LAB)? | A `p10-opt` hutch and three `p10-e1` / `p10-e2` / `p10-lab` areas. | The Enclosure grouping. |
| LCX-1 | Nice-to-have | The LCX piezo sub-station: is it a distinct enclosure or a sample sub-stage within E2? | Modelled as a nano-positioning stage within the E2 enclosure. | The LCX placement. |
| LAB-1 | Nice-to-have | The LAB area: is the simulated diffractometer a live offline endstation, or test-only (to exclude)? | Modelled as an offline `Goniometer` + detectors. | The LAB scope. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`OPT_MOT`, `E1_MOT01..97`, `E2_MOT01..96`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the optics-bank breakdown (mirrors / slits / lenses), and the CRL focal sizes. | A DCM `Monochromator`, grouped optics stages, and an E1 CRL `Transfocator`; physical detail pending. | The optics modelling. |

### Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Nice-to-have | The E2 sample-piezo / two-theta geometry and the LCX nano-positioner detail. | SmarAct / AttoCube `LinearStage` piezos and a `RotaryStage` two-theta arm; geometry pending. | The E2 / LCX sample modelling. |

### The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the high-frame-rate XPCS-detector assignment (Lambda vs Eiger), the detector models, and whether the Mythen strip detector warrants a distinct Family. | A wide `Camera` suite plus `EnergyDispersiveSpectrometer` MCAs; the Mythen modelled as a `Camera` for now. | The detector modelling. |
| HOST-1 | Nice-to-have | The Lambda and Lima cameras report on the bare `p10` host. Shared detector host, or registry artifact? | The cameras are homed in E2 (the XPCS detection stage); the host is flagged. | The detector-to-host mapping. |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P10 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, and the role of the P10 beam shutter (read from the registry, safety role not). | Permit leaves to be named; the beam shutter bound to `Shutter`, safety role pending. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does coherent diffraction imaging / ptychography enter CORA's catalog as a Method? (XPCS already binds the graduated `xpcs` Method.) | Deferred: the coherent-imaging practice reuses the pending `ptychography` slug; XPCS is already earned. | The ptychography Capability. |
