# Techniques

*What 19-BM is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 19-BM is pre-build, so the techniques below are design intent: the APS Practices that will bind them are carried pending on the [APS site page](../aps/index.md#the-techniques-adapted-here). The function view survives the eventual equipment choices, which is why it can be written before the hardware is procured.

19-BM is a single-mode beamline: filtered white-beam tomography. There is no monochromator and no mirror, so unlike 2-BM there is no beam-mode or energy-change technique. The beam spectrum is set by selecting filters in the F3-30 unit, and the science variety is in the acquisition cadence, not the optics.

| Technique | Catalog Method | What it is for |
| --- | --- | --- |
| Filtered white-beam tomography | `tomography` | the standard micron-resolution CT scan |
| Continuous-rotation tomography | `continuous_rotation_tomography` | high-throughput acquisition, the autonomous workhorse |
| Streaming tomography | `streaming_tomography` | live reconstruction feedback |
| Dark / flat fields | `dark_field`, `flat_field` | the reference frames every reconstruction needs |
| First light | `first_light` | commissioning the beam onto the detector |

A few points of intent shape the model:

- **Autonomy and throughput are the point.** 19-BM is built to run unattended at a high scan cadence with a robotic sample changer feeding it. The technique layer is ordinary tomography; what is distinctive is the autonomous operation around it (see [Governance](governance.md)) and the sample-exchange loop (see [Sample](equipment/sample.md)).
- **Spectrum is set by filtering, not optics.** Selecting Si / Ge / Cu filters in the F3-30 unit hardens or softens the white-beam spectrum. This replaces the energy-selection techniques 2-BM has, which depend on its monochromator.
- **Single beam mode.** There is one set of optics and one mode, so there is no beam-mode-change technique to model.

The concrete acquisition recipes (scan sequences, exposure, filter choices) are not written yet; they join as the beamline approaches commissioning. See [Open questions](questions.md) for what must be confirmed first.
