# Sample

*The sample-scanning side. PVs verified against dodal `src/dodal/beamlines/i13_1.py`, carried `confirm`.*

I13-1 raster-scans a coherent beam across the sample and reconstructs a real-space image from the far-field diffraction it records (ptychography / CDI). On this side that means one thing: a stage that drives the raster. The dodal coherence-branch module exposes the sample stage and the two cameras, and nothing of the shared I13 source and optics upstream (SRC-1, OPT-1), so this page is the sample side only.

| Asset | Family | PV | What it does |
| --- | --- | --- | --- |
| `SampleStage` | LinearStage | `BL13J-MO-PI-02:` | rasters the sample across the coherent beam (the ptychography scan) |

## The sample stage

The `SampleStage` is a PI piezo sample-scanning stage. Its operative motion is the ptychography raster: the scan trajectory that steps the sample through the coherent beam while the [detector](detector.md) records a far-field diffraction pattern at each point. CORA binds it to the catalog [`LinearStage`](../../../catalog/families.md) family; it carries the PVs `confirm` and tracks the stage's live status and full axis set as SAMPLE-1.

The same stage also carries a fixed-angle lab-frame variant (`BL13J-MO-PI-02:FIXANG:`). This is **a setting on the one stage, not a second Asset**: the same `SAMPLE-1` hardware, addressed in a lab-frame fixed-angle configuration. It is noted here so the reader knows the two PV faces are one stage (SAMPLE-1).

## Why no new family here

The scout anticipated a "coherent imaging device family" for I13-1. That is the wrong axis. The novelty at a ptychography / CDI beamline is not a kind of device; it is an **acquisition shape plus a reconstruction**: raster the coherent beam, capture the far-field diffraction, and invert the diffraction stack into a real-space image. That belongs to a [Method](../../../catalog/methods.md), not to a device class.

So the devices stay plain. The stage is a `LinearStage`, the [side camera and the Merlin detector](detector.md) are `Camera`s, and no family graduates. Ptychography / CDI is carried as a new pending Method (the fleet's first coherent diffractive imaging), TECH-1; the image reconstruction from the diffraction stack is `ComputePort` work, not a beamline device. The full deployment-level reasoning is on the [model](../model.md) page.

The honest caveat is the partial scope: the shared I13 source and optics (the undulator, monochromator, and mirrors that condition the coherent beam this stage scans through) are absent from the dodal module and deferred, not invented (SRC-1, OPT-1). An in-situ sample environment, if I13-1 runs one, is likewise not in the module and left to a later cut. The [beamline](../beamline.md) source-walk and the [inventory](../inventory.md) carry the flat reference.
