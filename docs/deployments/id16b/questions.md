# Open questions

*What CORA needs the ID16B team to confirm before the model can be trusted.*

ID16B was reverse-engineered from the beamline's own public BLISS Beacon device database ([`gitlab.esrf.fr/id16b/beamline_configuration`](https://gitlab.esrf.fr/id16b/beamline_configuration)), so the control handles in the [Inventory](inventory.md) are the beamline's real BLISS object and Tango device names, read from the config rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Control and the BLISS / Tango floor

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the BLISS object and Tango device handles read from the public config current and correct against the live system? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle. |
| CTRL-2 | Nice-to-have | Which BLISS scan procedures ID16B uses per mode (daiquiri_tomo vs daiquiri_fluo / fluo3d), and which the CORA edge drives through versus replaces. | A continuous-rotation tomo scan and a piezo raster fluo scan; the conduct-versus-replace split is per routine. | The orchestration seam over the `ControlPort`. |

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: one optics hutch and one experiment hutch holding the nanofocus and sample? | One `id16b-optics` and one `id16b-experiment` enclosure. | The Enclosure grouping. |
| ENV-1 | Nice-to-have | The sample environments (cryostream, furnace, xeol) in the config: do they enter a later cut, and as which Family? | Noted, not modelled in this cut; no `Cryostat` Family yet. | The sample-environment roster. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The U205 undulator energy reach and gap mapping. | An undulator source feeding the DCM; energy reach to confirm. | The source Asset. |
| OPT-1 | Blocks-go-live | The Kohzu crystal-pair selection per energy, and the KB focal spot / working distance. | Kohzu Si111 / Si333 / Si311; KB mirrors as the nanofocus. | The optics and nanofocus modelling. |

## Sample and detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The operative rotation / coarse / piezo-scanner axis set per mode (tomo vs fluo). | Rotation (srot) + coarse (sx/sy/sz) + PI piezo scanner (sampy/sampz); rotation is the tomo master motion, the piezo scanner the fluo raster. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The operative XRF detector and area detector per mode, and the detector-stage axes. | FalconX silicon-drift for nano-XRF (EnergyDispersiveSpectrometer); PCO / Zyla for nano-tomography (Camera). | The detector modelling. |
| DET-2 | Nice-to-have | The role of the optical spectrometer (QEPro / Hamamatsu): xeol, beam diagnostics, or a science channel? | An optical-emission spectrometer reusing EnergyDispersiveSpectrometer. | The optical-spectrometer modelling. |

## Safety and resources

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PSS-1 | Blocks-go-live | The ESRF PSS permit signals behind the front-end / fast shutters (not in the config). | Permit leaves to be named; the shutter handles are known, the permit signals are not. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the beam path and the cooling-water / beam supplies a run draws on. | Photon beam, cooling water, and vacuum, carried pending. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level, shared across beamlines). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Do nano-tomography and nano-XRF map cleanly onto the existing `tomography` and `scanning_fluorescence_microscopy` Methods? | Both reused as pending Practices; ID16B is a further consumer of each. | The two Practices. |
