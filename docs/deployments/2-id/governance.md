# Governance

*Who will act at 2-ID, and the trust shape that will gate it. Design-phase.*

Governance at 2-ID follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

2-ID is a design-phase scaffold in CORA, so this shape is not yet instantiated. The 2-ID operator pool and beamline-scientist assignments are not modelled ahead of confirmation; CORA does not invent a 2-ID operator roster.

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them rather than restating them.

2-ID-D adds one governance shape the tomography pilots do not have: an **autonomous alignment agent in the loop**. The EAA microprobe agent drives the zone-plate autofocus and drift-correction loop, and its own examples gate every action behind an operator confirmation, with motion and beam disabled by default. In CORA's model that maps cleanly: EAA registers as an [Agent](model.md#how-eaa-fits) whose proposals become Decisions, and the permit and clearance adjudication is the interpose point where an agent's proposed move is allowed or denied. The default-deny posture EAA already carries is the shape CORA's Conduit and Policy would enforce, not a new invention.

The concrete Zone, Conduit, and Policy instances, the operator pool, and the agent-authority policy land when the deployment approaches the point where CORA drives 2-ID, following the [2-BM governance](../2-bm/governance.md) shape.
