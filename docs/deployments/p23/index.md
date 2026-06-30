# P23

*PETRA III's in-situ X-ray diffraction beamline, and CORA's fifteenth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P23` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P23` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the experiment motor bank; scenarios deferred) |
| Source | An undulator for hard X-ray in-situ diffraction |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P23's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23), branch `debian/jessie`) and a verified research brief. The P23 registry is thin: it exposes one large generic motor bank (`eh_mot*`) whose per-axis roles are not labelled, and the detectors are not exposed. Every value is carried as `confirm` until P23 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P23 different

P23 "In-situ X-ray Diffraction and Imaging" is **CORA's fifteenth PETRA III beamline** and the facility's in-situ / operando diffraction beamline: diffraction and imaging of samples under in-situ conditions (electrochemistry, thin-film growth, controlled sample environments).

P23 is a thin **reuse-and-reinforce** scaffold: it coins no new vocabulary. The motor bank binds `LinearStage`, and the technique reuses the pending `diffraction` slug (`TECH-1`). The detectors are not exposed in this registry slice and are carried as a pending `Camera` placeholder (`DET-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Experiment hutch (`p23-eh`) | Yes | The experiment / instrument motor bank (grouped) + a dev stub |
| The optics / diffractometer breakdown | Grouped | The mono / mirrors / diffractometer are not individually labelled (`OPT-1`, `DIFF-1`) |
| The detectors | Pending placeholder | Not exposed in this registry slice (`DET-1`) |
| The per-axis bank roles | Grouped, not resolved | The `eh_mot*` bank not labelled (`GROUP-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A fifteenth beamline at an existing Site, modelled thinly.** PETRA III is already modelled; P23 adds the in-situ diffraction beamline and its practice. The sparse registry slice means a thin model with the detectors carried pending, the same model-what-the-source-supports posture as P11 / P21 / P65.
- **No new Family.** The motor bank binds `LinearStage`; the catalog is unchanged.
- **Optics / diffractometer grouped.** The monochromator, mirrors, and diffractometer are not individually labelled in the registry, so they are grouped into the experiment stage with the breakdown carried as questions (`OPT-1`, `DIFF-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the experiment / instrument motor bank.
- [Sample](equipment/sample.md): the experiment stage (grouped), the dev stub.
- [Detector](equipment/detector.md): the in-situ diffraction detectors (carried pending).

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p23/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P23 is designed to do, as intent. In-situ diffraction reuses the pending `diffraction` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P23 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P23's place as a thin in-situ diffraction scaffold, and the record of what is deliberately deferred.

## Not yet documented

P23 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
