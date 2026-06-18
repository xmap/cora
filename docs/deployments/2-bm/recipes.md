# Recipes

*Deployment-bound recipe designs for 2-BM (Recipe BC).*

A Recipe is an ordered, parameterized step sequence (setpoint / check / action) that expands into a [Procedure](procedures.md) once an operator binds its tunable values. Recipes are **deployment-bound**: they hardcode 2-BM device addresses, so they live here, not in the cross-facility [Catalog](../../catalog/index.md) (the portable rung is the [Method](../../catalog/methods.md)). See [Model](../../architecture/model.md) for the aggregate shape.

Each recipe below realizes one [Capability](../../catalog/capabilities.md) as a flat setpoint/check/action sequence, with only operator values bound and no feedback loop. Two are **runnable today** (they reuse an already-registered action body); two are **designs pending executors** (they invoke action bodies that are not registered yet, the registry today holds only `collect`, `discrete`, `continuous`). Addresses confirmed in [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) are shown plain; records not yet in the descriptor are marked *(illustrative, confirm with staff)* and tracked on [Open questions](questions.md).

## Runnable today

These two reuse the registered `collect` action body (acquire a frame stack, poll until done), so they can be conducted without new executor code. The pixel-wise baseline math (mean / std) is downstream data reduction, not a recipe step (per the catalog convention that reduction lives in pipelines, not in CORA); the captured stack becomes a baseline [Dataset](datasets.md). These same captures are also modeled as subject-less calibration [Runs](runs.md); a recipe is the as-data form of the capture sequence (it expands into a Procedure).

### `dark_baseline`

Realizes [`cora.capability.acquisition`](../../catalog/capabilities.md). Shutter closed, no beam, capture a dark-frame stack for reconstruction subtraction. Binds `repetitions` (frame count) and `dwell` (per-frame exposure).

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `S02BM-PSS:SBS` (StationShutter) | `closed` (verify) |
| 2 | check | `S02BM-PSS:SBS` | `== closed` |
| 3 | action | `collect` | `{ detector: "2bmSP1:", repetitions: <<repetitions>>, dwell: <<dwell>> }` |

### `flat_baseline`

Realizes [`cora.capability.acquisition`](../../catalog/capabilities.md). Shutter open, no sample in the beam, capture a flat-field stack for reconstruction division. Binds `repetitions` and `dwell`. Precondition: the sample is out of the beam path, which is an **operator assertion**, not a CORA setpoint (CORA does not drive the sample out automatically).

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `S02BM-PSS:SBS` (StationShutter) | `open` (verify) |
| 2 | check | `S02BM-PSS:SBS` | `== open` |
| 3 | action | `collect` | `{ detector: "2bmSP1:", repetitions: <<repetitions>>, dwell: <<dwell>> }` |
| 4 | setpoint | `S02BM-PSS:SBS` (StationShutter) | `closed` (verify, return to safe state) |

## Designs, pending executors

