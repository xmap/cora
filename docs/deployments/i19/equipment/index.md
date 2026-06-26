# The beamline

*The i19 beamline as areas you can jump to: the beam-delivery source, the sample stage that orients the crystal, the detector that records it, and the controls and resources cutting across them. The genuine novelty is governance: two experiment hutches sharing one optics line. Scaffold.*

The beamline divides into two kinds of thing. Along the beam sit the **stations**: the [Source](../beamline.md) (the shared optics that deliver and condition the beam), the [Sample](sample.md) station that orients the crystal in it, and the [Detector](detector.md) that records what diffracts. Cutting across them are the shared concerns: the [Controls](controls.md) that drive the hardware, the access-control seam that arbitrates them, and the resources the beamline draws on.

What makes i19 different from the rest of the fleet is not the instrument but the layout. i19 has **two experiment hutches in series**, EH1 and EH2, that **share one optics line**. Only the active hutch may drive the shared optics. A non-active hutch can read the shared-optics state, but it cannot move energy, operate the experiment shutter, set the attenuator, or drive a mirror piezo while the other hutch holds the beam. CORA models this as an Enclosure-permit plus a Trust-gate over the shared-optics Assets, with the i19-blueapi arbiter as an actuate-floor seam partner (the "EPICS is the floor" pattern, here a blueapi-arbiter floor); it is not a device family (ACCESS-1).

The stations are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways, by `controller_id`. The four-circle goniometer lives in EH2 per the descriptor (ENC-1).

## Stations

- [Source](../beamline.md): the shared BL19I optics that deliver and condition the beam. The undulator (SR19I) feeds the double-crystal monochromator (DCM), through the horizontal and vertical focusing mirrors (a hutch-keyed coating stripe: Si 5-10 / Rh 10-20 / Pt 20-30 keV), the attenuator absorber wedges, and the PSS-interlocked optics shutter. Energy is the coordinated DCM-plus-undulator-plus-stripe move, modelled as a PseudoAxis gated by the active-hutch permit (SRC-1, MONO-1, OPT-1, ACCESS-1). Every write to these Assets is access-gated by the active hutch (ACCESS-1).
- [Sample](sample.md): the two endstations. EH1 carries the on-axis and diagonal sample-viewing cameras and its trigger controller; EH2 carries the Newport kappa four-circle goniometer (phi / omega / kappa plus a 2THETA arm and det_z) composed into the named-not-built Assembly(Diffractometer), the serial / microfocus fixed-target arm, the MAPT aperture (pinhole plus collimator), and the sample backlight (DIFF-1, SERIAL-1, APERTURE-1, DET-1). The kappa four-circle is plain Goniometer reuse: kappa is a setting, not a new family.
- [Detector](detector.md): the Eiger area detector in EH2, the per-hutch beamstops, and the triggers (Zebra in each hutch, plus a PandA sequencer in EH2) (DET-1).

## Shared

- [Controls](controls.md): the Diamond EPICS control stack with the real dodal PV handles, the per-hutch Zebra and PandA timing and triggering, and the **access-control seam**. A hutch reads the shared-optics state directly over EPICS but posts its writes to the i19-blueapi arbiter, which compares the requesting hutch against the active-hutch readback (`BL19I-OP-STAT-01:EHStatus`) and runs or rejects (ACCESS-1, CTRL-1).
- Resources: the continuously-available supplies a run needs (photon beam, cooling water, vacuum); carried in the descriptor, with no operations page in this scaffold (SUP-1).

## Reference

The cross-cutting view that spans every station:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the dodal control handles, and pending confirmations). The PSS search-and-secure permit signals are Diamond facility signals, pending and not invented beyond the dodal InterlockedHutchShutter (PSS-1); see [Open questions](../questions.md).
