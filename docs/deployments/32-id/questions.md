# Open questions

*What CORA needs the 32-ID team to confirm before the model can be trusted.*

32-ID is a design-phase scaffold built from the published [32-ID docs](https://github.com/decarlof/32id-docs), which mix pre-APS-U and current values, so almost every value in the [Inventory](inventory.md) is carried as a fact still to confirm. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are recorded on [Model](model.md#deliberately-not-here-yet) instead). It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed, with the reason in the commit. Priorities are `Blocks-build` (the answer changes the structure of the model, so CORA cannot finalize the shape without it), `Blocks-go-live` (a placeholder is fine for the description, but the real value is needed before CORA observes or drives the hardware), and `Nice-to-have`.

## Topology and scope

The one structural unknown: how the canted source and its branches map onto CORA's Asset model. The answer decides whether 32-ID is one root Asset or two.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | 32-ID is canted: two undulators feeding two branches. Do `32-ID-B` and `32-ID-C` run off separate beams (two canted branches), and does the `32-ID-A` optics set (mask, slits, monochromator, mode shutter) serve both branches or is it duplicated per branch? Which undulator feeds which branch? | One root Unit Asset `32-ID` with one optics train; the branch multiplicity is unmodelled pending this answer. | One-vs-two root Assets and one-vs-two beam walks in the [descriptor](inventory.md). |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | What are the EPICS PV handles (and drive crates / IOC hosts) for each modelled device? | Control handles are unassigned; CORA leaves each device handle empty. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-go-live | What are the PSS search-and-secure permit signals for the three hutches (`32-ID-A`, `-B`, `-C`)? | Three hutches exist with permit signals to be named. | The Enclosure permit signals. |
| BLEPS-1 | Nice-to-have | Are the BLEPS (equipment-protection) fault and status signals readable as PVs for an external observer, and which map to a utility versus a specific device? CORA observes outcomes only; it never models the interlock logic. | Utility faults map to Supply status, device faults to an Asset condition; the matrix is not modelled. | The Supply and Asset condition mapping. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The exact device types and parameters of the two canted undulators (the source table lists "Planar 1.35" downstream and "Planar 2.8" upstream; a "U33" tuning curve is published). How do these labels relate, and what are the periods and gaps? | Two `InsertionDevice` Assets, downstream and upstream, planar; periods and the U33 relationship unconfirmed. | The insertion-device specs. |
| SRC-2 | Nice-to-have | The fixed front-end mask aperture and position, and the front-end window stack (count, material, thickness). | A beam-defining `Mask` near 24 m and a `Window` (Be assumed); sizes unconfirmed. | The front-end mask and window specs. |
| MONO-1 | Blocks-go-live | The Si(111) monochromator detail: per-axis motors, energy range over the 7 to 40 keV span, and whether it drives from a saved per-energy table. | One `Monochromator` Asset, Si(111), 7 to 40 keV; axes and saved positions unconfirmed. | The monochromator axes and energy model. |
| MODE-1 | Blocks-build | The white-beam to monochromatic switch (the P4-50 mode shutter with its white-beam stop and combined mono stops). Is this a per-branch hard split (one branch always white, one always mono) or a switchable mode on one optics set, and what is the switching sequence and interlock? | A `ModeShutter` plus beam stops; switching is a coordinated, interlocked move, structure tied to TOPO-1. | The beam-mode model (and whether it is a new Capability or an `energy_change` extension, decided on [Model](model.md)). |
| LAYOUT-1 | Nice-to-have | A single z-coordinate reference for the layout. The published docs give per-hutch positions but no common origin. | z values are carried as approximate from-source and flagged confirm. | Exact device z positions. |

## TXM endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TXM-1 | Blocks-go-live | Is the published TXM component list current post-APS-U, or does it carry pre-APS-U hardware? Specifically the granite stages, the rotation stage (Aerotech assumed), and the sample-positioning stack (Kohzu assumed). | The published overview is taken as current; stage models and axes carried confirm. | The TXM stage Assets and models. |
| OPTICS-1 | Blocks-go-live | What is the beam-condensing optic upstream of the sample: a capillary condenser, a condenser zone plate, or KB optics? | One `Condenser` Asset bound to a loose Family; optical type unconfirmed. | The condenser optic identity and Family. |
| OPTICS-2 | Blocks-go-live | The objective Fresnel zone plate parameters (outermost-zone width, diameter, material) that set the TXM resolution. | One `ZonePlate` Asset bound to a loose Family; parameters unconfirmed. | The zone-plate spec and Family. |
| OPTICS-3 | Nice-to-have | The Zernike phase ring used for phase contrast: its parameters and whether it is inserted or retracted per scan. | One `PhaseRing` Asset bound to a loose Family; inserted/retracted state not modelled. | The phase-ring spec and state model. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The TXM detector camera model, sensor, and frame rate. | One `Camera` Asset; model and sensor unconfirmed. | The camera Model binding. |
| DET-2 | Nice-to-have | The TXM indirect-detection objective magnification set and the scintillator material and thickness. | An `Objective` and a `Scintillator` Asset; details unconfirmed. | The detector optics specs. |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | Is the TXM flight path helium-filled or evacuated, and what gas supplies does the endstation draw on? | A flight path exists; its gas is unconfirmed (the projection microscope uses helium, the TXM is unconfirmed). | The Supply records and flight-path model. |
