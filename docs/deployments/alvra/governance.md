# Governance

*Who would act at Alvra and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

Alvra's principals are facility principals at the [PSI Site](../psi/index.md), not beamline-local: the SwissFEL instrument-scientist and operator pool, and the PSI safety-review body. Both are carried pending in the [site descriptor](../psi/index.md) until the PSI structure is confirmed; the `eco` device library is a controls library, not an organizational record, so it exposes no human roster (GOV-1). CORA's role kernel (the five-role authorization model) is facility-invariant, so Alvra inherits it; what Alvra adds to think about is the same two hazard gates LCLS-MFX raised, now at a second XFEL.

## The pump-probe laser Clearance

Alvra runs a class-4 optical laser for pump-probe. CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before laser-on work), the same posture LCLS-MFX takes for its pump-probe laser and 32-ID takes for its additive-manufacturing laser. This is distinct from whether the laser is a driven Asset: the device folds into the loose `Laser` family (the LCLS-MFX / 4-ID precedent), while the personnel-safety permit is a Clearance. The two coexist (LASER-1).

## The PSS permit

As at every beamline, beam-on work in an enclosure is gated by the facility personnel safety system (PSS). The SwissFEL PSS search-and-secure permit signals are not in the `eco` manifest and are carried pending (PSS-1). Alvra's enclosure structure (a shared Aramis optics hutch plus the Alvra experiment hutch) is itself carried `confirm` because the `eco` PV prefixes encode beamline-line zones (`SARFE10` front end, `SAROP11` optics, `SARES11` endstation), not the access-gated hutch or its safety meaning (ENC-1). The shared optics hutch is the same shared-zone question LCLS-MFX's front-end / transport zone raised, because the Aramis source feeds the Alvra, Bernina, and Cristallina stations (TOPO-1).

## What is not modelled

- **Trust instantiation.** No scenario instantiates Alvra trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.
- **The DAQ and acquisition software as principals.** The SwissFEL `sf-daq`, `bsread`, and the `eco` / `slic` scan suite are control-system software on the floor, not CORA actors (see [Controls](equipment/controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [PSI Site](../psi/index.md); see [Open questions](questions.md) for the governance items still to confirm.
