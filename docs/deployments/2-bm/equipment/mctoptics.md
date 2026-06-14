# MCTOptics at 2-BM

*The Optique Peter detector deployment: one Assembly, one Fixture, eight bound Assets, four Calibrations.*

The MCTOptics detector sits about 55 m from the source in the 2-BM experiment hutch. Its Assets are located in the `2-BM-B` Enclosure (the access-gated volume that gates them via the pre-flight permit check). It is the operator-facing imaging system: a vendor housing that carries three swappable microscope objectives on a turret, a linear focus stage, a single Oryx scientific camera, and a LuAG scintillator. The whole unit is controlled by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py). This page explains how CORA models it.

## The model in one picture

```
2-BM (Unit, Asset)
|
+-- Frame: 2BM_hutch_frame
|     |
|     +-- Mount: optics_mount   ----holds---->   MCTOptics_lens_turret
|                (6-DoF placement)               (same Asset as the lens_turret slot below;
|                                                 acts as the rigid mechanical anchor for the housing)
|
+-- Fixture: mctoptics_at_2bm   (surface_id = 2-BM Trust Surface)
      materializes Assembly = MCTOptics
      binds 8 slots:
        objective_0   -> MCTOptics_objective_0   (Asset, Family Objective)
        objective_1   -> MCTOptics_objective_1   (Asset, Family Objective)
        objective_2   -> MCTOptics_objective_2   (Asset, Family Objective)
        camera        -> Camera         (Asset, Family Camera)
        scintillator  -> Scintillator       (Asset, Family Scintillator)
        lens_turret   -> MCTOptics_lens_turret   (Asset, Family RotaryStage)
        focus         -> Focus   (Asset, Family LinearStage)
        lens_select   -> MCTOptics_lens_select   (Asset, Family PseudoAxis;
                                                   partition_rule = LookupTable
                                                     0 -> 121.5942 deg  (10x in beam)
                                                     1 ->  61.9841 deg  (2x  in beam)
                                                     2 ->   2.3006 deg  (1.1x in beam))
```

Note that `MCTOptics` is the name of the Assembly (the blueprint) and the Fixture (the materialization at 2-BM). It is NOT an Asset row in its own right. The conceptual MCTOptics-the-thing IS the Assembly plus Fixture pair; the physical instance is the eight bound Assets. Seven aggregates participate in the deployment: Assembly, Fixture, Asset, Mount, Frame, Model, Family. The deployment uses all of them.

## Vendor catalog (Models)

Four Models cover the hardware:

| Model | Manufacturer | Part number | Declared Families |
| --- | --- | --- | --- |
| `optique_peter_lens_turret_motor` | Optique Peter | `TripleObj-MCT-turret` | `RotaryStage` |
| `mitutoyo_plan_apo_nir` | Mitutoyo | `Plan-Apo-NIR` | `Objective` |
| `flir_oryx_orx_10g_51s5m_c` | FLIR | `ORX-10G-51S5M-C` | `Camera` |
| `crytur_luag_ce_100um` | Crytur | `LuAG:Ce-100um` | `Scintillator` |

Each Model carries the vendor identity that DOIs and citations need (PIDINST property 7). Assets bind to a Model at registration; the Asset's Family set must be a subset of the Model's declared families.

Two open vendor questions worth confirming with the 2-BM operator before the catalog locks. First, the Optique Peter Triple Objective ships with a turret motor whose underlying vendor may differ from Optique Peter (system integrators often source motors from third parties). Second, Mitutoyo Plan Apo NIR is a product family with one part number per magnification (10x, 2x, 1.1x each carry distinct catalog numbers); folding all three into one Model row is a v1 simplification that splits into three rows once part numbers are verified.

## Assembly: MCTOptics

The **Assembly** is the reusable composition blueprint. It declares the slot map (eight typed slots) and the Family the cluster presents as for binding purposes.

