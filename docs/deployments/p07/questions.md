# Open questions

*What CORA needs the P07 team to confirm before the model can be trusted.*

P07 was reverse-engineered from P07's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p07](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p07), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, magnet field, or energy calibration. P07 is CORA's eleventh PETRA III beamline, jointly operated by Helmholtz-Zentrum Hereon and DESY. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding an EH2 main and an EH2B secondary hutch, plus other hutches (EH1 / EH3 / EH4)? | A `p07-oh2` optics hutch and `p07-eh2` / `p07-eh2b` endstations, from the registry slice. | The Enclosure grouping. |
| OPERATOR-1 | Blocks-go-live | The Hereon (2/3) + DESY (1/3) joint operation: how does it map to CORA's Federation / Trust model? | A beamline on the PETRA III Site with a shared operator pool; the Hereon stake noted. | The operator / governance model. |
| HOST-1 | Nice-to-have | The other P07 hutches (EH1 / EH3 / EH4) are not in the public EH2 registry slice. Where are they? | Only EH2 / EH2B modelled; the others noted, not modelled. | The full hutch roster. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`exp*`, `oh*`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap / taper read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The multi-bounce DCM crystal cut and energy range, and the OH optics. | A multi-bounce `Monochromator`; physical detail pending. | The optics modelling. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The four-circle Eulerian diffractometer geometry and whether it composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset (e4cv + two-theta), not the composed Diffractometer Assembly. | The diffractometer modelling. |
| MAG-1 | Blocks-go-live | The 17 T magnet field, cryogen, and control / ramp interface. | A 17 T superconducting `Magnet` (the graduated catalog Family, a further consumer); field and control pending. | The per-Asset magnet field / control detail. |
| SAMPLE-1 | Nice-to-have | The EH2 sample-hexapod geometry and the Linkam stage handles. | A `Hexapod` + a `TemperatureController`; geometry pending. | The sample modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per hutch, the Pilatus / PerkinElmer models (the `_old` controller suffix), and the EH2B detection. | `Camera` area detectors plus `EnergyDispersiveSpectrometer` MCAs; models pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P07 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY / Hereon personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent, the cooling / beam supplies, and the magnet liquid-helium supply. | Photon beam, cooling water, vacuum, and liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY / Hereon operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do high-energy diffraction and high-field materials science enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `diffraction` / `magnetic_scattering` slugs; none coined. | The technique Capabilities. |
