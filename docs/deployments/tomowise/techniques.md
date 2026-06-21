# Techniques

*What TomoWISE is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../maxiv/index.md#the-techniques-adapted-here) is how a facility adapts it. TomoWISE is pre-build, so the techniques below are design intent: the MAX IV Practices that will bind them are carried pending on the [MAX IV site page](../maxiv/index.md#the-techniques-adapted-here). The function view survives the eventual equipment choices, which is why it can be written before the hardware is procured.

The beamline's five operation modes (TDR) select the source, filtering, monochromator, and KB optics for a given technique:

| Technique | Source | Monochromator | KB | What it is for |
| --- | --- | --- | --- | --- |
| Standard microtomography | CPMU14 | MLM | no | high-throughput monochromatic CT |
| High-speed microtomography (small FOV) | CPMU14 | MLM or none | no | sub-micron pixel, fast dynamics |
| Large-FOV / white-beam microtomography | 3T3PW | none | no | large or highly attenuating samples |
| Nanotomography | CPMU14 | MLM | yes | 200-nm-class cone-beam imaging |
| Laminography | CPMU14 | MLM | no | flat, extended samples (tilt axis, not a separate fixture) |

A few points of intent shape the model:

- **Source switching is first-class.** Two insertion devices (one `InsertionDevice` Family, two Assets) are selected per mode, unlike the single bending-magnet source at 2-BM. The mode determines which is in the beam.
- **Laminography is a tilt setpoint, not a separate station.** It runs on the microtomography endstation's tilt axis, mirroring the 2-BM laminography decision: the same installed stack, a different Method, not a new Fixture.
- **Monochromatic and white-beam are the same beamline.** Inserting or bypassing the MLM (and the filter chain) picks the spectrum; it is an operation mode over one set of optics, not two beamlines.

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join as the beamline approaches commissioning. See [Open questions](questions.md) for what must be confirmed first.
