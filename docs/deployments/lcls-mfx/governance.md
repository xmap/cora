# Governance

*Who would act at MFX and the trust shape that gates their commands. Design-phase: the principals are facility-level and carried pending.*

MFX's principals are facility principals at the [SLAC Site](../slac/index.md), not beamline-local: the LCLS instrument-scientist and operator pool, and the LCLS safety-review body. Both are carried pending in the [site descriptor](../slac/index.md) until the LCLS structure is confirmed. CORA's role kernel (the five-role authorization model) is facility-invariant, so MFX inherits it; what MFX adds to think about is two hazard gates the storage-ring exercises do not have.

## The pump-probe laser Clearance

MFX runs a class-4 optical laser for pump-probe, governed at LCLS by the Beam Transport Protection System (BTPS). CORA carries this as a `Clearance` hazard on the experiment (a facility-issued safety permit that must be Active before laser-on work), the same posture 32-ID takes for its additive-manufacturing laser. This is distinct from whether the laser is a driven Asset: the device folds into the loose `Laser` family (the 4-ID precedent), while the personnel-safety permit is a Clearance. The two coexist (LASER-1).

## The PPS permit

As at every beamline, beam-on work in an enclosure is gated by the facility personnel protection system (PPS). The LCLS PPS search-and-secure permit signals are not in `pcdshub` and are carried pending (PSS-1). MFX's enclosure structure (a shared front-end / transport zone plus the MFX experiment hutch) is itself carried `confirm` because the `pcdshub` PV prefixes encode beamline-line zones, not access-gated hutches (ENC-1).

## What is not modelled

- **Trust instantiation.** No scenario instantiates MFX trust zones or actors; this is a design-phase modelling exercise, so the governance shape is described, not seeded.
- **The DAQ and analysis software as principals.** The LCLS DAQ, `psana`, and the bluesky-based scan suite are control-system software on the floor, not CORA actors (see [Controls](equipment/controls.md)). When the per-shot acquisition axis is designed (DAQ-1), the question of which principal authorizes a DAQ run is part of that work.

People and agents are facility principals at the [SLAC Site](../slac/index.md); see [Open questions](questions.md) for the governance items still to confirm.
