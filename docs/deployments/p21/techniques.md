# Techniques

*What the modelled part of P21 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P21's diffraction techniques earn no catalog Method today, so the Methods below render unlinked and are carried pending until a technique enters scope (`TECH-1`).

## High-energy diffraction

P21's P21.2 / EH3 branches use a high-energy monochromatic beam for bulk / engineering diffraction, residual stress, and texture studies on the [sample stages](sample.md), reading area detectors.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| High-energy diffraction | `diffraction` | bulk / engineering diffraction on the high-energy branches; reuses the `diffraction` slug P07 / P08 share, a further consumer (`TECH-1`) |

## Total scattering / PDF

P21's P21.1 branch collects total scattering to high momentum transfer for pair-distribution-function analysis.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Total scattering / pair-distribution-function | `total_scattering` | high-Q total scattering on the P21.1 branch; reuses the `total_scattering` slug i15-1 / XPD / P02 share, a further consumer (`TECH-1`) |

## A thin high-energy materials beamline

P21 is a Swedish-collaboration high-energy materials beamline. Its techniques reuse the `diffraction` and `total_scattering` slugs already carried across the fleet, so none forces a new Method. The instrument anatomy reuses existing Families (`LinearStage`, `Slit`); the sparse registry slice means the model is deliberately thin, with the detectors carried pending.

## Not modelled yet

The concrete acquisition recipes (the diffraction / stress-mapping scans, the high-Q PDF collection) are not written yet; they join as the deployment approaches the point where CORA drives P21. Whether the diffraction Methods enter CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
