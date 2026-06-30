# Open questions

*What CORA needs the P21 team to confirm before the model can be trusted.*

P21 was reverse-engineered from P21's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p21](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p21), branch `debian/jessie`) and a verified research brief, not from a live connection. The P21 registry is thin: area-grouped generic motor banks, no detectors exposed. P21 is CORA's thirteenth PETRA III beamline, the Swedish Materials Science beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a P21.2 optics hutch, an EH3 endstation, and a LAB station (plus the P21.1 branch)? | A `p21-oh` / `p21-eh3` / `p21-lab` grouping, from the OnlineXML host names. | The Enclosure grouping. |
| HOST-1 | Blocks-go-live | The P21.1 station (`hasep211eh`) exposed only bookkeeping devices in this slice. Where is its device tree, and how do P21.1 / P21.2 relate? | Only P21.2 optics / EH3 / LAB modelled; P21.1 noted, not modelled. | The full beamline roster. |
| SRC-1 | Nice-to-have | The undulator source (absent from this slice). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`oh_u*`, `eh3_u*`, `lab*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator, mirrors, and slits within the P21.2 optics bank. | Grouped `LinearStage` optics stages; the breakdown pending. | The optics modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The high-energy diffraction detectors (area detectors, the PerkinElmer / Varex flat-panels typical of high-energy beamlines), absent from this registry slice. | A pending `Camera` placeholder; the detectors not invented. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P21 device, the three-host split, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool, the Swedish collaboration's role, and the safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do high-energy diffraction and total scattering enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `diffraction` / `total_scattering` slugs; none coined. | The technique Capabilities. |
