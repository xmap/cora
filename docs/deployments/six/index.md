# SIX

*The Soft Inelastic X-ray scattering (RIXS) beamline at NSLS-II, and CORA's first soft X-ray deployment. This page walks the operational core CORA models today. It is a reverse-engineered first cut, not yet a running model.*

| Property | Value |
| --- | --- |
| Asset | `SIX` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [NSLS-II](../nsls2/index.md) (bound via `facility_code = "nsls2"`, `FacilityKind = Site`) |
| Sector | `Sector 2` (PV namespace `XF:02ID*`; not a registered Asset) |
| Status | First cut, reverse-engineered, design-phase (descriptor + docs; scenarios deferred) |
| Source | An elliptically-polarizing undulator on the `SR:C02-ID` straight |
| Control stack | NSLS-II EPICS / ophyd (the same floor as FXI / HXN / BMM); handles bound from the profile collection, carried confirm |

!!! warning "First cut, and confirm-pending by intent"
    This scaffold was reverse-engineered from the beamline's own bluesky profile collection ([NSLS2/six-profile-collection](https://github.com/NSLS2/six-profile-collection)). EPICS PVs are real and verified against the `startup/*.py` files; vendor part numbers, serials, and physical positions are not in the profile collection and are open questions. Every value is carried as `confirm` until SIX staff verify it. What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes SIX different

SIX is **CORA's first soft X-ray beamline**. The hard X-ray deployments before it never exercised this regime, so SIX introduced three device classes new to the catalog. One (`GratingMonochromator`) has since graduated, earned by the 2nd soft beamline CSX; the other two stay loose at n=1:

- **A grating monochromator, not a crystal DCM.** The PGM disperses with an interchangeable grating (500 / 1200 / 1800 l/mm) and a premirror at a fixed-focus c-value; the exit slit sets the energy resolution. There is no Bragg crystal, so it binds the `GratingMonochromator` Family (graduated across SIX + CSX), not the catalog `Monochromator`.
- **A RIXS spectrometer arm.** The signature instrument is a meters-long energy-dispersive arm (a bridge truss, an in-arm optics chamber that disperses, and a detector chamber) that swings to a scattering angle and spreads the emitted soft X-rays onto a photon-counting camera. No catalog Family fits a multi-chamber dispersive arm, so it binds a loose `SpectrometerArm` Family.
- **A UHV cryostat manipulator.** The sample sits on an x/y/z/theta manipulator under ultra-high vacuum and cryogenic cooling, a sample-environment role no catalog motion Family captures, so it binds a loose `Manipulator` Family.

Everything else (the EPU, the mirrors, the slits, the shutters, the camera, the counters, the temperature controller) reuses an existing catalog Family.

## Scope: what is and is not modelled

| Part | In this cut | Why |
| --- | --- | --- |
| Optics (`XF:02IDA/B/C`) | Yes | EPU, M1, PGM, M3/M4 refocusing, the slits, the exit slit |
| RIXS endstation (`XF:02IDD-ES`) | Yes | The UHV cryostat manipulator, the spectrometer arm, the RIXS camera |
| New device classes | Mixed | `GratingMonochromator` graduated (earned by CSX); `SpectrometerArm`, `Manipulator` stay loose at n=1 (see [Model](model.md#new-loose-families)) |
| Legacy end-station PGM (`Mono:2` / `espgm`) | No | A legacy / discarded instance in the profile collection; the live `Mono:1` PGM is modelled |
| Integration scenarios + vendor Models | No | Design-phase; the descriptor and docs come first |

The deferred parts are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

- [Source](beamline.md): the generated device walk: the EPU, M1 and the front-end slit and polarization diagnostic, the PGM and its slits, and the M3/M4 refocusing optics and exit slit.
- [Sample](equipment/sample.md): the UHV cryostat manipulator, the sample chamber, the endstation mirrors, and the sample temperature controller.
- [Detector](equipment/detector.md): the RIXS spectrometer arm, the photon-counting RIXS camera, and the counting electronics.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS / ophyd control stack and the bluesky-orchestration seam; handles bound from the profile collection and carried confirm.

The cross-cutting reference view is the [Inventory](inventory.md). The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/six/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of SIX is designed to do, as intent. RIXS is a soft X-ray scattering technique new to CORA's imaging-heritage catalog and renders unlinked, carried pending.

## Governance

[Governance](governance.md): who will act at SIX and the trust shape that gates their commands. People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md).

## Model

[Model](model.md): the developer's by-kind index, the new loose families this deployment introduces, and the record of what is deliberately deferred.

## Not yet documented

SIX is not yet driven by CORA, so the operations runbook and the live experiment view are deliberately not written yet. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
