# Open questions

*What CORA needs the FXI team to confirm before the model can be trusted.*

This model is reverse-engineered from public NSLS-II open source (the bluesky profile collection [`NSLS2/fxi-profile-collection`](https://github.com/NSLS2/fxi-profile-collection) and the shared `NSLS2/nslsii` package), so this page is long by design: the EPICS PVs are read straight from the profile collection, but vendor identities, controller boxes, physical positions, and the safety layer are not in it. Each row is a fact the beamline team or an IOC `st.cmd` file owns, not a CORA modelling choice. It is a delete-on-answer queue: when an item is answered, the answer lands in the descriptor and the row is removed (with the reason in the commit). Priorities are `Blocks-build` (needed before the model is built for real), `Blocks-go-live` (needed before CORA controls or observes the hardware), and `Nice-to-have`.

## Source and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| SRC-1 | Blocks-go-live | What is the 18-ID insertion device (undulator vs damping wiggler), and its period, gap, and power? Not in the profile collection. | An insertion-device source, identity-only; recorded as a PhotonBeam Supply. | The Source Asset and the InsertionDevice settings. |
| PSS-1 | Blocks-go-live | What are the PSS search-and-secure permit-leaf PVs for hutches 18-IDA and 18-IDB? Only the PPS photon-shutter status `XF:18IDA-PPS{PSh}Pos-Sts` is in source. | Both hutches exist; the permit signal is a confirm note, not a guessed PV. | The Enclosure permit signals. |
| ENC-1 | Nice-to-have | Is the `XF:18ID1-ES` namespace (where the Kinetix camera lives) a distinct endstation area, or part of 18-IDB? | Two enclosures (18-IDA optics, 18-IDB experiment); 18ID1-ES folded into 18-IDB. | The Enclosure set and roles. |
| LAYOUT-1 | Nice-to-have | What are the device z positions along the beam? The profile collection carries no layout or z reference. | No z values are recorded; the device order is the source/sample/detection grouping only. | Device z positions. |

## Optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DCM-1 | Blocks-go-live | What is the DCM crystal cut (Si 111?) and the energy range? | A double-crystal monochromator; cut and range carried blank. | The Monochromator settings. |
| OPTIC-1 | Nice-to-have | Are the two mirrors collimating (`cm`) and toroidal (`tm`) respectively? Both are the same ophyd class with no role string in source; the labels are inferred from the instance names. | The role labels are carried `confirm`, not asserted. | The Mirror role labels. |
| OPTIC-2 | Nice-to-have | What are the slit blade-axis PV suffixes, and the PV prefix for the secondary-source slit (`TXM_SSA`)? | The white-beam slit `XF:18IDA-OP{PBSL:1` is bound; the secondary-source slit is identity-only. | The Slit axes. |
| OPTIC-3 | Nice-to-have | Should BetrandLens become a catalog Family? Condenser, ZonePlate, and PhaseRing graduated once FXI joined 32-ID as a second deployment; BetrandLens is FXI-only, so it stays a loose family tag pending a second sighting. | Loose family name that renders as text; not yet graduated. | Catalog Family graduation (Federation-scoped). |
| OPTIC-4 | Nice-to-have | Confirm the zone-plate values: NanoTools, 244 um diameter, 30 nm outer zone width. These are code constants, not staff-verified. | The code-constant values, carried `confirm`. | The ZonePlate settings. |
| FILT-1 | Nice-to-have | What are the materials and thicknesses of the eight pneumatic filter foils (relays on a Moxa ioLogik E1211)? | Eight foils, materials unknown. | The Filter foil settings. |

## Sample and detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| STAGE-1 | Nice-to-have | What is the sample translation stage (`TXMSampleStage`, sx/sy/sz) vendor and travel? | A LinearStage stack, identity-only. | The SampleStage settings. |
| STAGE-2 | Blocks-go-live | What is the tomography rotary (`pi_r`, `XF:18IDB-OP{TXM:2-Ax:R}`) hardware (air-bearing vs piezo), encoder resolution, and max speed? The "PI / Physik Instrumente" reading is a naming inference. | A RotaryStage, PSO-triggered, specs blank. | The SampleRotary settings (critical for the tomography Capability). |
| DET-1 | Nice-to-have | What are the scintillator material and thickness? | A scintillator-relay lens stage, material unknown. | The Scintillator settings. |
| DET-2 | Nice-to-have | What is the detector-support (`DetSupport`, DetU/DetD) PV prefix? `DetU.z` is the propagation distance in the magnification calculation. | The support is recorded, PV prefix blank. | The DetectorSupport binding. |
| CAM-1 | Blocks-go-live | Which cameras are physically installed and active? Source has Andor Neo2, Andor Marana, and Photometrics Kinetix; the U/D pairs share identical PVs (KinetixD is a placeholder reusing KinetixU's PVs). Is there a second detector position? | One detector position, bound to the live Kinetix; the rest are a roster note. | The Camera Assets and the detector Fixture. |
| CAM-2 | Nice-to-have | What are the camera vendor part numbers? Vendor names are inferred from ophyd class names; only `MARANA-4BV6X` / `SONA-4BV6X` / `KINETIX` / `KINETIX22` are literal in the readout config. | Vendor classes, no part numbers. | The Camera Models. |
| DIAG-1 | Nice-to-have | What are the ion-chamber channel PV suffixes (`ic1..ic4`, i404 quad electrometer)? | Read-only intensity probes, suffixes blank. | The IonChamber bindings. |
| ENV-1 | Nice-to-have | Is the Lakeshore 336 sample-environment temperature controller installed? It is disabled in source (`motor_lakeshore = []`). | Not modeled as a live device. | The sample-environment controller. |

## Controls and data

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DRIVE-1 | Blocks-go-live | What are the motion-controller boxes behind the EpicsMotors (model, protocol, axis count, serial, firmware, IP), and which IOC drives each device group? Confirmed not in public open source: FXI has no IOC-config repo, and its per-beamline IOC inventory (Ansible `nsls2.ioc_deploy` device roles + a `<bl>-epics-containers` repo) is ops-private. Needs FXI staff or inventory access. | Families only; box identities unknown. | The MotionController Models and the Drive identities. |
| ZEBRA-1 | Nice-to-have | Are there two position-trigger boxes? One is instantiated; a second is referenced in the public config. What is each wired to? | One trigger box, reading the rotary as the master encoder. | The TimingController set. |

## Governance

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| GOV-1 | Blocks-go-live | Who is the FXI operator and beamline-scientist pool, and the role assignments? The public config exposes only a coarse group-level controls authority, not the human roster CORA's Access model needs. | A pending facility actor pool; CORA applies its own per-Actor authority. | The Access Actors and Trust policies. |
