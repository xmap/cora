# The Microscope detector at 2-BM

*The Optique Peter detector deployment: a Microscope Assembly over a reusable Optics sub-assembly, materialized as one Fixture binding eight Assets, all contained in one Housing, with four Calibrations.*

The Microscope detector sits about 55 m from the source in the 2-BM experiment hutch. Its Assets are located in the `2-BM-B` Enclosure (the access-gated volume that gates them via the pre-flight permit check). It is the operator-facing imaging system: a vendor housing that carries three swappable microscope objectives on a sliding ball-screw selector, a linear focus stage, a FLIR Oryx scientific camera, and a LuAG scintillator. (Two Oryx cameras and a camera selector are physically installed, confirmed on the [2-BM beamline components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html); the v1 model below binds the one camera, with the second camera plus its Schunk selector recorded as a follow-on. See [Watch items](#watch-items).) The whole unit is controlled by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py) (MCTOptics is the IOC's process name, not the CORA model name). This page explains how CORA models it.

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
<li><span class="node">materializes Assembly = Microscope</span>
<ul>
<li><span class="node">sub-assembly optics</span> <span class="rel">&rarr; Assembly = Optics (content-hash pinned)</span></li>
<li><span class="node">leaf slot camera</span> <span class="rel">&rarr; Camera</span></li>
<li><span class="node">leaf slot scintillator</span> <span class="rel">&rarr; Scintillator</span></li>
</ul>
</li>
<li><span class="node">Optics sub-assembly slots</span> <span class="meta">bound in this Fixture</span>
<ul>
<li><span class="node">turret</span> <span class="rel">&rarr; Turret</span></li>
<li><span class="node">objectives (1+)</span> <span class="rel">&rarr; Objective_10x, Objective_2x, Objective_1.1x</span></li>
<li><span class="node">focus</span> <span class="rel">&rarr; Focus</span></li>
<li><span class="node">objective_selector</span> <span class="rel">&rarr; Objective_Selector</span></li>
</ul>
</li>
</ul>
</li>
</ul>
</li>
</ul>
</div>

`Microscope` is the name of the top Assembly (the blueprint) and, with `microscope_at_2bm`, of the Fixture (the materialization at 2-BM). `Optics` is a reusable sub-assembly the Microscope composes. `Housing` is the physical container. None of the three is an operator-facing Asset row in its own right except the housing: the conceptual Microscope-the-thing IS the Assembly plus Fixture pair, the reusable optics cluster IS the Optics sub-assembly, and the physical chassis IS the `Housing` Asset that parents the eight functional constituents.

## Two axes: composition and containment

This deployment uses both of CORA's structural axes, and they answer different questions.

- **Composition** (Assembly to Fixture, flat) answers *what logical cluster presents here for binding*. The Microscope Assembly composes the Optics sub-assembly plus two leaf slots (camera, scintillator). The Fixture binds the union of every leaf slot, the Microscope's own two plus the Optics sub-assembly's six, to eight concrete Assets.
- **Containment** (`Asset.parent_id`, a recursive tree) answers *what physical thing holds what*. The `Housing` Asset is the parent of all eight functional constituents. The housing is the part that is installed into the Mount; everything inside it inherits position from the housing's known internal layout. (The housing also physically holds a passive vitreous-carbon window, recorded in the descriptor but not yet registered as a CORA Asset.)

The same eight Assets sit on both axes at once: each is a Fixture-bound constituent (composition) and a child of the `Housing` (containment). The two axes are orthogonal, which is exactly why CORA keeps them separate.

## Vendor catalog (Models)

Five Models cover the hardware:

| Model | Manufacturer | Part number | Declared Families |
| --- | --- | --- | --- |
| `optique_peter_micrx080` | Optique Peter | `MICRX080` | `Housing` |
| `nanotec_st4118m1404_b` | Nanotec | `ST4118M1404-B` | `LinearStage` |
| `mitutoyo_plan_apo` | Mitutoyo | `Plan-Apo-NIR` | `Objective` |
| `flir_oryx` | FLIR | `ORX-10G-51S5M-C` | `Camera` |
| `crytur_luag` | Crytur | `LuAG:Ce-100um` | `Scintillator` |

Each Model carries the vendor identity that DOIs and citations need (PIDINST property 7). Assets bind to a Model at registration; the Asset's Family set must be a subset of the Model's declared families. The objective selector motor is a third-party stepper inside the Optique Peter housing, confirmed on the [2-BM beamline components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html) as a Nanotec `ST4118M1404-B` (with a Heidenhain ERO 1420 encoder), so the `Turret` Asset binds the Nanotec Model rather than an Optique Peter one.

One open vendor question worth confirming with the 2-BM operator before the catalog locks: Mitutoyo Plan Apo NIR is a product family with one part number per magnification (10x, 2x, 1.1x each carry distinct catalog numbers); folding all three into one Model row is a v1 simplification that splits into three rows once part numbers are verified.

## Assembly: Microscope

The top **Assembly** is the reusable composition blueprint. It does two things: it references the Optics sub-assembly by a version-pinned link, and it declares the leaf slots that are specific to a full detector (the parts that are not part of the reusable optics cluster).

| Member | Kind | Cardinality | Required Family |
| --- | --- | --- | --- |
| `optics` | sub-assembly link | one | (the Optics Assembly) |
| `camera` | leaf slot | `Exactly1` | `Camera` |
| `scintillator` | leaf slot | `Exactly1` | `Scintillator` |

The sub-assembly link pins the Optics Assembly's content hash, so a later revision of Optics does not silently change what a Microscope built today materializes (snapshot semantics). The camera and scintillator are leaf slots on the Microscope rather than the Optics sub-assembly because they are the parts a deployment swaps most often and the parts that vary between detector builds; the optics cluster (turret, objectives, objective selector, focus) is the stable, shareable core.

The Microscope Assembly presents the **`Detector`** Role through its `presents_as` set, the functional binding contract a Method targets when it needs a 2D imaging device without pinning a specific Family. The legacy scalar presenter field and the `Imager` presenter Family are both gone; `presents_as` is the sole presenter path. The Assembly's content hash (SHA-256 over its name, its slots, its sub-assembly links, the presented Roles (`presents_as`), and the parameter overrides schema) is stable: two facilities that publish the same Microscope Assembly converge on the same hash, which makes the blueprint cross-facility shareable when the federation layer lands.

The Microscope carries **zero `required_wires` in v1**. Earlier sketches modelled this detector as an Asset-with-ports that brokered routing between the turret, focus, and camera; the IOC played that role in real hardware. In CORA's model that brokering dissolves into three different surfaces: the PseudoAxis evaluator handles lens index to turret setpoint, the Conductor / ControlPort layer drives focus and other setpoints directly, and the camera trigger arrives from an external timing source (FPGA, encoder) that lives outside the cluster and is wired in at Plan level. None of these wires are intrinsic to the composition; they all depend on which Conductor, which trigger source, and which command path the deployment uses. The Assembly's value is the slot map plus the content hash.

## Sub-assembly: Optics

The **Optics** Assembly is the reusable core: the turret, the three objectives, the virtual objective selector, and the focus stage. It is content-hashed in its own right, so the same optics cluster can be referenced by more than one detector build (a second microscope at another station, a spare optics bench) without redeclaring its slot map.

| Slot | Cardinality | Required Family |
| --- | --- | --- |
| `turret` | `Exactly1` | `LinearStage` |
| `objectives` | `OneOrMore` | `Objective` |
| `objective_selector` | `Exactly1` | `PseudoAxis` |
| `focus` | `Exactly1` | `LinearStage` |

The three installed objectives (10x, 2x, 1.1x) all bind the single `objectives` slot. They differ only by the `magnification` setting, so one `OneOrMore` slot keeps the Optics blueprint (and its content hash) reusable across turret loadouts rather than baking three specific magnifications into the structure; a second beamline with a five-position turret reuses the same blueprint. Per-objective identity lives on the Asset (its name, settings, and calibration), not the slot. `objective_selector` is **the objective selector**: the virtual axis that picks which objective is in the beam (distinct from the separate, deferred camera selector).

The Optics sub-assembly is composed one level deep: it does not itself reference further sub-assemblies. At Fixture time, a Microscope expands one composing level, the Optics cluster, and rejects deeper nesting; that keeps the materialization rule simple until a real two-tier case earns the extra depth.

## Fixture: Microscope at 2-BM

The **Fixture** materializes the Microscope Assembly at this specific facility. It records:

- The Assembly id and its content hash (frozen at registration so later Assembly revisions do not silently change this materialization)
- The Trust Surface (`2-BM`) for governance scope
- The slot-to-Asset map binding eight Assets across six leaf slots (the Microscope's `camera` and `scintillator`, plus the Optics sub-assembly's `turret`, `objectives` [the three magnification objectives], `objective_selector`, and `focus`) to the eight specific Asset IDs above
- Parameter overrides, if any (none in v1)

When the Fixture is registered, the decider expands the union of the top Assembly's leaf slots and the referenced Optics sub-assembly's leaf slots into one flat slot namespace, then validates the bindings against that union. A leaf slot name that appeared in both blueprints would be rejected as a namespace collision; here the two sets are disjoint.

A Fixture is single-event genesis: it never changes after registration. Each of the eight bound Assets carries a `fixture_id` back-reference. Operators do not see this field directly; it is a query helper so "which Fixture is this Asset bound into" answers in one lookup.

The exclusivity invariant matters: an Asset can only belong to one Fixture at a time. `Focus` is bound into the Microscope Fixture, which means it cannot simultaneously be bound into a different Fixture for, say, a non-microscope imaging path. If a future deployment needs the same physical focus motor for a different cluster, the operator detaches it first.

## Physical placement and containment (Housing + Mount + Frame)

The **2BM_hutch_frame** is a named coordinate frame anchored to the hutch's optical table. The **optics_mount** is a named slot on that frame with a 6-DoF placement (translation in mm, rotation in degrees, extrinsic Tait-Bryan).

The `Housing` Asset is installed into this Mount. It is the rigid mechanical anchor for the whole detector: the housing's position fixes the cluster in space, and the eight functional constituents, which are its children in the containment tree, inherit their position geometrically from the housing's known internal layout. The housing is the one part with an explicit placement; the constituents do not each carry a Mount.

This is a documented approximation. The constituents have their own internal offsets that the model does not yet pin per-part. For tomography reconstruction (where the rotation center is calibrated separately) the approximation is comfortable. If a future use case needs pixel-accurate beam-propagation modelling, the escape valve is to give the constituents their own Mounts referenced to the housing's frame. Not in v1.

Where the axes meet: the Fixture answers "what logical cluster lives here for governance," the Mount answers "where in space the housing sits," and the containment tree answers "what the housing physically holds." Three orthogonal questions. The Fixture has no placement of its own; only Assets do, via the Mounts they are installed into, and at 2-BM only the housing is mounted.

## Routing the objective selector (PseudoAxis)

`Objective_Selector` is a virtual axis inside the Optics sub-assembly. Its **partition rule** is a closed `LookupTable` decomposing an integer index (0, 1, 2) into a turret position in millimeters (the selector is a sliding ball-screw stage, not a rotating turret):

| `Objective_Selector` | Turret position | Objective in beam |
| --- | --- | --- |
| `0` | `-60.030 mm` | 1.1x Mitutoyo |
| `1` | `-0.837 mm` | 2x Mitutoyo |
| `2` | `58.640 mm` | 10x Mitutoyo |

When an operator or Method writes `Objective_Selector = 1`, CORA's command-execution layer looks up the partition rule and writes the corresponding turret setpoint to the `Turret` motor. Every actuation is recorded as a control-dispatch event with a correlation id linking back to the originating partition-rule resolution, so the full chain (operator command, virtual-axis lookup, constituent setpoint) is reconstructable from the event log. The lookup table itself is event-sourced; revising it (for example, after a turret re-homing campaign) leaves a complete audit trail of which values were in effect at which times.

This replaces the older convention of carrying `Objective_Selector` as a Method parameter. The virtual axis is addressable, typed, and audit-complete.

## Calibrations

Four Calibrations downstream of this deployment, shown against their device on the [Layout](../beamline.md):

- Three `magnification` revisions, one per objective (9.83x / ~2x / 1.10x effective, derived from measured pixel size divided by sensor pitch; the 2x figure is nominal, pending re-measurement)
- One `effective_thickness` revision on the LuAG scintillator (100 micrometers)

All initial revisions are `AssertedSource` (operator-attested from vendor datasheets) with status `Provisional`. They get superseded by `MeasuredSource` revisions when the corresponding characterization Procedure runs.

## Engineering drawings

Four carriers hold a canonical engineering reference under the [Drawing VO](../../../architecture/modules/equipment/index.md): the Microscope Assembly (top composition blueprint), the `Housing` Asset (the physical chassis), the Mount (where the housing sits in the beamline), and each bound constituent Asset (build-to document for the specimen). Per the VO's anti-hook, these drawings are NOT collapsed even when they happen to point at the same vendor document.

The Optique Peter MICRX080 manual covers the housing composition, the slot layout, and every physical constituent, so v1 attaches the same `(EDMS, MAN-11863, 0521-0465-A)` triple to the Microscope Assembly, the housing, and the Mount. When the per-magnification Mitutoyo datasheets land they take over the Objective Asset drawings; the Assembly, housing, and Mount stay on MAN-11863.

| Carrier | Field | Value |
| --- | --- | --- |
| Microscope Assembly | `system` | `EDMS` |
| | `number` | `MAN-11863` |
| | `revision` | `0521-0465-A` |
| `Housing` (Asset) | `system` | `EDMS` |
| | `number` | `MAN-11863` |
| | `revision` | `0521-0465-A` |
| `optics_mount` (Mount) | `system` | `EDMS` |
| | `number` | `MAN-11863` |
| | `revision` | `0521-0465-A` |

Per-Asset drawings for the bound physical constituents are listed on the [Engineering drawings section](../assets.md#engineering-drawings) of the flat inventory. Vendor-tier drawings (per-magnification Mitutoyo datasheets, FLIR Oryx datasheet for the camera) are pending operator confirmation of part numbers.

## PIDINST citation

Two tiers of persistent identifiers:

- **The Fixture earns one DOI** as a citable experimental station. This mirrors the HZB PEAXIS precedent where the composite imaging station is published as a single Instrument with `HasComponent` relations to its parts.
- **Each physical bound Asset earns its own DOI**, plus the `Housing` chassis: the housing, the three Objectives, the Oryx camera, the LuAG scintillator, and the lens turret motor. The Fixture's PIDINST record references the constituents via `HasComponent`; each Asset's record references the Fixture via `IsComponentOf`.

`Objective_Selector` is intentionally NOT PIDINST-minted. PIDINST v1.0 requires a Manufacturer (Property 6) and Owner (Property 5), both of which assume a physical instrument with a vendor and an institutional steward. Virtual axes are software routing constructs over a real motor: they carry no Manufacturer (there is no vendor of LookupTables), no independent Owner, and no serial number. The lens index to turret position table is event-sourced via the partition rule and is fully audit-complete without a DOI; if a citation handle is ever needed it lives on the turret motor's DOI, not on the virtual axis. `GET /assets/{objective_selector_id}/pidinst` returns 404 (not applicable) by design.

For pilot v1, persistent identifiers are stub-minted (no real DOIs registered with DataCite). The production mint path is deferred until 2-BM commissions with real facility DataCite credentials.

## Operator runbook

**Switch the active objective.** Write the desired `Objective_Selector` index (0, 1, or 2) to the `Objective_Selector` PseudoAxis. The execution layer looks up the turret position and writes it to the `Turret` motor via the ControlPort. The full chain is audited.

Removing or replacing the scintillator or camera splits into two ceremonies. The light one returns the same Asset to its slot; the heavy one brings in a different physical Asset. Pick by intent, not by reflex.

**Detach and re-attach the same Asset (light, reversible).** Detaching an Asset from its Fixture slot (`detach_asset_from_fixture`) and later re-attaching it (`attach_asset_to_fixture`) is the reversible ceremony: while detached the Asset stays in inventory at lifecycle `Active` with its `fixture_id` cleared, and re-attaching creates no new aggregates. This works because the original Asset is in the Fixture's frozen `slot_asset_bindings`. It is the path for temporarily pulling a detector for cleaning or recalibration and putting the same one back.

**On-the-shelf state.** An Asset at lifecycle `Active` with `fixture_id = None` is the valid "in inventory, not currently mounted" state. There is no dedicated status word for it; the absence of a `fixture_id` IS the signal. This is the resting state of any detector that has been detached from one Fixture and not yet attached to another. The Asset stays fully addressable, its ports persist, and it can be re-attached to a Fixture slot it was originally declared in.

**Bring in a different Asset, or retire one (heavy).** A Fixture's slot bindings are frozen at genesis, and the `camera` and `scintillator` slots are `Exactly1`, so a substitute that was not bound at registration cannot simply be attached to the slot. Swapping in a different physical detector (a new camera, a fresh scintillator), or retiring one that leaves the facility for good (broken, end-of-life, returned to vendor), is therefore the heavier ceremony. The shape: decommission the old Asset (terminal lifecycle transition) if it is leaving, register the replacement (with its own Model binding), then register a NEW Fixture against the same Assembly with the updated slot map, then detach the surviving Assets from the old Fixture and attach them to the new one. A `rebind_fixture_slot` helper slice would collapse the per-slot churn to two or three commands; it is a watch-item that earns its keep at the second routine retirement.

**Plan rewiring across a swap.** Methods reference the Microscope Assembly (via `needed_assembly_ids`), not the specific Fixture or its bound Assets. A Plan that binds at Assembly level is unaffected by either ceremony. Plans that explicitly enumerate `asset_ids` need their list updated whenever the bound Asset id changes: never for an exchange between pre-declared siblings (the Asset ids do not change), always for a retirement (the new Asset has a new id).

## Watch items

A few model questions this deployment surfaces but does not pin down:

- The PseudoAxis slot constrains the Family but not the structural relationship between the PseudoAxis Asset's `partition_rule` and the `turret` slot. Today the rule references the lens turret motor by Asset id; neither the Optics sub-assembly nor the Microscope enforces that the referenced motor is the one bound into the `turret` slot. A future Assembly-level cross-slot constraint primitive could close this.
- Per-constituent placement is approximated by the housing's single Mount. The escape valve (one Mount per constituent, referenced to the housing's frame) is available if a use case needs pixel-accurate geometry. Note that `register_fixture` requires every bound constituent to be installed in some Mount; a pool-backed deployment therefore gives each constituent a lightweight Mount even though its spatial placement is approximated by the housing.
- Method-level binding validation does not yet enforce `needed_assembly_ids` satisfaction at Plan-binding time. A Plan that fails to include a Fixture materializing the required Assembly today passes silently; a future Plan-binding extension would catch this.
- Two cameras are physically installed (the FLIR Oryx 5 MP at `2bmSP1:` and a FLIR Oryx 31 MP at `2bmSP2:`), switched by a Schunk LPTM 30 selector (`2bmb:m5`) with per-camera rotation motors (`2bmb:m7`/`m8`), all confirmed on the [2-BM beamline components page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html). The v1 model binds the one camera through the Microscope's `camera` leaf slot. Modelling the second camera (likely a `camera` slot that becomes `OneOrMore` plus a camera-selector PseudoAxis and the Schunk selector + rotation stages) is a follow-on slice; the devices are recorded in the [descriptor](../../../../deployments/2-bm/beamline.yaml) with `new: true` today.

## See also

- [2-BM Assets](../assets.md) for the flat inventory listing the underlying Asset rows
- [2-BM Layout](../beamline.md) for the four downstream Calibration revisions, shown on their device
- [2-BM Enclosures](../enclosures.md) for the hutch permit that gates Runs and Procedures binding these Assets: these Assets are located in the `2-BM-B` Enclosure, which gates them through the located-in pre-flight chain walk
- [Equipment module](../../../architecture/modules/equipment/index.md) for the aggregate shapes (Family, Model, Asset, Mount, Frame, Assembly, Fixture)

The deployment scenario test at `apps/api/tests/integration/scenarios/test_2bm_microscope_setup.py` exercises the Microscope + Optics + Housing model described here, end-to-end against Postgres.
