# Detector

*One detector gantry serving both endstations. Design-phase; values are TDR design targets.*

TomoWISE has a single detector system on a gantry that travels the experiment hutch on 7 m floor rails, from the microtomography station at 45 m to the hutch wall at 52 m. It serves both endstations, so it is modelled once, in the detection stage of the [descriptor](../inventory.md).

## The model in one picture

What physically holds what, gantry down to the optics (containment, `Asset.parent_id`):

```
TomoWISE  (Unit, Asset)
└── DetectorGantry  (Component, Family Table; Xd/Yd/Zd on 7 m rails; the shared propagation rail)
    ├── MicLFOV  (Component, Family Housing; model optique_peter_micrx080)
    │   ├── Turret             (Device, LinearStage; objective changer)
    │   ├── Objective_1x       (Device, Objective)
    │   ├── Objective_2x       (Device, Objective)
    │   ├── ObjectiveSelector  (Device, PseudoAxis)
    │   └── Scintillator       (Device, Scintillator)
    ├── MicHR  (Component, Family Housing; model optique_peter_micrx080)
    │   ├── Turret             (Device, LinearStage; objective changer)
    │   ├── Objective_4x       (Device, Objective)
    │   ├── Objective_10x      (Device, Objective)
    │   ├── Objective_20x      (Device, Objective)
    │   ├── ObjectiveSelector  (Device, PseudoAxis)
    │   └── Scintillator       (Device, Scintillator)
    └── CameraI / CameraII / CameraIII / CameraIV  (Device, Camera; shared pool, paired per run)
```

Each microscope is the cross-facility `Microscope` Assembly (the same blueprint 2-BM uses), composing the reusable `Optics` sub-assembly plus the leaf slots. Unlike 2-BM, no Fixture is registered yet (TomoWISE is design-phase: no scenario binds Assets to slots), so the slot map below is the **planned** composition, not a materialized Fixture:

```
Planned composition (no Fixture registered yet)  -- per microscope
materializes Assembly = Microscope  (presents_as the Detector Role)
├── sub-assembly optics  -> Assembly = Optics
│   ├── turret               (Exactly1)   -> Turret
│   ├── objectives           (OneOrMore)  -> Objective_1x, Objective_2x   (MicLFOV)
│   │                                        Objective_4x, Objective_10x, Objective_20x  (MicHR)
│   ├── objective_selector   (Exactly1)   -> ObjectiveSelector
│   └── propagation_distance (ZeroOrOne)  -> (empty; the shared DetectorGantry rail provides it)
├── leaf slot scintillator   (Exactly1)   -> Scintillator
└── leaf slot camera         (ZeroOrOne)  -> (empty; drawn from the shared camera pool per run)
```

Two axes, orthogonal: **containment** (`Asset.parent_id`, the tree above) is what holds what; **composition** (Assembly to Fixture, the slot map) is what presents for binding. The `camera` and `propagation_distance` slots are `ZeroOrOne` and left empty here because TomoWISE shares its four cameras and one gantry rail across both microscopes (the catalog assembly was generalized to allow this); the `Housing` binds `optique_peter_micrx080` as the design-target candidate (DET-2).

## Gantry

| Device | Family | Design spec (TDR) |
| --- | --- | --- |
| `DetectorGantry` | `Table` | Xd, Yd, Zd axes, Zd on 7 m floor rails (45 to 52 m); the shared propagation rail. A removable flight tube (1 mbar) reduces air scatter. |

## Microscopes

Interchangeable visible-light microscopes (scintillator, objective, 45 deg mirror, CMOS camera) couple the scintillator image to the cameras, built for sensors up to 60 mm diagonal. Each is **composed as the cross-facility `Microscope` Assembly** that 2-BM also uses, not a loose family: a `Housing` anchors an `Optics` sub-assembly (a turret, the objectives, and a virtual objective selector that switches magnification "without intervening in the setup") over a `Scintillator`. The Optique Peter optics model from 2-BM, `optique_peter_micrx080`, is bound on each Housing as the design-target candidate (the TDR names only the vendor; confirmation is DET-2).

Because the two microscopes share the four cameras and the one `DetectorGantry` propagation rail, the assembly's `camera` and `propagation_distance` slots are decoupled: the catalog assembly was generalized to make both `ZeroOrOne`, and each microscope leaves them empty. The cameras are modelled as separate shared Assets (below); the gantry provides the propagation distance.

| Microscope | Family | Housing model | Design spec (TDR) |
| --- | --- | --- | --- |
| `MicLFOV` | `Housing` (Microscope Assembly) | `optique_peter_micrx080` | large field of view, 1-2x magnification, NA > 0.2; objectives 1x / 2x |
| `MicHR` | `Housing` (Microscope Assembly) | `optique_peter_micrx080` | high resolution, 4x / 10x / 20x, NA > 0.4 |

## Cameras

Four cameras span the throughput-versus-speed-versus-resolution trade, all shared across both microscopes. The models are chosen in project year 2 (DET-1); the sensors below are the design targets.

| Camera | Family | Design spec (TDR) |
| --- | --- | --- |
| `CameraI` | `Camera` | 16-25 Mpix, 16-bit sCMOS, 100-150 fps; general throughput |
| `CameraII` | `Camera` | 4 Mpix, 12-bit CMOS, > 50,000 fps; high-speed dynamics |
| `CameraIII` | `Camera` | ~4 Mpix, > 2,000 fps; streaming |
| `CameraIV` | `Camera` | 150 Mpix, 54 x 40 mm sensor, 3.76 um pixel; matches the large-sensor device procured for DanMAX |

## Families

All reused, none new: `Table` (the gantry), `Housing` (each microscope chassis, binding `optique_peter_micrx080`), `LinearStage` (the objective-changer turret), `Objective` (per-lens identity), `PseudoAxis` (the objective selector), `Scintillator`, and `Camera`. The composition reuses the 2-BM `Microscope` / `Optics` Assembly blueprints unchanged; only the `camera` and `propagation_distance` slot cardinalities were generalized to `ZeroOrOne`.

The camera models, the bound microscope-optics model confirmation (DET-2), and the trigger path are the main detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
