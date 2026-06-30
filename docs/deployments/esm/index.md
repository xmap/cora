# ESM

*The Electron Spectro-Microscopy beamline at NSLS-II, and CORA's third soft X-ray deployment, the first photoemission one. This page walks the ARPES branch CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `ESM` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 21` (PV namespace `XF:21ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (ARPES branch; XPEEM/LEEM deferred) |
| Source | Two elliptically-polarizing undulators (EPU57, EPU105) on the `SR:C21-ID` straight |
| Control stack | NSLS-II EPICS / ophyd (the same floor as the other NSLS-II beamlines); handles bound from the profile collection, carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/esm-arpes-profile-collection](https://github.com/NSLS2/esm-arpes-profile-collection)). EPICS PVs are real and verified against the `startup/*.py` files; vendor part numbers, serials, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until ESM staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes ESM different

ESM is **CORA's first photoemission beamline**. Every prior beamline measures photons; ESM measures **electrons** (photon-in / electron-out), which brings a new detector regime:

- **A hemispherical electron analyzer.** The Scienta SES records electron counts over a kinetic-energy by emission-angle window set by the pass energy and lens mode. No photon-detector Family fits, so it binds the `ElectronAnalyzer` Family (presents the Detector Role), which graduated once SST earned the 2nd Scienta SES.

It is also a **consolidation** of the soft X-ray regime:

- **Reuses the graduated `GratingMonochromator`.** ESM's PGM is the third soft X-ray plane-grating monochromator (after SIX and CSX), so it binds the catalog Family rather than minting one.
- **Graduates `Manipulator`.** ESM's LT six-axis UHV cryostat manipulator is the second UHV sample manipulator after SIX, earning the abstraction (two-deployment threshold): `Manipulator` becomes a catalog Family in this deployment, and SIX's references are swept loose to graduated (see [Model](model.md#what-this-deployment-graduates)).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`XF:21IDA/B/C`) | Yes | Two EPUs, M1, the PGM, M3, the KB pair M4A, M4B, the slits and exit slits |
| ARPES endstation (`XF:21ID1-ES`) | Yes | The UHV cryostat manipulator, the SES electron analyzer, the flux monitors |
| `Manipulator` | Graduated | The 2nd UHV manipulator earns it into the catalog (see [Model](model.md#what-this-deployment-graduates)) |
| XPEEM/LEEM branch (`21-ID-2`) | No | The LEEM/PEEM electron microscope is a future loose `ElectronMicroscope` Family (`PEEM-1`) |
| Sample-prep / load-lock transfer | No | The prep / analysis-chamber manipulators and the load-lock claw are deferred (`SAMPLE-1`) |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

- [Source](beamline.md): the generated device walk: the two EPUs, M1 and the polarization diagnostic, the PGM and M3, and the KB refocusing pair, M4B, and the exit slits.
- [Sample](equipment/sample.md): the ARPES UHV cryostat sample manipulator and the cryostat temperature controller.
- [Detector](equipment/detector.md): the hemispherical electron analyzer and the beam-current flux monitors.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/esm/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of ESM is designed to do, as intent. ARPES is a photoemission technique new to CORA's catalog and renders unlinked, carried pending.

## Governance

[Governance](governance.md): who will act at ESM and the trust shape that gates their commands. People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md).

## Model

[Model](model.md): the developer's by-kind index, the `Manipulator` graduation and `ElectronAnalyzer` this deployment introduces, and the record of what is deliberately deferred.

## Not yet documented

ESM is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
