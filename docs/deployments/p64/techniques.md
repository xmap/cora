# Techniques

*What the modelled part of P64 is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../petra-iii/index.md#the-techniques-adapted-here) is how a facility adapts it. P64's XAS technique earns no catalog Method today, so the Method below renders unlinked and is carried pending until a technique enters scope (`TECH-1`).

## Advanced X-ray absorption spectroscopy

P64 scans the incident energy across an absorption edge (the Tsai DCM coupled to the undulator) and reads the absorption in transmission (the Lambda detectors) and, for dilute samples, in fluorescence on the large [multi-element detector](equipment/detector.md), measuring EXAFS / XANES.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray absorption spectroscopy (EXAFS / XANES) | `xas_spectroscopy` | the coupled mono + undulator energy scan read against transmission / multi-element fluorescence; reuses the `xas_spectroscopy` slug BMM / ISS / i20-1 / P04 share, a further consumer (`TECH-1`) |

## A high-rate fluorescence EXAFS beamline on familiar vocabulary

P64 is the advanced half of the PETRA III XAS pair (with the applied [P65](../p65/index.md)). Its distinguishing capability is dilute, high-rate fluorescence detection via the large multi-element SIS3302 detector, but it coins no new vocabulary: it reuses the `xas_spectroscopy` slug already carried pending across the fleet, and its instrument anatomy reuses existing Families (the `Monochromator`, the `Mirror` pair, the `Camera` Lambda detectors, the `EnergyDispersiveSpectrometer` fluorescence detector). The continuous energy fly-scan is a control-plane detail, not a new Method.

## Not modelled yet

The concrete acquisition recipes (the QEXAFS / step-scan energy sequences, the multi-element detector deadtime handling, the DAC high-pressure XAS) are not written yet; they join as the deployment approaches the point where CORA drives P64. Whether `xas_spectroscopy` enters CORA's catalog is an owner-scope decision on [Model](model.md#deliberately-not-here-yet); see [Open questions](questions.md) for the world-facts to confirm first.
