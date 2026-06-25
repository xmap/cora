# SST

*The Spectroscopy Soft and Tender beamline at NSLS-II, and CORA's fourth soft X-ray deployment. This page walks the operational core CORA models today across its two branches. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `SST` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 7` (PV namespace `XF:07ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | Two EPUs on the `SR:C07-ID` straight (EPU60 soft, U42 tender) |
| Control stack | NSLS-II EPICS / ophyd, config-driven (devices.toml + the sst-base library); handles carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collections ([NSLS2/sst-rsoxs-profile-collection](https://github.com/NSLS2/sst-rsoxs-profile-collection), [NSLS2/sst-haxpes-profile-collection](https://github.com/NSLS2/sst-haxpes-profile-collection)) and the [NSLS-II-SST/sst-base](https://github.com/NSLS-II-SST/sst-base) device library. SST is the config-driven extraction mode: device instances live in `devices.toml` and the per-axis PV grammar in the pip libraries, so each PV is the toml prefix combined with the class suffixes, carried `confirm` until SST staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What SST adds

SST is the soft + tender X-ray spectroscopy beamline: two branches off a shared front end, a plane-grating monochromator for the soft branch and a Si double-crystal monochromator for the tender branch. It is a **consolidation** deployment that also earns one graduation:

- **It graduates `ElectronAnalyzer`.** The HAXPES (tender) endstation uses a Scienta SES hemispherical electron energy analyzer, the second after ESM. That earns the rule-of-three, so `ElectronAnalyzer` becomes a catalog Family (ESM's references are swept loose to graduated; see [Model](model.md#what-this-deployment-graduates)).
- **It reuses three graduated families across soft and tender.** The soft PGM is the 4th `GratingMonochromator`; the tender DCM reuses `Monochromator`; the RSoXS and HAXPES UHV manipulators are the 3rd and 4th `Manipulator`.
- **It is the config-driven extraction mode.** Unlike the `startup/*.py` beamlines, SST's instances are TOML + a shared `sst-base` library; the descriptor's PVs are verified against both.

It runs across two branches: SST-1 (soft, the RSoXS endstation) and SST-2 (tender, the HAXPES endstation).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Shared front end (`XF:07IDA`) | Yes | EPUs, M1 mirror, FOE slit, shutters |
| SST-1 soft + RSoXS | Yes | The soft PGM, the RSoXS manipulator, the Greateyes WAXS detector, the I0 monitors |
| SST-2 tender + HAXPES | Yes | The Si DCM, the tender mirrors, the HAXPES manipulator + slit, the Scienta SES |
| UCAL / NEXAFS TES microcalorimeter | No | A cryogenic microcalorimeter detector regime CORA has not modelled (a future family) |
| VPPEM photoemission microscope | No | An electron-microscope endstation, deferred (the `PEEM-1` family, shared with ESM's XPEEM) |
| Full multi-channel I400 | Coarsely | Only the one instantiated ion-chamber channel is modelled (`DET-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

- [Source](beamline.md): the generated device walk: the two EPUs, the shared front-end mirror and slit, the soft PGM (SST-1), and the tender DCM and mirrors (SST-2).
- [Sample](equipment/sample.md): the RSoXS UHV manipulator (SST-1) and the HAXPES UHV manipulator and slit (SST-2).
- [Detector](equipment/detector.md): the RSoXS Greateyes WAXS detector and flux monitors (SST-1), and the HAXPES Scienta SES electron analyzer and ion chamber (SST-2).

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack, its config-driven instrument map, and the bluesky-orchestration seam; handles carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/sst/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of SST is designed to do, as intent. RSoXS reuses the catalog scattering Method; HAXPES is a soft / tender photoemission technique carried pending.

## Governance

[Governance](governance.md): who will act at SST and the trust shape that gates their commands. People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md).

## Model

[Model](model.md): the developer's by-kind index, the `ElectronAnalyzer` graduation this deployment earns, and the record of what is deliberately deferred.

## Not yet documented

SST is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
