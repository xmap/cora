# Authorization rollout runbook

*Turning on the authorization gate at 2-BM without breaking the beamline. Records the starter Policy, the
reasoning behind what it does and does not permit, and what each live step actually did. Companion to
[Governance](governance.md), which describes the shape; this page describes the rollout.*

## Why a rollout needs a runbook at all

An allowlist can only be written from what a deployment has already done. Everything it has not yet needed is
absent, and absent means refused. That is a poor way to learn what a first Policy is missing, and a specifically
poor way to learn it at a beamline, because the commands most likely to be missing are the ones nobody has had
to use yet. Stopping a run is the sharpest case.

So the gate has a shadow posture. With `POLICY_POSTURE=shadow` the gate loads the Policy, reaches a real verdict,
records what it would have refused, and refuses nothing. The deployment behaves exactly as it did on the
permissive default. The refusals it did not apply are the inventory from which a real Policy gets written.

```
  POLICY_POSTURE=enforce   (default)   a refusal is applied
  POLICY_POSTURE=shadow                a refusal is recorded and dropped
  TRUST_POLICY_ID unset                there is no gate at all
```

There are two spellings, not three, and "off" is the third row above rather than a posture value. A second way
to say off is how a deployment ends up believing it is gated when it is not.

## The starter Policy

Defined 2026-08-31, id `01a057d2-9460-7980-954f-d9722c8d6938`, name `2-BM operators on the HTTP surface`.

| Axis | Value | Why |
| --- | --- | --- |
| `conduit_id` | nil sentinel | Every handler passes the nil sentinel today; Conduit injection is not wired. |
| `surface_id` | seeded HTTP Surface | The Surface operator traffic actually arrives on. Matching is strict. |
| `permitted_principal_ids` | operator seats A and B | See below. |
| `permitted_commands` | 58 names | See below. |

### Principals: only the seats the repository can account for

The deployment has four registered `human` Actors. Two are the operator seats pinned in
`cora.api.beamline_staff_seed` under deployment-stable ids. The other two were registered ad hoc during
commissioning in August, and their ids appear nowhere in the repository.

The starter Policy names the two pinned seats only. The rule is that a Policy may name a principal the
repository can account for, because a Policy referencing ids that exist nowhere in source cannot be reviewed,
cannot be reproduced on a fresh deployment, and cannot be explained to anyone later. The two commissioning
actors are left out deliberately, and the shadow period counts how much real work they did, which is a number
worth having before deciding whether to adopt them as seats or migrate their work to the pinned ones.

`SYSTEM_PRINCIPAL_ID` is also left out, and that omission is the most important one on this page. It is the
fallback principal that a request with no `X-Principal-Id` header runs as, and essentially all operator traffic
at 2-BM is header-less today. Permitting it would make the numbers look healthy while granting every caller
that can reach the port the full permitted command set, which is not a gate. Excluding it makes the shadow
period measure the one quantity that has to be known before enforcement: how much of this beamline's work is
done by nobody in particular.

### Commands: chosen by intent, cross-checked against history

The set is derived from what an operator at this beamline should be able to do, then checked against what the
deployment has actually issued. It is not the observed command list, because mirroring history would reproduce
history's gaps, and the gaps are the problem.

| Group | Reason for inclusion |
| --- | --- |
| Every brake (`StopRun`, `HoldRun`, `AbortRun`, `TruncateRun`, `HoldProcedure`, `AbortProcedure`, `TruncateProcedure`, `HoldVisit`) | Nothing exempts a brake from the Policy conjunct. Omitting one means an enforcing Policy refuses to let someone stop work. |
| Recording what already happened (`CompleteRun`, `CompleteProcedure`, `EndProcedureIteration`, `AppendProcedureActivities`) | The photons already hit the detector. Refusing the append does not un-run the scan, it only makes the record wrong. |
| The conduct path | What the beamline does. |
| Recipe and capability authoring | Preparing that work. |
| The clearance chain | The safety review this beamline runs. |
| Observation and supply ingest | Keeping the record current. |
| Reads for the subjects above | Reads traverse the same gate. A Policy that omits them makes the API unreadable under enforcement. |
| `DefinePolicy`, `RegisterActor` | Without them, enforcing this Policy removes the ability to author the next one. |

All 58 names were checked against the command names the source actually declares before the Policy was defined.
A misspelled command name in an allowlist is silently inert: it never matches, so it neither permits nor errors,
and the Policy simply refuses something its author believed it allowed.

Deliberately absent, in each case so the shadow period measures it rather than hiding it: every agent-raised
command, every remaining command in the wider surface, and the seed and bootstrap ceremonies. The ceremonies are
absent for a second reason as well, confirmed in source rather than assumed: `pilot_seed` builds its own kernel
with the permissive stub, and the equipment and family bootstraps write events directly, so no seeding path
consults the configured Policy and enforcement cannot break a re-seed.

## What happened on 2026-08-31

**The shadow posture reached the deployment.** Applied as a single trust-only patch onto the deployed head rather
than a jump to current main, so that the restart's blast radius was the gate and not the conduct path. Service
restarted clean, code inert with no policy id set.

**The starter Policy was defined** through `POST /policies`, while the gate was still permissive, and read back
from the event store with the shape above.

**Pointing the deployment at it failed the boot, correctly.** Setting `TRUST_POLICY_ID` tripped a guard that
refuses a configured policy id unless `REQUIRE_AUTHENTICATED_PRINCIPAL` is also on, because a spoofed
`X-Principal-Id` would otherwise win standing admin under the Policy. The service crash-looped for roughly four
minutes and was restored by removing the two environment lines.

The guard was right about enforcement and wrong about shadow, and the difference matters enough to state
plainly. A shadowed gate refuses nothing, so there is no gate to bypass and no admin to win; the deployment is
behaviourally what it already was, where the same caller could already issue the same command as the same
spoofed principal. Meanwhile turning the header check on is itself unshadowable, because it answers 401 at the
boundary above the gate, where no posture softens it, and header-less is how nearly all operator traffic
arrives. The guard therefore made the safe rollout reachable only through the unsafe one. It now reads both
postures and fires when either conjunct actually refuses, which keeps the protection at the boot that turns
enforcement on.

## Where the shadow inventory lands, and where it does not

The near-misses are recorded as `trust_authorize.policy_shadow_near_miss` warnings in the service log, each
carrying the principal, the command, the Surface, and the refusal that was not applied.

They are **not** in the verdict logbook, and that is worth stating because the design intends them to be. The
gate writes one `Verdict` row per decision to the logbook of the Conduit the command traversed, and the row is
skipped when that Conduit has none open. This deployment has no Conduit streams at all, and every handler
routes through the nil sentinel, so no verdict row can be written for any decision, shadowed or enforced. The
`trust_authorize.verdict_log_dormant` boot warning exists to say so. Until Conduit injection is wired, the
authorization record lives in the log rather than in the record, which is a real gap in a system whose claim is
that the record is the artifact.

## Rollback

Removing the `TRUST_POLICY_ID` and `POLICY_POSTURE` lines from the service environment and restarting returns
the deployment to the permissive default. The Policy stream stays where it is; a Policy nothing points at
decides nothing. Reverting the code is `git checkout main-deploy` and a restart.
