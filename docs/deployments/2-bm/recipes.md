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

The station shutter has three PVs in play, not one, corrected 2026-08-27 against TomoScan's own deployed autosave configuration (`2bmb:TomoScan:{Open,Close}ShutterPVName`), which is the beamline's own working reference for this switch: `S02BM-PSS:SBS:OpenEPICSC` and `S02BM-PSS:SBS:CloseEPICSC` are the momentary command PVs (write `1` to fire), and `S02BM-PSS:SBS:BeamBlockingM` is a status read-back only, inverted (1 means blocked/closed). An earlier draft of this recipe wrote the setpoint straight to `BeamBlockingM`; that PV is read-only-in-practice everywhere else in the codebase (permit monitoring, the safety envelope) and was never TomoScan's write target either. See [Enclosures](enclosures.md) for the full PSS signal set.

**A check on an enum PV compares against the LABEL, not the number.** Measured live on 2026-08-27: `BeamBlockingM` is a two-state enum whose choices are `[0] OFF` and `[1] ON`, and `EpicsCaControlPort` resolves a `DBR_ENUM` against the labels cached from the record, so a read surfaces the string `"ON"`. The "1 means blocked" convention above describes the RAW value the PLC holds, which is not what a criterion sees. A first conduct wrote correctly and then failed its own check with `value 'ON' did not equal expected 1`; the tables below now expect the label. The same applies to every other enum PV a recipe checks.

**`verify` is evidence, never a gate, and that is load-bearing here.** The same conduct recorded `post_reading: ""` on a setpoint that demonstrably succeeded: `CloseEPICSC` is momentary and had already self-reset before the post-write read landed. A verify that halted on mismatch would have failed a good write. Anything needing halt-on-mismatch uses a check step against the STATUS record, which is exactly why these recipes pair every command with one.

Both momentary-command questions are now answered by the same run: writing `1` to `CloseEPICSC` while the shutter was already closed completed cleanly and left the beamline byte-identical, so the command self-resets and is safe to repeat. APS PSS sign-off on the leaf names is still outstanding.

**`collect`'s `detector` parameter is a PV prefix with NO trailing colon, and it includes the camera's `cam1` segment.** The action body builds each address as `{detector}:TriggerMode`, `{detector}:AcquireTime` and so on, so the correct value at 2-BM is `2bmSP1:cam1`. An earlier version of the tables below read `2bmSP1:`, which is wrong twice over: the trailing colon produces a doubled separator, and the `cam1` segment is missing entirely. A conduct on 2026-08-31 failed at the capture step with `Control address '2bmSP1::TriggerMode' not connected`, which is what that mistake looks like from the outside. The seed code in `pilot_seed.py` always carried the correct form; only these tables were wrong.

**A check step's `timeout_s` decides between two different questions, and only one of them should wait.** A check can carry an optional `timeout_s`: absent (the default), the check reads once and a mismatch halts, byte-identical to before this field existed; present, the check reads once and, only if the criterion does not already hold, waits for it up to the deadline, judging whatever it last saw if the deadline expires. Whether to set it depends on what the check is asking. An **arrival check** asks "did the thing I just commanded actually happen": it follows a setpoint or an action that moves something, and the record it reads lags the command by however long the substrate takes to catch up, so it needs a deadline generous enough to clear that lag. A **gate check** asks "is this true right now": for example, whether a hutch is secured or a permit is clear, and an instantaneous read is correct there; waiting ten seconds for a hutch to become secured would not be a safety check, it would be a bug. Both are written the same way, a check step with a criterion and an optional `timeout_s`, so a recipe author has to choose deliberately rather than by default.

For the station shutter this is grounded: the status PV scans at 1 Hz and the command is a 1 second pulse, so roughly 2 seconds of substrate latency precede the device (measured 2026-08-28 on real EPICS). Because a check with a deadline still returns the instant the criterion holds rather than waiting out the whole deadline, generosity costs nothing on the happy path and only delays how fast a genuinely stuck shutter is reported, so `timeout_s: 10` is the sensible choice for every shutter check below. No comparable measurement exists yet for the energy-tracking optic axes or any other motor at 2-BM; sizing a motor arrival check needs a real settle-time measurement first, so `energy_setting`'s axis checks are flagged below rather than given an invented number.

