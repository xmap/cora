# Open questions

*What CORA needs the ID19 team to confirm before the model can be trusted.*

ID19 was reverse-engineered from the beamline's own public BLISS Beacon device database ([`gitlab.esrf.fr/id19/beamline_configuration`](https://gitlab.esrf.fr/id19/beamline_configuration)), so the control handles in the [Inventory](inventory.md) are the beamline's real BLISS object and Tango device names, read from the config rather than confirmed by staff. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Control and the BLISS / Tango floor

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | Are the BLISS object and Tango device handles read from the public config current and correct against the live system? | The handles in the descriptor are taken from the config and carried confirm. | Verifying each Asset's control handle on the BLISS floor. |
| CTRL-2 | Nice-to-have | Which BLISS scan procedure(s) ID19 uses per endstation (continuous / fly versus step), and which the CORA edge drives through versus replaces. | A continuous-rotation scan clocked by the rotation stage; the conduct-versus-replace split is per routine. | The orchestration seam over the `ControlPort`. |

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: one optics hutch and one experiment hutch holding both endstations, or a finer split? | One `id19-optics` and one `id19-experiment` enclosure. | The Enclosure grouping. |
| ENDSTATION-1 | Nice-to-have | The further endstations in the config (MH, MED, laminography LATOMO, RADIO, PCOTOMO, the SmarAct towers, the fluorescence MCAs): are they distinct endstations CORA should model? | Noted, not modelled in this cut; MR and HR are the two main tomography stations. | The remaining endstation roster. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | Which insertion device(s) feed which endstation / mode, and the energy reach. | The undulators (u13a/u32a/u17-6c/u32c) and the w150b wiggler, selected per mode; the wiggler drives white-beam tomography. | The source Asset and mode mapping. |
| OPT-1 | Blocks-go-live | The TripleMono crystal-pair / Laue / multilayer mode mapping, the transfocator lens recipe per energy, and the attenuator foil set. | TripleMono Bragg 17-99 keV plus Laue / multilayer; 8 Be transfocator lenses; Cu/Al attenuator banks folding into Filter. | The optics modelling. |

## Endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The operative rotation and sample-positioning axis set per endstation (the config carries spare / commented axes). | MR: mrsrot + mrsx/mrsy/mrxc/mryc; HR: hrsrot + hrsx/hrsy/hrsz/hrz0; XYOnRotation centring on each. | The sample-stage modelling. |
| DET-1 | Blocks-go-live | The operative Lima detector(s) and the indirect-detection optics per endstation, and the propagation-stage axes. | Interchangeable Frelon / PCO / Basler Lima cameras bound to `Camera`; the propagation stage binds `LinearStage`. | The detector modelling. |

## Safety and resources

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| PSS-1 | Blocks-go-live | The ESRF PSS search-and-secure permit signals behind the frontend / bsh shutters (not in the config). | Permit leaves to be named; the TangoShutter handles are known, the permit signals are not. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent of the beam path and the cooling-water / beam supplies a run draws on. | Photon beam, cooling water, and vacuum, carried pending. | The Supply observations. |
| GOV-1 | Nice-to-have | The ESRF operator pool and safety-review structure (site-level, shared across beamlines). | Carried pending on the ESRF Site, not instantiated per beamline. | The governance principals. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Blocks-go-live | Does ID19 microtomography map cleanly onto the existing `tomography` Method, or does parallel-beam / phase-contrast imaging want a distinct Method? | The existing `tomography` Method, a further consumer; carried as a pending Practice. | The microtomography Practice. |
