# Techniques

*What CORA would run at I13-1: hard X-ray ptychography and coherent diffraction imaging, a [Catalog](../../catalog/methods.md) Method bound through a [Diamond Practice](../diamond/index.md#the-techniques-adapted-here). It is the fleet's first coherent lensless imaging, and its Capability is new and deferred, the more so because only the coherence-branch endstation is in source.*

| Technique | Catalog method | Notes |
| --- | --- | --- |
| Ptychography / coherent diffraction imaging (CDI) | `ptychography` | a coherent beam is raster-scanned across overlapping points on the sample and the far-field coherent-diffraction pattern is captured at each point; the real-space image is reconstructed downstream. The fleet's first coherent lensless imaging. New Capability, pending (TECH-1) |

The technique is recorded as a pending [Practice](../diamond/index.md#the-techniques-adapted-here) on the Diamond Site, `I13-1_ptychography_practice` (TECH-1).

## The acquisition shape

Ptychography is not a new kind of device, it is a way of acquiring. A coherent beam is rastered across the sample in overlapping points, the [sample stage](equipment/sample.md) moving point to point (SAMPLE-1); at each point the Merlin (the Medipix3 photon-counting detector) records the far-field coherent-diffraction pattern; and the stack of diffraction patterns, together with the known scan positions, is enough to reconstruct a real-space image of the sample. The overlap between adjacent points is what makes the reconstruction tractable.

CDI is the same lensless-imaging idea read from far-field coherent diffraction; CORA carries the pair under the one `ptychography` Method (TECH-1).

So the parts in source are a raster `LinearStage` (the PI piezo sample-scanning stage, SAMPLE-1) and two `Camera`s: the Merlin as the science detector that records each diffraction frame, and the Aravis / GenICam side camera for sample alignment (DET-1). The novelty lives in how they are driven and in what happens afterward, not in a new device class.

## Why the Capability is new, and deferred

Ptychography is a genuinely new science Capability for CORA. The fleet has tomography, an XRF microprobe, and a hard X-ray nanoprobe, but no coherent lensless imaging: nowhere yet does a beamline raster a coherent beam and reconstruct an image from the diffraction it scatters. CORA carries the `ptychography` Method as pending rather than coining it outright, the same earn-the-abstraction discipline every new-domain technique follows (TECH-1).

It would be tempting to read the novelty as a new device family, a "coherent imaging" class. That is the wrong axis. The coherence is a property of the beam and the acquisition, and the devices that realise it are a raster `LinearStage` and `Camera`s already in the Catalog. The new thing is a Method, an acquisition shape plus a reconstruction, and it adds no Family ([Model](model.md)).

The image reconstruction, turning the stack of far-field diffraction patterns into a real-space image, is `ComputePort` work, not a beamline Method. It runs downstream of the acquisition, not on a device on the floor.

## Not modelled yet

This is a deliberately partial first cut, the same posture as the sibling i20-1 scaffold. The public dodal module exposes only the coherence-branch endstation, the sample stage, the side camera, and the Merlin detector. What sits upstream is absent from source and deferred, not invented:

- The shared I13 source and the optics that condition the coherent beam (the undulator, monochromator, mirrors, and slits) are upstream of the endstation and not in the module. They are carried as open questions, not fabricated (SRC-1, OPT-1).
- The machine state is observe-only against a loose `StorageRing`; the shared source is deferred with it (MACHINE-1, SRC-1).
- The PSS search-and-secure permit signals and the photon / front-end shutters are absent from the dodal module and carried pending, not invented (PSS-1).
- Beam-conditioning and shutter conduct paths, and the supporting infrastructure around the endstation, follow once their devices are in source (CTRL-1, SUP-1).

Each of these is named on the [Open questions](questions.md) page rather than guessed at. The source walk that grounds what is and is not present is the generated [beamline](beamline.md) view.
