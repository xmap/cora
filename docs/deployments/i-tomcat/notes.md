# Notes

## Techniques

*What I-TOMCAT is designed to do, as intent. Modelling exercise.*

A technique is a portable [Catalog](../../catalog/methods.md) Method; a [Practice](../psi/index.md#the-techniques-adapted-here) is how a facility adapts it. The PSI Practices that bind these are carried pending on the [PSI site page](../psi/index.md#the-techniques-adapted-here) until PSI staff confirm them. The function view survives the eventual equipment choices, which is why it can be written from the public pages before the controls are wired.

I-TOMCAT is a hard X-ray tomographic-microscopy beamline. Its techniques are the tomography-family Methods the catalog already carries, the same ones the APS [2-BM](../2-bm/index.md) pilot earned:

| Technique | Catalog Method | What it is for |
| --- | --- | --- |
| Standard microtomography | [`tomography`](../../catalog/methods.md) | absorption-contrast 3D imaging on the U15 undulator, monochromatic 8-30 keV |
| Propagation-based phase contrast | [`tomography`](../../catalog/methods.md) | edge-enhanced imaging of weakly-absorbing samples (a propagation distance, not a separate fixture) |
| Fast / dynamic 4D tomography | [`streaming_tomography`](../../catalog/methods.md) | continuous high-speed acquisition via the GigaFRoST streaming camera, for in-situ dynamics |

A few points of intent shape the model:

- **The GigaFRoST camera is the dynamic-tomography enabler.** The PSI in-house continuous-streaming camera (up to 1255 fps full-frame, ~8 GB/s, up to ~33,875 Hz on a reduced ROI) is what distinguishes I-TOMCAT's fast and dynamic 4D tomography from a standard CT beamline. It maps to the catalog `streaming_tomography` Method, not a new one.
- **Phase contrast is a propagation distance, not a separate station.** Propagation-based phase-contrast imaging runs on the same endstation by moving the detector back from the sample; it is an acquisition mode over one set of optics, modelled under `tomography`, mirroring the 2-BM decision.
- **Grating interferometry is out of scope.** The legacy TOMCAT offered it only occasionally; it is not modelled here and is not one of the SLS Practices until staff confirm it is offered on the rebuilt beamline (TECH-1).

The concrete acquisition recipes (scan sequences, energies, exposure) are not written yet; they join if the deployment firms toward a real connection. See [Open questions](#open-questions) for what must be confirmed first.

## Governance

*Who would act at I-TOMCAT, and the trust shape that would gate it. Modelling exercise.*

Governance at I-TOMCAT follows the same model as the 2-BM pilot: people and autonomous agents are facility principals at the [PSI Site](../psi/index.md#safety-and-governance), and on the beamline they surface through the actions they take. Their commands are gated by a trust shape (a Zone grouping the beamline's resources, a Conduit binding the surfaces that may issue commands, and Policies that say who may do what).

I-TOMCAT is a modelling exercise, so this shape is not yet instantiated. The PSI operator and safety-review structure is not public and is carried pending on the [PSI site page](../psi/index.md#safety-and-governance); CORA does not invent a PSI operator pool or review chain ahead of confirmation.

What is already settled is the boundary: clearances (the safety forms that must be active to start) are issued at the PSI Site, not on the beamline, and the beamline links up to them rather than restating them. The PSI personnel-safety-system form and interlock names are an open question (PSS-1 on [Open questions](#open-questions)).

The concrete Zone, Conduit, and Policy instances, and the operator pool, would land if the deployment firms toward a real connection, following the [2-BM governance](../2-bm/governance.md) shape.

## Model

*The developer's by-kind index: where each CORA aggregate's I-TOMCAT content lives, the SLS 2.0 control-stack seam this exercise draws, and the record of what is deliberately deferred. Design-phase scaffold.*

For the aggregate shapes see the [architecture model](../../architecture/model.md) and the per-BC [modules](../../architecture/modules/index.md).

| Aggregate (BC) | Where at I-TOMCAT |
| --- | --- |
| Asset (Equipment) | the stage pages: [Source](source.md), [Sample](sample.md), [Detector](detector.md) |
| Capability, Method (Recipe) | [Techniques](#techniques) |
| Enclosure (Enclosure) | [the index](index.md#enclosures) |
| Zone, Conduit, Policy (Trust); Actor (Access) | [Governance](#governance) |
| Procedure, Recipe, Caution, Supply, Subject, Run, Campaign, Dataset, Decision | deferred (design-phase; see below) |

### The seam: what CORA would replace vs drive through

I-TOMCAT is the fleet's view of an SLS 2.0 beamline, so the control-stack boundary matters more than usual. SLS is an EPICS facility with the BEC (Beamline and Experiment Control) scan layer over ophyd introduced for SLS 2.0.

| Layer | SLS tool | CORA seam |
| --- | --- | --- |
| Control (floor) | EPICS IOCs | **drive through** (never replaced; the floor CORA actuates and observes) |
| Scan / orchestration (edge) | BEC over ophyd | **replace** (CORA's edge replaces BEC's scan/experiment steering; the BEC-shares-ophyd nuance keeps a drive-through reading open, SEAM-1) |
| Detector / capture | the camera streaming + HDF5 writer chain | **drive through / observe** (specialized capture CORA observes) |
| Data-of-record | SciCat + the Ra/SLURM Fiji reconstruction pipeline | **replace / invert source-of-truth** (CORA owns its own Dataset; SciCat is a fact a future integration reads, not CORA's record) |

This is the standard CORA lens (EPICS is the floor, the facility's scan/data software is named only to draw the boundary). The single most consequential call, BEC replace vs drive-through, is carried as SEAM-1 on [Open questions](#open-questions) because BEC adopts the same ophyd device model CORA's edge would.

### What is deliberately not here yet

- **Integration scenarios.** No `test_i_tomcat_*.py` registers I-TOMCAT Assets into the event store. Scenario code is where Assets become real, and hard-registering a modelling-exercise beamline with unconfirmed facts would commit speculative structure. It lands if the deployment firms toward a real connection.
- **Vendor Models.** No catalog Model is bound. The "(target)" models in the descriptor are [open questions](#open-questions), not bindings, because they are read from public pages and not staff-confirmed.
- **Operations and experiment views.** A runbook and live experiment view for a beamline CORA has not connected to would be invention; see the note on the [index](index.md#not-yet-documented).

## Open questions

*What CORA needs the I-TOMCAT team to confirm before the model can be trusted.*

I-TOMCAT is a modelling exercise modelled from PSI's public pages and the SLS 2.0 design reports, so this page is long by design: almost every value on the [device pages](index.md) is read from a public page, not a staff-confirmed fact, and some are legacy TOMCAT specs whose validity for the rebuilt beamline is itself uncertain. Each row below is a fact the beamline team or a design report owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before first users), and `Nice-to-have`.

### Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | What are the EPICS PV prefix scheme and the BEC ophyd device handles for each I-TOMCAT device? | The PV scheme is not public and the BEC plugin is internal; CORA leaves each device handle empty. | Wiring each Asset to a real control handle. |
| SEAM-1 | Blocks-build | Does CORA's edge replace BEC's scan/experiment orchestration, or drive through it at the ophyd/`bec_messages` boundary? | CORA's edge replaces BEC's scan steering, conducting over EPICS; the shared ophyd device model keeps a drive-through reading open. | The control-stack seam boundary. |
| PSS-1 | Blocks-build | What are the PSS permit signals and access-interlock names for the optics and experiment hutches? | Both hutches exist with permit signals to be named. | The Enclosure permit signals. |
| ENC-1 | Blocks-go-live | Is `X02SA` genuinely the rebuilt I-TOMCAT, and what is the optics/experiment hutch grouping? | `X02SA` is I-TOMCAT (corroborated by the `/sls/x02sa/` raw-data path); two hutches, optics shared with S-TOMCAT. | The enclosure model and sector binding. |

### Sources and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | What are the U15 undulator period and gap range, and when does the HTSU10 source upgrade land? | A U15 undulator now, HTSU10 in 2027; period/gap to be named. | The InsertionDevice settings. |
| MACHINE-1 | Nice-to-have | What are the SLS 2.0 storage-ring state handles (current, fill) CORA observes? | Observe-only ring state, handles to be named. | The StorageRing observation handles. |
| MONO-1 | Blocks-go-live | Do the legacy DCMM optics (multilayer stripes, Si(111), energy range) still describe the rebuilt beamline? | The legacy fixed-exit DCMM, 8-50 keV (8-30 recommended), carried until confirmed. | The Monochromator / Window / Filter specs. |
| OPT-1 | Nice-to-have | What are the focusing / harmonic-rejection mirror coatings and handles? They are not on the public pages. | A focusing mirror exists but is deferred (not invented) until named. | The Mirror model. |
| OPT-2 | Nice-to-have | What is the beam-defining slit blade-axis map and the handles? | Beam-defining slits ahead of the endstation; axis map to be named. | The Slit model. |

### Endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | Is the rotation stage the Aerotech ABRX150, and are its specs (~1500 deg/s) final? | The "(target)" ABRX150, used as the trigger master clock. | The rotary stage Model binding. |
| SAMPLE-1 | Blocks-go-live | What are the sample positioning axis set, the slip-ring channel count, and the fast-shutter model? | A centring stage, a continuous-rotation slip ring, and a dose-limiting fast shutter; details to be named. | The sample-stage models. |
| TRIG-1 | Blocks-go-live | Does the air-bearing rotary TTL feed the camera triggers directly, or is a conditioner needed? | Direct rotary-master triggering; may evolve once camera trigger requirements firm. | The trigger / sync chain. |

### Detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | Which camera models are installed (the pco.edge family, pco.dimax, and the PSI GigaFRoST)? | Three cameras at the stated design-target sensors/speeds; models unbound. | The camera Model bindings. |
| DET-2 | Blocks-go-live | What is the microscope optics model, and does it compose the cross-facility `Microscope` Assembly the way 2-BM does? | A `Housing` with `Objective` + `Scintillator` constituents, 1x-40x; Assembly composition deferred. | The microscope Model and Assembly composition. |

### Techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Which tomography Practices does the rebuilt beamline offer (e.g. is grating interferometry offered)? | Standard + phase-contrast + dynamic 4D tomography; grating interferometry out of scope. | The SLS Practices that bind the catalog Methods. |
