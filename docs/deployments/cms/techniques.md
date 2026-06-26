# Techniques

*What the modelled part of CMS is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. CMS measures soft-matter and thin-film structure four ways: small-, wide-, and medium-angle scattering (SAXS / WAXS / MAXS), grazing-incidence scattering (GISAXS / GIWAXS), and specular X-ray reflectivity (XR). Three of those four are scattering the fleet already speaks; the Methods below render unlinked and are carried pending until the owner-scope decision (`TECH-1`) brings any of them into the catalog.

CMS is the NSLS-II twin of [SMI](../smi/techniques.md) (12-ID), and most of what it does reinforces vocabulary CORA already holds. Read this page for the one technique that is genuinely distinct: specular reflectivity.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Small-angle scattering (SAXS) | `small_angle_scattering` | low-Q on the [SAXS Pilatus 2M](equipment/detector.md); shares the science axis with [i22](../i22/techniques.md) and [SMI](../smi/techniques.md); Method not yet in catalog (`TECH-1`) |
| Wide- and medium-angle scattering (WAXS / MAXS) | `wide_angle_scattering` | wider-Q on the [Pilatus 800K heads](equipment/detector.md), one powered per configuration; shares the axis with [i22](../i22/techniques.md); Method not yet in catalog (`TECH-1`) |
| Grazing-incidence scattering (GISAXS / GIWAXS) | `grazing_incidence_scattering` | the same scattering with the sample at a grazing angle on `sth`; shares the axis with APS 9-ID and its NSLS-II twin [SMI](../smi/techniques.md); Method not yet in catalog (`TECH-1`) |
| Specular X-ray reflectivity (XR) | `reflectivity` | step `sth`, slide a detector region-of-interest in lockstep across the fixed [Pilatus 2M](equipment/detector.md), integrate the specular intensity; the second consumer of the reflectivity Method after [i10](../i10/techniques.md) (`XR-1`, `TECH-1`) |

All four techniques need the [incident-beam chain](beamline.md) (the DMM for energy, the mirrors, slits, and absorber foils), the [sample stack](equipment/sample.md) (the [Goniometer](equipment/sample.md), surface-leveling tilts, temperature stage), and the [endstation detectors](equipment/detector.md) (the Pilatus heads, beamstop, flux monitors). Scattering reads an area frame at one orientation; reflectivity reads the same area detector while the orientation is stepped.

## The scattering is reinforcement, not novelty

SAXS, WAXS, MAXS, and grazing-incidence scattering overlap the fleet heavily. CMS is the direct NSLS-II twin of [SMI](../smi/techniques.md), and the two share their science axis with Diamond [i22](../i22/techniques.md) and APS 9-ID / 12-ID-E: the same Camera / Goniometer / Slit / BeamStop / FluxMonitor vocabulary, zero new families, the same pending scattering Method slugs. MAXS is a detector-position variant of wide-angle scattering on a second Pilatus 800K head, not a technique of its own. GISAXS / GIWAXS is the same scattering with the sample tipped to a grazing angle on `sth`, a sample-orientation variant rather than a new Capability.

So the scattering side of CMS earns no new abstraction. It reinforces, at a second NSLS-II beamline, the case that the small- and wide-angle scattering Capabilities belong in the catalog (`TECH-1`), the same earn-the-abstraction discipline SMI and i22 already follow. The device Roles exist (the Pilatus heads present Detector, the flux monitors present Sensor), so what stays pending is the science Capability, not a device shape. Because those Capabilities are not yet in the catalog, the matching Site Practices (`CMS_small_angle_scattering_practice`, `CMS_wide_angle_scattering_practice`, `CMS_grazing_incidence_scattering_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

## Specular reflectivity, the distinct contribution

Specular X-ray reflectivity is the one technique CMS brings that the scattering vocabulary does not cover, and CORA models it as a **Method over existing devices**, coining no hardware.

There is no physical two-theta detector arm at CMS, and no point detector. The area detector stays fixed. The measurement steps the sample incidence angle `sth` (the same grazing-incidence angle the GISAXS Method uses) and, in lockstep, slides a software region-of-interest across the face of the fixed [Pilatus 2M](equipment/detector.md) to where the specularly reflected beam lands at each angle. The intensity inside that tracked region is integrated; the angle the region sits at is a **synthetic** two-theta computed from the geometry, not a value read off a moving arm. The result is the reflectivity curve: specular intensity versus angle, with the incident flux read on the [endstation flux monitor](equipment/detector.md) to normalize.

| Reuses | Role in XR |
| --- | --- |
| [Goniometer](equipment/sample.md) (`sth`) | steps the specular incidence angle |
| [Pilatus 2M Camera](equipment/detector.md) | read over a tracked region-of-interest; the synthetic two-theta is where that region sits |
| [endstation FluxMonitor](equipment/detector.md) | incident flux, for normalization |

That is the whole device list. XR coins no two-theta arm, no point detector, no new family. The reflectivity Method is the same one [i10](../i10/techniques.md) brought to CORA at its soft X-ray sibling, where the geometry is realized differently; CMS is the **second consumer** of the Method (`XR-1`), realizing it in the hard X-ray regime with no new hardware. As with the scattering Capabilities, the Method is not yet in the catalog and `CMS_reflectivity_practice` is carried pending (`TECH-1`, `XR-1`).

## Not modelled yet

The concrete acquisition recipes are not written yet. For scattering that is the per-frame exposures, detector distances, beamstop placement, and the azimuthal integration that turns 2D frames into I(Q) curves (the integration and reduction are `ComputePort` work, not beamline Methods). For reflectivity it is the `sth` step list, the region-of-interest tracking model that maps each angle to its place on the fixed Pilatus, and the synthetic two-theta calibration. These join as the deployment approaches the point where CORA drives CMS.

Whether any of these four techniques enters CORA's catalog is an owner-scope decision on [Model](model.md): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. The scattering Capabilities are shared pending slugs the fleet already debates; what CMS adds is a second consumer of the pending `reflectivity` Method (i10 plus CMS), which strengthens the case for cataloging it but leaves that an owner decision, not an automatic one (`XR-1`, `TECH-1`). See [Open questions](questions.md) for the world-facts to confirm first.
