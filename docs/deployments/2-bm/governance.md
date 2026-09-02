# Governance

*Who may act at 2-BM, and the trust policy that would gate their commands, if one were defined. Static config;
the per-run [decisions](experiment.md) operators and agents make are live, not here.*

## Who acts

Three named roles hold human principals at 2-BM today, seeded as `human` Actors by the
`cora.api.beamline_staff_seed` ceremony under pinned, deployment-stable ids. Their display names are personal
data: the ceremony writes each name only to the `actor_profile` PII vault, supplied at deploy time from the host
environment. The repository carries the pinned ids and the role labels and nothing else about these people: an id
is opaque, a role is not personal data, and no name, badge, ORCID, or address is checked in anywhere.
Facility-process principals (proposal PIs, the safety review board, the beamline scientist acting in a
review-chain capacity) are facility-wide and live at [APS](../aps/index.md#safety-and-governance). See
[Model](../../architecture/model.md) for the aggregate shape.

| Slot | Kind | Holds |
| --- | --- | --- |
| `2-bm-admin` | `human` | deployment administration |
| `2-bm-group-manager` | `human` | the imaging group, across more than one beamline |
| `2-bm-staff` | `human` | 2-BM itself |

The slots were `2-bm-operator-a` / `2-bm-operator-b` until the third role arrived. Only the labels changed: the
pinned ids are literals and did not move, because an id is what every grant already made hangs off, and re-pinning
one would leave a second Actor for the same person. That has happened here once already.

**A role carries no scope, and today that is a gap.** A `Policy` holds `(principal, command)` pairs gated by a
Conduit and a Surface; there is no beamline dimension in a grant. So "manages the imaging group across several
beamlines" and "staffs this one" are indistinguishable to authorization, and the group manager and the beamline
staff hold the same commands here. That costs nothing while CORA runs at a single beamline and becomes real at
the second. It is a gap in the Policy model rather than something a slot label can close, and it must not be
papered over by giving the two roles different COMMANDS: that would record a difference of scope as a difference
of capability, which is both false and hard to unpick later.

## The trust boundary

2-BM's boundary is shaped by the Trust BC aggregates (Zone, Conduit, Policy); the
[Trust module](../../architecture/modules/trust/index.md) defines what each one is. This page records only the
2-BM instances:

| Zone | Conduit | Endpoints |
| --- | --- | --- |
| `2-BM Zone` | `2-BM Local Conduit` | `2-BM Zone` -> `2-BM Zone` |

## Policy: defined, not yet pointed at

`TrustAuthorize` gates commands against exactly one configured Policy per deployment (`Settings.trust_policy_id`
is a single, optional `UUID`, not a collection). A deployment cannot run more than one Policy at a time, so a
two-Policy split (one for operator commands, a separate one for agent-issued Decision commands) is not a shape
`Settings` can express; any such split would have to be modeled inside one Policy's own permitted-principals and
permitted-commands rows instead.

A starter Policy now exists at 2-BM, named `2-BM operators on the HTTP surface`. It binds the nil Conduit and
the seeded HTTP Surface, permits the two operator seats above, and permits 58 command names. What it is for,
what it deliberately leaves out, and what the measurements say is in the
[authorization rollout runbook](authorization-rollout-runbook.md).

`trust_policy_id` is still unset, so the deployment continues to run on `AllowAllAuthorize`, the permissive stub
that admits every command from every principal regardless of Zone, Conduit, or Actor kind. The two seeded
operators are therefore still usable principals for hands-on testing, not principals a Policy has actually
vetted. A Policy that exists and a Policy that decides are two different things, and only the first is true
today.

Three properties of the Policy shape are worth reading before anyone writes the next one, because each limits
what a Policy at this beamline can say:

- **Permission is a cross product, not a grant list.** A Policy holds a set of principals and a set of commands,
  and permits every pairing of the two. It cannot say that one operator may conduct while another may only
  review. Combined with the one-Policy-per-deployment limit above, differentiated roles are not currently
  expressible at all, and the starter Policy is a union rather than a least-privilege set because a union is the
  only honest thing a single cross product can be.
- **A Policy binds one Surface, and matching is strict.** Commands arriving on the MCP Surface, and commands
  raised inside the process by agent runtimes (which pass no Surface and so arrive on the nil sentinel), never
  match a Policy bound to HTTP. Most of the commands this deployment issues are agent-raised, so most of its
  traffic is outside what any single HTTP-bound Policy can govern.
- **Nothing exempts a brake.** The liveness conjunct deliberately never refuses `StopRun`, `HoldProcedure` and
  their siblings, so that switching a principal off cannot also remove their ability to halt work. The Policy
  conjunct has no such exemption, so a Policy that omits a brake command refuses it. The starter Policy lists
  every brake explicitly for that reason, and a Policy derived from observed history would not have, because
  nobody at 2-BM has yet needed to stop a run.
