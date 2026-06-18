# Microscope

*The 2-BM Fixture that materializes the cross-facility `Microscope` Assembly: the Optique Peter detector, binding eight Assets across six slots over a reusable `Optics` sub-assembly, the optics in one `Housing` that rides the `PropagationDistance` rail, presenting the `Detector` Role.*

The Microscope detector sits about 55 m from the source in the 2-BM experiment hutch (Enclosure `2-BM-B`). It is the operator-facing imaging system: a vendor housing carrying three swappable objectives on a sliding ball-screw selector, a linear propagation-distance stage (the sample-to-detector rail), a FLIR Oryx camera, and a LuAG scintillator. (A second, higher-resolution Oryx camera and its `Camera_Selector` are also modelled; only the 31 MP sensor settings remain pending, see [Open items](#open-items).) The whole unit is driven by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py) (MCTOptics is the IOC process name, not the CORA model name). This page explains how CORA models it.

## The model in one picture

<div class="dtree" markdown="0">
<ul>
<li><span class="node">2-BM</span> <span class="meta">Unit, Asset</span>
<ul>
<li><span class="node">Frame: 2BM_hutch_frame</span>
<ul>
<li><span class="node">Mount: optics_mount</span> <span class="meta">6-DoF placement</span> <span class="rel">holds &rarr; Housing</span></li>
</ul>
</li>
<li><span class="node">DetectorTable</span> <span class="meta">Device, Family Table</span> <span class="rel">carries &rarr; PropagationDistance</span>
<ul>
<li><span class="node">PropagationDistance</span> <span class="meta">Device, LinearStage; sample-to-detector rail</span> <span class="rel">carries &rarr; Housing</span>
<ul>
<li><span class="node">Housing</span> <span class="meta">Component, Family Housing</span> <span class="rel">containment parent (Asset.parent_id)</span>
<ul>
<li><span class="node">Turret</span> <span class="meta">Device, LinearStage, sliding ball-screw objective selector</span></li>
<li><span class="node">Objective_10x</span> <span class="meta">Device, Objective, 10x</span></li>
<li><span class="node">Objective_2x</span> <span class="meta">Device, Objective, 2x</span></li>
<li><span class="node">Objective_1.1x</span> <span class="meta">Device, Objective, 1.1x</span></li>
<li><span class="node">Objective_Selector</span> <span class="meta">Device, PseudoAxis</span></li>
<li><span class="node">Camera</span> <span class="meta">Device, Camera</span></li>
<li><span class="node">Scintillator</span> <span class="meta">Device, Scintillator</span></li>
</ul>
</li>
</ul>
</li>
</ul>
</li>
<li><span class="node">Fixture: microscope_at_2bm</span> <span class="meta">surface_id = 2-BM Trust Surface</span>
<ul>
<li><span class="node">materializes Assembly = Microscope</span> <span class="meta">presents_as the Detector Role</span>
<ul>
<li><span class="node">sub-assembly optics</span> <span class="rel">&rarr; Assembly = Optics (content-hash pinned)</span></li>
<li><span class="node">leaf slot camera</span> <span class="meta">Exactly1</span> <span class="rel">&rarr; Camera</span></li>
<li><span class="node">leaf slot scintillator</span> <span class="meta">Exactly1</span> <span class="rel">&rarr; Scintillator</span></li>
</ul>
</li>
<li><span class="node">Optics sub-assembly slots</span> <span class="meta">bound in this Fixture</span>
<ul>
<li><span class="node">turret</span> <span class="meta">Exactly1</span> <span class="rel">&rarr; Turret</span></li>
<li><span class="node">objectives</span> <span class="meta">OneOrMore</span> <span class="rel">&rarr; Objective_10x, Objective_2x, Objective_1.1x</span></li>
<li><span class="node">propagation_distance</span> <span class="meta">Exactly1</span> <span class="rel">&rarr; PropagationDistance</span></li>
<li><span class="node">objective_selector</span> <span class="meta">Exactly1</span> <span class="rel">&rarr; Objective_Selector</span></li>
</ul>
</li>
</ul>
</li>
</ul>
</li>
</ul>
</div>

`Microscope` is the Assembly (the blueprint) and, with `microscope_at_2bm`, the Fixture (the materialization). `Optics` is a reusable sub-assembly the Microscope composes. `Housing` is the physical chassis; it parents seven of the eight functional constituents. The eighth, the `PropagationDistance` rail, is the part the housing itself rides on, so it parents the housing rather than sitting inside it.

## Two axes: composition and containment

Like the [sample tower](sample_tower.md), the detector uses both of CORA's structural axes.

- **Composition** (Assembly to Fixture, flat) answers *what logical cluster presents for binding*. The `Microscope` Assembly composes the `Optics` sub-assembly plus two leaf slots (`camera`, `scintillator`); the Fixture `microscope_at_2bm` binds eight Assets across six leaf slots on the 2-BM Trust Surface. The Assembly `presents_as` the `Detector` Role, so a Method can require a 2D imaging device without pinning a Family.
- **Containment** (`Asset.parent_id`) answers *what physically holds what*. The `Housing` parents seven constituents, the housing rides on the `PropagationDistance` rail (the sample-to-detector stage, so moving it travels the whole detector), and the rail sits on the `DetectorTable`, so the chain is `2-BM -> DetectorTable -> PropagationDistance -> Housing -> constituents`. The housing is the one part installed into a Mount (`optics_mount` on `2BM_hutch_frame`, 6-DoF), and the constituents inherit position from its known internal layout; the Mount records where it sits in space, the `parent_id` what it rests on (orthogonal axes). The rail-carries-housing mounting is an engineering assumption pending staff confirmation (see [Open items](#open-items)). This is an approximation: tomography reconstruction calibrates the rotation center separately, so per-constituent Mounts are not pinned (pixel-accurate beam-propagation modelling would add them).

The two axes are orthogonal: the same eight Assets sit on both at once.

## Composition: blueprint in the Catalog, materialized here

The `Microscope` and its reusable `Optics` core are cross-facility composition blueprints, not 2-BM-specific: their slot maps, sub-assembly links, and content hashes live in the [Assemblies catalog](../../../catalog/assemblies.md). In summary, the Microscope presents the `Detector` Role and composes the `Optics` sub-assembly (turret, objectives, objective selector, propagation distance) plus two leaf slots specific to a full detector, `camera` and `scintillator` (the parts a deployment swaps most often); the three objectives all bind the one `OneOrMore` objectives slot, differing only by `magnification`. This page covers how 2-BM materializes that blueprint.

The Fixture `microscope_at_2bm` binds eight Assets across six leaf slots on the 2-BM Trust Surface. It is single-event genesis (it never changes after registration), each bound Asset carries a `fixture_id` back-reference, and an Asset belongs to only one Fixture at a time.

The Microscope carries **zero `required_wires`**: lens selection is the `Objective_Selector` PseudoAxis handing the lens index to the MCTOptics composite (`LensSelect`, below), propagation distance and other setpoints go through the Conductor / ControlPort layer, and the camera trigger arrives from an external timing source wired at Plan level. None of these is intrinsic to the composition, so none is a blueprint wire.

## Vendor catalog (Models)

| Model | Manufacturer | Part number | Declared Families |
| --- | --- | --- | --- |
| `optique_peter_micrx080` | Optique Peter | `MICRX080` | `Housing` |
| `nanotec_st4118m1404_b` | Nanotec | `ST4118M1404-B` | `LinearStage` |
| `mitutoyo_plan_apo` | Mitutoyo | `Plan-Apo-NIR` | `Objective` |
| `flir_oryx` | FLIR | `ORX-10G-51S5M-C` | `Camera` |
| `flir_oryx_31mp` | FLIR | `ORX-10G-310S9M` | `Camera` |
| `schunk_lptm_30` | Schunk | `LPTM-30` | `LinearStage` |
| `crytur_luag` | Crytur | `LuAG:Ce-100um` | `Scintillator` |

Each Model carries the vendor identity PIDINST needs (Manufacturer + Model). The `Turret` binds the Nanotec Model because the objective-selector motor is a third-party stepper (Nanotec `ST4118M1404-B` with a Heidenhain ERO 1420 encoder) inside the Optique Peter housing, confirmed on the [components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). Mitutoyo Plan Apo NIR carries one part number per magnification, so the single `mitutoyo_plan_apo` row splits into three once those numbers are confirmed.

## Objective selector

`Objective_Selector` is a virtual axis. CORA addresses it by writing a lens index (0, 1, 2) to the composite `2bm:MCTOptics:LensSelect` PV; the MCTOptics IOC owns the sequencing behind that single write, moving the turret (`2bmb:m1`) to the selected objective's position and applying that objective's per-lens fine focus (`2bmb:m2`/`m3`/`m4`, the `LENS0/1/2_FOCUS` macros) and rotation offsets. CORA drives the high-level composite (`LensSelect`, `LensName`, `CameraSelect`, and the status readbacks), never the raw `2bmb:m1`-`m4` motor records. Confirmed by 2-BM staff (DET-2).

Its `partition_rule`, a closed `LookupTable` over lens index, is therefore CORA's PROVENANCE RECORD of which turret position each objective sits at (the selector is a sliding ball-screw stage, not a rotating turret), not an actuation path CORA executes:

| `Objective_Selector` | Turret position | Objective in beam |
| --- | --- | --- |
| `0` | `-60.030 mm` | 1.1x Mitutoyo |
| `1` | `-0.837 mm` | 2x Mitutoyo |
| `2` | `58.640 mm` | 10x Mitutoyo |

Writing `Objective_Selector = 1` writes lens index 1 to `2bm:MCTOptics:LensSelect`, and MCTOptics performs the move; the write is recorded as a control-dispatch event with a correlation id, and the lookup table is itself event-sourced, so revisions leave an audit trail of which positions were recorded when. The per-lens fine-focus motors (`2bmb:m2/m3/m4`) are MCTOptics-owned and are NOT modelled as CORA Assets; they move as a side effect of `LensSelect` (distinct from `PropagationDistance` / `2bmbAERO:m1`, the sample-to-detector rail CORA drives directly).

> **Deferred (DET-2 follow-up).** Whether to retire the index-to-position `LookupTable` (modelling `Objective_Selector` as a pass-through index write) and stop modelling `Turret` as a raw-motor Asset is a structural question for when CORA builds the real control layer. Today the actuation model is descriptive, so the provenance-record framing above is the intentional v1.

## Families

- **`Turret` is a `LinearStage`**, not a `RotaryStage`: the selector is a sliding ball-screw stage, so positions are in millimeters and constituent-wiring signal types are `linear_mm`.
- **`Objective`** declares per-lens identity only (`magnification`, `numerical_aperture`, `focal_length`, `working_distance`); motion is via the turret stage.
- **`Housing`, `Camera`, `Scintillator`, `LinearStage`, `PseudoAxis`** are reused unchanged.

## Calibration, drawings, and citation

- **Calibrations (4):** three `magnification` revisions (9.83x / ~2x / 1.10x effective; the 2x figure is nominal, pending re-measurement) and one `effective_thickness` on the LuAG scintillator (100 micrometers). All start `AssertedSource` / `Provisional` and are superseded by `MeasuredSource` revisions when the characterization Procedure runs.
- **Drawings:** the Optique Peter MICRX080 manual `(EDMS, MAN-11863, 0521-0465-A)` is the canonical reference for the Assembly, Housing, and Mount; per-Asset drawings are listed on the [Assets inventory](../assets.md#engineering-drawings).
- **PIDINST:** the Fixture earns one DOI as a citable station (HZB PEAXIS precedent), and each physical Asset plus the Housing earns its own, linked via `HasComponent` / `IsComponentOf`. `Objective_Selector` is not minted (a virtual axis has no Manufacturer or Owner). DOIs are stub-minted until 2-BM has facility DataCite credentials.

## Operating and swapping

Switch the active objective by writing the `Objective_Selector` index (0/1/2); the execution layer writes that index to the MCTOptics composite (`2bm:MCTOptics:LensSelect`), and MCTOptics moves the turret and applies the per-lens focus and rotation offsets. Pulling a detector for cleaning or recalibration and returning the same one is the light, reversible path (`detach_asset_from_fixture` then `attach_asset_to_fixture`; the Asset stays `Active` with `fixture_id` cleared). Bringing in a *different* camera or scintillator, or retiring one, is heavier: decommission the old Asset if it is leaving, register the replacement, register a new Fixture against the same Assembly with the updated slot map, then move the surviving Assets across. Methods that bind at Assembly level (`needed_assembly_ids`) are unaffected; Plans that enumerate `asset_ids` need the new id only on a retirement.

## Open items

- The `Objective_Selector` `partition_rule` references the turret motor by Asset id, but nothing enforces that this is the same motor bound into the `turret` slot; there is no cross-slot constraint primitive today.
- `register_fixture` requires every bound constituent to be installed in some Mount, so a pool-backed deployment gives each a lightweight Mount even though the housing approximates its placement.
- Plan-binding does not yet enforce `needed_assembly_ids` satisfaction: a Plan that omits a Fixture materializing the required Assembly passes silently today.
- The alternate 31 MP camera (`Camera_HighRes`) and the `Camera_Selector` (Schunk LPTM 30, `2bmb:m5`, rotation motors `2bmb:m7`/`m8`) are now registered Assets under the `Housing`: the selector switches the optical path between the 5 MP `Camera` (bound into the Fixture) and the 31 MP. `Camera_HighRes` is registered identity-only; item_020 confirms its sensor (6464 x 4852 px, 26 fps), leaving only bit depth, sensor kind, and readout mode pending ([DET-13](../questions.md#the-microscope-detector)), which the `Camera` schema needs before the settings group can be applied.
- Containment models `PropagationDistance` (the sample-to-detector rail, `2bmbAERO:m1`) as carrying the `Housing` (`DetectorTable -> PropagationDistance -> Housing`), on the engineering assumption that moving the rail travels the whole detector. Whether the entire microscope rides the rail, or only part of it moves while the rest stays on the table, is the open world-fact [DET-12](../questions.md#the-microscope-detector); a staff answer that contradicts it would flip the rail back to a housing constituent.

## Exercised model

The end-to-end model lives in `apps/api/tests/integration/scenarios/test_2bm_microscope_setup.py`: the Housing containment tree, the `Optics` sub-assembly, the `Microscope` Assembly presenting the `Detector` Role, the one Fixture binding eight Assets across six slots, the alternate 31 MP camera and its selector registered as Housing Assets outside the Fixture, and the objective-selector lookup, end to end against Postgres.
