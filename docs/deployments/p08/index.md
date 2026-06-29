# P08

*PETRA III's high-resolution diffraction beamline, and CORA's twelfth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P08` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P08` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + experiment endstation; scenarios deferred) |
| Source | An undulator for high-resolution hard X-ray diffraction |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P08's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no crystal cuts, energy calibration, or physical positions; those are open questions. The diffractometer / sample motor bank is grouped (per-axis roles not labelled). Every value is carried as `confirm` until P08 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P08 different

P08 "High Resolution Diffraction Beamline" is **CORA's twelfth PETRA III beamline** and the facility's high-resolution diffraction beamline: surface / interface diffraction, reflectivity, and high-resolution powder / single-crystal diffraction on a six-circle Kohzu diffractometer, with a notably rich detector set (Eiger, Pilatus, Mythen, PerkinElmer, Vortex SDD).

P08 coins **no new Family**. The six-circle Kohzu diffractometer binds the catalog `Goniometer` Family (not the composed `Diffractometer` Assembly, the P01 EH2 call); the DCM and multilayer monochromators bind `Monochromator`; the CRL `Transfocator`; the hexapod `Hexapod`; the absorber `Filter`; the detectors `Camera` / `EnergyDispersiveSpectrometer`. The technique (high-resolution diffraction / reflectivity) reuses the pending `diffraction` slug (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p08-oh`) | Yes | The undulator, the DCM, the multilayer mono, the CRL, the absorber, the slits |
| Experiment endstation (`p08-eh`) | Yes | The six-circle diffractometer, the hexapod, the detectors |
| The per-axis roles of the diff bank | Grouped, not resolved | The `diff*` Kohzu axes not labelled per axis; grouped (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; a Lambda on a bare host (`HOST-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A twelfth beamline at an existing Site.** PETRA III is already modelled; P08 adds the high-resolution diffraction beamline and its practice.
- **No new Family.** Every device binds an existing catalog Family across the optics and diffractometer endstation.
- **The diffractometer binds Goniometer.** The six-circle Kohzu binds the catalog `Goniometer`, not the composed `Diffractometer` Assembly (`DIFF-1`).
- **The Mythen strip detector is modelled as a Camera.** The one-dimensional Mythen2 binds `Camera` for now (a fold-vs-promote question for the catalog owner, the P10 precedent, `DET-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the DCM + multilayer mono, the CRL, the slits.
- [Sample](equipment/sample.md): the six-circle diffractometer and the hexapod.
- [Detector](equipment/detector.md): the Eiger, Pilatus, Mythen, PerkinElmer, and Vortex detectors.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p08/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P08 is designed to do, as intent. High-resolution diffraction reuses the pending `diffraction` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P08 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P08's place as the high-resolution diffraction beamline, and the record of what is deliberately deferred.

## Not yet documented

P08 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
