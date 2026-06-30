# P10

*PETRA III's coherence-applications beamline (XPCS and coherent imaging), and CORA's sixth PETRA III beamline. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `P10` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [PETRA III (DESY)](../petra-iii/index.md) (bound via `facility_code = "petra-iii"`, `FacilityKind = Site`) |
| Sector | `P10` (the PETRA III beamline name; not a registered Asset) |
| Status | First cut, reverse-engineered, operating beamline (the optics + three experiment areas; scenarios deferred) |
| Source | An undulator delivering coherent hard X-rays for XPCS and coherent imaging |
| Control stack | PETRA III Tango device floor + Sardana scan layer; per-beamline device handles read from the public OnlineXML registry, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from P10's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p10](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p10), branch `debian/jessie`) and a verified research brief. The registry carries real Tango device names and control handles, but no coherence lengths, energy calibration, or physical positions; those are open questions. The registry exposes generically-named motor banks (`OPT_MOT`, `E1_MOT`, `E2_MOT`) whose per-axis roles are not labelled, grouped here as the optics / endstation stages. Every value is carried as `confirm` until P10 staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes P10 different

P10 "Coherence Applications" is **CORA's sixth PETRA III beamline** and the fleet's **second XPCS beamline** after the APS 8-ID exercise. Its science is X-ray photon correlation spectroscopy (XPCS), coherent diffraction imaging / ptychography, and coherent-beam diffraction, across three experiment areas (E1 coherent imaging, E2 XPCS / diffraction, LAB).

The notable modelling first: P10 is the **first PETRA III beamline whose primary technique is already a graduated catalog Method**. XPCS was earned into the catalog by the APS 8-ID deployment, so P10's XPCS practice binds it **directly, not pending**, the first non-pending PETRA III practice. Coherent imaging reuses the pending `ptychography` / `coherent_surface_scattering` slugs (`TECH-1`).

P10 coins **no new Family**: the undulator binds `InsertionDevice`, the mono `Monochromator`, the CRL `Transfocator`, the hexapod `Hexapod`, the slits `Slit`, the two-theta arm `RotaryStage`, the shutter `Shutter`, the wide detector suite `Camera`, the fluorescence detectors `EnergyDispersiveSpectrometer`, the LAB diffractometer `Goniometer`.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics hutch (`p10-opt`) | Yes | The undulator, the DCM, the optics stages, the beam shutter |
| E1 coherent imaging (`p10-e1`) | Yes | The hexapod, the CRL, the guard slit, the sample bank, the Quadro detector |
| E2 XPCS / diffraction (`p10-e2`) | Yes | The mirrors, the sample piezos, the two-theta arm, the guard slit, the detector suite, the LCX piezo sub-station |
| LAB (`p10-lab`) | Yes | The simulated diffractometer and the offline detectors |
| The per-axis roles of the motor banks | Grouped, not resolved | `OPT_MOT`, `E1_MOT`, `E2_MOT` not labelled per axis; grouped as stage Assets (`GROUP-1`) |
| Tango / Sardana handles | Yes, from the registry | Read from the public OnlineXML; the Lambda / Lima cameras report on a bare host (`HOST-1`, `CTRL-1`) |
| PSS permit signals | No | Not in the OnlineXML; the beam shutter is read but the permit leaves are not (`PSS-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## Key modelling decisions

- **A sixth beamline at an existing Site.** PETRA III is already modelled; P10 adds the coherence beamline and the XPCS / coherent-imaging practices.
- **The first non-pending PETRA III practice.** XPCS binds the graduated catalog `xpcs` Method directly (the 8-ID precedent); the other PETRA III beamlines all carry pending practices because their techniques are not yet earned.
- **No new Family.** Every device binds an existing catalog Family across a five-enclosure layout.
- **The shared detectors are homed in the endstation that operates them.** The Lambda and Lima cameras report on a bare `p10` host; per the cross-host mapping decision they are homed in E2 (the XPCS detection stage) with the host flagged (`HOST-1`).

## The beamline

The systems in the areas the beam passes through, plus the controls that drive them. See [the beamline overview](equipment/index.md) for how the areas relate.

- [Source](beamline.md): the generated device walk: the undulator, the optics hutch, and the three experiment areas.
- [Sample](equipment/sample.md): the E1 hexapod + CRL, the E2 mirrors + sample piezos + two-theta arm, the LAB diffractometer, the LCX nano-positioner.
- [Detector](equipment/detector.md): the Quadro, Pilatus, PCO, Lambda, Eiger, Andor, Mythen, and Lima detectors.

Cutting across them:

- [Controls](equipment/controls.md): the PETRA III Tango floor + Sardana scan layer and the orchestration seam; handles read from the OnlineXML, carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/p10/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of P10 is designed to do, as intent. XPCS binds the graduated `xpcs` Method; coherent imaging reuses the pending `ptychography` Method (`TECH-1`).

## Governance

[Governance](governance.md): who will act at P10 and the trust shape that gates their commands. People and agents are facility principals at the [PETRA III Site](../petra-iii/index.md).

## Model

[Model](model.md): the developer's by-kind index, P10's place as the fleet's second XPCS beamline and PETRA III's first earned-Method practice, and the record of what is deliberately deferred.

## Not yet documented

P10 is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS permit signals are not in the OnlineXML and are not invented here (`PSS-1`).
