# Open questions

*What CORA needs the P06 team to confirm before the model can be trusted.*

P06 was reverse-engineered from P06's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p06](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p06), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no focal sizes, detector models, or energy calibration. P06 is CORA's third PETRA III beamline and its fullest scanning-probe deployment. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics / mono hutch feeding two scanning-probe endstations (MC01 micro, NC1 nano)? | A `p06-mono` hutch and two `p06-mc01` / `p06-nc1` endstations, read from the OnlineXML host names. | The Enclosure grouping. |
| HOST-1 | Nice-to-have | Several detectors (Lambda, the detector pool) report on a bare `p06` / `petra3` Tango host. Is that a shared detector host, or a registry artifact? | The detectors are homed in the endstation that operates them; the host is flagged. | The detector-to-host mapping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`mono_mot`, `mi_mot01..84`, `nat_mot01..32`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The sample / instrument-stage Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap / harmonic / taper read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the multilayer monochromator d-spacing, and the KB-lens focal sizes (horizontal and vertical). | A DCM + a multilayer `Monochromator`, two KB `Hexapod` carriers; handles read, physical detail pending. | The optics modelling. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SCAN-1 | Blocks-go-live | The Aerotech fly-scan raster trajectories and the motion-detector triggering coupling (MC01 and NC1). | `LinearStage` scan stages with a continuous fly-scan role; parameters pending. | The scanning-acquisition modelling. |
| SAMPLE-1 | Nice-to-have | The NC1 SmarAct sample-piezo axes and the Pegasus sample-rotation detail (the nano-tomography axis). | A `LinearStage` piezo stack and a `RotaryStage` rotation; axis set pending. | The sample-stage modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the Maia element count, and the area-detector models (Eiger / Lambda / Pilatus / PCO variants). | A Maia `EnergyDispersiveSpectrometer` (one Asset, six sub-devices), XIA fluorescence, and `Camera` area detectors; models pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P06 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do scanning fluorescence / diffraction microscopy and nano-tomography enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `scanning_fluorescence_microscopy` and `tomography` slugs; none coined. | The technique Capabilities. |
