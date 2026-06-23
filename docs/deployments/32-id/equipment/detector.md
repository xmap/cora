# Detector

*The TXM indirect-detection chain in 32-ID-C. Design-phase; values carried as confirm.*

The detector modelled here is the TXM indirect-detection chain: a scintillator converts the magnified X-ray image to visible light, a microscope objective couples it to a camera, all on a granite detector support downstream of a flight path that reduces air scatter. It is modelled in the detection stage of the [descriptor](../inventory.md), reusing the existing detector Families.

## The model in one picture

What holds what, support down to the camera (containment, `Asset.parent_id`):

```
32-ID  (Unit, Asset)
└── TXMDetectorSupport  (Component, Family Table; granite detector support, follower mechanics)
    ├── TXMScintillator  (Device, Scintillator; X-ray to visible conversion)
    ├── TXMObjective     (Device, Objective; couples the scintillator image to the camera)
    └── TXMCamera        (Device, Camera; records the image)
```

Unlike 2-BM and TomoWISE, the TXM detector is not composed as a `Microscope` Assembly here: the published optics are a zone-plate imaging system rather than a turret of swappable visible-light objectives, so this scaffold carries the chain as a plain device group until the confirmed optics make a composed shape worthwhile. It could earn the `Microscope` / `Optics` Assembly later, once a scenario registers the Fixture.

## Detector chain

| Device | Family | Design spec / note |
| --- | --- | --- |
| `TXMDetectorSupport` | `Table` | granite detector support and follower mechanics |
| `TXMScintillator` | `Scintillator` | converts the X-ray image to visible light; material and thickness unconfirmed (`DET-2`) |
| `TXMObjective` | `Objective` | visible-light coupling objective; magnification set unconfirmed (`DET-2`) |
| `TXMCamera` | `Camera` | detector camera; model, sensor, and frame rate unconfirmed (`DET-1`) |

The flight-path gas (helium or vacuum) is unconfirmed (`SUP-1`).

## Families

All reused, none new: `Table` (the detector support), `Scintillator`, `Objective`, and `Camera`. The camera model, the detector optics specs, and the flight-path gas are the detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
