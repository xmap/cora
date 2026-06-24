# 8-ID

*X-ray Photon Correlation Spectroscopy (XPCS) beamline at APS. This page walks the operational core CORA models today across four stations. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `8-ID` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 8` (organizational grouping; not a registered Asset) |
| Status | First cut, reverse-engineered (operational core modelled; robotic sample changer and the softGlue timing graph deferred) |
| Sources | Two undulators on the S08ID straight section |
| Control stack | APS EPICS (the same floor as 2-BM); device handles bound from the beamline's instrument repo, carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own Bluesky instrument repo ([BCDA-APS/8id-bits](https://github.com/BCDA-APS/8id-bits)); the extraction is in [`research/aps-reverse-engineering/`](https://github.com/xmap/cora/tree/main/research/aps-reverse-engineering). Like 4-ID it binds the real EPICS control handles, because 8-ID is operational. Every value is carried as `confirm` until 8-ID staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes 8-ID different

8-ID is the coherent-scattering beamline, and it is the deployment that **earns 4-ID's new device classes into the catalog**:

- **Coherence and speed.** XPCS measures intensity fluctuations of a coherent beam over time, so the detectors are fast area detectors (Eiger 4M, Lambda 2M, Rigaku 3M) gated by a softGlue FPGA timing fabric, downstream of an evacuated flight path.
- **A second diffractometer.** 8-ID-E carries a six-circle Huber diffractometer (mu, eta, chi, phi, nu, delta). Together with 4-ID's diffractometers this confirms the `Assembly(Diffractometer)` shape.
- **Independent reuse of 4-ID's device classes.** 8-ID has its own transfocators, LakeShore temperature controllers, and Sydor / TetrAMM beam-position monitors. Because these now appear at two independent beamlines (4-ID and 8-ID), they are held loose pending a cross-facility gate-review, recorded in the promotion register (see [Model](model.md#loose-families-held-for-gate-review)).

It runs across four stations: `8-ID-A` (optics), `8-ID-D` (focusing), `8-ID-E` (diffractometer endstation), `8-ID-I` (XPCS endstation).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics + focusing (`8-ID-A/D`) | Yes | Undulators, monochromator, FMBO mirrors, slits, the CRL transfocators |
| Diffractometer endstation (`8-ID-E`) | Yes | Six-circle Huber (binds the `Goniometer` Family) + temperature + beam-position monitor; the `Assembly(Diffractometer)` is in the catalog (`DIFF-1`) |
| XPCS endstation (`8-ID-I`) | Yes | Aerotech sample stages, the coherent area detectors, the flight path |
| UR5 robotic sample changer | No | A sample-changer shape CORA does not model yet (`SAMPLE-2`) |
| softGlue timing graph | Coarsely | One `TimingController`; the full FPGA signal graph is `XPCS-3` |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

- [Source](beamline.md): the generated device walk: the undulators, the MN1 monochromator, the FMBO mirrors and slits, and the 8-ID-D CRL transfocators.
- [Sample](equipment/sample.md): the 8-ID-E six-circle diffractometer and the 8-ID-I XPCS sample stages (Aerotech, rheometer, temperature-controlled holders).
- [Detector](equipment/detector.md): the coherent area detectors, their stage, the flight path and beam stop, and the beam-position monitors.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS control stack and the softGlue timing fabric; handles bound from the beamline config and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/8-id/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 8-ID is designed to do, as intent. XPCS and small-angle scattering are new to CORA's imaging-heritage catalog and render unlinked, carried pending.

## Governance

[Governance](governance.md): who will act at 8-ID and the trust shape that gates their commands. People and agents are facility principals at the [APS Site](../aps/index.md#who-acts-here).

## Model

[Model](model.md): the developer's by-kind index, the catalog graduation that lands with this deployment, and the record of what is deliberately deferred.

## Not yet documented

8-ID is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
