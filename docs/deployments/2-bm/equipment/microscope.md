# Microscope

*The 2-BM Fixture that materializes the cross-facility `Microscope` Assembly: the Optique Peter detector, binding eight Assets across six slots over a reusable `Optics` sub-assembly, the optics in one `Housing` that rides the `PropagationDistance` rail, presenting the `Detector` Role.*

The Microscope detector sits about 55 m from the source in the 2-BM experiment hutch (Enclosure `2-BM-B`). It is the operator-facing imaging system: a vendor housing carrying three swappable objectives on a sliding ball-screw selector, a linear propagation-distance stage (the sample-to-detector rail), a FLIR Oryx camera, and a LuAG scintillator. (A second, higher-resolution Oryx camera and its `Camera_Selector` are also modelled; only the 31 MP sensor settings remain pending, see [DET-13](../questions.md#the-microscope-detector).) The whole unit is driven by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py) (MCTOptics is the IOC process name, not the CORA model name). This page explains how CORA models it.

## The model in one picture

What physically holds what, hutch frame and detector table down to the optics (containment, `Asset.parent_id`):

```
2-BM  (Unit, Asset)
├── Frame: 2BM_hutch_frame
│   └── Mount: optics_mount  (6-DoF placement; holds -> Housing)
└── DetectorTable  (Device, Family Table; carries -> PropagationDistance)
    └── PropagationDistance  (Device, LinearStage; sample-to-detector rail; carries -> Housing)
        └── Housing  (Component, Family Housing; containment parent, Asset.parent_id)
            ├── Turret  (Device, LinearStage; sliding ball-screw objective selector)
            ├── Objective_10x  (Device, Objective, 10x)
            ├── Objective_2x  (Device, Objective, 2x)
            ├── Objective_1.1x  (Device, Objective, 1.1x)
            ├── Objective_Selector  (Device, PseudoAxis)
            ├── Camera  (Device, Camera)
            └── Scintillator  (Device, Scintillator)
```

The composition the Fixture materializes (Assembly to Fixture):

```
Fixture: microscope_at_2bm  (surface_id = 2-BM Trust Surface)
├── materializes Assembly = Microscope  (presents_as the Detector Role)
│   ├── sub-assembly optics       -> Assembly = Optics (content-hash pinned)
│   ├── leaf slot camera          (Exactly1)   -> Camera
│   └── leaf slot scintillator    (Exactly1)   -> Scintillator
└── Optics sub-assembly slots  (bound in this Fixture)
    ├── turret                 (Exactly1)   -> Turret
    ├── objectives             (OneOrMore)  -> Objective_10x, Objective_2x, Objective_1.1x
    ├── propagation_distance   (Exactly1)   -> PropagationDistance
    └── objective_selector     (Exactly1)   -> Objective_Selector
```

`Microscope` is the Assembly (the blueprint) and, with `microscope_at_2bm`, the Fixture (the materialization). `Optics` is a reusable sub-assembly the Microscope composes. `Housing` is the physical chassis; it parents seven of the eight functional constituents. The eighth, the `PropagationDistance` rail, is the part the housing itself rides on, so it parents the housing rather than sitting inside it.

## Two axes: composition and containment

Like the [sample tower](sample_tower.md), the detector uses both of CORA's structural axes.

- **Composition** (Assembly to Fixture, flat) answers *what logical cluster presents for binding*. The `Microscope` Assembly composes the `Optics` sub-assembly plus two leaf slots (`camera`, `scintillator`); the Fixture `microscope_at_2bm` binds eight Assets across six leaf slots on the 2-BM Trust Surface. The Assembly `presents_as` the `Detector` Role, so a Method can require a 2D imaging device without pinning a Family.
- **Containment** (`Asset.parent_id`) answers *what physically holds what*. The `Housing` parents seven constituents, the housing rides on the `PropagationDistance` rail (the sample-to-detector stage, so moving it travels the whole detector), and the rail sits on the `DetectorTable`, so the chain is `2-BM -> DetectorTable -> PropagationDistance -> Housing -> constituents`. The housing is the one part installed into a Mount (`optics_mount` on `2BM_hutch_frame`, 6-DoF), and the constituents inherit position from its known internal layout; the Mount records where it sits in space, the `parent_id` what it rests on (orthogonal axes). The rail-carries-housing mounting is an engineering assumption pending staff confirmation (see [DET-12](../questions.md#the-microscope-detector)). This is an approximation: tomography reconstruction calibrates the rotation center separately, so per-constituent Mounts are not pinned (pixel-accurate beam-propagation modelling would add them).

The two axes are orthogonal: the same eight Assets sit on both at once.

## Composition: blueprint in the Catalog, materialized here

The `Microscope` and its reusable `Optics` core are cross-facility composition blueprints, not 2-BM-specific: their slot maps, sub-assembly links, and content hashes live in the [Assemblies catalog](../../../catalog/assemblies.md). In summary, the Microscope presents the `Detector` Role and composes the `Optics` sub-assembly (turret, objectives, objective selector, propagation distance) plus two leaf slots specific to a full detector, `camera` and `scintillator` (the parts a deployment swaps most often); the three objectives all bind the one `OneOrMore` objectives slot, differing only by `magnification`. This page covers how 2-BM materializes that blueprint.

The Fixture `microscope_at_2bm` binds eight Assets across six leaf slots on the 2-BM Trust Surface. It is single-event genesis (it never changes after registration), each bound Asset carries a `fixture_id` back-reference, and an Asset belongs to only one Fixture at a time.

The Microscope carries **zero `required_wires`**: lens selection is the `Objective_Selector` PseudoAxis handing the lens index to the MCTOptics composite (`LensSelect`, below), propagation distance and other setpoints go through the Conductor / ControlPort layer, and the camera trigger arrives from an external timing source wired at Plan level. None of these is intrinsic to the composition, so none is a blueprint wire.

## Vendor catalog

| Model | Manufacturer | Part number | Declared Families |
| --- | --- | --- | --- |
| `optique_peter_micrx080` | Optique Peter | `MICRX080` | `Housing` |
| `nanotec_st4118` | Nanotec | `ST4118M1404-B` | `LinearStage` |
| `mitutoyo_plan_apo` | Mitutoyo | `Plan-Apo-NIR` | `Objective` |
| `flir_oryx` | FLIR | `ORX-10G-51S5M-C` | `Camera` |
| `flir_oryx_31mp` | FLIR | `ORX-10G-310S9M` | `Camera` |
| `schunk_lptm_30` | Schunk | `LPTM-30` | `LinearStage` |
| `crytur_luag` | Crytur | `LuAG:Ce-100um` | `Scintillator` |

Each Model carries the vendor identity PIDINST needs (Manufacturer + Model). The `Turret` binds the Nanotec Model because the objective-selector motor is a third-party stepper (Nanotec `ST4118M1404-B` with a Heidenhain ERO 1420 encoder) inside the Optique Peter housing, confirmed on the [components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). Mitutoyo Plan Apo NIR carries one part number per magnification, so the single `mitutoyo_plan_apo` row splits into three once those numbers are confirmed.

## Objective selector

`Objective_Selector` is a virtual axis. CORA addresses it by writing a lens index (0, 1, 2) to the composite `2bm:MCTOptics:LensSelect` PV; the MCTOptics IOC owns the sequencing behind that single write. The key fact 2-BM staff confirmed (DET-11, operator-verified 2026-06-19) is that the sequencing is a **two-input lookup**: the turret position depends on the **(lens, camera)** pair, not the lens alone. Whenever either `LensSelect` or the camera setpoint (`2bm:MCTOptics:CameraSelect`, driving the `Camera_Selector`) changes, MCTOptics looks up and applies three coordinated values, eighteen calibration PVs over six motors:

| Coupled lookup | Motor(s) | Value PVs | Per-camera dimension |
| --- | --- | --- | --- |
| Turret position | `2bmb:m1` | `Camera{N}LensPos{M}` (6) | active (~0.4-0.6 mm per-camera offset) |
| Camera rotation | `2bmb:m7` (Cam 0), `2bmb:m8` (Cam 1) | `Camera{N}Lens{M}Rotation` (6) | active (rotation-axis preservation) |
| Per-lens focus | `2bmb:m2`/`m3`/`m4` (per lens) | `Camera{N}Lens{M}Focus` (6) | degenerate today (Cam 0 == Cam 1) |

CORA drives only the high-level setpoints (`LensSelect` and `CameraSelect`) and reads the status readbacks (`LensSelected`, `CameraSelected`), never the raw `2bmb:m1`/`m2`/`m3`/`m4`/`m7`/`m8` motor records. Driving any underlying motor directly would bypass one of the three lookups and silently break rotation-axis alignment. Confirmed by 2-BM staff (DET-2, DET-11).

The operator-verified turret positions, the two-dimensional table MCTOptics resolves:

| Lens index | Objective | Camera 0 (5 MP) | Camera 1 (31 MP) |
| --- | --- | --- | --- |
| `0` | 1.1x Mitutoyo | `-59.8184 mm` | `-60.3784 mm` |
| `1` | 2x Mitutoyo | `-0.5734 mm` | `-0.9240 mm` |
| `2` | 10x Mitutoyo | `58.8707 mm` | `59.2300 mm` |

CORA models this **data-only**: its `partition_rule` stays a closed one-dimensional `LookupTable` over lens index, carrying the **Camera 0 column** (the in-beam 5 MP camera) as a single-camera PROVENANCE RECORD of where the turret sits per objective, not an actuation path CORA executes. The full two-dimensional table and the coupled rotation and focus PVs are documentary here and in the [descriptor](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml); they record "what was the turret-position lookup at scan time?" for a Run, but CORA does not resolve them, MCTOptics does.

Writing `Objective_Selector = 1` writes lens index 1 to `2bm:MCTOptics:LensSelect`, and MCTOptics performs the joint move; the write is recorded as a control-dispatch event with a correlation id, and the lookup table is itself event-sourced, so revisions leave an audit trail of which positions were recorded when. The per-lens fine-focus motors (`2bmb:m2/m3/m4`) are MCTOptics-owned and are NOT modelled as CORA Assets; they move as a side effect of `LensSelect`/`CameraSelect` (distinct from `PropagationDistance` / `2bmbAERO:m1`, the sample-to-detector rail CORA drives directly).

> **Deferred (control-layer follow-up).** A true two-dimensional `(lens, camera)` actuation path, resolving turret position, rotation, and focus from both inputs, waits for when CORA builds the real control layer; it would not add a new partition-rule shape (three parallel single-output lookups sharing the `(lens, camera)` input pair reuse the existing `LookupTable` form). Whether to then retire the index-to-position table (modelling `Objective_Selector` as a pass-through index write) and stop modelling `Turret` as a raw-motor Asset is the same structural question DET-2 raised. Today the actuation model is descriptive, so the single-camera provenance-record framing above is the intentional v1.

## Families

- **`Turret` is a `LinearStage`**, not a `RotaryStage`: the selector is a sliding ball-screw stage, so positions are in millimeters and constituent-wiring signal types are `linear_mm`.
- **`Objective`** declares per-lens identity only (`magnification`, `numerical_aperture`, `focal_length`, `working_distance`); motion is via the turret stage.
- **`Housing`, `Camera`, `Scintillator`, `LinearStage`, `PseudoAxis`** are reused unchanged.

## Calibration, drawings, and citation

- **Calibrations (4):** three `magnification` revisions (9.83x / ~2x / 1.10x effective; the 2x figure is nominal, pending re-measurement) and one `effective_thickness` on the LuAG scintillator (100 micrometers). All start `AssertedSource` / `Provisional` and are superseded by `MeasuredSource` revisions when the characterization Procedure runs.
- **Drawings:** the Optique Peter MICRX080 manual `(EDMS, MAN-11863, 0521-0465-A)` is the canonical reference for the Assembly, Housing, and Mount; per-Asset drawings are listed on the [Assets inventory](../inventory.md#engineering-drawings).
- **PIDINST:** the Fixture earns one DOI as a citable station (HZB PEAXIS precedent), and each physical Asset plus the Housing earns its own, linked via `HasComponent` / `IsComponentOf`. `Objective_Selector` is not minted (a virtual axis has no Manufacturer or Owner). DOIs are stub-minted until 2-BM has facility DataCite credentials.

## Operating and swapping

Switch the active objective by writing the `Objective_Selector` index (0/1/2); the execution layer writes that index to the MCTOptics composite (`2bm:MCTOptics:LensSelect`), and MCTOptics moves the turret and applies the per-lens focus and rotation offsets. Pulling a detector for cleaning or recalibration and returning the same one is the light, reversible path (`detach_asset_from_fixture` then `attach_asset_to_fixture`; the Asset stays `Active` with `fixture_id` cleared). Bringing in a *different* camera or scintillator, or retiring one, is heavier: decommission the old Asset if it is leaving, register the replacement, register a new Fixture against the same Assembly with the updated slot map, then move the surviving Assets across. Methods that bind at Assembly level (`needed_assembly_ids`) are unaffected; Plans that enumerate `asset_ids` need the new id only on a retirement.

## Exercised model

The end-to-end model lives in `apps/api/tests/integration/scenarios/test_2bm_microscope_setup.py`: the Housing containment tree, the `Optics` sub-assembly, the `Microscope` Assembly presenting the `Detector` Role, the one Fixture binding eight Assets across six slots, the alternate 31 MP camera and its selector registered as Housing Assets outside the Fixture, and the objective-selector lookup, end to end against Postgres.
