# Detector

*One detector gantry serving both endstations. Design-phase; values are TDR design targets.*

TomoWISE has a single detector system on a gantry that travels the experiment hutch on 7 m floor rails, from the microtomography station at 45 m to the hutch wall at 52 m. It serves both endstations, so it is modelled once, in the detection stage of the [descriptor](../inventory.md).

## Gantry

- **Detector gantry** (Family `Table`): three axes Xd, Yd, Zd, with Zd on the 7 m floor rails. A removable flight tube (1 mbar) reduces air scatter for the long propagation distances.

## Microscopes

Interchangeable visible-light microscopes (scintillator, objective, 45 deg mirror, CMOS camera) couple the scintillator image to the cameras, built for sensors up to 60 mm diagonal. Each is **composed as the cross-facility `Microscope` Assembly** that 2-BM also uses, rather than a loose family: a `Housing` anchors an `Optics` sub-assembly (a turret, the objectives, and a virtual objective selector for switching magnification "without intervening in the setup") over a `Scintillator`. The Optique Peter optics model from 2-BM, `optique_peter_micrx080`, is **bound** on each Housing as the design-target candidate (the TDR names only the vendor; confirmation is DET-2).

Because TomoWISE's two microscopes share the four cameras and the one `DetectorGantry` propagation rail, the assembly's `camera` and `propagation_distance` slots are **decoupled**: the catalog assembly was generalized to make both `ZeroOrOne`, and each microscope leaves them empty. The cameras are modelled as separate shared Assets (below); the gantry provides the propagation distance.

- **MicLFOV** (Assembly `Microscope`, Housing model `optique_peter_micrx080`): large field of view, 1-2x magnification, NA > 0.2; objectives 1x / 2x.
- **MicHR** (Assembly `Microscope`, Housing model `optique_peter_micrx080`): high resolution, 4x / 10x / 20x, NA > 0.4.

## Cameras

Four cameras span the throughput-versus-speed-versus-resolution trade. The models are chosen in project year 2 (DET-1); the sensors below are the design targets.

- **Camera I** (Family `Camera`): 16-25 Mpix, 16-bit sCMOS, 100-150 fps. General throughput.
- **Camera II** (Family `Camera`): 4 Mpix, 12-bit CMOS, > 50,000 fps. High-speed dynamics.
- **Camera III** (Family `Camera`): ~4 Mpix, > 2,000 fps. Streaming.
- **Camera IV** (Family `Camera`): 150 Mpix, 54 x 40 mm sensor, 3.76 um pixel. Matches the large-sensor device already procured for DanMAX.

The camera models, the bound microscope-optics model confirmation (DET-2), and the trigger path are the main detector-side [open questions](../questions.md). See [Inventory](../inventory.md) for the Asset tree.
