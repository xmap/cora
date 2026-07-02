# Open questions

*What CORA needs the MANACA team to confirm before the model can be trusted.*

MANACA was reverse-engineered from Sirius's public facility pages ([lnls.cnpem.br/facilities/manaca](https://lnls.cnpem.br/facilities/manaca/)) and a verified research brief, not from a live connection. LNLS publishes its control software (the Bluesky-based sophys family) openly, but no per-beamline EPICS PV manifest, so the [Inventory](index.md) is a planned shape with control handles unbound. MANACA is Sirius's first macromolecular-crystallography beamline, CORA's second modelled Sirius beamline after the [MOGNO](../mogno/index.md) tomography scaffold. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a shared optics hutch feeding one experiment hutch, or a different layout? | A `manaca-optics` zone and a `manaca-experiment` hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The undulator period and parameters. | An undulator source, 5-20 keV; period pending. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The Sirius storage-ring state MANACA reads. | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The monochromator crystal / multilayer type and handles. | A monochromator bound to `Monochromator`; 5-20 keV. | The monochromator modelling. |
| ENERGY-1 | Nice-to-have | Whether energy is scanned as the measurement (anomalous MX). | A master energy `PseudoAxis` the monochromator tracks. | The energy-axis modelling. |
| FILT-1 | Nice-to-have | The attenuator / transmission foil set. | An attenuator unit bound to `Filter`. | The attenuator Asset detail. |
| OPT-1 | Nice-to-have | The focusing mirrors and beam-defining slits (presence, handles). | No standalone mirror / slit device published; deferred. | The optics Asset detail. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GONIO-1 | Blocks-go-live | The goniometer geometry: the rotation, centring, and alignment axes. | A `Goniometer` (the graduated i03 family); axis set pending. | The goniometer modelling. |
| TEMP-1 | Nice-to-have | The cryostream sample-cooling sensor and setpoint handles. | A `TemperatureController` (the graduated family). | The temperature-control modelling. |
| SAMPLE-1 | Nice-to-have | The beamstop axes and the sample-environment detail. | A `BeamStop` at the sample; axis set pending. | The sample-stage modelling. |
| ROBOT-1 | Blocks-go-live | The automated 48-pin sample changer (load / centre / collect / unmount loop). | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family. | The sample-exchange modelling. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The area-detector model (a Pilatus / Eiger-class photon-counting detector), its translation stage, and the on-axis camera. | A `Camera` plus a `LinearStage` and an on-axis `Camera`; model not published, carried pending. | The detector modelling. |
| DIAG-1 | Nice-to-have | The incident-flux monitor handles. | A `FluxMonitor` (the graduated family). | The flux-monitor modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The EPICS PV and MXCuBE device handles per MANACA device (absent from any public per-beamline manifest). | The handles are unbound, carried pending; the control plane is the Sirius EPICS floor + MXCuBE3. | Binding each Asset's control handle. |
| ORCH-1 | Nice-to-have | Does MANACA run the Bluesky / Ophyd (sophys) orchestration layer, or another scan engine under MXCuBE? | Bluesky / sophys is a named facility direction (as MOGNO records); the MANACA status is unconfirmed. | The orchestration-layer modelling. |
| PSS-1 | Blocks-go-live | The Sirius personnel-safety permit signals and the photon / front-end shutters (not published per beamline). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |
| GOV-1 | Nice-to-have | The Sirius operator pool and safety-review structure (site-level). | Carried pending on the Sirius Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Do rotation MX and grid scan enter CORA's catalog as Capabilities / Methods? | Deferred: carried as pending Practices reusing the i03 `mx_data_collection` and `grid_scan` slugs; none coined. | The technique Capabilities. |
