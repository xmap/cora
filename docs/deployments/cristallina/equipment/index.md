# The beamline

*The Cristallina station as the areas you can jump to: the stages the beam passes through, plus the controls that drive them and the resources they draw on. Design-phase.*

The beamline divides into two kinds of thing. Along the beam, in order, sit the **stages**: the [Source](../beamline.md) that delivers and conditions the beam (the Aramis FEL source, the front end, and the `SAROP31` optics hutch), the [Endstation](endstation.md) where the focused beam meets the sample on the diffractometers in the dilution-fridge magnet, and the [Detector](detector.md) that records each shot. Cutting across them are the shared concerns: the [Controls](controls.md) that drive the hardware, and the resources the beamline draws on. Two access-gated zones contain it: a shared `SAROP31` optics hutch (the offset mirrors, the double-channel-cut mono, the pulse picker, the attenuator, the KB focusing mirrors, the alignment laser) and the Cristallina experiment hutch (the diffractometers, the DilSc magnet, the detectors). `slic` separates an optics hutch from an experimental hutch but does not encode the access-gated safety meaning (ENC-1).

The stages are containment trees of apparatus (`Asset.parent_id`); controls relate to that apparatus sideways; and a resource is a Supply in its own right.

## Stages

- [Source](../beamline.md): the Aramis FEL source, the front-end gas monitors and photon spectrometer, the front-end slit and attenuator, and the `SAROP31` optics hutch. The shared Aramis source is steered to one station at a time, the switched-source seam now closed across three stations (TOPO-1).
- [Endstation](endstation.md): the Cristallina endstation. The I0 chamber, the DM1 dilution-fridge and DM2 pulsed-magnet diffractometers orient the sample and position the detector arm, inside the DilSc dilution refrigerator and its vector superconducting magnet; the Cristallina-MX fast stage runs serial crystallography.
- [Detector](detector.md): the per-shot Jungfrau area detectors (a 1.5M and an I0 0.5M for Q, an 8M for MX), read not by a poll loop but by the SwissFEL event-driven DAQ.

## Shared

- [Controls](controls.md): the `slic` EPICS device library (with the real PV prefixes, in-repo), the SwissFEL CTA / EVR timing, and the event-driven DAQ that CORA references but does not own.
- Resources: the continuously-available supplies a run needs (the SwissFEL photon beam, cooling water, vacuum, and the dilution-fridge liquid helium); carried in the descriptor, with no operations page in this design phase. The FEL beam is a shared, switched resource (TOPO-1).

## Reference

The cross-cutting view that spans every area:

- [Inventory](../inventory.md): the full planned CORA Asset model (every device by `parent_id`, with Families, the `slic` control handles, and pending confirmations).
- [Model](../model.md): the `Diffractometer` Assembly design (DIFF-1), the `Magnet` rule-of-three (MAG-1), the `slic` provenance boundary, and the architectural gap register.
