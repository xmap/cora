# FAXTOR

*ALBA's BL31 fast X-ray micro-CT and radiography beamline, and CORA's first ALBA deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `FAXTOR` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [ALBA](../alba/index.md) (bound via `facility_code = "alba"`, `FacilityKind = Site`) |
| Sector | `BL31` (the ALBA beamline code; not a registered Asset) |
| Status | First cut, reverse-engineered, design / commissioning phase (the shared optics + the experiment endstation; scenarios deferred) |
| Source | A multipole wiggler feeding monochromatic (8-50 keV) and filtered-white (30-70 keV) imaging |
| Control stack | ALBA Tango / Sardana / Taurus (the fleet's second Tango / Sardana house-style after MAX IV); no public per-beamline handles, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from ALBA's public facility pages ([cells.es/en/beamlines/bl31-faxtor](https://www.cells.es/en/beamlines/bl31-faxtor)) and a verified research brief. ALBA publishes no per-beamline device manifest, so the control handles are not bound; vendor part numbers, the detector model, energy details, and physical positions are open questions. Every value is carried as `confirm` until FAXTOR staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes FAXTOR different

FAXTOR is **CORA's eighth Site** (ALBA, Barcelona) and its **second Tango / Sardana / Taurus control plane** (MAX IV is the first; the rest are EPICS, and the ESRF is BLISS). Its science is fast X-ray tomography and radiography: continuous-rotation micro-CT up to 20 Hz, 0.5-10 um pixel size, with absorption, propagation-phase, and grating-based contrast, fed by a multipole wiggler through a double multilayer monochromator (mono) or a filter set (filtered white beam).

For the modelling, FAXTOR is a **reuse-and-reinforce** deployment: it brings a wholly new Site and control-system house-style, but coins **no new vocabulary**. It is a tomography beamline, so it reuses the imaging Families and Methods the fleet already carries (the 2-BM pilot and the MAX IV TomoWISE design):

- The imaging device tree (`RotaryStage`, `LinearStage`, `Table`, `Shutter`, `Scintillator`, `Camera`) reuses the established tomography Families.
- The fast continuous-rotation tomography binds the catalog `continuous_rotation_tomography` Method; the absorption / phase micro-CT binds `tomography`.
- The Tango / Sardana control plane is the second consumer of the MAX IV controls house-style; ALBA originated Sardana, so this is its home facility.

FAXTOR coins no new Family and changes nothing in the catalog.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Shared optics (`faxtor-optics`) | Yes | The multipole wiggler, the double multilayer monochromator, the filter set, the beam slits |
| Experiment endstation (`faxtor-experiment`) | Yes | The rotary stage, the sample positioning and table, the fast shutter, and the scintillator + fast camera detector |
| The fast camera model | Named, not bound | The detector model is not published; a `Camera` Asset is carried fully pending (`DET-1`) |
| Exact optics handles | No | The DMM, mirrors, filters, and slits are carried confirm-pending (`MONO-1`, `OPT-1`, `OPT-2`, `FILT-1`) |
| Tango / Sardana / IcePAP handles | No | Absent from any public per-beamline manifest, carried pending, not invented (`CTRL-1`) |
| PSS permit signals and vacuum extent | No | Not published per beamline, carried pending, not invented (`PSS-1`, `SUP-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A new Site, a familiar control house-style.** ALBA is the 8th Site (`deployments/alba/site.yaml`); its Tango / Sardana / Taurus stack is the second after MAX IV, so the control plane is modelled the way TomoWISE did (handles omitted pending, `CTRL-1`), not invented.
- **No new families.** The wiggler binds `InsertionDevice`, the DMM `Monochromator`, the rotary `RotaryStage`, the camera `Camera`; the catalog is unchanged (the 2-BM / TomoWISE imaging precedent).
- **The detector is named, not bound.** The fast camera is the decision-critical device whose model is unpublished; it is carried as a pending `Camera` Asset so the [Detector](equipment/detector.md) page is real (`DET-1`).
- **Radiography is a pending Practice.** Fast tomography reuses the catalog tomography Methods; radiography has no portable Method yet and is carried pending, reusing the 7-BM radiography slug (`TECH-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the storage-ring state, the multipole wiggler, the double multilayer monochromator, the filter set, and the beam slits.
- [Sample](equipment/sample.md): the experiment endstation, the rotary stage, the sample positioning and table, and the fast shutter.
- [Detector](equipment/detector.md): the scintillator and the fast imaging camera.

Cutting across them:

- [Controls](equipment/controls.md): the ALBA Tango / Sardana / Taurus control stack and the Sardana-orchestration seam; handles not published per beamline, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/faxtor/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of FAXTOR is designed to do, as intent. Fast tomography reuses CORA's catalog tomography Methods; radiography renders unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at FAXTOR and the trust shape that gates their commands. People and agents are facility principals at the [ALBA Site](../alba/index.md).

## Model

[Model](model.md): the developer's by-kind index, the new ALBA Site and Tango / Sardana control house-style, and the record of what is deliberately deferred.

## Not yet documented

FAXTOR is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not published per beamline and are not invented here (`PSS-1`).
