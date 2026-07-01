# Open questions

*What CORA needs the P09 team to confirm before the model can be trusted.*

P09 was reverse-engineered from P09's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p09), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no crystal cuts, magnet field, or energy calibration. P09 is CORA's seventh PETRA III beamline and the second consumer of the 4-ID polarization / magnetism vocabulary. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a MONO optics-and-resonant-scattering hutch, a DIF diffraction hutch, and a MAG magnetism endstation? | A `p09-mono` hutch and `p09-dif` / `p09-mag` endstations, read from the OnlineXML host names. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator; gap read, period pending. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The per-axis roles of the MONO / DIF motor banks (`p09/motor/exp`, `p09/motor/dif`). | Grouped as stage Assets carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |
| HOST-1 | Nice-to-have | A shared Lambda detector reports on the bare `petra3` host, and the registry includes a `p07/hexapodsmall` row. Shared host / cross-beamline import? | The Lambda is noted unbound; the P07 device is excluded from P09. | The device-to-host mapping. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The DCM crystal cut, the mirror coatings, the CRL detail, and the absorber configuration. | A DCM `Monochromator`, two `Mirror`s, a `Transfocator` CRL, and `Filter` absorbers; physical detail pending. | The optics modelling. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DIFF-1 | Blocks-build | The diffractometer circle counts (MONO / DIF / MAG) and whether each composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset per area (six-circle E6C), not the composed Diffractometer Assembly, until detector arms are confirmed. | The diffractometer modelling. |
| POL-1 | Nice-to-have | The phase-retarder geometry (circles + AttoCube fine axes) and the polarization-analyzer detail. | The allowlisted-loose `PhaseRetarder` + `PolarizationAnalyzer` Families (the 4-ID precedent); detail pending. | The polarization-instrument modelling. |
| MAG-1 | Blocks-go-live | The MAG magnet field (14 T assumed), its cryogen, and its control / ramp interface. | A 14 T superconducting `Magnet` (the 4-ID loose Family); field and control pending. | The magnet modelling. |
| SAMPLE-1 | Nice-to-have | The MAG sample-hexapod and PI-piezo geometry. | A `Hexapod` + `LinearStage` piezos; geometry pending. | The MAG sample modelling. |
| TEMP-1 | Nice-to-have | The CryoCon / Lakeshore / LSCI sensor / setpoint handles. | `TemperatureController` controllers; cryogenic cooling. | The temperature-control modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector roster per area, the PerkinElmer / Pilatus / Andor models, and the SIS3302 fluorescence channel count (collapsed from the registry's ROI explosion). | `Camera` area detectors plus an `EnergyDispersiveSpectrometer` SIS3302 / MCA; models pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P09 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent, the cooling / beam supplies, and the magnet liquid-helium supply. | Photon beam, cooling water, vacuum, and liquid helium. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do resonant scattering, magnetic scattering, and XMCD enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `resonant_scattering` / `magnetic_scattering` / `xmcd` slugs 4-ID / i06 / i10 share; none coined. | The technique Capabilities. |
