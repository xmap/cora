# Open questions

*What CORA needs the P01 team to confirm before the model can be trusted.*

P01 was reverse-engineered from P01's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p01](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p01), branch `debian/jessie`) and a verified research brief, not from a live connection. The registry carries real Tango device names and control handles, but no physical detail (crystal cuts, energy ranges, bend radii, detector models). P01 is CORA's first PETRA III beamline and a further Tango / Sardana control floor (after MAX IV and ALBA). Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: two optics hutches (OH1, OH2) feeding three experiment hutches (EH1, EH2, EH3), or a different layout? | Two `p01-oh*` optics hutches and three `p01-eh*` experiment hutches, read from the OnlineXML host names. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters, and whether gap_a/gap_b/taper_a/taper_b mean two sections or a canted arrangement. | An undulator source, 2.5-80 keV; gap / taper virtual axes only. | The source Asset detail. |
| GROUP-1 | Nice-to-have | The Asset grouping of the registry's per-axis device list into instruments (one monochromator, one mirror, one sample stage). | The groupings on the [Inventory](index.md), inferred from the axis name prefixes. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MONO-1 | Blocks-go-live | The double-crystal monochromator crystal cut (Si 111 / 311) and energy range. | A DCM bound to `Monochromator`; Bragg / energy virtual axes read from the registry. | The monochromator modelling. |
| OPT-1 | Nice-to-have | The deflection-mirror coatings / stripes and incidence angles, the KB bend radii and focal sizes, the CRL lens count / material, and the diamond-monitor / RIXS-pre-optic roles. | Two OH1 mirrors and the EH3 KB pair bound to `Mirror`; the CRL bound to `Transfocator`; the diamond monitor bound to `FluxMonitor`; handles read, physical detail pending. | The optics Asset detail. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| NRS-1 | Blocks-go-live | The four EH1 high-resolution monochromators (400 / 1064 / 3D / 3W): which is in beam per Moessbauer isotope and resolution, and how the `hrm_ener` virtual axis couples them. | Four `Monochromator` Assets plus a `HighResMonoEnergy` `PseudoAxis`; selection per isotope pending. | The NRS instrument modelling. |
| DIFF-1 | Blocks-go-live | The EH2 diffractometer geometry: the full circle count beyond theta / two-theta, and whether it composes a Diffractometer Assembly with a detector arm. | A `Goniometer` Asset (theta / two-theta), not the composed Diffractometer Assembly, until a detector arm is confirmed. | The diffractometer modelling. |
| SAMPLE-1 | Nice-to-have | The EH3 RIXS sample-stage axes and sample-environment detail. | A `LinearStage` (x / y / b / rot / tilt) read from the registry. | The sample-stage modelling. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector models per endstation (the EH1 NRS avalanche photodiode, the EH2 diffraction detector, the EH3 RIXS spectrometer detector), which the OnlineXML does not carry as motor rows. | Detector positioning stages bound to `LinearStage`; the detector devices named, not bound. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-position-monitor, ion-chamber, and diamond-monitor handles and roles. | `FluxMonitor` positioning stages read from the registry. | The diagnostics modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P01 device, and whether the OnlineXML `debian/jessie` branch matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do nuclear resonant scattering and RIXS enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the `inelastic_x_ray_scattering` and `resonant_inelastic_scattering` slugs; none coined. | The technique Capabilities. |
