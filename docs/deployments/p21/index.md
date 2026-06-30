# P21

*PETRA III's Swedish Materials Science beamline (high-energy diffraction), and CORA's thirteenth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P21` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P21` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + EH3 + LAB stations; scenarios deferred) |
| Source | An undulator for high-energy hard X-ray materials science |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P21's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p21](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p21), branch `debian/jessie`) and a verified research brief. The P21 registry is thin: most devices are area-grouped generic motor banks (`oh_u*`, `eh3_u*`, `lab*`) whose per-axis roles are not labelled, and the detectors are not exposed. Every value is carried as `confirm` until P21 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P21 different

P21 "Swedish Materials Science" is **CORA's thirteenth PETRA III beamline** and a Swedish-collaboration high-energy materials beamline with two branches: P21.1 (high-energy diffraction / total scattering / PDF) and P21.2 (high-energy diffraction / imaging).

P21 is a thin **reuse-and-reinforce** scaffold: it coins no new vocabulary. The motor banks bind `LinearStage`, the slits `Slit`, and the techniques reuse the pending `diffraction` / `total_scattering` slugs (`TECH-1`). The detectors are not exposed in this registry slice and are carried as a pending `Camera` placeholder (`DET-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| P21.2 optics (`p21-oh`) | Yes | The optics motor bank (grouped) |
| EH3 endstation (`p21-eh3`) | Yes | The sample bank (grouped) |
| LAB station (`p21-lab`) | Yes | The sample bank + the slit virtual axes |
| The P21.1 station | Not modelled | Exposed only bookkeeping devices in this slice (`HOST-1`) |
| The detectors | Pending placeholder | Not exposed in this registry slice (`DET-1`) |
| The per-axis bank roles | Grouped, not resolved | `oh_u*`, `eh3_u*`, `lab*` not labelled (`GROUP-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A thirteenth beamline at an existing Site, modelled thinly.** PETRA III is already modelled; P21 adds the Swedish Materials Science beamline and its practices. The sparse registry slice means a thin model with the detectors carried pending, the same model-what-the-source-supports posture as P11 / P65.
- **No new Family.** The motor banks bind `LinearStage`, the slits `Slit`; the catalog is unchanged.
- **Multiple Tango hosts.** P21 is split across the `hasep212oh` (optics), `hasep21eh3` (EH3), and `haspp21lab` (LAB) hosts; the P21.1 station (`hasep211eh`) exposed only bookkeeping devices and is noted, not modelled (`HOST-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the P21.2 optics bank.
- [Sample](equipment/sample.md): the EH3 and LAB sample banks, the LAB slits.
- [Detector](equipment/detector.md): the high-energy diffraction detectors (carried pending).

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p21/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P21 is designed to do, as intent. High-energy diffraction and total scattering reuse the pending `diffraction` / `total_scattering` Methods (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P21 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P21's place as a thin Swedish Materials Science scaffold, and the record of what is deliberately deferred.

## Not yet documented

P21 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