| Slot | Cardinality | Required Family |
| --- | --- | --- |
| `objective_0` | `Exactly1` | `Objective` |
| `objective_1` | `Exactly1` | `Objective` |
| `objective_2` | `Exactly1` | `Objective` |
| `camera` | `Exactly1` | `Camera` |
| `scintillator` | `Exactly1` | `Scintillator` |
| `lens_turret` | `Exactly1` | `RotaryStage` |
| `focus` | `Exactly1` | `LinearStage` |
| `lens_select` | `Exactly1` | `PseudoAxis` |

The Assembly carries **zero `required_wires` in v1**. Earlier sketches of this composition modelled MCTOptics as an Asset-with-ports that brokered routing between the turret, focus, and camera; the IOC played that role in real hardware. In CORA's new model, that brokering role dissolves into three different surfaces: the PseudoAxis evaluator handles lens index to turret setpoint, the Conductor / ControlPort layer drives focus and other setpoints directly, and the camera trigger arrives from an external timing source (FPGA, encoder) that lives outside the MCTOptics cluster and is wired in at Plan level. None of these wires are intrinsic to MCTOptics-the-composition; they all depend on which Conductor, which trigger source, and which command path the deployment uses. The Assembly's value is the slot map alone, plus the content hash that makes the blueprint cross-facility shareable.

`presents_as_family_id` points at **`Imager`**, a general presenter Family the Assembly satisfies for any Method that declares `needed_family_ids = {Imager}`. (The Family was named `ImagingDetector` before the role-aggregate-design rename.) The Assembly's content hash (SHA-256 over slots + presented Family + parameter overrides schema) is stable: two facilities that publish the same MCTOptics Assembly converge on the same hash because the Family ids it folds in (the presented Family plus each slot's required Family) are deterministic `uuid5`-over-name, which makes the blueprint cross-facility shareable when the federation layer lands.

## Fixture: MCTOptics at 2-BM

The **Fixture** materializes the Assembly at this specific facility. It records:

- The Assembly id and its content hash (frozen at registration so later Assembly revisions do not silently change this materialization)
- The Trust Surface (`2-BM`) for governance scope
- The slot-to-Asset map binding the 8 named slots to the 8 specific Asset IDs above
- Parameter overrides, if any (none in v1)

A Fixture is single-event genesis: it never changes after registration. Each of the 8 bound Assets carries a `fixture_id` back-reference. Operators do not see this field directly; it is a query helper so "which Fixture is this Asset bound into" answers in one lookup.

The exclusivity invariant matters: an Asset can only belong to one Fixture at a time. `Focus` is bound into the MCTOptics Fixture, which means it cannot simultaneously be bound into a different Fixture for, say, a non-MCTOptics imaging path. If a future deployment needs the same physical focus motor for a different cluster, the operator detaches it from MCTOptics first.

## Physical placement (Mount + Frame)

The **2BM_hutch_frame** is a named coordinate frame anchored to the hutch's optical table. The **optics_mount** is a named slot on that frame with a 6-DoF placement (translation in mm, rotation in degrees, extrinsic Tait-Bryan). The `MCTOptics_lens_turret` motor is installed into this Mount as the rigid mechanical anchor for the housing: the motor body's position fixes the housing in space, and the objectives, camera, scintillator, and focus stage inherit their position geometrically from the housing's known internal layout.

This is a documented approximation. The motor body is not exactly at the housing's geometric center, and the other constituents have their own internal offsets. For tomography reconstruction (where the rotation center is calibrated separately) the approximation is comfortable. If a future use case needs pixel-accurate beam-propagation modelling, the escape valve is to register a dedicated `MCTOptics_housing` Asset (of a new Family `OpticalHousing`) whose only job is to carry the Mount; the constituents would then get their own Mounts referenced to the housing's frame. Not in v1.

Where Fixture and Mount fit together: the Fixture answers "what logical cluster lives here for governance," the Mount answers "where in space does this Asset sit." Two orthogonal axes. The Fixture has no placement of its own; only Assets do, via the Mounts they are installed into.

## Routing the lens selector (PseudoAxis)

`MCTOptics_lens_select` is a virtual axis. Its **partition rule** is a closed `LookupTable` decomposing an integer index (0, 1, 2) into a turret rotation in degrees:

