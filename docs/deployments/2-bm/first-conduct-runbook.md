# First conducted operation runbook

*The supervised procedure for the first time CORA drives 2-BM hardware itself,
rather than recording what TomoScan drove. Written to be read start to finish
before anything is changed, and followed with a second person watching.*

The pilot ran observe-only from 2026-08-09 with `CONTROL_WRITES_ENABLED=false`,
the deployment-wide safety switch, which cannot be partially applied.

## EXECUTED 2026-08-27

CORA drove 2-BM hardware for the first time. Procedure
`01a04581-ea57-7cf3-892b-558fc69680fe`: `succeeded: true`,
`completed_count: 2`, `actuation_kind: Physical`. It wrote `1` to
`S02BM-PSS:SBS:CloseEPICSC` over Channel Access and gated on the status
readback. The beamline was verified byte-identical to its recorded baseline
afterwards, and the deployment was returned to `actuation: inert` the same
session.

The genesis it recorded is the artifact:

```
ProcedureStarted    beam_requirement: "NotRequired"  beam_state_at_start: "Blocked"
ProcedureCompleted  actuation_kind: "Physical"
```

A reader can tell from that alone that the work ran with beam ABSENT under a
DECLARED exemption, rather than because beam happened to be available.

The rest of this page stays as the procedure to repeat, with what the run
taught folded in.

## EXECUTED 2026-08-30: the shutter OPEN command, refused by the PSS

The first attempt to open the shutter under CORA, run with no stored beam
(ring current about 3e-04 mA), the front-end shutter closed, and both hutches
secured. A narrow writable route for `S02BM-PSS:SBS:OpenEPICSC` was added for
the window and `CONTROL_WRITES_ENABLED` turned on for about twenty minutes.

Procedure `01a05424-d528-7cc1-a3c8-fde6009cb16e`: `succeeded: false`,
`completed_count: 1`, `actuation_kind: Physical`,
`substrate_writes: {OpenEPICSC: 1, CloseEPICSC: 1}`, `closing_failures: []`.

CORA's write reached the real command PV. The shutter did not open, because
`SR-ACIS:2BM:FesPermitM` and `S02BM-PSS:FES:FEEPSPermitM` both read `OFF`: the
PSS interlock chain refused, which is the safety system behaving exactly as
designed. The arrival check then waited its full 10 second deadline and failed
naming the real observed value, `value 'ON' did not equal expected 'OFF'`.

The point of the run is what happened next. The Procedure ABORTED, and the
closing steps ran anyway: they commanded the shutter closed and confirmed it
closed, with no closing failures. That is the first live exercise of closing
steps on real hardware, and an abort is a better exercise than a clean run,
because a clean run would only have tested the Completed path.

What this run did NOT prove: that CORA can open the shutter. It proved the
write reaches the hardware and the interlock refuses when permits are down.
Proving the open needs a window with permits granted, which is a beam-on ask.

## EXECUTED 2026-08-31: camera capture and the first commanded motion

Two commissioning conducts in one window, again with no beam.

**`dark_field` whole, including the capture step: FAILED, and usefully.**
Procedure `01a05554-b739-76b1-8293-96ac7eb43d7f`, `completed_count: 2`. The
shutter close and its check passed; `collect` failed with
`ControlNotConnectedError: Control address '2bmSP1::TriggerMode' not
connected`. The cause was the `detector` parameter, not the trigger-mode
mapping this page previously blamed: see the `collect` note in
[Recipes](recipes.md). The camera was left untouched because the failure
landed on the first detector write, so no settings needed restoring. The
`ADSpinnaker` trigger mapping remains UNPROVEN against hardware; this run
never reached it.

**`SampleTop_X` 0.1 mm move and return: SUCCEEDED.** Procedure
`01a05554-cd36-7c10-8f5d-a2c1dd4f0327`: `succeeded: true`,
`completed_count: 4`, `closing_failures: []`, axis back at 3.3 mm. This is the
first motion CORA has ever commanded at 2-BM.

Read what it proves narrowly. `2bmb:m18` reports `MSTA = 2`, so the
encoder-present bit is clear: it is an open-loop stepper, and `.RBV` is the
controller's own step count rather than an independent measurement. The
arrival check therefore confirms that the controller believes it issued the
steps, NOT that the stage physically moved. The conduct also completed in
492 ms, where two 0.1 mm moves at the record's `VELO` and `ACCL` should take
roughly twice that, which is unexplained and consistent with at least one
check finding its criterion already satisfied. Treat "CORA commanded a motor
and the record agreed" as the claim, and nothing stronger.

A survey of `MSTA` across the sample stack and hexapod, and which axes can
actually witness their own arrival, is in [Inventory](inventory.md).

## What this test does and does not do

