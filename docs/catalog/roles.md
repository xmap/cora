# Roles

*Equipment BC Roles. A Role is a global functional binding contract a Method authors against via `RoleRequirement.role_kind` (the federation-portable Layer 3 path; the slice-1 `family_id` path is the anatomical escape hatch). A Role names a CAPABILITY-SHAPED binding slot (e.g. "Imager", "Positioner") — Methods declare what the Plan must bind something to; Families and Assemblies advertise which Roles they satisfy via `presents_as`. The role_kind satisfaction check at `bind_plan_role` accepts iff (a) at least one Family on the Asset both declares the Role in its `presents_as` AND has `affordances` superset the Role's `required_affordances`, OR (b) the Asset is part of a materialized Assembly whose `presents_as` declares the Role. Roles are cross-facility vocabulary, not bound to any Site; deterministic uuid5 ids make a Method authored at APS 2-BM resolve to the same Role when shipped to MAX IV or DLS. See [Model](../architecture/model.md) for the aggregate shape and [Affordances](../reference/affordances.md) for the primitive-operation vocabulary.*

| Role | required_affordances | optional_affordances | Contract |
| --- | --- | --- | --- |
| `Imager` | `Imageable` | `Binnable`, `Coolable`, `Triggerable`, `Streamable` | Acquires 2D image frames on exposure or trigger. Satisfying Assets or composed Assemblies emit Image / Frame signals. Direct-detection Cameras and composed scintillator-relay Assemblies both satisfy this Role; the multi-Family disjunction accepts either path. |
| `Positioner` | `Homeable`, `Limitable` | `Rotatable`, `Translatable`, `Posable`, `Indexable`, `Capturable`, `Leading`, `Following` | Drives at least one degree of freedom to operator-commanded positions. Satisfying Families include LinearStage, RotaryStage, Hexapod, and indexable mechanisms. Single-axis and multi-axis Assets both satisfy; the contract is positioning capability, not axis count. |
| `Controller` | `Identifiable` | `Reportable`, `Pulsing` | Generates or routes signals (motion, timing) that govern subordinate Assets. Satisfying Families are the empty-Affordances `<Domain>Controller` leaves (MotionController, TimingController). The Controller does NOT itself perform motion / imaging; subordinate Assets do, under its supervision. |
| `Detector` | `Reportable` | `Triggerable`, `Streamable` | Reports a continuous or discrete measurement on query or trigger. Satisfying Families include ion chambers, photodiodes, thermocouples, and other point-sensor anatomies. Distinct from Imager: a Detector produces a scalar or short-vector Reading, not a 2D frame. |

Source of truth: [`_role_registry.py`](../../apps/api/src/cora/equipment/aggregates/role/_role_registry.py), seeded at lifespan via [`bootstrap_equipment`](../../apps/api/src/cora/equipment/_bootstrap.py).

## Closed-core set

The 4 Roles above ship as the closed-core seed registry. A fifth candidate — `Conditioner` (Attenuators / Shutters / Mirrors) — was deferred: no Affordance is universally required across those Families, so the required-set would be vacuous, degenerating the Role to a tag. A rule-of-three trigger gates a future definition: when three independent Method authors ask for the same conditioning-shaped binding slot, the Role lands.

## RoleId stability

Every `RoleId` is `uuid5(_ROLE_NAMESPACE, name.value.lower())` where `_ROLE_NAMESPACE = uuid5(NAMESPACE_DNS, 'cora.role')`. The case-insensitive lower-case key matches the projection's `UNIQUE INDEX (LOWER(name))`. A `define_role` POST with the same name as a seed Role (or any prior `define_role`) collides on the same stream and returns 409.

## Federation portability

Deterministic ids mean a Method authored at one facility binds against the same Role uuid at another. Operators verifying the namespace can recompute it from `uuid5(NAMESPACE_DNS, 'cora.role')` and the four seed ids from `uuid5(_ROLE_NAMESPACE, slug)` where `slug ∈ {"imager", "positioner", "controller", "detector"}`.
