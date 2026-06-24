# The beamline

*The part of 4-ID POLAR CORA models today, as areas you can jump to: the optics spine and the per-station experiment systems, plus the controls that drive them. First cut.*

4-ID POLAR is a polarization and magnetic-scattering beamline with four lead-shielded stations: `4-ID-A` (optics), and `4-ID-B`, `4-ID-G`, `4-ID-H` (experiment). This cut models the operational core across all four; the Raman station and the peripheral electronics are deferred (see [Model](../model.md#deliberately-not-here-yet)).

The modelled beamline divides into two kinds of thing. Along the beam, in order, sit the **stations**: the [Source](../beamline.md) that delivers, polarizes, and conditions the beam, the [Sample](sample.md) stage that places the specimen in it (and, at POLAR, applies field and temperature), and the [Detector](detector.md) that records what scatters. Cutting across them are the [Controls](controls.md) that drive the hardware. The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`.

## Stations

- [Source](../beamline.md): the `4-ID-A` optics spine and the shared front-end optics. The undulator pair feeds three diamond phase retarders that set the polarization state, the VDCM monochromator and its white-beam and mono slits, a diamond window, the toroidal and high-heat-load mirrors, the transfocator, and the per-station KB mirrors and filters.
- [Sample](sample.md): the 4-ID-G Huber diffractometers, the 4-ID-B polarization analyzer, and the sample environment across the stations: superconducting magnets, temperature controllers, positioning tables, and a pump-probe laser.
- [Detector](detector.md): the Eiger area detector, the beam-view flag cameras, the beam-position and intensity monitors, and the scaler counters.

## Shared

- [Controls](controls.md): the APS EPICS control stack. The device handles are bound from the beamline's instrument config and carried confirm (`CTRL-1`).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum, and the liquid helium and nitrogen the magnet and low-temperature environments draw on); carried in the descriptor, with no operations page yet in this first cut.

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model for the modelled part (every device by `parent_id`, with Families and pending confirmations). The hutch PSS permit signals are APS facility signals, not yet named (see [Open questions](../questions.md)).
