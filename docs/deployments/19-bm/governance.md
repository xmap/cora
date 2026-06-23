# Governance

*Who will act at 19-BM, and the trust shape that will gate it. Design-phase.*

Governance at 19-BM follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

19-BM is pre-build, so this shape is not yet instantiated. The concrete Zone, Conduit, and Policy instances, and the 19-BM operator pool, land when the beamline approaches commissioning, following the [2-BM governance](../2-bm/governance.md) shape. The APS clearances (the safety forms that must be active to start) are issued at the APS Site, not on the beamline, and the beamline links up to them.

## Autonomy is first-class here

19-BM is "Fast Autonomous Computed Tomography": running unattended at a high scan cadence with a robotic sample changer is the reason the beamline exists. That makes it the deployment where CORA's supervisory agents are intended to go from seeded-but-dormant to operational. The agents are already facility principals at APS, carried pending on the [APS site page](../aps/index.md#who-acts-here):

- The `RunSupervisor` watches a running scan and can hold it; 19-BM is where that supervision is expected to be enabled and to climb from observe-and-advise toward holding and truncating stalled runs.
- The autonomous loop also needs a way to **start** runs without an operator (queue the next sample, start its scan), which the spine does not yet expose to an agent. 19-BM is the forcing case for that capability; it is a design question, not a copy from 2-BM.

Like every agent in CORA, these act only by issuing a command the spine already exposes, through the same authorized path a person uses. None of this is built yet; 19-BM reserves the seam.

## The robotic sample changer gate

The robotic sample changer requires a separate safety review before implementation (recorded in the FDR). In CORA terms that review issues a Clearance that must be Active before the changer may operate, so autonomous loading cannot start until the review is on file. The changer Asset, its Clearance gate, and the autonomous loading flow are carried as an [open question](questions.md) (ROBOT-1) until the design and the review land.
