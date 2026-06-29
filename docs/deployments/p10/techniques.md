# Techniques

*What the modelled part of P10 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P10's primary technique, XPCS, is a graduated catalog Method (earned at the APS 8-ID), so its practice binds it directly; the coherent-imaging techniques reuse pending slugs (`TECH-1`).

## X-ray photon correlation spectroscopy

P10 illuminates the sample with a coherent beam and reads the speckle pattern on a high-frame-rate area detector (Lambda / Eiger); the intensity autocorrelation over time measures the sample dynamics.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray photon correlation spectroscopy (XPCS) | [`xpcs`](../../catalog/methods.md) | the coherent beam on the sample read by the high-frame-rate Lambda / Eiger, the correlation computed downstream; binds the graduated `xpcs` Method (earned at APS 8-ID), the second consumer |

## Coherent diffraction imaging

P10's E1 endstation focuses the coherent beam (the CRL) and records coherent diffraction patterns (the Quadro / Eiger) for ptychographic / coherent-diffraction reconstruction.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Coherent diffraction imaging / ptychography | `ptychography` | the focused coherent beam scanned across the sample, the diffraction recorded for phase retrieval; reuses the pending `ptychography` slug, a further consumer (`TECH-1`) |

## A graduated Method meets a new facility

P10 is the fleet's second XPCS beamline. Unlike the other PETRA III beamlines (whose techniques are not yet earned and carry pending practices), P10's XPCS practice binds the graduated `xpcs` Method directly, reusing the abstraction the APS 8-ID deployment forced into the catalog. This is the reuse-earns-the-abstraction principle working as intended: a technique graduated at one facility carries cleanly to another on a different control plane. The coherent-imaging side reuses the pending `ptychography` slug; the instrument anatomy reuses existing Families (the CRL `Transfocator`, the hexapod `Hexapod`, the detector suite `Camera`).

## Not modelled yet

The concrete acquisition recipes (the XPCS multi-tau / correlation sequences, the ptychographic scan trajectories, the coherent-diffraction exposures) are not written yet; they join as the deployment approaches the point where CORA drives P10. Whether `ptychography` enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
