# Detector

*The detection side. PVs reverse-engineered from dodal `src/dodal/beamlines/i13_1.py`, carried `confirm`. This is the coherence-branch endstation only; the shared I13 source and optics are upstream and deferred (SRC-1, OPT-1, see [the beam path](../beamline.md)).*

Ptychography reconstructs a real-space image from the far-field diffraction a coherent beam throws as it is raster-scanned across the sample. So the detection side has two cameras with very different jobs: the science detector that records the far-field coherent-diffraction pattern, and the optical side camera that lets you see the sample to align it.

| Asset | Family | PV | Role |
| --- | --- | --- | --- |
| `Detector` | [Camera](../../../catalog/families.md) | `BL13J-EA-DET-04:` | Merlin / Medipix3 photon-counting area detector; records the far-field coherent-diffraction pattern (DET-1) |
| `SideCamera` | [Camera](../../../catalog/families.md) | `BL13J-OP-FLOAT-03:` | Aravis / GenICam optical viewing camera; sample alignment (DET-1) |

## The science detector: the Merlin

The `Detector` is the Merlin photon-counting area detector built on a Medipix3 readout (`BL13J-EA-DET-04:`). It sits in the far field and records the coherent-diffraction pattern, the raw signal ptychography reconstructs from. It reuses the catalog `Camera` family: an area detector that returns frames is what `Camera` is, and a photon-counting far-field detector is a thin instance of it. CORA carries the PV `confirm` (DET-1) until it is bound on a live run.

## The side camera: sample alignment

The `SideCamera` is an Aravis / GenICam optical viewing camera (`BL13J-OP-FLOAT-03:`), the in-hutch eye used to align the sample before a scan. It also reuses `Camera` (DET-1). Two cameras, one family, different framing: one watches the diffraction, one watches the sample.

## Why no new family for coherent imaging

The scout anticipated a "coherent imaging device family." That is the wrong axis, and CORA does not coin it. What is new at I13-1 is not a device class, it is an *acquisition shape*: a coherent beam raster-scanned across the sample, plus a reconstruction. The hardware that carries that shape is ordinary, a raster `LinearStage` (the PI piezo sample stage, see [Sample](sample.md), SAMPLE-1) and two `Camera` instances. The novelty lives in the **Method**, ptychography / CDI, the fleet's first coherent diffractive imaging, carried pending (TECH-1). And the step that turns the diffraction stack into an image is `ComputePort` work, not a beamline device. Zero new families graduate from this cut; the catalog is unchanged.

## What is deferred

The shared I13 source and optics (undulator, monochromator, mirrors, slits) are upstream of the coherence branch and absent from the dodal module, so they are deferred rather than invented (SRC-1, OPT-1). The PSS search-and-secure permit signals and the photon / front-end shutters are likewise absent from the module and carried pending (PSS-1). The detection side modelled here is the endstation, not the beam that feeds it; see [the beam path](../beamline.md) for the generated source-walk.
