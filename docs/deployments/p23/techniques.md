# Techniques

*What the modelled part of P23 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P23's diffraction technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## In-situ X-ray diffraction

P23 measures diffraction (and imaging) of samples under in-situ / operando conditions, electrochemistry, thin-film growth, and controlled sample environments, on the [experiment diffractometer](equipment/sample.md).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| In-situ / operando X-ray diffraction | `diffraction` | diffraction of samples under in-situ conditions; reuses the `diffraction` slug P07 / P08 / P21 share, a further consumer (`TECH-1`) |

## A thin in-situ diffraction beamline

P23 is a thin in-situ diffraction beamline. Its technique reuses the `diffraction` slug already carried across the fleet, so it forces no new Method. The instrument anatomy reuses existing Families (`LinearStage`); the sparse registry slice means the model is deliberately thin, with the optics / diffractometer grouped and the detectors carried pending. The in-situ sample environments (the operando cells), if present, would be sample-environment Assets bound when the registry exposes them.

## Not modelled yet

The concrete acquisition recipes (the diffraction scans, the in-situ / operando time series, the environment-coupled measurements) are not written yet; they join as the deployment approaches the point where CORA drives P23. Whether the diffraction Method enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
