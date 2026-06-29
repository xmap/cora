# Techniques

*What the modelled part of FAXTOR is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../alba/index.md#the-techniques-adapted-here) is how a facility adapts it. FAXTOR is a fast-imaging beamline: its tomography techniques reuse Methods CORA's catalog already carries, and its radiography is carried pending until it enters scope (`TECH-1`).

## Fast tomography and radiography

FAXTOR sets the X-ray energy with the multipole wiggler and the double multilayer monochromator (8-50 keV mono) or the filter set (30-70 keV filtered white beam), then rotates the sample on the experiment endstation while the scintillator and fast camera record projections. Continuous-rotation acquisition reaches up to 20 Hz, at 0.5-10 um pixel size, with absorption, propagation-phase, and grating-based contrast.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Tomography | [`tomography`](../../catalog/methods.md) | absorption and propagation-phase micro-CT on the [experiment endstation](equipment/sample.md), the [rotary stage](equipment/sample.md) stepped against the [scintillator + camera](equipment/detector.md); reuses the catalog tomography Method (the 2-BM pilot) |
| Continuous-rotation tomography | [`continuous_rotation_tomography`](../../catalog/methods.md) | fast fly-scan tomography up to 20 Hz, the [rotary stage](equipment/sample.md) in continuous rotation as the trigger master (`TRIG-1`); reuses the catalog continuous-rotation Method |
| Radiography | `radiography` | time-resolved single-projection radiography; reuses the 7-BM `radiography` slug, no portable Method in the catalog yet; pending (`TECH-1`) |

Tomography needs the [incident energy](beamline.md) set by the [monochromator or filters](beamline.md), the [rotary stage and sample positioning](equipment/sample.md), and the [scintillator + fast camera](equipment/detector.md). Radiography needs the same beam and detector without the rotation sweep.

## A new Site on familiar vocabulary

FAXTOR is the fleet's fast-imaging beamline at ALBA, and it ties into the tomography lineage CORA already models: the same imaging device anatomy as the 2-BM pilot and the MAX IV TomoWISE design (a wiggler or undulator source, a multilayer monochromator, a rotary-stage endstation, and an indirect scintillator + camera detector). It reuses the `tomography` and `continuous_rotation_tomography` Methods directly; only radiography is carried pending, and none forces a new device family.

## Not modelled yet

The concrete acquisition recipes (the fly-scan tomography sequences and their counting times, the flat / dark sequencing, the phase-contrast and grating-based setups) are not written yet; they join as the deployment approaches the point where CORA drives FAXTOR. Whether radiography enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
