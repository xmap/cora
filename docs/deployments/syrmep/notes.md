# Notes

## Techniques

*What the modelled part of SYRMEP is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../elettra/index.md) is how a facility adapts it. SYRMEP is a hard X-ray microtomography beamline, so its core imaging techniques reuse the catalog Methods the fleet's imaging beamlines already share; the helical, white-beam, and phase-retrieval Methods are new to CORA's catalog and render unlinked, carried pending until a technique enters scope (`TECH-1`).

### Microtomography: absorption and phase contrast

SYRMEP sets the X-ray energy with the Si(111) monochromator (or passes white / pink beam), then rotates the specimen while the detector records projections. It does absorption tomography, propagation-based phase-contrast tomography (the long sample-to-detector rail), and diffraction-enhanced imaging.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Microtomography | [`tomography`](../../catalog/methods.md) | the canonical imaging routine on the [rotation stage](sample.md) and [camera](detector.md); reuses the 2-BM tomography Method directly |
| Continuous (fly) tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | trigger-driven continuous rotation under DonkiOrchestra; reuses the catalog Method |
| Wide / laminar-beam tomography | [`mosaic_tomography`](../../catalog/methods.md) | tiled tomography for samples beyond the field of view; reuses the catalog Method |
| Dark / flat field | [`dark_field`](../../catalog/methods.md), [`flat_field`](../../catalog/methods.md) | the reconstruction baseline frames; reuse the catalog acquisition Methods |
| Rotation-axis centring | [`center_alignment`](../../catalog/methods.md) | the alignment step; reuses the catalog Method |
| Helical CT | `helical_tomography` | the large-specimen continuous-pitch mode (the XC Hydra photon-counting setup); Method not yet in the catalog, renders unlinked |
| White / pink-beam tomography | `white_beam_tomography` | fast tomography with the DCM bypassed; Method not yet in the catalog |
| Phase retrieval | `phase_retrieval` | single-distance TIE-HOM / Paganin retrieval (the SYRMEP Tomo Project pipeline); a compute Method not yet in the catalog (`COMPUTE-1`) |

### A clean re-test of the imaging spine

SYRMEP's significance for the catalog is that it forces nothing new at the Family level: every device binds an existing imaging Family (`RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `Slit`, `Filter`, `Monochromator`), and the core tomography Practices bind real catalog Methods. It is the cleanest re-test the fleet has of whether the imaging spine ports to a brand-new Site and control house-style. The clinical breast-CT programme (SYRMA-3D) and the large-specimen helical work are extensions that would earn new Methods if the deployment enters pilot scope.

### Not modelled yet

The concrete acquisition recipes (the exposure, projection counts, angle ranges, propagation distances, and the phase-retrieval and ring-removal parameters) are not written yet; they join as the deployment approaches the point where CORA drives SYRMEP. Whether helical CT, white-beam tomography, and phase retrieval enter CORA's catalog is an owner-scope decision on [Model](#deliberately-not-here-yet); see [Open questions](#open-questions) for the world-facts to confirm first.

## Governance

*Who will act at SYRMEP, and the trust shape that will gate it. First cut.*

Governance at SYRMEP follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [Elettra Site](../elettra/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

SYRMEP is CORA's first Elettra deployment, so Elettra is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [Elettra Site](../elettra/index.md), shared across the facility's beamlines, until Elettra staff confirm them (`GOV-1`). SYRMEP is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives SYRMEP, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The Elettra personnel-safety permit signals and the front-end / safety shutters are not in public source, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). The Elettra 2.0 GeCo PLC interlock stack (Siemens S7-1500 over PROFINET) is the safety floor CORA never drives; it sits below the seam. What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [Elettra Site](../elettra/index.md), not on the beamline, and the beamline links up to them.

SYRMEP carries the hazard classes that come with hard X-ray imaging: an intense white / monochromatic beam, and, for the clinical breast-CT programme (SYRMA-3D), human-subject considerations that an experiment Clearance would carry. Those land with the work that brings them, modelled as hazards on the experiment rather than as Assets CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives SYRMEP, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's SYRMEP content lives, the new Elettra Site and Tango / DonkiOrchestra control house-style it introduces, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at SYRMEP |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Computed / virtual axes (Equipment) | [Source](source.md) (the incident-energy `PseudoAxis`) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### What makes SYRMEP new

