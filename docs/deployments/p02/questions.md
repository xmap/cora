# Open questions

*What CORA needs the P02 team to confirm before the model can be trusted.*

P02 was reverse-engineered from P02's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p02), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, pressure-cell detail, or energy calibration. P02 is CORA's eighth PETRA III beamline and the fleet's second diamond-anvil-cell deployment. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared OH1 optics hutch feeding a P02.1 powder endstation and a P02.2 extreme-conditions endstation? | A `p02-oh1` optics hutch and `p02-1-powder` / `p02-2-extreme` endstations, read from the device-name prefixes. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the motor banks (`eh1a/b`, `eh2a/b`, the OH1 bank). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| STUB-1 | Nice-to-have | The CH1 / CH2 `tangomotor` dummy stubs: test / placeholder devices, or real channels? | Noted as dummy stubs, not modelled. | The CH stub status. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the bendable HFM / VFM mirror coatings and focusing recipes, and the slit / CRL detail. | A DCM `Monochromator`, two bendable `Mirror`s, and `Slit`s; physical detail pending. | The optics modelling. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PRESSURE-1 | Blocks-go-live | The P02.2 diamond-anvil-cell control: the membrane / gas-loading / pressure-ramp interface, and the cell's positioning stages. | A `PressureCell` Asset (the catalog Family, graduated across 13-id and P02); membrane / load control pending. | The pressure-cell modelling. |
| TEMP-1 | Nice-to-have | The P02.1 sample-environment sensor / setpoint handles (Anton-Paar, Eurotherm, Lakeshore). | `TemperatureController` controllers; in-situ furnace / cryo. | The sample-environment modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per branch, the powder-vs-PDF detector roles (Pilatus 1M vs PerkinElmer), and the P02.2 high-pressure diffraction area detector. | `Camera` area detectors plus `EnergyDispersiveSpectrometer` fluorescence; roles pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P02 device, the shared OH1 optics with P03, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana; OH1 shared with P03. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the shared-optics access coupling with P03, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do powder diffraction and total scattering / PDF enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `powder_diffraction` / `total_scattering` slugs i11 / i15-1 / XPD share; none coined. | The technique Capabilities. |
