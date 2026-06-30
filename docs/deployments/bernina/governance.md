# Governance

*Who would act at Bernina and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

Bernina's principals are facility principals at the [PSI Site](../psi/index.md), not beamline-local: the SwissFEL instrument-scientist and operator pool, and the PSI safety-review body. Both are carried pending in the [site descriptor](../psi/index.md) until the PSI structure is confirmed; the `eco` device library is a controls library, not an organizational record, so it exposes no human roster (GOV-1). CORA's role kernel (the five-role authorization model) is facility-invariant, so Bernina inherits it. Bernina shares its Site, its Aramis source, and its safety posture with the sibling [Alvra](../alvra/governance.md) station, so most of the governance shape is the PSI-Site shape already described there; what is worth drawing out is the shared-source boundary and the laser Clearance.

## The shared Aramis source and the optics zone

Bernina is one of three co-equal stations (with Alvra and Cristallina) on one Aramis source, beam routed to one at a time (TOPO-1). The `SAROP21` optics hutch conditions the beam on the way to Bernina, but the source upstream of it is shared. That makes the optics-hutch Zone a shared-access boundary, the same question Alvra's optics hutch and LCLS-MFX's front-end / transport zone raise: who holds the permit when the beam is routed to a neighbour, and how the routing state gates each station's commands. The SwissFEL PSS search-and-secure permit signals are not in the `eco` manifest and are carried pending (PSS-1). Bernina's enclosure structure (the shared `SAROP21` optics hutch plus the Bernina experiment hutch) is carried `confirm` because the `eco` PV prefixes encode beamline-line zones, not access-gated hutches (ENC-1).

## The pump-probe laser Clearance

Bernina runs a class-4 optical laser for pump-probe. CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before laser-on work), the same posture Alvra, LCLS-MFX, and 32-ID take. This is distinct from whether the laser is a driven Asset: the device folds into the loose `Laser` family, while the personnel-safety permit is a Clearance. The two coexist (LASER-1).

## What is not modelled

- **Trust instantiation.** No scenario instantiates Bernina trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.
- **The Staeubli sample / detector robot as a principal or driven Asset.** The robot runs over PShell (HTTP), not EPICS, and its modelling is deferred (ROBOT-1); when it is modelled, whether an autonomous sample-handling Agent acts through it is part of that work.
- **The DAQ and acquisition software as principals.** The SwissFEL `sf-daq`, `bsread`, and the `eco` / `slic` scan suite are control-system software on the floor, not CORA actors (see [Controls](equipment/controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [PSI Site](../psi/index.md); see [Open questions](questions.md) for the governance items still to confirm.
