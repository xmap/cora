# I13-1

*Hard X-ray ptychography and coherent diffraction imaging (CDI) on the coherence branch of Diamond I13: a coherent lensless-imaging technique that raster-scans a coherent beam across the sample and reconstructs a real-space image from the far-field diffraction it records. This page describes how CORA would model and run I13-1; the model is reverse-engineered from the dodal controls library, not yet confirmed by Diamond staff, and is a deliberately partial first cut.*

| Property | Value |
| --- | --- |
| Asset | `I13-1` (root Asset, `tier = Unit`, `parent_id = None`) |
| Facility | [Diamond Light Source](../diamond/index.md) (bound via `facility_code = "diamond"`, `FacilityKind = Site`) |
| Sector | i13-1, the coherence branch of I13 (Hard X-ray Imaging and Coherence), Sector 13 (PV root `BL13J`, dodal module `i13_1`) |
| Status | First cut, **deliberately partial**: only the coherence-branch endstation; shared source and optics deferred (SRC-1, OPT-1) |
| Source | shared I13 undulator, upstream and not in the dodal module (deferred, SRC-1) |
| Control stack | Diamond EPICS / ophyd-async, read from dodal and carried `confirm` (CTRL-1) |

!!! warning "How CORA would land on I13-1, and why this scaffold is partial"
    These pages describe how CORA would model, govern, and conduct I13-1. They are not a survey of the beamline's current software. The hardware facts (devices, EPICS PVs) are read from the public [dodal](https://github.com/DiamondLightSource/dodal) controls library (`src/dodal/beamlines/i13_1.py`) and verified against it; every read value is carried `confirm` until staff verify it ([Open questions](questions.md)). **This is a deliberately partial first cut:** the dodal `i13_1` module exposes only the coherence-branch endstation (the sample stage, the side camera, the Merlin detector). The shared I13 source and optics (undulator, monochromator, mirrors, slits) are upstream and not in the module, so they are deferred, not invented (SRC-1, OPT-1). This is the same partial-first-cut posture as [I20-1](../i20-1/index.md). This is a design-phase scaffold: the descriptor and these docs, with scenarios deferred.

## What makes I13-1 different

I13-1 is CORA's first coherent lensless-imaging beamline. The fleet has tomography, an XRF microprobe, and a hard X-ray nanoprobe, but no ptychography or CDI. Ptychography raster-scans a coherent illumination across overlapping points on the sample and records a far-field coherent-diffraction pattern at each point; the real-space image is reconstructed downstream from the diffraction stack.

The novelty is **a Method, not a device family**: it is an acquisition shape (the coherent raster) plus a reconstruction, not a new class of hardware. The devices the technique needs are a sample-scanning stage and area detectors, both already in the catalog. So I13-1 coins no new Family and changes nothing in the catalog. The scout that surfaced I13-1 anticipated a new "coherent imaging" device family; that is the wrong axis (TECH-1).

## Scope: what is and is not modelled

| In this cut (the endstation) | Deferred (not invented) |
| --- | --- |
| `SampleStage`, the PI piezo sample-scanning stage, the ptychography raster (SAMPLE-1) | the shared I13 undulator source, upstream (SRC-1) |
| `SideCamera`, the Aravis / GenICam side viewing camera, for alignment (DET-1) | the shared I13 optics: monochromator, mirrors, slits (OPT-1) |
| `Detector`, the Merlin (Medipix3) photon-counting science detector (DET-1) | the PSS search-and-secure permit signals and the photon / front-end shutters (PSS-1) |
| `StorageRing`, machine state, observe-only (MACHINE-1) | the I13-2 imaging branch (out of this cut) |

The coherence-branch experiment hutch `i13-1` (`BL13J`) is the modelled Enclosure (ENC-1).

## Key modelling decisions

- **Zero new families.** Coherent imaging is an acquisition shape plus reconstruction, a Method, not a device class. Nothing graduates and the catalog is unchanged (TECH-1).
- **Coherent imaging is a Method.** Ptychography / CDI enters as a new pending Method, the fleet's first coherent diffractive imaging, carried pending; no `cora.capability.ptychography` is coined yet (TECH-1).
- **The raster binds `LinearStage`.** The PI piezo sample-scanning stage is the operative motion of the technique; the fixed-angle lab-frame variant (`BL13J-MO-PI-02:FIXANG:`) is a setting on the same stage, not a separate device (SAMPLE-1).
- **The detectors bind `Camera`.** The Merlin records the far-field coherent-diffraction pattern (the science detector); the side camera is for sample alignment (DET-1). The image reconstruction from the diffraction stack is `ComputePort` work, not a beamline device.
- **Deliberately partial.** The shared I13 source and optics are absent from dodal and deferred, not invented (SRC-1, OPT-1).

## The beamline

Along the beam, in order:

- [Source](beamline.md): the shared I13 undulator source (upstream, absent from the dodal module, SRC-1) and the shared optics (OPT-1).
- [Sample](equipment/sample.md): the PI piezo sample-scanning stage, the ptychography raster (SAMPLE-1).
- [Detector](equipment/detector.md): the Merlin (Medipix3) coherent-diffraction science detector and the side viewing camera (DET-1).

Cutting across:

- [Controls](equipment/controls.md): the EPICS PV handles read from dodal and carried `confirm` (CTRL-1); the PSS permit signals and shutters are absent from the module and pending (PSS-1).

The cross-cutting reference view is the [Inventory](inventory.md), authored from the same descriptor as the generated [Source](beamline.md) walk.

## Techniques

[Techniques](techniques.md): ptychography / CDI, the fleet's first coherent lensless imaging, recorded as a pending Diamond Practice (`I13-1_ptychography_practice`, TECH-1).

## Governance

[Governance](governance.md): who may act at I13-1 and the trust shape CORA applies. People and autonomous agents are facility principals at the [Diamond Site](../diamond/index.md#who-acts-here), gated by a trust shape (Zone + Conduit + Policy). Clearances are issued at the Diamond Site; the operator pool and review are carried pending (GOV-1).

## Model

[Model](model.md): the developer's by-kind index into where each I13-1 aggregate's content lives, why coherent imaging coins no new family, and what the partial roster defers.

## Not yet documented

- **The shared I13 source and optics.** The undulator, monochromator, mirrors, and slits are upstream and absent from the dodal module, so they are deferred, not invented (SRC-1, OPT-1).
- **Operations and experiment views.** A runbook and a live experiment view for a beamline CORA does not yet drive would be invention; they land when the shared source and optics are PV-bound and the team confirms.
