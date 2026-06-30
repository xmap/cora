# Open questions

*What CORA needs the 8.3.2 team to confirm before the model can be trusted.*

8.3.2 was reverse-engineered from ALS's public facility pages ([als.lbl.gov/beamlines/8-3-2](https://als.lbl.gov/beamlines/8-3-2/), [microct.lbl.gov](https://microct.lbl.gov/)) and the public [als-computing](https://github.com/als-computing) GitHub org, not from a live connection. The device structure is read from the DXchange / DXfile HDF5 data record that the ALS tooling reads, but ALS runs BCS (a LabVIEW Beamline Control System, not EPICS) and publishes no per-beamline channel manifest, so the [Inventory](inventory.md) is a planned shape with control handles unbound. This is CORA's first ALS Site and its first BCS / LabVIEW controls house-style. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: a single experiment hutch, or a separate optics hutch feeding it? | A single `8-3-2-hutch`. | The Enclosure grouping. |
| SRC-1 | Nice-to-have | The Superbend field and critical energy. | A superconducting bending-magnet source, 6-43 keV; field pending. | The source Asset detail. |
| ALSU-1 | Nice-to-have | The ALS-U upgrade fate of 8.3.2: does it go dark, get rebuilt, or relocate, and on what schedule? | Dark time no sooner than October 2027; 8.3.2's fate carried pending. | The deployment roadmap. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MACHINE-1 | Nice-to-have | The ALS storage-ring state 8.3.2 reads (the `source_name` / `current` handles). | Observe-only machine state, a loose `StorageRing`; exact handles pending. | The machine-state observation. |
| MONO-1 | Blocks-go-live | The energy optic: the mechanism (multilayer vs crystal), d-spacing, and how the `energy`, `Z2`, `turret1` / `turret2`, and `TC2` / `TC3` channels relate. | An energy-setting `Monochromator`, 6-43 keV; `energy` the master axis. | The monochromator and energy modelling. |
| OPT-2 | Nice-to-have | The slit blade-axis map (the `hslits_*` and `vslits_*` channels) and handles. | Horizontal + vertical slits bound to `Slit`. | The slit Asset detail. |
| FILT-1 | Nice-to-have | The attenuating-filter materials and thicknesses on the `filter_y` axis. | A filter bound to `Filter`. | The filter Asset detail. |

## Sample endstation

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SAMPLE-1 | Blocks-go-live | The sample-motor stack: the rotary, the sample-centring axes (`sample_x` / `sample_y`), and the role of `axis1pos` / `axis2pos` / `axis5pos`. | A `RotaryStage` plus a `LinearStage`; axis sets and models pending. | The sample-stage modelling. |
| ROT-1 | Blocks-go-live | Which sample-stack axis is the tomographic rotation. | One of the `axisNpos` channels is the rotation; identity pending. | The rotation Asset binding. |
| TRIG-1 | Nice-to-have | The triggering / synchronization scheme for continuous-rotation tomography. | The rotary stage is the master clock feeding the camera trigger. | The trigger wiring. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector chain: the camera sensor / frame rate / model, the `scintillator_type`, and the `camera_objective` set. | A `Scintillator` + `Objective` + `Camera`; specs are per-dataset values, model carried pending. | The detector modelling. |
| DET-2 | Nice-to-have | The detector-stack axes (`camera_distance`, `camera_elevation`, `tilt_motor`): models, travels, and which is the propagation distance. | A `LinearStage` detector stack; `camera_distance` the propagation distance. | The detector-stack modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-build | The BCS / LabVIEW control handles per 8.3.2 device (absent from any public manifest). | The handles are unbound, carried pending; the control plane is ALS BCS. | Binding each Asset's control handle. |
| PSS-1 | Blocks-go-live | The ALS personnel-safety permit signals and the photon / front-end shutters (not published per beamline). | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cooling-water / beam / power supplies. | Photon beam, cooling water, vacuum, and power. | The Supply observations. |
| GOV-1 | Nice-to-have | The ALS operator pool and safety-review structure (site-level). | Carried pending on the ALS Site, not instantiated per beamline. | The governance principals. |
