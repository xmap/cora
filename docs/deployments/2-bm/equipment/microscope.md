# The Microscope detector at 2-BM

*The Optique Peter detector: a `Microscope` Assembly over a reusable `Optics` sub-assembly, materialized as one Fixture binding eight Assets, all contained in one `Housing`, presenting the `Detector` Role.*

The Microscope detector sits about 55 m from the source in the 2-BM experiment hutch (Enclosure `2-BM-B`). It is the operator-facing imaging system: a vendor housing carrying three swappable objectives on a sliding ball-screw selector, a linear focus stage, a FLIR Oryx camera, and a LuAG scintillator. (A second Oryx camera and its selector are installed but not yet modelled; see [Open items](#open-items).) The whole unit is driven by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py) (MCTOptics is the IOC process name, not the CORA model name). This page explains how CORA models it.

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
<li><span class="node">Housing</span> <span class="meta">Component, Family Housing</span> <span class="rel">containment parent (Asset.parent_id)</span>
<ul>
<li><span class="node">Turret</span> <span class="meta">Device, LinearStage, sliding ball-screw objective selector</span></li>
<li><span class="node">Objective_10x</span> <span class="meta">Device, Objective, 10x</span></li>
<li><span class="node">Objective_2x</span> <span class="meta">Device, Objective, 2x</span></li>
<li><span class="node">Objective_1.1x</span> <span class="meta">Device, Objective, 1.1x</span></li>
<li><span class="node">Objective_Selector</span> <span class="meta">Device, PseudoAxis</span></li>
<li><span class="node">Focus</span> <span class="meta">Device, LinearStage</span></li>
<li><span class="node">Camera</span> <span class="meta">Device, Camera</span></li>
<li><span class="node">Scintillator</span> <span class="meta">Device, Scintillator</span></li>
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
<li><span class="node">focus</span> <span class="meta">Exactly1</span> <span class="rel">&rarr; Focus</span></li>
<li><span class="node">objective_selector</span> <span class="meta">Exactly1</span> <span class="rel">&rarr; Objective_Selector</span></li>
</ul>
</li>
</ul>
</li>
</ul>
</li>
</ul>
</div>

`Microscope` is the Assembly (the blueprint) and, with `microscope_at_2bm`, the Fixture (the materialization). `Optics` is a reusable sub-assembly the Microscope composes. `Housing` is the physical chassis and the only operator-facing Asset row of the three; it parents the eight functional constituents.

## Two axes: composition and containment

Like the [sample tower](sample_tower.md), the detector uses both of CORA's structural axes.

- **Composition** (Assembly to Fixture, flat) answers *what logical cluster presents for binding*. The `Microscope` Assembly composes the `Optics` sub-assembly plus two leaf slots (`camera`, `scintillator`); the Fixture `microscope_at_2bm` binds eight Assets across six leaf slots on the 2-BM Trust Surface. The Assembly `presents_as` the `Detector` Role, so a Method can require a 2D imaging device without pinning a Family.
- **Containment** (`Asset.parent_id`) answers *what physically holds what*. Here it is shallow: the `Housing` parents all eight constituents. The housing is the one part installed into a Mount (`optics_mount` on `2BM_hutch_frame`, 6-DoF), and the constituents inherit position from its known internal layout. This is an approximation: tomography reconstruction calibrates the rotation center separately, so per-constituent Mounts are not pinned (pixel-accurate beam-propagation modelling would add them).

The two axes are orthogonal: the same eight Assets sit on both at once.

## Composition: blueprint in the Catalog, materialized here

The `Microscope` and its reusable `Optics` core are cross-facility composition blueprints, not 2-BM-specific: their slot maps, sub-assembly links, and content hashes live in the [Assemblies catalog](../../../catalog/assemblies.md). In summary, the Microscope presents the `Detector` Role and composes the `Optics` sub-assembly (turret, objectives, objective selector, focus) plus two leaf slots specific to a full detector, `camera` and `scintillator` (the parts a deployment swaps most often); the three objectives all bind the one `OneOrMore` objectives slot, differing only by `magnification`. This page covers how 2-BM materializes that blueprint.

The Fixture `microscope_at_2bm` binds eight Assets across six leaf slots on the 2-BM Trust Surface. It is single-event genesis (it never changes after registration), each bound Asset carries a `fixture_id` back-reference, and an Asset belongs to only one Fixture at a time.

The Microscope carries **zero `required_wires`**: lens-index-to-turret routing is the `Objective_Selector` PseudoAxis (below), focus and other setpoints go through the Conductor / ControlPort layer, and the camera trigger arrives from an external timing source wired at Plan level. None of these is intrinsic to the composition, so none is a blueprint wire.

## Vendor catalog (Models)

| Model | Manufacturer | Part number | Declared Families |
| --- | --- | --- | --- |
| `optique_peter_micrx080` | Optique Peter | `MICRX080` | `Housing` |
| `nanotec_st4118m1404_b` | Nanotec | `ST4118M1404-B` | `LinearStage` |
| `mitutoyo_plan_apo` | Mitutoyo | `Plan-Apo-NIR` | `Objective` |
| `flir_oryx` | FLIR | `ORX-10G-51S5M-C` | `Camera` |
| `crytur_luag` | Crytur | `LuAG:Ce-100um` | `Scintillator` |

Each Model carries the vendor identity PIDINST needs (Manufacturer + Model). The `Turret` binds the Nanotec Model because the objective-selector motor is a third-party stepper (Nanotec `ST4118M1404-B` with a Heidenhain ERO 1420 encoder) inside the Optique Peter housing, confirmed on the [components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). Mitutoyo Plan Apo NIR carries one part number per magnification, so the single `mitutoyo_plan_apo` row splits into three once those numbers are confirmed.

## Objective selector

`Objective_Selector` is a virtual axis. Its `partition_rule` is a closed `LookupTable` mapping an integer index to a turret position in millimeters (the selector is a sliding ball-screw stage, not a rotating turret):

| `Objective_Selector` | Turret position | Objective in beam |
| --- | --- | --- |
| `0` | `-60.030 mm` | 1.1x Mitutoyo |
| `1` | `-0.837 mm` | 2x Mitutoyo |
| `2` | `58.640 mm` | 10x Mitutoyo |

Writing `Objective_Selector = 1` makes the command layer look up the rule and write the turret setpoint to `Turret`. Every actuation is recorded as a control-dispatch event with a correlation id, and the lookup table is itself event-sourced, so revisions leave an audit trail.

## Families

- **`Turret` is a `LinearStage`**, not a `RotaryStage`: the selector is a sliding ball-screw stage, so positions are in millimeters and constituent-wiring signal types are `linear_mm`.
- **`Objective`** declares per-lens identity only (`magnification`, `numerical_aperture`, `focal_length`, `working_distance`); motion is via the turret stage.
- **`Housing`, `Camera`, `Scintillator`, `LinearStage`, `PseudoAxis`** are reused unchanged.

## Calibration, drawings, and citation

- **Calibrations (4):** three `magnification` revisions (9.83x / ~2x / 1.10x effective; the 2x figure is nominal, pending re-measurement) and one `effective_thickness` on the LuAG scintillator (100 micrometers). All start `AssertedSource` / `Provisional` and are superseded by `MeasuredSource` revisions when the characterization Procedure runs.
- **Drawings:** the Optique Peter MICRX080 manual `(EDMS, MAN-11863, 0521-0465-A)` is the canonical reference for the Assembly, Housing, and Mount; per-Asset drawings are listed on the [Assets inventory](../assets.md#engineering-drawings).
- **PIDINST:** the Fixture earns one DOI as a citable station (HZB PEAXIS precedent), and each physical Asset plus the Housing earns its own, linked via `HasComponent` / `IsComponentOf`. `Objective_Selector` is not minted (a virtual axis has no Manufacturer or Owner). DOIs are stub-minted until 2-BM has facility DataCite credentials.

## Operating and swapping

Switch the active objective by writing the `Objective_Selector` index (0/1/2); the execution layer resolves the turret position and drives `Turret`. Pulling a detector for cleaning or recalibration and returning the same one is the light, reversible path (`detach_asset_from_fixture` then `attach_asset_to_fixture`; the Asset stays `Active` with `fixture_id` cleared). Bringing in a *different* camera or scintillator, or retiring one, is heavier: decommission the old Asset if it is leaving, register the replacement, register a new Fixture against the same Assembly with the updated slot map, then move the surviving Assets across. Methods that bind at Assembly level (`needed_assembly_ids`) are unaffected; Plans that enumerate `asset_ids` need the new id only on a retirement.

## Open items

- The `Objective_Selector` `partition_rule` references the turret motor by Asset id, but nothing enforces that this is the same motor bound into the `turret` slot; there is no cross-slot constraint primitive today.
- `register_fixture` requires every bound constituent to be installed in some Mount, so a pool-backed deployment gives each a lightweight Mount even though the housing approximates its placement.
- Plan-binding does not yet enforce `needed_assembly_ids` satisfaction: a Plan that omits a Fixture materializing the required Assembly passes silently today.
- Two cameras are installed (FLIR Oryx 5 MP at `2bmSP1:`, 31 MP at `2bmSP2:`), switched by a Schunk LPTM 30 selector (`2bmb:m5`) with rotation motors (`2bmb:m7`/`m8`); the v1 model binds the one camera, and the second camera plus selector is a follow-on recorded in the [descriptor](../../../../deployments/2-bm/beamline.yaml) with `new: true`.

## Exercised model

The end-to-end model lives in `apps/api/tests/integration/scenarios/test_2bm_microscope_setup.py`: the Housing containment tree, the `Optics` sub-assembly, the `Microscope` Assembly presenting the `Detector` Role, the one Fixture binding eight Assets across six slots, and the objective-selector lookup, end to end against Postgres.
