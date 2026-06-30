# CSX

*The Coherent Soft X-ray scattering beamline at NSLS-II, and CORA's second soft X-ray deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `CSX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 23` (the 23-ID-1 branch; PV namespace `XF:23ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | Two elliptically-polarizing undulators on the canted `SR:C23-ID` straight |
| Control stack | NSLS-II EPICS / ophyd (the same floor as the other NSLS-II beamlines); handles bound from the profile collection, carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/csx-profile-collection](https://github.com/NSLS2/csx-profile-collection)). EPICS PVs are real and verified against the `startup/csx1` files; vendor part numbers, serials, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until CSX staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What CSX consolidates

CSX is the **consolidation** of the soft X-ray regime that SIX opened. It earns abstractions rather than minting them:

- **It graduates `GratingMonochromator`.** CSX's VLS-PGM (200-2200 eV) is the second soft X-ray plane-grating monochromator after SIX's, which earns the rule-of-three: `GratingMonochromator` becomes a catalog Family in this deployment (see [Model](model.md#what-this-deployment-graduates)). The grating line density and energy range are a per-Asset settings difference, not a Family split.
- **It reuses the Diffractometer Assembly.** Its TARDIS endstation is an in-vacuum hkl E6C diffractometer; its circles bind the catalog `Goniometer` Family and the composed `Assembly(Diffractometer)`, a third hkl diffractometer after 4-ID and 8-ID (now in a soft X-ray, in-vacuum context).
- **It adds no new family of its own.** Every device reuses an existing catalog Family.

It runs on the inboard `23-ID-1` branch of the canted 23-ID straight (two EPUs feed the sector).

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`XF:23IDA`, `XF:23ID1-OP`) | Yes | Two EPUs, the front-end mirror, the VLS-PGM, the refocusing mirror, the slits |
| TARDIS endstation (`XF:23ID1-ES`) | Yes | The E6C diffractometer, the sample stage, the cryostat, the coherent detectors |
| `GratingMonochromator` | Graduated | The 2nd soft PGM earns it into the catalog (see [Model](model.md#what-this-deployment-graduates)) |
| Nanopositioner / holography detail | Coarsely | The sample holography stage is carried; the fine piezo nanopositioner is deferred |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

- [Source](beamline.md): the generated device walk: the two canted EPUs, the front-end mirror, the VLS-PGM, the refocusing mirror, and the branch slits.
- [Sample](equipment/sample.md): the TARDIS E6C diffractometer, the reciprocal-space coordination, the sample stage, and the cryostat temperature controller.
- [Detector](equipment/detector.md): the FastCCD and AXIS coherent area detectors, the fast shutter and diode, and the counting electronics.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/csx/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of CSX is designed to do, as intent. Its resonant and coherent soft X-ray scattering legs reuse existing catalog Methods, carried pending.

## Governance

[Governance](governance.md): who will act at CSX and the trust shape that gates their commands. People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md).

## Model

[Model](model.md): the developer's by-kind index, the `GratingMonochromator` graduation this deployment earns, and the record of what is deliberately deferred.

## Not yet documented

CSX is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
