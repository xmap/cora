# Enclosures

*Enclosure BC permits that gate Runs and Procedures at 2-BM.*

An Enclosure models the observed permit status of an access-gated volume: a physical space whose interlock and search-and-secure sequence must be satisfied before beam-on work proceeds inside it. See the [Enclosure module](../../architecture/modules/enclosure/index.md) for the aggregate shape and the permit / lifecycle axes.

2-BM has two hutch Enclosures, the optics hutch `2-BM-A` and the experiment hutch `2-BM-B`. Each is its own access-gated volume with its own Personnel Safety System permit, observed independently. They sit on the three clean axes the deployment keeps separate:

- Institutional geography is the Federation Facility (the APS Site, and its Areas).
- Equipment is the Asset (the `2-BM` Unit and the Devices under it, functional only).
- Operational access is the Enclosure (the two hutches).

## Anchoring and located-in

Each hutch Enclosure is anchored to the APS Site via `facility_code = "aps"`: it is a space contained in a larger space, NOT a pointer to an equipment Asset. `register_enclosure` takes the Facility slug, and the handler resolves it through the Federation BC's FacilityLookup port (an unknown slug is refused).

A Device declares which hutch it physically sits in via `located_in_enclosure_id`. That is the operational where, distinct from the institutional where (`facility_code`) the Device shares with the rest of the beamline. At 2-BM, `FrontEndDrive` is located in `2-BM-A` (the optics band); every other modelled Device sits in `2-BM-B` (the experiment hutch, including the P6-50 safety stack and its SBS shutter, which gates that hutch). See [Assets](assets.md) for the per-Device located-in column.

| Enclosure | Role | Anchored to | Gates |
| --- | --- | --- | --- |
| `2-BM-A` | optics hutch | `aps` Site (`facility_code`) | Devices located in `2-BM-A` and their descendants |
| `2-BM-B` | experiment hutch | `aps` Site (`facility_code`) | Devices located in `2-BM-B` and their descendants |

## Gate semantics

`start_run` and `start_procedure` both run an Enclosure pre-flight gate. The gate derives the Enclosure scope from the Asset chain, not from an explicit per-Method enclosure list: it starts from the Plan-bound (or Procedure-target) Assets, widens UP the `parent_id` chain via `AssetLookup.ancestors_of`, then collects the distinct `located_in_enclosure_id` across that closure and loads those Enclosures' permit status via `EnclosureLookup.find_by_ids`. A Device inherits a functional ancestor's hutch: if a Device declares no located-in but its parent Unit does, the parent's hutch enters the scope.

The decider then requires every collected Enclosure to be `Permitted` and `Active`:

- all collected Enclosures Permitted-and-Active, or no Device in scope is located in any Enclosure: the Run / Procedure starts (Permit-by-default on an empty set).
- every collected Enclosure fails the check: refused with `RunRequiresPermittedEnclosureError` / `ProcedureRequiresPermittedEnclosureError` (HTTP 409).
- some pass and some fail: refused with `RunEnclosureCoverageMismatchError` / `ProcedureEnclosureCoverageMismatchError` (HTTP 409).

Because each Device names exactly one hutch, each hutch's permit gates only the Runs whose Devices sit in it. A Run whose Plan binds only an A-side Device starts when `2-BM-A` is Permitted, even while `2-BM-B` is NotPermitted. A cross-hutch Run, whose Plan spans Devices in both hutches, needs BOTH hutches Permitted: while only one is, the mixed result raises `RunEnclosureCoverageMismatchError` naming the failing hutch. The `test_2bm_two_hutch_enclosure_gate` scenario exercises both shapes.

Every ancestor enters the widened scope regardless of its own lifecycle. Whether a retired ancestor's interlock still blocks is decided by the Enclosure's own lifecycle, not the Asset's: a Decommissioned Enclosure is excluded at the read layer, but an Enclosure that is still Active and NotPermitted on a Decommissioned ancestor Asset correctly refuses the Run (decommissioning an Asset does not retire the interlock on the hutch it sits in). The chain walk reads only the Equipment Asset projection and the Enclosure projection; it never crosses into the Federation Facility hierarchy.

See [Runs](runs.md) and [Procedures](procedures.md) for what each gated operation binds.

## Pending

No 2-BM Enclosures are registered yet. Two integration items remain:

- The production Personnel Safety System observer adapter, which subscribes to both hutch permit channels and reports interlock permit changes into `observe_enclosure_status`. Until it integrates at first pilot, the permit channel has no live source.
- The per-hutch search-and-secure permit PVs. Only the shutter PVs (`S02BM-PSS:FES`, `S02BM-PSS:SBS`) are known today; the permit signal for each hutch is an operator-confirm item, carried as a `confirm` note in the descriptor.

The chain-walk gate is in place and proven (see the `test_2bm_enclosure_chain_walk` and `test_2bm_two_hutch_enclosure_gate` scenarios) and fires the moment the two hutch Enclosures register.
