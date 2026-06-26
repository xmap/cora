# Governance

*Who will act at 13-ID-D, and the trust shape that will gate it. First cut.*

Governance at 13-ID-D follows the same model as the other APS beamlines: people and autonomous agents are facility principals at the [APS Site](../aps/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

13-ID-D is not yet driven by CORA, so this shape is not yet instantiated. As a reverse-engineered scaffold, the deployment is descriptor and docs today, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized. The GSECARS EPICS support tree exposes device templates and startup scripts, not the human roster, so the APS / GSECARS operator pool and the safety-review structure are carried pending at the [APS Site](../aps/index.md#who-acts-here), shared across the beamlines (`GOV-1`).

## The safety envelope

The safety tier is the other piece that is not yet settled, and at 13-ID-D it carries an extra leg the other APS beamlines do not. Clearances (the safety forms that must be active to start) are issued at the [APS Site](../aps/index.md#the-safety-envelope), not on the beamline, and 13-ID-D links up to them rather than restating them. What is specific to this station is the stack of hazard classes that an experiment Clearance would have to carry together: a hard X-ray beamline, plus the class-4 double-sided heating lasers at the sample, plus the pressurized gas membrane system that loads the diamond anvil cell. Those three land with the instruments that bring them, and the high-pressure sample environment is the novelty here (`HP-1`).

The PSS search-and-secure permit signals and the front-end and photon shutters are absent from the EPICS-native config, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`).

## The laser-safety permit leaf

13-ID-D adds a distinct enclosure permit axis the rest of the fleet has not needed: a dedicated laser-safety permit gating laser emission, separate from the X-ray PSS leaf. A Koyo safety PLC governs whether the heating lasers may emit into the enclosure. CORA models this as an Enclosure permit concern on the laser-emission axis, not as a device. It is carried pending and its logic is not invented here (`LASER-1`, `PSS-1`); the heating capability of the cell stays open-loop on commanded power and is not a closed-loop controller (`HEAT-1`).

## Where this lands

The concrete Zone, Conduit, and Policy instances, the operator pool, and both safety leaves (the PSS X-ray permit and the laser-emission permit) materialize when the deployment approaches the point where CORA drives 13-ID-D, following the [2-BM governance](../2-bm/governance.md) shape.
