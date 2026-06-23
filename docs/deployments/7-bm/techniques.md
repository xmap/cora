# Techniques

*What 7-BM is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. 7-BM is multi-technique, and which techniques enter the CORA pilot scope is itself an open question (TECH-1). The function view below survives the eventual equipment choices, which is why it can be written before the hardware is confirmed.

The beam mode is selected per technique over one set of optics, not a fixed source property (BEAM-1):

| Technique | Beam mode | Detector modality | Status in CORA |
| --- | --- | --- | --- |
| Tomography | monochromatic | 2D area camera (scintillator-coupled) | reuses the 2-BM Methods unchanged |
| High-speed imaging | white | high-speed movie camera, chopper-gated | new acquisition Method, pending |
| Radiography | focused (~8 keV) | point photodiode, digitizer-read | new acquisition Method, pending |
| Energy-dispersive diffraction | white | germanium energy-dispersive detector | new Method, pending |
| Confocal fluorescence | (docs stub) | spectroscopic detector | deferred until confirmed (the docs page is empty) |

A few points of intent shape the model:

- **Tomography is pure reuse.** 7-BM runs the same tomoScan engine as 2-BM (single, vertical, horizontal, mosaic scans), so its tomography binds the existing `tomography` and `mosaic_tomography` Methods and the 2-BM detector shape. No new tomography vocabulary is earned.
- **The new techniques are new acquisition Methods, not new Capabilities.** High-speed movie bursts, point-detector radiography traces, and the energy-to-q EDD measurement are new `Method` rows under the existing `acquisition` and `characterization` Capabilities. They are deployment vocabulary; the device Roles (Detector, Sensor) already exist. They are carried pending until the technique enters scope and its data unit is confirmed (HSI-1, RAD-1, DET-1).
- **Beam mode is an operation mode over one beamline.** Inserting or bypassing the monochromator, filtering the white beam, or focusing with the KB pair picks the spectrum for a technique; it is a mode over one set of optics, not separate beamlines (BEAM-1).
- **Techniques can combine.** The docs note energy-dispersive diffraction running simultaneously with tomography through shared optics; CORA models that as coordinated Runs under one Campaign, not a new combined technique (TECH-1).

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join as the techniques enter the pilot scope. See [Open questions](questions.md) for what must be confirmed first.
