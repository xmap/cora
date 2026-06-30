# Techniques

*What the modelled part of 8.3.2 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../als/index.md#the-techniques-adapted-here) is how a facility adapts it. 8.3.2 is a hard X-ray micro-tomography beamline: its techniques reuse Methods CORA's catalog already carries.

## Hard X-ray micro-tomography

8.3.2 sets the X-ray energy with the monochromator (6,000-43,000 eV from the Superbend source), then rotates the sample on the tomographic rotary stage while the scintillator, objective, and camera record projections. It images non-destructively in 3D at ~1 micron resolution, with absorption and propagation-phase contrast (the detector stack's `camera_distance` sets the propagation distance).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Tomography | [`tomography`](../../catalog/methods.md) | absorption and propagation-phase micro-CT, the [rotary stage](equipment/sample.md) stepped against the [scintillator + camera](equipment/detector.md); reuses the catalog tomography Method (the 2-BM pilot) |
| Continuous-rotation tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | fast fly-scan tomography, the [rotary stage](equipment/sample.md) in continuous rotation as the trigger master (`TRIG-1`); reuses the catalog continuous-rotation Method |

Tomography needs the [incident energy](beamline.md) set by the [monochromator](beamline.md), the [rotary stage and sample positioning](equipment/sample.md), and the [scintillator + objective + camera](equipment/detector.md), with the [detector stack](equipment/detector.md) setting the sample-to-detector propagation distance.

## A new Site on familiar vocabulary

8.3.2 is the ALS's hard X-ray micro-CT beamline, and it ties into the tomography lineage CORA already models: the same imaging device anatomy as the 2-BM pilot, the NSLS-II FXI design, and the ALBA FAXTOR design (a bending-magnet or insertion-device source, an energy-setting optic, a rotary-stage endstation, and an indirect scintillator + camera detector). It reuses the `tomography` and `continuous_rotation_tomography` Methods directly; none forces a new device family.

## Not modelled yet

The concrete acquisition recipes (the fly-scan tomography sequences and their counting times, the flat / dark sequencing, the propagation-phase setups) are not written yet; they join as the deployment approaches the point where CORA drives 8.3.2. See [Open questions](questions.md) for the world-facts to confirm first, in particular which sample-stack axis is the tomographic rotation (`ROT-1`) and the triggering scheme (`TRIG-1`).
