# Open questions

*What CORA needs the P08 team to confirm before the model can be trusted.*

P08 was reverse-engineered from P08's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p08), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts or energy calibration. P08 is CORA's twelfth PETRA III beamline, the high-resolution diffraction beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding the diffractometer experiment endstation? | A `p08-oh` optics hutch and a `p08-eh` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the `diff*` Kohzu diffractometer / sample bank. | Grouped as the `Goniometer` Asset carrying the bank prefix; per-axis roles pending. | The diffractometer Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The DCM and multilayer monochromator crystal cuts / d-spacing, and the CRL detail. | A DCM + a multilayer `Monochromator` and a `Transfocator` CRL; physical detail pending. | The optics modelling. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The six-circle Kohzu diffractometer geometry and whether it composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset (kozhue6cctrl + diff*), not the composed Diffractometer Assembly. | The diffractometer modelling. |
| SAMPLE-1 | Nice-to-have | The sample hexapod geometry. | A `Hexapod`; geometry pending. | The sample modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the models (Eiger 1M / Pilatus / Mythen2 / PerkinElmer / Vortex), and whether the Mythen strip detector warrants a distinct Family. | A `Camera` suite plus a `EnergyDispersiveSpectrometer` Vortex; the Mythen modelled as a `Camera` for now. | The detector modelling. |
| HOST-1 | Nice-to-have | A shared Lambda detector reports on the bare `petra3` host. Shared host, or registry artifact? | The Lambda is noted; the host is flagged. | The detector-to-host mapping. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P08 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does high-resolution diffraction enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `diffraction` slug; none coined. | The technique Capability. |
