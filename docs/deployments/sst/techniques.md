# Techniques

*What the modelled part of SST is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md) is how a facility adapts it. SST's two branches run two technique families, one reusing an existing pending Method and one new, both carried pending until a technique enters scope (`TECH-1`).

## Resonant soft X-ray scattering (SST-1)

The soft branch tunes the plane-grating monochromator to an absorption edge and records the scattered soft X-rays on the Greateyes area detector, resolving chemical and orientational order.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Resonant soft X-ray scattering (RSoXS) | `resonant_scattering` | reuses the 4-ID `resonant_scattering` Method, in a soft X-ray regime (a Plan / settings difference) on the [RSoXS endstation](equipment/sample.md) |

It needs the [soft PGM](beamline.md), the [RSoXS manipulator](equipment/sample.md), and the [WAXS detector and I0 monitors](equipment/detector.md).

## Photoelectron spectroscopy (SST-2)

The tender branch tunes the Si double-crystal monochromator and measures the kinetic-energy spectrum of emitted photoelectrons on the Scienta SES analyzer, probing chemical state and electronic structure.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray photoelectron spectroscopy (HAXPES) | `xray_photoelectron_spectroscopy` | tender photoemission on the [Scienta SES analyzer](equipment/detector.md); a new pending Method, distinct from ESM's angle-resolved variant |

It needs the [tender DCM](beamline.md), the [HAXPES manipulator and slit](equipment/sample.md), and the [SES analyzer](equipment/detector.md).

## Not modelled yet

The concrete acquisition recipes (energy scans, scattering exposures, analyzer sweeps) are not written yet; they join as the deployment approaches the point where CORA drives SST. The UCAL NEXAFS (TES microcalorimeter) and VPPEM techniques are deferred with their endstations (see [Model](model.md#deliberately-not-here-yet)). Whether RSoXS and HAXPES Methods enter CORA's catalog is an owner-scope decision; see [Open questions](questions.md) for the world-facts to confirm first.
