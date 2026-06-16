# Recipes

*Deployment-bound recipe designs for 2-BM (Recipe BC).*

A Recipe is an ordered, parameterized step sequence (setpoint / check / action) that expands into a [Procedure](procedures.md) once an operator binds its tunable values. Recipes are **deployment-bound**: they hardcode 2-BM device addresses, so they live here, not in the cross-facility [Catalog](../../catalog/index.md) (the portable rung is the [Method](../../catalog/methods.md)). See [Model](../../architecture/model.md) for the aggregate shape.

The two below are the first recipe designs. Both are clean Recipe v1 shapes: a flat setpoint/check/action sequence under one [Capability](../../catalog/capabilities.md), with only operator values bound and no feedback loop. Both are **authorable as data today but not yet runnable**: each invokes one or more action bodies that are not registered yet (the executor registry today holds only `collect`, `discrete`, `continuous`). The status note under each lists what it needs to run. Addresses confirmed in [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) are shown plain; addresses not yet in the descriptor are marked *(illustrative, confirm with staff)*.

## `set_energy`

Realizes [`cora.capability.energy_change`](../../catalog/capabilities.md). Drives the energy-tracking optic axes to their per-energy positions as one coordinated move. Binds one value: `energy_kev`.

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `2bma:m30` (Mono Bragg arm upstream) | `0.76 deg` (verify) |
| 2 | setpoint | `2bma:m31` (Mono Bragg arm downstream) | `0.76 deg` (verify) |
| 3 | setpoint | `2bma:m32` (Mono M2 vertical offset) | `1.21 mm` (verify) |
| 4 | setpoint | `2bma:m9` (SampleSlit vertical top) | `0.19 mm` (verify) |
| 5 | setpoint | `2bma:m10` (SampleSlit vertical bottom) | `-0.19 mm` (verify) |
| 6 | action | `coordinate_energy_move` | `{ energy_kev: <<energy_kev>>, axis_count: 5 }` |
| 7-11 | check | each axis readback (`.RBV`) *(illustrative)* | `within_tolerance` |

The setpoint positions are the curve outputs at 22 keV and are **provisional**: the per-energy curves await the real saved-position table from 2-BM staff. Because curve interpolation (`eval_lookup_table`) is deferred, a v1 recipe encodes **one energy's resolved positions**, so author one recipe per saved energy (the configured menu is 13.374 / 13.574 / 18.0 / 20.0 / 25.0 / 25.584 keV) until that runtime lands. `energy_kev` is recorded but does not drive live position computation at v1.

**To run, needs:** the `coordinate_energy_move` action body (not registered today); the per-energy curve runtime (`eval_lookup_table`) and the pseudoaxis constituent resolver (both deferred, so the five facets cannot yet be addressed as `pseudoaxis://` constituents); and the real readback (`.RBV`) PVs confirmed by staff.

## `hexapod_reboot`

Realizes [`cora.capability.maintenance`](../../catalog/capabilities.md). Recovers a stuck hexapod controller on the `2bmHXP:` axis: stop the IOC, power-cycle its PDU outlet, restart the IOC, confirm all axes enabled. A pure setpoint/action/check sequence with no scientific output. Optional bindings: the two settling durations.

Phase 1, stop the IOC:

- action `run_shell_script { script: "hexapod_IOC_stop.sh" }`
- check the IOC is stopped

Phase 2, power-cycle the PDU outlet:

- setpoint PDU outlet 4 = off, then action `pdu_power_toggle { outlet: 4, state: "off" }`, then check the outlet is off
- action `sleep { seconds: <<settle_off_s>> }` (power settling, 10 s in the captured run)
- setpoint PDU outlet 4 = on, then action `pdu_power_toggle { outlet: 4, state: "on" }`, then check the outlet is on
- action `sleep { seconds: <<settle_on_s>> }` (controller boot, 10 s)

Phase 3, restart the IOC:

- action `run_shell_script { script: "hexapod_IOC.sh" }`
- check the IOC is running

Phase 4, confirm enabled:

- action `caget_poll { pv: "2bmHXP:HexapodAllEnabled.VAL", timeout_s: 180, interval_s: 2 }` *(record illustrative)*
- check `2bmHXP:HexapodAllEnabled.VAL == 1` *(record illustrative)*

Only the `2bmHXP:` prefix is confirmed in the descriptor. The reboot-specific records (`HexapodAllEnabled.VAL`, the PDU `outlet 4` endpoints, the shell-script names, the IOC channel) come from the external `2bmb-bin/hexapod_reboot.py` script and are *(illustrative, confirm with staff)*. This recipe captures the **happy path only**: the force-enable fallback (if `HexapodAllEnabled` stays 0 after the timeout, run `caput 2bmHXP:EnableWork.PROC 1` then re-poll) is a conditional branch the v1 body cannot express, so it stays an operator decision and is the v2 conditional-branch trigger. The Equipment-BC fault and restore that bracket the ceremony, and the Caution registered against the controller, are separate commands in their own BCs, not recipe steps.

**To run, needs:** four action bodies that are not registered today (`run_shell_script`, `pdu_power_toggle`, `sleep`, `caget_poll`) plus their substrate adapters (a shell or SSH execution port, an HTTP port for the NetBooter PDU, a channel-access poll body); and the reboot-specific PVs confirmed by staff.

## Status

Both recipes are **designs, not yet runnable**. The body of each is expressible as Recipe v1 data, but conducting either would fail at the first unregistered action body. They are recorded here so the step order, addresses, and tunable values are captured as reviewable data ahead of the executor work. Writing the action bodies (and, for `set_energy`, the curve runtime) is the prerequisite before either can drive real motion. The cheaper-to-run alternative, if a runnable first recipe is wanted, is an acquisition recipe (dark or flat baseline) that reuses the existing `collect` / `discrete` action body.
