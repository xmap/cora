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

A Supply is a continuously-available resource a run draws on. Beamline-scope Supplies are tracked here;
facility-scope utilities live at [APS](../aps/index.md#the-resources-you-draw-on).

| Supply | Scope | Kind |
| --- | --- | --- |
| `2-BM detector LN2 dewar` | `Beamline` | `LiquidNitrogen` |

2-BM keeps no standing gas-mix or compressed-air Supply: sample gas is per-experiment and ESAF-gated (a
Run-level fact, not a beamline Supply), and compressed air is the APS facility shop-air line with no
beamline-local spec.

The photon beam, cooling water, vacuum, and electrical power are facility-scope utilities, observed through
BLEPS and recorded at the [APS](../aps/index.md#the-resources-you-draw-on) level rather than as beamline
Supplies; the BLEPS-to-Supply mapping is tracked on
[Open questions](questions.md#equipment-protection-bleps).

Beyond the physical utilities, a run also draws on a compute pool (for reconstruction) and on data-transfer and
storage tiers. These are modelled through the `ComputePort` and `TransferPort` (a Method plus a port, not a new
deployment aggregate). The confirmed pipeline (DATA-1 through DATA-7): the detector writes to fast local NVMe on
`tomdet` (`/local1`), tomoscan auto-uploads each scan to the analysis tier (`/data2` or `/data3`), tomocupy
reconstructs there (`..._rec/` beside the raw), and an operator copies the experiment to its canonical home on
Sojourner (`/gdata/dm/2BM/<yyyy-mm>/<exp>/{data,analysis,system}/`), shared to proposal and ESAF users through
the Globus collection `APS:DM:2BM` and archived to tape on a per-experiment timer (default one year). The
upstream tiers are transient, capacity-purged with no fixed schedule, so a dataset is briefly multi-homed and
then collapses to the Sojourner copy; there is no continuous beamtime-long sync. The reconstruction compute
resource itself is not yet pinned to a specific host or pool.
