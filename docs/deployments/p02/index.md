# P02

*PETRA III's hard X-ray diffraction beamline (powder / total scattering + extreme conditions), and CORA's eighth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P02` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P02` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the shared optics + the P02.1 powder and P02.2 extreme-conditions endstations; scenarios deferred) |
| Source | An undulator delivering high-energy hard X-rays (~60 keV) for diffraction |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P02's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no crystal cuts, the pressure-cell detail, energy calibration, or physical positions; those are open questions. The registry exposes large generically-named motor banks (`eh1a / eh1b / eh2a / eh2b`) whose per-axis roles are not labelled, grouped here as the endstation stages. Every value is carried as `confirm` until P02 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P02 different

P02 "Hard X-ray Diffraction Beamline" is **CORA's eighth PETRA III beamline** and the fleet's high-energy diffraction beamline, with two branches: **P02.1** (powder diffraction / total scattering / pair-distribution-function, ~60 keV) and **P02.2** (extreme conditions, diamond-anvil-cell high-pressure diffraction).

For the modelling, P02 coins **no new Family** but brings two notable things:

- The fleet's **second diamond-anvil-cell** endstation: the P02.2 high-pressure environment binds the catalog `PressureCell` Family the APS 13-id deployment introduced. Adding P02 as its second consumer crossed the rule-of-three promotion threshold and graduated the Family to the catalog (earned across 13-id and P02, `PRESSURE-1`).
- **Bendable focusing mirrors**: the HFM / VFM mirrors are exposed as curvature / ellipticity attribute motors, modelled as two `Mirror` Assets (`OPT-1`).

The techniques (powder diffraction, total scattering / PDF, high-pressure diffraction) reuse the pending `powder_diffraction` / `total_scattering` slugs that i11 / i15-1 / XPD already share (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Shared OH1 optics (`p02-oh1`) | Yes | The undulator, the DCM, the HFM / VFM mirrors, the slits, the optics bank |
| P02.1 powder endstation (`p02-1-powder`) | Yes | The sample banks (eh1a / eh1b), the sample environment, the Pilatus 1M + PerkinElmer |
| P02.2 extreme conditions (`p02-2-extreme`) | Yes | The sample banks (eh2a / eh2b), the pressure cell, the beam monitor, the fluorescence detectors |
| The per-axis roles of the motor banks | Grouped, not resolved | `eh1a/b`, `eh2a/b` not labelled per axis; grouped as stage Assets (`GROUP-1`) |
| The CH1 / CH2 dummy stubs | Noted, not modelled | Test / placeholder dummy motors (`STUB-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; the OH1 optics shared with P03 (`CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **An eighth beamline at an existing Site.** PETRA III is already modelled; P02 adds the high-energy diffraction beamline and its powder / total-scattering / high-pressure practices.
- **The diamond-anvil cell binds the catalog PressureCell.** P02.2 is the second consumer of the `PressureCell` Family, crossing the rule-of-three promotion threshold and graduating it to the catalog (earned across 13-id and P02, `PRESSURE-1`).
- **The bendable mirrors are two Mirror Assets.** The HFM / VFM curvature / ellipticity / tilt / z attribute motors are grouped as `HorizontalFocusingMirror` and `VerticalFocusingMirror` (`OPT-1`).
- **The shared P02 / P03 optics live here.** P02 owns the OH1 high-heatload optics hutch that P03 also draws from (the `HOST-1` cross-reference noted on the P03 page); modelled as the `p02-oh1` enclosure.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the OH1 optics, and the two endstations.
- [Sample](equipment/sample.md): the P02.1 powder sample stage + environment, the P02.2 sample stage + pressure cell.
- [Detector](equipment/detector.md): the Pilatus 1M, PerkinElmer, and fluorescence detectors.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p02/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P02 is designed to do, as intent. Powder diffraction, total scattering, and high-pressure diffraction reuse the pending `powder_diffraction` / `total_scattering` Methods (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P02 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P02's place as the fleet's second diamond-anvil-cell deployment, and the record of what is deliberately deferred.

## Not yet documented

P02 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
