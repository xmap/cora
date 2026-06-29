# SYRMEP

*Elettra's hard X-ray radiology and microtomography beamline, and CORA's first Elettra deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `SYRMEP` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Elettra](../elettra/index.md) (bound via `facility_code = "elettra"`, `FacilityKind = Site`) |
| Sector | `SYRMEP` (the hard X-ray imaging beamline; the bending magnet of section 6, not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (the source, optics, sample, and detector; scenarios deferred) |
| Source | Bending-magnet beam, monochromatic (Si(111) DCM) or white / pink |
| Control stack | Elettra Tango device floor with the in-house DonkiOrchestra scan engine (Elettra 2.0: the "Executer" device server); handles not in public source, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from public material (the [elettra.eu SYRMEP pages](https://www.elettra.eu/elettra-beamlines/syrmep.html), the EPJ Plus 2024 SYRMEP review, and and the J. Synchrotron Rad. 2023 large-FOV paper). The hardware facts (source, optics, detectors, stages, scan modes) are read from those sources; **the control handles are not in public source** (the in-house DonkiOrchestra scan engine's source location is unconfirmed and the acquisition code lives in the private `gitlab.elettra.eu` `syrmep_acquisition` group), so they are carried as confirm-pending placeholders, not invented Tango device URLs. Every value is carried `confirm` until SYRMEP staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes SYRMEP different

SYRMEP is two firsts at once. It is **CORA's eighth Site** (Elettra Sincrotrone Trieste), a re-test of the Site and Federation kernel, and it brings the **first Tango + DonkiOrchestra control house-style** to the fleet. The Tango device floor is shared with the ESRF's ID32, but the orchestration seam is different: SYRMEP runs the in-house, trigger-driven DonkiOrchestra framework (DonkiDirector scheduling DonkiPlayers over a ZeroMQ trigger train, collecting into HDF5), not BLISS and not EPICS. Its science is hard X-ray microtomography: absorption, propagation-based phase-contrast, and diffraction-enhanced imaging, plus a clinical breast-CT programme (SYRMA-3D).

For the modelling, SYRMEP's significance is the opposite of ID32's: where ID32 brought three loose families to a rule-of-three, **SYRMEP coins nothing new in the catalog**. It is a tomography beamline, so it reuses the established imaging spine the 2-BM, FXI, and 7-BM beamlines already share (`RotaryStage`, `LinearStage`, `Camera`, `Scintillator`, `Slit`, `Filter`, `Monochromator`). It is the cleanest possible re-test: a brand-new Site and control house-style on entirely familiar device vocabulary, binding the real catalog tomography Methods.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Source + optics (`syrmep-optics`) | Yes | The storage-ring state, the bending-magnet beam (a Supply), the Si(111) DCM and the mono / white beam mode, the incident-energy axis, the laminar-beam slits, and the filters |
| Sample (`syrmep-experiment`) | Yes | The heavy-payload rotation stage (`RotaryStage`) and the five-axis sample positioner (`LinearStage`) |
| Detector (`syrmep-experiment`) | Yes | The sample-to-detector propagation rail (`LinearStage`), the scintillator, and the sCMOS / CCD / photon-counting cameras (`Camera`) |
| Exact control handles | No | SYRMEP's Tango / DonkiOrchestra handles are not in public source, carried confirm-pending (`CTRL-1`) |
| PSS permit signals and shutters | No | Absent from public source, carried pending, not invented (`PSS-1`) |
| The reconstruction pipeline | Recorded as provenance, not built | The SYRMEP Tomo Project (phase retrieval, ring removal, FBP / iterative on ASTRA + TomoPy) is post-acquisition compute (`COMPUTE-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A new Site and a new control house-style.** Elettra is the 8th Site (`deployments/elettra/site.yaml`); the Tango / DonkiOrchestra handles are modelled as opaque edge strings over the `ControlPort`, the way the MX3 / ID32 heterogeneous-control precedent does, but carried confirm-pending because they are not in public source (`CTRL-1`).
- **No new family; the imaging spine is reused wholesale.** The bending-magnet source is a Supply (the 2-BM precedent); the DCM binds `Monochromator` with the mono / white beam as a per-Asset setting (the 2-BM DMM insert/retract precedent); the rotation stage binds `RotaryStage`; the cameras bind `Camera`; the incident energy is a `PseudoAxis`.
- **Real catalog tomography Methods, carried pending.** Unlike ID32 (which bound no catalog Method), SYRMEP's Practices reuse the catalog `tomography`, `continuous_rotation_tomography`, `mosaic_tomography`, `dark_field`, `flat_field`, and `center_alignment` Methods directly; the helical, white-beam, and phase-retrieval Methods are not yet in the catalog and render unlinked (`TECH-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the storage-ring state, the bending-magnet beam, the Si(111) DCM and the mono / white beam mode, the incident-energy axis, the laminar-beam slits, and the filters.
- [Sample](equipment/sample.md): the heavy-payload rotation stage and the five-axis sample positioner.
- [Detector](equipment/detector.md): the sample-to-detector propagation rail, the scintillator, and the sCMOS / CCD / photon-counting cameras.

Cutting across them:

- [Controls](equipment/controls.md): the Tango / DonkiOrchestra control stack and the orchestration seam; handles carried confirm-pending because they are not in public source.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/syrmep/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of SYRMEP is designed to do, as intent. The core tomography Methods are in CORA's catalog already; the helical, white-beam, and phase-retrieval Methods are new and render unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at SYRMEP and the trust shape that gates their commands. People and agents are facility principals at the [Elettra Site](../elettra/index.md).

## Model

[Model](model.md): the developer's by-kind index, the new Site and control house-style, the reuse of the imaging spine, and the record of what is deliberately deferred.

## Not yet documented

SYRMEP is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are absent from public source and are not invented here (`PSS-1`).