| `lens_select` | Turret position | Objective in beam |
| --- | --- | --- |
| `0` | `121.5942 deg` | 10x Mitutoyo |
| `1` | `61.9841 deg` | 2x Mitutoyo |
| `2` | `2.3006 deg` | 1.1x Mitutoyo |

When an operator or Method writes `lens_select = 1`, CORA's command-execution layer looks up the partition rule and writes the corresponding turret setpoint to the `MCTOptics_lens_turret` motor. Every actuation is recorded as a control-dispatch event with a correlation id linking back to the originating partition-rule resolution, so the full chain (operator command, virtual-axis lookup, constituent setpoint) is reconstructable from the event log. The lookup table itself is event-sourced; revising it (for example, after a turret re-homing campaign) leaves a complete audit trail of which values were in effect at which times.

This replaces the older convention of carrying `lens_select` as a Method parameter. The virtual axis is addressable, typed, and audit-complete.

## Calibrations

Four Calibrations downstream of this deployment, shown against their device on the [Layout](../beamline.md):

- Three `magnification` revisions, one per objective (9.83x / ~2x / 1.10x effective, derived from measured pixel size divided by sensor pitch; the 2x figure is nominal, pending re-measurement)
- One `effective_thickness` revision on the LuAG scintillator (100 micrometers)

All initial revisions are `AssertedSource` (operator-attested from vendor datasheets) with status `Provisional`. They get superseded by `MeasuredSource` revisions when the corresponding calibration Procedure runs.

## Engineering drawings

Three carriers hold a canonical engineering reference under the [Drawing VO](../../../architecture/modules/equipment/index.md): the Assembly (composition blueprint), the Mount (where the slot lives in the beamline), and each bound Asset (build-to document for the specimen). Per the VO's anti-hook, Assembly / Mount / Asset drawings are NOT collapsed even when they happen to point at the same vendor document.

The Optique Peter MICRX080 manual covers the housing composition, the slot layout, and every physical constituent, so v1 attaches the same `(EDMS, MAN-11863, 0521-0465-A)` triple to all three carriers. When the per-magnification Mitutoyo datasheets land they take over the Objective Asset drawings; the Assembly and Mount stay on MAN-11863.

| Carrier | Field | Value |
| --- | --- | --- |
| MCTOptics Assembly | `system` | `EDMS` |
| | `number` | `MAN-11863` |
| | `revision` | `0521-0465-A` |
| `optics_mount` (Mount) | `system` | `EDMS` |
| | `number` | `MAN-11863` |
| | `revision` | `0521-0465-A` |

