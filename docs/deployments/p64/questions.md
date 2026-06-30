# Open questions

*What CORA needs the P64 team to confirm before the model can be trusted.*

P64 was reverse-engineered from P64's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p64](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p64), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, detector element count, or energy calibration. P64 is CORA's ninth PETRA III beamline and the advanced half of the PETRA III XAS pair. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding the experiment endstation, sharing the optics with P65? | A `p64-oh` optics hutch and a `p64-eh` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; energy axis read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the sample bank (`exp_mot*`, `dac_*`) and the picomotor assignments. | Grouped as `LinearStage` Assets carrying the bank prefix; per-axis roles pending. | The sample-stage Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The Tsai DCM crystal cut and energy range, and the two mirror coatings / roles. | A Tsai `Monochromator` and two `Mirror`s; physical detail pending. | The optics modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The multi-element fluorescence detector element count (the 104-channel SIS3302), the deadtime / ROI handling, the two Lambda 750k roles, and the transmission ion chambers. | A grouped `EnergyDispersiveSpectrometer` + two `Camera` Lambdas; element count and ion chambers pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P64 device, the shared P64 / P65 optics host, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; optics shared with P65. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics coupling with P65, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does X-ray absorption spectroscopy enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `xas_spectroscopy` slug BMM / ISS / i20-1 / P04 share; none coined. | The technique Capability. |
