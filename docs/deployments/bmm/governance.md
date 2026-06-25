# Governance

*Who may act at BMM and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not known from the profile collection (GOV-1), so the principals are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. A BMM beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority.

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a scan, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer. The NSLS-II proposal and cycle are a fact CORA's Campaign uses for custody.

## Batch automation and agents

BMM's batch XAS, a wheel of many samples scanned unattended, is a natural place for an autonomous Agent: choosing the next sample, deciding when a spectrum has enough signal-to-noise, flagging a bad scan. If such an agent were added, it would be a facility principal scoped at the Site, governed by the same trust boundary, and each decision (which sample, rescan-or-advance) would be a [Decision](../../architecture/modules/decision/index.md) recorded in the run provenance. None is declared for BMM yet; the unattended wheel loop is conducted, not agent-driven, in this scaffold.
