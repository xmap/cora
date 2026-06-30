# Open questions

*What CORA needs the I-TOMCAT team to confirm before the model can be trusted.*

I-TOMCAT is a modelling exercise modelled from PSI's public pages and the SLS 2.0 design reports, so this page is long by design: almost every value in the [Inventory](inventory.md) is read from a public page, not a staff-confirmed fact, and some are legacy TOMCAT specs whose validity for the rebuilt beamline is itself uncertain. Each row below is a fact the beamline team or a design report owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the EPICS PV prefix scheme and the BEC ophyd device handles for each I-TOMCAT device? | The PV scheme is not public and the BEC plugin is internal; CORA leaves each device handle empty. | Wiring each Asset to a real control handle. |
| SEAM-1 | Blocks-build | Does CORA's edge replace BEC's scan/experiment orchestration, or drive through it at the ophyd/`bec_messages` boundary? | CORA's edge replaces BEC's scan steering, conducting over EPICS; the shared ophyd device model keeps a drive-through reading open. | The control-stack seam boundary. |
| PSS-1 | Blocks-build | What are the PSS permit signals and access-interlock names for the optics and experiment hutches? | Both hutches exist with permit signals to be named. | The Enclosure permit signals. |
| ENC-1 | Blocks-go-live | Is `X02SA` genuinely the rebuilt I-TOMCAT, and what is the optics/experiment hutch grouping? | `X02SA` is I-TOMCAT (corroborated by the `/sls/x02sa/` raw-data path); two hutches, optics shared with S-TOMCAT. | The enclosure model and sector binding. |

## Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | What are the U15 undulator period and gap range, and when does the HTSU10 source upgrade land? | A U15 undulator now, HTSU10 in 2027; period/gap to be named. | The InsertionDevice settings. |
| MACHINE-1 | Nice-to-have | What are the SLS 2.0 storage-ring state handles (current, fill) CORA observes? | Observe-only ring state, handles to be named. | The StorageRing observation handles. |
| MONO-1 | Blocks-go-live | Do the legacy DCMM optics (multilayer stripes, Si(111), energy range) still describe the rebuilt beamline? | The legacy fixed-exit DCMM, 8-50 keV (8-30 recommended), carried until confirmed. | The Monochromator / Window / Filter specs. |
| OPT-1 | Nice-to-have | What are the focusing / harmonic-rejection mirror coatings and handles? They are not on the public pages. | A focusing mirror exists but is deferred (not invented) until named. | The Mirror model. |
| OPT-2 | Nice-to-have | What is the beam-defining slit blade-axis map and the handles? | Beam-defining slits ahead of the endstation; axis map to be named. | The Slit model. |

## Endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | Is the rotation stage the Aerotech ABRX150, and are its specs (~1500 deg/s) final? | The "(target)" ABRX150, used as the trigger master clock. | The rotary stage Model binding. |
| SAMPLE-1 | Blocks-go-live | What are the sample positioning axis set, the slip-ring channel count, and the fast-shutter model? | A centring stage, a continuous-rotation slip ring, and a dose-limiting fast shutter; details to be named. | The sample-stage models. |
| TRIG-1 | Blocks-go-live | Does the air-bearing rotary TTL feed the camera triggers directly, or is a conditioner needed? | Direct rotary-master triggering; may evolve once camera trigger requirements firm. | The trigger / sync chain. |

## Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which camera models are installed (the pco.edge family, pco.dimax, and the PSI GigaFRoST)? | Three cameras at the stated design-target sensors/speeds; models unbound. | The camera Model bindings. |
| DET-2 | Blocks-go-live | What is the microscope optics model, and does it compose the cross-facility `Microscope` Assembly the way 2-BM does? | A `Housing` with `Objective` + `Scintillator` constituents, 1x-40x; Assembly composition deferred. | The microscope Model and Assembly composition. |

## Techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Which tomography Practices does the rebuilt beamline offer (e.g. is grating interferometry offered)? | Standard + phase-contrast + dynamic 4D tomography; grating interferometry out of scope. | The SLS Practices that bind the catalog Methods. |