It conducts the shutter half of [`dark_field`](recipes.md#dark_field): CORA
commands the station shutter closed and confirms it is closed. Two steps.

The capture step is deliberately NOT included. `collect` writes the
substrate-neutral string `"Internal"` to `2bmSP1:cam1:TriggerMode`, a two-value
enum accepting only `Off` / `On` (the Oryx is ADSpinnaker, not generic ADCore),
so the conduct would halt there. Dropping it also removed this runbook's one
irreversible side effect, since `collect` overwrites detector settings and
restores none of them.

It also does NOT conduct [`flat_field`](recipes.md#flat_field). That one opens
the shutter, and opening is where a check has to wait for the shutter to
arrive rather than read once. The mechanism that makes such a check safe has
since shipped, see [The settle gap, closed](#the-settle-gap-closed), but
nothing here uses it yet: the `flat_field` open check in
[Recipes](recipes.md#flat_field) still has no `timeout_s` set, so conducting
it today would hit the same false-negative risk the fix exists to prevent.
The capture step also still has the `TriggerMode` blocker described above,
since `flat_field` reuses `collect`.

A `flat_field` conduct needs three things, none of which is the settle gap:

1. A recipe author deliberately setting `timeout_s` on the open check.
2. The trigger-mode mapping this page's shutter-only conduct sidesteps.
3. A writable route for `S02BM-PSS:SBS:OpenEPICSC`, which does not exist.
   Confirmed against the live route table on 2026-08-30: the open command
   has no narrow route of its own, so longest-prefix match sends it to the
   broad read-only `S02BM-PSS:` route and it stays refused even after
   `CONTROL_WRITES_ENABLED` is turned on. That asymmetry with `CloseEPICSC`
   is deliberate, see [The route change](#the-route-change), so adding the
   route is a decision to make on purpose rather than a step to follow.

## Why the shutter-close assertion is the honest first conduct

Its check is timing-independent. The station shutter's resting state at 2-BM is
closed, so commanding it closed asserts a state the beamline is already in. If
the write had silently failed, the check would still have passed, which sounds
like a weakness and is the point: this run proves the CHAIN (Recipe expands,
Procedure registers, Conductor drives a real substrate, steps land in the
record) rather than proving the shutter moves. Motion is the second test, and
the fix that unblocks it is described next, though no recipe has picked it up
yet.

## The settle gap, closed

`CheckStep` used to offer exactly one behavior: a single instantaneous read,
where a read error, a non-Good quality, or a criterion mismatch halted the
conduct with a recorded failure. There was no settle, no retry, no timeout,
and no `sleep` or poll action body registered in production (the Conductor's
registry holds exactly `collect`, `discrete`, `continuous`, `stream`).

A shutter is not instantaneous. A check fired immediately after an open
command reads the shutter mid-travel and halts on a false negative. The
scenario test `test_2bm_flat_field.py` never surfaced this, because its
soft-IOC PV flips the instant it is written; that is a fixture that cannot
show this defect class.

This gap is now closed. `CheckStep` and `RecipeCheckStep` gained an optional
`timeout_s` field in commit `50c054d7c64`, "Let a check wait for its
criterion instead of asking once" (PR #736, landed 2026-08-28). When
`timeout_s` is absent, the default, behavior is byte-identical to before: one
instantaneous read, mismatch halts. When it is present, the check reads once
first, then consumes `ControlPort.subscribe`, already on the port contract
and already implemented by every adapter, until the criterion holds or the
deadline expires. On expiry, the last reading seen is judged by the same
mismatch branch as before, so a timeout raises the familiar
`CheckFailedError` naming the real observed value rather than a bare
timeout. A non-positive or non-numeric `timeout_s` is rejected at the recipe
wire parser rather than coerced: zero is not a synonym for absent. Journal
entries carry `waited_s`, 0.0 on the instantaneous path, so a check that
passed immediately stays distinct in the record from one that genuinely
waited.

Reading once before subscribing is the load-bearing detail, not an
optimization. A subscription delivers on change, and the common case is a
value that is already correct, which never changes into itself. A
subscribe-only implementation would wait out the whole deadline on exactly
the checks that pass instantly, reporting a false negative on healthy
hardware.

An earlier draft of this page also demanded a measured shutter response time
first. That was wrong, and the records themselves say why. Measured 2026-08-28:

```
S02BM-PSS:SBS:BeamBlockingM.SCAN   1 second     status is polled at 1 Hz
S02BM-PSS:SBS:CloseEPICSC.HIGH     1            command is a 1 s pulse
S02BM-PSS:SBS:CloseEPICSC.RTYP     bo           NOT a busy record
```

The shutter's own travel time is masked by the 1 Hz scan and cannot be
recovered from this PV, so it is not merely unmeasured but largely
unobservable. It also does not matter: a check that waits passes as soon as
the value arrives, whatever the latency turns out to be. The number was only
ever needed to size a fixed wait, and a fixed wait was always the wrong
mechanism.

What the same reads DO settle is that put-completion cannot help here.
`CloseEPICSC` and `OpenEPICSC` are plain `bo` records with no busy record
anywhere in the path, so a callback-style write returns when the record
finishes processing and says nothing about the shutter. That is why TomoScan
sleeps 2 s ON TOP of `put(wait=True)`, and that 2 s now reads as a command
pulse plus a scan period plus margin rather than a guess. Read it as the
latency a deadline has to CLEAR, not as a deadline value to copy: sizing is
below, and 2 s is the floor to stay well above.

**Verified against real EPICS on arcturus, 2026-08-28.** The deployment
stayed `inert` throughout: two read-only check Procedures against
`S02BM-PSS:SBS:BeamBlockingM`, no writes, nothing moved.

| Probe | Expect | `timeout_s` | Recorded `waited_s` |
| --- | --- | --- | --- |
| A | `ON` (already true) | 10 | 0.0 |
| B | `OFF` (never arrives) | 5 | 5.001924 |

Probe B is the load-bearing evidence: it shows the subscription actually
engaged (a broken `subscribe` would have returned 0.0), that the deadline
bounded the wait to under 2 ms of slop over the requested 5 s, and that the
last reading survived expiry, since the failure named the real observed
value, `value 'ON' did not equal expected 'OFF'`. Probe A is the negative
control for the read-first short-circuit: it confirms an already-satisfied
check returns immediately instead of waiting out the deadline. No leaked
monitors, beamline byte-identical afterwards.

**Sizing.** At 2-BM the status PV scans at 1 Hz and the command is a 1
second pulse, so roughly 2 seconds of substrate latency precede the device.
A deadline of a second or two would fail a healthy shutter. Generosity is
close to free here, because the check returns on arrival, not on expiry, so
something on the order of 10 seconds is the sensible choice for a shutter
check.

**Opt-in, and adoption is zero.** The mechanism is general and
direction-agnostic. Nothing in it knows about shutters, or about opening
versus closing; it applies to any check on any address on any substrate,
including motors and the hexapod. But it defaults off, and today no check
step in [Recipes](recipes.md) sets `timeout_s`, and there is no define-time
guard requiring one. A recipe whose check follows real motion still needs
its author to set the deadline deliberately. This matters most for
`energy_setting`, which drives five motors and then checks five axis
readbacks, and it is exactly what stands between this page and a
`flat_field` conduct (see [above](#what-this-test-does-and-does-not-do)).

Keep the distinction straight when writing a new check: an ARRIVAL check
("did the thing I just commanded happen?") needs a deadline, while a GATE
check ("is this true right now?", for example whether a hutch is secured) is
correct as an instantaneous read, because waiting for a hutch to become
secured would be wrong. Both are written the same way today, as a check step
with a criterion and an optional `timeout_s`, so the author has to choose
deliberately rather than by default.

## The enum-label gap, found by the same run

Separate from settle, and cheaper to fix. A check criterion on an enum PV must
expect the LABEL, not the raw number. `EpicsCaControlPort` resolves a
`DBR_ENUM` against labels cached from the record, so `BeamBlockingM` surfaces as
`"ON"`, while the descriptor's "1 = blocked" convention describes the raw value
the PLC holds. The first attempt wrote correctly and then failed its own check
with `value 'ON' did not equal expected 1`.

Live labels are `[0] OFF, [1] ON`. Any recipe checking any enum PV at this
beamline needs the same treatment; [Recipes](recipes.md) is corrected.

## Route scoping: the trap to avoid

`CONTROL_WRITES_ENABLED=true` is all-or-nothing. The live route table on
arcturus declares ten prefixes and **not one of them sets `read_only`**,
because today the global switch alone holds every write back. Flipping that
switch without first pinning the routes would make all ten writable at once,
including `2bmBLEPS:` (equipment protection), the whole `S02BM-PSS:` namespace,
`2bmHXP:` (hexapod) and every motor.

The second trap is inside the PSS namespace. `S02BM-PSS:` is a single broad
route covering both the shutter command records this test needs and the permit
and interlock records it must never touch. Making that one route writable would
open `StaA:SecureM`, `StaB:SecureM` and `FES:BeamBlockingM` along with it.

The registry resolves an address by **longest-prefix match**
(`control_port_registry.py`, routes sorted by descending prefix length, first
`startswith` wins), so a narrow writable route overrides a broad read-only one.
That is what makes the scoping below sound rather than hopeful.

## The route change

Edit `CONTROL_PORT_ROUTES` in `cora-env.sh` on the shared home. This is a
surgical change to an existing block, not a rewrite: preserve every existing
`text_addresses` entry exactly as it stands.

Add `"read_only": true` to all ten existing routes:

```
2bmBLEPS:    2bmHXP:     2bmSP2:    2bma:    2bmb:    2bm:
S02BM-PSS:   SR-ACIS:    2bmbAERO:  2bmSP1:  (see note below)
```

Then add the two narrow writable routes the test needs. These are longer than
`S02BM-PSS:` and `2bmSP1:` respectively, so they win the match:

```json
{"prefix": "S02BM-PSS:SBS:CloseEPICSC", "substrate": "epics_ca"},
{"prefix": "2bmSP1:cam1", "substrate": "epics_ca"}
```

`S02BM-PSS:SBS:OpenEPICSC` is deliberately NOT added. This test never opens the
shutter, so the open command stays unreachable, covered by the read-only
`S02BM-PSS:` route.

Note on `2bmSP1:`: the broad camera route carries
`text_addresses: ["2bmSP1:HDF1:FullFileName_RBV"]` and must keep it. Mark the
broad route `read_only` and let the narrow `2bmSP1:cam1` route carry the writes,
so the file-plugin records stay unwritable.

Then set:

```
CONTROL_WRITES_ENABLED=true
```

## Verifying the scoping before conducting anything

After restarting the service and BEFORE registering any Procedure, confirm the
posture from outside. `/readyz` reports a derived `actuation` field, and the
boot log line `boot.actuation_posture` prints the raw inputs beside the summary
so the claim can be audited rather than trusted:

```
ssh -L 8010:127.0.0.1:8010 2bmb@arcturus     # then curl localhost:8010/readyz
journalctl --user -u cora-api -n 50 | grep boot.actuation_posture
```

Expect `actuation` to read `reachable`, not `inert`. That is the honest report
once writes are on, and seeing it flip is itself the confirmation the config
took effect.

## Preconditions to confirm with beamline staff

Do not proceed until all of these hold.

| # | Precondition | Why it matters |
| --- | --- | --- |
| 1 | ANSWERED. `Close/OpenEPICSC.HIGH` is `1`, so both are one-second self-resetting pulses by construction, and the run confirmed it in practice: writing `1` to an already-closed shutter completed cleanly, left the beamline unchanged, and read back `""` after reset | The recipe writes `1` to close an already-closed shutter. If that write had any other effect, the premise of the test would be wrong |
| 2 | No concurrent writer during the window (TomoScan GUI, operator script, another CA client) | Two writers on one shutter is the failure mode no amount of CORA-side care prevents |
| 3 | MOOT while the capture step is excluded, and live again the moment it returns | `collect` writes `TriggerMode`, `AcquireTime` and `NumImages` on `2bmSP1:cam1` and restores none of them. Record the three with `caget` first; a baseline was saved as `camera-baseline-<stamp>.txt` on the shared home |
| 4 | Hutch state is understood | At the run: both hutches SECURED (`SecureM` ON), `FesPermitM` OFF, ring current 0.002 mA. No beam was permitted and nobody was inside. An UNSECURED hutch is the case to pause on, since it may mean someone is working in there |

Precondition 3 is the one most easily missed, because it is a side effect of a
step that otherwise reads as pure acquisition. It is dormant only for as long as
the capture step stays out of the recipe.

## The sequence

1. Confirm the preconditions above with staff.
2. Confirm the beamline is idle: `2bmb:TomoScan:ScanStatus` reads
   `Scan complete` and `2bmb:TomoScan:StartScan` reads `Done`.
3. Fetch the branch on lyra. Never fetch on arcturus: it has no route to
   GitHub and hangs for about five minutes rather than failing fast.
4. On arcturus, `git merge --ff-only origin/main` (local objects only, over the
   shared NFS home).
5. Stop the service deliberately: `systemctl --user stop cora-api.service`. A
   `kill` does not work; `Restart=always` respawns it in about a second.
6. Edit `cora-env.sh` per [The route change](#the-route-change).
7. Run the seed ceremony to register the Recipe. It is idempotent:
   `python -m cora.api.pilot_seed` (add `--dry-run` first to see what it would
   write).
8. Start the service: `systemctl --user start cora-api.service`.
9. Verify the posture per
   [Verifying the scoping](#verifying-the-scoping-before-conducting-anything).
10. Register a Procedure from the Recipe, then conduct it, with someone
    watching the shutter status and the log.
11. Read the record back: the Procedure's step entries carry the observed
    reading for each step, including the post-write evidence from `verify`.

## Rollback

`CONTROL_WRITES_ENABLED=false` in `cora-env.sh`, then restart. This is the
proven, fitness-tested switch and needs no other change; the route table can
keep its `read_only` flags, which are correct to leave in place permanently.

Because the unit sources `cora-env.sh` at each `ExecStart`, a `Restart=always`
loop picks up the edit on its next attempt without further action.
