# Open questions

*What CORA needs the P03 team to confirm before the model can be trusted.*

P03 was reverse-engineered from P03's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p03), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no focal sizes, multilayer d-spacing, or energy calibration. P03 is CORA's fifth PETRA III beamline and its first SAXS / WAXS beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: shared optics feeding a microfocus endstation and a nanofocus GINIX endstation? | A `p03-optics` section (shared with P02) and two `p03-microfocus` / `p03-nanofocus` endstations. | The Enclosure grouping. |
| HOST-1 | Nice-to-have | The first defining slit reports on the P02 optics host (`haspp02oh1`) and a Lambda on the bare `petra3` host. Shared Tango DB hosts, or registry artifacts? | The shared P02 / P03 optics are homed in `p03-optics`; the hosts are flagged. | The device-to-host mapping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`expmi_mot01..64` microfocus, `mot01..40` nanofocus). | Grouped as sample-stage Assets carrying the bank prefix; per-axis roles pending. | The sample-stage Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| OPT-1 | Blocks-go-live | The multilayer monochromator d-spacing, the mirror coatings, and the CRL / GINIX-waveguide focal sizes. | A multilayer `Monochromator`, two `Mirror`s, a CRL `Hexapod`, and the GINIX waveguide; handles read, physical detail pending. | The optics modelling. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Nice-to-have | The GINIX waveguide-to-sample geometry and the sample-hexapod / rotation detail. | A `Hexapod` sample stage and a `RotaryStage` rotation; geometry pending. | The GINIX sample modelling. |
| TEMP-1 | Nice-to-have | The Eurotherm 2604 sample-environment sensor / setpoint handles. | A `TemperatureController` sample environment. | The temperature-control modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per experiment, the SAXS-vs-WAXS assignment (Pilatus 300k / 1M), the sample-to-detector distance, and the fluorescence-detector channel count. | `Camera` Pilatus detectors plus `EnergyDispersiveSpectrometer` MCA / XIA detectors; assignment pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P03 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the photon / front-end shutters, and the role of the GINIX experiment shutter (absent / partial in the OnlineXML). | Permit leaves and shutters to be named; the GINIX shutter bound to `Shutter`, safety role pending. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level), and the shared-optics permit coupling with P02. | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do small-angle and wide-angle X-ray scattering enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `small_angle_scattering` and `wide_angle_scattering` slugs; none coined. | The technique Capabilities. |
