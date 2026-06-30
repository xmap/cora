# Open questions

*What CORA needs the P24 team to confirm before the model can be trusted.*

P24 was reverse-engineered from P24's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p24](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p24), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry exposes generic motor banks and the MCAs, but not the diffractometer geometry or the area detector. P24 is CORA's sixteenth PETRA III beamline, the chemical crystallography beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding an EH2 main and an EH1 experiment hutch? | A `p24-oh` optics hutch and `p24-eh2` / `p24-eh1` endstations. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (absent from this slice). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`oh_mot*`, `mot*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The `eh2_dmy*` dummy stubs: test / placeholder devices, or real channels? | Noted as dummy stubs, not modelled. | The stub status. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and mirrors within the optics bank. | Grouped `LinearStage` optics stages; the breakdown pending. | The optics modelling. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The chemical-crystallography diffractometer geometry (and whether it warrants a `Goniometer` / `Diffractometer` binding once labelled). | A grouped `LinearStage` sample stage; the diffractometer binding pending. | The diffractometer modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The single-crystal area detector (a Pilatus / Eiger-class photon-counting detector), absent from this registry slice. | A pending `Camera` placeholder plus the `EnergyDispersiveSpectrometer` MCAs. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P24 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does chemical crystallography enter CORA's catalog as a dedicated Capability / Method (vs reusing `diffraction`)? | Deferred: carried as a pending Practice reusing the `diffraction` slug; none coined. | The technique Capability. |
