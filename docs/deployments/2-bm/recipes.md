# Recipes

*Deployment-bound recipe designs for 2-BM (Recipe BC).*

A Recipe is an ordered, parameterized step sequence (setpoint / check / action) that expands into a [Procedure](procedures.md) once an operator binds its tunable values. Recipes are **deployment-bound**: they hardcode 2-BM device addresses, so they live here, not in the cross-facility [Catalog](../../catalog/index.md) (the portable rung is the [Method](../../catalog/methods.md)). See [Model](../../architecture/model.md) for the aggregate shape.

Addresses confirmed in [`beamline.yaml`](https://github.com/xmap/cora/blob/main/deployments/2-bm/beamline.yaml) are shown plain; records not yet in the descriptor are marked *(illustrative)* and tracked on [Open questions](questions.md).

The four recipes below are 2-BM's operational arc, each realizing one [Capability](../../catalog/capabilities.md) as a flat setpoint/check/action sequence with only operator values bound and no feedback loop: two baseline captures that feed reconstruction (`dark_field`, `flat_field`, `acquisition`), one coordinated optic-configuration change (`energy_setting`, `energy_change`), and one controller recovery (`hexapod_reboot`, `maintenance`).

| Recipe | Realizes | Target | Binds | Status |
| --- | --- | --- | --- | --- |
| `dark_field` | `acquisition` | `StationShutter` + detector | `repetitions`, `dwell` | Conductible today |
| `flat_field` | `acquisition` | `StationShutter` + detector | `repetitions`, `dwell` | Conductible today |
| `energy_setting` | `energy_change` | energy-tracking optic axes | `energy_kev` | Design, pending executor |
| `hexapod_reboot` | `maintenance` | `Hexapod` controller | reboot timings | Design, pending executor |

*Conductible today* means the recipe reuses the already-registered `collect` action body. *Design, pending executor* means the recipe is authorable as data now but invokes an action body that is not registered yet (the executor today holds only `collect`, `discrete`, `continuous`); the per-recipe blockers are listed under [What still needs to land](#what-still-needs-to-land).

## Acquisition baselines

Both baselines are calibration captures that feed reconstruction, and both reuse the registered `collect` action body (acquire a frame stack, poll until done), so they are conductible today. The pixel-wise baseline math (mean / std) is downstream data reduction, not a recipe step (per the catalog convention: pixel-wise baseline reduction stays in external pipelines, while a heavier compute step like reconstruction is a recorded compute Method); the captured stack becomes a baseline [Dataset](experiment.md), which makes each capture a [Run](experiment.md) (a Dataset-of-record makes the act a Run; see the [Run vs Procedure boundary](../../reference/modeling.md#run-vs-procedure-boundary) rule). The recipe is the as-data form of the capture sequence the Run conducts.

### `dark_field`

**Realizes** [`cora.capability.acquisition`](../../catalog/capabilities.md). Shutter closed, no beam: capture a dark-frame stack for reconstruction subtraction.

**Binds:** `repetitions` (frame count), `dwell` (per-frame exposure).

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `S02BM-PSS:SBS` (StationShutter) | `closed` (verify) |
| 2 | check | `S02BM-PSS:SBS` | `== closed` |
| 3 | action | `collect` | `{ detector: "2bmSP1:", repetitions: <<repetitions>>, dwell: <<dwell>> }` |

**Status:** conductible today (reuses `collect`).

### `flat_field`

**Realizes** [`cora.capability.acquisition`](../../catalog/capabilities.md). Shutter open, no sample in the beam: capture a flat-field stack for reconstruction division.

**Binds:** `repetitions`, `dwell`.

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `S02BM-PSS:SBS` (StationShutter) | `open` (verify) |
| 2 | check | `S02BM-PSS:SBS` | `== open` |
| 3 | action | `collect` | `{ detector: "2bmSP1:", repetitions: <<repetitions>>, dwell: <<dwell>> }` |
| 4 | setpoint | `S02BM-PSS:SBS` (StationShutter) | `closed` (verify, return to safe state) |

**Precondition:** the sample is out of the beam path. This is an operator assertion, not a CORA setpoint (CORA does not drive the sample out automatically).

**Status:** conductible today (reuses `collect`).

## Energy change

### `energy_setting`

**Realizes** [`cora.capability.energy_change`](../../catalog/capabilities.md). Drives the energy-tracking optic axes to their per-energy positions as one coordinated move.

**Binds:** `energy_kev`.

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `2bma:m30` (Mono Bragg arm upstream) | `0.76 deg` (verify) |
| 2 | setpoint | `2bma:m31` (Mono Bragg arm downstream) | `0.76 deg` (verify) |
| 3 | setpoint | `2bma:m32` (Mono M2 vertical offset) | `1.21 mm` (verify) |
| 4 | setpoint | `2bma:m9` (SampleSlit vertical top) | `0.19 mm` (verify) |
| 5 | setpoint | `2bma:m10` (SampleSlit vertical bottom) | `-0.19 mm` (verify) |
| 6 | action | `coordinate_energy_move` | `{ energy_kev: <<energy_kev>>, axis_count: 5 }` |
| 7-11 | check | each axis readback (`.RBV`) *(illustrative)* | `within_tolerance` |

The setpoint positions shown are illustrative curve outputs and are **provisional**: the per-energy curves await the real saved-position table from 2-BM staff. The curve-interpolation runtime (`eval_lookup_table`) exists, but a live free-keV recipe is still blocked on two things: the saved per-energy table is not populated, and the Plan.wiring-backed constituent resolver that would let the recipe address the five facets as `pseudoaxis://` constituents is deferred. So a v1 recipe encodes **one energy's resolved positions** as literal setpoints, one recipe per saved energy. The saved menu here is the **Mono** menu (the configured energies are listed on the [energy-tracking optic axes](inventory.md#energy-tracking-optic-axes)); `energy_setting` as written is the mono-mode recipe, and pink-mode energy selection is deferred with the [beam-mode work](questions.md#beam-mode) (`MODE-3` / `MIRROR-1`). `energy_kev` is recorded but does not drive live position computation at v1; once the saved table lands and the resolver ships, the runtime can interpolate an in-between energy (for example 22 keV, between the saved 20.0 and 25.0) rather than only the menu points.

**Status:** design, pending executor (see [What still needs to land](#what-still-needs-to-land)).

## Maintenance

### `hexapod_reboot`

**Realizes** [`cora.capability.maintenance`](../../catalog/capabilities.md). Recovers a stuck hexapod controller on the `2bmHXP:` axis: stop the IOC, power-cycle its PDU outlet, restart the IOC, confirm all axes enabled. A flat setpoint / action / check sequence with no scientific output.

**Binds:** the timing durations (`off_wait`, `on_wait`, `ioc_settle`).

| Phase | # | Step | Address / target | Value / params |
| --- | --- | --- | --- | --- |
| Stop the IOC | 1 | action | `run_shell_script` | `{ script: "hexapod_IOC_stop.sh" }` |
| | 2 | check | IOC | stopped |
| Power-cycle the PDU outlet | 3 | action | `pdu_power_toggle` | `{ outlet: 5, state: "off" }` |
| | 4 | check | PDU outlet 5 | off |
| | 5 | action | `sleep` | `{ seconds: <<off_wait>> }` (power discharge, default 10 s) |
| | 6 | action | `pdu_power_toggle` | `{ outlet: 5, state: "on" }` |
| | 7 | check | PDU outlet 5 | on |
| | 8 | action | `sleep` | `{ seconds: <<on_wait>> }` (controller boot, default 30 s) |
| Restart the IOC | 9 | action | `run_shell_script` | `{ script: "hexapod_IOC.sh" }` |
| | 10 | action | `sleep` | `{ seconds: <<ioc_settle>> }` (IOC settle, default 10 s) |
| | 11 | check | enable PV | connected |
| Confirm enabled | 12 | action | `caget_poll` | `{ pv: "2bmHXP:HexapodAllEnabled.VAL", timeout_s: 180, interval_s: 1 }` |
| | 13 | check | `2bmHXP:HexapodAllEnabled.VAL` | `== 1` |

The records are confirmed against the authoritative reboot script [`decarlof/2bmb-bin/hexapod_reboot.py`](https://github.com/decarlof/2bmb-bin/blob/HEAD/hexapod_reboot.py): the enable PVs (`2bmHXP:HexapodAllEnabled.VAL` read, `2bmHXP:EnableWork.PROC` force-enable), the IOC scripts, the host (`arcturus`), the NetBooter endpoints, outlet 5, and the timings (tracked [HXP-3/4/6](questions.md#the-hexapod), pending HXP-7 that this is the current copy). The `pdu_power_toggle` action drives the NetBooter PDU over HTTP (`/cmd.cgi?rly=N`, `/status.xml`); the relay index is zero-based, so operator-facing outlet 5 is the wire call `rly=4`. Which of the two PDUs (`a` / `b`) powers the hexapod, and its IP, live in the operator's `~/access.json`, not the repo: that is the one deployment secret left ([HXP-5](questions.md#the-hexapod)). The script also runs an optional TCP controller-readiness check (port 5001) between power-on and IOC restart, gated on a configured controller IP; the drive is now confirmed as the Aerotech Automation1-iXR3 (#156), so only the controller IP would remain to fill in.

The recipe captures the **happy path only** (controller enabled on the first check). The script's real flow is conditional: if `HexapodAllEnabled` is not `1`, it rechecks after 3 s, then issues `caput 2bmHXP:EnableWork.PROC 1` and polls every 1 s up to 180 s. That branch is the v2 conditional-branch trigger; at v1 it stays an operator decision. The Equipment-BC fault and restore that bracket the ceremony, and the Caution registered against the controller, are separate commands in their own BCs, not recipe steps. A manual Y-dial correction also follows a reboot, but it acts on the stage rather than the controller, so it is a separate [Caution](cautions.md#y-dial-after-a-reboot) (`HXP-8`), not a recipe step.

**Status:** design, pending executor (see [What still needs to land](#what-still-needs-to-land)).

## What still needs to land

`dark_field` and `flat_field` reuse the registered `collect` action body and are conductible today; the baseline reduction that follows the capture is downstream of the recipe (reconstruction, unlike baseline reduction, is itself a recorded compute Method). `energy_setting` and `hexapod_reboot` are valid Recipe v1 data but invoke action bodies that are not registered yet, so conducting either would fail at the first unregistered step. They are recorded here so the step order, addresses, and tunable values are reviewable ahead of the executor work, which sits in the same deferred-runtime bucket as live motion. The specific blockers:

- **`energy_setting`**: the `coordinate_energy_move` action body; the Plan.wiring-backed `pseudoaxis://` constituent resolver (deferred); and the real readback (`.RBV`) PVs. The per-energy saved table is now populated with the real `store_0` values (ENERGY-1/2, in the [energy curves](inventory.md#energy-tracking-optic-axes)).
- **`hexapod_reboot`**: the `run_shell_script` / `pdu_power_toggle` / `sleep` / `caget_poll` action bodies (plus `caput` for the force-enable branch) and their substrate adapters (a shell or SSH execution port, an HTTP port for the PDU, a channel-access read/write port); and the [HXP-5](questions.md#the-hexapod) PDU secret.

## Candidate recipes

The deterministic legs of the three newly modeled [Procedures](procedures.md) are candidate recipes for the same future executor work: the close-to-target aperture of `slit_centering` and the per-blade sweep of `blade_throw_characterization` are flat setpoint / action sequences, while their centring and edge-fit legs (and the whole `detector_z_rail_alignment` search) stay at the edge because recipes carry no feedback loop. They are not authored as recipes yet; the procedures above model the act today.
