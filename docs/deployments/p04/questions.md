# Open questions

*What CORA needs the P04 team to confirm before the model can be trusted.*

P04 was reverse-engineered from P04's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p04), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no grating line densities, polarization modes, or energy calibration. P04 is CORA's second PETRA III beamline and its first soft X-ray / grating-monochromator deployment. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a soft X-ray optics section feeding two experiment endstations (EXP1, EXP2)? | A `p04-optics` section and two `p04-exp*` endstations, read from the OnlineXML host names. | The Enclosure grouping. |
| HOST-1 | Nice-to-have | The optics (undulator, PGM, mirrors, exit slits) report on the `haspp04exp2` Tango host. Is that a shared Tango DB host for the optics, or a registry artifact? | The optics are the optics section (`p04-optics`); the host is flagged. | The optics-to-host mapping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the manipulator banks (`exp1_mot01..16`, `ps2.01..14`, `exp2_mot06/08`). | Grouped as `Manipulator` Assets carrying the handles; per-axis roles pending. | The sample-stage Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The variable-polarization undulator: the polarization modes (H / V / circular) and the row-phase axes that set them. | An APPLE-II-type undulator, 250-3000 eV; gap read, row-phase axes pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The plane-grating monochromator grating line densities and mode (included angle / c-value), the three mirror coatings and roles, and the exit-slit calibration. | A `GratingMonochromator`, three `Mirror`s, and exit `Slit`s; handles read, physical detail pending. | The optics modelling. |

## Sample and detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| EXSU-1 | Nice-to-have | The EXP2 exit-shutter unit (EXSU2) sub-roles: slit (Spalt), translation, beam-position monitor, baffle. | Modelled as a beam-defining `Slit`; the bpm / baffle roles pending. | The EXSU2 modelling. |
| DET-1 | Blocks-go-live | The electrometer measured channels (drain current vs I0) and the photoemission analyzer (the endstation spectrometer, not a motor row). | `FluxMonitor` electrometers; the analyzer named, not bound. | The detection modelling. |
| DIAG-1 | Nice-to-have | The EXP2 diagnostic-screen positions and the camera-to-screen mapping. | Motorized `Screen`s imaged by `Camera`s; positions pending. | The diagnostics modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P04 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do soft X-ray absorption and photoemission enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `xas_spectroscopy` and `angle_resolved_photoemission` slugs; none coined. | The technique Capabilities. |
