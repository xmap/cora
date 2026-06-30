# Techniques

*What the modelled part of XFP is designed to do, as intent. First cut.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../nsls2/index.md#the-techniques-adapted-here) is how a facility adapts it. XFP does one technique, **X-ray footprinting**, in two delivery modes: static / capillary-flow, and shutterless high-throughput. The Method below renders unlinked and is carried pending until the owner-scope decision (`TECH-1`) brings it into the catalog.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| X-ray footprinting (capillary-flow / static) | `x_ray_footprinting` | gate a timed white-beam dose onto a flowing solution capillary or flow-cell sample, recording exposure time x flux x attenuation as the delivered dose; the fleet's first dose-delivery Method, new to the catalog; readout is offline mass spec (`TECH-1`, `READOUT-1`) |
| High-throughput footprinting (HTFly) | `x_ray_footprinting` | sweep a fly-cell row through the defining slit at a set stage velocity so the exposure (dose) is the slit gap over the velocity, across a 96-well plate; the same `x_ray_footprinting` Method with the HTFly stage as the dose-timing (`TECH-1`, `HT-1`) |

Both modes need the [white-beam chain](beamline.md) (the mirror, the slits, the Al filter wheel for dose rate), the [dose gating](beamline.md) (the timed shutters or the delay-generator-fired Uniblitz, or the HTFly velocity), the [sample side](equipment/sample.md) (a stage and the delivery pump), and the [flux monitors](equipment/detector.md) (to record the delivered dose). They differ only in how the exposure is timed and how many samples are handled.

## The technique is dose delivery, and the readout is offline

This is the heart of what makes XFP a new shape for CORA. X-ray footprinting is not a measurement technique in the sense the rest of the fleet uses: the beamline does not record a structural signal. It **delivers a controlled radiolytic dose** to a biological macromolecule in solution, generating hydroxyl radicals that covalently modify the molecule at solvent-accessible sites. The modified sample is then analysed **offline by mass spectrometry**, which reveals which residues were exposed and thus maps the molecule's surface and conformational changes.

So the Method `x_ray_footprinting` is a **dose-delivery** Method:

- its controlled variable is the delivered dose (exposure time times flux times attenuation), not a detector setting;
- its product is a footprinted sample plus a dose record, not a measurement frame;
- its structural readout is the offline-readout seam (mass spec, downstream and off the beamline, `READOUT-1`).

That is why `x_ray_footprinting` is proposed as a Method distinct from anything in the catalog: not because the optics are unusual (a white beam, a filter, a shutter), but because the experiment shape, dose-in, sample-out, structure-read-elsewhere, is genuinely new. Whether the catalog ultimately holds a `x_ray_footprinting` Capability, or a broader "controlled-dose / irradiation" Capability with footprinting as a Practice adaptation, is the owner-scope decision (`TECH-1`); XFP records the case, it does not mint the vocabulary. The matching Site Practices (`XFP_footprinting_practice`, `XFP_high_throughput_footprinting_practice`) are carried pending in the [NSLS-II Site](../nsls2/index.md#the-techniques-adapted-here); each binding lands when its Capability does.

## A time-resolved mode, deferred

The profile collection also contains a time-resolved capillary-flow mode (a stopped-flow style mixing experiment before irradiation), but it is flagged unfinished in the source, so no Practice is recorded for it here; it is a later mode that would reuse the same `x_ray_footprinting` Method with a mixing step in the Procedure (`TECH-1`).

## Not modelled yet

The concrete acquisition recipes are not written yet. For footprinting that is the dose series (the set of exposure times or filter thicknesses that build a dose-response curve), the flow program that presents fresh sample, the aliquot-collection pattern, and the flux-to-absorbed-dose calibration that converts the measured flux to the dose the sample received (a seam constant that lives in offline analysis, `DOSE-1`). The downstream linkage to the offline mass-spec result is the offline-readout seam, not a beamline recipe (`READOUT-1`). These join as the deployment approaches the point where CORA drives XFP.

Whether `x_ray_footprinting` enters CORA's catalog is an owner-scope decision on [Model](model.md): a modelling exercise reinforces the case but does not mint cross-facility Method vocabulary on its own. See [Open questions](questions.md) for the world-facts to confirm first.
