# Open questions

*What CORA needs the 2-ID team to confirm before the model can be trusted.*

2-ID is a design-phase scaffold mined from the [EAA](https://github.com/AdvancedPhotonSource/EAA) APS-microprobe integration and its [2-ID-D launcher](https://github.com/AdvancedPhotonSource/eaa_driver_scripts_aps_2idd). The launcher is a simulation and EAA does not describe the source optics, so almost every value in the [Inventory](inventory.md) is carried as a fact still to confirm. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are recorded on [Model](model.md#deliberately-not-here-yet) instead). It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed, with the reason in the commit. Priorities are `Blocks-build` (the answer changes the structure of the model, so CORA cannot finalize the shape without it), `Blocks-go-live` (a placeholder is fine for the description, but the real value is needed before CORA observes or drives the hardware), and `Nice-to-have`.

## Topology and scope

The one structural unknown: the Sector 2 hutch roster and where the shared optics sit. The answer decides how many experiment hutches hang off the `2-ID` root and whether the source optics are one shared train or per-hutch.

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TOPO-1 | Blocks-build | What is Sector 2's experiment-hutch roster (2-ID-D plus which sister stations), which hutch do the source optics serve, what is the upstream optics-hutch identity, and what is the post-APS-U layout of the sector? | One root Unit Asset `2-ID` with one modelled experiment hutch `2-ID-D`; the sister hutch(es) and the optics-hutch are unmodelled pending this answer. | The hutch roster, the optics-hutch Enclosure, and one-vs-many hutch sub-trees in the [descriptor](inventory.md). |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | What are the EPICS PV handles (and drive crates / IOC hosts) for each modelled device, and the Bluesky / scanRecord configuration for the raster? | Control handles are unassigned; CORA leaves each device handle empty. | Wiring each Asset to a real control handle. |
| PSS-1 | Blocks-go-live | What is the PSS search-and-secure permit signal for the 2-ID-D hutch (and the other hutches once `TOPO-1` resolves the roster)? | The 2-ID-D hutch exists with a permit signal to be named. | The Enclosure permit signal. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The Sector 2 insertion-device source: device type, period, gap, and whether one source feeds more than one hutch. | One `InsertionDevice` Asset (undulator); type and period unconfirmed. | The insertion-device specs. |
| SRC-2 | Nice-to-have | The front-end and beam-defining optics between the source and the zone plate (front-end mask, window, white-beam and beam-defining slits), which EAA does not describe. | None modelled; the source stretch from front end to zone plate is carried as undescribed. | The front-end and beam-defining optics. |
| MONO-1 | Blocks-go-live | The monochromator: is it a double-crystal Si monochromator, what is its crystal and energy range, what are its axes, and which optics hutch is it in? | One `Monochromator` Asset, double-crystal, energy range unconfirmed; located upstream. | The monochromator presence, crystal, axes, and energy model. |
| OPTICS-1 | Blocks-go-live | The probe-forming Fresnel zone plate parameters (outermost-zone width, diameter, material) that set the spot size, and the order-sorting aperture that pairs with it. | One `ZonePlate` Asset (catalog Family) with a `zp_z` focus axis; the order-sorting aperture is folded in, not separately modelled. | The zone-plate spec and the order-sorting aperture. |

## Sample-scanning endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| AXIS-1 | Blocks-go-live | The sample-scanning axis complement: the horizontal scan axis (EAA evidences vertical `samy` and standoff `samz` but not the horizontal raster axis), and the coarse-stage vs fine-piezo split a microprobe carries. | One coarse `SamplePositioning` stack (`LinearStage`); the horizontal scan axis and coarse/fine split unconfirmed. | The sample-stage axes and the coarse/fine model. |
| ENV-1 | Nice-to-have | The sample environment: any in-situ stage (cryo, heating), and whether the endstation carries a rotation axis (which scanning fluorescence tomography would need). | No sample environment and no rotation axis modelled. | The sample-environment Fixtures and any rotation axis. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The energy-dispersive fluorescence detector: model, number of elements / segmentation, and energy resolution. | One fluorescence-detector Asset bound to the catalog `EnergyDispersiveSpectrometer` Family; model and channels unconfirmed. | The detector Model binding. |
| DET-2 | Nice-to-have | The detection readout chain: the preamplifier (EAA names a `Preamp1`), the EPICS scalers, and the I0 flux monitors (ion chambers) the scan normalizes against. | A preamplifier, scalers, and flux monitors exist as the readout chain; identities unconfirmed and not separately modelled. | The readout-chain Assets and the normalization model. |

## Supplies

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SUP-1 | Nice-to-have | What continuously-available supplies does the 2-ID-D endstation draw on (cooling water, and any sample-environment gases)? | A photon beam and cooling water; sample-environment supplies unconfirmed. | The Supply records. |
