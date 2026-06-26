# Governance

*Who will act at IOS, and the trust shape that will gate it. First cut.*

Governance at IOS follows the same model as the other NSLS-II beamlines: people and autonomous agents are facility principals at the [NSLS-II Site](../nsls2/index.md), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

IOS is not yet driven by CORA, so this shape is not yet instantiated. The profile collection exposes only coarse queue-server groups, not the human roster, so the NSLS-II operator and review structure is carried pending on the [NSLS-II Site](../nsls2/index.md) (`GOV-1`).

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the [NSLS-II Site](../nsls2/index.md), not on the beamline, and the beamline links up to them. The PSS search-and-secure permit signals and the photon shutters are absent from the profile collection, so the Enclosure permit leaves and the interlock structure are carried pending and not invented here (`PSS-1`).

IOS carries the hazard classes that come with its instruments, which an experiment Clearance would carry; those land with the instruments that bring them:

- the soft X-ray beam in the optics and endstation enclosures;
- the ultra-high vacuum of the PGM, the KB system, and the analyzer endstation;
- and, distinctively, the **ambient-pressure / operando sample environment**: a working gas atmosphere, the gas dosing and handling, and the sample heating that the reaction cell brings. That hardware is not in the profile collection, so its hazards (gas handling, pressure, temperature) are carried pending with the cell itself, not invented (`INSITU-1`).

The concrete Zone, Conduit, and Policy instances, and the operator pool, land when the deployment approaches the point where CORA drives IOS, following the [2-BM governance](../2-bm/governance.md) shape. It re-tests the Site and Federation kernel rather than introducing a new trust model.
