# Names as federation vocabulary

`Family`, `Role`, and `Model` names are not just labels. Each of these aggregates derives its identity from its name (or its vendor key), so the same concept resolves to the same id at every facility. A name is therefore a cross-facility contract: rename a `Family` and you mint a new identity that no longer matches the same `Family` elsewhere. This page is the system those names follow.

## The one principle

> A name-keyed aggregate's id is `uuid5(namespace, the aggregate's federation-stable natural key)`.

The natural key differs because the things differ:

| Aggregate | Natural key the id is derived from | Is the `name` the key? |
| --- | --- | --- |
| `Family` | the name | yes |
| `Role` | the name | yes |
| `Model` | the vendor key `(manufacturer, part_number)` | no: the `name` is a label |

A `Family` or `Role` has no identifier deeper than its name: "Camera" is the identity. A `Model` is a real-world vendor product that already has a globally stable identifier (its SKU), so its id is derived from `(manufacturer, part_number)` and the `name` rides on top as a human handle. It is one principle, applied to each thing's truest facility-independent identifier.

Practical consequence:

- Renaming a `Family` or `Role` changes its id. That is a federation break and a data migration, not a cosmetic edit.
- Renaming a `Model` `name` is harmless: identity is the vendor key, so the label can change freely.

## Three axes

The three aggregates are orthogonal axes, and an `Asset` sits at their intersection: it IS-A Family (anatomy), can present as a Role (function), and may bind a Model (vendor).

| Aggregate | Axis | Answers | Grammar | Casing |
| --- | --- | --- | --- | --- |
| `Family` | anatomy | what it IS (device class) | thing-noun, singular, noun-LAST | `PascalCase` |
| `Role` | function | what contract it fulfills | agent-noun (-er / -or) | `PascalCase` |
| `Model` | vendor | what product it is | `manufacturer_<model-or-line>` | `lower_snake` |

The grammar is the tell. `Camera`, `Scintillator`, `Hexapod`, `Housing` are thing-nouns (Families: what the device is). `Detector`, `Positioner`, `Controller`, `Sensor` are agent-nouns (Roles: the job a thing does). When you are unsure which aggregate a new name belongs to, the part of speech usually decides it.

## Per-aggregate rules

### Family (anatomy)

- **PascalCase, singular, a thing-noun.** `Camera`, not `Cameras`, not `Detector` (an agent-noun, which names a Role).
- **Anatomical, not vendor / substrate / deployment / content.** A `Family` names what the device IS, device-agnostic across facilities. Vendor identity lives on the bound `Model`; substrate (FPGA, VME card) lives in `settings`; deployment context never enters the name. This is why `TriggerFPGA` became `TimingController` and `OpticalHousing` became `Housing` ("Optical" named the contents, not the chassis's own nature).
- **Noun LAST (R3).** A qualifier precedes the family noun: `RotaryStage`, `LinearStage`, `MotionController`. Single-word is preferred; a compound is justified only when the qualifier names the device's own intrinsic nature (how it moves, what signal it generates), not its contents or the assembly it serves.
- **`<Domain>Controller`** for any separately-modelled, field-replaceable control-electronics box (`MotionController`, `TimingController`); the driven device carries a `controller_id` back-reference.
- A `Family` must have, or plausibly have, instances. A `Family` that exists only to be a binding target is a presenter Family, an anti-pattern (see Deprecations).

### Role (function)

- **PascalCase, singular, an agent-noun:** `Detector`, `Positioner`, `Controller`, `Sensor`. A `Role` names the job, not the device.
- A `Role` is the functional binding contract a `Method` targets through `presents_as` and `RoleRequirement`. It carries affordances, `produces`, `consumes`, and a docstring; it has no settings, no instances, and no ports.
- `Controller` is the bare `Role` (the function); `<Domain>Controller` is the `Family` (the box). The qualification keeps the two distinct.

### Model (vendor)

- **Identity is `(manufacturer, part_number)`, never the `name`.** The `name` is a human handle and a cross-reference slug (the deployment descriptor's `model:` fields point at it).
- **Handle form:** `<manufacturer-slug>_<recognizable model or product line>`, `lower_snake`. The full SKU lives in `part_number`, so the handle does not mash it, and it carries no function word, deployment token, or placeholder cruft. Example: `flir_oryx` with `part_number = ORX-10G-51S5M-C`, not `flir_oryx_orx_10g_51s5m_c`.
- **Unconfirmed products:** a `Model` whose `part_number` is the `unknown-pending-confirmation` sentinel gets a random id, so two genuinely-unidentified units stay distinct; it re-registers under its derived id once the real part number is confirmed. Such a `Model`'s name is provisional and is a beamline-staff question, not a guess.

## Canonicalization contract

Because the name is the key for `Family` and `Role`, the derivation canonicalizes so the same concept cannot fork:

- **Case-fold.** The name is lower-cased before hashing, so `Camera` and `camera` are one identity. Case is presentation; `PascalCase` is the display convention.
- **NFC-normalize.** Composed versus decomposed Unicode (an accent written as one character versus a letter plus a combining mark) is folded to one form before hashing, so a name that renders identically cannot fork across facilities. `Model` normalizes its manufacturer key the same way.
- **Per-aggregate namespace.** `Family`, `Role`, and `Model` each derive in their own namespace UUID, so a `Camera` Family and a hypothetical `Camera` Role never collide in id space.

## Deciding which aggregate a new name belongs to

1. Is it a vendor product (a thing you buy, with a manufacturer and a part number)? Then a `Model`.
2. Is it a binding contract a `Method` needs (a job, an agent-noun)? Then a `Role`.
3. Is it what a device fundamentally IS (a thing-noun, substrate-agnostic, reusable across facilities)? Then a `Family`.
4. Is it a variant of an existing one along a tunable axis (a faster camera, a thicker scintillator)? Then it is not a new name at all: it is `settings` on the existing one (settings over subtypes).

## Deprecations and smells

- **Presenter Families.** A `Family` that exists only as a presenter target, with no instances of its own, is a transitional shim from before Roles existed. The forward path is a `Role` plus `presents_as: frozenset[RoleId]`. The last presenter-Family shim has been retired: `Imager` was removed from the catalog, and detector Assemblies now present the `Detector` Role via `presents_as`. Binding a `Method` to a real, instanced `Family` (`needed_family_ids = {Camera}`) stays valid; only the instance-less contract proxy is the anti-pattern.
- **A bare agent-noun Family.** A bare `Controller` Family, or any agent-noun used as a Family name: agent-nouns name functions (Roles), not device classes. Qualify it (`MotionController`) or move it to a `Role`. (`Imager`, now retired, was an example of this smell.)
- **A Model `name` treated as identity.** It is a label. Identity is `(manufacturer, part_number)`.

## See also

- [Equipment module](../architecture/modules/equipment/index.md): the concrete Family corpus, the `<Domain>Controller` convention, and the function-by-anatomy matrix.
- [Conventions](conventions.md): identifiers, units, and the wider repo conventions.
