# Governance

*Who will act at SYRMEP, and the trust shape that will gate it. First cut.*

Governance at SYRMEP follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [Elettra Site](../elettra/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

SYRMEP is CORA's first Elettra deployment, so Elettra is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [Elettra Site](../elettra/index.md), shared across the facility's beamlines, until Elettra staff confirm them (`GOV-1`). SYRMEP is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives SYRMEP, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The Elettra personnel-safety permit signals and the front-end / safety shutters are not in public source, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). The Elettra 2.0 GeCo PLC interlock stack (Siemens S7-1500 over PROFINET) is the safety floor CORA never drives; it sits below the seam. What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [Elettra Site](../elettra/index.md), not on the beamline, and the beamline links up to them.

SYRMEP carries the hazard classes that come with hard X-ray imaging: an intense white / monochromatic beam, and, for the clinical breast-CT programme (SYRMA-3D), human-subject considerations that an experiment Clearance would carry. Those land with the work that brings them, modelled as hazards on the experiment rather than as Assets CORA drives for safety.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives SYRMEP, following the [2-BM governance](../2-bm/governance.md) shape.
