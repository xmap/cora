# Governance

*Who would act at Cristallina and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

Cristallina's principals are facility principals at the [PSI Site](../psi/index.md), not beamline-local: the SwissFEL instrument-scientist and operator pool, and the PSI safety-review body. Both are carried pending in the [site descriptor](../psi/index.md) until the PSI structure is confirmed; the `slic` device library is a controls library, not an organizational record, so it exposes no human roster (GOV-1). CORA's role kernel (the five-role authorization model) is facility-invariant, so Cristallina inherits it. Cristallina shares its Site, its Aramis source, and its safety posture with the sibling [Alvra](../alvra/governance.md) and [Bernina](../bernina/governance.md) stations, so most of the governance shape is the PSI-Site shape; what is worth drawing out is the shared-source boundary and the high-field-magnet hazard.

## The shared Aramis source and the optics zone

Cristallina is the third of three co-equal stations (with Alvra and Bernina) on one Aramis source, beam routed to one at a time (TOPO-1). The `SAROP31` optics hutch conditions the beam on the way to Cristallina, but the source upstream is shared. That makes the optics-hutch Zone a shared-access boundary, the same question Alvra and Bernina raise: who holds the permit when the beam is routed to a neighbour, and how the routing state gates each station's commands. With three stations now modelled on the one source, the routing state is a three-way selection, not a pair. The SwissFEL PSS search-and-secure permit signals are not in the `slic` manifest and are carried pending (PSS-1). Cristallina's enclosure structure (the shared `SAROP31` optics hutch plus the Cristallina experiment hutch) is carried `confirm` because the `slic` PV prefixes encode beamline-line zones, not access-gated hutches (ENC-1).

## The high-field-magnet Clearance

Cristallina's defining hazard is not a laser (the `slic` source has no pump-probe laser, LASER-1) but the **vector superconducting magnet** and its cryogens. The DilSc dilution refrigerator runs an Oxford Mercury iPS magnet to 5.2 Tesla on the z-axis, cooled by liquid helium. CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before high-field work), the same posture [ESRF ID32](../id32/governance.md) takes for its 9 T XMCD magnet and its liquid-helium plant. This is distinct from whether the magnet is a driven Asset: the device binds the loose `Magnet` family (the fourth consumer, held at the rule-of-three, MAG-1), while the personnel- and quench-safety permit is a Clearance. The two coexist, the same way the laser device and the laser Clearance coexist at Alvra and Bernina.

## What is not modelled

- **Trust instantiation.** No scenario instantiates Cristallina trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded. It would land, following the [2-BM governance](../2-bm/governance.md) shape, if and when the deployment approaches real scope.
- **The magnet as a safety-driven Asset.** The vector magnet is modelled as a hazard via a Clearance, not as an Asset CORA drives for safety (the ID32 magnet and the Alvra / Bernina laser precedent). Its field setpoints are an experiment concern; its safety is a permit.
- **The DAQ and acquisition software as principals.** The SwissFEL `sf-daq`, `bsread`, and the `slic` scan suite are control-system software on the floor, not CORA actors (see [Controls](equipment/controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [PSI Site](../psi/index.md); see [Open questions](questions.md) for the governance items still to confirm.