SYRMEP is two things at the facility level and nothing new at the catalog level. It is CORA's **eleventh Site** (Elettra Sincrotrone Trieste, Trieste), another re-test of the Site and Federation kernel, and the **first Tango + DonkiOrchestra** control house-style. The Tango device floor is shared with the ESRF's ID32, but the orchestration seam is the in-house, trigger-driven DonkiOrchestra framework (Elettra 2.0: the abstract "Executer" Tango device server), not BLISS and not EPICS. Its science is hard X-ray microtomography (absorption, propagation-based phase contrast, diffraction-enhanced imaging) plus the SYRMA-3D clinical breast-CT programme.

### No new families: the imaging spine ports wholesale

SYRMEP coins no new Family and changes nothing in the catalog. It is the cleanest re-test the fleet has of the imaging spine on a new Site:

- the bending-magnet source is a Supply (`PhotonBeam`), provenance only (the 2-BM precedent);
- the double-crystal Si(111) DCM binds `Monochromator`, with the mono / white (pink) beam choice as a per-Asset setting (the 2-BM `dmm_insertion` insert/retract precedent);
- the incident energy is a `PseudoAxis` over the DCM (the 2-BM energy-curve precedent);
- the laminar-beam slits bind `Slit`, the filters bind `Filter`, the upstream mask binds `Mask`;
- the heavy-payload rotation stage binds `RotaryStage` (the tomographic theta);
- the five-axis sample positioner binds `LinearStage`;
- the sample-to-detector propagation rail binds `LinearStage` (the 2-BM `CameraZ` precedent);
- the scintillator binds `Scintillator` and the sCMOS / CCD / photon-counting cameras bind `Camera`;
- the machine state binds the loose `StorageRing`.

Unlike ID32 (which bound no catalog Method), SYRMEP's core Practices bind the real catalog `tomography`, `continuous_rotation_tomography`, `mosaic_tomography`, `dark_field`, `flat_field`, and `center_alignment` Methods. The three new technique slugs (`helical_tomography`, `white_beam_tomography`, `phase_retrieval`) are registered pending in `tests/unit/deployments/test_site_descriptor.py` until they enter pilot scope.

### The Tango / DonkiOrchestra control plane

SYRMEP is the first Tango + DonkiOrchestra controls house-style in the fleet. CORA models the control handles as opaque edge strings over the `ControlPort`, the way the MX3 / ID32 heterogeneous-control precedent does. The crucial difference from ID32: **SYRMEP's handles are not in public source**. The DonkiOrchestra scan engine's source location is unconfirmed and the acquisition code is in the private `gitlab.elettra.eu` `syrmep_acquisition` group, so the handles are confirm-pending placeholders rather than read addresses (`CTRL-1`). The DonkiOrchestra orchestration (Elettra 2.0: the "Executer" device server) is the seam CORA's edge replaces, conducting over Tango rather than over BLISS or EPICS.

### Deliberately not here yet

| Deferred | Why | Tracking |
| --- | --- | --- |
| Every concrete control handle | not in public source (private gitlab group, unconfirmed DonkiOrchestra source) | `CTRL-1` |
| PSS permit signals and shutters | not in public source, not invented | `PSS-1` |
| The default routine camera, pixel size, FOV | sources name multiple detectors without pinning the routine one | `DET-1` |
| Helical CT, white-beam tomography, phase retrieval as catalog Methods | a CORA-scope decision pending pilot scope | `TECH-1` |
| The reconstruction pipeline as Compute provenance | post-acquisition compute; modelled when the deployment firms up | `COMPUTE-1` |
| Scenarios, operations runbook, live experiment view | SYRMEP is not yet driven by CORA | follows the [2-BM](../2-bm/index.md) shape |

## Open questions

*What CORA needs the SYRMEP team to confirm before the model can be trusted.*

