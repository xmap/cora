# Governance

*Who will act at 7-BM, and the trust shape that will gate it. Design-phase.*

Governance at 7-BM follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

Because 7-BM runs at the same APS Site as 2-BM, it reuses the APS facility envelope rather than creating a new one: the APS operator pool, the experiment-safety review structure, and the seeded agents are facility-wide and are inherited unchanged. This is the opposite of the TomoWISE deployment, which had to create a new MAX IV Site. 7-BM adds only its own beamline-bound principals (the 7-BM beamline scientists and operators), carried pending on the [APS site page](../aps/index.md#who-acts-here).

7-BM is pre-build for CORA, so the concrete trust shape is not yet instantiated. What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the APS Site, not on the beamline, and the beamline links up to them rather than restating them.

One governance question is sharper at 7-BM than at 2-BM: the flow and combustion hazard surface (flammable gas, fuel vapor, oxygen deficiency, a radioactive check source for detector calibration) is broader than the radiation-only hazard profile of micro-CT. CORA's current position is that this is handled by ESAF clearances plus operator Cautions plus the hutch alarms, not by a separate hazard aggregate. Whether combustion or flammable-gas work needs a review, approve, and expire workflow distinct from the standard ESAF clearance is the single question that would change that (HAZ-1).

The concrete Zone, Conduit, and Policy instances, and the beamline operator pool, land when the beamline approaches commissioning, following the [2-BM governance](../2-bm/governance.md) shape.
