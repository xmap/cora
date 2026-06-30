# Open questions

*What CORA needs the P22 team to confirm before the model can be trusted.*

P22 was reverse-engineered from P22's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p22), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry shows P22 sharing the P09 optics chain, with the HAXPS endstation as a grouped bank and the electron analyzer not exposed. P22 is CORA's fourteenth PETRA III beamline, the HAXPES beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: shared P09 optics feeding the HAXPS experiment endstation? | A `p22-optics` (shared with P09) and a `p22-haxps` endstation. | The Enclosure grouping. |
| SHARED-1 | Blocks-go-live | The P22 / P09 shared optics: the undulator, DCM, mirrors, and phase retarder are P09 devices. How are the two beamlines coordinated (shared straight, switched source, simultaneous operation)? | The optics are shared, homed in `p22-optics` with the relationship flagged. | The shared-optics coordination model. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | A shared P09 undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the HAXPS manipulator bank (the polar / azimuthal / translation axes). | Grouped as one `Manipulator` Asset; per-axis roles pending. | The manipulator Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The shared DCM crystal cut, the mirror coatings, and the phase-retarder geometry. | A DCM `Monochromator`, two `Mirror`s, and a loose `PhaseRetarder`; physical detail pending. | The optics modelling. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The HAXPES electron analyzer model (a hemispherical analyzer, e.g. SPECS / Scienta), its lens modes, and its control interface (absent from this registry slice). | An `ElectronAnalyzer` Asset (the NSLS-II ESM Family); model and control pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P22 device, the shared P09 optics handles, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; optics shared with P09. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics permit coupling with P09, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent (HAXPES needs UHV at the analyzer) and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does hard X-ray photoelectron spectroscopy enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `angle_resolved_photoemission` slug P04 shares; none coined. | The technique Capability. |