SYRMEP was reverse-engineered from public material (the [elettra.eu SYRMEP pages](https://www.elettra.eu/elettra-beamlines/syrmep.html), the EPJ Plus 2024 SYRMEP review, and the J. Synchrotron Rad. 2023 large-FOV paper). The hardware facts are read from those sources, but **the control handles are not in public source**: the in-house DonkiOrchestra scan engine's source location is unconfirmed and the acquisition code lives in the private `gitlab.elettra.eu` `syrmep_acquisition` group. So unlike the ID32 BLISS scaffold, the device handles on the [device pages](index.md) are confirm-pending placeholders rather than read addresses. This is CORA's first Elettra Site and first Tango / DonkiOrchestra controls house-style. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

### Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a white-beam optics zone feeding one imaging / tomography endstation, or a different layout? | A shared `syrmep-optics` zone and the `syrmep-experiment` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The bending-magnet source detail (critical energy, field across the 2.0 / 2.4 GeV modes). | A bending-magnet source (section 6); 5.59 keV critical energy and 1.45 T field at 2.4 GeV. | The source Asset detail. |

### Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The Elettra storage-ring state SYRMEP reads (the 2.0 GeV / 300 mA and 2.4 GeV modes; current, fill). | Observe-only machine state, a loose `StorageRing`; exact Tango handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The Si(111) DCM energy range and the authoritative bound: the EPJ Plus 2024 review states mono 10-40 keV, the elettra.eu spec still lists 9-40 keV. The Bragg / offset handles. | A `Monochromator` (Si(111), fixed-exit, 20 mm offset); energy a `PseudoAxis`; range 10-40 keV mono. | The monochromator and incident-energy Assets. |
| MODE-1 | Blocks-go-live | The mono / white (pink) beam switch: how the beam bypasses the DCM, and the white-beam energy (~16-30 keV average). | The beam mode is a per-Asset setting on the `Monochromator` (the 2-BM DMM insert/retract precedent). | The beam-mode modelling. |
| OPT-1 | Nice-to-have | The white-beam-defining mask dimensions and drawing. | A fixed `Mask` upstream of the optics. | The mask Asset detail. |
| OPT-2 | Blocks-go-live | The laminar-beam slit blade-axis map and handles, and the beam dimensions (sources cite ~120 x 4 mm at 20 m and ~160 x 5 mm at 23 m). | Slits bound to `Slit`; a ~120-160 mm wide, ~4-5 mm tall laminar beam at 7 mrad acceptance. | The slit Asset detail and beam geometry. |
| FOIL-1 | Nice-to-have | The absorption / beam-hardening filter foils and the selector handle. | Filters bound to `Filter`; foils pending. | The filter Asset detail. |

### Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The rotation stages: the heavy-payload rotator (up to 120 kg, 1-20 deg/s, 0.02 deg) is documented, but the standard sample rotation stage range / bearing / model and the rotator wobble spec are not. | A `RotaryStage` for the tomographic theta; a standard-stage variant and the wobble spec pending. | The rotation-stage modelling. |
| SAMPLE-1 | Blocks-go-live | The five-axis sample-positioning stage: motor vendors, micro-positioning resolution, axes, and handles. | A `LinearStage` facet set; vendors / resolution / axis map pending. | The sample-stage modelling. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The default routine-tomography camera and its pixel size and field of view: the sCMOS (2048x2048, 0.9-5.7 um) or the CCD (4008x2672, 4.5 um)? | Both bind `Camera`; the routine camera is pending. | The detector modelling. |
| DET-2 | Nice-to-have | The sample-to-detector propagation rail and the two-axis detector rail handles. | A `LinearStage` (range 3-160 cm). | The propagation-rail Asset. |
| DET-3 | Nice-to-have | The routine scintillator screen type and thickness (published configs cite GGG:Eu). | A `Scintillator`; type and thickness pending. | The scintillator Asset. |
| DET-4 | Nice-to-have | The XC Hydra photon-counting detector pixel size and configuration, and when it is used. | A `Camera` for the large-specimen / helical CT mode; pixel size pending. | The photon-counting detector modelling. |

### Controls and acquisition

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | The Tango device namespaces and the DonkiOrchestra (Elettra 2.0: "Executer") scan-engine handles: SYRMEP's control source is not public. | A Tango device floor with the in-house DonkiOrchestra scan engine; handles are confirm-pending placeholders. | The whole control plane (every device handle in the Inventory). |
| PSS-1 | Blocks-go-live | The Elettra personnel-safety permit signals and the front-end / safety shutters. | Enclosure permit leaves and a `Shutter`, carried pending, not invented. | The safety / interlock structure. |

### Techniques and compute

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | The technique scope: core tomography reuses catalog Methods, but helical CT, white-beam tomography, and phase retrieval are not yet catalog Methods. | The core tomography Practices reuse catalog Methods; the rest are pending and render unlinked. | Whether the new techniques enter the catalog (a CORA-scope call on [Model](#deliberately-not-here-yet)). |
| COMPUTE-1 | Nice-to-have | The reconstruction pipeline (the SYRMEP Tomo Project: phase retrieval, ring removal, FBP / iterative on ASTRA + TomoPy) and whether CORA records its invocation as Method / Compute provenance. | Post-acquisition compute CORA records as provenance, not data it owns. | The compute-provenance modelling. |
| SUP-1 | Nice-to-have | The facility supplies a run draws on (cooling water for the optics, the vacuum extent of the white-beam path). | `PhotonBeam`, `CoolingWater`, `Vacuum`. | The Supply detail. |

### Governance

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GOV-1 | Nice-to-have | The Elettra operator pool and safety-review structure (site-level). | Carried pending on the Elettra Site, not instantiated per beamline. | The governance principals. |
