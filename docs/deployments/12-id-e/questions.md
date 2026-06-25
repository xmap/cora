# Open questions

*What CORA needs the 12-ID-E team to confirm before the model can be trusted.*

12-ID-E was reverse-engineered from the beamline's own bluesky / BITS instrument ([BCDA-APS/usaxs-bits](https://github.com/BCDA-APS/usaxs-bits)), so the control handles in the [Inventory](inventory.md) are the beamline's real PVs, read from the `src/usaxs/configs/*.yml` device tables and `src/usaxs/devices/*.py` classes rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | Is 12-ID-E one experiment hutch served by a shared upstream 12-ID optics zone, or do the optics live in the same hutch? | Two enclosures: a shared `12-ID-optics` zone and the `12-ID-E` experiment hutch. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The 12-ID undulator period and type (absent from the USAXS instrument config). | An insertion-device sector; the undulator gap is not exposed as a device. | The source Asset detail. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The storage-ring state 12-ID-E reads (current, fill, top-up). | Observe-only machine state, a loose `StorageRing`; the exact PVs are pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The 12-ID monochromator crystal cut / d-spacing, the incident-energy range, and the real energy PVs (the instrument wraps it as a soft device). | A double-crystal `Monochromator`; cut and range carried pending. | The monochromator Asset. |
| ATTN-1 | Nice-to-have | The attenuator foil set (`12idPyFilter:`) and whether it folds into the `Filter` Family or earns a distinct `Attenuator` kind (the fleet-wide question). | An Al/Ti filter bank bound to `Filter`, the i03 / i15-1 precedent. | The attenuator's catalog home. |
| OPT-2 | Nice-to-have | The blade-axis roles of each slit (guard, USAXS-defining) and the detector / SAXS translation stage axes. | Four-blade variable openings bound to `Slit`; translation stages bound to `LinearStage`. | The slit and stage axis detail. |

## USAXS optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| BONSE-1 | Blocks-build | The Bonse-Hart crystal cut (channel-cut versus multi-bounce), the collimator / analyzer rocking-axis map, and the rocking-curve tolerance. | Matched channel-cut crystal stages on `RotaryStage`, each a rocking rotation plus alignment translations and a piezo fine-tilt. | The Bonse-Hart geometry; the CORA structural modelling is on [Model](model.md#deliberately-not-here-yet). |
| USAXS-1 | Blocks-go-live | Does the Bonse-Hart rocking-curve ultra-small-angle-scattering technique enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice, no `cora.capability.usaxs` coined. | The USAXS Capability. |

## Sample

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The sample-stage axis set, the PI C-867 sample rotator role, and what is mounted on them. | A `LinearStage` sample stage plus a `RotaryStage` rotator; the axis set carried pending. | The sample-stage modelling. |
| TEMP-1 | Nice-to-have | The Linkam T96 temperature range and the PTC10 channel map, and whether they coexist or swap per experiment. | Two `TemperatureController` Assets presenting the `Regulator` Role; range and channels pending. | The temperature-environment modelling. |
| LOADFRAME-1 | Nice-to-have | Is the in-situ load frame (in the device library but not the active instrument config) part of the operating beamline, and what is it? | Not modelled: deferred until it appears in the active config; no Family coined for an un-instantiated device. | The load-frame modelling. |

## Detection

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The UPD autoranging photodiode gain-decade map, the I0 / I00 / I000 / TRD flux-monitor channel assignment, the scaler channels, and the SAXS / WAXS area-detector prefixes. | The UPD photodiode + the I0 family + the scalers bound to `FluxMonitor` (gain autorange a device-state setting); the SAXS / WAXS Pilatus detectors bound to `Camera`. | The detector modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the EPICS PV handles read from the usaxs-bits instrument current and correct? | The handles in the descriptor are taken from the instrument config and carried confirm. | Verifying each Asset's control handle. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit signals and the front-end / photon shutters (absent from the instrument config). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the optics and flight paths. | Photon beam, cooling water, and vacuum on the optics and flight paths. | The Supply observations. |
| GOV-1 | Nice-to-have | The APS operator pool and safety-review structure (site-level, shared across the beamlines). | Carried pending on the APS Site, not instantiated per beamline. | The governance principals. |
