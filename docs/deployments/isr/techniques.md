# Techniques

*What ISR is designed to do, as intent. A deliberately partial first cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. ISR's mission is hard X-ray resonant scattering and surface / interface diffraction, with in-situ sample environments. The Methods below render unlinked and are **doubly deferred**: the Methods themselves are pending, and the multi-circle diffractometer they run on is absent from the source (`TECH-1`, `DIFF-1`).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant scattering | `resonant_scattering` | resonant elastic scattering near an absorption edge; reuses the Method APS [4-ID](../4-id/techniques.md) (POLAR) and [CSX](../csx/techniques.md) left pending; needs a tunable energy axis and a diffractometer, both absent from source (`TECH-1`, `RESONANT-1`, `DIFF-1`) |
| Surface / interface diffraction | `diffraction` | crystal truncation rods and surface structure; reuses the `diffraction` Method 4-ID / [8-ID](../8-id/techniques.md) left pending; needs the multi-circle diffractometer, absent from source (`TECH-1`, `DIFF-1`) |

Both techniques would need the [incident-beam chain](beamline.md) (the undulator, the DCM for energy, the focusing mirrors, the attenuator), a multi-circle [sample diffractometer](equipment/sample.md), and the [Eiger area detector](equipment/detector.md). The first two of those are partly modelled; the diffractometer is not.

## Reuse, not new vocabulary

ISR coins **no new Method**. Its resonant scattering reuses the `resonant_scattering` Method that APS 4-ID POLAR brought and CSX shares; its surface / CTR diffraction reuses the `diffraction` Method that 4-ID / 8-ID share. So ISR adds, when it lands, further consumers of two pending Methods, strengthening the case for cataloging them, but it does not mint vocabulary. The matching Site Practices (`ISR_resonant_scattering_practice`, `ISR_surface_diffraction_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here).

## Why these are doubly deferred

For every other beamline the technique Methods are deferred because the Capability is not yet in the catalog (the owner-scope decision). At ISR there is a second, harder deferral: the **devices** the techniques run on are not in the public source. Resonant scattering needs a tunable energy axis (a non-functional stub here, `RESONANT-1`) and surface diffraction needs a multi-circle diffractometer (only two axes bound, `DIFF-1`). So these Practices are intent recorded against a partial scaffold, not a capability CORA could drive today. They firm up as the diffractometer and the energy axis enter the source.

## Not modelled yet

The concrete acquisition recipes are not written yet, and cannot be until the diffractometer lands: the reciprocal-space (hkl) scans, the rocking-curve and CTR trajectories, the energy scans across an edge for resonant work, and the in-situ environment programs. The integration and reduction (azimuthal / CTR rod integration) are `ComputePort` work, not beamline Methods. These join as ISR's profile collection grows past its current optics-first state.

See [Open questions](questions.md) for the world-facts to confirm first, especially the diffractometer (`DIFF-1`) and the in-situ environment (`INSITU-1`).
