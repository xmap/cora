# Open questions

*What CORA needs the HXN team to confirm. This model is reverse-engineered from public open source (the [`NSLS2/hxn-profile-collection`](https://github.com/NSLS2/hxn-profile-collection) profile collection): the EPICS PVs are read from it, but vendor identities, physical positions, and the detector roster are not. Each row is a fact the beamline team owns. It is a delete-on-answer queue.*

Priorities: `Blocks-build` (changes the model structure), `Blocks-go-live` (needed before CORA controls or observes the hardware), `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Nice-to-have | IVU20 undulator period, gap range, and harmonic usage. The device (`SR:C3-ID:G1{IVU20:1}`) is confirmed; parameters are not in source. | An in-vacuum undulator, identity-only. | The InsertionDevice settings. |
| PSS-1 | Blocks-go-live | The PSS search-and-secure permit-leaf PVs per hutch. Only the photon shutter `XF:03IDB-PPS{PSh}` is in source. | The permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | Is the `XF:03IDB` intermediate zone (secondary-source aperture, slow shutter) a distinct enclosure, or part of the endstation? HXN spans three PV zones (3-ID-A/B/C). | Two enclosures (3-ID-A optics, 3-ID-C experiment); 3-ID-B folded. | The Enclosure set and roles. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Nice-to-have | DCM crystal cut and energy range. | A double-crystal monochromator; cut/range blank. | The Monochromator settings. |
| OPTIC-1 | Blocks-go-live | Are the zone plate and the multilayer Laue lens both permanently installed and operator-selected, or is one decommissioned? Both appear in source. | Both modelled, switchable. | The focusing-optic roster. |
| OPTIC-2 | Nice-to-have | Zone-plate parameters (outer-zone width, diameter, material). | A ZonePlate Asset, parameters blank. | The ZonePlate settings. |
| OPTIC-3 | Nice-to-have | Should `MultilayerLaueLens` become a catalog Family? HXN is its only sighting (a 1D crossed-pair lens, distinct from the circular ZonePlate). | A loose family name that renders as text; not yet graduated. | Catalog Family graduation (Federation-scoped). |

## Sample and detectors

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Blocks-go-live | The tomographic rotary (`sth`, on an ANC350) hardware, encoder resolution, and max speed. | A RotaryStage, specs blank. | The SampleRotary settings. |
| STAGE-2 | Nice-to-have | Does the SmarAct Smarpod 6-DOF pod fit the `Hexapod` Family (single coordinated parallel-kinematics move)? | Modelled as a Hexapod. | The SamplePod Family fit. |
| DET-1 | Blocks-go-live | The Xspress3 fluorescence detector: vendor (Quantum Detectors?), element count, energy resolution. Source shows 4 channels (C1-C4) plus a second unit. | One `EnergyDispersiveSpectrometer` Asset presenting the Sensor Role; specs blank. | The detector Model and element count. |
| CAM-1 | Blocks-go-live | Which pixel detectors are physically installed and active? Source has Merlin (x2), Eiger 1M, and Dexela; some classes are duplicated (`USE_RASMI`-gated). | Merlin1, Eiger1, Dexela1 modelled as Cameras; dormant duplicates excluded. | The detector roster and the per-scan detector slot. |
| DIAG-1 | Nice-to-have | The scaler / ion-chamber flux channel map (which channel is I0 for ptycho normalization). | Read-only flux counters, channel map blank. | The FluxCounter bindings. |

## Controls and techniques

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | The motion-controller box models, firmware, serials, and IPs. HXN exposes the controller PVs (Power PMAC `Ppmac:1` + `MC:2-8`; Attocube `ANC350:1-8`), which FXI did not, but vendor/firmware detail is still not in source. | Families bound (MotionController), models named where evident (PMAC, Attocube), specifics blank. | The MotionController Models and Drive identities. |
| ZEBRA-1 | Nice-to-have | Is `nanoZebra` (`Zeb:3`) the live trigger master, and is the PandABox (`67-nano-panda`, currently partly commented) the go-forward box? | One live Zebra; PandA deferred. | The TimingController set. |
| ENERGY-1 | Nice-to-have | Does an energy change co-move the zone-plate refocus per element edge, and is that table operator-data or a CORA Calibration? | Energy axis drives the monochromator; the optic co-move is noted, not modelled. | The energy-change Method shape. |