### `dark_field`

**Realizes** [`cora.capability.acquisition`](../../catalog/capabilities.md). Shutter closed, no beam: capture a dark-frame stack for reconstruction subtraction.

**Binds:** `repetitions` (frame count), `dwell` (per-frame exposure).

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `S02BM-PSS:SBS:CloseEPICSC` (StationShutter, close command) | `1` (verify) |
| 2 | check | `S02BM-PSS:SBS:BeamBlockingM` (StationShutter, status read-back) | `== "ON"` (closed), `timeout_s: 10` |
| 3 | action | `collect` | `{ detector: "2bmSP1:cam1", repetitions: <<repetitions>>, dwell: <<dwell>> }` |

Step 2 is an **arrival check**: it follows the close command, not a standing fact. It reads correctly today even without a deadline because the shutter's resting state at 2-BM is closed, so the criterion is usually already true before the check runs, but that is a fact about the beamline's rest state, not about the check, and it would not hold if the shutter happened to be open when this recipe ran. `timeout_s: 10` puts it on the same footing as `flat_field`'s checks below rather than leaving it correct by coincidence.

**Status:** steps 1 and 2 were conducted against real hardware on 2026-08-27 and completed (`actuation_kind: Physical`), before `timeout_s` existed; that conduct exercised the pre-fix instantaneous read, which passed because the shutter was already closed. Step 3 is NOT yet conductible: `collect` writes the substrate-neutral string `"Internal"` to `2bmSP1:cam1:TriggerMode`, and that record is a two-value enum accepting only `Off` / `On`. The Oryx is an ADSpinnaker camera, not generic ADCore, so the trigger vocabulary does not map. Conducting this recipe whole would halt at the capture step until that mapping is fixed.

### `flat_field`

**Realizes** [`cora.capability.acquisition`](../../catalog/capabilities.md). Shutter open, no sample in the beam: capture a flat-field stack for reconstruction division.

**Binds:** `repetitions`, `dwell`.

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `S02BM-PSS:SBS:OpenEPICSC` (StationShutter, open command) | `1` (verify) |
| 2 | check | `S02BM-PSS:SBS:BeamBlockingM` (StationShutter, status read-back) | `== "OFF"` (open, inverted polarity), `timeout_s: 10` |
| 3 | action | `collect` | `{ detector: "2bmSP1:cam1", repetitions: <<repetitions>>, dwell: <<dwell>> }` |

Step 2 is the motivating **arrival check** for the deadline field: it follows the open command, and unlike the close side, open is not the shutter's resting state, so this check cannot rely on the criterion already being true. Without `timeout_s` a check fired immediately after the open command reads the shutter mid-travel and halts on a false negative.

