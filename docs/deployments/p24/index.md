# P24

*PETRA III's chemical crystallography beamline, and CORA's sixteenth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P24` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P24` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + EH1 / EH2 hutches; scenarios deferred) |
| Source | An undulator for hard X-ray single-crystal / chemical crystallography |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P24's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p24](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p24), branch `debian/jessie`) and a verified research brief. The P24 registry exposes generic motor banks (`oh_mot*`, `mot*`) whose per-axis roles are not labelled, and the area detector is not exposed. Every value is carried as `confirm` until P24 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P24 different

P24 "Chemical Crystallography" is **CORA's sixteenth PETRA III beamline** and the facility's single-crystal / small-molecule chemical crystallography beamline: chemical crystallography on a diffractometer with area detection, across two experiment hutches (EH1, EH2).

P24 is a **reuse-and-reinforce** scaffold: it coins no new vocabulary. The diffractometer / sample positioning binds `LinearStage` (the registry does not label a goniometer), the slits `Slit`, the fluorescence MCA `EnergyDispersiveSpectrometer`, the coupled axes `PseudoAxis`, and the technique reuses the pending `diffraction` slug (no dedicated chemical-crystallography Method exists; `TECH-1`). The area detector is not exposed and is carried as a pending `Camera` placeholder (`DET-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p24-oh`) | Yes | The optics motor bank (grouped) + the ps1 / ps2 slits |
| EH2 main hutch (`p24-eh2`) | Yes | The diffractometer / sample bank, the coupled axes, the MCA, the area detector (pending) |
| EH1 hutch (`p24-eh1`) | Yes | The secondary sample bank |
| The diffractometer geometry | Grouped | Not labelled in the registry; grouped into the sample stage (`DIFF-1`) |
| The area detector | Pending placeholder | Not exposed in this registry slice (`DET-1`) |
| The per-axis bank roles | Grouped, not resolved | `oh_mot*`, `mot*` not labelled (`GROUP-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A sixteenth beamline at an existing Site.** PETRA III is already modelled; P24 adds the chemical crystallography beamline and its practice.
- **No new Family.** The motor banks bind `LinearStage`, the slits `Slit`, the MCA `EnergyDispersiveSpectrometer`, the coupled axes `PseudoAxis`; the catalog is unchanged.
- **The diffractometer is grouped, the area detector pending.** The registry does not label a goniometer or the area detector, so the diffractometer is grouped into the sample stage (`DIFF-1`) and the detector carried pending (`DET-1`), the model-what-the-source-supports posture.
- **Chemical crystallography reuses the `diffraction` Method.** No dedicated chemical-crystallography Method exists; the practice reuses the pending `diffraction` slug.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the optics bank, the slits.
- [Sample](equipment/sample.md): the EH2 diffractometer / sample bank, the EH1 sample bank.
- [Detector](equipment/detector.md): the MCA fluorescence detectors and the area detector (pending).

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p24/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P24 is designed to do, as intent. Chemical crystallography reuses the pending `diffraction` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P24 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P24's place as the chemical crystallography beamline, and the record of what is deliberately deferred.

## Not yet documented

P24 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
