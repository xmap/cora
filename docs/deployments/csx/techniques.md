# Techniques

*What the modelled part of CSX is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. CSX's scattering legs reuse Methods already in the catalog's pending set, so they render unlinked and are carried pending until a technique enters scope (`TECH-1`).

## Resonant soft X-ray scattering

CSX tunes the soft X-ray energy to an absorption edge and measures the scattered intensity through the TARDIS diffractometer, resolving electronic and magnetic order in reciprocal space.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant soft X-ray scattering | `resonant_scattering` | RSXS on the TARDIS E6C; reuses the 4-ID `resonant_scattering` Method, in a soft X-ray regime (a Plan / settings difference) |
| Soft X-ray diffraction | `diffraction` | coherent soft X-ray diffraction through the TARDIS circles; reuses the 4-ID / 8-ID `diffraction` Method |

Both need the [grating monochromator](beamline.md) (the incident energy), the [TARDIS diffractometer](equipment/sample.md), and the [coherent detectors](equipment/detector.md). The arm and sample circles select the momentum transfer.

## Coherence and holography

CSX's defining quality is beam coherence: the FastCCD records coherent-scattering and holography patterns. This is carried as a beam-quality enabler and as settings on the scattering Methods above, not coined as its own Method; whether coherent soft X-ray scattering becomes a distinct catalog Method is an owner-scope decision (`TECH-1`).

## Not modelled yet

The concrete acquisition recipes (energy maps, reciprocal-space scans, coherent / holography exposures) are not written yet; they join as the deployment approaches the point where CORA drives CSX. See [Open questions](questions.md) for the world-facts to confirm first.
