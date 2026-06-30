# Governance

*Who will act at P14, and the trust shape that will gate it. First cut.*

Governance at P14 follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [PETRA III Site](../petra-iii/index.md#who-acts-here), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

P14 is CORA's second EMBL Hamburg beamline, the sibling of [P13](../p13/governance.md) and, like it, a **sub-operator** on the PETRA III Site: the beamline shares the ring and Facility with the DESY beamlines but is operated by EMBL Hamburg, with its own staff and its own MXCuBE control domain. The EMBL Hamburg operator pool and safety-review structure are carried pending on the [PETRA III Site](../petra-iii/index.md#who-acts-here), distinct from the DESY pool and shared with P13, until EMBL staff confirm them (`GOV-1`). P14 is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives P14, following the [2-BM governance](../2-bm/governance.md) shape.

The two-hutch layout adds a governance nuance: EH1 and EH2 are separate experiment hutches under one beamline, so the trust shape would scope per hutch (each hutch its own Zone of resources and its own access state) while sharing the source / optics chain. That per-hutch scoping is carried as part of the enclosure question (`EH-1`).

The safety tier is the other piece that is not yet settled. The MXCuBE configs carry beamline devices, not the personnel-safety interlock leaves, so the Enclosure permit signals and the interlock structure are carried pending and are not invented here (`PSS-1`). The interlock is operated by DESY (the ring host) even where EMBL operates the beamline, so the boundary between the DESY-issued site clearance and the EMBL-operated experiment is itself a question (`GOV-1`). What is already settled is the shape: clearances (the safety forms that must be active to start) are issued at the [PETRA III Site](../petra-iii/index.md#the-safety-envelope), not on the beamline, and the beamline links up to them.

P14 also carries the hazard classes that come with an MX endstation: a cryostream and its liquid-nitrogen supply, and an automated sample changer moving in the experiment hutches. Those land with the instruments that bring them; the sample-changer custody loop, if modelled, would be a Procedure with a Subject thread (`ROBOT-1`), not an Asset CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the EMBL operator pool, land when the deployment approaches the point where CORA drives P14, following the [2-BM governance](../2-bm/governance.md) shape.
