# Enclosures

*Enclosure BC permits that gate Runs and Procedures at 2-BM.*

An Enclosure models the observed permit status of a physical space that gates experiments: at 2-BM, the experiment hutch whose interlock and search-and-secure sequence must be satisfied before beam-on work proceeds. See the [Enclosure module](../../architecture/modules/enclosure/index.md) for the aggregate shape and the permit / lifecycle axes.

## Containing Asset

A 2-BM enclosure binds to the `2-BM` Unit Asset (the root Asset declared on the [2-BM index](index.md), `tier = Unit`). Every 2-BM Device hangs directly off that Unit via `parent_id` (see [Assets](assets.md)). Binding the enclosure at the Unit is deliberate: through the pre-flight chain walk it then covers every Device under the beamline without a per-Device enclosure registration.

Finer-grained hutch enclosures (a separate permit per the 2-BM-A and 2-BM-B stations) would bind to hutch-tier Assets. Those Assets are not modelled at v1 (Devices nest directly under the `2-BM` Unit), so a per-station permit split is deferred until the station Assets register.

| Enclosure | Containing Asset | Covers |
| --- | --- | --- |
| `2-BM-hutch` (planned) | `2-BM` (Unit) | every Device under `2-BM` via the chain walk |

## Gate semantics

`start_run` and `start_procedure` both run an Enclosure pre-flight gate. The gate derives the Asset scope from the chain, not from an explicit per-Method enclosure list: it starts from the Plan-bound (or Procedure-target) Assets and widens the scope UP the `parent_id` chain to the facility-rooted Unit, then asks the Enclosure read model which Enclosures contain any Asset in that widened scope.

For 2-BM this means a Run whose Plan binds only a Device (say `Aerotech_ABRS_rotary`) is gated by the `2-BM` Unit's enclosure permit, because the walk climbs `Aerotech_ABRS_rotary` to its parent `2-BM` and finds the Unit-bound enclosure. Without the walk the Unit-bound enclosure would never match a Device-binding Plan, and the gate would silently pass.

The decider then requires every referencing Enclosure to be `Permitted` and `Active`:

- all referencing Enclosures Permitted-and-Active, or none referencing at all: the Run / Procedure starts.
- every referencing Enclosure fails the check: refused with `RunRequiresPermittedEnclosureError` / `ProcedureRequiresPermittedEnclosureError` (HTTP 409).
- some pass and some fail: refused with `RunEnclosureCoverageMismatchError` / `ProcedureEnclosureCoverageMismatchError` (HTTP 409).

Every ancestor enters the widened scope regardless of its own lifecycle. Whether a retired ancestor's interlock still blocks is decided by the Enclosure's own lifecycle, not the containing Asset's: a Decommissioned Enclosure is excluded at the read layer, but an Enclosure that is still Active and NotPermitted on a Decommissioned ancestor Asset correctly REFUSES the Run (decommissioning the containing Asset does not retire its interlock). The walk reads only the Equipment Asset projection and stops at the facility-rooted Unit; it never crosses into the Federation Facility hierarchy.

See [Runs](runs.md) and [Procedures](procedures.md) for what each gated operation binds.

## Pending

No 2-BM enclosures are registered yet. Registration is the trigger for the production Personnel Safety System observer adapter (the substrate that reports interlock permit changes into `observe_enclosure_status`); until that adapter integrates at first pilot, the permit channel has no live source. The chain-walk gate is in place and proven (see the `test_2bm_enclosure_chain_walk` scenario) and fires the moment a `2-BM` enclosure registers.
