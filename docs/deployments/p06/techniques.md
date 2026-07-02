# Techniques

*What the modelled part of P06 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P06 runs hard X-ray scanning-probe microscopy and nano-tomography, reusing Methods the fleet already carries pending, so the Methods below render unlinked until a technique enters scope (`TECH-1`).

## Scanning fluorescence / diffraction microscopy

P06 focuses the beam (the multilayer or crystal monochromator feeding the KB optics) to a micro or nano spot, then rasters the sample across it with the [Aerotech scan stage](sample.md) while the [Maia XRF array](detector.md) reads the fluorescence at each point (and the area detectors read scattering / diffraction).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Scanning X-ray fluorescence / diffraction microscopy | `scanning_fluorescence_microscopy` | the Aerotech raster fly-scan over the micro / nano focus reading the Maia array; reuses the slug 2-ID / XFM / LIX / ESRF ID16B share, a further consumer (`TECH-1`) |

## Nano-tomography

The NC1 nano-probe carries a Pegasus sample rotation (`samr`); rotating the sample in the nano-focused beam while reading the area detector gives nano-tomography.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Hard X-ray nano-tomography | `tomography` | the NC1 sample rotation + area detector; reuses the catalog `tomography` Method (the 2-BM / FXI / ID19 lineage), a further consumer (`TECH-1`) |

## A dense instrument on familiar vocabulary

P06 is the fleet's fullest scanning-probe beamline, but it coins no new vocabulary. Its techniques reuse the `scanning_fluorescence_microscopy` and `tomography` slugs already carried across the fleet, and its instrument anatomy reuses existing Families: the monochromators bind `Monochromator`, the hexapods `Hexapod`, the scan stages `LinearStage`, the Maia array `EnergyDispersiveSpectrometer`, the area detectors `Camera`. The novelty is in the density and diversity of the device tree (six controller families, two endstations, the Maia array), not in any new Family or Method.

## Not modelled yet

The concrete acquisition recipes (the raster fly-scan trajectories and dwell times, the Maia mapping readout, the nano-tomography rotation sequences) are not written yet; they join as the deployment approaches the point where CORA drives P06. Whether the scanning / nano-tomography Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
