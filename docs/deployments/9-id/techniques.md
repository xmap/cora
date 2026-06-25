# Techniques

*What the modelled part of 9-ID is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 9-ID's techniques are coherent surface scattering and grazing-incidence scattering, new to CORA's imaging-heritage catalog, so the Methods below render unlinked and are carried pending until one enters scope (`TECH-1`).

## Coherent surface scattering

The CSSI signature: a coherent beam strikes the sample surface at a shallow grazing angle, so the scattered intensity is sensitive to surface structure and, over time, surface dynamics.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Coherent surface scattering | `coherent_surface_scattering` | the grazing-incidence coherent measurement on the area detectors; Method not yet in catalog |
| Surface XPCS | `xpcs` | time-correlation of the surface speckle pattern; shares the 8-ID XPCS Method |

Both need the [grazing-incidence sample stack](equipment/sample.md) (the incidence rotation sets the angle) and the [coherent detectors](equipment/detector.md).

## Grazing-incidence scattering

GISAXS and GIWAXS read the small- and wide-angle scattering from the grazing-incidence geometry.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Grazing-incidence scattering | `grazing_incidence_scattering` | GISAXS on the Pilatus / Eiger and GIWAXS on the pedestal detector (`TECH-1`) |
| Wide-angle scattering | `wide_angle_scattering` | the GIWAXS leg; shares the i22 WAXS Method |

It needs the same sample stack and the [WAXS detector](equipment/detector.md) on its pedestal.

## Not modelled yet

The concrete acquisition recipes (incidence-angle scans, correlation time series, frame rates, exposures) are not written yet; they join as the deployment approaches the point where CORA drives 9-ID. Whether these Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
