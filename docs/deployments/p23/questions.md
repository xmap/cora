# Open questions

*What CORA needs the P23 team to confirm before the model can be trusted.*

P23 was reverse-engineered from P23's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p23), branch `debian/jessie`) and a verified research brief, not from a live connection. The P23 registry is thin: one area-grouped generic motor bank, no detectors exposed. P23 is CORA's fifteenth PETRA III beamline, the in-situ diffraction beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a single experiment hutch (the registry exposes one host)? Is there a separate optics hutch? | A `p23-eh` experiment hutch, from the OnlineXML `hasep23oh` host. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator source (absent from this slice). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the `eh_mot*` motor bank. | Grouped as one `LinearStage` stage carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The single `hasep23dev` axis: a dev / commissioning device, or a real channel? | Noted as a dev / commissioning stage. | The dev-stub status. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and mirrors within the bank. | Grouped into the experiment stage; the breakdown pending. | The optics modelling. |
| DIFF-1 | Blocks-build | The diffractometer geometry within the bank. | Grouped into the experiment stage; the diffractometer pending. | The diffractometer modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The in-situ diffraction detectors (area detectors, any fluorescence detectors), absent from this registry slice. | A pending `Camera` placeholder; the detectors not invented. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P23 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent, the cooling / beam supplies, and the in-situ sample-environment supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does in-situ X-ray diffraction enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `diffraction` slug; none coined. | The technique Capability. |
