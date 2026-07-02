# Techniques

*What the modelled part of MOGNO is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../sirius/index.md#the-techniques-adapted-here) is how a facility adapts it. MOGNO runs cone-beam X-ray tomography, which is already in CORA's catalog, so the Method below renders linked and the practice is carried pending until the technique enters scope (`TECH-1`).

## Cone-beam micro and nanotomography

MOGNO illuminates the sample with a quasi-monochromatic divergent (cone) beam and records projections as the sample rotates. Because the geometry is cone-beam, moving the sample along the cone between the secondary source and the detector changes the magnification, so a single instrument spans nanotomography (at the elliptical-mirror nanofocus) and microtomography (large field of view) by sample position. Phase contrast comes from propagation over the sample-to-detector distance, and time-resolved (4D) tomography from fast continuous rotation.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Cone-beam X-ray tomography | `tomography` | projections over a rotation on the [nanotomography](sample.md) and [microtomography](sample.md) stations, hardware-triggered by the [TATU timing unit](controls.md); reuses the graduated `tomography` Method the APS 2-BM pilot and NSLS-II FXI share; practice pending (`TECH-1`) |

Tomography at MOGNO needs the [rotation axis](sample.md) as the master clock, the [TATU trigger](controls.md) to hardware-sync projection acquisition, the [detector chain](detector.md) to record the projections plus flat and dark fields, and the [cone-beam magnification axis](detector.md) to set the resolution-and-field-of-view working point.

## A familiar technique on a third facility

MOGNO is the tomography spine reaching a third facility after the APS 2-BM bending-magnet micro-CT pilot and the NSLS-II FXI transmission microscope. It coins no new Method: the same `tomography` Method covers micro and nano variants, exactly as 2-BM uses it for both. What MOGNO reinforces is not the technique but the surrounding model, the cone-beam magnification as a `PseudoAxis`, the FPGA trigger as a `TimingController`, and the seam against a custom (non-Bluesky) orchestration layer.

The streaming and continuous-rotation tomography variants the catalog already carries (`streaming_tomography`, `continuous_rotation_tomography`) are plausible for MOGNO's 4D time-resolved work, but are not asserted here without a source; they would be added as practices once staff confirm the acquisition modes.

## Not modelled yet

The concrete acquisition recipes (the rotation ranges and speeds, the projection counts, the flat and dark field cadence, the per-energy and per-station alignment routines, and the reconstruction parameters) are not written yet; they join as the deployment approaches the point where CORA drives MOGNO. The reconstruction step (`ssc-raft` on the HPC cluster) is named on [Model](model.md#the-compute-axis-reconstruction-named-not-built) as the compute axis, not modelled here. See [Open questions](questions.md) for the world-facts to confirm first.
