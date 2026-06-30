# Techniques

*What the modelled part of P65 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P65's XAS technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Applied X-ray absorption spectroscopy

P65 scans the incident energy across an absorption edge (the channel-cut DCM) and reads the absorption in transmission (ion chambers) and fluorescence, for routine applied EXAFS / XANES (catalysis, batteries, environmental science).

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray absorption spectroscopy (EXAFS / XANES) | `xas_spectroscopy` | the CDCM energy scan read against transmission / fluorescence; reuses the `xas_spectroscopy` slug BMM / ISS / i20-1 / P04 / P64 share, a further consumer (`TECH-1`) |

## The applied half of the XAS pair

P65 is the applied / high-throughput half of the PETRA III XAS pair, the sibling of the advanced [P64](../p64/index.md). Where P64 specialises in dilute high-rate fluorescence with a large multi-element detector, P65 serves routine transmission + fluorescence EXAFS. Both reuse the `xas_spectroscopy` slug; neither coins a new Family or Method. P65's instrument anatomy is deliberately thin (a `Monochromator` energy axis, `LinearStage` sample bank, `Slit`, `Table`), matching what the registry exposes.

## Not modelled yet

The concrete acquisition recipes (the step / continuous energy scans, the ion-chamber / fluorescence detection chain, the sample-changer throughput loop) are not written yet; they join as the deployment approaches the point where CORA drives P65. Whether `xas_spectroscopy` enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
