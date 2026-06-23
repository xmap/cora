# 32-ID

*Canted insertion-device beamline at APS. This page walks the part of 32-ID CORA models today: the shared optics spine and the transmission X-ray microscope. It is a design-phase scaffold, not a running model.*

| Property | Value |
| --- | --- |
| Asset | `32-ID` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 32` (organizational grouping; not a registered Asset) |
| Status | Design-phase scaffold (spine + TXM modelled; other instruments deferred) |
| Sources | Canted pair of planar undulators (downstream, upstream); branch mapping unconfirmed |
| Control stack | APS EPICS (the same floor as 2-BM); device handles not yet on file |

!!! warning "Design phase, and partial by intent"
    This is a first-cut scaffold. CORA models only what the published [32-ID docs](https://github.com/decarlof/32id-docs) state with confidence, and carries every value as `confirm` until 32-ID staff verify it. Several of 32-ID's instruments are deliberately not modelled yet (see [Scope](#scope-what-is-and-is-not-modelled)). What CORA needs the team to confirm is on [Open questions](questions.md).

## What makes 32-ID different

32-ID is structurally unlike the 2-BM and TomoWISE tomography beamlines, in three ways that drive how much of it CORA models now:

- **Canted source.** Two undulators in one straight section feed two experimental branches. Whether the optics hutch serves both branches or is duplicated per branch, and which undulator feeds which branch, is the one structural unknown (tracked as `TOPO-1`).
- **Three stations.** `32-ID-A` is optics only (no experiments); `32-ID-B` and `32-ID-C` are experimental hutches. All three are lead-shielded and rated for white and mono beam.
- **Four in-house instruments.** A transmission X-ray microscope (TXM), white-beam high-speed imaging and ultrafast diffraction (HSI / HSID), an additive-manufacturing laser rig (AM), and a projection microscope (PM). Only the TXM sits squarely in CORA's tomography heritage.

## Scope: what is and is not modelled

This scaffold earns its abstractions. It models the part of 32-ID that is unambiguous and within CORA's existing shape, and defers the rest until the beamline forces it.

| Part | In this scaffold | Why |
| --- | --- | --- |
| Optics spine (`32-ID-A`) | Yes | Canted source, Si(111) monochromator, white-beam slits, mode shutter; shared by all branches |
| TXM endstation (`32-ID-C`) | Yes, coarse | 32-ID's tomography instrument; zone-plate optics bound to loose Families pending confirmation |
| HSI / HSID (`32-ID-B`) | No | White-beam imaging and diffraction; diffraction has no precedent in CORA's catalog (owner scope) |
| AM laser rig (`32-ID-B`) | No | An actuated non-X-ray energy source; modelled as a safety hazard, not an Asset (owner scope) |
| Projection microscope | No | Still "space holder" in the source docs; modelling it now would be invention |

The deferred instruments and the reasons are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

The systems CORA models today, along the beam:

- [Source](beamline.md): the 32-ID-A optics spine, rendered as the generated source-stage device walk: the canted undulator pair, the front-end mask and white-beam slits, the Si(111) monochromator, and the P4-50 mode shutter that selects white-beam or monochromatic operation.
- [Sample](equipment/sample.md): the TXM sample stage in 32-ID-C, the granite-supported rotation and zone-plate optics.
- [Detector](equipment/detector.md): the TXM indirect-detection chain (scintillator, objective, camera).

Cutting across them:

- [Controls](equipment/controls.md): the EPICS control stack and the remote-access path; device handles are not yet on file.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with Families and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/32-id/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 32-ID is designed to do, as intent. Each is a portable [Catalog](../../catalog/methods.md) Method that an APS [Practice](../aps/index.md#the-techniques-adapted-here) would adapt.

## Governance

[Governance](governance.md): who will act at 32-ID and the trust shape that gates their commands. People and agents are facility principals at the [APS Site](../aps/index.md#who-acts-here).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's 32-ID content lives, and the record of what is deliberately deferred.

## Not yet documented

32-ID is pre-build in CORA, so the operations runbook (procedures, recipes, cautions, enclosure permits) and the live experiment view are deliberately not written yet: a runbook for a beamline CORA does not yet drive would be invention, not record. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
