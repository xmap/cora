# 2-ID

*Hard X-ray microprobe beamline at APS, Sector 2. This page walks the part of 2-ID CORA models today: the 2-ID-D scanning fluorescence microprobe hutch. It is a design-phase scaffold, not a running model.*

| Property | Value |
| --- | --- |
| Asset | `2-ID` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [APS](../aps/index.md) (bound via `facility_code = "aps"`, `FacilityKind = Site`) |
| Sector | `Sector 2` (organizational grouping; not a registered Asset) |
| Modelled hutch | `2-ID-D` (the scanning fluorescence microprobe; a sister station is deferred) |
| Status | Design-phase scaffold (2-ID-D endstation modelled; source optics and live wiring deferred) |
| Source | Sector 2 insertion device (undulator); type and post-APS-U configuration unconfirmed |
| Control stack | APS EPICS with a Bluesky RunEngine over the scanRecord (the same floor as 2-BM); device handles not yet on file |

!!! warning "Design phase, and mined from a tool corpus"
    This scaffold is built from the APS-microprobe integration in the [Experiment Automation Agents (EAA)](https://github.com/AdvancedPhotonSource/EAA) project and its [2-ID-D launcher](https://github.com/AdvancedPhotonSource/eaa_driver_scripts_aps_2idd). EAA is read as a source of facts about the beamline, not copied as a design: CORA's Conductor replaces EAA's scan and autofocus orchestration, and EAA registers as an external Agent (see [Model](model.md#how-eaa-fits)). The launcher is a simulation, so it carries no real PV handles, detector identities, or motor bindings, and none are invented. Every value is carried as `confirm` until 2-ID staff verify it; what CORA needs the team to confirm is on [Open questions](questions.md).

## 2-ID the beamline, 2-ID-D the hutch

2-ID is one insertion-device beamline in Sector 2 whose source feeds more than one experiment hutch, the same root-and-hutch shape as 32-ID (root `32-ID`, hutches `32-ID-A/B/C`). The root Asset is `2-ID`; `2-ID-D` is the experiment hutch this scaffold models, the scanning fluorescence microprobe. A sister station (a 2-ID-E-class hutch) and the upstream optics location are deferred and flagged as `TOPO-1`, exactly as the 32-ID scaffold modelled only the 32-ID-C TXM and deferred 32-ID-B. The hutch roster and where the shared optics sit are the single structural unknown.

## What makes 2-ID-D a different shape from the tomography pilots

2-BM, 7-BM, 19-BM, and TomoWise are projection-imaging beamlines: a full-field beam passes through the sample to a camera, and a rotation builds a tomogram. 2-ID-D is the opposite acquisition model, which is what makes it a new modality for CORA rather than a reuse of the 2-BM shape:

- **A focused probe, not a full field.** A Fresnel zone plate focuses the monochromatic beam to a small spot. There is no full-field projection and no imaging camera in the tomography sense.
- **The sample scans, the detector counts.** The sample is rastered through the spot (a 2D fly raster or a 1D step scan), and at each point an energy-dispersive detector records a fluorescence spectrum. The image is a map assembled point by point, not a single exposure.
- **A fluorescence (energy-dispersive) detector.** The signal is a per-point X-ray spectrum from which element maps are fit downstream, a device class and data shape CORA's all-imaging catalog has no precedent for.
- **Autonomous alignment is already in the loop.** The EAA agent drives a zone-plate autofocus and drift-correction loop over EPICS. That orchestration is exactly what CORA's Conductor would take over, with EAA registered as the Agent that proposes (see [Model](model.md#how-eaa-fits)).

What 2-ID-D does **not** change: it runs on the same APS EPICS floor as 2-BM, and it reuses the APS Site envelope rather than creating one.

## Scope: what is and is not modelled

This scaffold earns its abstractions. It models the part of 2-ID that the EAA corpus evidences and that sits within CORA's existing shape, and defers the rest until the beamline forces it.

| Part | In this scaffold | Why |
| --- | --- | --- |
| 2-ID-D sample-scanning endstation | Yes | The raster stack, zone-plate focus, and fluorescence detector are what EAA's `aps_mic` integration evidences |
| Source-side optics (undulator, mono) | Thin | Carried confirm; EAA does not describe them, so they are not detailed (`SRC-1`, `MONO-1`, `TOPO-1`) |
| Sister hutch (2-ID-E class) | No | The corpus names only 2-ID-D; the hutch roster is `TOPO-1`, deferred like 32-ID-B |
| Scanning XRF mapping (Method) | Named, not coined | A new modality; the Method is pending in the catalog and the technique renders unlinked (`METHOD-1`) |
| Scanning fluorescence tomography | No | A Plan setpoint over the XRF Method, not a new Method; needs a rotation axis not evidenced here |
| Micro-XANES, ptychography | No | Named by world-facts but absent from EAA's `aps_mic` code path; modelling them now would be invention |

The deferred parts and the reasons are recorded on [Model](model.md#deliberately-not-here-yet).

## The beamline

The systems CORA models today, along the beam:

- [Source](beamline.md): the source-stage walk, rendered from the descriptor: the Sector 2 undulator and the monochromator that selects the scanning energy (both upstream, shared), and the Fresnel zone plate in 2-ID-D that forms the focused probe (with the `zp_z` focus axis EAA's autofocus drives).
- [Sample](equipment/sample.md): the sample-scanning stack in the 2-ID-D hutch, the raster axes the sample moves through the focused spot on.
- [Detector](equipment/detector.md): the energy-dispersive fluorescence detector in 2-ID-D that records a spectrum per scan point.

Cutting across them:

- [Controls](equipment/controls.md): the EPICS control stack and the Bluesky scan path; device handles are not yet on file.

The cross-cutting reference view is the [Inventory](inventory.md): the planned Asset tree by `parent_id` with Families and the values still pending confirmation. The [Source](beamline.md) page is generated from the [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-id/beamline.yaml) descriptor.

## Techniques

[Techniques](techniques.md): what the modelled part of 2-ID is designed to do, as intent. The scanning-XRF Method is a new modality, carried as a pending [Catalog](../../catalog/methods.md) Method an APS [Practice](../aps/index.md#the-techniques-adapted-here) would adapt once it enters the pilot scope.

## Governance

[Governance](governance.md): who will act at 2-ID and the trust shape that gates their commands. People and agents are facility principals at the [APS Site](../aps/index.md#who-acts-here).

## Model

[Model](model.md): the developer's by-kind index into where each CORA aggregate's 2-ID content lives, how EAA fits the seam, and the record of what is deliberately deferred.

## Not yet documented

2-ID is pre-build in CORA, so the operations runbook (procedures, recipes, cautions, enclosure permits) and the live experiment view are deliberately not written yet: a runbook for a beamline CORA does not yet drive would be invention, not record. They join as the deployment firms up. The [2-BM deployment](../2-bm/index.md) shows the shape they will take.