These two are clean Recipe v1 shapes but invoke action bodies that are not registered yet, so they are authorable as data but cannot be conducted until their executors land. That executor work sits in the same deferred-runtime bucket as live hexapod motion (see [Open questions](questions.md#the-hexapod)); it is not a separate surprise.

### `set_energy`

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

The setpoint positions are the curve outputs at 22 keV and are **provisional**: the per-energy curves await the real saved-position table from 2-BM staff. The curve-interpolation math (`eval_lookup_table`) now exists on main, but two things still block a live free-keV recipe: the saved per-energy table is not populated, and the Plan.wiring-backed constituent resolver that would let the recipe address the five facets as `pseudoaxis://` constituents is still deferred. So a v1 recipe still encodes **one energy's resolved positions** as literal setpoints, one recipe per saved energy (the configured menu is 13.374 / 13.574 / 18.0 / 20.0 / 25.0 / 25.584 keV); `energy_kev` is recorded but does not drive live position computation at v1.

**To run, needs:** the `coordinate_energy_move` action body (not registered today, only `collect` / `discrete` / `continuous` are); the Plan.wiring-backed pseudoaxis constituent resolver (still deferred, so the five facets cannot yet be addressed as `pseudoaxis://` constituents); the populated per-energy saved table from staff; and the real readback (`.RBV`) PVs. The curve-interpolation runtime (`eval_lookup_table`) itself has since landed on main.

### `hexapod_reboot`

Realizes [`cora.capability.maintenance`](../../catalog/capabilities.md). Recovers a stuck hexapod controller on the `2bmHXP:` axis: stop the IOC, power-cycle its PDU outlet, restart the IOC, confirm all axes enabled. A flat setpoint/action/check sequence with no scientific output. The records below are confirmed against the authoritative reboot script [`decarlof/2bmb-bin/hexapod_reboot.py`](https://github.com/decarlof/2bmb-bin/blob/HEAD/hexapod_reboot.py); the bindings are the timing durations.

Phase 1, stop the IOC:

- action `run_shell_script { script: "hexapod_IOC_stop.sh" }`
- check the IOC is stopped

Phase 2, power-cycle the PDU outlet (NetBooter PDU, **outlet 5**, over HTTP: `/cmd.cgi?rly=N` to toggle, `/status.xml` to read; the NetBooter relay index is zero-based, so the operator-facing outlet 5 is the wire call `rly=4` and the status element `<rly4>`):

- action `pdu_power_toggle { outlet: 5, state: "off" }`, then check the outlet is off
- action `sleep { seconds: <<off_wait>> }` (power discharge, default 10 s)
- action `pdu_power_toggle { outlet: 5, state: "on" }`, then check the outlet is on
- action `sleep { seconds: <<on_wait>> }` (controller boot, default 30 s)

Phase 3, restart the IOC:

- action `run_shell_script { script: "hexapod_IOC.sh" }`
- action `sleep { seconds: <<ioc_settle>> }` (IOC settle, default 10 s), then check the enable PV is connected

Phase 4, confirm enabled:

- action `caget_poll { pv: "2bmHXP:HexapodAllEnabled.VAL", timeout_s: 180, interval_s: 1 }`
- check `2bmHXP:HexapodAllEnabled.VAL == 1`

The PVs (`2bmHXP:HexapodAllEnabled.VAL` read, `2bmHXP:EnableWork.PROC` force-enable), the IOC scripts, the host (`arcturus`), the NetBooter endpoints, outlet 5, and the timings are all confirmed from the reboot script (tracked as [HXP-3 through HXP-6](questions.md#the-hexapod)). What is NOT in the repo: the script selects one of two PDUs (`a` default, or `b`), and that choice plus the PDU IP live in the operator's `~/access.json`, so they remain a deployment secret to confirm. The script also runs an optional TCP controller-readiness check (port 5001) between power-on and IOC restart, gated on a configured controller IP; its applicability to the Aerotech hexapod ties to the open drive identity (`DRIVE-4`).

This recipe captures the **happy path only** (controller enabled on the first check). The script's real flow is conditional: if `HexapodAllEnabled` is not `1`, it rechecks after 3 s, then issues `caput 2bmHXP:EnableWork.PROC 1` and polls every 1 s up to 180 s. That branch is a conditional the v1 body cannot express, so it stays an operator decision and is the v2 conditional-branch trigger. The Equipment-BC fault and restore that bracket the ceremony, and the Caution registered against the controller, are separate commands in their own BCs, not recipe steps.

One manual step follows a reboot but sits outside this controller-side sequence: per the staff [sample motor stack page](https://docs2bm.readthedocs.io/en/latest/source/ops/item_050.html) (`item_050`), the hexapod Y stage does not reset its dial correctly after a reboot (the Y dial reads 0 while the encoder reads 350), and the first Y move in that state raises a drive error. The operator must manually set the Y dial to 350 before any Y motion. Because it acts on the stage rather than the controller and is a manual correction, it is captured as the [Y-stage dial-misreset Caution](cautions.md#hexapod-y-stage-dial-misreset-after-reboot), not a recipe step.

**To run, needs:** action bodies that are not registered today (`run_shell_script`, `pdu_power_toggle` over the NetBooter HTTP API, `sleep`, `caget_poll`, plus `caput` for the force-enable branch) and their substrate adapters (a shell or SSH execution port, an HTTP port for the PDU, a channel-access read/write port). The records themselves are now confirmed from the reboot script; only the PDU selection (`a` / `b`) and its IP remain a deployment secret.

## Status

`dark_baseline` and `flat_baseline` are conductible today (they reuse `collect`); the baseline reduction that follows the capture is downstream of the recipe. `set_energy` and `hexapod_reboot` are valid Recipe v1 data but not yet runnable: conducting either would fail at the first unregistered action body. They are recorded here so the step order, addresses, and tunable values are captured as reviewable data ahead of the executor work, which sits in the same deferred-runtime bucket as live motion.
