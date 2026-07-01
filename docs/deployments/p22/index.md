# P22

*PETRA III's hard X-ray photoelectron spectroscopy beamline (HAXPES), and CORA's fourteenth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P22` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P22` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the shared P09 optics + the HAXPS endstation; scenarios deferred) |
| Source | An undulator (shared with P09) for hard X-ray photoemission |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P22's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22), branch `debian/jessie`) and a verified research brief. The registry shows P22 sharing the P09 optics chain (the undulator, DCM, mirrors, and phase retarder report on `p09/` addresses), with the HAXPS endstation as a grouped motor bank and the electron analyzer not exposed. Every value is carried as `confirm` until P22 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P22 different

P22 "Hard X-ray Photoelectron Spectroscopy (HAXPES)" is **CORA's fourteenth PETRA III beamline** and the facility's hard X-ray photoemission beamline. Its defining structural fact is that it **shares its optics chain with P09**: the undulator, the double-crystal monochromator, the mirror pair, the phase retarder, and the absorber are P09 devices (on `p09/` addresses), and P22 is the HAXPES branch off that chain (`SHARED-1`).

P22 coins **no new Family**. It reuses the catalog `PhaseRetarder` Family (P22 is the third consumer via the shared optics, completing the 4-ID/P09/P22 rule-of-three). The HAXPS sample stage binds `Manipulator`; the electron analyzer (the defining HAXPES instrument, not exposed in this registry slice) is carried pending against the catalog `ElectronAnalyzer` Family (graduated at NSLS-II ESM). The technique (HAXPES) reuses the pending `angle_resolved_photoemission` slug (`TECH-1`).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Shared P09 / P22 optics (`p22-optics`) | Yes | The undulator, the DCM, the mirrors, the phase retarder, the absorber (all P09 devices) |
| HAXPS endstation (`p22-haxps`) | Yes | The sample / instrument manipulator bank |
| The electron analyzer | Pending | The defining HAXPES instrument, not exposed in this slice (`DET-1`) |
| The per-axis sample-bank roles | Grouped, not resolved | The `p22/motor` bank not labelled per axis (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; the optics on the P09 host (`HOST-1`, `SHARED-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML; carried pending, not invented (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A fourteenth beamline at an existing Site, sharing P09's optics.** PETRA III is already modelled; P22 adds the HAXPES beamline. Its optics are P09 devices, homed in the `p22-optics` enclosure with the shared-optics relationship flagged (`SHARED-1`, `HOST-1`).
- **No new Family.** The phase retarder reuses the catalog `PhaseRetarder`; the sample stage binds `Manipulator`; the electron analyzer binds the catalog `ElectronAnalyzer` (carried pending, `DET-1`).
- **The electron analyzer is named, not bound.** The defining HAXPES detector is not a motor row in the registry; it is carried pending against the catalog `ElectronAnalyzer` Family so the [Detector](equipment/detector.md) page is real.

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the shared P09 optics (undulator, DCM, mirrors, phase retarder, absorber).
- [Sample](equipment/sample.md): the HAXPS sample manipulator.
- [Detector](equipment/detector.md): the electron analyzer (carried pending).

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p22/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P22 is designed to do, as intent. HAXPES reuses the pending `angle_resolved_photoemission` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P22 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md); the shared P09 optics couple their access state (`SHARED-1`).

## Model

[Model](model.md): the developer's by-kind index, P22's place as the HAXPES branch off the P09 optics, and the record of what is deliberately deferred.

## Not yet documented

P22 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
