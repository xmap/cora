# CMS

*The Complex Materials Scattering beamline at NSLS-II, beamline 11-BM: soft-matter and thin-film structure by small-, wide-, and medium-angle scattering (SAXS / WAXS / MAXS), grazing-incidence scattering (GISAXS / GIWAXS), and specular X-ray reflectivity (XR). CMS is the NSLS-II twin of [SMI](../smi/index.md). This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `CMS` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 11` (PV namespace `XF:11BM*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | A bending magnet (no insertion device; the 2-BM / 7-BM pattern) (`SRC-1`) |
| Control stack | NSLS-II EPICS / ophyd (the same floor as FXI / HXN / SRX / BMM / SIX / CHX / ESM / SMI); handles bound from the profile collection, carried confirm (`CTRL-1`) |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/cms-profile-collection](https://github.com/NSLS2/cms-profile-collection)). EPICS PVs are real and read from the `startup/*.py` files; vendor part numbers, serials, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until CMS staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes CMS different

Be honest about this beamline: most of CMS is reinforcement, not novelty. Its small-, wide-, and medium-angle scattering (SAXS / WAXS / MAXS) and its grazing-incidence scattering (GISAXS / GIWAXS) overlap the fleet heavily. CMS is the direct NSLS-II twin of [SMI](../smi/index.md) (12-ID), and it shares its science axis with Diamond [I22](../i22/index.md) and APS [9-ID](../9-id/index.md) / [12-ID-E](../12-id-e/index.md). The scattering reuses the same `Camera` / `Goniometer` / `Slit` / `BeamStop` / `FluxMonitor` vocabulary, coins no new Family, and sits on the same pending scattering Method slugs the twins left deferred. So the scattering is the shape ported once more, not a new shape.

CMS has two genuinely distinct contributions:

- **Specular X-ray reflectivity (XR).** XR is the second consumer of the reflectivity Method after Diamond [i10](../i10/index.md) (its soft X-ray RASOR sibling), and CMS realizes it with no new hardware. There is no physical two-theta detector arm and no point detector: the area detector stays fixed, and the "two-theta" is a synthetic software region-of-interest that slides across the fixed Pilatus face to where the reflected beam lands as the sample theta (`sth`) is stepped (`XR-1`). XR reuses the `Goniometer` (`sth`), the `Camera` (the Pilatus, read over a tracked region), and the `FluxMonitor` (incident flux), and coins nothing.
- **Another NSLS-II beamline re-testing the Site kernel.** CMS exercises the NSLS-II Site / Federation kernel once more, alongside its fleet siblings. The value is confidence that the kernel holds, not a new abstraction.

CMS coins **no new Family**, nothing graduates, and the catalog is unchanged. Frame the rest of these docs around what is distinct, XR and the Site reinforcement, and read the scattering as the fleet shape ported, not invented.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`XF:11BMA`, `XF:11BM1`) | Yes | The DMM, the toroidal and elliptical mirrors, the FOE slit, the attenuator foils, the beam-energy pseudo-axis, the FOE flux monitor (`ENC-1`) |
| Endstation (`XF:11BMB`) | Yes | The sample goniometer, the surface-leveling stage, the GIBar exchange arm, the Linkam stage, the SAXS / WAXS / MAXS detectors, the detector stage, the beamstop, the flux and beam-position monitors, the support table (`ENC-1`) |
| New device classes | None | Zero new Families coined; nothing graduates; the catalog is unchanged |
| Specular reflectivity (XR) | Method, not device | A software region-of-interest on the fixed Pilatus; reuses `Goniometer` + `Camera` + `FluxMonitor` (`XR-1`) |
| The GIBar sample-exchange robot | Catalog `LinearStage` | Modelled by its stage axes at n=1; no `SampleExchanger` Family coined (`ROBOT-1`) |
| The two-theta detector arm | No (does not exist) | XR's two-theta is synthetic; CORA invents no physical arm and no point detector (`XR-1`) |
| The insertion device | No (does not exist) | 11-BM is a bending magnet; CORA invents no `InsertionDevice` (`SRC-1`) |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md).

## Key modelling decisions

- **Reuse over coin.** Every device binds an existing catalog or loose Family, and the catalog changes nothing. No second fleet beamline has yet earned a new abstraction here.
- **11-BM is a bending-magnet source, so no `InsertionDevice`.** Machine state is observed through the loose `StorageRing` Family; the bending-magnet source detail is carried pending (`MACHINE-1`, `SRC-1`).
- **The DMM binds the catalog `Monochromator`.** The double-multilayer monochromator (`XF:11BMA-OP{Mono:DMM-Ax:Bragg}`) is a multilayer Bragg optic, following the 2-BM double-multilayer precedent and not the soft X-ray `GratingMonochromator`. Energy calibrations near 13.5 keV are carried confirm (`MONO-1`).
- **Specular reflectivity (XR) is a Method, not a device.** There is no physical two-theta detector arm: the area detector stays fixed and the two-theta is a synthetic software region-of-interest that slides across the fixed Pilatus face to where the reflected beam lands as `sth` is stepped. XR reuses the `Goniometer` (`sth`), the `Camera` (the Pilatus, read over a tracked region), and the `FluxMonitor` (incident flux). It coins no device, no two-theta arm, and no point detector, and is shared with i10 as the second consumer (`XR-1`).
- **The GIBar sample-exchange robot binds `LinearStage`.** The multi-axis sample-bar loader is modelled by its stage axes at n=1; no `SampleExchanger` Family is coined pending a second fleet sample robot (`ROBOT-1`).
- **Zero new Families coined, nothing graduates, the catalog is unchanged.**

## The beamline

- [Source](beamline.md): the generated device walk: the storage ring machine state, the double-multilayer monochromator and the beam-energy pseudo-axis over its Bragg angle, the toroidal and elliptical mirrors, the FOE slit, the attenuator foils, and the FOE flux monitor.
- [Sample](equipment/sample.md): the sample goniometer (with `sth` as both the grazing-incidence and the specular-reflectivity angle), the surface-leveling tilt stage, the GIBar sample-exchange arm, and the Linkam temperature stage.
- [Detector](equipment/detector.md): the SAXS, WAXS, and MAXS Pilatus detectors (the SAXS 2M also reads specular reflectivity XR), the detector translations and telescoping flight path, the SAXS beamstop, the endstation flux monitors, and the four-quadrant diamond-diode beam-position monitor.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm (`CTRL-1`).

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/cms/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of CMS is designed to do, as intent. SAXS maps to `small_angle_scattering` (shares i22 / SMI), WAXS and MAXS to `wide_angle_scattering` (shares i22), GISAXS and GIWAXS to `grazing_incidence_scattering` (shares 9-ID, with SMI the NSLS-II twin), and XR to `reflectivity` (shares i10, as the second consumer). All render unlinked, carried pending (`TECH-1`).

## Governance

[Governance](governance.md): who will act at CMS and the trust shape that gates their commands. People and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here), surfacing through their actions and gated by a Zone-plus-Conduit-plus-Policy trust shape. The NSLS-II operator pool and review are pending at the Site (`GOV-1`). PSS search-and-secure permit signals and the photon / front-end shutters are absent from the profile collection and carried pending, not invented (`PSS-1`).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's CMS content lives, and the record of what is deliberately deferred. CMS introduces no new Family.

## Not yet documented

CMS is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take. The PSS search-and-secure permit signals and shutters are absent from the profile collection and are not invented here (`PSS-1`).
