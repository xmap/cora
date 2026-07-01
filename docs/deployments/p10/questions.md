# Open questions

*What CORA needs the P10 team to confirm before the model can be trusted.*

P10 was reverse-engineered from P10's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p10](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p10), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no coherence lengths, energy calibration, or physical positions. P10 is CORA's sixth PETRA III beamline and a further XPCS beamline (after APS 8-ID and NSLS-II CHX). Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: an optics hutch feeding three experiment areas (E1 coherent imaging, E2 XPCS / diffraction, LAB)? | A `p10-opt` hutch and three `p10-e1` / `p10-e2` / `p10-lab` areas. | The Enclosure grouping. |
| LCX-1 | Nice-to-have | The LCX piezo sub-station: is it a distinct enclosure or a sample sub-stage within E2? | Modelled as a nano-positioning stage within the E2 enclosure. | The LCX placement. |
| LAB-1 | Nice-to-have | The LAB area: is the simulated diffractometer a live offline endstation, or test-only (to exclude)? | Modelled as an offline `Goniometer` + detectors. | The LAB scope. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`OPT_MOT`, `E1_MOT01..97`, `E2_MOT01..96`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the optics-bank breakdown (mirrors / slits / lenses), and the CRL focal sizes. | A DCM `Monochromator`, grouped optics stages, and an E1 CRL `Transfocator`; physical detail pending. | The optics modelling. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Nice-to-have | The E2 sample-piezo / two-theta geometry and the LCX nano-positioner detail. | SmarAct / AttoCube `LinearStage` piezos and a `RotaryStage` two-theta arm; geometry pending. | The E2 / LCX sample modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the high-frame-rate XPCS-detector assignment (Lambda vs Eiger), the detector models, and whether the Mythen strip detector warrants a distinct Family. | A wide `Camera` suite plus `EnergyDispersiveSpectrometer` MCAs; the Mythen modelled as a `Camera` for now. | The detector modelling. |
| HOST-1 | Nice-to-have | The Lambda and Lima cameras report on the bare `p10` host. Shared detector host, or registry artifact? | The cameras are homed in E2 (the XPCS detection stage); the host is flagged. | The detector-to-host mapping. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P10 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, and the role of the P10 beam shutter (read from the registry, safety role not). | Permit leaves to be named; the beam shutter bound to `Shutter`, safety role pending. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does coherent diffraction imaging / ptychography enter CORA's catalog as a Method? (XPCS already binds the graduated `xpcs` Method.) | Deferred: the coherent-imaging practice reuses the pending `ptychography` slug; XPCS is already earned. | The ptychography Capability. |
