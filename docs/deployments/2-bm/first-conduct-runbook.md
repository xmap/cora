# First conducted operation runbook

*The supervised procedure for the first time CORA drives 2-BM hardware itself,
rather than recording what TomoScan drove. Written to be read start to finish
before anything is changed, and followed with a second person watching.*

Until this runbook is executed, CORA has never written a PV at 2-BM. The pilot
has been observe-only since 2026-08-09 with `CONTROL_WRITES_ENABLED=false`,
which is the deployment-wide safety switch and cannot be partially applied.

## What this test does and does not do

It conducts one Recipe, [`dark_field`](recipes.md#dark_field), end to end: CORA
commands the station shutter closed, confirms it is closed, and captures a
frame stack. Three steps, two Assets.

It deliberately does NOT conduct [`flat_field`](recipes.md#flat_field), which is
its natural sibling. `flat_field` opens the shutter, and the reason that matters
is in [The settle gap](#the-settle-gap) below.

## Why dark_field is the honest first conduct

Its check is timing-independent. The station shutter's resting state at 2-BM is
closed, so a conduct that commands it closed asserts a state the beamline is
already in. If the write silently failed, the check would still pass, which
sounds like a weakness and is in fact the point: this run is proving the CHAIN
(Recipe expands, Procedure registers, Conductor drives a real substrate, steps
land in the record) rather than proving the shutter moves. Motion is the second
test, not the first, and it needs the settle gap closed.

What the run does prove is not nothing. The `collect` action body performs real
detector writes (`TriggerMode`, `AcquireTime`, `NumImages`, `Acquire`) and polls
`Acquire_RBV` to completion, so a real actuation with a real observable outcome
does happen, against hardware, recorded end to end.

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

Two things have to land before an opening conduct is attempted:

1. A measured shutter response time, from the beamline rather than from a guess.
2. Either a settle mechanism (a registered wait or a polling check) or a
   documented response time small enough that the question is moot. Adding an
   action body is new production surface and takes its own gate review.

## Route scoping: the trap to avoid

`CONTROL_WRITES_ENABLED=true` is all-or-nothing. The live route table on
arcturus declares eleven prefixes and **not one of them sets `read_only`**,
because today the global switch alone holds every write back. Flipping that
switch without first pinning the routes would make all eleven writable at once,
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

Add `"read_only": true` to all eleven existing routes:

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
| 1 | `OpenEPICSC` / `CloseEPICSC` are momentary commands that self-reset, and re-sending `1` when the shutter is already in that state is harmless | The recipe writes `1` to close an already-closed shutter. If that write has any other effect, the premise of the test is wrong |
| 2 | No concurrent writer during the window (TomoScan GUI, operator script, another CA client) | Two writers on one shutter is the failure mode no amount of CORA-side care prevents |
| 3 | The detector settings this test overwrites are expendable, or are recorded first | `collect` writes `TriggerMode`, `AcquireTime` and `NumImages` on `2bmSP1:cam1` and does NOT restore them. Whatever TomoScan had configured there is left at this test's values afterwards |
| 4 | Hutch state is understood | Measured 2026-08-27: `StaA:SecureM` and `StaB:SecureM` both read OFF and `SR-ACIS:2BM:FesPermitM` reads OFF. No beam is permitted, which is a safe posture for this test, but an unsecured hutch may mean someone is working inside |

Precondition 3 is the one most easily missed, because it is a side effect of a
step that otherwise looks read-only in intent. Record the three values with
`caget` before the run if they matter to the next scan.

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
