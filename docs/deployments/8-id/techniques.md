# Techniques

*What the modelled part of 8-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 8-ID's techniques are coherent-scattering and diffraction, new to CORA's imaging-heritage catalog, so the Methods below render unlinked and are carried pending until one enters scope (`TECH-1`).

## X-ray photon correlation spectroscopy

XPCS measures the time correlations of a coherent speckle pattern to probe sample dynamics, so it records long, fast time series on an area detector under a precisely gated exposure.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| XPCS | `xpcs` | coherent-scattering intensity time series on the Eiger / Lambda / Rigaku detectors, gated by the softGlue timing; Method not yet in catalog |
| Small-angle scattering | `small_angle_scattering` | static SAXS on the same detectors; a Plan setting over the same chain |

Both need the [XPCS sample stage](equipment/sample.md), the [coherent detectors](equipment/detector.md), and the flight path. The fast shutter and softGlue timing (`XPCS-1`, `XPCS-3`) gate the exposure.

## Six-circle diffraction

The 8-ID-E Huber diffractometer orients a single crystal through six circles and scans reciprocal space, sharing the diffraction Method with 4-ID.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Six-circle diffraction | `diffraction` | reciprocal-space scans on the six-circle Huber; shares the 4-ID `diffraction` Method (`TECH-1`) |

It needs the [diffractometer](equipment/sample.md). The reciprocal-space coordination is `DIFF-2`; the reusable `Assembly(Diffractometer)` is on [Model](model.md#deliberately-not-here-yet).

## Not modelled yet

The concrete acquisition recipes (correlation time series, frame rates, exposures) are not written yet; they join as the deployment approaches the point where CORA drives 8-ID. Whether XPCS and scattering Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
