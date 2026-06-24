# Techniques

*What the modelled part of 2-ID is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. This scaffold models 2-ID's 2-ID-D microprobe hutch, so the technique below is the scanning fluorescence one, carried as design intent. The function view survives the eventual hardware choices, which is why it can be written before the optics are confirmed.

## Scanning fluorescence microscopy

The microprobe focuses the monochromatic beam through a Fresnel zone plate to a small spot and rasters the sample through it, recording an X-ray fluorescence spectrum at each point with an energy-dispersive detector. Element maps are fit from the per-point spectra downstream (the EAA `XRF-Maps` lineage: scan data to fitted maps).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Scanning XRF mapping | `scanning_fluorescence_microscopy` (pending) | 2D fly raster or 1D step scan of the sample through the focused spot; a fluorescence spectrum per point |

This is a **new modality** for CORA. Every other deployment images by full-field projection and a rotation; this one builds an image point by point from a focused probe. There is no catalog Method for point-raster scanning fluorescence, so `scanning_fluorescence_microscopy` is named here but **not coined**: it renders unlinked, and the [APS Practice](../aps/index.md#the-techniques-adapted-here) that adapts it is carried pending (`METHOD-1`). The Method is earned into the catalog when 2-ID enters the pilot scope and a naming review accepts it, not in a design-phase scaffold. The coining decision is recorded on [Model](model.md#deliberately-not-here-yet).

## Energy

2-ID-D runs monochromatic, the energy set by the upstream monochromator (assumed double-crystal, range unconfirmed, `MONO-1`). Scanning XANES (stepping the energy across an absorption edge per pixel) is a world-fact capability of the beamline but is absent from EAA's `aps_mic` code path, so it is not modelled here (see [Not modelled yet](#not-modelled-yet)).

## Not modelled yet

These are techniques the beamline is known to do but that this scaffold defers, because EAA does not evidence them or because they need hardware not yet modelled:

- **Scanning fluorescence tomography.** A rotation over a sequence of XRF maps. This is a Plan setpoint over the scanning-XRF Method, not a separate Method (mirroring the 2-BM decision that laminography is a tomography Plan at a tilt setpoint), and it needs a rotation axis the endstation is not yet modelled with (`ENV-1`). It joins when the rotation axis is confirmed.
- **Micro-XANES and ptychography.** Named by world-facts about the beamline but absent from EAA's `aps_mic` code path. Ptychography in particular needs a coherent-diffraction (transmission) detector this scaffold does not model. Modelling either now would be invention.

The concrete acquisition recipes (scan ranges, dwell times, target elements, energies) are not written yet; they join as the deployment approaches the point where CORA drives 2-ID. See [Open questions](questions.md) for what must be confirmed first.
