# Open questions

*What CORA needs the P11 team to confirm before the model can be trusted.*

P11 was reverse-engineered from P11's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p11), branch `debian/jessie`) and a verified research brief, not from a live connection. The P11 registry is sparser in labelling than the other PETRA III beamlines: most devices are area-grouped motor banks whose per-axis roles are not exposed, so the goniometer and MX instruments are not individually resolvable. P11 is CORA's fourth PETRA III beamline and its first macromolecular-crystallography beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch and an experiment hutch? The registry exposes one Tango host (`haspp11oh`), so the split is inferred from device-name prefixes. | A `p11-oh` optics hutch and a `p11-eh` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (the OnlineXML exposes no undulator device). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`oh_mot*`, `granite_mot*`, `eh1/eh2/eh3_mot*`, the piezo bank). | Grouped as area positioning stages carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator, mirrors, and slits within the oh / granite banks. | Grouped `LinearStage` optics stages; the breakdown pending. | The optics modelling. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MX-1 | Blocks-build | The goniometer geometry and the MX instrument structure within the eh1 / eh2 / eh3 banks (the registry does not label them). | Grouped `LinearStage` experiment-hutch stages; the goniometer carried as a question. | The MX instrument modelling. |
| TEMP-1 | Nice-to-have | The cryostream sensor / setpoint handles. | An Oxford Cryostream 700 bound to `TemperatureController`. | The temperature-control modelling. |
| ROBOT-1 | Blocks-go-live | The automated sample changer (load / centre / collect / unmount loop), if present. | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family; not in the registry. | The sample-exchange modelling. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The Pilatus detector variant (300k / 1M / 2M / 6M), the sample-to-detector geometry, and the XIA fluorescence detector channel count. | A `Camera` Pilatus plus an `EnergyDispersiveSpectrometer` XIA detector; model pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P11 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do rotation MX and bio-imaging enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the i03 `mx_data_collection` and the `tomography` slugs; none coined. | The technique Capabilities. |
