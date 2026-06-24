# Governance

*Who may act at FXI and the trust shape that gates their commands. Reverse-engineered from the queue-server permissions and the shared `nslsii` proposal-gating; the human roster is not in the profile collection (GOV-1).*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take.

## Who acts

The profile collection exposes only a coarse authority model, not a human roster:

- `startup/user_group_permissions.yaml` defines two queue-server groups, `root` and `primary`, each an allow/forbid set of name regexes over `{plans, devices, functions}`. This is the bluesky-queueserver authority layer.
- The shared `nslsii.sync_experiment` validates each `data_session` against `api.nsls2.bnl.gov` (cycle + beamline), authenticates via BNL LDAP, and gates access with `should_they_be_here` (facility / beamline / data-session tiers).

The actual operator and beamline-scientist pool, and their role assignments, are not in source (GOV-1); the Site carries them as pending Actors.

## The trust boundary

CORA owns a finer authority than the queue-server's two groups. The mapping:

- The queue-server `root` / `primary` groups seed a Trust **Policy** / **Zone**: a coarse allow/forbid over plans and devices.
- `nslsii.sync_experiment`'s proposal/data-session gating maps to the Access **Actor** and the Campaign (proposal/cycle) custody.
- Above both, CORA's Trust BC adds per-Actor authority (who may start a run, override a caution, or commit a calibration) that the group-scoped queue-server model does not express.

No autonomous or adaptive agent Actor is declared: the FXI profile collection does not expose a standing agent (unlike, say, the adaptive-plan beamlines). Any future agent would be a facility principal scoped at the Site.
