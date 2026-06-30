# Techniques

*What I-TOMCAT is designed to do, as intent. Modelling exercise.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../psi/index.md#the-techniques-adapted-here) is how a facility adapts it. The PSI Practices that bind these are carried pending on the [PSI site page](../psi/index.md#the-techniques-adapted-here) until PSI staff confirm them. The function view survives the eventual equipment choices, which is why it can be written from the public pages before the controls are wired.

I-TOMCAT is a hard X-ray tomographic-microscopy beamline. Its techniques are the tomography-family Methods the catalog already carries, the same ones the APS [2-BM](../2-bm/index.md) pilot earned:

| Technique | Catalog Method | What it is for |
| --- | --- | --- |
| Standard microtomography | [`tomography`](../../catalog/methods.md) | absorption-contrast 3D imaging on the U15 undulator, monochromatic 8-30 keV |
| Propagation-based phase contrast | [`tomography`](../../catalog/methods.md) | edge-enhanced imaging of weakly-absorbing samples (a propagation distance, not a separate fixture) |
| Fast / dynamic 4D tomography | [`streaming_tomography`](../../catalog/methods.md) | continuous high-speed acquisition via the GigaFRoST streaming camera, for in-situ dynamics |

A few points of intent shape the model:

- **The GigaFRoST camera is the dynamic-tomography enabler.** The PSI in-house continuous-streaming camera (up to 1255 fps full-frame, ~8 GB/s, up to ~33,875 Hz on a reduced ROI) is what distinguishes I-TOMCAT's fast and dynamic 4D tomography from a standard CT beamline. It maps to the catalog `streaming_tomography` Method, not a new one.
- **Phase contrast is a propagation distance, not a separate station.** Propagation-based phase-contrast imaging runs on the same endstation by moving the detector back from the sample; it is an acquisition mode over one set of optics, modelled under `tomography`, mirroring the 2-BM decision.
- **Grating interferometry is out of scope.** The legacy TOMCAT offered it only occasionally; it is not modelled here and is not one of the SLS Practices until staff confirm it is offered on the rebuilt beamline (TECH-1).

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join if the deployment firms toward a real connection. See [Open questions](questions.md) for what must be confirmed first.
