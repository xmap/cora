---
date: 2026-06-19
slug: what-a-beamline-is-made-of
authors:
  - dgursoy
categories:
  - Architecture
tags:
  - equipment
  - assets
  - families
  - composition
  - inventory
links:
  - The Recipe Ladder: blog/posts/the-recipe-ladder.md
  - How CORA Remembers: blog/posts/how-cora-remembers.md
  - Equipment module: architecture/modules/equipment/index.md
  - Domain model: architecture/model.md
  - 2-BM assets: deployments/2-bm/assets.md
---

# What a Beamline Is Made Of: kinds, instances, and an inventory that stays honest

A photograph of a beamline looks like a fixed instrument. The reality is a population in slow motion. A detector is swapped for a better one. A stage is sent out for repair and a loaner takes its place. A mirror is recoated, a lens is recalibrated, a whole microscope is rebuilt around a new camera. Over a few years almost every part may change while everyone keeps calling it the same beamline. That is the old puzzle of the ship whose planks are replaced one by one: what makes it still the same thing? A system that means to record what a beamline did, for years, has to answer that puzzle first, because it cannot describe the work until it can faithfully name the equipment the work ran on.

<!-- more -->

An [earlier post](the-recipe-ladder.md) described the recipe ladder: how CORA models the work a beamline does, from a portable technique down to one run on one afternoon. This post is about the other half. A recipe is only meaningful against the hardware it runs on, so the equipment model is foundational: nearly every other part of CORA, a calibration, a plan, a safety zone, a procedure, ends up pointing at one specific piece of equipment. Getting that record right, and keeping it honest as the hardware changes, is what the equipment model is for.

## Kind and instance

The first move is to separate what a thing **is** from the particular thing in front of you. CORA models a beamline as a small ladder of identities, and the two rungs that matter most are the kind and the instance.

A **Family** is the device class, named for what it is and nothing more: `Camera`, `Mirror`, `Scintillator`, `Hexapod`, `RotaryStage`, `MotionController`. The names are deliberately anatomical and vendor-free. A `MotionController` Family covers an Aerotech drive, an older VME card, and a future servo board with equal honesty, because the vendor designation is not part of what the thing *is*. Family names are meant to be shared vocabulary across facilities, so two beamlines that both run a hexapod are speaking about the same kind even when the units differ.

An **Asset** is one physical instance the facility commissions, maintains, moves, and eventually retires: this detector, that sample stage, the HPC node in the rack. An Asset belongs to one or more Families at once, which is how a single box can be both, say, a `Camera` and something more specialized. Between the two sits an optional **Model**, the vendor catalog entry that pins a manufacturer and a part number to the Families that catalog row belongs to; an Asset can point at a Model to record exactly what it is on paper.

This is the answer to the ship-of-planks puzzle. The Asset is its own stream of events, with a stable identity that does not change when its Family memberships, its settings, or its parts do. The planks change; the stream is continuous. What the beamline *is* lives in the Family vocabulary; *which* beamline this is lives in the Asset.

## State that changes, and state that breaks

An instance is not static, and the interesting thing is that it carries two different kinds of changing state that are easy to confuse and important to keep apart.

The first is **lifecycle**: is this device part of the inventory, and is it available to be used? It moves through a small fixed set of states, Commissioned, Active, Maintenance, and finally Decommissioned, and the transitions are deliberate steps an operator takes. The second is **condition**: is the device actually working right now? Nominal, Degraded, or Faulted. The two are kept rigorously orthogonal, and that orthogonality is the point. An Active asset can be Faulted, broken but still owned and in service. A Decommissioned asset can be discovered Faulted on an inventory check months later, which is the honest thing to record about a dead unit sitting in storage. Collapsing the two into a single status would force a lie in one of those cases; keeping them apart lets the record stay true.

A third facet is the device's operational settings: the slow-changing parameters it runs at, such as a gap, an energy, an exposure, or a filter material. CORA keeps these honest with a simple division of labor. The Family declares a schema, a description of which settings a device of that kind may carry and what each one should look like. The Asset holds the actual values. Every time those values change, they are checked against that schema before they are accepted.

The split keeps the rules and the data in separate hands: the kind says what is allowed, the instance records what is set. A setting that no Family permits is turned away. And when an Asset belongs to two Families whose schemas disagree about the same setting, the clash is caught rather than quietly resolved. The boundary is enforced, not merely hoped for.

## What it is, and what it can do

Naming the kind of a device is not quite the same as saying what it can do, and CORA separates those too.

A Family carries a set of **affordances**, a closed vocabulary of device-level primitives, the small verbs a class of hardware supports. Above that sits a **Role**: the functional contract a recipe actually asks for. The four that ship today are `Detector`, `Positioner`, `Controller`, and `Sensor`. A Role names what operational shape a step needs without pinning the anatomy that provides it. "I need a positioner" is a Role; a hexapod, a linear stage, and a rotary stage are all Families that can satisfy it, and each one advertises the Roles it satisfies.

