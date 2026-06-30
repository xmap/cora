# Open questions

*What CORA needs the P61 team to confirm before the model can be trusted.*

P61 was reverse-engineered from P61's own public OnlineXML device registry ([gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61](https://gitlab.desy.de/petra-iii-debian-packages/python-nxstools-extras-p61), branch `debian/stretch`) and a verified research brief, not from a live connection. The P61 registry is thin: one generic motor bank, no source / press / detectors exposed. P61 is CORA's seventeenth PETRA III beamline, the high-energy white-beam wiggler beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a single experiment hutch (the registry exposes one host), and the P61A / P61B branch split? | A `p61-eh2` experiment hutch, from the OnlineXML `hasnp61eh2` host. | The Enclosure grouping. |
| GROUP-1 | Nice-to-have | The per-axis roles of the `eh_mot*` motor bank. | Grouped as one `LinearStage` stage carrying the bank prefix; per-axis roles pending. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | The damping-wiggler source parameters (period, field), and whether the beam is white or monochromated per branch. | A damping wiggler delivering high-energy white beam; parameters pending. | The source Asset detail. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PRESS-1 | Blocks-build | The Large Volume Press (P61A): its press / anvil control, and whether it should bind the allowlisted-loose `PressureCell` Family. | A pending press; would reuse `PressureCell` (the P02 / 13-id-d precedent) when exposed. | The press modelling. |

## The detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The energy-dispersive (Ge solid-state) detector, and any area detectors, absent from this registry slice. | A pending `EnergyDispersiveSpectrometer` placeholder; the chain not invented. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango device handles per P61 device, and whether the OnlineXML `debian/stretch` branch (unusual for the set) matches the live Tango database. | The handles read from the public OnlineXML, carried pending; the floor is Tango + Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The DESY personnel-safety permit signals, the white-beam shielding / interlock, and the photon / front-end shutters (absent from the OnlineXML). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling / beam supplies. | Photon beam, cooling water, vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The DESY operator pool and safety-review structure (site-level). | Carried pending on the PETRA III Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does energy-dispersive diffraction enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the `energy_dispersive_diffraction` slug; none coined. | The technique Capability. |
