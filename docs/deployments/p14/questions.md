# Open questions

*What CORA needs the P14 team to confirm before the model can be trusted.*

P14 was reverse-engineered from EMBL Hamburg's own public MXCuBE HardwareObjects configuration ([github.com/mxcube/mxcubecore](https://github.com/mxcube/mxcubecore/tree/develop/mxcubecore/configuration/embl_hh_p14), `configuration/embl_hh_p14` for EH1 and `configuration/embl_hh_pe2` for EH2), not from a live connection. EMBL publishes both endstation configs, so the two diffractometers and their axes are named (each experiment hutch resolves into a real `Goniometer`), but the exact geometry, the optics breakdown, the live-vs-mockup status of the EH2 axes, and the safety / operator boundary are not in them. P14 is CORA's second EMBL Hamburg beamline (the sibling of P13) and the first two-endstation MX beamline. Each row below is a fact the beamline team owns, not a CORA modelling choice (those are on [Model](model.md#deliberately-not-here-yet)). It is a delete-on-answer queue. Priorities are `Blocks-build`, `Blocks-go-live`, and `Nice-to-have`.

## Topology and scope

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| ENC-1 | Blocks-go-live | The hutch grouping: one optics hutch and two experiment hutches? The split is inferred from the device prefixes and the MX layout. | A `p14-oh` optics hutch feeding `p14-eh1` and `p14-eh2` experiment hutches. | The Enclosure grouping. |
| EH-1 | Blocks-go-live | The two-endstation layout: do EH1 and EH2 share one source / optics chain (energy + CRL), each with its own diffractometer host? | One shared optics chain feeding two hutches; per-hutch diffractometer and detector. | The multi-endstation topology and per-hutch trust scoping. |
| SRC-1 | Nice-to-have | The undulator source (the MXCuBE config exposes the energy service, not the undulator device). | An undulator beamline; the source carried pending. | The source Asset. |
| GROUP-1 | Nice-to-have | The per-axis roles of the KB mirror and slit motions (the P14KB / P14Atto motor groups). | Grouped as the optics-hutch focusing and slit stages; per-axis roles pending. | The Asset boundaries. |

## Source and optics

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| OPT-1 | Blocks-go-live | The optics breakdown: the monochromator and KB mirrors, the CRL lens count / material, and the aperture / slit-size tables. | Grouped `LinearStage` motions, a `Mirror` focusing optic, a `Transfocator` CRL, and `Slit` beam-defining boxes; the breakdown pending. | The optics modelling. |
| ENERGY-1 | Nice-to-have | The energy / monochromator coupling behind the `TINEEnergy` service (`/P14/Energy/P14Energy`), shared by both hutches. | A `PseudoAxis` energy service; the mono motions it drives pending. | The energy modelling. |

## Sample endstations

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| MX-1 | Blocks-build | The goniometer geometries of both endstations (the EH1 EMBLMiniDiff and the EH2 EMBLBSD): kappa range, axis offsets, the omega / kappa / centring axis assignment. | Both bound to the graduated `Goniometer` with named axes; the geometries carried as questions. | The MX instrument modelling. |
| MOCK-1 | Blocks-build | The EH2 axes published as `MotorMockup`: which are live on the floor and which are simulation placeholders in the config? | The EH2 diffractometer and table named and bound, but carried with a caution marker. | Whether the EH2 instrument is modelled live. |
| TABLE-1 | Nice-to-have | The EH2 experiment-table control handles (the EMBLTableMotor table_hor / table_ver carry no handle in the config object). | A `LinearStage` EH2 table; the handle pending. | The EH2 table modelling. |
| OAV-1 | Nice-to-have | The on-axis viewing objectives (MicrodiffZoom / ExporterZoom) magnification and the on-axis / sample-changer camera handles, both hutches. | `Objective` zooms plus `Camera` viewing; the camera handles pending. | The OAV modelling. |
| IMG-1 | Nice-to-have | The EH1 X-ray imaging camera (EMBLXrayImaging) control handle and role. | A `Camera` X-ray imaging device for centring; the handle pending. | The imaging modelling. |
| CRYO-1 | Nice-to-have | The cryostream (cooler model, sensor / setpoint handles); it is not a labelled device in the MXCuBE configs. | Carried as a question; the liquid nitrogen a Supply observation, not a device. | The temperature-control modelling. |
| ROBOT-1 | Blocks-go-live | The automated sample changer (load / centre / collect / unmount loop), per hutch. | A deferred sample-exchange Procedure over the spine + a Subject custody thread, not a device family; MXCuBE bookkeeping, not a device. | The sample-exchange modelling. |

## The detector

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| DET-1 | Blocks-go-live | The detector models (Eiger 16M silicon, Eiger 16M / 4M CdTe in EH1, Pilatus 2M in EH2, read from the configs), their ROI modes, and the sample-to-detector geometries. | `Camera` area detectors plus derived `PseudoAxis` distances; the geometries pending. | The detector modelling. |
| DIAG-1 | Nice-to-have | The beam-diagnostic service split (the beam intensity / centring services and the pin-diode flux). | Grouped `FluxMonitor` diagnostics; the per-service split pending. | The diagnostic modelling. |

## Control and safety

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| CTRL-1 | Blocks-go-live | The Exporter / TINE control handles per P14 device across the three diffractometer hosts, and whether the upstream MXCuBE `develop` configs match the live beamline. | The handles read from the public MXCuBE configs, carried pending; the floor is MXCuBE over Exporter + TINE. | Binding each Asset's control handle. |
| SEAM-1 | Blocks-go-live | The EMBL Hamburg control domain: MXCuBE over Exporter (microdiff) + TINE, distinct from the DESY Tango / Sardana floor (shared with P13). | A sub-operator control-domain within the PETRA III Site; EMBL's house style recorded on the Site. | The seam and Site modelling. |
| GOV-1 | Blocks-go-live | The EMBL Hamburg operator pool, the safety-review structure, and the boundary between the DESY-hosted ring interlock and the EMBL-operated beamline. | Carried pending on the PETRA III Site, shared with P13; the operator / interlock boundary a question. | The governance principals. |
| PSS-1 | Blocks-go-live | The personnel-safety permit signals and the photon / front-end shutters (absent from the MXCuBE configs), per hutch. | Permit leaves and shutters to be named; not invented here. | The Enclosure permit signals and the safety tier. |
| SUP-1 | Nice-to-have | The vacuum extent and the cryostream liquid-nitrogen / beam supplies. | Photon beam, cooling water, vacuum, and liquid nitrogen. | The Supply observations. |

## Technique

| ID | Priority | Question | CORA assumes | Resolves |
| --- | --- | --- | --- | --- |
| TECH-1 | Nice-to-have | Does rotation MX enter CORA's catalog as a Capability / Method? | Deferred: carried as a pending Practice reusing the i03 `mx_data_collection` slug; none coined. | The technique Capability. |
