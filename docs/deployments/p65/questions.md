# Open questions

*What CORA needs the P65 team to confirm before the model can be trusted.*

P65 was reverse-engineered from P65's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p65), branch `debian/jessie`) and a verified research brief, not from a live connection. The P65 registry slice is thin: an energy axis, a sample bank, a slit / table, the undulator. The XAS detection is not exposed. P65 is CORA's tenth PETRA III beamline and the applied half of the PETRA III XAS pair. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch (shared with P64) feeding the experiment endstation? | A `p65-oh` optics hutch and a `p65-eh` endstation. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; energy axis read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the banks (`oh_*`, `fe_*`, `a2_*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The `a2_dmy*` dummy stubs: test / placeholder devices, or real channels? | Noted as dummy stubs, not modelled. | The stub status. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The CDCM crystal cut and energy range, and the optics-bank breakdown. | A channel-cut `Monochromator` energy axis and grouped optics stages; physical detail pending. | The optics modelling. |
| HOST-1 | Nice-to-have | The CDCM energy / optics report on the shared P64 host (`hasnp64`). How is the shared optics split between P64 and P65? | The P65 optics are homed in `p65-oh`; the host is flagged. | The shared-optics mapping. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The XAS detection chain: the transmission ion chambers (I0 / I1 / I2), the fluorescence detector model, and the digitizer (absent from this registry slice). | A pending `FluxMonitor` placeholder; the chain not invented. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P65 device, the shared P64 / P65 optics host, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; optics shared with P64. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics coupling with P64, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does X-ray absorption spectroscopy enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `xas_spectroscopy` slug; none coined. | The technique Capability. |
