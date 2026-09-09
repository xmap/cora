# Notes

## Techniques

*What the modelled part of CMS is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. CMS measures soft-matter and thin-film structure four ways: small-, wide-, and medium-angle scattering (SAXS / WAXS / MAXS), grazing-incidence scattering (GISAXS / GIWAXS), and specular X-ray reflectivity (XR). Three of those four are scattering the fleet already speaks; the Methods below render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings any of them into the catalog.

CMS is the NSLS-II twin of [SMI](../smi/notes.md#techniques) (12-ID), and most of what it does reinforces vocabulary CORA already holds. Read this page for the one technique that is genuinely distinct: specular reflectivity.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Small-angle scattering (SAXS) | `small_angle_scattering` | low-Q on the [SAXS Pilatus 2M](detector.md); shares the science axis with [i22](../i22/notes.md#techniques) and [SMI](../smi/notes.md#techniques); Method not yet in catalog (`TECH-1`) |
| Wide- and medium-angle scattering (WAXS / MAXS) | `wide_angle_scattering` | wider-Q on the [Pilatus 800K heads](detector.md), one powered per configuration; shares the axis with [i22](../i22/notes.md#techniques); Method not yet in catalog (`TECH-1`) |
| Grazing-incidence scattering (GISAXS / GIWAXS) | `grazing_incidence_scattering` | the same scattering with the sample at a grazing angle on `sth`; shares the axis with APS 9-ID and its NSLS-II twin [SMI](../smi/notes.md#techniques); Method not yet in catalog (`TECH-1`) |
| Specular X-ray reflectivity (XR) | `reflectivity` | step `sth`, slide a detector region-of-interest in lockstep across the fixed [Pilatus 2M](detector.md), integrate the specular intensity; the second consumer of the reflectivity Method after [i10](../i10/notes.md#techniques) (`XR-1`, `TECH-1`) |

All four techniques need the [incident-beam chain](source.md) (the DMM for energy, the mirrors, slits, and absorber foils), the [sample stack](sample.md) (the [Goniometer](sample.md), surface-leveling tilts, temperature stage), and the [endstation detectors](detector.md) (the Pilatus heads, beamstop, flux monitors). Scattering reads an area frame at one orientation; reflectivity reads the same area detector while the orientation is stepped.

### The scattering is reinforcement, not novelty

SAXS, WAXS, MAXS, and grazing-incidence scattering overlap the fleet heavily. CMS is the direct NSLS-II twin of [SMI](../smi/notes.md#techniques), and the two share their science axis with Diamond [i22](../i22/notes.md#techniques) and APS 9-ID / 12-ID: the same Camera / Goniometer / Slit / BeamStop / FluxMonitor vocabulary, zero new families, the same pending scattering Method slugs. MAXS is a detector-position variant of wide-angle scattering on a second Pilatus 800K head, not a technique of its own. GISAXS / GIWAXS is the same scattering with the sample tipped to a grazing angle on `sth`, a sample-orientation variant rather than a new Capability.

So the scattering side of CMS earns no new abstraction. It reinforces, at a second NSLS-II beamline, the case that the small- and wide-angle scattering Capabilities belong in the catalog (`TECH-1`), the same earn-the-abstraction discipline SMI and i22 already follow. The device Roles exist (the Pilatus heads present Detector, the flux monitors present Sensor), so what stays pending is the science Capability, not a device shape. Because those Capabilities are not yet in the catalog, the matching Site Practices (`CMS_small_angle_scattering_practice`, `CMS_wide_angle_scattering_practice`, `CMS_grazing_incidence_scattering_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

### Specular reflectivity, the distinct contribution

Specular X-ray reflectivity is the one technique CMS brings that the scattering vocabulary does not cover, and CORA models it as a **Method over existing devices**, coining no hardware.

There is no physical two-theta detector arm at CMS, and no point detector. The area detector stays fixed. The measurement steps the sample incidence angle `sth` (the same grazing-incidence angle the GISAXS Method uses) and, in lockstep, slides a software region-of-interest across the face of the fixed [Pilatus 2M](detector.md) to where the specularly reflected beam lands at each angle. The intensity inside that tracked region is integrated; the angle the region sits at is a **synthetic** two-theta computed from the geometry, not a value read off a moving arm. The result is the reflectivity curve: specular intensity versus angle, with the incident flux read on the [endstation flux monitor](detector.md) to normalize.

| Reuses | Role in XR |
| --- | --- |
| [Goniometer](sample.md) (`sth`) | steps the specular incidence angle |
| [Pilatus 2M Camera](detector.md) | read over a tracked region-of-interest; the synthetic two-theta is where that region sits |
| [endstation FluxMonitor](detector.md) | incident flux, for normalization |

That is the whole device list. XR coins no two-theta arm, no point detector, no new family. The reflectivity Method is the same one [i10](../i10/notes.md#techniques) brought to CORA at its soft X-ray sibling, where the geometry is realized differently; CMS is the **second consumer** of the Method (`XR-1`), realizing it in the hard X-ray regime with no new hardware. As with the scattering Capabilities, the Method is not yet in the catalog and `CMS_reflectivity_practice` is carried pending (`TECH-1`, `XR-1`).

### Not modelled yet

The concrete acquisition recipes are not written yet. For scattering that is the per-frame exposures, detector distances, beamstop placement, and the azimuthal integration that turns 2D frames into I(Q) curves (the integration and reduction are `ComputePort` work, not beamline Methods). For reflectivity it is the `sth` step list, the region-of-interest tracking model that maps each angle to its place on the fixed Pilatus, and the synthetic two-theta calibration. These join as the deployment approaches the point where CORA drives CMS.

Whether any of these four techniques enters CORA's catalog is an owner-scope decision on [Model](#model): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. The scattering Capabilities are shared pending slugs the fleet already debates; what CMS adds is a second consumer of the pending `reflectivity` Method (i10 plus CMS), which strengthens the case for cataloging it but leaves that an owner decision, not an automatic one (`XR-1`, `TECH-1`). See [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at CMS, and the trust shape that will gate it. First cut.*

Governance at CMS follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

CMS is not yet driven by CORA, so this shape is not yet instantiated. As a modelling-exercise scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator pool and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md#safety-and-governance), shared with the rest of the fleet (GOV-1).

### The safety boundary

The safety tier is the other piece that is not yet settled. The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the beamline's profile collection, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (PSS-1). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

CMS adds the hazard classes that come with its instruments. Those land with the equipment that brings them, and an experiment Clearance would carry them.

| Hazard class | Where it lands | Tracking |
| --- | --- | --- |
| Hard X-ray beam | the [optics](index.md) and [endstation](index.md) enclosures (XF:11BMA, XF:11BMB) (ENC-1) | (PSS-1) |
| Vacuum optics and the telescoping flight path | the [Source](source.md) walk and the detector translations | (SUP-1) |
| In-situ temperature environments | the [Sample](sample.md) thermal / tensile stage | (TEMP-1) |

The hard X-ray beam is the interlocked hazard; its permit leaves stay pending until the PSS signals are confirmed (PSS-1). The vacuum extent and the cooling supply that the optics and flight path depend on are carried pending (SUP-1), and the in-situ temperature range that the Linkam stage brings is carried with it (TEMP-1). None of these is invented; each is recorded against its question.

### When the shape lands

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives CMS, following the [2-BM governance](../2-bm/governance.md) shape. Because CMS shares the NSLS-II EPICS and ophyd floor with FXI, HXN, SRX, BMM, SIX, CHX, ESM, and its twin SMI, it re-tests the Site and Federation kernel rather than introducing a new trust model. The Zone groups the same optics and endstation resources the [inventory](index.md) lists; the Conduit binds the command surfaces; the Policies bind to the NSLS-II operator roles carried pending at the Site (GOV-1).

## Model

*The developer's by-kind index: where each CORA aggregate's CMS content lives, how it models specular reflectivity without a device, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at CMS |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes CMS new

The honest answer is: not much on the scattering, and one real thing on reflectivity. CMS measures soft-matter and thin-film structure by small- and wide-angle scattering (SAXS / WAXS / MAXS), grazing-incidence scattering (GISAXS / GIWAXS), and specular X-ray reflectivity (XR). The scattering overlaps the fleet heavily: CMS is the direct NSLS-II twin of SMI (12-ID), and shares its science axis with Diamond I22 and APS 9-ID / 12-ID. That scattering reuses the existing `Camera` / `Goniometer` / `Slit` / `BeamStop` / `FluxMonitor` / `Monochromator` / `Mirror` vocabulary and contributes reinforcement, not novelty.

CMS's two genuinely distinct contributions are:

- **Specular X-ray reflectivity (XR), the fleet's first hard X-ray reflectometry.** It measures the specularly reflected intensity as a function of incidence angle to recover a film's depth profile. What is interesting for CORA is the mechanism: there is no physical two-theta detector arm. The area detector stays fixed, and the "two-theta" is synthetic, a software region-of-interest that slides across the fixed Pilatus face to where the reflected beam lands as the sample theta (sth) is stepped. So XR is purely a Method, realized over existing devices.
- **CMS as a further NSLS-II beamline, re-testing the Site and Federation kernel.** Its double-multilayer monochromator reuses the same `Monochromator` Family as the APS 2-BM DMM, reinforcing that reuse.

### No new families

CMS coins no new Family and changes nothing in the catalog.

- **11-BM is a bending-magnet source, not an insertion device** (the 2-BM / 7-BM pattern), so there is no `InsertionDevice` Asset; the machine state is observed through the loose `StorageRing`, and the source detail is `SRC-1`.
- **The DMM binds `Monochromator`** (a multilayer Bragg optic, the 2-BM double-multilayer precedent, not the soft X-ray `GratingMonochromator`); the incident energy is a `PseudoAxis` over its Bragg angle.
- **The scattering devices all reuse:** the focusing mirrors bind `Mirror`; the slits bind `Slit`; the attenuator foils bind `Filter`; the sample-orientation circles bind `Goniometer` (sth is the grazing / specular incidence axis); the surface-leveling stage binds `TiltStage`; the SAXS / WAXS / MAXS Pilatus detectors bind `Camera`; the detector translations and the telescoping flight path bind `LinearStage`; the beamstop binds `BeamStop`; the ion chamber, electrometers, and scintillation counter bind `FluxMonitor`; the diamond-diode beam-position monitor binds the graduated catalog `PositionMonitor` (presenting `Sensor`, distinct from `FluxMonitor` by measuring beam position rather than flux; the per-Asset channel map stays `DIAG-1`); the Linkam stage binds `TemperatureController`; the support table binds `Table`.

### How reflectivity is modelled (no device)

Specular reflectivity (XR) is modelled as a Method (a Practice) over existing devices, not as a new device or a new detector arm:

- the incidence angle is the `Goniometer` sample theta (sth);
- the reflected-beam intensity is read on the `Camera` (the Pilatus 2M, the same detector as SAXS) over a tracked region-of-interest;
- the incident flux for normalization is the `FluxMonitor` ion chamber.

The "two-theta" is synthetic: the detector does not move, and the region-of-interest is slid across the fixed detector face to follow where the reflected beam lands as sth is stepped. So XR coins no device, no `Diffractometer` detector arm, and no point detector. The reflectivity Method is **shared with i10** (its soft X-ray RASOR sibling); CMS is the second consumer (`XR-1`). i10 (point-detector, soft X-ray) and CMS (area-detector region-of-interest, hard X-ray) are the rule-of-three pressure that could eventually graduate one reflectivity Method into the catalog; the soft-versus-hard and point-versus-area distinctions are Practice-level adaptations, not a Method split.

### Deliberately not here yet

- **The GIBar sample-exchange arm (`ROBOT-1`).** The multi-axis sample-bar loader is genuinely new automation that no catalog Family covers. Per earn-the-abstraction it is modelled by its stage axes (`LinearStage` / `RotaryStage`) at n=1, and no `SampleExchanger` Family is coined; a second fleet sample robot would earn the abstraction. The garage-indexed pick / place semantics are carried as a note, not modelled.
- **The auxiliary analog I/O and viewing cameras.** The generic analog diode box is carried as flux / diagnostic channels per its wiring, not a Family; the Prosilica sample-viewing cameras are not modelled in this cut.
- **The scattering and reflectivity Methods.** Whether SAXS, WAXS, GISAXS, and XR enter CORA's catalog as Capabilities / Methods is an owner decision; the Practices render unlinked, pending. The scattering Methods are shared with i22 / SMI / 9-ID and the reflectivity Method with i10 (`TECH-1`, `XR-1`).
- **The chamber rebinding and the sth / schi swap.** The beamline_stage configurations rebind the logical goniometer axes across physical PVs at startup, and staff have at times swapped sth and schi; CORA models the logical `Goniometer` and carries the active binding as a setting (`SAMPLE-1`), not as separate Assets.
- **The simulated devices and full asset-tree scenarios.** No `test_cms_*.py` registers the asset tree, and no vendor Models are bound.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA does not yet drive would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the CMS team to confirm before the model can be trusted.*

CMS was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/cms-profile-collection](https://github.com/NSLS2/cms-profile-collection)), so the control handles on the [device pages](index.md) are the beamline's real PVs, read from the `startup/*.py` files rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Are the PV zones XF:11BMA (first optics) and XF:11BMB (endstation) two separate hutches? | Two enclosures: a `cms-optics` zone and the `cms-endstation` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 11-BM source: a bending magnet or a three-pole wiggler (absent from the profile collection as a device). | A bending-magnet source, observed only through the machine state. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state CMS reads (current, fill, status). | Observe-only machine state, a loose `StorageRing`; the exact PVs pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The DMM multilayer d-spacing, the energy range (calibrations near 13.5 keV), and the energy partition rule. | A double-multilayer `Monochromator`; the energy is a `PseudoAxis` over the Bragg angle; d-spacing pending. | The monochromator and incident-energy Assets. |
| OPT-1 | Nice-to-have | The toroidal and elliptical mirror coatings and bend mechanisms. | Focusing mirrors bound to `Mirror`; coatings and bend pending. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The blade-axis roles of each slit (the FOE slit and the five endstation JJ slits, including the s4 transmission / grazing geometry presets). | Four-blade and center / gap slits bound to `Slit`. | The slit Asset detail. |
| ATTN-1 | Nice-to-have | The attenuator foil set (the eight pneumatic absorbers) and whether it folds into `Filter` or earns a distinct `Attenuator` kind (the fleet-wide question). | The foils bound to `Filter` (the i03 / i15-1 precedent). | The attenuator's catalog home. |

### Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The sample-goniometer axes, the grazing / specular incidence axis (the historical sth versus schi swap), and the chamber rebinding (the beamline_stage configurations remap the logical axes across physical PVs at startup). | A `Goniometer` with sth as the incidence axis; the swap and the rebinding carried as settings. | The sample-stage modelling. |
| ROBOT-1 | Nice-to-have | The GIBar sample-exchange arm (a multi-axis sample-bar loader) and whether it earns a `SampleExchanger` Family or stays modelled as stage axes. | Modelled as `LinearStage` / `RotaryStage` axes at n=1; no `SampleExchanger` Family coined pending a second fleet sample robot. | The sample-exchange modelling; the CORA family decision is on [Model](#deliberately-not-here-yet). |
| TEMP-1 | Nice-to-have | The Linkam thermal / tensile stage temperature range and the tensile-load axis. | A `TemperatureController` Asset presenting the `Regulator` Role; range and load axis pending. | The temperature-environment modelling. |

### Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The SAXS / WAXS / MAXS Pilatus detector assignment (which 800K head is powered per configuration), the detector-distance calibrations, and the flux / beam-position channel map. | Three `Camera` Assets (Pilatus 2M SAXS, two 800K WAXS / MAXS); the monitors bind `FluxMonitor` and the diode beam-position monitor the graduated catalog `PositionMonitor`. | The detector modelling. |
| XR-1 | Blocks-go-live | The specular reflectivity (XR) realization: a fixed area detector read over a software region-of-interest tracking the reflected beam as the sample theta is stepped, with no physical two-theta arm. | XR is a Method over `Goniometer` (sth) + `Camera` (the Pilatus region) + `FluxMonitor`; no device coined; the reflectivity Method is shared with i10. | The reflectivity modelling; the CORA decision is on [Model](#deliberately-not-here-yet). |

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the profile collection current and correct? | The handles in the descriptor are taken from the profile collection and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the photon / front-end shutters (absent from the profile collection). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (the optics, the sample chamber, the SAXS flight path) and the cooling supply. | Photon beam, cooling water, and vacuum on the optics and flight path. | The Supply observations. |
| GOV-1 | Nice-to-have | The NSLS-II operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the NSLS-II Site, not instantiated per beamline. | The governance principals. |

### Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do the scattering and reflectivity techniques (SAXS, WAXS, GISAXS, XR) enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices; the scattering Methods are shared with i22 / SMI / 9-ID and the reflectivity Method with i10; none coined. | The technique Capabilities. |
