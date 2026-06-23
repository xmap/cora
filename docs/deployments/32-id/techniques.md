# Techniques

*What the modelled part of 32-ID is designed to do, as intent. Design-phase.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../aps/index.md#the-techniques-adapted-here) is how a facility adapts it. This scaffold models 32-ID's TXM endstation, so the techniques below are the TXM ones, carried as design intent. The function view survives the eventual hardware choices, which is why it can be written before the optics are confirmed.

## TXM nano-tomography

The transmission X-ray microscope images the internal structure of a sample at nanometre-class resolution by magnifying the transmitted beam through a Fresnel zone plate, then rotating the sample for a tomographic reconstruction.

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Nano-tomography | `tomography` | step-scan projections over a rotation, magnified by the zone-plate optics |
| Zernike phase-contrast nano-tomography | `tomography` | the phase ring is inserted for phase contrast; a Plan setting over the same Method, not a separate Method |

Both realize `cora.capability.tomography` and need the [TXM sample stage](equipment/sample.md) and the [TXM detector](equipment/detector.md). Phase contrast is a configuration of the same tomography Method (the phase ring inserted), mirroring the 2-BM decision that laminography is a tomography Plan at a tilt setpoint rather than a new Method.

## Energy and beam mode

32-ID delivers white or monochromatic beam, selected by the P4-50 mode shutter. The monochromatic branch uses the Si(111) monochromator over a 7 to 40 keV range. Whether CORA models the white-to-mono switch as a new Capability or as an extension of the existing `energy_change` vocabulary is an open design decision recorded on [Model](model.md); the world-fact half (the switch structure) is `MODE-1` on [Open questions](questions.md).

## Not modelled yet

32-ID's other techniques run on instruments this scaffold defers (see [Model](model.md#deliberately-not-here-yet)): white-beam high-speed imaging and ultrafast diffraction (32-ID-B), in-situ additive-manufacturing imaging (32-ID-B), and projection microscopy. Their Methods join when those instruments are modelled.

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join as the deployment approaches the point where CORA drives 32-ID. See [Open questions](questions.md) for what must be confirmed first.
