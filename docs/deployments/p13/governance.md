# Governance

*Who will act at P13, and the trust shape that will gate it. First cut.*

Governance at P13 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P13 is CORA's first EMBL Hamburg beamline, and the first **sub-operator** on the PETRA III Site: the beamline shares the ring and Facility with the DESY beamlines but is operated by EMBL Hamburg, with its own staff and its own MXCuBE control domain. The EMBL Hamburg operator pool and safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#who-acts-here), distinct from the DESY pool that P01 / P06 / P11 share, until EMBL staff confirm them (`GOV-1`). P13 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P13, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The MXCuBE config carries beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). The interlock at P13 is operated by DESY (the ring host) even where EMBL operates the beamline, so the boundary between the DESY-issued site clearance and the EMBL-operated experiment is itself a question (`GOV-1`). What is already settled is the shape: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

P13 also carries the hazard classes that come with an MX endstation: a cryostream and its liquid-nitrogen supply, and an automated sample changer moving in the experiment hutch. Those land with the instruments that bring them; the sample-changer custody loop, if modelled, would be a Procedure with a Subject thread (`ROBOT-1`), not an Asset CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the EMBL operator pool, land when the deployment approaches the point where CORA drives P13, following the [2-BM governance](../2-bm/governance.md) shape.
