# Open questions

*What CORA needs the FAXTOR team to confirm before the model can be trusted.*

FAXTOR was reverse-engineered from ALBA's public facility pages ([cells.es/en/beamlines/bl31-faxtor](https://www.cells.es/en/beamlines/bl31-faxtor)) and a verified research brief, not from a live connection. ALBA publishes no per-beamline device manifest, so the [Inventory](inventory.md) is a planned shape with control handles unbound. This is CORA's first ALBA Site and its second Tango / Sardana / Taurus controls house-style after MAX IV. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared optics hutch feeding one experiment hutch, or a different layout? | A `faxtor-optics` zone and a `faxtor-experiment` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The multipole-wiggler period, pole count, and field. | A multipole-wiggler source; period and field pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ALBA storage-ring state FAXTOR reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The double multilayer monochromator coating, d-spacing, and the monochromatic / filtered-white energy partition. | A DMM bound to `Monochromator`; 8-50 keV mono, 30-70 keV filtered white. | The monochromator and energy modelling. |
| FILT-1 | Nice-to-have | The filtered-white-beam filter materials and thicknesses. | A filter set bound to `Filter`. | The filter Asset detail. |
| OPT-1 | Nice-to-have | The focusing / harmonic-rejection mirrors (presence, coatings, handles). | Mirrors bound to `Mirror`; absent from public sources, deferred. | The mirror Asset detail. |
| OPT-2 | Nice-to-have | The beam-defining slit blade-axis map and handles. | Slits bound to `Slit`. | The slit Asset detail. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The experiment-endstation stage stack: the rotary, the sample positioning, the table degrees of freedom, and the fast shutter. | A `RotaryStage`, `LinearStage`, `Table`, and `Shutter`; axis sets and models pending. | The sample-stage modelling. |
| TRIG-1 | Nice-to-have | The triggering / synchronization scheme for continuous-rotation tomography. | The rotary stage is the master clock feeding the camera trigger. | The trigger wiring. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The fast imaging detector: the camera sensor, frame rate, and model, and the scintillator material and thickness. | A `Scintillator` plus a `Camera` supporting up to 20 Hz tomography; model not published, carried pending. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Tango / Sardana / IcePAP device handles per FAXTOR device (absent from any public manifest). | The handles are unbound, carried pending; the control plane is ALBA Tango / Sardana. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ALBA personnel-safety permit signals and the photon / front-end shutters (not published per beamline). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling-water / beam supplies. | Photon beam, cooling water, and vacuum. | The Supply observations. |
| GOV-1 | Nice-to-have | The ALBA operator pool and safety-review structure (site-level). | Carried pending on the ALBA Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does radiography enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the 7-BM `radiography` slug; fast tomography reuses the catalog tomography Methods. | The technique Capabilities. |
