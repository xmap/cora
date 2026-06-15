# The sample tower at 2-BM

*The 2-BM sample positioning stack: one `SampleTower` Assembly presenting as the `Positioner` Role, materialized as one Fixture binding the installed stack, with the kinematic order carried as a containment chain.*

The sample tower sits in the 2-BM experiment hutch (Enclosure `2-BM-B`). It is the operator-facing positioning system: a stack of motion stages, floor to sample, that places and rotates the specimen in the beam. Standard tomography, laminography, and mosaic / large-sample scans all run on this one tower; they differ in the scan recipe, not in the installed hardware. This page explains how CORA models it.

## The model in one picture

```
2-BM (Unit, Asset)
|
+-- SampleTable (Device, Family Table)            <-- base, floor-referenced
      +-- Hexapod (Device, Family Hexapod)         coarse 6-DoF pose
            +-- LaminographyPitch (Device, Family TiltStage)   Kohzu goniometer
                  +-- Rotary (Device, Family RotaryStage)      theta air-bearing
                        +-- SampleTop_X (Device, Family LinearStage)
                              +-- SampleTop_Z (Device, Family LinearStage)
```

```
Fixture: sample_tower_at_2bm
  materializes Assembly = SampleTower (presents_as the Positioner Role), which composes
  five leaf slots, bound to the installed stack:
    table         -> SampleTable
    coarse_pose   -> Hexapod
    tilt          -> LaminographyPitch
    rotation      -> Rotary
    sample_top (1+) -> SampleTop_X  |  one OneOrMore slot,
    sample_top (1+) -> SampleTop_Z  |  two bindings
```

`SampleTower` is the name of the Assembly (the blueprint). The conceptual tower-the-thing IS the Assembly plus its Fixture; there is no single physical chassis Asset (unlike the Microscope's `Housing`), because the tower is a kinematic stack where each stage is bolted to the one below.

## Two axes: composition and containment

Like the [Microscope](microscope.md), the tower uses both of CORA's structural axes, and they answer different questions.

- **Composition** (Assembly to Fixture, flat) answers *what logical cluster presents here for binding*. The `SampleTower` Assembly composes five leaf slots; the Fixture binds them to six concrete Assets (the `sample_top` OneOrMore slot carries two). The Assembly `presents_as` the `Positioner` Role, so a Method can require a sample positioner as one typed unit.
- **Containment** (`Asset.parent_id`, a recursive tree) answers *what physical thing holds what*. Here it is a literal-deep chain: `SampleTable` parents the `Hexapod`, which parents `LaminographyPitch`, then `Rotary`, then `SampleTop_X`, then `SampleTop_Z`. Each stage's position depends on the one below, which is the physical truth and is why the chain is deep rather than the Microscope's shallow housing-parents-all.

The two axes are orthogonal: the same Assets sit on both at once.

## The experiment-vs-loadout boundary

The load-bearing rule: a different *scan* over the same installed stack is a Recipe `Method` / `Plan`; a different *installed stack* (a stage added, removed, or physically exchanged) is a different Fixture.

- **Tomography, laminography, and mosaic are all Method/Plan over this one Fixture.** Laminography is not a separate instrument and not a second loadout: the Kohzu `LaminographyPitch` goniometer and its fixed wedge are permanently installed, and tomo vs lamino is a tilt *setpoint* on that stage (a Plan parameter), not a hardware insert or remove. Mosaic / large-sample tiling steps the `SampleTop` and table translations between sub-scans on the same stack.
- **A second Fixture is reserved for a real hardware exchange.** The 2-BM rotary kit (ABS250MP-M-AS installed, plus ABRS-150MP-M-AS and the ABS2000-1000AS-RU spindle) is interchangeable in principle, but the b-station stack runs the single installed ABS250MP today, so the swap is a future trigger, not a live loadout variant.

## Families

The tower introduces one new Family and reuses the rest.

- **`TiltStage`** (new): the Kohzu goniometer that tilts the rotation axis. A tilt is a rotational, limited-range stage, so it is not a `LinearStage`; and it is not a `RotaryStage`, because that Family's affordances include `Following` / `Marking` for the theta position-synchronised-output fly-scan, which a tilt does not do. `TiltStage` affords `Rotatable`, `Homeable`, `Limitable`.
- **`Table`** (the base): the bare role-noun for the sample optical table, following the `OpticalHousing` to `Housing` precedent (the qualifier names the contents, not the chassis kind). The Asset instance is `SampleTable`.
- **`Hexapod`, `RotaryStage`, `LinearStage`** are reused unchanged.

## Open items

- **STAGE-5** (operator): the rotary kit's mode/station labels (`fast tomo` / `mona tomo` / `spindle`) conflict pre vs post APS-U, and whether the b-station stack actively swaps among the kit today (the model assumes one installed ABS250MP, not swapped).
- **STAGE-6** (operator): the exact Kohzu model of `LaminographyPitch` (working value `SA16A-RM`; the source swivel kit also lists `SA16A-RS` / `SA07A-R2L`).
- **Deferred:** the fixed laminography wedge (a passive part, not a slotted Asset), the hexapod's six DoF facets (`PseudoAxis`), and the lamino pitch-tracks-theta coupling (a conduct-time PseudoAxis / Plan concern, not an Assembly template wire).

## Exercised model

The end-to-end model lives in `apps/api/tests/integration/scenarios/test_2bm_sample_tower_setup.py`: the Unit install, the five Families, the six stack Assets in the deep `parent_id` chain, the per-constituent Mount/install, the `SampleTower` Assembly presenting as the `Positioner` Role, the one Fixture binding the five-slot stack, the attaches, and a positioning Method/Practice/Plan that requires the tower as a unit (`needed_assembly_ids`). The scenario also asserts the experiment-vs-loadout boundary (the Fixture carries no scan-strategy override).