Per-Asset drawings for the seven bound physical Assets are listed on the [Engineering drawings section](../assets.md#engineering-drawings) of the flat inventory. Vendor-tier drawings (per-magnification Mitutoyo datasheets, FLIR Oryx datasheet for the camera) are pending operator confirmation of part numbers.

## PIDINST citation

Two tiers of persistent identifiers:

- **The Fixture earns one DOI** as a citable experimental station. This mirrors the HZB PEAXIS precedent where the composite imaging station is published as a single Instrument with `HasComponent` relations to its parts.
- **Each physical bound Asset earns its own DOI** (the seven physical Assets: three Objectives, the Oryx camera, the LuAG scintillator, the lens turret motor, and the Optique Peter focus stage). The Fixture's PIDINST record references them via `HasComponent`; each Asset's record references the Fixture via `IsComponentOf`.

`MCTOptics_lens_select` is intentionally NOT PIDINST-minted. PIDINST v1.0 requires a Manufacturer (Property 6) and Owner (Property 5), both of which assume a physical instrument with a vendor and an institutional steward. Virtual axes are software routing constructs over a real motor: they carry no Manufacturer (there is no vendor of LookupTables), no independent Owner, and no serial number. The lens index to turret angle table is event-sourced via the partition rule and is fully audit-complete without a DOI; if a citation handle is ever needed it lives on the lens turret motor's DOI, not on the virtual axis. `GET /assets/{lens_select_id}/pidinst` returns 404 (not applicable) by design.

For pilot v1, persistent identifiers are stub-minted (no real DOIs registered with DataCite). The production mint path is deferred until 2-BM commissions with real facility DataCite credentials.

## Operator runbook

**Switch the active objective.** Write the desired `lens_select` index (0, 1, or 2) to the `MCTOptics_lens_select` PseudoAxis. The execution layer looks up the turret position and writes it via the ControlPort. The full chain is audited.

Replacing the scintillator or camera splits into two genuinely different ceremonies depending on whether the detached Asset goes back on the shelf or leaves the facility for good. Both shapes are supported today; pick by intent, not by reflex.

**Exchange detector (routine, reversible).** When the swap is "use a different camera or scintillator for this experiment, the old one goes back on the shelf," the ceremony is light. Detach the current Asset from its Fixture slot (`detach_asset_from_fixture`), then attach the substitute Asset to the same slot (`attach_asset_to_fixture`). Both Assets stay in inventory at lifecycle `Active`; the one that was detached just has its `fixture_id` cleared. Re-attaching the original later is the same two commands in reverse, no new aggregates created. The constraint to be aware of: both Assets must have been declared in the Fixture's `slot_asset_bindings` at Fixture registration. If the substitute was not pre-declared at registration time, the only path today is "retire detector" below.

**On-the-shelf state.** An Asset at lifecycle `Active` with `fixture_id = None` is the valid "in inventory, not currently mounted" state. There is no dedicated status word for it; the absence of a `fixture_id` IS the signal. This is the resting state of any detector that has been detached from one Fixture and not yet attached to another. The Asset stays fully addressable, its ports persist, and it can be re-attached to a Fixture slot it was originally declared in.

**Retire detector (terminal, heavy).** When the swap is "this detector leaves the facility forever (broken, end-of-life, returned to vendor)," the ceremony is the full 15-command one. The shape: decommission the old Asset (terminal lifecycle transition), register the replacement (with its own Model binding), then register a NEW Fixture against the same Assembly with the updated slot map, then detach the surviving Assets from the old Fixture and attach them to the new one. A `rebind_fixture_slot` helper slice would collapse the per-slot churn to two or three commands; it is a watch-item that earns its keep at the second routine retirement.

**Plan rewiring across a swap.** Methods reference the MCTOptics Assembly (via `needed_assembly_ids`), not the specific Fixture or its bound Assets. A Plan that binds at Assembly level is unaffected by either ceremony. Plans that explicitly enumerate `asset_ids` need their list updated whenever the bound Asset id changes: never for an exchange between pre-declared siblings (the Asset ids do not change), always for a retirement (the new Asset has a new id).

## Watch items

A few model questions this deployment surfaces but does not pin down:

- The PseudoAxis slot constrains the Family but not the structural relationship between the PseudoAxis Asset's `partition_rule` and the `lens_turret` slot. Today the rule references the lens turret motor by Asset id; the Assembly does not enforce that the referenced motor is the one bound into the `lens_turret` slot. A future Assembly-level cross-slot constraint primitive could close this.
- The lens turret motor doubles as the housing's mechanical anchor. The model honestly says "one Asset, two roles"; a separate `OpticalHousing` Asset is the principled escape valve for finer-grained placement.
- Method-level binding validation does not yet enforce `needed_assembly_ids` satisfaction at Plan-binding time. A Plan that fails to include a Fixture materializing the required Assembly today passes silently; a future Plan-binding extension would catch this.

## See also

- [2-BM Assets](../assets.md) for the flat inventory listing the underlying Asset rows
- [2-BM Layout](../beamline.md) for the four downstream Calibration revisions, shown on their device
- [2-BM Enclosures](../enclosures.md) for the hutch permit that gates Runs and Procedures binding these Assets: these Assets are located in the `2-BM-B` Enclosure, which gates them through the located-in pre-flight chain walk
- [Equipment module](../../../architecture/modules/equipment/index.md) for the aggregate shapes (Family, Model, Asset, Mount, Frame, Assembly, Fixture)

The deployment scenario test at `apps/api/tests/integration/scenarios/test_2bm_mctoptics_setup.py` currently exercises an earlier shape of this deployment (flat parent-child composition); it will be rewritten to match the Assembly + Fixture model described here.
