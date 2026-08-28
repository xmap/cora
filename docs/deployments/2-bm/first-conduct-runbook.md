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
the shutter, and the reason that matters is [The settle gap](#the-settle-gap).

## Why the shutter-close assertion is the honest first conduct

Its check is timing-independent. The station shutter's resting state at 2-BM is
closed, so commanding it closed asserts a state the beamline is already in. If
the write had silently failed, the check would still have passed, which sounds
like a weakness and is the point: this run proves the CHAIN (Recipe expands,
Procedure registers, Conductor drives a real substrate, steps land in the
record) rather than proving the shutter moves. Motion is the second test, and it
needs the settle gap closed first.

## The settle gap

`CheckStep` is a single instantaneous read. Any of a read error, a non-Good
quality, or a criterion mismatch halts the conduct with a recorded failure.
There is no settle, no retry, no timeout, and no `sleep` or poll action body
registered in production (the Conductor's registry holds exactly `collect`,
`discrete`, `continuous`, `stream`).

A shutter is not instantaneous. A check fired immediately after an open command
reads the shutter mid-travel and halts on a false negative. The scenario test
`test_2bm_flat_field.py` never surfaces this, because its soft-IOC PV flips the
instant it is written; that is a fixture that cannot show this defect class.

One thing has to land before an opening conduct is attempted: a way for a check
to wait. Nothing else.

An earlier draft of this page also demanded a measured shutter response time
first. That was wrong, and the records themselves say why. Measured 2026-08-28:

```
S02BM-PSS:SBS:BeamBlockingM.SCAN   1 second     status is polled at 1 Hz
S02BM-PSS:SBS:CloseEPICSC.HIGH     1            command is a 1 s pulse
S02BM-PSS:SBS:CloseEPICSC.RTYP     bo           NOT a busy record
```

The shutter's own travel time is masked by the 1 Hz scan and cannot be
recovered from this PV, so it is not merely unmeasured but largely
unobservable. It also does not matter: a check that waits passes as soon as the
value arrives, whatever the latency turns out to be. The number was only ever
needed to size a fixed wait, and a fixed wait is the wrong mechanism.

What the same reads DO settle is that put-completion cannot help here.
`CloseEPICSC` and `OpenEPICSC` are plain `bo` records with no busy record
anywhere in the path, so a callback-style write returns when the record
finishes processing and says nothing about the shutter. That is why TomoScan
sleeps 2 s ON TOP of `put(wait=True)`, and that 2 s now reads as a command
pulse plus a scan period plus margin rather than a guess.

The fix is design-locked: a deadline-bearing check over the
`ControlPort.subscribe` seam that already exists on every substrate, never a
`sleep` action body.

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
