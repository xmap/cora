# Governance

*Who may act at 2-BM, and the trust policy that would gate their commands, if one were defined. Static config;
the per-run [decisions](experiment.md) operators and agents make are live, not here.*

## Who acts

Two beamline staff hold operator principals at 2-BM today, seeded as `human` Actors by the
`cora.api.beamline_staff_seed` ceremony under pinned, deployment-stable ids. Their display names are personal
data: the ceremony writes each name only to the `actor_profile` PII vault, supplied at deploy time from the host
environment. The repository carries the pinned seat ids and nothing else about these two people: an id is opaque,
and no name, badge, ORCID, or address is checked in anywhere. Facility-process
principals (proposal PIs, the safety review board, the beamline scientist acting in a review-chain capacity) are
facility-wide and live at [APS](../aps/index.md#safety-and-governance). See [Model](../../architecture/model.md)
for the aggregate shape.

| Actor | Kind |
| --- | --- |
| 2-BM operator (seat A) | `human` |
| 2-BM operator (seat B) | `human` |

## The trust boundary

2-BM's boundary is shaped by the Trust BC aggregates (Zone, Conduit, Policy); the
[Trust module](../../architecture/modules/trust/index.md) defines what each one is. This page records only the
2-BM instances:

| Zone | Conduit | Endpoints |
| --- | --- | --- |
| `2-BM Zone` | `2-BM Local Conduit` | `2-BM Zone` -> `2-BM Zone` |

## Policy: not yet defined

`TrustAuthorize` gates commands against exactly one configured Policy per deployment (`Settings.trust_policy_id`
is a single, optional `UUID`, not a collection). A deployment cannot run more than one Policy at a time, so a
two-Policy split (one for operator commands, a separate one for agent-issued Decision commands) is not a shape
`Settings` can express; any such split would have to be modeled inside one Policy's own permitted-principals and
permitted-commands rows instead.

2-BM has not defined a Policy yet, and `trust_policy_id` is unset. With no Policy configured, the deployment
runs on `AllowAllAuthorize`, the permissive stub that admits every command from every principal regardless of
Zone, Conduit, or Actor kind. The two seeded operators above are therefore usable principals for hands-on
testing, not principals a Policy has actually vetted. Defining a real Policy for 2-BM, and switching
`trust_policy_id` to point at it, is future work.
