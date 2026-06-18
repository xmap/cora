# Operations

*How 2-BM is operated, organized by the task in front of you: from a cold beamline to data on disk, and recovery
when something stalls.*

This zone is the runbook. The detailed records live in the pages under it: the [Procedures](procedures.md) (the
operational-task table and its per-step preconditions), the [Recipes](recipes.md) (deployment-bound step
sequences), the [Cautions](cautions.md) (operator tribal knowledge), and the [Enclosures](enclosures.md) (the two
hutch permits and the gate that uses them). This hub is the reading order and the conditions that must hold
before a run starts.

## Before a run

A run starts only when its beam path is permitted and the resources it needs are available.

- Permits: every hutch a run touches must be searched, secured, and Permitted. The two 2-BM hutches and the
  located-in pre-flight gate are on [Enclosures](enclosures.md).
- Resources: the consumables and utilities a run draws on, below.

## Supplies

A Supply is a continuously-available resource tracked at facility, sector, or beamline scope. Facility-scope
Supplies live at [APS](../aps/index.md#the-resources-you-draw-on). The beamline-scope Supply registered at 2-BM:

| Supply | Scope | Kind |
| --- | --- | --- |
| `2-BM detector LN2 dewar` | `Beamline` | `LiquidNitrogen` |

The sample-environment gas mix and compressed-air specs are open (`SUP-1`, `SUP-2` on
[Open questions](questions.md)); the data-storage tiers and the BLEPS-mapped utilities are tracked there too,
since CORA models storage and utility availability as Supplies.

## The task flow

The operating sequence, cold beamline to data on disk:

- Ready the beam: confirm the hutch permits, select the beam mode (Mono or Pink), and open the shutters. See
  [Procedures](procedures.md).
- Set the energy: drive the optic curves to a configured energy. The [`set_energy`](recipes.md#set_energy) recipe
  is the as-data form; the `set_energy` Procedure is the task record.
- Mount and align: home the stack and align the sample (`motor_homing`, the `*_alignment` Procedures). See
  [Procedures](procedures.md).
- Scan: capture the [`dark_baseline`](recipes.md#dark_baseline) and [`flat_baseline`](recipes.md#flat_baseline)
  references, then run the tomography Plan.
- Recover: when a stage stalls, the [Cautions](cautions.md) name the fix.

## When something goes wrong

Operator tribal knowledge is captured as [Cautions](cautions.md), each surfaced on run start and each naming its
recovery. A locked-up hexapod controller is recovered with the [`hexapod_reboot`](recipes.md#hexapod_reboot)
recipe; the Aerotech rotary's cold-start index miss is cleared by re-homing after a short settle; the hexapod Y
dial must be reset to 350 after any reboot before the first Y move.
