# Operations

*The 2-BM runbook, by task: ready the beam, set energy, mount and align, scan, recover.*

The detail lives in the pages under this one: [Procedures](procedures.md), [Recipes](recipes.md),
[Enclosures](enclosures.md) (the hutch permits), and [Cautions](cautions.md). A run starts only when its hutches
are Permitted and its resources are available.

## The task flow

- Ready the beam: confirm the hutch permits, pick the beam mode (Mono or Pink), open the shutters.
- Set the energy: [`energy_setting`](recipes.md#energy_setting) drives the optic curves to a configured energy.
- Mount and align: `motor_homing` and the `*_alignment` [Procedures](procedures.md).
- Scan: capture [`dark_baseline`](recipes.md#dark_baseline) and [`flat_baseline`](recipes.md#flat_baseline),
  then run the tomography Plan.
- Recover: the [Cautions](cautions.md) name the fix (a locked hexapod clears with
  [`hexapod_reboot`](recipes.md#hexapod_reboot)).

## Supplies

A Supply is a continuously-available resource tracked at beamline scope; facility-scope Supplies live at
[APS](../aps/index.md#the-resources-you-draw-on).

| Supply | Scope | Kind |
| --- | --- | --- |
| `2-BM detector LN2 dewar` | `Beamline` | `LiquidNitrogen` |

Pending Supplies: a sample-environment gas mix (`ProcessGas`, `SUP-1`) and a compressed-air supply (`CompressedAir`, `SUP-2`); storage tiers and BLEPS utilities are tracked on
[Open questions](questions.md).
