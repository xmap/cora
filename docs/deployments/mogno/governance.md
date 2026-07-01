# Governance

*Who will act at MOGNO, and the trust shape that will gate it. First cut.*

Governance at MOGNO follows the same model as the rest of the fleet: people and autonomous agents are facility principals at the [Sirius Site](../sirius/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

MOGNO is CORA's first Sirius deployment, so Sirius is a brand-new Site: the operator pool and the safety-review structure are carried pending on the [Sirius Site](../sirius/index.md#safety-and-governance), shared across the facility's beamlines, until LNLS staff confirm them (`GOV-1`). MOGNO is a reverse-engineered scaffold rather than a pilot, so the concrete Zone, Conduit, and Policy instances are deliberately not materialized; they land when the deployment approaches the point where CORA drives MOGNO, following the [2-BM governance](../2-bm/governance.md) shape.

The safety tier is the other piece that is not yet settled. The Sirius personnel-safety permit signals and the photon and front-end shutters are not in any public source, so the Enclosure permit leaves and the interlock structure are carried pending and are not invented here (`PSS-1`). What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [Sirius Site](../sirius/index.md#safety-and-governance), not on the beamline, and the beamline links up to them.

MOGNO carries the hazard classes that come with a tomography beamline: an intense X-ray beam (a quasi-monochromatic dipole source running up to ~68 keV), and the radiation-enclosure interlocks of the two experiment stations. Those land at the Site safety envelope; an experiment Clearance would carry the per-experiment authorization.

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives MOGNO, following the [2-BM governance](../2-bm/governance.md) shape.
