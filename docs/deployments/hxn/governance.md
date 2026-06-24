# Governance

*Who may act at HXN and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An HXN beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a run, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody; CORA confirms entitlement against the facility's proposal identity but applies its own per-Actor authority on top.

## Agents and the scanning loop

HXN's scanning workflows (auto-alignment, adaptive mapping) are where an autonomous or adaptive Agent would naturally act: proposing the next scan region or correction inside the conduct loop. If such an agent were added, it would be a facility principal scoped at the Site, governed by the same trust boundary, and each proposed move would be a [Decision](../../architecture/modules/decision/index.md) (the inference-recorder path for any LLM-backed agent). None is declared for HXN yet.