**Closing steps** (see [glossary](../../reference/glossary.md#recipe-ladder)): walked once `steps` above reaches a real terminal (Completed or Aborted), so the shutter closes even if the capture halts partway through instead of only on a clean run.

| # | Step | Address | Value / params |
| --- | --- | --- | --- |
| 1 | setpoint | `S02BM-PSS:SBS:CloseEPICSC` (StationShutter, close command) | `1` (verify, return to safe state) |
| 2 | check | `S02BM-PSS:SBS:BeamBlockingM` (StationShutter, status read-back) | `== "ON"` (closed), `timeout_s: 10` |

This closing check is the same **arrival check** as `dark_field`'s: it follows a close command and gets the same deadline for the same reason.

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
| 7-11 | check | each axis readback (`.RBV`) *(illustrative)* | `within_tolerance`, `timeout_s`: **needs measurement** |

The setpoint positions shown are illustrative curve outputs and are **provisional**: the per-energy curves await the real saved-position table from 2-BM staff. The curve-interpolation runtime (`eval_lookup_table`) exists, but a live free-keV recipe is still blocked on two things: the saved per-energy table is not populated, and the Plan.wiring-backed constituent resolver that would let the recipe address the five facets as `pseudoaxis://` constituents is deferred. So a v1 recipe encodes **one energy's resolved positions** as literal setpoints, one recipe per saved energy. The saved menu here is the **Mono** menu (the configured energies are listed on the [energy-tracking optic axes](inventory.md#energy-tracking-optic-axes)); `energy_setting` as written is the mono-mode recipe, and pink-mode energy selection is deferred with the [beam-mode work](questions.md#beam-mode) (`MODE-3` / `MIRROR-1`). `energy_kev` is recorded but does not drive live position computation at v1; once the saved table lands and the resolver ships, the runtime can interpolate an in-between energy (for example 22 keV, between the saved 20.0 and 25.0) rather than only the menu points.

Steps 7-11 are the recipe most exposed to the defect the check-step deadline fixes: five motor setpoints followed by five **arrival checks**, one per axis, each asking whether that axis actually reached its commanded position. Every one of them needs `timeout_s`. Unlike the shutter, there is no measured settle time for these axes, or for any motor at 2-BM, in this repository: the 2 second shutter figure comes from a scanned status PV and a momentary command pulse, neither of which describes a motor's move-and-settle behavior. Inventing a number here would look like the same kind of grounded sizing the shutter got and would not be; the table above marks it **needs measurement** rather than guessing. This is one more reason the recipe stays "design, pending executor": the real `.RBV` addresses are not pinned yet either, so there is nothing to measure against until both land.

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

Steps 2, 4, 7, and 11 are each an **arrival check**: they follow an action that changes real-world state (stop a process, toggle a relay, restart a process) and ask whether that state actually landed, so each would need a deliberate `timeout_s` once it is wired to a real address and criterion rather than the placeholder targets shown. This table carries no measured timing for any of them (how long the IOC takes to actually stop, how long the PDU's own status read lags a toggle), so no number is proposed here; the surrounding `sleep` actions are the pre-existing, coarser-grained way this recipe already compensates for exactly this kind of lag, and are a different mechanism from a check's own deadline. Step 13 is different in kind: `caget_poll` immediately before it (step 12) already polls the same PV up to 180 s with its own `timeout_s`, so by the time step 13 reads, arrival has already been confirmed by the poll. Step 13 is correctly an instantaneous read, a **gate check** on a value the previous step already waited for, not a second arrival check.

Every record above is confirmed against the authoritative reboot script, pinned at [`decarlof/2bmb-bin@372285c6`](https://github.com/decarlof/2bmb-bin/blob/372285c69492/hexapod_reboot.py) (HXP-3/4/6/7): the enable PVs (`2bmHXP:HexapodAllEnabled.VAL` read, `2bmHXP:EnableWork.PROC` force-enable), the IOC scripts, the host (`arcturus`), the NetBooter endpoints, outlet 5, and the timings. Staff confirmed that repo as the current production source on 2026-07-28, having read the deployed `/home/beams/2BMB/bin/hexapod_reboot.py` against it; the check was constant-level rather than byte-level, and the pin is the last commit to touch the file (2026-02-25, matching the deployed copy's date). CORA cites the commit rather than `HEAD` so the record stays true after the next edit. The upstream of that fork is `xray-imaging/2bmb-bin`, but the fork is what was compared against the beamline, so the fork is what is cited.

`2bmHXP:DisableHexapod.PROC` is the matching disable, available on the same panel. It is recorded as command surface, not built into a recipe: nothing yet needs to disable the hexapod deliberately.

The `pdu_power_toggle` action drives the NetBooter PDU (5 outlets, hexapod on outlet 5, `10.54.113.66`) over HTTP (`/cmd.cgi?rly=N`, `/status.xml`); the relay index is zero-based, so operator-facing outlet 5 is the wire call `rly=4`, and the operator screen's "PDU 1" is the script's `pdu a` (HXP-5). Its credentials stay in the operator's `~/access.json` and belong to deployment configuration, not to any Asset record. The toggle is edge-triggered rather than a level, which is why each power step above is paired with a check: pressing without reading first can leave the outlet in the state it started in.

The script also runs a TCP controller-readiness check (port 5001) between power-on and IOC restart, followed by a fixed 5 s firmware settle. It is skipped only when no controller IP is configured, so it is a real step rather than an optional one; it earns a place in the recipe once that IP lands. The drive is confirmed as the Aerotech Automation1-iXR3 (#156).

The recipe captures the **happy path only** (controller enabled on the first check). The script's real flow is conditional: if `HexapodAllEnabled` is not `1`, it rechecks after 3 s, then issues `caput 2bmHXP:EnableWork.PROC 1` and polls every 1 s up to 180 s. That branch is the v2 conditional-branch trigger; at v1 it stays an operator decision. The three durations the recipe binds are also not the whole budget: the controller and IOC readiness waits are 120 s each and the enable poll is 180 s, so the happy path lands near the "~2 min" `item_050` quotes while the worst case is closer to eight minutes.

The Equipment-BC fault and restore that bracket the ceremony, and the Caution registered against the controller, are separate commands in their own BCs, not recipe steps.

The reboot no longer ends with a manual Y-dial correction; staff confirmed on 2026-07-28 that the axes come back homed with user coordinates reset (HXP-8). CORA records the resulting [coordinate convention](inventory.md#hexapod-dof-model) but not a homing postcondition on this recipe, because nothing here performs the homing: the pinned script contains no homing step, and neither IOC wrapper does. Whatever re-homes the axes sits outside what HXP-7 certified, and until it is named ([HXP-9](questions.md#the-hexapod)) the recipe cannot claim a homed hexapod as its own outcome.

**Status:** design, pending executor (see [What still needs to land](#what-still-needs-to-land)).

## What still needs to land

`dark_field` and `flat_field` reuse the registered `collect` action body and are conductible today; the baseline reduction that follows the capture is downstream of the recipe (reconstruction, unlike baseline reduction, is itself a recorded compute Method). `energy_setting` and `hexapod_reboot` are valid Recipe v1 data but invoke action bodies that are not registered yet, so conducting either would fail at the first unregistered step. They are recorded here so the step order, addresses, and tunable values are reviewable ahead of the executor work, which sits in the same deferred-runtime bucket as live motion. The specific blockers:

- **`energy_setting`**: the `coordinate_energy_move` action body; the Plan.wiring-backed `pseudoaxis://` constituent resolver (deferred); and the real readback (`.RBV`) PVs. The per-energy saved table is now populated with the real `store_0` values (ENERGY-1/2, in the [energy curves](inventory.md#energy-tracking-optic-axes)).
- **`hexapod_reboot`**: the `run_shell_script` / `pdu_power_toggle` / `sleep` / `caget_poll` action bodies (plus `caput` for the force-enable branch) and their substrate adapters (a shell or SSH execution port, an HTTP port for the PDU, a channel-access read/write port). The PDU address and outlet are now known; only the credentials are deployment configuration.
    A further blocker surfaced when HXP-4 confirmed the two IOC script names: both are operator-desktop wrappers that open a `gnome-terminal` tab and run `ssh -t` interactively. A headless executor cannot invoke them as written. The recipe keeps the wrapper names, because they are what an operator runs, but `run_shell_script` will have to reach the launcher they wrap (`2bmHXP.pl stop` / `run`, under `iocBoot/ioc2bmHXP/softioc/` on `arcturus`) over a plain SSH port instead.

## Candidate recipes

The deterministic legs of the three newly modeled [Procedures](procedures.md) are candidate recipes for the same future executor work: the close-to-target aperture of `slit_centering` and the per-blade sweep of `blade_throw_characterization` are flat setpoint / action sequences, while their centring and edge-fit legs (and the whole `detector_z_rail_alignment` search) stay at the edge because recipes carry no feedback loop. They are not authored as recipes yet; the procedures above model the act today.
