# Detector

*The microscope and high-speed camera suite. Modelling exercise; values read from PSI's public pages.*

I-TOMCAT records the X-ray image with a visible-light microscope (interchangeable objectives over a scintillator) coupled to a suite of high-speed cameras. It is modelled in the detection stage of the [descriptor](../inventory.md). The PSI in-house GigaFRoST continuous-streaming camera is what defines I-TOMCAT's fast and dynamic 4D tomography.

## The model in one picture

What physically holds what, microscope down to the optics (containment, `Asset.parent_id`):

```
I-TOMCAT  (Unit, Asset)
└── Microscope  (Component, Family Housing; visible-light microscope, 1x-40x)
    ├── Objective       (Device, Objective; interchangeable, 1x to 40x)
    └── Scintillator    (Device, Scintillator; LSO:Tb / LuAG:Ce)
HighSpeedCamera / StreamingCamera / ScienceCamera  (Device, Camera; the camera suite, paired per run)
```

Unlike 2-BM, the microscope is carried as a plain `Housing` with `Objective` and `Scintillator` constituents rather than a composed catalog `Microscope` Assembly, because the rebuilt-beamline optics model is not yet confirmed (DET-2). It could earn the cross-facility `Microscope` / `Optics` Assembly composition (the one 2-BM and TomoWise use) once a scenario registers a Fixture.

## Microscope

The visible-light microscope couples the scintillator image to the cameras. The legacy TOMCAT carried six optical microscopes spanning 1x to 40x; the rebuilt-beamline optics model and the objective set are an open question (DET-2).

| Device | Family | Design spec (public pages) |
| --- | --- | --- |
| `Microscope` | `Housing` | visible-light microscope, 1x-40x; optics model and Assembly composition deferred (DET-2) |
| `Objective` | `Objective` | interchangeable objectives, 1x to 40x |
| `Scintillator` | `Scintillator` | LSO:Tb (5.9 um, sub-um res) or LuAG:Ce (20 um, most used); the rebuilt set is DET-2 |

## Cameras

Three cameras span the throughput-versus-speed trade. The models are read from the public detectors page and carried as "(target)" pending confirmation (DET-1); the GigaFRoST is the dynamic-tomography enabler.

| Camera | Family | Design spec (public pages) |
| --- | --- | --- |
| `HighSpeedCamera` | `Camera` | 2016x2016, 11 um pixel, up to 1255 fps; target pco.dimax |
| `StreamingCamera` | `Camera` | PSI in-house GigaFRoST, 2016x2016, 11 um, up to 1255 fps continuous (~8 GB/s, up to ~33,875 Hz reduced ROI) |
| `ScienceCamera` | `Camera` | general-throughput sCMOS; target pco.edge family (4.2 / 5.5 / 10) |

## Families

All reused, none new: `Housing` (the microscope chassis), `Objective` (per-lens identity), `Scintillator`, and `Camera`. No catalog Model is bound; the part numbers above are read from public pages, not staff-confirmed.

The camera models, the microscope optics model and Assembly composition (DET-2), and the trigger path are the main detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
