# Governance

*Who may act at FXI and the trust shape CORA applies. This is CORA's governance design landing on the beamline, not a description of the beamline's current controls authority.*

People and agents are facility principals at the [NSLS-II Site](../nsls2/index.md#who-acts-here); on the beamline they surface through the actions they take. The human roster is not yet known (GOV-1), so the principals below are the design shape, not a registered list.

## Who acts

CORA brings its own Access model: a small set of facility roles (operator, beamline scientist, safety reviewer, and the autonomous-agent and service principals) scoped at the NSLS-II Site. An FXI beamtime is run by an operator or beamline scientist Actor; a safety reviewer holds the clearance authority. The concrete people and their role assignments are pending staff confirmation (GOV-1).

## The trust boundary

CORA's Trust BC (Zone, Conduit, Policy) gates every command by who is acting and what the beamline state allows: who may start a run, override a caution, or commit a calibration. This authority is CORA's own, expressed per Actor, not inherited from the beamline's controls layer.

Two facts from the facility flow into this design:

- Proposal custody. An NSLS-II beamtime is scoped to a proposal and cycle. CORA uses that proposal/cycle as the Campaign and the custody key for who is entitled to act during a beamtime; it confirms entitlement against the facility's proposal identity but applies its own per-Actor authority on top.
- The floor already has a coarse, group-level command-authority layer at the controls level. CORA does not adopt it: CORA's per-Actor Trust model supersedes it with finer, auditable authority.

No autonomous or adaptive agent Actor is declared for FXI yet. If one were added (an alignment or experiment-steering agent), it would be a facility principal scoped at the Site, governed by the same Trust boundary and recorded in the [Experiment](experiment.md) decision provenance.
