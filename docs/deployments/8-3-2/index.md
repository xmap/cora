# 8.3.2

*The ALS hard X-ray micro-tomography beamline, and CORA's first ALS deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `8.3.2` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [ALS](../als/index.md) (bound via `facility_code = "als"`, `FacilityKind = Site`) |
| Beamline | `8.3.2` (the ALS beamline number; not a registered Asset) |
| Status | First cut, reverse-engineered, design phase (the source, optics, sample stack, and detector; scenarios deferred) |
| Source | A Superbend (superconducting bending magnet), 6,000-43,000 eV, ~1 micron resolution |
| Control stack | ALS BCS (Beamline Control System, a LabVIEW house-style); the fleet's first BCS plane. Live handles not public, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from ALS's public facility pages ([als.lbl.gov/beamlines/8-3-2](https://als.lbl.gov/beamlines/8-3-2/), [microct.lbl.gov](https://microct.lbl.gov/)) and the public [als-computing](https://github.com/als-computing) GitHub org. The device **structure** is read from the DXchange / DXfile HDF5 data-record schema that the ALS tooling reads ([als-computing/scicat_beamline](https://github.com/als-computing/scicat_beamline), [als-computing/microct](https://github.com/als-computing/microct)); the **live control handles are not public** (ALS runs BCS, a LabVIEW system, not EPICS, so there are no PVs to read). Vendor models, the multilayer / crystal detail, and the BCS channel handles are open questions. Every value is carried as `confirm` until 8.3.2 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes 8.3.2 different

8.3.2 is **CORA's first ALS Site** (the Advanced Light Source at Lawrence Berkeley National Laboratory) and its **first BCS control house-style**. Every prior Site is EPICS (the APS and NSLS-II beamlines), Tango / Sardana (MAX IV, ALBA), or BLISS (the ESRF); 8.3.2 introduces BCS, the ALS Beamline Control System, a LabVIEW stack. Its science is hard X-ray micro-tomography: non-destructive 3D imaging of solid objects at ~1 micron resolution, from a Superbend source over 6,000-43,000 eV.

For the modelling, 8.3.2 is a **reuse-and-reinforce** deployment: it brings a wholly new Site and a new control-system house-style, but coins **no new vocabulary**. It is a tomography beamline, so it reuses the imaging Families and Methods the fleet already carries (the 2-BM pilot, the NSLS-II FXI design, and the ALBA FAXTOR design):

- The imaging device tree (`StorageRing`, `InsertionDevice`, `Monochromator`, `Slit`, `Filter`, `RotaryStage`, `LinearStage`, `Scintillator`, `Objective`, `Camera`) reuses the established tomography Families.
- The micro-CT acquisition binds the catalog `tomography` Method; the fast fly-scan acquisition binds `continuous_rotation_tomography`.
- The BCS control plane is the fleet's first; ALS originated BCS, so this is its home facility.

8.3.2 coins no new Family and changes nothing in the catalog.

## The data-record descriptor mode

8.3.2 introduces a third way of seeding a reverse-engineered descriptor, between the two the fleet already uses:

- **2-BM** is operational and fully measured (real control handles, vendor models).
- **FXI** reads real EPICS PVs from a public bluesky profile collection.
- **FAXTOR** has no public device manifest at all (handles fully omitted).

8.3.2 sits between FXI and FAXTOR. The device **structure**, the named device hierarchy and its axes, is verified from the DXchange / DXfile **HDF5 data-record schema** that the ALS tooling reads (the SciCat ingester and the `microct` reconstruction backend). But the **live control handles are not public**: BCS is LabVIEW, not EPICS, so there are no PVs, and the BCS channel handles live with ALS staff. Each device therefore cites its HDF5 metadata path as the evidence for its structure, and carries the live control handle as `confirm`-pending (`CTRL-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Source state and Superbend | Yes | The storage-ring state (observe-only) and the Superbend source, recorded as a Supply |
| Conditioning optics | Yes | The monochromator, the horizontal / vertical slits, and the attenuating filter |
| Sample-motor stack | Yes | The tomographic rotary and the sample-centring linear stages |
| Detector chain | Yes | The scintillator, the camera objective, the camera, and the motorized detector stack |
| The detector model | Named, not bound | Detector specs are per-dataset values in the data record, not a fixed manifest; the `Camera` Asset is carried pending (`DET-1`) |
| The rotation axis identity | No | The data record exposes `axis1pos` / `axis2pos` / `axis5pos`; which is the tomographic rotation is pending (`ROT-1`) |
| BCS control handles | No | BCS is LabVIEW (not EPICS) and no public per-beamline channel manifest exists; carried pending, not invented (`CTRL-1`) |
| PSS permit signals and hutch grouping | No | Not published per beamline, carried pending, not invented (`PSS-1`, `ENC-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A new Site, a new control house-style.** ALS is the first ALS Site (`deployments/als/site.yaml`); its BCS / LabVIEW stack is the fleet's first BCS plane, modelled with handles omitted pending (`CTRL-1`), not invented.
- **No new families.** The Superbend binds `InsertionDevice` (recorded as a Supply), the energy optic `Monochromator`, the rotary `RotaryStage`, the camera `Camera`; the catalog is unchanged (the 2-BM / FXI / FAXTOR imaging precedent).
- **Structure from the data record, handles pending.** The device tree and axes are read from the DXfile HDF5 schema; the live BCS handles are carried `confirm`-pending (`CTRL-1`).
- **The detector is named, not bound.** Detector specs are per-dataset acquisition values, not a fixed manifest, so the camera model is carried pending so the [Detector](equipment/detector.md) page is real (`DET-1`).

## The beamline

The systems in the area the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the storage-ring state, the Superbend, the monochromator, the slits, and the attenuating filter.
- [Sample](equipment/sample.md): the tomographic rotary stage and the sample-centring linear stages.
- [Detector](equipment/detector.md): the scintillator, the camera objective, the camera, and the motorized detector stack.

Cutting across them:

- [Controls](equipment/controls.md): the ALS BCS / LabVIEW control stack, the emerging Bluesky-over-BCS acquisition layer, and the `splash_flows` data-movement / reconstruction seam; handles not published per beamline, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/8-3-2/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 8.3.2 is designed to do, as intent. Micro-CT reuses CORA's catalog tomography Methods.

## Governance

[Governance](governance.md): who will act at 8.3.2 and the trust shape that gates their commands. People and agents are facility principals at the [ALS Site](../als/index.md).

## Model

[Model](model.md): the developer's by-kind index, the new ALS Site and BCS / LabVIEW control house-style, and the record of what is deliberately deferred.

## Not yet documented

8.3.2 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals and shutters are not published per beamline and are not invented here (`PSS-1`). The ALS-U upgrade (dark time no sooner than October 2027) may reshape 8.3.2; its upgrade fate is a staff question (`ALSU-1`).