This indirection is what lets a technique travel. A method written against "a positioner and a detector" can run at any facility that has some Family advertising each Role, rather than being welded to one site's particular hardware. It is the same instinct as the recipe ladder, applied to equipment: keep the portable description and the local specifics on separate rungs, and match them only when an actual plan binds an actual instance.

## Made of

A beamline is not a flat list of parts; it is parts composed into larger things, and "made of" turns out to mean three different relations that CORA keeps separate on purpose.

The first is plain physical containment: the camera inside the microscope body is a child of the body. This is a single-parent tree recorded directly on each Asset, the genuine "what sits inside what," and it nests to any depth.

The second is reusable composition. An **Assembly** is a blueprint for a cluster: a map of named slots, each typed by the Family that must fill it, plus the wiring intrinsic to the cluster, and it can include smaller Assemblies as sub-blueprints. An Assembly is content-addressed, fingerprinted by its structure, so two operators who independently describe the same cluster arrive at the same identity, which is what makes a composition portable across facilities. The Assembly advertises the Roles the whole cluster satisfies, so a microscope built from a camera, a scintillator, and an optics group can present itself as a single `Detector` to a recipe.

The third is materialization. A **Fixture** is one realization of an Assembly: it binds each named slot to a specific Asset, snapshots the blueprint's fingerprint at the moment it was built, and records the parameters chosen for this particular build. The blueprint is the recipe for the cluster; the Fixture is the cluster actually bolted together on the bench this week.

Keeping containment, blueprint, and materialization on three separate axes means none of them has to pretend to be another, and the materialization can stay a flat, honest map of slot-to-instance even when the blueprint is deeply nested.

## When a part earns its own identity

The most common real question this model has to settle is mundane and constant: is this sub-component its own Asset, or just a detail of its parent? A turret of lenses, a controller driving a stage, a thermocouple on a holder. CORA answers with three tests, and any one of them is enough to make the sub-component its own Asset.

The first is lifecycle independence: can it be swapped or retired without retiring its parent? The second is external addressability: does anything else in the system need to point at it by name, a calibration, a wiring entry, a safety target? The third is settings divergence: does it need its own parameters that would collide with the parent's? Addressability tends to win the ties. At an imaging beamline the usual trigger is calibration: each lens position in a turret carries its own magnification, so each earns its own Asset and its own identity. A sub-component that fails all three tests is not a separate thing at all; it is a value in the parent's settings or an entry in its list of ports. The choice is consequential because each Asset is its own permanent stream, so the model gives an explicit rule rather than leaving it to taste.

## The thing being measured is not equipment

One boundary is worth drawing sharply. The sample, the specimen, the part being printed in situ, is not an Asset. It is a **Subject**, modeled separately, because it lives by a different clock and a different lifecycle: it is received, mounted, measured, and then returned, stored, or discarded, and it can be referenced across many runs. The sample changer and the environment rig that hold it are Assets; the thing they hold is a Subject. Conflating the two would tangle the lifecycle of a borrowed stage with the lifecycle of the specimen it happened to carry one afternoon, and those two stories deserve to be told separately.

## Honest edges

This is a real model carrying a real beamline, and it has deliberate edges.

Several of its structural rules are conventions rather than enforced invariants. The equipment tiers, the rough Unit, Component, Device depth labels borrowed from industrial practice, are not policed: a smart instrument with addressable sub-modules can legitimately nest a device inside a device, so the model allows it. Cross-references between aggregates are eventually consistent rather than checked on the spot: when an Asset records that it belongs to a Family, the write does not stop to confirm that Family stream exists, the same relaxed stance the rest of CORA takes on cross-aggregate links. Some checks are simply not built yet: the intrinsic wiring declared in an Assembly is a statement of intent that is not yet validated port-by-port against the materialized instances, cycle detection in the containment tree is limited to the obvious self-loop, and the persistent-identifier minting that would turn an Asset into a citable record is authored but not yet wired to issue identifiers. None of these are hidden; each waits for the use case that makes it worth building.

And the usual caveat holds: CORA is a pre-1.0 system, and the 2-BM beamline is the grounding corpus that keeps this model honest. The proof that the abstractions are right is that a real instrument, with real swaps and recalibrations and rebuilds, fits into them without forcing.

## Why this is foundational

The recipe ladder gave the work somewhere portable to live. The equipment model gives the hardware a faithful, changing record that the work can point at: a stable identity per instance, a clean split between what a thing is and what it can do, a disciplined boundary between the declarer of rules and the carrier of data, and three honest ways to say that one thing is made of another. The planks of the ship will keep being replaced. What stays the same is the record: an inventory that can tell you, years later, exactly which detector took this scan, what state it was in, what it was bolted into, and what it had become by then.
